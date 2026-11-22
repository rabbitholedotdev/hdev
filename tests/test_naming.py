"""Checagem `names` (F2-10): repos git temporários."""
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev import naming  # noqa: E402


def repo(d, files=("README.md",), config=None):
    git(d, "init", "-q", "-b", "main")
    git(d, "config", "user.name", "t")
    git(d, "config", "user.email", "t@example.invalid")
    for f in files:
        write(os.path.join(d, f), "x\n")
    if config is not None:
        write(os.path.join(d, ".hdev", "config.json"), json.dumps(config))
    commit(d, "base")
    return head(d)


def commit(d, msg):
    git(d, "add", "-A")
    assert git(d, "commit", "-q", "-m", msg).returncode == 0
    return head(d)


def head(d):
    return git(d, "rev-parse", "HEAD").stdout.strip()


def names(d, base=None):
    return naming.check_names(d, base)


class Modes(unittest.TestCase):
    def test_sem_naming_nao_ascii_e_falha(self):
        with TempDir() as d:
            repo(d, config={})
            write(os.path.join(d, "ação.py"), "x")
            r = names(d)
            self.assertFalse(r.ok)
            self.assertIn("mode fail", r.detail)
            self.assertEqual(r.warnings, [])
            self.assertIn("ação.py: não-ASCII 'ç', 'ã'", r.failures[0])
            code, out = hdev("check", "--root", d)
            self.assertEqual(code, 1)
            self.assertIn("[FALHA] names:", out)

    def test_fail_com_nao_ascii(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "fail"}})
            write(os.path.join(d, "ação.py"), "x")
            code, out = hdev("check", "--root", d)
            self.assertEqual(code, 1)
            self.assertIn("[FALHA] names:", out)
            self.assertIn("  falha: ação.py: não-ASCII", out)
            r = names(d)
            self.assertFalse(r.ok)
            self.assertEqual(r.warnings, [])
            self.assertIn("1 não-ASCII", r.detail)

    def test_fail_so_palavra_passa(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "fail"}})
            write(os.path.join(d, "tela.py"), "x")
            write(os.path.join(d, "migracao.py"), "x")
            r = names(d)
            self.assertTrue(r.ok)
            self.assertEqual(sorted(r.warnings), ["migracao.py: 'migracao' parece português (sufixo)",
                                                  "tela.py: 'tela' parece português (lista)"])

    def test_off(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "off"}})
            write(os.path.join(d, "ação.py"), "x")
            r = names(d, base="nao-existe")
            self.assertTrue(r.ok)
            self.assertEqual(r.detail, "desligado")

    def test_naming_malformada_e_modo_desconhecido(self):
        with TempDir() as d:
            repo(d, config={"naming": "x"})
            self.assertIn("; config naming inválida, usando padrão", names(d).detail)
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "Fail"}})
            r = names(d)
            self.assertIn("mode warn", r.detail)
            self.assertIn("modo desconhecido 'Fail', usando warn", r.detail)
        with TempDir() as d:
            repo(d, config=[])
            self.assertIn("config inválida, usando padrão", names(d).detail)


