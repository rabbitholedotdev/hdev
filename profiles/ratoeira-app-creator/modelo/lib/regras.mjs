// A camada de regras, uma só (APPS.md, regra de ouro 6): tela e ferramenta chamam estas funções,
// e é aqui que mora o "pode ou não pode" de cada papel.
import { transacao } from './banco.mjs';

export class Recusa extends Error {
  constructor(mensagem, status = 403) { super(mensagem); this.status = status; }
}

export function criarRegras(db) {
  return {
    // pessoa nova nasce no primeiro pedido; nome e papel vêm da Ratoeira a cada pedido
    tocarPessoa(pessoa) {
      transacao(db, () => db.prepare(
        `INSERT INTO pessoas (email, nome, papel, visto_em) VALUES (?, ?, ?, ?)
         ON CONFLICT(email) DO UPDATE SET nome = excluded.nome, papel = excluded.papel, visto_em = excluded.visto_em`,
      ).run(pessoa.email, pessoa.nome, pessoa.papel, Date.now()));
    },
    estado(pessoa) {
      const total = db.prepare('SELECT count(*) AS n FROM pessoas').get().n;
      return { eu: pessoa, pessoas: pessoa.papel === 'admin' ? total : undefined };
    },
    soAdmin(pessoa) {
      if (pessoa.papel !== 'admin') throw new Recusa('Só quem é admin do app pode fazer isso.');
    },
  };
}
