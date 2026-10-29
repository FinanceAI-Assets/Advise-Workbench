# Error Handling & Failure Recovery - Complete Deployment Guide

Stage 1.3.5: Centralized error tracking, user notifications, and failure recovery

## Complete Implementation Summary

### What Was Built

**4 New Python Modules:**
1. `src/core/error_handling/error_handler.py` - Centralized error tracking service
2. `src/core/notifications/notification_service.py` - User alert system
3. `src/core/observability/openobserve_logger.py` - OpenObserve integration for logs
4. `src/workers/task_orchestration.py` - Failure callback orchestration

**3 REST API Endpoints Groups:**
1. Project failure summary & trends
2. Document failure history
3. User notification management

**2 Database Tables:**
1. `task_failures` - Failure records with retry tracking
2. `in_app_notifications` - User notification queue

---

## Quick Deployment

### Step 1: Install Dependencies (already in requirements.txt)
```bash
pip install -r requirements.txt
```

### Step 2: Apply Database Migration
```bash
alembic upgrade head
# Applies migration/versions/027_error_handling.py
# Creates: task_failures, in_app_notifications, task_failure_metrics tables
```

### Step 3: Register Failure Tracking Routes
✅ DONE - routes already added to `src/app/main.py`

### Step 4: Wire Error Handlers into Celery Tasks

See `ERROR_HANDLER_INTEGRATION_GUIDE.md` for complete integration steps.

Each Celery task needs:
- Error handler callback on exception
- Success handler callback on completion
- Error classification logic

**Tasks to update (12 total):**
- Stage 1.2 (3): parse_document_with_docling, chunk_parsed_content, extract_structured_data
- Stage 1.3.1 (3): embed_chunks, generate_wiki_page, build_search_index
- Stage 1.3.2-4 (4): extract_facts_from_chunks, generate_wiki_pages_from_facts, deduplicate_wiki_pages, generate_embeddings_for_wiki
- Stage 1.1 (2): store_document_in_seaweedfs, (other intake tasks)

### Step 5: Restart Backend
```bash
./scripts/run_agent.sh
```

### Step 6: Verify
```bash
curl http://localhost:8000/api/failure-tracking/project/test_proj/summary
# Should return: {"total_failures": 0, "final_failures": 0, ...}
```

---

## Architecture

```
Document Processing Task
    ↓
    ├─→ Task Fails
    │   └─→ ErrorHandlerService.record_task_failure()
    │       ├─→ Store in task_failures table
    │       ├─→ TaskOrchestrator.on_task_failure()
    │       │   ├─→ OpenObserveLogger.log_task_failure()
    │       │   ├─→ NotificationService.notify_max_retries_exceeded()
    │       │   └─→ InAppNotification stored
    │       └─→ Retry (if error_type is retryable)
    │
    └─→ Task Succeeds
        └─→ TaskOrchestrator.on_task_success()
            ├─→ OpenObserveLogger.log_task_success()
            └─→ InAppNotification sent for milestones
```

---

## Configuration

No additional `.env` settings required. Uses defaults from `src/core/config.py`:

```python
# From config.py (Stage 1.3.5 defaults)
ERROR_HANDLER_MAX_RETRIES=3
ERROR_HANDLER_LOG_TO_OPENOBSERVE=true
NOTIFICATION_SEND_EMAIL=false  # Set to true + SMTP config for emails
OPENOBSERVE_ENDPOINT=http://localhost:5080
```

---

## Database Schema

### task_failures
```sql
id              VARCHAR(64) PK          -- Composite: doc_id + task_name + retry_count
task_name       VARCHAR(100)            -- parse_document_with_docling, etc.
document_file_id VARCHAR(64)            -- Document being processed
project_id      VARCHAR(64) FK
error_message   VARCHAR(500)            -- Truncated to 500 chars
error_type      VARCHAR(100)            -- timeout, api_error, validation_error, etc.
retry_count     INTEGER                 -- Attempt number
max_retries     INTEGER                 -- Max attempts allowed
is_final_failure BOOLEAN                -- true if retry_count >= max_retries
created_at      TIMESTAMP              

Indexes:
  - ix_task_failures_document
  - ix_task_failures_project
  - ix_task_failures_task
  - ix_task_failures_error_type
  - ix_task_failures_created
```

