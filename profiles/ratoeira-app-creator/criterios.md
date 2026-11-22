# Critérios de uma peça de app (ratoeira-app-creator)

Copie para o "Critério de pronto" do plano o que se aplica. Os mecânicos o `hdev judge` vê pelos testes e pelo
`hdev app check`; os `[juiz]` ele julga lendo o diff.

## Mecânicos
- `hdev app check apps/<nome>` verde: manifesto só com campos conhecidos, nome = pasta, porta livre, papéis, chaves só
  por nome, rotinas válidas; README, `agente/AGENTS.md`, `migracoes/001-...`; teste; nenhum `.env`/`.pem`; só
  `127.0.0.1`; toda página carrega `/_ratoeira/app.js`.
- Testes do app verdes, com: 401 sem identidade (e adulterada, vencida, de outro app, papel estranho); 403 em escrita
  sem o cabeçalho do app; migrações aplicadas com `user_version`.
- Migração já publicada não foi editada: mudança nova é um arquivo novo.

## [juiz]
- Uma camada de regras: a permissão de cada papel mora nas funções que tela e ferramenta chamam, não na rota.
- Efeito fora do app (e-mail, agenda, cobrança, publicação) em dois passos, com confirmação de pessoa.
- Sem login, cadastro ou chat próprio; sem Docker para app nosso; SQLite em `$DADOS`, nada de dado na pasta do código.
- O app relê do disco o que o agente pode mudar por fora; `agente/AGENTS.md` diz onde fica cada dado novo.
- Janela interna (card, gaveta, formulário) chama `ratoeira.tela({detalhe})` ao abrir e com `null` ao fechar.
- Tela com tema claro e escuro (`data-ratoeira-tema`). Recomendado, não reprova sozinho.
- Textos e nomes em pt-BR; README e `agente/AGENTS.md` atualizados com a mudança.
- "No ar" só se a evidência mostra `estado_publicacao` ok; teste local não é estar no ar.
