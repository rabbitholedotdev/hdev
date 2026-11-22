"""Releases do núcleo por tag git e o par `.harnessdev` + `.harnessdev.lock` no app (ADR 0002).

A tag é a fonte da verdade. A release é a árvore da tag extraída por `git archive` em
`<releases>/vX.Y.Z`, com `.release.json` (versão, commit e núcleo). Nada de worktree, nada de sync.
`<releases>` é `<núcleo>/releases`, ou o caminho em `HDEV_RELEASES_DIR` / `<núcleo>/.hdev/state/releases-dir`
(na Ratoeira: /opt/harness-dev/releases). Canal `latest` (F2-01): `<releases>/latest` é um symlink para a
última release promovida (`hdev release`, só com juiz pass); app no canal aponta `.harnessdev` para ele.
"""
import io
import json
import os
import re
import shutil
import subprocess
import tarfile

LINK = ".harnessdev"
LOCK = ".harnessdev.lock"
RELEASE_META = ".release.json"
VERSION_RX = re.compile(r"^v\d+\.\d+\.\d+$")
LATEST = "latest"
CHANNEL_LATEST, CHANNEL_PINNED = "latest", "pinned"
RELEASES_FILE = os.path.join(".hdev", "state", "releases-dir")


class ReleaseError(Exception):
    pass


