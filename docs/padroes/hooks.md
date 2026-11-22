# Padrão — contrato dos hooks do núcleo

- Entrada: JSON do Claude Code no stdin (`tool_name`, `tool_input`, `cwd`, `session_id`, `stop_hook_active`).
- Raiz do projeto: `$CLAUDE_PROJECT_DIR`, senão `cwd` do evento.
- Saída: exit 0 libera; exit 2 bloqueia com o motivo no stderr (o modelo lê). Nunca imprime valor de segredo.
- Três arquivos em `harness/hooks/` (ADR 0012): `pre_tool.py`, `stop_gate.py`, `session.py`. O comum fica em `hooks/_lib.py` e não conta.
- Cinco registros no manifesto: `pre_tool` em dois PreToolUse, `stop_gate` no Stop, `session` em UserPromptSubmit e PostToolUse.
- `hooks/secret_guard.py`, `destructive_guard.py`, `gate_tests.py`, `progress_guard.py` e `handoff_guard.py` são alias. Apagar é outra PR.
- Stop: trava de laço de 3 bloqueios seguidos por sessão (`.hdev/state/<hook>.json`).
- `stop_gate` no Stop roda o recorte do diff (alvo <30s), não a suíte. A suíte inteira é no `hdev fechar`.
  `gates.on_stop: false` desliga. No 4º bloqueio o hook grava `PAREI: gate esgotado (<guard>)`.
  `PAREI` (lista fechada ou gate esgotado) libera o Stop mesmo com teste vermelho ou progress atrasado.
- Unidade `open` sem PAREI da lista segura o Stop (exit 2, com o próximo passo). Na 4ª vez grava `PAREI: gate esgotado (open_unit)`. O handoff grava `stop_session` da sessão que sai; só o Stop dessa sessão passa, uma vez. `SessionStart` de outra sessão apaga. `allow_stop` sem sessão não libera. Sessão sem unidade marcada segue como antes. O Stop do Codex e do Grok aponta o mesmo `stop_gate.py`.
- `pre_tool` com `HDEV_PHASE=exec` nega `AskUserQuestion` (exit 2). Comando que já falhou duas vezes seguidas também sai 2. Colisão (outra sessão no mesmo arquivo há menos de 30 min) só avisa.
- `session` faz o ritual de início uma vez por sessão e corta saída longa: cabeça, linhas de erro e cauda; o resto vai para `.hdev/state/tool-output/`.
- Medidas: `.hdev/state/metrics.jsonl` (gate) e `.hdev/runs/metrics.jsonl` (judge). Ignorados pelo git.
- Hook novo só entra no lugar de um dos 5 registros, com ADR. Não suba o teto.
- `scripts/post-commit` (e o `post-checkout`, que o chama) é hook de git. Não entra nos 5 registros e não passa pelo Stop nem pelo PreToolUse.
