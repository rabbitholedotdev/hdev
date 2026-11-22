"""Entrada da CLI: hdev check | sync | init | judge | spec | base | fechar | eval | xray | triage | app | release | rollback | pin | area | wt | jev | handoff | resume | codex-exec | grok-review | graph | impact | library | reflect | improve."""
import argparse
import os
import sys

from . import (CORE_ROOT, VERSION, app, area, base, channel, check, eval as evalmod, fechar, graph as graphmod,
               handoff, init, jev, judge, spec, stop, sync, triage, versao, wrappers, xray)
from . import paths as pathmod
from .improve.compose import main_compose, main_revert
from .improve.probe import main_probe
from .library.command import main_library, main_reflect


def _default_root():
    cwd = os.getcwd()
    path = cwd
    while True:
        if os.path.isdir(os.path.join(path, ".git")) or os.path.isfile(os.path.join(path, ".hdev", "config.json")):
            return path
        parent = os.path.dirname(path)
        if parent == path:
            return cwd
        path = parent


def parser():
    p = argparse.ArgumentParser(prog="hdev", description="Núcleo harness-dev: check, init, judge, spec, jev, wrappers, app, release.")
    p.add_argument("--version", action="version", version="hdev %s" % VERSION)
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="impõe os tetos de complexidade")
    c.add_argument("--root", default=None)
    c.add_argument("--json", action="store_true")
    c.add_argument("--area", action="store_true", help="--root é uma área: confere cada projeto e os nomes")
    c.add_argument("--base", default=None, help="base do diff da checagem names (padrão: a da unidade)")
    c.set_defaults(func=check.main)

    sy = sub.add_parser("sync", help="gera .claude/settings.json a partir do manifesto")
    sy.add_argument("--root", default=None)
    sy.add_argument("--phase", default=None, help="liga só as skills dessa fase (skillOverrides)")
    sy.add_argument("--check", action="store_true", help="sai 1 e mostra o diff se o arquivo diverge")
    sy.set_defaults(func=sync.main)

    i = sub.add_parser("init", help="liga um repo a uma release do núcleo (.harnessdev + lock)")
    i.add_argument("target")
    i.add_argument("--version", dest="version", default=None,
                   help="fixa na tag vX.Y.Z (padrão: canal latest; sem latest, a maior tag)")
    i.add_argument("--core", default=None, help="checkout do núcleo (padrão: o deste hdev)")
    i.add_argument("--force", action="store_true", help="sobrescreve arquivos e troca a versão fixada")
    i.add_argument("--profile", default=init.DEFAULT_PROFILE, help="perfil: harness-developer ou ratoeira-app-creator")
    i.add_argument("--skill-only", action="store_true",
                   help="repo com regras próprias (área da Ratoeira): só .harnessdev, lock e a skill do perfil")
    i.set_defaults(func=init.main)

    j = sub.add_parser("judge", help="juiz de outro provedor sobre critério, diff e testes")
    j.add_argument("--plan", required=True, help="work/<id>/plan.md (alias: docs/plan-<tarefa>.md)")
    j.add_argument("--root", default=None)
    j.add_argument("--base", default=None,
                   help="força a base do diff (padrão: a da unidade; `hdev base --plan P` mostra qual)")
    j.add_argument("--head", default=None, help="com --base: julga só o intervalo base..head (sem não rastreados)")
    g =j.add_mutually_exclusive_group()
    g.add_argument("--tests-log", default=None, help="arquivo com a saída dos testes")
    g.add_argument("--run-tests", action="store_true", help="roda gates.full da config")
    j.add_argument("--dry-run", action="store_true", help="só mostra o pacote, não chama o juiz")
    j.add_argument("--rejulgar", action="store_true",
                   help="chama o juiz mesmo com o pacote idêntico ao do último unsure (ADR 0010)")
    j.add_argument("--no-cache", action="store_true",
                   help="ignora o veredito guardado e chama o provedor")
    j.add_argument("--json", action="store_true")
    j.set_defaults(func=judge.main)

    bs = sub.add_parser("base", help="base do diff da unidade (commit de antes da peça): mostra ou grava (ADR 0008)")
    bs.add_argument("--plan", required=True, help="work/<id>/plan.md (alias: docs/plan-<tarefa>.md)")
    bs.add_argument("--root", default=None)
    bs.add_argument("--marcar", nargs="?", const="", default=None, metavar="REF",
                    help="grava a base da unidade em .hdev/state/bases.json (padrão: a deduzida; ou REF)")
    bs.add_argument("--force", action="store_true", help="com --marcar: troca a base já gravada")
    bs.add_argument("--sha", action="store_true", help="só o SHA (git diff $(hdev base --plan P --sha))")
    bs.add_argument("--json", action="store_true")
    bs.set_defaults(func=base.main)

    fc = sub.add_parser("fechar", aliases=["close"],
                        help="fecha a unidade: commit 'INF-XXX feito: …; juiz pass|override' com trailers (ADR 0009)")
    fc.add_argument("--plan", required=True, help="work/<id>/plan.md (alias: docs/plan-<tarefa>.md)")
    fc.add_argument("--root", default=None)
    fc.add_argument("--resumo", default=None, help="resumo da 1ª linha (padrão: título do plano)")
    fc.add_argument("--override", default=None, metavar="'QUEM: MOTIVO'", help="fecha sem juiz pass, com o motivo")
    fc.add_argument("--squash", action="store_true", help="opcional: junta base..HEAD no marco (só intervalo local)")
    fc.add_argument("--dry-run", action="store_true",
                    help="mostra a mensagem, o gates.full, os shards e o cache, sem rodar")
    fc.add_argument("--no-cache", action="store_true", help="ignora o cache da suíte e roda de novo")
    fc.set_defaults(func=fechar.main, no_cache=False)

    ev = sub.add_parser("eval", help="roda um caso em braços isolados")
    evsub = ev.add_subparsers(dest="eval_command", required=True)
    rn = evsub.add_parser("run", help="clona no base_sha, aplica o braço e roda o aceite")
    rn.add_argument("--case", required=True, help="id em evals/tasks/<id>/task.json")
    rn.add_argument("--arms", required=True, help="plain,base ou cand-<id>, separados por vírgula")
    rn.add_argument("--runs", type=int, default=1, help="corridas por braço (braços × corridas ≤ 12)")
    rn.add_argument("--runner", choices=("auto", "claude", "fake", "none"), default="auto")
    rn.add_argument("--dry-run", action="store_true", help="mostra o plano, não clona e não roda")
    rn.add_argument("--root", default=None)
    rn.set_defaults(func=evalmod.main_run)

    ip = sub.add_parser("improve", help="testa candidatas do harness; compose cria a branch improve/<id>, revert desfaz")
    ipsub = ip.add_subparsers(dest="improve_command", required=True)
    pr = ipsub.add_parser("probe", help="plain, base e cand-<id> no mesmo caso; relatório e candidata na biblioteca")
    pr.add_argument("--case", required=True, help="id em evals/tasks/<id>/task.json")
    pr.add_argument("--cand", required=True, help="até 2 ids em .hdev/overlays/, por vírgula; demo nasce sozinha")
    pr.add_argument("--runs", type=int, default=3,
                    help="corridas por braço (>= 3, ou >= 2 com claude; braços × corridas <= 12)")
    pr.add_argument("--runner", choices=("fake", "none", "claude"), default="fake",
                    help="claude roda o Sonnet de verdade (eval.model)")
    pr.add_argument("--dry-run", action="store_true", help="mostra o plano, não clona e não roda")
    pr.add_argument("--root", default=None)
    pr.set_defaults(func=main_probe)
    co = ipsub.add_parser("compose", help="candidata ganharia vira branch local improve/<id> com trailer Harness-Edit")
    co.add_argument("--run", required=True, help="registro .hdev/runs/improve-<stamp>.json do probe")
    co.add_argument("--cand", required=True, help="id da candidata no registro")
    co.add_argument("--dry-run", action="store_true", help="mostra branch, arquivos e mensagem; não grava nada")
    co.add_argument("--root", default=None)
    co.set_defaults(func=main_compose)
    rv = ipsub.add_parser("revert", help="reverte o commit com Harness-Edit (commit novo, sem reescrever)")
    rg = rv.add_mutually_exclusive_group(required=True)
    rg.add_argument("--cand", help="último commit do HEAD com Harness-Edit: <id>")
    rg.add_argument("--commit", help="commit dado; recusa se não tem o trailer")
    rv.add_argument("--root", default=None)
    rv.set_defaults(func=main_revert)

    xr = sub.add_parser("xray", help="estima o contexto inicial da sessão")
    xr.add_argument("--root", default=None)
    xr.add_argument("--max", type=int, default=None, help="sai 1 se a estimativa passar de N")
    xr.add_argument("--json", action="store_true")
    xr.set_defaults(func=xray.main)

    tr = sub.add_parser("triage", help="decide a trilha fast (trivial) ou full e grava work/<id>/state.json")
    tr.add_argument("--id", required=True, help="id da unidade (pasta work/<id>)")
    tr.add_argument("--root", default=None)
    tg = tr.add_mutually_exclusive_group()
    tg.add_argument("--trivial", action="store_true",
                    help="um commit, sem dependência nova, sem mudança de contrato")
    tg.add_argument("--full", action="store_true", help="trilha cheia; na dúvida, esta")
    tr.add_argument("--one-commit", action="store_true", help="cabe num commit")
    tr.add_argument("--no-new-dependency", action="store_true", help="não adiciona dependência")
    tr.add_argument("--no-contract-change", action="store_true", help="não muda contrato")
    tr.set_defaults(func=triage.main)

    sc = sub.add_parser("spec", help="confere a spec da unidade")
    scsub = sc.add_subparsers(dest="spec_command", required=True)
    sck = scsub.add_parser("check", help="aceite em comando, fora de escopo e tabela de defaults")
    sck.add_argument("path", help="arquivo da spec")
    sck.set_defaults(func=spec.main_check)

    a = sub.add_parser("app", help="padrão ratoeira-app-creator: monta e confere um app da Ratoeira")
    asub = a.add_subparsers(dest="app_command", required=True)
    an = asub.add_parser("new", help="monta <área>/apps/<nome>/ pelo modelo do perfil")
    an.add_argument("nome")
    an.add_argument("--area", default=".", help="raiz da área (padrão: a pasta atual)")
    an.add_argument("--titulo", default=None)
    an.add_argument("--descricao", default=None)
    an.add_argument("--porta", type=int, default=None, help="padrão: a primeira livre a partir de 8800")
    an.add_argument("--areas", default=None, help="onde procurar portas usadas (padrão: a pasta acima da área)")
    ac = asub.add_parser("check", help="confere o contrato mecânico do APPS.md num app")
    ac.add_argument("pasta")
    ac.add_argument("--areas", default=None, help="onde procurar portas repetidas (padrão: três pastas acima)")
    ac.add_argument("--json", action="store_true")
    at = asub.add_parser("tag", help="na publicação: tag anotada <app>-vX.Y.Z em HEAD (ADR 0009)")
    at.add_argument("nome")
    at.add_argument("versao", help="vX.Y.Z")
    at.add_argument("--repo", default=".")
    at.add_argument("--dir", default=None, help="pasta do app (padrão: <repo>/<app>, <repo>/apps/<app> ou o repo)")
    at.add_argument("--message", "-m", default=None)
    at.add_argument("--publicado", action="store_true", help="confirma estado_publicacao ok")
    at.set_defaults(func=versao.main_app_tag)
    a.set_defaults(func=app.main)

    r = sub.add_parser("release", help="núcleo: tag anotada + instala + promove latest se houver juiz pass")
    r.add_argument("version")
    r.add_argument("--message", "-m", default=None)
    r.add_argument("--core", default=None)
    r.set_defaults(func=channel.main_release)

    rb = sub.add_parser("rollback", help="núcleo: volta latest para a promoção anterior (ou --to vX.Y.Z)")
    rb.add_argument("--to", default=None)
    rb.add_argument("--core", default=None)
    rb.set_defaults(func=channel.main_rollback)

    pn = sub.add_parser("pin", help="app: fixa .harnessdev numa versão, ou --latest para seguir o canal")
    pn.add_argument("version", nargs="?", default=None)
    pn.add_argument("--latest", action="store_true")
    pn.add_argument("--root", default=None)
    pn.add_argument("--core", default=None)
    pn.set_defaults(func=channel.main_pin)

    ar = sub.add_parser("area", help="área da Ratoeira")
    arsub = ar.add_subparsers(dest="area_command", required=True)
    sy = arsub.add_parser("sync", help="liga ao canal latest os projetos da área sem harness e confere todos")
    sy.add_argument("--area", default=".")
    sy.add_argument("--profile", default=init.DEFAULT_PROFILE)
    sy.add_argument("--skip", action="append", help="pasta a ignorar (repetível)")
    sy.add_argument("--core", default=None)
    sy.add_argument("--dry-run", action="store_true")
    ar.set_defaults(func=area.main_area)

    w = sub.add_parser("wt", help="worktrees em <área>/_wt/<repo>-<branch>")
    wsub = w.add_subparsers(dest="wt_command", required=True)
    wa = wsub.add_parser("add", help="cria a worktree da branch (cria a branch se não existir)")
    wa.add_argument("branch")
    wa.add_argument("--repo", default=".")
    wa.add_argument("--base", default=None, help="ponto de partida da branch nova (padrão: HEAD)")
    wm = wsub.add_parser("move", help="move uma worktree existente para _wt/")
    wm.add_argument("worktree")
    w.set_defaults(func=area.main_wt)
    jv = sub.add_parser("jev", help="decisão tipada no Jev (TypeSafe System One); sem a chave, sai 2 e o fluxo segue")
    jv.add_argument("preset", choices=sorted(jev.PRESETS), help="rotear | revisar-diff | humano | handoff")
    jv.add_argument("--state", default=None, help="state (texto). Também aceita stdin")
    jv.add_argument("--state-file", default=None, help="arquivo com o state (texto ou JSON)")
    jv.add_argument("--root", default=None, help="repo para ler .hdev/config.json (jev.ref, jev.model)")
    jv.add_argument("--ref", default=None, help="referência op:// da chave (padrão: config ou item typesafe - jev api)")
    jv.add_argument("--model", default=None, help="modelo Jev (padrão: jev-latest)")
    jv.add_argument("--dry-run", action="store_true", help="mostra o pedido e não chama a API")
    jv.add_argument("--json", action="store_true", help="JSON compacto (já é o padrão da saída)")
    jv.set_defaults(func=jev.main)

    cx = sub.add_parser("codex-exec", help="Codex não interativo: exec --json --approve-for-me")
    cx.add_argument("prompt", nargs="?", default=None)
    cx.add_argument("--prompt-file", default=None)
    cx.add_argument("--cd", default=None, help="cwd do agente (padrão: a pasta atual)")
    cx.add_argument("--model", default=None)
    cx.add_argument("--timeout", type=int, default=600)
    cx.add_argument("--titulo", default=None, help="1ª linha do pedido: hdev codex-exec: <título> (ADR 0007)")
    cx.add_argument("--isolar", action="store_true", help="roda numa cópia em /tmp, fora das áreas (revisor)")
    cx.set_defaults(func=wrappers.main_codex)

    gk = sub.add_parser("grok-review", help="Grok não interativo: --output-format json --always-approve --single")
    gk.add_argument("prompt", nargs="?")
    gk.add_argument("--prompt-file", default=None)
    gk.add_argument("--cd", default=None)
    gk.add_argument("--model", default=None)
    gk.add_argument("--timeout", type=int, default=600)
    gk.add_argument("--titulo", default=None, help="1ª linha do pedido: hdev grok-review: <título> (ADR 0007)")
    gk.add_argument("--sem-isolar", action="store_true", help="roda no repo (padrão: cópia isolada em /tmp)")
    gk.set_defaults(func=wrappers.main_grok)

    ho = sub.add_parser("handoff", help="grava o resumo em progress.md e abre a sessão nova (WebSocket nova)")
    ho.add_argument("--root", default=None)
    ho.add_argument("--dry-run", action="store_true")
    ho.add_argument("--estado", default="")
    ho.add_argument("--proximo", default="")
    ho.add_argument("--decisoes", default="")
    ho.add_argument("--bloqueios", default="")
    ho.add_argument("--texto", default=None, help="texto da sessão nova (padrão: o do orquestrador)")
    ho.add_argument("--sem-jev", action="store_true")
    ho.set_defaults(func=handoff.main)

    rs = sub.add_parser("resume", help="grava PAREI (lista fechada) ou lê o próximo passo e a fila de retentativa")
    rs.add_argument("--root", default=None)
    rs.add_argument("--reason", default=None, help="motivo; PAREI só se for da lista fechada")
    rs.add_argument("--next", dest="next_step", default=None, help="próximo passo depois da parada")
    rs.add_argument("--blocked-on", default=None, help="marca a unidade bloqueada nesta dependência; pede --next")
    rs.set_defaults(func=stop.main)

    g = sub.add_parser("graph", help="cache de código em .hdev/cache/graph (só AST)")
    gsub = g.add_subparsers(dest="graph_command", required=True)
    gu = gsub.add_parser("update", help="atualiza .hdev/cache/graph; sem o binário, avisa e sai 0")
    gu.add_argument("--root", default=None)
    gu.add_argument("--force", action="store_true", help="refaz mesmo com o sha igual ao HEAD")
    gu.set_defaults(func=graphmod.update_main)

    im = sub.add_parser("impact", help="quem chama ou importa o arquivo, e o que ele chama ou importa")
    im.add_argument("file")
    im.add_argument("--root", default=None)
    im.set_defaults(func=graphmod.impact_main)

    lib = sub.add_parser("library", help="biblioteca de lições: pull, status, tidy")
    lsub = lib.add_subparsers(dest="library_command", required=True)
    pl = lsub.add_parser("pull", help="traz poucas lições da spec ou do sintoma")
    pl.add_argument("--spec", default=None)
    pl.add_argument("--symptom", default=None)
    pl.add_argument("--k", type=int, default=5)
    pl.add_argument("--budget", type=int, default=1500)
    pl.add_argument("--unit", default=None)
    pl.add_argument("--tag", default=None)
    pl.add_argument("--root", default=None)
    pl.add_argument("--today", default=None)
    pl.set_defaults(func=main_library)
    st = lsub.add_parser("status", help="contagem e quem está elegível pra core")
    st.add_argument("--root", default=None)
    st.add_argument("--today", default=None, help="data YYYY-MM-DD para o ciclo")
    st.set_defaults(func=main_library)
    td = lsub.add_parser("tidy", help="promove, aposenta e apaga; repetir não muda")
    td.add_argument("--root", default=None)
    td.add_argument("--today", default=None, help="data YYYY-MM-DD para o ciclo")
    td.set_defaults(func=main_library)

    rf = sub.add_parser("reflect", help="digest da unidade, ou --add para gravar lições")
    rf.add_argument("--unit", default=None)
    rf.add_argument("--plan", default=None)
    rf.add_argument("--add", default=None, help="JSON com os itens a validar e gravar")
    rf.add_argument("--offline", action="store_true", help="não chama o segundo modelo; fica pending")
    rf.add_argument("--today", default=None)
    rf.add_argument("--root", default=None)
    rf.set_defaults(func=main_reflect)

    return p

def main(argv=None):
    args = parser().parse_args(argv)
    if getattr(args, "root", "unset") is None:
        args.root = _default_root()
    pathmod.load_dotenv(getattr(args, "root", None) or CORE_ROOT)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