### in_app_notifications
```sql
id              VARCHAR(64) PK
user_id         VARCHAR(64) FK users
document_file_id VARCHAR(64)            -- Optional, for context
project_id      VARCHAR(64) FK
notification_type VARCHAR(50)           -- failure, warning, success, info
title           VARCHAR(255)            -- Short title
message         TEXT                    -- Full message
is_read         BOOLEAN                 -- User-marked as read
read_at         TIMESTAMP               -- When user read it
created_at      TIMESTAMP
updated_at      TIMESTAMP

Indexes:
  - ix_in_app_notifications_user
  - ix_in_app_notifications_project
  - ix_in_app_notifications_type
  - ix_in_app_notifications_created
```

---

## REST API Endpoints

### Get Project Failure Summary
```
GET /api/failure-tracking/project/{project_id}/summary?hours=24

Response:
{
  "project_id": "proj_123",
  "lookback_hours": 24,
  "total_failures": 5,
  "final_failures": 2,
  "by_task": {
    "extract_facts_from_chunks": 3,
    "generate_wiki_pages_from_facts": 2
  },
  "by_error_type": {
    "api_error": 3,
    "timeout": 2
  }
}
```

### Get Recent Failures
```
GET /api/failure-tracking/project/{project_id}/recent-failures?limit=50&task_name=extract_facts_from_chunks

Response:
[
  {
    "id": "failure_...",
    "task_name": "extract_facts_from_chunks",
    "document_file_id": "file_123",
    "error_type": "llm_api_error",
    "error_message": "API timeout after 30s",
    "retry_count": 2,
    "max_retries": 3,
    "is_final_failure": false,
    "created_at": "2026-10-22T12:34:56"
  }
]
```

### Get Document Failure History
```
GET /api/failure-tracking/document/{document_file_id}/failures

Response:
{
  "document_file_id": "file_123",
  "failure_count": 3,
  "final_failures": 1,
  "job_status": "failed",
  "job_error_message": "Max retries exceeded on extract_facts",
  "failure_timeline": [
    {
      "task": "extract_facts_from_chunks",
      "error_type": "api_error",
      "error_message": "API timeout",
      "attempt": 1,
      "max_attempts": 3,
      "timestamp": "2026-10-22T12:30:00"
    },
    ...
  ]
}
```

### Get Error Type Breakdown
```
GET /api/failure-tracking/error-types-breakdown?project_id=proj_123&hours=24

Response:
{
  "project_id": "proj_123",
  "error_types": {
    "api_error": {
      "count": 5,
      "tasks": {"extract_facts": 3, "generate_wiki": 2},
      "final_failures": 2,
      "total_retries": 8
    },
    "timeout": {
      "count": 2,
      "tasks": {"chunk_parsed_content": 2},
      "final_failures": 0,
      "total_retries": 4
    }
  }
}
```

### Get Tasks by Reliability
```
GET /api/failure-tracking/tasks-by-reliability?project_id=proj_123&hours=24

Response:
{
  "project_id": "proj_123",
  "tasks_by_failure_severity": [
    {
      "task_name": "generate_embeddings_for_wiki",
      "total_failures": 3,
      "final_failures": 1,
      "error_types": {"api_error": 2, "timeout": 1}
    },
    {
      "task_name": "deduplicate_wiki_pages",
      "total_failures": 1,
      "final_failures": 0,
      "error_types": {"db_error": 1}
    }
  ]
}
```

### Get User Notifications
```
GET /api/failure-tracking/user/{user_id}/notifications?limit=20&unread_only=true

Response:
[
  {
    "id": "notif_123",
    "notification_type": "failure",
    "title": "Processing Failed: report.pdf",
    "message": "Task extract_facts_from_chunks failed after 3 retries",
    "document_file_id": "file_123",
    "is_read": false,
    "created_at": "2026-10-22T12:30:00"
  }
]
```

### Mark Notification as Read
```
POST /api/failure-tracking/notifications/{notification_id}/mark-read

Response:
{
  "id": "notif_123",
  "is_read": true,
  "read_at": "2026-10-22T12:35:00"
}
```

---

## Monitoring

### OpenObserve Logs

Log stream: `ingestion_pipeline`

Sample events:
```json
{
  "timestamp": "2026-10-22T12:30:45Z",
  "level": "ERROR",
  "task_name": "extract_facts_from_chunks",
  "document_file_id": "file_123",
  "error_message": "API timeout after 30s",
  "error_type": "llm_api_error",
  "retry_count": 2,
  "max_retries": 3,
  "is_final_failure": false
}
```

### Database Queries

