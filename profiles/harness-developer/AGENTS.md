# AGENTS.md

Regras para qualquer agente (Claude Code, Codex, agy) neste repositório. Curto de propósito.
O núcleo mora em `.harnessdev/` (canal `latest` ou `hdev pin vX.Y.Z`; ver `.harnessdev.lock`).
Não edite nada dentro de `.harnessdev/`.

## Fluxo
1. `hdev triage`. Brief: skill `briefing`, artefato `work/<id>/brief.md` (seção Opções na mesma sessão).
2. Skill `spec`, artefato `work/<id>/spec.md`. Portão: `hdev spec check` (0 ok, 1 falha, 2 uso, 3 dono).
3. `/revisar-spec` em outro provedor, sem histórico (`hdev grok-review` ou `hdev codex-exec`). Artefato `work/<id>/review.md`. Zero Blocker.
4. `/planejar` com TDD; `hdev jev rotear` sugere o worker (sem chave, segue). Trivial: `sem spec` no plano.
5. Opus só orquestra. Hooks em `.harnessdev/harness/hooks/` (3 arquivos, 5 registros; `hooks/*.py` é alias). Implementa `sonnet-implementar`; explora `haiku-explorar`. Prompt: `.harnessdev/PROMPT-ORCHESTRATOR.md`. Contexto cheio: `/handoff`.
6. `/revisar-diff` em outro provedor + `hdev jev revisar-diff`. `run_judge` false: corrija e siga. Parada: `.harnessdev/harness/prompts/_shared/stop-list.md`.
7. Pronto: CI remoto verde, ou `hdev fechar` (suíte inteira) + `hdev check` + `hdev judge`. Override do dono: "liberado sem juiz: <motivo>".
8. Até 5 linhas em Lições de `docs/progress.md` (arquivo ≤ 2.000 caracteres).

## Sem CI local
Com CI remoto, a validação é o CI do PR. Sem CI remoto (sem runner e sem Actions), o Stop roda `gates.fast` (padrão ligado) e `hdev fechar` roda `gates.full` num clone limpo do HEAD, em shards, com cache por tree sha. Durante a edição, no máximo um teste focado.

## Worktrees
Worktree só em `<área>/_wt/<repo>-<branch>` (`hdev wt add`).

## Segurança
`.harnessdev/harness/prompts/_shared/safety.md`. Parada: `.harnessdev/harness/prompts/_shared/stop-list.md`. Unidade aberta não encerra. Handoff leva plano, brief, permissão e o mesmo modelo.

## Comandos
- `python3 .harnessdev/bin/hdev check` · `hdev fechar --plan work/<id>/plan.md` · `hdev judge --plan work/<id>/plan.md --run-tests`
- Cache de código: `hdev graph update`. Quem chama um arquivo: `hdev impact <arquivo>`.
- `hdev jev rotear|revisar-diff|humano|handoff` · `hdev handoff [--dry-run]` · `hdev resume` · `hdev codex-exec` · `hdev grok-review`
- Versão do núcleo: `hdev pin vX.Y.Z` ou `hdev pin --latest` (passo do dono).

## Nomes
Nomes novos de desenvolvimento em inglês, ASCII, minúsculas e hífen; prosa em pt-BR. Regra:
`docs/padroes/naming.md`; portão `names` do `hdev check` (`naming.mode`).

<!-- perfil:harness-developer -->
## Perfil harness-developer
- `hdev check` é portão: peça não fecha com check vermelho.
- Peça nova entra com teste ou caso em `evals/tasks/`. O `hdev check` inclui as linhas `xray` e `graph`.
- No máximo 1 skill própria do perfil.
<!-- /perfil -->
