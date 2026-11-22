"""Testes do handoff automático: transcript, guards, hook, socket mockado, dry-run."""
import hashlib
from pathlib import Path
import json
import os
import socket
import sys
import threading
import unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, clean_env, run_hook, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import handoff as h  # noqa: E402
from hdev import wsunix  # noqa: E402


def assistant_line(input_tokens, cache_read=0, cache_create=0, model="claude-opus-5-5"):
    return json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "cache_read_input_tokens": cache_read,
                "cache_creation_input_tokens": cache_create,
                "output_tokens": 10,
            },
        },
    })


def write_transcript(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


class Usage(unittest.TestCase):
    def test_soma_input_e_caches_da_ultima_assistant(self):
        with TempDir() as d:
            p = os.path.join(d, "t.jsonl")
            write_transcript(p, [
                json.dumps({"type": "user", "message": {"role": "user", "content": "oi"}}),
                assistant_line(10, 5, 1),
                assistant_line(100, 20, 30),
            ])
            usage = h.last_assistant_usage(p)
            self.assertEqual(h.usage_tokens(usage), 150)
            self.assertAlmostEqual(h.usage_ratio(usage, 300), 0.5)

    def test_arquivo_ausente_devolve_none(self):
        self.assertIsNone(h.last_assistant_usage("/no/such/transcript.jsonl"))


class Guards(unittest.TestCase):
    def test_cooldown_e_max_por_dia(self):
        cfg = {"cooldown_sec": 600, "max_per_day": 2}
        now = h.now()
        st = {"handoff_seq": 1, "last_handoff_at": h.iso(now - timedelta(seconds=60)),
              "handoffs_on": {now.date().isoformat(): 1}}
        self.assertIn("cooldown", h.guard_reason(st, cfg, now_dt=now))
        st["last_handoff_at"] = h.iso(now - timedelta(seconds=601))
        self.assertIsNone(h.guard_reason(st, cfg, now_dt=now))
        st["handoffs_on"][now.date().isoformat()] = 2
        self.assertIn("limite diário", h.guard_reason(st, cfg, now_dt=now))

    def test_upsert_progress_respeita_teto_e_substitui_secao(self):
        base = "# Progresso\n\n## Pronto\n- x\n\n## Handoff #1 (antes)\n- Estado: velho\n\n## Lições\n- a\n"
        block = h.render_block(2, "novo estado", "próximo", "decisão", "nada")
        out = h.upsert_progress(base, block, limit=2000)
        self.assertIn("Handoff #2", out)
        self.assertNotIn("Handoff #1", out)
        self.assertIn("## Lições", out)
        self.assertLessEqual(len(out), 2000)
        huge = h.render_block(3, "E" * 5000, "p", "d", "b")
        tight = h.upsert_progress("# P\n", huge, limit=80)
        self.assertLessEqual(len(tight), 80)


class Hook(unittest.TestCase):
    def test_persiste_session_e_orienta_quando_cruza(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "handoff": {"window_tokens": 200, "threshold": 0.5, "cooldown_sec": 0, "max_per_day": 8},
            }))
            tr = os.path.join(d, "t.jsonl")
            write_transcript(tr, [assistant_line(80, 20, 0)])  # 100/200 = 0.5
            ev = {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "sess-abc",
                "transcript_path": tr,
                "cwd": d,
            }
            code, err = run_hook("handoff_guard.py", ev, env=clean_env(CLAUDE_PROJECT_DIR=d), cwd=d)
            self.assertEqual(code, 0, err)
            # run_hook só devolve stderr; relê o hook com stdout
            import subprocess
            r = subprocess.run(
                [sys.executable, os.path.join(ROOT, "hooks", "handoff_guard.py")],
                input=json.dumps(ev), capture_output=True, text=True,
                env=clean_env(CLAUDE_PROJECT_DIR=d), cwd=d, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertIn("additionalContext", out["hookSpecificOutput"])
            self.assertIn("/handoff", out["hookSpecificOutput"]["additionalContext"])
            st = json.loads(Path(d, ".hdev", "state", "session.json").read_text(encoding="utf-8"))
            self.assertEqual(st["session_id"], "sess-abc")
            self.assertEqual(st["usage_tokens"], 100)

    def test_stop_bloqueia_antes_e_libera_depois_do_handoff(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "handoff": {"window_tokens": 100, "threshold": 0.5, "cooldown_sec": 0, "max_per_day": 8},
            }))
            tr = os.path.join(d, "t.jsonl")
            write_transcript(tr, [assistant_line(80)])
            ev = {"hook_event_name": "Stop", "session_id": "s1", "transcript_path": tr, "cwd": d}
            import subprocess
            r = subprocess.run(
                [sys.executable, os.path.join(ROOT, "hooks", "handoff_guard.py")],
                input=json.dumps(ev), capture_output=True, text=True,
                env=clean_env(CLAUDE_PROJECT_DIR=d), cwd=d, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(out["decision"], "block")
            st = json.loads(Path(d, ".hdev", "state", "session.json").read_text(encoding="utf-8"))
            st["allow_stop"] = True
            write(os.path.join(d, ".hdev", "state", "session.json"), json.dumps(st))
            r_legacy = subprocess.run(
                [sys.executable, os.path.join(ROOT, "hooks", "handoff_guard.py")],
                input=json.dumps(ev), capture_output=True, text=True,
                env=clean_env(CLAUDE_PROJECT_DIR=d), cwd=d, timeout=30)
            self.assertEqual(r_legacy.returncode, 0, r_legacy.stderr)
            self.assertEqual(json.loads(r_legacy.stdout)["decision"], "block")
            st = json.loads(Path(d, ".hdev", "state", "session.json").read_text(encoding="utf-8"))
            st.pop("allow_stop", None)
            st["stop_session"] = "s1"
            write(os.path.join(d, ".hdev", "state", "session.json"), json.dumps(st))
            r2 = subprocess.run(
                [sys.executable, os.path.join(ROOT, "hooks", "handoff_guard.py")],
                input=json.dumps(ev), capture_output=True, text=True,
                env=clean_env(CLAUDE_PROJECT_DIR=d), cwd=d, timeout=30)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertEqual(json.loads(r2.stdout)["decision"], "approve")

    def _cfg_stop(self, d):
        return dict(h.settings(d), window_tokens=100, threshold=0.5, cooldown_sec=0, max_per_day=8)

    def test_stop_hook_active_nao_bloqueia_de_novo(self):
        with TempDir() as d:
            tr = os.path.join(d, "t.jsonl")
            write_transcript(tr, [assistant_line(80)])
            ev = {"hook_event_name": "Stop", "session_id": "s1", "transcript_path": tr, "cwd": d}
            out, _st = h.hook_decide(d, ev, self._cfg_stop(d))
            self.assertEqual(out["decision"], "block")
            out, _st = h.hook_decide(d, dict(ev, stop_hook_active=True), self._cfg_stop(d))
            self.assertIsNone(out)

    def test_stop_com_unidade_fechada_nao_bloqueia(self):
        with TempDir() as d:
            tr = os.path.join(d, "t.jsonl")
            write_transcript(tr, [assistant_line(80)])
            ev = {"hook_event_name": "Stop", "session_id": "s1", "transcript_path": tr, "cwd": d}
            unit = os.path.join(d, ".hdev", "state", "unit.json")
            write(unit, json.dumps({"id": "X-1", "status": "open"}))
            out, _st = h.hook_decide(d, ev, self._cfg_stop(d))
            self.assertEqual(out["decision"], "block")
            write(unit, json.dumps({"id": "X-1", "status": "closed"}))
            out, _st = h.hook_decide(d, ev, self._cfg_stop(d))
            self.assertIsNone(out)
            # Fora do Stop o aviso de handoff continua.
            out, _st = h.hook_decide(d, dict(ev, hook_event_name="UserPromptSubmit"), self._cfg_stop(d))
            self.assertIn("additionalContext", out["hookSpecificOutput"])

    def _cfg_modelo(self, d):
        write(os.path.join(d, ".hdev", "config.json"), json.dumps({
            "handoff": {"window_tokens": 200, "window_by_model": {"claude-opus-5-5": 1000},
                        "threshold": 0.5, "cooldown_sec": 0, "max_per_day": 8},
        }))

    def test_janela_por_modelo(self):
        with TempDir() as d:
            self._cfg_modelo(d)
            tr = os.path.join(d, "t.jsonl")
            ev = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "transcript_path": tr, "cwd": d}
            with mock.patch.dict(os.environ, clean_env(), clear=True):
                write_transcript(tr, [assistant_line(400)])  # 400/1000 = 0.4
                out, st = h.hook_decide(d, ev, h.settings(d))
                self.assertIsNone(out)
                self.assertAlmostEqual(st["usage_ratio"], 0.4)
                write_transcript(tr, [assistant_line(500)])  # 0.5: orienta
                out, _st = h.hook_decide(d, ev, h.settings(d))
                self.assertIn("additionalContext", out["hookSpecificOutput"])
                # Modelo fora do mapa cai em window_tokens: 150/200 = 0.75.
                write_transcript(tr, [assistant_line(150, model="claude-outro")])
                out, st = h.hook_decide(d, ev, h.settings(d))
                self.assertAlmostEqual(st["usage_ratio"], 0.75)
                self.assertIn("additionalContext", out["hookSpecificOutput"])

    def test_env_janela_ganha_do_mapa(self):
        with TempDir() as d:
            self._cfg_modelo(d)
            tr = os.path.join(d, "t.jsonl")
            write_transcript(tr, [assistant_line(80)])  # 80/100 com o env
            ev = {"hook_event_name": "UserPromptSubmit", "session_id": "s1", "transcript_path": tr, "cwd": d}
            with mock.patch.dict(os.environ, clean_env(HDEV_HANDOFF_WINDOW="100"), clear=True):
                cfg = h.settings(d)
                out, st = h.hook_decide(d, ev, cfg)
            self.assertEqual(cfg["window_by_model"], {})
            self.assertAlmostEqual(st["usage_ratio"], 0.8)
            self.assertIn("additionalContext", out["hookSpecificOutput"])

    def test_abaixo_do_limiar_silencia(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "handoff": {"window_tokens": 1000, "threshold": 0.5},
            }))
            tr = os.path.join(d, "t.jsonl")
            write_transcript(tr, [assistant_line(10)])
            ev = {"hook_event_name": "PostToolUse", "session_id": "s1", "transcript_path": tr, "cwd": d}
            import subprocess
            r = subprocess.run(
                [sys.executable, os.path.join(ROOT, "hooks", "handoff_guard.py")],
                input=json.dumps(ev), capture_output=True, text=True,
                env=clean_env(CLAUDE_PROJECT_DIR=d), cwd=d, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "")


