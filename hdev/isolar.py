"""Cópia de trabalho isolada para revisores aninhados (ADR 0007).

O gancho `commit-turno` do host (se existir) commita, no fim de cada turno de agente cuja pasta está numa área
(`HDEV_AREAS`, padrão `/srv/hdev/areas/`), o que mudou durante o turno, com a 1ª linha do pedido como mensagem. Um revisor
(`hdev grok-review`, `hdev codex-exec --isolar`) é um agente inteiro: rodando no repo, ele commitava o próprio
prompt e arrastava o trabalho em andamento do orquestrador. Aqui o revisor roda numa cópia em /tmp, fora das
áreas: o gancho não age. A cópia leva HEAD, o índice (staged) e o que está modificado/novo (não ignorado), então
`git diff` na cópia mostra o mesmo que no repo. O que o revisor grava volta para o repo como arquivo não
commitado (quem commita é o orquestrador). Só stdlib.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

AREAS = "/srv/hdev/areas/"
SKIP_BACK = (".git/", ".hdev/state/", ".hdev/runs/", "logs/")
LINKS = (".harnessdev", ".harnessdev.lock")


class IsolarError(Exception):
    pass


def _git_bin():
    return os.environ.get("HDEV_GIT_BIN") or ("/usr/bin/git" if os.path.exists("/usr/bin/git") else "git")


def _git(cwd, *args, entrada=None):
    try:
        return subprocess.run([_git_bin(), "-C", cwd, *args], capture_output=True, input=entrada, timeout=300)
    except (OSError, subprocess.SubprocessError) as e:
        raise IsolarError("git %s falhou: %s" % (args[0] if args else "", e))


def _out(r):
    return r.stdout.decode("utf-8", "replace") if isinstance(r.stdout, bytes) else (r.stdout or "")


def areas():
    return os.path.realpath(os.environ.get("HDEV_AREAS") or AREAS).rstrip("/") + "/"


def toplevel(path):
    r = _git(path, "rev-parse", "--show-toplevel")
    return os.path.realpath(_out(r).strip()) if r.returncode == 0 and _out(r).strip() else None


def _scratch_parent():
    base = os.path.realpath(os.environ.get("HDEV_SCRATCH_DIR") or tempfile.gettempdir())
    if (base.rstrip("/") + "/").startswith(areas()):
        raise IsolarError("pasta de rascunho %s está dentro de %s" % (base, areas()))
    return base


def _list(repo, *args):
    r = _git(repo, "ls-files", "-z", *args)
    if r.returncode != 0:
        raise IsolarError("git ls-files falhou em %s" % repo)
    return [p for p in _out(r).split("\0") if p]


def _sig(path):
    try:
        s = os.lstat(path)
    except OSError:
        return None
    return (s.st_mtime_ns, s.st_size)


def _rel_seguro(rel):
    """Caminho relativo do git, sem travessia (`..`) nem absoluto."""
    if not rel or os.path.isabs(rel):
        return False
    return all(p not in ("", ".", "..") for p in rel.split("/"))


def _ancestral_dentro(repo, dest):
    """False se algum ancestral de dest é link (ou resolve) para fora de repo."""
    raiz = os.path.realpath(repo)
    prefixo = raiz + os.sep
    cur = os.path.normpath(dest)
    visto = set()
    while cur not in visto:
        visto.add(cur)
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        if os.path.lexists(parent) and os.path.islink(parent):
            real = os.path.realpath(parent)
            if real != raiz and not real.startswith(prefixo):
                return False
        if os.path.lexists(parent):
            real = os.path.realpath(parent)
            if real == raiz:
                return True
            if not real.startswith(prefixo) and real != raiz:
                return False
        cur = parent
    return True


def _copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.lexists(dst):
        if os.path.isdir(dst) and not os.path.islink(dst):
            raise IsolarError("destino de devolução é diretório: %s" % dst)
        os.unlink(dst)
    if os.path.islink(src):
        os.symlink(os.readlink(src), dst)
    else:
        shutil.copy2(src, dst)


def snapshot(tree):
    """{caminho relativo: assinatura} de tudo que o git vê (rastreado + novo não ignorado), fora .git."""
    files = set(_list(tree, "--cached", "--others", "--exclude-standard"))
    return {rel: _sig(os.path.join(tree, rel)) for rel in files}


class Copia:
    """Contexto: cria a cópia, devolve o cwd equivalente lá dentro e, na saída, devolve o que mudou e limpa."""

    def __init__(self, cwd):
        self.cwd = os.path.realpath(cwd)
        self.repo = toplevel(self.cwd)
        if not self.repo:
            raise IsolarError("%s não é um repositório git" % self.cwd)
        self.rel = os.path.relpath(self.cwd, self.repo)
        self.dir = None
        self.devolvidos, self.conflitos, self.apagados, self.recusados = [], [], [], []

    def __enter__(self):
        parent = _scratch_parent()
        self.dir = os.path.realpath(tempfile.mkdtemp(prefix="hdev-isolado-", dir=parent))
        try:
            self._montar()
        except BaseException:
            self.limpar()
            raise
        return self

    @property
    def work(self):
        return os.path.normpath(os.path.join(self.dir, self.rel))

    def _montar(self):
        head = _out(_git(self.repo, "rev-parse", "--verify", "--quiet", "HEAD")).strip()
        r = _git(self.repo, "clone", "--quiet", "--shared", "--no-checkout", self.repo, self.dir)
        if r.returncode != 0:
            raise IsolarError("git clone --shared falhou: %s" % r.stderr.decode("utf-8", "replace")[-500:])
        if head:
            r = _git(self.dir, "checkout", "--quiet", "--detach", head)
            if r.returncode != 0:
                raise IsolarError("checkout de %s na cópia falhou" % head[:12])
            # índice igual ao do repo: o que está staged continua staged (os blobs vêm pelo --shared)
            src_index = _out(_git(self.repo, "rev-parse", "--git-path", "index")).strip()
            src_index = src_index if os.path.isabs(src_index) else os.path.join(self.repo, src_index)
            if os.path.isfile(src_index):
                shutil.copy2(src_index, os.path.join(self.dir, ".git", "index"))
        staged = _out(_git(self.repo, "diff", "--cached", "--name-only", "-z")).split("\0") if head else []
        mudados = set(_list(self.repo, "--modified", "--others", "--exclude-standard")) | {p for p in staged if p}
        for rel in sorted(mudados):
            src = os.path.join(self.repo, rel)
            if os.path.lexists(src) and not os.path.isdir(src):
                _copy(src, os.path.join(self.dir, rel))
        for rel in _list(self.repo, "--deleted"):
            try:
                os.unlink(os.path.join(self.dir, rel))
            except OSError:
                pass
        for name in LINKS:  # ligação com a release, se não for rastreada
            src, dst = os.path.join(self.repo, name), os.path.join(self.dir, name)
            if os.path.lexists(src) and not os.path.lexists(dst):
                _copy(src, dst)
        _git(self.dir, "update-index", "-q", "--refresh")
        self.antes_copia = snapshot(self.dir)
        self.antes_repo = {rel: _sig(os.path.join(self.repo, rel)) for rel in self.antes_copia}

    def devolver(self):
        """Arquivos novos/alterados pelo revisor voltam ao repo. Se o repo mexeu no mesmo arquivo, grava ao lado."""
        depois = snapshot(self.dir)
        for rel, sig in sorted(depois.items()):
            if rel.startswith(SKIP_BACK) or sig is None or self.antes_copia.get(rel) == sig:
                continue
            if not _rel_seguro(rel):
                self.recusados.append(rel)
                continue
            src, dst = os.path.join(self.dir, rel), os.path.join(self.repo, rel)
            if os.path.isdir(src):
                continue
            if _sig(dst) != self.antes_repo.get(rel):
                dst = dst + ".hdev-isolado"
                self.conflitos.append(rel)
            if not _ancestral_dentro(self.repo, dst):
                self.recusados.append(rel)
                if rel in self.conflitos:
                    self.conflitos.remove(rel)
                continue
            try:
                _copy(src, dst)
            except IsolarError:
                self.recusados.append(rel)
                if rel in self.conflitos:
                    self.conflitos.remove(rel)
                continue
            self.devolvidos.append(os.path.relpath(dst, self.repo))
        for rel in self.antes_copia:
            if rel not in depois and not rel.startswith(SKIP_BACK):
                self.apagados.append(rel)  # não propaga apagar: só avisa

    def limpar(self):
        if self.dir and os.environ.get("HDEV_KEEP_SCRATCH") != "1":
            shutil.rmtree(self.dir, ignore_errors=True)

    def __exit__(self, *exc):
        try:
            self.devolver()
        finally:
            self.limpar()
        self.relatar()
        return False

    def relatar(self):
        if self.devolvidos:
            sys.stderr.write("hdev: devolvido ao repo (não commitado): %s\n" % ", ".join(self.devolvidos))
        if self.conflitos:
            sys.stderr.write("hdev: o repo mudou nestes enquanto o revisor rodava; a versão dele ficou em "
                             "<arquivo>.hdev-isolado: %s\n" % ", ".join(self.conflitos))
        if self.apagados:
            sys.stderr.write("hdev: o revisor apagou na cópia (não propagado): %s\n" % ", ".join(self.apagados))
        if self.recusados:
            sys.stderr.write("hdev: devolução recusada (fora do repo): %s\n" % ", ".join(self.recusados))


def trocar_caminhos(prompt, repo, copia):
    """Caminhos absolutos do repo no pedido passam a apontar para a cópia (o revisor não grava no repo real)."""
    if not prompt or not repo:
        return prompt
    return re.sub(re.escape(repo.rstrip("/")) + r"(?![\w.-])", lambda _m: copia.rstrip("/"), prompt)
