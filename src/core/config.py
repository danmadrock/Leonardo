from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")
    
    # LLM
    LLM_MODEL: str = "gpt-4o-mini"
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    OLLAMA_BASE_URL: str | None = None
    LLM_TIMEOUT_SECONDS: float = 45.0
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_DELAY: float = 0.25

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://leonardo:secret@localhost:5432/leonardo"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Sources
    ENABLED_SOURCES: list[str] = ["arxiv", "semantic_scholar"]
    SEMANTIC_SCHOLAR_API_KEY: str | None = None
    SOURCE_TIMEOUT_SECONDS: float = 30.0

    # Pipeline
    MIN_PAPERS_THRESHOLD: int = 8
    MAX_SEARCH_ITERATIONS: int = 2
    ANALYSIS_BATCH_SIZE: int = 5
    MIN_FINDING_RELEVANCE: float = 0.3
    MAX_PAPERS_PER_SUBTASK: int = 10

    # API hardening
    API_RATE_LIMIT_REQUESTS: int = 60
    API_RATE_LIMIT_WINDOW_SECONDS: int = 60

    # Observability
    LOG_LEVEL: str = "INFO"
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()