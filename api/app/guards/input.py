"""Triagem da mensagem antes de gastar token.

Duas coisas ficam no codigo, nao no prompt: limite de tamanho (custo previsivel) e tentativa
explicita de desviar o assistente (defesa em profundidade — o modelo ja recusou no teste, mas
recusar antes economiza tokens e deixa rastro na auditoria).

Escopo e acessorio **nao** passam por aqui. "Voces vendem cordas?" e uma pergunta legitima de
cliente e a resposta certa e redirecionar com educacao, nao bloquear. Regra por palavra-chave
erraria o tom e negaria atendimento a quem tem duvida real.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CHARS = 800

_INJECTION = (
    re.compile(r"ignor[ea]\s+(todas\s+)?(as\s+)?(instru|orienta|regra)", re.IGNORECASE),
    re.compile(r"esque[cç]a\s+(todas\s+)?(as\s+)?(instru|regra)", re.IGNORECASE),
    re.compile(r"(system|prompt)\s+(prompt|do sistema|message)", re.IGNORECASE),
    re.compile(r"you are now|finja que (voc[eê]|voce) [eé]", re.IGNORECASE),
    re.compile(r"modo (desenvolvedor|dev|admin)", re.IGNORECASE),
    re.compile(r"revele?\s+(suas|as)\s+instru", re.IGNORECASE),
    re.compile(r"jailbreak|dan mode", re.IGNORECASE),
)

RECUSA_INJECTION = (
    "Não consigo seguir esse tipo de pedido, mas posso ajudar com instrumentos: "
    "catálogo, preço, pedido, troca ou frete. O que você precisa?"
)


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    code: str | None = None
    response: str | None = None


def screen(message: str) -> Verdict:
    texto = (message or "").strip()

    if len(texto) > MAX_CHARS:
        return Verdict(
            allowed=False,
            code="message_too_long",
            response=f"Mensagem muito longa ({len(texto)} caracteres). O limite é {MAX_CHARS}.",
        )

    if any(padrao.search(texto) for padrao in _INJECTION):
        return Verdict(allowed=False, code="injection_attempt", response=RECUSA_INJECTION)

    return Verdict(allowed=True)
