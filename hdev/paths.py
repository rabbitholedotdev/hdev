"""Installation paths. Defaults are generic; a local `.env` or the process env overrides them.

This module never prints secret values. `.env` is loaded only into `os.environ` for keys
that are not already set, so CI and explicit env win.
"""
import getpass
import os

from . import CORE_ROOT

_LOADED = False


def load_dotenv(root=None):
    """Load KEY=VALUE lines from `<root>/.env` into os.environ if the key is unset."""
    global _LOADED
    root = CORE_ROOT if root is None else root
    path = os.path.join(root, ".env")
    if not os.path.isfile(path):
        _LOADED = True
        return
    try:
        with open(path, encoding="utf-8") as handle:
            for raw in handle:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = val
    except OSError:
        pass
    _LOADED = True


def _env(*names, default=""):
    for name in names:
        val = os.environ.get(name)
        if val not in (None, ""):
            return val
    return default


def bin_dir():
    """Optional extra PATH prefix for host CLIs. Empty means do not prepend."""
    return _env("HDEV_BIN_DIR")


def account_wrapper():
    """Optional wrapper that injects the current user's CLI account env. Empty = skip."""
    return _env("HDEV_ACCOUNT_WRAPPER")


def codex_env_script():
    """Optional `node … env` script that prints KEY='value'; export KEY. Empty = skip."""
    return _env("HDEV_CODEX_ENV_SCRIPT")


def codex_bin():
    return _env("HDEV_CODEX_BIN", default="codex")


def grok_bin():
    return _env("HDEV_GROK_BIN", default="grok")


def areas():
    """Directory that marks 'agent areas' for isolated reviewer copies."""
    return _env("HDEV_AREAS", default="/srv/hdev/areas")


def agents_socket():
    explicit = _env("HDEV_AGENTS_SOCKET", "HDEV_HANDOFF_SOCKET")
    if explicit:
        return explicit
    user = os.environ.get("USER") or getpass.getuser() or "user"
    return "/run/hdev-agents-%s/agentes.sock" % user


def apps_md():
    """Optional host contract file for `hdev app check`. Empty = bundled profile only."""
    return _env("HDEV_APPS_MD")


def jev_ref():
    """1Password-style reference for the TypeSafe/Jev key. Not a secret; the item lives in the vault."""
    return _env("HDEV_JEV_REF", default="op://Vault/jev-api/credential")


def key_helper():
    """CLI that prints a vault item given a reference (`op`, or a host helper)."""
    return _env("HDEV_KEY_HELPER", "HDEV_RATOEIRA_CHAVE", default="op")


# Portable deny rules for generated Claude Code settings. `~` is the current user.
HOME_DENY = [
    "Read(~/.config/**)",
    "Read(~/.claude/**)",
    "Read(~/.codex/**)",
    "Read(~/.grok/**)",
    "Read(~/.cursor/**)",
    "Read(~/.ssh/**)",
]
