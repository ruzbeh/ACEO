"""End-to-end tests for the task workflow graph with mocked LLM responses.

These tests exercise the full LangGraph task workflow:
  intake → route → budget_check → architect → route → engineer → route → qa → route → publish

All LLM calls are mocked to return deterministic JSON responses.
ClickUp API calls are stubbed out (no external network).
"""
from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.orchestrator.graph import build_graph


# --- Mock LLM responses per agent ---

MOCK_RESPONSES: dict[str, dict[str, Any]] = {
    "coo_orchestrator": {
        # Sequence of routing decisions for each call
        "_sequence": [
            {"next_action": "needs_design", "reasoning": "New task, needs architecture first"},
            {"next_action": "needs_implementation", "reasoning": "Design complete, ready for coding"},
            {"next_action": "needs_qa", "reasoning": "Code written, needs review"},
            {"next_action": "all_done", "reasoning": "QA approved, shipping it"},
        ],
    },
    "chief_architect": {
        "design_document": {
            "overview": "REST API endpoint for user profile management",
            "components": ["UserProfileService", "ProfileRouter", "ProfileSchema"],
            "tech_stack": ["FastAPI", "SQLAlchemy", "Pydantic"],
        },
        "decision": "Implement as a standard CRUD REST API with Pydantic validation",
        "assumptions": ["PostgreSQL database is available", "Auth middleware exists"],
        "risks": ["Schema migration needed"],
        "confidence": 0.9,
    },
    "backend_engineer": {
        "code_artifacts": [
            {
                "path": "src/api/profile.py",
                "content": "from fastapi import APIRouter\nrouter = APIRouter()\n\n@router.get('/profile/{user_id}')\nasync def get_profile(user_id: str):\n    return {'user_id': user_id, 'name': 'Test User'}\n",
            },
            {
                "path": "src/models/profile.py",
                "content": "from pydantic import BaseModel\n\nclass Profile(BaseModel):\n    user_id: str\n    name: str\n",
            },
        ],
        "decision": "Implemented profile CRUD with FastAPI router",
        "assumptions": ["Using existing DB session pattern"],
        "risks": ["No auth check yet"],
        "confidence": 0.85,
    },
    "qa_engineer": {
        "review": {
            "approved": True,
            "summary": "Code looks good — clean API design, proper typing",
            "issues": [],
        },
        "test_results": {
            "passed": 3,
            "failed": 0,
            "tests": ["test_get_profile", "test_profile_model", "test_router_mounts"],
        },
        "decision": "Approved for merge",
        "assumptions": [],
        "risks": [],
        "confidence": 0.95,
    },
}


class _CallCounter:
    """Track per-agent call counts for sequenced responses."""

    def __init__(self):
        self.counts: dict[str, int] = {}

    def next(self, agent_id: str) -> int:
        idx = self.counts.get(agent_id, 0)
        self.counts[agent_id] = idx + 1
        return idx


_counter = _CallCounter()


def _mock_execute_factory():
    """Create a mock execute function that returns agent-specific responses."""
    counter = _CallCounter()

    async def mock_execute(context: dict[str, Any]) -> dict[str, Any]:
        # We need to figure out which agent this is for.
        # The runtime is instantiated with agent_def, so we patch at the class level.
        raise NotImplementedError("Should not be called directly")

    return mock_execute


def _make_mock_runtime(agent_id: str, counter: _CallCounter):
    """Create a mock runtime for a specific agent."""
    mock = MagicMock()

    async def execute(context: dict[str, Any]) -> dict[str, Any]:
        response = MOCK_RESPONSES.get(agent_id, {"raw": "unknown agent"})
        if "_sequence" in response:
            idx = counter.next(agent_id)
            seq = response["_sequence"]
            return seq[min(idx, len(seq) - 1)]
        return response

    mock.execute = execute
    return mock


@pytest.fixture
def agent_registry():
    """Load the real agent registry from YAML."""
    from pathlib import Path

    reg = AgentRegistry()
    yaml_path = Path("aeco/agents/definitions/v1_agents.yaml")
    reg.load_from_yaml(yaml_path)
    return reg


@pytest.fixture
def mock_audit_logger():
    """Create a mock audit logger that doesn't need a DB."""
    logger = MagicMock(spec=AuditLogger)
    logger.log = AsyncMock()
    return logger


@pytest.fixture
def counter():
    return _CallCounter()


