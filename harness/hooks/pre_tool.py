#!/usr/bin/env python3
"""PreToolUse: segredo, destrutivo, etiqueta do app, pergunta na execução, falha seguida e colisão.

Dois registros no manifesto chamam este arquivo (Bash, e o resto das ferramentas de edição).
`hooks/secret_guard.py` e `hooks/destructive_guard.py` delegam para `secret_main` e `destructive_main`.
"""
import json
import os
import re
import shlex
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_ROOT, os.path.join(_ROOT, "hooks")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import _lib  # noqa: E402

READERS = {"cat", "less", "more", "head", "tail", "bat", "batcat", "strings", "grep", "rg", "egrep", "fgrep",
           "sed", "awk", "xxd", "od", "hexdump", "base64", "source", ".", "cp", "scp", "rsync", "nl", "tac",
           "sort", "uniq", "cut", "diff", "vim", "vi", "nano", "jq", "python", "python3", "node", "openssl"}
SECRET_SPLIT = re.compile(r"\|\||&&|[|;&\n]|\$\(|`|\(|\)")

GIT = r"\bgit\b(?:\s+-(?:C|c)\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+"
RULES = [
    ("sudo", re.compile(r"(?:^|[;&|(`]|\$\()\s*sudo\b|\s+sudo\s")),
    ("git push (remoto só com o João)", re.compile(GIT + r"push\b")),
    ("git reset --hard", re.compile(GIT + r"reset\b[^;&|]*--hard")),
    ("git clean -f", re.compile(GIT + r"clean\b[^;&|]*\s-\w*f")),
    ("git checkout/restore que descarta mudanças", re.compile(GIT + r"(?:checkout|restore)\b[^;&|]*\s(?:--\s+)?\.(?:\s|$)")),
    ("git branch -D", re.compile(GIT + r"branch\b[^;&|]*\s-D\b")),
    ("git filter-branch/filter-repo", re.compile(GIT + r"filter-(?:branch|repo)\b")),
    ("mkfs", re.compile(r"\bmkfs(?:\.\w+)?\b")),
    ("dd em dispositivo", re.compile(r"\bdd\b[^;&|]*\bof=/dev/")),
    ("escrita direta em disco", re.compile(r">\s*/dev/(?:sd|nvme|vd|xvd|hd|mmcblk)")),
    ("fork bomb", re.compile(r":\(\)\s*\{")),
    ("chmod/chown recursivo na raiz ou na home", re.compile(r"\bch(?:mod|own)\b\s+(?:-\w*R\w*|--recursive)\b.*\s(?:/|~|\$HOME)/?(?:\s|$)")),
    ("curl/wget direto no shell", re.compile(r"\b(?:curl|wget)\b[^|;&]*\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b")),
    ("DROP de banco", re.compile(r"(?i)\bdrop\s+(?:table|database|schema)\b")),
    ("desligar/reiniciar a máquina", re.compile(r"(?:^|[;&|]\s*)(?:shutdown|reboot|poweroff|halt)\b")),
    ("systemctl que para serviço", re.compile(r"\bsystemctl\b[^;&|]*\b(?:stop|disable|mask|restart|kill)\b")),
    ("firewall", re.compile(r"(?:^|[;&|]\s*)(?:ufw|iptables|ip6tables|nft|firewall-cmd)\b")),
    ("docker prune", re.compile(r"\bdocker\b[^;&|]*\b(?:system|volume|image)\s+prune\b")),
    ("crontab -r", re.compile(r"\bcrontab\b[^;&|]*\s-r\b")),
]
SEGMENT_SPLIT = re.compile(r"(\|\||&&|[|;&\n]|\$\(|`|\(|\))")
OPENS, CLOSE = ("(", "$("), ")"
DANGER_TARGETS = {"/", "/*", "~", "~/", "~/*", "$HOME", "$HOME/", "${HOME}", "..", "../", "../*", "*", ".", "./", "./*",
                  ".git", "./.git"}
ASK_REASON = (
    "pre_tool: AskUserQuestion na execução. Não pergunte. Escolha o padrão em "
    "docs/padroes/defaults.md, anote em docs/decisions.md e siga. Parada só em "
    "harness/prompts/_shared/stop-list.md."
)


def _secret_tokens(segment):
    try:
        return shlex.split(segment, comments=False, posix=True)
    except ValueError:
        return segment.split()


