---
criado: 2026-11-01
atualizado: 2026-11-01
tags: [projeto, emporio-da-musica, dados]
---

# Dados e Premissas

Análise feita sobre `data/*.csv` (6 arquivos) e `data/políticas_da_loja.pdf` (8 páginas, v2.1 de junho/2025).

## Volumetria (medida, não estimada)

| Fonte | Registros | Chars | ~Tokens |
|---|---|---|---|
| `products.csv` | 65 produtos (id 81–145, sem lacunas) | 22.004 | 5.500 |
| `customers.csv` | 50 clientes | 3.682 | 920 |
| `orders.csv` | 20 pedidos | 1.301 | 325 |
| `order_items.csv` | 22 linhas | 208 | 52 |
| `promotions.csv` | 25 promoções (4 ativas) | 792 | 198 |
| `categories.csv` | 9 categorias | 730 | 182 |
| `políticas_da_loja.pdf` | 10 seções | 11.728 | **2.930** |

Integridade referencial: **limpa**. Nenhum `product_id`, `customer_id` ou `order_id` órfão; todos os 20
pedidos têm itens.

## As 7 armadilhas (viram casos de eval)

1. **Totais divergentes.** Pedido 3: 2×R$1.749 = R$3.498, mas `total_brl` = 3.450. Pedido 20:
   R$799 + R$689 = R$1.488, mas `total_brl` = 1.400. → O agente reporta o total gravado e sinaliza a
   divergência; **nunca recalcula nem inventa desconto**. O build reporta isso em `qualidade_dados`.
2. **`stock_quantity` é snapshot atual, não histórico.** Pedido 4 (`delivered`) contém o produto 96,
   hoje com estoque 0. → Nunca inferir "estava sem estoque" a partir do estoque atual.
3. **3 categorias declaradas e vazias**: 6 (Sopro/Madeiras), 7 (Metais), 8 (Cordas Orquestrais).
   Com produto: 1 (5), 2 (4), 3 (3), 4 (3), **5 (35)**, 9 (15). → "Tem saxofone?" exige resposta
   honesta ("não temos no catálogo atual"), nunca invenção.
4. **Estoque zero / descontinuado**: 96 e 113 com estoque 0 (113 também `discontinued`); 1 `coming_soon`.
   Impacto direto: "violões até R$1.000" tem 14 resultados na categoria 5, mas só **12 disponíveis**.
5. **Promoção inativa em produto famoso.** Takamine GD20 (id 95) = **R$2.199**, com promoção de 12%
   **inativa** em `promotions`. Teste ideal de "promoção expirada" (§7.3).
   Ativas: 127 (−10%), 121 (−20%), 90 (−18%), 94 (−8%).
6. **Poucos clientes com pedido.** Só 8 dos 50. Ids 3 e 7 têm 2 pedidos cada (um deles cancelado).
   Cliente 3 = `(67) 98432-1098` → pedidos 1 (`delivered`, `BRAB1234567BR`) e 19 (`cancelled`).
7. **`specs` é JSON serializado dentro do CSV.** Parse obrigatório; JSON inválido derruba o build
   (falha alta, não silenciosa).

**Bônus (políticas):** o PDF tem o e-mail como `contato@empóriodamusica.com.br` (com acento, artefato de
extração) na página 2, e `contato@emporiodamusica.com.br` na capa. Usamos a forma da capa.

## Decisões de modelagem

- **CSV → SQLite, não CSV → corpus.** Dados operacionais só por ferramenta tipada, com projeção fixa
  de campos. RAG sobre CSV transformaria "pergunta" em "chunk recuperável": um injection poderia
  despejar a base de clientes. Ver princípio III da constituição.
- **`v_products`** entrega preço de tabela + promoção ativa (maior desconto, se houver duplicidade) e
  `price_final`. Produto 95 sai com `promo_percent = NULL` e `price_final = 2199`.
- **Políticas: 1 arquivo por seção, 1 chunk por subseção** → **25 blocos** (média 118 tokens).
  Arquivo por seção é revisável a olho; chunk por subseção dá precisão na recuperação.
- **Retrieval lexical (FTS5/BM25), sem embeddings.** 25 blocos não justificam ANN; zero dependência.
- **Custo medido:** 280 tokens de política por turno (k=3) contra 2.930 do manual inteiro → **−90%**.

## Retrieval: três correções que custaram iteração

1. `MATCH` com texto natural **quebra** (`?`, pontuação) e aceita operadores (`NEAR`, `*`, `-`) — risco
   de injeção. Todo termo é normalizado e **citado** antes de virar expressão.
2. Prefixo de **5** caracteres como stemming barato de português. Com 6, `devolver` → `devolv` não
   casa com `devolucao` (`devolu`). Com 5, casa.
3. **Re-rank por cobertura ponderada por IDF + boost de título.** BM25 puro premia documento curto e
   termo frequente: "compra" ofuscava "devolução", e "tempo" (raro no corpus) pesava mais que
   "garantia". O boost de título usa a taxonomia do próprio manual.

## Testes que protegem isso

`api/tests/test_data.py` e `api/tests/test_rag.py` — 36 testes, incluindo contagens, integridade,
índice sincronizado, 11 perguntas em linguagem natural com seção esperada, e regressão da stoplist
(uma lista mal construída virava tokens como `"('a"` e **nenhuma** stopword era filtrada — bug real).
