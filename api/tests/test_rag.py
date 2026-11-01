import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.db.build import build_database
from app.db.connection import connect
from app.rag.policies import _STOPWORDS, build_query, extract_terms, normalize, search_policies

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
POLICIES_DIR = DATA_DIR / "policies"


@pytest.fixture(scope="module")
def conn(tmp_path_factory: pytest.TempPathFactory):
    path = tmp_path_factory.mktemp("rag") / "loja.db"
    build_database(path, DATA_DIR, POLICIES_DIR)
    with closing(connect(path)) as connection:
        yield connection


def test_normalize_strips_accents_and_case() -> None:
    assert normalize("Devolução") == "devolucao"


def test_build_query_quotes_terms_and_blocks_fts_operators() -> None:
    query = build_query('devolução OR NEAR("x"*) -compra?')

    assert "OR" not in query.replace(" OR ", "")
    assert '"devolucao"' in query
    assert "NEAR(" not in query


def test_build_query_drops_stopwords_and_returns_empty_for_noise() -> None:
    assert build_query("qual é o que a de") == ""
    assert build_query("???") == ""


@pytest.mark.parametrize(
    ("pergunta", "secao"),
    [
        ("posso devolver minha compra?", "4.1"),
        ("me arrependi da compra online", "4.1"),
        ("qual o horário de funcionamento?", "2"),
        ("vocês vendem cordas e palhetas?", "1"),
        ("posso parcelar em 12 vezes?", "3.1"),
        ("quanto tempo tenho de garantia?", "8.1"),
        ("qual o prazo de entrega para fora da cidade?", "5.2"),
        ("como funciona o desconto no pix?", "3"),
        ("meu pedido não chegou, e o rastreio?", "5.3"),
        ("quero trocar por outro modelo", "4.3"),
        ("quais itens não podem ser trocados?", "4.4"),
    ],
)
def test_search_handles_natural_language(
    conn: sqlite3.Connection, pergunta: str, secao: str
) -> None:
    hits = search_policies(conn, pergunta)

    assert hits, f"nenhum resultado para {pergunta!r}"
    assert secao in {hit.secao for hit in hits}, (
        f"{pergunta!r} deveria trazer §{secao}, trouxe {[h.secao for h in hits]}"
    )


def test_search_is_bounded_and_ordered(conn: sqlite3.Connection) -> None:
    hits = search_policies(conn, "devolução", limit=2)

    assert 0 < len(hits) <= 2
    assert hits[0].cobertura >= hits[-1].cobertura


def test_search_returns_nothing_for_off_topic(conn: sqlite3.Connection) -> None:
    assert search_policies(conn, "receita de bolo de cenoura") == []


def test_hit_carries_provenance(conn: sqlite3.Connection) -> None:
    hit = search_policies(conn, "devolução arrependimento", limit=1)[0]

    assert hit.secao == "4.1"
    assert hit.pagina == 4
    assert hit.versao == "2.1"
    assert "7 (sete) dias corridos" in hit.texto


def test_stopwords_are_clean_tokens() -> None:
    """Regressao: uma lista mal construida virava tokens como "('a" e nada era filtrado."""
    assert "posso" in _STOPWORDS
    assert "funciona" in _STOPWORDS
    sujos = sorted(t for t in _STOPWORDS if not (t.isalpha() or t.isdigit()))
    assert sujos == []


def test_extract_terms_drops_courtesy_and_question_words() -> None:
    assert extract_terms("Ola, bom dia! Como funciona o desconto no pix?") == ["desconto", "pix"]
