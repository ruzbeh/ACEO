import json
import time
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from aeco.integrations.llm.provider import LLMProviderFactory
from aeco.models.agent import AgentDefinition


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
        start_time = time.monotonic()

        # Build the prompt
        context_str = json.dumps(context, indent=2, default=str)
        messages = [
            SystemMessage(content=self._system_prompt),
            HumanMessage(
                content=f"Here is the current task context:\n\n{context_str}\n\n"
                "Please analyze this and provide your response as a JSON object "
                "according to your output format specification."
            ),
        ]

        # Call LLM
        response = await self.provider.invoke(messages)
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Parse response
        result = self._parse_response(response.content)

        # Audit log
        if self.audit_logger:
            await self.audit_logger.log(
                agent_id=self.agent_def.agent_id,
                action="llm_call",
                input_summary=context_str[:500],
                output_summary=str(result)[:500],
                llm_provider=self.agent_def.llm_config.provider,
                llm_model=self.agent_def.llm_config.model,
                tokens_used=getattr(response, "usage_metadata", {}).get(
                    "total_tokens"
                )
                if hasattr(response, "usage_metadata")
                else None,
                duration_ms=duration_ms,
                success=True,
            )

        return result

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Extract JSON from the LLM response."""
        # Try to find JSON in the response
        text = content.strip()

        # Handle markdown code blocks
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            text = text[start:end].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # If parsing fails, wrap raw text in a result dict
            return {"raw_response": content, "parse_error": True}
