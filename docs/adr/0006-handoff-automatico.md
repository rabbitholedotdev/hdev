# ADR 0006 — Handoff automático de sessão

- Status: aceito
- Data: 2026-11-15

## Contexto

O Opus orquestra sessões longas no harness-dev. O contexto da janela do modelo enche e o trabalho precisa continuar em outra sessão, com o mesmo agente, pasta, opções e conta, sem intervenção manual. Os tetos do `hdev check` fixavam exatamente 4 hooks.

## Decisão

- Hooks `UserPromptSubmit`, `PostToolUse` e `Stop` rodam `handoff_guard.py`: persistem `session_id` em `.hdev/state/session.json`, estimam o uso pela última mensagem assistant do transcript (input + caches / `handoff.window_tokens`) e, ao cruzar `handoff.threshold` (padrão 0.5), pedem ao agente que feche a unidade e rode `/handoff`.
- A skill `/handoff` e o comando `hdev handoff` gravom o resumo em `docs/progress.md` (com `handoff_seq`, cooldown e teto diário), consultam opcionalmente `hdev jev handoff`, abrem a sessão nova pelo WebSocket `op=nova` no socket do usuário (`/run/hdev-agents-<user>/agentes.sock`, path `/ws`) e orientam a encerrar a sessão antiga, sem apagá-la.
- O teto de hooks registrados passa de 4 para 7 (os 4 de sempre + o mesmo `handoff_guard.py` nos 3 eventos). Continua sendo um número exato, com arquivo e teste. Skills do núcleo ficam no teto 5 com a skill `handoff`.
- Só stdlib (ADR 0001). O cliente WebSocket Unix é mínimo, no próprio núcleo. Nenhuma mudança no core da Ratoeira.

## Consequências

- Apps precisam da release nova e do `settings.json` com os 7 hooks (init sem `--force` não reescreve settings já existente).
- Janela de tokens, limiar, cooldown, teto diário e socket são configuráveis em `.hdev/config.json`.
- Se o `session_id` do Claude não coincidir com o `sessao` da Ratoeira, o herdar de conta/opções fica "a confirmar" e usam-se os padrões da config.
