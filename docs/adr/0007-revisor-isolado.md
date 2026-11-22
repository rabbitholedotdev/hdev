# ADR 0007 — Revisor aninhado isolado

- Status: aceito
- Data: 2026-11-15

## Contexto

Num consumer app (15/11), seis commits saíram com o prompt do revisor como mensagem ("Você é revisor goldfish…", "Base directory for this skill…"). Quem commita é o gancho `commit-turno` do host (gerenciado em `$HDEV_HOST_HOOKS/claude`, `$HDEV_HOST_HOOKS/codex` e `$HDEV_HOST_HOOKS/grok`): no fim de cada turno de agente numa área (`$HDEV_AREAS/`), commita o que mudou no turno com a 1ª linha do pedido. Cada `hdev grok-review`/`codex-exec` é um agente inteiro, então commitava o próprio prompt e arrastava o trabalho em andamento do orquestrador (ex.: a spec de outra unidade entrou no commit do revisor). O Grok também lê os hooks do `.claude/settings.json` do projeto: a sessão do juiz sobrescreveu `session_id`/`transcript_path` em `.hdev/state/session.json`. E a skill `/handoff` deixou o agente escrever `## Handoff #4` à mão antes de o `hdev handoff` recusar (Jev), e o `| tail` escondeu o código de saída.

## Decisão

- **Título**: `codex-exec` e `grok-review` põem `hdev <comando>: <--titulo>` como 1ª linha do pedido (padrão "revisão sem contexto"). Se algum commit acontecer, a mensagem é essa.
- **Aninhado**: os wrappers exportam `HDEV_NESTED=1`; `handoff_guard`, `gate_tests` e `progress_guard` saem 0 logo no começo. `hook_decide` ignora transcript de Grok (`…/updates.jsonl`, `.grok/`, `grok-contas/`) e de Codex (`rollout-*`, `.codex/`). `secret_guard` e `destructive_guard` continuam valendo.
- **Cópia isolada** (`hdev/isolar.py`): `grok-review` roda por padrão (`--sem-isolar` desliga) e `codex-exec` com `--isolar` numa cópia em `/tmp/hdev-isolado-*` (`git clone --shared`, mesmo HEAD, índice copiado, modificados/novos não ignorados copiados, apagados apagados). Fora das áreas, o `commit-turno` não age. Caminhos absolutos do repo no pedido passam a apontar para a cópia. No fim, arquivo novo/alterado pelo revisor volta ao repo **sem commit** (o orquestrador commita); se o repo mexeu no mesmo arquivo nesse meio tempo, a versão do revisor fica em `<arquivo>.hdev-isolado`. Apagar não se propaga. A cópia é removida (`HDEV_KEEP_SCRATCH=1` mantém).
- **Skill `/handoff`**: nunca escrever `## Handoff` à mão; rodar sem pipe e ler `exit=$?`.
- Nada no core da Ratoeira muda (o `commit-turno` fica como está). Só stdlib (ADR 0001).

## Consequências

- `codex-exec` sem `--isolar` continua no repo (trabalho de executor); as skills de review pedem `--isolar`.
- Revisor que precisa de arquivo ignorado (ex.: `.env`, `node_modules`) não o vê na cópia; é o desejado para goldfish.
- Rollback: `hdev rollback --to v0.3.7`.
