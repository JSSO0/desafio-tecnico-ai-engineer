# ADR 0001 — Estratégia de testes

- **Status:** aceito
- **Data:** 2026-11-02
- **Contexto:** desafio técnico AI Engineer (Artefact). Agente de atendimento com LLM, tools
  determinísticas, RAG lexical e gate de saída. A suíte precisa rodar rápido, sem rede e sem
  chave, e ainda assim proteger as invariantes da [constituição](../../specs/constitution.md).

## Contexto

O produto tem três fontes de comportamento:

1. **Código nosso** — build da base, ferramentas tipadas, sessão, gate de preço, recuperação
   de políticas, contrato HTTP. Determinístico.
2. **Framework** — LangChain (`create_agent`, loop ReAct, parsing de tool call, mensagens).
   Código de terceiro, com testes próprios e evolução independente.
3. **Modelo de linguagem** — não determinístico, responde texto livre.

Testar tudo com o mesmo rigor produziria uma suíte lenta, frágil e que falha por motivo
errado. A decisão é onde colocar a confiança.

## Decisão

**Não testamos o LangChain.** Testamos as fronteiras que controlamos:

- as **tools** diretamente, como funções de negócio;
- a **extração do turno** (`run_turn`) com um agente roteirizado, no formato que o framework
  entrega;
- o **gate de saída** como função pura;
- o **contrato HTTP** e a **base de dados** como integrações estreitas;
- o **comportamento do modelo** por evals com provedor real, fora do `pytest` padrão.

O framework é tratado como biblioteca: confiamos no contrato público dele e verificamos apenas
o que fazemos com o resultado.

## Por que não testar o LangChain

| Motivo | Consequência prática |
|---|---|
| É código de terceiro, já coberto pelos testes do projeto upstream | Testá-lo duplicaria a suíte deles e não aumentaria a confiança no nosso produto |
| Os testes ficariam acoplados à estrutura interna (mensagens, callbacks, grafo do agente) | Um upgrade de versão quebraria a suíte sem mudança de comportamento — exatamente o anti-padrão "teste que quebra a cada refactor" |
| Os riscos que importam não estão nele | BOLA, preço sem lastro e projeção de PII vivem nas nossas tools, sessão e gate |
| O loop ReAct depende de um modelo não determinístico | Testá-lo de verdade exigiria rede e chave; o resultado seria flaky, não confiável |
| Fan-out de mocks internos esconde integração | Quanto mais internals mockamos, menos realidade testamos ("poke fewer holes in reality") |

O que fazemos no lugar:

- **Seam do framework:** `run_turn` recebe qualquer objeto com `.invoke()` e devolve mensagens.
  Um agente roteirizado (`FakeAgent`) exercita nossa extração de tool calls, tokens, resposta
  final e aplicação do gate sem importar o loop do LangChain.
- **Seam do provedor:** `build_model()` isola `init_chat_model`. A troca de provedor é
  configuração; o eval real é o teste de fumaça dessa fronteira, opt-in.
- **Contrato observável:** as tools são chamadas pelo que devolvem (`invoke`), não por como o
  framework as registra.

Se um dia o LangChain quebrar nosso uso, quem detecta é o teste do seam ou o eval — não um
teste que replica a implementação dele.

## O que é testado e por quê

Cada regra tem **um nível dono**. Não re-testamos a mesma afirmação em todas as camadas.

