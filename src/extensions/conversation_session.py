"""Engagement session tracking with idle detection.

Manages active engagement sessions per project with idle timeout detection.
One session per engagement (not per-conversation).
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

from src.core.tz import ist_now


class EngagementSession:
    """Tracks active engagement session (one per engagement)."""

    def __init__(self, project_id: str, idle_timeout_sec: int = 120):
        """Initialize engagement session.

        Args:
            project_id: Project/engagement ID
            idle_timeout_sec: Idle timeout in seconds (default 2 minutes)
        """
        self.project_id = project_id
        self.idle_timeout_sec = idle_timeout_sec
        self.last_activity_at = ist_now()

    def record_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity_at = ist_now()

    def get_idle_duration_seconds(self) -> int:
        """Return seconds since last activity."""
        elapsed = ist_now() - self.last_activity_at
        return int(elapsed.total_seconds())

    def is_idle(self) -> bool:
        """Check if session has exceeded idle timeout."""
        return self.get_idle_duration_seconds() >= self.idle_timeout_sec

    def close_session(self) -> dict:
        """Return session close metadata."""
        return {
            "engagement_id": self.project_id,
            "idle_duration_sec": self.get_idle_duration_seconds(),
            "closed_at": ist_now().isoformat(),
            "session_state": "idle_timeout" if self.is_idle() else "user_closed"
        }


class EngagementSessionRegistry:
    """Global registry of active engagement sessions (one per engagement)."""

    _sessions: Dict[str, EngagementSession] = {}
    _lock = asyncio.Lock()

    @classmethod
    async def start_session(cls, project_id: str, idle_timeout_sec: int = 120) -> EngagementSession:
        """Start or resume engagement session.

        If session already exists, resets idle timer (resume).
        If new, creates session with idle timeout.

        Args:
            project_id: Project/engagement ID
            idle_timeout_sec: Idle timeout in seconds (default 2 minutes)

        Returns:
            EngagementSession instance
        """
        async with cls._lock:
            key = project_id
            if key not in cls._sessions:
                cls._sessions[key] = EngagementSession(project_id, idle_timeout_sec)
            else:
                cls._sessions[key].record_activity()  # Resume: reset idle timer
            return cls._sessions[key]

    @classmethod
    async def record_activity(cls, project_id: str) -> None:
        """Record user activity in engagement.

        Called on any user action (message, decision, etc).
        Resets idle timer.

        Args:
            project_id: Project/engagement ID
        """
        async with cls._lock:
            key = project_id
            if key in cls._sessions:
                cls._sessions[key].record_activity()

    @classmethod
    async def close_session(cls, project_id: str) -> dict:
        """Close engagement session.

        Called when user navigates away from engagement.

        Args:
            project_id: Project/engagement ID

        Returns:
            Session close metadata
        """
        async with cls._lock:
            key = project_id
            if key in cls._sessions:
                session = cls._sessions.pop(key)
                return session.close_session()
            return {}

    @classmethod
    async def get_idle_sessions(cls) -> List[Tuple[str, EngagementSession]]:
        """Find all engagements with idle sessions.

        Returns:
            List of (project_id, EngagementSession) tuples for idle sessions
        """
        async with cls._lock:
            return [(k, s) for k, s in cls._sessions.items() if s.is_idle()]

    @classmethod
    async def get_session(cls, project_id: str) -> EngagementSession | None:
        """Get session for a project.

        Args:
            project_id: Project/engagement ID

        Returns:
            EngagementSession if exists, None otherwise
        """
        async with cls._lock:
            return cls._sessions.get(project_id)
