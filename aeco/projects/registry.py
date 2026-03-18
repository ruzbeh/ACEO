"""Project registry — stores and retrieves scanned project contexts."""
from __future__ import annotations

import logging

from aeco.projects.scanner import ProjectContext, scan_project

logger = logging.getLogger(__name__)


class ProjectRegistry:
    """In-memory registry of registered projects, keyed by name."""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectContext] = {}

    async def register(self, name: str, workspace_path: str) -> ProjectContext:
        """Scan a workspace and register the project under *name*."""
        logger.info(f"Registering project '{name}' at {workspace_path}")
        ctx = await scan_project(workspace_path)
        # Override project_name to the user-supplied name
        ctx = ctx.model_copy(update={"project_name": name})
        self._projects[name] = ctx
        return ctx

    def get(self, name: str) -> ProjectContext | None:
        """Return a registered project context by name, or None."""
        return self._projects.get(name)

    def list_projects(self) -> list[ProjectContext]:
        """Return all registered project contexts."""
        return list(self._projects.values())


# Module-level singleton
project_registry = ProjectRegistry()
