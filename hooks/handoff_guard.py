#!/usr/bin/env python3
# hdev-alias: handoff_guard → harness.hooks.session.handoff_main
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness.hooks.session import handoff_main

if __name__ == "__main__":
    sys.exit(handoff_main() or 0)
