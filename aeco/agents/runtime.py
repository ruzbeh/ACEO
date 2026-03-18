from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from aeco.agents.response_parser import parse_agent_response
from aeco.integrations.llm.provider import LLMProviderFactory
from aeco.logging.company_logger import (
    log_agent_end,
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
                "Please analyze this and provide your response as a JSON object "
                "according to your output format specification. You may use the provided tools "
                "if they help (e.g. read/write files, run code, update ClickUp). When done, reply with the final JSON only."
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
            result = self._parse_response(response.content if hasattr(response, "content") else str(response))
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
                await self.audit_logger.log(
                    agent_id=self.agent_def.agent_id,
                    action="llm_call",
                    input_summary=context_str[:500],
                    output_summary=str(result)[:500],
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
