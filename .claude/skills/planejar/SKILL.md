---
name: planejar
description: "Grava work/<id>/plan.md com critério verificável e TDD. Use com review sem Blocker, ou sem spec se for trivial."
---

# planejar

Saída: `work/<id>/plan.md`. Sem código nesta etapa.

## Passos
1. Trivial: o plano declara `sem spec` e o motivo. Senão, leia `work/<id>/spec.md` e `work/<id>/review.md`. Com Blocker, pare: a skill `revisar-spec` roda de novo. Sem Blocker, rode `hdev library pull --spec work/<id>/spec.md`.
2. Rode `hdev jev rotear` com a spec no state. Sem chave (exit 2), siga e anote. Não imprima a chave.
3. Leia só `references/template.md` e grave o plano. Critério de pronto é comando. Passos em TDD.
4. Rode `hdev base --plan work/<id>/plan.md --marcar`.

## Fora de escopo
- não confundir com `spec` (escreve a spec), `revisar-spec` (a review) nem `revisar-diff` (o diff).
