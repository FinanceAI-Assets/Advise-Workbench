"""Admin console: the Leading Practice library ingestion pipeline, from source upload to published practice.

An upload creates (or adds a version to) a practice and an ingestion job, then runs extract & chunk and
index & validate straight away (``src.memory.knowledge.practice_ingest``). The job record, in the
``ingestion_jobs`` collection, holds the stage results; the passages live in ``library_chunks``.

Publication stays governed: every quality gate must pass, the candidate is submitted to an approver, the
approver decides on the existing review page, and only then can an administrator publish. Publishing marks the
practice Approved, which is what the Leading Practice Library (``/api/library``) lists, and writes the released
body where the library's retrieval index picks it up.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.api.engagements import display_name, format_date, format_timestamp, record_activity
from src.app.api.reviews import _notify, _timeline
from src.core.auth import require_admin
from src.core.db.models import LpPractice, Review, User, WorkbenchRecord, utcnow
from src.core.db.session import get_db
from src.memory.knowledge import practice_ingest as ingest

router = APIRouter()
_LOG = logging.getLogger(__name__)

JOBS = "ingestion_jobs"
CHUNKS = "library_chunks"
MAX_FILES_PER_UPLOAD = 10
PROCESS_TIMEOUT_SEC = 180

# Fields the ingestion jobs table shows; the rest of a job record is pipeline detail.
_JOB_TABLE_FIELDS = ("source", "stage", "submittedBy", "when", "outcome", "detail")


# --- records --------------------------------------------------------------------------------------------------------


def _number(value: str) -> int:
    match = re.search(r"(\d+)$", value or "")
    return int(match.group(1)) if match else 0


def _row(db: Session, collection: str, record_id: str) -> WorkbenchRecord | None:
    return db.scalar(
        select(WorkbenchRecord).where(WorkbenchRecord.collection == collection, WorkbenchRecord.record_id == record_id)
    )


def _payload(row: WorkbenchRecord | None) -> dict[str, Any]:
    return json.loads(row.payload_json or "{}") if row is not None else {}


def _save(row: WorkbenchRecord, payload: dict[str, Any]) -> None:
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.updated_at = utcnow()


def pipeline_jobs(db: Session, practice_id: str | None = None) -> list[dict[str, Any]]:
    """Jobs that came through the upload pipeline, newest first (seeded demo jobs have no practice)."""
    rows = db.scalars(select(WorkbenchRecord).where(WorkbenchRecord.collection == JOBS)).all()
    jobs = [{"id": r.record_id, **_payload(r)} for r in rows]
    jobs = [j for j in jobs if j.get("practiceId") and (practice_id is None or j["practiceId"] == practice_id)]
    return sorted(jobs, key=lambda j: _number(j["id"]), reverse=True)


def job_table_rows(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(select(WorkbenchRecord).where(WorkbenchRecord.collection == JOBS)).all()
    ordered = sorted(rows, key=lambda r: (r.position, -_number(r.record_id)))
    return [{"id": r.record_id, **{k: _payload(r).get(k, "") for k in _JOB_TABLE_FIELDS}} for r in ordered]


def _chunks(db: Session, job_id: str) -> dict[str, Any]:
    return _payload(_row(db, CHUNKS, job_id)) or {"blocks": [], "chunks": []}


def _next_job_id(db: Session) -> str:
    ids = db.scalars(select(WorkbenchRecord.record_id).where(WorkbenchRecord.collection == JOBS)).all()
    return f"JOB-{max([_number(i) for i in ids] + [200]) + 1}"


def _next_practice_id(db: Session) -> str:
    ids = db.scalars(select(LpPractice.id)).all()
    return f"lp-{max([_number(i) for i in ids] + [0]) + 1:03d}"


def _published_hashes(db: Session, *, exclude: str) -> dict[str, str]:
    """Passage hashes of the current release of every other published practice."""
    hashes: dict[str, str] = {}
    latest: dict[str, str] = {}
    for job in pipeline_jobs(db):
        if job.get("release") and job["practiceId"] != exclude:
            latest.setdefault(job["practiceId"], job["id"])
    for practice_id, job_id in latest.items():
        for chunk in _chunks(db, job_id).get("chunks", []):
            hashes[chunk["sha256"]] = practice_id
    return hashes


def _bump_minor(version: str) -> str:
    match = re.match(r"^v?(\d+)(?:\.(\d+))?", version or "")
    if not match:
        return "v1.0"
    return f"v{match.group(1)}.{int(match.group(2) or 0) + 1}"


def _admin_event(db: Session, admin: User, title: str, detail: str) -> None:
    record_activity(db, project_id=None, actor=display_name(admin), kind="admin", title=title, detail=detail)


# --- upload ---------------------------------------------------------------------------------------------------------


def _analyse(filename: str, content: bytes, meta: dict[str, str], published_hashes: dict[str, str]) -> dict[str, Any]:
    """Extract & chunk, then index & validate. Pure computation, run off the event loop."""
    extraction = ingest.extract_blocks(filename, content)
    blocks = extraction["blocks"]
    chunks = ingest.chunk_blocks(blocks) if extraction["readable"] else []
    citations = ingest.analyse_citations(blocks)
    for chunk in chunks:
        chunk["quality"], chunk["tone"] = ingest.chunk_quality(chunk, citations["missing"])
    validation = ingest.validate(chunks, citations, published_hashes=published_hashes, **meta) if chunks else None
    return {"extraction": extraction, "blocks": blocks, "chunks": chunks, "citations": citations,
            "validation": validation, "detail": ingest.practice_detail(blocks)}


@router.post("/library/uploads", status_code=201)
async def upload_library_sources(
    files: list[UploadFile] = File(...),
    owner: str = Form(..., min_length=2, max_length=120),
    classification: str = Form("Internal methods content", max_length=80),
    rights: str = Form(..., min_length=3, max_length=300),
    title: str = Form("", max_length=200),
    category: str = Form("", max_length=64),
    maturity: str = Form("", max_length=32),
    version: str = Form("", max_length=24),
    practice_id: str = Form("", max_length=64),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Upload practice sources. Each file becomes one ingestion job; extraction and validation run immediately.

    ``practice_id`` attaches a corrected or new version to an existing practice (one file only).
    """
    if not files or len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(status_code=422, detail=f"Upload between 1 and {MAX_FILES_PER_UPLOAD} sources at a time")
    existing: LpPractice | None = None
    if practice_id:
        if len(files) != 1:
            raise HTTPException(status_code=422, detail="Attach one corrected source at a time")
        existing = db.scalar(select(LpPractice).where(LpPractice.id == practice_id.lower()))
        if existing is None:
            raise HTTPException(status_code=404, detail="Practice not found")

    payloads: list[tuple[UploadFile, bytes]] = []
    for upload in files:
        content = await upload.read(ingest.MAX_SOURCE_BYTES + 1)
        try:
            ingest.check_source(upload.filename or "", content)
        except ingest.SourceRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        digest = hashlib.sha256(content).hexdigest()
        duplicate = next((j for j in pipeline_jobs(db) if j.get("sha256") == digest), None)
        if duplicate is not None:
            raise HTTPException(
                status_code=409,
                detail=f"{upload.filename} was already uploaded as {duplicate['id']} ({duplicate.get('practiceId', '').upper()})",
            )
        payloads.append((upload, content))

    meta = {"owner": owner.strip(), "classification": classification.strip(), "rights": rights.strip()}
    created: list[dict[str, Any]] = []
    for upload, content in payloads:
        filename = upload.filename or "source"
        practice = existing
        practice_key = practice.id if practice else _next_practice_id(db)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(_analyse, filename, content, meta, _published_hashes(db, exclude=practice_key)),
                timeout=PROCESS_TIMEOUT_SEC,
            )
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail=f"Extraction of {filename} timed out") from exc
        except ingest.SourceRejected as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        created.append(_record_upload(db, admin, practice, practice_key, filename, content, meta, result,
                                      title=title, category=category, maturity=maturity, version=version))
        db.flush()
    db.commit()
    return {"jobs": created}


