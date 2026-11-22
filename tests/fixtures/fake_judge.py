"""Juiz falso para testes: lê o pacote no stdin e responde conforme argv[1].

pass | fail | unsure → JSON com o veredito; lixo → texto sem JSON; dorme → passa do timeout;
pede-criterio → pass só se o pacote tiver a seção de critério e a rubrica; pass-exit1 → JSON pass com exit 1;
fail-parte-2 → fail só na parte 2 do diff;
grok-arquivo → imita o argv do grok real (pacote em --prompt-file, sem -p vazio).
"""
import json
import sys
import time

mode = sys.argv[1] if len(sys.argv) > 1 else "pass"
package = sys.stdin.read()
if mode == "lixo":
    print("quota exceeded, tente depois")
    sys.exit(1)
if mode == "login":
    print("not logged in", file=sys.stderr)
    sys.exit(1)
if mode == "dorme":
    time.sleep(10)
if mode == "fail-parte-2":
    mode = "fail" if "=== DIFF (parte 2/" in package else "pass"
if mode == "pede-criterio":
    ok = "=== CRITÉRIO DE PRONTO" in package and "=== DIFF" in package and "CRITERIO_X" in package
    mode = "pass" if ok else "fail"
if mode == "pass-exit1":
    print(json.dumps({"verdict": "pass", "reasons": ["CLI quebrou depois de responder"]}))
    print("STDERR_DIAGNOSTICO chave=%s" % ("AK" + "IA" + "Q" * 16), file=sys.stderr)
    sys.exit(1)
if mode == "grok-arquivo":
    # Contrato do grok real: o pacote vem em --prompt-file <PATH>, não no stdin; -p sem valor é erro de uso.
    args = sys.argv[2:]
    if "-p" in args or "--single" in args or "--prompt-file" not in args:
        print("error: a value is required for '--single <PROMPT>'", file=sys.stderr)
        sys.exit(2)
    with open(args[args.index("--prompt-file") + 1], encoding="utf-8") as f:
        from_file = f.read()
    verdict = "pass" if "CRITERIO_X" in from_file and "=== DIFF" in from_file else "fail"
    print(json.dumps({"type": "result", "result": json.dumps({"verdict": verdict, "reasons": ["arquivo"]})}))
    sys.exit(0)
if mode == "eco":
    # Imita o codex: ecoa o pacote no stderr (que pode citar "tokens used") e responde sem contar tokens.
    print(package, file=sys.stderr)
    print(json.dumps({"verdict": "pass", "reasons": ["eco"]}))
    sys.exit(0)
if mode.startswith("envelope-"):
    # Imita a CLI grok com --output-format json: o veredito vem como texto dentro do envelope,
    # e o argv precisa trazer o schema (--json-schema).
    verdict = mode.split("-", 1)[1]
    has_schema = "--json-schema" in sys.argv and any('"verdict"' in a for a in sys.argv)
    inner = {"verdict": verdict if has_schema else "fail", "reasons": ["envelope: %s" % verdict]}
    print(json.dumps({"type": "result", "result": json.dumps(inner), "usage": {"output_tokens": 42}}))
    sys.exit(0)
print("pensando... tokens used: 1,234")
print(json.dumps({"verdict": mode, "reasons": ["motivo de teste: %s" % mode]}))
