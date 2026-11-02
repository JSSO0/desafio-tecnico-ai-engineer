# Empório da Música — Agente de Atendimento

Agente de atendimento ao cliente da **Empório da Música** (loja fictícia de instrumentos musicais, Campo Grande/MS), construído como entrega do desafio técnico de AI Engineer da Artefact.

O agente conversa em português com o tom da loja, consulta **dados operacionais** (catálogo, pedidos) por ferramentas determinísticas e **políticas internas** por recuperação por seção, recusando o que foge do escopo.

> **Status:** em construção. Fundação pronta (container, health checks, abstração de provedor).
> Fases e gates em [`memory-bank/03-fases-e-gates.md`](memory-bank/03-fases-e-gates.md).

---

## Stack

| Camada | Escolha |
|---|---|
| Linguagem | Python 3.12 |
| Agente | LangChain v1 (`create_agent`, loop ReAct) |
| API | FastAPI (OpenAPI/Swagger nativo) |
| Dados | SQLite (a partir dos CSVs originais) |
| Políticas | Markdown por seção + FTS5/BM25 (SQLite) |
| Provedores | OpenAI, Anthropic, DeepSeek (troca por `.env`) |
| Infra | Docker Compose |

---

## Como rodar

```bash
cp .env.example .env      # preencha a chave do provedor escolhido
docker compose up --build
```

- **Interface:** <http://localhost:8080>
- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Health: <http://localhost:8000/healthz> · <http://localhost:8000/readyz>
- Configuração ativa: <http://localhost:8000/v1/meta>

