# Portão do brief

Leia este arquivo só no passo 2. Grave `work/<id>/brief.md`.

## Como perguntar
Uma decisão por vez, só pela ferramenta de pergunta. A opção recomendada vem primeiro. O que não foi perguntado vira default anunciado na seção Suposições, com como reverter. Não pergunte o que o repo ou `docs/padroes/defaults.md` já responde.

## Portão
Os quatro fecham, e o dono confirma o resumo (a última pergunta):

- Fronteira de decisão vazia: nenhuma escolha de produto em aberto.
- Taxonomia clara: cada ponto está decidido, é default anunciado ou está fora de escopo.
- Ambiguidade ≤ 0,2: no máximo um ponto em cinco ainda cabe em mais de um sentido. Não há medidor; é juízo. Se passar, pergunte aquele ponto ou anuncie o default.
- O resumo, em um parágrafo, é o que o dono confirmou.

## Molde

```
# Brief — <id>

## Resumo
<o parágrafo confirmado>

## Taxonomia
- <ponto>: decidido | default | fora de escopo

## Suposições
| Dúvida | Default | Reverter |
| --- | --- | --- |
| <o que não foi perguntado> | <o padrão anunciado> | <como voltar atrás> |

## Fora de escopo
- ...

## Opções
<preenchida no passo 3>
```
