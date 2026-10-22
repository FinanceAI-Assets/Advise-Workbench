import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.auth import (
    create_access_token,
    create_refresh_token,
    create_sse_token,
    development_admin_access_enabled,
    ensure_oauth_user,
    ensure_user,
    get_current_user,
    require_project_role,
    rotate_refresh_token,
)
from src.core.cache import cache_service
from src.core.config import settings
from src.core.rate_limit import limiter
from src.core.db.models import Run, User
from src.core.db.session import get_db

router = APIRouter()


def _auth_login_rate_limit() -> str:
    """Evaluated per request so tests and env overrides can change limits without reloading modules."""
    return (settings.auth_login_rate_limit or "30/minute").strip() or "30/minute"


def _auth_refresh_rate_limit() -> str:
    return (settings.auth_refresh_rate_limit or "60/minute").strip() or "60/minute"


def _microsoft_sso_enabled() -> bool:
    return bool(settings.microsoft_sso_client_id.strip() and settings.microsoft_sso_client_secret.strip())


def _microsoft_authority() -> str:
    tenant = settings.microsoft_sso_tenant_id.strip() or "organizations"
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"


def _microsoft_openid_configuration_url() -> str:
    tenant = settings.microsoft_sso_tenant_id.strip() or "organizations"
    return f"https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration"


def _frontend_next(value: str | None) -> str:
    candidate = (value or "/engagements").strip()
    return candidate if candidate.startswith("/") and not candidate.startswith("//") else "/engagements"


def _microsoft_error_redirect(message: str) -> RedirectResponse:
    target = f"{settings.microsoft_sso_frontend_redirect_uri}?{urlencode({'microsoft_error': message})}"
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SseTokenBody(BaseModel):
    run_id: str | None = None


class MicrosoftExchangeRequest(BaseModel):
    code: str


@router.post("/login")
@limiter.limit(_auth_login_rate_limit)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = ensure_user(body.email, body.password, db)
    return {
        "access_token": create_access_token(user.email),
        "refresh_token": create_refresh_token(user.email, db, user.id),
        "token_type": "bearer",
        "role": "admin" if user.is_admin else (user.role or "user"),
    }


@router.get("/microsoft/status")
def microsoft_status() -> dict[str, bool]:
    return {"enabled": _microsoft_sso_enabled()}


@router.get("/microsoft/start")
def microsoft_start(next_path: str = "/engagements") -> RedirectResponse:
    if not _microsoft_sso_enabled():
        return _microsoft_error_redirect("Microsoft sign-in is not configured")

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    cache_service.set(
        f"oauth:microsoft:state:{state}",
        {"nonce": nonce, "next": _frontend_next(next_path)},
        ttl_seconds=600,
    )
    params = {
        "client_id": settings.microsoft_sso_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_sso_redirect_uri,
        "response_mode": "query",
        "scope": settings.microsoft_sso_scopes,
        "state": state,
        "nonce": nonce,
    }
    return RedirectResponse(f"{_microsoft_authority()}/authorize?{urlencode(params)}")


@router.get("/microsoft/callback")
def microsoft_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        return _microsoft_error_redirect(error_description or error)
    if not code or not state:
        return _microsoft_error_redirect("Microsoft sign-in response was incomplete")

    state_data = cache_service.get(f"oauth:microsoft:state:{state}")
    if not state_data or not state_data.get("nonce"):
        return _microsoft_error_redirect("Microsoft sign-in session expired")

    try:
        with httpx.Client(timeout=10.0) as client:
            token_response = client.post(
                f"{_microsoft_authority()}/token",
                data={
                    "client_id": settings.microsoft_sso_client_id,
                    "client_secret": settings.microsoft_sso_client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.microsoft_sso_redirect_uri,
                    "scope": settings.microsoft_sso_scopes,
                },
            )
        token_response.raise_for_status()
        token_data = token_response.json()
        id_token = token_data.get("id_token")
        if not isinstance(id_token, str):
            raise ValueError("Microsoft did not return an identity token")
        claims = _validate_microsoft_id_token(id_token, str(state_data["nonce"]))
        email = str(claims.get("preferred_username") or claims.get("email") or "").strip().lower()
        if not email:
            raise ValueError("Microsoft account did not include an email address")
        user = ensure_oauth_user(str(email), claims.get("name"), db)
        exchange_code = secrets.token_urlsafe(32)
        cache_service.set(
            f"oauth:microsoft:exchange:{exchange_code}",
            {
                "email": user.email,
                "access_token": create_access_token(user.email),
                "refresh_token": create_refresh_token(user.email, db, user.id),
                "next": str(state_data.get("next") or "/engagements"),
            },
            ttl_seconds=60,
        )
        target = f"{settings.microsoft_sso_frontend_redirect_uri}?{urlencode({'microsoft_code': exchange_code, 'next': state_data.get('next', '/engagements')})}"
        return RedirectResponse(target, status_code=status.HTTP_302_FOUND)
    except (httpx.HTTPError, ValueError, JWTError, HTTPException) as exc:
        if isinstance(exc, HTTPException):
            return _microsoft_error_redirect(str(exc.detail))
        return _microsoft_error_redirect("Microsoft sign-in could not be completed")


