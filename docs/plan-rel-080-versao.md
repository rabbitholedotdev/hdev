# Plano — REL-080 (versão 0.8.0)

Spec: sem spec (pedido do dono, 20/11: "corta a release v0.8.0")

## Objetivo
Versão 0.8.0 do núcleo: o que estava em `Unreleased` (#16 a #24: cache de código, biblioteca, improve probe e compose, braço real do eval, correções do handoff e do fechar) vira `## [0.8.0]`. Minor porque entram comandos novos (`hdev improve compose` e `revert`, runner `claude` real). Este commit só toca `hdev/__init__.py`, `CHANGELOG.md` e `docs/` (ADR 0009). Depois do merge: tag anotada `v0.8.0` e instalação em `/opt/harness-dev/releases/v0.8.0`, sem promover o `latest` (decisão do dono, 20/11: "só corta").

## Critério de pronto
- `python3 -c "import hdev; print(hdev.VERSION)"` imprime `0.8.0` e sai 0.
- `grep -c '^## \[0.8.0\] - 2026-11-20' CHANGELOG.md` imprime `1`; a seção `## [Unreleased]` fica vazia.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan docs/plan-rel-080-versao.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- Promover o canal `latest` para a v0.8.0: decisão do dono, porque o app consumidor segue o `latest`.
- `hdev sync` nos apps seguidores.
