# O que ler

Leia só no passo 2. Nada de histórico do chat e nada fora desta lista.

- a spec em `work/<id>/spec.md` (ou a nota `sem spec` no plano, se a tarefa for trivial)
- `work/<id>/plan.md`
- o diff: `git diff $(hdev base --plan work/<id>/plan.md --sha)` mais os não rastreados
- para cada arquivo do diff, `hdev impact <arquivo>`: leia quem chama ou importa e o que o arquivo chama ou importa, não só o diff

Confira segurança (segredo, permissão a mais, caminho destrutivo), excesso (o que a spec não pediu) e desvio (critério faltando ou fora de escopo feito). `no-go` ou `run_judge` false: corrija e revise de novo. `ask_human` true só em `harness/prompts/_shared/stop-list.md`.
