# Evidência — fechar --dry-run

HEAD `2357ee223c6d266906a1018b3a1618a4835d39ca`.

```
$ bin/hdev fechar --plan work/v2-parada-fechada/plan.md --dry-run
hdev fechar: commit do marco pulado (branch cursor/v2-parada-fechada-0ba7 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261120T010818007869Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_init.py tests/test_naming.py tests/test_smoke.py tests/test_triage.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_isolar.py tests/test_prompts.py tests/test_spec.py tests/test_wrappers.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_handoff.py tests/test_jev.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_hooks.py tests/test_judge.py tests/test_skills.py tests/test_sync.py
cache: miss
```

exit=0

Não gravou `evals/tasks/v2-parada-fechada/task.json`. O marco não nasceu: a branch não é `f2-11-v0.6.0`.
