# Evidência — corte de saída

80 linhas no PostToolUse. O modelo recebe cabeça, a linha de erro e a cauda. O texto inteiro fica no arquivo.

HEAD `ed1013bdd5c2050f3d02dd76d20907bfdce6d98a`.

```
$ CLAUDE_PROJECT_DIR="$d" python3 harness/hooks/session.py < evento.json
```

O evento é PostToolUse, Bash, `tool_response` com `linha 0` … `linha 79` e `ERROR: estourou` no meio.

exit=0

Trecho de `updatedToolOutput`:

```
[corte] saída completa: .hdev/state/tool-output/s-1795124409848606166.log
linha 0
...
linha 29
... linhas de erro ...
ERROR: estourou
... cauda ...
linha 60
...
linha 79
```

`linha 50` não está nesse texto. O arquivo tem 717 bytes e contém `linha 50`.
