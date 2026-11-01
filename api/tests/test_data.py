import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.db.build import build_database, data_quality_report, load_policies

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
POLICIES_DIR = DATA_DIR / "policies"


@pytest.fixture(scope="module")
def db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("data") / "loja.db"
    build_database(path, DATA_DIR, POLICIES_DIR)
    return path


@pytest.fixture(scope="module")
def conn(db_path: Path):
    with closing(sqlite3.connect(db_path)) as connection:
        yield connection


def test_counts_match_source_files(db_path: Path) -> None:
    report = build_database(db_path.with_name("counts.db"), DATA_DIR, POLICIES_DIR)

    assert report["categories"] == 9
    assert report["products"] == 65
    assert report["customers"] == 50
    assert report["orders"] == 20
    assert report["order_items"] == 22
    assert report["promotions"] == 25
    assert report["policies"] == len(load_policies(POLICIES_DIR))
    assert report["integridade"] is True


def test_every_policy_chunk_is_indexed(conn: sqlite3.Connection) -> None:
    policies = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    indexed = conn.execute("SELECT COUNT(*) FROM policies_fts").fetchone()[0]

    assert policies == indexed


@pytest.mark.parametrize(
    ("termo", "secao"),
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
def test_fts_retrieves_expected_section(conn: sqlite3.Connection, termo: str, secao: str) -> None:
    rows = conn.execute(
        "SELECT secao FROM policies_fts"
        " WHERE policies_fts MATCH ? ORDER BY bm25(policies_fts) LIMIT 3",
        (termo,),
    ).fetchall()

    assert rows, f"nenhum resultado para {termo!r}"
    assert secao in {row[0] for row in rows}, f"{termo!r} nao trouxe a secao {secao}"


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


def test_customer_phone_is_normalized(conn: sqlite3.Connection) -> None:
    digits = conn.execute("SELECT phone_digits FROM customers WHERE customer_id = 3").fetchone()[0]

    assert digits == "67984321098"


def test_data_quality_report_flags_known_divergences(conn: sqlite3.Connection) -> None:
    report = data_quality_report(conn)

    assert [item["order_id"] for item in report["totais_divergentes"]] == [3, 20]
    assert [item["category_id"] for item in report["categorias_sem_produto"]] == [6, 7, 8]
