#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-26.1
"""
What the live Worker (workers/live/) shares with the rest of this repository,
written into workers/live/live.gen.js from where each value is kept.

    python3 src/pages/live_gen.py            # write it
    python3 src/pages/live_gen.py --check    # say whether it is current; write nothing

    CHANNELS       src/fetch/youtube/fetch_channel_index.py CHANNELS: the
                   House's and the Senate's YouTube channel, by chamber
    NIGHT_WINDOWS  refusal.py NIGHT_WINDOWS: the hours, in UTC, the night
                   asks the General Court, which the Worker keeps out of
                   (votes, a later branch: the YouTube half asks YouTube only)
    SESSION_TITLE  here: the beginning of a stream's title stem that makes it
                   a chamber's session stream, "House Session (01/07/2027)"

THE PATTERN WRITTEN WITH ITS STEM. A title's stem is the title without its
date, in lower case, with "&" said as "and" and every run of other
characters made one space (stem() below): "Committee of Conference on SB 534
(05/22/2026" is "committee of conference on sb 534". The Worker's stem
(workers/live/youtube.js) is held to this one on every title in
collected/videos/ by preflight's _live_layer, and SESSION_TITLE is held to
match every title there that begins "House Session" or "Senate Session" and
no other: "Full Committee Work Session" is not a sitting.

READ, NOT IMPORTED. fetch_channel_index.py is a fetcher and refusal.py the
fetch lane's guard, and the Worker needs two literals from them; so each
file is parsed (ast) and the assignment read as a literal, and neither is
imported. A source that no longer assigns its literal where this reads it
stops this with its name rather than writing a file the Worker cannot use.

WHAT A CHANGE TAKES. Change the value where it is kept, run this, and commit
workers/live/live.gen.js with the change. preflight fails while the file
differs from what this would write, and names this command. It is the
workers/follow/site.gen.js pattern (follow_site.py), for the same reason: the
Worker is bundled by wrangler from what git holds, with no build step before
it, so it imports a plain module beside it. Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import ast
import json
import re

OUT = Path("workers/live/live.gen.js")
COMMAND = "python3 src/pages/live_gen.py"

CHANNEL_INDEX = Path("src/fetch/youtube/fetch_channel_index.py")
REFUSAL = Path("refusal.py")
# Every file the written one is made from.
SOURCES = (CHANNEL_INDEX, REFUSAL)

# The chambers by the letter the site and the Worker key them by.
CHAMBER = {"house": "H", "senate": "S"}

# The beginning of a session stream's stem, by chamber: 172 titles in the
# committed indexes on 26 October 2026, Organization Day's among them
# ("House Session (12/04/2024)", "Senate Session (12/04/24)"), and no other
# title begins this way.
SESSION_TITLE = {"H": r"^house session\b", "S": r"^senate session\b"}

# A title's date and everything after it: "(01/07/2027)", "(1/7/27",
# "(5/27/20 - morning session)", "(01/12/2026) (Full Stream)".
_DATE_TAIL = re.compile(r"\(\s*[0-9]{1,2}/[0-9]{1,2}/[0-9]{2,4}.*$", re.S)
_WORD = re.compile(r"[a-z0-9]+")


class SourceError(ValueError):
    """A source no longer says a value where, or how, this reads it."""


def stem(title):
    """A stream title as comparable words: its date and what follows it
    dropped, lower case, "&" as "and", and any other run of characters one
    space. workers/live/youtube.js's stem() is this one, held to it on every
    committed title."""
    t = _DATE_TAIL.sub("", title or "").lower().replace("&", " and ")
    return " ".join(_WORD.findall(t))


def session_of(title):
    """'H' or 'S' when the title is that chamber's session stream, else None."""
    s = stem(title)
    for chamber, pattern in SESSION_TITLE.items():
        if re.search(pattern, s):
            return chamber
    return None


def _base(root):
    return Path(root) if root is not None else _paths.ROOT


def _literal(path, name):
    """The value of the module-level `name = <literal>` in `path`, read by
    parsing it."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as e:
        raise SourceError(f"{path.as_posix()} could not be read: {e}") from None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name
                                                for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                raise SourceError(f"{path.as_posix()} no longer assigns {name} a literal") from None
    raise SourceError(f"{path.as_posix()} no longer assigns {name}")


def channels(root=None):
    raw = _literal(_base(root) / CHANNEL_INDEX, "CHANNELS")
    out = {}
    for name, letter in CHAMBER.items():
        entry = raw.get(name) if isinstance(raw, dict) else None
        cid = entry[0] if isinstance(entry, (tuple, list)) and entry else None
        if not (isinstance(cid, str) and re.fullmatch(r"UC[0-9A-Za-z_-]{22}", cid)):
            raise SourceError(f"{CHANNEL_INDEX.as_posix()} CHANNELS[{name!r}] is not a channel id "
                              f"as YouTube writes one (UC and 22 more): {entry!r}")
        out[letter] = cid
    return out


def night_windows(root=None):
    raw = _literal(_base(root) / REFUSAL, "NIGHT_WINDOWS")
    out = []
    for w in raw:
        try:
            wd, (sh, sm), (eh, em), _what = w
        except (TypeError, ValueError):
            raise SourceError(f"{REFUSAL.as_posix()} NIGHT_WINDOWS has an entry this cannot read: "
                              f"{w!r}") from None
        if (wd is not None and wd not in range(7)) or not all(
                isinstance(x, int) for x in (sh, sm, eh, em)):
            raise SourceError(f"{REFUSAL.as_posix()} NIGHT_WINDOWS has an entry this cannot read: "
                              f"{w!r}")
        out.append([wd, [sh, sm], [eh, em]])
    if not out:
        raise SourceError(f"{REFUSAL.as_posix()} NIGHT_WINDOWS is empty")
    return out


def values(root=None):
    """{name: (where it comes from, value)}, in the order they are written."""
    return {
        "CHANNELS": (f"{CHANNEL_INDEX.as_posix()} CHANNELS, by chamber: each one's YouTube "
                     "channel; its uploads playlist is the id with UC made UU",
                     channels(root)),
        "NIGHT_WINDOWS": (f"{REFUSAL.as_posix()} NIGHT_WINDOWS, in UTC: [weekday (0 is Monday) "
                          "or null for every day, [start hour, minute], [end hour, minute]]",
                          night_windows(root)),
        "SESSION_TITLE": ("src/pages/live_gen.py SESSION_TITLE: the beginning of a session "
                          "stream's title stem, by chamber (a RegExp source)",
                          SESSION_TITLE),
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
    return False, f"{OUT.as_posix()} is not what its sources say now"


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
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.as_posix()}: {', '.join(values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
