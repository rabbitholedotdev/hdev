# Plano — handoff-window-by-model

Spec: sem spec (correção pedida pelo dono, 20/11: o nudge de handoff mede contra 200k, e o `claude-opus-5-5` tem janela de 1M)

## Objetivo
O nudge de handoff mede o uso contra a janela do modelo da sessão. Hoje `hdev/handoff.py` divide pelo `handoff.window_tokens` (200000 em `.hdev/config.json`), mas o `claude-opus-5-5` tem `contextWindow` 1000000 (linha `result` de `~/.local/state/ratoeira/crons/hdev-v2-pr12-improve.log` no VM). Com limiar 0.5, o nudge sai aos 100k, 10% da janela real: o `.hdev/state/session.json` do worktree do PR12 tem `usage_ratio` 0.762 com 152439 tokens.

## Critério de pronto
- `python3 -m unittest tests.test_handoff -q` sai 0. Os dois testes novos (`test_janela_por_modelo`, `test_env_janela_ganha_do_mapa`) falham sem a mudança em `hdev/handoff.py`.
- Com `handoff.window_by_model` `{"claude-opus-5-5": 1000}` e `window_tokens` 200, um transcript do opus com 400 tokens não orienta e com 500 orienta. Um modelo fora do mapa usa `window_tokens`.
- `HDEV_HANDOFF_WINDOW` no ambiente ganha do mapa: a janela do env vale para todos os modelos.
- `.hdev/config.json` leva `handoff.window_by_model` `{"claude-opus-5-5": 1000000}`. `window_tokens` 200000 fica como reserva.
- Com o config do núcleo, o transcript real da corrida do PR13 no VM (`afcec51f…jsonl`, `claude-opus-5-5`, 134558 tokens) dá razão 0.135 em `window_for`, não 0.673 (janela 200000).
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0. O settings gerado não muda: `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` continua "60".
- `bin/hdev fechar --plan work/handoff-window-by-model/plan.md --dry-run` sai 0.
- [juiz] cada item aponta para um comando e a saída em `work/handoff-window-by-model/evidence/aceite.md`.

## Abordagem
`settings()` devolve `window_by_model` (modelo → tokens) de `handoff.window_by_model`. Com `HDEV_HANDOFF_WINDOW` no ambiente, o mapa fica vazio e a janela do env vale para todos. `hook_decide` só lê o modelo do transcript (`model_from_transcript`) quando há uso e o mapa não está vazio. A janela vem de `window_for(cfg, modelo)`: a do mapa, senão `window_tokens`. Modelo desconhecido ou `<synthetic>` cai em `window_tokens`, então o nudge sai cedo, nunca tarde. Ler a janela em tempo de execução não dá: o transcript e a entrada dos hooks não trazem a janela, e `contextWindow` só aparece no `result` final do `claude -p`.

## Passos
1. Testes que falham em `tests/test_handoff.py`.
2. `window_by_model` em `settings()`, `window_for` e a janela em `hook_decide`.
3. `handoff.window_by_model` no `.hdev/config.json` do núcleo.
4. Suíte, `hdev check` e `hdev sync --check` verdes.
5. Evidência e `hdev fechar --plan work/handoff-window-by-model/plan.md`.

## Testes
- `tests/test_handoff.py`: dois casos novos, em processo, com o ambiente limpo por `clean_env` (não dependem de `HDEV_HANDOFF_*` de fora).
- A suíte inteira com e sem `HDEV_HANDOFF_THRESHOLD=0.95 HDEV_HANDOFF_WINDOW=1000000`.

## Fora de escopo
- `hdev/sync.py` e o `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. O Claude Code aplica a porcentagem sobre a janela dele, limitada à do modelo. Com a janela certa no handoff, limiar em % + 10 fica coerente: no opus, nudge aos 500k e compactação perto de 600k.
- Apps com `handoff.window_tokens` próprio ou sem bloco `handoff` (consumer apps pinned to an older window): seguem em 200k até a release nova e o config de cada um.
- Janela pela status line (`context_window.context_window_size`).
- Janela do `claude-sonnet-5-5`: a confirmar. Fica fora do mapa (reserva 200k).
- Releases instaladas (`releases/v*/`, `/opt/harness-dev/releases`).

## Riscos
- Uma janela no mapa maior que a real faz o nudge sair tarde, e a compactação nativa sai antes. Só entra no mapa a janela vista num `result` do `claude -p` (`modelUsage.<modelo>.contextWindow`).
- Com o mapa, o hook lê o transcript duas vezes (uso e modelo).
