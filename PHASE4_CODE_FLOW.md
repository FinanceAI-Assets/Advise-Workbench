# Phase 4 Code Flow - Exact Sequence

**This document shows EXACTLY what code executes at each step.**

---

## 🔄 The Complete Flow

```
START: Phase 4 (_phase_evaluate)
│
├─ Line 2268: Print "[PHASE-EVALUATE] STARTED"
│
├─ Line 2270-2319: Run Visual QA checks
│  └─ Line 2319: save_visual_qa_report(...)
│
├─ Line 2424: _build_evaluator_pipeline(...)
│  └─ Evaluates: visual_qa, qa_report, guardrails, evidence
│
├─ Line 2427-2433: Log EVALUATION RESULTS
│  ├─ Status: pass/fail
│  ├─ Visual QA Passed: True/False
│  ├─ QA Passed: True/False
│  ├─ Guardrails Passed: True/False
│  ├─ Evidence Passed: True/False
│  └─ Print all results
│
├─ Line 2435: append_run_event(session, run_id, "evaluator_pipeline", evaluator_pipeline)
│
├─ Line 2449: IF hard_gate_enabled AND status != "pass":
│  │
│  ├─ YES → Line 2451-2659: Handle FAILURE
│  │  │
│  │  ├─ Line 2451: Query prior_retry_count
│  │  │  └─ Count of "evaluator_retry_requested" events
│  │  │
│  │  ├─ Line 2459: IF prior_retry_count < MAX_EVALUATOR_REMEDIATION_ROUNDS (3):
│  │  │  │
│  │  │  ├─ YES → RETRY PATH (Line 2460-2633)
│  │  │  │  │
│  │  │  │  ├─ Line 2460: run.status = "approved"
│  │  │  │  ├─ Line 2461: nxt = prior_retry_count + 1
│  │  │  │  ├─ Line 2467-2471: Log RETRY PATH
│  │  │  │  │
│  │  │  │  ├─ Line 2472-2605: INJECT FEEDBACK
│  │  │  │  │  ├─ Visual feedback hints
│  │  │  │  │  ├─ Evidence remediation
│  │  │  │  │  ├─ Narrative feedback
│  │  │  │  │  ├─ Guardrail directive
│  │  │  │  │  └─ Line 2603: run.plan_payload = json.dumps(retry_plan)
│  │  │  │  │
│  │  │  │  ├─ Line 2606-2624: append_run_event (RETRY RECORDED)
│  │  │  │  ├─ Line 2633: enqueue_run_execution(project_id, run_id)
│  │  │  │  │  └─ RE-QUEUES RUN TO QUEUE
│  │  │  │  │
│  │  │  │  ├─ Line 2637: Log ENQUEUE RESULT
│  │  │  │  └─ Line 2639: return True, None
│  │  │  │     └─ EXITS PHASE 4, RUN RE-QUEUED
│  │  │  │     └─ Orchestrator will restart from PHASE-PREPARE
│  │  │  │
│  │  │  └─ NO → INVESTIGATOR PATH (Line 2640-2765)
│  │  │     │
│  │  │     ├─ Line 2663: print "🔴 RETRIES EXHAUSTED"
│  │  │     │
│  │  │     ├─ Line 2669: investigator = InvestigatorAgent()
│  │  │     ├─ Line 2683: Query retry_events from database
│  │  │     ├─ Line 2696-2709: Build attempts_data
│  │  │     │
│  │  │     ├─ Line 2720: investigation_result = investigator.investigate_and_decide(attempts_data, context_info)
│  │  │     │  │
│  │  │     │  ├─ INVESTIGATOR AGENT EXECUTION:
│  │  │     │  ├─ Node 1: analyze_failures_node()
│  │  │     │  │  └─ Analyzes 3 attempts, finds patterns
│  │  │     │  ├─ Node 2: classify_root_cause_node()
│  │  │     │  │  └─ Classifies: data_problem, llm_problem, technical_problem, etc
│  │  │     │  ├─ Node 3: generate_chat_explanation_node()
│  │  │     │  │  └─ Creates user message
│  │  │     │  ├─ Node 4: make_routing_decision_node()
│  │  │     │  │  └─ Routes: phase_2, phase_3, or escalate
│  │  │     │  └─ Returns: investigation_result dict
│  │  │     │
│  │  │     ├─ Line 2748-2759: PERSIST CHAT MESSAGE
│  │  │     │  ├─ Query ConversationMessage by run_id
│  │  │     │  ├─ Create new message with investigator_analysis
│  │  │     │  ├─ session.add(msg)
│  │  │     │  ├─ session.commit()
│  │  │     │  └─ Log "Chat message persisted to conversation"
│  │  │     │
│  │  │     ├─ Line 2768: route_to = investigation_result["routing_decision"].get("route_to")
│  │  │     │
│  │  │     ├─ IF route_to == "phase_2": (Line 2770-2792)
│  │  │     │  ├─ run.status = "awaiting_clarification"
│  │  │     │  ├─ append_run_event(..., "investigator_routed_to_phase2", ...)
│  │  │     │  ├─ session.commit()
│  │  │     │  └─ NO RETURN = CONTINUE TO PHASE 5
│  │  │     │
│  │  │     ├─ ELIF route_to == "phase_3": (Line 2794-2815)
│  │  │     │  ├─ run.status = "approved"
│  │  │     │  ├─ Inject guidance into plan_payload
│  │  │     │  ├─ append_run_event(..., "investigator_routed_to_phase3", ...)
│  │  │     │  ├─ enqueue_run_execution(project_id, run_id)
│  │  │     │  └─ return True, None
│  │  │     │     └─ RE-QUEUES RUN WITH GUIDANCE
│  │  │     │
│  │  │     ├─ ELSE: route_to == "escalate" (Line 2817-2836)
│  │  │     │  ├─ run.status = "escalated_for_review"
│  │  │     │  ├─ append_run_event(..., "investigator_escalated", ...)
│  │  │     │  ├─ session.commit()
│  │  │     │  └─ NO RETURN = CONTINUE TO PHASE 5
│  │  │     │
│  │  │     └─ Line 2848: Log "INVESTIGATION PIPELINE COMPLETE"
│  │  │
│  │  └─ NO → Skip to line 2861 (status = failed)
│  │
│  └─ NO → Line 2841-2842: Continue to next phase (no action needed)
│
├─ Line 2841-2842: IF NOT hard_gate_enabled OR status == "pass":
│  └─ Continue to PHASE-REMEMBER
│
└─ END: Return None (or return False, message if failed)
```

