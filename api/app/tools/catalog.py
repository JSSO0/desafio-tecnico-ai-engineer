from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

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


@dataclass(frozen=True)
class CatalogFilter:
    """Catalogue filter as an object: five optional fields do not become five parameters."""

    term: str | None = None
    category: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    only_available: bool = True


def _where(catalog_filter: CatalogFilter) -> tuple[str, list[object]]:
    """Clausula e parametros na ordem certa. Pura, testavel sem banco."""
    clauses: list[str] = []
    params: list[object] = []

    if catalog_filter.term:
        clauses.append("(instr(unaccent(name), ?) > 0 OR instr(unaccent(description), ?) > 0)")
        params.extend([normalize(catalog_filter.term), normalize(catalog_filter.term)])
    if catalog_filter.category:
        clauses.append("(instr(unaccent(category_name), ?) > 0 OR CAST(category_id AS TEXT) = ?)")
        params.extend([normalize(catalog_filter.category), catalog_filter.category.strip()])
    if catalog_filter.min_price is not None:
        clauses.append("price_final >= ?")
        params.append(float(catalog_filter.min_price))
    if catalog_filter.max_price is not None:
        clauses.append("price_final <= ?")
        params.append(float(catalog_filter.max_price))
    if catalog_filter.only_available:
        clauses.append("stock_quantity > 0 AND status = 'active'")

    return (f" WHERE {' AND '.join(clauses)}" if clauses else ""), params


def make_catalog_tools(conn: sqlite3.Connection):
    # Excecao consciente ao limite de parametros: a assinatura e o schema que o modelo le.
    # Aninhar em um objeto trocaria a legibilidade do modelo por estetica de assinatura.
    @tool
    def search_products(  # noqa: PLR0913
        query: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        only_available: bool = True,
        limit: int = 8,
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
        where, params = _where(
            CatalogFilter(query, category, min_price, max_price, only_available)
        )
        limit = max(1, min(int(limit), 20))

        total = conn.execute(f"SELECT COUNT(*) FROM v_products{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {_COLUMNS} FROM v_products{where} ORDER BY price_final LIMIT ?",
            [*params, limit],
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
    def product_detail(name_or_id: str) -> dict[str, object]:
        """Detalhe de um produto: preco, estoque, especificacoes e promocao ativa.

        Use quando o cliente cita um modelo especifico ("quanto custa o Takamine GD20?").

        Args:
            nome_ou_id: nome (parcial serve) ou id numerico do produto.
        """
        raw = (name_or_id or "").strip()
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

    return [search_products, product_detail]
