"""Query API: ask with stored conversations, follow-ups from server-side history, conversation management,
cited-source lookup, and released-only visibility, over a source that went through the ingestion pipeline."""

import pytest
from fastapi.testclient import TestClient

from src.core.config import settings
from src.core.db.models import ChunkArchive, DocumentChunkLink
from src.core.db.session import session_scope
from src.query import pipeline as qp
from tests.unit import _pipeline_fakes
from tests.unit.test_library_ingestion import _login, _upload


@pytest.fixture
def env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from src.app.main import app as fastapi_app

    monkeypatch.setattr(settings, "workspace_root", str(tmp_path))
    monkeypatch.setattr(settings, "lp_library_local_path", "")
    monkeypatch.setattr(settings, "query_llm_retry_backoff_sec", 0.0)
    _pipeline_fakes.install(monkeypatch)
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
    # The fake embedder hashes text, so similarity is meaningless: every passage of the source is a search hit.
    monkeypatch.setattr(qp, "search", lambda pid, vectors: [qp.Source("chunk", c, 0.8) for c in chunk_ids])
    questions: list[str] = []

    def fake_llm(*, system, user, **_):
        if "standalone" in system:
            return "How are new vendors screened before onboarding?"
        questions.append(user.rsplit("QUESTION: ", 1)[-1])
        return "Vendors are screened against the approved criteria [S1]."

    monkeypatch.setattr(qp, "claude_generate", fake_llm)
    return {"client": client, "admin": admin, "user": _login(client, admin=False), "doc": doc, "chunks": chunk_ids,
            "released": released, "practice": entry["practiceId"], "questions": questions}


def test_candidates_are_never_retrieved_or_shown(env):
    client, user = env["client"], env["user"]
    r = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"}).json()
    assert r["status"] == "insufficient_evidence" and r["reason"] == "no_results" and r["sources"] == []
    assert client.get(f"/api/query/sources/chunk/{env['chunks'][0]}", headers=user).status_code == 404


def test_ask_follow_up_and_manage_the_conversation(env):
    client, user = env["client"], env["user"]
    env["released"].add(env["doc"])

    first = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["status"] == "answered" and body["conversation_id"] and body["turn_id"]
    assert body["understanding"]["question_type"] == "how" and body["variants"][0]["kind"] == "original"
    cite = body["citations"][0]
    assert cite["type"] == "chunk" and cite["practice_id"] == env["practice"] and cite["practice_title"]
    assert cite["link"] == f"/api/query/sources/chunk/{cite['id']}" and body["coverage"]["fully_cited"]

    # Follow-up: only the conversation id is sent; the earlier turn comes from the server.
    follow = client.post("/api/query", headers=user,
                         json={"question": "and what about it?", "conversation_id": body["conversation_id"]}).json()
    assert follow["conversation_id"] == body["conversation_id"]
    assert follow["understanding"]["is_follow_up"] and follow["standalone_question"].startswith("How are new vendors")
    assert env["questions"][-1] == follow["standalone_question"]

    listing = client.get("/api/query/conversations", headers=user).json()
    assert listing["total"] == 1 and listing["items"][0]["turn_count"] == 2
    assert listing["items"][0]["title"] == "How are vendors screened?"
    thread = client.get(f"/api/query/conversations/{body['conversation_id']}", headers=user).json()
    assert [t["id"] for t in thread["turns"]] == [body["turn_id"], follow["turn_id"]]

    renamed = client.patch(f"/api/query/conversations/{body['conversation_id']}", headers=user, json={"title": "Vendors"})
    assert renamed.json()["title"] == "Vendors"

    source = client.get(cite["link"], headers=user).json()
    assert source["text"] and source["practice_id"] == env["practice"] and source["verification"] == 1.0

    assert client.delete(f"/api/query/conversations/{body['conversation_id']}", headers=user).status_code == 200
    assert client.get(f"/api/query/conversations/{body['conversation_id']}", headers=user).status_code == 404


def test_conversations_are_private_and_save_false_stores_nothing(env):
    client, user, admin = env["client"], env["user"], env["admin"]
    env["released"].add(env["doc"])
    conv = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"}).json()["conversation_id"]
    assert client.get(f"/api/query/conversations/{conv}", headers=admin).status_code == 404
    assert client.post("/api/query", headers=admin, json={"question": "x y z", "conversation_id": conv}).status_code == 404
    assert client.delete(f"/api/query/conversations/{conv}", headers=admin).status_code == 404

    stateless = client.post("/api/query", headers=admin, json={"question": "How are vendors screened?", "save": False}).json()
    assert stateless["status"] == "answered" and stateless["turn_id"] is None and stateless["conversation_id"] is None
    assert client.get("/api/query/conversations", headers=admin).json()["total"] == 0


def test_feedback_and_admin_metrics(env, monkeypatch):
    monkeypatch.setattr(settings, "advise_workbench_env", "production")  # admin checks are relaxed in development
    client, user, admin = env["client"], env["user"], env["admin"]
    env["released"].add(env["doc"])
    first = client.post("/api/query", headers=user, json={"question": "How are vendors screened?"}).json()
    conv, turn = first["conversation_id"], first["turn_id"]

    path = f"/api/query/conversations/{conv}/turns/{turn}/feedback"
    rated = client.put(path, headers=user, json={"rating": "down", "comment": "Missing the sanctions check"})
    assert rated.status_code == 200 and rated.json()["feedback"]["rating"] == "down"
    assert client.put(path, headers=user, json={"rating": "up"}).json()["feedback"] == {
        "rating": "up", "comment": "", "at": client.get(f"/api/query/conversations/{conv}", headers=user).json()["turns"][0]["feedback"]["at"]}
    assert client.put(path, headers=admin, json={"rating": "up"}).status_code == 404  # not their conversation
    assert client.put(f"/api/query/conversations/{conv}/turns/nope/feedback", headers=user, json={"rating": "up"}).status_code == 404

    env["released"].clear()  # nothing published -> an unanswered question for the content-gap list
    client.post("/api/query", headers=user, json={"question": "What is the vendor exit process?", "save": False})

    assert client.get("/api/admin/library/query/metrics", headers=user).status_code == 403
    m = client.get("/api/admin/library/query/metrics?days=7", headers=admin).json()
    assert m["total"] >= 2 and m["by_status"]["answered"] >= 1 and m["feedback"]["up"] >= 1
    assert any(u["question"] == "What is the vendor exit process?" and u["reason"] == "no_results" for u in m["unanswered_questions"])
    assert {"avg", "p50", "p95"} <= set(m["latency_ms"]) and m["daily"] and "how" not in m["by_intent"]


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
        raise ConnectionError("qdrant unreachable")

    monkeypatch.setattr(qp, "search", outage)
    assert client.post("/api/query", headers=user, json={"question": "How are vendors screened?"}).status_code == 503
    assert client.post("/api/query").status_code == 401
