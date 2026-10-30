# Review Section: Developer Quick Reference & Guide

**Practical working guide for implementing changes, debugging issues, and optimizing the review workflow**

---

## Quick Start: How Review Section Works

### For Product Managers

The review section is a formal approval gate with:
- **State machine**: Awaiting review → Changes requested ↔ In review → Approved
- **Comment threading**: Reviewers and authors collaborate per-slide
- **Quality gates**: Automatic QA checks block poor-quality submissions
- **Audit trail**: Full decision history for compliance

**Key metric**: Cycle time from "Awaiting review" to "Approved" (typical: 1-3 days)

### For Backend Engineers

Review section has three independent subsystems you need to understand:

1. **Approval Workflow** (`src/app/api/reviews.py`)
   - Stateful FSM with DB-backed persistence
   - Comment lifecycle (Open → Resolved)
   - Timeline audit trail (append-only JSON)

2. **Quality Assessment** (`src/evaluation/pptx_qa.py`, etc.)
   - Post-render QA checks (completeness, design, geometry)
   - LLM-based visual feedback (design review, density analysis)
   - Evidence gate (citation validation)

3. **Storage & Caching**
   - Database: RunEvent (immutable QA results), Review/ReviewComment (state)
   - Filesystem: `workspace/{project_id}/runs/{run_id}/artifacts/`
   - Redis: Optional caching for branding + images

---

## Common Tasks & How-Tos

### Task 1: Add a New QA Check

**Goal**: Detect new quality issue (e.g., inconsistent fonts)

**Steps**:

1. **Identify check type**:
   - Deterministic (geometry, text patterns): Add to `pptx_qa.py`
   - Subjective (design): Add to `visual_qa.py` (LLM-based)

2. **For deterministic check** (geometry example):

   ```python
   # src/evaluation/pptx_qa.py
   
   def check_font_consistency(prs: Presentation) -> list[str]:
       """Detect font consistency issues."""
       issues = []
       fonts_seen = set()
       
       for slide_idx, slide in enumerate(prs.slides):
           for shape in slide.shapes:
               if shape.has_text_frame:
                   for para in shape.text_frame.paragraphs:
                       if para.font.name:
                           fonts_seen.add(para.font.name)
       
       if len(fonts_seen) > 3:
           issues.append(f"Multiple fonts detected: {fonts_seen}")
       
       return issues
   
   # Add to extract_quality_signals():
   def extract_quality_signals(artifact_path: Path, ...):
       ...
       font_issues = check_font_consistency(prs)
       if font_issues:
           qa_report["quality_flags"].extend(font_issues)
       ...
   ```

3. **For subjective check** (LLM-based):

   ```python
   # src/evaluation/visual_qa.py
   
   def evaluate_visual_feedback(artifact_path, qa_report):
       ...
       feedback_list = []
       
       # Template for new feedback type:
       new_feedback = {
           "slide_index": idx,
           "feedback_type": "design_review|evidence_gate|content_quality",
           "severity": "info|warning|error",
           "message": "...",
           "suggested_action": "...",
           "confidence": 0.85
       }
       feedback_list.append(new_feedback)
       ...
   ```

4. **Add to schema**:
   - Update `run_events.payload` comment to document new field
   - Update QA report JSON schema in `src/app/schemas/llm_contracts.py`

5. **Test**:
   ```bash
   pytest tests/unit/evaluation/test_pptx_qa.py -v
   ```

### Task 2: Change Approval Threshold

**Goal**: Lower completeness threshold from 0.80 to 0.75

**Changes**:

```python
# src/evaluation/pptx_qa.py
COMPLETENESS_THRESHOLD = 0.75  # Was 0.80

# Test coverage:
# pytest tests/unit/evaluation/test_thresholds.py
```

**Impact**:
- More decks pass quality gate automatically
- May need to adjust visual feedback prompts to compensate

### Task 3: Fix Comment Count Query (Performance)

**Issue**: `decide()` runs slow on old reviews (many comments)

**Solution**:

