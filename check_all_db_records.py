#!/usr/bin/env python
"""Comprehensive database records check."""

import json
from datetime import datetime
from src.core.db.session import SessionLocal
from src.core.db.models import (
    User, Project, ProjectBrand, EngagementMeta, Membership,
    Run, ConversationMessage, Conversation, ConversationSummary,
    RunTask, RunEvent, SwarmTeam, SwarmMessage, MemoryItem,
    ScheduledTask, WikiPage, ActivityEvent, Review, Notification,
    LpPractice, SavedPractice, WorkbenchRecord
)

def format_datetime(dt):
    """Format datetime for display."""
    if dt is None:
        return "None"
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*80}")
    print(f"{title:^80}")
    print(f"{'='*80}\n")

def main():
    db = SessionLocal()

    try:
        print_section("ADVISE WORKBENCH DATABASE RECORDS CHECK")

        # Users
        print_section("USERS")
        users = db.query(User).all()
        print(f"Total: {len(users)}")
        if users:
            for u in users:
                print(f"  • {u.id}")
                print(f"    Email: {u.email}")
                print(f"    Name: {u.full_name}")
                print(f"    Role: {u.role}")
                print(f"    Admin: {u.is_admin}")
                print(f"    Created: {format_datetime(u.created_at)}\n")

        # Projects
        print_section("PROJECTS")
        projects = db.query(Project).all()
        print(f"Total: {len(projects)}")
        if projects:
            for p in projects:
                print(f"  • {p.id}")
                print(f"    Name: {p.name}")
                print(f"    Created by: {p.created_by}")
                print(f"    Created: {format_datetime(p.created_at)}\n")

        # Engagement Meta (with idle detection)
        print_section("ENGAGEMENT META (Idle Detection)")
        engagements = db.query(EngagementMeta).all()
        print(f"Total: {len(engagements)}")
        if engagements:
            for e in engagements:
                print(f"  • Project: {e.project_id}")
                print(f"    Type: {e.type}")
                print(f"    Stage: {e.stage}")
                print(f"    Status: {e.status}")
                print(f"    Idle Detection: {e.enable_idle_detection} (timeout: {e.idle_timeout_seconds}s)")
                if e.last_activity_at:
                    print(f"    Last Activity: {format_datetime(e.last_activity_at)}")
                if e.engagement_session_id:
                    print(f"    Session ID: {e.engagement_session_id}")
                print(f"    Updated: {format_datetime(e.updated_at)}\n")

        # Memberships
        print_section("PROJECT MEMBERSHIPS")
        memberships = db.query(Membership).all()
        print(f"Total: {len(memberships)}")
        if memberships:
            for m in memberships:
                print(f"  • Project {m.project_id} - User {m.user_id}")
                print(f"    Role: {m.role}\n")

        # Conversations
        print_section("CONVERSATIONS")
        conversations = db.query(Conversation).all()
        print(f"Total: {len(conversations)}")
        if conversations:
            for c in conversations:
                print(f"  • {c.id}")
                print(f"    Title: {c.title}")
                print(f"    Project: {c.project_id}")
                print(f"    User: {c.user_id}")
                print(f"    Created: {format_datetime(c.created_at)}")
                print(f"    Updated: {format_datetime(c.updated_at)}\n")

        # Conversation Messages
        print_section("CONVERSATION MESSAGES")
        messages = db.query(ConversationMessage).all()
        print(f"Total: {len(messages)}")
        if messages:
            for m in messages[:5]:  # Show first 5
                print(f"  • {m.id}")
                print(f"    Conversation: {m.conversation_id}")
                print(f"    Role: {m.role}")
                print(f"    Content: {m.content[:100]}...")
                print(f"    Created: {format_datetime(m.created_at)}\n")
            if len(messages) > 5:
                print(f"  ... and {len(messages) - 5} more messages\n")

        # Conversation Summaries
        print_section("CONVERSATION SUMMARIES")
        summaries = db.query(ConversationSummary).all()
        print(f"Total: {len(summaries)}")
        if summaries:
            for s in summaries:
                print(f"  • Project: {s.project_id}")
                print(f"    Summary: {s.summary_text}")
                print(f"    FSM State: {s.conversation_fsm_state}")
                print(f"    Trigger: {s.summary_trigger}")
                if s.idle_duration_seconds:
                    print(f"    Idle Duration: {s.idle_duration_seconds}s")
                print(f"    Created: {format_datetime(s.created_at)}")
                print(f"    Updated: {format_datetime(s.updated_at)}\n")

        # Runs
        print_section("RUNS")
        runs = db.query(Run).all()
        print(f"Total: {len(runs)}")
        if runs:
            for r in runs[:5]:  # Show first 5
                print(f"  • {r.id}")
                print(f"    Project: {r.project_id}")
                print(f"    Status: {r.status}")
                print(f"    Output Types: {r.output_types}")
                print(f"    Created: {format_datetime(r.created_at)}\n")
            if len(runs) > 5:
                print(f"  ... and {len(runs) - 5} more runs\n")

        # Run Tasks
        print_section("RUN TASKS")
        tasks = db.query(RunTask).all()
        print(f"Total: {len(tasks)}")
        if tasks:
            for t in tasks[:5]:  # Show first 5
                print(f"  • {t.id}")
                print(f"    Run: {t.run_id}")
                print(f"    Title: {t.title}")
                print(f"    Phase: {t.phase}")
                print(f"    Status: {t.status}")
                print(f"    Created: {format_datetime(t.created_at)}\n")
            if len(tasks) > 5:
                print(f"  ... and {len(tasks) - 5} more tasks\n")

        # Memory Items
        print_section("MEMORY ITEMS")
        memories = db.query(MemoryItem).all()
        print(f"Total: {len(memories)}")
        if memories:
            for m in memories[:5]:  # Show first 5
                print(f"  • {m.id}")
                print(f"    Project: {m.project_id}")
                print(f"    Type: {m.memory_type}")
                print(f"    Key: {m.key}")
                print(f"    Value: {m.value[:100]}...")
                print(f"    Confidence: {m.confidence}\n")
            if len(memories) > 5:
                print(f"  ... and {len(memories) - 5} more memory items\n")

        # Scheduled Tasks
        print_section("SCHEDULED TASKS")
        scheduled = db.query(ScheduledTask).all()
        print(f"Total: {len(scheduled)}")
        if scheduled:
            for s in scheduled:
                print(f"  • {s.id}")
                print(f"    Name: {s.name}")
                print(f"    Project: {s.project_id}")
                print(f"    Status: {s.status}")
                print(f"    Trigger: {s.trigger_type}")
                print(f"    Cadence: {s.cadence_minutes} minutes")
                print(f"    Next Run: {format_datetime(s.next_run_at)}\n")

        # Wiki Pages
        print_section("WIKI PAGES")
        wiki_pages = db.query(WikiPage).all()
        print(f"Total: {len(wiki_pages)}")
        if wiki_pages:
            for w in wiki_pages[:5]:  # Show first 5
                print(f"  • {w.id}")
                print(f"    Title: {w.title}")
                print(f"    Category: {w.category}")
                print(f"    Type: {w.wiki_type}")
                print(f"    Project: {w.project_id}")
                print(f"    Created: {format_datetime(w.created_at)}\n")
            if len(wiki_pages) > 5:
                print(f"  ... and {len(wiki_pages) - 5} more wiki pages\n")

        # Reviews
        print_section("REVIEWS")
        reviews = db.query(Review).all()
        print(f"Total: {len(reviews)}")
        if reviews:
            for r in reviews:
                print(f"  • {r.id}")
                print(f"    Title: {r.title}")
                print(f"    Type: {r.artifact_type}")
                print(f"    State: {r.state}")
                print(f"    Risk: {r.risk}")
                print(f"    Created: {format_datetime(r.created_at)}\n")

        # Activity Events
        print_section("ACTIVITY EVENTS")
        activity = db.query(ActivityEvent).all()
        print(f"Total: {len(activity)}")
        if activity:
            for a in activity[:5]:  # Show first 5
                print(f"  • {a.id}")
                print(f"    Actor: {a.actor}")
                print(f"    Kind: {a.kind}")
                print(f"    Title: {a.title}")
                print(f"    Created: {format_datetime(a.created_at)}\n")
            if len(activity) > 5:
                print(f"  ... and {len(activity) - 5} more activity events\n")

        # Notifications
        print_section("NOTIFICATIONS")
        notifications = db.query(Notification).all()
        print(f"Total: {len(notifications)}")
        if notifications:
            for n in notifications[:5]:  # Show first 5
                print(f"  • {n.id}")
                print(f"    User: {n.user_id}")
                print(f"    Kind: {n.kind}")
                print(f"    Title: {n.title}")
                print(f"    Read: {n.read_at is not None}")
                print(f"    Created: {format_datetime(n.created_at)}\n")
            if len(notifications) > 5:
                print(f"  ... and {len(notifications) - 5} more notifications\n")

        # Workbench Records
        print_section("WORKBENCH RECORDS")
        records = db.query(WorkbenchRecord).all()
        print(f"Total: {len(records)}")
        if records:
            collections = {}
            for r in records:
                if r.collection not in collections:
                    collections[r.collection] = 0
                collections[r.collection] += 1

            for collection, count in collections.items():
                print(f"  • {collection}: {count} records")

        # Summary Statistics
        print_section("SUMMARY STATISTICS")
        print(f"Users: {len(users)}")
        print(f"Projects: {len(projects)}")
        print(f"Engagements: {len(engagements)}")
        print(f"Conversations: {len(conversations)}")
        print(f"Conversation Messages: {len(messages)}")
        print(f"Conversation Summaries: {len(summaries)}")
        print(f"Runs: {len(runs)}")
        print(f"Run Tasks: {len(tasks)}")
        print(f"Memory Items: {len(memories)}")
        print(f"Scheduled Tasks: {len(scheduled)}")
        print(f"Wiki Pages: {len(wiki_pages)}")
        print(f"Reviews: {len(reviews)}")
        print(f"Activity Events: {len(activity)}")
        print(f"Notifications: {len(notifications)}")
        print(f"Workbench Records: {len(records)}")

        print_section("DATABASE CHECK COMPLETE")

    finally:
        db.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
