import sqlite3

import pytest

from app.rag.policies import (
    _STOPWORDS,
    MAX_TERMOS,
    build_query,
    extract_terms,
    normalize,
    search_policies,
)


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


def test_build_query_caps_the_number_of_terms() -> None:
    pergunta = " ".join(f"termo{indice}" for indice in range(30))

    assert len(extract_terms(pergunta)) == MAX_TERMOS


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


def test_search_handles_accent_and_case_variants(conn: sqlite3.Connection) -> None:
    resultados = [
        tuple(hit.secao for hit in search_policies(conn, texto))
        for texto in ("devolução", "DEVOLUÇÃO", "devolucao")
    ]

    assert resultados[0]
    assert resultados[0] == resultados[1] == resultados[2]


def test_prefix_stemming_matches_verb_and_noun(conn: sqlite3.Connection) -> None:
    """Regressao: com prefixo de 6, 'devolver' nao casava com 'devolucao'."""
    hits = search_policies(conn, "devolver")

    assert "4.1" in {hit.secao for hit in hits}


@pytest.mark.parametrize(
    "pergunta",
    [
        'devolução OR NEAR("x"*)',
        "devolução -compra *",
        "devolução) (compra",
        'devolução "',
    ],
)
def test_search_survives_fts_operators_in_free_text(
    conn: sqlite3.Connection, pergunta: str
) -> None:
    hits = search_policies(conn, pergunta)

    assert "4.1" in {hit.secao for hit in hits}


def test_search_is_bounded_and_ordered(conn: sqlite3.Connection) -> None:
    hits = search_policies(conn, "devolução", limit=2)

    assert 0 < len(hits) <= 2
    assert hits[0].cobertura >= hits[-1].cobertura


def test_search_clamps_limit_to_supported_range(conn: sqlite3.Connection) -> None:
    assert len(search_policies(conn, "devolução", limit=0)) == 1
    assert len(search_policies(conn, "devolução", limit=99)) <= 5


def test_search_is_deterministic(conn: sqlite3.Connection) -> None:
    primeiro = [hit.secao for hit in search_policies(conn, "prazo de garantia")]
    segundo = [hit.secao for hit in search_policies(conn, "prazo de garantia")]

    assert primeiro == segundo
    assert "8.1" in primeiro


def test_search_returns_nothing_for_off_topic(conn: sqlite3.Connection) -> None:
    assert search_policies(conn, "receita de bolo de cenoura") == []


def test_search_returns_nothing_when_only_stopwords_remain(conn: sqlite3.Connection) -> None:
    assert search_policies(conn, "qual é o que a de para mim") == []


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