Check recent failures:
```sql
SELECT task_name, error_type, COUNT(*) 
FROM task_failures 
WHERE project_id = 'proj_123' 
  AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY task_name, error_type
ORDER BY COUNT(*) DESC;
```

Check user notifications:
```sql
SELECT notification_type, COUNT(*), COUNT(CASE WHEN is_read THEN 1 END) as read_count
FROM in_app_notifications 
WHERE user_id = 'user_123'
GROUP BY notification_type;
```

### Alerts to Set Up

1. **High failure rate:** 
   - Alert if final_failures > 10 in 1 hour per project

2. **Specific task failure:**
   - Alert if task X fails 3+ times in 30 minutes

3. **LLM API errors:**
   - Alert if llm_api_error count increases by 2x from baseline

---

## Integration with Existing Code

### Imports Required

In each Celery task file:
```python
from src.workers.task_orchestration import get_task_orchestrator
from src.core.db.models import DocumentJob, User
```

### Pattern for All Tasks

```python
@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, ...)
def my_task(self, document_file_id: str, project_id: str, ...):
    start_time = datetime.utcnow()
    
    try:
        # ... task logic ...
        
        # On success: call orchestrator
        orchestrator = get_task_orchestrator()
        orchestrator.on_task_success(
            task_name="my_task",
            document_file_id=document_file_id,
            project_id=project_id,
            user_id=user_id,
            user_email=user_email,
            document_filename=filename,
            duration_ms=...,
            result_metrics={"key": value},
        )
        return {"status": "success", ...}
    
    except Exception as e:
        logger.error("[MY_TASK] Failed: %s", str(e))
        
        # On failure: call orchestrator
        try:
            orchestrator = get_task_orchestrator()
            orchestrator.on_task_failure(
                task_name="my_task",
                document_file_id=document_file_id,
                project_id=project_id,
                user_id=user_id,
                user_email=user_email,
                document_filename=filename,
                error_message=str(e)[:500],
                error_type="error_classification",
                retry_count=self.request.retries,
                max_retries=self.max_retries,
                db=db,
            )
        except Exception as handler_error:
            logger.error("[MY_TASK] Error handler failed: %s", str(handler_error))
        
        raise self.retry(exc=e, countdown=60)
```

---

## Testing

### Unit Tests

```bash
pytest tests/unit/test_error_handler.py -v
pytest tests/unit/test_notification_service.py -v
pytest tests/unit/test_task_orchestration.py -v
```

### Integration Tests

```bash
# Start worker
celery -A src.app.celery worker --loglevel=info &

# Trigger failing task
python -m pytest tests/integration/test_error_handling_e2e.py -v

# Check results
curl http://localhost:8000/api/failure-tracking/project/test/summary
```

---

## Files Created/Modified

**New Files:**
- `src/core/error_handling/error_handler.py` (220 lines)
- `src/core/notifications/notification_service.py` (160 lines)
- `src/core/observability/openobserve_logger.py` (260 lines)
- `src/workers/task_orchestration.py` (380 lines)
- `src/app/api/failure_tracking.py` (450 lines)
- `migrations/versions/027_error_handling.py` (160 lines)
- `ERROR_HANDLER_INTEGRATION_GUIDE.md` (Reference guide)

**Modified Files:**
- `src/app/main.py` (+1 import, +1 router registration)
- `src/core/db/models.py` (+3 model classes: TaskFailure, InAppNotification)

---

## Next Steps

1. **Integrate with Celery Tasks:**
   - Follow `ERROR_HANDLER_INTEGRATION_GUIDE.md`
   - Update all 12 tasks across Stages 1.1-1.3
   - Test with integration tests

2. **Wire Email Notifications:**
   - Set `NOTIFICATION_SEND_EMAIL=true` in `.env`
   - Configure SMTP settings
   - Update `NotificationService._send_email()`

3. **OpenObserve Dashboard:**
   - Create dashboard in OpenObserve
   - Query logs by task_name, error_type
   - Set up alerts for failure rates

4. **Frontend Integration:**
   - Show failure history on document detail page
   - Display user notifications in sidebar
   - Add failure dashboard to admin panel

---

## Production Checklist

- [ ] Database migration applied
- [ ] Error handlers integrated into all 12 Celery tasks
- [ ] Integration tests passing
- [ ] Failure tracking endpoints responding
- [ ] OpenObserve receiving logs
- [ ] Email notifications configured (if needed)
- [ ] Frontend showing notifications
- [ ] Monitoring alerts configured
- [ ] Documentation reviewed by team

---
