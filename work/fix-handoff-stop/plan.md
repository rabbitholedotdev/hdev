# Plano — fix-handoff-stop

Spec: sem spec (correção pedida pelo dono, 20/11: o nudge de handoff segura o Stop para sempre em corrida headless)

## Objetivo
O nudge de handoff no Stop bloqueia uma vez por fim de turno, não para sempre. Hoje `hdev/handoff.py` `hook_decide` devolve `decision: block` em todo Stop acima do limiar (janela 200k, limiar 0.5), ignora `stop_hook_active` e bloqueia mesmo com a unidade fechada. Numa sessão SampleApp do VM isso deu "A hook blocked the turn from ending 9 consecutive times" (20/11 03:11).

## Critério de pronto
- `python3 -m unittest tests.test_handoff -q` sai 0. Os dois testes novos (`test_stop_hook_active_nao_bloqueia_de_novo`, `test_stop_com_unidade_fechada_nao_bloqueia`) falham sem a mudança em `hdev/handoff.py`.
- Stop acima do limiar com `stop_hook_active: true` não bloqueia (saída `None`). O primeiro Stop, sem a chave, continua bloqueando.
- Stop acima do limiar com `.hdev/state/unit.json` em `closed` não bloqueia. Com a unidade `open`, bloqueia. Fora do Stop, o aviso de handoff (`additionalContext`) continua.
- `HDEV_HANDOFF_THRESHOLD=0.95 HDEV_HANDOFF_WINDOW=1000000 python3 -m unittest tests.test_handoff tests.test_isolar -q` sai 0: o `clean_env` dos testes não deixa `HDEV_HANDOFF_*` de fora ganhar do config do teste.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/fix-handoff-stop/plan.md --dry-run` sai 0.
- [juiz] cada item aponta para um comando e a saída em `work/fix-handoff-stop/evidence/aceite.md`.

## Abordagem
Uma condição em `hook_decide`, depois da permissão do handoff (que continua sendo gasta primeiro): Stop com `stop_hook_active` (ou `stopHookActive`) ou com a unidade fechada devolve `None`. A unidade é lida por `hdev/unit.py` (`load`, `CLOSED`), sem import circular. Só `closed` libera; `open`, `blocked` e `ready-to-publish` seguem como antes. `tests/helpers.py` `clean_env` tira `HDEV_HANDOFF_*` do ambiente herdado; quem passa a variável em `extra` continua passando.

## Passos
1. Testes que falham em `tests/test_handoff.py`.
2. A condição em `hdev/handoff.py` e o `clean_env`.
3. Suíte, `hdev check` e `hdev sync --check` verdes.
4. Evidência e `hdev fechar --plan work/fix-handoff-stop/plan.md`.

## Testes
- `tests/test_handoff.py`: dois casos novos, em processo, com o config passado explícito (não depende do ambiente).
- A suíte inteira com e sem `HDEV_HANDOFF_THRESHOLD=0.95 HDEV_HANDOFF_WINDOW=1000000`.

## Fora de escopo
- Janela padrão de 200k contra a janela real do modelo (o log do PR12 mostra `contextWindow` 1000000 no `claude-opus-5-5`).
- O gate `open_unit` do `stop_gate.py`, que já tem a trava de quatro vezes.
- Releases instaladas (`releases/v*/`, `/opt/harness-dev/releases`): a correção chega aos apps na próxima release.

## Riscos
- Sessão interativa acima do limiar recebe o nudge uma vez por turno, não mais em laço. É o comportamento pedido.
