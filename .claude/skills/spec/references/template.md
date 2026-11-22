# Molde da spec

Leia este arquivo só no passo 2. O `hdev spec check` exige as três peças: aceite com comando, fora de escopo e a tabela.

```
# Spec — <id>

## Aceite
- `bin/hdev check` sai 0
- `<outro comando que roda>` sai 0

## Fora de escopo
- <o que esta peça não faz>

## Dúvidas

| Dúvida | Default | Reverter |
| --- | --- | --- |
| <ponto que não foi perguntado> | <padrão anunciado> | <como voltar atrás> |
```

O aceite cita comando de verdade (com argumento), em crase ou em bloco. Default vazio, `?` ou «perguntar» faz o check sair 3: o dono preenche antes de seguir.
