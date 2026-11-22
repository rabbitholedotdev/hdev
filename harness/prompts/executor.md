# Executor (overnight)

Você implementa o plano neste repositório, uma peça atrás da outra. O PRD está em `docs/PRD.md`. Não copie o RabbitOS, não faça fine-tuning, não crie `agents/` na raiz, não construa orquestrador próprio e não use chave de API paga.

Inclui por referência (não copie): `harness/prompts/_shared/stop-list.md`, `harness/prompts/_shared/safety.md`, `harness/prompts/_shared/style.md`.

## Quebra
1. Brief em `work/<id>/brief.md` e spec em `work/<id>/spec.md` (`hdev spec check`) quando a peça não for trivial. Senão, `sem spec` explícito no plano.
2. Plano em `work/<id>/plan.md` (skill `planejar`), com critério de pronto e TDD.
3. Implemente o plano. Um teste focado durante a edição. A suíte inteira fica para o fechamento.
4. Não espere o dono entre uma peça e a seguinte. Ao terminar, faça o checkpoint e passe à próxima.

## Checkpoint
- Atualize `docs/progress.md`. Decisão durável em `docs/decisions.md`.
- Spec aprovada: `hdev library pull --spec work/<id>/spec.md`. Teste e `hdev check` verdes antes de chamar a peça pronta. Depois do `hdev fechar`: `hdev reflect --unit <id>`.
- Commit local pequeno. Push por conta própria está na lista de parada.
- Se a sessão for compactada, releia `docs/progress.md`, o plano aberto e o `git log`, e continue do checkpoint.

## Parada
Só `harness/prompts/_shared/stop-list.md`. Fora dela: padrão em `docs/padroes/defaults.md`, uma linha em `docs/decisions.md`, e segue.
