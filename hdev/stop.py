"""Lista fechada de parada, PAREI retomável e fila idempotente de retentativa.

Pare só em 2FA/login ou ação destrutiva/irreversível. O resto vira linha em
docs/decisions.md e o fluxo segue. Quota do juiz entra na fila, não para o humano.
"""
import datetime
import json
import os
import re
import subprocess
import sys
import time

from . import unit as unitmod

PAREI_REL = os.path.join(".hdev", "state", "parei")
QUEUE_REL = os.path.join(".hdev", "state", "retry-queue.jsonl")
DECISIONS_REL = os.path.join("docs", "decisions.md")
DECISION_MAX = 240

# Lista fechada. Fora dela o agente escolhe o padrão e continua.
CLOSED = (
    ("2fa", re.compile(
        r"(?i)(\b2fa\b|two[- ]factor|\bmfa\b|c[oó]digo de verifica|verification code|\botp\b)")),
    ("login", re.compile(
        r"(?i)(\blogin\b|\blog in\b|sign[- ]in|\bnot logged\b|unauthori[sz]ed|autentica)")),
    ("destructive", re.compile(
        r"(?i)(\bsudo\b|\bfirewall\b|\bufw\b|git push|push para (?:o )?remoto|\bpublicar\b|"
        r"apagar .{0,40}fora|fora do repo|outra vm|área da ratoeira|area da ratoeira|"
        r"irrevers[ií]vel|destrutiv)")),
)
_NEG = re.compile(r"(?i)\bn[aã]o\b|\bsem\b|\bnunca\b")
RATE_RX = re.compile(r"(?i)rate.?limit|quota|usage limit")
PAREI_LINE = re.compile(
    r"^PAREI:\s*(?P<motivo>.+?)\s*\|\s*pr[oó]ximo:\s*(?P<proximo>.+)\s*$",
    re.IGNORECASE,
)
EXHAUSTED_RX = re.compile(r"(?i)^gate esgotado\b")
WAIT_RX = re.compile(r"(?i)^espera\b")
# Stop: recorte do diff. Passou disso, cai no smoke (a suíte inteira é no hdev fechar).
STOP_TIMEOUT = 22
SMOKE_TIMEOUT = 6
SMOKE_FILES = ("tests/test_smoke.py", "tests/test_stop.py")
HOOK_LABEL = {
    "secret_guard.py": "tests.test_hooks.SecretGuard",
    "destructive_guard.py": "tests.test_hooks.DestructiveGuard",
    "gate_tests.py": "tests.test_hooks.GateTests",
    "progress_guard.py": "tests.test_hooks.ProgressGuard",
    "handoff_guard.py": "tests.test_handoff.Hook",
    "pre_tool.py": "tests.test_hooks.PreTool",
    "stop_gate.py": "tests.test_hooks.StopGate",
    "session.py": "tests.test_hooks.Session",
}
REASON = {
    "2fa": "2FA ou código de verificação",
    "login": "login",
    "destructive": "ação destrutiva irreversível",
}
RECORDED = "fora da lista fechada; padrão conservador em docs/padroes/defaults.md; segue"


def _text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def classify(text):
    """Rótulo da lista fechada, ou None. 'não/sem/nunca' logo antes não conta."""
    blob = _text(text)
    for label, rx in CLOSED:
        for m in rx.finditer(blob):
            prefix = blob[max(0, m.start() - 24):m.start()]
            if _NEG.search(prefix):
                continue
            return label
    return None


def state_text(state):
    return _text(state)


def format_parei(motivo, proximo):
    motivo = " ".join((motivo or "").split()).replace("|", "/")
    proximo = " ".join((proximo or "").split()).replace("|", "/")
    if not motivo or not proximo:
        return None
    return "PAREI: %s | próximo: %s\n" % (motivo, proximo)


def parei_path(root):
    return os.path.join(root, PAREI_REL)


def write_parei(root, motivo, proximo):
    """Grava uma linha se o motivo está na lista fechada. Senão None e não para."""
    line = format_parei(motivo, proximo)
    motivo_only = " ".join((motivo or "").split()).replace("|", "/")
    if line is None or classify(motivo_only) is None:
        return None
    path = parei_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(line)
    unitmod.park(root)
    return line


