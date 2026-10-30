#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.6
"""
The state documents the guides and Learn pages rest on: from the laptop, where
a real browser can read them, to the sessions, which cannot.

    python3 src/ops/state_sources.py check                 the registry reads, and every
                                                            file in sources/ is one it names
    python3 src/ops/state_sources.py up [--dry-run]        the laptop sends what it read
    python3 src/ops/state_sources.py down [--into FOLDER]  a session takes them
    python3 src/ops/state_sources.py report [--since DAY]  what changed, from the bucket's record
    python3 src/ops/state_sources.py due [--used-by X]     registered documents never read,
                                                            or not read in their interval
    python3 src/ops/state_sources.py file FOLDER [...]     file a browser's downloads under
                     [--as ID] [--day DAY] [--dry-run]      sources/, by the address each
                                                            came from

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

THE PRINTOUTS (30 October 2026, the owner's word through the manager). The
owner's printouts of official pages are filed on the laptop by
file_printouts.py in records/sources/printouts/, named and hashed by its
INDEX.csv, and kept out of git. up sends each one the bucket lacks to
sources/printouts/<name>, once its bytes match the index; down puts each
one this machine lacks back in records/sources/printouts/, checked against
the index the same way. A printout is never replaced, here or there.

The nightly never reads sources/: its kit is cloud_kit.json's list, kit-down
takes kit/ alone, and preflight fails if anything in the kit could match
sources/. These are evidence for the people and sessions who write the guides,
not inputs to the build.

FILING DOWNLOADS (Phase 2, 30 October 2026). `file` reads a folder Chrome
saved into (Downloads) and copies each document it can place into
sources/<id>/<day>.<ext>. It places a file by the address Windows recorded
for the download (the HostUrl line of its Zone.Identifier stream, which
Chrome writes on every file it saves), and failing that by a file name that
only one registered address ends in. It copies, never moves or deletes; it
leaves a file it has already filed alone; and it names every state document
it could not place, with the row the registry would need. Only files
modified in the last 14 days are read unless --all says otherwise, so a
Downloads folder of years is not read whole. The day is the file's own
modification day, which is when it was saved, unless --day says otherwise.

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
# The owner's printouts of official pages: filed on the laptop by
# file_printouts.py under the names INDEX.csv gives, with their sha256, and
# kept out of git. up sends them to the bucket beside the readings, and down
# puts them back where file_printouts.py files them.
PRINTOUTS = "records/sources/printouts"
PRINTOUTS_INDEX = PRINTOUTS + "/INDEX.csv"
PRINTOUTS_PREFIX = PREFIX + "printouts/"

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
# Names Windows will not give a folder, and files a desktop leaves behind.
RESERVED = {"con", "prn", "aux", "nul", "printouts", "reports", "manifest", *(f"com{n}" for n in range(1, 10)),
            *(f"lpt{n}" for n in range(1, 10))}
JUNK = {"thumbs.db", "desktop.ini"}
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
    host = (urlsplit(url).hostname or "").lower()
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
        if not ID.match(i or "") or i in RESERVED:
            bad.append(f"{where}: the id is not lower-case letters, digits and hyphens, "
                       "or is a name Windows reserves")
        if i in out:
            bad.append(f"{where}: the id is used twice")
        if r["kind"] not in KINDS:
            bad.append(f"{where}: kind {r['kind']!r} is not one of {sorted(KINDS)}")
        if r["read_by"] not in READ_BY:
            bad.append(f"{where}: read_by {r['read_by']!r} is not one of {sorted(READ_BY)}")
        if r["changes"] not in CHANGES:
            bad.append(f"{where}: changes {r['changes']!r} is not one of {sorted(CHANGES)}")
        if not r["used_by"].strip() or "<" in r["used_by"]:
            bad.append(f"{where}: used_by is empty or a placeholder; say which guide or "
                       "page uses it (a document nothing uses is not registered)")
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
            if n.startswith(".") or n.lower() in JUNK or n.endswith(".part"):
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
    return sorted(files, key=reading_order), bad


def reading_order(f):
    """(day, n, rel): the order readings were made in. 2026-10-30.pdf is the
    first of that day and 2026-10-30-2.pdf the second, which a sort of the
    names alone would put first ("-" sorts before ".")."""
    rel, _, day = f
    m = NAME.match(rel.rsplit("/", 1)[-1])
    return (day, int(m.group(2) or 1) if m else 0, rel)


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
    for rel, i, day in sorted(files, key=reading_order):
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
        if last and reading_order((rel, i, day)) < reading_order((last["file"], i, last["read"])):
            raise Failed(f"{FOLDER}/{rel} was read before the bucket's latest "
                         f"version of {i} ({last['file']}); an older reading cannot be a "
                         "newer version. Move it out of sources/ if it is an old download")
        kind = "changed" if last else "new"
        plan.append((kind, rel, i, day, sha, size, last))
        e["versions"].append({"file": rel, "sha256": sha, "size": size, "read": day})
        e["checked"] = max(e.get("checked") or "", day)
    return plan, ids


def cmd_up(a, root):
    if a.dry_run or getattr(a, "locked", False):
        return _up(a, root)
    import cloud
    try:
        with cloud.machine_lock(root):
            return _up(a, root)
    except cloud.Failed as e:
        raise Failed(str(e))


def _up(a, root):
    reg = load_registry(root)
    files, bad = folder_files(root, reg)
    if bad:
        raise Failed(f"{len(bad)} file(s) in {FOLDER}/ are not filed under the registry, "
                     "and nothing is sent until they are:\n  " + "\n  ".join(bad))
    prints, wrong, missing, unindexed = printouts_here(root)
    if wrong:
        raise Failed(f"{len(wrong)} printout(s) in {PRINTOUTS}/ differ from the sha256 "
                     f"{PRINTOUTS_INDEX} gives them, or have a name it refuses, and nothing "
                     "is sent until they agree:\n  " + "\n  ".join(wrong))
    if not files and not prints:
        raise Failed(f"nothing in {FOLDER}/ or {PRINTOUTS}/ to send: a run that sends "
                     "nothing is not a success")
    bucket = open_bucket(a)
    # Every printout is checked against the bucket before anything is written,
    # so that a printout the bucket holds with other bytes stops the run before
    # a reading is sent, not after.
    todo, same = plan_printouts(bucket, prints)
    if files:
        _readings_up(a, root, reg, files, bucket)
    if prints:
        send_printouts(a, bucket, todo, same)
    if missing or unindexed:
        say(f"Printouts not here, so not sent: {len(missing)} in the index and not filed "
            f"in {PRINTOUTS}/ (python3 src/ops/file_printouts.py --check names them)"
            + (f"; {len(unindexed)} PDF(s) there the index does not name: "
               + ", ".join(unindexed) if unindexed else ""))


PRINTOUT_NAME = re.compile(r"^[a-z0-9][a-z0-9._-]{0,120}\.pdf$")


def printouts_index(root):
    """The index's rows: [row] for each one, its name checked."""
    p = Path(root) / PRINTOUTS_INDEX
    if not p.is_file():
        return []
    with open(p, encoding="utf-8", newline="") as f:
        return [r for r in csv.DictReader(f) if r.get("new_name")]