def _git(core, *args, binary=False):
    try:
        r = subprocess.run(["git", "-C", core, *args], capture_output=True, text=not binary, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise ReleaseError("git falhou: %s" % e)
    return r


def tags(core):
    """Tags vX.Y.Z do núcleo, da maior para a menor."""
    r = _git(core, "tag", "--list", "v*", "--sort=-v:refname")
    if r.returncode != 0:
        return []
    return [t for t in r.stdout.split() if VERSION_RX.match(t)]


def tag_commit(core, version):
    r = _git(core, "rev-parse", "--verify", "--quiet", "%s^{commit}" % version)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def releases_dir(core):
    """Onde as releases do núcleo moram. Fora do git: a configuração não viaja em clone nem em teste."""
    env = os.environ.get("HDEV_RELEASES_DIR", "").strip()
    if env:
        return os.path.realpath(env)
    try:
        with open(os.path.join(core, RELEASES_FILE), encoding="utf-8") as f:
            configured = f.read().strip()
    except OSError:
        configured = ""
    if configured:
        return os.path.realpath(configured)
    return os.path.join(os.path.realpath(core), "releases")


def latest_path(core):
    return os.path.join(releases_dir(core), LATEST)


def current_latest(core):
    """(versão, caminho, commit) da release promovida no canal latest, ou None se o canal ainda não existe."""
    link = latest_path(core)
    if not os.path.islink(link):
        return None
    meta = read_json(os.path.join(link, RELEASE_META)) or {}
    if not meta.get("version") or not meta.get("commit"):
        return None
    return meta["version"], os.path.realpath(link), meta["commit"]


def release_path(core, version):
    return os.path.join(releases_dir(core), version)


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def choose_version(core, version=None):
    if version:
        if not VERSION_RX.match(version):
            raise ReleaseError("versão %r fora do formato vX.Y.Z" % version)
        if not tag_commit(core, version):
            raise ReleaseError("a tag %s não existe no núcleo %s" % (version, core))
        return version
    found = tags(core)
    if not found:
        raise ReleaseError("o núcleo %s não tem tag vX.Y.Z: o operador cria a release (git tag v0.1.0) "
                           "e o init usa a maior" % core)
    return found[0]


def _ensure_prompt(tmp):
    """Monta PROMPT-ORCHESTRATOR.md na árvore extraída. Tag sem o papel não é reescrita."""
    from . import prompts as promptmod
    role = os.path.join(tmp, promptmod.PROMPTS, promptmod.ROLE)
    promptmod.write_shipped(tmp)
    if not os.path.isfile(role):
        return
    dest = os.path.join(tmp, promptmod.SHIPPED)
    if not os.path.isfile(dest):
        raise ReleaseError("a release tem %s e não gravou %s" % (
            os.path.join(promptmod.PROMPTS, promptmod.ROLE).replace(os.sep, "/"), promptmod.SHIPPED))
    with open(dest, encoding="utf-8") as f:
        head = f.read(240)
    if "<!-- compat:" not in head:
        raise ReleaseError("%s sem o banner de compat" % promptmod.SHIPPED)


def install(core, version):
    """Garante a release `version` instalada. Devolve (caminho, commit). Tag movida → ReleaseError."""
    commit = tag_commit(core, version)
    if not commit:
        raise ReleaseError("a tag %s não existe no núcleo %s" % (version, core))
    dest = release_path(core, version)
    # Pasta já instalada não se reescreve. Um hdev anterior (sem write_shipped) pode ter
    # deixado a release sem PROMPT-ORCHESTRATOR.md; a próxima versão nasce completa.
    if os.path.isdir(dest):
        meta = read_json(os.path.join(dest, RELEASE_META)) or {}
        if meta.get("commit") != commit:
            raise ReleaseError("release %s instalada com commit %s, mas a tag aponta para %s (tag movida?). "
                               "Não sobrescrevo: o operador decide." % (version, meta.get("commit"), commit))
        return dest, commit
    r = _git(core, "archive", "--format=tar", commit, binary=True)
    if r.returncode != 0:
        raise ReleaseError("git archive %s falhou: %s" % (version, (r.stderr or b"").decode(errors="replace")))
    os.makedirs(releases_dir(core), exist_ok=True)
    tmp = dest + ".tmp-%d" % os.getpid()
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tar:
            tar.extractall(tmp, filter="data")
        _ensure_prompt(tmp)
        with open(os.path.join(tmp, RELEASE_META), "w", encoding="utf-8") as f:
            json.dump({"version": version, "commit": commit, "core": os.path.realpath(core)}, f, indent=2)
            f.write("\n")
        os.rename(tmp, dest)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return dest, commit


def lock_data(core, version, commit, modo=None, channel=None):
    data = {"version": version, "commit": commit, "core": os.path.realpath(core)}
    if channel:
        data["channel"] = channel  # latest: segue a release promovida; pinned: fica em `version`
        data["releases"] = releases_dir(core)
    if modo:
        data["modo"] = modo  # "skill": repo de área ligado com `hdev init --skill-only`
    return data


def verify(root):
    """(ok, detalhe) do par link + lock no app. Sem nenhum dos dois: não se aplica (ok)."""
    link, lock_path = os.path.join(root, LINK), os.path.join(root, LOCK)
    has_link, has_lock = os.path.islink(link) or os.path.exists(link), os.path.exists(lock_path)
    if not has_link and not has_lock:
        return True, "sem .harnessdev (núcleo ou repo sem init)"
    if not has_lock:
        return False, ".harnessdev sem .harnessdev.lock"
    lock = read_json(lock_path)
    if not lock or not all(isinstance(lock.get(k), str) for k in ("version", "commit", "core")):
        return False, ".harnessdev.lock inválido (precisa de version, commit e core)"
    if not has_link:
        return False, "falta o symlink .harnessdev (rode hdev init)"
    if not os.path.islink(link):
        return False, ".harnessdev não é symlink (o núcleo não se copia para o app)"
    releases = lock.get("releases") if isinstance(lock.get("releases"), str) else releases_dir(lock["core"])
    if lock.get("channel") == CHANNEL_LATEST:
        return _verify_latest(link, releases)
    expected = os.path.join(releases, lock["version"])
    actual = os.path.realpath(link)
    if actual != os.path.realpath(expected):
        return False, ".harnessdev aponta para %s, mas o lock fixa %s" % (actual, expected)
    if not os.path.isdir(actual):
        return False, "release %s não instalada em %s" % (lock["version"], expected)
    meta = read_json(os.path.join(actual, RELEASE_META)) or {}
    if meta.get("version") != lock["version"]:
        return False, "release em %s declara versão %s, o lock fixa %s" % (expected, meta.get("version"),
                                                                           lock["version"])
    if meta.get("commit") != lock["commit"]:
        return False, "release %s tem commit %s, o lock fixa %s" % (lock["version"], meta.get("commit"),
                                                                     lock["commit"])
    return True, "%s (%s)" % (lock["version"], lock["commit"][:12])


def _verify_latest(link, releases):
    """Canal latest: o link é `<releases>/latest` (não a pasta resolvida) e ele resolve para uma release."""
    expected = os.path.join(releases, LATEST)
    if os.readlink(link) != expected:
        return False, ".harnessdev aponta para %s, mas o canal latest pede %s" % (os.readlink(link), expected)
    actual = os.path.realpath(link)
    meta = read_json(os.path.join(actual, RELEASE_META)) or {}
    if not os.path.isdir(actual) or not meta.get("version") or not meta.get("commit"):
        return False, "canal latest sem release promovida em %s" % expected
    if os.path.basename(actual) != meta["version"]:
        return False, "latest resolve para %s, que declara versão %s" % (actual, meta["version"])
    return True, "latest -> %s (%s)" % (meta["version"], meta["commit"][:12])
