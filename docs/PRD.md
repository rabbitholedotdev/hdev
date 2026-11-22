# PRD — Harness Dev (v0.7)

Este arquivo é a versão textual da Page v0.7, para a sessão overnight. A Page canônica é:
(internal canvas; omitted from the public tree)

O prompt de execução está em `harness/prompts/executor.md` (o orquestrador em `harness/prompts/orchestrator.md`). As tarefas estão em `work/backlog.md`.

## O que mudou na v0.7 (14/11/2026, America/Sao_Paulo)

- Local canônico na Ratoeira: `$HDEV_ROOT` (área developer). Worktrees: `$HDEV_ROOT-codex` e, se houver, `harness-dev-cursor`. Não mora em `~/code` nem dentro de `apps/`. Há um symlink de compatibilidade em `~/code/harness-dev`.
- Consumo pela raiz de qualquer projeto: `.harnessdev` (symlink para uma release `vX.Y.Z`) e `.harnessdev.lock` (versão fixada, versionado no app). O `hdev init` cria os dois. Nada do núcleo cresce na pasta do app. Ver ADR 0002.


## O que veio da v0.6


Este arquivo é a versão textual da Page v0.6, para a sessão overnight. A Page canônica é:
(internal canvas; omitted from the public tree)

O prompt de execução está em `harness/prompts/executor.md` (o orquestrador em `harness/prompts/orchestrator.md`). As tarefas estão em `work/backlog.md`.

## O que mudou na v0.6 (14/11/2026, America/Sao_Paulo)

- F1-02: o `hdev judge` liga de verdade ao Grok (modelo `grok-4.7`) pela CLI `grok`, por assinatura grok.com (já logada na Ratoeira e no Mac). Veredito em JSON, juiz de outro provedor, teste com fixture, juiz consultivo até cerca de 20 casos rotulados. Fallback: Codex. O `agy` hoje não oferece Grok. Sem chave de API paga.
- Execução barata: `grok-4.7-build-fast` para exploração e resumo. Não substitui a sessão principal do Claude no MVP, nem o juiz.
- F1-03 (João 14/11: cursor → grok; tarefa isolada pelo `grok` CLI da Ratoeira, `docs/plan-f1-ci-grok.md`): piloto Cursor, tarefa isolada com começo e fim — CI (lint, testes e `hdev check`) num worktree/PR pequeno. Prefere-se o Cursor CLI na própria Ratoeira, sem push e sem GitHub, se a CLI estiver instalada e logada. Alternativa (decisão do João): repo PRIVADO no GitHub. Não criar remoto nem fazer push sem essa decisão.
- A v0.5 permanece como base (consulta de 12 modelos, tudo por assinatura, sem fine-tuning agora).

## O que mudou na v0.5 (veredito de 12 modelos, 14/11/2026)

- Fine-tuning fica fora até depois da F2. Só reabre com falha medida que resistir a prompt e skill, via ADR que reabra a D4.
- Sem pasta `agents/` na raiz. Planejar é skill em `.claude/skills/planejar/`. Implementador é a sessão principal. Nenhum subagente em F0/F1. Se na F2 um reviewer só de leitura se justificar, mora em `.claude/agents/` e não substitui o juiz de outro provedor. Teto: no máximo 1 subagente.
- Sem orquestrador próprio. Contratos no núcleo; orquestração nas CLIs; `hdev judge` é a única cola entre provedores.
- Revisão multi-CLI restrita a PRD e ADR.
- F1 já inclui `hdev init` + uma tarefa real num repo externo mínimo (irmão, não um app).
- `hdev check` valida o provedor do modelo do juiz, não só o nome da CLI.

## Resumo

