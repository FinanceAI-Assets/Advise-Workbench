"""End-to-end integration tests for conversation summary feature."""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from src.core.db.models import (
    Conversation, ConversationMessage, ConversationSummary, EngagementMeta, User
)
from src.core.db.session import SessionLocal
from src.extensions.conversation_session import EngagementSessionRegistry
from src.core.tz import ist_now


@pytest.fixture
def db_session():
    """Provide a test database session."""
    db = SessionLocal()
    yield db
    db.close()


class TestConversationSummaryE2E:
    """End-to-end tests for conversation summary workflow."""

    @pytest.mark.asyncio
    async def test_e2e_session_creation_and_activity(self, db_session):
        """Test creating session and recording activity."""
        project_id = "proj_test_001"

        # Clear any existing sessions
        EngagementSessionRegistry._sessions.clear()

        # 1. Start engagement session
        session = await EngagementSessionRegistry.start_session(project_id, idle_timeout_sec=5)
        assert session is not None
        assert session.project_id == project_id

        # 2. Verify session is active (not idle)
        assert not session.is_idle()

        # 3. Record activity
        await EngagementSessionRegistry.record_activity(project_id)

        # 4. Verify activity resets idle timer
        idle_secs = session.get_idle_duration_seconds()
        assert idle_secs < 2

        # 5. Simulate idle (mock the timer)
        session.last_activity_at = ist_now() - timedelta(seconds=6)
        assert session.is_idle()

        # 6. Close session
        meta = await EngagementSessionRegistry.close_session(project_id)
        assert meta["engagement_id"] == project_id
        assert meta["session_state"] == "idle_timeout"

    def test_e2e_summary_creation_and_storage(self, db_session):
        """Test creating and storing conversation summary."""
        project_id = "proj_test_002"

        # 1. Create summary record
        summary = ConversationSummary(
            id=f"summary_{project_id}",
            project_id=project_id,
            summary_text="Discovered: client info | Decided: format pptx | Status: ready_to_plan",
            summary_metadata_json=json.dumps({
                "message_count": 5,
                "key_points": {
                    "discovery_slots": ["client", "audience"],
                    "decisions_made": ["format_pptx"],
                    "current_state": "ready_to_plan"
                }
            }),
            state_snapshot_json=json.dumps({
                "state": "ready_to_plan",
                "discovery_slots": {"client": "Acme Corp", "audience": "Executives"},
                "decision_answers": {"format": "pptx", "timeline": "2weeks"}
            }),
            discovery_slots_snapshot=json.dumps({
                "client": "Acme Corp",
                "audience": "Executives"
            }),
            decision_answers_snapshot=json.dumps({
                "format": "pptx",
                "timeline": "2weeks"
            }),
            conversation_fsm_state="ready_to_plan",
            summary_trigger="idle_10min",
            idle_duration_seconds=610,
        )

        # 2. Store summary (simulate upsert)
        db_session.add(summary)
        db_session.commit()

        # 3. Verify summary stored
        stored = db_session.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).first()

        assert stored is not None
        assert stored.summary_text == "Discovered: client info | Decided: format pptx | Status: ready_to_plan"
        assert stored.conversation_fsm_state == "ready_to_plan"
        assert stored.idle_duration_seconds == 610

    def test_e2e_summary_upsert_pattern(self, db_session):
        """Test upsert pattern - updating existing summary."""
        project_id = "proj_test_003"

        # 1. Create initial summary
        summary1 = ConversationSummary(
            id=f"summary_{project_id}",
            project_id=project_id,
            summary_text="Initial summary",
            summary_metadata_json="{}",
            state_snapshot_json=json.dumps({"state": "discovery"}),
            discovery_slots_snapshot="{}",
            decision_answers_snapshot="{}",
            conversation_fsm_state="discovery",
            summary_trigger="idle_10min",
        )
        db_session.add(summary1)
        db_session.commit()

        created_at = summary1.created_at

        # 2. Update summary (simulate upsert)
        existing = db_session.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).first()

        existing.summary_text = "Updated summary"
        existing.conversation_fsm_state = "ready_to_plan"
        existing.updated_at = ist_now()
        db_session.commit()

        # 3. Verify update
        updated = db_session.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).first()

        assert updated.summary_text == "Updated summary"
        assert updated.conversation_fsm_state == "ready_to_plan"
        assert updated.created_at == created_at  # created_at should not change
        assert updated.updated_at > created_at  # updated_at should change

    def test_e2e_state_snapshot_restoration(self, db_session):
        """Test restoring state from summary snapshot."""
        project_id = "proj_test_004"

        # 1. Create summary with state snapshot
        state_data = {
            "state": "structure_agreed",
            "discovery_slots": {"client": "Acme", "audience": "Board"},
            "decision_answers": {"format": "pptx", "timeline": "2weeks"},
            "slots": {"client": "Acme", "audience": "Board"},
            "deliverable": {"template_ids": ["pptx"], "representations": {}},
        }

        summary = ConversationSummary(
            id=f"summary_{project_id}",
            project_id=project_id,
            summary_text="Previous session: Discovered client and audience",
            summary_metadata_json="{}",
            state_snapshot_json=json.dumps(state_data),
            discovery_slots_snapshot=json.dumps(state_data["discovery_slots"]),
            decision_answers_snapshot=json.dumps(state_data["decision_answers"]),
            conversation_fsm_state="structure_agreed",
            summary_trigger="session_closed",
        )
        db_session.add(summary)
        db_session.commit()

        # 2. Retrieve summary (simulate restoration)
        retrieved = db_session.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).first()

        assert retrieved is not None

        # 3. Verify state can be restored
        restored_state = json.loads(retrieved.state_snapshot_json)
        assert restored_state["state"] == "structure_agreed"
        assert restored_state["discovery_slots"]["client"] == "Acme"
        assert restored_state["decision_answers"]["format"] == "pptx"

        # 4. Mark as restored
        retrieved.restored_at = ist_now()
        db_session.commit()

        # 5. Verify restoration tracking
        final = db_session.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).first()

        assert final.restored_at is not None

    def test_e2e_engagement_meta_idle_detection(self, db_session):
        """Test EngagementMeta idle detection configuration."""
        project_id = "proj_test_005"

        # 1. Create engagement with idle detection enabled
        meta = EngagementMeta(
            id=f"meta_{project_id}",
            project_id=project_id,
            engagement_session_id=None,
            last_activity_at=None,
            idle_timeout_seconds=600,  # 10 minutes
            enable_idle_detection=True,
        )
        db_session.add(meta)
        db_session.commit()

        # 2. Retrieve and verify
        retrieved = db_session.query(EngagementMeta).filter(
            EngagementMeta.project_id == project_id
        ).first()

        assert retrieved.idle_timeout_seconds == 600
        assert retrieved.enable_idle_detection is True

        # 3. Simulate activity (update last_activity_at)
        retrieved.last_activity_at = ist_now()
        db_session.commit()

        # 4. Verify activity tracked
        final = db_session.query(EngagementMeta).filter(
            EngagementMeta.project_id == project_id
        ).first()

        assert final.last_activity_at is not None

    def test_e2e_summary_expiration(self, db_session):
        """Test summary expiration (TTL cleanup)."""
        project_id = "proj_test_006"

        # 1. Create summary with expiration
        summary = ConversationSummary(
            id=f"summary_{project_id}",
            project_id=project_id,
            summary_text="Test summary",
            summary_metadata_json="{}",
            state_snapshot_json="{}",
            discovery_slots_snapshot="{}",
            decision_answers_snapshot="{}",
            conversation_fsm_state="discovery",
            summary_trigger="idle_10min",
            expires_at=ist_now() + timedelta(days=30),  # 30-day TTL
        )
        db_session.add(summary)
        db_session.commit()

        # 2. Verify expiration is set
        retrieved = db_session.query(ConversationSummary).filter(
            ConversationSummary.project_id == project_id
        ).first()

        assert retrieved.expires_at is not None

        # 3. Verify expiration is in future
        assert retrieved.expires_at > ist_now()
        assert (retrieved.expires_at - ist_now()).days >= 29
