from __future__ import annotations

import asyncio
import logging

from knowledge_agent.bot import run_bot
from knowledge_agent.memory import SQLiteMemoryStore
from knowledge_agent.qwen_config import ASSISTANT_TOOLS, ATLASSIAN_TOOLS
from knowledge_agent.qwen_runner import QwenRunner
from knowledge_agent.service import AssistantService
from knowledge_agent.settings import get_settings


async def main() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    SQLiteMemoryStore(settings.memory_db_path).initialize()
    runner = QwenRunner(settings)
    version = await runner.require_expected_version()
    logging.getLogger(__name__).info("Starting with Qwen Code %s", version)
    logging.getLogger(__name__).info(
        "Tool registry: atlassian=%s assistant=%s",
        ",".join(ATLASSIAN_TOOLS),
        ",".join(ASSISTANT_TOOLS),
    )

    await run_bot(settings, AssistantService(runner))


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