def env_dump(toks):
    """Comando que despeja o ambiente: printenv, env sem comando (`env -0`, `env -u X`), export -p, declare -x."""
    head = os.path.basename(toks[0])
    if head == "printenv":
        return "despejo do ambiente (`printenv`)"
    if head == "env":
        rest, i = toks[1:], 0
        while i < len(rest):
            if rest[i] in ("-u", "--unset", "-C", "--chdir", "-S", "--split-string"):
                i += 2
            elif rest[i].startswith("-") or re.match(r"^\w+=", rest[i]):
                i += 1
            else:
                return None
        return "despejo do ambiente (`%s`)" % " ".join(toks)
    if head == "export" and all(t == "-p" for t in toks[1:]):
        return "despejo do ambiente (`export`)"
    if head in ("declare", "typeset") and toks[1:] and all(re.match(r"^-[pxr]+$", t) for t in toks[1:]):
        return "despejo do ambiente (`%s`)" % " ".join(toks)
    return None


def bash_reads_secret(command):
    for segment in SECRET_SPLIT.split(command):
        toks = _secret_tokens(segment)
        if not toks:
            continue
        layers = _lib.wrapper_layers(toks)
        for layer, _ in layers:
            if layer and layer[0] == _lib.UNPARSED_ENV_S:
                return "env -S não interpretado"
            why = env_dump(layer) if layer else None
            if why:
                return why
        toks = layers[-1][0]
        if not toks:
            continue
        cmd = os.path.basename(toks[0])
        args = toks[1:]
        if cmd == "printenv":
            return "despejo do ambiente (`printenv`)"
        for j, tok in enumerate(args):
            if tok.startswith("<"):
                tok = tok[1:]
            prev = args[j - 1] if j else ""
            if _lib.is_sensitive_path(tok) and (cmd in READERS or prev == "<" or tok != args[j]):
                return "leitura de arquivo sensível: %s" % tok
        if re.search(r"<\s*\S+", segment):
            for m in re.finditer(r"<\s*([^\s<>|;&]+)", segment):
                if _lib.is_sensitive_path(m.group(1)):
                    return "leitura de arquivo sensível: %s" % m.group(1)
    return None


def texts_for(tool, inp):
    if tool == "Write":
        return [inp.get("content", "")]
    if tool == "Edit":
        return [inp.get("new_string", "")]
    if tool == "MultiEdit":
        return [e.get("new_string", "") for e in inp.get("edits", []) if isinstance(e, dict)]
    if tool == "Bash":
        return [inp.get("command", "")]
    return []


def secret_main(event=None):
    if event is None:
        event = _lib.read_event()
    tool = event.get("tool_name", "")
    inp = event.get("tool_input") or {}
    if not isinstance(inp, dict):
        return 0
    if tool == "Read" and _lib.is_sensitive_path(inp.get("file_path", "")):
        _lib.block("secret_guard: %s é arquivo sensível. Cite só o caminho; para usar a chave, "
                   "leia por referência (ex.: $(op read op://Vault/item/credential)) sem imprimir." % inp.get("file_path"))
    if tool == "Bash":
        why = bash_reads_secret(inp.get("command", ""))
        if why:
            _lib.block("secret_guard: %s. Segredo só por referência; não imprima o conteúdo." % why)
    for text in texts_for(tool, inp):
        if not isinstance(text, str):
            continue
        hits = _lib.find_secrets(text)
        if hits:
            desc = ", ".join("%s (linha %d)" % h for h in hits[:5])
            _lib.block("secret_guard: segredo literal detectado em %s: %s. Troque por referência "
                       "(op://..., nome de variável de ambiente)." % (tool, desc))
    return 0


def _tokens(segment):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def _inside(path, root):
    return path.startswith(root + os.sep)


def _resolve(cwd, target):
    expanded = os.path.expanduser(os.path.expandvars(target))
    if not os.path.isabs(expanded) and cwd is None:
        return None
    return os.path.realpath(os.path.join(cwd or "/", expanded))


def _next_cwd(toks, cwd):
    args = [t for t in toks[1:] if not t.startswith("-") or t == "-"]
    if not args:
        return os.path.realpath(os.path.expanduser("~"))
    if args[0] == "-" or "$(" in args[0] or "`" in args[0]:
        return None
    return _resolve(cwd, args[0])


def _protected(full, root):
    git_dir = os.path.join(root, ".git")
    return full == git_dir or _inside(full, git_dir)


def _segments(command):
    parts = SEGMENT_SPLIT.split(command)
    return [(parts[i], parts[i + 1] if i + 1 < len(parts) else "") for i in range(0, len(parts), 2)]


def rm_problem(command, root, cwd):
    stack = []
    for segment, sep in _segments(command):
        problem, cwd = _segment_problem(segment, sep, root, cwd)
        if problem:
            return problem
        if sep in OPENS:
            stack.append(cwd)
        elif sep == CLOSE and stack:
            cwd = stack.pop()
    return None


