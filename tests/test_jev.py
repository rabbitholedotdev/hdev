"""hdev jev: presets, chave ausente, chamada mockada, advice. Sem chave real."""
import io
import json
import os
import tempfile
import unittest
from unittest import mock

from hdev import jev
from tests.helpers import BIN, ROOT, clean_env, write
import subprocess
import sys


def _run(*args, env=None, stdin=""):
    r = subprocess.run([sys.executable, BIN, *args], capture_output=True, text=True,
                       env=env or clean_env(), cwd=ROOT, timeout=30, input=stdin)
    return r.returncode, r.stdout, r.stderr


class JevUnit(unittest.TestCase):
    def test_advice_compone_choice_e_noul(self):
        answers = {
            "worker": {"type": "choice", "choice": "sonnet", "confidence": 0.9},
            "precisa_humano": {"type": "noul", "noul": 0.12},
            "pronto_para_juiz": {"type": "noul", "noul": 0.81},
            "risco": {"type": "score", "score": 0.4},
        }
        got = jev.advice("revisar-diff", answers)
        self.assertEqual(got["worker"], "sonnet")
        self.assertIs(got["ask_human"], False)
        self.assertIs(got["run_judge"], True)
        self.assertEqual(got["risco"], 0.4)

    def test_noul_incerto_vira_none(self):
        got = jev.advice("humano", {"precisa_humano": {"type": "noul", "noul": 0.5}})
        self.assertIsNone(got["ask_human"])

    def test_ask_human_so_na_lista_fechada(self):
        alto = {"precisa_humano": {"type": "noul", "noul": 0.91}}
        fora = jev.advice("rotear", alto, state="qual o nome do arquivo?")
        self.assertIs(fora["ask_human"], False)
        self.assertIn("lista fechada", fora["recorded_decision"])
        negado = jev.advice("rotear", alto, state="não faça sudo; escolha a lib da stack")
        self.assertIs(negado["ask_human"], False)
        dentro = jev.advice("humano", alto, state="o site pediu 2FA")
        self.assertIs(dentro["ask_human"], True)
        self.assertNotIn("recorded_decision", dentro)
        sem_state = jev.advice("humano", alto)
        self.assertIs(sem_state["ask_human"], False)

    def test_presets_tem_os_quatro(self):
        self.assertEqual(set(jev.PRESETS), {"rotear", "revisar-diff", "humano", "handoff"})
        self.assertEqual(jev.PRESETS["rotear"]["worker"]["type"], "choice")
        self.assertEqual(jev.PRESETS["revisar-diff"]["risco"]["type"], "score")


class JevCli(unittest.TestCase):
    def test_dry_run_nao_precisa_de_chave(self):
        code, out, err = _run("jev", "humano", "--dry-run", "--state", "ok para seguir?")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertTrue(data["ok"])
        self.assertTrue(data["dry_run"])
        self.assertIn("precisa_humano", data["questions"])
        self.assertNotRegex(out, r"(?i)(sk-|ts_live|ops_)")

    def test_chave_ausente_sai_2_sem_eco(self):
        env = clean_env()
        env.pop("TYPESAFE_API_KEY", None)
        env["HDEV_KEY_HELPER"] = "/nao/existe/op"
        env["HDEV_JEV_REF"] = "op://CLI/TypeSafe Jev/password"
        code, out, err = _run("jev", "humano", "--state", "precisa decidir?", env=env)
        self.assertEqual(code, 2)
        data = json.loads(out)
        self.assertFalse(data["ok"])
        self.assertEqual(data["reason"], "missing_key")
        self.assertIn("op://CLI/TypeSafe Jev/password", data["hint"])
        self.assertNotRegex(out + err, r"(?i)(sk-|ts_live|ops_)")

    def test_resolve_key_nao_expoe_valor(self):
        with tempfile.TemporaryDirectory() as d:
            script = os.path.join(d, "chave")
            write(script, "#!/bin/sh\nprintf '%s' 'ts_live_TESTE_NAO_VAZADO'\n")
            os.chmod(script, 0o755)
            cfg = {"chave": script, "ref": "op://vault/item/credential"}
            key = jev.resolve_key(cfg)
            self.assertEqual(key, "ts_live_TESTE_NAO_VAZADO")

    def test_call_e_cli_com_urlopen_falso(self):
        payload = {"model": "jev-1.14.0",
                   "answers": {"precisa_humano": {"type": "noul", "noul": 0.2}},
                   "usage": {"input_tokens": 10, "output_tokens": 2}}

        class Resp:
            status = 200
            def read(self):
                return json.dumps(payload).encode()
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False

        def fake_open(req, timeout=30):
            self.assertEqual(req.full_url, jev.ENDPOINT)
            self.assertTrue(req.headers.get("Authorization", "").startswith("Bearer "))
            return Resp()

        env = clean_env(TYPESAFE_API_KEY="ts_live_TESTE_NAO_VAZADO")
        with mock.patch("hdev.jev.urllib.request.urlopen", side_effect=fake_open), \
             mock.patch.dict(os.environ, env, clear=True):
            # chama o módulo direto: a CLI importaria o patch no processo filho
            args = type("A", (), {"preset": "humano", "state": "tudo certo", "state_file": None,
                                  "model": None, "ref": None, "dry_run": False, "json": True,
                                  "root": ROOT})
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                code = jev.run(args)
            self.assertEqual(code, 0)
            data = json.loads(buf.getvalue())
            self.assertTrue(data["ok"])
            self.assertEqual(data["advice"]["ask_human"], False)
            self.assertNotIn("ts_live_TESTE_NAO_VAZADO", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
