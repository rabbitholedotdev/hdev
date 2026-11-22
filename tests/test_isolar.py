"""ADR 0007: título no pedido, HDEV_NESTED nos aninhados e revisor em cópia isolada fora das áreas."""
import json
import os
import stat
import subprocess
import sys
import unittest
from unittest import mock

from hdev import handoff as h
from hdev import isolar, wrappers
from tests.helpers import BIN, HOOKS, TempDir, clean_env, git, write

FAKE = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
prompt = args[args.index("--single") + 1] if "--single" in args else args[-1]
cwd = os.getcwd()
if "-C" in args:
    cwd = args[args.index("-C") + 1]
os.makedirs(os.path.join(cwd, "docs", "reviews"), exist_ok=True)
with open(os.path.join(cwd, "docs", "reviews", "fake.md"), "w") as f:
    f.write(json.dumps({"cwd": cwd, "nested": os.environ.get("HDEV_NESTED"), "prompt": prompt}))
print(json.dumps({"ok": True}))
'''


def make_repo(d):
    git(d, "init", "-q")
    write(os.path.join(d, ".gitignore"), "*.log\n")
    for name in ("a.txt", "b.txt", "d.txt"):
        write(os.path.join(d, name), name + "\n")
    git(d, "add", "-A")
    git(d, "commit", "-q", "--no-verify", "-m", "base")


def fake_bin(d, name):
    path = os.path.join(d, name)
    write(path, FAKE)
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


def commits(d):
    return git(d, "rev-list", "--count", "HEAD").stdout.strip()


class Titulo(unittest.TestCase):
    def test_primeira_linha_vira_titulo(self):
        p = wrappers.with_title("grok-review", "Você é revisor goldfish...", "goldfish spec INF-004")
        self.assertEqual(p.splitlines()[0], "hdev grok-review: goldfish spec INF-004")
        self.assertIn("Você é revisor goldfish", p)

    def test_padrao_uma_linha_sem_menor_e_curto(self):
        self.assertEqual(wrappers.title_line("codex-exec"), "hdev codex-exec: revisão sem contexto")
        self.assertEqual(wrappers.title_line("grok-review", "<x>\n  y"), "hdev grok-review: x> y")
        self.assertLessEqual(len(wrappers.title_line("grok-review", "z" * 200)), len("hdev grok-review: ") + 60)

    def test_env_aninhado(self):
        self.assertEqual(wrappers.grok_env()["HDEV_NESTED"], "1")
        self.assertEqual(wrappers.codex_env()["HDEV_NESTED"], "1")


class Copia(unittest.TestCase):
    def test_copia_leva_head_indice_e_mudancas_e_devolve(self):
        with TempDir() as d, TempDir() as scratch:
            repo = os.path.join(d, "repo")
            os.makedirs(repo)
            make_repo(repo)
            write(os.path.join(repo, "a.txt"), "a mudou\n")
            write(os.path.join(repo, "b.txt"), "b staged\n")
            git(repo, "add", "b.txt")
            write(os.path.join(repo, "c.txt"), "novo\n")
            os.unlink(os.path.join(repo, "d.txt"))
            write(os.path.join(repo, "e.log"), "ignorado\n")
            with mock.patch.dict(os.environ, {"HDEV_SCRATCH_DIR": scratch}):
                with isolar.Copia(repo) as c:
                    self.assertNotEqual(c.work, repo)
                    self.assertTrue(c.work.startswith(scratch))
                    self.assertEqual(git(c.work, "diff").stdout, git(repo, "diff").stdout)
                    self.assertEqual(git(c.work, "diff", "--cached").stdout, git(repo, "diff", "--cached").stdout)
                    self.assertTrue(os.path.isfile(os.path.join(c.work, "c.txt")))
                    self.assertFalse(os.path.exists(os.path.join(c.work, "d.txt")))
                    self.assertFalse(os.path.exists(os.path.join(c.work, "e.log")))
                    write(os.path.join(c.work, "docs", "reviews", "r.md"), "go\n")
                self.assertEqual(os.listdir(scratch), [])
            with open(os.path.join(repo, "docs", "reviews", "r.md")) as f:
                self.assertEqual(f.read(), "go\n")
            self.assertIn("docs/reviews/r.md", c.devolvidos)
            self.assertEqual(commits(repo), "1")

    def test_conflito_grava_ao_lado(self):
        with TempDir() as d, TempDir() as scratch:
            make_repo(d)
            with mock.patch.dict(os.environ, {"HDEV_SCRATCH_DIR": scratch}):
                with isolar.Copia(d) as c:
                    write(os.path.join(d, "a.txt"), "orquestrador\n")
                    os.utime(os.path.join(d, "a.txt"), ns=(1, 1))
                    write(os.path.join(c.work, "a.txt"), "revisor\n")
            with open(os.path.join(d, "a.txt")) as f:
                self.assertEqual(f.read(), "orquestrador\n")
            with open(os.path.join(d, "a.txt.hdev-isolado")) as f:
                self.assertEqual(f.read(), "revisor\n")
            self.assertEqual(c.conflitos, ["a.txt"])

    def test_rascunho_dentro_das_areas_e_recusado(self):
        with TempDir() as d:
            make_repo(d)
            env = {"HDEV_AREAS": os.path.dirname(d), "HDEV_SCRATCH_DIR": d}
            with mock.patch.dict(os.environ, env):
                with self.assertRaises(isolar.IsolarError):
                    with isolar.Copia(d):
                        pass

    def test_devolver_recusa_link_para_fora(self):
        with TempDir() as d, TempDir() as scratch, TempDir() as fora:
            make_repo(d)
            docs = os.path.join(d, "docs")
            os.makedirs(os.path.join(docs, "reviews"))
            with mock.patch.dict(os.environ, {"HDEV_SCRATCH_DIR": scratch}):
                with isolar.Copia(d) as c:
                    os.rename(docs, docs + ".orig")
                    os.symlink(fora, docs)
                    write(os.path.join(c.work, "docs", "reviews", "r.md"), "go\n")
            self.assertFalse(os.path.exists(os.path.join(fora, "reviews", "r.md")))
            self.assertFalse(os.path.exists(os.path.join(fora, "r.md")))
            self.assertNotIn("docs/reviews/r.md", c.devolvidos)
            self.assertIn("docs/reviews/r.md", c.recusados)

    def test_conflito_substitui_link_isolado_para_fora(self):
        with TempDir() as d, TempDir() as scratch, TempDir() as fora:
            make_repo(d)
            with mock.patch.dict(os.environ, {"HDEV_SCRATCH_DIR": scratch}):
                with isolar.Copia(d) as c:
                    write(os.path.join(d, "a.txt"), "orquestrador\n")
                    os.utime(os.path.join(d, "a.txt"), ns=(1, 1))
                    os.symlink(fora, os.path.join(d, "a.txt.hdev-isolado"))
                    write(os.path.join(c.work, "a.txt"), "revisor\n")
            self.assertEqual(os.listdir(fora), [])
            self.assertFalse(os.path.islink(os.path.join(d, "a.txt.hdev-isolado")))
            with open(os.path.join(d, "a.txt.hdev-isolado")) as f:
                self.assertEqual(f.read(), "revisor\n")
            with open(os.path.join(d, "a.txt")) as f:
                self.assertEqual(f.read(), "orquestrador\n")
            self.assertEqual(c.conflitos, ["a.txt"])

    def test_troca_caminhos_do_repo(self):
        p = isolar.trocar_caminhos("leia /r/app/docs/x.md e /r/app-irmao/y e /r/app", "/r/app", "/tmp/c")
        self.assertEqual(p, "leia /tmp/c/docs/x.md e /r/app-irmao/y e /tmp/c")


class Cli(unittest.TestCase):
    def _run(self, cwd, scratch, *args, **env):
        e = clean_env(HDEV_SCRATCH_DIR=scratch, **env)
        e.pop("HDEV_NESTED", None)
        return subprocess.run([sys.executable, BIN, *args], capture_output=True, text=True, cwd=cwd, env=e, timeout=60)

    def _fake_out(self, repo):
        with open(os.path.join(repo, "docs", "reviews", "fake.md")) as f:
            return json.loads(f.read())

    def test_grok_review_isolado_titulo_nested_sem_commit(self):
        with TempDir() as d, TempDir() as scratch, TempDir() as bins:
            make_repo(d)
            before = commits(d)
            r = self._run(d, scratch, "grok-review", "--titulo", "goldfish teste", "--",
                          "revise %s/a.txt" % d, HDEV_GROK_BIN=fake_bin(bins, "grok"))
            self.assertEqual(r.returncode, 0, r.stderr)
            out = self._fake_out(d)
            self.assertNotEqual(out["cwd"], d)
            self.assertIn("hdev-isolado-", out["cwd"])
            self.assertEqual(out["nested"], "1")
            self.assertEqual(out["prompt"].splitlines()[0], "hdev grok-review: goldfish teste")
            self.assertNotIn(d + "/a.txt", out["prompt"])
            self.assertIn("devolvido ao repo", r.stderr)
            self.assertEqual(commits(d), before)
            self.assertEqual(os.listdir(scratch), [])

    def test_grok_review_sem_isolar_roda_no_lugar(self):
        with TempDir() as d, TempDir() as scratch, TempDir() as bins:
            make_repo(d)
            r = self._run(d, scratch, "grok-review", "--sem-isolar", "--", "oi", HDEV_GROK_BIN=fake_bin(bins, "grok"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(os.path.realpath(self._fake_out(d)["cwd"]), d)

    def test_codex_isolar_e_opcional(self):
        with TempDir() as d, TempDir() as scratch, TempDir() as bins:
            make_repo(d)
            fake = fake_bin(bins, "codex")
            r = self._run(d, scratch, "codex-exec", "--", "oi", HDEV_CODEX_BIN=fake)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = self._fake_out(d)
            self.assertEqual(out["cwd"], d)
            self.assertEqual(out["nested"], "1")
            self.assertEqual(out["prompt"].splitlines()[0], "hdev codex-exec: revisão sem contexto")
            os.unlink(os.path.join(d, "docs", "reviews", "fake.md"))
            r = self._run(d, scratch, "codex-exec", "--isolar", "--titulo", "diff", "--", "oi", HDEV_CODEX_BIN=fake)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("hdev-isolado-", self._fake_out(d)["cwd"])

    def test_fora_de_git_roda_no_lugar_e_avisa(self):
        with TempDir() as d, TempDir() as scratch, TempDir() as bins:
            r = self._run(d, scratch, "grok-review", "--", "oi", HDEV_GROK_BIN=fake_bin(bins, "grok"))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("sem cópia isolada", r.stderr)
            self.assertEqual(os.path.realpath(self._fake_out(d)["cwd"]), d)


class HooksAninhados(unittest.TestCase):
    def _hook(self, name, event, cwd, **env):
        return subprocess.run([sys.executable, os.path.join(HOOKS, name)], input=json.dumps(event),
                              capture_output=True, text=True, cwd=cwd, timeout=60,
                              env=clean_env(CLAUDE_PROJECT_DIR=cwd, **env))

    def test_progress_e_gate_se_calam(self):
        with TempDir() as d:
            make_repo(d)
            write(os.path.join(d, "src", "x.py"), "x = 1\n")
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"gates": {"fast": ["false"]}}))
            ev = {"cwd": d, "session_id": "s", "hook_event_name": "Stop"}
            self.assertEqual(self._hook("progress_guard.py", ev, d).returncode, 2)
            self.assertEqual(self._hook("progress_guard.py", ev, d, HDEV_NESTED="1").returncode, 0)
            self.assertEqual(self._hook("gate_tests.py", ev, d, HDEV_GATE_TESTS="1").returncode, 2)
            self.assertEqual(self._hook("gate_tests.py", ev, d, HDEV_GATE_TESTS="1", HDEV_NESTED="1").returncode, 0)

    def test_handoff_guard_aninhado_nao_grava_estado(self):
        with TempDir() as d:
            ev = {"hook_event_name": "Stop", "session_id": "grok-1", "transcript_path": os.path.join(d, "t.jsonl"),
                  "cwd": d}
            r = self._hook("handoff_guard.py", ev, d, HDEV_NESTED="1")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "")
            self.assertFalse(os.path.exists(os.path.join(d, ".hdev", "state", "session.json")))

    def test_transcript_de_grok_ou_codex_nao_troca_a_sessao(self):
        with TempDir() as d:
            h.persist_session(d, "claude-1", transcript_path="/home/u/.claude/projects/x/claude-1.jsonl")
            for tp in ("/home/u/.grok/sessions/%2Fsrv%2Fx/01a1/updates.jsonl",
                       "/home/u/.config/ratoeira/grok-contas/ca/sessions/x/01a1/updates.jsonl",
                       "/home/u/.codex/sessions/2026/11/15/rollout-2026-11-15T07-00-00-abc.jsonl"):
                self.assertTrue(h.foreign_transcript(tp), tp)
                out, st = h.hook_decide(d, {"hook_event_name": "Stop", "session_id": "outro", "transcript_path": tp,
                                            "cwd": d})
                self.assertIsNone(out)
                self.assertEqual(h.load_state(d)["session_id"], "claude-1")
            self.assertFalse(h.foreign_transcript("/home/u/.claude/projects/x/claude-1.jsonl"))
            self.assertFalse(h.foreign_transcript(None))


if __name__ == "__main__":
    unittest.main()
