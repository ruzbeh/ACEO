"""Context Builder: assembles focused context for each agent run.

Sits between memory layers and agent execution. For each run it assembles
relevant goal, PRD, architecture slice, code files, recent decisions, and
experiment outcomes. See docs/architecture-vision.md section 8.
"""
from __future__ import annotations

import logging
from typing import Any

from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.memory.store import MemoryStore
from aeco.memory.vector import VectorMemory

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Assembles focused context for an agent run from all memory layers."""

    def __init__(
        self,
        vector_memory: VectorMemory | None = None,
        memory_store: MemoryStore | None = None,
        decision_ledger: DecisionLedgerStore | None = None,
    ) -> None:
        self.vector = vector_memory
        self.memory = memory_store
        self.ledger = decision_ledger

    async def build_for_initiative(
        self,
        initiative_title: str,
        initiative_goal: str,
        agent_role: str,
        initiative_id: str | None = None,
        workspace_path: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build context for an agent working on an initiative.

        Pulls from:
        - Vector memory: semantically relevant past artifacts
        - Structured memory: product/architecture canonical summaries
        - Decision ledger: recent decisions and their assumptions
        """
        ctx: dict[str, Any] = {}

        # 1. Relevant past work from vector memory
        if self.vector:
            query = f"{initiative_title} {initiative_goal}".strip()
            if query:
                try:
                    past = self.vector.search(query, n_results=5)
                    ctx["relevant_past_work"] = past
                except Exception as e:
                    logger.warning(f"Vector search failed: {e}")

        # 2. Canonical summaries from structured memory
        if self.memory:
            for category in ("product_summary", "architecture_summary", "incident_summary"):
                try:
                    entries = await self.memory.list_by_category(category)
                    if entries:
                        ctx[category] = entries[:3]
                except Exception as e:
                    logger.warning(f"Memory fetch for {category} failed: {e}")

        # 3. Recent decisions from the ledger
        if self.ledger:
            try:
                if initiative_id:
                    import uuid
                    decisions = await self.ledger.get_by_initiative(uuid.UUID(initiative_id))
                else:
                    decisions = await self.ledger.get_recent(limit=10)
                if decisions:
                    ctx["recent_decisions"] = decisions[:5]
            except Exception as e:
                logger.warning(f"Decision ledger fetch failed: {e}")

        # 4. Role-specific context hints
        ctx["agent_role"] = agent_role
        ctx["workspace_path"] = workspace_path

        # 5. Merge any extra context provided by the caller
        if extra:
            ctx.update(extra)

        return ctx

    async def build_for_task(
        self,
        task_title: str,
        task_description: str,
        agent_role: str,
        initiative_id: str | None = None,
        workspace_path: str = "",
        project_context: dict | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build context for an agent working on a specific task."""
        ctx = await self.build_for_initiative(
            initiative_title=task_title,
            initiative_goal=task_description,
            agent_role=agent_role,
            initiative_id=initiative_id,
            workspace_path=workspace_path,
            extra=extra,
        )
        if project_context:
            ctx["project_context"] = project_context
        return ctx
