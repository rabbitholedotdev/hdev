"""Eval com braços: plain, base, cand, teto, falso, CLI ausente e o caso do fechar."""
import json
import os
import stat
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, read_json, write  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hdev import eval as evalmod  # noqa: E402

PROBE = (
    "python3 -c \"import os; print('no' if not os.path.exists('CLAUDE.md') else 'yes')\""
)


def commit(d, msg="base"):
    git(d, "add", "-A")
    proc = git(d, "commit", "-q", "--no-verify", "-m", msg)
    assert proc.returncode == 0, proc.stderr
    return git(d, "rev-parse", "HEAD").stdout.strip()


def tiny(d):
    git(d, "init", "-q")
    git(d, "config", "user.name", "t")
    git(d, "config", "user.email", "t@example.invalid")
    write(os.path.join(d, ".gitignore"), ".hdev/runs/\n.hdev/state/\n.hdev/cache/\n")
    write(os.path.join(d, "CLAUDE.md"), "@AGENTS.md\n")
    write(os.path.join(d, "AGENTS.md"), "# A\n")
    write(os.path.join(d, ".claude", "settings.json"), "{}\n")
    write(os.path.join(d, ".claude", "skills", "hdev", "SKILL.md"),
          "---\nname: hdev\ndescription: Faz.\n---\n")
    write(os.path.join(d, ".claude", "hooks", "x.py"), "# x\n")
    write(os.path.join(d, ".claude", "agents", "a.md"), "---\nname: a\ndescription: Fica.\n---\n")
    write(os.path.join(d, "harness", "prompts", "executor.md"), "# e\n")
    write(os.path.join(d, "harness", "hooks", "session.py"), "# fica\n")
    write(os.path.join(d, "README.md"), "r\n")
    return commit(d)


def put_task(d, case, acceptance, prompt=None, base="HEAD", caps=None):
    task = {
        "id": case, "repo": ".", "base_sha": base, "prompt": prompt, "spec": None,
        "acceptance": acceptance, "caps": caps or {"runs": 12}, "draft": False,
    }
    write(os.path.join(d, "evals", "tasks", case, "task.json"),
          json.dumps(task, ensure_ascii=False, indent=2) + "\n")


def present(path):
    return os.path.lexists(path)


