# Phase 4 Debugging Guide - Quality Evaluation & Investigator Agent

**Last Updated**: 2026-11-03  
**Status**: Complete with enhanced logging

---

## 🎯 Quick Summary

Phase 4 has 2 main outcomes:

1. **✅ PASS**: All quality checks passed → Move to Phase 5 (Review)
2. **❌ FAIL**: Quality checks failed → Auto-retry (max 3 times) → If retries exhausted → Investigator Agent
3. **🚨 ESCALATE**: Technical issue → Mark as escalated_for_review

This guide shows you how to verify each step is working.

---

## 📋 What Phase 4 Does

```
┌─ Quality Evaluation Starts
│
├─ Visual QA Check (with timeout protection)
├─ QA Report Analysis  
├─ Guardrails Check
├─ Evidence Gate Check
│
├─ IF PASS:
│  └─ ✅ All done → Move to next phase
│
└─ IF FAIL:
   ├─ Current retry count < 3?
   │  └─ ✅ YES: Re-queue for Phase 3 with feedback
   │
   └─ Current retry count >= 3?
      └─ ✅ YES: Trigger Investigator Agent
         ├─ Node 1: Analyze failed attempts
         ├─ Node 2: Classify root cause
         ├─ Node 3: Generate chat message
         ├─ Node 4: Make routing decision
         │
         └─ Route to:
            ├─ Phase 2 (data/approach/requirements issues)
            ├─ Phase 3 (LLM problem + guidance)
            └─ Escalate (technical issues)
```

---

## 🔍 How to Check Phase 4 - Step by Step

### Step 1: Watch Logs in Real-Time (WHILE TESTING)

Run this command BEFORE testing in Sheldon:

```bash
# Watch Phase 4 logs in real-time
tail -f logs/app.log | grep -E "\[PHASE-EVALUATE\]|\[INVESTIGATOR"

# Alternative: More verbose (includes all node output)
tail -f logs/app.log | grep -E "\[PHASE-|NODE\]"
```

What you should see:

```
✅ [PHASE-EVALUATE] STARTED for run_id=run_abc123
✅ [PHASE-EVALUATE] 1. Running visual QA checks...
✅ [PHASE-EVALUATE] 1a. Visual QA completed successfully
✅ [PHASE-EVALUATE] 📊 EVALUATION RESULTS:
   Status: fail  (or pass)
   Visual QA Passed: False (or True)
```

---

### Step 2: Test Happy Path (Should PASS)

In Sheldon UI, run a simple request:

```
Generate a basic presentation with simple data that matches current context
```

**Expected logs:**

```
[PHASE-EVALUATE] 📊 EVALUATION RESULTS:
   Status: pass
   Visual QA Passed: True
   QA Passed: True
   Guardrails Passed: True
✅ [PHASE-EVALUATE] EVALUATION PASSED!
   All quality checks passed
   Moving to next phase (REMEMBER/REVIEW)...
```

**Result**: Run shows `review_ready` status in Sheldon UI

---

### Step 3: Test Retry Path (Retries < 3)

In Sheldon UI, run a request with slightly invalid data:

```
Generate presentation with metrics that don't exist in the data
```

**Expected logs (first run):**

```
[PHASE-EVALUATE] 📊 EVALUATION RESULTS:
   Status: fail
   Visual QA Passed: False
[PHASE-EVALUATE] ⚠️ EVALUATION FAILED - Current retry count: 0/3
[PHASE-EVALUATE] 🔄 RETRY PATH: Attempt 1/3
   Re-queuing run for Phase 3 generation with feedback...
   Failed checks: visual_qa=True, qa=False, guardrails=False
```

**Then it will re-run Phase 3 with feedback hints**

Continue with Step 4 after 2-3 retries...

---

### Step 4: Test Investigator Agent Path (Retries >= 3)

Keep testing the same request from Step 3 until retries are exhausted.

**Expected logs when Investigator triggers:**

```
════════════════════════════════════════════════════════════════════════════════
[PHASE-EVALUATE] 🔴 RETRIES EXHAUSTED (3/3)
[PHASE-EVALUATE] ⏳ Initiating Investigator Agent Analysis...
════════════════════════════════════════════════════════════════════════════════

[INVESTIGATOR] ✅ Investigator instance created
[INVESTIGATOR] 📋 Found 3 retry events
[INVESTIGATOR]   Attempt 1: Missing metric in chart...
[INVESTIGATOR]   Attempt 2: Chart still incomplete...
[INVESTIGATOR]   Attempt 3: Data validation failed...
[INVESTIGATOR] 🔍 Starting analysis pipeline...
```

Then watch for the 4 nodes:

