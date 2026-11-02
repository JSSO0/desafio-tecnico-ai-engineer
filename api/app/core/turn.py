from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnOutcome:
    """O que um turno produziu, num objeto so.

    Antes disto, gravar consumo e auditoria exigia passar de 10 a 12 argumentos em cada chamada,
    repetindo os mesmos campos em tres lugares. Aqui o turno e um valor: quem persiste recebe o
    objeto, nao a lista de campos. Acrescentar um campo novo passa a tocar um lugar so.
    """

    answer: str
    tools: tuple[str, ...] = ()
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    guard: str | None = None
    prompt_version: str = ""
    model: str = ""