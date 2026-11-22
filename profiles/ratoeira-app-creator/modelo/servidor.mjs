// {{titulo}}: {{descricao}}
// Padrão: $HDEV_APPS_MD. Só stdlib do Node 22 (node:http, node:sqlite).
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { abrirBanco } from './lib/banco.mjs';
import { lerSegredo, conferirIdentidade } from './lib/identidade.mjs';
import { criarRegras, Recusa } from './lib/regras.mjs';

const RAIZ = import.meta.dirname;
const MANIFESTO = JSON.parse(fs.readFileSync(path.join(RAIZ, 'ratoeira-app.json'), 'utf8'));
const PORTA = Number(process.env.PORTA || MANIFESTO.porta);
const BASE = process.env.RATOEIRA_BASE || '/' + MANIFESTO.nome;
const DADOS = process.env.DADOS || path.join(RAIZ, '.dados');
const SEGREDO = lerSegredo();
const ESCRITA = 'x-{{nome}}'; // cabeçalho que formulário de outro site não manda

const db = abrirBanco(path.join(DADOS, '{{nome}}.db'));
const regras = criarRegras(db);

const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml' };
const TELA = path.join(RAIZ, 'tela');

function responder(res, status, corpo, tipo = 'application/json') {
  const dados = tipo === 'application/json' ? JSON.stringify(corpo) : corpo;
  res.writeHead(status, { 'content-type': tipo, 'cache-control': 'no-store', 'x-content-type-options': 'nosniff', 'x-frame-options': 'SAMEORIGIN' });
  res.end(dados);
}

async function lerCorpo(req, max = 300_000) {
  let texto = '';
  for await (const parte of req) { texto += parte; if (texto.length > max) throw new Recusa('Pedido grande demais.', 413); }
  try { return texto ? JSON.parse(texto) : {}; } catch { throw new Recusa('JSON inválido.', 400); }
}

const servidor = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://x');
  let caminho = url.pathname;
  if (caminho === BASE) { res.writeHead(302, { location: BASE + '/' }); return res.end(); }
  if (caminho.startsWith(BASE + '/')) caminho = caminho.slice(BASE.length);

  try {
    if (caminho === '/saude') return responder(res, 200, { ok: true });

    // ---------- daqui pra baixo, só com a identidade da Ratoeira
    const pessoa = conferirIdentidade(req.headers['x-ratoeira-identidade'], { segredo: SEGREDO, app: BASE, papeis: MANIFESTO.papeis });
    if (!pessoa) {
      if (caminho.startsWith('/api/')) return responder(res, 401, { erro: 'Abra pela Ratoeira.' });
      return responder(res, 401, '<!doctype html><meta charset="utf-8"><title>{{titulo}}</title><p style="font:15px system-ui;margin:40px">Abra pela Ratoeira.</p>', MIME['.html']);
    }
    if (req.method !== 'GET' && req.headers[ESCRITA] !== '1') return responder(res, 403, { erro: 'Pedido sem o cabeçalho do app.' });
    regras.tocarPessoa(pessoa);

    if (caminho === '/api/estado' && req.method === 'GET') return responder(res, 200, regras.estado(pessoa));
    if (caminho === '/api/eco' && req.method === 'POST') return responder(res, 200, { recebido: await lerCorpo(req) });

    // tela (estática)
    if (req.method === 'GET') {
      const nome = caminho === '/' ? 'index.html' : caminho.slice(1);
      const arq = path.join(TELA, path.normalize(nome));
      if (arq.startsWith(TELA + path.sep) && fs.existsSync(arq) && fs.statSync(arq).isFile())
        return responder(res, 200, fs.readFileSync(arq), MIME[path.extname(arq)] || 'application/octet-stream');
    }
    return responder(res, 404, { erro: 'Não encontrado.' });
  } catch (e) {
    if (e instanceof Recusa) return responder(res, e.status, { erro: e.message });
    console.error(e);
    return responder(res, 500, { erro: 'Erro interno. Tente de novo; se repetir, use o botão Reportar da Ratoeira.' });
  }
});

servidor.listen(PORTA, '127.0.0.1', () => console.log(`{{nome}} em http://127.0.0.1:${PORTA}${BASE}/ (dados em ${DADOS})`));

for (const sinal of ['SIGTERM', 'SIGINT']) process.on(sinal, () => { servidor.close(); try { db.close(); } catch {} process.exit(0); });
