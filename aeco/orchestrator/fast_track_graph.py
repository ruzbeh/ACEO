"""LangGraph StateGraph assembly for the fast-track workflow.

Flow:
    START → intake → architect → [scaffold → build | build] → ship → verify → END
    architect --[escalate]→ END (returns escalation signal for initiative pipeline)
"""
from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.context.builder import ContextBuilder
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.fast_track_nodes import FastTrackNodes
from aeco.orchestrator.fast_track_state import FastTrackState

logger = logging.getLogger(__name__)


def _post_architect(state: FastTrackState) -> str:
    """After architect: escalate, scaffold (new project), or build (existing)."""
    if state.get("escalate_to_initiative"):
        return END
    if state.get("current_phase") == "done":
        return END
    if state.get("is_new_project"):
        return "scaffold"
    return "build"


def _post_ship(state: FastTrackState) -> str:
    """After ship: verify if preview URL exists, otherwise done."""
    if state.get("preview_url"):
        return "verify"
    return END


def build_fast_track_graph(
    registry: AgentRegistry,
    audit_logger: AuditLogger,
    context_builder: ContextBuilder,
    decision_ledger: DecisionLedgerStore,
    budget_engine=None,
) -> StateGraph:
    """Build and compile the fast-track workflow graph."""

    nodes = FastTrackNodes(
        registry=registry,
        audit_logger=audit_logger,
        context_builder=context_builder,
        decision_ledger=decision_ledger,
        budget_engine=budget_engine,
    )

    graph = StateGraph(FastTrackState)

    # Nodes
    graph.add_node("intake", nodes.intake)
    graph.add_node("architect", nodes.architect)
    graph.add_node("scaffold", nodes.scaffold)
    graph.add_node("build", nodes.build)
    graph.add_node("ship", nodes.ship)
    graph.add_node("verify", nodes.verify)

    # Edges
    graph.set_entry_point("intake")
    graph.add_edge("intake", "architect")

    # Architect can escalate (END), scaffold (new project), or build (existing)
    graph.add_conditional_edges(
        "architect",
        _post_architect,
        {
            "scaffold": "scaffold",
            "build": "build",
            END: END,
        },
    )

    graph.add_edge("scaffold", "build")
    graph.add_edge("build", "ship")

    # Ship can verify (if preview URL) or end
    graph.add_conditional_edges(
        "ship",
        _post_ship,
        {
            "verify": "verify",
            END: END,
        },
    )

    graph.add_edge("verify", END)

    return graph.compile()
