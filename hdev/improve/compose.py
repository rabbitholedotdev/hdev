"""hdev improve compose e revert — candidata `ganharia` vira branch local `improve/<id>`, e o revert desfaz.

O commit nasce por plumbing (índice temporário, `commit-tree`, `update-ref`): sem checkout, a árvore de trabalho,
o índice e o HEAD não mudam. Adotar é o merge humano da branch; aqui não há push, PR nem merge.
Trailers `Harness-Edit: <id>` e `Harness-Probe: <registro>`. O que a candidata pode editar: ADR 0014.
"""
import json
import os
import re
import subprocess
import tempfile

from .. import eval as evalmod
from . import probe as probemod

TRAILER = "Harness-Edit"
PROBE_TRAILER = "Harness-Probe"
LIBRARY_REL = "library/index.jsonl"
GUARD_SKILLS = ("revisar-diff", "revisar-spec")
# ADR 0014: papel direto, skill que não guarda, tools.md, defaults e botões do manifesto.
MAY_EDIT = (
    re.compile(r"^harness/prompts/[^/]+\.md$"),
    re.compile(r"^\.claude/skills/(?!(?:%s)/)[^/]+/.+$" % "|".join(GUARD_SKILLS)),
    re.compile(r"^tools\.md$"),
    re.compile(r"^docs/padroes/defaults\.md$"),
    re.compile(r"^\.hdev/config\.json$"),
)


class Refused(Exception):
    """Recusa: sai 1 e nada muda."""


def may_edit(rel):
    return any(rx.match(rel) for rx in MAY_EDIT)


def _git(root, *args, env=None, data=None):
    return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, env=env, input=data)


def _out(root, *args, env=None, data=None):
    proc = _git(root, *args, env=env, data=data)
    if proc.returncode != 0:
        raise Refused("git %s falhou: %s" % (args[0], proc.stderr.strip()))
    return proc.stdout


def _dirty(root):
    return bool(_git(root, "status", "--porcelain", "--untracked-files=no").stdout.strip())


def _head_tree(root):
    """caminho -> (modo, blob) do HEAD."""
    out = {}
    for entry in _out(root, "ls-tree", "-r", "-z", "HEAD").split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            mode, _, sha = meta.split()
            out[path] = (mode, sha)
    return out


def load_run(root, run):
    name = os.path.basename(run or "")
    name = name if name.endswith(".json") else name + ".json"
    try:
        with open(os.path.join(root, ".hdev", "runs", name), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        raise Refused("registro .hdev/runs/%s ausente ou ilegível" % name)
    if not isinstance(data, dict) or data.get("kind") != "improve":
        raise Refused("registro %s não é do improve probe" % name)
    return name, data


def _library(root, tree, cid, run_name):
    """Texto novo do índice com a lição desta candidata e deste probe em `active`; None se não há o que marcar."""
    if LIBRARY_REL not in tree:
        return None, []
    lines = _out(root, "cat-file", "blob", tree[LIBRARY_REL][1]).splitlines(True)
    marked = []
    for i, line in enumerate(lines):
        try:
            item = json.loads(line)
        except ValueError:
            continue
        runs = [ev.get("run") for ev in item.get("evidence") or [] if isinstance(ev, dict)]
        if (isinstance(item, dict) and item.get("source") == "improve" and item.get("status") == "candidate"
                and cid in (item.get("tags") or []) and run_name in runs):
            item["status"] = "active"
            lines[i] = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            marked.append(item["id"])
    return ("".join(lines) if marked else None), marked


def plan(root, run, cid):
    """Plano do compose. Junta todos os motivos de recusa em `problems`; não grava nada."""
    run_name, data = load_run(root, run)
    problems = []
    cand = next((c for c in data.get("candidates") or [] if isinstance(c, dict) and c.get("id") == cid), None)
    if not cid or not probemod._ID.match(cid):
        raise Refused("candidata inválida: %s" % cid)
    if cand is None:
        problems.append("%s não está no registro %s" % (cid, run_name))
    elif cand.get("verdict") != "ganharia":
        problems.append("%s deu %s em %s; só ganharia se adota" % (cid, cand.get("verdict"), run_name))
    folder = os.path.join(root, probemod.OVERLAYS_REL, cid)
    if not os.path.isdir(folder):
        problems.append("candidata %s sem pasta %s/%s/" % (cid, probemod.OVERLAYS_REL, cid))
    prefixes = probemod.load_protected(root)
    if prefixes is None:
        problems.append("falta %s" % probemod.PROTECTED_REL)
    tree = _head_tree(root)
    files, added, changed, removed = [], [], [], []
    for rel, origin in probemod.overlay_paths(root, cid) if os.path.isdir(folder) else []:
        if rel is None:
            problems.append("%s: remove inválido" % cid)
            continue
        if prefixes and probemod.is_protected(rel, prefixes):
            problems.append("%s: %s protegido (%s)" % (cid, rel, origin))
            continue
        if not may_edit(rel):
            problems.append("%s: %s fora do que pode editar (ADR 0014)" % (cid, rel))
            continue
        if origin == "remove":
            removed += [p for p in sorted(tree) if p == rel or p.startswith(rel + "/")]
            continue
        path = os.path.join(folder, *rel.split("/"))
        mode = "100755" if os.access(path, os.X_OK) else "100644"
        sha = _out(root, "hash-object", path).strip()
        if tree.get(rel) != (mode, sha):
            files.append((rel, path, mode))
            (changed if rel in tree else added).append(rel)
    if not problems and not (added or changed or removed):
        problems.append("%s não muda nada no HEAD" % cid)
    if _dirty(root):
        problems.append("árvore rastreada suja; commite ou guarde antes")
    branch = "improve/%s" % cid
    if _git(root, "rev-parse", "--verify", "--quiet", "refs/heads/" + branch).returncode == 0:
        problems.append("branch %s já existe" % branch)
    library, marked = _library(root, tree, cid, run_name)
    cand = cand or {}
    message = "improve: adota %s\n\n%s\nProbe %s no caso %s, base %s: %s, Δ %s.\n" \
              "Adotar é o merge desta branch; desfazer é `hdev improve revert --cand %s`.\n\n%s: %s\n%s: %s\n" % (
                  cid, cand.get("summary") or "candidata %s" % cid, run_name, data.get("case"),
                  str(data.get("base_sha") or "")[:12], cand.get("verdict"),
                  json.dumps(cand.get("delta") or {}, sort_keys=True), cid, TRAILER, cid, PROBE_TRAILER, run_name)
    return {"branch": branch, "added": added, "changed": changed + ([LIBRARY_REL] if library else []),
            "removed": sorted(set(removed)), "library": marked, "message": message, "problems": problems,
            "_files": files, "_library": library}


def compose(root, run, cid, dry_run=False):
    root = os.path.realpath(root)
    p = plan(root, run, cid)
    if p["problems"]:
        raise Refused("; ".join(p["problems"]))
    if dry_run:
        return p
    with tempfile.TemporaryDirectory(prefix="hdev-compose-") as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=os.path.join(tmp, "index"))
        _out(root, "read-tree", "HEAD", env=env)
        for rel, path, mode in p["_files"]:
            sha = _out(root, "hash-object", "-w", path).strip()
            _out(root, "update-index", "--add", "--cacheinfo", "%s,%s,%s" % (mode, sha, rel), env=env)
        if p["removed"]:
            _out(root, "update-index", "--force-remove", "--", *p["removed"], env=env)
        if p["_library"]:
            sha = _out(root, "hash-object", "-w", "--stdin", data=p["_library"]).strip()
            _out(root, "update-index", "--cacheinfo", "100644,%s,%s" % (sha, LIBRARY_REL), env=env)
        tree = _out(root, "write-tree", env=env).strip()
    commit = _out(root, "commit-tree", tree, "-p", "HEAD", "-F", "-", data=p["message"]).strip()
    # valor velho vazio: falha se a branch nasceu no meio do caminho
    _out(root, "update-ref", "-m", "hdev improve compose", "refs/heads/" + p["branch"], commit, "")
    p["commit"] = commit
    return p


