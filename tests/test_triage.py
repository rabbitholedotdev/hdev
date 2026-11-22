"""hdev triage: trilha fast ou full em work/<id>/state.json, sem reescrever plan.md."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import TempDir, hdev, read_json, write  # noqa: E402


def state_of(d, uid):
    return read_json(os.path.join(d, "work", uid, "state.json"))


def plan_of(d, uid):
    return os.path.join(d, "work", uid, "plan.md")


class Triage(unittest.TestCase):
    def test_trivial_cria_state_e_plano_e_reexecutar_converge(self):
        with TempDir() as d:
            code, out = hdev("triage", "--id", "subtrair", "--trivial", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("fast", out)
            state = state_of(d, "subtrair")
            self.assertEqual(state["id"], "subtrair")
            self.assertEqual(state["track"], "fast")
            self.assertIs(state["one_commit"], True)
            self.assertIs(state["new_dependency"], False)
            self.assertIs(state["contract_change"], False)
            plan = plan_of(d, "subtrair")
            with open(plan, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("Spec: sem spec", text)
            with open(os.path.join(d, "work", "subtrair", "state.json"), encoding="utf-8") as f:
                raw = f.read()
            code, out = hdev("triage", "--id", "subtrair", "--trivial", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("não alterado", out)
            with open(plan, encoding="utf-8") as f:
                self.assertEqual(f.read(), text)
            with open(os.path.join(d, "work", "subtrair", "state.json"), encoding="utf-8") as f:
                self.assertEqual(f.read(), raw)

    def test_tres_criterios_viram_fast_e_um_faltando_fica_full(self):
        with TempDir() as d:
            code, out = hdev("triage", "--id", "inf-006-foo", "--one-commit", "--no-new-dependency",
                             "--no-contract-change", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertEqual(state_of(d, "inf-006-foo")["track"], "fast")
            with open(plan_of(d, "inf-006-foo"), encoding="utf-8") as f:
                self.assertIn("Spec: sem spec", f.read())
        with TempDir() as d:
            code, out = hdev("triage", "--id", "inf-006-foo", "--one-commit", "--no-new-dependency", "--root", d)
            self.assertEqual(code, 0, out)
            state = state_of(d, "inf-006-foo")
            self.assertEqual(state["track"], "full")
            self.assertIs(state["one_commit"], True)
            self.assertIs(state["new_dependency"], False)
            self.assertIsNone(state["contract_change"])
            self.assertFalse(os.path.exists(plan_of(d, "inf-006-foo")))

    def test_sem_flags_ou_full_nao_cria_plano(self):
        with TempDir() as d:
            code, out = hdev("triage", "--id", "v2-pr2-work-tree", "--root", d)
            self.assertEqual(code, 0, out)
            state = state_of(d, "v2-pr2-work-tree")
            self.assertEqual(state["track"], "full")
            self.assertIsNone(state["one_commit"])
            self.assertIsNone(state["new_dependency"])
            self.assertIsNone(state["contract_change"])
            self.assertFalse(os.path.exists(plan_of(d, "v2-pr2-work-tree")))
            code, out = hdev("triage", "--id", "v2-pr2-work-tree", "--full", "--one-commit",
                             "--no-new-dependency", "--no-contract-change", "--root", d)
            self.assertEqual(code, 0, out)
            state = state_of(d, "v2-pr2-work-tree")
            self.assertEqual(state["track"], "full")
            self.assertIs(state["one_commit"], True)
            self.assertIs(state["new_dependency"], False)
            self.assertIs(state["contract_change"], False)
            self.assertFalse(os.path.exists(plan_of(d, "v2-pr2-work-tree")))

    def test_nao_reescreve_plano_existente_nem_ao_trocar_trilha(self):
        with TempDir() as d:
            write(plan_of(d, "subtrair"), "NAO_MEXER\n")
            code, out = hdev("triage", "--id", "subtrair", "--trivial", "--root", d)
            self.assertEqual(code, 0, out)
            with open(plan_of(d, "subtrair"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "NAO_MEXER\n")
            self.assertEqual(state_of(d, "subtrair")["track"], "fast")
            code, out = hdev("triage", "--id", "subtrair", "--full", "--root", d)
            self.assertEqual(code, 0, out)
            with open(plan_of(d, "subtrair"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "NAO_MEXER\n")
            self.assertEqual(state_of(d, "subtrair")["track"], "full")

    def test_id_invalido(self):
        with TempDir() as d:
            for bad in ("../x", "a/b", "Foo", "", "a_b", ".", ".."):
                code, out = hdev("triage", "--id", bad, "--trivial", "--root", d)
                self.assertNotEqual(code, 0, "%s -> %s" % (bad, out))
                self.assertFalse(os.path.exists(os.path.join(d, "work", "state.json")))


if __name__ == "__main__":
    unittest.main()
