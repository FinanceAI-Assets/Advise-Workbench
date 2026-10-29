# Wiring Error Handlers into Celery Tasks - Implementation Guide

Stage 1.3.5: Complete Error Handling Integration

## Overview

All Celery tasks from Stages 1.1-1.3 need to be updated with error handling callbacks. This guide provides the exact code patterns to apply.

---

## Pattern 1: Task Failure Callback

Add to EVERY `@shared_task` decorated function:

```python
from src.workers.task_orchestration import get_task_orchestrator

# Inside the except block (when catching Exception):
except Exception as e:
    logger.error("[TASK_NAME] Failed (attempt %d): %s", self.request.retries, str(e))
    
    # NEW: Log failure to error handler
    try:
        db = next(get_db_sync())
        orchestrator = get_task_orchestrator()
        orchestrator.on_task_failure(
            task_name="task_function_name",  # From @shared_task def name
            document_file_id=document_file_id,
            project_id=project_id,
            user_id="user_id_from_context",  # May need to query from DocumentJob
            user_email="email_from_context",
            document_filename=filename,
            error_message=str(e)[:500],
            error_type=self._classify_error(e),  # See error classification below
            retry_count=self.request.retries,
            max_retries=self.max_retries,
            db=db,
        )
    except Exception as handler_error:
        logger.error("[TASK_NAME] Failed to call error handler: %s", str(handler_error))
    finally:
        db.close()
    
    raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

---

## Pattern 2: Success Callback

Add to EVERY task's success path (just before return):

```python
# NEW: Log success
try:
    orchestrator = get_task_orchestrator()
    orchestrator.on_task_success(
        task_name="task_function_name",
        document_file_id=document_file_id,
        project_id=project_id,
        user_id="user_id_from_context",
        user_email="email_from_context",
        document_filename=filename,
        duration_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
        result_metrics={
            "chunks_created": chunk_count,  # or relevant metric
            "duration_ms": duration_ms,
        },
    )
except Exception as handler_error:
    logger.error("[TASK_NAME] Failed to call success handler: %s", str(handler_error))

return {
    "document_file_id": document_file_id,
    "status": "success",
    ...
}
```

---

## Pattern 3: Error Classification

Add this helper method to task modules:

```python
@staticmethod
def _classify_error(exc: Exception) -> str:
    """Classify error type for retry logic."""
    exc_str = str(exc).lower()
    
    # Network/transient errors
    if "timeout" in exc_str or "connection" in exc_str:
        return "timeout"
    if "429" in exc_str or "rate_limit" in exc_str:
        return "rate_limit"
    
    # LLM API errors
    if "anthropic" in exc_str or "api" in exc_str:
        return "llm_api_error"
    
    # Database errors
    if "database" in exc_str or "sql" in exc_str:
        return "db_error"
    
    # Validation errors
    if "validation" in exc_str or "format" in exc_str:
        return "validation_error"
    
    return "unknown_error"
```

---

## Files to Update - COMPLETE LIST

### Stage 1.2: Parsing Tasks
**File:** `src/workers/document_parsing_tasks.py`

Tasks to update:
1. `parse_document_with_docling` - Add error handler + success callback
2. `chunk_parsed_content` - Add error handler + success callback
3. `extract_structured_data` - Add error handler + success callback

### Stage 1.3.1: Embeddings Tasks
**File:** `src/workers/document_embedding_tasks.py`

Tasks to update:
1. `embed_chunks` - Add error handler + success callback
2. `generate_wiki_page` - Add error handler + success callback
3. `build_search_index` - Add error handler + success callback

### Stage 1.3.2-4: Knowledge Building Tasks
**File:** `src/workers/knowledge_building_tasks.py`

Tasks to update:
1. `extract_facts_from_chunks` - Add error handler + success callback
2. `generate_wiki_pages_from_facts` - Add error handler + success callback
3. `deduplicate_wiki_pages` - Add error handler + success callback
4. `generate_embeddings_for_wiki` - Add error handler + success callback

### Stage 1.1: Intake Tasks
**File:** `src/workers/document_intake_tasks.py`

Tasks to update:
1. `store_document_in_seaweedfs` - Add error handler + success callback
2. (Any other intake tasks)

---

## Getting User Context in Tasks

Tasks need `user_id` and `user_email` to send notifications. Options:

### Option A: Query from DocumentJob (Recommended)

```python
from src.core.db.models import DocumentJob, User

