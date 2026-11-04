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
                # STEP 1: Save summary to conversation state JSON file FIRST (source of truth)
                json_saved = False
                try:
                    from src.memory.short_term.conversation_state import load_state, save_state

                    # LOGGING: Check what we're about to set
                    logger.debug(f"[TRACE] summary.summary_text value: '{summary.summary_text}' (length={len(summary.summary_text) if summary.summary_text else 0})")
                    logger.debug(f"[TRACE] summary.summary_text is None: {summary.summary_text is None}")
                    logger.debug(f"[TRACE] summary.summary_text is empty: {summary.summary_text == ''}")

                    conversation = db.query(Conversation).filter(
                        Conversation.project_id == project_id
                    ).order_by(Conversation.updated_at.desc()).first()

                    if conversation:
                        # LOGGING: Before loading
                        logger.debug(f"[TRACE] Loading conversation state for {conversation.id}")
                        conv_state = load_state(conversation)
                        logger.debug(f"[TRACE] Loaded conv_state.conversation_summary BEFORE set: '{conv_state.conversation_summary}'")

                        # LOGGING: Set the value
                        logger.debug(f"[TRACE] Setting conv_state.conversation_summary = '{summary.summary_text}'")
                        conv_state.conversation_summary = summary.summary_text
                        logger.debug(f"[TRACE] Loaded conv_state.conversation_summary AFTER set: '{conv_state.conversation_summary}'")

                        # LOGGING: Before saving
                        json_output = conv_state.to_json()
                        logger.debug(f"[TRACE] to_json() output length: {len(json_output)} chars")
                        logger.debug(f"[TRACE] conversation_summary in JSON: {json_output.count('conversation_summary')}")

                        import json as json_lib
                        json_parsed = json_lib.loads(json_output)
                        logger.debug(f"[TRACE] ACTUAL conversation_summary value in JSON: '{json_parsed.get('conversation_summary')}'")
                        logger.debug(f"[TRACE] Is conversation_summary empty in JSON: {json_parsed.get('conversation_summary') == ''}")

                        # Actually save to JSON (source of truth)
                        save_state(conversation, conv_state)

                        # VERIFY: Read back from JSON file to ensure it was actually saved
                        from src.core.storage import workspace_path
                        json_path = workspace_path(project_id) / "conversation_state" / f"{conversation.id}.json"

                        if json_path.exists():
                            verify_json = json.loads(json_path.read_text(encoding='utf-8'))
                            saved_summary = verify_json.get('conversation_summary', '')

                            if saved_summary == summary.summary_text:
                                json_saved = True
                                logger.info(f"[1/2] VERIFIED: Saved conversation_summary to JSON file for {project_id}")
                            else:
                                logger.warning(f"[1/2] JSON MISMATCH: Saved '{saved_summary[:50]}' but expected '{summary.summary_text[:50]}'")
                                json_saved = False
                        else:
                            logger.error(f"[1/2] JSON FILE NOT FOUND after save: {json_path}")
                            json_saved = False
                    else:
                        logger.warning(f"No conversation found to save JSON state for {project_id}")
                except Exception as json_e:
                    logger.error(f"[1/2] CRITICAL: Failed to save conversation_summary to JSON file: {json_e}", exc_info=True)

                # STEP 2: Save to database SECOND (persistent storage) - only if JSON save succeeded
                if json_saved:
                    try:
                        await _upsert_conversation_summary(db, summary)
                        summary_count += 1
                        logger.debug(f"[2/2] Saved summary to database for {project_id}")
                        logger.info(f"Summary saved for engagement {project_id} (idle {session.get_idle_duration_seconds()}s) - JSON→DB sequence complete")
                    except Exception as db_e:
                        logger.error(f"[2/2] Failed to save summary to database: {db_e}", exc_info=True)
                else:
                    logger.error(f"Skipping database save because JSON save failed for {project_id}")

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

    # 3. Fetch ALL messages from conversation (entire history, not limited)
    # CHANGED: Was limit(50), now fetch entire conversation history
    # This ensures summary captures complete context regardless of conversation length
    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation.id
    ).order_by(
        ConversationMessage.created_at.asc()  # Chronological order (oldest first)
    ).all()

    if not messages:
        logger.warning(f"No messages found in conversation {conversation.id}")
        # Don't return None - even empty conversation should get a summary
        return ConversationSummary(
            id=f"summary_{project_id}",
            project_id=project_id,
            summary_text="No conversation messages yet.",
            summary_metadata_json=json.dumps({
                "message_count": 0,
                "generated_at": ist_now().isoformat()
            }),
            state_snapshot_json=json.dumps(conv_state.to_dict() if conv_state else {}),
            discovery_slots_snapshot=json.dumps({}),
            decision_answers_snapshot=json.dumps({}),
            conversation_fsm_state=conv_state.state if conv_state else "unknown",
            summary_trigger=trigger,
            idle_duration_seconds=idle_duration_sec if trigger == "idle_10min" else None,
            created_at=ist_now(),
            updated_at=ist_now(),
            expires_at=ist_now() + timedelta(days=30)
        )

    # 4. Build conversation transcript for LLM summarization (CHANGED: was metadata extraction)
    # DEPRECATED:
    # discovery_slots = {}
    # decision_answers = {}
    # for msg in reversed(messages):  # Chronological order
    #     if msg.metadata_json:
    #         try:
    #             meta = json.loads(msg.metadata_json)
    #             if "discovery" in meta:
    #                 discovery_slots.update(meta["discovery"])
    #             if "decision_answers" in meta:
    #                 decision_answers.update(meta["decision_answers"])
    #         except json.JSONDecodeError:
    #             logger.warning(f"Failed to parse metadata for message {msg.id}")

    # Build full conversation transcript in chronological order (oldest to newest)
    # CHANGED: Use all messages (already in asc order), not reversed
    # This preserves complete conversation flow for LLM summarization
    transcript_lines = []
    for msg in messages:  # Already chronological (asc from line 157)
        role = msg.role.upper() if msg.role else "UNKNOWN"
        content = msg.content or ""
        # Truncate individual messages to ~500 chars to avoid token overflow
        # But include ALL messages to preserve full conversation context
        if len(content) > 500:
            content = content[:500] + "..."
        transcript_lines.append(f"{role}: {content}")

    transcript = "\n".join(transcript_lines)

    if not transcript.strip():
        # Empty transcript - still generate summary
        logger.debug(f"Empty conversation content for {conversation.id}")
        summary_text = "Conversation started but no messages exchanged yet."
    else:
        # Generate LLM-based summary of ENTIRE conversation
        summary_text = await _generate_conversation_summary_llm(transcript)

    # 5. Extract metadata for analytics (optional)
    discovery_slots = {}
    decision_answers = {}
    for msg in reversed(messages):
        if msg.metadata_json:
            try:
                meta = json.loads(msg.metadata_json)
                if "discovery" in meta:
                    discovery_slots.update(meta["discovery"])
                if "decision_answers" in meta:
                    decision_answers.update(meta["decision_answers"])
            except json.JSONDecodeError:
                logger.debug(f"Skipped metadata parse for message {msg.id}")

    # 6. Create summary record
    summary = ConversationSummary(
        id=f"summary_{project_id}",  # Fixed ID per engagement for upsert
        project_id=project_id,
        summary_text=summary_text,
        summary_metadata_json=json.dumps({
            "message_count": len(messages),
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


# DEPRECATED: Old metadata-based summary generation
# def _generate_summary_text(
#     key_points: dict,
#     discovery_slots: dict,
#     decision_answers: dict
# ) -> str:
#     """Generate 2-3 line summary from key points.
#     Extracts major conversation points into concise narrative.
#     """
#     lines = []
#     if key_points.get("discovery_slots"):
#         discovery_str = ", ".join(key_points["discovery_slots"][:3])
#         lines.append(f"Discovered: {discovery_str}")
#     if key_points.get("decisions_made"):
#         decision_str = ", ".join(key_points["decisions_made"][:3])
#         lines.append(f"Decided: {decision_str}")
#     state = key_points.get("current_state", "in progress")
#     lines.append(f"Status: {state}")
#     return " | ".join(lines)


async def _generate_conversation_summary_llm(transcript: str) -> str:
    """Generate 2-4 line natural language summary of conversation using LLM.

    Summarizes actual conversation between user and assistant into concise narrative
    that captures what was discussed, decisions made, and next steps.

    Args:
        transcript: Full conversation transcript (USER: ... ASSISTANT: ...)

    Returns:
        2-4 line summary text from LLM
    """
    from src.llm import gateway

    prompt = f"""Summarize the following conversation in 2-4 lines.
Focus on: what was discussed, key decisions made, and any agreements or next steps.
Keep it concise and actionable.

Conversation:
{transcript}

Summary:"""

    # DEPRECATED: Old async gateway API
    # try:
    #     response = await gateway.agenerate(
    #         model="claude-opus-5",
    #         messages=[{"role": "user", "content": prompt}],
    #         max_tokens=200,
    #         temperature=0.3,
    #     )
    #     summary = response.content.strip() if response.content else ""

    # NEW: Use gateway.create_message() with proper API
    try:
        from src.agents.tool_agent import _extract_final_text_from_message

        msg = gateway.create_message(
            model=gateway.model_for("default"),
            max_tokens=200,
            temperature=0.3,
            system="You are a concise conversation summarizer. Generate a 2-4 line summary.",
            messages=[{"role": "user", "content": prompt}],
        )
        summary = _extract_final_text_from_message(msg).strip()
        if not summary:
            logger.warning("LLM returned empty summary")
            return "Conversation was held. Details to be documented."
        logger.debug(f"Generated LLM summary: {summary[:100]}...")
        return summary
    except Exception as e:
        logger.error(f"Failed to generate LLM summary: {e}", exc_info=True)
        return "Conversation summary could not be generated. Manual review recommended."


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
