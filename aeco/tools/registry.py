"""Register all tools with the gateway and expose LangChain tools for agents."""
from __future__ import annotations

from typing import List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from aeco.models.agent import AgentDefinition
from aeco.tools.budget_tools import budget_read, budget_update
from aeco.tools.metrics_tools import agent_logs_read, metrics_read
from aeco.tools.telemetry_tools import telemetry_ingest, telemetry_query
from aeco.tools.clickup_tools import (
    clickup_create_comment,
    clickup_create_task,
    clickup_read_task,
    clickup_update_task,
)
from aeco.tools.code_tools import code_execute
from aeco.tools.deploy_tools import deploy_preview, deploy_production, deploy_rollback
from aeco.tools.devops_tools import dev_server_start, dev_server_stop, package_install
from aeco.tools.facebook_tools import (
    facebook_create_campaign,
    facebook_create_adset,
    facebook_creative_report,
    facebook_diagnose_cpm,
    facebook_diagnose_zero_conversions,
    facebook_generate_ad_copy,
    facebook_get_account_overview,
    facebook_get_ads,
    facebook_get_adsets,
    facebook_get_campaigns,
    facebook_get_insights,
    facebook_update_adset,
    facebook_update_campaign,
)
from aeco.tools.file_tools import file_read, file_write
from aeco.tools.git_tools import git_branch, git_checkout, git_commit, git_merge, git_push
from aeco.tools.postmortem_tools import capture_page_screenshot, git_workspace_snapshot
from aeco.tools.gateway import ToolGateway
from aeco.tools.stripe_tools import (
    stripe_get_churn,
    stripe_get_customers,
    stripe_get_mrr,
    stripe_get_revenue,
)
from aeco.tools.whatsapp_tools import (
    whatsapp_send_alert,
    whatsapp_send_approval_request,
    whatsapp_send_message,
    whatsapp_send_portfolio_update,
)
from aeco.tools.scaffold_tools import scaffold_list_templates, scaffold_project
from aeco.tools.pattern_tools import pattern_list, pattern_use
from aeco.tools.smoke_tools import smoke_test_api, smoke_test_url
from aeco.tools.auth_tools import auth_add_provider, auth_generate_middleware, auth_setup_supabase
from aeco.tools.email_tools import email_send, email_send_template
from aeco.tools.cicd_tools import cicd_generate
from aeco.tools.browser_tools import (
    browser_click,
    browser_close,
    browser_console_errors,
    browser_fill,
    browser_get_text,
    browser_screenshot,
)


