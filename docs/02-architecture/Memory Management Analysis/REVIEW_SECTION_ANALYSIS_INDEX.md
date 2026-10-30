# Review Section Memory Management: Complete Analysis Index

**Comprehensive deep-dive analysis of approval workflows, artifact integrity verification, and visual feedback generation in the Advise Workbench review section**

---

## Overview

This analysis package consists of **3 comprehensive documents** examining the review section from multiple perspectives:

### Document 1: Technical Deep-Dive
**File**: `REVIEW_SECTION_MEMORY_ARCHITECTURE_ANALYSIS.md` (65 KB)

Comprehensive technical analysis covering:
- **Part 1: Approval Workflows** — State machine, decision flow, comment threading, revision management
- **Part 2: Artifact Integrity Verification** — QA pipeline, geometry validation, evidence gating, score calculation
- **Part 3: Visual Feedback Generation** — Design review loop, text density analysis, narrative coherence
- **Part 4: Memory Integration & Lifecycle** — Complete lifecycle, database relationships, memory footprint estimates
- **Part 5: Edge Cases & Error Handling** — Concurrency hazards, failure modes, recovery strategies
- **Part 6: Performance Optimization Opportunities** — Caching, denormalization, async strategies
- **Part 7: Data Consistency & Durability** — ACID guarantees, audit trail immutability
- **Part 8: Recommendations** — Immediate, medium-term, and long-term improvements

**Best for**: Architects, senior engineers, performance optimization

### Document 2: Visual Diagrams
**File**: `REVIEW_SECTION_VISUAL_DIAGRAMS.md` (45 KB)

9 major visual flows and diagrams:
1. Complete review lifecycle state machine
2. Approval decision flow (request → DB update → notification)
3. Artifact quality signals pipeline (render → extract → feedback)
4. Memory lifecycle across request scopes
5. Database schema & relationships (ERD)
6. Concurrent request handling & thread safety
7. Multi-tier persistence model (DB vs FS vs Cache)
8. Error handling & retry patterns
9. Realistic multi-actor approval scenario (Alice → Bob workflow)

**Best for**: Understanding data flows, onboarding, architecture reviews

### Document 3: Developer Guide
**File**: `REVIEW_SECTION_DEVELOPER_GUIDE.md` (35 KB)

Practical working guide with:
- Quick start for product managers & engineers
- 5 common implementation tasks with code examples
- Data model reference (SQL schema)
- API endpoints reference (all review endpoints)
- Testing guide (unit, integration, manual)
- Monitoring & observability metrics
- Performance tuning strategies
- Troubleshooting guide (common problems & solutions)
- Deployment checklist
- FAQ

**Best for**: Developers, QA, DevOps, support engineers

---

## Key Findings Summary

### Architecture Overview

The review section implements a **three-layer memory management system**:

```
Layer 1: Approval Workflow (State Machine)
├─ Storage: Database (Review, ReviewComment tables)
├─ Pattern: Transactional ACID updates
├─ Memory: ~5-10 KB per request (stateless handlers)
└─ Durability: Immediate (db.commit())

Layer 2: Artifact Integrity (QA Assessment)
├─ Storage: RunEvent (DB) + filesystem (optional)
├─ Pattern: Ephemeral in-memory analysis → persistent results
├─ Memory: ~300 KB peak during analysis → released
└─ Durability: Deferred (written after LLM completes)

Layer 3: Visual Feedback (Design Review)
├─ Storage: RunEvent (DB) + filesystem (optional) + Redis cache
├─ Pattern: LLM-based analysis with image generation
├─ Memory: ~36 MB peak (tempfile images) → auto-cleanup
└─ Durability: Eventual (fail-open, doesn't block approval)
```

### Critical Statistics

| Metric | Value | Notes |
|--------|-------|-------|
| Peak Memory (Concurrent Load) | ~46.6 MB | 10 concurrent renders |
| Approval Decision Latency | <100 ms | DB transaction only |
| QA Assessment Duration | 2-5 seconds | Includes LLM call |
| Visual Feedback Token Budget | ~10,000 tokens | Per artifact |
| Database Transaction Scope | Single `db.commit()` | All-or-nothing atomicity |
| Timeline JSON Growth | ~1 KB per state change | Archive after 1000+ entries |
| Comment Query Performance | O(N) count | Optimize with denormalized field |

