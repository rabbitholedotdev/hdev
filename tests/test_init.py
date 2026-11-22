"""hdev init (ADR 0002): release por tag, `.harnessdev` + `.harnessdev.lock`, nada do núcleo copiado no app."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import (ROOT, TempDir, fake_aws_key, git, hdev, make_core, read_json, run_hook,  # noqa: E402
                     write)

sys.path.insert(0, ROOT)
from hdev import release  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.tmp = self._tmp.__enter__()
        self.core = make_core(self.tmp)
        self.app = os.path.join(self.tmp, "app")
        os.makedirs(self.app)

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def init(self, *extra):
        return hdev("init", self.app, "--core", self.core, *extra)

    def check(self):
        return hdev("check", "--root", self.app)


class Init(Base):
    def test_init_liga_a_release_e_check_passa(self):
        code, out = self.init()
        self.assertEqual(code, 0, out)
        link = os.path.join(self.app, ".harnessdev")
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link), os.path.join(os.path.realpath(self.core), "releases", "v9.9.9"))
        lock = read_json(os.path.join(self.app, ".harnessdev.lock"))
        self.assertEqual(lock["version"], "v9.9.9")
        self.assertEqual(lock["commit"], git(self.core, "rev-parse", "HEAD").stdout.strip())
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("harnessdev: v9.9.9", out)
        self.assertIn("(na release)", out)

    def test_nada_do_nucleo_no_app(self):
        self.init()
        for rel in ("hooks", "hdev", "bin", "scripts", "profiles", os.path.join("tests", "test_hooks.py"),
                    os.path.join("tests", "helpers.py")):
            self.assertFalse(os.path.exists(os.path.join(self.app, rel)), rel)
        for name in ("planejar", "revisar-spec", "revisar-diff", "hdev", "briefing", "spec"):
            skill = os.path.join(self.app, ".claude", "skills", name)
            self.assertTrue(os.path.islink(skill), name)
            self.assertTrue(os.readlink(skill).startswith(os.path.join("..", "..", ".harnessdev")), name)
        for name in ("sonnet-implementar.md", "haiku-explorar.md"):
            agent = os.path.join(self.app, ".claude", "agents", name)
            self.assertTrue(os.path.islink(agent), name)
            self.assertEqual(os.readlink(agent), os.path.join("..", "..", ".harnessdev", ".claude", "agents", name))
        settings = read_json(os.path.join(self.app, ".claude", "settings.json"))
        self.assertEqual(set(settings), {"hooks"})
        commands = json.dumps(settings)
        self.assertEqual(commands.count("$CLAUDE_PROJECT_DIR/.harnessdev/harness/hooks/"), 5)
        self.assertNotIn("core", read_json(os.path.join(self.app, ".hdev", "config.json")))
        with open(os.path.join(self.app, "CLAUDE.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "@AGENTS.md\n")

    def test_sem_tag_recusa(self):
        bare = make_core(os.path.join(self.tmp, "semtag"), version=None)
        code, out = hdev("init", self.app, "--core", bare)
        self.assertEqual(code, 1, out)
        self.assertIn("tag", out)
        self.assertFalse(os.path.lexists(os.path.join(self.app, ".harnessdev")))

    def test_versao_inexistente_ou_mal_formada_recusa(self):
        for version in ("v0.0.0", "latest"):
            code, out = self.init("--version", version)
            self.assertEqual(code, 1, (version, out))

    def test_maior_tag_e_escolhida(self):
        git(self.core, "commit", "-q", "--allow-empty", "--no-verify", "-m", "depois")
        git(self.core, "tag", "v10.0.0")
        self.init()
        self.assertEqual(read_json(os.path.join(self.app, ".harnessdev.lock"))["version"], "v10.0.0")

    def test_segundo_init_reaproveita_e_tag_movida_recusa(self):
        self.assertEqual(self.init()[0], 0)
        code, out = self.init()
        self.assertEqual(code, 0, out)
        self.assertIn("mantido: .harnessdev.lock", out)
        git(self.core, "commit", "-q", "--allow-empty", "--no-verify", "-m", "move")
        git(self.core, "tag", "-f", "v9.9.9")
        code, out = self.init()
        self.assertEqual(code, 1, out)
        self.assertIn("tag movida", out)

    def test_troca_de_versao_so_com_force(self):
        self.init()
        git(self.core, "commit", "-q", "--allow-empty", "--no-verify", "-m", "nova")
        git(self.core, "tag", "v9.10.0")
        code, out = self.init("--version", "v9.10.0")
        self.assertEqual(code, 1, out)
        self.assertIn("--force", out)
        code, out = self.init("--version", "v9.10.0", "--force")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.readlink(os.path.join(self.app, ".harnessdev")).endswith("v9.10.0"))
        self.assertEqual(self.check()[0], 0)

    def test_nao_sobrescreve_sem_force(self):
        write(os.path.join(self.app, "AGENTS.md"), "meu AGENTS\n")
        code, out = self.init()
        self.assertEqual(code, 0, out)
        self.assertIn("pulado", out)
        with open(os.path.join(self.app, "AGENTS.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "meu AGENTS\n")

    def test_comando_de_testes_do_app_roda_verde(self):
        # revisão Codex, rodada 10: o consumidor não herda um comando que só funciona no núcleo
        self.assertEqual(self.init()[0], 0)
        cfg = read_json(os.path.join(self.app, ".hdev", "config.json"))
        cmd = cfg["gates"]["fast"]
        self.assertTrue(os.path.isfile(os.path.join(self.app, "tests", "test_smoke.py")))
        r = subprocess.run(cmd, cwd=self.app, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(cfg["gates"]["full"][:-1], cmd[:-1])
        self.assertEqual(cmd[-1], "-q")
        self.assertEqual(cfg["gates"]["full"][-1], "-v")
        self.assertNotIn("tests", cfg)
        self.assertNotIn("tests_command", json.dumps(cfg))

    def test_tests_do_app_nao_e_tocado(self):
        write(os.path.join(self.app, "tests", "test_meu.py"), "import unittest\n")
        self.assertEqual(self.init()[0], 0)
        self.assertFalse(os.path.exists(os.path.join(self.app, "tests", "test_smoke.py")))

    def test_recusa_o_proprio_nucleo_e_a_release(self):
        self.assertEqual(hdev("init", self.core, "--core", self.core)[0], 1)
        self.init()
        self.assertEqual(hdev("init", os.path.join(self.core, "releases", "v9.9.9"), "--core", self.core)[0], 1)


class Check(Base):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.init()[0], 0)

    def assertHarnessdevFails(self, contains):
        code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("FALHA] harnessdev", out)
        self.assertIn(contains, out)

    def test_lock_com_outra_versao_falha(self):
        path = os.path.join(self.app, ".harnessdev.lock")
        lock = read_json(path)
        lock["version"] = "v1.2.3"
        write(path, json.dumps(lock))
        self.assertHarnessdevFails("o lock fixa")

    def test_lock_com_outro_commit_falha(self):
        path = os.path.join(self.app, ".harnessdev.lock")
        lock = read_json(path)
        lock["commit"] = "0" * 40
        write(path, json.dumps(lock))
        self.assertHarnessdevFails("commit")

    def test_link_apagado_falha(self):
        os.remove(os.path.join(self.app, ".harnessdev"))
        self.assertHarnessdevFails("falta o symlink")

    def test_link_para_outra_pasta_falha(self):
        other = os.path.join(self.tmp, "outra")
        os.makedirs(other)
        os.remove(os.path.join(self.app, ".harnessdev"))
        os.symlink(other, os.path.join(self.app, ".harnessdev"))
        self.assertHarnessdevFails("aponta para")

    def test_link_sem_lock_falha(self):
        os.remove(os.path.join(self.app, ".harnessdev.lock"))
        self.assertHarnessdevFails("sem .harnessdev.lock")

    def test_versao_da_release_diferente_do_lock_falha(self):
        # revisão Codex, rodada 10: meta.version também é conferida
        meta = os.path.join(self.core, "releases", "v9.9.9", release.RELEASE_META)
        data = read_json(meta)
        data["version"] = "v0.0.0"
        write(meta, json.dumps(data))
        self.assertHarnessdevFails("versão")


class Worktree(Base):
    def test_consumidor_worktree_e_reconhecido_sem_mexer_no_compartilhado(self):
        # revisão Codex, rodada 10: em worktree, .git é arquivo. O repo é reconhecido pelo git; os hooks
        # do worktree são do repo principal, então o init não escreve lá e diz como ligar.
        main = os.path.join(self.tmp, "principal")
        os.makedirs(main)
        git(main, "init", "-q")
        git(main, "commit", "-q", "--allow-empty", "-m", "base")
        os.rmdir(self.app)
        self.assertEqual(git(main, "worktree", "add", "-q", "--detach", self.app).returncode, 0)
        self.assertTrue(os.path.isfile(os.path.join(self.app, ".git")))
        code, out = self.init()
        self.assertEqual(code, 0, out)
        self.assertNotIn("sem .git", out)
        self.assertIn("compartilhad", out)
        self.assertFalse(os.path.exists(os.path.join(main, ".git", "hooks", "pre-commit")))

    def test_core_hooks_path_e_respeitado(self):
        git(self.app, "init", "-q")
        git(self.app, "config", "core.hooksPath", ".meus-hooks")
        code, out = self.init()
        self.assertEqual(code, 0, out)
        self.assertTrue(os.access(os.path.join(self.app, ".meus-hooks", "pre-commit"), os.X_OK))


class AppGit(Base):
    def setUp(self):
        super().setUp()
        git(self.app, "init", "-q")
        self.assertEqual(self.init()[0], 0)

    def test_pre_commit_usa_a_release_e_barra_check_vermelho(self):
        hook = os.path.join(self.app, ".git", "hooks", "pre-commit")
        self.assertTrue(os.access(hook, os.X_OK))
        git(self.app, "add", "-A")
        r = git(self.app, "commit", "-q", "-m", "base")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(git(self.app, "ls-files", ".harnessdev").stdout.strip(), ".harnessdev")
        with open(os.path.join(self.app, "AGENTS.md"), "a", encoding="utf-8") as f:
            f.write("x\n" * 81)
        git(self.app, "add", "-A")
        r = git(self.app, "commit", "-q", "-m", "estoura")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("FALHA", r.stdout + r.stderr)
        with open(os.path.join(self.app, ".gitignore"), encoding="utf-8") as f:
            self.assertIn(".hdev/state/", f.read())

    def test_hooks_do_app_rodam_pela_release(self):
        ev = {"tool_name": "Write", "tool_input": {"file_path": "x.py", "content": "k = '%s'\n" % fake_aws_key()}}
        hook = os.path.join(self.app, ".harnessdev", "hooks", "secret_guard.py")
        self.assertTrue(os.path.isfile(hook))
        code, _ = run_hook(hook, ev)  # caminho absoluto: os.path.join ignora a pasta HOOKS
        self.assertEqual(code, 2)
        self.assertEqual(release.verify(self.app)[0], True)


if __name__ == "__main__":
    unittest.main()
