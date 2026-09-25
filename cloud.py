#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-25.1
"""
The nightly's kit and the laptop's backup, in the project's private R2 bucket.

    python3 cloud.py kit-list [--sizes]        the kit's paths, from cloud_kit.json
    python3 cloud.py seed-kit [--dry-run]      the laptop sends the kit, the first time
    python3 cloud.py kit-down                  an empty machine takes the kit
    python3 cloud.py kit-up [--dry-run]        ... and sends back what its night changed,
                                               with the night's logs and state
    python3 cloud.py state-down | state-up     the small state files only
    python3 cloud.py clear-refusal             lift the refusal record the night
                                               keeps in the bucket (a person's call)
    python3 cloud.py site-up --run ID          the night's built site, as one archive
    python3 cloud.py site-down --run ID        ... and back, for the publish job
    python3 cloud.py backup [--dry-run] [--with-site]
                                               everything git does not hold

    --local-bucket FOLDER   a folder stands in for the bucket, for testing
    --root FOLDER           the working folder (default: the current one)
    --workers N             transfers at once (default 8)

Run from the repository root. Credentials come from keys.r2(): the
environment on GitHub's machine, secrets.json on the laptop. Nothing here asks
the General Court, YouTube or GitHub anything; it talks to the bucket only,
and boto3 is needed only for that.

WHY THIS EXISTS

The nightly moved to GitHub's machines, which start empty every night. The
build reads 1.9 GB that git does not hold -- the day's files, the saved bill
pages, the dumped database, the outputs a build reads before it rewrites
them -- out of the 44.5 GB on the laptop, and cloud_kit.json lists it. The
laptop sends it once (seed-kit); each night takes it down (kit-down), builds,
and sends back what it changed (kit-up). The laptop's own copy of everything
else goes up with backup.

WHAT IT WILL NOT DO

Overwrite or delete anything in the bucket outright. An object about to be
replaced or removed is first copied to replaced/<date>/<prefix>/<path>, which
the bucket's lifecycle rule keeps for 30 days. Removals also stop above a
small share of what is there, because a walk of the wrong folder looks
exactly like a thousand deletions.

Report success for a partial transfer. Every file is checked against its size
and sha256 on the way down, every command ends on a line of counts and bytes,
and anything short is a non-zero exit with a plain sentence saying what.

Let two machines each overwrite the other. Each kit file has one owner. The
laptop's seed-kit never sends a file the night owns over the night's copy,
and the night's kit-up never sends a file the laptop owns; if the bucket's
copy of a file changed after this machine took it down, kit-up keeps the
bucket's and files its own under replaced/ rather than choose.

Send a secret or a reader's words. cloud_kit.json's "never" list is applied to
every command, and preflight holds the list to what it must contain.

THE BUCKET

    kit/<path>             the kit, laid out as the working folder is
    backup/<path>          the laptop's backup
    replaced/<date>/...    what a command would otherwise have overwritten or removed
    logs/<date>/<file>     the night's logs
    nights/<run>/          the night's built site, one archive, for the publish job
    state/<file>           refused.json, census.json and the rest (cloud_kit.json);
                           kit-manifest.json and backup-manifest.json, the size,
                           sha256 and date of every file sent, which is how an
                           unchanged file is never sent twice

On a machine, small state lives under archive/ -- archive/refused.json,
archive/census.json -- and only the bucket calls it state/. This machine's
own record lives in archive/cloud/: what kit-down fetched, which build_all.py
reads as "this folder is built from the kit"; what state-down took, which
state-up reads so a copy taken down is never sent back over a newer one; and
a cache of hashes so an unchanged file is not read twice either.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import child

KIT_FILE = "cloud_kit.json"
LOCAL = "archive/cloud"
KIT_RECORD = f"{LOCAL}/kit-down.json"
STATE_RECORD = f"{LOCAL}/state-down.json"
HASHES = f"{LOCAL}/hashes.json"
LOCK = f"{LOCAL}/lock"
MANIFEST = "state/{}-manifest.json"
MB = 1 << 20

# A removal is a decision. A walk of the wrong folder, or a disk that did not
# mount, looks exactly like a thousand files deleted, and moving them all to
# replaced/ would have them gone in 30 days. Above this share (or this count),
# nothing is removed without --allow-removals.
REMOVE_SHARE, REMOVE_MAX = 0.02, 1000

# Long transfers record their progress this often, so an interrupted first
# backup resumes rather than starting again.
CHECKPOINT = 300


class Failed(Exception):
    """A command that cannot go on: its message is the sentence the person reads."""


# What must never reach a log: GitHub's run logs of a public repository are
# public, and an error from the S3 client can carry the endpoint -- the
# account ID is in its host name -- which GitHub masks only if it was saved
# as a secret. R2Bucket adds the values it was given; everything printed
# passes through scrub().
_PRIVATE = []


def scrub(msg):
    msg = str(msg)
    for v in _PRIVATE:
        if v:
            msg = msg.replace(v, "<private>")
    return msg


def say(msg=""):
    print(scrub(msg), flush=True)


def human(n):
    n = float(n)
    if n < 1000:
        return f"{n:,.0f} bytes"
    for unit in ("KB", "MB", "GB", "TB"):
        n /= 1000
        if n < 1000 or unit == "TB":
            return f"{n:,.2f} {unit}"


# ---------------------------------------------------------------- patterns --

def glob_re(pat):
    """A glob over /-separated relative paths, as a regex. * and ? stay inside
    one folder; ** crosses any number of folders, none included."""
    out, i = ["^"], 0
    while i < len(pat):
        if pat.startswith("**/", i):
            out.append("(?:[^/]*/)*")
            i += 3
        elif pat.startswith("**", i):
            out.append(".*")
            i += 2
        else:
            c = pat[i]
            out.append("[^/]*" if c == "*" else "[^/]" if c == "?" else re.escape(c))
            i += 1
    out.append("$")
    return re.compile("".join(out))


def check_rel(p):
    """A relative /-path that cannot climb out of the working folder."""
    if (not isinstance(p, str) or not p or "\\" in p or p.startswith("/")
            or re.match(r"^[A-Za-z]:", p)
            or any(s in ("", ".", "..") for s in p.split("/"))):
        raise Failed(f"{KIT_FILE}: {p!r} is not a plain relative path")
    return p


def local(root, rel):
    return Path(root).joinpath(*rel.split("/"))


def expand(root, pat):
    """Every file under root matching one glob, as sorted /-paths. Only the
    folders the pattern can reach are walked: "Docket_*.txt" reads the root,
    not the 44 GB below it."""
    segs = pat.split("/")
    fixed = []
    for s in segs[:-1]:
        if "*" in s or "?" in s:
            break
        fixed.append(s)
    base = local(root, "/".join(fixed)) if fixed else Path(root)
    rx, deep, depth = glob_re(pat), "**" in pat, len(segs) - len(fixed)
    out = []
    if not base.is_dir():
        return out
    stack = [(base, "/".join(fixed), 1)]
    while stack:
        d, rel, lvl = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            r = f"{rel}/{e.name}" if rel else e.name
            if e.is_dir(follow_symlinks=False):
                if deep or lvl < depth:
                    stack.append((Path(e.path), r, lvl + 1))
            elif e.is_file(follow_symlinks=False) and rx.match(r):
                out.append(r)
    return sorted(out)


# --------------------------------------------------------------- the kit ----

def load_kit(root):
    p = Path(root) / KIT_FILE
    if not p.exists():
        raise Failed(f"No {KIT_FILE} in {Path(root).resolve()}. Run this from the "
                     "repository root, or give --root.")
    try:
        kit = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise Failed(f"{KIT_FILE} will not read: {e}")
    for e in kit.get("kit", []):
        if e.get("owner") not in ("night", "laptop"):
            raise Failed(f"{KIT_FILE}: an entry's owner is {e.get('owner')!r}, "
                         "not 'night' or 'laptop'")
        for x in list(e.get("paths", [])) + list(e.get("globs", [])):
            check_rel(x)
    for s in kit.get("state", []):
        check_rel(s["path"])
        if not s.get("key") or "/" in s["key"]:
            raise Failed(f"{KIT_FILE}: state key {s.get('key')!r} is not a plain name")
    return kit


def never_rx(kit):
    return [glob_re(g) for g in (kit.get("never") or {}).get("globs", [])]


def entry_matches(e, rel):
    return rel in e.get("paths", []) or any(glob_re(g).match(rel)
                                            for g in e.get("globs", []))


def owner_of(kit, rel):
    for e in kit.get("kit", []):
        if entry_matches(e, rel):
            return e["owner"]
    return None


def kit_files(root, kit):
    """({path: owner}, [entries that match nothing], [held back by never]).

    A required entry that matches nothing is missing: a partial kit builds a
    smaller site that passes its own checks, so it is a failure, not a note.
    """
    never = never_rx(kit)
    files, missing, held = {}, [], []
    for e in kit.get("kit", []):
        owner, found = e["owner"], []
        for p in e.get("paths", []):
            if local(root, p).is_file():
                found.append(p)
            elif not e.get("optional"):
                missing.append(p)
        for g in e.get("globs", []):
            got = expand(root, g)
            if not got and not e.get("optional"):
                missing.append(g)
            found.extend(got)
        for p in found:
            if any(rx.match(p) for rx in never):
                held.append(p)
                continue
            if files.get(p, owner) != owner:
                raise Failed(f"{KIT_FILE} gives {p} two owners; one file has one writer")
            files[p] = owner
    return files, missing, held


# ----------------------------------------------------------------- hashing --

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(4 * MB)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


class Hashes:
    """sha256 per file, reused while its size and date are unchanged."""

    def __init__(self, root):
        self.root = Path(root)
        self.path = local(root, HASHES)
        self.lock = threading.Lock()
        try:
            self.seen = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.seen = {}

    def entry(self, rel):
        """{"size", "sha256", "mtime_ns"} for a file as it stands now."""
        st = local(self.root, rel).stat()
        with self.lock:
            hit = self.seen.get(rel)
        if hit and hit[0] == st.st_size and hit[1] == st.st_mtime_ns:
            sha = hit[2]
        else:
            sha = sha256_of(local(self.root, rel))
            with self.lock:
                self.seen[rel] = [st.st_size, st.st_mtime_ns, sha]
        return {"size": st.st_size, "sha256": sha, "mtime_ns": st.st_mtime_ns}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with self.lock:
            tmp.write_text(json.dumps(self.seen), encoding="utf-8")
        os.replace(tmp, self.path)


def hash_all(hashes, rels, workers, what):
    """({rel: entry}, [failures]) for every file, several at a time."""
    out, bad = {}, []
    t0, last = time.time(), [time.time()]

    def one(rel):
        try:
            return rel, hashes.entry(rel), None
        except OSError as e:
            return rel, None, str(e)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for n, (rel, ent, err) in enumerate(ex.map(one, rels), 1):
            if err:
                bad.append(f"{rel}: {err}")
            else:
                out[rel] = ent
            if time.time() - last[0] > 30:
                last[0] = time.time()
                say(f"  read {n:,} of {len(rels):,} {what} ({time.time() - t0:.0f}s)")
    return out, bad


# ---------------------------------------------------------------- buckets --

class FolderBucket:
    """A folder standing in for the bucket: the same keys, as files. Object
    metadata sits beside them under .meta/, which no listing shows."""

    def __init__(self, folder):
        self.root = Path(folder)
        self.root.mkdir(parents=True, exist_ok=True)

    def describe(self):
        return f"the folder {self.root}"

    def _p(self, key):
        return self.root.joinpath(*key.split("/"))

    def _meta(self, key):
        return Path(str(self.root.joinpath(".meta", *key.split("/"))) + ".json")

    def list(self, prefix):
        base = self._p(prefix.rstrip("/"))
        out = {}
        if not base.is_dir():
            return out
        for dirpath, _, names in os.walk(base):
            for n in names:
                f = Path(dirpath) / n
                out[f.relative_to(self.root).as_posix()] = f.stat().st_size
        return out

    def head(self, key):
        if not self._p(key).exists():
            return None
        try:
            return json.loads(self._meta(key).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def put_file(self, src, key, meta):
        dst = self._p(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
        m = self._meta(key)
        m.parent.mkdir(parents=True, exist_ok=True)
        m.write_text(json.dumps(meta), encoding="utf-8")

    def get_file(self, key, dst):
        shutil.copyfile(self._p(key), dst)

    def copy(self, src, dst):
        d = self._p(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._p(src), d)
        if self._meta(src).exists():
            self._meta(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self._meta(src), self._meta(dst))

    def delete(self, key):
        self._p(key).unlink(missing_ok=True)
        self._meta(key).unlink(missing_ok=True)

    def get_bytes(self, key):
        try:
            return self._p(key).read_bytes()
        except FileNotFoundError:
            return None

    def put_bytes(self, key, data):
        dst = self._p(key)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dst)


class NotAsked(FolderBucket):
    """For a --dry-run on a machine that cannot reach the bucket yet: an empty
    bucket, so the run can still show everything a first upload would send."""

    def __init__(self, why):
        self.why = why

    def describe(self):
        return f"the bucket (not asked: {self.why})"

    def list(self, prefix):
        return {}

    def head(self, key):
        return None

    def get_bytes(self, key):
        return None


class R2Bucket:
    """Cloudflare R2 through its S3 endpoint. boto3 is imported here and
    nowhere else, so every other command, preflight included, runs without it."""

    def __init__(self, cfg, workers):
        _PRIVATE.extend(v for v in (cfg["account"], cfg["key_id"], cfg["secret"])
                        if len(v) >= 6)
        try:
            import boto3
            from boto3.s3.transfer import TransferConfig
            from botocore.config import Config
            from botocore.exceptions import ClientError
        except ImportError:
            raise Failed("cloud.py needs boto3 to reach R2: python3 -m pip install "
                         "boto3. --local-bucket FOLDER tests without it.")
        self.ClientError = ClientError
        # A large file goes up in four parts at once, beside the other workers.
        kw = dict(retries={"max_attempts": 10, "mode": "standard"},
                  max_pool_connections=workers * 4 + 4,
                  connect_timeout=30, read_timeout=300, signature_version="s3v4")
        try:
            # botocore 1.36 began sending checksums R2 did not accept at first;
            # asking for them only when an operation requires one works with
            # both.
            conf = Config(request_checksum_calculation="when_required",
                          response_checksum_validation="when_required", **kw)
        except TypeError:
            conf = Config(**kw)
        self.s3 = boto3.client(
            "s3", endpoint_url=f"https://{cfg['account']}.r2.cloudflarestorage.com",
            aws_access_key_id=cfg["key_id"], aws_secret_access_key=cfg["secret"],
            region_name="auto", config=conf)
        self.bucket = cfg["bucket"]
        # R2 wants every part but the last the same size, which this gives.
        self.tc = TransferConfig(multipart_threshold=64 * MB,
                                 multipart_chunksize=64 * MB, max_concurrency=4)

    def describe(self):
        return f"the R2 bucket {self.bucket}"

    def _missing(self, e):
        err = getattr(e, "response", {}) or {}
        return (err.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound")
                or err.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404)

    def list(self, prefix):
        out = {}
        pages = self.s3.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix)
        for page in pages:
            for o in page.get("Contents") or []:
                out[o["Key"]] = o["Size"]
        return out

    def head(self, key):
        try:
            got = self.s3.head_object(Bucket=self.bucket, Key=key)
        except self.ClientError as e:
            if self._missing(e):
                return None
            raise
        return dict(got.get("Metadata") or {})

    def put_file(self, src, key, meta):
        self.s3.upload_file(str(src), self.bucket, key,
                            ExtraArgs={"Metadata": meta}, Config=self.tc)

    def get_file(self, key, dst):
        self.s3.download_file(self.bucket, key, str(dst), Config=self.tc)

    def copy(self, src, dst):
        self.s3.copy({"Bucket": self.bucket, "Key": src}, self.bucket, dst,
                     Config=self.tc)

    def delete(self, key):
        self.s3.delete_object(Bucket=self.bucket, Key=key)

    def get_bytes(self, key):
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.ClientError as e:
            if self._missing(e):
                return None
            raise

    def put_bytes(self, key, data):
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data)


def open_bucket(a, preview=False):
    """The bucket named on the command line or by keys.r2(). With preview, a
    dry run that cannot reach it compares with an empty bucket and says so."""
    if a.local_bucket:
        return FolderBucket(a.local_bucket)
    try:
        import keys
        return R2Bucket(keys.r2(), a.workers)
    except (Failed, SystemExit) as e:
        if preview and a.dry_run:
            msg = str(e)
            return NotAsked("no R2 credentials here" if "R2_" in msg else
                            "boto3 is not installed" if "boto3" in msg else
                            msg.splitlines()[0][:80])
        raise Failed(str(e))


# ------------------------------------------------------- what the bucket holds --

def read_manifest(bucket, name):
    """(doc, raw) for the bucket's manifest; (None, None) when it has none."""
    key = MANIFEST.format(name)
    try:
        raw = bucket.get_bytes(key)
    except Exception as e:                                      # noqa: BLE001
        raise Failed(f"could not read {key} from {bucket.describe()}: "
                     f"{type(e).__name__}: {e}")
    if raw is None:
        return None, None
    try:
        doc = json.loads(raw.decode("utf-8"))
        if not isinstance(doc.get("files"), dict):
            raise ValueError("no files table")
    except (ValueError, AttributeError) as e:
        raise Failed(f"{key} in {bucket.describe()} will not read ({e}); nothing "
                     "was changed")
    return doc, raw


