"""Cache do grafo (graphify 0.9.112, só AST).

`graph.json` é node-link: nó com `id` e `source_file`; aresta em `links`
(ou `edges`) com `source`, `target`, `relation` e `confidence`
(`EXTRACTED`, `INFERRED` ou `AMBIGUOUS`). O sidecar
`.hdev/cache/graph/sha` guarda o HEAD em que o arquivo foi escrito.
Sem o binário, sem o arquivo ou com sha diferente, o comando avisa e segue.
"""
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys

CACHE_REL = os.path.join(".hdev", "cache", "graph")
GRAPH_NAME = "graph.json"
SHA_NAME = "sha"
IMPORT_RELATIONS = frozenset({"imports", "imports_from"})
IMPACT_RELATIONS = frozenset({"calls", "imports", "imports_from"})
EXTRACTED = "EXTRACTED"
MAX_DEPTH = 8
MAX_NODES = 2000
STEM_RX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
UPDATE_TIMEOUT = 300


def cache_dir(root):
    return os.path.join(root, CACHE_REL)


def graph_file(root):
    return os.path.join(cache_dir(root), GRAPH_NAME)


def sha_file(root):
    return os.path.join(cache_dir(root), SHA_NAME)


def norm_rel(root, path):
    """Caminho do repo com barra, sem `.` nem `..`. Absoluto vira relativo à raiz."""
    if not isinstance(path, str):
        return ""
    raw = path.replace("\\", "/").strip()
    if not raw:
        return ""
    if os.path.isabs(path):
        raw = os.path.relpath(path, root).replace(os.sep, "/")
    parts = []
    for part in raw.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return ""
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def git_root(start):
    try:
        r = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return os.path.realpath(start)
    if r.returncode != 0 or not r.stdout.strip():
        return os.path.realpath(start)
    return os.path.realpath(r.stdout.strip())


