# Braços

`plain` tira o andaime: CLAUDE.md, AGENTS.md, `.claude/settings.json`, `.claude/skills`, `.claude/hooks` e `harness/prompts`. O que sobra é o Claude Code puro.

`base` deixa o clone como está no `base_sha` da tarefa.

`cand-<id>` é a pasta `.hdev/overlays/<id>/` (gitignored, do `hdev improve`) ou, se não houver, `evals/arms/cand-<id>/`. O `hdev eval run` copia o conteúdo por cima do base e tira o `remove` da ficha `.hdev/overlays/<id>.json`. O overlay é lido da árvore de quem invoca o comando, não do commit antigo. Caminho de `harness/protected.txt` faz o `hdev check` falhar (ADR 0013).

## Runners

`none` não chama agente. `fake` imprime um usage fixo, sem modelo. `auto` chama o agente só se o caso tem prompt. `claude` chama o `eval.agent_cmd` (padrão `claude -p --output-format json`) com o Sonnet (`eval.model`), permissão `acceptEdits`, ferramentas estreitas, push e root proibidos e `eval.timeout_sec` (600 s); o caso precisa de prompt. Cada linha grava o modelo que rodou (`modelUsage`) e marca quando não é o pedido.
