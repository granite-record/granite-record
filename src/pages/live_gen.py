#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-26.1
"""
The constants the live Worker (workers/live/) takes from this repository,
written into workers/live/live.gen.js from the files that hold them.

    python3 src/pages/live_gen.py            # write it
    python3 src/pages/live_gen.py --check    # say whether it is current; write nothing

ONE SOURCE EACH, as src/pages/follow_site.py does for the email sender: a
value the Worker needs is read here from where the repository keeps it and
written into one plain module the Worker imports, and preflight fails while
the committed file differs from what this would write. The live layer's
design (26 October 2026, approved by the person as "defaults") names this
file and this pattern in its section 6.2.

    SQL_LOGIN     probe_db.py's DATABASE, USER and PASSWORD: the read-only
                  login the General Court publishes for its public SQL
                  database. Published, so not a secret (SECURITY.md says
                  so). THE HOST IS DELIBERATELY NOT HERE. It is named in
                  workers/live/wrangler.toml under production alone, so
                  that nothing a local run or a test imports can reach it.
    VOTE_WORD     fetch_rollcalls_db.py's VOTE_WORD: a ballot's code in
                  RollCallHistory, and the record's word for it
    BALLOT_CHAR   VOTE_WORD's codes as the live votes file's one character
                  a ballot (design section 2.5): Y Yea, N Nay, E excused,
                  X not excused, P presiding, and . for no vote recorded

probe_db.py and fetch_rollcalls_db.py are READ AS TEXT, never imported:
both are scripts that ask the General Court's database, and writing a
constants file should not load one. Their assignments are read with ast,
so a value written another way stops this with its name rather than being
guessed at. A word VOTE_WORD gains that BALLOT_CHARS below does not know
stops it too: what a new code means on the page is a decision, not a
default.

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import ast
import json

OUT = Path("workers/live/live.gen.js")
COMMAND = "python3 src/pages/live_gen.py"

PROBE_DB = Path("src/fetch/gc_db/probe_db.py")
ROLLCALLS_DB = Path("src/fetch/gc_db/fetch_rollcalls_db.py")

# The record's words for a ballot, as the live file's one character each.
# "" and "No vote recorded" are VOTE_WORD's words for codes 0, 5 and 7.
BALLOT_CHARS = {"Yea": "Y", "Nay": "N", "Not Voting/Excused": "E",
                "Not Voting/Not Excused": "X", "Presiding": "P",
                "": ".", "No vote recorded": "."}


class SourceError(ValueError):
    """A source no longer says a value where, or how, this reads it."""


def _base(root):
    return Path(root) if root is not None else _paths.ROOT


def assigned(path, names, root=None):
    """{name: value} of the top-level `NAME = <literal>` assignments in a
    Python file, read without importing it."""
    p = _base(root) / path
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as e:
        raise SourceError(f"{path.as_posix()} will not read ({e})")
    got = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            try:
                got[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                raise SourceError(f"{path.as_posix()}'s {node.targets[0].id} is not a plain value")
    missing = [n for n in names if n not in got]
    if missing:
        raise SourceError(f"{path.as_posix()} no longer assigns {', '.join(missing)} at the top level")
    return got


def published_login(root=None):
    """probe_db.py's DATABASE, USER and PASSWORD, read as text."""
    v = assigned(PROBE_DB, ("DATABASE", "USER", "PASSWORD"), root)
    if not all(isinstance(x, str) and x for x in v.values()):
        raise SourceError(f"{PROBE_DB.as_posix()}'s DATABASE, USER or PASSWORD is not a word")
    return {"database": v["DATABASE"], "user": v["USER"], "password": v["PASSWORD"]}


def values(root=None):
    """{export name: (where it comes from, value)}, in the file's order."""
    words = assigned(ROLLCALLS_DB, ("VOTE_WORD",), root)["VOTE_WORD"]
    if not isinstance(words, dict) or not words or \
            not all(isinstance(k, str) and k.isdigit() and isinstance(w, str) for k, w in words.items()):
        raise SourceError(f"{ROLLCALLS_DB.as_posix()}'s VOTE_WORD is not {{code: word}}")
    unknown = sorted({w for w in words.values() if w not in BALLOT_CHARS})
    if unknown:
        raise SourceError(f"VOTE_WORD has a word the live file has no character for: {unknown}; "
                          f"add it to live_gen.BALLOT_CHARS once its meaning on the page is decided")
    return {
        "SQL_LOGIN": (f"{PROBE_DB.as_posix()}: DATABASE, USER and PASSWORD, the read-only login the "
                      f"General Court publishes. The host is not here: wrangler.toml names it under "
                      f"production alone", published_login(root)),
        "VOTE_WORD": (f"{ROLLCALLS_DB.as_posix()}: VOTE_WORD, a ballot's code and the record's word",
                      dict(sorted(words.items(), key=lambda kv: int(kv[0])))),
        "BALLOT_CHAR": ("VOTE_WORD's codes as the live file's one character: Y Yea, N Nay, "
                        "E excused, X not excused, P presiding, . no vote recorded "
                        "(src/pages/live_gen.py BALLOT_CHARS)",
                        {k: BALLOT_CHARS[w] for k, w in sorted(words.items(), key=lambda kv: int(kv[0]))}),
    }


def render(root=None):
    """The text of workers/live/live.gen.js, from the sources as they stand."""
    lines = [
        "// WRITTEN BY src/pages/live_gen.py FROM THE REPOSITORY'S OWN FILES. Do not edit it:",
        "// change the value where the comment above it says it comes from, then run",
        f"//     {COMMAND}",
        "// and commit this file with the change. preflight fails while it differs from",
        "// what that command would write.",
        "",
    ]
    for name, (source, value) in values(root).items():
        lines += [f"// {source}.", f"export const {name} = {json.dumps(value, ensure_ascii=False)};"]
    return "\n".join(lines) + "\n"


def current(root=None):
    """(whether the committed file is what render() writes, the reason if not)."""
    path = _base(root) / OUT
    if not path.is_file():
        return False, f"{OUT.as_posix()} is not there"
    # read_text reads a checkout's CRLF as LF: autocrlf is on for the laptop.
    if path.read_text(encoding="utf-8") == render(root):
        return True, ""
    return False, f"{OUT.as_posix()} is not what the repository's files say now"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--check", action="store_true", help="say whether the file is current; write nothing")
    a = ap.parse_args()
    try:
        text = render()
    except SourceError as e:
        print(f"live_gen: {e}", file=sys.stderr)
        return 2
    path = _paths.ROOT / OUT
    if a.check:
        ok, why = current()
        print(f"{OUT.as_posix()} is current" if ok else f"{why}: run {COMMAND}")
        return 0 if ok else 1
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        print(f"{OUT.as_posix()} is current; nothing written")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.as_posix()}: {', '.join(values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
