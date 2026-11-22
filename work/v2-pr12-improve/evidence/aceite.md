# Aceite — v2-pr12-improve

> Superado: a tabela e as saídas dos itens 1, 2, 3, 6 e 7 abaixo são do HEAD `25e156f`. A prova final está na seção "Final", no fim desta página.

HEAD das corridas: `25e156f941c3655a3f5cba491ad5348dcb98899a` (branch `vm/v2-pr12-improve`). Base da unidade: `c0d51fd`.
Os commits depois desse HEAD só gravam esta evidência em `work/v2-pr12-improve/`.

| # | Comando | Exit | Ok |
|---|---|---|---|
| 1 | `python3 -m unittest tests.test_improve -q` | 0 | ok |
| 2 | `python3 -m unittest discover -s tests -q` | 0 | ok |
| 3 | `bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --dry-run` | 0 | ok |
| 4 | `bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --runner fake` | 0 | ok |
| 5 | `bin/hdev check` com `.hdev/overlays/bad/hooks/_lib.py` / sem | 1 / 0 | ok |
| 6 | `bin/hdev check` | 0 | ok |
| 7 | `bin/hdev sync --check` | 0 | ok |
| 8 | `bin/hdev fechar --plan work/v2-pr12-improve/plan.md --dry-run` | 0 | ok |
| 9 | [juiz] esta página | — | ok |

## 1. `python3 -m unittest tests.test_improve -q` — exit 0

```
Ran 20 tests
OK
```

Cobre: overlay em caminho protegido e `remove` de pasta acima de um protegido fazem `check_overlays` falhar com o caminho; overlay limpo e nenhum overlay passam; `check_overlays` está em `CHECKS`; probe recusa candidata protegida antes de clonar; dry-run imprime o plano e não grava `.hdev/runs/` nem `library/`; `a,b` × 4 = 16 > 12 sai 2 e nada roda; `--runs 2` recusado; probe com runner fake grava 3 braços × 3 corridas, `adopted: []`, xray da candidata abaixo do base, relatório com "não adotado"; `git status` fora de `.hdev/` e `library/` igual antes e depois, HEAD igual, arquivo removido pela candidata e `AGENTS.md` intactos na árvore; item da biblioteca `source: improve`, `status: candidate`, `generalization: pending`, evidência `{unit, run, delta}` e `store.problems` vazio; `demo` determinística e marcada; regras do veredito (empata, ganharia ≥ 15%, empata < 15%, perde por qualidade mesmo mais barata, perde por custo ≥ 15% pior, métrica sem dado ignorada, sem evidência), mediana e alerta de diff > 50%.

## 2. `python3 -m unittest discover -s tests -q` — exit 0

HEAD `25e156f`.

```
Ran 529 tests in 188.117s
OK
real	3m8.271s
```

Único aviso na saída é um `ResourceWarning` de `tests/test_naming.py:245`, que já existia antes desta PR.

## 3. dry-run — exit 0

```
hdev improve: dry-run (nada roda, nada se adota)
  caso: smoke-init-check
  braços: plain, base, cand-demo
  3 braços × 3 corridas = 9 (teto 12)
  candidata demo (domínio): tira a referência de opções da skill briefing
```

Nenhum arquivo `improve-*` nem `eval-*` novo em `.hdev/runs/`.

## 4. probe real com runner fake — exit 0

```
hdev improve: smoke-init-check, 3 braços × 3 corridas, nada adotado
  demo (domínio): empata [alerta diff > 50%]
  biblioteca: gravado lesson-0006
  registro: .hdev/runs/improve-<stamp>.json
  relatório: .hdev/runs/improve-<stamp>.md
```

Relatório:

```
| braço | corridas | pass | tokens | segundos | xray |
|---|---|---|---|---|---|
| plain | 3 | 1.0 | 18 | 0.243 | 293 |
| base | 3 | 1.0 | 18 | 0.251 | 1635 |
| cand-demo | 3 | 1.0 | 18 | 0.25 | 1635 |

Paradas fora da lista: sem medida no runner fake.

- `demo` (domínio): **empata**, não adotado. Δ {"pass": 0.0, "seconds": -0.004, "tokens": 0.0, "xray": 0.0}. Alerta: diff > 50%.
```

O alerta vem de a candidata tirar o arquivo inteiro (100% das linhas tocadas).

Item da biblioteca (linha nova de `library/index.jsonl`):

```
{"body_path":"library/lessons/0006.md",...,"evidence":[{"delta":{"pass":0.0,"seconds":-0.004,"tokens":0.0,"xray":0.0},"run":"improve-<stamp>.json","unit":"v2-pr12-improve"}],"generalization":"pending","id":"lesson-0006","kind":"lesson",...,"source":"improve","status":"candidate",...,"title":"Candidata demo do improve: empata",...}
```

