# Evidência — aceite

Comandos na branch `cursor/v2-pr4-prompts-2dad`, HEAD `864e1f60132e519dbfbd5cae0bb56d33b45a1008`.

## grep, wc, ls

```
$ test $(grep -rl 'stop-list.md' harness/prompts | wc -l) -ge 4
harness/prompts/reviewer.md
harness/prompts/orchestrator.md
harness/prompts/implementer.md
harness/prompts/executor.md
exit=0

$ test $(wc -l < AGENTS.md) -le 60
35
exit=0

$ test $(ls PROMPT-*.md 2>/dev/null | wc -l) -eq 0
exit=0
```

## python3 -m unittest discover -s tests -q

stdout do medidor: `ELAPSED 94.45`. stderr do unittest: `Ran 381 tests in 94.347s` e `OK`. exit=0.

## bin/hdev check

exit=0

```
[ok] agents: 35/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 7 registrados, com arquivo e teste
[ok] skills: 5/5
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json bate com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1970/2000 caracteres
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base d308a02 (bases.json v2-pr4-prompts), mode fail, 14 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto
```

exit=0
