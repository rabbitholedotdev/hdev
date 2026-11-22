"""hdev jev — decisões tipadas no TypeSafe System One (Jev).

Não gera texto. Envia state + perguntas e devolve Choice/Score/Noul.
A chave nunca vai a stdout, log ou exceção: vem de TYPESAFE_API_KEY ou de
um helper de cofre (HDEV_KEY_HELPER, padrão `op`) com uma referência op://.
Sem a chave, sai com código 2 e JSON de degradação — o fluxo segue sem Jev.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

from . import config as cfgmod
from . import stop as stopmod

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
DEFAULT_MODEL = "jev-latest"
DEFAULT_REF = "op://Vault/jev-api/credential"
CHAVE = "op"
MISSING = 2

# Vários juízos no mesmo state: barato e paralelo (docs.typesafe.ai/primitives).
PRESETS = {
    "rotear": {
        "worker": {
            "type": "choice",
            "instructions": "Which worker should handle this coding task next?",
            "criteria": {
                "haiku": "Search, read, or a small lookup; no production code edits",
                "sonnet": "Implement one spec item with TDD (test first, then minimal code)",
                "codex": "Goldfish review of a spec or a diff, or an OpenAI-side implementation",
                "grok": "Isolated review or judge-style check, no implementation",
            },
        },
        "precisa_humano": {
            "type": "noul",
            "instructions": "Does this task need a human decision before an agent proceeds?",
        },
    },
    "revisar-diff": {
        "risco": {
            "type": "score",
            "instructions": "How risky is this diff relative to the spec and plan?",
            "criteria": [
                "Low risk: small, in-scope, no secrets or destructive paths",
                "Medium risk: some uncertainty, but no clear safety issue",
                "High risk: secrets, permissions, data exposure, or clear scope break",
            ],
        },
        "pronto_para_juiz": {
            "type": "noul",
            "instructions": "The diff is complete enough to run the hard judge (hdev judge --run-tests).",
        },
        "precisa_humano": {
            "type": "noul",
            "instructions": "A human should review or decide before closing this change.",
        },
    },
    "humano": {
        "precisa_humano": {
            "type": "noul",
            "instructions": "A human should review or decide before an agent proceeds.",
        },
    },
    "handoff": {
        "unidade_fechada": {
            "type": "noul",
            "instructions": "This is a coherent finished unit of work that can be handed to a new session.",
        },
        "precisa_humano": {
            "type": "noul",
            "instructions": "A human should review before handing off or continuing.",
        },
    },
}

# Limiares no código (não no modelo). Noul perto de 0.5 é incerto.
NOUL_SIM = 0.7
NOUL_NAO = 0.3


def settings(root=None):
    data, _ = cfgmod.load(root) if root else ({}, None)
    jev = (data or {}).get("jev") or {}
    ref = os.environ.get("HDEV_JEV_REF") or jev.get("ref") or DEFAULT_REF
    model = os.environ.get("HDEV_JEV_MODEL") or jev.get("model") or DEFAULT_MODEL
    chave = (os.environ.get("HDEV_KEY_HELPER") or os.environ.get("HDEV_RATOEIRA_CHAVE")
             or jev.get("chave") or CHAVE)
    return {"ref": ref, "model": model, "chave": chave}


def resolve_key(cfg):
    """Devolve a chave ou None. Nunca imprime o valor."""
    env = (os.environ.get("TYPESAFE_API_KEY") or "").strip()
    if env:
        return env
    chave, ref = cfg["chave"], cfg["ref"]
    try:
        r = subprocess.run([chave, ref], capture_output=True, text=True, timeout=60,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (r.stdout or "").strip()
    if r.returncode == 0 and value:
        return value
    return None


def call_systemone(state, questions, key, model, opener=None):
    body = json.dumps({"model": model, "state": state, "questions": questions}, ensure_ascii=False).encode()
    req = urllib.request.Request(ENDPOINT, data=body, method="POST",
                                 headers={"Authorization": "Bearer " + key,
                                          "Content-Type": "application/json",
                                          "Accept": "application/json"})
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(req, timeout=30) as resp:
            raw = resp.read()
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as e:
        # não inclui o corpo/cabeçalho: pode ecoar a chave em eco invertido
        raise RuntimeError("TypeSafe HTTP %s" % e.code) from None
    except urllib.error.URLError as e:
        raise RuntimeError("TypeSafe indisponível") from None
    if status >= 400:
        raise RuntimeError("TypeSafe HTTP %s" % status)
    try:
        return json.loads(raw.decode())
    except ValueError:
        raise RuntimeError("TypeSafe respondeu JSON inválido") from None


def advice(preset, answers, state=None):
    """Compõe os números em orientação para o orquestrador (docs: combine in code).

    ask_human só fica true na lista fechada (2FA/login ou ação destrutiva), mesmo com noul alto.
    Fora dela, vira decisão registrada e o fluxo segue.
    """
    out = {}
    if not isinstance(answers, dict):
        return out
    worker = answers.get("worker") or {}
    if worker.get("type") == "choice" and worker.get("choice"):
        out["worker"] = worker["choice"]
    risco = answers.get("risco") or {}
    if risco.get("type") == "score" and isinstance(risco.get("score"), (int, float)):
        out["risco"] = risco["score"]
    text = stopmod.state_text(state)
    for key, dest in (("precisa_humano", "ask_human"), ("pronto_para_juiz", "run_judge"),
                      ("unidade_fechada", "unit_closed")):
        item = answers.get(key) or {}
        if item.get("type") == "noul" and isinstance(item.get("noul"), (int, float)):
            n = item["noul"]
            if n >= NOUL_SIM:
                if dest == "ask_human" and stopmod.classify(text) is None:
                    out[dest] = False
                    out["recorded_decision"] = stopmod.RECORDED
                else:
                    out[dest] = True
            elif n <= NOUL_NAO:
                out[dest] = False
            else:
                out[dest] = None  # incerto
    return out


def load_state(args):
    if getattr(args, "state_file", None):
        with open(args.state_file, encoding="utf-8") as f:
            text = f.read()
        try:
            return json.loads(text)
        except ValueError:
            return text
    if getattr(args, "state", None) is not None:
        if args.state == "-":
            text = sys.stdin.read()
            try:
                return json.loads(text)
            except ValueError:
                return text
        return args.state
    return None


def missing_payload(cfg, preset):
    return {"ok": False, "reason": "missing_key",
            "hint": "crie ou aponte a chave: %s %r (ou TYPESAFE_API_KEY / HDEV_JEV_REF)" % (cfg["chave"], cfg["ref"]),
            "preset": preset, "ref": cfg["ref"]}


def run(args):
    preset = args.preset
    questions = PRESETS[preset]
    state = load_state(args)
    if state is None or state == "":
        print("hdev jev: informe --state, --state-file ou state no stdin", file=sys.stderr)
        return 1
    root = getattr(args, "root", None)
    cfg = settings(root)
    if getattr(args, "model", None):
        cfg["model"] = args.model
    if getattr(args, "ref", None):
        cfg["ref"] = args.ref
    if getattr(args, "dry_run", False):
        payload = {"ok": True, "dry_run": True, "model": cfg["model"], "preset": preset,
                   "endpoint": ENDPOINT, "questions": questions, "state": state}
        print(json.dumps(payload, ensure_ascii=False, indent=2 if not getattr(args, "json", False) else None)
              if not getattr(args, "json", False) else json.dumps(payload, ensure_ascii=False))
        return 0
    key = resolve_key(cfg)
    if not key:
        payload = missing_payload(cfg, preset)
        print(json.dumps(payload, ensure_ascii=False))
        print("hdev jev: chave ausente; o fluxo segue sem Jev. " + payload["hint"], file=sys.stderr)
        return MISSING
    try:
        data = call_systemone(state, questions, key, cfg["model"])
    except RuntimeError as e:
        print("hdev jev: %s" % e, file=sys.stderr)
        return 1
    finally:
        key = None
    answers = data.get("answers") if isinstance(data, dict) else None
    adv = advice(preset, answers or {}, state=state)
    if adv.get("recorded_decision") and root:
        stopmod.append_decision(root, adv["recorded_decision"])
    payload = {"ok": True, "preset": preset, "model": data.get("model") if isinstance(data, dict) else cfg["model"],
               "answers": answers, "advice": adv,
               "usage": data.get("usage") if isinstance(data, dict) else None}
    print(json.dumps(payload, ensure_ascii=False, indent=None if getattr(args, "json", True) else 2))
    return 0


def main(args):
    return run(args)
