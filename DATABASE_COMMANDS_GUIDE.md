# Database Inspection & Query Guide

## Overview

This guide covers the database inspection utilities available for the Advise Workbench application. These tools help you check, query, and export records from the SQLite database.

---

## Quick Summary of Current Database State

### Statistics
- **Total Users**: 1
- **Total Projects**: 2
- **Total Conversations**: 1
- **Conversation Messages**: 9
- **Activity Events**: 2
- **Conversation Summaries**: 0 (no idle events yet)
- **Database Tables**: 37

### Key Records

#### Users
```
ID: u_cdca680ce9
Email: prgupta19@deloitte.com
Role: user
Admin: No
Created: 2026-11-03 17:12:36
```

#### Projects
1. **sfasdfa** (ID: p_c780c605fa)
   - Created: 2026-11-03 17:12:55
   - Status: active (Brief stage)
   - Code: SF-001

2. **TestingDBIntegrations** (ID: p_7dcb9fac3d)
   - Created: 2026-11-03 17:14:11
   - Status: active (Brief stage)
   - Code: TE-002

#### Conversations
- **ID**: conv_4101600695
- **Project**: TestingDBIntegrations (p_7dcb9fac3d)
- **User**: prgupta19@deloitte.com
- **Title**: Creative Studio
- **Messages**: 9
- **Created**: 2026-11-03 17:14:16
- **Last Updated**: 2026-11-03 17:19:56

---

## Database Tools

### 1. **check_all_db_records.py** - Full Database Audit

Provides a comprehensive overview of all database tables and their contents.

#### Usage
```bash
python check_all_db_records.py
```

#### Output Sections
- **Users** - All user accounts with email, role, admin status
- **Projects** - All projects and metadata
- **Engagement Meta** - Project engagement settings and idle detection status
- **Project Memberships** - User roles per project
- **Conversations** - All active conversations
- **Conversation Messages** - Message previews and metadata
- **Conversation Summaries** - Summary snapshots (if any exist)
- **Runs** - All execution runs
- **Run Tasks** - Individual task records
- **Memory Items** - Stored preferences and decisions
- **Scheduled Tasks** - Recurring task definitions
- **Wiki Pages** - Knowledge base pages
- **Reviews** - Artifact reviews
- **Activity Events** - Audit trail
- **Notifications** - User notifications
- **Workbench Records** - Generic workbench data

#### Example Output
```
================================================================================
                                     USERS                                      
================================================================================

Total: 1
  • u_cdca680ce9
    Email: prgupta19@deloitte.com
    Name: None
    Role: user
    Admin: False
    Created: 2026-11-03 17:12:36
```

---

### 2. **db_sql_queries.py** - Targeted SQL Queries

Runs specific SQL queries to examine database relationships and details.

#### Usage
```bash
python db_sql_queries.py
```

#### Available Queries
1. **ALL USERS** - User details
2. **ALL PROJECTS** - Project catalog
3. **ENGAGEMENT DETAILS WITH IDLE DETECTION** - Idle timeout settings
4. **ALL CONVERSATIONS** - Conversation records
5. **CONVERSATION MESSAGES (SUMMARY)** - Message metadata
6. **CONVERSATION MESSAGE CONTENT PREVIEW** - Message text previews
7. **CONVERSATION SUMMARIES STATISTICS** - Summary trigger types
8. **PROJECT MEMBERS (WITH DETAILS)** - User-project relationships
9. **ALL RUNS (TOKEN & COST INFO)** - Token usage and costs
10. **RUN TASKS (DETAILED)** - Task execution details
11. **MEMORY ITEMS (ACTIVE ONLY)** - Active memory records
12. **ACTIVITY LOG** - System activity timeline
13. **WORKBENCH RECORDS BY COLLECTION** - Record organization
14. **TOTAL TABLES** - Database schema info
15. **WIKI PAGES BY TYPE AND CATEGORY** - Knowledge organization
16. **SCHEDULED TASKS STATUS** - Task scheduling info

---

### 3. **db_export_utility.py** - Export to CSV/JSON

Exports database records to portable formats for analysis or backup.

#### Usage
```bash
python db_export_utility.py
```

#### Output Files

All files are saved to: `db_exports/`

**CSV Exports**
- `users.csv` - User accounts
- `projects.csv` - Project records
- `engagement_meta.csv` - Engagement settings
- `memberships.csv` - Project memberships
- `conversations.csv` - Conversation records
- `conversation_messages.csv` - All messages
- `activity_events.csv` - Activity log
- `export_summary.json` - Export metadata

**JSON Exports** (same as CSV with `.json` extension)

**Summary Report**
- `export_summary.json` - Export statistics and metadata

---

## Database Schema Overview

### Core Tables

#### users
```sql
id (PK)
email (UNIQUE)
hashed_password
created_at
full_name
job_title
is_admin
role
```

#### projects
```sql
id (PK)
name
created_by (FK -> users)
created_at
```

#### engagement_meta
```sql
id (PK)
project_id (FK -> projects, UNIQUE)
code, type, stage, status
enable_idle_detection (boolean)
idle_timeout_seconds (default: 600)
last_activity_at
engagement_session_id
created_at, updated_at
```

#### conversations
```sql
id (PK)
project_id (FK -> projects)
user_id (FK -> users)
title
skill_id
created_at, updated_at
```

#### conversation_messages
```sql
id (PK)
conversation_id (FK -> conversations)
role (assistant|user)
content (TEXT)
metadata_json
source_type
source_freshness_at
created_at
```

