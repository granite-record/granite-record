#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.4
"""
preflight's checks of the bucket and the refusals (cloud.py, refusal.py).

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import ast
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _paths

from pf_core import (_SWITCHED, _in_suite, _parsed, _run, _source, check)
from pf_shared import (NIGHTLY_STALE_HOURS, _ASKS_GC_FLOOR, _RUNNERS, _RUNNER_FLOORS,
                       _cloud_call, _inbox_files, _inbox_words, _installed_none,
                       _nightly_log_findings, _nightly_log_selftest, _nightly_night,
                       _runner_names, _wf_code, _wf_jobs, _wf_steps, _workflows, ic_SOURCES)


@check("cloud", "the captions inbox in the bucket: inbox-down writes nothing there, and "
       "inbox-clear removes only what the night's sent state no longer waits for, keeps a copy, "
       "and clears nothing on a dry night", needs=("cloud", "livestreams"))
def _inbox_bucket(CL, livestreams):
    """inbox-down brings every entry down, whatever its bytes, against a
    bucket that refuses every write; the corrupt one is named, and the night
    refuses it; its --dry-run writes nothing on this machine either, not
    even the lock's folder. inbox-clear clears nothing on a dry night -- by its flag, by
    the workflow's DRY_RUN, or as any run off main -- nor under --dry-run,
    nor with no state in the bucket. On a real night it removes the entries
    the bucket's state no longer waits for (read, refused, dropped), each
    copied to replaced/ first, and keeps what still waits, what was taken
    and not yet read, and a loose file a laptop has not finished sending.
    And the laptop's run records (18 October 2026): inbox-down brings the
    newest to where the verdict reads it, and takes away an earlier copy
    when the newest will not read; inbox-clear clears all but the newest,
    to replaced/ first, and none on a dry night."""
    import hashlib
    L = livestreams
    tmp = Path(tempfile.mkdtemp(prefix="gr-inbox-bucket-"))
    names = ("GITHUB_ACTIONS", CL.DRY_ENV, CL.REF_ENV, CL.NO_BUCKET)
    saved = {k: os.environ.get(k) for k in names}
    real_open = CL.open_bucket
    bucket, night = tmp / "bucket", tmp / "night"
    try:
        for k in names:
            os.environ.pop(k, None)
        os.environ[CL.NO_BUCKET] = "1"
        night.mkdir()
        b = CL.FolderBucket(bucket)
        src = tmp / "captions.en.json3"
        src.write_text(_inbox_words(), encoding="utf-8")
        vids = ("PFWAIT01", "PFTOOK01", "PFREAD01", "PFREFU01", "PFGONE01", "PFBAD01")
        for vid in vids:
            assert CL.inbox_add(b, vid, src, {"fetched": "2026-10-17T23:30:00Z"})
        bad = json.loads(b.get_bytes(f"{CL.INBOX}PFBAD01.json"))["key"]
        b.put_bytes(bad, b"not the file sent")
        b.put_bytes(f"{CL.INBOX}PFLOOSE1/{'0' * 64}/captions.en.json3", src.read_bytes())
        fin = {"status": "finished", "captions": "deferred"}
        state = {"videos": {
            "PFWAIT01": fin, "PFBAD01": fin, "PFLOOSE1": fin,
            "PFTOOK01": dict(fin, captions="captioned", by="inbox"),
            "PFREAD01": dict(fin, captions="captioned", by="inbox", read="2026-10-18"),
            "PFREFU01": dict(fin, inbox_refused={"entry": hashlib.sha256(
                b.get_bytes(f"{CL.INBOX}PFREFU01.json")).hexdigest(), "why": "x"})}}
        b.put_bytes(CL.INBOX_STATE, json.dumps(state).encode("utf-8"))
        # Two evenings' records of the laptop's runs (THE LAPTOP'S RUN RECORDS).
        runs = {f"{CL.INBOX_RUNS}2026101{d}T233000Z.json": f"2026-10-1{d}T23:30:00Z" for d in (6, 7)}
        for key, at in runs.items():
            b.put_bytes(key, json.dumps({"at": at, "sent": 1}).encode("utf-8"))
        older, newest = sorted(runs)
        before = _inbox_files(bucket)

        class ReadOnly(CL.FolderBucket):
            def _no(self, key):
                raise AssertionError(f"inbox-down tried to write {key} in the bucket")

            def put_file(self, src, key, meta):
                self._no(key)

            def put_bytes(self, key, data):
                self._no(key)

            def copy(self, src, dst):
                self._no(dst)

            def delete(self, key):
                self._no(key)

        CL.open_bucket = lambda a, preview=False: ReadOnly(a.local_bucket, create=False)
        # A dry run says what would come down and writes nothing, here or there.
        code, said = _cloud_call(CL, "inbox-down", "--dry-run", "--root", str(night),
                                 "--local-bucket", str(bucket))
        assert code == 0 and "would come down" in said and not (night / "archive").exists(), \
            f"inbox-down --dry-run wrote under {night / 'archive'}: {said}"
        code, said = _cloud_call(CL, "inbox-down", "--root", str(night),
                                 "--local-bucket", str(bucket))
        CL.open_bucket = real_open
        down = night / CL.INBOX_LOCAL
        assert code == 0 and sorted(p.stem for p in down.glob("*.json")) == sorted(vids), said
        assert (down / "PFBAD01" / "captions.en.json3").read_bytes() == b"not the file sent" \
            and "PFBAD01" in said and not (down / "PFLOOSE1").exists(), said
        assert L.inbox_problem("PFBAD01", (down / "PFBAD01.json").read_bytes(), down)
        assert not L.inbox_problem("PFWAIT01", (down / "PFWAIT01.json").read_bytes(), down)
        assert _inbox_files(bucket) == before
        # ... and the newest of the laptop's run records, where the verdict
        # reads it, beside the inbox and not in it.
        ran = night / CL.INBOX_RUN_LOCAL
        assert ran.is_file() and json.loads(ran.read_text(encoding="utf-8"))["at"] == runs[newest] \
            and "20261017T233000Z" in said and not (down / "laptop").exists(), said

        for argv, env in ((["--dry-night"], {}), (["--dry-run"], {}),
                          ([], {"GITHUB_ACTIONS": "true", CL.DRY_ENV: "true",
                                CL.REF_ENV: CL.MAIN_REF}),
                          ([], {"GITHUB_ACTIONS": "true", CL.DRY_ENV: "false",
                                CL.REF_ENV: "refs/heads/dev"})):
            os.environ.update(env)
            code, said = _cloud_call(CL, "inbox-clear", *argv, "--root", str(night),
                                     "--local-bucket", str(bucket))
            for k in env:
                os.environ.pop(k, None)
            assert code == 0 and _inbox_files(bucket) == before, \
                f"inbox-clear {argv} {env} cleared something: {said}"

        code, said = _cloud_call(CL, "inbox-clear", "--root", str(night),
                                 "--local-bucket", str(bucket))
        after = _inbox_files(bucket)
        left = CL.inbox_listing(CL.FolderBucket(bucket, create=False))
        assert code == 0 and sorted(left) == ["PFBAD01", "PFLOOSE1", "PFTOOK01", "PFWAIT01"], \
            (sorted(left), said)
        gone = [k for k in before if k.startswith(CL.INBOX) and k not in after]
        assert gone and all(k.split("/")[2].split(".")[0] in ("PFREAD01", "PFREFU01", "PFGONE01")
                            for k in gone), gone
        from datetime import datetime
        day = f"{datetime.now():%Y-%m-%d}"
        assert all(after.get(f"replaced/{day}/{k}") == before[k] for k in gone), \
            "inbox-clear removed an entry without keeping a copy under replaced/"
        assert all(after.get(k) == v for k, v in before.items()
                   if not k.startswith((CL.INBOX, CL.INBOX_RUNS, ".meta/"))), \
            "inbox-clear touched the rest"
        # The laptop's run records but the newest go, to replaced/ first.
        assert older not in after and after.get(f"replaced/{day}/{older}") == before[older] \
            and after.get(newest) == before[newest], \
            ("inbox-clear did not clear the older run record to replaced/ and keep the newest",
             sorted(k for k in after if CL.INBOX_RUNS in k))

        b.delete(CL.INBOX_STATE)
        snap = _inbox_files(bucket)
        code, said = _cloud_call(CL, "inbox-clear", "--root", str(night),
                                 "--local-bucket", str(bucket))
        assert code == 0 and _inbox_files(bucket) == snap, said
        # A newest run record that will not read is not brought, and the copy
        # an earlier inbox-down left is taken away: no record, not an old one.
        b.put_bytes(f"{CL.INBOX_RUNS}20261018T233000Z.json", b"not a record")
        code, said = _cloud_call(CL, "inbox-down", "--root", str(night),
                                 "--local-bucket", str(bucket))
        assert code == 0 and not ran.exists() and "will not read" in said, said
        return "ok", ("inbox-down writes nothing in the bucket and names the corrupt entry, which "
                      "the night refuses, and brings the laptop's newest run record, or none where "
                      "it will not read; a dry night, a run off main, --dry-run and a bucket with "
                      "no state clear nothing; a real night clears the read, refused and dropped "
                      "entries and the older run records, to replaced/ first, and keeps the rest")
    finally:
        CL.open_bucket = real_open
        for k, v in saved.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        shutil.rmtree(tmp, ignore_errors=True)


@check("cloud", "the kit names what the build reads, and nothing private or a reader's",
       needs=("cloud", "build_all"))
def _cloud_kit(CL, BA):
    """cloud_kit.json is the list of what the nightly's empty machine is given.
    It drifts the way every list here has: a step that starts reading a new
    file builds a different site there and passes all its own checks. And it
    is the one list whose mistakes leave the laptop -- a key, the Clerks'
    list, a reader's words -- so what it must never hold is checked too.

      - every output a build reads before rewriting it (build_all.CARRIED),
        and every input a --local step declares from outside the repository
        (ic_SOURCES), is in the kit; so are the caption summary, the logo
        the build lays over the clipart, and since 1 October the clipart
        itself, file by file (build_pages.BRAND_FILES), because it is no
        longer in the repository
      - nothing in the kit or the state is tracked by git, and every literal
        path in either is gitignored, so kit-down never writes over the
        checkout and no generated file is one `git add` from being published
      - neither holds a credential, reports/, CLERK_CORRECTIONS.md, captions,
        audio, anything of brand/ (no build reads the originals, the artist's
        or the clipart's) or the built site -- bar the one file of it a build
        reads before it rewrites it, which it does carry
      - small state lives under archive/ on a machine, state/ in the bucket
      - "never" names the credentials and the reader reports; the backup
        leaves out logs/ and never the Clerks' list, brand/ and assets/ (the
        only other copy of the logo, now that git holds none) or the
        What-changed reports
      - one file, one owner
    """
    kit = CL.load_kit(".")
    entries = kit["kit"]

    def in_kit(rel):
        return any(CL.entry_matches(e, rel) for e in entries)

    state_paths = {s["path"] for s in kit.get("state", [])}

    def names(rel):
        # A literal path, a directory the kit reaches into, or a state file.
        return in_kit(rel) or rel in state_paths or any(
            g.startswith(rel.rstrip("/") + "/")
            for e in entries for g in e.get("globs", []))
    bad = [p for p, _, _ in BA.CARRIED if not in_kit(p)]
    assert not bad, f"build_all.CARRIED names outputs the kit does not carry: {bad}"
    # From outside the repository: not the site, and not what a build step
    # writes without declaring it.
    ext = [k for k, v in ic_SOURCES.items()
           if not k.startswith("site/") and "does not declare it" not in v]
    bad = [k for k in ext if not names(k)]
    assert not bad, ("a --local step needs these from outside the repository and "
                     f"neither the kit nor the state brings them: {bad}")
    # SMALL STATE LIVES UNDER archive/ on a machine, and under state/ only in
    # the bucket: one convention, so a file is never looked for in two places.
    stray = sorted(p for p in state_paths if not p.startswith(("archive/", "reports/.cursor-")))
    assert not stray, f"state kept outside archive/ on the machine: {stray}"
    # The one file of last night's site a build reads before rewriting it --
    # a build from the kit alone showed it on 25 September -- and nothing else
    # of site/, which is rebuilt every night.
    LAST_SITE = {"site/committees.json"}
    import build_pages as BP
    clipart = [f"assets/{f}" for f in BP.BRAND_FILES if f != "site.webmanifest"]
    for must in ("caption_spans.json", "candidate_segments.json",
                 "assets/licensed/lockup.png", f"assets/licensed/{BP.HEADER_MARK}",
                 *clipart, *sorted(LAST_SITE)):
        assert in_kit(must), f"the kit does not carry {must}"

    samples = [p for e in entries for p in e.get("paths", [])]
    samples += [re.sub(r"\*+", "x", g).replace("?", "x") for e in entries
                for g in e.get("globs", [])]
    states = [s["path"] for s in kit.get("state", [])]
    forbidden = ["reports/", "CLERK_CORRECTIONS.md", "secrets.json", ".env",
                 ".dev.vars", "site/", "logs/", "brand/", ".git/",
                 ".claude/"]
    allowed = LAST_SITE | {"reports/.cursor-production"}
    for p in samples + states:
        for f in forbidden:
            if (p == f or p.startswith(f)) and p not in allowed:
                raise AssertionError(f"{p} is in the kit or the state, and "
                                     f"{f} must never be")
        assert not re.search(r"(?:captions|transcript)[^/]*\.json3?$|\.wav$|\.pem$|\.key$|\.pdf$",
                             p, re.I), f"{p} is in the kit: captions, audio, keys and PDFs are not"
    never = [CL.glob_re(g) for g in kit["never"]["globs"]]
    for want in ("secrets.json", ".dev.vars", ".env", "x/y.pem",
                 "reports/issues-production-2026-09-25.jsonl",
                 "reports/triage-production-2026-09-25.md"):
        assert any(rx.match(want) for rx in never), f"'never' does not hold back {want}"
    leave = [CL.glob_re(g) for grp in kit["backup"]["leave_out"] for g in grp["globs"]]
    for keep in ("CLERK_CORRECTIONS.md", "brand/licensed/drawing.png",
                 "assets/licensed/og.png", "brand/icon.png", "assets/favicon.ico",
                 "reports/gc-changes-2026-09-25.md",
                 "reports/.cursor-production", "work/VID/captions.en.json3",
                 "legislation/2026/HB1.html"):
        assert not any(rx.match(keep) for rx in leave + never), (
            f"the backup leaves out {keep}, which it is for")
    for out in ("logs/nightly-2026-09-25.log", "site/index.json", ".git/HEAD",
                "archive/cloud/hashes.json", "__pycache__/x.pyc"):
        assert any(rx.match(out) for rx in leave), f"the backup sends {out}"

    owners = {}
    for e in entries:
        for p in e.get("paths", []):
            assert owners.setdefault(p, e["owner"]) == e["owner"], f"{p} has two owners"
    said = (f"{len(entries)} entries: every carried output and outside input is in "
            f"it, {len(states)} state files, nothing private or a reader's; the "
            "backup keeps the Clerks' list and not the logs")
    try:
        listed = _run(["git", "ls-files"], capture_output=True, text=True, timeout=60)
        # NUL-separated: a text pipe on Windows turns \n into \r\n, and git
        # reads the \r as part of the name.
        ignored = _run(["git", "check-ignore", "--no-index", "--stdin", "-z"],
                       input="\0".join(samples + states) + "\0",
                       capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return "ok", said + f"; git would not answer ({e}), so what it tracks was not asked"
    if listed.returncode != 0 or ignored.returncode not in (0, 1):
        return "ok", said + "; not a git checkout, so what git tracks was not asked"
    both = sorted(set(samples + states) & set(listed.stdout.split("\n")))
    assert not both, f"the kit or the state names files git tracks: {both}"
    unignored = sorted(set(samples + states) - set(ignored.stdout.split("\0")))
    assert not unignored, ("the kit or the state names files .gitignore does not "
                           f"keep out, one `git add .` from the repository: {unignored}")
    return "ok", said + "; none of it tracked, and all of it gitignored"


def _cloud_fixture(root, kit_src):
    """A working folder for cloud.py: a small kit, with the real 'never' and
    'backup' rules, and a file of each kind they sort."""
    kit = {"kit": [
        {"what": "day", "owner": "night", "paths": ["Docket.txt"]},
        {"what": "outputs", "owner": "night", "paths": ["narratives.json"],
         "globs": ["nh-archive/**"]},
        {"what": "pages", "owner": "laptop", "globs": ["legislation/**"]}],
        "state": [{"path": "archive/census.json", "key": "census.json", "what": "x"},
                  {"path": "archive/refused.json", "key": "refused.json", "what": "x"}],
        "logs": {"globs": ["logs/*"]},
        "backup": kit_src["backup"], "never": kit_src["never"]}
    files = {"Docket.txt": "docket 1\n", "narratives.json": "{}",
             "nh-archive/snapshots/2026-09-24/a.gz": "a",
             "legislation/2026/HB1.html": "<p>one</p>",
             "legislation/2026/HB2.html": "<p>two</p>",
             "archive/census.json": '{"census": {}}',
             "secrets.json": '{"R2_SECRET_ACCESS_KEY": "not a real one"}',
             "reports/issues-production-2026-09-25.jsonl": "a reader's words\n",
             "reports/triage-production-2026-09-25.md": "a reader's words\n",
             "reports/gc-changes-2026-09-25.md": "what changed\n",
             "CLERK_CORRECTIONS.md": "the list\n",
             "brand/licensed/drawing.png": "png",
             "logs/nightly-2026-09-25.log": "log\n",
             "site/index.json": "[]", "tracked.py": "x = 1\n"}
    for rel, body in files.items():
        p = root.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    (root / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")


def _bucket_keys(bucket):
    return {p.relative_to(bucket).as_posix() for p in bucket.rglob("*")
            if p.is_file() and ".meta" not in p.relative_to(bucket).parts}


@check("cloud", "the state documents travel apart from the kit: nothing the night takes "
       "can match sources/, the registry reads, and up and down lose nothing",
       needs=("cloud", "state_sources"))
def _state_sources_apart(CL, SS):
    """The state documents the guides rest on are read in a browser on the
    laptop and carried to the sessions under the bucket's sources/ prefix
    (state_sources.py, 30 October 2026). They are evidence for people, not
    inputs to the build: a night that took them would build from whatever a
    browser saved last, unchecked. So no entry of cloud_kit.json's kit, state
    or dry_run lists can match a path under sources/, neither the nightly nor
    its workflows names the module, the registry reads (a General Court
    address in it is the owner's alone), and a round trip through a folder
    bucket sends each version once, records a reading that did not change as
    a check, never replaces a reading, and brings every version down whole.
    """
    import contextlib
    import hashlib
    import io
    kit = json.loads(_source("cloud_kit.json"))
    samples = ["sources/manifest.json", "sources/reports/20261030T000000000000.json"]
    samples += [f"sources/sos-register-vote/2026-10-30{n}.{x}"
                for x in sorted(SS.EXTS) for n in ("", "-2")]
    samples += ["sources/printouts/council-contact-us.pdf",
                "records/sources/printouts/council-contact-us.pdf"]
    pats = [p for e in kit.get("kit", []) for p in e.get("paths", []) + e.get("globs", [])]
    pats += [s["path"] for s in kit.get("state", [])]
    d = kit.get("dry_run") or {}
    pats += list(d.get("globs", [])) + ([d["store"]] if d.get("store") else [])
    hits = sorted({p for p in pats for s in samples
                   if CL.glob_re(p).match(s) or s == p or p.startswith("sources/")})
    assert not hits, (f"cloud_kit.json names what can match the state documents' folder, "
                      f"which the night must never take: {hits}")
    for f in [_paths.locate("nightly.py"), *sorted(Path(".github/workflows").glob("*.yml"))]:
        if f.exists():
            src = f.read_text(encoding="utf-8", errors="replace")
            assert "state_sources" not in src and "sources-down" not in src, (
                f"{f.name} names the state documents' hand-over, which the night never runs")
    reg = SS.load_registry(_paths.ROOT)
    gc = [i for i, r in reg.items() if SS.is_gc(r["url"])]
    assert all(reg[i]["read_by"] == "owner-only" for i in gc), gc
    t = Path(tempfile.mkdtemp(prefix="granite-sources-"))
    try:
        root, bucket = t / "root", t / "bucket"
        (root / "records" / "sources").mkdir(parents=True)
        shutil.copy(_paths.ROOT / SS.REGISTRY, root / SS.REGISTRY)
        one = next(i for i, r in reg.items() if r["read_by"] == "browser")
        folder = root / SS.FOLDER / one
        folder.mkdir(parents=True)

        def run(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                code = SS.main([*argv, "--root", str(root), "--local-bucket", str(bucket)])
            return code, out.getvalue()

        (folder / "2026-10-01.pdf").write_bytes(b"first")
        assert run("up")[0] == 0
        (folder / "2026-10-02.pdf").write_bytes(b"first")
        (folder / "2026-10-03.pdf").write_bytes(b"second")
        code, out = run("up")
        heads = [ln for ln in out.splitlines() if ln.isupper() or ln.endswith(":")]
        assert code == 0 and "CHANGED since the last reading:" in heads \
            and "READ AGAIN, UNCHANGED:" in heads, out
        keys = _bucket_keys(bucket)
        assert f"sources/{one}/2026-10-02.pdf" not in keys, "an unchanged reading was sent again"
        assert {f"sources/{one}/2026-10-01.pdf", f"sources/{one}/2026-10-03.pdf",
                "sources/manifest.json"} <= keys, keys
        assert any(k.startswith("replaced/") and k.endswith("sources/manifest.json")
                   for k in keys), "the manifest was replaced without its old copy kept"
        n = len(keys)
        code, out = run("up")
        assert code == 0 and len(_bucket_keys(bucket)) == n, ("a run with nothing new "
                                                             "wrote to the bucket")
        (folder / "2026-10-01.pdf").write_bytes(b"edited")
        code, out = run("up")
        assert code == 1 and "never replaced" in out, out
        assert (bucket / f"sources/{one}/2026-10-01.pdf").read_bytes() == b"first"
        (folder / "2026-10-01.pdf").write_bytes(b"first")
        # Two readings in one day: the second, -2, is the newer, whatever a
        # sort of the names says.
        (folder / "2026-10-04.pdf").write_bytes(b"third")
        (folder / "2026-10-04-2.pdf").write_bytes(b"fourth")
        assert run("up")[0] == 0
        man = json.loads((bucket / "sources" / "manifest.json").read_text(encoding="utf-8"))
        assert man["ids"][one]["versions"][-1]["file"] == f"{one}/2026-10-04-2.pdf", (
            "the second reading of a day is not the latest version", man["ids"][one])
        down = t / "down"
        code, out = run("down", "--into", str(down))
        assert code == 0, out
        got = sorted(p.relative_to(down).as_posix() for p in down.rglob("*") if p.is_file())
        assert got == [f"{one}/2026-10-01.pdf", f"{one}/2026-10-03.pdf",
                       f"{one}/2026-10-04-2.pdf", f"{one}/2026-10-04.pdf"], got
        (down / one / "2026-10-01.pdf").write_bytes(b"mine")
        code, out = run("down", "--into", str(down))
        assert code == 1 and (down / one / "2026-10-01.pdf").read_bytes() == b"mine", (
            "down wrote over a reading that differs from the bucket's", out)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = SS.main(["down", "--root", str(root), "--local-bucket", str(t / "empty"),
                            "--into", str(t / "down2")])
        assert code == 1, "down from a bucket with no record said it succeeded"
        (root / SS.FOLDER / "not-an-id").mkdir()
        (root / SS.FOLDER / "not-an-id" / "2026-10-01.pdf").write_bytes(b"x")
        code, out = run("up")
        assert code == 1 and "not an id" in out, out
        (root / SS.FOLDER / "not-an-id" / "2026-10-01.pdf").unlink()
        (root / SS.FOLDER / "not-an-id").rmdir()
        # The owner's printouts travel beside the readings, under the names and
        # sha256 their index gives, and come back where file_printouts.py files them.
        home = root / SS.PRINTOUTS
        home.mkdir(parents=True)
        body = b"a printout"
        (home / "council-contact-us.pdf").write_bytes(body)
        (home / "INDEX.csv").write_text(
            "new_name,title,publisher,url,url_from,printed,pages,cited_by,owner_name,sha256\n"
            f"council-contact-us.pdf,Contact Us,NH Executive Council,,,,2,,c.pdf,"
            f"{hashlib.sha256(body).hexdigest()}\n", encoding="utf-8")
        code, out = run("up")
        assert code == 0 and "Printouts: sent 1" in out, out
        assert (bucket / "sources" / "printouts" / "council-contact-us.pdf").read_bytes() == body
        (home / "council-contact-us.pdf").write_bytes(b"edited")
        code, out = run("up")
        assert code == 1 and "differ from the sha256" in out, ("an edited printout was "
                                                               "sent, or went unremarked", out)
        (home / "council-contact-us.pdf").unlink()
        code, out = run("down", "--into", str(t / "down3"))
        assert code == 0 and (t / "down3" / "printouts" / "council-contact-us.pdf"
                              ).read_bytes() == body, out
        assert not (home / "council-contact-us.pdf").exists(), (
            "down --into wrote printouts into the checkout")
        code, out = run("down")
        assert code == 0 and (home / "council-contact-us.pdf").read_bytes() == body, out
        # A printout here that differs is left alone, and the readings still come.
        (home / "council-contact-us.pdf").write_bytes(b"touched")
        (folder / "2026-10-03.pdf").rename(t / "aside.pdf")
        code, out = run("down")
        assert code == 1 and "differs from the index" in out, out
        assert (folder / "2026-10-03.pdf").read_bytes() == b"second", (
            "a printout's problem kept the readings from coming down", out)
        assert (home / "council-contact-us.pdf").read_bytes() == b"touched", (
            "down wrote over a printout here that differs")
        # A printout the bucket holds with other bytes stops up before any
        # reading is sent.
        (home / "council-contact-us.pdf").write_bytes(body)
        (bucket / "sources" / "printouts" / "council-contact-us.pdf").write_bytes(b"other")
        (bucket / ".meta" / "sources" / "printouts" / "council-contact-us.pdf.json").unlink()
        (folder / "2026-10-05.pdf").write_bytes(b"fifth")
        code, out = run("up")
        assert code == 1 and "other bytes" in out, out
        assert not (bucket / "sources" / one / "2026-10-05.pdf").exists(), (
            "up sent a reading before finding a printout it could not send")
    finally:
        shutil.rmtree(t, ignore_errors=True)
    return "ok", (f"{len(reg)} registered documents ({len(gc)} the General Court's, the "
                  "owner's alone); nothing in the kit can match sources/; a round trip "
                  "sends each version once and replaces none")


@check("cloud", "cloud.py sends, fetches and backs up without losing anything",
       needs=("cloud",))
def _cloud_round_trip(CL):
    """Every command against a folder standing in for the bucket.

    The laptop seeds the kit; an empty machine takes it down, byte for byte
    and date for date; the night changes a file of its own, one of the
    laptop's and adds one, and kit-up sends only the night's, keeping the
    copy it replaces. A second machine whose copy changed underneath it is
    refused rather than allowed to overwrite. The backup sends what git does
    not hold and nothing credential, reader-written, logged or built; a
    changed file and a deleted one both leave their last copy in replaced/;
    a deletion past the share a tidy-up reaches sends and moves nothing. And
    across all of it, no object is ever gone without a copy in replaced/.
    """
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="gr-cloud-"))
    try:
        root, bucket = tmp / "laptop", tmp / "bucket"
        root.mkdir()
        _cloud_fixture(root, real)
        B = ["--local-bucket", str(bucket)]
        seen = set()

        def call(*argv):
            code, out = _cloud_call(CL, *argv, *B)
            seen.update(k for k in _bucket_keys(bucket) if not k.startswith("replaced/")) \
                if bucket.exists() else None
            return code, out

        code, out = _cloud_call(CL, "kit-list", "--sizes", "--root", str(root))
        assert code == 0 and "kit: 5 files" in out and "legislation/2026/HB1.html" in out, \
            out[-300:]
        code, out = call("seed-kit", "--dry-run", "--root", str(root))
        assert code == 0 and "nothing sent" in out, out[-300:]
        assert not (bucket / "kit").exists(), "--dry-run sent something"
        code, out = call("seed-kit", "--root", str(root))
        assert code == 0, out[-300:]
        man = json.loads((bucket / "state" / "kit-manifest.json").read_text(encoding="utf-8"))
        assert man["count"] == 5, f"the kit manifest records {man['count']} files, not 5"
        code, out = call("seed-kit", "--root", str(root))
        assert code == 0 and "sent 0 files" in out, "a second seed sent unchanged files"
        code, out = call("state-up", "--root", str(root))
        assert code == 0 and (bucket / "state/census.json").exists(), out[-300:]
        (root / "archive/census.json").write_text('{"census": {"bills": 0}}', encoding="utf-8")
        code, out = call("state-up", "--root", str(root))
        assert code == 0 and "sent 1" in out, out[-300:]
        assert any(p.is_file() for p in bucket.glob("replaced/*/state/census.json*")), \
            "state-up overwrote state/census.json without keeping the old one"

        night = tmp / "night"
        night.mkdir()
        shutil.copy(root / "cloud_kit.json", night / "cloud_kit.json")
        # As the workflow does it: the state first, then the kit.
        assert call("state-down", "--root", str(night))[0] == 0
        code, out = call("kit-down", "--root", str(night))
        assert code == 0, out[-300:]
        for rel in man["files"]:
            a_, b_ = root.joinpath(*rel.split("/")), night.joinpath(*rel.split("/"))
            assert a_.read_bytes() == b_.read_bytes(), f"{rel} came down different"
            assert a_.stat().st_mtime_ns == b_.stat().st_mtime_ns, f"{rel} lost its date"
        (night / "Docket.txt").write_text("docket 2\n", encoding="utf-8")
        (night / "legislation/2026/HB1.html").write_text("<p>ONE</p>", encoding="utf-8")
        (night / "nh-archive/snapshots/2026-09-25").mkdir(parents=True)
        (night / "nh-archive/snapshots/2026-09-25/b.gz").write_text("b", encoding="utf-8")
        (night / "logs").mkdir()
        (night / "logs/nightly-x.log").write_text("the night\n", encoding="utf-8")
        (night / "archive/census.json").write_text('{"census": {"bills": 1}}', encoding="utf-8")
        code, out = call("kit-up", "--dry-run", "--root", str(night))
        assert code == 0 and (bucket / "kit/Docket.txt").read_text() == "docket 1\n", \
            "kit-up --dry-run sent something"
        code, out = call("kit-up", "--root", str(night))
        assert code == 0, out[-300:]
        assert (bucket / "kit/Docket.txt").read_text() == "docket 2\n", "the night's change did not go"
        assert (bucket / "kit/nh-archive/snapshots/2026-09-25/b.gz").exists(), "the night's new file did not go"
        assert (bucket / "kit/legislation/2026/HB1.html").read_text() == "<p>one</p>", \
            "kit-up sent a file the laptop owns"
        day = json.loads((night / CL.KIT_RECORD).read_text(encoding="utf-8"))["date"]
        assert (bucket / f"replaced/{day}/kit/Docket.txt").read_text() == "docket 1\n", \
            "the copy kit-up replaced is not in replaced/"
        assert (bucket / f"logs/{day}/nightly-x.log").exists(), "the night's log did not go"
        assert (bucket / "state/census.json").read_text() == '{"census": {"bills": 1}}'
        code, out = call("kit-up", "--root", str(night))
        assert code == 0 and "sent 0 files" in out, "kit-up run twice sent its files twice"

        other = tmp / "other"
        other.mkdir()
        shutil.copy(root / "cloud_kit.json", other / "cloud_kit.json")
        assert call("kit-down", "--root", str(other))[0] == 0
        (night / "Docket.txt").write_text("docket 3\n", encoding="utf-8")
        assert call("kit-up", "--root", str(night))[0] == 0
        (other / "Docket.txt").write_text("docket 3b\n", encoding="utf-8")
        code, out = call("kit-up", "--root", str(other))
        assert code == 1 and "two writers" in out, "a stale machine overwrote a newer kit file"
        assert (bucket / "kit/Docket.txt").read_text() == "docket 3\n"
        assert (bucket / f"replaced/{day}/kit-conflict/Docket.txt").read_text() == "docket 3b\n", \
            "the refused copy was not kept"

        try:
            ok = _run(["git", "init", "-q", str(root)], capture_output=True, timeout=60)
            ok = ok.returncode == 0 and _run(
                ["git", "-C", str(root), "add", "tracked.py", "cloud_kit.json"],
                capture_output=True, timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
        if not ok:
            return "ok", "kit round trip passed; git is not here for the backup's half"
        code, out = call("backup", "--root", str(root))
        assert code == 0, out[-300:]
        got = {k[len("backup/"):] for k in _bucket_keys(bucket) if k.startswith("backup/")}
        want = {"Docket.txt", "narratives.json", "nh-archive/snapshots/2026-09-24/a.gz",
                "legislation/2026/HB1.html", "legislation/2026/HB2.html",
                "archive/census.json", "reports/gc-changes-2026-09-25.md",
                "CLERK_CORRECTIONS.md", "brand/licensed/drawing.png"}
        assert got == want, (f"the backup sent {sorted(got - want)} and left out "
                             f"{sorted(want - got)}")
        (root / "legislation/2026/HB2.html").write_text("<p>TWO</p>", encoding="utf-8")
        (root / "reports/gc-changes-2026-09-25.md").unlink()
        code, out = call("backup", "--root", str(root))
        assert code == 0, out[-300:]
        today = f"{__import__('datetime').datetime.now():%Y-%m-%d}"
        assert (bucket / f"replaced/{today}/backup/legislation/2026/HB2.html").read_text() \
            == "<p>two</p>", "a changed file's last copy is not in replaced/"
        assert (bucket / f"replaced/{today}/backup/reports/gc-changes-2026-09-25.md").exists() \
            and not (bucket / "backup/reports/gc-changes-2026-09-25.md").exists(), \
            "a deleted file was not moved to replaced/"
        for rel in ("CLERK_CORRECTIONS.md", "brand/licensed/drawing.png", "Docket.txt"):
            (root / rel).unlink()
        code, out = call("backup", "--root", str(root))
        assert code == 1 and "Nothing was sent or moved" in out, \
            "three of eight files gone at once was taken for a tidy-up"
        assert (bucket / "backup/CLERK_CORRECTIONS.md").exists()

        lost = []
        for k in sorted(seen):
            if (bucket / k).exists():
                continue
            if not any(p.is_file() for p in bucket.glob(f"replaced/*/{k}*")):
                lost.append(k)
        assert not lost, f"gone from the bucket with no copy in replaced/: {lost}"

        fresh = tmp / "fresh"
        fresh.mkdir()
        shutil.copy(root / "cloud_kit.json", fresh / "cloud_kit.json")
        (fresh / "archive").mkdir()
        (fresh / "archive/refused.json").write_text('{"where": "here"}', encoding="utf-8")
        code, out = call("state-down", "--root", str(fresh))
        assert code == 0 and (fresh / "archive/census.json").exists(), out[-300:]
        assert (fresh / "archive/refused.json").exists(), \
            "state-down removed a refusal the bucket does not hold"
        return "ok", ("seed, down, up and backup against a folder bucket: byte and "
                      "date exact, owners respected, a stale writer refused, nothing "
                      "private or a reader's sent, and nothing gone without a copy "
                      "in replaced/")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _backup_fixture(CL, tmp):
    """A working folder with a git checkout, as _cloud_round_trip makes it, and a folder
    bucket holding its backup, made by cloud.py backup itself: (root, bucket, B, manifest),
    or None where git is not here to tell the files git holds from those it does not."""
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    root, bucket = tmp / "laptop", tmp / "bucket"
    root.mkdir()
    _cloud_fixture(root, real)
    try:
        ok = _run(["git", "init", "-q", str(root)], capture_output=True, timeout=60)
        ok = ok.returncode == 0 and _run(
            ["git", "-C", str(root), "add", "tracked.py", "cloud_kit.json"],
            capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.SubprocessError):
        ok = False
    if not ok:
        return None
    B = ["--local-bucket", str(bucket)]
    code, out = _cloud_call(CL, "backup", "--root", str(root), *B)
    assert code == 0, f"the fixture's backup failed: {out[-300:]}"
    man = json.loads((bucket / "state" / "backup-manifest.json").read_text(encoding="utf-8"))
    return root, bucket, B, man


@check("cloud", "kit-down asks once more, one file at a time, for what did not arrive: a file R2 "
                "refused once comes down, and one it refuses twice still makes the kit short",
       needs=("cloud",))
def _kit_down_asks_again(CL):
    """ONE MORE ASK (cloud.kit_down, 25 November 2026). R2 answered a dev dry
    run's kit-down with "ServiceUnavailable: Reduce your rate of simultaneous
    reads on the same object" for 9 of 36,255 files, after botocore's own ten
    tries each, and the night stopped on a short kit. kit-down now asks for
    what did not arrive once more, one file at a time after SECOND_PASS_PAUSE;
    only what fails that ask too makes the kit short.

    Against a folder bucket whose get_file refuses one kit file a set number of
    times: refused once, kit-down ends 0 with the file byte for byte and says it
    asked again; refused twice, it ends with THE KIT IS SHORT naming that file.
    The pause is set to nothing here, so the check waits on nothing.
    """
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="gr-cloud-again-"))
    real_open, real_pause = CL.open_bucket, CL.SECOND_PASS_PAUSE
    key = "kit/legislation/2026/HB1.html"
    refusals = {key: 0}

    class Refusing(CL.FolderBucket):
        def get_file(self, k, dst, size=None):
            if refusals.get(k, 0) > 0:
                refusals[k] -= 1
                raise OSError("ServiceUnavailable: Reduce your rate of simultaneous reads on "
                              "the same object.")
            return super().get_file(k, dst, size=size)

    try:
        root, bucket = tmp / "laptop", tmp / "bucket"
        root.mkdir()
        _cloud_fixture(root, real)
        B = ["--local-bucket", str(bucket)]
        code, out = _cloud_call(CL, "seed-kit", "--root", str(root), *B)
        assert code == 0, f"the fixture's seed-kit failed: {out[-300:]}"
        code, out = _cloud_call(CL, "state-up", "--root", str(root), *B)
        assert code == 0, f"the fixture's state-up failed: {out[-300:]}"
        CL.open_bucket = lambda a, preview=False: Refusing(a.local_bucket, create=False)
        CL.SECOND_PASS_PAUSE = 0
        for times, whole in ((1, True), (2, False)):
            night = tmp / f"night-{times}"
            night.mkdir()
            shutil.copy(root / "cloud_kit.json", night / "cloud_kit.json")
            assert _cloud_call(CL, "state-down", "--root", str(night), *B)[0] == 0
            refusals[key] = times
            code, out = _cloud_call(CL, "kit-down", "--root", str(night), *B)
            came = night / "legislation" / "2026" / "HB1.html"
            if whole:
                assert code == 0, (f"kit-down stopped on a file R2 refused once, though the second "
                                   f"ask would have brought it: {out[-400:]}")
                assert "asking for them again" in out and "1 of them arrived" in out, out[-400:]
                assert came.read_bytes() == (root / "legislation/2026/HB1.html").read_bytes(), \
                    "the file the second ask brought is not the laptop's"
            else:
                assert code != 0 and "THE KIT IS SHORT" in out and "legislation/2026/HB1.html" in out, \
                    f"a file refused twice did not make the kit short: {out[-400:]}"
                assert not came.exists(), "a file that never arrived is on the disk"
        return "ok", ("a kit file R2 refuses once comes down on kit-down's second ask, byte "
                      "for byte; one refused twice still makes the kit short")
    finally:
        CL.open_bucket, CL.SECOND_PASS_PAUSE = real_open, real_pause
        shutil.rmtree(tmp, ignore_errors=True)


@check("cloud", "restore brings the backup back into an empty folder, each file checked against "
                "the backup's manifest, and writes nothing to the bucket", needs=("cloud",))
def _cloud_restore(CL):
    """THE BACKUP, BROUGHT BACK (cloud.py; the refactor's stage 0, ops item 5): the laptop's
    46 GB backup had never been read back, and no command could. Every function cmd_restore
    reaches is read, and none puts, copies or deletes in the bucket (the reader first, on a put
    planted two calls down). Then against a folder bucket that cloud.py backup filled from a
    fixture, through a bucket that fails any write: a dry run makes no folder; a whole restore
    is byte and date exact and its last line counts restored, verified, missing and
    mismatched; a DEST with anything in it, one inside the working folder, a second DEST and a
    bucket with no backup are refused, the last without making the folder; --only takes a path
    (with a backslash), a glob and a second --only, and one naming nothing fails; an object gone
    from the bucket is missing and one changed there is mismatched, kept under _mismatched/
    and not at its own path, both named and exit 1; and a manifest entry on the never list,
    or one whose path climbs out of DEST, is never written, even where the bucket lists it."""
    import ast
    probe = ast.parse("def cmd_restore(a):\n    helper(a)\n\n\ndef helper(b):\n"
                      "    b.copy('k', 'j')\n")
    assert any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "copy"
               for d in _reached(probe, "cmd_restore").values() for n in ast.walk(d)), \
        "the reader of restore's code misses a copy two calls down"
    tree = ast.parse(_source(CL.__file__))
    reached = _reached(tree, "cmd_restore", leaves={"FolderBucket", "NotAsked", "R2Bucket"})
    WRITERS = {"put_file", "put_bytes", "copy", "delete", "keep"}
    NAMED = {"send", "write_manifest", "put_logs", "state_up", "Replacer", "Checkpoint",
             "send_refusal", "unsent_after", "open_bucket"}
    bad = sorted({f"{name} calls {n.func.attr}" for name, d in reached.items()
                  for n in ast.walk(d) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and n.func.attr in WRITERS}
                 | {f"cmd_restore reaches {name}" for name in reached if name in NAMED})
    assert {"cmd_restore", "restore_into", "open_to_read", "empty_dest"} <= set(reached), \
        f"cmd_restore was not found to read: {sorted(reached)}"
    assert not bad, "restore can write to the bucket: " + "; ".join(bad)

    writes = []

    class ReadOnly(CL.FolderBucket):
        def _no(self, what, key):
            writes.append(f"{what} {key}")
            raise AssertionError(f"restore tried to {what} {key} in the bucket")

        def put_file(self, src, key, meta):
            self._no("put", key)

        def put_bytes(self, key, data):
            self._no("put", key)

        def copy(self, src, dst):
            self._no("copy", dst)

        def delete(self, key):
            self._no("delete", key)

    tmp = Path(tempfile.mkdtemp(prefix="gr-restore-"))
    saved = CL.open_to_read
    try:
        made = _backup_fixture(CL, tmp)
        if made is None:
            return "ok", "restore reads the bucket and writes nothing there; git is not here for a backup to restore"
        root, bucket, B, man = made
        CL.open_to_read = lambda a: ReadOnly(a.local_bucket, create=False) if a.local_bucket \
            else saved(a)

        def restore(dest, *more):
            return _cloud_call(CL, "restore", str(dest), "--root", str(root), *B, *more)

        def tree_of(d):
            return sorted(p.relative_to(d).as_posix() for p in Path(d).rglob("*") if p.is_file())
        files = sorted(man["files"])
        assert len(files) == 9 and "CLERK_CORRECTIONS.md" in files, files
        dest = tmp / "back"
        code, out = restore(dest, "--dry-run")
        assert code == 0 and "nothing restored" in out and not dest.exists(), out[-300:]
        code, out = restore(dest)
        assert code == 0 and tree_of(dest) == files, (code, out[-400:], tree_of(dest))
        for rel in files:
            a_, b_ = root.joinpath(*rel.split("/")), dest.joinpath(*rel.split("/"))
            assert a_.read_bytes() == b_.read_bytes(), f"{rel} came back different"
            assert a_.stat().st_mtime_ns == b_.stat().st_mtime_ns, f"{rel} came back without its date"
        last = [ln for ln in out.splitlines() if ln.startswith("restore: of ")]
        assert last and "of 9 files asked for, 9 restored, 9 verified" in last[0] and \
            "0 mismatched; 0 missing from the bucket; 0 could not be read" in last[0], out[-400:]
        for argv, said in (((dest,), "is not empty"), ((root / "back",), "inside the working folder"),
                           ((tmp / "x", tmp / "y"), "takes one DEST")):
            code, out = _cloud_call(CL, "restore", *map(str, argv), "--root", str(root), *B)
            assert code == 1 and said in out, (argv, out[-300:])
        assert not (root / "back").exists() and not (tmp / "x").exists(), "a refused restore made its folder"
        code, out = _cloud_call(CL, "restore", str(tmp / "z"), "--root", str(root),
                                "--local-bucket", str(tmp / "no-bucket"))
        assert code == 1 and "holds no backup" in out and not (tmp / "no-bucket").exists(), out[-300:]
        code, out = restore(tmp / "only", "--only", "legislation\\2026\\HB1.html", "--only", "brand/**")
        assert code == 0 and tree_of(tmp / "only") == ["brand/licensed/drawing.png",
                                                       "legislation/2026/HB1.html"], (out[-300:], tree_of(tmp / "only"))
        code, out = restore(tmp / "none", "--only", "nothing/here.md")
        assert code == 1 and "names nothing the backup holds" in out, out[-300:]
        (bucket / "backup" / "Docket.txt").unlink()
        (bucket / "backup" / "narratives.json").write_text('{"changed": "in the bucket"}', encoding="utf-8")
        code, out = restore(tmp / "short")
        got = tree_of(tmp / "short")
        assert code == 1 and "1 mismatched" in out and "1 missing from the bucket" in out and \
            "Docket.txt is in the manifest and not in the bucket" in out and \
            "narratives.json arrived as" in out, out[-500:]
        assert "_mismatched/narratives.json" in got and "narratives.json" not in got and \
            "Docket.txt" not in got and len(got) == 8, got
        assert (tmp / "short" / "_mismatched" / "narratives.json").read_text(encoding="utf-8") == \
            '{"changed": "in the bucket"}', "the mismatched bytes were not kept"

        # A manifest naming what must never come back, as a leaked key could write one.
        doc = dict(man)
        doc["files"] = dict(man["files"])
        body = b"not a real one"
        import hashlib
        ent = {"size": len(body), "sha256": hashlib.sha256(body).hexdigest(), "mtime_ns": "0"}
        doc["files"].update({"secrets.json": ent, "../outside.txt": ent})
        (bucket / "backup" / "secrets.json").write_bytes(body)
        (bucket / "state" / "backup-manifest.json").write_text(json.dumps(doc), encoding="utf-8")

        class Lists(ReadOnly):
            # The bucket a leaked key wrote to: it lists the climbing path, and serves it.
            def list(self, prefix):
                got = super().list(prefix)
                got["backup/../outside.txt"] = len(body)
                return got

            def get_file(self, key, dst, size=None):
                if ".." in key.split("/"):
                    Path(dst).write_bytes(body)
                    return
                super().get_file(key, dst, size)
        CL.open_to_read = lambda a: Lists(a.local_bucket, create=False)
        code, out = restore(tmp / "never")
        got = tree_of(tmp / "never")
        assert "secrets.json" not in got and not (tmp / "outside.txt").exists() and \
            not any(p.name == "outside.txt" for p in tmp.rglob("outside.txt")), (got, out[-400:])
        assert code == 1 and "on the never list" in out and "would climb out of DEST" in out, out[-500:]
        assert not writes, f"restore tried to write to the bucket: {writes}"
    finally:
        CL.open_to_read = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("restore reaches no put, copy or delete; against a backup cloud.py made, a whole "
                  "restore came back byte and date exact, counted; a DEST not empty, inside the "
                  "working folder or doubled, and a bucket with no backup, refused; --only paths "
                  "and globs, twice; a missing and a mismatched file named, exit 1, the changed "
                  "bytes kept aside; a never-list path and a climbing one never written")


@check("cloud", "restore --sample restores files from across the backup into a folder of its own, "
                "deletes it, records how it went, and every pull says so", needs=("cloud",))
def _cloud_restore_sample(CL):
    """A SAMPLE RESTORE, MONTHLY (cloud.py; the refactor's stage 0, ops item 5). sample_of on a
    fixture of folders: one file from each folder first, then the rest at random, never a file
    over the limit or more bytes in all than allowed, the same seed the same files and other
    seeds others. Then against a backup cloud.py made, through a bucket that fails any write: a
    dry run restores and records nothing; a sample of four comes from four folders, verified, its
    folder deleted, and the record says when, how many and from which kind of bucket; a sample
    over a file changed in the bucket is exit 1, recorded as failed with the file named, and its
    folder is deleted all the same; --sample 0, or with a DEST or --only, is refused. pull reaches
    backup_news, and backup_news says each record: none, a good one, a failed one, one a week
    past due as STALE, and a folder's as a test."""
    import ast
    from datetime import datetime as dt
    files = {f"big/{i:03d}.txt": {"size": 10} for i in range(100)}
    files.update({"a/x.txt": {"size": 10}, "b/y.txt": {"size": 10}, "c/z.txt": {"size": 10},
                  "root.txt": {"size": 10}, "huge/h.bin": {"size": CL.SAMPLE_FILE_MOST + 1}})

    def tops(paths):
        return {p.split("/", 1)[0] if "/" in p else "" for p in paths}
    got = CL.sample_of(files, 5, "2026-11-16")
    assert len(got) == 5 and tops(got) == {"big", "a", "b", "c", ""}, got
    got = CL.sample_of(files, 3, "2026-11-16")
    assert len(got) == 3 and len(tops(got)) == 3, got
    many = CL.sample_of(files, 40, "2026-11-16")
    assert len(many) == 40 and "huge/h.bin" not in many and {"a", "b", "c", ""} <= tops(many), many[:8]
    assert CL.sample_of(files, 40, "2026-11-16") == many, "the same seed chose other files"
    assert any(CL.sample_of(files, 40, f"2026-12-{d:02d}") != many for d in range(1, 6)), \
        "five other seeds chose the same forty files"
    cheap = CL.sample_of(files, 40, "2026-11-16", bytes_most=95)
    assert len(cheap) == 9, f"a budget of 95 bytes took {len(cheap)} files of 10"
    assert CL.sample_of(files, 400, "x") == sorted(set(files) - {"huge/h.bin"}), \
        "a sample larger than the backup did not take every file it may"

    tree = ast.parse(_source(CL.__file__))
    assert "backup_news" in _reached(tree, "cmd_pull") and \
        "restore_sample" in _reached(tree, "cmd_restore"), \
        "pull no longer prints the laptop's backup records, or restore no longer samples"

    writes = []

    class ReadOnly(CL.FolderBucket):
        def put_file(self, src, key, meta):
            writes.append(key)

        def put_bytes(self, key, data):
            writes.append(key)

        def copy(self, src, dst):
            writes.append(dst)

        def delete(self, key):
            writes.append(key)

    tmp = Path(tempfile.mkdtemp(prefix="gr-sample-"))
    saved = CL.open_to_read
    try:
        made = _backup_fixture(CL, tmp)
        if made is None:
            return "ok", "sample_of chooses across the folders; git is not here for a backup to sample"
        root, bucket, B, man = made
        CL.open_to_read = lambda a: ReadOnly(a.local_bucket, create=False)
        rec_path = root.joinpath(*CL.SAMPLE_RECORD.split("/"))

        def sample(*argv):
            return _cloud_call(CL, "restore", *argv, "--root", str(root), *B)
        code, out = sample("--sample", "4", "--dry-run")
        assert code == 0 and "nothing recorded" in out and not rec_path.exists(), out[-300:]
        code, out = sample("--sample", "4")
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        assert code == 0 and rec.get("ok") is True and rec["asked"] == rec["picked"] == \
            rec["verified"] == rec["restored"] == 4 and rec["folders"] == 4 and \
            rec["mismatched"] == rec["missing"] == rec["failed"] == 0, (out[-300:], rec)
        assert rec["bucket"]["kind"] == "folder" and rec.get("removed") is True and \
            not Path(rec["folder"]).exists() and rec["at"][:4] == str(dt.now().year), rec
        (bucket / "backup" / "Docket.txt").write_text("docket, changed in the bucket\n", encoding="utf-8")
        code, out = sample("--sample", "9")
        rec = json.loads(rec_path.read_text(encoding="utf-8"))
        assert code == 1 and rec.get("ok") is False and rec["mismatched"] == 1 and \
            "Docket.txt" in rec.get("said", "") and rec["verified"] == 8, (out[-300:], rec)
        assert rec.get("removed") is True and not Path(rec["folder"]).exists(), \
            "a sample that failed left its folder behind"
        for argv, said in ((("--sample", "0"), "1 or more"),
                           ((str(tmp / "dest"), "--sample", "2"), "no DEST"),
                           (("--sample", "2", "--only", "Docket.txt"), "no --only")):
            code, out = sample(*argv)
            assert code == 1 and said in out, (argv, out[-300:])
        assert not writes, f"the sample restore wrote to the bucket: {writes}"

        now = dt(2026, 11, 16, 8, 0)

        def sample_news():
            # The sample's line of pull's, beside the backup's own (_backup_weekly holds that).
            return [ln for ln in CL.backup_news(root, now) if "SAMPLE" in ln.upper()]
        news = sample_news()
        assert len(news) == 1 and news[0].startswith("SAMPLE RESTORE FAILED --") and \
            "Docket.txt" in news[0] and "a test against a folder" in news[0], news
        good = {"ok": True, "at": "x", "picked": 50, "verified": 50, "folders": 12,
                "bucket": {"kind": "r2"}}
        for days, head in ((3, ""), (CL.SAMPLE_DAYS + 6, ""), (CL.SAMPLE_DAYS + 8, "STALE -- ")):
            CL.save_record(root, CL.SAMPLE_RECORD,
                           dict(good, epoch=now.timestamp() - days * 86400))
            news = sample_news()
            assert len(news) == 1 and news[0].startswith(head or "the last sample restore") and \
                f"{days} days ago" in news[0] and "50 of 50 files verified" in news[0] and \
                "a test" not in news[0], (days, news)
        rec_path.unlink()
        news = sample_news()
        assert len(news) == 1 and news[0].startswith("NO SAMPLE RESTORE on record") and \
            f"restore --sample {CL.SAMPLE_FILES}" in news[0], news
    finally:
        CL.open_to_read = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("one file from each folder first, the size limits held, a seed's sample "
                  "repeatable; a dry run records nothing; four files from four folders verified, "
                  "their folder deleted, recorded; a changed file recorded as a failure, exit 1, "
                  "its folder deleted too; misuse refused; nothing written to the bucket; pull "
                  "says none, good, failed, STALE past a week overdue, and a folder's as a test")


@check("cloud", "a backup from the laptop's repository carries the extras -- the repository's "
                "bundle, the memory, the scheduled tasks and the Task Scheduler entries -- and no "
                "credential", needs=("cloud",))
def _cloud_backup_extras(CL):
    """THE BACKUP'S EXTRAS (cloud.py; the refactor's stage 0, ops item 7): the local commits and
    tags, the memory of the owner's decisions, the morning triage's instructions and the Task
    Scheduler entries were in no backup. On a fixture -- a repository with a commit and a tag
    and no remote, a memory folder, scheduled tasks named granite-* and another, and Task
    Scheduler stood in for -- gather_extras makes a bundle git verifies and clones back with its
    tag, copies every memory file with its date and every granite-* task's file and no other,
    writes the entry in UTF-16 with its mark, and refuses a memory file shaped like a credential
    (made here, never typed, so this file holds none), naming it and not its value. Run again
    with nothing moved, the bundle stands as it was; a commit makes it again; a source file gone
    keeps its copy, and a memory folder gone keeps them all; a commit carrying a credential's
    shape stops the bundle, naming the path, and the last one stands. And backup gathers them
    outside the repository that holds secrets.json only with --extras, never on a dry run, sends
    them, and fails on the refused file once the rest has gone."""
    git = shutil.which("git")
    if not git:
        return "skip", "git is not here, so there is no repository to bundle"
    tmp = Path(tempfile.mkdtemp(prefix="gr-extras-"))
    saved = (CL.memory_folder, CL.claude_home, CL.scheduler_entries)

    def g(*args, cwd=None):
        r = _run([git, "-c", "user.name=preflight", "-c", "user.email=preflight@example.invalid",
                  *args], capture_output=True, timeout=120, cwd=cwd)
        assert r.returncode == 0, f"git {' '.join(args[:3])} failed: {(r.stderr or '')[-200:]}"
        return r.stdout

    def writable(fn, path, exc):
        os.chmod(path, 0o666)
        fn(path)
    try:
        root = tmp / "laptop"
        root.mkdir()
        _cloud_fixture(root, json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8")))
        g("init", "-q", str(root))
        g("-C", str(root), "add", "tracked.py", "cloud_kit.json")
        g("-C", str(root), "commit", "-q", "-m", "one")
        g("-C", str(root), "tag", "kept-here")
        memory, tasks = tmp / "memory", tmp / "tasks"
        (tasks / "granite-report-triage").mkdir(parents=True)
        (tasks / "granite-report-triage" / "SKILL.md").write_text("the triage\n", encoding="utf-8")
        (tasks / "another-project").mkdir()
        (tasks / "another-project" / "SKILL.md").write_text("not ours\n", encoding="utf-8")
        memory.mkdir()
        for name in ("MEMORY.md", "a.md", "b.md"):
            (memory / name).write_text(f"{name}\n", encoding="utf-8")
        token = "gh" + "p_" + "Q7" * 18                 # a token's shape, made here, never typed
        (memory / "careless.md").write_text(f"the key is {token}\n", encoding="utf-8")
        entry = '<?xml version="1.0" encoding="UTF-16"?>\r\n<Task version="1.3">\r\n</Task>\r\n'

        def gather():
            return CL.gather_extras(root, memory=memory, tasks=tasks,
                                    scheduler=lambda: {"\\Granite Record captions inbox": entry})
        out = root.joinpath(*CL.EXTRAS.split("/"))
        got = gather()
        bundle = out / "repository.bundle"
        heads = g("bundle", "list-heads", str(bundle), cwd=str(root))
        assert "refs/tags/kept-here" in heads and "refs/heads/" in heads, (heads, got)
        g("-C", str(root), "bundle", "verify", str(bundle))
        g("clone", "-q", str(bundle), str(tmp / "clone"))
        assert "kept-here" in g("-C", str(tmp / "clone"), "tag"), "the bundle cloned without its tag"
        for name in ("MEMORY.md", "a.md", "b.md"):
            a_, b_ = memory / name, out / "memory" / name
            assert a_.read_bytes() == b_.read_bytes() and \
                a_.stat().st_mtime_ns == b_.stat().st_mtime_ns, f"memory/{name} was not copied with its date"
        assert not (out / "memory" / "careless.md").exists(), "a file shaped like a credential was copied"
        refused = [p for p in got["problems"] if "careless.md" in p]
        assert len(refused) == 1 and "a GitHub token" in refused[0] and \
            token not in " ".join(got["problems"] + got["lines"]), got["problems"]
        assert (out / "scheduled-tasks" / "granite-report-triage" / "SKILL.md").read_text(
            encoding="utf-8") == "the triage\n" and not (out / "scheduled-tasks" / "another-project").exists()
        xml = (out / "task-scheduler" / "Granite Record captions inbox.xml").read_bytes()
        assert xml[:2] == b"\xff\xfe" and xml.decode("utf-16") == entry, xml[:40]
        index = json.loads((out / "extras.json").read_text(encoding="utf-8"))
        assert index["task_scheduler"] == ["\\Granite Record captions inbox"] and \
            index["memory"]["files"] == 3, index
        # Nothing moved: the bundle stands. A commit: it is made again, with the commit.
        made = bundle.stat().st_mtime_ns
        got = gather()
        assert bundle.stat().st_mtime_ns == made and any("no ref has moved" in ln for ln in got["lines"]), \
            got["lines"]
        (root / "tracked.py").write_text("x = 2\n", encoding="utf-8")
        g("-C", str(root), "commit", "-q", "-am", "two")
        got = gather()
        assert g("-C", str(root), "rev-parse", "HEAD").strip() in \
            g("bundle", "list-heads", str(bundle), cwd=str(root)), got["lines"]
        # A source gone keeps its copy; the whole memory folder gone keeps them all.
        (memory / "b.md").unlink()
        got = gather()
        assert (out / "memory" / "b.md").exists() and \
            any("1 kept whose source is gone" in ln for ln in got["lines"]), got["lines"]
        shutil.rmtree(memory)
        got = gather()
        assert all((out / "memory" / n).exists() for n in ("MEMORY.md", "a.md", "b.md")) and \
            any("the copy here stands" in ln for ln in got["lines"]), got["lines"]
        # A commit carrying a credential's shape: no new bundle, its path named, the last one stands.
        before = bundle.read_bytes()
        (root / "careless.py").write_text(f"KEY = '{token}'\n", encoding="utf-8")
        g("-C", str(root), "add", "careless.py")
        g("-C", str(root), "commit", "-q", "-m", "three")
        got = gather()
        assert bundle.read_bytes() == before and \
            any("careless.py looks like a GitHub token" in p for p in got["problems"]) and \
            token not in " ".join(got["problems"]), got["problems"]
        g("-C", str(root), "reset", "-q", "--hard", "HEAD~1")
        memory.mkdir()
        (memory / "careless.md").write_text(f"the key is {token}\n", encoding="utf-8")

        # backup: --extras here, never on a dry run; sent; failing on the refusal after the rest.
        CL.memory_folder = lambda r: memory
        CL.claude_home = lambda: tmp
        (tmp / "scheduled-tasks").mkdir()
        CL.scheduler_entries = lambda: {}
        bucket = tmp / "bucket"
        B = ["--root", str(root), "--local-bucket", str(bucket)]
        stamp = (out / "extras.json").stat().st_mtime_ns
        code, said = _cloud_call(CL, "backup", *B, "--dry-run")
        assert code == 0 and "not gathered on a dry run" in said and \
            (out / "extras.json").stat().st_mtime_ns == stamp, said[-300:]
        code, said = _cloud_call(CL, "backup", *B)
        assert code == 0 and "not the repository that holds secrets.json" in said and \
            (out / "extras.json").stat().st_mtime_ns == stamp, said[-300:]
        code, said = _cloud_call(CL, "backup", *B, "--extras")
        sent = {p.relative_to(bucket / "backup").as_posix()
                for p in (bucket / "backup").rglob("*") if p.is_file()}
        assert code == 1 and "extras are short" in said and "careless.md" in said and \
            token not in said, said[-400:]
        for rel in ("archive/backup-extras/repository.bundle", "archive/backup-extras/memory/a.md",
                    "archive/backup-extras/extras.json", "Docket.txt", "CLERK_CORRECTIONS.md"):
            assert rel in sent, f"the backup with its extras did not send {rel}: {sorted(sent)[:12]}"
        assert not any("careless" in s for s in sent), "a file shaped like a credential reached the bucket"
    finally:
        CL.memory_folder, CL.claude_home, CL.scheduler_entries = saved
        shutil.rmtree(tmp, onexc=writable)
    return "ok", ("a bundle git verifies and clones with its tag, made again only when a ref moves, "
                  "and not over a commit shaped like a credential; the memory copied with its "
                  "dates, a credential-shaped file refused by name, copies kept when sources go; "
                  "granite-* tasks alone; the entry in UTF-16; gathered by backup only with "
                  "--extras here and not on a dry run, sent, the refusal failing it after the rest")


@check("cloud", "the night warns when the laptop's backup is more than two weeks old, from one look "
                "at the bucket's backup manifest, and never holds a night for it",
       needs=("cloud", "nightly"))
def _night_backup_stale(CL, NI):
    """THE LAPTOP'S BACKUP (nightly.py) and THE LAPTOP'S BACKUP, AS THE NIGHT SEES IT (cloud.py;
    the refactor's stage 0, ops item 6): nothing said how old the laptop's backup was. The two
    names agree, and the workflow brings the state down before the night and its verdict. On a
    folder bucket that counts what it is asked, state-down looks at state/backup-manifest.json
    once, by its date and never its body, and records the date or its absence; a look that fails
    is recorded and never fails state-down; a dry state-down records nothing. Through the
    stand-in for boto3 the look is one HEAD and its LastModified. Then backup_warned(): no
    record, and a manifest 14 days old, say nothing; 15 or 40 days, none, a look that failed and
    a record that will not read each warn in one line with what to do, of a kind the gate never
    holds a night for, in the night's warnings and its standing ones."""
    import contextlib
    import io
    import types
    from datetime import datetime as dt, timedelta, timezone
    assert NI.BACKUP_SEEN.as_posix() == CL.BACKUP_SEEN == "archive/cloud/backup-seen.json", (
        NI.BACKUP_SEEN, CL.BACKUP_SEEN)
    assert NI.BACKUP_DAYS == CL.BACKUP_DAYS == 14 and NI.KIND_BACKUP.startswith(NI.KIND_HEALTH), \
        (NI.BACKUP_DAYS, CL.BACKUP_DAYS, NI.KIND_BACKUP)
    wf = _SWITCHED.workflow_dir / "nightly.yml"
    if wf.exists():
        text = _source(wf)
        down, night, close = (text.find(s) for s in ("python src/ops/cloud.py state-down",
                                                     "python nightly.py @flags",
                                                     "python nightly.py --runner --close"))
        assert -1 < down < night < close, "nightly.yml no longer brings the state down before the night"

    asked = []

    class Counting(CL.FolderBucket):
        def modified(self, key):
            asked.append(("modified", key))
            return super().modified(key)

        def get_bytes(self, key):
            asked.append(("get", key))
            return super().get_bytes(key)

    class Broken(CL.FolderBucket):
        def modified(self, key):
            raise OSError("the endpoint said no")

    here = Path(".").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gr-backup-seen-"))
    saved = CL.open_bucket
    mods, store, made = _fake_s3()
    saved_mods = {n: sys.modules.get(n) for n in mods}
    try:
        kit = {"kit": [], "state": [{"path": "archive/census.json", "key": "census.json", "what": "x"}],
               "never": {"globs": ["secrets.json"]}, "backup": {"leave_out": []}}
        night, bucket = tmp / "night", tmp / "bucket"
        night.mkdir()
        (night / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")
        (bucket / "state").mkdir(parents=True)
        (bucket / "state" / "census.json").write_text("{}", encoding="utf-8")
        man = bucket / "state" / "backup-manifest.json"
        seen = night.joinpath(*CL.BACKUP_SEEN.split("/"))

        def state_down(cls, *more):
            CL.open_bucket = lambda a, preview=False: cls(str(bucket))
            asked.clear()
            return _cloud_call(CL, "state-down", "--root", str(night), "--local-bucket", str(bucket), *more)
        code, out = state_down(Counting)
        rec = json.loads(seen.read_text(encoding="utf-8"))
        assert code == 0 and rec.get("absent") is True and \
            asked.count(("modified", "state/backup-manifest.json")) == 1, (out[-300:], rec, asked)
        man.write_text('{"files": {}}', encoding="utf-8")
        when = (dt.now() - timedelta(days=20)).timestamp()
        os.utime(man, (when, when))
        code, out = state_down(Counting)
        rec = json.loads(seen.read_text(encoding="utf-8"))
        assert code == 0 and abs(rec["written_epoch"] - when) < 2 and \
            "backup-manifest.json was last written" in out, (out[-300:], rec)
        assert [x for x in asked if x[1] == "state/backup-manifest.json"] == \
            [("modified", "state/backup-manifest.json")], f"state-down read the backup's manifest: {asked}"
        seen.unlink()
        code, out = state_down(Counting, "--dry-run")
        assert code == 0 and not seen.exists(), "a dry state-down recorded what it saw"
        code, out = state_down(Broken)
        rec = json.loads(seen.read_text(encoding="utf-8"))
        assert code == 0 and "the endpoint said no" in rec.get("error", ""), (out[-300:], rec)
        # Through the stand-in for boto3: one HEAD, and its LastModified.
        sys.modules.update(mods)
        r2 = CL.R2Bucket({"account": "acct0123456789", "key_id": "keyid0123456789",
                          "secret": "secret0123456789", "bucket": "granite-record-backup"}, 4)
        stamp = dt(2026, 11, 2, 10, 30, tzinfo=timezone.utc)
        heads = []
        plain = r2.s3.head_object

        def head_object(**kw):
            heads.append(kw["Key"])
            return dict(plain(**kw), LastModified=stamp)
        r2.s3.head_object = head_object
        assert r2.modified("state/backup-manifest.json") is None, "a missing manifest read as there"
        store[("granite-record-backup", "state/backup-manifest.json")] = (b"{}", {})
        assert r2.modified("state/backup-manifest.json") == stamp.timestamp() and \
            heads == ["state/backup-manifest.json"] * 2, heads

        # The warning, from what state-down left.
        def warned(rec):
            p = tmp / "seen.json"
            if rec is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(rec if isinstance(rec, str) else json.dumps(rec), encoding="utf-8")
            return NI.backup_warned(p)
        look = dt(2026, 11, 16, 3, 20)
        assert warned(None) == [], "no record of a look warned"
        for days, warns in ((0, False), (14, False), (15, True), (40, True)):
            w = look - timedelta(days=days)
            got = warned({"seen_epoch": look.timestamp(), "written_epoch": w.timestamp()})
            assert bool(got) == warns, (days, got)
            if warns:
                said = got[0][1]
                assert [k for k, _s in got] == [NI.KIND_BACKUP] and f"{days} days old" in said and \
                    NI.day_said(w.date()) in said and "python3 src/ops/cloud.py backup" in said and \
                    "\n" not in said, said
        for rec, words in (({"absent": True}, "holds no state/backup-manifest.json"),
                           ({"error": "OSError: the endpoint said no"}, "the endpoint said no"),
                           ("{not json", "would not read")):
            got = warned(rec)
            assert [k for k, _s in got] == [NI.KIND_BACKUP] and words in got[0][1], (rec, got)
        sentence = warned({"seen_epoch": look.timestamp(),
                           "written_epoch": (look - timedelta(days=20)).timestamp()})[0][1]
        assert NI.warning_reasons([(NI.KIND_BACKUP, sentence)], [], ()) == [], \
            "a stale backup would hold the night"
        os.chdir(tmp)
        Path("archive/cloud").mkdir(parents=True)
        Path(NI.BACKUP_SEEN).write_text((tmp / "seen.json").read_text(encoding="utf-8"), encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            mine = dict(NI.Night.warned(types.SimpleNamespace(v={"started": "2026-11-16T03:20:00"})))
        assert mine.get(NI.KIND_BACKUP) == sentence and sentence in NI.warns_of({}), (
            "the stale backup is not among the night's warnings and its standing ones")
    finally:
        os.chdir(here)
        CL.open_bucket = saved
        for n, m in saved_mods.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("state-down looks once, by date alone, and records the date, an absence or a "
                  "failed look without failing; R2's is one HEAD; 15 days, none, a failed look or "
                  "an unreadable record warn in one line with the command, 14 does not; never "
                  "holding a night, in the night's warnings and its standing ones")


@check("cloud", "the laptop's weekly backup runs the backup, and a sample restore when one is due, "
                "records each however it ends, every pull says so, and its Task Scheduler entry "
                "is set as the captions inbox's", needs=("cloud", "backup_weekly"))
def _backup_weekly(CL, BW):
    """THE BACKUP'S OWN RECORD (cloud.py) and src/ops/backup_weekly.py (the refactor's stage 0,
    ops items 5 and 6): the backup ran when the owner ran it, and nothing said when it last
    had. The entry: the template is XML and names no one's folder or account; --task-xml writes
    it for a checkout in UTF-16 with its mark, every Sunday, running the job from the checkout
    into its log, with the captions inbox's settings (whether logged on or not, on battery,
    waking the laptop, as soon as it can after a missed start, one at a time) and six hours to
    finish. The job, against a folder bucket: a first run backs up and, with none on record,
    samples, exit 0, both recorded; a second does not sample; a dry run records nothing; a try
    a build refuses is tried again after the wait and goes; a backup refused every time is
    exit 1, FAILED, and recorded by the backup itself; one that never started (the machine's
    lock held) is recorded by the job; a failed sample is exit 1 and recorded; GitHub's machine,
    and a checkout without secrets.json and no --local-bucket, are refused. And pull's line from
    the backup's record: none, a good one, a failed one, and one more than 14 days old as
    STALE."""
    import contextlib
    import io
    import time as time_
    import types
    import xml.etree.ElementTree as ET
    from datetime import datetime as dt
    template = _source(BW.XML)
    assert BW.CHECKOUT in template and not re.search(r"(?i)\\Users\\|S-1-5-21|<UserId>", template), \
        "the Task Scheduler template names a folder or an account of someone's"
    try:
        ET.fromstring(template.encode("utf-8"))
    except ET.ParseError as e:
        raise AssertionError(f"src/ops/backup_weekly.xml is not well-formed XML: {e}")
    assert CL.BACKUP_DAYS == 14 and CL.BACKUP_RECORD == "archive/cloud/backup.json", \
        (CL.BACKUP_DAYS, CL.BACKUP_RECORD)
    tmp = Path(tempfile.mkdtemp(prefix="gr-weekly-"))
    saved_time, saved_env = BW.time, os.environ.get("GITHUB_ACTIONS")

    def job(*argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = BW.main(list(argv))
        return code, out.getvalue()
    try:
        checkout = tmp / "a checkout"
        code, said = job("--task-xml", str(tmp / "task.xml"), "--root", str(checkout))
        raw = (tmp / "task.xml").read_bytes()
        assert code == 0 and raw[:2] == b"\xff\xfe" and \
            raw.decode("utf-16").startswith('<?xml version="1.0" encoding="UTF-16"?>') and \
            "<!--" not in raw.decode("utf-16"), raw[:80]
        assert f'schtasks /create /tn "{BW.TASK_NAME}" /xml' in said, said
        t = "{http://schemas.microsoft.com/windows/2004/02/mit/task}"
        doc = ET.fromstring(raw)

        def one(path):
            el = doc.find("/".join(t + p for p in path.split("/")))
            assert el is not None, f"the entry has no {path}"
            return (el.text or "").strip()
        week = "Triggers/CalendarTrigger/ScheduleByWeek"
        assert doc.find("/".join(t + p for p in (week + "/DaysOfWeek/Sunday").split("/"))) is not None \
            and one(week + "/WeeksInterval") == "1", "the entry is not every Sunday"
        for path, want in (("Settings/StartWhenAvailable", "true"), ("Settings/WakeToRun", "true"),
                           ("Settings/DisallowStartIfOnBatteries", "false"),
                           ("Settings/StopIfGoingOnBatteries", "false"),
                           ("Settings/MultipleInstancesPolicy", "IgnoreNew"),
                           ("Settings/ExecutionTimeLimit", "PT6H"),
                           ("Principals/Principal/LogonType", "Password"),
                           ("RegistrationInfo/URI", "\\" + BW.TASK_NAME),
                           ("Actions/Exec/Command", "cmd")):
            assert one(path) == want, f"the entry's {path} is {one(path)!r}, not {want!r}"
        assert one("Actions/Exec/Arguments") == (
            f'/c cd /d "{checkout.resolve()}" && python3 -X utf8 src\\ops\\backup_weekly.py '
            f'>> {BW.LOG} 2>&1'), one("Actions/Exec/Arguments")

        made = _backup_fixture(CL, tmp)
        if made is None:
            return "ok", "the entry is right; git is not here for a backup for the job to run"
        root, bucket, B, man = made
        rec_b = root.joinpath(*CL.BACKUP_RECORD.split("/"))
        rec_s = root.joinpath(*CL.SAMPLE_RECORD.split("/"))
        W = ["--root", str(root), "--local-bucket", str(bucket), "--retry-minutes", "0"]

        def read(p):
            return json.loads(p.read_text(encoding="utf-8"))
        first = read(rec_b)
        assert first.get("ok") is True and first.get("sent") == 9 and \
            first.get("manifest", {}).get("count") == 9, f"the fixture's backup recorded {first}"
        code, said = job(*W)
        b, s = read(rec_b), read(rec_s)
        assert code == 0 and "BACKUP WEEKLY ok" in said and "a sample restore is due (none on record)" in said \
            and b["ok"] and b["epoch"] > first["epoch"] and s["ok"] and s["bucket"]["kind"] == "folder", \
            (said[-400:], b, s)
        code, said = job(*W)
        assert code == 0 and "no sample restore this week" in said and read(rec_s)["epoch"] == s["epoch"], \
            said[-300:]
        before = rec_b.read_bytes(), rec_s.read_bytes()
        code, said = job(*W, "--dry-run")
        assert code == 0 and "(a dry run)" in said and (rec_b.read_bytes(), rec_s.read_bytes()) == before, \
            said[-300:]
        # A try a build refuses goes again after the wait.
        lock = root / ".build.lock"
        lock.write_text("x", encoding="utf-8")
        slept = []
        BW.time = types.SimpleNamespace(time=time_.time,
                                        sleep=lambda s: (slept.append(s), lock.unlink()))
        code, said = job(*W)
        assert code == 0 and slept == [0] and "try 1 of 3 did not finish" in said and read(rec_b)["ok"], \
            said[-400:]
        BW.time = saved_time
        # Refused every time: FAILED, recorded by the backup itself.
        lock.write_text("x", encoding="utf-8")
        code, said = job(*W)
        b = read(rec_b)
        assert code == 1 and "BACKUP WEEKLY FAILED -- the backup:" in said and b["ok"] is False and \
            ".build.lock is fresh" in b["said"] and "by" not in b, (said[-300:], b)
        lock.unlink()
        # Never started, the machine's lock held: recorded by the job.
        held = root.joinpath(*CL.LOCK.split("/"))
        held.write_text("pid 1 since 05:30", encoding="utf-8")
        code, said = job(*W)
        b = read(rec_b)
        assert code == 1 and b["ok"] is False and b.get("by") == "backup_weekly.py" and \
            "is held" in b["said"], (said[-300:], b)
        held.unlink()
        news = CL.backup_news(root, dt.now())
        assert news[0].startswith("BACKUP FAILED --") and "is held" in news[0], news
        # A sample that fails: exit 1, recorded by the sample itself.
        rec_s.unlink()
        (bucket / "backup" / "Docket.txt").write_text("changed in the bucket\n", encoding="utf-8")
        code, said = job(*W)
        s = read(rec_s)
        assert code == 1 and "the sample restore:" in said and s["ok"] is False and \
            "Docket.txt" in s.get("said", ""), (said[-300:], s)
        # Only the laptop's, and only its repository's.
        os.environ["GITHUB_ACTIONS"] = "true"
        code, said = job(*W)
        assert code == 1 and "GitHub's machine" in said, said[-200:]
        os.environ.pop("GITHUB_ACTIONS")
        code, said = job("--root", str(root))
        assert code == 1 and "not the repository that holds secrets.json" in said, said[-200:]

        now = dt(2026, 11, 16, 8, 0)
        good = {"ok": True, "at": "x", "sent": 12, "sent_bytes": 3_000_000,
                "manifest": {"count": 70_000, "bytes": 46_000_000_000}, "bucket": {"kind": "r2"}}
        for days, head in ((3, "the last backup was 3 days ago"), (14, "the last backup was 14 days ago"),
                           (15, "STALE -- the last backup was 15 days ago")):
            CL.save_record(root, CL.BACKUP_RECORD, dict(good, epoch=now.timestamp() - days * 86400))
            news = CL.backup_news(root, now)
            assert news[0].startswith(head) and "12 files sent" in news[0] and \
                "70,000 files" in news[0] and "a test" not in news[0] and \
                (("more than 14 days" in news[0]) == (days == 15)), (days, news)
        rec_b.unlink()
        news = CL.backup_news(root, now)
        assert news[0].startswith("NO BACKUP on record") and "cloud.py backup" in news[0] and \
            len(news) == 2, news
    finally:
        BW.time = saved_time
        if saved_env is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = saved_env
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("the entry every Sunday with the captions inbox's settings, written for a checkout "
                  "in UTF-16 from a template naming no one's; the job backs up, samples when due, "
                  "records nothing on a dry run, tries a refused backup again, fails loudly and "
                  "records it whether or not the backup could, fails on a short sample, keeps off "
                  "GitHub and other checkouts; pull says none, good, failed and STALE past 14 days")


@check("cloud", "state has one writer, a cleared refusal stays cleared, and the "
                "night's site travels as one file", needs=("cloud",))
def _cloud_state_and_site(CL):
    """Both machines hold the state files, so a copy taken down last night is
    not news: sent back, it would put last night's census over tonight's. Here
    the laptop's stale census is left alone, a census changed on both machines
    is a failure with neither lost, and a refusal lifted from the bucket by
    clear-refusal is not sent back by the machine that still holds it -- after
    the move the bucket's copy is the one that stops a night, so refusal.py
    --clear alone would leave every night stopped.

    And the built site reaches the publish job as ONE archive in the private
    bucket rather than as a GitHub artifact, which any signed-in user could
    download from a public repository with the licensed logo in it, or as
    55,000 billed writes: every file back, byte for byte, into an empty folder
    and never over one that is not. With it travels its own night's verdict
    (7 October 2026), which the publish job deploys by: site-up sends none
    but that run's, never a dry run's, and site-down writes it where
    --deploy-to production reads it, or refuses a site that came without it.
    """
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="gr-state-"))
    try:
        bucket = tmp / "bucket"
        laptop, night, other = tmp / "laptop", tmp / "night", tmp / "other"
        for d in (laptop, night, other):
            d.mkdir()
            _cloud_fixture(d, real)
        B = ["--local-bucket", str(bucket)]

        def call(root, *argv):
            return _cloud_call(CL, *argv, "--root", str(root), *B)

        def census(root, n):
            (root / "archive/census.json").write_text(
                json.dumps({"census": {"bills": n}}), encoding="utf-8")

        def remote(key):
            f = bucket / "state" / key
            return f.read_text(encoding="utf-8") if f.exists() else None
        census(laptop, 1)
        (night / "archive/census.json").unlink()
        (other / "archive/census.json").unlink()
        assert call(laptop, "state-up")[0] == 0 and '"bills": 1' in remote("census.json")
        assert call(night, "state-down")[0] == 0
        census(night, 2)
        code, out = call(night, "state-up")
        assert code == 0 and '"bills": 2' in remote("census.json"), out[-300:]
        code, out = call(laptop, "state-up")
        assert code == 0 and '"bills": 2' in remote("census.json"), (
            "the laptop's copy of last night's census went back over tonight's")
        assert "newer" in out, out[-300:]
        assert call(laptop, "state-down")[0] == 0
        assert '"bills": 2' in (laptop / "archive/census.json").read_text(encoding="utf-8")
        census(night, 3)
        census(laptop, 4)
        assert call(night, "state-up")[0] == 0
        code, out = call(laptop, "state-up")
        assert code == 1 and '"bills": 3' in remote("census.json"), (
            "a census changed on both machines was not refused: " + out[-200:])
        kept = list(bucket.glob("replaced/*/state-conflict/census.json"))
        assert kept and '"bills": 4' in kept[0].read_text(encoding="utf-8"), \
            "the refused census was not kept"

        (night / "archive/refused.json").write_text('{"where": "docket"}', encoding="utf-8")
        assert call(night, "state-up")[0] == 0 and remote("refused.json")
        assert call(other, "state-down")[0] == 0 and (other / "archive/refused.json").exists()
        code, out = call(other, "clear-refusal")
        assert code == 0 and remote("refused.json") is None, out[-300:]
        assert list(bucket.glob("replaced/*/state/refused.json*")), \
            "clear-refusal deleted the record instead of moving it to replaced/"
        assert "refusal.py --clear" in out, "clear-refusal did not say this machine still holds one"
        code, out = call(other, "state-up")
        assert code == 0 and remote("refused.json") is None, (
            "the refusal a person cleared from the bucket was sent back to it")

        site = night / "site"
        (site / "bill" / "2026").mkdir(parents=True)
        (site / "bill" / "2026" / "hb1.html").write_text("<p>HB 1</p>", encoding="utf-8")
        (site / "assets").mkdir()
        (site / "assets" / "lockup.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)))
        # Its own night's verdict goes with it, or nothing goes.
        mine = night / CL.NIGHT_VERDICT
        code, out = call(night, "site-up", "--run", "4242")
        assert code == 1 and not (bucket / "nights").exists(), \
            "a site went up with no verdict of its night beside it"
        for other_v in ({"run_id": "4241", "kind": "nightly"},
                        {"run_id": "4242", "kind": "nightly", "asked": {"dry_run": True}}):
            mine.write_text(json.dumps(other_v), encoding="utf-8")
            code, out = call(night, "site-up", "--run", "4242")
            assert code == 1 and not (bucket / "nights").exists(), (
                "a site went up with another run's verdict, or a dry run's", other_v)
        own = {"run_id": "4242", "kind": "nightly", "publishable": True,
               "asked": {"dry_run": False}}
        mine.write_text(json.dumps(own), encoding="utf-8")
        saved_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", "DRY_RUN")}
        os.environ.update(GITHUB_ACTIONS="true", DRY_RUN="true")
        try:
            code, out = call(night, "site-up", "--run", "4242")
        finally:
            for k, val in saved_env.items():
                os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
        assert code == 1 and not (bucket / "nights").exists(), \
            "a run the workflow calls a dry run sent its site for production"
        code, out = call(night, "site-up", "--run", "4242")
        assert code == 0 and (bucket / "nights/4242/site.tar.gz").is_file(), out[-300:]
        assert len([p for p in (bucket / "nights").rglob("*") if p.is_file()]) == 2, \
            "the site did not go up as one archive and its note"
        publish = tmp / "publish"
        publish.mkdir()
        shutil.copy(night / "cloud_kit.json", publish / "cloud_kit.json")
        code, out = call(publish, "site-down", "--run", "4242")
        assert code == 0, out[-300:]
        want = {p.relative_to(site).as_posix(): p.read_bytes()
                for p in site.rglob("*") if p.is_file()}
        got = {p.relative_to(publish / "site").as_posix(): p.read_bytes()
               for p in (publish / "site").rglob("*") if p.is_file()}
        assert got == want, "the site came back different"
        assert json.loads((publish / CL.SITE_VERDICT).read_text(encoding="utf-8")) == own, \
            "site-down did not bring the night's own verdict to where the deploy reads it"
        code, out = call(publish, "site-down", "--run", "4242")
        assert code == 1 and "not empty" in out, "site-down unpacked over a site already there"
        # A site.json that carries no verdict of its run -- one sent before 7
        # October 2026, or doctored -- brings nothing down.
        note = bucket / "nights/4242/site.json"
        doc = json.loads(note.read_text(encoding="utf-8"))
        bare = tmp / "bare"
        bare.mkdir()
        shutil.copy(night / "cloud_kit.json", bare / "cloud_kit.json")
        for v in (None, {"run_id": "4241"}):
            note.write_text(json.dumps(dict(doc, verdict=v)), encoding="utf-8")
            code, out = call(bare, "site-down", "--run", "4242")
            assert code == 1 and not (bare / "site").exists() and \
                not (bare / CL.SITE_VERDICT).exists(), \
                ("site-down brought a site down without its own night's verdict", v)
        note.write_text(json.dumps(doc), encoding="utf-8")
        assert call(night, "site-up", "--run", "4242")[0] == 0
        assert list(bucket.glob("replaced/*/nights/4242/site.tar.gz*")), \
            "a second site-up for one run overwrote the first"
        assert call(night, "site-up", "--run", "../x")[0] == 1
        return "ok", ("a stale census is left, one changed on both machines is refused "
                      "and kept, a cleared refusal is not sent back, and the site goes "
                      "up and comes down as one archive, byte for byte")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check("cloud", "a dry run sends back only what it fetched -- the day's files as the export "
                "served them, their archive, its logs apart, a refusal or a hold and its own "
                "verdict -- so nothing its branch's code made reaches main's next night",
       needs=("cloud", "build_all", "snapshot_gencourt"))
def _cloud_dry_night(CL, BA, SG):
    """7 October 2026. A dry run is how code not yet on main is tried, and
    until then its kit-up sent back every file of the night's it had changed
    and its state-up every state file: the outputs a build carries forward,
    the one file of the site a build reads, the study views, the bill
    requests, the list of calendars, the livestream index, the census and the
    night's verdict -- all written by that branch's code, and all taken down
    and read by main's next night. So dev's code reached production a night
    later with no merge. Now a dry night (--dry-night, or the workflow's
    DRY_RUN on GitHub's machine whatever a step passes, or there a ref other
    than main alone -- every run off main is a dry run, the person's decision
    of 7 October 2026) sends back only what the run fetched, as
    cloud_kit.json's "dry_run" names it:

      - the real kit's: of the night's files, only the archive's copy of
        what the export served -- a blob of the store, new since kit-down,
        whose bytes are what its name says -- and never a day's file, the
        archive's index, its day records or the database nights' copies; and
        of the state a refusal, a hold on the SQL host and its own verdict,
        never the census, the night's verdict, the week's or the first-seen
        ledger (since 7 October 2026, follow_changes.py) -- and no night
        file else
      - driven on a folder bucket: the blob of tonight's docket goes up, and
        the docket the run installed, the archive's index and day records,
        from-db/, a blob kit-down brought and one whose bytes are not its
        name all stay; a carried output, the bill requests and a removal stay
        as they were; the logs go to logs/<day>/dry-run/, which pull does not
        take; the census, the night's verdict and the first-seen ledger stay
        as they were while a refusal and the dry run's own verdict go up; and
        the next real night takes down main's outputs and main's docket, with
        tonight's blob

    THE REVIEW OF 7 OCTOBER 2026. Until then a dry night also sent the day's
    files as the run installed them, wherever the store held their bytes, and
    the archive's index.json and snapshots/<day>/ records: a branch that wrote
    the index in its own shape put that shape before main's next snapshot,
    which opens it and appends to it, and one that put an older docket back
    sent it to kit/, since the store holds every file the export ever served.
    """
    import contextlib
    import gzip
    import hashlib
    import io
    real = CL.load_kit(".")
    d = real.get("dry_run") or {}
    day_files = [f for f in list(SG.FILES) + [n for _, n in SG.EXTRA] if CL.owner_of(real, f)]
    assert d and "served" not in d and d.get("store") == "nh-archive/store" and \
        d.get("globs") == ["nh-archive/store/*"], (
            f"{CL.KIT_FILE}'s dry_run sends more than the archive's copies of what the export "
            "served: a day's file, the archive's index or its day records are its branch's "
            f"code's choice ({d.get('served')}, {d.get('globs')})")
    # A refusal, a hold, and a dry run's own verdict -- the night's or, since a
    # weekly off main is one too, the week's -- and never the census, the
    # night's verdict or the week's (7 October 2026), nor the first-seen
    # ledger of what the email sender has been told is new (follow_changes.py).
    assert set(d.get("state", [])) == {"refused.json", "sql-held.json", "last-dry-run.json",
                                       "last-dry-weekly.json"} and \
        set(CL.DRY_NEVER) == {"census.json", "last-night.json", "last-weekly.json",
                              "first-seen.json", "api-hashes.json"}, \
        (d.get("state"), CL.DRY_NEVER)
    # Every night file a dry night sends is an archived copy of what was served.
    store_sha = hashlib.sha256(b"x").hexdigest()
    blob = "nh-archive/store/" + store_sha + ".gz"
    samples = [p for e in real["kit"] if e["owner"] == "night" for p in e.get("paths", [])]
    samples += [re.sub(r"\*+", "x", g) for e in real["kit"] if e["owner"] == "night"
                for g in e.get("globs", [])]
    samples += [c[0] for c in BA.CARRIED] + day_files + [
        "nh-archive/from-db/2026-10-07/Docket.txt.gz", "nh-archive/from-db/2026-10-07/source.json",
        "nh-archive/snapshots/2026-10-07/manifest.json",
        "nh-archive/snapshots/2026-10-07/install.json",
        "nh-archive/snapshots/2026-10-07/Docket.txt.sha256", blob, "nh-archive/index.json"]
    tmp = Path(tempfile.mkdtemp(prefix="gr-drynight-"))
    try:
        (tmp / "nh-archive/store").mkdir(parents=True)
        with gzip.open(tmp / blob, "wb") as fh:
            fh.write(b"x")
        sent = sorted(r for r in set(samples) if CL.owner_of(real, r) == "night"
                      and CL.dry_sends(real, tmp, r, {}))
        # ... and not when kit-down brought it, or its bytes are not its name.
        brought = CL.dry_sends(real, tmp, blob, {blob: [1, store_sha, 0]})
        with gzip.open(tmp / blob, "wb") as fh:
            fh.write(b"y")
        misnamed = CL.dry_sends(real, tmp, blob, {})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert sent == [blob] and not brought and not misnamed, (
        "a dry night would send a night file its branch's code made or chose -- a day's file, "
        "the archive's index or day records, from-db/ -- or an archive copy kit-down brought "
        "or whose bytes are not its name", sent, brought, misnamed)
    must_stay = [c[0] for c in BA.CARRIED if CL.owner_of(real, c[0]) == "night"] + [
        "site/committees.json", "lsrs.json", "archive/queue.csv", "db/StatStudMeetings.psv",
        "db/_manifest.json", "videos_house_livestreams.csv", "committees.json"]
    assert {"narratives.json", "proceedings.csv"} <= set(must_stay) and \
        not [r for r in must_stay if r in sent], [r for r in must_stay if r in sent]

    # Driven, on a folder bucket. The workflow's word alone makes it a dry night.
    tmp = Path(tempfile.mkdtemp(prefix="gr-drynight-"))
    saved_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", CL.DRY_ENV, CL.REF_ENV)}
    try:
        bucket = tmp / "bucket"
        kit = {"kit": [
            {"what": "day", "owner": "night", "paths": ["Docket.txt"]},
            {"what": "outputs", "owner": "night", "paths": ["narratives.json", "lsrs.json"]},
            {"what": "archive", "owner": "night", "held": False, "globs": ["nh-archive/**"]},
            {"what": "pages", "owner": "laptop", "globs": ["legislation/**"]}],
            "state": [{"path": f"archive/{k}", "key": k, "what": "x"} for k in
                      ("census.json", "refused.json", "sql-held.json", "last-night.json",
                       "last-dry-run.json", "first-seen.json")],
            "logs": {"globs": ["logs/*", "reports/gc-changes-*.md"]},
            "dry_run": {"store": "nh-archive/store", "globs": ["nh-archive/store/*"],
                        "state": ["refused.json", "sql-held.json", "last-dry-run.json"]},
            "backup": real["backup"], "never": real["never"]}

        def machine(name, files=None):
            root = tmp / name
            root.mkdir()
            (root / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")
            for rel, body in (files or {}).items():
                f = root.joinpath(*rel.split("/"))
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))
            return root

        def call(root, *argv):
            return _cloud_call(CL, *argv, "--root", str(root), "--local-bucket", str(bucket))

        def remote(key):
            f = bucket.joinpath(*key.split("/"))
            return f.read_bytes() if f.is_file() else None

        def gz(data):
            return gzip.compress(data, mtime=0)

        D1 = b"2025|0001|HB1|introduced\n"
        sha1 = hashlib.sha256(D1).hexdigest()
        laptop = machine("laptop", {
            "Docket.txt": D1, "narratives.json": "{\"main\": 1}", "lsrs.json": "[]",
            "nh-archive/index.json": "{}", f"nh-archive/store/{sha1}.gz": gz(D1),
            "nh-archive/snapshots/2026-10-01/manifest.json": "{}",
            "legislation/2026/HB1.html": "<p>1</p>",
            "archive/census.json": "{\"census\": {\"bills\": 100}}",
            "archive/first-seen.json": "{\"format\": 1, \"main\": 1}",
            "archive/last-night.json": "{\"run_id\": \"700\", \"kind\": \"nightly\"}"})
        assert call(laptop, "seed-kit")[0] == 0 and call(laptop, "state-up")[0] == 0
        census, night_v = remote("state/census.json"), remote("state/last-night.json")
        ledger = remote("state/first-seen.json")
        assert census and night_v and ledger

        # A dry run that fetched: the export's docket, archived and installed;
        # and everything its own code made, chose or changed beside it -- the
        # archive's index in a shape of its own, its day records, a blob kit-down
        # brought rewritten, and one whose bytes are not its name.
        dry = machine("dry")
        assert call(dry, "state-down")[0] == 0 and call(dry, "kit-down")[0] == 0
        D2 = D1 + b"2025|0002|HB2|introduced\n"
        sha2 = hashlib.sha256(D2).hexdigest()
        liar = hashlib.sha256(b"what the name says").hexdigest()
        today = f"{__import__('datetime').datetime.now():%Y-%m-%d}"
        for rel, body in (("Docket.txt", D2), (f"nh-archive/store/{sha2}.gz", gz(D2)),
                          (f"nh-archive/store/{liar}.gz", gz(b"something else")),
                          (f"nh-archive/store/{sha1}.gz", gz(D1 + b"rewritten")),
                          ("nh-archive/index.json", b"{\"DEV-SHAPE\": true}"),
                          (f"nh-archive/snapshots/{today}/manifest.json", b"{}"),
                          (f"nh-archive/snapshots/{today}/install.json", b"{\"by\": \"dev\"}"),
                          (f"nh-archive/from-db/{today}/Docket.txt.gz", b"dev's rebuild"),
                          ("narratives.json", b"{\"dev\": 1}"), ("lsrs.json", b"[1]"),
                          (f"logs/nightly-{today}.log", b"the dry run's log"),
                          (f"reports/gc-changes-{today}.md", b"what the dry run saw"),
                          ("archive/census.json", b"{\"census\": {\"bills\": 1}}"),
                          ("archive/first-seen.json", b"{\"format\": 1, \"dev\": 1}"),
                          ("archive/last-night.json", b"{\"run_id\": \"701\"}"),
                          ("archive/last-dry-run.json", b"{\"run_id\": \"701\"}"),
                          ("archive/refused.json", b"{\"where\": \"docket\"}")):
            f = dry.joinpath(*rel.split("/"))
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(body)
        (dry / "nh-archive/snapshots/2026-10-01/manifest.json").unlink()   # stays undone
        os.environ.update(GITHUB_ACTIONS="true", **{CL.DRY_ENV: "true"})
        code, out = call(dry, "kit-up")
        assert code == 0, out[-400:]
        assert remote(f"kit/nh-archive/store/{sha2}.gz") == gz(D2), \
            "a dry run's fetch -- the archive's copy of the export's docket -- did not go back"
        assert remote("kit/Docket.txt") == D1 and \
            remote("kit/nh-archive/index.json") == b"{}" and \
            remote(f"kit/nh-archive/snapshots/{today}/manifest.json") is None and \
            remote(f"kit/nh-archive/snapshots/{today}/install.json") is None and \
            remote(f"kit/nh-archive/store/{sha1}.gz") == gz(D1) and \
            remote(f"kit/nh-archive/store/{liar}.gz") is None, (
                "a dry run sent back what its code chose -- the docket it installed, the "
                "archive's index or day records -- or an archive copy kit-down brought, or one "
                "whose bytes are not its name: main's next night would install, append to or "
                "read it")
        assert remote("kit/narratives.json") == b"{\"main\": 1}" and \
            remote("kit/lsrs.json") == b"[]" and \
            remote(f"kit/nh-archive/from-db/{today}/Docket.txt.gz") is None and \
            remote("kit/nh-archive/snapshots/2026-10-01/manifest.json") == b"{}", (
                "a dry run sent back what its own code made, or removed a kit file: main's next "
                "night would build from it")
        assert remote(f"logs/{today}/{CL.DRY_LOGS}/nightly-{today}.log") and \
            remote(f"logs/{today}/{CL.DRY_LOGS}/gc-changes-{today}.md") and \
            remote(f"logs/{today}/nightly-{today}.log") is None, \
            "a dry run's logs went where pull takes the night's"
        assert remote("state/census.json") == census and \
            remote("state/last-night.json") == night_v and \
            remote("state/last-dry-run.json") == b"{\"run_id\": \"701\"}" and \
            remote("state/refused.json"), (
                "a dry run's state-up sent the census or the night's verdict, or kept back its "
                "own verdict or a refusal")
        assert remote("state/first-seen.json") == ledger, (
            "a dry run sent back the first-seen ledger its branch's build left: main's next "
            "night would read dev's idea of what the email sender has been told")
        assert "kept back" in out and "narratives.json" in out, out[-600:]

        # A database night's docket, rebuilt by the run's own code, stays too.
        (dry / "Docket.txt").write_bytes(D2 + b"2025|0003|HB3|from the database\n")
        code, out = call(dry, "kit-up")
        assert code == 0 and remote("kit/Docket.txt") == D1, \
            "a dry run sent back day files its own code rebuilt from the database"
        # ... and state-up alone, under the word, sends the same and no more.
        (dry / "archive/sql-held.json").write_bytes(b"{\"held\": true}")
        assert call(dry, "state-up")[0] == 0 and remote("state/sql-held.json") and \
            remote("state/census.json") == census and remote("state/last-night.json") == night_v \
            and remote("state/first-seen.json") == ledger
        os.environ.pop(CL.DRY_ENV, None)
        # ... and the ref alone: a run of dev with Dry run unticked, no DRY_RUN
        # and no --dry-night, is a dry night all the same (7 October 2026, the
        # person's decision: until then it sent back everything dev's code
        # made, the census and the night's verdict with it), and sends no site
        # for production.
        os.environ[CL.REF_ENV] = "refs/heads/dev"
        (dry / "narratives.json").write_bytes(b"{\"dev\": 2}")
        (dry / "archive/census.json").write_bytes(b"{\"census\": {\"bills\": 2}}")
        (dry / "archive/last-night.json").write_bytes(b"{\"run_id\": \"702\"}")
        (dry / "archive/first-seen.json").write_bytes(b"{\"format\": 1, \"dev\": 2}")
        code, out = call(dry, "kit-up")
        assert code == 0 and remote("kit/narratives.json") == b"{\"main\": 1}" and \
            remote("state/census.json") == census and remote("state/last-night.json") == night_v \
            and remote("state/first-seen.json") == ledger and "a dry run" in out, (
                "a kit-up on GitHub's machine for a run of dev with Dry run unticked sent back "
                "what dev's code made, the census, the night's verdict or the first-seen ledger",
                out[-400:])
        # ... with a built site here and its night's verdict beside it, so
        # that only the ref can be what refuses it. (THE REVIEW OF 7 OCTOBER
        # 2026: with no site here, "no built site" refused it whatever
        # site-up made of the ref.)
        (dry / "site").mkdir()
        (dry / "site" / "index.html").write_bytes(b"<p>dev's build</p>")
        (dry / CL.FIRST_SEEN_NEXT).write_bytes(b"{\"format\": 1, \"dev\": 3}")
        code, out = call(dry, "site-up", "--run", "702")
        assert code == 1 and "sends no site for production" in out and \
            not (bucket / "nights").exists(), (
                "a run of a branch other than main sent its site, or the first-seen ledger its "
                "build left, for production, or was refused for something else", out[-300:])
        shutil.rmtree(dry / "site")
        (dry / CL.FIRST_SEEN_NEXT).unlink()
        os.environ[CL.REF_ENV] = CL.MAIN_REF
        # A New term run ticked with Dry run (the box is ticked unless a person
        # unticks it) is refused by nightly.py, and the workflow still gives its
        # kit-up --hold: nothing is held, nothing of the kit goes back -- not
        # even a day file the export served -- and its logs still go up, apart
        # (the review of 7 October 2026: this failed, and the logs were lost).
        D3 = D2 + b"2025|0004|HB4|introduced\n"
        sha3 = hashlib.sha256(D3).hexdigest()
        (dry / "Docket.txt").write_bytes(D3)
        (dry / f"nh-archive/store/{sha3}.gz").write_bytes(gz(D3))
        (dry / f"logs/refused-{today}.log").write_bytes(b"the refused New term run's log")
        code, out = call(dry, "kit-up", "--dry-night", "--hold", "9")
        assert code == 0 and remote("kit/Docket.txt") == D1 and \
            remote(f"kit/nh-archive/store/{sha3}.gz") is None and \
            not (bucket / "nights").exists() and \
            remote(f"logs/{today}/{CL.DRY_LOGS}/refused-{today}.log") and \
            remote("state/census.json") == census and \
            remote("state/last-night.json") == night_v, (
                "a dry night given --hold held or sent something of the kit, or failed and "
                "lost its logs", out[-500:])

        # The logs it sent are not taken by pull for the night's.
        b = CL.make_bucket(str(bucket), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            taken = CL.pull_logs(b, laptop, CL.load_kit(laptop), [today], False, {}, set(), True,
                                 today)[0]
        assert not taken, f"pull took a dry run's logs for the night's: {sorted(taken)}"

        # The next real night takes down main's outputs, main's docket and
        # index, and the archive's copy of what the dry run fetched.
        os.environ.pop("GITHUB_ACTIONS", None)
        nxt = machine("next")
        assert call(nxt, "kit-down")[0] == 0
        assert (nxt / "narratives.json").read_bytes() == b"{\"main\": 1}" and \
            (nxt / "Docket.txt").read_bytes() == D1 and \
            (nxt / "nh-archive/index.json").read_bytes() == b"{}" and \
            (nxt / f"nh-archive/store/{sha2}.gz").read_bytes() == gz(D2), \
            "main's next night took down what a dry run's code made or chose, or lost what it fetched"
        # A real night's kit-up still sends what its night changed.
        (nxt / "narratives.json").write_bytes(b"{\"main\": 2}")
        assert call(nxt, "kit-up")[0] == 0 and remote("kit/narratives.json") == b"{\"main\": 2}"
    finally:
        for k, val in saved_env.items():
            os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a dry night sends the archive's copy of what the export served, new and read "
                  "against its name, its logs under dry-run/, a refusal, a hold and its own "
                  f"verdict; the {len(day_files)} day files it installed, the archive's index "
                  "and day records, from-db/, a carried output, the bill requests, a removal, "
                  "the census, the night's verdict and the first-seen ledger stay, and the next "
                  "night takes down main's")


@check("cloud", "the first-seen ledger travels as the census does: in the night's state, never "
                "from a dry run, and with a New term run's site to the publish job, whole or not "
                "at all", needs=("cloud", "nightly", "follow_changes"))
def _first_seen_travels(CL, NI, FC):
    """7 October 2026. The ledger of what the changes files have told the
    email sender is new (follow_changes.py) is carried between nights the way
    archive/census.json is: in cloud_kit.json's state list, under one name in
    the three programs that handle it, and never among what a dry run may send
    (DRY_NEVER, which load_kit holds the kit's "dry_run" to). A New term run's
    is kept only when its deploy lands, on the publish job's machine, so
    site-up sends the ledger the night's build left beside its site and
    site-down brings it back to where nightly.py keeps it -- byte for byte,
    or the site-down fails before the verdict that would let it deploy."""
    assert FC.LEDGER.as_posix() == NI.FIRST_SEEN.as_posix() == "archive/first-seen.json" and \
        FC.CANDIDATE.as_posix() == NI.FIRST_SEEN_NEXT.as_posix() == CL.FIRST_SEEN_NEXT, (
            "follow_changes, nightly and cloud name the ledger differently",
            FC.LEDGER, NI.FIRST_SEEN, FC.CANDIDATE, NI.FIRST_SEEN_NEXT, CL.FIRST_SEEN_NEXT)
    real = CL.load_kit(".")
    state = {s["key"]: s["path"] for s in real.get("state", [])}
    assert state.get("first-seen.json") == NI.FIRST_SEEN.as_posix(), \
        f"{CL.KIT_FILE}'s state list does not carry the first-seen ledger: {sorted(state)}"
    assert "first-seen.json" in CL.DRY_NEVER and \
        "first-seen.json" not in (real.get("dry_run") or {}).get("state", []), CL.DRY_NEVER
    tmp = Path(tempfile.mkdtemp(prefix="gr-firstseen-"))
    try:
        bad = json.loads(json.dumps(real))
        bad["dry_run"]["state"] = list(bad["dry_run"]["state"]) + ["first-seen.json"]
        (tmp / "cloud_kit.json").write_text(json.dumps(bad), encoding="utf-8")
        try:
            CL.load_kit(tmp)
            refused = False
        except CL.Failed:
            refused = True
        assert refused, f"a {CL.KIT_FILE} whose dry run sends the first-seen ledger was taken"
        (tmp / "cloud_kit.json").unlink()

        bucket = tmp / "bucket"
        night, publish, bare = tmp / "night", tmp / "publish", tmp / "bare"
        night.mkdir()
        _cloud_fixture(night, real)
        shutil.rmtree(night / "site")
        for d in (publish, bare):
            d.mkdir()
            shutil.copy(night / "cloud_kit.json", d / "cloud_kit.json")
        B = ["--local-bucket", str(bucket)]

        def call(root, *argv):
            return _cloud_call(CL, *argv, "--root", str(root), *B)
        site = night / "site"
        (site / "changes").mkdir(parents=True)
        (site / "changes" / "current.json").write_text("{}", encoding="utf-8")
        (night / CL.NIGHT_VERDICT).write_text(json.dumps(
            {"run_id": "4242", "kind": "nightly", "publishable": True,
             "asked": {"dry_run": False, "new_term": True}}), encoding="utf-8")
        ledger = b'{"format": 1, "date": "2026-12-02", "sitting_term": "2027-2028"}\n'
        (night / CL.FIRST_SEEN_NEXT).write_bytes(ledger)
        # A dry run's -- by the workflow's word, or as every run off main is,
        # by its ref alone -- goes nowhere: site-up refuses it, ledger and all.
        saved_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", CL.DRY_ENV, CL.REF_ENV)}
        try:
            for env in ({CL.DRY_ENV: "true", CL.REF_ENV: CL.MAIN_REF},
                        {CL.REF_ENV: "refs/heads/dev"}):
                for k in saved_env:
                    os.environ.pop(k, None)
                os.environ.update(GITHUB_ACTIONS="true", **env)
                code, out = call(night, "site-up", "--run", "4242")
                assert code == 1 and not (bucket / "nights").exists(), \
                    ("a dry run sent its site, or the ledger its build left, for production",
                     env, out[-300:])
        finally:
            for k, val in saved_env.items():
                os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
        code, out = call(night, "site-up", "--run", "4242")
        assert code == 0 and (bucket / "nights/4242/first-seen.json").read_bytes() == ledger, \
            ("site-up did not send the ledger the night's build left beside its site", out[-300:])
        code, out = call(publish, "site-down", "--run", "4242")
        assert code == 0 and (publish / CL.FIRST_SEEN_NEXT).read_bytes() == ledger and \
            (publish / CL.SITE_VERDICT).is_file(), \
            ("site-down did not bring the ledger back to where nightly.py keeps it", out[-300:])
        # One that is not the ledger site.json names stops the site-down
        # before the verdict that would let the publish job deploy.
        (bucket / "nights/4242/first-seen.json").write_bytes(ledger.replace(b"2027", b"2025"))
        code, out = call(bare, "site-down", "--run", "4242")
        assert code == 1 and not (bare / CL.FIRST_SEEN_NEXT).exists() and \
            not (bare / CL.SITE_VERDICT).exists(), \
            ("site-down took a ledger that is not the one its night sent", out[-300:])
        # A night that left none sends none, and its site comes down without.
        (night / CL.FIRST_SEEN_NEXT).unlink()
        (night / CL.NIGHT_VERDICT).write_text(json.dumps(
            {"run_id": "4243", "kind": "nightly", "publishable": True,
             "asked": {"dry_run": False}}), encoding="utf-8")
        assert call(night, "site-up", "--run", "4243")[0] == 0 and \
            not (bucket / "nights/4243/first-seen.json").exists()
        shutil.rmtree(publish / "site")
        (publish / CL.FIRST_SEEN_NEXT).unlink()
        code, out = call(publish, "site-down", "--run", "4243")
        assert code == 0 and not (publish / CL.FIRST_SEEN_NEXT).exists(), out[-300:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("one name in follow_changes, nightly, cloud and the kit's state list; never a "
                  "dry run's to send, by its box or off main; with a New term run's site to the "
                  "publish job byte for byte, a changed one refused before the verdict, none "
                  "where none was left")


@check("cloud", "the data API's hashes travel as the first-seen ledger does: in the night's state, "
                "never from a dry run, and with a New term run's site to the publish job, whole or "
                "not at all", needs=("cloud", "nightly", "api_records"))
def _api_hashes_travel(CL, NI, AR):
    """16 November 2026. What the API's change feed compares each night with
    (api_records.py) is carried between nights as the first-seen ledger is
    (_first_seen_travels): in cloud_kit.json's state list, under one name in
    the three programs that handle it, never among what a dry run may send
    (DRY_NEVER, which load_kit holds the kit's "dry_run" to), and a New term
    run's beside its site to the publish job, where nightly.py keeps it once
    the deploy lands -- byte for byte, or the site-down fails before the
    verdict that would let it deploy."""
    assert AR.LEDGER.as_posix() == NI.API_HASHES.as_posix() == "archive/api-hashes.json" and \
        AR.CANDIDATE.as_posix() == NI.API_HASHES_NEXT.as_posix() == CL.API_HASHES_NEXT, (
            "api_records, nightly and cloud name the hashes differently",
            AR.LEDGER, NI.API_HASHES, AR.CANDIDATE, NI.API_HASHES_NEXT, CL.API_HASHES_NEXT)
    real = CL.load_kit(".")
    state = {s["key"]: s["path"] for s in real.get("state", [])}
    assert state.get("api-hashes.json") == NI.API_HASHES.as_posix(), \
        f"{CL.KIT_FILE}'s state list does not carry the data API's hashes: {sorted(state)}"
    assert "api-hashes.json" in CL.DRY_NEVER and \
        "api-hashes.json" not in (real.get("dry_run") or {}).get("state", []), CL.DRY_NEVER
    tmp = Path(tempfile.mkdtemp(prefix="gr-apihashes-"))
    try:
        bad = json.loads(json.dumps(real))
        bad["dry_run"]["state"] = list(bad["dry_run"]["state"]) + ["api-hashes.json"]
        (tmp / "cloud_kit.json").write_text(json.dumps(bad), encoding="utf-8")
        try:
            CL.load_kit(tmp)
            refused = False
        except CL.Failed:
            refused = True
        assert refused, f"a {CL.KIT_FILE} whose dry run sends the data API's hashes was taken"
        (tmp / "cloud_kit.json").unlink()

        bucket = tmp / "bucket"
        night, publish, bare = tmp / "night", tmp / "publish", tmp / "bare"
        night.mkdir()
        _cloud_fixture(night, real)
        shutil.rmtree(night / "site")
        for d in (publish, bare):
            d.mkdir()
            shutil.copy(night / "cloud_kit.json", d / "cloud_kit.json")
        B = ["--local-bucket", str(bucket)]

        def call(root, *argv):
            return _cloud_call(CL, *argv, "--root", str(root), *B)
        site = night / "site"
        (site / "api").mkdir(parents=True)
        (site / "api" / "index.json").write_text("{}", encoding="utf-8")
        (night / CL.NIGHT_VERDICT).write_text(json.dumps(
            {"run_id": "4252", "kind": "nightly", "publishable": True,
             "asked": {"dry_run": False, "new_term": True}}), encoding="utf-8")
        hashes = b'{"format": 1, "date": "2026-12-02", "hashes": {"bills": {}}, "nights": {}}\n'
        (night / CL.API_HASHES_NEXT).write_bytes(hashes)
        saved_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", CL.DRY_ENV, CL.REF_ENV)}
        try:
            for env in ({CL.DRY_ENV: "true", CL.REF_ENV: CL.MAIN_REF},
                        {CL.REF_ENV: "refs/heads/dev"}):
                for k in saved_env:
                    os.environ.pop(k, None)
                os.environ.update(GITHUB_ACTIONS="true", **env)
                code, out = call(night, "site-up", "--run", "4252")
                assert code == 1 and not (bucket / "nights").exists(), \
                    ("a dry run sent its site, or the hashes its build left, for production",
                     env, out[-300:])
        finally:
            for k, val in saved_env.items():
                os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
        code, out = call(night, "site-up", "--run", "4252")
        sent = bucket / "nights/4252/api-hashes.json"
        assert code == 0 and sent.is_file() and sent.read_bytes() == hashes, \
            ("site-up did not send the hashes the night's build left beside its site", out[-300:])
        code, out = call(publish, "site-down", "--run", "4252")
        assert code == 0 and (publish / CL.API_HASHES_NEXT).read_bytes() == hashes and \
            (publish / CL.SITE_VERDICT).is_file(), \
            ("site-down did not bring the hashes back to where nightly.py keeps them", out[-300:])
        (bucket / "nights/4252/api-hashes.json").write_bytes(hashes.replace(b"2026", b"2025"))
        code, out = call(bare, "site-down", "--run", "4252")
        assert code == 1 and not (bare / CL.API_HASHES_NEXT).exists() and \
            not (bare / CL.SITE_VERDICT).exists(), \
            ("site-down took hashes that are not the ones its night sent", out[-300:])
        (night / CL.API_HASHES_NEXT).unlink()
        (night / CL.NIGHT_VERDICT).write_text(json.dumps(
            {"run_id": "4253", "kind": "nightly", "publishable": True,
             "asked": {"dry_run": False}}), encoding="utf-8")
        assert call(night, "site-up", "--run", "4253")[0] == 0 and \
            not (bucket / "nights/4253/api-hashes.json").exists()
        shutil.rmtree(publish / "site")
        (publish / CL.API_HASHES_NEXT).unlink()
        code, out = call(publish, "site-down", "--run", "4253")
        assert code == 0 and not (publish / CL.API_HASHES_NEXT).exists(), out[-300:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("one name in api_records, nightly, cloud and the kit's state list; never a dry "
                  "run's to send, by its box or off main; with a New term run's site to the "
                  "publish job byte for byte, a changed one refused before the verdict, none where "
                  "none was left")


@check("cloud", "a weekly off main sends back none of the lists it took -- only its logs, apart, "
                "a refusal or a hold and its own verdict, never the week's -- and pull says its "
                "verdict is a dry run's", needs=("cloud", "nightly"))
def _cloud_dry_weekly(CL, NI):
    """7 OCTOBER 2026. A run of the weekly by hand on dev -- one ran that
    day, fetching -- sent every list it took back to the kit with kit-up (the
    committee rosters, the members who have left, the committee list, the
    study committees' views) and its verdict to state/last-weekly.json with
    state-up, and main's next night took them down and built from them. The
    weekly has no Dry run box. Every run of it off main is now a dry run (the
    person's decision), and cloud.py's dry night is the weekly's too:

      - the real kit's: each file the weekly takes is a night's file that a
        dry night keeps back; its verdict, archive/last-dry-weekly.json, is
        in the state list and among what a dry night sends, the week's own
        is never sent by one (DRY_NEVER), and pull brings it to
        archive/cloud/
      - driven on a folder bucket, on GitHub's machine for a run of dev with
        no DRY_RUN at all: the lists it took stay out of kit/; its log and its
        change list go to logs/<day>/dry-run/, which pull does not take; a
        refusal and a hold on the SQL host go up, since they hold every lane
        whichever branch met them; its own verdict goes up, while the week's
        and the census stay as the last real runs left them; the workflow's
        word alone does the same; pull says the verdict is a dry run of the
        weekly's; and the same week on main sends its lists and its verdict
        as it always did
    """
    import contextlib
    import io
    from datetime import date, datetime
    real = CL.load_kit(".")
    d = real.get("dry_run") or {}
    state = {s["key"]: s["path"] for s in real.get("state", [])}
    assert state.get("last-dry-weekly.json") == NI.WEEKLY_DRY_VERDICT.as_posix() and \
        state.get("last-weekly.json") == NI.WEEKLY_VERDICT.as_posix() and \
        "last-dry-weekly.json" in d.get("state", []) and "last-weekly.json" in CL.DRY_NEVER and \
        CL.VERDICTS.get("last-dry-weekly.json") == f"{CL.LOCAL}/last-dry-weekly.json", (
            "a dry weekly's verdict is not carried to the bucket and back beside the week's, or "
            "the week's is not one a dry night never sends", state, d.get("state"), CL.DRY_NEVER)
    weekly_files = (["data/committee_members.json", "former_members.json", "committees.json",
                     "db/_manifest.json"] + [f"db/{x}.psv" for x in NI.STUDY_WEEKLY])
    sent = [r for r in weekly_files if CL.owner_of(real, r) != "night"
            or CL.dry_sends(real, Path("."), r, {})]
    assert not sent, ("a dry night would send back a list the weekly takes, or the weekly takes "
                      "a file the kit does not give the night", sent)

    tmp = Path(tempfile.mkdtemp(prefix="gr-dryweek-"))
    saved_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", CL.DRY_ENV, CL.REF_ENV)}
    try:
        for k in saved_env:
            os.environ.pop(k, None)
        bucket = tmp / "bucket"
        keys = ("census.json", "refused.json", "sql-held.json", "last-night.json",
                "last-weekly.json", "last-dry-run.json", "last-dry-weekly.json")
        lists = ["data/committee_members.json", "committees.json", "former_members.json",
                 "db/StatStudMembers.psv"]
        kit = {"kit": [
            {"what": "day", "owner": "night", "paths": ["Docket.txt"]},
            {"what": "weekly", "owner": "night", "paths": lists},
            {"what": "archive", "owner": "night", "held": False, "globs": ["nh-archive/**"]}],
            "state": [{"path": f"archive/{k}", "key": k, "what": "x"} for k in keys],
            "logs": {"globs": ["logs/*", "reports/gc-changes-*.md"]},
            "dry_run": {"store": "nh-archive/store", "globs": ["nh-archive/store/*"],
                        "state": ["refused.json", "sql-held.json", "last-dry-run.json",
                                  "last-dry-weekly.json"]},
            "backup": real["backup"], "never": real["never"]}

        def put(root, files):
            for rel, body in files.items():
                f = root.joinpath(*rel.split("/"))
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(body if isinstance(body, bytes) else body.encode("utf-8"))

        def machine(name, files=None):
            root = tmp / name
            root.mkdir()
            (root / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")
            put(root, files or {})
            return root

        def call(root, *argv):
            return _cloud_call(CL, *argv, "--root", str(root), "--local-bucket", str(bucket))

        def remote(key):
            f = bucket.joinpath(*key.split("/"))
            return f.read_bytes() if f.is_file() else None

        mains = {"data/committee_members.json": b"{\"H01\": [1, 2, 3]}",
                 "committees.json": b"{\"H\": [1]}", "former_members.json": b"{\"1\": {}}",
                 "db/StatStudMembers.psv": b"a|1\n"}
        laptop = machine("laptop", dict(mains, **{
            "Docket.txt": "2025|0001|HB1|introduced\n", "nh-archive/index.json": "{}",
            "archive/census.json": "{\"census\": {\"bills\": 100}}",
            "archive/last-weekly.json": "{\"run_id\": \"800\", \"kind\": \"weekly\"}"}))
        assert call(laptop, "seed-kit")[0] == 0 and call(laptop, "state-up")[0] == 0
        census, week_v = remote("state/census.json"), remote("state/last-weekly.json")
        assert census and week_v

        # Sunday's fetches on dev: GitHub's machine and the ref, and nothing else.
        day = f"{datetime.now():%Y-%m-%d}"
        wk = machine("week")
        assert call(wk, "state-down")[0] == 0 and call(wk, "kit-down")[0] == 0
        dry_v = json.dumps({"run_id": "801", "kind": "weekly", "day": day, "clean": True,
                            "asked": {"dry_run": True}}).encode("utf-8")
        put(wk, {"data/committee_members.json": "{\"H01\": [1, 2, 3, 99]}",
                 "committees.json": "{\"H\": [1, 2]}",
                 "former_members.json": "{\"1\": {}, \"777\": {}}",
                 "db/StatStudMembers.psv": "a|1\nb|2\n",
                 f"logs/weekly-{day}.log": "the dev weekly's log",
                 f"reports/gc-changes-weekly-{day}.md": "what the dev weekly saw",
                 "archive/last-dry-weekly.json": dry_v,
                 "archive/last-weekly.json": "{\"run_id\": \"801\"}",
                 "archive/census.json": "{\"census\": {\"bills\": 1}}",
                 "archive/refused.json": "{\"where\": \"fetch_committees\"}",
                 "archive/sql-held.json": "{\"held\": true}"})
        os.environ.update(GITHUB_ACTIONS="true", **{CL.REF_ENV: "refs/heads/dev"})
        code, out = call(wk, "kit-up")
        assert code == 0, out[-400:]
        assert all(remote(f"kit/{r}") == body for r, body in mains.items()), (
            "a weekly of dev sent back a list it took, which main's next night would build from",
            {r: remote(f"kit/{r}") for r in mains})
        assert remote(f"logs/{day}/{CL.DRY_LOGS}/weekly-{day}.log") and \
            remote(f"logs/{day}/{CL.DRY_LOGS}/gc-changes-weekly-{day}.md") and \
            remote(f"logs/{day}/weekly-{day}.log") is None, \
            "a weekly of dev's logs went where pull takes the week's, or did not go"
        assert remote("state/refused.json") and remote("state/sql-held.json"), \
            "a refusal or a hold a weekly of dev met did not go up, so would not hold the next night"
        assert remote("state/last-dry-weekly.json") == dry_v and \
            remote("state/last-weekly.json") == week_v and remote("state/census.json") == census, \
            "a weekly of dev sent the week's verdict or the census, or kept back its own"
        # The workflow's word alone (weekly.yml sets it on dev) does the same.
        os.environ[CL.REF_ENV] = CL.MAIN_REF
        os.environ[CL.DRY_ENV] = "true"
        put(wk, {"committees.json": "{\"H\": [1, 2, 3]}"})
        code, out = call(wk, "state-up")
        assert code == 0 and remote("state/last-weekly.json") == week_v, out[-300:]
        code, out = call(wk, "kit-up")
        assert code == 0 and remote("kit/committees.json") == mains["committees.json"], out[-300:]
        os.environ.pop(CL.DRY_ENV, None)

        # The laptop's pull: the dry weekly's verdict, apart and said to be
        # one; the week's as it was; its logs left in the bucket.
        b = CL.make_bucket(str(bucket), 1)
        with contextlib.redirect_stdout(io.StringIO()):
            said, _ = CL.pull_verdicts(b, laptop, False, date.today())
            taken = CL.pull_logs(b, laptop, CL.load_kit(laptop), [day], False, {}, set(), True,
                                 day)[0]
        assert any(ln.startswith("last-dry-weekly.json: a dry run of the weekly, kept apart from "
                                 "the week's, of ") for ln in said) and \
            (laptop / CL.LOCAL / "last-dry-weekly.json").read_bytes() == dry_v and \
            (laptop / CL.LOCAL / "last-weekly.json").read_bytes() == week_v, (
                "pull did not bring a dry weekly's verdict apart from the week's, said to be one",
                said)
        assert not taken, f"pull took a dry weekly's logs for the week's: {sorted(taken)}"

        # The same week on main sends its lists and its verdict, as it did.
        os.environ.update(GITHUB_ACTIONS="true", **{CL.REF_ENV: CL.MAIN_REF})
        real_week = machine("main-week")
        assert call(real_week, "state-down")[0] == 0 and call(real_week, "kit-down")[0] == 0
        put(real_week, {"committees.json": "{\"H\": [5]}",
                        "archive/last-weekly.json": "{\"run_id\": \"802\"}"})
        code, out = call(real_week, "kit-up")
        assert code == 0 and remote("kit/committees.json") == b"{\"H\": [5]}" and \
            remote("state/last-weekly.json") == b"{\"run_id\": \"802\"}", (
                "a weekly of main no longer sends what it took, or its verdict", out[-300:])
    finally:
        for k, val in saved_env.items():
            os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"each of the {len(weekly_files)} files the weekly takes is kept back by a dry "
                  "night; a weekly of dev, by its ref or by the workflow's word, sends its logs "
                  "under dry-run/, a refusal, a hold and its own verdict, and none of its lists, "
                  "the week's verdict or the census; pull says the verdict is a dry run's and "
                  "leaves its logs; a weekly of main sends as before")


@check("cloud", "the weekly measures the bucket by its top-level prefixes, read only, folds it "
       "into the week's results, and warns of a prefix its lifecycle rule should empty that "
       "holds files older than the rule keeps", needs=("cloud", "nightly"))
def _cloud_bucket_size(CL, NI):
    """THE BUCKET'S SIZE, BY PREFIX (cloud.py; the refactor's ops inventory, item 13). On a
    folder bucket -- never the real one -- with files under kit/, nights/, logs/, replaced/,
    backup/ and the top level, metadata under .meta/, and dates set: bucket-size counts each
    prefix's files and bytes and its oldest file's age, leaves .meta/ out, and changes nothing
    in the bucket; it warns, one line each, exactly for nights/ and replaced/, whose oldest files
    are past their rule and a day, and not for logs/ at its rule and a day; it says the change
    since last week's record, read from the week's verdict where state-down puts it. The
    weekly's --close folds a record of its own run into the week's results, verdict and
    warnings, leaving clean and the exit alone, and says "not measured" for another run's or
    none; R2Bucket's dated listing reads the date R2 gives with each key; the paths agree; and
    weekly.yml runs it after kit-up, before the verdict, carrying on past its failure."""
    import contextlib
    import io
    import types
    from datetime import datetime, timezone
    tmp = Path(tempfile.mkdtemp(prefix="gr-bucketsize-"))
    here = os.getcwd()
    saved_env = {k: os.environ.get(k) for k in ("GITHUB_RUN_ID", "GITHUB_ACTIONS",
                                                "GITHUB_STEP_SUMMARY", "GITHUB_OUTPUT",
                                                "GITHUB_SHA")}
    day = 86400
    try:
        for k in saved_env:
            os.environ.pop(k, None)
        os.environ["GITHUB_RUN_ID"] = "4242"
        bucket, root = tmp / "bucket", tmp / "root"
        now = datetime.now().timestamp()
        for key, size, age in (("kit/Docket.txt", 3000, 0), ("kit/db/a.psv", 2000, 40),
                               ("state/last-night.json", 100, 0),
                               ("nights/901/site.tar.gz", 50000, 9), ("nights/905/site.json", 10, 1),
                               ("logs/2026-10-19/nightly-2026-10-19.log", 70, 31.5),
                               ("replaced/2026-10-17/kit/Docket.txt", 900, 32.5),
                               ("backup/manifest.json", 400, 60), ("README.txt", 5, 3),
                               (".meta/kit/Docket.txt.json", 99, 0)):
            p = bucket.joinpath(*key.split("/"))
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"x" * size)
            os.utime(p, (now - age * day, now - age * day))
        (root / "archive").mkdir(parents=True)
        (root / CL.BUCKET_LAST_WEEK).write_text(json.dumps({"run_id": "4100", "bucket": {
            "at": "2026-11-12T23:30:00", "bytes": 40000, "files": 7,
            "prefixes": {"nights/": {"files": 1, "bytes": 30000, "oldest_days": 2}}}}),
            encoding="utf-8")
        before = {p.relative_to(bucket).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
                  for p in bucket.rglob("*") if p.is_file()}
        code, out = _cloud_call(CL, "bucket-size", "--local-bucket", str(bucket), "--root",
                                str(root))
        assert code == 0, out[-400:]
        after = {p.relative_to(bucket).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
                 for p in bucket.rglob("*") if p.is_file()}
        assert after == before, "bucket-size changed the bucket"
        rec = json.loads((root / CL.BUCKET_RECORD).read_text(encoding="utf-8"))
        pre = rec["prefixes"]
        assert {p: (e["files"], e["bytes"]) for p, e in pre.items()} == {
            "nights/": (2, 50010), "kit/": (2, 5000), "replaced/": (1, 900),
            "backup/": (1, 400), "state/": (1, 100), "logs/": (1, 70), CL.BUCKET_TOP: (1, 5)}, pre
        assert list(pre)[0] == "nights/" and rec["files"] == 9 and rec["bytes"] == 56485, rec
        assert (pre["nights/"]["oldest_days"], pre["replaced/"]["oldest_days"],
                pre["logs/"]["oldest_days"], pre["kit/"]["oldest_days"]) == (9, 32, 31, 40), pre
        warned = rec["warnings"]
        assert len(warned) == 2 and warned[0].startswith("The bucket's nights/ holds a file 9 days "
                                                         "old") and \
            warned[1].startswith("The bucket's replaced/ holds a file 32 days old") and \
            all("\n" not in w and len(w) <= 300 and "check the rule" in w for w in warned), warned
        assert rec["run_id"] == "4242" and rec["before"]["bytes"] == 40000 and \
            rec["said"].startswith("56.48 KB in 9 files (+16.48 KB since 2026-11-12): nights/ "
                                   "50.01 KB, kit/ 5.00 KB"), rec["said"]
        assert "WARNING The bucket's nights/" in out and "kept in logs/bucket-size.json" in out, out

        # The week's last word, as the weekly's --close gives it.
        os.chdir(root)
        NI.write_json(NI.WEEKLY_VERDICT, {"kind": "weekly", "run_id": "4242", "clean": True,
                                          "results": {"committees": "installed"}})

        def close(told="success", outcomes=("weekly=success",)):
            with contextlib.redirect_stdout(io.StringIO()):
                c = NI.close_verdict(types.SimpleNamespace(weekly=True, dry_run=False, cold=None,
                                                           bucket=told, outcome=list(outcomes)))
            return c, json.loads(Path(NI.WEEKLY_VERDICT).read_text(encoding="utf-8"))
        c, v = close(None)
        assert c == 0 and "the bucket" not in v["results"] and "bucket" not in v, \
            ("a week told nothing of the bucket (an older workflow) says it", v)
        NI.write_json(NI.WEEKLY_VERDICT, {"kind": "weekly", "run_id": "4242", "clean": True,
                                          "results": {"committees": "installed"}})
        c, v = close()
        assert c == 0 and v["clean"] and v["results"]["the bucket"] == rec["said"] and \
            v["bucket"]["prefixes"] == pre and "before" not in v["bucket"] and \
            all(w in v.get("warnings", []) for w in warned), ("the week's verdict", c, v)
        # ... which next week's bucket-size reads as last week's.
        os.chdir(here)
        Path(root / CL.BUCKET_LAST_WEEK).write_text(json.dumps(v), encoding="utf-8")
        code, out = _cloud_call(CL, "bucket-size", "--local-bucket", str(bucket), "--root",
                                str(root))
        nxt = json.loads((root / CL.BUCKET_RECORD).read_text(encoding="utf-8"))
        assert code == 0 and nxt["before"]["bytes"] == rec["bytes"] and \
            "(+0 bytes since " in nxt["said"], nxt["said"]
        os.chdir(root)
        os.environ["GITHUB_RUN_ID"] = "4243"
        NI.write_json(NI.WEEKLY_VERDICT, {"kind": "weekly", "run_id": "4243", "clean": True,
                                          "results": {}})
        c, v = close("failure")
        assert c == 0 and v["results"]["the bucket"].startswith("not measured") and \
            v["results"]["the bucket"].endswith("(its step: failure)") and \
            "bucket" not in v and not v.get("warnings"), ("another run's record was taken", v)
        os.chdir(here)
    finally:
        os.chdir(here)
        for k, val in saved_env.items():
            os.environ.pop(k, None) if val is None else os.environ.__setitem__(k, val)
        shutil.rmtree(tmp, ignore_errors=True)
    # R2's listing gives each key's date, which dated() reads.
    class Pages:
        def paginate(self, *, Bucket, Prefix=""):
            assert Bucket == "b" and Prefix == ""
            yield {"Contents": [{"Key": "kit/a", "Size": 3, "LastModified":
                                 datetime(2026, 11, 1, tzinfo=timezone.utc)}]}
            yield {"KeyCount": 0}
    r2 = object.__new__(CL.R2Bucket)
    r2.bucket, r2.s3 = "b", types.SimpleNamespace(get_paginator=lambda name: Pages())
    assert r2.dated("") == {"kit/a": (3, datetime(2026, 11, 1, tzinfo=timezone.utc).timestamp())}
    assert CL.BUCKET_RECORD == NI.BUCKET_RECORD.as_posix() and \
        CL.BUCKET_LAST_WEEK == NI.WEEKLY_VERDICT.as_posix() and \
        any(e.get("path") == CL.BUCKET_LAST_WEEK for e in
            json.loads(_source(CL.KIT_FILE)).get("state") or []), \
        "the record's path, or last week's verdict's, is not the same in cloud.py and nightly.py"
    wf = _SWITCHED.workflow_dir / "weekly.yml"
    if wf.is_file():
        steps = _wf_steps(_wf_code(_wf_jobs(_source(wf)).get("weekly", [])))
        at = {k: n for n, st in enumerate(steps) for k in ("bucket-size", "kit-up", "--close")
              if any(f"cloud.py {k}" in ln or f"nightly.py --runner --weekly {k}" in ln
                     for ln in st)}
        step = "\n".join(steps[at["bucket-size"]]) if "bucket-size" in at else ""
        sid = re.search(r"^        id:\s*(\S+)", step, re.M)
        assert step and sid and at["kit-up"] < at["bucket-size"] < at["--close"] and \
            "continue-on-error: true" in step and "if: always()" in step, (
                "weekly.yml does not measure the bucket after kit-up and before its verdict, "
                "carrying on past a failure", at)
        assert f'--bucket "${{{{ steps.{sid.group(1)}.outcome }}}}"' in \
            "\n".join(steps[at["--close"]]), "the weekly verdict is not told the bucket step's outcome"
    return "ok", ("7 prefixes counted with their oldest file, .meta/ left out, the bucket "
                  "unchanged; nights/ at 9 days and replaced/ at 32 warn, logs/ at 31 does not; "
                  "the change since last week's verdict said; folded into the week's results, "
                  "verdict and warnings, clean and exit untouched; another run's record not "
                  "taken; R2's dates read; weekly.yml measures it after kit-up")


def _fake_s3():
    """boto3 and botocore as far as cloud.R2Bucket uses them, holding objects
    in a dict, with the argument names the real client takes -- so a call
    spelt wrong here fails as it would against R2, and nothing leaves the
    machine."""
    import types
    store, made = {}, {}

    class ClientError(Exception):
        def __init__(self, error_response, operation_name):
            super().__init__(f"{operation_name}: {error_response}")
            self.response = error_response

    def gone(op):
        return ClientError({"Error": {"Code": "NoSuchKey" if op == "GetObject" else "404"},
                            "ResponseMetadata": {"HTTPStatusCode": 404}}, op)

    class Body:
        """botocore's StreamingBody as R2Bucket reads it: whole, or a piece
        at a time until it gives b"", and closed."""

        def __init__(self, b):
            self.b, self.at = b, 0

        def read(self, amt=None):
            end = len(self.b) if amt is None else min(len(self.b), self.at + amt)
            out, self.at = self.b[self.at:end], end
            return out

        def close(self):
            pass

    class Paginator:
        def __init__(self, name):
            assert name == "list_objects_v2", name

        def paginate(self, *, Bucket, Prefix=""):
            keys = sorted(k for b, k in store if b == Bucket and k.startswith(Prefix))
            if not keys:
                yield {"KeyCount": 0}
            for i in range(0, len(keys), 2):
                yield {"Contents": [{"Key": k, "Size": len(store[(Bucket, k)][0])}
                                    for k in keys[i:i + 2]]}

    class Client:
        def get_paginator(self, name):
            return Paginator(name)

        def head_object(self, *, Bucket, Key):
            if (Bucket, Key) not in store:
                raise gone("HeadObject")
            data, meta = store[(Bucket, Key)]
            return {"ContentLength": len(data), "Metadata": dict(meta)}

        def upload_file(self, Filename, Bucket, Key, ExtraArgs=None, Callback=None,
                        Config=None):
            meta = (ExtraArgs or {}).get("Metadata") or {}
            assert all(isinstance(v, str) and v.isascii() for v in meta.values()), meta
            store[(Bucket, Key)] = (Path(Filename).read_bytes(),
                                    {k.lower(): v for k, v in meta.items()})

        def download_file(self, Bucket, Key, Filename, ExtraArgs=None, Callback=None,
                          Config=None):
            made["download_file"] = made.get("download_file", 0) + 1
            if (Bucket, Key) not in store:
                raise gone("HeadObject")
            Path(Filename).write_bytes(store[(Bucket, Key)][0])

        def copy(self, CopySource, Bucket, Key, ExtraArgs=None, Callback=None,
                 SourceClient=None, Config=None):
            src = (CopySource["Bucket"], CopySource["Key"])
            if src not in store:
                raise gone("HeadObject")
            store[(Bucket, Key)] = store[src]

        def delete_object(self, *, Bucket, Key):
            store.pop((Bucket, Key), None)
            return {}

        def get_object(self, *, Bucket, Key):
            if (Bucket, Key) not in store:
                raise gone("GetObject")
            return {"Body": Body(store[(Bucket, Key)][0])}

        def put_object(self, *, Bucket, Key, Body, Metadata=None):
            store[(Bucket, Key)] = (bytes(Body), dict(Metadata or {}))
            return {}

    def client(service_name, *, endpoint_url, aws_access_key_id,
               aws_secret_access_key, region_name, config):
        made.update(service=service_name, endpoint=endpoint_url, region=region_name)
        return Client()

    class TransferConfig:
        def __init__(self, multipart_threshold=8 * 1024 * 1024, max_concurrency=10,
                     multipart_chunksize=8 * 1024 * 1024, num_download_attempts=5,
                     max_io_queue=100, io_chunksize=256 * 1024, use_threads=True,
                     max_bandwidth=None):
            pass

    class Config:
        KNOWN = {"region_name", "signature_version", "user_agent", "connect_timeout",
                 "read_timeout", "retries", "max_pool_connections",
                 "request_checksum_calculation", "response_checksum_validation"}

        def __init__(self, **kw):
            unknown = set(kw) - self.KNOWN
            if unknown:
                raise TypeError(f"Got unexpected keyword argument(s): {unknown}")

    mods = {n: types.ModuleType(n) for n in
            ("boto3", "boto3.s3", "boto3.s3.transfer", "botocore",
             "botocore.config", "botocore.exceptions")}
    mods["boto3"].client = client
    mods["boto3.s3.transfer"].TransferConfig = TransferConfig
    mods["botocore.config"].Config = Config
    mods["botocore.exceptions"].ClientError = ClientError
    return mods, store, made


def _kit_unmatched(CL, root, kit):
    """[(entry, [its paths and globs that match no file under root])] for the
    kit entries that do not say optional: what cloud.kit_files calls missing,
    by entry, so that a failure can name the one to mark."""
    out = []
    for e in kit.get("kit", []):
        if e.get("optional"):
            continue
        gone = [x for x in e.get("paths", []) if not CL.local(root, x).is_file()]
        gone += [g for g in e.get("globs", []) if not CL.expand(root, g)]
        if gone:
            out.append((e, gone))
    return out


def _kit_unmatched_says(CL, unmatched):
    """One line per entry, saying which, whose, and what to do about it."""
    lines = []
    for e, gone in unmatched:
        what = " ".join(str(e.get("what") or "").split())[:90]
        lines.append(
            f"{CL.KIT_FILE}: the {'laptop' if e['owner'] == 'laptop' else 'night'}'s entry "
            f"\"{what}...\" names {', '.join(gone)}, which "
            f"{'matches' if len(gone) == 1 else 'match'} no file here. "
            + ('If the files do not exist yet, add "optional": true to that entry; if they '
               "should exist, the laptop job that makes them has not run."
               if e["owner"] == "laptop" else
               "The night's files reach this laptop with python3 src/ops/cloud.py pull; if no night "
               'has made them yet, add "optional": true to that entry.'))
    return lines


@check("cloud", "a kit entry that matches nothing is found, by name, unless it says optional",
       needs=("cloud",))
def _kit_unmatched_fixture(CL):
    """The data check below reads the laptop's own files, and so cannot run
    where they are not. Its logic on a fixture: a required entry of the
    laptop's whose glob matches nothing is reported, with the entry's own
    words and the remedy; the same entry marked optional is not; and what it
    reports is exactly what stops seed-kit."""
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="gr-kit-entries-"))
    try:
        _cloud_fixture(tmp, real)
        kit = json.loads((tmp / "cloud_kit.json").read_text(encoding="utf-8"))
        assert _kit_unmatched(CL, tmp, kit) == [], _kit_unmatched(CL, tmp, kit)
        frozen = {"what": "Each term's views as they stood at its end. Nothing is here until "
                          "the first freeze.", "owner": "laptop", "globs": ["db/term/*/*"]}
        kit["kit"].append(frozen)
        kit["kit"].append({"what": "a file of the night's", "owner": "night",
                           "paths": ["lsrs.json"]})
        (tmp / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")
        found = _kit_unmatched(CL, tmp, kit)
        said = _kit_unmatched_says(CL, found)
        assert [g for _, g in found] == [["db/term/*/*"], ["lsrs.json"]], found
        assert "db/term/*/*" in said[0] and "Each term's views" in said[0] and \
            '"optional": true' in said[0] and "the laptop's entry" in said[0], said[0]
        assert "cloud.py pull" in said[1] and '"optional": true' in said[1], said[1]
        # It is what stops seed-kit, word for word the same paths.
        code, out = _cloud_call(CL, "seed-kit", "--dry-run", "--root", str(tmp),
                                "--local-bucket", str(tmp / "bucket"))
        assert code == 1 and "db/term/*/*" in out and "lsrs.json" in out, out[-300:]
        frozen["optional"] = True
        kit["kit"][-1]["optional"] = True
        (tmp / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")
        assert _kit_unmatched(CL, tmp, kit) == []
        code, out = _cloud_call(CL, "seed-kit", "--dry-run", "--root", str(tmp),
                                "--local-bucket", str(tmp / "bucket"))
        assert code == 0, out[-300:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a required entry matching nothing is named with its remedy, an optional one "
                  "is not, and the two agree with what stops seed-kit")


@check("data", "every kit entry matches a file on this laptop, or says \"optional\": true -- one "
       "that matches nothing stops seed-kit here and kit-down on GitHub's machine",
       needs=("cloud",))
def _kit_entries_match(CL):
    """On 30 September 2026 cloud_kit.json gained an entry for the frozen
    term's views, db/term/*/*, which nothing had made yet. A required entry
    that matches nothing makes cloud.py seed-kit refuse the whole kit -- it
    stopped that night's caption send -- and, once the definition reaches
    main, stops kit-down on GitHub's machine before the night begins. Nothing
    checked it: cloud.py says so only when it is run.

    So, on the laptop: every entry that does not say optional matches at
    least one file for each path and glob it names. A failure names the entry
    and says what to do -- for one of the laptop's whose files do not exist
    yet, "optional": true. A data check, because the files it looks for are
    the laptop's own; skipped anywhere that is not the repository holding
    secrets.json."""
    if not CL.home("."):
        return "skip", ("not the laptop's own working folder (no secrets.json here): the kit's "
                        "files are looked for where they are made")
    kit = CL.load_kit(".")
    unmatched = _kit_unmatched(CL, ".", kit)
    assert not unmatched, "\n".join(_kit_unmatched_says(CL, unmatched))
    required = [e for e in kit["kit"] if not e.get("optional")]
    return "ok", (f"all {len(required)} kit entries that are not optional match files here "
                  f"({sum(1 for e in required if e['owner'] == 'laptop')} the laptop's); "
                  f"{len(kit['kit']) - len(required)} say optional")


@check("cloud", "seed-kit --only sends only the files it names, and every other copy stands",
       needs=("cloud",))
def _cloud_seed_only(CL):
    """The laptop's evening job sends the caption results and nothing else: a
    data file re-read on dev and not yet released must not reach the night by
    that back door. Against a folder bucket: after a first seed, two of the
    laptop's files change; --only names one; only that one goes, the other's
    copy and its manifest entry stand, and a plain seed-kit then sends it."""
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="gr-only-"))
    try:
        root, bucket = tmp / "laptop", tmp / "bucket"
        root.mkdir()
        _cloud_fixture(root, real)
        B = ["--local-bucket", str(bucket)]
        assert _cloud_call(CL, "seed-kit", "--root", str(root), *B)[0] == 0
        (root / "legislation/2026/HB1.html").write_text("<p>one, again</p>", encoding="utf-8")
        (root / "legislation/2026/HB2.html").write_text("<p>two, again</p>", encoding="utf-8")
        code, out = _cloud_call(CL, "seed-kit", "--root", str(root), "--only",
                                "legislation/2026/HB1.html", *B)
        assert code == 0 and "sent 1 files" in out, out[-300:]
        assert (bucket / "kit/legislation/2026/HB1.html").read_text(encoding="utf-8") == \
            "<p>one, again</p>", "--only did not send the file it named"
        assert (bucket / "kit/legislation/2026/HB2.html").read_text(encoding="utf-8") == \
            "<p>two</p>", "--only sent a file it did not name"
        man = json.loads((bucket / "state/kit-manifest.json").read_text(encoding="utf-8"))
        assert "legislation/2026/HB2.html" in man["files"], \
            "--only dropped a file it held back from the kit's manifest"
        code, out = _cloud_call(CL, "seed-kit", "--root", str(root), *B)
        assert code == 0 and "sent 1 files" in out, out[-300:]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", "--only sends what it names; every other change waits, in the bucket and its manifest"


def _send_night_fixture(root, kit_src):
    """_pull_fixture with the two caption-results files as the real kit
    carries them, the night's: three recordings' times, the maps beside
    them, and where each recording's captions stop; and what the timestamp
    probe reads to score them -- a proceedings table and one hand-timed
    proceeding, on PFOTHER, which the copies place a second away."""
    _pull_fixture(root, kit_src)
    kit = json.loads((root / "cloud_kit.json").read_text(encoding="utf-8"))
    kit["kit"].append({"what": "caption results", "owner": "night",
                       "paths": ["candidate_segments.json", "caption_spans.json"]})
    (root / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")
    with open(root / "proceedings.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["term", "bill", "body", "kind", "date",
                                           "video_id", "source", "predicted_offset"])
        w.writeheader()
        w.writerow({"term": "2025-2026", "bill": "HB77", "body": "H", "kind": "public hearing",
                    "date": "2026-09-23", "video_id": "PFOTHER", "source": "docket",
                    "predicted_offset": "30"})
    (root / "review").mkdir(exist_ok=True)
    (root / "review" / "ground_truth.csv").write_text(
        "video_id,bill,kind,observed_start,observed_end,notes,marked_on\n"
        "PFOTHER,HB77,public hearing,61.0,,,2026-10-10\n", encoding="utf-8")
    (root / "candidate_segments.json").write_text(json.dumps({
        "PFOTHER": {"HB77": [{"start": 60.0, "end": None, "how": "number",
                              "what": "hearing", "said": "x"}]},
        "VIDA": {"HB1": [{"start": 10.0, "end": 50.0, "how": "number"}]},
        "VIDB": {"HB2": [{"start": 70.0, "end": 90.0, "how": "number"}]},
        "_absent": {"VIDA": ["HB3"]}, "_sequence": {"VIDA": [], "VIDB": []},
        "_named_before": {"VIDB": ["HB5|hearing"]}}), encoding="utf-8")
    (root / "caption_spans.json").write_text(json.dumps({"about": "x", "recordings": {
        "PFOTHER": {"last": 120.0}, "VIDA": {"last": 60.0}, "VIDB": {"last": 95.0}}}),
        encoding="utf-8")


@check("cloud", "send-night sends the caption results only when a person names them, never a "
                "subset of their recordings or a worse score, resumes a send that stopped, and "
                "the next pull and night take it", needs=("cloud", "refusal", "livestreams"))
def _cloud_send_night(CL, R, livestreams):
    """THE DELIBERATE SEND (17 October 2026). The caption results have been
    the night's since 10 October and seed-kit never sends the laptop's copy
    over the night's, so a re-read on the laptop after a change to the
    patterns could reach no site. send-night is that send, and each of its
    guards is a way to lose what the night holds, or to put worse times on
    the site. Against a folder bucket, with the window's clock set
    (refusal.CLOCK_ENV) and the real timestamp probe scoring the copies:

      - --dry-run says what would change, with both copies' probe, and
        writes nothing, here or there;
      - a path of the laptop's, on the never list, under site/, not in the
        kit, or any night's file but the two caption-results files, is
        refused by name;
      - a copy holding a subset of the bucket's recordings -- the re-read of
        one recording that once cost 842 their results -- is refused, dry or
        not, for both files, and so is one that drops a map beside them;
        --allow-dropping accepts a named loss; a copy the probe scores worse
        is refused, printing both scores;
      - nothing is sent on GitHub's machine, from a folder in the stood-down
        home repository, inside the night window, after it while that
        night has sent no verdict and could still run (NIGHT_JOB_MINUTES,
        held to nightly.yml), beside a build's lock, past a refusal here the
        bucket lacks, over a release a New term run waits on, over another
        writer's copy in kit/, or when the manifest moves mid-run;
      - a send that stops after the upload -- its manifest write dropped, or
        its read-back wrong -- is resumed by the next run, which finds the
        copy in kit/ and records it; a send replaces the bucket's copy,
        keeping the old under replaced/, and records it as the laptop's copy
        in common, so --changes-only counts nothing waiting, the next pull
        reports no clash and the next night's kit-down takes it; a --from
        copy takes the laptop's copy's place, setting the laptop's aside.
    """
    import hashlib
    import time
    from datetime import datetime
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="gr-sendnight-"))
    names = ("GITHUB_ACTIONS", CL.NO_BUCKET, R.CLOCK_ENV, "GRANITE_PROCEEDINGS")
    saved = {k: os.environ.get(k) for k in names}
    saved_fns = (CL.open_bucket, CL.home)
    today = f"{datetime.now():%Y-%m-%d}"
    CS, SP = "candidate_segments.json", "caption_spans.json"
    try:
        # THE JOB'S TIME, held to the workflow: a night may run this long.
        yml = _source(".github/workflows/nightly.yml")
        assert max(int(m) for m in re.findall(r"timeout-minutes:\s*(\d+)", yml)) == \
            CL.NIGHT_JOB_MINUTES, "cloud.NIGHT_JOB_MINUTES is not the night job's timeout-minutes"
        os.environ.pop("GITHUB_ACTIONS", None)
        os.environ.pop("GRANITE_PROCEEDINGS", None)
        os.environ[CL.NO_BUCKET] = "1"
        # After the window (13:30 UTC) and while its night could still run,
        # so the night's verdict is what lets a send through.
        outside = "2026-10-14T15:00:00Z"
        os.environ[R.CLOCK_ENV] = outside
        bucket, laptop, night = tmp / "bucket", tmp / "laptop", tmp / "night"
        for d in (laptop, night):
            d.mkdir()
            _send_night_fixture(d, real)
        (night / "logs/nightly-2026-09-25.log").unlink()
        (night / "reports/gc-changes-2026-09-25.md").unlink()

        def call(root, *argv, kind=None):
            if kind:
                CL.open_bucket = lambda a, preview=False: kind(a.local_bucket,
                                                               create=not a.dry_run)
            try:
                return _cloud_call(CL, *argv, "--root", str(root), "--local-bucket", str(bucket))
            finally:
                CL.open_bucket = saved_fns[0]

        def doc(path):
            return json.loads(Path(path).read_text(encoding="utf-8"))

        def put(path, d):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(json.dumps(d), encoding="utf-8")

        def verdict(day):
            put(bucket / "state/last-night.json", {"kind": "nightly", "day": day, "clean": True})

        def manifest_sha(rel):
            return doc(bucket / "state/kit-manifest.json")["files"][rel]["sha256"]

        assert call(laptop, "seed-kit")[0] == 0
        verdict("2026-10-14")
        assert call(night, "state-down")[0] == 0 and call(night, "kit-down")[0] == 0
        # The night captions a recording and merges it into both files.
        cs, sp = doc(night / CS), doc(night / SP)
        cs["VIDC"] = {"HB4": [{"start": 5.0, "end": 9.0, "how": "number"}]}
        sp["recordings"]["VIDC"] = {"last": 30.0}
        put(night / CS, cs)
        put(night / SP, sp)
        assert call(night, "kit-up")[0] == 0
        code, out = call(laptop, "pull")
        assert code == 0, out[-400:]
        # The laptop re-reads after a change to the patterns: VIDA's time moves.
        cs = doc(laptop / CS)
        cs["VIDA"]["HB1"][0]["start"] = 12.0
        put(laptop / CS, cs)
        good = "places 1 of 1 hand-timed proceedings, median 1.0s"

        before, here = _tree(bucket), _tree(laptop)
        code, out = call(laptop, "send-night", CS, "--dry-run")
        assert code == 0 and "nothing sent" in out and "1 changed, 0 dropped" in out, out[-500:]
        assert out.count(good) == 2, f"the dry run did not print both copies' probe: {out[-500:]}"
        assert _tree(bucket) == before and _tree(laptop) == here, \
            "send-night --dry-run wrote to the bucket or the laptop"

        for p, why in (("legislation/2026/HB1.html", "the laptop's"),
                       ("secrets.json", "never list"), ("site/committees.json", "built site"),
                       ("elsewhere.json", "not in the kit"),
                       ("Docket.txt", "only the caption results")):
            code, out = call(laptop, "send-night", p)
            assert code == 1 and why in out, f"send-night {p} was not refused as {why}: {out[-300:]}"

        sub = tmp / "subset.json"
        put(sub, {k: cs[k] for k in ("VIDA", "PFOTHER", "_absent", "_sequence", "_named_before")})
        for dry in ((), ("--dry-run",)):
            code, out = call(laptop, "send-night", CS, "--from", str(sub), *dry)
            assert code == 1 and "drops 2" in out and "VIDB" in out and "VIDC" in out, \
                f"a re-read of a subset was not refused{dry}: {out[-400:]}"
        put(sub, {"about": "x", "recordings": {"VIDA": {"last": 60.0}, "PFOTHER": {"last": 1.0}}})
        code, out = call(laptop, "send-night", SP, "--from", str(sub))
        assert code == 1 and "VIDB" in out, f"caption_spans.json's subset was not refused: {out[-300:]}"
        for side in ("_sequence", "_named_before"):
            put(sub, {k: v for k, v in cs.items() if k != side})
            code, out = call(laptop, "send-night", CS, "--from", str(sub))
            assert code == 1 and f"drops 1" in out and side in out, \
                f"{side} gone whole was not refused: {out[-300:]}"
        put(sub, {k: v for k, v in cs.items() if k != "VIDB"})
        code, out = call(laptop, "send-night", CS, "--from", str(sub), "--allow-dropping", "VIDB",
                         "--dry-run")
        assert code == 0 and "named by --allow-dropping" in out, out[-400:]
        # A WORSE SCORE: the hand-timed proceeding an hour from where it was.
        worse = json.loads(json.dumps(cs))
        worse["PFOTHER"]["HB77"][0]["start"] = 3600.0
        put(sub, worse)
        code, out = call(laptop, "send-night", CS, "--from", str(sub))
        assert code == 1 and "scores worse" in out and good in out and "median 3539.0s" in out, \
            f"a copy the probe scores worse was not refused, with both scores: {out[-500:]}"

        # NOTHING IS SENT on GitHub's machine, or from a folder in the
        # stood-down home repository.
        os.environ["GITHUB_ACTIONS"] = "true"
        code, out = call(laptop, "send-night", CS)
        os.environ.pop("GITHUB_ACTIONS")
        assert code == 1 and "is a person's" in out, f"a send on GitHub's machine: {out[-300:]}"
        CL.home = lambda root: True
        put(laptop / "archive/runs-in-the-cloud.json", {})
        code, out = call(laptop, "send-night", CS, "--dry-run")
        assert code == 1 and "--allow-local-bucket" in out, \
            f"a folder send in the stood-down home repository: {out[-300:]}"
        assert call(laptop, "send-night", CS, "--dry-run", "--allow-local-bucket")[0] == 0
        CL.home = saved_fns[1]
        (laptop / "archive/runs-in-the-cloud.json").unlink()
        # ... nor while a night may hold the copy.
        os.environ[R.CLOCK_ENV] = "2026-10-14T09:00:00Z"
        code, out = call(laptop, "send-night", CS)
        assert code == 1 and "night window" in out, f"a send inside the night window: {out[-300:]}"
        os.environ[R.CLOCK_ENV] = outside
        verdict("2026-10-13")
        code, out = call(laptop, "send-night", CS)
        assert code == 1 and "no verdict" in out, f"a send while the night may still run: {out[-300:]}"
        code, out = call(laptop, "send-night", CS, "--dry-run")
        assert code == 0 and "A SEND NOW WOULD BE REFUSED" in out and "no verdict" in out, out[-300:]
        os.environ[R.CLOCK_ENV] = "2026-10-14T19:00:00Z"
        code, out = call(laptop, "send-night", CS, "--dry-run")
        assert code == 0 and "no verdict" not in out, \
            f"a night no longer able to run still stopped the send: {out[-300:]}"
        os.environ[R.CLOCK_ENV] = outside
        verdict("2026-10-14")
        (laptop / ".build.lock").write_text("x", encoding="utf-8")
        code, out = call(laptop, "send-night", CS)
        (laptop / ".build.lock").unlink()
        assert code == 1 and ".build.lock is fresh" in out, f"a send beside a build: {out[-300:]}"
        put(laptop / "archive/refused.json", {"at": "now", "epoch": time.time(), "where": "a test"})
        code, out = call(laptop, "send-night", CS)
        (laptop / "archive/refused.json").unlink()
        assert code == 1 and "send-refusal" in out, f"a send past an unsent refusal: {out[-300:]}"
        put(bucket / "nights/RUN1/kit.json", {"files": {CS: {"sha256": "a" * 64, "size": 1}},
                                              "base": {CS: manifest_sha(CS)}})
        code, out = call(laptop, "send-night", CS)
        shutil.rmtree(bucket / "nights")
        assert code == 1 and "run RUN1's New term night" in out, \
            f"a send over a release still waiting: {out[-300:]}"
        meta = bucket / ".meta" / "kit" / f"{CS}.json"
        kept_meta = meta.read_bytes()
        put(meta, {"sha256": "f" * 64, "mtime_ns": "1"})
        code, out = call(laptop, "send-night", CS)
        meta.write_bytes(kept_meta)
        assert code == 1 and "another machine" in out, f"a send over another writer's copy: {out[-300:]}"

        class Mover(CL.FolderBucket):
            """A night's kit-up lands between the comparison and the send."""
            reads = 0

            def get_bytes(self, key):
                data = super().get_bytes(key)
                if key == "state/kit-manifest.json":
                    Mover.reads += 1
                    if Mover.reads == 2:
                        d = json.loads(data)
                        d["files"][CS]["sha256"] = "0" * 64
                        data = json.dumps(d).encode("utf-8")
                return data
        code, out = call(laptop, "send-night", CS, kind=Mover)
        assert code == 1 and "changed while this ran" in out, f"a manifest moved mid-run: {out[-300:]}"
        assert _tree(bucket) == before, "a refused send-night wrote to the bucket"

        # A SEND THAT STOPS HALFWAY: the upload lands, the manifest write is
        # dropped. kit/ is new, the manifest old, this laptop's record as it was.
        class NoManifest(CL.FolderBucket):
            def put_bytes(self, key, data):
                if key == "state/kit-manifest.json":
                    raise OSError("the manifest write was dropped")
                super().put_bytes(key, data)
        was, old_sha = (bucket / "kit" / CS).read_bytes(), manifest_sha(CS)
        sent = (laptop / CS).read_bytes()
        rec_before = doc(laptop / CL.PULL_RECORD)["kit"][CS]
        code, out = call(laptop, "send-night", CS, kind=NoManifest)
        assert code == 1 and "Run send-night again" in out, out[-400:]
        assert (bucket / "kit" / CS).read_bytes() == sent and manifest_sha(CS) == old_sha \
            and doc(laptop / CL.PULL_RECORD)["kit"][CS] == rec_before, \
            "the halfway send did not leave kit/ new and the records old"
        code, out = call(laptop, "send-night", CS)
        assert code == 0 and "1 a stopped send left in kit/ recorded" in out, \
            f"a re-run did not resume the send that stopped: {out[-400:]}"
        assert manifest_sha(CS) == hashlib.sha256(sent).hexdigest(), \
            "the kit manifest does not record the copy sent"
        # The night's kit-up kept a copy there today already, so this one may
        # carry the time after its name (Replacer).
        assert any(p.read_bytes() == was for p in (bucket / f"replaced/{today}/kit").glob(f"{CS}*")), \
            "the bucket's previous copy was not kept under replaced/"
        code, out = call(laptop, "pull", "--changes-only")
        assert code == 0 and "has 0 of the night's" in out, \
            f"the pull record does not hold the copy sent: {out[-400:]}"
        code, out = call(laptop, "pull")
        assert code == 0 and "0 clashing" in out, f"the next pull clashed on the copy sent: {out[-400:]}"
        code, out = call(night, "kit-down")
        assert code == 0 and (night / CS).read_bytes() == sent, \
            f"the next night did not take the copy sent: {out[-300:]}"

        # A --from copy whose read-back is wrong: stopped, then resumed, and
        # in this laptop's copy's place, the laptop's own set aside.
        class Garble(CL.FolderBucket):
            put = False

            def put_file(self, src, key, meta):
                super().put_file(src, key, meta)
                Garble.put = True

            def get_bytes(self, key):
                data = super().get_bytes(key)
                return b"garbled" if Garble.put and key == f"kit/{SP}" else data
        merged, mine = tmp / "merged.json", (laptop / SP).read_bytes()
        sp = doc(laptop / SP)
        sp["recordings"]["VIDA"]["last"] = 61.0
        put(merged, sp)
        code, out = call(laptop, "send-night", SP, "--from", str(merged), kind=Garble)
        assert code == 1 and "did not read back" in out and (laptop / SP).read_bytes() == mine, \
            out[-400:]
        code, out = call(laptop, "send-night", SP, "--from", str(merged))
        assert code == 0 and "recorded" in out, out[-400:]
        assert (laptop / SP).read_bytes() == merged.read_bytes() == (bucket / "kit" / SP).read_bytes(), \
            "a --from copy did not take the laptop's copy's place"
        assert (laptop / f"{CL.SET_ASIDE}/{today}/{SP}").read_bytes() == mine, \
            "the laptop's own copy was not set aside"
        code, out = call(laptop, "pull")
        assert code == 0 and "0 clashing" in out, f"the next pull clashed on a --from copy: {out[-400:]}"
    finally:
        CL.open_bucket, CL.home = saved_fns
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("a dry run writes nothing and prints both probes; any path but the two caption "
                  "files, a subset of their recordings and a worse probe are refused, and so is a "
                  "send on GitHub, from home, in or after the window, beside a build, past a "
                  "refusal, over a waiting release or another writer's copy; a stopped send "
                  "resumes; the next pull and night take it without a clash")


@check("livestreams", "the evening job is retired, and the caption results are the night's",
       needs=("cloud", "livestreams"))
def _ls_evening_retired(CL, livestreams):
    """The laptop's evening job (laptop_evening.py, Windows' Task Scheduler,
    from 30 September 2026) captioned what YouTube refused GitHub's machine
    and sent candidate_segments.json and caption_spans.json to the kit. It
    captioned one recording in nine runs -- YouTube answered it with a 429
    every evening after the first -- and once sent a laptop build's reading
    into the kit. The person switched it off on 8 October and decided on the
    same day that the night owns the captions. So:

      - it is gone -- kept in obsolete/ from 10 October, and deleted with that
        folder on 23 October 2026 (git history keeps it) -- and no runner
        names it;
      - the two caption results are the night's in the kit, and the
        clustering model's segments, which only a person reruns, the
        laptop's;
      - a dry run sends neither back (the dry night sends only the store);
      - the livestream step's three small files are what it carries itself.
    """
    back = _paths.find("laptop_evening.py")
    assert not Path("laptop_evening.py").exists() and back is None, \
        f"laptop_evening.py is back ({back or 'at the root'}): the night takes the captions now"
    assert "laptop_evening.py" not in _RUNNERS and "laptop_evening.py" not in _RUNNER_FLOORS
    named = [r for r, ns in _runner_names().items() if any("laptop_evening" in n for n, _ in ns)]
    assert not named, f"{named} still start laptop_evening.py"
    kit = CL.load_kit(".")
    for f in ("candidate_segments.json", "caption_spans.json"):
        assert CL.owner_of(kit, f) == "night", f"{f} is the {CL.owner_of(kit, f)}'s in the kit"
        assert not CL.dry_sends(kit, Path("."), f, {}), f"a dry night would send {f}"
    assert CL.owner_of(kit, "work/x/segments.json") == "laptop", \
        "the clustering model's segments are not the laptop's"
    assert livestreams.carry_list() == ["archive/livestreams.json", "videos_house_livestreams.csv",
                                        "videos_senate_livestreams.csv"]
    return "ok", ("laptop_evening.py gone, named by no runner; the caption results the "
                  "night's, sent back by no dry run; the clustering segments the laptop's")


@check("cloud", "the R2 adapter makes the calls boto3 takes", needs=("cloud",))
def _cloud_r2_adapter(CL):
    """The folder bucket above tests the logic; R2 is reached through
    R2Bucket, which no check could run without asking a server. So boto3 is
    stood in for, with the real client's argument names, and one seed, one
    kit-down and one kit-up go through the adapter: the endpoint is the
    account's R2 address, a missing object reads as missing rather than as a
    failure, listings are read across pages, and metadata goes up as text.
    And the account and key never reach a printed line: GitHub's logs of a
    public repository are public, and an S3 error names its endpoint.
    """
    mods, store, made = _fake_s3()
    saved_mods = {n: sys.modules.get(n) for n in mods}
    saved_open = CL.open_bucket
    tmp = Path(tempfile.mkdtemp(prefix="gr-r2-"))
    try:
        sys.modules.update(mods)
        bucket = CL.R2Bucket({"account": "acct0123456789", "key_id": "keyid0123456789",
                              "secret": "secret0123456789",
                              "bucket": "granite-record-backup"}, 4)
        assert made == {"service": "s3",
                        "endpoint": "https://acct0123456789.r2.cloudflarestorage.com",
                        "region": "auto"}, made
        said = CL.scrub(f"Could not connect to the endpoint URL: {made['endpoint']} "
                        "with keyid0123456789 and secret0123456789")
        assert not any(v in said for v in ("acct0123456789", "keyid0123456789",
                                           "secret0123456789")), said
        assert bucket.get_bytes("state/none.json") is None and bucket.head("kit/none") is None
        CL.open_bucket = lambda a, preview=False: bucket
        root = tmp / "laptop"
        root.mkdir()
        _cloud_fixture(root, json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8")))
        code, out = _cloud_call(CL, "seed-kit", "--root", str(root))
        assert code == 0, out[-300:]
        keys = {k for _, k in store}
        assert "kit/Docket.txt" in keys and "state/kit-manifest.json" in keys, sorted(keys)
        assert store[("granite-record-backup", "kit/Docket.txt")][1].get("sha256"), \
            "no sha256 went up with the object"
        night = tmp / "night"
        night.mkdir()
        shutil.copy(root / "cloud_kit.json", night / "cloud_kit.json")
        code, out = _cloud_call(CL, "kit-down", "--root", str(night))
        assert code == 0 and (night / "Docket.txt").read_text() == "docket 1\n", out[-300:]
        # ONE GET A SMALL FILE (23 October 2026): kit-down's files under a part
        # come down by get_object, each read back against its sha256, and not
        # by download_file's HEAD and GET.
        assert not made.get("download_file"), \
            f"kit-down took {made['download_file']} small file(s) by download_file"
        (night / "Docket.txt").write_text("docket 2\n", encoding="utf-8")
        code, out = _cloud_call(CL, "kit-up", "--root", str(night))
        assert code == 0, out[-300:]
        assert store[("granite-record-backup", "kit/Docket.txt")][0] == \
            (night / "Docket.txt").read_bytes(), "the night's change did not go up"
        assert any(k.startswith("replaced/") and k.endswith("kit/Docket.txt")
                   for _, k in store), "the replaced copy did not go through the adapter"
        # A New term run's held files, and their release: the copy into kit/
        # is the bucket's own, and the object keeps its sha256.
        # A different LENGTH from "docket 2": kit-up takes a file of the same
        # size and date as unchanged without reading it, and on a disk whose
        # clock ticks every 16 ms a second write of the same length lands on
        # the first one's date more often than not (190 of 200 here).
        was = (night / "Docket.txt").read_bytes()
        (night / "Docket.txt").write_text("docket three\n", encoding="utf-8")
        now = (night / "Docket.txt").read_bytes()
        code, out = _cloud_call(CL, "kit-up", "--hold", "77", "--root", str(night))
        assert code == 0 and store[("granite-record-backup", "kit/Docket.txt")][0] == was and \
            store[("granite-record-backup", "nights/77/kit/Docket.txt")][0] == now, out[-300:]
        code, out = _cloud_call(CL, "kit-release", "--run", "77", "--root", str(night))
        got = store[("granite-record-backup", "kit/Docket.txt")]
        assert code == 0 and got[0] == now and \
            got[1].get("sha256") == CL.sha256_of(night / "Docket.txt"), out[-300:]
        return "ok", ("seed-kit, kit-down, kit-up, a held kit-up and its release through "
                      "R2Bucket against a stand-in for boto3: endpoint, pages, metadata and "
                      "missing objects as the real client has them")
    finally:
        CL.open_bucket = saved_open
        for n, m in saved_mods.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m
        shutil.rmtree(tmp, ignore_errors=True)


def _pull_fixture(root, kit_src):
    """_cloud_fixture with what pull reads besides: the night's logs and change
    lists in the kit's log globs, both verdicts in the state list, and the one
    file of the night's built site the real kit carries, which pull must leave
    alone."""
    _cloud_fixture(root, kit_src)
    kit = json.loads((root / "cloud_kit.json").read_text(encoding="utf-8"))
    kit["kit"].append({"what": "site", "owner": "night", "optional": True,
                       "paths": ["site/committees.json"]})
    kit["state"] += [{"path": "archive/last-night.json", "key": "last-night.json", "what": "x"},
                     {"path": "archive/last-dry-run.json", "key": "last-dry-run.json", "what": "x"},
                     {"path": "archive/last-weekly.json", "key": "last-weekly.json", "what": "x"},
                     {"path": "archive/last-dry-weekly.json", "key": "last-dry-weekly.json",
                      "what": "x"},
                     {"path": "archive/livestreams.json", "key": "livestreams.json", "what": "x"}]
    kit["logs"] = {"globs": ["logs/*", "reports/gc-changes-*.md"]}
    (root / "cloud_kit.json").write_text(json.dumps(kit), encoding="utf-8")
    (root / "site" / "committees.json").write_text("[]", encoding="utf-8")


def _tree(root):
    """{path: bytes} for every file under root."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in Path(root).rglob("*") if p.is_file()}


def _reached(tree, start, leaves=()):
    """The top-level functions and classes of a module that `start` can reach
    by name, itself included -- a class counting as all of its methods, except
    the `leaves`, which are not read: for cloud.py the bucket classes, whose
    writing methods exist for other commands. Whether pull CALLS one is read
    in pull's own functions."""
    import ast
    defs = {n.name: n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    seen, todo = set(), [start]
    while todo:
        name = todo.pop()
        if name in seen or name not in defs or name in leaves:
            continue
        seen.add(name)
        for n in ast.walk(defs[name]):
            if isinstance(n, ast.Name) and n.id in defs:
                todo.append(n.id)
    return {name: defs[name] for name in seen}


@check("cloud", "pull brings the nights' work to the laptop and writes nothing to the bucket, "
                "and a refusal crosses between the machines both ways", needs=("cloud", "refusal"))
def _cloud_pull(CL, R):
    """Until 26 September nothing brought GitHub's nights back: kit-down is for
    an empty machine and fails on a file that differs, so the laptop's data
    froze at the stand-down, its nightly logs stopped arriving, and the
    morning triage looked for a change list that was never there. And a
    refusal met on one machine stayed there: the night's in the bucket, the
    laptop's in archive/, each invisible to the other.

    Against a folder bucket: a night changes its own files, one of the
    laptop's and the built site, writes its logs, change lists and verdict,
    and sends them. A dry pull writes nothing anywhere and makes no folder. A
    pull brings the night's files -- including one the laptop has no pull
    record of, settled by the bucket's own old manifests -- its logs to
    logs/, its change lists to reports/ and its verdict to archive/cloud/,
    never archive/, and leaves the laptop's files, site/ and unknown log
    names alone. A night's file changed on the laptop, or a log the laptop
    wrote itself, or a file written while the pull ran, is a clash: left as
    it is, named, exit 1, and --take (however the path is written) sets it
    aside and takes the bucket's. --changes-only takes the change list and
    the verdict and says how old the last full pull is and how many of the
    night's files changed since; a verdict from before yesterday is STALE.
    A pull refuses on GitHub, beside a running build, from a bucket that
    holds neither a kit manifest nor a verdict (recording no read), and from
    a folder in the stood-down home repository. The days looked at start the
    day before the last pull's, and a record from the future is corrected.
    Throughout, a bucket that fails any put, copy or delete stands in, and
    every function pull can reach is read for one.

    The refusal: the night's comes down where the laptop has none, saying
    what it stops; where both hold one the newer stands and the older is set
    aside; the read is recorded with the kind of bucket. refusal.note() on a
    stood-down laptop sends one to a bucket that has none -- and from a
    folder that is not the repository holding secrets.json, never to the
    real bucket -- and when the bucket cannot be reached leaves a marker that
    pull and state-up report until send-refusal sends it, without note()
    failing. A newer laptop refusal behind an older one in the bucket keeps
    its marker, waits, is named by clear-refusal when the bucket's is
    lifted -- which then exits 1, as it does for any laptop refusal that
    waited behind the one cleared (newer and in force, or marked), and only
    then -- fails the next pull, and is sent. A refusal recorded here while
    a pull reads the bucket's is never written over: the pull creates the
    file or, finding one, compares the two. home() is the checkout that
    holds secrets.json, not the one keys.py sits in; and the recorder that
    proves a temp folder's refusal makes no bucket raises rather than make
    one, with GRANITE_NO_BUCKET left set.
    """
    import ast
    import contextlib
    import io
    import types
    from datetime import date, datetime, timedelta
    real = json.loads(Path(CL.KIT_FILE).read_text(encoding="utf-8"))
    tmp = Path(tempfile.mkdtemp(prefix="gr-pull-"))
    saved = (CL.open_bucket, R.MARK, R.CLOUD_BUCKET, os.environ.get("GITHUB_ACTIONS"),
             os.environ.get(CL.NO_BUCKET), CL.home, CL.make_bucket)
    today = f"{datetime.now():%Y-%m-%d}"
    writes = []

    class ReadOnly(CL.FolderBucket):
        def _no(self, what, key):
            writes.append(f"{what} {key}")
            raise AssertionError(f"pull tried to {what} {key} in the bucket")

        def put_file(self, src, key, meta):
            self._no("put", key)

        def put_bytes(self, key, data):
            self._no("put", key)

        def copy(self, src, dst):
            self._no("copy", dst)

        def delete(self, key):
            self._no("delete", key)

    # EVERY FUNCTION PULL CAN REACH, read: no put, copy, delete or Replacer.
    # The reader first, on a put two calls down that it must find.
    probe = ast.parse("def cmd_pull(a):\n    helper(a)\n\n\ndef helper(b):\n"
                      "    b.put_bytes('k', b'')\n")
    assert any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "put_bytes"
               for d in _reached(probe, "cmd_pull").values() for n in ast.walk(d)), \
        "the reader of pull's code misses a put two calls down"
    tree = ast.parse(_source(CL.__file__))
    reached = _reached(tree, "cmd_pull", leaves={"FolderBucket", "NotAsked", "R2Bucket"})
    WRITERS = {"put_file", "put_bytes", "copy", "delete", "keep"}
    NAMED = {"send", "write_manifest", "put_logs", "state_up", "Replacer", "Checkpoint",
             "send_refusal", "unsent_after"}
    bad = sorted({f"{name} calls {n.func.attr}" for name, d in reached.items()
                  for n in ast.walk(d) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and n.func.attr in WRITERS}
                 | {f"cmd_pull reaches {name}" for name in reached if name in NAMED})
    assert "cmd_pull" in reached and "pull_kit" in reached and "full_pull_news" in reached, \
        "cmd_pull was not found to read"
    assert not bad, "pull can write to the bucket: " + "; ".join(bad)

    # The days: from the day before the last pull's, seven at most, and a
    # record from the future corrected and said.
    ns = types.SimpleNamespace(day=None, changes_only=False)
    d0 = date(2026, 9, 28)
    assert CL.pull_days(ns, {"logs_through": "2026-09-28"}, d0) == (
        ["2026-09-27", "2026-09-28"], ""), "the day before the last pull's is not looked at again"
    days, note = CL.pull_days(ns, {"logs_through": "2026-10-03"}, d0)
    assert days == ["2026-09-27", "2026-09-28"] and "after today" in note, (days, note)
    assert len(CL.pull_days(ns, {}, d0)[0]) == CL.PULL_DAYS == 7
    assert CL.pull_days(ns, {"logs_through": "2026-09-01"}, d0)[0][0] == "2026-09-22"

    # --take, however a person writes the path; and naming --take when wrong.
    assert CL.take_paths(tmp, [".\\logs\\a.log", "./narratives.json", "Docket.txt",
                               str(tmp / "nh-archive" / "x.gz")]) == \
        {"logs/a.log", "narratives.json", "Docket.txt", "nh-archive/x.gz"}
    for wrong in ("..\\elsewhere.txt", str(tmp.parent / "outside.txt"), ".\\"):
        try:
            CL.take_paths(tmp, [wrong])
            raise AssertionError(f"--take {wrong!r} was taken as a file here")
        except CL.Failed as e:
            assert "--take" in str(e), f"a bad --take path's error does not name --take: {e}"

    def refusal(epoch, where):
        return json.dumps({"at": f"t{epoch}", "epoch": epoch, "where": where})

    try:
        os.environ.pop("GITHUB_ACTIONS", None)
        os.environ[CL.NO_BUCKET] = "1"
        bucket = tmp / "bucket"
        laptop, night = tmp / "laptop", tmp / "night"
        for d in (laptop, night):
            d.mkdir()
            _pull_fixture(d, real)
        (night / "logs/nightly-2026-09-25.log").unlink()
        (night / "reports/gc-changes-2026-09-25.md").unlink()

        def call(root, *argv, bucket=bucket):
            return _cloud_call(CL, *argv, "--root", str(root), "--local-bucket", str(bucket))

        def pull(root, *argv, bucket=bucket, kind=ReadOnly):
            CL.open_bucket = lambda a, preview=False: kind(a.local_bucket,
                                                           create=not a.dry_run)
            try:
                return call(root, "pull", *argv, bucket=bucket)
            finally:
                CL.open_bucket = saved[0]

        def text(root, rel):
            p = root.joinpath(*rel.split("/"))
            return p.read_text(encoding="utf-8") if p.exists() else None

        def dirs(*roots):
            return {p for r in roots for p in Path(r).rglob("*") if p.is_dir()} | {
                Path(r) for r in roots if Path(r).exists()}

        # A bucket nothing was ever sent to is no answer: nothing taken, no read.
        blank, fresh = tmp / "blank", tmp / "fresh"
        blank.mkdir()
        fresh.mkdir()
        _pull_fixture(fresh, real)
        code, out = pull(fresh, "--changes-only", bucket=blank)
        assert code == 1 and "neither" in out and not (fresh / CL.PULL_RECORD).exists(), (
            f"a pull of an empty bucket counted as reading the refusal record: {out[-300:]}")

        assert call(laptop, "seed-kit")[0] == 0
        assert call(night, "state-down")[0] == 0 and call(night, "kit-down")[0] == 0
        # The night: its own files, one of the laptop's, the site, the logs.
        (night / "Docket.txt").write_text("docket 2\n", encoding="utf-8")
        (night / "legislation/2026/HB1.html").write_text("<p>ONE</p>", encoding="utf-8")
        (night / "site/committees.json").write_text("[1]", encoding="utf-8")
        new = f"nh-archive/snapshots/{today}/b.gz"
        (night / new).parent.mkdir(parents=True, exist_ok=True)
        (night / new).write_text("b", encoding="utf-8")
        log = f"logs/nightly-{today}.log"
        (night / log).write_text(f"{'=' * 74}\nGranite Record nightly  {today} 02:17\n",
                                 encoding="utf-8")
        (night / f"logs/site-{today}.sha256").write_text("abc  1  index.html\n", encoding="utf-8")
        (night / "logs/other.log").write_text("not the night's own name\n", encoding="utf-8")
        (night / f"reports/gc-changes-{today}.md").write_text("what the night found\n",
                                                               encoding="utf-8")
        (night / f"reports/gc-changes-weekly-{today}.md").write_text("the weekly's\n",
                                                                      encoding="utf-8")
        (night / "archive/last-night.json").write_text(json.dumps(
            {"kind": "nightly", "day": today, "started": f"{today}T02:17:00",
             "clean": True}), encoding="utf-8")
        # ... and a dry run's, kept apart from it (7 October 2026).
        (night / "archive/last-dry-run.json").write_text(json.dumps(
            {"kind": "nightly", "day": today, "started": f"{today}T11:02:00",
             "clean": True, "asked": {"dry_run": True}}), encoding="utf-8")
        # ... and a dry weekly's, kept apart from the week's (7 October 2026).
        (night / "archive/last-dry-weekly.json").write_text(json.dumps(
            {"kind": "weekly", "day": today, "clean": False, "not_clean": ["committees: x"],
             "asked": {"dry_run": True}}), encoding="utf-8")
        (night / "archive/livestreams.json").write_text(json.dumps(
            {"version": 1, "videos": {}, "last_run": {"at": f"{today}T08:45:00Z"}}),
            encoding="utf-8")
        code, out = call(night, "kit-up")
        assert code == 0, out[-300:]
        assert call(night, "state-up")[0] == 0

        # A dry pull writes nothing, here or there, and makes no folder --
        # archive/cloud/ included, which the machine lock would have made.
        dry = tmp / "dry"
        dry.mkdir()
        _pull_fixture(dry, real)
        before, folders = _tree(dry), dirs(dry, bucket)
        assert not (dry / "archive/cloud").exists()
        code, out = call(dry, "pull", "--dry-run")
        assert code == 0 and "nothing written" in out, out[-400:]
        assert _tree(dry) == before and dirs(dry, bucket) == folders, \
            "pull --dry-run wrote a file or made a folder"
        code, out = call(dry, "pull", "--dry-run", bucket=tmp / "nowhere")
        assert code == 1 and not (tmp / "nowhere").exists(), \
            "pull --dry-run made the folder it was given as the bucket"
        before = _tree(laptop)
        code, out = pull(laptop, "--dry-run")
        assert code == 0 and "nothing written" in out, out[-400:]
        assert _tree(laptop) == before, "pull --dry-run wrote something on the laptop"

        code, out = pull(laptop)
        assert code == 0, out[-600:]
        assert "STALE" not in out, f"today's verdict was called stale: {out[-300:]}"
        assert text(laptop, "Docket.txt") == "docket 2\n", (
            "the night's changed file did not come down (the laptop's copy is the one it "
            "sent, which the bucket's older manifest records)")
        assert (laptop / "Docket.txt").stat().st_mtime_ns == (night / "Docket.txt").stat().st_mtime_ns
        assert text(laptop, new) == "b", "the night's new file did not come down"
        assert text(laptop, "legislation/2026/HB1.html") == "<p>one</p>", \
            "pull brought a file the laptop owns over the laptop's own"
        assert text(laptop, "site/committees.json") == "[]", "pull wrote into the laptop's site/"
        assert text(laptop, log) and text(laptop, f"logs/site-{today}.sha256"), \
            "the night's log did not reach logs/"
        assert text(laptop, f"reports/gc-changes-{today}.md") == "what the night found\n" \
            and text(laptop, f"reports/gc-changes-weekly-{today}.md"), \
            "the change lists did not reach reports/"
        assert not (laptop / "logs/other.log").exists(), "a log name pull does not know came down"
        assert text(laptop, "archive/cloud/last-night.json") and \
            not (laptop / "archive/last-night.json").exists(), \
            "the verdict went somewhere other than archive/cloud/"
        assert text(laptop, "archive/cloud/last-night.json") == text(night, "archive/last-night.json") \
            and text(laptop, "archive/cloud/last-dry-run.json") == \
            text(night, "archive/last-dry-run.json") and \
            not (laptop / "archive/last-dry-run.json").exists() and \
            "last-dry-run.json: a dry run, kept apart from the night's, of" in out, \
            "a dry run's verdict did not come down beside the night's, kept apart and said to be one"
        assert text(laptop, "archive/cloud/last-dry-weekly.json") == \
            text(night, "archive/last-dry-weekly.json") and \
            not (laptop / "archive/last-dry-weekly.json").exists() and \
            "last-dry-weekly.json: a dry run of the weekly, kept apart from the week's, of" in out, \
            "a dry weekly's verdict did not come down beside the week's, kept apart and said to be one"
        assert text(laptop, "archive/livestreams.json") == text(night, "archive/livestreams.json"), \
            "the night's livestream state did not reach archive/livestreams.json, where the " \
            "laptop's caption catch-up reads it"
        rec = json.loads(text(laptop, CL.PULL_RECORD))
        assert rec["refusal"]["read"] > 0 and "Docket.txt" in rec["kit"], rec.keys()
        assert rec["refusal"]["kind"] == "folder" and \
            rec["refusal"]["bucket"] == str(bucket.resolve()), \
            f"the read did not record which bucket it was: {rec['refusal']}"
        assert rec["full"]["epoch"] > 0, "a full pull was not recorded as one"
        R.MARK = laptop / "archive" / "refused.json"
        assert R.refusal_read() is None, "a folder bucket's read counted as the night's"
        code, out = pull(laptop)
        assert code == 0 and "files 0 taken" in out and "0 clashing" in out, out[-400:]

        # A second night; --changes-only says the laptop's copies are behind;
        # the laptop changed a night's file since.
        (night / "Docket.txt").write_text("docket 3\n", encoding="utf-8")
        (night / "narratives.json").write_text('{"night": 2}', encoding="utf-8")
        (night / log).write_text(f"{'=' * 74}\nGranite Record nightly  {today} 02:18\nagain\n",
                                 encoding="utf-8")
        assert call(night, "kit-up")[0] == 0
        code, out = pull(laptop, "--changes-only")
        assert code == 0 and "the last full pull was 0 hours ago" in out and \
            "2 of the night's 4 files changed since" in out, out[-500:]
        (laptop / "narratives.json").write_text('{"mine": 1}', encoding="utf-8")
        code, out = pull(laptop)
        assert code == 1 and "--take narratives.json" in out, out[-500:]
        assert text(laptop, "narratives.json") == '{"mine": 1}', "a clash was overwritten"
        assert text(laptop, "Docket.txt") == "docket 3\n", "a clash stopped the other files"
        assert "again" in text(laptop, log), "the newer copy of a log pull wrote did not replace it"
        code, out = pull(laptop, "--take", ".\\narratives.json")
        assert code == 0 and text(laptop, "narratives.json") == '{"night": 2}', out[-400:]
        assert text(laptop, f"{CL.SET_ASIDE}/{today}/narratives.json") == '{"mine": 1}', \
            "--take did not keep the laptop's copy"

        # A file written on the laptop while the pull was bringing it down is a
        # clash, not overwritten.
        (night / "Docket.txt").write_text("docket 4\n", encoding="utf-8")
        assert call(night, "kit-up")[0] == 0

        class Busy(ReadOnly):
            def get_file(self, key, dst, size=None):
                if key == "kit/Docket.txt":
                    (laptop / "Docket.txt").write_text("written while pull ran\n",
                                                       encoding="utf-8")
                super().get_file(key, dst, size=size)
        code, out = pull(laptop, kind=Busy)
        assert code == 1 and "Docket.txt" in out and "while this pull ran" in out, out[-500:]
        assert text(laptop, "Docket.txt") == "written while pull ran\n", \
            "pull replaced a file written while it ran"
        code, out = pull(laptop, "--take", str(laptop / "Docket.txt"))
        assert code == 0 and text(laptop, "Docket.txt") == "docket 4\n", out[-400:]

        # A log the laptop wrote itself is not pull's to replace.
        (bucket / "logs/2000-01-03").mkdir(parents=True)
        (bucket / "logs/2000-01-03/gc-changes-2000-01-03.md").write_text("the bucket's\n",
                                                                          encoding="utf-8")
        (laptop / "reports/gc-changes-2000-01-03.md").write_text("the laptop's own\n",
                                                                  encoding="utf-8")
        code, out = pull(laptop, "--day", "2000-01-03")
        assert code == 1 and "reports/gc-changes-2000-01-03.md" in out, out[-400:]
        assert text(laptop, "reports/gc-changes-2000-01-03.md") == "the laptop's own\n"

        # The morning triage's pull: the change list and the verdict, nothing else.
        triage = tmp / "triage"
        triage.mkdir()
        _pull_fixture(triage, real)
        code, out = pull(triage, "--changes-only")
        assert code == 0, out[-400:]
        assert text(triage, f"reports/gc-changes-{today}.md") and \
            text(triage, "archive/cloud/last-night.json"), "--changes-only missed what it is for"
        assert not (triage / log).exists() and text(triage, "Docket.txt") == "docket 1\n", \
            "--changes-only took more than the change list and the verdict"
        assert "NO FULL PULL has run here" in out, "--changes-only did not say no full pull ran"
        os.environ["GITHUB_ACTIONS"] = "true"
        code, out = pull(triage, "--changes-only")
        assert code == 1 and "laptop's" in out, "pull ran on GitHub's machine"
        os.environ.pop("GITHUB_ACTIONS")
        (triage / ".build.lock").write_text("x", encoding="utf-8")
        code, out = pull(triage, "--changes-only")
        assert code == 1 and "fresh" in out, "pull ran beside a build"
        (triage / ".build.lock").unlink()

        # The night's refusal reaches the laptop, saying what it stops; of
        # two, the newer stands.
        (night / "archive/refused.json").write_text(refusal(200, "night"), encoding="utf-8")
        assert call(night, "state-up")[0] == 0
        code, out = pull(laptop, "--changes-only")
        assert code == 0 and "THE BUCKET HOLDS A REFUSAL" in out, out[-400:]
        assert "older than 24 hours" in out and "hand fetches here are not stopped" in out \
            and "clear-refusal" in out, f"pull did not say what an old refusal stops: {out[-500:]}"
        assert '"night"' in text(laptop, "archive/refused.json"), "the night's refusal did not come down"
        (laptop / "archive/refused.json").write_text(refusal(300, "laptop"), encoding="utf-8")
        assert pull(laptop, "--changes-only")[0] == 0
        assert '"laptop"' in text(laptop, "archive/refused.json"), "a newer refusal here was replaced"
        (laptop / "archive/refused.json").write_text(refusal(100, "older"), encoding="utf-8")
        assert pull(laptop, "--changes-only")[0] == 0
        assert '"night"' in text(laptop, "archive/refused.json"), "the bucket's newer refusal did not stand"
        assert '"older"' in text(laptop, f"{CL.SET_ASIDE}/{today}/archive/refused.json"), \
            "the older refusal was dropped rather than set aside"

        # A refusal recorded here while the pull reads the bucket's -- a
        # fetch's note() between the look and the write -- is not written
        # over: the pull creates the file, and compares the two when it
        # cannot. create_whole itself refuses a file that is there.
        probe_file = tmp / "create-probe.json"
        probe_file.write_text("mine", encoding="utf-8")
        try:
            CL.create_whole(probe_file, b"theirs")
            raise AssertionError("create_whole wrote over a file that was there")
        except FileExistsError:
            pass
        assert probe_file.read_text(encoding="utf-8") == "mine" and \
            not probe_file.with_name(probe_file.name + ".part").exists(), \
            "create_whole changed the file that was there, or left its part file"
        real_create = CL.create_whole

        def landing(content):
            def create(dst, data):
                dst.write_text(content, encoding="utf-8")
                return real_create(dst, data)
            return create
        for landed, stays in ((refusal(400, "landed mid-pull"), '"landed mid-pull"'),
                              (refusal(150, "older mid-pull"), '"night"')):
            (laptop / "archive/refused.json").unlink()
            CL.create_whole = landing(landed)
            try:
                code, out = pull(laptop, "--changes-only")
            finally:
                CL.create_whole = real_create
            assert code == 0 and "while this pull read" in out, out[-400:]
            assert stays in text(laptop, "archive/refused.json"), (
                f"of a refusal recorded mid-pull and the bucket's, the wrong one stands here: "
                f"{text(laptop, 'archive/refused.json')}")
        assert any("older mid-pull" in p.read_text(encoding="utf-8")
                   for p in (laptop / CL.SET_ASIDE).rglob("refused.json*")), \
            "a refusal recorded mid-pull, older than the bucket's, was dropped, not set aside"
        (laptop / "archive/refused.json").unlink()
        assert pull(laptop, "--changes-only")[0] == 0 and \
            '"night"' in text(laptop, "archive/refused.json"), \
            "with nothing recorded mid-pull, the bucket's refusal was not created here"

        # The laptop's refusal reaches the bucket, from refusal.note() itself.
        # `mine` is a bucket of the night's (a verdict in it, from before
        # yesterday) that holds no refusal yet.
        away, mine = tmp / "away", tmp / "mine"
        away.mkdir()
        _pull_fixture(away, real)
        (mine / "state").mkdir(parents=True)
        (mine / "state/last-night.json").write_text(json.dumps(
            {"kind": "nightly", "day": "2000-01-01", "clean": True}), encoding="utf-8")
        (away / "archive/runs-in-the-cloud.json").write_text("{}", encoding="utf-8")
        R.MARK, R.CLOUD_BUCKET = away / "archive" / "refused.json", str(mine)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            R.note("fetch_x", "HTTP Error 403: Forbidden")
        sent = (mine / "state/refused.json")
        assert sent.exists() and sent.read_bytes() == R.MARK.read_bytes(), err.getvalue()[-300:]
        assert not (away / CL.UNSENT).exists(), "the unsent marker stayed after a send"
        # ... and when the bucket cannot be reached, note() still returns, loudly,
        # and the marker holds until send-refusal has sent it. With no folder
        # bucket, a temp folder is not the repository that holds secrets.json,
        # so the real bucket is never tried at all.
        sent.unlink()
        R.CLOUD_BUCKET = None
        with contextlib.redirect_stderr(io.StringIO()) as err:
            R.note("fetch_x", "HTTP Error 403: Forbidden")
        assert "THE BUCKET HAS NOT BEEN TOLD" in err.getvalue() and (away / CL.UNSENT).exists(), \
            "an unsent refusal was not loud, or left no marker"
        assert "secrets.json" in err.getvalue(), \
            f"a temp folder's refusal was not refused the real bucket: {err.getvalue()[-300:]}"
        # Refused before any bucket is made: the recorder raises rather than
        # hand on to the real make_bucket, and GRANITE_NO_BUCKET stays set,
        # so a send_refusal that lost its secrets.json test could reach
        # neither R2 nor anything else from here.
        made = []

        def recorder(*a, **k):
            made.append(a)
            raise AssertionError("send_refusal made a bucket for a temp folder's refusal")
        CL.make_bucket = recorder
        try:
            CL.send_refusal(away)
            raise AssertionError("a temp folder's refusal was sent without a folder bucket")
        except CL.Failed as e:
            assert "secrets.json" in str(e) and not made, (str(e), made)
        finally:
            CL.make_bucket = saved[6]
        assert os.environ.get(CL.NO_BUCKET) == "1", "GRANITE_NO_BUCKET was lifted"
        # home() is the checkout that HOLDS secrets.json: keys.PATH names the
        # file at the checkout's root, wherever keys.py sits, whether it is
        # there or not.
        import keys
        kept_path, homeless = keys.PATH, tmp / "homeless"
        homeless.mkdir()
        try:
            keys.PATH = homeless / "secrets.json"
            assert not CL.home(homeless), "a folder with no secrets.json in it counted as home"
            keys.PATH.write_text("{}", encoding="utf-8")
            assert CL.home(homeless) and not CL.home(away), \
                "home() did not find secrets.json's folder"
        finally:
            keys.PATH = kept_path
        code, out = pull(away, "--changes-only", bucket=mine)
        assert code == 1 and "send-refusal" in out and "IS NOT IN THE BUCKET" in out, out[-400:]
        assert "STALE" in out, f"a verdict from 2000 was not called stale: {out[-400:]}"
        code, out = call(away, "send-refusal", bucket=mine)
        assert code == 0 and sent.exists() and not (away / CL.UNSENT).exists(), out[-300:]
        assert pull(away, "--changes-only", bucket=mine)[0] == 0

        # A newer laptop refusal behind an older one in the bucket is not lost.
        older = refusal(__import__("time").time() - 3600, "older in the bucket")
        sent.write_text(older, encoding="utf-8")
        R.CLOUD_BUCKET = str(mine)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            R.note("fetch_y", "HTTP Error 403: Forbidden")
        marker = away / CL.UNSENT
        assert "HAS NOT TAKEN THIS REFUSAL" in err.getvalue() and marker.exists() and \
            "waiting behind" in marker.read_text(encoding="utf-8"), err.getvalue()[-400:]
        assert sent.read_text(encoding="utf-8") == older, "the bucket's refusal was overwritten"
        code, out = call(away, "send-refusal", bucket=mine)
        assert code == 1 and "waiting behind" in out and marker.exists(), out[-300:]
        code, out = pull(away, "--changes-only", bucket=mine)
        assert code == 0 and marker.exists() and "waits behind" in out, out[-400:]
        # Clearing the bucket's leaves the laptop's newer one, in force and
        # named by the marker, in no bucket: the clearing stands, and it
        # exits 1 saying to send it.
        code, out = call(away, "clear-refusal", bucket=mine)
        assert code == 1 and "HOLDS A REFUSAL THE BUCKET DOES NOT" in out and \
            "send-refusal" in out and "waiting behind" in out, \
            f"clear-refusal did not fail naming the laptop's refusal: {out[-400:]}"
        assert not sent.exists(), "clear-refusal did not clear the bucket's refusal"
        code, out = pull(away, "--changes-only", bucket=mine)
        assert code == 1 and "IS NOT IN THE BUCKET" in out and "send-refusal" in out, out[-400:]
        code, out = call(away, "send-refusal", bucket=mine)
        assert code == 0 and sent.read_bytes() == R.MARK.read_bytes() and not marker.exists(), \
            out[-300:]

        # clear-refusal's status, case by case, in a folder of its own: 1 only
        # when this machine's refusal waited behind the one cleared -- newer
        # and in force, or named by the marker -- and 0 otherwise.
        third, b3 = tmp / "third", tmp / "b3"
        third.mkdir()
        _pull_fixture(third, real)
        now_ = __import__("time").time()
        for here_, bucket_, marked, want in (
                (refusal(now_ - 60, "newer, in force"), refusal(now_ - 3600, "b"), False, 1),
                (refusal(now_ - 30 * 3600, "newer, past 24h"), refusal(now_ - 40 * 3600, "b"),
                 False, 0),
                (refusal(now_ - 7200, "older, marked"), refusal(now_ - 3600, "b"), True, 1),
                (refusal(now_ - 7200, "older, unmarked"), refusal(now_ - 3600, "b"), False, 0),
                (None, refusal(now_ - 3600, "b"), False, 0)):
            (b3 / "state").mkdir(parents=True, exist_ok=True)
            (b3 / "state/refused.json").write_text(bucket_, encoding="utf-8")
            (third / "archive/refused.json").unlink(missing_ok=True)
            if here_:
                (third / "archive/refused.json").write_text(here_, encoding="utf-8")
            (third / CL.UNSENT).unlink(missing_ok=True)
            if marked:
                (third / CL.UNSENT).parent.mkdir(parents=True, exist_ok=True)
                (third / CL.UNSENT).write_text("{}", encoding="utf-8")
            code, out = call(third, "clear-refusal", bucket=b3)
            assert code == want and not (b3 / "state/refused.json").exists(), (
                f"clear-refusal with this machine's refusal "
                f"{json.loads(here_)['where'] if here_ else 'absent'!r} "
                f"{'and the marker ' if marked else ''}exited {code}, not {want}: {out[-300:]}")
            assert want == 0 or "send-refusal" in out, out[-300:]

        # A folder bucket in the stood-down repository that holds secrets.json
        # is refused unless the test says so.
        CL.home = lambda root: Path(root).resolve() == away.resolve()
        try:
            code, out = pull(away, "--changes-only", bucket=mine)
            assert code == 1 and "--allow-local-bucket" in out, out[-300:]
            assert pull(away, "--changes-only", "--allow-local-bucket", bucket=mine)[0] == 0
        finally:
            CL.home = saved[5]

        # state-up reports a marker it cannot lift: this machine's refusal,
        # which its record says it sent, is not in the (empty) bucket...
        marker.write_text("{}", encoding="utf-8")
        code, out = call(away, "state-up", bucket=tmp / "nothing")
        assert code == 1 and "send-refusal" in out and marker.exists(), \
            f"state-up did not report the unsent refusal: {out[-300:]}"
        # ... and lifts one with no refusal here left to send.
        (away / "archive/refused.json").unlink()
        code, out = call(away, "state-up", bucket=tmp / "nothing")
        assert code == 0 and not marker.exists(), \
            f"state-up kept a marker with no refusal on file here to send: {out[-300:]}"
        assert not writes, "a pull wrote to the bucket: " + "; ".join(writes[:3])
        return "ok", (f"{len(reached)} functions pull reaches, none writing to the bucket; the "
                      "night's files, logs, change lists and verdict come down, the laptop's "
                      "files and site/ stay, a clash (one written mid-pull too) is named and "
                      "--take settles it however it is written, an empty bucket is no read, "
                      "and a refusal crosses both ways -- loudly when it cannot, and waiting "
                      "behind an older one rather than lost")
    finally:
        CL.open_bucket, R.MARK, R.CLOUD_BUCKET = saved[:3]
        CL.home, CL.make_bucket = saved[5], saved[6]
        for name, v in (("GITHUB_ACTIONS", saved[3]), (CL.NO_BUCKET, saved[4])):
            if v is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = v
        shutil.rmtree(tmp, ignore_errors=True)


@check("cloud", "a stood-down laptop's nightly check reads the nights pulled from GitHub")
def _pulled_nights_read():
    """_nightly_logs is a data check, so its reader of pulled nights would be
    tested only where there is data. Here it is tested on made-up pulls, under
    --code: never pulled, a fresh night, an old pull, a fresh pull of an old
    night, a verdict newer than the logs, and a week that installed nothing."""
    _pulled_night_selftest()
    _full_pull_selftest()
    return "ok", ("never pulled skips for 48 hours after the stand-down and fails after; an old "
                  "night fails, naming the pull or the Actions tab as the cause; a fresh "
                  "verdict counts; a week of nothing installed fails; a full pull over 48 "
                  "hours old fails, and a changes-only one is not a full one")


@check("cloud", "nothing preflight runs can reach the real bucket", needs=("cloud",))
def _no_bucket_here(CL):
    """preflight sets GRANITE_NO_BUCKET for itself and everything it runs,
    because since 26 September a refusal recorded on a stood-down laptop goes
    to the bucket, and a check that drove one in the wrong folder would stop
    the real night. With it set, cloud.py refuses R2 -- and says why -- while
    a folder bucket still works; the send refusal.note() makes goes through
    the same door."""
    saved = os.environ.get(CL.NO_BUCKET)
    tmp = Path(tempfile.mkdtemp(prefix="gr-nobucket-"))
    try:
        os.environ[CL.NO_BUCKET] = "1"
        try:
            CL.make_bucket(None, 1)
            raise AssertionError("cloud.make_bucket reached for R2 with GRANITE_NO_BUCKET set")
        except CL.Failed as e:
            assert CL.NO_BUCKET in str(e), str(e)
        assert isinstance(CL.make_bucket(str(tmp / "bucket"), 1), CL.FolderBucket)
        shutil.copy(CL.KIT_FILE, tmp / CL.KIT_FILE)
        code, out = _cloud_call(CL, "state-down", "--root", str(tmp))
        assert code == 1 and CL.NO_BUCKET in out, out[-300:]
        src = _source(CL.__file__)
        assert src.count("R2Bucket(") == 1 and "return R2Bucket(keys.r2()" in src, (
            "R2Bucket is made somewhere other than make_bucket, past GRANITE_NO_BUCKET")
    finally:
        if saved is None:
            os.environ.pop(CL.NO_BUCKET, None)
        else:
            os.environ[CL.NO_BUCKET] = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", "R2 refused with GRANITE_NO_BUCKET set, saying so; a folder bucket still made"


# The page the General Court's firewall serves in place of the one asked for,
# often with a 200; refusal.BLOCKED is what reads it.
_BLOCK_PAGE = "<html><title>Web Page Blocked</title>Attack ID: 20000001</html>"


@check("build", "every script that consults refusal.py records a refusal it meets, and stops")
def _every_fetcher_notes_refusal():
    """refusal.check() stops a fetch while a refusal is on file; refusal.note()
    is what puts one there. Until 7 October 2026 fifteen of the twenty-five
    scripts that check never noted: fetch_archive_bills, fetch_bill_status,
    fetch_bill_text, fetch_committee_details, fetch_committee_reports,
    fetch_journals, fetch_members, fetch_schedule, fetch_session,
    fetch_testimony, resolve_members, check_civics_links and the three
    probe_*.py that ask the web server. A 403 they met ended that run, or was
    retried, or was counted and the next page asked for -- and in every case
    the next fetch to start asked the same address again, which is the
    behaviour refusal.py exists to stop. fetch_bill_status and fetch_bill_text
    retried a 403 two and four times, on bill_status/legacy/bs2016/, the path
    the General Court's IT office asked be requested lightly.

    THE RULE, READ FROM THE CODE: a script that calls refusal.check() calls
    refusal.note() too -- an ast.Call, with refusal imported, as the check
    above reads refusal.check() -- so a new fetcher is held by it the day it is
    written. A note in a comment or a string is not one.

    AND WHAT IT DOES, for the fifteen (fourteen since fetch_testimony was
    retired on 7 October): each is driven through its main() in a
    temp folder on fake answers -- a 403, the block page served as a 200, and
    two dropped connections where one does not end the run -- and must stop
    with status 2, the refusal on file, after the one request that met it.
    Nothing reaches the network: urlopen, urlretrieve and an opener a script
    keeps as _OPENER are fakes for the drive, and a socket opened past
    them raises. refusal.MARK is the temp folder's, so no refusal is written
    here and none is sent to the bucket (refusal._governing reads the folder
    beside MARK).

    EVERY PATH THAT NOTES, NOT ONLY THE FIRST REQUEST (the review of 7
    October 2026). Driven at its first request alone, fetch_schedule's event
    pages and fetch_committee_reports' calendar PDFs -- the loops that make
    nearly all their requests -- could lose their note() and pass, and
    check_civics_links and fetch_bill_text's --embed-check each went on past
    a second dropped connection. So a script's later loop is driven too, its
    first requests answered with a page that leads there (`served`), and so
    are the one-request modes that note (--bill, --probe, --embed-check).

    AND NOTHING IT DID NOT MEET. Answered 404 everywhere, no script may
    record a refusal; nor may one that stops at its first failure record a
    single dropped connection, which is not one; nor check_civics_links a 403
    from nh.gov, which is that server's.

    AND TWO THAT NOTED AND WENT ON (7 October 2026): fetch_rollcall_parties
    stopped only at its second refusal and read a 503, the block page and a
    dropped connection as a page not there, and fetch_lsrs did not notice the
    block page and stopped on a refusal with status 1. Both are driven here,
    and on a 503 too, never run against the address.
    """
    import contextlib
    import http.client
    import importlib
    import io
    import socket
    import time as _time
    import types
    import urllib.error
    import urllib.request
    import refusal

    def calls(tree, attr):
        imported = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                    for a in n.names}
        return "refusal" in imported and any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == attr and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "refusal" for n in ast.walk(tree))

    def read(src):
        """(calls refusal.check(), calls refusal.note())."""
        tree = ast.parse(src)
        return calls(tree, "check"), calls(tree, "note")
    probes = {
        "a fetcher that checks and notes":
            ('import refusal\nrefusal.check("x")\ntry:\n    ask()\nexcept Exception as e:\n'
             '    refusal.note("x", str(e))\n    raise SystemExit(2)\n', (True, True)),
        "a fetcher that checks and never notes":
            ('import refusal\nrefusal.check("x")\nask()\n', (True, False)),
        "a note that is only a comment and a string":
            ('import refusal\nrefusal.check("x")\n# refusal.note("x", "403")\n'
             'WHY = "refusal.note(\'x\', \'403\')"\n', (True, False)),
        "a script that neither checks nor notes":
            ('import refusal\nprint(refusal.MARK)\n', (False, False)),
    }
    for what, (src, want) in probes.items():
        assert read(src) == want, f"the reader got {what} wrong: {read(src)}"

    checkers, missing = [], []
    for p in _paths.code_files("*.py", dirs=_paths.SCRIPT_DIRS):
        if _in_suite(p):
            continue
        try:
            tree = _parsed(p)
        except SyntaxError as e:
            raise AssertionError(f"{p.name} will not parse, so whether it records a "
                                 f"refusal cannot be read: {e}")
        if calls(tree, "check"):
            checkers.append(p.name)
            if not calls(tree, "note"):
                missing.append(p.name)
    # The floor is the check above's: every script that asks gc.nh.gov calls
    # refusal.check(), so as many call it as ask. Fewer is a code folder not read.
    assert len(checkers) >= _ASKS_GC_FLOOR, (
        f"{len(checkers)} scripts call refusal.check(); on 23 October {_ASKS_GC_FLOOR} did: "
        "the code folders are not being read")
    assert not missing, (
        "these call refusal.check() and never refusal.note(), so a refusal they meet "
        "stops that run and nothing else -- the next fetch asks the same address "
        "again:\n    " + "\n    ".join(missing)
        + "\n  Read the failure with refusal.classify(), and on \"refused\" (or a second "
          "\"dropped\") call\n  refusal.note(\"<script>\", why) and stop with status 2, as "
          "fetch_committees.py does.")

    # ---- the fourteen, driven -----------------------------------------------
    def files(**named):
        def write(root):
            for rel, text in named.items():
                f = root / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(text if isinstance(text, str) else json.dumps(text),
                             encoding="utf-8")
        return write
    two_bills = {"2025-2026": {"HB1": {"lsr_num": "0001", "lsr_year": "2025"},
                               "HB2": {"lsr_num": "0002", "lsr_year": "2025"}}}
    gc_links = [("a", "https://gc.nh.gov/a", "s"), ("b", "https://gc.nh.gov/b", "s")]
    # script: (arguments, fixture, {answer: requests made before it stops});
    # "drop" only where one dropped connection does not end the run.
    drives = {
        "fetch_archive_bills": (["--year", "2024"], None, {"403": 1, "block": 1}),
        "fetch_bill_status": (["--delay", "0"], files(**{
            "data/bills.json": two_bills, "data/sponsors.json": {"2025-2026": {}}}),
            {"403": 1, "block": 1, "drop": 2}),
        "fetch_bill_text": (["--delay", "0"], files(**{
            "data/bills.json": two_bills,
            "bill_status.json": {"2025-2026": {
                "HB1": {"text_pdf": "https://gc.nh.gov/x?id=1"},
                "HB2": {"text_pdf": "https://gc.nh.gov/x?id=2"}}}}),
            {"403": 1, "block": 1, "drop": 2}),
        "fetch_committee_details": (["--delay", "0"], files(**{"committees.json": {"H": [
            {"code": "1", "name": "A", "url": "https://gc.nh.gov/h1"},
            {"code": "2", "name": "B", "url": "https://gc.nh.gov/h2"}]}}),
            {"403": 1, "block": 1, "drop": 2}),
        "fetch_committee_reports": (["--year", "2026"], None, {"403": 1, "block": 1}),
        "fetch_journals": (["--year", "2026", "--delay", "0"], None,
                           {"403": 1, "block": 1, "drop": 2}),
        "fetch_members": (["--delay", "0"], files(**{"data/legislators.json": [
            {"id": "1", "name": "A"}, {"id": "2", "name": "B"}]}),
            {"403": 1, "block": 1, "drop": 2}),
        "fetch_schedule": ([], None, {"403": 1, "block": 1}),
        "fetch_session": (["--year", "2020", "--max-lsr", "3", "--delay", "0"], None,
                          {"403": 1, "block": 1, "drop": 2}),
        "resolve_members": (["--session", "2026", "--delay", "0"], files(**{
            "data/legislators.json": [], "RollCallHistory.txt": "2026|H|1|99||x|Yea|x\n",
            "RollCallSummary.txt": "2026|H|1|x|HB1\n", "Docket.txt": "x|0123|x|HB1|x\n"}),
            {"403": 1, "block": 1, "drop": 2}),
        # A HEAD that drops is asked again as a GET, and the two are the two
        # dropped connections that end it, on its first link. (A HEAD answered
        # with the block page has no page to read; a GET's is read.)
        "check_civics_links": (["--delay", "0"], None, {"403": 1, "drop": 2}),
        "probe_archive_shape": (["--delay", "0"], files(**{"archive_sample_ids.json": {
            "2016": [{"bill": "HB1", "lsr": "1"}, {"bill": "HB2", "lsr": "2"}]}}),
            {"403": 1, "block": 1, "drop": 2}),
        "probe_calendars": ([], None, {"403": 1, "block": 1}),
        "probe_schema": (["--dir", "."], None, {"403": 1, "block": 1, "drop": 2}),
        # AND TWO THAT NOTED BUT DID NOT STOP (7 October 2026). The roll call
        # party fetch asked once more after a 403 (--stop-refused 2) and read
        # a 503, the block page and a dropped connection as a missing page;
        # the LSR fetch did not notice the block page, and on its postback
        # asked for the results page next. Two roll calls, a chamber each.
        "fetch_rollcall_parties": (["--budget", "5", "--delay", "0"], files(**{
            "records/rollcalls/RollCallSummary_2004.txt":
                "2004|H|46|x|HB1|200|150|0|50|x\n2004|S|12|x|SB1|20|4|0|0|x\n"}),
            {"403": 1, "503": 1, "block": 1, "drop": 2}),
        "fetch_lsrs": ([], None, {"403": 1, "503": 1, "block": 1}),
    }

    class Page:
        """An answer with a 200: the block page, or a page served first."""
        def __init__(self, body):
            self.body, self.status, self.headers = body.encode(), 200, http.client.HTTPMessage()

        def read(self, n=-1):
            out = self.body if n is None or n < 0 else self.body[:n]
            self.body = self.body[len(out):]
            return out

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def answer(how, url):
        if how in ("403", "404", "503"):
            raise urllib.error.HTTPError(url, int(how), {"403": "Forbidden", "404": "Not Found",
                                                         "503": "Service Unavailable"}[how],
                                         http.client.HTTPMessage(), io.BytesIO(b""))
        if how == "drop":
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return Page(_BLOCK_PAGE)

    def no_socket(*a, **k):
        raise AssertionError("a fetcher driven by preflight opened a socket")

    here = os.getcwd()
    saved = (urllib.request.urlopen, urllib.request.urlretrieve, socket.create_connection,
             socket.socket.connect, _time.sleep, refusal.MARK, refusal.LOCK, sys.argv)
    present = {n: v for n, v in drives.items() if _paths.locate(f"{n}.py").exists()}
    mods = {n: importlib.import_module(n) for n in present}
    # Each drive: (script, which path, arguments, fixture, {answer: requests made
    # before it stops}, pages served before the answer, the links
    # check_civics_links is given). The first requests first, then the later
    # loops and the one-request modes that note too.
    plan = [(n, "", argv, fx, hows, (), None) for n, (argv, fx, hows) in present.items()]
    if "fetch_schedule" in present:
        # The schedule's list of events, answered, leads to the event pages.
        listing = json.dumps({"d": [{"title": f"HOUSE EDUCATION : GP 23{k}",
                                     "url": f"eventDetails.aspx?event={k}",
                                     "start": "2026-01-13T10:00:00"} for k in (1, 2)]})
        plan.append(("fetch_schedule", "its event pages", [], None,
                     {"403": 2, "block": 2, "drop": 3}, (listing,), None))
    if "fetch_committee_reports" in present:
        # The calendar list, answered with two of the year's, leads to the PDFs.
        index = (f'<select name="{mods["fetch_committee_reports"].SEL_DOC}">'
                 '<option value="HC1.pdf">No 1 January 2 2026</option>'
                 '<option value="HC2.pdf">No 2 January 9 2026</option></select>')
        plan.append(("fetch_committee_reports", "its calendar PDFs", ["--year", "2026"], None,
                     {"403": 2, "block": 2, "drop": 3}, (index,), None))
    if "fetch_lsrs" in present:
        # The search page, answered with its CSV link, leads to the postback.
        search = ('<a href="javascript:__doPostBack(&#39;ctl00$pageBody$lnkCVS&#39;,&#39;&#39;)">'
                  'Download CSV File</a>')
        plan.append(("fetch_lsrs", "its postback", [], None,
                     {"403": 2, "503": 2, "block": 2}, (search,), None))
    for name, what, argv, hows in (
            ("fetch_bill_status", "--bill", ["--bill", "HB1"], {"403": 1, "block": 1}),
            ("fetch_bill_text", "--probe", ["--probe", "HB1"], {"403": 1, "block": 1}),
            ("fetch_bill_text", "--embed-check", ["--embed-check", "--probe", "HB1"],
             {"403": 1, "block": 1, "drop": 2}),
            ("fetch_members", "--probe", ["--probe", "1"], {"403": 1, "block": 1}),
            ("fetch_session", "--probe", ["--year", "2020", "--probe"], {"403": 1, "block": 1})):
        if name in present:
            plan.append((name, what, argv, present[name][1], hows, (), None))
    nh_links = [("a", "https://www.nh.gov/a", "s"), ("b", "https://www.nh.gov/b", "s")]
    if "check_civics_links" in present:
        # nh.gov's refusals are that server's: nothing to record, only quiet answers.
        plan.append(("check_civics_links", "nh.gov's links", ["--delay", "0"], None, {}, (),
                     nh_links))
    wrong, runs, quiet_runs = [], 0, 0
    try:
        socket.create_connection, socket.socket.connect = no_socket, no_socket
        _time.sleep = lambda s: None
        for name, what, argv, fixture, hows, served, links in plan:
            M = mods[name]
            # What must NOT be recorded: a 404 everywhere; one dropped
            # connection, where the run stops at its first failure; and for
            # nh.gov's links, a 403 or two dropped connections too.
            quiet = ["404"] + ([] if "drop" in hows else ["drop"]) + (["403"] if links else [])
            for how, want in [*hows.items(), *((q, None) for q in quiet)]:
                tmp = Path(tempfile.mkdtemp(prefix=f"gr-note-{name}-"))
                asked = []

                def fake_open(req, *a, **k):
                    url = getattr(req, "full_url", req)
                    asked.append(url)
                    if len(asked) <= len(served):
                        return Page(served[len(asked) - 1])
                    return answer(how, url)

                def fake_retrieve(url, filename=None, *a, **k):
                    page = fake_open(url)
                    Path(filename).write_bytes(page.read())
                    return filename, page.headers
                try:
                    os.chdir(tmp)
                    (tmp / "archive").mkdir()
                    refusal.MARK, refusal.LOCK = tmp / "archive" / "refused.json", tmp / "archive" / ".lock"
                    urllib.request.urlopen, urllib.request.urlretrieve = fake_open, fake_retrieve
                    if fixture:
                        fixture(tmp)
                    patched = {}
                    if hasattr(M, "_OPENER"):
                        patched["_OPENER"] = types.SimpleNamespace(open=fake_open)
                    if name == "check_civics_links":
                        given = list(links or gc_links)
                        patched["links"] = lambda: list(given)
                    old = {k: getattr(M, k) for k in patched}
                    for k, v in patched.items():
                        setattr(M, k, v)
                    sys.argv = [f"{name}.py", *argv]
                    out = io.StringIO()
                    try:
                        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                            rc = M.main()
                    except SystemExit as e:
                        rc = e.code
                    except Exception as e:                      # noqa: BLE001
                        # A run a failure ends by raising: that is its status.
                        rc = f"{type(e).__name__}: {e}"[:80]
                    finally:
                        for k, v in old.items():
                            setattr(M, k, v)
                    runs += 1
                    noted = refusal.MARK.exists()
                    said = {"403": "a 403", "503": "a 503", "404": "a 404 everywhere",
                            "block": "the block page",
                            "drop": ("two dropped connections" if want is not None
                                     else "a dropped connection")}[how]
                    if links and how in ("403", "drop"):
                        said = f"nh.gov's {'403s' if how == '403' else 'dropped connections'}"
                    label = f"{name}{f' ({what})' if what else ''} on {said}"
                    if want is None:
                        quiet_runs += 1
                        if noted:
                            wrong.append(f"{label}: RECORDED A REFUSAL IT DID NOT MEET "
                                         f"-- {out.getvalue().strip()[-160:]!r}")
                    elif not (rc == 2 and noted and len(asked) == want):
                        wrong.append(f"{label}: exit {rc!r}, {len(asked)} request(s) where "
                                     f"{want} stop it, "
                                     f"{'refusal recorded' if noted else 'NO REFUSAL RECORDED'} "
                                     f"-- {out.getvalue().strip()[-160:]!r}")
                finally:
                    os.chdir(here)
                    urllib.request.urlopen, urllib.request.urlretrieve = saved[0], saved[1]
                    shutil.rmtree(tmp, ignore_errors=True)
    finally:
        os.chdir(here)
        (urllib.request.urlopen, urllib.request.urlretrieve, socket.create_connection,
         socket.socket.connect, _time.sleep, refusal.MARK, refusal.LOCK, sys.argv) = saved
    assert not wrong, ("a fetcher did not record a refusal it met and stop, or recorded one "
                       "it did not meet:\n    " + "\n    ".join(wrong))
    return "ok", (f"all {len(checkers)} scripts that call refusal.check() call refusal.note(); "
                  f"{len(present)} driven down {len(plan)} paths on a 403, the block page and "
                  f"dropped connections ({runs - quiet_runs} runs) record it and stop after the "
                  f"request that met it, and record nothing on a 404, a single dropped "
                  f"connection or nh.gov's 403 ({quiet_runs} runs)")


@check("build", "a laptop that has handed the nightly to GitHub runs none of it, and GitHub's "
       "own machine is never stood down", needs=("refusal", "nightly", "fetch_archive_db"))
def _stand_down(R, NI, FA):
    """archive/runs-in-the-cloud.json, written by `refusal.py --stand-down`, makes the
    nightly, the daily snapshot, publish.bat and the fetchers whose files
    GitHub's workflows own refuse on the laptop, each saying why: two machines
    running one nightly is two writers of every file it makes. It must never
    apply on GitHub's machine, whatever arrives there. Each script is run far
    enough to prove it stops, with whatever would ask anybody anything
    replaced by something that fails the check instead."""
    import contextlib
    import io
    import probe_db
    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-standdown-"))
    saved_env = os.environ.get("GITHUB_ACTIONS")
    saved_argv = sys.argv

    def refuses(fn, argv):
        sys.argv = argv
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            try:
                fn()
            except SystemExit as e:
                return e.code, err.getvalue()
        return None, err.getvalue()

    def asked(*_a, **_k):
        raise AssertionError("a stood-down script went on to ask for something")

    import fetch_committees as FC
    import fetch_committee_members_db as FCM
    import fetch_lsrs as FL
    import fetch_members_db as FM
    import snapshot_gencourt as SG
    saved = (FC.get, SG.run, probe_db.run, probe_db.run_to_file, FL.get)
    try:
        os.chdir(tmp)
        os.environ.pop("GITHUB_ACTIONS", None)
        assert R.stood_down() is None and R.stand_down("x") is None, "stood down with no file"
        Path("archive").mkdir()
        R.STANDDOWN.write_text('{"since": "2026-09-26T09:00:00"}', encoding="utf-8")
        code, said = refuses(lambda: R.stand_down("The nightly"), ["x"])
        assert code == R.STOOD_DOWN == 4 and "2026-09-26" in said and \
            str(R.STANDDOWN) in said, (code, said)
        FC.get = SG.run = probe_db.run = probe_db.run_to_file = FL.get = asked
        for label, fn, argv in (
                ("nightly.py", NI.main, ["nightly.py", "--no-fetch"]),
                ("nightly.py --runner", NI.main, ["nightly.py", "--runner", "--no-fetch"]),
                ("snapshot_gencourt.py", SG.main, ["snapshot_gencourt.py", "--into", "."]),
                ("fetch_committees.py", FC.main, ["fetch_committees.py"]),
                ("fetch_committee_members_db.py", FCM.main, ["fetch_committee_members_db.py"]),
                ("fetch_members_db.py", FM.main, ["fetch_members_db.py"]),
                ("fetch_lsrs.py", FL.main, ["fetch_lsrs.py"]),
                ("fetch_archive_db.py for the study views", FA.main,
                 ["fetch_archive_db.py", "--only", "StatStudMeetings", "--only", "vStatStudTemp"])):
            code, said = refuses(fn, argv)
            assert code == R.STOOD_DOWN, f"{label} did not stand down: {code} {said[-200:]}"
        assert not Path(".nightly.lock").exists(), "the stood-down nightly took its lock"
        os.environ["GITHUB_ACTIONS"] = "true"
        assert R.stood_down() is None and R.stand_down("x") is None, \
            "GitHub's own machine was stood down by a copy of the file"
    finally:
        FC.get, SG.run, probe_db.run, probe_db.run_to_file, FL.get = saved
        sys.argv = saved_argv
        if saved_env is None:
            os.environ.pop("GITHUB_ACTIONS", None)
        else:
            os.environ["GITHUB_ACTIONS"] = saved_env
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)

    assert set(FA.GITHUB_VIEWS) == set(NI.STUDY_NIGHTLY) | set(NI.STUDY_WEEKLY) | set(NI.STATUTE_VIEWS), (
        "fetch_archive_db.GITHUB_VIEWS and nightly.py's database views disagree about which "
        "views GitHub owns")
    bat = _source("publish.bat", errors="replace")
    guard = bat.find('if exist "' + str(R.STANDDOWN).replace("/", "\\") + '"')
    assert guard != -1, "publish.bat does not look for the stand-down file"
    assert guard < bat.find("python3 build_all.py") and guard < bat.find("call npx wrangler"), \
        "publish.bat looks for the stand-down file only after it has built or deployed"
    return "ok", (f"{R.STANDDOWN} stops the nightly, the snapshot, publish.bat and the six "
                  "fetchers GitHub owns, before any request; never on GitHub's machine")


