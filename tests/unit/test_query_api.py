"""The query pipeline end to end: POST /api/query (library and engagement scope, access, failures), Sheldon's
router -> rag_agent in an engagement Conversation, and Talk to data. Library sources and engagement uploads both go
through the ingestion pipeline (eager Celery against in-process fakes), as /api/admin/library/uploads and
/api/documents/upload queue them."""

import uuid

import pytest
from fastapi.testclient import TestClient

import src.app.api.projects.conversation as projects_module
from src.agents.conversation import sheldon_router_agent as router_agent
from src.core.config import settings
from src.core.db.models import ChunkArchive, DocumentChunkLink, DocumentJob, LpPractice
from src.core.db.session import session_scope
from src.memory.knowledge.library_release import LIBRARY_SCOPE
from src.query import pipeline as qp
from src.workflows.task_router.conversation_router import RouterDecision
from tests.unit import _pipeline_fakes
from tests.unit.test_library_ingestion import _login, _upload


@pytest.fixture
def env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from src.app.main import app as fastapi_app

    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(settings, "lp_library_local_path", "")
    monkeypatch.setattr(settings, "query_llm_retry_backoff_sec", 0.0)
    fakes = _pipeline_fakes.install(monkeypatch)
    client = TestClient(fastapi_app)
    admin = _login(client, admin=True)
    entry = _upload(client, admin).json()["jobs"][0]
    status = client.get(f"/api/admin/library/documents/status/{entry['ingestion']['job_id']}", headers=admin).json()
    doc = status["document_file_id"]
    with session_scope() as db:
        chunk_ids = [c for (c,) in db.query(ChunkArchive.id).join(DocumentChunkLink, DocumentChunkLink.chunk_id == ChunkArchive.id)
                     .filter(DocumentChunkLink.document_file_id == doc).order_by(DocumentChunkLink.chunk_number)]
    released: set[str] = set()
    monkeypatch.setattr(qp, "released_document_ids", lambda db: released)
    # The fake embedder hashes text, so similarity is meaningless: every passage of the library source is a search
    # hit, and in an engagement every passage indexed under its id (as Qdrant's project_id filter returns them).
    def fake_search(pid, vectors):
        if pid == LIBRARY_SCOPE:
            return [qp.Source("chunk", c, 0.8) for c in chunk_ids]
        with session_scope() as db:
            return [qp.Source("chunk", c, 0.9) for (c,) in db.query(ChunkArchive.id).filter(ChunkArchive.project_id == pid)]

    monkeypatch.setattr(qp, "search", fake_search)
    questions: list[str] = []

    def fake_llm(*, system, user, **_):
        if "standalone" in system:
            return "How are new vendors screened before onboarding?"
        questions.append(user)
        return "Vendors are screened against the approved criteria [S1]."

    monkeypatch.setattr(qp, "claude_generate", fake_llm)
    return {"client": client, "admin": admin, "user": _login(client, admin=False), "doc": doc, "chunks": chunk_ids,
            "released": released, "practice": entry["practiceId"], "questions": questions, **fakes}


WORKSHOP = ("Vendor master changes need an IT ticket and take nine days on average. The procurement team raises the "
            "ticket, the master data team validates bank details against the supplier letter, and finance approves "
            "the change before it is released to payments. ") * 4


