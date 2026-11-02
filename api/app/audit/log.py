"""Trilha de auditoria: uma linha JSON por turno, com PII mascarada.

O que fica registrado e o suficiente para reconstruir a decisao (quais ferramentas, que guard,
quantos tokens, qual prompt) sem guardar dado pessoal em claro. A politica de privacidade da
loja (secao 9) e a LGPD pedem minimizacao: telefone e e-mail nunca vao para o arquivo.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_PHONE = re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}[-.\s]?\d{4}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")


def redact(text: str) -> str:
    """Mascara telefone e e-mail. Aplicado antes de qualquer escrita em disco."""
    sem_email = _EMAIL.sub("[email]", text or "")
    return _PHONE.sub("[telefone]", sem_email)


def audit_event(
    *,
    logs_dir: Path,
    request_id: str,
    session_id: str,
    customer_id: int | None,
    message: str,
    tools: list[str],
    guard: str | None,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    prompt_version: str,
    model: str,
) -> None:
    registro = {
        "ts": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "session_id": session_id,
        "customer_id": customer_id,
        "message_chars": len(message),
        "message": redact(message),
        "tools": tools,
        "guard": guard,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "prompt_version": prompt_version,
        "model": model,
    }

    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        arquivo = logs_dir / f"audit-{datetime.now(UTC):%Y-%m-%d}.jsonl"
        with arquivo.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except OSError:
        # auditoria nao pode derrubar atendimento; a falha fica no log da aplicacao
        logger.exception("nao foi possivel escrever a trilha de auditoria")
