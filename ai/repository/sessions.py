"""In-process session store for multi-turn chat.

Each session is keyed by (user_id, session_id) and holds the last
SESSION_MAX_TURNS turns (a turn = one user message + one assistant answer).
Sessions expire SESSION_TTL_MINUTES after their last update.

This module is intentionally NOT thread-safe across multiple workers — a
single uvicorn worker is the deployment target. If we move to multi-worker
later, swap this for Redis. See CONTEXT.md "non-goals for v1".
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from config import SESSION_MAX_TURNS, SESSION_TTL_MINUTES


logger = logging.getLogger("foodshare.ai.sessions")


@dataclass
class Turn:
    role: str            # "user" or "assistant"
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    user_id: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    turns: list[Turn] = field(default_factory=list)
    last_used: float = field(default_factory=time.time)


class SessionStore:
    def __init__(
        self,
        ttl_seconds: int | None = None,
        max_turns: int | None = None,
    ) -> None:
        self._sessions: dict[tuple[int, str], Session] = {}
        self._lock = threading.Lock()
        self._ttl = (ttl_seconds if ttl_seconds is not None
                     else SESSION_TTL_MINUTES * 60)
        self._max_turns = max_turns if max_turns is not None else SESSION_MAX_TURNS

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def get_or_create(self, user_id: int, session_id: Optional[str]) -> Session:
        """Return the session for (user_id, session_id), creating it if absent.

        Lazy-expires on every call so old sessions disappear naturally.
        """
        self._sweep_expired_locked()
        with self._lock:
            if session_id:
                key = (user_id, session_id)
                sess = self._sessions.get(key)
                if sess is not None:
                    sess.last_used = time.time()
                    return sess
            # Either no id supplied, or id didn't match — create a new one.
            new_session = Session(user_id=user_id)
            self._sessions[(user_id, new_session.id)] = new_session
            return new_session

    def get(self, user_id: int, session_id: str) -> Optional[Session]:
        with self._lock:
            self._sweep_expired_locked()
            sess = self._sessions.get((user_id, session_id))
            if sess is None:
                return None
            sess.last_used = time.time()
            return sess

    def reset(self, user_id: int, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop((user_id, session_id), None) is not None

    def append_turn(
        self,
        session: Session,
        role: str,
        content: str,
    ) -> None:
        with self._lock:
            session.turns.append(Turn(role=role, content=content))
            # Trim to last N turns (N = max_turns * 2 — each turn is one
            # user + one assistant, so we want to keep at most max_turns
            # conversation rounds).
            cap = self._max_turns * 2
            if len(session.turns) > cap:
                session.turns = session.turns[-cap:]
            session.last_used = time.time()

    def stats(self) -> dict:
        with self._lock:
            return {
                "active_sessions": len(self._sessions),
                "ttl_seconds": self._ttl,
                "max_turns": self._max_turns,
            }

    # ------------------------------------------------------------------
    # internal
    # ------------------------------------------------------------------

    def _sweep_expired_locked(self) -> None:
        """Drop sessions whose last_used is older than TTL.

        Must be called with `self._lock` already held.
        """
        now = time.time()
        expired = [
            k for k, s in self._sessions.items()
            if now - s.last_used > self._ttl
        ]
        for k in expired:
            self._sessions.pop(k, None)
            logger.debug("expired session %s", k)


# Module-level singleton (single-worker assumption)
_store = SessionStore()


def get_store() -> SessionStore:
    return _store