### Three Subsystems

#### 1. Approval Workflow Engine
- **State Machine**: Draft → Awaiting review ↔ Changes requested → Approved
- **Persistence**: `Review` + `ReviewComment` tables (DB-backed)
- **Audit Trail**: Append-only timeline in `Review.payload_json`
- **Key Risk**: Race condition on comment count validation (mitigated: 409 Conflict)

#### 2. Artifact Integrity Pipeline
- **QA Checks**: Completeness, design, structure, geometry, placeholder detection
- **Evidence Gate**: Citation/source validation for numeric claims
- **Storage**: `RunEvent` table (immutable) + filesystem (debug)
- **Memory**: 300 KB peak during extraction, then released

#### 3. Visual Feedback Loop
- **LLM Model**: claude-opus-5-5 (critique tier)
- **Inputs**: Slide metadata, density metrics, rendered images (optional)
- **Outputs**: Per-slide feedback (design, evidence, content quality)
- **Memory**: 36 MB peak (PNG images via tempfile), auto-cleanup

### Performance Characteristics

**Best Case** (Simple approval, no artifacts):
- Memory: <5 KB
- Duration: 100 ms
- Database: 1 transaction

**Typical Case** (One artifact, basic QA):
- Memory: ~300 KB (QA analysis)
- Duration: 2-3 seconds
- Database: 2 transactions (quality event + approval)

**Worst Case** (Full visual feedback, multiple slides, large LLM):
- Memory: 36 MB (image generation + LLM)
- Duration: 10-15 seconds
- Database: 3 transactions + SSE broadcast

---

## Navigation Guide

### For Different Roles

**I'm a Product Manager — where should I start?**
→ Read: Developer Guide → Quick Start section
→ Then: Visual Diagrams → Diagram 9 (realistic workflow)
→ Result: Understand approval cycle time, user experience

**I'm a Backend Engineer implementing changes**
→ Read: Developer Guide → Common Tasks section
→ Then: Technical Analysis → Relevant part (e.g., Part 2 for QA checks)
→ Then: Visual Diagrams → Database schema (Diagram 5)
→ Result: Know exactly what to modify and how

**I'm an Architect reviewing design**
→ Read: Technical Analysis → All parts
→ Then: Visual Diagrams → All flows
→ Then: Developer Guide → Performance tuning section
→ Result: Understand bottlenecks, scalability limits, optimization opportunities

**I'm a DevOps/SRE managing production**
→ Read: Developer Guide → Monitoring section
→ Then: Developer Guide → Troubleshooting section
→ Then: Technical Analysis → Part 5 (error handling)
→ Result: Know what to monitor, how to diagnose issues

**I'm QA testing this feature**
→ Read: Developer Guide → Testing guide section
→ Then: Visual Diagrams → Error handling (Diagram 8)
→ Then: Developer Guide → Troubleshooting (for edge cases)
→ Result: Test plan, test data, edge cases to cover

---

## Key Files to Know

### Backend Source Code

| File | Purpose | Key Classes/Functions |
|------|---------|----------------------|
| `src/app/api/reviews.py` | Review API endpoints | `decide()`, `add_comment()`, `submit_revision()` |
| `src/evaluation/pptx_qa.py` | PPTX quality checks | `extract_quality_signals()`, `check_pptx_geometry()` |
| `src/evaluation/visual_qa.py` | Design review feedback | `evaluate_visual_feedback()`, `_extract_pptx_metadata()` |
| `src/evaluation/narrative_feedback.py` | Document coherence | `extract_narrative_signals()` |
| `src/evaluation/evidence_validator.py` | Citation validation | `validate_claims()` |
| `src/core/db/models.py` | Data models | `Review`, `ReviewComment`, `Run`, `RunEvent` |
| `src/core/observability/metrics.py` | Monitoring | `increment()` for review metrics |

### Database Schema

```sql
reviews          — Main review record (state machine)
review_comments  — Comment thread per review
run_events       — Quality signals (immutable log)
run_tasks        — Skill output (pptx_data, docx_data)
engagement_meta  — Project settings (retention_days, stage)
```

### Frontend Components

| Component | Purpose |
|-----------|---------|
| `ApprovalBanner` | Shows review state, handles approval |
| `ReviewPanel` | Displays quality scores, visual feedback |
| `CommentThread` | Thread of reviewer/author comments |
| `ToolActivityFeed` | Shows QA assessment progress |

