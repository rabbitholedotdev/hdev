#!/usr/bin/env python3
"""UserPromptSubmit e PostToolUse: ritual de início, handoff e corte de saída longa.

O Stop do handoff mora em `stop_gate.py` (o terceiro registro antigo não cabe nos dois daqui).
`hooks/handoff_guard.py` delega para `handoff_main`, com o mesmo stdin e a mesma saída.
`HDEV_XRAY=1` imprime o ritual e sai, sem gravar estado (`hdev xray` mede essa stdout).
"""
import json
import os
import re
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "hooks")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _lib  # noqa: E402
from hdev import handoff as h  # noqa: E402

HEAD_LINES = 30
TAIL_LINES = 20
MAX_CHARS = 4000
ERROR_LINE = re.compile(r"(?i)(\berror\b|\btraceback\b|\bexception\b|\bfatal\b|\bfailed\b|^FAIL:)")
_FAIL_KEYS = ("exit_code", "exitCode", "returncode", "code")


def _session_id(event):
    return event.get("session_id") or event.get("sessionId") or ""


def _event_name(event):
    return event.get("hook_event_name") or event.get("hookEventName") or ""


def response_failed(response):
    """True quando o PostToolUse traz falha explícita. Texto sem marca não conta."""
    if isinstance(response, dict):
        if response.get("is_error") is True or response.get("isError") is True:
            return True
        for key in _FAIL_KEYS:
            if key not in response:
                continue
            value = response[key]
            if value in (0, "0", None, False):
                return False
            try:
                return int(value) != 0
            except (TypeError, ValueError):
                return True
        return False
    if isinstance(response, str):
        return bool(re.search(r"(?m)^exit_code=[1-9]\d*\s*$", response))
    return False


def response_text(response):
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        parts = []
        for key in ("stdout", "stderr", "output", "content"):
            value = response.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
        if parts:
            return "\n".join(parts)
        try:
            return json.dumps(response, ensure_ascii=False)
        except TypeError:
            return str(response)
    if response is None:
        return ""
    return str(response)


def cut_text(text):
    """(curto, True) se passou do teto. Cabeça, linhas de erro e cauda. None se cabe."""
    if text is None:
        return None
    lines = text.splitlines()
    if len(text) <= MAX_CHARS and len(lines) <= HEAD_LINES + TAIL_LINES:
        return None
    head_n = min(HEAD_LINES, len(lines))
    tail_n = min(TAIL_LINES, len(lines))
    tail_from = max(head_n, len(lines) - tail_n)
    covered = set(range(head_n)) | set(range(tail_from, len(lines)))
    errors = []
    for i, line in enumerate(lines):
        if i in covered:
            continue
        if ERROR_LINE.search(line):
            errors.append(line)
            if len(errors) >= 40:
                break
    parts = list(lines[:head_n])
    if errors:
        parts.append("... linhas de erro ...")
        parts.extend(errors)
    if tail_from < len(lines):
        parts.append("... cauda ...")
        parts.extend(lines[tail_from:])
    return "\n".join(parts) + ("\n" if text.endswith("\n") or parts else "")


def _unit(root):
    env = os.environ.get("HDEV_UNIT")
    if env:
        return env
    branch = _lib.git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch:
        return branch.strip()
    return ""


def _edit_paths(event):
    if event.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return []
    inp = event.get("tool_input") or {}
    if not isinstance(inp, dict):
        return []
    paths = []
    for key in ("file_path", "path"):
        if isinstance(inp.get(key), str) and inp.get(key).strip():
            paths.append(inp[key])
    return paths


def record_post(event, root):
    """Anota falha de Bash e toque em arquivo, para o pre_tool da próxima chamada."""
    if response_failed(event.get("tool_response")) and event.get("tool_name") == "Bash":
        command = (event.get("tool_input") or {}).get("command", "")
        if isinstance(command, str):
            _lib.record_command_result(root, _session_id(event), command, True)
    elif event.get("tool_name") == "Bash":
        command = (event.get("tool_input") or {}).get("command", "")
        if isinstance(command, str) and command.strip() and _saw_exit(event.get("tool_response")):
            _lib.record_command_result(root, _session_id(event), command, False)
    paths = _edit_paths(event)
    if paths and not response_failed(event.get("tool_response")):
        _lib.record_touch(root, _session_id(event), paths, _unit(root))


def _saw_exit(response):
    """Há um código de saída e ele é zero. Sem código, não zera a contagem."""
    if isinstance(response, dict):
        for key in _FAIL_KEYS:
            if key in response and response[key] in (0, "0"):
                return True
    if isinstance(response, str) and re.search(r"(?m)^exit_code=0\s*$", response):
        return True
    return False


def _write_full(root, session, text):
    folder = os.path.join(root, ".hdev", "state", "tool-output")
    os.makedirs(folder, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session or "s")[:40]
    name = "%s-%d.log" % (safe, time.time_ns())
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return os.path.relpath(path, root)


def maybe_cut(event, root):
    """Texto de `updatedToolOutput`, ou None se a saída cabe."""
    raw = response_text(event.get("tool_response"))
    if not raw:
        return None
    redacted = _lib.redact(raw)
    short = cut_text(redacted)
    if short is None:
        return None
    try:
        rel = _write_full(root, _session_id(event), redacted if redacted.endswith("\n") else redacted + "\n")
    except OSError:
        return None
    return "[corte] saída completa: %s\n%s" % (rel, short if short.endswith("\n") else short + "\n")


