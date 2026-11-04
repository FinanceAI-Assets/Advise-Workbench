#!/usr/bin/env python3
"""Debug script to check summary generation status."""

import os
import sys
from sqlalchemy.orm import Session

# Add repo to path
sys.path.insert(0, os.path.dirname(__file__))

from src.core.db.session import SessionLocal
from src.core.db.models import Conversation, ConversationMessage, ConversationSummary, EngagementMeta
from src.extensions.conversation_session import EngagementSessionRegistry
import asyncio

def main():
    db: Session = SessionLocal()

    print("=" * 80)
    print("SUMMARY GENERATION DEBUG")
    print("=" * 80)

    # Check 1: Are there any conversations?
    conversations = db.query(Conversation).all()
    print(f"\n[1] Total conversations in DB: {len(conversations)}")
    for conv in conversations[-3:]:
        print(f"    - {conv.id} (project: {conv.project_id}, created: {conv.created_at})")

    if not conversations:
        print("    ⚠️  NO CONVERSATIONS FOUND - Create one first!")
        return

    # Check 2: Latest conversation messages
    latest_conv = conversations[-1]
    print(f"\n[2] Latest conversation: {latest_conv.id}")
    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == latest_conv.id
    ).order_by(ConversationMessage.created_at).all()

    print(f"    Messages in latest conv: {len(messages)}")
    if len(messages) < 2:
        print("    WARNING: NOT ENOUGH MESSAGES - Send at least 5-10 messages first!")
    for msg in messages[-5:]:
        role = msg.role.upper()
        content = (msg.content or "")[:60]
        try:
            print(f"    - {role}: {content}...")
        except UnicodeEncodeError:
            print(f"    - {role}: (content with unicode)")

    # Check 3: Session tracking
    print(f"\n[3] Active sessions in memory:")
    asyncio.run(check_sessions())

    # Check 4: EngagementMeta in DB
    print(f"\n[4] EngagementMeta records:")
    engagements = db.query(EngagementMeta).all()
    print(f"    Total engagements: {len(engagements)}")
    for eng in engagements[-3:]:
        print(f"    - {eng.project_id}: last_activity={eng.last_activity_at}, idle_detection={eng.enable_idle_detection}")

    if not engagements:
        print("    ⚠️  NO ENGAGEMENT META RECORDS - Idle detection may not be enabled!")

    # Check 5: Existing summaries
    print(f"\n[5] Existing summaries in DB:")
    summaries = db.query(ConversationSummary).all()
    print(f"    Total summaries: {len(summaries)}")
    for summary in summaries[-3:]:
        text = (summary.summary_text or "")[:80]
        print(f"    - {summary.project_id}: '{text}...' (trigger: {summary.summary_trigger})")

    # Check 6: State files
    print(f"\n[6] Conversation state JSON files:")
    for conv in conversations[-3:]:
        state_path = f"workspace/{conv.project_id}/conversation_state/{conv.id}.json"
        exists = os.path.exists(state_path)
        status = '[EXISTS]' if exists else '[MISSING]'
        print(f"    - {state_path}: {status}")
        if exists:
            try:
                import json
                with open(state_path) as f:
                    data = json.load(f)
                    summary_text = data.get('conversation_summary', '')
                    if summary_text:
                        print(f"      conversation_summary: '{summary_text[:60]}...'")
                    else:
                        print(f"      conversation_summary: (EMPTY)")
            except Exception as e:
                print(f"      Error reading file: {e}")

    # Check 7: What should trigger summary?
    print(f"\n[7] Summary generation triggers:")
    print(f"    - Idle detection worker: Every 120 seconds (2 minutes)")
    print(f"    - Idle timeout: 120 seconds")
    print(f"    - Check: Is application running with idle detection enabled?")
    print(f"    - Check: Are you waiting 2+ minutes after last message?")

    db.close()

    print("\n" + "=" * 80)
    print("NEXT STEPS:")
    print("=" * 80)
    print("1. If NO MESSAGES: Send 5-10 messages to Sheldon")
    print("2. If NO SESSIONS: Make sure idle detection worker is running (logs)")
    print("3. If NO ENGAGEMENT META: Check if idle detection is enabled for your project")
    print("4. WAIT 2+ MINUTES after last message")
    print("5. Run this script again to check if summary was generated")
    print("=" * 80)

async def check_sessions():
    """Check active sessions in registry."""
    try:
        # This won't show anything unless we can access the internal _sessions dict
        # For now, just verify the registry is accessible
        session = await EngagementSessionRegistry.get_session("test")
        print("    [OK] EngagementSessionRegistry is accessible")
        print("    (Note: Individual sessions not visible from outside)")
    except Exception as e:
        print(f"    [ERROR] Error checking sessions: {e}")

if __name__ == "__main__":
    main()
