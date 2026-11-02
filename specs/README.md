# Especificações

> **Estado: retrospectivo.** Estes artefatos foram escritos **depois** da implementação, a partir dos
> commits e do [`memory-bank/03-fases-e-gates.md`](../memory-bank/03-fases-e-gates.md). O histórico do
> Git **não foi reescrito** para parecer que as specs vieram antes. A numeração e os requisitos
> descrevem o que foi construído e verificado, não um plano ideal.

## Por que só a constituição existia

O projeto começou com spec-kit (`specify init --integration opencode`) e a
[constituição](constitution.md) foi escrita antes de qualquer código. As specs de feature, não: com
prazo de dois dias, o custo de cerimônia por fase foi timeboxado em 20 minutos e o desenvolvimento
seguiu com gates registrados no `memory-bank` — cada fase só avançava com artefato verificável e
aprovação.

Isso está declarado no README, na seção "Uso de assistentes de código". **Não havia spec de feature
no momento da entrega**; estes documentos foram produzidos depois, para deixar o processo auditável
em vez de perdido em conversa.

## Mapa: especificação → código

| Artefato | Fases | Commits |
|---|---|---|
| [spec.md](001-atendimento-por-texto/spec.md) | B1–B7 | todos |
| [plan.md](001-atendimento-por-texto/plan.md) | B1–B7 | todos |
| [tasks.md](001-atendimento-por-texto/tasks.md) | B1–B7 | `548d402` … `f509fd7` |
| [constituicao](constitution.md) | — | escrita **antes** da implementação |

## Onde olhar para julgar o processo

As specs contam o *quê*. Para julgar *como* as decisões foram tomadas, os artefatos mais honestos são:

- [`memory-bank/03-fases-e-gates.md`](../memory-bank/03-fases-e-gates.md) — o que foi entregue em cada
  fase, o que foi verificado e **quais bugs foram encontrados a cada passo**;
- [`docs/adr/`](../docs/adr/) — quatro decisões com alternativas descartadas e critério de reversão;
- [`README.md`](../README.md#uso-de-assistentes-de-código) — o que a IA fez, o que ela errou e como
  cada erro foi detectado.
