"""Git operations for agents: commit, branch, push, checkout, merge."""
from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)


def _workspace_root(ws: str | None) -> Path:
    return Path(ws or settings.workspace_path).expanduser().resolve()


def _git(root: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a git command in the workspace root."""
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "1"}
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


async def git_commit(
    message: str,
    files: list[str] | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Stage specified files (or all changes) and commit.

    Args:
        message: Commit message.
        files: Specific files to stage. If empty/None, stages all changes.
        workspace_path: Override workspace root.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if not (root / ".git").exists():
            return {"status": "error", "error": f"No git repo at {root}"}

        # Stage
        if files:
            for f in files:
                r = _git(root, "add", f)
                if r.returncode != 0:
                    return {"status": "error", "error": f"git add {f}: {r.stderr.strip()}"}
        else:
            r = _git(root, "add", "-A")
            if r.returncode != 0:
                return {"status": "error", "error": f"git add -A: {r.stderr.strip()}"}

        # Check if anything staged
        diff = _git(root, "diff", "--cached", "--stat")
        if not diff.stdout.strip():
            return {"status": "no_changes", "message": "Nothing to commit (no staged changes)"}

        # Commit
        r = _git(root, "commit", "-m", message)
        if r.returncode != 0:
            return {"status": "error", "error": f"git commit: {r.stderr.strip()}"}

        # Get the commit hash
        rev = _git(root, "rev-parse", "--short", "HEAD")
        return {
            "status": "ok",
            "commit": rev.stdout.strip(),
            "message": message,
            "files_staged": files or ["all"],
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def git_branch(
    branch_name: str,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Create and checkout a new branch.

    Args:
        branch_name: Name for the new branch.
        workspace_path: Override workspace root.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if not (root / ".git").exists():
            return {"status": "error", "error": f"No git repo at {root}"}

        r = _git(root, "checkout", "-b", branch_name)
        if r.returncode != 0:
            # Branch might already exist, try switching
            r2 = _git(root, "checkout", branch_name)
            if r2.returncode != 0:
                return {"status": "error", "error": f"git checkout -b: {r.stderr.strip()}"}
            return {"status": "ok", "branch": branch_name, "action": "switched_to_existing"}

        return {"status": "ok", "branch": branch_name, "action": "created"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def git_push(
    remote: str = "origin",
    branch: str | None = None,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Push the current branch to a remote.

    Args:
        remote: Git remote name (default: origin).
        branch: Branch to push. If None, pushes the current branch.
        workspace_path: Override workspace root.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if not (root / ".git").exists():
            return {"status": "error", "error": f"No git repo at {root}"}

        if not branch:
            rev = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
            current = rev.stdout.strip()
        else:
            current = branch

        r = _git(root, "push", "-u", remote, current, timeout=120)
        if r.returncode != 0:
            return {"status": "error", "error": f"git push: {r.stderr.strip()}"}

        return {"status": "ok", "remote": remote, "branch": current}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def git_checkout(
    branch: str,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Switch to an existing branch.

    Args:
        branch: Branch name to checkout.
        workspace_path: Override workspace root.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if not (root / ".git").exists():
            return {"status": "error", "error": f"No git repo at {root}"}

        r = _git(root, "checkout", branch)
        if r.returncode != 0:
            return {"status": "error", "error": f"git checkout: {r.stderr.strip()}"}

        return {"status": "ok", "branch": branch}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def git_merge(
    source_branch: str,
    workspace_path: str | None = None,
) -> dict[str, Any]:
    """Merge a source branch into the current branch.

    Args:
        source_branch: Branch to merge from.
        workspace_path: Override workspace root.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if not (root / ".git").exists():
            return {"status": "error", "error": f"No git repo at {root}"}

        r = _git(root, "merge", source_branch, "--no-edit")
        if r.returncode != 0:
            # Abort the merge if it conflicts
            _git(root, "merge", "--abort")
            return {
                "status": "conflict",
                "error": f"Merge conflict merging {source_branch}. Merge aborted.",
                "details": r.stdout.strip(),
            }

        rev = _git(root, "rev-parse", "--short", "HEAD")
        return {
            "status": "ok",
            "merged": source_branch,
            "commit": rev.stdout.strip(),
        }

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)
