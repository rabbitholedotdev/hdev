"""Base do diff por unidade (v0.3.9, ADR 0008).

O `commit-turno` da Ratoeira commita a cada turno do agente. Com `git diff HEAD`, o juiz só via o resto da peça
e dava falso negativo. A base passa a ser o commit de antes da unidade, nesta ordem:
1. `--base` explícita;
2. a gravada em `.hdev/state/bases.json` (`hdev base --plan P --marcar`, ou o primeiro `hdev judge` da unidade);
3. deduzida dos docs da unidade (plano, spec e review da spec):
   - doc já commitado: o pai do primeiro commit que o trouxe, ou o último commit antes do doc mais antigo (mtime),
     o que for mais antigo (o commit-turno pode ter levado código antes de levar a spec);
   - docs só na árvore: o último commit que fechou um item no backlog antes deles, senão o último commit antes deles;
4. HEAD (sem unidade reconhecida): o comportamento antigo.
O diff é base..árvore de trabalho, mais os não rastreados.
"""
import datetime
import json
import os
import re
import subprocess

from . import unit as unitmod

STATE = os.path.join(".hdev", "state", "bases.json")
# Planos novos: work/<id>/plan.md. O backlog continua um arquivo.
BACKLOGS = ("work/backlog.md",)
UNIT_RX = re.compile(r"^([a-z]+\d*-\d+)(?:-|$)", re.I)
WORK_PLAN_RX = re.compile(r"(?:^|/)work/([^/]+)/plan\.md$")
DOC_LINE_RX = re.compile(
    r"^\s*(?:Spec|Review)\s*:\s*`?((?:docs/specs/[^\s`)]+\.md|work/[^\s`)/]+/[^\s`)]+\.md))",
    re.I | re.M)
CLOSED_RX = re.compile(r"\|\s*feito\s*\||\[x\]|feito e fechado", re.I)
HEAD_FONTE = "HEAD (sem base da unidade)"


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout if r.returncode == 0 else ""


def _sha(root, ref):
    return _git(root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref).strip()


