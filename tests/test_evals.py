"""Casos mecânicos em evals/tasks/<id>/task.json.

`steps`, quando existe, é o cenário antigo (núcleo de teste, tag v9.9.9).
Sem `steps`, roda `acceptance`.
"""
import glob
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, make_core, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import eval as evalmod  # noqa: E402



def tracked_tasks(root):
    """Só caso commitado ou no índice, como no clone limpo do fechar.

    Fora da base, o `hdev fechar` deixa `evals/tasks/<id>/task.json` no worktree, sem commit (PRD, Evals e xray).
    """
    r = subprocess.run(["git", "-C", root, "ls-files", "-z", "--", "evals/tasks/*/task.json"],
                       capture_output=True, text=True)
    if r.returncode != 0:  # fora de um repo git: o glob de antes
        return sorted(glob.glob(os.path.join(root, "evals", "tasks", "*", "task.json")))
    return sorted(os.path.join(root, p) for p in r.stdout.split("\0") if p)


TASKS = tracked_tasks(ROOT)


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def run_case(case):
    """Lista de falhas (vazia = caso verde)."""
    steps = case.get("steps") or case.get("acceptance") or []
    with TempDir() as base:
        core = make_core(base)
        tmp = os.path.join(base, "app")
        os.makedirs(tmp)
        failures, _codes = evalmod.execute_steps(steps, tmp, core, tmp, invoke=lambda args: hdev(*args))
    return failures


class Evals(unittest.TestCase):
    def test_existe_ao_menos_um_caso(self):
        self.assertTrue(TASKS)
        self.assertFalse(os.path.isdir(os.path.join(ROOT, "evals", "cases")))

    def test_formato(self):
        ids = []
        for path in TASKS:
            case = load(path)
            ids.append(case["id"])
            self.assertEqual(case["repo"], ".")
            self.assertTrue(case.get("base_sha"))
            self.assertIn("acceptance", case)
            self.assertIn("caps", case)
            self.assertEqual(os.path.basename(os.path.dirname(path)), case["id"])
        self.assertEqual(ids, ["ratoeira-app-new-check", "smoke-init-check"])

    def test_smoke_guarda_a_tag_falsa(self):
        case = load(os.path.join(ROOT, "evals", "tasks", "smoke-init-check", "task.json"))
        self.assertIn("v9.9.9", json.dumps(case["steps"]))
        self.assertNotIn("v9.9.9", json.dumps(case["acceptance"]))

    def test_only_committed_cases(self):
        with TempDir() as d:
            write(os.path.join(d, "evals", "tasks", "a", "task.json"), "{}\n")
            git(d, "init", "-q")
            git(d, "add", "-A")
            git(d, "commit", "-q", "-m", "a")
            write(os.path.join(d, "evals", "tasks", "b", "task.json"), "{}\n")
            self.assertEqual(tracked_tasks(d), [os.path.join(d, "evals", "tasks", "a", "task.json")])

    def test_casos(self):
        for path in TASKS:
            case = load(path)
            with self.subTest(case=case["id"]):
                self.assertEqual(run_case(case), [])


if __name__ == "__main__":
    unittest.main()
