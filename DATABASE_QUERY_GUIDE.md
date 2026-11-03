# Database Query Guide - Conversation Summaries

## Quick Database Checks for Existing Engagements

### 1. Check via Python REPL (Recommended)

```bash
cd "D:\Users\PriyankaGupta\Documents\Conversation comp"
python
```

```python
# Import required modules
from src.core.db.session import SessionLocal
from src.core.db.models import ConversationSummary, EngagementMeta, Project
from sqlalchemy import select

# Create session
db = SessionLocal()

# Query 1: Check all conversation summaries
print("=== All Conversation Summaries ===")
summaries = db.query(ConversationSummary).all()
for s in summaries:
    print(f"\nProject ID: {s.project_id}")
    print(f"  Summary: {s.summary_text[:100]}...")
    print(f"  State: {s.conversation_fsm_state}")
    print(f"  Trigger: {s.summary_trigger}")
    print(f"  Created: {s.created_at}")
    print(f"  Updated: {s.updated_at}")
    print(f"  Restored: {s.restored_at}")
    print(f"  Idle Duration: {s.idle_duration_seconds}s")

# Query 2: Check specific engagement
project_id = "proj_xxxx"  # Replace with actual project ID
print(f"\n=== Engagement Summary for {project_id} ===")
summary = db.query(ConversationSummary).filter(
    ConversationSummary.project_id == project_id
).first()

if summary:
    print(f"Summary Text: {summary.summary_text}")
    print(f"FSM State: {summary.conversation_fsm_state}")
    print(f"Trigger: {summary.summary_trigger}")
    print(f"Idle Duration: {summary.idle_duration_seconds} seconds")
    print(f"State Snapshot Keys: {list(json.loads(summary.state_snapshot_json).keys())}")
    print(f"Discovery Slots: {json.loads(summary.discovery_slots_snapshot)}")
    print(f"Decision Answers: {json.loads(summary.decision_answers_snapshot)}")
else:
    print("No summary found for this engagement")

# Query 3: Check EngagementMeta idle detection settings
print(f"\n=== EngagementMeta Idle Detection ===")
meta = db.query(EngagementMeta).filter(
    EngagementMeta.project_id == project_id
).first()

if meta:
    print(f"Engagement Session ID: {meta.engagement_session_id}")
    print(f"Last Activity: {meta.last_activity_at}")
    print(f"Idle Timeout (seconds): {meta.idle_timeout_seconds}")
    print(f"Idle Detection Enabled: {meta.enable_idle_detection}")
else:
    print("No EngagementMeta found")

# Query 4: Count summaries and engagement stats
print("\n=== Summary Statistics ===")
total_summaries = db.query(ConversationSummary).count()
recently_restored = db.query(ConversationSummary).filter(
    ConversationSummary.restored_at.isnot(None)
).count()
idle_triggered = db.query(ConversationSummary).filter(
    ConversationSummary.summary_trigger == "idle_10min"
).count()
close_triggered = db.query(ConversationSummary).filter(
    ConversationSummary.summary_trigger == "session_closed"
).count()

print(f"Total Summaries: {total_summaries}")
print(f"Recently Restored: {recently_restored}")
print(f"Idle-triggered: {idle_triggered}")
print(f"Close-triggered: {close_triggered}")

# Query 5: Find engagements idle > 5 minutes
print("\n=== Engagements with Long Idle Duration ===")
from datetime import datetime
long_idle = db.query(ConversationSummary).filter(
    ConversationSummary.idle_duration_seconds > 300
).all()

for s in long_idle:
    print(f"{s.project_id}: {s.idle_duration_seconds}s idle")

db.close()
```

---

## 2. Direct SQL Queries

### Using SQLite CLI (if using SQLite)

```bash
sqlite3 "advise_workbench.db"
```

```sql
-- Show all conversation summaries
SELECT 
    project_id,
    summary_text,
    conversation_fsm_state,
    summary_trigger,
    idle_duration_seconds,
    created_at,
    updated_at,
    restored_at
FROM conversation_summaries;

-- Show summary count by trigger
SELECT 
    summary_trigger,
    COUNT(*) as count,
    AVG(idle_duration_seconds) as avg_idle_sec
FROM conversation_summaries
GROUP BY summary_trigger;

-- Show recently updated summaries
SELECT 
    project_id,
    summary_text,
    updated_at
FROM conversation_summaries
ORDER BY updated_at DESC
LIMIT 10;

-- Show restored engagements
SELECT 
    project_id,
    summary_text,
    restored_at,
    (JULIANDAY(restored_at) - JULIANDAY(created_at)) * 24 * 60 as minutes_until_restored
FROM conversation_summaries
WHERE restored_at IS NOT NULL
ORDER BY restored_at DESC;

-- Check EngagementMeta idle settings
SELECT 
    project_id,
    engagement_session_id,
    last_activity_at,
    idle_timeout_seconds,
    enable_idle_detection
FROM engagement_meta
WHERE enable_idle_detection = 1;
```

