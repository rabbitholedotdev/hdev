"""improve só em relatório: lista protegida, overlay, dry-run, teto, três braços, veredito, biblioteca."""
import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import TempDir, git, hdev, write  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hdev import check as checkmod  # noqa: E402
from hdev import eval as evalmod  # noqa: E402
from hdev.improve import probe as probemod  # noqa: E402

PROTECTED = "hooks/\nharness/hooks/\nhdev/improve/\n"


def repo(d):
    """Repo mínimo com a lista protegida e um caso que passa sempre."""
    git(d, "init", "-q")
    write(os.path.join(d, ".gitignore"), ".hdev/runs/\n.hdev/state/\n.hdev/cache/\n.hdev/overlays/\n")
    write(os.path.join(d, "CLAUDE.md"), "@AGENTS.md\n")
    write(os.path.join(d, "AGENTS.md"), "# A\n" + "linha longa do mapa para o xray medir\n" * 40)
    write(os.path.join(d, "harness", "prompts", "executor.md"), "# e\n")
    write(os.path.join(d, "harness", "protected.txt"), "# lista\n" + PROTECTED)
    write(os.path.join(d, "hooks", "_lib.py"), "# guarda\n")
    write(os.path.join(d, ".claude", "skills", "briefing", "references", "options.md"), "opções\n")
    task = {"id": "ok", "repo": ".", "base_sha": "HEAD", "prompt": None, "spec": None, "caps": {"runs": 12},
            "draft": False, "acceptance": [{"cmd": "python3 -c \"print('ok')\"", "expect_output": "ok"}]}
    write(os.path.join(d, "evals", "tasks", "ok", "task.json"), json.dumps(task) + "\n")
    git(d, "add", "-A")
    proc = git(d, "commit", "-q", "--no-verify", "-m", "base")
    assert proc.returncode == 0, proc.stderr


def overlay(d, cand, files=None, mark="domínio", remove=None):
    folder = os.path.join(d, ".hdev", "overlays", cand)
    os.makedirs(folder, exist_ok=True)
    for rel, text in (files or {}).items():
        write(os.path.join(folder, rel), text)
    meta = {"id": cand, "mark": mark, "summary": "candidata de teste %s" % cand, "remove": remove or []}
    write(os.path.join(d, ".hdev", "overlays", cand + ".json"), json.dumps(meta) + "\n")


