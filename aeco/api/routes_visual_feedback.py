"""Visual Feedback API: upload a screenshot + describe what to change.

POST /api/visual-feedback — upload screenshot + text, engineer fixes it
GET  /api/visual-feedback/{task_id} — check status
GET  /api/visual-feedback — list recent tasks
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from aeco.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/visual-feedback", tags=["visual-feedback"])

# In-memory store
_feedback_tasks: Dict[str, dict] = {}

# Set by main.py
_registry = None
_audit_logger = None


def set_dependencies(registry, audit_logger):
    global _registry, _audit_logger
    _registry = registry
    _audit_logger = audit_logger


# --- Response models ---

class VisualFeedbackResponse(BaseModel):
    task_id: str
    status: str  # running, done, error
    feedback: str
    screenshot_path: Optional[str] = None
    files_changed: List[str] = []
    git_commit: Optional[str] = None
    before_screenshot: Optional[str] = None
    after_screenshot: Optional[str] = None
    error: Optional[str] = None


# --- Endpoints ---

@router.post("", status_code=202)
async def submit_visual_feedback(
    feedback: str = Form(..., description="What needs to change — e.g. 'make the button blue' or 'fix the spacing on mobile'"),
    screenshot: UploadFile = File(..., description="Screenshot showing what needs to change"),
    workspace_path: str = Form(default="", description="Path to the project workspace"),
    target_file: Optional[str] = Form(default=None, description="Optional: specific file to edit (e.g. 'src/app/page.tsx')"),
    initiative_id: Optional[str] = Form(default=None, description="Optional: link to an existing initiative"),
):
    """Upload a screenshot and describe what to change. An engineer will fix it."""
    if _registry is None:
        raise HTTPException(status_code=503, detail="Visual feedback not initialized")

    task_id = str(uuid.uuid4())
    ws = workspace_path or getattr(settings, "default_workspace_path", "")
    if not ws:
        raise HTTPException(status_code=400, detail="workspace_path is required")

    # Save screenshot to workspace
    screenshots_dir = Path(ws) / ".aeco" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / f"feedback-{task_id[:8]}.png"

    content = await screenshot.read()
    screenshot_path.write_bytes(content)
    logger.info(f"Saved feedback screenshot to {screenshot_path} ({len(content)} bytes)")

    task_state = {
        "task_id": task_id,
        "feedback": feedback,
        "screenshot_path": str(screenshot_path),
        "workspace_path": ws,
        "target_file": target_file,
        "initiative_id": initiative_id,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "files_changed": [],
        "git_commit": None,
        "after_screenshot": None,
        "error": None,
    }
    _feedback_tasks[task_id] = task_state

    asyncio.create_task(_execute_visual_feedback(task_id))

    return {
        "task_id": task_id,
        "status": "running",
        "message": f"Engineer will review your screenshot and apply: {feedback}",
    }


@router.get("/{task_id}")
async def get_visual_feedback_status(task_id: str) -> VisualFeedbackResponse:
    task = _feedback_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return VisualFeedbackResponse(
        task_id=task_id,
        status=task["status"],
        feedback=task["feedback"],
        screenshot_path=task.get("screenshot_path"),
        files_changed=task.get("files_changed", []),
        git_commit=task.get("git_commit"),
        before_screenshot=task.get("screenshot_path"),
        after_screenshot=task.get("after_screenshot"),
        error=task.get("error"),
    )


@router.get("")
async def list_visual_feedback_tasks():
    return [
        {
            "task_id": tid,
            "feedback": t["feedback"],
            "status": t["status"],
            "started_at": t["started_at"],
        }
        for tid, t in sorted(
            _feedback_tasks.items(),
            key=lambda x: x[1]["started_at"],
            reverse=True,
        )
    ][:20]


# --- Execution ---

async def _execute_visual_feedback(task_id: str):
    """Run the visual feedback task: send screenshot + feedback to frontend engineer."""
    task = _feedback_tasks[task_id]

    try:
        from aeco.agents.runtime import create_executor

        # Pick the right engineer
        agent_id = "frontend_engineer"
        if task.get("target_file") and any(
            task["target_file"].endswith(ext) for ext in (".py", ".sql", ".sh")
        ):
            agent_id = "backend_engineer"

        if not _registry.has(agent_id):
            agent_id = "fullstack_engineer"

        agent_def = _registry.get(agent_id)
        runtime = create_executor(agent_def, _audit_logger)

        # Build context with screenshot reference
        context = {
            "task_title": f"Visual feedback: {task['feedback'][:80]}",
            "task_description": (
                f"The founder uploaded a screenshot and wants this change:\n\n"
                f"**Feedback:** {task['feedback']}\n\n"
                f"**Screenshot path:** {task['screenshot_path']}\n"
                f"IMPORTANT: Read the screenshot file at the path above to see what the founder sees.\n"
                f"Then make the requested changes.\n\n"
                + (f"**Target file hint:** {task['target_file']}\n" if task.get("target_file") else "")
                + f"**Workspace:** {task['workspace_path']}\n\n"
                f"After making changes:\n"
                f"1. git add and commit with message '[AECO] Visual feedback: {task['feedback'][:50]}'\n"
                f"2. If possible, start the dev server and take a screenshot of the result\n"
            ),
            "workspace_path": task["workspace_path"],
            "acceptance_criteria": [
                f"The change requested by the founder is applied: {task['feedback']}",
                "Code compiles without errors",
                "Changes are committed to git",
            ],
        }

        result = await asyncio.wait_for(
            runtime.execute(context),
            timeout=getattr(settings, "visual_feedback_timeout_seconds", 300),
        )

        # Extract results
        task["files_changed"] = result.get("files_changed", result.get("files_modified", []))
        task["git_commit"] = result.get("git_commit", result.get("commit_hash", ""))
        task["after_screenshot"] = result.get("after_screenshot", "")
        task["status"] = "done"

        logger.info(
            f"Visual feedback task {task_id} completed: "
            f"{len(task['files_changed'])} files changed, commit={task['git_commit']}"
        )

    except asyncio.TimeoutError:
        task["status"] = "error"
        task["error"] = "Task timed out after 300s"
        logger.error(f"Visual feedback task {task_id} timed out")

    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)
        logger.error(f"Visual feedback task {task_id} failed: {e}")
