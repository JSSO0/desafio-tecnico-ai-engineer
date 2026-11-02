from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

_NON_DIGIT = re.compile(r"\D")


def normalize(text: str) -> str:
    """Minusculas e sem acento, para comparar texto livre com os dados da loja."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def only_digits(value: str) -> str:
    return _NON_DIGIT.sub("", value or "")


def brl(value: float | Decimal) -> str:
    """Formata 2199.0 como 'R$ 2.199,00' — o modelo deve copiar, nao calcular."""
    whole, _, cents = f"{Decimal(str(value)):.2f}".partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return f"R$ {'.'.join(groups)},{cents}"
