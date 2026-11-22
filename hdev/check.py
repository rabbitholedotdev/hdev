"""hdev check — os tetos de complexidade do PRD v0.5 como portão."""
import glob
import json
import os
import re

from . import config as cfgmod
from . import release
from . import sync as syncmod

AGENTS_MAX = cfgmod.CAP_CEILING["agents"]
OVERLAY_MAX = 30
HOOKS_EXPECTED = cfgmod.CAP_CEILING["hooks"]
SKILLS_MAX = cfgmod.CAP_CEILING["skills"]
DESCRIPTION_MAX = 200
SUBAGENTS_MAX = cfgmod.CAP_CEILING["subagents"]
PROGRESS_MAX = cfgmod.CAP_CEILING["progress"]
OVERLAY_START = re.compile(r"<!--\s*perfil:[\w-]+\s*-->")
OVERLAY_END = re.compile(r"<!--\s*/perfil\s*-->")
HOOK_REL = re.compile(r"((?:harness/)?hooks/[\w-]+\.py)")
REAL_HOOKS = ("pre_tool.py", "session.py", "stop_gate.py")
ALIAS_HOOKS = ("destructive_guard.py", "gate_tests.py", "handoff_guard.py", "progress_guard.py", "secret_guard.py")


class Result:
    def __init__(self, name, ok, detail, warnings=None, failures=None, lines=None):
        self.name, self.ok, self.detail = name, ok, detail
        self.warnings, self.failures = list(warnings or []), list(failures or [])
        # ordem de impressão: (rótulo, texto); sem ela, falhas e depois avisos
        self.lines = list(lines) if lines is not None else (
            [("falha", x) for x in self.failures] + [("aviso", x) for x in self.warnings])

    def as_dict(self):
        d = {"check": self.name, "ok": self.ok, "detail": self.detail}
        if self.failures:
            d["failures"] = self.failures
        if self.warnings:
            d["warnings"] = self.warnings
        return d


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_agents(root):
    path = os.path.join(root, "AGENTS.md")
    if not os.path.isfile(path):
        return Result("agents", False, "falta AGENTS.md")
    lines = _read(path).splitlines()
    if len(lines) > AGENTS_MAX:
        return Result("agents", False, "AGENTS.md tem %d linhas (teto %d)" % (len(lines), AGENTS_MAX))
    start = next((i for i, l in enumerate(lines) if OVERLAY_START.search(l)), None)
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if OVERLAY_END.search(lines[i])), None)
        if end is None:
            return Result("agents", False, "bloco de perfil sem <!-- /perfil -->")
        size = end - start - 1
        if size > OVERLAY_MAX:
            return Result("agents", False, "bloco de perfil tem %d linhas (teto %d)" % (size, OVERLAY_MAX))
        return Result("agents", True, "%d/%d linhas, perfil %d/%d" % (len(lines), AGENTS_MAX, size, OVERLAY_MAX))
    return Result("agents", True, "%d/%d linhas" % (len(lines), AGENTS_MAX))


def check_claude_md(root):
    path = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(path):
        return Result("claude_md", False, "falta CLAUDE.md")
    if _read(path).strip() != "@AGENTS.md":
        return Result("claude_md", False, "CLAUDE.md deve conter só @AGENTS.md")
    return Result("claude_md", True, "só @AGENTS.md")


def registered_hooks(root):
    """Comandos de hook registrados em .claude/settings.json (lista) ou None se faltar o arquivo."""
    path = os.path.join(root, ".claude", "settings.json")
    if not os.path.isfile(path):
        return None
    data = json.loads(_read(path))
    commands = []
    for groups in (data.get("hooks") or {}).values():
        for group in groups or []:
            for hook in group.get("hooks") or []:
                if hook.get("type") == "command":
                    commands.append(hook.get("command", ""))
    return commands


