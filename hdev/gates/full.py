"""Suíte do `hdev fechar`: `gates.full` num clone limpo do HEAD, em shards.

O discover acha os arquivos. Cada shard ganha um `git clone --local` e roda
`python -m unittest` nos seus arquivos, para um teste que escreve arquivo não
ver o diretório do outro. Comando que não é discover roda inteiro, num clone só.
"""
import fnmatch
import os
import platform
import re
import shlex
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

from hdev import config as cfgmod

from . import full_cache

_RAN = re.compile(r"^Ran (\d+) tests? in ", re.M)
_FAIL = re.compile(r"^(?:FAIL|ERROR):\s+(\S+)(?:\s+\(([^)]+)\))?", re.M)
_VERB = re.compile(r"^\S+ \(([^)]+)\) \.\.\. (?:FAIL|ERROR)\s*$", re.M)


class SuiteError(Exception):
    pass


def resolved_shards(cfg):
    """`gates.shards`, ou min(núcleos, 4). Teto 16. Valor inválido vira 1."""
    gates = cfg.get("gates") if isinstance(cfg, dict) else None
    raw = gates.get("shards") if isinstance(gates, dict) else None
    if raw is None:
        return max(1, min(os.cpu_count() or 1, 4))
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return 1
    if n < 1:
        return 1
    return min(n, 16)


def parse_discover(cmd):
    """Spec do `python -m unittest discover`, ou None se o comando é outro."""
    argv = cmd
    if isinstance(cmd, str):
        try:
            argv = shlex.split(cmd)
        except ValueError:
            return None
    if not isinstance(argv, list):
        return None
    try:
        i = argv.index("unittest")
    except ValueError:
        return None
    if i < 1 or argv[i - 1] != "-m" or i + 1 >= len(argv) or argv[i + 1] != "discover":
        return None
    spec = {"exe": str(argv[0]), "start": ".", "pattern": "test*.py", "top": None, "verbose": False}
    args = argv[i + 2:]
    j = 0
    while j < len(args):
        a = args[j]
        nxt = args[j + 1] if j + 1 < len(args) else None
        if a in ("-s", "--start-directory") and nxt:
            spec["start"] = nxt
            j += 2
        elif a.startswith("--start-directory="):
            spec["start"] = a.split("=", 1)[1]
            j += 1
        elif a in ("-p", "--pattern") and nxt:
            spec["pattern"] = nxt
            j += 2
        elif a.startswith("--pattern="):
            spec["pattern"] = a.split("=", 1)[1]
            j += 1
        elif a in ("-t", "--top-level-directory") and nxt:
            spec["top"] = nxt
            j += 2
        elif a.startswith("--top-level-directory="):
            spec["top"] = a.split("=", 1)[1]
            j += 1
        elif a in ("-v", "--verbose"):
            spec["verbose"] = True
            j += 1
        elif a in ("-q", "--quiet"):
            spec["verbose"] = False
            j += 1
        else:
            j += 1
    return spec


def module_names(paths, start, pattern):
    """Arquivos rastreados que o discover pegaria, em ordem estável."""
    start = (start or ".").strip().replace("\\", "/").strip("/")
    prefix = "" if start in ("", ".") else start + "/"
    pattern = pattern or "test*.py"
    out = []
    for path in paths or []:
        path = str(path).replace("\\", "/")
        if prefix and not path.startswith(prefix):
            continue
        if not path.endswith(".py"):
            continue
        if "/__pycache__/" in path or path.endswith("/__init__.py") or path == "__init__.py":
            continue
        if not fnmatch.fnmatch(os.path.basename(path), pattern):
            continue
        if path not in out:
            out.append(path)
    out.sort()
    return out


def split_modules(modules, n):
    """Round-robin. Cada módulo entra uma vez. Sem lista vazia no meio."""
    modules = list(modules or [])
    if not modules:
        return []
    n = max(1, min(int(n), len(modules)))
    groups = [[] for _ in range(n)]
    for i, mod in enumerate(modules):
        groups[i % n].append(mod)
    return groups


def parse_output(text):
    """(contagem, nomes que falharam). O nome longo do parêntese ganha do curto."""
    tests = 0
    found = _RAN.search(text or "")
    if found:
        tests = int(found.group(1))
    names = []
    for match in _FAIL.finditer(text or ""):
        name = match.group(2) or match.group(1)
        if name and name not in names:
            names.append(name)
    for match in _VERB.finditer(text or ""):
        name = match.group(1)
        if name and name not in names:
            names.append(name)
    return tests, names


def command_text(cmd):
    if cmd is None:
        return "(sem comando)"
    if isinstance(cmd, str):
        return cmd
    return " ".join(shlex.quote(str(p)) for p in cmd)


