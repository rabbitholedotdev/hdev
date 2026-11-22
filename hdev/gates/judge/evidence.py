"""Testes, check e anexos de evidência que entram no pacote."""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from hdev import CORE_ROOT
from hdev import base as basemod
from hdev import config as cfgmod

from .constants import EVIDENCE_DIR, EVIDENCE_REF_RX, MAX_EVIDENCE_FILE
from .gitdiff import _git

def run_tests(root, cfg):
    cmd = cfgmod.gate_command(cfg, "full")
    if not cmd:
        return "(sem gates.full na config)"
    try:
        r = subprocess.run(cmd, cwd=root, shell=isinstance(cmd, str), capture_output=True, text=True,
                           timeout=cfgmod.gate_timeout(cfg, 600))
        return "exit %d\n%s%s" % (r.returncode, r.stdout[-20000:], r.stderr[-20000:])
    except subprocess.TimeoutExpired:
        return "timeout"
    except OSError as e:
        return "não consegui rodar os testes: %s" % e


def check_text(root, base=None):
    """Saída do hdev check na raiz, para o juiz ver o portão (regra 4 do AGENTS).

    Usa o bin/hdev da própria árvore (o núcleo naquela versão); senão, o deste núcleo."""
    own = os.path.join(root, "bin", "hdev")
    hdev_bin = own if os.path.isfile(own) else os.path.join(CORE_ROOT, "bin", "hdev")
    cmd = [sys.executable, hdev_bin, "check", "--root", root] + (["--base", base] if base else [])
    try:
        r = subprocess.run(cmd, cwd=root, capture_output=True,
                           text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "erro ao rodar hdev check: %s" % e
    return "exit %d\n%s%s" % (r.returncode, r.stdout[-10000:], r.stderr[-5000:])


def evidence(root, cfg, head=None, with_tests=True, base=None):
    """(testes, check). Com head, roda num clone temporário daquele commit, para a evidência bater com o diff.

    O check entra sempre; os testes só com with_tests (senão '' e quem chama usa o log dado, se houver)."""
    if not head:
        return (run_tests(root, cfg) if with_tests else ""), check_text(root, base)
    sha = _git(root, "rev-parse", "--verify", "%s^{commit}" % head).strip()
    if not sha:
        return "não achei o commit %s" % head, "não achei o commit %s" % head
    tmp = tempfile.mkdtemp(prefix="hdev-judge-")
    try:
        tree = os.path.join(tmp, "arvore")
        r = subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", root, tree], capture_output=True,
                           text=True, timeout=120)
        if r.returncode != 0:
            return "não consegui clonar %s: %s" % (sha[:12], r.stderr.strip()[-500:]), ""
        if subprocess.run(["git", "-C", tree, "checkout", "-q", "--detach", sha], capture_output=True,
                          timeout=120).returncode != 0:
            return "não consegui abrir o commit %s" % sha[:12], ""
        snap_cfg, err = cfgmod.load(tree)
        # gates.full vem do commit julgado. Chave antiga não é lida; config que não abre cai na atual.
        run_cfg = cfg if err else snap_cfg
        note = "(rodado num clone limpo do commit %s)\n" % sha[:12]
        return (note + run_tests(tree, run_cfg) if with_tests else ""), note + check_text(tree, base)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

def plan_evidence_tokens(plan_path, plan_text="", extra=()):
    """Tokens do plano que casam com o nome do arquivo em docs/evidence/ (stem, id F1-10 e o id da unidade)."""
    tokens = set()
    stem = os.path.splitext(os.path.basename(plan_path))[0].lower()
    tokens.add(stem)
    if stem.startswith("plan-") and stem[5:]:
        tokens.add(stem[5:])
    for m in re.finditer(r"\bF\d+-\d+\b", plan_text or "", re.I):
        tokens.add(m.group(0).lower())
    for tok in extra or ():
        if tok and len(tok) >= 4:  # id da unidade (C9-01, INF-008): o anexo pode levar só o id
            tokens.add(str(tok).lower())
    return tokens


def _read_evidence_file(root, rel, head=None):
    if head:
        return _git(root, "show", "%s:%s" % (head, rel))
    path = os.path.join(root, rel)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return ""


def unit_evidence_dir(plan_path):
    """`work/<id>/evidence` quando o plano é `work/<id>/plan.md`. Senão None."""
    norm = (plan_path or "").replace("\\", "/")
    found = basemod.WORK_PLAN_RX.search(norm)
    if not found or found.group(1) in (".", ".."):
        return None
    return "work/%s/evidence" % found.group(1)


def _evidence_listing(root, head=None):
    if head:
        listing = _git(root, "ls-tree", "-r", "--name-only", head, "--", EVIDENCE_DIR)
        return [p.replace("\\", "/") for p in listing.splitlines() if p]
    folder = os.path.join(root, EVIDENCE_DIR)
    try:
        return [os.path.join(EVIDENCE_DIR, n).replace("\\", "/")
                for n in sorted(os.listdir(folder))
                if not n.startswith(".") and os.path.isfile(os.path.join(folder, n))]
    except OSError:
        return []


