"""Fechamento da unidade (v0.4.0, ADR 0009).

`hdev fechar --plan P [--resumo T] [--override "operator: motivo"] [--squash] [--dry-run]` grava o marco da entrega:
  INF-006 feito: <resumo>; juiz pass|override
  (corpo curto)
  Unidade / Base / Head / Juiz ou Override / Harness-Versao   (trailers)
Os commits-turno ficam como checkpoints; o marco sai vazio (`--allow-empty`) se eles já levaram o código.
O marco só nasce na branch `base_branch` (`.hdev/config.json`; senão a base do remoto, senão a branch atual).
Noutra branch os portões rodam, o veredito vai para `.hdev/runs/fechar-*.json` e o commit não é criado.
Portões na branch base: base gravada por `hdev base --marcar` (dedução, HEAD e a base que o 1º judge grava não
fecham), base ancestral de HEAD, árvore sem mudança rastreada, intervalo sem commit de outra unidade, suíte
inteira verde (`gates.full`, quando existe) e juiz pass deste plano em HEAD (ou em ancestral com só docs/ no
meio) ou override do dono. A suíte roda num clone limpo do HEAD, em shards, com cache por tree sha. Árvore suja
rastreada recusa o fecho: a mensagem diz que a suíte cobre só o commit. Fora da base, juiz pass e a base marcada
não são exigidos (autorizam o commit, que não nasce); árvore, suíte e, se a base marcada existir, ancestral e
intervalo continuam valendo. O override não dispensa a suíte. No marco entra o trailer `Hdev-Gates-Full:`; fora da
base a mesma linha vai no veredito. `--dry-run` mostra o comando, os shards e o cache, sem rodar. `--no-cache`
força a corrida. `--squash` é opcional e só na branch base: intervalo local, `bkp/<id>-<sha>`, juiz de novo no
SHA novo. Nunca faz push nem merge. Tag de app não sai daqui: `hdev app tag`, na publicação.
Depois da suíte passar, grava `evals/tasks/<id>/task.json`. Não grava em falha nem em `--dry-run`.
Na branch base o arquivo entra no marco. Fora dela fica no worktree, sem commit.
"""
import datetime
import glob
import json
import os
import re
import subprocess

from . import VERSION
from . import base as basemod
from . import config as cfgmod
from . import eval as evalmod
from . import unit as unitmod
from .gates import full as fullmod

MARCAR = "hdev base --marcar"
ID_RX = re.compile(r"^([A-Z]+\d*-\d+)\b")
TITLE_RX = re.compile(r"^#\s+(?:Plano\s*[—:-]\s*)?(.+?)\s*$", re.M)
DOCS_ONLY = ("docs/",)


class FecharError(Exception):
    pass


def _run(root, *args, stdin=None):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, input=stdin, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise FecharError("git falhou: %s" % e)
    return r


def _out(root, *args):
    r = _run(root, *args)
    return r.stdout.strip() if r.returncode == 0 else None


def marked_base(root, key):
    """SHA da base gravada por `hdev base --marcar`, ou FecharError dizendo como gravar."""
    rec = basemod.recorded(root, key)
    if not rec:
        raise FecharError("%s sem base gravada: rode `hdev base --plan P --marcar [REF]` antes do código" % key)
    origem = str(rec[1].get("origem", ""))
    if not origem.startswith(MARCAR):
        raise FecharError("%s tem base %s de \"%s\"; fechar exige `hdev base --plan P --marcar [REF]` "
                          "(confira e grave com --force se mudar)" % (key, rec[0][:12], origem))
    return rec[0]


def mixed(root, base, head, uid):
    """Commits do intervalo cuja 1ª linha começa com o ID de outra unidade."""
    log = _out(root, "log", "--format=%h %s", "%s..%s" % (base, head)) or ""
    out = []
    for line in log.splitlines():
        sha, _, subject = line.partition(" ")
        m = ID_RX.match(subject)
        if m and m.group(1) != uid:
            out.append("%s %s" % (sha, subject[:60]))
    return out


def _docs_only(root, old, new):
    names = _out(root, "diff", "--name-only", old, new)
    return names is not None and all(n.startswith(DOCS_ONLY) for n in names.splitlines() if n)


def judge_pass(root, plan_rel, base, head):
    """(run, head julgado, cli) do pass que vale para `head`, ou None."""
    for path in sorted(glob.glob(os.path.join(root, ".hdev", "runs", "judge-*.json")), reverse=True):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("verdict") != "pass" or data.get("dirty"):
            continue
        if data.get("plan") != plan_rel or not isinstance(data.get("head_sha"), str):
            continue
        if data.get("base_sha") and data["base_sha"] != base:
            continue  # julgou outro diff
        judged = data["head_sha"]
        if judged == head or (_run(root, "merge-base", "--is-ancestor", judged, head).returncode == 0
                              and _docs_only(root, judged, head)):
            clis = [a.get("cli") for a in data.get("attempts", []) if a.get("verdict") == "pass"]
            return os.path.basename(path)[:-5], judged, (clis[0] if clis else None)
    return None


