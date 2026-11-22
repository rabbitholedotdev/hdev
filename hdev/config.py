"""Leitura de .hdev/config.json e provedor de cada modelo."""
import json
import os
import re
import shlex

# Provedor pelo nome do modelo (é o que importa para "juiz de outro provedor", não o nome da CLI).
_MODEL_PROVIDERS = [
    (re.compile(r"^(?:anthropic/)?claude-"), "anthropic"),
    (re.compile(r"^(?:openai/)?(?:gpt-|o\d|codex-)"), "openai"),
    (re.compile(r"^(?:google/)?gemini-"), "google"),
    (re.compile(r"^(?:xai/)?grok-"), "xai"),
]

# Provedores que cada CLI consegue rodar pela assinatura.
CLI_PROVIDERS = {
    "claude": {"anthropic"},
    "codex": {"openai"},
    "agy": {"google", "anthropic", "openai"},
    "grok": {"xai"},
}

# JSON Schema do veredito; entra no comando pelo marcador {schema}.
VERDICT_SCHEMA = json.dumps({
    "type": "object",
    "required": ["verdict", "reasons"],
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "fail", "unsure"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "criteria": {"type": "array", "items": {"type": "object", "properties": {
            "item": {"type": "string"}, "ok": {"type": "boolean"}}}},
    },
}, separators=(",", ":"))

# Como cada CLI recebe o pacote do juiz: stdin, ou o arquivo {prompt_file}. Papel sobrescreve com "command".
# grok: `-p/--single` exige o prompt como valor (revisão Codex, rodada 6); o pacote vai por --prompt-file.
DEFAULT_COMMANDS = {
    "codex": ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "-m", "{model}", "-"],
    "agy": ["agy", "-p", "--model", "{model}"],
    "claude": ["claude", "-p", "--model", "{model}"],
    "grok": ["grok", "--prompt-file", "{prompt_file}", "--model", "{model}", "--output-format", "json",
             "--json-schema", "{schema}"],
}


def model_provider(model):
    if not isinstance(model, str):
        return None
    for rx, provider in _MODEL_PROVIDERS:
        if rx.match(model.strip().lower()):
            return provider
    return None


def config_path(root):
    return os.path.join(root, ".hdev", "config.json")


# Tetos que o código impõe. `caps` no manifesto tem de ser igual; valor diferente falha o check.
# `skills` é o máximo visível por fase. No disco podem ser mais.
CAP_CEILING = {
    "agents": 60,
    "hooks": 5,
    "skills": 5,
    "subagents": 2,
    "progress": 2000,
    "context_initial": 15000,
}

# Chaves do repo. A release não as impõe ao app (a branch, os hooks, as skills, os tetos e a suíte são dele).
REPO_ONLY = ("base_branch", "hooks", "skills", "caps", "gates")


def legacy_error(data, where=".hdev/config.json"):
    """Erro se a config ainda traz o comando de teste antigo. Sem leitura dupla."""
    if not isinstance(data, dict):
        return None
    if "tests" in data:
        return "chave antiga tests em %s; use gates.fast e gates.full" % where
    judge = data.get("judge")
    if isinstance(judge, dict) and "tests_command" in judge:
        return "chave antiga judge.tests_command em %s; use gates.full" % where
    return None


def gate_command(cfg, which):
    """Comando de `gates.fast` ou `gates.full` (lista ou string), ou None."""
    gates = cfg.get("gates") if isinstance(cfg, dict) else None
    if not isinstance(gates, dict):
        return None
    cmd = gates.get(which)
    if isinstance(cmd, list) and cmd:
        return cmd
    if isinstance(cmd, str) and cmd.strip():
        return cmd
    return None


def gate_timeout(cfg, default):
    gates = cfg.get("gates") if isinstance(cfg, dict) else None
    if not isinstance(gates, dict) or "timeout" not in gates:
        return default
    try:
        return int(gates.get("timeout") or default)
    except (TypeError, ValueError):
        return default


def caps_error(data):
    """None se `caps` falta ou bate com o teto. Seção presente com valor diferente é erro."""
    if not isinstance(data, dict) or "caps" not in data:
        return None
    caps = data.get("caps")
    if not isinstance(caps, dict):
        return "caps precisa ser um objeto"
    for key, ceiling in CAP_CEILING.items():
        if caps.get(key) != ceiling:
            return "caps.%s é %r; o teto continua %s" % (key, caps.get(key), ceiling)
    return None


def _release_raw(root):
    """Dict da release, ou None se não há app ligado ou o arquivo não lê."""
    if not os.path.islink(os.path.join(root, ".harnessdev")):
        return None
    path = os.path.join(root, ".harnessdev", ".hdev", "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def load(root):
    """(config, erro). Erro é texto curto quando o arquivo falta, é inválido ou traz chave antiga."""
    path = config_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None, "falta .hdev/config.json"
    except ValueError as e:
        return None, ".hdev/config.json inválido: %s" % e
    if not isinstance(data, dict):
        return None, ".hdev/config.json precisa ser um objeto"
    err = legacy_error(data)
    if err:
        return None, err
    raw = _release_raw(root)
    if isinstance(raw, dict):
        err = legacy_error(raw, "release .hdev/config.json")
        if err:
            return None, err
    return merge(release_defaults(root), data), None


def release_defaults(root):
    """Config da release em uso (`.harnessdev/.hdev/config.json`), sem `core` nem chave de repo."""
    data = _release_raw(root)
    if not data:
        return {}
    data.pop("core", None)
    for key in REPO_ONLY:
        data.pop(key, None)
    return data


def merge(base, over):
    """Mescla recursiva: o que o app escreveu vence; o que ele não escreveu vem da release (F2-01)."""
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], value)
        else:
            out[key] = value
    return out


def validate_role(name, role):
    """(provedor, erro). Mesma regra no `hdev check` e antes de o `hdev judge` chamar alguém."""
    if not isinstance(role, dict):
        return None, "papel %s inválido" % name
    provider = model_provider(role.get("model"))
    if provider is None:
        return None, "papel %s: provedor desconhecido para o modelo %r" % (name, role.get("model"))
    cli = role.get("cli")
    if cli not in CLI_PROVIDERS:
        return None, "papel %s: CLI desconhecida %r" % (name, cli)
    if provider not in CLI_PROVIDERS[cli]:
        return None, "papel %s: a CLI %s não roda modelo %s (%s)" % (name, cli, provider, role.get("model"))
    return provider, None


def uses_prompt_file(role):
    cmd = role.get("command") or DEFAULT_COMMANDS.get(role.get("cli")) or []
    parts = [cmd] if isinstance(cmd, str) else cmd
    return any("{prompt_file}" in p for p in parts)


def role_command(role, prompt_file=""):
    cmd = role.get("command") or DEFAULT_COMMANDS.get(role.get("cli"))
    if not cmd:
        return None
    model = role.get("model", "")

    def fill(text, quote=lambda s: s):
        return (text.replace("{model}", quote(model)).replace("{schema}", quote(VERDICT_SCHEMA))
                .replace("{prompt_file}", quote(prompt_file)))

    if isinstance(cmd, str):  # vai pelo shell: valores entre aspas
        return fill(cmd, shlex.quote)
    return [fill(part) for part in cmd]
