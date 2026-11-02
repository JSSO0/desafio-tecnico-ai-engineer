# Tarefas — `001-atendimento-por-texto`

> **Retrospectivo.** Todas as tarefas abaixo foram concluídas; o commit ao lado é onde cada uma
> entrou. Nada foi reescrito no histórico para simular ordem.

## Fase 1 — Fundação (`548d402`)

- [x] T001 Repositório, `pyproject`, `Dockerfile` non-root com healthcheck
- [x] T002 `compose.yaml` com volume de dados e bind de logs
- [x] T003 `Settings` por env; chave de provedor por provedor (openai/anthropic/deepseek)
- [x] T004 `/healthz`, `/readyz`, `/v1/meta` + 3 testes de fumaça
- [x] T005 Constituição e `AGENTS.md`

## Fase 2 — Dados e corpus (`8930cc0` … `2bc0771`)

- [x] T006 Políticas convertidas para Markdown por seção, com tabelas reconstruídas à mão
- [x] T007 `build_database` idempotente; normalização de telefone; parse de `specs`
- [x] T008 View `v_products` com promoção ativa e preço final
- [x] T009 Relatório de qualidade de dados no build (pedidos 3 e 20, categorias 6/7/8)
- [x] T010 Índice FTS5 com `remove_diacritics`
- [x] T011 Consulta sanitizada (sem injeção de operadores) e prefixo de 5 caracteres
- [x] T012 Re-rank por cobertura com IDF e boost de título
- [x] T013 36 testes de dados e retrieval

## Fase 3 — Agente (`04f575a` … `276296b`)

- [x] T014 Normalização de texto, formato em reais e busca sem acento
- [x] T015 Ferramenta de catálogo com filtros
- [x] T016 Identificação do cliente e pedidos escopados à sessão
- [x] T017 Ferramenta de políticas e simulação de pagamento
- [x] T018 Gate de preço ancorado em resultado de ferramenta
- [x] T019 Harness ReAct com prompt versionado por hash
- [x] T020 CLI para validar cenários sem a API
- [x] T021 Testes de ferramenta, gate e extração do turno

## Fase 4 — API (`3b9cac9` … `7516247`)

- [x] T022 Runtime separado: sessões, mensagens, ledger
- [x] T023 Runner com streaming de tokens, tool calls e cards
- [x] T024 Autenticação por token opaco e contratos de resposta
- [x] T025 Rotas de sessão, uso, histórico e encerramento
- [x] T026 Chat em SSE com orçamento e falha como evento
- [x] T027 OpenAPI com esquema de segurança e eventos documentados
- [x] T028 Testes de sessão, autorização, SSE e orçamento

## Fase 5 — Guardrails (`012cd28` … `2a511fb`)

- [x] T029 Guard de entrada por tamanho e tentativa de desvio
- [x] T030 Trilha de auditoria com PII mascarada
- [x] T031 Contadores de janela para rate limit
- [x] T032 Guard, rate limit, orçamento e auditoria no turno
- [x] T033 Limite de criação de sessões por origem
- [x] T034 `evals/casos.jsonl` + runner contra a API real (14 casos)

## Fase 6 — Arquitetura (`f61c9ba` … `89a4814`)

- [x] T035 C4 níveis 1–3, implantação e dinâmico, renderizados e conferidos no navegador
- [x] T036 ADR 0003 (retrieval lexical) e ADR 0004 (limites e auditoria)
- [x] T037 `memory-bank/01` com decisões e números medidos

## Fase 7 — Interface (`522a658` … `f509fd7`)

- [x] T038 Interface integrada; `vendor/` reconstruído (React 18.3.1, ReactDOM, htm 3.1.1)
- [x] T039 CORS liberado para `:8080` com cabeçalhos de limite expostos
- [x] T040 Container nginx com proxy para a API e `proxy_buffering off`
- [x] T041 `serve.py` com pré-voo de assets e sonda de porta
- [x] T042 Guia de integração no README e no `web/README.md`

## Pendências (registradas, fora de escopo)

- [ ] Testes automatizados da interface
- [ ] Evals no CI com baseline
- [ ] C4 nível 4
- [ ] Embeddings para reranking
- [ ] Postgres + pgvector
- [ ] Deploy público com TLS
- [ ] Rotação e retenção da auditoria