def printout_name_ok(name):
    return bool(PRINTOUT_NAME.match(name)) and name.split(".")[0] not in RESERVED


def printouts_here(root):
    """(ok, wrong, missing, unindexed): [(row, path)] for each indexed printout
    filed here whose bytes are the sha256 the index gives; the filed ones whose
    are not, or whose name the index should not give; the indexed names not
    filed here; and the PDFs here the index does not name."""
    ok, wrong, missing = [], [], []
    rows = printouts_index(root)
    for r in rows:
        if not printout_name_ok(r["new_name"]):
            wrong.append(f"{PRINTOUTS_INDEX}: {r['new_name']!r} is not a plain lower-case "
                         "name ending .pdf")
            continue
        f = Path(root) / PRINTOUTS / r["new_name"]
        if not f.is_file():
            missing.append(r["new_name"])
        elif sha256_of(f) == r["sha256"]:
            ok.append((r, f))
        else:
            wrong.append(f"{PRINTOUTS}/{r['new_name']}")
    home = Path(root) / PRINTOUTS
    names = {r["new_name"] for r in rows}
    unindexed = sorted(f.name for f in home.glob("*.pdf")) if home.is_dir() else []
    unindexed = [n for n in unindexed if n not in names]
    return ok, wrong, missing, unindexed