class Replacer:
    """Copies an object to replaced/<date>/<prefix>/<path> before it is
    overwritten or removed. A path replaced twice in a day keeps both: the
    second copy takes the time as a suffix rather than overwrite the first."""

    def __init__(self, bucket, day):
        self.bucket, self.day = bucket, day
        self.stamp = datetime.now().strftime("%H%M%S")
        self.taken = set(bucket.list(f"replaced/{day}/"))
        self.lock = threading.Lock()
        self.n = 0

    def keep(self, key):
        dst = f"replaced/{self.day}/{key}"
        with self.lock:
            if dst in self.taken:
                dst = f"{dst}~{self.stamp}"
            self.taken.add(dst)
        self.bucket.copy(key, dst)
        with self.lock:
            self.n += 1
        return dst


def write_manifest(bucket, name, changes, removed, by, replacer, keep_old=True):
    """Merge this run's changes into the bucket's manifest as it stands NOW,
    so what another machine recorded meanwhile is kept, and put it back. The
    copy it replaces goes to replaced/ like anything else -- except a
    checkpoint's, which only ever adds to the one it replaces."""
    cur, raw = read_manifest(bucket, name)
    files = dict((cur or {}).get("files", {}))
    files.update(changes)
    for p in removed:
        files.pop(p, None)
    doc = {"prefix": name, "written": datetime.now().isoformat(timespec="seconds"),
           "by": by, "count": len(files),
           "bytes": sum(e["size"] for e in files.values()),
           "files": dict(sorted(files.items()))}
    key = MANIFEST.format(name)
    if raw is not None and keep_old:
        replacer.keep(key)
    bucket.put_bytes(key, json.dumps(doc, indent=0).encode("utf-8"))
    return doc


