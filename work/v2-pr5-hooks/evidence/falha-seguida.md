# Evidência — comando que já falhou duas vezes

A terceira tentativa do mesmo comando sai 2. As duas primeiras passam.

HEAD `ed1013bdd5c2050f3d02dd76d20907bfdce6d98a`. Diretório temporário. Comando: `python3 -c "import sys; sys.exit(1)"`.

O PostToolUse vai para `harness/hooks/session.py` com `tool_response.exit_code` 1. O PreToolUse vai para `harness/hooks/pre_tool.py`.

```
1 post  exit=0
1 pre   exit=0
2 post  exit=0
2 pre   exit=2
```

stderr da segunda pre:

```
pre_tool: comando já falhou 2 vezes seguidas (python3 -c "import sys; sys.exit(1)"). Segure: diagnostique antes de repetir.
```