db = next(get_db_sync())
try:
    # Find the job
    doc_job = db.query(DocumentJob).filter(
        DocumentJob.id == document_file_id
    ).first()
    
    if doc_job:
        user_id = doc_job.user_id
        user = db.query(User).filter(User.id == user_id).first()
        user_email = user.email if user else "unknown@example.com"
    else:
        user_id = "unknown"
        user_email = "unknown@example.com"
finally:
    db.close()
```

### Option B: Pass as Task Arguments

When enqueueing task, add user_id and user_email:
```python
# In API route
task = my_celery_task.delay(
    document_file_id=...,
    project_id=...,
    user_id=current_user.id,      # NEW
    user_email=current_user.email,  # NEW
    ...
)
```

---

## Complete Example: Updating parse_document_with_docling

BEFORE:
```python
@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, ...)
def parse_document_with_docling(self, document_file_id: str, project_id: str, ...):
    try:
        # ... parsing logic ...
        return {"status": "success", ...}
    except Exception as e:
        logger.error("[PARSE_TASK] Failed: %s", str(e))
        raise self.retry(exc=e, countdown=60)
```

AFTER:
```python
from src.workers.task_orchestration import get_task_orchestrator
from src.core.db.models import DocumentJob, User

@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, ...)
def parse_document_with_docling(self, document_file_id: str, project_id: str, ...):
    start_time = datetime.utcnow()
    
    try:
        # ... parsing logic ...
        
        # NEW: On success
        try:
            orchestrator = get_task_orchestrator()
            orchestrator.on_task_success(
                task_name="parse_document_with_docling",
                document_file_id=document_file_id,
                project_id=project_id,
                user_id=user_id,
                user_email=user_email,
                document_filename=filename,
                duration_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                result_metrics={"pages": page_count},
            )
        except Exception as handler_error:
            logger.error("[PARSE_TASK] Success handler failed: %s", str(handler_error))
        
        return {"status": "success", ...}
    
    except Exception as e:
        logger.error("[PARSE_TASK] Failed (attempt %d): %s", self.request.retries, str(e))
        
        # NEW: Log failure to error handler
        try:
            db = next(get_db_sync())
            doc_job = db.query(DocumentJob).filter(DocumentJob.id == document_file_id).first()
            user_id = doc_job.user_id if doc_job else "unknown"
            user = db.query(User).filter(User.id == user_id).first()
            user_email = user.email if user else "unknown@example.com"
            
            orchestrator = get_task_orchestrator()
            orchestrator.on_task_failure(
                task_name="parse_document_with_docling",
                document_file_id=document_file_id,
                project_id=project_id,
                user_id=user_id,
                user_email=user_email,
                document_filename=filename,
                error_message=str(e)[:500],
                error_type="parsing_error",
                retry_count=self.request.retries,
                max_retries=self.max_retries,
                db=db,
            )
        except Exception as handler_error:
            logger.error("[PARSE_TASK] Error handler failed: %s", str(handler_error))
        finally:
            if 'db' in locals():
                db.close()
        
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

---

## Import Additions

Add to each task file:

```python
from src.workers.task_orchestration import get_task_orchestrator
from src.core.db.models import DocumentJob, User  # May already be imported
```

---

## Testing Error Handler Integration

1. **Unit Test:** Simulate task failure
   ```bash
   python -m pytest tests/unit/test_error_handler.py -v
   ```

2. **Integration Test:** Actual Celery task with failure
   ```bash
   # Start Celery worker
   celery -A src.app.celery worker --loglevel=info
   
   # Enqueue failing task
   python -c "from src.workers.document_parsing_tasks import parse_document_with_docling; parse_document_with_docling.delay('bad_file_id', 'proj_123')"
   
   # Check database
   SELECT * FROM task_failures WHERE document_file_id = 'bad_file_id';
   SELECT * FROM in_app_notifications WHERE user_id = '...';
   ```

3. **API Test:** Check failure tracking endpoints
   ```bash
   curl http://localhost:8000/api/failure-tracking/project/proj_123/summary
   curl http://localhost:8000/api/failure-tracking/project/proj_123/recent-failures
   curl http://localhost:8000/api/failure-tracking/document/file_123/failures
   ```

---

## Monitoring Post-Implementation

Once wired, monitor:

1. **OpenObserve Logs:** Check ingestion_pipeline stream for error events
2. **Qdrant Status:** Ensure embeddings still storing correctly
3. **Database:** Query task_failures to verify logging
4. **API Response Times:** Failure tracking endpoints should be <100ms

---

## Rollback Plan

If error handlers cause issues:

1. Comment out orchestrator calls in task try/except blocks
2. Celery tasks will continue working without error tracking
3. Revert changes to git if needed
4. Error handling logic is isolated in src/workers/task_orchestration.py

---
