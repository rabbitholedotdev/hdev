"""hdev spec check: 0 ok, 1 falha, 2 uso, 3 precisa do dono."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, hdev, write  # noqa: E402

OK = os.path.join(ROOT, "tests", "fixtures", "spec-ok.md")
SEM = os.path.join(ROOT, "tests", "fixtures", "spec-sem-defaults.md")
VAZIO = """# Spec

## Aceite
- `bin/hdev check` sai 0

## Fora de escopo
- Nada de hooks.

| Dúvida | Default | Reverter |
| --- | --- | --- |
| nome do arquivo | | manter o nome velho |
"""


class SpecCheck(unittest.TestCase):
    def test_fixture_ok_sai_0(self):
        code, out = hdev("spec", "check", OK)
        self.assertEqual(code, 0, out)
        self.assertIn("ok", out)

    def test_fixture_sem_defaults_sai_1(self):
        code, out = hdev("spec", "check", SEM)
        self.assertEqual(code, 1, out)
        self.assertIn("tabela", out)

    def test_arquivo_ausente_sai_2(self):
        code, out = hdev("spec", "check", os.path.join(ROOT, "tests", "fixtures", "nao-existe.md"))
        self.assertEqual(code, 2, out)

    def test_sem_subcommand_sai_2(self):
        code, _out = hdev("spec")
        self.assertEqual(code, 2)

    def test_default_vazio_sai_3(self):
        with TempDir() as d:
            path = os.path.join(d, "spec.md")
            write(path, VAZIO)
            code, out = hdev("spec", "check", path)
            self.assertEqual(code, 3, out)
            self.assertIn("dono", out)

    def test_aceite_sem_comando_sai_1(self):
        with TempDir() as d:
            path = os.path.join(d, "spec.md")
            write(path, "# S\n\n## Aceite\n- um parágrafo\n\n## Fora de escopo\n- x\n\n"
                   "| Dúvida | Default | Reverter |\n| --- | --- | --- |\n| a | b | c |\n")
            code, out = hdev("spec", "check", path)
            self.assertEqual(code, 1, out)
            self.assertIn("aceite", out)


if __name__ == "__main__":
    unittest.main()
