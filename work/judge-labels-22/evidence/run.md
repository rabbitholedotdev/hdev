# Evidência — 22 rótulos do juiz

Suíte, check e `count_labels` no HEAD `7bc5a323c62e280ef7e0b6cc08a4e2cf4f0fb73e`, depois do merge de `origin/f2-11-v0.6.0` (`97ad787`, grafo). Este arquivo entrou depois dessa corrida. Os 13 JSON foram copiados byte a byte (0 diferenças contra os anexos). O sufixo do anexo (`_54dc`, `_c8d1` e os outros) saiu do nome com `git mv`; o conteúdo não mudou. `plan`, `run`, `judge_verdict`, `expected` e `note` não foram editados. `LABELS_NEEDED` continua 20.

## Por que a suíte não mudou

Nenhum teste contava rótulos no repo do núcleo. `test_consultivo_ate_20_rotulos` e o cache do juiz usam um diretório temporário (`consultivo (0/20` com a pasta vazia; `advisory` falso só com 20 rótulos escritos ali). `test_rotulo_invalido_ou_repetido_nao_conta` também. A regra `advisory = labels < LABELS_NEEDED` ficou. Com 22 rótulos no núcleo a suíte passou sem alterar teste.

CHANGELOG e `docs/progress.md` ficaram com os dois lados: a linha do cache de grafo e a dos 13 rótulos; no progresso, a linha dos 22 rótulos e a de PR1–PR13 (PR10 cache, PR13 parada fechada).

## 1. count_labels

```
$ python3 -c "from hdev.gates.judge import count_labels; print(count_labels('.'))"
22
```

exit=0

## 2. valid_label

Os 13 arquivos passam. exit=0. `invalid 0 of 13`.

```
ok 2026-11-16-f2-08-lock-versao-3a1bf47.json unsure pass
ok 2026-11-16-f2-10-english-names-5d6eb17.json fail fail
ok 2026-11-16-f2-10-english-names-7591815.json fail fail
ok 2026-11-19-v2-pr2-work-tree.json pass pass
ok 2026-11-19-v2-pr3-manifest-sync-5b672ae.json unsure unsure
ok 2026-11-19-v2-pr3-manifest-sync.json pass pass
ok 2026-11-19-v2-pr4-prompts.json pass pass
ok 2026-11-19-v2-pr5-hooks.json pass pass
ok 2026-11-19-v2-pr6-skills.json pass pass
ok 2026-11-19-v2-pr7-judge-pacote.json pass pass
ok 2026-11-19-v2-pr8-fechar-full.json pass pass
ok 2026-11-20-v2-parada-fechada.json pass pass
ok 2026-11-20-v2-pr9-evals-xray.json pass pass
```

## 3. Suíte

```
$ python3 -m unittest discover -s tests -t . -q
Ran 479 tests in 119.889s
OK
```

exit=0. A stdout também traz o aviso já conhecido de `tests/test_naming.py` (arquivo não-UTF-8 no teste) e as linhas do isolador sobre `a.txt.hdev-isolado`. Não falhou teste.

## 4. bin/hdev check

exit=0

```
[ok] agents: 41/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1983/2000 caracteres
[ok] xray: estimativa 1802/15000
[ok] graph: só o explorer; query, path, explain
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 179 segmentos novos, 0 não-ASCII, 0 avisos
```

## 5. bin/hdev sync --check

exit=0

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

Com este arquivo no disco, `count_labels` continua 22 e `bin/hdev check` e `bin/hdev sync --check` saem 0. A linha `names` passa a `182 segmentos novos` (a pasta `work/judge-labels-22/evidence/`). O resto do check é o mesmo, inclusive `progress: 1983/2000`.

## Nomes sem o sufixo do anexo

`git mv` tirou `_xxxx` dos 13 arquivos. O SHA-256 de cada JSON ficou igual. Lista acima já com o nome novo.

```
$ python3 -c "from hdev.gates.judge import count_labels; print(count_labels('.'))"
22
```

exit=0. `bin/hdev check` exit=0: `progress: 1983/2000`, `names: 182 segmentos novos`, `xray: estimativa 1805/15000` (medido antes deste parágrafo).
