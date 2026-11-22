# Plano — v2-pr10-graphify

Spec: sem spec (pedido fechado do dono: graphify como cache de contexto; a spec nova não cabe nesta PR)

## Objetivo
O grafo do graphify é cache, não dependência. O git o reconstrói sem token (só AST). `scripts/affected-tests` e `hdev impact` leem esse cache. Só o explorer recebe orientação de consulta. Sem o binário, sem o arquivo ou com sha velho, o comando avisa e segue.

## Critério de pronto
- O portão da CLI mora em `hdev/stop.py` (`hdev/gates/stop.py` não existe; o hook é `harness/hooks/stop_gate.py`). `bin/hdev impact hdev/stop.py` sai 0 e lista quem chama ou importa esse arquivo.
- `scripts/affected-tests hdev/stop.py` sai 0 e a stdout inclui `tests/test_stop.py`.
- `python3 -m unittest tests.test_graph -q` sai 0. A suíte cobre: aresta EXTRACTED entra e INFERRED fica de fora, grafo velho cai na suíte do módulo, grafo ausente cai com mensagem, graphify ausente não quebra o `hdev check`, a linha `graph` falha se o prompt do orquestrador ou do executor menciona o grafo.
- Com graphify instalado, o hook `scripts/post-commit` grava `.hdev/cache/graph/` num commit. Os dois comandos acima rodam nesse grafo. Registro em `work/v2-pr10-graphify/evidence/graph-real.md`.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0, com 5 registros e 3 arquivos, e a linha `graph` verde. `bin/hdev xray` continua abaixo de `caps.context_initial`.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-pr10-graphify/plan.md --dry-run` sai 0 e diz que o commit do marco foi pulado.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr10-graphify/evidence/aceite.md` (comandos do aceite, com o HEAD). O dry-run do fechar está em `work/v2-pr10-graphify/evidence/fechar-dry-run.md`.
  - impact: `bin/hdev impact hdev/stop.py` sai 0 e lista chamadores
  - testes afetados: `scripts/affected-tests hdev/stop.py` sai 0 e inclui `tests/test_stop.py`
  - suíte nova: `python3 -m unittest tests.test_graph -q` sai 0
  - suíte inteira: `python3 -m unittest discover -s tests -q` sai 0
  - portão: `bin/hdev check` sai 0, linha `graph` verde, hooks 5 registros e 3 arquivos
  - manifesto: `bin/hdev sync --check` sai 0
  - fechar: o dry-run imprime `commit do marco pulado`

## Abordagem
O pacote no PyPI é `graphifyy` (CLI `graphify`). Nesta peça a versão é 0.9.112, a mesma da operator host. `graphify update .` reextrai código e não chama LLM. A saída padrão é `graphify-out/graph.json`. `GRAPHIFY_OUT` (lido na partida do processo) troca o diretório. O comando e o hook usam `GRAPHIFY_OUT=.hdev/cache/graph`, com `GRAPHIFY_NO_TIPS=1`.

O `graph.json` dessa versão é node-link: nó com `id`, `label` e `source_file` (caminho relativo); aresta em `links` com `source`, `target`, `relation` e `confidence` (`EXTRACTED`, `INFERRED` ou `AMBIGUOUS`). Import de verdade é `imports` ou `imports_from` com `confidence` igual a `EXTRACTED`. Chamada de verdade, para o impacto, é `calls` com o mesmo `confidence`. O resto (`contains`, `method`, `INFERRED`, `AMBIGUOUS`) não entra.

O sidecar é `.hdev/cache/graph/sha`, uma linha com o `git rev-parse HEAD` de depois do update. Grafo fresco: o arquivo existe, o JSON abre e o sha é o HEAD. Senão está ausente, ilegível ou velho.

