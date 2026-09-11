#!/usr/bin/env python3
"""
Keep the text beside the calendars as they land.

Run from the repository root. No network, ever: it reads PDFs already on this
disk and writes the .txt next to them by calling extract_calendar_text.py,
which is a no-op when nothing is missing.

WHY THIS RUNS FOR HOURS

A calendar with no text beside it is on this disk and invisible -- the
hearings parser reads the .txt, not the .pdf, and 696 House calendars from
2002 to 2016 sat unread that way until this morning. The calendar drain is
fetching about 240 more an hour and will run into the evening, so this walks
behind it and keeps the readable set level with the fetched one.

It logs only when it actually extracts something, so a quiet log means
nothing arrived rather than that this died.
"""
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path.cwd()
if not (ROOT / "extract_calendar_text.py").exists():
    sys.exit(f"run this from the repository root; {ROOT} is not it")

LOG = ROOT / "logs" / "extract_watch.log"
EVERY = 20 * 60                      # a pass every twenty minutes
HOURS = 34                           # long enough to outlast the drain


def say(msg):
    line = time.strftime("%H:%M:%S ") + msg
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


(ROOT / "logs").mkdir(exist_ok=True)
say(f"watching for calendars with no text beside them, every "
    f"{EVERY // 60} minutes for {HOURS}h")

deadline = time.time() + HOURS * 3600
passes = total = 0
while time.time() < deadline:
    r = subprocess.run([sys.executable, "extract_calendar_text.py"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    passes += 1
    out = (r.stdout or "") + (r.stderr or "")
    done = 0
    for line in out.splitlines():
        # "697 extracted in 154s, 0 failed"
        if " extracted in " in line:
            try:
                done = int(line.split()[0].replace(",", ""))
            except ValueError:
                done = 0
            say(line.strip())
    if r.returncode != 0:
        say(f"extract_calendar_text exited {r.returncode}; "
            f"last words: {out.strip().splitlines()[-1:]}")
    total += done
    time.sleep(EVERY)

say(f"stopping after {HOURS}h: {passes} passes, {total:,} calendars given "
    f"text. Anything still missing is listed by "
    f"extract_calendar_text.py --check")
