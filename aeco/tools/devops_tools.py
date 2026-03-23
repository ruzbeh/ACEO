"""Package management and dev server tools for agents."""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)

# Track running dev server processes per workspace
_running_servers: dict[str, subprocess.Popen] = {}


def _workspace_root(ws: str | None) -> Path:
    return Path(ws or settings.workspace_path).expanduser().resolve()


def _detect_package_manager(root: Path) -> str | None:
    """Detect the package manager from project files."""
    if (root / "package-lock.json").exists() or (root / "package.json").exists():
        return "npm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "pyproject.toml").exists() or (root / "requirements.txt").exists():
        return "pip"
    if (root / "Pipfile").exists():
        return "pipenv"
    return None


async def package_install(
    workspace_path: str | None = None,
    manager: str | None = None,
) -> dict[str, Any]:
    """Install dependencies using the appropriate package manager.

    Args:
        workspace_path: Project root.
        manager: Force a specific package manager. Auto-detected if None.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        mgr = manager or _detect_package_manager(root)
        if not mgr:
            return {"status": "error", "error": f"No package manager detected in {root}"}

        commands = {
            "npm": ["npm", "install"],
            "yarn": ["yarn", "install"],
            "pnpm": ["pnpm", "install"],
            "pip": _pip_command(root),
            "pipenv": ["pipenv", "install"],
        }

        cmd = commands.get(mgr)
        if not cmd:
            return {"status": "error", "error": f"Unknown package manager: {mgr}"}

        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(root),
            )
        except FileNotFoundError:
            return {"status": "error", "error": f"{mgr} binary not found on PATH"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": f"{mgr} install timed out after 300s"}

        if r.returncode != 0:
            return {
                "status": "error",
                "error": f"{mgr} install failed: {r.stderr.strip()[:500]}",
            }

        return {
            "status": "ok",
            "manager": mgr,
            "output": r.stdout.strip()[-500:] if r.stdout else "",
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


def _pip_command(root: Path) -> list[str]:
    """Build the pip install command based on available files."""
    if (root / "pyproject.toml").exists():
        return ["pip", "install", "-e", "."]
    if (root / "requirements.txt").exists():
        return ["pip", "install", "-r", "requirements.txt"]
    return ["pip", "install", "."]


async def dev_server_start(
    command: str | None = None,
    workspace_path: str | None = None,
    port: int | None = None,
) -> dict[str, Any]:
    """Start a local dev server in the background.

    Args:
        command: Custom start command (e.g. 'npm run dev'). Auto-detected if None.
        workspace_path: Project root.
        port: Expected port (for reference in the response).
    """
    root = _workspace_root(workspace_path)
    key = str(root)

    # Stop existing server on same workspace
    if key in _running_servers:
        try:
            _running_servers[key].terminate()
        except ProcessLookupError:
            pass
        del _running_servers[key]

    if not command:
        # Auto-detect dev command
        if (root / "package.json").exists():
            command = "npm run dev"
            port = port or 3000
        elif (root / "pyproject.toml").exists():
            command = "python -m uvicorn main:app --reload --port 8000"
            port = port or 8000
        else:
            return {"status": "error", "error": "Cannot auto-detect dev command. Pass 'command' explicitly."}

    def _start() -> dict[str, Any]:
        try:
            proc = subprocess.Popen(
                command.split(),
                cwd=str(root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
            _running_servers[key] = proc

            # Wait a moment to check it doesn't immediately crash
            try:
                proc.wait(timeout=2)
                # If we get here, process exited (bad)
                stderr = proc.stderr.read().decode()[:500] if proc.stderr else ""
                return {
                    "status": "error",
                    "error": f"Server exited immediately (code {proc.returncode}): {stderr}",
                }
            except subprocess.TimeoutExpired:
                # Good - still running
                pass

            return {
                "status": "ok",
                "pid": proc.pid,
                "command": command,
                "port": port,
                "workspace": str(root),
            }
        except FileNotFoundError as e:
            return {"status": "error", "error": f"Command not found: {e}"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _start)


async def dev_server_stop(
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Stop a running dev server for the workspace.

    Args:
        workspace_path: Project root.
    """
    root = _workspace_root(workspace_path)
    key = str(root)

    if key not in _running_servers:
        return {"status": "ok", "message": "No server running for this workspace"}

    proc = _running_servers.pop(key)
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=10)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

    return {"status": "ok", "message": "Server stopped", "pid": proc.pid}
