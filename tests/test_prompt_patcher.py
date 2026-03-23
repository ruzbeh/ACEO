"""Tests for prompt patcher runtime injection."""
from __future__ import annotations

from aeco.agents.prompt_patcher import (
    get_patches_for_agent,
    inject_patches,
    load_active_patches,
)


class TestPromptPatcher:
    def test_no_patches_returns_base(self) -> None:
        load_active_patches([])
        result = inject_patches("some_agent", "Base prompt")
        assert result == "Base prompt"

    def test_patches_appended(self) -> None:
        load_active_patches([
            {
                "agent_id": "backend_engineer",
                "content": "Always check for idempotency",
                "evidence": "3 postmortems",
                "section": "Rules",
                "action": "append",
            }
        ])
        result = inject_patches("backend_engineer", "# Agent Prompt\n\nDo things.")
        assert "Applied Improvements" in result
        assert "Always check for idempotency" in result
        assert "3 postmortems" in result

    def test_patches_only_for_target_agent(self) -> None:
        load_active_patches([
            {
                "agent_id": "backend_engineer",
                "content": "Test rule",
                "evidence": "",
                "section": "Rules",
                "action": "append",
            }
        ])
        result = inject_patches("frontend_engineer", "Base prompt")
        assert result == "Base prompt"

    def test_multiple_patches_for_same_agent(self) -> None:
        load_active_patches([
            {
                "agent_id": "qa_engineer",
                "content": "Include integration tests",
                "evidence": "2 bugs",
                "section": "Rules",
                "action": "append",
            },
            {
                "agent_id": "qa_engineer",
                "content": "Test error paths",
                "evidence": "1 incident",
                "section": "Rules",
                "action": "append",
            },
        ])
        result = inject_patches("qa_engineer", "Base prompt")
        assert "Include integration tests" in result
        assert "Test error paths" in result

    def test_get_patches_for_agent(self) -> None:
        load_active_patches([
            {"agent_id": "a", "content": "rule1", "evidence": "", "section": "", "action": "append"},
            {"agent_id": "b", "content": "rule2", "evidence": "", "section": "", "action": "append"},
        ])
        assert len(get_patches_for_agent("a")) == 1
        assert len(get_patches_for_agent("b")) == 1
        assert len(get_patches_for_agent("c")) == 0
