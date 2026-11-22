# ADR 0008 — Base do diff por unidade

- Status: aceito
- Data: 2026-11-15

## Contexto

O `hdev judge` montava o diff contra `HEAD` (`hdev/judge.py:91`, `_diff_args`: `[base or "HEAD"]`). Numa área do host, o gancho `commit-turno` commita no fim de cada turno o que mudou (mensagem = 1ª linha do pedido, ex.: "Base directory for this skill…"). Parte da peça já está em commits quando o juiz roda, e ele só vê o resto. Num consumer app, um commit-turno levou metade de um teste; o juiz disse que o módulo não testava `/saude` nem a migração quebrada e deu `fail` duas vezes. A skill `revisar-diff` (e o state do `hdev jev revisar-diff`) dependia do mesmo `git diff` sem base.

## Decisão

- Módulo `hdev/base.py` e comando `hdev base --plan P [--marcar [REF]] [--force] [--sha|--json]`.
- Ordem da base: `--base` explícita → gravada em `.hdev/state/bases.json` (por unidade, ex.: `INF-006`) → deduzida → `HEAD`.
- Dedução pelos docs da unidade (plano, `docs/specs/<ID>-*.md`, review): doc commitado → pai do primeiro commit que o trouxe, ou o último commit antes do doc mais antigo (mtime), o que for mais antigo; docs só na árvore → o último commit que fechou um item no backlog (`docs/backlog.md`/`docs/tasks.md`: `| feito |`, `[x]`, "feito e fechado") antes deles, senão o último commit antes deles.
- Diff = base..árvore de trabalho + não rastreados. O pacote ganha `=== BASE DO DIFF` (SHA e fonte) e `=== COMMIT` com `base..HEAD`; a saída do juiz imprime `base do diff:`; o registro em `.hdev/runs/` leva `base_sha`, `base_fonte` e `unidade`.
- O primeiro `hdev judge` real da unidade grava a base deduzida: commits-turno seguintes não a movem. `--dry-run` não grava.
- Skills: `planejar` marca a base ao gravar o plano; `revisar-diff` usa `git diff $(hdev base --plan P --sha)`.
- Nada no core da Ratoeira muda (o `commit-turno` fica como está). Só stdlib (ADR 0001).

## Consequências

- O diff pode trazer mudanças de outra peça que estejam na mesma árvore; o juiz as aponta como "fora do critério". Base errada se corrige com `--base` ou `hdev base --marcar REF --force`.
- `--head` continua exigindo `--base` (intervalo fechado, usado nas releases do núcleo).
- Rollback: `hdev rollback --to v0.3.8`.
