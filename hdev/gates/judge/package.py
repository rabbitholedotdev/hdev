"""Monta e parte o pacote do juiz. Cabeçalho até MAX_HEAD; pacote até MAX_PACKAGE."""
import os
import re

from .constants import (
    CODE_EXT, DOC_EXT, MAX_HEAD, MAX_MANIFEST, MAX_MOVES_NOTE, MAX_PACKAGE, MAX_PARTS,
    PART_READ_CAP, PARTS_NOTE, RUBRIC,
)

def _blocks(diff):
    """Diff partido em blocos por arquivo (diff --git / === novo), na ordem."""
    blocks, cur = [], []
    for line in diff.splitlines():
        if (line.startswith("diff --git ") or line.startswith("=== novo")) and cur:
            blocks.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        blocks.append("\n".join(cur))
    return blocks


def _block_name(block):
    first = block.split("\n", 1)[0]
    if first.startswith("diff --git "):
        return first.split(" b/", 1)[-1]
    return first.split(": ", 1)[-1]


def _omitted_note(names, room):
    """Lista de omitidos sempre inteira (F1-06): todos os nomes; se não cabe, todos agrupados por pasta.

    Nunca corta no meio: cada arquivo omitido aparece pelo nome ou contado na sua pasta."""
    full = "[omitidos por tamanho (%d): %s]" % (len(names), ", ".join(names))
    if len(full) <= room:
        return full
    for depth in (None, 1):
        groups = {}
        for name in names:
            parts = name.split("/")[:-1]
            folder = "/".join(parts if depth is None else parts[:depth]) or "."
            groups[folder] = groups.get(folder, 0) + 1
        note = "[omitidos por tamanho (%d), agrupados por pasta: %s]" % (
            len(names), ", ".join("%s/ (%d)" % (k, v) for k, v in sorted(groups.items())))
        if len(note) <= room:
            return note
    return "[omitidos por tamanho (%d): lista não cabe no teto]" % len(names)


