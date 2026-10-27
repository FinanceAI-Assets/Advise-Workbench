# Prompt Versioning Infrastructure Implementation

## Overview
This document outlines the implementation of prompt version tracking in run records, allowing the system to record which prompts and their versions were used on every run.

## Completed Components

### 1. Database Schema ✅
**File**: `src/core/db/models.py`
- Added `prompts_used` field to `Run` model (line 137)
- Stores JSON list: `[{"name": "prompt_name", "version": "1.0"}, ...]`
- Default: None (nullable)

### 2. Prompt Registry Enhancement ✅
**File**: `src/prompts/registry.py`

**New imports**:
- `contextvars` - for thread-safe context variables
- `json` - for serialization

**New context variable**:
- `_prompts_used_context` - tracks prompts used in current run

**New functions**:
- `_record_prompt_used(name, version)` - records a prompt was used
- `get_prompts_used()` - returns list of all prompts used: `[{"name": "...", "version": "..."}, ...]`
- `reset_prompts_used()` - clears tracked prompts (call at run start)

**Modified function**:
- `get_prompt(name)` - now calls `_record_prompt_used()` after loading

### 3. Coordinator Integration (Partial) ✅
**File**: `src/workflows/orchestrator.py`
- Added import: `from src.prompts.registry import get_prompts_used`
- Ready for integration at run completion points

## Remaining Work

### 1. Integration Points
Need to add calls to record prompts in run completion flow:

**In `src/workflows/orchestrator.py`**, at points where run status transitions to "review_ready" or completion:

```python
def _record_prompts_on_run_complete(session: Session, run_id: str) -> None:
    """Record which prompts were used in this run."""
    from src.core.db.models import Run
    
    prompts = get_prompts_used()
    if prompts:
        run = session.query(Run).filter(Run.id == run_id).first()
        if run:
            run.prompts_used = json.dumps(prompts)
            session.commit()
```

**Integration points** (examples):
- After `run.status = "review_ready"` (finalization phase)
- After successful execution before status change
- In error handling paths to capture what was used

### 2. Run Start Initialization
Add to run setup (before execution starts):
```python
reset_prompts_used()  # Clear any previous context
```

### 3. Migration (if needed)
If existing runs in DB need baseline data, create a migration:
- Set `prompts_used = NULL` for all existing runs
- Or backfill with empty JSON array `[]`

### 4. Testing
Create tests to verify:
- Prompts are tracked during execution
- Multiple prompt calls accumulate correctly
- Different versions are recorded
- `prompts_used` field is populated in Run model

## Usage Example

```python
# During run execution
from src.prompts.registry import get_prompts_used

# Prompts are automatically tracked when get_prompt() is called
# At run completion:
prompts = get_prompts_used()
# Result: [{"name": "agent_pptx_fallback", "version": "1"}, {"name": "sheldon_context_reply", "version": "1"}, ...]

# Store in run
run.prompts_used = json.dumps(prompts)
session.commit()
```

## Query Examples

### Get prompts used in a run
```sql
SELECT 
    id,
    status,
    JSON_ARRAY_LENGTH(JSON(prompts_used)) as prompt_count,
    prompts_used
FROM runs
WHERE id = 'run-123'
```

### Find runs that used a specific prompt
```sql
SELECT id, prompts_used
FROM runs
WHERE prompts_used LIKE '%"name": "agent_pptx_fallback"%'
```

### Track prompt version adoption
```sql
SELECT 
    JSON_EXTRACT(p, '$.name') as prompt_name,
    JSON_EXTRACT(p, '$.version') as prompt_version,
    COUNT(*) as usage_count
FROM runs, JSON_EACH(runs.prompts_used) as p
WHERE created_at > datetime('now', '-7 days')
GROUP BY prompt_name, prompt_version
ORDER BY usage_count DESC
```

## Benefits

1. **Auditability**: Know exactly which prompts drove each run
2. **Debugging**: Correlate run quality issues with prompt versions
3. **Migration Tracking**: See adoption rate of new prompt versions
4. **Performance Analysis**: Compare outcomes across prompt versions
5. **Reproducibility**: Recreate a run with the exact same prompts

## Next Steps

1. Add `_record_prompts_on_run_complete()` function to orchestrator
2. Integrate into run completion flow (review_ready or post-execution)
3. Integrate into run start (reset_prompts_used())
4. Create migration for database schema
5. Add unit/integration tests
6. Document in API or admin interface
