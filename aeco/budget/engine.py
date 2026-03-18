"""Budget Engine: approval tiers, spend tracking, anomaly detection, and optimization.

Approval tiers (from project design):
  - <$20:       auto-approve
  - $20-$200:   Budget Controller agent approval
  - $200-$1000: founder notification (approve + alert)
  - >$1000:     founder explicit approval required (escalate)
"""
from __future__ import annotations

import logging
import statistics
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from aeco.models.budget import (
    AlertSeverity,
    ApprovalStatus,
    BudgetAlert,
    BudgetPeriod,
    SpendCategory,
    SpendRecord,
)

logger = logging.getLogger(__name__)

# --- Approval tier thresholds ---
TIER_AUTO = 20.0
TIER_AGENT = 200.0
TIER_NOTIFY = 1000.0

# Anomaly detection: flag if spend deviates >20% from rolling average
ANOMALY_DEVIATION_PERCENT = 20.0

# Token-to-cost estimate (per 1M tokens, rough defaults)
TOKEN_COST_MAP: dict[str, float] = {
    "anthropic/claude-sonnet-4": 3.00,
    "anthropic/claude-opus-4": 15.00,
    "anthropic/claude-haiku-4": 0.25,
    "openai/gpt-4o": 2.50,
    "openai/gpt-4o-mini": 0.15,
}
DEFAULT_COST_PER_M_TOKENS = 3.00


def estimate_cost(tokens: int, model: str | None = None) -> float:
    """Estimate USD cost from token count and model."""
    per_m = TOKEN_COST_MAP.get(model or "", DEFAULT_COST_PER_M_TOKENS)
    return (tokens / 1_000_000) * per_m


class SpendRequest:
    """A request to spend against a budget."""

    def __init__(
        self,
        agent_id: str,
        amount: float,
        category: SpendCategory = SpendCategory.LLM_TOKENS,
        description: str = "",
        workflow_run_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        initiative_id: uuid.UUID | None = None,
        tokens_used: int | None = None,
        llm_model: str | None = None,
    ):
        self.agent_id = agent_id
        self.amount = amount
        self.category = category
        self.description = description
        self.workflow_run_id = workflow_run_id
        self.task_id = task_id
        self.initiative_id = initiative_id
        self.tokens_used = tokens_used
        self.llm_model = llm_model


class SpendDecision:
    """Result of a spend approval check."""

    def __init__(
        self,
        status: ApprovalStatus,
        reasoning: str,
        amount: float,
        remaining_budget: float,
        utilization_percent: float,
        warnings: list[dict] | None = None,
        optimization_hints: list[str] | None = None,
    ):
        self.status = status
        self.reasoning = reasoning
        self.amount = amount
        self.remaining_budget = remaining_budget
        self.utilization_percent = utilization_percent
        self.warnings = warnings or []
        self.optimization_hints = optimization_hints or []

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "reasoning": self.reasoning,
            "amount": self.amount,
            "remaining_budget": self.remaining_budget,
            "utilization_percent": round(self.utilization_percent, 1),
            "warnings": self.warnings,
            "optimization_hints": self.optimization_hints,
        }


