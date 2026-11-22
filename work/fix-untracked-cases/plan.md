# Plano — fix-untracked-cases

Spec: sem spec (correção pedida pelo dono, 20/11: o caso que o `hdev fechar` deixa no worktree quebra a suíte e o Stop)

## Objetivo
Fora da branch base, o `hdev fechar` grava `evals/tasks/<id>/task.json` e deixa o arquivo no worktree, sem commit (PRD, "Evals e xray"). Dois leitores tropeçam nele. `tests/test_evals.py` lê toda pasta de `evals/tasks/` por glob: no checkout principal do VM (f458037), `python3 -m unittest discover -s tests -q` saiu 1, com `test_casos` ×7 e `test_formato`, um por caso não rastreado. O `progress_guard` do Stop conta o arquivo como mudança e bloqueia (corrida headless do PR13, 20/11: "1 arquivo(s) mudaram (evals/tasks/v2-pr13-compose/task.json) e docs/progress.md não foi atualizado"). A suíte do fechar passa porque roda num clone limpo, sem arquivo fora do git.

## Critério de pronto
- `python3 -m unittest tests.test_evals tests.test_hooks -q` sai 0. Os dois testes novos (`test_only_committed_cases`, `test_untracked_fechar_case_does_not_count`) falham sem a mudança.
- Com um caso não rastreado em `evals/tasks/<x>/task.json`, `python3 -m unittest tests.test_evals -q` sai 0. Na base a9658ac, o mesmo cenário sai 1.
- O `progress_guard` ignora só caso não rastreado em `evals/tasks/`. O mesmo caso depois do `git add` volta a contar.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/fix-untracked-cases/plan.md --dry-run` sai 0.
- [juiz] cada item aponta para um comando e a saída em `work/fix-untracked-cases/evidence/aceite.md`.

## Abordagem
`tests/test_evals.py` monta `TASKS` com `git ls-files` (só caso commitado ou no índice), como o clone limpo do fechar. Fora de um repo git, cai no glob de hoje. `harness/hooks/stop_gate.py` `changed_paths` pula a linha `??` em `evals/tasks/`. O `hdev fechar`, o `record_case` e o PRD não mudam: o caso segue no worktree para o `hdev eval run --case <id>`.

## Passos
1. Testes que falham em `tests/test_evals.py` e `tests/test_hooks.py`.
2. `TASKS` por `git ls-files` e o filtro em `changed_paths`.
3. Suíte, `hdev check` e `hdev sync --check` verdes.
4. Evidência e `hdev fechar --plan work/fix-untracked-cases/plan.md`.

## Testes
- `tests/test_evals.py`: repo temporário com um caso commitado e um fora do git; só o commitado entra.
- `tests/test_hooks.py` `ProgressGuard`: caso fora do git libera o Stop; o mesmo caso com `git add` bloqueia.

## Fora de escopo
- Na branch base o caso entra no marco (PRD). Commitado, ele entraria em `test_evals`: `test_formato` fixa os dois ids e `test_casos` roda o aceite do caso no núcleo de teste. Isso pede decisão do dono; nenhum marco gravou caso até hoje.
- Os casos não rastreados no checkout principal do VM ficam (saída normal do fechar).
- Releases instaladas (`releases/v*/`, `/opt/harness-dev/releases`): a correção chega aos apps na próxima release.

## Riscos
- Caso escrito à mão e ainda fora do índice não roda em `test_evals` nem pede `docs/progress.md` no Stop até o `git add`. É o que a suíte do fechar já cobre: só o commit.
