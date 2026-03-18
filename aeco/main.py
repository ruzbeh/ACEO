"""AECO FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from aeco.agents.registry import registry
from aeco.api.routes_agents import router as agents_router
from aeco.api.routes_budget import router as budget_router
from aeco.api.routes_initiatives import router as initiatives_router
from aeco.api.routes_initiatives import set_initiative_graph
from aeco.tools.gateway import tool_gateway
from aeco.tools.registry import register_all_tools
from aeco.api.routes_projects import router as projects_router
from aeco.api.routes_tasks import router as tasks_router
from aeco.api.routes_webhooks import router as webhooks_router
from aeco.api.routes_workflows import router as workflows_router
from aeco.api.routes_workflows import set_graph
from aeco.audit.logger import AuditLogger
from aeco.budget.engine import BudgetEngine
from aeco.config import settings
from aeco.context.builder import ContextBuilder
from aeco.logging.company_logger import init_company_logging
from aeco.db.session import async_session_factory
from aeco.memory.decision_ledger import DecisionLedgerStore
from aeco.memory.store import MemoryStore
from aeco.memory.vector import VectorMemory
from aeco.orchestrator.graph import build_graph
from aeco.orchestrator.initiative_graph import build_initiative_graph
from aeco.tools.budget_tools import set_budget_engine


def _setup_logging() -> None:
    """Send AECO logs to console and optionally to a log file."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    aeco_logger = logging.getLogger("aeco")
    aeco_logger.setLevel(level)
    aeco_logger.propagate = False

    # Console
    if not any(getattr(h, "stream", None) == sys.stdout for h in aeco_logger.handlers):
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        aeco_logger.addHandler(ch)

    # File (when log_path is set and non-empty)
    if settings.log_path and settings.log_path.strip():
        log_file = Path(settings.log_path.strip())
        log_file.parent.mkdir(parents=True, exist_ok=True)
        if not any(
            getattr(h, "baseFilename", None) == str(log_file.resolve())
            for h in aeco_logger.handlers
            if isinstance(h, logging.FileHandler)
        ):
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(formatter)
            aeco_logger.addHandler(fh)


_setup_logging()
logger = logging.getLogger(__name__)


async def _mark_stale_runs_failed() -> None:
    """Mark any workflow runs still 'running' as failed (e.g. after server restart)."""
    from sqlalchemy import select

    from aeco.models.task import Task, TaskStatus
    from aeco.models.workflow import WorkflowRun

    async with async_session_factory() as session:
        result = await session.execute(
            select(WorkflowRun).where(WorkflowRun.status == "running")
        )
        runs = result.scalars().all()
        for run in runs:
            run.status = "failed"
            run.current_node = "failed"
            run.state_snapshot = {"error": "Server restarted; run abandoned."}
            task = await session.get(Task, run.task_id)
            if task:
                task.status = TaskStatus.BLOCKED
        if runs:
            await session.commit()
            logger.info("Marked %s stale workflow run(s) as failed (server restarted)", len(runs))


async def _mark_stale_portfolios_failed() -> None:
    """Mark any portfolio cycles still 'running' as failed (e.g. after server restart)."""
    try:
        from sqlalchemy import select
        from aeco.models.portfolio_cycle import PortfolioCycle
        from datetime import datetime, timezone
        async with async_session_factory() as session:
            result = await session.execute(
                select(PortfolioCycle).where(PortfolioCycle.status == "running")
            )
            cycles = result.scalars().all()
            for c in cycles:
                c.status = "failed"
                c.current_phase = "failed"
                c.completed_at = datetime.now(timezone.utc)
            if cycles:
                await session.commit()
                logger.info("Marked %s stale portfolio cycle(s) as failed (server restarted)", len(cycles))
    except Exception as e:
        logger.debug(f"Stale portfolio cleanup skipped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the system on startup."""
    logger.info("Starting AECO...")
    await _mark_stale_runs_failed()
    await _mark_stale_portfolios_failed()

    # Register tools and load agent definitions
    register_all_tools(tool_gateway)
    agents_yaml = Path("aeco/agents/definitions/v1_agents.yaml")
    if agents_yaml.exists():
        registry.load_from_yaml(agents_yaml)
        logger.info(f"Loaded {len(registry.list_agents())} agents")
    else:
        logger.warning(f"Agent definitions not found at {agents_yaml}")

    # Create workspace directory
    Path(settings.workspace_path).mkdir(parents=True, exist_ok=True)

    # Structured company logging (workflow / agent / tool)
    init_company_logging(
        log_path=settings.company_log_path,
        console=settings.company_log_console,
    )

    # Vector memory for artifact ingestion and retrieval
    vector_memory = VectorMemory(
        host=settings.chroma_host,
        port=settings.chroma_port,
    )
    # Budget engine for cost governance
    budget_engine = BudgetEngine(async_session_factory)
    set_budget_engine(budget_engine)
    logger.info("Budget engine initialized")

    # Build and register the task-level workflow graph
    audit_logger = AuditLogger(async_session_factory)
    compiled_graph = build_graph(registry, audit_logger, vector_memory, budget_engine)
    set_graph(compiled_graph)
    logger.info("Task workflow graph compiled")

    # Build and register the initiative-level workflow graph
    memory_store = MemoryStore(async_session_factory)
    decision_ledger = DecisionLedgerStore(async_session_factory)
    context_builder = ContextBuilder(
        vector_memory=vector_memory,
        memory_store=memory_store,
        decision_ledger=decision_ledger,
    )
    initiative_graph = build_initiative_graph(
        registry=registry,
        audit_logger=audit_logger,
        context_builder=context_builder,
        decision_ledger=decision_ledger,
        budget_engine=budget_engine,
    )
    set_initiative_graph(initiative_graph)
    logger.info("Initiative workflow graph compiled")

    # Build and register the portfolio-level workflow graph
    from aeco.orchestrator.portfolio_graph import build_portfolio_graph
    from aeco.api.routes_portfolio import set_portfolio_graph

    portfolio_graph = build_portfolio_graph(
        registry=registry,
        audit_logger=audit_logger,
        context_builder=context_builder,
        decision_ledger=decision_ledger,
        budget_engine=budget_engine,
        initiative_graph=initiative_graph,
    )
    set_portfolio_graph(portfolio_graph)
    logger.info("Portfolio workflow graph compiled")

    yield

    logger.info("AECO shutting down")


app = FastAPI(
    title="AECO - Agentic Engineering Company OS",
    version="0.1.0",
    description="Multi-agent system for autonomous software engineering",
    lifespan=lifespan,
)

# CORS for dashboard dev server
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(tasks_router)
app.include_router(workflows_router)
app.include_router(agents_router)
app.include_router(webhooks_router)
app.include_router(projects_router)
app.include_router(budget_router)
app.include_router(initiatives_router)

# Portfolio orchestration
from aeco.api.routes_portfolio import router as portfolio_router
app.include_router(portfolio_router)

# WebSocket for real-time events
from aeco.api.routes_ws import router as ws_router
app.include_router(ws_router)

# Dashboard (static SPA) — prefer dashboard/dist/ build output, fallback to static/dashboard/
_project_root = Path(__file__).resolve().parent.parent
_dashboard_path = _project_root / "dashboard" / "dist"
if not _dashboard_path.exists():
    _dashboard_path = _project_root / "static" / "dashboard"
if _dashboard_path.exists():
    app.mount("/dashboard", StaticFiles(directory=str(_dashboard_path), html=True), name="dashboard")


@app.get("/")
async def root():
    """Redirect to dashboard."""
    return RedirectResponse(url="/dashboard/", status_code=302)


@app.get("/health")
@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