class BudgetEngine:
    """Core budget engine with approval tiers, anomaly detection, and optimization."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Budget CRUD
    # ------------------------------------------------------------------

    async def create_budget(
        self,
        name: str,
        total_budget: float,
        period_start: datetime,
        period_end: datetime,
        scope: str = "global",
        scope_id: str | None = None,
    ) -> BudgetPeriod:
        async with self._session_factory() as session:
            budget = BudgetPeriod(
                name=name,
                total_budget=total_budget,
                period_start=period_start,
                period_end=period_end,
                scope=scope,
                scope_id=scope_id,
            )
            session.add(budget)
            await session.commit()
            await session.refresh(budget)
            return budget

    async def get_active_budget(
        self, scope: str = "global", scope_id: str | None = None
    ) -> BudgetPeriod | None:
        """Get the currently active budget for a scope."""
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            stmt = (
                select(BudgetPeriod)
                .where(
                    BudgetPeriod.is_active.is_(True),
                    BudgetPeriod.scope == scope,
                    BudgetPeriod.period_start <= now,
                    BudgetPeriod.period_end >= now,
                )
            )
            if scope_id:
                stmt = stmt.where(BudgetPeriod.scope_id == scope_id)
            else:
                stmt = stmt.where(BudgetPeriod.scope_id.is_(None))
            result = await session.execute(stmt.order_by(BudgetPeriod.created_at.desc()))
            return result.scalars().first()

    async def get_budget_summary(
        self, budget_id: uuid.UUID
    ) -> dict:
        """Get a full budget summary with spend breakdown."""
        async with self._session_factory() as session:
            budget = await session.get(BudgetPeriod, budget_id)
            if not budget:
                return {"error": "Budget not found"}

            # Spend by category
            stmt = (
                select(
                    SpendRecord.category,
                    func.sum(SpendRecord.amount).label("total"),
                    func.count(SpendRecord.id).label("count"),
                )
                .where(SpendRecord.budget_period_id == budget_id)
                .group_by(SpendRecord.category)
            )
            result = await session.execute(stmt)
            by_category = {
                row.category.value: {"total": round(row.total, 4), "count": row.count}
                for row in result
            }

            # Spend by agent
            stmt_agent = (
                select(
                    SpendRecord.agent_id,
                    func.sum(SpendRecord.amount).label("total"),
                    func.count(SpendRecord.id).label("count"),
                    func.sum(SpendRecord.tokens_used).label("tokens"),
                )
                .where(SpendRecord.budget_period_id == budget_id)
                .group_by(SpendRecord.agent_id)
            )
            result_agent = await session.execute(stmt_agent)
            by_agent = {
                row.agent_id: {
                    "total": round(row.total, 4),
                    "count": row.count,
                    "tokens": row.tokens or 0,
                }
                for row in result_agent
            }

            # Recent alerts
            stmt_alerts = (
                select(BudgetAlert)
                .where(BudgetAlert.budget_period_id == budget_id)
                .order_by(BudgetAlert.created_at.desc())
                .limit(10)
            )
            result_alerts = await session.execute(stmt_alerts)
            alerts = [
                {
                    "type": a.alert_type,
                    "severity": a.severity.value,
                    "message": a.message,
                    "agent_id": a.agent_id,
                    "acknowledged": a.acknowledged,
                    "created_at": a.created_at.isoformat(),
                }
                for a in result_alerts.scalars()
            ]

            return {
                "budget_id": str(budget.id),
                "name": budget.name,
                "scope": budget.scope,
                "total_budget": budget.total_budget,
                "spent": round(budget.spent, 4),
                "reserved": round(budget.reserved, 4),
                "remaining": round(budget.remaining, 4),
                "utilization_percent": round(budget.utilization_percent, 1),
                "period_start": budget.period_start.isoformat(),
                "period_end": budget.period_end.isoformat(),
                "by_category": by_category,
                "by_agent": by_agent,
                "recent_alerts": alerts,
            }

    # ------------------------------------------------------------------
    # Approval engine
    # ------------------------------------------------------------------

    async def request_spend(
        self,
        request: SpendRequest,
        budget_id: uuid.UUID | None = None,
        pre_approval_only: bool = False,
    ) -> SpendDecision:
        """Evaluate a spend request against budget and policy.

        When pre_approval_only=True, only check and return decision; do not add
        SpendRecord or update budget (used by workflow budget_check before agent runs).
        Actual spend is recorded later from audit log via record_spend().
        """
        async with self._session_factory() as session:
            # Find the budget
            if budget_id:
                budget = await session.get(BudgetPeriod, budget_id)
            else:
                now = datetime.now(timezone.utc)
                stmt = (
                    select(BudgetPeriod)
                    .where(
                        BudgetPeriod.is_active.is_(True),
                        BudgetPeriod.period_start <= now,
                        BudgetPeriod.period_end >= now,
                    )
                    .order_by(BudgetPeriod.created_at.desc())
                )
                result = await session.execute(stmt)
                budget = result.scalars().first()

            if not budget:
                logger.warning(
                    "No active budget configured; spending is untracked. "
                    "Create a budget period in the dashboard to monitor and control spend."
                )
                return SpendDecision(
                    status=ApprovalStatus.AUTO_APPROVED,
                    reasoning="No active budget configured; auto-approving",
                    amount=request.amount,
                    remaining_budget=0.0,
                    utilization_percent=0.0,
                    warnings=[{
                        "type": "policy_violation",
                        "message": "No active budget period — spending is untracked",
                        "severity": "warning",
                    }],
                )

            remaining = budget.remaining
            warnings: list[dict] = []
            optimization_hints: list[str] = []

            # Check if spend would exceed budget
            if request.amount > remaining:
                record = SpendRecord(
                    budget_period_id=budget.id,
                    workflow_run_id=request.workflow_run_id,
                    task_id=request.task_id,
                    initiative_id=request.initiative_id,
                    agent_id=request.agent_id,
                    category=request.category,
                    amount=request.amount,
                    description=request.description,
                    approval_status=ApprovalStatus.DENIED,
                    tokens_used=request.tokens_used,
                    llm_model=request.llm_model,
                )
                session.add(record)
                alert = BudgetAlert(
                    budget_period_id=budget.id,
                    alert_type="overspend",
                    severity=AlertSeverity.CRITICAL,
                    message=(
                        f"Denied ${request.amount:.2f} spend by {request.agent_id}: "
                        f"would exceed remaining ${remaining:.2f}"
                    ),
                    agent_id=request.agent_id,
                    workflow_run_id=request.workflow_run_id,
                )
                session.add(alert)
                await session.commit()

                return SpendDecision(
                    status=ApprovalStatus.DENIED,
                    reasoning=f"Insufficient budget: requested ${request.amount:.2f}, remaining ${remaining:.2f}",
                    amount=request.amount,
                    remaining_budget=remaining,
                    utilization_percent=budget.utilization_percent,
                    warnings=[{
                        "type": "overspend",
                        "message": "Request exceeds remaining budget",
                        "severity": "critical",
                    }],
                    optimization_hints=await self._generate_optimization_hints(
                        session, budget.id, request.agent_id
                    ),
                )

            # Determine approval tier
            if request.amount < TIER_AUTO:
                status = ApprovalStatus.AUTO_APPROVED
                reasoning = f"Auto-approved: ${request.amount:.2f} under ${TIER_AUTO} threshold"
            elif request.amount < TIER_AGENT:
                status = ApprovalStatus.APPROVED
                reasoning = (
                    f"Budget Controller approved: ${request.amount:.2f} "
                    f"within ${TIER_AUTO}-${TIER_AGENT} range"
                )
            elif request.amount < TIER_NOTIFY:
                status = ApprovalStatus.APPROVED
                reasoning = (
                    f"Approved with founder notification: ${request.amount:.2f} "
                    f"within ${TIER_AGENT}-${TIER_NOTIFY} range"
                )
                warnings.append({
                    "type": "policy_violation",
                    "message": f"Spend >${TIER_AGENT} requires founder notification",
                    "severity": "warning",
                })
            else:
                status = ApprovalStatus.ESCALATED
                reasoning = (
                    f"Escalated to founder: ${request.amount:.2f} exceeds ${TIER_NOTIFY} threshold"
                )
                warnings.append({
                    "type": "policy_violation",
                    "message": f"Spend >${TIER_NOTIFY} requires founder explicit approval",
                    "severity": "critical",
                })

            # Anomaly detection
            anomaly_warnings = await self._detect_anomalies(
                session, budget.id, request
            )
            warnings.extend(anomaly_warnings)

            # Optimization hints
            optimization_hints = await self._generate_optimization_hints(
                session, budget.id, request.agent_id
            )

            # High utilization warning
            projected_util = ((budget.spent + request.amount) / budget.total_budget) * 100
            if projected_util > 90:
                warnings.append({
                    "type": "trend",
                    "message": f"Budget utilization will reach {projected_util:.0f}% after this spend",
                    "severity": "critical" if projected_util > 95 else "warning",
                })

            # Record the spend (skip when pre_approval_only — actual spend recorded from audit)
            if not pre_approval_only:
                approved = status in (ApprovalStatus.AUTO_APPROVED, ApprovalStatus.APPROVED)
                record = SpendRecord(
                    budget_period_id=budget.id,
                    workflow_run_id=request.workflow_run_id,
                    task_id=request.task_id,
                    initiative_id=request.initiative_id,
                    agent_id=request.agent_id,
                    category=request.category,
                    amount=request.amount,
                    description=request.description,
                    approval_status=status,
                    approved_by="budget_engine" if approved else None,
                    tokens_used=request.tokens_used,
                    llm_model=request.llm_model,
                )
                session.add(record)

                if approved:
                    budget.spent += request.amount
                elif status == ApprovalStatus.ESCALATED:
                    budget.reserved += request.amount

            # Create alerts for warnings (only when recording)
            if not pre_approval_only:
                for w in warnings:
                    if w["severity"] in ("critical", "warning"):
                        alert = BudgetAlert(
                            budget_period_id=budget.id,
                            alert_type=w["type"],
                            severity=AlertSeverity(w["severity"]),
                            message=w["message"],
                            agent_id=request.agent_id,
                            workflow_run_id=request.workflow_run_id,
                        )
                        session.add(alert)

                await session.commit()

            return SpendDecision(
                status=status,
                reasoning=reasoning,
                amount=request.amount,
                remaining_budget=budget.remaining,
                utilization_percent=budget.utilization_percent,
                warnings=warnings,
                optimization_hints=optimization_hints,
            )

    # ------------------------------------------------------------------
    # Record spend (for post-hoc tracking, e.g., from audit logs)
    # ------------------------------------------------------------------

    async def record_spend(
        self,
        agent_id: str,
        tokens_used: int,
        llm_model: str | None = None,
        workflow_run_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        initiative_id: uuid.UUID | None = None,
        description: str = "",
    ) -> SpendDecision:
        """Estimate cost from tokens and record as a spend request."""
        cost = estimate_cost(tokens_used, llm_model)
        request = SpendRequest(
            agent_id=agent_id,
            amount=cost,
            category=SpendCategory.LLM_TOKENS,
            description=description or f"LLM call: {tokens_used} tokens on {llm_model}",
            workflow_run_id=workflow_run_id,
            task_id=task_id,
            initiative_id=initiative_id,
            tokens_used=tokens_used,
            llm_model=llm_model,
        )
        return await self.request_spend(request)

    # ------------------------------------------------------------------
    # Anomaly detection
    # ------------------------------------------------------------------

    async def _detect_anomalies(
        self,
        session: AsyncSession,
        budget_id: uuid.UUID,
        request: SpendRequest,
    ) -> list[dict]:
        """Detect if this spend is anomalous compared to historical patterns."""
        warnings: list[dict] = []

        # Get recent spend by this agent
        stmt = (
            select(SpendRecord.amount)
            .where(
                SpendRecord.budget_period_id == budget_id,
                SpendRecord.agent_id == request.agent_id,
                SpendRecord.approval_status.in_([
                    ApprovalStatus.AUTO_APPROVED,
                    ApprovalStatus.APPROVED,
                ]),
            )
            .order_by(SpendRecord.created_at.desc())
            .limit(20)
        )
        result = await session.execute(stmt)
        recent_amounts = [row[0] for row in result]

        if len(recent_amounts) >= 3:
            avg = statistics.mean(recent_amounts)
            if avg > 0:
                deviation = abs(request.amount - avg) / avg * 100
                if deviation > ANOMALY_DEVIATION_PERCENT:
                    severity = "critical" if deviation > 50 else "warning"
                    warnings.append({
                        "type": "anomaly",
                        "message": (
                            f"Spend ${request.amount:.4f} by {request.agent_id} deviates "
                            f"{deviation:.0f}% from rolling avg ${avg:.4f}"
                        ),
                        "severity": severity,
                    })

        return warnings

    # ------------------------------------------------------------------
    # Optimization engine
    # ------------------------------------------------------------------

    async def _generate_optimization_hints(
        self,
        session: AsyncSession,
        budget_id: uuid.UUID,
        agent_id: str,
    ) -> list[str]:
        """Generate cost optimization suggestions based on spend patterns."""
        hints: list[str] = []

        # Analyze model usage and suggest cheaper alternatives
        stmt = (
            select(
                SpendRecord.llm_model,
                func.sum(SpendRecord.amount).label("total"),
                func.sum(SpendRecord.tokens_used).label("tokens"),
                func.count(SpendRecord.id).label("count"),
            )
            .where(
                SpendRecord.budget_period_id == budget_id,
                SpendRecord.agent_id == agent_id,
                SpendRecord.llm_model.isnot(None),
            )
            .group_by(SpendRecord.llm_model)
        )
        result = await session.execute(stmt)
        model_usage = list(result)

        for row in model_usage:
            model = row.llm_model
            if model and "opus" in model.lower():
                hints.append(
                    f"Agent {agent_id} uses {model} (${row.total:.2f} over {row.count} calls). "
                    f"Consider claude-sonnet for routine tasks to save ~80%."
                )
            if row.tokens and row.count and (row.tokens / row.count) > 50000:
                hints.append(
                    f"Agent {agent_id} averages {row.tokens // row.count} tokens/call. "
                    f"Consider truncating context or summarizing prior messages."
                )

        # Check iteration efficiency
        stmt_tasks = (
            select(
                SpendRecord.task_id,
                func.count(SpendRecord.id).label("call_count"),
                func.sum(SpendRecord.amount).label("total"),
            )
            .where(
                SpendRecord.budget_period_id == budget_id,
                SpendRecord.agent_id == agent_id,
                SpendRecord.task_id.isnot(None),
            )
            .group_by(SpendRecord.task_id)
        )
        result_tasks = await session.execute(stmt_tasks)
        task_costs = list(result_tasks)

        if len(task_costs) >= 3:
            costs = [row.total for row in task_costs]
            avg_cost = statistics.mean(costs)
            if avg_cost > 5.0:
                hints.append(
                    f"Agent {agent_id} averages ${avg_cost:.2f}/task. "
                    f"Review if iteration count can be reduced."
                )

        return hints

    async def get_workflow_cost(
        self, workflow_run_id: uuid.UUID
    ) -> dict:
        """Get total cost breakdown for a workflow run."""
        async with self._session_factory() as session:
            stmt = (
                select(
                    SpendRecord.agent_id,
                    SpendRecord.category,
                    func.sum(SpendRecord.amount).label("total"),
                    func.sum(SpendRecord.tokens_used).label("tokens"),
                    func.count(SpendRecord.id).label("count"),
                )
                .where(SpendRecord.workflow_run_id == workflow_run_id)
                .group_by(SpendRecord.agent_id, SpendRecord.category)
            )
            result = await session.execute(stmt)
            breakdown: dict[str, dict] = {}
            total_cost = 0.0
            total_tokens = 0
            for row in result:
                agent = row.agent_id
                if agent not in breakdown:
                    breakdown[agent] = {"total": 0.0, "tokens": 0, "categories": {}}
                breakdown[agent]["total"] += row.total
                breakdown[agent]["tokens"] += row.tokens or 0
                breakdown[agent]["categories"][row.category.value] = round(row.total, 4)
                total_cost += row.total
                total_tokens += row.tokens or 0

            return {
                "workflow_run_id": str(workflow_run_id),
                "total_cost": round(total_cost, 4),
                "total_tokens": total_tokens,
                "by_agent": {
                    k: {
                        "total": round(v["total"], 4),
                        "tokens": v["tokens"],
                        "categories": v["categories"],
                    }
                    for k, v in breakdown.items()
                },
            }

    async def get_spend_by_initiative(
        self, initiative_id: uuid.UUID, budget_id: uuid.UUID | None = None
    ) -> dict:
        """Get spend breakdown for an initiative (optionally within a budget period)."""
        async with self._session_factory() as session:
            stmt = (
                select(
                    SpendRecord.agent_id,
                    func.sum(SpendRecord.amount).label("total"),
                    func.sum(SpendRecord.tokens_used).label("tokens"),
                    func.count(SpendRecord.id).label("count"),
                )
                .where(SpendRecord.initiative_id == initiative_id)
            )
            if budget_id:
                stmt = stmt.where(SpendRecord.budget_period_id == budget_id)
            stmt = stmt.group_by(SpendRecord.agent_id)
            result = await session.execute(stmt)
            by_agent: dict[str, dict] = {}
            total_cost = 0.0
            total_tokens = 0
            for row in result:
                by_agent[row.agent_id] = {
                    "total": round(row.total, 4),
                    "tokens": row.tokens or 0,
                    "count": row.count,
                }
                total_cost += row.total
                total_tokens += row.tokens or 0

            # List records for timeline
            stmt_records = (
                select(SpendRecord)
                .where(SpendRecord.initiative_id == initiative_id)
            )
            if budget_id:
                stmt_records = stmt_records.where(SpendRecord.budget_period_id == budget_id)
            stmt_records = stmt_records.order_by(SpendRecord.created_at.desc()).limit(50)
            result_records = await session.execute(stmt_records)
            records = [
                {
                    "id": str(r.id),
                    "agent_id": r.agent_id,
                    "amount": round(r.amount, 4),
                    "tokens_used": r.tokens_used,
                    "created_at": r.created_at.isoformat(),
                }
                for r in result_records.scalars().all()
            ]

            return {
                "initiative_id": str(initiative_id),
                "total_cost": round(total_cost, 4),
                "total_tokens": total_tokens,
                "by_agent": by_agent,
                "records": records,
            }

    async def get_spend_over_time(
        self,
        budget_id: uuid.UUID,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        group_by: str = "day",
    ) -> dict:
        """Get spend aggregated over time (daily or weekly buckets)."""
        from sqlalchemy import cast, Date
        async with self._session_factory() as session:
            stmt = select(SpendRecord).where(SpendRecord.budget_period_id == budget_id)
            if from_date:
                stmt = stmt.where(SpendRecord.created_at >= from_date)
            if to_date:
                stmt = stmt.where(SpendRecord.created_at <= to_date)
            result = await session.execute(stmt)
            rows = result.scalars().all()

            # Bucket by date (day or week start)
            buckets: dict[str, float] = {}
            for r in rows:
                dt = r.created_at
                if group_by == "week":
                    # ISO week Monday
                    start = dt - datetime.timedelta(days=dt.weekday())
                    key = start.strftime("%Y-%m-%d")
                else:
                    key = dt.strftime("%Y-%m-%d")
                buckets[key] = buckets.get(key, 0.0) + r.amount

            series = [{"date": k, "amount": round(v, 4)} for k, v in sorted(buckets.items())]
            return {
                "budget_id": str(budget_id),
                "group_by": group_by,
                "series": series,
                "total": round(sum(buckets.values()), 4),
            }

    async def get_spend_by_initiative_list(
        self, budget_id: uuid.UUID
    ) -> list[dict]:
        """Get total spend per initiative for the budget period (for dashboard)."""
        async with self._session_factory() as session:
            stmt = (
                select(
                    SpendRecord.initiative_id,
                    func.sum(SpendRecord.amount).label("total"),
                    func.sum(SpendRecord.tokens_used).label("tokens"),
                    func.count(SpendRecord.id).label("count"),
                )
                .where(
                    SpendRecord.budget_period_id == budget_id,
                    SpendRecord.initiative_id.isnot(None),
                )
                .group_by(SpendRecord.initiative_id)
            )
            result = await session.execute(stmt)
            return [
                {
                    "initiative_id": str(row.initiative_id),
                    "total": round(row.total, 4),
                    "tokens": row.tokens or 0,
                    "count": row.count,
                }
                for row in result
            ]

    async def get_optimization_report(
        self, budget_id: uuid.UUID
    ) -> dict:
        """Generate a comprehensive optimization report for a budget period."""
        async with self._session_factory() as session:
            budget = await session.get(BudgetPeriod, budget_id)
            if not budget:
                return {"error": "Budget not found"}

            # Gather hints for all agents
            stmt = (
                select(SpendRecord.agent_id)
                .where(SpendRecord.budget_period_id == budget_id)
                .distinct()
            )
            result = await session.execute(stmt)
            agent_ids = [row[0] for row in result]

            all_hints: dict[str, list[str]] = {}
            for agent_id in agent_ids:
                hints = await self._generate_optimization_hints(
                    session, budget_id, agent_id
                )
                if hints:
                    all_hints[agent_id] = hints

            # Cost trend (most expensive agents)
            stmt_top = (
                select(
                    SpendRecord.agent_id,
                    func.sum(SpendRecord.amount).label("total"),
                )
                .where(SpendRecord.budget_period_id == budget_id)
                .group_by(SpendRecord.agent_id)
                .order_by(func.sum(SpendRecord.amount).desc())
                .limit(5)
            )
            result_top = await session.execute(stmt_top)
            top_spenders = [
                {"agent_id": row.agent_id, "total": round(row.total, 4)}
                for row in result_top
            ]

            # Projected burn rate
            days_elapsed = (datetime.now(timezone.utc) - budget.period_start).days or 1
            daily_rate = budget.spent / days_elapsed
            days_remaining = (budget.period_end - datetime.now(timezone.utc)).days
            projected_total = budget.spent + (daily_rate * max(days_remaining, 0))

            return {
                "budget_id": str(budget.id),
                "budget_name": budget.name,
                "spent": round(budget.spent, 4),
                "remaining": round(budget.remaining, 4),
                "utilization_percent": round(budget.utilization_percent, 1),
                "daily_burn_rate": round(daily_rate, 4),
                "projected_total_spend": round(projected_total, 2),
                "projected_over_budget": projected_total > budget.total_budget,
                "top_spenders": top_spenders,
                "optimization_hints": all_hints,
                "recommendation": (
                    "REDUCE SPEND: projected to exceed budget"
                    if projected_total > budget.total_budget
                    else "ON TRACK: spend within projections"
                ),
            }
