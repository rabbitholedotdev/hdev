# Plano — REL-081 (versão 0.8.1)

Spec: sem spec (decisão do dono, 21/11: "Sim, v0.8.1 + latest")

## Objetivo
Versão 0.8.1 do núcleo: o que estava em `Unreleased` (#28, etiqueta do app da Ratoeira barra escrita em código) vira `## [0.8.1]`. Patch, como o dono escolheu: o comportamento novo fica dentro dos hooks que já existem e não muda comando nem contrato. Este commit só toca `hdev/__init__.py`, `CHANGELOG.md` e `docs/` (ADR 0009). Depois do merge: tag anotada `v0.8.1`, instalação em `/opt/harness-dev/releases/v0.8.1`, `hdev check` com o código novo nos apps que seguem o `latest`, e só então a promoção.

## Critério de pronto
- `python3 -c "import hdev; print(hdev.VERSION)"` imprime `0.8.1` e sai 0.
- `grep -c '^## \[0.8.1\] - 2026-11-21' CHANGELOG.md` imprime `1`; a seção `## [Unreleased]` fica vazia.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan docs/plan-rel-081-versao.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- `hdev sync` nos apps seguidores (o matcher com `NotebookEdit` chega a eles no próximo sync).
