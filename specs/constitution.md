# Constitution — Empório da Música (Agente de Atendimento)

Desafio técnico AI Engineer · Artefact · entrega 02/11/2026

Estes princípios valem para toda feature. Em caso de conflito, a ordem abaixo é a prioridade.

## I. Fidelidade factual acima de fluência

O agente nunca afirma preço, estoque, prazo ou condição sem que o dado venha de uma execução de
ferramenta no mesmo turno. Uma resposta fluente e errada é pior que uma resposta curta e correta.

- Gate determinístico de saída: resposta que cita `R$` sem tool de preço no turno é bloqueada.
- Política só é citada a partir de seção recuperada; sem evidência, admitir e encaminhar à gerência.

## II. Segredo fora do cliente, sempre

Chave de provedor vive apenas no servidor (`env`/`env_file`). Nunca no bundle, nunca em log, nunca
na imagem, nunca no `memory-bank/`. Verificação automatizada no CI local: `grep` por padrões de chave.

## III. Dados por ferramenta, não por corpus

Dados operacionais são acessados apenas por ferramentas tipadas com projeção fixa de campos.
CSV não entra em índice de recuperação. Motivo duplo: minimização de dados e resistência a
prompt injection (o modelo não consegue "pedir" o que a ferramenta não devolve).

## IV. Autorização não é decisão do modelo

A identidade do cliente é vinculada à sessão no servidor. Ferramentas nunca aceitam identificador de
cliente vindo do modelo. Toda leitura é escopada ao que a sessão tem direito.

## V. Ferramentas read-only

Nenhuma ferramenta escreve em banco de negócio, arquivo de negócio ou serviço externo. O blast radius
de um prompt injection bem-sucedido é uma resposta errada — nunca uma transação.

## VI. Simplicidade verificável

Menor solução que resolve o problema, com dependência mínima. Nada de vector DB, embeddings ou
multiagente sem dor concreta. Toda decisão de complexidade precisa de justificativa no README.

## VII. Observabilidade e limite por padrão

Todo turno gera registro de auditoria (com PII redigida) e consome orçamento de tokens contabilizado.
Rate limit e orçamento são impostos no servidor e visíveis ao cliente da API.

## VIII. Entrega incremental com gate humano

Cada fase termina em artefato verificável, commit próprio e aprovação explícita antes da próxima.
Sem force-push. O histórico do Git é parte da entrega.

## Portões de qualidade (por fase)

1. `ruff check` limpo e `pytest` verde.
2. `docker compose up --build` do zero funciona.
3. Nenhum segredo rastreável no diff.
4. Caso novo em `evals/casos.jsonl` para toda mudança de comportamento do agente.
5. `memory-bank/03-fases-e-gates.md` atualizado.
