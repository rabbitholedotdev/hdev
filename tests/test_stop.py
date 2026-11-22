"""PAREI, decisões e fila de retentativa. Sem rede."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import stop  # noqa: E402


class StopList(unittest.TestCase):
    def test_lista_fechada_e_negacao(self):
        self.assertEqual(stop.classify("o site pediu 2FA"), "2fa")
        self.assertEqual(stop.classify("not logged in"), "login")
        self.assertEqual(stop.classify("a próxima ação é git push"), "destructive")
        self.assertIsNone(stop.classify("escolher o nome do arquivo"))
        self.assertIsNone(stop.classify("não faça sudo; só o nome"))
        self.assertIsNone(stop.classify("sem git push neste repo"))

    def test_parei_so_na_lista(self):
        with TempDir() as d:
            self.assertIsNone(stop.write_parei(d, "dúvida de nome", "escolher"))
            self.assertFalse(os.path.exists(stop.parei_path(d)))
            line = stop.write_parei(d, "pediram 2FA", "repetir o login")
            self.assertTrue(line.startswith("PAREI:"))
            self.assertIn("próximo:", line)
            rec = stop.read_parei(d)
            self.assertEqual(rec["kind"], "2fa")
            self.assertTrue(stop.allows_stop(d, {}))
            stop.clear_parei(d)
            self.assertFalse(stop.allows_stop(d, {}))
            self.assertTrue(stop.allows_stop(d, {"stop_reason": "login do provedor"}))
            self.assertFalse(stop.allows_stop(d, {"stop_reason": "qual biblioteca"}))

    def test_decisao_curta_nao_repete(self):
        with TempDir() as d:
            stop.append_decision(d, "segue com o nome em inglês")
            stop.append_decision(d, "segue com o nome em inglês")
            with open(os.path.join(d, "docs", "decisions.md"), encoding="utf-8") as f:
                text = f.read()
            self.assertEqual(text.count("nome em inglês"), 1)
            self.assertIn("Append-only", text)

    def test_fila_idempotente_e_retomavel(self):
        with TempDir() as d:
            self.assertTrue(stop.enqueue_retry(d, "judge-rate-limit", "docs/plan-x.md", "hdev judge --plan docs/plan-x.md"))
            self.assertFalse(stop.enqueue_retry(d, "judge-rate-limit", "docs/plan-x.md", "hdev judge --plan docs/plan-x.md"))
            self.assertEqual(len(stop.pending_retries(d)), 1)
            got = stop.resume(d)
            self.assertEqual(got["acao"], "retry")
            self.assertIn("hdev judge", got["proximo"])
            again = stop.resume(d)
            self.assertEqual(again["acao"], "nada")
            self.assertTrue(stop.enqueue_retry(d, "judge-rate-limit", "docs/plan-x.md", "hdev judge --plan docs/plan-x.md"))
            self.assertEqual(len(stop.pending_retries(d)), 1)

    def test_cli_grava_ou_decide_e_resume_consome(self):
        with TempDir() as d:
            code, out = hdev("resume", "--root", d, "--reason", "pediram 2FA", "--next", "seguir o plano")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertTrue(data["parou"])
            self.assertIn("PAREI:", data["parei"])
            code, out = hdev("resume", "--root", d)
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertEqual(data["acao"], "parei")
            self.assertEqual(data["proximo"], "seguir o plano")
            self.assertFalse(os.path.exists(stop.parei_path(d)))
            code, out = hdev("resume", "--root", d, "--reason", "nome do arquivo", "--next", "usar inglês")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertFalse(data["parou"])
            with open(os.path.join(d, "docs", "decisions.md"), encoding="utf-8") as f:
                self.assertIn("nome do arquivo", f.read())
            code, out = hdev("resume", "--root", d, "--reason", "só o motivo")
            self.assertEqual(code, 1, out)

    def test_recorte_mapeia_hdev_e_hooks_senao_smoke(self):
        with TempDir() as d:
            write(os.path.join(d, "tests", "test_stop.py"), "")
            write(os.path.join(d, "tests", "test_hooks.py"), "")
            write(os.path.join(d, "tests", "test_smoke.py"), "")
            self.assertEqual(stop.affected_modules(d, ["hdev/stop.py", "docs/a.md"]), ["tests.test_stop"])
            self.assertEqual(stop.affected_modules(d, ["hooks/gate_tests.py"]), ["tests.test_hooks.GateTests"])
            self.assertEqual(stop.affected_modules(d, ["harness/hooks/pre_tool.py"]), ["tests.test_hooks.PreTool"])
            self.assertEqual(stop.affected_modules(d, ["hooks/_lib.py"]), ["tests.test_smoke"])
            self.assertEqual(stop.affected_modules(d, ["README.md"]), ["tests.test_smoke"])
            self.assertTrue(stop.is_suite_command(["python3", "-m", "unittest", "discover", "-s", "tests"]))
            self.assertFalse(stop.is_suite_command([sys.executable, "-c", "raise SystemExit(1)"]))

    def test_gate_esgotado_grava_parei_retomavel(self):
        with TempDir() as d:
            line = stop.write_exhausted(d, "gate_tests", "FALHOU_X")
            self.assertIn("PAREI: gate esgotado (gate_tests)", line)
            self.assertIn("próximo: FALHOU_X", line)
            self.assertTrue(stop.allows_stop(d, {}))
            got = stop.resume(d)
            self.assertEqual(got["acao"], "parei")
            self.assertIn("FALHOU_X", got["proximo"])
            self.assertFalse(os.path.exists(stop.parei_path(d)))


class Unidade(unittest.TestCase):
    def _git(self, d):
        git(d, "init", "-q")
        git(d, "config", "user.name", "t")
        git(d, "config", "user.email", "t@example.invalid")
        write(os.path.join(d, ".gitignore"), ".hdev/state/\n.hdev/runs/\n")
        write(os.path.join(d, "README.md"), "x\n")
        git(d, "add", "-A")
        git(d, "commit", "-q", "--no-verify", "-m", "inicial")
        return git(d, "rev-parse", "HEAD").stdout.strip()

    def test_marcar_abre_e_fechar_pass_fecha(self):
        with TempDir() as d:
            base = self._git(d)
            plan = "work/alfa/plan.md"
            write(os.path.join(d, plan), "# Plano — alfa\n\n## Passos\n1. escrever o teste\n")
            git(d, "add", "-A")
            git(d, "commit", "-q", "--no-verify", "-m", "plano")
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"base_branch": "branch-base"}))
            code, out = hdev("base", "--plan", plan, "--root", d, "--marcar", base)
            self.assertEqual(code, 0, out)
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "open")
            self.assertEqual(rec["id"], "alfa")
            self.assertEqual(rec["next"], "escrever o teste")
            self.assertEqual(rec["brief"], "work/alfa/brief.md")
            code, out = hdev("fechar", "--plan", plan, "--root", d, "--dry-run")
            self.assertEqual(code, 0, out)
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "open")
            code, out = hdev("fechar", "--plan", plan, "--root", d)
            self.assertEqual(code, 0, out)
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "closed")

    def test_plano_docs_abre_e_fechar_fecha(self):
        with TempDir() as d:
            base = self._git(d)
            plan = "docs/plan-inf-006-banco.md"
            write(os.path.join(d, plan), "# Plano — SQLite\n\n## Passos\n1. gravar a migração\n")
            git(d, "add", "-A")
            git(d, "commit", "-q", "--no-verify", "-m", "plano")
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"base_branch": "branch-base"}))
            code, out = hdev("base", "--plan", plan, "--root", d, "--marcar", base)
            self.assertEqual(code, 0, out)
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "open")
            self.assertEqual(rec["id"], "INF-006")
            self.assertEqual(rec["plan"], plan)
            self.assertEqual(rec["next"], "gravar a migração")
            code, out = hdev("fechar", "--plan", plan, "--root", d)
            self.assertEqual(code, 0, out)
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "closed")
            self.assertEqual(rec["id"], "INF-006")
            self.assertEqual(rec["plan"], plan)

    def test_standing_ok_publicar_nao_para_e_sem_ele_para(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "state", "unit.json"), json.dumps({
                "id": "alfa", "status": "open", "next": "publicar", "plan": "work/alfa/plan.md",
                "brief": "work/alfa/brief.md", "blocked_on": "", "parked": False,
            }))
            code, out = hdev("resume", "--root", d, "--reason", "vou publicar", "--next", "seguir")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertTrue(data["parou"])
            self.assertIn("PAREI:", data["parei"])
            self.assertTrue(os.path.isfile(os.path.join(d, ".hdev", "state", "parei")))
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"stop": {"standing_ok": ["publicar"]}}))
            os.remove(os.path.join(d, ".hdev", "state", "parei"))
            code, out = hdev("resume", "--root", d, "--reason", "vou publicar", "--next", "seguir")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertFalse(data["parou"])
            self.assertIn("READY-TO-PUBLISH:", data["ready"])
            self.assertIn("alfa", data["ready"])
            with open(os.path.join(d, ".hdev", "state", "ready-to-publish"), encoding="utf-8") as f:
                self.assertIn("READY-TO-PUBLISH: alfa |", f.read())
            self.assertFalse(os.path.exists(stop.parei_path(d)))
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "ready-to-publish")

    def test_blocked_on_pega_a_proxima_ou_deixa_a_linha(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "state", "unit.json"), json.dumps({
                "id": "alfa", "status": "open", "next": "esperar", "plan": "work/alfa/plan.md",
            }))
            write(os.path.join(d, "work", "backlog.md"),
                  "- [ ] work/alfa/plan.md esta\n- [ ] work/beta/plan.md outra\n- [x] work/gama/plan.md feita\n")
            code, out = hdev("resume", "--root", d, "--blocked-on", "merge da outra faixa", "--next", "retomar")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertFalse(data["parou"])
            self.assertIn("pegue a próxima unidade", data["proximo"])
            self.assertFalse(os.path.exists(stop.parei_path(d)))
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "blocked")
            self.assertEqual(rec["blocked_on"], "merge da outra faixa")
            write(os.path.join(d, "work", "backlog.md"), "- [x] work/beta/plan.md feita\n")
            code, out = hdev("resume", "--root", d, "--blocked-on", "merge da outra faixa", "--next", "retomar quando entrar")
            self.assertEqual(code, 0, out)
            data = json.loads(out)
            self.assertTrue(data["parou"])
            self.assertIn("espera merge da outra faixa", data["parei"])
            self.assertTrue(stop.allows_stop(d, {}))
            got = stop.resume(d)
            self.assertEqual(got["acao"], "parei")
            self.assertIn("retomar quando entrar", got["proximo"])
            rec = read_json(os.path.join(d, ".hdev", "state", "unit.json"))
            self.assertEqual(rec["status"], "open")


if __name__ == "__main__":
    unittest.main()
