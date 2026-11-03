"""Conversation summary generation and persistence worker.

Handles:
1. Idle engagement detection
2. Summary generation (hybrid: extract + LLM)
3. Summary persistence (upsert pattern)
4. State snapshot management
"""

import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from src.core.db.models import Conversation, ConversationMessage, ConversationSummary, EngagementMeta
from src.core.tz import ist_now
from src.extensions.conversation_session import EngagementSessionRegistry
from src.memory.short_term.conversation_state import ConversationState

logger = logging.getLogger(__name__)


async def check_idle_engagements_and_summarize(db: Session) -> dict:
    """Background task: Check idle engagements, generate and save summaries.

    Runs periodically (every 2 minutes) to detect idle engagements and create summaries.

    Args:
        db: Database session

    Returns:
        Dict with summary_count of generated summaries
    """
    summary_count = 0

    # Get all idle sessions
    idle_sessions = await EngagementSessionRegistry.get_idle_sessions()

    for project_id, session in idle_sessions:
        try:
            # Check if idle detection enabled for this engagement
            engagement = db.query(EngagementMeta).filter(
                EngagementMeta.project_id == project_id
            ).first()

            if not engagement or not engagement.enable_idle_detection:
                logger.debug(f"Idle detection disabled for engagement {project_id}")
                continue

            # Generate summary from current state
            summary = await _generate_engagement_summary(
                db, project_id, "idle_10min", session.get_idle_duration_seconds()
            )

            if summary:
                # UPSERT: Save or update summary
                await _upsert_conversation_summary(db, summary)
                summary_count += 1
                logger.info(f"Summary saved for engagement {project_id} (idle {session.get_idle_duration_seconds()}s)")

            # Close session after summarizing
            await EngagementSessionRegistry.close_session(project_id)

        except Exception as e:
            logger.error(f"Failed to summarize idle engagement {project_id}: {e}", exc_info=True)

    return {"summaries_generated": summary_count}


async def _generate_engagement_summary(
    db: Session,
    project_id: str,
    trigger: str = "idle_10min",
    idle_duration_sec: int = 0
) -> ConversationSummary | None:
    """Generate summary for engagement.

    Extract key points from recent conversations + generate 2-3 line narrative.

    Args:
        db: Database session
        project_id: Project/engagement ID
        trigger: Summary trigger ("idle_10min" | "session_closed" | "manual")
        idle_duration_sec: Seconds of idle time (for metadata)

    Returns:
        ConversationSummary instance or None if no conversation found
    """

    # 1. Get latest conversation for this engagement
    conversation = db.query(Conversation).filter(
        Conversation.project_id == project_id
    ).order_by(
        Conversation.updated_at.desc()
    ).first()

    if not conversation:
        logger.warning(f"No conversation found for engagement {project_id}")
        return None

    # 2. Load current conversation state from JSON file
    conv_state = await _load_conversation_state_json(project_id, conversation.id)

    # 3. Fetch recent messages (limit 50 to avoid token overflow)
    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation.id
    ).order_by(
        ConversationMessage.created_at.desc()
    ).limit(50).all()

    if not messages:
        logger.warning(f"No messages found in conversation {conversation.id}")
        return None

    # 4. Extract discovery slots and decisions from message metadata
    discovery_slots = {}
    decision_answers = {}
    for msg in reversed(messages):  # Chronological order
        if msg.metadata_json:
            try:
                meta = json.loads(msg.metadata_json)
                if "discovery" in meta:
                    discovery_slots.update(meta["discovery"])
                if "decision_answers" in meta:
                    decision_answers.update(meta["decision_answers"])
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse metadata for message {msg.id}")

    # 5. Generate hybrid summary
    # Extract key points
    key_points = {
        "discovery_slots": list(discovery_slots.keys()),
        "decisions_made": list(decision_answers.keys()),
        "current_state": conv_state.state if conv_state else "unknown"
    }

    # Generate 2-3 line narrative (hybrid: structured + LLM)
    summary_text = _generate_summary_text(key_points, discovery_slots, decision_answers)

    # 6. Create summary record
    summary = ConversationSummary(
        id=f"summary_{project_id}",  # Fixed ID per engagement for upsert
        project_id=project_id,
        summary_text=summary_text,
        summary_metadata_json=json.dumps({
            "message_count": len(messages),
            "key_points": key_points,
            "generated_at": ist_now().isoformat()
        }),
        state_snapshot_json=json.dumps(conv_state.to_dict() if conv_state else {}),
        discovery_slots_snapshot=json.dumps(discovery_slots),
        decision_answers_snapshot=json.dumps(decision_answers),
        conversation_fsm_state=conv_state.state if conv_state else "unknown",
        summary_trigger=trigger,
        idle_duration_seconds=idle_duration_sec if trigger == "idle_10min" else None,
        created_at=ist_now(),
        updated_at=ist_now(),
        expires_at=ist_now() + timedelta(days=30)  # TTL: 30 days
    )

    logger.debug(f"Generated summary for engagement {project_id}: {len(summary_text)} chars")
    return summary


