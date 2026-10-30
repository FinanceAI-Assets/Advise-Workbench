# Review Section: Visual Architecture Diagrams

**Comprehensive visual representation of approval workflows, data flows, and memory management patterns**

---

## Diagram 1: Complete Review Lifecycle State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                    REVIEW LIFECYCLE STATE MACHINE                │
└─────────────────────────────────────────────────────────────────┘

                          START (Draft)
                              │
                              ▼
                        ┌──────────────┐
                        │ Awaiting review
                        │ (v0.1)        │
                        └──────┬─────┬──┘
                               │     │
                          ┌────┘     └─────┐
                          │                │
                          ▼                ▼
                  ┌─────────────┐    ┌──────────────────┐
                  │  Approved   │    │ Changes requested│
                  │  (TERMINAL) │    │ (v0.1)           │
                  └─────────────┘    └──────┬───────────┘
                      △                     │
                      │                     │ Owner submits revision
                      │                     │ (increment version)
                      │                     ▼
                      │              ┌─────────────────┐
                      │              │ In review       │
                      │              │ (v0.2)          │
                      │              └────────┬────────┘
                      │                       │
                      └───────────────────────┘
                         Reviewer approves
                         & no open comments

TRANSITIONS:
├─ Awaiting review → Approved (reviewer: approve & all comments resolved)
├─ Awaiting review → Changes requested (reviewer: request_changes & note)
├─ Changes requested → In review (owner: submit_revision & all comments resolved)
└─ In review → Awaiting review (state resets after version increment)

STORAGE:
├─ Review.state: Current FSM state (DB column)
├─ Review.version_label: v0.1, v0.2, ... (incremented on revision)
├─ Review.payload_json: Approval timeline (append-only log)
└─ ReviewComment.status: Open | Resolved (per comment)
```

---

## Diagram 2: Approval Decision Flow

```
┌────────────────────────────────────────────────────────────────────┐
│         POST /api/reviews/{review_id}/decision                    │
└────────────────────────────────────────────────────────────────────┘

                        Decision Request Body
                        {
                          decision: "approve" | "request_changes"
                          note: "..."  (required for request_changes)
                        }
                              │
                              ▼
                   ┌──────────────────────┐
                   │ Load Review from DB  │
                   │ (validation)         │
                   └──────────┬───────────┘
                              │
                              ▼
                   ┌──────────────────────┐
                   │ Check: Is reviewer?  │
                   └──────────┬───────────┘
                              │
                        ┌─────┴─────┐
                        │           │
                    [YES]           [NO] → 403 Forbidden
                        │
                        ▼
                ┌─────────────────────────┐
                │ Which decision?         │
                └────┬──────────────┬─────┘
                     │              │
              [approve]      [request_changes]
                     │              │
                     ▼              ▼
        ┌──────────────────┐  ┌────────────────────┐
        │ Check open       │  │ Validate note      │
        │ comments = 0?    │  │ length > 0         │
        └────┬─────────┬───┘  └────┬────────────┬──┘
             │         │            │            │
          [0]|      [>0]        [OK]│       [EMPTY] → 422
             │         │            │
             ▼         ▼            ▼
         ┌────┐   ┌─────┐    ┌──────────────────┐
         │OK  │   │409  │    │ Set state =      │
         └────┘   │CONFLICT  │ "Changes req."   │
             │    └─────┘    │ Add comment      │
             │               └────────┬─────────┘
             └────┬────────────────────┘
                  │
                  ▼
         ┌──────────────────────────┐
         │ Update Review in DB       │
         ├─────────────────────────┐│
         │ • Review.state           ││
         │ • Review.payload_json    ││  ATOMIC
         │   (append timeline)      ││  TRANSACTION
         │ • Review.updated_at      ││
         │ • ReviewComment (if req) ││
         │ • EngagementMeta (stage) ││
         │ • Notification (if not   ││
         │   self-review)           ││
         └──────────────┬───────────┘│
                        ▼            │
              db.commit() ←──────────┘
                        │
                        ▼
         ┌──────────────────────────┐
         │ Return JSON Response      │
         │ { id, state }            │
         └──────────┬───────────────┘
                    │
                    ▼
         ┌──────────────────────────┐
         │ Frontend updates          │
         │ ApprovalBanner UI        │
         └──────────────────────────┘
