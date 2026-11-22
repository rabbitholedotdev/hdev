# Evidência — aceite

A suíte `discover` e o `fechar` rodaram no HEAD `cd48bb58d2870efbe169b6bccc42dd95b892638c` (ainda sem esta página). Check, sync, help, `wc` e `tests.test_judge` rodaram de novo com a evidência no git (`3502bdf`): a linha `names` passou de 16 para 19 segmentos; o resto igual. O check abaixo é o da repetição.

## Cache com --run-tests

O log de testes entra no pacote sem tempo de parede e sem pasta temporária. `Ran 413 tests in 52.382s` vira `Ran 413 tests in TIME`. `/tmp/hdev-judge-<id>`, `/private/tmp/...` e `/var/folders/.../T/...` viram `/tmp/TMP`. A chave segue o hash desse pacote, mais base, head, plano, papéis, versão da rubrica e o modo dos testes. OK/FAILED, a contagem e o nome do teste que falhou ficam. Uma falha muda a chave. Duas corridas iguais com `--run-tests` acertam o cache.

Nesta correção, árvore ainda sem o commit da página:

- `python3 -m unittest tests.test_judge -q`: 67 testes em 12.458s, OK. ELAPSED 12.53. exit=0.
- `wc -l hdev/gates/judge/*.py | sort -n | tail -2 | head -1`: `289 hdev/gates/judge/package.py` (< 400). exit=0.
- `python3 -m unittest discover -s tests -q`: 414 testes em 106.689s, OK. ELAPSED 106.80. exit=0.
- `bin/hdev check`: exit=0. names 19 segmentos, 0 avisos.
- `bin/hdev sync --check`: exit=0.

O juiz grok e o Codex não rodaram.

## python3 -m unittest tests.test_judge -q

No `cd48bb5`: stderr `Ran 66 tests in 14.064s` e `OK`. ELAPSED 14.20. exit=0.
Repetido no `3502bdf`: stderr `Ran 66 tests in 13.360s` e `OK`. ELAPSED 13.43. exit=0.

Cobre corte do diff, leitura da evidência commitada, acerto de cache (o falso roda uma vez), erro de cache em cada parte da chave, `--no-cache`, erro e unsure sem cache.

## wc -l hdev/gates/judge/*.py | sort -n | tail -2 | head -1

```
  284 hdev/gates/judge/run.py
```

284 < 400. exit=0.

## python3 -m unittest discover -s tests -q

stderr: `Ran 413 tests in 106.848s` e `OK`. ELAPSED 106.96. exit=0.

O `ResourceWarning` de `tests/test_naming.py:245` já estava no arquivo (não é desta PR).

## bin/hdev check

exit=0

```
[ok] agents: 39/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json bate com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1953/2000 caracteres
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 9cf7672 (bases.json v2-pr7-judge-pacote), mode fail, 19 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto
```

exit=0

## bin/hdev judge --help

Antes, no `9cf7672`. exit=0. Flags: `--plan`, `--root`, `--base`, `--head`, `--tests-log`, `--run-tests`, `--dry-run`, `--rejulgar`, `--json`.

```
usage: hdev judge [-h] --plan PLAN [--root ROOT] [--base BASE] [--head HEAD]
                  [--tests-log TESTS_LOG | --run-tests] [--dry-run]
                  [--rejulgar] [--json]

options:
  -h, --help            show this help message and exit
  --plan PLAN           work/<id>/plan.md (alias: docs/plan-<tarefa>.md)
  --root ROOT
  --base BASE           força a base do diff (padrão: a da unidade; `hdev base
                        --plan P` mostra qual)
  --head HEAD           com --base: julga só o intervalo base..head (sem não
                        rastreados)
  --tests-log TESTS_LOG
                        arquivo com a saída dos testes
  --run-tests           roda gates.full da config
  --dry-run             só mostra o pacote, não chama o juiz
  --rejulgar            chama o juiz mesmo com o pacote idêntico ao do último
                        unsure (ADR 0010)
  --json
```

Depois, neste HEAD. exit=0. As mesmas, mais `--no-cache`.

```
usage: hdev judge [-h] --plan PLAN [--root ROOT] [--base BASE] [--head HEAD]
                  [--tests-log TESTS_LOG | --run-tests] [--dry-run]
                  [--rejulgar] [--no-cache] [--json]

options:
  -h, --help            show this help message and exit
  --plan PLAN           work/<id>/plan.md (alias: docs/plan-<tarefa>.md)
  --root ROOT
  --base BASE           força a base do diff (padrão: a da unidade; `hdev base
                        --plan P` mostra qual)
  --head HEAD           com --base: julga só o intervalo base..head (sem não
                        rastreados)
  --tests-log TESTS_LOG
                        arquivo com a saída dos testes
  --run-tests           roda gates.full da config
  --dry-run             só mostra o pacote, não chama o juiz
  --rejulgar            chama o juiz mesmo com o pacote idêntico ao do último
                        unsure (ADR 0010)
  --no-cache            ignora o veredito guardado e chama o provedor
  --json
```

## Fora desta página

- `hdev fechar --dry-run`: `work/v2-pr7-judge-pacote/evidence/fechar-dry-run.md`