#### conversation_summaries
```sql
id (PK)
project_id (FK -> projects, UNIQUE)
summary_text
summary_metadata_json
state_snapshot_json
conversation_fsm_state
summary_trigger (idle_10min|session_closed)
idle_duration_seconds
created_at, updated_at
restored_at
```

#### memberships
```sql
id (PK)
project_id (FK -> projects)
user_id (FK -> users)
role (Owner|Editor|Viewer|etc)
```

---

## Common Use Cases

### 1. Check All Users
```bash
python check_all_db_records.py | grep -A 20 "USERS"
```

### 2. View Conversation History
```bash
python db_sql_queries.py | grep -A 30 "CONVERSATION MESSAGE"
```

### 3. Check Project Engagement Settings
```bash
python db_sql_queries.py | grep -A 20 "ENGAGEMENT DETAILS"
```

### 4. Export Conversation Data for Analysis
```bash
python db_export_utility.py
# Then open: db_exports/conversation_messages.json
```

### 5. Check Activity Audit Trail
```bash
python db_sql_queries.py | grep -A 10 "ACTIVITY LOG"
```

### 6. Verify Idle Detection Configuration
```bash
python check_all_db_records.py | grep -A 15 "Idle Detection"
```

---

## Idle Detection / Conversation Summaries

### Current Status
- **Conversation Summaries**: 0 (not yet triggered)
- **Idle Detection**: Enabled for all engagements (600 seconds timeout)

### How to Trigger Summaries
1. Open an engagement in the UI
2. Send a message to SHELDON
3. Wait 10 minutes of inactivity, OR
4. Call the close engagement API endpoint:
   ```
   POST /api/v1/projects/{project_id}/close-engagement-session
   ```

### What Gets Recorded
When idle detection triggers:
- `conversation_summaries` table records state snapshot
- `summary_trigger` = "idle_10min" or "session_closed"
- `conversation_fsm_state` = current state machine state
- `state_snapshot_json` = complete conversation context
- `discovery_slots_snapshot` = discovered information
- `decision_answers_snapshot` = captured decisions

---

## Direct SQL Commands

For advanced users, you can write custom Python scripts using SQLAlchemy:

### Example 1: Count Messages per Conversation
```python
from src.core.db.session import SessionLocal
from src.core.db.models import ConversationMessage
from sqlalchemy import func

db = SessionLocal()
result = db.query(
    ConversationMessage.conversation_id,
    func.count(ConversationMessage.id).label('message_count')
).group_by(ConversationMessage.conversation_id).all()

for conv_id, count in result:
    print(f"Conversation {conv_id}: {count} messages")
```

### Example 2: Get Latest Messages by Conversation
```python
from src.core.db.session import SessionLocal
from src.core.db.models import ConversationMessage
from sqlalchemy import desc

db = SessionLocal()
latest = db.query(ConversationMessage)\
    .order_by(desc(ConversationMessage.created_at))\
    .limit(10)\
    .all()

for msg in latest:
    print(f"{msg.role}: {msg.content[:100]}")
```

### Example 3: Find Conversations by Project
```python
from src.core.db.session import SessionLocal
from src.core.db.models import Conversation

db = SessionLocal()
conversations = db.query(Conversation)\
    .filter(Conversation.project_id == 'p_7dcb9fac3d')\
    .all()

for conv in conversations:
    print(f"{conv.title} - {len(conv.id)} messages")
```

---

## Performance Tips

1. **For Large Exports**: The export utility handles up to thousands of records efficiently
2. **SQL Queries**: Add `.limit(100)` for large result sets
3. **Pagination**: Use `.offset()` and `.limit()` for big datasets
4. **Indexes**: Most frequently queried columns already have indexes:
   - `projects.id`, `users.id`, `conversations.project_id`
   - `conversation_messages.conversation_id`, `conversation_messages.created_at`
   - `engagement_meta.project_id`

---

## Troubleshooting

### Migration Not Applied
If you see "Migration not applied yet":
```bash
alembic upgrade head
```

### Database Locked
If database is locked, make sure no other processes are using it:
```bash
# Check for running FastAPI server
# Kill if necessary and retry
```

### Export Directory Issues
If export fails, ensure the directory exists:
```bash
mkdir db_exports
python db_export_utility.py
```

---

## Database Maintenance

### Backup Current Database
```bash
# Copy advise_workbench.db to a backup location
cp advise_workbench.db advise_workbench.db.backup
```

### Clear Conversation Messages (Archive)
```python
from src.core.db.session import SessionLocal
from src.core.db.models import ConversationMessage
from datetime import datetime, timedelta

db = SessionLocal()
# Delete messages older than 90 days
cutoff = datetime.now() - timedelta(days=90)
db.query(ConversationMessage).filter(
    ConversationMessage.created_at < cutoff
).delete()
db.commit()
```

### Optimize Database
```bash
# Run SQLite optimization
sqlite3 advise_workbench.db "VACUUM;"
```

---

## File Locations

| Item | Path |
|------|------|
| Database File | `advise_workbench.db` |
| Query Scripts | Root directory |
| Exports | `db_exports/` |
| Models | `src/core/db/models.py` |
| Session | `src/core/db/session.py` |
| Migrations | `migrations/versions/` |

---

## Additional Resources

- Database Models: `src/core/db/models.py`
- Session Management: `src/core/db/session.py`
- Alembic Migrations: `migrations/`
- API Routes: `src/app/api/`

---

## Questions?

For issues or questions:
1. Check logs: Application logs in `src/app/main.py`
2. Review CLAUDE.md: Project instructions and setup
3. Check migrations: `migrations/versions/` for schema changes

