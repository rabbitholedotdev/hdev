# ADR 0012 — Três arquivos de hook e cinco registros

- Status: aceito (João, 19/11/2026, no desenho da v2)
- Data: 2026-11-19
- Complementa a ADR 0006, que tinha posto o teto em 7 registros.

## Contexto

Cinco scripts em `hooks/` ocupavam 7 registros. `handoff_guard.py` sozinho ia em UserPromptSubmit, PostToolUse e Stop. Não cabia, sem subir o teto, negar pergunta na execução, segurar comando que falhou duas vezes, avisar colisão, fazer o ritual de início e cortar saída longa.

## Decisão

- A lógica mora em `harness/hooks/pre_tool.py`, `stop_gate.py` e `session.py`. `hooks/_lib.py` continua o comum e não conta como hook. Não se move: a sessão aberta importa esse arquivo.
- `pre_tool` junta segredo e destrutivo. Com `HDEV_PHASE=exec`, `AskUserQuestion` sai 2 e o motivo aponta `docs/padroes/defaults.md` e `harness/prompts/_shared/stop-list.md`. Comando que já falhou duas vezes seguidas sai 2. Arquivo mexido por outra sessão há menos de 30 minutos gera aviso (exit 0), com a unidade no texto.
- `stop_gate` no Stop junta testes afetados, PAREI e progress. O handoff de Stop roda neste arquivo, para o `decision` de encerrar não sumir. `session` fica com dois registros: UserPromptSubmit (ritual uma vez por sessão e handoff) e PostToolUse (corte e handoff).
- O corte guarda cabeça, linhas de erro e cauda. O resto vai para `.hdev/state/tool-output/` e o modelo recebe `updatedToolOutput`.
- O manifesto tem 5 registros. `caps.hooks` desce de 7 para 5. O `hdev check` mostra os 5 registros, os 3 arquivos e os aliases à parte.
- O desenho da migração escrevia o aceite como "hooks 5/7". Aqui o teto é 5 registros e 3 arquivos, não 5 de um teto que continua 7.
- Cada `hooks/*.py` antigo vira alias fino do comportamento que já tinha (mesmo stdin, mesmo exit). `hdev init` e `hdev release` instalam o alias e os 3 arquivos. `releases/v*/` já instalado não se reescreve. Apagar o alias é outra PR. Não há registro de `SessionStart`: seria o 6º.

## Consequências

- `hdev sync` regenera `.claude/settings.json`. Sessão já aberta não relê o arquivo.
- Init novo aponta para `.harnessdev/harness/hooks/`. Settings já existente não muda sem `--force`. O alias em `.harnessdev/hooks/` continua executável.
