# Complete Logging Verification - All Phases 2-4

**Updated**: 2026-11-03  
**Status**: Comprehensive logging added to every decision point

---

## 🚀 Quick Start

### Step 1: Restart Server

```bash
# Kill old server (Ctrl+C)
# Then start fresh:
uvicorn src.app.main:app --reload

# Wait for: "Application startup complete"
```

### Step 2: Watch Logs in Real-Time

```bash
# Terminal A: Watch ALL phase/investigator logs
tail -f logs/app.log | grep -E "\[PHASE-|INVESTIGATOR|EVALUATION RESULTS|RETRIES EXHAUSTED"

# Terminal B: Test in Sheldon UI
# (Run a request)
```

### Step 3: Verify Each Step

As logs appear, you should see THIS EXACT SEQUENCE:

---

## ✅ COMPLETE LOG SEQUENCE

### SECTION 1: Phase 2 Validation ✅

```
================================================================================
[PHASE-2-VALIDATE] START for user=..., conversation=...
[PHASE-2-VALIDATE] Instruction: ...
================================================================================

[CONTEXT-VALIDATE] Starting context validation...
[CONTEXT-VALIDATE] Report: has_issues=False, confidence=1.00
[CONTEXT-VALIDATE] ✅ Validation passed, continuing to phase2_route...

🔵 [PHASE2-ENTERED] intent=slide_agree | has_agents=?
✅ [PHASE-RESPOND] executed
```

**What to verify**: 
- ✅ `[PHASE-2-VALIDATE] START`
- ✅ `[CONTEXT-VALIDATE] ✅ Validation passed`
- ✅ `[PHASE-RESPOND] executed`

---

### SECTION 2: Phase 3 Generation ✅

```
================================================================================
[ORCHESTRATOR] STARTING RUN EXECUTION
[ORCHESTRATOR] Project: p_c91ccece8a
[ORCHESTRATOR] Run ID: run_abc123
[ORCHESTRATOR] Will execute 6 phases...
================================================================================

[PHASE-PREPARE] STARTED for run_id=run_abc123
[PHASE-PREPARE] 1. Loading run from database...
[PHASE-PREPARE] 1b. Run loaded: status=approved
... (more phase-prepare logs)
[PHASE-PREPARE] [OK] PHASE COMPLETE - moving to next phase

[PHASE-CONTEXT] STARTED for run_id=run_abc123
... (context loading)
[PHASE-CONTEXT] [OK] STEPS 1-7 COMPLETE

[PATH-ROUTER] STARTED for run_id=run_abc123
[PATH-ROUTER] Router decision: path=1.c, confidence=0.75
[PATH-ROUTER] [OK] COMPLETE

[PHASE-GENERATE] STARTED for run_id=run_abc123
... (model loading, artifact generation)
[PHASE-GENERATE] [OK] PHASE COMPLETE - all outputs streamed
[PHASE-GENERATE] All artifacts generated and persisted to disk
```

**What to verify**:
- ✅ `[ORCHESTRATOR] STARTING RUN EXECUTION`
- ✅ `[PHASE-PREPARE] STARTED`
- ✅ `[PHASE-GENERATE] STARTED`
- ✅ `[PHASE-GENERATE] [OK] PHASE COMPLETE`

---

### SECTION 3: Phase 4 Evaluation - CRITICAL ⭐

#### A. Evaluation Results Check:

```
[PHASE-EVALUATE] 🔎 CHECKING EVALUATION STATUS...
[PHASE-EVALUATE]   hard_gate_enabled: True
[PHASE-EVALUATE]   evaluator_pipeline['status']: fail (or pass)

[PHASE-EVALUATE] 📊 EVALUATION RESULTS:
[PHASE-EVALUATE]   Status: fail
[PHASE-EVALUATE]   Visual QA Passed: False
[PHASE-EVALUATE]   QA Passed: True
[PHASE-EVALUATE]   Guardrails Passed: True
[PHASE-EVALUATE]   Evidence Passed: True
```

