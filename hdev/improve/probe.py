"""hdev improve probe — testa candidatas do harness e só relata. Não adota nada (adotar é `hdev improve compose`).

Candidata = overlay `.hdev/overlays/<id>/` (espelha a raiz) + ficha `.hdev/overlays/<id>.json`
(`mark`, `summary`, `remove`). O `hdev eval run` aplica no clone; a árvore de trabalho não muda.
Três braços (plain, base, cand-<id>), n >= 3 corridas (n >= 2 com o claude real), teto do eval.
Runner `fake`, `none` ou `claude` (Sonnet, o mesmo do `hdev eval run`).
"""
import datetime
import difflib
import json
import os
import re
import statistics

from .. import eval as evalmod
from .. import unit as unitmod
from ..library import reflect

PROTECTED_REL = os.path.join("harness", "protected.txt")
OVERLAYS_REL = os.path.join(".hdev", "overlays")
MARKS = ("invariante", "domínio")
VERDICTS = ("ganharia", "empata", "perde", "sem evidência")
GAIN = 0.15
DIFF_ALERT = 0.5
MIN_RUNS = 3
MIN_RUNS_REAL = 2  # modelo real custa: n >= 2 cabe no orçamento de 9 corridas
MAX_CANDS = 2
COSTS = ("tokens", "seconds", "xray")
_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# Candidata determinística: tirar uma peça é a candidata mais barata. Referência de skill que não guarda.
DEMO = {
    "id": "demo",
    "mark": "domínio",
    "summary": "tira a referência de opções da skill briefing",
    "remove": [".claude/skills/briefing/references/options.md"],
}


