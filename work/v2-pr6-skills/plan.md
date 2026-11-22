# Plano — v2-pr6-skills

Spec: sem spec (pedido fechado do dono: skills finas e o verbo `hdev spec check`; a spec nova não cabe nesta PR)

## Objetivo
Cada skill do núcleo fica fina, e `hdev spec check` confere a spec da unidade.

## Critério de pronto
- `bin/hdev spec check tests/fixtures/spec-ok.md` sai 0.
- `bin/hdev spec check tests/fixtures/spec-sem-defaults.md` sai 1.
- `bin/hdev check` sai 0 e a linha `skills` mostra visíveis por fase ≤ 5 e descriptions ≤ 200.
- `bin/hdev sync --check` sai 0.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev fechar --plan work/v2-pr6-skills/plan.md --dry-run` na branch da PR sai 0 e diz que o commit do marco foi pulado.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr6-skills/evidence/aceite.md` (comandos do aceite, com o HEAD). O dry-run do fechar está em `work/v2-pr6-skills/evidence/fechar-dry-run.md`.
  - spec ok: `bin/hdev spec check tests/fixtures/spec-ok.md` sai 0
  - spec sem a tabela: `bin/hdev spec check tests/fixtures/spec-sem-defaults.md` sai 1
  - portão: `bin/hdev check` sai 0; a linha `skills` tem F0, F1 e F2 com no máximo 5 e `descriptions <= 200`
  - manifesto: `bin/hdev sync --check` sai 0
  - suíte: `python3 -m unittest discover -s tests -q` sai 0
  - fechar: o dry-run imprime `commit do marco pulado`

## Abordagem
O teto de 5 passa a ser o que a fase mostra (`skillOverrides`), não o total no disco. Description desce para 200. O check do núcleo exige Fora de escopo (com «não confundir com»), `references/` e um caso em `evals/skills/`. F0 fica com `hdev`. F1 fica com `hdev`, `briefing`, `spec`, `revisar-spec` e `planejar`. F2 fica com `hdev`, `handoff`, `planejar`, `revisar-spec` e `revisar-diff`. O brainstorm do rabbitOS entra adaptado na seção Opções do brief, sem copiar o repo. Jev sem chave (exit 2): segui sem worker.

## Passos
1. Testes que falham: spec ok sai 0, spec sem defaults sai 1, default vazio sai 3, uso sai 2, fase com 6 falha, skill do núcleo sem Fora de escopo falha, cada skill tem um caso.
2. Implementar o mínimo para os testes passarem.
3. `hdev check` e `hdev sync --check` verdes.
4. `hdev fechar --plan work/v2-pr6-skills/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
5. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_spec.py` — exit 0, 1, 2 e 3
- `tests/test_skills.py` — formato fino no núcleo e um caso por skill
- `tests/test_check.py` — fase com 6 falha; 6 no disco passa; description de 201 falha
- `tests/test_sync.py` — fase com 6 recusa o sync; no repo, briefing e spec ficam off na F2
- `tests/test_base.py` — `work/<id>/spec.md` entra na unidade
- `tests/test_init.py` e `tests/test_app.py` — links novos e a linha de skills

## Fora de escopo
- Apagar os aliases em `hooks/`. Fica para outra PR.
- Reescrever `releases/v*/` já instalado.
- Subir teto de hooks ou de subagentes. O número de skills visíveis continua 5.
- O runner de `evals/` (é a PR 9). Aqui só o caso e o teste de que ele existe.
- Rodar o juiz grok ou o fallback Codex.
- Mexer em `master` ou fazer merge.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`.

## Riscos
- A sessão aberta lê `.claude/settings.json` e os hooks no caminho atual. `hdev sync` reescreve o settings no lugar; os scripts de hook não se movem.
- App ligado não herda `skills` do manifesto (chave de repo). O check do app continua na description e, se ele declarar fases, no teto de 5. O formato fino vale no núcleo.
