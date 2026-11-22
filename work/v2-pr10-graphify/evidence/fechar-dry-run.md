# Evidência — fechar --dry-run

HEAD `e9127d655d4df97b90085459e5ac8ebcdd1337e0`. Branch `cursor/v2-pr10-graphify-9174`. O marco não nasce fora da base.

## bin/hdev fechar --plan work/v2-pr10-graphify/plan.md --dry-run

exit=0

```
hdev fechar: commit do marco pulado (branch cursor/v2-pr10-graphify-9174 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261120T010503868237Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_judge.py tests/test_skills.py tests/test_sync.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_init.py tests/test_naming.py tests/test_smoke.py tests/test_triage.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_isolar.py tests/test_prompts.py tests/test_spec.py tests/test_wrappers.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_jev.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
cache: miss
```
