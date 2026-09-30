#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.6
"""
Daily snapshot of the NH General Court bulk data files.

    python3 snapshot_gencourt.py --dir nh-archive              # archive only
    python3 snapshot_gencourt.py --dir nh-archive --into .     # archive, then install for the build
    python3 snapshot_gencourt.py --plan                        # what it would ask for; no request

Docket.txt and its siblings are LIVE views, not archives. Nothing guarantees
last session's rows will still be there next year. Run this daily and you
accumulate the history that cross-session comparison depends on -- history you
cannot reconstruct later if you skip a day.

Fourteen requests, one file each, a few seconds apart. Unchanged files are not
stored twice: the store is content-addressed.

WHAT CHANGED ON 12 SEPTEMBER, AND WHY

This is the one fetch meant to run every night with nobody watching, and until
the 12th it had none of the rules the others were given after this address
blocked the project twice:

  - it retried EVERY failure three times, a 403 included, so an address that
    had just said no was asked again, and again, fourteen files over;
  - it took no lock, so it could run beside the bill-text lane as a second
    worker at the same address -- which is how the second block was earned;
  - it asked for the next file the instant the last one finished;
  - and it saved whatever came back, so the firewall's block page, which
    arrives with HTTP 200, would have been stored as that day's Docket.txt.

Now: refusal.check() before anything; refusal.hold() for the whole run (under
the nightly, whose lock it recognises as its parent's); still() before every
request; every answer read once, by refusal.classify() -- a refusal ends the
run and is recorded, two dropped connections end it and are recorded, a page
that is not a data file is not stored; a pause between files; every write a
part file and a rename.

AND IT FEEDS THE BUILD. The build reads Docket.txt and the rest from the
repository root, and nothing refreshed those: on the 12th they were the copies
downloaded by hand on 2 September, older than this archive's own copy of the
6th. --into DIR installs tonight's files there -- all of them or none, because
a build from some of today's files and some of last week's is a record of no
day at all -- and refuses a file that has shrunk sharply against the copy it
would replace, because a truncated Docket.txt parses cleanly into a smaller
site. Exit 0 installed or archived, 1 a failure, 2 refused.
"""

import argparse
import gzip
import hashlib
import html
import json
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import refusal

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
                    "contact@graniterecord.org)"}

# A file tonight this much smaller than the copy it would replace is not
# installed. Bills are added through a session and the docket only grows; the
# one real fall, a new term starting, is a person's decision (--allow-shrink).
SHRINK = 0.30
MIN_BYTES = 40          # smaller than this is not a data file
# What may precede a data file's first character: a byte-order mark, which
# the General Court's files carry, and whitespace.
LEADING = "".join(map(chr, (0xFEFF, 32, 13, 10, 9)))


def targets():
    return [(BASE + f, f) for f in FILES] + EXTRA


# THE PAGE FIRST (30 September 2026). The General Court's downloads page links
# these files as "Current Data Tables - data refreshes on file access", and the
# page that lists them is what rebuilds them from the database when it is
# opened. On 28 September it said "Error Generating Members File : Execution
# Timeout Expired. ..." while every file it linked was 3 bytes long. This
# script used to ask for the files alone, and so took whatever the last
# visitor's rebuild had left. It opens the page first now, as a person would,
# keeps what the page said in snapshots/<day>/page.json for the nightly's
# verdict, and goes on to the files whatever it said: the files themselves show
# whether they arrived whole, and an error they do not show is no reason to go
# without them. The "Members File" of that message is legislators.txt, one of
# these: opened on 30 September the page listed it first, answered in nine
# seconds and rewrote Docket.txt in the second it was asked; on the 28th it
# did not list it at all.
PAGE = BASE
PAGE_TIMEOUT = 300      # seconds: the page rebuilds every table before it answers
PAGE_ERROR = re.compile(r"Error Generating\b.{0,400}", re.I)


def page_said(body):
    """What the Dynamic Data Files page says went wrong rebuilding the files,
    as plain text, or "" when it reports nothing."""
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else (body or "")
    text = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)))
    m = PAGE_ERROR.search(text)
    if not m:
        return ""
    said = m.group(0)
    cut = said.find(" LSR Table")          # the page's own list of files follows it
    return (said[:cut] if cut > 0 else said).strip()


