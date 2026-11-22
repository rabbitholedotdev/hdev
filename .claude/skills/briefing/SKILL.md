---
name: briefing
description: "Fecha work/<id>/brief.md com a fronteira vazia. Use no começo da peça, quando pedirem briefing ou brief."
---

# briefing

Modelo forte, na sessão interativa. Não escreve spec nem código.

## Passos
1. Rode `hdev triage --id <id> --full` (trilha cheia; `--trivial` só se couber num commit). O verbo grava `work/<id>/state.json`.
2. Leia só `references/gate.md` e grave `work/<id>/brief.md`. Pare se o portão não fecha.
3. Na mesma sessão, leia só `references/options.md` e acrescente `## Opções`. O dono escolhe uma.
4. Rode `hdev library pull --spec work/<id>/brief.md --tag pergunta`. Só entram lições com essa tag.

## Fora de escopo
- não confundir com `spec` (a spec), `planejar` (o plano) nem `revisar-spec` (a review).
- Não pesquisa além do que o portão pedir. Não chama o juiz.
