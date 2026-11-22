"""Monta o prompt que a release entrega na raiz.

O app instalado lê `.harnessdev/PROMPT-ORCHESTRATOR.md`. A fonte é
`harness/prompts/orchestrator.md` mais `_shared/`. Tag antiga, sem essa pasta,
não é reescrita: o arquivo do `git archive` fica.
"""
import os

PROMPTS = os.path.join("harness", "prompts")
ROLE = "orchestrator.md"
SHARED = (
    os.path.join("_shared", "style.md"),
    os.path.join("_shared", "safety.md"),
    os.path.join("_shared", "stop-list.md"),
)
SHIPPED = "PROMPT-ORCHESTRATOR.md"
BANNER = ("<!-- compat: montado na instalação da release; "
          "fonte harness/prompts/orchestrator.md + _shared/ -->\n")


class PromptError(Exception):
    pass


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def assemble(root):
    """Texto do prompt compat, ou None se este núcleo não tem o papel do orquestrador."""
    base = os.path.join(root, PROMPTS)
    role = os.path.join(base, ROLE)
    if not os.path.isfile(role):
        return None
    parts = [_read(role)]
    missing = []
    for rel in SHARED:
        path = os.path.join(base, rel)
        if not os.path.isfile(path):
            missing.append(os.path.join(PROMPTS, rel).replace(os.sep, "/"))
            continue
        parts.append(_read(path))
    if missing:
        raise PromptError("falta %s" % ", ".join(missing))
    return BANNER + "\n" + "\n".join(part.rstrip() + "\n" for part in parts)


def write_shipped(root):
    """Grava PROMPT-ORCHESTRATOR.md em `root` quando há papel para montar. Devolve o caminho ou None."""
    text = assemble(root)
    if text is None:
        return None
    dest = os.path.join(root, SHIPPED)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)
    return dest
