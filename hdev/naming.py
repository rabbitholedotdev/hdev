"""Checagem `names` do hdev check: nomes novos de desenvolvimento em inglês (F2-10, docs/padroes/naming.md)."""
import fnmatch
import json
import os
import re
import subprocess

PT_WORDS = (
    "arquivo arquivos banco cliente clientes conta contas conteudo criar dados documento documentos empresa enviar "
    "equipe espaco espacos ferramenta ferramentas imagem imagens modelo modelos nome nomes nova novo acao acoes "
    "botao botoes padrao padroes sessao sessoes pagina paginas painel pasta pastas pedido pedidos plano planos "
    "preco precos produto produtos projeto projetos publicar rascunho relatorio relatorios rotina rotinas salvar "
    "servico servicos tarefa tarefas tela telas teste testes unidade usuario usuarios"
).split()
DEFAULT_MODE = "fail"
DEFAULT_ALLOW = ["unidade"]
MODES = ("warn", "fail", "off")
TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


class GitError(Exception):
    pass


def _git(root, name, *args, ok=(0,)):
    """(rc, saída em texto UTF-8 com surrogateescape); rc fora de `ok` ou falha ao rodar: GitError(name)."""
    try:
        r = subprocess.run(["git", "-C", root, "-c", "core.quotePath=false", name, *args], capture_output=True,
                           timeout=60)
    except (OSError, subprocess.SubprocessError):
        raise GitError(name)
    if r.returncode not in ok:
        raise GitError(name)
    return r.returncode, r.stdout.decode("utf-8", errors="surrogateescape")


def _load_config(root, notes):
    mode, allow_words, allow_paths = DEFAULT_MODE, list(DEFAULT_ALLOW), []
    path = os.path.join(root, ".hdev", "config.json")
    if not os.path.exists(path):
        return mode, allow_words, allow_paths
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        if not isinstance(cfg, dict):
            raise ValueError
    except (OSError, ValueError):
        notes.append("config inválida, usando padrão")
        return mode, allow_words, allow_paths
    if "naming" not in cfg:
        return mode, allow_words, allow_paths
    naming = cfg["naming"]
    if not isinstance(naming, dict):
        notes.append("config naming inválida, usando padrão")
        return mode, allow_words, allow_paths
    if "mode" in naming:
        m = naming["mode"]
        if isinstance(m, str) and m in MODES:
            mode = m
        else:
            mode = "warn"
            notes.append("modo desconhecido '%s', usando warn" % m)
    for key, target, lower in (("allow_words", allow_words, True), ("allow_paths", allow_paths, False)):
        value = naming.get(key)
        if isinstance(value, list):
            target.extend((v.lower() if lower else v) for v in value if isinstance(v, str))
    return mode, allow_words, allow_paths


def _read_bases(root):
    """(entradas {id: dict}, inválido). Ausente: ({}, False)."""
    path = os.path.join(root, ".hdev", "state", "bases.json")
    if not os.path.isfile(path):
        return {}, False
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}, True
    return (data, False) if isinstance(data, dict) else ({}, True)


def _is_ancestor(root, sha):
    """True/False; GitError se o git falha (rc ≠ 0/1)."""
    rc, _ = _git(root, "merge-base", "--is-ancestor", sha, "HEAD", ok=(0, 1))
    return rc == 0


def _elect_base(root, notes):
    """(sha, fonte). Elege a base da unidade (passo 1 da spec)."""
    bases, invalid = _read_bases(root)
    if invalid:
        notes["bases"] = True
    dropped, cands = 0, []  # cands: (dist, prioridade, ts, id, sha, fonte)
    for uid, entry in bases.items():
        try:
            sha = entry.get("base") if isinstance(entry, dict) else None
            if not isinstance(sha, str) or not sha:
                raise GitError("entry")
            _, full = _git(root, "rev-parse", "--verify", "--quiet", sha + "^{commit}")
            full = full.strip()
            if not _is_ancestor(root, full):
                continue
            _, count = _git(root, "rev-list", "--count", "%s..HEAD" % full)
            ts = entry.get("ts")
            cands.append((int(count.strip()), 0, ts if isinstance(ts, str) else "", uid, full,
                          "bases.json %s" % uid))
        except (GitError, ValueError):
            dropped += 1
    try:
        _, log = _git(root, "log", "--format=%H%x00%s", "-n", "200", "HEAD")
        for line in log.splitlines():
            sha, _, subject = line.partition("\0")
            if " feito: " in subject:
                _, count = _git(root, "rev-list", "--count", "%s..HEAD" % sha)
                cands.append((int(count.strip()), 1, "", "", sha, "fechamento"))
                break
    except (GitError, ValueError):
        dropped += 1
    notes["dropped"] = dropped
    if not cands:
        _, head = _git(root, "rev-parse", "HEAD")
        return head.strip(), "HEAD"
    cands.sort(key=lambda c: c[3])           # menor id
    cands.sort(key=lambda c: c[2], reverse=True)  # maior ts (reverse mantém a ordem dos empates)
    cands.sort(key=lambda c: (c[0], c[1]))   # menor distância; bases.json antes de fechamento
    return cands[0][4], cands[0][5]