def bucket_sha(bucket, key):
    """The sha256 of an object: its own record of it where it carries one,
    else its bytes read; None where there is no such object."""
    meta = bucket.head(key)
    if meta is None:
        return None
    if isinstance(meta, dict) and re.fullmatch(r"[0-9a-f]{64}", str(meta.get("sha256", ""))):
        return meta["sha256"]
    got = bucket.get_bytes(key)
    return None if got is None else hashlib.sha256(got).hexdigest()


def plan_printouts(bucket, prints):
    """([(row, path, key)] to send, how many the bucket holds already), or
    Failed where it holds one with other bytes: a printout is never replaced."""
    todo, same = [], 0
    for r, f in prints:
        key = PRINTOUTS_PREFIX + r["new_name"]
        theirs = bucket_sha(bucket, key)
        if theirs is None:
            todo.append((r, f, key))
        elif theirs != r["sha256"]:
            raise Failed(f"{key} is in the bucket with other bytes than {PRINTOUTS_INDEX} "
                         "gives it; nothing is sent. A person looks first")
        else:
            same += 1
    return todo, same


def send_printouts(a, bucket, todo, same):
    n = sum(f.stat().st_size for _, f, _ in todo)
    if a.dry_run:
        say(f"\nPrintouts: {len(todo)} would be sent, {same} already in the bucket.")
        return
    for r, f, key in todo:
        bucket.put_file(f, key, {"sha256": r["sha256"]})
    say(f"\nPrintouts: sent {len(todo)}, {n:,} bytes; {same} already in the bucket.")


def printouts_down(a, bucket, root, home):
    """(taken, bytes, problems, held, unindexed): each indexed printout the
    bucket holds and `home` lacks, checked against the index; and the
    printouts the bucket holds that this machine's index does not name yet."""
    took = n = 0
    bad = []
    have = {k: v for k, v in bucket.list(PRINTOUTS_PREFIX).items()}
    rows = {r["new_name"]: r for r in printouts_index(root) if printout_name_ok(r["new_name"])}
    held = [k for k in have if k[len(PRINTOUTS_PREFIX):] in rows]
    unindexed = sorted(k[len(PRINTOUTS_PREFIX):] for k in have
                       if k[len(PRINTOUTS_PREFIX):] not in rows)
    for key in sorted(held):
        r = rows[key[len(PRINTOUTS_PREFIX):]]
        dst = home / r["new_name"]
        if dst.is_file():
            if sha256_of(dst) != r["sha256"]:
                bad.append(f"{dst.name} here differs from the index and was left as it is")
            continue
        if a.dry_run:
            took += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        bucket.get_file(key, tmp, have[key])
        if sha256_of(tmp) != r["sha256"]:
            tmp.unlink(missing_ok=True)
            bad.append(f"{key} came down with other bytes than the index gives")
            continue
        os.replace(tmp, dst)
        took += 1
        n += dst.stat().st_size
    return took, n, bad, len(held), unindexed


