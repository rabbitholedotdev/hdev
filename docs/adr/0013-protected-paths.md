# ADR 0013 — Lista protegida do improve

- Status: aceito (desenho da v2, seção 5a, linha 12 da tabela)
- Data: 2026-11-20

## Contexto

O `hdev improve` propõe candidatas que mexem no próprio harness. Uma candidata que afrouxa um guarda, o teto ou o juiz ganharia na métrica de custo e perderia a segurança. O desenho pede uma lista do que nenhuma candidata toca, e que essa lista só mude por ADR.

## Decisão

- A lista mora em `harness/protected.txt`, um prefixo por linha. Pasta termina em `/`.
- Entram: os hooks (`hooks/`, `harness/hooks/`, onde moram os padrões de segredo e destrutivo), `harness/prompts/_shared/`, a deny list (`hdev/sync.py` e o `.claude/settings.json` gerado), os tetos (`hdev/check.py`, `hdev/config.py`), o juiz (`hdev/judge.py`, `hdev/gates/judge/`), o próprio `hdev/improve/`, esta lista e `.github/CODEOWNERS`.
- O desenho escreve `hdev/gates/check.py`; o caminho real é `hdev/check.py`. Os tetos também moram em `hdev/config.py` (`CAP_CEILING`).
- A linha `overlays` do `hdev check` falha quando um arquivo de `.hdev/overlays/<cand>/` ou um `remove` da ficha cai num prefixo da lista, e nomeia o caminho. O `hdev improve probe` recusa a mesma candidata antes de rodar.

## Consequências

- Mudar a lista é mudar `harness/protected.txt`, e isso pede ADR nova.
- O check cobra só a lista protegida. O que a candidata pode editar (papel, skill que não guarda, `tools.md`, `docs/padroes/defaults.md`, botões do manifesto) fica no texto do desenho; a PR13 decide se vira regra.
