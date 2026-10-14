"""Seed (or clear) the illustrative workbench demo data shown in the UI design.

    DEMO_SEED_PASSWORD=<password> python -m scripts.seed_demo          # create or refresh
    python -m scripts.seed_demo --clear                                # remove it again

Idempotent: every demo row has an id starting with "demo" (or a fixed design
code such as RV-104), so a second run updates in place and --clear removes only
what this script created. Refuses to run when ADVISE_WORKBENCH_ENV is production.
All names and organizations are fictional. Demo accounts use the allowed sign-in domain, so load them only
into a local or demonstration database: an address may match a real colleague's.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select

from src.core.auth import allowed_email_domains, get_password_hash
from src.core.config import settings
from src.core.db.models import (
    ActivityEvent,
    Conversation,
    ConversationMessage,
    EngagementMeta,
    LpPractice,
    Membership,
    Notification,
    Project,
    Review,
    ReviewComment,
    Run,
    SavedPractice,
    User,
    WorkbenchRecord,
)
from src.core.db.session import init_db, session_scope
from src.core.storage import ensure_workspace, workspace_path

SEED_DIR = Path(__file__).resolve().parents[1] / "data" / "seed" / "workbench"
RUN_ID = "run_demo_ns118"
NORTHSTAR = "p_demo_ns042"

USERS = [
    ("u_demo_alex", "alex.chen", "Alex Chen", "Engagement lead", False),
    ("u_demo_priya", "priya.shah", "Priya Shah", "Engagement reviewer", False),
    ("u_demo_sam", "sam.rivera", "Sam Rivera", "Contributor", False),
    ("u_demo_maya", "maya.patel", "Maya Patel", "Practice owner", False),
    ("u_demo_jamie", "jamie.lee", "Jamie Lee", "Analyst", False),
    ("u_demo_jordan", "jordan.kim", "Jordan Kim", "Platform administrator", True),
]

# id, name, code, type, stage, progress, next task, due, start, close, classification, retention, members
ENGAGEMENTS = [
    (NORTHSTAR, "Northstar transformation", "NS-042", "Operating model redesign", "Drafting", 64,
     "Resolve 2 review comments", "2026-10-12", "2026-09-28", "2026-11-30", "Internal · Engagement-scoped", 180,
     [("alex", "Engagement lead"), ("priya", "Independent reviewer"), ("sam", "Contributor"),
      ("maya", "Practice advisor"), ("jamie", "Viewer")]),
    ("p_demo_me019", "Meridian service excellence", "ME-019", "Service excellence", "In review", 82,
     "Approve executive memo", "2026-10-09", "2026-09-14", "2026-11-14", "Internal · Engagement-scoped", 180,
     [("priya", "Engagement lead"), ("alex", "Independent reviewer"), ("maya", "Contributor")]),
    ("p_demo_at031", "Atlas finance modernization", "AT-031", "Finance modernization", "Sources", 36,
     "Validate evidence scope", "2026-10-14", "2026-10-01", "2026-12-18", "Restricted · Engagement-scoped", 365,
     [("sam", "Engagement lead"), ("alex", "Contributor"), ("maya", "Independent reviewer")]),
    ("p_demo_ce012", "Cedar change readiness", "CE-012", "Change readiness", "Approved", 100,
     "Export adoption toolkit", "2026-10-10", "2026-08-17", "2026-10-16", "Internal · Engagement-scoped", 180,
     [("maya", "Engagement lead"), ("alex", "Contributor"), ("priya", "Independent reviewer")]),
    ("p_demo_hg028", "Horizon governance reset", "HG-028", "Governance reset", "Brief", 18,
     "Confirm sponsor objectives", "2026-10-16", "2026-10-05", "2026-12-04", "Internal · Engagement-scoped", 180,
     [("alex", "Engagement lead"), ("sam", "Independent reviewer")]),
    ("p_demo_su007", "Summit operating rhythm", "SU-007", "Operating rhythm", "Sources", 30,
     "Index leadership interview notes", "2026-10-19", "2026-10-05", "2026-12-11", "Internal · Engagement-scoped", 180,
     [("priya", "Engagement lead"), ("alex", "Contributor")]),
    ("p_demo_pi015", "Pioneer shared services", "PI-015", "Shared services design", "Drafting", 55,
     "Draft service catalogue options", "2026-10-21", "2026-09-21", "2026-12-01", "Internal · Engagement-scoped", 180,
     [("sam", "Engagement lead"), ("alex", "Contributor")]),
    ("p_demo_lu023", "Lumen controls uplift", "LU-023", "Controls uplift", "Brief", 10,
     "Agree control scope with sponsor", "2026-10-23", "2026-10-07", "2026-12-15", "Restricted · Engagement-scoped", 365,
     [("maya", "Engagement lead"), ("alex", "Viewer")]),
]
_ROLE = {"Engagement lead": "Owner", "Viewer": "Viewer"}

NORTHSTAR_BRIEF = {
    "client_org": "Northstar (illustrative)",
    "brief": "Design a future-state operating model and a practical 90-day transformation roadmap.",
    "sponsor_objective": "Improve accountability and execution",
    "scope": "Shared services · 3 functional areas",
    "success_measures": "Ownership clarity · Pilot adoption · Escalation resolution",
}

MILESTONES = [
    ("m1", "Discovery & evidence baseline", "Sam Rivera", "2026-10-06", "Complete"),
    ("m2", "Roadmap & recommendations", "Alex Chen", "2026-10-12", "Drafting"),
    ("m3", "Sponsor review & export", "Priya Shah", "2026-10-16", "Scheduled"),
]

# when, actor, kind, title, detail
ACTIVITY = [
    ("2026-10-07 10:30", "Alex Chen", "brief", "Brief confirmed", "Sponsor objective validated."),
    ("2026-10-07 14:12", "Alex Chen", "review", "Roadmap v0.7 submitted", ""),
    ("2026-10-07 16:24", "Priya Shah", "review", "Changes requested",
     "RV-104 · Evidence gap and pilot accountability comments added."),
    ("2026-10-06 11:05", "Maya Patel", "library", "Operating model playbook updated",
     "Approved library release · v3.2"),
    ("2026-10-08 09:40", "Sam Rivera", "source", "6 engagement documents indexed", "JOB-207 · Complete"),
    ("2026-10-08 09:42", "Alex Chen", "deck", "Northstar roadmap v0.8 created",
     "RUN-118 · Review fixes prepared; not yet resubmitted."),
    ("2026-10-08 09:45", "System", "evidence", "Evidence check completed",
     "RV-104 · 22 of 23 claims cited. Benefits assumption remains unsupported."),
]

# id, project, run, title, type, version, owner, reviewer, due, state, risk
REVIEWS = [
    ("RV-104", NORTHSTAR, RUN_ID, "Transformation roadmap", "pptx", "v0.8", "alex", "priya", "2026-10-12",
     "Changes requested", "Medium risk"),
    ("DR-042-02", NORTHSTAR, RUN_ID, "Operating model recommendations", "docx", "v0.6", "alex", None, "",
     "Draft", ""),
    ("RV-101", "p_demo_me019", None, "Meridian executive memo", "docx", "v1.2", "priya", "alex", "2026-10-09",
     "In review", "Low risk"),
    ("RV-099", "p_demo_ce012", None, "Cedar adoption toolkit", "pptx", "v1.0", "maya", "priya", "2026-10-10",
     "Approved", "Low risk"),
    ("RV-106", "p_demo_at031", None, "Atlas finance memo", "docx", "v0.4", "sam", "maya", "2026-10-14",
     "Awaiting review", "Medium risk"),
    ("RV-108", "p_demo_hg028", None, "Horizon discovery summary", "docx", "v0.2", "alex", "sam", "2026-10-16",
     "Assigned", "Low risk"),
    ("LP-041", None, None, "Benefits toolkit", "practice", "v2.1", "maya", "priya", "2026-10-09",
     "Attribution gap", "Medium risk"),
    ("LP-052", None, None, "Service handoff guide", "practice", "v1.1", "sam", "maya", "2026-10-11",
     "Quality review", "Low risk"),
    ("LP-063", None, None, "Control design guide", "practice", "v1.3", "maya", "sam", "2026-10-13",
     "Quality review", "Low risk"),
    ("LP-072", None, None, "Adoption metrics", "practice", "v2.0", "maya", "priya", "2026-10-15",
     "Pending", "Low risk"),
    ("SK-008", None, None, "Roadmap builder", "skill", "v2.2", "maya", "priya", "2026-10-09",
     "Test failed", "Medium risk"),
    ("SK-014", None, None, "Operating model advisor", "skill", "v3.1", "sam", "maya", "2026-10-12",
     "Testing", "Low risk"),
    ("SK-019", None, None, "Evidence checker", "skill", "v2.3", "maya", "sam", "2026-10-14",
     "Definition review", "Low risk"),
    ("AR-019", None, None, "Atlas access request", "access", "", "sam", "jordan", "2026-10-10",
     "Blocked · High risk", "High risk"),
]

# kind, title, body, link, read
NOTIFICATIONS = [
    ("mention", "Priya Shah mentioned you in RV-104",
     "“Please make the pilot owner explicit and keep benefits directional until validated.”", "/reviews/RV-104", False),
    ("system", "Northstar discovery notes indexed",
     "JOB-207 · 6 engagement documents are now available to permitted team members.",
     f"/engagements/{NORTHSTAR}?tab=sources", False),
    ("system", "Roadmap generation completed",
     "RUN-118 · PPTX v0.8 and DOCX v0.6 are available. Review is required before export.",
     f"/engagements/{NORTHSTAR}/deliverables", False),
    ("review", "Changes requested on RV-104", "2 review comments need your response. Due 12 Oct 2026.",
     "/reviews/RV-104", True),
    ("review", "Meridian executive memo assigned to you", "RV-101 · DOCX v1.2 · Due 09 Oct 2026.",
     "/reviews/RV-101", True),
    ("mention", "Sam Rivera mentioned you in Northstar sources",
     "“Service inventory is uploaded; page 12 has the ownership table.”", f"/engagements/{NORTHSTAR}?tab=sources", True),
    ("system", "Operating model playbook updated", "Approved library release · v3.2 · 06 Oct.", "/library", True),
    ("review", "Cedar adoption toolkit approved", "RV-099 · PPTX v1.0 approved by Priya Shah.", "/reviews/RV-099", True),
]

# Practices beyond the four cards that ship in lp_library.json (candidates awaiting publication).
CANDIDATE_PRACTICES = [
    ("lp-041", "Benefits realization toolkit", "Transformation", "Defined", "v2.1", "Quality review", "Maya Patel"),
    ("lp-052", "Service handoff guide", "Operating model", "Defined", "v1.1", "Quality review", "Sam Rivera"),
    ("lp-063", "Control design guide", "Risk & controls", "Managed", "v1.3", "Quality review", "Maya Patel"),
    ("lp-072", "Adoption metrics", "Change & adoption", "Defined", "v2.0", "Pending", "Maya Patel"),
]
PRACTICE_CATEGORY = {
    "lp-016": "Operating model",
    "lp-021": "Governance",
    "lp-033": "Operating model",
    "lp-040": "Transformation",
}

INGESTION_JOBS = [
    ("JOB-208", {"source": "Benefits toolkit v2.1", "stage": "Index validated", "submittedBy": "Maya Patel",
                 "when": "09:30", "outcome": "86 / 86 chunks indexed",
                 "detail": "benefits-realization-toolkit-v2.1.docx · 42 pages · 86 chunks · 0 duplicates · "
                           "Permission metadata passed"}),
    ("JOB-207", {"source": "Northstar uploads", "stage": "Completed", "submittedBy": "Sam Rivera", "when": "09:40",
                 "outcome": "6 documents indexed", "detail": "Engagement-scoped to NS-042"}),
    ("JOB-206", {"source": "Policy connector", "stage": "Extract & chunk", "submittedBy": "System", "when": "09:20",
                 "outcome": "2 OCR failures",
                 "detail": "Policy handbook scanned.pdf and Control appendix scanned.pdf were excluded. Replace the "
                           "scans or run approved OCR."}),
    ("JOB-205", {"source": "Governance guide v2.4", "stage": "Completed", "submittedBy": "Priya Shah",
                 "when": "Yesterday", "outcome": "Published", "detail": ""}),
]
RETENTION_EXCEPTIONS = [
    ("RE-012", {"engagement": "Northstar NS-042", "requested": "365 days after close",
                "owner": "Alex Chen", "approver": "Priya Shah", "state": "Awaiting owner confirmation",
                "justification": "Retain the pilot evidence and reviewed roadmap for the annual adoption evaluation."}),
    ("RE-009", {"engagement": "Atlas AT-031", "requested": "Legal hold · Annual review",
                "owner": "Sam Rivera", "approver": "Jordan Kim", "state": "Approved · Hold active",
                "justification": "Legal hold on restricted finance sources."}),
]
EXPORT_REQUESTS = [
    ("EX-031", {"artifact": "Northstar PPTX v0.8", "requestedBy": "Alex Chen", "engagement": "NS-042",
                "gates": "2 comments · 1 claim gap", "state": "Blocked", "reviewId": "RV-104"}),
    ("EX-028", {"artifact": "Cedar PPTX v1.0", "requestedBy": "Maya Patel", "engagement": "CE-012",
                "gates": "Evidence & review passed", "state": "Ready for release", "reviewId": "RV-099"}),
    ("EX-026", {"artifact": "Atlas DOCX v0.4", "requestedBy": "Sam Rivera", "engagement": "AT-031",
                "gates": "Restricted-source owner pending", "state": "Blocked", "reviewId": "RV-106"}),
]

DOCUMENTS = {
    "Northstar discovery notes.md": "# Northstar discovery notes\n\nInterviews across three shared-service areas found "
    "unclear service ownership and slow escalations. Page 8: decision rights are duplicated between functions.\n",
    "Northstar service inventory.md": "# Northstar service inventory\n\nPage 12: 14 services, 5 without a named "
    "accountable owner.\n",
    "Sponsor objectives.md": "# Sponsor objectives\n\nImprove accountability and execution. Quantified benefits are "
    "not yet baselined.\n",
    "Escalation log summary.md": "# Escalation log summary\n\nMedian time to resolve cross-functional escalations: "
    "not yet measured consistently.\n",
    "Governance forum map.md": "# Governance forum map\n\nSeven forums, overlapping remits in two.\n",
    "Pilot candidate services.md": "# Pilot candidate services\n\nTwo services shortlisted for a 90-day ownership pilot.\n",
}

SLIDES = [
    ("title", "Northstar transformation roadmap", ["A phased roadmap to a resilient operating model"]),
    ("content", "Why change now", ["Service ownership is unclear in 5 of 14 services", "Escalations cross three functions"]),
    ("content", "What we heard in discovery", ["Decision rights are duplicated", "Handoffs lack named owners"]),
    ("content", "A phased roadmap to a resilient operating model",
     ["01 / 0–30 days · Align: baseline processes and agree decision rights.",
      "02 / 31–60 days · Design: pilot service ownership and test controls.",
      "03 / 61–90 days · Scale: measure outcomes and embed governance."]),
    ("content", "Days 0–30: Align", ["Confirm service owners", "Map handoffs", "Establish an adoption baseline"]),
    ("content", "Days 31–60: Design & pilot", ["Test one service area with named owners", "Weekly evidence review"]),
    ("content", "Days 61–90: Scale & embed", ["Scale validated controls", "Keep benefits directional until baselined"]),
    ("content", "Governance and decision rights", ["One accountable owner per service", "Stage gates reviewed monthly"]),
    ("content", "Pilot design", ["Two candidate services", "Success measured by ownership clarity and adoption"]),
    ("content", "Risks and assumptions", ["Benefits estimates are assumptions pending a baseline"]),
    ("content", "Measures of success", ["Ownership clarity", "Pilot adoption", "Escalation resolution"]),
    ("content", "Next steps", ["Resolve review comments", "Submit v0.9 for independent review"]),
]

NARRATIVE = """# Operating model recommendations

