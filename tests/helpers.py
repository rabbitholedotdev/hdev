"""Utilidades dos testes. Segredos de teste são montados em tempo de execução (o fonte fica limpo)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = os.path.join(ROOT, "hooks")
BIN = os.path.join(ROOT, "bin", "hdev")


def fake_aws_key():
    return "AK" + "IA" + "Q" * 16


def fake_anthropic_key():
    return "sk" + "-ant-" + "a1B2" * 8


def clean_env(**extra):
    # HDEV_HANDOFF_* de fora (corrida headless com limiar 0.95) ganharia do config do teste.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR" and not k.startswith("HDEV_HANDOFF_")}
    env.update(extra)
    return env


def run_hook(name, event, env=None, cwd=None):
    r = subprocess.run([sys.executable, os.path.join(HOOKS, name)], input=json.dumps(event),
                       capture_output=True, text=True, env=env or clean_env(), cwd=cwd, timeout=120)
    return r.returncode, r.stderr


def hdev(*args, cwd=None):
    r = subprocess.run([sys.executable, BIN, *args], capture_output=True, text=True, cwd=cwd or ROOT,
                       env=clean_env(), timeout=300)
    return r.returncode, r.stdout + r.stderr


def git(cwd, *args):
    # commit.gpgsign=false: o assinador do ambiente às vezes leva segundos por commit de teste
    return subprocess.run(["git", "-c", "commit.gpgsign=false", "-C", cwd, *args], capture_output=True, text=True,
                          timeout=60, env=clean_env(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid",
                                                    GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
                                                    HDEV_SKIP_GRAPH="1"))


class TempDir:
    def __enter__(self):
        self.path = os.path.realpath(tempfile.mkdtemp(prefix="hdev-test-"))
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


def make_core(parent, version="v9.9.9"):
    """Núcleo de teste: cópia da árvore atual (rastreada + nova não ignorada) num git novo, com tag `version`.

    A tag fica no núcleo de teste, nunca no real; `releases/` nasce dentro dele.
    """
    core = os.path.join(parent, "core")
    listed = subprocess.run(["git", "-C", ROOT, "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                            capture_output=True, text=True, timeout=60).stdout.split("\0")
    for rel in listed:
        if not rel or rel.startswith(("logs/", "docs/")) or not os.path.isfile(os.path.join(ROOT, rel)):
            continue
        dest = os.path.join(core, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(os.path.join(ROOT, rel), dest)
    git(core, "init", "-q")
    git(core, "add", "-A")
    git(core, "commit", "-q", "--no-verify", "-m", "núcleo de teste")
    if version:
        git(core, "tag", version)
    return core


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
