# Evidência — aceite v0.7.1

Suíte inteira depois do merge de `origin/f2-11-v0.6.0` (`c0d51fd`, biblioteca PR11). Sem `hdev base --marcar` neste repo. Sem tag `v0.7.1` e sem `hdev release` no núcleo real. `releases/` do núcleo não foi tocado.

## Suíte focada

```
$ python3 -m unittest tests.test_stop tests.test_hooks tests.test_handoff tests.test_release_ship tests.test_prompts -q
Ran 94 tests in 8.356s
OK
```

exit=0

Cobre: Stop da sessão que saiu sai 0 e o seguinte sai 2; Stop da sessão nova com unidade aberta sai 2; `SessionStart` da sessão nova apaga `stop_session`; `allow_stop: true` sem id sai 2; PAREI libera; `standing_ok` publicar grava `READY-TO-PUBLISH` e não para; o comando dos hooks `.codex/hooks.json` e `.grok/hooks/stop.json` usa a mesma sessão; `release.install`, `hdev pin` e `hdev release` gravam `PROMPT-ORCHESTRATOR.md` com `<!-- compat:`; pasta já instalada não ganha o arquivo de volta; `hdev sync` grava os dois hooks e `sync --check` sai 1 se o do Codex diverge; `hdev check` falha se o AGENTS.md liga um `.md` ausente na release; `hdev base --plan docs/plan-inf-006-banco.md --marcar` abre `INF-006` e `hdev fechar` fecha.

## Suíte inteira

```
$ python3 -m unittest discover -s tests -q
Ran 514 tests in 124.068s
OK
```

exit=0. Inclui `tests.test_library` que entrou com o PR11.

## bin/hdev check

exit=0

```
[ok] agents: 41/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1145/2000 caracteres
[ok] xray: estimativa 1872/15000
[ok] graph: só o explorer; query, path, explain
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 223 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

exit=0

## Causa do prompt ausente na v0.7.0

A tag `v0.6.0` (`47c348a`) não tem `write_shipped` em `hdev/release.py`. A tag `v0.7.0` tirou `PROMPT-ORCHESTRATOR.md` da raiz (fica `harness/prompts/orchestrator.md`) e o `install` dessa tag chama `write_shipped`. Quem rodou o pin foi o `hdev` já pinado, o da v0.6.0: `git archive` sem montar o arquivo. O `install` seguinte vê a pasta e devolve, sem reescrever. Instalação nova, com este código, grava o arquivo. A pasta `v0.7.0` que já está no disco fica como está.

## Versão

`hdev/__init__.py` tem `VERSION = "0.7.1"`. `CHANGELOG.md` tem `## [0.7.1]`. A tag `v0.7.1` não existe neste repo.

## hdev fechar --dry-run

HEAD `8312f9e` (depois do merge do PR11), branch `cursor/v071-parada-fix-c24d`. Árvore limpa. O marco não nasce: a branch não é `f2-11-v0.6.0`.

```
$ python3 bin/hdev fechar --plan work/v071-parada-fix/plan.md --dry-run
hdev fechar: commit do marco pulado (branch cursor/v071-parada-fix-c24d não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261120T050035419619Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_judge.py tests/test_release_ship.py tests/test_spec.py tests/test_wrappers.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_init.py tests/test_library.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_isolar.py tests/test_naming.py tests/test_skills.py tests/test_sync.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_jev.py tests/test_prompts.py tests/test_smoke.py tests/test_triage.py
cache: miss
  reflita: hdev reflect --unit v071-parada-fix
```

exit=0. `hdev reflect` não foi executado.