def fit_diff(diff, budget):
    """Blocos inteiros por arquivo até caber no orçamento; os que não cabem vão listados pelo nome.

    O corte é sempre em fronteira de bloco e a lista de omitidos vai inteira (revisão Codex,
    judge-20261115T003907053023Z)."""
    if len(diff) <= budget:
        return diff
    blocks = _blocks(diff)
    full_all = len(_omitted_note([_block_name(b) for b in blocks], float("inf")))
    reserve = min(full_all + 2, max(budget // 2, 200))
    kept, omitted, used = [], [], 0
    for block in blocks:
        if used + len(block) + 1 <= budget - reserve:
            kept.append(block)
            used += len(block) + 1
        else:
            omitted.append(_block_name(block))
    return "\n".join(kept + [_omitted_note(omitted, max(budget - used - 1, 0))])


def _trim_lines(text, limit, keep="head"):
    """Corta uma seção do cabeçalho em fronteira de linha, com aviso; keep='tail' guarda o fim."""
    if len(text) <= limit:
        return text
    lines = text.splitlines()
    marker = "[seção cortada em fronteira de linha: %d caracteres omitidos]"
    out, size = [], len(marker % len(text)) + 1
    for line in (reversed(lines) if keep == "tail" else lines):
        if size + len(line) + 1 > limit:
            break
        out.append(line)
        size += len(line) + 1
    if keep == "tail":
        out.reverse()
    kept = "\n".join(out)
    note = marker % (len(text) - len(kept))
    return "%s\n%s" % (note, kept) if keep == "tail" else "%s\n%s" % (kept, note)

_DURATION = re.compile(r"\bin \d+(?:\.\d+)?s\b")
# Pasta temporária do clone (`hdev-judge-`) ou de um teste (`hdev-test-`), e o resto de /tmp.
_TMP_PATH = re.compile(
    r"(?:/(?:private/)?tmp/|/var/folders/(?:[^/\s]+/){2}T/)(?:hdev-(?:judge|test)-)?[A-Za-z0-9_.-]{6,}"
)


def normalize_test_log(text):
    """Tira tempo de parede e pasta temporária. Fica o exit, a contagem, OK/FAILED e o nome do teste.

    O hash do pacote é a chave do cache. `Ran 413 tests in 52.382s` mudava a cada corrida e o
    cache com --run-tests nunca acertava. A falha continua no texto, então a chave muda."""
    if not text:
        return text
    text = _TMP_PATH.sub("/tmp/TMP", text)
    return _DURATION.sub("in TIME", text)


def _prepare_head(criterion, tests_text, rubric=RUBRIC, **secs):
    """Cabeçalho do pacote até MAX_HEAD: apara a maior seção por vez em fronteira de linha.

    Devolve (cabeçalho, seções aparadas)."""
    tests_text = normalize_test_log(tests_text) or "(sem log de testes)"
    sections = {"tests": tests_text}
    for key in ("base", "commits", "check", "evidence", "stat", "moves", "manifest"):
        sections[key] = secs.get(key) or ""
    titles = (("base", "BASE DO DIFF"), ("commits", "COMMIT"), ("check", "HDEV CHECK"), ("evidence", "EVIDÊNCIA"),
              ("stat", "ARQUIVOS"), ("moves", "RENOMEADOS SEM MUDANÇA"), ("manifest", "MANIFESTO"))

    def head_of(sec):
        h = "%s\n\n=== CRITÉRIO DE PRONTO\n%s\n\n=== TESTES\n%s\n\n" % (rubric, criterion, sec["tests"])
        for key, title in titles:
            if sec[key]:
                h += "=== %s\n%s\n\n" % (title, sec[key])
        return h + "=== DIFF\n"

    head = head_of(sections)
    trimmed = []
    # apara a maior seção por vez (testes guardam o fim, onde fica o resumo; o resto guarda o começo)
    while len(head) > MAX_HEAD:
        key = max(("tests", "evidence", "stat", "check", "commits", "moves", "manifest"),
                  key=lambda k: len(sections[k]))
        cur = sections[key]
        target = max(len(cur) - (len(head) - MAX_HEAD) - 100, 200)
        if target >= len(cur):
            break
        sections[key] = _trim_lines(cur, target, keep="tail" if key in ("tests", "check") else "head")
        if key not in trimmed:
            trimmed.append(key)
        head = head_of(sections)
    return head, trimmed


def build_package(criterion, diff, tests_text, stat="", check_out="", commits="", evidence_out="", base_out="",
                  moves_out=""):
    """Pacote do juiz até MAX_PACKAGE sem corte bruto: o cabeçalho é aparado por seção em fronteira
    de linha (até MAX_HEAD) e o diff só perde blocos inteiros, com a lista de omitidos inteira."""
    head, _ = _prepare_head(criterion, tests_text, base=base_out, commits=commits, check=check_out,
                            evidence=evidence_out, stat=stat, moves=moves_out)
    budget = max(MAX_PACKAGE - len(head) - 200, 0)
    return head + (fit_diff(diff, budget) if diff else "(diff vazio)") + "\n"


_PURE_HEADER = ("diff --git ", "similarity index 100%", "rename from ", "rename to ", "copy from ", "copy to ")


def split_pure_moves(diff):
    """(diff sem os movimentos puros, [(R|C, de, para)]). Movimento puro: similarity 100%, sem hunk nem modo."""
    kept, moves = [], []
    for block in _blocks(diff) if diff else []:
        lines = block.splitlines()
        pure = (lines and lines[0].startswith("diff --git ")
                and any(line == "similarity index 100%" for line in lines)
                and all(line.startswith(_PURE_HEADER) for line in lines))
        if not pure:
            kept.append(block)
            continue
        kind, src, dst = "R", None, None
        for line in lines:
            for prefix, k in (("rename from ", "R"), ("copy from ", "C")):
                if line.startswith(prefix):
                    kind, src = k, line[len(prefix):]
            for prefix in ("rename to ", "copy to "):
                if line.startswith(prefix):
                    dst = line[len(prefix):]
        if src is None or dst is None:
            kept.append(block)
            continue
        moves.append((kind, src, dst))
    return "\n".join(kept), moves


def moves_note(moves, room=MAX_MOVES_NOTE):
    """Lista dos movimentos puros: um por linha; se não cabe, agrupada por par de pastas (nunca some nome
    sem contagem)."""
    if not moves:
        return ""
    full = "%d arquivo(s) só mudaram de lugar (conteúdo idêntico):\n%s" % (
        len(moves), "\n".join("%s %s -> %s" % m for m in moves))
    if len(full) <= room:
        return full
    groups = {}
    for kind, src, dst in moves:
        k = (kind, os.path.dirname(src) or ".", os.path.dirname(dst) or ".")
        groups[k] = groups.get(k, 0) + 1
    note = "%d arquivo(s) só mudaram de lugar (conteúdo idêntico), agrupados por pasta:\n%s" % (
        len(moves), "\n".join("%s %s/ -> %s/ (%d)" % (k[0], k[1], k[2], v) for k, v in sorted(groups.items())))
    return note if len(note) <= room else _trim_lines(note, room)


def block_priority(block):
    """Ordem dos blocos nas partes: código, testes, docs/config, resto (lógica primeiro)."""
    name = _block_name(block).lower()
    base = os.path.basename(name)
    is_test = "test" in base or "/tests/" in "/" + name or "/testes/" in "/" + name
    if name.endswith(CODE_EXT):
        return 1 if is_test else 0
    if is_test:
        return 1
    if name.endswith(DOC_EXT):
        return 2
    return 3


def split_parts(diff, hard, max_parts=MAX_PARTS, soft=None):
    """Blocos (lógica primeiro) empacotados em partes. Devolve (partes, cortados, omitidos).

    `soft` é o alvo de cada parte (com cabeçalho grande, menor, para o diff não ir para o meio
    de um pacote único). `hard` é o teto: bloco maior que isso entra cortado em fronteira de
    linha, com aviso no texto (`cortados`). O que passa de `max_parts` fica de fora, nomeado
    em `omitidos`. Arquivo que cabe em `hard` não é cortado: abre outra parte."""
    soft = hard if soft is None else min(soft, hard)
    blocks = sorted(_blocks(diff), key=block_priority) if diff else []
    parts, cur, size = [], [], 0
    for block in blocks:
        cut = None
        piece = block
        if len(piece) + 1 > hard:
            cut = {"arquivo": _block_name(block), "caracteres": len(block)}
            piece = _trim_lines(block, max(hard - 200, 200))
        if cur and size + len(piece) + 1 > soft:
            parts.append(cur)
            cur, size = [], 0
        cur.append((piece, cut))
        size += len(piece) + 1
    if cur:
        parts.append(cur)
    omitted = [_block_name(b) for p in parts[max_parts:] for b, _ in p]
    kept = parts[:max_parts]
    cut_list = [c for p in kept for _, c in p if c]
    return ["\n".join(b for b, _ in p) for p in kept], cut_list, omitted


def manifest_text(parts):
    lines = []
    for i, part in enumerate(parts, 1):
        names = [_block_name(b) for b in _blocks(part)]
        lines.append("parte %d/%d (%d arquivo(s)): %s" % (i, len(parts), len(names), ", ".join(names)))
    return _trim_lines("\n".join(lines), MAX_MANIFEST)


def build_packages(criterion, diff, tests_text, stat="", check_out="", commits="", evidence_out="", base_out="",
                   max_parts=MAX_PARTS):
    """Pacote(s) do juiz (v0.4.2, ADR 0010). Movimentos puros viram lista; se o resto do diff cabe, um pacote
    (igual ao de antes); senão, partes com o mesmo cabeçalho, o MANIFESTO e a nota de partes na rubrica.

    Devolve (pacotes, meta) — meta diz o que entrou, o que foi cortado e o que ficou de fora."""
    rest, moves = split_pure_moves(diff)
    moves_out = moves_note(moves)
    secs = dict(base=base_out, commits=commits, check=check_out, evidence=evidence_out, stat=stat, moves=moves_out)
    head, trimmed = _prepare_head(criterion, tests_text, **secs)
    meta = {"partes": 1, "renomeados_puros": len(moves), "arquivos_no_diff": len(_blocks(rest)) if rest else 0,
            "cortados": [], "omitidos": [], "secoes_aparadas": trimmed}
    if not rest:
        return [head + "(diff vazio)\n"], meta
    probe = RUBRIC + PARTS_NOTE.format(i=max_parts, n=max_parts)
    head_p, _ = _prepare_head(criterion, tests_text, rubric=probe, manifest="m" * MAX_MANIFEST, **secs)
    # hard: o que ainda cabe em MAX_PACKAGE. soft: o que cabe sem empurrar o diff para o meio
    # de um pacote único (cabeçalho grande + diff inteiro passava de PART_READ_CAP e o juiz
    # não via os arquivos do meio). Arquivo que cabe em hard não é cortado.
    hard = max(MAX_PACKAGE - len(head_p) - 300, 1000)
    soft = min(hard, max(PART_READ_CAP - len(head_p) - 300, 1000))
    if len(rest) <= soft and len(head) + len(rest) + 1 <= PART_READ_CAP:
        return [head + rest + "\n"], meta
    parts, cut, omitted = split_parts(rest, hard, max_parts, soft)
    if omitted:
        # alvo curto demais omitiria arquivo que cabe no teto duro: alarga, não esconde
        wider, cut_w, omitted_w = split_parts(rest, hard, max_parts, hard)
        if len(omitted_w) < len(omitted):
            parts, cut, omitted = wider, cut_w, omitted_w
    manifest = manifest_text(parts)
    if omitted:
        manifest += "\n[fora do pacote por passar de %d partes (%d): %s]" % (
            max_parts, len(omitted), _omitted_note(omitted, MAX_MANIFEST)[1:-1])
    packages = []
    for i, part in enumerate(parts, 1):
        rubric = RUBRIC + PARTS_NOTE.format(i=i, n=len(parts))
        h, tr = _prepare_head(criterion, tests_text, rubric=rubric, manifest=manifest, **secs)
        packages.append(h.replace("=== DIFF\n", "=== DIFF (parte %d/%d)\n" % (i, len(parts)), 1) + part + "\n")
        trimmed = sorted(set(trimmed) | set(tr))
    meta.update({"partes": len(parts), "cortados": cut, "omitidos": omitted, "secoes_aparadas": trimmed})
    return packages, meta
