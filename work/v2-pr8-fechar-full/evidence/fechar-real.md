# Evidência — fechar duas vezes

HEAD `59860342390f0045013de42f948ddbe4bdce1d8b`. Tree `8c4965662f28375c6e1411bd4237df48f4cceee7`. Branch `cursor/v2-pr8-fechar-full-eee7`, que não é a base `f2-11-v0.6.0`. As duas corridas foram nesse HEAD, com a árvore limpa. O marco não foi criado.

A parede é o relógio do fechar. O serial é a soma dos shards (clone local + testes). Os quatro shards disputam os núcleos e cada um clona o repo, então a soma fica acima de um `discover -q` sozinho. A parede é o que o fechar esperou.

## Primeira

424 testes, 4 shards, parede 67.5s, serial 189.7s, cache miss.

```
$ bin/hdev fechar --plan work/v2-pr8-fechar-full/plan.md
hdev fechar: commit do marco pulado (branch cursor/v2-pr8-fechar-full-eee7 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T233748040408Z.json
  suíte: pass tree=8c4965662f28375c6e1411bd4237df48f4cceee7 tests=424 shards=4 wall=67.5s serial=189.7s cache=miss
  Hdev-Gates-Full: pass tree=8c4965662f28375c6e1411bd4237df48f4cceee7 tests=424 shards=4 s=67.5 cache=miss
```

ELAPSED 67.57. exit=0.

## Segunda

O mesmo tree. A linha diz que veio do cache. A suíte não rodou de novo.

```
$ bin/hdev fechar --plan work/v2-pr8-fechar-full/plan.md
hdev fechar: commit do marco pulado (branch cursor/v2-pr8-fechar-full-eee7 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T233757421094Z.json
  suíte: pass tree=8c4965662f28375c6e1411bd4237df48f4cceee7 tests=424 shards=4 wall=67.5s serial=189.7s cache=hit (veio do cache)
  Hdev-Gates-Full: pass tree=8c4965662f28375c6e1411bd4237df48f4cceee7 tests=424 shards=4 s=67.5 cache=hit
```

ELAPSED 0.09. exit=0.
