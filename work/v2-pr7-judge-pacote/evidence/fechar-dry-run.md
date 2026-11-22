# Evidência — fechar --dry-run

HEAD `cd48bb58d2870efbe169b6bccc42dd95b892638c`, branch `cursor/v2-pr7-judge-package-8699`. Esta página não muda o comando.

```
$ bin/hdev fechar --plan work/v2-pr7-judge-pacote/plan.md --dry-run
hdev fechar: commit do marco pulado (branch cursor/v2-pr7-judge-package-8699 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T224859061767Z.json
exit=0
```

A suíte (`gates.full`) rodou dentro do fechar e ficou verde. O marco não foi criado.
