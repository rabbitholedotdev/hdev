# ADR 0002 — Consumo do harness pela raiz do projeto via `.harnessdev`

- Status: aceito (João, 14/11/2026, America/Sao_Paulo)
- Área: núcleo / `hdev init`

## Contexto

Qualquer projeto precisa alcançar o harness a partir da própria raiz, com um nome previsível (`.harnessdev`). Os apps fixam a versão. Nada do núcleo deve crescer dentro da pasta do app. O checkout canônico do harness passa a ser `$HDEV_ROOT`.

## Opções consideradas

1. **Git submodule** — o app guarda um ponteiro de commit. Funciona como trava de versão, mas pesa: `.git` de submodule, comandos extra, e o checkout do núcleo entra na árvore do app.
2. **Git subtree** — copia o código do harness para dentro do app. A pasta do app cresce. Fere o PRD.
3. **`hdev init` copiando a árvore**, com ou sem lock — também duplica arquivos no app. Sem lock, as versões divergem.
4. **`hdev init` criando um symlink `.harnessdev` para uma release versionada** (`releases/vX.Y.Z`, a partir de tag git) **e um `.harnessdev.lock` versionado no app** — no app só entram o link e um arquivo pequeno de trava. A versão fica fixa. O núcleo não é copiado.

## Decisão

A opção 4. O `hdev init` no repositório consumidor:

- instala (se ainda não houver) a release `vX.Y.Z` em `$HDEV_ROOT/releases/vX.Y.Z`, a partir da tag git `vX.Y.Z` (worktree ou checkout da tag; a tag é a fonte da verdade);
- cria o symlink `.harnessdev` → essa pasta de release;
- grava `.harnessdev.lock` (versionado no app) com a versão fixada.

O `hdev check` confere se o alvo do symlink coincide com o lock. Sem `git push`. Atualizar a versão é um passo explícito do `hdev init` (ou equivalente), não um sync automático. Este lock é do consumidor; não é o `.harness/lock.json` que a v0.4/v0.5 deixaram de fora do MVP.

## Consequências

- Nada do núcleo cresce na pasta do app: só `.harnessdev` e `.harnessdev.lock`.
- Apps em pastas diferentes podem fixar versões diferentes.
- Releases moram no checkout canônico, fora dos apps.
- Implementação do `init` e do `check` fica como tarefa (F1-04). Até existir a primeira tag, o init pode recusar ou pedir a versão.

## Implementação (F1-04, 14/11/2026)
- Release por `git archive <tag>` (sem worktree), com `.release.json` (versão, commit). Tag movida → recusa.
- No app também entram arquivos do próprio app (não do núcleo): `AGENTS.md` e `docs/progress.md` (modelos do
  perfil), `CLAUDE.md`, `.claude/settings.json` (só hooks, em `.harnessdev/hooks/`), o link da skill,
  `.hdev/config.json`. Sem tag, o init recusa.