def _last_decision(root):
    path = os.path.join(root, "docs", "decisions.md")
    try:
        with open(path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    except OSError:
        return "—"
    if not lines:
        return "—"
    line = lines[-1]
    return line if len(line) <= 160 else line[:159].rstrip() + "…"


def _open_spec(root):
    found = []
    work = os.path.join(root, "work")
    if os.path.isdir(work):
        for name in sorted(os.listdir(work)):
            if os.path.isfile(os.path.join(work, name, "spec.md")):
                found.append("work/%s/spec.md" % name)
    docs = os.path.join(root, "docs", "specs")
    if os.path.isdir(docs):
        for name in sorted(os.listdir(docs)):
            if name.endswith(".md") and not name.endswith(".review.md"):
                found.append("docs/specs/" + name)
    if not found:
        return "—"
    if len(found) == 1:
        return found[0]
    return "%s (+%d)" % (found[0], len(found) - 1)


def _estado(root, event=None):
    """Plano, brief, permissões, estado e modelo. Não grava nada."""
    try:
        from hdev import unit as unitmod
        rec = unitmod.load(root) or {}
        perms = h._permissions(root)
        model = h.current_model(root, event=event) or "—"
        if not rec:
            return "estado: —; plano: —; brief: —; próximo: —; permissões: %s; modelo: %s" % (perms, model)
        return "estado: %s; plano: %s; brief: %s; próximo: %s; permissões: %s; modelo: %s" % (
            rec.get("status") or "—", rec.get("plan") or "—", rec.get("brief") or "—",
            rec.get("next") or "—", perms, model)
    except Exception:
        return "estado: —"


def ritual_text(root, event=None):
    progress = os.path.join(root, "docs", "progress.md")
    try:
        with open(progress, encoding="utf-8") as f:
            size = len(f.read())
        prog = "progress: %d caracteres" % size
    except OSError:
        prog = "progress: ausente"
    log = _lib.git(root, "log", "-5", "--oneline")
    git_bit = " | ".join(log.splitlines()) if log else "—"
    unit = _unit(root) or "—"
    return "ritual de início — %s; decisão: %s; git: %s; spec: %s; unidade: %s; %s" % (
        prog, _last_decision(root), git_bit, _open_spec(root), unit, _estado(root, event))


def _ritual_path(root):
    return os.path.join(root, ".hdev", "state", "ritual.json")


def maybe_ritual(event, root):
    """Texto do ritual na primeira vez desta sessão. UserPromptSubmit ou SessionStart."""
    if _event_name(event) not in ("UserPromptSubmit", "SessionStart"):
        return None
    session = _session_id(event)
    path = _ritual_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    seen = state.get("sessions") if isinstance(state, dict) else None
    if not isinstance(seen, list):
        seen = []
    if session and session in seen:
        return None
    text = ritual_text(root, event)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"sessions": (seen + [session])[-20:]}, f)
    except OSError:
        pass
    return text


def _handoff_out(event, root):
    try:
        cfg = h.settings(root)
        out, _st = h.hook_decide(root, event, cfg)
    except Exception:
        return None
    try:
        _lib.record_metric(root, {
            "hook": "handoff_guard",
            "event": _event_name(event),
            "ratio": None if not isinstance(_st, dict) else _st.get("usage_ratio"),
            "nudged": bool(out),
        })
    except Exception:
        pass
    return out


def handoff_main(event=None):
    """Comportamento antigo do handoff_guard: só o handoff, nos três eventos."""
    if _lib.nested():
        return 0
    if event is None:
        event = _lib.read_event()
    out = _handoff_out(event, _lib.project_root(event))
    if out:
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    return 0


def _merge(name, handoff_out, cut, ritual):
    if cut is None and not ritual:
        return handoff_out
    spec = {"hookEventName": name or "PostToolUse"}
    if cut:
        spec["updatedToolOutput"] = cut
    extra = []
    if isinstance(handoff_out, dict):
        ctx = (handoff_out.get("hookSpecificOutput") or {}).get("additionalContext")
        if ctx:
            extra.append(ctx)
        elif handoff_out.get("reason"):
            extra.append(handoff_out["reason"])
    if ritual:
        extra.append(ritual)
    if extra:
        spec["additionalContext"] = "\n".join(extra)
    out = {"hookSpecificOutput": spec}
    if isinstance(handoff_out, dict) and handoff_out.get("decision"):
        out["decision"] = handoff_out["decision"]
        if handoff_out.get("reason"):
            out["reason"] = handoff_out["reason"]
    return out


def main():
    if os.environ.get("HDEV_XRAY") == "1":
        root = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        text = ritual_text(root)
        sys.stdout.write(text if text.endswith("\n") else text + "\n")
        return 0
    if _lib.nested():
        return 0
    event = _lib.read_event()
    name = _event_name(event)
    root = _lib.project_root(event)
    if name == "PostToolUse":
        record_post(event, root)
        cut = maybe_cut(event, root)
    else:
        cut = None
    if name == "UserPromptSubmit":
        try:
            _lib.record_chip(root, _session_id(event), event.get("prompt"))
        except Exception:
            pass  # a etiqueta nunca derruba o prompt

    ritual = maybe_ritual(event, root)
    merged = _merge(name, _handoff_out(event, root), cut, ritual)
    if merged:
        sys.stdout.write(json.dumps(merged, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