---

## 3. Python Script for Detailed Analysis

Create file `check_summaries.py`:

```python
#!/usr/bin/env python
"""Check conversation summaries in database."""

import json
from datetime import datetime
from src.core.db.session import SessionLocal
from src.core.db.models import ConversationSummary, EngagementMeta, Project
from src.core.tz import ist_now

def check_all_summaries():
    """Display all conversation summaries."""
    db = SessionLocal()
    
    summaries = db.query(ConversationSummary).all()
    
    if not summaries:
        print("No summaries found in database")
        return
    
    print(f"\n{'='*80}")
    print(f"TOTAL SUMMARIES: {len(summaries)}")
    print(f"{'='*80}\n")
    
    for i, summary in enumerate(summaries, 1):
        print(f"{i}. PROJECT: {summary.project_id}")
        print(f"   Summary: {summary.summary_text}")
        print(f"   State: {summary.conversation_fsm_state}")
        print(f"   Trigger: {summary.summary_trigger}")
        print(f"   Idle Duration: {summary.idle_duration_seconds}s" if summary.idle_duration_seconds else "   Idle Duration: N/A")
        print(f"   Created: {summary.created_at}")
        print(f"   Updated: {summary.updated_at}")
        print(f"   Restored: {summary.restored_at if summary.restored_at else 'Not yet restored'}")
        
        # Parse snapshots
        try:
            state_snap = json.loads(summary.state_snapshot_json)
            print(f"   State Snapshot Keys: {list(state_snap.keys())}")
            
            discovery = json.loads(summary.discovery_slots_snapshot)
            if discovery:
                print(f"   Discovered: {list(discovery.keys())}")
            
            decisions = json.loads(summary.decision_answers_snapshot)
            if decisions:
                print(f"   Decisions: {list(decisions.keys())}")
        except json.JSONDecodeError:
            print(f"   [Error parsing snapshots]")
        
        print()
    
    # Statistics
    print(f"\n{'='*80}")
    print("STATISTICS")
    print(f"{'='*80}")
    
    idle_count = sum(1 for s in summaries if s.summary_trigger == "idle_10min")
    close_count = sum(1 for s in summaries if s.summary_trigger == "session_closed")
    restored_count = sum(1 for s in summaries if s.restored_at)
    avg_idle = sum(s.idle_duration_seconds for s in summaries if s.idle_duration_seconds) / max(1, idle_count)
    
    print(f"Idle-triggered: {idle_count}")
    print(f"Close-triggered: {close_count}")
    print(f"Restored: {restored_count}")
    print(f"Average Idle Duration: {avg_idle:.0f}s")
    
    db.close()

def check_engagement_idle_settings():
    """Check EngagementMeta idle detection settings."""
    db = SessionLocal()
    
    metas = db.query(EngagementMeta).filter(
        EngagementMeta.enable_idle_detection == True
    ).all()
    
    if not metas:
        print("No engagements with idle detection enabled")
        return
    
    print(f"\n{'='*80}")
    print(f"IDLE DETECTION SETTINGS: {len(metas)} engagements")
    print(f"{'='*80}\n")
    
    for meta in metas:
        print(f"Project: {meta.project_id}")
        print(f"  Timeout: {meta.idle_timeout_seconds}s")
        print(f"  Enabled: {meta.enable_idle_detection}")
        print(f"  Last Activity: {meta.last_activity_at if meta.last_activity_at else 'Never'}")
        
        # Calculate current idle time
        if meta.last_activity_at:
            idle_secs = (ist_now() - meta.last_activity_at).total_seconds()
            is_idle = idle_secs > meta.idle_timeout_seconds
            print(f"  Current Idle: {idle_secs:.0f}s {'(IDLE!)' if is_idle else '(Active)'}")
        
        print()
    
    db.close()

if __name__ == "__main__":
    print("\n" + "="*80)
    print("CONVERSATION SUMMARIES DATABASE CHECK")
    print("="*80)
    
    check_all_summaries()
    check_engagement_idle_settings()
    
    print("\n" + "="*80)
    print("Check complete")
    print("="*80)
```

Run it:
```bash
python check_summaries.py
```

---

## 4. Check Active Sessions (In-Memory)

```python
from src.extensions.conversation_session import EngagementSessionRegistry

# Check active sessions
active_sessions = EngagementSessionRegistry._sessions
print(f"Active Sessions: {len(active_sessions)}")
for project_id, session in active_sessions.items():
    idle_secs = session.get_idle_duration_seconds()
    print(f"  {project_id}: {idle_secs}s idle (timeout: {session.idle_timeout_sec}s)")
```

---

