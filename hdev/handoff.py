"""hdev handoff — resume em docs/progress.md e abre a próxima sessão via WebSocket da Ratoeira."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone, timedelta

from . import config as cfgmod
from . import jev as jevmod
from . import stop as stopmod
from . import unit as unitmod
from . import wsunix

PROGRESS_MAX = 2000
DEFAULT_WINDOW = 200000
DEFAULT_THRESHOLD = 0.5
DEFAULT_COOLDOWN = 600
DEFAULT_MAX_DAY = 8
DEFAULT_AGENTE = "claude"
DEFAULT_MODE = "auto"
ZONE = "America/Sao_Paulo"
def _model_of(obj):
    if not isinstance(obj, dict):
        return None
    msg = obj.get("message") if isinstance(obj.get("message"), dict) else None
    for src in (msg, obj):
        if not isinstance(src, dict):
            continue
        for key in ("model", "modelId", "model_id"):
            val = src.get(key)
            if isinstance(val, str) and val.strip() and val.strip().lower() not in ("none", "null"):
                return val.strip()
    return None


def model_from_transcript(path):
    """Modelo da última mensagem assistant no JSONL, ou None."""
    if not path:
        return None
    last = None
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not _is_assistant(obj):
                    continue
                found = _model_of(obj)
                if found:
                    last = found
    except OSError:
        return None
    return last


def current_model(root, st=None, event=None, transcript=None):
    """Modelo da sessão: transcript, evento, estado gravado, senão o da config."""
    event = event or {}
    if transcript is None:
        transcript = event.get("transcript_path") or event.get("transcriptPath")
    found = model_from_transcript(transcript) if transcript else None
    if not found:
        ev = event.get("model")
        if isinstance(ev, str) and ev.strip():
            found = ev.strip()
    if st is None:
        st = load_state(root)
    if not found and isinstance(st.get("model"), str) and st.get("model").strip():
        found = st["model"].strip()
    if not found:
        op = st.get("opcoes") if isinstance(st.get("opcoes"), dict) else {}
        if isinstance(op.get("model"), str) and op["model"].strip():
            found = op["model"].strip()
    if not found:
        found = settings(root).get("model") or ""
    return found


def pin_model(root, st, event=None):
    model = current_model(root, st, event, transcript=(st or {}).get("transcript_path"))
    if not model:
        return st
    st = dict(st)
    st["model"] = model
    op = dict(st.get("opcoes") or {})
    op["model"] = model
    st["opcoes"] = op
    return st


def _permissions(root):
    from . import stop as stopmod
    tokens = stopmod.standing_tokens(root)
    return ", ".join(tokens) if tokens else "nenhuma"


def opening_text(root, seq, model):
    """Abertura da sessão nova. Nunca só 'leia o progress e continue'."""
    from . import unit as unitmod
    rec = unitmod.load(root) or {}
    model = model or "—"
    perms = _permissions(root)
    if rec.get("id") or rec.get("status"):
        return (
            "handoff #%s. Continue a unidade %s, status %s. "
            "Plano: %s. Brief: %s. Próximo: %s. "
            "Permissões de pé: %s. Modelo: %s. "
            "Rode `hdev resume` e faça o próximo passo."
        ) % (seq, rec.get("id") or "—", rec.get("status") or "—",
             rec.get("plan") or "—", rec.get("brief") or "—",
             rec.get("next") or "seguir o plano", perms, model)
    return (
        "handoff #%s. Nenhuma unidade marcada. "
        "Plano: —. Brief: —. Próximo: leia o backlog. "
        "Permissões de pé: %s. Modelo: %s. Rode `hdev resume`."
    ) % (seq, perms, model)
NUDGE = (
    "O contexto desta sessão está em %.0f%% da janela configurada. "
    "Termine a unidade atual (não comece outra) e rode a skill /handoff "
    "(comando `hdev handoff`). Depois encerre esta sessão; não a apague."
)


def _tz():
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(ZONE)
    except Exception:
        return timezone(timedelta(hours=-3), name=ZONE)


def now():
    return datetime.now(_tz())


def iso(dt=None):
    dt = dt or now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt.isoformat(timespec="seconds")


def settings(root=None):
    data, _ = cfgmod.load(root) if root else ({}, None)
    h = (data or {}).get("handoff") or {}
    window = int(os.environ.get("HDEV_HANDOFF_WINDOW") or h.get("window_tokens") or DEFAULT_WINDOW)
    # A janela do env vale para todo modelo; sem env, handoff.window_by_model ganha de window_tokens.
    by_model = h.get("window_by_model") if isinstance(h.get("window_by_model"), dict) else {}
    if os.environ.get("HDEV_HANDOFF_WINDOW"):
        by_model = {}
    threshold = float(os.environ.get("HDEV_HANDOFF_THRESHOLD") or h.get("threshold") or DEFAULT_THRESHOLD)
    cooldown = int(os.environ.get("HDEV_HANDOFF_COOLDOWN") or h.get("cooldown_sec") or DEFAULT_COOLDOWN)
    max_day = int(os.environ.get("HDEV_HANDOFF_MAX_DAY") or h.get("max_per_day") or DEFAULT_MAX_DAY)
    sock = os.environ.get("HDEV_HANDOFF_SOCKET") or h.get("socket") or default_socket()
    agente = h.get("agente") or DEFAULT_AGENTE
    mode = h.get("mode") or DEFAULT_MODE
    use_jev = h.get("jev", True)
    if os.environ.get("HDEV_HANDOFF_JEV") == "0":
        use_jev = False
    roles = (data or {}).get("roles") or {}
    model = ((roles.get("planner") or roles.get("executor") or {}).get("model"))
    return {
        "window_tokens": window,
        "window_by_model": by_model,
        "threshold": threshold,
        "cooldown_sec": cooldown,
        "max_per_day": max_day,
        "socket": sock,
        "agente": agente,
        "mode": mode,
        "jev": bool(use_jev),
        "model": model,
    }


def default_socket():
    from . import paths as pathmod
    return pathmod.agents_socket()


def state_path(root):
    return os.path.join(root, ".hdev", "state", "session.json")


def load_state(root):
    path = state_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(root, data):
    path = state_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def persist_session(root, session_id, **extra):
    """Grava session_id (e metadados opcionais) em .hdev/state/session.json."""
    st = load_state(root)
    if session_id:
        st["session_id"] = session_id
    st["updated_at"] = iso()
    for k, v in extra.items():
        if v is not None:
            st[k] = v
    save_state(root, st)
    return st


def _walk_usage(obj):
    if isinstance(obj, dict):
        if any(k in obj for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")):
            if any(isinstance(obj.get(k), (int, float)) for k in (
                    "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "output_tokens")):
                return obj
        for v in obj.values():
            found = _walk_usage(v)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _walk_usage(v)
            if found:
                return found
    return None


def _is_assistant(obj):
    if not isinstance(obj, dict):
        return False
    typ = str(obj.get("type") or obj.get("role") or "").lower()
    if typ in ("assistant", "ai"):
        return True
    msg = obj.get("message")
    if isinstance(msg, dict) and str(msg.get("role") or "").lower() == "assistant":
        return True
    return typ == "completion" and _walk_usage(obj) is not None


def last_assistant_usage(transcript_path):
    """Último bloco de usage da mensagem assistant no JSONL, ou None."""
    last = None
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if not _is_assistant(obj):
                    continue
                usage = _walk_usage(obj)
                if usage:
                    last = usage
    except OSError:
        return None
    return last


def usage_tokens(usage):
    if not usage:
        return 0
    def n(key):
        v = usage.get(key) or 0
        try:
            return int(v)
        except (TypeError, ValueError):
            return 0
    return n("input_tokens") + n("cache_read_input_tokens") + n("cache_creation_input_tokens")


def window_for(cfg, model):
    """Janela do modelo no mapa; fora dele, window_tokens (o nudge sai cedo, nunca tarde)."""
    return int((cfg.get("window_by_model") or {}).get(model) or cfg["window_tokens"])


def usage_ratio(usage, window_tokens):
    if not window_tokens:
        return None
    return usage_tokens(usage) / float(window_tokens)


def over_threshold(ratio, threshold):
    return ratio is not None and ratio >= threshold


def parse_ts(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, _tz())
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt.astimezone(_tz())


def guard_reason(st, cfg, now_dt=None):
    """None se pode fazer handoff; senão o motivo."""
    now_dt = now_dt or now()
    last = parse_ts(st.get("last_handoff_at"))
    if last and (now_dt - last).total_seconds() < cfg["cooldown_sec"]:
        falta = int(cfg["cooldown_sec"] - (now_dt - last).total_seconds())
        return "cooldown: espere %ds desde o handoff #%s" % (max(falta, 1), st.get("handoff_seq") or "?")
    day = now_dt.date().isoformat()
    counts = st.get("handoffs_on") or {}
    n = int(counts.get(day) or 0)
    if n >= cfg["max_per_day"]:
        return "limite diário: %d handoffs em %s (máx. %d)" % (n, day, cfg["max_per_day"])
    return None


def next_seq(st):
    try:
        return int(st.get("handoff_seq") or 0) + 1
    except (TypeError, ValueError):
        return 1


# A permissão de encerrar é da sessão que o handoff aposenta, não do repo.
# `allow_stop: true` sem este id (estado antigo) não libera: falha fechada.
STOP_SESSION = "stop_session"


def bound_stop_session(st):
    """Id da sessão que pode encerrar, ou None. Booleano solto não conta."""
    if not isinstance(st, dict):
        return None
    sid = st.get(STOP_SESSION)
    if isinstance(sid, str) and sid.strip():
        return sid.strip()
    return None


def stop_permitted(st, session_id):
    """True só quando o Stop é da sessão gravada no handoff."""
    bound = bound_stop_session(st)
    event_id = session_id.strip() if isinstance(session_id, str) else ""
    return bool(bound and event_id and bound == event_id)


def _drop_stop(st):
    st.pop(STOP_SESSION, None)
    st.pop("allow_stop", None)
    return st


def grant_stop(st, session_id):
    """Marca a sessão que sai. Sem id, não concede."""
    st = dict(st or {})
    _drop_stop(st)
    if isinstance(session_id, str) and session_id.strip():
        st[STOP_SESSION] = session_id.strip()
    return st


def consume_stop(root):
    """Um Stop permitido gasta a permissão."""
    st = load_state(root)
    if STOP_SESSION not in st and "allow_stop" not in st:
        return st
    _drop_stop(st)
    st["updated_at"] = iso()
    save_state(root, st)
    return st


def clear_stop_if_other(root, session_id):
    """SessionStart de outra sessão apaga a permissão. A sessão marcada fica."""
    st = load_state(root)
    bound = bound_stop_session(st)
    event_id = session_id.strip() if isinstance(session_id, str) else ""
    if not bound or not event_id or bound == event_id:
        return st
    _drop_stop(st)
    st["updated_at"] = iso()
    save_state(root, st)
    return st


def hook_output(event_name, ratio, allow_stop=False):
    """JSON de stdout do hook (additionalContext / decision)."""
    pct = (ratio or 0) * 100
    text = NUDGE % pct
    ev = event_name or ""
    if ev == "Stop":
        if allow_stop:
            return {"decision": "approve", "reason": "Handoff já feito; esta sessão pode encerrar."}
        return {"decision": "block", "reason": text}
    return {
        "hookSpecificOutput": {
            "hookEventName": ev or "UserPromptSubmit",
            "additionalContext": text,
        }
    }


def foreign_transcript(path):
    """Transcript de Grok (sessions/.../updates.jsonl) ou Codex (rollout-*.jsonl): não é a sessão do orquestrador."""
    if not path:
        return False
    p = str(path).replace("\\", "/")
    return (p.endswith("/updates.jsonl") or "/.grok/" in p or "/grok-contas/" in p or "/.codex/" in p
            or os.path.basename(p).startswith("rollout-"))


def unit_closed(root):
    """Unidade fechada: o trabalho acabou e o Stop não pede handoff."""
    rec = unitmod.load(root)
    return bool(rec) and rec.get("status") == unitmod.CLOSED


def hook_decide(root, event, cfg=None):
    """Persiste session_id, mede o uso e, se cruzar o limiar, devolve o JSON de orientação."""
    cfg = cfg or settings(root)
    session_id = event.get("session_id") or event.get("sessionId")
    transcript = event.get("transcript_path") or event.get("transcriptPath")
    cwd = event.get("cwd")
    ev_name = event.get("hook_event_name") or event.get("hookEventName") or ""
    if foreign_transcript(transcript):
        return None, load_state(root)  # ADR 0007: sessão de revisor aninhado não sobrescreve a do orquestrador
    st = persist_session(root, session_id, cwd=cwd, transcript_path=transcript)
    usage = last_assistant_usage(transcript) if transcript else None
    window = cfg["window_tokens"]
    if usage and cfg.get("window_by_model"):
        window = window_for(cfg, model_from_transcript(transcript))
    ratio = usage_ratio(usage, window) if usage else None
    tokens = usage_tokens(usage) if usage else None
    if tokens is not None:
        st = persist_session(root, session_id, usage_tokens=tokens, usage_ratio=ratio)
    if ev_name == "SessionStart":
        st = clear_stop_if_other(root, session_id or "")
    if ev_name == "Stop" and stop_permitted(st, session_id or ""):
        st = consume_stop(root)
        return hook_output(ev_name, ratio, allow_stop=True), st
    # Um bloqueio por fim de turno: com stop_hook_active o Stop já voltou de um bloqueio e passa.
    if ev_name == "Stop" and (event.get("stop_hook_active") or event.get("stopHookActive") or unit_closed(root)):
        return None, st
    if not over_threshold(ratio, cfg["threshold"]):
        return None, st
    if guard_reason(st, cfg):
        return None, st
    return hook_output(ev_name, ratio, allow_stop=False), st


def _compact(s, n):
    s = " ".join((s or "").split())
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)].rstrip() + "…"


def render_block(seq, estado, proximo, decisoes, bloqueios, when=None, jev_note=None):
    when = when or now()
    lines = [
        "## Handoff #%s (%s %s)" % (seq, when.strftime("%Y-%m-%d %H:%M"), ZONE),
        "- Estado: %s" % (_compact(estado, 240) or "—"),
        "- Próximo: %s" % (_compact(proximo, 240) or "—"),
        "- Decisões: %s" % (_compact(decisoes, 240) or "—"),
        "- Bloqueios: %s" % (_compact(bloqueios, 240) or "—"),
    ]
    if jev_note:
        lines.append("- Jev: %s" % _compact(jev_note, 200))
    return "\n".join(lines) + "\n"


def upsert_progress(text, block, limit=PROGRESS_MAX):
    """Troca a seção ## Handoff (se houver) ou acrescenta no fim, cabendo no teto."""
    text = text or ""
    if not text.endswith("\n") and text:
        text += "\n"
    start = text.find("## Handoff")
    if start >= 0:
        rest = text[start + 2:]
        nxt = rest.find("\n## ")
        end = (start + 2 + nxt) if nxt >= 0 else len(text)
        new = text[:start].rstrip() + "\n\n" + block.strip() + "\n" + text[end:].lstrip()
    else:
        new = text.rstrip() + "\n\n" + block.strip() + "\n"
    if len(new) <= limit:
        return new
    # tenta só o bloco, depois corta o bloco
    head = text[:start].rstrip() + "\n\n" if start >= 0 else ""
    if not head:
        # mantém o começo curto
        keep = text[:400].rsplit("\n", 1)[0] + "\n\n"
        candidate = keep + block.strip() + "\n"
        if len(candidate) <= limit:
            return candidate
        room = limit - len(keep) - 1
        return keep + block.strip()[:max(0, room)].rstrip() + "\n"
    room = limit - len(head) - 1
    return head + block.strip()[:max(0, room)].rstrip() + "\n"


