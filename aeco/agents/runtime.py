from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from aeco.agents.response_parser import (
    extract_code_artifacts_from_text,
    parse_agent_response,
)
from aeco.integrations.llm.provider import LLMProviderFactory
from aeco.logging.company_logger import (
    log_agent_end,
    log_agent_parse_result,
    log_agent_start,
    log_agent_tool_round,
)
from aeco.models.agent import AgentDefinition
from aeco.tools.gateway import tool_gateway
from aeco.tools.registry import get_langchain_tools


class AgentRuntime:
    """Executes a single agent: loads prompt, calls LLM, returns structured output."""

    def __init__(self, agent_def: AgentDefinition, audit_logger: Any = None) -> None:
        self.agent_def = agent_def
        self.audit_logger = audit_logger
        self.provider = LLMProviderFactory.create(agent_def.llm_config)
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        path = Path(self.agent_def.system_prompt_path)
        if not path.exists():
            raise FileNotFoundError(
                f"System prompt not found: {path} for agent {self.agent_def.agent_id}"
            )
        return path.read_text()

    async def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent with the given context and return parsed response."""
        run_id = context.get("workflow_run_id")
        task_id = context.get("task_id")
        context_keys = [k for k in context.keys() if k not in ("relevant_past_work", "project_context", "existing_messages", "recent_messages")]
        log_agent_start(
            agent_id=self.agent_def.agent_id,
            task_id=task_id,
            run_id=run_id,
            context_keys=context_keys,
        )

        start_time = time.monotonic()
        context_str = json.dumps(context, indent=2, default=str)
        messages: list[Any] = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(
                content=f"Here is the current task context:\n\n{context_str}\n\n"
                "IMPORTANT — Output format: Reply with exactly one JSON object inside a code block. "
                "Use double quotes for strings, no trailing commas, no comments. "
                "Example: ```json\n{\"key\": \"value\"}\n``` "
                "You may use the provided tools if they help (e.g. read/write files, run code, update ClickUp). "
                "If you used tools, you must still end your reply with a single ```json ... ``` block. When done, output ONLY that block; no other text before or after."
            ),
        ]

        langchain_tools = get_langchain_tools(self.agent_def, tool_gateway)
        model = self.provider.get_chat_model()
        max_tool_rounds = 10
        response = None

        try:
            if langchain_tools:
                bound = model.bind_tools(langchain_tools)
                for round_index in range(max_tool_rounds):
                    response = await bound.ainvoke(messages)
                    tool_calls = getattr(response, "tool_calls", None) or []
                    if not tool_calls:
                        break
                    agent_perms = set(self.agent_def.permissions)
                    tool_messages = []
                    for tc in tool_calls:
                        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                        if not isinstance(args, dict):
                            args = {}
                        tc_id = (tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", None)) or ""
                        if not name:
                            continue
                        try:
                            result = await tool_gateway.execute(
                                name, self.agent_def.agent_id, agent_perms, **args
                            )
                            content = json.dumps(result, default=str)
                            log_agent_tool_round(
                                agent_id=self.agent_def.agent_id,
                                task_id=task_id,
                                run_id=run_id,
                                tool_name=name,
                                round_index=round_index,
                                success=True,
                            )
                        except Exception as e:
                            content = json.dumps({"error": str(e)})
                            log_agent_tool_round(
                                agent_id=self.agent_def.agent_id,
                                task_id=task_id,
                                run_id=run_id,
                                tool_name=name,
                                round_index=round_index,
                                success=False,
                                error=str(e),
                            )
                        tool_messages.append(
                            ToolMessage(tool_call_id=tc_id, content=content)
                        )
                    messages = [*messages, response, *tool_messages]
            else:
                response = await self.provider.invoke(messages)

            if response is None:
                response = await self.provider.invoke(messages)
            duration_ms = int((time.monotonic() - start_time) * 1000)
            raw_content = response.content if hasattr(response, "content") else str(response)
            if not isinstance(raw_content, str):
                raw_content = str(raw_content) if raw_content else ""
            result = self._parse_response(raw_content)

            # On parse failure: retry once with a focused JSON-only prompt
            if result.get("parse_error"):
                import logging as _log
                _log.getLogger(__name__).warning(
                    "[%s] LLM response did not parse as JSON (%d chars). Retrying with JSON-only prompt...",
                    self.agent_def.agent_id,
                    len(raw_content),
                )
                retry_messages = [
                    SystemMessage(content=self._system_prompt),
                    HumanMessage(content=(
                        "Your previous response could not be parsed as JSON. "
                        "Here is what you said:\n\n"
                        f"{raw_content[:3000]}\n\n"
                        "Please reformat your answer as ONLY a JSON object inside ```json ... ``` markers. "
                        "No other text before or after. Just the JSON block."
                    )),
                ]
                try:
                    retry_response = await self.provider.invoke(retry_messages)
                    retry_content = retry_response.content if hasattr(retry_response, "content") else str(retry_response)
                    if not isinstance(retry_content, str):
                        retry_content = str(retry_content) if retry_content else ""
                    retry_result = self._parse_response(retry_content)
                    if not retry_result.get("parse_error"):
                        _log.getLogger(__name__).info(
                            "[%s] Retry succeeded — got valid JSON on second attempt.",
                            self.agent_def.agent_id,
                        )
                        result = retry_result
                        raw_content = retry_content
                except Exception as retry_err:
                    _log.getLogger(__name__).warning(
                        "[%s] Retry also failed: %s", self.agent_def.agent_id, retry_err
                    )

            # If still a parse failure after retry: build fallback but KEEP parse_error flag
            if result.get("parse_error"):
                import logging as _log
                _log.getLogger(__name__).error(
                    "[%s] PARSE FAILED after retry (%d chars). Raw preview:\n%s",
                    self.agent_def.agent_id,
                    len(raw_content),
                    raw_content[:1500],
                )
                code_artifacts = extract_code_artifacts_from_text(
                    result.get("raw_response") or raw_content
                )
                summary = (result.get("raw_response") or raw_content or "").strip()[:500]
                result = {
                    "parse_error": True,
                    "raw_response": raw_content[:2000],
                    "decision": summary or "Task completed; no valid JSON summary returned.",
                    "code_artifacts": code_artifacts,
                    "assumptions": [],
                    "risks": [],
                    "confidence": 0.5,
                }
                log_agent_parse_result(
                    agent_id=self.agent_def.agent_id,
                    parse_ok=False,
                    raw_length=len(raw_content),
                    used_fallback=True,
                    task_id=task_id,
                    run_id=run_id,
                )
            else:
                log_agent_parse_result(
                    agent_id=self.agent_def.agent_id,
                    parse_ok=True,
                    raw_length=len(raw_content),
                    used_fallback=False,
                    task_id=task_id,
                    run_id=run_id,
                )
            um = getattr(response, "usage_metadata", None)
            tokens = um.get("total_tokens") if isinstance(um, dict) else getattr(um, "total_tokens", None)

            log_agent_end(
                agent_id=self.agent_def.agent_id,
                task_id=task_id,
                run_id=run_id,
                duration_ms=duration_ms,
                success=True,
                tokens_used=tokens,
                output_summary=str(result)[:300],
            )

            # Audit log
            if self.audit_logger:
                _run_id = run_id
                _task_id = task_id
                _init_id = context.get("initiative_id")
                if isinstance(_run_id, str) and _run_id:
                    try:
                        _run_id = uuid.UUID(_run_id)
                    except ValueError:
                        _run_id = None
                if isinstance(_task_id, str) and _task_id:
                    try:
                        _task_id = uuid.UUID(_task_id)
                    except ValueError:
                        _task_id = None
                if isinstance(_init_id, str) and _init_id:
                    try:
                        _init_id = uuid.UUID(_init_id)
                    except ValueError:
                        _init_id = None
                await self.audit_logger.log(
                    agent_id=self.agent_def.agent_id,
                    action="llm_call",
                    input_summary=context_str[:500],
                    output_summary=str(result)[:500],
                    workflow_run_id=_run_id,
                    task_id=_task_id,
                    initiative_id=_init_id,
                    llm_provider=self.agent_def.llm_config.provider,
                    llm_model=self.agent_def.llm_config.model,
                    tokens_used=tokens,
                    duration_ms=duration_ms,
                    success=True,
                )

            return result

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

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Extract JSON from the LLM response, handling various formats robustly."""
        return parse_agent_response(content)