def _readings_up(a, root, reg, files, bucket):
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
    sent = 0
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
        sent += size
    for i, e in ids.items():
        if i in reg:
            e["url"] = reg[i]["url"]
    doc = {"about": "State documents read on the laptop: src/ops/state_sources.py.",
           "written": datetime.now().isoformat(timespec="seconds"),
           "ids": dict(sorted(ids.items()))}
    if bucket.get_bytes(MANIFEST_KEY) != raw:
        raise Failed(f"{MANIFEST_KEY} changed in the bucket while this ran (another up, "
                     "elsewhere); the files are sent, the record is not. Run up again")
    if raw is not None:
        import cloud
        cloud.Replacer(bucket, date.today().isoformat()).keep(MANIFEST_KEY)
    bucket.put_bytes(MANIFEST_KEY, json.dumps(doc, indent=1).encode("utf-8"))
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    bucket.put_bytes(f"{REPORTS}{stamp}.json", json.dumps(report, indent=1).encode("utf-8"))
    say(f"\nSent {len(sends)} version(s), {sent:,} bytes new to the bucket; recorded "
        f"{len(report['rows'])} reading(s); the change report is at "
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
    """The readings into --into (default sources/), and the printouts into
    records/sources/printouts/, or into <--into>/printouts/ when --into is
    given, so that a session asking to leave the checkout alone gets that.
    A problem with either is told at the end, after the other was taken."""
    into = Path(a.into).resolve() if a.into else Path(root) / FOLDER
    home = into / "printouts" if a.into else Path(root) / PRINTOUTS
    bucket = open_bucket(a)
    man, raw = read_manifest(bucket)
    p_took, p_n, p_bad, p_held, p_new = printouts_down(a, bucket, root, home)
    if raw is None and not p_held and not p_new:
        raise Failed(f"the bucket holds no {MANIFEST_KEY} and no printouts: nothing has been "
                     "sent, or this is the wrong bucket")
    say(f"Printouts: {p_held} in the bucket that the index names; "
        + (f"{p_took} would be taken" if a.dry_run else f"took {p_took}, {p_n:,} bytes")
        + f", into {home}.")
    if p_new:
        say(f"  {len(p_new)} more in the bucket that this machine's {PRINTOUTS_INDEX} does "
            "not name yet (its next pull of dev will): " + ", ".join(p_new))
    problems = list(p_bad)
    if raw is None:
        say(f"No readings yet: the bucket holds no {MANIFEST_KEY}.")
    else:
        try:
            _readings_down(a, root, bucket, man, into)
        except Failed as e:
            problems.append(str(e))
    if problems:
        raise Failed("\n  ".join(["not everything came down:"] + problems))


def _readings_down(a, root, bucket, man, into):
    rec_path = Path(root) / DOWN_RECORD
    try:
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rec = {}
    before = (rec.get("folders") or {}).get(str(into), {})
    took = n = 0
    short, clash = [], []
    now = {}
    for i, e in sorted(man["ids"].items()):
        for v in e.get("versions", []):
            dst = into / v["file"]
            if dst.is_file():
                if sha256_of(dst) != v["sha256"]:
                    clash.append(v["file"])
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
    if clash:
        raise Failed(f"{len(clash)} file(s) here differ from the bucket's under the same "
                     "name and were left as they are; nothing is written over a reading: "
                     + ", ".join(clash))
    if short:
        raise Failed(f"{len(short)} file(s) came down with other bytes than the manifest "
                     "records, and were not kept: " + ", ".join(short))
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    folders = dict(rec.get("folders") or {})
    folders[str(into)] = now
    rec_path.write_text(json.dumps({"at": datetime.now().isoformat(timespec="seconds"),
                                    "folders": folders}, indent=1), encoding="utf-8")
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
        if e.get("url") and e["url"] != r["url"]:
            out.append((i, f"its address changed since it was last read ({e['url']})"))
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
    pool = [r for r in reg.values() if r["read_by"] == "browser"]
    if a.used_by:
        got = [g for g in got if a.used_by in reg[g[0]]["used_by"].split()]
        pool = [r for r in pool if a.used_by in r["used_by"].split()]
        if not pool:
            raise Failed(f"no registered document is used by {a.used_by!r}")
    say(f"{len(got)} of {len(pool)} documents a browser reads"
        + (f" for {a.used_by}" if a.used_by else "") + " are due:")
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


# ------------------------------------------------------------------- file --

RECENT_DAYS = 14
COPY_SUFFIX = re.compile(r" \(\d+\)(?=\.[^.]+$)")     # Chrome's "name (1).pdf"


def norm_url(url):
    """An address as compared: no scheme, no www., the host in lower case,
    no trailing slash, no fragment."""
    p = urlsplit(url.strip())
    host = (p.hostname or "").lower().removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    return f"{host}{path}" + (f"?{p.query}" if p.query else "")


def downloaded_from(path):
    """The address Windows recorded for a download, or None. Chrome writes
    it to the file's Zone.Identifier stream, read on Windows as the file
    name followed by ':Zone.Identifier'. Elsewhere, and for a file saved
    another way, there is none."""
    try:
        # The built-in open, as Chrome's own write goes: on NTFS the name with
        # its colon opens the stream; pathlib is kept out of it.
        with open(str(path) + ":Zone.Identifier", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return None
    for line in text.splitlines():
        k, _, v = line.partition("=")
        if k.strip().lower() == "hosturl" and v.strip().startswith("https://"):
            return v.strip()
    return None


def leaf(url):
    from urllib.parse import unquote
    return unquote(urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]).lower()


def place(path, reg, by_url, by_leaf):
    """(id, how) for a downloaded file, or (None, why)."""
    url = downloaded_from(path)
    if url:
        i = by_url.get(norm_url(url))
        if i:
            return i, f"from {url}"
        loose = [j for k, j in by_url.items() if loose_url(k) == loose_url(norm_url(url))]
        if len(loose) == 1:
            return loose[0], f"from {url}, which differs from the registered address only in case or query"
        if not is_state_url(url):
            return None, f"downloaded from {url}, which the registry does not name"
    name = COPY_SUFFIX.sub("", path.name).lower()
    ids = by_leaf.get(name, [])
    if len(ids) == 1:
        return ids[0], "by its name" + (f" (downloaded from {url})" if url else "")
    if len(ids) > 1:
        return None, f"its name fits {len(ids)} registered addresses: {', '.join(ids)}"
    if url:
        return None, f"downloaded from {url}, which the registry does not name"
    return None, None


def loose_url(n):
    return n.split("?", 1)[0].lower()


def is_state_url(url):
    host = (urlsplit(url).hostname or "").lower()
    return host == "nh.gov" or host.endswith(".nh.gov")


def cmd_file(a, root):
    reg = load_registry(root)
    if not a.paths:
        raise Failed("file needs a folder (or files) to file from, e.g. ~/Downloads")
    by_url = {norm_url(r["url"]): i for i, r in reg.items() if r["url"]}
    by_leaf = {}
    for i, r in reg.items():
        if r["url"] and r["kind"] in ("pdf", "data"):
            by_leaf.setdefault(leaf(r["url"]), []).append(i)
    if a.as_id and a.as_id not in reg:
        raise Failed(f"--as {a.as_id}: not an id in {REGISTRY}")
    if a.as_id and reg[a.as_id]["kind"] == "wanted":
        raise Failed(f"--as {a.as_id}: a wanted row; give it its address and kind first")
    cands = []
    cutoff = datetime.now().timestamp() - RECENT_DAYS * 86400
    for raw in a.paths:
        p = Path(raw).expanduser()
        if p.is_file():
            cands.append(p)
        elif p.is_dir():
            cands += [q for q in sorted(p.iterdir()) if q.is_file()
                      and (a.all or q.stat().st_mtime >= cutoff)]
        else:
            raise Failed(f"{raw}: no such file or folder")
    cands = [q for q in cands if ":" not in q.name and not q.name.endswith((".part", ".crdownload", ".tmp"))
             and q.suffix.lower().lstrip(".") in EXTS]
    if a.as_id and len(cands) != 1:
        raise Failed(f"--as names one document, and {len(cands)} files were given")
    filed, already, unplaced = [], [], []
    base = Path(root) / FOLDER
    claimed = {}                 # (id, file name) -> sha256, for what this run files
    # The oldest download first, so that of two readings in one day the later
    # is -2, as up reads them.
    cands.sort(key=lambda q: (q.stat().st_mtime, q.name))
    for q in cands:
        if a.as_id:
            i, how = a.as_id, "as named"
            url = downloaded_from(q)
            if url and norm_url(url) != norm_url(reg[i]["url"]):
                raise Failed(f"{q.name} was downloaded from {url}, not from {i}'s address "
                             f"{reg[i]['url']}; file it under the right id, or fix the registry")
        else:
            i, how = place(q, reg, by_url, by_leaf)
        if not i:
            url = downloaded_from(q)
            if how or (url and is_state_url(url)):
                unplaced.append((q, how, url))
            continue
        sha = sha256_of(q)
        d = base / i
        day = a.day or date.fromtimestamp(q.stat().st_mtime).isoformat()
        ext = q.suffix.lower().lstrip(".")
        # Already filed only if the same bytes are filed under this same day. The
        # same bytes on a later day are a new reading that found no change, and
        # are filed, so that up records the check and due moves on.
        def taken(f):
            return (i, f.name) in claimed or f.exists()

        def bytes_of(f):
            return claimed.get((i, f.name)) or sha256_of(f)
        today = [f for f in [d / f"{day}.{ext}", *[d / f"{day}-{n}.{ext}" for n in range(2, 100)]]
                 if taken(f)]
        same = [f for f in today if bytes_of(f) == sha]
        if same:
            already.append((q, i, same[0].name))
            continue
        dst = d / (f"{day}.{ext}" if not today else f"{day}-{len(today) + 1}.{ext}")
        if taken(dst):
            raise Failed(f"{FOLDER}/{i}/ has a gap in {day}'s readings; a person looks first")
        claimed[(i, dst.name)] = sha
        filed.append((q, i, dst, how))
        if not a.dry_run:
            import shutil
            d.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".part")
            shutil.copyfile(q, tmp)
            os.replace(tmp, dst)
    verb = "Would file" if a.dry_run else "Filed"
    say(f"{verb} {len(filed)}; {len(already)} already filed; {len(unplaced)} state "
        f"document(s) not placed; of {len(cands)} file(s) read.")
    for q, i, dst, how in filed:
        say(f"  {verb.upper():<10} {q.name}  ->  {FOLDER}/{i}/{dst.name}  ({how})")
    for q, i, name in already:
        say(f"  ALREADY    {q.name}  =  {FOLDER}/{i}/{name}")
    for q, why, url in unplaced:
        say(f"  NOT PLACED {q.name}: {why or 'no address recorded for it and no registered name fits'}")
        if url:
            say(f"             a row for it: {suggest_row(url, reg)}")
    if unplaced:
        raise Failed(f"{len(unplaced)} state document(s) could not be placed (above); what "
                     "could be placed was filed")
    if not filed:
        say("Nothing new to file." + ("" if cands else f" No document saved in the last "
                                       f"{RECENT_DAYS} days was found there."))


