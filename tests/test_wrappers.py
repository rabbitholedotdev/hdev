"""Wrappers Codex/Grok: argv e env no contrato da rotina, binário no PATH."""
import os
import unittest
from unittest import mock

from hdev import wrappers
from tests.helpers import BIN, ROOT, clean_env
import subprocess
import sys


class Cmd(unittest.TestCase):
    def test_codex_cmd_contrato_da_rotina(self):
        cmd = wrappers.codex_cmd("revise o diff", "/tmp/proj", model="gpt-5")
        self.assertEqual(cmd[0], "codex")
        self.assertEqual(cmd[1:7], ["exec", "--json", "--approve-for-me",
                                    "--skip-git-repo-check", "-C", "/tmp/proj"])
        self.assertEqual(cmd[-3:], ["-m", "gpt-5", "revise o diff"])

    def test_codex_bin_pelo_env(self):
        with mock.patch.dict(os.environ, {"HDEV_CODEX_BIN": "/opt/custom/codex"}):
            cmd = wrappers.codex_cmd("p", "/wrk")
        self.assertEqual(cmd[0], "/opt/custom/codex")

    def test_grok_cmd_usa_single_depois_das_flags(self):
        # não usar `-p` antes de --output-format: o -p come o próximo argumento
        cmd = wrappers.grok_cmd("goldfish da spec", model="grok-4.7")
        self.assertEqual(cmd[0], "grok")
        self.assertEqual(cmd[1:4], ["--output-format", "json", "--always-approve"])
        self.assertEqual(cmd[-4:], ["-m", "grok-4.7", "--single", "goldfish da spec"])
        self.assertNotIn("-p", cmd)

    def test_grok_env(self):
        env = wrappers.grok_env()
        self.assertEqual(env["GROK_FOLDER_TRUST"], "0")
        self.assertEqual(env["GROK_DISABLE_AUTOUPDATER"], "1")
        self.assertEqual(env["NO_BROWSER"], "1")

    def test_cli_sem_pedido_sai_1(self):
        r = subprocess.run([sys.executable, BIN, "codex-exec"], capture_output=True, text=True,
                           env=clean_env(), cwd=ROOT, timeout=15)
        self.assertEqual(r.returncode, 1)
        self.assertIn("informe o pedido", r.stderr)

    def test_cli_binario_ausente(self):
        env = clean_env(HDEV_GROK_BIN="/nao/existe/grok")
        r = subprocess.run([sys.executable, BIN, "grok-review", "--", "oi"],
                           capture_output=True, text=True, env=env, cwd=ROOT, timeout=15)
        self.assertEqual(r.returncode, 127)
        self.assertIn("não encontrado", r.stderr)


if __name__ == "__main__":
    unittest.main()
