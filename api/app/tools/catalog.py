from __future__ import annotations

import json
import sqlite3

from langchain.tools import tool

from app.core.text import brl, normalize

_COLUMNS = (
    "product_id, name, category_id, category_name, price_brl, price_final, "
    "promo_percent, promo_name, stock_quantity, status, description, specs_json"
)


def _product_card(row: sqlite3.Row) -> dict[str, object]:
    card: dict[str, object] = {
        "product_id": row["product_id"],
        "nome": row["name"],
        "categoria": row["category_name"],
        "preco": brl(row["price_brl"]),
        "disponivel": row["stock_quantity"] > 0 and row["status"] == "active",
        "estoque": row["stock_quantity"],
    }
    if row["status"] != "active":
        card["status"] = row["status"]
    if row["promo_percent"] is not None:
        card["promocao"] = row["promo_name"]
        card["desconto_percent"] = row["promo_percent"]
        card["preco_com_desconto"] = brl(row["price_final"])
    return card


def _where(
    termo: str | None,
    categoria: str | None,
    preco_min: float | None,
    preco_max: float | None,
    somente_disponiveis: bool,
) -> tuple[str, list[object]]:
    """Clausula e parametros na ordem certa. Pura, testavel sem banco."""
    clauses: list[str] = []
    params: list[object] = []

    if termo:
        clauses.append("(instr(unaccent(name), ?) > 0 OR instr(unaccent(description), ?) > 0)")
        params.extend([normalize(termo), normalize(termo)])
    if categoria:
        clauses.append("(instr(unaccent(category_name), ?) > 0 OR CAST(category_id AS TEXT) = ?)")
        params.extend([normalize(categoria), categoria.strip()])
    if preco_min is not None:
        clauses.append("price_final >= ?")
        params.append(float(preco_min))
    if preco_max is not None:
        clauses.append("price_final <= ?")
        params.append(float(preco_max))
    if somente_disponiveis:
        clauses.append("stock_quantity > 0 AND status = 'active'")

    return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), params


def make_catalog_tools(conn: sqlite3.Connection):
    @tool
    def buscar_produtos(
        termo: str | None = None,
        categoria: str | None = None,
        preco_min: float | None = None,
        preco_max: float | None = None,
        somente_disponiveis: bool = True,
        limite: int = 8,
    ) -> dict[str, object]:
        """Consulta o catalogo de instrumentos com filtros.

        Use quando o cliente procura algo para comprar: "violao ate 1000", "baixo", "ukulele".
        Filtra pelo preco que o cliente paga (com promocao ativa ja aplicada).

        Args:
            termo: palavra do nome ou da descricao (ignora acento e caixa).
            categoria: nome ou id da categoria (ex.: "Violoes", "5").
            preco_min: preco minimo em reais.
            preco_max: preco maximo em reais.
            somente_disponiveis: se True (padrao), esconde esgotado e descontinuado.
            limite: quantos itens devolver (1 a 20, padrao 8).

        Returns:
            total_encontrado, itens e uma observacao quando nada casa com o filtro.
        """
        where, params = _where(termo, categoria, preco_min, preco_max, somente_disponiveis)
        limite = max(1, min(int(limite), 20))

        total = conn.execute(f"SELECT COUNT(*) FROM v_products{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM v_products{where} ORDER BY price_final LIMIT ?",
            [*params, limite],
        ).fetchall()

        return {
            "total_encontrado": total,
            "retornados": len(rows),
            "produtos": [_product_card(row) for row in rows],
            "observacao": None
            if rows
            else (
                "Nenhum produto atende a esses filtros."
                " Ofereca ajustar o termo ou a faixa de preco."
            ),
        }

    @tool
    def detalhe_produto(nome_ou_id: str) -> dict[str, object]:
        """Detalhe de um produto: preco, estoque, especificacoes e promocao ativa.

        Use quando o cliente cita um modelo especifico ("quanto custa o Takamine GD20?").

        Args:
            nome_ou_id: nome (parcial serve) ou id numerico do produto.
        """
        raw = (nome_ou_id or "").strip()
        row = None

        if raw.isdigit():
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM v_products WHERE product_id = ?", (int(raw),)
            ).fetchone()

        if row is None and not raw.isdigit() and raw:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM v_products"
                " WHERE instr(unaccent(name), ?) > 0 ORDER BY price_final LIMIT 1",
                (normalize(raw),),
            ).fetchone()

        if row is None:
            tokens = [token for token in normalize(raw).split() if len(token) >= 3]
            if tokens:
                clauses = " AND ".join("instr(unaccent(name), ?) > 0" for _ in tokens)
                row = conn.execute(
                    f"SELECT {_COLUMNS} FROM v_products WHERE {clauses}"
                    " ORDER BY price_final LIMIT 1",
                    tokens,
                ).fetchone()

        if row is None:
            return {
                "encontrado": False,
                "instrucao": "Nao encontrei esse produto no catalogo. Nao invente nome nem preco;"
                " ofereca buscar por categoria ou termo parecido.",
            }

        card = _product_card(row)
        card["encontrado"] = True
        card["descricao"] = row["description"]
        if row["specs_json"]:
            card["especificacoes"] = json.loads(row["specs_json"])
        return card

    return [buscar_produtos, detalhe_produto]
