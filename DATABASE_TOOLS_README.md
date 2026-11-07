# Database Tools & Commands Reference

Quick reference for all database inspection and query tools available in the Advise Workbench application.

---

## Available Tools

### 1. **Quick Stats** ⚡ (Fastest)
```bash
python quick_db_stats.py
```
**Best for**: Quick overview of total records in each table  
**Output**: Bar chart with counts and latest activity  
**Time**: < 1 second

### 2. **Full Audit** 📊 (Comprehensive)
```bash
python check_all_db_records.py
```
**Best for**: Complete inspection of all records with details  
**Output**: Detailed information for each table (previews for large sets)  
**Time**: < 2 seconds

### 3. **SQL Queries** 🔍 (Targeted)
```bash
python db_sql_queries.py
```
**Best for**: Specific queries with joins and relationships  
**Output**: 16 different pre-built SQL queries  
**Time**: < 2 seconds

### 4. **Export Data** 💾 (Portability)
```bash
python db_export_utility.py
```
**Best for**: Exporting records for analysis, backup, or sharing  
**Output**: CSV and JSON files in `db_exports/` folder  
**Time**: < 3 seconds

---

## What's In Your Database Right Now?

```
╔═══════════════════════════════════════════╗
║        DATABASE SUMMARY (Nov 3, 2026)     ║
╠═══════════════════════════════════════════╣
║ Users:                      1              ║
║ Projects:                   2              ║
║ Conversations:              1              ║
║ Messages:                   9              ║
║ Total Records:             20              ║
╠═══════════════════════════════════════════╣
║ Conversation Summaries:     0 (not yet)   ║
║ Runs:                       0              ║
║ Memory Items:               0              ║
║ Wiki Pages:                 0              ║
╚═══════════════════════════════════════════╝
```

### Recent Activity
- Last message: **2026-11-03 17:30:40**
- Last user action: **2026-11-03 17:30:40**
- Projects created: **2026-11-03 17:12:55 - 17:14:11**

---

## User Information

| Field | Value |
|-------|-------|
| **ID** | u_cdca680ce9 |
| **Email** | prgupta19@deloitte.com |
| **Role** | user |
| **Admin** | No |
| **Created** | 2026-11-03 17:12:36 |

---

## Project Details

### Project 1: **sfasdfa**
- **ID**: p_c780c605fa
- **Created**: 2026-11-03 17:12:55
- **Stage**: Brief
- **Status**: Active
- **Code**: SF-001
- **Idle Detection**: Enabled (600s timeout)

### Project 2: **TestingDBIntegrations**
- **ID**: p_7dcb9fac3d
- **Created**: 2026-11-03 17:14:11
- **Stage**: Brief
- **Status**: Active
- **Code**: TE-002
- **Idle Detection**: Enabled (600s timeout)
- **Conversations**: 1 (Creative Studio)

---

## Conversation Details

### Conversation: "Creative Studio"
- **ID**: conv_4101600695
- **Project**: TestingDBIntegrations
- **User**: prgupta19@deloitte.com
- **Created**: 2026-11-03 17:14:16
- **Updated**: 2026-11-03 17:19:56
- **Messages**: 9

#### Message History
1. **17:14:16** - Assistant: Welcome to Creative Studio
2. **17:14:25** - User: Hi Sheldon
3. **17:15:09** - Assistant: Northwind info
4. **17:16:44** - User: Create proposal for Northwind SAP FY 2027
5. **17:17:30** - Assistant: Proposal alignment
6. **17:18:57** - User: Manufacturing focus info
7. **17:19:56** - Assistant: Case-led narrative info
8. **17:29:54** - User: I'd like case_led
9. **17:30:40** - Assistant: Case-led approach confirmed

---

## Database Commands by Use Case

### **Check Everything**
```bash
# Full comprehensive audit
python check_all_db_records.py
```

### **Quick Glance**
```bash
# Just the numbers
python quick_db_stats.py
```

### **Find Specific Info**
```bash
# Run SQL queries for relationships
python db_sql_queries.py
```

### **Export for External Use**
```bash
# Create CSV/JSON files for analysis
python db_export_utility.py
# Then check: db_exports/ folder
```

### **Verify Idle Detection**
```bash
python quick_db_stats.py
# Look for "Engagements: 2" with idle detection enabled
```

### **Check Conversation History**
```bash
python db_sql_queries.py | grep -A 20 "CONVERSATION MESSAGE CONTENT"
```

---

## What Each Tool Outputs

### quick_db_stats.py
```
============================================================
DATABASE STATISTICS - QUICK VIEW
============================================================

Users                    1  █
Projects                 2  ██
Messages                 9  █████████
...
Total Records           20
------------------------------------------------------------
LATEST ACTIVITY
  • Message         2026-11-03 17:30:40
  ...
```

