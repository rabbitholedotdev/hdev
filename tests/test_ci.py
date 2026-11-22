"""F1-03: lint stdlib e o exit code de scripts/ci.

Só exercita o lint, direto ou com `scripts/ci --only lint`. Não roda o passo `testes`.
"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "scripts", "lint.py")
CI = os.path.join(ROOT, "scripts", "ci")


def write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class Ci(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def lint(self):
        return subprocess.run([sys.executable, LINT, "--root", self.root], capture_output=True,
                              text=True, timeout=30)

    def test_import_nao_usado(self):
        write(self.root, "hdev/ruim.py", "import os\n\nx = 1\n")
        result = self.lint()
        saida = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("import não usado", saida)
        self.assertIn("os", saida)

    def test_espaco_no_fim(self):
        write(self.root, "hooks/ruim.py", "x = 1 \n")
        result = self.lint()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("espaço no fim", result.stdout + result.stderr)

    def test_erro_de_sintaxe(self):
        write(self.root, "tests/ruim.py", "def f(\n")
        result = self.lint()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("erro de sintaxe", result.stdout + result.stderr)

    def test_tab_na_indentacao(self):
        write(self.root, "bin/tab.py", "def f():\n\treturn 1\n")
        result = self.lint()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tab na indentação", result.stdout + result.stderr)

    def test_arquivo_bom(self):
        write(self.root, "scripts/bom.py", "import os\n\n\ndef caminho():\n    return os.getcwd()\n")
        result = self.lint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_init_pode_importar_sem_uso(self):
        write(self.root, "hdev/__init__.py", "import os\n")
        result = self.lint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_nome_em_all_conta_como_uso(self):
        write(self.root, "hdev/mod.py", 'from os import path, getcwd\n__all__ = ["path"]\n')
        result = self.lint()
        saida = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("getcwd", saida)
        self.assertNotIn("import não usado: path", saida)

    def test_ci_devolve_exit_do_lint(self):
        write(self.root, "hdev/ruim.py", "import sys\n")
        direto = self.lint()
        via = subprocess.run([CI, "--only", "lint", "--root", self.root], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        self.assertNotEqual(direto.returncode, 0)
        self.assertEqual(via.returncode, direto.returncode)
        self.assertIn("ci: lint FALHOU", via.stdout)
        self.assertNotIn("ci: testes", via.stdout)
        self.assertNotIn("ci: check", via.stdout)

    def test_ci_only_lint_ok(self):
        write(self.root, "hooks/bom.py", "x = 1\n")
        via = subprocess.run([CI, "--only", "lint", "--root", self.root], cwd=ROOT,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(via.returncode, 0, via.stdout + via.stderr)
        self.assertIn("ci: lint ok", via.stdout)
        self.assertNotIn("ci: testes", via.stdout)
        self.assertNotIn("ci: check", via.stdout)


if __name__ == "__main__":
    unittest.main()