def load_protected(root):
    """Prefixos de `harness/protected.txt`, ou None se o arquivo falta."""
    try:
        with open(os.path.join(root, PROTECTED_REL), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return None
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def is_protected(rel, prefixes):
    """Cai num prefixo, ou é pasta acima de um (tirar `harness` leva `harness/hooks/`)."""
    for entry in prefixes:
        bare = entry.rstrip("/")
        if rel == bare or (entry.endswith("/") and rel.startswith(entry)) or bare.startswith(rel + "/"):
            return True
    return False


def cand_ids(root):
    folder = os.path.join(root, OVERLAYS_REL)
    if not os.path.isdir(folder):
        return []
    return sorted(name for name in os.listdir(folder) if os.path.isdir(os.path.join(folder, name)))


def overlay_paths(root, cid):
    """(caminho relativo, de onde veio) dos arquivos do overlay e do `remove` da ficha. `remove` ruim vira None."""
    folder = os.path.join(root, OVERLAYS_REL, cid)
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames.sort()
        for name in sorted(filenames):
            out.append((os.path.relpath(os.path.join(dirpath, name), folder).replace(os.sep, "/"), "arquivo"))
    for raw in evalmod.overlay_meta(root, cid).get("remove") or []:
        out.append((evalmod.safe_rel(raw), "remove"))
    return out


def overlay_problems(root, only=None):
    """Erros das candidatas: caminho protegido, `remove` inválido, ficha sem marca."""
    ids = cand_ids(root) if only is None else list(only)
    if not ids:
        return []
    prefixes = load_protected(root)
    if prefixes is None:
        return ["overlay sem %s" % PROTECTED_REL.replace(os.sep, "/")]
    found = []
    for cid in ids:
        for rel, origin in overlay_paths(root, cid):
            if rel is None:
                found.append("%s: remove inválido" % cid)
            elif is_protected(rel, prefixes):
                found.append("%s: %s protegido (%s)" % (cid, rel, origin))
        meta = evalmod.overlay_meta(root, cid)
        if meta and meta.get("mark") not in MARKS:
            found.append("%s: mark fora de %s" % (cid, "/".join(MARKS)))
    return found


def propose(root, cid, editor=None):
    """Ficha da candidata. `demo` nasce determinística se faltar; o resto vem pronto do disco.

    `editor` é a costura para o modelo de outro provedor; nesta PR é sempre None (sem modelo).
    """
    if editor is not None:
        raise evalmod.EvalError("editor de modelo fica para depois; nesta PR só overlay pronto")
    if not cid or not _ID.match(cid):
        raise evalmod.EvalError("candidata inválida: %s" % cid)
    folder = os.path.join(root, OVERLAYS_REL, cid)
    if cid == "demo" and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
        with open(folder + ".json", "w", encoding="utf-8") as f:
            json.dump(DEMO, f, ensure_ascii=False, indent=2)
            f.write("\n")
    if not os.path.isdir(folder):
        raise evalmod.EvalError("candidata %s sem pasta %s/%s/" % (cid, OVERLAYS_REL, cid))
    meta = evalmod.overlay_meta(root, cid)
    return {"id": cid, "mark": meta.get("mark"), "summary": meta.get("summary") or "",
            "remove": list(meta.get("remove") or [])}


def _median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def _tokens(row):
    tok = row.get("tokens")
    if not isinstance(tok, dict) or tok.get("input") is None or tok.get("output") is None:
        return None
    return tok["input"] + tok["output"]


def arm_metrics(rows):
    """Mediana por braço. `pass` é a taxa; métrica sem dado vira None."""
    rows = list(rows)
    if not rows:
        return {"runs": 0, "pass": None, "tokens": None, "seconds": None, "xray": None}
    models = sorted({r["model"] for r in rows if r.get("model")})
    out = {
        "runs": len(rows),
        "pass": round(sum(1 for r in rows if r.get("pass")) / len(rows), 2),
        "tokens": _median(_tokens(r) for r in rows),
        "seconds": _median(r.get("seconds") for r in rows),
        "xray": _median(r.get("xray") for r in rows),
    }
    if any("model" in r for r in rows):
        out["model"] = ",".join(models) or None
    return out


def deltas(base, cand):
    """Variação relativa da candidata contra o base, por métrica com dado dos dois lados."""
    out = {}
    for key in ("pass",) + COSTS:
        b, c = base.get(key), cand.get(key)
        if b is None or c is None:
            continue
        out[key] = round((c - b) / b, 3) if b else (0.0 if c == b else 1.0)
    return out


def verdict(base, cand):
    """Qualidade nunca cai; custo conta a partir de 15%."""
    if not base.get("runs") or not cand.get("runs"):
        return "sem evidência"
    if (cand.get("pass") or 0) < (base.get("pass") or 0):
        return "perde"
    d = deltas(base, cand)
    costs = [d[k] for k in COSTS if k in d]
    if any(v >= GAIN for v in costs):
        return "perde"
    if any(v <= -GAIN for v in costs):
        return "ganharia"
    return "empata"


def diff_alert(base_lines, changed_lines):
    return base_lines > 0 and changed_lines / base_lines > DIFF_ALERT


def diff_size(root, cid):
    """(linhas dos arquivos tocados na árvore, linhas mudadas pela candidata)."""
    base_total = changed = 0
    folder = os.path.join(root, OVERLAYS_REL, cid)
    for rel, origin in overlay_paths(root, cid):
        if rel is None:
            continue
        old = _lines(os.path.join(root, *rel.split("/")))
        new = [] if origin == "remove" else _lines(os.path.join(folder, *rel.split("/")))
        base_total += len(old)
        changed += sum(1 for line in difflib.ndiff(old, new) if line[:1] in "+-")
    return base_total, changed


def _lines(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read().splitlines()
    except (OSError, UnicodeError):
        return []


def _lesson(cid, meta, result, unit, run_name):
    summary = meta.get("summary") or "candidata %s" % cid
    return {
        "kind": "lesson",
        "title": "Candidata %s do improve: %s" % (cid, result["verdict"]),
        "when_to_use": "quando o improve repetir a candidata %s que %s" % (cid, summary),
        "not_for": "out-of-domain example",
        "body": "quando o improve testar a candidata %s, faça a leitura do relatório antes de adotar, "
                "porque o probe deu %s e nada foi adotado" % (cid, result["verdict"]),
        "tags": ["improve", "candidata", cid],
        "scope": "global",
        "source": "improve",
        "evidence": [{"unit": unit, "run": run_name, "delta": result["delta"]}],
    }


def _write(root, stem, payload, report):
    folder = os.path.join(root, ".hdev", "runs")
    os.makedirs(folder, exist_ok=True)
    for name, text in ((stem + ".json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n"),
                       (stem + ".md", report)):
        tmp = os.path.join(folder, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, os.path.join(folder, name))
    return stem + ".json", stem + ".md"


def _report(payload):
    def fmt(m):
        return "| %s | %s | %s | %s | %s | %s |" % (
            m["runs"], m["pass"], m["tokens"], m["seconds"], m["xray"], m.get("model") or "—")
    lines = ["# improve probe — %s" % payload["case"], "",
             "Só relatório. Nada adotado (adotar é `hdev improve compose`).", "",
             "Base `%s`, runner `%s`, %d corridas por braço." % (
                 payload["base_sha"][:12], payload["runner"], payload["runs"]), "",
             "| braço | corridas | pass | tokens | segundos | xray | modelo |", "|---|---|---|---|---|---|---|"]
    for arm, m in payload["arms"].items():
        lines.append("| %s " % arm + fmt(m))
    if payload.get("model"):
        lines += ["", "Modelo pedido: `%s`." % payload["model"]]
        if payload.get("model_mismatch"):
            lines.append("Alerta: %d corrida(s) com modelo ≠ pedido." % payload["model_mismatch"])
    lines += ["", "Paradas fora da lista: sem medida no runner %s." % payload["runner"], ""]
    for c in payload["candidates"]:
        alert = " Alerta: diff > 50%." if c["diff_alert"] else ""
        lines.append("- `%s` (%s): **%s**, não adotado. Δ %s.%s" % (
            c["id"], c["mark"], c["verdict"], json.dumps(c["delta"], sort_keys=True), alert))
    return "\n".join(lines) + "\n"


def probe(root, case, cands, runs, runner, dry_run=False, unit=None):
    root = os.path.realpath(root)
    if runner not in ("fake", "none", "claude"):
        raise evalmod.EvalError("improve só roda com --runner fake, none ou claude")
    if not cands or len(cands) > MAX_CANDS:
        raise evalmod.EvalError("de 1 a %d candidatas" % MAX_CANDS)
    least = MIN_RUNS_REAL if runner == "claude" else MIN_RUNS
    if runs < least:
        raise evalmod.EvalError("--runs pede >= %d por braço" % least)
    metas = [propose(root, cid) for cid in cands]
    bad = overlay_problems(root, cands)
    if bad:
        raise evalmod.EvalError("candidata recusada: %s" % "; ".join(bad), code=1)
    arms = ",".join(["plain", "base"] + ["cand-" + cid for cid in cands])
    res = evalmod.run(root, case, arms, runs, runner, dry_run=dry_run)
    if dry_run:
        res["candidates"] = metas
        return res
    by_arm = {}
    for row in res["results"]:
        by_arm.setdefault(row["arm"], []).append(row)
    arm_m = {arm: arm_metrics(by_arm.get(arm, [])) for arm in ("plain", "base")}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = "improve-%s" % stamp
    unit = unit or (unitmod.load(root) or {}).get("id") or case
    results = []
    for meta in metas:
        m = arm_metrics(by_arm.get("cand-" + meta["id"], []))
        arm_m["cand-" + meta["id"]] = m
        base_lines, changed = diff_size(root, meta["id"])
        results.append({"id": meta["id"], "mark": meta["mark"], "summary": meta["summary"], "metrics": m,
                        "delta": deltas(arm_m["base"], m), "verdict": verdict(arm_m["base"], m),
                        "diff": {"base_lines": base_lines, "changed": changed},
                        "diff_alert": diff_alert(base_lines, changed), "adopted": False})
    payload = {"kind": "improve", "version": 1, "case": case, "base_sha": res["base_sha"],
               "runner": runner, "model": res.get("model"), "runs": runs, "eval_run": res["run"], "arms": arm_m,
               "candidates": results, "adopted": [],
               "model_mismatch": sum(1 for r in res["results"] if r.get("model_ok") is False)}
    lessons = [_lesson(c["id"], meta, c, unit, stem + ".json")
               for c, meta in zip(results, metas) if c["verdict"] != "sem evidência"]
    payload["library"] = reflect.add_items(root, unit, lessons, offline=True) if lessons else []
    run_name, report_name = _write(root, stem, payload, _report(payload))
    return {"run": run_name, "report": report_name, "eval": res, "payload": payload}


def main_probe(args):
    cands = [c.strip() for c in (args.cand or "").split(",") if c.strip()]
    try:
        res = probe(args.root, args.case, cands, args.runs, args.runner, args.dry_run)
    except evalmod.EvalError as e:
        print("hdev improve: %s" % e)
        return e.code
    if res.get("dry_run"):
        print("hdev improve: dry-run (nada roda, nada se adota)")
        print("  caso: %s" % res["case"])
        print("  braços: %s" % ", ".join(res["arms"]))
        if res.get("model"):
            print("  modelo: %s" % res["model"])
        print("  %d braços × %d corridas = %d (teto %d)" % (
            len(res["arms"]), res["runs"], len(res["arms"]) * res["runs"], evalmod.RUN_CAP))
        for c in res["candidates"]:
            print("  candidata %s (%s): %s" % (c["id"], c["mark"], c["summary"]))
        return 0
    payload = res["payload"]
    print("hdev improve: %s, %d braços × %d corridas, nada adotado" % (
        payload["case"], len(payload["arms"]), payload["runs"]))
    for c in payload["candidates"]:
        print("  %s (%s): %s%s" % (c["id"], c["mark"], c["verdict"], " [alerta diff > 50%]" if c["diff_alert"] else ""))
    for item in payload["library"]:
        print("  biblioteca: %s %s" % (item["action"], item["id"] or item["reason"]))
    print("  registro: .hdev/runs/%s" % res["run"])
    print("  relatório: .hdev/runs/%s" % res["report"])
    return 0
