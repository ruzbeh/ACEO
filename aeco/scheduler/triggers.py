"""Metric-based triggers that auto-start portfolio cycles when thresholds are breached."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class MetricTrigger:
    """A trigger that fires when a metric crosses a threshold."""

    def __init__(
        self,
        trigger_id: str,
        name: str,
        metric_source: str,
        metric_name: str,
        comparison: str,
        threshold: float,
        cooldown_minutes: int = 60,
        action_type: str = "portfolio_run",
        action_args: dict[str, Any] | None = None,
    ):
        self.trigger_id = trigger_id
        self.name = name
        self.metric_source = metric_source  # "stripe", "facebook", "telemetry", "agent_metrics"
        self.metric_name = metric_name  # "churn_rate", "mrr", "error_rate", etc.
        self.comparison = comparison  # "gt", "lt", "gte", "lte", "change_gt", "change_lt"
        self.threshold = threshold
        self.cooldown_minutes = cooldown_minutes
        self.action_type = action_type
        self.action_args = action_args or {}
        self.is_active = True
        self.last_triggered_at: datetime | None = None
        self.last_value: float | None = None
        self.trigger_count: int = 0

    def evaluate(self, current_value: float) -> bool:
        """Check if the trigger should fire."""
        if not self.is_active:
            return False

        # Check cooldown
        if self.last_triggered_at:
            elapsed = (datetime.now(timezone.utc) - self.last_triggered_at).total_seconds()
            if elapsed < self.cooldown_minutes * 60:
                return False

        self.last_value = current_value
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
        }
        comparator = ops.get(self.comparison)
        if not comparator:
            logger.warning(f"Unknown comparison: {self.comparison}")
            return False

        return comparator(current_value, self.threshold)

    def fire(self) -> dict[str, Any]:
        """Mark as triggered and return action to execute."""
        self.last_triggered_at = datetime.now(timezone.utc)
        self.trigger_count += 1
        logger.info(
            f"Trigger '{self.name}' fired: {self.metric_name}={self.last_value} "
            f"{self.comparison} {self.threshold}"
        )
        return {
            "trigger_id": self.trigger_id,
            "trigger_name": self.name,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "metric_value": self.last_value,
        }

    def to_dict(self) -> dict:
        return {
            "trigger_id": self.trigger_id,
            "name": self.name,
            "metric_source": self.metric_source,
            "metric_name": self.metric_name,
            "comparison": self.comparison,
            "threshold": self.threshold,
            "cooldown_minutes": self.cooldown_minutes,
            "action_type": self.action_type,
            "action_args": self.action_args,
            "is_active": self.is_active,
            "last_triggered_at": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "last_value": self.last_value,
            "trigger_count": self.trigger_count,
        }


class TriggerEngine:
    """Manages metric triggers and evaluates them against live data."""

    def __init__(self):
        self._triggers: dict[str, MetricTrigger] = {}
        self._metric_fetchers: dict[str, Callable[..., Coroutine]] = {}

    def register_fetcher(self, source: str, fetcher: Callable[..., Coroutine]):
        """Register a function that fetches metric values for a source."""
        self._metric_fetchers[source] = fetcher

    def add_trigger(self, trigger: MetricTrigger) -> MetricTrigger:
        self._triggers[trigger.trigger_id] = trigger
        logger.info(f"Added trigger '{trigger.name}' ({trigger.trigger_id})")
        return trigger

    def remove_trigger(self, trigger_id: str) -> bool:
        if trigger_id in self._triggers:
            del self._triggers[trigger_id]
            return True
        return False

    def list_triggers(self) -> list[dict]:
        return [t.to_dict() for t in self._triggers.values()]

    def get_trigger(self, trigger_id: str) -> MetricTrigger | None:
        return self._triggers.get(trigger_id)

    async def check_all(self) -> list[dict]:
        """Evaluate all active triggers. Returns list of fired trigger actions."""
        fired: list[dict] = []

        for trigger in list(self._triggers.values()):
            if not trigger.is_active:
                continue

            fetcher = self._metric_fetchers.get(trigger.metric_source)
            if not fetcher:
                logger.warning(f"No fetcher for source '{trigger.metric_source}'")
                continue

            try:
                value = await fetcher(trigger.metric_name)
                if value is not None and trigger.evaluate(value):
                    action = trigger.fire()
                    fired.append(action)
            except Exception as e:
                logger.error(f"Error checking trigger '{trigger.name}': {e}")

        return fired

    async def setup_default_triggers(self):
        """Register built-in metric triggers for common scenarios."""
        defaults = [
            MetricTrigger(
                trigger_id=str(uuid.uuid4()),
                name="Churn spike alert",
                metric_source="stripe",
                metric_name="churn_rate",
                comparison="gt",
                threshold=5.0,
                cooldown_minutes=1440,  # Once per day
                action_args={"goals": ["Investigate and reduce customer churn spike"]},
            ),
            MetricTrigger(
                trigger_id=str(uuid.uuid4()),
                name="MRR drop alert",
                metric_source="stripe",
                metric_name="mrr_change_pct",
                comparison="lt",
                threshold=-10.0,
                cooldown_minutes=1440,
                action_args={"goals": ["Investigate MRR decline and propose recovery initiatives"]},
            ),
            MetricTrigger(
                trigger_id=str(uuid.uuid4()),
                name="Ad spend anomaly",
                metric_source="facebook",
                metric_name="spend_efficiency",
                comparison="lt",
                threshold=0.7,
                cooldown_minutes=720,  # 12 hours
                action_args={"goals": ["Optimize Facebook ad campaigns — spend efficiency below 70%"]},
            ),
            MetricTrigger(
                trigger_id=str(uuid.uuid4()),
                name="Agent error rate spike",
                metric_source="agent_metrics",
                metric_name="max_error_rate",
                comparison="gt",
                threshold=15.0,
                cooldown_minutes=360,  # 6 hours
                action_type="agent_review",
                action_args={"goals": ["Review and fix agents with error rates above 15%"]},
            ),
        ]

        for trigger in defaults:
            self.add_trigger(trigger)

        return defaults
