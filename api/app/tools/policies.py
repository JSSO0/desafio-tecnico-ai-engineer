from __future__ import annotations

import sqlite3

from langchain.tools import tool

from app.rag.policies import search_policies


def make_policy_tools(conn: sqlite3.Connection):
    @tool
    def consultar_politicas(pergunta: str, limite: int = 3) -> dict[str, object]:
        """Regras da loja: trocas, devolucoes, frete, pagamento, garantia, horario, privacidade.

        Use para qualquer duvida de procedimento ("posso devolver?", "aceita pix?",
        "qual o prazo de entrega?"). Devolve os trechos do manual com secao e pagina.

        Args:
            pergunta: a duvida do cliente em linguagem natural.
            limite: quantos trechos devolver (1 a 5, padrao 3).
        """
        hits = search_policies(conn, pergunta, limit=limite)

        if not hits:
            return {
                "encontrado": False,
                "instrucao": "Nao ha regra para isso no manual. Diga que vai confirmar com a"
                " gerencia antes de responder (politica 10). Nao invente prazo nem condicao.",
            }

        return {
            "encontrado": True,
            "trechos": [
                {**hit.to_dict(), "citacao": f"Politica §{hit.secao}"} for hit in hits
            ],
        }

    return [consultar_politicas]
