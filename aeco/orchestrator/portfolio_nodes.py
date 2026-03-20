"""Node functions for the portfolio-level LangGraph workflow.

Flow: opportunity_scan → portfolio_review → execute_portfolio → portfolio_evaluate → rebalance → (loop or close)
"""
from __future__ import annotations

import asyncio
import json
import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from aeco.agents.executor_factory import create_executor
from aeco.agents.registry import AgentRegistry
from aeco.audit.logger import AuditLogger
from aeco.config import settings
from aeco.context.builder import ContextBuilder
from aeco.workspace_scanner.scanner import scan_workspace
from aeco.events import (
    PORTFOLIO_CLOSED,
    PORTFOLIO_CYCLE_STARTED,
    PORTFOLIO_DECISIONS_MADE,
    PORTFOLIO_EVALUATED,
    PORTFOLIO_EXECUTION_COMPLETED,
    PORTFOLIO_EXECUTION_STARTED,
    PORTFOLIO_OPPORTUNITIES_DISCOVERED,
    PORTFOLIO_REBALANCED,
    event_bus,
)
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.orchestrator.portfolio_state import PortfolioState
from aeco.tools.whatsapp_tools import (
    whatsapp_send_alert,
    whatsapp_send_portfolio_update,
)

if TYPE_CHECKING:
    from aeco.budget.engine import BudgetEngine

logger = logging.getLogger(__name__)


