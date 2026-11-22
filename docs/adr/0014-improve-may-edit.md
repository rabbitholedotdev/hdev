# ADR 0014 — O que uma candidata do improve pode editar

- Status: aceito (desenho da v2, seção 5a, linha 13 da tabela; a ADR 0013 deixou a decisão para a PR13)
- Data: 2026-11-20
- Complementa a ADR 0013, que fica como está.

## Contexto

A ADR 0013 barra o que nenhuma candidata toca (`harness/protected.txt`). O desenho também diz o que ela pode editar: o papel, a skill que não guarda, `tools.md`, `docs/padroes/defaults.md` e os botões do manifesto. Só com a lista protegida, uma candidata que mexe em `AGENTS.md`, num módulo do `hdev/` fora da lista ou num teste chegaria a uma branch de adoção.

## Decisão

- A lista vira regra, cobrada no `hdev improve compose` (a adoção). Fora dela, o compose sai 1 e nomeia o caminho.
- Pode: `harness/prompts/<papel>.md` (arquivo direto da pasta; `_shared/` segue protegido), `.claude/skills/<skill>/...` menos as skills que guardam (`revisar-diff`, `revisar-spec`: são os portões de revisão em outro provedor), `tools.md`, `docs/padroes/defaults.md` e `.hdev/config.json` (os botões; os tetos continuam em `hdev/config.py`, protegido).
- Vale para o arquivo do overlay e para o `remove` da ficha. Tirar uma peça da lista é candidata válida.
- A lista mora em `hdev/improve/compose.py` (`MAY_EDIT`), dentro de `hdev/improve/`, que é protegido.
- O probe e a linha `overlays` do `hdev check` seguem cobrando só a lista protegida: o probe só toca o clone e serve para medir até o que não se adota.

## Consequências

- Mudar a lista do que pode editar pede ADR nova. `harness/protected.txt` não muda nesta ADR.
- Candidata que ganha fora da lista fica no relatório e na biblioteca, sem branch.