`scripts/affected-tests` sobe pelas arestas de import EXTRACTED a partir dos nós do arquivo (quem importa), no máximo 8 saltos e 2000 nós. Teste é `tests/test_*.py` na primeira pasta. Se o próprio arquivo é teste e está no grafo, entra. Aresta INFERRED não entra. Se o grafo não serve, ou o arquivo não tem nó, a stdout volta a suíte do módulo: o radical do nome (`hdev/stop.py` → `stop`) casa `tests/test_<radical>*.py`. Sem esse arquivo, a suíte inteira é `tests/test_*.py` nessa pasta. O motivo vai no stderr e o comando sai 0.

`hdev impact <arquivo>` lista, num salto, os arquivos do repo que chamam ou importam o alvo e os que o alvo chama ou importa (só EXTRACTED). Nome sem `source_file` (a stdlib) sai numa linha `fora do repo`, para o revisor não ir lê-la. O mesmo fallback de grafo velho ou ausente vai no stderr; a stdout fica vazia, sem inventar chamador.

`scripts/post-commit` é versionado como `scripts/pre-commit`. O `hdev init` copia os dois e o `scripts/post-checkout` (que só chama o post-commit). Não sobrescreve hook que já existe e não mexe em worktree compartilhada. `post-checkout` é barato: se o sha já é o HEAD, `hdev graph update` não chama o binário. Sem graphify, o hook avisa e sai 0. `HDEV_SKIP_GRAPH=1` pula (os testes de git usam isso). Não é hook do Claude e não entra nos 5 registros. Sem merge driver: o grafo não é commitado (`.hdev/cache/` já está no gitignore).

A linha `graph` do `hdev check` lê `AGENTS.md`, `CLAUDE.md`, os prompts do orquestrador e do executor (no núcleo ou em `.harnessdev`) e os `SKILL.md` e `references/` das skills. Falha se aparecer `graphify`, `GRAPH_REPORT` ou a palavra `grafo`. O `.claude/agents/haiku-explorar.md` fica de fora dessa varredura e precisa citar `graphify query`, `graphify path` e `graphify explain`. O `hdev check` não executa o binário.

O `revisar-diff` manda rodar `hdev impact` em cada arquivo do diff e ler esse conjunto. O texto não usa as palavras que a linha `graph` recusa, e não entra no contexto inicial (o xray lê a description da skill e o prompt do executor, não o `references/` nem o reviewer).

## Passos
1. Testes que falham: fixture, fallback, linha `graph`, hook.
2. Implementar até os testes passarem.
3. `hdev check`, `hdev sync --check` e o xray verdes.
4. Hook real num commit, com graphify 0.9.112, e os dois comandos no grafo gerado.
5. `hdev fechar --plan work/v2-pr10-graphify/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
6. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_graph.py` — fixture `tests/fixtures/graph/graph.json`, fallback, check, hook, binário ausente
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Modo always-on do graphify, `--strict` (negar Read/Grep até consultar o grafo), o SKILL.md de 824 linhas e carregar `GRAPH_REPORT` em toda sessão.
- `graphify install` em qualquer plataforma. Nenhum merge driver.
- Trocar `gates.fast`, `gates.full` ou o Stop para usar `affected-tests`. Fica como passo seguinte possível.
- Rodar o juiz grok, o fallback Codex, um claude real ou qualquer API paga.
- Mexer em `master` ou fazer merge.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`. Não ligar nada novo no Stop nem no PreToolUse.
- Reescrever `releases/v*/` já instalado.

## Riscos
- O `core.hooksPath` desta VM aponta para o dispatcher do Cursor. O hook versionado mora em `scripts/` e o `init` copia para o git do app. Nesta VM, para o commit de evidência, o `post-commit` do `.git/hooks` é o que o dispatcher já chama. O dispatcher não é hook do Claude.
- `hdev/stop.py` é importado por vários testes, não só `tests/test_stop.py`. A lista do grafo é maior que a suíte do módulo. O critério pede que `tests/test_stop.py` esteja na lista.
- Outra PR aberta mexe em `hdev/cli.py`, `hdev/check.py` e no orquestrador. Aqui o diff nesses arquivos é o subcomando, a linha `graph` e nada no orquestrador.