**What to verify**:
- ✅ `[PHASE-EVALUATE] 📊 EVALUATION RESULTS:` appears
- ✅ `Status:` is shown (fail or pass)
- ✅ All check results visible

---

#### B. HAPPY PATH (If evaluation passes):

```
================================================================================
[PHASE-EVALUATE] ✅✅✅ EVALUATION PASSED! ✅✅✅
[PHASE-EVALUATE]   All quality checks PASSED
[PHASE-EVALUATE]   Moving to PHASE-REMEMBER (next phase)
================================================================================
```

**What to verify**:
- ✅ `✅✅✅ EVALUATION PASSED! ✅✅✅` message
- ✅ No investigator logs after this

---

#### C. RETRY PATH (If evaluation fails and retry < 3):

```
[PHASE-EVALUATE] ⚠️ EVALUATION FAILED - Current retry count: 0/3
[PHASE-EVALUATE] 🔄 RETRY PATH: Attempt 1/3
[PHASE-EVALUATE]   Re-queuing run for Phase 3 generation with feedback...
[PHASE-EVALUATE]   Failed checks: visual_qa=True, qa=False, guardrails=False
```

**What to verify**:
- ✅ `Current retry count:` shown (0/3, 1/3, or 2/3)
- ✅ `RETRY PATH:` message
- ✅ Failed checks listed
- ⏳ Run re-queues (orchestrator restarts from PREPARE)

Continue watching for next retry...

---

#### D. INVESTIGATOR TRIGGER (If retry count >= 3):

```
================================================================================
[PHASE-EVALUATE] 🔴 RETRIES EXHAUSTED (3/3)
[PHASE-EVALUATE] ⏳ Initiating Investigator Agent Analysis...
================================================================================

[INVESTIGATOR] 🤖 Creating InvestigatorAgent instance...
[INVESTIGATOR] ✅ InvestigatorAgent instance created successfully

[INVESTIGATOR] 🔎 Querying database for retry events...
[INVESTIGATOR] 📋 RETRY EVENT SUMMARY:
[INVESTIGATOR]   Total retry events in database: 3
[INVESTIGATOR]   Attempt 1: Missing metric in chart generation...
[INVESTIGATOR]   Attempt 2: Chart data validation failed...
[INVESTIGATOR]   Attempt 3: Metadata extraction error...
```

**What to verify**:
- ✅ `🔴 RETRIES EXHAUSTED (3/3)` message
- ✅ `🤖 Creating InvestigatorAgent instance...`
- ✅ `✅ InvestigatorAgent instance created successfully`
- ✅ Retry events listed (should be 3)

---

### SECTION 4: Investigator Analysis - 4 Nodes ⭐

#### Node 1: Analyze Failures

```
────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 🔍 NODE 1: ANALYZE FAILURES
[INVESTIGATOR-NODE] Input: 3 failed attempts
[INVESTIGATOR-NODE]   Patterns found: 2
[INVESTIGATOR-NODE]   Error evolution: SAME stage fails every attempt: generation
[INVESTIGATOR-NODE] ✅ NODE 1 COMPLETE
```

**What to verify**:
- ✅ `NODE 1: ANALYZE FAILURES`
- ✅ Patterns found: (number)
- ✅ `✅ NODE 1 COMPLETE`

---

#### Node 2: Classify Root Cause

```
────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 🎯 NODE 2: CLASSIFY ROOT CAUSE
[INVESTIGATOR-NODE] Input: 3 attempts analyzed
[INVESTIGATOR-NODE]   Root Cause: data_problem
[INVESTIGATOR-NODE]   Confidence: 95.0%
[INVESTIGATOR-NODE]   Reasoning: The requested metrics are not available...
[INVESTIGATOR-NODE] ✅ NODE 2 COMPLETE
```

**What to verify**:
- ✅ `NODE 2: CLASSIFY ROOT CAUSE`
- ✅ Root Cause: (one of 5: data_problem, llm_problem, technical_problem, approach_problem, requirements_problem)
- ✅ Confidence: (0-100%)
- ✅ `✅ NODE 2 COMPLETE`

---

