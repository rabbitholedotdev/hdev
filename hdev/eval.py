"""hdev eval run — um caso, braços isolados, sem mexer na árvore de trabalho.

Cada braço e cada corrida ganham um `git clone --local` no `base_sha` da tarefa.
`plain` tira o andaime. `base` deixa o clone. `cand-<id>` copia `.hdev/overlays/<id>/`
(ou `evals/arms/cand-<id>/`, se não houver) por cima do base e tira o `remove` da ficha
`.hdev/overlays/<id>.json`. O overlay é lido de quem invoca o hdev, não do commit antigo.
Tokens só saem do JSON `usage` do agente. Sem agente, `tokens` é null.
"""
import datetime
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

from . import CORE_ROOT
from . import config as cfgmod
from .gates import full as fullmod
from . import xray as xraymod

RUN_CAP = 12
DEFAULT_AGENT = "claude -p --output-format json"
EVAL_MODEL = "claude-sonnet-5-5"
AGENT_TIMEOUT = 600
# Só entram no executável `claude`, e cada flag só se o comando não a traz. O clone tem origin local: nada de push.
CLAUDE_FLAGS = (
    ("--permission-mode", ["acceptEdits"]),
    ("--allowedTools", ["Bash(python3:*)", "Bash(bin/hdev:*)", "Bash(git status:*)", "Bash(git diff:*)",
                        "Bash(git log:*)"]),
    ("--disallowedTools", ["Bash(git push:*)", "Bash(sudo:*)"]),
)
PREAMBLE = ("Você está num clone descartável deste repositório. Trabalhe só dentro desta pasta: "
            "não leia nem escreva fora dela, não faça push e não use privilégio de root.\n\n")
# Variáveis da sessão de fora: os hooks do clone não podem apontar para a árvore de quem invoca.
AGENT_ENV_DROP = ("CLAUDE_PROJECT_DIR", "CLAUDECODE")
FAKE_USAGE = {"input_tokens": 11, "output_tokens": 7, "cache_read_input_tokens": 3}
STRIP = (
    "CLAUDE.md",
    "AGENTS.md",
    ".claude/settings.json",
    ".claude/skills",
    ".claude/hooks",
    "harness/prompts",
)
_CAND = re.compile(r"^cand-[a-z0-9][a-z0-9-]*$")
_SECTION = re.compile(r"(?m)^##[ \t]+Critério de pronto[ \t]*$")
_TICK = re.compile(r"`([^`\n]+)`")
_CMD = re.compile(r"^(?:bin/hdev|hdev|python3|python)(?:\s|$)")
# sai/exit 0, sai 1, exit = 0, sai ≠ 0, ou um "= 0" solto. Sem isso não há chute.
_EXIT_RE = re.compile(
    r"(?i)\b(?:sai|exit)\b(?:\s+code)?\s*(?:(≠|!=)\s*0|(?:=|==)?\s*(\d+))|(?<![\w.])=\s*(\d+)"
)
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class EvalError(Exception):
    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def _cfg(root):
    cfg, _err = cfgmod.load(root)
    return cfg or {}


def _as_argv(raw):
    if isinstance(raw, list) and raw and all(isinstance(p, str) and p for p in raw):
        return list(raw)
    if isinstance(raw, str) and raw.strip():
        return shlex.split(raw)
    return None


def _eval_cfg(cfg):
    ev = cfg.get("eval") if isinstance(cfg, dict) else None
    return ev if isinstance(ev, dict) else {}


def agent_argv(cfg):
    """Comando do agente. Padrão: `claude -p --output-format json`, com Sonnet e as travas do clone."""
    ev = _eval_cfg(cfg)
    argv = _as_argv(ev.get("agent_cmd")) or shlex.split(DEFAULT_AGENT)
    if os.path.basename(argv[0]) != "claude":
        return argv
    model = ev.get("model") if isinstance(ev.get("model"), str) and ev["model"].strip() else EVAL_MODEL
    for flag, values in (("--model", [model]),) + CLAUDE_FLAGS:
        if flag not in argv:
            argv += [flag] + values
    return argv


def argv_model(argv):
    """Modelo que o argv pede (`--model X`), ou None."""
    if argv and "--model" in argv[:-1]:
        return argv[argv.index("--model") + 1]
    return None


def agent_timeout(cfg):
    value = _eval_cfg(cfg).get("timeout_sec")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return AGENT_TIMEOUT
    return value