def _secs(value):
    return "%.1f" % float(value)


def trailer(result):
    """Linha `Hdev-Gates-Full:` de um pass, ou None."""
    if not result or not result.get("ok"):
        return None
    return "Hdev-Gates-Full: pass tree=%s tests=%d shards=%d s=%s cache=%s" % (
        result["tree"], int(result["tests"]), int(result["shards"]), _secs(result["wall_s"]), result["cache"])


def summary(result):
    extra = " (veio do cache)" if result.get("cache") == "hit" else ""
    return "suíte: pass tree=%s tests=%d shards=%d wall=%ss serial=%ss cache=%s%s" % (
        result["tree"], int(result["tests"]), int(result["shards"]), _secs(result["wall_s"]),
        _secs(result["serial_s"]), result["cache"], extra)


def format_plan(plan):
    plan = plan or {}
    lines = ["gates.full: %s" % (plan.get("command_text") or "(sem comando)")]
    if not plan.get("command"):
        return "\n".join(lines)
    lines.append("shards: %d" % int(plan.get("workers") or 0))
    groups = plan.get("groups") or []
    if not groups:
        lines.append("  shard 0: comando único")
    else:
        for i, group in enumerate(groups):
            lines.append("  shard %d: %s" % (i, " ".join(group)))
    if plan.get("no_cache"):
        lines.append("cache: miss (--no-cache)")
    else:
        lines.append("cache: %s" % ("hit" if plan.get("hit") else "miss"))
    return "\n".join(lines)


