#!/usr/bin/env python3
"""Runs server.py and bot.py as one Render service.
server.py hosts the health check Render polls, so it must never go down
just because bot.py crashed. Each process is restarted independently on
crash, with backoff, instead of taking the whole service down."""
import subprocess
import sys
import time

SCRIPTS = ["server.py", "bot.py"]
MAX_BACKOFF = 60


def spawn(script):
    return subprocess.Popen([sys.executable, "-u", script])


procs = {script: spawn(script) for script in SCRIPTS}
backoff = {script: 1 for script in SCRIPTS}

while True:
    for script, p in list(procs.items()):
        code = p.poll()
        if code is not None:
            wait = backoff[script]
            print(f"[run.py] {script} exited with code {code}, restarting in {wait}s", flush=True)
            time.sleep(wait)
            procs[script] = spawn(script)
            backoff[script] = min(wait * 2, MAX_BACKOFF)
        else:
            backoff[script] = 1
    time.sleep(2)
