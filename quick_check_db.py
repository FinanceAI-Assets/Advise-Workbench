#!/usr/bin/env python
"""Quick check of conversation summaries in database."""

import json
from src.core.db.session import SessionLocal
from src.core.db.models import ConversationSummary, EngagementMeta

def main():
    db = SessionLocal()

    print("\n" + "="*80)
    print("CONVERSATION SUMMARIES - QUICK CHECK")
    print("="*80)

    # Check if migration applied
    try:
        count = db.query(ConversationSummary).count()
    except Exception as e:
        print(f"\nERROR: Migration not applied yet!")
        print(f"Run: alembic upgrade head")
        print(f"Error: {e}")
        db.close()
        return

    print(f"\nTotal Summaries in Database: {count}")

    if count == 0:
        print("No summaries yet. Waiting for first idle engagement...")
        print("\nTo trigger a summary manually:")
        print("  1. Open an engagement in the UI")
        print("  2. Send a message to SHELDON")
        print("  3. Wait 10 minutes or call POST /{pid}/close-engagement-session")
        db.close()
        return

    # Show all summaries
    summaries = db.query(ConversationSummary).all()

    print("\n" + "-"*80)
    print("SUMMARIES:")
    print("-"*80)

    for i, s in enumerate(summaries, 1):
        print(f"\n{i}. Project ID: {s.project_id}")
        print(f"   Summary: {s.summary_text}")
        print(f"   State: {s.conversation_fsm_state}")
        print(f"   Trigger: {s.summary_trigger}")

        if s.idle_duration_seconds:
            mins = s.idle_duration_seconds / 60
            print(f"   Idle Duration: {s.idle_duration_seconds}s ({mins:.1f} min)")

        print(f"   Created: {s.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Updated: {s.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

        if s.restored_at:
            print(f"   Restored: {s.restored_at.strftime('%Y-%m-%d %H:%M:%S')} ✓")
        else:
            print(f"   Restored: Not yet")

        # Parse snapshots
        try:
            state = json.loads(s.state_snapshot_json or "{}")
            discovery = json.loads(s.discovery_slots_snapshot or "{}")
            decisions = json.loads(s.decision_answers_snapshot or "{}")

            if discovery:
                print(f"   Discovered: {list(discovery.keys())}")
            if decisions:
                print(f"   Decisions: {list(decisions.keys())}")
        except:
            pass

    # Statistics
    print("\n" + "-"*80)
    print("STATISTICS:")
    print("-"*80)

    idle_count = sum(1 for s in summaries if s.summary_trigger == "idle_10min")
    close_count = sum(1 for s in summaries if s.summary_trigger == "session_closed")
    restored_count = sum(1 for s in summaries if s.restored_at)

    print(f"Idle-triggered: {idle_count}")
    print(f"Close-triggered: {close_count}")
    print(f"Restored: {restored_count}")

    # Check EngagementMeta
    print("\n" + "-"*80)
    print("ENGAGEMENT META - IDLE DETECTION:")
    print("-"*80)

    metas = db.query(EngagementMeta).all()
    print(f"Total engagements: {len(metas)}")

    enabled = sum(1 for m in metas if m.enable_idle_detection)
    print(f"Idle detection enabled: {enabled}")

    if enabled > 0:
        print("\nEngagements with idle detection:")
        for m in metas:
            if m.enable_idle_detection:
                print(f"  {m.project_id}: timeout={m.idle_timeout_seconds}s")

    print("\n" + "="*80)
    print("Check complete!")
    print("="*80 + "\n")

    db.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