---

## 🔑 Critical Variables

### MAX_EVALUATOR_REMEDIATION_ROUNDS
```python
# Line 131
MAX_EVALUATOR_REMEDIATION_ROUNDS = 3
```
**What it means**: Allow up to 3 retry attempts before triggering investigator.

---

### hard_gate_enabled
```python
# Line 1356 (default)
hard_gate_enabled = True

# Line 1377-1378 (can be overridden in settings.json)
if "hard_gate_enabled" in settings_data:
    hard_gate_enabled = bool(settings_data["hard_gate_enabled"])
```
**What it means**: If True, quality failures trigger retries/investigator. If False, skip to next phase.

---

### prior_retry_count
```python
# Line 2451 - Query count from database
prior_retry_count = int(
    session.scalar(
        select(func.count()).select_from(RunEvent).where(
            RunEvent.run_id == run_id, 
            RunEvent.event_type == "evaluator_retry_requested"
        )
    )
    or 0
)
```
**What it means**: How many times has this run already been retried? (0, 1, 2, or 3+)

---

## 📊 Decision Tree

```
evaluator_pipeline["status"] == "pass"?
├─ YES → Continue to next phase (no action)
└─ NO:
   hard_gate_enabled == True?
   ├─ NO → Continue to next phase (skip retries)
   └─ YES:
      prior_retry_count < 3?
      ├─ YES → RETRY PATH (attempt X/3)
      │  ├─ Inject feedback
      │  ├─ Enqueue run
      │  └─ Return (run re-starts)
      │
      └─ NO → INVESTIGATOR PATH (retries exhausted)
         ├─ Create InvestigatorAgent
         ├─ Analyze 3 failed attempts
         ├─ Classify root cause
         ├─ Generate chat message
         ├─ Make routing decision
         ├─ Route: phase_2 / phase_3 / escalate
         └─ Return (continue or re-queue)
```

