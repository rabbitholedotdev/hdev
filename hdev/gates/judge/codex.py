"""Fallback Codex: papel `roles.judge_fallback` com CLI `codex` (provedor openai).

Também atende um papel `judge` cuja CLI é codex (os testes apontam o falso assim).
Stdin, sem `--prompt-file`, salvo se o comando do papel pedir. A chamada é `invoke.execute`.
"""
from .invoke import execute

CLI = "codex"
ROLE = "judge_fallback"


def matches(role):
    return isinstance(role, dict) and role.get("cli") == CLI


def call(role_name, role, package, timeout, root, part=None):
    return execute(role_name, role, package, timeout, root, part=part)
