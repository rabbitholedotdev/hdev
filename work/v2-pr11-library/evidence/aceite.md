# Evidência — aceite

Comandos no HEAD `bc2d07b`. A suíte `discover` desse código: `Ran 509 tests in 123.609s` OK. O aviso de arquivo aberto em `tests/test_naming.py` já existia; o teste novo não imprime sha, caminho temporário nem horário. Esta página não muda comando. Check, sync, pull, reflect, status, tidy e o dry-run do fechar foram repetidos no commit que a inclui.

Juiz grok não rodou. Codex não rodou. Nenhum claude real foi chamado. Jev `rotear` saiu 2 (sem chave).

## 1. pull na spec de exemplo

`bin/hdev library pull --spec tests/fixtures/spec-ok.md --k 5 --budget 1500`

exit=0. 2 itens, 71 tok, teto 1500. As cinco lições semeadas são candidatas, e candidata ocupa no máximo 2 vagas. Por isso 4 acertos viram 2.

```
lesson-0005  candidata  3.5342  39 tok
quando o teste imprime caminho temporário ou horário de corrida, faça o teste calar esses valores, porque a chave do juiz muda e o cache não acerta.

lesson-0002  candidata  2.5748  32 tok
quando a prova precisa ser lida pelo juiz, faça o arquivo na pasta de evidência da unidade, porque fora dela o juiz não lê.

corte: 2 itens de 4, 2 de fora, 71 tok de lição (teto 1500), 0 skills
```

## 2. pull com mais de 5 acertos

`bin/hdev library pull --root tests/fixtures/library-cut --spec spec.md --k 5 --budget 1500`

exit=0. 8 acertos, entram 5, 3 ficam de fora. 125 tok, teto 1500.

```
corte: 5 itens de 8, 3 de fora, 125 tok de lição (teto 1500), 0 skills
```

Os cinco primeiros são `lesson-0001` … `lesson-0005`, todos ativos, 25 tok cada.

## 3. suíte da biblioteca

`python3 -m unittest tests.test_library -q`

exit=0.

```
Ran 30 tests in 0.702s

OK
```

Cobre ordem BM25, escopo, `not_for`, orçamento, 2 skills, 2 vagas de candidata, sintoma, corte e forma, dedup, segundo modelo falso, `pending`, vitória e derrota no fechar, fórmula, transições, core só na lista, tetos.

## 4. reflect, status, tidy

`bin/hdev reflect --unit v2-pr10-graphify --offline` exit=0. O digest abre com `unidade: v2-pr10-graphify`, traz o plano, a evidência da unidade, `paradas: (nenhuma)`, `juiz: (nenhum)`, `eval: (nenhum)`.

`bin/hdev library status` exit=0.

```
biblioteca: 5 itens, 0 ativas, 0 core, 5 candidatas, 0 aposentadas
elegível pra core: nenhuma
```

`bin/hdev library tidy` duas vezes, exit=0 as duas, a mesma stdout:

```
tidy: promovidas 0, aposentadas 0, apagadas 0
```

O índice não mudou na segunda. O dry-run do fechar também não pontuou.

## 5. suíte inteira

`python3 -m unittest discover -s tests -q` exit=0. `Ran 509 tests in 123.609s` OK.

## 6. check

`bin/hdev check` exit=0.

```
[ok] agents: 42/60 linhas, perfil 5/30
[ok] hooks: 5 registros, 3 arquivos (pre_tool.py, session.py, stop_gate.py)
[ok] skills: visíveis F0 1/5, F1 5/5, F2 5/5; descriptions <= 200
[ok] xray: estimativa 1868/15000
[ok] graph: só o explorer; query, path, explain
[ok] library: 5 itens, 0 ativas (teto 60); lições <= 3 linhas
[ok] names: base 77fbd1d (fechamento), mode fail, 215 segmentos novos, 0 não-ASCII, 0 avisos
```

## 7. sync

`bin/hdev sync --check` exit=0. `settings.json` bate com o manifesto. Stop do Codex e do Grok também.

## 8. fechar

`bin/hdev fechar --plan work/v2-pr11-library/plan.md --dry-run` exit=0. Marco pulado. Detalhe em `work/v2-pr11-library/evidence/fechar-dry-run.md`.

## Regra not_for

Termos de conteúdo: 3 letras ou mais, sem acento, fora da lista de stopwords. O item sai quando a fração desses termos de `not_for` que aparece na consulta é maior ou igual a 0,5. `not_for` vazio não tira ninguém. Um termo só exige esse termo.

## Lições semeadas

`hdev reflect --unit v2-pr10-graphify --add work/v2-pr11-library/seed-items.json --offline --today 2026-11-20`. As cinco ficaram `candidate` com `generalization: pending`.

1. Chave de cache do juiz sem saída volátil.
2. Evidência na pasta da unidade, porque fora dela o juiz não lê.
3. Marco só na branch base.
4. Parada só na lista fechada.
5. Teste sem caminho temporário nem horário de corrida no log.

## Chamadas

- Dedup: BM25 do par dividido pelo score do texto contra ele mesmo. Limiar 0.52. Acima, a evidência entra no item que já existe.
- Sem provedor, ou com `--offline`, o item fica `pending` e não promove. `fail` do segundo modelo descarta. `pass` marca `checked`.
- `active` não vira `core` sozinho. `hdev library status` lista quem tem pelo menos 5 vitórias e taxa maior ou igual a 0,7.
- Campo extra no índice: `generalization` e `retired_on`.
- Vitória no fechar: o primeiro juiz do plano passou e não houve `PAREI` fora da lista fechada. Senão é derrota. `--dry-run` não grava.
- Item global da release (`.harnessdev/library/`) entra no pull e o reflect não escreve lá.