```python
# Add denormalized field to Review model
class Review(Base):
    __tablename__ = "reviews"
    ...
    open_comment_count: int = Column(Integer, default=0)

# Update on comment lifecycle
def add_comment(...):
    review.open_comment_count += 1
    db.add(comment)
    db.commit()

def resolve_comment(...):
    review.open_comment_count = max(0, review.open_comment_count - 1)
    comment.status = "Resolved"
    db.commit()

# Use in decide()
def decide(...):
    ...
    if review.open_comment_count > 0:
        raise HTTPException(status_code=409, ...)
    ...

# Alembic migration
# alembic revision --autogenerate -m "Add open_comment_count denormalized field"
```

### Task 4: Implement Review Retention Cleanup

**Goal**: Delete old artifacts per `EngagementMeta.retention_days`

**Implementation**:

```python
# src/jobs/cleanup_artifacts.py

from datetime import datetime, timedelta
from src.core.storage import workspace_path
from src.core.db.models import Run, EngagementMeta

def cleanup_old_artifacts(db: Session):
    """Delete artifacts older than engagement retention_days."""
    
    # Get all engagements with retention policies
    metas = db.query(EngagementMeta).filter(
        EngagementMeta.retention_days.isnot(None)
    ).all()
    
    for meta in metas:
        retention_days = meta.retention_days
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        # Find old runs
        old_runs = db.query(Run).filter(
            Run.project_id == meta.project_id,
            Run.created_at < cutoff_date,
            Run.status == "done"
        ).all()
        
        for run in old_runs:
            artifacts_dir = workspace_path(run.project_id) / "runs" / run.id / "artifacts"
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir)
                logger.info(f"Deleted artifacts for run {run.id}")

# Schedule as cron job or background task
# In src/app/main.py lifespan:
if settings.enable_artifact_cleanup:
    scheduler.schedule_job(
        cleanup_old_artifacts,
        trigger="cron",
        hour=2,  # 2 AM UTC
        minute=0
    )
```

### Task 5: Debug Why Approval Is Blocked

**Scenario**: User sees "Cannot approve" error

**Troubleshooting**:

```python
# Check 1: Review state
SELECT state FROM reviews WHERE id = 'RV-101';
# Expected: "Awaiting review" or "In review"
# Problem states: "Draft", "Approved", "Changes requested"

# Check 2: Open comments
SELECT COUNT(*) FROM review_comments 
WHERE review_id = 'RV-101' AND status = 'Open';
# Expected: 0
# If > 0: User must resolve comments first

# Check 3: User is reviewer
SELECT reviewer_id, owner_id FROM reviews WHERE id = 'RV-101';
# Expected: reviewer_id matches current user
# If not: User is not authorized

# Check 4: Review exists
SELECT * FROM reviews WHERE id = 'RV-101';
# If empty: Review was deleted or ID is wrong

# Example debugging in FastAPI:
@router.post("/{review_id}/decision")
def decide(review_id: str, body: DecisionRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    review = db.scalar(select(Review).where(Review.id == review_id))
    if not review:
        logger.warning(f"Review not found: {review_id}")
        raise HTTPException(status_code=404, detail="Review not found")
    
    if user.id != review.reviewer_id:
        logger.warning(f"User {user.id} not reviewer for {review_id}. Reviewer: {review.reviewer_id}")
        raise HTTPException(status_code=403, detail="Not the assigned reviewer")
    
    if review.state not in {"Awaiting review", "In review"}:
        logger.warning(f"Review {review_id} in state {review.state}, can't decide")
        raise HTTPException(status_code=409, detail=f"Review is {review.state.lower()}")
    
    open_count = db.scalar(
        select(func.count()).select_from(ReviewComment).where(
            ReviewComment.review_id == review_id,
            ReviewComment.status == "Open"
        )
    )
    if open_count > 0:
        logger.warning(f"Review {review_id} has {open_count} open comments")
        raise HTTPException(status_code=409, detail=f"Resolve the {open_count} open comment(s) first")
    
    # Proceed with decision...
```

---

## Data Model Reference

### Core Tables (Review Section)

