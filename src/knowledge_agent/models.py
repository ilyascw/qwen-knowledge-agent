from __future__ import annotations

from pydantic import BaseModel


class MemoryRecord(BaseModel):
    key: str
    content: str
    created_at: str
    updated_at: str
