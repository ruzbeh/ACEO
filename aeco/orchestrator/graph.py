"""LangGraph StateGraph assembly for the AECO workflow."""

from langgraph.graph import END, StateGraph

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.orchestrator.edges import route_decision
from aeco.orchestrator.nodes import WorkflowNodes
from aeco.orchestrator.state import AECOState


def build_graph(registry: AgentRegistry, audit_logger: AuditLogger) -> StateGraph:
    """Build and compile the AECO workflow graph.

    Flow:
        START → intake → route
        route --[needs_design]→ architect → route
        route --[needs_implementation]→ engineer → route
        route --[needs_qa]→ qa → route
        route --[all_done | max_iterations]→ publish → END
    """
    nodes = WorkflowNodes(registry, audit_logger)

    graph = StateGraph(AECOState)

    # Add nodes
    graph.add_node("intake", nodes.intake)
    graph.add_node("route", nodes.route)
    graph.add_node("architect", nodes.architect)
    graph.add_node("engineer", nodes.engineer)
    graph.add_node("qa", nodes.qa)
    graph.add_node("publish", nodes.publish)

    # Entry point
    graph.set_entry_point("intake")

    # Edges
    graph.add_edge("intake", "route")

    # Route uses conditional edges
    graph.add_conditional_edges(
        "route",
        route_decision,
        {
            "architect": "architect",
            "engineer": "engineer",
            "qa": "qa",
            "publish": "publish",
        },
    )

    # After each agent, go back to route for next decision
    graph.add_edge("architect", "route")
    graph.add_edge("engineer", "route")
    graph.add_edge("qa", "route")

    # Publish ends the workflow
    graph.add_edge("publish", END)

    return graph.compile()
