---
criado: 2026-11-02
atualizado: 2026-11-02
tags: [projeto, emporio-da-musica, comandos]
---

# Como rodar

## Subir tudo

```bash
cp .env.example .env      # preencha a chave do provedor escolhido
docker compose up --build
```

- API e Swagger: <http://localhost:8000/docs>
- Saúde: `/healthz` (vivo) e `/readyz` (base carregada + chave presente)
- Configuração ativa: `/v1/meta` (provedor, modelo, `prompt_version`)

## Trocar de provedor

Uma linha no `.env`, sem tocar em código:

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4.1-mini
OPENAI_API_KEY=...
```

## Verificações

```bash
docker compose exec api pytest                 # 146 testes, sem rede e sem chave
docker compose exec api ruff check .           # estilo e imports
docker compose exec api python scripts/eval.py # 14 casos contra a API real
python scripts/conversas.py                    # regenera docs/exemplos/ (roda no host)
docker compose exec api python scripts/build_db.py   # reconstroi a base
```

## Conversar sem a API

```bash
docker compose exec api python -m app.cli
docker compose exec api -T python -m app.cli --once "Quanto custa o Takamine GD20?"
```

## Onde olhar quando algo falha

| Sintoma | Onde |
|---|---|
| Resposta sem preço / "vou confirmar" | `logs/audit-AAAA-MM-DD.jsonl`, campo `guard` |
| `429` | `X-RateLimit-*`, `Retry-After`, `GET /v1/sessions/{id}/usage` |
| Base desatualizada | `docker compose down -v` e subir de novo (reconstroi do CSV) |
| Resposta estranha do modelo | `prompt_version` no `/v1/meta` e em cada linha de auditoria |
