# Evidência — fechar --dry-run

HEAD `bc2d07b`. Branch `cursor/v2-pr11-library-9348`. O marco não nasce fora da base. O índice da biblioteca não mudou.

## bin/hdev fechar --plan work/v2-pr11-library/plan.md --dry-run

exit=0

```
hdev fechar: commit do marco pulado (branch cursor/v2-pr11-library-9348 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261120T043910785626Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_judge.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_init.py tests/test_library.py tests/test_skills.py tests/test_sync.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_isolar.py tests/test_naming.py tests/test_smoke.py tests/test_triage.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_jev.py tests/test_prompts.py tests/test_spec.py tests/test_wrappers.py
cache: miss
  reflita: hdev reflect --unit v2-pr11-library
```
