"""Suíte do fechar: clone limpo do HEAD, shards e cache por tree sha."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import TempDir, git, hdev, read_json, write  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hdev.gates import full as fullmod  # noqa: E402
from hdev.gates import full_cache  # noqa: E402

PLAN = "docs/plan-inf-009-suite.md"
TRAILER = re.compile(
    r"Hdev-Gates-Full: pass tree=[0-9a-f]{40} tests=\d+ shards=\d+ s=\d+\.\d cache=(?:hit|miss)")
OK_TEST = (
    "import os\nimport unittest\n"
    "class T(unittest.TestCase):\n"
    "    def test_ok(self):\n"
    "        path = os.environ.get('HDEV_SHARD_COUNTER')\n"
    "        if path:\n"
    "            with open(path, 'a', encoding='utf-8') as handle:\n"
    "                handle.write('x')\n"
    "                handle.flush()\n"
)
OTHER_TEST = (
    "import unittest\n"
    "class T(unittest.TestCase):\n"
    "    def test_outro(self):\n"
    "        self.assertEqual(1, 1)\n"
)
BAD_TEST = (
    "import unittest\n"
    "class T(unittest.TestCase):\n"
    "    def test_falha(self):\n"
    "        self.fail('quebrou')\n"
)
READ_TEST = (
    "import os\nimport unittest\n"
    "class T(unittest.TestCase):\n"
    "    def test_marker(self):\n"
    "        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n"
    "        with open(os.path.join(root, 'marker.txt'), encoding='utf-8') as handle:\n"
    "            self.assertEqual(handle.read(), 'committed\\n')\n"
)


def commit(d, msg):
    git(d, "add", "-A")
    r = git(d, "commit", "-q", "--no-verify", "-m", msg)
    assert r.returncode == 0, r.stderr
    return git(d, "rev-parse", "HEAD").stdout.strip()


def init_repo(d):
    git(d, "init", "-q")
    git(d, "config", "user.name", "t")
    git(d, "config", "user.email", "t@example.invalid")
    write(os.path.join(d, ".gitignore"), ".hdev/runs/\n.hdev/cache/\n.hdev/state/\n")
    write(os.path.join(d, "README.md"), "x\n")
    commit(d, "inicial")


def discover(shards, extra=()):
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v", *extra]
    return {"gates": {"full": cmd, "timeout": 60, "shards": shards}}


def put_config(d, cfg):
    write(os.path.join(d, ".hdev", "config.json"), json.dumps(cfg))


def cache_files(d):
    folder = os.path.join(d, ".hdev", "cache", "full")
    if not os.path.isdir(folder):
        return []
    return [n for n in os.listdir(folder) if n.endswith(".json")]


def counter_size(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return len(handle.read())
    except OSError:
        return 0


class Corte(unittest.TestCase):
    def test_cada_modulo_uma_vez(self):
        mods = ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py", "tests/test_d.py", "tests/test_e.py"]
        parts = fullmod.split_modules(mods, 2)
        flat = [item for group in parts for item in group]
        self.assertEqual(sorted(flat), mods)
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(len(parts), 2)
        self.assertEqual(fullmod.split_modules(mods, 1), [mods])
        self.assertEqual(len(fullmod.split_modules(mods, 9)), 5)
        self.assertEqual(fullmod.split_modules([], 4), [])

    def test_so_entra_arquivo_de_teste_no_start(self):
        names = fullmod.module_names(
            ["tests/test_a.py", "tests/test_b.py", "tests/helpers.py", "docs/test_x.py", "tests/__init__.py"],
            "tests", "test*.py")
        self.assertEqual(names, ["tests/test_a.py", "tests/test_b.py"])

    def test_chave_muda_com_tree_comando_shards_python_e_timeout(self):
        base = {"tree": "a" * 40, "command": ["python3", "-m", "unittest", "discover", "-s", "tests"],
                "shards": 4, "workers": 4, "python": "3.12.3", "timeout": 600}
        key, _payload = full_cache.cache_key(**base)
        for field, value in (
            ("tree", "b" * 40),
            ("command", ["python3", "-m", "unittest", "discover", "-s", "tests", "-q"]),
            ("shards", 2),
            ("workers", 2),
            ("python", "3.11.0"),
            ("timeout", 30),
        ):
            other = dict(base)
            other[field] = value
            other_key, _other = full_cache.cache_key(**other)
            self.assertNotEqual(key, other_key, field)
        changed, _payload = full_cache.cache_key(fmt=2, **base)
        self.assertNotEqual(key, changed)

    def test_store_recusa_falha_timeout_e_erro(self):
        with TempDir() as d:
            for kind in ("fail", "timeout", "error"):
                result = {"ok": False, "kind": kind, "tree": "a" * 40, "tests": 1, "shards": 1,
                          "wall_s": 0.1, "serial_s": 0.1, "failures": ["x"]}
                self.assertFalse(full_cache.store(d, "k-" + kind, {}, result))
            self.assertEqual(cache_files(d), [])


class Corrida(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.d = self._tmp.__enter__()
        self.counter = os.path.join(self.d, "counter.txt")
        self._old = os.environ.get("HDEV_SHARD_COUNTER")
        os.environ["HDEV_SHARD_COUNTER"] = self.counter

    def tearDown(self):
        if self._old is None:
            os.environ.pop("HDEV_SHARD_COUNTER", None)
        else:
            os.environ["HDEV_SHARD_COUNTER"] = self._old
        self._tmp.__exit__(None, None, None)

    def test_clone_ignora_sujo_e_nao_rastreado(self):
        init_repo(self.d)
        write(os.path.join(self.d, "marker.txt"), "committed\n")
        write(os.path.join(self.d, "tests", "test_read.py"), READ_TEST)
        put_config(self.d, discover(2))
        commit(self.d, "testes")
        write(os.path.join(self.d, "marker.txt"), "dirty\n")
        write(os.path.join(self.d, "tests", "test_read.py"), BAD_TEST)
        write(os.path.join(self.d, "tests", "test_extra.py"), BAD_TEST)
        result = fullmod.execute(self.d)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["cache"], "miss")

    def test_corte_e_falha_de_um_shard(self):
        init_repo(self.d)
        write(os.path.join(self.d, "tests", "test_ok.py"), OK_TEST)
        write(os.path.join(self.d, "tests", "test_bad.py"), BAD_TEST)
        put_config(self.d, discover(2))
        commit(self.d, "testes")
        planned = fullmod.plan(self.d)
        flat = [item for group in planned["groups"] for item in group]
        self.assertEqual(sorted(flat), ["tests/test_bad.py", "tests/test_ok.py"])
        self.assertEqual(len(flat), len(set(flat)))
        self.assertEqual(len(planned["groups"]), 2)
        result = fullmod.execute(self.d)
        self.assertFalse(result["ok"], result)
        self.assertEqual(result["tests"], 2)
        self.assertTrue(any("test_falha" in name for name in result["failures"]), result["failures"])
        self.assertIn("suíte vermelha", result["message"])
        self.assertEqual(cache_files(self.d), [])
        again = fullmod.execute(self.d)
        self.assertFalse(again["ok"])
        self.assertEqual(counter_size(self.counter), 2)

    def test_cache_acerto_erro_e_no_cache(self):
        init_repo(self.d)
        write(os.path.join(self.d, "tests", "test_ok.py"), OK_TEST)
        write(os.path.join(self.d, "tests", "test_other.py"), OTHER_TEST)
        put_config(self.d, discover(1))
        commit(self.d, "testes")
        first = fullmod.execute(self.d)
        self.assertTrue(first["ok"], first)
        self.assertEqual(first["cache"], "miss")
        self.assertEqual(first["shards"], 1)
        self.assertEqual(first["tests"], 2)
        self.assertEqual(counter_size(self.counter), 1)
        second = fullmod.execute(self.d)
        self.assertEqual(second["cache"], "hit")
        self.assertEqual(counter_size(self.counter), 1)
        forced = fullmod.execute(self.d, no_cache=True)
        self.assertEqual(forced["cache"], "miss")
        self.assertEqual(counter_size(self.counter), 2)
        put_config(self.d, discover(2))
        changed = fullmod.execute(self.d)
        self.assertEqual(changed["cache"], "miss", changed)
        self.assertEqual(changed["shards"], 2)
        self.assertEqual(counter_size(self.counter), 3)
        put_config(self.d, discover(2, extra=("-q",)))
        command = fullmod.execute(self.d)
        self.assertEqual(command["cache"], "miss")
        self.assertEqual(counter_size(self.counter), 4)
        put_config(self.d, discover(2))
        back = fullmod.execute(self.d)
        self.assertEqual(back["cache"], "hit")
        self.assertEqual(counter_size(self.counter), 4)
        write(os.path.join(self.d, "README.md"), "y\n")
        commit(self.d, "muda a arvore")
        tree = fullmod.execute(self.d)
        self.assertEqual(tree["cache"], "miss")
        self.assertEqual(counter_size(self.counter), 5)

    def test_timeout_e_erro_nao_entram_no_cache(self):
        init_repo(self.d)
        script = (
            "import os, time\n"
            "path = os.environ['HDEV_SHARD_COUNTER']\n"
            "handle = open(path, 'a', encoding='utf-8')\n"
            "handle.write('x')\n"
            "handle.flush()\n"
            "handle.close()\n"
            "time.sleep(30)\n"
        )
        put_config(self.d, {"gates": {"full": [sys.executable, "-c", script], "timeout": 1, "shards": 2}})
        commit(self.d, "timeout")
        first = fullmod.execute(self.d)
        self.assertFalse(first["ok"])
        self.assertEqual(first["kind"], "timeout")
        self.assertIn("passou de", first["message"])
        self.assertEqual(cache_files(self.d), [])
        second = fullmod.execute(self.d)
        self.assertEqual(second["kind"], "timeout")
        self.assertEqual(counter_size(self.counter), 2)
        self.assertEqual(cache_files(self.d), [])
        put_config(self.d, {"gates": {"full": [os.path.join(self.d, "bin-ausente")], "timeout": 30, "shards": 1}})
        commit(self.d, "comando ausente")
        err = fullmod.execute(self.d)
        self.assertFalse(err["ok"])
        self.assertEqual(err["kind"], "error")
        self.assertIn("não rodei a suíte", err["message"])
        again = fullmod.execute(self.d)
        self.assertEqual(again["kind"], "error")
        self.assertEqual(cache_files(self.d), [])


class Trailer(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.d = self._tmp.__enter__()
        init_repo(self.d)
        write(os.path.join(self.d, "tests", "test_ok.py"), OTHER_TEST)
        write(os.path.join(self.d, PLAN), "# Plano — suíte\n")

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def test_trailer_no_marco(self):
        put_config(self.d, discover(1))
        head = commit(self.d, "testes")
        code, out = hdev("base", "--plan", PLAN, "--root", self.d, "--marcar",
                         git(self.d, "rev-list", "--max-parents=0", "HEAD").stdout.strip())
        self.assertEqual(code, 0, out)
        tree = git(self.d, "rev-parse", "HEAD^{tree}").stdout.strip()
        write(os.path.join(self.d, ".hdev", "runs", "judge-20990101T000000Z.json"), json.dumps(
            {"verdict": "pass", "plan": PLAN, "head_sha": head, "base_sha":
             git(self.d, "rev-list", "--max-parents=0", "HEAD").stdout.strip(),
             "dirty": False, "attempts": [{"cli": "grok", "verdict": "pass"}]}))
        code, out = hdev("fechar", "--plan", PLAN, "--root", self.d)
        self.assertEqual(code, 0, out)
        msg = git(self.d, "log", "-1", "--format=%B").stdout
        self.assertRegex(msg, TRAILER)
        self.assertIn("tree=%s" % tree, msg)
        self.assertIn("cache=miss", msg)
        self.assertIn("shards=1", msg)

    def test_trailer_no_veredito_e_dry_run(self):
        put_config(self.d, dict(discover(1), base_branch="branch-base"))
        head = commit(self.d, "fora da base")
        code, out = hdev("fechar", "--plan", PLAN, "--root", self.d, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("gates.full", out)
        self.assertIn("shard", out)
        self.assertIn("cache: miss", out)
        self.assertIn("commit do marco pulado", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)
        code, out = hdev("fechar", "--plan", PLAN, "--root", self.d)
        self.assertEqual(code, 0, out)
        self.assertIn("cache=miss", out)
        self.assertNotIn("veio do cache", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)
        runs = [n for n in os.listdir(os.path.join(self.d, ".hdev", "runs")) if n.startswith("fechar-")]
        data = read_json(os.path.join(self.d, ".hdev", "runs", sorted(runs)[-1]))
        self.assertEqual(data["verdict"], "pass")
        self.assertEqual(data["milestone"], "skipped")
        self.assertRegex(data["gates_full"], TRAILER)
        self.assertIn("cache=miss", data["gates_full"])
        code, out = hdev("fechar", "--plan", PLAN, "--root", self.d)
        self.assertEqual(code, 0, out)
        self.assertIn("veio do cache", out)
        self.assertIn("cache=hit", out)
        code, out = hdev("fechar", "--plan", PLAN, "--root", self.d, "--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("gates.full", out)
        self.assertIn("cache: hit", out)
        code, out = hdev("fechar", "--plan", PLAN, "--root", self.d, "--no-cache")
        self.assertEqual(code, 0, out)
        self.assertIn("cache=miss", out)
        self.assertNotIn("veio do cache", out)


if __name__ == "__main__":
    unittest.main()