def open_page():
    """{"status", "said"}: the page asked for once. status is "ok", "error" (the
    page answered and reported a failed rebuild), or refusal.classify's word for
    a request that did not come back as a page."""
    try:
        data = get(PAGE, timeout=PAGE_TIMEOUT)
    except Exception as e:                                  # noqa: BLE001
        kind = refusal.classify(e) or "failed"
        # Slow, not refusing: the page rebuilds every table before it answers,
        # so a timeout here is not counted with the dropped connections that
        # end a run. A reset or an unanswered close still is.
        inner = getattr(e, "reason", e)
        if kind == "dropped" and (isinstance(inner, TimeoutError) or "timed out" in str(inner).lower()):
            kind = "slow"
        return {"status": kind, "said": f"{type(e).__name__}: {e}"[:200]}
    if refusal.classify(body=data[:4000].decode("utf-8", "replace")) == "refused":
        return {"status": "refused", "said": "the firewall's block page, served as 200"}
    said = page_said(data)
    return {"status": "error" if said else "ok", "said": said}


def write_atomically(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def get(url, timeout=120):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def read_one(url):
    """(data, None) or (None, (kind, why)). One request; no retry of its own."""
    try:
        data = get(url)
    except Exception as e:                                  # noqa: BLE001
        return None, (refusal.classify(e) or "failed", f"{type(e).__name__}: {e}")
    head = data[:4000].decode("utf-8", "replace")
    if refusal.classify(body=head) == "refused":
        return None, ("refused", "the firewall's block page, served as 200")
    stripped = head.lstrip(LEADING).lower()
    if len(data) < MIN_BYTES or stripped.startswith(("<!doctype", "<html", "<?xml")):
        return None, ("failed", f"not a data file ({len(data):,} bytes)")
    return data, None


def install(fetched, into, allow_shrink=False):
    """Copy tonight's files where the build reads them: all, or none. (ok, lines)"""
    into = Path(into)
    lines, refused = [], []
    for name, data in fetched.items():
        old = into / name
        if old.exists() and not allow_shrink:
            before = old.stat().st_size
            if before and len(data) < before * (1 - SHRINK):
                refused.append(f"{name} is {len(data):,} bytes against {before:,} "
                               f"installed ({(len(data) - before) / before:+.0%})")
    if refused:
        return False, ["NOT INSTALLED, any of it: " + "; ".join(refused),
                       "A fall that size is a truncated file far more often than a "
                       "record getting shorter. --allow-shrink if it is real."]
    for name, data in fetched.items():
        write_atomically(into / name, data)
        lines.append(f"  installed {name} -> {into / name}")
    return True, lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="nh-archive", help="archive directory")
    ap.add_argument("--into", help="after a complete fetch, install the files here "
                                   "for the build")
    ap.add_argument("--allow-shrink", action="store_true")
    ap.add_argument("--delay", type=float, default=4.0,
                    help="seconds between files (default 4), jittered")
    ap.add_argument("--plan", action="store_true", help="list the requests; make none")
    a = ap.parse_args()

    if a.plan:
        for url, name in targets():
            print(f"  {name:24} {url}")
        print(f"\n{len(targets())} requests, about {a.delay:g}s apart. Nothing asked.")
        return 0

    # Once GitHub's nightly takes the day's files, this machine does not: two
    # machines asking for the same fourteen files, and two writers of the
    # copies the build reads. The lane's daily line meets this every night
    # until it is taken out of watchers/gc_lane.queue.
    refusal.stand_down("The daily snapshot", "GitHub's nightly takes the day's "
                       "files now, and they reach this machine from R2.")
    refusal.check("The daily snapshot")
    with refusal.hold("the daily snapshot") as held:
        return run(a, held)


