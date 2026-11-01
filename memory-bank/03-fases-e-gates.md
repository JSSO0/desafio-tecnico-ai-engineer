---
criado: 2026-11-01
atualizado: 2026-11-01
tags: [projeto, emporio-da-musica, gates]
---

# Fases e Gates

Regra: **nenhuma fase avança sem aprovação explícita do dono do projeto.** Gate = 5–10 min.

## Cronograma acordado

| Dia | Blocos |
|---|---|
| 01/11 (hoje) | B1 fundação → B2 dados → B3 agente/CLI → B4 API → B5 guards/limites/auditoria → B6 RAG → B7 evals v0 |
| 02/11 | B8 C4 → B9 README/memory-bank → B10 evals full + 3 provedores + docker → B11 conversas → B12 congelamento |
| 03/11 | buffer |

## Registro

### GATE 0 — Fundação (B1)
- **Status:** entregue, aguardando validação
- **Entregue:** repositório git, `pyproject.toml`, `Dockerfile` (multi-layer, non-root, healthcheck),
  `compose.yaml`, `.env.example`, `api/app/main.py` com `/healthz`, `/readyz`, `/v1/meta`,
  3 testes de fumaça, README esqueleto, `AGENTS.md`, `memory-bank/`, spec-kit inicializado.
- **Verificação executada:**
  - `docker compose up --build` → container `healthy`
  - `/healthz` 200 · `/readyz` 200 · `/v1/meta` 200 · `/docs` 200
  - `ruff check .` → All checks passed
  - `pytest` → 3 passed
- **Decisões:**
  - Provedor default `deepseek:deepseek-chat`; os outros dois comentados no `.env.example`.
  - **spec-kit mantido**: `specify init --integration opencode` funcionou nativamente (comandos em
    `.opencode/commands/`), instalado via `uvx` efêmero — nada instalado na máquina. Tempo total
    ≈ 8 min, dentro do timebox de 20 min. Artefatos em `.specify/`.
  - Constituição escrita com 8 princípios (`.specify/memory/constitution.md`).
- **Bug encontrado e corrigido:** chave de API vazia (`DEEPSEEK_API_KEY=`) era contada como
  "configurada" porque `""` não é `None`. `/readyz` agora reporta `llm_configured: false` corretamente.


### GATE 1 — Agente responde os 4 cenários
- **Status:** pendente

### GATE 2 — Contrato de API congelado
- **Status:** pendente

### GATE 3 — RAG por seção com citação
- **Status:** pendente

### GATE 4 — Diagramas C4
- **Status:** pendente

## Cortes acordados (se atrasar)

1. `simular_pagamento` → regra vai para o RAG §3.
2. Diagrama C4 *dynamic* (mantém L1–L3).
3. Evals 25 → 15 (preservando os 6 casos de dados sujos).
4. Diagrama de deployment.

**Nunca cortar:** gate de preço, auditoria, orçamento de tokens, RAG por seção, README, 4 conversas.