| Camada / superfície | Nível | Por que vale testar |
|---|---|---|
| `build_database`, `load_policies`, `data_quality_report` | integração com SQLite real | É a fonte de verdade de toda resposta. Corrupção silenciosa contamina todas as tools; o build precisa falhar alto (specs inválido, CSV ausente) e ser idempotente |
| `v_products` e regras de promoção | integração com SQLite real | Preço é dinheiro. Promoção inativa não pode descontar; promoção ativa precisa aparecer; divergência de total não pode ser "corrigida" |
| `connect` somente leitura | integração | A constituição promete blast radius zero: uma tool comprometida não escreve. Isso precisa ser verificável, não aspiracional |
| `search_policies` + `normalize` + `build_query` | unitário + integração | O retrieval é determinístico e já teve quatro regressões reais (sanitização de FTS, prefixo, stoplist, IDF). Pergunta em linguagem natural é o caminho do cliente |
| Tools de catálogo, pedidos, políticas e pagamento | integração (tool como unidade) | Concentram regra de negócio: parcela mínima, desconto PIX, escopo por cliente, projeção de campos. É onde um erro vira preço errado ou dado de outro cliente |
| `SessionContext` + `consultar_pedido` | integração | Autorização não é decisão do modelo. O teste de pedido alheio e de resposta idêntica para "não existe" prova o anti-BOLA |
| `enforce_price_grounding` | unitário | É a constituição em código. Sem teste, o gate é só um comentário; com teste, `R$` inventado é bloqueado |
| `run_turn` (seam) | unitário com agente roteirizado | Erros de atribuição (pegar a resposta intermediária, somar token errado, não aplicar o gate) são nossos e silenciosos |
| `/healthz`, `/readyz`, `/v1/meta` | contrato HTTP | Readiness precisa significar "pronto"; chave vazia não é chave configurada; segredo não vaza em resposta |
| Configuração de provedor | unitário | Troca de provedor por `.env` é requisito explícito do desafio |

## O que não é testado (e por quê)

| Item | Motivo |
|---|---|
| Loop ReAct, parsing e callbacks do LangChain | Código de terceiro; testar duplica o upstream e acopla a suíte à versão |
| Prosa do modelo (tom, estilo, frase exata) | Não determinístico. O que importa é fato ancorado, tool chamada e gate — cobertos por asserts de comportamento e evals |
| Snapshot do prompt inteiro | Quebraria a cada ajuste de redação sem indicar regressão de comportamento. O contrato é: tools expostas e regras de citação |
| Provedor real no `pytest` padrão | Exige chave, custa dinheiro e é flaky. Roda como eval opt-in antes do congelamento |
| Cobertura como meta | Cobertura é sintoma, não objetivo; persegui-la gera testes de getter e de framework |
| E2E de UI | Fora de escopo do desafio (UI delegada) |

## Alternativas consideradas

1. **Mockar os internals do LangChain para "testar o agente".** Rejeitada: alto acoplamento,
   baixa fidelidade, quebra a cada upgrade. O seam com agente roteirizado dá o mesmo sinal com
   menos mentira.
2. **Rodar o agente real em todo `pytest`.** Rejeitada: chave, custo, latência e flakiness.
   Fica como eval opt-in.
3. **Só testes E2E de conversa.** Rejeitada: falha sem localizar a causa, lenta, e não cobre
   bordas de dinheiro/autorização que os testes de tool cobrem barato.
4. **Não testar a base porque "os CSVs são a especificação".** Rejeitada: o build transforma,
   indexa e normaliza; é justamente onde erros silenciosos entram.

## Consequências

- A suíte padrão roda offline e sem chave; o feedback é em segundos.
- Refatorar o agente ou subir a versão do LangChain não deve quebrar testes de negócio.
- O comportamento do modelo fica coberto por evals, não por `pytest`; a confiança nele é
  amostral e explícita, não fingida.
- Toda regra nova precisa escolher seu nível dono; duplicar assert entre camadas é considerado
  defeito de suíte.

## Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Fake do agente divergir do formato real do framework | O fake usa apenas os campos que `run_turn` consome; o eval real com provedor roda antes do congelamento |
| Eval não rodar no CI e a regressão passar | Eval é gate manual documentado no `memory-bank`; os casos de dados sujos também existem como testes determinísticos |
| Teste de tool virar teste de SQL | Asserts focam no contrato de saída (campos, valores, escopo), não na query |
| Dados de origem mudarem e os números fixos quebrarem | Os CSVs são entrada imutável do desafio; a quebra é sinal para revisar a premissa, não para afrouxar o teste |

## Como reverter

Se o framework mudar de forma que o seam deixe de representar a realidade, o caminho é
adicionar um **contract test** mínimo do adapter (mensagens de entrada/saída) em vez de
reintroduzir testes de internals. A decisão de não testar o LangChain permanece; muda apenas
a fidelidade do dublê.