def write_progress(root, block):
    path = os.path.join(root, "docs", "progress.md")
    try:
        with open(path, encoding="utf-8") as f:
            cur = f.read()
    except OSError:
        cur = "# Progresso\n"
        os.makedirs(os.path.dirname(path), exist_ok=True)
    new = upsert_progress(cur, block)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)
    return path, len(new)


def jev_note(root, estado, proximo, decisoes, bloqueios):
    """Sanity check opcional via API do Jev (sem passar pela CLI, pra não misturar stdout). Nunca ecoa a chave."""
    state = "\n".join([
        "estado: %s" % (estado or ""),
        "proximo: %s" % (proximo or ""),
        "decisoes: %s" % (decisoes or ""),
        "bloqueios: %s" % (bloqueios or ""),
    ])
    cfg = jevmod.settings(root)
    key = jevmod.resolve_key(cfg)
    if not key:
        return "sem chave; fluxo segue"
    try:
        data = jevmod.call_systemone(state, jevmod.PRESETS["handoff"], key, cfg["model"])
    except Exception as e:
        return "jev indisponível (%s)" % type(e).__name__
    finally:
        key = None
    answers = data.get("answers") if isinstance(data, dict) else {}
    adv = jevmod.advice("handoff", answers or {}, state=state)
    if adv.get("recorded_decision"):
        stopmod.append_decision(root, adv["recorded_decision"])
    unidade = adv.get("unit_closed")
    humano = adv.get("ask_human")
    bits = []
    if unidade is False:
        bits.append("unidade_fechada=não")
    elif unidade is True:
        bits.append("unidade_fechada=sim")
    elif "unidade_fechada" in (answers or {}):
        bits.append("unidade_fechada=incerto")
    if humano is True:
        bits.append("precisa_humano=sim")
    elif humano is False:
        bits.append("precisa_humano=não")
    if adv.get("recorded_decision"):
        bits.append("decisão registrada; segue")
    return ", ".join(bits) if bits else "ok"


