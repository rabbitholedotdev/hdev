"""Lê o JSON do veredito, conta rótulos e monta o diagnóstico do unsure."""
import json
import os
import re

from .constants import LABELS_DIR, MAX_EVIDENCE_FILE

def _verdict_in(obj, depth=0):
    """Objeto com 'verdict' dentro de obj: ele mesmo, um campo, ou JSON em texto num campo (envelope da CLI)."""
    if depth > 4:
        return None
    if isinstance(obj, dict):
        if "verdict" in obj:
            return obj
        children = list(obj.values())
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    found = None
    for child in children:
        hit = _find_verdict(child, depth + 1) if isinstance(child, str) else _verdict_in(child, depth + 1)
        found = hit or found
    return found


def _find_verdict(output, depth=0):
    decoder, found = json.JSONDecoder(), None
    i = output.find("{")
    while i != -1:
        try:
            obj, end = decoder.raw_decode(output, i)
        except ValueError:
            i = output.find("{", i + 1)
            continue
        hit = _verdict_in(obj, depth)
        if hit is not None:
            found = hit
            i = output.find("{", end)
        else:
            i = output.find("{", i + 1)
    return found


def parse_verdict(output):
    """Último objeto JSON com 'verdict' na saída (também dentro de envelope). None se não houver."""
    found = _find_verdict(output)
    if found is None:
        return None
    v = str(found.get("verdict", "")).strip().lower()
    v = {"não sei": "unsure", "nao sei": "unsure", "unknown": "unsure", "ok": "pass"}.get(v, v)
    if v not in ("pass", "fail", "unsure"):
        v = "unsure"
    reasons = found.get("reasons") or []
    return {"verdict": v, "reasons": reasons if isinstance(reasons, list) else [str(reasons)],
            "criteria": found.get("criteria") or []}


def tokens_from(output):
    m = re.search(r"(?i)tokens?\s+used[:\s]+([\d,.]+)", output)
    return int(re.sub(r"[,.]", "", m.group(1))) if m else None

VERDICTS = ("pass", "fail", "unsure")


def valid_label(data):
    """Rótulo no formato do README: plan, run, judge_verdict, expected, by."""
    if not isinstance(data, dict):
        return False
    for key in ("plan", "run", "by"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            return False
    return data.get("judge_verdict") in VERDICTS and data.get("expected") in VERDICTS


def count_labels(root):
    """Rótulos válidos do operador em evals/judge-labels/, um por (plan, run). Inválido ou repetido não conta."""
    folder = os.path.join(root, LABELS_DIR)
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return 0
    cases = set()
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            continue
        if valid_label(data):
            cases.add((data["plan"].strip(), data["run"].strip()))
    return len(cases)

def diagnose(result, meta, prev):
    """Diagnóstico acionável quando o juiz não decide (unsure), em vez de rejulgar em loop."""
    tips = []
    if meta.get("omitidos"):
        tips.append("%d arquivo(s) ficaram fora do pacote (passou de %s partes): suba judge.max_parts na config "
                    "ou divida a unidade; nomes no registro (pacote.omitidos)." % (len(meta["omitidos"]),
                                                                                  meta.get("max_partes")))
    if meta.get("cortados"):
        tips.append("arquivo(s) maiores que uma parte entraram cortados: %s. Mova a prova para "
                    "work/<id>/evidence/*.md (ou docs/evidence/) ou divida o arquivo."
                    % ", ".join(c["arquivo"] for c in meta["cortados"][:10]))
    if meta.get("secoes_aparadas"):
        tips.append("seções do cabeçalho aparadas por tamanho: %s. Encurte o log de testes (resumo no fim) e a "
                    "evidência." % ", ".join(meta["secoes_aparadas"]))
    if meta.get("evidencia_truncada"):
        tips.append("anexo(s) com mais de %d caracteres truncados: %s. Divida em arquivos menores com o mesmo "
                    "prefixo." % (MAX_EVIDENCE_FILE, ", ".join(meta["evidencia_truncada"])))
    if not meta.get("evidencia"):
        tips.append("nenhum anexo casou com o plano: em work/<id>/evidence/*.md entra todo .md da unidade; "
                    "em docs/evidence/ o nome tem de conter <stem-do-plano ou id>. O juiz só vê comando e saída "
                    "se estiverem no diff, nos testes ou num desses anexos.")
    statuses = [a.get("status") for a in result.get("attempts", []) if a.get("status")]
    if statuses:
        tips.append("CLI do juiz: %s." % "; ".join(sorted(set(statuses))))
    asked = [str(r) for a in result.get("attempts", []) for r in (a.get("reasons") or [])
             if a.get("verdict") == "unsure"]
    if asked:
        tips.append("o juiz pediu (responda cada item com comando e saída num anexo, ou ajuste o critério se o "
                    "item não é verificável): " + " | ".join(r[:300] for r in asked[:6]))
    streak = 1
    for data in prev:
        if data.get("verdict") != "unsure":
            break
        streak += 1
    if streak >= 3:
        tips.append("%d unsure seguidos neste plano: não rejulgue sem mudar o pacote. Se o critério pede o que o "
                    "diff não mostra, reescreva o critério em itens verificáveis (comando + saída esperada) ou "
                    "peça o override do operador." % streak)
    return streak, tips
