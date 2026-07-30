from pathlib import Path

import pytest

from knowledge_agent.session import SessionStateError, SessionStore


def test_session_is_created_and_marked_started(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)

    initial = store.current()
    store.mark_started(initial.session_id)

    resumed = store.current()
    assert resumed.session_id == initial.session_id
    assert resumed.started is True


def test_reset_removes_active_transcript_and_preserves_other_files(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    initial = store.current()
    transcript = tmp_path / "projects" / "agent" / "chats" / f"{initial.session_id}.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text("history", encoding="utf-8")
    memory = tmp_path / "memory.db"
    memory.write_text("memory", encoding="utf-8")

    replacement = store.reset()

    assert replacement.session_id != initial.session_id
    assert replacement.started is False
    assert not transcript.exists()
    assert memory.read_text(encoding="utf-8") == "memory"


def test_invalid_session_state_fails_loudly(tmp_path: Path) -> None:
    (tmp_path / "active_session.json").write_text("{}", encoding="utf-8")

    with pytest.raises(SessionStateError):
        SessionStore(tmp_path).current()