class FakeServer(threading.Thread):
    """Servidor Unix+WebSocket mínimo que responde listar/abrir/nova."""

    def __init__(self, path, handler):
        super().__init__(daemon=True)
        self.path = path
        self.handler = handler
        self.error = None
        self.ready = threading.Event()
        self._sock = None

    def run(self):
        try:
            if os.path.exists(self.path):
                os.unlink(self.path)
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._sock = srv
            srv.bind(self.path)
            srv.listen(1)
            srv.settimeout(5)
            self.ready.set()
            conn, _ = srv.accept()
            conn.settimeout(5)
            self._serve(conn)
            conn.close()
            srv.close()
        except Exception as e:
            self.error = e
            self.ready.set()

    def _serve(self, conn):
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk
        key = None
        for line in data.split(b"\r\n"):
            if line.lower().startswith(b"sec-websocket-key:"):
                key = line.split(b":", 1)[1].strip().decode("ascii")
        if not key:
            conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return
        acc = wsunix.base64.b64encode(hashlib.sha1((key + wsunix.GUID).encode("ascii")).digest())
        conn.sendall(
            b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
            b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + acc + b"\r\n\r\n"
        )
        # vários pedidos na mesma conexão? o cliente atual abre e fecha por request.
        # Este fake atende um pedido e acaba; o teste usa request_fn in-process em outros casos.
        opcode, payload = wsunix.decode_frame(conn)
        obj = json.loads(payload.decode("utf-8"))
        resp = self.handler(obj)
        conn.sendall(wsunix.encode_frame(json.dumps(resp), opcode=wsunix.OP_TEXT, masked=False))


