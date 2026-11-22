"""Ambiente e wrapper das CLIs do host usados pelo hdev judge."""
import os
import shlex
import subprocess
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import TempDir  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from hdev import cli_runtime as runtime  # noqa: E402
from hdev import judge as judgemod  # noqa: E402

EXPORTS = (
    "CODEX_HOME='/home/user/.config/hdev/codex-accounts/acct-test-id'; export CODEX_HOME\n"
    "CODEX_SQLITE_HOME='/home/user/.codex'; export CODEX_SQLITE_HOME\n"
)


class Parse(unittest.TestCase):
    def test_export_e_unset(self):
        updates, unsets = runtime.parse_account_exports(EXPORTS)
        self.assertEqual(updates["CODEX_HOME"], "/home/user/.config/hdev/codex-accounts/acct-test-id")
        self.assertEqual(updates["CODEX_SQLITE_HOME"], "/home/user/.codex")
        self.assertEqual(unsets, set())

        updates, unsets = runtime.parse_account_exports("unset CODEX_HOME\nunset CODEX_SQLITE_HOME\n")
        self.assertEqual(updates, {})
        self.assertEqual(unsets, {"CODEX_HOME", "CODEX_SQLITE_HOME"})

    def test_ignora_linha_opaca(self):
        updates, unsets = runtime.parse_account_exports("echo rm -rf /\nFOO$BAR=1\nnot an assignment\n")
        self.assertEqual(updates, {})
        self.assertEqual(unsets, set())


class Path(unittest.TestCase):
    def test_prefixa_se_o_diretorio_existe(self):
        with TempDir() as d:
            env = runtime.prepend_ratoeira_path({"PATH": "/usr/bin"}, bin_dir=d)
            self.assertEqual(env["PATH"], d + os.pathsep + "/usr/bin")
            again = runtime.prepend_ratoeira_path(env, bin_dir=d)
            self.assertEqual(again["PATH"], env["PATH"])

    def test_sem_diretorio_nao_mexe(self):
        env = {"PATH": "/usr/bin"}
        self.assertEqual(runtime.prepend_ratoeira_path(env, bin_dir="/nao/existe/ratoeira-bin"), env)


class Wrap(unittest.TestCase):
    def test_prefixa_codex_quando_o_wrapper_existe(self):
        with TempDir() as d:
            wrapper = os.path.join(d, "conta-claude")
            with open(wrapper, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nexec \"$@\"\n")
            os.chmod(wrapper, 0o755)
            cmd = ["codex", "exec", "--sandbox", "read-only", "-"]
            self.assertEqual(runtime.wrap_command(cmd, wrapper=wrapper), [wrapper, *cmd])
            self.assertEqual(
                runtime.wrap_command("codex exec -", wrapper=wrapper),
                "%s codex exec -" % shlex.quote(wrapper),
            )
            self.assertEqual(runtime.wrap_command([wrapper, *cmd], wrapper=wrapper), [wrapper, *cmd])

    def test_nao_prefixa_stub_nem_wrapper_ausente(self):
        cmd = [sys.executable, "-c", "print(1)"]
        self.assertEqual(runtime.wrap_command(cmd, wrapper="/nao/existe/conta-claude"), cmd)
        self.assertEqual(runtime.wrap_command(["juiz-falso"], wrapper="/nao/existe/conta-claude"), ["juiz-falso"])


