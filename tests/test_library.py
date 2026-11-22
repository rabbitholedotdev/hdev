"""Biblioteca: pull, reflect, pontos e ciclo. Sem rede e sem valor volátil no log."""
import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, TempDir, git, hdev, read_json, write  # noqa: E402

sys.path.insert(0, ROOT)
from hdev import check as checkmod  # noqa: E402
from hdev import xray  # noqa: E402
from hdev.library import life, pull, reflect, store, text  # noqa: E402

def text_of(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


BODY = "quando o teste do check falha no aceite, faça o conserto mínimo, porque o portão precisa passar.\n"
QUERY = "teste do check no aceite"
SIMILAR_A = (
    "quando a chave de cache do juiz inclui saída volátil de teste, "
    "faça a chave só com a árvore, porque a saída muda"
)
SIMILAR_B = (
    "quando a chave de cache do juiz inclui saída volátil, "
    "faça a chave só com a árvore estável, porque a saída muda entre corridas"
)
OTHER = (
    "quando a prova precisa ser lida pelo juiz, "
    "faça o arquivo na pasta de evidência da unidade, porque fora dela o juiz não lê"
)


def lesson(root, iid, when=QUERY, body=BODY, **kw):
    rel = "library/lessons/%s.md" % iid
    item = {
        "id": iid,
        "kind": kw.get("kind", "lesson"),
        "title": kw.get("title", "titulo " + iid),
        "when_to_use": when,
        "not_for": kw.get("not_for", ""),
        "body_path": rel if kw.get("kind", "lesson") != "skill" else "library/skills/%s.md" % iid,
        "scope": kw.get("scope", "global"),
        "tags": kw.get("tags", ["teste", "check", "aceite"]),
        "evidence": kw.get("evidence", []),
        "wins": kw.get("wins", 0),
        "losses": kw.get("losses", 0),
        "uses": kw.get("uses", 0),
        "created": kw.get("created", "2026-01-01"),
        "last_used": kw.get("last_used", "2026-06-01"),
        "status": kw.get("status", "active"),
        "source": "operator",
        "generalization": kw.get("generalization", "checked"),
    }
    if kw.get("kind") == "script":
        item["body_path"] = "library/scripts/%s" % kw["name"]
        item["test"] = kw.get("test")
    if "retired_on" in kw:
        item["retired_on"] = kw["retired_on"]
    store.write_body(root, item["body_path"], body if body.endswith("\n") else body + "\n")
    item["_root"] = root
    return item


def save(root, items):
    store.save_local(root, items)


class Rank(unittest.TestCase):
    def test_bm25_poe_o_mais_parecido_na_frente(self):
        with TempDir() as root:
            high = lesson(root, "lesson-0002", when="alpha beta cache alpha beta cache")
            low = lesson(root, "lesson-0001", when="alpha")
            picked = pull.select([high, low], "alpha beta cache", repo="demo")
            self.assertEqual([row["id"] for row in picked], ["lesson-0002", "lesson-0001"])
            self.assertGreater(picked[0]["score"], picked[1]["score"])

    def test_semelhanca_separa_o_limiar(self):
        self.assertGreaterEqual(text.similarity(SIMILAR_A, SIMILAR_B), text.DEDUP_SIM)
        self.assertLess(text.similarity(SIMILAR_A, OTHER), text.DEDUP_SIM)

    def test_escopo_e_not_for(self):
        with TempDir() as root:
            write(os.path.join(root, ".hdev", "config.json"), json.dumps({"repo": "demo", "area": "lab"}))
            items = [
                lesson(root, "lesson-0001", scope="global"),
                lesson(root, "lesson-0002", scope="repo:demo"),
                lesson(root, "lesson-0003", scope="repo:outro"),
                lesson(root, "lesson-0004", scope="area:lab"),
                lesson(root, "lesson-0005", not_for="browser visual"),
                lesson(root, "lesson-0006", status="retired"),
            ]
            query = QUERY + " browser visual"
            picked = pull.select(items, query, repo="demo", area="lab")
            ids = [row["id"] for row in picked]
            self.assertIn("lesson-0001", ids)
            self.assertIn("lesson-0002", ids)
            self.assertIn("lesson-0004", ids)
            self.assertNotIn("lesson-0003", ids)
            self.assertNotIn("lesson-0005", ids)
            self.assertNotIn("lesson-0006", ids)
            kept = pull.select(items, QUERY, repo="demo", area="lab")
            self.assertIn("lesson-0005", [row["id"] for row in kept])

    def test_not_for_vazio_nao_corta_e_metade_corta(self):
        self.assertFalse(text.blocked_by_not_for("", "browser visual"))
        self.assertTrue(text.blocked_by_not_for("browser visual", "so browser aqui"))
        self.assertFalse(text.blocked_by_not_for("browser visual", "juiz cache"))

    def test_orcamento_e_teto_de_skill(self):
        with TempDir() as root:
            huge = "x" * 400
            small = "oi\n"
            items = [
                lesson(root, "lesson-0001", body=huge),
                lesson(root, "lesson-0002", body=small),
                lesson(root, "lesson-0003", kind="skill", body="skill um\n"),
                lesson(root, "lesson-0004", kind="skill", body="skill dois\n"),
                lesson(root, "lesson-0005", kind="skill", body="skill tres\n"),
            ]
            picked = pull.select(items, QUERY, k=5, budget=5, repo="demo")
            ids = [row["id"] for row in picked]
            self.assertNotIn("lesson-0001", ids)
            self.assertIn("lesson-0002", ids)
            self.assertEqual(sum(1 for row in picked if row["kind"] == "skill"), 2)
            self.assertLessEqual(pull.lesson_tokens(picked), 5)
            self.assertLessEqual(len(picked), 5)

    def test_candidata_ocupa_no_maximo_duas_vagas(self):
        with TempDir() as root:
            items = [lesson(root, "lesson-%04d" % n, status="active" if n <= 3 else "candidate") for n in range(1, 8)]
            picked = pull.select(items, QUERY, k=5, budget=1500, repo="demo")
            ids = [row["id"] for row in picked]
            self.assertEqual(ids, ["lesson-0001", "lesson-0002", "lesson-0003", "lesson-0004", "lesson-0005"])
            only = [lesson(root, "lesson-1%03d" % n, status="candidate") for n in range(1, 5)]
            picked = pull.select(only, QUERY, k=5, budget=1500, repo="demo")
            self.assertEqual(len(picked), 2)

    def test_corte_em_k(self):
        with TempDir() as root:
            items = [lesson(root, "lesson-%04d" % n) for n in range(1, 9)]
            picked = pull.select(items, QUERY, k=5, budget=1500, repo="demo")
            self.assertEqual(len(picked), 5)
            self.assertEqual([row["id"] for row in picked], ["lesson-%04d" % n for n in range(1, 6)])

    def test_sintoma_poe_recorrencia_na_frente(self):
        with TempDir() as root:
            rare = lesson(root, "lesson-0001", when="cache", losses=1, uses=1)
            often = lesson(root, "lesson-0002", when="cache cache cache cache cache")
            normal = pull.select([rare, often], "cache", repo="demo")
            self.assertEqual(normal[0]["id"], "lesson-0002")
            symptom = pull.select([rare, often], "cache", symptom=True, repo="demo")
            self.assertEqual([row["id"] for row in symptom], ["lesson-0001", "lesson-0002"])

    def test_brief_so_pergunta(self):
        with TempDir() as root:
            items = [
                lesson(root, "lesson-0001", tags=["pergunta", "teste"]),
                lesson(root, "lesson-0002", tags=["teste", "check"]),
            ]
            picked = pull.select(items, QUERY, tag="pergunta", repo="demo")
            self.assertEqual([row["id"] for row in picked], ["lesson-0001"])


class ReflectCase(unittest.TestCase):
    def test_corta_caminho_sha_id_e_numero_e_recusa_forma_ruim(self):
        with TempDir() as root:
            os.makedirs(os.path.join(root, "work", "v2-pr10-graphify"))
            raw = (
                "quando a chave de cache do juiz inclui a saída 389 do teste em "
                "work/v2-pr10-graphify/evidence/aceite.md no commit 97ad787, "
                "faça a chave só com a árvore, porque a saída muda."
            )
            results = reflect.add_items(root, "v2-pr10-graphify", [{
                "kind": "lesson", "title": "cache do juiz", "when_to_use": "quando a chave de cache muda",
                "not_for": "video juridico", "body": raw, "tags": ["juiz", "cache"], "scope": "global",
            }], offline=True, today=datetime.date(2026, 11, 20))
            self.assertEqual(results[0]["action"], "gravado")
            body = store.read_body(store.load_local(root)[0])
            self.assertNotIn("work/", body)
            self.assertNotIn("97ad787", body)
            self.assertNotIn("389", body)
            self.assertNotIn("v2-pr10-graphify", body)
            self.assertTrue(text.lesson_shape_ok(body))
            bad = reflect.add_items(root, "v2-pr10-graphify", [{
                "kind": "lesson", "title": "ruim", "when_to_use": "caso ruim",
                "body": "quando work/foo/bar.md, faça 12, porque 97ad787",
            }], offline=True, today=datetime.date(2026, 11, 20))
            self.assertEqual(bad[0]["action"], "recusado")

    def test_dedup_junta_evidencia(self):
        with TempDir() as root:
            os.makedirs(os.path.join(root, "work", "demo"))
            first = reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "cache", "when_to_use": "chave de cache do juiz",
                "body": SIMILAR_A, "evidence": [{"unit": "alpha", "run": "fechar", "delta": {"pass": 1}}],
            }], offline=True, today=datetime.date(2026, 11, 20))
            second = reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "cache", "when_to_use": "chave de cache do juiz",
                "body": SIMILAR_B, "evidence": [{"unit": "beta", "run": "fechar", "delta": {"pass": 1}}],
            }], offline=True, today=datetime.date(2026, 11, 20))
            self.assertEqual(first[0]["action"], "gravado")
            self.assertEqual(second[0]["action"], "juntado")
            self.assertEqual(second[0]["id"], first[0]["id"])
            items = store.load_local(root)
            self.assertEqual(len(items), 1)
            units = [ev["unit"] for ev in items[0]["evidence"]]
            self.assertEqual(units, ["alpha", "beta"])
            kept = reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "prova", "when_to_use": "prova para o juiz",
                "body": OTHER,
            }], offline=True, today=datetime.date(2026, 11, 20))
            self.assertEqual(kept[0]["action"], "gravado")
            self.assertEqual(len(store.load_local(root)), 2)

    def _fake_root(self, verdict):
        root = self._tmp
        script = os.path.join(root, "fake_judge.py")
        marker = os.path.join(root, "called.txt")
        write(script, "import pathlib, sys\n"
                      "pathlib.Path(sys.argv[2]).write_text('1')\n"
                      "print('{\"verdict\":\"' + sys.argv[1] + '\",\"reasons\":[\"x\"]}')\n")
        write(os.path.join(root, ".hdev", "config.json"), json.dumps({
            "roles": {
                "executor": {"cli": "claude", "model": "claude-opus-5-5"},
                "judge": {"cli": "grok", "model": "grok-4.7",
                          "command": [sys.executable, script, verdict, marker]},
            },
            "judge": {"timeout": 15},
        }))
        os.makedirs(os.path.join(root, "work", "demo"))
        return root, marker

    def test_segundo_modelo_descarta_e_offline_fica_pending(self):
        self._tmp_ctx = TempDir()
        self._tmp = self._tmp_ctx.__enter__()
        try:
            root, marker = self._fake_root("fail")
            dropped = reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "cache", "when_to_use": "chave de cache",
                "body": OTHER,
            }], offline=False, today=datetime.date(2026, 11, 20))
            self.assertEqual(dropped[0]["action"], "descartado")
            self.assertEqual(store.load_local(root), [])
            self.assertTrue(os.path.isfile(marker))
            os.remove(marker)
            pending = reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "cache", "when_to_use": "chave de cache",
                "body": OTHER,
            }], offline=True, today=datetime.date(2026, 11, 20))
            self.assertEqual(pending[0]["action"], "gravado")
            self.assertFalse(os.path.isfile(marker))
            self.assertEqual(store.load_local(root)[0]["generalization"], "pending")
        finally:
            self._tmp_ctx.__exit__(None, None, None)

    def test_segundo_modelo_ok_marca_checked_e_cli_ausente_fica_pending(self):
        self._tmp_ctx = TempDir()
        self._tmp = self._tmp_ctx.__enter__()
        try:
            root, _marker = self._fake_root("pass")
            ok = reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "prova", "when_to_use": "prova para o juiz",
                "body": OTHER,
            }], offline=False, today=datetime.date(2026, 11, 20))
            self.assertEqual(ok[0]["reason"], "checked")
            cfg = read_json(os.path.join(root, ".hdev", "config.json"))
            cfg["roles"]["judge"]["command"] = ["hdev-cli-ausente-xyz"]
            write(os.path.join(root, ".hdev", "config.json"), json.dumps(cfg))
            missing = reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "parada", "when_to_use": "lista fechada",
                "body": "quando o motivo não está na lista fechada, faça o padrão e uma linha de decisão, porque parar fora da lista segura a sessão.",
            }], offline=False, today=datetime.date(2026, 11, 20))
            self.assertEqual(missing[0]["action"], "gravado")
            stored = [item for item in store.load_local(root) if item["id"] == missing[0]["id"]][0]
            self.assertEqual(stored["generalization"], "pending")
        finally:
            self._tmp_ctx.__exit__(None, None, None)

    def test_script_sem_teste_nao_entra(self):
        with TempDir() as root:
            os.makedirs(os.path.join(root, "work", "demo"))
            refused = reflect.add_items(root, "demo", [{
                "kind": "script", "name": "cache-key.py", "title": "chave",
                "when_to_use": "quando a chave muda", "body": "print('ok')\n",
            }], offline=True, today=datetime.date(2026, 11, 20))
            self.assertEqual(refused[0]["action"], "recusado")
            write(os.path.join(root, "tests", "test_cache_key.py"), "def test_ok():\n    assert 'cache-key.py'\n")
            stored = reflect.add_items(root, "demo", [{
                "kind": "script", "name": "cache-key.py", "title": "chave",
                "when_to_use": "quando a chave muda", "body": "print('ok')\n",
                "test": "tests/test_cache_key.py",
            }], offline=True, today=datetime.date(2026, 11, 20))
            self.assertEqual(stored[0]["action"], "gravado")

    def test_digest_nao_eco_sha_do_juiz(self):
        with TempDir() as root:
            write(os.path.join(root, "work", "demo", "plan.md"), "# Plano — demo\n")
            write(os.path.join(root, "work", "demo", "evidence", "nota.md"), "primeira linha\n")
            write(os.path.join(root, ".hdev", "state", "parei"),
                  "PAREI: pediram 2FA | próximo: seguir\n")
            write(os.path.join(root, ".hdev", "runs", "judge-20200101T000000Z.json"), json.dumps({
                "verdict": "pass", "plan": "work/demo/plan.md", "head_sha": "abc1234dead",
            }))
            code, out = hdev("reflect", "--unit", "demo", "--offline", "--root", root)
            self.assertEqual(code, 0)
            self.assertIn("unidade: demo", out)
            self.assertIn("juiz: pass", out)
            self.assertIn("PAREI:", out)
            self.assertNotIn("abc1234dead", out)

    def test_release_e_so_leitura(self):
        with TempDir() as root:
            os.makedirs(os.path.join(root, "work", "demo"))
            release = os.path.join(root, ".harnessdev")
            global_item = lesson(release, "lesson-0099", scope="global")
            store.save_local(release, [global_item])
            before = text_of(store.index_path(release))
            reflect.add_items(root, "demo", [{
                "kind": "lesson", "title": "local", "when_to_use": "caso local",
                "body": OTHER,
            }], offline=True, today=datetime.date(2026, 11, 20))
            after = text_of(store.index_path(release))
            self.assertEqual(before, after)
            _picked, payload = pull.pull(root, QUERY, unit="demo")
            self.assertIn("lesson-0099", payload["ids"])


