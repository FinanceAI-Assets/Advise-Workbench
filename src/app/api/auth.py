from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.auth import (
    create_access_token,
    create_refresh_token,
    create_sse_token,
    ensure_user,
    get_current_user,
    require_project_role,
    rotate_refresh_token,
)
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


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SseTokenBody(BaseModel):
    run_id: str | None = None


@router.post("/login")
@limiter.limit(_auth_login_rate_limit)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    user = ensure_user(body.email, body.password, db)
    return {
        "access_token": create_access_token(user.email),
        "refresh_token": create_refresh_token(user.email, db, user.id),
        "token_type": "bearer",
    }


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
        "isAdmin": bool(user.is_admin),
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