def fake_argv(cfg):
    """Processo que imprime um JSON com usage. Não chama modelo."""
    ev = cfg.get("eval") if isinstance(cfg, dict) else None
    raw = ev.get("fake_cmd") if isinstance(ev, dict) else None
    argv = _as_argv(raw)
    if argv:
        return argv
    payload = json.dumps({"usage": FAKE_USAGE})
    return [sys.executable, "-c", "print(%r)" % payload]


def command_missing(argv):
    if not argv:
        return True
    exe = argv[0]
    if os.sep in exe:
        return not (os.path.isfile(exe) and os.access(exe, os.X_OK))
    return shutil.which(exe) is None


def strip_list(root):
    path = os.path.join(root, "evals", "arms", "plain", "arm.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return list(STRIP)
    listed = data.get("strip") if isinstance(data, dict) else None
    if isinstance(listed, list) and listed and all(isinstance(item, str) and item for item in listed):
        return list(listed)
    return list(STRIP)


def _remove(path):
    if os.path.islink(path) or os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)


def _copy_tree(src, dest):
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [name for name in dirnames if name not in (".git", "__pycache__")]
        rel = os.path.relpath(dirpath, src)
        target = dest if rel == "." else os.path.join(dest, rel)
        os.makedirs(target, exist_ok=True)
        for name in filenames:
            shutil.copy2(os.path.join(dirpath, name), os.path.join(target, name))


def cand_dir(root, arm):
    """Pasta do overlay: `.hdev/overlays/<id>/` primeiro, `evals/arms/cand-<id>/` depois."""
    over = os.path.join(root, ".hdev", "overlays", arm[len("cand-"):])
    return over if os.path.isdir(over) else os.path.join(root, "evals", "arms", arm)


