# Token Consumption & Character Limits Architecture

Comprehensive guide to token budgets, character limits, and their impact on performance throughout the Advise Workbench end-to-end execution pipeline.

## Table of Contents

1. [End-to-End Token Consumption Flow](#end-to-end-token-consumption-flow)
2. [Character Limits at Each Stage](#character-limits-at-each-stage)
3. [Token Budget Enforcement](#token-budget-enforcement)
4. [Compression Strategy](#compression-strategy)
5. [Performance Impact Analysis](#performance-impact-analysis)
6. [Configuration Reference](#configuration-reference)

---

## End-to-End Token Consumption Flow

### Complete 9-Phase Orchestration with Token Tracking

```
Phase 1: PREPARE (0 tokens)
  └─ Load run, validate permissions, set status=running

Phase 2: CONTEXT (1.2K-11.5K tokens)
  ├─ Load conversation digest (5-12K tokens typically)
  ├─ Build initial state (500-1K tokens overhead)
  ├─ [SHELDON ROUTER AGENT] Intent classification
  │  ├─ Input: 1,000-3,000 tokens
  │  └─ Output: 200-500 tokens
  │  └─ Cost: $0.015-0.050
  └─ Route Decision:
     ├─ Path 1a (Conversational): ANSWER AGENT → RUN ENDS (saves $2.50-3.50)
     ├─ Path 1b (RAG Search): RAG AGENT → RUN ENDS (saves $1.90-3.50)
     └─ Path 2 (Full Generation): Continue to Phase 3

Phase 3: GENERATE - COORDINATOR (15K-55K tokens)
  ├─ [COORDINATOR PLANNING] 1-2 calls (3.5K-11.5K tokens)
  └─ [SPECIALIST AGENTS] (4-7 agents):
     ├─ PPTX Agent: 8K-20K tokens
     ├─ DOCX Agent: 4K-12K tokens
     ├─ XLSX Agent (RACI): 2K-5K tokens
     ├─ SOP Agent: 2.5K-6.5K tokens
     ├─ Narrative Agent: 1.5K-4K tokens
     ├─ Process Map Agent: 1.5K-4K tokens
     └─ PDF Agent: 2K-5K tokens
  └─ PHASE TOTALS: 25K-55K tokens

Phase 4: EVALUATE (4.5K-15.3K tokens)
  ├─ Visual QA: 2.5K-6.5K tokens
  ├─ Guardrail Checks: 1.2K-3.8K tokens
  └─ Evaluator Pipeline: 1.8K-5K tokens

Phase 5: REMEMBER (0 tokens) - DB only
Phase 6: FINALIZE (0 tokens) - Write token usage to DB
Phase 7: POST-EXECUTION (background, non-blocking)
Phase 8: APPROVAL & REVIEW (0 tokens - user interaction)
Phase 9: REGENERATION (if triggered, 5K-25K tokens per attempt)
```

### Token Consumption by Output Type

| Output Type | Min Chars | Avg Chars | Max Chars | Min Tokens | Avg Tokens | Max Tokens | Min Cost | Avg Cost | Max Cost |
|---|---|---|---|---|---|---|---|---|---|
| DOCX SOP | 8K | 15K | 25K | 4K | 8K | 15K | $0.30 | $0.70 | $1.20 |
| PPTX Deck | 12K | 40K | 75K | 8K | 20K | 35K | $1.50 | $3.50 | $5.50 |
| XLSX RACI | 5K | 10K | 15K | 2K | 4K | 8K | $0.20 | $0.50 | $0.90 |
| PDF Report | 10K | 18K | 30K | 4K | 8K | 15K | $0.30 | $0.70 | $1.20 |
| Narrative | 3K | 6K | 10K | 2K | 4K | 8K | $0.15 | $0.40 | $0.80 |
| Process Map | 5K | 12K | 20K | 1.5K | 3K | 6K | $0.10 | $0.30 | $0.60 |
| Multi (4-5 outputs) | 40K | 100K | 170K | 20K | 35K | 78K | $1.50 | $2.50 | $6.50 |

### Typical Run Scenarios

**Scenario A: Conversational Path (Early Exit)**
```
Engagement Creation → Context → Sheldon Router → Answer Agent → APPROVED
Characters: 2K-5K
Tokens: 1.2K-3.5K
Cost: $0.015-0.050
```

**Scenario B: RAG Path (Early Exit)**
```
Engagement Creation → Context → Router → RAG Agent (1-2 calls) → APPROVED
Characters: 3K-8K
Tokens: 2.6K-11K
Cost: $0.05-0.30
```

**Scenario C: Full Generation - Single Output**
```
Engagement Creation → Context → Router → Coordinator → DOCX Agent → Evaluate → APPROVE
Characters: 10K-30K
Tokens: 12.2K-36.5K
Cost: $0.85-2.70
```

**Scenario D: Full Generation - Multiple Outputs (4-5)**
```
Engagement Creation → Context → Router → Coordinator 
  ├─ PPTX (40-150 slides)
  ├─ DOCX (Narrative)
  ├─ XLSX (RACI)
  ├─ SOP (document)
  └─ Process Map
→ Evaluate → APPROVE
Characters: 40K-170K
Tokens: 32K-78K
Cost: $2.50-6.50
Status: COMPLETE (may exceed 50K budget → compression triggered)
```

**Scenario E: Full Generation + 2 Regenerations**
```
Run 1: Full generation → Evaluation fails
Run 2: Regeneration attempt 1 (10K-20K tokens) → Still issues
Run 3: Regeneration attempt 2 (8K-15K tokens) → Approved

Total Tokens: 65K-135K (exceeds 50K budget → compression applied)
Total Cost: $5.00-12.00
```

### Cost Calculation Formula

```python
cost_usd = (
    tokens_input * 3.00 / 1_000_000
    + tokens_output * 15.00 / 1_000_000
    + tokens_cache_read * 0.30 / 1_000_000
    + tokens_cache_creation * 3.75 / 1_000_000
)

# Typical multi-output run (50K tokens):
# Input: 25K × $3.00/MTok = $0.075
# Output: 25K × $15.00/MTok = $0.375
# Total: $0.45
```

---

## Character Limits at Each Stage

### System Prompt Character Limits

| Component | Char Limit | Source | Purpose | Impact |
|-----------|-----------|--------|---------|--------|
| Skill descriptions | 4,000 | `_shared.py:244` | Wrapped/sanitized to prevent injection | ~1,142 tokens |
| Skill instructions | 48,000 | `_shared.py:253` | Core craft instructions from SKILL.md | ~13,714 tokens - **NO truncation** |
| Workflow steps | 16,000 | `_shared.py:262` | Reasoning sequence | ~4,571 tokens |
| Feedback loop | 8,000 | `_shared.py:274` | Self-correction guidance | ~2,286 tokens |
| Acceptance checks | 8,000 | `_shared.py:287` | Quality gate criteria | ~2,286 tokens |
| Companion files | 48,000 | `_shared.py:311` | Domain reference material | ~13,714 tokens |
| Post-processor rules | 16,000 | `_shared.py:349` | Brand & tone guidelines | ~4,571 tokens |

**Key Point:** System prompt components are NOT auto-truncated. Instead, compression is applied to user prompt and context if budget is exceeded.

### User Prompt Character Limits

| Component | Char Limit | Behavior | Impact |
|-----------|-----------|----------|--------|
| Regeneration directive | 800 | Hard truncation at 800 chars | Feedback from planner may be cut off |
| Text editor max | 12,000 | Hard truncation | Users can't edit/paste beyond 12K chars |
| Knowledge batch | 12,000 | Per fact-extraction call | Limits chunk size for knowledge building |
| Per-message in digest | 600 | Individual messages truncated | Conversation history compressed |

### Conversation Digest Character Limits (Primary Constraint)

| Component | Limit | Behavior | Token Equiv. | Impact |
|-----------|-------|----------|--------------|--------|
| Coordinator digest | 12,000 | Main conversation context to coordinator | ~3,429 tokens | Context loss if conversation is long |
| Subagent digest | 3,500 | Passed to DOCX/PPTX agents | ~1,000 tokens | Agents receive compressed history |
| Planner excerpt | 6,000 | Used in planning phase | ~1,714 tokens | Planning decisions based on limited context |
| Compaction threshold | 32,000 | Triggers multi-tier compaction | ~9,143 tokens | Automatic compression when exceeded |
| Hard cap | 32,000 | Absolute maximum context size | - | Enforces hard boundary |

**Performance Impact:**
- 50-message conversation: Only ~40 recent messages fit in 12K chars (first 10 dropped)
- Subagents only see ~3.5K chars (~1K tokens) of conversation history
- Older messages automatically compressed/summarized

### Retrieved Context Character Limits

| Tier | Limit | Content | Impact |
|------|-------|---------|--------|
| Tier 0 | 2,000 chars | CONTEXT.md (project-specific) | Always included, no loss |
| Tier 1 | 12,000 chars | LP (Leading Practice) snippets | May exclude some practices if tight |
| Tier 2 | 10,000+ chars | Source doc chunks (BM25 ranked) | Lower-ranked sources dropped first |
| Total | 32,000 chars | Sum of all tiers | Context assembly stops at 32K |

**Behavior:** BM25-ranked chunks included sequentially until character budget exhausted. Lower-relevance chunks dropped first.

### Agent-Specific Input Limits (Prompt Tokens)

| Agent Type | Max Prompt Tokens | Config Key | Char Equiv. (~3.5 chars/token) |
|------------|-------------------|-----------|--------------------------------|
| Subagent | 6,000 | `subagent_max_prompt_tokens` | ~21,000 chars |
| Coordinator planner | 12,000 | `coordinator_max_prompt_tokens` | ~42,000 chars |
| Proposal generation | 8,000 | `proposal_max_prompt_tokens` | ~28,000 chars |
| Coordinator plan max | 8,192 | `anthropic_coordinator_plan_max_tokens` | ~28,672 chars |

### Tool Output Character Limits

| Tool | Limit | Config Key | Source |
|------|-------|-----------|--------|
| Tool result to text | 24,000 chars | Hardcoded | `registry.py:1830` |
| Web capture | 8,000 chars | Configurable | `web_capture.py:174` |
| Bash max output | 65,536 bytes | `bash_max_output_bytes` | `config.py:378` |
| Bash max lines | 400 lines | `bash_max_output_lines` | `config.py:379` |

### Hardcoded Character Thresholds

| Threshold | Value | Behavior | Source |
|-----------|-------|----------|--------|
| Message fragment cutoff | 24 chars | Drops <24 char messages from digest | `context_compaction.py:138` |
| Per-message cap | 600 chars | Truncates individual messages in digest | `conversation_digest.py:114` |
| Context section max | 2,000 chars | Excerpt compression triggers | `token_budgets.py:225` |
| Instruction section max | 2,000 chars | Instruction reduction tier | `token_budgets.py:257` |
| Compaction min cap | 200 chars | Absolute floor for digests | `context_compaction.py:26` |
| Sectioned digest min | 1,200 chars | Minimum for sectioned assembly | `conversation_digest.py:146` |
| Tiered compaction trigger | 32,000 chars | Enables multi-tier compression | `config.py:315` |

---

## Token Budget Enforcement

### Budget Tracking Infrastructure

**Context Variables (Carried Across Phases):**
```python
_run_usage: dict = {
    "input_tokens": int,
    "output_tokens": int,
    "cache_read_tokens": int,
    "cache_creation_tokens": int
}
_run_cost: float  # USD cost
```

**Database Persistence (Run model):**
```sql
tokens_input: INTEGER
tokens_output: INTEGER
tokens_cache_read: INTEGER
tokens_cache_creation: INTEGER
cost_usd: DECIMAL(10, 4)
```

### Pre-Call Budget Verification

**Location:** `src/llm/token_budgets.py:76-126`

```python
def check_budget(system: str, user: str, needed_output_tokens: int = 4096):
    remaining_budget = get_remaining_budget()
    prompt_tokens = estimate_prompt_tokens(system, user)
    total_needed = prompt_tokens + needed_output_tokens + SAFETY_MARGIN_TOKENS
    
    compression_needed = max(0, total_needed - remaining_budget)
    
    if remaining_budget < 1000 and compression_needed > 0:
        raise RunBudgetExceeded()  # Hard fail if budget critical
    
    return (fits=compression_needed == 0, info={...})
```

### Token Estimation Formula

**Fixed Ratio Throughout Application:**
```
tokens = characters / 3.5
```

**Why 3.5?** Empirically more accurate than 4.0 chars/token ratio.

**Message Overhead:** +100 tokens for framing and stop sequences

**Safety Margin:** 500 tokens always reserved

**Examples:**
- 350 chars = 100 tokens
- 3,500 chars = 1,000 tokens
- 12,000 chars = 3,429 tokens
- 32,000 chars = 9,143 tokens

### Budget Enforcement Logic

**Per-Run Limit:** `ANTHROPIC_MAX_TOKENS_PER_RUN` = **50,000 tokens** default (~175K chars equivalent)

**Budget Check Flow:**
```
1. Check if (prompt_tokens + output_tokens + 500) > remaining_budget
2. If remaining_budget < 1,000 AND over budget: FAIL (RunBudgetExceeded)
3. If remaining_budget >= 1,000 AND over budget: COMPRESS
4. If fits: EXECUTE model call
5. Charge tokens via charge_llm_usage(tokens)
6. Decrement remaining budget
7. On budget exhaustion: Run terminates (no more LLM calls)
```

### Live Token Tracking

**Real-Time Monitoring:**
```python
usage = get_live_usage(run_id)  # Returns current run's token count
# UI polls this during generation to show live consumption
```

**Final Recording (in finalize phase):**
```python
_write_token_usage(run, _run_usage, _run_cost)
# Writes to Run.tokens_input, tokens_output, etc.
```

---

## Compression Strategy

### When Compression Triggers

**Detection:**
```python
if (system_chars + user_chars + context_chars) / 3.5 > remaining_token_budget:
    apply_compression()  # Graceful degradation
```

**Compression happens BEFORE model call** → No API failures due to size

### 5-Tier Compression Strategy

**Location:** `src/llm/token_budgets.py:138-329`

Triggered sequentially when budget exceeded:

#### Tier 1: Trim Verbose Examples
- **Removes:** "Example:" sections from system prompt
- **Tokens saved:** 500-2K (~1-6%)
- **Impact:** Example-based guidance lost
- **Triggers at:** First compression attempt

#### Tier 2: Compress Context Excerpts
- **Removes:** Context > 2,000 chars → truncate to 1,500 chars or 15 lines
- **Tokens saved:** 2K-5K (~5-15%)
- **Impact:** Context details compressed, nuance lost
- **Marker added:** "[...context truncated...]"

#### Tier 3: Reduce User Instruction
- **Removes:** Instruction sections → truncate to 2,000 chars
- **Tokens saved:** 1K-3K (~3-10%)
- **Impact:** Requirements clarity reduced
- **Trigger:** After Tier 2 if still over budget

#### Tier 4: Simplify ProcessModel JSON
- **Keeps:** process_name, first 10 steps, all roles, first 5 decisions
- **Removes:** Optional fields, middle steps, extra decisions
- **Tokens saved:** 1K-2K (~3-6%)
- **Impact:** Process model loses granularity (50+ steps → 10 steps)
- **Trigger:** After Tier 3 if still over budget

#### Tier 5: Hard Truncation with Safety Buffer
- **Aggressive mode (default):** Keep first 40% + last 10% + "[...truncated...]"
- **Conservative mode:** Keep first 60% + last 20% + "[...truncated...]"
- **Tokens saved:** 5K-15K (~10-40%)
- **Impact:** Significant information loss (40-60% of content dropped)
- **Trigger:** Last resort, after Tiers 1-4

**Cumulative Impact:**
```
Tier 1:         500-2K tokens removed
Tier 1+2:     2.5K-7K tokens removed
Tier 1-3:     3.5K-10K tokens removed
Tier 1-4:     4.5K-12K tokens removed
Tier 1-5:     9.5K-27K tokens removed
```

### Tiered Conversation Compaction (Within Digests)

**Location:** `src/memory/short_term/context_compaction.py:19-138`

Applied when conversation digest exceeds limits:

**Tier 1: Micro-compact**
- Drop fragments < 24 chars
- Truncate messages to 600 chars max
- Removal: ~10-15% of digest

**Tier 2: Snip Oldest**
- Keep newest 120 messages only
- Removal: ~20-30% (drop oldest messages)

**Tier 3: Auto-summary**
- Compress older messages to one summary line (max 1,200 chars)
- Keep newer messages verbatim
- Removal: ~40-50%

**Tier 4: Context Collapse**
- Keep only last 5 messages + collapse marker
- Removal: ~90%+ (extreme case)

---

## Performance Impact Analysis

### Impact by Compression Level

**Scenario A: Normal Execution (No Compression)**
```
Total characters: 25K-35K
Total tokens: 7K-10K
Model performance: OPTIMAL (full context + instructions)
Cost: $0.10-0.15
Quality: Excellent - model has complete context
```

**Scenario B: Compression Triggered (Tiers 1-2)**
```
Characters removed: 2.5K-7K
Total characters: 18K-30K
Total tokens: 5K-8.5K
Model performance: ACCEPTABLE (minor context loss)
Cost: $0.08-0.13
Quality: Good - most context preserved
```

**Scenario C: Deep Compression (Tiers 3-5)**
```
Characters removed: 8K-20K
Total characters: 15K-25K
Total tokens: 4K-7K
Model performance: DEGRADED (significant information loss)
Cost: $0.05-0.10
Quality: Fair - missing mid-level details
```

**Scenario D: Hard Truncation (Tier 5, Aggressive)**
```
Characters removed: 15K-20K (40-60% of content)
Total characters: 5K-15K
Total tokens: 1.4K-4.3K
Model performance: POOR (hallucinations likely)
Cost: $0.02-0.06
Quality: Poor - major context gaps, likely errors
```

### Real-World Performance Impact

**Example 1: Long Conversation**
```
Actual messages: 50 messages × 300 chars = 15,000 chars
Digest limit: 12,000 chars
Result: Last ~40 messages fit, first 10 dropped
Impact: Model doesn't see early decisions/context
Risk: Contradictory decisions or repeated work
```

**Example 2: Rich Process Model**
```
ProcessModel JSON: 12,000 chars (50 steps, 20 decisions)
Tier 4 compression: Keep name, 10 steps, roles, 5 decisions = 3,000 chars
Chars removed: 9,000 (75% loss)
Impact: Model only sees top 10 steps
Risk: Missing nuanced decision points, workflow gaps in output
```

**Example 3: Large Document Processing**
```
Document size: 100K chars
KNOWLEDGE_FACT_BATCH_CHARS: 12,000 chars per call
Number of calls: 100K / 12,000 = 8-9 calls
Total tokens: 8-9 × (12K / 3.5) = ~27K-31K tokens
Impact: 8-9 LLM calls for one document (30% of budget!)
```

### Token Consumption vs. Quality Trade-off

| Scenario | Tokens | Cost | Quality | Recommendation |
|----------|--------|------|---------|-----------------|
| No compression | 7K-10K | $0.10-0.15 | Excellent | Default/preferred |
| Tier 1-2 compression | 5K-8.5K | $0.08-0.13 | Good | Acceptable |
| Tier 3-5 compression | 4K-7K | $0.05-0.10 | Fair | Use with caution |
| Hard truncation | 1.4K-4.3K | $0.02-0.06 | Poor | Last resort only |

---

## Configuration Reference

### Environment Variables

```env
# Character Limits (chars)
CONVERSATION_DIGEST_MAX_CHARS=12000
SUBAGENT_CONVERSATION_DIGEST_MAX_CHARS=3500
COORDINATOR_PLANNING_CONTEXT_CHARS=7000
TEXT_EDITOR_MAX_CHARACTERS=12000
MEMORY_COMPACTION_CHAR_CAP=32000
CONVERSATION_DIGEST_TIERED_COMPACTION_THRESHOLD_CHARS=32000

# Token Budget
ANTHROPIC_MAX_TOKENS_PER_RUN=50000
TOKEN_ESTIMATE_RATIO=3.5
TOKEN_BUDGET_SAFETY_MARGIN_TOKENS=500

# Compression
PROMPT_COMPRESSION_ENABLED=true
PROMPT_COMPRESSION_STRATEGY=aggressive  # or "conservative"
PROMPT_COMPRESSION_LOG_VERBOSE=true

# Per-Call Prompt Tokens
SUBAGENT_MAX_PROMPT_TOKENS=6000
COORDINATOR_MAX_PROMPT_TOKENS=12000
PROPOSAL_MAX_PROMPT_TOKENS=8000
ANTHROPIC_COORDINATOR_PLAN_MAX_TOKENS=8192

# Thinking Budgets (Extended Thinking)
ANTHROPIC_THINKING_BUDGET_TOKENS=8000
ANTHROPIC_SUBAGENT_THINKING_BUDGET_TOKENS=8000
ANTHROPIC_PLANNING_THINKING_BUDGET_TOKENS=6000

# Conversation Summary
CONVERSATION_SUMMARY_TRIGGER_INTERVAL=6
CONVERSATION_SUMMARY_RECENT_EXCLUDE_COUNT=6
CONVERSATION_SOURCE_FRESHNESS_TTL_SECONDS=259200

# Output Tokens
ANTHROPIC_MAX_TOKENS=4096
ANTHROPIC_COORDINATOR_PLAN_MAX_TOKENS=8192

# Retry & Timeouts
LLM_MAX_RETRIES=3
LLM_TIMEOUT_SEC=180
ANTHROPIC_TIMEOUT_SEC=45

# Rate Limiting
RUN_CREATE_RATE_LIMIT=20/minute
RUN_APPROVE_RATE_LIMIT=20/minute
QUERY_RATE_LIMIT=30/minute

# Database & Concurrency
RUN_MAX_ACTIVE_GLOBAL=500
RUN_MAX_ACTIVE_PER_PROJECT=20
RUN_MAX_ACTIVE_PER_USER=8
DATABASE_POOL_SIZE=20
```

### Configuration Sections

**Token/Character in `src/core/config.py`:**

```python
# Lines 287-320: Token budgets
ANTHROPIC_MAX_TOKENS = 4096
ANTHROPIC_COORDINATOR_PLAN_MAX_TOKENS = 8192
ANTHROPIC_THINKING_BUDGET_TOKENS = 8000

# Lines 311-320: Character limits
CONVERSATION_DIGEST_MAX_CHARS = 12000
SUBAGENT_CONVERSATION_DIGEST_MAX_CHARS = 3500
COORDINATOR_PLANNING_CONTEXT_CHARS = 7000

# Lines 301-305: Token estimation
TOKEN_ESTIMATE_RATIO = 3.5
TOKEN_BUDGET_SAFETY_MARGIN_TOKENS = 500
PROMPT_COMPRESSION_ENABLED = True
PROMPT_COMPRESSION_STRATEGY = "aggressive"
```

---

## Key Implementation Files

| File | Purpose | Lines |
|------|---------|-------|
| `src/llm/token_budgets.py` | Token estimation, compression logic, budget checking | 329 |
| `src/llm/run_budget.py` | Budget context managers, token accumulation | - |
| `src/llm/middleware/usage.py` | `record_usage()` function, charges budget + metrics | - |
| `src/prompts/prompt_hygiene.py` | Untrusted wrapping, injection defense | 58 |
| `src/agents/specialists/_shared.py` | Zoned prompt building | 1026 |
| `src/memory/retrieval.py` | Tiered context, BM25 ranking, MMR dedup | - |
| `src/memory/short_term/conversation_digest.py` | Digest building, compaction | - |
| `src/memory/short_term/context_compaction.py` | Tiered compaction logic | 138 |
| `src/app/api/projects/conversation.py` | Turn orchestration | - |
| `src/core/db/models.py` | Run model with token columns | - |
| `src/workflows/orchestrator.py` | `_write_token_usage()`, phase orchestration | - |

---

## Summary & Best Practices

### Key Findings

✅ **Character limits ARE configured at every step**
- System prompt: 4K-48K per component (NOT truncated)
- User prompt: 800-12K (truncated if needed)
- Context digest: 3.5K-12K (compressed automatically)
- Total assembled: 32K hard cap

✅ **Limits restrict prompts PROGRESSIVELY**
- Compression applied before model call (no API failures)
- 5-tier strategy: examples → context → instruction → JSON → hard truncate
- Graceful degradation from full context to minimal

✅ **Performance DEGRADES with compression**
- No compression: Optimal (7K-10K tokens, excellent quality)
- Tiers 1-2: Good (5K-8.5K tokens, acceptable quality)
- Tiers 3-5: Poor (1.4K-7K tokens, degraded quality)

✅ **Token consumption DECREASES with compression** but at **cost of quality**
- Normal: 7K-10K tokens ($0.10-0.15)
- Compressed: 4K-7K tokens ($0.05-0.10)
- Hard truncated: 1.4K-4.3K tokens ($0.02-0.06)

✅ **Budget is enforced proactively**
- Compression happens BEFORE model call
- Hard fail only if budget critical (<1,000 tokens remaining)
- Prevents runaway token consumption

### Recommendations

1. **Monitor token usage** during long engagements (50+ messages)
2. **Configure higher budgets** for complex processes with many outputs
3. **Use conservative compression** for quality-critical tasks
4. **Set conversation summary triggers** to keep digest manageable
5. **Track metrics** on compression rates and quality impact
6. **Increase per-run budget** for document-heavy engagements

