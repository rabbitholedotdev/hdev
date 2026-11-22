# Perfil harness-developer

Perfil padrão. Aplicado por `hdev init` (ADR 0002), a partir da release fixada no `.harnessdev.lock`:
- `AGENTS.md` daqui vira o `AGENTS.md` inicial do app, com o bloco `<!-- perfil:harness-developer -->`
  (≤ 30 linhas, conferido pelo `hdev check`). É do app: o dono edita.
- `progress.md` daqui vira o `docs/progress.md` inicial do app.

Regras do perfil: `hdev check` é portão; peça nova entra com teste ou eval; no máximo 1 skill própria.
`app-developer` nasceu como `ratoeira-app-creator` (F1-09, apps da Ratoeira); `worker-developer` só nasce com o
primeiro consumidor real.
