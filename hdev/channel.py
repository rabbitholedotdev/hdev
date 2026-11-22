"""Canal latest (F2-01): `hdev release` promove, `hdev rollback` volta, `hdev pin` fixa ou solta um app.

`<releases>/latest` é um symlink para a última release promovida. Promover exige um `hdev judge` pass em
`<núcleo>/.hdev/runs/` cujo `head_sha` é o commit da tag, ou um ancestral dele que só difere em `docs/` e
`hdev/__init__.py`/`CHANGELOG.md` (o commit de versão). Cada promoção e cada rollback entram em `<releases>/latest-history.jsonl`.
"""
import datetime
import glob
import json
import os
import subprocess

from . import init as initmod
from . import release
from . import versao

HISTORY = "latest-history.jsonl"
RELEASE_ONLY = ("docs/", "hdev/__init__.py", "CHANGELOG.md")


def _git(core, *args):
    try:
        r = subprocess.run(["git", "-C", core, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def history_path(core):
    return os.path.join(release.releases_dir(core), HISTORY)


def history(core):
    try:
        with open(history_path(core), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and release.VERSION_RX.match(str(item.get("version", ""))):
            out.append(item)
    return out


def _only_release_files(core, old, new):
    changed = _git(core, "diff", "--name-only", old, new)
    if changed is None:
        return False
    return all(path.startswith(RELEASE_ONLY[0]) or path in RELEASE_ONLY[1:] for path in changed.splitlines() if path)


def judge_pass(core, commit):
    """(run, detalhe) do juiz que libera `commit`, ou (None, motivo)."""
    runs = sorted(glob.glob(os.path.join(core, ".hdev", "runs", "judge-*.json")), reverse=True)
    for path in runs:
        data = release.read_json(path) or {}
        head = data.get("head_sha")
        if data.get("verdict") != "pass" or not isinstance(head, str) or data.get("dirty"):
            continue
        run = os.path.basename(path)[:-5]
        if head == commit:
            return run, "juiz pass no próprio commit"
        if (_git(core, "merge-base", "--is-ancestor", head, commit) is not None
                and _only_release_files(core, head, commit)):
            return run, "juiz pass em %s; até a tag só docs/, hdev/__init__.py e CHANGELOG.md" % head[:12]
    return None, "nenhum hdev judge pass (sem mudanças locais) com head no commit %s" % commit[:12]


def _set_latest(core, version, action, run=None):
    link = release.latest_path(core)
    previous = release.current_latest(core)
    tmp = "%s.tmp-%d" % (link, os.getpid())
    if os.path.lexists(tmp):
        os.remove(tmp)
    os.symlink(version, tmp)  # relativo: a pasta de releases pode mudar de lugar inteira
    os.replace(tmp, link)
    entry = {"ts": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "action": action,
             "version": version, "commit": release.tag_commit(core, version),
             "previous": previous[0] if previous else None}
    if run:
        entry["run"] = run
    with open(history_path(core), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def promote(core, version):
    """Instala e promove `version` para latest se houver juiz pass. Devolve (promovida?, detalhe)."""
    dest, commit = release.install(core, version)
    run, detail = judge_pass(core, commit)
    if not run:
        current = release.current_latest(core)
        return False, "release %s instalada em %s; latest continua em %s: %s" % (
            version, dest, current[0] if current else "(nenhuma)", detail)
    current = release.current_latest(core)
    if current and current[0] == version:
        return True, "latest já está em %s (%s)" % (version, run)
    _set_latest(core, version, "promote", run)
    return True, "latest -> %s (%s: %s)" % (version, run, detail)


def tag_release(core, version, message=None):
    """Cria a tag anotada em HEAD (árvore limpa, VERSION igual à tag) se ela ainda não existe."""
    if not release.VERSION_RX.match(version or ""):
        raise release.ReleaseError("versão %r fora do formato vX.Y.Z" % version)
    if release.tag_commit(core, version):
        return False
    status = _git(core, "status", "--porcelain", "--untracked-files=no")
    if status is None or status:
        raise release.ReleaseError("árvore do núcleo com mudanças: commite antes de criar a tag")
    init_py = _git(core, "show", "HEAD:hdev/__init__.py") or ""
    if 'VERSION = "%s"' % version[1:] not in init_py:
        raise release.ReleaseError("hdev/__init__.py em HEAD não declara VERSION = \"%s\"" % version[1:])
    versao.check_core_changelog(core, version)
    if _git(core, "tag", "-a", version, "-m", message or "release %s" % version) is None:
        raise release.ReleaseError("git tag %s falhou" % version)
    return True


def rollback(core, to=None):
    """Volta latest para `to` ou para a promoção anterior à atual. Não precisa de juiz: já foi promovida."""
    current = release.current_latest(core)
    promoted = [e["version"] for e in history(core) if e.get("action") == "promote"]
    if to:
        if to not in promoted:
            raise release.ReleaseError("%s nunca foi promovida para latest; rollback só para release já promovida" % to)
        target = to
    else:
        if not current:
            raise release.ReleaseError("canal latest sem release promovida")
        older = [v for v in reversed(promoted) if v != current[0]]
        seen = list(reversed(promoted))
        if current[0] in seen:
            idx = seen.index(current[0])
            older = [v for v in seen[idx + 1:] if v != current[0]]
        if not older:
            raise release.ReleaseError("não há promoção anterior a %s" % current[0])
        target = older[0]
    release.install(core, target)
    return _set_latest(core, target, "rollback")


def pin(root, version=None, core=None):
    """App: `version` fixa o .harnessdev nessa release; sem versão, volta ao canal latest."""
    root = os.path.realpath(root)
    lock = release.read_json(os.path.join(root, release.LOCK)) or {}
    core = os.path.realpath(core or lock.get("core") or initmod.default_core())
    report = {"target": root, "written": [], "kept": [], "skipped": [], "notes": []}
    modo = lock.get("modo")
    if version:
        version = release.choose_version(core, version)
        dest, commit = release.install(core, version)
        initmod.link_and_lock(root, core, version, commit, dest, True, report, modo, release.CHANNEL_PINNED, dest)
        return "fixado em %s (%s)" % (version, commit[:12])
    latest = release.current_latest(core)
    if not latest:
        raise release.ReleaseError("canal latest sem release promovida em %s" % release.releases_dir(core))
    initmod.link_and_lock(root, core, latest[0], latest[2], latest[1], True, report, modo, release.CHANNEL_LATEST,
                          release.latest_path(core))
    return "canal latest (hoje %s, %s)" % (latest[0], latest[2][:12])


def main_release(args):
    core = os.path.realpath(args.core or initmod.default_core())
    try:
        created = tag_release(core, args.version, args.message)
        ok, detail = promote(core, args.version)
    except release.ReleaseError as e:
        print("hdev release: %s" % e)
        return 1
    print("hdev release %s: %s%s" % (args.version, "tag criada; " if created else "", detail))
    return 0 if ok else 2


def main_rollback(args):
    core = os.path.realpath(args.core or initmod.default_core())
    try:
        entry = rollback(core, args.to)
    except release.ReleaseError as e:
        print("hdev rollback: %s" % e)
        return 1
    print("hdev rollback: latest -> %s (antes %s)" % (entry["version"], entry["previous"]))
    return 0


def main_pin(args):
    if bool(args.version) == bool(args.latest):
        print("hdev pin: diga a versão (vX.Y.Z) ou --latest")
        return 1
    try:
        print("hdev pin em %s: %s" % (os.path.realpath(args.root), pin(args.root, args.version, args.core)))
    except (release.ReleaseError, ValueError) as e:
        print("hdev pin: %s" % e)
        return 1
    return 0