@router.post("/microsoft/exchange")
def microsoft_exchange(body: MicrosoftExchangeRequest) -> dict[str, str]:
    key = f"oauth:microsoft:exchange:{body.code}"
    data = cache_service.pop(key)
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Microsoft sign-in code is invalid or expired")
    return {
        "access_token": str(data["access_token"]),
        "refresh_token": str(data["refresh_token"]),
        "email": str(data["email"]),
        "next": str(data.get("next") or "/engagements"),
    }


def _validate_microsoft_id_token(token: str, expected_nonce: str) -> dict:
    unverified_claims = jwt.get_unverified_claims(token)
    issuer = str(unverified_claims.get("iss") or "")
    if not issuer.startswith("https://login.microsoftonline.com/") or not issuer.endswith("/v2.0"):
        raise JWTError("Unexpected Microsoft token issuer")
    if unverified_claims.get("nonce") != expected_nonce:
        raise JWTError("Invalid Microsoft token nonce")

    with httpx.Client(timeout=10.0) as client:
        metadata = client.get(_microsoft_openid_configuration_url())
        metadata.raise_for_status()
        jwks = client.get(metadata.json()["jwks_uri"])
        jwks.raise_for_status()
    header = jwt.get_unverified_header(token)
    key = next((item for item in jwks.json()["keys"] if item.get("kid") == header.get("kid")), None)
    if not key:
        raise JWTError("Microsoft signing key not found")
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=settings.microsoft_sso_client_id,
        issuer=issuer,
    )


@router.post("/refresh")
@limiter.limit(_auth_refresh_rate_limit)
def refresh_session(request: Request, body: RefreshRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user, new_refresh = rotate_refresh_token(db, body.refresh_token)
    return {
        "access_token": create_access_token(user.email),
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/sse-token")
def issue_sse_token(
    body: SseTokenBody,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    rid = (body.run_id or "").strip()
    if rid:
        run = db.scalar(select(Run).where(Run.id == rid))
        if run is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot issue token for this run",
            )
        try:
            require_project_role(run.project_id, {"Owner", "Editor", "Viewer"}, user, db)
        except HTTPException:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot issue token for this run",
            ) from None
    return {
        "sse_token": create_sse_token(user.email, run_id=rid or None),
        "expires_in": int(settings.jwt_sse_exp_seconds),
    }


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    job_title: str | None = None


def _profile(user: User) -> dict:
    name = (user.full_name or "").strip() or user.email.split("@")[0]
    return {
        "id": user.id,
        "email": user.email,
        "name": name,
        "jobTitle": user.job_title or "",
        "isAdmin": bool(user.is_admin or user.role == "admin"),
        "role": "admin" if user.is_admin else (user.role or "user"),
        "canSwitchAdmin": bool(user.is_admin or user.role == "admin" or development_admin_access_enabled()),
    }


@router.get("/me")
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    # get_current_user may return a cached copy without profile fields, so read the row.
    row = db.scalar(select(User).where(User.id == user.id))
    return _profile(row or user)


@router.patch("/me")
def update_me(
    body: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.scalar(select(User).where(User.id == user.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if body.full_name is not None:
        row.full_name = body.full_name.strip()[:255] or None
    if body.job_title is not None:
        row.job_title = body.job_title.strip()[:128] or None
    db.commit()
    return _profile(row)
