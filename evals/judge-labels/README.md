# Rótulos do juiz

O `hdev judge` é consultivo enquanto houver menos de 20 rótulos válidos aqui (PRD v0.6). Válido = JSON no
formato abaixo, com `plan`, `run` e `by` preenchidos e `judge_verdict`/`expected` em `pass|fail|unsure`;
dois arquivos com o mesmo `plan` + `run` contam como um.
Só o João rotula. Um arquivo por caso, `<data>-<tarefa>.json`:

```json
{
  "plan": "docs/plan-<tarefa>.md",
  "run": ".hdev/runs/judge-<carimbo>.json",
  "judge_verdict": "pass",
  "expected": "pass",
  "by": "joao",
  "note": "por que o juiz acertou ou errou"
}
```

Com 20 rótulos o juiz deixa de ser consultivo; antes disso, a taxa de acerto (`judge_verdict == expected`)
é o que decide se ele passa a barrar sozinho.
