from __future__ import annotations

from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from aeco.config import settings
from aeco.integrations.llm.provider import LLMProvider
from aeco.models.agent import LLMConfig


class AnthropicProvider(LLMProvider):
    def __init__(self, config: LLMConfig) -> None:
        super().__init__(config)
        self._model = ChatAnthropic(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_request_timeout,
        )

    def get_chat_model(self) -> BaseChatModel:
        return self._model

    async def invoke(self, messages: list[BaseMessage]) -> Any:
        return await self._model.ainvoke(messages)
