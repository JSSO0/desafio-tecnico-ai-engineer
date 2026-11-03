"""Recuperacao das politicas da loja: BM25 nativo do SQLite (FTS5), por bloco do manual.

Tres decisoes que valem registro:

1. **A consulta e sanitizada antes de virar expressao FTS.** `MATCH` tem sintaxe propria
   (`"`, `*`, `NEAR`, `OR`, `-`), entao texto livre do cliente quebra a busca — e um cliente
   malicioso poderia injetar operadores. Cada termo e normalizado e citado; nada e concatenado
   cru na expressao. Mesma disciplina de consulta parametrizada.
2. **Prefixo de 6 caracteres como stemming barato de portugues.** Sem stemmer, "devolver" nao
   casa com "devolucao". Cada termo longo entra duas vezes (termo exato + prefixo), e o BM25
   ordena o ruido.
3. **Re-rank por cobertura ponderada por IDF.** BM25 puro premia documento curto e termo
   frequente: "compra" aparece em varios blocos e ofusca "devolucao", que e o sinal real.
   Com 25 blocos, o IDF e calculavel na hora e corrige isso sem dependencia externa.
"""

from __future__ import annotations

import math
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.text import normalize

MAX_TERMOS = 12
PREFIXO_MIN = 5
CANDIDATOS_MIN = 10
TITULO_BOOST = 2.0

STOPWORDS_PATH = Path(__file__).with_name("stopwords.txt")


@lru_cache
def load_stopwords() -> frozenset[str]:
    """Stopwords live in a file because they are domain data, tuned by observation."""
    lines = STOPWORDS_PATH.read_text(encoding="utf-8").splitlines()
    return frozenset(
        palavra
        for line in lines
        if not line.lstrip().startswith("#")
        for palavra in line.split()
    )


STOPWORDS = load_stopwords()

_TERMO = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class PolicyHit:
    secao: str
    secao_pai: str
    title: str
    text: str
    pagina: int | None
    versao: str | None
    score: float
    coverage: float

    def to_dict(self) -> dict[str, object]:
        return {
            "secao": self.secao,
            "secao_pai": self.secao_pai,
            "titulo": self.title,
            "texto": self.text,
            "pagina": self.pagina,
            "versao": self.versao,
            "score": self.score,
        }


def extract_terms(question: str) -> list[str]:
    terms = [
        term
        for term in _TERMO.findall(normalize(question))
        if len(term) >= 2 and term not in STOPWORDS
    ]
    return list(dict.fromkeys(terms))[:MAX_TERMOS]


def build_query(question: str) -> str:
    """Turns free text into a safe FTS expression. Returns "" when there is no usable term."""
    terms = extract_terms(question)
    if not terms:
        return ""

    expressions: list[str] = []
    for term in terms:
        expressions.append(f'"{term}"')
        if len(term) >= PREFIXO_MIN:
            expressions.append(f'"{term[:PREFIXO_MIN]}"*')
    return " OR ".join(expressions)


def _prefix(term: str) -> str:
    return term[:PREFIXO_MIN] if len(term) >= PREFIXO_MIN else term


def _term_weights(conn: sqlite3.Connection, terms: list[str]) -> dict[str, float]:
    """IDF over the manual blocks: a rare term weighs more than an omnipresent one."""
    total = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] or 1
    weights: dict[str, float] = {}
    for term in terms:
        prefixo = _prefix(term)
        expression = f'"{prefixo}"*' if len(term) >= PREFIXO_MIN else f'"{term}"'
        df = conn.execute(
            "SELECT COUNT(*) FROM policies_fts WHERE policies_fts MATCH ?", (expression,)
        ).fetchone()[0]
        weights[term] = math.log(1 + total / max(df, 1))
    return weights


def search_policies(conn: sqlite3.Connection, question: str, limit: int = 3) -> list[PolicyHit]:
    terms = extract_terms(question)
    query = build_query(question)
    if not query:
        return []

    limit = max(1, min(limit, 5))
    weights = _term_weights(conn, terms)
    rows = conn.execute(
        """
        SELECT p.secao, p.secao_pai, p.titulo, p.texto, p.pagina, p.versao,
               round(bm25(policies_fts), 4) AS score
        FROM policies_fts
        JOIN policies p ON p.policy_id = policies_fts.rowid
        WHERE policies_fts MATCH ?
        ORDER BY bm25(policies_fts)
        LIMIT ?
        """,
        (query, max(limit * 4, CANDIDATOS_MIN)),
    ).fetchall()

    candidates: list[PolicyHit] = []
    for row in rows:
        haystack = normalize(f"{row['titulo']} {row['texto']}")
        title = normalize(row["titulo"])
        coverage = sum(
            weight * (TITULO_BOOST if _prefix(term) in title else 1.0)
            for term, weight in weights.items()
            if _prefix(term) in haystack
        )
        candidates.append(
            PolicyHit(
                secao=row["secao"],
                secao_pai=row["secao_pai"],
                title=row["titulo"],
                text=row["texto"],
                pagina=row["pagina"],
                versao=row["versao"],
                score=row["score"],
                coverage=round(coverage, 4),
            )
        )

    candidates.sort(key=lambda hit: (-hit.coverage, hit.score))
    return candidates[:limit]