class Life(unittest.TestCase):
    def test_formula(self):
        today = datetime.date(2026, 1, 1)
        fresh = {"wins": 0, "losses": 0, "created": "2026-01-01", "last_used": None}
        self.assertAlmostEqual(life.score(fresh, today), 0.5)
        later = datetime.date(2026, 1, 1) + datetime.timedelta(days=60)
        self.assertAlmostEqual(life.score(fresh, later), 0.25)
        wins = {"wins": 2, "losses": 0, "created": "2026-01-01", "last_used": "2026-01-01"}
        self.assertAlmostEqual(life.score(wins, today), 0.75)
        mixed = {"wins": 3, "losses": 1, "created": "2026-01-01", "last_used": "2026-01-01"}
        self.assertAlmostEqual(life.score(mixed, today), 4.0 / 6.0)

    def _active(self, iid, **kw):
        item = {
            "id": iid, "kind": "lesson", "title": iid, "when_to_use": "uso", "not_for": "",
            "body_path": "library/lessons/%s.md" % iid, "scope": "global", "tags": [],
            "evidence": kw.get("evidence", []), "wins": kw.get("wins", 0), "losses": kw.get("losses", 0),
            "uses": kw.get("uses", 0), "created": "2026-01-01", "last_used": kw.get("last_used", "2026-06-01"),
            "status": kw.get("status", "active"), "source": "operator",
            "generalization": kw.get("generalization", "checked"),
        }
        if "retired_on" in kw:
            item["retired_on"] = kw["retired_on"]
        return item

    def test_transicoes(self):
        today = datetime.date(2026, 6, 1)
        two = self._active("lesson-0001", status="candidate", evidence=[
            {"unit": "alpha", "run": "fechar", "delta": {"pass": 1}},
            {"unit": "beta", "run": "fechar", "delta": {"pass": 1}},
        ])
        same = self._active("lesson-0002", status="candidate", evidence=[
            {"unit": "alpha", "run": "fechar", "delta": {"pass": 1}},
            {"unit": "alpha", "run": "fechar", "delta": {"pass": 1}},
        ])
        pending = self._active("lesson-0003", status="candidate", generalization="pending", evidence=[
            {"unit": "alpha", "run": "fechar", "delta": {"pass": 1}},
            {"unit": "beta", "run": "fechar", "delta": {"pass": 1}},
        ])
        probe = self._active("lesson-0004", status="candidate", evidence=[
            {"unit": "alpha", "run": "probe", "delta": {"pass": 1}},
        ])
        low = self._active("lesson-0005", wins=0, losses=4, uses=4, last_used="2026-06-01")
        young = self._active("lesson-0006", wins=0, losses=3, uses=3, last_used="2026-06-01")
        stale_day = (today - datetime.timedelta(days=90)).isoformat()
        fresh_day = (today - datetime.timedelta(days=89)).isoformat()
        stale = self._active("lesson-0007", uses=1, last_used=stale_day)
        fresh = self._active("lesson-0008", uses=1, last_used=fresh_day)
        core = self._active("lesson-0009", status="core", wins=0, losses=9, uses=9, last_used="2020-01-01")
        eligible = self._active("lesson-0010", status="active", wins=5, losses=1, uses=6)
        kept, _removed = life.tidy_items(
            [two, same, pending, probe, low, young, stale, fresh, core, eligible], today)
        by_id = {item["id"]: item for item in kept}
        self.assertEqual(by_id["lesson-0001"]["status"], "active")
        self.assertEqual(by_id["lesson-0002"]["status"], "candidate")
        self.assertEqual(by_id["lesson-0003"]["status"], "candidate")
        self.assertEqual(by_id["lesson-0004"]["status"], "active")
        self.assertEqual(by_id["lesson-0005"]["status"], "retired")
        self.assertEqual(by_id["lesson-0006"]["status"], "active")
        self.assertEqual(by_id["lesson-0007"]["status"], "retired")
        self.assertEqual(by_id["lesson-0008"]["status"], "active")
        self.assertEqual(by_id["lesson-0009"]["status"], "core")
        self.assertEqual(by_id["lesson-0010"]["status"], "active")
        self.assertTrue(life.core_eligible(by_id["lesson-0010"]))
        self.assertFalse(life.core_eligible(self._active("lesson-0011", wins=5, losses=3)))
        self.assertFalse(life.core_eligible(self._active("lesson-0012", wins=4, losses=0)))

    def test_cap_aposenta_o_pior_e_core_nao_nasce_sozinho(self):
        today = datetime.date(2026, 6, 1)
        items = [self._active("lesson-%04d" % n, uses=0, losses=0, wins=0, last_used="2026-06-01")
                 for n in range(1, 62)]
        items[0]["uses"] = 3
        items[0]["losses"] = 3
        kept, _removed = life.tidy_items(items, today)
        by_id = {item["id"]: item["status"] for item in kept}
        self.assertEqual(by_id["lesson-0001"], "retired")
        self.assertEqual(sum(1 for status in by_id.values() if status == "active"), 60)
        self.assertNotIn("core", by_id.values())

    def test_aposentada_some_depois_de_180_dias(self):
        with TempDir() as root:
            origin = datetime.date(2026, 1, 1)
            item = lesson(root, "lesson-0001", status="retired", retired_on=origin.isoformat())
            save(root, [item])
            life.tidy_root(root, origin + datetime.timedelta(days=179))
            self.assertEqual(len(store.load_local(root)), 1)
            self.assertTrue(os.path.isfile(store.body_path(item)))
            first = life.tidy_root(root, origin + datetime.timedelta(days=180))
            self.assertEqual(first["deleted"], 1)
            self.assertEqual(store.load_local(root), [])
            self.assertFalse(os.path.isfile(os.path.join(root, item["body_path"])))
            second = life.tidy_root(root, datetime.date(2026, 6, 30))
            self.assertEqual(second, {"promoted": 0, "retired": 0, "deleted": 0})

    def test_tidy_idempotente(self):
        with TempDir() as root:
            save(root, [lesson(root, "lesson-0001", status="candidate", generalization="pending")])
            code, first = hdev("library", "tidy", "--today", "2026-06-01", "--root", root)
            self.assertEqual(code, 0)
            blob = text_of(store.index_path(root))
            code, second = hdev("library", "tidy", "--today", "2026-06-01", "--root", root)
            self.assertEqual(code, 0)
            self.assertEqual(first, second)
            self.assertEqual(text_of(store.index_path(root)), blob)

    def test_vitoria_e_derrota_e_repetir_nao_soma(self):
        with TempDir() as root:
            item = lesson(root, "lesson-0001", status="candidate", generalization="checked",
                          wins=0, losses=0, uses=0, last_used=None)
            save(root, [item])
            write(os.path.join(root, "work", "demo", "pulled.json"), json.dumps({"ids": ["lesson-0001"]}))
            write(os.path.join(root, ".hdev", "runs", "judge-20200102T000000Z.json"), json.dumps(
                {"verdict": "fail", "plan": "work/demo/plan.md"}))
            write(os.path.join(root, ".hdev", "runs", "judge-20200101T000000Z.json"), json.dumps(
                {"verdict": "pass", "plan": "work/demo/plan.md"}))
            self.assertTrue(life.attribute(root, "demo", "work/demo/plan.md", datetime.date(2026, 6, 1)))
            stored = store.load_local(root)[0]
            self.assertEqual(stored["wins"], 1)
            self.assertEqual(stored["losses"], 0)
            self.assertEqual(stored["uses"], 1)
            self.assertEqual(stored["last_used"], "2026-06-01")
            self.assertFalse(life.attribute(root, "demo", "work/demo/plan.md", datetime.date(2026, 6, 2)))
            self.assertEqual(store.load_local(root)[0]["wins"], 1)
            write(os.path.join(root, ".hdev", "state", "parei"),
                  "PAREI: dúvida de nome | próximo: seguir\n")
            write(os.path.join(root, "work", "outro", "pulled.json"), json.dumps({"ids": ["lesson-0001"]}))
            self.assertFalse(life.attribute(root, "outro", "work/demo/plan.md", datetime.date(2026, 6, 1)))
            self.assertEqual(store.load_local(root)[0]["losses"], 1)

    def test_parada_da_lista_nao_e_derrota(self):
        with TempDir() as root:
            save(root, [lesson(root, "lesson-0001", wins=0, losses=0, uses=0, last_used=None)])
            write(os.path.join(root, "work", "demo", "pulled.json"), json.dumps({"ids": ["lesson-0001"]}))
            write(os.path.join(root, ".hdev", "runs", "judge-20200101T000000Z.json"), json.dumps(
                {"verdict": "pass", "plan": "work/demo/plan.md"}))
            write(os.path.join(root, ".hdev", "state", "parei"),
                  "PAREI: pediram 2FA | próximo: seguir\n")
            self.assertTrue(life.attribute(root, "demo", "work/demo/plan.md", datetime.date(2026, 6, 1)))
            self.assertEqual(store.load_local(root)[0]["wins"], 1)


