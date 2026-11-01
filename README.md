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

## Premissas e qualidade dos dados

*(preenchido na fase de dados — ver `memory-bank/02-dados-e-premissas.md`)*

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
