from pathlib import Path

from aeco.config import settings


def _resolve_workspace_path(relative_path: str) -> Path:
    """Resolve a path within the workspace, preventing directory traversal."""
    workspace = Path(settings.workspace_path).resolve()
    target = (workspace / relative_path).resolve()
    if not str(target).startswith(str(workspace)):
        raise ValueError(f"Path '{relative_path}' escapes workspace directory")
    return target


async def file_write(path: str, content: str) -> dict:
    """Write content to a file in the workspace."""
    target = _resolve_workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return {"status": "ok", "path": str(target.relative_to(Path(settings.workspace_path).resolve()))}


async def file_read(path: str) -> dict:
    """Read a file from the workspace."""
    target = _resolve_workspace_path(path)
    if not target.exists():
        return {"status": "error", "error": f"File not found: {path}"}
    return {"status": "ok", "content": target.read_text(), "path": path}
