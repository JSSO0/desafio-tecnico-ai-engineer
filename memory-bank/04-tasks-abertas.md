---
criado: 2026-11-02
atualizado: 2026-11-02
tags: [projeto, emporio-da-musica, tarefas]
---

# Tasks Abertas

## Antes de entregar

- [x] Suite verde (146 testes) e `ruff` limpo
- [x] Evals contra a API real (14/14)
- [x] Conversas de exemplo geradas por script (5)
- [x] C4 níveis 1–3 + implantação + dinâmico, renderizados e conferidos
- [x] ADRs 0001–0004
- [x] README com instruções, justificativas, limitações e uso de IA
- [ ] **Push para o repositório público** (`origin` está no fim do B2; 34 commits locais à frente)
- [ ] Tag `v1.0-entrega` no commit final
- [ ] Conferir que `.env` não foi versionado em nenhum commit

## Fora do escopo desta entrega (registrado no README)

- Testes automatizados da interface (hoje é validada no navegador, não em CI)
- C4 nível 4 (decisão registrada em `docs/architecture/c4.md`)
- Embeddings / busca semântica de produto (ADR 0003)
- Postgres + pgvector (ADR 0003 e README)
- Evals no CI com baseline
- Rotação e retenção da auditoria
- Rate limit distribuído (hoje é local e por IP da conexão)

## Dívidas técnicas conscientes

- `prompt_version` é o hash do arquivo: mudou uma vírgula, muda a versão. Serve para correlacionar,
  não para comparar qualidade entre versões.
- O agente às vezes re-chama `identificar_cliente` no turno seguinte, porque o histórico não guarda
  saída de ferramenta. Custa uma tool barata e mantém o contexto pequeno.
- `logs/` é bind mount; em produção viraria volume gerenciado com retenção.
