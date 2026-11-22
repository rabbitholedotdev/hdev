#!/usr/bin/env python3
# hdev-alias: progress_guard → harness.hooks.stop_gate.progress_main
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness.hooks.stop_gate import progress_main

if __name__ == "__main__":
    sys.exit(progress_main() or 0)