def _segment_problem(segment, sep, root, cwd):
    toks = [t for t in _tokens(segment) if t not in ("{", "}")]
    toks, chdir = _lib.wrapper_layers(toks)[-1]
    if toks and toks[0] == _lib.UNPARSED_ENV_S:
        return "env -S não interpretado", cwd
    if toks and os.path.basename(toks[0]) in ("cd", "pushd"):
        if sep in ("$(", "`"):
            return None, None
        return None, _next_cwd(toks, cwd)
    run_cwd = cwd
    if chdir is not None:
        run_cwd = None if "$(" in chdir or "`" in chdir else _resolve(cwd, chdir)
    return _rm_targets_problem(toks, root, run_cwd), cwd


def _rm_targets_problem(toks, root, cwd):
    if not toks or os.path.basename(toks[0]) not in ("rm", "rmdir", "shred", "unlink", "find"):
        return None
    name = os.path.basename(toks[0])
    if name == "find":
        if not ("-delete" in toks or ("-exec" in toks and "rm" in toks)):
            return None
        targets = [t for t in toks[1:] if not t.startswith("-")][:1] or ["."]
    else:
        flags = "".join(t[1:] for t in toks[1:] if t.startswith("-") and not t.startswith("--"))
        long_flags = [t for t in toks[1:] if t.startswith("--")]
        recursive = "r" in flags.lower() or "--recursive" in long_flags or name == "shred"
        targets = [t for t in toks[1:] if not t.startswith("-")]
        if not recursive:
            for t in targets:
                full = _resolve(cwd, t)
                if full is None:
                    return "rm com diretório incerto depois de cd: %s" % t
                if _protected(full, root):
                    return "rm no .git desligaria o checkout"
                if not _inside(full, root):
                    return "rm fora do repo: %s" % t
            return None
    strict = name != "find"
    for t in targets:
        if strict and (t in DANGER_TARGETS or t.rstrip("/") in DANGER_TARGETS):
            return "%s recursivo em alvo perigoso: %s" % (name, t)
        full = _resolve(cwd, t)
        if full is None:
            return "%s com diretório incerto depois de cd: %s" % (name, t)
        if full == root and strict:
            return "%s apagaria o repo inteiro" % name
        if _protected(full, root):
            return "%s no .git apagaria o histórico" % name
        if full != root and not _inside(full, root):
            return "%s recursivo fora do repo: %s" % (name, t)
    return None


def check(command, root, cwd):
    for label, rx in RULES:
        if rx.search(command):
            return label
    return rm_problem(command, root, cwd)


