# Plano técnico — `001-atendimento-por-texto`

> **Retrospectivo**, escrito após a implementação. Para o raciocínio de cada decisão no momento em
> que foi tomada, ver [`docs/adr/`](../../docs/adr/) e
> [`memory-bank/03-fases-e-gates.md`](../../memory-bank/03-fases-e-gates.md).

## Checagem da constituição

| Princípio | Como foi atendido | Evidência |
|---|---|---|
| I. Fidelidade factual | Gate de preço no código; política só com seção recuperada | `guards/grounding.py`, eval `preco-takamine` |
| II. Segredo fora do cliente | `.env` gitignored, chave só no servidor | nenhum segredo no histórico |
| III. Dados por ferramenta | 6 tools tipadas, CSV fora do corpus | `tools/`, ADR 0003 |
| IV. Autorização fora do modelo | `SessionContext` no servidor; `consultar_pedido` sem `customer_id` | `tools/orders.py`, eval `pedido-de-outro-cliente` |
| V. Ferramentas read-only | conexão SQLite `mode=ro` | `db/connection.py` |
| VI. Simplicidade verificável | sem embeddings, sem vector DB, sem multiagente | ADR 0003 |
| VII. Observabilidade e limite | auditoria JSONL, rate limit, orçamento | `audit/log.py`, `runtime/store.py` |
| VIII. Entrega incremental | 7 fases, gates, commits por assunto | 53 commits |

## Stack e por quê

| Camada | Escolha | Alternativa descartada |
|---|---|---|
| Orquestração | LangChain v1 `create_agent` (loop ReAct sobre LangGraph) | framework próprio: reinventaria loop, parsing e streaming |
| API | FastAPI | Flask: sem OpenAPI nativo, que é o contrato da UI |
| Dados | SQLite (arquivo, WAL) | Postgres: sem dor operacional neste volume |
| Políticas | Markdown por seção + FTS5/BM25 | embeddings: 25 blocos não justificam ANN |
| Interface | React 18 + htm, estático | Vite + bundler: build step sem retorno para uma tela |

## Arquitetura

Contexto, contêineres, componentes, implantação e dinâmico em
[`docs/architecture/c4.md`](../../docs/architecture/c4.md).

Resumo: cliente → API (sessão, guardrails, agente, RAG, limites, auditoria) → SQLite operacional
read-only + SQLite de execução + trilha JSONL, com provedor de LLM externo por configuração.

## Contratos

8 rotas documentadas em `/docs`, com `securitySchemes: HTTPBearer`:

`POST /v1/sessions` · `POST /v1/chat` (SSE) · `GET /v1/sessions/{id}/usage` ·
`GET /v1/sessions/{id}/messages` · `DELETE /v1/sessions/{id}` · `GET /v1/meta` · `/healthz` · `/readyz`

Eventos SSE: `token`, `tool_call`, `card`, `guard`, `usage`, `done`, `error`.

**Decisão de contrato:** o gate de preço roda depois dos tokens; quando bloqueia, envia `guard` com
`acao=substituir_resposta` e o cliente troca o texto. Bufferizar anularia o streaming (ADR 0002).

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Alucinação de preço | gate determinístico + eval dedicado |
| Injection despejando dados de cliente | CSV fora do corpus; tools com projeção fixa |
| BOLA em consulta de pedido | identidade na sessão, nunca no argumento |
| Custo fora de controle | orçamento por sessão, rate limit, 120 sessões/h por origem |
| Prazo de 2 dias | vertical slice primeiro; cortes acordados antes de começar |
| Provedor indisponível | erro como evento SSE, sem stack trace ao cliente |

## Fases (cada uma com gate de aprovação)

| Fase | Entrega | Gate |
|---|---|---|
| B1 | fundação: container, health, abstração de provedor | GATE 0 |
| B2 | base operacional, políticas em Markdown, índice FTS5 | (entra no GATE 1) |
| B3 | 6 ferramentas, harness ReAct, gate de preço, CLI | GATE 1 |
| B4 | API: sessão, SSE, uso, histórico, OpenAPI | GATE 2 |
| B5 | guardrails, limites, auditoria, evals | GATE 3 |
| B6 | C4, ADRs, memory-bank | GATE 4 |
| B7 | interface integrada, container nginx | — |

## Verificação

`pytest` (151) · `ruff` · `scripts/eval.py` (14 casos contra a API real) · `docker compose up --build`
a partir de volume vazio · inspeção no navegador dos dois caminhos da interface.
