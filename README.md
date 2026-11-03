# Empório da Música — Customer Support Agent

A customer-support agent for **Empório da Música** (a fictional musical-instrument store in Campo
Grande, Brazil), built as the deliverable for Artefact's AI Engineer technical challenge.

The agent talks to customers in Portuguese, in the store's own voice. It answers from **operational
data** (catalogue, orders) through deterministic tools and from **internal policy** through
section-level retrieval, and it declines what falls outside the store's scope.

## How this README maps to the brief

| The brief asks for | Where |
|---|---|
| Instructions to run: environment, model provider, commands | [Running it](#running-it) |
| Justification of technical decisions: framework, LLM, retrieval, prompt strategy | [Technical decisions](#technical-decisions) |
| Known limitations and what I would do with more time | [Known limitations](#known-limitations-and-what-i-would-do-with-more-time) |
| Use of code assistants: which, and how | [Use of code assistants](#use-of-code-assistants) |

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Agent | LangChain v1 (`create_agent`, ReAct loop) |
| API | FastAPI (native OpenAPI/Swagger) |
| Data | SQLite (built from the original CSVs) |
| Policy | Markdown per section + FTS5/BM25 (SQLite) |
| Providers | OpenAI, Anthropic, DeepSeek (switch via `.env`) |
| Infra | Docker Compose |

---

## Running it

### Requirements

- **Docker with Compose** — that is the only requirement to run everything.
- Python 3.12 and Node are **not** needed on the host: the API, the database build and the interface
  all run inside containers. Python 3.12 is only needed if you run the test suite outside Docker.

### Environment setup

```bash
cp .env.example .env      # then fill in the key of the provider you chose
docker compose up --build
```

The **only required variable is the provider API key**. Everything else has a working default:

| Variable | Default | What it does |
|---|---|---|
| `LLM_PROVIDER` | `deepseek` | `openai`, `anthropic` or `deepseek` |
| `LLM_MODEL` | `deepseek-chat` | any tool-calling model from that provider |
| `LLM_TEMPERATURE` | `0.2` | low on purpose: factual support, not creative writing |
| `DEEPSEEK_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | — | fill only the one for the active provider |
| `BUDGET_TOKENS` | `60000` | per-session token budget, enforced server-side |
| `MAX_MESSAGES_PER_MINUTE` | `10` | per-session rate limit |
| `MAX_SESSIONS_PER_HOUR` | `120` | per-origin session cap (anti denial-of-wallet) |
| `SESSION_TTL_MINUTES` | `30` | sliding session lifetime |
| `CORS_ORIGINS` | dev origins | comma-separated; empty turns CORS off |

**The provider key never leaves the server.** It is read from the environment by the API, is absent
from the UI bundle, from the images and from the logs (verified by grep over the whole history), and
the browser only ever holds an opaque session token.

### Endpoints once it is up

- **Interface:** <http://localhost:8080>
- API: <http://localhost:8000> · Swagger: <http://localhost:8000/docs>
- Health: `/healthz` · `/readyz` · Active configuration: `/v1/meta`

To work on the interface without Docker: `cd web && python serve.py` (serves on
<http://localhost:5173>). Details in [`web/README.md`](web/README.md).

### Commands

```bash
docker compose up --build                 # start API + interface
docker compose ps                         # service status
docker compose logs -f api                # follow the API
docker compose down                       # stop, keeping data
docker compose down -v                    # wipe data: rebuilds the base from CSVs on next start

docker compose exec api pytest            # 162 tests, no network, no key
docker compose exec api ruff check .      # lint and import order
docker compose exec api python scripts/eval.py     # 15 cases against the real model
docker compose exec api python scripts/build_db.py # rebuild SQLite from the CSVs
docker compose exec api python -m app.cli          # talk to the agent without the API
python scripts/conversas.py               # regenerate docs/exemplos/ (runs on the host)
```

### Switching provider

One line in `.env`, no code change:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
```

### Trying the interface

Open <http://localhost:8080> and click **Iniciar atendimento**. Three messages cover the main paths:

| Type this | What should happen |
|---|---|
| `Quais opções de violões vocês têm disponíveis custando até R$1000?` | `search_products` chip + card with price and stock; **12 items**, excluding the out-of-stock and the discontinued one |
| `Oi, meu pedido não chegou. Meu telefone é (67) 98432-1098` | `identify_customer` + `lookup_order` chips; two orders, one cancelled with its reason |
| `Me arrependi da compra online, posso devolver?` | `lookup_policy` chip; 7-day window, 10-business-day refund, §4.1 cited |

The **Sessão** panel shows token usage, remaining budget and the state of `/healthz`, `/readyz` and
`/v1/meta`. The **API URL** field defaults to `http://localhost:8000` and is saved in `localStorage`.
To go through the bundled nginx — same origin, no CORS, and the path that also works from another
machine — set the field to the page origin (`http://localhost:8080`) and click **Conectar**.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| "API offline" in the panel | the API did not start: `docker compose logs api` |
| `401 expired_token` | the 30-minute session expired: **Nova sessão** |
| `429 rate_limited` | more than 10 messages in a minute; wait for `Retry-After` |
| `429 too_many_sessions` | 120 sessions per hour per origin; `eval.py` uses 15 per run |
| `400 message_too_long` | message above 800 characters |
| Answer without a price, asking to confirm | the gate acted: see `logs/audit-YYYY-MM-DD.jsonl`, field `guard` |

The audit trail lives in `logs/audit-YYYY-MM-DD.jsonl`, one record per turn, with phone and e-mail
masked.

---

## Architecture

C4 diagrams (context, containers, components, deployment and dynamic) in Mermaid, with the notation
key and the scope rationale: [`docs/architecture/c4.md`](docs/architecture/c4.md).

In one sentence: client → FastAPI (session, guardrails, ReAct agent, RAG, limits, audit) → read-only
operational SQLite + runtime SQLite + JSONL trail, with an external LLM provider chosen by
configuration.

---

## Technical decisions

Full rationale, alternatives and rollback in [`docs/adr/`](docs/adr/). This section is the short
version of the reasoning.

### Agent framework — LangChain v1 (`create_agent`)

**Chosen** because it supplies, without extra code: the ReAct loop, tool schemas generated from Python
type hints, streaming of token and tool-call chunks, and middleware hooks for cross-cutting concerns.
Rebuilding those means writing and testing several hundred lines of parsing, streaming and message
plumbing — infrastructure, not product.

**Rejected:** a hand-rolled loop (full control, but the control we would gain is over code we would
have to maintain); raw provider SDKs (same, minus the free tool schema); LangGraph directly
(`create_agent` already *is* a LangGraph graph; dropping one level buys nothing for a single-agent
loop).

**Cost accepted:** coupling to a framework that evolves fast. Mitigated by ADR 0001 — the test suite
covers our boundaries (tools, turn extraction, price gate, HTTP contract) and deliberately does not
test the framework, so an upgrade only breaks us if our own contract changes.

### Model and provider

**Requirement:** three providers, switchable by configuration, key never reaching the client.
`init_chat_model(model, model_provider)` resolves the integration lazily and gives one uniform
interface with tool calling.

**Default: DeepSeek (`deepseek-chat`)** — cheapest per token of the three and it passed the tool-calling
suite (15/15) without a single prompt change. OpenAI and Anthropic are one `.env` line away and were
exercised during development.

**Trade-off:** tool-calling reliability varies by model, and a cheap model is where it shows first.
That is why the acceptance test runs the **real model** through the real API — a mocked agent would
hide exactly this difference.

**What would change the choice:** an on-premise requirement (Ollama is one provider key away) or a
material drop in eval pass rate.

### Retrieval architecture — two paths, on purpose

Structured and textual knowledge fail differently, so they are queried differently.

| Knowledge | Path | Why |
|---|---|---|
| Catalogue, orders, promotions | 6 typed tools over SQLite, fixed field projection | exact values, numeric filters, joins and aggregation |
| Internal policy (25 blocks) | FTS5/BM25, 1–3 sections per turn, cited | free-text questions, needs attribution to a section |

**Why not RAG over the CSVs.** Three reasons, in order of weight: (a) numeric predicates ("up to
R$1000"), joins and aggregation are retrieval-hostile — a chunk cannot filter; (b) a chunk dump can
expose the whole customer table, which turns prompt injection into a **disclosure** rather than a
wrong answer; (c) the manual forbids quoting a price without querying the system, and a chunk is not a
query.

**Why not embeddings for policy.** 25 blocks do not justify an ANN index, an embedding provider and an
ingestion pipeline. The real weakness of lexical search is synonymy, and it is documented as such —
hybrid reranking is the next step (ADR 0003), not a silent gap.

**What made lexical retrieval actually work** — three fixes, each found by testing, not by design:

1. **Query sanitisation.** `MATCH` has its own syntax (`"`, `*`, `NEAR`, `-`); free text breaks the
   search and, worse, lets a client inject operators. Every term is normalised and quoted.
2. **A 5-character prefix as a cheap Portuguese stemmer.** At 6, `devolver` did not match
   `devolução` — the stem diverges on the sixth letter.
3. **IDF + title-boost re-ranking.** Plain BM25 ranked "compra" above "devolução" and "tempo" (rare in
   the corpus) above "garantia"; weighting by inverse document frequency and giving the manual's own
   headings a boost fixed the order.

**Measured cost:** ~280 policy tokens per turn, against 2,930 for the whole manual (−90%).

### Prompt strategy

The prompt is a **versioned file** (`api/app/agent/prompts/v1.md`). Its short hash is the
`prompt_version` written to every audit line and exposed by `/v1/meta`, so each answer is attributable
to a prompt revision.

**Structure, in this order:** role → tone (from the manual's §7.1: informal but professional) → the one
non-negotiable rule (never state price, stock or deadline without a tool result) → the tool list with
when-to-use → situation-by-situation guidance (order, promotion, out of stock, out of scope, complaint)
→ output format (WhatsApp: short, no tables, single-asterisk emphasis) → closing.

**What the prompt deliberately does not contain:** data, prices or policy text. Context that is always
present stops being context and becomes noise — and stale data. Retrieval and tools are the only path
to facts.

**Guardrails are not instructions.** Input triage and the price gate are code, not text: asking a model
to "never invent prices" is a wish, while comparing every `R$` in the answer against the tool output of
the same turn is a control.

**Three changes were driven by failure, not taste:**

- factual store fields (address, phone) had to be named as "must query" — the model was deferring;
- WhatsApp emphasis (`*one asterisk*`) replaced markdown, which rendered literally;
- the in-store return rule came from an independent test session that caught the agent granting an
  online-only right.

**History policy:** the model receives the conversation but not tool payloads. That took turn 3 from
13.4k to 2.7k input tokens (−80%). The cost is that it may re-query instead of remembering — cheap, and
the data is always current.

### Data access and authorization

Customer identity lives in the server-side `SessionContext`; tools read from it, never from the
argument the model produced. `lookup_order` takes no `customer_id`: a request for another customer's
order returns "not found", without confirming existence. Every tool opens SQLite read-only. The
consequence is deliberate — a successful prompt injection costs a wrong answer, never a transaction or
a data leak.

### Session and credentials

Opaque 256-bit token, stored only as a SHA-256 hash, 30-minute sliding TTL, revocable per session
(ADR 0002). JWT was rejected: revocation and a per-session budget need server state anyway. The
consequence reaches the client — `EventSource` cannot send headers, so streaming uses `fetch` +
`ReadableStream`.

### Cost and limits

60k tokens per session, 10 messages/minute and 120 sessions/hour per origin, all enforced in the server
and visible in `/usage`, in the `usage` SSE event and in `X-RateLimit-*` headers. "Be brief" in the
prompt was rejected as a control: it limits neither cost nor abuse.

---

## Guardrails, limits and cost

| Layer | What it does |
|---|---|
| Input (code) | rejects messages above 800 characters (`400`) and explicit instruction-override attempts (`guard: injection_attempt`, without calling the provider) |
| Model | persona and tone from the manual; forbids stating price, stock or deadline without a tool |
| Output (code) | price gate: every `R$` must exist in a tool result from the same turn |
| Authorization | opaque token; `lookup_order` uses the session's customer, never an id coming from the model |
| Cost | 60k-token budget per session, 10 messages/minute per session, 120 sessions/hour per origin |
| Audit | one JSONL line per turn in `logs/`, with phone and e-mail masked |

Scope and accessories are **not** blocked by keyword: "do you sell guitar strings?" is a legitimate
question, and the right answer is a polite redirect — not denying service.

## Evaluation

Declarative cases in [`evals/casos.jsonl`](evals/casos.jsonl), executed **against the real API** (same
path as production, with real model and latency):

```bash
docker compose exec api python scripts/eval.py            # table
docker compose exec api python scripts/eval.py --json     # machine-readable
docker compose exec api python scripts/eval.py --ids pix,devolucao
```

They cover the four scenarios from the brief, the six data traps, an injection attempt, an
out-of-scope question and a lookup for another customer's order. Current result: **15/15**.

## Data assumptions and quality

The source files **were not edited**. Divergences are reported by the build (`qualidade_dados`) and
treated as documented assumptions — never silently corrected:

| Finding | Impact on behaviour |
|---|---|
| Orders 3 and 20 have `total_brl` different from the sum of items (R$3,450 vs R$3,498; R$1,400 vs R$1,488) | The agent reports the stored total and flags the divergence; it does not recompute or invent a discount |
| `stock_quantity` is the **current** stock, not the stock at order time | Never infer "it was out of stock" from today's stock |
| Categories 6 (Woodwinds), 7 (Brass) and 8 (Orchestral strings) have no products | A question about a saxophone or a violin gets an honest answer, with no invention |
| Products 96 and 113 have zero stock (113 is discontinued) | "Guitars up to R$1,000" returns 12 available, not 14 |
| The 12% promotion on the Takamine GD20 (id 95) is **inactive** | Correct price is R$2,199, with no discount |
| 18 of the 50 customers have orders; ids 3 and 7 have two each (one cancelled) | Identification by phone, not by name |

Full detail in [`memory-bank/02-dados-e-premissas.md`](memory-bank/02-dados-e-premissas.md).

## Interaction examples

Five conversations in [`docs/exemplos/`](docs/exemplos/), **generated by script** against the real API
(`scripts/conversas.py`), not written by hand:

| File | Scenario |
|---|---|
| [01-catalogo-e-preco](docs/exemplos/01-catalogo-e-preco.md) | price-range filter and the price of one model |
| [02-status-de-pedido](docs/exemplos/02-status-de-pedido.md) | phone identification and order status (multi-turn) |
| [03-politica-de-devolucao](docs/exemplos/03-politica-de-devolucao.md) | buyer's remorse and defect, citing §4.1, §4.2 and §8.1 |
| [04-fora-de-escopo-e-acessorio](docs/exemplos/04-fora-de-escopo-e-acessorio.md) | off-topic subject and an accessory the store does not sell |
| [05-tentativa-de-desvio](docs/exemplos/05-tentativa-de-desvio.md) | request to ignore instructions, refused by the guard |

Each transcript records **which tool was consulted in which turn** — that is what demonstrates the
"when to consult" the brief asks for.

## Frontend integration

Starting point for whoever builds the UI. The full contract is in `/docs` (OpenAPI).

1. **Session:** `POST /v1/sessions` returns an `access_token`. Keep it **in memory** — not in
   `localStorage`, to reduce XSS exposure.
2. **Every call** carries `Authorization: Bearer <access_token>`. An expired token returns `401` with
   `detail.code = expired_token`: just open a new session.
3. **Chat:** `POST /v1/chat` responds with `text/event-stream`. Use `fetch` + `ReadableStream` —
   `EventSource` does not send headers, so it cannot carry the Bearer token.
4. **Rendering:**
   - concatenate `token.delta` (the answer arrives in pieces);
   - `card` carries structured data (`produto`, `pedido`, `politica`, `pagamento`) to render as a
     block, not as text;
   - if a `guard` event arrives with `acao = substituir_resposta`, **replace** the already rendered
     text with its `texto` field — the price gate can correct the answer after the tokens;
   - `usage` updates the token meter; `done` ends the turn and carries `request_id`.
5. **Errors:** `400` long message · `401` token · `429` rate limit or budget (read `Retry-After`).
   A failure mid-stream arrives as an `error` event, not as an HTTP status.
6. **CORS:** open for development origins (`localhost:5173`, `3000`, `4173`), configurable in
   `CORS_ORIGINS`. The `X-RateLimit-*` and `X-Budget-Remaining` headers are exposed to the browser.
7. **History:** `GET /v1/sessions/{id}/messages` returns previous turns, useful to rehydrate the
   screen. `DELETE /v1/sessions/{id}` ends the session and deletes the history.

## Known limitations and what I would do with more time

**Limitations**

1. **Simple interface, no build step.** It is React 18 + htm served as static files, not a Vite app
   with routing and UI tests. It demonstrates the contract; it is not a finished product.
2. **SQLite without horizontal replication.** Fine for this volume; scaling would need a shared
   database.
3. **Per-origin rate limit uses the connection IP.** Behind a proxy, every client shares the proxy's IP.
4. **Audit in a file**, with no automatic rotation or scheduled retention.
5. **Lexical retrieval does not cover synonymy.** "Something to play bossa nova" finds nothing through
   BM25 — the agent has to rephrase with the customer instead of inventing.
6. **No semantic product search** (ADR 0003).
7. **No person-level authentication**: anonymous session. Adequate for the scope, insufficient for a
   logged-in area.
8. **Cost in currency is not computed** — tokens only. Price per model varies and goes stale.
9. **Evals run on demand**, not in CI with a baseline.
10. **C4 level 4 out of scope**, by decision recorded in `docs/architecture/c4.md`.

**With more time, in order of value**

1. Hybrid retrieval: BM25 for recall + embeddings only to rerank the top 10 candidates.
2. Evals in CI, with a versioned baseline and regression blocking.
3. Postgres (data and sessions) + pgvector, migrating the data repository.
4. Automated interface tests (today it is validated manually in the browser).
5. Audit rotation, defined retention and shipping to storage.
6. Distributed rate limit and budget (Redis) for multiple replicas.
7. Human-in-the-loop for complaints and high-value returns.
8. Observability with OpenTelemetry and a latency SLO.

## Use of code assistants

**Main tool: opencode in agent mode**, with purpose-built engineering skills (planning, security, AI,
design) and **spec-kit** for spec-driven development. The model behind it was DeepSeek — the same
provider used by the agent. Supporting tools: Playwright (browser verification), pytest and ruff.

**How it was used** — not as a loose code generator, but in cycles with acceptance criteria:

1. **Read before writing.** The agent read the 6 CSVs and the PDF before proposing anything; the data
   analysis (volume, integrity, divergences) became a documented assumption and an eval case.
2. **Plan with explicit trade-offs.** Every relevant decision had options, cost and a rollback path
   (ADRs 0001–0005). Two choices from the original plan were reverted by evidence: a regex scope guard
   (became the model's judgement) and Mermaid's `C4Context` type (the layout crossed labels).
3. **Real verification, not "it should work".** Every phase ended with `pytest`, `ruff`,
   `docker compose up --build` and, at the end, `scripts/eval.py` against the API with the real model.
4. **Test before fixing.** Every bug below became a regression test.
5. **Review as a gate.** Each phase stopped for human approval before the next one started; the review
   round at the end produced eight accepted improvements and two rejected ones, with reasons.

**What the agent got wrong and how it was caught** (transparency matters more than a list of wins):

| Error | How it surfaced |
|---|---|
| The price gate blocked a **correct** answer (`R$ 2,199.00` parsed as 2,199 + 00) | first real CLI run |
| A badly built search stoplist (`(...).__str__().split()` produced `"('a"`), so no word was filtered | a test with a real question, not a sanity `SELECT` |
| A 6-character prefix did not match `devolver` with `devolução` | natural-language retrieval test |
| Context grew to 13.4k tokens by the third turn | reading real usage |
| Phantom, nameless `tool_call` events in the SSE stream | inspecting the stream body |
| The address answered from memory instead of querying the manual | a scenario from the brief itself |
| Encoding corrupted by a Windows shell command | byte check before committing |
| The agent granted an in-store return window that only applies online, and invented requirements | an independent test session, run against the UI |
| It applied a consistency review to one call site instead of the whole codebase | the reviewer pointed it out; the fix became a lint rule |

**Two agent sessions ran in parallel by mistake** and collided in the same working tree. The history
came out interleaved (15 commits in 2 minutes, no duplicated files). The fix was to serialise, adopt
the best of what the other session produced (test infrastructure, ADR 0001, `uv.lock`) and keep the
habit of small, single-subject commits.

---

## Structure

```
api/            # FastAPI + agent
  app/
    api/        # routes
    core/       # configuration
  tests/
web/            # interface (React 18 + htm, no build step) + nginx
data/           # original CSVs and PDF (untouched)
scripts/        # utilities (build_db, eval, conversations)
docs/           # architecture (C4), ADRs, conversation examples, test rounds
evals/          # agent test cases
memory-bank/    # project context for coding agents
specs/          # development artifacts (spec-kit)
```

### Spec-driven development

The project started with **spec-kit** (GitHub Spec-Driven Development), each phase requiring explicit
approval before moving on. Only the **artifacts** are versioned:

```
specs/
  constitution.md          # project principles (written BEFORE the code)
  README.md                # how to read it and what is retrospective
  001-atendimento-por-texto/
    spec.md                # the what and the why
    plan.md                # stack, architecture, risks
    tasks.md               # verifiable tasks, each with its commit
```

**Honesty about the order:** the constitution was written before implementation; `spec.md`, `plan.md`
and `tasks.md` were written **afterwards**, from the commits and
`memory-bank/03-fases-e-gates.md`. With a two-day deadline, the cost of per-phase ceremony was
timeboxed and development proceeded with gates recorded in the memory bank. The Git history was **not
rewritten** to simulate another order — retrospective specs are a legitimate SDD practice (spec-kit
itself ships `/speckit.converge`); hiding that it is retrospective would not be.

Tool folders (`.specify/`, `.opencode/`) stay out of version control — they are reproducible with
`uvx --from git+https://github.com/github/spec-kit.git specify init` and are not part of the
deliverable.