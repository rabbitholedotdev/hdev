# Plano — v2-pr3-manifest-sync

Spec: sem spec (pedido fechado do dono: manifesto único e `hdev sync`; a spec nova não cabe nesta PR)

## Objetivo
`.hdev/config.json` é o manifesto, e `.claude/settings.json` é gerado a partir dele.

## Critério de pronto
- `bin/hdev sync --check` sai 0.
- `python3 -c "import json;print(len(json.load(open('.claude/settings.json'))['permissions']['allow']))"` imprime no máximo 15.
- `python3 -m unittest discover -s tests -q` verde.
- `bin/hdev check` verde.
- `bin/hdev fechar --plan work/v2-pr3-manifest-sync/plan.md --dry-run` na branch da PR sai 0 e diz que o commit do marco foi pulado.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr3-manifest-sync/evidence/settings-equivalencia.md` (hooks, deny, allow, gates, tetos, CLI de área). O dry-run do fechar está em `work/v2-pr3-manifest-sync/evidence/fechar-dry-run.md`.
  - hooks iguais aos de `b1b4809`: o python imprime `hooks_iguais True`
  - deny igual: o python imprime `deny_igual True`
  - allow de 37 para 15: o python imprime `allow_antes 37` e `allow_depois 15`, com as duas listas
  - uma fonte de teste: o python imprime `sem_tests True` e os argv de `gates.fast` e `gates.full`
  - tetos iguais: o python imprime `caps {"agents": 80, "hooks": 7, "progress": 2000, "skills": 5, "subagents": 2}`
  - CLI de área: `git diff --stat b1b4809 HEAD -- hdev/area.py` não lista arquivo

## Abordagem
`gates.fast` alimenta o Stop e `gates.full` alimenta o `fechar` e o juiz. Chave antiga (`tests`, `judge.tests_command`) é erro, sem leitura dupla. `hdev sync` grava o settings com ordem estável; `--phase` liga skills por `skillOverrides` (`on`/`off`), que o Claude Code honra. `disabledSkills` não existe. Jev sem chave (exit 2): segui sem worker.

## Passos
1. Testes que falham: chave antiga é erro, release não vaza as seções novas, `sync --check` e o `check` mostram o mesmo diff, allow ≤ 15, denies iguais, hooks iguais, `--phase` não apaga skill, juiz e fechar usam `gates.full`, o Stop usa `gates.fast`.
2. Implementar o mínimo para os testes passarem.
3. `hdev check` verde.
4. `hdev fechar --plan work/v2-pr3-manifest-sync/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
5. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_sync.py` — manifesto, sync, drift, tetos, allow/deny/hooks (escrito antes do código)
- `tests/test_hooks.py::GateTests` — Stop lê `gates.fast`; chave antiga não roda
- `tests/test_judge.py` — juiz roda `gates.full`
- `tests/test_fechar.py::ReleaseBase` — release não vaza `base_branch`, `hooks`, `skills`, `caps`, `gates`
- `tests/test_init.py` — app nasce com `gates.fast`/`gates.full`

## Fora de escopo
- Reduzir hooks de 7 para 5 (ADR 0012 é outra PR).
- Subir teto, mudar a CLI de área (salvo alias), apagar skill, push, merge, tag.
- Rodar o juiz grok ou o fallback Codex.
