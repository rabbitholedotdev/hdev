"""Comum aos hooks do núcleo: evento, raiz do projeto, padrões de segredo e trava de laço.

Só stdlib. Nunca devolve nem imprime o valor de um segredo: só o tipo e a linha.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import time

# Padrões de segredo literal. O fonte não casa consigo mesmo (as classes [..] quebram o casamento).
SECRET_PATTERNS = [
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai-key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}")),
    ("private-key", re.compile("-----BEGIN" + r"[A-Z ]*PRIVATE KEY-----")),
    ("assigned-secret", re.compile(
        r"""(?i)\b(?:api[_-]?key|secret|token|passw(?:or)?d)["']?\s*[:=]\s*["']([^"'\s$<>{}]{16,})["']""")),
    # Sem aspas (`TOKEN=...` no shell ou no .env): só conta com cara de chave (ver _high_entropy).
    ("assigned-secret", re.compile(
        r"(?i)(?:^|[\s;&|(])[\w-]*(?:api[_-]?key|secret|token|passw(?:or)?d)[\w-]*\s*[:=]\s*"
        r"(?![/.~$])([\w+/=.-]{20,})(?=$|[\s;&|)])")),
]
_PLACEHOLDER = re.compile(r"(?i)^(?:op://|env:|vault:)|example|placeholder|changeme|dummy|fake|x{6,}|\*{4,}")
_HEX = re.compile(r"^[0-9a-fA-F]{32,}$")


def _high_entropy(value):
    """Valor sem aspas só é segredo se parecer chave: maiúscula+minúscula+dígito, hex longo ou muitos dígitos."""
    classes = sum(bool(re.search(rx, value)) for rx in ("[A-Z]", "[a-z]", "[0-9]"))
    return classes == 3 or bool(_HEX.match(value)) or (len(value) >= 32 and len(re.findall("[0-9]", value)) >= 6)

# Arquivos que só se citam pelo caminho.
SENSITIVE_PATH = re.compile(
    r"(?:^|/)(?:\.env(?:\.[\w.-]+)?|[\w.-]*chaves\.env|id_(?:rsa|dsa|ecdsa|ed25519)|[^/]*\.pem|[^/]*\.p12"
    r"|[^/]*\.key|credentials(?:\.json)?|\.netrc|\.npmrc|\.pypirc|\.git-credentials)$"
    r"|^/proc/(?:\d+|self|thread-self)/(?:task/\d+/)?environ$")
SAFE_SUFFIXES = (".example", ".sample", ".template", ".dist")


WRAPPERS = {"env", "command", "exec", "nohup", "time", "nice", "timeout", "stdbuf", "ionice", "builtin"}
# Opções que levam valor no token seguinte: o valor não é o comando (revisão Codex, rodada 10).
OPTS_WITH_VALUE = {
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "--class", "-n", "--classdata", "-p", "--pid"},
    "stdbuf": {"-i", "-o", "-e", "--input", "--output", "--error"},
    "time": {"-f", "--format", "-o", "--output"},
    "exec": {"-a"},
}


UNPARSED_ENV_S = "__unparsed_env_S__"


def _compose_chdir(prev, new):
    # Junta env -C em cadeia: env -C /var env -C tmp vira /var/tmp.
    if new is None or new == "":
        return prev
    expanded = os.path.expanduser(new)
    if os.path.isabs(expanded):
        return expanded
    if prev is None:
        return new
    return os.path.normpath(os.path.join(prev, new))


def _apply_env_S(toks, value):
    # Insere no comeco de toks o comando de env -S, ou um marcador se nao der para confiar.
    if "$(" in value or "`" in value or "${" in value:
        toks[:0] = [UNPARSED_ENV_S]
        return
    try:
        parts = shlex.split(value, posix=True)
    except ValueError:
        toks[:0] = [UNPARSED_ENV_S]
        return
    toks[:0] = parts


