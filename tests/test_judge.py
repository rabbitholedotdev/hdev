"""hdev judge com CLI de juiz falsa (stub): pacote, veredito, segundo provedor, scan de segredo."""
import json
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, fake_aws_key, git, hdev, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import config as cfgmod  # noqa: E402
from hdev import judge as judgemod  # noqa: E402
from hdev import stop as stopmod  # noqa: E402

FAKE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "fake_judge.py")
PLAN = "# Plano\n\n## Critério de pronto\n- CRITERIO_X: a.py existe\n\n## Passos\n1. criar a.py\n"


def repo(d, judge_mode, fallback_mode=None, timeout=30):
    roles = {
        "executor": {"cli": "claude", "model": "claude-opus-5-5"},
        "judge": {"cli": "codex", "model": "gpt-5.5", "command": [sys.executable, FAKE, judge_mode]},
    }
    if fallback_mode:
        roles["judge_fallback"] = {"cli": "agy", "model": "gemini-3-pro",
                                   "command": [sys.executable, FAKE, fallback_mode]}
    git(d, "init", "-q")
    write(os.path.join(d, ".hdev", "config.json"), json.dumps({"roles": roles, "judge": {"timeout": timeout}}))
    write(os.path.join(d, ".gitignore"), ".hdev/runs/\n.hdev/cache/\n.hdev/state/\n")
    write(os.path.join(d, "docs", "plan-x.md"), PLAN)
    git(d, "add", "-A")
    git(d, "commit", "-q", "-m", "base")
    write(os.path.join(d, "a.py"), "print('oi')\n")


class Judge(unittest.TestCase):
    def test_plano_em_work_usa_o_id_da_pasta(self):
        for uid in ("subtrair", "inf-006-foo"):
            with TempDir() as d:
                repo(d, "pass")
                plan = "work/%s/plan.md" % uid
                write(os.path.join(d, plan), PLAN)
                code, out = hdev("judge", "--plan", plan, "--root", d, "--json")
                self.assertEqual(code, 0, out)
                data = json.loads(out)
                self.assertEqual(data["unidade"], uid)
                self.assertEqual(data["plan"], plan)

    def test_pass_e_registro(self):
        with TempDir() as d:
            repo(d, "pede-criterio")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 0, out)
            runs = os.listdir(os.path.join(d, ".hdev", "runs"))
            self.assertIn("metrics.jsonl", runs)
            with open(os.path.join(d, ".hdev", "runs", "metrics.jsonl"), encoding="utf-8") as f:
                line = json.loads(f.readline())
            self.assertEqual(line["tokens"], 1234)
            self.assertEqual(line["verdict"], "pass")

    def test_fail_nao_vai_ao_segundo_provedor(self):
        with TempDir() as d:
            repo(d, "fail", "pass")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 1, out)
            self.assertEqual(json.loads(out)["calls"], 1)

    def test_unsure_tenta_segundo_provedor(self):
        with TempDir() as d:
            repo(d, "unsure", "pass")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 0, out)
            self.assertEqual(json.loads(out)["calls"], 2)

    def test_cli_sem_json_vira_sem_veredito(self):
        with TempDir() as d:
            repo(d, "lixo", "lixo")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, out)
            self.assertIn("liberado sem juiz", out)

    def test_quota_entra_na_fila_idempotente_login_grava_parei(self):
        with TempDir() as d:
            repo(d, "lixo")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 2, out)
            data = json.loads(out)
            self.assertEqual(data["retomada"]["acao"], "retry")
            self.assertIn("docs/plan-x.md", data["retomada"]["proximo"])
            hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(len(stopmod.pending_retries(d)), 1)
            code, resume = hdev("resume", "--root", d)
            self.assertEqual(code, 0, resume)
            self.assertEqual(json.loads(resume)["acao"], "retry")
            self.assertEqual(json.loads(hdev("resume", "--root", d)[1])["acao"], "nada")
        with TempDir() as d:
            repo(d, "login")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 2, out)
            data = json.loads(out)
            self.assertEqual(data["retomada"]["acao"], "parei")
            self.assertTrue(os.path.isfile(stopmod.parei_path(d)))
            rec = stopmod.read_parei(d)
            self.assertEqual(rec["kind"], "login")
            self.assertIn("hdev judge", rec["proximo"])

    def test_timeout_vira_sem_veredito(self):
        with TempDir() as d:
            repo(d, "dorme", timeout=1)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, out)

    def test_cli_ausente_vira_sem_veredito(self):
        with TempDir() as d:
            repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["roles"]["judge"]["command"] = ["hdev-cli-que-nao-existe-xyz", "-"]
            write(cfg_path, json.dumps(cfg))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, out)

    def test_segredo_no_diff_nao_chama_o_juiz(self):
        with TempDir() as d:
            repo(d, "pass")
            write(os.path.join(d, "b.py"), "k = '%s'\n" % fake_aws_key())
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 3, out)
            self.assertNotIn(fake_aws_key(), out)
            self.assertFalse(os.path.exists(os.path.join(d, ".hdev", "runs")))

    def test_arquivo_sensivel_vai_so_pelo_nome(self):
        with TempDir() as d:
            repo(d, "pass")
            write(os.path.join(d, ".env"), "SEGREDO_LITERAL_DE_TESTE=1\n")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertIn(".env", out)
            self.assertNotIn("SEGREDO_LITERAL_DE_TESTE", out)

    def test_juiz_do_mesmo_provedor_e_recusado(self):
        with TempDir() as d:
            repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["roles"]["judge"]["model"] = "claude-sonnet-5-5"
            cfg["roles"]["judge"]["cli"] = "agy"
            write(cfg_path, json.dumps(cfg))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, out)


