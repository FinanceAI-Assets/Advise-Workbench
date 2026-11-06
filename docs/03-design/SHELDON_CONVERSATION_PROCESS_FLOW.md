# Sheldon Conversation to Document Generation Process Flow

**Complete Technical Documentation of Data Flow and Variable Passing**

---

## Table of Contents

1. [Process Overview](#process-overview)
2. [Phase 1: Sheldon Conversation System](#phase-1-sheldon-conversation-system)
3. [Phase 2: Conversation to Run Transformation](#phase-2-conversation-to-run-transformation)
4. [Phase 3: Coordinator Planning & Execution](#phase-3-coordinator-planning--execution)
5. [Phase 4: Agent Execution & Document Generation](#phase-4-agent-execution--document-generation)
6. [Key Data Structures](#key-data-structures)
7. [Variable Passing Between Components](#variable-passing-between-components)

---

## Process Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHELDON CONVERSATION SYSTEM                  │
│  (Agent Personality: Energetic Execution Partner)               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ↓
          [PHASE 1: Conversation Turns]
          User & Sheldon discuss deliverables
          Messages saved to ConversationMessage table
                     │
                     ↓
          [PHASE 2: Conversation Digest Builder]
          Latest conversation messages compacted
          ConversationState maintained per-conversation
                     │
                     ↓
          [PHASE 3: Plan Confirmation & Run Creation]
          User approves plan → Create Run record
          Conversation passed to Coordinator
                     │
                     ↓
          [PHASE 4: Coordinator Orchestration]
          Plan → Task Board → Sub-agents in order
          Each agent receives AgentContext
                     │
                     ↓
     ┌───────────────┼───────────────┐
     ↓               ↓               ↓
  DOCX Agent     PPTX Agent    XLSX Agent    ...
  (Narrative,   (Slides,       (RACI,
   SOP, BRD)    Decks)         Tables)
     │               │               │
     └───────────────┼───────────────┘
                     ↓
          [Final Deliverables]
          DOCX/PPTX/XLSX/PDF files ready
```

---

## Phase 1: Sheldon Conversation System

### 1.1 Sheldon Agent Personality

**File:** `src/agents/conversation/agent_personality.py`

Sheldon is the **energetic execution partner** with:
- **Name:** "Sheldon"
- **Role:** "Your execution partner"
- **Catchphrases:** Context-specific messages (start_planning, confirming_plan, starting_execution, etc.)
- **Progress Markers:** Visual indicators (→, ✓, 🎯, ✨, ⚠️)
- **Insight Templates:** Strategic observation patterns

**Key Methods:**
```python
AgentPersonality.get_catchphrase(context: str) → str
AgentPersonality.CELEBRATION_EMOJI → list of emoji strings
AgentPersonality.PROGRESS_MARKERS → dict of phase-to-marker mapping
```

### 1.2 Conversation Message Flow

**File:** `src/app/api/projects/conversation.py`

**HTTP Endpoints:**
- `POST /projects/{project_id}/conversations/{conversation_id}/turns`
  - User sends message to Sheldon
  - Sheldon responds with guidance, questions, or confirmations

**Message Types:**
1. **User Messages** - Instructions, answers, confirmations
2. **Assistant Messages** - Sheldon's responses, catchphrases, options
3. **Plan Confirmations** - User approves execution plan

### 1.3 Conversation State Management

**File:** `src/memory/short_term/conversation_state.py`

```python
@dataclass
class ConversationState:
    schema_version: int              # Current: 2
    state: str                       # FSM state (see below)
    slots: dict[str, Any]            # User answers to discovery questions
    deliverable: dict[str, Any]      # Current deliverable being discussed
    last_router: dict[str, Any]      # Last routing decision (intent, confidence)
    pending_questions: list[str]     # Questions Sheldon should ask next
    surfaced_wiki_refs: list[str]    # References from knowledge base
    # [DEPRECATED: history_summary removed - consolidated into conversation_summary]
    # history_summary: str             # Compact summary for context
    conversation_summary: str        # Unified summary: rolling (inline every 6 msgs) + session (idle/completion)
```

**FSM States:**
```
new → exploring → discovery → storyline_building → slide_negotiation 
  → structure_agreed → ready_to_plan → plan_proposed → confirming → done
```

**Persistence:**
- Location: `workspace/{project_id}/conversation_state/{conversation_id}.json`
- Loaded/saved at each turn
- Survives across requests and sessions

### 1.4 Conversation Message Storage

**Database Model:** `ConversationMessage` (in `src/core/db/models.py`)

```python
class ConversationMessage(Base):
    id: str                          # UUID primary key
    conversation_id: str             # FK to Conversation
    role: str                        # "user" or "assistant"
    content: str                     # Message text
    metadata_json: str               # Plan metadata, decisions, etc.
    created_at: datetime             # Timestamp
```

**Example Metadata for Plan Confirmation:**
```json
{
    "plan_confirmed": true,
    "plan_hash": "<sha256>",
    "instruction": "Create a RACI and SOP for the new onboarding process",
    "template_output_types": ["xlsx", "docx"],
    "custom_output_types": [],
    "output_type_representations": {"docx": "Standard Word format"},
    "content_skill_targets": {"docx": "sop_v2"},
    "discovery": { /* discovery answers */ },
    "decision_answers": { /* decision tree answers */ },
    "strategy_dossier": { /* strategy options */ },
    "selected_strategy": { /* user's chosen strategy */ },
    "deck_outline_preview": { /* agreed slide structure */ },
    "document_outline_preview": { /* agreed document structure */ },
    "wiki_context_refs": [ /* knowledge base references */ ]
}
```

---

## Phase 2: Conversation to Run Transformation

### 2.1 Conversation Digest Building

**File:** `src/memory/short_term/conversation_digest.py`

**Purpose:** Compact conversation history for coordinator and sub-agents

**Function:**
```python
def build_conversation_digest_for_run_with_trace(
    *,
    session: Session,
    project_id: str,
    conversation_id: str,
    char_cap: int = 10000,           # Total character limit
    message_limit: int = 40,         # Max messages to include
    per_message_chars: int = 600     # Chars per message
) -> tuple[str, CompactionTrace]
```

**Process:**
1. Query `ConversationMessage` records (newest → oldest, then reversed to oldest → newest)
2. Filter stale messages (configurable TTL in `conversation_source_freshness_ttl_seconds`)
3. Redact emails (PII protection)
4. Extract metadata markers:
   - Plan hash indicators
   - Failure hints (fail, error, issue, blocked, regression)
   - Non-negotiable constraints (must, should not, cannot)
5. Compact using `TieredCompactor` to respect token budgets
6. Return: digest string + trace metadata

**Output Example:**
```
USER (2 hours ago): Create a process map for the new vendor onboarding workflow

ASSISTANT (1:45 ago): Great! I'm mapping this out. [catchphrase] 🎯

USER: Should cover approval steps and risk assessment

ASSISTANT: Blueprint locked in! 📋 Ready to start planning your process map and SOP?

USER (CONFIRMED): Yes, let's generate both
```

### 2.2 Plan Payload Construction

**File:** `src/app/api/runs.py`, function `_build_plan_payload()`

**Inputs from Conversation:**
- `instruction` - User's final deliverable instruction
- `output_types` - Requested formats (pptx, docx, xlsx, pdf, process_map, etc.)
- `custom_output_types` - User-defined deliverable types
- `output_type_representations` - Format specifications per output
- `content_skill_targets` - Deliverable-specific content skills (e.g., "sop_v2" for SOP)
- `regeneration_directive` - Special handling instructions (e.g., "make more visual")

**Plan Payload Structure:**
```python
plan_payload = {
    "instruction": str,
    "output_types": list[str],
    "custom_output_types": list[str],
    "output_type_representations": dict[str, str],
    "content_skill_targets": dict[str, str],
    "regeneration_directive": str,
    "discovery": dict,                    # Discovery questions answered
    "decision_answers": dict,             # Decision tree selections
    "strategy_dossier": dict,             # Strategy options evaluated
    "selected_strategy": dict,            # Chosen strategy
    "deck_outline_preview": dict,         # Agreed slide structure (if applicable)
    "document_outline_preview": dict      # Agreed document structure (if applicable)
}
```

### 2.3 Run Creation & Queueing

**File:** `src/workflows/orchestrator.py`

**Flow:**
```python
# In _execute_plan_now() endpoint handler:

1. Extract plan metadata from latest ConversationMessage
2. Build plan_payload (includes all discovery, decisions, strategies)
3. Run permission pipeline (guardrails, policy evaluation, ADD-001 checks)
4. Create Run record:
   - status: "approved" (after human confirmation) or "plan_blocked" (if guardrails reject)
   - plan_json: serialized plan_payload
   - conversation_id: linked back to conversation
   - project_id, user_id, run_id
5. Emit RunEvent(type="run_created", payload=...)
6. Enqueue to RunQueue → run_worker picks it up
```

---

## Phase 3: Coordinator Planning & Execution

### 3.1 Coordinator Initialization

**File:** `src/agents/supervisor_agent.py`

**Class:** `Coordinator` (inherits from `CoordinatorExecution`, `CoordinatorPlanning`)

**Initialization:**
```python
class Coordinator:
    def __init__(self):
        self.context_engine = TieredContextEngine()          # Wiki + memory retrieval
        self.qa_loop = QAAgentLoop()                         # Quality assurance
        self.guardrails = GuardrailPipeline()                # Policy/safety checks
        self.dpdp = DPDPService()                            # Data protection
        self.enrichment_engine = ContentEnrichmentEngine()   # Audience, risk, value analysis
        self.quality_framework = UnifiedQualityFramework()   # Quality standards
        self.skill_registry = self._load_skill_registry()    # Available content skills
        self.output_requirements = self._load_output_requirements()  # Format specs
```

### 3.2 Coordinator Input Contract

**File:** `src/app/schemas/coordinator_run.py`

```python
@dataclass
class CoordinatorRunInput:
    raw_text: str                                    # Full conversation text
    user_instruction: str                           # Cleaned user instruction
    requested_outputs: list[str]                    # Requested format types
    project_id: str                                 # Project identifier
    run_id: str                                     # Run identifier
    plan_payload: dict[str, Any]                    # Complete plan from conversation
    dpdp_flags: dict[str, Any]                      # Data protection settings
    qa_threshold: float = 0.8                       # Quality gate threshold
    max_qa_loops: int = 2                           # Max remediation attempts
    output_type_representations: dict[str, str]    # Format specifications
    user_id: str | None = None                      # User making request
```

### 3.3 Execution Plan Generation

**File:** `src/agents/supervisor_agent.py`

**Coordinator Planning Phase:**

1. **LLM Planning (if enabled):**
   - Input: `user_instruction`, `requested_outputs`, skill registry (trimmed)
   - Output: `ExecutionPlan` with:
     - `ordered_output_types: list[str]` - LLM-determined order (pptx before docx, etc.)
     - `rationale: str` - Reasoning for order
     - `per_output_notes: dict[str, str]` - Agent-specific guidance
     - `execution_milestones: list[dict]` - Key checkpoints
     - `thinking_excerpt: str` - Extended reasoning (if available)

2. **Fallback Ordering:**
   - If LLM planning disabled or fails:
     - Use complexity weights: pptx(5) > xlsx(4) > docx(3) > narrative(2) > process_map(1)
     - Apply canonical ordering based on dependencies

3. **Merge with Ceiling:**
   - User-requested outputs = ceiling
   - Planned order = what fits within ceiling
   - Result: final execution order

```python
ExecutionPlan:
    ordered_output_types: ["pptx", "docx", "xlsx"]
    rationale: "Start with deck for executive summary, then supporting docs"
    per_output_notes: {
        "pptx": "Emphasize strategic timeline and ROI",
        "docx": "Detail SOP with approval gates"
    }
    execution_milestones: [
        {"output_type": "pptx", "label": "Executive deck ready for review"}
    ]
    used_llm_plan: true
```

### 3.4 State Machine & Task Board

**File:** `src/agents/supervisor_state.py`

**CoordinatorStateManager:**
```python
@dataclass
class CoordinatorStateManager:
    run_id: str
    project_id: str
    current_state: str = "init"           # FSM state
    
    # Task Board: one task per output_type
    task_board: dict[str, dict] = {
        "pptx": {
            "status": "queued",           # queued → running → completed/failed
            "assigned_teammate": None,
            "output_type": "pptx",
            "created_at": datetime,
            "started_at": None,
            "completed_at": None
        },
        "docx": {...},
        "xlsx": {...}
    }
    
    execution_plan: ExecutionPlanSnapshot  # Saved LLM plan
    failure_context: dict[str, Any]        # Error details if retry needed
    replanning_count: int = 0              # How many times replanned
```

**FSM Transitions:**
```
init → planning → task_assignment → execution → finalize → done
                                       ↑              │
                                       └──replan_on_failure
```

---

## Phase 4: Agent Execution & Document Generation

### 4.1 Agent Context Building

**File:** `src/agents/base_agent.py`

**Function:** `build_agent_context(state: AdviseWorkbenchState, output_type: str) → AgentContext`

```python
@dataclass
class AgentContext:
    # Immutable request context
    output_type: str                                    # "pptx", "docx", etc.
    project_id: str
    run_id: str
    user_id: str
    
    # Conversation-derived context
    raw_text: str                                       # Original user input
    user_instruction: str                              # Cleaned instruction
    user_intent_original: str                          # Immutable intent
    conversation_digest: str                           # Compacted conversation
    
    # Assembled content
    assembled_context: str                             # Project context, wiki refs
    process_model: dict[str, Any]                      # Process definitions
    retrieval_excerpt: str                             # Retrieved knowledge base content
    prior_artifacts_excerpt: str                       # Previous DOCX/PPTX/PDF excerpts
    
    # Specifications
    output_type_representations: dict[str, Any]        # Format requirements
    skill_instructions_by_output: dict[str, str]       # Per-output skill guidance
    skill_card: dict[str, Any]                         # Skill metadata
    plan_payload: dict[str, Any]                       # Complete plan from conversation
    
    # Enrichment
    enrichment: ContentEnrichment | None               # Audience, risk, value analysis
    branding: BrandingContext | None                   # Brand guidelines
    deliverable_metadata: dict | None                  # Output-specific metadata
    deliverable_archetype: str                         # "process_doc", "narrative", etc.
    
    # Optional
    compaction_snapshot: dict | None                   # Token budget tracking
    emit_event: Callable | None                        # Callback to emit RunEvent
    swarm_teammate_id: str | None                      # For subprocess execution
```

### 4.2 Sub-Agent Tool Loop

**File:** `src/agents/tool_agent.py`, function `run_subagent_tool_loop()`

**Process per Agent:**
```python
# For output_type = "docx" (example):

1. Create AgentContext with:
   - User instruction: "Create an SOP for new vendor onboarding"
   - Conversation digest: Compacted messages from Sheldon
   - Skill targets: {"docx": "sop_v2"}
   - Plan payload: Complete discovery/decisions/strategies
   - Retrieved context: Wiki articles on vendor process
   - Prior excerpts: Any existing SOP sections from earlier generation

2. Initialize sub-agent prompt:
   - System instructions for SOP generation
   - Skill instructions (from skill_card with id=sop_v2)
   - Audience hints (executives, operational, mixed)
   - Risk focus: Key risks to address
   - Value emphasis: Drivers to emphasize
   - Conversation context: What user discussed with Sheldon

3. Tool loop (max rounds = subagent_tool_max_rounds):
   - Agent has access to tools:
     * retrieve_context(query) → wiki + memory
     * web_search(query) → Tavily API (if enabled)
     * artifact_tools: fetch/modify markdown
   - Each round tracks: tool_name, inputs, outputs, duration
   - Continue until agent produces final markdown or reaches token limit

4. Extract final output:
   - Extract markdown from final message
   - Validate against output schema
   - Return AgentOutput with updates dict

# Output for docx_agent returns:
AgentOutput.updates = {
    "docx_markdown": """# Vendor Onboarding SOP
    
    ## Phase 1: Initial Contact
    ...
    """,
    "docx_artifacts": {...}  # optional
}
AgentOutput.tool_trace = [
    {"tool": "retrieve_context", "input": {"query": "vendor approval"}, "output": "..."},
    ...
]
```

### 4.3 Multi-Agent Execution

**File:** `src/agents/supervisor_execution.py`

**Sequential Execution (Following Execution Plan):**

```python
# For each output_type in execution_plan.ordered_output_types:

for output_type in execution_plan.ordered_output_types:
    # Build context specific to this output
    agent_context = build_agent_context(state, output_type)
    
    # Call appropriate agent
    agent_fn = _OUTPUT_AGENTS[output_type]  # run_pptx_agent, run_docx_agent, etc.
    
    agent_output = agent_fn(
        context=agent_context,
        emit_event=emit_run_event_callback
    )
    
    # Merge results into shared state
    merge_agent_output(state, agent_output)
    
    # Emit event for UI
    emit_run_event(
        type="agent_tool_round",
        payload={
            "agent": output_type,
            "status": "completed",
            "tool_trace": agent_output.tool_trace,
            "output_keys": list(agent_output.updates.keys())
        }
    )
```

### 4.4 Individual Agent Functions

**Available Agents:** `src/agents/specialists/document_agents.py`

```python
async def run_pptx_agent(context: AgentContext) -> AgentOutput:
    """Generates PPTX slides with narrative and visuals"""
    # Returns: pptx_slides (list of slide dicts)
    
async def run_docx_agent(context: AgentContext) -> AgentOutput:
    """Generates Word documents (SOP, narrative, BRD)"""
    # Returns: docx_markdown
    
async def run_xlsx_agent(context: AgentContext) -> AgentOutput:
    """Generates Excel spreadsheets (RACI, tables)"""
    # Returns: xlsx_markdown, xlsx_cells
    
async def run_pdf_agent(context: AgentContext) -> AgentOutput:
    """Generates PDF reports"""
    # Returns: pdf_markdown
    
async def run_sop_agent(context: AgentContext) -> AgentOutput:
    """Specialized SOP generation (wrapper around docx with sop_v2 skill)"""
    # Returns: docx_markdown (SOP format)
    
async def run_narrative_agent(context: AgentContext) -> AgentOutput:
    """Specialized narrative/executive summary"""
    # Returns: narrative_md
    
async def run_drawio_agent(context: AgentContext) -> AgentOutput:
    """Generates process maps (DrawIO/Mermaid)"""
    # Returns: drawio_xml, process_map_mermaid
```

### 4.5 Quality Assurance Gate

**File:** `src/evaluation/qa.py`

**Post-Generation QA Loop:**

```python
# After all agents complete:

qa_loop = QAAgentLoop()
qa_results = qa_loop.evaluate_outputs(
    state=final_state,
    qa_threshold=0.8,
    max_loops=2
)

# If quality_score < threshold:
#   Generate remediation prompt
#   Re-run failing agents with guidance
#   Repeat up to max_loops times
#
# If still fails after max_loops:
#   Apply fallback strategy (simplified template, etc.)
#   Emit warning event
#   Continue to finalization
```

### 4.6 Document File Generation

**File:** `src/core/storage.py`, function `save_run_artifacts()`

**Format-Specific Generation:**

```python
# From markdown/intermediate formats → final files

if "pptx_slides" in state:
    # PPTX Generation: slide dicts → python-pptx → .pptx file
    from src.deliverables.pptx_generator import generate_pptx
    pptx_bytes = generate_pptx(
        slides=state["pptx_slides"],
        branding=state["branding_context"],
        metadata=state["pptx_metadata"]
    )
    save_path = workspace_path(project_id) / "runs" / run_id / "output.pptx"
    save_path.write_bytes(pptx_bytes)
    emit_run_event("deliverable_generated", {"type": "pptx", "path": save_path})

if "docx_markdown" in state:
    # DOCX Generation: markdown → pandoc → python-docx → .docx file
    from src.deliverables.docx_generator import generate_docx
    docx_bytes = generate_docx(
        markdown=state["docx_markdown"],
        branding=state["branding_context"],
        template=state.get("docx_template")
    )
    save_path = workspace_path(project_id) / "runs" / run_id / "output.docx"
    save_path.write_bytes(docx_bytes)

if "xlsx_cells" in state:
    # XLSX Generation: cell data → openpyxl → .xlsx file
    from src.deliverables.xlsx_generator import generate_xlsx
    xlsx_bytes = generate_xlsx(
        cells=state["xlsx_cells"],
        styles=state.get("xlsx_styles", {})
    )
    save_path = workspace_path(project_id) / "runs" / run_id / "output.xlsx"
    save_path.write_bytes(xlsx_bytes)
```

**Output Storage:**
```
workspace/
  {project_id}/
    runs/
      {run_id}/
        output.pptx
        output.docx
        output.xlsx
        output.pdf
        process_map.drawio
        run_state.json         # Final state snapshot
        run_metadata.json      # Audit trail
```

---

## Key Data Structures

### AdviseWorkbenchState

**Type:** `dict[str, Any]` (internal working state during run execution)

**Key Fields:**
```python
{
    # Request metadata
    "project_id": str,
    "run_id": str,
    "user_id": str,
    
    # Conversation inputs
    "raw_text": str,                                    # Full conversation
    "user_instruction": str,                          # User's deliverable request
    "user_intent_original": str,                      # Cleaned intent (immutable)
    "conversation_digest": str,                       # Compacted conversation
    
    # Plan & execution
    "plan_payload": dict,                             # Complete plan from conversation
    "requested_outputs": list[str],                   # User-requested formats
    "execution_plan": ExecutionPlan,                  # LLM-determined order
    "current_phase": str,                             # "planning", "execution", etc.
    
    # Assembled context
    "assembled_context": str,                         # Project context
    "planner_retrieval_excerpt": str,                 # Retrieved wiki content
    "process_model": dict,                            # Process definitions
    
    # Specification
    "skill_card": dict,                               # Skill metadata
    "skill_instructions_by_output": dict[str, str],  # Per-output guidance
    "output_type_representations": dict[str, str],    # Format specs
    
    # Enrichment
    "content_enrichment": ContentEnrichment,          # Audience/risk/value analysis
    "branding_context": BrandingContext,              # Brand guidelines
    
    # Generated outputs (accumulated)
    "pptx_slides": list[dict],                        # PPTX slide dicts
    "docx_markdown": str,                             # DOCX markdown
    "xlsx_markdown": str,                             # XLSX markdown
    "xlsx_cells": dict,                               # XLSX cell data
    "pdf_markdown": str,                              # PDF markdown
    "narrative_md": str,                              # Narrative/executive summary
    "sop_markdown": str,                              # SOP (variant of docx)
    "drawio_xml": str,                                # Process map DrawIO
    "process_map_mermaid": str,                       # Process map Mermaid
    
    # QA & quality
    "qa_results": dict,                               # Quality evaluation results
    "visual_qa_report": dict,                         # Visual quality checks
    
    # Internal callbacks
    "_emit_run_event": Callable,                      # Event emission callback
    "_session": Session                               # Database session
}
```

### Run & RunEvent Models

**File:** `src/core/db/models.py`

```python
class Run(Base):
    __tablename__ = "runs"
    
    id: str                                    # UUID, primary key
    project_id: str                            # FK to Project
    user_id: str                               # Who created it
    status: str                                # approved, running, done, failed, etc.
    plan_json: str                             # Serialized plan_payload
    conversation_id: str | None                # FK to Conversation
    
    # Execution tracking
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    
    # Results
    artifacts_json: str | None                 # Generated file metadata
    final_state_json: str | None               # Last state snapshot

class RunEvent(Base):
    __tablename__ = "run_events"
    
    id: str                                    # UUID
    run_id: str                                # FK to Run
    event_type: str                            # coordinator_plan, agent_tool_round, etc.
    phase: str                                 # planning, execution, finalization
    schema_version: str                        # run-events-v1
    
    # Envelope (canonical)
    ts_ms: int                                 # Timestamp milliseconds
    payload: str (JSON)                        # Event-specific data
    
    # Audit trail
    created_at: datetime
```

---

## Variable Passing Between Components

### 1. Conversation → Run Bridge

```
User sends message in Sheldon conversation
        ↓
ConversationMessage created + saved
        ↓
Sheldon responds (AgentPersonality.get_catchphrase())
        ↓
ConversationState updated (slots, deliverable, state machine)
        ↓
User confirms plan
        ↓
Conversation metadata extracted:
  - plan_hash
  - instruction
  - template_output_types
  - decision_answers
  - discovery (slots)
  - content_skill_targets
  - selected_strategy
        ↓
Plan payload constructed
        ↓
Run created with:
  - plan_json = plan_payload (serialized)
  - conversation_id = ref back to conversation
        ↓
Conversation messages converted to digest
```

### 2. Run → Coordinator Context

```
Run approved (status="approved")
        ↓
run_worker() fetches Run record
        ↓
CoordinatorRunInput constructed:
  - raw_text: conversation messages concatenated
  - user_instruction: cleaned from plan_payload
  - requested_outputs: template_output_types
  - plan_payload: passed through from conversation
  - user_id, project_id, run_id, etc.
        ↓
Coordinator.coordinate(CoordinatorRunInput) called
        ↓
AdviseWorkbenchState initialized:
  - Conversation digest built from conversation_id
  - All plan fields copied into state
  - Context engine retrieves wiki/memory
  - Enrichment engine analyzes content
```

### 3. Coordinator → Agent Contexts

```
Execution plan generated
        ↓
For each output_type in ordered_output_types:
  
  1. build_agent_context(state, output_type)
     → Filters/extracts:
       - conversation_digest (all agents get full digest)
       - plan_payload (all agents get plan details)
       - user_instruction (all agents get instruction)
       - skill_instructions_by_output[output_type]
       - prior_artifacts_excerpt (from earlier agents)
       - process_model (shared reference)
       - enrichment (audience/risk/value analysis)
  
  2. Agent receives AgentContext
  
  3. Agent uses context to:
     - Understand user intent from conversation
     - Respect content_skill_targets (e.g., "sop_v2")
     - Follow discovered requirements (from discovery slots)
     - Honor selected strategies
     - Reference prior generated sections
  
  4. Agent produces AgentOutput
     - updates: {output_key: generated_content}
     - tool_trace: [{tool, input, output, ...}, ...]
  
  5. merge_agent_output(state, agent_output)
     → state.updated with output
     → State now has both prior outputs + new output
```

### 4. Agent Output → Files

```
Final state accumulated across all agents:
{
    "pptx_slides": [...],
    "docx_markdown": "...",
    "xlsx_cells": {...},
    ...
}
        ↓
Quality assurance loop (QAAgentLoop)
        ↓
Visual quality checks
        ↓
Format generators (pptx_generator, docx_generator, etc.)
        ↓
Binary files written to workspace/{project_id}/runs/{run_id}/
        ↓
RunEvent emitted per file
        ↓
Run status updated to "done"
        ↓
User notified, files available in UI
```

---

## Critical Variable References

### Variables Shared Across Full Flow

| Variable | Source | Type | Usage | Scope |
|----------|--------|------|-------|-------|
| `conversation_id` | User's conversation record | `str (UUID)` | Links to ConversationMessage, ConversationState | Full flow |
| `plan_payload` | Conversation's plan metadata | `dict` | Passed to Coordinator, all agents receive via context | Coordinator + all agents |
| `user_instruction` | Cleaned from plan_payload | `str` | Drives agent prompts, skill selection | Coordinator + all agents |
| `conversation_digest` | Built from messages + state | `str` | Full context for agents (what user discussed) | Coordinator + all agents |
| `requested_outputs` | From plan_payload template_output_types | `list[str]` | Determines which agents run | Coordinator |
| `project_id` | Associated with run | `str (UUID)` | Workspace directory, DB queries, context isolation | Full flow |
| `run_id` | Generated when run created | `str (UUID)` | Tracks all events, file storage, user reference | Full flow |
| `state` | AdviseWorkbenchState (mutable) | `dict` | Accumulated outputs, shared between agents | Coordinator + agents |
| `content_skill_targets` | From plan_payload | `dict[str, str]` | Specifies deliverable type for format (e.g., "sop_v2") | Agents |
| `discovery` | From plan_payload (slots) | `dict` | User's answers to discovery questions | Agents (via context) |
| `process_model` | Retrieved from wiki/memory | `dict` | Shared reference for all agents | All agents |
| `branding_context` | From project settings | `dict` | Applied to all generated documents | All agents |
| `enrichment` | ContentEnrichmentEngine output | `dict` | Audience/risk/value analysis for all agents | All agents |

### Variable Transformation Chain

```
User Input (Chat)
  ↓ (save as ConversationMessage)
ConversationMessage.content + metadata
  ↓ (build digest + load state)
ConversationState + conversation_digest
  ↓ (extract plan metadata)
plan_payload (dict with discovery, decisions, strategies)
  ↓ (create CoordinatorRunInput)
plan_payload → CoordinatorRunInput.plan_payload
  ↓ (initialize state)
AdviseWorkbenchState["plan_payload"] + other fields
  ↓ (for each output, build context)
AgentContext.plan_payload + fields
  ↓ (agent prompt construction)
Agent receives full context in system prompt + user context message
  ↓ (agent generates)
AgentOutput.updates[output_key]
  ↓ (merge)
AdviseWorkbenchState[output_key] = generated_content
  ↓ (format generator)
Binary file (PPTX/DOCX/XLSX)
```

---

## Summary: Information Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ SHELDON CONVERSATION                                            │
│ (User discusses deliverables with Sheldon agent personality)   │
└────────────────┬────────────────────────────────────────────────┘
                 │
        ┌────────▼────────┐
        │ ConversationMsg │ Saved to DB
        │   Metadata      │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │  ConversationState
        │  FSM State Mgmt │ JSON to disk
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Plan Confirmation│
        │ + Plan Payload   │ Extracted
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   Run Created    │ plan_json = plan_payload
        │  (queued)        │ conversation_id = link
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │ Conversation     │ build_conversation_digest()
        │ Digest Built     │
        └────────┬────────┘
                 │
        ┌────────▼────────────────────────────────────┐
        │ CoordinatorRunInput                         │
        │ - raw_text (conversation)                   │
        │ - user_instruction (from plan)              │
        │ - plan_payload (all details)                │
        │ - requested_outputs                         │
        └────────┬───────────────────────────────────┘
                 │
        ┌────────▼────────────────────────────────────┐
        │ AdviseWorkbenchState (initialized)          │
        │ - conversation_digest                       │
        │ - plan_payload fields                       │
        │ - process_model (retrieved)                 │
        │ - enrichment (computed)                     │
        │ - branding (loaded)                         │
        └────────┬───────────────────────────────────┘
                 │
      ┌──────────┴──────────┬──────────────┐
      │                     │              │
  ┌───▼────┐  ┌────▼────┐ ┌───▼────┐
  │PPTX    │  │ DOCX    │ │ XLSX   │  ... (more agents)
  │Agent   │  │ Agent   │ │ Agent  │
  └───┬────┘  └────┬────┘ └───┬────┘
      │            │          │
      │ AgentContext (per agent):
      │ - conversation_digest (FULL)
      │ - plan_payload (FULL)
      │ - user_instruction
      │ - user_intent_original
      │ - skill_instructions (specific to output_type)
      │ - prior_artifacts_excerpt (from earlier agents)
      │ - process_model, enrichment, branding (shared)
      │
      └─────────────┬──────────────────┘
                    │
      ┌─────────────▼──────────────────┐
      │ Run Tool Loop (per agent)       │
      │ - Call LLM with full context   │
      │ - Tool use (retrieve, search)  │
      │ - Generate markdown/data       │
      └─────────────┬──────────────────┘
                    │
      ┌─────────────▼──────────────────┐
      │ AgentOutput (per agent)         │
      │ - updates: {output_key: "..."}  │
      │ - tool_trace: [...]            │
      └─────────────┬──────────────────┘
                    │
      ┌─────────────▼──────────────────┐
      │ Merge into State                │
      │ state[output_key] = generated   │
      └─────────────┬──────────────────┘
                    │
      ┌─────────────▼──────────────────┐
      │ Quality Assurance               │
      │ (per output if needed)          │
      └─────────────┬──────────────────┘
                    │
      ┌─────────────▼──────────────────┐
      │ Format Generators               │
      │ markdown → PPTX/DOCX/XLSX      │
      └─────────────┬──────────────────┘
                    │
      ┌─────────────▼──────────────────┐
      │ Save Artifacts                  │
      │ workspace/{project}/{run}/      │
      │  output.pptx                    │
      │  output.docx                    │
      │  output.xlsx                    │
      └─────────────┬──────────────────┘
                    │
      ┌─────────────▼──────────────────┐
      │ Run Completed                   │
      │ Status = "done"                 │
      │ Emit events to UI               │
      └─────────────────────────────────┘
```

---

## Configuration & Tuning

### Conversation Digest Configuration
- **Freshness TTL:** `conversation_source_freshness_ttl_seconds` (default: 259200 = 3 days)
- **Message limit:** `message_limit=40` (max messages to include)
- **Per-message chars:** `per_message_chars=600` (max per message)
- **Total cap:** `char_cap=10000` (total digest size)

### Coordinator Configuration
- **Planning enabled:** `coordinator_llm_planning_enabled` (bool)
- **Thinking budget:** `anthropic_thinking_budget_tokens` (int)
- **Debug logging:** `advise_workbench_coordinator_debug_log` (path)

### Agent Configuration
- **Max rounds:** `subagent_tool_max_rounds` (per-agent iteration limit)
- **Max tokens:** `subagent_tool_max_tokens` (token budget per agent)
- **QA threshold:** `qa_threshold=0.8` (quality gate)
- **QA max loops:** `max_qa_loops=2` (remediation attempts)

### Quality Framework
- **Visual QA enabled:** Feature flag for design review
- **Guardrails enabled:** Policy/safety checks on plan
- **Data protection:** DPDP flags in run creation

---

## Error Handling & Retry

### If Conversation Digest Fails
- Empty digest returned
- Agents receive user_instruction + plan_payload (sufficient context)
- RunEvent emitted with warning

### If Agent Fails
- Error captured in tool_trace
- If `max_qa_loops` not exceeded:
  - Generate remediation prompt
  - Re-run agent with error context
  - Increment remediation count
- If still fails:
  - Apply fallback strategy (simplified template)
  - Emit warning, continue

### If Output Validation Fails
- QA loop detects quality < threshold
- Regeneration directive applied
- Agent re-run with guidance

### If Run Aborted
- Graceful shutdown enabled via `_draining` flag
- Active futures await bounded window
- Partial results saved where possible

---

## Audit Trail & Observability

### Run Events Emitted

| Event Type | Payload | When |
|------------|---------|------|
| `run_created` | {run_id, conversation_id, status} | Run record created |
| `coordinator_plan` | {ordered_outputs, rationale, thinking_excerpt} | Plan generated |
| `agent_tool_round` | {agent, round, tools, output_keys} | Agent completes round |
| `qa_evaluation` | {output_type, score, issues} | QA check done |
| `deliverable_generated` | {type, path, size_bytes} | File written |
| `run_completed` | {status, artifacts} | Run finished |

### Database Audit Trail
- All events persisted to `run_events` table
- Immutable (append-only log)
- Searchable by project_id, run_id, event_type, phase
- SSE-published to frontend in real-time

---

## End-to-End Example

**User interaction:**
```
Sheldon: Hi! Let's create your vendor onboarding documentation. What's the scope?

User: New vendor approval process for international suppliers

Sheldon: Got it! I'll map that out. 🎯 Let me gather details...
[Questions about decision points, approval roles, timeline]

User: [Answers questions about 5 approval stages, 3 roles]

Sheldon: Blueprint locked in! 📋 Ready to generate:
- Process map (DrawIO)
- SOP (Word document)
- RACI matrix (Excel)
Shall we go?

User: Yes, let's do it!
```

**Backend processing:**
```
1. User's last message stored as ConversationMessage
2. Plan metadata extracted:
   - instruction = "Create process map, SOP, RACI for new vendor approval"
   - template_output_types = ["process_map", "docx", "xlsx"]
   - content_skill_targets = {"docx": "sop_v2", "xlsx": "raci_v2"}
   - discovery = {stages: 5, roles: 3, ...}

3. Run created, approved, queued

4. Coordinator receives:
   - conversation_digest = full Sheldon chat with context markers
   - plan_payload = all discovery + decisions
   - requested_outputs = [process_map, docx, xlsx]

5. Coordinator plans:
   - order = [process_map (simple), docx (medium), xlsx (fast)]
   - rationale = "Map first for context, then details"

6. process_map agent:
   - context.conversation_digest = "User discussed 5 approval stages..."
   - context.process_model = standard process definitions
   - context.skill_instructions = "Generate DrawIO diagram for approval flow"
   - generates drawio_xml

7. docx agent:
   - context.conversation_digest = full
   - context.plan_payload.content_skill_targets["docx"] = "sop_v2"
   - context.prior_artifacts_excerpt includes process_map description
   - generates SOP markdown following sop_v2 skill

8. xlsx agent:
   - context.plan_payload.discovery.roles = 3 (knows from user answers)
   - context.skill_instructions = "Generate RACI for roles: [Admin, Mgr, Director]"
   - generates RACI cell data

9. Quality checks pass

10. Files generated:
    - process_map.drawio
    - vendor_onboarding_sop.docx
    - vendor_approval_raci.xlsx

11. User sees all three in deliverables panel
```

---

## Conclusion

The Sheldon conversation system is tightly integrated with the document generation pipeline:

1. **Conversation** = where requirements are gathered (Sheldon asks questions)
2. **State machine** = tracks conversation progress toward confirmable plan
3. **Digest** = compacts conversation into actionable context for agents
4. **Plan payload** = carries all decisions, discovery, strategies to agents
5. **Agent context** = filtered view of state relevant to each output type
6. **Tool loops** = agents use tools (wiki, search) to enrich content
7. **Merge** = accumulate outputs into shared state
8. **Format generation** = convert markdown/data to binary files
9. **Audit trail** = full event log for compliance and debugging

Every variable is traced from conversation message through to final document, enabling full reproducibility and human-in-the-loop approval at each stage.
