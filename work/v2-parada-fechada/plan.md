# Plano — v2-parada-fechada

Spec: sem spec (pedido fechado do dono, incidente de 2026-11-19; a spec nova não cabe nesta PR)

## Objetivo
Unidade aberta não deixa a sessão morrer no vazio. A parada continua só a lista fechada.

## Modelo
Um arquivo, `.hdev/state/unit.json`: `id`, `status` (`open`, `blocked`, `ready-to-publish`, `closed`), `next`, `blocked_on`, `plan`, `brief`, `parked`.

- `hdev base --marcar` abre (`open`) e guarda o primeiro passo do plano.
- `hdev fechar` pass (não o `--dry-run`) fecha (`closed`).
- `hdev resume --blocked-on` marca `blocked`. Com outra unidade no backlog, o Stop manda pegar essa. Sem outra, grava `PAREI: espera …` e a sessão pode acabar.
- PAREI da lista, ou `gate esgotado`, estaciona (`parked`): a sessão acaba e a unidade segue aberta. `hdev resume` tira o estacionamento.
- `stop.standing_ok` no manifesto (ex.: `["publicar"]`) cobre um item da lista. Vira `READY-TO-PUBLISH: <unidade> | <o quê>` em `.hdev/state/ready-to-publish` e o status `ready-to-publish`. Sem a chave, publicar continua parada.
- Sem arquivo, o Stop é o de hoje.

Não rodei `hdev base --marcar` neste repo: a sessão aberta usa o Stop. A transição fica no teste, em pasta temporária.

## Critério de pronto
- `python3 -m unittest tests.test_stop tests.test_hooks tests.test_handoff -q` sai 0. Cobre: unidade aberta com árvore limpa e gate verde bloqueia e cita o próximo passo; PAREI da lista libera; trava esgotada grava `PAREI: gate esgotado (open_unit)`; handoff (`allow_stop`) ainda encerra; sem unidade marcada o Stop segue; `standing_ok` publicar grava `READY-TO-PUBLISH` e não para, e sem a chave publicar para; `--blocked-on` manda pegar a próxima unidade e, sem outra, deixa parar com linha retomável; o texto do handoff leva brief, permissões, estado e o mesmo modelo; `fechar` pass fecha a unidade.
- Num fixture temporário: `echo '{"hook_event_name":"Stop","session_id":"t"}' | python3 harness/hooks/stop_gate.py` sai 2 com o próximo passo se a unidade está aberta, e 0 depois de `hdev resume --reason "2FA" --next "…"`. Os dois saem em `work/v2-parada-fechada/evidence/aceite.md`.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0 e a linha `hooks` mostra 5 registros e 3 arquivos.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-parada-fechada/plan.md --dry-run` sai 0.
- `hdev/__init__.py` declara `VERSION = "0.7.0"` e `CHANGELOG.md` tem `## [0.7.0]`. As checagens do `tag_release` (versão e seção) passam no HEAD. Sem tag e sem `hdev release`.
- [juiz] cada item aponta para um comando e a saída em `work/v2-parada-fechada/evidence/aceite.md` (comandos do aceite, com o HEAD). O dry-run do fechar está em `work/v2-parada-fechada/evidence/fechar-dry-run.md`.

## Abordagem
O Stop novo mora em `stop_gate.py`, depois do gate e do progress, antes do handoff. Exit 2 e o próximo passo no stderr. Na 4ª vez, `PAREI: gate esgotado (open_unit)`. `allow_stop` do handoff continua liberando. `hdev sync` também grava `.codex/hooks.json` e `.grok/hooks/stop.json` no formato da doc oficial (Stop, `type: command`, o mesmo `stop_gate.py`). Sem Antigravity. Sem registro novo no Claude: continuam 5 e 3.

Jev não foi chamado (sem API paga). A base desta branch já é `905244b` (PR #11). Juiz grok não roda nesta VM.

## Passos
1. Testes que falham: unidade aberta, PAREI, trava, handoff, sem unidade, standing_ok, blocked-on, texto do handoff, fechar.
2. Implementar o mínimo até os testes passarem.
3. `hdev check` e `hdev sync --check` verdes.
4. `hdev fechar --plan work/v2-parada-fechada/plan.md --dry-run` na branch da PR.
5. Juiz grok no operator host (não roda nesta VM; sem Codex e sem API paga).

## Testes
- `tests/test_stop.py` — lista, standing_ok, blocked-on, abrir e fechar
- `tests/test_hooks.py` — Stop com unidade aberta, trava, handoff, sem unidade
- `tests/test_handoff.py` — texto da sessão nova
- `tests/test_sync.py` — Stop do Codex e do Grok
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Rodar o juiz grok, o Codex, um claude de verdade ou API paga.
- Mexer em `master` ou fazer merge.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`.
- Reescrever `releases/v*/` já instalado.
- Subir teto de hooks, skills ou subagentes. Sem registro novo.
- Antigravity.
- `hdev base --marcar` neste repo.

## Riscos
- A sessão aberta chama `harness/hooks/stop_gate.py`. O arquivo fica no mesmo caminho. O teste do Stop roda em pasta temporária, com `CLAUDE_PROJECT_DIR` fora deste repo.
- O Grok também lê `.claude/settings.json`. Com o arquivo em `.grok/hooks/`, o Stop pode rodar duas vezes. A trava ainda cai em PAREI; não libera em silêncio.
- `hdev fechar` (PR #11) grava `evals/tasks/<id>/task.json` depois da suíte. O `--dry-run` não grava. Esse arquivo não entra no commit.