```sql
-- Main review record
CREATE TABLE reviews (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) FOREIGN KEY,
    run_id VARCHAR(64) FOREIGN KEY,
    title VARCHAR(255),
    artifact_type VARCHAR(32),    -- "pptx" | "docx"
    version_label VARCHAR(16),    -- "v0.1", "v0.2"
    owner_id VARCHAR(64) FOREIGN KEY,      -- Who submitted
    reviewer_id VARCHAR(64) FOREIGN KEY,   -- Who approves
    due_date DATETIME,
    state VARCHAR(32),                    -- FSM state
    payload_json TEXT,                    -- Approval timeline + metadata
    created_at DATETIME,
    updated_at DATETIME
);

CREATE INDEX ix_reviews_project_id ON reviews(project_id);
CREATE INDEX ix_reviews_reviewer_id ON reviews(reviewer_id);
CREATE INDEX ix_reviews_owner_id ON reviews(owner_id);
CREATE INDEX ix_reviews_state ON reviews(state);

-- Comments (thread)
CREATE TABLE review_comments (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    review_id VARCHAR(64) FOREIGN KEY,
    author VARCHAR(255),
    title VARCHAR(255),
    body TEXT,
    anchor VARCHAR(64),         -- Optional: "slide_3"
    status VARCHAR(32),         -- "Open" | "Resolved"
    created_at DATETIME
);

CREATE INDEX ix_review_comments_review_id ON review_comments(review_id);
CREATE INDEX ix_review_comments_status ON review_comments(status);
```

### Related Tables (Quality Assessment)

```sql
-- Run events (quality signals)
CREATE TABLE run_events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(64) FOREIGN KEY,
    event_type VARCHAR(64),     -- "artifact_rendered", "quality_checked"
    payload TEXT,               -- JSON: QA scores, feedback
    created_at DATETIME,
    INDEX ix_run_events_type (run_id, event_type)
);

-- Run tasks (skill output)
CREATE TABLE run_tasks (
    id VARCHAR(64) PRIMARY KEY,
    run_id VARCHAR(64) PRIMARY KEY,
    output_json TEXT,           -- {"pptx_data": {...}} or similar
    PRIMARY KEY (id, run_id)
);
```

---

## API Endpoints Reference

### Review Management

```python
# List reviews visible to user
GET /api/reviews
Response: {
    items: [
        {
            id: "RV-101",
            title: "Q4 Sales Deck",
            engagement: "Acme Corp",
            type: "PPTX v0.1",
            state: "Awaiting review",
            dueDate: "Oct 30",
            ...
        }
    ],
    mine: ["RV-101", ...],  # My action items
    total: 42
}

# Get review detail with comments
GET /api/reviews/{review_id}
Response: {
    id: "RV-101",
    artifactType: "pptx",
    versionLabel: "v0.2",
    state: "Awaiting review",
    comments: [
        {
            id: "1",
            title: "Slide 3: Clarity",
            status: "Open",
            body: "...",
            attribution: "Bob Smith · Oct 30, 2:35 PM"
        }
    ],
    openCount: 1,
    resolvedCount: 0,
    canDecide: true,  // Current user is reviewer
    canRevise: false,
    approvalStatus: "Awaiting review"
}

# Submit artifact for review
POST /api/reviews
Body: {
    projectId: "proj_123",
    runId: "run_abc",
    artifactType: "pptx",
    title: "Q4 Sales Deck",
    reviewerId: "user_bob_id",
    dueDate: "2026-11-01"
}
Response: { id: "RV-101" }

# Add comment
POST /api/reviews/{review_id}/comments
Body: {
    title: "Slide 5: Title",
    body: "This slide needs...",
    anchor: "slide_5"
}
Response: { id: "1" }

# Resolve comment
POST /api/reviews/{review_id}/comments/{comment_id}/resolve
Response: { id: "1", status: "Resolved" }

# Submit decision (approve or request changes)
POST /api/reviews/{review_id}/decision
Body: {
    decision: "approve" | "request_changes",
    note: "..." // Required for request_changes
}
Response: { id: "RV-101", state: "Approved" | "Changes requested" }

# Submit revision (after changes requested)
POST /api/reviews/{review_id}/submit-revision
Body: {
    note: "Updated slide 3 for clarity"
}
Response: {
    id: "RV-101",
    state: "In review",
    versionLabel: "v0.2"
}
```

---

## Testing Guide

### Unit Tests (Fast)

```bash
# Test approval workflow state machine
pytest tests/unit/reviews/test_approval_workflow.py -v

# Test comment threading
pytest tests/unit/reviews/test_comments.py -v

# Test QA checks
pytest tests/unit/evaluation/test_pptx_qa.py -v
pytest tests/unit/evaluation/test_visual_qa.py -v

# Test evidence validation
pytest tests/unit/evaluation/test_evidence_validator.py -v
```

