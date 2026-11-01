# AGENTS.md

Instruções para qualquer agente de código (opencode, Claude Code, Copilot, Cursor) que abrir este repositório.
Fonte de verdade do contexto do projeto. Mantenha atualizado ao final de cada fase.

## O que é este projeto

Agente de atendimento ao cliente da **Empório da Música** (loja fictícia de instrumentos musicais) para o
desafio técnico de AI Engineer da Artefact. Entrega avaliada por: repositório público com histórico real,
README com justificativas, e 3–5 conversas de exemplo.

## Regras invioláveis

1. **Nenhum segredo no repositório.** Chaves só no `.env` (gitignored) ou em `env_file` do Compose.
   Nunca no front-end, nunca em log, nunca em imagem Docker, nunca nesta pasta `memory-bank/`.
2. **CSV não entra em corpus de RAG.** Dados operacionais são acessados apenas por ferramentas tipadas
   com projeção de campos. Motivo: minimização de dados + resistência a prompt injection.
   Ver `memory-bank/02-dados-e-premissas.md`.
3. **Preço, estoque e prazo só saem de resultado de ferramenta.** O gate de saída bloqueia resposta que
   cite `R$` sem tool de preço no turno. Não afrouxe esse gate.
4. **Autorização não é decidida pelo modelo.** `consultar_pedido` usa o cliente vinculado à sessão;
   nunca aceite `customer_id` vindo do modelo.
5. **Ferramentas são read-only.** Nenhuma tool escreve em banco, arquivo de negócio ou serviço externo.
6. **Commits por incremento coerente.** Sem force-push, sem squash de tudo em um commit.
   Um commit = um assunto, tipo convencional (`feat`/`fix`/`test`/`docs`/`refactor`/`chore`) com escopo
   (`feat(db):`, `test(rag):`). Se o diff passa de ~10 arquivos ou mistura assuntos, quebre em commits.
   Mudança de comportamento e o teste dela entram juntos.

## Comandos

```bash
docker compose up --build          # sobe a API
docker compose logs -f api         # logs
docker compose exec api pytest     # testes
docker compose exec api ruff check .
```

## Onde está cada coisa

| Preciso de… | Vá para |
|---|---|
| Decisões de arquitetura e por quê | `memory-bank/01-arquitetura-e-decisoes.md`, `docs/adr/` |
| Armadilhas dos dados (leia antes de mexer) | `memory-bank/02-dados-e-premissas.md` |
| Estado das fases e o que foi aprovado | `memory-bank/03-fases-e-gates.md` |
| O que falta | `memory-bank/04-tasks-abertas.md` |
| Diagramas | `docs/architecture/` (Mermaid) |
| Casos de teste do agente | `evals/casos.jsonl` |
| Especificações e constituição | `specs/` |

## Sobre as ferramentas de spec-driven development

`.specify/` e `.opencode/` são **ferramenta local, gitignored** — não fazem parte da entrega.
O que é versionado são os artefatos: `specs/constitution.md` e, por feature, `specs/NNN-*/spec.md`,
`plan.md`, `tasks.md`.

Para reativar os comandos `/speckit.*` em um clone novo:

```bash
uvx --from git+https://github.com/github/spec-kit.git specify init --here --force \
  --non-interactive --integration opencode
```

## Convenções

- Python 3.12, type hints em tudo, `ruff` limpo.
- Prompt de sistema é **arquivo versionado** em `api/app/agent/prompts/`; o hash curto entra no log de auditoria.
- Toda mudança de comportamento do agente exige um caso novo em `evals/casos.jsonl`.
- Ao terminar uma fase: atualize `memory-bank/03-fases-e-gates.md` e faça um commit descritivo.
