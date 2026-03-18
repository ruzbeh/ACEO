"""Tests for the Security Reviewer agent integration in the initiative workflow."""
from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aeco.agents.registry import AgentRegistry
from aeco.orchestrator.initiative_graph import _post_security_review


# --- Routing tests ---

class TestSecurityReviewRouting:
    def test_cleared_goes_to_task_planning(self):
        state = {"current_phase": "task_planning", "security_review": {"cleared": True}}
        assert _post_security_review(state) == "task_planning"

    def test_critical_not_cleared_goes_to_close(self):
        state = {"current_phase": "closed", "security_review": {"cleared": False, "risk_level": "critical"}}
        assert _post_security_review(state) == "close"

    def test_no_phase_defaults_to_task_planning(self):
        state = {}
        assert _post_security_review(state) == "task_planning"


# --- Agent registration test ---

class TestSecurityReviewerRegistration:
    def test_security_reviewer_in_yaml(self):
        from pathlib import Path
        reg = AgentRegistry()
        reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))
        assert reg.has("security_reviewer")
        agent = reg.get("security_reviewer")
        assert agent.role == "security"
        assert "workspace:read" in agent.permissions

    def test_total_agent_count_is_15(self):
        from pathlib import Path
        reg = AgentRegistry()
        reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))
        assert len(reg.list_agents()) == 15


# --- Initiative graph compilation test ---

class TestInitiativeGraphWithSecurityReview:
    def test_graph_compiles_with_security_review_node(self):
        """Verify the initiative graph compiles with the new security_review node."""
        from aeco.agents.registry import AgentRegistry
        from aeco.audit.logger import AuditLogger
        from aeco.context.builder import ContextBuilder
        from aeco.memory.decision_ledger import DecisionLedgerStore
        from aeco.orchestrator.initiative_graph import build_initiative_graph
        from pathlib import Path

        reg = AgentRegistry()
        reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))

        mock_audit = MagicMock(spec=AuditLogger)
        mock_ctx = MagicMock(spec=ContextBuilder)
        mock_ledger = MagicMock(spec=DecisionLedgerStore)

        graph = build_initiative_graph(reg, mock_audit, mock_ctx, mock_ledger)
        # Graph compiles without error
        assert graph is not None