def standing_tokens(root):
    """Itens de `stop.standing_ok`. Lista vazia se a chave não existe."""
    from . import config as cfgmod
    data, err = cfgmod.load(root)
    if err or not isinstance(data, dict):
        return []
    block = data.get("stop")
    if not isinstance(block, dict):
        return []
    raw = block.get("standing_ok")
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        if isinstance(item, str) and item.strip() and item.strip() not in out:
            out.append(item.strip())
    return out


def _first_span(blob):
    """(rótulo, trecho) do primeiro casamento da lista, ou (None, None)."""
    for label, rx in CLOSED:
        for match in rx.finditer(blob or ""):
            prefix = blob[max(0, match.start() - 24):match.start()]
            if _NEG.search(prefix):
                continue
            return label, blob[match.start():match.end()]
    return None, None


def standing_hit(root, motivo):
    """Token de standing_ok que cobre o casamento da lista, ou None."""
    _label, span = _first_span(" ".join((motivo or "").split()))
    if not span:
        return None
    for tok in standing_tokens(root):
        if re.search(r"(?i)(?<!\w)%s(?!\w)" % re.escape(tok), span):
            return tok
    return None


def write_ready(root, what):
    """Item coberto por standing_ok: não para; deixa a unidade pronta para publicar."""
    rec = unitmod.mark_ready(root)
    uid = rec.get("id") or "?"
    what = " ".join((what or "publicar").split()).replace("|", "/")
    if len(what) > 180:
        what = what[:179].rstrip() + "…"
    line = "READY-TO-PUBLISH: %s | %s\n" % (uid, what)
    path = os.path.join(root, ".hdev", "state", "ready-to-publish")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(line)
    return line


def write_wait(root, dependency, proximo):
    """Sem outra unidade: linha retomável dizendo o que a bloqueada espera."""
    line = format_parei("espera %s" % (dependency or "dependência"), proximo or "retomar")
    if line is None:
        return None
    path = parei_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(line)
    unitmod.park(root)
    return line


def read_parei(root):
    path = parei_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            raw = f.read().strip()
    except OSError:
        return None
    m = PAREI_LINE.match(raw)
    if not m:
        return None
    motivo, proximo = m.group("motivo").strip(), m.group("proximo").strip()
    kind = classify(motivo)
    if kind is None and not EXHAUSTED_RX.match(motivo) and not WAIT_RX.match(motivo):
        return None
    if not kind:
        kind = "exhausted" if EXHAUSTED_RX.match(motivo) else "espera"
    return {"motivo": motivo, "proximo": proximo, "line": raw, "kind": kind}


def clear_parei(root):
    try:
        os.remove(parei_path(root))
    except OSError:
        pass


def allows_stop(root, event=None):
    """True se já há PAREI (lista fechada ou gate esgotado) ou o evento traz a lista fechada."""
    event = event or {}
    if read_parei(root):
        return True
    bits = []
    for key in ("stop_reason", "reason"):
        val = event.get(key)
        if isinstance(val, str) and val.strip():
            bits.append(val)
    return classify("\n".join(bits)) is not None


def write_exhausted(root, guard, what):
    """Trava do Stop esgotada: grava PAREI em vez de liberar em silêncio."""
    guard = re.sub(r"[^A-Za-z0-9_-]", "", guard or "") or "gate"
    what = " ".join((what or "vermelho").split()).replace("|", "/") or "vermelho"
    if len(what) > 180:
        what = what[:179].rstrip() + "…"
    line = format_parei("gate esgotado (%s)" % guard, what)
    path = parei_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(line)
    unitmod.park(root)
    return line


