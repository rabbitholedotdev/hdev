"""Cache do veredito, por sha, em `.hdev/cache/judge/` (gitignored).

Entra na chave: sha da base, sha do head, hash do plano, CLI/provedor/modelo do juiz e do
fallback, versão da rubrica (PROMPT_VERSION + texto), se os testes rodaram (off, run ou log)
e o hash do pacote. O log de testes entra sem tempo de parede nem pasta temporária
(pass/fail, contagem e o nome do teste que falhou ficam). Qualquer um diferente erra o cache.

Não grava erro, falha de provedor nem unsure. `--no-cache` não lê; um pass ou fail limpo
grava por cima, para a corrida seguinte acertar.
"""
import hashlib
import json
import os

from hdev import config as cfgmod

from . import constants

CACHE_DIR = os.path.join(".hdev", "cache", "judge")


def prompt_version():
    blob = (constants.PROMPT_VERSION + "\n" + constants.RUBRIC + "\n" + constants.PARTS_NOTE).encode("utf-8")
    return constants.PROMPT_VERSION + ":" + hashlib.sha256(blob).hexdigest()[:16]


def plan_sha(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _role(cfg, name):
    role = ((cfg or {}).get("roles") or {}).get(name) or {}
    if not isinstance(role, dict):
        role = {}
    model = role.get("model") or ""
    return role.get("cli") or "", cfgmod.model_provider(model) or "", model


def tests_mode(do_run_tests, tests_log):
    """off | run (--run-tests) | log (--tests-log)."""
    if do_run_tests:
        return "run"
    if tests_log:
        return "log"
    return "off"


def cache_key(base_sha, head_sha, plan_sha, provider, model, prompt_version, run_tests, package_sha,
              cli="", fallback_cli="", fallback_provider="", fallback_model=""):
    """(sha256, payload). `run_tests` é off, run ou log."""
    if not isinstance(run_tests, str):
        run_tests = "run" if run_tests else "off"
    payload = {
        "base_sha": base_sha or "",
        "head_sha": head_sha or "",
        "plan_sha": plan_sha or "",
        "cli": cli or "",
        "provider": provider or "",
        "model": model or "",
        "fallback_cli": fallback_cli or "",
        "fallback_provider": fallback_provider or "",
        "fallback_model": fallback_model or "",
        "prompt_version": prompt_version or "",
        "run_tests": run_tests,
        "package_sha": package_sha or "",
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest(), payload


def make_key(cfg, base_sha, head_sha, plan_text, package_sha, do_run_tests, tests_log):
    cli, provider, model = _role(cfg, "judge")
    fb_cli, fb_provider, fb_model = _role(cfg, "judge_fallback")
    return cache_key(
        base_sha, head_sha, plan_sha(plan_text), provider, model, prompt_version(),
        tests_mode(do_run_tests, tests_log), package_sha, cli=cli, fallback_cli=fb_cli,
        fallback_provider=fb_provider, fallback_model=fb_model)


def cacheable(result):
    """Pass ou fail com toda tentativa limpa. Unsure, uso, segredo e falha de CLI ficam de fora."""
    if not isinstance(result, dict) or result.get("verdict") not in ("pass", "fail"):
        return False
    attempts = result.get("attempts") or []
    if not attempts:
        return False
    for attempt in attempts:
        if not isinstance(attempt, dict):
            return False
        if attempt.get("status") or attempt.get("blocked"):
            return False
        if attempt.get("verdict") not in ("pass", "fail", "unsure"):
            return False
        if "seconds" not in attempt:
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
