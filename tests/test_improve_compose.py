"""improve compose e revert: recusas, dry-run, branch `improve/<cand>` com trailer, biblioteca e revert."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_improve as base  # noqa: E402  (só as funções de fixture; as classes não entram aqui)
from helpers import TempDir, git, hdev, write  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hdev.improve import compose as composemod  # noqa: E402
from hdev.improve import probe as probemod  # noqa: E402
from hdev.library import reflect  # noqa: E402

RUN = "improve-fixture.json"
OPTIONS = ".claude/skills/briefing/references/options.md"


def repo(d):
    """Repo do probe com identidade local e sem assinar: o hdev faz commit por conta própria."""
    base.repo(d)
    git(d, "config", "user.name", "t")
    git(d, "config", "user.email", "t@example.invalid")
    git(d, "config", "commit.gpgsign", "false")


def fixture(d, cand="lean", verdict="ganharia", files=None, remove=None, lesson=True):
    """Repo com overlay, registro do probe escrito à mão e, se pedido, a lição do probe já no HEAD."""
    repo(d)
    base.overlay(d, cand, files if files is not None else {"harness/prompts/executor.md": "# e curto\n"},
                 remove=remove if remove is not None else [OPTIONS])
    result = {"id": cand, "mark": "domínio", "summary": "candidata de teste %s" % cand,
              "verdict": verdict, "delta": {"xray": -0.2}}
    payload = {"kind": "improve", "version": 1, "case": "ok", "base_sha": "f" * 40, "runner": "fake",
               "runs": 3, "candidates": [result], "adopted": []}
    write(os.path.join(d, ".hdev", "runs", RUN), json.dumps(payload) + "\n")
    if lesson:
        reflect.add_items(d, "u-test", [probemod._lesson(cand, result, result, "u-test", RUN)], offline=True)
        git(d, "add", "-A")
        proc = git(d, "commit", "-q", "--no-verify", "-m", "lição do probe")
        assert proc.returncode == 0, proc.stderr


def compose(d, *extra, cand="lean"):
    return hdev("improve", "compose", "--run", RUN, "--cand", cand, "--root", d, *extra)


def branches(d):
    return git(d, "branch", "--list", "improve/*").stdout.split()


def lib_status(d, rev):
    text = git(d, "show", "%s:library/index.jsonl" % rev).stdout
    return [json.loads(line)["status"] for line in text.splitlines() if line.strip()]


class RefuseTest(unittest.TestCase):
    def assert_refused(self, d, needle, *extra):
        head = git(d, "rev-parse", "HEAD").stdout
        status = git(d, "status", "--porcelain").stdout
        code, out = compose(d, *extra)
        self.assertEqual(code, 1, out)
        self.assertIn(needle, out)
        self.assertEqual(branches(d), [])
        self.assertEqual(git(d, "rev-parse", "HEAD").stdout, head)
        self.assertEqual(git(d, "status", "--porcelain").stdout, status)

    def test_refuses_verdict_not_ganharia(self):
        with TempDir() as d:
            fixture(d, verdict="empata")
            self.assert_refused(d, "empata")
            self.assert_refused(d, "empata", "--dry-run")

    def test_refuses_candidate_missing_from_run(self):
        with TempDir() as d:
            fixture(d)
            base.overlay(d, "other", {"tools.md": "x\n"})
            code, out = compose(d, cand="other")
            self.assertEqual(code, 1, out)
            self.assertIn("other", out)

    def test_refuses_protected_path(self):
        with TempDir() as d:
            fixture(d, files={"hooks/_lib.py": "# afrouxa\n"}, remove=[])
            self.assert_refused(d, "hooks/_lib.py")

    def test_refuses_outside_may_edit(self):
        with TempDir() as d:
            fixture(d, files={"AGENTS.md": "# A\n"}, remove=[".claude/skills/revisar-diff/SKILL.md"])
            self.assert_refused(d, "AGENTS.md")
            self.assert_refused(d, ".claude/skills/revisar-diff/SKILL.md")

    def test_refuses_dirty_tracked_tree(self):
        with TempDir() as d:
            fixture(d)
            write(os.path.join(d, "AGENTS.md"), "# sujo\n")
            self.assert_refused(d, "suja")

    def test_refuses_existing_branch(self):
        with TempDir() as d:
            fixture(d)
            git(d, "branch", "improve/lean")
            code, out = compose(d)
            self.assertEqual(code, 1, out)
            self.assertIn("improve/lean", out)

    def test_refuses_candidate_that_changes_nothing(self):
        with TempDir() as d:
            fixture(d, files={"harness/prompts/executor.md": "# e\n"}, remove=[])
            self.assert_refused(d, "não muda nada")


class ComposeTest(unittest.TestCase):
    def test_may_edit_rule(self):
        ok = ["harness/prompts/executor.md", ".claude/skills/briefing/SKILL.md", OPTIONS, "tools.md",
              "docs/padroes/defaults.md", ".hdev/config.json"]
        bad = ["harness/prompts/_shared/style.md", "harness/prompts/x/y.md", ".claude/skills/revisar-spec/SKILL.md",
               ".claude/skills", "AGENTS.md", "hdev/eval.py", "tests/test_x.py", "docs/padroes/naming.md"]
        for rel in ok:
            self.assertTrue(composemod.may_edit(rel), rel)
        for rel in bad:
            self.assertFalse(composemod.may_edit(rel), rel)

    def test_dry_run_prints_plan_and_changes_nothing(self):
        with TempDir() as d:
            fixture(d)
            head = git(d, "rev-parse", "HEAD").stdout
            code, out = compose(d, "--dry-run")
            self.assertEqual(code, 0, out)
            for needle in ("improve/lean", "muda: harness/prompts/executor.md", "sai: " + OPTIONS,
                           "muda: library/index.jsonl", "Harness-Edit: lean", "Harness-Probe: " + RUN):
                self.assertIn(needle, out)
            self.assertEqual(branches(d), [])
            self.assertEqual(git(d, "rev-parse", "HEAD").stdout, head)
            self.assertEqual(git(d, "status", "--porcelain").stdout, "")

    def test_compose_then_revert(self):
        with TempDir() as d:
            fixture(d)
            head = git(d, "rev-parse", "HEAD").stdout.strip()
            current = git(d, "symbolic-ref", "HEAD").stdout
            code, out = compose(d)
            self.assertEqual(code, 0, out)
            self.assertEqual(branches(d), ["improve/lean"])
            # um commit só, em cima do HEAD; a base e a árvore não mudam
            self.assertEqual(git(d, "rev-list", "--count", head + "..improve/lean").stdout.strip(), "1")
            self.assertEqual(git(d, "rev-parse", "improve/lean^").stdout.strip(), head)
            self.assertEqual(git(d, "rev-parse", "HEAD").stdout.strip(), head)
            self.assertEqual(git(d, "symbolic-ref", "HEAD").stdout, current)
            self.assertEqual(git(d, "status", "--porcelain").stdout, "")
            msg = git(d, "log", "-1", "--format=%B", "improve/lean").stdout
            self.assertIn("Harness-Edit: lean", msg)
            trailers = git(d, "log", "-1", "--format=%(trailers:key=Harness-Edit,valueonly)", "improve/lean").stdout
            self.assertEqual(trailers.strip(), "lean")
            self.assertEqual(git(d, "show", "improve/lean:harness/prompts/executor.md").stdout, "# e curto\n")
            self.assertNotEqual(git(d, "cat-file", "-e", "improve/lean:" + OPTIONS).returncode, 0)
            self.assertEqual(lib_status(d, "improve/lean"), ["active"])
            self.assertEqual(lib_status(d, "HEAD"), ["candidate"])
            # adoção = merge humano; o revert desfaz com commit novo
            git(d, "merge", "-q", "--ff-only", "improve/lean")
            code, out = hdev("improve", "revert", "--cand", "lean", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertEqual(base.slurp(d, "harness", "prompts", "executor.md"), "# e\n")
            self.assertTrue(os.path.isfile(os.path.join(d, *OPTIONS.split("/"))))
            self.assertEqual(lib_status(d, "HEAD"), ["candidate"])
            self.assertEqual(git(d, "rev-list", "--count", head + "..HEAD").stdout.strip(), "2")
            code, out = hdev("improve", "revert", "--cand", "lean", "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("já revertido", out)

    def test_compose_without_lesson_in_head_still_composes(self):
        with TempDir() as d:
            fixture(d, lesson=False)
            code, out = compose(d)
            self.assertEqual(code, 0, out)
            self.assertNotEqual(git(d, "cat-file", "-e", "improve/lean:library/index.jsonl").returncode, 0)


class RevertTest(unittest.TestCase):
    def test_revert_refuses_commit_without_trailer(self):
        with TempDir() as d:
            repo(d)
            head = git(d, "rev-parse", "HEAD").stdout
            code, out = hdev("improve", "revert", "--commit", "HEAD", "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("Harness-Edit", out)
            self.assertEqual(git(d, "rev-parse", "HEAD").stdout, head)

    def test_revert_refuses_unknown_candidate(self):
        with TempDir() as d:
            repo(d)
            code, out = hdev("improve", "revert", "--cand", "nada", "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("nada", out)


if __name__ == "__main__":
    unittest.main()
