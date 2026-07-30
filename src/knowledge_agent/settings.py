from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, AnyHttpUrl, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PositiveInt = Annotated[int, Field(gt=0)]


class Settings(BaseSettings):
    """Validated application configuration sourced only from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    telegram_bot_token: SecretStr = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    telegram_user_id: PositiveInt = Field(validation_alias="TELEGRAM_USER_ID")

    qwen_api_key: SecretStr | None = Field(
        default=None,
        validation_alias="QWEN_API_KEY",
    )
    qwen_credentials_file: Path | None = Field(
        default=None,
        validation_alias="QWEN_CREDENTIALS_FILE",
    )
    qwen_credentials_env_key: str | None = Field(
        default=None,
        validation_alias="QWEN_CREDENTIALS_ENV_KEY",
    )
    qwen_api_base_url: AnyHttpUrl = Field(validation_alias="QWEN_API_BASE_URL")
    qwen_model: Annotated[str, Field(min_length=1)] = Field(
        validation_alias=AliasChoices("QWEN_MODEL", "KR_EVAL_QWEN_MODEL")
    )
    qwen_binary: str = Field(
        default="qwen",
        validation_alias=AliasChoices("QWEN_BINARY", "KR_EVAL_QWEN_BINARY"),
    )
    qwen_timeout_seconds: PositiveInt = Field(
        default=300,
        validation_alias=AliasChoices(
            "QWEN_TIMEOUT_SECONDS",
            "KR_EVAL_QWEN_TIMEOUT_SECONDS",
        ),
    )
    qwen_required_version: str = Field(
        default="0.13.1",
        validation_alias="QWEN_REQUIRED_VERSION",
    )
    qwen_enforce_version: bool = Field(
        default=True,
        validation_alias="QWEN_ENFORCE_VERSION",
    )

    jira_url: AnyHttpUrl = Field(validation_alias="JIRA_URL")
    jira_username: Annotated[str, Field(min_length=1)] = Field(validation_alias="JIRA_USERNAME")
    jira_api_token: SecretStr = Field(validation_alias="JIRA_API_TOKEN")
    confluence_url: AnyHttpUrl = Field(validation_alias="CONFLUENCE_URL")
    confluence_username: Annotated[str, Field(min_length=1)] = Field(
        validation_alias="CONFLUENCE_USERNAME"
    )
    confluence_api_token: SecretStr = Field(validation_alias="CONFLUENCE_API_TOKEN")

    agent_profile_dir: Path = Field(
        default=Path("agent"),
        validation_alias="AGENT_PROFILE_DIR",
    )
    memory_db_path: Path = Field(
        default=Path("data/memory.db"),
        validation_alias="MEMORY_DB_PATH",
    )
    qwen_runtime_dir: Path = Field(
        default=Path("data/qwen-runtime"),
        validation_alias="QWEN_RUNTIME_DIR",
    )
    qwen_workspace_dir: Path = Field(
        default=Path("data/qwen-workspace"),
        validation_alias="QWEN_WORKSPACE_DIR",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )
    max_message_length: Annotated[int, Field(ge=1, le=100_000)] = Field(
        default=12_000,
        validation_alias="MAX_MESSAGE_LENGTH",
    )

    @model_validator(mode="after")
    def validate_paths(self) -> Settings:
        profile = self.agent_profile_dir.resolve()
        if not (profile / "QWEN.md").is_file():
            raise ValueError(f"Qwen profile must contain QWEN.md: {profile}")
        self.agent_profile_dir = profile
        self.memory_db_path = self.memory_db_path.resolve()
        self.qwen_runtime_dir = self.qwen_runtime_dir.resolve()
        self.qwen_workspace_dir = self.qwen_workspace_dir.resolve()
        if self.qwen_credentials_file is not None:
            self.qwen_credentials_file = self.qwen_credentials_file.resolve()
        has_direct_key = bool(
            self.qwen_api_key is not None and self.qwen_api_key.get_secret_value()
        )
        if not has_direct_key and (
            self.qwen_credentials_file is None or not self.qwen_credentials_env_key
        ):
            raise ValueError(
                "Set QWEN_API_KEY or both QWEN_CREDENTIALS_FILE and QWEN_CREDENTIALS_ENV_KEY"
            )
        return self

    def resolved_qwen_api_key(self) -> str:
        """Read one selected key from env or a read-only Qwen settings secret."""
        if self.qwen_api_key is not None and self.qwen_api_key.get_secret_value():
            return self.qwen_api_key.get_secret_value()

        if self.qwen_credentials_file is None or not self.qwen_credentials_env_key:
            raise RuntimeError("Qwen credentials are not configured")
        try:
            raw = self.qwen_credentials_file.read_text(encoding="utf-8")
            document = json.loads(raw)
            value = document["env"][self.qwen_credentials_env_key]
        except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError(
                f"Cannot read {self.qwen_credentials_env_key!r} from Qwen credentials file"
            ) from exc
        if not isinstance(value, str) or not value:
            raise ValueError(
                f"Qwen credentials file contains no value for {self.qwen_credentials_env_key!r}"
            )
        return value


class MemorySettings(BaseSettings):
    """Small settings boundary used by the isolated MCP subprocess."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=True)

    memory_db_path: Path = Field(validation_alias="MEMORY_DB_PATH")


def get_settings() -> Settings:
    return Settings()