def _unit_evidence_listing(root, plan_path, head=None):
    """`.md` direto em `work/<id>/evidence/`. Com head, só o que está no commit (ls-tree)."""
    folder = unit_evidence_dir(plan_path)
    if not folder:
        return []
    if head:
        listing = _git(root, "ls-tree", "-r", "--name-only", head, "--", folder)
        paths = [p.replace("\\", "/") for p in listing.splitlines() if p]
    else:
        base = os.path.join(root, folder)
        try:
            paths = [os.path.join(folder, n).replace("\\", "/")
                     for n in sorted(os.listdir(base))
                     if not n.startswith(".") and os.path.isfile(os.path.join(base, n))]
        except OSError:
            paths = []
    return [p for p in paths if os.path.dirname(p) == folder and p.endswith(".md")
            and not os.path.basename(p).startswith(".")]


def _clip_evidence(body):
    if len(body) <= MAX_EVIDENCE_FILE:
        return body, False
    return body[:MAX_EVIDENCE_FILE] + "\n[arquivo truncado em %d caracteres]\n" % MAX_EVIDENCE_FILE, True


def evidence_items(root, plan_path, plan_text="", head=None, extra=()):
    """[(arquivo, texto, truncado?)]. `docs/evidence/` casa o nome; `work/<id>/evidence/*.md` entra inteiro."""
    tokens = plan_evidence_tokens(plan_path, plan_text, extra)
    items = []
    seen = set()
    rows = [(rel, False) for rel in _evidence_listing(root, head)]
    rows.extend((rel, True) for rel in _unit_evidence_listing(root, plan_path, head))
    for rel, own in rows:
        if rel in seen:
            continue
        seen.add(rel)
        if not own and not any(tok in os.path.basename(rel).lower() for tok in tokens):
            continue
        body = _read_evidence_file(root, rel, head)
        if not body:
            continue
        body, truncated = _clip_evidence(body)
        items.append((rel, body, truncated))
    return items


def piece_evidence(root, plan_path, plan_text="", head=None, extra=()):
    """Anexos da peça: `work/<id>/evidence/*.md` ou, no legado, `docs/evidence/` cujo nome casa."""
    return "\n\n".join("--- %s\n%s" % (rel, body.rstrip())
                        for rel, body, _ in evidence_items(root, plan_path, plan_text, head, extra))


def check_evidence_refs(root, plan_path, plan_text="", head=None, extra=()):
    """Anexos citados no plano que não existem ou não entrariam no pacote.

    `work/<id>/evidence/*.md` entra sem casar o nome. `docs/evidence/` continua pelo nome.
    Devolve a mensagem de erro (falha cedo, antes de rodar testes e chamar o juiz) ou ""."""
    tokens = plan_evidence_tokens(plan_path, plan_text, extra)
    unit = unit_evidence_dir(plan_path)
    present = set(_evidence_listing(root, head))
    present.update(_unit_evidence_listing(root, plan_path, head))
    problems = []
    for ref in sorted(set(EVIDENCE_REF_RX.findall(plan_text or ""))):
        ref = ref.rstrip(".")
        if ref.endswith("/") or ref in (EVIDENCE_DIR, unit) or "*" in ref:
            continue
        if unit and ref.startswith(unit + "/"):
            if os.path.dirname(ref) != unit or not ref.endswith(".md"):
                problems.append("%s: só arquivos .md direto em %s/ entram no pacote" % (ref, unit))
            elif ref not in present:
                problems.append("%s: citado no plano e não existe%s" % (ref, " no commit julgado" if head else ""))
            continue
        if os.path.dirname(ref) != EVIDENCE_DIR:
            where = "%s/*.md" % unit if unit else "work/<id>/evidence/*.md"
            problems.append("%s: só arquivos direto em %s/ entram no pacote (ou %s da unidade)"
                            % (ref, EVIDENCE_DIR, where))
        elif ref not in present:
            problems.append("%s: citado no plano e não existe%s" % (ref, " no commit julgado" if head else ""))
        elif not any(tok in os.path.basename(ref).lower() for tok in tokens):
            problems.append("%s: existe, mas o nome não contém nenhum de %s e o juiz não o veria"
                            % (ref, ", ".join(sorted(tokens))))
    if not problems:
        return ""
    return ("anexo de evidência com problema (o juiz não foi chamado): %s. Em work/<id>/plan.md grave "
            "work/<id>/evidence/*.md (todo .md entra, até %d caracteres). No legado, renomeie para "
            "docs/evidence/<stem-do-plano ou id da unidade>-<assunto>.md ou corrija o plano."
            % ("; ".join(problems), MAX_EVIDENCE_FILE))
