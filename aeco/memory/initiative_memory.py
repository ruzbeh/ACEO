"""Institutional memory — the company learns from past initiatives."""
from __future__ import annotations
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("memory/initiatives")

class InitiativeMemory:
    """Persist and retrieve lessons from completed initiatives."""

    def __init__(self, base_dir: Path | str = MEMORY_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def record_lesson(
        self,
        initiative_id: str,
        title: str,
        verdict: str,
        workspace_path: str,
        lessons: list[str],
        what_worked: list[str],
        what_failed: list[str],
        tags: list[str] | None = None,
    ) -> None:
        """Save lessons from a completed initiative."""
        entry = {
            "initiative_id": initiative_id,
            "title": title,
            "verdict": verdict,
            "workspace_path": workspace_path,
            "lessons": lessons,
            "what_worked": what_worked,
            "what_failed": what_failed,
            "tags": tags or [],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        path = self.base_dir / f"{initiative_id[:8]}.json"
        path.write_text(json.dumps(entry, indent=2))
        logger.info(f"Recorded {len(lessons)} lessons from initiative {initiative_id[:8]}")

    async def get_relevant_lessons(
        self,
        title: str,
        workspace_path: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Retrieve lessons from past initiatives relevant to a new one.

        Simple relevance: same workspace_path first, then keyword overlap in title.
        """
        all_lessons = []
        for f in self.base_dir.glob("*.json"):
            try:
                entry = json.loads(f.read_text())
                # Score: same workspace = 10 points, each shared word in title = 1 point
                score = 0
                if entry.get("workspace_path") == workspace_path:
                    score += 10
                title_words = set(title.lower().split())
                entry_words = set(entry.get("title", "").lower().split())
                score += len(title_words & entry_words)
                if score > 0:
                    all_lessons.append((score, entry))
            except Exception:
                continue

        all_lessons.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in all_lessons[:limit]]

    async def get_all_lessons(self) -> list[dict[str, Any]]:
        """Return all recorded lessons."""
        lessons = []
        for f in sorted(self.base_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                lessons.append(json.loads(f.read_text()))
            except Exception:
                continue
        return lessons
