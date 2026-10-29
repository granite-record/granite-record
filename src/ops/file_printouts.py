#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-26.1
"""
Put the person's printouts of official pages where the guides' evidence is
kept, under the names the index gives them.

    python3 src/ops/file_printouts.py ~/Downloads           # look there, copy what matches
    python3 src/ops/file_printouts.py ~/Downloads ~/Desktop --dry-run
    python3 src/ops/file_printouts.py --check               # which are filed, which missing

WHY (26 October 2026). The guides and Learn pages rest on pages the person
printed, because most nh.gov agencies refuse this project's machines. Those
printouts were read in a cloud session and lived nowhere else, and a cloud
session's disk is gone when it ends. The person chose to keep the PDFs on
their own computer and only the index in git ("Index in git, PDFs on
laptop"): records/sources/printouts/INDEX.csv names each one -- its new
name, the page's title and address, the day it was printed, the guides and
Learn pages that cite that address -- with the sha256 of the file.

A file is found by its sha256, not its name, so it does not matter what the
download was called or which folder it is in. It is copied, never moved or
deleted, and a file already filed is left alone. Nothing here reaches the
network.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import hashlib
import shutil

ROOT = _paths.ROOT
HOME = ROOT / "records" / "sources" / "printouts"
INDEX = HOME / "INDEX.csv"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def index():
    if not INDEX.is_file():
        sys.exit(f"no index at {INDEX.relative_to(ROOT)}: nothing to file against")
    with open(INDEX, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("folders", nargs="*", help="where the downloaded PDFs are")
    ap.add_argument("--dry-run", action="store_true", help="say what would be copied")
    ap.add_argument("--check", action="store_true", help="which printouts are filed")
    a = ap.parse_args()
    rows = index()
    want = {r["sha256"]: r for r in rows}
    if a.check or not a.folders:
        have = [r for r in rows if (HOME / r["new_name"]).is_file()
                and sha256(HOME / r["new_name"]) == r["sha256"]]
        print(f"{len(have)} of {len(rows)} printouts filed in {HOME.relative_to(ROOT)}")
        for r in rows:
            if r not in have:
                print(f"  missing  {r['new_name']:<52} (downloaded as {r['owner_name']})")
        return 0 if len(have) == len(rows) else 1
    HOME.mkdir(parents=True, exist_ok=True)
    found = {}
    for folder in a.folders:
        for p in Path(folder).expanduser().rglob("*.pdf"):
            try:
                h = sha256(p)
            except OSError:
                continue
            if h in want and h not in found:
                found[h] = p
    copied = 0
    for h, src in sorted(found.items(), key=lambda kv: want[kv[0]]["new_name"]):
        dest = HOME / want[h]["new_name"]
        if dest.is_file() and sha256(dest) == h:
            continue
        print(f"  {'would copy' if a.dry_run else 'copy'}  {src.name}  ->  {dest.relative_to(ROOT)}")
        if not a.dry_run:
            shutil.copy2(src, dest)
        copied += 1
    missing = [r for r in rows if r["sha256"] not in found and not (HOME / r["new_name"]).is_file()]
    print(f"{copied} {'to copy' if a.dry_run else 'copied'}; "
          f"{len(rows) - len(missing)} of {len(rows)} now accounted for")
    for r in missing:
        print(f"  not found  {r['owner_name']}  ({r['title']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
