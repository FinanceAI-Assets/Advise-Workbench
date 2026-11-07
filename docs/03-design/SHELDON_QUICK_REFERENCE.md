# Sheldon Conversation → Document Generation: Quick Reference

**One-page cheat sheet for developers**

---

## The 5-Phase Flow

### Phase 1: User Converses with Sheldon
```
File: src/app/api/projects/conversation.py
Table: ConversationMessage (role, content, metadata_json)
State: ConversationState (FSM, slots, deliverable, pending_questions)
Location: workspace/{project_id}/conversation_state/{conversation_id}.json
```
- User messages create ConversationMessage records
- Sheldon responds with personality (AgentPersonality from src/agents/conversation/agent_personality.py)
- State transitions: new → exploring → discovery → storyline_building → slide_negotiation → structure_agreed → ready_to_plan → plan_proposed → confirming → done

### Phase 2: Plan Confirmation & Digest Building
```
File: src/memory/short_term/conversation_digest.py
Function: build_conversation_digest_for_run_with_trace()
Output: Compacted conversation string (char_cap: 10000, message_limit: 40)
```
- Extract plan metadata from ConversationMessage.metadata_json:
  - `instruction`, `template_output_types`, `discovery`, `decision_answers`, `strategy_dossier`, `selected_strategy`
- Build digest (newest → oldest messages, then reverse to oldest → newest)
- Create Run record with `plan_json` = serialized plan_payload

### Phase 3: Coordinator Planning
```
File: src/agents/supervisor_agent.py (Coordinator class)
Input: CoordinatorRunInput (src/app/schemas/coordinator_run.py)
Output: ExecutionPlan with ordered_output_types, rationale, per_output_notes
```
**Variables passed:**
- `raw_text` = conversation messages concatenated
- `user_instruction` = cleaned instruction
- `plan_payload` = all discovery/decisions/strategies/selected_strategy
- `requested_outputs` = template_output_types
- `conversation_id` = link back to conversation

**Coordinator builds state:**
```python
AdviseWorkbenchState = {
    "conversation_digest": str,          # Compacted messages
    "plan_payload": dict,                # All discovery/decisions
    "user_instruction": str,
    "user_intent_original": str,
    "process_model": dict,               # Retrieved from wiki
    "branding_context": BrandingContext,
    "content_enrichment": ContentEnrichment,  # Audience/risk/value
    "skill_instructions_by_output": dict,
    # ... more fields
}
```

### Phase 4: Agent Execution (Sequential per ExecutionPlan)
```
File: src/agents/base_agent.py
Function: build_agent_context(state: AdviseWorkbenchState, output_type: str) → AgentContext
```

**For each output_type in execution_plan.ordered_output_types:**

```python
AgentContext {
    # All get conversation context:
    conversation_digest: str,        # Full conversation digest
    plan_payload: dict,              # All plan details
    user_instruction: str,
    user_intent_original: str,
    
    # Output-specific:
    output_type: str,                # "pptx", "docx", "xlsx", etc.
    skill_instructions_by_output[output_type]: str,
    plan_payload["content_skill_targets"].get(output_type): str,  # "sop_v2", "raci_v2"
    
    # Shared across all agents:
    process_model: dict,
    branding: BrandingContext,
    content_enrichment: ContentEnrichment,
    
    # From earlier agents:
    prior_artifacts_excerpt: str,    # Previous outputs
}
```

**Agent loop:**
```
run_subagent_tool_loop(context) {
  1. Initialize with system prompt + skill instructions
  2. Tool use loop (max rounds = subagent_tool_max_rounds):
     - retrieve_context(query) → wiki/memory
     - web_search(query) → Tavily
     - other artifact tools
  3. Extract final markdown/data
  4. Return AgentOutput { updates: {output_key: content}, tool_trace: [...] }
}
```

### Phase 5: Finalization
```
Files: src/core/storage.py (save_run_artifacts)
Format: markdown → PPTX/DOCX/XLSX generators → Binary files
Location: workspace/{project_id}/runs/{run_id}/{output.pptx|output.docx|...}
```
- QA loop validates quality
- Visual QA checks
- Format generators create binary files
- RunEvent("deliverable_generated") emitted

---

## Critical Variable Chains

### Conversation → Run
```
ConversationMessage.metadata_json {
    plan_confirmed: true,
    plan_hash: str,
    instruction: str,
    template_output_types: list[str],
    discovery: dict,
    decision_answers: dict,
    strategy_dossier: dict,
    selected_strategy: dict,
    ...
}
    ↓ (extract & build)
plan_payload = {
    instruction: str,
    output_types: list[str],
    content_skill_targets: dict[str, str],  # {"docx": "sop_v2", "xlsx": "raci_v2"}
    discovery: dict,
    decision_answers: dict,
    strategy_dossier: dict,
    selected_strategy: dict,
    ...
}
    ↓
Run {
    plan_json: json.dumps(plan_payload),
    conversation_id: str,
    ...
}
```

