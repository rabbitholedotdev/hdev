# Evidência — colisão

Aviso, não bloqueio. Outra sessão mexeu em `hdev/a.py` há 1 min. Com 31 min, não avisa.

HEAD `ed1013bdd5c2050f3d02dd76d20907bfdce6d98a`. Diretório temporário; `CLAUDE_PROJECT_DIR` aponta para ele.

```
$ python3 -c 'import json,time,os,sys
d=sys.argv[1]
os.makedirs(os.path.join(d,".hdev","state"))
open(os.path.join(d,".hdev","state","touches.jsonl"),"w").write(json.dumps({"session":"outra","path":"hdev/a.py","ts":time.time()-60,"unit":"v2-pr5-hooks"})+"\n")' "$d"
$ printf '%s' '{"tool_name":"Edit","tool_input":{"file_path":"hdev/a.py"},"session_id":"esta","cwd":"'"$d"'"}' | CLAUDE_PROJECT_DIR="$d" python3 harness/hooks/pre_tool.py
```

stdout:

```
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "pre_tool: colisão: hdev/a.py foi mexido pela sessão outra há 1 min (unidade v2-pr5-hooks, outra sessão da Ratoeira)."}}
```

stderr:

```
pre_tool: colisão: hdev/a.py foi mexido pela sessão outra há 1 min (unidade v2-pr5-hooks, outra sessão da Ratoeira).
```

exit=0

O mesmo Edit com o toque há 31 min sai 0 e não imprime `colisão`.
