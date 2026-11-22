"""Área da Ratoeira (F2-01): `hdev check --area`, `hdev area sync` e `hdev wt` (worktrees em `<área>/_wt/`).

Projeto de área é um repositório git (clone ou worktree) sob a área, inclusive dentro de uma
pasta-pai sem `.git` (ex.: `rag/rag-mcp`). Ficam de fora: nomes com `_` ou `.` na frente
(`_contexto`, `_wt`), as pastas de estado da área (`estado`, `insights`, `apps`) e o próprio
núcleo harness-dev e as worktrees dele (têm `bin/hdev` e `hdev/__init__.py`). Worktrees vão em
`<área>/_wt/` na raiz da área, mesmo quando o repo mora numa pasta-pai.
"""

import os
import re
import subprocess

from . import init as initmod
from . import release

SKIP = {"estado", "insights", "apps", "node_modules"}
WT = "_wt"
NAME_RX = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class Result:
    def __init__(self, name, ok, detail):
        self.name, self.ok, self.detail = name, ok, detail

    def as_dict(self):
        return {"name": self.name, "ok": self.ok, "detail": self.detail}


def _git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def is_core(path):
    return os.path.isfile(os.path.join(path, "bin", "hdev")) and os.path.isfile(os.path.join(path, "hdev", "__init__.py"))


def folders(area, skip=()):
    """Pastas de primeiro nível visíveis (compat)."""
    out = []
    try:
        names = os.listdir(area)
    except OSError:
        return out
    for name in sorted(names):
        path = os.path.join(area, name)
        if name.startswith(("_", ".")) or name in SKIP or name in skip or not os.path.isdir(path):
            continue
        out.append((name, path))
    return out


def walk_dirs(area, skip=()):
    """Pastas visíveis em qualquer nível, sem entrar em repositório git nem em _wt/estado/etc."""
    out = []

    def walk(base):
        try:
            names = os.listdir(base)
        except OSError:
            return
        for name in sorted(names):
            path = os.path.join(base, name)
            if name.startswith(("_", ".")) or name in SKIP or name in skip or not os.path.isdir(path):
                continue
            out.append((name, path))
            if os.path.lexists(os.path.join(path, ".git")):
                continue
            walk(path)

    walk(area)
    return out


def projects(area, skip=()):
    """(nome, caminho) dos projetos da área: pastas com `.git`, menos o núcleo, em qualquer nível."""
    return [(n, p) for n, p in walk_dirs(area, skip) if os.path.lexists(os.path.join(p, ".git")) and not is_core(p)]


def bad_names(area, skip=()):
    """Pastas novas fora da regra: inglês, ASCII, minúsculas, hífen. Aviso, não falha (legado fica)."""
    return [n for n, _ in walk_dirs(area, skip) if not NAME_RX.match(n)]


def check_area(area, skip=()):
    results = []
    for name, path in projects(area, skip):
        lock = release.read_json(os.path.join(path, release.LOCK))
        if lock is None and not os.path.lexists(os.path.join(path, release.LINK)):
            results.append(Result(name, False, "sem harness: rode `hdev area sync`"))
            continue
        ok, detail = release.verify(path)
        channel = (lock or {}).get("channel")
        if ok and channel != release.CHANNEL_LATEST:
            detail += " (fixo%s: `hdev pin --latest` para seguir o canal)" % ("" if channel else ", lock antigo")
        results.append(Result(name, ok, detail))
    names = bad_names(area, skip)
    results.append(Result("names", True, "aviso: fora do padrão inglês/minúsculas/hífen: %s" % ", ".join(names)
                          if names else "todas em inglês, minúsculas e hífen"))
    return results


def sync(area, profile=initmod.DEFAULT_PROFILE, dry_run=False, skip=(), core=None):
    """Liga ao núcleo (canal latest) os projetos da área que ainda não têm `.harnessdev`. Não mexe nos ligados."""
    done = []
    for name, path in projects(area, skip):
        if os.path.lexists(os.path.join(path, release.LOCK)) or os.path.lexists(os.path.join(path, release.LINK)):
            continue
        if dry_run:
            done.append((name, "seria ligado (perfil %s)" % profile))
            continue
        try:
            rep = initmod.init(path, core=core, profile=profile)
        except (ValueError, OSError) as e:
            done.append((name, "erro: %s" % e))
            continue
        done.append((name, "ligado: %s, canal %s, %d arquivo(s) escrito(s)" % (rep["version"], rep["channel"],
                                                                             len(rep["written"]))))
    return done


