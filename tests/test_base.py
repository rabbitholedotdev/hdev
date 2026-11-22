"""Base do diff por unidade (ADR 0008): o commit-turno não esconde do juiz o trabalho já commitado da peça."""
import calendar
import json
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, clean_env, hdev, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import base as basemod  # noqa: E402

FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "fake_judge.py")
PLAN = ("# Plano — inf-006-banco\n\nSpec: docs/specs/INF-006-banco.md\n\n## Critério de pronto\n"
        "- CRITERIO_X: teste de /saude no gestor\n")
BACKLOG = "| ID | Item | Status |\n|---|---|---|\n| INF-004 | publicar | {s4} |\n| INF-006 | banco | {s6} |\n"
TURNO = "Base directory for this skill: /srv/hdev/areas/x/.claude/skills/hdev"


def epoch(hhmm):
    return calendar.timegm(time.strptime("2026-11-15 %s" % hhmm, "%Y-%m-%d %H:%M"))


def git_at(d, hhmm, *args):
    stamp = "@%d +0000" % epoch(hhmm)
    env = clean_env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
                    GIT_COMMITTER_EMAIL="t@example.invalid", GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)
    r = subprocess.run(["git", "-C", d, *args], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def commit(d, hhmm, msg):
    git_at(d, hhmm, "add", "-A")
    git_at(d, hhmm, "commit", "-q", "--no-verify", "-m", msg)
    return git_at(d, hhmm, "rev-parse", "HEAD")


def touch(d, rel, hhmm):
    os.utime(os.path.join(d, rel), (epoch(hhmm), epoch(hhmm)))


def unit_repo(d, spec_committed=False):
    """Simula a peça INF-006 com o commit-turno: fecha o INF-004, depois turnos commitam pedaços da peça.

    Devolve (sha que fechou o INF-004, sha do turno que levou parte do teste)."""
    git_at(d, "10:00", "init", "-q")
    roles = {"executor": {"cli": "claude", "model": "claude-opus-5-5"},
             "judge": {"cli": "codex", "model": "gpt-5.5", "command": [sys.executable, FAKE, "pede-criterio"]}}
    write(os.path.join(d, ".hdev", "config.json"), json.dumps({"roles": roles, "judge": {"timeout": 30}}))
    write(os.path.join(d, ".gitignore"), ".hdev/runs/\n.hdev/state/\n")
    write(os.path.join(d, "work", "backlog.md"), BACKLOG.format(s4="a-fazer", s6="a-fazer"))
    write(os.path.join(d, "gestor", "teste", "app.test.mjs"), "// esqueleto\n")
    commit(d, "10:00", "inicial")
    write(os.path.join(d, "work", "backlog.md"), BACKLOG.format(s4="feito", s6="a-fazer"))
    fechou = commit(d, "11:00", TURNO)
    # 11:10: a peça começa (spec e plano); 11:30: turno commita o teste do /saude (commit-turno, só rastreados)
    write(os.path.join(d, "docs", "specs", "INF-006-banco.md"), "# INF-006\n")
    write(os.path.join(d, "docs", "plan-inf-006-banco.md"), PLAN)
    touch(d, "docs/specs/INF-006-banco.md", "11:10")
    touch(d, "docs/plan-inf-006-banco.md", "11:10")
    write(os.path.join(d, "gestor", "teste", "app.test.mjs"), "// esqueleto\ntest('SAUDE_NO_TURNO')\n")
    git_at(d, "11:30", "add", "gestor/teste/app.test.mjs")
    if spec_committed:
        git_at(d, "11:30", "commit", "-q", "--no-verify", "-m", TURNO)
        git_at(d, "11:40", "add", "docs")
        git_at(d, "11:40", "commit", "-q", "--no-verify", "-m", TURNO)
    else:
        git_at(d, "11:30", "commit", "-q", "--no-verify", "-m", TURNO)
    turno = git_at(d, "11:40", "rev-parse", "HEAD~1" if spec_committed else "HEAD")
    # ainda na árvore: mudança rastreada e arquivo novo
    write(os.path.join(d, "gestor", "teste", "app.test.mjs"),
          "// esqueleto\ntest('SAUDE_NO_TURNO')\ntest('MIGRACAO_NA_ARVORE')\n")
    write(os.path.join(d, "gestor", "lib", "banco.mjs"), "export const NOVO_NAO_RASTREADO = 1\n")
    return fechou, turno


class Unidade(unittest.TestCase):
    def test_id_da_unidade_pelo_plano(self):
        self.assertEqual(basemod.unit_id("docs/plan-inf-006-sqlite-migracoes.md"), "INF-006")
        self.assertEqual(basemod.unit_id("docs/plan-f2-05-revisor-isolado.md"), "F2-05")
        self.assertIsNone(basemod.unit_id("docs/plan-x.md"))
        self.assertIsNone(basemod.unit_id("docs/plan-subtrair.md"))
        self.assertEqual(basemod.unit_key("docs/plan-x.md"), "plan-x")
        self.assertEqual(basemod.unit_id("work/subtrair/plan.md"), "subtrair")
        self.assertEqual(basemod.unit_id("work/inf-006-foo/plan.md"), "inf-006-foo")
        self.assertEqual(basemod.unit_key("work/inf-006-foo/plan.md"), "inf-006-foo")
        self.assertIsNone(basemod.unit_id("work/backlog.md"))

    def test_cita_spec_em_work(self):
        text = "Spec: work/subtrair/spec.md\nReview: work/subtrair/review.md\n"
        docs = basemod.unit_docs("/tmp/nao-existe", "work/subtrair/plan.md", text)
        self.assertIn("work/subtrair/spec.md", docs)
        self.assertIn("work/subtrair/review.md", docs)

    def test_irmao_em_work_entra_na_unidade(self):
        with TempDir() as d:
            write(os.path.join(d, "work", "peca", "spec.md"), "# s\n")
            docs = basemod.unit_docs(d, "work/peca/plan.md", "# Plano\n")
            self.assertIn("work/peca/spec.md", docs)

    def test_marcar_work_plan_grava_o_id_da_pasta(self):
        with TempDir() as d:
            git_at(d, "10:00", "init", "-q")
            write(os.path.join(d, "README.md"), "x\n")
            base = commit(d, "10:00", "inicial")
            write(os.path.join(d, "work", "inf-006-foo", "plan.md"), "# Plano — inf-006-foo\n")
            code, out = hdev("base", "--plan", "work/inf-006-foo/plan.md", "--root", d, "--marcar", base)
            self.assertEqual(code, 0, out)
            self.assertIn("inf-006-foo", out)
            saved = read_json(os.path.join(d, ".hdev", "state", "bases.json"))
            self.assertEqual(set(saved), {"inf-006-foo"})
            self.assertEqual(saved["inf-006-foo"]["base"], base)
            self.assertEqual(saved["inf-006-foo"]["plan"], "work/inf-006-foo/plan.md")

    def test_fechamento_so_conta_item_que_virou_feito(self):
        with TempDir() as d:
            fechou, turno = unit_repo(d)
            self.assertTrue(basemod.closes_item(d, fechou))
            self.assertFalse(basemod.closes_item(d, turno))

    def test_item_fechado_conta_em_work_backlog(self):
        with TempDir() as d:
            git_at(d, "10:00", "init", "-q")
            write(os.path.join(d, "work", "backlog.md"), BACKLOG.format(s4="a-fazer", s6="a-fazer"))
            commit(d, "10:00", "inicial")
            write(os.path.join(d, "work", "backlog.md"), BACKLOG.format(s4="feito", s6="a-fazer"))
            fechou = commit(d, "11:00", "fecha")
            write(os.path.join(d, "docs", "backlog.md"), BACKLOG.format(s4="a-fazer", s6="a-fazer"))
            commit(d, "11:10", "docs antigo")
            write(os.path.join(d, "docs", "backlog.md"), BACKLOG.format(s4="feito", s6="a-fazer"))
            docs = commit(d, "11:20", "docs nao conta")
            self.assertTrue(basemod.closes_item(d, fechou))
            self.assertFalse(basemod.closes_item(d, docs))
            self.assertEqual(basemod.closed_item_commit(d), fechou)


class JuizVeTudo(unittest.TestCase):
    def test_commit_turno_nao_esconde_o_trabalho_da_unidade(self):
        with TempDir() as d:
            fechou, _ = unit_repo(d)
            code, old = hdev("judge", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--base", "HEAD",
                             "--dry-run")
            self.assertEqual(code, 0, old)
            self.assertNotIn("+test('SAUDE_NO_TURNO')", old.split("=== DIFF", 1)[1])  # o falso negativo de antes
            code, out = hdev("judge", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--dry-run")
            self.assertEqual(code, 0, out)
            diff = out.split("=== DIFF", 1)[1]
            for marca in ("+test('SAUDE_NO_TURNO')", "+test('MIGRACAO_NA_ARVORE')", "NOVO_NAO_RASTREADO", "# INF-006"):
                self.assertIn(marca, diff)
            self.assertIn("=== BASE DO DIFF\n%s" % fechou[:12], out)
            self.assertIn("último item fechado", out)
            self.assertIn("(mais a árvore de trabalho", out)

    def test_spec_commitada_depois_do_codigo_usa_o_mtime(self):
        with TempDir() as d:
            fechou, _ = unit_repo(d, spec_committed=True)
            code, out = hdev("judge", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertIn("=== BASE DO DIFF\n%s" % fechou[:12], out)
            self.assertIn("+test('SAUDE_NO_TURNO')", out.split("=== DIFF", 1)[1])

    def test_primeiro_juiz_grava_a_base_e_turnos_seguintes_nao_movem(self):
        with TempDir() as d:
            fechou, _ = unit_repo(d)
            code, out = hdev("judge", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--json")
            self.assertEqual(code, 0, out)
            res = json.loads(out)
            self.assertEqual(res["base_sha"], fechou)
            self.assertEqual(res["unidade"], "INF-006")
            saved = read_json(os.path.join(d, ".hdev", "state", "bases.json"))
            self.assertEqual(saved["INF-006"]["base"], fechou)
            commit(d, "12:00", TURNO)  # o turno leva tudo, inclusive a spec
            code, out = hdev("judge", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--dry-run")
            self.assertIn("=== BASE DO DIFF\n%s — gravada" % fechou[:12], out)
            self.assertIn("MIGRACAO_NA_ARVORE", out.split("=== DIFF", 1)[1])

    def test_relatorio_mostra_a_base_usada(self):
        with TempDir() as d:
            fechou, _ = unit_repo(d)
            code, out = hdev("judge", "--plan", "docs/plan-inf-006-banco.md", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("base do diff: %s (deduzida: último item fechado" % fechou[:12], out)

    def test_base_explicita_vence_a_gravada(self):
        with TempDir() as d:
            fechou, turno = unit_repo(d)
            self.assertEqual(hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--marcar",
                                  fechou)[0], 0)
            code, out = hdev("judge", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--base", turno,
                             "--dry-run")
            self.assertIn("=== BASE DO DIFF\n%s — --base" % turno[:12], out)
            self.assertNotIn("+test('SAUDE_NO_TURNO')", out.split("=== DIFF", 1)[1])


class Comando(unittest.TestCase):
    def test_marcar_mostrar_e_force(self):
        with TempDir() as d:
            fechou, turno = unit_repo(d)
            code, out = hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--sha")
            self.assertEqual((code, out.strip()), (0, fechou))
            code, out = hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--marcar", turno)
            self.assertEqual(code, 0, out)
            code, out = hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--marcar", fechou)
            self.assertEqual(code, 1, out)
            self.assertIn("--force", out)
            code, out = hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--marcar", fechou,
                             "--force")
            self.assertEqual(code, 0, out)
            code, out = hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--json")
            info = json.loads(out)
            self.assertEqual((info["sha"], info["tipo"]), (fechou, "gravada"))

    def test_marcar_sem_ref_grava_a_deduzida(self):
        with TempDir() as d:
            fechou, _ = unit_repo(d)
            code, out = hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--marcar")
            self.assertEqual(code, 0, out)
            saved = read_json(os.path.join(d, ".hdev", "state", "bases.json"))["INF-006"]
            self.assertEqual(saved["base"], fechou)
            self.assertIn("deduzida", saved["origem"])

    def test_ref_inexistente_e_uso(self):
        with TempDir() as d:
            unit_repo(d)
            code, out = hdev("base", "--plan", "docs/plan-inf-006-banco.md", "--root", d, "--marcar", "nao-existe")
            self.assertEqual(code, 64, out)

    def test_sem_unidade_fica_no_head(self):
        with TempDir() as d:
            git_at(d, "10:00", "init", "-q")
            write(os.path.join(d, "docs", "plan-x.md"), PLAN)
            commit(d, "10:00", "base")
            info = basemod.resolve(d, "docs/plan-x.md", PLAN)
            self.assertIsNone(info["sha"])
            self.assertEqual(info["tipo"], "head")


if __name__ == "__main__":
    unittest.main()