Para desenvolver a interface sem Docker: `cd web && python serve.py` (sobe em
<http://localhost:5173>). Detalhes em [`web/README.md`](web/README.md).

### Trocar de provedor

Uma linha no `.env`, sem tocar em código:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
```

---

## Arquitetura

Diagramas C4 (contexto, contêineres, componentes, implantação e dinâmico) em Mermaid, com a chave de
notação e a justificativa de escopo: [`docs/architecture/c4.md`](docs/architecture/c4.md).

Em uma frase: cliente → API FastAPI (sessão, guardrails, agente ReAct, RAG, limites, auditoria) →
SQLite operacional somente leitura + SQLite de execução + trilha JSONL, com provedor de LLM externo
escolhido por configuração.

## Decisões técnicas

*(justificativa completa no fechamento — ver `docs/adr/` e `memory-bank/01-arquitetura-e-decisoes.md`)*

- **Híbrido ferramenta + seção:** dados operacionais por 6 ferramentas tipadas sobre SQLite;
  políticas por recuperação em 25 blocos do manual, com citação. Nada de RAG sobre CSV.
- **Retrieval lexical (FTS5/BM25)** com prefixo de 5 caracteres e re-rank por cobertura com IDF:
  280 tokens de política por turno contra 2.930 do manual inteiro.
- **Token opaco de sessão** em vez de JWT (revogação e orçamento por sessão) — ADR 0002.
- **Guardrail no código, não no prompt** — o gate de preço roda sobre a saída.
- **Nomenclatura:** identificador em inglês, fronteira em português (ADR 0005).

## Guardrails, limites e custo

| Camada | O que faz |
|---|---|
| Entrada (código) | recusa mensagem acima de 800 caracteres (`400`) e tentativa explícita de desvio (`guard: injection_attempt`, sem chamar o provedor) |
| Modelo | persona e tom do manual; proibição de afirmar preço, estoque ou prazo sem ferramenta |
| Saída (código) | gate de preço: todo `R$` precisa existir em resultado de ferramenta do mesmo turno |
| Autorização | token opaco; `consultar_pedido` usa o cliente da sessão, nunca um id vindo do modelo |
| Custo | orçamento de 60 mil tokens por sessão, 10 mensagens/minuto por sessão, 20 sessões/hora por origem |
| Auditoria | uma linha JSONL por turno em `logs/`, com telefone e e-mail mascarados |

Escopo e acessório **não** são bloqueados por palavra-chave: "vocês vendem cordas?" é pergunta
legítima e a resposta certa é redirecionar com educação, não negar atendimento.

## Avaliação

Casos declarativos em [`evals/casos.jsonl`](evals/casos.jsonl), executados **contra a API real**
(mesmo caminho da produção, com modelo e latência reais):

```bash
docker compose exec api python scripts/eval.py            # tabela
docker compose exec api python scripts/eval.py --json     # saída para máquina
docker compose exec api python scripts/eval.py --ids pix,devolucao
```

Cobrem os 4 cenários do enunciado, as 6 armadilhas dos dados, tentativa de injeção, pergunta fora
de escopo e consulta de pedido de outro cliente. Resultado atual: **14/14**.


## Premissas e qualidade dos dados

Os arquivos de origem **não foram editados**. Divergências são reportadas pelo build
(`qualidade_dados`) e tratadas como premissa documentada, nunca corrigidas em silêncio:

| Achado | Impacto no comportamento |
|---|---|
| Pedidos 3 e 20 têm `total_brl` diferente da soma dos itens (R$3.450 vs R$3.498; R$1.400 vs R$1.488) | O agente reporta o total gravado e sinaliza a divergência; não recalcula nem inventa desconto |
| `stock_quantity` é o estoque **atual**, não o da data do pedido | Nunca inferir "estava sem estoque" a partir do estoque de hoje |
| Categorias 6 (Sopro/Madeiras), 7 (Metais) e 8 (Cordas Orquestrais) não têm produtos | Pergunta sobre saxofone/violino recebe resposta honesta, sem invenção |
| Produtos 96 e 113 com estoque 0 (113 descontinuado) | "Violões até R$1.000" retorna 12 disponíveis, não 14 |
| Promoção de 12% no Takamine GD20 (id 95) está **inativa** | Preço correto é R$2.199, sem desconto |
| 18 dos 50 clientes têm pedido; ids 3 e 7 têm 2 pedidos cada (um deles cancelado) | Identificação por telefone, não por nome |

Detalhamento completo em [`memory-bank/02-dados-e-premissas.md`](memory-bank/02-dados-e-premissas.md).

## Exemplos de interação

Cinco conversas em [`docs/exemplos/`](docs/exemplos/), **geradas por script** contra a API real
(`scripts/conversas.py`), não escritas à mão:

| Arquivo | Cenário |
|---|---|
| [01-catalogo-e-preco](docs/exemplos/01-catalogo-e-preco.md) | filtro por faixa de preço e preço de um modelo |
| [02-status-de-pedido](docs/exemplos/02-status-de-pedido.md) | identificação por telefone e status de pedido (multi-turno) |
| [03-politica-de-devolucao](docs/exemplos/03-politica-de-devolucao.md) | arrependimento e defeito, com citação de §4.1, §4.2 e §8.1 |
| [04-fora-de-escopo-e-acessorio](docs/exemplos/04-fora-de-escopo-e-acessorio.md) | assunto fora da loja e acessório não vendido |
| [05-tentativa-de-desvio](docs/exemplos/05-tentativa-de-desvio.md) | pedido para ignorar instruções, recusado pelo guard |

Cada transcrição registra **em qual turno** cada ferramenta foi consultada — é o que demonstra o
"quando consultar" que o enunciado pede.

## Integração da interface

Ponto de partida para quem constrói o front. O contrato completo está em `/docs` (OpenAPI).

1. **Sessão:** `POST /v1/sessions` devolve `access_token`. Guarde **em memória** — não em
   `localStorage`, para reduzir exposição a XSS.
2. **Toda chamada** leva `Authorization: Bearer <access_token>`. Token expirado devolve `401` com
   `detail.code = expired_token`: basta abrir nova sessão.
3. **Chat:** `POST /v1/chat` responde `text/event-stream`. Use `fetch` + `ReadableStream` —
   `EventSource` não envia cabeçalhos, então não funciona com Bearer.
4. **Renderização:**
   - concatene `token.delta` (é a resposta em pedaços);
   - `card` traz o dado estruturado (`produto`, `pedido`, `politica`, `pagamento`) para renderizar
     como bloco, não como texto;
   - se chegar `guard` com `acao = substituir_resposta`, **substitua** o texto já renderizado pelo
     campo `texto` — o gate de preço pode corrigir a resposta depois dos tokens;
   - `usage` atualiza o medidor de tokens; `done` encerra o turno e traz `request_id`.
5. **Erros:** `400` mensagem longa · `401` token · `429` rate limit ou orçamento (leia `Retry-After`).
   Falha no meio do stream chega como evento `error`, não como status HTTP.
6. **CORS:** liberado para as origens de desenvolvimento (`localhost:5173`, `3000`, `4173`),
   configurável em `CORS_ORIGINS`. Os cabeçalhos `X-RateLimit-*` e `X-Budget-Remaining` são expostos
   ao navegador.
7. **Histórico:** `GET /v1/sessions/{id}/messages` devolve os turnos anteriores, útil para reidratar a
   tela. `DELETE /v1/sessions/{id}` encerra e apaga o histórico.

## Limitações conhecidas e o que faria com mais tempo

**Limitações**

1. **Interface simples, sem build step.** É React 18 + htm servido como estático, não um app Vite
   com roteamento e testes de UI. Serve para demonstrar o contrato, não como produto final.
2. **SQLite sem réplica horizontal.** Atende o volume; escalar exigiria banco compartilhado.
3. **Rate limit por origem usa o IP da conexão.** Atrás de proxy, todos compartilham o IP do proxy.
4. **Auditoria em arquivo**, sem rotação automática nem retenção programada.
5. **Retrieval lexical não cobre sinonímia.** "Algo para tocar bossa nova" não acha nada por BM25 —
   o agente precisa reformular com o cliente em vez de inventar.
6. **Sem busca semântica de produto** (decisão do ADR 0003).
7. **Sem autenticação de pessoa**: sessão anônima. Adequado ao escopo, insuficiente para área logada.
8. **Custo em reais/dólares não é calculado** — só tokens. O preço por modelo varia e envelhece.
9. **Evals rodam sob demanda**, não no CI com baseline.
10. **C4 nível 4 fora de escopo**, por decisão registrada em `docs/architecture/c4.md`.

**Com mais tempo, nesta ordem de valor**

1. Retrieval híbrido: BM25 para recall + embeddings só no rerank dos 10 candidatos.
2. Evals no CI, com baseline versionado e bloqueio de regressão.
3. Postgres (dados e sessões) + pgvector, com migração do repositório de dados.
4. Testes automatizados da interface (hoje ela é validada manualmente no navegador).
5. Rotação de auditoria, retenção definida e envio para armazenamento.
6. Rate limit e orçamento distribuídos (Redis) para múltiplas réplicas.
7. Human-in-the-loop para reclamação e devolução de alto valor.
8. Observabilidade com OpenTelemetry e SLO de latência.

## Uso de assistentes de código

Ferramenta principal: **opencode** em modo agente, com skills de engenharia próprias (planejamento,
segurança, IA, design) e **spec-kit** para desenvolvimento guiado por especificação. O modelo foi o
DeepSeek, usado também como provedor do agente.

**Como foi usado** — não como gerador de código solto, mas em ciclos com critério de aceite:

1. **Leitura antes de escrever.** O agente leu os 6 CSVs e o PDF antes de propor qualquer coisa; a
   análise de dados (volumetria, integridade, divergências) virou premissa documentada e caso de eval.
2. **Plano com trade-offs explícitos.** Cada decisão relevante teve opções, custo e reversão (ADRs
   0001–0004). Duas escolhas do plano original foram revertidas por evidência: guard de escopo por
   regex (virou decisão do modelo) e tipo `C4Context` do Mermaid (layout cruzava rótulos).
3. **Verificação real, não "deve funcionar".** Toda fase terminou com `pytest`, `ruff`,
   `docker compose up --build` e, no fim, `scripts/eval.py` contra a API com modelo real.
4. **Teste antes do conserto.** Todo bug abaixo virou teste de regressão.

**O que o agente errou e como foi pego** (transparência importa mais que a lista de acertos):

| Erro | Como apareceu |
|---|---|
| Gate de preço bloqueava resposta **correta** (`R$ 2.199,00` lido como 2.199 + 00) | primeira execução real do CLI |
| Stoplist de busca mal construída (`(...).__str__().split()` gerava `"('a"`), nenhuma palavra era filtrada | teste com pergunta real, não com `SELECT` de sanidade |
| Prefixo de 6 caracteres não casava `devolver`/`devolução` | teste de retrieval em linguagem natural |
| Contexto inflava para 13,4k tokens no 3º turno | leitura do consumo real |
| `tool_call` fantasma e sem nome no SSE | inspeção do corpo do stream |
| Endereço respondido de memória em vez de consultar o manual | cenário do próprio enunciado |
| Encoding corrompido por comando de shell no Windows | conferência de bytes antes do commit |

**Duas sessões de agente rodaram em paralelo por engano** e colidiram no mesmo working tree. O
histórico ficou entrelaçado (15 commits em 2 minutos, sem duplicação de arquivo). A correção foi
serializar, adotar o que a outra sessão produziu de melhor (infraestrutura de testes, ADR 0001,
`uv.lock`) e manter o hábito de commits pequenos por assunto.


---

## Estrutura

```
api/            # FastAPI + agente
  app/
    api/        # rotas
    core/       # configuração
  tests/
web/            # interface (React 18 + htm, sem build step) + nginx
data/           # CSVs e PDF originais (intocados)
scripts/        # utilitários (build_db, eval, conversas)
docs/           # arquitetura (C4), ADRs, exemplos de conversa
evals/          # casos de teste do agente
memory-bank/    # contexto do projeto para agentes de código
specs/          # artefatos de desenvolvimento (spec-kit)
```

### Desenvolvimento guiado por especificação

O projeto começou com **spec-kit** (GitHub Spec-Driven Development), cada fase com aprovação explícita
antes de avançar. Só os **artefatos** são versionados:

```
specs/
  constitution.md          # princípios do projeto (escrita ANTES do código)
  README.md                # como ler e o que é retrospectivo
  001-atendimento-por-texto/
    spec.md                # o quê e por quê
    plan.md                # stack, arquitetura, riscos
    tasks.md               # tarefas verificáveis, com o commit de cada uma
```

**Honestidade sobre a ordem:** a constituição foi escrita antes da implementação; `spec.md`,
`plan.md` e `tasks.md` foram escritos **depois**, a partir dos commits e do
`memory-bank/03-fases-e-gates.md`. Com dois dias de prazo, o custo de cerimônia por fase foi
timeboxado e o desenvolvimento seguiu com gates registrados no memory-bank. O histórico do Git **não
foi reescrito** para simular outra ordem — spec retroativa é prática válida de SDD (o próprio
spec-kit tem `/speckit.converge`), esconder que é retroativo não seria.

As pastas de ferramenta (`.specify/`, `.opencode/`) ficam fora do controle de versão — são
reproduzíveis com `uvx --from git+https://github.com/github/spec-kit.git specify init` e não
pertencem à entrega.
