# Plano — CFG-001 (base do núcleo vira master)

Spec: sem spec (decisão do dono, 20/11: "Base vira master")

## Objetivo
O `base_branch` do núcleo passa de `f2-11-v0.6.0` para `master`. Hoje as duas estão no mesmo commit (5b31928), mas cada PR na f2-11 pedia depois um PR de sincronização para a master. Com a base na master, o marco do `hdev fechar` nasce na master e a f2-11 deixa de ser a linha de integração. Só a chave do repo muda: a release não impõe `base_branch` ao app (`hdev/config.py` `REPO_ONLY`).

## Critério de pronto
- `python3 -c "import json; print(json.load(open('.hdev/config.json'))['base_branch'])"` imprime `master` e sai 0.
- `python3 -c "from hdev import fechar; print(fechar.configured_base_branch('.'))"` imprime `master` e sai 0.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan docs/plan-cfg-001-base-master.md --dry-run` sai 0 e diz que a branch do PR não é a base `master`.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- Apagar a branch `f2-11-v0.6.0` do GitHub.
- Promover o canal `latest` (continua na v0.7.1).
