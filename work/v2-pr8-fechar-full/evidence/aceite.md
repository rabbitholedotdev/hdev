# Evidência — aceite

O fechar duas vezes está em `work/v2-pr8-fechar-full/evidence/fechar-real.md`, no HEAD `59860342390f0045013de42f948ddbe4bdce1d8b` (tree `8c4965662f28375c6e1411bd4237df48f4cceee7`). Os comandos abaixo rodaram no HEAD `c8ef21bf74d0fd8c66a0b37115dc8c8e7ee6ebeb`, que já tinha os caminhos desta pasta. Este commit só preenche o texto. O juiz grok e o Codex não rodaram.

## bin/hdev fechar --plan work/_example/plan.md --dry-run

exit=0. Mostra `gates.full`, o corte em 4 shards e `cache: miss` (o tree deste HEAD não é o do fechar real). Não rodou a suíte.

```
hdev fechar: commit do marco pulado (branch cursor/v2-pr8-fechar-full-eee7 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T233837908726Z.json
gates.full: python3 -m unittest discover -s tests -v
shards: 4
  shard 0: tests/test_app.py tests/test_ci.py tests/test_gates_full.py tests/test_isolar.py tests/test_prompts.py tests/test_spec.py tests/test_wrappers.py
  shard 1: tests/test_base.py tests/test_cli_runtime.py tests/test_handoff.py tests/test_jev.py tests/test_run_grok.py tests/test_stop.py
  shard 2: tests/test_channel.py tests/test_evals.py tests/test_hooks.py tests/test_judge.py tests/test_skills.py tests/test_sync.py
  shard 3: tests/test_check.py tests/test_fechar.py tests/test_init.py tests/test_naming.py tests/test_smoke.py tests/test_triage.py
cache: miss
```

ELAPSED 0.09.

## python3 -m unittest tests.test_gates_full -q

stderr: `Ran 10 tests in 3.513s` e `OK`. ELAPSED 3.56. exit=0.

Cobre clone limpo (sujeira e não rastreado ficam de fora), corte em que cada módulo entra uma vez, falha de um shard com o nome do teste, cache na mesma árvore, erro de cache quando mudam árvore, comando ou shards, falha, timeout e erro sem cache, `--no-cache` e o formato do trailer.

## python3 -m unittest discover -s tests -q

stderr: `Ran 424 tests in 108.625s` e `OK`. ELAPSED 108.73. exit=0.

O `ResourceWarning` de `tests/test_naming.py:245` já estava no arquivo. As linhas `hdev: devolvido ao repo` são o teste do isolador, não falha.

Parede do fechar com shards, no HEAD anterior: 67.5s (424 testes, 4 shards). Este discover em série: 108.6s. A soma dos relógios dos shards foi 189.7s (cada um clona o repo e os quatro disputam os núcleos).

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
[ok] progress: 1941/2000 caracteres
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base 77fbd1d (fechamento), mode fail, 121 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev sync --check

```
hdev sync: settings.json bate com o manifesto
```

exit=0
