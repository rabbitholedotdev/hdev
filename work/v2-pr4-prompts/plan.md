# Plano — v2-pr4-prompts

Spec: sem spec (pedido fechado do dono: prompts por papel e uma lista de parada; a spec nova não cabe nesta PR)

## Objetivo
A lista de parada mora num arquivo só, e cada papel aponta para ela.

## Critério de pronto
- `test $(grep -rl 'stop-list.md' harness/prompts | wc -l) -ge 4` sai 0.
- `test $(wc -l < AGENTS.md) -le 60` sai 0.
- `test $(ls PROMPT-*.md 2>/dev/null | wc -l) -eq 0` sai 0.
- `python3 -m unittest discover -s tests -q` verde.
- `bin/hdev check` verde.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-pr4-prompts/plan.md --dry-run` na branch da PR sai 0 e diz que o commit do marco foi pulado.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr4-prompts/evidence/aceite.md` (comandos do aceite, com o HEAD). O dry-run do fechar está em `work/v2-pr4-prompts/evidence/fechar-dry-run.md`. A compat da release está em `work/v2-pr4-prompts/evidence/compat-prompt.md`.
  - quatro papéis citam `stop-list.md`: o `grep -rl` imprime pelo menos 4 caminhos e o `test` sai 0
  - `AGENTS.md` cabe: `wc -l` imprime no máximo 60
  - a raiz não tem `PROMPT-*.md`: o `ls` não lista arquivo e o `test` sai 0
  - suíte: `python3 -m unittest discover -s tests -q` sai 0
  - portão: `bin/hdev check` sai 0 e a linha `prompts` está ok
  - manifesto: `bin/hdev sync --check` sai 0
  - compat: init num app temporário a partir de um núcleo de teste deixa `.harnessdev/PROMPT-ORCHESTRATOR.md` no disco, com o texto do orquestrador e o da lista de parada
  - tag antiga: um archive sem `harness/prompts/` mantém o `PROMPT-ORCHESTRATOR.md` que já estava nele (teste `tests.test_prompts`)
  - teto: `caps.agents` é 60; hooks 7, skills 5, subagentes 2 e progress 2000 não mudam
  - fechar: o dry-run imprime `commit do marco pulado`

## Abordagem
Os papéis em `harness/prompts/` incluem `_shared/` por referência. O `install` da release grava `PROMPT-ORCHESTRATOR.md` na pasta instalada, juntando `orchestrator.md` e `_shared/`, para o app continuar achando `.harnessdev/PROMPT-ORCHESTRATOR.md`. Tag sem `harness/prompts/` não é reescrita. O `check` recusa o marcador `## stop-list` em outro `.md`. Jev sem chave (exit 2): segui sem worker.

## Passos
1. Testes que falham: papéis citam a lista, raiz sem `PROMPT-*.md`, teto 60, marcador único, release entrega o prompt, tag antiga preserva o arquivo.
2. Implementar o mínimo para os testes passarem.
3. `hdev check` verde.
4. `hdev fechar --plan work/v2-pr4-prompts/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
5. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_prompts.py` — lista única, papéis, compat do install, tag antiga (escrito antes do código)
- `tests/test_check.py::Tetos` — `caps.agents` 60 para o caso que estoura hooks continuar apontando `caps.hooks`

## Fora de escopo
- Subir teto, mudar hooks (7), skills (5) ou subagentes (2).
- Mudar a CLI de área, reescrever `releases/v*/`, push de release, merge, tag.
- Rodar o juiz grok ou o fallback Codex.
- Apagar o alias `docs/plan-<tarefa>.md`.

## Riscos
- App instalado lê `.harnessdev/PROMPT-ORCHESTRATOR.md`. Sem a montagem no `install`, a próxima release quebra o perfil e a skill.
- O marcador da lista, se copiado para a evidência, faz o `check` falhar.