def _looks_false_unit(note):
    return note and "unidade_fechada=não" in note


def build_opcoes(st, cfg):
    op = dict(st.get("opcoes") or {})
    if cfg.get("mode"):
        op.setdefault("mode", cfg["mode"])
    model = op.get("model") or cfg.get("model")
    if model and "model" not in op:
        op["model"] = model
    # só string/bool, ids curtos (o servidor filtra)
    clean = {}
    for k, v in op.items():
        if isinstance(v, (str, bool)) and k:
            clean[str(k)] = v
        if len(clean) >= 10:
            break
    return clean


def build_payload(root, cfg, st, seq, texto=None):
    agente = st.get("agente") or cfg["agente"]
    cwd = st.get("cwd") or os.path.realpath(root)
    payload = {
        "id": 1,
        "op": "nova",
        "agente": agente,
        "cwd": cwd,
        "opcoes": build_opcoes(st, cfg),
        "texto": texto or opening_text(root, seq, st.get("model") or cfg.get("model")),
    }
    if st.get("conta"):
        payload["conta"] = st["conta"]
    return payload


def enrich_from_listar(st, lista, session_id=None):
    """Preenche agente/cwd a partir da lista do servidor, se a sessão aparecer."""
    sid = session_id or st.get("session_id")
    if not lista or not sid:
        return st, "sessão não encontrada no listar (a confirmar)"
    hit = None
    for item in lista:
        if not isinstance(item, dict):
            continue
        if item.get("sessao") == sid or item.get("sessionId") == sid:
            hit = item
            break
    if not hit:
        return st, "sessão %s não está no listar (a confirmar: id Claude = id Ratoeira?)" % sid
    if hit.get("agente"):
        st["agente"] = hit["agente"]
    if hit.get("cwd"):
        st["cwd"] = hit["cwd"]
    if hit.get("conta"):
        st["conta"] = hit["conta"]
    return st, None


