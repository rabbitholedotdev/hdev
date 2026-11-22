# Evidência — grafo real

graphify `0.9.112`, pacote PyPI `graphifyy` (o README diz que o nome no pip é esse; a CLI continua `graphify`). Instalado com `pip install graphifyy==0.9.112`. O comando foi `graphify update .` com `GRAPHIFY_OUT=.hdev/cache/graph`. O log diz `no LLM needed`. Não rodei `query` com modelo, nem `label`, nem `graphify install`.

## Hook no commit e9127d6

O `scripts/post-commit` rodou no commit `e9127d655d4df97b90085459e5ac8ebcdd1337e0`. Saída:

```
Updating code graph in . (no LLM needed)...
[graphify watch] Rebuilt: 2365 nodes, 5478 edges, 185 communities
[graphify watch] graph.json, graph.html and GRAPH_REPORT.md updated in .hdev/cache/graph
Code graph updated. For doc/paper/image changes run /graphify --update in your AI assistant.
grafo atualizado em .hdev/cache/graph (e9127d655d4d)
```

O sidecar `.hdev/cache/graph/sha` ficou igual ao HEAD: `e9127d655d4df97b90085459e5ac8ebcdd1337e0`.

O `graph.json` tem 2365 nós e 5478 arestas: 4840 EXTRACTED e 638 INFERRED. Uma aresta real:

```
source tests_test_stop -> target hdev_stop
relation imports_from
confidence EXTRACTED
```

`GRAPH_REPORT.md` caiu dentro de `.hdev/cache/graph/`. O gitignore `.hdev/cache/` cobre o grafo, o relatório e o sha. Nenhum prompt lê esse relatório.

## Comandos no grafo

`bin/hdev impact hdev/stop.py` exit=0. Lista `tests/test_stop.py`, `hdev/cli.py` e os outros que chamam ou importam o arquivo. O que ele importa de projeto não aparece: os imports são da stdlib (`json`, `os`, `sys` e o resto), na linha `fora do repo`.

`scripts/affected-tests hdev/stop.py` exit=0. A stdout traz `tests/test_stop.py` e mais sete testes que chegam nele por import EXTRACTED, em no máximo 8 saltos.

O caminho do desenho `hdev/gates/stop.py` não existe neste repo.