def plan_title(plan_text):
    m = TITLE_RX.search(plan_text or "")
    return m.group(1) if m else None


def message(uid, resumo, base, judged, juiz=None, override=None, nota=None, gates=None):
    kind = "pass" if juiz else "override"
    lines = ["%s feito: %s; juiz %s" % (uid, resumo, kind), ""]
    lines.append(nota or "Marco de fechamento; os commits-turno do intervalo são checkpoints.")
    lines += ["", "Unidade: %s" % uid, "Base: %s" % base[:12], "Head: %s" % judged[:12]]
    lines.append("Juiz: %s" % juiz if juiz else "Override: %s" % override)
    lines.append("Harness-Versao: v%s" % VERSION)
    if gates:
        lines.append(gates)
    return "\n".join(lines) + "\n"


def require_suite(root, no_cache=False):
    """Roda gates.full num clone limpo. Sem config ou sem comando, não há suíte. Chave antiga é erro."""
    try:
        result = fullmod.execute(root, no_cache=no_cache)
    except fullmod.SuiteError as e:
        raise FecharError(str(e))
    if result is None or result.get("ok"):
        return result
    raise FecharError(result.get("message") or "suíte vermelha")


def not_pushed(root, base, head):
    total = _out(root, "rev-list", "--count", "%s..%s" % (base, head))
    local = _out(root, "rev-list", "--count", head, "--not", base, "--remotes")
    return total is not None and total == local


def current_branch(root):
    return _out(root, "rev-parse", "--abbrev-ref", "HEAD") or "HEAD"


