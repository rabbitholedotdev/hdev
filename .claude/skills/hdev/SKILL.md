---
name: hdev
description: "Liga e confere o harness numa área ou repo. Use em init, check, eval, xray, worktree, app da Ratoeira ou fechar com o juiz."
---

# hdev

No núcleo, `bin/hdev`. No app, `python3 .harnessdev/bin/hdev`.

## Passos
1. Projeto novo ou clonado: `hdev area sync` ou `hdev init`. Conferir: `hdev check`.
2. Leia só `references/commands.md` no passo que precisar do verbo (worktree, spec, plano, juiz, app, handoff, eval, xray).
3. Nomes novos em inglês, minúsculas e hífen. Parada só em `harness/prompts/_shared/stop-list.md`. Unidade aberta (`.hdev/state/unit.json`) não encerra a sessão.

## Fechar
`hdev fechar --plan P` roda `gates.full` num clone limpo do HEAD, em shards, com cache por tree sha. `--dry-run` mostra o plano e não roda. `--no-cache` força a corrida. Fora da branch base o marco não nasce. Depois da suíte passar, grava `evals/tasks/<id>/task.json`. No pass, pontua o pull e imprime `hdev reflect --unit <id>`.

## Biblioteca
`hdev library pull` depois da spec aprovada. `hdev library pull --symptom` antes de diagnosticar falha. `hdev reflect` depois do fechar. Skill da biblioteca não se instala.

## Eval e xray
`hdev eval run --case <id> --arms plain,base --runs N` compara braços num clone do `base_sha`. `hdev xray` estima o contexto inicial. O `hdev check` cobra `caps.context_initial`.

## Cache de código
`hdev graph update` refresca `.hdev/cache/graph/`. `hdev impact <arquivo>` lista quem chama ou importa o arquivo, e o que ele chama ou importa. O hook de git faz o mesmo update. Detalhe em `references/commands.md`.

## Fora de escopo
- não confundir com `briefing`, `spec`, `planejar`, `revisar-spec` ou `revisar-diff`: cada uma faz uma etapa. Esta skill é o mapa dos verbos.
- não instalar skill de ferramenta externa nem ligar hook novo no Claude. O cache é comando e hook de git.
