# Comando

Leia só no passo 2. Sem `| tail` nem outro pipe: o código de saída tem de ser o do hdev.

No núcleo:

```
bin/hdev handoff --estado "..." --proximo "..." --decisoes "..." --bloqueios "..."; echo "exit=$?"
```

No app, `python3 .harnessdev/bin/hdev handoff ...`.

O comando grava o resumo em `docs/progress.md`, pode consultar o Jev e abre a sessão nova. Exit 0 com o id da sessão: encerre esta. Não apague a conversa antiga. Não chame de novo aqui (há cooldown e teto diário). Exit 1 (`"ok": false`) com cooldown, limite diário ou unidade não fechada: continue aqui. `--dry-run` só mostra o pedido.
