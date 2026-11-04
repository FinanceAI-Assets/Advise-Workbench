#!/usr/bin/env python3
"""Check conversation_summaries table."""

import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from src.core.db.session import SessionLocal
from src.core.db.models import ConversationSummary

def safe_print(text):
    """Print text safely handling unicode."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('utf-8', errors='replace').decode('utf-8'))

def main():
    db = SessionLocal()

    print("=" * 100)
    print("CONVERSATION_SUMMARIES TABLE CONTENTS")
    print("=" * 100)

    summaries = db.query(ConversationSummary).order_by(
        ConversationSummary.created_at.desc()
    ).limit(10).all()

    print(f"\nTotal recent summaries: {len(summaries)}\n")

    for i, summary in enumerate(summaries, 1):
        try:
            safe_print(f"[{i}] ID: {summary.id}")
            safe_print(f"    Project ID: {summary.project_id}")
            safe_print(f"    Trigger: {summary.summary_trigger}")
            safe_print(f"    Created: {summary.created_at}")
            safe_print(f"    Updated: {summary.updated_at}")
            safe_print(f"    Summary Text:")

            if summary.summary_text:
                text = summary.summary_text
                if len(text) > 200:
                    text = text[:200] + "..."
                safe_print(f"      {text}")
            else:
                safe_print(f"      (empty)")

            # Parse metadata
            try:
                meta = json.loads(summary.summary_metadata_json or '{}')
                msg_count = meta.get('message_count', 'unknown')
                safe_print(f"    Message Count: {msg_count}")
            except:
                safe_print(f"    Message Count: (error parsing metadata)")

            safe_print(f"    State Snapshot: {len(summary.state_snapshot_json or '')} bytes")
            print()
        except Exception as e:
            safe_print(f"    [Error displaying record: {e}]")
            print()

    db.close()

    print("=" * 100)
    total = db.query(ConversationSummary).count()
    print(f"Total summaries in database: {total}")
    print("=" * 100)

if __name__ == "__main__":
    main()
