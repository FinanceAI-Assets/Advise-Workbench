# Visual QA Error Analysis - Complete Root Cause & Fix Guide

**Date**: 2026-11-04  
**Status**: Deep analysis complete - Ready for implementation  
**Priority**: CRITICAL - Blocks Phase 5 implementation

---

## 🚨 Problem Statement

**What's happening**: When Visual QA evaluation encounters a Claude API circuit breaker error (rate limiting), the actual error message is lost and replaced with a generic "PPTX visual critic call failed" message. This causes the Investigator agent to misclassify the error, and the View Artifacts button shows even when evaluation fails.

**Expected behavior**: 
1. Actual error messages (circuit breaker, rate limit) should be captured and stored
2. Investigator should see real errors and classify them as `external_service_error`
3. View Artifacts button should only show when evaluation passes successfully

---

## 🔍 Error Flow Analysis

### Current (Broken) Flow:

```
Claude API Circuit Breaker Error
        ↓
visual_qa.py line 294: claude_generate_json() raises RateLimitError
        ↓
visual_qa.py line 301-303: Exception caught but GENERIC MESSAGE returned
        ↓
orchestrator.py line 2310: Generic message stored in RunEvent
        ↓
orchestrator.py line 2665-2696: Investigator reads RunEvent
        ↓
investigator_agent.py line 71: Sees generic message, not actual circuit breaker
        ↓
investigator_agent.py line 202-207: Claude tries to classify generic message
        ↓
RESULT: Misclassified as "llm_problem" instead of "external_service_error"
```

---

## 📋 Files That Need Changes

### 1. **src/evaluation/visual_qa.py** (2 critical issues)

**Issue 1A: Line 245-246 - Generic error in pixel path**
```python
except Exception as exc:
    degraded_reason = f"pixel vision pass failed: {exc}"  # GOOD - captures actual error
```
✅ This one actually captures the error in `degraded_reason`. However, it falls through instead of returning.

**Issue 1B: Line 301-303 - CRITICAL: Generic error in metadata path**
```python
except Exception:
    # Fail-open: visual critic issues should not block pipeline progression.
    return {**_empty, "summary": "PPTX visual critic call failed; continuing without critic output"}
```
❌ **THIS IS THE PROBLEM**: Actual error (circuit breaker, rate limit) is lost. Returns generic message.

**Fix needed:**
- Capture actual exception message
- Store full error details in dict payload
- Include error type (RateLimitError, etc.)
- Add timestamp of error

**Code location**: Lines 292-303

---

### 2. **src/workflows/orchestrator.py** (2 issues)

**Issue 2A: Line 2263-2266 - Thread exception handling**
```python
except Exception as qa_error:
    print(f"[PHASE-EVALUATE] 1a. Visual QA error: {qa_error}")
    visual_qa_result["report"] = {"status": "error", "summary": f"Visual QA error: {qa_error}"}
```
✅ This captures the error IF an exception is raised in the thread. But visual_qa.py catches exceptions internally, so this doesn't help.

**Issue 2B: Line 2310 - Event storage (depends on visual_qa.py fix)**
```python
append_run_event(session, run_id, "visual_qa_report", visual_qa_report)
```
This stores whatever visual_qa.py returns. Once visual_qa.py captures real errors, this will store them.

**Fix needed**: 
- Once visual_qa.py returns proper error details, ensure they're stored in RunEvent payload
- Add detailed logging of what's being stored in RunEvent

**Code location**: Lines 2310

---

### 3. **src/agents/investigator_agent.py** (1 critical issue)

**Issue 3: Lines 68-86 - Error message classification**

The agent reads error messages from RunEvent but doesn't recognize API circuit breaker errors as external service errors.

**Current logic:**
```python
for i, attempt in enumerate(attempts):
    try:
        error = attempt.get("error") or attempt.get("message", "Unknown")
        # ... stores in attempt_summaries ...
```

The agent then tries to classify using keyword matching (line 90-99), but:
- "PPTX visual critic call failed" doesn't contain keywords like "circuit", "rate", "anthropic", "api"
- Generic message gets misclassified

**Fix needed:**
- Add special handling for "PPTX visual critic call failed" errors
- Extract actual error details from the dict structure
- Classify as `external_service_error` when error payload contains API-related errors
- Add new root cause category: `external_service_error` (6th category)

**Code location**: Lines 68-86, 173-182 (root_causes dict)

---

### 4. **frontend/components/conversation/RunProgressCard.tsx** (1 issue)

**Issue 4: Line 72 - View Artifacts button visibility**

```typescript
{showArtifactsLink && (run.finished || run.active || stoppedWithFiles) ? (
```

Current condition:
- Shows button if `run.finished` OR `run.active` OR `stoppedWithFiles`
- `stoppedWithFiles` = `run.failed && run.outputs.length > 0`

