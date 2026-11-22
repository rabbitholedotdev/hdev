# Padrão de nomes: desenvolvimento em inglês

Regra do núcleo (F2-10, ADR 0011): o padrão de desenvolvimento da Ratoeira é inglês. Conferida pela checagem `names`
do `hdev check`.

## Regra
- Inglês: tudo que é estrutura de desenvolvimento **novo**: repo, pasta, arquivo, branch, worktree, id/slug de
  unidade e de app, identificador de código (função, classe, variável, módulo), chave de config/JSON, nome de teste,
  nome de comando e de flag novos. ASCII, minúsculas e hífen em caminhos e branches.
- Arquivo segue a convenção da linguagem (`README.md`, `test_x.py`): maiúscula, `_` e `.` não são checados.

## O que fica em pt-BR
Prosa para pessoas: docs de produto, `docs/progress.md`, specs e planos (o texto), textos da UI e mensagens de app
para público brasileiro (APPS.md), mensagens ao operador. Commits: o formato do ADR 0009 continua
(`<ID> feito: <resumo>; juiz pass|override`, `<ID>: <efeito>`, `release: vX.Y.Z`); o texto livre pode ser pt-BR. O
marcador ` feito: ` é contrato de ferramenta e não muda.

## Legado
Não se renomeia por esta regra: `espacos.json` do core do host, pastas e repos existentes (consumer apps),
comandos e flags do próprio hdev (`fechar`, `--marcar`), a branch/tag `unidade/<ID>`
(ADR 0009) e o modelo do perfil ratoeira-app-creator. Renomear legado é decisão do operador.

## Portão (`hdev check`, linha `names`)
- Olha só o que é novo desde a base da unidade (`--base REF`, ou a base de `.hdev/state/bases.json`, ou o último
  commit `... feito: ...`, ou `HEAD`): caminhos do diff (árvore, índice, não rastreados) e a branch atual.
- Não-ASCII (qualquer caractere acima de 127) num nome novo: `FALHA` e exit 1 com `mode: fail` (padrão da v0.6.0,
  inclusive sem chave `naming`); aviso e exit 0 com `mode: warn`.
- Palavra em português sem acento (lista abaixo, ou sufixo `cao`/`coes` com 5+ letras): sempre aviso, nunca falha.
- Config em `.hdev/config.json`: `"naming": {"mode": "warn|fail|off", "allow_words": [...], "allow_paths": [...]}`.
  `allow_words` soma-se ao padrão `unidade`; `allow_paths` são globs `fnmatch` contra o caminho do segmento.
- Voltar um repo a `warn`: `"naming": {"mode": "warn"}`. O núcleo continua em `fail`.
- Identificador, chave de JSON, comando e flag ficam na revisão do diff (`revisar-diff`), não no portão.

## Lista de palavras em português (`PT_WORDS`)
Fonte da verdade: `hdev/naming.py`; um teste confere esta cópia.

`arquivo, arquivos, banco, cliente, clientes, conta, contas, conteudo, criar, dados, documento, documentos, empresa, enviar, equipe, espaco, espacos, ferramenta, ferramentas, imagem, imagens, modelo, modelos, nome, nomes, nova, novo, acao, acoes, botao, botoes, padrao, padroes, sessao, sessoes, pagina, paginas, painel, pasta, pastas, pedido, pedidos, plano, planos, preco, precos, produto, produtos, projeto, projetos, publicar, rascunho, relatorio, relatorios, rotina, rotinas, salvar, servico, servicos, tarefa, tarefas, tela, telas, teste, testes, unidade, usuario, usuarios`
