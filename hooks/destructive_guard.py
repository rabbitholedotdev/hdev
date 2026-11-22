#!/usr/bin/env python3
# hdev-alias: destructive_guard → harness.hooks.pre_tool.destructive_main
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from harness.hooks.pre_tool import destructive_main

if __name__ == "__main__":
    sys.exit(destructive_main() or 0)
