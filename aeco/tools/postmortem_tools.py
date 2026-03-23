"""Tools for postmortem documentation: git snapshot and optional page screenshots."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from aeco.config import settings
from aeco.tools.file_tools import _resolve_workspace_path

logger = logging.getLogger(__name__)


def _workspace_root(ws: str | None) -> Path:
    return Path(ws or settings.workspace_path).expanduser().resolve()


def _find_chrome_binary() -> str | None:
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(name)
        if p:
            return p
    if sys.platform == "darwin":
        mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        if os.path.isfile(mac):
            return mac
    return None


async def git_workspace_snapshot(
    workspace_path: str | None = None,
    max_diff_chars: int = 16000,
) -> dict[str, Any]:
    """Return git status, diff --stat, and a truncated diff for the workspace (if it is a git repo)."""
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if not (root / ".git").exists():
            return {
                "status": "not_a_git_repo",
                "message": f"No .git at {root}. Change summary cannot be computed from git.",
                "workspace_root": str(root),
            }
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "1"}
        try:
            st = subprocess.run(
                ["git", "-C", str(root), "status", "--short"],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            stat = subprocess.run(
                ["git", "-C", str(root), "diff", "--stat", "HEAD"],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
            )
            diff = subprocess.run(
                ["git", "-C", str(root), "diff", "HEAD"],
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
        except subprocess.TimeoutExpired as e:
            return {"status": "error", "error": f"git timeout: {e}"}
        except FileNotFoundError:
            return {"status": "error", "error": "git binary not found on PATH"}

        diff_text = (diff.stdout or "") + (diff.stderr or "")
        truncated = diff_text
        if len(truncated) > max_diff_chars:
            truncated = truncated[:max_diff_chars] + "\n\n… [diff truncated by max_diff_chars] …"

        return {
            "status": "ok",
            "workspace_root": str(root),
            "git_status_short": st.stdout or "(empty)",
            "git_diff_stat": stat.stdout or "(empty)",
            "git_diff_excerpt": truncated,
            "diff_total_chars": len(diff_text),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def capture_page_screenshot(
    url: str,
    relative_path: str,
    workspace_path: str | None = None,
    width: int = 1280,
    height: int = 720,
) -> dict[str, Any]:
    """Capture a viewport screenshot of a URL using headless Chrome/Chromium; saves PNG under workspace."""
    if not url or not url.startswith(("http://", "https://")):
        return {"status": "error", "error": "url must start with http:// or https://"}

    if not relative_path.lower().endswith(".png"):
        return {"status": "error", "error": "relative_path must end with .png"}

    try:
        out = _resolve_workspace_path(relative_path.strip(), workspace_path)
    except ValueError as e:
        return {"status": "error", "error": str(e)}

    root = _workspace_root(workspace_path)
    chrome = _find_chrome_binary()
    if not chrome:
        return {
            "status": "unavailable",
            "error": "No Chrome/Chromium found. Install Google Chrome or set PATH to chromium.",
        }

    out.parent.mkdir(parents=True, exist_ok=True)

    def _shot() -> dict[str, Any]:
        cmd = [
            chrome,
            "--headless",
            "--disable-gpu",
            f"--window-size={width},{height}",
            f"--screenshot={out}",
            "--hide-scrollbars",
            "--no-sandbox",
            url,
        ]
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=90,
            )
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "screenshot timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

        if r.returncode != 0:
            return {
                "status": "error",
                "error": (r.stderr or r.stdout or "chrome failed")[:500],
            }
        if not out.is_file():
            return {"status": "error", "error": "screenshot file was not created"}
        rel = out.relative_to(root)
        return {
            "status": "ok",
            "path": str(rel),
            "url": url,
            "bytes": out.stat().st_size,
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _shot)
