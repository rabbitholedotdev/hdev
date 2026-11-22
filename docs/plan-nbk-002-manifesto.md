# Plano — NBK-002 (NotebookEdit volta ao matcher do manifesto)

Spec: sem spec (decisão do dono, 21/11: NotebookEdit "Caminho B")

## Objetivo
Passo 2 do caminho B. O matcher do PreToolUse de edição volta a ser `Write|Edit|MultiEdit|NotebookEdit|Read|AskUserQuestion`, no manifesto (`.hdev/config.json`), no `.claude/settings.json` do núcleo e no `tests/test_sync.py`. Com isso, a etiqueta do app (CHIP-001) também barra o NotebookEdit.

A v0.8.3 trouxe a tolerância (NBK-001): no app, o `hdev check` aceita o matcher com ou sem NotebookEdit. Por isso, quando esta release for promovida, os apps com o `.claude/settings.json` antigo seguem verdes, ao contrário da v0.8.1 (REL-082). Cada app recebe o matcher novo no próximo `hdev sync`, ao fazer merge da main. O número de registros continua 5.

## Critério de pronto
- `python3 -c "import json; print([m['matcher'] for m in json.load(open('.hdev/config.json'))['hooks']['PreToolUse']])"` imprime `['Bash', 'Write|Edit|MultiEdit|NotebookEdit|Read|AskUserQuestion']`.
- `python3 -m unittest tests.test_sync tests.test_hooks.AppChip -q` sai 0.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0 (manifesto e `.claude/settings.json` do núcleo batem).
- `bin/hdev fechar --plan docs/plan-nbk-002-manifesto.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- O merge só entra depois da v0.8.3 promovida no `latest`.
- Release e promoção: com o sim do João. Antes do promote, o pré-check roda `hdev check` em clones dos apps com o `.harnessdev` apontando para a release nova, e a linha `sync` precisa seguir verde onde já está.
- `hdev sync` nos apps: cada um faz quando fizer merge da main.
- A saída da tolerância: entra no NBK-003, quando nenhum app tiver o matcher antigo.
