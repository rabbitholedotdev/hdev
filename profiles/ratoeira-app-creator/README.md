# Perfil ratoeira-app-creator

O "app-developer" do PRD: um perfil para apps locais do host (homelab / agent platform).
Plano original: `docs/plan-f1-ratoeira-app-creator.md`.

- `skill/SKILL.md`: da ideia ao app publicado.
- `criterios.md`: critérios de pronto de uma peça de app (mecânicos e `[juiz]`).
- `modelo/`: o esqueleto que `hdev app new` copia (Node 22 só stdlib).
- `AGENTS.md` e `progress.md`: o que `hdev init --profile ratoeira-app-creator` põe num repo de app próprio.

Não copia o `APPS.md` do host (ele muda com o host): aponta para `$HDEV_APPS_MD` e confere só o mecânico (`hdev app check`).

Área do host (repo com regras, skills e commit automático próprios): `hdev init <área> --profile
ratoeira-app-creator --skill-only` liga só `.harnessdev`, o lock e a skill; o `hdev check` ali confere só isso.
