# Phase 4 Deep Dive - Verification Checklist

**Purpose**: Verify that the entire Phase 4 retry → investigator flow is correctly implemented.

---

## 🚨 Critical Facts (Verified in Code)

✅ **Line 131**: `MAX_EVALUATOR_REMEDIATION_ROUNDS = 3` - Set to 3
✅ **Line 1356**: `hard_gate_enabled = True` - Enabled by default
✅ **Line 2449**: Quality evaluation results logged
✅ **Line 2459**: `if prior_retry_count < MAX_EVALUATOR_REMEDIATION_ROUNDS:` - Retry check
✅ **Line 2633**: `enqueue_run_execution(project_id, run_id)` - Re-queue happens
✅ **Line 2629-2634**: Investigator triggered when `prior_retry_count >= 3`

---

## 🧪 Test Plan

### Test Scenario: Retry Path (Fail 3 Times Then Investigator)

1. **Send request that will FAIL quality checks**
   - Something that causes visual QA to fail but isn't a technical error
   - Example: "Generate presentation with metrics that don't match data perfectly"

2. **Monitor logs for EXACT sequence:**

---

## ✅ Verification Checklist

### PART 1: Phase 4 Entry ✅

Look for:
```
════════════════════════════════════════════════════════════════════════════════
[PHASE-EVALUATE] STARTED for run_id=run_abc123
════════════════════════════════════════════════════════════════════════════════
```

**VERIFY**: 
- [ ] You see `[PHASE-EVALUATE] STARTED`
- [ ] If NOT → Phase 4 wasn't reached (check Phase 3 logs)

---

### PART 2: Evaluation Results ✅

Look for:
```
────────────────────────────────────────────────────────────────────────────────
[PHASE-EVALUATE] 📊 EVALUATION RESULTS:
[PHASE-EVALUATE]   Status: fail
[PHASE-EVALUATE]   Visual QA Passed: False
[PHASE-EVALUATE]   QA Passed: True/False
[PHASE-EVALUATE]   Guardrails Passed: True/False
[PHASE-EVALUATE]   Evidence Passed: True/False
────────────────────────────────────────────────────────────────────────────────
```

**VERIFY**:
- [ ] You see `📊 EVALUATION RESULTS:`
- [ ] Status is clearly shown (`fail` or `pass`)
- [ ] All check results are visible
- [ ] If Status is `pass` → Skip to PART 8 (no retries needed)

---

### PART 3: Decision Logic ✅

Look for:
```
════════════════════════════════════════════════════════════════════════════════
[PHASE-EVALUATE] ⚙️ PHASE-EVALUATE DECISION LOGIC
[PHASE-EVALUATE]   MAX_EVALUATOR_REMEDIATION_ROUNDS: 3
[PHASE-EVALUATE]   hard_gate_enabled: True
[PHASE-EVALUATE]   evaluator_pipeline['status']: fail
════════════════════════════════════════════════════════════════════════════════
```

**VERIFY**:
- [ ] `MAX_EVALUATOR_REMEDIATION_ROUNDS: 3` (should always be 3)
- [ ] `hard_gate_enabled: True` (if False, no retries!)
- [ ] `evaluator_pipeline['status']: fail` (should be fail for this test)

---

### PART 4: Retry Count Check ✅

Look for:
```
════════════════════════════════════════════════════════════════════════════════
[PHASE-EVALUATE] 🔴 EVALUATION FAILED
[PHASE-EVALUATE] RETRY COUNT CHECK:
[PHASE-EVALUATE]   prior_retry_count: 0
[PHASE-EVALUATE]   MAX_EVALUATOR_REMEDIATION_ROUNDS: 3
[PHASE-EVALUATE]   prior_retry_count < MAX?: True
════════════════════════════════════════════════════════════════════════════════
```

**VERIFY** (First attempt):
- [ ] `prior_retry_count: 0` (first try)
- [ ] `prior_retry_count < MAX?: True` (should enter retry logic)

**VERIFY** (Second attempt):
- [ ] `prior_retry_count: 1` (second try)
- [ ] `prior_retry_count < MAX?: True` (still retry)

**VERIFY** (Third attempt):
- [ ] `prior_retry_count: 2` (third try)
- [ ] `prior_retry_count < MAX?: True` (last retry)

**VERIFY** (Fourth attempt - should trigger investigator):
- [ ] `prior_retry_count: 3` (exhausted)
- [ ] `prior_retry_count < MAX?: False` (NO retry, trigger investigator)

---

### PART 5: Retry Path (Attempts 1, 2, 3) ✅

Look for:
```
[PHASE-EVALUATE] 🔄 RETRY PATH: Attempt 1/3
[PHASE-EVALUATE]   Re-queueing run for Phase 3 generation with feedback...
[PHASE-EVALUATE]   Failed checks: visual_qa=True, qa=False, guardrails=True
[PHASE-EVALUATE] ⏳ ENQUEUING RUN FOR RETRY...
[PHASE-EVALUATE] ✅ ENQUEUE RESULT: True
[PHASE-EVALUATE] 🔁 RUN WILL RE-START FROM PHASE-PREPARE WITH FEEDBACK
[PHASE-EVALUATE] ✅ RETURNING from Phase 4 (run re-queued)
```