class WsUnix(unittest.TestCase):
    def test_pedido_e_resposta_na_mesma_id(self):
        with TempDir() as d:
            sock_path = os.path.join(d, "agentes.sock")

            def handler(msg):
                self.assertEqual(msg["op"], "nova")
                self.assertEqual(msg["id"], 7)
                return {"t": "resposta", "id": 7, "ok": True, "dados": {"sessao": "new-1", "agente": "claude"}}

            srv = FakeServer(sock_path, handler)
            srv.start()
            self.assertTrue(srv.ready.wait(3), srv.error)
            resp = wsunix.request(sock_path, {"id": 7, "op": "nova", "agente": "claude", "cwd": d, "texto": "oi"},
                                  timeout=5)
            srv.join(3)
            self.assertIsNone(srv.error)
            self.assertTrue(resp["ok"])
            self.assertEqual(resp["dados"]["sessao"], "new-1")


class Command(unittest.TestCase):
    def test_dry_run_mostra_payload_sem_enviar(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "roles": {"planner": {"cli": "claude", "model": "claude-opus-5-5"}},
                "handoff": {"window_tokens": 200000, "threshold": 0.5, "socket": "/no/such.sock"},
            }))
            write(os.path.join(d, ".hdev", "state", "session.json"), json.dumps({
                "session_id": "old-sess", "agente": "claude", "cwd": d, "conta": "pessoal:x",
                "opcoes": {"model": "claude-opus-5-5", "effort": "high"},
            }))
            os.makedirs(os.path.join(d, "docs"), exist_ok=True)
            write(os.path.join(d, "docs", "progress.md"), "# Progresso\n")
            result = h.run_handoff(d, estado="spec pronta", proximo="implementar item 1",
                                   decisoes="TDD", bloqueios="nenhum", dry_run=True, use_jev=False)
            self.assertTrue(result["ok"])
            self.assertTrue(result["dry_run"])
            payload = result["payload"]
            self.assertEqual(payload["op"], "nova")
            self.assertEqual(payload["agente"], "claude")
            self.assertEqual(payload["cwd"], d)
            self.assertEqual(payload["conta"], "pessoal:x")
            self.assertEqual(payload["opcoes"].get("mode"), "auto")
            self.assertIn("handoff #", payload["texto"])
            # dry-run não grava progress nem mexe no seq
            self.assertNotIn("Handoff #", Path(d, "docs", "progress.md").read_text(encoding="utf-8"))

    def test_envia_nova_no_socket_mockado_e_nao_apaga(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "handoff": {"cooldown_sec": 0, "max_per_day": 8, "jev": False},
            }))
            write(os.path.join(d, ".hdev", "state", "session.json"), json.dumps({
                "session_id": "old-sess", "agente": "claude", "cwd": d,
            }))
            os.makedirs(os.path.join(d, "docs"), exist_ok=True)
            write(os.path.join(d, "docs", "progress.md"), "# Progresso\n")
            seen = []

            def request_fn(msg, timeout=30):
                seen.append(msg)
                op = msg.get("op")
                mid = msg.get("id")
                if op == "listar":
                    return {"t": "resposta", "id": mid, "ok": True,
                            "dados": [{"agente": "claude", "sessao": "old-sess", "cwd": d}]}
                if op == "abrir":
                    return {"t": "resposta", "id": mid, "ok": True, "dados": {
                        "agente": "claude", "sessao": "old-sess", "cwd": d, "conta": None,
                        "config": {"configOptions": [
                            {"id": "model", "currentValue": "claude-opus-5-5"},
                            {"id": "effort", "currentValue": "high"},
                        ], "modes": {"currentModeId": "auto"}},
                    }}
                if op == "nova":
                    self.assertNotIn("conversa-apagar", json.dumps(msg))
                    self.assertEqual(msg["opcoes"].get("mode"), "auto")
                    return {"t": "resposta", "id": mid, "ok": True,
                            "dados": {"agente": "claude", "sessao": "new-sess", "cwd": d}}
                return {"t": "resposta", "id": mid, "ok": False, "erro": "op desconhecida"}

            result = h.run_handoff(d, estado="ok", proximo="seguir", dry_run=False, use_jev=False,
                                   request_fn=request_fn)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["new_session"], "new-sess")
            self.assertTrue(result["stop_old"])
            ops = [m["op"] for m in seen]
            self.assertIn("nova", ops)
            self.assertNotIn("conversa-apagar", ops)
            st = json.loads(Path(d, ".hdev", "state", "session.json").read_text(encoding="utf-8"))
            self.assertEqual(st["last_new_session_id"], "new-sess")
            self.assertEqual(st["stop_session"], "old-sess")
            self.assertNotIn("allow_stop", st)
            self.assertEqual(st["handoff_seq"], 1)
            prog = Path(d, "docs", "progress.md").read_text(encoding="utf-8")
            self.assertIn("Handoff #1", prog)
            self.assertIn("seguir", prog)

    def test_cooldown_bloqueia_envio(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "handoff": {"cooldown_sec": 600, "max_per_day": 8, "jev": False},
            }))
            write(os.path.join(d, ".hdev", "state", "session.json"), json.dumps({
                "handoff_seq": 1, "last_handoff_at": h.iso(),
            }))
            called = []
            result = h.run_handoff(d, dry_run=False, use_jev=False,
                                   request_fn=lambda msg, **kw: called.append(msg) or {"ok": True})
            self.assertFalse(result["ok"])
            self.assertIn("cooldown", result["error"])
            self.assertEqual(called, [])


