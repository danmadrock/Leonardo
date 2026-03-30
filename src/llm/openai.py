import logging
from typing import TypeVar, cast
import instructor
import litellm
from litellm.types.utils import ModelResponse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from src.llm.base import BaseLLM, Message
from src.core.config import settings
from src.core.exceptions import LLMError


logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LiteLLMClient(BaseLLM):
    def __init__(self) -> None:
        self._model = settings.LLM_MODEL
        self._instructor_client = instructor.from_litellm(litellm.acompletion)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def complete(
        self,
        messages: list[Message],
        response_model: type[T] | None = None,
    ) -> str | T:
        msgs = cast(list[ChatCompletionMessageParam], [m.to_dict() for m in messages])
        try:
            if response_model is not None:
                    return cast(T, await self._instructor_client.chat.completions.create(
                    model = self._model,
                    messages = msgs,
                    response_model = response_model,
                    max_tokens = 2000,
                    ))
            response = cast(ModelResponse, await litellm.acompletion(
                model = self._model,
                messages = msgs,
                max_tokens = 4000,
                stream=False
            ))
            return response.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM call failed", extra={"error": str(exc)})
            raise LLMError(f"LLM failed: {exc}") from exc


_client: LiteLLMClient | None = None


def get_llm() -> LiteLLMClient:
    global _client
    if _client is None:
        _client = LiteLLMClient()
    return _client
