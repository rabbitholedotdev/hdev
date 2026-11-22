# Caso — spec

Entrada: `work/<id>/brief.md` com a opção escolhida.
Saída: `work/<id>/spec.md` com aceite em comando, fora de escopo e tabela dúvida → default → reverter.
Portão: `bin/hdev spec check work/<id>/spec.md` sai 0. Sem a tabela, sai 1.
