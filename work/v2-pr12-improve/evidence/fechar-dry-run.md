# fechar --dry-run — v2-pr12-improve

HEAD: `25e156f941c3655a3f5cba491ad5348dcb98899a`

`bin/hdev fechar --plan work/v2-pr12-improve/plan.md --dry-run` — exit 0

```
hdev fechar: commit do marco pulado (branch vm/v2-pr12-improve não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-<stamp>.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_jev.py tests/test_prompts.py tests/test_spec.py tests/test_wrappers.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_improve.py tests/test_judge.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_init.py tests/test_library.py tests/test_skills.py tests/test_sync.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_isolar.py tests/test_naming.py tests/test_smoke.py tests/test_triage.py
cache: miss
  reflita: hdev reflect --unit v2-pr12-improve
```

Marco pulado: a branch não é a base. A suíte não roda no dry-run.
