# Changelog

Formato [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/); versões em [SemVer](https://semver.org/lang/pt-BR/).
Em `0.x`: patch = correção compatível; minor = comando, skill, gate ou contrato novo (quebra de contrato também, em
destaque); `1.0.0` declara o contrato estável. Tag anotada `vX.Y.Z` por `hdev release`, igual a `hdev/__init__.py`;
o release exige a seção da versão aqui (ADR 0009).

## [Unreleased]

## [0.8.4] - 2026-11-21
### Mudado
- O matcher do PreToolUse de edição volta a ter `NotebookEdit` (`Write|Edit|MultiEdit|NotebookEdit|Read|AskUserQuestion`) no manifesto e no `.claude/settings.json` do núcleo (NBK-002), e a etiqueta do app também barra o NotebookEdit. Com a tolerância da 0.8.3, o `hdev check` dos apps segue verde com o matcher antigo; cada app recebe o novo no próximo `hdev sync`.

## [0.8.3] - 2026-11-21
### Mudado
- No app, o `hdev check` (linha `sync`) e o `hdev sync --check` aceitam o matcher do PreToolUse de edição com ou sem `NotebookEdit` (NBK-001). Isso prepara a release que põe o `NotebookEdit` no manifesto sem deixar o check dos apps vermelho; cada app faz o `hdev sync` quando fizer merge da main. O núcleo segue estrito, e a tolerância sai quando nenhum app tiver o matcher antigo.

### Corrigido
- A etiqueta do app também barra escrita por interpretador em código do repo: `python`/`python3 -c`, `node -e`, `perl -e`, `ruby -e`, script pelo stdin ou heredoc (`python3 - <<EOF`) e `bash -c`/`sh -c` (o comando de dentro passa pelo mesmo detector). Vale a heurística de escrita no código (`open(..., 'w')`, `write_text`, `writeFileSync`, `os.remove`, `shutil.*`...); leitura passa. O alvo não é resolvido: conta como código.
- Com a etiqueta, leitura por interpretador com `>` no código (`print(a > b)`, `x => x`, heredoc) deixa de ser barrada: o corte do comando respeita aspas e tira o corpo dos heredocs.

## [0.8.2] - 2026-11-21
### Corrigido
- O matcher do PreToolUse de edição volta a `Write|Edit|MultiEdit|Read|AskUserQuestion`. Na v0.8.1 ele ganhava `NotebookEdit` no manifesto, e o `.claude/settings.json` rastreado de cada app ficava diferente do manifesto: o `hdev check` saía 1 na linha `sync` até cada app rodar `hdev sync` e commitar. A v0.8.1 ficou 22 s no `latest` e voltou. A etiqueta do app segue barrando Write, Edit e MultiEdit; o `NotebookEdit` só é barrado onde o matcher já o inclui.

## [0.8.1] - 2026-11-21
### Adicionado
- Etiqueta do app da Ratoeira (`<ratoeira-contexto>` no prompt): conversa ligada a um app deste repo (vale a sessão) ou mensagem que marca o app (vale o turno) é de uso do app. O `pre_tool.py` barra Write, Edit, MultiEdit, NotebookEdit e escrita do shell em código do repo (raiz e worktrees; `.hdev/` não conta) e manda abrir sem a etiqueta na pasta do repo. Leitura passa. O app do repo sai do `titulo`/`nome` do `ratoeira-app.json` na raiz ou um nível abaixo. O matcher do PreToolUse ganha `NotebookEdit`.

## [0.8.0] - 2026-11-20
### Adicionado
- Cache de código: `hdev graph update` e o hook de git `scripts/post-commit` gravam `.hdev/cache/graph/` (AST, sem LLM). `hdev impact` e `scripts/affected-tests` leem esse cache; sem ele, avisam e caem na suíte do módulo. A linha `graph` do `hdev check` recusa a consulta fora do explorer.
- 13 rótulos novos do juiz, total 22. Com isso o juiz deixa de ser consultivo (`advisory = labels < LABELS_NEEDED`, que é 20).
- Biblioteca: `hdev library pull`, `hdev library status`, `hdev library tidy` e `hdev reflect`. Lição curta entre peças, com orçamento. O `hdev fechar` pass pontua o pull. O `hdev check` cobra o índice.
- `hdev improve probe`: testa candidatas do harness (overlay em `.hdev/overlays/<id>/`) nos braços plain, base e candidata, com runner `fake`, e só relata em `.hdev/runs/improve-*`. Candidata vira lição `source: improve` na biblioteca. Nada é adotado. `harness/protected.txt` (ADR 0013) e a linha `overlays` do `hdev check` barram candidata em caminho protegido.
- `hdev improve compose --run <registro> --cand <id> [--dry-run]`: candidata `ganharia` vira branch local `improve/<id>` com um commit e os trailers `Harness-Edit:` e `Harness-Probe:`; a lição vira `active` no mesmo commit. Adotar é o merge humano. `hdev improve revert --cand <id>|--commit <rev>` desfaz com commit de revert. O que a candidata pode editar vira regra (ADR 0014).
- Braço real: `hdev eval run --runner claude` e `hdev improve probe --runner claude` rodam o Sonnet (`eval.model`), com travas do clone, `eval.timeout_sec` (600) e o modelo medido por linha.

### Corrigido
- Handoff: o nudge no Stop não segura mais a sessão para sempre. Respeita `stop_hook_active` e não bloqueia com a unidade fechada.
- Caso do `hdev fechar` fora da base: `tests/test_evals.py` só lê caso commitado (`git ls-files`) e o `progress_guard` não conta o `evals/tasks/<id>/task.json` não rastreado. A suíte dentro do checkout volta a passar depois do fechar.
- Handoff: a janela segue o modelo da sessão (`handoff.window_by_model`, modelo → tokens; `window_tokens` fica como reserva). O núcleo mede o `claude-opus-5-5` contra 1.000.000 tokens, não 200.000: o nudge saía em 10% da janela real.

## [0.7.1] - 2026-11-20
### Corrigido
- Depois do handoff, só a sessão que saiu pode encerrar (`stop_session` em `.hdev/state/session.json`). A sessão nova, com a unidade aberta, continua no Stop. A permissão se gasta no primeiro Stop e some no `SessionStart` de outra sessão. `allow_stop: true` sem sessão ligada não libera. O Stop do Codex e do Grok usa o mesmo `stop_gate.py`.
- Toda release nova grava `PROMPT-ORCHESTRATOR.md` (banner de compat) em `hdev release`, `hdev pin` e `install` com `HDEV_RELEASES_DIR`. Release já instalada não se reescreve. `hdev check` falha se o `AGENTS.md` do app liga um `.md` sob `.harnessdev/` que a release pinada não tem.
### Apps
- Quem está na v0.7.0 faz `hdev pin v0.7.1` e `hdev sync`. A pasta `releases/v0.7.0` fica como está.
### Rollback
- `hdev rollback --to v0.7.0` (canal), ou a tag `v0.7.0` no código.

## [0.7.0] - 2026-11-20
### Adicionado
- `hdev triage` e plano em `work/<id>/plan.md` (o id é a pasta; `docs/plan-<tarefa>.md` segue alias). Fora da branch base o `hdev fechar` não cria o marco (#4).
- Manifesto único: `hdev sync` gera `.claude/settings.json`. Skills por fase (`skillOverrides`) (#5, #8).
- Papéis em `harness/prompts/`. A lista de parada é uma: `harness/prompts/_shared/stop-list.md` (#6).
- `hdev resume` grava `PAREI:` (lista fechada) ou devolve o próximo passo. `hdev resume --blocked-on` marca espera de outra faixa.
- Juiz em pacote, com cache por sha (#9). `hdev fechar` roda `gates.full` num clone limpo, em shards, com cache por tree sha (#10).
- `hdev eval` e `hdev xray`. Caso em `evals/tasks/<id>/task.json` (#11).
- Unidade em `.hdev/state/unit.json`. Stop não encerra unidade `open` sem PAREI. `stop.standing_ok` vira `READY-TO-PUBLISH`. Handoff leva plano, brief, permissão, estado e o mesmo modelo.
- `hdev sync` também grava o Stop do Codex (`.codex/hooks.json`) e do Grok (`.grok/hooks/stop.json`), no mesmo `stop_gate.py`.
### Mudado
- Hooks: 3 arquivos e 5 registros. O teto desce de 7 para 5. `hooks/*.py` fica alias (#7).
- Stop: recorte do diff. A suíte inteira fica no `hdev fechar`. Trava esgotada grava `PAREI: gate esgotado (<guard>)`.
- Backlog da base: `work/backlog.md`.
### Removido
- Histórico rastreado de planos, specs e reviews (o conteúdo permanece no git) (#3).
### Apps
- Quem vem da v0.6.0, depois de `hdev pin v0.7.0`, roda `hdev sync`. O sync põe o Stop em 5 registros, grava o Stop do Codex e do Grok, e troca `tests` / `judge.tests_command` por `gates` no config do app. Sem isso o `hdev check` fica vermelho.
### Rollback
- `hdev rollback --to v0.6.0` (canal), ou a tag `v0.6.0` no código.

## [0.6.0] - 2026-11-18
### Mudado
- Padrão `naming.mode = fail` (ADR 0011): nome novo com não-ASCII reprova o `hdev check` sem config. Palavra em
  português sem acento continua só aviso. `warn` e `off` por opt-in no `.hdev/config.json`. Modo desconhecido
  continua caindo em `warn`.
### Rollback
- `hdev rollback --to v0.5.0` (canal), ou a tag `v0.5.0` no código.

## [0.5.0] - 2026-11-16
### Adicionado
- Checagem `names` no `hdev check` (ADR 0011, `docs/padroes/naming.md`): nomes novos de desenvolvimento em inglês.
  Não-ASCII em segmento novo ou na branch; palavra em português sem acento (lista/sufixo) só avisa.
- `hdev check --base REF`; `hdev judge` passa a base da unidade ao check do clone.
- Padrão `naming.mode = warn`: nenhum repo quebra. Para passar um repo a `fail`: `"naming": {"mode": "fail"}` no
  `.hdev/config.json` dele (o núcleo já roda em `fail`).
- Proposta para a v0.6.0 (decisão do João): mudar `DEFAULT_MODE` para `fail` em `hdev/naming.py`, como mudança de
  comportamento.
### Rollback
- `hdev rollback --to v0.4.2` (canal), ou a tag `v0.4.2` no código.

## [0.4.2] - 2026-11-16
### Corrigido
- `hdev judge` não perde mais arquivos em silêncio quando o diff passa do teto (ADR 0010): renames detectados
  (`-M -C`), movimentos puros em lista (`RENOMEADOS SEM MUDANÇA`), diff grande julgado por partes com `MANIFESTO`
  (`judge.max_parts`, padrão 8; `judge.parallel`, padrão 3); `fail` numa parte reprova, `pass` com arquivo fora
  vira `unsure`; o registro traz `pacote` (partes, cortados, omitidos, anexos) e `package_sha`.
- Anexos em `docs/evidence/` casam também pelo id da unidade; anexo citado no plano que não existe ou não casaria
  falha cedo (exit 64), antes de testes e juiz.
- `unsure` traz `diagnostico` e `unsure_seguidos`; pacote idêntico ao do último `unsure` só é rejulgado com
  `--rejulgar`.
### Rollback
- `hdev rollback --to v0.4.1` (canal), ou a tag `v0.4.1` no código.

## [0.4.1] - 2026-11-16
### Corrigido
- No canal latest, `.harnessdev.lock` passa a registrar a versão e o commit da release promovida. A promoção
  continua sem tocar nos apps; o próximo `hdev init` (sem `--force`) atualiza só esses campos. `hdev app tag`
  deixa de anotar um harness antigo (ADR 0003).

## [0.4.0] - 2026-11-15
### Adicionado
- `hdev fechar --plan P`: commit de fechamento `INF-XXX feito: <resumo>; juiz pass|override` com os trailers
  `Unidade`, `Base`, `Head`, `Juiz`/`Override` e `Harness-Versao`. Commits-turno ficam como checkpoints.
- `hdev fechar --squash` opcional (intervalo só local, backup `bkp/<id>-<sha>`, juiz de novo no SHA novo).
- `hdev app tag <app> vX.Y.Z --publicado`: tag anotada `<app>-vX.Y.Z`, só na publicação, imutável.
- `CHANGELOG.md` do núcleo; ADR 0009.
### Mudado
- Fechar exige a base gravada por `hdev base --marcar` (dedução, HEAD e a base do 1º judge não fecham).
- `hdev release` recusa versão sem seção no `CHANGELOG.md`; o commit de versão pode tocar `CHANGELOG.md` sem perder
  o juiz pass para a promoção.
### Rollback
- `hdev rollback --to v0.3.9` (canal), ou a tag `rollback/pre-v0.4.0` no código.

## [0.3.9] - 2026-11-15
- Juiz julga desde a base da unidade (`hdev base`), não desde o último commit-turno (ADR 0008).

## [0.3.8] - 2026-11-15
- Revisor aninhado isolado e `/handoff` consertado (ADR 0007).

## [0.3.7] - 2026-11-15
- Handoff automático de sessão (ADR 0006).

## [0.3.6] - 2026-11-15
- Orquestrador Opus, subagentes, Jev e wrappers Codex/Grok (ADR 0005).

## [0.3.5] - 2026-11-15
- Fluxo spec, review goldfish, TDD e review do diff (ADR 0004).

## Anteriores
- v0.1.0 a v0.3.4: ver as tags `vX.Y.Z`, `docs/progress.md` e `docs/adr/0001` a `0003`.