---

## Common Questions & Quick Answers

### Q: Where is the review state stored?
**A**: `reviews.state` (VARCHAR column). Values: "Awaiting review", "Changes requested", "In review", "Approved", "Draft"

### Q: How are approvals prevented if comments exist?
**A**: In `decide()`, query counts open comments. If count > 0, return 409 Conflict.

### Q: What happens if visual feedback LLM fails?
**A**: Caught gracefully. Empty feedback list returned. Approval not blocked.

### Q: Where are QA scores persisted?
**A**: Primarily in `RunEvent.payload` (JSON). Optional: `qa_report_*.json` files.

### Q: How long do artifacts stay on disk?
**A**: Configured per project via `EngagementMeta.retention_days`. Default: indefinite.

### Q: Can a review go backwards in states?
**A**: No. Revision only valid from "Changes requested" → "In review" → back to "Awaiting review" for reviewer.

---

## Recommended Reading Order

### For Understanding the System (30 minutes)
1. Developer Guide → Quick Start
2. Visual Diagrams → Diagram 1 (State Machine)
3. Visual Diagrams → Diagram 3 (Quality Pipeline)
4. Visual Diagrams → Diagram 9 (Realistic Workflow)

### For Implementing Changes (1-2 hours)
1. Developer Guide → Common Tasks section (relevant task)
2. Technical Analysis → Relevant part
3. Visual Diagrams → Database schema (Diagram 5)
4. Developer Guide → Testing guide

### For Optimization Work (2-4 hours)
1. Technical Analysis → Part 6 (Performance Optimization)
2. Technical Analysis → Part 4 (Memory Lifecycle)
3. Developer Guide → Performance Tuning section
4. Visual Diagrams → All diagrams (understand bottlenecks)

### For Incident Response (10-15 minutes)
1. Developer Guide → Troubleshooting section
2. Visual Diagrams → Error handling (Diagram 8)
3. Technical Analysis → Part 5 (Edge Cases)

---

## Metrics to Monitor

### Operational Metrics
- `review_submitted_total` — Gauge of reviews in system
- `review_cycle_time_seconds` — Histogram from "Awaiting" → "Approved"
- `review_awaiting_review_count` — Current reviews pending approval
- `review_revision_count` — How many iterations per review

### Quality Metrics
- `artifact_completeness_score` — Gauge of content completeness
- `artifact_quality_flags_total` — Count of flags raised
- `artifact_visual_feedback_generated_total` — LLM feedback calls

### Performance Metrics
- `review_approval_latency_ms` — Decision endpoint response time
- `qa_assessment_duration_seconds` — Time to extract quality signals
- `visual_qa_token_usage` — LLM tokens spent per artifact

### Error Metrics
- `review_approval_blocked_total` — Approval blocked (open comments)
- `review_permission_denied_total` — Access denied errors
- `qa_assessment_failed_total` — LLM feedback failures
- `artifact_integrity_check_failures` — Geometry/structure issues

---

## Deployment Considerations

### Prerequisites
- PostgreSQL/SQLite with `reviews` + `review_comments` tables
- Redis (optional, for SSE + image caching)
- LLM API access (optional, for visual feedback)

### Configuration
```env
# In .env
ENABLE_REVIEWS=true                      # Enable review API
REVIEW_APPROVE_RATE_LIMIT=20/minute      # Approval rate limit
ARTIFACT_RETENTION_DAYS=90                # Retention policy (per project)
VISUAL_QA_ENABLED=true                    # Enable LLM feedback
VISUAL_QA_MODEL=claude-opus-5-5           # Critique model
```

### Monitoring Setup
1. Export metrics to Prometheus
2. Create dashboards for review metrics
3. Set up alerts:
   - Stuck reviews (>7 days in "Awaiting review")
   - High error rate (>5% failed approvals)
   - Slow assessment (<1 artifact/min)

---

## Future Enhancements (Roadmap)

### Phase 1 (Q1 2027): Stability
- [ ] Add indexes for comment count queries
- [ ] Implement denormalized `open_comment_count` field
- [ ] Soft-delete reviews for compliance

