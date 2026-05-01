import pytest
from app.config import get_settings, SystemSettings, LLMSettings


class TestConfig:
    def test_get_settings(self):
        settings = get_settings()
        assert settings.system.name == "CodeGuard Agent"
        assert settings.system.version == "1.0.0"

    def test_system_settings(self):
        settings = SystemSettings()
        assert settings.log_level in ("DEBUG", "INFO", "WARNING", "ERROR")

    def test_llm_settings(self):
        settings = LLMSettings()
        assert settings.model == "gpt-4o"
        assert settings.temperature >= 0
        assert settings.temperature <= 1
        assert settings.max_tokens > 0
