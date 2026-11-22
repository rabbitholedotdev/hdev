# ADR 0010 — Juiz por partes, renames em lista e anexos validados

- Status: aceito
- Data: 2026-11-16
- Origem: a long consumer-app unit levou 7 juízes (2 fail, 4 unsure) até o pass; pedido do João
  (16/11, 04:43 -03): "Resolve esse problema da reprovação do juiz para agora e para o futuro".

## Contexto

O pacote do juiz tem teto de 200 mil caracteres (metade para o cabeçalho). A C9-01 moveu ~300 arquivos e criou
outros 29: o diff com renames tinha ~590 mil caracteres (7 milhões sem eles). O `fit_diff` mantinha blocos inteiros
até o teto e listava o resto só pelo nome, na ordem do git: 310–326 arquivos ficavam de fora, entre eles os de
lógica que o critério citava, e o registro do veredito não dizia isso. Anexos de evidência só entravam se o nome
contivesse o stem do plano; `c9-01-hunks-*.md` ficou invisível. O juiz respondeu `unsure` quatro vezes pelo mesmo
motivo e a sessão rejulgou em loop.

## Decisão

- `git diff -M -C -l20000` explícito no diff e no stat (não depende de `diff.renames` do usuário).
- Movimento puro (similarity 100%, sem hunk nem modo) sai do diff e vai para a seção `RENOMEADOS SEM MUDANÇA`
  (um por linha; agrupado por par de pastas se não couber).
- Se o resto do diff cabe, o pacote é o de antes. Senão, o diff é dividido em partes (lógica, testes, docs, resto),
  cada uma com o mesmo cabeçalho, um `MANIFESTO` (arquivo → parte) e uma nota na rubrica. O juiz é chamado por parte
  (até `judge.parallel`, padrão 3, em paralelo). `fail` em qualquer parte reprova; `pass` só com todas em pass.
- Teto de partes `judge.max_parts` (padrão 8). O que passa dele fica fora e é nomeado; com algo fora, `pass` vira
  `unsure`. Arquivo maior que uma parte entra cortado em fronteira de linha, com aviso no texto e no registro.
- O registro do veredito ganha `pacote` (partes, arquivos no diff, movimentos, cortados, omitidos, seções aparadas,
  anexos e anexos truncados) e `package_sha`.
- Anexos: o id da unidade (`C9-01`, `INF-008`) também casa o nome. Anexo citado no plano (`docs/evidence/...`) que não
  existe, está em subpasta ou não casaria pelo nome falha cedo (exit 64), antes de rodar testes e chamar o juiz.
- `unsure` traz `diagnostico` (o que ficou de fora, o que o juiz pediu, a CLI) e `unsure_seguidos`; a partir de 3,
  manda mudar o pacote ou o critério. Pacote idêntico ao do último `unsure` não é rejulgado (exit 64) sem `--rejulgar`.
- Exit codes e o formato do veredito não mudam; o core da Ratoeira não muda.

## Consequências

- Unidade grande custa N chamadas do juiz (tempo e cota); o paralelismo limita o tempo.
- Uma parte não vê as outras: o critério é julgado parte a parte, e a evidência no cabeçalho é a ponte.
- Rollback: `hdev rollback --to v0.4.1` (canal) ou a tag `v0.4.1` no código.
