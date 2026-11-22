# Aceite — fix-untracked-cases

HEAD das corridas: `28e908358b3aab3b6bcfcafea86a8f9051169cee` (base a9658ac), worktree `$HOME/hdev-wt/fix-untracked-cases` no host, 20/11.

## 1. Testes novos
`python3 -m unittest tests.test_evals tests.test_hooks -q` → exit 0.
```
Ran 60 tests in 8.197s
OK
```
Sem a mudança (testes novos já escritos, antes de `tracked_tasks` e do filtro em `changed_paths`), `python3 -m unittest tests.test_evals tests.test_hooks.ProgressGuard` → exit 1:
```
ERROR: test_only_committed_cases (tests.test_evals.Evals.test_only_committed_cases)
NameError: name 'tracked_tasks' is not defined
FAIL: test_untracked_fechar_case_does_not_count (tests.test_hooks.ProgressGuard.test_untracked_fechar_case_does_not_count)
AssertionError: 2 != 0
Ran 14 tests in 1.600s
FAILED (failures=1, errors=1)
```
Os dois arquivos de teste novos num clone em a9658ac (sem o filtro em `stop_gate.py`): `python3 -m unittest tests.test_evals tests.test_hooks -q` → exit 1, `FAIL: test_untracked_fechar_case_does_not_count`, `Ran 60 tests`, `FAILED (failures=1)`.

## 2. Caso não rastreado
Cópia do caso que o fechar gravou no checkout principal (`evals/tasks/fix-handoff-stop/task.json`) em `evals/tasks/zz-untracked/task.json`, fora do git (`git status --porcelain --untracked-files=all` → `?? evals/tasks/zz-untracked/task.json`).
- Neste HEAD: `python3 -m unittest tests.test_evals -q` → exit 0, `Ran 5 tests`, `OK`.
- Num clone em a9658ac, mesmo arquivo: `python3 -m unittest tests.test_evals -q` → exit 1:
```
FAIL: test_casos (tests.test_evals.Evals.test_casos) (case='fix-handoff-stop')
FAIL: test_formato (tests.test_evals.Evals.test_formato)
Ran 4 tests in 1.562s
FAILED (failures=2)
```
O arquivo e o clone foram apagados depois.

## 3. progress_guard
`test_untracked_fechar_case_does_not_count` (item 1, exit 0): com só `?? evals/tasks/u/task.json` o hook sai 0; depois do `git add -A` sai 2 e a mensagem cita `evals/tasks/u/task.json`.

## 4. Suíte
`time python3 -m unittest discover -s tests -q` → exit 0.
```
Ran 557 tests in 79.492s
OK
real	1m19.682s
```

## 5. check
`bin/hdev check` → exit 0 (todas as linhas `[ok]`; hooks 5 registros, 3 arquivos; names base a9658ac).

## 6. sync
`bin/hdev sync --check` → exit 0: `hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também`.

## 7. fechar --dry-run
`bin/hdev fechar --plan work/fix-untracked-cases/plan.md --dry-run` → exit 0: `hdev fechar: commit do marco pulado (branch vm/fix-untracked-cases não é a base f2-11-v0.6.0).`, 4 shards, `cache: miss`.

## Depois do merge de f2-11 a61847a (#21)
HEAD `dacef2089b71f021e1c9d407e039d01e6066cb64` (merge; conflito só em `docs/decisions.md`, as duas linhas ficaram, f2-11 primeiro). Base da unidade remarcada: `hdev base --plan work/fix-untracked-cases/plan.md --marcar a61847a… --force`. O worktree tem `?? evals/tasks/fix-untracked-cases/task.json`, deixado pelo `hdev fechar` da unidade (pass, 557 testes, tree fedf798).
- `python3 -m unittest tests.test_evals tests.test_hooks -q` → exit 0, `Ran 60 tests`, `OK`.
- `python3 -m unittest tests.test_evals -q`, com o caso não rastreado no worktree → exit 0, `Ran 5 tests`, `OK`.
- `time python3 -m unittest discover -s tests -q`, no worktree e com o mesmo caso → exit 0, `Ran 569 tests in 86.847s`, `OK`, `real 1m27.044s`.
- `bin/hdev check` → exit 0, 15 linhas `[ok]`.
- `bin/hdev sync --check` → exit 0.
- `bin/hdev fechar --plan work/fix-untracked-cases/plan.md --dry-run` → exit 0, marco pulado (branch fora da base), 4 shards, `cache: miss`.