### Phase 2 (Q2 2027): Performance
- [ ] Visual feedback image caching (Redis, 7d TTL)
- [ ] Artifact retention lifecycle (automated cleanup)
- [ ] Comment pagination (lazy-load for old reviews)

### Phase 3 (Q3 2027): Scale
- [ ] Archive timeline after 1000 entries
- [ ] Separate evidence cache
- [ ] Review analytics dashboard

### Phase 4 (Q4 2027): Intelligence
- [ ] Predictive approval routing
- [ ] Bulk approval (multiple artifacts at once)
- [ ] Custom feedback templates

---

## Appendix: Code Snippets

### Check if Review Can Be Approved
```python
# Key validation logic from src/app/api/reviews.py::decide()
if review.state not in {"Awaiting review", "In review"}:
    raise HTTPException(status_code=409, detail=f"Review is {review.state.lower()}")

open_comments = db.scalar(
    select(func.count()).select_from(ReviewComment).where(
        ReviewComment.review_id == review.id, ReviewComment.status == "Open"
    )
)
if open_comments > 0:
    raise HTTPException(status_code=409, detail="Resolve the open comments before approving")

# If passes both checks: review can be approved
review.state = "Approved"
db.commit()
```

### Extract Quality Signals
```python
# Key flow from src/evaluation/pptx_qa.py::extract_quality_signals()
prs = Presentation(str(artifact_path))

# Calculate scores
completeness_score = calculate_completeness(prs.slides)
design_score = assess_design(prs)
structure_score = assess_structure(prs)

# Detect issues
quality_flags = []
if completeness_score < 0.8:
    quality_flags.append("low_completeness")
if evidence_gate_failed:
    quality_flags.append("unsubstantiated_claims")
if geometry_issues:
    quality_flags.extend(geometry_issues)

# Return report
return {
    "completeness_score": completeness_score,
    "design_score": design_score,
    "structure_score": structure_score,
    "quality_flags": quality_flags,
    "evidence_gate": evidence_result
}
```

---

## Document Statistics

| Metric | Value |
|--------|-------|
| Total Pages | ~145 |
| Total Words | ~42,000 |
| Code Examples | 50+ |
| Diagrams | 9 major flows |
| Tables | 30+ |
| Links | Cross-referenced |
| Audience | Engineers, architects, PMs, DevOps |
| Estimated Read Time | 3-6 hours (full) / 30 min (quick) |

---

## How to Use This Analysis

### Option 1: Quick Orientation (30 min)
Read in this order:
1. This file → Overview section
2. Developer Guide → Quick Start
3. Visual Diagrams → Diagrams 1, 3, 9

### Option 2: Full Understanding (2-3 hours)
Read in this order:
1. This file → Entire document
2. Developer Guide → All sections
3. Visual Diagrams → All diagrams
4. Technical Analysis → Skip Part 6 (optional)

### Option 3: Deep Mastery (4-6 hours)
Read everything in order:
1. This file
2. Developer Guide
3. Visual Diagrams
4. Technical Analysis
5. Make notes on paper

### Option 4: Problem-Driven (Variable)
1. Start with Developer Guide → Troubleshooting
2. Jump to relevant section of Technical Analysis
3. Reference Visual Diagrams as needed

---

## Questions & Feedback

Found an issue in this analysis?
- Check if it's addressed in another document
- Verify against actual source code (`src/app/api/reviews.py`)
- Update this document with corrections

Need clarification?
- Consult Visual Diagrams first (often clearer than prose)
- Search across all three documents
- Refer to actual code files listed above

Have suggestions?
- Suggested improvements go in README.md
- Architectural changes go in CLAUDE.md
- Operational docs belong in docs/06-deployment-operations/

---

**Document Version**: 1.0  
**Created**: 2026-10-30  
**Format**: Markdown (3 files)  
**Total Size**: ~145 KB  
**Audience**: All engineering roles  
**Classification**: Architecture / Internal Documentation  

---

## Next Steps

1. **Read** the appropriate document for your role (see Navigation Guide above)
2. **Bookmark** this index for future reference
3. **Share** with team members who need to understand review section
4. **Update** as system evolves (add recommendations as they're implemented)
5. **Reference** in code reviews, design docs, incident reports

**Last Updated**: 2026-10-30  
**Maintainer**: Architecture Team  
**Review Cycle**: Quarterly (Q1, Q2, Q3, Q4)
