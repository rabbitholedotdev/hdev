# Progresso

Atualizado 2026-11-20. Teto 2.000 caracteres. Decisões duráveis: `docs/decisions.md`.

## Pronto
- F0+F1 (15/11, juiz grok). F2-03..F2-06 = v0.3.6..v0.3.9 (ADR 0005..0008).
- v0.4.0 (ADR 0009) fechar/tag/CHANGELOG; v0.4.1 lock; F2-09 / v0.4.2 (ADR 0010) juiz por partes.
- F2-10 / v0.5.0 (ADR 0011). F2-11 / v0.6.0 no latest (47c348a, juiz pass, Codex go).
- Juiz: 22 rótulos (20/11); consultivo só abaixo de 20.
- v0.7.0: triage, sync, papéis, juiz em pacote, fechar, eval, xray, parada, cache de código.
- v0.8.0: improve compose/revert, braço real do eval (Sonnet), Stop do handoff, janela por modelo, caso não rastreado do fechar.
- v0.8.1/v0.8.2: etiqueta do app da Ratoeira barra escrita em código (CHIP-001); a 0.8.2 tira o NotebookEdit do matcher.
- v0.8.3: a etiqueta do app também barra escrita por interpretador (CHIP-002); o check do app tolera o matcher com ou sem NotebookEdit (NBK-001).
- v0.8.4: o NotebookEdit volta ao matcher do PreToolUse de edição (NBK-002); os apps recebem no próximo `hdev sync`.
- Braço real do eval: `--runner claude` com Sonnet (eval e probe).

## Falta
- `--single` da rotina no clone do host CLI (`grok-single`); o núcleo não publica sozinho.
- v2 PR1–PR13: juiz grok no host do operador. PR10: cache. Parada fechada: GitHub #13. PR11: biblioteca. PR12: improve só em relatório. PR13: compose e revert.

## Lições
- Chave do cache do juiz sem saída volátil. Evidência na pasta da unidade.
- `hdev fechar` só cria o marco na branch base. Stop do handoff é da sessão que saiu.
- Jev sem chave sai 2 e o fluxo segue. Não ecoar a chave.
- Tetos: AGENTS.md 60. Hooks 5/3. Skills visíveis ≤ 5. Subagentes 2.
- Biblioteca: `hdev library pull` depois da spec; `hdev reflect` depois do fechar. Prompt nasce no install novo.
