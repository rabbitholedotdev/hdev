# Evidência — compat `.harnessdev/PROMPT-ORCHESTRATOR.md`

HEAD `864e1f60132e519dbfbd5cae0bb56d33b45a1008`.

O `git archive` da release não traz `PROMPT-ORCHESTRATOR.md` na raiz (a raiz do núcleo não tem `PROMPT-*.md`). `release.install` chama `hdev.prompts.write_shipped`: se existe `harness/prompts/orchestrator.md`, grava na pasta da release o texto do papel mais `_shared/style.md`, `_shared/safety.md` e `_shared/stop-list.md`. Tag sem `harness/prompts/` não é reescrita; o teste `tests.test_prompts.Compat.test_tag_sem_harness_prompts_mantem_o_arquivo_do_archive` confere que o arquivo do archive (`ANTIGO`) permanece.

Comando: `hdev init` de um app temporário contra um núcleo de teste (`tests.helpers.make_core`, tag `v9.9.9`), que passa por `release.install`.

```
HEAD 864e1f60132e519dbfbd5cae0bb56d33b45a1008
init_exit 0
existe True
bytes 3363
tem_orquestrador True
tem_frase_2fa True
linhas_do_marcador 1
na_raiz_do_app False
na_raiz_do_nucleo False
--- primeiras 12 linhas ---
<!-- compat: montado na instalação da release; fonte harness/prompts/orchestrator.md + _shared/ -->

# Orquestrador

Você é só o orquestrador. Não implementa, não reescreve a spec e não faz a review goldfish na mesma sessão.

Inclui por referência (não copie): `harness/prompts/_shared/stop-list.md`, `harness/prompts/_shared/safety.md`, `harness/prompts/_shared/style.md`.

No app o binário é `python3 .harnessdev/bin/hdev`; no núcleo, `bin/hdev`.

## Loop
1. Leia `docs/progress.md`, `docs/decisions.md`, `docs/backlog.md` (se existir) e o plano da peça (`work/<id>/plan.md`). Rode `hdev resume`: se houver próximo passo (PAREI ou fila de retentativa), faça esse passo. Uma unidade por vez. Handoff #N continua de onde parou.
```

`linhas_do_marcador 1` é a contagem de linhas do arquivo montado iguais ao heading da lista. O arquivo fica em `<app>/.harnessdev/PROMPT-ORCHESTRATOR.md`, não na raiz do app nem na raiz do núcleo.
