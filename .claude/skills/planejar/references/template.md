# Molde do plano

Leia só no passo 3.

```
# Plano — <tarefa>

Spec: work/<id>/spec.md
Review: work/<id>/review.md (zero Blocker)
(ou "sem spec (trivial: <motivo>)")

## Objetivo
<uma frase>

## Critério de pronto
- <comando que confere>
- [juiz] <o que só o juiz avalia>

## Abordagem
<escolha e o porquê, 1–3 linhas. Se o Jev rotear, anote o worker>

## Passos
1. Escrever o teste que descreve o critério (deve falhar).
2. Implementar o mínimo para o teste passar.
3. `hdev check` verde.
4. Skill `revisar-diff` em outro provedor (`docs/reviews/<tarefa>.md`).
5. Fechar com `hdev judge --plan work/<id>/plan.md --run-tests`.
6. Até 5 linhas na seção Lições de `docs/progress.md`.

## Testes
- <arquivo::caso> — <o que prova>

## Fora de escopo
- ...

## Riscos
- ...
```

Sem review sem Blocker e sem `sem spec`, não grave o plano. Plano que pede hook, skill ou subagente a mais precisa de ADR. Segredo só por referência. `ask_human` true só em `harness/prompts/_shared/stop-list.md`: aí `hdev resume --reason … --next …`. O resto vira uma linha em `docs/decisions.md` e o plano continua (`docs/padroes/defaults.md`).
