from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Literal, TypedDict, cast

from pydantic import BaseModel

from src.core.config import settings
from src.core.exceptions import LLMError

try:
    import instructor
except ImportError:  # pragma: no cover - handled in runtime environments without instructor
    instructor = None  # type: ignore[assignment]

try:
    import litellm
except ImportError:  # pragma: no cover - handled in runtime environments without litellm
    litellm = None  # type: ignore[assignment]

class Message(TypedDict):
    role: Literal["system", "user", "assistant", "tool"]
    content: str


class BaseLLM(ABC):
    @abstractmethod
    async def complete(self, messages: list[Message], response_model: type[BaseModel] | None = None) -> str | BaseModel:
        """Run a chat completion request."""


class LiteLLMClient(BaseLLM):
    def __init__(self, model: str | None = None, max_retries: int = 3, retry_base_delay: float = 0.25, temperature: float = 0.0) -> None:
        self.model = model or settings.LLM_MODEL
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.temperature = temperature

    async def _acompletion(self, **kwargs: Any) -> Any:
        if litellm is None:
            raise RuntimeError("litellm is not installed")
        return await litellm.acompletion(**kwargs)

    async def complete(self, messages: list[Message], response_model: type[BaseModel] | None = None) -> str | BaseModel:
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if response_model is not None:
                    if instructor is None:
                        raise RuntimeError("instructor is required for structured outputs")
                    instructor_module = instructor
                    from_litellm = cast(Any, instructor_module.from_litellm)
                    client = from_litellm(self._acompletion)
                    return await client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=self.temperature,
                        response_model=response_model,
                    )
                response = await self._acompletion(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                )
                return self._extract_text(response)
            except Exception as exc:  # noqa: BLE001 - normalize all provider errors to LLMError
                last_error = exc
                if attempt >= self.max_retries:
                    break
                await asyncio.sleep(self.retry_base_delay * (2 ** (attempt - 1)))
        raise LLMError(
            f"LLM completion failed after {self.max_retries} retries for model {self.model}"
        ) from last_error

    @staticmethod
    def _extract_text(response: Any) -> str:
        if isinstance(response, dict):
            return str(response["choices"][0]["message"]["content"])
        choice = response.choices[0]
        message = getattr(choice, "message", None)
        content = getattr(message, "content", None)
        if content is None:
            raise ValueError("LLM response does not include message content")
        return str(content)


_client: LiteLLMClient | None = None


def get_llm() -> LiteLLMClient:
    global _client
    if _client is None:
        _client = LiteLLMClient()
    return _client