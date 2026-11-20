#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
app.js, made of its parts in src/pages/app/.

    python3 src/pages/app_parts.py            # write app.js from its parts
    python3 src/pages/app_parts.py --check    # say whether app.js is its parts (exit 1 if not)
    python3 src/pages/app_parts.py --split    # carry an edit made in app.js back into its parts

WHY (20 November 2026, the refactor's finding 6). app.js is the bill search
and every record page's script, past fourteen thousand lines in one file.
Its own headers already divided it -- the bill's facts, versions, report a
problem, member and committee, the videos, boot, the votes page -- and
the BILLMATCH regions that site/billmatch.js is cut from were four stretches
somewhere in the middle. Each of those is now a file of its own in
src/pages/app/, and app.js is the parts joined in the order of their names.
Nothing was reordered, so app.js is the file it was, to the byte.

EDIT THE PART, THEN WRITE app.js. app.js stays in the repository, written
from the parts: everything that reads it -- the build, which publishes it as
site/app.js and cuts site/billmatch.js from it, the fast path, the quick
preview, the search index, and every check that reads its text or runs it in
node -- reads the joined file as before and never a part. preflight's
_app_js_is_its_parts fails while app.js is not its parts. A change merged
into app.js from a branch older than the parts goes back into them with
--split, which cuts app.js where each part begins (its first line, which is
found once in app.js) and refuses where it cannot tell.

THE STAMP IS app.js's, ON ITS FIRST LINE. The parts carry none, as a
builder's inline/ scripts carry none: a part's version is app.js's. Writing
keeps app.js's first line, the stamp, and puts the parts after it, so
inventory.py and preflight's _stamps read app.js as before and data.html
counts the same stamped files: a part changed is app.js changed, and
`inventory.py --bump-changed` raises app.js's stamp.

A PART IS NAMED NNN-what.js: three digits that put it in its place, a word
or two for what it holds. Each ends with a line end, so a part's last line is
never joined to the next part's first. A part named *-billmatch-*.js is one
BILLMATCH region whole, from its BILLMATCH:BEGIN line to its BILLMATCH:END
line, and no other part holds a BILLMATCH marker: what billmatch.js carries
is those parts.

Standard library and _paths only. It writes app.js, and the parts only with
--split.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import re

APP = "src/pages/app.js"
FOLDER = "src/pages/app"
NAME = re.compile(r"\d{3}-[a-z][a-z0-9]*(?:-[a-z0-9]+)*\.js")
BILLMATCH = "-billmatch-"
BEGIN, END = b"// BILLMATCH:BEGIN", b"// BILLMATCH:END"
STAMP = re.compile(rb"//[ \t]*GRANITE_VERSION:[ \t]*\d{4}-\d{2}-\d{2}\.\d+[ \t]*\r?\n")


def _base(root):
    return Path(root).resolve() if root is not None else _paths.ROOT


def parts(root=None):
    """The parts, in the order app.js is joined from them: every file in
    src/pages/app/, by name."""
    d = _base(root) / FOLDER
    return sorted((p for p in d.iterdir() if p.is_file()), key=lambda p: p.name) if d.is_dir() else []


def _lines(raw):
    """`raw` (bytes) as its lines, each with its line end."""
    return raw.splitlines(keepends=True)


def _stamp_line(root):
    """app.js's first line, its stamp, as bytes. ValueError where app.js is
    not here or does not begin with one."""
    p = _base(root) / APP
    if not p.is_file():
        raise ValueError(f"{APP} is not here: it holds the stamp the parts are written under; "
                         "restore it from git (git checkout -- src/pages/app.js)")
    first = (_lines(p.read_bytes()) or [b""])[0]
    if not STAMP.fullmatch(first):
        raise ValueError(f"{APP} does not begin with its stamp line (// GRANITE_VERSION: ...)")
    return first


def joined(root=None):
    """The parts joined, as bytes: app.js but its first line."""
    return b"".join(p.read_bytes() for p in parts(root))


def whole(root=None):
    """What app.js is: its stamp line, then the parts. Bytes."""
    return _stamp_line(root) + joined(root)


def _same(a, b):
    return a.replace(b"\r\n", b"\n") == b.replace(b"\r\n", b"\n")


def stale(root=None):
    """None where app.js is its parts (line ends aside, which git's checkout
    decides), else a sentence that says what to run."""
    try:
        want = whole(root)
    except ValueError as e:
        return str(e)
    have = (_base(root) / APP).read_bytes()
    if _same(want, have):
        return None
    a, b = _lines(have.replace(b"\r\n", b"\n")), _lines(want.replace(b"\r\n", b"\n"))
    n = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    return (f"{APP} is not its parts in {FOLDER}/ (from line {n + 1}): edit the part and run "
            "python3 src/pages/app_parts.py, or, for an edit made in app.js, "
            "python3 src/pages/app_parts.py --split")


def faults(root=None):
    """What is wrong with the parts, as sentences: a name not NNN-what.js; a
    part empty or not ending with a line end; a part whose first line is not
    found exactly once at the head of a line in the join (so --split could
    not find where it begins); a billmatch part that is not one BILLMATCH
    region whole, and a marker in any other part."""
    out = []
    ps = parts(root)
    if not ps:
        return [f"{FOLDER}/ holds no parts"]
    texts = {p.name: p.read_bytes().replace(b"\r\n", b"\n") for p in ps}
    every = [ln for t in texts.values() for ln in _lines(t)]
    for name, t in texts.items():
        if not NAME.fullmatch(name):
            out.append(f"{name}: a part is named NNN-what.js")
        if not t or not t.endswith(b"\n"):
            out.append(f"{name}: a part is not empty and ends with a line end")
            continue
        lines = _lines(t)
        if every.count(lines[0]) != 1:
            out.append(f"{name}: its first line is found {every.count(lines[0])} times in app.js, "
                       "so --split cannot tell where it begins")
        marks = [i for i, ln in enumerate(lines) if ln.strip().startswith((BEGIN, END))]
        if BILLMATCH in name:
            if not (lines[0].strip().startswith(BEGIN) and lines[-1].strip().startswith(END)
                    and marks == [0, len(lines) - 1]):
                out.append(f"{name}: a billmatch part is one BILLMATCH region whole, from its "
                           "BEGIN line to its END line and no other marker")
        elif marks:
            out.append(f"{name}:{marks[0] + 1}: a BILLMATCH marker outside a billmatch part")
    return out


def write(root=None):
    """Write app.js from its parts, keeping its stamp line. True where it changed."""
    p = _base(root) / APP
    want = whole(root)
    if p.read_bytes() == want:
        return False
    p.write_bytes(want)
    return True


def split(root=None):
    """Cut app.js, after its stamp line, into the parts there are, each
    beginning at its first line as it stands, and write each part that
    changed. Returns the names written. ValueError, and nothing written,
    where a part's first line is not in app.js exactly once, in order."""
    base = _base(root)
    ps = parts(root)
    if not ps:
        raise ValueError(f"{FOLDER}/ holds no parts to cut app.js into")
    lines = _lines((base / APP).read_bytes())
    _stamp_line(root)
    body = lines[1:]
    plain = [ln.rstrip(b"\r\n") for ln in body]
    at = []
    for p in ps:
        head = (_lines(p.read_bytes()) or [b""])[0].rstrip(b"\r\n")
        hits = [i for i, ln in enumerate(plain) if ln == head]
        if len(hits) != 1:
            raise ValueError(f"{p.name}: its first line is found {len(hits)} times in app.js; "
                             "cut that part by hand")
        at.append(hits[0])
    if at[0] != 0 or at != sorted(at) or len(set(at)) != len(at):
        raise ValueError("the parts' first lines are not in app.js in the parts' order, "
                         "the first at its second line; cut them by hand")
    wrote = []
    for p, a, b in zip(ps, at, at[1:] + [len(body)]):
        text = b"".join(body[a:b])
        if p.read_bytes() != text:
            p.write_bytes(text)
            wrote.append(p.name)
    return wrote


def main():
    ap = argparse.ArgumentParser(description="app.js, made of its parts in src/pages/app/.")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="say whether app.js is its parts")
    g.add_argument("--split", action="store_true",
                   help="carry an edit made in app.js back into its parts")
    a = ap.parse_args()
    try:
        bad = faults()
        if bad:
            print("the parts are not right:\n  " + "\n  ".join(bad))
            return 1
        n = len(parts())
        if a.check:
            why = stale()
            print(why or f"{APP} is its {n} parts.")
            return 1 if why else 0
        if a.split:
            wrote = split()
            print(f"wrote {len(wrote)} of {n} parts from {APP}: " + ", ".join(wrote) if wrote
                  else f"every part is what {APP} holds already.")
            why = stale()
            if why:
                print(why)
                return 1
            return 0
        changed = write()
        print(f"{APP}: written from its {n} parts." if changed
              else f"{APP} is its {n} parts already.")
        return 0
    except ValueError as e:
        print(f"REFUSED: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
