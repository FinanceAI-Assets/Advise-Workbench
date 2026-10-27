"""Admin view of the configured model provider: which one is active, its models, capabilities and health."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.core.auth import require_admin
from src.core.db.models import User
from src.llm import gateway

router = APIRouter()


@router.get("/llm/status")
def llm_status(_admin: User = Depends(require_admin)) -> dict:
    """Readiness of the LLM provider. Spends no tokens; secrets are never included."""
    return gateway.health()
