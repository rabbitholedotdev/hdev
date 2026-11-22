# Plano — REL-082 (versão 0.8.2: matcher sem NotebookEdit)

Spec: sem spec (decisão do dono, 21/11: "Sim, faz a v0.8.2")

## Objetivo
A v0.8.1 pôs `NotebookEdit` no matcher do PreToolUse de edição. O `.claude/settings.json` de cada app está no git, então o `hdev check` dos apps passou a sair 1 na linha `sync` ("arquivo gerado diverge do manifesto"), e o `latest` voltou para a v0.8.0 em 22 s. A v0.8.2 devolve o matcher de antes (`Write|Edit|MultiEdit|Read|AskUserQuestion`) no manifesto, no `.claude/settings.json` e no `tests/test_sync.py`. A etiqueta do app (CHIP-001) continua igual. O commit também sobe a versão para 0.8.2 (`hdev/__init__.py`, `CHANGELOG.md`, `docs/`).

## Critério de pronto
- `python3 -c "import json; print([m['matcher'] for m in json.load(open('.hdev/config.json'))['hooks']['PreToolUse']])"` imprime `['Bash', 'Write|Edit|MultiEdit|Read|AskUserQuestion']`.
- `python3 -c "import hdev; print(hdev.VERSION)"` imprime `0.8.2`; `grep -c '^## \[0.8.2\] - 2026-11-21' CHANGELOG.md` imprime `1`.
- `python3 -m unittest tests.test_hooks.AppChip tests.test_sync -q` sai 0.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan docs/plan-rel-082-versao.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- `hdev sync` nos apps.
- Barrar `NotebookEdit` nos apps cujo matcher não o inclui.
