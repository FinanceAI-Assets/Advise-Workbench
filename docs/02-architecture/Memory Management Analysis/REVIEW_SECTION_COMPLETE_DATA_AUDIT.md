# Review Section: Complete Data Capture & Storage Audit

**Comprehensive mapping of all data captured, storage locations, retention periods, prompts, and LLM interactions in the review section**

---

## Table of Contents

1. [Data Types Captured](#data-types-captured)
2. [Storage Layer Mapping](#storage-layer-mapping)
3. [Retention Periods](#retention-periods)
4. [Prompt Storage & Tracking](#prompt-storage--tracking)
5. [Complete Data Flow by Step](#complete-data-flow-by-step)
6. [Database Schema (Review Section)](#database-schema-review-section)
7. [Filesystem Structure](#filesystem-structure)
8. [Memory Allocation & Lifecycle](#memory-allocation--lifecycle)
9. [LLM Interaction Data](#llm-interaction-data)
10. [Process Data Tracking](#process-data-tracking)
11. [Compliance & Audit Trail](#compliance--audit-trail)

---

## Data Types Captured

### 1. Review Metadata (Core)

**What's Captured**:
```python
Review model (src/core/db/models.py:513)
├── id: String(64)              # PK: "RV-{number}-{uuid}"
├── project_id: String(64)       # FK → Project
├── run_id: String(64)           # FK → Run (artifact source)
├── title: String(255)           # Artifact name
├── artifact_type: String(32)    # "pptx" | "docx" | "pdf" | "xlsx"
├── version_label: String(64)    # "v0.1", "v0.2", etc. (incremented on revision)
├── owner_id: String(64)         # FK → User (who submitted)
├── reviewer_id: String(64)      # FK → User (who approves)
├── due_date: String(32)         # Due date (ISO or formatted)
├── state: String(32)            # FSM state: "Awaiting review", "Changes requested", "In review", "Approved"
├── risk: String(32)             # Risk level or assessment
├── payload_json: Text           # JSON blob (see below)
├── created_at: DateTime         # Review creation timestamp
└── updated_at: DateTime         # Last state change timestamp

Size per record: ~1-5 KB (metadata only)
```

**payload_json Contents**:
```json
{
    "approvalTimeline": [
        {
            "id": "uuid_hex[:8]",
            "title": "State change description",
            "attribution": "Name · Timestamp",
            "icon": "edit|check|comment"
        }
    ],
    "evidenceChecks": [
        {
            "claim": "50% revenue growth",
            "slide": 5,
            "substantiated": true,
            "citation": "Source reference",
            "confidence": 0.95
        }
    ],
    "slide": {
        "preview_data": "...",
        "index": 0
    }
}
```

**Size**: ~5-10 KB per review (grows ~200B per timeline entry)

---

### 2. Comments Thread (ReviewComment)

**What's Captured**:
```python
ReviewComment model (src/core/db/models.py:534)
├── id: Integer              # Auto-increment PK
├── review_id: String(64)    # FK → Review
├── author: String(255)      # Display name of commenter
├── title: String(255)       # Optional: comment label
├── body: Text               # Full comment text
├── anchor: String(64)       # Optional: "slide_3" (location reference)
├── status: String(16)       # "Open" | "Resolved"
├── created_at: DateTime     # Immutable timestamp
└── (no updated_at field)    # Status updated, timestamp remains original

Size per comment: ~200-500 bytes
```

**Typical Comment**:
```json
{
    "id": 1,
    "review_id": "RV-101",
    "author": "Bob Smith",
    "title": "Slide 5: Title clarity",
    "body": "This slide needs a clearer heading. Consider: 'Revenue Drivers Q4 2026'",
    "anchor": "slide_5",
    "status": "Open",
    "created_at": "2026-10-30T14:35:00Z"
}
```

**Growth Pattern**: 
- Average review: 3-5 comments
- Complex review: 15-20 comments
- Total per review: ~1-10 KB

---

### 3. Quality Assessment Data (RunEvent)

**What's Captured**:
```python
RunEvent model (src/core/db/models.py:182)
├── id: Integer              # Auto-increment PK
├── run_id: String(64)       # FK → Run
├── event_type: String(64)   # "artifact_rendered" | "quality_checked" | "visual_feedback_generated"
├── payload: Text            # JSON blob (quality scores, flags, feedback)
├── created_at: DateTime     # Immutable timestamp
└── (no update field)        # Immutable event log

Size per event: ~1-5 KB
```

**artifact_rendered Event**:
```json
{
    "event_type": "artifact_rendered",
    "run_id": "run_abc123",
    "output_type": "pptx",
    "artifact_path": "workspace/proj_123/runs/run_abc123/artifacts/deck_001.pptx",
    "file_size_bytes": 2457600,
    "quality_assessment": {
        "completeness_score": 0.92,
        "design_score": 0.88,
        "structure_score": 0.95,
        "overall_quality": 0.92
    },
    "quality_flags": [
        "missing_speaker_notes_slide_5",
        "text_density_high_slide_3",
        "unsubstantiated_claim_slide_7"
    ],
    "evidence_gate": {
        "passed": true,
        "unsubstantiated_claims": 0
    },
    "geometry_issues": [],
    "created_at": "2026-10-30T14:31:45Z"
}
```

**visual_feedback_generated Event**:
```json
{
    "event_type": "visual_feedback_generated",
    "run_id": "run_abc123",
    "output_type": "pptx",
    "feedback_round": 1,
    "slide_feedbacks": [
        {
            "slide_index": 3,
            "feedback_type": "design_review",
            "severity": "warning",
            "message": "Text density is high (424 chars vs 350 target)",
            "suggested_action": "Move supporting details to speaker notes",
            "confidence": 0.85,
            "addressed": false
        }
    ],
    "revision_needed": false,
    "created_at": "2026-10-30T14:31:50Z"
}
```

---

### 4. Skill Output (RunTask)

**What's Captured**:
```python
RunTask model (src/core/db/models.py:200)
├── id: String(64)           # Task ID: "draft_pptx" | "draft_docx" | "draft_xlsx"
├── run_id: String(64)       # FK → Run (composite PK with id)
├── output_json: Text        # Generated skill output (JSON)
├── status: String(16)       # "completed" | "failed" | "pending"
├── phase: String(16)        # "act" (execution phase)
├── title: Text              # Task name
├── description: Text        # Task description
├── skills_used_json: Text   # ["pptx_generator", "visual_qa", ...]
├── tools_invoked_json: Text # ["memory_lookup", "web_search", ...]
└── started_at: DateTime     # When task started
└── completed_at: DateTime   # When task completed

Size per task: ~50-500 KB (depends on generated content)
```

**PPTX Skill Output**:
```json
{
    "pptx_data": {
        "slides": [
            {
                "title": "Opening",
                "body": "Slide content...",
                "speaker_notes": "Notes for speaker...",
                "layout_type": "title_only|title_content|2_column",
                "elements": [
                    {
                        "type": "bullet_list|text|image|table",
                        "content": "...",
                        "properties": {}
                    }
                ]
            }
        ],
        "metadata": {
            "deck_title": "Q4 Sales Deck",
            "slide_count": 12,
            "audience": "executives"
        }
    }
}
```

**Typical Sizes**:
- Simple deck (5 slides): ~50 KB
- Medium deck (12 slides): ~80 KB
- Complex deck (20 slides): ~150 KB

---

## Storage Layer Mapping

### Layer 1: Database (PostgreSQL/SQLite) - PRIMARY STORAGE

#### Tables for Review Section

| Table | Purpose | Data Stored | Size per Record | Indexes | TTL |
|-------|---------|------------|-----------------|---------|-----|
| `reviews` | Review metadata + approval timeline | Metadata, payload_json | 1-10 KB | project_id, reviewer_id, owner_id, state | Indefinite (soft-delete via archive) |
| `review_comments` | Comment thread | Author, body, status | 200-500 B | review_id, status | Indefinite (immutable log) |
| `run_events` | Quality assessment (immutable log) | QA scores, flags, feedback | 1-5 KB | run_id, event_type | Indefinite (audit trail) |
| `run_tasks` | Skill outputs | Generated pptx_data, docx_data | 50-500 KB | run_id, status, phase | Indefinite (reusable for reruns) |
| `run` | Run metadata | Status, tokens, approval state | 1-2 KB | project_id, created_at | Indefinite |
| `engagement_meta` | Project settings (retention) | retention_days, stage | 500 B | project_id | Indefinite |

**Example Query Patterns**:

```sql
-- Load full review with comments
SELECT r.*, COUNT(DISTINCT c.id) as comment_count
FROM reviews r
LEFT JOIN review_comments c ON c.review_id = r.id
WHERE r.id = 'RV-101'
GROUP BY r.id;

-- Count open comments (approval validation)
SELECT COUNT(*) FROM review_comments
WHERE review_id = 'RV-101' AND status = 'Open';

-- Load QA scores for artifact
SELECT payload FROM run_events
WHERE run_id = 'run_abc123' AND event_type = 'artifact_rendered'
ORDER BY created_at DESC LIMIT 1;

-- Load all visible reviews for user
SELECT r.* FROM reviews r
WHERE r.project_id IN (SELECT project_id FROM memberships WHERE user_id = ?)
   OR r.owner_id = ?
   OR r.reviewer_id = ?
ORDER BY r.created_at DESC;
```

---

### Layer 2: Filesystem - ARTIFACT & DEBUG STORAGE

#### Artifact Artifacts

```
workspace/
└─ {project_id}/
   └─ runs/
      └─ {run_id}/
         ├─ artifacts/
         │  ├─ deck_001.pptx              (2-50 MB, binary OOXML)
         │  ├─ report_001.docx            (1-15 MB, binary OOXML)
         │  ├─ dashboard_001.xlsx         (1-5 MB, binary OOXML)
         │  ├─ output.pdf                 (2-25 MB, binary PDF)
         │  ├─ process_map.svg            (100 KB - 2 MB, vector)
         │  ├─ process_map.pdf            (2-10 MB, rasterized)
         │  ├─ deck.html                  (3-15 MB, self-contained HTML viewer)
         │  ├─ deck.pdf                   (2-25 MB, PDF export)
         │  ├─ handoff_bundle.zip         (20-100 MB, packaged delivery)
         │  ├─ metadata.json              (1-5 KB, artifact inventory)
         │  ├─ qa_report_pptx.json        (2-10 KB, quality assessment)
         │  ├─ qa_report_docx.json        (2-10 KB)
         │  ├─ qa_report_xlsx.json        (1-5 KB)
         │  ├─ pptx_visual_feedback.json  (2-5 KB, design review feedback)
         │  ├─ pptx_render_signals.json   (1-2 KB, pending content signals)
         │  ├─ pptx_integrity.json        (500 B, SHA256 hashes)
         │  ├─ narrative_signals.json     (1-3 KB, coherence assessment)
         │  └─ .manifest                  (500 B, inventory list)
         │
         ├─ workspace_state.json          (1-2 KB, run state snapshot)
         │
         └─ temp/
            ├─ logo.png                   (Auto-deleted after render)
            └─ images/
               └─ page_*.png              (Auto-deleted after visual QA)
```

**Storage Access**:

```python
# From src/core/storage.py
from src.core.storage import workspace_path

# Get artifact path
artifact_dir = workspace_path(project_id) / "runs" / run_id / "artifacts"

# Write artifact
artifact_path = artifact_dir / "deck_001.pptx"
prs.save(str(artifact_path))  # Binary write

# Read artifact
with open(artifact_path, "rb") as f:
    file_bytes = f.read()

# Write quality report (JSON)
qa_report_path = artifact_dir / "qa_report_pptx.json"
qa_report_path.write_text(json.dumps(qa_report), encoding="utf-8")

# Read quality report
with open(qa_report_path) as f:
    qa_report = json.load(f)
```

---

### Layer 3: Redis Cache - OPTIONAL PERFORMANCE LAYER

**Cached Data**:

```python
# From src/deliverables/branding_service.py & elsewhere

# Branding context (project-wide)
cache_key = f"branding:project:{project_id}"
redis.setex(cache_key, 86400, branding_dict)  # 24 hour TTL
# Hit: Saves DB query + color resolution

# Logo image bytes (global)
cache_key = f"logo:url:{hash(logo_url)}"
redis.setex(cache_key, 3600, image_bytes)   # 1 hour TTL
# Hit: Saves HTTP fetch + tempfile creation

# Token usage (per-run)
cache_key = f"run:tokens:{run_id}"
redis.set(cache_key, usage_snapshot)        # Session lifetime
# Hit: Accumulates tokens from concurrent LLM calls

# Visual QA rendered images (optional)
cache_key = f"visual_qa_image:{hash(artifact_path)}:{page_idx}"
redis.setex(cache_key, 604800, image_bytes) # 7 day TTL
# Hit: Skips pypdfium2 render on re-review
```

**Fallback**:
- If Redis unavailable: In-memory dict (single-process only)
- Check: `if redis_available() else memory_cache[key]`

---

### Layer 4: In-Memory (Request Scope) - EPHEMERAL

**Data Held During Request**:

```python
# Request lifecycle for approval decision

def decide(...):
    # Load from DB (request scope)
    review = db.scalar(...)           # ~1 KB in memory
    
    # Query open comments count
    open_count = db.scalar(...)       # ~100 B in memory
    
    # Validate & prepare update
    actor_name = display_name(user)   # ~100 B in memory
    
    # Dict for DB update
    update_dict = {
        "state": "Approved",
        "payload_json": json.dumps(...), # ~1 KB
        "updated_at": utcnow()
    }
    
    # Transaction
    db.commit()                        # All released after commit
    
    # Peak memory: ~5 KB per request
```

**Request Timing**:
```
Request Start (1 KB)
  ├─ Load review (1 KB) → 2 KB total
  ├─ Query comments (100 B) → 2.1 KB
  ├─ Prepare update (1 KB) → 3.1 KB
  ├─ db.commit() (DB write)
  ├─ Build response (1 KB) → 4.1 KB
  └─ Return to client
Request End (GC: all released)
```

---

## Retention Periods

### Data Retention Policy Matrix

| Data Type | DB/Filesystem | Retention | Cleanup Policy | Manual Delete? |
|-----------|---------------|-----------|----------------|-|
| Review record | DB (reviews) | Indefinite | Soft-delete (deleted_at field) | Yes (archive) |
| Review comments | DB (review_comments) | Indefinite | Immutable audit trail | No (keep always) |
| QA scores/flags | DB (run_events) | Indefinite | Immutable audit log | No (keep for audit) |
| Visual feedback | DB (run_events) + FS | Indefinite | Immutable | No |
| Skill output | DB (run_tasks) | Indefinite | Reusable for reruns | No (keep for reuse) |
| Artifact files | FS (workspace/) | **Per project** | Automated cleanup via cron | Yes (optional) |
| QA reports (JSON) | FS (workspace/) | Per artifact | Deleted with artifact | Yes |
| Feedback JSON | FS (workspace/) | Per artifact | Deleted with artifact | Yes |
| Temp images | System tmpdir | Render lifetime | Auto-delete via context manager | No (automatic) |
| Branding cache | Redis | 24 hours | TTL-based expiration | Yes (manual invalidate) |
| Logo cache | Redis | 1 hour | TTL-based expiration | Yes (manual invalidate) |

### Project-Level Retention Configuration

**From EngagementMeta table**:

```python
class EngagementMeta(Base):
    retention_days: int | None = Column(Integer)  # From src/core/db/models.py:93

# Example configurations:
{
    "project_id": "proj_client_001",
    "retention_days": 90,              # Delete artifacts older than 90 days
    "stage": "Approved"
}

{
    "project_id": "proj_internal_tools",
    "retention_days": None,            # Indefinite retention (never delete)
    "stage": "In review"
}
```

### Cleanup Execution

**Scheduled Job** (pseudo-code):

```python
# Runs daily (e.g., 2 AM UTC)
def cleanup_old_artifacts():
    metas = db.query(EngagementMeta).filter(
        EngagementMeta.retention_days.isnot(None)
    ).all()
    
    for meta in metas:
        cutoff_date = datetime.utcnow() - timedelta(days=meta.retention_days)
        
        old_runs = db.query(Run).filter(
            Run.project_id == meta.project_id,
            Run.created_at < cutoff_date,
            Run.status == "done"
        ).all()
        
        for run in old_runs:
            artifacts_dir = workspace_path(run.project_id) / "runs" / run.id / "artifacts"
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir)  # Delete entire artifacts directory
                # DB records (reviews, run_events) kept for audit trail
                logger.info(f"Deleted artifacts for run {run.id}")
```

---

## Prompt Storage & Tracking

### Prompt Registry Architecture

**Location**: `src/prompts/registry.py`

**Storage Model**:

```yaml
# File: config/prompts/{name}.yaml
name: skill_pptx_generator
version: "1.0"
description: "Generate PPTX slide JSON from engagement brief"
system: |
  You are an expert presentation designer...
  [System prompt text, ~3-5 KB]
user: |
  Generate slides for: ${engagement_name}
  Topics: ${topics}
  [User prompt template, ~2-3 KB]
```

**Prompt Registry** (`src/prompts/registry.py`):

```python
@lru_cache(maxsize=256)
def get_prompt(name: str) -> Prompt:
    """Load prompt from config/prompts/{name}.yaml and cache."""
    path = PROMPTS_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    prompt = Prompt(
        name=name,
        version=str(data["version"]),
        description=str(data.get("description") or ""),
        system=str(data.get("system") or ""),
        user=str(data.get("user") or ""),
    )
    _record_prompt_used(prompt.name, prompt.version)  # Track usage
    return prompt
```

### Prompt Usage Tracking

**Context Variable** (`src/prompts/registry.py`):

```python
# Thread-local context variable to track prompts used in current run
_prompts_used_context: contextvars.ContextVar[set[tuple[str, str]]] = contextvars.ContextVar(
    "prompts_used", default=set()
)

def _record_prompt_used(name: str, version: str) -> None:
    """Record that a prompt was used in the current run context."""
    try:
        used = _prompts_used_context.get()
        if not isinstance(used, set):
            used = set()
        used.add((name, version))  # Tuple: (name, version)
        _prompts_used_context.set(used)
    except (LookupError, RuntimeError):
        pass  # Silently skip if context unavailable

def get_prompts_used() -> list[dict[str, str]]:
    """Return all prompts used in current run as [{name, version}, ...]."""
    try:
        used = _prompts_used_context.get()
        if not used:
            return []
        return [{"name": name, "version": version} for name, version in sorted(used)]
    except (LookupError, RuntimeError):
        return []
```

### Prompt Storage in Run Record

**Run Table** (`src/core/db/models.py:136`):

```python
class Run(Base):
    prompts_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON list: [{"name": "skill_pptx_generator", "version": "1.0"}, ...]
```

**Persistence**:

```python
# At run completion (src/workflows/orchestrator.py)
run.prompts_used = json.dumps(get_prompts_used())
db.commit()

# Query to retrieve
SELECT prompts_used FROM runs WHERE id = 'run_abc123';
# Returns: [
#   {"name": "skill_pptx_generator", "version": "1.0"},
#   {"name": "visual_qa_feedback", "version": "1.5"},
#   {"name": "evidence_validator", "version": "2.0"}
# ]
```

### System Prompts for Review Section

**Stored in config/prompts/**:

| Prompt File | Version | Purpose | Size |
|------------|---------|---------|------|
| `skill_pptx_generator.yaml` | 1.0+ | Generate PPTX slide JSON | 4-5 KB |
| `skill_docx_generator.yaml` | 1.0+ | Generate DOCX section JSON | 3-4 KB |
| `skill_xlsx_generator.yaml` | 1.0+ | Generate XLSX sheet JSON | 2-3 KB |
| `visual_qa_feedback.yaml` | 1.5+ | Design review feedback generation | 5-6 KB |
| `evidence_validator.yaml` | 2.0+ | Citation validation | 2-3 KB |
| `narrative_coherence_check.yaml` | 1.0+ | Story flow assessment | 4-5 KB |

---

## Complete Data Flow by Step

### Step 1: Review Submission

```
USER ACTION: "Submit artifact for review"
   │
   ├─ Input: POST /api/reviews
   │  {
   │    projectId: "proj_123",
   │    runId: "run_abc123",
   │    artifactType: "pptx",
   │    title: "Q4 Sales Deck",
   │    reviewerId: "user_bob_id",
   │    dueDate: "2026-11-01"
   │  }
   │
   ├─ CREATED DATA:
   │  ├─ Review record (DB)
   │  │  INSERT INTO reviews (id, project_id, run_id, title, artifact_type, version_label, owner_id, reviewer_id, state, payload_json, created_at, updated_at)
   │  │  VALUES ('RV-101', 'proj_123', 'run_abc123', 'Q4 Sales Deck', 'pptx', 'v0.1', 'user_alice_id', 'user_bob_id', 'Awaiting review', '{"approvalTimeline": [...]}', NOW(), NOW())
   │  │
   │  └─ Timeline entry (in payload_json)
   │     {
   │       "id": "uuid_8char",
   │       "title": "Submitted for review",
   │       "attribution": "Alice Smith · Oct 30, 2026 2:35 PM",
   │       "icon": "edit"
   │     }
   │
   ├─ STORAGE:
   │  └─ DB (reviews table): 1 new row (~1 KB)
   │     ├─ payload_json: Timeline entry (~200 B)
   │     ├─ Indexed on: project_id, reviewer_id, owner_id, state
   │     └─ TTL: Indefinite
   │
   ├─ NOTIFICATION:
   │  ├─ DB (notifications table): 1 insert
   │  │  "RV-101 ready for review · Submitted by Alice Smith"
   │  │
   │  └─ SSE broadcast (if enabled)
   │     {event: "review.submitted", review_id: "RV-101"}
   │
   └─ MEMORY: ~5 KB (request scope) → Released after response
```

---

### Step 2: Quality Assessment (Parallel to Review)

```
TRIGGER: Run completes, artifacts rendered
   │
   ├─ PHASE A: Artifact Extraction (pptx_qa.py)
   │  ├─ Load artifact from disk: workspace/.../artifacts/deck_001.pptx (2-50 MB)
   │  │
   │  ├─ ANALYSIS IN MEMORY:
   │  │  ├─ Presentation object: ~50-100 KB
   │  │  ├─ Extract slides data: ~100-200 KB
   │  │  ├─ QA checks: ~50-100 KB
   │  │  └─ PEAK MEMORY: ~300 KB
   │  │
   │  ├─ COMPUTE QA SCORES:
   │  │  {
   │  │    completeness_score: 0.92,
   │  │    design_score: 0.88,
   │  │    structure_score: 0.95,
   │  │    quality_flags: ["missing_notes_5", "text_dense_3"],
   │  │    evidence_gate: {passed: true}
   │  │  }
   │  │
   │  └─ Release all objects → GC
   │
   ├─ PHASE B: Visual Feedback Generation (visual_qa.py)
   │  ├─ Extract slide metadata (text, density, layout)
   │  │
   │  ├─ Render images (optional)
   │  │  ├─ pypdfium2: PDF → PNG (top 12 pages)
   │  │  ├─ MEMORY ALLOCATION: 36 MB (tempfile context)
   │  │  └─ Used for LLM context
   │  │
   │  ├─ LLM CALL (visual_qa_feedback.yaml)
   │  │  {
   │  │    model: "claude-opus-5-5",
   │  │    system_prompt: get_prompt("visual_qa_feedback").render_system(...),
   │  │    user_prompt: "Analyze deck: {...}",
   │  │    images: [base64_encoded_pngs],
   │  │    temperature: 0.2,
   │  │    max_tokens: 2000,
   │  │    tokens_input: ~10000,
   │  │    tokens_output: ~1000
   │  │  }
   │  │
   │  ├─ LLM RESPONSE:
   │  │  {
   │  │    slide_feedbacks: [
   │  │      {slide_index: 3, feedback_type: "design_review", message: "..."}
   │  │    ],
   │  │    revision_needed: false
   │  │  }
   │  │
   │  └─ Release images, temp files → Auto-cleanup
   │
   ├─ PHASE C: Persist Results (run_events)
   │  ├─ DB INSERT (run_events table)
   │  │  {
   │  │    run_id: "run_abc123",
   │  │    event_type: "artifact_rendered",
   │  │    payload: "{...quality_scores...}",
   │  │    created_at: NOW()
   │  │  }
   │  │
   │  ├─ DB INSERT (2nd event: visual_feedback)
   │  │  {
   │  │    run_id: "run_abc123",
   │  │    event_type: "visual_feedback_generated",
   │  │    payload: "{...feedback_list...}",
   │  │    created_at: NOW()
   │  │  }
   │  │
   │  ├─ FS WRITE (artifacts directory)
   │  │  ├─ qa_report_pptx.json: ~5 KB
   │  │  ├─ pptx_visual_feedback.json: ~3 KB
   │  │  └─ pptx_render_signals.json: ~1 KB
   │  │
   │  └─ TRACK PROMPTS USED
   │     run.prompts_used = [
   │       {"name": "visual_qa_feedback", "version": "1.5"}
   │     ]
   │
   └─ MEMORY: Peak ~36 MB (tempfiles) → Auto-cleanup, then ~300 KB QA data → Persisted
```

---

### Step 3: Review Display & Comments

```
USER ACTION: "View review and add comment"
   │
   ├─ API CALL: GET /api/reviews/RV-101
   │
   ├─ DATABASE QUERIES:
   │  ├─ SELECT * FROM reviews WHERE id = 'RV-101'
   │  │  → Returns: review metadata + payload_json (timeline + evidence)
   │  │
   │  └─ SELECT * FROM review_comments WHERE review_id = 'RV-101' ORDER BY created_at
   │     → Returns: all comments (Open and Resolved)
   │
   ├─ RESPONSE TO FRONTEND:
   │  {
   │    id: "RV-101",
   │    state: "Awaiting review",
   │    approvalTimeline: [
   │      {title: "Submitted for review", attribution: "Alice · Oct 30 2:35 PM", icon: "edit"}
   │    ],
   │    comments: [
   │      {id: 1, author: "Bob", status: "Open", body: "..."}
   │    ],
   │    openCount: 1,
   │    canDecide: true,
   │    qualitySignals: {completeness: 0.92, flags: [...]}
   │  }
   │
   ├─ MEMORY: ~10-20 KB per request (request scope) → Released
   │
   ├─ ADD COMMENT: POST /api/reviews/RV-101/comments
   │  {
   │    title: "Slide 5 clarity",
   │    body: "This slide needs...",
   │    anchor: "slide_5"
   │  }
   │
   ├─ CREATED DATA:
   │  ├─ ReviewComment insert (DB)
   │  │  {
   │  │    id: 2,
   │  │    review_id: 'RV-101',
   │  │    author: 'Bob Smith',
   │  │    title: 'Slide 5 clarity',
   │  │    body: '...',
   │  │    anchor: 'slide_5',
   │  │    status: 'Open',
   │  │    created_at: NOW()
   │  │  }
   │  │
   │  └─ Notification insert
   │     → Alice: "Bob commented on RV-101"
   │
   └─ STORAGE: ~300 B new row (review_comments table)
```

---

### Step 4: Approval Decision

```
USER ACTION: "Approve review" or "Request changes"
   │
   ├─ API CALL: POST /api/reviews/RV-101/decision
   │  {
   │    decision: "approve",
   │    note: ""
   │  }
   │
   ├─ VALIDATION (DB QUERIES):
   │  ├─ Load review: SELECT * FROM reviews WHERE id = 'RV-101'
   │  ├─ Check permissions: Is user the reviewer? ✓
   │  ├─ Check state: Is review in "Awaiting review" state? ✓
   │  └─ Check open comments: SELECT COUNT(*) FROM review_comments WHERE review_id = 'RV-101' AND status = 'Open'
   │     → Result: 0 comments (OK to approve)
   │
   ├─ DECISION LOGIC:
   │  ├─ If approve:
   │  │  ├─ Set review.state = "Approved"
   │  │  ├─ Append timeline entry (payload_json)
   │  │  ├─ Check if all other reviews for project are approved
   │  │  │  └─ If yes: Update project stage = "Approved"
   │  │  └─ Create notification for owner
   │  │
   │  └─ If request_changes:
   │     ├─ Set review.state = "Changes requested"
   │     ├─ Append timeline entry
   │     ├─ Auto-create system ReviewComment (changes requested note)
   │     └─ Create notification for owner
   │
   ├─ DATABASE UPDATES (ATOMIC TRANSACTION):
   │  ├─ UPDATE reviews SET state = 'Approved', payload_json = '{...}', updated_at = NOW()
   │  │  WHERE id = 'RV-101'
   │  │
   │  ├─ UPDATE engagement_meta SET stage = 'Approved' WHERE project_id = 'proj_123'
   │  │  (only if all reviews approved)
   │  │
   │  └─ INSERT INTO notifications (user_id, kind, title, body, link, created_at)
   │     VALUES ('user_alice_id', 'review', 'RV-101 approved', '...', '/reviews/RV-101', NOW())
   │
   ├─ PAYLOAD UPDATES:
   │  {
   │    "approvalTimeline": [
   │      {title: "Submitted for review", ...},
   │      {title: "Approved", attribution: "Bob · Oct 30 3:45 PM", icon: "check"}
   │    ],
   │    "evidenceChecks": [...],
   │    "slide": {...}
   │  }
   │
   ├─ AUDIT TRAIL:
   │  └─ activity_events table: 1 insert
   │     {actor: "Bob Smith", kind: "review", title: "RV-101: Approved", detail: "..."}
   │
   └─ MEMORY: ~5 KB (request scope) → Released
      └─ DURABILITY: All changes persisted atomically via db.commit()
```

---

### Step 5: Revision Workflow

```
USER ACTION: "Submit revision" (after changes requested)
   │
   ├─ PREREQUISITES:
   │  ├─ Review state: "Changes requested" ✓
   │  ├─ All open comments resolved ✓
   │  └─ New artifact version available (user uploaded/regenerated)
   │
   ├─ API CALL: POST /api/reviews/RV-101/submit-revision
   │  {
   │    note: "Updated slide 5 with clarity improvement"
   │  }
   │
   ├─ DATABASE UPDATES (ATOMIC):
   │  ├─ UPDATE reviews
   │  │  SET version_label = 'v0.2',    ← Increment version
   │  │      state = 'In review',       ← Back to reviewable state
   │  │      updated_at = NOW()
   │  │  WHERE id = 'RV-101'
   │  │
   │  ├─ Append to payload_json (timeline):
   │  │  {
   │  │    title: "Revised v0.2 submitted",
   │  │    attribution: "Alice Smith · Oct 30 4:20 PM",
   │  │    icon: "edit"
   │  │  }
   │  │
   │  ├─ INSERT INTO notifications
   │  │  → Bob: "Alice submitted v0.2 for review"
   │  │
   │  └─ UPDATE activity_events
   │     → "Alice submitted RV-101 v0.2"
   │
   ├─ QUALITY RE-ASSESSMENT (Parallel):
   │  ├─ Extract QA for new artifact
   │  ├─ Emit new RunEvent('artifact_rendered')
   │  └─ Generate new visual feedback
   │
   └─ FRONTEND UPDATES:
      ├─ Review.state: "In review" (reviewable again)
      ├─ Review.versionLabel: "v0.2"
      └─ New quality signals displayed
```

---

## Database Schema (Review Section)

### Complete Schema with Relationships

```sql
-- Main review record
CREATE TABLE reviews (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) FOREIGN KEY REFERENCES projects(id),
    run_id VARCHAR(64),                    -- FK to runs.id (nullable)
    title VARCHAR(255) NOT NULL,
    artifact_type VARCHAR(32) NOT NULL,    -- "pptx", "docx", "pdf", "xlsx"
    version_label VARCHAR(64) NOT NULL DEFAULT "",  -- "v0.1", "v0.2"
    owner_id VARCHAR(64) FOREIGN KEY REFERENCES users(id),
    reviewer_id VARCHAR(64) FOREIGN KEY REFERENCES users(id),
    due_date VARCHAR(32) NOT NULL DEFAULT "",
    state VARCHAR(32) NOT NULL DEFAULT "Awaiting review",
    risk VARCHAR(32) NOT NULL DEFAULT "",
    payload_json TEXT NOT NULL DEFAULT "{}",  -- Approval timeline + evidence
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_reviews_project_id (project_id),
    INDEX ix_reviews_reviewer_id (reviewer_id),
    INDEX ix_reviews_owner_id (owner_id),
    INDEX ix_reviews_state (state)
);

-- Comment thread per review
CREATE TABLE review_comments (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    review_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES reviews(id),
    author VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL DEFAULT "",
    body TEXT NOT NULL,
    anchor VARCHAR(64) NOT NULL DEFAULT "",  -- Optional: "slide_3"
    status VARCHAR(16) NOT NULL DEFAULT "Open",  -- "Open" or "Resolved"
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_review_comments_review_id (review_id),
    INDEX ix_review_comments_status (status)
);

-- Quality assessment (immutable event log)
CREATE TABLE run_events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    run_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES runs(id),
    event_type VARCHAR(64) NOT NULL,
    payload TEXT NOT NULL,  -- JSON: QA scores, flags, feedback
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_run_events_run_id (run_id),
    INDEX ix_run_events_type (run_id, event_type)
);

-- Skill output (per task)
CREATE TABLE run_tasks (
    id VARCHAR(64) NOT NULL,
    run_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES runs(id),
    project_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES projects(id),
    output_json TEXT NOT NULL DEFAULT "{}",  -- Skill payload
    status VARCHAR(16) NOT NULL DEFAULT "queued",
    phase VARCHAR(16) NOT NULL DEFAULT "act",
    ...other columns...
    PRIMARY KEY (id, run_id),
    INDEX ix_run_tasks_run_id (run_id),
    INDEX ix_run_tasks_status (status)
);

-- Run metadata (includes tokens, prompts)
CREATE TABLE runs (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES projects(id),
    status VARCHAR(32) NOT NULL,
    tokens_input INTEGER,
    tokens_output INTEGER,
    tokens_cache_read INTEGER,
    tokens_cache_creation INTEGER,
    cost_usd FLOAT,
    prompts_used TEXT,  -- JSON: [{"name": "...", "version": "..."}]
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ...
    INDEX ix_runs_project_created_at (project_id, created_at)
);

-- Project configuration (retention policy)
CREATE TABLE engagement_meta (
    project_id VARCHAR(64) PRIMARY KEY FOREIGN KEY REFERENCES projects(id),
    retention_days INTEGER,  -- Days to keep artifacts
    stage VARCHAR(32),       -- Current approval stage
    ...other columns...
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Notifications
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES users(id),
    kind VARCHAR(16) NOT NULL,  -- "review", "mention"
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL DEFAULT "",
    link VARCHAR(255) NOT NULL DEFAULT "",
    read_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_notifications_user_id (user_id)
);

-- Activity log
CREATE TABLE activity_events (
    id INTEGER PRIMARY KEY AUTO_INCREMENT,
    project_id VARCHAR(64) FOREIGN KEY REFERENCES projects(id),
    actor VARCHAR(255) NOT NULL,
    kind VARCHAR(32) NOT NULL,  -- "review"
    title VARCHAR(255) NOT NULL,
    detail TEXT NOT NULL DEFAULT "",
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_activity_events_project_id (project_id),
    INDEX ix_activity_events_kind (kind),
    INDEX ix_activity_events_created_at (created_at)
);
```

---

## Filesystem Structure

### Artifact Organization

```
workspace/
│
├─ {project_id}/
│  │
│  ├─ runs/
│  │  │
│  │  ├─ {run_id_1}/
│  │  │  │
│  │  │  ├─ artifacts/                          ← Main artifact directory
│  │  │  │  │
│  │  │  │  ├─ MAIN ARTIFACTS:
│  │  │  │  │  ├─ deck_001.pptx                 (2-50 MB, binary)
│  │  │  │  │  ├─ report_001.docx               (1-15 MB, binary)
│  │  │  │  │  ├─ dashboard_001.xlsx            (1-5 MB, binary)
│  │  │  │  │  └─ output.pdf                    (2-25 MB, binary)
│  │  │  │  │
│  │  │  │  ├─ EXPORT FORMATS:
│  │  │  │  │  ├─ deck.html                     (3-15 MB, self-contained)
│  │  │  │  │  ├─ deck.pdf                      (2-25 MB, from soffice)
│  │  │  │  │  ├─ process_map.svg               (100 KB - 2 MB, vector)
│  │  │  │  │  ├─ process_map.pdf               (2-10 MB, rasterized)
│  │  │  │  │  └─ handoff_bundle.zip            (20-100 MB, packaged)
│  │  │  │  │
│  │  │  │  ├─ QUALITY ASSESSMENT (JSON):
│  │  │  │  │  ├─ qa_report_pptx.json           (2-10 KB)
│  │  │  │  │  ├─ qa_report_docx.json           (2-10 KB)
│  │  │  │  │  ├─ qa_report_xlsx.json           (1-5 KB)
│  │  │  │  │  └─ qa_report_pdf.json            (1-5 KB)
│  │  │  │  │
│  │  │  │  ├─ VISUAL FEEDBACK (JSON):
│  │  │  │  │  ├─ pptx_visual_feedback.json     (2-5 KB)
│  │  │  │  │  ├─ docx_visual_feedback.json     (2-5 KB)
│  │  │  │  │  └─ narrative_signals.json        (1-3 KB)
│  │  │  │  │
│  │  │  │  ├─ RENDER SIGNALS (JSON):
│  │  │  │  │  ├─ pptx_render_signals.json      (1-2 KB)
│  │  │  │  │  ├─ pptx_layout_plan.json         (2-5 KB)
│  │  │  │  │  └─ pptx_integrity.json           (500 B, SHA256 hashes)
│  │  │  │  │
│  │  │  │  ├─ METADATA:
│  │  │  │  │  ├─ metadata.json                 (1-5 KB, artifact inventory)
│  │  │  │  │  └─ .manifest                     (500 B, file list)
│  │  │  │  │
│  │  │  │  └─ AUTO-CLEANED:
│  │  │  │     └─ (No files older than retention_days)
│  │  │  │
│  │  │  ├─ workspace_state.json                (1-2 KB, run state)
│  │  │  └─ logs/
│  │  │     └─ run.log                          (execution log)
│  │  │
│  │  ├─ {run_id_2}/
│  │  │  └─ ... (same structure)
│  │  │
│  │  └─ {run_id_N}/
│  │     └─ ... (same structure)
│  │
│  ├─ wiki/
│  │  ├─ pages/
│  │  │  └─ *.md                                (Wiki pages, LLM-maintained)
│  │  └─ indexes/
│  │     └─ *.json                              (Search indexes)
│  │
│  ├─ conversation_state/
│  │  └─ {conversation_id}.json                 (Conversation FSM state)
│  │
│  └─ settings.json                             (Project settings, API keys)
│
└─ leading_practices/
   ├─ wiki/
   │  ├─ pages/                                 (Global leading practices)
   │  └─ indexes/
   └─ .meta/
      └─ wiki_rebuild_events.jsonl              (Graph rebuild queue)
```

### File Write Flow (Example: PPTX Render)

```python
# src/deliverables/pptx/deliverable_pptx.py

def render(self, payload: dict, run_dir: Path, branding: BrandingContext) -> Path:
    """Render PPTX from payload and write to disk."""
    
    # 1. Create presentation in memory
    prs = Presentation()
    
    # 2. Add slides from payload (all in-memory)
    for slide_data in payload["slides"]:
        slide = prs.slides.add_slide(...)
        # ... format slides ...
    
    # 3. Apply branding (in-memory)
    for shape in prs.slides.iter_shapes():
        # ... apply colors, fonts ...
    
    # 4. WRITE TO DISK
    artifact_dir = workspace_path(project_id) / "runs" / run_id / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = artifact_dir / "deck_001.pptx"
    prs.save(str(output_path))  # Binary write: 2-50 MB
    
    # 5. Write metadata JSON
    metadata = {
        "artifact_type": "pptx",
        "file_size_bytes": output_path.stat().st_size,
        "slide_count": len(prs.slides),
        "created_at": utcnow().isoformat()
    }
    (artifact_dir / "metadata.json").write_text(json.dumps(metadata))
    
    return output_path
```

### File Retention Cleanup

```python
# Scheduled job example

def cleanup_old_artifacts():
    """Delete artifacts older than engagement retention_days."""
    
    for project in get_all_projects():
        meta = session.query(EngagementMeta).filter_by(project_id=project.id).first()
        if not meta or not meta.retention_days:
            continue  # No retention policy set
        
        cutoff = datetime.utcnow() - timedelta(days=meta.retention_days)
        old_runs = session.query(Run).filter(
            Run.project_id == project.id,
            Run.created_at < cutoff,
            Run.status == "done"
        ).all()
        
        for run in old_runs:
            artifact_dir = workspace_path(project.id) / "runs" / run.id / "artifacts"
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)  # DELETE: 2-100 MB freed per run
                logger.info(f"Cleaned artifacts for {run.id}")
        
        # Note: DB records (reviews, run_events) NOT deleted
        #       Keeps audit trail for compliance
```

---

## Memory Allocation & Lifecycle

### Peak Memory Usage Scenarios

#### Scenario 1: Simple Approval Decision

```
Timeline:
  t₀: Request start
      └─ Framework: 100 B

  t₁: Load review from DB
      ├─ Review object: 1 KB
      ├─ Framework overhead: 100 B
      └─ Total: ~1.1 KB

  t₂: Query open comments
      ├─ Query result: 100 B
      ├─ Framework: 100 B
      └─ Total: ~1.2 KB

  t₃: Prepare update dict
      ├─ Update payload: 1 KB
      ├─ Review object: 1 KB
      └─ Total: ~2.2 KB

  t₄: db.commit() (database write)
      ├─ All local data flushed to DB
      └─ Memory: 2.2 KB (waiting for response)

  t₅: Build response JSON
      ├─ Response dict: 1 KB
      └─ Total: ~3.2 KB

  t₆: Return to client
      └─ Request ends, GC releases all

PEAK MEMORY: ~3.2 KB (negligible)
```

#### Scenario 2: Quality Assessment with Visual Feedback

```
Timeline:
  t₀: Load artifact from disk
      ├─ Presentation object: 50-100 KB
      └─ Memory: 100 KB

  t₁: Extract QA metadata
      ├─ Text content: 50 KB
      ├─ Scores dict: 1 KB
      ├─ Flags list: 2 KB
      └─ Memory: 153 KB (running total)

  t₂: Render images for LLM
      ├─ pypdfium2.PdfDocument: 100 KB (in-memory PDF parse)
      ├─ PIL.Image × 12 pages: 2 MB (RAM for PIL Images)
      ├─ PNG bytes: ~3 MB (in-memory buffer)
      └─ PEAK MEMORY: ~5.3 MB

  t₃: LLM API call
      ├─ Request sent to Claude API (bytes transferred, not held)
      ├─ Images × 12 still in memory: 3 MB
      └─ Memory: ~5.3 MB (waiting for response)

  t₄: LLM response received
      ├─ Feedback JSON: 5 KB
      ├─ Images released via context manager: -3 MB
      ├─ PDF parse object released: -100 KB
      └─ Memory: ~105 KB

  t₅: Persist results
      ├─ Write RunEvent to DB: 5 KB
      ├─ Write JSON files to FS: ~5 KB
      └─ Memory: ~110 KB

  t₆: Return response
      ├─ Release all objects
      └─ Memory: 0 KB (GC'd)

PEAK MEMORY: ~5.3 MB (images context)
SUSTAINED: ~100 KB (QA data + overhead)
```

---

## LLM Interaction Data

### LLM Calls for Review Section

#### Call 1: Visual Feedback Generation

**Endpoint**: Claude API (claude-opus-5-5)

**Input**:
```python
{
    "model": "claude-opus-5-5",
    "system": get_prompt("visual_qa_feedback").render_system(),
    # System prompt: ~5 KB
    # "You are an expert presentation designer assessing slide quality..."
    
    "messages": [{
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"""Analyze this slide deck for design and content quality.
                
Deck metadata: {metadata_json}
QA scores: completeness={score}, design={score}, structure={score}
Slide structure: {slide_structure_json}

Provide specific feedback for each slide:
1. Design issues (text density, layout, hierarchy)
2. Content clarity (message, relevance)
3. Evidence quality (citations, sources)
"""
                # User prompt: ~3 KB
            },
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64_encoded_page_1  # ~100 KB base64
                }
            },
            # ... 11 more images (~100 KB each) ...
        ]
    }],
    
    "max_tokens": 2000,
    "temperature": 0.2  # Deterministic feedback
}
```

**Output**:
```json
{
    "choices": [{
        "message": {
            "content": "json_response_here"
        }
    }],
    "usage": {
        "prompt_tokens": 10234,     # ~12 KB of tokens
        "completion_tokens": 1045,  # ~1 KB of tokens
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0
    }
}
```

**Stored Data**:
```python
# 1. In RunEvent (DB)
run_events.insert({
    "run_id": "run_abc123",
    "event_type": "visual_feedback_generated",
    "payload": json.dumps({
        "slide_feedbacks": [...],
        "revision_needed": false,
        "model": "claude-opus-5-5",
        "input_tokens": 10234,
        "output_tokens": 1045
    }),
    "created_at": utcnow()
})

# 2. In Run (token tracking)
run.tokens_input += 10234
run.tokens_output += 1045
run.cost_usd += calculate_cost(10234, 1045)

# 3. In Prompts registry
prompts_used.add(("visual_qa_feedback", "1.5"))

# 4. In filesystem (optional)
(artifact_dir / "pptx_visual_feedback.json").write_text(
    json.dumps({"slide_feedbacks": [...], ...})
)
```

---

#### Call 2: Evidence Validation

**Endpoint**: Claude API (claude-opus-5-5)

**Input**:
```python
{
    "model": "claude-opus-5-5",
    "system": get_prompt("evidence_validator").render_system(),
    # System prompt: ~3 KB
    # "You are an evidence validator checking claims against sources..."
    
    "messages": [{
        "role": "user",
        "content": f"""Validate these claims against provided evidence:

Claims:
- "50% revenue growth in Q4" (Slide 5)
- "Top 3 market leader" (Slide 8)
- "$500M total addressable market" (Slide 12)

Evidence (slide context):
Slide 5: "Revenue: Q3=$1M, Q4=$1.5M, Growth=50%"
Slide 8: "Market leaders: CompetitorA 45%, CompetitorB 35%, Us 20%"
Slide 12: "TAM from Gartner Report 2026"

For each claim, determine:
1. Is it substantiated by provided evidence?
2. What is the confidence level (0-1)?
3. Any missing citations?
"""  # User prompt: ~1.5 KB
    }]
}
```

**Output**:
```json
{
    "choices": [{
        "message": {
            "content": "{\n\"claim_validations\": [\n..."
        }
    }],
    "usage": {
        "prompt_tokens": 3500,
        "completion_tokens": 800
    }
}
```

---

### Token Tracking & Cost Calculation

**Location**: `src/llm/run_budget.py`

```python
class _RunTokenUsage:
    """Tracks cumulative token usage per run."""
    
    def charge(self, input_tokens: int, output_tokens: int, 
               cache_read: int = 0, cache_creation: int = 0):
        """Add tokens to run total."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cache_read_tokens += cache_read
        self.cache_creation_tokens += cache_creation
    
    def to_model(self) -> dict:
        """Return as Run model update."""
        return {
            "tokens_input": self.input_tokens,
            "tokens_output": self.output_tokens,
            "tokens_cache_read": self.cache_read_tokens,
            "tokens_cache_creation": self.cache_creation_tokens,
            "cost_usd": self.calculate_cost()
        }

# Pricing (from Claude API docs)
CLAUDE_OPUS_PRICING = {
    "input": 0.015,          # $0.015 per 1K input tokens
    "output": 0.045,         # $0.045 per 1K output tokens
    "cache_read": 0.00375,   # $0.00375 per 1K cached input tokens
    "cache_creation": 0.0375 # $0.0375 per 1K cache creation tokens
}
```

**Persisted to DB**:

```python
# Run record update
run.tokens_input = 10234
run.tokens_output = 1045
run.tokens_cache_read = 0
run.tokens_cache_creation = 0
run.cost_usd = (10234 * 0.015 + 1045 * 0.045) / 1000  # ≈ $0.19

db.commit()

# Query to retrieve
SELECT id, tokens_input, tokens_output, cost_usd FROM runs WHERE id = 'run_abc123';
# Returns: run_abc123 | 10234 | 1045 | 0.19
```

---

## Process Data Tracking

### Run Event Timeline (Event Log)

**Location**: `run_events` table (immutable append-only log)

```sql
-- Complete timeline for one run
SELECT event_type, created_at, payload FROM run_events
WHERE run_id = 'run_abc123'
ORDER BY created_at ASC;

-- Results:
| event_type | created_at | payload |
|--|--|--|
| run_started | 2026-10-30 14:15:00 | {"action": "run_created", "instruction": "..."} |
| plan_generated | 2026-10-30 14:16:00 | {"plan_nodes": [...], "execution_plan": {...}} |
| task_started | 2026-10-30 14:16:05 | {"task_id": "draft_pptx", "status": "running"} |
| task_completed | 2026-10-30 14:19:00 | {"task_id": "draft_pptx", "output_tokens": 4100, "duration_ms": 175000} |
| artifact_rendered | 2026-10-30 14:19:15 | {"output_type": "pptx", "completeness_score": 0.92, "quality_flags": [...]} |
| visual_feedback_generated | 2026-10-30 14:19:45 | {"slide_feedbacks": [...], "model": "claude-opus-5-5"} |
| run_approved | 2026-10-30 14:20:00 | {"approved_by": "user_alice_id", "approval_gates": "passed"} |
| run_completed | 2026-10-30 14:20:05 | {"status": "done", "total_tokens": 15234, "cost_usd": 0.35} |
```

### Prompts Used Tracking

```python
# After each prompt render, tracking via context variable
from src.prompts.registry import _record_prompt_used, get_prompts_used

# During run execution:
prompt = get_prompt("visual_qa_feedback")  # Loads from config/prompts/visual_qa_feedback.yaml
prompt.render_system(...)                 # Calls _record_prompt_used("visual_qa_feedback", "1.5")

# At run completion:
run.prompts_used = json.dumps(get_prompts_used())
# Result: [
#   {"name": "visual_qa_feedback", "version": "1.5"},
#   {"name": "evidence_validator", "version": "2.0"},
#   {"name": "narrative_coherence_check", "version": "1.0"}
# ]
```

---

## Compliance & Audit Trail

### Audit Requirements Met

| Requirement | Implementation | Storage |
|--|--|--|
| Full decision history | Approval timeline in payload_json | reviews table |
| Immutable event log | RunEvent append-only (no updates) | run_events table |
| Comment preservation | ReviewComment never deleted | review_comments table |
| Token accountability | Tracked in run record | runs table (tokens_*) |
| Prompt usage | Tracked in prompts_used field | runs table |
| Timestamp immutability | created_at never updated | All tables |
| Actor attribution | author/created_by on all mutations | reviews, review_comments, activity_events |
| Evidence preservation | payload_json stores evidence checks | reviews table |
| Activity log | All key actions logged | activity_events table |

### Soft Delete Pattern

```python
# For compliance retention, use soft-delete instead of hard-delete
class Review(Base):
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

# When archiving a review:
review.deleted_at = utcnow()
db.commit()

# When querying (automatic filter):
SELECT * FROM reviews
WHERE project_id = ? AND deleted_at IS NULL
ORDER BY created_at DESC;

# For audit (show all, including deleted):
SELECT * FROM reviews
WHERE project_id = ?
ORDER BY created_at DESC;  # No WHERE filter
```

---

## Summary Tables

### Data Capture Checklist

```
✓ Review metadata (id, state, version, participants)
✓ Approval timeline (state changes, timestamps, actors)
✓ Comments thread (author, body, anchor, status)
✓ QA scores (completeness, design, structure)
✓ Quality flags (specific issues detected)
✓ Evidence validation (claims, citations, confidence)
✓ Visual feedback (design review, slide-by-slide)
✓ Skill outputs (pptx_data, docx_data, xlsx_data)
✓ Artifact files (binary PPTX/DOCX/XLSX)
✓ Prompts used (name, version tracking)
✓ Token usage (input, output, cache)
✓ Cost calculation (USD)
✓ Activity audit (all user actions)
✓ Notifications (approval alerts)
✓ Branding context (colors, fonts, logo)
```

### Storage Summary

| Storage Medium | Data Type | Estimated Size | TTL | Accessed By |
|--|--|--|--|--|
| **Database (runs)** | Approval timeline | 5-10 KB | Indefinite | API, audit |
| **Database (reviews)** | QA scores, flags | 1-5 KB | Indefinite | API, frontend |
| **Database (run_events)** | Feedback details | 2-5 KB | Indefinite | API, analytics |
| **Database (run_tasks)** | Skill outputs | 50-500 KB | Indefinite | Rerun, API |
| **Database (prompts_used)** | Prompt tracking | ~500 B | Indefinite | Audit |
| **Filesystem** | PPTX/DOCX/XLSX | 2-50 MB | Per project | Download API |
| **Filesystem** | QA/feedback JSON | 2-10 KB | Per artifact | Debug |
| **Filesystem** | Process maps | 100 KB-2 MB | Per project | Download |
| **Filesystem** | Handoff bundle | 20-100 MB | Per project | Delivery |
| **Redis** | Branding cache | ~1 KB | 24 hours | Performance |
| **Redis** | Images cache | 100-200 KB | 7 days | Visual QA |
| **Temp files** | Rendered images | ~3 MB | Request scope | LLM input |

---

## Conclusion

The review section implements a **comprehensive data capture and storage system** with:

1. **Multi-layer persistence**: Database (primary), filesystem (artifacts), Redis (cache)
2. **Immutable audit trail**: Append-only event logs for compliance
3. **Complete process tracking**: Prompts, tokens, decisions, comments
4. **Flexible retention**: Per-project policies with soft-delete
5. **LLM transparency**: Full token accounting and prompt versioning
6. **Memory efficiency**: Ephemeral request-scope data, persistent DB-backed state

All data is **capture-at-source**, **persisted immediately**, and **retained indefinitely** for audit compliance, with optional artifact cleanup per retention policies.

---

**Document Version**: 1.0  
**Last Updated**: 2026-10-30  
**Scope**: Review section complete data audit  
**Audience**: Architects, compliance, DevOps
