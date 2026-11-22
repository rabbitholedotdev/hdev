# Evidência — aceite

Uma seção. Corridas anteriores (pai `c6baa68`, workspace com `bases.json`) foram retiradas: não contam.

Clone limpo do HEAD, detached, sem `bases.json`:

```
git clone -q . /tmp/c
git -C /tmp/c checkout -q --detach HEAD
```

Os comandos rodaram nesse clone, nesta ordem. `bin/hdev check` saiu antes de `--marcar`. Juiz, Codex, claude real e API paga não rodaram.

## python3 -m unittest tests.test_sync.Autocompact -q

exit=0. 6 testes em 0.595s.

```
----------------------------------------------------------------------
Ran 6 tests in 0.595s

OK
```

## python3 -m unittest discover -s tests -q

exit=0. 520 testes em 130.381s.

```
hdev: devolvido ao repo (não commitado): a.txt.hdev-isolado
hdev: o repo mudou nestes enquanto o revisor rodava; a versão dele ficou em <arquivo>.hdev-isolado: a.txt
hdev: devolvido ao repo (não commitado): a.txt.hdev-isolado
hdev: o repo mudou nestes enquanto o revisor rodava; a versão dele ficou em <arquivo>.hdev-isolado: a.txt
hdev: devolvido ao repo (não commitado): docs/reviews/r.md
hdev: devolução recusada (fora do repo): docs/reviews/r.md
----------------------------------------------------------------------
Ran 520 tests in 130.381s

OK
```

O `ResourceWarning` de `tests/test_naming.py` também saiu (arquivo temporário com caminho do clone). A contagem é a de cima.

## bin/hdev check

exit=0. Sem `bases.json`. A linha `library` passa. O autocompact está no check `config`.

```
[ok] agents: 42/60 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py); aliases: destructive_guard.py, gate_tests.py, handoff_guard.py, progress_guard.py, secret_guard.py
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json, Codex e Grok batem com o manifesto
[ok] prompts: 4 papéis, lista única
[ok] progress: 1145/2000 caracteres
[ok] xray: estimativa 1872/15000
[ok] graph: só o explorer; query, path, explain
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 227 segmentos novos, 0 não-ASCII, 0 avisos, branch: detached
```

## bin/hdev sync --check

exit=0.

```
hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também
```

## bin/hdev base --plan work/autocompact-net/plan.md

exit=0. Sem `--marcar`.

```
autocompact-net: base c6baa68b071d (deduzida: pai de 944379a462f2, o primeiro commit com um doc da unidade)
```

## bin/hdev base --plan work/autocompact-net/plan.md --marcar

exit=0. No clone limpo não havia base gravada, então deduz `c6baa68` e grava em `.hdev/state/bases.json` (gitignored). Rodou depois do `check`.

```
hdev base: autocompact-net -> c6baa68b071d gravada em .hdev/state/bases.json
```

## bin/hdev fechar --plan work/autocompact-net/plan.md --dry-run

exit=0. Branch detached não é `f2-11-v0.6.0`, então o marco não nasce. O nome do JSON em `.hdev/runs/` leva o relógio dessa corrida.

```
hdev fechar: commit do marco pulado (branch HEAD não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261120T055408670241Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_fechar.py tests/test_hooks.py tests/test_judge.py tests/test_release_ship.py tests/test_spec.py tests/test_wrappers.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_gates_full.py tests/test_init.py tests/test_library.py tests/test_run_grok.py tests/test_stop.py tests/test_xray.py
  shard 2: tests/test_channel.py tests/test_eval.py tests/test_graph.py tests/test_isolar.py tests/test_naming.py tests/test_skills.py tests/test_sync.py
  shard 3: tests/test_check.py tests/test_evals.py tests/test_handoff.py tests/test_jev.py tests/test_prompts.py tests/test_smoke.py tests/test_triage.py
cache: miss
  reflita: hdev reflect --unit autocompact-net
```
