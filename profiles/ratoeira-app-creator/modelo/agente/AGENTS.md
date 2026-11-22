# {{titulo}}: como o agente usa o app

{{descricao}} **Não tem ferramentas (MCP):** leia e grave o banco direto, pela camada de regras quando der.

## Onde fica cada coisa

- Banco: `/var/lib/ratoeira/apps/{{nome}}/{{nome}}.db` (SQLite, WAL). O app está rodando: leia com `sqlite3 -readonly`.
- Formato: `migracoes/` (a versão aplicada fica em `PRAGMA user_version`).

| Tabela | O quê |
|---|---|
| `pessoas` | quem abriu o app: e-mail, nome, papel (vem da Ratoeira), `visto_em` (ms) |

## Cuidados

- Papel é da Ratoeira: não mude `papel` na mão; a próxima visita sobrescreve.
- Efeito fora do app (e-mail, agenda, cobrança, publicação) só em dois passos: prepara, a pessoa confirma.
