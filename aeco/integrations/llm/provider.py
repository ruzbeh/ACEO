from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage

from aeco.models.agent import LLMConfig


class LLMProvider(ABC):
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    def get_chat_model(self) -> BaseChatModel:
        """Return a LangChain chat model instance."""

    @abstractmethod
    async def invoke(self, messages: list[BaseMessage]) -> Any:
        """Invoke the LLM with messages."""


class LLMProviderFactory:
    @staticmethod
    def create(config: LLMConfig) -> LLMProvider:
        match config.provider:
            case "anthropic":
                from aeco.integrations.llm.anthropic import AnthropicProvider

                return AnthropicProvider(config)
            case "openai":
                from aeco.integrations.llm.openai import OpenAIProvider

                return OpenAIProvider(config)
            case _:
                raise ValueError(f"Unknown LLM provider: {config.provider}")
