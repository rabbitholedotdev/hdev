# Plano — v2-pr9-evals-xray

Spec: sem spec (pedido fechado do dono: evals com braços e xray; a spec nova não cabe nesta PR)

## Objetivo
Cada andaime (prompt, skill, hook) tem de caber no contexto inicial e de poder ser comparado com o Claude Code puro. O caso mora em `evals/tasks/`. O `hdev eval run` isola os braços. O `hdev xray` mede o que a sessão carrega antes da primeira palavra.

## Critério de pronto
- `bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1` sai 0 e grava `.hdev/runs/eval-*.json` com pass, tokens e seconds por braço.
- O mesmo comando com `--runner fake` preenche tokens com o usage do falso (não estima).
- `bin/hdev xray --max 15000` sai 0 e mostra a tabela por fonte. `bin/hdev xray --max 100` sai 1.
- `python3 -m unittest tests.test_eval tests.test_xray tests.test_evals -q` sai 0. A suíte cobre: plain tira os arquivos do harness, base mantém, o overlay `cand-<id>` aplica, a árvore de trabalho não muda, o teto de 12 recusa, o falso preenche tokens a partir do JSON, CLI do agente ausente sai 3, xray acima do teto sai 1 e falha o `hdev check`, fechar grava o caso depois do pass e não grava depois da falha.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0 e a linha `xray` mostra a estimativa contra `caps.context_initial`.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-pr9-evals-xray/plan.md --dry-run` sai 0 e diz que o commit do marco foi pulado.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr9-evals-xray/evidence/aceite.md` (comandos do aceite, com o HEAD). O dry-run do fechar está em `work/v2-pr9-evals-xray/evidence/fechar-dry-run.md`.
  - eval: `bin/hdev eval run --case smoke-init-check --arms plain,base --runs 1` sai 0 e o JSON tem pass, tokens e seconds
  - falso: o mesmo com `--runner fake` traz tokens do usage
  - xray: `--max 15000` sai 0 com a tabela; `--max 100` sai 1
  - suíte nova: `python3 -m unittest tests.test_eval tests.test_xray tests.test_evals -q` sai 0
  - suíte inteira: `python3 -m unittest discover -s tests -q` sai 0
  - portão: `bin/hdev check` sai 0 e a linha `xray` está verde
  - manifesto: `bin/hdev sync --check` sai 0
  - fechar: o dry-run imprime `commit do marco pulado`

## Abordagem
O caso replayável é `evals/tasks/<id>/task.json`: `repo`, `base_sha`, `prompt` e `spec` opcionais, `acceptance`, `caps`. Os dois casos de `evals/cases/` vão para aí. `evals/cases/` sai: só `tests/test_evals.py` lia a pasta. O teste passa a ler as tarefas. O cenário mecânico (init com a tag `v9.9.9`, app new, check) fica no campo `steps` quando o `acceptance` do runner não pode repetir a tag falsa. `evals/judge-labels/` e `evals/skills/` não mudam.

Braços em `evals/arms/`. `plain` apaga CLAUDE.md, AGENTS.md, `.claude/settings.json`, `.claude/skills`, `.claude/hooks` e `harness/prompts`. `base` deixa o clone como está no `base_sha`. `cand-<id>` é uma pasta de overlay em cima do base; não há candidato real nesta PR. O overlay é lido da árvore de quem invoca o `hdev`, não do commit antigo.

`hdev eval run` clona com o mesmo `git clone --local` do `hdev/gates/full.py`. Um clone por braço e corrida, no `base_sha`. A árvore de trabalho não é checkout nem commit. O agente só roda se a tarefa tem `prompt` (`auto`) ou se o runner foi pedido (`fake` ou `claude`). O comando do claude vem de `eval.agent_cmd` (padrão `claude -p --output-format json`). Nesta VM não se chama o binário real. O falso é um processo que imprime JSON com `usage`. Sem o executável: exit 3, sem traceback. Tokens só saem desse JSON; sem agente, `tokens` é null. Estimativa não entra nesse campo. Teto: braços × corridas ≤ 12 (e ≤ `caps.runs` da tarefa, se for menor). Acima disso, exit 2. O registro vai para `.hdev/runs/eval-<ts>.json` (gitignored), com pass, tokens, seconds, exit codes e o total de xray do braço.

`hdev fechar`, depois da suíte passar, grava ou refresca `evals/tasks/<id>/task.json`. A base vem de `.hdev/state/bases.json`. Os comandos vêm dos crases da seção Critério de pronto (`bin/hdev`, `hdev`, `python3`). `hdev ...` vira `bin/hdev ...` e repetições se juntam. O exit sai da mesma linha (`sai 0`, `exit 1`, `sai ≠ 0`, `= 0`). Sem essa frase, ou se duas frases discordam, o caso fica `draft` true e o exit não vira 0 por chute. Falha e `--dry-run` não gravam. A escrita é depois do portão: não muda o tree sha do cache da PR8 e não esbarra na recusa de árvore suja. Na branch base o arquivo entra no marco (`git add` e o commit que já existia). Fora da base o marco não nasce; o arquivo fica no worktree, sem commit, e o tree do portão continua o do HEAD.

`hdev xray` soma, com rótulo de estimativa: CLAUDE.md e os `@imports` recursivos, nome e description das skills visíveis da fase, descriptions dos subagentes, a stdout do ritual e o prompt do papel `executor` mais os `_shared` que ele cita. O ritual roda `harness/hooks/session.py` com `HDEV_XRAY=1`, que imprime o texto e sai antes de gravar estado. Método: 1 token por 4 bytes UTF-8, arredondando para cima. Não é o tokenizador do modelo. `--max N` sai 1 se o total passa de N. `hdev check` ganha a linha `xray` com o teto `caps.context_initial` (15000 neste repo, igual ao código).

Jev sem chave: não chamei (sem API paga). Juiz grok e Codex não rodam nesta VM.

## Passos
1. Testes que falham: braços, teto, falso, CLI ausente, xray, fechar grava o caso.
2. Implementar até os testes passarem.
3. `hdev check` e `hdev sync --check` verdes.
4. Os comandos do aceite, com a saída em `evidence/`.
5. `hdev fechar --plan work/v2-pr9-evals-xray/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
6. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_eval.py` — braços, árvore, teto, falso, CLI ausente, fechar
- `tests/test_xray.py` — estimativa, teto, linha do check
- `tests/test_evals.py` — os dois casos mecânicos, agora em `evals/tasks/`
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Rodar o juiz grok, o fallback Codex, um claude real ou qualquer API paga.
- Candidato real em `evals/arms/cand-*`. Só o formato e o loader.
- Mexer em `evals/judge-labels/` ou `evals/skills/`.
- Mexer em `master` ou fazer merge.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`.
- Reescrever `releases/v*/` já instalado.
- Subir teto de hooks, skills ou subagentes. O teto novo é o do contexto inicial (15000), no mesmo regime dos outros `caps`.

## Riscos
- A sessão aberta lê `.claude/settings.json` e os hooks no caminho atual. `HDEV_XRAY=1` sai antes de gravar; o caminho normal do `session.py` não muda. Nenhum arquivo de hook é movido.
- `plain` no clone antigo não pode ser o `{core}` do init: a release instalada pelas tags reais é antiga e o check novo a reprovaria. O cenário do init continua no `steps`, com o núcleo de teste.
- A suíte inteira roda em 4 shards. Os testes novos usam pasta temporária; não escrevem no `.hdev/runs` do repo.
- O fechar de verdade, na branch base, passa a incluir o `task.json` no marco. O `--squash` deixa de preservar o tree sha byte a byte: a única diferença é esse arquivo.