def check_hooks(root):
    try:
        commands = registered_hooks(root)
    except ValueError as e:
        return Result("hooks", False, ".claude/settings.json inválido: %s" % e)
    if commands is None:
        return Result("hooks", False, "falta .claude/settings.json")
    if len(commands) != HOOKS_EXPECTED:
        return Result("hooks", False, "%d hooks registrados (tem que ser %d)" % (len(commands), HOOKS_EXPECTED))
    # No app, os hooks e os testes deles moram na release (.harnessdev/); no núcleo, na raiz.
    link_mark = "/%s/" % release.LINK
    linked = all(link_mark in cmd for cmd in commands)
    base = os.path.join(root, release.LINK) if linked else root
    prefix = (release.LINK + "/") if linked else ""
    real_names = []
    for cmd in commands:
        m = HOOK_REL.search(cmd)
        if not m:
            return Result("hooks", False, "hook sem arquivo em %shooks/: %s" % (prefix, cmd))
        rel = m.group(1)
        if not os.path.isfile(os.path.join(base, rel)):
            return Result("hooks", False, "hook sem arquivo em %s%s: %s" % (prefix, rel, cmd))
        if rel.startswith("harness/hooks/"):
            real_names.append(os.path.basename(rel))
    real = sorted(set(real_names))
    if real != list(REAL_HOOKS):
        return Result("hooks", False, "arquivos reais %s (têm que ser %s)" % (
            ", ".join(real) or "—", ", ".join(REAL_HOOKS)))
    # Testado = um arquivo de tests/ cita "<hook>.py" entre aspas e executa hook (run_hook ou subprocess).
    runners = [_read(p) for p in glob.glob(os.path.join(base, "tests", "**", "*.py"), recursive=True)]
    runners = [t for t in runners if re.search(r"\brun_hook\(|\bsubprocess\.(?:run|Popen|call)\(", t)]
    untested = [name for name in real
                if not any(re.search(r"[\"']%s[\"']" % re.escape(name), t) for t in runners)]
    if untested:
        return Result("hooks", False, "hook sem teste em tests/: %s" % ", ".join(untested))
    hooks_dir = os.path.join(base, "hooks")
    missing = [name for name in ALIAS_HOOKS if not os.path.isfile(os.path.join(hooks_dir, name))]
    if missing:
        return Result("hooks", False, "alias ausente em %shooks/: %s" % (prefix, ", ".join(missing)))
    for name in ALIAS_HOOKS:
        if "hdev-alias" not in _read(os.path.join(hooks_dir, name)):
            return Result("hooks", False, "alias sem delegação: %s" % name)
    on_disk = sorted(os.path.basename(p) for p in glob.glob(os.path.join(hooks_dir, "*.py"))
                     if not os.path.basename(p).startswith("_"))
    extra = [name for name in on_disk if name not in ALIAS_HOOKS]
    if extra:
        return Result("hooks", False, "hook em hooks/ fora do registro: %s" % ", ".join(extra))
    disk_real = sorted(
        os.path.basename(p) for p in glob.glob(os.path.join(base, "harness", "hooks", "*.py"))
        if not os.path.basename(p).startswith("_"))
    extra_real = [name for name in disk_real if name not in REAL_HOOKS]
    if extra_real:
        return Result("hooks", False, "hook real fora dos 3 arquivos: %s" % ", ".join(extra_real))
    return Result("hooks", True, "%d registros, %d arquivos (%s); aliases: %s%s" % (
        len(commands), len(real), ", ".join(real), ", ".join(ALIAS_HOOKS),
        " (na release)" if linked else ""))


_RELEASE_MD = re.compile(r"\.harnessdev/([A-Za-z0-9_./+-]+?\.md)")


