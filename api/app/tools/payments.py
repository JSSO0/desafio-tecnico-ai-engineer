from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from langchain.tools import tool

from app.core.text import brl

DESCONTO_PIX = Decimal("5")
PARCELA_MINIMA = ((3, Decimal("0")), (6, Decimal("80")), (12, Decimal("100")))
FORMA_MINIMA_3X = Decimal("50")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _min_per_installment(count: int) -> tuple[Decimal, bool]:
    """(minimum per installment, whether a minimum total applies) per policy 3.1."""
    if count <= 3:
        return Decimal("0"), True
    if count <= 6:
        return PARCELA_MINIMA[1][1], False
    return PARCELA_MINIMA[2][1], False


def allowed_installments(total: Decimal) -> list[int]:
    """Which installment counts the rule allows. Computed here: the model must not guess."""
    permitidas: list[int] = []
    for count in range(1, 13):
        minimum, exige_minimo_total = _min_per_installment(count)
        if exige_minimo_total and total < FORMA_MINIMA_3X:
            continue
        if _money(total / count) >= minimum:
            permitidas.append(count)
    return permitidas


def make_payment_tools():
    @tool
    def simulate_payment(
        amount: float,
        method: str,
        installments: int = 1,
        promo_price: bool = False,
    ) -> dict[str, object]:
        """Aplica as regras de pagamento da loja sobre um valor.

        Use para responder desconto no PIX e se um parcelamento e permitido. O valor nao muda:
        e o mesmo do produto informado por outra ferramenta.

        Args:
            valor: valor em reais do produto ou pedido.
            forma: pix, debito, credito ou boleto.
            parcelas: numero de parcelas no credito (1 a 12).
            preco_ja_promocional: True quando o valor ja tem desconto de promocao ativa
                (o desconto de PIX nao se acumula sobre preco promocional).
        """
        method = (method or "").strip().lower()
        if method not in {"pix", "debito", "credito", "boleto"}:
            return {
                "permitido": False,
                "motivo": "forma de pagamento desconhecida",
                "formas_aceitas": ["pix", "debito", "credito", "boleto"],
            }

        base = _money(Decimal(str(amount)))
        if base <= 0:
            return {"permitido": False, "motivo": "valor invalido"}

        notes: list[str] = []
        discount = Decimal("0")
        final_amount = base

        if method == "pix":
            if promo_price:
                notes.append(
                    "O desconto de PIX nao se aplica sobre preco ja promocional (politica §6.2)."
                )
            else:
                discount = DESCONTO_PIX
                final_amount = _money(base * (1 - discount / 100))

            if base > Decimal("2000"):
                notes.append(
                    "Acima de R$ 2.000,00 e permitido combinar formas de pagamento (politica §3.1)."
                )
            return {
                "permitido": True,
                "forma": "pix",
                "valor_base": brl(base),
                "desconto_percent": float(discount),
                "valor_final": brl(final_amount),
                "observacoes": notes,
            }

        if method in {"debito", "boleto"}:
            if int(installments) > 1:
                return {
                    "permitido": False,
                    "motivo": f"{method} e a vista, em parcela unica (politica §3).",
                }
            if method == "boleto":
                notes.append("Compensacao em ate 3 dias uteis (politica §3).")
            return {
                "permitido": True,
                "forma": method,
                "valor_base": brl(base),
                "valor_final": brl(base),
                "observacoes": notes,
            }

        # credito
        installments = int(installments)
        if not 1 <= installments <= 12:
            return {
                "permitido": False,
                "motivo": "O cartao de credito parcela de 1 a 12 vezes (politica §3).",
            }

        if installments <= 3:
            minimum = PARCELA_MINIMA[0][1]
            if base < FORMA_MINIMA_3X:
                return {
                    "permitido": False,
                    "motivo": (
                        "Parcelamento em ate 3x nao vale para compras abaixo de R$ 50,00"
                        " (politica §3.1)."
                    ),
                }
        elif installments <= 6:
            minimum = PARCELA_MINIMA[1][1]
        else:
            minimum = PARCELA_MINIMA[2][1]

        per_installment = _money(base / installments)
        if per_installment < minimum:
            return {
                "permitido": False,
                "motivo": (
                    f"Em {installments}x cada parcela ficaria em {brl(per_installment)},"
                    f" abaixo do minimo de {brl(minimum)} para essa faixa."
                    " Parcelas menores sao possiveis."
                ),
                "valor_final": brl(base),
                "parcelas_permitidas": allowed_installments(base),
            }

        notes.append("Parcelamento sem juros (politica §3).")
        return {
            "permitido": True,
            "forma": "credito",
            "valor_base": brl(base),
            "valor_final": brl(base),
            "parcelas": installments,
            "valor_parcela": brl(per_installment),
            "parcela_minima_aplicada": brl(minimum),
            "parcelas_permitidas": allowed_installments(base),
            "observacoes": notes,
        }

    return [simulate_payment]
