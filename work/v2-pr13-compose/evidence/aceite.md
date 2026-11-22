# Aceite — v2-pr13-compose

HEAD das corridas: `282664a7a49b10471705f518cef36cae29192af7` (branch `vm/v2-pr13-compose`). Base da unidade: `c951dd6`.
Os commits depois desse HEAD só gravam esta evidência em `work/v2-pr13-compose/`.
Todo teste e todo `hdev check`, `fechar` e `improve probe` rodaram com o prefixo `env -u HDEV_HANDOFF_THRESHOLD -u HDEV_HANDOFF_WINDOW` (o ambiente da corrida sem cabeça trazia essas duas variáveis; o conserto é outra PR). Abaixo, `$P` é esse prefixo.

| # | Comando | Exit | Ok |
|---|---|---|---|
| 1 | `$P python3 -m unittest tests.test_improve tests.test_improve_compose -q` | 0 | ok |
| 2 | `$P python3 -m unittest discover -s tests -q` | 0 | ok |
| 3 | `$P bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --runner fake` / `bin/hdev improve compose --run <registro> --cand demo --dry-run` | 0 / 1 | ok |
| 4 | compose, merge e revert num clone temporário + `ComposeTest.test_compose_then_revert` | 0 / 0 | ok |
| 5 | `bin/hdev improve compose --run improve-bad.json --cand bad --dry-run` (overlay em `hooks/_lib.py`) | 1 | ok |
| 6 | `$P bin/hdev check` | 0 | ok |
| 7 | `bin/hdev sync --check` | 0 | ok |
| 8 | `$P bin/hdev fechar --plan work/v2-pr13-compose/plan.md --dry-run` | 0 | ok |
| 9 | [juiz] esta página | — | ok |

## 1. Testes do improve — exit 0

```
Ran 33 tests in 25.274s
OK
```

`tests/test_improve_compose.py` (13): recusa por veredito `empata` (com e sem `--dry-run`), candidata fora do registro, caminho protegido (`hooks/_lib.py`), fora do que pode editar (`AGENTS.md`, `remove` de `.claude/skills/revisar-diff/SKILL.md`), árvore rastreada suja, branch `improve/lean` que já existe, candidata que não muda nada; em toda recusa HEAD, `git status` e `improve/*` ficam iguais. Regra `may_edit` (ADR 0014). Dry-run mostra branch, `muda`/`sai`, a lição e os trailers e não grava nada. Caminho feliz: `improve/lean` com um commit cujo pai é o HEAD, trailer `Harness-Edit: lean` lido por `%(trailers)`, overlay e `remove` aplicados, lição `active` na branch e `candidate` no HEAD, HEAD, branch atual e árvore intactos; depois do `merge --ff-only`, `hdev improve revert --cand lean` sai 0, árvore e lição voltam, e o segundo revert sai 1 ("já revertido"). Compose sem lição no HEAD funciona. `revert --commit HEAD` sem trailer sai 1 nomeando `Harness-Edit`; `--cand` sem commit sai 1. Os 20 de `tests/test_improve.py` seguem verdes.

## 2. Suíte inteira — exit 0

```
Ran 553 tests in 286.208s
OK
real	4m46.456s
```

## 3. Probe real e compose `--dry-run` no repo — exit 0 / 1

```
$ $P bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --runner fake
hdev improve: smoke-init-check, 3 braços × 3 corridas, nada adotado
  demo (domínio): empata [alerta diff > 50%]
  biblioteca: gravado lesson-0006
  registro: .hdev/runs/improve-20261120T075052925998Z.json
  relatório: .hdev/runs/improve-20261120T075052925998Z.md
exit=0
$ bin/hdev improve compose --run improve-20261120T075052925998Z.json --cand demo --dry-run
hdev improve compose: recusado: demo deu empata em improve-20261120T075052925998Z.json; só ganharia se adota; árvore rastreada suja; commite ou guarde antes
exit=1
$ git status --porcelain
 M library/index.jsonl
?? library/lessons/0006.md
$ git branch --list 'improve/*'
(vazio)
```

