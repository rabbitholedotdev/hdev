# Estágios

Leia só neste passo. A ordem é fixa. Cada achado é Blocker, Major ou Nit. Zero Blocker no fim para passar. Se um estágio falha, a spec é corrigida e aquele estágio reaudita uma vez. A segunda falha encerra: a review fica no-go e o autor reescreve a spec fora desta sessão.

1. Compreensão. Reescreva o pedido com as suas palavras, sem completar o que a spec não diz. Se não fecha, é Blocker.
2. Completude. Tem de haver aceite em comando, fora de escopo e a tabela dúvida → default → reverter. Buraco que impede implementar é Blocker.
3. Prontidão. Um implementador começa sem perguntar. Falta de arquivo ou de comando é Major; se trava o primeiro passo, é Blocker.
4. Riscos. Segurança, dado, irreversível. Risco sem dono nem default é Major.

Não instale o plugin EGM. Não use Spec Kit, BMAD nem OpenSpec.