# -------------------------------------------------------------- transfers --

class Progress:
    def __init__(self, what, n, total):
        self.what, self.n, self.total = what, n, total
        self.done = self.bytes = 0
        self.t0 = self.last = time.time()
        self.lock = threading.Lock()

    def tick(self, size):
        with self.lock:
            self.done += 1
            self.bytes += size
            now = time.time()
            if now - self.last < 30:
                return
            self.last = now
            done, got = self.done, self.bytes
            rate = got / max(1.0, now - self.t0)
        left = (self.total - got) / rate if rate else 0
        say(f"  {self.what} {done:,} of {self.n:,} files, {human(got)} of "
            f"{human(self.total)}, {human(rate)}/s"
            + (f", about {left / 3600:.1f} h left" if left > 5400 else
               f", about {left / 60:.0f} min left" if left > 90 else ""))


class Checkpoint:
    """Records each file as it lands, and writes the manifest every
    CHECKPOINT seconds, so an interrupted run resumes rather than restarts."""

    def __init__(self, bucket, name, by, replacer, base=None):
        self.bucket, self.name, self.by, self.replacer = bucket, name, by, replacer
        self.done = dict(base or {})
        self.lock = threading.Lock()
        self.last = time.time()
        self.writing = False
        self.first = True

    def __call__(self, rel, ent):
        with self.lock:
            self.done[rel] = ent
            if self.writing or time.time() - self.last < CHECKPOINT:
                return
            self.writing = True
            snap, first = dict(self.done), self.first
        try:
            write_manifest(self.bucket, self.name, snap, [], self.by + " (in progress)",
                           self.replacer, keep_old=first)
            with self.lock:
                self.first = False
        except Exception as e:                                  # noqa: BLE001
            say(f"  (progress not recorded this time: {type(e).__name__}: {e})")
        finally:
            with self.lock:
                self.last, self.writing = time.time(), False


def send(bucket, root, prefix, todo, remote_keys, replacer, workers, record=None):
    """Upload {rel: entry} under prefix/, keeping any object it replaces.
    Returns ({rel: entry} sent, [failures])."""
    sent, bad = {}, []
    lock = threading.Lock()
    prog = Progress("sent", len(todo), sum(e["size"] for e in todo.values()))

    def one(item):
        rel, ent = item
        key = f"{prefix}/{rel}"
        try:
            src = local(root, rel)
            st = src.stat()
            if st.st_size != ent["size"] or st.st_mtime_ns != ent["mtime_ns"]:
                raise OSError("it changed while this ran; the next run sends it")
            if key in remote_keys:
                replacer.keep(key)
            bucket.put_file(src, key, {"sha256": ent["sha256"],
                                       "mtime_ns": str(ent["mtime_ns"])})
        except Exception as e:                                  # noqa: BLE001
            with lock:
                bad.append(f"{rel}: {type(e).__name__}: {e}")
            return
        with lock:
            sent[rel] = ent
        prog.tick(ent["size"])
        if record:
            record(rel, ent)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, sorted(todo.items())))
    return sent, bad


