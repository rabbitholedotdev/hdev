"""Manifesto único: gates/skills/hooks/caps e o settings gerado por hdev sync."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, hdev, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev import config as cfgmod  # noqa: E402
from hdev import fechar as fecharmod  # noqa: E402
from hdev import sync as syncmod  # noqa: E402

# Denies de .claude/settings.json antes desta PR. O gerado tem de conter todos.
DENY_HOJE = [
    "Bash(sudo *)",
    "Bash(sudo)",
    "Bash(git push *)",
    "Bash(git push)",
    "Bash(rm -rf *)",
    "Bash(curl *)",
    "Bash(curl)",
    "Bash(wget *)",
    "Bash(wget)",
    "Read(~/.config/**)",
    "Read(~/.claude/**)",
    "Read(~/.codex/**)",
    "Read(~/.grok/**)",
    "Read(~/.cursor/**)",
    "Read(~/.ssh/**)",
    "Read(/etc/shadow)",
]

# 5 registros (ADR 0012): evento, matcher, tipo, comando, timeout.
HOOKS_HOJE = [
    ("PostToolUse", None, "command", 'python3 "$CLAUDE_PROJECT_DIR/harness/hooks/session.py"', 30),
    ("PreToolUse", "Bash", "command", 'python3 "$CLAUDE_PROJECT_DIR/harness/hooks/pre_tool.py"', 30),
    ("PreToolUse", "Write|Edit|MultiEdit|NotebookEdit|Read|AskUserQuestion", "command",
     'python3 "$CLAUDE_PROJECT_DIR/harness/hooks/pre_tool.py"', 30),
    ("Stop", None, "command", 'python3 "$CLAUDE_PROJECT_DIR/harness/hooks/stop_gate.py"', 900),
    ("UserPromptSubmit", None, "command", 'python3 "$CLAUDE_PROJECT_DIR/harness/hooks/session.py"', 30),
]


def flat_hooks(hooks):
    rows = []
    for event, groups in (hooks or {}).items():
        for group in groups or []:
            for hook in group.get("hooks") or []:
                rows.append((event, group.get("matcher"), hook.get("type"), hook.get("command"), hook.get("timeout")))
    return sorted(rows)


def mini_cfg():
    return {
        "phase": "F2",
        "gates": {"fast": ["python3", "-m", "unittest"], "full": ["python3", "-m", "unittest", "-v"]},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python3 hooks/x.py", "timeout": 1}]}]},
        "skills": {"F0": ["hdev"], "F2": ["hdev", "planejar"]},
    }


class Manifesto(unittest.TestCase):
    def test_chave_antiga_e_erro_sem_ler_o_comando(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"tests": {"command": ["false"]}}))
            cfg, err = cfgmod.load(d)
            self.assertIsNone(cfg)
            self.assertIn("gates.fast", err)
            self.assertIn("chave antiga", err)
            write(os.path.join(d, ".hdev", "config.json"), json.dumps(
                {"gates": {"full": ["true"]}, "judge": {"tests_command": ["false"], "timeout": 5}}))
            cfg, err = cfgmod.load(d)
            self.assertIsNone(cfg)
            self.assertIn("gates.full", err)

    def test_chave_antiga_na_release_e_erro(self):
        with TempDir() as d:
            rel = os.path.join(d, "rel")
            write(os.path.join(rel, ".hdev", "config.json"), json.dumps({"tests": {"command": ["x"]}, "version": 1}))
            os.symlink(rel, os.path.join(d, ".harnessdev"))
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"profile": "app"}))
            cfg, err = cfgmod.load(d)
            self.assertIsNone(cfg)
            self.assertIn("chave antiga", err)
            self.assertIn("release", err)

    def test_fechar_recusa_chave_antiga(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"tests": {"command": ["false"]}}))
            with self.assertRaises(fecharmod.FecharError) as cm:
                fecharmod.require_suite(d)
            self.assertIn("gates.full", str(cm.exception))

    def test_caps_diferente_do_teto_falha(self):
        self.assertIsNone(cfgmod.caps_error({"caps": dict(cfgmod.CAP_CEILING)}))
        err = cfgmod.caps_error({"caps": dict(cfgmod.CAP_CEILING, hooks=7)})
        self.assertIn("caps.hooks", err)
        self.assertIsNone(cfgmod.caps_error({}))


class Sync(unittest.TestCase):
    def _repo(self, d):
        write(os.path.join(d, ".hdev", "config.json"), json.dumps(mini_cfg()))
        for name in ("hdev", "planejar"):
            write(os.path.join(d, ".claude", "skills", name, "SKILL.md"),
                  "---\nname: %s\ndescription: x\n---\n" % name)

    def test_fase_nao_apaga_skill_e_o_arquivo_e_estavel(self):
        with TempDir() as d:
            self._repo(d)
            code, out = hdev("sync", "--root", d, "--phase", "F0")
            self.assertEqual(code, 0, out)
            self.assertTrue(os.path.isfile(os.path.join(d, ".claude", "skills", "planejar", "SKILL.md")))
            self.assertTrue(os.path.isfile(os.path.join(d, ".claude", "skills", "hdev", "SKILL.md")))
            path = os.path.join(d, ".claude", "settings.json")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertTrue(text.endswith("\n"))
            again = syncmod.render(d, "F0")
            self.assertEqual(text, again)
            self.assertEqual(text, json.dumps(json.loads(text), ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            settings = json.loads(text)
            self.assertEqual(settings["skillOverrides"], {"hdev": "on", "planejar": "off"})
            self.assertLessEqual(len(settings["permissions"]["allow"]), 15)
            for item in DENY_HOJE:
                self.assertIn(item, settings["permissions"]["deny"])

    def test_check_e_sync_check_usam_o_mesmo_diff(self):
        with TempDir() as d:
            self._repo(d)
            write(os.path.join(d, ".claude", "settings.json"), "{}\n")
            diff = syncmod.sync_diff(d)
            self.assertTrue(diff)
            code, out = hdev("sync", "--check", "--root", d)
            self.assertEqual(code, 1)
            self.assertEqual(out, diff)
            result = checkmod.check_sync(d)
            self.assertFalse(result.ok)
            self.assertEqual("\n".join(result.failures) + "\n", diff)
            self.assertEqual(hdev("sync", "--root", d)[0], 0)
            self.assertEqual(syncmod.sync_diff(d), "")
            codex = read_json(os.path.join(d, ".codex", "hooks.json"))
            self.assertIn("stop_gate.py", codex["hooks"]["Stop"][0]["hooks"][0]["command"])
            self.assertEqual(read_json(os.path.join(d, ".grok", "hooks", "stop.json")), codex)
            self.assertTrue(checkmod.check_sync(d).ok)
            self.assertEqual(hdev("sync", "--check", "--root", d)[0], 0)

    def test_repo_real_bate_com_o_manifesto(self):
        code, out = hdev("sync", "--check", "--root", ROOT)
        self.assertEqual(code, 0, out)
        settings = read_json(os.path.join(ROOT, ".claude", "settings.json"))
        allow = settings["permissions"]["allow"]
        self.assertLessEqual(len(allow), 15)
        self.assertEqual(len(allow), len(set(allow)))
        self.assertEqual(sum("bin/hdev check" in item for item in allow), 1)
        self.assertEqual(sum("bin/hdev judge" in item for item in allow), 1)
        self.assertFalse(any("python3 bin/hdev" in item or item.startswith("Bash(/") for item in allow))
        self.assertEqual(settings["permissions"]["deny"], DENY_HOJE)
        self.assertEqual(flat_hooks(settings["hooks"]), HOOKS_HOJE)
        self.assertEqual(settings["env"]["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"], "60")
        self.assertIsInstance(settings["env"]["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"], str)
        self.assertEqual(settings["skillOverrides"]["hdev"], "on")
        self.assertEqual(settings["skillOverrides"]["handoff"], "on")
        self.assertEqual(settings["skillOverrides"]["briefing"], "off")
        self.assertEqual(settings["skillOverrides"]["spec"], "off")
        self.assertLessEqual(sum(v == "on" for v in settings["skillOverrides"].values()), 5)
        cfg, err = cfgmod.load(ROOT)
        self.assertIsNone(err, err)
        self.assertNotIn("tests", cfg)
        self.assertNotIn("tests_command", cfg.get("judge") or {})
        self.assertTrue(cfgmod.gate_command(cfg, "fast"))
        self.assertTrue(cfgmod.gate_command(cfg, "full"))
        self.assertIsNone(cfgmod.caps_error(cfg))
        over = syncmod.skill_overrides(ROOT, cfg, "F0")
        self.assertEqual(over["hdev"], "on")
        self.assertEqual(over["handoff"], "off")
        self.assertTrue(os.path.isfile(os.path.join(ROOT, ".claude", "skills", "handoff", "SKILL.md")))

    def test_sync_troca_tests_por_gates(self):
        with TempDir() as d:
            cfg = mini_cfg()
            cfg.pop("gates", None)
            cfg["tests"] = {"command": ["python3", "-m", "unittest", "discover"], "timeout": 12,
                            "on_stop": False}
            cfg["judge"] = {"tests_command": ["python3", "-m", "unittest", "-v"], "timeout": 3}
            write(os.path.join(d, ".hdev", "config.json"), json.dumps(cfg))
            for name in ("hdev", "planejar"):
                write(os.path.join(d, ".claude", "skills", name, "SKILL.md"),
                      "---\nname: %s\ndescription: x\n---\n" % name)
            code, out = hdev("sync", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("tests virou gates", out)
            data = read_json(os.path.join(d, ".hdev", "config.json"))
            self.assertNotIn("tests", data)
            self.assertNotIn("tests_command", data["judge"])
            self.assertEqual(data["judge"]["timeout"], 3)
            self.assertEqual(data["gates"]["fast"], ["python3", "-m", "unittest", "discover"])
            self.assertEqual(data["gates"]["full"], ["python3", "-m", "unittest", "-v"])
            self.assertEqual(data["gates"]["timeout"], 12)
            self.assertIs(data["gates"]["on_stop"], False)

    def test_fase_com_seis_recusa(self):
        with TempDir() as d:
            cfg = mini_cfg()
            cfg["skills"]["F2"] = ["a", "b", "c", "d", "e", "f"]
            write(os.path.join(d, ".hdev", "config.json"), json.dumps(cfg))
            code, out = hdev("sync", "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("6", out)
            self.assertIn("teto 5", out)


def _roles():
    return {
        "executor": {"cli": "claude", "model": "claude-opus-5-5"},
        "judge": {"cli": "grok", "model": "grok-4.7"},
    }


class MatcherNotebookEdit(unittest.TestCase):
    """NBK-001: no app, o check aceita o matcher de edição com ou sem NotebookEdit até cada app rodar `hdev sync`."""
    VELHO = "Write|Edit|MultiEdit|Read|AskUserQuestion"
    NOVO = "Write|Edit|MultiEdit|NotebookEdit|Read|AskUserQuestion"

    def _app(self, d, release_matcher, app_matcher):
        with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as f:
            core = f.read().replace(self.NOVO, self.VELHO)  # o núcleo já tem o NOVO (NBK-002); a release falsa escolhe
        self.assertIn('"%s"' % self.VELHO, core)
        rel = os.path.join(d, "rel")
        write(os.path.join(rel, ".claude", "settings.json"), core.replace(self.VELHO, release_matcher))
        app = os.path.join(d, "app")
        os.makedirs(app)
        os.symlink(rel, os.path.join(app, ".harnessdev"))
        write(syncmod.settings_path(app), syncmod.render(app).replace(release_matcher, app_matcher))
        syncmod.write_cli_hooks(app)
        return app

    def test_app_aceita_o_matcher_com_ou_sem_notebookedit(self):
        for rel_m, app_m in ((self.VELHO, self.NOVO), (self.NOVO, self.VELHO), (self.NOVO, self.NOVO)):
            with TempDir() as d:
                app = self._app(d, rel_m, app_m)
                self.assertEqual(syncmod.settings_diff(app), "", (rel_m, app_m))
                self.assertTrue(checkmod.check_sync(app).ok, (rel_m, app_m))
                self.assertEqual(hdev("sync", "--check", "--root", app)[0], 0, (rel_m, app_m))

    def test_app_com_outro_matcher_segue_divergindo(self):
        with TempDir() as d:
            app = self._app(d, self.NOVO, "Write|Edit")
            self.assertTrue(syncmod.settings_diff(app))
            self.assertFalse(checkmod.check_sync(app).ok)

    def test_nucleo_segue_estrito(self):
        with TempDir() as d:
            cfg = mini_cfg()
            cfg["hooks"]["PreToolUse"] = [{"matcher": self.VELHO, "hooks": [
                {"type": "command", "command": "python3 hooks/y.py", "timeout": 1}]}]
            write(os.path.join(d, ".hdev", "config.json"), json.dumps(cfg))
            for name in ("hdev", "planejar"):
                write(os.path.join(d, ".claude", "skills", name, "SKILL.md"),
                      "---\nname: %s\ndescription: x\n---\n" % name)
            self.assertEqual(hdev("sync", "--root", d)[0], 0)
            self.assertEqual(syncmod.settings_diff(d), "")
            path = syncmod.settings_path(d)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            write(path, text.replace(self.VELHO, self.NOVO))
            self.assertTrue(syncmod.settings_diff(d))


class Autocompact(unittest.TestCase):
    def _repo(self, d, cfg):
        write(os.path.join(d, ".hdev", "config.json"), json.dumps(cfg))
        for name in ("hdev", "planejar"):
            write(os.path.join(d, ".claude", "skills", name, "SKILL.md"),
                  "---\nname: %s\ndescription: x\n---\n" % name)

    def _cfg(self, handoff=None, roles=False):
        cfg = mini_cfg()
        if handoff is not None:
            cfg["handoff"] = handoff
        if roles:
            cfg["roles"] = _roles()
        return cfg

    def test_sync_grava_a_porcentagem_como_string(self):
        with TempDir() as d:
            self._repo(d, self._cfg({"window_tokens": 200000, "threshold": 0.5}))
            code, out = hdev("sync", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn(".claude/settings.json", out)
            path = os.path.join(d, ".claude", "settings.json")
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.assertIn('"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "60"', text)
            self.assertNotIn('"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": 60', text)
            self.assertEqual(read_json(path)["env"], {"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "60"})
            self.assertEqual(text, syncmod.render(d))

    def test_default_deriva_limiar_mais_dez(self):
        self.assertEqual(syncmod.autocompact_pct({}), 60)
        self.assertEqual(syncmod.autocompact_pct({"handoff": {"threshold": 0.5}}), 60)
        self.assertEqual(syncmod.autocompact_pct({"handoff": {"threshold": 0.25}}), 35)
        self.assertEqual(syncmod.autocompact_pct({"handoff": {"threshold": 0.25, "autocompact_pct": 80}}), 80)
        self.assertEqual(syncmod.autocompact_pct({"handoff": {"autocompact_pct": 60.0}}), 60)
        cfg, err = cfgmod.load(ROOT)
        self.assertIsNone(err, err)
        self.assertNotIn("autocompact_pct", cfg.get("handoff") or {})
        self.assertEqual(cfg["handoff"]["threshold"], 0.5)
        self.assertEqual(syncmod.autocompact_pct(cfg), 60)
        with TempDir() as d:
            self._repo(d, self._cfg({"threshold": 0.25}))
            self.assertIn('"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "35"', syncmod.render(d))
            self._repo(d, self._cfg())
            self.assertIn('"CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "60"', syncmod.render(d))

    def test_check_falha_no_limiar_ou_abaixo(self):
        cases = (
            {"threshold": 0.5, "autocompact_pct": 50},
            {"threshold": 0.5, "autocompact_pct": 40},
            {"threshold": 0.4, "autocompact_pct": 40},
        )
        for handoff in cases:
            with TempDir() as d:
                self._repo(d, self._cfg(handoff, roles=True))
                result = checkmod.check_config(d)
                self.assertFalse(result.ok, result.detail)
                self.assertIn("limiar", result.detail)
                self.assertIn(str(handoff["autocompact_pct"]), result.detail)
        with TempDir() as d:
            self._repo(d, self._cfg({"threshold": 0.4, "autocompact_pct": 41}, roles=True))
            result = checkmod.check_config(d)
            self.assertTrue(result.ok, result.detail)

    def test_check_falha_acima_de_95(self):
        for pct in (96, 100):
            with TempDir() as d:
                self._repo(d, self._cfg({"threshold": 0.5, "autocompact_pct": pct}, roles=True))
                code, out = hdev("sync", "--root", d)
                self.assertEqual(code, 0, out)
                self.assertEqual(
                    read_json(os.path.join(d, ".claude", "settings.json"))["env"]["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"],
                    str(pct))
                self.assertTrue(checkmod.check_sync(d).ok)
                result = checkmod.check_config(d)
                self.assertFalse(result.ok, result.detail)
                self.assertIn("acima de 95", result.detail)
                self.assertIn(str(pct), result.detail)
        with TempDir() as d:
            self._repo(d, self._cfg({"threshold": 0.5, "autocompact_pct": 95}, roles=True))
            result = checkmod.check_config(d)
            self.assertTrue(result.ok, result.detail)

    def test_check_falha_se_settings_diverge(self):
        with TempDir() as d:
            self._repo(d, self._cfg({"threshold": 0.5}))
            code, out = hdev("sync", "--root", d)
            self.assertEqual(code, 0, out)
            path = os.path.join(d, ".claude", "settings.json")
            data = read_json(path)
            data["env"]["CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"] = "40"
            write(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
            result = checkmod.check_sync(d)
            self.assertFalse(result.ok, result.detail)
            blob = "\n".join(result.failures)
            self.assertIn("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE", blob)
            self.assertIn("40", blob)
            code, out = hdev("sync", "--check", "--root", d)
            self.assertEqual(code, 1)
            self.assertEqual(out, blob + "\n")

    def test_pct_que_nao_e_inteiro_falha_o_check_e_o_sync(self):
        with TempDir() as d:
            self._repo(d, self._cfg({"autocompact_pct": "60"}, roles=True))
            result = checkmod.check_config(d)
            self.assertFalse(result.ok, result.detail)
            self.assertIn("inteiro", result.detail)
            code, out = hdev("sync", "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("inteiro", out)
