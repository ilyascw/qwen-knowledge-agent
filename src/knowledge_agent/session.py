from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


class SessionStateError(RuntimeError):
    """The persisted Qwen session state is missing or malformed."""


@dataclass(frozen=True)
class SessionState:
    session_id: str
    started: bool


class SessionStore:
    """Tracks one active Qwen session and removes it on explicit reset."""

    def __init__(self, runtime_dir: Path) -> None:
        self._runtime_dir = runtime_dir
        self._state_path = runtime_dir / "active_session.json"

    def current(self) -> SessionState:
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        if not self._state_path.exists():
            state = self._new_state()
            self._write(state)
            return state

        try:
            document = json.loads(self._state_path.read_text(encoding="utf-8"))
            session_id = str(document["session_id"])
            started = document["started"]
            uuid.UUID(session_id)
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SessionStateError(f"Invalid Qwen session state: {self._state_path}") from exc
        if not isinstance(started, bool):
            raise SessionStateError(f"Invalid Qwen session state: {self._state_path}")
        return SessionState(session_id=session_id, started=started)

    def mark_started(self, session_id: str) -> None:
        state = self.current()
        if state.session_id != session_id:
            raise SessionStateError("Active Qwen session changed while a request was running")
        if not state.started:
            self._write(SessionState(session_id=session_id, started=True))

    def reset(self) -> SessionState:
        current = self.current()
        for transcript in self._runtime_dir.rglob(f"{current.session_id}.jsonl"):
            transcript.unlink()
        state = self._new_state()
        self._write(state)
        return state

    @staticmethod
    def _new_state() -> SessionState:
        return SessionState(session_id=str(uuid.uuid4()), started=False)

    def _write(self, state: SessionState) -> None:
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = self._state_path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(asdict(state), ensure_ascii=False),
            encoding="utf-8",
        )
        temporary_path.replace(self._state_path)