def _upload_doc(env, pid: str, name: str = "workshop-notes.txt", text: str = WORKSHOP):
    r = env["client"].post("/api/documents/upload", headers=env["user"], data={"project_id": pid},
                           files={"file": (name, text.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    return r.json()


def _engagement(env) -> str:
    """An engagement owned by the user, with one document uploaded through /api/documents/upload (the pipeline)."""
    created = env["client"].post("/api/projects", json={"name": f"Northwind {uuid.uuid4().hex[:6]}"}, headers=env["user"])
    assert created.status_code == 200, created.text
    pid = created.json()["id"]
    assert _upload_doc(env, pid)["ingestion"]["status"] == "completed"
    return pid


# --- engagement uploads through the ingestion pipeline --------------------------------------------------------------


def _passages(pid: str) -> dict[str, str]:
    with session_scope() as db:
        return {c.id: c.text for c in db.query(ChunkArchive).filter(ChunkArchive.project_id == pid)}


def test_engagement_upload_is_indexed_by_the_pipeline(env):
    client, user = env["client"], env["user"]
    created = client.post("/api/projects", json={"name": "Contoso"}, headers=user).json()
    pid = created["id"]
    body = _upload_doc(env, pid)
    ingestion = body["ingestion"]
    assert ingestion["status"] == "completed" and ingestion["searchable"] and ingestion["progress_percent"] == 100
    assert ingestion["stages"] == ["uploading", "parsing", "chunking", "embedding"] and ingestion["chunk_count"] > 0
    # S3 holds the file; Postgres and Qdrant hold its passages under the engagement's id.
    assert any(k.split("/")[1] == pid for k in env["s3"].objects)
    passages = _passages(pid)
    assert passages and any("nine days" in t for t in passages.values())
    assert env["get_store"]().count(project_id=pid) == len(passages)

    listed = client.get(f"/api/documents/list?project_id={pid}", headers=user).json()
    assert [d["filename"] for d in listed["documents"]] == ["workshop-notes.txt"] and len(listed["items"]) == 1
    assert listed["documents"][0]["ingestion"]["status"] == "completed"
    status = client.get(f"/api/documents/status/{ingestion['job_id']}?project_id={pid}", headers=user)
    assert status.status_code == 200 and status.json()["ingestion"]["searchable"]
    # Not a member: no status.
    assert client.get(f"/api/documents/status/{ingestion['job_id']}?project_id={pid}", headers=env["admin"]).status_code == 403


def test_engagements_never_share_passages(env):
    client, user = env["client"], env["user"]
    a, b = _engagement(env), _engagement(env)  # the same document in both
    pa, pb = _passages(a), _passages(b)
    assert pa and pb and not set(pa) & set(pb) and sorted(pa.values()) == sorted(pb.values())
    ask = {"question": "How long do vendor master changes take?", "include_library": False}
    cites = client.post("/api/query", headers=user, json={**ask, "engagement_id": a}).json()["citations"]
    assert cites and {c["id"] for c in cites} <= set(pa)


def test_a_new_version_replaces_the_old_and_delete_removes_it(env):
    client, user = env["client"], env["user"]
    eid = _engagement(env)
    old = set(_passages(eid))
    _upload_doc(env, eid, text=WORKSHOP.replace("nine days", "four days"))
    new = _passages(eid)
    assert new and not old & set(new) and all("nine days" not in t for t in new.values())
    with session_scope() as db:
        statuses = [s for (s,) in db.query(DocumentJob.status).filter(DocumentJob.project_id == eid)]
    assert sorted(statuses) == ["completed", "deleted"]

    deleted = client.delete(f"/api/documents/delete?project_id={eid}&filename=workshop-notes.txt", headers=user)
    assert deleted.status_code == 200 and _passages(eid) == {} and env["get_store"]().count(project_id=eid) == 0
    r = client.post("/api/query", headers=user, json={"question": "How long do vendor master changes take?",
                                                       "engagement_id": eid, "include_library": False}).json()
    assert r["status"] == "insufficient_evidence" and r["reason"] == "no_results"


def test_upload_survives_a_queue_outage_and_reindex_recovers(env, monkeypatch):
    from src.workers import pipeline

    client, user = env["client"], env["user"]
    pid = client.post("/api/projects", json={"name": "Fabrikam"}, headers=user).json()["id"]
    real_start = pipeline.start_pipeline

    def broker_down(ctx):
        raise ConnectionError("RabbitMQ unreachable")

    monkeypatch.setattr(pipeline, "start_pipeline", broker_down)
    ingestion = _upload_doc(env, pid)["ingestion"]
    assert ingestion["status"] == "failed" and "RabbitMQ" in ingestion["error"]
    assert all(k.split("/")[1] != pid for k in env["s3"].objects)  # nothing left behind for a worker that never comes

    monkeypatch.setattr(pipeline, "start_pipeline", real_start)
    redone = client.post(f"/api/documents/reindex?project_id={pid}", headers=user).json()["documents"]
    assert [d["ingestion"]["status"] for d in redone] == ["completed"] and _passages(pid)


def test_sheldon_names_documents_still_processing(env, monkeypatch):
    client, user = env["client"], env["user"]
    eid = _engagement(env)
    with session_scope() as db:
        db.add(DocumentJob(id=f"doc_{uuid.uuid4().hex[:12]}", job_id=str(uuid.uuid4()), project_id=eid, user_id="x",
                           filename="budget.xlsx", status="parsing"))
    _route_as(monkeypatch, "knowledge_question")
    reply = client.post(f"/api/projects/{eid}/conversation/messages", headers=user,
                        json={"content": "How long do vendor master changes take?"}).json()["messages"][-1]
    assert "Still processing, so not searched yet: budget.xlsx" in reply["content"]
    assert reply["metadata"]["pending_documents"] == ["budget.xlsx"]


# --- POST /api/query -----------------------------------------------------------------------------------------------


def test_candidates_are_never_retrieved_or_shown(env):
    client, user = env["client"], env["user"]
    r = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"}).json()
    assert r["status"] == "insufficient_evidence" and r["reason"] == "no_results" and r["sources"] == []
    assert client.get(f"/api/query/sources/chunk/{env['chunks'][0]}", headers=user).status_code == 404


def test_library_answer_with_stateless_follow_up(env):
    client, user = env["client"], env["user"]
    env["released"].add(env["doc"])

    first = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "answered" and body["understanding"]["question_type"] == "how"
    cite = body["citations"][0]
    assert cite["type"] == "chunk" and cite["scope"] == "library" and cite["practice_id"] == env["practice"]
    assert cite["link"] == f"/api/query/sources/chunk/{cite['id']}" and body["coverage"]["fully_cited"]
    source = client.get(cite["link"], headers=user).json()
    assert source["text"] and source["practice_id"] == env["practice"] and source["verification"] == 1.0

    history = [{"role": "user", "content": "How are vendors screened?"}, {"role": "assistant", "content": body["answer"]}]
    follow = client.post("/api/query", headers=user, json={"question": "and what about it?", "history": history}).json()
    assert follow["understanding"]["is_follow_up"] and follow["standalone_question"].startswith("How are new vendors")


def test_engagement_documents_are_answered_for_members_only(env):
    client, user, admin = env["client"], env["user"], env["admin"]
    eid = _engagement(env)
    r = client.post("/api/query", headers=user,
                    json={"question": "How long do vendor master changes take?", "engagement_id": eid, "include_library": False})
    assert r.status_code == 200, r.text
    cite = r.json()["citations"][0]
    assert cite["type"] == "chunk" and cite["scope"] == "engagement" and cite["filename"] == "workshop-notes.txt"
    assert cite["link"].endswith(f"?engagement_id={eid}")
    assert "Vendor master changes" in client.get(cite["link"], headers=user).json()["text"]

    # Not a member: no answer and no source text from that engagement.
    assert client.post("/api/query", headers=admin, json={"question": "How long?", "engagement_id": eid}).status_code == 403
    assert client.get(cite["link"], headers=admin).status_code == 404
    assert client.post("/api/query", headers=user, json={"question": "x y", "include_library": False}).status_code == 422


def test_health_reports_readiness_and_limits(env, monkeypatch):
    from src.app.api import query as query_api

    monkeypatch.setattr(query_api, "get_qdrant_client", qp.get_qdrant_client)  # the in-memory store
    monkeypatch.setattr(query_api, "is_claude_enabled", lambda: False)
    h = env["client"].get("/api/query/health", headers=env["user"]).json()
    assert h["search_available"] and not h["model_available"] and not h["ready"]

    def unreachable(*_a, **_k):
        raise ConnectionError("down")

    monkeypatch.setattr(query_api, "get_qdrant_client", unreachable)
    assert env["client"].get("/api/query/health", headers=env["user"]).json()["search_available"] is False
    assert h["limits"]["question_max_chars"] == 2000 and h["limits"]["top_k_default"] == settings.query_top_k


def test_model_failure_and_search_outage(env, monkeypatch):
    client, user = env["client"], env["user"]
    env["released"].add(env["doc"])

    def down(**_):
        raise RuntimeError("down")

    monkeypatch.setattr(qp, "claude_generate", down)
    r = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"}).json()
    assert r["status"] == "llm_unavailable" and r["answer"].startswith("Unable to process question now") and r["sources"]
    assert r["model_calls"] == 3

    def outage(pid, vectors):
        raise ConnectionError("qdrant unreachable at http://10.0.0.5:6333")

    monkeypatch.setattr(qp, "search", outage)
    failed = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"})
    assert failed.status_code == 503 and "10.0.0.5" not in failed.text  # no internal details
    assert client.post("/api/query").status_code == 401


# --- Sheldon: router agent -> rag_agent --------------------------------------------------------------------------


def _route_as(monkeypatch, intent: str, rationale: str = "router decision"):
    def fake_route_turn(**_):
        return RouterDecision(intent=intent, confidence=0.9, extracted_slots={}, output_types=[], representations={},
                              content_skill_hint=None, next_state="exploring", missing_slots=[], reply_hint=None,
                              rationale=rationale)

    monkeypatch.setattr(projects_module, "route_turn", fake_route_turn)


def test_sheldon_sends_document_questions_to_the_rag_agent(env, monkeypatch):
    client, user = env["client"], env["user"]
    env["released"].add(env["doc"])
    eid = _engagement(env)
    _route_as(monkeypatch, "knowledge_question")
    resp = client.post(f"/api/projects/{eid}/conversation/messages", headers=user,
                       json={"content": "How long do vendor master changes take?"})
    assert resp.status_code == 200, resp.text
    reply = resp.json()["messages"][-1]
    meta = reply["metadata"]
    assert reply["role"] == "assistant" and meta["kind"] == "rag_answer" and meta["status"] == "answered"
    assert "[S1]" in reply["content"] and "Sources:" in reply["content"]
    assert {s["scope"] for s in meta["sources"]} == {"engagement", "library"}  # the engagement's files + the library
    assert meta["scope"]["engagement_id"] == eid


def test_sheldon_says_so_when_nothing_supports_an_answer(env, monkeypatch):
    client, user = env["client"], env["user"]
    eid = _engagement(env)
    monkeypatch.setattr(qp, "claude_generate", lambda **_: "INSUFFICIENT_EVIDENCE")
    _route_as(monkeypatch, "knowledge_question")
    reply = client.post(f"/api/projects/{eid}/conversation/messages", headers=user,
                        json={"content": "What is the client's cafeteria budget?"}).json()["messages"][-1]
    assert reply["metadata"]["status"] == "insufficient_evidence" and "won't guess" in reply["content"]


def test_sheldon_keeps_chat_away_from_the_rag_agent(env, monkeypatch):
    client, user = env["client"], env["user"]
    eid = _engagement(env)
    _route_as(monkeypatch, "smalltalk")
    monkeypatch.setattr(projects_module, "_recommend_output_types", lambda *_a, **_k: ([], [], {}, "", None))
    reply = client.post(f"/api/projects/{eid}/conversation/messages", headers=user,
                        json={"content": "Thanks, that was a useful workshop yesterday"}).json()["messages"][-1]
    assert reply["metadata"]["kind"] == "conversational_response"


@pytest.mark.parametrize("intent, rationale, message, state, expected", [
    ("knowledge_question", "", "What does the workshop say about vendor master changes?", "exploring", "rag"),
    ("knowledge_question", "", "Create a deck on vendor master changes", "exploring", "supervisor"),
    ("clarify", "router_llm_unavailable", "What does the report say about AP?", "exploring", "rag"),
    ("discovery_answer", "router_llm_unavailable", "What does the report say about AP?", "discovery", "supervisor"),
    ("commit", "", "Go with the SCQA arc", "storyline_building", "supervisor"),
    ("smalltalk", "", "Thanks!", "exploring", "conversation"),
])
def test_router_agent_picks_the_agent(intent, rationale, message, state, expected):
    assert router_agent.route(intent=intent, rationale=rationale, message=message, state=state) == expected


# --- Talk to data ---------------------------------------------------------------------------------------------------


def test_talk_to_data_answers_through_the_query_pipeline(env):
    client, user = env["client"], env["user"]
    env["released"].add(env["doc"])
    with session_scope() as db:
        db.get(LpPractice, env["practice"]).status = "Approved"
    r = client.post("/api/library/ask", headers=user, json={"question": "How are new vendors screened?"}).json()
    assert r["status"] == "answered" and r["answer"].endswith("[1].") and "[S1]" not in r["answer"]
    assert r["sources"][0]["practiceId"] == env["practice"] and r["citations"][0]["ref"] == "1"
    assert [p["id"] for p in r["practices"]] == [env["practice"]]
