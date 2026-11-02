# ADR 0004 — Orçamento, limites e auditoria

- **Status:** aceito
- **Data:** 2026-11-02
- **Contexto:** cada turno consome tokens pagos e a API é pública. O manual da loja cita a LGPD
  (seção 9) e o enunciado pede que o custo seja visível. Sem controle, um cliente mal-comportado
  (ou um script) consome o orçamento do provedor sem que ninguém perceba.

## Decisão

Três controles no servidor, nenhum no prompt:

| Controle | Valor | Onde é imposto |
|---|---|---|
| Orçamento por sessão | 60.000 tokens | `store.usage()` antes de abrir o stream; `429 budget_exhausted` |
| Mensagens por minuto | 10 por sessão | contagem na janela de 60 s; `429` + `Retry-After: 60` |
| Sessões por origem | 20 por hora | contagem por IP; `429` + `Retry-After: 3600` |
| Auditoria | 1 linha JSONL por turno | PII mascarada, `prompt_version`, `request_id` |

O consumo é visível em três lugares: `GET /usage`, evento SSE `usage` e cabeçalhos
`X-RateLimit-*` / `X-Budget-Remaining`.

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Pedir no prompt que o modelo seja breve | Não é controle: não limita custo nem impede abuso. |
| Só rate limit, sem orçamento | Rate limit por minuto não impede consumo alto em várias sessões. |
| Contador em memória | Reinício do container zera o estado e o orçamento vira ficção. |
| Log em banco relacional | JSONL append-only é suficiente, auditável e não acopla ao caminho de escrita do runtime. |

## Consequências

- O custo é previsível e o cliente sabe quanto falta (o que também educa o uso).
- A trilha serve para depurar ("por que respondeu isso?") sem guardar dado pessoal em claro.
- **Limitação conhecida:** a contagem por origem usa `request.client.host`. Atrás de proxy, todos os
  clientes compartilham o IP do proxy — em produção exige `X-Forwarded-For` de proxy confiável.
- **Limitação conhecida:** o arquivo JSONL cresce sem rotação. Com mais tempo: rotação por tamanho e
  envio para armazenamento com retenção definida.

## Reversão

Os limites são configuração (`budget_tokens`, `max_messages_per_minute`, `max_sessions_per_hour`).
Mover os contadores para Redis mantém a interface do `RuntimeStore`.
