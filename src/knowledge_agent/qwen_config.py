from __future__ import annotations

import sys
from typing import Any

from knowledge_agent.settings import Settings

ATLASSIAN_TOOLS = (
    "jira_search",
    "jira_get_issue",
    "confluence_search",
    "confluence_get_page",
    "confluence_get_page_children",
)
ASSISTANT_TOOLS = ("recall_memory", "remember", "forget")


def qualified(server: str, tool: str) -> str:
    return f"mcp__{server}__{tool}"


def build_qwen_config(settings: Settings) -> dict[str, Any]:
    """Build the least-privilege Qwen project config without embedding secrets."""
    atlassian_rules = [qualified("atlassian", tool) for tool in ATLASSIAN_TOOLS]
    assistant_rules = [qualified("assistant", tool) for tool in ASSISTANT_TOOLS]
    allowed_rules = atlassian_rules + assistant_rules

    return {
        "context": {"fileName": "QWEN.md"},
        "model": {"name": settings.qwen_model},
        "modelProviders": {
            "openai": [
                {
                    "id": settings.qwen_model,
                    "name": settings.qwen_model,
                    "baseUrl": str(settings.qwen_api_base_url),
                    "envKey": "QWEN_AGENT_API_KEY",
                }
            ]
        },
        "security": {"auth": {"selectedType": "openai"}},
        "general": {
            "chatRecording": True,
            "checkpointing": {"enabled": False},
        },
        "privacy": {"usageStatisticsEnabled": False},
        "tools": {
            "approvalMode": "default",
            "core": allowed_rules,
        },
        "permissions": {
            "allow": allowed_rules,
            "deny": [
                "Read",
                "Edit",
                "WebFetch",
                "WebSearch",
                "Bash",
                "Bash(*)",
            ],
        },
        "mcp": {"allowed": ["atlassian", "assistant"]},
        "mcpServers": {
            "atlassian": {
                "command": "mcp-atlassian",
                "args": [
                    "--read-only",
                    "--toolsets",
                    "all",
                    "--enabled-tools",
                    ",".join(ATLASSIAN_TOOLS),
                ],
                "description": "Read-only Jira and Confluence access",
                "timeout": 120_000,
                "includeTools": list(ATLASSIAN_TOOLS),
                "env": {
                    "JIRA_URL": "$JIRA_URL",
                    "JIRA_USERNAME": "$JIRA_USERNAME",
                    "JIRA_API_TOKEN": "$JIRA_API_TOKEN",
                    "CONFLUENCE_URL": "$CONFLUENCE_URL",
                    "CONFLUENCE_USERNAME": "$CONFLUENCE_USERNAME",
                    "CONFLUENCE_API_TOKEN": "$CONFLUENCE_API_TOKEN",
                },
            },
            "assistant": {
                "command": sys.executable,
                "args": ["-m", "knowledge_agent.mcp_server"],
                "description": "Private long-term memory",
                "timeout": 30_000,
                "includeTools": list(ASSISTANT_TOOLS),
                "env": {"MEMORY_DB_PATH": "$MEMORY_DB_PATH"},
            },
        },
        "$version": 3,
    }