def _trailer(root, sha):
    return _out(root, "log", "-1", "--format=%%(trailers:key=%s,valueonly)" % TRAILER, sha).strip()


def revert(root, cand=None, commit=None):
    """Reverte o commit com `Harness-Edit:` na branch atual. Commit novo; a história não muda."""
    root = os.path.realpath(root)
    if _dirty(root):
        raise Refused("árvore rastreada suja; commite ou guarde antes")
    if commit:
        proc = _git(root, "rev-parse", "--verify", "--quiet", commit + "^{commit}")
        if proc.returncode != 0:
            raise Refused("commit %s não existe" % commit)
        sha = proc.stdout.strip()
        if not _trailer(root, sha):
            raise Refused("commit %s sem trailer %s:; o revert só desfaz edição do improve" % (commit, TRAILER))
    else:
        if not cand or not probemod._ID.match(cand):
            raise Refused("candidata inválida: %s" % cand)
        found = _out(root, "log", "--format=%H", "--grep=^%s: %s$" % (TRAILER, cand), "HEAD").split()
        sha = next((s for s in found if cand in _trailer(root, s).split()), None)
        if sha is None:
            raise Refused("nenhum commit com %s: %s no HEAD" % (TRAILER, cand))
    if _out(root, "log", "--format=%H", "-F", "--grep=This reverts commit %s" % sha, "HEAD").strip():
        raise Refused("commit %s já revertido" % sha[:12])
    proc = _git(root, "revert", "--no-edit", sha)
    if proc.returncode != 0:
        _git(root, "revert", "--abort")
        raise Refused("git revert falhou e foi abortado: %s" % (proc.stderr.strip() or proc.stdout.strip()))
    return {"reverted": sha, "edit": _trailer(root, sha), "commit": _out(root, "rev-parse", "HEAD").strip()}


def main_compose(args):
    try:
        p = compose(args.root, args.run, args.cand, args.dry_run)
    except (Refused, evalmod.EvalError) as e:
        print("hdev improve compose: recusado: %s" % e)
        return 1
    head = "dry-run (nada muda)" if args.dry_run else "branch %s criada em %s" % (p["branch"], p["commit"][:12])
    print("hdev improve compose: %s" % head)
    print("  branch: %s" % p["branch"])
    for label, key in (("novo", "added"), ("muda", "changed"), ("sai", "removed")):
        for rel in p[key]:
            print("  %s: %s" % (label, rel))
    for iid in p["library"]:
        print("  biblioteca: %s candidate -> active" % iid)
    print("  mensagem:")
    for line in p["message"].splitlines():
        print("    " + line)
    if not args.dry_run:
        print("  adotar é o merge humano de %s; nada foi enviado" % p["branch"])
    return 0


def main_revert(args):
    try:
        res = revert(args.root, args.cand, args.commit)
    except Refused as e:
        print("hdev improve revert: recusado: %s" % e)
        return 1
    print("hdev improve revert: %s (%s: %s) revertido em %s" % (
        res["reverted"][:12], TRAILER, res["edit"], res["commit"][:12]))
    return 0
