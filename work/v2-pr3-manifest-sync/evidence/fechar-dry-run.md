# Evidência — fechar dry-run e hdev check

Rodado na branch `cursor/v2-pr3-manifest-sync-62e5`, no commit `c25f626b4fea9222aece43271c02c8b480dd51b8`. A base da unidade é `b1b4809`. O commit seguinte só acrescenta anexos em `work/v2-pr3-manifest-sync/evidence/` e ajusta o critério do plano. O comportamento do `fechar` e do `check` não muda.

## bin/hdev check

Comando: `bin/hdev check`

Exit: 0

```
[ok] agents: 65/80 linhas, perfil 5/30
[ok] claude_md: só @AGENTS.md
[ok] hooks: 7 registrados, com arquivo e teste
[ok] skills: 5/5
[ok] subagents: 2/2 na F2
[ok] config: executor anthropic, juiz xai
[ok] sync: settings.json bate com o manifesto
[ok] progress: 1821/2000 caracteres
[ok] harnessdev: sem .harnessdev (núcleo ou repo sem init)
[ok] names: base b1b4809 (bases.json v2-pr3-manifest-sync), mode fail, 7 segmentos novos, 0 não-ASCII, 0 avisos
```

## bin/hdev fechar --plan work/v2-pr3-manifest-sync/plan.md --dry-run

Comando: `bin/hdev fechar --plan work/v2-pr3-manifest-sync/plan.md --dry-run`

Exit: 0

```
hdev fechar: commit do marco pulado (branch cursor/v2-pr3-manifest-sync-62e5 não é a base f2-11-v0.6.0).
  veredito: .hdev/runs/fechar-20261119T200659827682Z.json
```

O marco não foi criado: a branch da PR não é `base_branch` (`f2-11-v0.6.0`).
