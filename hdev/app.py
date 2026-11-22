"""hdev app — o padrão ratoeira-app-creator: `new` monta um app pelo modelo do perfil, `check` confere o
contrato mecânico do APPS.md do host (o que um comando consegue ver; o resto é do juiz).

O APPS.md (HDEV_APPS_MD, se definido) é a fonte da verdade no host: aqui fica só o que
foi extraído de apps reais e o mínimo para recusar cedo.
"""
import glob
import json
import os
import re

from . import CORE_ROOT
from .check import Result

PROFILE = os.path.join(CORE_ROOT, "profiles", "ratoeira-app-creator")
MODELO = os.path.join(PROFILE, "modelo")
NOME_RX = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
CHAVE_RX = re.compile(r"^[A-Z][A-Z0-9_]*$")
MIGRACAO_RX = re.compile(r"^(\d{3})-.+\.sql$")
# campos do manifesto (APPS.md, tabela do manifesto): campo desconhecido faz a publicação ser recusada
CAMPOS = {"nome", "titulo", "descricao", "porta", "preparar", "iniciar", "saude", "papeis", "publico", "pacotes",
          "chaves", "ambiente", "memoria", "cpu", "rotinas", "chat", "aparece", "icone"}
OBRIGATORIOS = ("nome", "titulo", "descricao", "porta", "iniciar", "papeis")
PULAR = {"node_modules", ".git", ".dados", "venv", ".venv", "__pycache__", ".pytest_cache"}
SEM_PONTE = {"publico", "docs", "comunidade", "agente"}  # páginas públicas, manuais e prints não levam a ponte
CODIGO = (".mjs", ".js", ".cjs", ".ts", ".py")
PORTA_INICIAL = 8800


def _arquivos(pasta):
    for raiz, dirs, nomes in os.walk(pasta):
        dirs[:] = [d for d in dirs if d not in PULAR]
        for n in nomes:
            yield os.path.join(raiz, n)


def _ler(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def manifesto(pasta):
    path = os.path.join(pasta, "ratoeira-app.json")
    if not os.path.isfile(path):
        return None, "falta ratoeira-app.json"
    try:
        data = json.loads(_ler(path))
    except ValueError as e:
        return None, "ratoeira-app.json inválido: %s" % e
    if not isinstance(data, dict):
        return None, "ratoeira-app.json não é um objeto"
    return data, None


def portas_usadas(areas, fora=None):
    """{porta: pasta} dos manifestos em <areas>/*/apps/*/ (fora = a pasta do próprio app)."""
    usadas = {}
    for path in glob.glob(os.path.join(areas, "*", "apps", "*", "ratoeira-app.json")):
        pasta = os.path.dirname(path)
        if fora and os.path.realpath(pasta) == os.path.realpath(fora):
            continue
        try:
            porta = json.loads(_ler(path)).get("porta")
        except (ValueError, AttributeError):
            continue
        if isinstance(porta, int):
            usadas[porta] = pasta
    return usadas


# ---------- check

def check_manifesto(pasta):
    m, err = manifesto(pasta)
    if err:
        return Result("manifesto", False, err)
    extra = sorted(set(m) - CAMPOS)
    if extra:
        return Result("manifesto", False, "campo desconhecido (a publicação recusa): %s" % ", ".join(extra))
    falta = [c for c in OBRIGATORIOS if c not in m]
    if falta:
        return Result("manifesto", False, "falta: %s" % ", ".join(falta))
    nome = m["nome"]
    if not isinstance(nome, str) or not NOME_RX.match(nome):
        return Result("manifesto", False, "nome %r: só minúsculas, números e hífen" % nome)
    if nome != os.path.basename(os.path.realpath(pasta)):
        return Result("manifesto", False, "nome %r diferente da pasta %r" % (nome, os.path.basename(pasta)))
    porta = m["porta"]
    if not isinstance(porta, int) or isinstance(porta, bool) or not 1024 <= porta <= 65535:
        return Result("manifesto", False, "porta %r fora de 1024..65535" % porta)
    papeis = m["papeis"]
    if not isinstance(papeis, list) or not papeis or not all(isinstance(p, str) and p for p in papeis) \
            or len(set(papeis)) != len(papeis):
        return Result("manifesto", False, "papeis: lista não vazia, sem repetir, do que pode mais pro que pode menos")
    chaves = m.get("chaves", [])
    if not isinstance(chaves, list) or not all(isinstance(c, str) and CHAVE_RX.match(c) for c in chaves):
        return Result("manifesto", False, "chaves: só nomes em MAIÚSCULAS (o valor nunca vai no manifesto)")
    for r in m.get("rotinas", []):
        if not isinstance(r, dict) or not r.get("nome") or not r.get("comando") \
                or ("quando" in r) == ("intervalo" in r):
            return Result("manifesto", False, "rotina %r: nome, comando e só um de quando/intervalo" % (
                r.get("nome") if isinstance(r, dict) else r))
    if "aparece" in m and m["aparece"] not in ("area", "todas"):
        return Result("manifesto", False, "aparece: \"area\" ou \"todas\"")
    if "icone" in m:
        icone = os.path.join(pasta, str(m["icone"]))
        if not os.path.isfile(icone) or os.path.splitext(icone)[1].lower() not in (".svg", ".png", ".webp") \
                or os.path.getsize(icone) > 256 * 1024:
            return Result("manifesto", False, "icone: .svg/.png/.webp na pasta do app, até 256 KB")
    return Result("manifesto", True, "%s, porta %d, papéis %s" % (nome, porta, "/".join(papeis)))


def check_porta(pasta, areas=None):
    m, err = manifesto(pasta)
    if err or not isinstance(m.get("porta"), int):
        return Result("porta", False, err or "sem porta")
    areas = areas or os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(pasta))))
    dono = portas_usadas(areas, fora=pasta).get(m["porta"])
    if dono:
        return Result("porta", False, "porta %d já é de %s" % (m["porta"], os.path.relpath(dono, areas)))
    return Result("porta", True, "%d livre entre os apps de %s" % (m["porta"], areas))


