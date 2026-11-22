# Evidência — aceite

Código no HEAD `2357ee223c6d266906a1018b3a1618a4835d39ca`. A suíte inteira rodou nessa árvore, antes do commit da evidência. Sem `hdev base --marcar` neste repo. Sem tag `v0.7.0` e sem `hdev release`. `releases/` não foi tocado.

## Suíte focada

```
$ python3 -m unittest tests.test_stop tests.test_hooks tests.test_handoff -q
Ran 76 tests in 6.849s
OK
```

exit=0

## Suíte inteira

```
$ python3 -m unittest discover -s tests -q
Ran 460 tests in 115.079s
OK
```

exit=0

## bin/hdev check

exit=0

```
[ok] agents: 40/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1914/2000 caracteres
[ok] xray: estimativa 1745/15000
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 149 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

exit=0

## Hook num fixture temporário

O cwd é o fixture. `CLAUDE_PROJECT_DIR` não aponta para este repo. Unidade `alfa` aberta, próximo `escrever o teste`.

```
$ echo '{"hook_event_name":"Stop","session_id":"t"}' | python3 harness/hooks/stop_gate.py
unidade alfa aberta. Próximo: escrever o teste
```

exit=2

```
$ bin/hdev resume --root <fixture> --reason "2FA" --next "seguir o plano"
{"ok": true, "parou": true, "parei": "PAREI: 2FA | próximo: seguir o plano", "proximo": "seguir o plano"}
```

exit=0

```
$ echo '{"hook_event_name":"Stop","session_id":"t"}' | python3 harness/hooks/stop_gate.py
```

exit=0

## Versão 0.7.0

`git show HEAD:hdev/__init__.py` contém `VERSION = "0.7.0"`. `check_core_changelog` na `v0.7.0` não levantou erro. A tag `v0.7.0` não existe neste repo.

## App da v0.6.0 para a v0.7.0

Núcleo temporário (clone local), tags só lá: `v0.6.0` em `02c8720`, `v0.7.0` em `e2f9c0e`. App criado com o `hdev init` da v0.6.0.

- settings do app: 7 hooks (`secret_guard.py` em `.harnessdev/hooks/`). Sem `.codex/hooks.json`.
- `hdev pin v0.7.0`: `fixado em v0.7.0 (e2f9c0e4e50d)`.
- `hdev check` antes do sync: exit=1. `hooks: 7 hooks registrados (tem que ser 5)`. Também `chave antiga tests`.
- `hdev sync`: exit=0. Imprime `config: tests virou gates`.
- settings depois: 5 hooks. `.codex/hooks.json` e `.grok/hooks/stop.json` iguais, comando `python3 "$(git rev-parse --show-toplevel)/.harnessdev/harness/hooks/stop_gate.py"`.
- `hdev check` depois: exit=0. Linha `hooks: 5 registros, 3 arquivos`.

O que o app roda depois do pin: `hdev sync`. Isso acerta os registros, o Stop do Codex e do Grok, e a chave `tests`.