class Prepare(unittest.TestCase):
    def test_codex_usa_wrapper_sem_rodar_o_modulo(self):
        with TempDir() as d:
            wrapper = os.path.join(d, "conta-claude")
            with open(wrapper, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\nexec \"$@\"\n")
            os.chmod(wrapper, 0o755)
            with mock.patch.object(runtime, "apply_account_env") as apply_env:
                cmd, env = runtime.prepare_judge_call(
                    ["codex", "exec", "-"], env={"PATH": "/usr/bin"}, bin_dir=d,
                    wrapper=wrapper, script=os.path.join(d, "ausente.mjs"),
                )
            self.assertEqual(cmd[0], wrapper)
            self.assertEqual(cmd[1], "codex")
            self.assertTrue(env["PATH"].startswith(d + os.pathsep))
            apply_env.assert_not_called()

    def test_sem_wrapper_aplica_env_do_modulo(self):
        with TempDir() as d:
            script = os.path.join(d, "contas-codex.mjs")
            with open(script, "w", encoding="utf-8") as f:
                f.write("# placeholder\n")
            done = subprocess.CompletedProcess(["node"], 0, stdout=EXPORTS, stderr="")
            with mock.patch.object(runtime.subprocess, "run", return_value=done) as run:
                cmd, env = runtime.prepare_judge_call(
                    ["codex", "exec", "-"], env={"PATH": "/usr/bin"}, bin_dir=d,
                    wrapper=os.path.join(d, "sem-wrapper"), script=script,
                )
            self.assertEqual(cmd, ["codex", "exec", "-"])
            self.assertEqual(env["CODEX_HOME"], "/home/user/.config/hdev/codex-accounts/acct-test-id")
            self.assertEqual(env["CODEX_SQLITE_HOME"], "/home/user/.codex")
            run.assert_called_once()
            self.assertEqual(run.call_args[0][0], ["node", script, "env"])

    def test_respeita_CODEX_HOME_ja_definido(self):
        with TempDir() as d:
            script = os.path.join(d, "contas-codex.mjs")
            open(script, "w", encoding="utf-8").close()
            with mock.patch.object(runtime.subprocess, "run") as run:
                _cmd, env = runtime.prepare_judge_call(
                    ["codex", "exec", "-"],
                    env={"PATH": "/usr/bin", "CODEX_HOME": "/ja/definido"},
                    bin_dir=d, wrapper=os.path.join(d, "sem"), script=script,
                )
            self.assertEqual(env["CODEX_HOME"], "/ja/definido")
            run.assert_not_called()

    def test_stub_python_nao_ganha_wrapper_nem_account_env(self):
        with TempDir() as d:
            wrapper = os.path.join(d, "conta-claude")
            with open(wrapper, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
            os.chmod(wrapper, 0o755)
            with mock.patch.object(runtime, "apply_account_env") as apply_env:
                cmd, env = runtime.prepare_judge_call(
                    [sys.executable, "fake_judge.py", "pass"], env={"PATH": "/usr/bin"},
                    bin_dir=d, wrapper=wrapper, script=os.path.join(d, "x.mjs"),
                )
            self.assertEqual(cmd[0], sys.executable)
            apply_env.assert_not_called()
            self.assertNotIn("CODEX_HOME", env)


class CallJudge(unittest.TestCase):
    def test_subprocess_recebe_env_e_wrapper(self):
        with TempDir() as d:
            wrapper = os.path.join(d, "conta-claude")
            with open(wrapper, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
            os.chmod(wrapper, 0o755)
            done = subprocess.CompletedProcess([], 0, stdout='{"verdict":"unsure","reasons":["x"]}', stderr="")
            role = {"cli": "codex", "model": "gpt-5.5"}
            with mock.patch.object(judgemod.cli_runtime, "CONTA_CLAUDE", wrapper), \
                    mock.patch.object(judgemod.cli_runtime, "RATOEIRA_BIN", d), \
                    mock.patch.object(judgemod.subprocess, "run", return_value=done) as run:
                attempt = judgemod.call_judge("judge_fallback", role, "pacote", 5, d)
            self.assertEqual(attempt["verdict"], "unsure")
            args, kwargs = run.call_args
            self.assertEqual(args[0][0], wrapper)
            self.assertEqual(args[0][1], "codex")
            self.assertIn("env", kwargs)
            self.assertTrue(kwargs["env"]["PATH"].startswith(d + os.pathsep))
