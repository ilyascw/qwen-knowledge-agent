import json
from pathlib import Path
from typing import Any

import pytest

from knowledge_agent.qwen_runner import (
    QwenError,
    QwenRunner,
    _extract_qwen_error,
    extract_result_text,
    parse_envelope,
)
from knowledge_agent.session import SessionState
from knowledge_agent.settings import Settings


def make_settings(tmp_path: Path) -> Settings:
    profile = tmp_path / "agent"
    profile.mkdir()
    (profile / "QWEN.md").write_text("# test", encoding="utf-8")
    return Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "telegram-secret",
            "TELEGRAM_USER_ID": 42,
            "QWEN_API_KEY": "model-secret",
            "QWEN_API_BASE_URL": "https://llm.example/v1",
            "QWEN_MODEL": "qwen-test",
            "JIRA_URL": "https://jira.example",
            "JIRA_USERNAME": "user@example.com",
            "JIRA_API_TOKEN": "jira-secret",
            "CONFLUENCE_URL": "https://confluence.example",
            "CONFLUENCE_USERNAME": "user@example.com",
            "CONFLUENCE_API_TOKEN": "confluence-secret",
            "AGENT_PROFILE_DIR": profile,
            "MEMORY_DB_PATH": tmp_path / "memory.db",
            "QWEN_RUNTIME_DIR": tmp_path / "runtime",
            "QWEN_WORKSPACE_DIR": tmp_path / "workspace",
        }
    )


def test_parse_envelope_accepts_array_and_json_lines() -> None:
    items = [{"type": "system"}, {"type": "result"}]

    assert parse_envelope(json.dumps(items)) == items
    assert parse_envelope("\n".join(json.dumps(item) for item in items)) == items


def test_invalid_envelope_is_an_error() -> None:
    with pytest.raises(QwenError):
        parse_envelope("not json")


def test_extracts_structured_qwen_error() -> None:
    stdout = json.dumps(
        {
            "type": "result",
            "is_error": True,
            "error": {"message": "No auth type is selected"},
        }
    )

    assert _extract_qwen_error(stdout) == "No auth type is selected"


def test_extracts_final_text_answer() -> None:
    messages: list[dict[str, Any]] = [
        {"type": "assistant", "message": {"content": []}},
        {"type": "result", "is_error": False, "result": "Обычный ответ"},
    ]

    assert extract_result_text(messages) == "Обычный ответ"


def test_new_session_uses_id_and_started_session_resumes(tmp_path: Path) -> None:
    runner = QwenRunner(make_settings(tmp_path))
    session_id = "123e4567-e89b-12d3-a456-426614174000"

    initial = runner._command("hello", SessionState(session_id=session_id, started=False))
    resumed = runner._command("again", SessionState(session_id=session_id, started=True))

    assert initial[-2:] == ["--session-id", session_id]
    assert resumed[-2:] == ["--resume", session_id]
    assert "--chat-recording" in initial