class Pacote(unittest.TestCase):
    """F1-06: intervalo de commits, seções ARQUIVOS e HDEV CHECK, comando de teste do juiz, corte por arquivo."""

    def _two_commits(self, d):
        repo(d, "pass")
        self._commit_a_then_b(d)

    def _commit_a_then_b(self, d):
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "a")
        write(os.path.join(d, "b.py"), "print('b')\n")
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "b")
        write(os.path.join(d, "solto.txt"), "NAO_RASTREADO\n")

    def test_head_julga_so_o_intervalo(self):
        with TempDir() as d:
            self._two_commits(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "HEAD~2",
                             "--head", "HEAD~1", "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertIn("a.py", out)
            self.assertNotIn("b.py", out)
            self.assertNotIn("NAO_RASTREADO", out)
            self.assertIn("=== ARQUIVOS", out)
            commit = out.split("=== COMMIT", 1)[1].split("===", 1)[0]
            self.assertIn(" a\n", commit)  # assunto do commit do intervalo
            self.assertIn("branches que contêm HEAD~1:", commit)
            self.assertNotIn("(nenhuma)", commit)

    def test_head_roda_testes_num_clone_do_commit(self):
        with TempDir() as d:
            repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["gates"] = {"full": [sys.executable, "-c",
                                     "import os; print('TEM_B' if os.path.exists('b.py') else 'SEM_B')"]}
            write(cfg_path, json.dumps(cfg))
            self._commit_a_then_b(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "HEAD~2",
                             "--head", "HEAD~1", "--run-tests", "--dry-run")
            self.assertEqual(code, 0, out)
            tests_section = out.split("=== TESTES", 1)[1].split("=== HDEV CHECK", 1)[0]
            self.assertIn("SEM_B", tests_section)
            self.assertIn("clone limpo do commit", tests_section)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "HEAD~2",
                             "--head", "HEAD", "--run-tests", "--dry-run")
            self.assertIn("TEM_B", out.split("=== TESTES", 1)[1].split("=== HDEV CHECK", 1)[0])

    def test_tokens_do_pacote_ecoado_nao_contam(self):
        with TempDir() as d:
            repo(d, "eco")
            write(os.path.join(d, "a.py"), "# tokens used: 9,999\n")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 0, out)
            self.assertIsNone(json.loads(out)["attempts"][0]["tokens"])

    def test_head_sem_base_e_uso(self):
        with TempDir() as d:
            self._two_commits(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--head", "HEAD")
            self.assertEqual(code, 64, out)

    def test_run_tests_usa_gates_full_e_traz_check(self):
        with TempDir() as d:
            repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["gates"] = {
                "fast": [sys.executable, "-c", "print('COMANDO_RAPIDO')"],
                "full": [sys.executable, "-c", "print('COMANDO_DO_JUIZ')"],
            }
            write(cfg_path, json.dumps(cfg))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--run-tests", "--dry-run")
            self.assertEqual(code, 0, out)
            tests_section = out.split("=== TESTES", 1)[1].split("=== HDEV CHECK", 1)[0]
            self.assertIn("COMANDO_DO_JUIZ", tests_section)
            self.assertNotIn("COMANDO_RAPIDO", tests_section)
            self.assertIn("=== HDEV CHECK", out)
            self.assertIn("agents:", out)

    def test_tests_command_antigo_e_erro(self):
        with TempDir() as d:
            repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["gates"] = {"full": [sys.executable, "-c", "print('NAO_RODA')"]}
            cfg["judge"]["tests_command"] = [sys.executable, "-c", "print('ANTIGO')"]
            write(cfg_path, json.dumps(cfg))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--run-tests", "--dry-run")
            self.assertEqual(code, 64, out)
            self.assertIn("chave antiga", out)
            self.assertNotIn("ANTIGO", out)
            self.assertNotIn("NAO_RODA", out)

    def test_diff_grande_corta_por_arquivo_e_lista_omitidos(self):
        diff = "diff --git a/um.py b/um.py\n+%s\ndiff --git a/dois.py b/dois.py\n+%s\n" % ("x" * 50, "y" * 500)
        fitted = judgemod.fit_diff(diff, 200)
        self.assertIn("um.py", fitted)
        self.assertNotIn("y" * 500, fitted)
        self.assertIn("omitidos por tamanho (1): dois.py", fitted)

    def test_intervalo_inexistente_e_uso_sem_chamar_o_juiz(self):
        # revisão Codex, rodada 11: falha do git diff não vira "diff vazio" com pass
        with TempDir() as d:
            self._two_commits(d)
            for base, head in (("ref-que-nao-existe", "HEAD"), ("HEAD~1", "ref-que-nao-existe")):
                code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", base, "--head", head)
                self.assertEqual(code, 64, out)
                self.assertIn("ref-que-nao-existe", out)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "ref-que-nao-existe")
            self.assertEqual(code, 64, out)
            self.assertFalse(os.path.exists(os.path.join(d, ".hdev", "runs")))

    def test_check_entra_sem_run_tests_e_com_tests_log(self):
        # revisão Codex, rodada 11: o pacote traz o check sempre
        with TempDir() as d:
            self._two_commits(d)
            log = os.path.join(d, "log.txt")
            write(log, "Ran 3 tests\nOK\n")
            for extra in ((), ("--tests-log", log), ("--base", "HEAD", "--head", "HEAD")):
                code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--dry-run", *extra)
                self.assertEqual(code, 0, out)
                self.assertIn("\n=== HDEV CHECK\n", out, extra)
                self.assertIn("agents:", out.split("=== HDEV CHECK", 1)[1], extra)

    def test_muitos_arquivos_cabem_no_teto_sem_corte_bruto(self):
        # revisão Codex, rodada 11 e judge-20261115T003907053023Z: 6.000 arquivos; a lista de omitidos
        # entra no orçamento e vai inteira (pelo nome, ou agrupada por pasta se os nomes não cabem)
        for name, agrupada in (("f%04d.py", False), ("pasta/subpasta/modulo_com_nome_comprido_%04d.py", True)):
            diff = "".join("diff --git a/{0} b/{0}\n+{1}\n".format(name % i, "q" * 100) for i in range(6000))
            pkg = judgemod.build_package("crit", diff, "ok", stat="muitos", check_out="exit 0")
            self.assertLessEqual(len(pkg), judgemod.MAX_PACKAGE, name)
            self.assertNotIn("pacote truncado", pkg)
            self.assertNotIn(" e mais ", pkg)
            kept = pkg.count("diff --git ")
            last = pkg.rstrip().rsplit("\n", 1)[-1]
            if agrupada:
                m = re.fullmatch(r"\[omitidos por tamanho \((\d+)\), agrupados por pasta: (.*)\]", last)
                self.assertIsNotNone(m, last[:200])
                total = sum(int(x) for x in re.findall(r"/ \((\d+)\)", m.group(2)))
                self.assertEqual(total, 6000 - kept)
            else:
                m = re.fullmatch(r"\[omitidos por tamanho \((\d+)\): (.*)\]", last)
                self.assertIsNotNone(m, last[:200])
                self.assertEqual(len(m.group(2).split(", ")), 6000 - kept)  # todos os nomes, nenhum some
            self.assertEqual(int(m.group(1)), 6000 - kept)

    def test_corte_final_em_fronteira_de_bloco_e_lista_inteira(self):
        # judge-20261115T003907053023Z: cabeçalho enorme não pode empurrar o corte para dentro do diff
        blocks = ["diff --git a/m%02d.py b/m%02d.py\n+%s\n" % (i, i, chr(97 + i % 26) * 30000) for i in range(12)]
        tests = "\n".join("linha de teste %06d" % i for i in range(20000)) + "\nRan 9 tests\nOK"
        evidence = "\n".join("evidencia %06d" % i for i in range(8000))
        pkg = judgemod.build_package("crit", "".join(blocks), tests, stat="12 arquivos", check_out="exit 0",
                                     evidence_out=evidence)
        self.assertLessEqual(len(pkg), judgemod.MAX_PACKAGE)
        self.assertNotIn("pacote truncado", pkg)
        diff_part = pkg.split("\n=== DIFF\n", 1)[1]
        last = diff_part.rstrip().rsplit("\n", 1)[-1]
        m = re.fullmatch(r"\[omitidos por tamanho \((\d+)\): (.*)\]", last)
        self.assertIsNotNone(m, last[:200])
        listed = m.group(2).split(", ")
        kept = [b for b in blocks if b.rstrip("\n") in diff_part]
        self.assertGreater(len(kept), 0)
        self.assertEqual(len(kept) + len(listed), 12)  # todo bloco: inteiro no pacote ou nomeado na lista
        self.assertEqual(diff_part.count("diff --git "), len(kept))  # nenhum bloco partido
        # o cabeçalho foi aparado em fronteira de linha, com aviso, e os testes guardam o resumo do fim
        tests_part = pkg.split("=== TESTES\n", 1)[1].split("\n\n=== ", 1)[0]
        self.assertIn("seção cortada em fronteira de linha", tests_part)
        self.assertTrue(tests_part.endswith("Ran 9 tests\nOK"))
        for line in tests_part.splitlines()[1:-2]:
            self.assertRegex(line, r"^linha de teste \d{6}$")

    def test_lista_de_omitidos_nao_e_cortada_pelo_orcamento(self):
        diff = "".join("diff --git a/d/arquivo_%03d.py b/d/arquivo_%03d.py\n+%s\n" % (i, i, "w" * 2000)
                       for i in range(300))
        fitted = judgemod.fit_diff(diff, 20000)
        self.assertLessEqual(len(fitted), 20000)
        last = fitted.rsplit("\n", 1)[-1]
        self.assertTrue(last.startswith("[omitidos por tamanho (") and last.endswith("]"), last[:120])
        kept = fitted.count("diff --git ")
        self.assertIn("(%d)" % (300 - kept), last)
        for i in range(300):
            name = "d/arquivo_%03d.py" % i
            self.assertTrue(("b/%s\n" % name) in fitted or name in last, name)

    def test_check_do_commit_julgado_sem_run_tests(self):
        # judge-20261115T003907053023Z: com --base/--head e sem --run-tests, HDEV CHECK vem do clone do commit
        with TempDir() as d:
            self._two_commits(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "HEAD~2",
                             "--head", "HEAD~1", "--dry-run")
            self.assertEqual(code, 0, out)
            check = out.split("\n=== HDEV CHECK\n", 1)[1].split("\n\n=== ", 1)[0]
            self.assertIn("clone limpo do commit", check)
            self.assertIn("agents:", check)
            self.assertIn("(sem log de testes)", out.split("=== TESTES", 1)[1].split("===", 1)[0])

    def test_pacote_nao_passa_do_teto(self):
        big = "diff --git a/g.py b/g.py\n+%s\n" % ("z" * (judgemod.MAX_PACKAGE * 2))
        pkg = judgemod.build_package("crit", big, "ok", stat="g.py | 1 +", check_out="exit 0")
        self.assertLessEqual(len(pkg), judgemod.MAX_PACKAGE + 100)
        self.assertIn("omitidos por tamanho (1): g.py", pkg)


    def test_pacote_inclui_evidence_da_peca(self):
        with TempDir() as d:
            repo(d, "pass")
            write(os.path.join(d, "docs", "plan-f1-areas-ratoeira.md"),
                  "# Plano F1-10\n\n## Critério de pronto\n- version e tag\n")
            write(os.path.join(d, "docs", "evidence", "codex-exec-ok.txt"), "NAO_ENTRA\n")
            write(os.path.join(d, "docs", "evidence", "f1-10-release.txt"), "HDEV_VERSION_020\n")
            git(d, "add", "-A")
            git(d, "commit", "-q", "-m", "evidence")
            code, out = hdev("judge", "--plan", "docs/plan-f1-areas-ratoeira.md", "--root", d,
                             "--base", "HEAD~1", "--head", "HEAD", "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertIn("=== EVIDÊNCIA\n", out)
            ev = out.split("=== EVIDÊNCIA", 1)[1].split("===", 1)[0]
            self.assertIn("HDEV_VERSION_020", ev)
            self.assertIn("docs/evidence/f1-10-release.txt", ev)
            self.assertNotIn("NAO_ENTRA", ev)
            self.assertNotIn("codex-exec-ok.txt", ev)

    def test_evidence_da_unidade_no_head_ignora_nao_rastreado(self):
        with TempDir() as d:
            repo(d, "pass")
            plan = "work/subtrair/plan.md"
            write(os.path.join(d, plan), PLAN)
            write(os.path.join(d, "work", "subtrair", "evidence", "x.md"), "PROVA_COMMITADA\n")
            write(os.path.join(d, "work", "subtrair", "evidence", "nota.txt"), "NAO_TXT\n")
            git(d, "add", "-A")
            git(d, "commit", "-q", "-m", "evidencia da unidade")
            write(os.path.join(d, "work", "subtrair", "evidence", "solto.md"), "PROVA_SOLTA\n")
            code, out = hdev("judge", "--plan", plan, "--root", d, "--base", "HEAD~1", "--head", "HEAD",
                             "--dry-run")
            self.assertEqual(code, 0, out)
            ev = out.split("=== EVIDÊNCIA", 1)[1].split("===", 1)[0]
            self.assertIn("work/subtrair/evidence/x.md", ev)
            self.assertIn("PROVA_COMMITADA", ev)
            self.assertNotIn("PROVA_SOLTA", ev)
            self.assertNotIn("NAO_TXT", ev)

    def test_diagnostico_sem_anexo_cita_a_pasta_da_unidade(self):
        _, tips = judgemod.diagnose({"attempts": []}, {}, [])
        text = " ".join(tips)
        self.assertIn("work/<id>/evidence", text)
        self.assertIn("docs/evidence/", text)

    def test_evidence_vem_do_commit_julgado(self):
        with TempDir() as d:
            repo(d, "pass")
            write(os.path.join(d, "docs", "plan-f1-areas-ratoeira.md"),
                  "# Plano F1-10\n\n## Critério de pronto\n- x\n")
            write(os.path.join(d, "docs", "evidence", "f1-10-release.txt"), "NO_COMMIT\n")
            git(d, "add", "-A")
            git(d, "commit", "-q", "-m", "ev")
            write(os.path.join(d, "docs", "evidence", "f1-10-release.txt"), "NA_WORKTREE\n")
            code, out = hdev("judge", "--plan", "docs/plan-f1-areas-ratoeira.md", "--root", d,
                             "--base", "HEAD~1", "--head", "HEAD", "--dry-run")
            self.assertEqual(code, 0, out)
            ev = out.split("=== EVIDÊNCIA", 1)[1].split("===", 1)[0]
            self.assertIn("NO_COMMIT", ev)
            self.assertNotIn("NA_WORKTREE", ev)


def grok_repo(d, verdict):
    """Juiz grok (fixture de envelope), fallback codex, como na config do núcleo."""
    repo(d, "pass")
    cfg_path = os.path.join(d, ".hdev", "config.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg["roles"]["judge"] = {"cli": "grok", "model": "grok-4.7",
                             "command": [sys.executable, FAKE, "envelope-" + verdict, "--json-schema", "{schema}"]}
    cfg["roles"]["judge_fallback"] = {"cli": "codex", "model": "gpt-5.5", "command": [sys.executable, FAKE, "pass"]}
    write(cfg_path, json.dumps(cfg))



def _grande(d, n=14, linhas=1500):
    """n módulos novos de ~linhas*12 caracteres cada (diff bem acima de uma parte)."""
    for i in range(n):
        write(os.path.join(d, "src", "mod_%02d.py" % i), "".join("v%05d = %d\n" % (k, k) for k in range(linhas)))
    write(os.path.join(d, "docs", "nota.md"), "# nota\n" + "texto\n" * 50)


class Partes(unittest.TestCase):
    """F2-09 / v0.4.2 (ADR 0010): renames em lista, diff grande por partes, anexos validados, unsure acionável."""

    def test_renomeado_puro_vira_lista_sem_conteudo(self):
        with TempDir() as d:
            repo(d, "pass")
            write(os.path.join(d, "velho", "grande.py"), "".join("MARCA_CONTEUDO_%05d = 1\n" % k for k in range(3000)))
            git(d, "add", "-A")
            git(d, "commit", "-q", "-m", "antes")
            git(d, "mv", "velho", "novo")
            git(d, "commit", "-q", "-m", "move")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "HEAD~1", "--head", "HEAD",
                             "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertIn("=== RENOMEADOS SEM MUDANÇA\n", out)
            self.assertIn("R velho/grande.py -> novo/grande.py", out)
            self.assertNotIn("MARCA_CONTEUDO_", out)

    def test_diff_com_cabecalho_grande_parte_em_vez_de_esconder_o_meio(self):
        # ~80k em vários arquivos e suíte grande: cabe em várias partes, mas o atalho
        # de uma parte cola o diff depois do cabeçalho e o meio some para o juiz.
        blocks = ["diff --git a/hdev/f%02d.py b/hdev/f%02d.py\n+%s\n" % (i, i, "x" * 2800) for i in range(27)]
        diff = "".join(blocks)
        # suíte no tamanho do gates.full (a saída do juiz guarda no máximo 20k+20k)
        tests = "\n".join("linha %06d" % i for i in range(3500)) + "\nRan 3 tests\nOK\n"
        pkgs, meta = judgemod.build_packages("criterio", diff, tests, stat="27 arquivos", check_out="exit 0")
        self.assertGreater(meta["partes"], 1, meta)
        self.assertEqual(meta["omitidos"], [])
        self.assertEqual(meta["cortados"], [])
        blob = "\n".join(pkgs)
        for i in range(27):
            self.assertEqual(blob.count("b/hdev/f%02d.py\n" % i), 1)
        for pkg in pkgs:
            self.assertLessEqual(len(pkg), judgemod.MAX_PACKAGE)
            self.assertNotIn("omitidos por tamanho", pkg)

    def test_arquivo_cortado_pede_evidencia(self):
        _, tips = judgemod.diagnose({"attempts": []},
                                    {"cortados": [{"arquivo": "enorme.py"}], "evidencia": ["x.md"]}, [])
        text = " ".join(tips)
        self.assertIn("enorme.py", text)
        self.assertIn("work/<id>/evidence", text)

    def test_diff_grande_vira_partes_sem_corte_silencioso(self):
        diff = "".join("diff --git a/doc%02d.md b/doc%02d.md\n+%s\n" % (i, i, "d" * 40000) for i in range(4))
        diff += "".join("diff --git a/src/m%02d.py b/src/m%02d.py\n+%s\n" % (i, i, "c" * 40000) for i in range(6))
        pkgs, meta = judgemod.build_packages("crit", diff, "ok", stat="10 arquivos", check_out="exit 0")
        self.assertGreater(len(pkgs), 1)
        self.assertEqual(meta["partes"], len(pkgs))
        self.assertEqual(meta["omitidos"], [])
        for i, pkg in enumerate(pkgs, 1):
            self.assertLessEqual(len(pkg), judgemod.MAX_PACKAGE)
            self.assertIn("=== DIFF (parte %d/%d)\n" % (i, len(pkgs)), pkg)
            self.assertIn("=== MANIFESTO\n", pkg)
            self.assertNotIn("omitidos por tamanho", pkg)
        joined = "".join(p.split("=== DIFF (parte", 1)[1] for p in pkgs)
        for name in ["doc%02d.md" % i for i in range(4)] + ["src/m%02d.py" % i for i in range(6)]:
            self.assertEqual(joined.count("b/%s\n" % name), 1, name)  # cada arquivo inteiro em uma parte só
        first = pkgs[0].split("=== DIFF (parte", 1)[1]
        self.assertIn("src/m00.py", first)  # lógica primeiro
        self.assertNotIn("doc00.md\n+", first)

    def test_bloco_maior_que_a_parte_entra_cortado_e_registrado(self):
        diff = "diff --git a/enorme.py b/enorme.py\n" + "".join("+linha %06d\n" % k for k in range(30000))
        pkgs, meta = judgemod.build_packages("crit", diff, "ok")
        self.assertEqual([c["arquivo"] for c in meta["cortados"]], ["enorme.py"])
        self.assertIn("seção cortada em fronteira de linha", "".join(pkgs))
        for pkg in pkgs:
            self.assertLessEqual(len(pkg), judgemod.MAX_PACKAGE)

    def test_partes_chamam_o_juiz_uma_vez_cada_e_passam(self):
        with TempDir() as d:
            repo(d, "pass")
            _grande(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 0, out)
            res = json.loads(out)
            self.assertGreater(res["pacote"]["partes"], 1)
            self.assertEqual(res["calls"], res["pacote"]["partes"])
            self.assertEqual(sorted(a["parte"] for a in res["attempts"]), list(range(1, res["pacote"]["partes"] + 1)))

    def test_fail_numa_parte_reprova(self):
        with TempDir() as d:
            repo(d, "fail-parte-2")
            _grande(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 1, out)
            self.assertTrue(any(r.startswith("[parte 2/") for r in json.loads(out)["reasons"]))

    def test_passou_do_maximo_de_partes_nao_vira_pass(self):
        with TempDir() as d:
            repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["judge"]["max_parts"] = 1
            write(cfg_path, json.dumps(cfg))
            _grande(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 2, out)
            res = json.loads(out)
            self.assertEqual(res["verdict"], "unsure")
            self.assertTrue(res["pacote"]["omitidos"])
            self.assertTrue(any("max_parts" in t for t in res["diagnostico"]))

    def test_anexo_da_unidade_citado_ausente_fala_a_pasta(self):
        with TempDir() as d:
            repo(d, "pass")
            plan = "work/subtrair/plan.md"
            write(os.path.join(d, plan), PLAN + "\nProva em `work/subtrair/evidence/x.md`.\n")
            code, out = hdev("judge", "--plan", plan, "--root", d)
            self.assertEqual(code, 64, out)
            self.assertIn("work/subtrair/evidence/x.md", out)
            self.assertIn("não existe", out)
            self.assertIn("work/<id>/evidence", out)
            self.assertFalse(os.path.exists(os.path.join(d, ".hdev", "runs")))

    def test_anexo_citado_que_nao_existe_ou_nao_casa_falha_cedo(self):
        for nome, existe, trecho in (("docs/evidence/x-saida.md", False, "não existe"),
                                     ("docs/evidence/hunks-motor.md", True, "o juiz não o veria")):
            with TempDir() as d:
                repo(d, "pass")
                write(os.path.join(d, "docs", "plan-x.md"), PLAN + "\nProva em `%s`.\n" % nome)
                if existe:
                    write(os.path.join(d, nome), "saida\n")
                code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
                self.assertEqual(code, 64, out)
                self.assertIn(trecho, out)
                self.assertFalse(os.path.exists(os.path.join(d, ".hdev", "runs")))

    def test_anexo_com_o_id_da_unidade_entra(self):
        with TempDir() as d:
            repo(d, "pass")
            write(os.path.join(d, "docs", "plan-c9-01-fonte-unica.md"), PLAN)
            write(os.path.join(d, "docs", "evidence", "c9-01-hunks.md"), "PROVA_PELO_ID\n")
            code, out = hdev("judge", "--plan", "docs/plan-c9-01-fonte-unica.md", "--root", d, "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertIn("PROVA_PELO_ID", out.split("=== EVIDÊNCIA", 1)[1])

    def test_unsure_repetido_vira_diagnostico_e_nao_rejulga_igual(self):
        with TempDir() as d:
            repo(d, "unsure")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 2, out)
            first = json.loads(out)
            self.assertEqual(first["unsure_seguidos"], 1)
            self.assertTrue(first["diagnostico"])
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 64, out)
            self.assertIn("pacote idêntico", out)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--rejulgar")
            self.assertEqual(code, 2, out)
            self.assertIn("diagnóstico:", out)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--rejulgar", "--json")
            self.assertEqual(json.loads(out)["unsure_seguidos"], 3)
            self.assertTrue(any("unsure seguidos" in t for t in json.loads(out)["diagnostico"]))