```

---

## Diagram 3: Artifact Quality Signals Pipeline

```
┌────────────────────────────────────────────────────────────────────┐
│      ARTIFACT RENDER → QUALITY EXTRACTION → VISUAL FEEDBACK         │
└────────────────────────────────────────────────────────────────────┘

Run completes: prs.save() [artifact written to disk]
        │ workspace/{project_id}/runs/{run_id}/artifacts/deck_001.pptx
        │ (Binary OOXML, 2-50 MB)
        │
        ▼
┌──────────────────────────────────────┐
│ extract_quality_signals()            │
│ (src/evaluation/pptx_qa.py)          │
├──────────────────────────────────────┤
│ INPUT:                               │
│  • artifact_path: Path to .pptx      │
│  • run_dir: workspace/.../artifacts/ │
│                                      │
│ PROCESS:                             │
│  1. Load artifact from disk          │
│     Presentation obj: ~50-100 KB     │
│                                      │
│  2. PPTX QA Checks:                  │
│     ├─ Slide count (≤ 20)            │
│     ├─ Completeness scoring          │
│     ├─ Design review                 │
│     ├─ Geometry validation           │
│     ├─ Placeholder detection         │
│     └─ Evidence gate                 │
│                                      │
│  3. Calculate scores                 │
│     ├─ completeness_score: 0–1.0     │
│     ├─ design_score: 0–1.0           │
│     ├─ structure_score: 0–1.0        │
│     └─ overall: weighted avg         │
│                                      │
│  4. Generate quality_flags           │
│     [                                │
│       "missing_speaker_notes_3",     │
│       "geometry_issue_slide_5",      │
│       "evidence_unsubstantiated_7"   │
│     ]                                │
│                                      │
│ OUTPUT:                              │
│  QA Report dict (~500 B)             │
│  {                                   │
│    completeness_score: 0.92,         │
│    design_score: 0.88,               │
│    structure_score: 0.95,            │
│    quality_flags: [...],             │
│    evidence_gate: {...},             │
│    geometry_issues: [...]            │
│  }                                   │
│                                      │
│ MEMORY:                              │
│  Peak: ~300 KB (released after)      │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Emit RunEvent('artifact_rendered')   │
│ (src/workflows/run_events.py)        │
├──────────────────────────────────────┤
│ Persist to: run_events table (DB)    │
│ Payload: QA scores + flags           │
│ Storage: immutable audit trail       │
└──────────┬───────────────────────────┘
           │ [QA scores satisfy threshold]
           │ [Visual feedback needed]
           │
           ▼
┌──────────────────────────────────────┐
│ evaluate_visual_feedback()           │
│ (src/evaluation/visual_qa.py)        │
├──────────────────────────────────────┤
│ INPUT:                               │
│  • artifact_path: Path to .pptx      │
│  • qa_report: Scores dict            │
│                                      │
│ PROCESS:                             │
│  1. Extract slide metadata           │
│     ├─ Text lines per slide          │
│     ├─ Slide structure               │
│     ├─ Text density metrics          │
│     └─ Layout types                  │
│                                      │
│  2. Render images (optional)         │
│     ├─ pypdfium2.PdfDocument()       │
│     ├─ Top 12 pages → PNG            │
│     └─ Memory: 36 MB peak (tempfile) │
│                                      │
│  3. Call LLM (critique_model)        │
│     ├─ Input: Images + text context  │
│     ├─ System: Design review prompt  │
│     └─ Tokens: ~10k input            │
│                                      │
│  4. Parse feedback JSON              │
│     [                                │
│       {                              │
│         slide_index: 3,              │
│         feedback_type: design_review │
│         message: "...",              │
│         confidence: 0.85             │
│       },                             │
│       ...                            │
│     ]                                │
│                                      │
│ OUTPUT:                              │
│  Feedback list (~2-5 KB)             │
│                                      │
│ MEMORY:                              │
│  Peak: 36 MB (images) → Released     │
└──────────┬───────────────────────────┘
           │
           ▼
