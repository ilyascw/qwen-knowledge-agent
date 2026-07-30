from __future__ import annotations

import asyncio
import shutil

from knowledge_agent.memory import SQLiteMemoryStore
from knowledge_agent.qwen_config import ASSISTANT_TOOLS, ATLASSIAN_TOOLS, build_qwen_config
from knowledge_agent.qwen_runner import QwenRunner
from knowledge_agent.settings import get_settings


async def check() -> None:
    settings = get_settings()
    if shutil.which(settings.qwen_binary) is None:
        raise RuntimeError(f"Qwen binary is not in PATH: {settings.qwen_binary}")
    if shutil.which("mcp-atlassian") is None:
        raise RuntimeError("mcp-atlassian is not in PATH")

    version = await QwenRunner(settings).require_expected_version()
    store = SQLiteMemoryStore(settings.memory_db_path)
    store.initialize()

    config = build_qwen_config(settings)
    atlassian = config["mcpServers"]["atlassian"]
    assistant = config["mcpServers"]["assistant"]
    if set(atlassian["includeTools"]) != set(ATLASSIAN_TOOLS):
        raise RuntimeError("Atlassian tool allowlist is inconsistent")
    if set(assistant["includeTools"]) != set(ASSISTANT_TOOLS):
        raise RuntimeError("Assistant tool allowlist is inconsistent")

    print(f"[ok] qwen: {version}")
    print("[ok] Atlassian: read-only, 5 tools")
    print(f"[ok] private memory: {settings.memory_db_path} ({store.count()} records)")
    print("[ok] configuration is valid")


def main() -> None:
    asyncio.run(check())


if __name__ == "__main__":
    main()
