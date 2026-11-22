# Plano — v2-pr2-work-tree

Spec: sem spec (pedido fechado do dono: árvore `work/<id>/`, sem spec nova)

## Objetivo
Uma unidade mora em `work/<id>/`, e `judge`, `fechar` e `base` aceitam `work/<id>/plan.md` sem deixar de aceitar `docs/plan-<tarefa>.md`.

## Critério de pronto
- `python3 -m unittest tests.test_fechar tests.test_judge tests.test_base tests.test_triage -q` verde.
- `python3 -m unittest discover -s tests -q` verde.
- `bin/hdev check` verde.
- `bin/hdev fechar --plan work/v2-pr2-work-tree/plan.md --dry-run` na branch da PR sai 0 e diz que o commit do marco foi pulado.
- [juiz] o caminho legado `docs/plan-*` continua valendo; tetos iguais (AGENTS 65/80, hooks 7, skills 5, subagentes 2); CLI de área sem mudança de comportamento; `fechar` não commita fora da branch base.

## Abordagem
Um helper (`unit_id`) lê o id da pasta em `work/<id>/plan.md` e o id legado no nome `docs/plan-*`. O marco do `fechar` só nasce na `base_branch`. Triage é determinística por flags. Jev sem chave (exit 2): segui sem worker.

## Passos
1. Testes que falham: id da pasta, marco pulado fora da base, `judge`/`base` com `work/<id>/plan.md`, `hdev triage`.
2. Implementar o mínimo para os testes passarem.
3. `hdev check` verde.
4. `hdev fechar --plan work/v2-pr2-work-tree/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
5. Juiz grok no operator host (não roda nesta VM).

## Fora de escopo
- Push, merge, tag, bump de versão.
- Rodar o juiz grok ou o fallback Codex.
- Mudar a CLI de área, os tetos, os hooks ou as skills além do caminho do plano.
- Apagar o alias `docs/plan-<tarefa>.md`.