def _git(root, *args):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _python_version(exe):
    if not exe:
        return platform.python_version()
    try:
        r = subprocess.run([exe, "-c", "import platform; print(platform.python_version())"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return platform.python_version()
    ver = (r.stdout or "").strip()
    return ver or platform.python_version()


def _prepare(root, no_cache=False):
    """Contexto da suíte, ou None se não há comando. SuiteError na chave antiga."""
    cfg, err = cfgmod.load(root)
    if err:
        if str(err).startswith("chave antiga"):
            raise SuiteError(err)
        return None
    if not cfg:
        return None
    cmd = cfgmod.gate_command(cfg, "full")
    if not cmd:
        return None
    timeout = cfgmod.gate_timeout(cfg, 900)
    tree = _git(root, "rev-parse", "--verify", "HEAD^{tree}")
    commit = _git(root, "rev-parse", "--verify", "HEAD")
    if not tree or not commit:
        raise SuiteError("não rodei a suíte: sem commit HEAD")
    configured = resolved_shards(cfg)
    spec = parse_discover(cmd)
    modules = []
    groups = None
    if spec:
        listing = _git(root, "ls-tree", "-r", "--name-only", commit)
        modules = module_names(listing.splitlines(), spec["start"], spec["pattern"])
        if modules:
            groups = split_modules(modules, configured)
    workers = len(groups) if groups else 1
    exe = spec["exe"] if spec else (cmd[0] if isinstance(cmd, list) and cmd else "")
    py = _python_version(exe) if exe else platform.python_version()
    key, payload = full_cache.cache_key(tree, cmd, configured, workers, py, timeout)
    hit = None if no_cache else full_cache.load(root, key)
    return {
        "cmd": cmd, "timeout": timeout, "tree": tree, "commit": commit, "configured": configured,
        "spec": spec, "modules": modules, "groups": groups, "workers": workers, "python": py,
        "key": key, "payload": payload, "hit": hit, "no_cache": bool(no_cache),
    }


def plan(root, no_cache=False):
    """Plano sem rodar. `hit` diz se a próxima corrida reusaria o cache."""
    ctx = _prepare(root, no_cache=no_cache)
    if ctx is None:
        return {"command": None, "command_text": "(sem comando)", "workers": 0, "groups": [], "hit": False,
                "no_cache": bool(no_cache)}
    return {
        "command": ctx["cmd"], "command_text": command_text(ctx["cmd"]), "workers": ctx["workers"],
        "groups": ctx["groups"] or [], "hit": ctx["hit"] is not None, "no_cache": bool(no_cache),
        "tree": ctx["tree"], "configured": ctx["configured"],
    }


def _clone(root, commit, dest):
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        r = subprocess.run(["git", "clone", "-q", "--local", "--no-checkout", root, dest],
                           capture_output=True, text=True, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "clone falhou: %s" % e
    if r.returncode != 0:
        return (r.stderr or r.stdout or "clone falhou").strip()[:300]
    try:
        r = subprocess.run(["git", "-C", dest, "checkout", "-q", "--detach", commit],
                           capture_output=True, text=True, timeout=120, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return "checkout falhou: %s" % e
    if r.returncode != 0:
        return (r.stderr or r.stdout or "checkout falhou").strip()[:300]
    return None


def clone_at(root, commit, dest):
    """Clone local e checkout do `commit` em `dest`. None, ou o texto do erro."""
    return _clone(root, commit, dest)


def _shard_argv(spec, paths):
    cmd = [spec["exe"], "-m", "unittest"]
    if spec["verbose"]:
        cmd.append("-v")
    cmd.extend(paths)
    return cmd


def _tail(text):
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return (lines[-1] if lines else "")[:200]


def _run_one(root, commit, dest, cmd, timeout, shell):
    t0 = time.monotonic()
    err = _clone(root, commit, dest)
    if err:
        return {"kind": "error", "ok": False, "tests": 0, "failures": [], "code": 1,
                "elapsed": time.monotonic() - t0, "detail": err}
    try:
        r = subprocess.run(cmd, cwd=dest, shell=shell, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"kind": "timeout", "ok": False, "tests": 0, "failures": [], "code": 1,
                "elapsed": time.monotonic() - t0, "detail": "timeout"}
    except OSError as e:
        return {"kind": "error", "ok": False, "tests": 0, "failures": [], "code": 1,
                "elapsed": time.monotonic() - t0, "detail": str(e)}
    text = (r.stdout or "") + "\n" + (r.stderr or "")
    tests, names = parse_output(text)
    ok = r.returncode == 0 and not names
    if not ok and not names:
        names = [_tail(text) or "exit %d" % r.returncode]
    return {"kind": "pass" if ok else "fail", "ok": ok, "tests": tests, "failures": names,
            "code": r.returncode, "elapsed": time.monotonic() - t0, "detail": _tail(text)}


def _aggregate(parts, wall, timeout):
    kind = "pass"
    for part in parts:
        if part["kind"] in ("timeout", "error"):
            kind = part["kind"]
            break
        if part["kind"] != "pass":
            kind = "fail"
    failures = []
    tests = 0
    serial = 0.0
    code = 0
    detail = ""
    for part in parts:
        tests += part["tests"]
        serial += part["elapsed"]
        if part["code"]:
            code = part["code"]
        if part.get("detail"):
            detail = part["detail"]
        for name in part["failures"]:
            if name and name not in failures:
                failures.append(name)
    if kind == "timeout":
        message = "suíte passou de %ds" % timeout
    elif kind == "error":
        message = "não rodei a suíte: %s" % (detail or "erro")
    elif kind != "pass":
        hint = ", ".join(failures)[:200]
        message = "suíte vermelha (exit %d); hdev fechar exige a suíte inteira verde. %s" % (code or 1, hint)
    else:
        message = ""
        failures = []
    return {"ok": kind == "pass", "kind": kind, "tests": tests, "failures": failures,
            "wall_s": wall, "serial_s": serial, "message": message, "code": code or (0 if kind == "pass" else 1)}


def execute(root, no_cache=False):
    """Roda a suíte, ou devolve o cache. None se não há `gates.full`.

    O resultado de um pass tem `cache` `hit` ou `miss`. Falha não é gravada.
    """
    ctx = _prepare(root, no_cache=no_cache)
    if ctx is None:
        return None
    if ctx["hit"] is not None:
        found = dict(ctx["hit"])
        found["cache"] = "hit"
        found["ok"] = True
        found["kind"] = "pass"
        return found
    parent = tempfile.mkdtemp(prefix="hdev-full-")
    t0 = time.monotonic()
    try:
        if ctx["groups"]:
            spec = ctx["spec"]
            jobs = [(os.path.join(parent, "s%d" % i), _shard_argv(spec, group), False)
                    for i, group in enumerate(ctx["groups"])]
        else:
            shell = isinstance(ctx["cmd"], str)
            jobs = [(os.path.join(parent, "s0"), ctx["cmd"], shell)]
        parts = []
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futs = [pool.submit(_run_one, root, ctx["commit"], dest, cmd, ctx["timeout"], shell)
                    for dest, cmd, shell in jobs]
            for fut in futs:
                parts.append(fut.result())
    finally:
        shutil.rmtree(parent, ignore_errors=True)
    agg = _aggregate(parts, time.monotonic() - t0, ctx["timeout"])
    result = {
        "ok": agg["ok"], "kind": agg["kind"], "tree": ctx["tree"], "tests": agg["tests"],
        "shards": ctx["workers"], "wall_s": agg["wall_s"], "serial_s": agg["serial_s"],
        "failures": agg["failures"], "cache": "miss", "message": agg["message"], "code": agg["code"],
    }
    if result["ok"]:
        full_cache.store(root, ctx["key"], ctx["payload"], result)
    return result
