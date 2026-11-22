# Plano — v2-pr5-hooks

Spec: sem spec (pedido fechado do dono: ADR 0012 já aprovado; a spec nova não cabe nesta PR)

## Objetivo
A lógica dos hooks mora em 3 arquivos, com 5 registros no manifesto. O script antigo em `hooks/` vira alias.

## Critério de pronto
- `echo '{"tool_name":"AskUserQuestion"}' | HDEV_PHASE=exec python3 harness/hooks/pre_tool.py; test $? -eq 2` sai 0.
- `python3 -m unittest tests.test_hooks -q` sai 0.
- `python3 -m unittest discover -s tests -q` sai 0.
- `bin/hdev check` sai 0 e a linha `hooks` mostra 5 registros e 3 arquivos.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-pr5-hooks/plan.md --dry-run` na branch da PR sai 0 e diz que o commit do marco foi pulado.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr5-hooks/evidence/aceite.md` (comandos do aceite, com o HEAD). O dry-run do fechar está em `work/v2-pr5-hooks/evidence/fechar-dry-run.md`.
  - pergunta na execução: o `pre_tool.py` com `HDEV_PHASE=exec` sai 2
  - suíte dos hooks: `python3 -m unittest tests.test_hooks -q` sai 0
  - suíte: `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo
  - portão: `bin/hdev check` sai 0 e a linha `hooks` tem 5 registros e 3 arquivos; aliases listados à parte
  - manifesto: `bin/hdev sync --check` sai 0
  - colisão, comando que falhou duas vezes e corte de saída: um arquivo de evidência cada, com comando e saída
  - alias: cada `hooks/*.py` e o alvo no módulo novo saem iguais no mesmo stdin (teste)
  - fechar: o dry-run imprime `commit do marco pulado`

## Abordagem
`pre_tool.py` junta segredo e destrutivo, nega `AskUserQuestion` na execução, segura o comando na terceira tentativa e avisa colisão (exit 0). `stop_gate.py` junta o gate e o progress; o handoff de Stop roda ali. `session.py` tem os outros dois registros: ritual uma vez por sessão e corte da saída longa. O desenho dizia "hooks 5/7"; o teto novo é 5 registros e 3 arquivos (ADR 0012). `hooks/_lib.py` não se move. Jev sem chave (exit 2): segui sem worker.

## Passos
1. Testes que falham: pergunta na execução, trava da segunda falha, aviso de colisão, corte, ritual, alias igual ao alvo, check com 5 e 3.
2. Implementar o mínimo para os testes passarem.
3. `hdev check` e `hdev sync --check` verdes.
4. `hdev fechar --plan work/v2-pr5-hooks/plan.md --dry-run` na branch da PR (marco pulado, exit 0).
5. Juiz grok no operator host (não roda nesta VM; sem fallback Codex).

## Testes
- `tests/test_hooks.py` — comportamento antigo, pergunta, falha seguida, colisão, corte, ritual, alias (escrito junto com o código; o portão da sessão não deixa apagar o script antigo antes do novo existir)
- `tests/test_check.py` — registro a mais, alias ausente, arquivo real ausente
- `tests/test_sync.py` — os 5 registros
- `tests/test_init.py` — app aponta para `.harnessdev/harness/hooks/`
- `tests/test_smoke.py` — teto 5

## Fora de escopo
- Apagar os aliases em `hooks/`. Fica para outra PR.
- Reescrever `releases/v*/` já instalado.
- Subir teto, skill nova, 6º registro (`SessionStart`).
- Rodar o juiz grok ou o fallback Codex.
- Mexer em `master` ou fazer merge.

## Riscos
- A sessão aberta chama `hooks/*.py` até o fim. O arquivo tem de continuar no mesmo caminho e sair com o mesmo código. Não mover, não apagar.
- App com settings antigo não é reescrito no init sem `--force`. O alias cobre o caminho velho; o check novo exige os 5 registros, então o app antigo passa no hook e falha o check até o init com `--force`.