class JevStop(unittest.TestCase):
    def _answers(self, humano, unidade=0.95):
        return {"answers": {
            "precisa_humano": {"type": "noul", "noul": humano},
            "unidade_fechada": {"type": "noul", "noul": unidade},
        }}

    def test_fora_da_lista_registra_e_segue(self):
        with TempDir() as d:
            with mock.patch("hdev.handoff.jevmod.resolve_key", return_value="k"), \
                 mock.patch("hdev.handoff.jevmod.call_systemone", return_value=self._answers(0.92)):
                result = h.run_handoff(d, estado="escolher nome do arquivo", proximo="criar o arquivo",
                                       skip_socket=True)
            self.assertTrue(result["ok"], result)
            self.assertIn("decisão registrada", Path(d, "docs", "progress.md").read_text(encoding="utf-8"))
            text = Path(d, "docs", "decisions.md").read_text(encoding="utf-8")
            self.assertIn("lista fechada", text)
            self.assertFalse(Path(d, ".hdev", "state", "parei").exists())

    def test_lista_fechada_grava_parei_e_nao_abre_sessao(self):
        with TempDir() as d:
            def boom(*_a, **_k):
                raise AssertionError("socket")
            with mock.patch("hdev.handoff.jevmod.resolve_key", return_value="k"), \
                 mock.patch("hdev.handoff.jevmod.call_systemone", return_value=self._answers(0.96)):
                result = h.run_handoff(d, estado="pediram 2FA", proximo="repetir depois do código",
                                       request_fn=boom)
            self.assertFalse(result["ok"])
            self.assertIn("PAREI:", result["error"])
            self.assertIn("2FA", result["error"])
            self.assertTrue(result.get("parei"))
            self.assertTrue(Path(d, ".hdev", "state", "parei").is_file())


