"""Fechamento da unidade e SemVer (ADR 0009): marco com trailers, base marcada obrigatória, squash opcional,
tag de app só na publicação, CHANGELOG.md no release do núcleo."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import VERSION  # noqa: E402
from hdev import config as cfgmod  # noqa: E402
from hdev import versao  # noqa: E402

PLAN = "docs/plan-inf-006-banco.md"
TURNO = "Base directory for this skill: /srv/hdev/areas/x/.claude/skills/hdev"


def commit(d, msg, allow_empty=False):
    git(d, "add", "-A")
    r = git(d, "commit", "-q", "--no-verify", *(["--allow-empty"] if allow_empty else []), "-m", msg)
    assert r.returncode == 0, r.stderr
    return git(d, "rev-parse", "HEAD").stdout.strip()


def judge_run(d, head, base, verdict="pass", plan=PLAN, dirty=False, name="judge-20990101T000000Z"):
    write(os.path.join(d, ".hdev", "runs", name + ".json"), json.dumps(
        {"verdict": verdict, "plan": plan, "head_sha": head, "base_sha": base, "dirty": dirty,
         "attempts": [{"cli": "grok", "verdict": verdict}]}))


def last_message(d):
    return git(d, "log", "-1", "--format=%B").stdout


class Fechar(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.d = self._tmp.__enter__()
        git(self.d, "init", "-q")
        git(self.d, "config", "user.name", "t")
        git(self.d, "config", "user.email", "t@example.invalid")
        write(os.path.join(self.d, ".gitignore"), ".hdev/runs/\n.hdev/state/\n")
        write(os.path.join(self.d, "README.md"), "x\n")
        self.base = commit(self.d, "inicial")
        write(os.path.join(self.d, PLAN), "# Plano — SQLite WAL e migrações\n")
        write(os.path.join(self.d, "app.mjs"), "// 1\n")
        commit(self.d, TURNO)
        write(os.path.join(self.d, "app.mjs"), "// 2\n")
        self.head = commit(self.d, TURNO)

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def fechar(self, *extra):
        return hdev("fechar", "--plan", PLAN, "--root", self.d, *extra)

    def marcar(self, ref=None):
        code, out = hdev("base", "--plan", PLAN, "--root", self.d, "--marcar", ref or self.base)
        self.assertEqual(code, 0, out)

    def test_sem_base_marcada_nao_fecha(self):
        judge_run(self.d, self.head, self.base)
        code, out = self.fechar()
        self.assertEqual(code, 1, out)
        self.assertIn("--marcar", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), self.head)

    def test_base_gravada_pelo_juiz_nao_vale(self):
        os.makedirs(os.path.join(self.d, ".hdev", "state"))
        write(os.path.join(self.d, ".hdev", "state", "bases.json"), json.dumps(
            {"INF-006": {"base": self.base, "plan": PLAN, "origem": "1º hdev judge (deduzida: x)"}}))
        judge_run(self.d, self.head, self.base)
        code, out = self.fechar()
        self.assertEqual(code, 1, out)
        self.assertIn("1º hdev judge", out)

    def test_pass_gera_marco_com_trailers_e_preserva_checkpoints(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        code, out = self.fechar("--resumo", "SQLite WAL e migrações")
        self.assertEqual(code, 0, out)
        msg = last_message(self.d)
        self.assertTrue(msg.startswith("INF-006 feito: SQLite WAL e migrações; juiz pass\n"), msg)
        trailers = git(self.d, "log", "-1", "--format=%(trailers:only,unfold)").stdout
        for line in ("Unidade: INF-006", "Base: %s" % self.base[:12], "Head: %s" % self.head[:12],
                     "Juiz: pass (grok, judge-20990101T000000Z)", "Harness-Versao: v%s" % VERSION):
            self.assertIn(line, trailers)
        self.assertEqual(git(self.d, "rev-parse", "HEAD~1").stdout.strip(), self.head)  # sem squash
        self.assertEqual(git(self.d, "rev-list", "--count", "HEAD").stdout.strip(), "4")
        self.assertIn("INF-006 | base %s | juiz pass" % self.base[:7], out)

    def test_resumo_padrao_vem_do_titulo_do_plano(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        self.assertEqual(self.fechar()[0], 0)
        self.assertIn("INF-006 feito: SQLite WAL e migrações; juiz pass", last_message(self.d))

    def test_sem_pass_so_com_override(self):
        self.marcar()
        judge_run(self.d, self.head, self.base, verdict="fail")
        code, out = self.fechar()
        self.assertEqual(code, 1, out)
        self.assertIn("--override", out)
        code, out = self.fechar("--override", "operator: juiz falso negativo por commit-turno")
        self.assertEqual(code, 0, out)
        msg = last_message(self.d)
        self.assertIn("; juiz override\n", msg)
        self.assertIn("Override: operator: juiz falso negativo por commit-turno", msg)
        self.assertNotIn("Juiz: pass", msg)

    def test_pass_de_outro_head_base_ou_sujo_nao_vale(self):
        self.marcar()
        judge_run(self.d, self.head, self.base, dirty=True, name="judge-20990101T000001Z")
        judge_run(self.d, self.head, "0" * 40, name="judge-20990101T000002Z")
        judge_run(self.d, self.head, self.base, plan="docs/plan-inf-007-x.md", name="judge-20990101T000003Z")
        self.assertEqual(self.fechar()[0], 1)

    def test_codigo_depois_do_juiz_pede_juiz_de_novo_docs_nao(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        write(os.path.join(self.d, "docs", "progress.md"), "INF-006 em fechamento\n")
        commit(self.d, TURNO)
        self.assertEqual(self.fechar("--dry-run")[0], 0)
        write(os.path.join(self.d, "app.mjs"), "// 3\n")
        commit(self.d, TURNO)
        self.assertEqual(self.fechar("--dry-run")[0], 1)

    def test_arvore_suja_e_intervalo_misturado_nao_fecham(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        write(os.path.join(self.d, "app.mjs"), "// sujo\n")
        code, out = self.fechar()
        self.assertEqual(code, 1, out)
        self.assertIn("árvore", out)
        write(os.path.join(self.d, "app.mjs"), "// 4\n")
        head = commit(self.d, "INF-004: publica no gateway")
        judge_run(self.d, head, self.base, name="judge-20990102T000000Z")
        code, out = self.fechar()
        self.assertEqual(code, 1, out)
        self.assertIn("misturado", out)

    def test_dry_run_nao_commita(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        code, out = self.fechar("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("Unidade: INF-006", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), self.head)

    def test_squash_opcional_guarda_backup_e_pede_juiz_de_novo(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        tree = git(self.d, "rev-parse", "HEAD^{tree}").stdout.strip()
        code, out = self.fechar("--squash")
        self.assertEqual(code, 0, out)
        self.assertIn("juiz --plan", out.replace("hdev judge", "juiz"))
        self.assertEqual(git(self.d, "rev-parse", "HEAD~1").stdout.strip(), self.base)
        diff = git(self.d, "diff", "--name-only", tree, "HEAD").stdout.strip()
        self.assertEqual(diff, "evals/tasks/INF-006/task.json")
        bkp = "bkp/inf-006-%s" % self.head[:12]
        self.assertEqual(git(self.d, "rev-parse", bkp).stdout.strip(), self.head)

    def test_suite_vermelha_nao_fecha_verde_fecha(self):
        red = [sys.executable, "-c", "import sys; sys.exit(1)"]
        green = [sys.executable, "-c", "import sys; sys.exit(0)"]
        write(os.path.join(self.d, ".hdev", "config.json"), json.dumps(
            {"gates": {"full": red, "timeout": 30}}))
        head = commit(self.d, TURNO)
        self.marcar()
        judge_run(self.d, head, self.base)
        code, out = self.fechar("--override", "operator: override não dispensa a suíte")
        self.assertEqual(code, 1, out)
        self.assertIn("suíte vermelha", out)
        write(os.path.join(self.d, ".hdev", "config.json"), json.dumps(
            {"gates": {"full": green, "timeout": 30}}))
        head = commit(self.d, TURNO)
        judge_run(self.d, head, self.base, name="judge-20990103T000000Z")
        self.assertEqual(self.fechar()[0], 0)

    def test_squash_recusa_intervalo_ja_enviado(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        git(self.d, "update-ref", "refs/remotes/origin/main", self.head)
        code, out = self.fechar("--squash")
        self.assertEqual(code, 1, out)
        self.assertIn("remoto", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), self.head)

    def _off_base(self, extra=None):
        cfg = {"base_branch": "branch-base"}
        if extra:
            cfg.update(extra)
        write(os.path.join(self.d, ".hdev", "config.json"), json.dumps(cfg))
        return commit(self.d, "configura a branch base")

    def _runs(self):
        folder = os.path.join(self.d, ".hdev", "runs")
        return [n for n in os.listdir(folder) if n.startswith("fechar-")] if os.path.isdir(folder) else []

    def test_work_plan_fecha_com_id_da_pasta(self):
        plan = "work/subtrair/plan.md"
        write(os.path.join(self.d, plan), "# Plano — subtrair\n")
        head = commit(self.d, "turno do plano")
        code, out = hdev("base", "--plan", plan, "--root", self.d, "--marcar", self.base)
        self.assertEqual(code, 0, out)
        judge_run(self.d, head, self.base, plan=plan, name="judge-20990104T000000Z")
        code, out = hdev("fechar", "--plan", plan, "--root", self.d)
        self.assertEqual(code, 0, out)
        self.assertTrue(last_message(self.d).startswith("subtrair feito:"), last_message(self.d))

    def test_plano_legado_sem_id_continua_recusado(self):
        plan = "docs/plan-subtrair.md"
        write(os.path.join(self.d, plan), "# Plano — subtrair\n")
        commit(self.d, "plano sem id no nome")
        code, out = hdev("fechar", "--plan", plan, "--root", self.d, "--dry-run")
        self.assertEqual(code, 1, out)
        self.assertIn("plano sem id", out)

    def test_na_branch_base_configurada_o_marco_nasce(self):
        branch = git(self.d, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        write(os.path.join(self.d, ".hdev", "config.json"), json.dumps({"base_branch": branch}))
        head = commit(self.d, "na base")
        self.marcar()
        judge_run(self.d, head, self.base, name="judge-20990105T000000Z")
        code, out = self.fechar()
        self.assertEqual(code, 0, out)
        self.assertIn("fechada", out)
        self.assertNotIn("pulado", out)

    def test_fora_da_base_pula_marco_e_grava_veredito(self):
        head = self._off_base()
        code, out = self.fechar()
        self.assertEqual(code, 0, out)
        self.assertIn("commit do marco pulado", out)
        self.assertIn("branch-base", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual(len(self._runs()), 1)
        data = read_json(os.path.join(self.d, ".hdev", "runs", self._runs()[0]))
        self.assertEqual(data["milestone"], "skipped")
        self.assertEqual(data["verdict"], "pass")
        self.assertEqual(data["unidade"], "INF-006")
        self.assertEqual(data["base_branch"], "branch-base")
        self.assertEqual(data["head"], head)

    def test_fora_da_base_dry_run_nao_commita(self):
        head = self._off_base()
        code, out = self.fechar("--dry-run")
        self.assertEqual(code, 0, out)
        self.assertIn("commit do marco pulado", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual(len(self._runs()), 1)

    def test_fora_da_base_squash_nao_reescreve(self):
        self.marcar()
        judge_run(self.d, self.head, self.base)
        head = self._off_base()
        code, out = self.fechar("--squash")
        self.assertEqual(code, 0, out)
        self.assertIn("pulado", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)
        self.assertEqual(git(self.d, "branch", "--list", "bkp/*").stdout.strip(), "")

    def test_fora_da_base_suite_vermelha_e_arvore_suja_nao_passam(self):
        red = [sys.executable, "-c", "import sys; sys.exit(1)"]
        head = self._off_base({"gates": {"full": red, "timeout": 30}})
        code, out = self.fechar()
        self.assertEqual(code, 1, out)
        self.assertIn("suíte vermelha", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)
        write(os.path.join(self.d, ".hdev", "config.json"), json.dumps({"base_branch": "branch-base"}))
        head = commit(self.d, "suite verde ausente")
        write(os.path.join(self.d, "app.mjs"), "// sujo\n")
        code, out = self.fechar("--dry-run")
        self.assertEqual(code, 1, out)
        self.assertIn("árvore", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)

    def test_fora_da_base_base_do_juiz_mistura_e_ancestral_nao_passam(self):
        head = self._off_base()
        write(os.path.join(self.d, ".hdev", "state", "bases.json"), json.dumps(
            {"INF-006": {"base": self.base, "plan": PLAN, "origem": "1º hdev judge (deduzida: x)"}}))
        code, out = self.fechar("--dry-run")
        self.assertEqual(code, 1, out)
        self.assertIn("1º hdev judge", out)
        self.marcar()
        write(os.path.join(self.d, "app.mjs"), "// outra unidade\n")
        head = commit(self.d, "INF-004: publica no gateway")
        code, out = self.fechar("--dry-run")
        self.assertEqual(code, 1, out)
        self.assertIn("misturado", out)
        tree = git(self.d, "rev-parse", "HEAD^{tree}").stdout.strip()
        lado = git(self.d, "commit-tree", tree, "-m", "lado").stdout.strip()
        code, out = hdev("base", "--plan", PLAN, "--root", self.d, "--marcar", lado, "--force")
        self.assertEqual(code, 0, out)
        code, out = self.fechar("--dry-run")
        self.assertEqual(code, 1, out)
        self.assertIn("ancestral", out)
        self.assertEqual(git(self.d, "rev-parse", "HEAD").stdout.strip(), head)


class ReleaseBase(unittest.TestCase):
    def test_base_branch_da_release_nao_vaza_para_o_app(self):
        with TempDir() as d:
            rel = os.path.join(d, "rel")
            write(os.path.join(rel, ".hdev", "config.json"), json.dumps({
                "base_branch": "f2-11-v0.6.0", "version": 1,
                "hooks": {"Stop": []}, "skills": {"F2": ["hdev"]},
                "caps": {"agents": 80, "hooks": 7, "skills": 5, "subagents": 2, "progress": 2000},
                "gates": {"fast": ["python3", "-m", "unittest"], "full": ["python3", "-m", "unittest"]},
                "roles": {"judge": {"cli": "grok", "model": "grok-4.7"}},
            }))
            os.symlink(rel, os.path.join(d, ".harnessdev"))
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"profile": "app"}))
            cfg, err = cfgmod.load(d)
            self.assertIsNone(err)
            for key in ("base_branch", "hooks", "skills", "caps", "gates"):
                self.assertNotIn(key, cfg)
            self.assertEqual(cfg["roles"]["judge"]["cli"], "grok")
            write(os.path.join(d, ".hdev", "config.json"), json.dumps(
                {"profile": "app", "base_branch": "main", "gates": {"fast": ["app"], "full": ["app"]}}))
            cfg, err = cfgmod.load(d)
            self.assertIsNone(err)
            self.assertEqual(cfg["base_branch"], "main")
            self.assertEqual(cfg["gates"]["fast"], ["app"])
            self.assertNotIn("hooks", cfg)


class AppTag(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.d = self._tmp.__enter__()
        git(self.d, "init", "-q")
        git(self.d, "config", "user.name", "t")
        git(self.d, "config", "user.email", "t@example.invalid")
        write(os.path.join(self.d, "mcc", "VERSION"), "0.1.0\n")
        write(os.path.join(self.d, "mcc", "CHANGELOG.md"), "# Changelog\n\n## [0.1.0] - 2026-11-15\n- Inbox\n")
        write(os.path.join(self.d, "gestor", "x.mjs"), "\n")
        self.head = commit(self.d, "inicial")

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def tag(self, *args):
        return hdev("app", "tag", *args, "--repo", self.d)

    def test_so_na_publicacao(self):
        code, out = self.tag("mcc", "v0.1.0")
        self.assertEqual(code, 1, out)
        self.assertIn("--publicado", out)
        self.assertEqual(git(self.d, "tag").stdout.strip(), "")

    def test_cria_tag_anotada_com_hifen_e_e_imutavel(self):
        code, out = self.tag("mcc", "v0.1.0", "--publicado")
        self.assertEqual(code, 0, out)
        self.assertEqual(git(self.d, "cat-file", "-t", "mcc-v0.1.0").stdout.strip(), "tag")
        self.assertEqual(git(self.d, "rev-parse", "mcc-v0.1.0^{commit}").stdout.strip(), self.head)
        self.assertIn("Harness-Versao:", git(self.d, "tag", "-l", "-n20", "mcc-v0.1.0").stdout)
        self.assertEqual(self.tag("mcc", "v0.1.0", "--publicado")[0], 1)

    def test_version_e_changelog_do_app_tem_de_bater(self):
        code, out = self.tag("mcc", "v0.2.0", "--publicado")
        self.assertEqual(code, 1, out)
        self.assertIn("VERSION", out)
        code, out = self.tag("gestor", "v0.1.0", "--publicado")
        self.assertEqual(code, 0, out)
        self.assertIn("sem VERSION", out)

    def test_nomes_invalidos(self):
        for app, ver in (("MCC", "v0.1.0"), ("mcc/x", "v0.1.0"), ("mcc", "0.1"), ("mcc-v1", "v0.1.0")):
            with self.assertRaises(versao.VersaoError):
                versao.app_tag_name(app, ver)
        self.assertEqual(versao.app_tag_name("mcc", "0.1.0"), "mcc-v0.1.0")


class Changelog(unittest.TestCase):
    def test_secao_da_versao(self):
        text = "# Changelog\n\n## [Unreleased]\n\n## [0.4.0] - 2026-11-15\n- x\n\n## [0.3.9]\n"
        self.assertTrue(versao.changelog_has(text, "v0.4.0"))
        self.assertTrue(versao.changelog_has(text, "0.3.9"))
        self.assertFalse(versao.changelog_has(text, "v0.4.1"))
        with self.assertRaises(versao.VersaoError):
            versao.changelog_has(text, "v0.4")

    def test_nucleo_tem_secao_da_versao_atual(self):
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
            self.assertTrue(versao.changelog_has(f.read(), VERSION))


if __name__ == "__main__":
    unittest.main()
