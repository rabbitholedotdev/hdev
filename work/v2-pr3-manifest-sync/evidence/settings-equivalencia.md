# Evidência — settings, gates, tetos e CLI de área

Comandos rodados na branch `cursor/v2-pr3-manifest-sync-62e5`, no commit `c25f626b4fea9222aece43271c02c8b480dd51b8`. A base é `b1b4809`. O commit que adiciona este arquivo não altera `.claude/settings.json`, `.hdev/config.json` nem `hdev/area.py`.

## Comparação

Comando:

```bash
python3 - << 'PY'
import json, subprocess
base = "b1b4809"
head = "c25f626b4fea9222aece43271c02c8b480dd51b8"
old = json.loads(subprocess.check_output(["git", "show", "%s:.claude/settings.json" % base]))
new = json.loads(subprocess.check_output(["git", "show", "%s:.claude/settings.json" % head]))

def regs(hooks):
    rows = []
    for event, groups in hooks.items():
        for group in groups or []:
            for hook in group.get("hooks") or []:
                rows.append((event, group.get("matcher"), hook.get("type"), hook.get("command"), hook.get("timeout")))
    return sorted(rows)

print("hooks_iguais", regs(old["hooks"]) == regs(new["hooks"]))
print("deny_igual", old["permissions"]["deny"] == new["permissions"]["deny"])
print("allow_antes", len(old["permissions"]["allow"]))
print("allow_depois", len(new["permissions"]["allow"]))
print("--- allow antes ---")
for item in old["permissions"]["allow"]:
    print(item)
print("--- allow depois ---")
for item in new["permissions"]["allow"]:
    print(item)
cfg = json.loads(subprocess.check_output(["git", "show", "%s:.hdev/config.json" % head]))
print("sem_tests", "tests" not in cfg and "tests_command" not in (cfg.get("judge") or {}))
print("gates.fast", json.dumps(cfg["gates"]["fast"]))
print("gates.full", json.dumps(cfg["gates"]["full"]))
print("caps", json.dumps(cfg["caps"], sort_keys=True))
PY
```

Saída (exit 0):

```
hooks_iguais True
deny_igual True
allow_antes 37
allow_depois 15
--- allow antes ---
Bash(python3 -m unittest *)
Bash(python3 -m unittest)
Bash(python -m unittest *)
Bash(python3 -m pytest *)
Bash(python -m pytest *)
Bash(pytest *)
Bash(python3 bin/hdev check *)
Bash(python3 bin/hdev check)
Bash(bin/hdev check *)
Bash(bin/hdev check)
Bash($HDEV_ROOT/bin/hdev check *)
Bash($HDEV_ROOT/bin/hdev check)
Bash(git add *)
Bash(git add)
Bash(git commit *)
Bash(git commit)
Bash(git status *)
Bash(git status)
Bash(git diff *)
Bash(git diff)
Bash(git log *)
Bash(git log)
Edit(.claude/**)
Bash(python3 bin/hdev judge *)
Bash(python3 bin/hdev judge)
Bash(bin/hdev judge *)
Bash(bin/hdev judge)
Bash($HDEV_ROOT/bin/hdev judge *)
Bash($HDEV_ROOT/bin/hdev judge)
Bash(grok --prompt-file *)
Bash(grok -p *)
Bash(grok --json-schema *)
Bash(grok --output-format *)
Bash($HDEV_BIN_DIR/grok --prompt-file *)
Bash($HDEV_BIN_DIR/grok -p *)
Bash($HDEV_BIN_DIR/grok --json-schema *)
Bash($HDEV_BIN_DIR/grok --output-format *)
--- allow depois ---
Bash(bin/hdev check*)
Bash(bin/hdev judge*)
Bash(git add*)
Bash(git commit*)
Bash(git diff*)
Bash(git log*)
Bash(git status*)
Bash(grok -p *)
Bash(grok --json-schema *)
Bash(grok --output-format *)
Bash(grok --prompt-file *)
Bash(pytest *)
Bash(python3 -m pytest*)
Bash(python3 -m unittest*)
Edit(.claude/**)
sem_tests True
gates.fast ["python3", "-m", "unittest", "discover", "-s", "tests", "-q"]
gates.full ["python3", "-m", "unittest", "discover", "-s", "tests", "-v"]
caps {"agents": 80, "hooks": 7, "progress": 2000, "skills": 5, "subagents": 2}
```

`hooks_iguais True` compara evento, matcher, type, command e timeout, ordenados. `deny_igual True` é a lista inteira, na mesma ordem.

## CLI de área

Comando: `git diff --stat b1b4809 c25f626b4fea9222aece43271c02c8b480dd51b8 -- hdev/area.py`

Saída (exit 0): vazia. Nenhum arquivo listado.