def _record_upload(
    db: Session,
    admin: User,
    practice: LpPractice | None,
    practice_id: str,
    filename: str,
    content: bytes,
    meta: dict[str, str],
    result: dict[str, Any],
    *,
    title: str,
    category: str,
    maturity: str,
    version: str,
) -> dict[str, Any]:
    extraction, chunks, validation = result["extraction"], result["chunks"], result["validation"]
    readable = bool(chunks)
    stem = re.sub(r"[-_]+", " ", filename.rsplit(".", 1)[0]).strip()
    previous = pipeline_jobs(db, practice_id)
    if practice is None:
        practice_title = (title.strip() or stem[:1].upper() + stem[1:])[:200]
        candidate_version = version.strip() or "v1.0"
        category = category or "Operating model"
        maturity = maturity or "Defined"
        practice = LpPractice(
            id=practice_id, title=practice_title, description=result["detail"]["description"], category=category,
            maturity=maturity, version_label=candidate_version, status="Quality review" if readable else "Not eligible",
            owner=meta["owner"], payload_json="{}",
        )
        db.add(practice)
    else:
        practice_title = title.strip() or (previous[0]["title"] if previous else practice.title)
        live = practice.status == "Approved"
        if version.strip():
            candidate_version = version.strip()
        elif previous and not previous[0].get("release"):
            candidate_version = previous[0]["version"]  # a correction keeps the candidate's version
        else:
            candidate_version = _bump_minor(practice.version_label) if live else practice.version_label or "v1.0"
        if not live:  # a published practice stays live, unchanged, until the new version is released
            practice.status = "Quality review" if readable else "Not eligible"
            practice.title = practice_title
        # A correction or new version keeps the candidate's taxonomy unless the upload changes it.
        category = category or (previous[0].get("category") if previous else "") or practice.category
        maturity = maturity or (previous[0].get("maturity") if previous else "") or practice.maturity

    job_id = _next_job_id(db)
    ingest.store_upload(job_id, filename, content)
    now = datetime.now()
    open_correction = next((j["correction"] for j in previous if (j.get("correction") or {}).get("status") == "Open"), None)
    if open_correction is not None:
        for job in previous:
            if (job.get("correction") or {}).get("id") == open_correction["id"]:
                row = _row(db, JOBS, job["id"])
                payload = _payload(row)
                payload["correction"]["status"] = f"Corrected in {job_id}"
                _save(row, payload)

    review = db.scalar(select(Review).where(Review.id == practice_id.upper(), Review.artifact_type == "practice"))
    if review is not None:
        # The new source needs its own approval: the earlier decision covered different content.
        review.state = "Draft"
        review.version_label = candidate_version
        _timeline(review, f"New source uploaded ({job_id}); resubmission required", display_name(admin), "edit")

    missing = result["citations"]["missing"]
    if not readable:
        stage, outcome = "Extract & chunk", "No readable text"
        detail = f"{filename} · {extraction.get('reason') or 'No text'} · Excluded from retrieval"
    else:
        stage = "Quality review"
        outcome = f"{validation['indexed']} / {validation['total']} chunks indexed"
        detail = (f"{filename} · {extraction['pages']} pages · {len(chunks)} chunks · "
                  f"{validation['internalDuplicates']} duplicates · "
                  + (f"Reference {', '.join(map(str, missing))} unattributed" if missing else "Citations verified"))
    payload = {
        "source": f"{practice_title} {candidate_version}",
        "stage": stage,
        "submittedBy": display_name(admin),
        "when": format_timestamp(now),
        "outcome": outcome,
        "detail": detail,
        "practiceId": practice_id,
        "title": practice_title,
        "version": candidate_version,
        "category": category,
        "maturity": maturity,
        "filename": filename,
        "sizeBytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "uploadedById": admin.id,
        "uploadedAt": now.isoformat(timespec="seconds"),
        "parseMode": extraction["parseMode"],
        "pages": extraction["pages"],
        "readable": readable,
        "reason": extraction.get("reason", ""),
        "chunkCount": len(chunks),
        "citations": result["citations"],
        "validation": validation,
        "resolvesCorrection": open_correction,
        **meta,
    }
    db.add(WorkbenchRecord(collection=JOBS, record_id=job_id, position=-_number(job_id),
                           payload_json=json.dumps(payload, ensure_ascii=False)))
    db.add(WorkbenchRecord(collection=CHUNKS, record_id=job_id,
                           payload_json=json.dumps({"blocks": result["blocks"], "chunks": chunks}, ensure_ascii=False)))
    _admin_event(db, admin, f"{job_id} uploaded: {filename}", f"{practice_id.upper()} {candidate_version} · {outcome}")
    return {"id": job_id, "practiceId": practice_id, "stage": stage, "outcome": outcome, "readable": readable}