def wrapper_layers(toks):
    """Cada camada do comando sem os prefixos que so o embrulham, da de fora para a de dentro.

    Devolve [(tokens, chdir)]: o ultimo item e o comando real; chdir e o env -C DIR acumulado (ou None).
    Ex.: command env -u X cat .env. env -C /var env -C tmp rm ... acumula chdir /var/tmp. env -S expande a string.
    """
    toks, chdir, layers = list(toks), None, []
    while toks and re.match(r"^\w+=", toks[0]):
        toks.pop(0)
    while toks and os.path.basename(toks[0]) in WRAPPERS:
        layers.append((list(toks), chdir))
        head = os.path.basename(toks.pop(0))
        with_value = OPTS_WITH_VALUE.get(head, set())
        while toks:
            t = toks[0]
            if t in with_value:
                value = toks[1] if len(toks) > 1 else ""
                del toks[:2]
                if head == "env" and t in ("-C", "--chdir"):
                    chdir = _compose_chdir(chdir, value)
                elif head == "env" and t in ("-S", "--split-string"):
                    _apply_env_S(toks, value)
            elif head == "env" and (t.startswith("--chdir=") or (t.startswith("-C") and len(t) > 2)):
                value = t.split("=", 1)[1] if t.startswith("--chdir=") else t[2:]
                toks.pop(0)
                chdir = _compose_chdir(chdir, value)
            elif head == "env" and (t.startswith("--split-string=") or (t.startswith("-S") and len(t) > 2)):
                value = t.split("=", 1)[1] if t.startswith("--split-string=") else t[2:]
                toks.pop(0)
                _apply_env_S(toks, value)
            elif t.startswith("-") or re.match(r"^\w+=", t):
                toks.pop(0)
            else:
                break
        if head == "timeout" and toks and re.match(r"^\d+(?:\.\d+)?[smhd]?$", toks[0]):
            toks.pop(0)  # a duracao
    layers.append((toks, chdir))
    return layers


def strip_wrappers(toks):
    """Tira `VAR=x` e prefixos que só embrulham o comando real (env, nohup, timeout 5, nice -n 10...)."""
    return wrapper_layers(toks)[-1][0]


def find_secrets(text):
    """Lista de (tipo, linha) para cada segredo literal achado. Nunca o valor."""
    found = []
    for kind, lineno, _ in _secret_spans(text):
        if (kind, lineno) not in found:
            found.append((kind, lineno))
    return found


def _secret_spans(text):
    """(tipo, linha, (início, fim) no texto) de cada ocorrência de segredo."""
    found, offset = [], 0
    for lineno, line in enumerate(text.splitlines(True), 1):
        for kind, rx in SECRET_PATTERNS:
            for m in rx.finditer(line):
                value = m.group(1) if m.groups() else m.group(0)
                if kind == "assigned-secret" and _PLACEHOLDER.search(value):
                    continue
                if kind == "assigned-secret" and not m.group(0).rstrip().endswith(("'", '"')) \
                        and not _high_entropy(value):
                    continue
                span = m.span(1) if m.groups() else m.span(0)
                found.append((kind, lineno, (offset + span[0], offset + span[1])))
        offset += len(line)
    return found


def redact(text):
    """Texto com cada segredo literal trocado por [segredo omitido: tipo]."""
    spans = sorted(((s, e, kind) for kind, _, (s, e) in _secret_spans(text)), reverse=True)
    out, last = text, None
    for s, e, kind in spans:
        if last is not None and e > last:  # sobreposto ao já trocado
            continue
        out = out[:s] + "[segredo omitido: %s]" % kind + out[e:]
        last = s
    return out


def is_sensitive_path(path):
    p = path.strip().strip("'\"")
    if not p or p.endswith(SAFE_SUFFIXES):
        return False
    return bool(SENSITIVE_PATH.search(p))


def read_event():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}
    return data if isinstance(data, dict) else {}


def project_root(event):
    root = os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()
    return os.path.realpath(root)


