# ADR 0011 — Nomes de desenvolvimento em inglês, com portão no hdev check

- Status: aceito
- Data: 2026-11-16
- Origem: pedido do João (16/11, 14:38 -03): "o padrão de desenvolvimento é inglês"; "esse padrão tem que ser o da
  ratoeira". Disparo: uma sessão propôs `espacos.json` e pastas em português para o construtor de landing pages.

## Contexto

A regra "nomes novos em inglês, minúsculas e hífen" era uma linha no AGENTS.md, sem dizer o que é "nome" nem o que
pode ficar em pt-BR, e nada conferia. O `hdev check --area` olha pastas da área, não o diff da unidade.

## Decisão

- Regra escrita em `docs/padroes/naming.md` e resumida na seção `## Nomes` do AGENTS.md do núcleo e dos perfis.
- Checagem `names` no `hdev check`: nomes novos desde a base da unidade (caminhos e branch). Não-ASCII é aviso com
  `naming.mode = warn` e falha com `fail` (padrão desde v0.6.0); palavra em português sem acento é sempre só aviso.
- `hdev check --base REF` e `hdev judge` (que passa a base da unidade ao check do clone, sem `bases.json`).
- Legado não se renomeia; renomear é decisão do João.

## Rollout

1. v0.5.0: padrão `warn`; nenhum repo quebra. Cada repo passa a `fail` com `"naming": {"mode": "fail"}` no
   `.hdev/config.json`; o núcleo já roda em `fail`.
2. v0.6.0 (João, 16/11 e 18/11): `DEFAULT_MODE = "fail"` em `hdev/naming.py`. `warn` e `off` por opt-in.

## Perguntas abertas ao João

Fechadas em 18/11: o modelo do app-creator (`migracoes/`, `tela/`, `teste/`) fica em português; `unidade/<ID>`
fica (ADR 0009); alias em inglês de `fechar`/`--marcar`/`--rejulgar` fica para depois.

## Consequências

Nome novo com não-ASCII quebra o check a partir da v0.6.0. Falso positivo da lista é só aviso e se cala com
`allow_words`/`allow_paths`. Repo legado que ainda não aguenta o portão: `"naming": {"mode": "warn"}`.
