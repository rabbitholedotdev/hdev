# Comandos

Leia só no passo que for usar o verbo.

- Worktree: `hdev wt add <branch> --repo <repo>` em `<área>/_wt/<repo>-<branch>`. Antiga: `hdev wt move <pasta>`.
- Peça: `hdev triage`, skill `briefing`, skill `spec`, `hdev spec check work/<id>/spec.md`, skill `revisar-spec`, skill `planejar`, skill `revisar-diff`.
- Biblioteca: `hdev library pull --spec work/<id>/spec.md` depois da spec aprovada. Brief pede `--tag pergunta`. `hdev library pull --symptom "<texto>"` antes de diagnosticar falha. `hdev reflect --unit <id>` depois do fechar. `hdev library status` e `hdev library tidy`.
- Improve: `hdev improve probe --case <id> --cand demo --runs 3 --runner fake` testa candidata de `.hdev/overlays/<id>/` e só relata; não adota. `--dry-run` mostra o plano.
- Juiz: `hdev judge --plan work/<id>/plan.md --run-tests`. A base é `hdev base --plan P`. Fechar: `hdev fechar --plan P [--dry-run] [--no-cache]`. A suíte `gates.full` roda num clone limpo do HEAD, em shards, com cache por tree sha.
- Eval: `hdev eval run --case <id> --arms plain,base --runs N [--runner auto|claude|fake|none] [--dry-run]`. Xray: `hdev xray [--max N] [--json]`.
- Cache de código: `hdev graph update` (sob demanda; o hook de git faz o mesmo). `hdev impact <arquivo>` lista quem chama ou importa e o que o arquivo chama ou importa. Sem o cache, os dois avisam e `scripts/affected-tests` usa `tests/test_<módulo>*.py`; se não houver, a suíte `tests/test_*.py`.
- App: `hdev app new <nome> --area .` e `hdev app check apps/<nome>`. Tag só depois de publicado.
- Jev: `hdev jev rotear|revisar-diff|humano|handoff`. Wrappers: `hdev codex-exec`, `hdev grok-review`.
- Handoff: skill `handoff` e `hdev handoff` (a sessão nova leva plano, brief, permissão de pé, estado e o mesmo modelo). Retomada: `hdev resume` e `hdev resume --blocked-on "<dependência>" --next "…"`.
- Versão: `hdev pin vX.Y.Z` fixa; `hdev pin --latest` volta ao canal. Release e rollback são do núcleo.

Hooks: 3 arquivos em `harness/hooks/` e 5 registros. `hooks/*.py` é alias. Skills visíveis por fase: no máximo 5.
