# Plano — v2-pr11-library

Spec: sem spec (pedido fechado do dono: biblioteca de lições entre peças; a spec nova não cabe nesta PR)

## Objetivo
A base fica curta. Cada peça puxa poucas lições sob um teto de tokens, em vez de crescer o AGENTS.md.

## Critério de pronto
- `bin/hdev library pull --spec tests/fixtures/spec-ok.md --k 5 --budget 1500` sai 0, lista no máximo 5 itens e o total de tokens de lição fica dentro de 1500.
- `bin/hdev library pull --root tests/fixtures/library-cut --spec spec.md --k 5 --budget 1500` sai 0 e mostra o corte: há mais de 5 acertos e só 5 entram.
- `python3 -m unittest tests.test_library -q` sai 0. Cobre: ordem BM25, escopo e `not_for`, orçamento e teto de 2 skills, candidata em no máximo 2 vagas, modo sintoma, corte de generalização, dedup que junta, segundo modelo falso que descarta e o caso `pending`, vitória e derrota no fechar, fórmula do ponto, cada transição do ciclo, `active` para `core` só na lista, tetos do check.
- `bin/hdev reflect --unit v2-pr10-graphify --offline` sai 0 e imprime o digest. `bin/hdev library status` sai 0. `bin/hdev library tidy` sai 0 e, na segunda vez, o mesmo resultado.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem e o tempo.
- `bin/hdev check` sai 0, linha `library` verde, skills 5/5, hooks 5 registros e 3 arquivos, xray abaixo do teto.
- `bin/hdev sync --check` sai 0.
- `bin/hdev fechar --plan work/v2-pr11-library/plan.md --dry-run` sai 0.
- [juiz] cada item aponta para um comando e a saída em `work/v2-pr11-library/evidence/aceite.md`.

## Abordagem
Stdlib, pacote `hdev/library/`. O índice é `library/index.jsonl`. O corpo mora em `library/lessons/`, `library/skills/` ou `library/scripts/`. Campo extra `generalization` (`checked` ou `pending`) e `retired_on` quando aposenta.

`not_for` tira o item quando metade ou mais dos termos de conteúdo (3+ letras, sem stopword) aparece na consulta. Vazio não tira. BM25 usa título, `when_to_use` e tags. Dedup é o BM25 do par dividido pelo score do texto contra ele mesmo; limiar `0.52`. Acima disso a evidência entra no item que já existe.

Sem provedor, ou com `--offline`, a lição fica `generalization: pending` e não promove. O segundo modelo passa pela cadeia do juiz (`judge` / `judge_fallback`). `fail` descarta. `pass` marca `checked`.

Ponto = `(wins + 1) / (wins + losses + 2) × 0.5 ^ (dias sem uso / 60)`. O `hdev library tidy` promove, aposenta e apaga. Repetir no mesmo dia não muda. O `hdev fechar` pass chama os dois. `--dry-run` não pontua.

Jev `rotear` sem chave (exit 2). Segui sem worker. Juiz grok não roda nesta VM.

## Passos
1. Testes que falham: pull, reflect, pontos, fechar, check.
2. Implementar até `tests.test_library` passar.
3. Semear 5 lições reais com `hdev reflect --add --offline`.
4. `hdev check`, `hdev sync --check` e a suíte verdes.
5. `hdev fechar --plan work/v2-pr11-library/plan.md --dry-run` (marco pulado, exit 0).
6. Juiz grok no operator host.

## Testes
- `tests/test_library.py` — pull, reflect, ciclo, fechar, tetos
- `python3 -m unittest discover -s tests -q` — o resto não quebra

## Fora de escopo
- Skill nova, hook novo, dependência nova. `VERSION` parado. `releases/v*/` congelado.
- Promover `core` nesta PR. A lista só mostra quem está elegível.
- Rodar o juiz grok, o Codex, um claude real ou qualquer API paga.
- `hdev base --marcar` neste repo. Mexer em `master` ou fazer merge.

## Riscos
- Com 22 rótulos o juiz barra. A evidência em `work/v2-pr11-library/evidence/` tem de fechar cada item do critério.
- `docs/progress.md` está no teto de 2.000. A linha dos 22 rótulos e a do cache ficam.
