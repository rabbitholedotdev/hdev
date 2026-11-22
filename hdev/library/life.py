"""Pontos, vitória no fechar e o ciclo idempotente do `hdev library tidy`."""
import datetime
import json
import os

from hdev import stop as stopmod

from . import store

RETIRE_SCORE = 0.4
RETIRE_USES = 4
UNUSED_DAYS = 90
DELETE_DAYS = 180
CORE_WINS = 5
CORE_RATE = 0.7


def as_date(value):
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(value)


def days_idle(item, today):
    raw = item.get("last_used") or item.get("created")
    if not raw:
        return 0
    return max(0, (today - as_date(raw)).days)


def score(item, today):
    """(wins + 1) / (wins + losses + 2) × 0.5 ^ (dias sem uso / 60)."""
    wins = int(item.get("wins") or 0)
    losses = int(item.get("losses") or 0)
    base = (wins + 1.0) / (wins + losses + 2.0)
    return base * (0.5 ** (days_idle(item, today) / 60.0))


def win_rate(item):
    total = int(item.get("wins") or 0) + int(item.get("losses") or 0)
    if total <= 0:
        return 0.0
    return int(item.get("wins") or 0) / float(total)


def core_eligible(item):
    return (item.get("status") == "active" and int(item.get("wins") or 0) >= CORE_WINS
            and win_rate(item) >= CORE_RATE)


def _win_units(item):
    found = set()
    for ev in item.get("evidence") or []:
        if not isinstance(ev, dict) or not ev.get("unit"):
            continue
        delta = ev.get("delta") if isinstance(ev.get("delta"), dict) else {}
        if delta.get("pass") == 1 or ev.get("result") == "win":
            found.add(ev["unit"])
    return found


def has_probe(item):
    for ev in item.get("evidence") or []:
        if not isinstance(ev, dict):
            continue
        if ev.get("probe") is True:
            return True
        run = str(ev.get("run") or "")
        if run == "probe" or run.startswith("probe:") or run.startswith("probe-"):
            return True
    return False


def promotes(item):
    if item.get("status") != "candidate" or item.get("generalization") != "checked":
        return False
    if has_probe(item):
        return True
    return len(_win_units(item)) >= 2


def should_retire(item, today):
    if item.get("status") != "active":
        return False
    if int(item.get("uses") or 0) >= RETIRE_USES and score(item, today) < RETIRE_SCORE:
        return True
    return days_idle(item, today) >= UNUSED_DAYS


def _retire(item, today):
    item["status"] = "retired"
    if not item.get("retired_on"):
        item["retired_on"] = today.isoformat()


def tidy_items(items, today):
    """Devolve (itens, caminhos de corpo apagados). Não grava."""
    items = [dict(item) for item in items]
    for item in items:
        if item.get("status") == "retired" and not item.get("retired_on"):
            item["retired_on"] = today.isoformat()
        elif promotes(item):
            item["status"] = "active"
        elif should_retire(item, today):
            _retire(item, today)
    active = [item for item in items if item.get("status") == "active"]
    extra = len(active) - store.ACTIVE_CAP
    if extra > 0:
        worst = sorted(active, key=lambda item: (score(item, today), item.get("id") or ""))
        for item in worst[:extra]:
            _retire(item, today)
    kept = []
    removed = []
    for item in items:
        retired_on = item.get("retired_on")
        if item.get("status") == "retired" and retired_on:
            if (today - as_date(retired_on)).days >= DELETE_DAYS:
                removed.append(item.get("body_path"))
                continue
        kept.append(item)
    return kept, removed


def tidy_root(root, today=None):
    today = as_date(today or datetime.date.today())
    path = store.index_path(root)
    if not os.path.isfile(path):
        return {"promoted": 0, "retired": 0, "deleted": 0}
    before = {item["id"]: item.get("status") for item in store.load_local(root)}
    items = store.load_local(root)
    kept, removed = tidy_items(items, today)
    store.save_local(root, kept)
    for rel in removed:
        if not rel:
            continue
        if any(item.get("body_path") == rel for item in kept):
            continue
        target = os.path.join(root, rel)
        if os.path.isfile(target):
            os.remove(target)
    after = {item["id"]: item.get("status") for item in kept}
    promoted = sum(1 for iid, status in after.items() if before.get(iid) == "candidate" and status == "active")
    retired = sum(1 for iid, status in after.items() if before.get(iid) == "active" and status == "retired")
    deleted = sum(1 for iid in before if iid not in after)
    return {"promoted": promoted, "retired": retired, "deleted": deleted}