def resumed(bucket, prefix, entries, known, remote_keys):
    """Objects in the bucket the manifest does not know, left by a run that
    stopped before it recorded them. Where one holds the same bytes -- its own
    sha256 says so -- it is recorded, not sent again, and not moved to
    replaced/ as though it were something older."""
    have = {}
    for rel, ent in entries.items():
        key = f"{prefix}/{rel}"
        if rel in known or remote_keys.get(key) != ent["size"]:
            continue
        if (bucket.head(key) or {}).get("sha256") == ent["sha256"]:
            have[rel] = ent
    return have


def diff(entries, known, have, prefix, remote_keys):
    """(to send, unchanged): a file is unchanged when what the bucket holds
    under its key has its size and sha256. A manifest entry whose object has
    gone from the bucket is sent again rather than trusted."""
    todo, same = {}, []
    for rel, ent in entries.items():
        was = have.get(rel) or (known.get(rel) if f"{prefix}/{rel}" in remote_keys
                                else None)
        if was and was["sha256"] == ent["sha256"] and was["size"] == ent["size"]:
            same.append(rel)
        else:
            todo[rel] = ent
    return todo, same


# ----------------------------------------------------------------- guards --

class machine_lock:
    """One cloud.py at a time on a machine: two would each write a manifest
    from what they alone had seen."""

    def __init__(self, root):
        self.path = local(root, LOCK)

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and time.time() - self.path.stat().st_mtime < 180:
            held = self.path.read_text(encoding="utf-8", errors="replace").strip()
            raise Failed(f"{LOCK} is held ({held}): another cloud.py is running "
                         "here. Wait for it.")
        self.path.write_text(f"pid {os.getpid()} since {datetime.now():%H:%M}",
                             encoding="utf-8")
        self.stop = threading.Event()

        def beat():
            while not self.stop.wait(60):
                try:
                    os.utime(self.path, None)
                except OSError:
                    pass
        threading.Thread(target=beat, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.path.unlink(missing_ok=True)
        return False


def quiet_disk(root):
    """A build or a nightly rewriting the outputs right now would have this
    send a file half written. build_all touches .build.lock every 30 seconds
    and nightly.py holds .nightly.lock for the night."""
    for name, live in ((".build.lock", 180), (".nightly.lock", 6 * 3600)):
        p = local(root, name)
        if p.exists() and time.time() - p.stat().st_mtime < live:
            raise Failed(f"{name} is fresh: a build or a nightly is writing the "
                         "files this would send. Run this when it has finished.")


def removal_ok(n, total, allow):
    return allow or n <= max(1, min(REMOVE_MAX, int(total * REMOVE_SHARE)))


def show(label, rels, sizes, limit=8):
    if not rels:
        return
    say(f"  {label}: {len(rels):,} files, {human(sum(sizes.get(r, 0) for r in rels))}")
    for r in sorted(rels)[:limit]:
        say(f"      {r}")
    if len(rels) > limit and limit:
        say(f"      ... and {len(rels) - limit:,} more")


def sizes_of(entries):
    return {r: e["size"] for r, e in entries.items()}


# --------------------------------------------------------------- commands --

def cmd_kit_list(a, root):
    kit = load_kit(root)
    files, missing, held = kit_files(root, kit)
    sizes = {p: local(root, p).stat().st_size for p in files}
    for p in sorted(files):
        print(f"{sizes[p]}\t{p}" if a.sizes else p)
    err = sys.stderr
    if a.sizes:
        for e in kit["kit"]:
            mine = [p for p in files if entry_matches(e, p)]
            print(f"  {len(mine):>7,} files {human(sum(sizes[p] for p in mine)):>12}  "
                  f"[{e['owner']}] {e['what'][:72]}", file=err)
    print(f"kit: {len(files):,} files, {human(sum(sizes.values()))} "
          f"({sum(1 for o in files.values() if o == 'night'):,} the night's, "
          f"{sum(1 for o in files.values() if o == 'laptop'):,} the laptop's)",
          file=err, flush=True)
    if held:
        print(f"  {len(held):,} matched and held back by the never list: "
              + ", ".join(held[:5]), file=err)
    if missing:
        raise Failed(f"{len(missing)} entr{'y' if len(missing) == 1 else 'ies'} of "
                     f"{KIT_FILE} match nothing here: {', '.join(missing[:8])}")


def cmd_seed_kit(a, root):
    kit = load_kit(root)
    quiet_disk(root)
    files, missing, _ = kit_files(root, kit)
    if missing:
        raise Failed(f"not sending a partial kit: {', '.join(missing[:8])} "
                     f"{'is' if len(missing) == 1 else 'are'} missing here, and a kit "
                     "without them builds a smaller site that passes its own checks.")
    bucket = open_bucket(a, preview=True)
    hashes = Hashes(root)
    say(f"seed-kit: {len(files):,} files in {KIT_FILE}; reading them")
    entries, bad = hash_all(hashes, sorted(files), a.workers, "kit files")
    hashes.save()
    if bad:
        raise Failed(f"{len(bad)} kit files would not read: {'; '.join(bad[:4])}")
    man, _ = read_manifest(bucket, "kit")
    known = (man or {}).get("files", {})
    remote = bucket.list("kit/")
    have = resumed(bucket, "kit", entries, known, remote)
    todo, same = diff(entries, known, have, "kit", remote)
    # The night's own files: sent while the bucket's kit has none, never over
    # a copy the kit records -- which, after the first night, is the night's.
    kept = [r for r in todo if files[r] == "night" and r in known
            and f"kit/{r}" in remote]
    for r in kept:
        todo.pop(r)
    elsewhere = [r for r in known if r not in entries]
    total = sum(e["size"] for e in entries.values())
    say(f"  {'first seed of' if man is None else 'the kit is already in'} "
        f"{bucket.describe()}: {len(entries):,} files, {human(total)} here")
    sz = sizes_of(entries)
    show("to send", list(todo), sz)
    show("unchanged, not sent", same, sz, limit=0)
    show("the night's own; its copy in the bucket stands", kept, sz)
    show("in the bucket's kit and not here; left as they are", elsewhere,
         {r: known[r]["size"] for r in elsewhere})
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(todo):,} files, "
            f"{human(sum(e['size'] for e in todo.values()))} would go to kit/ in "
            f"{bucket.describe()}.")
        return
    day = f"{datetime.now():%Y-%m-%d}"
    rep = Replacer(bucket, day)
    ck = Checkpoint(bucket, "kit", "seed-kit", rep, base=have)
    sent, fails = send(bucket, root, "kit", todo, remote, rep, a.workers, record=ck)
    doc = write_manifest(bucket, "kit", {**have, **sent}, [], "seed-kit", rep,
                         keep_old=ck.first)
    say(f"seed-kit: sent {len(sent):,} files, "
        f"{human(sum(e['size'] for e in sent.values()))}; {len(same):,} unchanged; "
        f"{len(kept):,} left as the night has them; {rep.n:,} older copies kept "
        f"under replaced/{day}/")
    say(f"  {MANIFEST.format('kit')}: {doc['count']:,} files, {human(doc['bytes'])}")
    if fails:
        raise Failed(f"{len(fails)} of {len(todo):,} files did not send, so the kit "
                     f"in the bucket is short: {'; '.join(fails[:4])}. Run seed-kit "
                     "again: what did send is recorded and will not go twice.")


