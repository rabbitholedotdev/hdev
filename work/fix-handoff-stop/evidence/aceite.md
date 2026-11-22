# Aceite — fix-handoff-stop

HEAD do código: `8152ad967ce8130cbce0c3696fb7295dfdb85566` (branch `vm/fix-handoff-stop`, base `c951dd6`). Rodado no host, 2026-11-20 04:50 -03.

## 1. Testes do handoff

`python3 -m unittest tests.test_handoff -q` → exit 0

```
Ran 16 tests in 0.674s

OK
```

## 1b. Os testes novos falham sem a mudança em hdev/handoff.py

`git show c951dd6:hdev/handoff.py > /tmp/hfix-old.py && cp hdev/handoff.py /tmp/hfix-new.py && cp /tmp/hfix-old.py hdev/handoff.py && python3 -m unittest tests.test_handoff -q; c=$?; cp /tmp/hfix-new.py hdev/handoff.py; rm -f /tmp/hfix-old.py /tmp/hfix-new.py; git diff --quiet HEAD -- hdev/handoff.py && echo 'hdev/handoff.py restaurado'; exit $c` → exit 1

```
FAIL: test_stop_com_unidade_fechada_nao_bloqueia
FAIL: test_stop_hook_active_nao_bloqueia_de_novo
Ran 16 tests in 0.430s
FAILED (failures=2)
hdev/handoff.py restaurado
```

## 2-3. stop_hook_active e unidade fechada (casos do teste, um a um)

`python3 -m unittest -v tests.test_handoff.Hook.test_stop_hook_active_nao_bloqueia_de_novo tests.test_handoff.Hook.test_stop_com_unidade_fechada_nao_bloqueia` → exit 0

```
test_stop_hook_active_nao_bloqueia_de_novo (tests.test_handoff.Hook.test_stop_hook_active_nao_bloqueia_de_novo) ... ok
test_stop_com_unidade_fechada_nao_bloqueia (tests.test_handoff.Hook.test_stop_com_unidade_fechada_nao_bloqueia) ... ok
Ran 2 tests in 0.013s
OK
```

## 4. Testes herméticos com HDEV_HANDOFF_* no ambiente

`HDEV_HANDOFF_THRESHOLD=0.95 HDEV_HANDOFF_WINDOW=1000000 python3 -m unittest tests.test_handoff tests.test_isolar -q` → exit 0

```
Ran 32 tests in 2.202s

OK
```

## 5. Suíte inteira

`python3 -m unittest discover -s tests -q` → exit 0

```
Ran 542 tests in 116.019s

OK
```

## 6. hdev check

`bin/hdev check` → exit 0

```
[ok] agents: 42/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1194/2000 caracteres
[ok] xray: estimativa 1910/15000
[ok] graph: só o explorer; query, path, explain
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] overlays: nenhuma
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base c951dd6 (bases.json fix-handoff-stop), mode fail, 5 segmentos novos, 0 não-ASCII, 0 avisos
```

## 7. hdev sync --check

`bin/hdev sync --check` → exit 0

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

## 8. hdev fechar --dry-run

`bin/hdev fechar --plan work/fix-handoff-stop/plan.md --dry-run` → exit 0

```
hdev fechar: commit do marco pulado (branch vm/fix-handoff-stop não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261120T075216446937Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_jev.py tests/test_prompts.py tests/test_smoke.py tests/test_triage.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_improve.py tests/test_judge.py tests/test_release_ship.py tests/test_spec.py tests/test_wrappers.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_init.py tests/test_library.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_isolar.py tests/test_naming.py tests/test_skills.py tests/test_sync.py
cache: miss
  reflita: hdev reflect --unit fix-handoff-stop
```

