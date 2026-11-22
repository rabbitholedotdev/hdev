# Fechar dry-run — v2-eval-claude-arm

HEAD `0a1f0bc`.

```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev fechar --plan work/v2-eval-claude-arm/plan.md --dry-run
hdev fechar: commit do marco pulado (branch vm/v2-eval-claude-arm não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-<stamp>.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_jev.py tests/test_prompts.py tests/test_smoke.py tests/test_triage.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_improve.py tests/test_judge.py tests/test_release_ship.py tests/test_spec.py tests/test_wrappers.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_init.py tests/test_library.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_isolar.py tests/test_naming.py tests/test_skills.py tests/test_sync.py
cache: miss
  reflita: hdev reflect --unit v2-eval-claude-arm
exit=0
```