### Integration Tests (Slow, uses DB)

```bash
# Full approval workflow
pytest tests/integration/reviews/test_workflow.py -v

# QA pipeline with real artifacts
pytest tests/integration/evaluation/test_qa_pipeline.py -v

# Database transactions (ACID)
pytest tests/integration/reviews/test_transactions.py -v
```

### Manual Testing

```bash
# Start local server
uvicorn src.app.main:app --reload

# 1. Create a run (via Studio)
# 2. Submit for review
POST http://localhost:8000/api/reviews
{
    "projectId": "test-proj",
    "runId": "run-123",
    "artifactType": "pptx",
    "title": "Test Deck",
    "reviewerId": "bob-id",
    "dueDate": ""
}

# 3. Add a comment
POST http://localhost:8000/api/reviews/RV-101/comments
{
    "title": "Slide 1",
    "body": "Update title slide",
    "anchor": "slide_1"
}

# 4. Resolve comment
POST http://localhost:8000/api/reviews/RV-101/comments/1/resolve

# 5. Approve
POST http://localhost:8000/api/reviews/RV-101/decision
{
    "decision": "approve",
    "note": ""
}

# 6. Verify state
GET http://localhost:8000/api/reviews/RV-101
# Should show state: "Approved"
```

---

## Monitoring & Observability

### Key Metrics to Track

```python
# src/core/observability/metrics.py

# Review lifecycle
review_submitted_total          # Gauge: total reviews in system
review_awaiting_review_count    # Gauge: in "Awaiting review" state
review_approved_total           # Counter: cumulative approvals
review_cycle_time_seconds       # Histogram: "Awaiting review" → "Approved"
review_average_revision_count   # Gauge: avg revisions per review

# Quality assessment
artifact_qa_completeness_score  # Histogram: completeness_score distribution
artifact_qa_design_score        # Histogram: design_score distribution
artifact_quality_flags_total    # Counter: total flags raised
artifact_visual_feedback_generated_total  # Counter: LLM feedback calls

# Comments & collaboration
review_comment_count            # Gauge: total comments per review
review_comment_resolution_time  # Histogram: "Open" → "Resolved"
review_self_approval_rate       # Gauge: % where owner == reviewer

# Errors
review_approval_blocked_total   # Counter: approval blocked (open comments)
review_permission_denied_total  # Counter: access denied
qa_assessment_failed_total      # Counter: LLM feedback failures

# Database
review_table_row_count          # Gauge: total review records
review_comment_table_row_count  # Gauge: total comments
review_event_table_size_bytes   # Gauge: payload_json total size
```

### Health Checks

```bash
# Is review system operational?
GET /health
{
    "status": "ok",
    "checks": {
        "database": "ok",
        "redis": "ok",
        "llm_api": "ok"
    }
}

# Is any review stuck?
SELECT state, COUNT(*) FROM reviews GROUP BY state;
# Expected: small counts, no "Draft" (should be deleted)

# Are comments resolving normally?
SELECT 
    TIMESTAMPDIFF(HOUR, rc.created_at, rc.updated_at) as resolution_hours,
    COUNT(*) as count
FROM review_comments rc
WHERE status = 'Resolved'
GROUP BY resolution_hours
ORDER BY resolution_hours;
# Should show most resolved within 24 hours
```

---

## Performance Tuning

### Slow Query: Comment Count on Approval

**Before**:
```sql
SELECT COUNT(*) FROM review_comments 
WHERE review_id = ? AND status = 'Open'
```
**After**: Use denormalized `Review.open_comment_count` field

### Slow Query: Get All Reviews for User

**Before**:
```sql
SELECT * FROM reviews 
WHERE owner_id = ? OR reviewer_id = ?
ORDER BY created_at DESC
```
**After**: Add separate composite index
```sql
CREATE INDEX ix_reviews_owner_reviewer ON reviews(owner_id, created_at DESC);
CREATE INDEX ix_reviews_reviewer_created ON reviews(reviewer_id, created_at DESC);
```

### High Memory: Visual Feedback Image Generation

**Before**: Generate PNG for all top 12 slides (36 MB)
**After**: Limit to top 3 slides (9 MB) for basic review, cache others

