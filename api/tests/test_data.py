import csv
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.core.errors import DataSourceError
from app.db.build import build_database, data_quality_report, load_policies


def _copy_data(data_dir: Path, destination: Path) -> Path:
    destination = destination / "data"
    shutil.copytree(data_dir, destination)
    return destination


def _products_csv(data_dir: Path) -> Path:
    return next(data_dir.glob("* - products.csv"))


def test_counts_match_source_files(
    tmp_path: Path, data_dir: Path, policies_dir: Path
) -> None:
    report = build_database(tmp_path / "loja.db", data_dir, policies_dir)

    assert report["categories"] == 9
    assert report["products"] == 65
    assert report["customers"] == 50
    assert report["orders"] == 20
    assert report["order_items"] == 22
    assert report["promotions"] == 25
    assert report["policies"] == len(load_policies(policies_dir))
    assert report["integridade"] is True


def test_rebuild_is_idempotent(
    tmp_path: Path, data_dir: Path, policies_dir: Path
) -> None:
    banco = tmp_path / "loja.db"
    primeiro = build_database(banco, data_dir, policies_dir)
    segundo = build_database(banco, data_dir, policies_dir)

    assert primeiro == segundo
    with closing(sqlite3.connect(banco)) as conn:
        policies = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
        indexados = conn.execute("SELECT COUNT(*) FROM policies_fts").fetchone()[0]
    assert policies == indexados


