"""Índice local `library/index.jsonl` e a cópia só de leitura da release."""
import glob
import json
import os
import re

from . import text as textmod

LOCAL_DIR = "library"
INDEX_NAME = "index.jsonl"
RELEASE_REL = os.path.join(".harnessdev", "library", INDEX_NAME)
KINDS = ("lesson", "skill", "script", "default", "eval-case")
STATUSES = ("candidate", "active", "core", "retired")
SOURCES = ("reflect", "improve", "operator")
KIND_DIR = {
    "lesson": "library/lessons",
    "default": "library/lessons",
    "eval-case": "library/lessons",
    "skill": "library/skills",
    "script": "library/scripts",
}
REQUIRED = (
    "id", "kind", "title", "when_to_use", "not_for", "body_path", "scope", "tags",
    "evidence", "wins", "losses", "uses", "created", "last_used", "status", "source",
)
SCOPE_RX = re.compile(r"^(?:global|repo:[a-z0-9][a-z0-9_-]*|area:[a-z0-9][a-z0-9_-]*)$")
DAY_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ID_RX = re.compile(r"^[a-z][a-z0-9-]{0,48}$")
ACTIVE_CAP = 60


def index_path(root):
    return os.path.join(root, LOCAL_DIR, INDEX_NAME)


def release_index_path(root):
    return os.path.join(root, RELEASE_REL)