def slurp(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class Bracos(unittest.TestCase):
    def test_plain_tira_base_mantem_e_nao_apaga_o_hook(self):
        with TempDir() as d:
            tiny(d)
            plain = os.path.join(d, "plain")
            base = os.path.join(d, "base")
            for dest in (plain, base):
                os.makedirs(dest)
                for rel in ("CLAUDE.md", "AGENTS.md", ".claude/settings.json", ".claude/skills/hdev/SKILL.md",
                            ".claude/hooks/x.py", ".claude/agents/a.md", "harness/prompts/executor.md",
                            "harness/hooks/session.py"):
                    src = os.path.join(d, rel)
                    target = os.path.join(dest, rel)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(src, encoding="utf-8") as handle:
                        text = handle.read()
                    write(target, text)
            evalmod.apply_arm(plain, "plain", d)
            evalmod.apply_arm(base, "base", d)
            for rel in ("CLAUDE.md", "AGENTS.md", ".claude/settings.json", ".claude/skills/hdev/SKILL.md",
                        ".claude/hooks/x.py", "harness/prompts/executor.md"):
                self.assertFalse(present(os.path.join(plain, rel)), rel)
                self.assertTrue(present(os.path.join(base, rel)), rel)
            self.assertTrue(present(os.path.join(plain, "harness", "hooks", "session.py")))
            self.assertTrue(present(os.path.join(plain, ".claude", "agents", "a.md")))
            self.assertEqual(slurp(os.path.join(d, "CLAUDE.md")), "@AGENTS.md\n")

    def test_runner_plain_nao_tem_claude_e_base_tem(self):
        with TempDir() as d:
            tiny(d)
            put_task(d, "sonda", [{"cmd": PROBE, "expect_exit": 0, "expect_output": "no"}])
            code, out = hdev("eval", "run", "--case", "sonda", "--arms", "plain", "--runs", "1",
                             "--runner", "none", "--root", d)
            self.assertEqual(code, 0, out)
            put_task(d, "sonda", [{"cmd": PROBE, "expect_exit": 0, "expect_output": "yes"}])
            code, out = hdev("eval", "run", "--case", "sonda", "--arms", "base", "--runs", "1",
                             "--runner", "none", "--root", d)
            self.assertEqual(code, 0, out)

    def test_cand_aplica_overlay_e_nao_mexe_na_origem(self):
        with TempDir() as d:
            tiny(d)
            marker = os.path.join(d, "evals", "arms", "cand-demo", "marker.txt")
            write(marker, "novo\n")
            antes = slurp(marker)
            put_task(d, "demo", [{
                "cmd": "python3 -c \"print(open('marker.txt').read().strip())\"",
                "expect_exit": 0, "expect_output": "novo",
            }])
            code, out = hdev("eval", "run", "--case", "demo", "--arms", "cand-demo", "--runs", "1",
                             "--runner", "none", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertEqual(slurp(marker), antes)
            self.assertFalse(present(os.path.join(d, "marker.txt")))

    def test_arvore_de_trabalho_nao_muda(self):
        with TempDir() as d:
            tiny(d)
            put_task(d, "eco", [{
                "cmd": "python3 -c \"print('eco')\"", "expect_exit": 0, "expect_output": "eco",
            }])
            commit(d, "tarefa")
            tracked = os.path.join(d, "README.md")
            write(tracked, "DIRTY\n")
            write(os.path.join(d, "solto.txt"), "solto\n")
            status = git(d, "status", "--porcelain").stdout
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "plain,base", "--runs", "1",
                             "--runner", "none", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertEqual(git(d, "status", "--porcelain").stdout, status)
            self.assertEqual(slurp(tracked), "DIRTY\n")
            self.assertEqual(slurp(os.path.join(d, "solto.txt")), "solto\n")
            runs = [name for name in os.listdir(os.path.join(d, ".hdev", "runs")) if name.startswith("eval-")]
            self.assertEqual(len(runs), 1)
            data = read_json(os.path.join(d, ".hdev", "runs", runs[0]))
            self.assertEqual([row["pass"] for row in data["results"]], [True, True])
            self.assertIsNone(data["results"][0]["tokens"])
            self.assertIsInstance(data["results"][0]["seconds"], (int, float))
            self.assertIsInstance(data["results"][0]["xray"], int)

    def test_teto_de_12_recusa(self):
        with TempDir() as d:
            tiny(d)
            put_task(d, "eco", [{"cmd": "python3 -c \"print(1)\"", "expect_exit": 0}])
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "plain,base", "--runs", "7",
                             "--root", d)
            self.assertEqual(code, 2, out)
            self.assertIn("12", out)
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "plain", "--runs", "13", "--root", d)
            self.assertEqual(code, 2, out)
            self.assertFalse(os.path.isdir(os.path.join(d, ".hdev", "runs")))

    def test_falso_preenche_tokens_do_json(self):
        with TempDir() as d:
            tiny(d)
            script = os.path.join(d, "falso.py")
            write(script, "#!/usr/bin/env python3\nimport json\nprint(json.dumps({'usage': {'input_tokens': 21, "
                          "'output_tokens': 4, 'cache_read_input_tokens': 8}}))\n")
            os.chmod(script, os.stat(script).st_mode | stat.S_IEXEC)
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({"eval": {"fake_cmd": script}}))
            put_task(d, "eco", [{"cmd": "python3 -c \"print('eco')\"", "expect_exit": 0, "expect_output": "eco"}],
                     prompt="faz")
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "base", "--runs", "1",
                             "--runner", "fake", "--root", d)
            self.assertEqual(code, 0, out)
            runs = os.listdir(os.path.join(d, ".hdev", "runs"))
            data = read_json(os.path.join(d, ".hdev", "runs", runs[0]))
            self.assertEqual(data["results"][0]["tokens"], {"input": 21, "output": 4, "cache": 8})
            self.assertNotEqual(data["results"][0]["tokens"]["input"], data["results"][0]["xray"])

    def test_sem_agente_tokens_null(self):
        with TempDir() as d:
            tiny(d)
            put_task(d, "eco", [{"cmd": "python3 -c \"print('eco')\"", "expect_exit": 0}])
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "base", "--runs", "1",
                             "--runner", "auto", "--root", d)
            self.assertEqual(code, 0, out)
            data = read_json(os.path.join(d, ".hdev", "runs", os.listdir(os.path.join(d, ".hdev", "runs"))[0]))
            self.assertIsNone(data["results"][0]["tokens"])
            self.assertIsNone(data["results"][0]["agent_exit"])

    def test_cli_ausente_sai_3(self):
        with TempDir() as d:
            tiny(d)
            missing = os.path.join(d, "no-such-claude")
            write(os.path.join(d, ".hdev", "config.json"),
                  json.dumps({"eval": {"agent_cmd": [missing, "-p", "--output-format", "json"]}}))
            put_task(d, "eco", [{"cmd": "python3 -c \"print(1)\"", "expect_exit": 0}], prompt="oi")
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "base", "--runs", "1",
                             "--runner", "claude", "--root", d)
            self.assertEqual(code, 3, out)
            self.assertIn("ausente", out)
            self.assertNotIn("Traceback", out)


