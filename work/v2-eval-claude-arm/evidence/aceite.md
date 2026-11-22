# Aceite — v2-eval-claude-arm

HEAD do código e da doc quando os comandos rodaram: `0a1f0bc` (código em `05d7b0c`; `0a1f0bc` só soma doc). Branch `vm/v2-eval-claude-arm`, base `c951dd6`.
Todo comando com o prefixo `env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW` (pedido do orquestrador: as variáveis da rodada headless quebram os testes do handoff por um motivo de outra PR).

Corridas reais do Sonnet nesta PR: **8** (2 no eval + 6 no probe), dentro do teto de 9. Nenhuma outra chamada de modelo (sem juiz, Codex, Grok, Jev).

| # | comando | exit | ok |
|---|---|---|---|
| 1 | `python3 -m unittest tests.test_eval tests.test_improve -q` | 0 | ok |
| 2 | `python3 -m unittest discover -s tests -q` | 0 | ok |
| 3 | `bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1 --runner claude --dry-run` | 0 | ok |
| 4 | `bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1 --runner claude` | 0 | ok |
| 5 | `bin/hdev improve probe --case smoke-init-check --cand demo --runs 2 --runner claude` | 0 | ok |
| 6 | `bin/hdev check` | 0 | ok |
| 7 | `bin/hdev sync --check` | 0 | ok |
| 8 | `bin/hdev fechar --plan work/v2-eval-claude-arm/plan.md --dry-run` | 0 | ok |

## 1. Testes do eval e do improve
```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -m unittest tests.test_eval tests.test_improve -q
Ran 49 tests in 29.646s
OK
```
Antes da implementação os testes novos falharam (7 falhas, 4 erros em `tests.test_eval`). Nenhum teste chama modelo: o claude é um script falso `fakebin/claude` que confere o preâmbulo e o ambiente e devolve `usage`/`modelUsage`.

## 2. Suíte completa
```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW python3 -m unittest discover -s tests -q
Ran 552 tests in 278.359s
OK
```

## 3. Dry-run com o modelo
```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1 --runner claude --dry-run
hdev eval: dry-run
  caso: smoke-init-check
  base: 8ec80b39eaa0
  braços: plain, base
  corridas: 1
  runner: claude
  modelo: claude-sonnet-5-5
  aceite: 1 passos
exit=0
```
Nada clonado, nada rodado.

## 4. Corrida real (2 corridas)
```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1 --runner claude
hdev eval: smoke-init-check plain,base × 1
  plain#1: pass tokens=in=6 out=300 cache=128738 14.426s xray=293 model=claude-sonnet-5-5
  base#1: pass tokens=in=8 out=320 cache=176625 13.839s xray=1635 model=claude-sonnet-5-5
  registro: .hdev/runs/eval-20261120T074837429037Z.json
exit=0
```
Registro: `"model": "claude-sonnet-5-5"`; as duas linhas com `model_ok: true`, `agent_exit: 0`. Tokens reais (não o 11/7/3 do fake).

## 5. Probe real (6 corridas)
`git status --porcelain` e `git diff --stat` antes: vazios.
```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev improve probe --case smoke-init-check --cand demo --runs 2 --runner claude
hdev improve: smoke-init-check, 3 braços × 2 corridas, nada adotado
  demo (domínio): perde [alerta diff > 50%]
  biblioteca: gravado lesson-0006
  registro: .hdev/runs/improve-20261120T075044081389Z.json
  relatório: .hdev/runs/improve-20261120T075044081389Z.md
exit=0
```
Relatório (trecho):
```
| braço | corridas | pass | tokens | segundos | xray | modelo |
| plain | 2 | 1.0 | 457.0 | 17.7355 | 293.0 | claude-sonnet-5-5 |
| base | 2 | 1.0 | 253.0 | 12.681 | 1635.0 | claude-sonnet-5-5 |
| cand-demo | 2 | 1.0 | 1126.0 | 27.7835 | 1635.0 | claude-sonnet-5-5 |
Modelo pedido: `claude-sonnet-5-5`.
- `demo` (domínio): **perde**, não adotado. Δ {"pass": 0.0, "seconds": 1.191, "tokens": 3.451, "xray": 0.0}.
```
`model_mismatch: 0`. Depois: `git status --porcelain` = `M library/index.jsonl` e `?? library/lessons/0006.md`; `git diff --stat` = `library/index.jsonl | 1 +`. Harness (`harness/`, `.claude/`, `hooks/`, `hdev/`, `AGENTS.md`, `CLAUDE.md`, `.hdev/config.json`) sem mudança. Limpeza: `git restore library/` e remoção de `library/lessons/0006.md` (criado pela corrida); `git status --porcelain` vazio.

## Números reais por braço e corrida (Sonnet)
| corrida | braço | pass | in | out | cache | segundos | modelo |
|---|---|---|---|---|---|---|---|
| eval | plain#1 | pass | 6 | 300 | 128738 | 14.426 | claude-sonnet-5-5 |
| eval | base#1 | pass | 8 | 320 | 176625 | 13.839 | claude-sonnet-5-5 |
| probe | plain#1 | pass | 8 | 479 | 174068 | 16.914 | claude-sonnet-5-5 |
| probe | plain#2 | pass | 8 | 419 | 173939 | 18.557 | claude-sonnet-5-5 |
| probe | base#1 | pass | 8 | 353 | 176723 | 14.634 | claude-sonnet-5-5 |
| probe | base#2 | pass | 4 | 141 | 88178 | 10.728 | claude-sonnet-5-5 |
| probe | cand-demo#1 | pass | 20 | 1116 | 312247 | 26.861 | claude-sonnet-5-5 |
| probe | cand-demo#2 | pass | 20 | 1096 | 312272 | 28.706 | claude-sonnet-5-5 |

Leitura: o aceite do `smoke-init-check` é trivial (todas passam); o que diferencia é custo. O `tokens` do probe é in+out e não conta o cache, que domina o custo real. O braço `plain` ainda carrega a config de usuário do Claude Code (o agente herda a conta), então não é "Claude puro" de verdade.

## 6. Check
```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev check
[ok] agents: 42/60 linhas, perfil 5/30
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); ...
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] xray: estimativa 1915/15000
exit=0
```

## 7. Sync
```
$ env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW bin/hdev sync --check
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
exit=0
```

## 8. Fechar dry-run
Em `fechar-dry-run.md`. Exit 0.

## 9. [juiz]
Cada item acima tem comando, exit e saída. O juiz não rodou nesta PR (proibido no pedido).
