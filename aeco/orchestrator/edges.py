"""Conditional edge logic for the AECO workflow graph."""

import logging

from aeco.orchestrator.state import AECOState

logger = logging.getLogger(__name__)


def route_decision(state: AECOState) -> str:
    """Determine the next node based on the orchestrator's routing decision."""
    next_action = state.get("next_action", "needs_design")
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 5)

    # Safety valve: stop if too many iterations
    if iteration >= max_iter:
        logger.warning(f"Max iterations ({max_iter}) reached, forcing publish")
        return "publish"

    match next_action:
        case "needs_design":
            return "architect"
        case "needs_implementation":
            return "engineer"
        case "needs_qa":
            return "qa"
        case "all_done":
            return "publish"
        case _:
            logger.warning(f"Unknown next_action '{next_action}', defaulting to publish")
            return "publish"
