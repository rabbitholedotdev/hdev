# Plano — v071-parada-fix

Spec: sem spec (pedido fechado do dono; dois bugs confirmados na v0.7.0, c6baa68)

## Objetivo
A sessão nova não herda o direito de encerrar com a unidade aberta. Toda release nova traz `PROMPT-ORCHESTRATOR.md`. O plano em `docs/plan-<id>-<slug>.md` abre e fecha a unidade.

## Critério de pronto
- [x] Depois do handoff, Stop da sessão que saiu sai 0. Stop da sessão nova, com a unidade aberta, sai 2. O segundo Stop da sessão que saiu sai 2 (a permissão se gasta).
- [x] `SessionStart` de outra sessão apaga `stop_session`. O Stop seguinte da sessão antiga, com a unidade aberta, sai 2.
- [x] `session.json` só com `allow_stop: true` e unidade aberta: Stop sai 2.
- [x] PAREI da lista continua liberando o Stop. `standing_ok` publicar grava `READY-TO-PUBLISH` e não para.
- [x] O Stop que o `.codex/hooks.json` e o `.grok/hooks/stop.json` disparam usa a mesma sessão: a velha sai 0, a nova sai 2.
- [x] `hdev pin` e `hdev sync` num app temporário, com `HDEV_RELEASES_DIR` temporário, gravam `.codex/hooks.json` e `.grok/hooks/stop.json`. Os dois têm Stop `type: command` apontando `stop_gate.py`. `hdev sync --check` sai 1 se um deles diverge.
- [x] `release.install`, `hdev pin` e `hdev release` numa pasta nova de releases gravam `PROMPT-ORCHESTRATOR.md` com o banner `<!-- compat:`. Release já instalada não é reescrita. A tag `v0.7.0` instalada de novo, em pasta vazia, também ganha o arquivo.
- [x] `hdev check` falha quando o `AGENTS.md` do app liga um `.md` sob `.harnessdev/` que a release pinada não tem.
- [x] `hdev base --plan docs/plan-inf-006-banco.md --marcar` abre a unidade (`open`, id `INF-006`). `hdev fechar` fecha (`closed`) com esse plano.
- [x] `python3 -m unittest discover -s tests -q` sai 0. `bin/hdev check` sai 0. `bin/hdev sync --check` sai 0.
- [x] `VERSION` é `0.7.1` e `CHANGELOG.md` tem `## [0.7.1]`. Sem tag e sem `hdev release` neste repo.

Prova: `work/v071-parada-fix/evidence/aceite.md`.

## Modelo
Um campo, `stop_session`, no `.hdev/state/session.json` (um arquivo por repo). O handoff grava o id da sessão que sai. O Stop passa só se o `session_id` do evento é esse id. Some no primeiro Stop que passou e no `SessionStart` de outro id. `allow_stop: true` sem o id não libera: um booleano não diz quem pode parar, e foi isso que vazou para a sessão nova.

O prompt compat continua montado em `release.install` (`_ensure_prompt`). `hdev pin`, `hdev release` e o `install` com `HDEV_RELEASES_DIR` passam por aí. Pasta que já existe não se mexe. O `hdev check` lê o `AGENTS.md` do app e o perfil que ele inclui com `@.harnessdev/...`.

## Passos
1. Testes da sessão, do prompt, do plano em `docs/` e dos hooks do Codex e do Grok.
2. Código mínimo até os testes passarem.
3. `hdev check` e `hdev sync --check`.
4. Suíte inteira.

## Fora de escopo
- Reescrever `releases/v0.7.0` já instalada. Sem tag. Sem juiz, sem Codex, sem claude real, sem API paga.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`.
- Registro novo de hook. O teto continua 5.
- `hdev base --marcar` neste repo (abriria a unidade no Stop desta sessão).
- `docs/plan-closed-stop.md` e `docs/plan-subtrair.md`.