┌──────────────────────────────────────┐
│ Storage & Distribution               │
├──────────────────────────────────────┤
│ 1. DB: RunEvent.payload              │
│    (immutable audit trail)           │
│                                      │
│ 2. FS: qa_report_pptx.json           │
│    workspace/.../artifacts/          │
│                                      │
│ 3. FS: pptx_visual_feedback.json     │
│    workspace/.../artifacts/          │
│                                      │
│ 4. SSE: Broadcast to frontend        │
│    Real-time review display          │
│                                      │
│ 5. Cache: Redis (optional)           │
│    Images: TTL 7 days                │
└──────────────────────────────────────┘
```

---

## Diagram 4: Memory Lifecycle Across Request Scopes

```
┌────────────────────────────────────────────────────────────────────┐
│           REQUEST LIFECYCLE & MEMORY ALLOCATION                    │
└────────────────────────────────────────────────────────────────────┘

TIME         REQUEST 1                       REQUEST 2
             (Quality Assessment)            (Approval Decision)
             ────────────────────            ──────────────────
             
t₀           ┌──────────────────┐
│            │ Start request    │
│            │ Memory: 100 B    │
│            └────────┬─────────┘
│                     │
t₁           ┌────────▼──────────┐
│            │ Load artifact     │
│            │ (50-100 KB)       │
│            └────────┬──────────┘
│                     │
t₂           ┌────────▼──────────┐            ┌──────────────────┐
│            │ Extract QA        │            │ Start request    │
│            │ (~300 KB peak)    │            │ Memory: 100 B    │
│            └────────┬──────────┘            └────────┬─────────┘
│                     │                               │
t₃           ┌────────▼──────────┐            ┌────────▼──────────┐
│            │ LLM visual        │            │ Load Review       │
│            │ feedback call     │            │ (5-10 KB)         │
│            │ (36 MB images)    │            └────────┬──────────┘
│            └────────┬──────────┘                     │
│                     │                    ┌──────────▼──────────┐
t₄           ┌────────▼──────────┐        │ Validate reviewer   │
│            │ Emit RunEvent     │        └────────┬──────────┘
│            │ (DB write)        │                 │
│            │ Memory: 2 KB      │    ┌────────────▼──────────┐
│            └────────┬──────────┘    │ Load open comments    │
│                     │               │ count (DB query)      │
t₅           ┌────────▼──────────┐    │ Memory: 100 B        │
│            │ Write feedback    │    └────────┬──────────┘
│            │ JSON to FS        │             │
│            │ (5 KB)            │ ┌──────────▼──────────┐
│            └────────┬──────────┘ │ Update Review row   │
│                     │            │ Append timeline     │
t₆           ┌────────▼──────────┐ │ Create Notification │
│            │ Return response   │ │ (DB transaction)    │
│            │ to client         │ │ Memory: 300 B       │
│            │                   │ └────────┬──────────┘
│            │ GC: Release       │          │
│            │ • Presentation    │ ┌────────▼──────────┐
│            │ • QA scores       │ │ db.commit()       │
│            │ • Feedback list   │ │ (ACID guarantee)  │
│            │ • Images          │ │ Memory: 0 B       │
│            │ Memory: 100 B     │ └────────┬──────────┘
│            └────────┬──────────┘          │
│                     │            ┌────────▼──────────┐
t₇           ┌────────▼──────────┐ │ Return response   │
│            │ Request complete  │ │ { id, state }     │
│            │ Memory: 0 B       │ │ Memory: 0 B       │
│            └──────────────────┘ └──────────────────┘
│

MEMORY FOOTPRINT OVER TIME:

400 KB |           ┌─────────────────┐
       |          ╱                  ╲
300 KB |  ┌──────╱                    ╲────┐
       | ╱                                 ╲
200 KB |                                    ╲
       |                                     
100 KB | ┌───────────┐           ┌──────────┐
       |╱            ╲          ╱           ╲
   0 B └──────────────────────────────────────

       t₀  t₁  t₂  t₃  t₄  t₅  t₆  t₇

Key: Request 1 (Quality) uses up to 300+ KB peak (tempfile images)
     Request 2 (Approval) uses <20 KB constant
```

---

## Diagram 5: Database Schema Relationships (Review Section)

```
┌────────────────────────────────────────────────────────────────────┐
│              REVIEW SECTION ENTITY RELATIONSHIP DIAGRAM            │
└────────────────────────────────────────────────────────────────────┘

┌──────────────┐
│    User      │
├──────────────┤
│ id (PK)      │
│ email        │
│ is_admin     │
└──────┬───┬──┘
       │   │
  [owner] [reviewer]
       │   │
       │   └──────────────┐
       │                  │
       ▼                  ▼
