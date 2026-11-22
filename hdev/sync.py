"""hdev sync — gera `.claude/settings.json` a partir do manifesto (`.hdev/config.json`).

Ordem de chave estável (`sort_keys`) e newline no fim. `--check` não escreve: sai 1 e mostra o diff.
`--phase` liga só as skills dessa fase via `skillOverrides` (`on`/`off`), que o Claude Code honra.
Não apaga skill. No app (`.harnessdev` symlink) regenera só os hooks, como o `hdev init`.
No núcleo, `env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` é string: a compactação nativa fica acima do handoff.
"""
import difflib
import json
import os
import sys

from . import config as cfgmod
from . import paths as pathmod

# Uma forma por comando. `bin/hdev` no lugar de `python3 bin/hdev` e do caminho absoluto.
# `*` colado cobre o comando com e sem argumentos. `python3` é o interpretador; `python` sai.
# Flags do grok ficam como estavam. Deny não entra aqui.
ALLOW = [
    "Bash(bin/hdev check*)",
    "Bash(bin/hdev judge*)",
    "Bash(git add*)",
    "Bash(git commit*)",
    "Bash(git diff*)",
    "Bash(git log*)",
    "Bash(git status*)",
    "Bash(grok -p *)",
    "Bash(grok --json-schema *)",
    "Bash(grok --output-format *)",
    "Bash(grok --prompt-file *)",
    "Bash(pytest *)",
    "Bash(python3 -m pytest*)",
    "Bash(python3 -m unittest*)",
    "Edit(.claude/**)",
]

# A lista de hoje, na mesma ordem. Não tirar entrada: o deny não enfraquece.
# Caminhos de home usam `~` (portátil). Sem username absoluto no manifesto.
DENY = [
    "Bash(sudo *)",
    "Bash(sudo)",
    "Bash(git push *)",
    "Bash(git push)",
    "Bash(rm -rf *)",
    "Bash(curl *)",
    "Bash(curl)",
    "Bash(wget *)",
    "Bash(wget)",
    *pathmod.HOME_DENY,
    "Read(/etc/shadow)",
]


class SyncError(Exception):
    pass


# Porcentagem (1-100) em que a compactação nativa dispara. O Claude Code só abaixa o limiar
# dela e copia o env como string (doc: code.claude.com/docs/en/env-vars).
AUTOCOMPACT_ENV = "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE"
# Acima do handoff, para o handoff sair primeiro; ainda abaixo de 100, para a janela não encher.
AUTOCOMPACT_MARGIN = 10
AUTOCOMPACT_MAX = 95


def _handoff(cfg):
    block = cfg.get("handoff") if isinstance(cfg, dict) else None
    return block if isinstance(block, dict) else {}


