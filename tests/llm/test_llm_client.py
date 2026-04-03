from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from src.core.exceptions import LLMError
from src.llm.base import LiteLLMClient


class StructuredAnswer(BaseModel):
    topic: str
    confidence: float


@pytest.mark.asyncio
async def test_complete_passes_messages_to_litellm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Say hello"},
    ]
    mock_completion = AsyncMock(
        return_value={"choices": [{"message": {"content": "hello"}}]}
    )
    monkeypatch.setattr(
        "src.llm.base.litellm", SimpleNamespace(acompletion=mock_completion)
    )

    llm = LiteLLMClient(model="gpt-test")
    result = await llm.complete(messages)

    assert result == "hello"
    mock_completion.assert_awaited_once_with(
        model="gpt-test",
        messages=messages,
        temperature=0.0,
    )


@pytest.mark.asyncio
async def test_complete_with_response_model_returns_pydantic_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [{"role": "user", "content": "Return structured output"}]
    expected = StructuredAnswer(topic="llm", confidence=0.91)

    create_mock = AsyncMock(return_value=expected)
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock))
    )

    monkeypatch.setattr(
        "src.llm.base.instructor",
        SimpleNamespace(from_litellm=lambda acompletion: fake_client),
    )
    monkeypatch.setattr(
        "src.llm.base.litellm", SimpleNamespace(acompletion=AsyncMock())
    )

    llm = LiteLLMClient(model="gpt-test")
    result = await llm.complete(messages, response_model=StructuredAnswer)

    assert isinstance(result, StructuredAnswer)
    assert result == expected
    create_mock.assert_awaited_once_with(
        model="gpt-test",
        messages=messages,
        temperature=0.0,
        response_model=StructuredAnswer,
    )


@pytest.mark.asyncio
async def test_complete_raises_llm_error_after_three_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_completion = AsyncMock(side_effect=RuntimeError("boom"))
    mock_sleep = AsyncMock()

    monkeypatch.setattr(
        "src.llm.base.litellm", SimpleNamespace(acompletion=mock_completion)
    )
    monkeypatch.setattr("src.llm.base.asyncio.sleep", mock_sleep)

    llm = LiteLLMClient(model="gpt-test", max_retries=3)

    with pytest.raises(LLMError):
        await llm.complete([{"role": "user", "content": "fail"}])

    assert mock_completion.await_count == 3
    assert mock_sleep.await_count == 2
