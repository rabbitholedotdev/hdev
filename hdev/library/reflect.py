"""`hdev reflect`: digest da unidade, generalização, dedup e gravação local."""
import datetime
import json
import os
import re

from hdev import config as cfgmod

from . import life
from . import store
from . import text as textmod

PREFIX = {
    "lesson": "lesson",
    "skill": "skill",
    "script": "script",
    "default": "default",
    "eval-case": "eval",
}
SCRIPT_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*\.(?:py|sh)$")
PROMPT = (
    "Lição candidata, já sem caminho e sem número.\n"
    "Pergunta: isto só vale para uma tarefa, ou serve para outras?\n"
    "JSON só: {\"verdict\":\"fail\"} se só vale para uma tarefa; "
    "{\"verdict\":\"pass\"} se generaliza.\n\n%s"
)


def _head(path, limit):
    try:
        with open(path, encoding="utf-8") as handle:
            rows = handle.read().splitlines()
    except OSError:
        return []
    return rows[:limit]


def _first_line(path):
    for line in _head(path, 20):
        if line.strip():
            return line.strip()
    return ""


def _judge_lines(root, unit):
    folder = os.path.join(root, ".hdev", "runs")
    if not os.path.isdir(folder):
        return []
    lines = []
    needle = "work/%s/" % unit
    for name in sorted(os.listdir(folder)):
        if not (name.startswith("judge-") and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        plan = str(data.get("plan") or "").replace("\\", "/")
        if data.get("unidade") != unit and needle not in plan:
            continue
        lines.append("juiz: %s" % data.get("verdict"))
    return lines


def _eval_lines(root, unit):
    folder = os.path.join(root, ".hdev", "runs")
    if not os.path.isdir(folder):
        return []
    lines = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("kind") != "eval":
            continue
        hay = " ".join(str(data.get(key) or "") for key in ("case", "unidade", "unit"))
        if unit not in hay:
            continue
        results = [row for row in data.get("results") or [] if isinstance(row, dict)]
        passed = sum(1 for row in results if row.get("pass") is True)
        lines.append("eval: %s pass=%d" % (data.get("case") or "?", passed))
    return lines


def _parei_lines(root, unit):
    found = []
    path = os.path.join(root, ".hdev", "state", "parei")
    if os.path.isfile(path):
        for line in _head(path, 20):
            if line.strip():
                found.append(line.strip())
    folder = os.path.join(root, "work", unit)
    if os.path.isdir(folder):
        for dirpath, _dirs, files in os.walk(folder):
            for name in sorted(files):
                if not name.endswith((".md", ".txt")):
                    continue
                for line in _head(os.path.join(dirpath, name), 400):
                    if line.strip().upper().startswith("PAREI:"):
                        found.append(line.strip())
    return found


def digest(root, unit):
    folder = os.path.join(root, "work", unit)
    if not os.path.isdir(folder):
        return None
    lines = ["unidade: %s" % unit]
    plan = os.path.join(folder, "plan.md")
    if os.path.isfile(plan):
        lines.append("plano: work/%s/plan.md" % unit)
        lines.extend(_head(plan, 40))
    decisions = os.path.join(folder, "decisions.md")
    if os.path.isfile(decisions):
        lines.append("decisões:")
        lines.extend(_head(decisions, 20))
    evidence = os.path.join(folder, "evidence")
    if os.path.isdir(evidence):
        lines.append("evidência:")
        for name in sorted(os.listdir(evidence)):
            if name.endswith(".md"):
                lines.append("- %s: %s" % (name, _first_line(os.path.join(evidence, name))[:120]))
    unit_path = os.path.join(root, ".hdev", "state", "unit.json")
    if os.path.isfile(unit_path):
        try:
            with open(unit_path, encoding="utf-8") as handle:
                data = json.load(handle)
            status = data.get("status") if isinstance(data, dict) and data.get("id") in (None, "", unit) else "ausente"
        except (OSError, ValueError):
            status = "ilegível"
        lines.append("unidade-status: %s" % status)
    lines.append("paradas:")
    stopped = _parei_lines(root, unit)
    lines.extend(stopped or ["(nenhuma)"])
    lines.append("juiz:")
    lines.extend(_judge_lines(root, unit) or ["(nenhum)"])
    lines.append("eval:")
    lines.extend(_eval_lines(root, unit) or ["(nenhum)"])
    return "\n".join(lines) + "\n"


def ask(root, body):
    """'drop' se o segundo modelo diz que é só desta tarefa, 'ok' se generaliza, None sem provedor."""
    from hdev.gates.judge.run import _judge_one
    cfg, err = cfgmod.load(root)
    if err or not isinstance(cfg, dict):
        return None
    roles = cfg.get("roles") or {}
    if not isinstance(roles.get("judge"), dict) and not isinstance(roles.get("judge_fallback"), dict):
        return None
    _attempts, final = _judge_one(cfg, PROMPT % body, root)
    if not final:
        return None
    if final.get("verdict") == "fail":
        return "drop"
    if final.get("verdict") == "pass":
        return "ok"
    return None


def _next_id(items, kind):
    prefix = PREFIX[kind]
    pattern = re.compile(r"^%s-(\d+)$" % prefix)
    nums = []
    for item in items:
        match = pattern.match(item.get("id") or "")
        if match:
            nums.append(int(match.group(1)))
    return "%s-%04d" % (prefix, (max(nums) if nums else 0) + 1)


def _body_rel(kind, iid, name=None):
    folder = store.KIND_DIR[kind]
    if kind == "script":
        return "%s/%s" % (folder, name)
    return "%s/%s.md" % (folder, iid.split("-", 1)[1])


def _local_copy(root, item):
    rel = item["body_path"]
    target = os.path.join(root, rel)
    if not os.path.isfile(target):
        store.write_body(root, rel, store.read_body(item))
    copied = dict(item)
    copied["_root"] = root
    return copied


def _append_evidence(item, evidence):
    have = item.setdefault("evidence", [])
    for ev in evidence or []:
        if isinstance(ev, dict) and ev not in have:
            have.append(ev)


def _similar(text, items):
    best, best_score = None, 0.0
    for item in items:
        try:
            body = store.read_body(item)
        except OSError:
            continue
        score = textmod.similarity(text, textmod.blob(item.get("title"), item.get("when_to_use"), body))
        if score > best_score:
            best, best_score = item, score
    if best is not None and best_score >= textmod.DEDUP_SIM:
        return best
    return None


def _prepare(raw, unit):
    if not isinstance(raw, dict):
        return None, "item inválido"
    kind = raw.get("kind") or "lesson"
    if kind not in store.KINDS:
        return None, "kind inválido"
    title = textmod.strip_specifics(raw.get("title") or "", unit)
    when = textmod.strip_specifics(raw.get("when_to_use") or "", unit)
    not_for = textmod.strip_specifics(raw.get("not_for") or "", unit)
    body = textmod.strip_specifics(raw.get("body") or "", unit)
    tags = []
    for tag in raw.get("tags") or []:
        if not isinstance(tag, str):
            continue
        cleaned = textmod.strip_specifics(tag, unit).strip().lower()
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
    if not title or not when or not body:
        return None, "texto vazio depois do corte"
    if kind == "lesson" and not textmod.lesson_shape_ok(body):
        return None, "lição fora da forma ou com mais de %d linhas" % textmod.LESSON_LINES
    scope = raw.get("scope") or "global"
    if not isinstance(scope, str) or not store.SCOPE_RX.match(scope):
        return None, "scope inválido"
    source = raw.get("source") or "reflect"
    if source not in store.SOURCES:
        return None, "source inválido"
    evidence = raw.get("evidence") or []
    if not isinstance(evidence, list):
        return None, "evidence inválida"
    name = raw.get("name")
    if kind == "script":
        if not isinstance(name, str) or not SCRIPT_NAME.match(name):
            return None, "script pede name em inglês com .py ou .sh"
    prepared = {
        "kind": kind, "title": title, "when_to_use": when, "not_for": not_for, "body": body,
        "tags": tags, "scope": scope, "source": source, "evidence": [ev for ev in evidence if isinstance(ev, dict)],
        "name": name, "test": raw.get("test"),
    }
    return prepared, None


def add_items(root, unit, payload, offline=False, today=None):
    today = life.as_date(today or datetime.date.today())
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return [{"action": "recusado", "id": None, "reason": "JSON precisa ser lista ou objeto"}]
    results = []
    for raw in payload:
        prepared, reason = _prepare(raw, unit)
        if prepared is None:
            results.append({"action": "recusado", "id": None, "reason": reason})
            continue
        results.append(_store_one(root, prepared, offline, today))
    return results


def _store_one(root, prepared, offline, today):
    local = store.load_local(root)
    visible = store.load_for_pull(root)
    text = textmod.blob(prepared["title"], prepared["when_to_use"], prepared["body"])
    match = _similar(text, visible)
    if match is not None:
        if os.path.realpath(match.get("_root") or "") != os.path.realpath(root):
            match = _local_copy(root, match)
            local = [item for item in local if item["id"] != match["id"]]
            local.append(match)
        else:
            match = next(item for item in local if item["id"] == match["id"])
        _append_evidence(match, prepared["evidence"])
        store.save_local(root, local)
        return {"action": "juntado", "id": match["id"], "reason": "semelhança"}
    if prepared["kind"] == "script":
        rel = _body_rel("script", "script-0000", prepared["name"])
        probe = {"body_path": rel, "test": prepared.get("test")}
        if not store.script_tested(root, probe):
            return {"action": "recusado", "id": None, "reason": "script sem teste"}
    generalization = "pending"
    if not offline:
        answer = ask(root, prepared["body"])
        if answer == "drop":
            return {"action": "descartado", "id": None, "reason": "só desta tarefa"}
        if answer == "ok":
            generalization = "checked"
    iid = _next_id(local, prepared["kind"])
    rel = _body_rel(prepared["kind"], iid, prepared.get("name"))
    item = {
        "id": iid,
        "kind": prepared["kind"],
        "title": prepared["title"],
        "when_to_use": prepared["when_to_use"],
        "not_for": prepared["not_for"],
        "body_path": rel,
        "scope": prepared["scope"],
        "tags": prepared["tags"],
        "evidence": prepared["evidence"],
        "wins": 0,
        "losses": 0,
        "uses": 0,
        "created": today.isoformat(),
        "last_used": None,
        "status": "candidate",
        "source": prepared["source"],
        "generalization": generalization,
    }
    if prepared.get("test"):
        item["test"] = prepared["test"]
    store.write_body(root, rel, prepared["body"])
    local.append(item)
    store.save_local(root, local)
    return {"action": "gravado", "id": iid, "reason": generalization}


def format_add(results):
    lines = []
    for row in results:
        if row["action"] == "gravado":
            lines.append("gravado: %s candidata %s" % (row["id"], row["reason"]))
        elif row["action"] == "juntado":
            lines.append("juntado: %s" % row["id"])
        elif row["action"] == "descartado":
            lines.append("descartado: %s" % row["reason"])
        else:
            lines.append("recusado: %s" % row["reason"])
    return "\n".join(lines) + ("\n" if lines else "")