# Claude falso: devolve usage e modelUsage com o --model que recebeu. Sai 4 se o prompt vier sem o preâmbulo
# ou se o ambiente trouxer CLAUDE_PROJECT_DIR/CLAUDECODE. `modelo` fixa a resposta; `sono` segura o processo.
FAKE_CLAUDE = """#!/usr/bin/env python3
import json, os, sys, time
argv = sys.argv[1:]
prompt = sys.stdin.read()
if "clone descartável" not in prompt or "CLAUDE_PROJECT_DIR" in os.environ or "CLAUDECODE" in os.environ:
    sys.exit(4)
time.sleep(%(sono)s)
model = %(modelo)r or (argv[argv.index("--model") + 1] if "--model" in argv else "nenhum")
print(json.dumps({"type": "result", "usage": {"input_tokens": 40, "output_tokens": 9},
                  "modelUsage": {"claude-haiku-5-5": {"outputTokens": 1}, model: {"outputTokens": 9}}}))
"""


def fake_claude(d, modelo=None, sono=0, extra=None):
    """Grava `<d>/fakebin/claude` e o manifesto que aponta para ele. Nenhum modelo é chamado."""
    path = os.path.join(d, "fakebin", "claude")
    write(path, FAKE_CLAUDE % {"modelo": modelo, "sono": sono})
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    ev = {"agent_cmd": [path, "-p", "--output-format", "json"]}
    ev.update(extra or {})
    write(os.path.join(d, ".hdev", "config.json"), json.dumps({"eval": ev}))
    return path


def last_run(d):
    folder = os.path.join(d, ".hdev", "runs")
    return read_json(os.path.join(folder, sorted(n for n in os.listdir(folder) if n.startswith("eval-"))[-1]))


def eco_task(d, prompt="faz"):
    put_task(d, "eco", [{"cmd": "python3 -c \"print('eco')\"", "expect_exit": 0}], prompt=prompt)