@pytest.mark.asyncio
async def test_full_task_workflow_happy_path(agent_registry, mock_audit_logger, counter):
    """Test the complete task workflow: design → implement → QA → publish.

    This runs the full LangGraph graph with mocked LLM responses,
    verifying the state machine transitions correctly through all nodes.
    """

    # Patch create_executor to return our mock runtimes
    original_create_executor = None

    def mock_create_executor(agent_def, audit_logger=None):
        return _make_mock_runtime(agent_def.agent_id, counter)

    with patch("aeco.orchestrator.nodes.create_executor", side_effect=mock_create_executor), \
         patch("aeco.orchestrator.nodes.clickup_create_task", new_callable=AsyncMock, return_value={"id": "MOCK_CU_123"}), \
         patch("aeco.orchestrator.nodes.clickup_create_comment", new_callable=AsyncMock), \
         patch("aeco.orchestrator.nodes.file_write", new_callable=AsyncMock):

        graph = build_graph(agent_registry, mock_audit_logger)

        task_id = str(uuid.uuid4())
        run_id = str(uuid.uuid4())

        initial_state = {
            "workflow_run_id": run_id,
            "task_id": task_id,
            "clickup_task_id": None,
            "task_title": "Add user profile API endpoint",
            "task_description": "Create a REST API endpoint for CRUD operations on user profiles with proper validation.",
            "status": "todo",
            "workspace_path": "",
            "project_context": None,
            "messages": [],
            "design_document": None,
            "code_artifacts": [],
            "test_results": None,
            "review_feedback": None,
            "current_agent": None,
            "next_action": None,
            "iteration_count": 0,
            "max_iterations": 10,
            "budget_spent": 0.0,
            "budget_remaining": 100.0,
            "budget_warnings": [],
            "budget_optimization_hints": [],
            "budget_approved": True,
            "errors": [],
        }

        result = await graph.ainvoke(initial_state)

        # Verify workflow completed
        assert result["status"] == "done", f"Expected status 'done', got '{result['status']}'"

        # Verify we went through expected iterations
        # intake(0) → route(1) → architect → route(2) → engineer → route(3) → qa → route(4) → publish
        assert result["iteration_count"] >= 4, f"Expected at least 4 iterations, got {result['iteration_count']}"

        # Verify design document was produced
        assert result["design_document"] is not None, "Design document should be produced"

        # Verify code artifacts were produced
        assert len(result["code_artifacts"]) >= 2, f"Expected at least 2 code artifacts, got {len(result['code_artifacts'])}"

        # Verify QA passed
        assert result["test_results"] is not None, "Test results should exist"

        # Verify messages were accumulated
        assert len(result["messages"]) > 0, "Messages should be recorded"

        # Verify ClickUp task was created
        assert result["clickup_task_id"] == "MOCK_CU_123"

        # Verify no errors
        assert len(result.get("errors", [])) == 0, f"Unexpected errors: {result.get('errors')}"


@pytest.mark.asyncio
async def test_workflow_max_iterations_safety_valve(agent_registry, mock_audit_logger):
    """Test that the workflow stops at max_iterations even if COO keeps routing."""

    call_count = 0

    def mock_create_executor(agent_def, audit_logger=None):
        mock = MagicMock()

        async def execute(context: dict[str, Any]) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            if agent_def.agent_id == "coo_orchestrator":
                # Always request more work — never says all_done
                return {"next_action": "needs_design", "reasoning": "More work needed"}
            if agent_def.agent_id == "chief_architect":
                return {
                    "design_document": {"overview": "v" + str(call_count)},
                    "decision": "redesign",
                    "assumptions": [],
                    "risks": [],
                    "confidence": 0.5,
                }
            return {"raw": "fallback"}

        mock.execute = execute
        return mock

    with patch("aeco.orchestrator.nodes.create_executor", side_effect=mock_create_executor), \
         patch("aeco.orchestrator.nodes.clickup_create_task", new_callable=AsyncMock, return_value={"id": "CU_456"}), \
         patch("aeco.orchestrator.nodes.clickup_create_comment", new_callable=AsyncMock), \
         patch("aeco.orchestrator.nodes.file_write", new_callable=AsyncMock):

        graph = build_graph(agent_registry, mock_audit_logger)

        initial_state = {
            "workflow_run_id": str(uuid.uuid4()),
            "task_id": str(uuid.uuid4()),
            "clickup_task_id": None,
            "task_title": "Infinite loop test",
            "task_description": "This should stop at max_iterations.",
            "status": "todo",
            "workspace_path": "",
            "project_context": None,
            "messages": [],
            "design_document": None,
            "code_artifacts": [],
            "test_results": None,
            "review_feedback": None,
            "current_agent": None,
            "next_action": None,
            "iteration_count": 0,
            "max_iterations": 3,
            "budget_spent": 0.0,
            "budget_remaining": 100.0,
            "budget_warnings": [],
            "budget_optimization_hints": [],
            "budget_approved": True,
            "errors": [],
        }

        result = await graph.ainvoke(initial_state)

        # Should have stopped and published
        assert result["status"] == "done"
        assert result["iteration_count"] <= 4  # max_iterations=3 + 1 for the final route


