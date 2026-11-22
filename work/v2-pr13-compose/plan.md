# Plano — v2-pr13-compose

Spec: sem spec (pedido fechado do dono: compose do improve, linha 13 do desenho da v2, seção 5a; continua a PR12)

## Objetivo
Uma candidata que o probe julgou `ganharia` vira mudança comum de revisar: branch local `improve/<cand>` com um commit que traz o trailer `Harness-Edit: <cand>` e o id do probe. Adotar é o merge humano dessa branch; o hdev não faz push, não abre PR e não faz merge. `hdev improve revert` desfaz uma edição adotada com um commit de revert, sem reescrever história.

## Critério de pronto
1. `python3 -m unittest tests.test_improve tests.test_improve_compose -q` sai 0.
2. `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
3. `bin/hdev improve probe --case smoke-init-check --cand demo --runs 3 --runner fake` sai 0; `bin/hdev improve compose --run <esse registro> --cand demo --dry-run` sai como o veredito pede (1, com o motivo, quando não é `ganharia`; 0 com o plano quando é); depois, `git status --porcelain` só mostra o que o probe gravou (`library/`) e `git branch --list 'improve/*'` sai vazio.
4. Caminho feliz ponta a ponta num repo temporário (teste `ComposeTest.test_compose_then_revert` e corrida com script na evidência): compose cria `improve/<cand>`, `git log -1 --format=%B improve/<cand>` mostra `Harness-Edit:`; depois do merge, `bin/hdev improve revert --cand <cand>` sai 0 e a árvore volta.
5. Compose de candidata cujo overlay toca `hooks/_lib.py` sai 1 e nomeia o caminho.
6. `bin/hdev check` sai 0 (skills 5/5, hooks 5 registros/3 arquivos, xray abaixo do teto).
7. `bin/hdev sync --check` sai 0.
8. `bin/hdev fechar --plan work/v2-pr13-compose/plan.md --dry-run` sai 0.
9. [juiz] cada item aponta para um comando e a saída em `work/v2-pr13-compose/evidence/aceite.md`.

## Abordagem
Stdlib. Um módulo novo `hdev/improve/compose.py` (dentro de `hdev/improve/`, que é protegido: nenhuma candidata o edita). Reusa `probe.overlay_paths`, `probe.load_protected`, `probe.is_protected`, `probe.propose` e `eval.overlay_meta`.

O commit nasce por plumbing do git, sem checkout: índice temporário (`GIT_INDEX_FILE`) lido do HEAD, `hash-object -w` e `update-index` para o overlay, `update-index --force-remove` para o `remove`, `write-tree`, `commit-tree -p HEAD` e `update-ref refs/heads/improve/<cand> <sha> ""` (o valor velho vazio garante que a branch não existia). A árvore de trabalho, o índice e o HEAD não mudam; a branch base fica intacta.

Recusa (sai 1, diz por quê, não muda nada), juntando todos os motivos: candidata fora do registro ou com veredito diferente de `ganharia`; caminho protegido (`harness/protected.txt`); caminho fora da lista do que pode editar; `remove` inválido; candidata que não muda nada no HEAD; árvore rastreada suja; branch `improve/<cand>` que já existe. `--dry-run` mostra branch, arquivos (novo, muda, sai) e a mensagem com o trailer, e não grava nada.

Lista do que pode editar vira regra (ADR 0014), cobrada só no compose: `harness/prompts/<papel>.md` (sem `_shared/`), `.claude/skills/<skill>/` menos as que guardam (`revisar-diff`, `revisar-spec`), `tools.md`, `docs/padroes/defaults.md` e `.hdev/config.json`. O probe e a linha `overlays` do check continuam cobrando só a lista protegida (o probe só toca o clone). `harness/protected.txt` não muda.

Mensagem: `improve: adota <cand>`, corpo com resumo, caso, veredito e Δ, e no fim os trailers `Harness-Edit: <cand>` e `Harness-Probe: <registro>`.

Biblioteca: o mesmo commit marca `status: active` no item `source: improve` do HEAD cuja evidência aponta esse registro e cuja tag é a candidata (status que já existe). Merge = adoção = lição ativa; o revert volta a `candidate`. Item que só está na árvore (probe sem commit) não entra, e a árvore suja já recusa.

Revert: `hdev improve revert --cand <cand>` acha o commit mais novo do HEAD com o trailer `Harness-Edit: <cand>`; `--commit <rev>` usa o commit dado e recusa se ele não tem o trailer. Recusa árvore suja e commit já revertido. Roda `git revert --no-edit` na branch atual.

## Passos
1. ADR 0014 (lista do que pode editar).
2. Testes que falham em `tests/test_improve_compose.py`.
3. `hdev/improve/compose.py` e os subverbos `compose` e `revert` na CLI.
4. `hdev check`, `hdev sync --check` e a suíte verdes.
5. Probe real com runner fake e compose `--dry-run`; corrida ponta a ponta num clone temporário; evidência; `git restore library/` e limpeza de `.hdev/runs/improve-*`.
6. `hdev fechar --plan work/v2-pr13-compose/plan.md`.

## Testes
- `tests/test_improve_compose.py` — recusa por veredito, caminho protegido, fora da lista, árvore suja e branch existente; dry-run não muda nada; caminho feliz (branch, um commit, trailer, overlay e remove aplicados, biblioteca ativa, base intacta); revert por candidata e recusa de commit sem trailer
- `tests/test_improve.py` — o probe não quebra
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Push, PR, merge (o merge é humano).
- Editor de outro provedor; braço com claude real. Só runner `fake` ou `--dry-run`.
- Lista do que pode editar no `hdev check` e no probe.
- Recusar quando o HEAD andou desde o probe (o commit registra o `base_sha` do probe no corpo).
- Skill nova, hook novo, dependência nova. `VERSION` parado. `releases/v*/` congelado.

## Riscos
- O probe com runner fake raramente dá `ganharia` no repo real; o caminho feliz é provado por ficha `ganharia` escrita no teste.
- Segundos de parede no fake variam; o veredito do item 3 pode mudar entre corridas. O item aceita qualquer veredito e confere a saída que ele pede.
- `docs/progress.md` perto do teto de 2.000.
