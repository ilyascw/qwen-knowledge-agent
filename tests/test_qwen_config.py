from pathlib import Path

from knowledge_agent.qwen_config import ASSISTANT_TOOLS, ATLASSIAN_TOOLS, build_qwen_config
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
        }
    )


def test_config_exposes_only_explicit_mcp_tools(tmp_path: Path) -> None:
    config = build_qwen_config(make_settings(tmp_path))
    atlassian_rules = {f"mcp__atlassian__{tool}" for tool in ATLASSIAN_TOOLS}
    assistant_rules = {f"mcp__assistant__{tool}" for tool in ASSISTANT_TOOLS}

    assert set(config["tools"]["core"]) == atlassian_rules | assistant_rules
    assert set(config["permissions"]["allow"]) == atlassian_rules | assistant_rules
    assert "run_shell_command" not in config["tools"]["core"]
    assert "read_file" not in config["tools"]["core"]
    assert "save_memory" not in config["tools"]["core"]


def test_atlassian_server_is_read_only_and_filtered(tmp_path: Path) -> None:
    config = build_qwen_config(make_settings(tmp_path))
    server = config["mcpServers"]["atlassian"]

    assert "--read-only" in server["args"]
    enabled_index = server["args"].index("--enabled-tools") + 1
    assert set(server["args"][enabled_index].split(",")) == set(ATLASSIAN_TOOLS)
    assert set(server["includeTools"]) == set(ATLASSIAN_TOOLS)


def test_generated_config_does_not_contain_secrets(tmp_path: Path) -> None:
    config_text = str(build_qwen_config(make_settings(tmp_path)))

    assert "model-secret" not in config_text
    assert "jira-secret" not in config_text
    assert "confluence-secret" not in config_text
    assert "QWEN_AGENT_API_KEY" in config_text


def test_transcript_recording_is_enabled_for_session_resume(tmp_path: Path) -> None:
    config = build_qwen_config(make_settings(tmp_path))

    assert config["general"]["chatRecording"] is True
    assert config["general"]["checkpointing"]["enabled"] is False
    assert config["privacy"]["usageStatisticsEnabled"] is False


def test_headless_auth_type_is_explicit(tmp_path: Path) -> None:
    config = build_qwen_config(make_settings(tmp_path))

    assert config["security"]["auth"]["selectedType"] == "openai"
