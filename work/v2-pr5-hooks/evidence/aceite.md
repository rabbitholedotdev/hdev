# Evidência — aceite

Comandos no HEAD `ed1013bdd5c2050f3d02dd76d20907bfdce6d98a`. Repetidos no HEAD `05d745b57cc255cb8a1ebfc04f843c98af970a40` (mesmo código, com esta evidência): suíte `Ran 389 tests in 95.759s` OK; hooks `Ran 46 tests in 5.383s` OK; check, sync e fechar saíram 0.

## Pergunta na execução

```
$ echo '{"tool_name":"AskUserQuestion"}' | HDEV_PHASE=exec python3 harness/hooks/pre_tool.py; test $? -eq 2
pre_tool: AskUserQuestion na execução. Não pergunte. Escolha o padrão em docs/padroes/defaults.md, anote em docs/decisions.md e siga. Parada só em harness/prompts/_shared/stop-list.md.
exit=0
```

O `pre_tool.py` sai 2. O `test` sai 0.

## python3 -m unittest tests.test_hooks -q

stderr: `Ran 46 tests in 5.846s` e `OK`. ELAPSED 5.91. exit=0.

## python3 -m unittest discover -s tests -q

stderr: `Ran 389 tests in 95.717s` e `OK`. ELAPSED 95.84. exit=0.

O `ResourceWarning` de `tests/test_naming.py:245` já estava no arquivo (não é desta PR).

## bin/hdev check

exit=0

```
[ok] agents: 36/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: 5/5
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json bate com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1986/2000 caracteres
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 55 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto
```

exit=0

## Fora desta página

- Colisão: `work/v2-pr5-hooks/evidence/collision.md`
- Comando que falhou duas vezes: `work/v2-pr5-hooks/evidence/falha-seguida.md`
- Corte de saída: `work/v2-pr5-hooks/evidence/corte.md`
- `hdev fechar --dry-run`: `work/v2-pr5-hooks/evidence/fechar-dry-run.md`