def suggest_row(url, reg=None):
    """A registry row for an address it lacks, for a person to check and add."""
    p = urlsplit(url)
    host = (p.hostname or "").removeprefix("www.").replace(".nh.gov", "").replace(".", "-")
    stem = re.sub(r"\.(pdf|html?|aspx|xlsx?|csv)$", "", leaf(url))
    i = f"{host}-{re.sub(r'[^a-z0-9]+', '-', stem).strip('-')[:48].strip('-')}"
    base, n = i, 1
    while reg and i in reg:
        n += 1
        i = f"{base}-{n}"
    kind = "pdf" if leaf(url).endswith(".pdf") else "page"
    row = [i, url, kind, "", "", "", "unknown", "owner-only" if is_gc(url) else "browser",
           "<who uses it>", "discovered", f"downloaded {date.today().isoformat()}"]
    import io
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(row)
    return out.getvalue()


COMMANDS = {"check": cmd_check, "up": cmd_up, "down": cmd_down, "report": cmd_report,
            "due": cmd_due, "file": cmd_file}


def main(argv=None, locked=False):
    """`locked`: the caller (cloud.py sources-up) holds cloud.py's machine lock."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("paths", nargs="*", metavar="PATH",
                    help="file: the folders (or files) a browser saved into")
    ap.add_argument("--dry-run", action="store_true",
                    help="up, down, file: say, and send or copy nothing")
    ap.add_argument("--as", dest="as_id", metavar="ID",
                    help="file: the one file given is this registered document")
    ap.add_argument("--day", metavar="YYYY-MM-DD",
                    help="file: the day it was read (default: the file's own day)")
    ap.add_argument("--all", action="store_true",
                    help=f"file: read every file, not only the last {RECENT_DAYS} days'")
    ap.add_argument("--used-by", metavar="X",
                    help="due: only what this guide or page uses, e.g. learn:state-budget")
    ap.add_argument("--into", metavar="FOLDER", help="down: where to put them (default sources/)")
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="report: versions read since then")
    ap.add_argument("--local-bucket", metavar="FOLDER",
                    help="use a folder as the bucket (testing; no credentials)")
    ap.add_argument("--root", default=".", help="the working folder")
    a = ap.parse_args(argv)
    a.locked = locked
    if a.paths and a.command != "file":
        ap.error(f"{a.command} takes no PATH; only file does")
    for flag in ("since", "day"):
        v = getattr(a, flag)
        if v:
            try:
                if date.fromisoformat(v) > date.today():
                    ap.error(f"--{flag} {v}: a day that has not come")
            except ValueError:
                ap.error(f"--{flag} {v}: not YYYY-MM-DD")
    root = Path(a.root).resolve()
    try:
        COMMANDS[a.command](a, root)
    except Failed as e:
        print(f"\nstate_sources.py {a.command} FAILED: {e}", file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
