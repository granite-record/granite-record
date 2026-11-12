#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-09.2
"""
What a bill's Bill Text tab needs beside the texts build_bill_versions.py
wrote: each amendment's number, and where each statute the texts cite links.

    python3 src/parse/build_version_links.py --site site
    python3 src/parse/build_version_links.py --check       # counts, writes nothing

Asks nobody: it reads the index and the texts already under site/versions/
and writes the two fields into each index.

    "amendments": [{..., "num": "2025-0695h"}]     the number the amendment's
                                                   own text prints first
    "rsa": {"RSA 91-A:2": "/laws/91-a#s2", ...}    every citation in any of
                                                   the bill's versions or
                                                   amendments, as written

A SEPARATE STEP, NOT build_bill_versions.py, because that script keeps what
it compared under a hash of its own code and of every module it imports
(build_cache.signature), and a line added there would have made the next
night compare every pair again to learn nothing new.

A MERGE: an index is read, the two fields are set, and it is written back
only if it changed, so a second run writes nothing and a run over part of
the tree touches only that part. Citations only, no definition's pop-up: that
needs each chapter's definitions and the chapter a passage is read under,
which the text states only in the "Amend RSA ..." clause above it.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re

import rsa_links

# An amendment's number is the first thing in its text with that shape:
# "March 3, 2025 2025-0695h 11/08 Amendment to HB 10-FN"; a committee of
# conference's "2026-2109-CofC" is its own. app.js's amendmentOwn reads the
# same, from the same first thousand characters.
AMENDMENT_NO = re.compile(r"\b(\d{4}-\d{4})(-?[A-Za-z]*)")


def amendment_number(text):
    """'2025-0695h' (as printed: 2026-2109-CofC) for an amendment's text, or '' where it prints none."""
    m = AMENDMENT_NO.search((text or "")[:1000])
    return (m.group(1) + m.group(2)) if m else ""


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def linked(index, folder, bill):
    """The index with `num` on each amendment its text numbers and `rsa`
    where any text cites a statute the site can link; the index as it was
    otherwise."""
    out = dict(index)
    amds = []
    texts = [read(folder / f"{bill}.{i}.txt") for i in range(len(index.get("versions") or []))]
    for j, a in enumerate(index.get("amendments") or []):
        t = read(folder / f"{bill}.a{j}.txt")
        texts.append(t)
        a = {k: v for k, v in a.items() if k != "num"}
        num = amendment_number(t)
        if num:
            a["num"] = num
        amds.append(a)
    if "amendments" in index:
        out["amendments"] = amds
    cites = dict(sorted(rsa_links.rsa_links(*texts).items()))
    out.pop("rsa", None)
    if cites:
        out["rsa"] = cites
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    root = Path(a.site) / "versions"
    seen = wrote = numbered = cited = 0
    for folder in sorted(p for p in root.glob("*") if p.is_dir()):
        for f in sorted(folder.glob("*.json")):
            # An index has one dot: HB10.json. A comparison is HB10.0-1.json
            # and a version's blocks HB10.0.blocks.json.
            if f.name.count(".") != 1:
                continue
            bill = f.stem
            try:
                old = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(old, dict) or "versions" not in old:
                continue
            seen += 1
            new = linked(old, folder, bill)
            numbered += sum(1 for x in new.get("amendments") or [] if x.get("num"))
            cited += bool(new.get("rsa"))
            if new != old:
                wrote += 1
                if not a.check:
                    f.write_text(json.dumps(new, separators=(",", ":")),
                                 encoding="utf-8")
    print(f"  {seen:,} version indexes read; {numbered:,} amendments numbered; "
          f"{cited:,} bills cite a statute the site links; "
          f"{wrote:,} {'would change' if a.check else 'written'}")
    # Silence is not success: a tree with no index in it is a step that ran
    # on the wrong folder, and exiting zero would say it had worked.
    if not seen:
        raise SystemExit(f"STOP: no version index under {root}")


if __name__ == "__main__":
    main()