def short_red(text):
    """Uma linha do que ficou vermelho, para o `próximo` do PAREI."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    pick = ""
    for ln in lines:
        if ln.startswith(("FAIL", "ERROR", "AssertionError")) or "FALHOU" in ln or "Error" in ln:
            pick = ln
            break
    if not pick and lines:
        pick = lines[-1]
    pick = " ".join(pick.split()).replace("|", "/")
    if len(pick) > 160:
        pick = pick[:159].rstrip() + "…"
    return pick or "vermelho"


def _label_file(label):
    parts = (label or "").split(".")
    if len(parts) < 2:
        return None
    return parts[0] + "/" + parts[1] + ".py"


def module_for(path):
    """Módulo de teste para um arquivo de hdev/ ou hooks/, ou o próprio teste."""
    path = (path or "").replace("\\", "/").split(" -> ")[-1].strip().lstrip("./")
    base = os.path.basename(path)
    if path.startswith("tests/test_") and path.endswith(".py"):
        return path[:-3].replace("/", ".")
    if path.startswith("hdev/") and base.endswith(".py") and base != "__init__.py":
        return "tests.test_" + base[:-3]
    if (path.startswith("hooks/") or path.startswith("harness/hooks/")) and base.endswith(".py") \
            and not base.startswith("_"):
        return HOOK_LABEL.get(base, "tests.test_hooks")
    return None


def smoke_modules(root):
    for rel in SMOKE_FILES:
        if os.path.isfile(os.path.join(root, rel)):
            return [rel[:-3].replace("/", ".")]
    return []


def affected_modules(root, paths):
    """Testes do diff em hdev/ e hooks/. Sem mapeamento, o smoke."""
    mods = []
    for path in paths or []:
        label = module_for(path)
        if not label:
            continue
        rel = _label_file(label)
        if rel and os.path.isfile(os.path.join(root, rel)) and label not in mods:
            mods.append(label)
    return mods or smoke_modules(root)


def is_suite_command(cmd):
    text = cmd if isinstance(cmd, str) else " ".join(str(p) for p in (cmd or []))
    return "unittest" in text and "discover" in text


def stop_argv(root, paths):
    mods = affected_modules(root, paths)
    if not mods:
        return None
    return [sys.executable, "-m", "unittest", "-q", *mods]


def changed_files(root):
    """Caminhos sujos (índice, árvore, não rastreados). None se não for um repo git."""
    try:
        r = subprocess.run(["git", "-C", root, "status", "--porcelain", "--untracked-files=all"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    paths = []
    for line in r.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].split(" -> ")[-1].strip().strip('"')
        if path.startswith((".hdev/state/", ".hdev/runs/", "logs/")):
            continue
        paths.append(path)
    return paths


def append_decision(root, text):
    """Uma linha curta em docs/decisions.md. A última igual não repete."""
    body = " ".join((text or "").split())
    if not body:
        return None
    if len(body) > DECISION_MAX:
        body = body[:DECISION_MAX - 1].rstrip() + "…"
    path = os.path.join(root, DECISIONS_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    prev = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            prev = f.read()
    last = ""
    for line in prev.splitlines():
        if line.startswith("- "):
            last = line
    if last.endswith(body):
        return path
    stamp = datetime.date.today().isoformat()
    with open(path, "a", encoding="utf-8") as f:
        if not prev:
            f.write("# Decisões\n\nAppend-only. O `docs/progress.md` guarda só o estado atual "
                    "(teto 2.000).\n\n")
        elif not prev.endswith("\n"):
            f.write("\n")
        f.write("- %s: %s\n" % (stamp, body))
    return path


def _queue_path(root):
    return os.path.join(root, QUEUE_REL)


def _events(root):
    path = _queue_path(root)
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict):
                out.append(item)
    return out


def pending_retries(root):
    """Pendentes na ordem de entrada. `done` tira a chave; um enqueue novo depois volta a valer."""
    state, order = {}, []
    for ev in _events(root):
        key = ev.get("key")
        if not key:
            continue
        if ev.get("op") == "enqueue":
            state[key] = ev
            if key not in order:
                order.append(key)
        elif ev.get("op") == "done":
            state.pop(key, None)
    return [state[k] for k in order if k in state]


def enqueue_retry(root, kind, detail, proximo):
    """Idempotente: a mesma chave pendente não duplica."""
    key = "%s|%s" % (kind, " ".join(str(detail).split())[:200])
    if any(item.get("key") == key for item in pending_retries(root)):
        return False
    rec = {"op": "enqueue", "key": key, "kind": kind, "detail": str(detail)[:300],
           "proximo": " ".join(str(proximo).split()), "ts": int(time.time())}
    path = _queue_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return True


def take_retry(root):
    items = pending_retries(root)
    if not items:
        return None
    item = items[0]
    path = _queue_path(root)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"op": "done", "key": item["key"], "ts": int(time.time())},
                           ensure_ascii=False) + "\n")
    return item


def judge_block_kind(output):
    """login/2FA na saída do juiz, ou quota. Destrutivo no pacote ecoado não conta."""
    kind = classify(output)
    if kind in ("2fa", "login"):
        return "login"
    if RATE_RX.search(output or ""):
        return "rate"
    return None


def note_judge_block(root, plan_rel, attempts):
    """Quota entra na fila; login/2FA grava PAREI. Pass ou fail não muda nada."""
    attempts = attempts or []
    if any(a.get("verdict") in ("pass", "fail") for a in attempts):
        return None
    kinds = [a.get("blocked") for a in attempts if a.get("blocked")]
    proximo = "hdev judge --plan %s --run-tests" % plan_rel
    if "login" in kinds:
        line = write_parei(root, "login no juiz", proximo)
        return {"acao": "parei", "parei": (line or "").strip(), "proximo": proximo}
    if "rate" in kinds:
        enqueue_retry(root, "judge-rate-limit", plan_rel, proximo)
        return {"acao": "retry", "proximo": proximo}
    return None


def resume(root, reason=None, proximo=None, blocked_on=None):
    """Com motivo: grava PAREI ou uma decisão. Sem motivo: devolve o próximo passo e consome.

    `--blocked-on` marca a unidade bloqueada. Com outra no backlog, não para.
    Sem outra, grava a espera e a sessão pode acabar.
    """
    if blocked_on:
        rec = unitmod.mark_blocked(root, blocked_on, proximo or "")
        others = unitmod.other_units(root, rec.get("id") or "")
        if others:
            return {"ok": True, "parou": False, "bloqueada": True,
                    "proximo": "pegue a próxima unidade do backlog", "outros": others}
        line = write_wait(root, blocked_on, proximo or "retomar")
        return {"ok": True, "parou": True, "bloqueada": True, "parei": (line or "").strip(),
                "proximo": proximo}
    if reason or proximo:
        if standing_hit(root, reason):
            line = write_ready(root, reason)
            return {"ok": True, "parou": False, "ready": (line or "").strip(), "proximo": proximo}
        line = write_parei(root, reason, proximo)
        if line:
            rec = read_parei(root)
            return {"ok": True, "parou": True, "parei": line.strip(),
                    "proximo": rec["proximo"] if rec else None}
        path = append_decision(root, "segue: %s" % " ".join((reason or "").split()))
        return {"ok": True, "parou": False,
                "decisao": os.path.relpath(path, root) if path else None, "proximo": None}
    rec = read_parei(root)
    if rec:
        clear_parei(root)
        unitmod.lift(root, rec["motivo"])
        return {"ok": True, "acao": "parei", "motivo": rec["motivo"], "proximo": rec["proximo"]}
    item = take_retry(root)
    if item:
        return {"ok": True, "acao": "retry", "kind": item.get("kind"), "proximo": item.get("proximo")}
    return {"ok": True, "acao": "nada", "proximo": None}


def main(args):
    root = os.path.realpath(args.root)
    reason = getattr(args, "reason", None) or ""
    proximo = getattr(args, "next_step", None) or ""
    blocked = getattr(args, "blocked_on", None) or ""
    if blocked:
        if reason or not proximo:
            print("hdev resume: --blocked-on pede --next e não leva --reason", file=sys.stderr)
            return 1
        payload = resume(root, blocked_on=blocked, proximo=proximo)
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    if bool(reason) ^ bool(proximo):
        print("hdev resume: --reason e --next vão juntos", file=sys.stderr)
        return 1
    payload = resume(root, reason or None, proximo or None)
    print(json.dumps(payload, ensure_ascii=False))
    return 0
