# Parada

## stop-list

Única lista. Fora dela o agente não para: escolhe o padrão de `docs/padroes/defaults.md`, escreve uma linha em `docs/decisions.md` e segue. Dentro dela, grava com `hdev resume --reason "<motivo>" --next "<próximo passo>"` (linha `PAREI: … | próximo: …` em `.hdev/state/parei`). `hdev resume` retoma.

Para só quando o próximo passo for um destes:

- 2FA, login ou código de verificação;
- ação destrutiva ou irreversível: apagar fora do repo, sudo, publicar, push, firewall, outra VM ou área da Ratoeira.

`stop.standing_ok` no manifesto cobre um item desta lista. Esse item não para: grava `READY-TO-PUBLISH: <unidade> | <o quê>` em `.hdev/state/ready-to-publish` e segue para a próxima unidade. Sem a chave, publicar continua parada.
