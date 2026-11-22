"""hdev spec check — aceite em comando, fora de escopo e tabela dúvida → default → reverter.

Sai 0 quando a spec fecha, 1 quando falta peça, 2 em erro de uso e 3 quando a tabela existe
mas um default está vazio (precisa do dono). Não executa os comandos do aceite.
"""
import os
import re
import unicodedata

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
_CODE = re.compile(r"`([^`\n]+)`")
_TOKEN = re.compile(r"^[A-Za-z0-9_./+-]+$")
_BLANK = {"", "-", "?", "todo", "tbd", "perguntar", "dono", "a definir", "em aberto"}


def _fold(text):
    base = unicodedata.normalize("NFD", text or "")
    stripped = "".join(c for c in base if unicodedata.category(c) != "Mn")
    return stripped.strip().lower()


def _sections(text):
    found = []
    heading = None
    buf = []
    for line in text.splitlines(keepends=True):
        m = _HEADING.match(line.rstrip("\n"))
        if m:
            if heading is not None or buf:
                found.append((heading, "".join(buf)))
            heading = m.group(2).strip()
            buf = []
        else:
            buf.append(line)
    if heading is not None or buf:
        found.append((heading, "".join(buf)))
    return found


def _section(text, pattern):
    rx = re.compile(pattern, re.I)
    for heading, body in _sections(text):
        if heading and rx.match(heading):
            return body
    return None


def _has_body(text):
    for line in (text or "").splitlines():
        s = line.strip()
        if s and not re.fullmatch(r"[-*_]{3,}", s):
            return True
    return False


def _is_command(text):
    raw = (text or "").strip()
    if raw.startswith("$ "):
        raw = raw[2:].strip()
    parts = raw.split()
    if len(parts) < 2 or not _TOKEN.match(parts[0]):
        return False
    return True


def _commands(section):
    found = []
    for match in _FENCE.finditer(section or ""):
        for line in match.group(1).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                found.append(line)
    for match in _CODE.finditer(section or ""):
        found.append(match.group(1).strip())
    return [item for item in found if _is_command(item)]


def _cells(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_row(line):
    s = line.strip()
    return s.startswith("|") and s.count("|") >= 3


def _is_sep(line):
    if not _is_row(line):
        return False
    cells = [c for c in _cells(line) if c]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c) for c in cells)


def _tables(text):
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if _is_row(lines[i]) and i + 1 < len(lines) and _is_sep(lines[i + 1]):
            header = _cells(lines[i])
            rows = []
            j = i + 2
            while j < len(lines) and _is_row(lines[j]) and not _is_sep(lines[j]):
                rows.append(_cells(lines[j]))
                j += 1
            yield header, rows
            i = j
        else:
            i += 1


def _col(header, name):
    for i, cell in enumerate(header):
        if _fold(cell) == name:
            return i
    return None


def _defaults(text):
    for header, rows in _tables(text):
        if _col(header, "duvida") is None:
            continue
        if _col(header, "default") is None or _col(header, "reverter") is None:
            continue
        kept = [row for row in rows if any(cell.strip() for cell in row)]
        return header, kept
    return None


def _blank(value):
    return _fold(value) in _BLANK


def check_text(text):
    """(código, mensagens). 0 ok, 1 falha o check, 3 precisa do dono."""
    problems = []
    aceite = _section(text, r"^aceite\b")
    if aceite is None or not _commands(aceite):
        problems.append("aceite sem comando")
    fora = _section(text, r"^fora de escopo\b")
    if fora is None or not _has_body(fora):
        problems.append("falta fora de escopo")
    table = _defaults(text)
    if table is None:
        problems.append("falta a tabela dúvida, default, reverter")
    elif not table[1]:
        problems.append("tabela sem linha")
    if problems:
        return 1, problems
    header, rows = table
    default_i = _col(header, "default")
    duvida_i = _col(header, "duvida")
    blanks = []
    for row in rows:
        value = row[default_i] if default_i < len(row) else ""
        if _blank(value):
            label = row[duvida_i].strip() if duvida_i < len(row) else ""
            blanks.append(label or "?")
    if blanks:
        return 3, ["default vazio (%s); precisa do dono" % ", ".join(blanks)]
    return 0, []


def main_check(args):
    path = getattr(args, "path", None)
    if not path:
        print("hdev spec check: falta o arquivo")
        return 2
    if os.path.isdir(path) or not os.path.isfile(path):
        print("hdev spec check: arquivo não encontrado: %s" % path)
        return 2
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeError) as e:
        print("hdev spec check: %s" % e)
        return 2
    code, msgs = check_text(text)
    if code == 0:
        print("hdev spec check: ok")
    else:
        print("hdev spec check: %s" % "; ".join(msgs))
    return code
