# Plano — REL-083 (versão 0.8.3)

Spec: sem spec (decisão do dono, 21/11: "Sim, v0.8.3 + latest")

## Objetivo
Versão 0.8.3 do núcleo: o que estava em `Unreleased` vira `## [0.8.3]`. Isso inclui o #31 (CHIP-002: a etiqueta do app também barra escrita por interpretador) e o #32 (NBK-001: o check do app tolera o matcher com ou sem NotebookEdit). É patch, porque os dois ficam dentro dos hooks e do `hdev sync --check` que já existem e não mudam comando, contrato nem o manifesto de hooks. Este commit só toca `hdev/__init__.py`, `CHANGELOG.md` e `docs/` (ADR 0009). Depois do merge vem a tag anotada `v0.8.3`, a instalação em `/opt/harness-dev/releases/v0.8.3` e o pré-check: `hdev check` num clone do a consumer app com o `.harnessdev` apontando para a v0.8.3 e os hooks do manifesto iguais aos da v0.8.2. Só então a promoção.

## Critério de pronto
- `python3 -c "import hdev; print(hdev.VERSION)"` imprime `0.8.3` e sai 0.
- `grep -c '^## \[0.8.3\] - 2026-11-21' CHANGELOG.md` imprime `1`; a seção `## [Unreleased]` fica vazia.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan docs/plan-rel-083-versao.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- O `NotebookEdit` no manifesto: entra no NBK-002, depois desta release promovida.
- `hdev sync` nos apps seguidores (nada muda para eles nesta versão).
