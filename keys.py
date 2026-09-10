#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.1
"""
The one place a credential is read from, and it is not the command line.

    import keys
    api = keys.youtube()            # raises with instructions if absent

WHY A FILE AND NOT A FLAG

fetch_channel_index.py took --key. An argument on a command line is visible to
every process on the machine -- `Get-CimInstance Win32_Process` prints the full
command line of everything running, which is how six stacked review.py
processes were found in this project -- and it lands in shell history, in the
scrollback, and in any log that echoes the command. A key that is typed once
into a gitignored file is exposed to none of that.

WHY IT MATTERS MORE HERE THAN USUALLY

This repository is meant to be shared. A key committed once is a key that
lives in the history forever, and rewriting published history is not something
anyone does calmly at the point they notice. secrets.json is in .gitignore,
secrets.example.json shows the shape, and preflight fails if a tracked file
ever starts to look like it holds a key.

WHAT IS DELIBERATELY NOT SECRET

probe_db.py carries the General Court's database host, user and password in
the open. Those are published by the General Court in "ODBC and Data Table
Structure.pdf" at gc.nh.gov/downloads, for public use, against a read-only
account. Hiding a published credential would not protect anything and would
stop somebody reproducing this work from the same sources.
"""

import json
from pathlib import Path

PATH = Path(__file__).resolve().parent / "secrets.json"
EXAMPLE = "secrets.example.json"


def _load():
    if not PATH.exists():
        raise SystemExit(
            f"No {PATH.name}. Copy {EXAMPLE} to {PATH.name} and fill it in.\n"
            f"It is in .gitignore and will not be committed.")
    try:
        return json.loads(PATH.read_text(encoding="utf-8"))
    except ValueError as e:
        raise SystemExit(f"{PATH.name} is not valid JSON: {e}")


def get(name, what=""):
    """One value, or an error that says what to do about it."""
    v = (_load().get(name) or "").strip()
    # A placeholder left in from the example is not a key, and failing later
    # against the API with "invalid credential" hides where it came from.
    if not v or v.startswith("your "):
        raise SystemExit(
            f"{PATH.name} has no usable {name}." + (f" {what}" if what else ""))
    return v


def youtube():
    return get("youtube_api_key",
               "Get one at console.cloud.google.com, enable YouTube Data "
               "API v3, and restrict the key to that API.")
