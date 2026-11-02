from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from langchain.tools import tool

from app.core.text import brl

DESCONTO_PIX = Decimal("5")
PARCELA_MINIMA = ((3, Decimal("0")), (6, Decimal("80")), (12, Decimal("100")))
FORMA_MINIMA_3X = Decimal("50")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def make_payment_tools():
    @tool
    def simular_pagamento(
        valor: float,
        forma: str,
        parcelas: int = 1,
        preco_ja_promocional: bool = False,
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
        forma = (forma or "").strip().lower()
        if forma not in {"pix", "debito", "credito", "boleto"}:
            return {
                "permitido": False,
                "motivo": "forma de pagamento desconhecida",
                "formas_aceitas": ["pix", "debito", "credito", "boleto"],
            }

        base = _money(Decimal(str(valor)))
        if base <= 0:
            return {"permitido": False, "motivo": "valor invalido"}

        notes: list[str] = []
        discount = Decimal("0")
        final_amount = base

        if forma == "pix":
            if preco_ja_promocional:
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

        if forma in {"debito", "boleto"}:
            if int(parcelas) > 1:
                return {
                    "permitido": False,
                    "motivo": f"{forma} e a vista, em parcela unica (politica §3).",
                }
            if forma == "boleto":
                notes.append("Compensacao em ate 3 dias uteis (politica §3).")
            return {
                "permitido": True,
                "forma": forma,
                "valor_base": brl(base),
                "valor_final": brl(base),
                "observacoes": notes,
            }

        # credito
        parcelas = int(parcelas)
        if not 1 <= parcelas <= 12:
            return {
                "permitido": False,
                "motivo": "O cartao de credito parcela de 1 a 12 vezes (politica §3).",
            }

        if parcelas <= 3:
            minimum = PARCELA_MINIMA[0][1]
            if base < FORMA_MINIMA_3X:
                return {
                    "permitido": False,
                    "motivo": (
                        "Parcelamento em ate 3x nao vale para compras abaixo de R$ 50,00"
                        " (politica §3.1)."
                    ),
                }
        elif parcelas <= 6:
            minimum = PARCELA_MINIMA[1][1]
        else:
            minimum = PARCELA_MINIMA[2][1]

        per_installment = _money(base / parcelas)
        if per_installment < minimum:
            return {
                "permitido": False,
                "motivo": (
                    f"Em {parcelas}x cada parcela ficaria em {brl(per_installment)},"
                    f" abaixo do minimo de {brl(minimum)} para essa faixa."
                    " Parcelas menores sao possiveis."
                ),
                "valor_final": brl(base),
            }

        notes.append("Parcelamento sem juros (politica §3).")
        return {
            "permitido": True,
            "forma": "credito",
            "valor_base": brl(base),
            "valor_final": brl(base),
            "parcelas": parcelas,
            "valor_parcela": brl(per_installment),
            "parcela_minima_aplicada": brl(minimum),
            "observacoes": notes,
        }

    return [simular_pagamento]
