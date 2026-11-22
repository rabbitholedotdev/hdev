"""Orquestra o juiz: pacote, cache, provedor e registro."""
import concurrent.futures
import datetime
import glob
import hashlib
import json
import os

from hdev import base as basemod
from hdev import config as cfgmod
from hdev import stop as stopmod

from . import cache as cachemod
from . import codex as codexmod
from . import grok as grokmod
from .constants import EXIT, LABELS_NEEDED, MAX_PARTS, PARALLEL
from .evidence import check_evidence_refs, evidence, evidence_items
from hdev import CORE_ROOT
import sys

sys.path.insert(0, os.path.join(CORE_ROOT, "hooks"))
import _lib  # noqa: E402

from .gitdiff import (
    JudgeError, _git, collect_diff, commit_text, criterion_from_plan, diff_stat, resolve_commit,
)
from .invoke import execute
from .package import build_packages
from .verdict import count_labels, diagnose


def call_judge(role_name, role, package, timeout, root, part=None):
    """Grok (xai), Codex (fallback) ou outra CLI. O falso dos testes entra pelo comando do papel."""
    if grokmod.matches(role):
        return grokmod.call(role_name, role, package, timeout, root, part=part)
    if codexmod.matches(role):
        return codexmod.call(role_name, role, package, timeout, root, part=part)
    return execute(role_name, role, package, timeout, root, part=part)


def _from_cache(root, hit):
    """O veredito guardado, sem chamada. Os rótulos são relidos: a linha consultiva não envelhece."""
    served = dict(hit)
    served["cache"] = True
    served["calls"] = 0
    served["seconds"] = 0
    labels = count_labels(root)
    served["labels"] = labels
    served["advisory"] = labels < LABELS_NEEDED
    return served

def _judge_one(cfg, package, root, part=None):
    """Cadeia judge → judge_fallback sobre um pacote. Devolve (tentativas, final pass/fail ou None)."""
    roles = cfg.get("roles") or {}
    timeout = int((cfg.get("judge") or {}).get("timeout", 600))
    executor_provider = cfgmod.model_provider((roles.get("executor") or {}).get("model"))
    attempts = []
    for name in ("judge", "judge_fallback"):
        role = roles.get(name)
        if role is None:
            continue
        provider, role_err = cfgmod.validate_role(name, role)
        if role_err:
            attempts.append({"role": name, "status": "recusado: %s" % role_err})
            continue
        if executor_provider is None or provider == executor_provider:
            attempts.append({"role": name, "status": "recusado: mesmo provedor do executor (ou executor sem provedor)"})
            continue
        attempt = call_judge(name, role, package, timeout, root, part=part)
        attempts.append(attempt)
        if attempt.get("verdict") in ("pass", "fail"):
            break  # fail não é rerrolado no segundo provedor
    final = next((a for a in attempts if a.get("verdict") in ("pass", "fail")), None)
    return attempts, final


def _int_cfg(cfg, key, default, low=1, high=32):
    try:
        return max(low, min(high, int((cfg.get("judge") or {}).get(key, default))))
    except (TypeError, ValueError):
        return default


def previous_runs(root, plan_rel, limit=20):
    """Registros anteriores deste plano, do mais novo ao mais velho."""
    out = []
    for path in sorted(glob.glob(os.path.join(root, ".hdev", "runs", "judge-*.json")), reverse=True):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if data.get("plan") == plan_rel:
            data["_run"] = os.path.basename(path)[:-5]
            out.append(data)
            if len(out) >= limit:
                break
    return out