def test_build_fails_loudly_on_invalid_specs_json(
    tmp_path: Path, data_dir: Path, policies_dir: Path
) -> None:
    copia = _copy_data(data_dir, tmp_path)
    products = _products_csv(copia)
    with products.open(encoding="utf-8-sig", newline="") as handle:
        leitor = csv.DictReader(handle)
        campos = leitor.fieldnames or []
        lines = list(leitor)
    lines[0]["specs"] = "{isto nao e json"
    with products.open("w", encoding="utf-8", newline="") as handle:
        escritor = csv.DictWriter(handle, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(lines)

    with pytest.raises(DataSourceError, match="specs invalido no produto"):
        build_database(tmp_path / "loja.db", copia, copia / "policies")


def test_build_fails_loudly_when_source_csv_is_missing(
    tmp_path: Path, data_dir: Path, policies_dir: Path
) -> None:
    copia = _copy_data(data_dir, tmp_path)
    next(copia.glob("* - categories.csv")).unlink()

    with pytest.raises(DataSourceError, match="categories"):
        build_database(tmp_path / "loja.db", copia, copia / "policies")


def test_every_policy_chunk_is_indexed(conn: sqlite3.Connection) -> None:
    policies = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    indexed = conn.execute("SELECT COUNT(*) FROM policies_fts").fetchone()[0]

    assert policies == indexed


def test_policy_chunks_carry_complete_provenance(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT secao, titulo, texto, pagina, versao FROM policies"
    ).fetchall()

    assert len(rows) == 25
    for secao, titulo, text, pagina, versao in rows:
        assert secao
        assert titulo
        assert text.strip()
        assert pagina is not None and 1 <= pagina <= 10
        assert versao == "2.1"


def test_policy_loader_fails_when_directory_is_empty(tmp_path: Path) -> None:
    with pytest.raises(DataSourceError, match="nenhuma politica"):
        load_policies(tmp_path)


@pytest.mark.parametrize(
    ("term", "secao"),
    [
        ("devolucao", "4.1"),
        ("arrependimento", "4.1"),
        ("horario funcionamento", "2"),
        ("parcelamento", "3.1"),
        ("rastreamento", "5.3"),
        ("garantia", "8.1"),
        ("acessorios", "1"),
    ],
)
def test_fts_retrieves_expected_section(conn: sqlite3.Connection, term: str, secao: str) -> None:
    rows = conn.execute(
        "SELECT secao FROM policies_fts"
        " WHERE policies_fts MATCH ? ORDER BY bm25(policies_fts) LIMIT 3",
        (term,),
    ).fetchall()

    assert rows, f"nenhum resultado para {term!r}"
    assert secao in {row[0] for row in rows}, f"{term!r} nao trouxe a secao {secao}"


def test_fts_handles_accented_query(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT secao FROM policies_fts"
        " WHERE policies_fts MATCH ? ORDER BY bm25(policies_fts) LIMIT 1",
        ("devolução",),
    ).fetchall()

    assert rows[0][0] == "4.1"


def test_view_keeps_inactive_promotion_out_of_final_price(conn: sqlite3.Connection) -> None:
    price_brl, price_final, promo = conn.execute(
        "SELECT price_brl, price_final, promo_percent FROM v_products WHERE product_id = 95"
    ).fetchone()

    assert price_brl == pytest.approx(2199.0)
    assert promo is None
    assert price_final == pytest.approx(2199.0)


def test_view_applies_active_promotion(conn: sqlite3.Connection) -> None:
    price_brl, price_final, promo = conn.execute(
        "SELECT price_brl, price_final, promo_percent FROM v_products WHERE product_id = 127"
    ).fetchone()

    assert promo == pytest.approx(10.0)
    assert price_final == pytest.approx(round(price_brl * 0.9, 2))


def test_every_active_promotion_is_reflected_in_the_view(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT price_brl, price_final, promo_percent FROM v_products"
        " WHERE promo_percent IS NOT NULL"
    ).fetchall()

    assert rows, "esperava promocoes ativas na base"
    for price_brl, price_final, promo in rows:
        assert promo > 0
        assert price_final == pytest.approx(round(price_brl * (1 - promo / 100), 2))


def test_inactive_promotions_never_reach_the_view(conn: sqlite3.Connection) -> None:
    produtos_com_promo_inativa = conn.execute(
        """
        SELECT v.product_id
        FROM v_products v
        WHERE v.product_id IN (SELECT product_id FROM promotions WHERE is_active = 0)
          AND v.product_id NOT IN (SELECT product_id FROM promotions WHERE is_active = 1)
        """
    ).fetchall()

    assert produtos_com_promo_inativa
    for (product_id,) in produtos_com_promo_inativa:
        promo = conn.execute(
            "SELECT promo_percent FROM v_products WHERE product_id = ?", (product_id,)
        ).fetchone()[0]
        assert promo is None


def test_stock_is_current_snapshot_not_history(conn: sqlite3.Connection) -> None:
    """Pedido 4 (entregue) contem o produto 96, hoje com estoque 0. Nao inferir falta na epoca."""
    stock = conn.execute(
        "SELECT stock_quantity FROM products WHERE product_id = 96"
    ).fetchone()[0]
    no_pedido = conn.execute(
        "SELECT COUNT(*) FROM order_items WHERE order_id = 4 AND product_id = 96"
    ).fetchone()[0]

    assert stock == 0
    assert no_pedido == 1


def test_eighteen_customers_have_orders(conn: sqlite3.Connection) -> None:
    com_pedido = conn.execute("SELECT COUNT(DISTINCT customer_id) FROM orders").fetchone()[0]

    assert com_pedido == 18


def test_customer_phone_is_normalized(conn: sqlite3.Connection) -> None:
    digits = conn.execute("SELECT phone_digits FROM customers WHERE customer_id = 3").fetchone()[0]

    assert digits == "67984321098"


def test_data_quality_report_flags_known_divergences(conn: sqlite3.Connection) -> None:
    report = data_quality_report(conn)

    assert [item["order_id"] for item in report["totais_divergentes"]] == [3, 20]
    assert [item["category_id"] for item in report["categorias_sem_produto"]] == [6, 7, 8]


def test_data_quality_report_never_corrects_the_source(conn: sqlite3.Connection) -> None:
    report = data_quality_report(conn)
    pedido_3 = conn.execute("SELECT total_brl FROM orders WHERE order_id = 3").fetchone()[0]

    assert pedido_3 == pytest.approx(3450.0)
    assert report["totais_divergentes"][0]["soma_itens"] == pytest.approx(3498.0)


def test_connection_is_read_only(conn: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM products")
