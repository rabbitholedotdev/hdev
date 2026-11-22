"""Provedor xai pela CLI grok. No núcleo é o papel `judge` (modelo grok-4.7).

O pacote vai em `--prompt-file` quando o comando do papel traz `{prompt_file}` (o padrão).
A chamada em si é `invoke.execute`: o falso dos testes e o wrapper da conta continuam um só caminho.
"""
from .invoke import execute

CLI = "grok"
PROVIDER = "xai"


def matches(role):
    return isinstance(role, dict) and role.get("cli") == CLI


def call(role_name, role, package, timeout, root, part=None):
    return execute(role_name, role, package, timeout, root, part=part)
