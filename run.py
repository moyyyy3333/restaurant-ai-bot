#!/usr/bin/env python3
"""Runs server.py and bot.py together as one Railway service.
If either dies, exit so Railway restarts the whole service."""
import subprocess
import sys
import time

procs = [
    subprocess.Popen([sys.executable, "-u", "server.py"]),
    subprocess.Popen([sys.executable, "-u", "bot.py"]),
]

while True:
    for p in procs:
        code = p.poll()
        if code is not None:
            sys.exit(code)
    time.sleep(2)