`git status --porcelain` e `git diff --stat`:

```
antes:  (vazio) / (vazio)
depois: M library/index.jsonl, ?? library/lessons/0006.md / library/index.jsonl | 1 +
git diff --stat -- harness .claude hooks hdev AGENTS.md CLAUDE.md .hdev/config.json: (vazio)
```

Depois: `git restore library/` e a remoção de `library/lessons/0006.md`. A lição da `demo` não é lição real (só prova o caminho); não entra na PR. `git status --porcelain` voltou vazio.

## 5. lista protegida no check — exit 1 / exit 0

Com `.hdev/overlays/bad/hooks/_lib.py`:

```
[FALHA] overlays: bad: hooks/_lib.py protegido (arquivo)
```

exit 1. Sem o overlay (`demo` continua):

```
[ok] overlays: 1 candidatas, nenhuma em caminho protegido
```

exit 0.

## 6. `bin/hdev check` — exit 0

```
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: ...
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] xray: estimativa 1908/15000
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] overlays: 1 candidatas, nenhuma em caminho protegido
```

AGENTS.md 42/60, progress 1154/2000, subagentes 2/2.

## 7. `bin/hdev sync --check` — exit 0

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

## 8. `bin/hdev fechar --plan work/v2-pr12-improve/plan.md --dry-run` — exit 0

Saída em `work/v2-pr12-improve/evidence/fechar-dry-run.md`. Marco pulado (a branch não é a base); a suíte não roda no dry-run.

## Nada chamou modelo

`hdev improve probe` só aceita `--runner fake` ou `none`. O juiz, o Codex, o Grok, o Jev e um claude real não rodaram.

## Final — HEAD `649993b6f2e845d1ebfc42855288ab226d32994f` (clone limpo)

Esta seção substitui as saídas dos itens 1, 2, 3, 6 e 7 acima, que foram medidas no HEAD `25e156f`. Depois daquele HEAD vieram três mudanças:
- `72dd731` reverte `38c2024`. O caso `evals/tasks/v2-pr12-improve/task.json`, gravado pelo `fechar`, quebrava `tests.test_evals` (`test_formato` e `test_casos`).
- `a8f4665` faz o merge da v0.7.1 (`cc7b4a2`).
- `649993b` faz o merge da rede de autocompact (`4aa6b39`, #16).
Nos dois merges, o único conflito foi em `docs/decisions.md`, resolvido mantendo todas as linhas em ordem: v0.7.1, autocompact e PR12. O `hdev/check.py` mantém o `autocompact_error` e o `check_overlays`.

Todos os comandos rodaram num `git clone` novo, em HEAD destacado em `649993b`, com `git status --porcelain` vazio no fim.

| # | Comando | Exit | Resultado |
|---|---|---|---|
| 1 | `python3 -m unittest tests.test_improve -q` | 0 | `Ran 20 tests`, OK |
| 2 | `python3 -m unittest discover -s tests -q` | 0 | `Ran 540 tests in 76.349s`, OK |
| 3 | `bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --dry-run` | 0 | 3 braços × 3 corridas = 9 (teto 12) |
| 6 | `bin/hdev check` | 0 | todas as linhas `[ok]` |
| 7 | `bin/hdev sync --check` | 0 | bate com o manifesto |

Itens 4, 5 e 8: as provas acima, do HEAD `25e156f`, continuam valendo. O código do `improve`, do `check` e do `eval` não mudou depois dele; os merges só trouxeram a v0.7.1 e o autocompact.

### 2. Suíte completa

```
Ran 540 tests in 76.349s

OK
```

Avisos na saída: o `ResourceWarning` de `tests/test_naming.py:245`, que já existia antes, e as mensagens `hdev:` dos testes do revisor isolado.

### 1. `tests.test_improve`

```
Ran 20 tests in 0.956s

OK
```

### 6. `bin/hdev check`

```
[ok] agents: 42/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1194/2000 caracteres
[ok] xray: estimativa 1904/15000
[ok] graph: só o explorer; query, path, explain
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] overlays: nenhuma
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 239 segmentos novos, 0 não-ASCII, 0 avisos, branch: detached
```

### 7. `bin/hdev sync --check`

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

### 3. dry-run do probe

```
hdev improve: dry-run (nada roda, nada se adota)
  caso: smoke-init-check
  braços: plain, base, cand-demo
  3 braços × 3 corridas = 9 (teto 12)
  candidata demo (domínio): tira a referência de opções da skill briefing
```