### Run → AdviseWorkbenchState
```
Run.plan_json (deserialized)
    ↓
CoordinatorRunInput {
    raw_text: str,
    user_instruction: str,
    plan_payload: dict,
    requested_outputs: list[str],
    ...
}
    ↓
AdviseWorkbenchState["plan_payload"] = plan_payload (full dict)
AdviseWorkbenchState["conversation_digest"] = build_conversation_digest_for_run(...)
AdviseWorkbenchState["user_instruction"] = cleaned instruction
AdviseWorkbenchState["user_intent_original"] = immutable original intent
AdviseWorkbenchState["process_model"] = load from wiki
AdviseWorkbenchState["branding_context"] = load from project
AdviseWorkbenchState["content_enrichment"] = ContentEnrichmentEngine.analyze(...)
```

### State → AgentContext (Per Output)
```
AgentContext = build_agent_context(state, output_type="docx")
    ↓ Copies:
    - conversation_digest (FULL)
    - plan_payload (FULL)
    - user_instruction
    - user_intent_original
    - plan_payload["content_skill_targets"].get(output_type)  # "sop_v2"
    - process_model (shared reference)
    - branding (shared reference)
    - content_enrichment (shared reference)
    - prior_artifacts_excerpt (from state["docx_markdown"] + state["narrative_md"] etc.)
    - skill_instructions_by_output[output_type]
```

### Agent Output → Final State
```
AgentOutput {
    updates: {
        "docx_markdown": "# SOP\n...",  # or other output_key per type
        "docx_artifacts": {...}
    },
    tool_trace: [
        {tool: "retrieve_context", input: {...}, output: {...}, duration_ms: 123},
        ...
    ]
}
    ↓ merge_agent_output(state, output)
AdviseWorkbenchState["docx_markdown"] = generated markdown
    ↓
format generators (docx_generator.generate_docx(markdown, branding, ...))
    ↓
Binary file written to disk
```

---

## Key Files & Functions

| Purpose | File | Function/Class |
|---------|------|---|
| Conversation Chat API | `src/app/api/projects/conversation.py` | `post_conversation_turn()`, `confirm_project_conversation_plan()`, `_execute_plan_now()` |
| Sheldon Personality | `src/agents/conversation/agent_personality.py` | `AgentPersonality` class |
| Conversation State FSM | `src/memory/short_term/conversation_state.py` | `ConversationState`, `load_state()`, `save_state()` |
| Digest Builder | `src/memory/short_term/conversation_digest.py` | `build_conversation_digest_for_run_with_trace()` |
| Coordinator Orchestration | `src/agents/supervisor_agent.py` | `Coordinator` class |
| Planning Phase | `src/agents/planner_agent.py` | `CoordinatorPlanning` mixin |
| Execution Phase | `src/agents/supervisor_execution.py` | `CoordinatorExecution` mixin |
| Agent Context Builder | `src/agents/base_agent.py` | `build_agent_context()`, `AgentContext`, `AgentOutput` |
| PPTX Agent | `src/agents/specialists/document_agents.py` | `run_pptx_agent()` |
| DOCX Agent | `src/agents/specialists/document_agents.py` | `run_docx_agent()` |
| XLSX Agent | `src/agents/specialists/document_agents.py` | `run_xlsx_agent()` |
| Quality Loop | `src/evaluation/qa.py` | `QAAgentLoop` |
| File Generation | `src/core/storage.py` | `save_run_artifacts()` |
| Run Orchestration | `src/workflows/orchestrator.py` | `run_worker()`, `enqueue_run_execution()` |

---

## Configuration Hotspots

```python
# Conversation Digest (src/core/config.py)
conversation_source_freshness_ttl_seconds = 259200  # 3 days
conversation_digest_exclude_stale_sources = True
conversation_digest_char_cap = 10000
conversation_digest_message_limit = 40

# Coordinator (src/core/config.py)
coordinator_llm_planning_enabled = True
anthropic_thinking_budget_tokens = 10000
subagent_tool_max_rounds = 10
subagent_tool_max_tokens = 200000

# QA (src/evaluation/qa.py)
qa_threshold = 0.8
max_qa_loops = 2

# Guardrails (src/guardrails/permission_pipeline.py)
dpdp_enabled = True
policy_enforcement_mode = "enforce"  # or "dry_run"

# Storage (src/core/storage.py)
workspace_root = "workspace/"  # relative to repo root
```