```
────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 🔍 NODE 1: ANALYZE FAILURES
[INVESTIGATOR-NODE] Input: 3 failed attempts
[INVESTIGATOR-NODE]   Patterns found: 2
[INVESTIGATOR-NODE]   Error evolution: SAME stage fails every attempt: gen
[INVESTIGATOR-NODE] ✅ NODE 1 COMPLETE

────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 🎯 NODE 2: CLASSIFY ROOT CAUSE
[INVESTIGATOR-NODE] Input: 3 attempts analyzed
[INVESTIGATOR-NODE]   Root Cause: data_problem
[INVESTIGATOR-NODE]   Confidence: 95.0%
[INVESTIGATOR-NODE]   Reasoning: The metrics requested are not available in the current data...
[INVESTIGATOR-NODE] ✅ NODE 2 COMPLETE

────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 💬 NODE 3: GENERATE CHAT EXPLANATION
[INVESTIGATOR-NODE] Input: data_problem at confidence 95.0%
[INVESTIGATOR-NODE]   Message length: 547 chars
[INVESTIGATOR-NODE] ✅ NODE 3 COMPLETE

────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 🚦 NODE 4: MAKE ROUTING DECISION
[INVESTIGATOR-NODE] Input: data_problem
[INVESTIGATOR-NODE]   Route: phase_2
[INVESTIGATOR-NODE]   Reason: Data/context issue needs clarification
[INVESTIGATOR-NODE]   Message: Let's clarify the data before retrying...
[INVESTIGATOR-NODE] ✅ NODE 4 COMPLETE
════════════════════════════════════════════════════════════════════════════════

────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR] 📊 ANALYSIS COMPLETE:
[INVESTIGATOR]   Root Cause: data_problem
[INVESTIGATOR]   Confidence: 95.0%
[INVESTIGATOR]   Routing to: phase_2
[INVESTIGATOR]   Chat message length: 547
────────────────────────────────────────────────────────────────────────────────

[INVESTIGATOR] ↩️ ROUTING DECISION: PHASE 2 (Clarification Needed)
[INVESTIGATOR]   Message: Let's clarify the data before retrying...
[INVESTIGATOR] ✅ Run status set to 'awaiting_clarification'
[INVESTIGATOR] ✅ Event recorded: investigator_routed_to_phase2

════════════════════════════════════════════════════════════════════════════════
[INVESTIGATOR] ✅ INVESTIGATION PIPELINE COMPLETE
[INVESTIGATOR]   Status: awaiting_clarification
[INVESTIGATOR]   Chat message persisted: YES
════════════════════════════════════════════════════════════════════════════════
```

---

## 🔍 How to Check Specific Scenarios

### Scenario A: Was Phase 4 Entered?

```bash
grep "\[PHASE-EVALUATE\] STARTED" logs/app.log | tail -5
```

Expected:
```
[PHASE-EVALUATE] STARTED for run_id=run_abc123
```

If NOT there: Phase 4 wasn't reached. Check Phase 3 logs.

---

### Scenario B: Did Quality Check PASS or FAIL?

```bash
grep "\[PHASE-EVALUATE\] 📊 EVALUATION RESULTS" logs/app.log | tail -1
```

Expected:
```
[PHASE-EVALUATE] 📊 EVALUATION RESULTS:
   Status: pass (or fail)
   Visual QA Passed: True/False
   QA Passed: True/False
   Guardrails Passed: True/False
   Evidence Passed: True/False
```

---

### Scenario C: Did it Retry or Call Investigator?

```bash
# If retrying:
grep "RETRY PATH: Attempt" logs/app.log | tail -3

# If calling investigator:
grep "RETRIES EXHAUSTED" logs/app.log | tail -1
```

---

### Scenario D: What Root Cause Was Detected?

```bash
grep "Root Cause:" logs/app.log | tail -1
```

Expected:
```
[INVESTIGATOR]   Root Cause: data_problem
```

Or:
```
[INVESTIGATOR]   Root Cause: llm_problem
[INVESTIGATOR]   Root Cause: technical_problem
[INVESTIGATOR]   Root Cause: approach_problem
[INVESTIGATOR]   Root Cause: requirements_problem
```

---

### Scenario E: What Routing Decision Was Made?

```bash
grep "ROUTING DECISION:" logs/app.log | tail -1
```

Expected:
```
[INVESTIGATOR] ↩️ ROUTING DECISION: PHASE 2 (Clarification Needed)
[INVESTIGATOR] ♻️ ROUTING DECISION: PHASE 3 (LLM Problem with Guidance)
[INVESTIGATOR] 🚨 ROUTING DECISION: ESCALATE (Technical Issue)
```

---

### Scenario F: Did Chat Message Get Saved?

```bash
grep "Chat message persisted" logs/app.log | tail -1
```

Expected:
```
[INVESTIGATOR] Chat message persisted to conversation
```