```python
def evaluate_visual_feedback(artifact_path, full_analysis=False):
    max_pages = 12 if full_analysis else 3
    images = _render_pdf_pages_to_png(artifact_path, max_pages=max_pages)
    ...
```

---

## Troubleshooting Guide

### Problem: "Review not found" when it exists

**Possible causes**:
1. Wrong review ID (typo)
2. User doesn't have permission (not owner/reviewer/admin)
3. Review was deleted (soft-delete: `deleted_at` is set)

**Check**:
```sql
SELECT * FROM reviews WHERE id = 'RV-101';
SELECT deleted_at FROM reviews WHERE id = 'RV-101';
```

### Problem: Approval hangs (database deadlock)

**Possible causes**:
1. Concurrent transactions on same review
2. Long-running transaction blocking update

**Check**:
```sql
-- PostgreSQL
SELECT * FROM pg_locks WHERE NOT granted;

-- MySQL
SHOW ENGINE INNODB STATUS;
```

**Fix**: Use optimistic locking (version field)

### Problem: QA scores missing from review

**Possible causes**:
1. Quality assessment failed (LLM timeout)
2. RunEvent not created
3. Frontend not polling for events

**Check**:
```sql
SELECT * FROM run_events 
WHERE run_id = 'run_123' AND event_type = 'artifact_rendered'
ORDER BY created_at DESC;
```

**Fix**: Check logs for LLM error, retry quality assessment

### Problem: Visual feedback shows old design issues after revision

**Possible causes**:
1. Cache not invalidated after artifact update
2. Old feedback JSON still on filesystem

**Check**:
```bash
ls -lt workspace/{project_id}/runs/{run_id}/artifacts/pptx_visual_feedback.json
# Check modification time matches recent revision
```

**Fix**:
```python
# Invalidate feedback on revision
def submit_revision(...):
    ...
    # Delete cached feedback JSON to force regeneration
    feedback_file = workspace_path(...) / "artifacts" / "pptx_visual_feedback.json"
    if feedback_file.exists():
        feedback_file.unlink()
    ...
```

---

## Deployment Checklist

- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Review endpoints enabled (`ENABLE_REVIEWS=true` in env)
- [ ] LLM feedback optional but configured (fallback to no feedback)
- [ ] Redis configured for SSE (optional but recommended)
- [ ] Artifact cleanup job scheduled (if using retention)
- [ ] Monitoring dashboards created (review metrics)
- [ ] Alert thresholds configured (stuck reviews, high error rate)
- [ ] User documentation updated (approval workflow)
- [ ] Admin guide published (managing old reviews)

---

## FAQ

**Q: Can I approve my own artifact?**
A: Yes, if you're assigned as both owner and reviewer. It's recorded as "self-review" in the timeline.

**Q: What happens if I delete an artifact?**
A: Review metadata remains (immutable). QA scores in DB stay available. Can't download artifact anymore.

**Q: How many comments can a review have?**
A: Unlimited, but payload_json grows. Consider archiving timeline after 1000+ comments.

**Q: Can I change the reviewer after submission?**
A: Current system doesn't support this. Create new review with different reviewer instead.

**Q: What's the maximum deck size?**
A: ~50 MB artifact file. QA assessment processes in memory (~300 KB peak). No practical limit.

**Q: How long are artifacts kept?**
A: Configured per engagement (`EngagementMeta.retention_days`). Default: indefinite (no cleanup).

**Q: Can I have multiple reviews per artifact?**
A: No, existing check prevents duplicate: `if existing is not None: raise 409 Conflict`

**Q: What if LLM feedback generation fails?**
A: Fails gracefully (empty feedback list). Approval continues. QA scores still available.

---

## References

- **Code**: `src/app/api/reviews.py`, `src/evaluation/pptx_qa.py`, `src/evaluation/visual_qa.py`
- **Database**: `src/core/db/models.py::Review`, `ReviewComment`
- **Tests**: `tests/unit/reviews/`, `tests/integration/reviews/`
- **Monitoring**: `src/core/observability/metrics.py`
- **Documentation**: Related markdown files in `docs/02-architecture/`

---

**Document Version**: 1.0  
**Last Updated**: 2026-10-30  
**Audience**: Developers, DevOps, QA Engineers
