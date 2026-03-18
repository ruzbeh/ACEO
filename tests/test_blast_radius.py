"""Tests for blast-radius assessment and approval policies."""
from __future__ import annotations

from aeco.budget.blast_radius import BlastRadiusLevel, assess_blast_radius


class TestBlastRadiusAssessment:
    def test_empty_inputs_returns_low(self):
        result = assess_blast_radius()
        assert result.level == BlastRadiusLevel.LOW
        assert result.score == 0
        assert not result.requires_security_review
        assert not result.requires_founder_approval

    def test_db_migration_raises_score(self):
        result = assess_blast_radius(design_document="We need an ALTER TABLE migration to add columns")
        assert result.score >= 30
        assert any(f["factor"] == "production_db_migration" for f in result.factors)

    def test_auth_changes_detected(self):
        result = assess_blast_radius(design_document="Rewrite the JWT authentication flow with OAuth2")
        assert any(f["factor"] == "auth_changes" for f in result.factors)

    def test_payment_changes_detected(self):
        result = assess_blast_radius(prd={"description": "Add Stripe billing integration with subscriptions"})
        assert any(f["factor"] == "payment_changes" for f in result.factors)

    def test_critical_when_many_factors(self):
        result = assess_blast_radius(
            design_document="ALTER TABLE migration for auth system with payment billing changes and breaking API v2"
        )
        assert result.level == BlastRadiusLevel.CRITICAL
        assert result.requires_security_review
        assert result.requires_founder_approval

    def test_medium_for_multi_factor_change(self):
        result = assess_blast_radius(
            design_document="Frontend UI change with multi-service coordination and breaking change deprecation"
        )
        assert result.level in (BlastRadiusLevel.MEDIUM, BlastRadiusLevel.HIGH)

    def test_large_task_graph_increases_score(self):
        tasks = [{"title": f"Task {i}"} for i in range(10)]
        result_small = assess_blast_radius(task_graph=[{"title": "Single task"}])
        result_large = assess_blast_radius(task_graph=tasks)
        assert result_large.score > result_small.score

    def test_security_review_escalates_level(self):
        result = assess_blast_radius(
            design_document="Simple config change",
            security_review={"risk_level": "critical", "cleared": False},
        )
        assert result.level in (BlastRadiusLevel.HIGH, BlastRadiusLevel.CRITICAL)
        assert result.requires_security_review

    def test_low_risk_no_escalation(self):
        result = assess_blast_radius(
            design_document="Add a new logging utility function",
            security_review={"risk_level": "low", "cleared": True},
        )
        assert result.level == BlastRadiusLevel.LOW

    def test_reasoning_includes_factors(self):
        result = assess_blast_radius(design_document="JWT authentication rewrite")
        assert "auth_changes" in result.reasoning