If this is NOT there, the chat message failed to persist. Check conversation_id.

---

## 🚨 Troubleshooting

### Problem: "No PHASE-EVALUATE logs visible"

**Check 1**: Is Phase 4 even being called?
```bash
grep "PHASE-EVALUATE.*STARTED" logs/app.log
```

If empty: Phase 3 didn't complete. Check orchestrator logs.

**Check 2**: Is settings.quality_evaluation_enabled = True?
```bash
grep "quality_evaluation_enabled" logs/app.log | head -1
```

If False: Phase 4 disabled. Check `.env` file.

---

### Problem: "Evaluation passed but run still failed"

This shouldn't happen, but if it does:

```bash
# See exact status:
grep "\[PHASE-EVALUATE\] EVALUATION PASSED\|failed" logs/app.log | tail -5
```

---

### Problem: "Investigator not triggering"

Check these in order:

```bash
# 1. Did retries reach exhaustion?
grep "RETRIES EXHAUSTED\|prior_retry_count" logs/app.log | tail -3

# 2. Did investigator get created?
grep "Investigator instance created" logs/app.log

# 3. Did it error?
grep "\[INVESTIGATOR\] ❌ ERROR" logs/app.log
```

---

### Problem: "Chat message not showing in Sheldon"

```bash
# 1. Was message persisted?
grep "Chat message persisted" logs/app.log

# 2. Was conversation ID found?
grep "conversation_id" logs/app.log | tail -3

# 3. Check database directly for message:
sqlite3 advise_workbench.db "SELECT id, role, content FROM conversation_message WHERE run_id='run_abc123' ORDER BY created_at DESC LIMIT 3;"
```

---

## 📊 Understanding the Logs

### Color Coding

- `✅` = Success
- `⚠️` = Warning
- `❌` = Error
- `🔴` = Critical
- `↩️` = Routing to Phase 2
- `♻️` = Routing to Phase 3
- `🚨` = Escalating

### Log Levels

- **NODE 1 (Analyze)**: Pattern detection from 3 attempts
- **NODE 2 (Classify)**: Root cause classification with confidence %
- **NODE 3 (Explain)**: Chat message generation
- **NODE 4 (Route)**: Routing decision

### Expected Confidence Range

- `data_problem`: 0.80 - 0.99
- `llm_problem`: 0.60 - 0.95
- `technical_problem`: 0.85 - 0.99
- `approach_problem`: 0.70 - 0.95

---

## 🧪 Test Checklist

Use this to verify Phase 4 works end-to-end:

- [ ] Happy path: Simple request → Quality PASS
- [ ] Retry path: Invalid request → Quality FAIL → Retry 1-3
- [ ] Investigator path: 3 retries exhausted → Investigator called
- [ ] Node 1: Patterns detected (should show 1-3 patterns)
- [ ] Node 2: Root cause classified (one of 5 categories)
- [ ] Node 3: Chat message generated (>200 chars)
- [ ] Node 4: Routing decision made (phase_2, phase_3, or escalate)
- [ ] Chat message appears in Sheldon UI
- [ ] Run status updated correctly (awaiting_clarification/approved/escalated_for_review)

---

## 📝 Example: Full Test Session

```bash
# Terminal 1: Watch logs
tail -f logs/app.log | grep -E "\[PHASE-EVALUATE\]|\[INVESTIGATOR"

# Terminal 2: Run test in Sheldon
# (enter request in Sheldon UI)

# Watch logs appear in Terminal 1
# Should see all 4 nodes executing
```

After test completes:

```bash
# Check final status
grep "run status set to\|Status:" logs/app.log | tail -3

# Verify investigator message persisted
sqlite3 advise_workbench.db "SELECT content FROM conversation_message WHERE run_id='run_abc123' AND content LIKE '%Investigator%' LIMIT 1;"
```

---

## ✅ Success Indicators

Phase 4 is working correctly if you see:

1. ✅ `[PHASE-EVALUATE] STARTED`
2. ✅ Quality evaluation results (status: pass or fail)
3. ✅ For failed runs: Retry attempts OR Investigator trigger
4. ✅ All 4 nodes executing: `[INVESTIGATOR-NODE] ✅ NODE X COMPLETE`
5. ✅ Routing decision made and executed
6. ✅ Chat message persisted
7. ✅ Run status updated

---

## 🎓 Next Steps

After verifying Phase 4:

1. Run all 5 test cases from testing guide
2. Monitor logs for any errors
3. Verify chat messages appear in Sheldon UI
4. Test Phase 2 clarification path (awaiting_clarification → user responds)
5. Test Phase 3 retry path (approved → regenerate with guidance)
6. Test escalation path (escalated_for_review → shown to user)

---

**Your logs now have full debugging info!** 🚀

Run any test case and watch Phase 4 in detail with these new logs.
