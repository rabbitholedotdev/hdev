"""Compatibilidade: `import hdev.judge` segue valendo.

A implementação mora em `hdev.gates.judge`. Este arquivo só reexporta, para a CLI, o fechar
e os testes não trocarem de caminho. `subprocess` e `cli_runtime` ficam aqui porque os testes
patcham os dois neste módulo (o patch de `subprocess.run` vale para o pacote, que chama o
mesmo módulo).
"""
import subprocess

from hdev import cli_runtime
from hdev.gates.judge import (  # noqa: F401
    CODE_EXT, DOC_EXT, EVIDENCE_DIR, EVIDENCE_REF_RX, EXIT, LABELS_DIR, LABELS_NEEDED,
    MAX_EVIDENCE_FILE, MAX_HEAD, MAX_MANIFEST, MAX_MOVES_NOTE, MAX_PACKAGE, MAX_PARTS,
    MAX_UNTRACKED_FILE, PARALLEL, PART_READ_CAP, PARTS_NOTE, PROMPT_VERSION, RENAME_ARGS, RUBRIC,
    JudgeError, build_package, build_packages, call_judge, check_evidence_refs, check_text,
    collect_diff, commit_text, count_labels, criterion_from_plan, diagnose, diff_stat, evidence,
    evidence_items, filtered_diff, fit_diff, judge, judged_refs, main, parse_verdict, piece_evidence,
    plan_evidence_tokens, previous_runs, record, resolve_commit, run_tests, split_parts, tokens_from,
    unit_evidence_dir, valid_label,
)
