"""Project registration and listing API routes."""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.db.session import get_session
from aeco.models.project import Project
from aeco.projects.registry import project_registry
from aeco.projects.scanner import ProjectContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["projects"])


class RegisterProjectRequest(BaseModel):
    name: str
    workspace_path: str


class ProjectResponse(BaseModel):
    id: Optional[str] = None
    name: str
    workspace_path: str
    language: Optional[str] = None
    framework: Optional[str] = None
    structure: dict = {}
    key_files: List[str] = []
    existing_patterns: str = ""

    model_config = {"from_attributes": True}


@router.post("", response_model=ProjectResponse, status_code=201)
async def register_project(
    req: RegisterProjectRequest, session: AsyncSession = Depends(get_session)
):
    """Register a project by name and workspace path. Scans the directory and stores metadata."""
    # Scan the project
    try:
        ctx: ProjectContext = await project_registry.register(req.name, req.workspace_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Persist to DB (upsert)
    result = await session.execute(select(Project).where(Project.name == req.name))
    existing = result.scalar_one_or_none()

    if existing:
        existing.workspace_path = ctx.workspace_path
        existing.language = ctx.language
        existing.framework = ctx.framework
        existing.structure = ctx.structure
        existing.key_files = ctx.key_files
        db_project = existing
    else:
        db_project = Project(
            id=uuid.uuid4(),
            name=ctx.project_name,
            workspace_path=ctx.workspace_path,
            language=ctx.language,
            framework=ctx.framework,
            structure=ctx.structure,
            key_files=ctx.key_files,
        )
        session.add(db_project)

    await session.commit()
    await session.refresh(db_project)

    return ProjectResponse(
        id=str(db_project.id),
        name=db_project.name,
        workspace_path=db_project.workspace_path,
        language=db_project.language,
        framework=db_project.framework,
        structure=db_project.structure,
        key_files=db_project.key_files,
        existing_patterns=ctx.existing_patterns,
    )


@router.get("", response_model=list[ProjectResponse])
async def list_projects(session: AsyncSession = Depends(get_session)):
    """List all registered projects."""
    result = await session.execute(select(Project).order_by(Project.name))
    projects = result.scalars().all()
    return [
        ProjectResponse(
            id=str(p.id),
            name=p.name,
            workspace_path=p.workspace_path,
            language=p.language,
            framework=p.framework,
            structure=p.structure,
            key_files=p.key_files,
        )
        for p in projects
    ]


@router.get("/{name}", response_model=ProjectResponse)
async def get_project(name: str, session: AsyncSession = Depends(get_session)):
    """Get project details by name, including structure."""
    result = await session.execute(select(Project).where(Project.name == name))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{name}' not found")

    # Also check in-memory registry for patterns (ephemeral data)
    ctx = project_registry.get(name)
    existing_patterns = ctx.existing_patterns if ctx else ""

    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        workspace_path=project.workspace_path,
        language=project.language,
        framework=project.framework,
        structure=project.structure,
        key_files=project.key_files,
        existing_patterns=existing_patterns,
    )
