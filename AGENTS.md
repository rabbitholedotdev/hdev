# AGENTS.md — núcleo harness-dev

Mapa. A regra mora em `harness/prompts/`; este arquivo não a repete.

## Onde
- Papéis: `harness/prompts/orchestrator.md`, `executor.md`, `implementer.md`, `reviewer.md`.
- Cada papel inclui `harness/prompts/_shared/` por referência (`stop-list.md`, `safety.md`, `style.md`).
- Plano e evidência: `work/<id>/`. Estado: `docs/progress.md`. Decisão: `docs/decisions.md`.
- Manifesto: `.hdev/config.json`. `hdev sync` gera `.claude/settings.json`.
- Hooks: `harness/hooks/` (`pre_tool.py`, `stop_gate.py`, `session.py`). Alias em `hooks/`. Unidade aberta segura o Stop.
- Skills: `.claude/skills/`. Caso de cada uma: `evals/skills/`.
- Evals: `evals/tasks/<id>/task.json`. Braços em `evals/arms/`. Contexto: `hdev xray`.
- Cache de código: `.hdev/cache/graph/` (`hdev graph update`). Impacto: `hdev impact`. Consulta extra só no `haiku-explorar`.
- Biblioteca: `library/` no repo. `hdev library pull` traz poucas lições. `hdev reflect` grava. Release em `.harnessdev/library/` é só leitura.

## Fluxo
1. `hdev triage`. Brief: skill `briefing` → `work/<id>/brief.md` (seção Opções na mesma sessão).
2. Skill `spec` → `work/<id>/spec.md`. Portão: `hdev spec check`. Aprovada: `hdev library pull`.
3. Skill `revisar-spec`, outro provedor, sem histórico → `work/<id>/review.md`. Zero Blocker.
4. Skill `planejar`, TDD. Opus orquestra (`harness/prompts/orchestrator.md`); implementa `sonnet-implementar`; explora `haiku-explorar`.
5. Skill `revisar-diff`, outro provedor. Pronto: `hdev check` e `hdev judge --run-tests`.
6. `hdev fechar --plan P` roda `gates.full` em clone limpo (base de `hdev base --marcar`). Depois: `hdev reflect`. Até 5 linhas em Lições (`docs/progress.md` ≤ 2.000).

## Verbos
`hdev check` · `xray` · `eval` · `sync [--check]` · `init` · `judge` · `spec check` · `resume` · `jev` · `handoff` · `codex-exec` · `grok-review` · `base` · `fechar` · `triage` · `app` · `release` · `rollback` · `pin` · `area` · `wt` · `graph update` · `impact` · `library` · `reflect` · `improve`

## Tetos
AGENTS.md ≤ 60 (perfil ≤ 30) · hooks = 5 registros, 3 arquivos · skills visíveis por fase ≤ 5 (description ≤ 200) · subagentes ≤ 2 (F2+; F0/F1 = 0) · xray ≤ `caps.context_initial` · juiz de outro provedor que o executor.

## Nomes
Inglês, ASCII, minúsculas e hífen; prosa em pt-BR (`docs/padroes/naming.md`). Worktree em `<área>/_wt/<repo>-<branch>` (`hdev wt add`).

## Não fazer
Cópia do RabbitOS, orquestrador próprio, pasta `agents/` na raiz, fine-tuning, chave de API paga. Spec Kit, BMAD, OpenSpec e o plugin EGM não se instalam sozinhos.

<!-- perfil:harness-developer -->
## Perfil harness-developer
- `hdev check` é portão: peça não fecha com check vermelho.
- Peça nova do núcleo entra com teste em `tests/` ou caso em `evals/tasks/`.
- No máximo 1 skill própria do perfil.
- Mudar decisão D1–D4 ou teto (hooks, subagentes) só por ADR em `docs/adr/`.
<!-- /perfil -->
