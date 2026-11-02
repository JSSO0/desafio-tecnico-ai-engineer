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

*(preenchido ao longo das fases — ver `docs/adr/` e `memory-bank/01-arquitetura-e-decisoes.md`)*

- [ADR 0001 — Estratégia de testes](docs/adr/0001-estrategia-de-testes.md): testamos as nossas
  fronteiras (dados, tools, gate, contrato HTTP), não o loop do LangChain. O motivo e o que
  cada camada protege estão no ADR.

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
