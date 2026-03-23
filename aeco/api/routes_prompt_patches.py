"""API routes for prompt patch management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from aeco.db.session import async_session_factory

router = APIRouter(prefix="/api/prompt-patches", tags=["prompt-patches"])


class PatchResponse(BaseModel):
    id: str
    agent_id: str
    prompt_file: str
    section: Optional[str] = None
    action: str
    content: str
    evidence: str
    expected_improvement: str
    status: str
    applied_at: Optional[str] = None
    created_at: str


@router.get("")
async def list_patches(status: Optional[str] = None):
    """List all prompt patches, optionally filtered by status."""
    from sqlalchemy import select
    from aeco.models.prompt_patch import PromptPatch

    async with async_session_factory() as session:
        stmt = select(PromptPatch).order_by(PromptPatch.created_at.desc())
        if status:
            stmt = stmt.where(PromptPatch.status == status)
        result = await session.execute(stmt)
        patches = []
        for p in result.scalars():
            patches.append({
                "id": str(p.id),
                "agent_id": p.agent_id,
                "prompt_file": p.prompt_file,
                "section": p.section,
                "action": p.action,
                "content": p.content,
                "evidence": p.evidence,
                "expected_improvement": p.expected_improvement,
                "status": p.status,
                "applied_at": p.applied_at.isoformat() if p.applied_at else None,
                "created_at": p.created_at.isoformat(),
            })
    return {"patches": patches}


@router.post("/{patch_id}/approve")
async def approve_patch(patch_id: str):
    """Approve a proposed patch — it will be injected at runtime."""
    from sqlalchemy import select
    from aeco.models.prompt_patch import PromptPatch
    from aeco.agents.prompt_patcher import load_active_patches

    async with async_session_factory() as session:
        stmt = select(PromptPatch).where(PromptPatch.id == uuid.UUID(patch_id))
        result = await session.execute(stmt)
        patch = result.scalar_one_or_none()
        if not patch:
            raise HTTPException(404, "Patch not found")
        if patch.status != "proposed":
            raise HTTPException(400, f"Patch is already {patch.status}")

        patch.status = "approved"
        patch.applied_at = datetime.now(timezone.utc)
        await session.commit()

        # Reload active patches in memory
        await _reload_active_patches(session)

    return {"status": "approved", "patch_id": patch_id}


@router.post("/{patch_id}/reject")
async def reject_patch(patch_id: str):
    """Reject a proposed patch."""
    from sqlalchemy import select
    from aeco.models.prompt_patch import PromptPatch

    async with async_session_factory() as session:
        stmt = select(PromptPatch).where(PromptPatch.id == uuid.UUID(patch_id))
        result = await session.execute(stmt)
        patch = result.scalar_one_or_none()
        if not patch:
            raise HTTPException(404, "Patch not found")

        patch.status = "rejected"
        await session.commit()

    return {"status": "rejected", "patch_id": patch_id}


@router.delete("/{patch_id}")
async def delete_patch(patch_id: str):
    """Remove a patch entirely."""
    from sqlalchemy import select, delete
    from aeco.models.prompt_patch import PromptPatch

    async with async_session_factory() as session:
        stmt = delete(PromptPatch).where(PromptPatch.id == uuid.UUID(patch_id))
        await session.execute(stmt)
        await session.commit()

        await _reload_active_patches(session)

    return {"status": "deleted"}


async def _reload_active_patches(session):
    """Reload all approved patches into the in-memory patcher."""
    from sqlalchemy import select
    from aeco.models.prompt_patch import PromptPatch
    from aeco.agents.prompt_patcher import load_active_patches

    stmt = select(PromptPatch).where(PromptPatch.status == "approved")
    result = await session.execute(stmt)
    patches = [
        {
            "agent_id": p.agent_id,
            "content": p.content,
            "evidence": p.evidence,
            "section": p.section,
            "action": p.action,
        }
        for p in result.scalars()
    ]
    load_active_patches(patches)
