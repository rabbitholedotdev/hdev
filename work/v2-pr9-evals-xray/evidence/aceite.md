# Evidência — aceite

Comandos no HEAD `134587d2e170a2730794819b637754b67d0351b5`. Este commit só preenche o texto. O ritual do xray inclui `git log -5`, então o total pode andar alguns tokens aqui; continua abaixo de 15000. O juiz grok e o Codex não rodaram. Nenhum claude real foi chamado.

## bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1

exit=0. O JSON é `.hdev/runs/eval-20261120T001028707467Z.json` (gitignored). `tokens` é null: a tarefa não tem prompt e o runner `auto` não chama agente. `plain` mede 293 e `base` mede 1635: o plain tirou o andaime no clone.

```
hdev eval: smoke-init-check plain,base × 1
  plain#1: pass tokens=null 0.094s xray=293
  base#1: pass tokens=null 0.090s xray=1635
  registro: .hdev/runs/eval-20261120T001028707467Z.json
```

```json
{
  "kind": "eval",
  "version": 1,
  "case": "smoke-init-check",
  "repo": ".",
  "base_sha": "8ec80b39eaa06655f1dddc1754803008dcfde50f",
  "runner": "auto",
  "arms": ["plain", "base"],
  "runs": 1,
  "xray_method": "estimativa: 1 token por 4 bytes UTF-8, arredondando para cima",
  "results": [
    {
      "arm": "plain",
      "run": 1,
      "pass": true,
      "tokens": null,
      "seconds": 0.094,
      "exit_codes": [0],
      "agent_exit": null,
      "xray": 293
    },
    {
      "arm": "base",
      "run": 1,
      "pass": true,
      "tokens": null,
      "seconds": 0.09,
      "exit_codes": [0],
      "agent_exit": null,
      "xray": 1635
    }
  ]
}
```

## o mesmo com --runner fake

exit=0. Tokens 11/7/3 saem do JSON `usage` do processo falso, não da estimativa (293 e 1635).

```
hdev eval: smoke-init-check plain,base × 1
  plain#1: pass tokens=in=11 out=7 cache=3 0.101s xray=293
  base#1: pass tokens=in=11 out=7 cache=3 0.098s xray=1635
  registro: .hdev/runs/eval-20261120T001028985161Z.json
```

```json
{
  "results": [
    {
      "arm": "plain",
      "pass": true,
      "tokens": {"input": 11, "output": 7, "cache": 3},
      "seconds": 0.101,
      "agent_exit": 0,
      "xray": 293
    },
    {
      "arm": "base",
      "pass": true,
      "tokens": {"input": 11, "output": 7, "cache": 3},
      "seconds": 0.098,
      "agent_exit": 0,
      "xray": 1635
    }
  ]
}
```

## bin/hdev xray --max 15000

exit=0. Total 1655. Maiores fontes: AGENTS.md 645, executor.md 340, stop-list.md 137, ritual 136, safety.md 94.

```
fonte                                        estimativa
CLAUDE.md                                    3
AGENTS.md                                    645
skill:handoff                                29
skill:hdev                                   33
skill:planejar                               31
skill:revisar-diff                           29
skill:revisar-spec                           32
agent:haiku-explorar                         58
agent:sonnet-implementar                     64
ritual                                       136
prompt:harness/prompts/executor.md           340
prompt:harness/prompts/_shared/stop-list.md  137
prompt:harness/prompts/_shared/safety.md     94
prompt:harness/prompts/_shared/style.md      24
total                                        1655
estimativa: 1 token por 4 bytes UTF-8, arredondando para cima
```

## bin/hdev xray --max 100

exit=1. A tabela é a mesma. A última linha: `hdev xray: estimativa 1655 passa de 100`.

## python3 -m unittest tests.test_eval tests.test_xray tests.test_evals -q

stderr: `Ran 21 tests in 2.848s` e `OK`. exit=0.