@check("build", "on a stood-down laptop no General Court request starts in GitHub's night "
                "window or the half hour before it, none goes on inside it, and none starts "
                "before the real bucket's refusal record is read since the last one",
       needs=("refusal", "probe_db"))
def _night_window(R, PD):
    """One fetch at a time is the rule this address was blocked twice for
    breaking, and since 26 September GitHub's machine asks the General Court
    every night (08:17 UTC since 27 September, four hours allowed, and often
    started late) and early on Monday (04:17, two). Its refusals go to the
    bucket, not to the laptop. So on a stood-down laptop, and nowhere else:

      - the window is one definition, in UTC, 08:00 to 13:30 daily (an hour
        for GitHub's late start) and 04:00 to 06:30 on Monday, two windows
        there with the laptop free between them now that the night starts
        at 08:17; its sentence names it in Eastern time, EDT or EST as the
        date has it, and says when it ends;
      - refusal.check(), which every General Court fetcher calls, exits 4 in
        it and in the 30 minutes before it, and exits 4 outside it until the
        bucket's refusal record has been read (cloud.py pull) since the last
        window closed -- a read of the REAL bucket: a --local-bucket folder's
        read does not count; a standing refusal still exits 2 first;
      - a run that started before the window stops at it: hold().still(),
        which the fetchers that hold archive/.lock ask before every request,
        turns False at the window's first minute, and says why once -- and
        the run cannot then end as finished: a `with hold()` block left
        normally or by sys.exit(0) exits 4, a 2, a 3 or an exception passes
        unchanged, release() raises nothing, and the file the run's starter
        named in WINDOW_STOP_ENV says the window stopped it;
      - every one of probe_db's bridges to the SQL host, which the night and
        the weekly also query, stops in the window and the half hour before
        without starting PowerShell or touching its output file -- read from
        the source, so a bridge added later that starts PowerShell without
        asking first fails here -- and the refusal record does not govern
        them;
      - the lane asks before each step, daily ones included (the lane's own
        check drives it);
      - none of it applies without the stand-down, or on GitHub's machine.
    """
    import ast
    import contextlib
    import io
    from datetime import datetime, timezone

    def utc(s):
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    w = R.night_window(utc("2026-09-29T08:30"))                    # a Tuesday
    assert w and w[0] == utc("2026-09-29T08:00") and w[1] == utc("2026-09-29T13:30"), w
    for t in ("2026-09-29T07:59", "2026-09-29T13:30", "2026-09-29T14:00", "2026-09-27T04:30"):
        assert R.night_window(utc(t)) is None, f"{t} UTC was called inside the window"
    assert R.night_window(utc("2026-09-29T13:00")), \
        "13:00 UTC, an hour-late night still running, was called outside the window"
    w = R.night_window(utc("2026-09-28T04:30"))                    # a Monday: the weekly
    assert w and w[0] == utc("2026-09-28T04:00") and w[1] == utc("2026-09-28T06:30"), w
    assert R.night_window(utc("2026-09-28T07:00")) is None, \
        "07:00 UTC on a Monday, between the weekly and the night, was called inside a window"
    w = R.night_window(utc("2026-09-28T08:30"))                    # and the night after it
    assert w and w[0] == utc("2026-09-28T08:00") and w[1] == utc("2026-09-28T13:30"), w
    said = R.describe_window(*R.night_window(utc("2026-09-29T08:30")))
    assert "4:00 a.m. EDT" in said and "9:30 a.m. EDT" in said, said
    said = R.describe_window(*R.night_window(utc("2026-12-08T09:00")))
    assert "3:00 a.m. EST" in said and "8:30 a.m. EST" in said, said
    said = R.describe_window(*R.night_window(utc("2026-12-07T05:00")))
    assert "Sunday 11:00 p.m. EST" in said and "Monday 1:30 a.m. EST" in said, said
    assert R.last_window_end(utc("2026-09-29T14:00")) == utc("2026-09-29T13:30")
    assert R.last_window_end(utc("2026-09-29T07:00")) == utc("2026-09-28T13:30")
    assert R.last_window_end(utc("2026-09-28T07:00")) == utc("2026-09-28T06:30"), \
        "between Monday's two windows, the last to close was not the weekly's"
    assert R.eastern(utc("2026-03-08T06:59"))[1] == "EST" and \
        R.eastern(utc("2026-03-08T07:00"))[1] == "EDT" and \
        R.eastern(utc("2026-11-01T05:59"))[1] == "EDT" and \
        R.eastern(utc("2026-11-01T06:00"))[1] == "EST", "the daylight-time rule is wrong"
    assert R.START_MARGIN_MINUTES == 30 < R.SOON_MINUTES, "the half hour before is not 30 minutes"

    # EVERY FUNCTION IN probe_db THAT STARTS POWERSHELL asks window_check()
    # first. The reader is tried first on one that does not.
    SPAWN = {("child", "popen"), ("subprocess", "run"), ("subprocess", "Popen"),
             ("subprocess", "call"), ("subprocess", "check_output"), ("subprocess", "check_call")}

    def unguarded(tree):
        out, starts = [], []
        for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
            calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name)]
            spawns = [n.lineno for n in calls if (n.func.value.id, n.func.attr) in SPAWN]
            if not spawns:
                continue
            starts.append(fn.name)
            checks = [n.lineno for n in calls
                      if (n.func.value.id, n.func.attr) == ("refusal", "window_check")]
            if not checks or min(checks) > min(spawns):
                out.append(fn.name)
        return out, starts
    probe = ast.parse("def fine(x):\n    refusal.window_check('q')\n    child.popen(x)\n\n"
                      "def late(x):\n    child.popen(x)\n    refusal.window_check('q')\n\n"
                      "def bare(x):\n    subprocess.run(x)\n")
    assert unguarded(probe)[0] == ["late", "bare"], unguarded(probe)
    bad, starts = unguarded(_parsed(PD.__file__))
    assert {"run", "run_to_file", "_bridge"} <= set(starts), \
        f"probe_db's bridges were not found to read: {starts}"
    assert not bad, (f"probe_db starts PowerShell without asking refusal.window_check() first "
                     f"in {', '.join(bad)}: GitHub's night queries that host too")

    here = os.getcwd()
    tmp = Path(tempfile.mkdtemp(prefix="gr-window-"))
    saved = (R.MARK, os.environ.get("GITHUB_ACTIONS"), os.environ.get(R.CLOCK_ENV),
             PD.subprocess.run, PD.child.popen, R.LOCK)

    def at(t):
        os.environ[R.CLOCK_ENV] = t + "Z"

    def exits(fn):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            try:
                fn()
            except SystemExit as e:
                return e.code, err.getvalue()
        return None, err.getvalue()

    def asked(*_a, **_k):
        raise AssertionError("the SQL host was asked inside the window")

    def read_at(t, kind="r2"):
        (tmp / "archive/cloud").mkdir(parents=True, exist_ok=True)
        (tmp / "archive/cloud/pull.json").write_text(json.dumps(
            {"refusal": {"read": utc(t).timestamp(), "kind": kind}}), encoding="utf-8")
    try:
        os.chdir(tmp)
        os.environ.pop("GITHUB_ACTIONS", None)
        R.MARK, R.LOCK = Path("archive") / "refused.json", Path("archive") / ".lock"
        Path("archive").mkdir()
        at("2026-09-29T08:30:00")
        assert exits(lambda: R.check("t"))[0] is None, "the window held a laptop that has not stood down"
        (tmp / "archive/runs-in-the-cloud.json").write_text("{}", encoding="utf-8")
        code, said = exits(lambda: R.check("The test fetch"))
        assert code == R.STOOD_DOWN == 4 and "9:30 a.m. EDT" in said and "window" in said, (code, said)
        assert R.CLOCK_ENV in said, "a sentence judged at a test clock did not say so"
        PD.subprocess.run = PD.child.popen = asked
        out = tmp / "out.jsonl"
        out.write_text("what was on disk\n", encoding="utf-8")
        bridges = (lambda: PD.run("x", [("q", "SELECT 1")]),
                   lambda: PD.run_to_file("x", "SELECT 1", tmp / "out.psv"),
                   lambda: PD.run_to_file_counted("x", "SELECT 1", "SELECT 1", tmp / "c.psv"),
                   lambda: PD.run_to_jsonl("x", "SELECT 1", "SELECT 1", out),
                   lambda: PD._bridge(PD.PS_JSONL, {}, print, 60))
        for n, fn in enumerate(bridges):
            code, said = exits(fn)
            assert code == 4 and "database" in said, (n, code, said)
        assert out.read_text(encoding="utf-8") == "what was on disk\n", \
            "run_to_jsonl stopped for the window emptied the file it would have written"

        # The half hour before: nothing starts, the SQL host included.
        at("2026-09-30T07:40:00")
        code, said = exits(lambda: R.check("t"))
        assert code == 4 and "opens at 4:00 a.m. EDT" in said and "30 minutes" in said, (code, said)
        code, said = exits(lambda: PD.run("x", [("q", "SELECT 1")]))
        assert code == 4 and "30 minutes" in said, (code, said)
        at("2026-09-30T07:15:00")
        read_at("2026-09-29T13:45")
        assert "opens at 4:00 a.m. EDT" in R.window_soon(), "a window 45 minutes off was not mentioned"
        assert exits(lambda: R.check("t"))[0] is None, "a fetch 45 minutes before the window was held"
        at("2026-09-30T06:00:00")
        assert R.window_soon() == "", "a window two hours off was mentioned"

        # A run already going when the window opens stops at its next request,
        # and cannot then end as though it had finished: a block left normally
        # exits 4, and the file its starter named says the window stopped it.
        at("2026-09-30T07:59:00")
        told = tmp / "window-stop.json"
        os.environ[R.WINDOW_STOP_ENV] = str(told)
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                with R.hold("the test fetch") as held:
                    assert held.still(), "a held run was stopped before the window"
                    assert held.window is None and not told.exists(), \
                        "a run was marked stopped by a window that had not opened"
                    at("2026-09-30T08:00:00")
                    first, second = held.still(), held.still()
            raise AssertionError("a with-block the window stopped ended as though it had "
                                 "finished (status 0)")
        except SystemExit as e:
            assert e.code == R.STOOD_DOWN, f"a with-block the window stopped exited {e.code}"
        finally:
            os.environ.pop(R.WINDOW_STOP_ENV, None)
        said = err.getvalue()
        assert not first and not second, "a held run went on asking inside the window"
        assert "stops before its next request" in said and "4:00 a.m. EDT" in said, said
        assert said.count("stops before its next request") == 1, "still() said why twice"
        assert "not as finished" in said, f"the exit 4 did not say why: {said[-300:]}"
        assert told.exists() and "the test fetch" in told.read_text(encoding="utf-8"), \
            "the file the starter named was not written when the window stopped the run"
        assert not R.LOCK.exists(), "a hold the window stopped kept its lock"
        # sys.exit(0) is finishing too; a refusal's 2, a lost lock's 3 and an
        # exception are not the hold's to change, and release() raises nothing.
        for leave, want in ((lambda: sys.exit(0), R.STOOD_DOWN), (lambda: sys.exit(None), R.STOOD_DOWN),
                            (lambda: sys.exit(2), 2), (lambda: sys.exit(3), 3),
                            (lambda: (_ for _ in ()).throw(KeyError("k")), KeyError)):
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    with R.hold("t") as held:
                        held.still()
                        leave()
                raise AssertionError("unreached")
            except SystemExit as e:
                assert e.code == want, f"a stopped hold left by {want} exited {e.code}"
            except KeyError:
                assert want is KeyError, "an exception in a stopped hold was replaced"
        with contextlib.redirect_stderr(io.StringIO()):
            held = R.hold("t")
            held.__enter__()
            held.still()
        held.release()
        assert not R.LOCK.exists(), "release() left the lock"
        at("2026-09-30T07:59:00")
        with R.hold("t") as held:
            held.still()
        assert held.window is None, "a hold the window never stopped was marked stopped"
        (tmp / "archive/runs-in-the-cloud.json").unlink()
        at("2026-09-30T08:30:00")
        with R.hold("the test fetch") as held:
            assert held.still(), "a laptop that has not stood down was stopped by the window"
        (tmp / "archive/runs-in-the-cloud.json").write_text("{}", encoding="utf-8")

        # After the window: the web server's fetchers want a read of the bucket.
        (tmp / "archive/cloud/pull.json").unlink()
        at("2026-09-29T14:00:00")
        code, said = exits(lambda: R.check("t"))
        assert code == 4 and "cloud.py pull" in said and "never" in said, (code, said)
        assert exits(lambda: R.window_check("t"))[0] is None, \
            "the SQL host's check wanted a pull, which the web server's refusals are for"
        read_at("2026-09-29T11:00")
        code, said = exits(lambda: R.check("t"))
        assert code == 4 and "cloud.py pull" in said, "a read from inside the window was enough"
        read_at("2026-09-29T13:45", kind="folder")
        code, said = exits(lambda: R.check("t"))
        assert code == 4 and "cloud.py pull" in said and R.refusal_read() is None, \
            "a pull from a --local-bucket folder counted as reading the night's refusal record"
        read_at("2026-09-29T13:45")
        assert exits(lambda: R.check("t"))[0] is None, "a read since the window closed was not enough"
        at("2026-09-29T08:30:00")
        R.MARK.write_text(json.dumps({"at": "x", "epoch": __import__("time").time(),
                                      "where": "w"}), encoding="utf-8")
        assert exits(lambda: R.check("t"))[0] == 2, "a standing refusal did not stop the fetch first"
        R.MARK.unlink()
        os.environ["GITHUB_ACTIONS"] = "true"
        assert exits(lambda: R.check("t"))[0] is None and R.gc_turn() is None, \
            "GitHub's own machine was held by the laptop's window"
        with R.hold("t") as held:
            assert held.still(), "GitHub's own machine's run was stopped by the laptop's window"
    finally:
        R.MARK, PD.subprocess.run, PD.child.popen, R.LOCK = saved[0], saved[3], saved[4], saved[5]
        for name, v in (("GITHUB_ACTIONS", saved[1]), (R.CLOCK_ENV, saved[2])):
            if v is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = v
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)

    # The lane asks before every step, in run_daily and in main's queue loop.
    tree = ast.parse(_source(_paths.locate("watchers/gc_lane.py")))
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("run_daily", "main"):
        body = ast.unparse(fns[name])
        assert "githubs_turn()" in body and "run_child(" in body and \
            body.index("githubs_turn()") < body.index("run_child("), \
            f"the lane's {name} does not ask whose turn it is before it starts a step"
    assert "STOOD_DOWN" in ast.unparse(fns["run_daily"]), \
        "the lane records a daily step held for GitHub's turn as run"
    return "ok", ("the window is 4:00 to 9:30 a.m. EDT, and midnight to 2:30 on Mondays too, "
                  "and nothing starts in the half hour before; the fetchers, all four SQL "
                  "bridges and the lane wait it out, a held run stops at its first minute, and "
                  "the web server's fetchers wait for a read of the real bucket's refusal since; "
                  "not without the stand-down, nor on GitHub")


