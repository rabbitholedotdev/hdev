"""F1-03: scripts/run-grok.sh com um grok falso (sem rede, sem conta)."""
import os
import stat
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "scripts", "run-grok.sh")

FAKE = """#!/bin/sh
printf '%s\\n' "$@" > "$HDEV_FAKE_ARGS"
echo fumaca > feito.txt
git add feito.txt && git -c user.email=t@t -c user.name=t commit -qm "feat: fake" && echo ok
"""


def sh(*args, cwd=None):
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True, check=True).stdout


class RunGrok(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.main, self.wt = os.path.join(t, "main"), os.path.join(t, "wt")
        os.makedirs(os.path.join(self.main, ".hdev"))
        sh("git", "init", "-q", "-b", "master", self.main)
        with open(os.path.join(self.main, ".hdev", "config.json"), "w") as f:
            f.write('{"roles": {"isolated": {"cli": "grok", "model": "grok-4.7-build-fast"}}}')
        with open(os.path.join(self.main, "PROMPT.md"), "w") as f:
            f.write("faça\n")
        sh("git", "add", ".", cwd=self.main)
        sh("git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base", cwd=self.main)
        self.fake = os.path.join(t, "grok")
        with open(self.fake, "w") as f:
            f.write(FAKE)
        os.chmod(self.fake, os.stat(self.fake).st_mode | stat.S_IEXEC)
        self.args = os.path.join(t, "args.txt")

    def tearDown(self):
        self.tmp.cleanup()

    def run_runner(self):
        env = dict(os.environ, HDEV_MAIN=self.main, HDEV_GROK_WORKTREE=self.wt, HDEV_GROK_BRANCH="grok/ci",
                   HDEV_GROK_BIN=self.fake, HDEV_GROK_WRAPPER="/nao/existe", HDEV_FAKE_ARGS=self.args,
                   XAI_API_KEY="nao-deve-passar")
        return subprocess.run([RUNNER, os.path.join(self.main, "PROMPT.md")], env=env, capture_output=True,
                              text=True, timeout=60)

    def test_uma_rodada_no_worktree_proprio(self):
        r = self.run_runner()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("START", r.stdout)
        self.assertIn("END", r.stdout)
        self.assertEqual(sh("git", "branch", "--show-current", cwd=self.wt).strip(), "grok/ci")
        self.assertIn("feat: fake", sh("git", "log", "--oneline", "grok/ci", cwd=self.main))
        self.assertNotIn("feat: fake", sh("git", "log", "--oneline", "master", cwd=self.main))

    def test_nao_interativo_com_modelo_da_config_e_negacoes(self):
        self.run_runner()
        with open(self.args) as f:
            args = f.read().split("\n")
        self.assertIn("--prompt-file", args)
        self.assertEqual(args[args.index("-m") + 1], "grok-4.7-build-fast")
        self.assertEqual(args[args.index("--cwd") + 1], self.wt)
        for rule in ("Bash(git push:*)", "Bash(sudo:*)", "Bash(curl:*)"):
            self.assertIn(rule, args)

    def test_para_em_waiting(self):
        os.makedirs(os.path.join(self.main, "docs"))
        with open(os.path.join(self.main, "docs", "WAITING.md"), "w") as f:
            f.write("parado\n")
        r = self.run_runner()
        self.assertEqual(r.returncode, 3)
        self.assertFalse(os.path.exists(self.wt))

    def test_exige_prompt_explicito(self):
        env = dict(os.environ, HDEV_MAIN=self.main, HDEV_GROK_WORKTREE=self.wt, HDEV_GROK_BRANCH="grok/ci",
                   HDEV_GROK_BIN=self.fake, HDEV_GROK_WRAPPER="/nao/existe", HDEV_FAKE_ARGS=self.args)
        r = subprocess.run([RUNNER], env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("uso: scripts/run-grok.sh <prompt.md>", r.stderr)
        self.assertNotIn("PROMPT-GROK-CI", r.stdout + r.stderr)
        self.assertFalse(os.path.exists(self.wt))

    def test_chave_de_api_nao_chega_ao_grok(self):
        fake_env = os.path.join(self.tmp.name, "env.txt")
        with open(self.fake, "a") as f:
            f.write('env > "%s"\n' % fake_env)
        self.run_runner()
        with open(fake_env) as f:
            self.assertNotIn("XAI_API_KEY", f.read())


if __name__ == "__main__":
    unittest.main()
