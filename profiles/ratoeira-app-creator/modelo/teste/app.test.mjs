// Testes do {{titulo}}: o servidor de verdade numa porta livre, com identidade assinada como o gateway.   npm test
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import net from 'node:net';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { assinarIdentidade } from '../lib/identidade.mjs';

const RAIZ = path.join(import.meta.dirname, '..');
const M = JSON.parse(fs.readFileSync(path.join(RAIZ, 'ratoeira-app.json'), 'utf8'));
const BASE = '/' + M.nome;
const SEGREDO = randomBytes(32).toString('base64');
const DADOS = fs.mkdtempSync(path.join(os.tmpdir(), `${M.nome}-teste-`));
let porta, servidor;

const portaLivre = () => new Promise((ok) => { const s = net.createServer().listen(0, '127.0.0.1', () => { const p = s.address().port; s.close(() => ok(p)); }); });
const identidade = (extra = {}) => assinarIdentidade({ email: 'ana@exemplo.invalid', papel: M.papeis[0], app: BASE, segredo: SEGREDO, ...extra });
const pedir = (caminho, { headers = {}, ...op } = {}) => fetch(`http://127.0.0.1:${porta}${BASE}${caminho}`, { ...op, headers });

before(async () => {
  porta = await portaLivre();
  servidor = spawn(process.execPath, ['--disable-warning=ExperimentalWarning', 'servidor.mjs'], {
    cwd: RAIZ, env: { ...process.env, PORTA: String(porta), DADOS, RATOEIRA_SEGREDO: SEGREDO }, stdio: 'pipe',
  });
  for (let i = 0; i < 100; i++) {
    try { if ((await fetch(`http://127.0.0.1:${porta}${BASE}/saude`)).ok) return; } catch {}
    await new Promise((r) => setTimeout(r, 50));
  }
  throw new Error('o servidor não subiu');
});
after(() => { servidor?.kill(); fs.rmSync(DADOS, { recursive: true, force: true }); });

test('saúde responde sem login', async () => {
  assert.equal((await pedir('/saude')).status, 200);
});

test('sem identidade, ou adulterada, ou de outro app: 401', async () => {
  assert.equal((await pedir('/api/estado')).status, 401);
  assert.equal((await pedir('/')).status, 401);
  const [payload] = identidade().split('.');
  assert.equal((await pedir('/api/estado', { headers: { 'x-ratoeira-identidade': payload + '.xxx' } })).status, 401);
  assert.equal((await pedir('/api/estado', { headers: { 'x-ratoeira-identidade': identidade({ app: '/outro' }) } })).status, 401);
  assert.equal((await pedir('/api/estado', { headers: { 'x-ratoeira-identidade': identidade({ exp: 1 }) } })).status, 401);
  assert.equal((await pedir('/api/estado', { headers: { 'x-ratoeira-identidade': identidade({ papel: 'dono-do-mundo' }) } })).status, 401);
});

test('com identidade: estado e tela', async () => {
  const r = await pedir('/api/estado', { headers: { 'x-ratoeira-identidade': identidade() } });
  assert.equal(r.status, 200);
  assert.equal((await r.json()).eu.email, 'ana@exemplo.invalid');
  const html = await (await pedir('/', { headers: { 'x-ratoeira-identidade': identidade() } })).text();
  assert.match(html, /\/_ratoeira\/app\.js/);
});

test('escrita sem o cabeçalho do app: 403; com ele: 200', async () => {
  const id = { 'x-ratoeira-identidade': identidade(), 'content-type': 'application/json' };
  assert.equal((await pedir('/api/eco', { method: 'POST', headers: id, body: '{}' })).status, 403);
  assert.equal((await pedir('/api/eco', { method: 'POST', headers: { ...id, [`x-${M.nome}`]: '1' }, body: '{"a":1}' })).status, 200);
});

test('migrações aplicadas com user_version', async () => {
  const { DatabaseSync } = await import('node:sqlite');
  const db = new DatabaseSync(path.join(DADOS, `${M.nome}.db`));
  assert.ok(db.prepare('PRAGMA user_version').get().user_version >= 1);
  db.close();
});
