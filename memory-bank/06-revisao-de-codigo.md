---
criado: 2026-11-02
atualizado: 2026-11-02
tags: [projeto, emporio-da-musica, revisao]
---

# Revisão de código (rodada 1)

Revisão feita pelo dono do projeto depois da entrega técnica, com 10 apontamentos. O valor desta
nota é registrar **o que foi aceito, o que foi recusado e por quê** — revisão sem critério vira
lista de desejos.

| # | Apontamento | Veredito | O que foi feito |
|---|---|---|---|
| 1 | Argumentos demais | **Aceito** | `TurnOutcome`; `audit_event` 12→6, `add_usage` 8→2 |
| 2 | Resposta inline no health | **Aceito com outra causa** | faltava `response_model`, não abstração: Swagger mostrava `{}` |
| 3 | CORS hardcoded | **Parcial** | já era configurável; parsing saiu para `allowed_origins`, default de dev mantido |
| 4 | PT/EN misturado | **Aceito** | 436 identificadores; padrão no ADR 0005 |
| 5 | Classe de exceções | **Parcial** | hierarquia (`EmporioError`/`DataSourceError`), não uma por arquivo |
| 6 | Stopwords no código | **Aceito** | `api/app/rag/stopwords.txt`, 106 palavras |
| 7 | Muitos `if` no SQL | **Parcial** | extração para `_where()` com teste; sem criar abstração de filtro |
| 8 | `try/except` em tudo | **Recusado** | esconderia bug; o que faltava era handler global, que foi feito |
| 9 | `conversas.py` é necessário? | **Sim** | é o gerador dos 5 exemplos; cliente HTTP extraído para `api_client.py` |
| 10 | `for` sem `break` | **Recusado** | laços iteram listas do caso de teste, não entrada; sem risco de loop |

## Os dois recusados, com critério

**8 — `try/except` "por garantia".** Capturar sem poder tratar transforma falha barulhenta em
sucesso silencioso. Este projeto já pagou duas vezes por falha silenciosa (stoplist quebrada e
`R$ 2.199,00` lido como `2.199 + 00`), e as duas só apareceram porque alguém olhou o resultado. O
que faltava de verdade era a borda: handler global devolvendo JSON com `request_id`.

**10 — `for` sem `break`.** Os laços iteram `deve_conter`, `nao_deve_conter` e `tools_esperadas`
do caso de teste. Comprimento fixo por dado, sem entrada de usuário e sem I/O. Trocar por `all()`
seria mais curto e menos legível.

## Números

- 8 iterações de refatoração, cada uma com commit próprio e suíte verde antes e depois
- 151 → 159 testes
- 436 identificadores renomeados, **zero** mudança de comportamento (evals 14/14 antes e depois)
- 1 limite de configuração corrigido: `max_sessions_per_hour` 20 → 60, porque 20 barrava o próprio
  eval (14 sessões por execução) e barraria quem clica "nova sessão" durante a avaliação

## O que a revisão pegou e os testes não pegariam

Os testes cobrem comportamento; não cobrem forma. Lista longa de parâmetros, contrato vazio no
Swagger e nomenclatura inconsistente passam por 151 testes verdes sem reclamar. Foi a leitura humana
que apontou — e por isso duas dessas viraram gate (lint `PLR0913`) em vez de comentário.