#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Daily snapshot of the NH General Court bulk data files.

Docket.txt and its siblings are LIVE views, not archives. Nothing guarantees
last session's rows will still be there next year. Run this daily from today
and you accumulate the history that cross-session comparison depends on --
history you cannot reconstruct later if you skip it.

Cheap: the whole set is a few MB, and unchanged files are not re-stored.

    python3 snapshot_gencourt.py --dir ~/nh-archive

Run it daily. On Mac/Linux, `crontab -e` then:
    15 3 * * *  /usr/bin/python3 /path/to/snapshot_gencourt.py --dir /path/to/nh-archive
On Windows, use Task Scheduler.

Standard library only. Nothing to install.
"""

import argparse
import gzip
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://gc.nh.gov/dynamicdatadump/"

FILES = [
    "Docket.txt",          # every scheduling + status action. The important one.
    "LSRs.txt",            # bill records
    "LsrsOnly.txt",
    "LsrSponsors.txt",     # powers the sponsored/co-sponsored view
    "legislators.txt",     # powers the by-legislator view
    "RollCallSummary.txt", # powers roll calls by bill
    "RollCallHistory.txt", # powers roll calls by legislator
    "Committees.txt",
    "SubjectCodes.txt",    # NH's own topic taxonomy
    "GeneralCodes.txt",
    "BodyStatusCodes.txt", # powers the status diagram
    "HouseDistricts.txt",  # powers town -> legislator lookup
    "Counties.txt",
]

EXTRA = [("https://gc.nh.gov/downloads/Members.txt", "Members.txt")]


UA = {"User-Agent": "granite-record/1.0 (civic transparency archive; "
                    "corrections@graniterecord.org)"}


def fetch(url, tries=3):
    """Retry, because this is the one job whose failures cannot be undone.

    Every other script can be re-run tomorrow against the same data. This one
    captures files that are overwritten as the session advances, so a day lost
    to a transient network error is a day gone for good. A single timeout used
    to be enough to lose it.
    """
    last = None
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:
            last = e
            if n < tries - 1:
                time.sleep(5 * (n + 1))
    raise last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, help="archive directory")
    a = ap.parse_args()

    root = Path(a.dir).expanduser()
    today = date.today().isoformat()
    snap = root / "snapshots" / today
    store = root / "store"
    snap.mkdir(parents=True, exist_ok=True)
    store.mkdir(parents=True, exist_ok=True)

    index_path = root / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    targets = [(BASE + f, f) for f in FILES] + EXTRA
    manifest, new, same, failed = {}, 0, 0, 0

    for url, name in targets:
        try:
            data = fetch(url)
        except (urllib.error.URLError, urllib.error.HTTPError) as e:
            print(f"  FAIL  {name}: {e}")
            failed += 1
            manifest[name] = {"error": str(e)}
            continue

        digest = hashlib.sha256(data).hexdigest()
        blob = store / f"{digest}.gz"

        if not blob.exists():
            with gzip.open(blob, "wb") as fh:
                fh.write(data)
            new += 1
            tag = "NEW "
        else:
            same += 1
            tag = "same"

        # A readable pointer for today, so you can browse snapshots by date.
        (snap / (name + ".sha256")).write_text(digest, encoding="utf-8")

        manifest[name] = {"sha256": digest, "bytes": len(data)}
        prev = index.get(name, {}).get("last_sha256")
        changed = " (changed)" if prev and prev != digest else ""
        print(f"  {tag}  {name:24} {len(data):>10,} bytes{changed}")

        index.setdefault(name, {})["last_sha256"] = digest
        index[name].setdefault("history", [])
        if not index[name]["history"] or index[name]["history"][-1][1] != digest:
            index[name]["history"].append([today, digest])

    (snap / "manifest.json").write_text(json.dumps(manifest, indent=2),
                                    encoding="utf-8")
    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

    total = sum(p.stat().st_size for p in store.glob("*.gz"))
    print(f"\n{today}: {new} new, {same} unchanged, {failed} failed")
    print(f"Archive now {total / 1e6:.1f} MB across {len(list(store.glob('*.gz')))} blobs")
    if failed:
        print("\nA failure means that file was unreachable today, not that it is gone.")
        print("If the same file fails several days running, check the downloads page.")
        sys.exit(1)


def restore(archive_dir, snapshot_date, name, out):
    """Pull one file back out of the archive."""
    root = Path(archive_dir).expanduser()
    digest = (root / "snapshots" / snapshot_date / f"{name}.sha256").read_text(encoding="utf-8").strip()
    with gzip.open(root / "store" / f"{digest}.gz", "rb") as fh, open(out, "wb") as o:
        shutil.copyfileobj(fh, o)


if __name__ == "__main__":
    main()
