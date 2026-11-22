# Evidência — fechar --dry-run

HEAD `ed1013bdd5c2050f3d02dd76d20907bfdce6d98a`, branch `cursor/v2-pr5-hooks-f0fd`.

```
$ bin/hdev fechar --plan work/v2-pr5-hooks/plan.md --dry-run
hdev fechar: commit do marco pulado (branch cursor/v2-pr5-hooks-f0fd não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T213958487046Z.json
exit=0
```

A suíte (`gates.full`) rodou dentro do fechar e ficou verde. O marco não foi criado.
