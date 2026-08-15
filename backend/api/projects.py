"""
api/projects.py
---------------
Project-related API routes.

Handles creating projects, listing user projects, and fetching individual
projects with their generated files.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import get_current_user
from db.database import get_db
from db.models import GeneratedFile, GenerationRun, Project

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Request/Response schemas ─────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    prompt: str


class ProjectResponse(BaseModel):
    id: str
    prompt: str
    status: str
    created_at: str


class ProjectDetailResponse(BaseModel):
    id: str
    prompt: str
    status: str
    created_at: str
    files: dict[str, str]


class CreateProjectResponse(BaseModel):
    project_id: str
    run_id: str


# ── List all projects ────────────────────────────────────────────────────────

@router.get("/", summary="List projects")
async def list_projects(
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the authenticated user's projects, newest first."""
    result = await db.execute(
        select(Project)
        .where(Project.user_id == uuid.UUID(user_id))
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()

    return {
        "projects": [
            ProjectResponse(
                id=str(p.id),
                prompt=p.prompt,
                status=p.status,
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            for p in projects
        ]
    }


# ── Get a single project with files ──────────────────────────────────────────

@router.get("/{project_id}", summary="Get project")
async def get_project(
    project_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a single project with its generated files."""
    result = await db.execute(
        select(Project).where(
            Project.id == uuid.UUID(project_id),
            Project.user_id == uuid.UUID(user_id),
        )
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get the latest run's files
    run_result = await db.execute(
        select(GenerationRun)
        .where(GenerationRun.project_id == project.id)
        .order_by(GenerationRun.started_at.desc())
        .limit(1)
    )
    run = run_result.scalar_one_or_none()

    files: dict[str, str] = {}
    if run:
        files_result = await db.execute(
            select(GeneratedFile).where(GeneratedFile.run_id == run.id)
        )
        for f in files_result.scalars().all():
            files[f.path] = f.content

    return ProjectDetailResponse(
        id=str(project.id),
        prompt=project.prompt,
        status=project.status,
        created_at=project.created_at.isoformat() if project.created_at else "",
        files=files,
    )


# ── Create a project + generation run ────────────────────────────────────────

@router.post("/", summary="Create project", status_code=201)
async def create_project(
    payload: CreateProjectRequest,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a Project + GenerationRun and return the run_id.
    The frontend uses run_id to open the WebSocket connection.
    """
    project = Project(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        prompt=payload.prompt,
        status="running",
    )
    db.add(project)

    run = GenerationRun(
        id=uuid.uuid4(),
        project_id=project.id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)

    await db.commit()

    return CreateProjectResponse(
        project_id=str(project.id),
        run_id=str(run.id),
    )
