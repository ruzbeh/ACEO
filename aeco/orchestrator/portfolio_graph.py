"""LangGraph StateGraph assembly for the portfolio-level workflow.
Flow:
    START → opportunity_scan → portfolio_review → execute_portfolio → portfolio_evaluate → rebalance
    rebalance --[continue & budget & under max_cycles]→ opportunity_scan (loop)
    rebalance --[done | no budget | max_cycles]→ close → END
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, StateGraph

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.budget.engine import BudgetEngine
from aeco.context.builder import ContextBuilder
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.portfolio_nodes import PortfolioNodes
from aeco.orchestrator.portfolio_state import PortfolioState

logger = logging.getLogger(__name__)


def _post_rebalance(state: PortfolioState) -> str:
    """After rebalance, continue scanning or close."""
    if state.get("current_phase") == "closed":
        return "close"
    return "opportunity_scan"


def build_portfolio_graph(
    registry: AgentRegistry,
    audit_logger: AuditLogger,
    context_builder: ContextBuilder,
    decision_ledger: DecisionLedgerStore,
    budget_engine: BudgetEngine | None = None,
    initiative_graph: Any = None,
) -> StateGraph:
    """Build and compile the portfolio-level workflow graph."""

    nodes = PortfolioNodes(
        registry=registry,
        audit_logger=audit_logger,
        context_builder=context_builder,
        decision_ledger=decision_ledger,
        budget_engine=budget_engine,
        initiative_graph=initiative_graph,
    )

    graph = StateGraph(PortfolioState)

    # Nodes
    graph.add_node("opportunity_scan", nodes.opportunity_scan)
    graph.add_node("portfolio_review", nodes.portfolio_review)
    graph.add_node("execute_portfolio", nodes.execute_portfolio)
    graph.add_node("portfolio_evaluate", nodes.portfolio_evaluate)
    graph.add_node("rebalance", nodes.rebalance)
    graph.add_node("close", nodes.close)

    # Linear pipeline
    graph.set_entry_point("opportunity_scan")
    graph.add_edge("opportunity_scan", "portfolio_review")
    graph.add_edge("portfolio_review", "execute_portfolio")
    graph.add_edge("execute_portfolio", "portfolio_evaluate")
    graph.add_edge("portfolio_evaluate", "rebalance")

    # Rebalance decides: continue → opportunity_scan, done → close
    graph.add_conditional_edges(
        "rebalance",
        _post_rebalance,
        {
            "opportunity_scan": "opportunity_scan",
            "close": "close",
        },
    )

    graph.add_edge("close", END)

    return graph.compile()
