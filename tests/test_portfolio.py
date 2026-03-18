"""Tests for the portfolio-level workflow: graph compilation, routing, agent registration, and e2e mock."""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.context.builder import ContextBuilder
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.portfolio_graph import _post_rebalance, build_portfolio_graph
from aeco.orchestrator.portfolio_state import PortfolioState


# --- Routing tests ---


class TestPostRebalanceRouting:
    def test_continue_goes_to_opportunity_scan(self):
        state = {"current_phase": "opportunity_scan"}
        assert _post_rebalance(state) == "opportunity_scan"

    def test_closed_goes_to_close(self):
        state = {"current_phase": "closed"}
        assert _post_rebalance(state) == "close"

    def test_default_goes_to_opportunity_scan(self):
        state = {}
        assert _post_rebalance(state) == "opportunity_scan"


# --- Agent registration tests ---


class TestPortfolioAgentRegistration:
    def test_product_strategist_registered(self):
        reg = AgentRegistry()
        reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))
        assert reg.has("product_strategist")
        agent = reg.get("product_strategist")
        assert agent.role == "strategist"
        assert "metrics:read" in agent.permissions

    def test_ceo_director_registered(self):
        reg = AgentRegistry()
        reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))
        assert reg.has("ceo_director")
        agent = reg.get("ceo_director")
        assert agent.role == "executive"
        assert "budget:read" in agent.permissions

    def test_total_agent_count_is_17(self):
        reg = AgentRegistry()
        reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))
        assert len(reg.list_agents()) == 17


# --- Graph compilation test ---


class TestPortfolioGraphCompilation:
    def test_graph_compiles(self):
        reg = AgentRegistry()
        reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))

        graph = build_portfolio_graph(
            registry=reg,
            audit_logger=MagicMock(spec=AuditLogger),
            context_builder=MagicMock(spec=ContextBuilder),
            decision_ledger=MagicMock(spec=DecisionLedgerStore),
        )
        assert graph is not None


# --- Mock e2e test ---


MOCK_OPPORTUNITIES = [
    {
        "title": "Fix checkout funnel drop-off",
        "goal": "Reduce step-3 abandonment by 20%",
        "hypothesis": "Simplifying the form will reduce drop-off",
        "estimated_impact": 8,
        "estimated_cost": 5,
        "confidence": 0.85,
        "category": "efficiency",
        "evidence": ["40% drop at step 3", "3 support tickets/day about checkout"],
    },
]

MOCK_CEO_DECISION = {
    "fund": [
        {
            "title": "Fix checkout funnel drop-off",
            "goal": "Reduce step-3 abandonment by 20%",
            "hypothesis": "Simplifying the form will reduce drop-off",
            "allocated_budget": 200.0,
            "priority": "high",
            "reasoning": "High confidence, clear data signal",
        },
    ],
    "kill": [],
    "scale": [],
    "reasoning": "One high-confidence opportunity with clear ROI",
    "decision": "Fund checkout fix",
    "assumptions": ["Step-3 drop is form complexity, not pricing"],
    "risks": ["May need backend changes too"],
    "confidence": 0.8,
}


@pytest.mark.asyncio
async def test_portfolio_e2e_mock():
    """Run a full portfolio cycle with mocked agents (no LLM calls)."""

    reg = AgentRegistry()
    reg.load_from_yaml(Path("aeco/agents/definitions/v1_agents.yaml"))

    mock_audit = MagicMock(spec=AuditLogger)
    mock_audit.log = AsyncMock()
    mock_ctx = MagicMock(spec=ContextBuilder)
    mock_ctx.build_for_initiative = AsyncMock(return_value={})
    mock_ledger = MagicMock(spec=DecisionLedgerStore)
    mock_ledger.record = AsyncMock()

    # Mock initiative graph that returns immediately with a verdict
    mock_initiative_graph = MagicMock()

    async def mock_initiative_invoke(state):
        return {
            **state,
            "current_phase": "closed",
            "verdict": "scale",
            "budget_spent": 50.0,
            "execution_results": [{"title": "Task 1", "status": "completed"}],
        }

    mock_initiative_graph.ainvoke = mock_initiative_invoke

    def mock_create_executor(agent_def, audit_logger=None):
        mock = MagicMock()

        async def execute(context):
            if agent_def.agent_id == "product_strategist":
                return {
                    "opportunities": MOCK_OPPORTUNITIES,
                    "decision": "Found 1 opportunity",
                    "assumptions": [],
                    "risks": [],
                    "confidence": 0.85,
                }
            if agent_def.agent_id == "ceo_director":
                return MOCK_CEO_DECISION
            return {"decision": "fallback", "assumptions": [], "risks": [], "confidence": 0.5}

        mock.execute = execute
        return mock

    with patch("aeco.orchestrator.portfolio_nodes.create_executor", side_effect=mock_create_executor):
        graph = build_portfolio_graph(
            registry=reg,
            audit_logger=mock_audit,
            context_builder=mock_ctx,
            decision_ledger=mock_ledger,
            initiative_graph=mock_initiative_graph,
        )

        initial_state: PortfolioState = {
            "portfolio_id": str(uuid.uuid4()),
            "company_goals": ["Increase conversion rate", "Reduce churn"],
            "opportunities": [],
            "active_initiatives": [],
            "portfolio_decisions": [],
            "funded_initiatives": [],
            "killed_initiatives": [],
            "execution_results": [],
            "total_budget": 1000.0,
            "budget_spent": 0.0,
            "budget_remaining": 1000.0,
            "current_phase": "opportunity_scan",
            "cycle_count": 0,
            "max_cycles": 1,  # Single cycle for test speed
            "workspace_path": "",
            "messages": [],
            "decisions": [],
            "errors": [],
        }

        result = await graph.ainvoke(initial_state)

        # Verify portfolio completed
        assert result["current_phase"] == "closed"
        assert result["cycle_count"] >= 1

        # Verify opportunities were discovered
        assert len(result["opportunities"]) >= 1

        # Verify CEO made decisions
        assert len(result["portfolio_decisions"]) >= 1

        # Verify execution happened
        assert len(result["execution_results"]) >= 1

        # Verify messages accumulated
        assert len(result["messages"]) > 0
