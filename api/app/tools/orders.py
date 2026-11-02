from __future__ import annotations

import sqlite3

from langchain.tools import tool

from app.agent.session import SessionContext
from app.core.text import brl, only_digits

_STATUS_LABEL = {
    "pending": "pendente",
    "confirmed": "confirmado",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}


def _order_row(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    items = conn.execute(
        """
        SELECT i.quantity, p.name, p.price_brl
        FROM order_items i JOIN products p ON p.product_id = i.product_id
        WHERE i.order_id = ? ORDER BY p.name
        """,
        (row["order_id"],),
    ).fetchall()

    soma = sum(item["quantity"] * item["price_brl"] for item in items)
    pedido: dict[str, object] = {
        "pedido": row["order_id"],
        "status": _STATUS_LABEL.get(row["status"], row["status"]),
        "data": row["order_date"],
        "total": brl(row["total_brl"]),
        "pagamento": row["payment_method"],
        "itens": [
            {"produto": item["name"], "quantidade": item["quantity"]} for item in items
        ],
    }
    if row["tracking_code"]:
        pedido["rastreio"] = row["tracking_code"]
    if row["estimated_delivery"]:
        pedido["previsao_entrega"] = row["estimated_delivery"]
    if row["notes"]:
        pedido["observacao"] = row["notes"]
    if abs(soma - row["total_brl"]) > 0.01:
        # divergencia conhecida da base: reportar o total gravado, nunca recalcular
        pedido["total_divergente"] = True
        pedido["instrucao"] = (
            "O total gravado difere da soma dos itens. Informe o total do pedido e, se o cliente"
            " questionar, diga que vai confirmar com a equipe."
        )
    return pedido


def make_order_tools(conn: sqlite3.Connection, session: SessionContext):
    @tool
    def identificar_cliente(telefone: str) -> dict[str, object]:
        """Identifica o cliente pelo telefone e vincula este atendimento a ele.

        Use antes de qualquer consulta de pedido. Nunca peca CPF.

        Args:
            telefone: telefone informado pelo cliente, com ou sem formatacao.
        """
        digits = only_digits(telefone)
        if digits.startswith("55") and len(digits) > 11:
            digits = digits[2:]

        if len(digits) < 10:
            return {
                "identificado": False,
                "motivo": "telefone incompleto",
                "instrucao": "Peca o telefone com DDD.",
            }

        row = conn.execute(
            "SELECT customer_id, name, city FROM customers WHERE phone_digits = ?", (digits,)
        ).fetchone()

        if row is None:
            session.customer_id = None
            session.customer_name = None
            return {
                "identificado": False,
                "instrucao": "Nao encontrei cadastro com esse telefone. Peca para conferir o numero"
                " usado na compra; nao invente dados de cliente.",
            }

        session.customer_id = row["customer_id"]
        session.customer_name = row["name"]
        return {
            "identificado": True,
            "nome": row["name"],
            "primeiro_nome": row["name"].split()[0],
            "cidade": row["city"],
        }

    @tool
    def consultar_pedido(order_id: int | None = None) -> dict[str, object]:
        """Pedidos do cliente ja identificado: status, itens, rastreio e previsao.

        Sem order_id, lista todos os pedidos do cliente. So consulta pedidos do cliente
        vinculado a este atendimento.

        Args:
            order_id: numero do pedido, quando o cliente informar.
        """
        if not session.identified:
            return {
                "erro": "cliente_nao_identificado",
                "instrucao": "Peca o telefone do cadastro e chame identificar_cliente antes.",
            }

        if order_id is None:
            rows = conn.execute(
                "SELECT * FROM orders WHERE customer_id = ? ORDER BY order_date DESC",
                (session.customer_id,),
            ).fetchall()
            if not rows:
                return {
                    "encontrado": False,
                    "mensagem": "Nenhum pedido encontrado para este cadastro.",
                }
            return {"encontrado": True, "pedidos": [_order_row(conn, row) for row in rows]}

        row = conn.execute(
            "SELECT * FROM orders WHERE order_id = ? AND customer_id = ?",
            (int(order_id), session.customer_id),
        ).fetchone()

        if row is None:
            # mesma resposta para "nao existe" e "nao e seu": nao confirma existencia
            return {
                "encontrado": False,
                "mensagem": "Nao encontrei esse pedido no cadastro deste cliente.",
            }

        return {"encontrado": True, "pedido": _order_row(conn, row)}

    return [identificar_cliente, consultar_pedido]
