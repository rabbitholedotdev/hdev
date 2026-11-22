// Quem é a pessoa: cabeçalho x-ratoeira-identidade assinado pelo gateway (APPS.md, "Identidade").
import { createHmac, timingSafeEqual } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export function lerSegredo() {
  let s = (process.env.RATOEIRA_SEGREDO || '').trim();
  // na Ratoeira o systemd entrega o arquivo (LoadCredential=ratoeira-segredo:...)
  if (!s && process.env.CREDENTIALS_DIRECTORY) {
    try { s = fs.readFileSync(path.join(process.env.CREDENTIALS_DIRECTORY, 'ratoeira-segredo'), 'utf8').trim(); } catch {}
  }
  return s;
}

// Devolve {email, nome, papel} ou null. Recusa: sem cabeçalho, assinatura errada, vencido, outro app, papel estranho.
export function conferirIdentidade(cabecalho, { segredo, app, papeis }) {
  if (!segredo || segredo.length < 32 || typeof cabecalho !== 'string' || cabecalho.length > 4096) return null;
  const partes = cabecalho.split('.');
  if (partes.length !== 2) return null;
  const [payload, assinatura] = partes;
  const certa = createHmac('sha256', segredo).update(payload).digest();
  let veio;
  try { veio = Buffer.from(assinatura, 'base64url'); } catch { return null; }
  if (veio.length !== certa.length || !timingSafeEqual(veio, certa)) return null;
  let d;
  try { d = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8')); } catch { return null; }
  if (!d || typeof d.email !== 'string' || !d.email.includes('@')) return null;
  if (typeof d.exp !== 'number' || d.exp < Math.floor(Date.now() / 1000)) return null;
  if (d.app !== app) return null;
  // sem papel definido: vale o último da lista (o app nasce liberado)
  const papel = d.papel == null ? papeis[papeis.length - 1] : d.papel;
  if (!papeis.includes(papel)) return null;
  return { email: d.email.toLowerCase(), nome: String(d.nome || d.email), papel };
}

// pros testes e pro dev.mjs: gera um cabeçalho como o gateway geraria
export function assinarIdentidade({ email, nome = email, papel, app, segredo, exp = Math.floor(Date.now() / 1000) + 60 }) {
  const payload = Buffer.from(JSON.stringify({ email, nome, app, papel, exp })).toString('base64url');
  return payload + '.' + createHmac('sha256', segredo).update(payload).digest('base64url');
}