---

## Common Debug Workflows

### Debug: Conversation Not Converting to Run
1. Check ConversationMessage has `plan_confirmed=true` in metadata_json
2. Verify ConversationState FSM is in "plan_proposed" or "confirming"
3. Check permission pipeline didn't block (look for `plan_blocked` status)
4. Verify `_build_plan_payload()` extracted all required fields

### Debug: Agent Not Receiving Correct Context
1. Check `conversation_digest` is populated: `state.get("conversation_digest")`
2. Verify `plan_payload` has discovery fields: `state.get("plan_payload")["discovery"]`
3. Confirm `content_skill_targets` matches output_type:
   - For docx + SOP: should be `{"docx": "sop_v2"}`
4. Check skill instructions loaded: `state.get("skill_instructions_by_output")[output_type]`

### Debug: Document Quality Issues
1. Check QA evaluation result: look for `qa_evaluation` RunEvent
2. Check remediation loop executed: `qa_loop_count` in state
3. Verify fallback strategy applied if max loops exceeded
4. Check visual QA report: `visual_qa_report` in state

### Debug: Missing Prior Context in Agent
1. Verify `prior_artifacts_excerpt` populated from earlier agents:
   - PPTX should add to `state["narrative_md"]` or similar
   - DOCX agent should see prior PPTX in `prior_artifacts_excerpt`
2. Check ordering (earlier agents need lower complexity weights)

---

## Testing Checklist

When adding new features to conversation or agent flow:

- [ ] ConversationMessage created with correct role (user/assistant)
- [ ] ConversationState FSM transitions validated
- [ ] Conversation digest builds without errors
- [ ] Plan metadata extracted correctly from ConversationMessage
- [ ] Plan payload all fields populated (discovery, decisions, strategy)
- [ ] Run created with conversation_id link
- [ ] CoordinatorRunInput all required fields present
- [ ] AdviseWorkbenchState initialized with conversation_digest
- [ ] AgentContext has conversation_digest (check via assertion)
- [ ] AgentContext has plan_payload (check all key fields)
- [ ] Agent receives correct skill_instructions_by_output
- [ ] Agent receives correct content_skill_targets (e.g., "sop_v2")
- [ ] AgentOutput.updates has correct output_key (not generic)
- [ ] Output file generated and saved to correct path
- [ ] RunEvent emitted for deliverable_generated
- [ ] UI shows deliverable ready for download

---

## Troubleshooting Variable Loss

| Variable | Where It Comes From | Where It Goes | Common Loss Causes |
|----------|---|---|---|
| `conversation_digest` | Built from ConversationMessage records | AdviseWorkbenchState, all AgentContexts | Stale message filters excluding all records |
| `plan_payload` | ConversationMessage.metadata_json | CoordinatorRunInput, AdviseWorkbenchState | Serialization error in JSON, missing fields |
| `discovery` | User answers in slots | plan_payload["discovery"] → AgentContext | Slots not saved to ConversationState |
| `content_skill_targets` | plan_payload (explicit or inferred) | Coordinator → Agent via skill instructions | Skill ID typo, not matching registered skills |
| `selected_strategy` | User choice in slide negotiation | plan_payload["selected_strategy"] | Decision tree UI bug, not saved to metadata |
| `prior_artifacts_excerpt` | Earlier agent outputs in state | AgentContext for later agents | Agent output key doesn't match expected format |

---

## Key Insight: Context is Additive

As flow progresses, **context accumulates but never shrinks**:
1. Conversation → full message history
2. Digest → compacted but full conversation
3. Plan payload → adds discovery/decisions
4. AdviseWorkbenchState → adds retrieved context, enrichment, branding
5. AgentContext → subsets of state relevant to output_type
6. Final state → all agent outputs merged

If an agent lacks context, look **upstream** at earlier steps, not downstream.

---

## Quick Audit Trail Search

Find what happened to a specific conversation:

```sql
-- Find run(s) from conversation
SELECT * FROM runs WHERE conversation_id = '{conversation_id}' ORDER BY created_at DESC;

-- Get all events for a run
SELECT * FROM run_events WHERE run_id = '{run_id}' ORDER BY ts_ms;

-- Find plans
SELECT payload FROM run_events WHERE run_id = '{run_id}' AND event_type = 'coordinator_plan';

-- Find agent work
SELECT payload FROM run_events WHERE run_id = '{run_id}' AND event_type = 'agent_tool_round' AND payload LIKE '%"agent":"docx"%';

-- Find errors
SELECT * FROM run_events WHERE run_id = '{run_id}' AND payload LIKE '%error%' OR payload LIKE '%failed%';
```
