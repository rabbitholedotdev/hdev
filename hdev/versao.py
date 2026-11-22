"""SemVer (v0.4.0, ADR 0009): CHANGELOG.md do núcleo e tag de app `<app>-vX.Y.Z` na publicação.

Núcleo: `hdev release vX.Y.Z` só cria a tag se `CHANGELOG.md` em HEAD tiver a seção `## [X.Y.Z]`.
App: `hdev app tag <app> vX.Y.Z --publicado [--repo R] [--dir D]` cria a tag anotada `<app>-vX.Y.Z` em HEAD, só
depois da publicação (`estado_publicacao` ok). Sem tag por unidade. Se a pasta do app tem `VERSION` ou
`CHANGELOG.md`, eles têm de bater com a versão. A tag é imutável: existente, recusa.
"""
import os
import re
import subprocess

from . import VERSION
from . import release

APP_RX = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SEMVER_RX = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class VersaoError(Exception):
    pass


def _git(repo, *args):
    try:
        r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise VersaoError("git falhou: %s" % e)
    return r


def plain(version):
    m = SEMVER_RX.match(version or "")
    if not m:
        raise VersaoError("versão %r fora do formato vX.Y.Z" % version)
    return "%s.%s.%s" % m.groups()


def changelog_has(text, version):
    v = re.escape(plain(version))
    return re.search(r"^##\s*\[?v?%s\]?(?:\s|$)" % v, text or "", re.M) is not None


def check_core_changelog(core, version):
    r = _git(core, "show", "HEAD:CHANGELOG.md")
    if r.returncode != 0:
        raise release.ReleaseError("CHANGELOG.md ausente em HEAD (SemVer do núcleo, ADR 0009)")
    if not changelog_has(r.stdout, version):
        raise release.ReleaseError("CHANGELOG.md em HEAD sem a seção ## [%s]" % plain(version))


def app_tag_name(app, version):
    if not APP_RX.match(app or "") or re.search(r"-v\d", app):
        raise VersaoError("nome de app %r inválido (minúsculas, dígitos e hífen)" % app)
    return "%s-v%s" % (app, plain(version))


def _app_dir(repo, app, folder=None):
    if folder:
        return folder if os.path.isabs(folder) else os.path.join(repo, folder)
    for cand in (os.path.join(repo, app), os.path.join(repo, "apps", app)):
        if os.path.isdir(cand):
            return cand
    return repo


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def app_tag(repo, app, version, folder=None, message=None, publicado=False):
    """Cria `<app>-vX.Y.Z` anotada em HEAD. Devolve (nome, commit, notas)."""
    repo = os.path.realpath(repo)
    name = app_tag_name(app, version)
    if not publicado:
        raise VersaoError("tag de app só na publicação: confira `estado_publicacao` ok e repita com --publicado")
    if _git(repo, "rev-parse", "--verify", "--quiet", "refs/tags/%s" % name).returncode == 0:
        raise VersaoError("%s já existe; tag de app é imutável (suba a versão)" % name)
    status = _git(repo, "status", "--porcelain", "--untracked-files=no")
    if status.returncode != 0 or status.stdout.strip():
        raise VersaoError("árvore com mudança rastreada: feche a unidade antes de marcar a publicação")
    d = _app_dir(repo, app, folder)
    notes = []
    ver = _read(os.path.join(d, "VERSION"))
    if ver is not None and ver.strip().lstrip("v") != plain(version):
        raise VersaoError("%s/VERSION diz %s, não %s" % (os.path.relpath(d, repo), ver.strip(), plain(version)))
    log = _read(os.path.join(d, "CHANGELOG.md"))
    if log is not None and not changelog_has(log, version):
        raise VersaoError("%s/CHANGELOG.md sem a seção ## [%s]" % (os.path.relpath(d, repo), plain(version)))
    if ver is None and log is None:
        notes.append("sem VERSION nem CHANGELOG.md em %s" % (os.path.relpath(d, repo) or "."))
    lock = release.read_json(os.path.join(repo, release.LOCK)) or {}
    harness = lock.get("version") or "v%s" % VERSION
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    body = "%s v%s publicado\n\n%s\nApp: %s\nVersao: %s\nCommit: %s\nHarness-Versao: %s\n" % (
        app, plain(version), (message.strip() + "\n") if message else "", app, plain(version), head[:12], harness)
    r = _git(repo, "tag", "-a", name, "-m", body, "HEAD")
    if r.returncode != 0:
        raise VersaoError("git tag %s falhou: %s" % (name, r.stderr.strip()[:200]))
    return name, head, notes


def main_app_tag(args):
    try:
        name, head, notes = app_tag(args.repo, args.nome, args.versao, args.dir, args.message, args.publicado)
    except VersaoError as e:
        print("hdev app tag: %s" % e)
        return 1
    print("hdev app tag: %s em %s (local; push só com o dono liberando)" % (name, head[:12]))
    for n in notes:
        print("  nota: %s" % n)
    return 0