def enrich_from_resumo(st, resumo):
    if not isinstance(resumo, dict):
        return st
    if resumo.get("agente"):
        st["agente"] = resumo["agente"]
    if resumo.get("cwd"):
        st["cwd"] = resumo["cwd"]
    if resumo.get("conta"):
        st["conta"] = resumo["conta"]
    cfg = resumo.get("config") or {}
    opcoes = st.get("opcoes") or {}
    for opt in cfg.get("configOptions") or []:
        if not isinstance(opt, dict):
            continue
        oid, val = opt.get("id"), opt.get("currentValue")
        if oid and val is not None and str(oid) in ("model", "effort", "reasoning_effort", "mode"):
            opcoes[str(oid)] = val
    modes = cfg.get("modes") or {}
    if modes.get("currentModeId") and "mode" not in opcoes:
        opcoes["mode"] = modes["currentModeId"]
    if opcoes:
        st["opcoes"] = opcoes
    return st


def record_success(root, st, seq, new_session, now_dt=None):
    now_dt = now_dt or now()
    day = now_dt.date().isoformat()
    counts = dict(st.get("handoffs_on") or {})
    counts[day] = int(counts.get(day) or 0) + 1
    st["handoff_seq"] = seq
    st["last_handoff_at"] = iso(now_dt)
    st["handoffs_on"] = counts
    st["last_new_session_id"] = new_session
    st["updated_at"] = iso(now_dt)
    retired = st.get("session_id") if isinstance(st.get("session_id"), str) else ""
    st = grant_stop(st, retired)
    save_state(root, st)
    return st


