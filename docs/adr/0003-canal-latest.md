# ADR 0003 — Canal latest para os consumidores do harness

- Status: aceito (João, 14/11/2026, America/Sao_Paulo: "tudo que usa o harness usa sempre a versão mais recente sem eu ter que atualizar"; "manda ver")
- Área: núcleo / `hdev init`, `hdev release`, `hdev pin`, `hdev rollback`
- Complementa a ADR 0002 (a release continua imutável e por tag).

## Decisão
1. As releases saem do checkout do núcleo: na Ratoeira, `/opt/harness-dev/releases` (fora da ACL das áreas e fora de `$HDEV_HOST_PREFIX`, que é trocado nas atualizações). O caminho vem de `HDEV_RELEASES_DIR` ou de `<núcleo>/.hdev/state/releases-dir`.
2. `<releases>/latest` aponta para a última release promovida. Apps no canal ligam `.harnessdev` a `latest` e recebem cada release sem init nem commit.
3. Promover exige `hdev judge` pass cujo head é o commit da tag (ou ancestral com só docs/versão no meio). Sem juiz, a release fica instalada e o canal não anda.
4. `hdev rollback` devolve o canal a uma release já promovida; `hdev pin` fixa um app (ADR 0002 continua valendo para quem fixar).
5. O init escreve por referência (AGENTS.md importa o perfil da release; config do app só com o que é dele), para regra nova do núcleo chegar sem sobrescrever customização.

## Consequências
- Uma release ruim chega a todos os apps do canal de uma vez: o juiz é o portão e o rollback é um comando.
- `.harnessdev.lock` no canal registra a versão e o commit efetivos de `latest`. A promoção não reescreve o arquivo do app; o próximo `hdev init` (sem `--force`) atualiza só esses campos. Quem aponta a release em uso continua sendo o symlink `latest`.
- Hooks continuam por referência (`.harnessdev/hooks/`); a lista de hooks registrada no `.claude/settings.json` do app não muda sozinha.
