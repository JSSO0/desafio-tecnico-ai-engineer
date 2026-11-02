# ADR 0002 — Sessão com token opaco

- **Status:** aceito
- **Data:** 2026-11-02
- **Contexto:** o front-end (delegado a outro time) precisa de uma credencial para falar com a API.
  Não há conta de usuário, não há login. Ainda assim precisamos de três coisas que dependem de
  identidade: orçamento de tokens por sessão, revogação imediata e histórico isolado.

## Decisão

Token **opaco** de 256 bits (`secrets.token_urlsafe(32)`), guardado no servidor apenas como hash
SHA-256, enviado em `Authorization: Bearer`, com TTL de 30 minutos **deslizantes** e revogação por
`DELETE /v1/sessions/{id}`.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| JWT assinado | Stateless, mas revogação é o problema: invalidar exige allowlist de `jti` — ou seja, estado no servidor de qualquer jeito. Não resolve quota. |
| Sem credencial | Não há como isolar histórico, cobrar orçamento nem revogar. Um cliente consumiria o orçamento do outro. |
| OIDC completo | Resolveria identidade de pessoa, não de sessão anônima. Custo e complexidade sem retorno no escopo. |

## Consequências

- O token **não carrega dado nenhum**: não há PII legível em trânsito, e o servidor pode revogar na hora.
- `session_id` na URL **não é credencial**: a rota confere se o id pertence ao token e devolve 404
  quando não pertence (não confirma existência).
- Como o header é obrigatório, o cliente **não pode usar `EventSource`** para o SSE (ele não envia
  headers). O caminho é `fetch` + `ReadableStream`, o que está documentado no contrato do `/v1/chat`.
- `DELETE` apaga as mensagens junto com a revogação, atendendo ao direito de exclusão da política §9.

## Reversão

Trocar por JWT exige: `jti` no payload, allowlist de revogação e um passo de troca de token. O
restante do código (dependência `require_session`) não muda.
