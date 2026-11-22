# Plano — CHIP-001 (etiqueta do app barra escrita em código)

Spec: sem spec (decisão do dono, 21/11: "Sim, manda fazer" e "As duas")

## Objetivo
Na Ratoeira, a etiqueta do app ("+ SampleApp") marca a trilha da conversa. Com a etiqueta de um app deste repo, a conversa é de uso do app: trabalho operacional pelas ferramentas MCP dele, sem mudar código. Sem a etiqueta, na pasta do repo, é dev com o harness-dev. O chat põe a etiqueta no prompt num bloco `<ratoeira-contexto>`: "Esta conversa está ligada ao X" (só na 1ª mensagem; vale a sessão) e "App marcado na mensagem: X (…)" (vale o turno). O PreToolUse não traz o prompt, então o `session.py` grava a etiqueta no UserPromptSubmit e o `pre_tool.py` lê.

## Critério de pronto
- `python3 -m unittest tests.test_hooks.AppChip -v` sai 0 com os 6 casos: etiqueta ligada barra Write/Edit/MultiEdit/NotebookEdit e escrita do shell em código (`>`, `sed -i`, `rm` depois de `cd`, `cp` para o repo, `git commit`, `tee`) e libera leitura (`Read`, `cat`, `git status`, `grep`), escrita fora do repo (`/tmp`) e em `.hdev/`; sem etiqueta ou só com "Tela aberta agora" libera; etiqueta de outro app libera; marcada vale só no turno e ligada vale na sessão (outra sessão passa); contexto copiado de outra conversa não conta; worktree do repo também é barrado.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0 (matcher do PreToolUse com `NotebookEdit` no manifesto e no `.claude/settings.json`).
- `bin/hdev fechar --plan docs/plan-chip-001-etiqueta-app.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- Escrita por interpretador (`python -c`, `node -e`): passa.
- Regra no AGENTS.md da área Duartes (feita fora deste repo, sem commit).
- Release e promoção do `latest`: com o sim do João, depois do merge.
