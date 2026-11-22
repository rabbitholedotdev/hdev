---
name: revisar-diff
description: "Revisa o diff em outro provedor, antes do juiz. Use depois de implementar, quando pedirem revisar-diff."
---

# revisar-diff

O implementador não faz esta review. Outro provedor, contexto zero.

## Passos
1. Rode `hdev jev revisar-diff` com spec, plano e diff no state. Sem chave (exit 2), siga e anote.
2. Leia só `references/reading.md`. O diff começa em `hdev base --plan work/<id>/plan.md --sha`.
3. Leia só `references/template.md` e grave `docs/reviews/<tarefa>.md`. `hdev judge` continua o portão.

## Fora de escopo
- não confundir com `revisar-spec` (a spec, antes do código) nem com o `hdev judge` (o portão duro).
