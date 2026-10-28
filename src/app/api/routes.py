from fastapi import APIRouter

from src.app.api import (
    admin_console,
    admin_library,
    agent_bash,
    auth,
    documents,
    documents_async,
    dpdp,
    drawio_collab,
    engagements,
    formats,
    library,
    lp_library,
    memory,
    model_realtime_ws,
    models,
    projects,
    query,
    reviews,
    run_artifacts,
    runs,
    skills,
    swarm,
    tasks,
    workbench,
)

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(projects.router, prefix="/projects", tags=["projects"])
router.include_router(agent_bash.router, prefix="/projects", tags=["agent-bash"])
router.include_router(engagements.router, prefix="/engagements", tags=["engagements"])
router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
router.include_router(library.router, tags=["library"])
router.include_router(workbench.router, tags=["workbench"])
router.include_router(admin_console.router, prefix="/admin", tags=["admin-console"])
router.include_router(admin_library.router, prefix="/admin", tags=["admin-library"])
router.include_router(documents.router, prefix="/documents", tags=["documents"])
router.include_router(documents_async.router, prefix="/admin/library/documents", tags=["library-documents"])
router.include_router(query.router, prefix="/query", tags=["query"])
router.include_router(query.admin_router, prefix="/admin/library/query", tags=["admin-library"])
router.include_router(runs.router, prefix="/runs", tags=["runs"])
router.include_router(swarm.router, prefix="/runs", tags=["swarm"])
router.include_router(run_artifacts.router, prefix="/runs", tags=["run-artifacts"])
router.include_router(drawio_collab.router, prefix="/drawio", tags=["drawio-collab"])
router.include_router(model_realtime_ws.router, prefix="/ws", tags=["model-realtime-ws"])
router.include_router(skills.router, prefix="/workspace/{pid}/skills", tags=["skills"])
router.include_router(formats.router, prefix="/workspace/{pid}", tags=["output-types"])
router.include_router(lp_library.router, prefix="/lp-library", tags=["lp-library"])
router.include_router(dpdp.router, prefix="/dpdp", tags=["dpdp"])
router.include_router(memory.router, prefix="/memory", tags=["memory"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(models.router, tags=["models"])
