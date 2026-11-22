# Vereditos para o João rotular

Atualizado 2026-11-14 15:52 America/Sao_Paulo.

O `hdev judge` é consultivo até 20 rótulos válidos em `evals/judge-labels/` (formato no README desta pasta). Só o João rotula. Esta lista é só para conferência humana: não preenche `expected` nem `by`.

Para o rótulo oficial, um JSON por caso, `<data>-<tarefa>.json`, com `plan`, `run` (caminho do arquivo em `.hdev/runs/`), `judge_verdict`, `expected`, `by` e, se quiser, `note`.

Há 9 peças com veredito de referência (as do WAITING de 15:18). Existem também 4 corridas anteriores no diretório de runs, listadas no fim: o juiz descartou o veredito ou a peça foi julgada de novo depois do F1-06. Em `concorda` / `discorda`, deixe em branco e marque uma das duas.

Juiz: grok-4.7 (assinatura, `--prompt-file`). Fallback Codex, quando houve, saiu 401 e foi descartado.

## A rotular (9)

### F0-01 — estrutura
- plan: `docs/plan-f0-estrutura.md`
- run: `.hdev/runs/judge-20261114T181201684503Z.json`
- veredito do juiz: **fail**
- motivo: no clone limpo de `c94d976`, o `hdev check` saiu 1 (hook citado sem arquivo) e os testes nem começaram (não havia pasta `tests/`); o critério pedia check verde.
- João: concorda / discorda: ________

### F0-02 — skill brainstorm
- plan: `docs/plan-f0-skill-brainstorm.md`
- run: `.hdev/runs/judge-20261114T181334487887Z.json`
- veredito do juiz: **fail**
- motivo: o diff de `9e6f6ad` só traz plano e spec; falta `.claude/skills/brainstorm/SKILL.md`. Os testes falharam sem `tests/`, e o check saiu 1 por hook ausente.
- João: concorda / discorda: ________

### F0-03 — hooks
- plan: `docs/plan-f0-hooks.md`
- run: `.hdev/runs/judge-20261114T181443172623Z.json`
- veredito do juiz: **pass**
- motivo: no clone de `187800a` o check viu 4 hooks com arquivo e teste; `tests/test_hooks.py` passou (22 testes) e o diff ficou no escopo, sem risco extra.
- João: concorda / discorda: ________

### F0-04 — CLI hdev
- plan: `docs/plan-f0-hdev-cli.md`
- run: `.hdev/runs/judge-20261114T175405606622Z.json`
- veredito do juiz: **pass**
- motivo: no clone limpo de `a9abdaf`, 63 testes (check, init, judge) e o `hdev check` passaram; o diff implementa só essa peça e não traz segredo, destrutivo nem chave de API.
- João: concorda / discorda: ________

### F0-05 — eval de fumaça
- plan: `docs/plan-f0-eval-fumaca.md`
- run: `.hdev/runs/judge-20261114T181531523323Z.json`
- veredito do juiz: **pass**
- motivo: o caso de fumaça e o `tests/test_evals.py` no clone de `e67f90b` fizeram a suíte passar (65 testes) e o `hdev check` saiu 0; o diff se limita a essa peça.
- João: concorda / discorda: ________

### F1-02 — juiz Grok
- plan: `docs/plan-f1-juiz-grok.md`
- run: `.hdev/runs/judge-20261114T181719985156Z.json`
- veredito do juiz: **pass**
- motivo: no clone de `2eada3c` os 6 itens e 74 testes passaram, com `hdev check` verde e juiz xai; provedor, schema JSON e leitura do envelope têm teste.
- João: concorda / discorda: ________

### F1-04 — `.harnessdev`
- plan: `docs/plan-f1-harnessdev.md`
- run: `.hdev/runs/judge-20261114T180747512367Z.json`
- veredito do juiz: **pass**
- motivo: 98 testes e check verdes no clone de `69d01b9`; o diff cobre archive/link/lock e recusa tag movida ou troca de versão sem `--force`.
- João: concorda / discorda: ________

