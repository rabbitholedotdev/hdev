"""Skills finas: description, Fora de escopo, references/ e um caso por skill."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402

FINA = """---
name: a
description: Faz uma coisa curta. Use quando pedirem a.
---

# a

## Passos
1. Rode `hdev check`. Leia `references/molde.md`.

## Fora de escopo
- não confundir com hdev.
"""


def nucleo(d, skill=FINA, phases=None, eval_text="Portão: x\n", ref=True):
    write(os.path.join(d, "hdev", "cli.py"), "# nucleo\n")
    write(os.path.join(d, ".hdev", "config.json"), json.dumps({"skills": phases or {"F0": ["a"]}}))
    write(os.path.join(d, ".claude", "skills", "a", "SKILL.md"), skill)
    if ref:
        write(os.path.join(d, ".claude", "skills", "a", "references", "molde.md"), "molde\n")
    if eval_text is not None:
        write(os.path.join(d, "evals", "skills", "a.md"), eval_text)


class Formato(unittest.TestCase):
    def test_skill_fina_passa(self):
        with TempDir() as d:
            nucleo(d)
            r = checkmod.check_skills(d)
            self.assertTrue(r.ok, r.detail)
            self.assertIn("F0 1/5", r.detail)
            self.assertIn("descriptions <= 200", r.detail)

    def test_sem_fora_de_escopo_falha(self):
        with TempDir() as d:
            nucleo(d, skill=FINA.replace("## Fora de escopo\n- não confundir com hdev.\n", ""))
            r = checkmod.check_skills(d)
            self.assertFalse(r.ok, r.detail)
            self.assertIn("Fora de escopo", r.detail)

    def test_sem_caso_falha(self):
        with TempDir() as d:
            nucleo(d, eval_text=None)
            r = checkmod.check_skills(d)
            self.assertFalse(r.ok, r.detail)
            self.assertIn("evals/skills/a.md", r.detail)

    def test_references_sem_arquivo_falha(self):
        with TempDir() as d:
            nucleo(d, ref=False)
            r = checkmod.check_skills(d)
            self.assertFalse(r.ok, r.detail)
            self.assertIn("references/", r.detail)

    def test_fase_com_seis_falha(self):
        with TempDir() as d:
            nucleo(d, phases={"F1": ["a", "b", "c", "d", "e", "f"]})
            r = checkmod.check_skills(d)
            self.assertFalse(r.ok, r.detail)
            self.assertIn("6", r.detail)


class Repo(unittest.TestCase):
    def test_cada_skill_tem_um_caso(self):
        folder = os.path.join(ROOT, ".claude", "skills")
        names = sorted(n for n in os.listdir(folder)
                       if os.path.isfile(os.path.join(folder, n, "SKILL.md")))
        self.assertGreaterEqual(len(names), 7)
        for name in names:
            path = os.path.join(ROOT, "evals", "skills", name + ".md")
            self.assertTrue(os.path.isfile(path), name)
            with open(path, encoding="utf-8") as f:
                self.assertIn("Portão", f.read(), name)

    def test_check_mostra_fases_e_teto_da_description(self):
        r = checkmod.check_skills(ROOT)
        self.assertTrue(r.ok, r.detail)
        self.assertIn("F0 1/5", r.detail)
        self.assertIn("F1 5/5", r.detail)
        self.assertIn("F2 5/5", r.detail)
        self.assertIn("descriptions <= 200", r.detail)
        for name in os.listdir(os.path.join(ROOT, ".claude", "skills")):
            path = os.path.join(ROOT, ".claude", "skills", name, "SKILL.md")
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as f:
                desc = checkmod.skill_description(f.read())
            self.assertTrue(desc and len(desc) <= 200, name)


if __name__ == "__main__":
    unittest.main()
