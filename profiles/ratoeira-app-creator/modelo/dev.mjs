// Desenvolvimento local, sem a Ratoeira: sobe o app e um proxy que faz o papel do gateway (assina a identidade).
//   npm run dev                          → http://localhost:<porta+1000>/{{nome}}/ como dev@local, papel admin
//   APP_PAPEL=membro npm run dev         → como membro
// Fora da Ratoeira não há /_ratoeira/app.js: a tela segue sem chat (window.ratoeira?.).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { assinarIdentidade } from './lib/identidade.mjs';

const RAIZ = import.meta.dirname;
const M = JSON.parse(fs.readFileSync(path.join(RAIZ, 'ratoeira-app.json'), 'utf8'));
const SEGREDO = randomBytes(32).toString('base64');
const PORTA_APP = M.porta, PORTA_DEV = M.porta + 1000, BASE = '/' + M.nome;
const email = process.env.APP_EMAIL || 'dev@local', papel = process.env.APP_PAPEL || M.papeis[0];

const app = spawn(process.execPath, ['--disable-warning=ExperimentalWarning', 'servidor.mjs'], {
  cwd: RAIZ, stdio: 'inherit',
  env: { ...process.env, PORTA: String(PORTA_APP), DADOS: path.join(RAIZ, '.dados'), RATOEIRA_SEGREDO: SEGREDO },
});

http.createServer((req, res) => {
  if (req.url.startsWith('/_ratoeira/')) { res.writeHead(200, { 'content-type': 'text/javascript' }); return res.end('// sem a ponte fora da Ratoeira'); }
  const headers = { ...req.headers, 'x-ratoeira-identidade': assinarIdentidade({ email, papel, app: BASE, segredo: SEGREDO }) };
  const p = http.request({ host: '127.0.0.1', port: PORTA_APP, path: req.url, method: req.method, headers }, (r) => {
    res.writeHead(r.statusCode, r.headers); r.pipe(res);
  });
  p.on('error', () => { res.writeHead(502); res.end('app ainda subindo'); });
  req.pipe(p);
}).listen(PORTA_DEV, '127.0.0.1', () => console.log(`dev: http://localhost:${PORTA_DEV}${BASE}/ como ${email} (${papel})`));

for (const sinal of ['SIGTERM', 'SIGINT']) process.on(sinal, () => { app.kill(); process.exit(0); });
