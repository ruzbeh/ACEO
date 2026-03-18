"""AECO event bus for real-time notifications."""
from aeco.events.bus import EventBus

# Module-level singleton — import this everywhere
event_bus = EventBus()

# Event type constants
INITIATIVE_PHASE_CHANGED = "initiative.phase_changed"
INITIATIVE_DECISION_RECORDED = "initiative.decision_recorded"
INITIATIVE_TASK_STARTED = "initiative.task_started"
INITIATIVE_TASK_COMPLETED = "initiative.task_completed"
INITIATIVE_SECURITY_REVIEWED = "initiative.security_reviewed"
INITIATIVE_CLOSED = "initiative.closed"

AGENT_STARTED = "agent.started"
AGENT_COMPLETED = "agent.completed"

BUDGET_SPEND_RECORDED = "budget.spend_recorded"
BUDGET_ALERT_CREATED = "budget.alert_created"
BUDGET_BLAST_RADIUS = "budget.blast_radius_assessed"

PORTFOLIO_CYCLE_STARTED = "portfolio.cycle_started"
PORTFOLIO_OPPORTUNITIES_DISCOVERED = "portfolio.opportunities_discovered"
PORTFOLIO_DECISIONS_MADE = "portfolio.decisions_made"
PORTFOLIO_EXECUTION_STARTED = "portfolio.execution_started"
PORTFOLIO_EXECUTION_COMPLETED = "portfolio.execution_completed"
PORTFOLIO_EVALUATED = "portfolio.evaluated"
PORTFOLIO_REBALANCED = "portfolio.rebalanced"
PORTFOLIO_CLOSED = "portfolio.closed"
