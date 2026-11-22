# ADR 0004 — Teto de 5 skills e review goldfish no fluxo

- Status: aceito (João, 15/11/2026, America/Sao_Paulo: "pode publicar e implementar isso")
- Área: núcleo / skills `revisar-spec`, `revisar-diff`, `planejar`; `hdev check`
- Complementa o teto do PRD e a F2 do harness.

## Decisão
1. O teto de skills do `hdev check` sobe de 3 para 5, para caber no núcleo as skills finas `revisar-spec` e `revisar-diff` além de `planejar` e `hdev`. Description continua ≤ 1.000 caracteres. Skills ligadas à release seguem sem contar no teto do app.
2. O fluxo da peça é: spec curta em `docs/specs/` → review goldfish em outro provedor (`docs/specs/<spec>.review.md`, go/no-go) → plano com TDD → código → review cruzada do diff (`docs/reviews/<tarefa>.md`) → `hdev judge` (gate duro) → até 5 linhas em Lições no `docs/progress.md`.
3. Tarefa trivial pode declarar `sem spec` no plano, com motivo. Não se instala Spec Kit, BMAD, OpenSpec nem o plugin EGM por conta própria; o plugin do [elephant-goldfish-model](https://github.com/google/elephant-goldfish-model) fica só como opcional documentado.

## Consequências
- O núcleo passa a ter 4 skills (teto 5). Apps no canal latest recebem as novas skills no init/re-init; o symlink antigo não se cria sozinho.
- A review não substitui o juiz nem acrescenta subagente no teto da F1: roda em sessão ou CLI de outro provedor, com contexto zero.
