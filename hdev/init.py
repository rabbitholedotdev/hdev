"""hdev init — liga um repositório a uma release do núcleo (ADR 0002), sem copiar o núcleo.

No alvo entram `.harnessdev` (symlink para `<releases>/latest`, ou para `<releases>/vX.Y.Z` com --version),
`.harnessdev.lock` e os arquivos do próprio app: AGENTS.md por referência (importa as regras do perfil da
release em uso, que se atualizam sozinhas; o app só escreve as dele), docs/progress.md, CLAUDE.md,
.claude/settings.json (só os hooks, apontando para `.harnessdev/harness/hooks/`; o alias fica em `.harnessdev/hooks/`), os links das skills do fluxo (briefing, spec, revisar-spec, planejar, revisar-diff, handoff) e hdev, os subagentes em .claude/agents/,
.hdev/config.json só com o que é do app (o resto vem da release, ver config.load) e .gitignore.
"""
import json
import os
import re
import shutil
import stat
import subprocess

from . import CORE_ROOT
from . import release

DEFAULT_PROFILE = "harness-developer"
PROFILE_RX = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SKILL_LINKS = [os.path.join(".claude", "skills", n) for n in (
    "briefing", "handoff", "planejar", "revisar-diff", "revisar-spec", "spec")]
AREA_SKILL_LINKS = [os.path.join(".claude", "skills", "hdev")]  # vale também no --skill-only (camada de área)
AGENT_FILES = ["sonnet-implementar.md", "haiku-explorar.md"]


def app_files(profile):
    """(destino no app, fonte na release). São arquivos do app: o dono edita à vontade."""
    base = os.path.join("profiles", profile)
    return [("docs/progress.md", os.path.join(base, "progress.md"))]


def agents_text(profile):
    """AGENTS.md do app por referência: as regras do perfil ficam na release e seguem o canal (F2-01)."""
    ref = "%s/profiles/%s/AGENTS.md" % (release.LINK, profile)
    return ("# AGENTS.md\n\n"
            "As regras do harness-dev deste repo estão em `%s` (release em uso, ver `.harnessdev.lock`).\n"
            "Leia esse arquivo antes de qualquer tarefa e siga-o; ele se atualiza com o núcleo, não o copie.\n"
            "@%s\n\n"
            "## Regras deste repo\n"
            "<!-- o que é só deste repo entra aqui; segurança do núcleo não se afrouxa -->\n") % (ref, ref)


def _links(rels):
    return [(rel, os.path.join(*([".."] * rel.count(os.sep)), release.LINK, rel)) for rel in rels]


def skill_links(release_dir, profile, rels=None):
    """(link no app, alvo relativo). Skills do fluxo e hdev; a skill do perfil, se ele tiver (`profiles/<p>/skill/`)."""
    wanted = SKILL_LINKS + AREA_SKILL_LINKS if rels is None else rels
    links = [(rel, alvo) for rel, alvo in _links(wanted) if os.path.isdir(os.path.join(release_dir, rel))]
    if os.path.isfile(os.path.join(release_dir, "profiles", profile, "skill", "SKILL.md")):
        rel = os.path.join(".claude", "skills", profile)
        links.append((rel, os.path.join("..", "..", release.LINK, "profiles", profile, "skill")))
    return links
