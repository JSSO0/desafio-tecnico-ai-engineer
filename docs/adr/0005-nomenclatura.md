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
| Parâmetros de ferramenta (`termo`, `categoria`, `telefone`) | **português** | é o schema que o modelo lê; renomear muda o contrato com o LLM |
| Chaves de saída (`secao`, `titulo`, `preco`) | **português** | contrato com a interface: `web/app.js` lê `dados.nome`, `dados.preco` |
| Nomes de ferramenta (`buscar_produtos`) | **português** | o prompt, os evals e o mapa de cards da UI dependem do nome |
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