Cobre plain (tira o andaime e não apaga `harness/hooks`), base (mantém), overlay `cand-demo`, árvore de trabalho intocada, teto de 12, tokens do JSON falso, CLI ausente com exit 3, xray acima do teto com exit 1 e `[FALHA] xray` no check, fechar que grava o caso no pass e não grava na falha nem no dry-run. O cenário mecânico dos dois casos (tag `v9.9.9`, app new) continua em `tests.test_evals`.

## python3 -m unittest discover -s tests -q

stderr: `Ran 443 tests in 114.240s` e `OK`. exit=0.

O `ResourceWarning` de `tests/test_naming.py:245` já estava no arquivo. As linhas `hdev: devolvido ao repo` são o teste do isolador, não falha.

## bin/hdev check

exit=0. A linha do xray: `[ok] xray: estimativa 1655/15000`.

```
[ok] agents: 40/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json bate com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1935/2000 caracteres
[ok] xray: estimativa 1655/15000
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 138 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto
```

exit=0.

## bin/hdev fechar --plan work/v2-pr9-evals-xray/plan.md --dry-run

exit=0. Imprime `commit do marco pulado`. Não rodou a suíte e não gravou `evals/tasks/`. A saída inteira está em `work/v2-pr9-evals-xray/evidence/fechar-dry-run.md`.

## Correção do exit — HEAD 61e3dd627387952d06af07f4e777d7568aaab422

O fechar lia o comando e gravava `expect_exit: 0` sempre. `bin/hdev xray --max 100` saía 1 no plano e 0 no caso. `hdev check` e `bin/hdev check` entravam os dois. Agora o exit sai da mesma linha (`sai 1`, `exit 1`, `sai ≠ 0`, `= 0`). Sem frase segura, ou se duas frases discordam, o caso fica `draft` e o exit não vira 0. `hdev ...` vira `bin/hdev ...` e a repetição se junta.

O caso abaixo foi gravado numa pasta temporária (`record_case` no mesmo caminho do fechar). Esta árvore não tem `.hdev/state/bases.json`, então `base_sha` fica null. O dry-run não escreve o arquivo. `git status` depois ficou limpo.

```json
{
  "id": "v2-pr9-evals-xray",
  "repo": ".",
  "base_sha": null,
  "prompt": null,
  "spec": null,
  "acceptance": [
    {"cmd": "bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1", "expect_exit": 0},
    {"cmd": "bin/hdev xray --max 15000", "expect_exit": 0},
    {"cmd": "bin/hdev xray --max 100", "expect_exit": 1},
    {"cmd": "python3 -m unittest tests.test_eval tests.test_xray tests.test_evals -q", "expect_exit": 0},
    {"cmd": "python3 -m unittest discover -s tests -q", "expect_exit": 0},
    {"cmd": "bin/hdev check", "expect_exit": 0},
    {"cmd": "bin/hdev sync --check", "expect_exit": 0},
    {"cmd": "bin/hdev fechar --plan work/v2-pr9-evals-xray/plan.md --dry-run", "expect_exit": 0}
  ],
  "caps": {"runs": 12},
  "draft": false
}
```

`bin/hdev xray --max 100` está com `expect_exit` 1. `hdev check` não aparece ao lado de `bin/hdev check`.

### python3 -m unittest tests.test_eval tests.test_xray tests.test_evals -q

stderr: `Ran 27 tests in 2.997s` e `OK`. exit=0.

### python3 -m unittest discover -s tests -q

stderr: `Ran 449 tests in 115.330s` e `OK`. exit=0.

O `ResourceWarning` de `tests/test_naming.py:245` já estava no arquivo. As linhas `hdev: devolvido ao repo` são o teste do isolador.

### bin/hdev check

exit=0. A linha do xray neste HEAD: `[ok] xray: estimativa 1650/15000`.

```
[ok] agents: 40/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json bate com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1935/2000 caracteres
[ok] xray: estimativa 1650/15000
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 141 segmentos novos, 0 não-ASCII, 0 avisos
```

### bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto
```

exit=0.
