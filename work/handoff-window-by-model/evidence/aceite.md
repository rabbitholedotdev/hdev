# Aceite — handoff-window-by-model

HEAD do código: `a849e33d7921c564d31e9838c4f88d31d8172339` (branch `vm/handoff-window-by-model`, base `a9658ac`). Rodado no host, 2026-11-20 05:57 -03. Cada comando roda em `bash -o pipefail -c`: o exit é o do comando, não o do `grep`.

## 1. Testes do handoff

`env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -m unittest tests.test_handoff -q 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^OK|^FAILED"` → exit 0

```
Ran 18 tests in 0.517s

OK
```

## 1b. Os testes novos falham sem a mudança em hdev/handoff.py

`git show a9658ac:hdev/handoff.py > /tmp/hw-old.py && cp hdev/handoff.py /tmp/hw-new.py && cp /tmp/hw-old.py hdev/handoff.py && env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -m unittest tests.test_handoff -q 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^FAILED|^KeyError"; c=${PIPESTATUS[0]}; cp /tmp/hw-new.py hdev/handoff.py; rm -f /tmp/hw-old.py /tmp/hw-new.py; git diff --quiet HEAD -- hdev/handoff.py && echo 'hdev/handoff.py restaurado'; exit $c` → exit 1

```
ERROR: test_env_janela_ganha_do_mapa (tests.test_handoff.Hook.test_env_janela_ganha_do_mapa)
KeyError: 'window_by_model'
FAIL: test_janela_por_modelo (tests.test_handoff.Hook.test_janela_por_modelo)
Ran 18 tests in 0.518s

FAILED (failures=1, errors=1)
hdev/handoff.py restaurado
```

## 2. Janela por modelo e env (casos do teste, um a um)

`env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -m unittest -v tests.test_handoff.Hook.test_janela_por_modelo tests.test_handoff.Hook.test_env_janela_ganha_do_mapa 2>&1 | grep -E " ok$|FAIL|ERROR|^Ran|^OK" | sed "s/ (.*) / /"` → exit 0

```
test_janela_por_modelo ... ok
test_env_janela_ganha_do_mapa ... ok
Ran 2 tests in 0.008s

OK
```

## 3. Config do núcleo

`env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -c 'from hdev import handoff as h; c = h.settings("."); print(c["window_tokens"], c["window_by_model"], h.window_for(c, "claude-opus-5-5"), h.window_for(c, "claude-outro"))'` → exit 0

```
200000 {'claude-opus-5-5': 1000000} 1000000 200000
```

## 4. Transcript real da corrida do PR13 (claude-opus-5-5)

`T=$HOME/.claude/projects/<session>.jsonl; env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -c 'import sys; from hdev import handoff as h; t = sys.argv[1]; c = h.settings("."); u = h.last_assistant_usage(t); m = h.model_from_transcript(t); print("modelo", m, "tokens", h.usage_tokens(u), "razão nova", round(h.usage_ratio(u, h.window_for(c, m)), 3), "razão com 200000", round(h.usage_ratio(u, 200000), 3))' "$T"` → exit 0

```
modelo claude-opus-5-5 tokens 134558 razão nova 0.135 razão com 200000 0.673
```

## 5. Testes herméticos com HDEV_HANDOFF_* no ambiente

`HDEV_HANDOFF_THRESHOLD=0.95 HDEV_HANDOFF_WINDOW=1000000 python3 -m unittest tests.test_handoff tests.test_isolar -q 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^OK|^FAILED"` → exit 0

```
Ran 34 tests in 1.719s

OK
```

## 6. Suíte inteira

`env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -m unittest discover -s tests -q 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^OK|^FAILED"` → exit 0

```
Ran 557 tests in 125.093s

OK
```

## 6b. Suíte inteira com HDEV_HANDOFF_* no ambiente

`HDEV_HANDOFF_THRESHOLD=0.95 HDEV_HANDOFF_WINDOW=1000000 python3 -m unittest discover -s tests -q 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|^OK|^FAILED"` → exit 0

```
Ran 557 tests in 96.498s

OK
```

## 7. hdev check

`env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev check` → exit 0

```
[ok] agents: 42/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1206/2000 caracteres
[ok] xray: estimativa 1907/15000
[ok] graph: só o explorer; query, path, explain
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] overlays: nenhuma
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base a9658ac (bases.json handoff-window-by-model), mode fail, 4 segmentos novos, 0 não-ASCII, 0 avisos
```

## 8. hdev sync --check e o autocompact do settings gerado

`env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev sync --check && python3 -c 'import json; print("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", repr(json.load(open(".claude/settings.json"))["env"]["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"]))'` → exit 0

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
CLAUDE_AUTOCOMPACT_PCT_OVERRIDE '60'
```

## 9. fechar --dry-run

`env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev fechar --plan work/handoff-window-by-model/plan.md --dry-run` → exit 0

```
hdev fechar: commit do marco pulado (branch vm/handoff-window-by-model não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261120T090121687364Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_isolar.py tests/test_naming.py tests/test_skills.py tests/test_sync.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_improve.py tests/test_jev.py tests/test_prompts.py tests/test_smoke.py tests/test_triage.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_improve_compose.py tests/test_judge.py tests/test_release_ship.py tests/test_spec.py tests/test_wrappers.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_init.py tests/test_library.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
cache: miss
  reflita: hdev reflect --unit handoff-window-by-model
```
