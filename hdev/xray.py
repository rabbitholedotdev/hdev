"""hdev xray — o que uma sessão carrega antes da primeira palavra.

Estimativa determinística, não é o tokenizador do modelo: 1 token por 4 bytes
UTF-8, arredondando para cima. Fonte vazia vale 0. O campo `tokens` do eval não
usa este número.
"""
import json
import os
import re
import subprocess
import sys

from . import config as cfgmod

METHOD = "estimativa: 1 token por 4 bytes UTF-8, arredondando para cima"
ROLE_REL = os.path.join("harness", "prompts", "executor.md")
SHARED_RX = re.compile(r"harness/prompts/_shared/[\w.-]+\.md")
IMPORT_RX = re.compile(r"(?<![\w/])@([A-Za-z0-9_./-]+\.md)\b")


def estimate_tokens(text):
    """Tokens estimados de `text`. Vazio vale 0."""
    if not text:
        return 0
    return (len(text.encode("utf-8")) + 3) // 4


def cap_of(root):
    """`caps.context_initial`, ou o teto do código se o manifesto não trouxer."""
    cfg, _err = cfgmod.load(root)
    default = cfgmod.CAP_CEILING["context_initial"]
    caps = cfg.get("caps") if isinstance(cfg, dict) else None
    if not isinstance(caps, dict) or "context_initial" not in caps:
        return default
    try:
        return int(caps["context_initial"])
    except (TypeError, ValueError):
        return default


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeError):
        return ""


def _allowed(root, path):
    """O arquivo fica no repo ou na release ligada (`.harnessdev`)."""
    real = os.path.realpath(path)
    bases = [os.path.realpath(root)]
    link = os.path.join(root, ".harnessdev")
    if os.path.lexists(link):
        bases.append(os.path.realpath(link))
    return any(real == base or real.startswith(base + os.sep) for base in bases)


def _label(root, path):
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    if not rel.startswith("../"):
        return rel
    return os.path.realpath(path)


def claude_sources(root):
    """(rótulo, texto) de CLAUDE.md e dos @imports, sem repetir e sem sair do repo."""
    start = os.path.join(root, "CLAUDE.md")
    out = []
    seen = set()

    def add(path, label):
        if not os.path.isfile(path) or not _allowed(root, path):
            return
        real = os.path.realpath(path)
        if real in seen:
            return
        seen.add(real)
        text = _read(path)
        out.append((label, text))
        base = os.path.dirname(path)
        for match in IMPORT_RX.finditer(text):
            nxt = os.path.normpath(os.path.join(base, match.group(1)))
            add(nxt, _label(root, nxt))

    if os.path.isfile(start):
        add(start, "CLAUDE.md")
    return out


def visible_skill_names(root):
    """Skills da fase atual. Sem lista no manifesto, as que estão no disco."""
    cfg, _err = cfgmod.load(root)
    phase = str((cfg or {}).get("phase") or "")
    skills = (cfg or {}).get("skills") if isinstance(cfg, dict) else None
    if isinstance(skills, dict) and isinstance(skills.get(phase), list):
        return [n for n in skills[phase] if isinstance(n, str) and n]
    folder = os.path.join(root, ".claude", "skills")
    if not os.path.isdir(folder):
        return []
    names = []
    for name in sorted(os.listdir(folder)):
        if os.path.isfile(os.path.join(folder, name, "SKILL.md")):
            names.append(name)
    return names


def _front_description(text):
    from .check import skill_description
    return skill_description(text) or ""


def skill_sources(root):
    out = []
    for name in visible_skill_names(root):
        path = os.path.join(root, ".claude", "skills", name, "SKILL.md")
        desc = _front_description(_read(path)) if os.path.isfile(path) else ""
        out.append(("skill:%s" % name, name + "\n" + desc))
    return out


def agent_sources(root):
    folder = os.path.join(root, ".claude", "agents")
    if not os.path.isdir(folder):
        return []
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        desc = _front_description(_read(path))
        out.append(("agent:%s" % name[:-3], name[:-3] + "\n" + desc))
    return out


def _script(root):
    for rel in ("harness/hooks/session.py", os.path.join(".harnessdev", "harness", "hooks", "session.py")):
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            return path
    return None


def ritual_stdout(root):
    """Stdout do ritual, sem gravar estado quando o script honra `HDEV_XRAY`."""
    script = _script(root)
    if not script:
        return ""
    env = dict(os.environ)
    env["HDEV_XRAY"] = "1"
    env["CLAUDE_PROJECT_DIR"] = root
    env.pop("HDEV_NESTED", None)
    event = json.dumps({
        "hook_event_name": "UserPromptSubmit",
        "session_id": "hdev-xray",
        "cwd": root,
    })
    try:
        proc = subprocess.run([sys.executable, script], input=event, capture_output=True, text=True,
                              timeout=30, cwd=root, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout or ""


def _find(root, rel):
    for base in (root, os.path.join(root, ".harnessdev")):
        path = os.path.join(base, rel)
        if os.path.isfile(path) and _allowed(root, path):
            prefix = "" if os.path.realpath(base) == os.path.realpath(root) else ".harnessdev/"
            return path, prefix + rel.replace(os.sep, "/")
    return None, None


def prompt_sources(root):
    """O papel executor e os `_shared` que ele cita."""
    path, label = _find(root, ROLE_REL)
    if not path:
        return []
    text = _read(path)
    out = [("prompt:%s" % label, text)]
    seen = {os.path.realpath(path)}
    for rel in SHARED_RX.findall(text):
        shared, shared_label = _find(root, rel)
        if not shared:
            continue
        real = os.path.realpath(shared)
        if real in seen:
            continue
        seen.add(real)
        out.append(("prompt:%s" % shared_label, _read(shared)))
    return out


def _row(label, text):
    raw = text or ""
    return {"source": label, "tokens": estimate_tokens(raw), "bytes": len(raw.encode("utf-8"))}


def measure(root):
    """Relatório com `sources`, `total`, `method` e `estimate` true."""
    root = os.path.realpath(root)
    rows = []
    for label, text in claude_sources(root):
        rows.append(_row(label, text))
    for label, text in skill_sources(root):
        rows.append(_row(label, text))
    for label, text in agent_sources(root):
        rows.append(_row(label, text))
    rows.append(_row("ritual", ritual_stdout(root)))
    for label, text in prompt_sources(root):
        rows.append(_row(label, text))
    return {
        "estimate": True,
        "method": METHOD,
        "total": sum(row["tokens"] for row in rows),
        "sources": rows,
    }


def format_table(report):
    rows = report.get("sources") or []
    width = max([len("fonte"), len("total")] + [len(row["source"]) for row in rows])
    lines = ["%-*s  %s" % (width, "fonte", "estimativa")]
    for row in rows:
        lines.append("%-*s  %d" % (width, row["source"], row["tokens"]))
    lines.append("%-*s  %d" % (width, "total", report.get("total") or 0))
    lines.append(report.get("method") or METHOD)
    return "\n".join(lines)


def main(args):
    root = os.path.realpath(args.root)
    report = measure(root)
    limit = getattr(args, "max", None)
    if limit is not None:
        report = dict(report)
        report["max"] = limit
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_table(report))
    if limit is not None and report["total"] > limit:
        print("hdev xray: estimativa %d passa de %d" % (report["total"], limit))
        return 1
    return 0
