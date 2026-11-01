---
criado: 2026-11-01
atualizado: 2026-11-01
tags: [projeto, emporio-da-musica, desafio-artefact, moc]
---

# Empório da Música — Índice

> Desafio técnico AI Engineer (Artefact). Entrega: 02/11/2026. Buffer: 03/11.

> [!info] Visão
> Agente de atendimento ao cliente (PT-BR) para loja fictícia de instrumentos musicais.
> **Stack:** Python 3.12 · LangChain v1 (`create_agent`, ReAct) · FastAPI · SQLite · FTS5/BM25 · Docker Compose.
> **Provedores:** OpenAI / Anthropic / DeepSeek por `env`, sem tocar em código.
> **Fora de escopo (delegado):** UI React, C4 nível 4, embeddings/pgvector.

## Mapa

- [[01-arquitetura-e-decisoes]] — ADRs e o raciocínio por trás de cada escolha.
- [[02-dados-e-premissas]] — achados da análise dos CSVs e do manual de políticas.
- [[03-fases-e-gates]] — o que foi aprovado em cada gate.
- [[04-tasks-abertas]] — pendências.
- [[05-como-rodar]] — comandos e verificação.

## Fatos que não podem ser esquecidos

1. CSV **não** é corpus de RAG — só ferramenta tipada (minimização + anti-injection).
2. `consultar_pedido` não aceita `customer_id`; usa a sessão (anti-BOLA).
3. Preço/estoque/prazo só saem de resultado de ferramenta (gate de saída).
4. Políticas: recuperação **por seção**, 1–2 por turno, com citação.
5. 3 categorias do catálogo estão vazias (6, 7, 8) — nunca inventar produto.
6. Pedidos 3 e 20 têm `total_brl` divergente da soma dos itens — documentar, não "corrigir".
7. `stock_quantity` é snapshot atual, não histórico.
