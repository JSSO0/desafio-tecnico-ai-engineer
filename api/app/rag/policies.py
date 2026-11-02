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
    """Stopwords ficam em arquivo porque sao dado de dominio, ajustado por observacao."""
    linhas = STOPWORDS_PATH.read_text(encoding="utf-8").splitlines()
    return frozenset(
        palavra
        for linha in linhas
        if not linha.lstrip().startswith("#")
        for palavra in linha.split()
    )


STOPWORDS = load_stopwords()

_TERMO = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class PolicyHit:
    secao: str
    secao_pai: str
    title: str
    texto: str
    pagina: int | None
    versao: str | None
    score: float
    coverage: float

    def to_dict(self) -> dict[str, object]:
        return {
            "secao": self.secao,
            "secao_pai": self.secao_pai,
            "titulo": self.title,
            "texto": self.texto,
            "pagina": self.pagina,
            "versao": self.versao,
            "score": self.score,
        }


def extract_terms(question: str) -> list[str]:
    terms = [
        termo
        for termo in _TERMO.findall(normalize(question))
        if len(termo) >= 2 and termo not in STOPWORDS
    ]
    return list(dict.fromkeys(terms))[:MAX_TERMOS]


def build_query(question: str) -> str:
    """Transforma texto livre em expressao FTS segura. Retorna "" quando nao ha termo util."""
    terms = extract_terms(question)
    if not terms:
        return ""

    expressions: list[str] = []
    for termo in terms:
        expressions.append(f'"{termo}"')
        if len(termo) >= PREFIXO_MIN:
            expressions.append(f'"{termo[:PREFIXO_MIN]}"*')
    return " OR ".join(expressions)


def _prefix(termo: str) -> str:
    return termo[:PREFIXO_MIN] if len(termo) >= PREFIXO_MIN else termo


def _term_weights(conn: sqlite3.Connection, terms: list[str]) -> dict[str, float]:
    """IDF sobre os blocos do manual: termo raro pesa mais que termo onipresente."""
    total = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] or 1
    weights: dict[str, float] = {}
    for termo in terms:
        prefixo = _prefix(termo)
        expression = f'"{prefixo}"*' if len(termo) >= PREFIXO_MIN else f'"{termo}"'
        df = conn.execute(
            "SELECT COUNT(*) FROM policies_fts WHERE policies_fts MATCH ?", (expression,)
        ).fetchone()[0]
        weights[termo] = math.log(1 + total / max(df, 1))
    return weights


def search_policies(conn: sqlite3.Connection, question: str, limit: int = 3) -> list[PolicyHit]:
    terms = extract_terms(question)
    query = build_query(question)
    if not query:
        return []

    limite = max(1, min(limit, 5))
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
        (query, max(limite * 4, CANDIDATOS_MIN)),
    ).fetchall()

    candidates: list[PolicyHit] = []
    for row in rows:
        haystack = normalize(f"{row['titulo']} {row['texto']}")
        title = normalize(row["titulo"])
        coverage = sum(
            weight * (TITULO_BOOST if _prefix(termo) in title else 1.0)
            for termo, weight in weights.items()
            if _prefix(termo) in haystack
        )
        candidates.append(
            PolicyHit(
                secao=row["secao"],
                secao_pai=row["secao_pai"],
                title=row["titulo"],
                texto=row["texto"],
                pagina=row["pagina"],
                versao=row["versao"],
                score=row["score"],
                coverage=round(coverage, 4),
            )
        )

    candidates.sort(key=lambda hit: (-hit.coverage, hit.score))
    return candidates[:limite]
