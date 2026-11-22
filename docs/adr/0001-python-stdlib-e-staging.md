# ADR 0001 — Python só com stdlib; `.claude/` via staging na sessão headless

Data: 2026-11-14 · Estado: aceito (João pode trocar)

## Contexto
O núcleo precisa rodar em qualquer repo irmão sem instalar nada. A sessão overnight roda `claude -p` com
`--permission-mode acceptEdits`: escreve arquivos do repo, mas não executa `python3`, não commita e não escreve em `.claude/`.

## Decisão
1. Hooks e `hdev` em Python 3 só com stdlib; testes com `unittest`. Nada de pip, npm ou venv.
2. `bin/hdev` é chamado como `python3 bin/hdev` (o bit de execução não pôde ser posto pela sessão).
3. `.claude/settings.json` e `.claude/skills/brainstorm/SKILL.md` foram escritos em `staging/claude/`.
   `hdev init` aceita as duas origens enquanto o João não move; depois do `mv`, `staging/` some.

## Consequências
- `hdev check` na raiz fica vermelho (`hooks`, `skills`) até o `mv staging/claude .claude` (ver `docs/WAITING.md`).
- Nenhum teste foi executado nesta sessão; o primeiro run é do João (ou de uma sessão com permissão de execução).

## Atualização (2026-11-14, sessão com allowlist)
O João moveu para `.claude/` e pôs ali uma allowlist estreita. `staging/` foi removido e `hdev init` lê só de
`.claude/`; do `settings.json` copia apenas `hooks` (as `permissions` são deste repo, não do alvo).
Primeiro run: 65 testes verdes e `hdev check` verde.
