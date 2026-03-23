"""Applies approved prompt patches to agent prompt files at runtime."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# In-memory store of active patches (loaded from DB on startup)
_active_patches: dict[str, list[dict[str, Any]]] = {}


def load_active_patches(patches: list[dict[str, Any]]) -> None:
    """Load approved/applied patches into memory, grouped by agent_id."""
    global _active_patches
    _active_patches.clear()
    for patch in patches:
        agent_id = patch["agent_id"]
        if agent_id not in _active_patches:
            _active_patches[agent_id] = []
        _active_patches[agent_id].append(patch)
    logger.info(f"Loaded {len(patches)} active patches for {len(_active_patches)} agents")


def get_patches_for_agent(agent_id: str) -> list[dict[str, Any]]:
    """Get all active patches for an agent."""
    return _active_patches.get(agent_id, [])


def inject_patches(agent_id: str, base_prompt: str) -> str:
    """Inject active patches into an agent's system prompt.

    Appends patch content as an '## Applied Improvements' section.
    This is non-destructive — the original prompt file is not modified.
    """
    patches = get_patches_for_agent(agent_id)
    if not patches:
        return base_prompt

    patch_lines = ["\n\n## Applied Improvements\n"]
    patch_lines.append("The following rules were added based on past performance data:\n")
    for p in patches:
        patch_lines.append(f"- {p['content']}")
        if p.get("evidence"):
            patch_lines.append(f"  (Evidence: {p['evidence']})")

    return base_prompt + "\n".join(patch_lines)