def configured_base_branch(root):
    """Onde o marco pode nascer: `base_branch` do repo, senão `origin/HEAD`, senão a branch atual."""
    cfg, _err = cfgmod.load(root)
    if cfg:
        name = cfg.get("base_branch")
        if isinstance(name, str) and name.strip():
            return name.strip()
    ref = _out(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if ref and "/" in ref:
        return ref.split("/", 1)[1]
    return current_branch(root)


def base_for_close(root, uid, on_base):
    """SHA marcado, ou None fora da base quando não há registro. Registro ruim falha nos dois casos."""
    item = basemod.load(root).get(uid)
    if not isinstance(item, dict) and not on_base:
        return None
    return marked_base(root, uid)


def record_skip(root, payload):
    runs = os.path.join(root, ".hdev", "runs")
    os.makedirs(runs, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = "fechar-%s.json" % stamp
    with open(os.path.join(runs, name), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return name


def close(root, plan, resumo=None, override=None, squash=False, dry_run=False, no_cache=False):
    root = os.path.realpath(root)
    plan_path = plan if os.path.isabs(plan) else os.path.join(root, plan)
    try:
        with open(plan_path, encoding="utf-8") as f:
            plan_text = f.read()
    except OSError as e:
        raise FecharError(str(e))
    plan_rel = basemod._rel(root, plan_path)
    uid = basemod.unit_id(plan_rel)
    if not uid:
        raise FecharError("plano sem id de unidade no nome (work/<id>/plan.md ou docs/plan-inf-006-...md): %s"
                          % plan_rel)
    if override is not None and not override.strip():
        raise FecharError("--override pede o motivo e quem autorizou (ex.: \"operator: juiz falso negativo\")")
    branch = current_branch(root)
    trunk = configured_base_branch(root)
    on_base = branch == trunk
    base = base_for_close(root, uid, on_base)
    head = _out(root, "rev-parse", "--verify", "HEAD")
    if not head or (base and _run(root, "merge-base", "--is-ancestor", base, head).returncode != 0):
        raise FecharError("base %s não é ancestral de HEAD; corrija com `hdev base --marcar REF --force`"
                          % (base or "")[:12])
    if _out(root, "status", "--porcelain", "--untracked-files=no"):
        raise FecharError("árvore com mudança rastreada: a suíte cobre só o commit; commite antes de fechar")
    if base:
        misturados = mixed(root, base, head, uid)
        if misturados:
            raise FecharError("intervalo misturado (separe, ou redefina o escopo e julgue de novo): %s"
                              % "; ".join(misturados))
    try:
        planned = fullmod.plan(root, no_cache=no_cache) if dry_run else None
    except fullmod.SuiteError as e:
        raise FecharError(str(e))
    suite = None if dry_run else require_suite(root, no_cache=no_cache)
    gates_line = fullmod.trailer(suite) if suite else None
    found = judge_pass(root, plan_rel, base, head) if base else None
    if on_base and override is None and not found:
        raise FecharError("sem `hdev judge` pass de %s em HEAD (%s) com base %s; julgue, ou --override \"motivo\""
                          % (plan_rel, head[:12], base[:12]))
    juiz = None
    judged = head
    if override is None and found:
        run, judged, cli = found
        juiz = "pass (%s%s)" % ("%s, " % cli if cli else "", run)
    resumo = (resumo or plan_title(plan_text) or uid).strip()
    nota = None
    if on_base and squash:
        if not not_pushed(root, base, head):
            raise FecharError("--squash recusado: parte do intervalo %s..HEAD já está num remoto" % base[:12])
        nota = "Squash de %s..%s (backup em bkp/%s-%s); juiz de novo no SHA novo." % (
            base[:12], head[:12], uid.lower(), head[:12])
    task_rel = None
    if not dry_run:
        try:
            task_rel = evalmod.record_case(root, uid, plan_text, base, plan_rel)
        except OSError as e:
            raise FecharError("não gravei o caso: %s" % e)
    msg = message(uid, resumo, base, judged, None if override is not None else juiz, override, nota,
                  gates_line) if on_base else ""
    out = {"unidade": uid, "base": base, "head": head, "mensagem": msg, "squash": bool(on_base and squash),
           "commit": None, "branch": branch, "base_branch": trunk, "marco": "commit" if on_base else "pulado",
           "plan": planned, "suite": suite, "task": task_rel}
    if not on_base:
        payload = {
            "kind": "fechar", "verdict": "dry-run" if dry_run else "pass", "milestone": "skipped",
            "plan": plan_rel, "unidade": uid, "branch": branch, "base_branch": trunk, "base": base,
            "head": head, "squash": bool(squash), "juiz": juiz, "override": override}
        if dry_run:
            payload["dry_run"] = True
        if gates_line:
            payload["gates_full"] = gates_line
        out["run"] = record_skip(root, payload)
        if not dry_run:
            unitmod.close_unit(root, uid)
            _library_after_pass(root, uid, plan_rel)
        return out
    if dry_run:
        return out
    if squash:
        if _run(root, "branch", "bkp/%s-%s" % (uid.lower(), head[:12]), head).returncode != 0:
            raise FecharError("não criei o backup bkp/%s-%s" % (uid.lower(), head[:12]))
        if _run(root, "reset", "--soft", base).returncode != 0:
            raise FecharError("git reset --soft %s falhou" % base[:12])
    if task_rel and _run(root, "add", "--", task_rel).returncode != 0:
        raise FecharError("não consegui preparar o caso %s" % task_rel)
    r = _run(root, "commit", "-q", "--allow-empty", "-F", "-", stdin=msg)
    if r.returncode != 0:
        raise FecharError("git commit falhou: %s" % (r.stderr.strip() or r.stdout.strip())[:300])
    out["commit"] = _out(root, "rev-parse", "HEAD")
    unitmod.close_unit(root, uid)
    _library_after_pass(root, uid, plan_rel)
    return out


def _library_after_pass(root, uid, plan_rel):
    """Pontua o pull e roda o tidy. O --dry-run não chega aqui."""
    from .library import life as lifemod
    lifemod.attribute(root, uid, plan_rel)
    lifemod.tidy_root(root)


def progress_line(res, kind):
    return "%s | base %s | juiz %s | fecha %s | harness v%s" % (
        res["unidade"], res["base"][:7], kind, (res["commit"] or "?")[:7], VERSION)


def _print_suite(res, dry_run):
    if dry_run:
        print(fullmod.format_plan(res.get("plan")))
        return
    suite = res.get("suite")
    if suite and suite.get("ok"):
        print("  " + fullmod.summary(suite))
        line = fullmod.trailer(suite)
        if line:
            print("  " + line)


def main(args):
    try:
        res = close(args.root, args.plan, args.resumo, args.override, args.squash, args.dry_run, args.no_cache)
    except FecharError as e:
        print("hdev fechar: %s" % e)
        return 1
    if res.get("marco") == "pulado":
        print("hdev fechar: commit do marco pulado (branch %s não é a base %s)." % (
            res["branch"], res["base_branch"]))
        if res.get("run"):
            print("  veredito: .hdev/runs/%s" % res["run"])
        if res.get("task"):
            print("  caso: %s" % res["task"])
        _print_suite(res, args.dry_run)
        _reflect_hint(res)
        return 0
    if args.dry_run:
        print(res["mensagem"], end="")
        _print_suite(res, True)
        _reflect_hint(res)
        return 0
    kind = "override" if args.override is not None else "pass"
    print("hdev fechar: %s fechada em %s (base %s)" % (res["unidade"], res["commit"][:12], res["base"][:12]))
    if res.get("task"):
        print("  caso: %s" % res["task"])
    _print_suite(res, False)
    print("  progress: %s" % progress_line(res, kind))
    if res["squash"]:
        print("  squash feito: rode `hdev judge --plan %s --run-tests` de novo no SHA novo." % args.plan)
    print("  push só com unidade fechada e o dono liberando destino, branch e tags.")
    _reflect_hint(res)
    return 0


def _reflect_hint(res):
    print("  reflita: hdev reflect --unit %s" % res["unidade"])
