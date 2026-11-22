# Evidência — aceite

Comandos no HEAD `7c1be9e696822c22db45a82735e907f2f72d57c2`. Spec, check e sync repetidos no HEAD `eb83b1cc1dc249efd7f6d2d33edb64700e4cb6f4` (mesmo resultado; este arquivo já estava na árvore). A suíte e o fechar rodaram no primeiro HEAD. Este commit só registra a repetição.

## bin/hdev spec check tests/fixtures/spec-ok.md

```
hdev spec check: ok
exit=0
```

## bin/hdev spec check tests/fixtures/spec-sem-defaults.md

```
hdev spec check: falta a tabela dúvida, default, reverter
exit=1
```

## bin/hdev check

exit=0

```
[ok] agents: 39/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json bate com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1953/2000 caracteres
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 94 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto
```

exit=0

## python3 -m unittest discover -s tests -q

stderr: `Ran 406 tests in 98.193s` e `OK`. ELAPSED 98.31. exit=0.

O `ResourceWarning` de `tests/test_naming.py:245` já estava no arquivo (não é desta PR).

## Fora desta página

- `hdev fechar --dry-run`: `work/v2-pr6-skills/evidence/fechar-dry-run.md`