def _paths(out):
    parts = out.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def _nonascii(text):
    seen = []
    for ch in text:
        if ord(ch) > 127 and ch not in seen:
            seen.append(ch)
    return seen


def _show(ch):
    o = ord(ch)
    return "'\\x%02x'" % (o - 0xDC00) if 0xDC80 <= o <= 0xDCFF else "'%s'" % ch


def _disp(text):
    """Texto do item: byte não-UTF-8 (surrogate) sai como \\xNN, sem aspas."""
    return "".join("\\x%02x" % (ord(c) - 0xDC00) if 0xDC80 <= ord(c) <= 0xDCFF else c for c in text)


def _tokens(component):
    seen = []
    for chunk in re.split(r"[^A-Za-z0-9]+", component):
        for tok in TOKEN_RE.findall(chunk):
            tok = tok.lower()
            if tok not in seen:
                seen.append(tok)
    return seen


def _word_lines(item, component, allow):
    out = []
    for tok in _tokens(component):
        if tok in allow:
            continue
        if tok in PT_WORDS:
            out.append("%s: '%s' parece português (lista)" % (item, tok))
        elif len(tok) >= 5 and tok.endswith(("cao", "coes")):
            out.append("%s: '%s' parece português (sufixo)" % (item, tok))
    return out


def _run(root, base):
    from .check import Result

    notes = []
    mode, allow_words, allow_paths = _load_config(root, notes)
    if mode == "off":
        return Result("names", True, "desligado")
    try:
        _git(root, "rev-parse", "--git-dir")
    except GitError:
        return Result("names", True, "não é repo git, não checado")
    extra = {}
    tail = []
    if base is not None:
        rc, full = _git(root, "rev-parse", "--verify", "--quiet", base + "^{commit}", ok=(0, 1, 128))
        full = full.strip()
        if rc != 0 or not full:
            return Result("names", False, "base inválida '%s'" % base)
        sha, source = full, "--base"
        if not _is_ancestor(root, sha):
            tail.append("base não é ancestral de HEAD")
    else:
        sha, source = _elect_base(root, extra)
    if extra.get("bases"):
        notes.append("bases.json inválido, ignorado")
    if extra.get("dropped"):
        notes.append("%d candidatos de base descartados" % extra["dropped"])
    notes.extend(tail)

    changed = set()
    for cached in ((), ("--cached",)):
        _, out = _git(root, "diff", "-z", "--name-status", "-M", "-C", "--diff-filter=ACR", *cached, sha)
        changed.update(_diff_new_paths(out))
    _, out = _git(root, "ls-files", "-z", "--others", "--exclude-standard")
    changed.update(_paths(out))
    _, out = _git(root, "ls-tree", "-r", "-t", "-z", "--name-only", sha)
    existing = set(_paths(out))

    segments = set()
    for path in changed:
        parts = path.split("/")
        for i in range(1, len(parts) + 1):
            seg = "/".join(parts[:i])
            if seg not in existing:
                segments.add(seg)
    muted = {s for s in segments if any(fnmatch.fnmatchcase(s, g) for g in allow_paths)}
    segments -= muted

    items = [(seg, seg.rsplit("/", 1)[-1], seg) for seg in sorted(segments)]
    detached = False
    _, branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch.strip()
    if branch == "HEAD":
        detached = True
    elif branch not in ("main", "master"):
        items.append(("branch " + branch, branch, None))

    failures, warnings, lines, bad, nwarn = [], [], [], 0, 0
    for item, component, seg in items:
        item = _disp(item)
        chars = _nonascii(component)
        if chars:
            bad += 1
            line = "%s: não-ASCII %s" % (item, ", ".join(_show(c) for c in chars))
            kind = "falha" if mode == "fail" else "aviso"
            (failures if kind == "falha" else warnings).append(line)
            lines.append((kind, line))
        words = _word_lines(item, component, allow_words)
        nwarn += len(words)
        warnings.extend(words)
        lines.extend(("aviso", w) for w in words)

    ok = not (mode == "fail" and bad)
    detail = "base %s (%s), mode %s, %d segmentos novos, %d não-ASCII, %d avisos" % (
        sha[:7], source, mode if mode in MODES else DEFAULT_MODE, len(segments), bad, nwarn)
    if muted:
        detail += ", %d calados por allow_paths" % len(muted)
    if detached:
        detail += ", branch: detached"
    if notes:
        detail += "; " + "; ".join(notes)
    return Result("names", ok, detail, warnings=warnings, failures=failures, lines=lines)


def _diff_new_paths(out):
    parts = out.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    result, i = [], 0
    while i < len(parts):
        n = 2 if parts[i][:1] in ("R", "C") else 1
        if i + n < len(parts):
            result.append(parts[i + n])
        i += n + 1
    return result


def check_names(root, base=None):
    """Result da checagem `names`; nunca solta exceção (contrato de erros, passo 9 da spec)."""
    from .check import Result

    try:
        return _run(root, base)
    except GitError as e:
        return Result("names", True, "erro do git (%s), não checado" % e)
    except Exception as e:  # o portão nunca solta exceção
        return Result("names", True, "erro do git (%s), não checado" % type(e).__name__)