def _commit(path, msg):
    git(path, "add", "-A")
    result = git(path, "commit", "-q", "--no-verify", "-m", msg)
    if result.returncode != 0:
        raise AssertionError("commit falhou")


class Fechar(unittest.TestCase):
    def _repo(self, verdict="pass"):
        ctx = TempDir()
        root = ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)
        git(root, "init", "-q")
        git(root, "config", "user.name", "t")
        git(root, "config", "user.email", "t@example.invalid")
        write(os.path.join(root, ".gitignore"), ".hdev/runs/\n.hdev/state/\n")
        write(os.path.join(root, "README.md"), "x\n")
        write(os.path.join(root, ".hdev", "config.json"), json.dumps({"base_branch": "outra"}))
        write(os.path.join(root, "work", "demo", "plan.md"), "# Plano — demo\n\n## Critério de pronto\n- `true` sai 0\n")
        day = datetime.date.today().isoformat()
        pulled = lesson(root, "lesson-0001", status="active", wins=0, losses=0, uses=0, last_used=None)
        weak = lesson(root, "lesson-0002", status="active", wins=0, losses=3, uses=3, last_used=day)
        others = [lesson(root, "lesson-%04d" % n, status="active", wins=0, losses=0, uses=0,
                         last_used=day) for n in range(3, 62)]
        save(root, [pulled, weak] + others)
        write(os.path.join(root, "work", "demo", "pulled.json"), json.dumps({"ids": ["lesson-0001"]}))
        _commit(root, "base")
        write(os.path.join(root, ".hdev", "runs", "judge-20200101T000000Z.json"), json.dumps(
            {"verdict": verdict, "plan": "work/demo/plan.md"}))
        return root

    def test_fechar_marca_vitoria_e_aposenta_o_pior(self):
        root = self._repo("pass")
        code, out = hdev("fechar", "--plan", "work/demo/plan.md", "--root", root)
        self.assertEqual(code, 0)
        self.assertIn("reflita: hdev reflect --unit demo", out)
        by_id = {item["id"]: item for item in store.load_local(root)}
        self.assertEqual(by_id["lesson-0001"]["wins"], 1)
        self.assertEqual(by_id["lesson-0001"]["uses"], 1)
        self.assertEqual(by_id["lesson-0002"]["status"], "retired")
        self.assertEqual(sum(1 for item in by_id.values() if item["status"] == "active"), 60)

    def test_fechar_marca_derrota_quando_o_primeiro_juiz_falha(self):
        root = self._repo("fail")
        code, _out = hdev("fechar", "--plan", "work/demo/plan.md", "--root", root)
        self.assertEqual(code, 0)
        stored = [item for item in store.load_local(root) if item["id"] == "lesson-0001"][0]
        self.assertEqual(stored["wins"], 0)
        self.assertEqual(stored["losses"], 1)

    def test_dry_run_nao_pontua(self):
        root = self._repo("pass")
        before = text_of(store.index_path(root))
        code, out = hdev("fechar", "--plan", "work/demo/plan.md", "--root", root, "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("reflita:", out)
        self.assertEqual(text_of(store.index_path(root)), before)


class CheckCaps(unittest.TestCase):
    def test_check_recusa_teto_forma_corpo_e_script(self):
        with TempDir() as root:
            items = [lesson(root, "lesson-%04d" % n) for n in range(1, 62)]
            items.append(lesson(root, "lesson-0099", body="linha\n" * 4))
            save(root, items)
            ok, detail = store.report(root)
            self.assertFalse(ok)
            self.assertTrue(detail)
            save(root, [lesson(root, "lesson-0001", body="linha\n" * 4)])
            ok, detail = store.report(root)
            self.assertFalse(ok)
            self.assertIn("lição", detail)
            save(root, [lesson(root, "lesson-0001", kind="script", name="cache-key.py", body="print(1)\n")])
            ok, detail = store.report(root)
            self.assertFalse(ok)
            self.assertIn("script", detail)
            write(store.index_path(root), "{nao e json\n")
            ok, detail = store.report(root)
            self.assertFalse(ok)

    def test_skills_e_hooks_do_nucleo_seguem_no_teto(self):
        hooks = checkmod.check_hooks(ROOT)
        skills = checkmod.check_skills(ROOT)
        self.assertTrue(hooks.ok)
        self.assertIn("5 registros, 3 arquivos", hooks.detail)
        self.assertTrue(skills.ok)
        self.assertIn("5/5", skills.detail)
        self.assertFalse(os.path.isdir(os.path.join(ROOT, ".claude", "skills", "library")))

    def test_prompts_chamam_a_biblioteca(self):
        orch = text_of(os.path.join(ROOT, "harness", "prompts", "orchestrator.md"))
        impl = text_of(os.path.join(ROOT, "harness", "prompts", "implementer.md"))
        brief = text_of(os.path.join(ROOT, ".claude", "skills", "briefing", "SKILL.md"))
        self.assertIn("hdev library pull --spec", orch)
        self.assertIn("hdev reflect", orch)
        self.assertIn("--symptom", impl)
        self.assertIn("--tag pergunta", brief)


class Cli(unittest.TestCase):
    def test_pull_status(self):
        with TempDir() as root:
            write(os.path.join(root, ".hdev", "config.json"), json.dumps({"repo": "demo"}))
            write(os.path.join(root, "spec.md"), "# Spec\n\n" + QUERY + "\n")
            save(root, [lesson(root, "lesson-%04d" % n, status="active") for n in range(1, 4)])
            code, out = hdev("library", "pull", "--spec", "spec.md", "--k", "5", "--budget", "1500",
                             "--unit", "demo", "--root", root)
            self.assertEqual(code, 0)
            self.assertIn("corte:", out)
            self.assertLessEqual(out.count("tok\n"), 5)
            data = read_json(os.path.join(root, "work", "demo", "pulled.json"))
            self.assertLessEqual(len(data["ids"]), 5)
            self.assertLessEqual(data["tokens"], 1500)
            code, status = hdev("library", "status", "--today", "2026-06-01", "--root", root)
            self.assertEqual(code, 0)
            self.assertIn("biblioteca:", status)
            self.assertIn("elegível pra core:", status)
