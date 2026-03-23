"""Track LLM costs per initiative."""
from __future__ import annotations
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

# Approximate costs per 1M tokens (input/output)
MODEL_COSTS = {
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5": {"input": 0.80, "output": 4.0},
    "claude-opus-4": {"input": 15.0, "output": 75.0},
}

class InitiativeCostTracker:
    """Track token usage and estimated $ cost per initiative."""

    def __init__(self):
        self._costs: dict[str, dict[str, Any]] = defaultdict(lambda: {
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
            "agent_breakdown": defaultdict(lambda: {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}),
        })

    def record_usage(
        self,
        initiative_id: str,
        agent_id: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record token usage for an agent call within an initiative."""
        costs = MODEL_COSTS.get(model, MODEL_COSTS.get("claude-sonnet-4", {"input": 3.0, "output": 15.0}))
        cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000

        entry = self._costs[initiative_id]
        entry["total_input_tokens"] += input_tokens
        entry["total_output_tokens"] += output_tokens
        entry["total_cost_usd"] += cost

        agent = entry["agent_breakdown"][agent_id]
        agent["input_tokens"] += input_tokens
        agent["output_tokens"] += output_tokens
        agent["cost_usd"] += cost
        agent["calls"] += 1

    def get_initiative_cost(self, initiative_id: str) -> dict[str, Any]:
        """Get cost summary for an initiative."""
        entry = self._costs.get(initiative_id)
        if not entry:
            return {"total_input_tokens": 0, "total_output_tokens": 0, "total_cost_usd": 0.0, "agent_breakdown": {}}
        return {
            "total_input_tokens": entry["total_input_tokens"],
            "total_output_tokens": entry["total_output_tokens"],
            "total_cost_usd": round(entry["total_cost_usd"], 4),
            "agent_breakdown": dict(entry["agent_breakdown"]),
        }

    def get_all_costs(self) -> dict[str, dict[str, Any]]:
        """Get costs for all initiatives."""
        return {k: self.get_initiative_cost(k) for k in self._costs}
