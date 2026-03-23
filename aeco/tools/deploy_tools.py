"""Deployment tools for agents: preview, production, rollback via Vercel CLI."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from aeco.config import settings

logger = logging.getLogger(__name__)


def _workspace_root(ws: str | None) -> Path:
    return Path(ws or settings.workspace_path).expanduser().resolve()


def _find_cli(name: str) -> str | None:
    return shutil.which(name)


async def deploy_preview(
    workspace_path: str | None = None,
    provider: str = "vercel",
) -> dict[str, Any]:
    """Deploy to a preview environment and return the preview URL.

    Args:
        workspace_path: Project root to deploy.
        provider: Hosting provider ('vercel' or 'netlify').
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if provider == "vercel":
            cli = _find_cli("vercel")
            if not cli:
                return {"status": "error", "error": "Vercel CLI not found. Install with: npm i -g vercel"}

            r = subprocess.run(
                [cli, "--yes", "--cwd", str(root)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(root),
            )
            if r.returncode != 0:
                return {"status": "error", "error": f"vercel deploy failed: {r.stderr.strip()[:500]}"}

            # Vercel outputs the preview URL on stdout
            url = r.stdout.strip().split("\n")[-1]
            return {"status": "ok", "preview_url": url, "provider": "vercel"}

        elif provider == "netlify":
            cli = _find_cli("netlify")
            if not cli:
                return {"status": "error", "error": "Netlify CLI not found. Install with: npm i -g netlify-cli"}

            r = subprocess.run(
                [cli, "deploy", "--dir", str(root), "--json"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(root),
            )
            if r.returncode != 0:
                return {"status": "error", "error": f"netlify deploy failed: {r.stderr.strip()[:500]}"}

            import json
            try:
                result = json.loads(r.stdout)
                url = result.get("deploy_url", r.stdout.strip())
            except json.JSONDecodeError:
                url = r.stdout.strip().split("\n")[-1]
            return {"status": "ok", "preview_url": url, "provider": "netlify"}

        return {"status": "error", "error": f"Unknown provider: {provider}. Supported: vercel, netlify"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def deploy_production(
    workspace_path: str | None = None,
    provider: str = "vercel",
) -> dict[str, Any]:
    """Promote to production deployment.

    Args:
        workspace_path: Project root to deploy.
        provider: Hosting provider.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if provider == "vercel":
            cli = _find_cli("vercel")
            if not cli:
                return {"status": "error", "error": "Vercel CLI not found."}

            r = subprocess.run(
                [cli, "--yes", "--prod", "--cwd", str(root)],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(root),
            )
            if r.returncode != 0:
                return {"status": "error", "error": f"vercel --prod failed: {r.stderr.strip()[:500]}"}

            url = r.stdout.strip().split("\n")[-1]
            return {"status": "ok", "production_url": url, "provider": "vercel"}

        elif provider == "netlify":
            cli = _find_cli("netlify")
            if not cli:
                return {"status": "error", "error": "Netlify CLI not found."}

            r = subprocess.run(
                [cli, "deploy", "--dir", str(root), "--prod", "--json"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(root),
            )
            if r.returncode != 0:
                return {"status": "error", "error": f"netlify deploy --prod failed: {r.stderr.strip()[:500]}"}

            import json
            try:
                result = json.loads(r.stdout)
                url = result.get("url", r.stdout.strip())
            except json.JSONDecodeError:
                url = r.stdout.strip().split("\n")[-1]
            return {"status": "ok", "production_url": url, "provider": "netlify"}

        return {"status": "error", "error": f"Unknown provider: {provider}"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)


async def deploy_rollback(
    workspace_path: str | None = None,
    provider: str = "vercel",
) -> dict[str, Any]:
    """Rollback the production deployment to the previous version.

    Args:
        workspace_path: Project root.
        provider: Hosting provider.
    """
    root = _workspace_root(workspace_path)

    def _run() -> dict[str, Any]:
        if provider == "vercel":
            cli = _find_cli("vercel")
            if not cli:
                return {"status": "error", "error": "Vercel CLI not found."}

            # Vercel rollback via CLI
            r = subprocess.run(
                [cli, "rollback", "--yes", "--cwd", str(root)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(root),
            )
            if r.returncode != 0:
                return {"status": "error", "error": f"vercel rollback failed: {r.stderr.strip()[:500]}"}

            return {"status": "ok", "action": "rolled_back", "provider": "vercel"}

        return {"status": "error", "error": f"Rollback not supported for provider: {provider}"}

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _run)
