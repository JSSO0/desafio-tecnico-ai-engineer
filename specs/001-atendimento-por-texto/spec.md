# Spec — Atendimento por texto da Empório da Música

> **Retrospectiva**, escrita após a implementação. Descreve o que foi construído e verificado.
> Artefatos irmãos: [plan.md](plan.md) · [tasks.md](tasks.md).

**Feature:** `001-atendimento-por-texto`
**Escopo:** um único sistema de atendimento conversacional, com API e interface, sobre os dados
operacionais e o manual de políticas fornecidos.

---

## Problema

A equipe da loja é sobrecarregada por perguntas repetitivas: horário, preço, disponibilidade, status
de pedido, política de troca. O agente precisa responder essas perguntas **sem inventar dado** — o
manual é explícito: "nunca fornecer informações sobre preços, estoque ou prazos sem consultar o
sistema".

## Personas

| Persona | Necessidade |
|---|---|
| **Cliente** | resposta rápida, correta e no tom da loja, por texto |
| **Atendente humano** | assumir a conversa quando o caso escala |
| **Avaliador** | conseguir verificar o comportamento sem ler todo o código |

---

## Histórias de usuário

### US1 — Catálogo e preço (prioridade: alta)

Como cliente, quero saber o que a loja tem e quanto custa, **para decidir a compra**.

- **Dado** "violões até R$1.000", **quando** peço opções, **então** recebo itens na faixa com preço e
  disponibilidade, sem esgotado nem descontinuado.
- **Dado** um modelo específico, **quando** pergunto o preço, **então** recebo o valor gravado na base.
- **Dado** um produto com promoção **inativa**, **quando** pergunto de desconto, **então** ouço que não
  está vigente, com o preço atual.

### US2 — Status de pedido (prioridade: alta)

Como cliente, quero saber onde está meu pedido, **para não precisar ligar**.

- **Dado** que ainda não me identifiquei, **quando** peço status, **então** o agente pede meu telefone
  antes de consultar.
- **Dado** meu telefone, **quando** informo, **então** vejo meus pedidos com status, itens, rastreio e
  previsão.
- **Dado** um pedido de **outro cliente**, **quando** informo o número, **então** a resposta é
  "não encontrei no seu cadastro", sem revelar nada.

### US3 — Políticas da loja (prioridade: alta)

Como cliente, quero entender troca, devolução, frete, pagamento e garantia, **para saber meus direitos**.

- **Dado** que me arrependi de uma compra online, **quando** pergunto, **então** recebo prazo,
  condições, prazo de reembolso e quem paga o frete, com a seção do manual citada.
- **Dado** uma pergunta fora do manual, **quando** faço, **então** o agente admite e diz que vai
  confirmar com a gerência.

### US4 — Limite de escopo (prioridade: média)

Como lojista, quero que o agente **não** prometa o que a loja não faz.

- **Dado** pergunta sobre acessório (cordas, palhetas, cabos, cases, pedais, amplificadores),
  **então** informa que a loja trabalha só com instrumentos e redireciona.
- **Dado** pergunta fora do domínio (capital de país, receita), **então** redireciona com gentileza.
- **Dado** pedido para ignorar instruções, **então** recusa **sem chamar o provedor**.

### US5 — Custo e controle visíveis (prioridade: média)

Como responsável pela loja, quero ver o consumo e ter limites **para o custo não fugir**.

- Consumo de tokens visível por sessão, rate limit e orçamento impostos no servidor.
- Trilha de auditoria por turno, com dado pessoal mascarado.

---

## Requisitos funcionais

| ID | Requisito |
|---|---|
| FR-001 | Consultar catálogo com filtro por termo, categoria e faixa de preço |
| FR-002 | Devolver preço de tabela, promoção ativa e preço final, sem recalcular divergência da base |
| FR-003 | Identificar o cliente por telefone e vincular a identidade à sessão |
| FR-004 | Consultar pedidos **somente** do cliente vinculado |
| FR-005 | Recuperar políticas por seção, com `secao`, `pagina` e citação |
| FR-006 | Aplicar regras de pagamento (PIX 5%, parcelamento por faixa) de forma determinística |
| FR-007 | Recusar mensagem acima de 800 caracteres |
| FR-008 | Recusar tentativa explícita de desvio de instrução, sem chamar o provedor |
| FR-009 | Bloquear resposta que cite valor em reais sem lastro em ferramenta |
| FR-010 | Emitir resposta em streaming com eventos de token, ferramenta, dado estruturado e consumo |
| FR-011 | Limitar mensagens por sessão, sessões por origem e tokens por sessão |
| FR-012 | Registrar um evento de auditoria por turno com PII mascarada e versão do prompt |

## Requisitos não funcionais

| ID | Requisito | Verificação |
|---|---|---|
| NFR-001 | Resposta começa a chegar em segundos, não ao fim | SSE com eventos `token` observados |
| NFR-002 | Nenhuma credencial de provedor no cliente | `.env` fora do versionamento; busca por segredo no histórico |
| NFR-003 | Funcionar com três provedores, trocando só configuração | `LLM_PROVIDER` + `LLM_MODEL` |
| NFR-004 | Subir com um comando, do zero | `docker compose up --build` com volume limpo |
| NFR-005 | Suíte determinística, sem rede e sem chave | 151 testes |
| NFR-006 | Custo de contexto por turno abaixo de 10% do corpus inteiro | ~280 tokens contra 2.930 (−90%) |

---

## Fora de escopo (registrado no README)

Interface com build step e testes de UI · C4 nível 4 · embeddings e busca semântica · Postgres/pgvector
· deploy público · evals no CI · rotação da auditoria · autenticação de pessoa.

## Premissas de dados

Sete armadilhas nos dados de origem (totais divergentes, estoque como snapshot, categorias vazias,
promoção inativa, poucos clientes com pedido, `specs` como JSON embutido) estão documentadas em
[`memory-bank/02-dados-e-premissas.md`](../../memory-bank/02-dados-e-premissas.md) e viraram casos de
eval. **Nenhum arquivo de origem foi editado.**
