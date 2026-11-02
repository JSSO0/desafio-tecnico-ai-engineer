# Aplicação da política de devolução

> Regra da loja: prazo, condições, reembolso e quem paga o frete, com citação da seção.

Transcrição gerada por [`scripts/conversas.py`](../../scripts/conversas.py) contra a API real (`http://127.0.0.1:8000/v1/chat`, provedor definido no `.env`).

---

**Cliente:** Me arrependi da compra que fiz online, posso devolver?

**Assistente:** Pode sim. Pela política de trocas e devoluções, compras online têm *7 dias corridos* após o recebimento pra desistir, sem precisar justificar.

O produto precisa estar na embalagem original, sem sinais de uso, com todos os acessórios e manuais. O reembolso sai na mesma forma de pagamento em até 10 dias úteis, e o frete da devolução é por nossa conta.

Quer que eu já encaminhe seu pedido pra equipe dar início à devolução?

> consultou: `consultar_politicas`

---

**Cliente:** E se o produto vier com defeito?

**Assistente:** Se vier com defeito de fabricação, você pode trocar em até *30 dias corridos* após a compra (política de trocas, §4.2). Depois disso, a garantia legal de *90 dias* continua valendo — a gente pode intermediar com o fabricante pra você (§8.1).

Só não cobre mau uso, queda, umidade excessiva ou modificação não autorizada. Muitos fabricantes ainda dão garantia própria de 6 meses a 2 anos, que vem no certificado do produto.

Quer que eu registre o defeito pra equipe avaliar?

> consultou: `consultar_politicas`

---

## O que aconteceu

- **Ferramentas chamadas:** `consultar_politicas`
- **Guard acionado:** não
- **Requisições:** 34af5e7926fa, ab416944736a
