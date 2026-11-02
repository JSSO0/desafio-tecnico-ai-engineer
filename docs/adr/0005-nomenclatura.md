# ADR 0005 — Padrão de nomenclatura

- **Status:** aceito
- **Data:** 2026-11-02
- **Contexto:** o código misturava português e inglês, às vezes dentro da mesma função: `brl(value)`
  tinha assinatura em inglês e corpo em português (`inteiro`, `centavos`). Não era escolha — era
  acúmulo.

## Decisão

**Identificador de código em inglês. Fronteira em português.**

| Onde | Idioma | Por quê |
|---|---|---|
| Variáveis, funções, classes, módulos | inglês | o stack é inglês (FastAPI, LangChain) e a maior parte do código é infraestrutura |
| Parâmetros de ferramenta (`termo`, `categoria`, `telefone`) | **português** | é o schema que o modelo lê; mudar seria mudar o contrato com o LLM |
| Chaves de saída (`secao`, `preco`, `politica`) | **português** | contrato com a interface e com o log de auditoria |
| Mensagens ao usuário e ao operador | **português** | quem lê é a loja |
| Nomes de teste (`test_posso_devolver_traz_secao_4_1`) | **português** | são frases de comportamento, não nomes de símbolo |

## Alternativas descartadas

| Alternativa | Por que não |
|---|---|
| Tudo em português (linguagem ubíqua radical) | coerente com DDD, mas o código é majoritariamente infraestrutura; `store.append_message` em português não ganha nada e perde familiaridade com a documentação das libs |
| Tudo em inglês, inclusive strings e parâmetros | quebraria o contrato com o modelo e a leitura de quem opera a loja |
| Não padronizar | foi o que gerou o problema: 8 arquivos com metade de cada idioma |

## Consequências

- 436 identificadores renomeados em 18 arquivos, com **tokenizador** e não regex: regex trocaria
  também texto dentro de string, que é justamente o que o cliente lê.
- Nenhum parâmetro de ferramenta mudou — o contrato com o modelo e os evals seguem idênticos.
- Custo: diff grande, sem ganho funcional. Feito de uma vez, num commit só, com suíte verde antes e
  depois.

## Reversão

Não há automação que force o padrão; a verificação é em revisão. Se o time preferir tudo em
português, a renomeação é mecânica e o teste continua verde.