# Plano — NBK-001 (o check do app tolera o matcher com ou sem NotebookEdit)

Spec: sem spec (decisão do dono, 21/11: NotebookEdit "Caminho B")

## Objetivo
O plano é voltar com `NotebookEdit` no matcher do PreToolUse de edição sem deixar o `hdev check` dos apps vermelho, o que aconteceu na v0.8.1 (REL-082). No app, o `.claude/settings.json` esperado vem dos hooks da release (`init.settings_text` via `.harnessdev`). Quando a release muda o matcher, os 69 apps que hoje batem (o a consumer app main, 51 worktrees, 3 repos e 14 temporários) passam a divergir na linha `sync` até cada branch rodar `hdev sync` e commitar.

Este é o passo 1 do caminho B. No app, o `settings_diff` (`hdev/sync.py`) passa a tratar `Write|Edit|MultiEdit|Read|AskUserQuestion` e `Write|Edit|MultiEdit|NotebookEdit|Read|AskUserQuestion` como o mesmo matcher, nos dois sentidos. Assim, a release seguinte pode mudar o manifesto, e cada app faz o sync quando fizer merge da main. O núcleo segue estrito. Qualquer outra diferença segue divergindo.

## Critério de pronto
- `python3 -m unittest tests.test_sync.MatcherNotebookEdit -v` sai 0 com os 3 casos:
  - o app aceita o matcher com ou sem NotebookEdit nos 3 pares release/app (`settings_diff` vazio, `check_sync` ok, `hdev sync --check` 0);
  - o app com outro matcher (`Write|Edit`) segue divergindo;
  - o núcleo com o matcher trocado segue divergindo.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0 (o manifesto de hooks e o `.claude/settings.json` do núcleo não mudam).
- `bin/hdev fechar --plan docs/plan-nbk-001-check-tolerante.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- O `NotebookEdit` no manifesto: entra no NBK-002, depois desta release promovida, com pré-check em clone de cada app com o `.harnessdev` apontando para a release nova.
- O sync dos apps: cada um faz quando fizer merge da main.
- A saída da tolerância: entra no NBK-003, quando o pré-check mostrar 0 apps com o matcher antigo.
- Release e promoção do `latest`: com o sim do João, depois do merge.