def cmd_kit_down(a, root):
    kit = load_kit(root)
    bucket = open_bucket(a)
    man, _ = read_manifest(bucket, "kit")
    if man is None:
        raise Failed(f"{bucket.describe()} has no {MANIFEST.format('kit')}: the "
                     "laptop's seed-kit has not run, so there is no kit to take.")
    want = man["files"]
    # What the kit's definition requires and the bucket does not hold is the
    # same partial kit as a failed download, and is found before one.
    short = []
    for e in kit.get("kit", []):
        if e.get("optional"):
            continue
        short += [p for p in e.get("paths", []) if p not in want]
        short += [g for g in e.get("globs", [])
                  if not any(glob_re(g).match(p) for p in want)]
    rec_path = local(root, KIT_RECORD)
    prev = {}
    if rec_path.exists():
        try:
            prev = json.loads(rec_path.read_text(encoding="utf-8")).get("files", {})
        except (OSError, ValueError):
            prev = {}
    todo, here, clash = {}, [], []
    for rel, ent in want.items():
        f = local(root, rel)
        if not f.exists():
            todo[rel] = ent
            continue
        sha = sha256_of(f)
        if sha == ent["sha256"] and f.stat().st_size == ent["size"]:
            here.append(rel)
        elif rel in prev and prev[rel][1] == sha:
            todo[rel] = ent             # an earlier kit-down's copy: safe to replace
        else:
            clash.append(rel)           # this machine's own: left alone
    total = sum(e["size"] for e in want.values())
    say(f"kit-down: {len(want):,} files, {human(total)} in kit/ of "
        f"{bucket.describe()}; {len(todo):,} to fetch, {len(here):,} already here")
    if a.dry_run:
        say(f"--dry-run: nothing fetched. {len(todo):,} files, "
            f"{human(sum(e['size'] for e in todo.values()))} would come down; "
            f"{len(clash):,} here differ from the kit; the definition requires "
            f"{len(short):,} the bucket lacks.")
        return
    got, bad = set(), []
    lock = threading.Lock()
    prog = Progress("fetched", len(todo), sum(e["size"] for e in todo.values()))

    def one(item):
        rel, ent = item
        dst = local(root, rel)
        tmp = dst.with_name(dst.name + ".part")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            bucket.get_file(f"kit/{rel}", tmp)
            size, sha = tmp.stat().st_size, sha256_of(tmp)
            if size != ent["size"] or sha != ent["sha256"]:
                raise OSError(f"arrived as {size:,} bytes, sha256 {sha[:12]}; the "
                              f"manifest says {ent['size']:,}, {ent['sha256'][:12]}")
            os.replace(tmp, dst)
            ns = int(ent.get("mtime_ns") or 0)
            if ns:
                os.utime(dst, ns=(ns, ns))
        except Exception as e:                                  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            with lock:
                bad.append(f"{rel}: {type(e).__name__}: {e}")
            return
        with lock:
            got.add(rel)
        prog.tick(size)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(one, sorted(todo.items())))
    # THE RECORD: what arrived, which kit-up compares the night's files with,
    # and which build_all.py reads as "this folder is built from the kit".
    now = datetime.now()
    arrived = {r: [want[r]["size"], want[r]["sha256"], int(want[r].get("mtime_ns") or 0)]
               for r in sorted(set(here) | got)}
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    rec_path.write_text(json.dumps({
        "at": now.isoformat(timespec="seconds"), "date": f"{now:%Y-%m-%d}",
        "epoch": time.time(), "manifest_written": man.get("written"),
        "files": arrived}), encoding="utf-8")
    say(f"kit-down: fetched {len(got):,} files, {human(sum(want[r]['size'] for r in got))}; "
        f"{len(here):,} were already here; every one checked against its size and "
        "sha256")
    problems = []
    if bad:
        problems.append(f"{len(bad)} files did not arrive whole: {'; '.join(bad[:4])}.")
    if clash:
        problems.append(f"{len(clash)} files here differ from the kit and were left "
                        f"as they are, kit-down being for an empty machine: "
                        f"{', '.join(clash[:4])}.")
    if short:
        problems.append(f"{KIT_FILE} requires {', '.join(short[:6])}, and the "
                        "bucket's kit holds none of it: run seed-kit on the laptop.")
    if problems:
        raise Failed("THE KIT IS SHORT. " + " ".join(problems)
                     + " A partial kit builds a smaller site that passes its own checks.")


def log_files(root, kit, since):
    never = never_rx(kit)
    out = set()
    for g in (kit.get("logs") or {}).get("globs", []):
        for rel in expand(root, g):
            if not any(rx.match(rel) for rx in never) \
                    and local(root, rel).stat().st_mtime >= since - 1:
                out.add(rel)
    return sorted(out)


def put_logs(bucket, root, logs, day):
    sent, bad = [], []
    existing = bucket.list(f"logs/{day}/")
    stamp = datetime.now().strftime("%H%M%S")
    for rel in logs:
        key = f"logs/{day}/{rel.rsplit('/', 1)[-1]}"
        if key in existing:
            key = f"{key}~{stamp}"
        try:
            bucket.put_file(local(root, rel), key, {})
            sent.append(rel)
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"{rel} (log): {type(e).__name__}: {e}")
    return sent, bad


def state_present(root, kit):
    return [s for s in kit.get("state", []) if local(root, s["path"]).is_file()]


def _sha(data):
    return None if data is None else hashlib.sha256(data).hexdigest()


def load_state_record(root):
    """What the bucket held of each state file when this machine last took
    them down or sent them: {"files": {key: sha256 or None}, "cleared": {...}},
    or None when this machine has no such record."""
    try:
        d = json.loads(local(root, STATE_RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("files"), dict) else None


def save_state_record(root, rec):
    p = local(root, STATE_RECORD)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec["at"] = datetime.now().isoformat(timespec="seconds")
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def state_up(bucket, root, kit, rep, day):
    """Send each state file this machine changed, and nothing it merely holds.

    ONE WRITER, AGAIN. Both machines hold these files, and a copy taken down
    last night is not news: sent back, it would put last night's census over
    tonight's. So a file goes up where the bucket holds none, or where it
    changed here since this machine took it down and did not change in the
    bucket. Where both changed, the bucket's stands and this machine's is
    kept under replaced/<day>/state-conflict/ -- a failure, except for a
    refusal on both sides, which is one fact however it arrived. A file
    cleared from the bucket by a person is never sent back, and one absent
    here is never removed there: a refusal is cleared by a person, not by a
    machine that happens not to hold it. Returns (sent, bytes, unchanged,
    notes, failures).
    """
    rec = load_state_record(root)
    base = dict((rec or {}).get("files", {}))
    cleared = dict((rec or {}).get("cleared", {}))
    n = size = same = 0
    notes, bad = [], []
    for s in state_present(root, kit):
        key, obj = s["key"], f"state/{s['key']}"
        try:
            data = local(root, s["path"]).read_bytes()
            mine = _sha(data)
            old = bucket.get_bytes(obj)
            theirs = _sha(old)
            if theirs == mine:
                same += 1
                base[key] = mine
                continue
            if cleared.get(key) == mine:
                notes.append(f"{s['path']} is the {key} a person cleared from the "
                             "bucket, and is not sent back")
                continue
            known = rec is not None and key in base
            was = base.get(key) if known else None
            if old is None:
                if known and was is not None and was == mine:
                    notes.append(f"{s['path']} was removed from the bucket after this "
                                 "machine took it down, and is not sent back")
                    continue
            elif not known:
                bad.append(f"{obj}: the bucket holds another copy and this machine "
                           "has no record of taking it down; run state-down first")
                continue
            elif mine == was:
                notes.append(f"{obj}: the bucket's is newer than this machine's copy, "
                             "which is left as it is")
                continue
            elif theirs != was:
                kept = f"replaced/{day}/state-conflict/{key}"
                bucket.put_bytes(kept, data)
                if key == "refused.json":
                    notes.append(f"a refusal is on file in the bucket and here; the "
                                 f"bucket's stands, this machine's is at {kept}")
                else:
                    bad.append(f"{obj} changed in the bucket and here since this "
                               f"machine took it down; the bucket's stands, this "
                               f"machine's is at {kept}")
                continue
            if old is not None:
                rep.keep(obj)
            bucket.put_bytes(obj, data)
            base[key] = mine
            n += 1
            size += len(data)
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"{obj}: {type(e).__name__}: {e}")
    save_state_record(root, {"files": base, "cleared": cleared})
    return n, size, same, notes, bad