GITIGNORE = (".hdev/state/", ".hdev/runs/", ".hdev/cache/", "__pycache__/")
HOOKS_FROM = "$CLAUDE_PROJECT_DIR/hooks/"
HOOKS_TO = "$CLAUDE_PROJECT_DIR/%s/hooks/" % release.LINK
APP_FAST = ("python3", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q")
APP_FULL = APP_FAST[:-1] + ("-v",)
SMOKE_TEST = '''"""Teste mínimo do hdev init: troque pelos testes do app."""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Smoke(unittest.TestCase):
    def test_agents_md_existe(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "AGENTS.md")))


if __name__ == "__main__":
    unittest.main()
'''



def agent_links(release_dir, rels=None):
    """(link no app, alvo relativo) para os subagentes do núcleo, se existirem na release."""
    wanted = AGENT_FILES if rels is None else rels
    links = []
    for name in wanted:
        if os.path.isfile(os.path.join(release_dir, ".claude", "agents", name)):
            rel = os.path.join(".claude", "agents", name)
            links.append((rel, os.path.join("..", "..", release.LINK, ".claude", "agents", name)))
    return links



def default_core():
    """O checkout do núcleo. Rodando de dentro de uma release, é o núcleo gravado nela (ou o dono de `releases/`)."""
    meta = release.read_json(os.path.join(CORE_ROOT, release.RELEASE_META))
    if meta is not None:
        core = meta.get("core")
        return core if isinstance(core, str) and os.path.isdir(core) else os.path.dirname(os.path.dirname(CORE_ROOT))
    return CORE_ROOT


def _rel(report, path):
    return os.path.relpath(path, report["target"])


def _write(path, text, force, report):
    if os.path.lexists(path) and not force:
        report["skipped"].append(_rel(report, path))
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.islink(path):
        os.remove(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    report["written"].append(_rel(report, path))


def _symlink(path, target, force, report):
    if os.path.islink(path) and os.readlink(path) == target:
        report["kept"].append(_rel(report, path))
        return
    if os.path.lexists(path):
        if not force:
            report["skipped"].append(_rel(report, path))
            return
        if os.path.isdir(path) and not os.path.islink(path):
            raise ValueError("%s é pasta de verdade; não apago (mova à mão)" % _rel(report, path))
        os.remove(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    os.symlink(target, path)
    report["written"].append(_rel(report, path))


def settings_text(release_dir):
    with open(os.path.join(release_dir, ".claude", "settings.json"), encoding="utf-8") as f:
        hooks = json.load(f).get("hooks", {})
    # as `permissions` do núcleo são a allowlist do núcleo; no app, decide o dono
    text = json.dumps({"hooks": hooks}, ensure_ascii=False, indent=2) + "\n"
    text = text.replace("$CLAUDE_PROJECT_DIR/harness/hooks/",
                        "$CLAUDE_PROJECT_DIR/%s/harness/hooks/" % release.LINK)
    return text.replace(HOOKS_FROM, HOOKS_TO)


def config_text(release_dir, profile=DEFAULT_PROFILE):
    """Só o que é do app. Papéis, fase e o timeout do juiz vêm da release (config.load mescla por baixo)."""
    with open(os.path.join(release_dir, ".hdev", "config.json"), encoding="utf-8") as f:
        core_cfg = json.load(f)
    # testes do app, não do núcleo (revisão Codex, rodada 10): o comando tem que rodar no app recém-iniciado.
    # gates.fast no Stop, gates.full no fechar e no juiz. on_stop ausente: o gate roda. false desliga.
    gates = core_cfg.get("gates") if isinstance(core_cfg.get("gates"), dict) else {}
    try:
        timeout = int(gates.get("timeout", 600) or 600)
    except (TypeError, ValueError):
        timeout = 600
    cfg = {"version": core_cfg.get("version", 1), "profile": profile,
           "gates": {"fast": list(APP_FAST), "full": list(APP_FULL), "timeout": timeout}}
    return json.dumps(cfg, ensure_ascii=False, indent=2) + "\n"


def ensure_tests(target, report):
    """Sem tests/ no app, cria um teste mínimo para o gate ter o que rodar. tests/ existente não é tocado."""
    folder = os.path.join(target, "tests")
    if os.path.lexists(folder):
        report["kept"].append("tests/")
        return
    _write(os.path.join(folder, "__init__.py"), "", False, report)
    _write(os.path.join(folder, "test_smoke.py"), SMOKE_TEST, False, report)


def _same_lock(current, wanted):
    """No canal latest, núcleo/canal/releases/modo iguais dispensam --force; version e commit podem andar com o latest."""
    if not current or current.get("channel") != wanted.get("channel"):
        return current == wanted
    if wanted.get("channel") == release.CHANNEL_LATEST:
        keys = ("core", "channel", "releases", "modo")
        return all(current.get(k) == wanted.get(k) for k in keys)
    return current == wanted


def link_and_lock(target, core, version, commit, release_dir, force, report, modo=None, channel=None,
                  link_target=None):
    link, lock_path = os.path.join(target, release.LINK), os.path.join(target, release.LOCK)
    link_target = link_target or release_dir
    current = release.read_json(lock_path)
    wanted = release.lock_data(core, version, commit, modo, channel)
    if current and not _same_lock(current, wanted) and not force:
        raise ValueError(".harnessdev.lock fixa %s (%s); para trocar para %s (%s) use --force" % (
            current.get("version"), current.get("channel") or "fixo", version, channel or "fixo"))
    if os.path.lexists(link) and not os.path.islink(link):
        raise ValueError(".harnessdev existe e não é symlink; não mexo")
    if (os.path.islink(link) and os.readlink(link) != link_target
            and os.path.realpath(link) != os.path.realpath(link_target) and not force):
        raise ValueError(".harnessdev aponta para %s; para trocar use --force" % os.readlink(link))
    _symlink(link, link_target, True, report)
    if _same_lock(current, wanted) and wanted.get("channel") == release.CHANNEL_LATEST:
        # atualiza o registro da release promovida; a promoção em si não toca no app
        if current and (current.get("version") != wanted.get("version") or current.get("commit") != wanted.get("commit")):
            updated = dict(current)
            updated["version"] = wanted["version"]
            updated["commit"] = wanted["commit"]
            wanted = updated
        else:
            wanted = current
    elif _same_lock(current, wanted):
        wanted = current
    if current != wanted:
        with open(lock_path, "w", encoding="utf-8") as f:
            json.dump(wanted, f, indent=2)
            f.write("\n")
        report["written"].append(release.LOCK)
    else:
        report["kept"].append(release.LOCK)


def _git_out(target, *args):
    try:
        r = subprocess.run(["git", "-C", target, *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def hooks_dir(target):
    """(pasta de hooks que o git usa, compartilhada?) ou (None, False) se o alvo não é a raiz de um repo.

    Pelo git, não por `.git/`: vale em worktree (`.git` é arquivo) e com `core.hooksPath`. Compartilhada é a
    pasta fora do git dir deste checkout sem `core.hooksPath` (worktree usa os hooks do repo principal)."""
    top = _git_out(target, "rev-parse", "--show-toplevel")
    if not top or os.path.realpath(top) != os.path.realpath(target):
        return None, False
    hooks = _git_out(target, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
    git_dir = _git_out(target, "rev-parse", "--absolute-git-dir")
    if not hooks or not git_dir:
        return None, False
    own = _git_out(target, "config", "core.hooksPath") is not None
    hooks, git_dir = os.path.realpath(hooks), os.path.realpath(git_dir)
    shared = not own and not hooks.startswith(git_dir + os.sep)
    return hooks, shared


GIT_HOOKS = ("pre-commit", "post-commit", "post-checkout")


def install_pre_commit(target, release_dir, report):
    """Copia os hooks de git versionados em `scripts/`. Não é hook do Claude.

    Não sobrescreve um arquivo que já existe e não mexe na pasta compartilhada de uma worktree.
    """
    hooks, shared = hooks_dir(target)
    if hooks is None:
        report["notes"].append("o alvo não é a raiz de um repositório git: pre-commit não instalado")
        return
    if shared:
        report["notes"].append("worktree: os hooks em %s são compartilhados com o repo principal; não mexi. "
                               "Para ligar só aqui: git config extensions.worktreeConfig true && "
                               "git config --worktree core.hooksPath .hdev/hooks, e copie "
                               ".harnessdev/scripts/pre-commit, post-commit e post-checkout para lá" % hooks)
        return
    installed = []
    for name in GIT_HOOKS:
        src = os.path.join(release_dir, "scripts", name)
        if not os.path.isfile(src):
            continue
        hook = os.path.join(hooks, name)
        if os.path.exists(hook):
            report["notes"].append("%s já existe: não mexi" % hook)
            continue
        os.makedirs(os.path.dirname(hook), exist_ok=True)
        shutil.copyfile(src, hook)
        os.chmod(hook, os.stat(hook).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        installed.append(name)
    if installed:
        report["notes"].append("hooks de git instalados: %s" % ", ".join(installed))


def update_gitignore(target):
    gi = os.path.join(target, ".gitignore")
    lines = []
    if os.path.exists(gi):
        with open(gi, encoding="utf-8") as f:
            lines = f.read().splitlines()
    wanted = [l for l in GITIGNORE if l not in lines]
    if wanted:
        with open(gi, "a", encoding="utf-8") as f:
            if lines and lines[-1].strip():
                f.write("\n")
            f.write("\n".join(wanted) + "\n")


def init(target, version=None, core=None, force=False, profile=DEFAULT_PROFILE, skill_only=False):
    if not PROFILE_RX.match(profile or ""):
        raise ValueError("perfil %r inválido" % profile)
    core = os.path.realpath(core or default_core())
    target = os.path.realpath(target)
    if target == core or target.startswith(release.releases_dir(core) + os.sep):
        raise ValueError("o alvo é o próprio núcleo")
    notes = []
    try:
        latest = None if version else release.current_latest(core)
        if latest:
            version, release_dir, commit = latest
            channel, link_target = release.CHANNEL_LATEST, release.latest_path(core)
        else:
            if not version:
                notes.append("canal latest ainda sem release promovida: fixado na maior tag; quando houver, "
                             "`hdev pin --latest`")
            version = release.choose_version(core, version)
            release_dir, commit = release.install(core, version)
            channel, link_target = release.CHANNEL_PINNED, release_dir
    except release.ReleaseError as e:
        raise ValueError(str(e))
    if not os.path.isfile(os.path.join(release_dir, "profiles", profile, "AGENTS.md")):
        raise ValueError("a release %s não tem o perfil %s" % (version, profile))
    if skill_only and not skill_links(release_dir, profile, AREA_SKILL_LINKS):
        raise ValueError("a release %s não tem skill para --skill-only (hdev nem profiles/%s/skill/)" % (version, profile))
    os.makedirs(target, exist_ok=True)
    report = {"target": target, "version": version, "commit": commit, "release": release_dir, "channel": channel,
              "written": [], "kept": [], "skipped": [], "notes": notes}
    link_and_lock(target, core, version, commit, release_dir, force, report, "skill" if skill_only else None,
                  channel, link_target)
    if skill_only:
        return init_skill_only(target, release_dir, version, profile, force, report)
    _write(os.path.join(target, "AGENTS.md"), agents_text(profile), force, report)
    for dest, src in app_files(profile):
        with open(os.path.join(release_dir, src), encoding="utf-8") as f:
            _write(os.path.join(target, dest), f.read(), force, report)
    _write(os.path.join(target, "CLAUDE.md"), "@AGENTS.md\n", force, report)
    _write(os.path.join(target, ".claude", "settings.json"), settings_text(release_dir), force, report)
    from . import sync as syncmod
    cli_hooks = syncmod.render_cli_hooks(target)
    for rel in syncmod.CLI_HOOKS:
        _write(os.path.join(target, rel), cli_hooks, force, report)
    _write(os.path.join(target, ".hdev", "config.json"), config_text(release_dir, profile), force, report)
    for rel, alvo in skill_links(release_dir, profile):
        _symlink(os.path.join(target, rel), alvo, force, report)
    for rel, alvo in agent_links(release_dir):
        _symlink(os.path.join(target, rel), alvo, force, report)
    ensure_tests(target, report)
    update_gitignore(target)
    install_pre_commit(target, release_dir, report)
    return report


def init_skill_only(target, release_dir, version, profile, force, report):
    """Repo que já tem regras próprias (área da Ratoeira): só `.harnessdev`, lock e os links das skills hdev e do perfil.

    AGENTS.md, CLAUDE.md, .claude/settings.json (hooks), .hdev/, tests/, docs/progress.md e o pre-commit ficam
    como estão: os 4 hooks e o pre-commit travariam o fluxo da área (Stop com progress, commit automático)."""
    for rel, alvo in skill_links(release_dir, profile, AREA_SKILL_LINKS):
        _symlink(os.path.join(target, rel), alvo, force, report)
    report["notes"].append("só a skill (%s, %s): regras, hooks, config, testes e pre-commit do repo não foram tocados"
                           % (profile, version))
    return report


def main(args):
    try:
        report = init(args.target, version=args.version, core=args.core, force=args.force,
                      profile=getattr(args, "profile", DEFAULT_PROFILE), skill_only=getattr(args, "skill_only", False))
    except (ValueError, OSError) as e:
        print("hdev init: %s" % e)
        return 1
    print("hdev init em %s: núcleo %s (%s), canal %s" % (report["target"], report["version"], report["commit"][:12],
                                                        report["channel"]))
    print("  release: %s" % report["release"])
    for key, label in (("written", "escrito"), ("kept", "mantido"), ("skipped", "pulado (já existe; use --force)")):
        for rel in report[key]:
            print("  %s: %s" % (label, rel))
    for note in report["notes"]:
        print("  nota: %s" % note)
    print("Próximo passo: python3 .harnessdev/bin/hdev check --root %s" % report["target"])
    return 0