def overlay_meta(root, cid):
    """Ficha `.hdev/overlays/<id>.json`, ou {} se não houver."""
    try:
        with open(os.path.join(root, ".hdev", "overlays", cid + ".json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def safe_rel(rel):
    """Caminho relativo sem `..` e sem raiz, em `/`; None se não serve."""
    if not isinstance(rel, str) or not rel.strip() or rel.startswith("/") or "\\" in rel:
        return None
    parts = [p for p in rel.strip().split("/") if p not in ("", ".")]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def apply_arm(clone, arm, root):
    """Aplica o braço no clone. `root` é quem invoca (o overlay mora lá)."""
    if arm == "base":
        return
    if arm == "plain":
        for rel in strip_list(root):
            _remove(os.path.join(clone, *rel.split("/")))
        return
    if _CAND.match(arm or ""):
        src = cand_dir(root, arm)
        if not os.path.isdir(src):
            raise EvalError("braço %s sem pasta .hdev/overlays/ nem evals/arms/" % arm)
        _copy_tree(src, clone)
        for raw in overlay_meta(root, arm[len("cand-"):]).get("remove") or []:
            rel = safe_rel(raw)
            if rel is None:
                raise EvalError("remove inválido: %r" % raw)
            _remove(os.path.join(clone, *rel.split("/")))
        return
    raise EvalError("braço desconhecido: %s" % arm)


def parse_arms(root, text):
    if not isinstance(text, str) or not text.strip():
        raise EvalError("falta --arms")
    arms = [part.strip() for part in text.split(",") if part.strip()]
    if not arms:
        raise EvalError("falta --arms")
    for arm in arms:
        if arm in ("plain", "base"):
            continue
        if not _CAND.match(arm):
            raise EvalError("braço desconhecido: %s" % arm)
        if not os.path.isdir(cand_dir(root, arm)):
            raise EvalError("braço %s sem pasta .hdev/overlays/ nem evals/arms/" % arm)
    return arms


def run_budget(task, arms, runs):
    """Teto duro 12, e o `caps.runs` da tarefa se for menor."""
    cap = RUN_CAP
    caps = task.get("caps") if isinstance(task, dict) else None
    if isinstance(caps, dict) and "runs" in caps:
        try:
            cap = min(RUN_CAP, int(caps["runs"]))
        except (TypeError, ValueError):
            cap = RUN_CAP
    if runs < 1:
        raise EvalError("--runs pede um inteiro >= 1")
    total = len(arms) * runs
    if total > cap:
        raise EvalError("%d braços × %d corridas = %d; o teto é %d por tarefa" % (len(arms), runs, total, cap))
    return cap


def load_task(root, case_id):
    if not case_id or not _SAFE_ID.match(case_id):
        raise EvalError("caso ausente: %s" % case_id)
    path = os.path.join(root, "evals", "tasks", case_id, "task.json")
    if not os.path.isfile(path):
        raise EvalError("caso ausente: %s" % case_id)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise EvalError("caso %s inválido: %s" % (case_id, e))
    if not isinstance(data, dict):
        raise EvalError("caso %s inválido" % case_id)
    if data.get("id") not in (None, case_id):
        raise EvalError("caso %s com id %s" % (case_id, data.get("id")))
    return data


def task_repo(root, task):
    repo = task.get("repo") or "."
    if not isinstance(repo, str) or not repo.strip():
        raise EvalError("repo ausente")
    path = root if repo == "." else (repo if os.path.isabs(repo) else os.path.join(root, repo))
    path = os.path.realpath(path)
    if not os.path.isdir(os.path.join(path, ".git")) and not os.path.isfile(os.path.join(path, ".git")):
        raise EvalError("repo sem git: %s" % repo)
    return path


def resolve_commit(repo, sha):
    try:
        proc = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", "%s^{commit}" % sha],
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise EvalError("git falhou: %s" % e)
    commit = (proc.stdout or "").strip()
    if proc.returncode != 0 or not commit:
        raise EvalError("base_sha inválida: %s" % sha)
    return commit


def agent_wanted(task, runner):
    """`auto` só roda com prompt. `fake` e `claude` rodam mesmo sem prompt."""
    if runner == "none":
        return False
    if runner == "auto":
        prompt = task.get("prompt")
        return isinstance(prompt, str) and bool(prompt.strip())
    if runner == "claude":
        prompt = task.get("prompt")
        if not (isinstance(prompt, str) and prompt.strip()):
            raise EvalError("runner claude pede prompt no caso; sem ele o modelo roda à toa")
        return True
    if runner == "fake":
        return True
    raise EvalError("runner desconhecido: %s" % runner)


def _num(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _cache(usage):
    read = usage.get("cache_read_input_tokens")
    create = usage.get("cache_creation_input_tokens")
    if read is None and create is None:
        return _num(usage.get("cache_tokens")) if "cache_tokens" in usage else None
    total = 0
    seen = False
    for value in (read, create):
        num = _num(value)
        if num is None:
            continue
        total += num
        seen = True
    return total if seen else None


def _usage_dicts(text, key="usage"):
    found = []
    raw = (text or "").strip()
    if not raw:
        return found
    chunks = [raw]
    chunks.extend(line.strip() for line in raw.splitlines() if line.strip().startswith("{"))
    for chunk in chunks:
        try:
            obj = json.loads(chunk)
        except ValueError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get(key), dict):
            found.append(obj[key])
    return found


def parse_model(text):
    """Modelo de mais tokens de saída no último `modelUsage` (o haiku auxiliar não ganha), ou None."""
    found = [usage for usage in _usage_dicts(text, "modelUsage") if usage]
    if not found:
        return None

    def out(item):
        stats = item[1] if isinstance(item[1], dict) else {}
        return _num(stats.get("outputTokens")) or 0
    return max(found[-1].items(), key=out)[0]


def model_ok(wanted, got):
    """O modelo medido começa com o pedido (aceita sufixo de data)."""
    return isinstance(got, str) and got.startswith(wanted)


def parse_usage(text):
    """`{input, output, cache}` do último usage, ou None se o agente não mandou."""
    found = _usage_dicts(text)
    if not found:
        return None
    usage = found[-1]
    return {"input": _num(usage.get("input_tokens")), "output": _num(usage.get("output_tokens")),
            "cache": _cache(usage)}


def _sub(text, tmp, core, clone):
    return str(text).replace("{tmp}", tmp).replace("{core}", core).replace("{clone}", clone)


def _needs(steps, needle):
    try:
        blob = json.dumps(steps)
    except (TypeError, ValueError):
        return False
    return needle in blob


def hdev_invoke(args, cwd):
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_PROJECT_DIR"}
    try:
        proc = subprocess.run([sys.executable, os.path.join(CORE_ROOT, "bin", "hdev"), *args],
                              capture_output=True, text=True, cwd=cwd, timeout=300, env=env)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _run_cmd(cmd, cwd, tmp, core, clone):
    if isinstance(cmd, str):
        try:
            argv = shlex.split(cmd)
        except ValueError as e:
            return 1, str(e)
    elif isinstance(cmd, list):
        argv = [str(part) for part in cmd]
    else:
        return 1, "cmd inválido"
    argv = [_sub(part, tmp, core, clone) for part in argv]
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _expected_label(step):
    if step.get("expect_nonzero"):
        return "≠ 0"
    return str(step.get("expect_exit", 0))


def _exit_ok(step, code):
    """Exit bate com o passo. Sem chave, o padrão antigo continua 0."""
    if step.get("expect_nonzero"):
        return code != 0
    return code == step.get("expect_exit", 0)


def execute_steps(steps, tmp, core, clone, invoke=None):
    """(falhas, exit codes). `invoke` roda um argv do hdev e devolve (code, saída)."""
    if invoke is None:
        invoke = lambda args: hdev_invoke(args, clone or tmp)  # noqa: E731
    failures = []
    codes = []
    for n, step in enumerate(steps or [], 1):
        if not isinstance(step, dict):
            failures.append("passo %d: tipo desconhecido" % n)
            continue
        if "run" in step:
            args = [_sub(part, tmp, core, clone) for part in step["run"]]
            code, out = invoke(args)
            codes.append(code)
            if not _exit_ok(step, code):
                failures.append("passo %d (%s): exit %d, esperado %s\n%s" % (
                    n, " ".join(step["run"]), code, _expected_label(step), out))
            if step.get("expect_output") and step["expect_output"] not in out:
                failures.append("passo %d: saída sem %r" % (n, step["expect_output"]))
        elif "cmd" in step:
            code, out = _run_cmd(step["cmd"], clone or tmp, tmp, core, clone)
            codes.append(code)
            if not _exit_ok(step, code):
                failures.append("passo %d (cmd): exit %d, esperado %s\n%s" % (
                    n, code, _expected_label(step), out))
            if step.get("expect_output") and step["expect_output"] not in out:
                failures.append("passo %d: saída sem %r" % (n, step["expect_output"]))
        elif "append_lines" in step:
            spec = step["append_lines"]
            try:
                with open(os.path.join(tmp, spec["file"]), "a", encoding="utf-8") as handle:
                    handle.write("linha\n" * int(spec["count"]))
            except (OSError, KeyError, TypeError, ValueError) as e:
                failures.append("passo %d: %s" % (n, e))
        else:
            failures.append("passo %d: tipo desconhecido %s" % (n, sorted(step)))
    return failures, codes


def run_agent(argv, prompt, cwd, timeout=AGENT_TIMEOUT):
    env = {key: value for key, value in os.environ.items() if key not in AGENT_ENV_DROP}
    try:
        proc = subprocess.run(argv, input=prompt or "", capture_output=True, text=True, cwd=cwd, timeout=timeout,
                              env=env)
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"
    except OSError as e:
        return 1, "", str(e)
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _safe_arm(arm):
    return re.sub(r"[^A-Za-z0-9._-]", "_", arm)[:40]


def _one(root, repo, sha, task, arm, n, want, argv, parent, model=None, timeout=AGENT_TIMEOUT, real=False):
    t0 = time.monotonic()
    dest = os.path.join(parent, "%s-%d" % (_safe_arm(arm), n))
    failures = []
    codes = []
    tokens = None
    agent_exit = None
    got_model = None
    xray_total = None
    err = fullmod.clone_at(repo, sha, dest)
    if err:
        failures.append("clone: %s" % err)
    else:
        try:
            apply_arm(dest, arm, root)
        except EvalError as e:
            failures.append(str(e))
        try:
            xray_total = xraymod.measure(dest)["total"]
        except Exception:
            xray_total = None
        if want:
            prompt = task.get("prompt") if isinstance(task.get("prompt"), str) else ""
            agent_exit, out, err_text = run_agent(argv, (PREAMBLE + prompt) if real else prompt, dest, timeout)
            tokens = parse_usage(out)
            got_model = parse_model(out)
            if err_text == "timeout" and not out:
                failures.append("agente timeout (%ss)" % timeout)
            elif agent_exit != 0:
                failures.append("agente exit %s" % agent_exit)
        steps = task.get("acceptance") or []
        tmp = tempfile.mkdtemp(prefix="hdev-eval-tmp-", dir=parent)
        core = ""
        if not failures and _needs(steps, "{core}"):
            core_dest = dest + "-core"
            core_err = fullmod.clone_at(repo, sha, core_dest)
            if core_err:
                failures.append("core: %s" % core_err)
            else:
                core = core_dest
        if not any(item.startswith("clone:") or item.startswith("core:") for item in failures):
            step_failures, codes = execute_steps(steps, tmp, core, dest if not err else tmp)
            failures.extend(step_failures)
    row = {
        "arm": arm, "run": n, "pass": not failures, "tokens": tokens,
        "seconds": round(time.monotonic() - t0, 3), "exit_codes": codes,
        "agent_exit": agent_exit, "xray": xray_total,
    }
    if model:
        row["model"] = got_model
        row["model_ok"] = model_ok(model, got_model)
    if failures:
        row["failures"] = failures
    return row


def _payload(case, repo, sha, runner, arms, runs):
    return {
        "kind": "eval", "version": 1, "case": case, "repo": repo, "base_sha": sha,
        "runner": runner, "arms": arms, "runs": runs, "xray_method": xraymod.METHOD,
    }


def write_run(root, payload):
    folder = os.path.join(root, ".hdev", "runs")
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = "eval-%s.json" % stamp
    path = os.path.join(folder, name)
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
    return name


def run(root, case, arms, runs, runner, dry_run=False):
    root = os.path.realpath(root)
    task = load_task(root, case)
    parsed = parse_arms(root, arms)
    run_budget(task, parsed, runs)
    repo = task_repo(root, task)
    sha = resolve_commit(repo, task.get("base_sha") or "HEAD")
    want = agent_wanted(task, runner)
    argv = None
    model = None
    cfg = _cfg(root)
    if want:
        argv = fake_argv(cfg) if runner == "fake" else agent_argv(cfg)
        model = None if runner == "fake" else argv_model(argv)
        if command_missing(argv):
            payload = _payload(case, task.get("repo") or ".", sha, runner, parsed, runs)
            payload["error"] = "agente ausente: %s" % argv[0]
            name = write_run(root, payload)
            raise EvalError("agente ausente: %s (registro .hdev/runs/%s)" % (argv[0], name), code=3)
    acceptance = task.get("acceptance") or []
    if dry_run:
        return {"dry_run": True, "case": case, "arms": parsed, "runs": runs, "runner": runner,
                "base_sha": sha, "acceptance": acceptance, "agent": want, "model": model}
    parent = tempfile.mkdtemp(prefix="hdev-eval-")
    try:
        results = [_one(root, repo, sha, task, arm, n, want, argv, parent, model, agent_timeout(cfg),
                        runner != "fake")
                   for arm in parsed for n in range(1, runs + 1)]
    finally:
        shutil.rmtree(parent, ignore_errors=True)
    payload = _payload(case, task.get("repo") or ".", sha, runner, parsed, runs)
    payload["model"] = model
    payload["results"] = results
    name = write_run(root, payload)
    return {"run": name, "results": results, "case": case, "runner": runner, "arms": parsed, "runs": runs,
            "base_sha": sha, "model": model}


def _format_row(row):
    tokens = row.get("tokens")
    if tokens is None:
        shown = "null"
    else:
        shown = "in=%s out=%s cache=%s" % (tokens.get("input"), tokens.get("output"), tokens.get("cache"))
    flag = "pass" if row.get("pass") else "fail"
    line = "  %s#%s: %s tokens=%s %.3fs xray=%s" % (
        row.get("arm"), row.get("run"), flag, shown, row.get("seconds") or 0, row.get("xray"))
    if "model" in row:
        line += " model=%s" % row["model"] + ("" if row.get("model_ok") else " [modelo ≠ pedido]")
    return line


def main_run(args):
    try:
        res = run(args.root, args.case, args.arms, args.runs, args.runner, args.dry_run)
    except EvalError as e:
        print("hdev eval: %s" % e)
        return e.code
    if res.get("dry_run"):
        print("hdev eval: dry-run")
        print("  caso: %s" % res["case"])
        print("  base: %s" % res["base_sha"][:12])
        print("  braços: %s" % ", ".join(res["arms"]))
        print("  corridas: %d" % res["runs"])
        print("  runner: %s" % res["runner"])
        if res.get("model"):
            print("  modelo: %s" % res["model"])
        print("  aceite: %d passos" % len(res["acceptance"]))
        return 0
    print("hdev eval: %s %s × %d" % (res["case"], ",".join(res["arms"]), res["runs"]))
    for row in res["results"]:
        print(_format_row(row))
        if row.get("failures"):
            print("    %s" % row["failures"][0].splitlines()[0][:200])
    print("  registro: .hdev/runs/%s" % res["run"])
    return 0 if all(row.get("pass") and row.get("model_ok", True) for row in res["results"]) else 1


def normalize_cmd(cmd):
    """`hdev ...` vira `bin/hdev ...`. O binário solto não está no PATH."""
    cmd = " ".join((cmd or "").split())
    if cmd == "hdev" or cmd.startswith("hdev "):
        cmd = "bin/" + cmd
    return cmd


def parse_exit(span):
    """('eq', n) ou ('nonzero', None). None se a frase não fecha o exit."""
    match = _EXIT_RE.search(span or "")
    if not match:
        return None
    if match.group(1):
        return ("nonzero", None)
    number = match.group(2) if match.group(2) is not None else match.group(3)
    if number is None:
        return None
    return ("eq", int(number))


def _criterio(text):
    match = _SECTION.search(text or "")
    if not match:
        return None
    rest = text[match.end():]
    nxt = re.search(r"(?m)^##[ \t]+", rest)
    return rest[:nxt.start()] if nxt else rest


def _span_after(body, end):
    """Texto do comando até a quebra de linha ou o próximo crase."""
    rest = body[end:]
    cuts = [pos for pos in (rest.find("\n"), rest.find("`")) if pos >= 0]
    return rest[:min(cuts)] if cuts else rest


def _step(cmd, parsed):
    if parsed[0] == "nonzero":
        return {"cmd": cmd, "expect_nonzero": True}
    return {"cmd": cmd, "expect_exit": parsed[1]}


def commands_from_plan(text):
    """(passos, confiante). `hdev` e `bin/hdev` viram um só. Exit ilegível não vira 0."""
    body = _criterio(text)
    if body is None:
        return [], False
    found = []
    for match in _TICK.finditer(body):
        raw = match.group(1).strip()
        if not _CMD.match(raw):
            continue
        found.append((normalize_cmd(raw), parse_exit(_span_after(body, match.end()))))
    order = []
    groups = {}
    for cmd, parsed in found:
        groups.setdefault(cmd, []).append(parsed)
        # A menção sem exit não puxa o comando para antes da frase que fecha.
        if parsed is not None and cmd not in order:
            order.append(cmd)
    for cmd in groups:
        if cmd not in order:
            order.append(cmd)
    if not order:
        return [], False
    items = []
    confident = True
    for cmd in order:
        parses = [item for item in groups[cmd] if item is not None]
        if not parses or any(item != parses[0] for item in parses[1:]):
            confident = False
            continue
        items.append(_step(cmd, parses[0]))
    if not items:
        confident = False
    return items, confident


def acceptance_from_plan(text):
    """Passos com exit lido do critério. Lista vazia se nada fecha com confiança."""
    items, confident = commands_from_plan(text)
    return items if confident else []


def _spec_rel(root, uid):
    rel = "work/%s/spec.md" % uid
    if os.path.isfile(os.path.join(root, rel)):
        return rel
    return None


def record_case(root, uid, plan_text, base_sha, plan_rel):
    """Grava `evals/tasks/<id>/task.json` depois do portão. Devolve o caminho relativo."""
    if not uid or not _SAFE_ID.match(uid):
        raise OSError("id de unidade inválido: %s" % uid)
    rel = "evals/tasks/%s/task.json" % uid
    path = os.path.join(root, rel)
    old = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                old = loaded
        except (OSError, ValueError):
            old = {}
    acceptance, confident = commands_from_plan(plan_text)
    draft = not confident
    prompt = old.get("prompt") if isinstance(old.get("prompt"), str) else None
    caps = dict(old.get("caps")) if isinstance(old.get("caps"), dict) else {}
    caps["runs"] = 12
    task = {
        "id": uid,
        "repo": ".",
        "base_sha": base_sha,
        "prompt": prompt,
        "spec": _spec_rel(root, uid),
        "acceptance": acceptance,
        "caps": caps,
        "draft": draft,
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(task, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
    return rel.replace(os.sep, "/")