def destructive_main(event=None):
    if event is None:
        event = _lib.read_event()
    if event.get("tool_name") != "Bash":
        return 0
    command = (event.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        return 0
    root = _lib.project_root(event)
    cwd = os.path.realpath(event.get("cwd") or root)
    why = check(command, root, cwd)
    if why:
        _lib.block("destructive_guard: bloqueado (%s). Se for 2FA/login ou ação irreversível, pare com "
                   "`hdev resume --reason \"<motivo>\" --next \"<passo>\"`. Senão escolha outro caminho." % why)
    return 0


def _session_id(event):
    return event.get("session_id") or event.get("sessionId") or ""


def _edit_paths(event):
    if event.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
        return []
    inp = event.get("tool_input") or {}
    if not isinstance(inp, dict):
        return []
    paths = []
    for key in ("file_path", "path"):
        if isinstance(inp.get(key), str) and inp.get(key).strip():
            paths.append(inp[key])
    return paths


def loop_reason(event):
    if event.get("tool_name") != "Bash":
        return None
    command = (event.get("tool_input") or {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        return None
    root = _lib.project_root(event)
    count = _lib.command_fail_count(root, _session_id(event), command)
    if count < 2:
        return None
    short = _lib.norm_command(command)
    if len(short) > 120:
        short = short[:119].rstrip() + "…"
    return ("pre_tool: comando já falhou %d vezes seguidas (%s). "
            "Segure: diagnostique antes de repetir." % (count, short))


def collision_reason(event, now=None):
    paths = _edit_paths(event)
    if not paths:
        return None
    root = _lib.project_root(event)
    hit = _lib.other_touch(root, paths, _session_id(event), now=now)
    if not hit:
        return None
    age_min = int((time_now(now) - hit["ts"]) / 60)
    unit = hit.get("unit") or "—"
    return ("pre_tool: colisão: %s foi mexido pela sessão %s há %d min "
            "(unidade %s, outra sessão da Ratoeira)." % (hit["path"], hit["session"], age_min, unit))


CHIP_REASON = ("pre_tool: conversa com a etiqueta do app %s: use as ferramentas do %s; para mudar código (%s), "
               "abra sem a etiqueta na pasta do repo.")
CHIP_TOOLS = {"Write": ("file_path",), "Edit": ("file_path",), "MultiEdit": ("file_path",),
              "NotebookEdit": ("notebook_path",)}
WRITE_ALL = {"rm", "rmdir", "touch", "mkdir", "truncate", "tee", "unlink", "shred", "chmod", "chown"}
WRITE_DEST = {"cp", "mv", "install", "ln", "rsync"}
WRITE_INPLACE = {"sed", "perl"}
GIT_WRITES = {"add", "commit", "apply", "am", "merge", "rebase", "checkout", "switch", "restore", "reset", "stash",
              "cherry-pick", "revert", "rm", "mv", "push", "pull", "clean"}
REDIRECT = re.compile(r"\d?>>?\|?\s*([^\s;&|<>()]+)")
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
MASK = str.maketrans("()|;&`\n", "\x10\x11\x12\x13\x14\x15\x16")
UNMASK = {v: k for k, v in MASK.items()}
HEREDOC = re.compile(r"(?<!<)<<(?!<)-?[ \t]*(['\"]?)([\w.-]+)\1")
INTERP = re.compile(r"(python|node|perl|ruby|bash|sh|zsh|dash)(?:js|[\d.]+)?$")
INLINE = {"python": "c", "node": "ep", "perl": "eE", "ruby": "e", "bash": "c", "sh": "c", "zsh": "c", "dash": "c"}
SHELLS = {"bash", "sh", "zsh", "dash"}
_MODE = r"""(?:mode\s*=\s*)?['"][rbtU]*[wax+][rbtU+]*['"]"""
# shortcut: não vê escrita por subprocess/os.system nem por script em arquivo; amplie se aparecer na prática.
WRITE_CODE = re.compile("|".join((
    r"\bopen\s*\(.*?,\s*" + _MODE,                                  # open(p, 'w'), File.open(p, 'a')
    r"\.open\s*\(\s*" + _MODE,                                      # Path(p).open('w')
    r"""\bopen\b[^;]*?['"]\s*(?:>|\+<)""",                          # perl: open(F, '>', p), open F, ">p"
    r"\.write_(?:text|bytes)\s*\(|\.touch\s*\(",
    r"\bos\.(?:remove|replace|removedirs)\s*\(",
    r"\bshutil\.(?!which\b|disk_usage\b|get_terminal_size\b)\w+",
    r"\b(?:writeFile|appendFile|unlink|rmdir|rename|copyFile|mkdir|makedirs|truncate|symlink)(?:Sync)?\s*\(",
    r"\b(?:rm|cp|write)Sync\s*\(|\bcreateWriteStream\b|\bfs\.(?:promises\.)?write\s*\(",
    r"\b(?:File|IO)\.(?:write|binwrite|delete)\b|\bFileUtils\.\w+",
    r"""\b(?:unlink|rename|rmdir|mkdir)\s+[$"']""",                 # perl sem parênteses
)))


def _code(full, trees):
    """Caminho dentro do repo (raiz ou worktree), fora do estado `.hdev/`."""
    if ".hdev" in full.split(os.sep):
        return False
    return any(full == t or _inside(full, t) for t in trees)


def _written(segment, toks):
    """Alvos de escrita de um trecho do shell. A escrita por interpretador fica em `_interp_write`."""
    out = [t for t in REDIRECT.findall(QUOTED.sub("''", segment)) if t]
    if not toks:
        return out
    name = os.path.basename(toks[0])
    args = [t for t in toks[1:] if not t.startswith("-")]
    if name in WRITE_ALL:
        out += args
    elif name in WRITE_DEST and args:
        out.append(args[-1])
    elif name in WRITE_INPLACE and any(t == "--in-place" or (t[:1] == "-" and t[1:2] != "-" and "i" in t)
                                       for t in toks[1:]):
        out += args[1:]
    elif name == "git" and GIT_WRITES & set(toks[1:]):
        out.append(".")
    return out


def _quote_safe(command):
    """Separadores entre aspas não cortam o trecho (`python3 -c "print(a > b)"`); "$(...)" segue cortando."""
    def mask(m):
        s = m.group(0)
        return s if s[0] == '"' and ("$(" in s or "`" in s) else s.translate(MASK)
    return QUOTED.sub(mask, command)


def _heredocs(command):
    """(comando sem o corpo dos heredocs, [corpos]): o corpo não é shell, a não ser que vá para um shell."""
    out, bodies = "", []
    while True:
        m = HEREDOC.search(command)
        nl = command.find("\n", m.end()) if m else -1
        if nl < 0:
            return out + command, bodies
        end = re.compile(r"^[ \t]*%s[ \t]*$" % re.escape(m.group(2)), re.M).search(command, nl + 1)
        bodies.append(command[nl + 1:end.start() if end else len(command)])
        out, command = out + command[:nl + 1], command[end.end():] if end else ""


def _interp_write(toks, command, bodies, trees, cwd):
    """Escrita por interpretador: código inline (-c/-e) ou script pelo stdin/heredoc. O alvo não é resolvido."""
    m = INTERP.match(os.path.basename(toks[0])) if toks else None
    if not m:
        return None
    kind, args, codes = m.group(1), toks[1:], []
    for i, t in enumerate(args):
        if kind == "node" and t.startswith(("--eval=", "--print=")):
            codes.append(t.split("=", 1)[1])
        elif (kind == "node" and t in ("--eval", "--print")) or (
                re.match(r"^-[A-Za-z]+$", t) and set(t[1:]) & set(INLINE[kind])):
            codes.append(args[i + 1] if i + 1 < len(args) else "")
    script = next((t for t in args if not t.startswith("-") or t == "-"), "-")
    stdin = not codes and (script == "-" or script.startswith("<"))
    if kind in SHELLS:
        return next(filter(None, (chip_write_target(c, trees, cwd) for c in (bodies if stdin else codes))), None)
    if stdin:
        codes = [command]
    return "escrita por %s" % os.path.basename(toks[0]) if any(WRITE_CODE.search(c) for c in codes) else None


def chip_write_target(command, trees, cwd):
    """Primeiro alvo de escrita em código no comando, ou None. cwd desconhecido conta como a raiz."""
    stack = []
    shell, bodies = _heredocs(command)
    for segment, sep in _segments(_quote_safe(shell)):
        segment = segment.translate(UNMASK)
        toks = [t for t in _tokens(segment) if t not in ("{", "}")]
        toks, chdir = _lib.wrapper_layers(toks)[-1]
        if toks and os.path.basename(toks[0]) in ("cd", "pushd") and sep not in ("$(", "`"):
            cwd = _next_cwd(toks, cwd)
        else:
            run_cwd = cwd if chdir is None else (None if "$(" in chdir or "`" in chdir else _resolve(cwd, chdir))
            for target in _written(segment, toks):
                full = _resolve(run_cwd or trees[0], target)
                if full and _code(full, trees):
                    return target
            hit = _interp_write(toks, command, bodies, trees, run_cwd)
            if hit:
                return hit
        if sep in OPENS:
            stack.append(cwd)
        elif sep == CLOSE and stack:
            cwd = stack.pop()
    return None


def chip_reason(event):
    """Etiqueta de um app deste repo na conversa: escrita em código vira bloqueio; leitura passa."""
    tool = event.get("tool_name")
    if tool not in CHIP_TOOLS and tool != "Bash":
        return None
    root = _lib.project_root(event)
    app = _lib.chip_app(root, _session_id(event))
    if not app:
        return None
    inp = event.get("tool_input") or {}
    if not isinstance(inp, dict):
        return None
    trees = _lib.worktrees(root)
    cwd = os.path.realpath(event.get("cwd") or root)
    if tool == "Bash":
        command = inp.get("command", "")
        hit = chip_write_target(command, trees, cwd) if isinstance(command, str) else None
    else:
        hit = next((p for p in (inp.get(k) for k in CHIP_TOOLS[tool])
                    if isinstance(p, str) and p.strip() and _code(_resolve(cwd, p), trees)), None)
    return CHIP_REASON % (app, app, hit) if hit else None


def time_now(now):
    import time
    return time.time() if now is None else now


def _warn(event, text):
    sys.stderr.write(text + "\n")
    ev = event.get("hook_event_name") or event.get("hookEventName") or "PreToolUse"
    sys.stdout.write(json.dumps({"hookSpecificOutput": {
        "hookEventName": ev, "additionalContext": text,
    }}, ensure_ascii=False) + "\n")


def main():
    event = _lib.read_event()
    if event.get("tool_name") == "AskUserQuestion" and os.environ.get("HDEV_PHASE") == "exec":
        _lib.block(ASK_REASON)
    secret_main(event)
    destructive_main(event)
    chip = chip_reason(event)
    if chip:
        _lib.block(chip)
    held = loop_reason(event)
    if held:
        _lib.block(held)
    warn = collision_reason(event)
    if warn:
        _warn(event, warn)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
