# Plano — autocompact-net

Spec: sem spec (pedido fechado do dono: a compactação nativa não pode disparar antes do handoff; a spec nova não cabe nesta PR)

## Objetivo
O settings gerado leva `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` acima do limiar do handoff, para a compactação nativa do Claude Code não sair na frente, e ainda sair antes da janela encher se o handoff falhar.

## Critério de pronto
- [ ] `python3 -m unittest tests.test_sync.Autocompact -q` sai 0. A suíte cobre a string no settings, o default (limiar em % + 10), a falha no limiar ou abaixo, a falha acima de 95 e a falha quando o settings diverge.
- [ ] `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- [ ] `bin/hdev check` sai 0.
- [ ] `bin/hdev sync --check` sai 0.
- [ ] `bin/hdev base --plan work/autocompact-net/plan.md` sai 0.
- [ ] `bin/hdev base --plan work/autocompact-net/plan.md --marcar` sai 0.
- [ ] `bin/hdev fechar --plan work/autocompact-net/plan.md --dry-run` sai 0.
- [ ] [juiz] cada item aponta para um comando e a saída em `work/autocompact-net/evidence/aceite.md` (comandos do aceite, numa seção só, no HEAD).
  - [ ] `python3 -m unittest tests.test_sync.Autocompact -q` sai 0
  - [ ] `python3 -m unittest discover -s tests -q` sai 0
  - [ ] `bin/hdev check` sai 0
  - [ ] `bin/hdev sync --check` sai 0
  - [ ] `bin/hdev base --plan work/autocompact-net/plan.md` sai 0
  - [ ] `bin/hdev base --plan work/autocompact-net/plan.md --marcar` sai 0
  - [ ] `bin/hdev fechar --plan work/autocompact-net/plan.md --dry-run` sai 0

## Abordagem
`hdev sync` põe o `env` no settings do núcleo. A chave opcional é `handoff.autocompact_pct`. Sem ela, o valor é a porcentagem inteira do `handoff.threshold` (default 0.5) mais 10, hoje 60. Vai como string: o Claude Code copia o `env` como está, e a variável é uma porcentagem (a doc usa `50`). O `hdev check` recusa valor no limiar ou abaixo, ou acima de 95. Settings diferente do manifesto falha em `hdev sync --check`, que o check já chama.

O manifesto deste repo não ganha a chave: 60 é o default. O settings do app continua só com hooks.

## Passos
1. Teste que falha: string no settings, default, cada recusa do check.
2. Implementar o mínimo no sync e no check.
3. `hdev sync` regenera `.claude/settings.json`.
4. `hdev check` verde.

## Testes
- `tests/test_sync.py` — classe `Autocompact`
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Bump de VERSION. A rede entra na próxima release.
- Editar a lógica de sessão em `hdev/handoff.py` ou `harness/hooks/stop_gate.py`.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`.
- Rodar o juiz, o Codex, um claude real ou qualquer API paga.
- Mexer em `master` ou fazer merge. A PR entra em `f2-11-v0.6.0`.
- Copiar o `env` para o settings do app (continua só os hooks).
- `docs/plan-closed-stop.md` e `docs/plan-subtrair.md`.

## Riscos
- O Claude Code ignora valor acima do limiar padrão dele. 60 está abaixo, então a variável vale. 95 é o teto do check para a compactação ainda disparar se o handoff falhar.
- Outra PR aberta mexe na sessão do handoff e no `stop_gate.py`. Esta não toca nesses arquivos.