**VERIFY** (Should appear 3 times):
- [ ] `🔄 RETRY PATH: Attempt 1/3` (first retry)
- [ ] `Re-queueing run for Phase 3 generation with feedback...`
- [ ] `🔁 RUN WILL RE-START FROM PHASE-PREPARE WITH FEEDBACK`
- [ ] `✅ ENQUEUE RESULT: True` (successfully queued)

**Then it should:**
- [ ] Orchestrator restarts from PHASE-PREPARE
- [ ] Phase 3 generation runs AGAIN with feedback injected
- [ ] Phase 4 evaluation runs AGAIN
- [ ] Shows next attempt (2/3, then 3/3)

---

### PART 6: Exhaustion (Attempt 4) ✅

Look for:
```
════════════════════════════════════════════════════════════════════════════════
[PHASE-EVALUATE] 🔴 RETRIES EXHAUSTED (3/3)
[PHASE-EVALUATE] ⏳ Initiating Investigator Agent Analysis...
════════════════════════════════════════════════════════════════════════════════
```

**VERIFY**:
- [ ] After 3 retries, you see `🔴 RETRIES EXHAUSTED (3/3)`
- [ ] NOT another retry (no `🔄 RETRY PATH`)
- [ ] Next section shows investigator trigger

---

### PART 7: Investigator Agent Execution ✅

Look for:
```
[INVESTIGATOR] 🤖 Creating InvestigatorAgent instance...
[INVESTIGATOR] ✅ InvestigatorAgent instance created successfully

[INVESTIGATOR] 🔎 Querying database for retry events...
[INVESTIGATOR] 📋 RETRY EVENT SUMMARY:
[INVESTIGATOR]   Total retry events in database: 3
[INVESTIGATOR]   Attempt 1: Error summary...
[INVESTIGATOR]   Attempt 2: Error summary...
[INVESTIGATOR]   Attempt 3: Error summary...

[INVESTIGATOR] 🔍 CALLING INVESTIGATION PIPELINE...
✅ INVESTIGATION PIPELINE RETURNED RESULT

[INVESTIGATOR] 📊 INVESTIGATING RESULT:
[INVESTIGATOR]   Root cause: data_problem
[INVESTIGATOR]   Confidence: 95.0%
[INVESTIGATOR]   Route to: phase_2
[INVESTIGATOR]   Chat message created: True
```

**VERIFY**:
- [ ] `🤖 Creating InvestigatorAgent instance...`
- [ ] `✅ InvestigatorAgent instance created successfully`
- [ ] `Total retry events in database: 3` (should be exactly 3)
- [ ] Each attempt listed (1, 2, 3)
- [ ] `✅ INVESTIGATION PIPELINE RETURNED RESULT`
- [ ] Root cause detected (one of: data_problem, llm_problem, technical_problem, etc)
- [ ] Confidence shown (0-100%)
- [ ] Route decision shown (phase_2, phase_3, or escalate)

---

### PART 8: All 4 Nodes Execute ✅

Look for:
```
────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 🔍 NODE 1: ANALYZE FAILURES
[INVESTIGATOR-NODE] Input: 3 failed attempts
[INVESTIGATOR-NODE]   Patterns found: X
[INVESTIGATOR-NODE]   Error evolution: ...
[INVESTIGATOR-NODE] ✅ NODE 1 COMPLETE

[INVESTIGATOR-NODE] 🎯 NODE 2: CLASSIFY ROOT CAUSE
[INVESTIGATOR-NODE] Input: 3 attempts analyzed
[INVESTIGATOR-NODE]   Root Cause: data_problem
[INVESTIGATOR-NODE]   Confidence: 95.0%
[INVESTIGATOR-NODE] ✅ NODE 2 COMPLETE

[INVESTIGATOR-NODE] 💬 NODE 3: GENERATE CHAT EXPLANATION
[INVESTIGATOR-NODE] Input: data_problem at confidence 95.0%
[INVESTIGATOR-NODE]   Message length: XXX chars
[INVESTIGATOR-NODE] ✅ NODE 3 COMPLETE

[INVESTIGATOR-NODE] 🚦 NODE 4: MAKE ROUTING DECISION
[INVESTIGATOR-NODE] Input: data_problem
[INVESTIGATOR-NODE]   Route: phase_2
[INVESTIGATOR-NODE] ✅ NODE 4 COMPLETE
════════════════════════════════════════════════════════════════════════════════
```

**VERIFY**:
- [ ] All 4 nodes appear in order (1 → 2 → 3 → 4)
- [ ] Each node shows `✅ NODE X COMPLETE`
- [ ] Node 2 shows root cause classification
- [ ] Node 4 shows routing decision

---

### PART 9: Final Routing ✅

Look for ONE of these:

**PHASE 2 Path:**
```
[INVESTIGATOR] ↩️ ROUTING → PHASE 2 (Clarification Needed)
[INVESTIGATOR]   Reason: Data/context issue needs clarification
[INVESTIGATOR]   ✅ Database: run.status → 'awaiting_clarification'
[INVESTIGATOR]   ✅ Event: investigator_routed_to_phase2 recorded
[INVESTIGATOR] ✅ PHASE 2 ROUTING COMPLETE
```

**PHASE 3 Path:**
```
[INVESTIGATOR] ♻️ ROUTING → PHASE 3 (LLM Problem with Guidance)
[INVESTIGATOR]   Reason: Model needs better guidance
[INVESTIGATOR]   Guidance items: 3
[INVESTIGATOR]   ✅ Database: run.status → 'approved'
[INVESTIGATOR]   ✅ RUN RE-QUEUED
[INVESTIGATOR] ✅ PHASE 3 ROUTING COMPLETE
```

**ESCALATE Path:**
```
[INVESTIGATOR] 🚨 ROUTING → ESCALATE (Technical Issue)
[INVESTIGATOR]   Reason: Format or tool limitation
[INVESTIGATOR]   ✅ Database: run.status → 'escalated_for_review'
[INVESTIGATOR]   ✅ Event: investigator_escalated recorded
[INVESTIGATOR] ✅ ESCALATION ROUTING COMPLETE
```

**VERIFY** (ONE should appear):
- [ ] One of the 3 routing paths above
- [ ] Database status updated (awaiting_clarification / approved / escalated_for_review)
- [ ] Event recorded
- [ ] Message shown to user in Sheldon chat

---

### PART 10: Complete ✅

Look for:
```
════════════════════════════════════════════════════════════════════════════════
[INVESTIGATOR] ✅ INVESTIGATION PIPELINE COMPLETE
[INVESTIGATOR]   Status: awaiting_clarification (or approved or escalated_for_review)
[INVESTIGATOR]   Chat message persisted: YES
════════════════════════════════════════════════════════════════════════════════
```

**VERIFY**:
- [ ] `✅ INVESTIGATION PIPELINE COMPLETE`
- [ ] Status shown
- [ ] Chat message persisted: YES

---

## 🎯 Summary Checklist

### If evaluation PASSES:
- [ ] See `✅✅✅ EVALUATION PASSED! ✅✅✅`
- [ ] No retries or investigator
- [ ] Move to next phase

### If evaluation FAILS:
- [ ] See `🔴 EVALUATION FAILED`
- [ ] See `prior_retry_count: 0`, `1`, or `2` (not 3)
- [ ] See `🔄 RETRY PATH: Attempt X/3`
- [ ] See `✅ ENQUEUE RESULT: True`
- [ ] Orchestrator restarts

### After 3 retries:
- [ ] See `prior_retry_count: 3`
- [ ] See `🔴 RETRIES EXHAUSTED (3/3)`
- [ ] See `🤖 Creating InvestigatorAgent instance...`
- [ ] See all 4 nodes execute
- [ ] See routing decision
- [ ] See chat message persisted

---

## 🚀 How to Test

### Terminal 1: Restart Server
```bash
uvicorn src.app.main:app --reload
# Wait for "Application startup complete"
```

### Terminal 2: Watch Logs
```bash
tail -f logs/app.log | grep -E "\[PHASE-EVALUATE\]|\[INVESTIGATOR\]|EVALUATION|RETRIES|ROUTING"
```

### Terminal 3: Test in Sheldon
```
Request something that will fail quality checks.
Example: "Generate presentation with non-existent metrics"
```

### Terminal 2: Watch for Each Part
- Look for Part 1 (entry)
- Look for Part 2 (results)
- Look for Part 3 (decision logic)
- Look for Part 4 (retry count check)
- Repeat Parts 4-5 three times
- Look for Part 6 (exhaustion)
- Look for Part 7-10 (investigator)

---

## 🔴 If Something is Wrong

### If no `[PHASE-EVALUATE]` logs:
```bash
# Phase 4 wasn't reached
grep "\[PHASE-EVALUATE\]" logs/app.log
```
→ Check if Phase 3 completed

### If only 1 attempt, no retries:
```bash
# Retry logic didn't trigger
grep "prior_retry_count\|RETRY PATH" logs/app.log
```
→ Check if `hard_gate_enabled` is `True`

### If investigator never appears:
```bash
# Retries didn't go to 3
grep "RETRIES EXHAUSTED\|prior_retry_count: 3" logs/app.log
```
→ Might be getting re-queued but Phase 4 not re-running

### If chat message doesn't show:
```bash
# Message not persisted
grep "Chat message persisted" logs/app.log
```
→ Check database for conversation_id

---

## ✅ Success = All Checkmarks

When you run the test, you should see:
1. ✅ Phase 4 entry
2. ✅ Evaluation results
3. ✅ Decision logic
4. ✅ Retry count (0, 1, 2 sequentially)
5. ✅ Retry path x3 (with enqueue)
6. ✅ Retries exhausted (count = 3)
7. ✅ Investigator created
8. ✅ All 4 nodes execute
9. ✅ Routing decision
10. ✅ Pipeline complete

If you see all of these → **Everything is working correctly!** 🎉
