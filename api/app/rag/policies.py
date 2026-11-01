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
import unicodedata
from dataclasses import dataclass

MAX_TERMOS = 12
PREFIXO_MIN = 5
CANDIDATOS_MIN = 10
TITULO_BOOST = 2.0

_STOPWORDS = frozenset(
    " ".join(
        (
            "a ao aos as com como da das de do dos e em entre era essa esse esta este eu foi ha",
            "isso isto ja mais mas me meu minha meus minhas na nao nas no nos o os ou para pela",
            "pelas pelo pelos por pode podem poderia posso pra pro qual quais quando quanto",
            "quantos que quem quero gostaria se sem ser seu sua seus suas so sou tambem tem tenho",
            "ter tu um uma voce voces vou fazer saber preciso onde",
            # cortesia e verbos genericos de pergunta: nao carregam intencao e roubam o topo
            "funciona funcionar funcionamento tempo informacao informacoes duvida duvidas",
            "ajuda obrigado obrigada oi ola favor tudo bem bom boa blz tchau dia dias",
        )
    ).split()
)

_TERMO = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class PolicyHit:
    secao: str
    secao_pai: str
    titulo: str
    texto: str
    pagina: int | None
    versao: str | None
    score: float
    cobertura: float

    def to_dict(self) -> dict[str, object]:
        return {
            "secao": self.secao,
            "secao_pai": self.secao_pai,
            "titulo": self.titulo,
            "texto": self.texto,
            "pagina": self.pagina,
            "versao": self.versao,
            "score": self.score,
        }


def normalize(text: str) -> str:
    """Minusculas e sem acento, para casar com o tokenizer do indice."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def extract_terms(pergunta: str) -> list[str]:
    termos = [
        termo
        for termo in _TERMO.findall(normalize(pergunta))
        if len(termo) >= 2 and termo not in _STOPWORDS
    ]
    return list(dict.fromkeys(termos))[:MAX_TERMOS]


def build_query(pergunta: str) -> str:
    """Transforma texto livre em expressao FTS segura. Retorna "" quando nao ha termo util."""
    termos = extract_terms(pergunta)
    if not termos:
        return ""

    expressoes: list[str] = []
    for termo in termos:
        expressoes.append(f'"{termo}"')
        if len(termo) >= PREFIXO_MIN:
            expressoes.append(f'"{termo[:PREFIXO_MIN]}"*')
    return " OR ".join(expressoes)


def _prefixo(termo: str) -> str:
    return termo[:PREFIXO_MIN] if len(termo) >= PREFIXO_MIN else termo


def _term_weights(conn: sqlite3.Connection, termos: list[str]) -> dict[str, float]:
    """IDF sobre os blocos do manual: termo raro pesa mais que termo onipresente."""
    total = conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0] or 1
    pesos: dict[str, float] = {}
    for termo in termos:
        prefixo = _prefixo(termo)
        expressao = f'"{prefixo}"*' if len(termo) >= PREFIXO_MIN else f'"{termo}"'
        df = conn.execute(
            "SELECT COUNT(*) FROM policies_fts WHERE policies_fts MATCH ?", (expressao,)
        ).fetchone()[0]
        pesos[termo] = math.log(1 + total / max(df, 1))
    return pesos


def search_policies(conn: sqlite3.Connection, pergunta: str, limit: int = 3) -> list[PolicyHit]:
    termos = extract_terms(pergunta)
    query = build_query(pergunta)
    if not query:
        return []

    limite = max(1, min(limit, 5))
    pesos = _term_weights(conn, termos)
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

    candidatos: list[PolicyHit] = []
    for row in rows:
        haystack = normalize(f"{row['titulo']} {row['texto']}")
        titulo = normalize(row["titulo"])
        cobertura = sum(
            peso * (TITULO_BOOST if _prefixo(termo) in titulo else 1.0)
            for termo, peso in pesos.items()
            if _prefixo(termo) in haystack
        )
        candidatos.append(
            PolicyHit(
                secao=row["secao"],
                secao_pai=row["secao_pai"],
                titulo=row["titulo"],
                texto=row["texto"],
                pagina=row["pagina"],
                versao=row["versao"],
                score=row["score"],
                cobertura=round(cobertura, 4),
            )
        )

    candidatos.sort(key=lambda hit: (-hit.cobertura, hit.score))
    return candidatos[:limite]
