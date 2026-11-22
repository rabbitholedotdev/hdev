"""CLI de `hdev library` e `hdev reflect`."""
import datetime
import json
import os

from hdev import base as basemod

from . import life
from . import pull as pullmod
from . import reflect as reflectmod
from . import store


def _today(value):
    if not value:
        return datetime.date.today()
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _unit(args):
    if getattr(args, "unit", None):
        return args.unit
    plan = getattr(args, "plan", None)
    if plan:
        return basemod.unit_id(plan)
    return None


def main_library(args):
    root = os.path.realpath(args.root)
    cmd = args.library_command
    today = _today(getattr(args, "today", None))
    if getattr(args, "today", None) and today is None:
        print("hdev library: --today pede YYYY-MM-DD")
        return 2
    if cmd == "pull":
        code, text = pullmod.command(
            root, spec=getattr(args, "spec", None), symptom=getattr(args, "symptom", None),
            k=getattr(args, "k", 5), budget=getattr(args, "budget", 1500),
            unit=getattr(args, "unit", None), tag=getattr(args, "tag", None))
        print(text, end="")
        return code
    if cmd == "status":
        print(life.format_status(root, today), end="")
        return 0
    if cmd == "tidy":
        if not os.path.isfile(store.index_path(root)):
            print("tidy: sem índice")
            return 0
        print(life.format_tidy(life.tidy_root(root, today)), end="")
        return 0
    print("hdev library: comando desconhecido")
    return 2


def main_reflect(args):
    root = os.path.realpath(args.root)
    unit = _unit(args)
    if not unit:
        print("hdev reflect: informe --unit ou --plan")
        return 2
    today = _today(getattr(args, "today", None))
    if getattr(args, "today", None) and today is None:
        print("hdev reflect: --today pede YYYY-MM-DD")
        return 2
    if args.add:
        path = args.add if os.path.isabs(args.add) else os.path.join(root, args.add)
        if not os.path.isfile(path) and os.path.isfile(args.add):
            path = args.add
        if not os.path.isfile(path):
            print("hdev reflect: --add não encontrado")
            return 1
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError) as exc:
            print("hdev reflect: JSON inválido: %s" % exc)
            return 1
        results = reflectmod.add_items(root, unit, payload, offline=bool(args.offline), today=today)
        print(reflectmod.format_add(results), end="")
        if any(row["action"] in ("gravado", "juntado") for row in results):
            return 0
        return 1
    text = reflectmod.digest(root, unit)
    if text is None:
        print("hdev reflect: sem pasta work/%s" % unit)
        return 1
    print(text, end="")
    return 0
