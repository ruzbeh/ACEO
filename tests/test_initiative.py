"""Tests for initiative models, decision ledger, context builder, and initiative state."""

import uuid
from datetime import datetime, timedelta, timezone

from aeco.models.initiative import Initiative, InitiativeStatus, InitiativeVerdict
from aeco.models.decision_ledger import DecisionCategory, DecisionRecord
from aeco.models.agent_output import AgentOutput
from aeco.models.task import Task


# ---------------------------------------------------------------------------
# Initiative model tests
# ---------------------------------------------------------------------------

class TestInitiativeModel:
    def test_instantiate_with_defaults(self) -> None:
        init = Initiative(
            id=uuid.uuid4(),
            title="Add onboarding flow",
            goal="Increase signup conversion by 20%",
            status=InitiativeStatus.DRAFT.value,
            verdict=InitiativeVerdict.PENDING.value,
        )
        assert init.__tablename__ == "initiatives"
        assert init.title == "Add onboarding flow"
        assert init.status == InitiativeStatus.DRAFT.value
        assert init.verdict == InitiativeVerdict.PENDING.value

    def test_instantiate_with_all_fields(self) -> None:
        now = datetime.now(timezone.utc)
        init = Initiative(
            id=uuid.uuid4(),
            title="Full initiative",
            goal="Test all fields",
            hypothesis="If we do X, then Y",
            north_star_metric="conversion_rate",
            local_metric="step_2_completion",
            constraints={"budget": 500, "deadline": "2026-04-01"},
            non_goals="Do not change the auth flow",
            status=InitiativeStatus.EXECUTING.value,
            verdict=InitiativeVerdict.ITERATE.value,
            evaluation_window_ends_at=now + timedelta(days=7),
            rollout_plan={"stages": ["canary", "50%", "100%"]},
            task_graph_snapshot={"tasks": ["T1", "T2"]},
            created_at=now,
            updated_at=now,
        )
        assert init.status == "executing"
        assert init.verdict == "iterate"
        assert init.constraints["budget"] == 500


class TestInitiativeStatusEnum:
    def test_all_values(self) -> None:
        expected = {
            "draft", "planning", "executing", "in_review",
            "rolling_out", "measuring", "closed",
        }
        actual = {m.value for m in InitiativeStatus}
        assert actual == expected


class TestInitiativeVerdictEnum:
    def test_all_values(self) -> None:
        expected = {"pending", "scale", "iterate", "kill"}
        actual = {m.value for m in InitiativeVerdict}
        assert actual == expected


# ---------------------------------------------------------------------------
# Decision Ledger model tests
# ---------------------------------------------------------------------------

class TestDecisionRecordModel:
    def test_instantiate(self) -> None:
        record = DecisionRecord(
            id=uuid.uuid4(),
            category="architecture",
            agent_id="chief_architect",
            decision="Use event-driven architecture",
            reasoning="Better decoupling for microservices",
            assumptions=["Team has Kafka experience"],
            evidence_refs=["design-doc-v1"],
            risks=["Kafka complexity"],
            confidence=0.85,
            alternatives_considered=["REST polling", "GraphQL subscriptions"],
        )
        assert record.__tablename__ == "decision_ledger"
        assert record.confidence == 0.85
        assert len(record.assumptions) == 1
        assert record.outcome is None

    def test_outcome_fields(self) -> None:
        record = DecisionRecord(
            id=uuid.uuid4(),
            category="evaluation",
            agent_id="agent_evaluator",
            decision="Kill initiative",
            outcome="Metrics did not improve",
            assumptions_validated={"user_demand": False},
            lessons_learned="Validate demand before building",
        )
        assert record.outcome == "Metrics did not improve"
        assert record.assumptions_validated["user_demand"] is False


class TestDecisionCategoryEnum:
    def test_all_values(self) -> None:
        expected = {
            "architecture", "initiative", "budget", "routing",
            "rollout", "evaluation", "hiring",
        }
        actual = {m.value for m in DecisionCategory}
        assert actual == expected


# ---------------------------------------------------------------------------
# AgentOutput model tests
# ---------------------------------------------------------------------------

class TestAgentOutput:
    def test_defaults(self) -> None:
        output = AgentOutput()
        assert output.confidence == 0.0
        assert output.artifact_refs == []
        assert output.assumptions == []
        assert output.risks == []
        assert output.success_criteria == []

    def test_full_output(self) -> None:
        output = AgentOutput(
            artifact_refs=["design-doc.md"],
            decision="Chose REST over GraphQL",
            assumptions=["Low query complexity"],
            risks=["May need migration later"],
            confidence=0.75,
            requested_followups=["Implement endpoints"],
            blocking_dependencies=["Auth service must be ready"],
            success_criteria=["All endpoints pass integration tests"],
        )
        assert output.confidence == 0.75
        assert len(output.risks) == 1

    def test_confidence_bounds(self) -> None:
        import pytest
        with pytest.raises(Exception):
            AgentOutput(confidence=1.5)
        with pytest.raises(Exception):
            AgentOutput(confidence=-0.1)

    def test_serialization(self) -> None:
        output = AgentOutput(
            decision="Test decision",
            confidence=0.8,
            assumptions=["A1"],
        )
        d = output.model_dump()
        assert d["decision"] == "Test decision"
        assert d["confidence"] == 0.8


# ---------------------------------------------------------------------------
# Task model with initiative_id FK
# ---------------------------------------------------------------------------

class TestTaskInitiativeFK:
    def test_task_has_initiative_id(self) -> None:
        init_id = uuid.uuid4()
        task = Task(
            id=uuid.uuid4(),
            title="Implement feature",
            initiative_id=init_id,
        )
        assert task.initiative_id == init_id

    def test_task_initiative_id_optional(self) -> None:
        task = Task(
            id=uuid.uuid4(),
            title="Standalone task",
        )
        assert task.initiative_id is None


# ---------------------------------------------------------------------------
# Initiative State (TypedDict validation)
# ---------------------------------------------------------------------------

class TestInitiativeState:
    def test_state_construction(self) -> None:
        from aeco.orchestrator.initiative_state import InitiativeState

        state: InitiativeState = {
            "initiative_id": str(uuid.uuid4()),
            "title": "Test",
            "goal": "Test goal",
            "hypothesis": "If X then Y",
            "workspace_path": "./workspace",
            "project_context": None,
            "prd": None,
            "design_document": None,
            "task_graph": [],
            "execution_results": [],
            "evaluation": None,
            "north_star_metric": None,
            "local_metrics": [],
            "success_threshold": None,
            "evaluation_window_days": 7,
            "decisions": [],
            "current_phase": "intake",
            "verdict": None,
            "iteration_count": 0,
            "max_iterations": 3,
            "messages": [],
            "errors": [],
            "budget_spent": 0.0,
            "budget_remaining": 0.0,
        }
        assert state["current_phase"] == "intake"
        assert state["max_iterations"] == 3