class Grok(unittest.TestCase):
    def test_veredito_no_envelope_json(self):
        with TempDir() as d:
            grok_repo(d, "pass")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 0, out)
            result = json.loads(out)
            self.assertEqual(result["calls"], 1)
            self.assertEqual(result["attempts"][0]["provider"], "xai")
            self.assertEqual(result["reasons"], ["envelope: pass"])

    def test_fail_do_grok_nao_vai_ao_codex(self):
        with TempDir() as d:
            grok_repo(d, "fail")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 1, out)
            self.assertEqual(json.loads(out)["calls"], 1)

    def test_unsure_do_grok_cai_no_codex(self):
        with TempDir() as d:
            grok_repo(d, "unsure")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 0, out)
            self.assertEqual([a["cli"] for a in json.loads(out)["attempts"]], ["grok", "codex"])

    def test_comando_padrao_do_grok(self):
        cmd = cfgmod.role_command({"cli": "grok", "model": "grok-4.7"}, "/x/pacote.txt")
        self.assertEqual(cmd[:5], ["grok", "--prompt-file", "/x/pacote.txt", "--model", "grok-4.7"])
        self.assertNotIn("-p", cmd)  # `-p/--single` exige valor na CLI real (revisão Codex, rodada 6)
        self.assertIn("json", cmd[cmd.index("--output-format") + 1])
        schema = json.loads(cmd[cmd.index("--json-schema") + 1])
        self.assertEqual(schema["properties"]["verdict"]["enum"], ["pass", "fail", "unsure"])
        self.assertTrue(cfgmod.uses_prompt_file({"cli": "grok"}))
        self.assertFalse(cfgmod.uses_prompt_file({"cli": "codex"}))

    def test_pacote_vai_por_prompt_file_e_some_depois(self):
        with TempDir() as d:
            grok_repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["roles"]["judge"]["command"] = [sys.executable, FAKE, "grok-arquivo", "--prompt-file",
                                                "{prompt_file}", "--model", "{model}"]
            write(cfg_path, json.dumps(cfg))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 0, out)
            self.assertEqual([a["cli"] for a in json.loads(out)["attempts"]], ["grok"])
            leftovers = [n for n in os.listdir(os.path.join(d, ".hdev", "state")) if n.startswith("judge-package")]
            self.assertEqual(leftovers, [])

    def test_grok_com_p_vazio_falha_e_cai_no_codex(self):
        with TempDir() as d:
            grok_repo(d, "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["roles"]["judge"]["command"] = [sys.executable, FAKE, "grok-arquivo", "-p", "--model", "{model}"]
            write(cfg_path, json.dumps(cfg))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual([a["cli"] for a in json.loads(out)["attempts"]], ["grok", "codex"])

    def test_consultivo_ate_20_rotulos(self):
        with TempDir() as d:
            grok_repo(d, "pass")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertIn("consultivo (0/20", out)
            for i in range(20):
                label = {"plan": "docs/plan-x.md", "run": ".hdev/runs/judge-%02d.json" % i,
                         "judge_verdict": "pass", "expected": "pass", "by": "operator", "note": ""}
                write(os.path.join(d, "evals", "judge-labels", "caso-%02d.json" % i), json.dumps(label))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            result = json.loads(out)
            self.assertFalse(result["advisory"])
            self.assertEqual(result["labels"], 20)

    def test_rotulo_invalido_ou_repetido_nao_conta(self):
        with TempDir() as d:
            folder = os.path.join(d, "evals", "judge-labels")
            for i in range(20):
                write(os.path.join(folder, "lixo-%02d.json" % i), "{}" if i % 2 else "texto")
            same = {"plan": "p", "run": "r", "judge_verdict": "pass", "expected": "fail", "by": "operator"}
            write(os.path.join(folder, "a.json"), json.dumps(same))
            write(os.path.join(folder, "b.json"), json.dumps(same))
            write(os.path.join(folder, "c.json"), json.dumps(dict(same, expected="talvez")))
            self.assertEqual(judgemod.count_labels(d), 1)


class Robustez(unittest.TestCase):
    """Achados da revisão Codex (rodada 5): exit ≠ 0 e papel inválido."""

    def test_exit_nao_zero_descarta_pass_e_vai_ao_fallback(self):
        with TempDir() as d:
            repo(d, "pass-exit1", "fail")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            result = json.loads(out)
            self.assertEqual(code, 1, out)
            self.assertEqual(result["calls"], 2)
            self.assertIn("descartado", result["attempts"][0]["status"])
            self.assertNotIn("verdict", result["attempts"][0])
            # F1-06: o fim do stderr fica no registro para diagnóstico, com segredo redigido
            self.assertIn("STDERR_DIAGNOSTICO", result["attempts"][0]["stderr_tail"])
            self.assertNotIn(fake_aws_key(), out)
            runs = os.path.join(d, ".hdev", "runs")
            for name in os.listdir(runs):
                with open(os.path.join(runs, name), encoding="utf-8") as f:
                    self.assertNotIn(fake_aws_key(), f.read())

    def test_stderr_redigido_inteiro_antes_do_corte(self):
        # revisão Codex, rodada 13: segredo longo que atravessa o corte não deixa sufixo no registro
        body = ("Zq9Ab7" * 800)  # 4.800 caracteres, montado em tempo de execução
        stderr = "erro\nto" + "ken = \"" + body + "\"\nfim\n"
        done = subprocess.CompletedProcess([], 1, stdout="", stderr=stderr)
        role = {"cli": "codex", "model": "gpt-5.5", "command": ["juiz-falso"]}
        with TempDir() as d, mock.patch.object(judgemod.subprocess, "run", return_value=done):
            attempt = judgemod.call_judge("judge", role, "pacote", 5, d)
        tail = attempt["stderr_tail"]
        self.assertLessEqual(len(tail), 800)
        self.assertNotIn(body[-40:], tail)
        self.assertIn("fim", tail)

    def test_exit_nao_zero_sem_fallback_fica_sem_veredito(self):
        with TempDir() as d:
            repo(d, "pass-exit1")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, out)

    def test_papel_com_modelo_desconhecido_nao_e_chamado(self):
        with TempDir() as d:
            repo(d, "pass", "pass")
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["roles"]["judge"]["model"] = "modelo-misterioso"
            write(cfg_path, json.dumps(cfg))
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            result = json.loads(out)
            self.assertEqual(code, 0, out)
            self.assertIn("provedor desconhecido", result["attempts"][0]["status"])
            self.assertNotIn("seconds", result["attempts"][0])
            self.assertEqual(result["calls"], 1)


