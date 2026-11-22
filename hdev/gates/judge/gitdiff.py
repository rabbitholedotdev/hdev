"""Diff, commits e texto do critério. O git que falha vira JudgeError, não diff vazio."""
import os
import re
import subprocess
import sys

from hdev import CORE_ROOT

from .constants import MAX_UNTRACKED_FILE, RENAME_ARGS

sys.path.insert(0, os.path.join(CORE_ROOT, "hooks"))
import _lib  # noqa: E402

class JudgeError(Exception):
    """Erro de uso ou de git que impede montar o pacote: o juiz não é chamado."""


def _git(root, *args, strict=False):
    """Saída do git. Com strict, falha vira JudgeError (diff que falhou não pode virar 'diff vazio')."""
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        if strict:
            raise JudgeError("git %s falhou: %s" % (args[0], e))
        return ""
    if r.returncode != 0 and strict:
        raise JudgeError("git %s falhou: %s" % (args[0], _lib.redact(r.stderr.strip())[-300:]))
    return r.stdout if r.returncode == 0 else ""


def resolve_commit(root, ref):
    """SHA do commit `ref`, ou JudgeError se não existir (revisão Codex, rodada 11)."""
    sha = _git(root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref).strip()
    if not sha:
        raise JudgeError("commit inexistente: %s" % ref)
    return sha


def criterion_from_plan(text):
    """Seção '## Critério de pronto' do plano; o plano inteiro se não houver a seção."""
    m = re.search(r"^##\s+Crit[ée]rio de pronto\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    return m.group(1).strip() if m else text.strip()


def filtered_diff(diff):
    """Remove do diff os blocos de arquivos sensíveis (vão só pelo nome)."""
    out, skipping = [], False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[-1]
            skipping = _lib.is_sensitive_path(path)
            out.append(line if not skipping else "%s\n[conteúdo omitido: arquivo sensível]" % line)
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out)


def _diff_args(base, head):
    if head:
        return ["%s..%s" % (base, head)]
    return [base or "HEAD"]


def commit_text(root, base=None, head=None):
    """Commits do intervalo e as branches que contêm o head (evidência de 'commit em master').

    Sem head e com base (a da unidade): os commits base..HEAD, que entram no diff junto com a árvore de trabalho."""
    if not head:
        if not base:
            return ""
        log = _git(root, "log", "--format=%h %s", "%s..HEAD" % base).strip()
        return "%s\n(mais a árvore de trabalho e os não rastreados)" % (log or "(sem commits depois da base)")
    log = _git(root, "log", "--format=%h %s", "%s..%s" % (base, head)).strip()
    branches = _git(root, "branch", "--format=%(refname:short)", "--contains", head).split()
    return "%s\nbranches que contêm %s: %s" % (log or "(sem commits)", head, ", ".join(branches) or "(nenhuma)")


def diff_stat(root, base=None, head=None):
    return _git(root, "diff", *RENAME_ARGS, "--stat=120", *_diff_args(base, head), "--").strip()


def collect_diff(root, base=None, head=None):
    # -M/-C explícitos (não dependem de diff.renames do usuário): mover arquivo não vira apagar + criar
    diff = _git(root, "diff", *RENAME_ARGS, *_diff_args(base, head), "--", strict=True)
    parts = [filtered_diff(diff)]
    if head:  # intervalo de commits: a árvore de trabalho não entra
        return "\n".join(p for p in parts if p)
    for rel in _git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        path = os.path.join(root, rel)
        if _lib.is_sensitive_path(rel):
            parts.append("=== novo (sensível, omitido): %s" % rel)
            continue
        try:
            if os.path.getsize(path) > MAX_UNTRACKED_FILE:
                parts.append("=== novo (grande, omitido): %s" % rel)
                continue
            with open(path, encoding="utf-8") as f:
                parts.append("=== novo: %s\n%s" % (rel, f.read()))
        except (OSError, UnicodeDecodeError):
            parts.append("=== novo (binário/ilegível): %s" % rel)
    return "\n".join(p for p in parts if p)
