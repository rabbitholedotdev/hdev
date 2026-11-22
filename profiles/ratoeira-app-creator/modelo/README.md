# {{titulo}}

{{descricao}}

## Papéis

- `admin`: tudo, inclusive ver o time.
- `membro`: o próprio uso. É o último da lista: quem não tem papel definido entra com ele.

## O que roda

- `servidor.mjs`: Node 22 só com a stdlib (`node:http`, `node:sqlite`), em `127.0.0.1:$PORTA`, dados em `$DADOS`.
- Rotina `backup`: cópia diária do banco, guarda 14 dias.

## Rodar local

```
npm test          # o servidor de verdade, com identidade assinada como o gateway
npm run dev       # app + proxy que imita a Ratoeira (sem chat)
```

## Pôr no ar

Pelo chat de quem é admin: `publicar_app` com o nome `{{nome}}`; só está no ar depois que `estado_publicacao` der ok.

## Limites conhecidos

- (anote aqui o que o app ainda não faz)