@check("workflows", "the captions inbox comes down before the livestream step, is taken from "
       "where it came down, and is cleared only after the night's last state-up and never on "
       "a dry run", needs=("cloud",))
def _workflows_captions_inbox(CL):
    """THE CAPTIONS INBOX (17 October 2026) in nightly.yml's night job, in
    order: cloud.py inbox-down on a fetching night, before the livestream
    step; that step's --inbox naming the folder inbox-down fills
    (cloud.INBOX_LOCAL); and inbox-clear after the last state-up, since it
    reads the state the bucket holds, with a condition that is false on a
    dry run -- cloud.py refuses a dry night itself as well, but a step that
    ran there would be a step that could. No other job, and no other
    workflow, clears the inbox.

    And what a failure costs (the review of 17 October 2026, which found all
    three of these could be dropped with every workflow check still green):
    both inbox steps carry continue-on-error and a short timeout-minutes of
    their own -- without it an R2 hiccup in inbox-down would skip the night
    itself, which only a step that succeeded or carried on is followed by --
    and the clear step's condition requires, as plain conjuncts with no
    "||", that inbox-down and kit-up both succeeded: a kit-up that failed
    left the readings behind while the state says they were read, and the
    entry is what the next night takes again."""
    files = _workflows()
    wf = _SWITCHED.workflow_dir / "nightly.yml"
    if not files or not wf.exists():
        return "skip", "no .github/workflows/nightly.yml here"
    elsewhere = [f"{f.name}:{j}" for f in files
                 for j, jl in _wf_jobs(f.read_text(encoding="utf-8")).items()
                 if (f.name, j) != ("nightly.yml", "night")
                 and any("cloud.py inbox-" in ln for ln in _wf_code(jl))]
    assert not elsewhere, f"the captions inbox is brought down or cleared in {elsewhere}"
    night = _wf_jobs(wf.read_text(encoding="utf-8")).get("night") or []
    steps = ["\n".join(s) for s in _wf_steps(_wf_code(night))]

    def at(pat):
        return [k for k, s in enumerate(steps) if re.search(pat, s)]
    down, ls = at(r"python src/ops/cloud\.py inbox-down"), \
        at(r"python src/ops/livestreams\.py --since-state")
    ups, clear = at(r"python src/ops/cloud\.py state-up"), at(r"python src/ops/cloud\.py inbox-clear")
    assert len(down) == 1 and len(ls) == 1 and len(clear) == 1 and ups, \
        f"nightly.yml's night: inbox-down at {down}, the livestream step at {ls}, inbox-clear " \
        f"at {clear}, state-up at {ups}; one of each is wanted"
    assert down[0] < ls[0], "nightly.yml brings the captions inbox down after the livestream step"
    assert re.search(r"^        if: env\.FETCH == 'true'\s*$", steps[down[0]], re.M), \
        "nightly.yml's inbox-down step does not run on a fetching night only, as the livestreams do"
    assert re.search(r"--since-state --inbox " + re.escape(CL.INBOX_LOCAL) + r"\s*$",
                     steps[ls[0]], re.M), \
        f"nightly.yml's livestream step does not take the inbox from {CL.INBOX_LOCAL}"
    assert clear[0] > max(ups), \
        "nightly.yml clears the captions inbox before the night's state has gone back"
    for k, what in ((down[0], "inbox-down"), (clear[0], "inbox-clear")):
        assert re.search(r"^        continue-on-error: true\s*$", steps[k], re.M), \
            f"nightly.yml's {what} step has no continue-on-error, so its failure stops the night"
        lim = re.search(r"^        timeout-minutes:\s*(\d+)\s*$", steps[k], re.M)
        assert lim and int(lim.group(1)) <= 15, \
            f"nightly.yml's {what} step has no timeout-minutes of its own, of 15 or less"

    def sid(k):
        m = re.search(r"^        id:\s*(\S+)\s*$", steps[k], re.M)
        return m.group(1) if m else None
    kit = at(r"python src/ops/cloud\.py kit-up")
    assert len(kit) == 1 and sid(down[0]) and sid(kit[0]) and kit[0] < clear[0], \
        "nightly.yml's inbox-down or kit-up step has no id, or kit-up comes after inbox-clear"
    cond = re.search(r"^        if:\s*(.+)$", steps[clear[0]], re.M)
    terms = {t.strip() for t in cond.group(1).split("&&")} if cond else set()
    want = {"env.DRY_RUN == 'false'", f"steps.{sid(down[0])}.outcome == 'success'",
            f"steps.{sid(kit[0])}.outcome == 'success'"}
    assert cond and "||" not in cond.group(1) and want <= terms, (
        f"nightly.yml's inbox-clear step's condition is {cond.group(1) if cond else None!r}; it "
        f"must require each of {sorted(want)}, joined by && alone")
    return "ok", (f"inbox-down before the livestream step, --inbox {CL.INBOX_LOCAL}, inbox-clear "
                  "after the last state-up, only when DRY_RUN is false and inbox-down and kit-up "
                  "succeeded; both carry on past a failure inside their own limits; nowhere else")


