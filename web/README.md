# Interface de atendimento

UI estática da Empório da Música: React 18 + htm, **sem build step**. Serve direto do disco ou de
dentro do nginx no Compose.

## Rodar

**Com Docker** (junto da API):

```bash
docker compose up --build
# interface: http://localhost:8080
# API:       http://localhost:8000/docs
```

**Sem Docker** (desenvolvimento):

```bash
python serve.py          # abre http://localhost:5173
```

A API precisa estar em `http://localhost:8000`. A URL é editável na própria tela (painel **Sessão**)
e fica salva em `localStorage`; o padrão é `http://localhost:8000`.

## CORS

A interface chama a API de outra origem, então a API libera:

- `http://localhost:5173` e `127.0.0.1:5173` — `serve.py`
- `http://localhost:8080` e `127.0.0.1:8080` — container nginx
- `localhost:3000` e `localhost:4173` — outras ferramentas de dev

Ajustável em `CORS_ORIGINS` (lista separada por vírgula) no `.env` da API. Os cabeçalhos
`X-RateLimit-*` e `X-Budget-Remaining` são expostos ao navegador.

O container também faz **proxy de `/v1`, `/healthz`, `/readyz` e `/docs`** para a API. Com isso a
interface funciona na mesma origem — útil se você não puder alcançar `localhost:8000` do navegador.
Para usar esse caminho, basta deixar a URL da API vazia no painel de sessão.

## O que a tela faz

- abre sessão anônima e guarda o token **em memória** (não em `localStorage`);
- conversa por `POST /v1/chat` lendo o SSE com `fetch` + `ReadableStream` (não usa `EventSource`,
  que não envia `Authorization`);
- renderiza `card` como bloco estruturado (produto, pedido, política, pagamento);
- ao receber `guard` com `acao = substituir_resposta`, **substitui** o texto já renderizado;
- mostra consumo de tokens e o estado de `/healthz`, `/readyz` e `/v1/meta`;
- permite encerrar a sessão (`DELETE`), o que apaga o histórico no servidor.

## Dependências vendorizadas

O pacote original veio **sem a pasta `vendor/`**, então a página quebrava em `React is not defined`
e parecia erro de rede. As bibliotecas foram baixadas e versionadas localmente:

| Arquivo | Versão | Licença |
|---|---|---|
| `vendor/react.production.min.js` | 18.3.1 | MIT |
| `vendor/react-dom.production.min.js` | 18.3.1 | MIT |
| `vendor/htm.umd.js` | 3.1.1 | Apache-2.0 |

Nenhum passo de instalação é necessário: não há `node_modules` nem bundler.
