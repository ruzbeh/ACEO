"""AECO FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from aeco.agents.registry import registry
from aeco.api.routes_agents import router as agents_router
from aeco.api.routes_tasks import router as tasks_router
from aeco.api.routes_webhooks import router as webhooks_router
from aeco.api.routes_workflows import router as workflows_router
from aeco.api.routes_workflows import set_graph
from aeco.audit.logger import AuditLogger
from aeco.config import settings
from aeco.db.session import async_session_factory
from aeco.orchestrator.graph import build_graph

logging.basicConfig(level=getattr(logging, settings.log_level))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the system on startup."""
    logger.info("Starting AECO...")

    # Load agent definitions
    agents_yaml = Path("aeco/agents/definitions/v1_agents.yaml")
    if agents_yaml.exists():
        registry.load_from_yaml(agents_yaml)
        logger.info(f"Loaded {len(registry.list_agents())} agents")
    else:
        logger.warning(f"Agent definitions not found at {agents_yaml}")

    # Create workspace directory
    Path(settings.workspace_path).mkdir(parents=True, exist_ok=True)

    # Build and register the workflow graph
    audit_logger = AuditLogger(async_session_factory)
    compiled_graph = build_graph(registry, audit_logger)
    set_graph(compiled_graph)
    logger.info("Workflow graph compiled")

    yield

    logger.info("AECO shutting down")


app = FastAPI(
    title="AECO - Agentic Engineering Company OS",
    version="0.1.0",
    description="Multi-agent system for autonomous software engineering",
    lifespan=lifespan,
)

app.include_router(tasks_router)
app.include_router(workflows_router)
app.include_router(agents_router)
app.include_router(webhooks_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