def missing_release_links(root):
    """Arquivos `.harnessdev/*.md` citados pelo AGENTS.md do app que a release pinada não tem.

    O AGENTS.md do app só aponta o perfil (`@.harnessdev/profiles/.../AGENTS.md`). Esse include
    entra na busca: é ali que o prompt compat é ligado.
    """
    link = os.path.join(root, release.LINK)
    if not os.path.islink(link):
        return []
    agents = os.path.join(root, "AGENTS.md")
    try:
        with open(agents, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []
    blobs = [text]
    seen = set()
    for rel in _RELEASE_MD.findall(text):
        if not re.search(r"(?m)^@\.harnessdev/%s\s*$" % re.escape(rel), text):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        try:
            with open(os.path.join(link, rel), encoding="utf-8") as f:
                blobs.append(f.read())
        except OSError:
            continue
    release_root = os.path.realpath(link)
    missing = []
    for blob in blobs:
        for rel in _RELEASE_MD.findall(blob):
            if rel in missing:
                continue
            if not os.path.isfile(os.path.join(release_root, rel)):
                missing.append(rel)
    return missing


def check_harnessdev(root):
    ok, detail = release.verify(root)
    if not ok:
        return Result("harnessdev", False, detail)
    missing = missing_release_links(root)
    if missing:
        return Result("harnessdev", False,
                      "release sem arquivo que o AGENTS.md liga em .harnessdev/: " + ", ".join(missing))
    return Result("harnessdev", True, detail)


def skill_description(text):
    """description do frontmatter YAML (linha simples ou bloco > / |). None se faltar."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None
    front = lines[1:end]
    for i, line in enumerate(front):
        m = re.match(r"^description:\s*(.*)$", line)
        if not m:
            continue
        value = m.group(1).strip()
        if value in ("", ">", "|", ">-", "|-", ">+", "|+"):
            block = []
            for nxt in front[i + 1:]:
                if nxt.startswith((" ", "\t")) or not nxt.strip():
                    block.append(nxt.strip())
                else:
                    break
            joiner = "\n" if value.startswith("|") else " "
            value = joiner.join(b for b in block if b).strip()
        return value.strip("'\"")
    return None


def _core_skill(path):
    """Skill ligada à release (`.claude/skills/x` -> `../../.harnessdev/...`): é do núcleo, não conta no teto do app."""
    folder = os.path.dirname(path)
    return os.path.islink(folder) and ("/%s/" % release.LINK) in "/" + os.readlink(folder).replace(os.sep, "/") + "/"


def _is_nucleus(root):
    """O núcleo (este repo), não um app ligado por `.harnessdev`."""
    return (os.path.isfile(os.path.join(root, "hdev", "cli.py"))
            and not os.path.islink(os.path.join(root, ".harnessdev")))


def _phase_key(name):
    m = re.match(r"(?i)^F(\d+)$", str(name))
    if m:
        return (0, int(m.group(1)), "")
    return (1, 0, str(name))


def _scope_ok(text):
    m = re.search(r"(?m)^#{1,6}[ \t]+Fora de escopo[ \t]*$", text)
    if not m:
        return False
    rest = text[m.end():]
    nxt = re.search(r"(?m)^#{1,6}[ \t]+", rest)
    section = rest[:nxt.start()] if nxt else rest
    return "não confundir com" in section


def _refs_problem(skill_dir, text):
    names = re.findall(r"references/([A-Za-z0-9_-]+\.md)", text)
    if not names:
        return "sem references/"
    missing = [n for n in names if not os.path.isfile(os.path.join(skill_dir, "references", n))]
    if missing:
        return "references/ sem arquivo: %s" % ", ".join(missing)
    return None


def _eval_ok(root, name):
    path = os.path.join(root, "evals", "skills", name + ".md")
    if not os.path.isfile(path):
        return False
    with open(path, encoding="utf-8") as f:
        return bool(f.read().strip())


def _phase_bits(root):
    """Lista 'F0 1/5, ...' ou um texto de erro. None se o manifesto não traz fases."""
    data, err = cfgmod.load(root)
    if err or not isinstance(data, dict):
        return None
    skills = data.get("skills")
    if not isinstance(skills, dict) or not skills:
        return None
    bits = []
    for phase in sorted(skills, key=_phase_key):
        names = skills[phase]
        if not isinstance(names, list) or not all(isinstance(n, str) and n for n in names):
            return "skills.%s precisa ser uma lista de nomes" % phase
        if len(names) > SKILLS_MAX:
            return "fase %s com %d skills visíveis (teto %d)" % (phase, len(names), SKILLS_MAX)
        bits.append("%s %d/%d" % (phase, len(names), SKILLS_MAX))
    return bits


def check_skills(root):
    skill_files = sorted(glob.glob(os.path.join(root, ".claude", "skills", "*", "SKILL.md")))
    own = [p for p in skill_files if not _core_skill(p)]
    nucleus = _is_nucleus(root)
    for path in skill_files:
        name = os.path.basename(os.path.dirname(path))
        text = _read(path)
        desc = skill_description(text)
        if not desc:
            return Result("skills", False, "skill %s sem description no frontmatter" % name)
        if len(desc) > DESCRIPTION_MAX:
            return Result("skills", False, "skill %s: description com %d caracteres (teto %d)" % (
                name, len(desc), DESCRIPTION_MAX))
        if not nucleus:
            continue
        if not _scope_ok(text):
            return Result("skills", False, "skill %s sem Fora de escopo (não confundir com)" % name)
        if not re.search(r"\bhdev\b", text):
            return Result("skills", False, "skill %s sem verbo hdev" % name)
        ref = _refs_problem(os.path.dirname(path), text)
        if ref:
            return Result("skills", False, "skill %s %s" % (name, ref))
        if not _eval_ok(root, name):
            return Result("skills", False, "skill %s sem caso em evals/skills/%s.md" % (name, name))
    phases = _phase_bits(root)
    if isinstance(phases, str):
        return Result("skills", False, phases)
    if isinstance(phases, list):
        detail = "visíveis %s; descriptions <= %d" % (", ".join(phases), DESCRIPTION_MAX)
    else:
        extra = " (+%d do núcleo)" % (len(skill_files) - len(own)) if len(skill_files) != len(own) else ""
        detail = "%d próprias%s; descriptions <= %d" % (len(own), extra, DESCRIPTION_MAX)
    return Result("skills", True, detail)


def _core_agent(path):
    """Agent ligado à release (arquivo -> ../../.harnessdev/...): é do núcleo, não conta no teto do app."""
    return os.path.islink(path) and ("/%s/" % release.LINK) in "/" + os.readlink(path).replace(os.sep, "/") + "/"


def check_subagents(root):
    if os.path.isdir(os.path.join(root, "agents")):
        return Result("subagents", False, "pasta agents/ na raiz é proibida (subagente mora em .claude/agents/)")
    agents = glob.glob(os.path.join(root, ".claude", "agents", "*.md"))
    own = [p for p in agents if not _core_agent(p)]
    data, _ = cfgmod.load(root)
    phase = str((data or {}).get("phase") or "F1")
    m = re.match(r"(?i)^F(\d+)$", phase)
    if not m:
        return Result("subagents", False, "phase %r inválida em .hdev/config.json (use F0, F1, F2...)" % phase)
    limit = SUBAGENTS_MAX if int(m.group(1)) >= 2 else 0  # F0/F1: 0; F2+: 2 (ADR 0005)
    if len(own) > limit:
        return Result("subagents", False, "%d subagentes (teto %d na %s)" % (len(own), limit, phase.upper()))
    core = len(agents) - len(own)
    extra = " (+%d do núcleo)" % core if core else ""
    return Result("subagents", True, "%d/%d na %s%s" % (len(own), limit, phase.upper(), extra))


def check_config(root):
    data, err = cfgmod.load(root)
    if err:
        return Result("config", False, err)
    roles = data.get("roles") or {}
    for needed in ("executor", "judge"):
        if not isinstance(roles.get(needed), dict):
            return Result("config", False, "falta o papel %s em roles" % needed)
    providers = {}
    for name, role in roles.items():
        provider, role_err = cfgmod.validate_role(name, role)
        if role_err:
            return Result("config", False, role_err)
        providers[name] = provider
    # juiz, fallback e a tarefa isolada (F1-03, grok) não podem ser do provedor do executor
    for judge in ("judge", "judge_fallback", "isolated"):
        if judge in providers and providers[judge] == providers["executor"]:
            return Result("config", False, "%s usa %s, mesmo provedor do executor (%s)" % (
                judge, roles[judge].get("model"), providers["executor"]))
    caps_err = cfgmod.caps_error(data)
    if caps_err:
        return Result("config", False, caps_err)
    if not cfgmod.gate_command(data, "fast") or not cfgmod.gate_command(data, "full"):
        return Result("config", False, "faltam gates.fast e gates.full")
    err = syncmod.autocompact_error(data)
    if err:
        return Result("config", False, err)
    return Result("config", True, "executor %s, juiz %s" % (providers["executor"], providers["judge"]))


PROMPT_DIR = os.path.join("harness", "prompts")
STOP_REL = os.path.join(PROMPT_DIR, "_shared", "stop-list.md")
STOP_MARKER = "## stop-list"
ROLE_FILES = ("orchestrator.md", "executor.md", "implementer.md", "reviewer.md")
ROLE_MAX = 120
_WALK_SKIP = {".git", "releases", "__pycache__", ".hdev", "node_modules"}


def _marker_line(text):
    return any(line.strip() == STOP_MARKER for line in text.splitlines())


def check_prompts(root):
    """A lista de parada mora num arquivo. Outro `.md` com o marcador, ou `PROMPT-*.md` na raiz, falha."""
    stop = os.path.join(root, STOP_REL)
    if not os.path.isfile(stop):
        if os.path.islink(os.path.join(root, release.LINK)):
            return Result("prompts", True, "app: lista na release")
        return Result("prompts", False, "falta %s" % STOP_REL.replace(os.sep, "/"))
    if not _marker_line(_read(stop)):
        return Result("prompts", False, "%s sem o marcador da lista" % STOP_REL.replace(os.sep, "/"))
    base = os.path.join(root, PROMPT_DIR)
    for rel in (os.path.join("_shared", "safety.md"), os.path.join("_shared", "style.md")):
        if not os.path.isfile(os.path.join(base, rel)):
            return Result("prompts", False, "falta %s" % os.path.join(PROMPT_DIR, rel).replace(os.sep, "/"))
    style = _read(os.path.join(base, "_shared", "style.md"))
    if len(style.splitlines()) != 1 or not style.strip():
        return Result("prompts", False, "style.md tem de ser uma linha")
    for name in ROLE_FILES:
        path = os.path.join(base, name)
        if not os.path.isfile(path):
            return Result("prompts", False, "falta %s" % os.path.join(PROMPT_DIR, name).replace(os.sep, "/"))
        text = _read(path)
        if "stop-list.md" not in text:
            return Result("prompts", False, "%s não cita stop-list.md" % name)
        n = len(text.splitlines())
        if n > ROLE_MAX:
            return Result("prompts", False, "%s tem %d linhas (teto %d)" % (name, n, ROLE_MAX))
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _WALK_SKIP]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            if rel == STOP_REL.replace(os.sep, "/"):
                continue
            try:
                text = _read(path)
            except OSError:
                continue
            if _marker_line(text):
                hits.append(rel)
    root_prompts = sorted(n for n in os.listdir(root) if n.startswith("PROMPT-") and n.endswith(".md"))
    if root_prompts or hits:
        bits = []
        if root_prompts:
            bits.append("PROMPT na raiz: " + ", ".join(root_prompts))
        if hits:
            bits.append("marcador fora da lista: " + ", ".join(hits))
        return Result("prompts", False, "; ".join(bits))
    return Result("prompts", True, "%d papéis, lista única" % len(ROLE_FILES))


def check_sync(root):
    """O mesmo diff de `hdev sync --check`. Arquivo gerado que divergiu falha o portão."""
    try:
        diff = syncmod.sync_diff(root)
    except syncmod.SyncError as e:
        return Result("sync", False, str(e))
    if diff:
        return Result("sync", False, "arquivo gerado diverge do manifesto", failures=diff.splitlines())
    return Result("sync", True, "settings.json, Codex e Grok batem com o manifesto")


def check_progress(root):
    path = os.path.join(root, "docs", "progress.md")
    if not os.path.isfile(path):
        return Result("progress", False, "falta docs/progress.md")
    size = len(_read(path))
    if size > PROGRESS_MAX:
        return Result("progress", False, "docs/progress.md com %d caracteres (teto %d)" % (size, PROGRESS_MAX))
    return Result("progress", True, "%d/%d caracteres" % (size, PROGRESS_MAX))


def check_names(root, base=None):
    from . import naming
    return naming.check_names(root, base)


_GRAPH_FORBIDDEN = re.compile(r"graphify|GRAPH_REPORT|\bgrafo\b", re.IGNORECASE)
_GRAPH_EXPLORER_REL = os.path.join(".claude", "agents", "haiku-explorar.md")
_GRAPH_PHRASES = ("graphify query", "graphify path", "graphify explain")
_GRAPH_CONTEXT = (
    "AGENTS.md",
    "CLAUDE.md",
    os.path.join("harness", "prompts", "orchestrator.md"),
    os.path.join("harness", "prompts", "executor.md"),
    os.path.join(".harnessdev", "harness", "prompts", "orchestrator.md"),
    os.path.join(".harnessdev", "harness", "prompts", "executor.md"),
)


def check_graph(root):
    """graphify e GRAPH_REPORT só no explorer. O binário não roda."""
    explorer = os.path.join(root, _GRAPH_EXPLORER_REL)
    skip = set()
    if os.path.isfile(explorer):
        skip.add(os.path.realpath(explorer))
    seen = set()
    hits = []
    paths = []
    for rel in _GRAPH_CONTEXT:
        path = os.path.join(root, rel)
        if os.path.isfile(path):
            paths.append((rel.replace(os.sep, "/"), path))
    skills = os.path.join(root, ".claude", "skills")
    for pattern in ("*/SKILL.md", "*/references/*.md"):
        for path in sorted(glob.glob(os.path.join(skills, pattern))):
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            paths.append((rel, path))
    for rel, path in paths:
        real = os.path.realpath(path)
        if real in seen or real in skip:
            continue
        seen.add(real)
        try:
            text = _read(path)
        except OSError:
            continue
        if _GRAPH_FORBIDDEN.search(text):
            hits.append(rel)
    if hits:
        return Result("graph", False, "menção a grafo fora do explorer: " + ", ".join(hits))
    if not os.path.isfile(explorer):
        return Result("graph", False, "falta .claude/agents/haiku-explorar.md")
    try:
        text = _read(explorer)
    except OSError as e:
        return Result("graph", False, "explorer ilegível: %s" % e)
    missing = [phrase for phrase in _GRAPH_PHRASES if phrase not in text]
    if missing:
        return Result("graph", False, "explorer sem %s" % ", ".join(missing))
    return Result("graph", True, "só o explorer; query, path, explain")


def check_library(root):
    """Índice local válido, lição curta, script com teste, no máximo 60 ativas."""
    from .library import store as libstore
    ok, detail = libstore.report(root)
    return Result("library", ok, detail)


def check_overlays(root):
    """Candidata do improve não toca caminho de `harness/protected.txt` (ADR 0013)."""
    from .improve import probe as probemod
    found = probemod.overlay_problems(root)
    if found:
        return Result("overlays", False, found[0], failures=found[1:])
    ids = probemod.cand_ids(root)
    return Result("overlays", True, "%d candidatas, nenhuma em caminho protegido" % len(ids) if ids else "nenhuma")


def check_xray(root):
    """Contexto inicial estimado contra `caps.context_initial`."""
    from . import xray as xraymod
    try:
        report = xraymod.measure(root)
    except Exception as e:
        return Result("xray", False, "erro: %s" % e)
    cap = xraymod.cap_of(root)
    total = int(report["total"])
    return Result("xray", total <= cap, "estimativa %d/%d" % (total, cap))


CHECKS = [check_agents, check_claude_md, check_hooks, check_skills, check_subagents, check_config, check_sync,
          check_prompts, check_progress, check_xray, check_graph, check_library, check_overlays, check_harnessdev, check_names]


def area_mode(root):
    """Repo ligado com `hdev init --skill-only`: o lock diz `"modo": "skill"`."""
    return (release.read_json(os.path.join(root, release.LOCK)) or {}).get("modo") == "skill"


def check_core_skills(root):
    """Em repo de área: as skills ligadas à release resolvem até um SKILL.md (os tetos do harness não se aplicam)."""
    linked, broken = [], []
    for path in sorted(glob.glob(os.path.join(root, ".claude", "skills", "*"))):
        if os.path.islink(path) and ("/%s/" % release.LINK) in "/" + os.readlink(path).replace(os.sep, "/") + "/":
            (linked if os.path.isfile(os.path.join(path, "SKILL.md")) else broken).append(os.path.basename(path))
    if broken:
        return Result("core_skills", False, "skill ligada sem SKILL.md na release: %s" % ", ".join(broken))
    if not linked:
        return Result("core_skills", False, "nenhuma skill ligada a .harnessdev/ em .claude/skills/")
    return Result("core_skills", True, "%s (repo de área: tetos do harness não se aplicam)" % ", ".join(linked))


def run(root, base=None):
    results = []
    for fn in ([check_harnessdev, check_core_skills] if area_mode(root) else CHECKS):
        try:
            results.append(fn(root, base) if fn is check_names else fn(root))
        except Exception as e:  # um check quebrado vira falha, não traceback
            results.append(Result(fn.__name__.replace("check_", ""), False, "erro: %s" % e))
    return results


def main(args):
    root = os.path.realpath(args.root)
    if getattr(args, "area", False):
        from . import area
        results = area.check_area(root)
    else:
        results = run(root, getattr(args, "base", None))
    if args.json:
        print(json.dumps([r.as_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            print("[%s] %s: %s" % ("ok" if r.ok else "FALHA", r.name, r.detail))
            for kind, line in getattr(r, "lines", ()):
                print("  %s: %s" % (kind, line))
    return 0 if all(r.ok for r in results) else 1