┌──────────────────────────────────────────┐
│            Review                        │
├──────────────────────────────────────────┤
│ id (PK)              VARCHAR(64)         │◄───┐
│ project_id (FK)      VARCHAR(64)         │    │
│ run_id (FK)          VARCHAR(64)         │    │
│ title                VARCHAR(255)        │    │
│ artifact_type        "pptx"|"docx"       │    │
│ version_label        "v0.1", "v0.2"...   │    │
│ owner_id (FK → User) VARCHAR(64)         │    │
│ reviewer_id (FK→User)VARCHAR(64)         │    │
│ due_date             DATETIME            │    │ (FK)
│ state                VARCHAR(32)         │    │
│   • "Awaiting review"                    │    │
│   • "Changes requested"                  │    │
│   • "In review"                          │    │
│   • "Approved"                           │    │
│ payload_json         TEXT                │    │
│   {                                      │    │
│     approvalTimeline: [{...}],           │    │
│     evidenceChecks: [{...}],             │    │
│     slide: {...}                         │    │
│   }                                      │    │
│ created_at           DATETIME            │    │
│ updated_at           DATETIME            │    │
└──────────┬───────────────────────────────┘    │
           │                                     │
           │ (1:N)                              │
           ▼                                     │
┌──────────────────────────────────────────┐    │
│         ReviewComment                    │    │
├──────────────────────────────────────────┤    │
│ id (PK)              INTEGER             │    │
│ review_id (FK) ──────────────────────────┼────┘
│ author               VARCHAR(255)        │
│ title                VARCHAR(255)        │
│ body                 TEXT                │
│ anchor               VARCHAR(64)         │ (optional slide ref)
│ status               "Open"|"Resolved"   │
│ created_at           DATETIME            │
└──────────────────────────────────────────┘


Related entities (for context):

┌──────────────────────────────────────────┐
│              Run                         │
├──────────────────────────────────────────┤
│ id (PK)              VARCHAR(64)         │◄─── Review.run_id (FK)
│ project_id (FK)      VARCHAR(64)         │
│ status               VARCHAR(32)         │
│ review_ready         BOOLEAN             │
│ approval_metadata_json TEXT              │
│ created_at           DATETIME            │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│            RunEvent                      │
├──────────────────────────────────────────┤
│ id (PK)              INTEGER             │
│ run_id (FK)          VARCHAR(64)         │
│ event_type           VARCHAR(64)         │
│   "artifact_rendered"                    │
│   "quality_checked"                      │
│ payload              TEXT (JSON)         │◄─── QA scores, feedback
│ created_at           DATETIME            │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│          EngagementMeta                  │
├──────────────────────────────────────────┤
│ project_id (FK)      VARCHAR(64)         │◄─── Review.project_id
│ stage                VARCHAR(32)         │◄─── Updated on approval
│   "Brief"                                │
│   "In review"                            │
│   "Approved"                             │
│ retention_days       INTEGER             │
│ updated_at           DATETIME            │
└──────────────────────────────────────────┘

INDEXES (for performance):
├─ reviews(project_id) — fast review list per engagement
├─ reviews(reviewer_id) — find my assigned reviews
├─ reviews(owner_id) — find my submitted reviews
├─ reviews(state) — filter by workflow state
├─ review_comments(review_id, status) — count open comments (approval validation)
└─ run_events(run_id, event_type) — retrieve QA signals
```

---

## Diagram 6: Concurrent Request Handling & Thread Safety

```
┌────────────────────────────────────────────────────────────────────┐
│        CONCURRENCY PATTERNS & POTENTIAL RACE CONDITIONS             │
└────────────────────────────────────────────────────────────────────┘

SCENARIO 1: Approve While Comment Added

Thread A (Approval)              Thread B (Comment)          Database
────────────────────            ─────────────────           ────────

GET review.id = "RV-101"
  │                             
  ├─ SELECT COUNT(*)            
  │  FROM review_comments       
  │  WHERE status='Open'        
  │  → Result: 0 comments       
  │                             POST /comments
  │                             │   ├─ INSERT ReviewComment
  │                             │   │ (status='Open')
  │                             │   └─ COMMIT
  │                             │       [RACE POINT: Comment
  │                             │        added but A already
  │                             │        verified count=0]
  │
  ├─ UPDATE Review.state='Approved'
  │ WHERE count=0
  │ → SUCCESS (but comment exists!)
  │
  └─ db.commit()
    → PROBLEM: Approved with open comment!