#### Node 3: Generate Chat Explanation

```
────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 💬 NODE 3: GENERATE CHAT EXPLANATION
[INVESTIGATOR-NODE] Input: data_problem at confidence 95.0%
[INVESTIGATOR-NODE]   Message length: 547 chars
[INVESTIGATOR-NODE] ✅ NODE 3 COMPLETE
```

**What to verify**:
- ✅ `NODE 3: GENERATE CHAT EXPLANATION`
- ✅ Message length: (should be > 200)
- ✅ `✅ NODE 3 COMPLETE`

---

#### Node 4: Make Routing Decision

```
────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR-NODE] 🚦 NODE 4: MAKE ROUTING DECISION
[INVESTIGATOR-NODE] Input: data_problem
[INVESTIGATOR-NODE]   Route: phase_2
[INVESTIGATOR-NODE]   Reason: Data/context issue needs clarification
[INVESTIGATOR-NODE]   Message: Let's clarify the data before retrying...
[INVESTIGATOR-NODE] ✅ NODE 4 COMPLETE
════════════════════════════════════════════════════════════════════════════════
```

**What to verify**:
- ✅ `NODE 4: MAKE ROUTING DECISION`
- ✅ Route: (phase_2, phase_3, or escalate)
- ✅ Reason: (shown)
- ✅ `✅ NODE 4 COMPLETE`

---

### SECTION 5: Investigator Result Processing ⭐

#### Result Summary:

```
────────────────────────────────────────────────────────────────────────────────
[INVESTIGATOR] 📊 ANALYSIS COMPLETE:
[INVESTIGATOR]   Root Cause: data_problem
[INVESTIGATOR]   Confidence: 95.0%
[INVESTIGATOR]   Routing to: phase_2
[INVESTIGATOR]   Chat message length: 547
────────────────────────────────────────────────────────────────────────────────

[INVESTIGATOR] 💬 PERSISTING CHAT MESSAGE...
[INVESTIGATOR]   Found conversation: conv_abc123
[INVESTIGATOR] ✅ Chat message persisted to conversation conv_abc123
[INVESTIGATOR]   Message length: 547 chars
```

**What to verify**:
- ✅ `📊 ANALYSIS COMPLETE:`
- ✅ Root Cause, Confidence, Routing shown
- ✅ `💬 PERSISTING CHAT MESSAGE...`
- ✅ `✅ Chat message persisted to conversation`

---

#### Routing Decision Handler:

```
================================================================================
[INVESTIGATOR] 🚦 ROUTING DECISION HANDLER
[INVESTIGATOR]   Route decision: phase_2
================================================================================

[INVESTIGATOR] ↩️ ROUTING → PHASE 2 (Clarification Needed)
[INVESTIGATOR]   Reason: Data/context issue needs clarification
[INVESTIGATOR]   Message preview: Let's clarify the data...
[INVESTIGATOR]   ✅ Database: run.status → 'awaiting_clarification'
[INVESTIGATOR]   ✅ Database: error_message saved
[INVESTIGATOR]   ✅ Event: investigator_routed_to_phase2 recorded
[INVESTIGATOR] ✅ PHASE 2 ROUTING COMPLETE
```

**What to verify** (one of these three):

**For PHASE 2:**
- ✅ `↩️ ROUTING → PHASE 2`
- ✅ `run.status → 'awaiting_clarification'`
- ✅ `investigator_routed_to_phase2 recorded`

**For PHASE 3:**
- ✅ `♻️ ROUTING → PHASE 3`
- ✅ `run.status → 'approved'`
- ✅ `guidance injected into plan_payload`
- ✅ `investigator_routed_to_phase3 recorded`
- ✅ `RUN RE-QUEUED` (re-runs generation)

**For ESCALATE:**
- ✅ `🚨 ROUTING → ESCALATE`
- ✅ `run.status → 'escalated_for_review'`
- ✅ `investigator_escalated recorded`

---

### SECTION 6: Final Status

