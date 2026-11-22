#!/usr/bin/env python3
"""Lint stdlib do harness-dev.

Todo `.py` de hdev/, hooks/, tests/, bin/ e scripts/ tem que compilar, sem import não usado
(exceto `__init__.py` e nomes em `__all__`), sem espaço no fim da linha e sem tab na indentação.

Uso: python3 scripts/lint.py [--root DIR]
"""
import argparse
import ast
import os
import sys

DIRS = ("hdev", "hooks", "tests", "bin", "scripts")


def python_files(root):
    found = []
    for name in DIRS:
        base = os.path.join(root, name)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in filenames:
                if filename.endswith(".py"):
                    found.append(os.path.join(dirpath, filename))
    return sorted(found)


def _string_list(node):
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return None
    names = []
    for elt in node.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            names.append(elt.value)
        else:
            return None
    return names


class _Uses(ast.NodeVisitor):
    """Nomes importados, nomes lidos e os exportados em `__all__`."""

    def __init__(self):
        self.imported = []
        self.used = set()
        self.exported = set()

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name == "*":
                continue
            self.imported.append((alias.asname or alias.name.split(".")[0], node.lineno))

    def visit_ImportFrom(self, node):
        if node.module == "__future__":
            return
        for alias in node.names:
            if alias.name == "*":
                continue
            self.imported.append((alias.asname or alias.name, node.lineno))

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used.add(node.id)

    def _export(self, target, value):
        if isinstance(target, ast.Name) and target.id == "__all__" and value is not None:
            names = _string_list(value)
            if names is not None:
                self.exported.update(names)

    def visit_Assign(self, node):
        for target in node.targets:
            self._export(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        self._export(node.target, node.value)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._export(node.target, node.value)
        self.generic_visit(node)


def check_file(root, path):
    rel = os.path.relpath(path, root)
    problems = []
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except UnicodeDecodeError as exc:
        return [(rel, 1, "erro de sintaxe: %s" % exc)]
    for lineno, line in enumerate(text.splitlines(), 1):
        indent = line[:len(line) - len(line.lstrip(" \t"))]
        if "\t" in indent:
            problems.append((rel, lineno, "tab na indentação"))
        if line.endswith(" ") or line.endswith("\t"):
            problems.append((rel, lineno, "espaço no fim da linha"))
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        problems.append((rel, exc.lineno or 1, "erro de sintaxe: %s" % (exc.msg or "inválida")))
        return problems
    if os.path.basename(path) == "__init__.py":
        return problems
    uses = _Uses()
    uses.visit(tree)
    for name, lineno in uses.imported:
        if name not in uses.used and name not in uses.exported:
            problems.append((rel, lineno, "import não usado: %s" % name))
    return problems


def lint(root):
    problems = []
    for path in python_files(root):
        problems.extend(check_file(root, path))
    problems.sort(key=lambda item: (item[0], item[1], item[2]))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(prog="lint.py", description="Lint stdlib do harness-dev.")
    parser.add_argument("--root", default=None, help="raiz do repo ou de um fixture")
    args = parser.parse_args(argv)
    if args.root is None:
        root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    else:
        root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("lint: raiz inexistente: %s" % root)
        return 1
    problems = lint(root)
    for rel, lineno, msg in problems:
        print("%s:%d: %s" % (rel, lineno, msg))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
