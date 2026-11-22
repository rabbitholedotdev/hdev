"""Trilha da unidade: fast (trivial) ou full. Grava work/<id>/state.json e não reescreve plan.md."""
import json
import os
import re

ID_RX = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FAST_PLAN = """# Plano — {id}

Spec: sem spec (trivial: um commit, sem dependência nova, sem mudança de contrato)

## Objetivo
{id}

## Critério de pronto
- `hdev check` verde.

## Abordagem
Trilha rápida (`hdev triage`).

## Passos
1. Escrever o teste que falha.
2. Implementar o mínimo.
3. `hdev check` verde.

## Fora de escopo
- Spec, review e trilha cheia.
"""


class TriageError(Exception):
    pass


def decide(trivial, full, one_commit, no_new_dependency, no_contract_change):
    """fast só com os três critérios (ou --trivial). --full vence. O resto é full."""
    if trivial:
        one_commit = no_new_dependency = no_contract_change = True
    fast = (not full) and bool(one_commit) and bool(no_new_dependency) and bool(no_contract_change)
    return {
        "track": "fast" if fast else "full",
        "one_commit": True if one_commit else None,
        "new_dependency": False if no_new_dependency else None,
        "contract_change": False if no_contract_change else None,
    }


def run(root, uid, trivial=False, full=False, one_commit=False, no_new_dependency=False,
        no_contract_change=False):
    if not isinstance(uid, str) or not ID_RX.match(uid):
        raise TriageError("id inválido: %s" % uid)
    root = os.path.realpath(root)
    folder = os.path.realpath(os.path.join(root, "work", uid))
    if not folder.startswith(root + os.sep):
        raise TriageError("id inválido: %s" % uid)
    os.makedirs(folder, exist_ok=True)
    state = {"id": uid}
    state.update(decide(trivial, full, one_commit, no_new_dependency, no_contract_change))
    path = os.path.join(folder, "state.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    plan_path = os.path.join(folder, "plan.md")
    created = False
    if os.path.isfile(plan_path):
        kept = True
    elif state["track"] == "fast":
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(FAST_PLAN.format(id=uid))
        created, kept = True, False
    else:
        kept = False
    return {"state": state, "plan_created": created, "plan_kept": kept,
            "plan": "work/%s/plan.md" % uid}


def main(args):
    try:
        res = run(args.root, args.id, args.trivial, args.full, args.one_commit, args.no_new_dependency,
                  args.no_contract_change)
    except TriageError as e:
        print("hdev triage: %s" % e)
        return 2
    print("hdev triage: %s track %s" % (res["state"]["id"], res["state"]["track"]))
    if res["plan_created"]:
        print("  plano %s" % res["plan"])
    elif res["plan_kept"]:
        print("  plano existente, não alterado")
    return 0
