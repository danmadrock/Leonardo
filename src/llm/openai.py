"""Compatibility module.
Canonical LiteLLM implementation lives in :mod:`src.llm.base`.
"""


from src.llm.base import LiteLLMClient, get_llm


__all__ = ["LiteLLMClient", "get_llm"]