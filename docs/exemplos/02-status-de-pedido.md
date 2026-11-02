# Status de pedido com identificação por telefone

> Consulta não trivial: o agente pede o telefone, identifica o cliente e só então consulta os pedidos.

Transcrição gerada por [`scripts/conversas.py`](../../scripts/conversas.py) contra a API real (`http://127.0.0.1:8000/v1/chat`, provedor definido no `.env`).

---

**Cliente:** Oi, meu pedido não chegou ainda, pode ver pra mim?

**Assistente:** Claro! Pra eu consultar seu pedido, me passa seu telefone com DDD?

---

**Cliente:** (67) 98432-1098

**Assistente:** Oi, Pedro! Achei seus pedidos aqui:

- Pedido 19, de 22/02, Taylor 214ce Elétrico Aço Natural, R$ 7.499,00 — *cancelado*, porque o pagamento (boleto) não foi confirmado no prazo.
- Pedido 1, de 15/10/2025, Martin D-28, R$ 11.499,00 — *entregue*, rastreio BRAB1234567BR.

O pedido que não chegou é o 19, certo? Ele foi cancelado por falta de confirmação do boleto. Quer que eu veja com a equipe se ainda dá pra refazer esse pedido?

> consultou: `identificar_cliente`, `consultar_pedido`

---

**Cliente:** E o pedido 19?

**Assistente:** O pedido 19 está *cancelado*: o boleto não foi pago/confirmado dentro do prazo, então o pedido não seguiu para entrega.

Se quiser, posso verificar com a equipe se dá pra refazer o pedido da Taylor 214ce. Quer?

---

## O que aconteceu

- **Ferramentas chamadas:** `consultar_pedido`, `identificar_cliente`
- **Guard acionado:** não
- **Requisições:** 8c7a79ea9346, fc0c7b2704ff, 5b95acdaf59d
