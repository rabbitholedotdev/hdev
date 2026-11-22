"""Cache da suíte do fechar, por tree sha, em `.hdev/cache/full/` (gitignored).

Entra na chave: tree sha do HEAD, comando `gates.full`, shards configurado, workers
efetivos, versão do Python do interpretador, timeout e a versão do formato.
O tree cobre o código. O comando cobre como os testes são achados. Shards e
workers cobrem o corte. A versão do Python cobre o interpretador. O timeout entra
porque um valor menor pode transformar um pass antigo em timeout. O formato entra
para um runner novo não reusar um JSON velho.

Não grava falha, timeout nem erro. `--no-cache` não lê; um pass grava por cima.
"""
import hashlib
import json
import os

CACHE_DIR = os.path.join(".hdev", "cache", "full")
FORMAT = 1


def cache_key(tree, command, shards, workers, python, timeout, fmt=FORMAT):
    """(sha256, payload)."""
    payload = {
        "tree": tree or "",
        "command": command if isinstance(command, str) else [str(p) for p in (command or [])],
        "shards": int(shards),
        "workers": int(workers),
        "python": python or "",
        "timeout": int(timeout),
        "format": int(fmt),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest(), payload


def cacheable(result):
    """Só pass limpo. Falha, timeout e erro ficam de fora."""
    if not isinstance(result, dict) or result.get("ok") is not True:
        return False
    if result.get("kind") != "pass":
        return False
    if result.get("failures"):
        return False
    for key in ("tree", "tests", "shards", "wall_s", "serial_s"):
        if key not in result:
            return False
    return True


def _path(root, key):
    return os.path.join(root, CACHE_DIR, key + ".json")


def load(root, key):
    try:
        with open(_path(root, key), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("key_sha") != key:
        return None
    result = data.get("result")
    if not cacheable(result):
        return None
    return result


def store(root, key, payload, result):
    if not cacheable(result):
        return False
    path = _path(root, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"key_sha": key, "key": payload, "result": result}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return True