class BaseChoice(unittest.TestCase):
    def test_bases_json_fechamento_e_head(self):
        with TempDir() as d:
            b0 = repo(d)
            write(os.path.join(d, "a.py"), "x")
            b1 = commit(d, "A-1 feito: a; juiz pass")
            r = names(d)
            self.assertIn("base %s (fechamento)" % b1[:7], r.detail)
            write(os.path.join(d, "b.py"), "x")
            b2 = commit(d, "turno")
            write(os.path.join(d, ".hdev", "state", "bases.json"), json.dumps(
                {"U-1": {"base": b0, "ts": "2026-01-01T00:00:00Z"}}))
            # bases.json está a 3 commits; fechamento a 1: vence o fechamento
            self.assertIn("(fechamento)", names(d).detail)
            write(os.path.join(d, ".hdev", "state", "bases.json"), json.dumps(
                {"U-1": {"base": b2, "ts": "2026-01-01T00:00:00Z"}}))
            self.assertIn("base %s (bases.json U-1)" % b2[:7], names(d).detail)

    def test_empate_ts_e_id_e_ordem(self):
        with TempDir() as d:
            b0 = repo(d)
            write(os.path.join(d, ".hdev", "state", "bases.json"), json.dumps({
                "B-1": {"base": b0, "ts": "2026-01-01T00:00:00Z"},
                "A-1": {"base": b0, "ts": "2026-01-01T00:00:00Z"},
                "C-1": {"base": b0, "ts": "2026-02-01T00:00:00Z"}}))
            self.assertIn("(bases.json C-1)", names(d).detail)
            write(os.path.join(d, ".hdev", "state", "bases.json"), json.dumps({
                "B-1": {"base": b0}, "A-1": {"base": b0}}))
            self.assertIn("(bases.json A-1)", names(d).detail)

    def test_entrada_ruim_descartada_e_recuo_head(self):
        with TempDir() as d:
            b0 = repo(d)
            write(os.path.join(d, ".hdev", "state", "bases.json"), json.dumps({
                "X-1": {"plan": "p"}, "X-2": {"base": "0" * 40}, "X-3": "lixo"}))
            r = names(d)
            self.assertIn("base %s (HEAD)" % b0[:7], r.detail)
            self.assertIn("3 candidatos de base descartados", r.detail)

    def test_nao_ancestral_nao_conta(self):
        with TempDir() as d:
            b0 = repo(d)
            git(d, "checkout", "-q", "-b", "other")
            write(os.path.join(d, "o.py"), "x")
            other = commit(d, "o")
            git(d, "checkout", "-q", "main")
            write(os.path.join(d, ".hdev", "state", "bases.json"), json.dumps({"O-1": {"base": other}}))
            r = names(d)
            self.assertIn("(HEAD)", r.detail)
            self.assertNotIn("descartados", r.detail)

    def test_bases_json_ilegivel(self):
        with TempDir() as d:
            repo(d)
            write(os.path.join(d, ".hdev", "state", "bases.json"), "{")
            self.assertIn("bases.json inválido, ignorado", names(d).detail)

    def test_base_invalida(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "warn"}})
            r = names(d, base="xyz")
            self.assertFalse(r.ok)
            self.assertEqual(r.detail, "base inválida 'xyz'")
            code, out = hdev("check", "--root", d, "--base", "xyz")
            self.assertEqual(code, 1)
            self.assertIn("[FALHA] names: base inválida 'xyz'", out)
            code, out = hdev("check", "--root", d, "--base", "xyz", "--json")
            data = {x["check"]: x for x in json.loads(out)}
            self.assertFalse(data["names"]["ok"])
            self.assertNotIn("warnings", data["names"])

    def test_base_explicita_nao_ancestral(self):
        with TempDir() as d:
            repo(d)
            git(d, "checkout", "-q", "-b", "other")
            write(os.path.join(d, "o.py"), "x")
            other = commit(d, "o")
            git(d, "checkout", "-q", "main")
            r = names(d, base=other)
            self.assertIn("(--base)", r.detail)
            self.assertIn("base não é ancestral de HEAD", r.detail)