1. Repo `harness-dev`, CLI `hdev` com `check`, `init` (cópia simples) e `judge`. Versão por tag git. Sem `sync` e sem lockfile no MVP.
2. Um perfil no MVP: `harness-developer`. Planejar é skill. Implementador é a sessão principal do Claude Code. Sem `agents/` na raiz e sem subagente em F0/F1.
3. Tudo roda nas CLIs de assinatura (`claude`, `codex`, `grok` e, no Mac, `agy`). Sem chave de API paga e sem teto em dólar.
4. Na F1 o juiz preferencial é o Grok (`grok-4.7` via CLI `grok`); o fallback é o Codex. Execução barata pode usar `grok-4.7-build-fast`.
5. O Cursor entra só em tarefas isoladas (F1-03: CI com lint, testes e `hdev check`), com começo e fim claros. Não é o implementador overnight. Sem push até o João decidir um remoto.
6. Observabilidade mede consumo para comparar modelos; não é freio de custo.

## Papéis

- Planejar: skill em `.claude/skills/planejar/`, produz `docs/plan-<tarefa>.md` a partir de spec em `docs/specs/` com review go (ou `sem spec` trivial), com TDD. Review da spec: skill `revisar-spec`. Review do diff: skill `revisar-diff`. Juiz (`hdev judge`) continua o gate duro.
- Implementador: sessão principal do Claude Code (é ali que os hooks rodam: 3 arquivos, 5 registros, ADR 0012).
- Juiz: `hdev judge` no Grok (`grok-4.7`); fallback no Codex. Veredito em JSON (`pass` / `fail` / `não sei`). Consultivo até ~20 casos.
- Execução barata: Grok `grok-4.7-build-fast` para exploração e resumo.
- Tarefa isolada na nuvem ou no CLI local: Cursor, PR/worktree pequeno, depois da F1-03.

## Núcleo

Comandos no MVP: `hdev check`, `hdev init`, `hdev judge`. Um modelo por papel em `.hdev/config.json`. O juiz não usa o mesmo provedor de quem executou.

Tetos do `hdev check`: AGENTS.md ≤ 60 linhas (overlay ≤ 30, no máximo 1 skill); 5 registros de hook e 3 arquivos (ADR 0012); skills visíveis por fase ≤ 5 (description ≤ 200; no disco podem ser mais); subagentes ≤ 2 na F2.

## Fases

- F0: repo, AGENTS.md, tetos, 4 hooks com teste, skill brainstorm (depois renomeada para planejar), `hdev check/init/judge` e um caso de fumaça. Pronto quando `hdev check` e os testes mecânicos ficam verdes.
- F1: peça real de ponta a ponta; `hdev init` + tarefa real num repo irmão mínimo; adaptador Grok do juiz; piloto Cursor de CI. O piloto Cursor pode ficar pendente se a CLI ou o remoto não estiverem prontos. O João confirma a release.
- F2: suíte de evals. Juiz consultivo até ~20 casos rotulados.

## Decisões

- D1–D5: como na v0.5 (repo e CLI, F0/F1, um modelo por papel, tudo por assinatura, fine-tuning fora).
- D6 (João aprovou em 14/11/2026): juiz Grok por assinatura, fallback Codex, execução barata no `grok-4.7-build-fast`.
- D7 (pendente do João se for preciso GitHub): repo privado no GitHub só se o piloto Cursor não puder rodar localmente na Ratoeira. Não criar nem fazer push sem essa decisão.

## Skills finas (v2, 19/11/2026)

O fluxo da peça é triage, briefing (`work/<id>/brief.md`, com a seção Opções na mesma sessão), spec (`work/<id>/spec.md`, `hdev spec check`), review limpa (`revisar-spec`, `work/<id>/review.md`, zero Blocker), plano e review do diff. Cada skill do núcleo tem description de até 200 caracteres, seção Fora de escopo, detalhe em `references/` e um caso em `evals/skills/`. Visíveis por fase: no máximo 5 (`skillOverrides`). `releases/v*/` já instalado não muda. O `hdev` continua ferramenta de desenvolvimento.

## Fechar e a suíte (v2, 19/11/2026)

