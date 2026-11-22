"""Chama a CLI do papel e lê o veredito. Grok e Codex passam por aqui; o falso dos testes também."""
import os
import subprocess
import time

from hdev import cli_runtime
from hdev import config as cfgmod
from hdev import stop as stopmod
from hdev import CORE_ROOT
import sys

sys.path.insert(0, os.path.join(CORE_ROOT, "hooks"))
import _lib  # noqa: E402

from .verdict import parse_verdict, tokens_from

def execute(role_name, role, package, timeout, root, part=None):
    attempt = {"role": role_name, "cli": role.get("cli"), "model": role.get("model"),
               "provider": cfgmod.model_provider(role.get("model"))}
    if part:
        attempt["parte"] = part
    prompt_file = ""
    if cfgmod.uses_prompt_file(role):
        state = os.path.join(root, ".hdev", "state")
        os.makedirs(state, exist_ok=True)
        suffix = "%s-p%d" % (role_name, part) if part else role_name
        prompt_file = os.path.join(state, "judge-package-%s.txt" % suffix)
        with open(prompt_file, "w", encoding="utf-8") as f:
            f.write(package)
    cmd = cfgmod.role_command(role, prompt_file)
    cmd, env = cli_runtime.prepare_judge_call(cmd)
    started = time.monotonic()
    try:
        r = subprocess.run(cmd, input=package, shell=isinstance(cmd, str), capture_output=True, text=True,
                           timeout=timeout, env=env)
        output = (r.stdout or "") + "\n" + (r.stderr or "")
        attempt["exit"] = r.returncode
        parsed = parse_verdict(r.stdout or "") or parse_verdict(output)
        if r.returncode != 0:  # diagnóstico no registro, redigido antes de cortar
            # o texto inteiro, senão um segredo que atravessa o corte deixa o sufixo (revisão Codex, rodada 13)
            attempt["stderr_tail"] = _lib.redact(r.stderr or "")[-800:]
        if not (parsed and r.returncode == 0):
            kind = stopmod.judge_block_kind(output)
            if kind:
                attempt["blocked"] = kind
        if parsed and r.returncode != 0:
            # CLI que falhou não aprova nem reprova: vai ao segundo provedor (revisão Codex, rodada 5)
            attempt["status"] = "exit %d: veredito %s descartado" % (r.returncode, parsed["verdict"])
        elif parsed:
            attempt.update(parsed)
        else:
            attempt["status"] = "sem JSON de veredito (exit %d)" % r.returncode
            if attempt.get("blocked") == "login":
                attempt["status"] += "; parece login"
            elif attempt.get("blocked") == "rate":
                attempt["status"] += "; parece quota"
        attempt["tokens"] = tokens_from(output.replace(package, ""))  # CLI que ecoa o pacote não conta tokens dele
    except FileNotFoundError:
        attempt["status"] = "CLI não encontrada: %s" % (cmd[0] if isinstance(cmd, list) else cmd)
    except subprocess.TimeoutExpired:
        attempt["status"] = "timeout (%ds)" % timeout
    except (OSError, TypeError) as e:
        attempt["status"] = "erro ao chamar: %s" % e
    finally:
        if prompt_file:
            try:
                os.remove(prompt_file)
            except OSError:
                pass
    attempt["seconds"] = round(time.monotonic() - started, 2)
    return attempt
