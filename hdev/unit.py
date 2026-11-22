"""Estado da unidade aberta. Um arquivo: `.hdev/state/unit.json`.

`hdev base --marcar` abre. `hdev fechar` pass fecha. `hdev resume --blocked-on`
bloqueia. PAREI da lista (ou gate esgotado) estaciona: a sessão pode acabar e a
unidade continua aberta. `stop.standing_ok` no manifesto tira o item da parada
e deixa `ready-to-publish`. Sem unidade marcada, o Stop segue como antes.
"""
import json
import os
import re

REL = os.path.join(".hdev", "state", "unit.json")
OPEN = "open"
BLOCKED = "blocked"
READY = "ready-to-publish"
CLOSED = "closed"
STATUSES = (OPEN, BLOCKED, READY, CLOSED)
_CLOSED_LINE = re.compile(r"\|\s*feito\s*\||\[x\]|feito e fechado", re.I)
_WORK = re.compile(r"work/([^/\s]+)/")
_ID = re.compile(r"\b([A-Za-z][A-Za-z0-9]*-\d+)\b")
_BACKLOGS = ("work/backlog.md", "docs/backlog.md")


def path(root):
    return os.path.join(root, REL)


def load(root):
    try:
        with open(path(root), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _norm(rec):
    rec = rec or {}
    status = rec.get("status") if rec.get("status") in STATUSES else OPEN
    return {
        "id": rec.get("id") or "",
        "status": status,
        "next": rec.get("next") or "",
        "blocked_on": rec.get("blocked_on") or "",
        "plan": rec.get("plan") or "",
        "brief": rec.get("brief") or "",
        "parked": bool(rec.get("parked")),
    }


def save(root, rec):
    rec = _norm(rec)
    dest = path(root)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = "%s.tmp-%d" % (dest, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, dest)
    return rec


def brief_for(plan_rel):
    norm = (plan_rel or "").replace("\\", "/")
    if norm.endswith("/plan.md"):
        return norm[:-len("plan.md")] + "brief.md"
    return ""


def next_from_plan(text):
    """Primeiro passo numerado da seção Passos, ou vazio."""
    in_steps = False
    for line in (text or "").splitlines():
        if line.startswith("##"):
            in_steps = line.lower().startswith("## passos")
            continue
        if not in_steps:
            continue
        found = re.match(r"\s*\d+\.\s+(\S.*)", line)
        if found:
            step = " ".join(found.group(1).split())
            return step[:200]
    return ""


def next_of(root, rec):
    rec = rec or {}
    nxt = " ".join((rec.get("next") or "").split())
    if nxt:
        return nxt
    plan = rec.get("plan") or ""
    if plan:
        try:
            with open(os.path.join(root, plan), encoding="utf-8") as f:
                found = next_from_plan(f.read())
        except OSError:
            found = ""
        if found:
            return found
    return "seguir o plano"


def open_unit(root, uid, plan_rel, nxt):
    """Abre (ou troca) a unidade corrente. Uma só por vez."""
    return save(root, {
        "id": uid or "",
        "status": OPEN,
        "next": " ".join((nxt or "").split()) or "seguir o plano",
        "blocked_on": "",
        "plan": plan_rel or "",
        "brief": brief_for(plan_rel),
        "parked": False,
    })


def close_unit(root, uid):
    """Fecha a unidade corrente se for esta (ou se ainda não havia arquivo)."""
    rec = load(root)
    if rec and rec.get("id") and uid and rec.get("id") != uid:
        return rec
    base = rec or {}
    base["id"] = (rec or {}).get("id") or uid or ""
    base["status"] = CLOSED
    base["parked"] = False
    base["blocked_on"] = ""
    return save(root, base)


def mark_blocked(root, dependency, nxt):
    rec = load(root) or {}
    rec["status"] = BLOCKED
    rec["blocked_on"] = " ".join((dependency or "").split())
    if nxt:
        rec["next"] = " ".join(str(nxt).split())
    rec["parked"] = False
    return save(root, rec)


def mark_ready(root):
    rec = load(root) or {}
    rec["status"] = READY
    rec["parked"] = False
    rec["blocked_on"] = ""
    return save(root, rec)


def park(root):
    rec = load(root)
    if not rec:
        return None
    rec["parked"] = True
    return save(root, rec)


def lift(root, motivo):
    """Consome o PAREI: tira o estacionamento. Espera bloqueada volta a aberta."""
    rec = load(root)
    if not rec:
        return None
    rec["parked"] = False
    if (motivo or "").lower().startswith("espera") and rec.get("status") == BLOCKED:
        rec["status"] = OPEN
        rec["blocked_on"] = ""
    return save(root, rec)


def _line_ids(line):
    found = _WORK.search(line)
    if found:
        return [found.group(1)]
    found = _ID.search(line)
    return [found.group(1)] if found else []


def other_units(root, current_id):
    """Outras unidades abertas no backlog. Sem arquivo, nenhuma."""
    current = (current_id or "").lower()
    found = []
    for rel in _BACKLOGS:
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        for line in text.splitlines():
            raw = line.strip()
            if not raw or raw.startswith("#") or _CLOSED_LINE.search(raw):
                continue
            if not raw.startswith(("-", "*", "|")) or raw.startswith("| ---"):
                continue
            if set(raw) <= set("|-: "):
                continue
            for uid in _line_ids(raw):
                if uid.lower() != current and uid not in found:
                    found.append(uid)
    return found