def cmd_kit_up(a, root):
    kit = load_kit(root)
    rec_path = local(root, KIT_RECORD)
    if not rec_path.exists():
        raise Failed(f"no {KIT_RECORD}: kit-up sends what changed since kit-down, "
                     "and this machine has no record of a kit-down.")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    before = rec.get("files", {})
    day = rec.get("date") or f"{datetime.now():%Y-%m-%d}"
    files, _, _ = kit_files(root, kit)
    bucket = open_bucket(a)
    hashes = Hashes(root)
    # Unchanged since kit-down, by size and date, needs no reading.
    entries, maybe = {}, []
    for rel in sorted(files):
        st = local(root, rel).stat()
        b = before.get(rel)
        if b and b[0] == st.st_size and b[2] == st.st_mtime_ns:
            entries[rel] = {"size": b[0], "sha256": b[1], "mtime_ns": b[2]}
        else:
            maybe.append(rel)
    got, bad = hash_all(hashes, maybe, a.workers, "changed files")
    entries.update(got)
    if bad:
        raise Failed(f"{len(bad)} kit files would not read: {'; '.join(bad[:4])}")
    changed = [r for r, e in entries.items()
               if r not in before or before[r][1] != e["sha256"]]
    night = [r for r in changed if files[r] == "night"]
    theirs = [r for r in changed if files[r] == "laptop"]
    gone = [r for r in before if r not in files and not local(root, r).exists()
            and owner_of(kit, r) == "night"]
    man, _ = read_manifest(bucket, "kit")
    cur = (man or {}).get("files", {})
    # The bucket's copy must still be the one this machine took down -- or
    # already be this very file, from a kit-up of the same night that is
    # being run again. Anything else is another writer's.
    there = {r: (cur.get(r) or {}).get("sha256") for r in night}
    already = [r for r in night if there[r] == entries[r]["sha256"]]
    conflict = [r for r in night if r not in already
                and there[r] != (before[r][1] if r in before else None)]
    night = [r for r in night if r not in conflict and r not in already]
    since = max(rec.get("epoch") or 0, rec.get("logs_sent") or 0)
    logs = log_files(root, kit, since)
    here_state = state_present(root, kit)
    sz = sizes_of(entries)
    say(f"kit-up: {len(files):,} kit files here; {len(changed):,} changed or new "
        f"since kit-down at {rec.get('at', '?')}")
    show("the night's, to send", night, sz)
    show("the laptop's, changed here and not sent: the laptop owns them", theirs, sz)
    show("changed in the bucket since kit-down; its copy stands and this "
         "machine's goes to replaced/", conflict, sz)
    show("the night's, gone since kit-down", gone, {r: before[r][0] for r in gone})
    say(f"  logs for logs/{day}/: {len(logs):,} files, "
        f"{human(sum(local(root, r).stat().st_size for r in logs))}; state files "
        f"here: {len(here_state)}")
    if not removal_ok(len(gone), len(before), a.allow_removals):
        raise Failed(f"{len(gone):,} of the night's kit files are gone since kit-down, "
                     "more than a night removes. Nothing was sent. "
                     "--allow-removals if it is meant.")
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(night):,} files, "
            f"{human(sum(sz[r] for r in night))} would go to kit/; {len(gone):,} "
            f"would move to replaced/; {len(logs):,} logs; state compared and sent "
            "where it differs.")
        return
    rep = Replacer(bucket, day)
    remote = bucket.list("kit/")
    sent, fails = send(bucket, root, "kit", {r: entries[r] for r in night}, remote,
                       rep, a.workers)
    for r in conflict:
        try:
            bucket.put_file(local(root, r), f"replaced/{day}/kit-conflict/{r}",
                            {"sha256": entries[r]["sha256"],
                             "mtime_ns": str(entries[r]["mtime_ns"])})
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{r} (the conflicting copy): {type(e).__name__}: {e}")
    removed = []
    for r in gone:
        try:
            if f"kit/{r}" in remote:
                rep.keep(f"kit/{r}")
                bucket.delete(f"kit/{r}")
            removed.append(r)
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{r} (moving to replaced/): {type(e).__name__}: {e}")
    doc = write_manifest(bucket, "kit", sent, removed, "kit-up", rep)
    # What this machine now holds in common with the bucket: a second kit-up
    # the same night starts from here, not from what came down.
    for r, e in list(sent.items()) + [(r, entries[r]) for r in already]:
        before[r] = [e["size"], e["sha256"], e["mtime_ns"]]
    for r in removed:
        before.pop(r, None)
    rec["files"] = before
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    lsent, lfail = put_logs(bucket, root, logs, day)
    if not lfail:
        rec["logs_sent"] = time.time()
        rec_path.write_text(json.dumps(rec), encoding="utf-8")
    sn, sbytes, ssame, snotes, sfail = state_up(bucket, root, kit, rep, day)
    fails += lfail + sfail
    for note in snotes:
        say(f"  state: {note}")
    say(f"kit-up: sent {len(sent):,} files, "
        f"{human(sum(e['size'] for e in sent.values()))}; moved {len(removed):,} to "
        f"replaced/; {len(lsent):,} logs, "
        f"{human(sum(local(root, r).stat().st_size for r in lsent))}; {sn} state "
        f"files sent, {ssame} unchanged, {human(sbytes)}; {rep.n:,} older copies "
        f"kept under replaced/{day}/")
    say(f"  {MANIFEST.format('kit')}: {doc['count']:,} files, {human(doc['bytes'])}")
    if fails or conflict:
        raise Failed(
            (f"{len(fails)} did not send: {'; '.join(fails[:4])}. " if fails else "")
            + (f"{len(conflict)} kit file(s) changed in the bucket after this machine "
               f"took them down, which is two writers for one file: "
               f"{', '.join(conflict[:4])}. The bucket's copy stands; this machine's "
               f"is under replaced/{day}/kit-conflict/." if conflict else ""))


def cmd_state_up(a, root):
    kit = load_kit(root)
    here = state_present(root, kit)
    bucket = open_bucket(a)
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(here)} state files here would be "
            f"compared with state/ and sent where they differ: "
            + (", ".join(s["path"] for s in here) or "none"))
        return
    day = f"{datetime.now():%Y-%m-%d}"
    rep = Replacer(bucket, day)
    n, size, same, notes, bad = state_up(bucket, root, kit, rep, day)
    for note in notes:
        say(f"  {note}")
    say(f"state-up: {len(here)} state files here; sent {n}, {human(size)}; {same} "
        f"unchanged; {rep.n} older copies kept under replaced/")
    if bad:
        raise Failed(f"{len(bad)} state files did not send: {'; '.join(bad)}")


