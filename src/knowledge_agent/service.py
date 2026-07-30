from __future__ import annotations

import asyncio
from typing import Protocol


class AnsweringAgent(Protocol):
    async def answer(self, user_message: str) -> str: ...

    async def start_new_session(self) -> str: ...


class AssistantService:
    """Serializes the single user's requests and delegates them to Qwen."""

    def __init__(self, agent: AnsweringAgent) -> None:
        self._agent = agent
        self._lock = asyncio.Lock()

    async def reply(self, message: str) -> str:
        async with self._lock:
            return await self._agent.answer(message)

    async def start_new_session(self) -> None:
        async with self._lock:
            await self._agent.start_new_session()


def split_telegram_text(text: str, limit: int = 4_000) -> list[str]:
    """Split a reply below Telegram's 4096-character hard limit."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remainder = text
    while remainder:
        if len(remainder) <= limit:
            chunks.append(remainder)
            break
        boundary = remainder.rfind("\n", 0, limit + 1)
        if boundary <= 0:
            boundary = remainder.rfind(" ", 0, limit + 1)
        if boundary <= 0:
            boundary = limit
        chunks.append(remainder[:boundary].rstrip())
        remainder = remainder[boundary:].lstrip()
    return chunks