## 5. Key Queries for Troubleshooting

### Check for duplicate summaries (should be 0)
```python
from sqlalchemy import func
db = SessionLocal()
duplicates = db.query(
    ConversationSummary.project_id,
    func.count(ConversationSummary.id).label('count')
).group_by(ConversationSummary.project_id).having(
    func.count(ConversationSummary.id) > 1
).all()

if duplicates:
    print(f"ERROR: Found {len(duplicates)} projects with multiple summaries!")
else:
    print("OK: No duplicate summaries (UNIQUE constraint working)")
```

### Check expiration
```python
from datetime import datetime
from src.core.tz import ist_now

db = SessionLocal()
expired = db.query(ConversationSummary).filter(
    ConversationSummary.expires_at < ist_now()
).count()

print(f"Expired summaries (cleanup needed): {expired}")
```

### Check restored summaries
```python
db = SessionLocal()
restored = db.query(ConversationSummary).filter(
    ConversationSummary.restored_at.isnot(None)
).all()

for s in restored:
    time_to_restore = (s.restored_at - s.created_at).total_seconds() / 60
    print(f"{s.project_id}: Restored after {time_to_restore:.1f} minutes")
```

---

## 6. Real-Time Monitoring Script

Create `monitor_summaries.py`:

```python
#!/usr/bin/env python
"""Monitor conversation summaries in real-time."""

import time
import json
from datetime import datetime
from src.core.db.session import SessionLocal
from src.core.db.models import ConversationSummary, EngagementMeta
from src.extensions.conversation_session import EngagementSessionRegistry
from src.core.tz import ist_now

def monitor_loop(interval=30):
    """Monitor summaries and sessions continuously."""
    print(f"Monitoring every {interval} seconds... (Ctrl+C to stop)\n")
    
    try:
        while True:
            db = SessionLocal()
            
            # Get counts
            total = db.query(ConversationSummary).count()
            idle_triggered = db.query(ConversationSummary).filter(
                ConversationSummary.summary_trigger == "idle_10min"
            ).count()
            restored = db.query(ConversationSummary).filter(
                ConversationSummary.restored_at.isnot(None)
            ).count()
            
            # Active sessions
            active_sessions = len(EngagementSessionRegistry._sessions)
            
            # Idle sessions
            idle_sessions = sum(
                1 for s in EngagementSessionRegistry._sessions.values() 
                if s.is_idle()
            )
            
            # Display
            print(f"[{ist_now().strftime('%H:%M:%S')}]")
            print(f"  Summaries: {total} total | {idle_triggered} idle-triggered | {restored} restored")
            print(f"  Active Sessions: {active_sessions} | Idle: {idle_sessions}")
            
            # Show any recent updates
            recent = db.query(ConversationSummary).order_by(
                ConversationSummary.updated_at.desc()
            ).limit(3).all()
            
            if recent:
                print(f"  Recent:")
                for s in recent:
                    print(f"    {s.project_id}: {s.summary_text[:50]}...")
            
            print()
            
            db.close()
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped")

if __name__ == "__main__":
    monitor_loop(interval=10)  # Check every 10 seconds
```

Run it:
```bash
python monitor_summaries.py
```

---

## Summary of Checks

| Check | Command | Purpose |
|-------|---------|---------|
| All summaries | `db.query(ConversationSummary).all()` | View all saved summaries |
| Specific engagement | `db.query(ConversationSummary).filter(project_id=...)` | Check one engagement's summary |
| Idle settings | `db.query(EngagementMeta).filter(enable_idle_detection=True)` | View idle detection config |
| Active sessions | `EngagementSessionRegistry._sessions` | See which engagements are active |
| Restore tracking | `filter(restored_at.isnot(None))` | Find restorations |
| Duplicates | `GROUP BY project_id HAVING count > 1` | Verify UNIQUE constraint works |
| Expiration | `filter(expires_at < now())` | Check cleanup needed |

---

## Expected Data After Implementation

After running the system for a while with engagements:

✅ `conversation_summaries` table has rows (one per active engagement)  
✅ Each row has ONE entry per project_id (UNIQUE constraint)  
✅ `summary_text` contains 2-3 line summaries like: "Discovered: client, audience | Decided: format_pptx | Status: ready_to_plan"  
✅ `state_snapshot_json` contains complete state for restoration  
✅ `restored_at` is NULL until engagement is resumed  
✅ `idle_duration_seconds` shows time before summary was generated  
✅ `EngagementMeta` has idle settings (timeout: 600s, enabled: true)  

---

## Notes

- Database file: `advise_workbench.db` (at repo root)
- All times are in IST (Indian Standard Time)
- UPSERT ensures ONE summary per engagement (no duplicates)
- Background task runs every 2 minutes to detect idle
- Set `enable_idle_detection=False` to disable for specific engagement
