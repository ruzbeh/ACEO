"""Node functions for the fast-track workflow: Architect -> Build -> Ship.

Designed for small, bounded tasks where the full initiative pipeline is overkill.
If the architect determines the task is too complex, it escalates to the initiative pipeline.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from aeco.agents.executor_factory import create_executor
from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.config import settings
from aeco.context.builder import ContextBuilder
from aeco.logging.company_logger import log_initiative_node
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.fast_track_state import FastTrackState
from aeco.tools.deploy_tools import deploy_preview
from aeco.tools.devops_tools import package_install
from aeco.tools.git_tools import git_branch, git_commit
from aeco.tools.scaffold_tools import scaffold_project
from aeco.tools.smoke_tools import smoke_test_url
from aeco.workspace_scanner.scanner import scan_workspace

if TYPE_CHECKING:
    from aeco.budget.engine import BudgetEngine

logger = logging.getLogger(__name__)

# Fast-track complexity thresholds
MAX_FAST_TRACK_FILES = 8
MAX_FAST_TRACK_FILES_SCAFFOLD = 25  # Higher limit for scaffolded new projects
FAST_TRACK_BUDGET_CAP = 20.0  # auto-approve under $20


def _msg(sender: str, msg_type: str, content: Any) -> dict:
    return {
        "sender": sender,
        "type": msg_type,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


class FastTrackNodes:
    """Node functions for the 3-step fast-track pipeline."""

    def __init__(
        self,
        registry: AgentRegistry,
        audit_logger: AuditLogger,
        context_builder: ContextBuilder,
        decision_ledger: DecisionLedgerStore,
        budget_engine: "BudgetEngine | None" = None,
    ) -> None:
        self.registry = registry
        self.audit = audit_logger
        self.ctx = context_builder
        self.ledger = decision_ledger
        self.budget = budget_engine

    # ------------------------------------------------------------------
    # intake: scan workspace, build project context
    # ------------------------------------------------------------------

    async def intake(self, state: FastTrackState) -> dict:
        """Initialize fast-track: scan workspace and build project context."""
        logger.info(f"Fast-track intake: {state['request'][:100]}")
        log_initiative_node(
            "fast_track_intake",
            f"Fast-track request: {state['request'][:200]}",
            initiative_id=state["request_id"],
        )

        workspace_path = state.get("workspace_path") or settings.workspace_path
        project_context = None
        try:
            project_context = await scan_workspace(workspace_path)
        except Exception as e:
            logger.warning(f"Workspace scan failed: {e}")

        return {
            "current_phase": "architect",
            "project_context": project_context,
            "workspace_path": workspace_path,
            "messages": [_msg("system", "status", f"Fast-track started: {state['request'][:100]}")],
        }

    # ------------------------------------------------------------------
    # architect: minimal plan (what to change, approach)
    # ------------------------------------------------------------------

    async def architect(self, state: FastTrackState) -> dict:
        """Architect produces a minimal plan for the fast-track task."""
        logger.info("Fast-track architect: creating plan")
        log_initiative_node("fast_track_architect", "Architect planning", initiative_id=state["request_id"])

        agent_def = self.registry.get("chief_architect")
        runtime = create_executor(agent_def, self.audit)

        context = {
            "action": "fast_track_plan",
            "request": state["request"],
            "workspace_path": state.get("workspace_path", ""),
            "project_context": state.get("project_context"),
            "instructions": (
                "This is a FAST-TRACK task. Create a minimal implementation plan.\n"
                "Your plan must include:\n"
                "1. 'approach': Brief description of the implementation approach (2-3 sentences)\n"
                "2. 'files_to_change': List of files to create or modify\n"
                "3. 'estimated_complexity': 'low', 'medium', or 'high'\n"
                "4. 'escalate': true if this task is too complex for fast-track "
                f"(needs >={MAX_FAST_TRACK_FILES} files for existing projects, "
                "database migrations, new infrastructure, or fundamental architecture changes). false otherwise.\n"
                "5. 'escalate_reason': Why this should be escalated (only if escalate=true)\n"
                "6. 'is_new_project': true if this is a new app/product to build from scratch "
                "(empty workspace or request asks to 'build', 'create', 'make' a new app). "
                "false if modifying an existing project.\n"
                "7. 'stack': If is_new_project=true, recommended stack. Options: 'nextjs-supabase-stripe' "
                "(default for SaaS), 'fastapi-react-postgres', 'landing-page-only'\n"
                "8. 'features': If is_new_project=true, list of features needed. "
                "Options: 'auth', 'payments', 'file-upload', 'ai-generation'\n"
                "9. 'project_name': If is_new_project=true, a short slug name for the project\n\n"
                "For new projects, the scaffolder will generate boilerplate automatically — "
                "only list the custom business logic files in 'files_to_change'.\n"
                "Keep it brief. No full design document needed."
            ),
        }

        try:
            result = await asyncio.wait_for(
                runtime.execute(context),
                timeout=settings.initiative_task_timeout_seconds,
            )
        except Exception as e:
            logger.error(f"Fast-track architect failed: {e}")
            return {
                "current_phase": "done",
                "errors": [f"Architect failed: {e}"],
                "messages": [_msg("architect", "error", str(e))],
            }

        # Detect new project
        is_new_project = result.get("is_new_project", False)
        # Also infer from state hints
        if state.get("stack") or state.get("features"):
            is_new_project = True

        # Check if architect wants to escalate
        should_escalate = result.get("escalate", False)
        files_to_change = result.get("files_to_change", [])
        file_limit = MAX_FAST_TRACK_FILES_SCAFFOLD if is_new_project else MAX_FAST_TRACK_FILES
        if len(files_to_change) >= file_limit:
            should_escalate = True

        if should_escalate:
            reason = result.get("escalate_reason", "Task exceeds fast-track scope")
            logger.info(f"Fast-track escalating to initiative: {reason}")
            return {
                "current_phase": "escalated",
                "escalate_to_initiative": True,
                "plan": result,
                "decisions": [{"agent": "chief_architect", "phase": "fast_track_architect", "decision": f"Escalated: {reason}"}],
                "messages": [_msg("architect", "escalate", reason)],
            }

        next_phase = "scaffold" if is_new_project else "build"
        return {
            "current_phase": next_phase,
            "plan": result,
            "escalate_to_initiative": False,
            "is_new_project": is_new_project,
            "stack": result.get("stack") or state.get("stack") or "nextjs-supabase-stripe",
            "features": result.get("features") or state.get("features") or [],
            "project_name": result.get("project_name") or state.get("project_name"),
            "decisions": [{"agent": "chief_architect", "phase": "fast_track_architect", "decision": result.get("approach", "Plan created")}],
            "messages": [_msg("architect", "plan", f"Plan ready: {len(files_to_change)} files. New project: {is_new_project}")],
        }

    # ------------------------------------------------------------------
    # build: fullstack engineer implements the plan
    # ------------------------------------------------------------------

    async def build(self, state: FastTrackState) -> dict:
        """Fullstack engineer implements the architect's plan."""
        logger.info("Fast-track build: implementing changes")
        log_initiative_node("fast_track_build", "Engineer implementing", initiative_id=state["request_id"])

        agent_def = self.registry.get("fullstack_engineer")
        runtime = create_executor(agent_def, self.audit)

        plan = state.get("plan") or {}
        scaffold_result = state.get("scaffold_result")

        # Build scaffold context if project was scaffolded
        scaffold_info = ""
        if scaffold_result and scaffold_result.get("status") == "ok":
            scaffold_files = scaffold_result.get("files_created", [])
            scaffold_info = (
                f"\n\nIMPORTANT: A project skeleton has already been scaffolded at "
                f"{scaffold_result.get('path', state.get('workspace_path'))} with {len(scaffold_files)} files.\n"
                f"Stack: {scaffold_result.get('stack')}, Features: {scaffold_result.get('features')}\n"
                f"Key files already created: {', '.join(scaffold_files[:15])}\n"
                "DO NOT recreate boilerplate (auth, Stripe webhook, layout, middleware). "
                "Focus ONLY on the custom business logic specific to this product.\n"
            )

        context = {
            "action": "fast_track_implement",
            "request": state["request"],
            "plan": plan,
            "workspace_path": state.get("workspace_path", ""),
            "project_context": state.get("project_context"),
            "instructions": (
                "Implement the following plan in the workspace.\n\n"
                f"User request: {state['request']}\n\n"
                f"Architect plan: {plan.get('approach', 'No specific plan')}\n"
                f"Files to change: {plan.get('files_to_change', [])}\n"
                f"{scaffold_info}\n"
                "Requirements:\n"
                "- Write clean, production-ready code\n"
                "- Follow existing patterns in the codebase\n"
                "- Run any available tests to verify your changes\n"
                "- Include all necessary imports and dependencies\n"
                "- List all files you created or modified in 'files_changed'\n"
            ),
        }

        try:
            result = await asyncio.wait_for(
                runtime.execute(context),
                timeout=settings.initiative_task_timeout_seconds,
            )
        except Exception as e:
            logger.error(f"Fast-track build failed: {e}")
            return {
                "current_phase": "done",
                "errors": [f"Build failed: {e}"],
                "messages": [_msg("engineer", "error", str(e))],
            }

        files_changed = result.get("files_changed", result.get("files_modified", []))
        return {
            "current_phase": "ship",
            "build_result": result,
            "files_changed": files_changed,
            "decisions": [{"agent": "fullstack_engineer", "phase": "fast_track_build", "decision": result.get("decision", "Code implemented")}],
            "messages": [_msg("engineer", "build", f"Built: {len(files_changed)} files changed")],
        }

    # ------------------------------------------------------------------
    # ship: git commit + install deps + deploy preview
    # ------------------------------------------------------------------

    async def ship(self, state: FastTrackState) -> dict:
        """Commit changes, install deps, deploy preview."""
        logger.info("Fast-track ship: committing and deploying")
        log_initiative_node("fast_track_ship", "Shipping changes", initiative_id=state["request_id"])

        workspace = state.get("workspace_path") or settings.workspace_path
        request_id = state["request_id"]
        errors: list[str] = []
        messages: list[dict] = []

        # 1. Create feature branch
        branch_name = f"aeco/fast-track-{request_id[:8]}"
        try:
            branch_result = await git_branch(branch_name, workspace)
            if branch_result["status"] == "error":
                errors.append(f"Branch: {branch_result['error']}")
        except Exception as e:
            errors.append(f"Branch failed: {e}")

        # 2. Git commit
        git_result = None
        commit_msg = f"fast-track: {state['request'][:72]}"
        try:
            git_result = await git_commit(
                message=commit_msg,
                files=state.get("files_changed") or None,
                workspace_path=workspace,
            )
            if git_result.get("status") == "ok":
                messages.append(_msg("ship", "git", f"Committed: {git_result.get('commit', '?')}"))
            elif git_result.get("status") == "no_changes":
                messages.append(_msg("ship", "git", "No changes to commit"))
            else:
                errors.append(f"Git commit: {git_result.get('error', 'unknown error')}")
        except Exception as e:
            errors.append(f"Git commit failed: {e}")

        # 3. Install dependencies
        try:
            pkg_result = await package_install(workspace)
            if pkg_result["status"] == "error":
                errors.append(f"Package install: {pkg_result['error']}")
            else:
                messages.append(_msg("ship", "deps", f"Dependencies installed ({pkg_result.get('manager', '?')})"))
        except Exception as e:
            # Non-fatal: deps might already be installed
            logger.warning(f"Package install skipped: {e}")

        # 4. Deploy preview
        deploy_result = None
        preview_url = None
        try:
            deploy_result = await deploy_preview(workspace)
            if deploy_result.get("status") == "ok":
                preview_url = deploy_result.get("preview_url")
                messages.append(_msg("ship", "deploy", f"Preview deployed: {preview_url}"))
            else:
                errors.append(f"Deploy: {deploy_result.get('error', 'unknown error')}")
        except Exception as e:
            errors.append(f"Deploy failed: {e}")

        # Route to verify if we got a URL, otherwise done
        next_phase = "verify" if preview_url else "done"
        return {
            "current_phase": next_phase,
            "git_result": git_result,
            "deploy_result": deploy_result,
            "preview_url": preview_url,
            "errors": errors,
            "messages": messages,
            "decisions": [{
                "agent": "system",
                "phase": "fast_track_ship",
                "decision": f"Shipped. Preview: {preview_url or 'N/A'}. Commit: {git_result.get('commit', 'N/A') if git_result else 'N/A'}",
            }],
        }

    # ------------------------------------------------------------------
    # scaffold: generate project from template (new projects only)
    # ------------------------------------------------------------------

    async def scaffold(self, state: FastTrackState) -> dict:
        """Scaffold a new project from a template. Deterministic — no LLM call."""
        logger.info("Fast-track scaffold: generating project skeleton")
        log_initiative_node("fast_track_scaffold", "Scaffolding project", initiative_id=state["request_id"])

        project_name = state.get("project_name") or "new-project"
        stack = state.get("stack") or "nextjs-supabase-stripe"
        features = state.get("features") or []
        workspace = state.get("workspace_path") or settings.workspace_path

        try:
            result = await scaffold_project(
                name=project_name,
                stack=stack,
                features=features,
                workspace_path=workspace,
            )
        except Exception as e:
            logger.error(f"Scaffold failed: {e}")
            return {
                "current_phase": "build",
                "scaffold_result": {"status": "error", "error": str(e)},
                "errors": [f"Scaffold failed: {e}"],
                "messages": [_msg("scaffold", "error", str(e))],
            }

        if result.get("status") != "ok":
            return {
                "current_phase": "build",
                "scaffold_result": result,
                "errors": [f"Scaffold error: {result.get('error', 'unknown')}"],
                "messages": [_msg("scaffold", "error", result.get("error", "unknown"))],
            }

        # Update workspace path to the scaffolded project directory
        scaffolded_path = result.get("path", workspace)
        files_created = result.get("files_created", [])
        logger.info(f"Scaffolded {len(files_created)} files at {scaffolded_path}")

        return {
            "current_phase": "build",
            "scaffold_result": result,
            "workspace_path": scaffolded_path,
            "files_changed": files_created,
            "messages": [_msg("scaffold", "complete", f"Scaffolded {len(files_created)} files ({stack}, features: {features})")],
        }

    # ------------------------------------------------------------------
    # verify: smoke test the deployed preview
    # ------------------------------------------------------------------

    async def verify(self, state: FastTrackState) -> dict:
        """Smoke test the deployed preview URL."""
        preview_url = state.get("preview_url")
        if not preview_url:
            return {
                "current_phase": "done",
                "messages": [_msg("verify", "skip", "No preview URL to verify")],
            }

        logger.info(f"Fast-track verify: smoke testing {preview_url}")
        log_initiative_node("fast_track_verify", f"Smoke testing {preview_url}", initiative_id=state["request_id"])

        try:
            result = await smoke_test_url(preview_url, timeout=30)
        except Exception as e:
            logger.warning(f"Smoke test failed: {e}")
            return {
                "current_phase": "done",
                "smoke_result": {"status": "error", "error": str(e)},
                "messages": [_msg("verify", "error", f"Smoke test failed: {e}")],
            }

        passed = result.get("checks_passed", 0)
        failed = result.get("checks_failed", 0)
        logger.info(f"Smoke test: {passed} passed, {failed} failed")

        return {
            "current_phase": "done",
            "smoke_result": result,
            "messages": [_msg("verify", "smoke_test", f"Smoke test: {passed} passed, {failed} failed")],
        }
