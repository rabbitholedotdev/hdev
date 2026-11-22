"""Juiz como pacote. `hdev.judge` reexporta daqui para não quebrar quem já importa."""
from .constants import (
    CODE_EXT, DOC_EXT, EVIDENCE_DIR, EVIDENCE_REF_RX, EXIT, LABELS_DIR, LABELS_NEEDED,
    MAX_EVIDENCE_FILE, MAX_HEAD, MAX_MANIFEST, MAX_MOVES_NOTE, MAX_PACKAGE, MAX_PARTS,
    MAX_UNTRACKED_FILE, PARALLEL, PART_READ_CAP, PARTS_NOTE, PROMPT_VERSION, RENAME_ARGS, RUBRIC,
)
from .evidence import (
    check_evidence_refs, check_text, evidence, evidence_items, piece_evidence, plan_evidence_tokens,
    run_tests, unit_evidence_dir,
)
from .gitdiff import (
    JudgeError, collect_diff, commit_text, criterion_from_plan, diff_stat, filtered_diff, resolve_commit,
)
from .package import build_package, build_packages, fit_diff, split_parts
from .run import call_judge, judge, judged_refs, main, previous_runs, record
from .verdict import count_labels, diagnose, parse_verdict, tokens_from, valid_label

__all__ = [
    "CODE_EXT", "DOC_EXT", "EVIDENCE_DIR", "EVIDENCE_REF_RX", "EXIT", "JudgeError", "LABELS_DIR",
    "LABELS_NEEDED", "MAX_EVIDENCE_FILE", "MAX_HEAD", "MAX_MANIFEST", "MAX_MOVES_NOTE", "MAX_PACKAGE",
    "MAX_PARTS", "MAX_UNTRACKED_FILE", "PARALLEL", "PART_READ_CAP", "PARTS_NOTE", "PROMPT_VERSION",
    "RENAME_ARGS", "RUBRIC", "build_package", "build_packages", "call_judge", "check_evidence_refs",
    "check_text", "collect_diff", "commit_text", "count_labels", "criterion_from_plan", "diagnose",
    "diff_stat", "evidence", "evidence_items", "filtered_diff", "fit_diff", "judge", "judged_refs",
    "main", "parse_verdict", "piece_evidence", "plan_evidence_tokens", "previous_runs", "record",
    "resolve_commit", "run_tests", "split_parts", "tokens_from", "unit_evidence_dir", "valid_label",
]
