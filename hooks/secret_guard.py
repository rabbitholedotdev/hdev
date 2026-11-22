#!/usr/bin/env python3
# hdev-alias: secret_guard → harness.hooks.pre_tool.secret_main
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness.hooks.pre_tool import secret_main

if __name__ == "__main__":
    sys.exit(secret_main() or 0)