**Problem**: Button shows even when evaluation failed (because outputs were generated in Phase 3, but Phase 4 evaluation failed)

**Fix needed:**
- Add condition to check if evaluation passed
- Need to expose `evaluation_passed` flag from Run model
- Only show button if `evaluation_passed === true`

**Code location**: Line 72

---

## 🔧 Implementation Plan

### Step 1: Fix visual_qa.py (CRITICAL)

**File**: `src/evaluation/visual_qa.py`

**Change at lines 292-303**:

Replace:
```python
try:
    critic_model = str(getattr(settings, "pptx_visual_critic_model", "") or "").strip() or critique_model()
    result = claude_generate_json(
        system=system,
        user=user,
        model=critic_model,
        temperature=0.1,
        max_tokens=1400,
    )
except Exception:
    # Fail-open: visual critic issues should not block pipeline progression.
    return {**_empty, "summary": "PPTX visual critic call failed; continuing without critic output"}
```

With:
```python
try:
    critic_model = str(getattr(settings, "pptx_visual_critic_model", "") or "").strip() or critique_model()
    result = claude_generate_json(
        system=system,
        user=user,
        model=critic_model,
        temperature=0.1,
        max_tokens=1400,
    )
except Exception as e:
    import traceback
    error_type = type(e).__name__
    error_msg = str(e)
    error_trace = traceback.format_exc()
    
    # Fail-open: visual critic issues should not block pipeline progression.
    return {
        **_empty, 
        "summary": "PPTX visual critic call failed; continuing without critic output",
        "error_details": {
            "error_type": error_type,
            "error_message": error_msg,
            "full_trace": error_trace[:500],  # First 500 chars of traceback
        }
    }
```

**Why**: 
- Captures actual error type (RateLimitError, APIConnectionError, etc.)
- Preserves error message so investigator can see real issue
- Stores traceback for debugging

---

### Step 2: Update Investigator Agent

**File**: `src/agents/investigator_agent.py`

**Change 2A: Add external_service_error category (lines 144-150)**

Replace:
```python
root_causes = {
    "data_problem": "Data Problem",
    "approach_problem": "Approach Problem",
    "requirements_problem": "Requirements Problem",
    "technical_problem": "Technical Problem",
    "llm_problem": "LLM Problem",
}
```

With:
```python
root_causes = {
    "data_problem": "Data Problem",
    "approach_problem": "Approach Problem",
    "requirements_problem": "Requirements Problem",
    "technical_problem": "Technical Problem",
    "llm_problem": "LLM Problem",
    "external_service_error": "External Service Error",
}
```

**Why**: Add new category for API circuit breaker and rate limit errors

---

**Change 2B: Update error extraction (lines 68-86)**

Replace error extraction logic with:
```python
for i, attempt in enumerate(attempts):
    try:
        # First check if error_details exists (from visual_qa.py)
        error_details = attempt.get("error_details", {})
        if error_details:
            error_type = error_details.get("error_type", "Unknown")
            error_msg = error_details.get("error_message", "Unknown")
            error = f"{error_type}: {error_msg}"
        else:
            error = attempt.get("error") or attempt.get("message", "Unknown")
        
        stage = attempt.get("stage", "unknown")
        artifact = attempt.get("artifact", "unknown")

        attempt_summaries.append(
            {
                "attempt": i + 1,
                "error": str(error)[:200],
                "stage": stage,
                "artifact": artifact,
                "error_details": error_details,  # Pass details forward
            }
        )
        error_messages.append(str(error).lower())
        error_stages.append(stage)
    except Exception as e:
        _LOG.warning(f"[INVESTIGATOR-NODE] Could not parse attempt {i}: {e}")
        attempt_summaries.append({"attempt": i + 1, "error": "Parse failed"})
```

**Why**: Extracts actual error type and message from error_details dict that visual_qa.py provides

---

**Change 2C: Update classification prompt (lines 173-199)**

Update system_prompt to include external_service_error detection:
```python
system_prompt = """You are a root cause classification expert. Analyze generation failures.

Classify into EXACTLY ONE category:
- data_problem: Missing/incomplete/conflicting data
- approach_problem: Wrong strategy/methodology
- requirements_problem: Unclear/ambiguous specifications
- technical_problem: Tool limitation, unsupported format
- llm_problem: Model understanding failure, hallucination, logic error
- external_service_error: API rate limit, circuit breaker, service unavailable

SPECIAL RULE: If you see "RateLimitError", "circuit breaker", "anthropic", or "rate limit" 
in the error messages, classify as "external_service_error" with high confidence.

Return JSON: {"root_cause": "category", "confidence": 0.0-1.0, "reasoning": "..."}"""
```

**Why**: Explicitly tells Claude to detect API errors and classify as external_service_error

---

### Step 3: Update Database Model

**File**: `src/core/db/models.py`

Check if Run model has `evaluation_passed` field. If not, add:

```python
class Run(Base):
    # ... existing fields ...
    evaluation_passed: Mapped[bool] = mapped_column(Boolean, default=False)
```

**Code location**: Check around line where Run model is defined

**Why**: Need to track whether evaluation passed to control UI button visibility

---

### Step 4: Update Orchestrator to Set evaluation_passed Flag

**File**: `src/workflows/orchestrator.py`

**Location**: Around line 2420-2430 where evaluation status is checked

Add:
```python
# After determining evaluation results
if evaluator_pipeline["status"] == "pass":
    run.evaluation_passed = True
else:
    run.evaluation_passed = False

session.commit()
```

**Why**: Persist evaluation result to database so frontend can check it

---

### Step 5: Update Frontend Button Visibility

**File**: `frontend/components/conversation/RunProgressCard.tsx`

**Location**: Line 72

Update the condition to check evaluation_passed:

```typescript
{showArtifactsLink && (run.finished || run.active || stoppedWithFiles) && (run.finished ? run.evaluation_passed : true) ? (
```

Or more clearly:
```typescript
{showArtifactsLink && ((run.active || stoppedWithFiles) || (run.finished && run.evaluation_passed)) ? (
```

This means:
- Show for active runs (still generating)
- Show for stopped-with-files (user might want to check partial outputs)
- Show for finished runs ONLY if evaluation_passed is true

**Why**: Prevents showing button when evaluation failed

---

## 📊 Expected Result After Fixes

### Error Flow (Fixed):

```
Claude API Circuit Breaker Error
        ↓
visual_qa.py line 294: claude_generate_json() raises RateLimitError
        ↓
visual_qa.py line 301-303: Exception caught, ACTUAL ERROR CAPTURED
        ↓
Returns: {
    "summary": "PPTX visual critic call failed",
    "error_details": {
        "error_type": "RateLimitError",
        "error_message": "Rate limit exceeded",
        ...
    }
}
        ↓
orchestrator.py line 2310: Full details stored in RunEvent
        ↓
orchestrator.py line 2665-2696: Investigator reads RunEvent
        ↓
investigator_agent.py line 71-75: Extracts "RateLimitError: Rate limit exceeded"
        ↓
investigator_agent.py line 202-207: Claude sees real error in classification prompt
        ↓
RESULT: Correctly classified as "external_service_error" with high confidence
```

---

## 🧪 Testing Strategy

### Before Implementation:
1. Verify current behavior in logs - see generic "PPTX visual critic call failed"
2. Check that View Artifacts button shows even on failed evaluations

### After Implementation:
1. Trigger a Visual QA that hits circuit breaker
2. Watch logs for:
   - Actual error type (RateLimitError, APIConnectionError, etc.)
   - Error details in RunEvent
   - Investigator correctly classifying as external_service_error
3. Verify View Artifacts button only shows when evaluation passes

---

## 🔍 Key Code Sections (Quick Reference)

| File | Line | Issue | Fix Type |
|------|------|-------|----------|
| visual_qa.py | 301-303 | Generic error returned | Capture exception details |
| investigator_agent.py | 144-150 | Missing external_service_error | Add new root_cause category |
| investigator_agent.py | 68-86 | Generic error extraction | Extract error_details dict |
| investigator_agent.py | 173-182 | Classification doesn't detect API errors | Update prompt with rule |
| models.py | TBD | Missing evaluation_passed flag | Add field to Run model |
| orchestrator.py | 2420-2430 | Flag not set | Set evaluation_passed on run |
| RunProgressCard.tsx | 72 | Button shows on failed eval | Check evaluation_passed flag |

---

## ✅ Verification Checklist

- [ ] visual_qa.py captures actual error type and message
- [ ] orchestrator.py logs show error_details in RunEvent
- [ ] investigator_agent.py has external_service_error category
- [ ] investigator_agent.py correctly extracts error_details
- [ ] investigator classification prompt includes API error rule
- [ ] Run model has evaluation_passed field
- [ ] orchestrator.py sets evaluation_passed flag
- [ ] RunProgressCard checks evaluation_passed for button visibility
- [ ] Test with real circuit breaker error
- [ ] Investigator correctly classifies API errors
- [ ] View Artifacts button only shows on successful evaluation

---

## 💡 Why These Issues Exist

1. **Generic error in visual_qa.py**: Fail-open design (don't block pipeline) combined with generic exception handler
2. **Missing external_service_error**: Agent was only designed for content/data/approach problems, not infrastructure
3. **Button visibility**: UI logic only checked status, not evaluation_passed flag (didn't exist)
4. **No error_details flow**: Error details lost at multiple points in the pipeline

---

## 🚀 Next Steps

1. Implement changes in order (Steps 1-5)
2. Test with actual circuit breaker trigger
3. Verify logs show correct error flow
4. Once working, proceed to Phase 5 implementation