@pytest.mark.asyncio
async def test_workflow_qa_rejection_triggers_rework(agent_registry, mock_audit_logger):
    """Test that QA rejection sends the task back to engineering."""

    route_calls = 0

    def mock_create_executor(agent_def, audit_logger=None):
        mock = MagicMock()

        async def execute(context: dict[str, Any]) -> dict[str, Any]:
            nonlocal route_calls
            if agent_def.agent_id == "coo_orchestrator":
                route_calls += 1
                if route_calls == 1:
                    return {"next_action": "needs_implementation", "reasoning": "Straight to coding"}
                if route_calls == 2:
                    return {"next_action": "needs_qa", "reasoning": "Code ready for review"}
                if route_calls == 3:
                    # After QA rejection, rework
                    return {"next_action": "needs_implementation", "reasoning": "QA rejected, rework needed"}
                if route_calls == 4:
                    return {"next_action": "needs_qa", "reasoning": "Rework done, re-review"}
                return {"next_action": "all_done", "reasoning": "QA passed on retry"}
            if agent_def.agent_id == "backend_engineer":
                return {
                    "code_artifacts": [{"path": "main.py", "content": "print('hello')"}],
                    "decision": "implemented",
                    "assumptions": [],
                    "risks": [],
                    "confidence": 0.8,
                }
            if agent_def.agent_id == "qa_engineer":
                # First QA call rejects, second approves
                first_qa = not context.get("review_feedback")
                if first_qa:
                    return {
                        "review": {"approved": False, "summary": "Missing error handling"},
                        "test_results": {"passed": 1, "failed": 1},
                        "decision": "Rejected",
                        "assumptions": [],
                        "risks": ["Missing error handling"],
                        "confidence": 0.6,
                    }
                return {
                    "review": {"approved": True, "summary": "Fixed, looks good now"},
                    "test_results": {"passed": 2, "failed": 0},
                    "decision": "Approved",
                    "assumptions": [],
                    "risks": [],
                    "confidence": 0.9,
                }
            return {"raw": "fallback"}

        mock.execute = execute
        return mock

    with patch("aeco.orchestrator.nodes.create_executor", side_effect=mock_create_executor), \
         patch("aeco.orchestrator.nodes.clickup_create_task", new_callable=AsyncMock, return_value={"id": "CU_789"}), \
         patch("aeco.orchestrator.nodes.clickup_create_comment", new_callable=AsyncMock), \
         patch("aeco.orchestrator.nodes.file_write", new_callable=AsyncMock):

        graph = build_graph(agent_registry, mock_audit_logger)

        initial_state = {
            "workflow_run_id": str(uuid.uuid4()),
            "task_id": str(uuid.uuid4()),
            "clickup_task_id": None,
            "task_title": "QA rejection rework test",
            "task_description": "First QA pass should reject, second should approve.",
            "status": "todo",
            "workspace_path": "",
            "project_context": None,
            "messages": [],
            "design_document": None,
            "code_artifacts": [],
            "test_results": None,
            "review_feedback": None,
            "current_agent": None,
            "next_action": None,
            "iteration_count": 0,
            "max_iterations": 10,
            "budget_spent": 0.0,
            "budget_remaining": 100.0,
            "budget_warnings": [],
            "budget_optimization_hints": [],
            "budget_approved": True,
            "errors": [],
        }

        result = await graph.ainvoke(initial_state)

        assert result["status"] == "done"
        # Should have gone through: route→eng→route→qa(reject)→route→eng→route→qa(approve)→route→publish
        assert route_calls >= 4, f"Expected at least 4 route calls (QA rejection + rework), got {route_calls}"
