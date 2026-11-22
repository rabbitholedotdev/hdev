---
name: spec
description: "Escreve work/<id>/spec.md a partir do brief. Use depois do briefing, quando pedirem a spec."
---

# spec

A partir do caminho escolhido no brief. Sem código.

## Passos
1. Leia `work/<id>/brief.md` (resumo, suposições e a opção escolhida).
2. Leia só `references/template.md` e grave `work/<id>/spec.md`.
3. Rode `hdev spec check work/<id>/spec.md`. 0 segue. 1 corrige a spec. 3 pergunta o default vazio ao dono e preenche a tabela. 2 é erro de uso.

## Fora de escopo
- não confundir com `briefing` (o brief e as opções), `planejar` (o plano) nem `revisar-spec` (a review).
