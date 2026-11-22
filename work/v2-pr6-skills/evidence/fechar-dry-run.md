# Evidência — fechar --dry-run

HEAD `7c1be9e696822c22db45a82735e907f2f72d57c2`, branch `cursor/v2-pr6-skills-5e49`. O commit seguinte só grava esta página.

```
$ bin/hdev fechar --plan work/v2-pr6-skills/plan.md --dry-run
hdev fechar: commit do marco pulado (branch cursor/v2-pr6-skills-5e49 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T221312622627Z.json
exit=0
```

A suíte (`gates.full`) rodou dentro do fechar e ficou verde. O marco não foi criado.
