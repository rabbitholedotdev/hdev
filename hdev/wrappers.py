"""Wrappers não interativos de Codex e Grok.

Bins vêm de HDEV_CODEX_BIN / HDEV_GROK_BIN (padrão: `codex` e `grok` no PATH).
O `-p` do Grok come o próximo argumento; usamos `--single` depois das outras flags.

v0.3.8 (ADR 0007): o pedido ganha uma 1ª linha `hdev <comando>: <título>` (é ela que vira a mensagem
do commit-turno, se houver commit); o agente aninhado recebe `HDEV_NESTED=1` (os hooks de sessão do
orquestrador se calam); revisor roda numa cópia isolada em /tmp (grok-review por padrão; codex-exec
com `--isolar`).
"""
import os
import subprocess
import sys

from . import isolar

CODEX_BIN = "codex"
GROK_BIN = "grok"

GROK_ENV = {
    "GROK_FOLDER_TRUST": "0",
    "GROK_DISABLE_AUTOUPDATER": "1",
    "NO_BROWSER": "1",
}
NESTED_ENV = {"HDEV_NESTED": "1"}
DEFAULT_TITLE = "revisão sem contexto"
TITLE_MAX = 60


def _bin(env_name, default):
    return os.environ.get(env_name) or default


def read_prompt(args):
    if getattr(args, "prompt_file", None):
        with open(args.prompt_file, encoding="utf-8") as f:
            return f.read()
    prompt = getattr(args, "prompt", None)
    if prompt == "-":
        return sys.stdin.read()
    if prompt:
        return prompt
    return None


def title_line(kind, titulo=None):
    """1ª linha do pedido: `hdev grok-review: <título>` (uma linha, sem `<` no começo, até TITLE_MAX)."""
    t = " ".join((titulo or "").split()).lstrip("<").strip() or DEFAULT_TITLE
    if len(t) > TITLE_MAX:
        t = t[: TITLE_MAX - 1].rstrip() + "…"
    return "hdev %s: %s" % (kind, t)


def with_title(kind, prompt, titulo=None):
    return "%s\n\n%s" % (title_line(kind, titulo), prompt)


def codex_cmd(prompt, cwd, model=None):
    cmd = [_bin("HDEV_CODEX_BIN", CODEX_BIN), "exec", "--json", "--approve-for-me",
           "--skip-git-repo-check", "-C", cwd]
    if model:
        cmd += ["-m", model]
    cmd.append(prompt)
    return cmd


def grok_cmd(prompt, model=None):
    # equivalente a `grok --output-format json --always-approve --single <pedido>`
    cmd = [_bin("HDEV_GROK_BIN", GROK_BIN), "--output-format", "json", "--always-approve"]
    if model:
        cmd += ["-m", model]
    cmd += ["--single", prompt]
    return cmd


def nested_env(base=None):
    env = dict(base if base is not None else os.environ)
    env.update(NESTED_ENV)
    return env


def grok_env():
    env = nested_env()
    env.update(GROK_ENV)
    return env


def codex_env():
    return nested_env()


def _run(cmd, cwd, env, timeout):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)
    except FileNotFoundError:
        print("hdev: binário não encontrado: %s" % cmd[0], file=sys.stderr)
        return 127
    except subprocess.TimeoutExpired:
        print("hdev: tempo esgotado", file=sys.stderr)
        return 124
    if r.stdout:
        sys.stdout.write(r.stdout)
        if not r.stdout.endswith("\n"):
            sys.stdout.write("\n")
    if r.returncode and r.stderr:
        sys.stderr.write(r.stderr[-4000:])
        if not r.stderr.endswith("\n"):
            sys.stderr.write("\n")
    return r.returncode


def _run_isolated(build, prompt, cwd, env, timeout):
    """Roda `build(prompt, cwd_da_copia)` numa cópia em /tmp; sem git, roda no lugar e avisa."""
    try:
        copia = isolar.Copia(cwd)
    except isolar.IsolarError as e:
        print("hdev: sem cópia isolada (%s); rodando na pasta atual" % e, file=sys.stderr)
        return _run(build(prompt, cwd), cwd, env, timeout)
    try:
        with copia:
            p = isolar.trocar_caminhos(prompt, copia.repo, copia.dir)
            return _run(build(p, copia.work), copia.work, env, timeout)
    except isolar.IsolarError as e:
        print("hdev: cópia isolada falhou (%s)" % e, file=sys.stderr)
        return 1


def main_codex(args):
    prompt = read_prompt(args)
    if not prompt:
        print("hdev codex-exec: informe o pedido (argumento, --prompt-file ou stdin)", file=sys.stderr)
        return 1
    prompt = with_title("codex-exec", prompt, getattr(args, "titulo", None))
    cwd = os.path.realpath(getattr(args, "cd", None) or os.getcwd())
    timeout = int(getattr(args, "timeout", 0) or 0) or 600
    model = getattr(args, "model", None)
    if getattr(args, "isolar", False):
        return _run_isolated(lambda p, c: codex_cmd(p, c, model), prompt, cwd, codex_env(), timeout)
    return _run(codex_cmd(prompt, cwd, model), cwd, codex_env(), timeout)


def main_grok(args):
    prompt = read_prompt(args)
    if not prompt:
        print("hdev grok-review: informe o pedido (argumento, --prompt-file ou stdin)", file=sys.stderr)
        return 1
    prompt = with_title("grok-review", prompt, getattr(args, "titulo", None))
    cwd = os.path.realpath(getattr(args, "cd", None) or os.getcwd())
    timeout = int(getattr(args, "timeout", 0) or 0) or 600
    model = getattr(args, "model", None)
    if getattr(args, "sem_isolar", False):
        return _run(grok_cmd(prompt, model), cwd, grok_env(), timeout)
    return _run_isolated(lambda p, c: grok_cmd(p, model), prompt, cwd, grok_env(), timeout)