def _is_ancestor(root, a, b):
    try:
        r = subprocess.run(["git", "-C", root, "merge-base", "--is-ancestor", a, b], capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0


def _rel(root, plan_path):
    path = plan_path if os.path.isabs(plan_path) else os.path.join(root, plan_path)
    return os.path.relpath(os.path.realpath(path), os.path.realpath(root)).replace(os.sep, "/")


def unit_id(plan_path):
    """`work/<id>/plan.md` -> `<id>` (nome da pasta). Legado: `docs/plan-inf-006-sqlite.md` -> `INF-006`;
    `plan-f2-05-x.md` -> `F2-05`; sem id -> None. Juiz, fechar e base usam só esta função."""
    norm = (plan_path or "").replace("\\", "/")
    found = WORK_PLAN_RX.search(norm)
    if found and found.group(1) not in (".", ".."):
        return found.group(1)
    stem = os.path.splitext(os.path.basename(norm))[0]
    if stem.lower().startswith("plan-"):
        stem = stem[5:]
    m = UNIT_RX.match(stem)
    return m.group(1).upper() if m else None


def unit_key(plan_path):
    return unit_id(plan_path) or os.path.splitext(os.path.basename(plan_path))[0]


def _same_unit(rel, uid):
    """A citação é desta unidade: o nome começa pelo id, ou o arquivo mora em work/<id>/."""
    if not uid:
        return True
    norm = rel.replace("\\", "/")
    low = uid.lower()
    if os.path.basename(norm).lower().startswith(low):
        return True
    return norm.startswith("work/%s/" % low)


def unit_docs(root, plan_rel, plan_text=""):
    """Plano + specs da unidade (pelo id no nome, ou citadas em `Spec:`/`Review:` no plano)."""
    docs = [plan_rel]
    uid = unit_id(plan_rel)
    folder = os.path.join(root, "docs", "specs")
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        names = []
    if uid:
        low = uid.lower()
        for n in names:
            if n.endswith(".md") and (n.lower().startswith(low + "-") or n.lower().startswith(low + ".")):
                docs.append("docs/specs/" + n)
    for m in DOC_LINE_RX.finditer(plan_text or ""):
        rel = m.group(1)
        if rel not in docs and _same_unit(rel, uid):
            docs.append(rel)
    found = WORK_PLAN_RX.search((plan_rel or "").replace("\\", "/"))
    if found:
        unit = found.group(1)
        for name in ("brief.md", "spec.md", "review.md"):
            rel = "work/%s/%s" % (unit, name)
            if os.path.isfile(os.path.join(root, rel)):
                docs.append(rel)
    out = []
    for d in docs:
        if d not in out:
            out.append(d)
    return out


def _mtime(root, docs):
    best = None
    for d in docs:
        try:
            t = os.path.getmtime(os.path.join(root, d))
        except OSError:
            continue
        if best is None or t < best[0]:
            best = (t, d)
    return best


def _until(epoch):
    return datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def commit_before(root, epoch):
    return _git(root, "log", "-1", "--format=%H", "--until=%s" % _until(epoch), "HEAD").strip() or None


def _key(line):
    body = line[1:].strip()
    if body.startswith("|"):
        cells = [c.strip() for c in body.strip("|").split("|")]
        return cells[0] if cells else body
    return body[:40]


def closes_item(root, commit):
    """O commit marca algum item como feito no backlog (linha nova com feito/[x] que antes não tinha)?"""
    patch = _git(root, "show", "--format=", "--unified=0", commit, "--", *BACKLOGS)
    added, removed = set(), set()
    for line in patch.splitlines():
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("+") and CLOSED_RX.search(line):
            added.add(_key(line))
        elif line.startswith("-") and CLOSED_RX.search(line):
            removed.add(_key(line))
    return bool(added - removed)


def closed_item_commit(root, epoch=None, limit=200):
    args = ["log", "--format=%H", "-n", str(limit)]
    if epoch is not None:
        args.append("--until=%s" % _until(epoch))
    for c in _git(root, *args, "HEAD", "--", *BACKLOGS).split():
        if closes_item(root, c):
            return c
    return None


def first_add_commit(root, docs):
    out = _git(root, "log", "--diff-filter=A", "--format=%H", "--reverse", "HEAD", "--", *docs).split()
    return out[0] if out else None


def deduce(root, plan_rel, plan_text=""):
    """(sha, fonte) deduzidos dos docs da unidade, ou (None, motivo)."""
    if not _sha(root, "HEAD"):
        return None, "repo sem commits"
    docs = unit_docs(root, plan_rel, plan_text)
    oldest = _mtime(root, docs)
    before = commit_before(root, oldest[0]) if oldest else None
    added = first_add_commit(root, docs)
    if added:
        parent = _sha(root, "%s^" % added)
        if not parent:
            return None, "doc da unidade no primeiro commit do repo"
        if before and before != parent and _is_ancestor(root, before, parent):
            return before, "último commit antes de %s (mtime), mais antigo que o pai de %s" % (oldest[1], added[:12])
        return parent, "pai de %s, o primeiro commit com um doc da unidade" % added[:12]
    if not oldest:
        return None, "docs da unidade não encontrados"
    closed = closed_item_commit(root, oldest[0])
    if closed:
        return closed, "último item fechado no backlog (%s) antes de %s" % (closed[:12], oldest[1])
    if before:
        return before, "último commit antes de %s (mtime)" % oldest[1]
    return None, "nenhum commit antes de %s" % oldest[1]


def state_path(root):
    return os.path.join(root, STATE)


def load(root):
    try:
        with open(state_path(root), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save(root, key, sha, origem, plan_rel):
    data = load(root)
    data[key] = {"base": sha, "plan": plan_rel, "origem": origem,
                 "ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    path = state_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return data[key]


def recorded(root, key):
    item = load(root).get(key)
    if not isinstance(item, dict) or not isinstance(item.get("base"), str):
        return None
    sha = _sha(root, item["base"])
    return (sha, item) if sha else None


def resolve(root, plan_path, plan_text="", explicit=None):
    """{"sha", "fonte", "unidade", "tipo"}; sha None = HEAD (comportamento antigo)."""
    plan_rel = _rel(root, plan_path)
    key = unit_key(plan_rel)
    if explicit:
        return {"sha": _sha(root, explicit) or explicit, "fonte": "--base %s" % explicit, "unidade": key,
                "tipo": "explicita"}
    rec = recorded(root, key)
    if rec:
        return {"sha": rec[0], "fonte": "gravada em %s (%s, %s)" % (STATE, rec[1].get("origem", "?"),
                                                                     rec[1].get("ts", "?")),
                "unidade": key, "tipo": "gravada"}
    sha, why = deduce(root, plan_rel, plan_text)
    if sha:
        return {"sha": sha, "fonte": "deduzida: %s" % why, "unidade": key, "tipo": "deduzida"}
    return {"sha": None, "fonte": "%s: %s" % (HEAD_FONTE, why), "unidade": key, "tipo": "head"}


def main(args):
    root = os.path.realpath(args.root)
    plan_path = args.plan if os.path.isabs(args.plan) else os.path.join(root, args.plan)
    try:
        with open(plan_path, encoding="utf-8") as f:
            plan_text = f.read()
    except OSError as e:
        print("hdev base: %s" % e)
        return 64
    plan_rel = _rel(root, plan_path)
    key = unit_key(plan_rel)
    if args.marcar is not None:  # sem REF: grava a base que resolve() acha agora (deduzida, ou HEAD)
        ref = args.marcar or resolve(root, plan_rel, plan_text)["sha"] or "HEAD"
        sha = _sha(root, ref)
        if not sha:
            print("hdev base: commit inexistente: %s" % ref)
            return 64
        rec = recorded(root, key)
        if rec and rec[0] != sha and not args.force:
            print("hdev base: %s já tem base %s (%s); use --force para trocar" % (key, rec[0][:12],
                                                                                 rec[1].get("origem", "?")))
            return 1
        save(root, key, sha, "hdev base --marcar %s" % (args.marcar or "(deduzida)"), plan_rel)
        nxt = unitmod.next_from_plan(plan_text) or ("seguir %s" % plan_rel)
        unitmod.open_unit(root, key, plan_rel, nxt)
        print("hdev base: %s -> %s gravada em %s" % (key, sha[:12], STATE))
        return 0
    info = resolve(root, plan_rel, plan_text)
    if args.sha:
        print(info["sha"] or _sha(root, "HEAD"))
    elif args.json:
        print(json.dumps(info, ensure_ascii=False))
    else:
        print("%s: base %s (%s)" % (key, (info["sha"] or "HEAD")[:12], info["fonte"]))
    return 0