PULLED_NIGHTLY = re.compile(r"^logs/nightly-\d{4}-\d\d-\d\d\.log$")
PULL_STALE_HOURS = 24         # a pull older than this is the likelier reason a night looks old
FULL_PULL_HOURS = 48          # the laptop's copies of the night's files, at most this old
STANDDOWN_GRACE_HOURS = 48    # never having pulled is a skip only this long after the stand-down


def _standdown_since(path):
    """When this laptop stood down, as a naive local time: the stand-down
    file's "since" (refusal.py --stand-down writes local time), or the file's
    own date when that will not read. None when there is no file."""
    from datetime import datetime
    p = Path(path)
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return datetime.fromisoformat(str(d.get("since")))
    except (OSError, ValueError, TypeError, AttributeError):
        try:
            return datetime.fromtimestamp(p.stat().st_mtime)
        except OSError:
            return None


def _grace(since, now):
    """(still within STANDDOWN_GRACE_HOURS of the stand-down, "N hours ago")."""
    if since is None:
        return False, "at a time its stand-down file does not say"
    hours = (now - since).total_seconds() / 3600
    return hours <= STANDDOWN_GRACE_HOURS, f"{hours:.0f} hours ago ({since:%Y-%m-%d %H:%M})"


def _pulled_night_findings(logs, cloud, now, since=None):
    """(problems, summary) for a laptop that has stood down, as of `now`.

    Its own nightly stopped at the stand-down; GitHub's nights reach it only
    through `cloud.py pull`, which writes archive/cloud/pull.json (with the
    logs it wrote), archive/cloud/last-night.json and logs/nightly-<day>.log.
    problems is None when nothing has ever been pulled and the laptop stood
    down (`since`) no more than STANDDOWN_GRACE_HOURS ago: after that, never
    having pulled is a failure naming the pull, because a laptop that never
    pulls would otherwise skip this check for good. The newest night is
    the later of the newest pulled log's start and the verdict's; older than
    NIGHTLY_STALE_HOURS is a problem, whose remedy depends on whether the pull
    or the night is what is old. The week of nights that installed nothing is
    read from the pulled logs. The laptop's own last REPORTS FAILED: is not:
    no nightly here will run the reports step again, so it could never clear.
    """
    from datetime import datetime

    def doc(p):
        try:
            d = json.loads(Path(p).read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else None
        except (OSError, ValueError):
            return None
    rec, verdict = doc(Path(cloud) / "pull.json"), doc(Path(cloud) / "last-night.json")
    if not rec and not verdict:
        grace, ago = _grace(since, now)
        said = (f"this laptop stood down {ago}, and nothing has been pulled from the bucket "
                "since: python3 src/ops/cloud.py pull brings GitHub's nights here, and this check "
                "reads them")
        if grace:
            return None, said + f" (it skips for {STANDDOWN_GRACE_HOURS} hours after the stand-down)"
        return [said[0].upper() + said[1:] + ". Until then this laptop's data, nightly logs and "
                "change lists stop at the stand-down. The pull reads the bucket only and asks the "
                "General Court nothing. It clears when a pull brings a night from the last 48 "
                "hours."], said
    nights = []
    for name in sorted(n for n in (rec or {}).get("files", {}) if PULLED_NIGHTLY.match(n)):
        f = Path(logs) / name.split("/", 1)[1]
        if f.exists():
            n = _nightly_night(f.read_text(encoding="utf-8", errors="replace"))
            n["name"] = f.name
            n["started"] = n["started"] or datetime.fromtimestamp(f.stat().st_mtime)
            nights.append(n)
    newest, what = None, ""
    if nights:
        newest, what = max(n["started"] for n in nights), "the newest pulled nightly log"
    raw = (verdict or {}).get("started") or (verdict or {}).get("day")
    try:
        v = datetime.fromisoformat(raw) if raw else None
    except ValueError:
        v = None
    if v and (newest is None or v > newest):
        newest, what = v, "archive/cloud/last-night.json, the night's verdict"
    pulled = datetime.fromtimestamp(float(rec["epoch"])) if rec and rec.get("epoch") else None
    since = (f"{(now - pulled).total_seconds() / 3600:.0f} hours ago" if pulled
             else "never")
    problems = []
    if newest is None:
        problems.append(
            f"The last pull ({since}) brought no night's log or verdict here. python3 src/ops/cloud.py "
            "pull brings them; if it finds none, the nightly on GitHub has not sent any (its "
            "Actions tab says why), and starting it is the person's decision. It clears when a "
            "pull brings a night from the last 48 hours.")
    else:
        hours = (now - newest).total_seconds() / 3600
        if hours > NIGHTLY_STALE_HOURS:
            old_pull = pulled is None or (now - pulled).total_seconds() / 3600 > PULL_STALE_HOURS
            problems.append(
                f"The newest night this laptop has, from {what}, started "
                f"{newest:%Y-%m-%d %H:%M}, {hours:.0f} hours ago. "
                + ("The last pull from the bucket was " + since + ": python3 src/ops/cloud.py pull "
                   "brings the nights since. " if old_pull else
                   f"python3 src/ops/cloud.py pull ran {since} and found nothing newer, so the nightly "
                   "on GitHub has stopped, or stopped reaching kit-up, which sends its log: its "
                   "Actions tab says which. Starting it again is the person's decision; do not "
                   "run nightly.py here, which refuses on a stood-down laptop anyway. ")
                + "It clears when a pull brings a night from the last 48 hours.")
    week = _installed_none(nights)
    if week:
        problems.append(week)
    summary = (f"stood down; {len(nights)} of GitHub's nightly logs pulled here, the newest "
               + (f"night {newest:%Y-%m-%d %H:%M} ({what})" if newest else "night none")
               + f"; last pulled {since}"
               + ("" if not verdict else
                  f"; the verdict says {'CLEAN' if verdict.get('clean') else 'NOT CLEAN'}"))
    return problems, summary


def _pulled_night_selftest():
    """The stood-down reader on made-up pulls whose answers are known."""
    from datetime import datetime, timedelta
    now = datetime(2026, 9, 30, 9, 0)
    tmp = Path(tempfile.mkdtemp())
    logs, cloud = tmp / "logs", tmp / "archive" / "cloud"
    logs.mkdir()
    cloud.mkdir(parents=True)

    def pulled(at, *days, verdict=None, installed=True):
        files = {}
        for d in days:
            body = (f"Granite Record nightly  {d} 02:17\n"
                    + ("\n--- what the General Court changed ---\n" if installed else
                       "\nFETCH DEFERRED: a refusal is on file (x)\n"))
            (logs / f"nightly-{d}.log").write_text(body, encoding="utf-8")
            files[f"logs/nightly-{d}.log"] = "sha"
        (cloud / "pull.json").write_text(json.dumps(
            {"epoch": at.timestamp(), "files": files}), encoding="utf-8")
        if verdict:
            (cloud / "last-night.json").write_text(json.dumps(verdict), encoding="utf-8")
    try:
        assert _pulled_night_findings(logs, cloud, now, now - timedelta(hours=20))[0] is None, \
            "never pulled, the day after the stand-down, was not a skip"
        p = _pulled_night_findings(logs, cloud, now, now - timedelta(hours=49))[0]
        assert p and len(p) == 1 and "python3 src/ops/cloud.py pull" in p[0], \
            f"never pulled, 49 hours after the stand-down, did not fail naming the pull: {p}"
        assert _pulled_night_findings(logs, cloud, now, None)[0], \
            "never pulled, with no stand-down date to go by, was a skip"
        pulled(now - timedelta(hours=2), "2026-09-30")
        assert _pulled_night_findings(logs, cloud, now)[0] == [], "a night from this morning failed"
        pulled(now - timedelta(days=3), "2026-09-27")
        p = _pulled_night_findings(logs, cloud, now)[0]
        assert len(p) == 1 and "python3 src/ops/cloud.py pull brings" in p[0], p
        pulled(now - timedelta(hours=1), "2026-09-27")
        p = _pulled_night_findings(logs, cloud, now)[0]
        assert len(p) == 1 and "Actions tab" in p[0] and "found nothing newer" in p[0], p
        pulled(now - timedelta(hours=1), "2026-09-27",
               verdict={"day": "2026-09-30", "started": "2026-09-30T02:17:00", "clean": True})
        assert _pulled_night_findings(logs, cloud, now)[0] == [], \
            "a fresh verdict did not count as a night"
        days = [f"{now - timedelta(days=k):%Y-%m-%d}" for k in range(6, -1, -1)]
        pulled(now - timedelta(hours=1), *days, installed=False)
        p = _pulled_night_findings(logs, cloud, now)[0]
        assert len(p) == 1 and "installed none" in p[0], p
        sd = tmp / "runs-in-the-cloud.json"
        sd.write_text(json.dumps({"since": "2026-09-26T15:04:05"}), encoding="utf-8")
        assert _standdown_since(sd) == datetime(2026, 9, 26, 15, 4, 5)
        sd.write_text("{}", encoding="utf-8")
        assert _standdown_since(sd) is not None, "a stand-down with no date gave no time at all"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _full_pull_findings(cloud, now, since):
    """(problems, summary) about the laptop's copies of the night's files, on
    a laptop that has stood down: problems is None for a skip.

    --changes-only is the morning's pull and brings no kit file, so a laptop
    that only ever triages keeps the night's files -- proceedings.csv, the
    narratives, the day's data -- as they were on the last FULL pull, which
    pull.json records ("full"). Older than FULL_PULL_HOURS is a failure
    naming python3 src/ops/cloud.py pull; never is a skip for STANDDOWN_GRACE_HOURS
    after the stand-down and a failure after, as the nightly check's is."""
    from datetime import datetime
    try:
        rec = json.loads((Path(cloud) / "pull.json").read_text(encoding="utf-8"))
        full = (rec.get("full") or {}) if isinstance(rec, dict) else {}
    except (OSError, ValueError, AttributeError):
        full = {}
    if not full.get("epoch"):
        grace, ago = _grace(since, now)
        said = (f"no full pull has run here since this laptop stood down {ago}: the night's files "
                "on this laptop are as they were then")
        if grace:
            return None, said + f" (this skips for {STANDDOWN_GRACE_HOURS} hours after the stand-down)"
        return [said[0].upper() + said[1:] + ". python3 src/ops/cloud.py pull brings them (it reads the "
                "bucket only; --changes-only does not bring them). It clears on the first full "
                "pull."], said
    at = datetime.fromtimestamp(float(full["epoch"]))
    hours = (now - at).total_seconds() / 3600
    said = f"the last full pull was {hours:.0f} hours ago ({at:%Y-%m-%d %H:%M})"
    if hours > FULL_PULL_HOURS:
        return [said[0].upper() + said[1:] + f", more than {FULL_PULL_HOURS}: this laptop's "
                "copies of the night's files are that old, and a build or a check here reads "
                "them. python3 src/ops/cloud.py pull brings them (it reads the bucket only; "
                "--changes-only does not bring them). It clears on the next full pull."], said
    return [], said


def _full_pull_selftest():
    """_full_pull_findings on made-up pull records whose answers are known."""
    from datetime import datetime, timedelta
    now = datetime(2026, 9, 30, 9, 0)
    tmp = Path(tempfile.mkdtemp())
    try:
        assert _full_pull_findings(tmp, now, now - timedelta(hours=10))[0] is None, \
            "no full pull, the morning after the stand-down, was not a skip"
        p = _full_pull_findings(tmp, now, now - timedelta(hours=50))[0]
        assert p and "python3 src/ops/cloud.py pull" in p[0], p
        (tmp / "pull.json").write_text(json.dumps(
            {"epoch": now.timestamp(), "mode": "changes-only"}), encoding="utf-8")
        assert _full_pull_findings(tmp, now, now - timedelta(hours=50))[0], \
            "a changes-only pull counted as a full one"
        (tmp / "pull.json").write_text(json.dumps(
            {"full": {"epoch": (now - timedelta(hours=47)).timestamp()}}), encoding="utf-8")
        assert _full_pull_findings(tmp, now, None)[0] == [], "a full pull 47 hours old failed"
        (tmp / "pull.json").write_text(json.dumps(
            {"full": {"epoch": (now - timedelta(hours=49)).timestamp()}}), encoding="utf-8")
        p = _full_pull_findings(tmp, now, None)[0]
        assert p and "49 hours ago" in p[0] and "python3 src/ops/cloud.py pull" in p[0], p
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@check("data", "a stood-down laptop's copies of the night's files are no more than 48 hours old")
def _full_pull_fresh():
    """On a laptop that has stood down, the night's files -- the day's data,
    the carried outputs, the snapshots -- change on GitHub every night and
    reach this laptop only through a full `python3 src/ops/cloud.py pull`. The
    morning triage's --changes-only brings the change list and not them, so
    the laptop's data can grow old while every morning looks attended to.
    Fails when the last full pull is over 48 hours old (or, 48 hours after the
    stand-down, when there has never been one), naming the pull. The pull
    reads the bucket and asks the General Court nothing; running it is still
    the person's to decide, because it can clash with work here."""
    from datetime import datetime
    import refusal
    _full_pull_selftest()
    if refusal.stood_down() is None:
        return "skip", "this laptop has not stood down: its own nightly keeps its files"
    problems, summary = _full_pull_findings(Path("archive/cloud"), datetime.now(),
                                            _standdown_since(refusal.STANDDOWN))
    if problems is None:
        return "skip", summary
    assert not problems, "\n".join(problems)
    return "ok", summary


@check("data", "the nightly is still running, and its last report pull worked")
def _nightly_logs():
    """The nightly runs from Task Scheduler with nobody watching, so the way to
    notice it has stopped is its logs. Read from logs/:

      - no nightly log at all is a skip: it has never been scheduled here;
      - logs that show no schedule -- no three runs in a row about a day
        apart -- are runs by hand, and their age is not a finding: the check
        skips unless one of the two below fails;
      - on a schedule, the newest log from a run that started more than 48
        hours ago fails;
      - the last seven logs of nights meant to fetch (not --no-fetch) that
        installed none of the General Court's files fail, naming what stopped
        each -- a refusal on file, the lane's lock, a build, preflight, a
        failed fetch. Those files are live views and cannot be fetched later.
        Until 13 September this looked for DEFERRED: instead, which failed a
        week of waiting out a refusal and passed a week of failed fetches;
      - the newest log whose night reached the reports step recording REPORTS
        FAILED: fails, without quoting it. Until 13 September it read only the
        newest log, so a night deferred to a build hid the failed pull before.

    Every failure says the remedy is the person's and how it clears: nightly.py
    fetches from the General Court and pulls from D1, and a session told to
    make preflight green must not reach for it.

    A data check, not a code one, on purpose: nightly.py gates itself on
    preflight --code, and a check that failed on the nightly's own last log
    would stop the next night's fetch because the last night's report pull
    failed. The reader is unit-tested on made-up logs first (and, under
    --code, on logs nightly.main() really writes).

    ON A LAPTOP THAT HAS STOOD DOWN (26 September 2026) the nightly runs on
    GitHub and this laptop's own logs stop at the stand-down, so they would
    fail here forever. What it reads instead is what `cloud.py pull` brought:
    the pulled nightly logs and archive/cloud/last-night.json
    (_pulled_night_findings). Never pulled is a skip that says so for 48
    hours after the stand-down, and a failure naming python3 src/ops/cloud.py pull
    after that -- a laptop that never pulled once skipped this for good; a
    newest night older than 48 hours fails, with python3 src/ops/cloud.py pull as the
    remedy when the pull is what is old, and the Actions tab when the pull is
    fresh and the night is not.
    """
    from datetime import datetime
    import refusal
    _nightly_log_selftest()
    _pulled_night_selftest()
    if refusal.stood_down() is not None:
        problems, summary = _pulled_night_findings(Path("logs"), Path("archive/cloud"),
                                                   datetime.now(),
                                                   _standdown_since(refusal.STANDDOWN))
        if problems is None:
            return "skip", summary
        assert not problems, "\n".join(problems)
        return "ok", summary
    problems, summary, scheduled = _nightly_log_findings(Path("logs"), datetime.now())
    if problems is None:
        return "skip", summary
    assert not problems, "\n".join(problems)
    return ("ok" if scheduled else "skip"), summary
