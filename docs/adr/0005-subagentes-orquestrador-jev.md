# ADR 0005 — Opus orquestra; teto de 2 subagentes na F2; Jev como gate

- Status: aceito (João, 15/11/2026, America/Sao_Paulo: "pode implementar... instale o jev" e "resolva o ponto frágil também")
- Área: núcleo / `.claude/agents`, `hdev jev`, wrappers, `hdev check`, fase F2
- Complementa ADR 0004 (fluxo goldfish) e o teto de subagentes da F1.

## Decisão
1. A fase do núcleo sobe para F2 (F2-01 e F2-02 já tinham saído com a config ainda em F1).
2. O teto de subagentes no `hdev check` sobe de 1 para 2 a partir da F2 (F0/F1 continuam 0). Os dois do núcleo são `sonnet-implementar` (TDD, um item) e `haiku-explorar` (busca/leitura). Pasta `agents/` na raiz segue proibida.
3. Na sessão principal, o Opus 5.5 só orquestra (lê backlog, delega, roda `hdev judge`, atualiza progress). Hooks de Stop ficam nessa sessão. Isso não é um "orquestrador próprio" (produto à parte), que continua vedado.
4. Codex e Grok não viram subagentes nativos: entram por `hdev codex-exec` e `hdev grok-review`, no contrato das rotinas da Ratoeira, com caminho absoluto `$HDEV_BIN_DIR` e o mesmo env do `agentes.json`.
5. Jev (TypeSafe System One) é gate tipado, não skill nova: `hdev jev` chama `POST /v1/systemone`. Várias perguntas no mesmo state. Chave por `HDEV_KEY_HELPER` (`op://Vault/jev-api/credential` ou `HDEV_JEV_REF` / `TYPESAFE_API_KEY`). Sem chave, exit 2 e o fluxo segue. A chave nunca é impressa.
6. Limiares (Noul ≥ 0,7 sim, ≤ 0,3 não, o meio incerto) ficam no código, não no modelo.

## Consequências
- Apps no canal latest recebem os agents no `hdev init` (symlink). AGENTS.md customizado do app não é sobrescrito sem `--force`.
- `hdev jev handoff` existe para um handoff futuro; não dispara sessão nova sozinho.
