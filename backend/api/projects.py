"""
api/projects.py
---------------
Project-related API routes.

Currently a stub — all endpoints return placeholder responses so the router
can be wired up and tested end-to-end before the database layer (Phase 2) and
agent pipeline (Phases 4-6) are built.

Real implementations will be added phase by phase:
  Phase 2 → persist/fetch projects from DB
  Phase 5 → POST /projects triggers the generation run + opens WebSocket
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from core.security import get_current_user

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    prompt: str


# ── List all projects ────────────────────────────────────────────────────────

@router.get("/", summary="List projects")
async def list_projects(user_id: str = Depends(get_current_user)):
    """
    Return the authenticated user's projects.

    TODO (Phase 2): query the DB for projects belonging to the current user.
    """
    return {"projects": [], "message": "stub — no DB yet"}


# ── Get a single project ─────────────────────────────────────────────────────

@router.get("/{project_id}", summary="Get project")
async def get_project(project_id: str, user_id: str = Depends(get_current_user)):
    """
    Return a single project by id.

    TODO (Phase 2): fetch from DB; raise 404 if not found or not owned by user.
    """
    return {"project_id": project_id, "message": "stub — no DB yet"}


# ── Create a project + kick off a generation run ─────────────────────────────

@router.post("/", summary="Create project", status_code=201)
async def create_project(payload: CreateProjectRequest, user_id: str = Depends(get_current_user)):
    """
    Accept a natural-language prompt, create a Project + GenerationRun row,
    and return the run_id the frontend will use to open a WebSocket connection.

    TODO (Phase 2): insert Project + GenerationRun rows into DB.
    TODO (Phase 5): start `graph.astream_events()` and wire to WebSocket.
    """
    return {
        "project_id": "stub-project-id",
        "run_id": "stub-run-id",
        "message": "stub — agent pipeline not wired yet",
        "prompt": payload.prompt,
    }