class Segments(unittest.TestCase):
    def test_rename_e_copia_valem_caminho_novo(self):
        with TempDir() as d:
            repo(d, files=["docs/a.txt", "docs/b.txt"])
            os.rename(os.path.join(d, "docs", "a.txt"), os.path.join(d, "docs", "tela.txt"))
            git(d, "add", "-A")
            r = names(d)
            self.assertEqual(r.warnings, ["docs/tela.txt: 'tela' parece português (lista)"])
            self.assertIn("1 segmentos novos", r.detail)

    def test_copia(self):
        with TempDir() as d:
            repo(d)
            body = "".join("linha %d\n" % i for i in range(40))
            write(os.path.join(d, "big.txt"), body)
            commit(d, "big")
            with open(os.path.join(d, "big.txt"), "a") as f:
                f.write("mais\n")
            write(os.path.join(d, "copia-ç.txt"), body)
            git(d, "add", "-A")
            r = names(d, base="HEAD")
            self.assertIn("copia-ç.txt", (r.failures + r.warnings)[0])

    def test_existente_na_base_nao_e_testado(self):
        with TempDir() as d:
            repo(d, files=["tela/x.py", "ação.py"])
            write(os.path.join(d, "tela", "fresh.py"), "x")
            write(os.path.join(d, "ação.py"), "mudou")
            r = names(d)
            self.assertEqual(r.warnings, [])
            self.assertIn("1 segmentos novos", r.detail)

    def test_allow_words_e_paths(self):
        with TempDir() as d:
            repo(d, config={"naming": {"allow_words": ["TELA"], "allow_paths": ["content/*"],
                                       "mode": "fail"}})
            write(os.path.join(d, "tela.py"), "x")
            write(os.path.join(d, "content", "ação", "y.py"), "x")
            r = names(d)
            self.assertTrue(r.ok)
            self.assertEqual(r.warnings, [])
            self.assertIn("2 calados por allow_paths", r.detail)
            self.assertIn("2 segmentos novos", r.detail)

    def test_tokens_camel_e_sufixo(self):
        with TempDir() as d:
            repo(d)
            write(os.path.join(d, "NovoArquivo.py"), "x")
            write(os.path.join(d, "sessao-sessao.py"), "x")
            write(os.path.join(d, "acao.py"), "x")
            write(os.path.join(d, "ok.py"), "x")
            r = names(d)
            self.assertIn("acao.py: 'acao' parece português (lista)", r.warnings)
            self.assertIn("NovoArquivo.py: 'novo' parece português (lista)", r.warnings)
            self.assertEqual(sum(1 for w in r.warnings if w.startswith("sessao-sessao.py")), 1)
            self.assertIn("4 avisos", r.detail)

    def test_byte_nao_utf8(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "fail"}})
            open(os.path.join(os.fsencode(d), b"a\xffb.txt"), "w").write("x")
            r = names(d)
            self.assertFalse(r.ok)
            self.assertEqual(r.failures, ["a\\xffb.txt: não-ASCII '\\xff'"])


class Extras(unittest.TestCase):
    def test_naming_sem_mode_e_fail_sem_nota(self):
        with TempDir() as d:
            repo(d, config={"naming": {"allow_words": ["x"]}})
            r = names(d)
            self.assertIn("mode fail", r.detail)
            self.assertNotIn(";", r.detail)

    def test_camel_case(self):
        with TempDir() as d:
            repo(d)
            write(os.path.join(d, "userTelaPage.py"), "x")
            self.assertEqual(names(d).warnings, ["userTelaPage.py: 'tela' parece português (lista)"])

    def test_gitignore_respeitado(self):
        with TempDir() as d:
            repo(d, files=[".gitignore"])
            write(os.path.join(d, ".gitignore"), "tela/\n")
            write(os.path.join(d, "tela", "x.py"), "x")
            self.assertEqual(names(d).warnings, [])

    def test_caminho_so_no_indice(self):
        with TempDir() as d:
            repo(d)
            write(os.path.join(d, "tela.py"), "x")
            git(d, "add", "tela.py")
            os.remove(os.path.join(d, "tela.py"))
            self.assertEqual(names(d).warnings, ["tela.py: 'tela' parece português (lista)"])

    def test_unidade_irremovivel(self):
        with TempDir() as d:
            repo(d, config={"naming": {"allow_words": [], "mode": "fail"}})
            write(os.path.join(d, "unidade", "x.py"), "x")
            self.assertEqual(names(d).warnings, [])

    def test_config_inteira_ilegivel(self):
        with TempDir() as d:
            repo(d)
            write(os.path.join(d, ".hdev", "config.json"), "{ruim")
            r = names(d)
            self.assertIn("mode fail", r.detail)
            self.assertIn("; config inválida, usando padrão", r.detail)

    def test_repo_sem_commit(self):
        with TempDir() as d:
            git(d, "init", "-q", "-b", "main")
            write(os.path.join(d, "ação.py"), "x")
            r = names(d)
            self.assertTrue(r.ok)
            self.assertRegex(r.detail, r"^erro do git \(.+\), não checado$")
            code, _ = hdev("check", "--root", d)
            self.assertNotIn("[FALHA] names", _)


