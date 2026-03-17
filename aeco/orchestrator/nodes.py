"""Node functions for the AECO LangGraph workflow."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from aeco.agents.registry import AgentRegistry
from aeco.agents.runtime import AgentRuntime
from aeco.audit.logger import AuditLogger
from aeco.orchestrator.state import AECOState
from aeco.tools.clickup_tools import clickup_create_comment, clickup_create_task

logger = logging.getLogger(__name__)


def _make_message(sender: str, msg_type: str, content: Any) -> dict:
    return {
        "sender": sender,
        "type": msg_type,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class WorkflowNodes:
    """Container for all node functions, with shared dependencies."""

    def __init__(self, registry: AgentRegistry, audit_logger: AuditLogger) -> None:
        self.registry = registry
        self.audit_logger = audit_logger

    async def intake(self, state: AECOState) -> dict:
        """Initialize the workflow. Create ClickUp task if needed."""
        logger.info(f"Intake: processing task '{state['task_title']}'")

        clickup_task_id = state.get("clickup_task_id")

        # Create ClickUp task if we don't have one
        if not clickup_task_id:
            try:
                result = await clickup_create_task(
                    name=state["task_title"],
                    description=state["task_description"],
                )
                clickup_task_id = result["id"]
                logger.info(f"Created ClickUp task: {clickup_task_id}")
            except Exception as e:
                logger.warning(f"Failed to create ClickUp task: {e}")

        return {
            "clickup_task_id": clickup_task_id,
            "status": "intake",
            "current_agent": "coo_orchestrator",
            "messages": [
                _make_message(
                    "system",
                    "status_update",
                    f"Workflow started for: {state['task_title']}",
                )
            ],
        }

    async def route(self, state: AECOState) -> dict:
        """COO Orchestrator decides what happens next."""
        logger.info(f"Route: iteration {state['iteration_count']}")

        agent_def = self.registry.get("coo_orchestrator")
        runtime = AgentRuntime(agent_def, self.audit_logger)

        context = {
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "current_status": state["status"],
            "iteration_count": state["iteration_count"],
            "max_iterations": state["max_iterations"],
            "has_design": state.get("design_document") is not None,
            "has_code": len(state.get("code_artifacts", [])) > 0,
            "has_test_results": state.get("test_results") is not None,
            "review_feedback": state.get("review_feedback"),
            "recent_messages": state.get("messages", [])[-5:],
        }

        result = await runtime.execute(context)

        next_action = result.get("next_action", "needs_design")
        reasoning = result.get("reasoning", "")

        logger.info(f"Route decision: {next_action} — {reasoning}")

        return {
            "next_action": next_action,
            "current_agent": "coo_orchestrator",
            "iteration_count": state["iteration_count"] + 1,
            "messages": [
                _make_message(
                    "coo_orchestrator",
                    "status_update",
                    {"decision": next_action, "reasoning": reasoning},
                )
            ],
        }

    async def architect(self, state: AECOState) -> dict:
        """Chief Architect produces a design document."""
        logger.info("Architect: creating design document")

        agent_def = self.registry.get("chief_architect")
        runtime = AgentRuntime(agent_def, self.audit_logger)

        context = {
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "existing_messages": state.get("messages", [])[-10:],
        }

        result = await runtime.execute(context)
        design_doc = json.dumps(result.get("design_document", result), indent=2)

        # Post design to ClickUp
        if state.get("clickup_task_id"):
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**Architecture Design**\n\n```json\n{design_doc[:3000]}\n```",
                )
            except Exception as e:
                logger.warning(f"Failed to post design to ClickUp: {e}")

        return {
            "design_document": design_doc,
            "status": "architect_design",
            "current_agent": "chief_architect",
            "next_action": "needs_implementation",
            "messages": [
                _make_message("chief_architect", "design_document", result)
            ],
        }

    async def engineer(self, state: AECOState) -> dict:
        """Backend Engineer writes code based on the design."""
        logger.info("Engineer: implementing code")

        agent_def = self.registry.get("backend_engineer")
        runtime = AgentRuntime(agent_def, self.audit_logger)

        context = {
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "design_document": state.get("design_document"),
            "review_feedback": state.get("review_feedback"),
            "existing_code": state.get("code_artifacts", []),
            "recent_messages": state.get("messages", [])[-10:],
        }

        result = await runtime.execute(context)
        code_artifacts = result.get("code_artifacts", [])

        # Post summary to ClickUp
        if state.get("clickup_task_id"):
            files = [a.get("path", "unknown") for a in code_artifacts]
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**Implementation Complete**\nFiles: {', '.join(files)}",
                )
            except Exception as e:
                logger.warning(f"Failed to post to ClickUp: {e}")

        return {
            "status": "engineering",
            "current_agent": "backend_engineer",
            "next_action": "needs_qa",
            "review_feedback": None,  # Clear previous feedback
            "code_artifacts": code_artifacts,
            "messages": [_make_message("backend_engineer", "code_artifact", result)],
        }

    async def qa(self, state: AECOState) -> dict:
        """QA Engineer reviews code and runs tests."""
        logger.info("QA: reviewing and testing")

        agent_def = self.registry.get("qa_engineer")
        runtime = AgentRuntime(agent_def, self.audit_logger)

        context = {
            "task_title": state["task_title"],
            "task_description": state["task_description"],
            "design_document": state.get("design_document"),
            "code_artifacts": state.get("code_artifacts", []),
            "recent_messages": state.get("messages", [])[-10:],
        }

        result = await runtime.execute(context)

        review = result.get("review", {})
        approved = review.get("approved", False)
        feedback = review.get("summary", "")
        test_results = result.get("test_results", {})

        # Post review to ClickUp
        if state.get("clickup_task_id"):
            status_emoji = "approved" if approved else "needs changes"
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**QA Review: {status_emoji}**\n{feedback}",
                )
            except Exception as e:
                logger.warning(f"Failed to post QA review to ClickUp: {e}")

        next_action = "all_done" if approved else "needs_implementation"

        return {
            "status": "qa_review",
            "current_agent": "qa_engineer",
            "next_action": next_action,
            "review_feedback": None if approved else feedback,
            "test_results": test_results,
            "messages": [_make_message("qa_engineer", "code_review", result)],
        }

    async def publish(self, state: AECOState) -> dict:
        """Finalize: update ClickUp task status and post summary."""
        logger.info("Publish: finalizing workflow")

        # Update ClickUp task to done
        if state.get("clickup_task_id"):
            try:
                await clickup_create_comment(
                    state["clickup_task_id"],
                    f"**Workflow Complete**\n"
                    f"Iterations: {state['iteration_count']}\n"
                    f"Files created: {len(state.get('code_artifacts', []))}",
                )
            except Exception as e:
                logger.warning(f"Failed to post completion to ClickUp: {e}")

        return {
            "status": "done",
            "current_agent": None,
            "next_action": None,
            "messages": [
                _make_message(
                    "system",
                    "status_update",
                    f"Workflow completed after {state['iteration_count']} iterations",
                )
            ],
        }
