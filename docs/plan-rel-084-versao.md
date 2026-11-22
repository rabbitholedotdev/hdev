# Plano — REL-084 (versão 0.8.4)

Spec: sem spec (decisão do dono, 21/11: "Sim, #34 + v0.8.4")

## Objetivo
Versão 0.8.4 do núcleo: o que estava em `Unreleased` vira `## [0.8.4]`. Isso é o #34 (NBK-002): o `NotebookEdit` volta ao matcher do PreToolUse de edição. É patch, porque é a mesma correção da v0.8.1, agora sem quebrar os apps: a v0.8.3, que está no `latest`, aceita no app o matcher com ou sem NotebookEdit. Este commit só toca `hdev/__init__.py`, `CHANGELOG.md` e `docs/` (ADR 0009).

Depois do merge vêm a tag anotada `v0.8.4`, a instalação em `/opt/harness-dev/releases/v0.8.4` e o pré-check:
- `hdev check` num clone do a consumer app com o `.harnessdev` apontando para a v0.8.3 e para a v0.8.4, com as mesmas falhas;
- a linha `sync` da v0.8.4, simulada em cada app que hoje passa, tem de seguir verde.

Só então a promoção.

## Critério de pronto
- `python3 -c "import hdev; print(hdev.VERSION)"` imprime `0.8.4` e sai 0.
- `grep -c '^## \[0.8.4\] - 2026-11-21' CHANGELOG.md` imprime `1`; a seção `## [Unreleased]` fica vazia.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan docs/plan-rel-084-versao.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- `hdev sync` nos apps: cada um faz quando fizer merge da main.
- A saída da tolerância: entra no NBK-003.