def slurp(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as handle:
        return handle.read()


def runs_in(d, prefix):
    return sorted(glob.glob(os.path.join(d, ".hdev", "runs", prefix + "*")))


def status_outside(d):
    out = git(d, "status", "--porcelain", "--untracked-files=all").stdout.splitlines()
    return [line for line in out if not line[3:].startswith((".hdev/", "library/"))]


class ProtectedTest(unittest.TestCase):
    def test_overlay_in_protected_path_fails_check(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "bad", {"hooks/_lib.py": "# afrouxa\n"})
            res = checkmod.check_overlays(d)
            self.assertFalse(res.ok)
            self.assertIn("hooks/_lib.py", res.detail)

    def test_remove_of_protected_parent_fails_check(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "cut", remove=["harness"])
            res = checkmod.check_overlays(d)
            self.assertFalse(res.ok)
            self.assertIn("harness", res.detail)

    def test_clean_overlay_passes_check(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "lean", {"harness/prompts/executor.md": "# e curto\n"})
            res = checkmod.check_overlays(d)
            self.assertTrue(res.ok, res.detail)

    def test_no_overlay_passes_and_check_lists_it(self):
        with TempDir() as d:
            repo(d)
            self.assertTrue(checkmod.check_overlays(d).ok)
        self.assertIn(checkmod.check_overlays, checkmod.CHECKS)

    def test_protected_overlay_refused_before_running(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "bad", {"hdev/improve/probe.py": "# x\n"})
            with self.assertRaises(evalmod.EvalError) as ctx:
                probemod.probe(d, "ok", ["bad"], 3, "fake")
            self.assertIn("hdev/improve/probe.py", str(ctx.exception))
            self.assertEqual(runs_in(d, "eval-"), [])


class ProbeTest(unittest.TestCase):
    def test_dry_run_prints_plan_and_runs_nothing(self):
        with TempDir() as d:
            repo(d)
            code, out = hdev("improve", "probe", "--case", "ok", "--cand", "demo", "--runs", "3",
                             "--dry-run", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("plain, base, cand-demo", out)
            self.assertIn("3 braços × 3 corridas = 9", out)
            self.assertEqual(runs_in(d, ""), [])
            self.assertFalse(os.path.exists(os.path.join(d, "library")))

    def test_run_cap_refuses_over_twelve(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "a")
            overlay(d, "b")
            code, out = hdev("improve", "probe", "--case", "ok", "--cand", "a,b", "--runs", "4",
                             "--runner", "fake", "--root", d)
            self.assertEqual(code, 2, out)
            self.assertIn("teto é 12", out)
            self.assertEqual(runs_in(d, ""), [])

    def test_runs_below_three_refused(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "a")
            with self.assertRaises(evalmod.EvalError):
                probemod.probe(d, "ok", ["a"], 2, "fake")

    def test_probe_records_three_arms_and_adopts_nothing(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "lean", {"AGENTS.md": "# A\n"}, remove=[".claude/skills/briefing/references/options.md"])
            before = status_outside(d)
            head = git(d, "rev-parse", "HEAD").stdout
            res = probemod.probe(d, "ok", ["lean"], 3, "fake", unit="u-test")
            rows = res["eval"]["results"]
            self.assertEqual(sorted({(r["arm"], r["run"]) for r in rows}),
                             sorted((a, n) for a in ("plain", "base", "cand-lean") for n in (1, 2, 3)))
            self.assertTrue(all(r["pass"] for r in rows))
            record = json.loads(slurp(d, ".hdev", "runs", res["run"]))
            self.assertEqual(record["kind"], "improve")
            self.assertEqual(record["adopted"], [])
            cand = record["candidates"][0]
            self.assertEqual(cand["id"], "lean")
            self.assertIn(cand["verdict"], probemod.VERDICTS)
            self.assertLess(cand["metrics"]["xray"], record["arms"]["base"]["xray"])
            report = slurp(d, ".hdev", "runs", res["report"])
            self.assertIn("não adotado", report)
            self.assertNotIn("%%", report)
            # a candidata só tocou o clone
            self.assertEqual(status_outside(d), before)
            self.assertEqual(git(d, "rev-parse", "HEAD").stdout, head)
            self.assertTrue(os.path.isfile(os.path.join(d, ".claude", "skills", "briefing", "references",
                                                        "options.md")))
            self.assertEqual(slurp(d, "AGENTS.md").count("\n"), 41)

    def test_library_item_from_probe(self):
        with TempDir() as d:
            repo(d)
            overlay(d, "lean", {"AGENTS.md": "# A\n"})
            res = probemod.probe(d, "ok", ["lean"], 3, "fake", unit="u-test")
            lines = slurp(d, "library", "index.jsonl").splitlines()
            self.assertEqual(len(lines), 1)
            item = json.loads(lines[0])
            self.assertEqual(item["source"], "improve")
            self.assertEqual(item["status"], "candidate")
            self.assertEqual(item["generalization"], "pending")
            ev = item["evidence"][0]
            self.assertEqual(ev["unit"], "u-test")
            self.assertEqual(ev["run"], res["run"])
            self.assertIn("xray", ev["delta"])
            from hdev.library import store
            self.assertEqual(store.problems(d), [])

    def test_demo_proposal_is_deterministic_and_marked(self):
        with TempDir() as d:
            repo(d)
            first = probemod.propose(d, "demo")
            second = probemod.propose(d, "demo")
            self.assertEqual(first, second)
            self.assertIn(first["mark"], probemod.MARKS)
            self.assertTrue(first["remove"])
            self.assertEqual(probemod.overlay_problems(d), [])

    def test_probe_runner_claude_aceita_dois_e_mostra_modelo(self):
        from test_eval import fake_claude
        with TempDir() as d:
            repo(d)
            overlay(d, "lean", {"AGENTS.md": "# A\n"})
            path = os.path.join(d, "evals", "tasks", "ok", "task.json")
            task = json.loads(slurp(path))
            task["prompt"] = "faz"
            write(path, json.dumps(task) + "\n")
            git(d, "add", "-A")
            git(d, "commit", "-q", "--no-verify", "-m", "prompt")
            fake_claude(d)
            code, out = hdev("improve", "probe", "--case", "ok", "--cand", "lean", "--runs", "2",
                             "--runner", "claude", "--dry-run", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("modelo: claude-sonnet-5-5", out)
            res = probemod.probe(d, "ok", ["lean"], 2, "claude", unit="u-test")
            self.assertEqual(len(res["eval"]["results"]), 6)
            self.assertTrue(all(r["model"] == "claude-sonnet-5-5" for r in res["eval"]["results"]))
            record = json.loads(slurp(d, ".hdev", "runs", res["run"]))
            self.assertEqual(record["model"], "claude-sonnet-5-5")
            self.assertEqual(record["arms"]["base"]["model"], "claude-sonnet-5-5")
            self.assertIn("claude-sonnet-5-5", slurp(d, ".hdev", "runs", res["report"]))


class VerdictTest(unittest.TestCase):
    BASE = {"runs": 3, "pass": 1.0, "tokens": 100, "seconds": 10.0, "xray": 1000}

    def cand(self, **kw):
        out = dict(self.BASE)
        out.update(kw)
        return out

    def test_equal_ties(self):
        self.assertEqual(probemod.verdict(self.BASE, self.cand()), "empata")

    def test_cost_better_by_fifteen_wins(self):
        self.assertEqual(probemod.verdict(self.BASE, self.cand(tokens=85)), "ganharia")

    def test_cost_better_below_fifteen_ties(self):
        self.assertEqual(probemod.verdict(self.BASE, self.cand(tokens=90)), "empata")

    def test_quality_drop_loses_even_if_cheaper(self):
        self.assertEqual(probemod.verdict(self.BASE, self.cand(**{"pass": 0.67, "tokens": 10})), "perde")

    def test_cost_worse_by_fifteen_loses(self):
        self.assertEqual(probemod.verdict(self.BASE, self.cand(xray=1150, tokens=50)), "perde")

    def test_missing_metric_ignored(self):
        self.assertEqual(probemod.verdict(dict(self.BASE, tokens=None), self.cand(tokens=None)), "empata")

    def test_no_runs_no_evidence(self):
        self.assertEqual(probemod.verdict(self.BASE, self.cand(runs=0)), "sem evidência")
        self.assertEqual(probemod.verdict(dict(self.BASE, runs=0), self.cand()), "sem evidência")

    def test_metrics_use_median(self):
        rows = [{"pass": True, "tokens": {"input": 10, "output": 5}, "seconds": s, "xray": 7}
                for s in (1.0, 2.0, 50.0)]
        got = probemod.arm_metrics(rows)
        self.assertEqual(got, {"runs": 3, "pass": 1.0, "tokens": 15, "seconds": 2.0, "xray": 7})

    def test_diff_alert_over_half(self):
        self.assertTrue(probemod.diff_alert(10, 6))
        self.assertFalse(probemod.diff_alert(10, 5))


if __name__ == "__main__":
    unittest.main()