def run_handoff(root, estado="", proximo="", decisoes="", bloqueios="", dry_run=False,
                use_jev=None, texto=None, request_fn=None, skip_socket=False):
    cfg = settings(root)
    if use_jev is False:
        cfg = dict(cfg, jev=False)
    st = load_state(root)
    reason = guard_reason(st, cfg)
    seq = next_seq(st)
    note = None
    if cfg["jev"] and not dry_run:
        note = jev_note(root, estado, proximo, decisoes, bloqueios)
        if note and "precisa_humano=sim" in note:
            blob = "\n".join([estado or "", proximo or "", decisoes or "", bloqueios or ""])
            kind = stopmod.classify(blob) or "login"
            line = stopmod.write_parei(root, stopmod.REASON[kind], proximo or "hdev resume")
            return {
                "ok": False,
                "error": (line or "PAREI").strip(),
                "jev": note,
                "parei": True,
                "seq": seq,
            }
        if _looks_false_unit(note):
            return {
                "ok": False,
                "error": "Jev não considera a unidade fechada; continue nela antes do handoff.",
                "jev": note,
                "seq": seq,
            }
    block = render_block(seq, estado, proximo, decisoes, bloqueios, jev_note=note)
    st = pin_model(root, st)
    payload = build_payload(root, cfg, st, seq, texto=texto)
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "seq": seq,
            "blocked": reason,
            "payload": payload,
            "socket": cfg["socket"],
            "progress": block,
            "jev": note,
        }
    if reason:
        return {"ok": False, "error": reason, "seq": seq, "payload": payload}
    write_progress(root, block)
    if (decisoes or "").strip():
        stopmod.append_decision(root, decisoes)
    if skip_socket:
        return {"ok": True, "seq": seq, "payload": payload, "skipped_socket": True}
    fn = request_fn or (lambda msg, **kw: wsunix.request(cfg["socket"], msg, timeout=kw.get("timeout", 120)))
    # tenta listar/abrir para herdar agente/cwd/opcoes/conta (só leitura da sessão atual; não apaga)
    try:
        listed = fn({"id": 1, "op": "listar", "cwd": payload["cwd"]}, timeout=30)
        if listed.get("ok") and listed.get("dados") is not None:
            st, _warn = enrich_from_listar(st, listed.get("dados"), st.get("session_id"))
            st = pin_model(root, st)
            payload = build_payload(root, cfg, st, seq, texto=texto)
    except Exception:
        pass
    if st.get("session_id") and st.get("agente"):
        try:
            opened = fn({
                "id": 2, "op": "abrir",
                "agente": st["agente"], "sessao": st["session_id"],
                "cwd": st.get("cwd") or payload["cwd"],
            }, timeout=30)
            if opened.get("ok") and isinstance(opened.get("dados"), dict):
                st = enrich_from_resumo(st, opened["dados"])
                st = pin_model(root, st)
                payload = build_payload(root, cfg, st, seq, texto=texto)
        except Exception:
            pass
    payload["id"] = 3
    resp = fn(payload, timeout=120)
    if not resp.get("ok"):
        return {
            "ok": False,
            "error": resp.get("erro") or "o servidor recusou a sessão nova",
            "seq": seq,
            "payload": payload,
            "response": {k: resp.get(k) for k in ("t", "id", "ok", "erro") if k in resp},
        }
    dados = resp.get("dados") or {}
    new_id = dados.get("sessao") or dados.get("sessionId")
    if not new_id:
        return {"ok": False, "error": "resposta ok sem id de sessão (a confirmar o formato)", "seq": seq,
                "payload": payload}
    record_success(root, st, seq, new_id)
    return {
        "ok": True,
        "seq": seq,
        "new_session": new_id,
        "payload": payload,
        "stop_old": True,
        "message": (
            "Sessão nova: %s (handoff #%s). Encerre esta sessão agora. "
            "Não apague a conversa antiga."
        ) % (new_id, seq),
    }


def main(args):
    root = os.path.realpath(args.root)
    result = run_handoff(
        root,
        estado=getattr(args, "estado", "") or "",
        proximo=getattr(args, "proximo", "") or "",
        decisoes=getattr(args, "decisoes", "") or "",
        bloqueios=getattr(args, "bloqueios", "") or "",
        dry_run=bool(getattr(args, "dry_run", False)),
        use_jev=False if getattr(args, "sem_jev", False) else None,
        texto=getattr(args, "texto", None),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("ok") and result.get("message"):
        print(result["message"], file=sys.stderr)
    return 0 if result.get("ok") and not result.get("blocked") else (0 if result.get("dry_run") else 1)