## Summary
Northstar should start with accountability, validate it through a pilot, then scale what works.

## Recommendation 1: Name an accountable owner for every service
Five of fourteen services have no named owner [2]. Assign owners before redesigning processes [1].

## Recommendation 2: Agree decision rights before redesign
Decision rights are duplicated between functions [2]. Use the playbook's decision-rights template [1].

## Recommendation 3: Pilot for 90 days
Test one service area with named owners and a weekly evidence review [3].

## Assumptions
Quantified benefits are directional only until a baseline is validated.
"""

CLAIMS = [
    (0, 3, "Baseline processes and agree decision rights in the first 30 days.", "grounded",
     "Operating model playbook v3.2, §4"),
    (1, 3, "Pilot service ownership before scaling.", "grounded", "Northstar discovery notes, p.8"),
    (2, 3, "The roadmap will reduce operating cost by a quantified amount.", "unsupported", None),
    (3, 4, "Service owners are confirmed in the alignment phase.", "grounded", "Operating model playbook v3.2, §4"),
    (4, 5, "One service area is tested with named owners.", "grounded", "Transformation governance guide v2.4, §6"),
    (5, 6, "Validated controls are scaled after the pilot.", "grounded", "Transformation governance guide v2.4, §6"),
]

CONVERSATION = [
    ("user", "Using our discovery notes and approved practices, propose a 90-day operating model roadmap and flag "
     "anything the evidence does not support."),
    ("assistant", "**Start with accountability, validate through a pilot, then scale what works.**\n\n"
     "**Days 0–30 / Align** — Confirm service owners, map handoffs and agree decision rights. Establish an adoption "
     "baseline. [1] Playbook v3.2, §4 · [2] Discovery notes, p.8\n\n"
     "**Days 31–60 / Design & pilot** — Test one service area with named owners and weekly evidence review. "
     "[1] Playbook · [3] Governance guide, §6\n\n"
     "**Days 61–90 / Scale & embed** — Scale validated controls. Keep benefits directional until a baseline is "
     "confirmed. [3] Governance guide, §6\n\n"
     "**Evidence gap: quantified benefits** — No permitted source validates a cost-reduction target. Human review is "
     "required."),
]


def demo_email(local_part: str) -> str:
    """Demo accounts live on the first allowed sign-in domain (example.com when sign-in is unrestricted)."""
    return f"{local_part}@{(allowed_email_domains() or ['example.com'])[0]}"


def _uid(key: str | None) -> str | None:
    return f"u_demo_{key}" if key else None


def _upsert(db, model, pk, **fields):
    row = db.get(model, pk)
    if row is None:
        row = model(id=pk, **fields)
        db.add(row)
    else:
        for key, value in fields.items():
            setattr(row, key, value)
    return row


def _record(db, collection: str, record_id: str, payload: dict, *, project_id=None, user_id=None, position=0) -> None:
    row = db.scalar(
        select(WorkbenchRecord).where(
            WorkbenchRecord.collection == collection, WorkbenchRecord.record_id == record_id
        )
    )
    if row is None:
        row = WorkbenchRecord(collection=collection, record_id=record_id)
        db.add(row)
    row.project_id, row.user_id, row.position = project_id, user_id, position
    row.payload_json = json.dumps(payload, ensure_ascii=False)


def _load(name: str) -> dict:
    return json.loads((SEED_DIR / f"{name}.json").read_text(encoding="utf-8"))


def _seed_users(db, password: str) -> None:
    hashed = get_password_hash(password)
    for uid, local_part, name, title, is_admin in USERS:
        _upsert(db, User, uid, email=demo_email(local_part), hashed_password=hashed, full_name=name, job_title=title,
                is_admin=is_admin)


def _seed_engagements(db) -> None:
    for index, row in enumerate(ENGAGEMENTS):
        pid, name, code, kind, stage, progress, task, due, start, close, classification, retention, members = row
        owner = next(key for key, title in members if title == "Engagement lead")
        _upsert(db, Project, pid, name=name, created_by=_uid(owner))
        db.flush()
        extra = NORTHSTAR_BRIEF if pid == NORTHSTAR else {
            "client_org": f"{name.split()[0]} (illustrative)",
            "brief": f"{kind} engagement for a fictional organization used in this sample workspace.",
        }
        _upsert(
            db, EngagementMeta, f"em_demo_{code.lower()}", project_id=pid, code=code, type=kind, stage=stage,
            progress=progress, next_task=task, due_date=due, start_date=start, target_close=close,
            classification=classification, retention_days=retention, status="active",
            # Listed order is most recently worked on first.
            updated_at=datetime(2026, 10, 8, 9, 45) - timedelta(hours=index), **extra,
        )
        for key, title in members:
            mid = f"m_demo_{code.lower()}_{key}"
            _upsert(db, Membership, mid, project_id=pid, user_id=_uid(key), role=_ROLE.get(title, "Editor"))
            _record(db, "member_roles", mid, {"title": title}, project_id=pid)
    for position, (mid, name, owner, target, status) in enumerate(MILESTONES):
        _record(db, "milestones", f"demo-ns-{mid}", {"name": name, "owner": owner, "target": target, "status": status},
                project_id=NORTHSTAR, position=position)


def _seed_activity(db) -> None:
    db.execute(delete(ActivityEvent).where(ActivityEvent.project_id.in_([row[0] for row in ENGAGEMENTS])))
    for when, actor, kind, title, detail in ACTIVITY:
        db.add(ActivityEvent(project_id=NORTHSTAR, actor=actor, kind=kind, title=title, detail=detail,
                             created_at=datetime.strptime(when, "%Y-%m-%d %H:%M")))


def _seed_reviews(db) -> None:
    detail = _load("review")
    payload = {key: detail[key] for key in ("slide", "evidenceChecksRunMeta", "evidenceChecks", "approvalTimeline")}
    for rid, pid, run_id, title, kind, version, owner, reviewer, due, state, risk in REVIEWS:
        _upsert(
            db, Review, rid, project_id=pid, run_id=run_id, title=title, artifact_type=kind, version_label=version,
            owner_id=_uid(owner), reviewer_id=_uid(reviewer), due_date=due, state=state, risk=risk,
            payload_json=json.dumps(payload if rid == "RV-104" else {}, ensure_ascii=False),
        )
    db.flush()
    db.execute(delete(ReviewComment).where(ReviewComment.review_id == "RV-104"))
    for comment in detail["comments"]:
        author, _, anchor = comment["attribution"].partition(" · ")
        db.add(ReviewComment(review_id="RV-104", author=author, title=comment["title"], body=comment["body"],
                             anchor=anchor, status="Resolved" if comment["status"] == "Resolved" else "Open"))


def _seed_notifications(db) -> None:
    db.execute(delete(Notification).where(Notification.user_id == _uid("alex")))
    for kind, title, body, link, read in NOTIFICATIONS:
        db.add(Notification(user_id=_uid("alex"), kind=kind, title=title, body=body, link=link,
                            read_at=datetime(2026, 10, 8, 9, 0) if read else None,
                            created_at=datetime(2026, 10, 8, 9, 46)))


def _seed_library(db) -> None:
    library = _load("lp_library")
    for card in library["cards"]:
        detail = library["practices"].get(card["id"], {})
        version, _, rest = card["versionLabel"].partition(" · ")
        _upsert(
            db, LpPractice, card["id"], title=card["title"], description=card["description"],
            category=PRACTICE_CATEGORY.get(card["id"], card["category"]), maturity=card["maturity"],
            version_label=version, status="Approved", owner=rest.split(" · ")[0],
            payload_json=json.dumps({**detail, "updatedMeta": rest}, ensure_ascii=False),
        )
    for pid, title, category, maturity, version, status, owner in CANDIDATE_PRACTICES:
        _upsert(db, LpPractice, pid, title=title, description="Candidate release awaiting publication.",
                category=category, maturity=maturity, version_label=version, status=status, owner=owner,
                payload_json="{}")
    db.flush()
    for position, card in enumerate(library["cards"]):
        _record(db, "engagement_practices", f"demo-ns-{card['id']}", {"practiceId": card["id"], "title": card["title"]},
                project_id=NORTHSTAR, position=position)
    _upsert(db, SavedPractice, 900001, user_id=_uid("alex"), practice_id="lp-016")


def _seed_skills_and_admin(db) -> None:
    skills = _load("skills")
    for position, card in enumerate(skills["cards"]):
        _record(db, "skills", card["id"], {**card, "detail": skills["skills"].get(card["id"])}, position=position)
    for name in ("overview", "admin_engagements", "admin_library", "admin_skills", "admin_reviews"):
        _record(db, "admin_screens", f"demo-{name}", _load(name))
    for collection, rows in (
        ("ingestion_jobs", INGESTION_JOBS),
        ("retention_exceptions", RETENTION_EXCEPTIONS),
        ("export_requests", EXPORT_REQUESTS),
    ):
        for position, (record_id, payload) in enumerate(rows):
            _record(db, collection, record_id, payload, position=position)


def _seed_run(db) -> None:
    """A finished Northstar run with a deck, a document and an evidence register, built without a model call."""
    plan = {"instruction": "90-day operating model roadmap", "output_types": ["pptx", "docx"]}
    _upsert(db, Run, RUN_ID, project_id=NORTHSTAR, status="review_ready", output_types='["pptx", "docx"]',
            instruction="Propose a 90-day operating model roadmap and flag unsupported claims.",
            plan_payload=json.dumps(plan), created_at=datetime(2026, 10, 8, 9, 42))
    ensure_workspace(NORTHSTAR)
    docs = workspace_path(NORTHSTAR) / "source_docs"
    docs.mkdir(parents=True, exist_ok=True)
    for name, text in DOCUMENTS.items():
        (docs / name).write_text(text, encoding="utf-8")
    run_dir = workspace_path(NORTHSTAR) / "runs" / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    slides = [
        {"slide_type": "title" if kind == "title" else "bullets", "title": title, "bullets": bullets}
        for kind, title, bullets in SLIDES
    ]
    (run_dir / "pptx_slides.json").write_text(json.dumps(slides, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_dir / "narrative.md").write_text(NARRATIVE, encoding="utf-8")
    claims = [
        {"id": f"claim-{i}", "slide_index": slide + 1, "slide_title": SLIDES[slide][1], "claim": text,
         "claim_type": "statement", "status": status, "citation": citation}
        for i, slide, text, status, citation in CLAIMS
    ]
    summary = {"total": len(claims), "grounded": sum(c["status"] == "grounded" for c in claims),
               "unsupported": sum(c["status"] == "unsupported" for c in claims)}
    (run_dir / "evidence_claims.json").write_text(
        json.dumps({"claims": claims, "summary": summary}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _write_office_files(run_dir)


def _write_office_files(run_dir: Path) -> None:
    from docx import Document
    from pptx import Presentation

    deck = Presentation()
    for kind, title, bullets in SLIDES:
        slide = deck.slides.add_slide(deck.slide_layouts[0 if kind == "title" else 1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = "\n".join(bullets)
    deck.save(str(run_dir / "output.pptx"))
    document = Document()
    for line in NARRATIVE.strip().splitlines():
        if line.startswith("# "):
            document.add_heading(line[2:], level=0)
        elif line.startswith("## "):
            document.add_heading(line[3:], level=1)
        elif line.strip():
            document.add_paragraph(line)
    document.save(str(run_dir / "output.docx"))


def _seed_conversation(db) -> None:
    _upsert(db, Conversation, "conv_demo_ns042_03", project_id=NORTHSTAR, user_id=_uid("alex"),
            title="Roadmap planning", skill_id="sk-008")
    db.flush()
    db.execute(delete(ConversationMessage).where(ConversationMessage.conversation_id == "conv_demo_ns042_03"))
    for role, content in CONVERSATION:
        db.add(ConversationMessage(conversation_id="conv_demo_ns042_03", role=role, content=content,
                                   created_at=datetime(2026, 10, 8, 9, 40)))


def seed(password: str) -> None:
    init_db()
    with session_scope() as db:
        _seed_users(db, password)
        db.flush()
        _seed_engagements(db)
        _seed_activity(db)
        _seed_reviews(db)
        _seed_notifications(db)
        _seed_library(db)
        _seed_skills_and_admin(db)
        _seed_run(db)
        _seed_conversation(db)
    print(f"Seeded {len(USERS)} demo users and {len(ENGAGEMENTS)} engagements. Sign in as {demo_email('alex.chen')}.")


def clear() -> None:
    init_db()
    project_ids = [row[0] for row in ENGAGEMENTS]
    user_ids = [row[0] for row in USERS]
    with session_scope() as db:
        db.execute(delete(ReviewComment).where(ReviewComment.review_id.in_([r[0] for r in REVIEWS])))
        db.execute(delete(Review).where(Review.id.in_([r[0] for r in REVIEWS])))
        db.execute(delete(Notification).where(Notification.user_id.in_(user_ids)))
        db.execute(delete(SavedPractice).where(SavedPractice.user_id.in_(user_ids)))
        db.execute(delete(LpPractice).where(LpPractice.id.like("lp-%")))
        db.execute(delete(ActivityEvent).where(ActivityEvent.project_id.in_(project_ids)))
        db.execute(delete(WorkbenchRecord).where(WorkbenchRecord.project_id.in_(project_ids)))
        db.execute(
            delete(WorkbenchRecord).where(
                WorkbenchRecord.collection.in_(
                    ["skills", "admin_screens", "ingestion_jobs", "retention_exceptions", "export_requests"]
                )
            )
        )
        conversations = select(Conversation.id).where(Conversation.project_id.in_(project_ids))
        db.execute(delete(ConversationMessage).where(ConversationMessage.conversation_id.in_(conversations)))
        db.execute(delete(Conversation).where(Conversation.project_id.in_(project_ids)))
        db.execute(delete(Run).where(Run.project_id.in_(project_ids)))
        db.execute(delete(EngagementMeta).where(EngagementMeta.project_id.in_(project_ids)))
        db.execute(delete(Membership).where(Membership.project_id.in_(project_ids)))
        db.execute(delete(Project).where(Project.id.in_(project_ids)))
        db.execute(delete(User).where(User.id.in_(user_ids)))
    for pid in project_ids:
        shutil.rmtree(workspace_path(pid), ignore_errors=True)
    print("Removed the workbench demo data.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clear", action="store_true", help="remove the demo data instead of creating it")
    args = parser.parse_args()
    if str(settings.advise_workbench_env).lower() == "production":
        print("Refusing to touch demo data when ADVISE_WORKBENCH_ENV is production.", file=sys.stderr)
        return 2
    if args.clear:
        clear()
        return 0
    password = os.environ.get("DEMO_SEED_PASSWORD", "")
    if len(password) < 8:
        print("Set DEMO_SEED_PASSWORD (8+ characters) for the demo accounts.", file=sys.stderr)
        return 2
    seed(password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
