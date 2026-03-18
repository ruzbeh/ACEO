"""Register all tools with the gateway and expose LangChain tools for agents."""
from __future__ import annotations

from typing import List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from aeco.models.agent import AgentDefinition
from aeco.tools.budget_tools import budget_read, budget_update
from aeco.tools.metrics_tools import agent_logs_read, metrics_read
from aeco.tools.clickup_tools import (
    clickup_create_comment,
    clickup_create_task,
    clickup_read_task,
    clickup_update_task,
)
from aeco.tools.code_tools import code_execute
from aeco.tools.facebook_tools import (
    facebook_create_campaign,
    facebook_get_campaigns,
    facebook_get_insights,
    facebook_update_campaign,
)
from aeco.tools.file_tools import file_read, file_write
from aeco.tools.gateway import ToolGateway
from aeco.tools.stripe_tools import (
    stripe_get_churn,
    stripe_get_customers,
    stripe_get_mrr,
    stripe_get_revenue,
)


def register_all_tools(gateway: ToolGateway) -> None:
    """Register all AECO tools with the gateway."""
    gateway.register("file_write", file_write, {"workspace:write"})
    gateway.register("file_read", file_read, {"workspace:read"})
    gateway.register("code_execute", code_execute, {"code:execute"})
    gateway.register("clickup_read_task", clickup_read_task, {"clickup:read"})
    gateway.register("clickup_update_task", clickup_update_task, {"clickup:write"})
    gateway.register("clickup_create_comment", clickup_create_comment, {"clickup:comment"})
    gateway.register("clickup_create_task", clickup_create_task, {"clickup:write"})
    gateway.register("budget_read", budget_read, {"budget:read"})
    gateway.register("budget_update", budget_update, {"budget:write"})
    gateway.register("metrics_read", metrics_read, {"metrics:read"})
    gateway.register("agent_logs_read", agent_logs_read, {"agent_logs:read"})
    # Facebook/Meta Ads
    gateway.register("facebook_get_campaigns", facebook_get_campaigns, {"facebook:read"})
    gateway.register("facebook_get_insights", facebook_get_insights, {"facebook:read"})
    gateway.register("facebook_update_campaign", facebook_update_campaign, {"facebook:write"})
    gateway.register("facebook_create_campaign", facebook_create_campaign, {"facebook:write"})
    # Stripe
    gateway.register("stripe_get_mrr", stripe_get_mrr, {"stripe:read"})
    gateway.register("stripe_get_revenue", stripe_get_revenue, {"stripe:read"})
    gateway.register("stripe_get_churn", stripe_get_churn, {"stripe:read"})
    gateway.register("stripe_get_customers", stripe_get_customers, {"stripe:read"})


