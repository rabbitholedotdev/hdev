"""Cache do grafo: aresta EXTRACTED, fallback e a linha graph do check."""
import json
import os
import shutil
import stat
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import BIN, ROOT, TempDir, clean_env, git, hdev, make_core, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev.graph import (  # noqa: E402
    affected_tests, head_sha, impact, update, write_sha,
)
from hdev.init import init  # noqa: E402

FIXTURE = os.path.join(ROOT, "tests", "fixtures", "graph", "graph.json")
SCRIPT = os.path.join(ROOT, "scripts", "affected-tests")


def _quiet(fn, *args, **kwargs):
    """O update imprime o sha do repo. No teste isso iria para o log do juiz e a chave mudaria."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return fn(*args, **kwargs)


def _repo(tmp):
    root = os.path.join(tmp, "repo")
    os.makedirs(os.path.join(root, "tests"))
    os.makedirs(os.path.join(root, "hdev"))
    for name in ("test_stop.py", "test_stop_more.py", "test_cli.py", "test_other.py", "test_unrelated.py"):
        write(os.path.join(root, "tests", name), "# teste\n")
    write(os.path.join(root, "hdev", "stop.py"), "# stop\n")
    git(root, "init", "-q")
    git(root, "add", "-A")
    r = git(root, "commit", "-q", "-m", "base")
    if r.returncode != 0:
        raise RuntimeError(r.stderr)
    return root


def _plant(root, sha=None):
    dest = os.path.join(root, ".hdev", "cache", "graph")
    os.makedirs(dest, exist_ok=True)
    shutil.copy(FIXTURE, os.path.join(dest, "graph.json"))
    write_sha(root, sha if sha is not None else head_sha(root))


def _chain(n):
    """A0 <- A1 <- ... <- A(n). A1 e A(n) são testes. O resto é código."""
    nodes, links = [], []
    for i in range(n + 1):
        if i in (1, n):
            sf = "tests/test_hop%d.py" % i
        else:
            sf = "pkg/a%d.py" % i
        nodes.append({"id": "n%d" % i, "label": sf, "source_file": sf})
        if i:
            links.append({"source": "n%d" % i, "target": "n%d" % (i - 1),
                          "relation": "imports_from", "confidence": "EXTRACTED"})
    return {"nodes": nodes, "links": links}


class Fixture(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.root = _repo(self._tmp.__enter__())

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def test_extracted_entra_e_inferred_fica_de_fora(self):
        _plant(self.root)
        paths, msg = affected_tests(self.root, ["hdev/stop.py"])
        self.assertIsNone(msg)
        self.assertEqual(paths, ["tests/test_cli.py", "tests/test_stop.py"])
        text, note = impact(self.root, "hdev/stop.py")
        self.assertIsNone(note)
        self.assertIn("tests/test_stop.py", text)
        self.assertIn("hdev/cli.py", text)
        self.assertIn("hdev/config.py", text)
        self.assertIn("fora do repo: json", text)
        self.assertNotIn("test_other", text)

    def test_grafo_velho_cai_na_suite_do_modulo(self):
        _plant(self.root, sha="0" * 40)
        paths, msg = affected_tests(self.root, ["hdev/stop.py"])
        self.assertIn("velho", msg)
        self.assertIn("suíte do módulo stop", msg)
        self.assertEqual(paths, ["tests/test_stop.py", "tests/test_stop_more.py"])
        text, note = impact(self.root, "hdev/stop.py")
        self.assertEqual(text, "")
        self.assertIn("velho", note)
        self.assertIn("fallback", note)

    def test_grafo_ausente_avisa_e_cai(self):
        paths, msg = affected_tests(self.root, ["hdev/stop.py"])
        self.assertIn("ausente", msg)
        self.assertIn("fallback", msg)
        self.assertEqual(paths, ["tests/test_stop.py", "tests/test_stop_more.py"])

    def test_arquivo_sem_suite_propria_cai_na_suite_inteira(self):
        paths, msg = affected_tests(self.root, ["hdev/nope.py"])
        self.assertIn("ausente", msg)
        self.assertIn("suíte inteira", msg)
        self.assertIn("tests/test_unrelated.py", paths)
        self.assertIn("tests/test_stop.py", paths)

    def test_json_ilegivel_cai(self):
        _plant(self.root)
        write(os.path.join(self.root, ".hdev", "cache", "graph", "graph.json"), "{")
        _paths, msg = affected_tests(self.root, ["hdev/stop.py"])
        self.assertIn("ilegível", msg)
        self.assertIn("suíte do módulo", msg)

    def test_corte_em_oito_saltos(self):
        _plant(self.root)
        path = os.path.join(self.root, ".hdev", "cache", "graph", "graph.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_chain(9), f)
        for i in (1, 9):
            write(os.path.join(self.root, "tests", "test_hop%d.py" % i), "# hop\n")
        paths, msg = affected_tests(self.root, ["pkg/a0.py"])
        self.assertIn("tests/test_hop1.py", paths)
        self.assertNotIn("tests/test_hop9.py", paths)
        self.assertIn("cortada", msg)

    def test_script_imprime_os_testes(self):
        _plant(self.root)
        r = subprocess.run([sys.executable, SCRIPT, "hdev/stop.py"], cwd=self.root,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.splitlines(), ["tests/test_cli.py", "tests/test_stop.py"])
        r = subprocess.run([sys.executable, SCRIPT], cwd=self.root, capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 2)


class Update(unittest.TestCase):
    def test_binario_ausente_nao_quebra(self):
        with TempDir() as tmp:
            root = _repo(tmp)
            env = dict(os.environ)
            env["PATH"] = "/usr/bin:/bin"
            env["HOME"] = tmp
            old = os.environ.copy()
            os.environ.clear()
            os.environ.update(env)
            try:
                code = _quiet(update, root)
            finally:
                os.environ.clear()
                os.environ.update(old)
            self.assertEqual(code, 0)
            self.assertFalse(os.path.exists(os.path.join(root, ".hdev", "cache", "graph", "sha")))

    def test_update_grava_o_sha_e_so_chama_update(self):
        with TempDir() as tmp:
            root = _repo(tmp)
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            fake = os.path.join(bindir, "graphify")
            write(fake, "#!/bin/sh\n"
                  "out=\"${GRAPHIFY_OUT:-graphify-out}\"\n"
                  "mkdir -p \"$out\"\n"
                  "printf '%s\\n' \"$@\" > \"$out/argv\"\n"
                  "printf '%s' \"$GRAPHIFY_OUT\" > \"$out/outenv\"\n"
                  "echo '{\"nodes\":[],\"links\":[]}' > \"$out/graph.json\"\n"
                  "echo 'Updating code graph (no LLM needed)'\n"
                  "exit 0\n")
            os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
            old_path, old_home = os.environ.get("PATH"), os.environ.get("HOME")
            os.environ["PATH"] = bindir + ":/usr/bin:/bin"
            os.environ["HOME"] = tmp
            try:
                code = _quiet(update, root)
                again = _quiet(update, root)
            finally:
                if old_path is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = old_path
                if old_home is None:
                    os.environ.pop("HOME", None)
                else:
                    os.environ["HOME"] = old_home
            self.assertEqual(code, 0)
            cache = os.path.join(root, ".hdev", "cache", "graph")
            with open(os.path.join(cache, "argv"), encoding="utf-8") as f:
                self.assertEqual(f.read().splitlines(), ["update", "."])
            with open(os.path.join(cache, "outenv"), encoding="utf-8") as f:
                self.assertEqual(f.read(), ".hdev/cache/graph")
            with open(os.path.join(cache, "sha"), encoding="utf-8") as f:
                self.assertEqual(f.read().strip(), head_sha(root))
            self.assertEqual(again, 0)

    def test_falha_nao_grava_sha(self):
        with TempDir() as tmp:
            root = _repo(tmp)
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            fake = os.path.join(bindir, "graphify")
            write(fake, "#!/bin/sh\nexit 1\n")
            os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
            old_path = os.environ.get("PATH")
            os.environ["PATH"] = bindir + ":/usr/bin:/bin"
            try:
                code = _quiet(update, root)
            finally:
                if old_path is None:
                    os.environ.pop("PATH", None)
                else:
                    os.environ["PATH"] = old_path
            self.assertEqual(code, 1)
            self.assertFalse(os.path.exists(os.path.join(root, ".hdev", "cache", "graph", "sha")))


class Hook(unittest.TestCase):
    def test_post_commit_chama_o_update(self):
        with TempDir() as tmp:
            root = os.path.join(tmp, "repo")
            os.makedirs(os.path.join(root, "bin"))
            write(os.path.join(root, "bin", "hdev"),
                  "import os, sys\nopen(os.environ['HOOK_LOG'], 'w').write(' '.join(sys.argv[1:]))\n")
            write(os.path.join(root, "leiame.txt"), "oi\n")
            git(root, "init", "-q")
            hook = os.path.join(root, ".git", "hooks", "post-commit")
            os.makedirs(os.path.dirname(hook), exist_ok=True)
            shutil.copy(os.path.join(ROOT, "scripts", "post-commit"), hook)
            os.chmod(hook, os.stat(hook).st_mode | stat.S_IXUSR)
            log = os.path.join(tmp, "hook-log")
            env = clean_env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                            GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
                            HOOK_LOG=log)
            env.pop("HDEV_SKIP_GRAPH", None)
            git(root, "add", "-A")
            r = subprocess.run(["git", "-c", "commit.gpgsign=false", "-C", root, "commit", "-q", "-m", "um"],
                               capture_output=True, text=True, timeout=30, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(log, encoding="utf-8") as f:
                called = f.read()
            self.assertIn("graph update", called)
            self.assertIn(root, called)

    def test_init_copia_post_commit_e_post_checkout(self):
        with TempDir() as tmp:
            core = make_core(tmp)
            app = os.path.join(tmp, "app")
            os.makedirs(app)
            git(app, "init", "-q")
            init(app, core=core, version="v9.9.9")
            for name in ("pre-commit", "post-commit", "post-checkout"):
                hook = os.path.join(app, ".git", "hooks", name)
                self.assertTrue(os.access(hook, os.X_OK), name)


class Linha(unittest.TestCase):
    def _tree(self, tmp, orchestrator="", executor="", skill="hdev graph update\n", explorer=None):
        root = os.path.join(tmp, "repo")
        write(os.path.join(root, "AGENTS.md"), "# A\n")
        write(os.path.join(root, "CLAUDE.md"), "@AGENTS.md\n")
        write(os.path.join(root, "harness", "prompts", "orchestrator.md"), orchestrator)
        write(os.path.join(root, "harness", "prompts", "executor.md"), executor)
        write(os.path.join(root, ".claude", "skills", "hdev", "SKILL.md"), skill)
        if explorer is None:
            explorer = "use graphify query, graphify path e graphify explain\n"
        write(os.path.join(root, ".claude", "agents", "haiku-explorar.md"), explorer)
        return root

    def test_orquestrador_com_grafo_falha(self):
        with TempDir() as tmp:
            root = self._tree(tmp, orchestrator="consulte o grafo antes\n")
            result = checkmod.check_graph(root)
            self.assertFalse(result.ok)
            self.assertIn("orchestrator.md", result.detail)

    def test_executor_com_graphify_falha(self):
        with TempDir() as tmp:
            root = self._tree(tmp, executor="rode graphify query\n")
            result = checkmod.check_graph(root)
            self.assertFalse(result.ok)
            self.assertIn("executor.md", result.detail)

    def test_skill_com_graph_report_falha(self):
        with TempDir() as tmp:
            root = self._tree(tmp, skill="leia GRAPH_REPORT todo turno\n")
            result = checkmod.check_graph(root)
            self.assertFalse(result.ok)
            self.assertIn("SKILL.md", result.detail)

    def test_so_o_explorer_passa(self):
        with TempDir() as tmp:
            root = self._tree(tmp)
            result = checkmod.check_graph(root)
            self.assertTrue(result.ok, result.detail)

    def test_explorer_sem_path_falha(self):
        with TempDir() as tmp:
            root = self._tree(tmp, explorer="graphify query e graphify explain\n")
            result = checkmod.check_graph(root)
            self.assertFalse(result.ok)
            self.assertIn("graphify path", result.detail)

    def test_check_real_nao_chama_o_binario(self):
        with TempDir() as tmp:
            bindir = os.path.join(tmp, "bin")
            os.makedirs(bindir)
            marker = os.path.join(tmp, "chamou")
            write(os.path.join(bindir, "graphify"), "#!/bin/sh\ntouch \"$MARKER\"\nexit 1\n")
            os.chmod(os.path.join(bindir, "graphify"), stat.S_IXUSR)
            env = clean_env(PATH=bindir + ":/usr/bin:/bin", HOME=tmp, MARKER=marker)
            r = subprocess.run([sys.executable, BIN, "check", "--root", ROOT], cwd=ROOT,
                               capture_output=True, text=True, env=env, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("[ok] graph:", r.stdout)
            self.assertIn("5 registros", r.stdout)
            self.assertIn("3 arquivos", r.stdout)
            self.assertFalse(os.path.exists(marker))


class LogEstavel(unittest.TestCase):
    def test_duas_corridas_normalizadas_iguais(self):
        if os.environ.get("HDEV_GRAPH_LOG_CHECK") == "1":
            return
        from hdev.gates.judge.package import normalize_test_log
        env = os.environ.copy()
        env["HDEV_GRAPH_LOG_CHECK"] = "1"
        cmd = [sys.executable, "-m", "unittest", "tests.test_graph", "-q"]
        runs = []
        for _ in range(2):
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env, timeout=180)
            blob = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, blob)
            self.assertEqual(r.stdout, "")
            self.assertNotIn("grafo atualizado", blob)
            self.assertNotIn("grafo em dia", blob)
            runs.append(normalize_test_log(blob))
        self.assertEqual(runs[0], runs[1])


if __name__ == "__main__":
    unittest.main()
