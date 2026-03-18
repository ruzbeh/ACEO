"""Execute AECO agents via the Claude Code CLI subprocess."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aeco.agents.response_parser import parse_agent_response
from aeco.config import settings
from aeco.logging.company_logger import log_agent_end, log_agent_start
from aeco.models.agent import AgentDefinition

logger = logging.getLogger(__name__)

# Map AECO permissions to Claude Code tool names
_PERMISSION_TO_TOOLS: dict[str, list[str]] = {
    "workspace:write": ["Write", "Edit"],
    "workspace:read": ["Read", "Glob", "Grep"],
    "code:execute": ["Bash"],
}

# Base tools every agent gets (read-only exploration)
_BASE_TOOLS = ["Read", "Glob", "Grep"]


@dataclass
class ExecutionMeta:
    """Metadata from a Claude Code CLI execution."""
    cost_usd: float = 0.0
    duration_ms: int = 0
    num_turns: int = 0
    session_id: str = ""


class ClaudeCodeExecutor:
    """Executes an agent by shelling out to the Claude Code CLI.

    The CLI is invoked in non-interactive mode with --output-format json.
    The agent's system prompt is passed via --append-system-prompt,
    and the context is piped via stdin to avoid argument length limits.
    """

    def __init__(self, agent_def: AgentDefinition, audit_logger: Any = None) -> None:
        self.agent_def = agent_def
        self.audit_logger = audit_logger
        self._system_prompt = self._load_system_prompt()
        self.last_meta = ExecutionMeta()

    def _load_system_prompt(self) -> str:
        path = Path(self.agent_def.system_prompt_path)
        if not path.exists():
            raise FileNotFoundError(
                f"System prompt not found: {path} for agent {self.agent_def.agent_id}"
            )
        return path.read_text()

    def _resolve_allowed_tools(self) -> list[str]:
        """Map agent permissions to Claude Code tool names."""
        cfg = self.agent_def.claude_code_config
        if cfg and cfg.allowed_tools:
            return cfg.allowed_tools

        tools = set(_BASE_TOOLS)
        for perm in self.agent_def.permissions:
            mapped = _PERMISSION_TO_TOOLS.get(perm, [])
            tools.update(mapped)
        return sorted(tools)

    def _build_prompt(self, context: dict[str, Any]) -> str:
        """Build the user prompt sent to Claude Code via stdin."""
        context_str = json.dumps(context, indent=2, default=str)
        workspace = context.get("workspace_path", "")

        return (
            f"Here is the current task context:\n\n{context_str}\n\n"
            f"You are the {self.agent_def.name} ({self.agent_def.role}) agent in the AECO system.\n"
            + (f"You are working in the directory: {workspace}\n" if workspace else "")
            + "Use the available tools to read existing files, write new files, and execute code as needed.\n\n"
            "When you are finished, output your final response as a single JSON object "
            "according to your output format specification. The JSON must include at minimum: "
            "decision, assumptions, risks, confidence. Include code_artifacts if you wrote files."
        )

    def _build_command(self, context: dict[str, Any]) -> list[str]:
        """Build the claude CLI command."""
        binary = settings.claude_code_binary
        cfg = self.agent_def.claude_code_config

        max_turns = cfg.max_turns if cfg else 10
        allowed_tools = self._resolve_allowed_tools()

        cmd = [
            binary,
            "-p",
            "--output-format", "json",
            "--max-turns", str(max_turns),
            "--verbose",
        ]

        # Append the agent's system prompt
        cmd.extend(["--append-system-prompt", self._system_prompt])

        # Restrict tools
        if allowed_tools:
            cmd.extend(["--allowedTools", ",".join(allowed_tools)])

        # Model override
        model = (cfg.model if cfg else None) or None
        if model:
            cmd.extend(["--model", model])

        return cmd

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent via Claude Code CLI and return parsed response."""
        run_id = context.get("workflow_run_id")
        task_id = context.get("task_id")
        context_keys = [
            k for k in context.keys()
            if k not in ("relevant_past_work", "project_context", "existing_messages", "recent_messages")
        ]
        log_agent_start(
            agent_id=self.agent_def.agent_id,
            task_id=task_id,
            run_id=run_id,
            context_keys=context_keys,
        )

        start_time = time.monotonic()
        cmd = self._build_command(context)
        prompt = self._build_prompt(context)
        workspace_raw = context.get("workspace_path", "") or settings.workspace_path
        workspace = str(Path(workspace_raw).expanduser().resolve()) if workspace_raw else ""

        if workspace and not Path(workspace).is_dir():
            raise FileNotFoundError(
                f"Workspace path does not exist or is not a directory: {workspace}. "
                "Use an absolute path to an existing project or create the directory."
            )

        cfg = self.agent_def.claude_code_config
        timeout = (cfg.timeout_seconds if cfg else None) or settings.claude_code_default_timeout

        logger.info(
            f"ClaudeCode: executing {self.agent_def.agent_id} "
            f"(max_turns={cfg.max_turns if cfg else 10}, timeout={timeout}s, "
            f"tools={self._resolve_allowed_tools()})"
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace or None,
            )
        except FileNotFoundError:
            logger.warning(
                "Claude Code CLI not found (%s); falling back to LangChain executor for %s",
                settings.claude_code_binary,
                self.agent_def.agent_id,
            )
            from aeco.agents.runtime import AgentRuntime
            fallback = AgentRuntime(self.agent_def, self.audit_logger)
            return await fallback.execute(context)

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=prompt.encode()),
                timeout=timeout,
            )

            stdout = stdout_bytes.decode(errors="replace")
            stderr = stderr_bytes.decode(errors="replace")

            if proc.returncode != 0:
                logger.error(
                    f"ClaudeCode process exited with code {proc.returncode}: {stderr[:500]}"
                )
                raise RuntimeError(
                    f"Claude Code CLI failed (exit {proc.returncode}): {stderr[:500]}"
                )

            # Parse the CLI JSON envelope
            envelope = json.loads(stdout)
            is_error = envelope.get("is_error", False)
            result_text = envelope.get("result", "")

            self.last_meta = ExecutionMeta(
                cost_usd=envelope.get("cost_usd", 0.0),
                duration_ms=envelope.get("duration_ms", 0),
                num_turns=envelope.get("num_turns", 0),
                session_id=envelope.get("session_id", ""),
            )

            if is_error:
                raise RuntimeError(f"Claude Code returned error: {result_text[:500]}")

            # Parse the agent's structured JSON from the result text
            result = parse_agent_response(result_text)

            duration_ms = int((time.monotonic() - start_time) * 1000)

            log_agent_end(
                agent_id=self.agent_def.agent_id,
                task_id=task_id,
                run_id=run_id,
                duration_ms=duration_ms,
                success=True,
                tokens_used=None,
                output_summary=str(result)[:300],
            )

            if self.audit_logger:
                await self.audit_logger.log(
                    agent_id=self.agent_def.agent_id,
                    action="claude_code_call",
                    input_summary=prompt[:500],
                    output_summary=str(result)[:500],
                    llm_provider="claude_code",
                    llm_model=self.agent_def.claude_code_config.model if self.agent_def.claude_code_config else "default",
                    tokens_used=None,
                    duration_ms=duration_ms,
                    success=True,
                    extra={
                        "cost_usd": self.last_meta.cost_usd,
                        "num_turns": self.last_meta.num_turns,
                        "session_id": self.last_meta.session_id,
                    },
                )

            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log_agent_end(
                agent_id=self.agent_def.agent_id,
                task_id=task_id,
                run_id=run_id,
                duration_ms=duration_ms,
                success=False,
                error=f"Timeout after {timeout}s",
            )
            raise TimeoutError(
                f"Claude Code execution timed out after {timeout}s "
                f"for agent {self.agent_def.agent_id}"
            )

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            log_agent_end(
                agent_id=self.agent_def.agent_id,
                task_id=task_id,
                run_id=run_id,
                duration_ms=duration_ms,
                success=False,
                error=str(e),
            )
            raise