class Abertura(unittest.TestCase):
    def test_texto_leva_brief_permissao_estado_e_o_mesmo_modelo(self):
        with TempDir() as d:
            write(os.path.join(d, ".hdev", "config.json"), json.dumps({
                "handoff": {"cooldown_sec": 0, "max_per_day": 8, "jev": False, "mode": "auto"},
                "roles": {"planner": {"cli": "claude", "model": "claude-sonnet-5-5"},
                          "executor": {"cli": "claude", "model": "claude-sonnet-5-5"}},
                "stop": {"standing_ok": ["publicar"]},
            }))
            write(os.path.join(d, ".hdev", "state", "unit.json"), json.dumps({
                "id": "alfa", "status": "open", "next": "escrever o teste",
                "plan": "work/alfa/plan.md", "brief": "work/alfa/brief.md",
                "blocked_on": "", "parked": False,
            }))
            tr = os.path.join(d, "t.jsonl")
            write_transcript(tr, [assistant_line(10, model="claude-opus-5-5")])
            write(os.path.join(d, ".hdev", "state", "session.json"), json.dumps({
                "session_id": "old", "transcript_path": tr, "cwd": d,
            }))
            write(os.path.join(d, "docs", "progress.md"), "# Progresso\n")
            result = h.run_handoff(d, estado="no meio", proximo="escrever o teste",
                                   dry_run=True, use_jev=False)
            self.assertTrue(result["ok"], result)
            texto = result["payload"]["texto"]
            self.assertIn("work/alfa/plan.md", texto)
            self.assertIn("work/alfa/brief.md", texto)
            self.assertIn("publicar", texto)
            self.assertIn("open", texto)
            self.assertIn("escrever o teste", texto)
            self.assertIn("claude-opus-5-5", texto)
            self.assertNotIn("claude-sonnet-5-5", texto)
            self.assertIn("handoff #", texto)
            self.assertNotIn("Leia docs/progress.md e docs/decisions.md", texto)
            self.assertEqual(result["payload"]["opcoes"].get("model"), "claude-opus-5-5")


if __name__ == "__main__":
    unittest.main()
