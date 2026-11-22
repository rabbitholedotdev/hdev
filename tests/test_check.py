"""hdev check: o repo real passa e cada teto estourado falha."""
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, hdev, make_core, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev import config as cfgmod  # noqa: E402
from hdev.init import init  # noqa: E402


def results(root):
    return {r.name: r for r in checkmod.run(root)}


class RepoReal(unittest.TestCase):
    def test_repo_real_passa(self):
        code, out = hdev("check", "--root", ROOT)
        self.assertEqual(code, 0, out)

    def test_fallback_codex_usa_modelo_da_conta(self):
        cfg, err = cfgmod.load(ROOT)
        self.assertIsNone(err, err)
        role = (cfg.get("roles") or {}).get("judge_fallback") or {}
        self.assertEqual(role.get("cli"), "codex")
        self.assertEqual(role.get("model"), "gpt-6.1-sol")


class Tetos(unittest.TestCase):
    def setUp(self):
        self._tmp = TempDir()
        tmp = self._tmp.__enter__()
        self.d = os.path.join(tmp, "app")
        init(self.d, core=make_core(tmp))
        self.rel = os.path.join(self.d, ".harnessdev")  # release do núcleo de teste (descartável)

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    def assertFails(self, name, contains=None):
        r = results(self.d)[name]
        self.assertFalse(r.ok, r.detail)
        if contains:
            self.assertIn(contains, r.detail)

    def test_caps_acima_do_teto_falha(self):
        path = os.path.join(self.d, ".hdev", "config.json")
        cfg = read_json(path)
        cfg["caps"] = {"agents": 60, "hooks": 8, "skills": 5, "subagents": 2, "progress": 2000}
        write(path, json.dumps(cfg))
        self.assertFails("config", "caps.hooks")

    def test_app_recem_ligado_passa(self):
        bad = [(r.name, r.detail) for r in checkmod.run(self.d) if not r.ok]
        self.assertEqual(bad, [])

    def test_agents_81_linhas_falha(self):
        with open(os.path.join(self.d, "AGENTS.md"), "a", encoding="utf-8") as f:
            f.write("x\n" * 81)
        self.assertFails("agents", "linhas")

    def test_perfil_31_linhas_falha(self):
        path = os.path.join(self.d, "AGENTS.md")
        write(path, "# A\n<!-- perfil:harness-developer -->\n" + "- x\n" * 31 + "<!-- /perfil -->\n")
        self.assertFails("agents", "perfil")

    def test_claude_md_com_mais_coisa_falha(self):
        write(os.path.join(self.d, "CLAUDE.md"), "@AGENTS.md\nmais regra\n")
        self.assertFails("claude_md")

    def test_hook_a_mais_falha(self):
        path = os.path.join(self.d, ".claude", "settings.json")
        data = read_json(path)
        data["hooks"]["Stop"][0]["hooks"].append({"type": "command", "command": "python3 hooks/extra.py"})
        write(path, json.dumps(data))
        self.assertFails("hooks", "6 hooks")

    def test_hook_no_disco_fora_do_registro_falha(self):
        write(os.path.join(self.rel, "hooks", "extra.py"), "pass\n")
        self.assertFails("hooks", "extra.py")

    def test_hook_sem_teste_falha(self):
        os.remove(os.path.join(self.rel, "tests", "test_hooks.py"))
        self.assertFails("hooks", "sem teste")

    def test_hook_registrado_sem_arquivo_na_release_falha(self):
        os.remove(os.path.join(self.rel, "harness", "hooks", "stop_gate.py"))
        self.assertFails("hooks", "harness/hooks/stop_gate.py")

    def test_alias_ausente_falha(self):
        os.remove(os.path.join(self.rel, "hooks", "gate_tests.py"))
        self.assertFails("hooks", ".harnessdev/hooks/")

    def test_fase_com_seis_skills_falha(self):
        path = os.path.join(self.d, ".hdev", "config.json")
        cfg = read_json(path)
        cfg["skills"] = {"F1": ["a", "b", "c", "d", "e", "f"]}
        write(path, json.dumps(cfg))
        self.assertFails("skills", "6")

    def test_seis_no_disco_passa(self):
        for n in ("a", "b", "c", "d", "e", "f"):
            write(os.path.join(self.d, ".claude", "skills", n, "SKILL.md"), "---\nname: %s\ndescription: x\n---\n" % n)
        r = results(self.d)["skills"]
        self.assertTrue(r.ok, r.detail)
        self.assertIn("6 próprias", r.detail)
        self.assertIn("descriptions <= 200", r.detail)

    def test_cinco_skills_passa(self):
        for n in ("a", "b", "c", "d", "e"):
            write(os.path.join(self.d, ".claude", "skills", n, "SKILL.md"), "---\nname: %s\ndescription: x\n---\n" % n)
        r = results(self.d)["skills"]
        self.assertTrue(r.ok, r.detail)
        self.assertIn("5 próprias", r.detail)

    def test_skills_do_nucleo_nao_contam_no_teto(self):
        for n in ("a", "b", "c"):
            write(os.path.join(self.d, ".claude", "skills", n, "SKILL.md"), "---\nname: %s\ndescription: x\n---\n" % n)
        r = results(self.d)["skills"]
        self.assertTrue(r.ok, r.detail)
        self.assertIn("3 próprias (+7 do núcleo)", r.detail)

    def test_description_longa_falha(self):
        write(os.path.join(self.d, ".claude", "skills", "a", "SKILL.md"),
              "---\nname: a\ndescription: >\n  " + "y" * 201 + "\n---\n")
        self.assertFails("skills", "201")

    def test_skill_sem_description_falha(self):
        write(os.path.join(self.d, ".claude", "skills", "a", "SKILL.md"), "---\nname: a\n---\n")
        self.assertFails("skills", "sem description")

    def test_hook_citado_so_em_comentario_falha(self):
        write(os.path.join(self.rel, "tests", "test_hooks.py"),
              "# secret_guard destructive_guard gate_tests progress_guard: testar depois\n")
        self.assertFails("hooks", "sem teste")

    def _phase(self, phase):
        path = cfgmod.config_path(self.d)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["phase"] = phase
        write(path, json.dumps(data))

    def test_um_subagente_em_f1_falha_e_em_f2_passa(self):
        write(os.path.join(self.d, ".claude", "agents", "reviewer.md"), "---\nname: reviewer\n---\n")
        self._phase("F1")
        self.assertFails("subagents", "teto 0 na F1")
        self._phase("F2")
        self.assertTrue(results(self.d)["subagents"].ok)
        self._phase("depois")
        self.assertFails("subagents", "phase")

    def test_dois_subagentes_em_f2_passa(self):
        self._phase("F2")
        for n in ("r1", "r2"):
            write(os.path.join(self.d, ".claude", "agents", n + ".md"), "---\nname: %s\n---\n" % n)
        self.assertTrue(results(self.d)["subagents"].ok)

    def test_tres_subagentes_falha(self):
        self._phase("F2")
        for n in ("r1", "r2", "r3"):
            write(os.path.join(self.d, ".claude", "agents", n + ".md"), "---\nname: %s\n---\n" % n)
        self.assertFails("subagents", "3 subagentes")

    def test_pasta_agents_na_raiz_falha(self):
        os.makedirs(os.path.join(self.d, "agents"))
        self.assertFails("subagents", "agents/")

    def _roles(self, **roles):
        path = cfgmod.config_path(self.d)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("roles", {}).update(roles)  # F2-01: o resto dos papéis vem da release
        write(path, json.dumps(data))

    def test_juiz_grok_com_fallback_codex_passa(self):
        self._roles(judge={"cli": "grok", "model": "grok-4.7"},
                    judge_fallback={"cli": "codex", "model": "gpt-5.5"})
        config = results(self.d)["config"]
        self.assertTrue(config.ok, config.detail)
        self.assertIn("xai", config.detail)

    def test_cli_grok_com_modelo_de_outro_provedor_falha(self):
        self._roles(judge={"cli": "grok", "model": "gpt-5.5"})
        self.assertFails("config", "não roda")

    def test_juiz_mesmo_provedor_falha(self):
        self._roles(judge={"cli": "claude", "model": "claude-sonnet-5-5"})
        self.assertFails("config", "mesmo provedor")

    def test_juiz_agy_com_modelo_claude_falha(self):
        # o nome da CLI é outro, mas o provedor do modelo é o mesmo do executor
        self._roles(judge={"cli": "agy", "model": "claude-sonnet-5-5"})
        self.assertFails("config", "mesmo provedor")

    def test_fallback_mesmo_provedor_falha(self):
        self._roles(judge_fallback={"cli": "agy", "model": "claude-opus-5-5"})
        self.assertFails("config", "judge_fallback")

    def test_cli_incompativel_com_modelo_falha(self):
        self._roles(judge={"cli": "codex", "model": "gemini-3-pro"})
        self.assertFails("config", "não roda")

    def test_modelo_desconhecido_falha(self):
        self._roles(judge={"cli": "codex", "model": "misterio-1"})
        self.assertFails("config", "desconhecido")

    def test_papel_isolado_grok_passa(self):
        # F1-03 (operator 14/11: cursor → grok): a tarefa isolada roda pelo grok
        self._roles(isolated={"cli": "grok", "model": "grok-4.7"})
        config = results(self.d)["config"]
        self.assertTrue(config.ok, config.detail)

    def test_papel_isolado_mesmo_provedor_falha(self):
        self._roles(isolated={"cli": "claude", "model": "claude-opus-5-5"})
        self.assertFails("config", "isolated")

    def test_papel_isolado_cli_errada_falha(self):
        self._roles(isolated={"cli": "grok", "model": "gpt-6.1-sol"})
        self.assertFails("config", "não roda")

    def test_sem_config_falha(self):
        os.remove(cfgmod.config_path(self.d))
        self.assertFails("config", "falta")

    def test_progress_grande_falha(self):
        write(os.path.join(self.d, "docs", "progress.md"), "z" * 2001)
        self.assertFails("progress", "2001")

    def test_cli_exit_1_quando_falha(self):
        shutil.rmtree(os.path.join(self.d, ".claude"))
        code, out = hdev("check", "--root", self.d)
        self.assertEqual(code, 1)
        self.assertIn("FALHA", out)


class Provedor(unittest.TestCase):
    def test_prefixos(self):
        self.assertEqual(cfgmod.model_provider("claude-opus-5-5"), "anthropic")
        self.assertEqual(cfgmod.model_provider("gpt-5.5"), "openai")
        self.assertEqual(cfgmod.model_provider("gpt-6.1-sol"), "openai")
        self.assertEqual(cfgmod.model_provider("o3"), "openai")
        self.assertEqual(cfgmod.model_provider("gemini-3-pro"), "google")
        self.assertEqual(cfgmod.model_provider("grok-4.7"), "xai")
        self.assertEqual(cfgmod.model_provider("grok-4.7-build-fast"), "xai")
        self.assertIsNone(cfgmod.model_provider("x"))

    def test_description_em_bloco(self):
        text = "---\nname: a\ndescription: |\n  linha um\n  linha dois\nother: 1\n---\n"
        self.assertEqual(checkmod.skill_description(text), "linha um\nlinha dois")


if __name__ == "__main__":
    unittest.main()
