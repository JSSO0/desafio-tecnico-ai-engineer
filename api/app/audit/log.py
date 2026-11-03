"""Trilha de auditoria: uma linha JSON por turno, com PII mascarada.

O que fica registrado e o suficiente para reconstruir a decisao (quais ferramentas, que guard,
quantos tokens, qual prompt) sem guardar dado pessoal em claro. A politica de privacidade da loja
(secao 9) e a LGPD pedem minimizacao: telefone e e-mail nunca vao para o arquivo.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.core.turn import TurnOutcome

logger = logging.getLogger(__name__)

_PHONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}[-.\s]?\d{4}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")


def redact(text: str) -> str:
    """Mascara telefone e e-mail. Aplicado antes de qualquer escrita em disco."""
    sem_email = _EMAIL.sub("[email]", text or "")
    return _PHONE.sub("[telefone]", sem_email)


@dataclass(frozen=True)
class AuditEntry:
    """Quem falou e onde: identidade do registro, separada do que o turno produziu."""

    request_id: str
    session_id: str
    customer_id: int | None
    message: str


def audit_event(logs_dir: Path, entry: AuditEntry, outcome: TurnOutcome) -> None:
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "request_id": entry.request_id,
        "session_id": entry.session_id,
        "customer_id": entry.customer_id,
        "message_chars": len(entry.message),
        "message": redact(entry.message),
        "tools": list(outcome.tools),
        "guard": outcome.guard,
        "tokens_in": outcome.tokens_in,
        "tokens_out": outcome.tokens_out,
        "latency_ms": outcome.latency_ms,
        "prompt_version": outcome.prompt_version,
        "model": outcome.model,
    }

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        audit_path = logs_dir / f"audit-{datetime.now(UTC):%Y-%m-%d}.jsonl"
        with audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        # auditoria nao pode derrubar atendimento; a falha fica no log da aplicacao
        logger.exception("nao foi possivel escrever a trilha de auditoria")