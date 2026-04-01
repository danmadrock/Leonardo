from src.core.config import settings

def test_settings_loads() -> None:
    assert settings.LLM_MODEL is not None
    assert settings.REDIS_URL.startswith("redis://")
    assert "arxiv" in settings.ENABLED_SOURCES