MITIGATION (CURRENT):
├─ Recheck count immediately before UPDATE
├─ Use state machine: approve only from valid states
└─ Return 409 CONFLICT if race detected on retry

SOLUTION (RECOMMENDED):
├─ Add FOREIGN KEY constraint: Can't approve if comments exist
├─ Or use pessimistic locking: LOCK IN EXCLUSIVE MODE
└─ Or accept race + require manual reconsideration


SCENARIO 2: Revision While Approval Pending

Thread A (Revision)             Thread B (Approval)         Database
───────────────────            ──────────────────         ────────

POST /submit-revision           
  │                             POST /decision
  ├─ Check: state='Changes req'
  │   state='Changes req' ✓     │
  │                             ├─ Check: open comments
  ├─ UPDATE state='In review'   │   → open comments: 0
  │ version='v0.2'              │
  │ COMMIT                      ├─ UPDATE state='Approved'
  │   [SUCCESS]                 │   WHERE version='v0.1'
  │                             │   → Updates WRONG version!
  │   [STATE: version='v0.2'    │
  │    state='In review']       └─ db.commit()
  │
  └─ Result: Review shows version='v0.2'
    but approval timestamp is for v0.1!

MITIGATION (CURRENT):
├─ State machine enforces order: Can't revise from 'In review'
└─ Reviewer checks version before approving

SOLUTION (RECOMMENDED):
├─ Optimistic locking: Add version_number column
├─ Reject approval if version changed since load
└─ Require explicit recheck if version bumped


SCENARIO 3: Parallel Artifact Renders (Quality Assessment)

Thread A (PPTX Render)          Thread B (DOCX Render)      Filesystem
──────────────────────          ──────────────────────      ──────────

Load: deck_001.pptx             Load: report_001.docx
Size: 10 MB                     Size: 5 MB
Memory: 50 KB                   Memory: 50 KB
  │                               │
  ├─ Extraction: +250 KB          ├─ Extraction: +250 KB
  │ [Peak: ~300 KB]               │ [Peak: ~300 KB]
  │                               │
  ├─ Call LLM visual feedback    [Independent execution]
  │ Create PNG images             No shared state
  │ Memory: +36 MB (tempfile)     (Different artifacts)
  │ [Peak: ~36.3 MB]              
  │                               
  ├─ Cleanup temp images         ├─ LLM call
  │ Memory: back to 50 KB         │ [Running in parallel]
  │                               │
  └─ Emit RunEvent               ├─ Cleanup
    (DB write)                    └─ Emit RunEvent
                                   (DB write)

TOTAL MEMORY WITH BOTH:
├─ Thread A (PPTX): ~36.3 MB (peak)
├─ Thread B (DOCX): ~0.3 MB
├─ Framework overhead: ~10 MB
└─ TOTAL: ~46.6 MB (well within 512 MB Python limits)

✓ NO RACE CONDITION: Each artifact processed independently
✓ NO SHARED STATE: Tempfiles are process-private
✓ SCALABLE: 10 concurrent renders = ~460 MB (acceptable)
```

---

## Diagram 7: Storage Persistence Model

```
┌────────────────────────────────────────────────────────────────────┐
│       MULTI-TIER PERSISTENCE: DB vs FILESYSTEM vs CACHE             │
└────────────────────────────────────────────────────────────────────┘

Data Type                   Tier 1: DB          Tier 2: Filesystem    Tier 3: Cache
─────────────────────────   ──────────         ──────────────────    ─────────────

Review metadata             Review row         N/A                   N/A
(state, version, etc)       (persistent)       

Approval timeline           payload_json       N/A                   N/A
(audit trail)              (persistent)       

ReviewComments             ReviewComment       N/A                   N/A
(open issues)              rows                (persistent)          

QA scores                  RunEvent.payload    qa_report_*.json      Redis (1h TTL)
(completeness, design)      (immutable)        (debug export)        

Visual feedback            RunEvent.payload    pptx_visual_          Redis (7d TTL)
(design review)            (immutable)         feedback.json         

