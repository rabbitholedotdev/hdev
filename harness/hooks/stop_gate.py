#!/usr/bin/env python3
"""Stop: testes afetados, PAREI, progress e o handoff que antes era o terceiro registro.

`hooks/gate_tests.py` delega para `gate_main`. `hooks/progress_guard.py` delega para `progress_main`.
Os dois, em sequência, mais o handoff de Stop, rodam em `main`.
"""
import os
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "hooks")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _lib  # noqa: E402
from hdev import config as cfgmod  # noqa: E402
from hdev import stop as stopmod  # noqa: E402

GATE = "gate_tests"
PROGRESS = "progress_guard"
PROGRESS_FILE = "docs/progress.md"
LIMIT = 2000
IGNORED_PREFIXES = ("logs/", ".hdev/state/", ".hdev/runs/", "docs/decisions.md")


def _event(event):
    if event is None:
        return _lib.read_event()
    return event


def gate_on(gates):
    env = os.environ.get("HDEV_GATE_TESTS")
    if env == "1":
        return True
    if env == "0":
        return False
    return (gates or {}).get("on_stop") is not False


def _run(cmd, root, timeout):
    try:
        r = subprocess.run(cmd, cwd=root, shell=isinstance(cmd, str), capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or ""), False
    except subprocess.TimeoutExpired:
        return False, "testes passaram de %ds (timeout)" % timeout, True
    except OSError as e:
        return False, "não consegui rodar os testes: %s" % e, False


def _timeout(root):
    gates = _lib.load_config(root).get("gates") or {}
    try:
        return int(gates.get("timeout", 600) or 600)
    except (TypeError, ValueError):
        return 600


def _slice(root, cmd):
    if not stopmod.is_suite_command(cmd):
        return cmd, _timeout(root)
    paths = stopmod.changed_files(root)
    if not paths:
        return None, 0
    argv = stopmod.stop_argv(root, paths)
    if not argv:
        return None, 0
    return argv, stopmod.STOP_TIMEOUT


def gate_main(event=None):
    if _lib.nested():
        return 0
    event = _event(event)
    root = _lib.project_root(event)
    if _lib.closed_stop(root, event):
        return 0
    raw = _lib.load_config(root)
    err = cfgmod.legacy_error(raw)
    if err:
        sys.stderr.write("gate_tests: %s\n" % err)
        return 2
    gates = raw.get("gates") if isinstance(raw.get("gates"), dict) else {}
    if not gate_on(gates):
        return 0
    cmd = gates.get("fast")
    if not cmd:
        sys.stderr.write("gate_tests: sem gates.fast em .hdev/config.json; nada a conferir.\n")
        return 0
    argv, timeout = _slice(root, cmd)
    if argv is None:
        return 0
    started = time.monotonic()
    ok, out, timed_out = _run(argv, root, timeout)
    if timed_out and stopmod.is_suite_command(cmd):
        smoke = stopmod.stop_argv(root, [])
        if smoke and smoke != argv:
            ok, out, _ = _run(smoke, root, stopmod.SMOKE_TIMEOUT)
            out = "recorte passou de %ds; smoke. %s" % (stopmod.STOP_TIMEOUT, out)
    seconds = round(time.monotonic() - started, 2)
    _lib.record_metric(root, {"event": GATE, "ok": ok, "seconds": seconds})
    if ok:
        _lib.loop_guard_reset(root, GATE)
        return 0
    if _lib.loop_guard_exceeded(root, GATE, event.get("session_id", "")):
        line = stopmod.write_exhausted(root, GATE, stopmod.short_red(out))
        _lib.record_metric(root, {"event": GATE, "parei": True})
        sys.stderr.write("gate_tests: trava esgotada. %s\n" % (line or "").strip())
        return 0
    tail = _lib.redact(out[-20000:])[-3000:]
    _lib.block("gate_tests: critério de pronto vermelho (%ss). Corrija antes de encerrar. "
               "Parada só com PAREI da lista fechada (2FA/login ou ação destrutiva).\n%s" % (seconds, tail))


def changed_paths(root):
    out = _lib.git(root, "status", "--porcelain", "--untracked-files=all")
    if out is None:
        return None
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if line.startswith("??") and path.startswith("evals/tasks/"):
            continue  # caso que o `hdev fechar` deixa fora da base, sem commit de propósito (PRD, Evals e xray)
        if not path.startswith(IGNORED_PREFIXES):
            paths.append(path)
    return paths


