# ADR 0005 — Padrão de nomenclatura e de parâmetros

- **Status:** aceito (revisado)
- **Data:** 2026-11-02
- **Contexto:** o código misturava português e inglês, às vezes dentro da mesma função: `brl(value)`
  tinha assinatura em inglês e corpo em português (`inteiro`, `centavos`). Não era escolha — era
  acúmulo. O mesmo valia para assinaturas longas: `audit_event` tinha 12 parâmetros.

## Decisão 1 — um padrão de nome

**Identificador de código em inglês. Fronteira em português.**

| Onde | Idioma | Por quê |
|---|---|---|
| Variáveis, funções, classes, módulos | inglês | o stack é inglês (FastAPI, LangChain) e a maior parte do código é infraestrutura |
| Nomes de ferramenta (`search_products`, `lookup_order`) | inglês | prompt, evals e mapa de cards atualizados; o modelo se adaptou sem ajuste de prompt |
| Parâmetros de ferramenta (`query`, `category`, `phone`) | inglês | é o schema que o modelo lê — e ele leu o novo sem perder acerto (evals 14/14) |
| Chaves de saída (`secao`, `titulo`, `preco`) | **português** | ver nota abaixo: nunca são lidas pelo código, só pela interface |
| Mensagens ao usuário e ao operador | **português** | quem lê é a loja |
| Nomes de teste (`test_posso_devolver_traz_secao_4_1`) | **português** | são frases de comportamento, não símbolos |

## Decisão 2 — parâmetro demais vira objeto

Nenhuma função passa de **5 parâmetros**, e a regra é um gate de lint (`PLR0913`, `max-args = 5`).
Quando o conjunto de campos forma um conceito, ele vira valor:

| Antes | Depois |
|---|---|
| `audit_event(logs_dir, request_id, session_id, customer_id, message, outcome)` | `audit_event(logs_dir, AuditEntry, outcome)` |
| `store.append_message(session_id, role=, content=, guard=, latency_ms=)` | `append_user_message(session_id, content)` e `append_assistant_message(session_id, outcome)` |
| `add_usage(session_id, tokens_in=, tokens_out=, tools=, guard=, latency_ms=, prompt_version=, model=)` | `add_usage(session_id, TurnOutcome)` |
| `_where(termo, categoria, preco_min, preco_max, somente_disponiveis)` | `_where(CatalogFilter)` |

**Exceção única e explícita:** `buscar_produtos` mantém 6 parâmetros com `# noqa: PLR0913`. A
assinatura dela é o schema que o modelo preenche; aninhar em objeto trocaria a legibilidade do modelo
por estética de assinatura — e o custo de uma chamada malformada é maior que o de uma assinatura longa.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Tudo em português (linguagem ubíqua radical) | o código é majoritariamente infraestrutura; `store.append_message` em português não ganha nada e perde familiaridade com a documentação das libs |
| Tudo em inglês, inclusive schema e chaves de saída | quebraria o contrato com o modelo e com a interface, exigindo mudar `web/app.js` e regenerar os exemplos |
| Não padronizar | foi o que gerou o problema: 8 arquivos com metade de cada idioma |

## Consequências

- **687 identificadores** renomeados em 37 arquivos, em duas passadas, com **tokenizador** e não
  regex: regex trocaria também texto dentro de string, que é o que o cliente lê.
- Nenhum parâmetro de ferramenta e nenhuma chave de saída mudaram — evals em 14/14 antes e depois.
- `parametrize` do pytest quebra de forma silenciosa nesse tipo de renomeação: o nome do parâmetro
  está dentro de string. Três testes precisaram de correção manual; não há como automatizar com
  segurança.
- O padrão é verificável por lint para parâmetros; para nomes, a verificação é em revisão.

## Reversão

A renomeação é mecânica e o teste continua verde. Se o time preferir tudo em português, o caminho é
o mesmo script com o mapa invertido.

## Nota — por que a chave de saída ficou em português

Renomear chave de saída não é mexer em código nosso: é mexer em contrato de terceiro. O levantamento
mostrou:

| Superfície | Alcance |
|---|---|
| `web/app.js` lendo `data.*` | **32 chaves** em ~35 pontos |
| Valores de `card.tipo` e chaves `tipo`/`dados`, `acao`/`texto` | 6 valores e 4 chaves no payload SSE |
| Colunas do banco (`secao`, `titulo`, `texto`, `pagina`, `versao`) | schema, `build.py` e o front-matter dos 10 arquivos de política |
| Cobertura | **os evals não olham chave de card**: um erro só aparece na tela |

Traduzir metade (só o payload da API) move a inconsistência de lugar: o banco e os arquivos de
política continuariam em português, e o mapeamento passaria a existir em algum ponto entre eles. Com
prazo curto e sem teste que proteja, o risco não paga.

**Decisão:** o payload fala a língua do domínio (português), o código fala inglês, e a tradução
acontece exatamente na borda que o modelo e a interface leem. Se um dia o payload for traduzido, o
caminho é junto com o schema do banco e os arquivos de origem, não antes.