def judge(root, plan_path, base=None, tests_log=None, do_run_tests=False, dry_run=False, head=None,
          rejulgar=False, no_cache=False):
    cfg, err = cfgmod.load(root)
    if err:
        return {"verdict": "usage", "error": err}
    if head and not base:
        return {"verdict": "usage", "error": "--head pede --base (intervalo base..head)"}
    with open(plan_path if os.path.isabs(plan_path) else os.path.join(root, plan_path), encoding="utf-8") as f:
        plan_text = f.read()
        criterion = criterion_from_plan(plan_text)
    plan_rel = os.path.relpath(os.path.join(root, plan_path), root)
    try:
        for ref in (base, head):
            if ref:
                resolve_commit(root, ref)
        # base da unidade (ADR 0008): o commit-turno não esconde do juiz o que já foi commitado na peça
        base_info = basemod.resolve(root, plan_path, plan_text, explicit=base)
        if not head:
            base = base_info["sha"]
        unit_tokens = [base_info.get("unidade")] if base_info.get("unidade") else []
        # anexos citados no plano: falha cedo, antes de rodar testes e chamar o juiz (ADR 0010)
        ev_err = check_evidence_refs(root, plan_path, plan_text, head, unit_tokens)
        if ev_err:
            raise JudgeError(ev_err)
        diff = collect_diff(root, base, head)
    except JudgeError as e:
        return {"verdict": "usage", "error": str(e)}
    # o check entra sempre (revisão Codex, rodada 11); os testes vêm do log dado ou são rodados
    tests_text, check_out = evidence(root, cfg, head, with_tests=do_run_tests and not tests_log,
                                    base=base_info.get("sha") or base)
    if tests_log:
        with open(tests_log, encoding="utf-8") as f:
            tests_text = f.read()[-40000:]
    base_out = "%s — %s" % ((base_info["sha"] or "HEAD")[:12], base_info["fonte"])
    items = evidence_items(root, plan_path, plan_text, head, unit_tokens)
    evidence_out = "\n\n".join("--- %s\n%s" % (rel, body.rstrip()) for rel, body, _ in items)
    max_parts = _int_cfg(cfg, "max_parts", MAX_PARTS)
    packages, meta = build_packages(criterion, diff, tests_text, base_out=base_out,
                                    stat=diff_stat(root, base, head), check_out=check_out,
                                    commits=commit_text(root, base, head), evidence_out=evidence_out,
                                    max_parts=max_parts)
    meta.update({"max_partes": max_parts, "evidencia": [rel for rel, _, _ in items],
                 "evidencia_truncada": [rel for rel, _, t in items if t]})
    package = ("\n\n######## PARTE SEGUINTE ########\n\n".join(packages) if len(packages) > 1 else packages[0])

    hits = _lib.find_secrets(package)
    if hits:
        lines = ", ".join("%s (linha %d do pacote)" % h for h in hits[:10])
        return {"verdict": "secret", "error": "segredo no pacote, juiz não chamado: %s" % lines}
    if dry_run:
        return {"verdict": "dry-run", "package": package, "pacote": meta}
    package_sha = hashlib.sha256(package.encode("utf-8")).hexdigest()
    prev = previous_runs(root, plan_rel)
    if (not rejulgar and prev and prev[0].get("verdict") == "unsure"
            and prev[0].get("package_sha") == package_sha):
        return {"verdict": "usage", "error": "pacote idêntico ao do último unsure (%s): o juiz diria o mesmo. "
                "Mude a evidência, o critério ou o diff (diagnóstico no registro anterior), ou use --rejulgar."
                % prev[0]["_run"]}
    if base_info["tipo"] == "deduzida":  # a 1ª dedução fica: commits-turno seguintes não a movem
        basemod.save(root, base_info["unidade"], base_info["sha"], "1º hdev judge (%s)" % base_info["fonte"],
                     plan_rel)

    refs = judged_refs(root, base, head)
    key, key_payload = cachemod.make_key(
        cfg, refs.get("base_sha") or "", refs.get("head_sha") or "", plan_text, package_sha,
        do_run_tests, tests_log)
    if not no_cache and not rejulgar:
        hit = cachemod.load(root, key)
        if hit:
            return _from_cache(root, hit)

    n = len(packages)
    if n == 1:
        attempts, final = _judge_one(cfg, packages[0], root)
        verdict = final["verdict"] if final else "unsure"
        reasons = final.get("reasons", []) if final else [a.get("status") or "unsure" for a in attempts]
    else:
        workers = min(n, _int_cfg(cfg, "parallel", PARALLEL))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_judge_one, cfg, pkg, root, i) for i, pkg in enumerate(packages, 1)]
            outcomes = [f.result() for f in futures]
        attempts = [a for atts, _ in outcomes for a in atts]
        verdicts = [fin["verdict"] if fin else "unsure" for _, fin in outcomes]
        verdict = "fail" if "fail" in verdicts else ("pass" if all(v == "pass" for v in verdicts) else "unsure")
        reasons = []
        for i, ((atts, fin), v) in enumerate(zip(outcomes, verdicts), 1):
            rs = fin.get("reasons", []) if fin else [a.get("status") or "unsure" for a in atts]
            reasons += ["[parte %d/%d: %s] %s" % (i, n, v, r) for r in (rs or ["(sem motivo)"])]
    if verdict == "pass" and meta["omitidos"]:
        verdict = "unsure"
        reasons = ["%d arquivo(s) ficaram fora do pacote (mais de %d partes): pass não vale sem o juiz ver tudo"
                   % (len(meta["omitidos"]), max_parts)] + reasons
    labels = count_labels(root)
    result = {
        "advisory": labels < LABELS_NEEDED,
        "labels": labels,
        "verdict": verdict,
        "reasons": reasons,
        "attempts": attempts,
        "calls": sum(1 for a in attempts if "seconds" in a),
        "seconds": round(sum(a.get("seconds", 0) for a in attempts), 2),
        "plan": plan_rel,
        "package_chars": len(package),
        "package_sha": package_sha,
        "pacote": meta,
        "base_fonte": base_info["fonte"],
        "unidade": base_info["unidade"],
    }
    if verdict == "unsure":
        streak, tips = diagnose(result, meta, prev)
        result["unsure_seguidos"] = streak
        result["diagnostico"] = tips
        note = stopmod.note_judge_block(root, plan_rel, attempts)
        if note:
            result["retomada"] = note
    result.update(refs)
    record(root, result)
    cachemod.store(root, key, key_payload, result)
    return result