def problem(root, event=None):
    if _lib.closed_stop(root, event or {}):
        return None
    progress = os.path.join(root, PROGRESS_FILE)
    if os.path.exists(progress):
        with open(progress, encoding="utf-8") as f:
            size = len(f.read())
        if size > LIMIT:
            return "%s tem %d caracteres (teto %d). Encurte: fica o estado atual, sai o histórico." % (
                PROGRESS_FILE, size, LIMIT)
    paths = changed_paths(root)
    if not paths:
        return None
    if PROGRESS_FILE not in paths:
        shown = ", ".join(paths[:5]) + (" ..." if len(paths) > 5 else "")
        return "%d arquivo(s) mudaram (%s) e %s não foi atualizado." % (len(paths), shown, PROGRESS_FILE)
    return None


def progress_main(event=None):
    if _lib.nested():
        return 0
    event = _event(event)
    root = _lib.project_root(event)
    why = problem(root, event)
    if not why:
        _lib.loop_guard_reset(root, PROGRESS)
        return 0
    if _lib.loop_guard_exceeded(root, PROGRESS, event.get("session_id", "")):
        line = stopmod.write_exhausted(root, PROGRESS, why)
        sys.stderr.write("progress_guard: trava esgotada. %s\n" % (line or "").strip())
        return 0
    _lib.block("progress_guard: " + why)


OPEN_UNIT = "open_unit"


def _handoff_allows(root, event):
    """A sessão aposentada pelo handoff pode encerrar. Codex e Grok chamam este mesmo script."""
    try:
        from hdev import handoff as handoffmod
        return handoffmod.stop_permitted(handoffmod.load_state(root), _session(event))
    except Exception:
        return False


def _session(event):
    return event.get("session_id") or event.get("sessionId") or ""


def open_unit_main(event=None):
    """Unidade aberta segura o Stop. PAREI da lista, handoff e unidade ausente liberam."""
    if _lib.nested():
        return 0
    event = _event(event)
    root = _lib.project_root(event)
    if _lib.closed_stop(root, event) or _handoff_allows(root, event):
        _lib.loop_guard_reset(root, OPEN_UNIT)
        return 0
    from hdev import unit as unitmod
    rec = unitmod.load(root)
    status = (rec or {}).get("status")
    if status == "blocked":
        return _blocked_stop(root, event, rec)
    if status != "open":
        _lib.loop_guard_reset(root, OPEN_UNIT)
        return 0
    nxt = unitmod.next_of(root, rec)
    if _lib.loop_guard_exceeded(root, OPEN_UNIT, _session(event)):
        line = stopmod.write_exhausted(root, OPEN_UNIT, nxt)
        sys.stderr.write("open_unit: trava esgotada. %s\n" % (line or "").strip())
        return 0
    _lib.block("unidade %s aberta. Próximo: %s" % (rec.get("id") or "?", nxt))


def _blocked_stop(root, event, rec):
    from hdev import unit as unitmod
    others = unitmod.other_units(root, rec.get("id") or "")
    if not others:
        if not stopmod.read_parei(root):
            stopmod.write_wait(root, rec.get("blocked_on") or "dependência", rec.get("next") or "retomar")
        _lib.loop_guard_reset(root, "blocked_unit")
        return 0
    if _lib.loop_guard_exceeded(root, "blocked_unit", _session(event)):
        line = stopmod.write_exhausted(root, "blocked_unit", "pegue a próxima unidade do backlog")
        sys.stderr.write("blocked_unit: trava esgotada. %s\n" % (line or "").strip())
        return 0
    shown = ", ".join(others[:4])
    _lib.block("unidade %s bloqueada em %s. Próximo: pegue a próxima unidade do backlog (%s)" % (
        rec.get("id") or "?", rec.get("blocked_on") or "?", shown))


def _call(fn, event):
    try:
        return fn(event) or 0
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1


def main():
    event = _lib.read_event()
    root = _lib.project_root(event)
    permitted = _handoff_allows(root, event)
    for fn in (gate_main, progress_main, open_unit_main):
        code = _call(fn, event)
        if code:
            return code
    from harness.hooks.session import handoff_main
    code = handoff_main(event) or 0
    if permitted and not code:
        try:
            from hdev import handoff as handoffmod
            handoffmod.consume_stop(root)
        except Exception:
            pass
    return code


if __name__ == "__main__":
    sys.exit(main() or 0)
