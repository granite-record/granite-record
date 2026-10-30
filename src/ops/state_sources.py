#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.1
"""
The state documents the guides and Learn pages rest on: from the laptop, where
a real browser can read them, to the sessions, which cannot.

    python3 src/ops/state_sources.py check                 the registry reads, and every
                                                            file in sources/ is one it names
    python3 src/ops/state_sources.py up [--dry-run]        the laptop sends what it read
    python3 src/ops/state_sources.py down [--into FOLDER]  a session takes them
    python3 src/ops/state_sources.py report [--since DAY]  what changed, from the bucket's record
    python3 src/ops/state_sources.py due                   registered documents never read,
                                                            or not read in their interval

    --local-bucket FOLDER   a folder stands in for the bucket, for testing
    --root FOLDER           the working folder (default: the current one)

WHY (30 October 2026). The state's web host answers a script with 403, from a
data centre and from the laptop's home connection alike, and the project will
not pretend to be a browser. So the documents are read in a real browser on
the laptop -- by the owner, or by a session there that uses the owner's own
Chrome -- and this carries what was read to the bucket, and from it to any
session. docs/design/state-sources/DESIGN.md compares the ways of reading
them; this file is the hand-over, which is the same whichever way is chosen.

THE REGISTRY. records/sources/REGISTRY.csv lists every state page and document
the site depends on: its id, its address, the page it is found on, how often
it is guessed to change, and who uses it. A file is filed under its id, so a
document the registry does not name is refused rather than carried unnamed.
Rows whose read_by is owner-only are the General Court's (the Legislative
Budget Assistant's pages): no automated reader opens them, ever; the owner
saves them by hand, and this carries the copy like any other.

THE FOLDER. sources/<id>/<YYYY-MM-DD>.<ext>, one file per reading, named by
the day it was read (a second reading the same day is <YYYY-MM-DD>-2.<ext>).
git ignores sources/. On the laptop it is where readings are put; in a
session it is where `down` puts them.

THE BUCKET. sources/<id>/<file> as in the folder, and sources/manifest.json:
for each id, every distinct version (file, sha256, size, the day read) and
the last day it was read at all. Nothing under sources/ is ever overwritten
or removed: a reading whose bytes match the id's latest version is recorded
as a check and not sent again, and a different one is a new version beside
the old. The manifest is the one object replaced, and its previous copy goes
to replaced/<day>/ as cloud.py does for every object it replaces. Each `up`
also leaves its change report at sources/reports/<stamp>.json.

The nightly never reads sources/: its kit is cloud_kit.json's list, kit-down
takes kit/ alone, and preflight fails if anything in the kit could match
sources/. These are evidence for the people and sessions who write the guides,
not inputs to the build.

WHAT IT ASKS. The bucket, and nothing else. No state site, and never the
General Court. boto3 only for the real bucket.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import hashlib
import json
import os
import re
from datetime import date, datetime
from urllib.parse import urlsplit

REGISTRY = "records/sources/REGISTRY.csv"
FOLDER = "sources"
PREFIX = "sources/"
MANIFEST_KEY = PREFIX + "manifest.json"
REPORTS = PREFIX + "reports/"
DOWN_RECORD = "archive/cloud/sources-down.json"

FIELDS = ["id", "url", "kind", "title", "publisher", "owner_page", "changes",
          "read_by", "used_by", "listed_in", "note"]
KINDS = {"page", "pdf", "app", "data", "wanted"}
READ_BY = {"browser", "owner-only", "find"}
# How often each is read again, in days: a guess per kind of change, to be
# replaced by what the change reports measure (DESIGN.md, "How often").
CHANGES = {"live": 7, "election": 7, "budget": 14, "yearly": 30, "unknown": 30, "rarely": 90}
EXTS = {"pdf", "html", "txt", "md", "csv", "xls", "xlsx", "json", "png", "mhtml"}
NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-([2-9]|[1-9]\d))?\.([a-z0-9]+)$")
ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
# The General Court's hosts. Written without a scheme on purpose: this file
# names them to keep every automated reader away, and asks nothing of them.
GC_HOSTS = ("gc.nh.gov", "gencourt.state.nh.us")


class Failed(Exception):
    pass


def say(msg=""):
    print(msg, flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def is_gc(url):
    host = urlsplit(url).netloc.lower()
    return any(host == h or host.endswith("." + h) for h in GC_HOSTS)


# ---------------------------------------------------------------- registry --

def load_registry(root):
    """{id: row}, or Failed with every problem named."""
    p = Path(root) / REGISTRY
    if not p.is_file():
        raise Failed(f"no {REGISTRY}: nothing to file readings against")
    with open(p, encoding="utf-8", newline="") as f:
        rd = csv.DictReader(f)
        if rd.fieldnames != FIELDS:
            raise Failed(f"{REGISTRY}'s columns are {rd.fieldnames}, not {FIELDS}")
        rows = list(rd)
    bad, out, urls = [], {}, {}
    for n, r in enumerate(rows, start=2):
        i = r["id"]
        where = f"{REGISTRY} line {n} ({i or 'no id'})"
        if not ID.match(i or ""):
            bad.append(f"{where}: the id is not lower-case letters, digits and hyphens")
        if i in out:
            bad.append(f"{where}: the id is used twice")
        if r["kind"] not in KINDS:
            bad.append(f"{where}: kind {r['kind']!r} is not one of {sorted(KINDS)}")
        if r["read_by"] not in READ_BY:
            bad.append(f"{where}: read_by {r['read_by']!r} is not one of {sorted(READ_BY)}")
        if r["changes"] not in CHANGES:
            bad.append(f"{where}: changes {r['changes']!r} is not one of {sorted(CHANGES)}")
        if not r["used_by"].strip():
            bad.append(f"{where}: used_by is empty; a document nothing uses is not registered")
        if r["kind"] == "wanted":
            if r["url"]:
                bad.append(f"{where}: a wanted row has an address; give it its kind")
            if not r["title"]:
                bad.append(f"{where}: a wanted row needs a title saying what is wanted")
        else:
            if not r["url"].startswith("https://"):
                bad.append(f"{where}: the address is not https")
            elif r["url"] in urls:
                bad.append(f"{where}: the address is registered twice, as {urls[r['url']]} too")
            urls[r["url"]] = i
        if r["url"] and is_gc(r["url"]) and r["read_by"] != "owner-only":
            bad.append(f"{where}: a General Court address must say read_by owner-only: "
                       "no automated reader opens it")
        out[i] = r
    if bad:
        raise Failed("the registry does not read:\n  " + "\n  ".join(bad))
    return out


# ------------------------------------------------------------------ folder --

def folder_files(root, reg, folder=FOLDER):
    """([(rel, id, day)], [problems]) for every file under the folder, where
    rel is <id>/<name> as the bucket keys it (without the prefix)."""
    base = Path(root) / folder
    files, bad = [], []
    if not base.is_dir():
        return files, bad
    for dirpath, dirs, names in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(base).as_posix()
        for n in sorted(names):
            if n.startswith("."):
                continue
            rel = n if rel_dir == "." else f"{rel_dir}/{n}"
            parts = rel.split("/")
            if len(parts) != 2:
                bad.append(f"{folder}/{rel}: not <id>/<YYYY-MM-DD>.<ext>")
                continue
            i, name = parts
            m = NAME.match(name)
            if i not in reg:
                bad.append(f"{folder}/{rel}: {i!r} is not an id in {REGISTRY}")
            elif reg[i]["kind"] == "wanted":
                bad.append(f"{folder}/{rel}: {i!r} is a wanted row; give it its address "
                           "and kind in the registry first")
            elif not m:
                bad.append(f"{folder}/{rel}: the name is not <YYYY-MM-DD>.<ext>")
            elif m.group(3) not in EXTS:
                bad.append(f"{folder}/{rel}: .{m.group(3)} is not one of {sorted(EXTS)}")
            else:
                try:
                    day = date.fromisoformat(m.group(1))
                except ValueError:
                    bad.append(f"{folder}/{rel}: {m.group(1)} is not a day")
                    continue
                if day > date.today():
                    bad.append(f"{folder}/{rel}: read on {day}, which has not come yet")
                    continue
                files.append((rel, i, m.group(1)))
    return sorted(files), bad


# ------------------------------------------------------------------ bucket --

def open_bucket(a):
    import cloud
    try:
        return cloud.make_bucket(a.local_bucket, cloud.WORKERS)
    except (cloud.Failed, SystemExit) as e:
        raise Failed(str(e))


def read_manifest(bucket):
    raw = bucket.get_bytes(MANIFEST_KEY)
    if raw is None:
        return {"ids": {}}, None
    try:
        doc = json.loads(raw.decode("utf-8"))
    except ValueError as e:
        raise Failed(f"{MANIFEST_KEY} in the bucket will not read ({e}); nothing is sent "
                     "over it")
    if not isinstance(doc.get("ids"), dict):
        raise Failed(f"{MANIFEST_KEY} in the bucket has no ids")
    return doc, raw


def latest(entry):
    v = entry.get("versions") or []
    return v[-1] if v else None


# ---------------------------------------------------------------------- up --

def plan_up(root, reg, man, files):
    """What `up` would do with each local file, oldest reading first:
    [(kind, rel, id, day, sha, size, previous)] where kind is new, changed,
    unchanged or known (a file already sent, or a check already recorded)."""
    ids = json.loads(json.dumps(man["ids"]))      # a copy to play the run forward on
    plan = []
    for rel, i, day in sorted(files, key=lambda f: (f[2], f[0])):
        p = Path(root) / FOLDER / rel
        sha, size = sha256_of(p), p.stat().st_size
        e = ids.setdefault(i, {"versions": [], "checks": [], "checked": None})
        e.setdefault("checks", [])
        mine = next((v for v in e["versions"] + e["checks"] if v["file"] == rel), None)
        if mine is not None:
            if mine["sha256"] != sha:
                raise Failed(f"{FOLDER}/{rel} differs from the copy the bucket's record "
                             "holds under that name; a reading is never replaced. Name the "
                             f"new one {day}-2.<ext>")
            plan.append(("known", rel, i, day, sha, size, None))
            continue
        last = latest(e)
        if last and last["sha256"] == sha:
            # Read again and the same: recorded as a check, and not sent.
            plan.append(("unchanged", rel, i, day, sha, size, last))
            e["checks"].append({"file": rel, "sha256": sha, "read": day})
            e["checked"] = max(e.get("checked") or "", day)
            continue
        if last and day < last["read"]:
            raise Failed(f"{FOLDER}/{rel} was read on {day}, before the bucket's latest "
                         f"version of {i} ({last['read']}); an older reading cannot be a "
                         "newer version. Move it out of sources/ if it is an old download")
        kind = "changed" if last else "new"
        plan.append((kind, rel, i, day, sha, size, last))
        e["versions"].append({"file": rel, "sha256": sha, "size": size, "read": day})
        e["checked"] = max(e.get("checked") or "", day)
    return plan, ids


def cmd_up(a, root):
    reg = load_registry(root)
    files, bad = folder_files(root, reg)
    if bad:
        raise Failed(f"{len(bad)} file(s) in {FOLDER}/ are not filed under the registry, "
                     "and nothing is sent until they are:\n  " + "\n  ".join(bad))
    if not files:
        raise Failed(f"nothing in {FOLDER}/ to send: a run that sends nothing is not a "
                     "success")
    bucket = open_bucket(a)
    man, raw = read_manifest(bucket)
    plan, ids = plan_up(root, reg, man, files)
    sends = [p for p in plan if p[0] in ("new", "changed")]
    report = change_report(plan, reg)
    show_report(report, a.dry_run)
    if a.dry_run:
        say(f"\nDry run: {len(sends)} file(s) would be sent; nothing was.")
        return
    if not report["rows"]:
        return
    for kind, rel, i, day, sha, size, _ in sends:
        key = PREFIX + rel
        have = bucket.head(key)
        if have is not None:
            got = bucket.get_bytes(key)
            if got is None or hashlib.sha256(got).hexdigest() != sha:
                raise Failed(f"{key} is in the bucket with other bytes and no record in its "
                             "manifest; nothing over it is sent. A person looks first")
            continue
        bucket.put_file(Path(root) / FOLDER / rel, key, {"sha256": sha, "read": day})
    for i, e in ids.items():
        if i in reg:
            e["url"] = reg[i]["url"]
    doc = {"about": "State documents read on the laptop: src/ops/state_sources.py.",
           "written": datetime.now().isoformat(timespec="seconds"),
           "ids": dict(sorted(ids.items()))}
    if raw is not None:
        import cloud
        cloud.Replacer(bucket, date.today().isoformat()).keep(MANIFEST_KEY)
    bucket.put_bytes(MANIFEST_KEY, json.dumps(doc, indent=1).encode("utf-8"))
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    bucket.put_bytes(f"{REPORTS}{stamp}.json", json.dumps(report, indent=1).encode("utf-8"))
    n = sum(p[5] for p in sends)
    say(f"\nSent {len(sends)} file(s), {n:,} bytes; the change report is at "
        f"{REPORTS}{stamp}.json")


def change_report(plan, reg):
    rows = []
    for kind, rel, i, day, sha, size, prev in plan:
        if kind == "known":
            continue
        rows.append({"what": kind, "id": i, "file": rel, "read": day, "sha256": sha,
                     "size": size, "url": reg.get(i, {}).get("url", ""),
                     "previous": ({"file": prev["file"], "read": prev["read"],
                                   "sha256": prev["sha256"]} if prev else None)})
    return {"written": datetime.now().isoformat(timespec="seconds"), "rows": rows}


def show_report(report, dry=False):
    rows = report["rows"]
    if not rows:
        say("Nothing new: every file here is already in the bucket's record.")
        return
    for what in ("changed", "new", "unchanged"):
        got = [r for r in rows if r["what"] == what]
        if not got:
            continue
        say({"changed": "\nCHANGED since the last reading:",
             "new": "\nNEW: the first reading of these:",
             "unchanged": "\nREAD AGAIN, UNCHANGED:"}[what])
        for r in got:
            tail = (f"  (was {r['previous']['sha256'][:12]}, read {r['previous']['read']})"
                    if r["previous"] and what == "changed" else "")
            say(f"  {r['read']}  {r['sha256'][:12]}  {r['id']}{tail}")


# -------------------------------------------------------------------- down --

def cmd_down(a, root):
    into = Path(a.into).resolve() if a.into else Path(root) / FOLDER
    bucket = open_bucket(a)
    man, _ = read_manifest(bucket)
    rec_path = Path(root) / DOWN_RECORD
    try:
        before = json.loads(rec_path.read_text(encoding="utf-8")).get("latest", {})
    except (OSError, ValueError):
        before = {}
    took = n = 0
    short = []
    now = {}
    for i, e in sorted(man["ids"].items()):
        for v in e.get("versions", []):
            dst = into / v["file"]
            if dst.is_file() and sha256_of(dst) == v["sha256"]:
                continue
            if a.dry_run:
                took += 1
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".part")
            bucket.get_file(PREFIX + v["file"], tmp, v["size"])
            if sha256_of(tmp) != v["sha256"]:
                tmp.unlink(missing_ok=True)
                short.append(v["file"])
                continue
            os.replace(tmp, dst)
            took += 1
            n += v["size"]
        last = latest(e)
        if last:
            now[i] = last["sha256"]
    changed = sorted(i for i in now if i in before and before[i] != now[i])
    new = sorted(i for i in now if i not in before)
    if before:
        say(f"Since this machine last took them: {len(changed)} changed, {len(new)} new.")
        for i in changed:
            last = latest(man["ids"][i])
            say(f"  CHANGED  {last['read']}  {last['sha256'][:12]}  {i}")
        for i in new:
            last = latest(man["ids"][i])
            say(f"  NEW      {last['read']}  {last['sha256'][:12]}  {i}")
    if a.dry_run:
        say(f"Dry run: {took} file(s) would be taken into {into}; none was.")
        return
    if short:
        raise Failed(f"{len(short)} file(s) came down with other bytes than the manifest "
                     "records, and were not kept: " + ", ".join(short))
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(json.dumps({"at": datetime.now().isoformat(timespec="seconds"),
                                    "latest": now}, indent=1), encoding="utf-8")
    say(f"Took {took} file(s), {n:,} bytes, into {into}; {len(now)} documents in all.")


# ------------------------------------------------------------ report, due --

def cmd_report(a, root):
    bucket = open_bucket(a)
    man, _ = read_manifest(bucket)
    since = a.since or "0000-00-00"
    rows = []
    for i, e in sorted(man["ids"].items()):
        vs = e.get("versions", [])
        for k, v in enumerate(vs):
            if v["read"] >= since:
                rows.append((v["read"], "changed" if k else "new", i, v["sha256"]))
    say(f"{len(man['ids'])} documents in the bucket's record"
        + (f"; versions read since {a.since}:" if a.since else "; every version:"))
    for day, what, i, sha in sorted(rows):
        say(f"  {day}  {what:<8} {sha[:12]}  {i}")
    if not rows:
        say("  none")


def due(reg, man, today=None):
    """[(id, why)] for each registered document a browser should read now."""
    today = today or date.today()
    out = []
    for i, r in reg.items():
        if r["read_by"] != "browser" or r["kind"] == "wanted":
            continue
        e = man["ids"].get(i)
        last = (e or {}).get("checked") or (latest(e)["read"] if e and latest(e) else None)
        if not last:
            out.append((i, "never read"))
            continue
        gap = (today - date.fromisoformat(last)).days
        if gap >= CHANGES[r["changes"]]:
            out.append((i, f"last read {last}, {gap} days ago"))
    return out


def cmd_due(a, root):
    reg = load_registry(root)
    bucket = open_bucket(a)
    man, _ = read_manifest(bucket)
    got = due(reg, man)
    say(f"{len(got)} of {sum(1 for r in reg.values() if r['read_by'] == 'browser')} "
        "documents a browser reads are due:")
    for i, why in got:
        say(f"  {i:<56} {why}   {reg[i]['url']}")
    owner = [i for i, r in reg.items() if r["read_by"] == "owner-only"]
    wanted = [i for i, r in reg.items() if r["kind"] == "wanted"]
    say(f"\nThe owner's alone (the General Court's; no automated reader): {len(owner)}. "
        f"Wanted, address not yet known: {len(wanted)}.")


def cmd_check(a, root):
    reg = load_registry(root)
    files, bad = folder_files(root, reg)
    if bad:
        raise Failed("\n  ".join([f"{len(bad)} file(s) in {FOLDER}/ are not filed:"] + bad))
    say(f"{REGISTRY}: {len(reg)} rows read; {len(files)} file(s) in {FOLDER}/ filed under them.")


COMMANDS = {"check": cmd_check, "up": cmd_up, "down": cmd_down, "report": cmd_report,
            "due": cmd_due}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("--dry-run", action="store_true", help="up, down: say, and send nothing")
    ap.add_argument("--into", metavar="FOLDER", help="down: where to put them (default sources/)")
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="report: versions read since then")
    ap.add_argument("--local-bucket", metavar="FOLDER",
                    help="use a folder as the bucket (testing; no credentials)")
    ap.add_argument("--root", default=".", help="the working folder")
    a = ap.parse_args(argv)
    if a.since:
        try:
            date.fromisoformat(a.since)
        except ValueError:
            ap.error(f"--since {a.since}: not YYYY-MM-DD")
    root = Path(a.root).resolve()
    try:
        COMMANDS[a.command](a, root)
    except Failed as e:
        print(f"\nstate_sources.py {a.command} FAILED: {e}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