def _whole(value):
    """Inteiro, ou float sem fração (o JSON `60.0`). Bool não conta."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _percent(ratio):
    """Porcentagem inteira mais próxima. O 1e-9 tira a poeira de float (0.29*100)."""
    return int(round(float(ratio) * 100.0 + 1e-9))


def threshold_percent(cfg):
    """Limiar do handoff em %. Chave ausente: o default do handoff (0.5 → 50)."""
    from .handoff import DEFAULT_THRESHOLD
    raw = _handoff(cfg).get("threshold", DEFAULT_THRESHOLD)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise SyncError("handoff.threshold precisa ser um número")
    return _percent(raw)


def autocompact_pct(cfg):
    """Porcentagem da compactação nativa. Sem `handoff.autocompact_pct`: limiar em % + 10."""
    block = _handoff(cfg)
    if "autocompact_pct" in block and block.get("autocompact_pct") is not None:
        pct = _whole(block.get("autocompact_pct"))
        if pct is None:
            raise SyncError("handoff.autocompact_pct precisa ser um inteiro")
        return pct
    return threshold_percent(cfg) + AUTOCOMPACT_MARGIN


def autocompact_error(cfg):
    """None se a compactação fica depois do handoff e até 95. Senão o motivo, para o check."""
    try:
        pct = autocompact_pct(cfg)
        limit = threshold_percent(cfg)
    except SyncError as e:
        return str(e)
    if pct <= limit:
        return ("CLAUDE_AUTOCOMPACT_PCT_OVERRIDE %d está no limiar do handoff ou abaixo (%d); "
                "a compactação dispararia antes do handoff" % (pct, limit))
    if pct > AUTOCOMPACT_MAX:
        return "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE %d está acima de %d" % (pct, AUTOCOMPACT_MAX)
    return None


def _is_app(root):
    return os.path.islink(os.path.join(root, ".harnessdev"))


def _known_skills(root, skills):
    known = []
    seen = set()
    if isinstance(skills, dict):
        for names in skills.values():
            if not isinstance(names, list):
                continue
            for name in names:
                if isinstance(name, str) and name not in seen:
                    seen.add(name)
                    known.append(name)
    folder = os.path.join(root, ".claude", "skills")
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.startswith("."):
                continue
            if os.path.isfile(os.path.join(folder, name, "SKILL.md")) and name not in seen:
                seen.add(name)
                known.append(name)
    return known


def _check_phase_lists(skills):
    """Cada fase mostra no máximo o teto. O disco pode ter mais."""
    ceiling = cfgmod.CAP_CEILING["skills"]
    for phase, names in skills.items():
        if not isinstance(names, list) or not all(isinstance(name, str) and name for name in names):
            raise SyncError("skills.%s precisa ser uma lista de nomes" % phase)
        if len(names) > ceiling:
            raise SyncError("fase %s tem %d skills visíveis (teto %d)" % (phase, len(names), ceiling))


def skill_overrides(root, cfg, phase=None):
    """Mapa nome → on|off. Skill fora da fase fica off; o diretório não é apagado."""
    skills = cfg.get("skills") if isinstance(cfg, dict) else None
    if not isinstance(skills, dict) or not skills:
        raise SyncError("manifesto sem skills")
    _check_phase_lists(skills)
    chosen = str(cfg.get("phase") or "") if phase is None else str(phase)
    if chosen not in skills:
        raise SyncError("fase %s não está em skills" % chosen)
    enabled = skills[chosen]
    enabled_set = set(enabled)
    return {name: ("on" if name in enabled_set else "off") for name in sorted(_known_skills(root, skills))}


def render_manifest(root, cfg, phase=None):
    hooks = cfg.get("hooks") if isinstance(cfg, dict) else None
    if not isinstance(hooks, dict) or not hooks:
        raise SyncError("manifesto sem hooks")
    settings = {
        "env": {AUTOCOMPACT_ENV: str(autocompact_pct(cfg))},
        "hooks": hooks,
        "permissions": {
            "allow": list(ALLOW),
            "defaultMode": "acceptEdits",
            "deny": list(DENY),
        },
        "skillOverrides": skill_overrides(root, cfg, phase),
    }
    return json.dumps(settings, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render(root, phase=None):
    """Texto que o settings.json deve ter. No app, só os hooks da release (caminho reescrito)."""
    root = os.path.realpath(root)
    if _is_app(root):
        if phase:
            raise SyncError("hdev sync --phase vale no núcleo; o app não traz skills no manifesto")
        from . import init
        try:
            return init.settings_text(os.path.realpath(os.path.join(root, ".harnessdev")))
        except (OSError, ValueError) as e:
            raise SyncError("não gerei o settings do app: %s" % e)
    cfg, err = cfgmod.load(root)
    if err:
        raise SyncError(err)
    return render_manifest(root, cfg, phase)


def settings_path(root):
    return os.path.join(root, ".claude", "settings.json")


# Stop das outras CLIs. O formato está na doc: Codex em `.codex/hooks.json`,
# Grok em `.grok/hooks/*.json`. Os dois usam `hooks.Stop[].hooks[]` com
# `type: command`. O script é o mesmo `stop_gate.py`. Sem Antigravity.
CLI_HOOKS = (
    os.path.join(".codex", "hooks.json"),
    os.path.join(".grok", "hooks", "stop.json"),
)


def _stop_script(root):
    if _is_app(root):
        return ".harnessdev/harness/hooks/stop_gate.py"
    return "harness/hooks/stop_gate.py"


def render_cli_hooks(root):
    """JSON do Stop do Codex e do Grok. Aponta para o mesmo stop_gate.py."""
    cmd = 'python3 "$(git rev-parse --show-toplevel)/%s"' % _stop_script(root)
    payload = {
        "hooks": {
            "Stop": [{
                "hooks": [{
                    "type": "command",
                    "command": cmd,
                    "timeout": 900,
                }],
            }],
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def cli_hooks_diff(root):
    expected = render_cli_hooks(root)
    parts = []
    for rel in CLI_HOOKS:
        path = os.path.join(root, rel)
        try:
            with open(path, encoding="utf-8") as f:
                actual = f.read()
        except OSError:
            actual = ""
        if actual == expected:
            continue
        parts.append("".join(difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=rel,
            tofile="hdev sync",
        )))
    return "".join(parts)


def sync_diff(root, phase=None):
    """settings.json e os Stop do Codex e do Grok."""
    return settings_diff(root, phase) + cli_hooks_diff(root)


def write_cli_hooks(root):
    text = render_cli_hooks(root)
    for rel in CLI_HOOKS:
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def migrate_legacy_gates(root):
    """Troca `tests` e `judge.tests_command` por `gates` no config do app. Não mexe se não houver chave velha."""
    path = os.path.join(root, ".hdev", "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    tests = data.get("tests") if isinstance(data.get("tests"), dict) else None
    judge = data.get("judge") if isinstance(data.get("judge"), dict) else None
    if tests is None and not (isinstance(judge, dict) and "tests_command" in judge):
        return False
    gates = dict(data.get("gates") if isinstance(data.get("gates"), dict) else {})
    if tests:
        if "fast" not in gates and tests.get("command"):
            gates["fast"] = tests["command"]
        if "timeout" not in gates and tests.get("timeout") is not None:
            gates["timeout"] = tests["timeout"]
        if "on_stop" not in gates and "on_stop" in tests:
            gates["on_stop"] = tests["on_stop"]
        data.pop("tests", None)
    if isinstance(judge, dict) and "tests_command" in judge:
        if "full" not in gates and judge.get("tests_command"):
            gates["full"] = judge["tests_command"]
        judge.pop("tests_command", None)
        if judge:
            data["judge"] = judge
        else:
            data.pop("judge", None)
    if gates:
        data["gates"] = gates
    tmp = path + ".tmp-%d" % os.getpid()
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    return True


# shortcut: no app, o matcher de edição com ou sem NotebookEdit conta igual (NBK-001), para a release que põe o
# NotebookEdit no manifesto não deixar o check dos apps vermelho; tire quando nenhum app tiver mais o antigo.
EDIT_MATCHERS = ('"Write|Edit|MultiEdit|NotebookEdit|Read|AskUserQuestion"', '"Write|Edit|MultiEdit|Read|AskUserQuestion"')


def settings_diff(root, phase=None):
    """Diff unificado do arquivo commitado contra o que seria gerado. Vazio se bate."""
    expected = render(root, phase)
    path = settings_path(root)
    try:
        with open(path, encoding="utf-8") as f:
            actual = f.read()
    except OSError:
        actual = ""
    if actual == expected or (_is_app(root) and actual.replace(*EDIT_MATCHERS) == expected.replace(*EDIT_MATCHERS)):
        return ""
    return "".join(difflib.unified_diff(
        actual.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=".claude/settings.json",
        tofile="hdev sync",
    ))


def write_settings(root, phase=None):
    text = render(root, phase)
    path = settings_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return text


def main(args):
    root = os.path.realpath(args.root)
    phase = args.phase
    try:
        if args.check:
            diff = sync_diff(root, phase)
        else:
            migrated = migrate_legacy_gates(root)
            write_settings(root, phase)
            write_cli_hooks(root)
            diff = ""
    except SyncError as e:
        print("hdev sync: %s" % e)
        return 1
    if args.check:
        if diff:
            sys.stdout.write(diff)
            return 1
        print("hdev sync: settings.json bate com o manifesto; Stop do Codex e do Grok também")
        return 0
    print("hdev sync: .claude/settings.json")
    if migrated:
        print("hdev sync: config: tests virou gates")
    return 0
