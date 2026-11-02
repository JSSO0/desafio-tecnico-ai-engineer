---
criado: 2026-11-01
atualizado: 2026-11-02
tags: [projeto, emporio-da-musica, arquitetura, adr]
---

# Arquitetura e Decisões

## Forma do sistema, em uma frase

Cliente → API FastAPI (sessão, guardrails, agente ReAct, RAG, limites, auditoria) → SQLite
operacional (somente leitura) + SQLite de execução (sessões, consumo) + JSONL de auditoria, com um
provedor de LLM externo escolhido por configuração.

Diagramas completos em [`docs/architecture/c4.md`](../docs/architecture/c4.md) — contexto,
contêineres, componentes, implantação e dinâmico. **Nível 4 (código) fora de escopo**, por decisão
registrada no próprio documento.

## ADRs

| ADR                                               | Decisão                                             | Por que importa                                      |
| ------------------------------------------------- | --------------------------------------------------- | ---------------------------------------------------- |
| [0001](../docs/adr/0001-estrategia-de-testes.md)  | Não testar o LangChain; testar as nossas fronteiras | Evita suíte frágil que quebra a cada upgrade         |
| [0002](../docs/adr/0002-sessao-e-token-opaco.md)  | Token opaco em vez de JWT                           | Revogação e orçamento por sessão exigem estado       |
| [0003](../docs/adr/0003-retrieval-lexical.md)     | BM25 nativo em vez de embeddings                    | 25 blocos não justificam ANN; custo zero e testável  |
| [0004](../docs/adr/0004-orcamento-e-auditoria.md) | Limites e auditoria no servidor                     | Custo previsível e rastreabilidade com PII mascarada |

## As cinco decisões que sustentam o resto

1. **Dados não vão para o corpus.** Catálogo e pedidos só por ferramenta tipada, com projeção fixa de
   campos. Um injection não consegue "pedir" o que a ferramenta não devolve.
2. **Identidade fora do modelo.** `SessionContext` vive no servidor; `consultar_pedido` não aceita
   `customer_id`. É o que impede BOLA do tipo "mostre o pedido 6" (de outro cliente).
3. **Preço só com lastro.** O gate compara todo `R$` da resposta com os números que voltaram de
   ferramenta no turno.
4. **Streaming com correção.** O gate roda depois dos tokens; por isso existe o evento `guard` com
   `acao=substituir_resposta`. Bufferizar anularia o streaming.
5. **Histórico sem payload de ferramenta.** O contexto guarda a conversa, não os JSONs. Turno 3 caiu
   de 13,4k para 2,7k tokens (−80%); o agente reconsulta quando precisa.

## Números medidos (não estimados)

| Medida                              | Valor                                      |
| ----------------------------------- | ------------------------------------------ |
| Tokens de política por turno (k=3)  | ~280 contra 2.930 do manual inteiro (−90%) |
| Primeiro turno (prompt + 6 schemas) | ~2,5k tokens de entrada                    |
| Turno com ferramenta                | ~5k a 8k tokens de entrada                 |
| Turno 3 de uma conversa             | ~2,7k tokens                               |
| Testes                              | 146                                        |
| Evals contra a API real             | 14/14                                      |
