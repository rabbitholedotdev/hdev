# Plano — v2-pr8-fechar-full

Spec: sem spec (pedido fechado do dono: o fechar roda a suíte inteira; a spec nova não cabe nesta PR)

## Objetivo
`hdev fechar` roda `gates.full` num clone limpo do HEAD, em shards, com cache por tree sha.

## Critério de pronto
- `bin/hdev fechar --plan work/_example/plan.md --dry-run` sai 0 e mostra `gates.full`.
- `python3 -m unittest tests.test_gates_full -q` sai 0. A suíte cobre: clone limpo ignora arquivo sujo e não rastreado; o corte dos shards cobre cada módulo uma vez; shard que falha entra na soma com o nome do teste; cache acerta na mesma árvore; erra se mudam árvore, comando ou shards; falha, timeout e erro não entram no cache; `--no-cache`; formato do trailer.
- `bin/hdev fechar --plan work/v2-pr8-fechar-full/plan.md` duas vezes no mesmo HEAD: a primeira roda os shards (testes, shards, tempo de parede e serial); a segunda diz que veio do cache. As duas saídas ficam em `work/v2-pr8-fechar-full/evidence/fechar-real.md`.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr8-fechar-full/evidence/aceite.md` (comandos do aceite, com o HEAD). O fechar real está em `work/v2-pr8-fechar-full/evidence/fechar-real.md`.
  - dry-run: sai 0 e imprime `gates.full`
  - suíte nova: `python3 -m unittest tests.test_gates_full -q` sai 0
  - fechar duas vezes: a segunda linha traz `veio do cache`
  - suíte inteira: `python3 -m unittest discover -s tests -q` sai 0
  - portão: `bin/hdev check` sai 0
  - manifesto: `bin/hdev sync --check` sai 0

## Abordagem
A corrida mora em `hdev/gates/full.py`. O cache mora em `hdev/gates/full_cache.py`, no mesmo desenho do cache do juiz (`.hdev/cache/full/`, gitignored, gravação atômica). `hdev/fechar.py` continua o portão: chama a suíte e, se passar, grava o trailer.

Árvore com mudança rastreada: o fechar recusa, como hoje. A mensagem diz que a suíte cobre só o commit. A corrida, quando acontece, clona o HEAD e não vê sujeira nem arquivo não rastreado.

Shards: o padrão é `min(núcleos, 4)`. `gates.shards` no manifesto troca o número (teto 16). Se o comando é `unittest discover`, os módulos (arquivos que casam com `-s`/`-p`) são repartidos em round-robin, cada um uma vez. Cada shard ganha um `git clone --local` próprio e roda `python -m unittest` nos seus arquivos. Comando que não é discover roda inteiro num clone só (1 worker). Tempo serial é a soma dos shards (clone + testes). Tempo de parede é o relógio da corrida paralela. Não rodo a suíte duas vezes para medir o serial.

Cache: a chave leva o tree sha do HEAD, o comando `gates.full`, o `gates.shards` resolvido, o número de workers, a versão do Python do interpretador do comando, o timeout e a versão do formato do resultado. O tree sha cobre o código. O comando cobre o jeito de achar os testes. Shards e workers cobrem o corte. A versão do Python cobre o interpretador. O timeout entra porque um timeout menor pode transformar um pass antigo em timeout. O formato entra para um runner novo não reusar um JSON velho. Falha, timeout e erro não são gravados. `--no-cache` não lê; um pass grava, para a corrida seguinte acertar.

Trailer, no marco (branch base): `Hdev-Gates-Full: pass tree=<sha> tests=<n> shards=<k> s=<secs> cache=<hit|miss>`. `s` é o tempo de parede, uma casa. Fora da base o marco não nasce (exit 0 se a suíte passa) e a mesma linha vai em `.hdev/runs/fechar-*.json`. `--dry-run` mostra o comando, o corte e se o cache acertaria, sem rodar e sem cravar pass.

`work/_example/plan.md` já existe. Não reescrevi.

Jev sem chave: não chamei (sem API paga). Juiz grok e Codex não rodam nesta VM.

## Passos
1. Testes que falham: clone limpo, corte, falha de shard, cache, `--no-cache`, trailer.
2. Implementar a corrida e o cache até os testes passarem.
3. `hdev check` e `hdev sync --check` verdes.
4. `hdev fechar` duas vezes na branch da PR (marco pulado, exit 0). A segunda vem do cache.
5. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_gates_full.py` — clone, shards, cache, trailer
- `tests/test_fechar.py` — o dry-run não roda mais a suíte; a suíte vermelha continua no fechar de verdade
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Rodar o juiz grok ou o fallback Codex. Sem API paga.
- Mexer em `master` ou fazer merge.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`.
- Reescrever `releases/v*/` já instalado.
- Subir teto de hooks, skills ou subagentes.
- Fazer o `hdev judge --run-tests` usar shards. O juiz continua com o comando único.

## Riscos
- A sessão aberta não importa o fechar pelos hooks. Nenhum hook importa `hdev.fechar` nem `hdev.gates.full`.
- Testes que escrevem arquivo no clone não se cruzam: um diretório por shard. Estado fora do clone (porta, arquivo fixo em `/tmp`) continua risco; a suíte de hoje usa pasta temporária.
- O cache não pode guardar falha: uma queda transitória tem de rodar de novo.
- `--dry-run` deixa de executar a suíte. Quem usava o dry-run para ver a suíte vermelha precisa rodar o fechar de verdade.
