#!/usr/bin/env python
"""Quick database statistics summary."""

from src.core.db.session import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()

    print("\n" + "="*60)
    print("DATABASE STATISTICS - QUICK VIEW")
    print("="*60 + "\n")

    # Define all queries
    queries = {
        "Users": "SELECT COUNT(*) as count FROM users",
        "Projects": "SELECT COUNT(*) as count FROM projects",
        "Engagements": "SELECT COUNT(*) as count FROM engagement_meta",
        "Memberships": "SELECT COUNT(*) as count FROM memberships",
        "Conversations": "SELECT COUNT(*) as count FROM conversations",
        "Messages": "SELECT COUNT(*) as count FROM conversation_messages",
        "Summaries": "SELECT COUNT(*) as count FROM conversation_summaries",
        "Runs": "SELECT COUNT(*) as count FROM runs",
        "Run Tasks": "SELECT COUNT(*) as count FROM run_tasks",
        "Memory Items": "SELECT COUNT(*) as count FROM memory_items",
        "Scheduled Tasks": "SELECT COUNT(*) as count FROM scheduled_tasks",
        "Wiki Pages": "SELECT COUNT(*) as count FROM wiki_pages",
        "Reviews": "SELECT COUNT(*) as count FROM reviews",
        "Activity Events": "SELECT COUNT(*) as count FROM activity_events",
        "Notifications": "SELECT COUNT(*) as count FROM notifications",
        "Workbench Records": "SELECT COUNT(*) as count FROM workbench_records",
    }

    # Execute queries
    stats = {}
    for label, query in queries.items():
        try:
            result = db.execute(text(query))
            count = result.scalar()
            stats[label] = count
        except Exception as e:
            stats[label] = f"ERROR: {str(e)[:20]}"

    # Display results
    for label, count in stats.items():
        if isinstance(count, int):
            bar = "█" * min(count, 30)
            print(f"{label:20} {str(count):>5}  {bar}")
        else:
            print(f"{label:20} {count}")

    # Summary
    print("\n" + "-"*60)
    total_records = sum(v for v in stats.values() if isinstance(v, int))
    print(f"{'Total Records':20} {total_records:>5}")
    print("-"*60 + "\n")

    # Latest activity
    print("LATEST ACTIVITY\n")

    try:
        result = db.execute(text("""
            SELECT 'Message' as type, created_at FROM conversation_messages
            UNION ALL
            SELECT 'Activity', created_at FROM activity_events
            UNION ALL
            SELECT 'Project', created_at FROM projects
            ORDER BY created_at DESC LIMIT 5
        """))

        for row in result:
            event_type, timestamp = row
            print(f"  • {event_type:15} {str(timestamp)[:19]}")
    except:
        pass

    print("\n" + "="*60 + "\n")

    db.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