O veredito foi `empata`, então a recusa com exit 1 é a saída pedida. `git status` só mostra o que o probe gravou na biblioteca; o compose não mudou nada. Limpeza depois: `git restore library/`; `library/lessons/0006.md`, `.hdev/runs/improve-*` e o `eval-*` do probe apagados.

## 4. Caminho feliz ponta a ponta — exit 0

Clone temporário (`git clone --local` deste HEAD em `/tmp/pr13-e2e-*/repo`, identidade local, hooks de git desligados no clone). Candidata `lean`: `harness/prompts/executor.md` curto e `remove` de `.claude/skills/briefing/references/options.md`. Probe de verdade com runner fake; deu `ganharia`.

```
$ $P bin/hdev improve probe --case smoke-init-check --cand lean --runs 3 --runner fake
  lean (domínio): ganharia [alerta diff > 50%]
  biblioteca: gravado lesson-0006
  registro: .hdev/runs/improve-20261120T074815720521Z.json
exit=0
# Δ {"pass":0.0,"tokens":0.0,"seconds":-0.261,"xray":-0.36}
$ bin/hdev improve compose --run <registro> --cand lean --dry-run   # lição ainda não commitada
hdev improve compose: recusado: árvore rastreada suja; commite ou guarde antes
exit=1
$ git add library && git commit -qm "lição do probe"
$ bin/hdev improve compose --run <registro> --cand lean
hdev improve compose: branch improve/lean criada em ecf52ae037ce
  muda: harness/prompts/executor.md
  muda: library/index.jsonl
  sai: .claude/skills/briefing/references/options.md
  biblioteca: lesson-0006 candidate -> active
  adotar é o merge humano de improve/lean; nada foi enviado
exit=0
$ git status --porcelain
(vazio)
$ git log -1 --format=%B improve/lean
improve: adota lean

executor curto
Probe improve-20261120T074815720521Z.json no caso smoke-init-check, base 8ec80b39eaa0: ganharia, Δ {"pass": 0.0, "seconds": -0.261, "tokens": 0.0, "xray": -0.36}.
Adotar é o merge desta branch; desfazer é `hdev improve revert --cand lean`.

Harness-Edit: lean
Harness-Probe: improve-20261120T074815720521Z.json
$ git merge -q --ff-only improve/lean      # o merge humano
$ bin/hdev improve revert --cand lean
hdev improve revert: ecf52ae037ce (Harness-Edit: lean) revertido em e312c99ef04d
exit=0
$ git diff --stat HEAD~2 HEAD
(vazio: árvore igual à de antes do merge)
$ bin/hdev improve revert --commit HEAD~2   # "lição do probe", sem trailer
hdev improve revert: recusado: commit HEAD~2 sem trailer Harness-Edit:; o revert só desfaz edição do improve
exit=1
```

O mesmo caminho está no teste `ComposeTest.test_compose_then_revert` (item 1). O clone fica no diretório temporário do sistema; nenhuma branch `improve/*` foi criada nesta worktree.

## 5. Caminho protegido — exit 1

No repo real, overlay `.hdev/overlays/bad/hooks/_lib.py` e registro `improve-bad.json` com veredito `ganharia`:

```
$ bin/hdev improve compose --run improve-bad.json --cand bad --dry-run
hdev improve compose: recusado: bad: hooks/_lib.py protegido (arquivo); árvore rastreada suja; commite ou guarde antes
exit=1
```

No clone do item 4, com árvore limpa: `recusado: bad: hooks/_lib.py protegido (arquivo)`, exit 1. Overlay e registro apagados depois.

## 6. `hdev check` — exit 0

```
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: ...
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] xray: estimativa 1915/15000
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] overlays: nenhuma
```

As 15 linhas `[ok]`; agents 42/60, progress 1206/2000.

## 7. `hdev sync --check` — exit 0

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

## 8. `hdev fechar --dry-run` — exit 0

Saída em `fechar-dry-run.md`.
