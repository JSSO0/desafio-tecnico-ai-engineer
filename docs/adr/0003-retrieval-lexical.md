# ADR 0003 — Recuperação lexical em vez de embeddings

- **Status:** aceito
- **Data:** 2026-11-02
- **Contexto:** o manual tem 8 páginas convertidas em 25 blocos (seção e subseção) e o catálogo tem
  65 produtos. A pergunta chega em português livre ("me arrependi, posso devolver?", "posso parcelar
  em 12x"). O custo por turno precisa ser baixo e o resultado precisa ser explicável e testável.

## Decisão

Índice **FTS5 do SQLite com BM25** e três correções em cima:

1. **Consulta sanitizada** — cada termo é normalizado e citado antes de virar expressão `MATCH`,
   porque texto livre quebra a sintaxe e permite injetar operadores (`NEAR`, `*`, `-`).
2. **Prefixo de 5 caracteres** como stemming barato de português (`devolver` casa com `devolucao`).
   Com 6 não casava: a raiz muda na sexta letra.
3. **Re-rank por cobertura ponderada por IDF + boost de título** — BM25 puro premia documento curto e
   termo frequente: "compra" ofuscava "devolução" e "tempo" (raro no corpus) pesava mais que
   "garantia". O título usa a taxonomia do próprio manual.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Embeddings + ANN (pgvector, FAISS) | 25 blocos não justificam índice aproximado. Adiciona dependência, custo de embedding na ingestão e mais um serviço para operar — sem ganho mensurável nesta escala. |
| Busca semântica no provedor (retrieval tool) | Custo por consulta, latência e menos controle sobre a citação da seção. |
| Texto inteiro no prompt | ~2.930 tokens por turno contra ~280 com recuperação por seção (−90%). |

## Consequências

- **Custo e latência:** a recuperação é uma consulta SQL local, sem chamada externa.
- **Explicabilidade:** cada trecho carrega `secao`, `pagina`, `versao` e a citação sai pronta.
- **Limite conhecido:** recall depende de vocabulário. "Quero algo para tocar bossa nova" não acha
  nada por BM25 — nesse caso o agente precisa reformular com o cliente, não inventar.
- **Testável sem rede:** 11 perguntas em linguagem natural com seção esperada rodam no `pytest`.

## Com mais tempo

Híbrido: BM25 como recall e embeddings só para reranking dos 10 candidatos. Mantém o custo
controlado e cobre sinonímia, que é a única fraqueza real da abordagem atual.

## Reversão

A interface é `search_policies(conn, pergunta, limit) -> list[PolicyHit]`. Trocar a implementação não
altera ferramenta, prompt nem contrato da API.