def _msg(sender: str, msg_type: str, content: Any) -> dict:
    return {
        "sender": sender,
        "type": msg_type,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _check_parse_error(result: dict, agent_id: str) -> str | None:
    """If the agent result has parse_error, return a human-readable error string."""
    if result.get("parse_error"):
        raw = result.get("raw_response", "")
        preview = raw[:500] if raw else "(empty)"
        return (
            f"Agent '{agent_id}' returned a non-JSON response. "
            f"The LLM output could not be parsed into the expected format. "
            f"Raw response preview: {preview}"
        )
    return None


class PortfolioNodes:
    """Node functions for portfolio-level orchestration."""

    def __init__(
        self,
        registry: AgentRegistry,
        audit_logger: AuditLogger,
        context_builder: ContextBuilder,
        decision_ledger: DecisionLedgerStore,
        budget_engine: "BudgetEngine | None" = None,
        initiative_graph: Any = None,
    ) -> None:
        self.registry = registry
        self.audit = audit_logger
        self.ctx = context_builder
        self.ledger = decision_ledger
        self.budget = budget_engine
        self.initiative_graph = initiative_graph

    # ------------------------------------------------------------------
    # opportunity_scan: Product Strategist discovers opportunities
    # ------------------------------------------------------------------

    def _build_product_context(self, workspace_path: str) -> dict:
        """Scan workspace to build product context for agents."""
        try:
            ctx = scan_workspace(workspace_path)
            logger.info(
                f"Product context: {ctx.get('product_name', '?')}, "
                f"stack={ctx.get('tech_stack', [])}, files={ctx.get('file_count', 0)}"
            )
            return ctx
        except Exception as e:
            logger.warning(f"Workspace scan failed: {e}")
            return {"product_name": "Unknown", "error": str(e)}

    async def _call_product_strategist(
        self, context: dict, messages: list
    ) -> tuple[dict, list, str | None]:
        """Call product strategist and return (result, opportunities, parse_err)."""
        agent_def = self.registry.get("product_strategist")
        runtime = create_executor(agent_def, self.audit)

        messages.append(_msg("system", "agent_call", {
            "agent": "product_strategist",
            "action": "Calling Product Strategist to discover opportunities...",
            "context_keys": list(context.keys()),
        }))

        result = await runtime.execute(context)

        parse_err = _check_parse_error(result, "product_strategist")
        opportunities = []

        if parse_err:
            logger.warning(parse_err)
            messages.append(_msg("product_strategist", "parse_error", {
                "error": parse_err,
                "raw_preview": result.get("raw_response", "")[:500],
            }))
        else:
            opportunities = result.get("opportunities", [])
            messages.append(_msg("product_strategist", "response", {
                "opportunities_found": len(opportunities),
                "decision": result.get("decision", ""),
                "portfolio_gaps": result.get("portfolio_gaps", []),
                "confidence": result.get("confidence", 0),
            }))

        return result, opportunities, parse_err

    async def opportunity_scan(self, state: PortfolioState) -> dict:
        cycle = state.get("cycle_count", 0)
        goals = state.get("company_goals", [])
        budget_remaining = state.get("budget_remaining", 0)
        workspace_path = state.get("workspace_path", settings.workspace_path)

        logger.info(f"Portfolio cycle {cycle}: scanning for opportunities")

        messages = [
            _msg("system", "phase_start", {
                "phase": "opportunity_scan",
                "cycle": cycle,
                "goals": goals,
                "budget_remaining": budget_remaining,
            }),
        ]

        await event_bus.emit(PORTFOLIO_CYCLE_STARTED, {
            "portfolio_id": state["portfolio_id"],
            "cycle": cycle,
        })

        # ── NEW: Scan workspace to build product context ──
        product_context = self._build_product_context(workspace_path)
        messages.append(_msg("system", "workspace_scanned", {
            "product_name": product_context.get("product_name", "?"),
            "tech_stack": product_context.get("tech_stack", []),
            "file_count": product_context.get("file_count", 0),
        }))

        result = {}
        opportunities = []
        parse_err = None

        try:
            recent_outcomes = []
            for init in state.get("active_initiatives", []):
                if init.get("verdict"):
                    recent_outcomes.append({
                        "title": init.get("title"),
                        "verdict": init.get("verdict"),
                        "budget_spent": init.get("budget_spent", 0),
                    })

            # ── CRITICAL: Include product context so the agent knows what the product IS ──
            context = {
                "company_goals": goals,
                "product_context": {
                    "product_name": product_context.get("product_name", "Unknown"),
                    "product_description": product_context.get("product_description", ""),
                    "tech_stack": product_context.get("tech_stack", []),
                    "directory_structure": product_context.get("directory_structure", "")[:1500],
                    "has_tests": product_context.get("has_tests", False),
                    "has_docker": product_context.get("has_docker", False),
                    "file_count": product_context.get("file_count", 0),
                    "key_config_files": {
                        k: v[:500] for k, v in product_context.get("key_files", {}).items()
                        if k in ("package.json", "pyproject.toml", "requirements.txt",
                                 ".env.example", ".env.sample", "docker-compose.yml",
                                 "README.md", "readme.md")
                    },
                },
                "recent_outcomes": recent_outcomes,
                "active_initiatives": state.get("active_initiatives", []),
                "budget_remaining": budget_remaining,
                "cycle_count": cycle,
                "past_opportunities": [
                    {"title": o.get("title"), "category": o.get("category")}
                    for o in state.get("opportunities", [])[-5:]
                ],
                "workspace_path": workspace_path,
            }

            # ── First attempt ──
            result, opportunities, parse_err = await self._call_product_strategist(
                context, messages
            )

            # ── RETRY: If 0 opportunities and no parse error, try once more with emphasis ──
            if not opportunities and not parse_err:
                logger.warning(
                    "Product Strategist returned 0 opportunities (valid JSON but empty). "
                    "Retrying with emphasis..."
                )
                messages.append(_msg("system", "retry", {
                    "reason": "No opportunities in first attempt",
                    "action": "Retrying with stronger emphasis on generating concrete opportunities",
                }))
                context["IMPORTANT_INSTRUCTION"] = (
                    "You MUST return at least 1-3 concrete opportunities. "
                    "The product is real, the goals are real, the budget is available. "
                    "Analyze the product_context and propose specific, actionable improvements. "
                    "Do NOT return an empty opportunities array."
                )
                result, opportunities, parse_err = await self._call_product_strategist(
                    context, messages
                )

            # Log each opportunity
            for i, opp in enumerate(opportunities):
                title = opp.get("title", f"Opportunity {i+1}")
                messages.append(_msg("product_strategist", "opportunity", {
                    "index": i + 1,
                    "title": title,
                    "goal": opp.get("goal", ""),
                    "hypothesis": opp.get("hypothesis", ""),
                    "estimated_impact": opp.get("estimated_impact", ""),
                    "confidence": opp.get("confidence", 0),
                    "category": opp.get("category", ""),
                }))

            logger.info(f"Product Strategist discovered {len(opportunities)} opportunities")

        except Exception as e:
            err_msg = f"Product Strategist failed: {e}"
            logger.error(err_msg, exc_info=True)
            messages.append(_msg("product_strategist", "error", {
                "error": err_msg,
                "traceback": traceback.format_exc()[:500],
            }))

        # Record in decision ledger
        try:
            await self.ledger.record(
                category="portfolio",
                agent_id="product_strategist",
                decision=result.get("decision", f"Discovered {len(opportunities)} opportunities"),
                reasoning=json.dumps([o.get("title") for o in opportunities])[:500],
                assumptions=result.get("assumptions", []),
                risks=result.get("risks", []),
                confidence=result.get("confidence", 0.0),
            )
        except Exception:
            pass

        await event_bus.emit(PORTFOLIO_OPPORTUNITIES_DISCOVERED, {
            "portfolio_id": state["portfolio_id"],
            "count": len(opportunities),
            "titles": [o.get("title", "") for o in opportunities],
        })

        errors = []
        if not opportunities:
            err = "No opportunities discovered — the Product Strategist returned empty results."
            if parse_err:
                err += f" (Parse error: LLM response was not valid JSON)"
            errors.append(err)
            messages.append(_msg("system", "warning", err))
            logger.error(
                "CIRCUIT BREAKER: 0 opportunities after retry. "
                "Check: (1) Is the workspace_path correct? (2) Is the LLM API key valid? "
                "(3) Check logs/company.log for raw LLM responses."
            )

        return {
            "opportunities": opportunities,
            "current_phase": "portfolio_review",
            "decisions": [{
                "agent": "product_strategist",
                "phase": "opportunity_scan",
                "decision": result.get("decision", ""),
                "opportunity_count": len(opportunities),
            }],
            "messages": messages,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # portfolio_review: CEO reviews and makes funding/kill decisions
    # ------------------------------------------------------------------

    async def portfolio_review(self, state: PortfolioState) -> dict:
        opportunities = state.get("opportunities", [])
        budget_remaining = state.get("budget_remaining", 0)

        logger.info(f"CEO: reviewing {len(opportunities)} opportunities, ${budget_remaining:.2f} remaining")

        # ── CIRCUIT BREAKER: If no opportunities, skip CEO review entirely ──
        if not opportunities:
            logger.warning("No opportunities to review — skipping CEO review")
            return {
                "funded_initiatives": [],
                "killed_initiatives": [],
                "current_phase": "executing",
                "portfolio_decisions": [{
                    "agent": "ceo_director",
                    "phase": "portfolio_review",
                    "funded": [],
                    "killed": [],
                    "scaled": [],
                    "reasoning": "No opportunities to review — Product Strategist found nothing.",
                }],
                "messages": [
                    _msg("system", "phase_start", {
                        "phase": "portfolio_review",
                        "opportunities_count": 0,
                        "budget_remaining": budget_remaining,
                    }),
                    _msg("system", "warning", "Skipped CEO review: no opportunities available."),
                ],
                "errors": ["No opportunities available for CEO review."],
            }

        messages = [
            _msg("system", "phase_start", {
                "phase": "portfolio_review",
                "opportunities_count": len(opportunities),
                "budget_remaining": budget_remaining,
            }),
        ]

        funded = []
        killed = []
        scaled = []
        result = {}

        try:
            agent_def = self.registry.get("ceo_director")
            runtime = create_executor(agent_def, self.audit)

            context = {
                "company_goals": state.get("company_goals", []),
                "active_initiatives": state.get("active_initiatives", []),
                "opportunities": opportunities[-10:],
                "budget_state": {
                    "total": state.get("total_budget", 0),
                    "spent": state.get("budget_spent", 0),
                    "remaining": budget_remaining,
                },
                "past_decisions": state.get("portfolio_decisions", [])[-5:],
                "cycle_count": state.get("cycle_count", 0),
                "IMPORTANT_INSTRUCTION": (
                    "You MUST fund at least one opportunity if the budget allows. "
                    "The opportunities have been vetted by the Product Strategist. "
                    "Allocate budget and set priority for each funded initiative."
                ),
            }

            messages.append(_msg("system", "agent_call", {
                "agent": "ceo_director",
                "action": f"CEO reviewing {len(opportunities)} opportunities with ${budget_remaining:.2f} budget...",
            }))

            result = await runtime.execute(context)

            # Check for parse errors
            parse_err = _check_parse_error(result, "ceo_director")
            if parse_err:
                logger.warning(parse_err)
                messages.append(_msg("ceo_director", "parse_error", {
                    "error": parse_err,
                    "raw_preview": result.get("raw_response", "")[:500],
                }))
            else:
                funded = result.get("fund", [])
                killed = result.get("kill", [])
                scaled = result.get("scale", [])

                messages.append(_msg("ceo_director", "decisions", {
                    "funded_count": len(funded),
                    "killed_count": len(killed),
                    "scaled_count": len(scaled),
                    "reasoning": result.get("reasoning", ""),
                    "decision": result.get("decision", ""),
                    "confidence": result.get("confidence", 0),
                }))

                # Log each funding decision
                for f in funded:
                    messages.append(_msg("ceo_director", "fund_decision", {
                        "title": f.get("title", "?"),
                        "allocated_budget": f.get("allocated_budget", 0),
                        "priority": f.get("priority", ""),
                        "reasoning": f.get("reasoning", ""),
                    }))

            logger.info(f"CEO decisions: fund {len(funded)}, kill {len(killed)}, scale {len(scaled)}")

        except Exception as e:
            err_msg = f"CEO review failed: {e}"
            logger.error(err_msg, exc_info=True)
            messages.append(_msg("ceo_director", "error", {
                "error": err_msg,
                "traceback": traceback.format_exc()[:500],
            }))

        # Record in decision ledger
        try:
            await self.ledger.record(
                category="portfolio",
                agent_id="ceo_director",
                decision=result.get("decision", f"Fund {len(funded)}, kill {len(killed)}"),
                reasoning=result.get("reasoning", ""),
                assumptions=result.get("assumptions", []),
                risks=result.get("risks", []),
                confidence=result.get("confidence", 0.0),
            )
        except Exception:
            pass

        await event_bus.emit(PORTFOLIO_DECISIONS_MADE, {
            "portfolio_id": state["portfolio_id"],
            "funded": len(funded),
            "killed": len(killed),
            "scaled": len(scaled),
        })

        # WhatsApp notification: CEO decisions
        try:
            await whatsapp_send_portfolio_update(
                phase="CEO Decisions Made",
                cycle=state.get("cycle_count", 0),
                opportunities=len(opportunities),
                funded=len(funded),
                killed=len(killed),
                budget_spent=state.get("budget_spent", 0),
            )
        except Exception as e:
            logger.debug(f"WhatsApp notification skipped: {e}")

        errors = []
        if not funded and not killed and not scaled:
            err = "CEO made no decisions — no initiatives funded, killed, or scaled."
            if result.get("parse_error"):
                err += " (LLM response was not valid JSON)"
            errors.append(err)
            messages.append(_msg("system", "warning", err))

        return {
            "funded_initiatives": funded,
            "killed_initiatives": killed,
            "current_phase": "executing",
            "portfolio_decisions": [{
                "agent": "ceo_director",
                "phase": "portfolio_review",
                "funded": [f.get("title") for f in funded],
                "killed": killed,
                "scaled": scaled,
                "reasoning": result.get("reasoning", ""),
            }],
            "messages": messages,
            "errors": errors,
        }

    # ------------------------------------------------------------------
    # execute_portfolio: run funded initiatives via existing initiative graph
    # ------------------------------------------------------------------

    async def execute_portfolio(self, state: PortfolioState) -> dict:
        """Create and run initiatives sequentially using the existing initiative graph."""
        funded = state.get("funded_initiatives", [])
        killed = state.get("killed_initiatives", [])
        workspace_path = state.get("workspace_path", settings.workspace_path)

        logger.info(f"Executing portfolio: {len(funded)} to fund, {len(killed)} to kill")

        messages = [
            _msg("system", "phase_start", {
                "phase": "executing",
                "funded_count": len(funded),
                "killed_count": len(killed),
                "workspace": workspace_path,
            }),
        ]

        if not funded and not killed:
            messages.append(_msg("system", "info", "Nothing to execute — no initiatives were funded or killed."))

        await event_bus.emit(PORTFOLIO_EXECUTION_STARTED, {
            "portfolio_id": state["portfolio_id"],
            "initiatives_to_run": len(funded),
            "initiatives_to_kill": len(killed),
        })

        results = []

        # Kill marked initiatives
        for init_id in killed:
            try:
                from aeco.db.session import async_session_factory
                from aeco.models.initiative import Initiative, InitiativeStatus, InitiativeVerdict
                async with async_session_factory() as session:
                    initiative = await session.get(Initiative, uuid.UUID(init_id))
                    if initiative and initiative.status != InitiativeStatus.CLOSED.value:
                        initiative.status = InitiativeStatus.CLOSED.value
                        initiative.verdict = InitiativeVerdict.KILL.value
                        await session.commit()
                        logger.info(f"Killed initiative: {initiative.title}")
                        results.append({
                            "title": initiative.title,
                            "action": "killed",
                            "initiative_id": init_id,
                        })
                        messages.append(_msg("system", "initiative_killed", {
                            "title": initiative.title,
                            "id": init_id,
                        }))
            except Exception as e:
                logger.warning(f"Failed to kill initiative {init_id}: {e}")
                messages.append(_msg("system", "error", f"Failed to kill initiative {init_id}: {e}"))

        # Run funded initiatives
        for idx, funded_init in enumerate(funded):
            title = funded_init.get("title", "Untitled")
            goal = funded_init.get("goal", "")
            hypothesis = funded_init.get("hypothesis", "")
            allocated = funded_init.get("allocated_budget", 0)

            messages.append(_msg("system", "initiative_start", {
                "index": idx + 1,
                "total": len(funded),
                "title": title,
                "goal": goal,
                "allocated_budget": allocated,
            }))

            if not self.initiative_graph:
                logger.warning("No initiative graph available; skipping execution")
                results.append({
                    "title": title,
                    "action": "skipped",
                    "reason": "No initiative graph",
                })
                messages.append(_msg("system", "warning", f"Skipped '{title}': no initiative graph available"))
                continue

            # Create initiative in DB
            try:
                from aeco.db.session import async_session_factory
                from aeco.models.initiative import Initiative
                async with async_session_factory() as session:
                    initiative = Initiative(
                        title=title,
                        goal=goal,
                        hypothesis=hypothesis,
                    )
                    session.add(initiative)
                    await session.commit()
                    await session.refresh(initiative)
                    init_id = str(initiative.id)
                    messages.append(_msg("system", "initiative_created", {
                        "id": init_id,
                        "title": title,
                    }))
            except Exception as e:
                logger.error(f"Failed to create initiative '{title}': {e}")
                results.append({"title": title, "action": "failed", "error": str(e)})
                messages.append(_msg("system", "error", f"Failed to create initiative '{title}': {e}"))
                continue

            # Build initial state for initiative graph
            # Include product context so initiative agents know what they're working on
            product_ctx = self._build_product_context(workspace_path)
            from aeco.orchestrator.initiative_state import InitiativeState
            init_state: InitiativeState = {
                "initiative_id": init_id,
                "title": title,
                "goal": goal,
                "hypothesis": hypothesis,
                "workspace_path": workspace_path,
                "project_context": {
                    "product_name": product_ctx.get("product_name", "Unknown"),
                    "product_description": product_ctx.get("product_description", ""),
                    "tech_stack": product_ctx.get("tech_stack", []),
                    "directory_structure": product_ctx.get("directory_structure", "")[:1000],
                },
                "prd": None,
                "design_document": None,
                "security_review": None,
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
                "max_iterations": 2,
                "messages": [],
                "errors": [],
                "budget_spent": 0.0,
                "budget_remaining": allocated,
            }

            timeout = getattr(settings, "initiative_task_timeout_seconds", 600) * 3

            try:
                logger.info(f"Running initiative [{idx+1}/{len(funded)}]: {title}")
                messages.append(_msg("system", "info", f"Executing initiative '{title}'..."))

                final_state = await asyncio.wait_for(
                    self.initiative_graph.ainvoke(init_state),
                    timeout=timeout,
                )

                verdict = final_state.get("verdict", "kill")
                budget_used = final_state.get("budget_spent", 0)

                # Collect sub-messages from initiative
                init_messages = final_state.get("messages", [])
                for m in init_messages[-10:]:
                    messages.append(_msg(
                        m.get("sender", "initiative"),
                        f"initiative:{m.get('type', 'info')}",
                        m.get("content", ""),
                    ))

                # Collect sub-errors
                init_errors = final_state.get("errors", [])
                for e in init_errors:
                    messages.append(_msg("initiative", "error", f"[{title}] {e}"))

                # Update DB
                from aeco.models.initiative import Initiative, InitiativeStatus
                from aeco.db.session import async_session_factory
                async with async_session_factory() as session:
                    db_init = await session.get(Initiative, uuid.UUID(init_id))
                    if db_init and db_init.status != InitiativeStatus.CLOSED.value:
                        db_init.status = InitiativeStatus.CLOSED.value
                        db_init.verdict = verdict
                        db_init.north_star_metric = final_state.get("north_star_metric")
                        await session.commit()

                results.append({
                    "title": title,
                    "initiative_id": init_id,
                    "action": "completed",
                    "verdict": verdict,
                    "budget_spent": budget_used,
                    "tasks_executed": len(final_state.get("execution_results", [])),
                    # Full initiative internals for rich UI
                    "prd": final_state.get("prd"),
                    "design_document": final_state.get("design_document"),
                    "security_review": final_state.get("security_review"),
                    "task_graph": final_state.get("task_graph", []),
                    "execution_details": final_state.get("execution_results", []),
                    "evaluation": final_state.get("evaluation"),
                    "decisions": final_state.get("decisions", []),
                    "north_star_metric": final_state.get("north_star_metric"),
                    "success_threshold": final_state.get("success_threshold"),
                })

                messages.append(_msg("system", "initiative_complete", {
                    "title": title,
                    "verdict": verdict,
                    "budget_spent": budget_used,
                    "tasks_executed": len(final_state.get("execution_results", [])),
                }))
                logger.info(f"Initiative '{title}' completed: verdict={verdict}")

            except asyncio.TimeoutError:
                logger.warning(f"Initiative '{title}' timed out")
                results.append({
                    "title": title,
                    "initiative_id": init_id,
                    "action": "timeout",
                })
                messages.append(_msg("system", "timeout", f"Initiative '{title}' timed out after {timeout}s"))
            except Exception as e:
                logger.error(f"Initiative '{title}' failed: {e}")
                results.append({
                    "title": title,
                    "initiative_id": init_id,
                    "action": "failed",
                    "error": str(e),
                })
                messages.append(_msg("system", "error", {
                    "title": title,
                    "error": str(e),
                    "traceback": traceback.format_exc()[:500],
                }))

        total_spent = sum(r.get("budget_spent", 0) for r in results)

        await event_bus.emit(PORTFOLIO_EXECUTION_COMPLETED, {
            "portfolio_id": state["portfolio_id"],
            "results_count": len(results),
            "total_spent": total_spent,
        })

        messages.append(_msg("system", "phase_complete", {
            "phase": "executing",
            "results_count": len(results),
            "total_spent": total_spent,
        }))

        return {
            "execution_results": results,
            "budget_spent": state.get("budget_spent", 0) + total_spent,
            "budget_remaining": state.get("budget_remaining", 0) - total_spent,
            "current_phase": "evaluating",
            "messages": messages,
        }

    # ------------------------------------------------------------------
    # portfolio_evaluate: aggregate outcomes across initiatives
    # ------------------------------------------------------------------

    async def portfolio_evaluate(self, state: PortfolioState) -> dict:
        logger.info("Evaluating portfolio outcomes")

        results = state.get("execution_results", [])
        completed = [r for r in results if r.get("action") == "completed"]
        scaled = [r for r in completed if r.get("verdict") == "scale"]
        killed_results = [r for r in completed if r.get("verdict") == "kill"]
        iterated = [r for r in completed if r.get("verdict") == "iterate"]
        failed = [r for r in results if r.get("action") in ("failed", "timeout")]

        summary = {
            "total_executed": len(results),
            "completed": len(completed),
            "scaled": len(scaled),
            "killed": len(killed_results),
            "iterated": len(iterated),
            "failed": len(failed),
            "total_budget_spent": state.get("budget_spent", 0),
            "budget_remaining": state.get("budget_remaining", 0),
            "success_rate": len(scaled) / max(len(completed), 1),
        }

        messages = [
            _msg("system", "phase_start", {"phase": "evaluating"}),
            _msg("system", "evaluation_summary", summary),
        ]

        # Log each result
        for r in results:
            messages.append(_msg("system", "result_detail", {
                "title": r.get("title", "?"),
                "action": r.get("action", "?"),
                "verdict": r.get("verdict", ""),
                "budget_spent": r.get("budget_spent", 0),
            }))

        try:
            await self.ledger.record(
                category="portfolio",
                agent_id="system",
                decision=f"Portfolio evaluation: {summary['scaled']} scaled, {summary['killed']} killed",
                reasoning=json.dumps(summary),
                assumptions=[],
                risks=[],
                confidence=1.0,
            )
        except Exception:
            pass

        await event_bus.emit(PORTFOLIO_EVALUATED, {
            "portfolio_id": state["portfolio_id"],
            **summary,
        })

        return {
            "current_phase": "rebalancing",
            "decisions": [{
                "agent": "system",
                "phase": "portfolio_evaluate",
                "summary": summary,
            }],
            "messages": messages,
        }

    # ------------------------------------------------------------------
    # rebalance: decide whether to continue the portfolio loop
    # ------------------------------------------------------------------

    async def rebalance(self, state: PortfolioState) -> dict:
        cycle = state.get("cycle_count", 0) + 1
        max_cycles = state.get("max_cycles", 3)
        budget_remaining = state.get("budget_remaining", 0)

        should_continue = cycle < max_cycles and budget_remaining > 0

        next_phase = "opportunity_scan" if should_continue else "closed"
        logger.info(
            f"Rebalance: cycle {cycle}/{max_cycles}, "
            f"budget remaining ${budget_remaining:.2f}, "
            f"next={next_phase}"
        )

        messages = [
            _msg("system", "rebalance", {
                "cycle": cycle,
                "max_cycles": max_cycles,
                "budget_remaining": budget_remaining,
                "should_continue": should_continue,
                "next_phase": next_phase,
            }),
        ]

        if should_continue:
            messages.append(_msg("system", "info", f"Continuing to cycle {cycle + 1} — ${budget_remaining:.2f} remaining"))
        else:
            reason = "max cycles reached" if cycle >= max_cycles else "budget exhausted"
            messages.append(_msg("system", "info", f"Portfolio loop ending: {reason}"))

        # Refresh active initiatives from DB for next cycle
        active = []
        if should_continue:
            try:
                from aeco.db.session import async_session_factory
                from aeco.models.initiative import Initiative, InitiativeStatus
                from sqlalchemy import select
                async with async_session_factory() as session:
                    result = await session.execute(
                        select(Initiative).where(
                            Initiative.status != InitiativeStatus.CLOSED.value
                        )
                    )
                    for init in result.scalars():
                        active.append({
                            "id": str(init.id),
                            "title": init.title,
                            "status": init.status,
                            "verdict": init.verdict,
                        })
            except Exception as e:
                logger.warning(f"Failed to refresh active initiatives: {e}")

        await event_bus.emit(PORTFOLIO_REBALANCED, {
            "portfolio_id": state["portfolio_id"],
            "cycle": cycle,
            "next_phase": next_phase,
            "budget_remaining": budget_remaining,
        })

        return {
            "cycle_count": cycle,
            "current_phase": next_phase,
            "active_initiatives": active if active else state.get("active_initiatives", []),
            "funded_initiatives": [],
            "killed_initiatives": [],
            "messages": messages,
        }

    # ------------------------------------------------------------------
    # close: finalize the portfolio cycle
    # ------------------------------------------------------------------

    async def close(self, state: PortfolioState) -> dict:
        cycles = state.get("cycle_count", 0)
        spent = state.get("budget_spent", 0)
        results = state.get("execution_results", [])
        goals = state.get("company_goals", [])

        logger.info(
            f"Portfolio closed: {cycles} cycles, ${spent:.2f} spent, "
            f"{len(results)} initiative results"
        )

        messages = [
            _msg("system", "phase_start", {"phase": "closed"}),
            _msg("system", "portfolio_closed", {
                "cycles": cycles,
                "budget_spent": spent,
                "budget_remaining": state.get("budget_remaining", 0),
                "total_results": len(results),
                "goals": goals,
            }),
        ]

        # Summarize each result
        for r in results:
            messages.append(_msg("system", "final_result", {
                "title": r.get("title", "?"),
                "action": r.get("action", "?"),
                "verdict": r.get("verdict", ""),
            }))

        # Collect all errors
        all_errors = state.get("errors", [])
        if all_errors:
            messages.append(_msg("system", "errors_summary", {
                "count": len(all_errors),
                "errors": all_errors,
            }))

        await event_bus.emit(PORTFOLIO_CLOSED, {
            "portfolio_id": state["portfolio_id"],
            "cycles": cycles,
            "budget_spent": spent,
            "results_count": len(results),
        })

        # WhatsApp notification: portfolio complete
        completed = [r for r in results if r.get("action") == "completed"]
        scaled = [r for r in completed if r.get("verdict") == "scale"]
        try:
            await whatsapp_send_alert(
                alert_type="Portfolio Complete",
                severity="info",
                message=(
                    f"Finished {cycles} cycle(s)\n"
                    f"Budget spent: ${spent:.2f}\n"
                    f"Initiatives run: {len(results)}\n"
                    f"Scaled: {len(scaled)}\n"
                    f"Goals: {', '.join(goals)}"
                ),
            )
        except Exception as e:
            logger.debug(f"WhatsApp notification skipped: {e}")

        return {
            "current_phase": "closed",
            "messages": messages,
        }
