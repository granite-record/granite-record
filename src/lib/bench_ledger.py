#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
The bench's ledger, review/checked.jsonl, read one way by every reader.

    import bench_ledger as BL
    BL.read(path)          # every line, in the file's order
    BL.judgments(lines)    # the lines a reader takes, in the file's order
    BL.judged(path)        # {(kind, key): [lines]}, the one that counts LAST
    BL.who(line)           # "hand", "link" or None

The ledger is append-only. src/checks/review.py writes the owner's judgments
from the laptop's bench, and src/checks/bench_pull.py appends what she
approved from the hosted bench. Three rules decide what a reader takes from
it, and they live here so that no reader decides them again:

WHOSE A LINE IS. "by": "hand" is the owner's: from the laptop's bench, or
from the hosted bench through her own link. "by": "link:<id>" is a
contributor's, merged by her from the hosted bench under the link's id,
never its name. A line with no "by" is the owner's (none is written that
way now; the first bench wrote "hand" from its first day). Any other value
is no one's this ledger accepts -- an assistant's judgments stay in a file
of their own (tests/related_judged_2026-10-11.json) -- and no reader takes
it.

THE OWNER'S LINE BEATS A CONTRIBUTOR'S, whatever the order. Within one pool
a later look at an item supersedes an earlier one, as it always has; but a
contributor's line, merged after hers, never replaces hers. So judged()
lists an item's lines with every contributor's before every one of hers,
each pool in the file's order, and the last line is the one that counts --
which is what every reader that takes entries[-1] already reads.

A WITHDRAWAL is one appended line, {"kind": "withdraw", "by": "hand",
"link": "<id>"}: every line of that link is read by no reader, wherever it
stands in the file. The ledger is never rewritten.

Reads one file and writes nothing.
"""

import json
import re
from pathlib import Path

LEDGER = Path("review") / "checked.jsonl"
WITHDRAW = "withdraw"
LINK_ID = re.compile(r"^[a-z0-9]{1,16}$")


def read(path=LEDGER):
    """Every line of the ledger that is a JSON object, in the file's order;
    [] where there is no file. A line that will not parse is passed over, as
    every reader always has."""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if isinstance(d, dict):
            out.append(d)
    return out


def link_of(line):
    """The link id a contributor's line names ("link:b3k9" -> "b3k9"), or ""."""
    by = line.get("by")
    if isinstance(by, str) and by.startswith("link:") and LINK_ID.match(by[5:]):
        return by[5:]
    return ""


def who(line):
    """"hand" for the owner's line, "link" for a contributor's, None for a
    line no reader takes (WHOSE A LINE IS)."""
    by = line.get("by")
    if by is None or by == "hand":
        return "hand"
    return "link" if link_of(line) else None


def withdrawn(lines):
    """The link ids the owner has withdrawn, by her own line."""
    return {str(d.get("link")) for d in lines
            if d.get("kind") == WITHDRAW and who(d) == "hand"
            and LINK_ID.match(str(d.get("link") or ""))}


def judgments(lines):
    """The judgments a reader takes, in the file's order: the owner's and the
    contributors' whose link is not withdrawn; no withdrawal line, and no line
    that is no one's."""
    gone = withdrawn(lines)
    return [d for d in lines
            if d.get("kind") != WITHDRAW and who(d) is not None
            and not (who(d) == "link" and link_of(d) in gone)]


def ranked(entries):
    """An item's lines in the order that makes the last one count: every
    contributor's line before every one of the owner's, each in the file's
    order."""
    return [e for e in entries if who(e) == "link"] + [e for e in entries if who(e) == "hand"]


def supersedes(new, old):
    """Whether `new`, met after `old` in the file, is the line that counts:
    a line of the owner's always is; a contributor's only over another
    contributor's or over nothing."""
    return old is None or who(new) == "hand" or who(old) == "link"


def by_item(lines):
    """{(kind, key): [lines]} for every item `lines` judge, each list ranked()
    so that its last line is the one that counts."""
    seen = {}
    for d in judgments(lines):
        seen.setdefault((d.get("kind"), d.get("key")), []).append(d)
    return {k: ranked(v) for k, v in seen.items()}


def judged(path=LEDGER):
    """by_item() of the ledger at `path`."""
    return by_item(read(path))