class CheckBase(unittest.TestCase):
    def test_check_text_passa_base(self):
        done = subprocess.CompletedProcess([], 0, "ok\n", "")
        with TempDir() as d, mock.patch.object(judgemod.subprocess, "run", return_value=done) as run:
            judgemod.check_text(d, "abc1234")
            cmd = run.call_args[0][0]
            self.assertEqual(cmd[cmd.index("--base") + 1], "abc1234")
            judgemod.check_text(d)
            self.assertNotIn("--base", run.call_args[0][0])


class Parse(unittest.TestCase):
    def test_envelope_com_json_em_texto(self):
        inner = json.dumps({"verdict": "fail", "reasons": ["x"]})
        out = json.dumps({"type": "result", "result": inner}) + "\n"
        self.assertEqual(judgemod.parse_verdict(out)["verdict"], "fail")

    def test_envelope_aninhado_em_lista(self):
        out = json.dumps({"messages": [{"content": json.dumps({"verdict": "pass"})}]})
        self.assertEqual(judgemod.parse_verdict(out)["verdict"], "pass")

    def test_ultimo_json_vence_e_normaliza(self):
        out = 'eco {"verdict": "pass"} ... final {"verdict": "não sei", "reasons": "falta teste"}'
        v = judgemod.parse_verdict(out)
        self.assertEqual(v["verdict"], "unsure")
        self.assertEqual(v["reasons"], ["falta teste"])

    def test_sem_json(self):
        self.assertIsNone(judgemod.parse_verdict("nada aqui {quebrado"))

    def test_criterio_do_plano(self):
        self.assertIn("CRITERIO_X", judgemod.criterion_from_plan(PLAN))
        self.assertNotIn("criar a.py", judgemod.criterion_from_plan(PLAN))