def check_esqueleto(pasta):
    falta = [rel for rel in ("README.md", os.path.join("agente", "AGENTS.md")) if not os.path.isfile(os.path.join(pasta, rel))]
    if falta:
        return Result("esqueleto", False, "falta %s" % ", ".join(falta))
    nums = sorted(int(MIGRACAO_RX.match(n).group(1)) for n in os.listdir(os.path.join(pasta, "migracoes"))
                  if MIGRACAO_RX.match(n)) if os.path.isdir(os.path.join(pasta, "migracoes")) else []
    if not nums:
        return Result("esqueleto", False, "falta migracoes/001-inicio.sql")
    if nums[0] != 1 or len(set(nums)) != len(nums):
        return Result("esqueleto", False, "migracoes/: numeração começa em 001 e não repete")
    return Result("esqueleto", True, "README, agente/AGENTS.md, %d migração(ões)" % len(nums))


def check_testes(pasta):
    for d in ("teste", "testes", "tests"):
        achados = [p for p in glob.glob(os.path.join(pasta, d, "**", "*"), recursive=True)
                   if os.path.isfile(p) and re.search(r"(^test_.*\.py$|\.test\.m?js$|_test\.py$)", os.path.basename(p))]
        if achados:
            return Result("testes", True, "%d arquivo(s) em %s/" % (len(achados), d))
    return Result("testes", False, "sem teste em teste/, testes/ ou tests/ (401 sem identidade é o mínimo)")


def check_segredos(pasta):
    ruins = []
    for p in _arquivos(pasta):
        n = os.path.basename(p)
        if (n == ".env" or (n.startswith(".env.") and n not in (".env.exemplo", ".env.example"))
                or n.endswith((".pem", ".key")) or n == "chaves.env" or n.startswith("id_rsa")):
            ruins.append(os.path.relpath(p, pasta))
    if ruins:
        return Result("segredos", False, "arquivo de segredo na pasta do código: %s" % ", ".join(sorted(ruins)[:5]))
    return Result("segredos", True, "nenhum .env/.pem/.key/chaves.env")


def check_escuta(pasta):
    m, _ = manifesto(pasta)
    textos = [(os.path.relpath(p, pasta), _ler(p)) for p in _arquivos(pasta) if p.endswith(CODIGO)]
    abertos = [rel for rel, t in textos if "0.0.0.0" in t]
    if abertos:
        return Result("escuta", False, "0.0.0.0 em %s (só 127.0.0.1)" % ", ".join(abertos[:3]))
    if not any("127.0.0.1" in t for _, t in textos) and "127.0.0.1" not in str((m or {}).get("iniciar", "")):
        return Result("escuta", False, "não achei 127.0.0.1 no código nem no iniciar")
    return Result("escuta", True, "só 127.0.0.1")


