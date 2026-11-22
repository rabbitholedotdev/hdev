"""Release nova traz PROMPT-ORCHESTRATOR.md; pin + sync mantêm o Stop do Codex e do Grok."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, clean_env, git, hdev, make_core, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev import release  # noqa: E402
from hdev.init import agents_text  # noqa: E402

BANNER = "<!-- compat:"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _prompt(dest):
    return os.path.join(dest, "PROMPT-ORCHESTRATOR.md")


class Links(unittest.TestCase):
    def test_check_falha_quando_o_agents_liga_arquivo_ausente(self):
        with TempDir() as d:
            rel = os.path.join(d, "releases", "v9.9.9")
            write(os.path.join(rel, "profiles", "harness-developer", "AGENTS.md"),
                  "Prompt: `.harnessdev/PROMPT-ORCHESTRATOR.md`.\n"
                  "Parada: `.harnessdev/harness/prompts/_shared/stop-list.md`.\n")
            write(os.path.join(rel, "harness", "prompts", "_shared", "stop-list.md"), "## stop-list\n")
            write(_prompt(rel), BANNER + "\nok\n")
            write(os.path.join(rel, release.RELEASE_META), json.dumps({
                "version": "v9.9.9", "commit": "abc", "core": d,
            }))
            app = os.path.join(d, "app")
            os.makedirs(app)
            os.symlink(rel, os.path.join(app, ".harnessdev"))
            write(os.path.join(app, ".harnessdev.lock"), json.dumps({
                "version": "v9.9.9", "commit": "abc", "core": d,
                "releases": os.path.join(d, "releases"),
            }))
            write(os.path.join(app, "AGENTS.md"), agents_text("harness-developer"))
            ok = checkmod.check_harnessdev(app)
            self.assertTrue(ok.ok, ok.detail)
            os.remove(_prompt(rel))
            bad = checkmod.check_harnessdev(app)
            self.assertFalse(bad.ok, bad.detail)
            self.assertIn("PROMPT-ORCHESTRATOR.md", bad.detail)
            self.assertNotIn("stop-list.md", bad.detail)


class Paths(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.tmp = self._tmp.__enter__()
        self._prev = os.environ.get("HDEV_RELEASES_DIR")
        self.core = make_core(self.tmp, version="v0.7.1")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("HDEV_RELEASES_DIR", None)
        else:
            os.environ["HDEV_RELEASES_DIR"] = self._prev
        self._tmp.__exit__(None, None, None)

    def _dir(self, name):
        dest = os.path.join(self.tmp, name)
        os.environ["HDEV_RELEASES_DIR"] = dest
        return dest

    def _assert_prompt(self, folder):
        path = _prompt(folder)
        self.assertTrue(os.path.isfile(path), path)
        text = _read(path)
        self.assertIn(BANNER, text)
        self.assertIn("## stop-list", text)
        return path

    def test_install_pin_e_release_gravam_o_prompt(self):
        installed = os.path.join(self._dir("by-install"), "v0.7.1")
        dest, _commit = release.install(self.core, "v0.7.1")
        self.assertEqual(os.path.realpath(dest), os.path.realpath(installed))
        path = self._assert_prompt(dest)
        os.remove(path)
        again, _commit = release.install(self.core, "v0.7.1")
        self.assertEqual(os.path.realpath(again), os.path.realpath(dest))
        self.assertFalse(os.path.isfile(path))

        self._dir("by-pin")
        app = os.path.join(self.tmp, "app")
        code, out = hdev("pin", "v0.7.1", "--root", app, "--core", self.core)
        self.assertEqual(code, 0, out)
        pinned = os.path.join(os.environ["HDEV_RELEASES_DIR"], "v0.7.1")
        self._assert_prompt(pinned)
        code, out = hdev("sync", "--root", app)
        self.assertEqual(code, 0, out)
        codex = os.path.join(app, ".codex", "hooks.json")
        grok = os.path.join(app, ".grok", "hooks", "stop.json")
        self.assertTrue(os.path.isfile(codex), out)
        self.assertTrue(os.path.isfile(grok), out)
        codex_hook = json.loads(_read(codex))
        grok_hook = json.loads(_read(grok))
        self.assertEqual(codex_hook, grok_hook)
        cmd = codex_hook["hooks"]["Stop"][0]["hooks"][0]
        self.assertEqual(cmd["type"], "command")
        self.assertIn(".harnessdev/harness/hooks/stop_gate.py", cmd["command"])
        code, out = hdev("sync", "--check", "--root", app)
        self.assertEqual(code, 0, out)
        write(codex, "{}\n")
        code, out = hdev("sync", "--check", "--root", app)
        self.assertEqual(code, 1, out)
        self.assertIn(".codex/hooks.json", out)
        code, out = hdev("sync", "--root", app)
        self.assertEqual(code, 0, out)

        write(os.path.join(app, ".hdev", "config.json"), json.dumps({
            "gates": {"on_stop": True, "fast": [sys.executable, "-c", "raise SystemExit(0)"]},
        }))
        write(os.path.join(app, "docs", "progress.md"), "ok\n")
        write(os.path.join(app, ".hdev", "state", "unit.json"), json.dumps({
            "id": "alfa", "status": "open", "next": "seguir", "plan": "docs/plan-inf-006-banco.md",
        }))
        git(app, "init", "-q")
        write(os.path.join(app, "AGENTS.md"), agents_text("harness-developer"))
        linked = checkmod.check_harnessdev(app)
        self.assertTrue(linked.ok, linked.detail)
        os.remove(_prompt(pinned))
        missing = checkmod.check_harnessdev(app)
        self.assertFalse(missing.ok, missing.detail)
        self.assertIn("PROMPT-ORCHESTRATOR.md", missing.detail)

        def run_hook(command, session):
            ev = {"hook_event_name": "Stop", "session_id": session, "cwd": app}
            r = subprocess.run(command, input=json.dumps(ev), shell=True, capture_output=True, text=True,
                               cwd=app, env=clean_env(CLAUDE_PROJECT_DIR=app), timeout=60)
            return r.returncode, r.stderr

        codex_cmd = json.loads(_read(codex))["hooks"]["Stop"][0]["hooks"][0]["command"]
        grok_cmd = json.loads(_read(grok))["hooks"]["Stop"][0]["hooks"][0]["command"]
        self.assertIn("stop_gate.py", codex_cmd)
        self.assertIn("stop_gate.py", grok_cmd)
        write(os.path.join(app, ".hdev", "state", "session.json"), json.dumps({"stop_session": "velha"}))
        code, err = run_hook(codex_cmd, "velha")
        self.assertEqual(code, 0, err)
        self.assertNotIn("aberta", err)
        write(os.path.join(app, ".hdev", "state", "session.json"), json.dumps({"stop_session": "velha"}))
        code, err = run_hook(grok_cmd, "nova")
        self.assertEqual(code, 2, err)
        self.assertIn("aberta", err)
        write(os.path.join(app, ".hdev", "state", "session.json"), json.dumps({"allow_stop": True}))
        code, err = run_hook(codex_cmd, "velha")
        self.assertEqual(code, 2, err)

        self._dir("by-release")
        code, out = hdev("release", "v0.7.1", "--core", self.core)
        self.assertIn(code, (0, 2), out)
        self._assert_prompt(os.path.join(os.environ["HDEV_RELEASES_DIR"], "v0.7.1"))

        fresh = self._dir("by-tag-070")
        if release.tag_commit(ROOT, "v0.7.0"):
            dest, _commit = release.install(ROOT, "v0.7.0")
            self.assertTrue(dest.startswith(os.path.realpath(fresh)))
            self._assert_prompt(dest)
