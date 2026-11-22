"""`hdev library pull`: BM25, escopo, not_for, orçamento e vagas de candidata."""
import json
import os

from hdev import config as cfgmod
from hdev import xray

from . import store
from . import text as textmod

K_DEFAULT = 5
BUDGET_DEFAULT = 1500
CANDIDATE_SLOTS = 2
SKILL_CAP = 2


def repo_name(root):
    cfg, _err = cfgmod.load(root)
    if isinstance(cfg, dict):
        name = cfg.get("repo")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return os.path.basename(os.path.realpath(root))


def area_name(root):
    cfg, _err = cfgmod.load(root)
    if isinstance(cfg, dict):
        name = cfg.get("area")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def scope_ok(item, repo, area):
    scope = item.get("scope")
    if scope == "global":
        return True
    if repo and scope == "repo:%s" % repo:
        return True
    if area and scope == "area:%s" % area:
        return True
    return False


def recurring(item):
    if int(item.get("losses") or 0) >= 1 or int(item.get("uses") or 0) >= 2:
        return True
    return "bloqueio" in (item.get("tags") or [])


def _doc(item):
    tags = " ".join(item.get("tags") or [])
    return "%s\n%s\n%s" % (item.get("title") or "", item.get("when_to_use") or "", tags)


def _unit_from_spec(spec):
    norm = (spec or "").replace("\\", "/")
    marker = "/work/"
    if norm.startswith("work/"):
        norm = "/" + norm
    if marker not in norm:
        return None
    rest = norm.split(marker, 1)[1]
    name = rest.split("/", 1)[0]
    if name in ("", ".", ".."):
        return None
    return name


def resolve_spec(root, spec):
    if not spec:
        return None
    if os.path.isabs(spec) and os.path.isfile(spec):
        return spec
    in_root = os.path.join(root, spec)
    if os.path.isfile(in_root):
        return in_root
    if os.path.isfile(spec):
        return spec
    return None


def rank(items, query, symptom=False, tag=None, repo=None, area=None):
    """Pares (item, score) com score > 0, já filtrados e ordenados."""
    pool = []
    for item in items:
        if item.get("status") == "retired":
            continue
        if not scope_ok(item, repo, area):
            continue
        if tag and tag not in (item.get("tags") or []):
            continue
        if textmod.blocked_by_not_for(item.get("not_for") or "", query):
            continue
        pool.append(item)
    if not pool:
        return []
    scores = textmod.bm25_scores(query, [_doc(item) for item in pool])
    ranked = [(item, score) for item, score in zip(pool, scores) if score > 0]
    if symptom:
        ranked.sort(key=lambda pair: (0 if recurring(pair[0]) else 1, -pair[1], pair[0]["id"]))
    else:
        ranked.sort(key=lambda pair: (-pair[1], pair[0]["id"]))
        promoted = [pair for pair in ranked if pair[0].get("status") in ("active", "core")]
        cands = [pair for pair in ranked if pair[0].get("status") == "candidate"]
        ranked = promoted + cands
    return ranked


def select(items, query, k=K_DEFAULT, budget=BUDGET_DEFAULT, symptom=False, tag=None, repo=None, area=None):
    """Itens puxados, na ordem. Cada um traz score, tokens e body."""
    if k < 1:
        return []
    return _fill(rank(items, query, symptom, tag, repo, area), k, budget)


def _fill(ranked, k, budget):
    picked = []
    lesson_tokens = 0
    skills = 0
    cand_n = 0
    for item, score in ranked:
        if len(picked) >= k:
            break
        is_cand = item.get("status") == "candidate"
        if is_cand and cand_n >= CANDIDATE_SLOTS:
            continue
        try:
            body = store.read_body(item)
        except OSError:
            continue
        tokens = xray.estimate_tokens(body)
        if item.get("kind") == "skill":
            if skills >= SKILL_CAP:
                continue
        elif lesson_tokens + tokens > budget:
            continue
        picked.append({
            "id": item["id"],
            "score": round(score, 4),
            "tokens": tokens,
            "status": item.get("status"),
            "kind": item.get("kind"),
            "body": body,
        })
        if item.get("kind") == "skill":
            skills += 1
        else:
            lesson_tokens += tokens
        if is_cand:
            cand_n += 1
    return picked


def lesson_tokens(picked):
    return sum(row["tokens"] for row in picked if row.get("kind") != "skill")


def pull(root, query, spec_rel="", symptom="", unit=None, k=K_DEFAULT, budget=BUDGET_DEFAULT, tag=None):
    repo, area = repo_name(root), area_name(root)
    items = store.load_for_pull(root)
    ranked = rank(items, query, symptom=bool(symptom), tag=tag, repo=repo, area=area)
    picked = _fill(ranked, k, budget)
    payload = {
        "unit": unit,
        "spec": spec_rel or "",
        "symptom": symptom or "",
        "ids": [row["id"] for row in picked],
        "scores": [
            {"id": row["id"], "score": row["score"], "tokens": row["tokens"],
             "status": row["status"], "kind": row["kind"]}
            for row in picked
        ],
        "tokens": lesson_tokens(picked),
        "budget": budget,
        "k": k,
        "matched": len(ranked),
    }
    if unit:
        folder = os.path.join(root, "work", unit)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "pulled.json")
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
        payload["pulled"] = "work/%s/pulled.json" % unit
    return picked, payload


def format_pull(picked, payload):
    lines = []
    labels = {"candidate": "candidata", "active": "ativa", "core": "core"}
    for row in picked:
        lines.append("%s  %s  %.4f  %d tok" % (
            row["id"], labels.get(row["status"], row["status"]), row["score"], row["tokens"]))
        lines.append(row["body"].rstrip())
        lines.append("")
    skills = sum(1 for row in picked if row.get("kind") == "skill")
    left = max(int(payload.get("matched") or 0) - len(picked), 0)
    lines.append("corte: %d itens de %d, %d de fora, %d tok de lição (teto %d), %d skills" % (
        len(picked), int(payload.get("matched") or 0), left, payload["tokens"], payload["budget"], skills))
    return "\n".join(lines).rstrip() + "\n"


def command(root, spec=None, symptom=None, k=K_DEFAULT, budget=BUDGET_DEFAULT, unit=None, tag=None):
    if bool(spec) == bool(symptom):
        return 2, "hdev library pull: informe --spec ou --symptom\n"
    if k < 1 or budget < 1:
        return 2, "hdev library pull: --k e --budget precisam ser positivos\n"
    query = symptom or ""
    spec_rel = ""
    if spec:
        path = resolve_spec(root, spec)
        if not path:
            return 1, "hdev library pull: spec não encontrada\n"
        with open(path, encoding="utf-8") as handle:
            query = handle.read()
        spec_rel = spec.replace("\\", "/")
        if tag is None and os.path.basename(path) == "brief.md":
            tag = "pergunta"
        if unit is None:
            unit = _unit_from_spec(spec_rel)
    try:
        picked, payload = pull(
            root, query, spec_rel=spec_rel, symptom=symptom or "", unit=unit,
            k=k, budget=budget, tag=tag)
    except ValueError as exc:
        return 1, "hdev library pull: %s\n" % exc
    return 0, format_pull(picked, payload)
