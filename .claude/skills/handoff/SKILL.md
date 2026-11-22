---
name: handoff
description: "Abre a sessão nova quando o contexto enche. Use quando o hook avisar ou hdev handoff for o próximo passo."
---

# handoff

Não comece unidade nova nesta sessão.

## Passos
1. Feche o que for fato. Não escreva `## Handoff` à mão em `docs/progress.md`.
2. Leia só `references/command.md` e rode `hdev handoff` sem pipe. A sessão nova recebe plano, brief, permissões de pé, estado, próximo passo e o mesmo modelo. Exit 0: encerre esta sessão, sem apagar a antiga. Exit 1: fique.

## Fora de escopo
- não confundir com `hdev resume` (PAREI e a fila) nem com abrir uma unidade nova.
