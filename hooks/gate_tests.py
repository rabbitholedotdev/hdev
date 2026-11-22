#!/usr/bin/env python3
# hdev-alias: gate_tests → harness.hooks.stop_gate.gate_main
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness.hooks.stop_gate import gate_main

if __name__ == "__main__":
    sys.exit(gate_main() or 0)
