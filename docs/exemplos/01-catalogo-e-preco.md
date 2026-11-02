# Catálogo com filtro de preço e preço de um modelo

> Consulta de dados: busca com faixa de preço e depois detalhe de um produto.

Transcrição gerada por [`scripts/conversas.py`](../../scripts/conversas.py) contra a API real (`http://127.0.0.1:8000/v1/chat`, provedor definido no `.env`).

---

**Cliente:** Oi! Quais opções de violões vocês têm disponíveis custando até R$1000?

**Assistente:** Temos 12 violões até R$ 1000. Algumas opções:

- Tagima Memphis AC-39 Nylon Natural — R$ 429,90 (disponível)
- Rozini RC-104 Nylon Estudante — R$ 459,90 (disponível)
- Shelby SN-100 Folk Aço Preto — R$ 549,00 (disponível)
- Yamaha C40 Nylon Natural — R$ 599,90 (disponível)
- Yamaha F310 Aço Natural — R$ 699,90 (disponível)

Quer que eu filtre por nylon ou aço, ou por uma faixa de preço mais específica?

> consultou: `buscar_produtos`

> guard: `preco_sem_ferramenta`

---

**Cliente:** E quanto custa o Takamine GD20? Ele está com desconto?

**Assistente:** O Takamine GD20 Dreadnought Natural sai por *R$ 2.199,00* e está disponível (5 em estoque). Não tem promoção ativa nele agora.

Sobre violões até R$ 1.000, achei 12 opções. Algumas delas:
- Tagima Memphis AC-39 Nylon Natural — R$ 429,90 (disponível)
- Rozini RC-104 Nylon Estudante — R$ 459,90 (disponível)
- Shelby SN-100 Folk Aço Preto — R$ 549,00 (disponível)
- Giannini GF-1R Aço Folk Sunburst — R$ 579,90 (disponível)
- Yamaha C40 Nylon Natural — R$ 599,90 (disponível)

Quer que eu filtre por nylon ou aço, ou por uma faixa de preço mais específica?

> consultou: `detalhe_produto`, `buscar_produtos`

---

## O que aconteceu

- **Ferramentas chamadas:** `buscar_produtos`, `detalhe_produto`
- **Guard acionado:** `preco_sem_ferramenta`
- **Requisições:** c7d6afcc7c47, b8b747102444