Evidence validation        RunEvent.payload    (integrated into      N/A
(citation checks)          (immutable)         visual feedback)       

Artifact files             N/A                 deck_*.pptx           N/A
(PPTX/DOCX/XLSX)                              (workspace/)          

Temporary files            N/A                 tempdir/*.png         N/A
(rendered images)                              (auto-delete)         

Branding context           ProjectBrand        N/A                   Redis (24h TTL)
(colors, fonts)            table               

Notification queue         Notification        N/A                   Redis queue
(approval alerts)          table               (if Redis backend)


WRITE PATTERNS:

┌─ INSERT Review row
├─ on: submit_for_review()
└─ → DB commit (ACID)

┌─ UPDATE Review state + payload_json
├─ on: decide(), submit_revision()
└─ → DB commit (ACID, transactional)

┌─ INSERT ReviewComment
├─ on: add_comment()
└─ → DB commit

┌─ INSERT RunEvent (artifact_rendered)
├─ on: extract_quality_signals() + emit_event()
└─ → DB write (part of run orchestrator transaction)

┌─ WRITE qa_report_*.json
├─ on: optional debug export
├─ path: workspace/{project_id}/runs/{run_id}/
└─ → filesystem (non-critical)

┌─ WRITE pptx_visual_feedback.json
├─ on: evaluate_visual_feedback() completes
├─ path: workspace/{project_id}/runs/{run_id}/
└─ → filesystem (non-critical, also in DB)


READ PATTERNS:

┌─ SELECT Review + comments
├─ on: get_review() API call
├─ result: ~10-50 KB JSON response
└─ → serves to frontend

┌─ SELECT count(ReviewComment WHERE status='Open')
├─ on: approve validation
├─ result: integer count
└─ → gates approval decision (409 if count > 0)

┌─ SELECT RunEvent WHERE event_type='artifact_rendered'
├─ on: review page loads
├─ result: QA report from DB
└─ → displays quality scores + flags

┌─ READ qa_report_*.json
├─ on: optional manual review of QA results
├─ path: filesystem
└─ → useful for debugging

┌─ READ artifact (.pptx, .docx, etc)
├─ on: download from API
├─ size: 2-50 MB
└─ → streamed to client


CONSISTENCY GUARANTEES:

Database (ACID):
├─ Atomicity: All review updates in single transaction
├─ Consistency: State machine constraints enforced
├─ Isolation: Serializable isolation level (on PostgreSQL)
└─ Durability: Committed data survives crashes

Filesystem (Eventual Consistency):
├─ QA reports written after DB commit
├─ Safe to lose (recomputable from artifact)
└─ No read-before-write requirements

Cache (TTL-based):
├─ Branding: 24h TTL (project lifecycle)
├─ Images: 7d TTL (allow re-review without re-render)
└─ Stale data acceptable (invalidated on update)
```

---

## Diagram 8: Error Handling & Retry Patterns

```
┌────────────────────────────────────────────────────────────────────┐
│         ERROR HANDLING & RECOVERY STRATEGIES                        │
└────────────────────────────────────────────────────────────────────┘

APPROVAL DECISION ERROR CASES:

┌─ 404 Not Found
│  └─ Review doesn't exist
│     ├─ Cause: Stale client link, concurrent deletion
│     └─ Recovery: Return 404, suggest refresh

├─ 403 Forbidden
│  └─ User not assigned reviewer
│     ├─ Cause: Security check, wrong user
│     └─ Recovery: Return 403, suggest login as correct user

├─ 409 Conflict
│  ├─ Open comments exist (approve case)
│  │  ├─ Cause: Race condition (comment added after verification)
│  │  └─ Recovery: Require user to refresh + recheck comments
│  │
│  └─ Review state invalid (revision case)
│     ├─ Cause: State changed by another user
│     └─ Recovery: Return 409 with current state, suggest refresh

├─ 422 Unprocessable Entity
│  └─ Request validation failed (missing note for request_changes)
│     ├─ Cause: Client didn't provide required field
│     └─ Recovery: Return 422 with field error, require input


QA SIGNAL GENERATION ERROR CASES:

┌─ LLM feedback fails (timeout/invalid JSON)
│  ├─ Impact: No design review feedback
│  ├─ Cause: LLM API error, timeout
│  └─ Recovery:
│     ├─ Log exception
│     ├─ Return empty feedback list (fail-open)
│     ├─ Still emit artifact_rendered event (with empty feedback)
│     └─ Review continues without design feedback


DATABASE WRITE ERROR CASES:

┌─ db.commit() fails (deadlock, connection lost)
│  ├─ Impact: Decision not persisted
│  ├─ Cause: Concurrent transaction conflict, network issue
│  └─ Recovery:
│     ├─ Catch exception at API layer
│     ├─ Rollback transaction (SQLAlchemy auto-rollback)
│     ├─ Return 500 Internal Server Error
│     ├─ Log full stack trace
│     └─ Recommend retry (idempotent if retry uses same decision ID)


ARTIFACT DISAPPEARANCE:

┌─ Artifact file deleted but Review/QA data exists
│  ├─ Impact: Can't recompute QA or download artifact
│  ├─ Cause: Manual deletion, retention policy cleanup
│  └─ Recovery:
│     ├─ Review/comments still accessible (DB-backed)
│     ├─ QA scores cached in RunEvent (available)
│     ├─ Return 404 if user tries to download
│     └─ Suggest regeneration (new run needed)


RETRY STRATEGY FOR IDEMPOTENT OPERATIONS:

┌─ Decision endpoint (approve/request_changes)
│  ├─ Idempotency: Approve same decision twice → 409
│  ├─ Not fully idempotent (side effects: notification)
│  └─ Recommendation:
│     ├─ Add idempotency key to request headers
│     ├─ Cache decision result by (review_id, user_id, timestamp window)
│     └─ Return cached result on retry within window

└─ Revision endpoint (submit_revision)
   ├─ Idempotency: Resubmit same revision → version increments
   ├─ Not idempotent (version bumps on each call)
   └─ Recommendation:
      ├─ Frontend tracks submission state locally
      ├─ Disable resubmit button during submission
      └─ Use optimistic update with rollback on error
```

---

## Diagram 9: Approval Workflow Timeline (Multi-Actor Scenario)

```
┌────────────────────────────────────────────────────────────────────┐
│     REALISTIC APPROVAL WORKFLOW: ALICE → BOB → ALICE (revision)     │
└────────────────────────────────────────────────────────────────────┘

Time    Alice (Author)           Bob (Reviewer)          Review State
────    ──────────────           ──────────────          ────────────

10:00   Finishes draft            
        deck_001.pptx
        (48 slides)
        
        submit_for_review()
        ├─ POST /reviews
        │  project_id=proj_123
        │  artifact_type=pptx
        │  reviewer_id=bob_id
        │
        └─ CREATE Review           
          id=RV-101
          state='Awaiting review'  State: Awaiting review
          version=v0.1
          
                                   🔔 Notification: "RV-101 ready for review"

10:15                              Opens review page
                                   get_review(RV-101)
                                   ├─ Load QA scores
                                   │  completeness: 0.78 (low!)
                                   │  design: 0.82
                                   │  flags: ["missing_speaker_notes_15"]
                                   │
                                   └─ Load comments
                                      (empty initially)

10:20                              add_comment()
                                   ├─ POST /reviews/RV-101/comments
                                   │  title: "Slide 15: Missing speaker notes"
                                   │  body: "Slide 15 title mentions 'Key insights'
                                   │         but has no speaker notes to explain.
                                   │         Add 2-3 sentences."
                                   │  anchor: "slide_15"
                                   │
                                   └─ CREATE ReviewComment (status=Open)
                                      id=1
                                   
                                      🔔 Notification: "Bob commented on RV-101"
        
10:25   🔔 Notification received
        Views comment
        ├─ Agrees with feedback
        └─ Decides to revise
        
        Re-renders deck offline
        Updates slide 15 with notes
        deck_002.pptx (new local file)

10:30                              Waits for revision
                                   (Reviews other work)

10:45   Uploads revised deck       
        ├─ Updates workspace/artifacts/
        │  (via manual upload or regeneration)
        │
        └─ submit_revision()
           POST /reviews/RV-101/submit-revision
           ├─ Check: state == 'Changes requested'?
           │  ✗ Current state = 'Awaiting review'
           │  → BLOCKED: Can't submit revision yet
           │
           └─ ERROR: Need Bob to request changes first
           
           🔔 Alice realizes: Bob hasn't formally rejected yet
              (comment doesn't trigger state change)

                                   resolve_comment()
                                   ├─ POST /reviews/RV-101/comments/1/resolve
                                   │  → Comment.status = 'Resolved'
                                   │
                                   └─ EMIT timeline: "Comment addressed..."
                                   
                                   decide()
                                   ├─ POST /reviews/RV-101/decision
                                   │  decision: 'request_changes'
                                   │  note: "Good revision. Slide 15 notes are clear now.
                                   │         Ready for formal review."
                                   │
                                   └─ UPDATE Review
                                      state = 'Changes requested'
                                      ├─ CREATE ReviewComment (auto: system comment)
                                      │  from: Bob
                                      │  title: "Changes requested"
                                      │  body: "[Bob's feedback]"
                                      │
                                      └─ EMIT timeline: "Changes requested"
                                      
                                      State: Changes requested
                                      
                                      🔔 Notification: "Alice, changes requested on RV-101"

11:00   🔔 Notification received
        Sees Bob's formal feedback
        
        submit_revision()
        ├─ Check: state == 'Changes requested'? ✓
        ├─ Check: open_comments == 0? ✓
        ├─ UPDATE Review
        │  version_label: v0.1 → v0.2
        │  state: 'In review'
        │
        └─ EMIT timeline: "Revised v0.2 submitted"
        
        State: In review (v0.2)
        
        🔔 Notification: "Bob, v0.2 ready for review"

11:05                              Sees notification
                                   
                                   get_review(RV-101)
                                   ├─ Loads v0.2 metadata
                                   ├─ Re-extracts QA for new artifact
                                   │  completeness: 0.95 (much better!)
                                   │  design: 0.92
                                   │  flags: [] (no flags)
                                   │
                                   └─ Reviews new slides
                                      (only ~2 changed)

11:10                              decide()
                                   ├─ POST /reviews/RV-101/decision
                                   │  decision: 'approve'
                                   │  note: ''
                                   │
                                   └─ UPDATE Review
                                      state = 'Approved'
                                      
                                      ├─ CHECK: All reviews for this project approved?
                                      │  → YES
                                      │
                                      └─ UPDATE EngagementMeta
                                         stage = 'Approved'
                                      
                                      State: Approved ✓
                                      
                                      🔔 Notification: "Alice, RV-101 approved!"

11:15   🔔 Notification received
        Sees approval
        ├─ Review complete
        └─ Can now export/deliver artifacts


APPROVAL TIMELINE (Audit Trail):

[✓] 10:00 - "Submitted for review" by Alice · edit icon
[✓] 10:20 - "Comment added: Slide 15: Missing speaker notes" by Bob · comment icon
[✓] 10:50 - "Comment addressed: Slide 15: Missing speaker notes" by Bob · check icon
[✓] 10:50 - "Changes requested" by Bob · comment icon
[✓] 11:00 - "Revised v0.2 submitted" by Alice · edit icon
[✓] 11:10 - "Approved v0.2" by Bob · check icon

DATABASE STATE AT COMPLETION:

Review:
├─ state: 'Approved'
├─ version_label: 'v0.2'
└─ payload_json:
   {
     "approvalTimeline": [7 entries],
     "evidenceChecks": [...],
     "slide": {...}
   }

ReviewComments:
├─ id=1: "Slide 15..." (status=Resolved)
├─ id=2: "Changes requested" (status=Open, auto-created)
└─ [no others]

EngagementMeta:
└─ stage: 'Approved'
```

---

## Summary of Visual Patterns

| Pattern | Where | Key Property |
|---------|-------|--------------|
| **State Machine** | Review.state | Ordered transitions prevent invalid states |
| **Audit Trail** | Review.payload_json + RunEvent | Immutable append-only log |
| **Optimistic Reads** | Comment count validation | Read-check-write pattern (some race risk) |
| **ACID Transactions** | db.commit() | All-or-nothing state updates |
| **Fail-Open Feedback** | LLM error handling | Missing feedback doesn't block approval |
| **Tempfile Cleanup** | Image rendering | Auto-delete on scope exit |
| **Multi-Tier Storage** | DB + FS + Cache | Each tier for different access patterns |

---

**Document Version**: 1.0  
**Visual Diagrams**: 9 major flows  
**Last Updated**: 2026-10-30  
**Format**: ASCII diagrams + Mermaid-compatible descriptions
