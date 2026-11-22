"""Prompts por papel: uma lista de parada, e a release ainda entrega PROMPT-ORCHESTRATOR.md."""
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, make_core, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev import config as cfgmod  # noqa: E402
from hdev import prompts  # noqa: E402
from hdev import release  # noqa: E402

ROLES = ("orchestrator.md", "executor.md", "implementer.md", "reviewer.md")
STOP = os.path.join("harness", "prompts", "_shared", "stop-list.md")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Lista(unittest.TestCase):
    def test_quatro_papeis_citam_a_lista(self):
        found = []
        for name in ROLES:
            path = os.path.join(ROOT, "harness", "prompts", name)
            self.assertTrue(os.path.isfile(path), name)
            text = _read(path)
            self.assertIn("stop-list.md", text, name)
            self.assertLessEqual(len(text.splitlines()), 120, name)
            found.append(path)
        self.assertGreaterEqual(len(found), 4)

    def test_estilo_e_uma_linha(self):
        text = _read(os.path.join(ROOT, "harness", "prompts", "_shared", "style.md"))
        self.assertEqual(len(text.splitlines()), 1)
        self.assertTrue(text.strip())

    def test_raiz_sem_prompt(self):
        names = [n for n in os.listdir(ROOT) if n.startswith("PROMPT-") and n.endswith(".md")]
        self.assertEqual(names, [])

    def test_agents_cabe_em_60(self):
        lines = _read(os.path.join(ROOT, "AGENTS.md")).splitlines()
        self.assertLessEqual(len(lines), 60)
        self.assertEqual(cfgmod.CAP_CEILING["agents"], 60)
        self.assertEqual(cfgmod.CAP_CEILING["hooks"], 5)
        self.assertEqual(cfgmod.CAP_CEILING["skills"], 5)
        self.assertEqual(cfgmod.CAP_CEILING["subagents"], 2)
        self.assertEqual(cfgmod.CAP_CEILING["progress"], 2000)
        self.assertEqual(cfgmod.CAP_CEILING["context_initial"], 15000)

    def test_check_do_repo_aceita_a_lista_unica(self):
        result = checkmod.check_prompts(ROOT)
        self.assertTrue(result.ok, result.detail)

    def test_marcador_em_outro_md_falha(self):
        with TempDir() as d:
            write(os.path.join(d, STOP), "# Parada\n\n## stop-list\n\n- 2FA\n")
            write(os.path.join(d, "harness", "prompts", "_shared", "safety.md"), "# Segurança\n\nx\n")
            write(os.path.join(d, "harness", "prompts", "_shared", "style.md"), "curto\n")
            for name in ROLES:
                write(os.path.join(d, "harness", "prompts", name), "ver _shared/stop-list.md\n")
            ok = checkmod.check_prompts(d)
            self.assertTrue(ok.ok, ok.detail)
            write(os.path.join(d, "AGENTS.md"), "## stop-list\n")
            bad = checkmod.check_prompts(d)
            self.assertFalse(bad.ok, bad.detail)
            self.assertIn("AGENTS.md", bad.detail)

    def test_papel_longo_falha(self):
        with TempDir() as d:
            write(os.path.join(d, STOP), "# Parada\n\n## stop-list\n\n- 2FA\n")
            write(os.path.join(d, "harness", "prompts", "_shared", "safety.md"), "# Segurança\n")
            write(os.path.join(d, "harness", "prompts", "_shared", "style.md"), "curto\n")
            for name in ROLES:
                write(os.path.join(d, "harness", "prompts", name), "ver _shared/stop-list.md\n")
            write(os.path.join(d, "harness", "prompts", "orchestrator.md"),
                  "ver _shared/stop-list.md\n" + ("x\n" * 120))
            bad = checkmod.check_prompts(d)
            self.assertFalse(bad.ok, bad.detail)
            self.assertIn("120", bad.detail)

    def test_app_sem_a_lista_na_raiz_passa(self):
        with TempDir() as d:
            os.symlink("/tmp", os.path.join(d, ".harnessdev"))
            result = checkmod.check_prompts(d)
            self.assertTrue(result.ok, result.detail)


class Compat(unittest.TestCase):
    def test_assemble_junta_papel_e_shared(self):
        text = prompts.assemble(ROOT)
        self.assertIn("orquestrador", text.lower())
        self.assertIn("## stop-list", text)
        self.assertIn("2FA, login ou código de verificação", text)

    def test_papel_sem_shared_recusa(self):
        with TempDir() as d:
            write(os.path.join(d, "harness", "prompts", "orchestrator.md"), "papel\n")
            with self.assertRaises(prompts.PromptError):
                prompts.assemble(d)

    def test_init_entrega_prompt_orchestrator(self):
        with TempDir() as tmp:
            core = make_core(tmp)
            app = os.path.join(tmp, "app")
            os.makedirs(app)
            code, out = hdev("init", app, "--core", core)
            self.assertEqual(code, 0, out)
            path = os.path.join(app, ".harnessdev", "PROMPT-ORCHESTRATOR.md")
            self.assertTrue(os.path.isfile(path), out)
            text = _read(path)
            self.assertIn("orquestrador", text.lower())
            self.assertIn("## stop-list", text)
            self.assertFalse(os.path.isfile(os.path.join(app, "PROMPT-ORCHESTRATOR.md")))
            self.assertFalse(os.path.isfile(os.path.join(core, "PROMPT-ORCHESTRATOR.md")))

    def test_tag_sem_harness_prompts_mantem_o_arquivo_do_archive(self):
        with TempDir() as d:
            core = os.path.join(d, "core")
            write(os.path.join(core, "PROMPT-ORCHESTRATOR.md"), "ANTIGO\n")
            git(core, "init", "-q")
            git(core, "add", "-A")
            git(core, "commit", "-q", "--no-verify", "-m", "antigo")
            git(core, "tag", "v0.0.1")
            dest, _commit = release.install(core, "v0.0.1")
            self.assertEqual(_read(os.path.join(dest, "PROMPT-ORCHESTRATOR.md")), "ANTIGO\n")
            self.assertFalse(os.path.isfile(os.path.join(dest, "harness", "prompts", "orchestrator.md")))


class Grep(unittest.TestCase):
    def test_grep_acha_pelo_menos_quatro(self):
        r = subprocess.run(["grep", "-rl", "stop-list.md", "harness/prompts"], cwd=ROOT,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        files = [line for line in r.stdout.splitlines() if line]
        self.assertGreaterEqual(len(files), 4)
