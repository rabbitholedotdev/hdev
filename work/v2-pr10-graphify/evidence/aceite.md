# Evidência — aceite

Comandos do grafo no HEAD `e9127d655d4df97b90085459e5ac8ebcdd1337e0`. A correção do cache do juiz e o merge da parada fechada (`131311c`, v0.7.0) estão em `13068081768b16d9cadb370adc3464d1fad371ae`. O detalhe da suíte repetida está em `work/v2-pr10-graphify/evidence/judge-cache.md`. O juiz grok e o Codex não rodaram. Nenhum claude real foi chamado.

`hdev/gates/stop.py` não existe. O arquivo da CLI é `hdev/stop.py` (o hook de parada é `harness/hooks/stop_gate.py`, que os testes não importam). Os comandos usam `hdev/stop.py`.

## bin/hdev impact hdev/stop.py

exit=0

```
hdev/stop.py
quem chama ou importa:
  harness/hooks/stop_gate.py  calls, imports_from
  hdev/cli.py  imports_from
  hdev/gates/judge/invoke.py  calls, imports_from
  hdev/gates/judge/run.py  calls, imports_from
  hdev/handoff.py  calls, imports_from
  hdev/jev.py  calls, imports_from
  hooks/_lib.py  calls, imports
  tests/test_judge.py  calls, imports_from
  tests/test_smoke.py  calls, imports_from
  tests/test_stop.py  calls, imports_from
o que chama ou importa:
  fora do repo: datetime, json, os, re, subprocess, sys, time
```

## scripts/affected-tests hdev/stop.py

exit=0. A stdout inclui `tests/test_stop.py`. Os outros entram porque importam, direto ou em até 8 saltos de import EXTRACTED, alguém que importa `hdev/stop.py`. `tests/test_stop.py` também importa o arquivo direto.

```
tests/test_channel.py
tests/test_cli_runtime.py
tests/test_handoff.py
tests/test_isolar.py
tests/test_jev.py
tests/test_judge.py
tests/test_smoke.py
tests/test_stop.py
```

## python3 -m unittest tests.test_graph -q

exit=0. 18 testes em 0.467s.

## python3 -m unittest discover -s tests -q

exit=0. 467 testes em 114.911s.

## bin/hdev check

exit=0. Hooks continuam 5 registros e 3 arquivos. A linha `graph` passa. O xray fica em 1692, abaixo de 15000.

```
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] xray: estimativa 1692/15000
[ok] graph: só o explorer; query, path, explain
```

## bin/hdev sync --check

exit=0

```
hdev sync: settings.json bate com o manifesto
```

## bin/hdev xray --max 15000

exit=0. Total 1692.

## bin/hdev fechar --plan work/v2-pr10-graphify/plan.md --dry-run

exit=0. O texto está em `work/v2-pr10-graphify/evidence/fechar-dry-run.md`.