### check_all_db_records.py
```
================================================================================
                                USERS
================================================================================
Total: 1
  • u_cdca680ce9
    Email: prgupta19@deloitte.com
    Role: user
    ...

================================================================================
                             CONVERSATIONS
================================================================================
Total: 1
  • conv_4101600695
    Title: Creative Studio
    ...
```

### db_sql_queries.py
```
================================================================================
                          PROJECT MEMBERS (WITH DETAILS)
================================================================================
project_id | name | user_id | email | role
p_7dcb9fac3d | TestingDBIntegrations | u_cdca680ce9 | prgupta19@deloitte.com | Owner
```

### db_export_utility.py
```
Files Created:
  • users.csv (0.2 KB)
  • projects.csv (0.2 KB)
  • conversations.csv (0.2 KB)
  • conversation_messages.csv (7.5 KB)
  ...
```

---

## Database Schema (Key Tables)

```
users
├── id (PK)
├── email
├── role
└── is_admin

projects
├── id (PK)
├── name
├── created_by (FK → users)
└── created_at

conversations
├── id (PK)
├── project_id (FK → projects)
├── user_id (FK → users)
├── title
└── created_at

conversation_messages
├── id (PK)
├── conversation_id (FK → conversations)
├── role (user|assistant)
├── content
└── created_at

engagement_meta
├── id (PK)
├── project_id (FK → projects)
├── idle_timeout_seconds (600)
├── enable_idle_detection (true)
└── last_activity_at
```

---

## Export Files Location

All exports are saved to: **`db_exports/`**

```
db_exports/
├── users.csv
├── users.json
├── projects.csv
├── projects.json
├── conversations.csv
├── conversations.json
├── conversation_messages.csv
├── conversation_messages.json
├── engagement_meta.csv
├── engagement_meta.json
├── memberships.csv
├── memberships.json
├── activity_events.csv
├── activity_events.json
└── export_summary.json
```

---

## Common Queries

### Count All Records
```bash
python quick_db_stats.py
```

### Get All Users with Projects
```bash
python db_sql_queries.py | grep -A 20 "PROJECT MEMBERS"
```

### View Recent Messages
```bash
python db_sql_queries.py | grep -A 15 "CONVERSATION MESSAGE CONTENT"
```

### Check Idle Detection Settings
```bash
python db_sql_queries.py | grep -A 10 "ENGAGEMENT DETAILS"
```

### Get Activity Timeline
```bash
python db_sql_queries.py | grep -A 10 "ACTIVITY LOG"
```

---

## Troubleshooting

### Database file not found
```bash
# Check if database exists
ls -la advise_workbench.db
# If missing, run migrations
alembic upgrade head
```

### SQLite3 issues
```bash
# Install if needed
pip install sqlalchemy sqlite3
```

### Export folder issues
```bash
# Create folder if missing
mkdir -p db_exports
python db_export_utility.py
```

### Migration not applied
```bash
# Apply all pending migrations
alembic upgrade head
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `quick_db_stats.py` | Quick statistics summary |
| `check_all_db_records.py` | Comprehensive database audit |
| `db_sql_queries.py` | Pre-built SQL queries |
| `db_export_utility.py` | Export to CSV/JSON |
| `quick_check_db.py` | Conversation summary check |
| `DATABASE_COMMANDS_GUIDE.md` | Detailed SQL guide |
| `DATABASE_TOOLS_README.md` | This file |

---

## Quick Start

### First Time Setup
```bash
# 1. Check database exists
python quick_db_stats.py

# 2. Run full audit
python check_all_db_records.py

# 3. Export everything
python db_export_utility.py

# 4. Check exports
ls -la db_exports/
```

### Daily Usage
```bash
# Check current state
python quick_db_stats.py

# Deep dive if needed
python check_all_db_records.py
```

### Analysis & Backup
```bash
# Export current data
python db_export_utility.py

# Store exports
cp -r db_exports/ db_exports_backup_$(date +%Y%m%d)/
```

---

## Performance Notes

- **Database size**: ~1-2 MB (with 20 records)
- **All scripts**: < 2 seconds execution
- **Export time**: < 3 seconds
- **Idle timeout**: 600 seconds (10 minutes)

---

## Next Steps

1. **Monitor Idle Detection**: Wait for 10 minutes of inactivity to trigger conversation summaries
2. **Create More Conversations**: Test with different projects and users
3. **Run Experiments**: Use export data for analysis
4. **Archive Old Data**: Clean up using the guides

---

## Support

For detailed information, see:
- `DATABASE_COMMANDS_GUIDE.md` - Complete SQL reference
- `CLAUDE.md` - Project setup guide
- `src/core/db/models.py` - Database schema definitions
- `README_RUN.md` - Setup and run instructions

