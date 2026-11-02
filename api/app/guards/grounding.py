"""Gate de saida: valor em reais so passa se estiver ancorado em resultado de ferramenta.

Nao e instrucao no prompt — e verificacao no codigo. Se a resposta cita um valor que nenhuma
ferramenta devolveu no turno, ela e substituida por uma resposta segura. Isso cobre tanto
alucinacao quanto "preco de memoria" e atende a regra do manual de nunca informar preco sem
consultar o sistema.

Limite conhecido: o gate compara valores, nao intencao. Um numero que coincida com um id de
produto presente na saida da ferramenta passaria. O custo de um falso negativo aqui e baixo;
o de um falso positivo (bloquear resposta correta) seria alto, entao o criterio e permissivo.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

MONEY = re.compile(r"R\$\s*([\d.]{1,15}(?:,\d{1,2})?)")
NUMBER = re.compile(r"\d+(?:[.,]\d{1,2})?")

FALLBACK = (
    "Deixa eu confirmar esses valores no sistema antes de te passar, tá? "
    "Já te respondo com o preço certinho."
)


def _to_decimal(raw: str) -> Decimal | None:
    cleaned = raw.replace(".", "").replace(",", ".") if "," in raw else raw
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def extract_amounts(text: str) -> list[Decimal]:
    """Valores em reais citados no texto, em ordem de aparicao."""
    return [value for match in MONEY.finditer(text or "") if (value := _to_decimal(match.group(1)))]


def grounded_values(tool_output: str) -> set[Decimal]:
    """Todo numero que apareceu em resultado de ferramenta no turno.

    Valores em reais sao lidos primeiro e removidos do texto: sem isso, "R$ 2.199,00" seria
    lido como 2.199 + 00 pelo extrator de numeros soltos, e a resposta certa seria bloqueada.
    """
    text = tool_output or ""
    values: set[Decimal] = set(extract_amounts(text))
    for match in NUMBER.finditer(MONEY.sub(" ", text)):
        value = _to_decimal(match.group(0))
        if value is not None:
            values.add(value)
    return values


def enforce_price_grounding(answer: str, tool_output: str) -> tuple[str, str | None]:
    """Devolve (resposta_final, guard_aplicado). guard_aplicado e None quando nada foi bloqueado."""
    amounts = extract_amounts(answer)
    if not amounts:
        return answer, None

    allowed = grounded_values(tool_output)
    if all(amount in allowed for amount in amounts):
        return answer, None

    return FALLBACK, "preco_sem_ferramenta"
