# Plano — CHIP-002 (a etiqueta do app também barra escrita por interpretador)

Spec: sem spec (decisão do dono, 21/11: interpretador "PR para fechar")

## Objetivo
Na v0.8.2, com a etiqueta de um app deste repo (`<ratoeira-contexto>`), o `pre_tool.py` barra Write, Edit, MultiEdit, NotebookEdit e a escrita comum do shell em código do repo. A escrita por interpretador passava: `python3 -c "open('mcc/x.js','w')..."`, `node -e "fs.writeFileSync(...)"`, `python3 - <<EOF`. Esta unidade fecha esse buraco sem barrar todo interpretador: a leitura (`python3 -c "import json; print(...)"`) segue passando.

## Como
- `_interp_write` (em `harness/hooks/pre_tool.py`) acha o código inline de `python`/`python3*` `-c`, `node -e/-p/--eval/--print`, `perl -e/-E` (sem `-i`; o `-i` já barra), `ruby -e`. Script pelo stdin (`python3 -`, `python3 <<EOF`, `... | python3`, `<<<`) conta o comando inteiro, com o corpo do heredoc.
- `WRITE_CODE` é a heurística de escrita: `open(..., 'w'|'a'|'x'|'+')`, `.open('w')`, `open` do perl com `>`/`+<`, `write_text`/`write_bytes`, `touch`, `os.remove/replace/removedirs`, `shutil.*` (menos `which`, `disk_usage`, `get_terminal_size`), `writeFile*`/`appendFile*`/`unlink*`/`rename*`/`mkdir*`/`rm*Sync`/`createWriteStream`/`fs.write`, `File.write`/`IO.write`/`File.delete`/`FileUtils.*`, e `unlink`/`rename`/`rmdir`/`mkdir` do perl sem parênteses.
- `bash -c`/`sh -c`/`zsh -c`/`dash -c` passam o comando de dentro pelo mesmo detector (`chip_write_target`), com o cwd do trecho. `bash <<EOF` passa o corpo.
- O alvo da escrita por interpretador não é resolvido: conta como código, como o cwd desconhecido já conta como a raiz. Para escrever fora do repo com a etiqueta, use Write ou `>` para `/tmp`.
- O corte em trechos passa a respeitar aspas (`_quote_safe`) e tira o corpo dos heredocs (`_heredocs`). Sem isso, `python3 -c "print(1 > 0)"`, `node -e "x => x"` e um heredoc com `>` eram barrados por engano (o `>` de dentro virava redirecionamento). `"$(...)"` entre aspas duplas segue cortando.

## Critério de pronto
- `python3 -m unittest tests.test_hooks.AppChip -v` sai 0 com os 7 casos. O caso novo `test_interpretador_barra_escrita_e_libera_leitura` barra 14 escritas por interpretador (python/python3/python3.11 -c, node -e/--eval, perl -e, ruby -e, bash -c, sh -c com cd, env -C, heredoc para python3, cat heredoc | python3, bash heredoc) e libera 8 leituras (json com open sem modo, `print(... > 0)`, `x => x > 1`, `perl -ne`, `File.read`, `bash -c 'cat ... | wc'`, heredoc de leitura, saída redirecionada para `/tmp`); sem etiqueta, as 14 passam.
- `python3 -m unittest discover -s tests -q` sai 0, com a contagem (`Ran N tests`, `OK`).
- `bin/hdev check` sai 0.
- `bin/hdev sync --check` sai 0 (o manifesto de hooks não muda).
- `bin/hdev fechar --plan docs/plan-chip-002-interpretador.md --dry-run` sai 0.
- [juiz] cada item tem comando e saída no log de evidência deste commit.

## Fora de escopo
- Manifesto de hooks (`.hdev/config.json` `hooks`) e o matcher do PreToolUse: não mudam (REL-082).
- Escrita por `subprocess`/`os.system`/`child_process` e por script em arquivo (`python3 x.py`): passa (shortcut no código).
- Release e promoção do `latest`: com o sim do João, depois do merge.
