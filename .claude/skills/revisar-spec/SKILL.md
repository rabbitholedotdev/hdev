---
name: revisar-spec
description: "Revisa a spec em outro provedor, sem histórico. Use depois da spec e antes do plano, quando pedirem revisar-spec."
---

# revisar-spec

Outro provedor, sem histórico da sessão que escreveu a spec. Não instala o plugin EGM.

## Passos
1. Rode `hdev grok-review --titulo "spec <id>"` ou `hdev codex-exec --isolar --titulo "spec <id>"`. O pedido leva só o caminho `work/<id>/spec.md`.
2. Leia só `references/stages.md` e rode os estágios nessa ordem. No máximo uma reauditoria por estágio.
3. Leia só `references/template.md` e grave `work/<id>/review.md`. Zero Blocker para passar.

## Fora de escopo
- não confundir com `spec` (escreve a spec), `planejar` (o plano) nem `revisar-diff` (o diff).