def cmd_state_down(a, root):
    """Each state file the bucket holds comes down, and what it held is
    recorded for state-up. One the bucket lacks is left alone here: an absence
    is not an instruction to delete. One changed here since the last
    state-down, and not yet sent, is left as well: taking the bucket's over it
    would lose what this machine wrote."""
    kit = load_kit(root)
    bucket = open_bucket(a)
    rec = load_state_record(root)
    base = dict((rec or {}).get("files", {}))
    n, size, same, absent, kept, bad = 0, 0, 0, [], [], []
    for s in kit.get("state", []):
        key = s["key"]
        try:
            data = bucket.get_bytes(f"state/{key}")
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"state/{key}: {type(e).__name__}: {e}")
            continue
        dst = local(root, s["path"])
        if data is None:
            absent.append(key)
            if not a.dry_run:
                base[key] = None
            continue
        here = dst.read_bytes() if dst.exists() else None
        if here == data:
            same += 1
            base[key] = _sha(data)
            continue
        if here is not None and rec is not None and _sha(here) != base.get(key):
            kept.append(s["path"])
            continue
        if a.dry_run:
            say(f"  would take state/{key} -> {s['path']}, {human(len(data))}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dst)
        base[key] = _sha(data)
        n += 1
        size += len(data)
    if not a.dry_run:
        save_state_record(root, {"files": base,
                                 "cleared": dict((rec or {}).get("cleared", {}))})
    say(f"state-down{' --dry-run, nothing taken' if a.dry_run else ''}: took {n} "
        f"state files, {human(size)}; {same} already here"
        + (f"; the bucket holds no {', '.join(absent)}" if absent else "")
        + (f"; left {', '.join(kept)} as this machine changed it, for state-up"
           if kept else ""))
    if bad:
        raise Failed(f"{len(bad)} state files could not be read: {'; '.join(bad)}")


def cmd_clear_refusal(a, root):
    """Lift the refusal record the nightly's machine keeps in the bucket.

    refusal.py --clear lifts this machine's archive/refused.json. The nightly
    starts empty and takes its refusal record from the bucket's
    state/refused.json, so after the move that copy is the one that stops a
    night, and it outlives any machine. This moves it to replaced/, never
    deletes it, and records that it was cleared, so no state-up sends the same
    refusal back. Clearing it is a person's decision, after netcheck.py.
    """
    kit = load_kit(root)
    entry = next((s for s in kit.get("state", []) if s["key"] == "refused.json"), None)
    if entry is None:
        raise Failed(f"{KIT_FILE} names no refused.json in its state list")
    bucket = open_bucket(a)
    obj = "state/refused.json"
    data = bucket.get_bytes(obj)
    if data is None:
        say("clear-refusal: the bucket holds no refusal (state/refused.json); "
            "nothing to clear there")
    elif a.dry_run:
        say(f"--dry-run: state/refused.json ({human(len(data))}) would move to "
            "replaced/; nothing moved")
        return
    else:
        day = f"{datetime.now():%Y-%m-%d}"
        moved = Replacer(bucket, day).keep(obj)
        bucket.delete(obj)
        say(f"clear-refusal: state/refused.json ({human(len(data))}) moved to "
            f"{moved}; nothing in the bucket stops a fetch now")
    rec = load_state_record(root) or {"files": {}}
    rec["files"]["refused.json"] = None
    if data is not None:
        rec.setdefault("cleared", {})["refused.json"] = _sha(data)
    save_state_record(root, rec)
    if local(root, entry["path"]).exists():
        say(f"  this machine still holds {entry['path']}: python3 refusal.py "
            "--clear lifts it here")


# THE NIGHT'S BUILT SITE, AS ONE FILE. The publish job runs on another
# machine and needs the night's site/. Handed over as a GitHub artifact it
# would be downloadable by anyone signed in to GitHub, the repository being
# public, and it carries the licensed logo. Sent as 55,000 objects it would be
# 55,000 billed writes a night. So it goes to the private bucket as one
# archive, nights/<run>/site.tar.gz, with nights/<run>/site.json beside it
# saying what it holds; the bucket's lifecycle rule deletes nights/ after a
# few days.
RUN_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _night_keys(run):
    if not run or not RUN_ID.match(run):
        raise Failed(f"--run {run!r} is not a run id (letters, digits, . _ -)")
    return f"nights/{run}/site.tar.gz", f"nights/{run}/site.json"


def _site_dir(root, name):
    try:
        return local(root, check_rel(name))
    except Failed:
        raise Failed(f"--site {name!r} is not a plain relative folder")


def _site_files(site):
    out = []
    for dirpath, _, names in os.walk(site):
        for nm in names:
            p = Path(dirpath) / nm
            out.append((p.relative_to(site).as_posix(), p))
    return sorted(out)


def cmd_site_up(a, root):
    import tarfile
    key, meta_key = _night_keys(a.run)
    site = _site_dir(root, a.site)
    files = _site_files(site) if site.is_dir() else []
    if not files:
        raise Failed(f"no built site in {a.site}/ to send")
    total = sum(p.stat().st_size for _, p in files)
    say(f"site-up: {a.site}/ holds {len(files):,} files, {human(total)}")
    if a.dry_run:
        say(f"--dry-run: nothing sent. They would go as one archive to {key}.")
        return
    bucket = open_bucket(a)
    tmp = local(root, f"{LOCAL}/site-{a.run}.tar.gz")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(tmp, "w:gz", compresslevel=6) as tf:
            for rel, p in files:
                tf.add(p, arcname=rel, recursive=False)
        size, sha = tmp.stat().st_size, sha256_of(tmp)
        remote = bucket.list(f"nights/{a.run}/")
        rep = Replacer(bucket, f"{datetime.now():%Y-%m-%d}")
        for k in (key, meta_key):
            if k in remote:
                rep.keep(k)
        bucket.put_file(tmp, key, {"sha256": sha, "files": str(len(files))})
        got = bucket.list(f"nights/{a.run}/").get(key)
        if got != size:
            raise Failed(f"{key} arrived as {got} bytes, not {size:,}")
        bucket.put_bytes(meta_key, json.dumps({
            "run": a.run, "files": len(files), "bytes": total, "size": size,
            "sha256": sha, "written": datetime.now().isoformat(timespec="seconds"),
        }, indent=1).encode("utf-8"))
    finally:
        tmp.unlink(missing_ok=True)
    say(f"site-up: {len(files):,} files, {human(total)}, sent as one archive of "
        f"{human(size)} to {key}")


def cmd_site_down(a, root):
    import tarfile
    key, meta_key = _night_keys(a.run)
    bucket = open_bucket(a)
    raw = bucket.get_bytes(meta_key)
    if raw is None:
        raise Failed(f"{bucket.describe()} has no {meta_key}: no site was sent for "
                     f"run {a.run}, or the lifecycle rule has deleted it")
    meta = json.loads(raw.decode("utf-8"))
    site = _site_dir(root, a.site)
    if site.exists() and any(site.iterdir()):
        raise Failed(f"{a.site}/ is not empty here; site-down unpacks the night's "
                     "site into an empty folder, and nothing already here is "
                     "overwritten")
    say(f"site-down: run {a.run}'s site, {meta['files']:,} files, "
        f"{human(meta['bytes'])} in an archive of {human(meta['size'])}")
    if a.dry_run:
        say("--dry-run: nothing fetched.")
        return
    tmp = local(root, f"{LOCAL}/site-{a.run}.tar.gz")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        bucket.get_file(key, tmp)
        size, sha = tmp.stat().st_size, sha256_of(tmp)
        if size != meta["size"] or sha != meta["sha256"]:
            raise Failed(f"{key} arrived as {size:,} bytes, sha256 {sha[:12]}; "
                         f"{meta_key} says {meta['size']:,}, {meta['sha256'][:12]}")
        site.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp, "r:gz") as tf:
            tf.extractall(site, filter="data")
    finally:
        tmp.unlink(missing_ok=True)
    files = _site_files(site)
    total = sum(p.stat().st_size for _, p in files)
    if len(files) != meta["files"] or total != meta["bytes"]:
        raise Failed(f"the site unpacked as {len(files):,} files, {human(total)}; "
                     f"{meta_key} says {meta['files']:,}, {human(meta['bytes'])}")
    say(f"site-down: {len(files):,} files, {human(total)} unpacked into {a.site}/, "
        "every one accounted for")