def get_langchain_tools(
    agent_def: AgentDefinition, gateway: ToolGateway
) -> List[StructuredTool]:
    """Build LangChain StructuredTools for an agent (only tools they're allowed to use)."""
    allowed = gateway.get_tools_for_agent(agent_def)
    agent_perms = set(agent_def.permissions)
    tools = []

    def make_tool(name: str, description: str, args_schema: type[BaseModel]):
        async def run(**kwargs):
            return await gateway.execute(
                name, agent_def.agent_id, agent_perms, **kwargs
            )
        return StructuredTool.from_function(
            coroutine=run,
            name=name,
            description=description,
            args_schema=args_schema,
        )

    if "file_write" in allowed:
        class FileWriteArgs(BaseModel):
            path: str = Field(description="Relative path within workspace")
            content: str = Field(description="File content to write")
        tools.append(
            make_tool(
                "file_write",
                "Write content to a file in the workspace. Use for creating or overwriting code/docs.",
                FileWriteArgs,
            )
        )
    if "file_read" in allowed:
        class FileReadArgs(BaseModel):
            path: str = Field(description="Relative path within workspace")
        tools.append(
            make_tool(
                "file_read",
                "Read a file from the workspace. Use to read existing code or design docs.",
                FileReadArgs,
            )
        )
    if "code_execute" in allowed:
        class CodeExecuteArgs(BaseModel):
            code: str = Field(description="Python code to run (e.g. tests)")
            timeout: int = Field(default=30, description="Timeout in seconds")
            workspace_path: Optional[str] = Field(
                default=None,
                description="Workspace root path to run code in; use when task context provides one.",
            )
        tools.append(
            make_tool(
                "code_execute",
                "Execute Python code in the workspace. Use for running tests or scripts. Pass workspace_path from context when available.",
                CodeExecuteArgs,
            )
        )
    if "clickup_read_task" in allowed:
        class ClickUpReadTaskArgs(BaseModel):
            task_id: str = Field(description="ClickUp task ID")
        tools.append(
            make_tool(
                "clickup_read_task",
                "Get details of a ClickUp task.",
                ClickUpReadTaskArgs,
            )
        )
    if "clickup_update_task" in allowed:
        class ClickUpUpdateTaskArgs(BaseModel):
            task_id: str = Field(description="ClickUp task ID")
            status: Optional[str] = Field(default=None, description="New status")
            name: Optional[str] = Field(default=None, description="New name")
            description: Optional[str] = Field(default=None, description="New description")
        tools.append(
            make_tool(
                "clickup_update_task",
                "Update a ClickUp task's status, name, or description.",
                ClickUpUpdateTaskArgs,
            )
        )
    if "clickup_create_comment" in allowed:
        class ClickUpCreateCommentArgs(BaseModel):
            task_id: str = Field(description="ClickUp task ID")
            comment_text: str = Field(description="Comment body (markdown supported)")
        tools.append(
            make_tool(
                "clickup_create_comment",
                "Post a comment on a ClickUp task.",
                ClickUpCreateCommentArgs,
            )
        )
    if "clickup_create_task" in allowed:
        class ClickUpCreateTaskArgs(BaseModel):
            name: str = Field(description="Task name")
            description: str = Field(default="", description="Task description")
        tools.append(
            make_tool(
                "clickup_create_task",
                "Create a new task in the default ClickUp list.",
                ClickUpCreateTaskArgs,
            )
        )

    if "budget_read" in allowed:
        class BudgetReadArgs(BaseModel):
            scope: str = Field(default="global", description="Budget scope: global, project, or agent")
            scope_id: Optional[str] = Field(default=None, description="Scope identifier (project name or agent_id)")
        tools.append(
            make_tool(
                "budget_read",
                "Read the current budget status with spend breakdown, alerts, and utilization. Use to check remaining budget before expensive operations.",
                BudgetReadArgs,
            )
        )
    if "budget_update" in allowed:
        class BudgetUpdateArgs(BaseModel):
            agent_id: str = Field(description="Agent requesting the spend")
            amount: float = Field(description="USD amount to spend")
            category: str = Field(default="llm_tokens", description="Spend category: llm_tokens, compute, api_calls, storage, tooling, other")
            description: str = Field(default="", description="What this spend is for")
            workflow_run_id: Optional[str] = Field(default=None, description="Associated workflow run ID")
            task_id: Optional[str] = Field(default=None, description="Associated task ID")
            tokens_used: Optional[int] = Field(default=None, description="LLM tokens consumed")
            llm_model: Optional[str] = Field(default=None, description="LLM model used")
        tools.append(
            make_tool(
                "budget_update",
                "Submit a spend request for approval. Returns approval decision with warnings and optimization hints.",
                BudgetUpdateArgs,
            )
        )

    if "metrics_read" in allowed:
        class MetricsReadArgs(BaseModel):
            metric_type: str = Field(default="agent_performance", description="One of: agent_performance, workflow_stats, cost_summary, error_rates")
            agent_id: Optional[str] = Field(default=None, description="Filter by agent ID")
            workflow_run_id: Optional[str] = Field(default=None, description="Filter by workflow run ID")
            limit: int = Field(default=50, description="Max records")
        tools.append(
            make_tool(
                "metrics_read",
                "Read system metrics: agent performance, workflow stats, cost summaries, error rates.",
                MetricsReadArgs,
            )
        )
    if "agent_logs_read" in allowed:
        class AgentLogsReadArgs(BaseModel):
            agent_id: Optional[str] = Field(default=None, description="Filter by agent ID")
            action: Optional[str] = Field(default=None, description="Filter by action type (e.g. llm_call)")
            success: Optional[bool] = Field(default=None, description="Filter by success/failure")
            limit: int = Field(default=50, description="Max records")
        tools.append(
            make_tool(
                "agent_logs_read",
                "Read agent execution logs: token usage, duration, outcomes, errors.",
                AgentLogsReadArgs,
            )
        )

    return tools
