# Plano — v2-pr12-improve

Spec: sem spec (pedido fechado do dono: improve só em relatório, linha 12 do desenho da v2; a spec nova não cabe nesta PR)

## Objetivo
O hdev propõe e testa variantes do próprio harness contra os casos de eval, grava relatório e candidatas na biblioteca, e não adota nada. Adotar (compose, branch `improve/*`, trailer `Harness-Edit:`, `hdev improve revert`) fica para a PR13.

## Critério de pronto
- `python3 -m unittest tests.test_improve -q` sai 0.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --dry-run` sai 0, mostra o plano de 3 braços × 3 corridas e não roda nada.
- `bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --runner fake` sai 0, grava `.hdev/runs/improve-*.json` e o relatório `.md`, e põe candidata `source: improve` na biblioteca. `git status --porcelain` e `git diff --stat` antes e depois: `harness/`, `.claude/`, `hooks/`, `hdev/`, `AGENTS.md`, `CLAUDE.md` e `.hdev/config.json` não mudam.
- Com `.hdev/overlays/bad/hooks/_lib.py`, `bin/hdev check` sai 1 e nomeia o caminho; sem o overlay, `bin/hdev check` sai 0.
- `bin/hdev check` sai 0, linha `library` verde, skills 5/5, hooks 5 registros e 3 arquivos, xray abaixo do teto.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-pr12-improve/plan.md --dry-run` sai 0.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr12-improve/evidence/aceite.md`.

## Abordagem
Stdlib. Pacote pequeno `hdev/improve/` (um módulo `probe.py`). Reusa `hdev/eval.py` (clone por braço no `base_sha`, teto de 12, runner `fake`), `hdev/library/reflect.add_items` (validação e dedup da PR11) e o `hdev check`.

Candidata = overlay em `.hdev/overlays/<cand>/` (gitignored), que espelha a raiz do repo, mais a ficha `.hdev/overlays/<cand>.json` (`mark`: `invariante` ou `domínio`, `summary`, `remove`). A ficha fica fora da pasta para não ser copiada no clone. `remove` lista caminhos que a candidata tira; tirar uma peça é candidata válida. No eval, o braço `cand-<id>` lê `.hdev/overlays/<id>/` primeiro e cai em `evals/arms/cand-<id>/` se não houver. O overlay só toca o clone, nunca a árvore de trabalho.

Propose sem modelo: `--cand demo` gera, se faltar, a candidata determinística `demo` (tira `.claude/skills/briefing/references/options.md`, marca `domínio`). A costura para o editor de outro provedor é o parâmetro `editor` de `propose`; nesta PR ele é sempre `None`.

Lista protegida em `harness/protected.txt` (ADR 0013): hooks, `_shared/`, deny list (`hdev/sync.py`, `.claude/settings.json`), tetos (`hdev/check.py`, `hdev/config.py`), juiz, `hdev/improve/`, a própria lista e `.github/CODEOWNERS`. Prefixo por linha. Linha `overlays` nova no `hdev check`: arquivo ou `remove` de overlay que cai num prefixo protegido falha e nomeia o caminho. O probe recusa a mesma candidata antes de rodar.

Probe: braços `plain`, `base` e `cand-<id>` (até 2 candidatas), n ≥ 3 corridas por braço, teto do eval (12). Acima do teto, nada roda. Métricas pela mediana: aceite (taxa de pass), tokens (in+out), segundos e xray. Paradas fora da lista: sem medida no runner fake; o relatório diz isso. Regra: pass da candidata abaixo do base = `perde`; custo pior ≥ 15% = `perde`; custo melhor ≥ 15% sem piora = `ganharia`; senão `empata`; sem corrida dos dois lados = `sem evidência`. Diff > 50% das linhas dos arquivos tocados = alerta. Tudo marcado "não adotado".

Saída: `.hdev/runs/improve-<stamp>.json` e `.md` (o caminho é impresso). Cada candidata com resultado vira lição `source: improve`, `status: candidate`, `generalization: pending` (offline), evidência `{unit, run, delta}`.

Jev não foi chamado. Juiz grok não roda nesta VM.

## Passos
1. ADR 0013 e `harness/protected.txt`.
2. Testes que falham em `tests/test_improve.py`.
3. `hdev/improve/probe.py`, braço do eval lendo `.hdev/overlays/`, linha `overlays` no check, verbo `improve` na CLI.
4. `hdev check`, `hdev sync --check` e a suíte verdes.
5. Corrida real com runner fake no `smoke-init-check`; evidência; `git restore library/`.
6. `hdev fechar --plan work/v2-pr12-improve/plan.md`.

## Testes
- `tests/test_improve.py` — check com overlay protegido e limpo, dry-run, teto, 3 braços × n, veredito, biblioteca, árvore intacta
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Compose, branch `improve/*`, PR, trailer `Harness-Edit:`, `hdev improve revert` (PR13).
- Editor de outro provedor de verdade; braço com claude real. Só runner `fake` ou `--dry-run`.
- Lista do que pode editar no check (só a lista protegida é cobrada).
- Skill nova, hook novo, dependência nova. `VERSION` parado. `releases/v*/` congelado.

## Riscos
- Segundos de parede no runner fake variam; o veredito usa a mediana e pode oscilar. Teste do veredito usa números fixos.
- `docs/progress.md` perto do teto de 2.000.
