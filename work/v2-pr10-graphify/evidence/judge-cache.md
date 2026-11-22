# Evidência — cache do juiz

O `update` do grafo imprimia o sha do repo temporário no stdout do teste. `normalize_test_log` só tira duração e caminho `/tmp`, então o `package_sha` mudava a cada corrida. Os testes de `tests/test_graph.py` agora capturam stdout e stderr. A função de normalizar não foi afrouxada: hex no meio do log continua na chave.

Base já em `131311c` (parada fechada, v0.7.0). O merge está no branch. `VERSION` ficou `0.7.0`, sem tag nova.

Duas corridas de `python3 -m unittest discover -s tests -q` no mesmo código. As duas saíram 0. 479 testes. Depois de `normalize_test_log`, os dois textos são iguais.

Corrida 1, trecho cru: `Ran 479 tests in 144.470s`. Corrida 2: `Ran 479 tests in 136.892s`. Nenhuma das duas imprimiu `grafo atualizado` nem `grafo em dia`.

Texto normalizado (as duas corridas):

```
hdev: devolvido ao repo (não commitado): a.txt.hdev-isolado
hdev: o repo mudou nestes enquanto o revisor rodava; a versão dele ficou em <arquivo>.hdev-isolado: a.txt
hdev: devolvido ao repo (não commitado): a.txt.hdev-isolado
hdev: o repo mudou nestes enquanto o revisor rodava; a versão dele ficou em <arquivo>.hdev-isolado: a.txt
hdev: devolvido ao repo (não commitado): docs/reviews/r.md
hdev: devolução recusada (fora do repo): docs/reviews/r.md
/workspace/tests/test_naming.py:245: ResourceWarning: unclosed file <_io.TextIOWrapper name=b'/tmp/TMP/a\xffb.txt' mode='w' encoding='UTF-8'>
  open(os.path.join(os.fsencode(d), b"a\xffb.txt"), "w").write("x")
ResourceWarning: Enable tracemalloc to get the object allocation traceback
----------------------------------------------------------------------
Ran 479 tests in TIME

OK
```

O aviso do `test_naming` traz a pasta temporária; a normalização já troca isso por `/tmp/TMP`. As linhas do isolador são fixas (o nome do arquivo não muda). Nada disso leva sha de commit.

## bin/hdev check

HEAD `13068081768b16d9cadb370adc3464d1fad371ae`. exit=0.

```
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] xray: estimativa 1783/15000
[ok] graph: só o explorer; query, path, explain
```

## bin/hdev sync --check

exit=0

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

## bin/hdev fechar --plan work/v2-pr10-graphify/plan.md --dry-run

exit=0. Marco pulado. O veredito foi `.hdev/runs/fechar-20261120T034636614851Z.json`.