```
════════════════════════════════════════════════════════════════════════════════
[INVESTIGATOR] ✅ INVESTIGATION PIPELINE COMPLETE
[INVESTIGATOR]   Status: awaiting_clarification (or approved or escalated_for_review)
[INVESTIGATOR]   Chat message persisted: YES
════════════════════════════════════════════════════════════════════════════════
```

**What to verify**:
- ✅ `✅ INVESTIGATION PIPELINE COMPLETE`
- ✅ Final Status shown
- ✅ Chat message persisted: YES

---

## 🔍 Quick Reference Commands

### Command 1: See ALL phase/investigator logs
```bash
tail -f logs/app.log | grep -E "\[PHASE-|INVESTIGATOR|EVALUATION"
```

### Command 2: See only Phase 4 evaluation
```bash
grep "\[PHASE-EVALUATE\]" logs/app.log | tail -20
```

### Command 3: See only investigator
```bash
grep "\[INVESTIGATOR" logs/app.log | tail -50
```

### Command 4: See full run for specific ID
```bash
grep "run_f381d8a188" logs/app.log | grep -E "\[PHASE-|INVESTIGATOR"
```

### Command 5: See if evaluator PASSED
```bash
grep "EVALUATION PASSED" logs/app.log
```

### Command 6: See if investigator triggered
```bash
grep "RETRIES EXHAUSTED" logs/app.log
```

### Command 7: See root causes detected
```bash
grep "Root Cause:" logs/app.log
```

### Command 8: See routing decisions
```bash
grep "ROUTING →" logs/app.log
```

---

## ✅ Success Checklist

After running a test, ALL of these should appear in logs:

- [ ] `[PHASE-2-VALIDATE] START`
- [ ] `[CONTEXT-VALIDATE] ✅ Validation passed`
- [ ] `[ORCHESTRATOR] STARTING RUN EXECUTION`
- [ ] `[PHASE-PREPARE] STARTED`
- [ ] `[PHASE-GENERATE] STARTED`
- [ ] `[PHASE-EVALUATE] STARTED`
- [ ] `[PHASE-EVALUATE] 📊 EVALUATION RESULTS:`
- [ ] Either:
  - `✅ EVALUATION PASSED!` OR
  - `🔄 RETRY PATH: Attempt X/3` OR
  - `🔴 RETRIES EXHAUSTED (3/3)`
- [ ] If exhausted:
  - `[INVESTIGATOR] 🤖 Creating InvestigatorAgent instance...`
  - `[INVESTIGATOR] ✅ InvestigatorAgent instance created successfully`
- [ ] All 4 nodes execute:
  - `[INVESTIGATOR-NODE] 🔍 NODE 1: ANALYZE FAILURES` → `✅ NODE 1 COMPLETE`
  - `[INVESTIGATOR-NODE] 🎯 NODE 2: CLASSIFY ROOT CAUSE` → `✅ NODE 2 COMPLETE`
  - `[INVESTIGATOR-NODE] 💬 NODE 3: GENERATE CHAT EXPLANATION` → `✅ NODE 3 COMPLETE`
  - `[INVESTIGATOR-NODE] 🚦 NODE 4: MAKE ROUTING DECISION` → `✅ NODE 4 COMPLETE`
- [ ] Routing decision shown:
  - `[INVESTIGATOR] 🚦 ROUTING DECISION HANDLER`
  - One of: `↩️ ROUTING → PHASE 2` OR `♻️ ROUTING → PHASE 3` OR `🚨 ROUTING → ESCALATE`
- [ ] Chat message persisted:
  - `[INVESTIGATOR] ✅ Chat message persisted to conversation`
- [ ] Final status:
  - `[INVESTIGATOR] ✅ INVESTIGATION PIPELINE COMPLETE`

---

## 🚀 Ready?

1. **Restart server**: `uvicorn src.app.main:app --reload`
2. **Watch logs**: `tail -f logs/app.log | grep -E "\[PHASE-|INVESTIGATOR"`
3. **Test in Sheldon**: Request generation
4. **Verify**: All checkmarks above appear in logs

You should now see **EVERYTHING** that happens! 🎉