Sem runner do GitHub e sem Actions. O verde local é o `hdev fechar`. Ele roda `gates.full` num clone limpo do HEAD, em shards (`gates.shards`, padrão min(núcleos, 4)), e guarda o pass em cache por tree sha. Falha, timeout e erro não entram no cache. Na branch base o marco leva o trailer `Hdev-Gates-Full:`. Fora da base a mesma linha vai no veredito e o commit não nasce. `releases/v*/` já instalado não muda.

## Evals e xray (v2, 19/11/2026)

O caso replayável mora em `evals/tasks/<id>/task.json` (`repo`, `base_sha`, prompt e spec opcionais, aceite e tetos). `hdev eval run` clona esse sha, uma vez por braço e corrida, e não mexe na árvore de trabalho. `plain` é Claude Code sem o andaime. `base` é o harness naquele sha. `cand-<id>` é um overlay; o formato existe, sem candidato real. O agente só entra com prompt, ou quando o runner é pedido. Tokens vêm do JSON de usage; sem agente, ficam null. No máximo 12 corridas por tarefa.

`hdev xray` estima o contexto inicial (CLAUDE.md e imports, skills visíveis, subagentes, ritual, prompt do executor). A conta é 1 token por 4 bytes UTF-8, arredondando para cima, e leva o rótulo de estimativa. `hdev check` falha se passar de `caps.context_initial` (15000). `hdev fechar`, depois da suíte passar, grava o caso da unidade. Na branch base o arquivo entra no marco. Fora dela fica no worktree, sem commit. `evals/judge-labels/` e `evals/skills/` continuam no lugar. `releases/v*/` já instalado não muda.

## Grafo como cache (v2, 20/11/2026)

`graphify update` (AST, sem LLM) roda no hook de git pós-commit e no `hdev graph update`. O grafo fica em `.hdev/cache/graph/` (gitignored), com o sha do HEAD ao lado. `scripts/affected-tests` lê só arestas de import EXTRACTED. `hdev impact` lista quem chama e o que o arquivo chama. Só o explorer (`haiku-explorar`) recebe `graphify query`, `path` e `explain`. Sem o binário, sem o arquivo ou com sha velho, o comando avisa e cai na suíte do módulo (`tests/test_<módulo>*.py`, senão `tests/test_*.py`). `GRAPH_REPORT` não entra na sessão. `gates.fast` e `gates.full` não mudam nesta peça. `releases/v*/` já instalado não muda.

## Parada fechada (v2, 20/11/2026)

A unidade mora em `.hdev/state/unit.json` (`open`, `blocked`, `ready-to-publish`, `closed`). `hdev base --marcar` abre. `hdev fechar` pass fecha. Com a unidade aberta e sem PAREI da lista, o Stop não encerra a sessão: diz o próximo passo. Na quarta vez grava `PAREI: gate esgotado (open_unit)`. O handoff continua podendo encerrar; a sessão nova leva plano, brief, permissões de pé (`stop.standing_ok`), estado e o mesmo modelo. Item da lista coberto por `stop.standing_ok` vira `READY-TO-PUBLISH` e o agente pega a próxima unidade. Sem a chave, publicar continua parada. `hdev resume --blocked-on` marca a espera de outra faixa. `releases/v*/` já instalado não muda.

## Biblioteca (v2, 20/11/2026)

Lições entre peças ficam em `library/` (uma linha de JSON por item, corpo ao lado). `hdev library pull` traz no máximo 5, com 1.500 tokens de lição e 2 skills, depois da spec aprovada. O brief pede a tag `pergunta`. Antes de diagnosticar uma falha, `--symptom`. `hdev reflect` grava no repo; a cópia em `.harnessdev/library/` é só leitura. Item novo nasce `candidate`. Sem o segundo modelo, ou com `--offline`, fica `generalization: pending` e não promove. `hdev library tidy` promove, aposenta e apaga; o `hdev fechar` pass chama o tidy e pontua o pull. `--dry-run` não pontua. `active` não vira `core` sozinho: `hdev library status` lista quem está elegível. `hdev check` cobra índice válido, lição de até 3 linhas, script com teste e no máximo 60 ativas. Skill da biblioteca não se instala. `releases/v*/` já instalado não muda.