def run(a, held):
    root = Path(a.dir).expanduser()
    today = date.today().isoformat()
    snap = root / "snapshots" / today
    store = root / "store"
    snap.mkdir(parents=True, exist_ok=True)
    store.mkdir(parents=True, exist_ok=True)

    index_path = root / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}

    manifest, fetched = {}, {}
    new = same = failed = dropped = 0
    stopped = ""
    work = targets()
    i = 0
    retried = set()

    # The page first: opening it is what rebuilds the files.
    if refusal.MARK.exists():
        stopped = "refused"
        print("  archive/refused.json is on file. Stopping.")
    elif not held.still():
        stopped = "lock"
        print("  the run holding archive/.lock is gone. Stopping.")
    else:
        page = open_page()
        page["asked"] = date.today().isoformat()
        write_atomically(snap / "page.json", json.dumps(page, indent=2).encode("utf-8"))
        print(f"  page  {PAGE}: " + {"ok": "answered, and reported no error",
                                      "error": f"answered, and reported: {page['said'][:200]}"}.get(
            page["status"], f"{page['status']}: {page['said'][:100]}"), flush=True)
        if page["status"] == "refused":
            refusal.note("snapshot_gencourt", page["said"])
            stopped = "refused"
        elif page["status"] == "dropped":
            dropped += 1

    while not stopped and i < len(work):
        url, name = work[i]
        time.sleep(a.delay * random.uniform(0.75, 1.25))
        # Immediately before the request: a refusal another fetch met while
        # this one waited, or a nightly killed while it waited, stops it here.
        if refusal.MARK.exists():
            stopped = "refused"
            print("  archive/refused.json is on file. Stopping.")
            break
        if not held.still():
            stopped = "lock"
            print("  the run holding archive/.lock is gone. Stopping.")
            break
        data, err = read_one(url)
        if err:
            kind, why = err
            print(f"  FAIL  {name}: {kind}: {why[:100]}", flush=True)
            if kind == "refused":
                refusal.note("snapshot_gencourt", why)
                stopped = "refused"
                break
            if kind == "dropped":
                dropped += 1
                if dropped >= 2:
                    refusal.note("snapshot_gencourt", why)
                    stopped = "refused"
                    break
                # Once, after a pause: a lost day cannot be fetched later, and
                # one dropped connection is bad luck. The second is a refusal.
                if name not in retried:
                    retried.add(name)
                    print("        once more in a minute", flush=True)
                    time.sleep(60)
                    continue
            failed += 1
            manifest[name] = {"error": f"{kind}: {why}"[:200]}
            i += 1
            continue

        digest = hashlib.sha256(data).hexdigest()
        blob = store / f"{digest}.gz"
        if not blob.exists():
            tmp = blob.with_name(blob.name + ".part")
            with gzip.open(tmp, "wb") as fh:
                fh.write(data)
            os.replace(tmp, blob)
            new += 1
            tag = "NEW "
        else:
            same += 1
            tag = "same"
        write_atomically(snap / (name + ".sha256"), digest.encode("utf-8"))
        manifest[name] = {"sha256": digest, "bytes": len(data)}
        prev = index.get(name, {}).get("last_sha256")
        changed = " (changed)" if prev and prev != digest else ""
        print(f"  {tag}  {name:24} {len(data):>10,} bytes{changed}", flush=True)
        index.setdefault(name, {})["last_sha256"] = digest
        index[name].setdefault("history", [])
        if not index[name]["history"] or index[name]["history"][-1][1] != digest:
            index[name]["history"].append([today, digest])
        fetched[name] = data
        i += 1

    write_atomically(snap / "manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))
    write_atomically(index_path, json.dumps(index, indent=2).encode("utf-8"))
    total = sum(p.stat().st_size for p in store.glob("*.gz"))
    print(f"\n{today}: {new} new, {same} unchanged, {failed} failed"
          + (f", stopped ({stopped})" if stopped else ""))
    print(f"Archive now {total / 1e6:.1f} MB across {len(list(store.glob('*.gz')))} blobs")

    complete = not stopped and not failed and len(fetched) == len(work)
    if a.into:
        if complete:
            ok, lines = install(fetched, a.into, a.allow_shrink)
            print("\n".join(lines))
            if not ok:
                return 1
        else:
            print(f"\nNothing installed into {a.into}: {len(fetched)} of {len(work)} "
                  "files arrived, and a build from some of tonight's files and some "
                  "of an earlier day's is a record of no day.")
    if stopped == "refused":
        print("\nRefused. refusal.py holds every fetch for a day; netcheck.py says "
              "what kind it was.")
        return 2
    if stopped or failed:
        print("\nA failure means that file was unreachable tonight, not that it is "
              "gone.\nIf the same file fails several nights running, check the "
              "downloads page.")
        return 1
    return 0


def restore(archive_dir, snapshot_date, name, out):
    """Pull one file back out of the archive."""
    root = Path(archive_dir).expanduser()
    digest = (root / "snapshots" / snapshot_date / f"{name}.sha256").read_text(encoding="utf-8").strip()
    with gzip.open(root / "store" / f"{digest}.gz", "rb") as fh, open(out, "wb") as o:
        shutil.copyfileobj(fh, o)


if __name__ == "__main__":
    sys.exit(main())
