// SQLite do app (APPS.md, "Banco"): WAL, busy_timeout, foreign_keys, migrações numeradas em migracoes/.
import { DatabaseSync } from 'node:sqlite';
import fs from 'node:fs';
import path from 'node:path';

const MIGRACOES = path.join(import.meta.dirname, '..', 'migracoes');

export function abrirBanco(arquivo) {
  fs.mkdirSync(path.dirname(arquivo), { recursive: true });
  const db = new DatabaseSync(arquivo);
  db.exec('PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 15000; PRAGMA foreign_keys = ON;');
  migrar(db);
  return db;
}

function migrar(db) {
  const atual = db.prepare('PRAGMA user_version').get().user_version;
  const arquivos = fs.readdirSync(MIGRACOES).filter((a) => /^\d{3}-.+\.sql$/.test(a)).sort();
  for (const a of arquivos) {
    const versao = Number(a.slice(0, 3));
    if (versao <= atual) continue;
    db.exec('BEGIN IMMEDIATE');
    try {
      db.exec(fs.readFileSync(path.join(MIGRACOES, a), 'utf8'));
      db.exec(`PRAGMA user_version = ${versao}`);
      db.exec('COMMIT');
    } catch (e) {
      db.exec('ROLLBACK');
      throw new Error(`migração ${a} falhou: ${e.message}`);
    }
  }
}

// transação curta; se a função lançar, desfaz
export function transacao(db, fn) {
  db.exec('BEGIN IMMEDIATE');
  try { const r = fn(); db.exec('COMMIT'); return r; }
  catch (e) { db.exec('ROLLBACK'); throw e; }
}