def format_tidy(result):
    return "tidy: promovidas %d, aposentadas %d, apagadas %d\n" % (
        result["promoted"], result["retired"], result["deleted"])


def format_status(root, today=None):
    today = as_date(today or datetime.date.today())
    items = store.load_local(root)
    counts = {name: 0 for name in store.STATUSES}
    for item in items:
        counts[item.get("status")] = counts.get(item.get("status"), 0) + 1
    lines = ["biblioteca: %d itens, %d ativas, %d core, %d candidatas, %d aposentadas" % (
        len(items), counts.get("active", 0), counts.get("core", 0),
        counts.get("candidate", 0), counts.get("retired", 0))]
    eligible = [item for item in items if core_eligible(item)]
    eligible.sort(key=lambda item: item["id"])
    if not eligible:
        lines.append("elegível pra core: nenhuma")
    else:
        lines.append("elegível pra core:")
        for item in eligible:
            lines.append("%s  %d vitórias  taxa %.2f" % (item["id"], item["wins"], win_rate(item)))
    return "\n".join(lines) + "\n"


def _parei_outside(text):
    for line in (text or "").splitlines():
        stripped = line.strip()
        match = stopmod.PAREI_LINE.match(stripped)
        if match:
            if stopmod.classify(match.group("motivo")) is None:
                return True
            continue
        if stripped.upper().startswith("PAREI:"):
            return True
    return False


def unexpected_stop(root, unit):
    """Parada cuja motivo não está na lista fechada. Lista fechada não conta."""
    chunks = []
    parei = stopmod.parei_path(root)
    if os.path.isfile(parei):
        try:
            with open(parei, encoding="utf-8") as handle:
                chunks.append(handle.read())
        except OSError:
            pass
    folder = os.path.join(root, "work", unit)
    if os.path.isdir(folder):
        for dirpath, _dirs, files in os.walk(folder):
            for name in files:
                if not name.endswith((".md", ".txt")):
                    continue
                try:
                    with open(os.path.join(dirpath, name), encoding="utf-8") as handle:
                        chunks.append(handle.read())
                except OSError:
                    continue
    return any(_parei_outside(chunk) for chunk in chunks)


def first_judge_passed(root, plan_rel):
    """O primeiro veredito pass/fail/unsure deste plano. Sem registro, não passou."""
    folder = os.path.join(root, ".hdev", "runs")
    if not os.path.isdir(folder):
        return False
    names = sorted(name for name in os.listdir(folder) if name.startswith("judge-") and name.endswith(".json"))
    for name in names:
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("plan") != plan_rel:
            continue
        verdict = data.get("verdict")
        if verdict in ("pass", "fail", "unsure"):
            return verdict == "pass"
    return False


def attribute(root, unit, plan_rel, today=None):
    """Marca vitória ou derrota nos ids de work/<id>/pulled.json. A segunda vez não muda."""
    today = as_date(today or datetime.date.today())
    path = os.path.join(root, "work", unit, "pulled.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("scored"):
        return False
    ids = [item for item in data.get("ids") or [] if isinstance(item, str)]
    win = first_judge_passed(root, plan_rel) and not unexpected_stop(root, unit)
    items = store.load_local(root)
    by_id = {item["id"]: item for item in items}
    changed = False
    for iid in ids:
        item = by_id.get(iid)
        if item is None:
            continue
        item["uses"] = int(item.get("uses") or 0) + 1
        item["last_used"] = today.isoformat()
        if win:
            item["wins"] = int(item.get("wins") or 0) + 1
        else:
            item["losses"] = int(item.get("losses") or 0) + 1
        evidence = {"unit": unit, "run": "fechar", "delta": {"pass": 1 if win else 0}}
        have = item.setdefault("evidence", [])
        if evidence not in have:
            have.append(evidence)
        changed = True
    if changed:
        store.save_local(root, items)
    data["scored"] = True
    data["win"] = win
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
    os.replace(tmp, path)
    return win
