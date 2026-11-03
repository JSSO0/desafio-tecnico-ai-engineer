from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.errors import SessionError
from app.core.turn import TurnOutcome

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


@dataclass(frozen=True)
class Session:
    session_id: str
    expires_at: str
    customer_id: int | None
    customer_name: str | None
    budget_tokens: int


def _now() -> datetime:
    return datetime.now(UTC)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RuntimeStore:
    """Sessoes, historico e consumo. A base operacional continua somente leitura."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # --- sessoes ---------------------------------------------------------

    def create(self, ttl_minutes: int, budget_tokens: int) -> tuple[str, Session]:
        token = secrets.token_urlsafe(32)
        session_id = secrets.token_hex(8)
        expires = _now() + timedelta(minutes=ttl_minutes)
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, token_hash, created_at, expires_at,"
                " budget_tokens) VALUES (?, ?, ?, ?, ?)",
                (session_id, _hash(token), _now().isoformat(), expires.isoformat(), budget_tokens),
            )
            conn.commit()
        return token, Session(session_id, expires.isoformat(), None, None, budget_tokens)

    def by_token(self, token: str, ttl_minutes: int) -> Session:
        """Valida o token e desliza a expiracao. Token opaco: revogavel e sem conteudo legivel."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token_hash = ?", (_hash(token),)
            ).fetchone()

            if row is None:
                raise SessionError("invalid_token", "Token de sessao invalido.")
            if row["revoked_at"] is not None:
                raise SessionError("revoked_token", "Sessao encerrada.")

            expires = datetime.fromisoformat(row["expires_at"])
            if expires <= _now():
                raise SessionError("expired_token", "Sessao expirada. Abra uma nova.")

            next_expiry = (_now() + timedelta(minutes=ttl_minutes)).isoformat()
            conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE session_id = ?",
                (next_expiry, row["session_id"]),
            )
            conn.commit()

        return Session(
            session_id=row["session_id"],
            expires_at=next_expiry,
            customer_id=row["customer_id"],
            customer_name=row["customer_name"],
            budget_tokens=row["budget_tokens"],
        )

    def revoke(self, session_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE session_id = ?",
                (_now().isoformat(), session_id),
            )
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.commit()

    def bind_customer(self, session_id: str, customer_id: int | None, name: str | None) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "UPDATE sessions SET customer_id = ?, customer_name = ? WHERE session_id = ?",
                (customer_id, name, session_id),
            )
            conn.commit()

    # --- consumo ---------------------------------------------------------

    def add_usage(self, session_id: str, outcome: TurnOutcome) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO usage_ledger (session_id, tokens_in, tokens_out, tools, guard,"
                " latency_ms, prompt_version, model, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    outcome.tokens_in,
                    outcome.tokens_out,
                    json.dumps(list(outcome.tools), ensure_ascii=False),
                    outcome.guard,
                    outcome.latency_ms,
                    outcome.prompt_version,
                    outcome.model,
                    _now().isoformat(),
                ),
            )
            conn.commit()

    def usage(self, session: Session) -> dict[str, object]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens_in), 0) AS tin, COALESCE(SUM(tokens_out), 0) AS tout,"
                " COUNT(*) AS turnos FROM usage_ledger WHERE session_id = ?",
                (session.session_id,),
            ).fetchone()

        consumed = int(row["tin"]) + int(row["tout"])
        return {
            "tokens_in": int(row["tin"]),
            "tokens_out": int(row["tout"]),
            "tokens_total": consumed,
            "turnos": int(row["turnos"]),
            "budget_tokens": session.budget_tokens,
            "remaining": max(session.budget_tokens - consumed, 0),
        }

    # --- mensagens -------------------------------------------------------

    def append_user_message(self, session_id: str, content: str) -> int:
        return self._append(session_id, "user", content)

    def append_assistant_message(self, session_id: str, outcome: TurnOutcome) -> int:
        return self._append(
            session_id,
            "assistant",
            outcome.answer,
            guard=outcome.guard,
            latency_ms=outcome.latency_ms,
        )

    def _append(
        self,
        session_id: str,
        role: str,
        content: str,
        guard: str | None = None,
        latency_ms: int | None = None,
    ) -> int:
        with closing(self._connect()) as conn:
            cursor = conn.execute(
                "INSERT INTO messages (session_id, role, content, guard, created_at, latency_ms)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, role, content, guard, _now().isoformat(), latency_ms),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def messages(self, session_id: str) -> list[dict[str, object]]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT message_id, role, content, guard, created_at, latency_ms"
                " FROM messages WHERE session_id = ? ORDER BY message_id",
                (session_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # --- limites ---------------------------------------------------------

    def recent_turns(self, session_id: str, window_seconds: int = 60) -> int:
        """Mensagens do usuario na janela: base do rate limit por sessao."""
        cutoff = (_now() - timedelta(seconds=window_seconds)).isoformat()
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM messages"
                " WHERE session_id = ? AND role = 'user' AND created_at > ?",
                (session_id, cutoff),
            ).fetchone()
        return int(row[0])

    def register_creation(self, client_ip: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT INTO session_creations (client_ip, created_at) VALUES (?, ?)",
                (client_ip, _now().isoformat()),
            )
            conn.commit()

    def creations_by_ip(self, client_ip: str, window_minutes: int = 60) -> int:
        cutoff = (_now() - timedelta(minutes=window_minutes)).isoformat()
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM session_creations"
                " WHERE client_ip = ? AND created_at > ?",
                (client_ip, cutoff),
            ).fetchone()
        return int(row[0])
