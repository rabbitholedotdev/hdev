// Tela do {{titulo}}. Sem a ponte (fora da Ratoeira), window.ratoeira não existe: tudo com ratoeira?.
const BASE = location.pathname.replace(/\/[^/]*$/, '');
const ESCRITA = { 'x-{{nome}}': '1', 'content-type': 'application/json' };

// pilha das janelas internas: cada card/gaveta/formulário avisa o chat ao abrir e ao fechar (APPS.md, "Tela")
const pilha = [];
export function abrirDetalhe(texto) { pilha.push(texto); window.ratoeira?.tela({ detalhe: pilha.join(' › ') }); }
export function fecharDetalhe() { pilha.pop(); window.ratoeira?.tela({ detalhe: pilha.length ? pilha.join(' › ') : null }); }

async function api(caminho, opcoes = {}) {
  const r = await fetch(BASE + caminho, opcoes.method && opcoes.method !== 'GET' ? { ...opcoes, headers: ESCRITA } : opcoes);
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(corpo.erro || `erro ${r.status}`);
  return corpo;
}

async function carregar() {
  const status = document.getElementById('status');
  try {
    const d = await api('/api/estado');
    document.getElementById('estado').textContent = `Olá, ${d.eu.nome} (${d.eu.papel}).`;
    status.textContent = '';
  } catch (e) { status.textContent = e.message; }
}

const perguntar = document.getElementById('perguntar');
if (window.ratoeira) {
  perguntar.hidden = false;
  // botão que pede algo ao chat: o texto já diz onde ficam os dados (agente/AGENTS.md)
  perguntar.onclick = () => window.ratoeira.chat.nova('Olhando o app {{titulo}}, me diz o que está pendente pra mim.');
  window.ratoeira.aoTerminar(carregar);
}
carregar();