WRAP = (
    "import sys\n"
    "import runpy\n"
    "open(sys.argv[1], 'a', encoding='utf-8').write('1\\n')\n"
    "script = sys.argv[2]\n"
    "sys.argv = [script] + sys.argv[3:]\n"
    "runpy.run_path(script, run_name='__main__')\n"
)


def arm_counter(d):
    """Troca o falso por um contador + o mesmo falso. Devolve o arquivo de contagem.

    Os dois ficam em `.hdev/runs/` (gitignored no repo de teste) para não entrarem no diff."""
    runs = os.path.join(d, ".hdev", "runs")
    os.makedirs(runs, exist_ok=True)
    counter = os.path.join(runs, "calls.txt")
    wrap = os.path.join(runs, "count_judge.py")
    write(wrap, WRAP)
    cfg_path = os.path.join(d, ".hdev", "config.json")
    cfg = read_json(cfg_path)
    for role in (cfg.get("roles") or {}).values():
        cmd = role.get("command") if isinstance(role, dict) else None
        if isinstance(cmd, list) and FAKE in cmd:
            role["command"] = [cmd[0], wrap, counter] + cmd[1:]
    write(cfg_path, json.dumps(cfg))
    return counter


def ncalls(counter):
    if not os.path.isfile(counter):
        return 0
    with open(counter, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def cache_files(d):
    folder = os.path.join(d, ".hdev", "cache", "judge")
    if not os.path.isdir(folder):
        return []
    return [n for n in os.listdir(folder) if n.endswith(".json")]


class Cache(unittest.TestCase):
    """Segunda corrida igual reusa o veredito. Erro e unsure não entram."""

    def test_hit_chama_o_falso_uma_vez_e_diz_que_veio_do_cache(self):
        with TempDir() as d:
            repo(d, "pass")
            counter = arm_counter(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertNotIn("cache:", out)
            self.assertIn("consultivo (0/20", out)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("cache: veredito reutilizado; o provedor não foi chamado", out)
            self.assertIn("veredito: pass (0 chamada(s), 0s)", out)
            self.assertIn("consultivo (0/20", out)
            self.assertEqual(ncalls(counter), 1)
            self.assertEqual(len(cache_files(d)), 1)
            metrics = os.path.join(d, ".hdev", "runs", "metrics.jsonl")
            with open(metrics, encoding="utf-8") as f:
                self.assertEqual(len(f.read().strip().splitlines()), 1)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            data = json.loads(out)
            self.assertTrue(data["cache"])
            self.assertEqual(data["verdict"], "pass")
            self.assertEqual(data["calls"], 0)
            self.assertEqual(ncalls(counter), 1)

    def test_no_cache_chama_de_novo(self):
        with TempDir() as d:
            repo(d, "pass")
            counter = arm_counter(d)
            self.assertEqual(hdev("judge", "--plan", "docs/plan-x.md", "--root", d)[0], 0)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--no-cache")
            self.assertEqual(code, 0, out)
            self.assertNotIn("cache: veredito reutilizado", out)
            self.assertIn("1 chamada", out)
            self.assertEqual(ncalls(counter), 2)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("cache: veredito reutilizado", out)
            self.assertEqual(ncalls(counter), 2)

    def test_log_so_muda_tempo_e_tmp_e_a_chave_fica(self):
        # --run-tests: "Ran N tests in 52.382s" e /tmp/hdev-judge-<id> mudavam o package_sha
        import hashlib

        from hdev.gates.judge import cache as cachemod

        diff = "diff --git a/a.py b/a.py\n+x\n"
        check = "exit 0\n[ok] agents\n"

        def packed(log):
            pkgs, _meta = judgemod.build_packages("crit", diff, log, stat="1 arquivo", check_out=check)
            pkg = pkgs[0]
            sha = hashlib.sha256(pkg.encode("utf-8")).hexdigest()
            key, payload = cachemod.cache_key(
                "a" * 40, "b" * 40, "c" * 64, "xai", "grok-4.7", "1:abc", "run", sha, cli="grok",
                fallback_cli="codex", fallback_provider="openai", fallback_model="gpt-6.1-sol")
            return key, pkg, payload["package_sha"]

        lento = (
            "test_passa (tests.test_a.T.test_passa) ... ok\n"
            "Ran 413 tests in 52.382s\n\nOK\n"
            "File \"/tmp/hdev-judge-abc123/arvore/tests/test_a.py\", line 4\n"
            "File \"/private/tmp/hdev-test-zzzzzz/x.txt\", line 1\n"
        )
        rapido = (
            "test_passa (tests.test_a.T.test_passa) ... ok\n"
            "Ran 413 tests in 49.512s\n\nOK\n"
            "File \"/tmp/hdev-judge-qwerty/arvore/tests/test_a.py\", line 4\n"
            "File \"/var/folders/ab/cdefghij/T/hdev-test-yyyyyy/x.txt\", line 1\n"
        )
        falha = (
            "test_passa (tests.test_a.T.test_passa) ... ok\n"
            "FAIL: test_quebra (tests.test_a.T.test_quebra)\n"
            "AssertionError: 1 != 2\n"
            "Ran 413 tests in 50.000s\n\nFAILED (failures=1)\n"
            "File \"/tmp/hdev-judge-other99/arvore/tests/test_a.py\", line 9\n"
        )
        key_a, pkg_a, sha_a = packed(lento)
        key_b, pkg_b, sha_b = packed(rapido)
        key_c, pkg_c, _sha_c = packed(falha)
        self.assertEqual(key_a, key_b)
        self.assertEqual(sha_a, sha_b)
        self.assertEqual(pkg_a, pkg_b)
        self.assertIn("Ran 413 tests", pkg_a)
        self.assertIn("\nOK\n", pkg_a)
        self.assertIn("test_passa", pkg_a)
        self.assertNotIn("52.382", pkg_a)
        self.assertNotIn("49.512", pkg_a)
        self.assertNotIn("abc123", pkg_a)
        self.assertNotIn("qwerty", pkg_a)
        self.assertNotIn("zzzzzz", pkg_a)
        self.assertNotEqual(key_c, key_a)
        self.assertIn("test_quebra", pkg_c)
        self.assertIn("FAILED (failures=1)", pkg_c)
        self.assertNotIn("other99", pkg_c)

    def test_cada_parte_da_chave_erra_o_cache(self):
        from hdev.gates.judge import cache as cachemod
        base = dict(base_sha="a" * 40, head_sha="b" * 40, plan_sha="c" * 64, provider="xai",
                    model="grok-4.7", prompt_version="1:abc", run_tests="off", package_sha="d" * 64,
                    cli="grok", fallback_cli="codex", fallback_provider="openai",
                    fallback_model="gpt-6.1-sol")
        key, _payload = cachemod.cache_key(**base)
        changes = {
            "base_sha": "e" * 40,
            "head_sha": "f" * 40,
            "plan_sha": "1" * 64,
            "provider": "openai",
            "model": "grok-4",
            "prompt_version": "2:abc",
            "run_tests": "run",
            "package_sha": "2" * 64,
            "cli": "agy",
            "fallback_cli": "agy",
            "fallback_provider": "google",
            "fallback_model": "gpt-5.5",
        }
        for field, value in changes.items():
            other = dict(base, **{field: value})
            got, _payload = cachemod.cache_key(**other)
            self.assertNotEqual(got, key, field)

    def test_miss_quando_plano_modelo_base_testes_ou_versao_mudam(self):
        from hdev.gates.judge import constants as judge_constants
        with TempDir() as d:
            repo(d, "pass")
            counter = arm_counter(d)
            self.assertEqual(hdev("judge", "--plan", "docs/plan-x.md", "--root", d)[0], 0)
            self.assertEqual(ncalls(counter), 1)
            plan = os.path.join(d, "docs", "plan-x.md")
            write(plan, PLAN + "\n- mais um item\n")
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertNotIn("cache: veredito reutilizado", out)
            self.assertEqual(ncalls(counter), 2)
            write(plan, PLAN)
            cfg_path = os.path.join(d, ".hdev", "config.json")
            cfg = read_json(cfg_path)
            cfg["roles"]["judge"]["model"] = "gpt-5.4"
            write(cfg_path, json.dumps(cfg))
            code, _out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 0, _out)
            self.assertEqual(ncalls(counter), 3)
            cfg = read_json(cfg_path)
            cfg["roles"]["judge"]["model"] = "gpt-5.5"
            cfg["gates"] = {"full": [sys.executable, "-c", "print('OK')"]}
            write(cfg_path, json.dumps(cfg))
            code, _out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--run-tests")
            self.assertEqual(code, 0, _out)
            self.assertEqual(ncalls(counter), 4)
            git(d, "add", "-A")
            git(d, "commit", "-q", "-m", "b")
            code, _out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "HEAD~1",
                              "--head", "HEAD")
            self.assertEqual(code, 0, _out)
            self.assertEqual(ncalls(counter), 5)
            code, _out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--base", "HEAD",
                              "--head", "HEAD")
            self.assertEqual(code, 0, _out)
            self.assertEqual(ncalls(counter), 6)
            primeiro = judgemod.judge(d, "docs/plan-x.md")
            self.assertEqual(primeiro["verdict"], "pass")
            self.assertFalse(primeiro.get("cache"))
            self.assertEqual(ncalls(counter), 7)
            with mock.patch.object(judge_constants, "PROMPT_VERSION", "2"):
                outro = judgemod.judge(d, "docs/plan-x.md")
            self.assertEqual(outro["verdict"], "pass")
            self.assertFalse(outro.get("cache"))
            self.assertEqual(ncalls(counter), 8)
            de_novo = judgemod.judge(d, "docs/plan-x.md")
            self.assertTrue(de_novo.get("cache"))
            self.assertEqual(ncalls(counter), 8)

    def test_erro_nao_entra_no_cache(self):
        with TempDir() as d:
            repo(d, "lixo")
            counter = arm_counter(d)
            code, _out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, _out)
            self.assertEqual(cache_files(d), [])
            self.assertEqual(ncalls(counter), 1)
            runs = os.path.join(d, ".hdev", "runs")
            for name in os.listdir(runs):
                if name.startswith("judge-"):
                    os.remove(os.path.join(runs, name))
            code, _out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, _out)
            self.assertEqual(ncalls(counter), 2)
            self.assertEqual(cache_files(d), [])

    def test_unsure_nao_entra_no_cache(self):
        with TempDir() as d:
            repo(d, "unsure")
            counter = arm_counter(d)
            code, out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d, "--json")
            self.assertEqual(code, 2, out)
            self.assertEqual(json.loads(out)["verdict"], "unsure")
            self.assertEqual(cache_files(d), [])
            runs = os.path.join(d, ".hdev", "runs")
            for name in os.listdir(runs):
                if name.startswith("judge-"):
                    os.remove(os.path.join(runs, name))
            code, _out = hdev("judge", "--plan", "docs/plan-x.md", "--root", d)
            self.assertEqual(code, 2, _out)
            self.assertEqual(ncalls(counter), 2)
            self.assertEqual(cache_files(d), [])

    def test_help_lista_as_flags_e_no_cache(self):
        code, out = hdev("judge", "--help")
        self.assertEqual(code, 0, out)
        for flag in ("--plan", "--root", "--base", "--head", "--tests-log", "--run-tests",
                     "--dry-run", "--rejulgar", "--json", "--no-cache"):
            self.assertIn(flag, out)


if __name__ == "__main__":
    unittest.main()