def slug(branch):
    return re.sub(r"[^a-z0-9]+", "-", branch.lower()).strip("-")


def area_root(main):
    """Raiz da área Ratoeira a partir do repo principal.

    Anda pra cima até o pai se chamar `areas`, ou até achar AGENTS.md com `_wt`,
    `_contexto` ou `.harnessdev.lock`. Se não achar (testes, layout antigo), o pai do repo.
    """
    fallback = os.path.dirname(main)
    cur = main
    while True:
        parent = os.path.dirname(cur)
        if parent == cur:
            return fallback
        if os.path.basename(parent) == "areas":
            return cur
        # _contexto é marca típica da área; AGENTS.md + (_wt ou lock) cobre área já organizada.
        if os.path.isdir(os.path.join(parent, "_contexto")) or (
            os.path.isfile(os.path.join(parent, "AGENTS.md")) and (
                os.path.isdir(os.path.join(parent, WT))
                or os.path.isfile(os.path.join(parent, ".harnessdev.lock"))
            )
        ):
            return parent
        cur = parent


def repo_of(path):
    """(repo principal, área) de um checkout ou worktree, pelo git common dir."""
    common = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common:
        raise ValueError("%s não é um repositório git" % path)
    main = os.path.dirname(os.path.realpath(common))
    return main, area_root(main)


def wt_path(repo, branch):
    main, area = repo_of(repo)
    if not slug(branch):
        raise ValueError("branch %r sem nome utilizável" % branch)
    return main, os.path.join(area, WT, "%s-%s" % (os.path.basename(main), slug(branch)))


def wt_add(repo, branch, base=None):
    main, dest = wt_path(repo, branch)
    if os.path.lexists(dest):
        raise ValueError("%s já existe" % dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if _git(main, "rev-parse", "--verify", "--quiet", "refs/heads/%s" % branch):
        args = ["worktree", "add", dest, branch]
    else:
        args = ["worktree", "add", "-b", branch, dest] + ([base] if base else [])
    r = subprocess.run(["git", "-C", main, *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise ValueError("git worktree add falhou: %s" % r.stderr.strip()[-300:])
    return dest


def wt_move(worktree):
    """Move uma worktree existente para `<área>/_wt/<repo>-<branch>` (git worktree move: o git fica sabendo)."""
    worktree = os.path.realpath(worktree)
    branch = _git(worktree, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD":
        raise ValueError("%s sem branch (HEAD solto?)" % worktree)
    main, dest = wt_path(worktree, branch)
    if worktree == main:
        raise ValueError("%s é o repositório principal, não uma worktree" % worktree)
    if worktree == dest:
        return dest
    if os.path.lexists(dest):
        raise ValueError("%s já existe" % dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    r = subprocess.run(["git", "-C", main, "worktree", "move", worktree, dest], capture_output=True, text=True,
                       timeout=120)
    if r.returncode != 0:
        raise ValueError("git worktree move falhou: %s" % r.stderr.strip()[-300:])
    return dest


def main_area(args):
    area = os.path.realpath(args.area)
    skip = tuple(args.skip or ())
    for name, what in sync(area, args.profile, args.dry_run, skip, args.core):
        print("%s: %s" % (name, what))
    for r in check_area(area, skip):
        print("[%s] %s: %s" % ("ok" if r.ok else "FALHA", r.name, r.detail))
    return 0


def main_wt(args):
    try:
        if args.wt_command == "add":
            dest = wt_add(args.repo, args.branch, args.base)
        else:
            dest = wt_move(args.worktree)
    except ValueError as e:
        print("hdev wt: %s" % e)
        return 1
    print("worktree em %s" % dest)
    return 0
