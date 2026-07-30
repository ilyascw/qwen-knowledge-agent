from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from knowledge_agent.memory import SQLiteMemoryStore
from knowledge_agent.settings import MemorySettings

MCP_SERVER_NAME = "assistant"

mcp = FastMCP(MCP_SERVER_NAME)


@lru_cache(maxsize=1)
def _memory() -> SQLiteMemoryStore:
    settings = MemorySettings()
    store = SQLiteMemoryStore(settings.memory_db_path)
    store.initialize()
    return store


@mcp.tool(
    name="recall_memory",
    description="Search the agent's private long-term memory. This does not query Atlassian.",
)
def recall_memory(
    query: Annotated[str, Field(description="Words or topic to find; empty returns recent items")],
    limit: Annotated[int, Field(default=10, ge=1, le=50)] = 10,
) -> str:
    records = _memory().recall(query, limit)
    payload = [record.model_dump(mode="json") for record in records]
    return json.dumps(payload, ensure_ascii=False)


@mcp.tool(
    name="remember",
    description="Create or replace one item in the agent's private long-term memory.",
)
def remember(
    key: Annotated[
        str,
        Field(description="Stable short key without spaces, for example user.language"),
    ],
    content: Annotated[str, Field(description="Fact or preference worth retaining")],
) -> str:
    record = _memory().remember(key, content)
    return json.dumps(record.model_dump(mode="json"), ensure_ascii=False)


@mcp.tool(
    name="forget",
    description="Delete exactly one item from the agent's private long-term memory.",
)
def forget(
    key: Annotated[str, Field(description="Exact memory key returned by recall_memory")],
) -> str:
    deleted = _memory().forget(key)
    return json.dumps({"key": key, "deleted": deleted}, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
