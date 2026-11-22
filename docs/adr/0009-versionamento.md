# ADR 0009 — Padrão de versionamento (fechamento, base obrigatória, SemVer)

- Status: aceito
- Data: 2026-11-15
- Origem: brainstorm Claude/Codex/Grok de 15/11 (`proposta.md`) e decisões do João (15/11, 22:40 -03).

## Contexto

Na Ratoeira, o `commit-turno` commita cada turno com a frase do pedido como mensagem. O `git log` vira uma pilha de
checkpoints ("Base directory…", "Você é o juiz…") e não mostra onde uma unidade fechou, com qual base, nem se foi
juiz pass ou override. A base da unidade (ADR 0008) podia ficar só deduzida. O núcleo não tinha `CHANGELOG.md`, e
apps (um consumer app com vários módulos no mesmo repo) não tinham regra de tag. O core do host não muda.

## Decisão

- Trunk com uma unidade aberta por árvore; branch/worktree (`hdev wt`) só para trabalho paralelo.
- `commit-turno` continua como está: commits de checkpoint, preservados. **Squash é opcional, nunca obrigatório.**
- `hdev fechar --plan P [--resumo T] [--override "quem: motivo"] [--squash] [--dry-run]` grava o marco:
  `INF-006 feito: <resumo>; juiz pass|override`, corpo curto e os trailers `Unidade`, `Base`, `Head` (o SHA julgado),
  `Juiz: pass (<cli>, <run>)` ou `Override: <quem: motivo>`, e `Harness-Versao`. Vazio (`--allow-empty`) quando os
  checkpoints já levaram o código.
- Portões do fechamento: base gravada por `hdev base --plan P --marcar` (dedução, `HEAD` e a base que o 1º
  `hdev judge` grava não fecham); base ancestral de `HEAD`; árvore sem mudança rastreada; intervalo `base..HEAD` sem
  commit cuja 1ª linha comece com o ID de outra unidade; juiz pass deste plano, sem mudança local, com a mesma base, em
  `HEAD` ou num ancestral com só `docs/` no meio. Sem pass, só com `--override`; override não vira pass.
- `--squash`: só se nenhum commit do intervalo está num remoto; cria `bkp/<id>-<sha>`, `reset --soft` na base e
  grava o marco; o juiz roda de novo no SHA novo.
- Índice no `docs/progress.md`: `hdev fechar` imprime a linha `INF-006 | base … | juiz … | fecha … | harness …`.
- Mensagens feitas de propósito: `<ID>: <efeito>`; manutenção sem unidade: `release: vX.Y.Z` ou `chore: …`.
- Núcleo em SemVer com `CHANGELOG.md` (Keep a Changelog, seção `Unreleased`). Em `0.x`, minor para comando, gate ou
  contrato novo. `hdev release` recusa versão sem `## [X.Y.Z]` no changelog; o commit de versão pode tocar
  `CHANGELOG.md` sem invalidar o juiz pass da promoção.
- App: versão independente da unidade e do harness. Tag anotada `<app>-vX.Y.Z` (hífen, não barra; ex.:
  `mcc-v0.1.0`) só na publicação: `hdev app tag <app> vX.Y.Z --publicado`. Imutável; `VERSION`/`CHANGELOG.md` da
  pasta do app, se existem, têm de bater. A tag registra o harness do `.harnessdev.lock`.
- Marcos de unidades antigas (sem reescrever histórico): tag anotada local `unidade/<ID>` no commit que fechou a
  unidade, e `base/<ID>` para a base marcada. Exemplo: `unidade/APP-001..006` e `base/MOD-001`.
- Push só com unidade fechada e o dono liberando destino, branch e tags. Sem force-push.

## Consequências

- `git log --oneline --grep ' feito: '` lista as entregas; os trailers dão base, julgamento e harness.
- Unidade que só tinha base deduzida precisa de `hdev base --marcar` (conferida) antes de fechar.
- Fora de escopo (core): mudar mensagem, momento ou hooks do `commit-turno`.
- Rollback: canal `hdev rollback --to v0.3.9`; código, a tag `rollback/pre-v0.4.0` (= `v0.3.9`, `31765e1`).
