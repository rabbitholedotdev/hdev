# Evidência — fechar dry-run

Rodado na branch `cursor/v2-pr4-prompts-2dad`, HEAD `864e1f60132e519dbfbd5cae0bb56d33b45a1008`. A base da unidade é `d308a02`. O commit seguinte só acrescenta `work/v2-pr4-prompts/evidence/`.

## bin/hdev fechar --plan work/v2-pr4-prompts/plan.md --dry-run

exit=0

```
hdev fechar: commit do marco pulado (branch cursor/v2-pr4-prompts-2dad não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T204431631626Z.json
```

O marco não foi criado: a branch da PR não é `base_branch` (`f2-11-v0.6.0`). A suíte (`gates.full`) rodou dentro do `fechar` e ficou verde (o comando saiu 0 em cerca de 96s).