class BracoClaude(unittest.TestCase):
    def test_argv_padrao_tem_sonnet_proibidas_e_permissao(self):
        argv = evalmod.agent_argv({})
        self.assertEqual(argv[:4], ["claude", "-p", "--output-format", "json"])
        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-5-5")
        self.assertEqual(argv[argv.index("--permission-mode") + 1], "acceptEdits")
        i = argv.index("--disallowedTools")
        self.assertEqual(argv[i + 1:i + 3], ["Bash(git " + "push:*)", "Bash(su" + "do:*)"])
        self.assertIn("--allowedTools", argv)
        self.assertEqual(evalmod.argv_model(argv), "claude-sonnet-5-5")

    def test_eval_model_e_model_do_comando(self):
        argv = evalmod.agent_argv({"eval": {"model": "claude-haiku-5-5"}})
        self.assertEqual(argv[argv.index("--model") + 1], "claude-haiku-5-5")
        argv = evalmod.agent_argv({"eval": {"agent_cmd": "claude -p --model claude-opus-5-5"}})
        self.assertEqual(argv.count("--model"), 1)
        self.assertEqual(evalmod.argv_model(argv), "claude-opus-5-5")
        argv = evalmod.agent_argv({"eval": {"agent_cmd": "claude -p --permission-mode plan"}})
        self.assertEqual(argv.count("--permission-mode"), 1)
        self.assertIn("--disallowedTools", argv)
        # outro executável não ganha flag do claude
        self.assertEqual(evalmod.agent_argv({"eval": {"agent_cmd": "python3 x.py"}}), ["python3", "x.py"])
        self.assertIsNone(evalmod.argv_model(["python3", "x.py"]))

    def test_timeout_configuravel(self):
        self.assertEqual(evalmod.agent_timeout({}), 600)
        self.assertEqual(evalmod.agent_timeout({"eval": {"timeout_sec": 5}}), 5)
        self.assertEqual(evalmod.agent_timeout({"eval": {"timeout_sec": "x"}}), 600)
        self.assertEqual(evalmod.agent_timeout({"eval": {"timeout_sec": 0}}), 600)

    def test_parse_model_fica_com_o_de_mais_saida(self):
        text = json.dumps({"usage": {}, "modelUsage": {
            "claude-haiku-5-5": {"inputTokens": 900, "outputTokens": 20},
            "claude-sonnet-5-5": {"inputTokens": 10, "outputTokens": 300}}})
        self.assertEqual(evalmod.parse_model(text), "claude-sonnet-5-5")
        self.assertIsNone(evalmod.parse_model(json.dumps({"usage": {"input_tokens": 1}})))
        self.assertIsNone(evalmod.parse_model("não é json"))
        self.assertTrue(evalmod.model_ok("claude-sonnet-5-5", "claude-sonnet-5-5-20261001"))
        self.assertFalse(evalmod.model_ok("claude-sonnet-5-5", "claude-opus-5-5"))
        self.assertFalse(evalmod.model_ok("claude-sonnet-5-5", None))

    def test_corrida_grava_modelo_tokens_e_segundos(self):
        with TempDir() as d:
            tiny(d)
            fake_claude(d)
            eco_task(d)
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "plain,base", "--runs", "1",
                             "--runner", "claude", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("model=claude-sonnet-5-5", out)
            self.assertNotIn("≠", out)
            data = last_run(d)
            self.assertEqual(data["model"], "claude-sonnet-5-5")
            for row in data["results"]:
                self.assertTrue(row["pass"], row)
                self.assertEqual(row["model"], "claude-sonnet-5-5")
                self.assertTrue(row["model_ok"])
                self.assertEqual(row["tokens"], {"input": 40, "output": 9, "cache": None})
                self.assertIsInstance(row["seconds"], (int, float))

    def test_ambiente_sem_variaveis_da_sessao_de_fora(self):
        from unittest import mock
        with TempDir() as d:
            tiny(d)
            fake_claude(d)
            eco_task(d)
            with mock.patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": d, "CLAUDECODE": "1"}):
                res = evalmod.run(d, "eco", "base", 1, "claude")
            self.assertEqual(res["results"][0]["agent_exit"], 0, res["results"][0])

    def test_modelo_diferente_e_marcado(self):
        with TempDir() as d:
            tiny(d)
            fake_claude(d, modelo="claude-opus-5-5")
            eco_task(d)
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "base", "--runs", "1",
                             "--runner", "claude", "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("modelo ≠ pedido", out)
            row = last_run(d)["results"][0]
            self.assertEqual(row["model"], "claude-opus-5-5")
            self.assertFalse(row["model_ok"])

    def test_timeout_e_falha_nunca_pass(self):
        with TempDir() as d:
            tiny(d)
            fake_claude(d, sono=5, extra={"timeout_sec": 1})
            eco_task(d)
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "base", "--runs", "1",
                             "--runner", "claude", "--root", d)
            self.assertEqual(code, 1, out)
            row = last_run(d)["results"][0]
            self.assertFalse(row["pass"])
            self.assertIn("timeout", row["failures"][0])

    def test_claude_sem_prompt_recusa_antes_de_gastar(self):
        with TempDir() as d:
            tiny(d)
            fake_claude(d)
            eco_task(d, prompt=None)
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "base", "--runs", "1",
                             "--runner", "claude", "--root", d)
            self.assertEqual(code, 2, out)
            self.assertIn("prompt", out)
            self.assertFalse(os.path.isdir(os.path.join(d, ".hdev", "runs")))

    def test_dry_run_mostra_o_modelo(self):
        with TempDir() as d:
            tiny(d)
            fake_claude(d)
            eco_task(d)
            code, out = hdev("eval", "run", "--case", "eco", "--arms", "plain,base", "--runs", "1",
                             "--runner", "claude", "--dry-run", "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("modelo: claude-sonnet-5-5", out)
            self.assertFalse(os.path.isdir(os.path.join(d, ".hdev", "runs")))

    def test_caso_smoke_tem_prompt(self):
        task = read_json(os.path.join(ROOT, "evals", "tasks", "smoke-init-check", "task.json"))
        self.assertTrue(isinstance(task.get("prompt"), str) and task["prompt"].strip())


class FecharGrava(unittest.TestCase):
    def _repo(self, d, green=True):
        git(d, "init", "-q")
        git(d, "config", "user.name", "t")
        git(d, "config", "user.email", "t@example.invalid")
        write(os.path.join(d, ".gitignore"), ".hdev/runs/\n.hdev/state/\n")
        write(os.path.join(d, "README.md"), "x\n")
        base = commit(d, "inicial")
        plan = "work/caso/plan.md"
        write(os.path.join(d, plan),
              "# Plano — caso\n\n## Critério de pronto\n- `python3 -c \"print(1)\"` sai 0\n")
        cmd = [sys.executable, "-c", "import sys; sys.exit(%d)" % (0 if green else 1)]
        write(os.path.join(d, ".hdev", "config.json"),
              json.dumps({"base_branch": "branch-base", "gates": {"full": cmd, "timeout": 30}}))
        head = commit(d, "turno")
        code, out = hdev("base", "--plan", plan, "--root", d, "--marcar", base)
        assert code == 0, out
        return plan, base, head

    def test_pass_grava_depois_e_falha_nao_grava(self):
        with TempDir() as d:
            plan, base, head = self._repo(d, green=False)
            rel = os.path.join(d, "evals", "tasks", "caso", "task.json")
            write(rel, json.dumps({"id": "caso", "draft": True, "acceptance": [], "prompt": "guarda"}) + "\n")
            commit(d, "caso antigo")
            code, out = hdev("fechar", "--plan", plan, "--root", d)
            self.assertEqual(code, 1, out)
            self.assertIn("suíte vermelha", out)
            antigo = slurp(rel)
            self.assertIn("guarda", antigo)
            self.assertNotIn("python3", antigo)
            cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]
            write(os.path.join(d, ".hdev", "config.json"),
                  json.dumps({"base_branch": "branch-base", "gates": {"full": cmd, "timeout": 30}}))
            head = commit(d, "suite verde")
            tree = git(d, "rev-parse", "HEAD^{tree}").stdout.strip()
            code, out = hdev("fechar", "--plan", plan, "--root", d)
            self.assertEqual(code, 0, out)
            self.assertIn("caso:", out)
            self.assertEqual(git(d, "rev-parse", "HEAD").stdout.strip(), head)
            data = read_json(rel)
            self.assertEqual(data["base_sha"], base)
            self.assertFalse(data["draft"])
            self.assertEqual(data["acceptance"][0]["cmd"], 'python3 -c "print(1)"')
            self.assertEqual(data["acceptance"][0]["expect_exit"], 0)
            self.assertEqual(data["prompt"], "guarda")
            committed = git(d, "show", "HEAD:evals/tasks/caso/task.json").stdout
            self.assertIn("draft", committed)
            self.assertNotIn("python3", committed)
            runs = [name for name in os.listdir(os.path.join(d, ".hdev", "runs")) if name.startswith("fechar-")]
            verdict = read_json(os.path.join(d, ".hdev", "runs", runs[-1]))
            self.assertIn(tree, verdict.get("gates_full", ""))

    def test_dry_run_nao_grava(self):
        with TempDir() as d:
            plan, _base, head = self._repo(d, green=True)
            code, out = hdev("fechar", "--plan", plan, "--root", d, "--dry-run")
            self.assertEqual(code, 0, out)
            self.assertFalse(os.path.exists(os.path.join(d, "evals", "tasks", "caso", "task.json")))
            self.assertEqual(git(d, "rev-parse", "HEAD").stdout.strip(), head)

    def test_na_base_o_caso_entra_no_marco(self):
        with TempDir() as d:
            plan, base, _head = self._repo(d, green=True)
            branch = git(d, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "base_branch": branch,
                "gates": {"full": [sys.executable, "-c", "import sys; sys.exit(0)"], "timeout": 30},
            }))
            head = commit(d, "na base")
            code, out = hdev("base", "--plan", plan, "--root", d, "--marcar", base, "--force")
            self.assertEqual(code, 0, out)
            # fora do juiz: o marco na base pede pass. Este teste usa a branch como base e
            # o conjunto já marcou a base; sem juiz o fechar recusa. O override não dispensa a suíte.
            code, out = hdev("fechar", "--plan", plan, "--root", d, "--override", "operator: teste do caso")
            self.assertEqual(code, 0, out)
            self.assertIn("fechada", out)
            self.assertNotEqual(git(d, "rev-parse", "HEAD").stdout.strip(), head)
            shown = git(d, "show", "HEAD:evals/tasks/caso/task.json").stdout
            self.assertIn("python3", shown)
            parent = git(d, "show", "HEAD~1:evals/tasks/caso/task.json")
            self.assertNotEqual(parent.returncode, 0)


