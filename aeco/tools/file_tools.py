from __future__ import annotations

from pathlib import Path

from aeco.config import settings


def _resolve_workspace_path(relative_path: str, workspace_path: str | None = None) -> Path:
    """Resolve a path within the workspace, preventing directory traversal."""
    ws = workspace_path or settings.workspace_path
    workspace = Path(ws).resolve()
    target = (workspace / relative_path).resolve()
    if not str(target).startswith(str(workspace)):
        raise ValueError(f"Path '{relative_path}' escapes workspace directory")
    return target


async def file_write(path: str, content: str, workspace_path: str | None = None) -> dict:
    """Write content to a file in the workspace."""
    target = _resolve_workspace_path(path, workspace_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    ws = workspace_path or settings.workspace_path
    return {"status": "ok", "path": str(target.relative_to(Path(ws).resolve()))}


async def file_read(path: str, workspace_path: str | None = None) -> dict:
    """Read a file from the workspace."""
    target = _resolve_workspace_path(path, workspace_path)
    if not target.exists():
        return {"status": "error", "error": f"File not found: {path}"}
    return {"status": "ok", "content": target.read_text(), "path": path}
