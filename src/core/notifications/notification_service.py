"""In-app notifications for document ingestion (read via /api/failure-tracking/user/{user_id}/notifications)."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from src.core.db.models import InAppNotification
from src.core.tz import ist_now

logger = logging.getLogger(__name__)


def notify_in_app(
    db: Session,
    *,
    user_id: str,
    project_id: str,
    notification_type: str,  # success, failure, warning, info
    title: str,
    message: str,
    document_file_id: str | None = None,
) -> None:
    now = ist_now()
    db.add(
        InAppNotification(
            id=f"ntf_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            project_id=project_id,
            document_file_id=document_file_id,
            notification_type=notification_type,
            title=title[:255],
            message=message,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    logger.info("[NOTIFY] %s for user %s: %s", notification_type, user_id, title)