def head_sha(root):
    try:
        r = subprocess.run(["git", "-C", root, "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    sha = r.stdout.strip()
    return sha or None


def read_sha(root):
    path = sha_file(root)
    try:
        with open(path, encoding="utf-8") as f:
            sha = f.read().strip()
    except OSError:
        return None
    return sha or None


def write_sha(root, sha):
    os.makedirs(cache_dir(root), exist_ok=True)
    path = sha_file(root)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(sha + "\n")
    os.replace(tmp, path)


def cache_problem(root):
    """None se o grafo está no HEAD. Senão um texto curto (ausente, velho, ...)."""
    if not os.path.isfile(graph_file(root)):
        return "ausente"
    side = read_sha(root)
    head = head_sha(root)
    if not side:
        return "velho (sem sha)"
    if not head:
        return "velho (sem HEAD)"
    if side != head:
        return "velho (sha %s != HEAD %s)" % (side[:12], head[:12])
    return None


def _split(data):
    if not isinstance(data, dict):
        raise ValueError("graph.json sem objeto")
    nodes = data.get("nodes") or []
    links = data.get("links")
    if links is None:
        links = data.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(links, list):
        raise ValueError("graph.json sem listas")
    return nodes, links


def open_graph(root):
    """((nós, arestas), None) ou (None, problema)."""
    problem = cache_problem(root)
    if problem:
        return None, problem
    try:
        with open(graph_file(root), encoding="utf-8") as f:
            data = json.load(f)
        return _split(data), None
    except (OSError, ValueError, json.JSONDecodeError):
        return None, "ilegível"


def _end(value):
    if isinstance(value, dict):
        value = value.get("id")
    if isinstance(value, str) and value:
        return value
    return None


def _index(root, nodes):
    file_of = {}
    present = set()
    labels = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        nid = node.get("id")
        if not isinstance(nid, str) or not nid:
            continue
        labels[nid] = node.get("label") if isinstance(node.get("label"), str) else ""
        sf = norm_rel(root, node.get("source_file"))
        if not sf:
            continue
        file_of[nid] = sf
        present.add(sf)
    return file_of, present, labels


def is_test_path(rel):
    if not rel.endswith(".py"):
        return False
    parts = rel.split("/")
    return len(parts) == 2 and parts[0] == "tests" and os.path.basename(rel).startswith("test_")


def module_stem(path):
    base = os.path.basename((path or "").rstrip("/"))
    stem, _ext = os.path.splitext(base)
    return stem


def _tests_named(root, pattern):
    folder = os.path.join(root, "tests")
    if not os.path.isdir(folder):
        return []
    out = []
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".py") or not os.path.isfile(os.path.join(folder, name)):
            continue
        if fnmatch.fnmatch(name, pattern):
            out.append("tests/" + name)
    return out


def suite_for(root, files):
    """(caminhos, 'módulo'|'inteira', radicais). Sem `tests/test_<radical>*.py`, a suíte inteira."""
    stems = []
    chosen = []
    full = False
    for rel in files:
        stem = module_stem(rel)
        stems.append(stem)
        if not STEM_RX.match(stem or ""):
            full = True
            continue
        hits = _tests_named(root, "test_%s*.py" % stem)
        if hits:
            chosen.extend(hits)
        else:
            full = True
    if full or not chosen:
        return _tests_named(root, "test_*.py"), "inteira", stems
    return sorted(set(chosen)), "módulo", list(dict.fromkeys(stems))


def fallback_message(problem, kind, stems):
    if kind == "módulo":
        alvo = "suíte do módulo %s" % ", ".join(stems)
    else:
        alvo = "suíte inteira"
    return "grafo %s: fallback para a %s" % (problem, alvo)


def _import_reverse(links):
    rev = {}
    for edge in links:
        if not isinstance(edge, dict):
            continue
        if edge.get("confidence") != EXTRACTED or edge.get("relation") not in IMPORT_RELATIONS:
            continue
        src, tgt = _end(edge.get("source")), _end(edge.get("target"))
        if not src or not tgt:
            continue
        rev.setdefault(tgt, []).append(src)
    return rev


def tests_touching(file_of, rev, rels):
    """Testes que importam `rels`, subindo no máximo MAX_DEPTH arestas EXTRACTED.

    Devolve (caminhos, cortou). O corte é 8 saltos ou 2000 nós, o que vier antes.
    """
    wanted = set(rels)
    start = [nid for nid, sf in file_of.items() if sf in wanted]
    seen = set(start)
    frontier = list(start)
    found = set()
    for rel in rels:
        if rel in wanted and is_test_path(rel) and rel in set(file_of.values()):
            found.add(rel)
    depth = 0
    truncated = False
    while frontier and depth < MAX_DEPTH:
        nxt = []
        for nid in frontier:
            for src in rev.get(nid, ()):
                if src in seen:
                    continue
                if len(seen) >= MAX_NODES:
                    truncated = True
                    break
                seen.add(src)
                sf = file_of.get(src)
                if sf and is_test_path(sf):
                    found.add(sf)
                nxt.append(src)
            if truncated:
                break
        frontier = nxt
        depth += 1
        if truncated:
            break
    if frontier and depth >= MAX_DEPTH:
        truncated = True
    return sorted(found), truncated


def affected_tests(root, files):
    """(caminhos na stdout, mensagem no stderr ou None)."""
    root = os.path.realpath(root)
    rels = [norm_rel(root, f) for f in files]
    graph, problem = open_graph(root)
    if problem:
        paths, kind, stems = suite_for(root, rels)
        return paths, fallback_message(problem, kind, stems)
    nodes, links = graph
    file_of, present, _labels = _index(root, nodes)
    known = [rel for rel in rels if rel in present]
    unknown = [rel for rel in rels if rel not in present]
    found, truncated = tests_touching(file_of, _import_reverse(links), known)
    notes = []
    if truncated:
        notes.append("busca de imports cortada (até %d saltos e %d nós)" % (MAX_DEPTH, MAX_NODES))
    if unknown:
        extra, kind, stems = suite_for(root, unknown)
        found = sorted(set(found) | set(extra))
        notes.append(fallback_message("sem nó (%s)" % ", ".join(unknown), kind, stems))
    return found, (" ".join(notes) if notes else None)


def _accumulate(bucket, other, relation):
    bucket.setdefault(other, set()).add(relation)


def impact_sets(root, rel, nodes, links):
    file_of, _present, labels = _index(root, nodes)
    incoming, outgoing = {}, {}
    external = set()
    for edge in links:
        if not isinstance(edge, dict):
            continue
        if edge.get("confidence") != EXTRACTED or edge.get("relation") not in IMPACT_RELATIONS:
            continue
        src_id, tgt_id = _end(edge.get("source")), _end(edge.get("target"))
        if not src_id or not tgt_id:
            continue
        src, tgt = file_of.get(src_id), file_of.get(tgt_id)
        relation = edge.get("relation")
        if src == rel and tgt and tgt != rel:
            _accumulate(outgoing, tgt, relation)
        elif tgt == rel and src and src != rel:
            _accumulate(incoming, src, relation)
        elif src == rel and not tgt:
            label = labels.get(tgt_id) or tgt_id
            if label and label != rel:
                external.add(label)
    return incoming, outgoing, external


def format_impact(rel, incoming, outgoing, external):
    lines = [rel, "quem chama ou importa:"]
    if incoming:
        for path in sorted(incoming):
            lines.append("  %s  %s" % (path, ", ".join(sorted(incoming[path]))))
    else:
        lines.append("  (ninguém)")
    lines.append("o que chama ou importa:")
    if outgoing:
        for path in sorted(outgoing):
            lines.append("  %s  %s" % (path, ", ".join(sorted(outgoing[path]))))
    elif not external:
        lines.append("  (ninguém)")
    if external:
        lines.append("  fora do repo: %s" % ", ".join(sorted(external)))
    return "\n".join(lines)


def impact(root, path):
    """(texto, mensagem no stderr ou None). Texto vazio se o grafo não serve."""
    root = os.path.realpath(root)
    rel = norm_rel(root, path)
    graph, problem = open_graph(root)
    if problem:
        _paths, kind, stems = suite_for(root, [rel])
        return "", fallback_message(problem, kind, stems)
    nodes, links = graph
    incoming, outgoing, external = impact_sets(root, rel, nodes, links)
    _file_of, present, _labels = _index(root, nodes)
    note = None if rel in present else "arquivo sem nó no grafo: %s" % rel
    return format_impact(rel, incoming, outgoing, external), note


def graphify_bin(env=None):
    env = os.environ if env is None else env
    found = shutil.which("graphify", path=env.get("PATH"))
    if found:
        return found
    home = env.get("HOME") or ""
    candidate = os.path.join(home, ".local", "bin", "graphify")
    if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def _show_update(text):
    keep = ("no LLM", "Rebuilt", "No relevant", "graph.json", "Code graph", "error", "Error", "falhou")
    shown = [ln for ln in (text or "").splitlines() if any(k in ln for k in keep)]
    for ln in shown[:12]:
        print(ln)


def update(root, force=False):
    """Roda `graphify update .` (AST). 0 se atualizou, pulou ou o binário não está. 1 se ele falhou."""
    root = os.path.realpath(root)
    head = head_sha(root)
    if not force and head and read_sha(root) == head and os.path.isfile(graph_file(root)):
        print("grafo em dia (%s)" % head[:12])
        return 0
    binary = graphify_bin()
    if not binary:
        print("graphify não instalado: grafo não atualizado", file=sys.stderr)
        return 0
    os.makedirs(cache_dir(root), exist_ok=True)
    env = dict(os.environ)
    env["GRAPHIFY_OUT"] = CACHE_REL.replace(os.sep, "/")
    env["GRAPHIFY_NO_TIPS"] = "1"
    try:
        proc = subprocess.run([binary, "update", "."], cwd=root, env=env,
                              capture_output=True, text=True, timeout=UPDATE_TIMEOUT)
    except subprocess.TimeoutExpired:
        print("graphify update estourou o tempo", file=sys.stderr)
        return 1
    except OSError as e:
        print("graphify update não rodou: %s" % e, file=sys.stderr)
        return 1
    _show_update((proc.stdout or "") + "\n" + (proc.stderr or ""))
    if proc.returncode != 0 or not os.path.isfile(graph_file(root)):
        print("graphify update falhou", file=sys.stderr)
        return 1
    if not head:
        print("grafo escrito, sem HEAD para o sha", file=sys.stderr)
        return 1
    write_sha(root, head)
    print("grafo atualizado em .hdev/cache/graph (%s)" % head[:12])
    return 0


def affected_main(argv, root=None):
    if not argv:
        print("uso: scripts/affected-tests <arquivo>...", file=sys.stderr)
        return 2
    root = os.path.realpath(root or git_root(os.getcwd()))
    paths, msg = affected_tests(root, argv)
    if msg:
        print(msg, file=sys.stderr)
    for path in paths:
        print(path)
    return 0


def impact_main(args):
    text, msg = impact(args.root, args.file)
    if msg:
        print(msg, file=sys.stderr)
    if text:
        print(text)
    return 0


def update_main(args):
    return update(args.root, force=getattr(args, "force", False))