class ExitDoPlano(unittest.TestCase):
    def test_sai_1_grava_expect_exit_1(self):
        text = "## Critério de pronto\n- `python3 -c \"import sys; sys.exit(1)\"` sai 1\n"
        items, ok = evalmod.commands_from_plan(text)
        self.assertTrue(ok)
        self.assertEqual(items, [{
            "cmd": 'python3 -c "import sys; sys.exit(1)"', "expect_exit": 1,
        }])
        text = "## Critério de pronto\n- `python3 -c \"import sys; sys.exit(1)\"` exit 1\n"
        items, ok = evalmod.commands_from_plan(text)
        self.assertTrue(ok)
        self.assertEqual(items[0]["expect_exit"], 1)

    def test_exit_ilegivel_vira_rascunho_sem_chutar_zero(self):
        text = "## Critério de pronto\n- `python3 -c \"print(1)\"` quando der\n"
        items, ok = evalmod.commands_from_plan(text)
        self.assertFalse(ok)
        self.assertEqual(items, [])
        with TempDir() as d:
            rel = evalmod.record_case(d, "caso", text, None, "work/caso/plan.md")
            data = read_json(os.path.join(d, rel))
            self.assertTrue(data["draft"])
            self.assertEqual(data["acceptance"], [])

    def test_hdev_e_bin_hdev_viram_um_so(self):
        text = "## Critério de pronto\n- falha o `hdev check`, segue\n- `bin/hdev check` sai 0\n"
        items, ok = evalmod.commands_from_plan(text)
        self.assertTrue(ok)
        self.assertEqual(items, [{"cmd": "bin/hdev check", "expect_exit": 0}])

    def test_exits_que_discordam_nao_viram_zero(self):
        text = "## Critério de pronto\n- `bin/hdev check` sai 0\n- `bin/hdev check` sai 1\n"
        items, ok = evalmod.commands_from_plan(text)
        self.assertFalse(ok)
        self.assertEqual(items, [])

    def test_plano_desta_unidade_le_o_xray_e_deduplica(self):
        text = slurp(os.path.join(ROOT, "work", "v2-pr9-evals-xray", "plan.md"))
        items, ok = evalmod.commands_from_plan(text)
        self.assertTrue(ok, items)
        cmds = [item["cmd"] for item in items]
        self.assertEqual(cmds.count("bin/hdev check"), 1)
        self.assertFalse(any(cmd == "hdev check" or cmd.startswith("hdev ") for cmd in cmds))
        by = {item["cmd"]: item for item in items}
        self.assertEqual(by["bin/hdev xray --max 100"]["expect_exit"], 1)
        self.assertEqual(by["bin/hdev xray --max 15000"]["expect_exit"], 0)
        self.assertEqual(by["bin/hdev check"]["expect_exit"], 0)
        self.assertLess(cmds.index("python3 -m unittest discover -s tests -q"), cmds.index("bin/hdev check"))

    def test_repete_o_caso_que_o_fechar_gravaria(self):
        plan = (
            "# Plano — eco\n\n## Critério de pronto\n"
            "- `python3 -c \"import sys; sys.exit(1)\"` exit 1\n"
            "- `python3 -c \"print('ok')\"` = 0\n"
            "- `python3 -c \"import sys; sys.exit(3)\"` sai ≠ 0\n"
            "- `hdev check` sai 0\n"
            "- `bin/hdev check` sai 0\n"
        )
        # O check de verdade não entra no replay: o fixture troca por python,
        # e o plano desta unidade é conferido no teste de cima.
        replay = (
            "# Plano — eco\n\n## Critério de pronto\n"
            "- `python3 -c \"import sys; sys.exit(1)\"` exit 1\n"
            "- `python3 -c \"print('ok')\"` = 0\n"
            "- `python3 -c \"import sys; sys.exit(3)\"` sai ≠ 0\n"
        )
        items, ok = evalmod.commands_from_plan(plan)
        self.assertTrue(ok)
        self.assertEqual(
            [item["cmd"] for item in items if item["cmd"].endswith("check")],
            ["bin/hdev check"])
        with TempDir() as d:
            rel = evalmod.record_case(d, "eco", replay, "abc", "work/eco/plan.md")
            data = read_json(os.path.join(d, rel))
            self.assertFalse(data["draft"])
            self.assertEqual(data["acceptance"][0]["expect_exit"], 1)
            failures, codes = evalmod.execute_steps(data["acceptance"], d, "", d)
            self.assertEqual(failures, [])
            self.assertEqual(codes, [1, 0, 3])


if __name__ == "__main__":
    unittest.main()
