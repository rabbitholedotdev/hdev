"""Canal latest, pin, rollback, init por referência, área e worktrees (F2-01, v0.3.3)."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, make_core, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import area, channel, release  # noqa: E402
from hdev import check as checkmod  # noqa: E402
from hdev import config as cfgmod  # noqa: E402
from hdev import judge as judgemod  # noqa: E402
from hdev.init import init  # noqa: E402


def head(repo):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def set_version(core, version, commit=True, changelog=True):
    path = os.path.join(core, "hdev", "__init__.py")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    write(path, re.sub(r'VERSION = "[^"]+"', 'VERSION = "%s"' % version[1:], text))
    log = os.path.join(core, "CHANGELOG.md")
    if changelog and os.path.isfile(log):  # SemVer do núcleo (ADR 0009): release pede a seção da versão
        with open(log, encoding="utf-8") as f:
            text = f.read()
        write(log, text.replace("## [Unreleased]\n", "## [Unreleased]\n\n## [%s] - 2099-01-01\n- teste\n" % version[1:], 1))
    if commit:
        git(core, "commit", "-q", "-a", "--no-verify", "-m", "versão %s" % version)


def judge_run(core, sha, verdict="pass", dirty=False, name="judge-20990101T000000Z"):
    write(os.path.join(core, ".hdev", "runs", name + ".json"),
          json.dumps({"verdict": verdict, "head_sha": sha, "dirty": dirty}))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.tmp = self._tmp.__enter__()
        self.core = make_core(self.tmp, version=None)
        self.releases = os.path.join(self.tmp, "opt", "releases")
        write(os.path.join(self.core, release.RELEASES_FILE), self.releases + "\n")
        set_version(self.core, "v9.9.9")
        git(self.core, "tag", "-a", "v9.9.9", "-m", "r")
        self.app = os.path.join(self.tmp, "app")

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def release(self, version):
        return hdev("release", version, "--core", self.core)

    def promote_first(self):
        judge_run(self.core, head(self.core))
        code, out = self.release("v9.9.9")
        self.assertEqual(code, 0, out)


class Promotion(Base):
    def test_releases_fora_do_nucleo_e_sem_juiz_nao_promove(self):
        code, out = self.release("v9.9.9")
        self.assertEqual(code, 2, out)
        self.assertIn("latest continua em (nenhuma)", out)
        self.assertTrue(os.path.isdir(os.path.join(self.releases, "v9.9.9")))
        self.assertFalse(os.path.lexists(os.path.join(self.core, "releases")))
        self.assertIsNone(release.current_latest(self.core))

    def test_juiz_pass_no_commit_da_tag_promove_e_init_segue_o_canal(self):
        self.promote_first()
        self.assertEqual(release.current_latest(self.core)[0], "v9.9.9")
        report = init(self.app, core=self.core)
        self.assertEqual(report["channel"], "latest")
        link = os.path.join(self.app, ".harnessdev")
        self.assertEqual(os.readlink(link), os.path.join(self.releases, "latest"))
        lock = read_json(os.path.join(self.app, ".harnessdev.lock"))
        self.assertEqual((lock["channel"], lock["releases"]), ("latest", self.releases))
        self.assertEqual(lock["version"], "v9.9.9")
        code, out = hdev("check", "--root", self.app)
        self.assertEqual(code, 0, out)
        self.assertIn("latest -> v9.9.9", out)

    def test_nova_release_chega_ao_app_sem_tocar_nele(self):
        self.promote_first()
        init(self.app, core=self.core)
        lock_before = read_json(os.path.join(self.app, ".harnessdev.lock"))
        write(os.path.join(self.core, "hooks", "nota.txt"), "x\n")
        git(self.core, "add", "-A")
        git(self.core, "commit", "-q", "--no-verify", "-m", "peça")
        judge_run(self.core, head(self.core), name="judge-20990102T000000Z")
        write(os.path.join(self.core, "docs", "progress.md"), "release\n")
        git(self.core, "add", "-A")
        git(self.core, "commit", "-q", "--no-verify", "-m", "docs")
        set_version(self.core, "v9.10.0")
        code, out = self.release("v9.10.0")
        self.assertEqual(code, 0, out)
        self.assertIn("tag criada", out)
        self.assertEqual(git(self.core, "cat-file", "-t", "v9.10.0").stdout.strip(), "tag")  # anotada
        self.assertTrue(os.path.realpath(os.path.join(self.app, ".harnessdev")).endswith("v9.10.0"))
        self.assertEqual(read_json(os.path.join(self.app, ".harnessdev.lock")), lock_before)
        self.assertEqual(hdev("check", "--root", self.app)[0], 0)
        report = init(self.app, core=self.core)
        self.assertEqual(report["written"].count(".harnessdev.lock"), 1)
        lock = read_json(os.path.join(self.app, ".harnessdev.lock"))
        self.assertEqual(lock["version"], "v9.10.0")
        self.assertEqual(lock["channel"], "latest")
        self.assertEqual(lock["commit"], head(self.core))

    def test_codigo_depois_do_juiz_nao_promove(self):
        self.promote_first()
        judge_run(self.core, head(self.core), name="judge-20990102T000000Z")
        write(os.path.join(self.core, "hdev", "extra.py"), "X = 1\n")
        git(self.core, "add", "-A")
        git(self.core, "commit", "-q", "--no-verify", "-m", "código sem juiz")
        set_version(self.core, "v9.10.0")
        code, out = self.release("v9.10.0")
        self.assertEqual(code, 2, out)
        self.assertEqual(release.current_latest(self.core)[0], "v9.9.9")

    def test_pass_com_mudanca_local_ou_fail_nao_vale(self):
        judge_run(self.core, head(self.core), dirty=True)
        judge_run(self.core, head(self.core), verdict="fail", name="judge-20990102T000000Z")
        self.assertEqual(self.release("v9.9.9")[0], 2)

    def test_tag_recusa_versao_diferente_e_arvore_suja(self):
        code, out = self.release("v9.11.0")
        self.assertEqual(code, 1, out)
        self.assertIn("VERSION", out)
        set_version(self.core, "v9.11.0", commit=False)
        code, out = self.release("v9.11.0")
        self.assertEqual(code, 1, out)
        self.assertIn("mudanças", out)

    def test_tag_recusa_versao_sem_secao_no_changelog(self):
        set_version(self.core, "v9.13.0", changelog=False)
        code, out = self.release("v9.13.0")
        self.assertEqual(code, 1, out)
        self.assertIn("CHANGELOG.md", out)
        self.assertIsNone(release.tag_commit(self.core, "v9.13.0"))

    def test_rollback_volta_e_so_para_promovida(self):
        self.promote_first()
        init(self.app, core=self.core)
        set_version(self.core, "v9.10.0")
        judge_run(self.core, head(self.core), name="judge-20990102T000000Z")
        self.assertEqual(self.release("v9.10.0")[0], 0)
        git(self.core, "tag", "-a", "v9.12.0", "-m", "nunca promovida")
        code, out = hdev("rollback", "--to", "v9.12.0", "--core", self.core)
        self.assertEqual(code, 1, out)
        code, out = hdev("rollback", "--core", self.core)
        self.assertEqual(code, 0, out)
        self.assertIn("latest -> v9.9.9 (antes v9.10.0)", out)
        self.assertTrue(os.path.realpath(os.path.join(self.app, ".harnessdev")).endswith("v9.9.9"))
        actions = [e["action"] for e in channel.history(self.core)]
        self.assertEqual(actions, ["promote", "promote", "rollback"])
        self.assertEqual(hdev("rollback", "--core", self.core)[0], 1)  # não há promoção anterior a v9.9.9


class Pin(Base):
    def test_sem_latest_init_fixa_na_maior_tag_com_nota(self):
        report = init(self.app, core=self.core)
        self.assertEqual(report["channel"], "pinned")
        self.assertTrue(any("pin --latest" in n for n in report["notes"]))
        self.assertEqual(hdev("check", "--root", self.app)[0], 0)

    def test_pin_fixa_e_volta_ao_canal(self):
        self.promote_first()
        init(self.app, core=self.core)
        code, out = hdev("pin", "v9.9.9", "--root", self.app)
        self.assertEqual(code, 0, out)
        lock = read_json(os.path.join(self.app, ".harnessdev.lock"))
        self.assertEqual(lock["channel"], "pinned")
        self.assertEqual(os.readlink(os.path.join(self.app, ".harnessdev")), os.path.join(self.releases, "v9.9.9"))
        self.assertEqual(hdev("check", "--root", self.app)[0], 0)
        code, out = hdev("pin", "--latest", "--root", self.app)
        self.assertEqual(code, 0, out)
        self.assertEqual(read_json(os.path.join(self.app, ".harnessdev.lock"))["channel"], "latest")
        self.assertEqual(hdev("pin", "--root", self.app)[0], 1)

    def test_lock_antigo_continua_valido(self):
        old = os.path.join(self.tmp, "old")
        dest, commit = release.install(self.core, "v9.9.9")
        os.makedirs(old)
        os.symlink(dest, os.path.join(old, ".harnessdev"))
        write(os.path.join(old, ".harnessdev.lock"),
              json.dumps({"version": "v9.9.9", "commit": commit, "core": self.core}))
        self.assertEqual(release.verify(old), (True, "v9.9.9 (%s)" % commit[:12]))

    def test_latest_quebrado_falha(self):
        self.promote_first()
        init(self.app, core=self.core)
        os.remove(os.path.join(self.releases, "latest"))
        self.assertFalse(release.verify(self.app)[0])


class Reference(Base):
    def test_agents_e_config_por_referencia(self):
        self.promote_first()
        init(self.app, core=self.core)
        with open(os.path.join(self.app, "AGENTS.md"), encoding="utf-8") as f:
            agents = f.read()
        self.assertIn("@.harnessdev/profiles/harness-developer/AGENTS.md", agents)
        own = read_json(os.path.join(self.app, ".hdev", "config.json"))
        self.assertNotIn("roles", own)
        cfg, err = cfgmod.load(self.app)
        self.assertIsNone(err)
        self.assertEqual(cfg["roles"]["judge"]["cli"], "grok")
        self.assertEqual(cfg["gates"]["fast"], own["gates"]["fast"])
        self.assertEqual(cfg["gates"]["full"], own["gates"]["full"])
        self.assertNotIn("hooks", cfg)
        self.assertNotIn("base_branch", cfg)
        own["roles"] = {"judge": {"model": "gpt-6.1-sol", "cli": "codex"}}
        write(os.path.join(self.app, ".hdev", "config.json"), json.dumps(own))
        cfg, _ = cfgmod.load(self.app)
        self.assertEqual(cfg["roles"]["judge"]["cli"], "codex")
        self.assertEqual(cfg["roles"]["executor"]["cli"], "claude")  # o que o app não escreveu vem da release
        self.assertTrue(os.path.isfile(os.path.join(self.app, ".claude", "skills", "hdev", "SKILL.md")))
        bad = [(r.name, r.detail) for r in checkmod.run(self.app) if not r.ok]
        self.assertEqual(bad, [])

    def test_juiz_grava_o_que_julgou(self):
        refs = judgemod.judged_refs(self.core, None, None)
        self.assertEqual((refs["head_sha"], refs["dirty"]), (head(self.core), False))
        write(os.path.join(self.core, "solto.txt"), "x\n")
        self.assertTrue(judgemod.judged_refs(self.core, None, None)["dirty"])  # pass sujo não libera promoção
        first = git(self.core, "rev-list", "--max-parents=0", "HEAD").stdout.strip()
        refs = judgemod.judged_refs(self.core, first, "HEAD")
        self.assertEqual((refs["base_sha"], refs["head_sha"], refs["dirty"]), (first, head(self.core), False))


class Area(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.tmp = self._tmp.__enter__()
        self.core = make_core(self.tmp)
        self.area = os.path.join(self.tmp, "area")
        for name in ("rag-mcp", "Projeto Velho", "estado", "_contexto"):
            os.makedirs(os.path.join(self.area, name))
        git(os.path.join(self.area, "rag-mcp"), "init", "-q")
        write(os.path.join(self.area, "rag-mcp", "README.md"), "x\n")
        git(os.path.join(self.area, "rag-mcp"), "add", "-A")
        git(os.path.join(self.area, "rag-mcp"), "commit", "-q", "--no-verify", "-m", "x")
        git(os.path.join(self.area, "estado"), "init", "-q")

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def test_check_area_sync_e_nomes(self):
        res = {r.name: r for r in area.check_area(self.area)}
        self.assertEqual(set(res), {"rag-mcp", "names"})
        self.assertFalse(res["rag-mcp"].ok)
        self.assertIn("Projeto Velho", res["names"].detail)
        done = dict(area.sync(self.area, core=self.core))
        self.assertIn("ligado", done["rag-mcp"])
        res = {r.name: r for r in area.check_area(self.area)}
        self.assertTrue(res["rag-mcp"].ok, res["rag-mcp"].detail)
        self.assertEqual(area.sync(self.area, core=self.core), [])  # ligado não é tocado de novo
        code, out = hdev("check", "--area", "--root", self.area)
        self.assertEqual(code, 0, out)

    def test_nucleo_e_worktree_dele_ficam_de_fora(self):
        os.rename(self.core, os.path.join(self.area, "harness-dev"))
        names = [n for n, _ in area.projects(self.area)]
        self.assertEqual(names, ["rag-mcp"])

    def test_wt_add_e_move_em_wt(self):
        repo = os.path.join(self.area, "rag-mcp")
        dest = area.wt_add(repo, "feat/Search-API")
        self.assertEqual(dest, os.path.join(self.area, "_wt", "rag-mcp-feat-search-api"))
        self.assertTrue(os.path.isfile(os.path.join(dest, "README.md")))
        with self.assertRaises(ValueError):
            area.wt_add(repo, "feat/Search-API")
        side = os.path.join(self.area, "rag-mcp-fix")
        git(repo, "worktree", "add", "-q", "-b", "fix/f0-01", side)
        moved = area.wt_move(side)
        self.assertEqual(moved, os.path.join(self.area, "_wt", "rag-mcp-fix-f0-01"))
        self.assertIn(moved, git(repo, "worktree", "list").stdout)
        self.assertFalse(os.path.exists(side))
        with self.assertRaises(ValueError):
            area.wt_move(repo)
        names = [n for n, _ in area.projects(self.area)]
        self.assertEqual(names, ["rag-mcp"])  # _wt fica de fora

    def test_projetos_em_pasta_pai_e_wt_na_raiz_da_area(self):
        rag = os.path.join(self.area, "rag")
        os.makedirs(rag)
        os.rename(os.path.join(self.area, "rag-mcp"), os.path.join(rag, "rag-mcp"))
        names = [n for n, p in area.projects(self.area)]
        self.assertEqual(names, ["rag-mcp"])
        self.assertTrue(area.projects(self.area)[0][1].endswith(os.path.join("rag", "rag-mcp")))
        dest = area.wt_add(os.path.join(rag, "rag-mcp"), "feat/x")
        self.assertEqual(dest, os.path.join(self.area, "_wt", "rag-mcp-feat-x"))
        os.makedirs(os.path.join(self.area, "harness"))
        os.rename(self.core, os.path.join(self.area, "harness", "harness-dev"))
        names = [n for n, _ in area.projects(self.area)]
        self.assertEqual(names, ["rag-mcp"])


if __name__ == "__main__":
    unittest.main()
