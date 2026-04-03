from src.llm.base import LiteLLMClient


class LocalLLM(LiteLLMClient):
    """LiteLLM client for local providers (Ollama/vLLM/OpenAI-compatible endpoints)."""
