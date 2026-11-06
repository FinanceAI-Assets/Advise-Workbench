#!/usr/bin/env python
"""Export database records to CSV or JSON format."""

import json
import csv
from datetime import datetime
from pathlib import Path
from src.core.db.session import SessionLocal
from sqlalchemy import text
from src.core.db.models import (
    User, Project, Conversation, ConversationMessage,
    EngagementMeta, ActivityEvent, Membership
)

def export_to_csv(data, filename):
    """Export records to CSV."""
    if not data:
        print(f"No data to export to {filename}")
        return

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

    print(f"✓ Exported {len(data)} records to {filename}")

def export_to_json(data, filename):
    """Export records to JSON."""
    if not data:
        print(f"No data to export to {filename}")
        return

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)

    print(f"✓ Exported {len(data)} records to {filename}")

def serialize_model(obj):
    """Convert SQLAlchemy model to dict."""
    if obj is None:
        return None
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

def main():
    db = SessionLocal()
    export_dir = Path("D:\\Users\\PriyankaGupta\\Documents\\Conversation comp\\db_exports")
    export_dir.mkdir(exist_ok=True)

    print("\n" + "="*80)
    print("DATABASE EXPORT UTILITY")
    print("="*80 + "\n")

    # Export Users
    print("Exporting Users...")
    users = db.query(User).all()
    users_data = [serialize_model(u) for u in users]
    export_to_csv(users_data, export_dir / "users.csv")
    export_to_json(users_data, export_dir / "users.json")

    # Export Projects
    print("\nExporting Projects...")
    projects = db.query(Project).all()
    projects_data = [serialize_model(p) for p in projects]
    export_to_csv(projects_data, export_dir / "projects.csv")
    export_to_json(projects_data, export_dir / "projects.json")

    # Export Engagement Meta
    print("\nExporting Engagement Meta...")
    engagements = db.query(EngagementMeta).all()
    engagements_data = [serialize_model(e) for e in engagements]
    export_to_csv(engagements_data, export_dir / "engagement_meta.csv")
    export_to_json(engagements_data, export_dir / "engagement_meta.json")

    # Export Memberships
    print("\nExporting Memberships...")
    memberships = db.query(Membership).all()
    memberships_data = [serialize_model(m) for m in memberships]
    export_to_csv(memberships_data, export_dir / "memberships.csv")
    export_to_json(memberships_data, export_dir / "memberships.json")

    # Export Conversations
    print("\nExporting Conversations...")
    conversations = db.query(Conversation).all()
    conversations_data = [serialize_model(c) for c in conversations]
    export_to_csv(conversations_data, export_dir / "conversations.csv")
    export_to_json(conversations_data, export_dir / "conversations.json")

    # Export Conversation Messages
    print("\nExporting Conversation Messages...")
    messages = db.query(ConversationMessage).all()
    messages_data = [serialize_model(m) for m in messages]
    export_to_csv(messages_data, export_dir / "conversation_messages.csv")
    export_to_json(messages_data, export_dir / "conversation_messages.json")

    # Export Activity Events
    print("\nExporting Activity Events...")
    activity = db.query(ActivityEvent).all()
    activity_data = [serialize_model(a) for a in activity]
    export_to_csv(activity_data, export_dir / "activity_events.csv")
    export_to_json(activity_data, export_dir / "activity_events.json")

    # Generate Summary Report
    print("\n" + "-"*80)
    print("Generating Summary Report...")
    print("-"*80 + "\n")

    summary = {
        "export_timestamp": datetime.now().isoformat(),
        "export_directory": str(export_dir),
        "statistics": {
            "users": len(users),
            "projects": len(projects),
            "engagements": len(engagements),
            "memberships": len(memberships),
            "conversations": len(conversations),
            "conversation_messages": len(messages),
            "activity_events": len(activity),
        },
        "user_details": [
            {
                "id": u.id,
                "email": u.email,
                "role": u.role,
                "is_admin": u.is_admin,
                "created_at": str(u.created_at)
            }
            for u in users
        ],
        "project_details": [
            {
                "id": p.id,
                "name": p.name,
                "created_by": p.created_by,
                "created_at": str(p.created_at)
            }
            for p in projects
        ]
    }

    report_file = export_dir / "export_summary.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"✓ Summary report: {report_file}")

    # Print Summary
    print("\n" + "="*80)
    print("EXPORT SUMMARY")
    print("="*80)
    print(f"\nExport Directory: {export_dir}")
    print(f"\nStatistics:")
    for key, value in summary["statistics"].items():
        print(f"  • {key}: {value}")

    print(f"\nFiles Created:")
    for f in sorted(export_dir.glob("*")):
        size_kb = f.stat().st_size / 1024
        print(f"  • {f.name} ({size_kb:.1f} KB)")

    print("\n" + "="*80)
    print("Export Complete!")
    print("="*80 + "\n")

    db.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
