"""Tests for the Budget Engine: models, approval tiers, anomaly detection, optimization."""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from aeco.models.budget import (
    AlertSeverity,
    ApprovalStatus,
    BudgetAlert,
    BudgetPeriod,
    SpendCategory,
    SpendRecord,
)
from aeco.budget.engine import (
    TIER_AGENT,
    TIER_AUTO,
    TIER_NOTIFY,
    estimate_cost,
    BudgetEngine,
    SpendRequest,
)


# ---------------------------------------------------------------------------
# Model instantiation tests (no DB required)
# ---------------------------------------------------------------------------

class TestBudgetModels:
    def test_budget_period_instantiate(self) -> None:
        now = datetime.now(timezone.utc)
        bp = BudgetPeriod(
            id=uuid.uuid4(),
            name="March 2026",
            scope="global",
            total_budget=500.0,
            spent=100.0,
            reserved=50.0,
            period_start=now,
            period_end=now + timedelta(days=30),
        )
        assert bp.__tablename__ == "budget_periods"
        assert bp.remaining == 350.0
        assert bp.utilization_percent == 20.0

    def test_budget_period_zero_budget(self) -> None:
        now = datetime.now(timezone.utc)
        bp = BudgetPeriod(
            id=uuid.uuid4(),
            name="Empty",
            total_budget=0.0,
            spent=0.0,
            reserved=0.0,
            period_start=now,
            period_end=now + timedelta(days=1),
        )
        assert bp.utilization_percent == 0.0
        assert bp.remaining == 0.0

    def test_spend_record_instantiate(self) -> None:
        sr = SpendRecord(
            id=uuid.uuid4(),
            budget_period_id=uuid.uuid4(),
            agent_id="backend_engineer",
            category=SpendCategory.LLM_TOKENS,
            amount=0.015,
            description="LLM call",
            approval_status=ApprovalStatus.AUTO_APPROVED,
            tokens_used=5000,
            llm_model="anthropic/claude-sonnet-4",
        )
        assert sr.__tablename__ == "spend_records"
        assert sr.category == SpendCategory.LLM_TOKENS
        assert sr.amount == 0.015

    def test_budget_alert_instantiate(self) -> None:
        alert = BudgetAlert(
            id=uuid.uuid4(),
            budget_period_id=uuid.uuid4(),
            alert_type="anomaly",
            severity=AlertSeverity.WARNING,
            message="Spend deviates 35% from average",
            agent_id="chief_architect",
        )
        assert alert.__tablename__ == "budget_alerts"
        assert alert.severity == AlertSeverity.WARNING
        assert not alert.acknowledged


class TestSpendCategoryEnum:
    def test_all_values(self) -> None:
        expected = {"llm_tokens", "compute", "api_calls", "storage", "tooling", "other"}
        actual = {m.value for m in SpendCategory}
        assert actual == expected


class TestApprovalStatusEnum:
    def test_all_values(self) -> None:
        expected = {"auto_approved", "approved", "denied", "pending", "escalated"}
        actual = {m.value for m in ApprovalStatus}
        assert actual == expected


# ---------------------------------------------------------------------------
# Cost estimation tests
# ---------------------------------------------------------------------------

class TestCostEstimation:
    def test_estimate_known_model(self) -> None:
        cost = estimate_cost(1_000_000, "anthropic/claude-sonnet-4")
        assert cost == 3.00

    def test_estimate_unknown_model_uses_default(self) -> None:
        cost = estimate_cost(1_000_000, "some/unknown-model")
        assert cost == 3.00  # DEFAULT_COST_PER_M_TOKENS

    def test_estimate_none_model(self) -> None:
        cost = estimate_cost(1_000_000)
        assert cost == 3.00

    def test_estimate_small_token_count(self) -> None:
        cost = estimate_cost(4000, "anthropic/claude-sonnet-4")
        assert abs(cost - 0.012) < 0.001

    def test_estimate_opus_expensive(self) -> None:
        cost = estimate_cost(1_000_000, "anthropic/claude-opus-4")
        assert cost == 15.00


# ---------------------------------------------------------------------------
# Approval tier logic tests
# ---------------------------------------------------------------------------

class TestApprovalTiers:
    def test_tier_thresholds(self) -> None:
        assert TIER_AUTO == 20.0
        assert TIER_AGENT == 200.0
        assert TIER_NOTIFY == 1000.0

    def test_spend_request_construction(self) -> None:
        req = SpendRequest(
            agent_id="qa_engineer",
            amount=5.50,
            category=SpendCategory.COMPUTE,
            description="Test execution",
        )
        assert req.agent_id == "qa_engineer"
        assert req.amount == 5.50
        assert req.category == SpendCategory.COMPUTE

    def test_spend_request_with_all_fields(self) -> None:
        wf_id = uuid.uuid4()
        task_id = uuid.uuid4()
        req = SpendRequest(
            agent_id="backend_engineer",
            amount=25.0,
            category=SpendCategory.LLM_TOKENS,
            description="Large context call",
            workflow_run_id=wf_id,
            task_id=task_id,
            tokens_used=100000,
            llm_model="anthropic/claude-opus-4",
        )
        assert req.workflow_run_id == wf_id
        assert req.tokens_used == 100000


# ---------------------------------------------------------------------------
# SpendDecision serialization
# ---------------------------------------------------------------------------

class TestSpendDecision:
    def test_to_dict(self) -> None:
        from aeco.budget.engine import SpendDecision

        decision = SpendDecision(
            status=ApprovalStatus.AUTO_APPROVED,
            reasoning="Under threshold",
            amount=5.0,
            remaining_budget=495.0,
            utilization_percent=1.0,
            warnings=[{"type": "info", "message": "all good", "severity": "info"}],
            optimization_hints=["Consider using haiku for simple tasks"],
        )
        d = decision.to_dict()
        assert d["status"] == "auto_approved"
        assert d["amount"] == 5.0
        assert d["remaining_budget"] == 495.0
        assert d["utilization_percent"] == 1.0
        assert len(d["warnings"]) == 1
        assert len(d["optimization_hints"]) == 1
