"""Unit tests for conversation session management and idle detection."""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys

# NEW: Fix async test discovery
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.extensions.conversation_session import EngagementSession, EngagementSessionRegistry
from src.core.tz import ist_now


pytestmark = pytest.mark.asyncio


class TestEngagementSession:
    """Test EngagementSession idle detection."""

    def test_session_creation(self):
        """Test session is created with correct idle timeout."""
        session = EngagementSession("proj_123", idle_timeout_sec=600)

        assert session.project_id == "proj_123"
        assert session.idle_timeout_sec == 600
        assert session.last_activity_at is not None

    def test_record_activity_updates_timestamp(self):
        """Test recording activity updates last_activity_at."""
        session = EngagementSession("proj_123", idle_timeout_sec=600)
        original_time = session.last_activity_at

        # Wait a bit to ensure time difference
        import time
        time.sleep(0.01)

        session.record_activity()

        assert session.last_activity_at > original_time

    def test_get_idle_duration_seconds(self):
        """Test calculating idle duration."""
        session = EngagementSession("proj_123", idle_timeout_sec=600)

        # Idle duration should be minimal
        idle_secs = session.get_idle_duration_seconds()
        assert idle_secs >= 0
        assert idle_secs < 2  # Should be close to 0

    def test_is_idle_false_when_active(self):
        """Test is_idle returns False for active session."""
        session = EngagementSession("proj_123", idle_timeout_sec=600)

        assert not session.is_idle()

    def test_is_idle_true_when_timed_out(self):
        """Test is_idle returns True when idle timeout exceeded."""
        session = EngagementSession("proj_123", idle_timeout_sec=1)

        # Mock last_activity_at to be > 1 second ago
        session.last_activity_at = ist_now() - timedelta(seconds=2)

        assert session.is_idle()

    def test_close_session_metadata(self):
        """Test close_session returns correct metadata."""
        session = EngagementSession("proj_123", idle_timeout_sec=600)

        meta = session.close_session()

        assert meta["engagement_id"] == "proj_123"
        assert "closed_at" in meta
        assert "idle_duration_sec" in meta
        assert "session_state" in meta
        assert meta["session_state"] in ["idle_timeout", "user_closed"]


class TestEngagementSessionRegistry:
    """Test EngagementSessionRegistry for managing active sessions."""

    @pytest.mark.asyncio
    async def test_start_session_creates_new(self):
        """Test starting a new session."""
        # Clear any existing sessions
        EngagementSessionRegistry._sessions.clear()

        session = await EngagementSessionRegistry.start_session("proj_123", 600)

        assert session is not None
        assert session.project_id == "proj_123"
        assert "proj_123" in EngagementSessionRegistry._sessions

    @pytest.mark.asyncio
    async def test_start_session_resumes_existing(self):
        """Test resuming existing session resets idle timer."""
        EngagementSessionRegistry._sessions.clear()

        # Create initial session
        session1 = await EngagementSessionRegistry.start_session("proj_123", 600)
        time1 = session1.last_activity_at

        # Resume session
        import time
        time.sleep(0.01)
        session2 = await EngagementSessionRegistry.start_session("proj_123", 600)
        time2 = session2.last_activity_at

        # Should be same session object but with updated time
        assert time2 > time1

    @pytest.mark.asyncio
    async def test_record_activity(self):
        """Test recording activity in active session."""
        EngagementSessionRegistry._sessions.clear()

        await EngagementSessionRegistry.start_session("proj_123", 600)

        import time
        time.sleep(0.01)
        await EngagementSessionRegistry.record_activity("proj_123")

        session = await EngagementSessionRegistry.get_session("proj_123")
        assert session.get_idle_duration_seconds() < 2

    @pytest.mark.asyncio
    async def test_close_session(self):
        """Test closing session."""
        EngagementSessionRegistry._sessions.clear()

        await EngagementSessionRegistry.start_session("proj_123", 600)
        meta = await EngagementSessionRegistry.close_session("proj_123")

        assert meta["engagement_id"] == "proj_123"
        assert "proj_123" not in EngagementSessionRegistry._sessions

    @pytest.mark.asyncio
    async def test_get_idle_sessions(self):
        """Test finding idle sessions."""
        EngagementSessionRegistry._sessions.clear()

        # Create active session
        await EngagementSessionRegistry.start_session("proj_active", 600)

        # Create idle session (timeout = 1 sec)
        session_idle = await EngagementSessionRegistry.start_session("proj_idle", 1)
        session_idle.last_activity_at = ist_now() - timedelta(seconds=2)

        idle_sessions = await EngagementSessionRegistry.get_idle_sessions()

        # Should find one idle session
        assert len(idle_sessions) == 1
        assert idle_sessions[0][0] == "proj_idle"

    @pytest.mark.asyncio
    async def test_get_session_returns_none_for_missing(self):
        """Test getting non-existent session."""
        EngagementSessionRegistry._sessions.clear()

        session = await EngagementSessionRegistry.get_session("proj_missing")

        assert session is None
