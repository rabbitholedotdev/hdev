"""Ambiente e wrapper opcional das CLIs do host para o hdev judge.

Alguns hosts não deixam o login do Codex em ~/.codex/auth.json. A conta padrão
vive em CODEX_HOME, e um wrapper (HDEV_ACCOUNT_WRAPPER) pode exportar isso para
o processo. Sem esse env, `codex exec` responde 401 (Missing bearer). O PATH
extra é HDEV_BIN_DIR, se o diretório existir. Não copia credencial entre
usuários: só aplica o env da conta do usuário corrente. Sem as variáveis, o
juiz chama a CLI que estiver no PATH.
"""
import os
import re
import shlex
import subprocess

from . import paths as pathmod

RATOEIRA_BIN = pathmod.bin_dir()
CONTA_CLAUDE = pathmod.account_wrapper()
CONTAS_CODEX = pathmod.codex_env_script()
ACCOUNT_CLIS = frozenset({"codex", "grok", "claude", "opencode"})
_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


def prepend_ratoeira_path(env, bin_dir=None):
    """Coloca HDEV_BIN_DIR no PATH, se o diretório existir e ainda não estiver lá."""
    bin_dir = RATOEIRA_BIN if bin_dir is None else bin_dir
    env = dict(env)
    if not os.path.isdir(bin_dir):
        return env
    path = env.get("PATH") or ""
    parts = path.split(os.pathsep) if path else []
    if bin_dir in parts:
        return env
    env["PATH"] = bin_dir + (os.pathsep + path if path else "")
    return env


def cli_basename(cmd):
    if not cmd:
        return ""
    if isinstance(cmd, str):
        try:
            parts = shlex.split(cmd)
        except ValueError:
            return ""
        first = parts[0] if parts else ""
    else:
        first = cmd[0] if cmd else ""
    return os.path.basename(first)


def needs_account_env(cmd):
    return cli_basename(cmd) in ACCOUNT_CLIS


def wrap_command(cmd, wrapper=None):
    """Prefixa o comando com o wrapper de conta quando o arquivo existe e a CLI precisa dele."""
    wrapper = CONTA_CLAUDE if wrapper is None else wrapper
    if not cmd or not needs_account_env(cmd):
        return cmd
    if not (os.path.isfile(wrapper) and os.access(wrapper, os.X_OK)):
        return cmd
    if isinstance(cmd, str):
        quoted = shlex.quote(wrapper)
        if cmd.startswith(quoted + " ") or cmd.startswith(wrapper + " "):
            return cmd
        return "%s %s" % (quoted, cmd)
    if cmd[0] == wrapper:
        return cmd
    return [wrapper, *list(cmd)]


def parse_account_exports(text):
    """Lê a saída de `node contas-codex.mjs env` (KEY='valor'; export KEY / unset KEY)."""
    updates, unsets = {}, set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        for stmt in line.split(";"):
            stmt = stmt.strip()
            if not stmt or stmt.startswith("export "):
                continue
            if stmt.startswith("unset "):
                name = stmt.split(None, 1)[1] if len(stmt.split()) > 1 else ""
                if _NAME.match(name):
                    unsets.add(name)
                    updates.pop(name, None)
                continue
            if "=" not in stmt:
                continue
            name, val = stmt.split("=", 1)
            if not _NAME.match(name):
                continue
            try:
                parts = shlex.split(val, posix=True)
            except ValueError:
                continue
            updates[name] = parts[0] if parts else ""
            unsets.discard(name)
    return updates, unsets


def apply_account_env(env, script=None):
    """Aplica CODEX_HOME da conta do usuário corrente, se ainda não estiver definido."""
    script = CONTAS_CODEX if script is None else script
    env = dict(env)
    if env.get("CODEX_HOME") or env.get("CODEX_SQLITE_HOME"):
        return env
    if not os.path.isfile(script):
        return env
    try:
        result = subprocess.run(
            ["node", script, "env"], capture_output=True, text=True, env=env, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return env
    if result.returncode != 0:
        return env
    updates, unsets = parse_account_exports(result.stdout or "")
    for key in unsets:
        env.pop(key, None)
    env.update(updates)
    return env


def prepare_judge_call(cmd, env=None, bin_dir=None, wrapper=None, script=None):
    """PATH extra + wrapper/env da conta, sem copiar credencial entre usuários."""
    bin_dir = RATOEIRA_BIN if bin_dir is None else bin_dir
    wrapper = CONTA_CLAUDE if wrapper is None else wrapper
    script = CONTAS_CODEX if script is None else script
    env = prepend_ratoeira_path(os.environ if env is None else env, bin_dir=bin_dir)
    if needs_account_env(cmd):
        if os.path.isfile(wrapper) and os.access(wrapper, os.X_OK):
            cmd = wrap_command(cmd, wrapper=wrapper)
        else:
            env = apply_account_env(env, script=script)
    return cmd, env