### F1-05 — revisão Codex
- plan: `docs/plan-f1-revisao-codex.md`
- run: `.hdev/runs/judge-20261114T180435954207Z.json`
- veredito do juiz: **pass**
- motivo: no clone de `993ddfc`, 87 testes e check verdes; os achados (rm com `cd` e `.git`, sem exceção em `/tmp`, despejo de ambiente, segredo sem aspas, etc.) têm teste correspondente.
- João: concorda / discorda: ________

### F1-06 — pacote do juiz
- plan: `docs/plan-f1-pacote-juiz.md`
- run: `.hdev/runs/judge-20261114T181114601203Z.json`
- veredito do juiz: **unsure**
- motivo: 104 testes e check verdes no clone de `a5ee63d`; o grok ficou em dúvida só no item de ter julgado F0-04, F1-05 e F1-04, porque `.hdev/runs/` não entra no git e não aparece no pacote. O fallback Codex saiu 401 e foi descartado.
- João: concorda / discorda: ________

## Corridas anteriores (4), não são o veredito de referência

Úteis para ver o que o pacote antigo induziu. Se for rotular alguma, use o `run` dela e não o da tabela acima.

### F0-04 — primeira tentativa
- run: `.hdev/runs/judge-20261114T174448070312Z.json`
- veredito do juiz: **fail**
- motivo: a suíte (98 testes) e o check pareciam ok, mas o pacote incluía scripts em `logs/` (tmux/relançamento) e o diff de `run-session.sh` chegou cortado.
- João: concorda / discorda: ________

### F0-04 — segunda tentativa
- run: `.hdev/runs/judge-20261114T174626548705Z.json`
- veredito do juiz: **unsure**
- motivo: o grok não viu os nomes dos testes nem a saída do `hdev check` no bloco de testes, e o miolo do diff estava cortado. O fallback Codex saiu 401 e foi descartado.
- João: concorda / discorda: ________

### F0-04 — terceira tentativa
- run: `.hdev/runs/judge-20261114T175058641707Z.json`
- veredito do juiz: **fail**
- motivo: o log de testes (103 OK) não batia com a árvore julgada: citava casos que os arquivos novos não tinham e omitia os que o diff trazia.
- João: concorda / discorda: ________

### F1-05 — primeira tentativa
- run: `.hdev/runs/judge-20261114T175926500709Z.json`
- veredito do juiz: **unsure**
- motivo: os 6 critérios e 87 testes no commit `993ddfc` passaram, mas o grok ficou em dúvida (depois a peça foi julgada de novo e passou). O fallback Codex saiu 401 e foi descartado.
- João: concorda / discorda: ________

## Rotulados em 20/11 (13)

- `2026-11-16-f2-08-lock-versao-3a1bf47.json`: juiz unsure, expected pass
- `2026-11-16-f2-10-english-names-5d6eb17.json`: juiz fail, expected fail
- `2026-11-16-f2-10-english-names-7591815.json`: juiz fail, expected fail
- `2026-11-19-v2-pr2-work-tree.json`: juiz pass, expected pass
- `2026-11-19-v2-pr3-manifest-sync-5b672ae.json`: juiz unsure, expected unsure
- `2026-11-19-v2-pr3-manifest-sync.json`: juiz pass, expected pass
- `2026-11-19-v2-pr4-prompts.json`: juiz pass, expected pass
- `2026-11-19-v2-pr5-hooks.json`: juiz pass, expected pass
- `2026-11-19-v2-pr6-skills.json`: juiz pass, expected pass
- `2026-11-19-v2-pr7-judge-pacote.json`: juiz pass, expected pass
- `2026-11-19-v2-pr8-fechar-full.json`: juiz pass, expected pass
- `2026-11-20-v2-parada-fechada.json`: juiz pass, expected pass
- `2026-11-20-v2-pr9-evals-xray.json`: juiz pass, expected pass
