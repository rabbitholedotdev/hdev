# Padrões que o agente decide sozinho

Fora de `harness/prompts/_shared/stop-list.md`, o agente não pergunta. Escolhe o padrão conservador,
acrescenta uma linha em `docs/decisions.md` e continua.

| Ambiguidade | Padrão conservador |
| --- | --- |
| nome novo | inglês, ASCII, minúsculas e hífen (`docs/padroes/naming.md`) |
| biblioteca dentro da stack | a que o repo já usa; sem dependência nova |
| layout de teste | a pasta de teste que o repo já tem; um teste focado no que mudou |
| escopo menor | o menor corte que cumpre o critério de pronto do plano |
| escolha reversível | a opção mais fácil de desfazer; anotar e seguir |
| lição de outra peça | `hdev library pull` com orçamento; não crescer o AGENTS.md |
| spec sem go | reescrever em outra sessão e outro provedor; não encerrar |
| unidade fechada ou `READY-TO-PUBLISH` | a próxima unidade aberta do backlog |
| juiz esperando outra faixa | `hdev resume --blocked-on "<dependência>" --next "…"` |
| item em `stop.standing_ok` | `READY-TO-PUBLISH` e a próxima unidade |

Unidade aberta (`.hdev/state/unit.json`, status `open`) não encerra a sessão. O handoff leva plano, brief, permissões de pé, estado, próximo passo e o mesmo modelo.

`docs/progress.md` guarda só o estado atual (teto 2.000). Decisão durável não entra lá.
