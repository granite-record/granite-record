#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
The scripts a builder writes into its pages, each read from a file of its own.

    import inline_js as IJ
    SCRIPT = "<script>\\n" + IJ.script("build_nobill_votes") + "</script>"
    IJ.script("chrome.lang_head", OFFER=..., LANGS=..., NOTICE=...)

WHY (20 November 2026, the refactor's finding 5). A page builder's own
script -- a filter, a tab strip, the language check before the first paint
-- was a Python string in the builder, where no JavaScript tool, search for
dead code or check of a twin could see it. Each is now a .js file, and the
builder reads it here and writes it into the page as the string was: the
built page is the same to the byte.

WHERE THE FILES ARE. In a folder named inline/ beside the builder that reads
them: src/pages/inline/ for the page builders, src/checks/inline/ for the
check tools (the bench's page, drawn_pages' driver). A file is named for its
builder: <builder>.js, or <builder>.<what>.js where the builder has more
than one. That name is how this finds the folder: the builder's file,
wherever _paths finds it, and inline/ beside it. One builder reads each file,
and a builder reads its files only through script() (preflight,
_inline_scripts_read_once). The folders are not code folders (_paths.SRC_DIRS):
nothing finds a file in them by a bare name, nothing copies one into site/,
and each reaches a reader only inside the page its builder writes.

WHAT A FILE HOLDS: the script exactly as the page carries it, which is the
string's value and not the text that stood between its quotes -- an escape
such as \\n or \\\\ in a Python string is the one character it stood for here,
and a raw string's backslashes are themselves. So a file carries no comment
and no version stamp that the page does not carry: the comments the page has
always carried are the script's own, and the file's version is its
builder's. A file is read as Python reads its own source, with its line ends
as \\n whatever the checkout wrote (core.autocrlf), which is what the string
held; a script that needs a carriage return in it cannot be kept here.

A HOLE IS __NAME__: two underscores, a capital, capitals, digits and single
underscores, two underscores (__OFFER__, __DISTRICT_WORDS__), the form the
builders already filled with str.replace. A JavaScript name of that shape is
taken as a hole. script() fills every hole from its keyword arguments, in one
pass, so a value that itself holds __SOMETHING__ is written as it is; and it
refuses (ValueError) a hole left with no value, a value with no hole, and a
value that is not a string. A {} is JavaScript's and never a hole here.

Standard library and _paths only; it reads, and writes nothing.
"""

import re
from pathlib import Path

import _paths

# The folder, beside a builder, that holds its scripts.
FOLDER = "inline"

# A file's name: the builder's module name, and a word for which of its scripts.
NAME = re.compile(r"[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)?")

# A hole: __NAME__, the name with no double underscore inside it.
HOLE = re.compile(r"__([A-Z](?:[A-Z0-9]|_(?!_))*)__")


def path(name):
    """The file `name` is: inline/<name>.js beside the builder the name
    begins with. LookupError where there is no such builder."""
    if not NAME.fullmatch(name or ""):
        raise ValueError(f"inline_js: {name!r} is not <builder> or <builder>.<what>")
    builder = name.split(".", 1)[0]
    home = _paths.find(builder + ".py")
    if home is None:
        raise LookupError(f"inline_js: {name} names no builder: there is no {builder}.py "
                          "in any code folder")
    return home.parent / FOLDER / f"{name}.js"


def holes(text):
    """The holes `text` has, in the order they first appear."""
    return list(dict.fromkeys(m.group(1) for m in HOLE.finditer(text)))


def read(name):
    """The file `name` as it stands, its holes unfilled: Python's reading
    of it (universal newlines), which is what the string held."""
    with open(path(name), encoding="utf-8", newline=None) as fh:
        return fh.read()


def fill(text, values, what="the script"):
    """`text` with every hole filled from `values` ({NAME: string}), in one
    pass; ValueError for a hole no value fills, a value no hole takes, or a
    value that is not a string. `what` names the text in the refusal."""
    want = holes(text)
    unfilled = [h for h in want if h not in values]
    if unfilled:
        raise ValueError(f"inline_js: {what} has holes no value fills: "
                         + ", ".join(f"__{h}__" for h in unfilled))
    spare = [k for k in values if k not in want]
    if spare:
        raise ValueError(f"inline_js: {what} has no hole for "
                         + ", ".join(f"__{k}__" for k in spare))
    odd = [k for k, v in values.items() if not isinstance(v, str)]
    if odd:
        raise ValueError(f"inline_js: the values for {', '.join(odd)} in {what} are not strings")
    return HOLE.sub(lambda m: values[m.group(1)], text) if want else text


def script(name, **values):
    """The script `name` as its builder writes it into a page, its holes
    filled from `values`. The one way a builder has its scripts."""
    return fill(read(name), values, f"{name}.js")


def files(root=None):
    """Every inline script under `root` (this repository by default): the
    inline/ folders beside the code folders, as {name: path}."""
    out = {}
    for d in _paths.code_dirs(root):
        folder = Path(d) / FOLDER
        if folder.is_dir():
            for f in sorted(folder.glob("*.js")):
                out[f.stem] = f
    return dict(sorted(out.items()))
