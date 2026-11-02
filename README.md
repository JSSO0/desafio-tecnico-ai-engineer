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

- API: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Health: <http://localhost:8000/healthz> · <http://localhost:8000/readyz>
- Configuração ativa: <http://localhost:8000/v1/meta>

### Trocar de provedor

Uma linha no `.env`, sem tocar em código:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
```

---

## Decisões técnicas

*(justificativa completa no fechamento — ver `docs/adr/` e `memory-bank/01-arquitetura-e-decisoes.md`)*

- **Híbrido ferramenta + seção:** dados operacionais por 6 ferramentas tipadas sobre SQLite;
  políticas por recuperação em 25 blocos do manual, com citação. Nada de RAG sobre CSV.
- **Retrieval lexical (FTS5/BM25)** com prefixo de 5 caracteres e re-rank por cobertura com IDF:
  280 tokens de política por turno contra 2.930 do manual inteiro.
- **Token opaco de sessão** em vez de JWT (revogação e orçamento por sessão) — ADR 0002.
- **Guardrail no código, não no prompt** — o gate de preço roda sobre a saída.

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

## Limitações conhecidas e o que faria com mais tempo

*(preenchido no fechamento)*

## Uso de assistentes de código

*(preenchido no fechamento)*

---

## Estrutura

```
api/            # FastAPI + agente
  app/
    api/        # rotas
    core/       # configuração
  tests/
data/           # CSVs e PDF originais (intocados)
scripts/        # utilitários (build_db, smoke tests)
docs/           # arquitetura (C4), ADRs, exemplos de conversa
evals/          # casos de teste do agente
memory-bank/    # contexto do projeto para agentes de código
specs/          # artefatos de desenvolvimento (spec-kit)
```

### Desenvolvimento guiado por especificação

O projeto é construído em fases com **spec-kit** (GitHub Spec-Driven Development), cada uma com
aprovação explícita antes de avançar. Só os **artefatos** são versionados:

```
specs/
  constitution.md        # princípios do projeto (prioridade em caso de conflito)
  001-*/spec.md          # o quê e por quê
  001-*/plan.md          # stack, arquitetura, restrições
  001-*/tasks.md         # tarefas verificáveis
```

As pastas de ferramenta (`.specify/`, `.opencode/`) ficam fora do controle de versão — são
reproduzíveis com `uvx --from git+https://github.com/github/spec-kit.git specify init` e não
pertencem à entrega.