def check_tela(pasta):
    paginas, sem = 0, []
    for p in _arquivos(pasta):
        rel = os.path.relpath(p, pasta)
        if not p.endswith(".html") or rel.split(os.sep)[0] in SEM_PONTE:
            continue
        t = _ler(p).lower()
        if "<html" not in t and "<!doctype" not in t:
            continue  # parcial de template
        if "abra pela ratoeira" in t:
            continue  # a página do 401, servida justamente fora da Ratoeira
        paginas += 1
        if "/_ratoeira/app.js" not in t:
            sem.append(rel)
    if sem:
        return Result("tela", False, "página sem /_ratoeira/app.js: %s" % ", ".join(sorted(sem)[:5]))
    return Result("tela", True, "%d página(s) com a ponte" % paginas)


CHECKS = [check_manifesto, check_porta, check_esqueleto, check_testes, check_segredos, check_escuta, check_tela]


def run_check(pasta, areas=None):
    pasta = os.path.realpath(pasta)
    out = []
    for fn in CHECKS:
        try:
            out.append(fn(pasta, areas) if fn is check_porta else fn(pasta))
        except Exception as e:  # check quebrado vira falha, não traceback
            out.append(Result(fn.__name__.replace("check_", ""), False, "erro: %s" % e))
    return out


# ---------- new

def proxima_porta(areas, inicial=PORTA_INICIAL):
    usadas = portas_usadas(areas)
    porta = inicial
    while porta in usadas:
        porta += 1
    return porta


def new(nome, area, titulo=None, descricao=None, porta=None, areas=None):
    if not NOME_RX.match(nome or ""):
        raise ValueError("nome %r: só minúsculas, números e hífen (vira o endereço /%s/)" % (nome, nome))
    area = os.path.realpath(area)
    destino = os.path.join(area, "apps", nome)
    if os.path.lexists(destino):
        raise ValueError("%s já existe; não sobrescrevo" % destino)
    areas = os.path.realpath(areas or os.path.dirname(area))
    usadas = portas_usadas(areas)
    if porta is None:
        porta = proxima_porta(areas)
    elif isinstance(porta, bool) or not isinstance(porta, int) or not 1024 <= porta <= 65535:
        raise ValueError("porta %r fora de 1024..65535" % (porta,))
    elif porta in usadas:
        raise ValueError("porta %d já é de %s" % (porta, os.path.relpath(usadas[porta], areas)))
    titulo = titulo or nome.replace("-", " ").capitalize()
    descricao = descricao or "Descreva em uma linha o que o app faz."
    for campo, valor in (("titulo", titulo), ("descricao", descricao)):
        if re.search(r"[\"'`<>\\{}]", valor) or len(valor) > 200:
            raise ValueError("%s: texto simples, até 200 caracteres, sem aspas, crase, < > ou chaves" % campo)
    trocas = {"{{nome}}": nome, "{{titulo}}": titulo, "{{descricao}}": descricao, "{{porta}}": str(porta)}
    escritos = []
    for raiz, _, nomes in os.walk(MODELO):
        for n in nomes:
            src = os.path.join(raiz, n)
            rel = os.path.relpath(src, MODELO)
            texto = _ler(src)
            for k, v in trocas.items():
                texto = texto.replace(k, v)
            dest = os.path.join(destino, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(texto)
            escritos.append(rel)
    json.loads(_ler(os.path.join(destino, "ratoeira-app.json")))  # o modelo tem que sair JSON válido
    return destino, porta, sorted(escritos)


# ---------- CLI

def _imprimir(results, as_json):
    if as_json:
        print(json.dumps([r.as_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            print("[%s] %s: %s" % ("ok" if r.ok else "FALHA", r.name, r.detail))
    return 0 if all(r.ok for r in results) else 1


def main(args):
    if args.app_command == "check":
        if not os.path.isdir(args.pasta):
            print("hdev app check: %s não é pasta" % args.pasta)
            return 1
        return _imprimir(run_check(args.pasta, args.areas), args.json)
    try:
        destino, porta, escritos = new(args.nome, args.area, titulo=args.titulo, descricao=args.descricao,
                                       porta=args.porta, areas=args.areas)
    except (ValueError, OSError) as e:
        print("hdev app new: %s" % e)
        return 1
    print("hdev app new: %s (porta %d, %d arquivos do modelo)" % (destino, porta, len(escritos)))
    print("Próximo: cd %s && npm test && python3 <hdev> app check ." % destino)
    print("Antes de codar, confirme com a pessoa: o que faz, papéis, efeitos fora do app, se precisa de chat.")
    return 0