def _read_lines(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.readlines()
    except OSError:
        return []


def load_index(path, root):
    """Itens do arquivo. Linha vazia some. JSON ruim sobe ValueError."""
    items = []
    for raw in _read_lines(path):
        line = raw.strip()
        if not line:
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError("linha do índice não é objeto")
        obj["_root"] = root
        items.append(obj)
    return items


def load_local(root):
    path = index_path(root)
    if not os.path.isfile(path):
        return []
    return load_index(path, root)


def load_for_pull(root):
    """Local mais os itens `global` da release. O id local vence."""
    by_id = {}
    release = release_index_path(root)
    local = index_path(root)
    if os.path.isfile(release) and os.path.realpath(release) != os.path.realpath(local):
        release_root = os.path.dirname(os.path.dirname(release))
        for item in load_index(release, release_root):
            if item.get("scope") == "global":
                by_id[item.get("id")] = item
    for item in load_local(root):
        by_id[item.get("id")] = item
    return list(by_id.values())


def public_item(item):
    return {key: value for key, value in item.items() if not str(key).startswith("_")}


def save_local(root, items):
    path = index_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = "".join(
        json.dumps(public_item(item), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for item in items
    )
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        handle.write(body)
    os.replace(tmp, path)


def body_path(item):
    rel = item.get("body_path") or ""
    root = item.get("_root") or ""
    if os.path.isabs(rel):
        return rel
    return os.path.join(root, rel)


def read_body(item):
    path = body_path(item)
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def write_body(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text if text.endswith("\n") else text + "\n")
    return path


def item_error(item):
    """Texto do primeiro problema, ou None se a linha serve."""
    if not isinstance(item, dict):
        return "linha inválida"
    for key in REQUIRED:
        if key not in item:
            return "falta %s" % key
    if not isinstance(item["id"], str) or not ID_RX.match(item["id"]):
        return "id inválido"
    if item["kind"] not in KINDS:
        return "%s: kind inválido" % item["id"]
    if item["status"] not in STATUSES:
        return "%s: status inválido" % item["id"]
    if item["source"] not in SOURCES:
        return "%s: source inválido" % item["id"]
    if not isinstance(item["scope"], str) or not SCOPE_RX.match(item["scope"]):
        return "%s: scope inválido" % item["id"]
    if not isinstance(item["title"], str) or not item["title"].strip():
        return "%s: title vazio" % item["id"]
    if not isinstance(item["when_to_use"], str) or not item["when_to_use"].strip():
        return "%s: when_to_use vazio" % item["id"]
    if not isinstance(item["not_for"], str):
        return "%s: not_for inválido" % item["id"]
    if not isinstance(item["tags"], list) or not all(isinstance(tag, str) for tag in item["tags"]):
        return "%s: tags inválidas" % item["id"]
    if not isinstance(item["evidence"], list):
        return "%s: evidence inválida" % item["id"]
    for key in ("wins", "losses", "uses"):
        if not isinstance(item[key], int) or item[key] < 0:
            return "%s: %s inválido" % (item["id"], key)
    if not isinstance(item["created"], str) or not DAY_RX.match(item["created"]):
        return "%s: created inválido" % item["id"]
    if item["last_used"] is not None and (not isinstance(item["last_used"], str) or not DAY_RX.match(item["last_used"])):
        return "%s: last_used inválido" % item["id"]
    rel = item["body_path"]
    if not isinstance(rel, str) or not rel or rel.startswith("/") or ".." in rel.split("/"):
        return "%s: body_path inválido" % item["id"]
    folder = KIND_DIR[item["kind"]]
    if not rel.startswith(folder + "/"):
        return "%s: body_path fora de %s" % (item["id"], folder)
    gen = item.get("generalization")
    if gen is not None and gen not in ("checked", "pending"):
        return "%s: generalization inválida" % item["id"]
    retired = item.get("retired_on")
    if retired is not None and (not isinstance(retired, str) or not DAY_RX.match(retired)):
        return "%s: retired_on inválido" % item["id"]
    return None


def script_tested(root, item):
    base = os.path.basename(item["body_path"])
    cited = item.get("test")
    if isinstance(cited, str) and cited:
        paths = [os.path.join(root, cited)]
    else:
        paths = sorted(glob.glob(os.path.join(root, "tests", "test_*.py")))
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                if base in handle.read():
                    return True
        except OSError:
            continue
    return False


def installed_library_skills(root):
    lib = os.path.realpath(os.path.join(root, "library", "skills"))
    folder = os.path.join(root, ".claude", "skills")
    if not os.path.isdir(folder):
        return []
    hits = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        try:
            real = os.path.realpath(path)
        except OSError:
            continue
        if real == lib or real.startswith(lib + os.sep):
            hits.append(name)
    return hits


def problems(root):
    """Lista de erros do índice local. Vazio se não há índice ou se ele fecha."""
    path = index_path(root)
    if not os.path.isfile(path):
        return []
    try:
        items = load_local(root)
    except ValueError as exc:
        return ["índice inválido: %s" % exc]
    found = []
    seen = set()
    active = 0
    for item in items:
        err = item_error(item)
        if err:
            found.append(err)
            continue
        if item["id"] in seen:
            found.append("%s: id repetido" % item["id"])
        seen.add(item["id"])
        if item["status"] == "active":
            active += 1
        body_file = body_path(item)
        if not os.path.isfile(body_file):
            found.append("%s: corpo ausente" % item["id"])
            continue
        try:
            body = read_body(item)
        except OSError as exc:
            found.append("%s: corpo ilegível (%s)" % (item["id"], exc))
            continue
        if item["kind"] == "lesson" and not textmod.lesson_shape_ok(body):
            found.append("%s: lição passa de %d linhas ou foge da forma" % (item["id"], textmod.LESSON_LINES))
        if item["kind"] == "script" and not script_tested(root, item):
            found.append("%s: script sem teste" % item["id"])
    if active > ACTIVE_CAP:
        found.append("%d ativas (teto %d)" % (active, ACTIVE_CAP))
    installed = installed_library_skills(root)
    if installed:
        found.append("skill da biblioteca instalada: %s" % ", ".join(installed))
    return found


def report(root):
    found = problems(root)
    if found:
        return False, found[0]
    items = load_local(root) if os.path.isfile(index_path(root)) else []
    active = sum(1 for item in items if item.get("status") == "active")
    if not items:
        return True, "vazia"
    return True, "%d itens, %d ativas (teto %d); lições <= %d linhas" % (
        len(items), active, ACTIVE_CAP, textmod.LESSON_LINES)
