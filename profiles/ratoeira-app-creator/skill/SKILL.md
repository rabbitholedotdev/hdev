---
name: ratoeira-app-creator
description: "Cria ou muda um app da Ratoeira, da ideia ao publicado. Use quando pedirem um app, painel ou quadro na Ratoeira."
---

# ratoeira-app-creator

O contrato é o `APPS.md` do host (`$HDEV_APPS_MD`) e a skill
do perfil. **Leia o APPS.md antes de codar; ele vence esta skill.** Aqui fica só o que os apps
de verdade mostram e o que o harness confere.

## Da ideia ao ar
1. **Confirmar** (uma mensagem): nome, o que faz, papéis (do que pode mais pro que pode menos), efeitos fora do app,
   se precisa de chat (MCP) e, com mais de uma área, se aparece só na área (`"aparece": "area"`).
2. **Plano** `docs/plan-<app>-<peça>.md` (skill `planejar`, após review go da spec) com os critérios de `criterios.md` deste perfil.
3. **Esqueleto:** `hdev app new <nome> --area <raiz da área>` monta `apps/<nome>/` pelo modelo (Node 22, só stdlib,
   porta livre a partir de 8800). Começar de um app parecido que já existe também vale:
   copie a estrutura, nunca dados.
4. **Construir** na camada de regras (`lib/regras.mjs`): tela e ferramenta chamam as mesmas funções.
5. **Provar (no fechamento, não a cada mudança):** CI roda no CI remoto, não local. Com CI remoto, a prova é o CI do
   PR verde. Sem ele, `npm test` (servidor de verdade, 401 sem identidade, 403 sem o cabeçalho de escrita) roda só
   no fechamento, pelo `hdev judge --run-tests` (clone limpo), ou quando o operador pedir; durante o trabalho, no máximo
   um teste focado para depurar. `hdev app check apps/<nome>` verde. Depois `hdev judge`.
6. **Publicar:** só pelo `publicar_app` do MCP `ratoeira` (admin), sem sudo, unit ou config de gateway. Chave que falta:
   `pedir_chave` ou `definir_chaves_app`, valor nunca na conversa. Pronto só com `estado_publicacao` ok.
7. **Fechar:** README e `agente/AGENTS.md` dizem o que mudou; `comunidade.json` sobe a `versao` se o app é da comunidade.

## Como o operador trabalha (observado, 14/11/2026)
- Pede pelo chat do host, em pt-BR, frases curtas ("faz o que falta", "resolva esses problemas", "procure").
  O host commita cada turno com a frase dele como mensagem: o porquê fica no plano e no `progress.md`, não no commit.
- Trabalha em rajadas (15 commits de apps num dia) e com mais de uma sessão na mesma coisa: confira o que a outra
  sessão já fez antes de mexer ("concilie para não ter conflito").
- Tudo em português: pastas (`tela/`, `teste/`, `lib/`, `migracoes/`, `agente/`), funções (`conferirIdentidade`,
  `abrirBanco`, `criarRegras`), mensagens de erro e textos. Só a CLI `rabbit` é em inglês.
- Stack mínima: Node 22 com `node:http`, `node:sqlite`, `node:test`, quase sem dependência; Python + Flask só quando a
  mídia pede. Sem framework de front: HTML, CSS com tema claro/escuro e JS leve.
- Todo app traz `dev.mjs` (proxy que imita a Ratoeira), um `teste/app.test.mjs` de ponta a ponta, rotina `backup`
  diária do SQLite guardando 14 dias, `memoria` 256M e `cpu` 25% quando é leve.
- Botões da tela mandam pedidos prontos ao chat (`ratoeira.chat.nova`) dizendo onde estão os dados: o app é feito
  para o agente usar junto.
- README com: Papéis, O que roda, Rodar local, Pôr no ar, Limites conhecidos. `agente/AGENTS.md` com "Onde fica cada
  coisa" (banco, tabelas, pastas). Apps saem prontos para a comunidade (`comunidade.json`, `INSTALAR.md`, prints).
- Segredo só por nome (`chaves`) ou `op://`; nunca valor em arquivo, log ou conversa.