class Branch(unittest.TestCase):
    def test_unidade_passa_e_tela_avisa(self):
        with TempDir() as d:
            repo(d)
            git(d, "checkout", "-q", "-b", "unidade/F2-10")
            self.assertEqual(names(d).warnings, [])
            git(d, "checkout", "-q", "-b", "unidade/tela")
            self.assertEqual(names(d).warnings, ["branch unidade/tela: 'tela' parece português (lista)"])

    def test_branch_nao_ascii_em_fail(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "fail"}})
            git(d, "checkout", "-q", "-b", "ação")
            r = names(d)
            self.assertFalse(r.ok)
            self.assertEqual(r.failures, ["branch ação: não-ASCII 'ç', 'ã'"])

    def test_detached(self):
        with TempDir() as d:
            h = repo(d)
            git(d, "checkout", "-q", "--detach", h)
            self.assertIn(", branch: detached", names(d).detail)


class Output(unittest.TestCase):
    def test_formato_e_json(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "warn"}})
            write(os.path.join(d, "zeta.py"), "x")
            write(os.path.join(d, "pasta", "ação.py"), "x")
            r = names(d)
            self.assertRegex(r.detail, r"^base [0-9a-f]{7} \(HEAD\), mode warn, 3 segmentos novos, 1 não-ASCII, "
                                       r"1 avisos$")
            self.assertEqual(r.warnings, ["pasta: 'pasta' parece português (lista)",
                                          "pasta/ação.py: não-ASCII 'ç', 'ã'"])
            code, out = hdev("check", "--root", d, "--json")
            data = {x["check"]: x for x in json.loads(out)}
            self.assertEqual(data["names"]["warnings"], r.warnings)
            self.assertNotIn("failures", data["names"])
            self.assertNotIn("warnings", data["agents"] if "agents" in data else {})

    def test_linhas_intercaladas_por_item(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "fail"}})
            write(os.path.join(d, "a-tela-ç.py"), "x")
            write(os.path.join(d, "b-ç.py"), "x")
            write(os.path.join(d, "c-tela.py"), "x")
            code, out = hdev("check", "--root", d)
            got = [l.strip() for l in out.splitlines() if l.startswith("  ")]
            self.assertEqual(got, [
                "falha: a-tela-ç.py: não-ASCII 'ç'", "aviso: a-tela-ç.py: 'tela' parece português (lista)",
                "falha: b-ç.py: não-ASCII 'ç'", "aviso: c-tela.py: 'tela' parece português (lista)"])

    def test_config_ausente_sem_nota(self):
        with TempDir() as d:
            repo(d)
            self.assertNotIn("config", names(d).detail)

    def test_result_as_dict_sem_listas_vazias(self):
        self.assertEqual(checkmod.Result("x", True, "d").as_dict(), {"check": "x", "ok": True, "detail": "d"})

    def test_cobertura_da_lista_no_padrao(self):
        with open(os.path.join(ROOT, "docs", "padroes", "naming.md"), encoding="utf-8") as f:
            text = f.read()
        missing = [w for w in naming.PT_WORDS if w not in text.replace("`", " ").replace(",", " ").split()]
        self.assertEqual(missing, [])


class Errors(unittest.TestCase):
    def test_nao_e_repo(self):
        with TempDir() as d:
            r = names(d)
            self.assertTrue(r.ok)
            self.assertEqual(r.detail, "não é repo git, não checado")
            self.assertEqual(r.warnings + r.failures, [])

    def test_erro_do_git_exit_zero_em_fail(self):
        with TempDir() as d:
            repo(d, config={"naming": {"mode": "fail"}})
            write(os.path.join(d, "ação.py"), "x")
            real = subprocess.run

            def fake(cmd, *a, **k):
                if "ls-files" in cmd:
                    return subprocess.CompletedProcess(cmd, 1, b"", b"boom")
                return real(cmd, *a, **k)
            with mock.patch.object(naming.subprocess, "run", side_effect=fake):
                r = names(d)
            self.assertTrue(r.ok)
            self.assertEqual(r.detail, "erro do git (ls-files), não checado")

    def test_git_ausente_nao_solta_excecao(self):
        with TempDir() as d:
            repo(d)
            with mock.patch.object(naming.subprocess, "run", side_effect=OSError("sem git")):
                self.assertTrue(names(d).ok)


if __name__ == "__main__":
    unittest.main()