def register_all_tools(gateway: ToolGateway) -> None:
    """Register all AECO tools with the gateway."""
    gateway.register("file_write", file_write, {"workspace:write"})
    gateway.register("file_read", file_read, {"workspace:read"})
    gateway.register("git_workspace_snapshot", git_workspace_snapshot, {"workspace:read"})
    gateway.register("capture_page_screenshot", capture_page_screenshot, {"workspace:write"})
    gateway.register("code_execute", code_execute, {"code:execute"})
    gateway.register("clickup_read_task", clickup_read_task, {"clickup:read"})
    gateway.register("clickup_update_task", clickup_update_task, {"clickup:write"})
    gateway.register("clickup_create_comment", clickup_create_comment, {"clickup:comment"})
    gateway.register("clickup_create_task", clickup_create_task, {"clickup:write"})
    gateway.register("budget_read", budget_read, {"budget:read"})
    gateway.register("budget_update", budget_update, {"budget:write"})
    gateway.register("metrics_read", metrics_read, {"metrics:read"})
    gateway.register("agent_logs_read", agent_logs_read, {"agent_logs:read"})
    # Telemetry
    gateway.register("telemetry_ingest", telemetry_ingest, {"telemetry:write"})
    gateway.register("telemetry_query", telemetry_query, {"telemetry:read"})
    # Facebook/Meta Ads
    gateway.register("facebook_get_campaigns", facebook_get_campaigns, {"facebook:read"})
    gateway.register("facebook_get_adsets", facebook_get_adsets, {"facebook:read"})
    gateway.register("facebook_get_ads", facebook_get_ads, {"facebook:read"})
    gateway.register("facebook_get_insights", facebook_get_insights, {"facebook:read"})
    gateway.register("facebook_get_account_overview", facebook_get_account_overview, {"facebook:read"})
    gateway.register("facebook_diagnose_cpm", facebook_diagnose_cpm, {"facebook:read"})
    gateway.register("facebook_diagnose_zero_conversions", facebook_diagnose_zero_conversions, {"facebook:read"})
    gateway.register("facebook_update_campaign", facebook_update_campaign, {"facebook:write"})
    gateway.register("facebook_update_adset", facebook_update_adset, {"facebook:write"})
    gateway.register("facebook_create_campaign", facebook_create_campaign, {"facebook:write"})
    gateway.register("facebook_create_adset", facebook_create_adset, {"facebook:write"})
    gateway.register("facebook_creative_report", facebook_creative_report, {"facebook:read"})
    gateway.register("facebook_generate_ad_copy", facebook_generate_ad_copy, {"facebook:read"})
    # Stripe
    gateway.register("stripe_get_mrr", stripe_get_mrr, {"stripe:read"})
    gateway.register("stripe_get_revenue", stripe_get_revenue, {"stripe:read"})
    gateway.register("stripe_get_churn", stripe_get_churn, {"stripe:read"})
    gateway.register("stripe_get_customers", stripe_get_customers, {"stripe:read"})
    # WhatsApp
    gateway.register("whatsapp_send_message", whatsapp_send_message, {"whatsapp:send"})
    gateway.register("whatsapp_send_approval_request", whatsapp_send_approval_request, {"whatsapp:send"})
    gateway.register("whatsapp_send_portfolio_update", whatsapp_send_portfolio_update, {"whatsapp:send"})
    gateway.register("whatsapp_send_alert", whatsapp_send_alert, {"whatsapp:send"})
    # Git
    gateway.register("git_commit", git_commit, {"git:write"})
    gateway.register("git_branch", git_branch, {"git:write"})
    gateway.register("git_push", git_push, {"git:push"})
    gateway.register("git_checkout", git_checkout, {"git:write"})
    gateway.register("git_merge", git_merge, {"git:write"})
    # Deploy
    gateway.register("deploy_preview", deploy_preview, {"deploy:write"})
    gateway.register("deploy_production", deploy_production, {"deploy:write"})
    gateway.register("deploy_rollback", deploy_rollback, {"deploy:write"})
    # Package management & dev server
    gateway.register("package_install", package_install, {"devops:execute"})
    gateway.register("dev_server_start", dev_server_start, {"devops:execute"})
    gateway.register("dev_server_stop", dev_server_stop, {"devops:execute"})
    # Scaffold
    gateway.register("scaffold_project", scaffold_project, {"scaffold:write"})
    gateway.register("scaffold_list_templates", scaffold_list_templates, {"scaffold:read"})
    # Patterns
    gateway.register("pattern_list", pattern_list, {"pattern:read"})
    gateway.register("pattern_use", pattern_use, {"pattern:write"})
    # Smoke tests
    gateway.register("smoke_test_url", smoke_test_url, {"smoke:read"})
    gateway.register("smoke_test_api", smoke_test_api, {"smoke:read"})
    # Auth
    gateway.register("auth_setup_supabase", auth_setup_supabase, {"auth:write"})
    gateway.register("auth_add_provider", auth_add_provider, {"auth:write"})
    gateway.register("auth_generate_middleware", auth_generate_middleware, {"auth:write"})
    # Email
    gateway.register("email_send", email_send, {"email:send"})
    gateway.register("email_send_template", email_send_template, {"email:send"})
    # CI/CD
    gateway.register("cicd_generate", cicd_generate, {"cicd:write"})
    # Browser (Playwright)
    gateway.register("browser_screenshot", browser_screenshot, {"browser:read"})
    gateway.register("browser_click", browser_click, {"browser:write"})
    gateway.register("browser_fill", browser_fill, {"browser:write"})
    gateway.register("browser_get_text", browser_get_text, {"browser:read"})
    gateway.register("browser_console_errors", browser_console_errors, {"browser:read"})
    gateway.register("browser_close", browser_close, {"browser:read"})


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

    if "telemetry_query" in allowed:
        class TelemetryQueryArgs(BaseModel):
            metric_name: str = Field(description="Metric to query (e.g. conversion_rate, mrr)")
            product: Optional[str] = Field(default=None, description="Filter by product")
            days: int = Field(default=7, description="Look-back period in days")
            aggregation: str = Field(default="avg", description="One of: avg, sum, count, min, max, latest, trend")
        tools.append(
            make_tool(
                "telemetry_query",
                "Query product telemetry data with aggregations. Use to check real metrics like conversion rates, MRR, error rates.",
                TelemetryQueryArgs,
            )
        )
    if "telemetry_ingest" in allowed:
        class TelemetryIngestArgs(BaseModel):
            metric_name: str = Field(description="Metric name")
            value: float = Field(description="Metric value")
            product: Optional[str] = Field(default=None, description="Product name")
            source: Optional[str] = Field(default=None, description="Data source")
        tools.append(
            make_tool(
                "telemetry_ingest",
                "Record a product metric value. Use for tracking conversion rates, user counts, etc.",
                TelemetryIngestArgs,
            )
        )

    if "git_workspace_snapshot" in allowed:
        class GitSnapshotArgs(BaseModel):
            max_diff_chars: int = Field(
                default=16000,
                description="Max characters of git diff to return (truncates long diffs).",
            )
        tools.append(
            make_tool(
                "git_workspace_snapshot",
                "Get git status, diff --stat, and truncated diff for the initiative workspace. "
                "Use to document exactly what changed on disk.",
                GitSnapshotArgs,
            )
        )

    if "capture_page_screenshot" in allowed:
        class ScreenshotArgs(BaseModel):
            url: str = Field(description="Full http(s) URL to capture (e.g. dashboard or deployed app).")
            relative_path: str = Field(
                description="Where to save the PNG under the workspace, e.g. postmortems/<id>/dashboard.png"
            )
            width: int = Field(default=1280, description="Viewport width in pixels")
            height: int = Field(default=720, description="Viewport height in pixels")
        tools.append(
            make_tool(
                "capture_page_screenshot",
                "Save a viewport screenshot of a web page using headless Chrome/Chromium. "
                "Requires Chrome/Chromium installed. Use for visual evidence of the shipped UI or dashboard.",
                ScreenshotArgs,
            )
        )

    # --- Git tools ---
    if "git_commit" in allowed:
        class GitCommitArgs(BaseModel):
            message: str = Field(description="Commit message describing the change")
            files: Optional[List[str]] = Field(default=None, description="Specific files to stage. Stages all if None.")
        tools.append(
            make_tool(
                "git_commit",
                "Stage files and create a git commit. Use after writing code to version the changes.",
                GitCommitArgs,
            )
        )
    if "git_branch" in allowed:
        class GitBranchArgs(BaseModel):
            branch_name: str = Field(description="Name for the new branch (e.g. 'aeco/initiative-abc123')")
        tools.append(
            make_tool(
                "git_branch",
                "Create and checkout a new git branch. Use at the start of an initiative to isolate work.",
                GitBranchArgs,
            )
        )
    if "git_push" in allowed:
        class GitPushArgs(BaseModel):
            remote: str = Field(default="origin", description="Git remote name")
            branch: Optional[str] = Field(default=None, description="Branch to push (current if None)")
        tools.append(
            make_tool(
                "git_push",
                "Push the current branch to a remote repository.",
                GitPushArgs,
            )
        )
    if "git_checkout" in allowed:
        class GitCheckoutArgs(BaseModel):
            branch: str = Field(description="Branch name to switch to")
        tools.append(
            make_tool(
                "git_checkout",
                "Switch to an existing git branch.",
                GitCheckoutArgs,
            )
        )
    if "git_merge" in allowed:
        class GitMergeArgs(BaseModel):
            source_branch: str = Field(description="Branch to merge into current branch")
        tools.append(
            make_tool(
                "git_merge",
                "Merge a source branch into the current branch. Aborts on conflict.",
                GitMergeArgs,
            )
        )

    # --- Deploy tools ---
    if "deploy_preview" in allowed:
        class DeployPreviewArgs(BaseModel):
            provider: str = Field(default="vercel", description="Hosting provider: 'vercel' or 'netlify'")
        tools.append(
            make_tool(
                "deploy_preview",
                "Deploy the workspace to a preview URL. Returns the preview URL on success.",
                DeployPreviewArgs,
            )
        )
    if "deploy_production" in allowed:
        class DeployProductionArgs(BaseModel):
            provider: str = Field(default="vercel", description="Hosting provider: 'vercel' or 'netlify'")
        tools.append(
            make_tool(
                "deploy_production",
                "Deploy the workspace to production. Use only after QA approval.",
                DeployProductionArgs,
            )
        )
    if "deploy_rollback" in allowed:
        class DeployRollbackArgs(BaseModel):
            provider: str = Field(default="vercel", description="Hosting provider")
        tools.append(
            make_tool(
                "deploy_rollback",
                "Rollback production deployment to the previous version.",
                DeployRollbackArgs,
            )
        )

    # --- DevOps tools ---
    if "package_install" in allowed:
        class PackageInstallArgs(BaseModel):
            manager: Optional[str] = Field(default=None, description="Package manager (npm, pip, etc). Auto-detected if None.")
        tools.append(
            make_tool(
                "package_install",
                "Install project dependencies using the appropriate package manager. Auto-detects npm/pip/yarn.",
                PackageInstallArgs,
            )
        )
    if "dev_server_start" in allowed:
        class DevServerStartArgs(BaseModel):
            command: Optional[str] = Field(default=None, description="Start command (e.g. 'npm run dev'). Auto-detected if None.")
            port: Optional[int] = Field(default=None, description="Expected port number")
        tools.append(
            make_tool(
                "dev_server_start",
                "Start a local dev server in the background for testing. Auto-detects the start command.",
                DevServerStartArgs,
            )
        )
    if "dev_server_stop" in allowed:
        class DevServerStopArgs(BaseModel):
            pass
        tools.append(
            make_tool(
                "dev_server_stop",
                "Stop the running dev server for this workspace.",
                DevServerStopArgs,
            )
        )

    # --- Scaffold tools ---
    if "scaffold_project" in allowed:
        class ScaffoldProjectArgs(BaseModel):
            name: str = Field(description="Project name (e.g. 'headshot-ai')")
            stack: str = Field(default="nextjs-supabase-stripe", description="Template stack to use")
            features: Optional[List[str]] = Field(default=None, description="Feature add-ons: auth, payments, file-upload, ai-generation")
        tools.append(make_tool("scaffold_project", "Generate a full project skeleton from a template with optional features.", ScaffoldProjectArgs))
    if "scaffold_list_templates" in allowed:
        class ScaffoldListArgs(BaseModel):
            pass
        tools.append(make_tool("scaffold_list_templates", "List available project templates, features, and patterns.", ScaffoldListArgs))

    # --- Pattern tools ---
    if "pattern_list" in allowed:
        class PatternListArgs(BaseModel):
            pass
        tools.append(make_tool("pattern_list", "List available reusable UI/API patterns.", PatternListArgs))
    if "pattern_use" in allowed:
        class PatternUseArgs(BaseModel):
            name: str = Field(description="Pattern name (e.g. 'pricing-table', 'hero-section')")
            target_path: str = Field(description="Destination path relative to workspace")
            variables: Optional[dict] = Field(default=None, description="Variable substitutions for the pattern")
        tools.append(make_tool("pattern_use", "Copy a reusable pattern into the project with variable substitution.", PatternUseArgs))

    # --- Smoke test tools ---
    if "smoke_test_url" in allowed:
        class SmokeTestUrlArgs(BaseModel):
            url: str = Field(description="Full URL to test")
            checks: Optional[List[str]] = Field(default=None, description="Checks: status_200, has_content, no_error_page")
            timeout: int = Field(default=30, description="Timeout seconds")
        tools.append(make_tool("smoke_test_url", "Verify a deployed URL is healthy (HTTP 200, has content, no errors).", SmokeTestUrlArgs))
    if "smoke_test_api" in allowed:
        class SmokeTestApiArgs(BaseModel):
            base_url: str = Field(description="Base URL of the API")
            endpoints: Optional[List[dict]] = Field(default=None, description="Endpoints to test: [{path, method, expected_status}]")
        tools.append(make_tool("smoke_test_api", "Test multiple API endpoints for health.", SmokeTestApiArgs))

    # --- Auth tools ---
    if "auth_setup_supabase" in allowed:
        class AuthSetupArgs(BaseModel):
            pass
        tools.append(make_tool("auth_setup_supabase", "Configure Supabase auth files (client, server helpers) in a Next.js project.", AuthSetupArgs))
    if "auth_add_provider" in allowed:
        class AuthProviderArgs(BaseModel):
            provider: str = Field(default="google", description="OAuth provider: google, github, apple")
        tools.append(make_tool("auth_add_provider", "Add an OAuth provider button component.", AuthProviderArgs))
    if "auth_generate_middleware" in allowed:
        class AuthMiddlewareArgs(BaseModel):
            pass
        tools.append(make_tool("auth_generate_middleware", "Generate Next.js middleware for auth session refresh and route protection.", AuthMiddlewareArgs))

    # --- Email tools ---
    if "email_send" in allowed:
        class EmailSendArgs(BaseModel):
            to: str = Field(description="Recipient email")
            subject: str = Field(description="Email subject")
            body: str = Field(description="Email body (HTML)")
        tools.append(make_tool("email_send", "Send a transactional email via Resend.", EmailSendArgs))
    if "email_send_template" in allowed:
        class EmailTemplateArgs(BaseModel):
            to: str = Field(description="Recipient email")
            template: str = Field(description="Template: welcome, receipt, password_reset")
            variables: Optional[dict] = Field(default=None, description="Template variables")
        tools.append(make_tool("email_send_template", "Send a templated transactional email.", EmailTemplateArgs))

    # --- CI/CD tools ---
    if "cicd_generate" in allowed:
        class CicdGenerateArgs(BaseModel):
            provider: str = Field(default="github-actions", description="CI provider")
            deploy_target: str = Field(default="vercel", description="Deploy target: vercel, none")
        tools.append(make_tool("cicd_generate", "Generate CI/CD pipeline config (GitHub Actions + Vercel).", CicdGenerateArgs))

    # --- Browser tools (Playwright) ---
    if "browser_screenshot" in allowed:
        class BrowserScreenshotArgs(BaseModel):
            url: str = Field(description="Full URL to screenshot (e.g. http://localhost:3000)")
            save_path: Optional[str] = Field(default=None, description="Path to save PNG (relative to workspace). If None, returns base64.")
            full_page: bool = Field(default=False, description="Capture full scrollable page")
            wait_for: Optional[str] = Field(default=None, description="CSS selector to wait for before screenshot")
        tools.append(make_tool("browser_screenshot", "Take a screenshot of a web page. Use to see what the app looks like after building/deploying. Returns console errors too.", BrowserScreenshotArgs))
    if "browser_click" in allowed:
        class BrowserClickArgs(BaseModel):
            url: str = Field(description="Page URL to navigate to")
            selector: str = Field(description="CSS selector of element to click (e.g. 'button.submit', '#login-btn')")
            wait_after: float = Field(default=1.0, description="Seconds to wait after click")
        tools.append(make_tool("browser_click", "Navigate to a URL and click an element. Returns screenshot after click.", BrowserClickArgs))
    if "browser_fill" in allowed:
        class BrowserFillArgs(BaseModel):
            url: str = Field(description="Page URL")
            selector: str = Field(description="CSS selector of input (e.g. 'input[name=email]')")
            value: str = Field(description="Value to type into the input")
            submit_selector: Optional[str] = Field(default=None, description="CSS selector of submit button to click after filling")
        tools.append(make_tool("browser_fill", "Fill a form field on a page and optionally submit. Returns screenshot after.", BrowserFillArgs))
    if "browser_get_text" in allowed:
        class BrowserGetTextArgs(BaseModel):
            url: str = Field(description="Page URL")
            selector: Optional[str] = Field(default=None, description="CSS selector of element. If None, returns full page text.")
        tools.append(make_tool("browser_get_text", "Get text content from a page or specific element. Use to read page content without screenshots.", BrowserGetTextArgs))
    if "browser_console_errors" in allowed:
        class BrowserConsoleArgs(BaseModel):
            url: str = Field(description="Page URL to check")
            wait_seconds: float = Field(default=3.0, description="How long to wait for errors to appear")
        tools.append(make_tool("browser_console_errors", "Load a page and collect all console errors and warnings. Essential for debugging runtime issues.", BrowserConsoleArgs))
    if "browser_close" in allowed:
        class BrowserCloseArgs(BaseModel):
            pass
        tools.append(make_tool("browser_close", "Close browser context to free resources.", BrowserCloseArgs))

    return tools
