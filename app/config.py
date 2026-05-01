import os
from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml
from pydantic_settings import BaseSettings
from pydantic import Field


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _YamlLoader:
    _raw: dict[str, Any] = {}

    @classmethod
    def load(cls) -> dict[str, Any]:
        if not cls._raw:
            config_path = _PROJECT_ROOT / "config.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    cls._raw = yaml.safe_load(f) or {}
            else:
                cls._raw = {}
        return cls._raw

    @classmethod
    def get(cls, dot_path: str, default: Any = None) -> Any:
        data = cls.load()
        keys = dot_path.split(".")
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return default
            if data is None:
                return default
        if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            env_expr = data[2:-1]
            if ":" in env_expr:
                env_key, fallback = env_expr.split(":", 1)
                return os.getenv(env_key, fallback)
            return os.getenv(env_expr, default)
        return data


class SystemSettings(BaseSettings):
    name: str = "CodeGuard Agent"
    version: str = "1.0.0"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    def __init__(self, **kwargs: Any) -> None:
        yaml_vals = {
            "name": _YamlLoader.get("system.name"),
            "version": _YamlLoader.get("system.version"),
            "log_level": _YamlLoader.get("system.log_level"),
            "host": _YamlLoader.get("system.host"),
            "port": _YamlLoader.get("system.port"),
        }
        yaml_vals = {k: v for k, v in yaml_vals.items() if v is not None}
        yaml_vals.update(kwargs)
        super().__init__(**yaml_vals)


class GitSettings(BaseSettings):
    platform: str = "gitlab"
    base_url: str = "https://gitlab.com"
    access_token: str = ""
    webhook_secret: str = ""

    def __init__(self, **kwargs: Any) -> None:
        yaml_vals = {
            "platform": _YamlLoader.get("git.platform"),
            "base_url": _YamlLoader.get("git.base_url"),
            "access_token": _YamlLoader.get("git.access_token"),
            "webhook_secret": _YamlLoader.get("git.webhook_secret"),
        }
        yaml_vals = {k: v for k, v in yaml_vals.items() if v is not None}
        yaml_vals.update(kwargs)
        super().__init__(**yaml_vals)


class LLMSettings(BaseSettings):
    provider: str = "openai"
    model: str = "gpt-4o"
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.1
    retry_max_attempts: int = 3
    retry_backoff_seconds: int = 2

    def __init__(self, **kwargs: Any) -> None:
        yaml_vals = {
            "provider": _YamlLoader.get("llm.provider"),
            "model": _YamlLoader.get("llm.model"),
            "api_key": _YamlLoader.get("llm.api_key"),
            "api_base": _YamlLoader.get("llm.api_base"),
            "max_tokens": _YamlLoader.get("llm.max_tokens"),
            "temperature": _YamlLoader.get("llm.temperature"),
            "retry_max_attempts": _YamlLoader.get("llm.retry_max_attempts"),
            "retry_backoff_seconds": _YamlLoader.get("llm.retry_backoff_seconds"),
        }
        yaml_vals = {k: v for k, v in yaml_vals.items() if v is not None}
        yaml_vals.update(kwargs)
        super().__init__(**yaml_vals)


class VectorDBSettings(BaseSettings):
    provider: str = "chroma"
    persist_directory: str = "./data/chroma"
    collection_standards: str = "coding_standards"
    collection_code: str = "code_snippets"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    def __init__(self, **kwargs: Any) -> None:
        yaml_vals = {
            "provider": _YamlLoader.get("vector_db.provider"),
            "persist_directory": _YamlLoader.get("vector_db.persist_directory"),
            "collection_standards": _YamlLoader.get("vector_db.collection_standards"),
            "collection_code": _YamlLoader.get("vector_db.collection_code"),
            "embedding_model": _YamlLoader.get("vector_db.embedding_model"),
            "embedding_dim": _YamlLoader.get("vector_db.embedding_dim"),
        }
        yaml_vals = {k: v for k, v in yaml_vals.items() if v is not None}
        yaml_vals.update(kwargs)
        super().__init__(**yaml_vals)


class DatabaseSettings(BaseSettings):
    url: str = "postgresql+asyncpg://codeguard:codeguard@localhost:5432/codeguard"
    pool_size: int = 10
    max_overflow: int = 20

    def __init__(self, **kwargs: Any) -> None:
        yaml_vals = {
            "url": _YamlLoader.get("database.url"),
            "pool_size": _YamlLoader.get("database.pool_size"),
            "max_overflow": _YamlLoader.get("database.max_overflow"),
        }
        yaml_vals = {k: v for k, v in yaml_vals.items() if v is not None}
        yaml_vals.update(kwargs)
        super().__init__(**yaml_vals)


class RedisSettings(BaseSettings):
    url: str = "redis://localhost:6379/0"

    def __init__(self, **kwargs: Any) -> None:
        yaml_vals = {
            "url": _YamlLoader.get("redis.url"),
        }
        yaml_vals = {k: v for k, v in yaml_vals.items() if v is not None}
        yaml_vals.update(kwargs)
        super().__init__(**yaml_vals)


class AgentConfig(BaseSettings):
    enabled: bool = True
    timeout_seconds: int = 120
    extra: dict[str, Any] = Field(default_factory=dict)


class AgentSettings(BaseSettings):
    code_scan: AgentConfig = AgentConfig()
    standard_compare: AgentConfig = AgentConfig(timeout_seconds=60)
    refactor_suggest: AgentConfig = AgentConfig(timeout_seconds=180)
    verify: AgentConfig = AgentConfig(timeout_seconds=300)

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        raw = _YamlLoader.load().get("agents", {})
        for agent_name in ("code_scan", "standard_compare", "refactor_suggest", "verify"):
            if agent_name in raw:
                agent_raw = raw[agent_name]
                current = getattr(self, agent_name)
                updated = current.model_copy(update={
                    k: v for k, v in agent_raw.items()
                    if k in AgentConfig.model_fields
                })
                setattr(self, agent_name, updated)


class NotificationSettings(BaseSettings):
    enabled: bool = False
    channels: list[dict[str, Any]] = Field(default_factory=list)

    def __init__(self, **kwargs: Any) -> None:
        yaml_vals = {
            "enabled": _YamlLoader.get("notification.enabled"),
            "channels": _YamlLoader.get("notification.channels"),
        }
        yaml_vals = {k: v for k, v in yaml_vals.items() if v is not None}
        yaml_vals.update(kwargs)
        super().__init__(**yaml_vals)


class AppSettings(BaseSettings):
    system: SystemSettings = SystemSettings()
    git: GitSettings = GitSettings()
    llm: LLMSettings = LLMSettings()
    vector_db: VectorDBSettings = VectorDBSettings()
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    agents: AgentSettings = AgentSettings()
    notification: NotificationSettings = NotificationSettings()


@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()