def judged_refs(root, base, head):
    """O que foi julgado (F2-01): a promoção do canal latest só aceita pass cujo head é o commit da tag."""
    head_sha = _git(root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % (head or "HEAD")).strip() or None
    base_sha = _git(root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % base).strip() if base else None
    dirty = False if head else bool(_git(root, "status", "--porcelain").strip())
    return {"base_sha": base_sha or None, "head_sha": head_sha, "dirty": dirty}


def record(root, result):
    runs = os.path.join(root, ".hdev", "runs")
    os.makedirs(runs, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    with open(os.path.join(runs, "judge-%s.json" % stamp), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(os.path.join(runs, "metrics.jsonl"), "a", encoding="utf-8") as f:
        for a in result["attempts"]:
            if "seconds" in a:
                f.write(json.dumps({"ts": stamp, "stage": "judge", "plan": result["plan"], "cli": a.get("cli"),
                                    "model": a.get("model"), "seconds": a["seconds"], "tokens": a.get("tokens"),
                                    "verdict": a.get("verdict"), "status": a.get("status")},
                                   ensure_ascii=False) + "\n")


def main(args):
    root = os.path.realpath(args.root)
    try:
        result = judge(root, args.plan, base=args.base, tests_log=args.tests_log, do_run_tests=args.run_tests,
                       dry_run=args.dry_run, head=args.head, rejulgar=getattr(args, "rejulgar", False),
                       no_cache=getattr(args, "no_cache", False))
    except OSError as e:
        print("hdev judge: %s" % e)
        return EXIT["usage"]
    verdict = result["verdict"]
    if verdict == "dry-run":
        print(result["package"])
        return 0
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif verdict in ("usage", "secret"):
        print("hdev judge: %s" % result["error"])
    else:
        print("veredito: %s (%d chamada(s), %ss)" % (verdict, result["calls"], result["seconds"]))
        if result.get("cache"):
            print("  cache: veredito reutilizado; o provedor não foi chamado")
        print("  base do diff: %s (%s)" % ((result.get("base_sha") or "HEAD")[:12], result.get("base_fonte", "?")))
        meta = result.get("pacote") or {}
        print("  pacote: %s parte(s), %s arquivo(s) no diff, %s movimento(s) puro(s) em lista%s%s" % (
            meta.get("partes", 1), meta.get("arquivos_no_diff", "?"), meta.get("renomeados_puros", 0),
            "; %d cortado(s)" % len(meta["cortados"]) if meta.get("cortados") else "",
            "; %d FORA do pacote" % len(meta["omitidos"]) if meta.get("omitidos") else ""))
        if result["advisory"]:
            print("  consultivo (%d/%d casos rotulados): o operador decide o fechamento."
                  % (result["labels"], LABELS_NEEDED))
        for reason in result["reasons"]:
            print("  - %s" % reason)
        if verdict == "unsure":
            for tip in result.get("diagnostico") or []:
                print("  diagnóstico: %s" % tip)
            print("Sem veredito: bloqueia só este fechamento. Override do operador em docs/progress.md: "
                  "\"liberado sem juiz: <motivo>\".")
            retomada = result.get("retomada") or {}
            if retomada.get("proximo"):
                print("  retomada: %s (%s)" % (retomada["proximo"], retomada.get("acao")))
    return EXIT.get(verdict, 2)