def tracked_files(root):
    try:
        r = child.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True)
    except OSError as e:
        raise Failed(f"git will not run ({e}), so what git holds cannot be told "
                     "from what it does not")
    if r.returncode != 0:
        raise Failed(f"{root} is not a git checkout, so what git holds cannot be "
                     "told from what it does not")
    return {p for p in (r.stdout or "").split("\0") if p}


def backup_files(root, kit, with_site):
    """Everything here git does not track, less what the backup leaves out and
    what is never sent, as sorted /-paths."""
    tracked = tracked_files(root)
    leave = [g for grp in (kit.get("backup") or {}).get("leave_out", [])
             for g in grp["globs"] if not (with_site and g.startswith("site/"))]
    rxs = [glob_re(g) for g in leave + (kit.get("never") or {}).get("globs", [])]
    prune = [glob_re(g[:-3]) for g in leave if g.endswith("/**")]
    out, stack = [], [(Path(root), "")]
    while stack:
        d, rel = stack.pop()
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            r = f"{rel}/{e.name}" if rel else e.name
            if e.is_dir(follow_symlinks=False):
                if not any(rx.match(r) for rx in prune):
                    stack.append((Path(e.path), r))
            elif e.is_file(follow_symlinks=False) and r not in tracked \
                    and not any(rx.match(r) for rx in rxs):
                out.append(r)
    return sorted(out)


def cmd_backup(a, root):
    kit = load_kit(root)
    quiet_disk(root)
    rels = backup_files(root, kit, a.with_site)
    bucket = open_bucket(a, preview=True)
    hashes = Hashes(root)
    say(f"backup: {len(rels):,} files here that git does not hold"
        + ("" if a.with_site else ", site/ left out") + "; reading them")
    entries, unread = hash_all(hashes, rels, a.workers, "files")
    hashes.save()
    man, _ = read_manifest(bucket, "backup")
    known = (man or {}).get("files", {})
    remote = bucket.list("backup/")
    have = resumed(bucket, "backup", entries, known, remote)
    todo, same = diff(entries, known, have, "backup", remote)
    # Gone from here since the last backup: moved to replaced/, never deleted,
    # and only below the share a real tidy-up reaches. site/ is not "gone"
    # when --with-site was simply not given, and a file that would not read
    # is not gone either.
    unread_rels = {u.split(": ", 1)[0] for u in unread}
    gone = [r for r in known if r not in entries and r not in unread_rels
            and not local(root, r).exists()
            and (a.with_site or not r.startswith("site/"))]
    total = sum(e["size"] for e in entries.values())
    say(f"  {'first backup to' if man is None else 'changes since the last backup to'} "
        f"{bucket.describe()}: {len(entries):,} files, {human(total)} here")
    sz = sizes_of(entries)
    show("to send", list(todo), sz)
    show("unchanged, not sent", same, sz, limit=0)
    show("gone from here since the last backup, to be moved to replaced/", gone,
         {r: known[r]["size"] for r in gone})
    if unread:
        say(f"  {len(unread):,} files would not read and are not sent: "
            + "; ".join(unread[:3]))
    if not removal_ok(len(gone), len(known), a.allow_removals):
        raise Failed(f"{len(gone):,} files the backup holds are gone from here, which "
                     "looks like the wrong folder or a missing disk rather than a "
                     "tidy-up. Nothing was sent or moved. --allow-removals if it is "
                     "meant.")
    if a.dry_run:
        say(f"--dry-run: nothing sent. {len(todo):,} files, "
            f"{human(sum(e['size'] for e in todo.values()))} would go to backup/ in "
            f"{bucket.describe()}; {len(gone):,} would move to replaced/.")
        return
    day = f"{datetime.now():%Y-%m-%d}"
    rep = Replacer(bucket, day)
    ck = Checkpoint(bucket, "backup", "backup", rep, base=have)
    sent, fails = send(bucket, root, "backup", todo, remote, rep, a.workers, record=ck)
    removed = []
    for r in gone:
        try:
            if f"backup/{r}" in remote:
                rep.keep(f"backup/{r}")
                bucket.delete(f"backup/{r}")
            removed.append(r)
        except Exception as e:                                  # noqa: BLE001
            fails.append(f"{r} (moving to replaced/): {type(e).__name__}: {e}")
    doc = write_manifest(bucket, "backup", {**have, **sent}, removed, "backup", rep,
                         keep_old=ck.first)
    say(f"backup: sent {len(sent):,} files, "
        f"{human(sum(e['size'] for e in sent.values()))}; {len(same):,} unchanged; "
        f"{len(removed):,} moved to replaced/; {rep.n:,} older copies kept under "
        f"replaced/{day}/")
    say(f"  {MANIFEST.format('backup')}: {doc['count']:,} files, {human(doc['bytes'])}")
    fails = unread + fails
    if fails:
        raise Failed(f"{len(fails)} files did not go, so the backup is short: "
                     f"{'; '.join(fails[:4])}. Run backup again: what did send is "
                     "recorded and will not go twice.")


COMMANDS = {"kit-list": cmd_kit_list, "seed-kit": cmd_seed_kit,
            "kit-down": cmd_kit_down, "kit-up": cmd_kit_up,
            "state-down": cmd_state_down, "state-up": cmd_state_up,
            "clear-refusal": cmd_clear_refusal,
            "site-up": cmd_site_up, "site-down": cmd_site_down,
            "backup": cmd_backup}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="The nightly's kit and the laptop's backup, in R2.")
    ap.add_argument("command", choices=sorted(COMMANDS))
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would be sent, and send nothing")
    ap.add_argument("--sizes", action="store_true", help="kit-list: with sizes")
    ap.add_argument("--with-site", action="store_true",
                    help="backup: include the built site/, which it leaves out")
    ap.add_argument("--allow-removals", action="store_true",
                    help="move more files to replaced/ than a normal run would")
    ap.add_argument("--local-bucket", metavar="FOLDER",
                    help="use a folder as the bucket (testing; no credentials)")
    ap.add_argument("--root", default=".", help="the working folder")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--run", help="site-up, site-down: the night's run id "
                                  "(GitHub's run id), which names nights/<run>/")
    ap.add_argument("--site", default="site",
                    help="site-up, site-down: the built site's folder")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    t0 = time.time()
    try:
        if a.command == "kit-list":
            cmd_kit_list(a, root)
        else:
            with machine_lock(root):
                COMMANDS[a.command](a, root)
    except Failed as e:
        print(scrub(f"\ncloud.py {a.command} FAILED: {e}"), file=sys.stderr, flush=True)
        return 1
    except KeyboardInterrupt:
        print(f"\ncloud.py {a.command} FAILED: interrupted; what had been sent is "
              "recorded up to the last checkpoint", file=sys.stderr, flush=True)
        return 1
    except Exception as e:                                      # noqa: BLE001
        print(scrub(f"\ncloud.py {a.command} FAILED: {type(e).__name__}: {e}"),
              file=sys.stderr, flush=True)
        return 1
    if a.command != "kit-list":
        say(f"({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
