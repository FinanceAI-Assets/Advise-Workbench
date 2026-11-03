#!/usr/bin/env python
"""Direct SQL queries for database inspection."""

from src.core.db.session import SessionLocal
from sqlalchemy import text

def run_query(db, query, title):
    """Execute and display a SQL query."""
    print(f"\n{'='*80}")
    print(f"{title:^80}")
    print(f"{'='*80}\n")
    print(f"Query: {query}\n")
    print("-" * 80)

    try:
        result = db.execute(text(query))
        rows = result.fetchall()

        if not rows:
            print("(No results)")
            return

        # Print header
        if result.keys():
            header = " | ".join(str(k) for k in result.keys())
            print(header)
            print("-" * 80)

        # Print rows
        for row in rows:
            print(" | ".join(str(val) if val is not None else "NULL" for val in row))

    except Exception as e:
        print(f"ERROR: {e}")

def main():
    db = SessionLocal()

    print("\n" + "="*80)
    print("SQL QUERY TOOLKIT FOR DATABASE INSPECTION")
    print("="*80)

    # User queries
    run_query(db, "SELECT id, email, full_name, role, is_admin, created_at FROM users;",
              "ALL USERS")

    # Project queries
    run_query(db, "SELECT id, name, created_by, created_at FROM projects;",
              "ALL PROJECTS")

    # Engagement Meta
    run_query(db, """SELECT project_id, code, type, stage, status,
                           enable_idle_detection, idle_timeout_seconds,
                           last_activity_at, created_at
                    FROM engagement_meta;""",
              "ENGAGEMENT DETAILS WITH IDLE DETECTION")

    # Conversations
    run_query(db, """SELECT id, project_id, user_id, title, created_at, updated_at
                    FROM conversations;""",
              "ALL CONVERSATIONS")

    # Conversation messages with details
    run_query(db, """SELECT cm.id, cm.conversation_id, cm.role,
                           LENGTH(cm.content) as content_length,
                           cm.source_type, cm.created_at
                    FROM conversation_messages cm
                    ORDER BY cm.created_at DESC;""",
              "CONVERSATION MESSAGES (SUMMARY)")

    # Message content details
    run_query(db, """SELECT conversation_id, role,
                           SUBSTR(content, 1, 100) as content_preview,
                           created_at
                    FROM conversation_messages
                    ORDER BY created_at;""",
              "CONVERSATION MESSAGE CONTENT PREVIEW")

    # Conversation summary status
    run_query(db, """SELECT COUNT(*) as total_summaries,
                           SUM(CASE WHEN summary_trigger = 'idle_10min' THEN 1 ELSE 0 END) as idle_triggered,
                           SUM(CASE WHEN summary_trigger = 'session_closed' THEN 1 ELSE 0 END) as closed_triggered
                    FROM conversation_summaries;""",
              "CONVERSATION SUMMARIES STATISTICS")

    # Project membership details
    run_query(db, """SELECT m.project_id, p.name, m.user_id, u.email, m.role
                    FROM memberships m
                    JOIN projects p ON m.project_id = p.id
                    JOIN users u ON m.user_id = u.id;""",
              "PROJECT MEMBERS (WITH DETAILS)")

    # Runs by project
    run_query(db, """SELECT r.id, r.project_id, r.status,
                           r.tokens_input, r.tokens_output,
                           r.cost_usd, r.created_at
                    FROM runs r
                    ORDER BY r.created_at DESC;""",
              "ALL RUNS (TOKEN & COST INFO)")

    # Run tasks by project
    run_query(db, """SELECT rt.id, rt.run_id, rt.project_id, rt.title,
                           rt.phase, rt.status, rt.priority,
                           rt.started_at, rt.completed_at
                    FROM run_tasks rt
                    ORDER BY rt.created_at DESC;""",
              "RUN TASKS (DETAILED)")

    # Memory items by project
    run_query(db, """SELECT project_id, memory_type, key,
                           LENGTH(value) as value_length,
                           confidence, source, created_at
                    FROM memory_items
                    WHERE is_archived = 0
                    ORDER BY created_at DESC;""",
              "MEMORY ITEMS (ACTIVE ONLY)")

    # Activity log
    run_query(db, """SELECT id, actor, kind, title,
                           project_id, created_at
                    FROM activity_events
                    ORDER BY created_at DESC;""",
              "ACTIVITY LOG")

    # Workbench records by collection
    run_query(db, """SELECT collection, COUNT(*) as record_count,
                           MAX(updated_at) as last_updated
                    FROM workbench_records
                    GROUP BY collection
                    ORDER BY record_count DESC;""",
              "WORKBENCH RECORDS BY COLLECTION")

    # Database size info
    run_query(db, """SELECT COUNT(*) as total_tables
                    FROM sqlite_master
                    WHERE type='table' AND name NOT LIKE 'sqlite_%';""",
              "TOTAL TABLES")

    # Wiki page summary
    run_query(db, """SELECT wiki_type, category, COUNT(*) as count
                    FROM wiki_pages
                    GROUP BY wiki_type, category;""",
              "WIKI PAGES BY TYPE AND CATEGORY")

    # Scheduled tasks status
    run_query(db, """SELECT id, project_id, name, status,
                           trigger_type, cadence_minutes,
                           next_run_at, last_run_at, last_run_status
                    FROM scheduled_tasks;""",
              "SCHEDULED TASKS STATUS")

    print("\n" + "="*80)
    print("QUERY TOOLKIT COMPLETE")
    print("="*80 + "\n")

    db.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