def load_config(root):
    try:
        with open(os.path.join(root, ".hdev", "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def block(reason):
    """Exit 2: o Claude Code bloqueia a ação e mostra o motivo ao modelo."""
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)


def git(root, *args, timeout=30):
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _state_path(root, name):
    return os.path.join(root, ".hdev", "state", name + ".json")


def loop_guard_exceeded(root, name, session_id, limit=3):
    """Conta bloqueios seguidos de um Stop hook na sessão. True quando passou do limite (aí libera)."""
    path = _state_path(root, name)
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        state = {}
    count = state.get("count", 0) + 1 if state.get("session") == session_id else 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"session": session_id, "count": count, "ts": time.time()}, f)
    return count > limit


def loop_guard_reset(root, name):
    try:
        os.remove(_state_path(root, name))
    except OSError:
        pass


def nested():
    """Agente aninhado (revisor via hdev grok-review/codex-exec, ADR 0007): os hooks de sessão do orquestrador se calam."""
    return os.environ.get("HDEV_NESTED") == "1"


def closed_stop(root, event=None):
    """True se a parada está na lista fechada (arquivo PAREI ou stop_reason do evento)."""
    pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if pkg not in sys.path:
        sys.path.insert(0, pkg)
    from hdev.stop import allows_stop
    return allows_stop(root, event or {})


def record_metric(root, entry):
    """Observabilidade: uma linha JSON por medida em .hdev/state/metrics.jsonl."""
    try:
        path = os.path.join(root, ".hdev", "state", "metrics.jsonl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": round(time.time(), 3), **entry}) + "\n")
    except OSError:
        pass


def norm_command(command):
    return " ".join((command or "").split())


def norm_path(path):
    return os.path.normpath(str(path).strip()).replace("\\", "/")


def _fail_path(root):
    return os.path.join(root, ".hdev", "state", "cmd-fail.json")


def command_fail_count(root, session_id, command):
    """Falhas seguidas deste comando nesta sessão. Outro comando ou outra sessão não conta."""
    try:
        with open(_fail_path(root), encoding="utf-8") as f:
            state = json.load(f)
    except (OSError, ValueError):
        return 0
    if not isinstance(state, dict):
        return 0
    if state.get("session") != (session_id or "") or state.get("command") != norm_command(command):
        return 0
    try:
        return int(state.get("count") or 0)
    except (TypeError, ValueError):
        return 0


def record_command_result(root, session_id, command, failed):
    """Conta falha seguida, ou zera quando o mesmo comando passa."""
    command = norm_command(command)
    if not command:
        return 0
    session_id = session_id or ""
    count = command_fail_count(root, session_id, command)
    count = count + 1 if failed else 0
    path = _fail_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"session": session_id, "command": command, "count": count}, f)
    return count


# Colisão: outra sessão mexeu no mesmo arquivo há menos de 30 min (ADR 0012).
TOUCH_WINDOW = 30 * 60


def record_touch(root, session_id, paths, unit=""):
    folder = os.path.join(root, ".hdev", "state")
    os.makedirs(folder, exist_ok=True)
    now = time.time()
    session_id = session_id or ""
    with open(os.path.join(folder, "touches.jsonl"), "a", encoding="utf-8") as f:
        for raw in paths:
            if not isinstance(raw, str) or not raw.strip():
                continue
            f.write(json.dumps({
                "session": session_id, "path": norm_path(raw), "ts": now, "unit": unit or "",
            }, ensure_ascii=False) + "\n")


def other_touch(root, paths, session_id, now=None, window=TOUCH_WINDOW):
    """Toque mais recente de outra sessão no mesmo caminho, dentro da janela. Ou None."""
    now = time.time() if now is None else now
    wanted = {norm_path(p) for p in paths if isinstance(p, str) and p.strip()}
    if not wanted:
        return None
    try:
        with open(os.path.join(root, ".hdev", "state", "touches.jsonl"), encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return None
    session_id = session_id or ""
    best = None
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict) or rec.get("session") == session_id:
            continue
        if norm_path(rec.get("path") or "") not in wanted:
            continue
        try:
            ts = float(rec.get("ts"))
        except (TypeError, ValueError):
            continue
        age = now - ts
        if age < 0 or age >= window:
            continue
        if best is None or ts > best["ts"]:
            best = {"session": rec.get("session") or "", "path": norm_path(rec.get("path") or ""),
                    "ts": ts, "unit": rec.get("unit") or ""}
    return best


