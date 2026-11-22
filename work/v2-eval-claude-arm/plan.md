# Plano — v2-eval-claude-arm

Spec: sem spec (pedido fechado do dono: braço real do eval com Sonnet, aprovado depois da PR12)

## Objetivo
`hdev eval run --runner claude` e `hdev improve probe --runner claude` viram um braço real e medido, com o Sonnet (`claude-sonnet-5-5`) de executor, e rodam de verdade, com orçamento pequeno (≤ 9 corridas reais), para dar os primeiros números reais.

## Critério de pronto
- `python3 -m unittest tests.test_eval tests.test_improve -q` sai 0.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1 --runner claude --dry-run` sai 0, mostra `modelo: claude-sonnet-5-5` e não roda nada.
- `bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1 --runner claude` sai 0, grava `.hdev/runs/eval-*.json`, e cada linha mostra o modelo `claude-sonnet-5-5`, tokens reais (não o 11/7/3 do fake) e segundos (2 corridas reais).
- `bin/hdev improve probe --case smoke-init-check --cand demo --runs 2 --runner claude` sai 0 e grava o relatório (6 corridas reais; total 8 ≤ 9). `git status --porcelain` e `git diff --stat` antes e depois: arquivos do harness iguais; depois, `git restore library/`.
- `bin/hdev check` sai 0 (skills 5/5, hooks 5 registros e 3 arquivos, xray abaixo do teto).
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-eval-claude-arm/plan.md --dry-run` sai 0.
- [juiz] cada item aponta para o comando e a saída em `work/v2-eval-claude-arm/evidence/aceite.md`, com os números reais por braço (pass, tokens, segundos, modelo).

## Abordagem
Stdlib, só `hdev/eval.py` e `hdev/improve/probe.py`; sem camada nova de runner.

- Modelo: constante `EVAL_MODEL = "claude-sonnet-5-5"`, trocável por `eval.model` no manifesto. `agent_argv` põe `--model` se o `eval.agent_cmd` não nomeia um. `roles.executor` fica como está.
- Segurança do agente aninhado (só quando o executável se chama `claude`; cada flag só entra se o comando não a traz): `--permission-mode acceptEdits`, `--allowedTools` estreito (`Bash(python3:*)`, `Bash(bin/hdev:*)`, `Bash(git status:*)`, `Bash(git diff:*)`, `Bash(git log:*)`), sempre `--disallowedTools` com push do git e root proibidos. O prompt ganha um preâmbulo fixo: clone descartável, nada fora da pasta, sem push, sem root. Ambiente do agente sem `CLAUDE_PROJECT_DIR` e `CLAUDECODE` (os hooks do clone não podem apontar para esta árvore).
- Timeout: `eval.timeout_sec`, padrão 600 s. Timeout é corrida que falha (`agente timeout`), nunca pass.
- Modelo medido: `parse_model` lê as chaves de `modelUsage` do JSON e fica com a de mais tokens de saída. A linha grava `model`; o registro grava o pedido (`model`). Linha cujo modelo não começa com o pedido ganha `model_ok: false` e `[modelo ≠ pedido]` na saída e no relatório.
- Runner `claude` com caso sem prompt recusa (sai 2) antes de gastar. O `smoke-init-check` ganha um prompt curto (rodar `bin/hdev check` e responder numa linha, sem editar).
- Probe: aceita `--runner claude`; com modelo real o mínimo cai para n ≥ 2 (orçamento), o fake segue n ≥ 3. O dry-run mostra o modelo; o relatório ganha a coluna modelo.
- Teto `RUN_CAP = 12` fica.

## Passos
1. Testes que falham em `tests/test_eval.py` e `tests/test_improve.py`.
2. `hdev/eval.py` (argv, modelo, timeout, ambiente, prompt) e `hdev/improve/probe.py` (runner e mínimo); CLI.
3. Prompt no `smoke-init-check`.
4. Suíte, `hdev check`, `hdev sync --check`.
5. Dry-run, corrida real (2), probe real (6). Evidência; `git restore library/`.
6. Docs: uma linha em `docs/decisions.md`, `docs/progress.md`, CHANGELOG, `evals/arms/README.md`.
7. `hdev fechar --plan work/v2-eval-claude-arm/plan.md`.

## Testes
- `tests/test_eval.py` — argv com modelo, tools proibidas e permissão; `eval.model` e `--model` do comando; timeout configurável e falho; `parse_model`; linha marcada quando o modelo não bate; claude sem prompt recusa; dry-run mostra o modelo. Tudo com comando falso chamado `claude`, sem modelo.
- `tests/test_improve.py` — probe com runner claude falso e n = 2; dry-run com modelo.
- `python3 -m unittest discover -s tests -q` — o resto não quebra.

## Fora de escopo
- Compose e revert (outra PR). `hdev/handoff.py` (outra PR).
- Juiz, Codex, Grok, Jev: não rodam nesta PR.
- Skill, hook ou dependência nova. `VERSION` parado. `releases/v*/` congelado.

## Riscos
- Custo: 8 corridas reais do Sonnet; teto de 9 nesta PR.
- O `modelUsage` pode trazer um modelo auxiliar (haiku); por isso vale o de mais saída.
- Hooks do braço `base` no `base_sha` rodam dentro do agente aninhado; o timeout de 600 s segura travas.
- `python3:*` liberado deixa o agente rodar código; o limite é o prompt e o clone descartável.
