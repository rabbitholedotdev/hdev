"""Xray: estimativa determinística, teto e a linha do hdev check."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, hdev, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev import xray  # noqa: E402


def snap(folder):
    found = {}
    if not os.path.isdir(folder):
        return found
    for dirpath, _dirs, names in os.walk(folder):
        for name in names:
            path = os.path.join(dirpath, name)
            try:
                with open(path, "rb") as handle:
                    found[os.path.relpath(path, folder)] = handle.read()
            except OSError:
                found[os.path.relpath(path, folder)] = None
    return found


class Estimativa(unittest.TestCase):
    def test_conta_4_bytes_e_rotula(self):
        self.assertEqual(xray.estimate_tokens(""), 0)
        self.assertEqual(xray.estimate_tokens("abcd"), 1)
        self.assertEqual(xray.estimate_tokens("abcde"), 2)
        self.assertEqual(xray.estimate_tokens("á"), xray.estimate_tokens("á"))
        self.assertIn("estimativa", xray.METHOD)
        self.assertIn("4 bytes", xray.METHOD)

    def test_import_recursivo_nao_repete_e_nao_sai_do_repo(self):
        with TempDir() as d:
            write(os.path.join(d, "CLAUDE.md"), "@a.md\n")
            write(os.path.join(d, "a.md"), "@b.md\n@a.md\n")
            write(os.path.join(d, "b.md"), "@../fora.md\nola\n")
            write(os.path.join(os.path.dirname(d), "fora.md"), "segredo\n")
            labels = [label for label, _text in xray.claude_sources(d)]
            self.assertEqual(labels, ["CLAUDE.md", "a.md", "b.md"])
            blob = " ".join(text for _label, text in xray.claude_sources(d))
            self.assertNotIn("segredo", blob)

    def test_so_as_skills_da_fase(self):
        with TempDir() as d:
            write(os.path.join(d, ".claude", "skills", "hdev", "SKILL.md"),
                  "---\nname: hdev\ndescription: Uma.\n---\n")
            write(os.path.join(d, ".claude", "skills", "outra", "SKILL.md"),
                  "---\nname: outra\ndescription: Duas.\n---\n")
            write(os.path.join(d, ".hdev", "config.json"),
                  json.dumps({"phase": "F0", "skills": {"F0": ["hdev"]}}))
            names = [row["source"] for row in xray.measure(d)["sources"]]
            self.assertIn("skill:hdev", names)
            self.assertNotIn("skill:outra", names)


class Teto(unittest.TestCase):
    def test_repo_dentro_e_acima(self):
        antes = snap(os.path.join(ROOT, ".hdev", "state"))
        code, out = hdev("xray", "--max", "15000", "--root", ROOT)
        self.assertEqual(code, 0, out)
        self.assertIn("fonte", out)
        self.assertIn("total", out)
        self.assertIn("estimativa", out)
        self.assertIn("ritual", out)
        code, out = hdev("xray", "--max", "100", "--root", ROOT)
        self.assertEqual(code, 1, out)
        self.assertIn("passa de 100", out)
        self.assertEqual(snap(os.path.join(ROOT, ".hdev", "state")), antes)

    def test_check_falha_acima_do_teto(self):
        with TempDir() as d:
            write(os.path.join(d, "CLAUDE.md"), "a" * 60004)
            result = checkmod.check_xray(d)
            self.assertFalse(result.ok)
            self.assertIn("estimativa", result.detail)
            code, out = hdev("check", "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("[FALHA] xray:", out)

    def test_check_do_repo_tem_a_linha(self):
        code, out = hdev("check", "--root", ROOT)
        self.assertEqual(code, 0, out)
        self.assertIn("[ok] xray: estimativa ", out)
        self.assertIn("/15000", out)


if __name__ == "__main__":
    unittest.main()
