from pathlib import Path

import pytest

from knowledge_agent.memory import MemoryError, SQLiteMemoryStore


def store_at(path: Path) -> SQLiteMemoryStore:
    store = SQLiteMemoryStore(path)
    store.initialize()
    return store


def test_remember_recall_and_update(tmp_path: Path) -> None:
    store = store_at(tmp_path / "memory.db")

    created = store.remember("user.language", "Отвечать на русском")
    updated = store.remember("user.language", "Отвечать кратко на русском")

    assert created.key == "user.language"
    assert updated.content == "Отвечать кратко на русском"
    assert store.count() == 1
    assert store.recall("русском")[0].key == "user.language"


def test_recall_ranks_more_matching_terms_first(tmp_path: Path) -> None:
    store = store_at(tmp_path / "memory.db")
    store.remember("project.alpha", "Python сервис")
    store.remember("project.beta", "Python Telegram сервис")

    records = store.recall("python telegram")

    assert [record.key for record in records] == ["project.beta", "project.alpha"]


def test_forget_deletes_only_requested_key(tmp_path: Path) -> None:
    store = store_at(tmp_path / "memory.db")
    store.remember("first", "one")
    store.remember("second", "two")

    assert store.forget("first")
    assert not store.forget("missing")
    assert [record.key for record in store.recall("")] == ["second"]


@pytest.mark.parametrize("key", ["", "has spaces", " "])
def test_invalid_key_is_rejected(tmp_path: Path, key: str) -> None:
    store = store_at(tmp_path / "memory.db")

    with pytest.raises(MemoryError):
        store.remember(key, "value")