# Etiqueta do app da Ratoeira: o chat põe `<ratoeira-contexto>` no começo do prompt quando a conversa está ligada a um
# app ("ligada", só na 1ª mensagem; vale a sessão toda) ou quando a mensagem marca o app ("marcado", vale o turno).
# Com a etiqueta de um app deste repo, a conversa é de uso do app: o pre_tool barra escrita em código.
CHIP_BLOCK = re.compile(r"<ratoeira-contexto>\n?([\s\S]*?)\n?</ratoeira-contexto>")
CHIP_WRAPPED = re.compile(r"<ratoeira-(copia|troca|conversa)\b[^>]*>[\s\S]*?</ratoeira-\1>")
CHIP_LINKED = re.compile(r"^Esta conversa está ligada ao (.+?): as ferramentas MCP", re.M)
CHIP_MARKED = re.compile(r"^App marcado na mensagem: (.+?) \(", re.M)


def chip_in_prompt(prompt):
    """(ligados, marcados) da etiqueta no prompt. Contexto copiado ou vindo de outra conversa não conta."""
    m = CHIP_BLOCK.search(CHIP_WRAPPED.sub("", prompt if isinstance(prompt, str) else ""))
    if not m:
        return [], []
    return CHIP_LINKED.findall(m.group(1)), CHIP_MARKED.findall(m.group(1))


def repo_apps(root):
    """Nomes (minúsculos) dos apps da Ratoeira deste repo: `titulo` e `nome` do ratoeira-app.json na raiz ou um nível abaixo."""
    names = set()
    try:
        dirs = [root] + [os.path.join(root, n) for n in sorted(os.listdir(root))]
    except OSError:
        return names
    for d in dirs:
        try:
            with open(os.path.join(d, "ratoeira-app.json"), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        for key in ("titulo", "nome"):
            if isinstance(data, dict) and isinstance(data.get(key), str) and data[key].strip():
                names.add(data[key].strip().lower())
    return names


def _load_chip(root):
    try:
        with open(_state_path(root, "chip"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def record_chip(root, session_id, prompt):
    """UserPromptSubmit: guarda o app da etiqueta desta sessão (ligado soma; marcado troca a cada prompt)."""
    linked, marked = chip_in_prompt(prompt)
    state = _load_chip(root)
    if not linked and not marked and session_id not in state:
        return
    mine = repo_apps(root)
    entry = state.get(session_id) if isinstance(state.get(session_id), dict) else {}
    keep_linked = sorted(set(entry.get("linked") or []) | {a for a in linked if a.strip().lower() in mine})
    keep_marked = sorted({a for a in marked if a.strip().lower() in mine})
    if keep_linked or keep_marked:
        state[session_id] = {"linked": keep_linked, "marked": keep_marked, "ts": time.time()}
    else:
        state.pop(session_id, None)
    recent = sorted(state.items(), key=lambda kv: (kv[1] or {}).get("ts", 0) if isinstance(kv[1], dict) else 0)[-20:]
    path = _state_path(root, "chip")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(recent), f, ensure_ascii=False)


def chip_app(root, session_id):
    """App da etiqueta desta sessão (ligado na conversa ou marcado no último prompt), ou None."""
    entry = _load_chip(root).get(session_id)
    if not isinstance(entry, dict):
        return None
    names = list(entry.get("linked") or []) + list(entry.get("marked") or [])
    return names[0] if names else None


def worktrees(root):
    """Raiz e worktrees do mesmo repo (caminhos reais)."""
    out = git(root, "worktree", "list", "--porcelain") or ""
    paths = {os.path.realpath(line[9:]) for line in out.splitlines() if line.startswith("worktree ")}
    return sorted(paths | {os.path.realpath(root)})
