"""hdev app (F1-09, perfil ratoeira-app-creator): `new` monta pelo modelo, `check` confere o contrato do APPS.md."""
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, make_core, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import app as appmod  # noqa: E402
from hdev import check as checkmod  # noqa: E402
from hdev.init import init  # noqa: E402

PROFILE = os.path.join(ROOT, "profiles", "ratoeira-app-creator")


def ler(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def node_ok():
    node = shutil.which("node")
    if not node:
        return False
    v = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v").split(".")
    return (int(v[0]), int(v[1])) >= (22, 13)


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        self.areas = os.path.join(self._tmp.__enter__(), "areas")
        self.area = os.path.join(self.areas, "demo-area")
        os.makedirs(self.area)

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def novo(self, nome="painel", **kw):
        return appmod.new(nome, self.area, **kw)

    def falhas(self, pasta):
        return {r.name: r.detail for r in appmod.run_check(pasta) if not r.ok}

    def editar_manifesto(self, pasta, **campos):
        path = os.path.join(pasta, "ratoeira-app.json")
        m = read_json(path)
        m.update(campos)
        write(path, json.dumps(m))


class New(Base):
    def test_monta_pelo_modelo_e_check_passa(self):
        destino, porta, escritos = self.novo(titulo="Painel", descricao="Um painel de teste.")
        self.assertEqual(destino, os.path.join(os.path.realpath(self.area), "apps", "painel"))
        self.assertEqual(porta, 8800)
        for rel in ("README.md", "ratoeira-app.json", "servidor.mjs", "dev.mjs", "package.json", ".gitignore",
                    "lib/identidade.mjs", "lib/banco.mjs", "lib/regras.mjs", "migracoes/001-inicio.sql",
                    "agente/AGENTS.md", "tela/index.html", "teste/app.test.mjs"):
            self.assertIn(rel, escritos)
        m = read_json(os.path.join(destino, "ratoeira-app.json"))
        self.assertEqual((m["nome"], m["titulo"], m["porta"]), ("painel", "Painel", 8800))
        sobra = [p for p in escritos if "{{" in ler(os.path.join(destino, p))]
        self.assertEqual(sobra, [])
        self.assertEqual(self.falhas(destino), {})

    def test_porta_pula_as_usadas_em_outras_areas(self):
        write(os.path.join(self.areas, "trabalho", "apps", "x", "ratoeira-app.json"), '{"porta": 8800}')
        write(os.path.join(self.areas, "trabalho", "apps", "y", "ratoeira-app.json"), '{"porta": 8801}')
        self.assertEqual(self.novo()[1], 8802)

    def test_recusas(self):
        self.novo()
        with self.assertRaisesRegex(ValueError, "já existe"):
            self.novo()
        with self.assertRaisesRegex(ValueError, "minúsculas"):
            self.novo("Painel Novo")
        with self.assertRaisesRegex(ValueError, "porta 8800 já é"):
            self.novo("outro", porta=8800)
        for ruim in (-1, 0, 1023, 65536):
            with self.assertRaisesRegex(ValueError, "fora de 1024..65535"):
                self.novo("outro3", porta=ruim)
        self.assertFalse(os.path.exists(os.path.join(self.area, "apps", "outro3")))
        with self.assertRaisesRegex(ValueError, "aspas"):
            self.novo("outro2", titulo='O "melhor"')

    def test_cli(self):
        code, out = hdev("app", "new", "quadro", "--area", self.area, "--porta", "8900")
        self.assertEqual(code, 0, out)
        self.assertIn("porta 8900", out)
        code, out = hdev("app", "check", os.path.join(self.area, "apps", "quadro"))
        self.assertEqual(code, 0, out)
        code, out = hdev("app", "check", os.path.join(self.area, "nao-existe"))
        self.assertEqual(code, 1, out)

    @unittest.skipUnless(node_ok(), "sem node >= 22.13")
    def test_testes_do_modelo_rodam_verdes_no_node(self):
        destino = self.novo()[0]
        r = subprocess.run(["node", "--disable-warning=ExperimentalWarning", "--test", "teste/app.test.mjs"],
                           cwd=destino, capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("401", r.stdout)


class Check(Base):
    def setUp(self):
        super().setUp()
        self.app = self.novo()[0]

    def test_campo_desconhecido_falha(self):
        self.editar_manifesto(self.app, dominio="x.com")
        self.assertIn("campo desconhecido", self.falhas(self.app)["manifesto"])

    def test_nome_diferente_da_pasta_falha(self):
        self.editar_manifesto(self.app, nome="outro")
        self.assertIn("diferente da pasta", self.falhas(self.app)["manifesto"])

    def test_chave_com_cara_de_valor_falha(self):
        self.editar_manifesto(self.app, chaves=["sk-123abc"])
        self.assertIn("chaves", self.falhas(self.app)["manifesto"])

    def test_rotina_com_quando_e_intervalo_falha(self):
        self.editar_manifesto(self.app, rotinas=[{"nome": "a", "comando": "true", "quando": "daily", "intervalo": "1h"}])
        self.assertIn("rotina", self.falhas(self.app)["manifesto"])

    def test_icone_grande_falha(self):
        write(os.path.join(self.app, "icone.svg"), "x" * (257 * 1024))
        self.editar_manifesto(self.app, icone="icone.svg")
        self.assertIn("icone", self.falhas(self.app)["manifesto"])

    def test_porta_repetida_em_outra_area_falha(self):
        write(os.path.join(self.areas, "trabalho", "apps", "x", "ratoeira-app.json"), '{"porta": 8800}')
        self.assertIn("trabalho", self.falhas(self.app)["porta"])

    def test_esqueleto_incompleto_falha(self):
        os.remove(os.path.join(self.app, "agente", "AGENTS.md"))
        self.assertIn("agente", self.falhas(self.app)["esqueleto"])

    def test_migracao_que_nao_comeca_em_001_falha(self):
        os.rename(os.path.join(self.app, "migracoes", "001-inicio.sql"), os.path.join(self.app, "migracoes", "002-a.sql"))
        self.assertIn("001", self.falhas(self.app)["esqueleto"])

    def test_sem_teste_falha(self):
        shutil.rmtree(os.path.join(self.app, "teste"))
        self.assertIn("testes", self.falhas(self.app))

    def test_env_na_pasta_falha_mas_exemplo_e_dados_nao(self):
        write(os.path.join(self.app, ".env.exemplo"), "A=\n")
        write(os.path.join(self.app, ".dados", "chaves.env"), "")
        self.assertNotIn("segredos", self.falhas(self.app))
        write(os.path.join(self.app, ".env"), "")
        self.assertIn(".env", self.falhas(self.app)["segredos"])

    def test_escuta_em_todas_as_interfaces_falha(self):
        write(os.path.join(self.app, "lib", "x.mjs"), "server.listen(1, '0.0.0.0')\n")
        self.assertIn("0.0.0.0", self.falhas(self.app)["escuta"])

    def test_pagina_sem_a_ponte_falha_parcial_e_publico_nao(self):
        write(os.path.join(self.app, "publico", "p.html"), "<!doctype html><p>link público</p>")
        write(os.path.join(self.app, "tela", "parcial.html"), "<div>pedaço</div>")
        write(os.path.join(self.app, "tela", "abra.html"), "<!doctype html><title>Abra pela Ratoeira · Painel</title>")
        self.assertNotIn("tela", self.falhas(self.app))
        write(os.path.join(self.app, "tela", "outra.html"), "<!doctype html><title>Outra · Painel</title>")
        self.assertIn("outra.html", self.falhas(self.app)["tela"])

    def test_json_quebrado_falha_sem_traceback(self):
        write(os.path.join(self.app, "ratoeira-app.json"), "{")
        f = self.falhas(self.app)
        self.assertIn("inválido", f["manifesto"])
        self.assertIn("porta", f)


class Perfil(unittest.TestCase):
    def test_init_com_o_perfil_liga_skill_e_check_passa(self):
        with TempDir() as tmp:
            d = os.path.join(tmp, "app")
            report = init(d, core=make_core(tmp), profile="ratoeira-app-creator")
            self.assertIn(os.path.join(".claude", "skills", "ratoeira-app-creator"), report["written"])
            skill = os.path.join(d, ".claude", "skills", "ratoeira-app-creator", "SKILL.md")
            self.assertTrue(os.path.isfile(skill))
            self.assertIn("@.harnessdev/profiles/ratoeira-app-creator/AGENTS.md", ler(os.path.join(d, "AGENTS.md")))
            self.assertIn("<!-- perfil:ratoeira-app-creator -->",
                          ler(os.path.join(d, ".harnessdev", "profiles", "ratoeira-app-creator", "AGENTS.md")))
            self.assertEqual(read_json(os.path.join(d, ".hdev", "config.json"))["profile"], "ratoeira-app-creator")
            bad = [(r.name, r.detail) for r in checkmod.run(d) if not r.ok]
            self.assertEqual(bad, [])
            self.assertIn("0 próprias (+8 do núcleo)", {r.name: r.detail for r in checkmod.run(d)}["skills"])

    def test_perfil_inexistente_recusa(self):
        with TempDir() as tmp:
            with self.assertRaisesRegex(ValueError, "não tem o perfil"):
                init(os.path.join(tmp, "app"), core=make_core(tmp), profile="worker-developer")
            with self.assertRaisesRegex(ValueError, "inválido"):
                init(os.path.join(tmp, "app2"), core=make_core(tmp), profile="../x")

    def test_padrao_continua_harness_developer(self):
        with TempDir() as tmp:
            d = os.path.join(tmp, "app")
            init(d, core=make_core(tmp))
            self.assertFalse(os.path.lexists(os.path.join(d, ".claude", "skills", "ratoeira-app-creator")))
            self.assertIn("@.harnessdev/profiles/harness-developer/AGENTS.md", ler(os.path.join(d, "AGENTS.md")))

    def test_perfil_cabe_nos_tetos(self):
        desc = checkmod.skill_description(ler(os.path.join(PROFILE, "skill", "SKILL.md")))
        self.assertTrue(desc and len(desc) <= checkmod.DESCRIPTION_MAX)
        self.assertEqual(os.listdir(os.path.join(PROFILE, "skill")), ["SKILL.md"])  # 1 skill própria, no máximo
        for rel in ("criterios.md", "README.md", "AGENTS.md", "progress.md", os.path.join("modelo", "ratoeira-app.json")):
            self.assertTrue(os.path.isfile(os.path.join(PROFILE, rel)), rel)

    def test_modelo_sem_dado_de_cliente_nem_segredo(self):
        proibidos = re.compile(r"example-client|personal-domain\.invalid|user@example|op://\w|sk-[a-z0-9]|akia", re.I)
        for raiz, _, nomes in os.walk(PROFILE):
            for n in nomes:
                self.assertIsNone(proibidos.search(ler(os.path.join(raiz, n))), n)


class SoSkill(unittest.TestCase):
    """`hdev init --skill-only` (F1-10): área da Ratoeira ganha só .harnessdev, lock e a skill do perfil."""

    def setUp(self):
        self._tmp = TempDir()
        self.tmp = self._tmp.__enter__()
        self.core = make_core(self.tmp)
        self.area = os.path.join(self.tmp, "area")
        write(os.path.join(self.area, "AGENTS.md"), "# Área\nregra da área\n" + "x\n" * 90)
        write(os.path.join(self.area, ".claude", "skills", "copy", "SKILL.md"), "---\nname: copy\ndescription: x\n---\n")
        write(os.path.join(self.area, ".claude", "settings.local.json"), "{}")
        git(self.area, "init", "-q")

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def test_so_link_lock_e_skill_e_nada_da_area_muda(self):
        antes = ler(os.path.join(self.area, "AGENTS.md"))
        code, out = hdev("init", self.area, "--core", self.core, "--profile", "ratoeira-app-creator", "--skill-only")
        self.assertEqual(code, 0, out)
        self.assertEqual(ler(os.path.join(self.area, "AGENTS.md")), antes)
        for rel in ("CLAUDE.md", os.path.join(".claude", "settings.json"), ".hdev", "tests", "docs",
                    os.path.join(".claude", "skills", "planejar"),
                    os.path.join(".claude", "skills", "revisar-spec"),
                    os.path.join(".claude", "skills", "revisar-diff"), ".gitignore"):
            self.assertFalse(os.path.lexists(os.path.join(self.area, rel)), rel)
        self.assertFalse(os.path.exists(os.path.join(self.area, ".git", "hooks", "pre-commit")))
        skill = os.path.join(self.area, ".claude", "skills", "ratoeira-app-creator")
        self.assertTrue(os.path.islink(skill))
        self.assertTrue(os.path.isfile(os.path.join(skill, "SKILL.md")))
        self.assertTrue(os.path.islink(os.path.join(self.area, ".harnessdev")))
        lock = read_json(os.path.join(self.area, ".harnessdev.lock"))
        self.assertEqual((lock["version"], lock["modo"]), ("v9.9.9", "skill"))

    def test_check_em_modo_area(self):
        init(self.area, core=self.core, profile="ratoeira-app-creator", skill_only=True)
        res = {r.name: r for r in checkmod.run(self.area)}
        self.assertEqual(set(res), {"harnessdev", "core_skills"})
        self.assertTrue(all(r.ok for r in res.values()), [(r.name, r.detail) for r in res.values()])
        code, out = hdev("check", "--root", self.area)
        self.assertEqual(code, 0, out)
        self.assertIn("repo de área", out)
        # link da skill quebrado: falha
        os.remove(os.path.join(self.area, ".claude", "skills", "ratoeira-app-creator"))
        os.symlink(os.path.join("..", "..", ".harnessdev", "profiles", "nao-existe"),
                   os.path.join(self.area, ".claude", "skills", "ratoeira-app-creator"))
        self.assertFalse({r.name: r for r in checkmod.run(self.area)}["core_skills"].ok)

    def test_app_completo_sem_config_nao_vira_modo_area(self):
        app = os.path.join(self.tmp, "app")
        init(app, core=self.core, profile="ratoeira-app-creator")
        os.remove(os.path.join(app, ".hdev", "config.json"))
        res = {r.name: r for r in checkmod.run(app)}
        self.assertIn("config", res)
        self.assertFalse(res["config"].ok)

    def test_perfil_sem_skill_liga_so_a_skill_hdev(self):
        init(self.area, core=self.core, profile="harness-developer", skill_only=True)
        skills = os.path.join(self.area, ".claude", "skills")
        self.assertEqual(sorted(os.listdir(skills)), ["copy", "hdev"])
        self.assertTrue(os.path.isfile(os.path.join(skills, "hdev", "SKILL.md")))
        self.assertTrue(all(r.ok for r in checkmod.run(self.area)))

    def test_release_sem_skill_nenhuma_recusa_antes_de_escrever(self):
        shutil.rmtree(os.path.join(self.core, ".claude", "skills", "hdev"))
        git(self.core, "commit", "-q", "-a", "--no-verify", "-m", "sem hdev")
        git(self.core, "tag", "-f", "v9.9.9")
        with self.assertRaisesRegex(ValueError, "não tem skill"):
            init(self.area, core=self.core, profile="harness-developer", skill_only=True)
        self.assertFalse(os.path.lexists(os.path.join(self.area, ".harnessdev")))
        self.assertFalse(os.path.lexists(os.path.join(self.area, ".harnessdev.lock")))

    def test_app_check_roda_pela_release_na_area(self):
        init(self.area, core=self.core, profile="ratoeira-app-creator", skill_only=True)
        bin_ = os.path.join(self.area, ".harnessdev", "bin", "hdev")
        r = subprocess.run([sys.executable, bin_, "app", "new", "quadro", "--area", self.area], capture_output=True,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, bin_, "app", "check", os.path.join(self.area, "apps", "quadro")],
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
