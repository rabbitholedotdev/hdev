# Plano — v2-pr7-judge-pacote

Spec: sem spec (pedido fechado do dono: o juiz vira pacote, com cache por sha; a spec nova não cabe nesta PR)

## Objetivo
`hdev/judge.py` vira o pacote `hdev/gates/judge/`, com o mesmo comportamento e um cache por sha.

## Critério de pronto
- `python3 -m unittest tests.test_judge -q` sai 0. A suíte cobre a regra de partir o diff, a leitura da evidência commitada, o acerto de cache com as mesmas entradas (o falso roda uma vez), a falha de cache quando cada parte da chave muda, `--no-cache` e erro que não entra no cache.
- `wc -l hdev/gates/judge/*.py | sort -n | tail -2 | head -1` mostra o maior arquivo com menos de 400 linhas.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0.
- `bin/hdev judge --help` lista as flags de antes e mais `--no-cache`. O antes e o depois ficam na evidência.
- `bin/hdev fechar --plan work/v2-pr7-judge-pacote/plan.md --dry-run` sai 0 e diz que o commit do marco foi pulado.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr7-judge-pacote/evidence/aceite.md` (comandos do aceite, com o HEAD). O dry-run do fechar está em `work/v2-pr7-judge-pacote/evidence/fechar-dry-run.md`.
  - suíte do juiz: `python3 -m unittest tests.test_judge -q` sai 0
  - maior arquivo: a linha do `wc` tem menos de 400
  - suíte inteira: `python3 -m unittest discover -s tests -q` sai 0
  - portão: `bin/hdev check` sai 0
  - manifesto: `bin/hdev sync --check` sai 0
  - flags: `bin/hdev judge --help` tem as de antes e `--no-cache`
  - fechar: o dry-run imprime `commit do marco pulado`

## Abordagem
O comportamento sai de `hdev/judge.py` para um arquivo por assunto: pacote e corte, evidência, veredito, chamada. Grok (CLI `grok`, provedor xai, papel `judge`) e Codex (papel `roles.judge_fallback`) ficam em arquivos próprios e usam o mesmo executor de subprocesso, para o falso dos testes continuar valendo. `hdev/judge.py` fica um shim que reexporta o pacote: `bin/hdev`, `fechar` e os testes que importam `hdev.judge` não mudam de caminho. O cache mora em `.hdev/cache/judge/` (gitignored). A chave leva sha da base, sha do head, hash do plano, provedor e modelo (e o do fallback), versão da rubrica e do formato do pacote, se os testes rodaram, e o hash do pacote. `--no-cache` e `--rejulgar` chamam de novo. Erro, falha de provedor e `unsure` não entram no cache (o unsure repetido continua na regra dos 3 e no bloqueio de pacote idêntico). Jev sem chave (exit 2): segui sem worker.

## Passos
1. Testes que falham: cache acerta na segunda corrida igual; cada parte da chave erra; `--no-cache` chama de novo; erro e unsure não gravam cache.
2. Implementar o pacote e o cache até os testes passarem. O shim fica no lugar.
3. `hdev check` e `hdev sync --check` verdes.
4. `hdev fechar --plan work/v2-pr7-judge-pacote/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
5. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_judge.py` — corte, evidência, veredito, grok falso, e o cache com o falso
- `tests/test_cli_runtime.py` — a chamada ainda passa pelo shim
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Rodar o juiz grok ou o fallback Codex. Sem API paga.
- Mexer em `master` ou fazer merge.
- Mover, apagar ou renomear `hooks/` ou `harness/hooks/`. Não apagar `.claude/settings.json`.
- Reescrever `releases/v*/` já instalado.
- Subir teto de hooks, skills ou subagentes.
- Mudar o texto das linhas de saída que já existem (a linha do cache é nova).

## Riscos
- A sessão aberta importa o juiz pelos hooks só se algum script puxar `hdev.judge`. Nenhum hook importa o juiz hoje. O arquivo `hdev/judge.py` continua no lugar, reexportando o pacote, o tempo todo.
- O cache não pode guardar erro: uma falha transitória da CLI tem de chamar de novo.
- `unsure` fora do cache: a regra dos 3 segue lendo `.hdev/runs/`.
- O hash do pacote entra na chave. A primeira vez que o juiz grava uma base deduzida, a linha BASE DO DIFF muda de «deduzida» para «gravada» e o cache erra uma vez. Com a base já marcada, a segunda corrida acerta.
- O log de testes entra no pacote sem tempo de parede nem pasta temporária. Pass/fail, contagem e o nome do teste que falhou ficam. Sem isso, `--run-tests` nunca acerta o cache.