# --- submit & release -----------------------------------------------------------------------------------------------


def latest_job(db: Session, practice_id: str) -> dict[str, Any] | None:
    jobs = pipeline_jobs(db, practice_id)
    return jobs[0] if jobs else None


def gates_for(job: dict[str, Any]) -> list[dict[str, Any]]:
    if not job.get("readable"):
        return [{"id": "qg-0", "label": "Readable source", "result": "Failed", "tone": "warn", "passed": False,
                 "detail": job.get("reason") or "No readable text"}]
    return ingest.quality_gates(job)


class SubmitRequest(BaseModel):
    approver_id: str = Field(alias="approverId")
    reason: str = Field(default="", max_length=500)

    model_config = {"populate_by_name": True}


@router.post("/library/{practice_id}/submit")
def submit_for_approval(
    practice_id: str, body: SubmitRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    """Send a candidate whose quality gates all pass to an approver, who decides on the review page."""
    practice = db.scalar(select(LpPractice).where(LpPractice.id == practice_id.lower()))
    job = latest_job(db, practice_id.lower()) if practice else None
    if practice is None or job is None:
        raise HTTPException(status_code=404, detail="No uploaded source for this practice")
    if job.get("release"):
        raise HTTPException(status_code=409, detail=f"{job['version']} is already published; upload a new version first")
    failing = [g["label"] for g in gates_for(job) if not g["passed"]]
    if failing:
        raise HTTPException(status_code=409, detail=f"Resolve the quality gates before submitting: {', '.join(failing)}")
    approver = db.scalar(select(User).where(User.id == body.approver_id))
    if approver is None:
        raise HTTPException(status_code=404, detail="Approver not found")

    review_id = practice.id.upper()
    review = db.scalar(select(Review).where(Review.id == review_id))
    if review is not None and review.artifact_type != "practice":
        raise HTTPException(status_code=409, detail=f"Review {review_id} belongs to another artifact")
    if review is None:
        review = Review(id=review_id, title=job["title"], artifact_type="practice", payload_json="{}")
        db.add(review)
    review.title = job["title"]
    review.version_label = job["version"]
    review.owner_id = job.get("uploadedById") or admin.id
    review.reviewer_id = approver.id
    review.due_date = (date.today() + timedelta(days=3)).isoformat()
    review.state = "In review"
    review.risk = ""
    payload = json.loads(review.payload_json or "{}")
    payload["evidenceChecks"] = [
        {"id": g["id"], "check": g["label"], "result": "Passed" if g["passed"] else "Gap", "resultLabel": g["result"],
         "action": g["detail"]}
        for g in gates_for(job)
    ]
    payload["evidenceChecksRunMeta"] = f"{job['id']} · {job['chunkCount']} chunks · {job['pages']} pages · Quality gates passed"
    review.payload_json = json.dumps(payload, ensure_ascii=False)
    _timeline(review, f"Submitted for approval ({job['id']})", display_name(admin), "edit")

    row = _row(db, JOBS, job["id"])
    stored = _payload(row)
    stored.update({"stage": "Quality review", "outcome": f"Awaiting approval by {display_name(approver)}",
                   "submitted": {"reviewId": review_id, "approverId": approver.id, "at": datetime.now().isoformat(timespec="seconds")}})
    _save(row, stored)
    if approver.id != admin.id:
        _notify(db, approver.id, kind="review", title=f"Approve practice release: {job['title']} {job['version']}",
                body=f"{review_id} · Submitted by {display_name(admin)}", link=f"/reviews/{review_id}")
    _admin_event(db, admin, f"{review_id} {job['version']} submitted for approval",
                 f"Approver: {display_name(approver)}" + (f" · {body.reason.strip()}" if body.reason.strip() else ""))
    db.commit()
    return {"reviewId": review_id, "state": review.state, "approver": display_name(approver)}


def record_correction(db: Session, practice_id: str, correction: dict[str, Any]) -> bool:
    """Attach a correction request to the practice's latest uploaded source. False when it has none."""
    job = latest_job(db, practice_id)
    if job is None:
        return False
    row = _row(db, JOBS, job["id"])
    payload = _payload(row)
    payload["correction"] = {**correction, "status": "Open", "requestedAt": datetime.now().isoformat(timespec="minutes")}
    payload.update({"stage": "Quality review", "outcome": f"{correction['id']} correction requested"})
    _save(row, payload)
    return True


def release(db: Session, practice: LpPractice, review: Review, admin: User) -> dict[str, Any] | None:
    """Publish the latest uploaded version. Returns None for practices that never came through the pipeline."""
    job = latest_job(db, practice.id)
    if job is None:
        return None
    if job.get("release"):
        raise HTTPException(status_code=409, detail=f"{practice.id.upper()} {job['version']} is already published")
    failing = [g["label"] for g in gates_for(job) if not g["passed"]]
    if failing:
        raise HTTPException(status_code=409, detail=f"Quality gates still open: {', '.join(failing)}")

    stored_chunks = _chunks(db, job["id"])
    detail = ingest.practice_detail(stored_chunks.get("blocks", []))
    users = {u.id: u for u in db.scalars(select(User)).all()}
    approver = display_name(users.get(review.reviewer_id or ""))
    previous = practice.version_label if practice.status == "Approved" else ""
    now = datetime.now()
    citations = job.get("citations") or {}
    references = len(citations.get("references", []))
    verified = len(citations.get("attributed", []))

    practice.title = job["title"]
    practice.description = detail["description"] or practice.description
    practice.category = job.get("category") or practice.category
    practice.maturity = job.get("maturity") or practice.maturity
    practice.version_label = job["version"]
    practice.owner = job["owner"]
    practice.payload_json = json.dumps({
        "maturity": f"{practice.maturity} maturity",
        "recommendedWhen": detail["recommendedWhen"],
        "coreGuidance": detail["coreGuidance"],
        "sourceAttribution": job["rights"],
        "practiceOwner": job["owner"],
        "approvedMeta": f"Approved by {approver} · {format_date(now.date().isoformat())}",
        "sourceQuality": (f"{verified} / {references} citations verified · " if references else "")
                         + f"{job['chunkCount']} passages · {job['pages']} pages · {job['id']}",
        "updatedMeta": f"Updated {format_date(now.date().isoformat(), year=False)}",
    }, ensure_ascii=False)

    markdown = ingest.render_markdown(job["title"], {
        "Practice": f"{practice.id.upper()} {job['version']}",
        "Taxonomy": f"{practice.category} · {practice.maturity} maturity",
        "Owner": job["owner"],
        "Approved by": approver,
        "Source attribution": job["rights"],
        "Classification": job["classification"],
    }, stored_chunks.get("blocks", []))
    ingest.write_release(practice.id, job["version"], markdown)

    releases = sum(1 for j in pipeline_jobs(db, practice.id) if j.get("release"))
    record = {
        "auditId": f"PUB-{_number(practice.id):03d}-{releases + 1:02d}",
        "publishedAt": now.isoformat(timespec="minutes"),
        "publishedBy": display_name(admin),
        "approver": approver,
        "selfReview": review.owner_id is not None and review.owner_id == review.reviewer_id,
        "previousVersion": previous,
    }
    row = _row(db, JOBS, job["id"])
    payload = _payload(row)
    payload.update({"stage": "Completed", "outcome": f"Published {job['version']}", "release": record})
    if payload.get("resolvesCorrection"):
        payload["resolvesCorrection"]["status"] = "Resolved"
    _save(row, payload)

    try:
        from src.memory.knowledge import lp_index

        lp_index.load_index(force=True)
    except Exception:  # the index rebuilds on its next scan; publication itself has succeeded
        _LOG.warning("leading practice index refresh failed after publishing %s", practice.id, exc_info=True)
    return record


# --- console screen -------------------------------------------------------------------------------------------------


def _notice(title: str, description: str) -> dict[str, str]:
    return {"title": title, "description": description}


def _when(value: str | None) -> str:
    if not value:
        return ""
    try:
        return format_timestamp(datetime.fromisoformat(value))
    except ValueError:
        return value


def _plain_section(section: str) -> str:
    return re.sub(r"^§[\d.]+\s*", "", section or "")


def library_sections(db: Session, practice_id: str | None) -> dict[str, Any] | None:
    """The pipeline tabs for one practice's latest upload, or None when it has none (the demo fixture is shown)."""
    jobs = pipeline_jobs(db)
    if practice_id is None:
        if not jobs:
            return None
        practice_id = jobs[0]["practiceId"]
    job = latest_job(db, practice_id)
    practice = db.scalar(select(LpPractice).where(LpPractice.id == practice_id))
    if job is None or practice is None:
        return None

    users = {u.id: u for u in db.scalars(select(User)).all()}
    review = db.scalar(select(Review).where(Review.id == practice.id.upper(), Review.artifact_type == "practice"))
    reviewer = display_name(users.get(review.reviewer_id or "")) if review and review.reviewer_id else ""
    code, title, version = practice.id.upper(), job["title"], job["version"]
    readable = bool(job.get("readable"))
    published = bool(job.get("release"))
    live_version = practice.version_label if practice.status == "Approved" else ""
    validation = job.get("validation") or {"checks": [], "retrievalChecks": [], "indexed": 0, "total": 0}
    citations = job.get("citations") or {"missing": [], "references": [], "attributed": []}
    gates = gates_for(job)
    failing = [g for g in gates if not g["passed"]]
    review_state = review.state if review else "Not submitted"
    approved = review is not None and review.state == "Approved"
    chunks = _chunks(db, job["id"]).get("chunks", [])
    flagged = next((c for c in chunks if c.get("tone") == "warn" and "Reference" in c.get("quality", "")), None)
    correction = job.get("correction") if (job.get("correction") or {}).get("status") == "Open" else None
    resolved = job.get("resolvesCorrection")

    blockers: list[str] = []
    if failing:
        blockers.append(f"Quality gates open: {', '.join(g['label'] for g in failing)}")
    if not approved:
        blockers.append("Independent approval is " + ("pending" if review_state == "In review" else review_state.lower()))
    can_publish = not published and not blockers

    if failing:
        gate = failing[0]
        if gate["id"] == "qg-2":
            blocker = _notice(
                f"Unattributed source in reference {', '.join(map(str, citations['missing']))}",
                "Replace it with a verifiable source or remove the statement. Publication is blocked until the correction is reviewed.",
            )
        else:
            blocker = _notice(f"{gate['label']} needs attention", f"{gate['detail']}. Publication is blocked until this is resolved.")
    else:
        blocker = None

    steps_status = {
        "extract": ("complete", "Complete") if readable else ("in-progress", "Needs readable source"),
        "index": ("complete", "Complete") if readable else ("upcoming", "Pending"),
        "quality": ("complete", "Approved") if approved or published else
                   ("in-progress", "Awaiting approval" if review_state == "In review" else "Current"),
        "publish": ("complete", "Published") if published else
                   ("in-progress", "Ready") if can_publish else ("upcoming", "Pending"),
    }
    step_ids = [("source-upload", "Source upload", ("complete", "Complete")),
                ("extract-chunk", "Extract & chunk", steps_status["extract"]),
                ("index-validate", "Index & validate", steps_status["index"]),
                ("quality-review", "Quality review", steps_status["quality"]),
                ("approve-publish", "Approve & publish", steps_status["publish"])]
    pipeline_steps = [
        {"id": sid, "index": i, "label": label, "status": status, "helper": helper,
         **({"icon": "cycle"} if status == "in-progress" else {})}
        for i, (sid, label, (status, helper)) in enumerate(step_ids, start=1)
    ]

    latest = jobs[0]
    return {
        "selectedPracticeId": practice.id,
        "pipelineSource": "upload",
        "pipelineSteps": pipeline_steps,
        "latestIngestionJob": {
            "id": latest["id"].lower(),
            "submittedAt": _when(latest.get("uploadedAt")),
            "filename": latest["filename"],
            "meta": f"{latest.get('sizeBytes', 0) / 1024 / 1024:.1f} MB · Uploaded by {latest['submittedBy']} · {latest['classification']}",
            "status": "Published" if latest.get("release") else "Indexed" if latest.get("readable") else "Not readable",
            "extractionMeta": f"{latest['pages']} pages · {latest['chunkCount']} chunks",
            "indexValidationMeta": (f"{(latest.get('validation') or {}).get('indexed', 0)} / {latest['chunkCount']} indexed · "
                                    f"{(latest.get('validation') or {}).get('internalDuplicates', 0)} duplicates"),
            "provenanceMeta": "Source hash & uploader recorded",
            "warning": None if latest.get("readable") else _notice(
                f"{latest['filename']} could not be read",
                f"{latest.get('reason') or 'No text found'}. Upload a text-readable PDF, Word, PowerPoint or Excel file; the source is excluded from retrieval."),
        },
        "qualityReview": {
            "id": practice.id,
            "code": code,
            "title": title,
            "versionLabel": "Published" if published else f"{version} candidate",
            "approvalState": "Published" if published else ("Approval blocked" if failing else review_state),
            "taxonomy": job.get("category") or practice.category,
            "maturity": job.get("maturity") or practice.maturity,
            "practiceOwner": job["owner"],
            "approver": reviewer or "Not assigned",
            "sourceAttribution": job.get("rights", ""),
            "sourceQualityChecks": [{"id": g["id"], "label": g["label"], "state": "Passed" if g["passed"] else g["result"]} for g in gates],
            "warning": blocker,
            "footnote": (f"Published {live_version} remains available to users. " if live_version and not published else "")
                        + "Approving creates a new immutable release with a full audit record.",
        },
        "extraction": {
            "subtitle": f"{job['id']} · {title} {version} · {job['pages']} pages / {job['chunkCount']} chunks",
            "sourceHash": f"SHA-256 {job['sha256'][:12]}… recorded · Source version pinned",
            "chunks": [
                {"id": c["id"], "code": c["code"], "page": c.get("page"), "section": c.get("section") or "",
                 "tokens": c["tokens"], "quality": c.get("quality", "Readable"), "tone": c.get("tone", "ok"),
                 "passageMeta": f"~{c['tokens']} tokens · Heading-aware split · {ingest.OVERLAP_TOKENS}-token overlap",
                 "passage": c["text"]}
                for c in chunks
            ],
            "provenance": _notice("Provenance preserved",
                                  "Page and section locators are attached to each chunk. No classification or owner metadata is dropped."),
            "error": None if readable else _notice(
                "No readable text", f"{job.get('reason') or 'The source could not be read'}. Upload a text-readable PDF, Word, PowerPoint or Excel file; this source is excluded from retrieval."),
        },
        "indexValidation": {
            "subtitle": f"{job['id']} · {title} · {version} candidate",
            "summary": f"{validation['indexed']} / {validation['total']} chunks",
            "checks": validation["checks"],
            "inspection": [
                {"label": "Index", "value": "leading-practice-library · Served to users" if published
                 else "practice-candidates · Not served to users"},
                {"label": "Checksum", "value": f"Source and chunk hashes recorded in {job['id']}"},
                {"label": "Validated", "value": f"{_when(validation.get('validatedAt'))} · System" if validation.get("validatedAt") else "Not validated"},
            ],
            "warning": None if published else _notice(
                "Indexed is not published",
                f"The candidate stays outside user retrieval until every quality gate passes and {reviewer or 'an independent approver'} approves the release."),
            "retrievalChecks": validation["retrievalChecks"],
        },
        "qualityGates": {
            "practiceId": practice.id,
            "title": f"Quality review: {title}",
            "subtitle": f"{code} · {version} candidate · Owner: {job['owner']} · Approver: {reviewer or 'Not assigned'}",
            "gates": gates,
            "blocker": blocker,
            "metadata": [
                {"label": "Taxonomy", "value": f"{job.get('category') or practice.category} · {job.get('maturity') or practice.maturity} maturity"},
                {"label": "Owner / rights", "value": f"{job['owner']} · {job['rights']}"},
                {"label": "Flagged passage", "value": (
                    f"{ingest.locator(flagged)} · {flagged['quality']}" if flagged else "None flagged")},
                {"label": "Published baseline", "value": f"{live_version} remains available to users" if live_version and not published
                 else f"{version} is live" if published else "Not yet published"},
            ],
            "correction": {
                "assignee": job["owner"],
                "due": (date.today() + timedelta(days=2)).isoformat(),
                "sourceLocation": (f"Page {flagged['page']} · " if flagged and flagged.get("page") else "")
                                  + (f"{_plain_section(flagged['section'])} · " if flagged else "")
                                  + (f"Reference {', '.join(map(str, citations['missing']))}" if citations["missing"] else "Whole source"),
                "requiredCorrection": (
                    "Replace the unattributed reference with an original, verifiable source or remove the claim. "
                    "Upload a corrected file and preserve source locators for all unaffected passages."
                    if citations["missing"] else f"Resolve: {'; '.join(g['detail'] for g in failing) or 'reviewer feedback'}."),
                "severity": f"Publication-blocking · {failing[0]['label']}" if failing else "Advisory",
            },
            "review": {"id": review.id, "state": review.state, "reviewer": reviewer,
                       "selfReview": review.owner_id is not None and review.owner_id == review.reviewer_id} if review else None,
            "openCorrection": correction,
            "approvers": sorted(({"id": u.id, "name": display_name(u)} for u in users.values()), key=lambda u: u["name"].lower()),
            "canSubmit": not published and not failing and review_state not in {"In review", "Approved"},
            "canPublish": can_publish,
        },
        "release": {
            "practiceId": practice.id,
            "subtitle": f"{code} · {title} {version} · " + (f"Published {_when(job['release']['publishedAt'])}" if published else "Release candidate"),
            "gates": ([{"id": "rg-0", "label": f"Correction {resolved['id']}", "result": "Resolved" if published or not failing else "Open",
                        "detail": resolved.get("reason", "")[:120], "tone": "ok" if published or not failing else "warn"}]
                      if resolved else [])
                     + [
                        {"id": "rg-1", "label": "Citation verification", "result": next(g["result"] for g in gates if g["id"] in ("qg-2", "qg-0")),
                         "detail": next(g["detail"] for g in gates if g["id"] in ("qg-2", "qg-0")),
                         "tone": "ok" if not citations["missing"] and readable else "warn"},
                        {"id": "rg-2", "label": "Index & metadata", "result": f"{validation['indexed']} / {validation['total']} validated",
                         "detail": f"{job['id']} · Source hash retained", "tone": "ok" if readable else "warn"},
                        {"id": "rg-3", "label": "Independent review", "result": review_state,
                         "detail": (f"{reviewer}" + (" · Self-review" if review and review.owner_id == review.reviewer_id else "")) if reviewer
                         else "Submit for approval in Quality review", "tone": "ok" if approved or published else "warn"},
                     ],
            "notice": _notice(
                f"{version} published",
                f"Immutable release created {_when(job['release']['publishedAt'])}. The Leading Practice Library now serves {version}"
                + (f"; {job['release']['previousVersion']} is retained for provenance." if job["release"].get("previousVersion") else "."),
            ) if published else _notice("Not yet published", "; ".join(blockers) + "." if blockers else "Ready to publish."),
            "record": [
                {"label": "Owner", "value": job["owner"]},
                {"label": "Approver", "value": (f"{reviewer} · " + ("Self-review" if review and review.owner_id == review.reviewer_id else "Independent reviewer"))
                 if reviewer else "Not assigned"},
                {"label": "Rights", "value": f"{job['rights']} · {job.get('maturity') or practice.maturity} maturity"},
                {"label": "Audit", "value": f"{job['release']['auditId']} · Source, checks and approval retained" if published
                 else "Created on publication"},
                {"label": "Previous version", "value": (f"{job['release']['previousVersion']} · Superseded, retained for provenance"
                                                        if published and job["release"].get("previousVersion")
                                                        else f"{live_version} · Live until this release" if live_version and not published
                                                        else "None · First release")},
            ],
            "published": published,
            "canPublish": can_publish,
            "blockers": blockers,
        },
    }


def inventory_rows(db: Session) -> list[dict[str, Any]]:
    """Practice inventory, with each practice's latest candidate when one is in flight."""
    latest: dict[str, dict[str, Any]] = {}
    for job in pipeline_jobs(db):
        latest.setdefault(job["practiceId"], job)
    rows = []
    for practice in db.scalars(select(LpPractice).order_by(LpPractice.id)).all():
        job = latest.get(practice.id)
        candidate = job is not None and not job.get("release")
        rows.append({
            "id": practice.id,
            "practiceSource": f"{(job or {}).get('title') or practice.title} · {practice.id.upper()}",
            "version": f"{job['version']} candidate" if candidate else practice.version_label,
            "indexing": ("Indexed" if job.get("readable") else "Not readable") if job else "Indexed",
            "lifecycle": ("Candidate in review" if practice.status == "Approved" else practice.status) if candidate else practice.status,
        })
    return rows