def _generate_summary_text(
    key_points: dict,
    discovery_slots: dict,
    decision_answers: dict
) -> str:
    """Generate 2-3 line summary from key points.

    Extracts major conversation points into concise narrative.

    Args:
        key_points: Dict of extracted key points
        discovery_slots: Dict of discovery answers
        decision_answers: Dict of decisions made

    Returns:
        2-3 line summary text
    """

    lines = []

    # Line 1: Current state + discovery
    if key_points.get("discovery_slots"):
        discovery_str = ", ".join(key_points["discovery_slots"][:3])  # First 3
        lines.append(f"Discovered: {discovery_str}")

    # Line 2: Decisions made
    if key_points.get("decisions_made"):
        decision_str = ", ".join(key_points["decisions_made"][:3])  # First 3
        lines.append(f"Decided: {decision_str}")

    # Line 3: Current conversation state
    state = key_points.get("current_state", "in progress")
    lines.append(f"Status: {state}")

    return " | ".join(lines)


async def _upsert_conversation_summary(
    db: Session,
    summary: ConversationSummary
) -> None:
    """UPSERT summary: Update existing or insert new.

    ONE row per engagement (unique on project_id).
    Always updates if exists, never creates duplicates.

    Args:
        db: Database session
        summary: ConversationSummary to save
    """

    existing = db.query(ConversationSummary).filter(
        ConversationSummary.project_id == summary.project_id
    ).first()

    if existing:
        # UPDATE existing row
        existing.summary_text = summary.summary_text
        existing.summary_metadata_json = summary.summary_metadata_json
        existing.state_snapshot_json = summary.state_snapshot_json
        existing.discovery_slots_snapshot = summary.discovery_slots_snapshot
        existing.decision_answers_snapshot = summary.decision_answers_snapshot
        existing.conversation_fsm_state = summary.conversation_fsm_state
        existing.summary_trigger = summary.summary_trigger
        existing.idle_duration_seconds = summary.idle_duration_seconds
        existing.updated_at = ist_now()
        db.commit()
        logger.info(f"Updated summary for engagement {summary.project_id}")
    else:
        # INSERT new row
        db.add(summary)
        db.commit()
        logger.info(f"Created new summary for engagement {summary.project_id}")


async def _load_conversation_state_json(
    project_id: str,
    conversation_id: str
) -> ConversationState | None:
    """Load conversation state from JSON file.

    Args:
        project_id: Project ID
        conversation_id: Conversation ID

    Returns:
        ConversationState instance or None if file not found
    """
    import os

    json_path = f"workspace/{project_id}/conversation_state/{conversation_id}.json"

    if not os.path.exists(json_path):
        logger.warning(f"Conversation state file not found: {json_path}")
        return None

    try:
        with open(json_path, 'r') as f:
            state_dict = json.load(f)
        return ConversationState.from_dict(state_dict)
    except Exception as e:
        logger.error(f"Failed to load conversation state from {json_path}: {e}")
        return None
