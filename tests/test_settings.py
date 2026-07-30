from pathlib import Path

import pytest
from pydantic import ValidationError

from knowledge_agent.settings import Settings


def valid_data(tmp_path: Path) -> dict[str, object]:
    profile = tmp_path / "agent"
    profile.mkdir()
    (profile / "QWEN.md").write_text("# test", encoding="utf-8")
    return {
        "TELEGRAM_BOT_TOKEN": "token",
        "TELEGRAM_USER_ID": 7,
        "QWEN_API_KEY": "key",
        "QWEN_API_BASE_URL": "https://llm.example/v1",
        "QWEN_MODEL": "qwen",
        "JIRA_URL": "https://jira.example",
        "JIRA_USERNAME": "user",
        "JIRA_API_TOKEN": "token",
        "CONFLUENCE_URL": "https://confluence.example",
        "CONFLUENCE_USERNAME": "user",
        "CONFLUENCE_API_TOKEN": "token",
        "AGENT_PROFILE_DIR": profile,
        "MEMORY_DB_PATH": tmp_path / "memory.db",
    }


def test_settings_resolve_runtime_paths(tmp_path: Path) -> None:
    settings = Settings.model_validate(valid_data(tmp_path))

    assert settings.agent_profile_dir.is_absolute()
    assert settings.memory_db_path.is_absolute()


def test_settings_accept_eval_qwen_names(tmp_path: Path) -> None:
    data = valid_data(tmp_path)
    data.pop("QWEN_MODEL")
    data["KR_EVAL_QWEN_MODEL"] = "qwen-from-eval"
    data["KR_EVAL_QWEN_TIMEOUT_SECONDS"] = 600

    settings = Settings.model_validate(data)

    assert settings.qwen_model == "qwen-from-eval"
    assert settings.qwen_timeout_seconds == 600


def test_api_key_can_be_read_from_qwen_settings_secret(tmp_path: Path) -> None:
    data = valid_data(tmp_path)
    data["QWEN_API_KEY"] = ""
    credentials_file = tmp_path / "qwen-settings.json"
    credentials_file.write_text(
        '{"env":{"CUSTOM_MODEL_KEY":"from-secret-file"}}',
        encoding="utf-8",
    )
    data["QWEN_CREDENTIALS_FILE"] = credentials_file
    data["QWEN_CREDENTIALS_ENV_KEY"] = "CUSTOM_MODEL_KEY"

    settings = Settings.model_validate(data)

    assert settings.resolved_qwen_api_key() == "from-secret-file"


def test_non_positive_user_id_is_rejected(tmp_path: Path) -> None:
    data = valid_data(tmp_path)
    data["TELEGRAM_USER_ID"] = 0

    with pytest.raises(ValidationError):
        Settings.model_validate(data)


def test_missing_agent_prompt_is_rejected(tmp_path: Path) -> None:
    data = valid_data(tmp_path)
    data["AGENT_PROFILE_DIR"] = tmp_path / "missing"

    with pytest.raises(ValidationError, match=r"QWEN\.md"):
        Settings.model_validate(data)