---

## 🎯 For Each Test Case

### Test: First Attempt Fails
```
prior_retry_count = 0
0 < 3? YES → RETRY (Attempt 1/3)
  └─ Inject feedback → enqueue_run_execution()
```

### Test: Second Attempt Fails  
```
prior_retry_count = 1
1 < 3? YES → RETRY (Attempt 2/3)
  └─ Inject feedback → enqueue_run_execution()
```

### Test: Third Attempt Fails
```
prior_retry_count = 2
2 < 3? YES → RETRY (Attempt 3/3)
  └─ Inject feedback → enqueue_run_execution()
```

### Test: Fourth Attempt (after 3 retries)
```
prior_retry_count = 3
3 < 3? NO → INVESTIGATOR AGENT
  ├─ Query database (find 3 retry_requested events)
  ├─ Run 4-node analysis
  ├─ Route to phase_2 / phase_3 / escalate
  └─ Return (finish or re-queue)
```

---

## 🚨 What Could Go Wrong

### Scenario A: Investigator Never Triggered
**Cause**: `prior_retry_count` never reaches 3
**Check**:
```bash
grep "prior_retry_count:" logs/app.log | tail -10
```
**Fix**: Ensure Phase 4 is being called each time

---

### Scenario B: No Retry Happens
**Cause**: `hard_gate_enabled` is False OR `prior_retry_count >= 3` on first run
**Check**:
```bash
grep "hard_gate_enabled:" logs/app.log
grep "prior_retry_count:" logs/app.log | head -1
```
**Fix**: Check settings.json for hard_gate_enabled

---

### Scenario C: Investigator Created But Doesn't Analyze
**Cause**: InvestigatorAgent().investigate_and_decide() failed
**Check**:
```bash
grep "\[INVESTIGATOR\].*ERROR\|Exception" logs/app.log
```
**Fix**: Check error message in logs

---

### Scenario D: Chat Message Not Saved
**Cause**: Conversation not found
**Check**:
```bash
grep "Found conversation\|ERROR.*conversation" logs/app.log
```
**Fix**: Verify conversation_id is set

---

## ✅ How to Trace a Single Run

```bash
# 1. Find your run ID
RUNID="run_abc123"

# 2. See entire Phase 4 for this run
grep "$RUNID" logs/app.log | grep -E "\[PHASE-EVALUATE\]|\[INVESTIGATOR"

# 3. See retry count progression
grep "$RUNID" logs/app.log | grep "prior_retry_count"

# 4. See if investigator triggered
grep "$RUNID" logs/app.log | grep "RETRIES EXHAUSTED"

# 5. See all nodes executed
grep "$RUNID" logs/app.log | grep "\[INVESTIGATOR-NODE\]"

# 6. See final routing
grep "$RUNID" logs/app.log | grep "ROUTING →"
```

---

## 🎓 Summary

**The code flow is:**

1. **Evaluate** quality checks (pass or fail?)
2. **If fail:**
   - **If retry count < 3:** Retry with feedback (go back to Phase 3)
   - **If retry count >= 3:** Trigger investigator agent
3. **Investigator:**
   - Analyze all 3 failed attempts
   - Classify root cause (5 categories)
   - Generate chat explanation
   - Route (phase_2, phase_3, escalate)
4. **Persist** chat message to conversation
5. **Return** (continue or re-queue)

**If you see all these steps in logs → Everything is working!** ✅
