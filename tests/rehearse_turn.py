#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-05.9
"""
The turn from one term to the next, rehearsed offline on a copy.

    python3 tests/rehearse_turn.py --copy DIR              make the copy, freeze, build, and
                                                           run every night (2.5 hours)
    python3 tests/rehearse_turn.py --copy DIR --guards     the nights' guards only, no full
                                                           build (a few minutes)
    python3 tests/rehearse_turn.py --copy DIR --views V    ... and the database night at the
                                                           turn, from V: a folder of the views
                                                           fetch_day_db.py leaves (.night/dbday)
                                                           of the same days as the installed files
    python3 tests/rehearse_turn.py --copy DIR --reuse      the copy and its pre-turn build are
                                                           there from a run that stopped before
                                                           its first night: run the nights. After
                                                           a whole run the copy's installed files
                                                           are 2027's, and a new copy is wanted
    python3 tests/rehearse_turn.py --copy DIR --pre-only   make the copy, freeze, build the pre-
                                                           turn baseline and stop: its site is
                                                           there to compare with another build's
                                                           before --reuse runs the nights

DIR must not be inside the repository: the copy is the repository's committed
code (git archive HEAD) and the kit's data (cloud_kit.json, as GitHub's
machine gets it), and every night of the rehearsal writes only there. Nothing
is asked of anybody: the General Court's export and database are answered by
this script from files it makes, a socket that tries to connect fails, the
proxies are dead, GRANITE_NO_BUCKET is set, and a step of the night this does
not stand in for stops the rehearsal rather than run.

WHY (5 October 2026)

Fed a fake first 2027 batch on a copy, the build of fa01eb6 wrote no
2025-2026 at all and exited 0; a docket holding 2025, 2026 and 2027 grew,
nothing shrank, and a scheduled night would have published the turn
unasked (private/NEW_TERM_DESIGN.md). The fixes -- the freeze
(freeze_term.py), the term built nightly from it (build_data.py
--frozen-terms), the rule that rows of a finished term in new files are
counted and never merged, the turn guard (snapshot_gencourt.judge) and the
rest -- are proved here the only way they can be before December: by
running the nights the turn will bring, on a copy, through nightly.main()
itself, and building the site after them. The person runs it again in
November on the laptop, after the late-November database download and the
freeze that follows it, and before Organization Day (2 December 2026).

THE NIGHTS, IN ORDER (each says what it expects, and PASS or FAIL)

  pre-turn     the copy's own build with the freeze in place: the baseline
               every comparison below is against (not with --guards)
  G1           a scheduled night, the export as installed: installs
  G2           Organization Day: resolutions only (HR 1-5, SR 1-5 of 2027), the
               rest as installed, a third of the House new: refused, "a new term"
  G3, G4, G5   the design's variants B (a clean first batch), C (B with ten 2026
               rows left in) and D (the 2027 batch appended, nothing smaller):
               each refused as a new term, D without any file being smaller
  G6           the 20 September pattern (LSRs.txt and legislators.txt empty, the
               rest whole): "empty", and the database is asked
  G7           the two roll-call files empty before any turn: still a failure,
               and the database is asked
  G8           a New term run whose freeze is stale: stops before any request
  G9           a New term run of B with the roll-call files empty: taken
  OD0          Organization Day's roster before the docket turns, with the term's
               freeze moved aside: "roster", nothing installed (the review of 5
               October 2026)
  OD           the same with the freeze in place: the next House and an
               LsrsOnly.txt of the sitting only installed on a scheduled night,
               a full build, and 2025-2026 compared with the pre-turn build --
               still the session's term, so nothing of it moves but a sponsor
               who left mid-term gaining a link
  DB1, DB2     (with --views) the database night between Organization Day and
               the switch: the views hold 2027 rows and a new roster. With
               tonight's Members.txt naming the new roster it is installed,
               the 2027 rows left out and said, and built in full and compared
               as OD is -- but for the bills whose docket rows the views, of
               another day than the export installed, hold otherwise: their
               history, stations and status are counted apart, and their
               sponsors and ballots held as every bill's are; with the old
               Members.txt the roster guard stops it
  NT           THE SWITCH: a New term run of B (roll calls still 2026's, the new
               roster), the full build, the publish
  A1           the next scheduled night: B grown by five rows and a 2026 row left
               in, the roll calls empty (the copies they replace are 2025-2026's
               frozen ones): a full build, clean, and the left-out row on the
               run's page
  A2           the first 2027 roll calls: installed
  C-, D-, S-level  variants C and D after the switch, and S -- only the sponsor
               files naming 2027 -- at build_data and narrative level: the term
               stays whole, the stragglers are counted and left out, and nobody's
               2026 sponsors are filed under 2027-2028

The fake roster seats a third of the House new, moves one continuing member to
another district and changes another's party: their 2025-2026 sponsorships keep
the seat and party they held then (build_site_v2's term roster).

WHAT IT PROVES, AND HOW (after NT and after A1, against the pre-turn build)

  2025-2026 whole        data/bills.json's slice equal record for record but
                         for the archived mark; data/sponsors.json's equal;
                         site/bills/2025 and /2026 and site/bill/2025 and /2026
                         compared file by file, and every difference sorted by
                         the field it is in, so the expected ones (the
                         archived mark and its coverage, the session_over
                         note, a CACR's election, a sponsor who left mid-term
                         gaining the link the pre-turn build lacked) stand
                         apart from anything else; the term's index file,
                         site/idx/<term>.json, the same way; proceedings.csv's
                         rows of the
                         term equal in content; the Senate's hearing reports,
                         chapters and topics of the term equal
  2027-2028 appears      its index and its bills, with the sentinel titles
  no leak                no 2025-2026 title on a 2027 page, and the two bills
                         given a 2025 bill's number and LSR take nothing of it,
                         read from each 2027 page's own record
                         (build_bill_pages.embedded), and none examined is a
                         failure
  the verdicts           the scheduled nights publish nothing of the turn; the
                         New term run is publishable and its publish sets the
                         baseline; A1 is clean and publishable

Its record is DIR/rehearsal.json; it exits 0 when every expectation held.
private/TURNOVER_REHEARSAL.md says what it proved on 5 October 2026.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import socket
import subprocess
import tarfile
import time
import types
import urllib.request
from datetime import datetime

REPO = _paths.ROOT
TERM, NEW = "2025-2026", "2027-2028"
BOM = b"\xef\xbb\xbf"
DAY = "2026-10-05"                     # the stated day of every build here
RESULTS = {"nights": [], "checks": [], "failed": []}


def note(ok, what, detail=""):
    """One expectation, said and kept."""
    RESULTS["checks"].append({"ok": bool(ok), "what": what, "detail": str(detail)[:600]})
    if not ok:
        RESULTS["failed"].append(what)
    print(f"  {'PASS' if ok else 'FAIL'}  {what}" + (f"  -- {str(detail)[:300]}" if detail and not ok else ""),
          flush=True)
    return ok


def env(seed="2"):
    return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONHASHSEED=seed,
                GRANITE_BUILD_DATE=DAY, HTTP_PROXY="http://127.0.0.1:9",
                HTTPS_PROXY="http://127.0.0.1:9", NO_PROXY="", GRANITE_NO_BUCKET="1")


def sh(cmd, cwd, log=None, seed="2"):
    """A script in the copy, found by its bare name in the copy's code folders
    (_paths.script), its output to `log`."""
    t = time.time()
    cmd = [_paths.script(cmd[0], root=cwd)] + list(cmd[1:])
    with (open(log, "w", encoding="utf-8") if log else contextlib.nullcontext()) as fh:
        r = subprocess.run([sys.executable] + cmd, cwd=cwd, env=env(seed),
                           stdout=fh or subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, encoding="utf-8", errors="replace")
    return r.returncode, time.time() - t, (r.stdout or "")


# ---- the copy ------------------------------------------------------------------------

def copy_on_path(root):
    """The copy's code folders in front of the import path, so a module
    imported from here on is the copy's, wherever under it the module sits."""
    sys.path[:0] = [str(d) for d in _paths.code_dirs(root)]


def make_copy(dest):
    """The committed code and the kit's data, at `dest`."""
    if dest.resolve() == REPO or REPO in dest.resolve().parents:
        sys.exit(f"{dest} is inside the repository; the copy goes elsewhere")
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest} is not empty; give an empty folder, or --reuse")
    dest.mkdir(parents=True, exist_ok=True)
    tar = dest.parent / (dest.name + ".tar")
    subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", "-o", str(tar), "HEAD"],
                   check=True)
    with tarfile.open(tar) as t:
        t.extractall(dest, filter="data")
    tar.unlink()
    import cloud
    files, missing, _ = cloud.kit_files(REPO, cloud.load_kit(REPO))
    if missing:
        print(f"  the kit is missing {len(missing)} entr(ies) here: {missing[:4]}")
    n = 0
    for rel in sorted(files):
        src, out = REPO / rel, dest / rel
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        n += 1
    print(f"copy: HEAD's code and {n:,} kit files -> {dest}")


def installed_state(root):
    """{name: bytes} of the day files installed in the copy."""
    import freeze_term
    return {n: (root / n).read_bytes() for n in freeze_term.SESSION_FILES if (root / n).exists()}


def restore(root, files):
    for n, b in files.items():
        (root / n).write_bytes(b)


# ---- the fakes, from real rows ---------------------------------------------------------

def lines(b):
    return b.decode("utf-8-sig", "replace").splitlines()


def join(rows):
    return BOM + "".join(r + "\r\n" for r in rows).encode("utf-8")


def shift(s):
    """2024 and 2025 dates and years two years on, so a row of the 2025 session's
    first batch reads as one of 2027's."""
    s = re.sub(r"(\d{1,2}/\d{1,2}/)2025\b", r"\g<1>2027", s)
    s = re.sub(r"(\d{1,2}/\d{1,2}/)2024\b", r"\g<1>2026", s)
    return s


def first_batch(docket, resolutions_only=False):
    """The 2025 session's rows entered before 1 January 2025 -- Organization Day
    2024 and the first bills -- as 2027's, with fresh LSR numbers but for two
    bills, which keep their 2025 number AND LSR (the coincidence the
    Legislation fill once took a subject through)."""
    out, lsr_map, keep = [], {}, set()
    for ln in lines(docket):
        f = ln.split("|")
        if len(f) < 7 or f[0] != "2025":
            continue
        d = f[2].split(" ")[0].split("/")
        if len(d) != 3 or d[2] != "2024":
            continue
        if resolutions_only and not re.match(r"^(HR|SR)\d", f[3]):
            continue
        out.append(f)
    bills = sorted({f[3] for f in out if re.match(r"^(HB|SB)\d", f[3])})
    keep = set(bills[:2])
    for f in out:
        if f[3] not in lsr_map:
            lsr_map[f[3]] = f[1] if f[3] in keep else f"{7000 + len(lsr_map):04d}"
    rows = []
    for f in out:
        g = list(f)
        g[0], g[1] = "2027", lsr_map[f[3]]
        g = [shift(x) for x in g]
        rows.append("|".join(g))
    return rows, lsr_map, sorted(keep)


def fake_lsrs(template, lsr_map, n=20):
    """LSRs.txt records of 2027 for the batch's first `n` bills, titled
    TEST-2027 so a leak either way is a string search."""
    t = lines(template)[0].split("|")
    rows = []
    for bill, lsr in list(sorted(lsr_map.items()))[:n]:
        g = list(t)
        m = re.match(r"([A-Z]+)(\d+)", bill)
        g[0], g[1] = "2027", lsr
        g[2] = f"TEST-2027 sentinel title of {bill}."
        g[3] = "S" if bill.startswith("S") else "H"
        g[8] = f"27-{lsr}"
        g[9] = f"{m.group(1)}  {int(m.group(2)):04d}"
        g[10] = bill
        for i in (11, 12, 13, 14, 21, 22, 31, 32):
            if i < len(g):
                g[i] = ""
        rows.append("|".join(g))
    return rows


def fake_sponsors(lsr_rows, legislators):
    """LsrsOnly.txt and LsrSponsors.txt rows of 2027 for those records: each
    bill's prime sponsor a sitting member, by the roster given."""
    ids = [ln.split("|")[0] for ln in lines(legislators) if "|" in ln]
    only, spons = [], []
    for i, ln in enumerate(lsr_rows):
        f = ln.split("|")
        mid = ids[(i * 7) % len(ids)]
        only.append(f"27-{f[1]}|{mid}|{int(f[1])}|2027|Prime|{f[10]}|{f[3]}|{f[2]}")
        spons.append(f"2027|{f[1]}|1|{mid}|1")
    return only, spons


def new_roster(legislators, members):
    """A third of the House new on Organization Day, the same people in
    legislators.txt and Members.txt (R1 of the design); and of those who
    stay, one in another district and one of another party, whose 2025-2026
    records must keep the seat and party of the term (the review of 5
    October 2026). (legislators, members, [(old id, new id)], {id: (field,
    was, now)})."""
    leg = lines(legislators)
    mem = lines(members)
    head, mrows = mem[0], mem[1:]
    swapped, out, moved = [], [], {}
    house = [i for i, ln in enumerate(leg) if ln.split("|")[4:5] == ["H"]]
    pick = set(house[::3])
    stay = [i for i in house if i not in pick]
    by_mail = {}
    for i, ln in enumerate(leg):
        f = ln.split("|")
        if i in pick:
            k = len(swapped)
            new = f"{990000 + k}"
            old_mail = f[14].strip().lower()
            f[0], f[1], f[2], f[3] = new, f"Newmember{k}", "Test", ""
            f[14] = f"Test.Newmember{k}@gc.nh.gov"
            by_mail[old_mail] = (f[1], f[2], f[14])
            swapped.append((ln.split("|")[0], new))
        elif stay and i == stay[0]:
            moved[f[0]] = ("district", f[7], str(int(f[7] or 0) + 40))
            f[7] = moved[f[0]][2]
        elif len(stay) > 1 and i == stay[1]:
            moved[f[0]] = ("party", f[8], "D" if f[8].upper() == "R" else "R")
            f[8] = moved[f[0]][2]
        out.append("|".join(f))
    cols = {c.strip().lower(): j for j, c in enumerate(head.split("\t"))}
    mout = [head]
    for r in mrows:
        g = r.split("\t")
        key = g[cols["workemail"]].strip().lower() if cols.get("workemail", 99) < len(g) else ""
        if key in by_mail:
            last, first, mail = by_mail[key]
            g[cols["lastname"]], g[cols["firstname"]], g[cols["workemail"]] = last, first, mail
        mout.append("\t".join(g))
    return (join(out), BOM + "".join(r + "\r\n" for r in mout).encode("utf-8"), swapped,
            moved)


def rollcalls_2027():
    """Two House roll calls of 2027, and their ballots."""
    s = ["2027|H|1|1/7/2027 10:15:33 AM||300|2|34|38|||Call of the Roll|||",
         "2027|H|2|1/7/2027 10:25:50 AM||57|280|20|38|||Rules Suspension|||"]
    return join(s), join(["2027|H|1|332247|960||Yea|", "2027|H|2|332247|960||Nay|"])


class Batches:
    """Every export the nights are answered with, made once from the frozen
    (pre-turn) day files."""

    def __init__(self, root):
        day = root / "frozen" / TERM / "day"
        self.base = {p.name: p.read_bytes() for p in day.iterdir() if p.is_file()}
        b = self.base
        self.batch, self.lsr_map, self.coincide = first_batch(b["Docket.txt"])
        self.resolutions, _, _ = first_batch(b["Docket.txt"], resolutions_only=True)
        self.lsrs = fake_lsrs(b["LSRs.txt"], self.lsr_map)
        self.leg_r1, self.mem_r1, self.swapped, self.moved = new_roster(b["legislators.txt"],
                                                                       b["Members.txt"])
        self.only, self.spons = fake_sponsors(self.lsrs, self.leg_r1)
        self.straggle = lines(b["Docket.txt"])[-10:]

    def export(self, docket=None, lsrs=None, sponsors=True, rollcalls="old", roster="old",
               empty=()):
        """{name: bytes} for one night."""
        b = dict(self.base)
        if docket is not None:
            b["Docket.txt"] = join(docket)
        if lsrs is not None:
            b["LSRs.txt"] = join(lsrs)
            if sponsors:
                b["LsrsOnly.txt"], b["LsrSponsors.txt"] = join(self.only), join(self.spons)
        if rollcalls == "empty":
            b["RollCallSummary.txt"] = b["RollCallHistory.txt"] = BOM
        elif rollcalls == "2027":
            b["RollCallSummary.txt"], b["RollCallHistory.txt"] = rollcalls_2027()
        if roster == "new":
            b["legislators.txt"], b["Members.txt"] = self.leg_r1, self.mem_r1
            if lsrs is None:
                # THE SITTING ONLY: LsrsOnly.txt lists sitting members alone
                # (none of its 353 was off the roster on 5 October 2026), so
                # the export of a night whose roster has turned drops the
                # departed members' sponsorships of 2025-2026 with them.
                sitting = {ln.split("|")[0] for ln in lines(self.leg_r1)}
                b["LsrsOnly.txt"] = join([ln for ln in lines(b["LsrsOnly.txt"])
                                          if ln.split("|")[1:2] and ln.split("|")[1] in sitting])
        for n in empty:
            b[n] = BOM
        return b

    def variant(self, v, **kw):
        base_docket = lines(self.base["Docket.txt"])
        if v == "R":
            return self.export(docket=self.resolutions, roster="new", **kw)
        if v == "OD":
            # Organization Day's roster, the files still 2025-2026's.
            return self.export(roster="new", **kw)
        if v == "S":
            # Only the sponsor files naming 2027 (the review of 5 October
            # 2026): the guard and the build must agree it is a new term.
            b = self.export(**kw)
            b["LsrsOnly.txt"] = join(lines(b["LsrsOnly.txt"]) + self.only)
            b["LsrSponsors.txt"] = join(lines(b["LsrSponsors.txt"]) + self.spons)
            return b
        if v == "B":
            return self.export(docket=self.batch, lsrs=self.lsrs, roster="new", **kw)
        if v == "B+":
            grown = self.batch + [r.replace("Introduced", "Introduced again", 1)
                                  for r in self.batch[-5:]]
            return self.export(docket=grown, lsrs=self.lsrs, roster="new", **kw)
        if v == "B+late":
            # ... and a 2026 row entered after the switch: a chapter number, say.
            grown = self.batch + [r.replace("Introduced", "Introduced again", 1)
                                  for r in self.batch[-5:]] + self.straggle[-1:]
            return self.export(docket=grown, lsrs=self.lsrs, roster="new", **kw)
        if v == "C":
            return self.export(docket=self.batch + self.straggle, lsrs=self.lsrs, roster="new", **kw)
        if v == "D":
            return self.export(docket=base_docket + self.batch, **kw)
        raise ValueError(v)


# ---- the night, through nightly.main() ---------------------------------------------------

class Nights:
    """nightly.main() in the copy, with every step it starts answered here."""

    def __init__(self, root, logs):
        self.root, self.logs = root, logs
        os.chdir(root)
        copy_on_path(root)
        sys.dont_write_bytecode = True
        os.environ.update(env())
        for k in ("GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY", "GITHUB_ACTIONS", "GITHUB_SHA"):
            os.environ.pop(k, None)
        self._no_network()
        import nightly as NI
        import snapshot_gencourt as SG
        import refusal
        import probe_db
        import caption_span                                     # noqa: F401
        self.NI, self.SG, self.refusal, self.PD = NI, SG, refusal, probe_db
        NI.run = self.fake
        NI.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time)
        SG.time = types.SimpleNamespace(sleep=lambda s: None, time=time.time)
        NI.live_fingerprint = lambda base, timeout=180: "an-older-build"
        NI.tracked_changes = lambda: ([], [])
        NI.captions_compared = lambda work="work", markers="candidate_segments.json": (2850, 2851)
        NI.upload_and_check = lambda a, site, target, base: True
        NI.current_branch = lambda: NI.REPO_BRANCH
        self.state = {"export": {}, "views": None, "build": "stub", "label": ""}
        self.calls = []

    @staticmethod
    def _no_network():
        def no(*a, **k):
            raise OSError("the rehearsal asks nobody anything")
        socket.create_connection = no
        socket.socket.connect = no
        urllib.request.urlopen = no

    # The steps.
    def fake(self, args, label, cwd=None):
        NI, name = self.NI, Path(args[0]).name
        self.calls.append([name] + list(args[1:]))
        NI.say(f"\n--- {label} ---")
        if name == "preflight.py":
            rc = 0
        elif name == "snapshot_gencourt.py":
            rc = self.snapshot(args)
        elif name == "fetch_day_db.py":
            rc = self.dbday()
        elif name == "fetch_archive_db.py":
            rc = self.study(args, cwd)
        elif name in ("fetch_lsrs.py",):
            rc = 0
        elif name == "fetch_calendar_archive.py":
            rc = 1
        elif name == "gc_changes.py":
            out = Path(args[args.index("--out") + 1])
            out.parent.mkdir(exist_ok=True)
            out.write_text("# changes (rehearsal)\n", encoding="utf-8")
            rc = 0
        elif name == "build_all.py":
            rc = self.build(args)
        elif name == "check_site.py":
            rc = (sh(["check_site.py"] + list(args[1:]), self.root,
                     self.logs / f"check_site_{self.state['label']}.log")[0]
                  if self.state["build"] == "real" else 0)
        else:
            raise AssertionError(f"the night started {name}, which the rehearsal does not "
                                 "stand in for")
        NI.say(f"  (0s, exit {rc})")
        return rc

    def snapshot(self, args):
        SG = self.SG
        served = self.state["export"]

        def get(url, timeout=120):
            if url == SG.PAGE:
                return b"<html><body><h1>DYNAMIC DATA FILES</h1></body></html>"
            return served.get(url.rsplit("/", 1)[-1], BOM)
        SG.get = get
        a = argparse.Namespace(dir=args[args.index("--dir") + 1],
                               into=args[args.index("--into") + 1],
                               allow_shrink="--allow-shrink" in args,
                               allow_turn="--allow-turn" in args, delay=0.0, plan=False)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc = SG.run(a, types.SimpleNamespace(still=lambda: True))
        for ln in out.getvalue().splitlines():
            self.NI.say("  " + ln, echo=False)
        return rc

    def dbday(self):
        NI = self.NI
        shutil.rmtree(NI.DB_DAY, ignore_errors=True)
        if not self.state["views"]:
            NI.DB_DAY.mkdir(parents=True)
            (NI.DB_DAY / "source.json").write_text(json.dumps(
                {"asked": datetime.now().isoformat(timespec="seconds"),
                 "views": {"Docket": {"error": "CONNECT_FAIL: the rehearsal has no database"}}}),
                encoding="utf-8")
            return 1
        shutil.copytree(self.state["views"], NI.DB_DAY)
        return 0

    def study(self, args, cwd):
        """The study views as installed: taken, and nothing moves."""
        views = [args[i + 1] for i, x in enumerate(args) if x == "--only"]
        db = Path(cwd) / "db"
        db.mkdir(parents=True, exist_ok=True)
        man_in = self.NI.load_json(Path("db") / "_manifest.json") or {}
        man = {}
        for v in views:
            src = Path("db") / f"{v}.psv"
            if src.exists():
                shutil.copy2(src, db / f"{v}.psv")
                man[v] = {**(man_in.get(v) or {}), "rows": self.NI.count_lines(src)}
        (db / "_manifest.json").write_text(json.dumps(man), encoding="utf-8")
        return 0

    def build(self, args):
        if self.state["build"] != "real":
            return 0
        # AS GITHUB'S MACHINE BUILDS: from an empty site/, but for the one
        # file of last night's the kit brings (site/committees.json). On the
        # laptop's folder the departed members' pages of the night before are
        # still there, and check_site rightly refuses to deploy them.
        site = self.root / "site"
        keep = (site / "committees.json").read_bytes() if (site / "committees.json").exists() else None
        shutil.rmtree(site, ignore_errors=True)
        if keep is not None:
            site.mkdir()
            (site / "committees.json").write_bytes(keep)
        rc, secs, _ = sh(list(args), self.root, self.logs / f"build_{self.state['label']}.log")
        print(f"    (the full build: exit {rc}, {secs / 60:.0f} min)", flush=True)
        return rc

    def night(self, label, *argv, export=None, views=None, build="stub", run_id="900"):
        """One night: (exit, verdict, the snapshot's install record)."""
        NI = self.NI
        self.state.update(export=export or {}, views=views, build=build, label=label)
        NI.LOG = []
        del self.calls[:]
        os.environ["GITHUB_RUN_ID"] = run_id
        sys.argv = ["nightly.py", *argv]
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = NI.main()
            except SystemExit as e:
                code = e.code
        (self.logs / f"night_{label}.log").write_text("\n".join(NI.LOG), encoding="utf-8")
        v = NI.load_json(NI.VERDICT) or {}
        rec = NI.load_json(NI.snapshot_day("nh-archive") / NI.INSTALL_RECORD) or {}
        RESULTS["nights"].append({"night": label, "argv": list(argv), "exit": code,
                                  "fetch": v.get("fetch"), "built": v.get("built"),
                                  "publishable": v.get("publishable"), "clean": v.get("clean"),
                                  "gates": v.get("gates"), "new_term": v.get("new_term"),
                                  "warnings": v.get("warnings"), "page": NI.plain_why(v)
                                  if not v.get("clean") else "",
                                  "steps": [c[0] for c in self.calls]})
        print(f"\n{label}: exit {code}, fetch {str(v.get('fetch'))[:150]!r}, built {v.get('built')}, "
              f"publishable {v.get('publishable')}, clean {v.get('clean')}", flush=True)
        return code, v, rec


# ---- what the turn must leave as it was ---------------------------------------------------

def keep_pre_turn(root, pre):
    """The pre-turn build's 2025-2026, kept to compare the turn's with."""
    pre.mkdir(parents=True, exist_ok=True)
    bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
    sp = json.loads((root / "data" / "sponsors.json").read_text(encoding="utf-8"))
    (pre / "bills.json").write_text(json.dumps({TERM: bills.get(TERM)}), encoding="utf-8")
    (pre / "sponsors.json").write_text(json.dumps({TERM: sp.get(TERM)}), encoding="utf-8")
    # The term's index file, not index.json, which dev retired on 5 October 2026.
    for rel in ("site/meta.json", "proceedings.csv", "senate_hearing_reports.json",
                "chapters.json", "topics_assigned.json", f"site/idx/{TERM}.json", "floor_index.json",
                "data/member_votes.json"):
        if (root / rel).exists():
            (pre / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / rel, pre / rel)
    for rel in ("site/bills/2025", "site/bills/2026", "site/bill/2025", "site/bill/2026",
                "site/versions/2025", "site/versions/2026"):
        if (root / rel).is_dir():
            shutil.rmtree(pre / rel, ignore_errors=True)
            shutil.copytree(root / rel, pre / rel)


def json_diff_keys(a, b, prefix=""):
    """The keys whose values differ between two JSON objects, dotted, one level
    into nested objects."""
    out = []
    for k in sorted(set(a) | set(b)):
        x, y = a.get(k, "<absent>"), b.get(k, "<absent>")
        if x == y:
            continue
        if isinstance(x, dict) and isinstance(y, dict) and not prefix:
            out += json_diff_keys(x, y, f"{k}.")
        else:
            out.append(prefix + k)
    return out


EXPECTED = re.compile(r"^(archived|archived\..*|session_over)$")
# What a sponsor gains when a name the pre-turn build left unlinked finds its
# page: a member who left mid-term, whose bill status sponsor carries a web id
# and whose name the sitting roster of the day did not hold. After the turn
# the term looks for such a name among the members who left as well
# (build_site_v2.bill_sponsor_list's `left`), so they gain the link to the
# page they had all along, and their seat reads as everyone else's.
LINK_GAINED = {"slug", "display_full", "district_label", "display", "display_plain"}


def link_gained(was, now, site):
    """True when two sponsor lists differ only by names that gained a link to a
    page that is there."""
    if not isinstance(was, list) or not isinstance(now, list) or len(was) != len(now):
        return False
    for x, y in zip(was, now):
        if x == y:
            continue
        keys = {k for k in set(x) | set(y) if x.get(k) != y.get(k)}
        if x.get("slug") or not y.get("slug") or not keys <= LINK_GAINED or \
                not (site / "legislator" / f"{y['slug']}.html").exists():
            return False
    return True


def page_moved(was, now, site):
    """True when two lists of sponsors differ only in the link of members who
    gained one (link_gained) or whose own page moved with the seat
    Organization Day gave them -- the label still the seat they sat in, the
    link to the page there is now -- and in at least one of the latter."""
    if not isinstance(was, list) or not isinstance(now, list) or len(was) != len(now):
        return False
    moved = False
    for x, y in zip(was, now):
        if x == y:
            continue
        keys = {k for k in set(x) | set(y) if x.get(k) != y.get(k)}
        if not y.get("slug") or not (site / "legislator" / f"{y['slug']}.html").exists():
            return False
        if keys == {"slug"} and x.get("slug"):
            moved = True
        elif x.get("slug") or not keys <= LINK_GAINED:
            return False
    return moved


def speaker_moved(was, now, site):
    """True when two lists of a bill's stations differ only in the link of a
    hearing report's speaker whose own page moved with their seat."""
    leaves = []

    def walk(x, y, path):
        if x == y:
            return
        if isinstance(x, dict) and isinstance(y, dict):
            for k in set(x) | set(y):
                walk(x.get(k), y.get(k), path + (k,))
        elif isinstance(x, list) and isinstance(y, list) and len(x) == len(y):
            for a, b in zip(x, y):
                walk(a, b, path)
        else:
            leaves.append((path, x, y))
    walk(was, now, ())
    return bool(leaves) and all(
        p[-2:] == ("member", "slug") and x and y
        and (site / "legislator" / f"{y}.html").exists() for p, x, y in leaves)


def compare_term(root, pre, label, finished=True, other_day=None):
    """2025-2026 after the turn against the pre-turn build: what differs, by field.
    `finished` False is a night before the switch whose roster has turned
    (OD, DB1): the term is still the session's, and nothing of it moves --
    not the archived mark, not the session_over note -- but a sponsor who
    left mid-term gaining a link.

    `other_day` is the bills whose docket rows the night's files hold
    otherwise than the pre-turn build's (DB1's database views are another
    day's than the export installed): their history, stations and status may
    move with the docket, and are counted apart; their sponsors and ballots
    may not, and the proceedings of every other bill are held equal."""
    other_day = set(other_day or ())
    from collections import Counter
    bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
    sp = json.loads((root / "data" / "sponsors.json").read_text(encoding="utf-8"))
    was_b = json.loads((pre / "bills.json").read_text(encoding="utf-8"))[TERM]
    was_s = json.loads((pre / "sponsors.json").read_text(encoding="utf-8"))[TERM]
    now_b = bills.get(TERM) or {}
    differ = [b for b in was_b if {k: v for k, v in (now_b.get(b) or {}).items()
                                   if k != "archived" or not finished} != was_b[b]]
    note(len(now_b) == len(was_b) and not differ,
         f"{label}: data/bills.json {TERM} is the pre-turn slice record for record"
         + (" but the archived mark" if finished else "")
         + f" ({len(now_b):,} of {len(was_b):,} records, {len(differ)} differing)", differ[:5])
    if finished:
        note(all(r.get("archived") for r in now_b.values()),
             f"{label}: every {TERM} record carries the archived mark")
    # The ballots of the term, by who cast them and how they are named.
    if (pre / "data" / "member_votes.json").exists():
        def ballots(p):
            return Counter((v["member_id"], v["name"], v["party"], v["vote_number"], v["year"])
                           for v in json.loads(p.read_text(encoding="utf-8"))
                           if v.get("year") in ("2025", "2026"))
        a, b = ballots(pre / "data" / "member_votes.json"), ballots(root / "data" / "member_votes.json")
        unnamed = sum(n for k, n in b.items() if str(k[1]).startswith(("Member #", "Former member")))
        note(a == b, f"{label}: the term's {sum(a.values()):,} ballots are cast and named as before, "
                     f"each member with their party ({unnamed:,} unnamed)",
             [k for k in (set(a) ^ set(b))][:4])
    note((sp.get(TERM) or {}) == was_s,
         f"{label}: data/sponsors.json {TERM} equal to the pre-turn slice, every list "
         f"({len(sp.get(TERM) or {}):,} of {len(was_s):,})")
    # EVERY BILL'S RECORD, as the page carries it: in site/bills/<year>/ where
    # it is too large to travel inside its page, else inside the page itself
    # (build_bill_pages.embedded) -- so all of the term's bills, and not the
    # few files the per-bill folder keeps.
    copy_on_path(root)
    import build_bill_pages as BBP

    def record(site, yr, bid):
        f = site / "bills" / yr / f"{bid}.json"
        raw = f.read_text(encoding="utf-8") if f.exists() else \
            BBP.embedded(site / "bill" / yr / f"{bid.lower()}.html")
        return json.loads(raw) if raw else None
    fields, pages, samples, missing = Counter(), Counter(), {}, []
    rows0 = json.loads((pre / "site" / "idx" / f"{TERM}.json").read_text(encoding="utf-8"))
    mine = [(str(r.get("year")), r["id"]) for r in rows0]
    for yr, bid in mine:
        a, b = record(pre / "site", yr, bid), record(root / "site", yr, bid)
        if a is None or b is None:
            missing.append(f"{yr}/{bid}")
            continue
        for k in json_diff_keys(a, b):
            if bid in other_day and k.split(".")[0] not in ("sponsors", "rollcalls"):
                fields["(another day's docket)"] += 1
                continue
            # A CACR's journey and status turn with the calendar, not the
            # term: "goes to the voters in November 2026" is "went" once the
            # election has passed, which by the turn it has.
            key = (f"{k} (CACR)" if bid.startswith("CACR")
                   and k.split(".")[0] in ("journey", "status", "next_step") else k)
            if k == "sponsors" and link_gained(a.get(k), b.get(k), root / "site"):
                key = "sponsors (a link gained)"
            elif k == "sponsors" and page_moved(a.get(k), b.get(k), root / "site"):
                key = "sponsors (a page moved with its seat)"
            elif k == "stations" and speaker_moved(a.get(k), b.get(k), root / "site"):
                key = "stations (a speaker's page moved with their seat)"
            fields[key] += 1
            top = k.split(".")[0]
            samples.setdefault(key, f"{yr}/{bid}: {str(a.get(top))[:160]} -> "
                                    f"{str(b.get(top))[:160]}")
    for year in ("2025", "2026"):
        p0, p1 = pre / "site" / "bill" / year, root / "site" / "bill" / year
        for p in p0.rglob("*.html"):
            q = p1 / p.relative_to(p0)
            pages["same" if q.exists() and q.read_bytes() == p.read_bytes() else
                  "differ" if q.exists() else "gone"] += 1
        pages["new"] += sum(1 for q in p1.rglob("*.html") if not (p0 / q.relative_to(p1)).exists())
    other = {k: n for k, n in fields.items() if (not EXPECTED.match(k) or not finished)
             and "(CACR)" not in k and k not in ("sponsors (a link gained)",
                                                 "(another day's docket)",
                                                 "sponsors (a page moved with its seat)",
                                                 "stations (a speaker's page moved with their seat)")}
    RESULTS.setdefault("term_fields", {})[label] = {"fields": dict(fields), "samples": samples,
                                                    "pages": dict(pages), "missing": missing}
    print(f"    the {len(mine):,} records of {TERM}: fields that differ {dict(fields)}")
    print(f"    site/bill/{{2025,2026}} pages: {dict(pages)}")
    note(not missing, f"{label}: every {TERM} bill has its record on the site", missing[:5])
    note(not other, f"{label}: the {len(mine):,} records of {TERM} differ from the pre-turn build "
                    + ("only in the archived mark, the session_over note, a CACR's election, "
                       "a sponsor who left mid-term gaining a link and one whose page moved with "
                       "their seat" if finished else
                       "only in a sponsor who left mid-term gaining a link and one whose page "
                       "moved with their seat"),
         {k: samples.get(k) for k in list(other)[:6]})
    # The term's index file's entries (site/idx/<term>.json; index.json is
    # retired).
    def idx(p):
        rows = json.loads(p.read_text(encoding="utf-8"))
        return {(str(r.get("year")), r.get("id")): r for r in rows if isinstance(r, dict)}
    i0 = idx(pre / "site" / "idx" / f"{TERM}.json")
    i1 = idx(root / "site" / "idx" / f"{TERM}.json")
    kf = Counter()
    for k in i0:
        if k[1] in other_day:
            continue
        for f in json_diff_keys(i0[k], i1.get(k, {})):
            kf[f"{f} (CACR)" if str(k[1]).startswith("CACR") else f] += 1
    RESULTS["term_fields"][label]["index"] = dict(kf)
    print(f"    site/idx/{TERM}.json entries: {len(i0):,} against {len(i1):,}; fields that differ: "
          f"{dict(kf)}")
    note(len(i0) == len(i1) and not [f for f in kf if (f != "archived" or not finished)
                                      and "(CACR)" not in f],
         f"{label}: site/idx/{TERM}.json's {len(i0):,} entries differ only in "
         + ("the archived mark and a CACR's election" if finished else "a CACR's election"),
         dict(kf))
    # The table of proceedings, by content.
    import csv
    def procs(p):
        with open(p, encoding="utf-8", newline="") as fh:
            return sorted(tuple(r.values()) for r in csv.DictReader(fh) if r.get("term") == TERM
                          and r.get("bill") not in other_day)
    a, b = procs(pre / "proceedings.csv"), procs(root / "proceedings.csv")
    note(a == b, f"{label}: proceedings.csv's {len(a):,} rows of {TERM} equal in content",
         f"{len(a)} against {len(b)}")
    for rel, key in (("senate_hearing_reports.json", TERM), ("chapters.json", TERM),
                     ("topics_assigned.json", TERM)):
        if (pre / rel).exists():
            x = json.loads((pre / rel).read_text(encoding="utf-8")).get(key)
            y = json.loads((root / rel).read_text(encoding="utf-8")).get(key)
            note(x == y, f"{label}: {rel}'s {key} equal ({len(x or {}):,} bills)")
    # The floor debates of the term, by bill and date.
    def floor(p):
        d = json.loads(p.read_text(encoding="utf-8"))
        return {b: [e for e in (v if isinstance(v, list) else [v])
                    if str((e or {}).get("date") or "")[:4] in ("2025", "2026")]
                for b, v in d.items()}
    if (pre / "floor_index.json").exists():
        x, y = floor(pre / "floor_index.json"), floor(root / "floor_index.json")
        x = {b: v for b, v in x.items() if v}
        y = {b: v for b, v in y.items() if v}
        note(x == y, f"{label}: floor_index.json's {TERM} debates equal "
                     f"({sum(len(v) for v in x.values()):,} entries)")


def check_new_term(root, batches, label):
    """2027-2028 is there with its first batch, and takes nothing of 2025-2026."""
    bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
    new = bills.get(NEW) or {}
    want = {f.split("|")[3] for f in batches.batch}
    note(want <= set(new), f"{label}: data/bills.json {NEW} holds the batch's "
                           f"{len(want)} measures ({len(new)} in all)", sorted(want - set(new))[:6])
    note((root / "site" / "idx" / f"{NEW}.json").exists(), f"{label}: site/idx/{NEW}.json written")
    old_titles = {r.get("title") for r in (bills.get(TERM) or {}).values() if r.get("title")}
    # EACH 2027 PAGE'S OWN RECORD (the review of 5 October 2026): these read
    # site/bills/2027/*.json, which the build does not write for records this
    # small -- they travel inside their pages -- so they examined nothing and
    # passed. A record is read as compare_term reads one, and none read fails.
    copy_on_path(root)
    import build_bill_pages as BBP

    def record(bid):
        f = root / "site" / "bills" / "2027" / f"{bid}.json"
        raw = f.read_text(encoding="utf-8") if f.exists() else \
            BBP.embedded(root / "site" / "bill" / "2027" / f"{bid.lower()}.html")
        return json.loads(raw) if raw else None
    pages = sorted({p.stem.upper() for p in (root / "site" / "bill" / "2027").glob("*.html")}
                   | {p.stem.upper() for p in (root / "site" / "bills" / "2027").glob("*.json")})
    leaked, read = [], 0
    for bid in pages:
        r = record(bid)
        if r is None:
            continue
        read += 1
        if r.get("title") and r.get("title") in old_titles:
            leaked.append(bid)
    note(read and not leaked, f"{label}: no 2027 bill page carries a 2025-2026 title "
                              f"({read} of {len(pages)} pages' records read)", leaked[:6])
    for b in batches.coincide:
        r = new.get(b) or {}
        # The subject: a committee may come from the bill's own docket rows,
        # which in this fake are 2025's words relabelled; a subject comes only
        # from the bill records and the Legislation fill, which is the join
        # that once ignored the year. So the test is a subject CODE, or the
        # namesake's own subject. Not any subject at all: SubjectCodes.txt
        # gives "Regular Meeting" no code, so a bill whose LSR row names none
        # reads that name in data/bills.json (HR 48 of 2026 does today), and
        # the site retires it (build_site_v2.unify_vocabulary) before a page
        # shows it.
        old = (bills.get(TERM) or {}).get(b) or {}
        took = {k: r.get(k) for k in ("subject_code",) if r.get(k)}
        if old.get("subject_code") and r.get("subject") == old.get("subject"):
            took["subject"] = r.get("subject")
        rec = record(b)
        # Anywhere in it: a docket line's count or a hearing station's.
        testimony = rec is not None and '"testimony"' in json.dumps(rec)
        note(rec is not None and not took and not testimony,
             f"{label}: {b} of 2027, given a 2025 bill's number and LSR, takes neither its "
             "committee, subject nor sign-in counts, by its page's own record",
             {**took, "testimony": testimony, "record": rec is not None})
    sp = json.loads((root / "data" / "sponsors.json").read_text(encoding="utf-8"))
    stray = [b for b in (sp.get(NEW) or {}) if b not in new]
    note(not stray, f"{label}: sponsors.json {NEW} lists only bills of {NEW}", stray[:6])


# ---- the rehearsal --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--copy", required=True, help="the scratch folder (outside the repository)")
    ap.add_argument("--reuse", action="store_true",
                    help="the copy is made and built by a run that stopped before its first "
                         "night: run the nights")
    ap.add_argument("--guards", action="store_true", help="no full build; the guards only")
    ap.add_argument("--views", help="a folder of the database's views for the database night")
    ap.add_argument("--pre-only", action="store_true",
                    help="make the copy, freeze and build the pre-turn baseline, and stop")
    a = ap.parse_args()
    root = Path(a.copy).resolve()
    logs = root / "_rehearsal"
    pre = logs / "pre"
    if not a.reuse:
        make_copy(root)
    logs.mkdir(parents=True, exist_ok=True)

    # THE FREEZE, IN THE COPY: the tool itself, on the copy's installed files.
    for what in (["--views"], ["--session"], ["--check"]):
        if what == ["--views"] and (root / "db" / "term" / TERM / "manifest.json").exists():
            print("freeze --views: db/term is in the copy already (the kit's); kept")
            continue
        rc, _, out = sh(["freeze_term.py"] + what, root)
        print(f"freeze_term.py {what[0]}: exit {rc}\n  " + "\n  ".join(out.strip().splitlines()[-6:]))
        note(rc == 0, f"freeze_term.py {what[0]} in the copy")

    # THE PRE-TURN DATA, for the build_data-level comparisons (a minute).
    if not (pre / "bills.json").exists():
        rc, _, _ = sh(["build_data.py", "--dir", ".", "--out", str(logs / "pre_data")], root)
        note(rc == 0, "build_data on the pre-turn files")
        pre.mkdir(parents=True, exist_ok=True)
        for f in ("bills", "sponsors"):
            d = json.loads((logs / "pre_data" / f"{f}.json").read_text(encoding="utf-8"))
            (pre / f"{f}.json").write_text(json.dumps({TERM: d.get(TERM)}), encoding="utf-8")
    # THE PRE-TURN BUILD, the baseline of every comparison.
    if not a.guards and not (a.reuse and (pre / "site" / "idx" / f"{TERM}.json").exists()):
        rc, secs, _ = sh(["build_all.py", "--local", "--no-captions"], root, logs / "build_pre.log")
        print(f"pre-turn build: exit {rc} in {secs / 60:.0f} min")
        note(rc == 0, "the pre-turn build, with the freeze in place")
        keep_pre_turn(root, pre)
    if a.pre_only:
        (logs / "rehearsal.json").write_text(json.dumps(RESULTS, indent=1), encoding="utf-8")
        print(f"\n--pre-only: the copy and its pre-turn build are at {root}; --reuse runs the nights")
        return 1 if RESULTS["failed"] else 0
    N = Nights(root, logs)
    NI = N.NI
    # The census a night is gated against: this build's, as a night would keep it.
    site = Path("site")
    NI.write_json(NI.CENSUS, {"census": NI.census(site), "fingerprint": NI.fingerprint(site),
                              "day": DAY, "run_id": "899", "sha": ""})
    batches = Batches(root)
    pre_files = installed_state(root)
    print(f"\nthe batch: {len(batches.batch)} docket rows of 2027 ({len(batches.resolutions)} of them "
          f"Organization Day's resolutions), {len(batches.lsrs)} LSR records, {len(batches.swapped)} "
          f"House members new; {batches.coincide} keep a 2025 number and LSR")

    def refused_as_turn(label, v, rec, files_smaller):
        note(not v.get("built") and not v.get("publishable") and str(v.get("fetch")).startswith("turned"),
             f"{label}: refused as a new term, nothing installed or built", v.get("fetch"))
        note(installed_state(root) == pre_files, f"{label}: the installed files are as they were")
        note(NI.NEW_TERM_TURN in NI.plain_why(v), f"{label}: the run's page says a new term and which box",
             NI.plain_why(v)[:200])
        if files_smaller is not None:
            note(bool(rec.get("shrunk")) == files_smaller,
                 f"{label}: {'some' if files_smaller else 'no'} file much smaller",
                 rec.get("shrunk"))

    # G1: an ordinary night.
    code, v, rec = N.night("G1", "--runner", export=batches.export(), run_id="901")
    note(v.get("fetch") == "installed" and installed_state(root) == pre_files,
         "G1: the export as installed is installed, and nothing moves", v.get("fetch"))
    # G2-G5: the turn on a scheduled night; G10, only the sponsor files naming 2027.
    for label, var in (("G2", "R"), ("G3", "B"), ("G4", "C"), ("G5", "D"), ("G10", "S")):
        code, v, rec = N.night(label, "--runner", export=batches.variant(var), run_id="902")
        refused_as_turn(f"{label} ({var})", v, rec, False if var in ("D", "S") else None)
    # G6: the 20 September pattern.
    code, v, rec = N.night("G6", "--runner", export=batches.export(
        empty=("LSRs.txt", "legislators.txt")), run_id="906")
    note(str(v.get("fetch")).startswith("empty: 2 of 14") and "the database" in " ".join(v.get("tried") or []),
         "G6: two files empty and the rest whole is still 'empty', and the database is asked",
         (v.get("fetch"), v.get("tried")))
    # G7: the roll calls empty before any turn.
    code, v, rec = N.night("G7", "--runner", export=batches.export(rollcalls="empty"), run_id="907")
    note(str(v.get("fetch")).startswith("empty: 2 of 14") and installed_state(root) == pre_files,
         "G7: empty roll-call files with no new term are a failure, not data", v.get("fetch"))
    # G8: a New term run whose freeze is stale: a row of the term entered
    # after the freeze -- the clerk's "Died on Table, Session ended" of the
    # 10th of October, say.
    late = lines(pre_files["Docket.txt"])[-1].split("|")
    late[5] = "Died on Table, Session ended"
    (root / "Docket.txt").write_bytes(pre_files["Docket.txt"] + "|".join(late).encode() + b"\r\n")
    code, v, rec = N.night("G8", "--runner", "--new-term", export=batches.variant("B"), run_id="908")
    note(code == 1 and (v.get("new_term") or {}).get("refused") == NI.REFUSED_FREEZE
         and "snapshot_gencourt.py" not in [c[0] for c in N.calls],
         "G8: a New term run with a stale freeze stops before any request", v.get("new_term"))
    restore(root, pre_files)
    # G9: the New term run takes empty roll-call files.
    code, v, rec = N.night("G9", "--runner", "--new-term",
                           export=batches.variant("B", rollcalls="empty"), run_id="909")
    note(v.get("fetch") == "installed" and (root / "RollCallSummary.txt").read_bytes() == BOM,
         "G9: the New term run installs the turn with the roll-call files empty", v.get("fetch"))
    restore(root, pre_files)
    real = "stub" if a.guards else "real"
    # THE TERM'S ROSTER, FROZEN FIRST (the review of 5 October 2026): a first
    # --session after Organization Day would freeze the next House as the
    # term's. On the copy's own files with the new roster, in a folder of its
    # own, it is refused.
    import freeze_term as FT
    late = logs / "first_freeze_late"
    shutil.rmtree(late, ignore_errors=True)
    late.mkdir(parents=True)
    restore(late, {**pre_files, "legislators.txt": batches.leg_r1, "Members.txt": batches.mem_r1})
    shutil.copy2(root / "verification_manifest.csv", late / "verification_manifest.csv")
    try:
        FT.freeze_session(TERM, root=late)
        said = "frozen"
    except FT.Refused as e:
        said = str(e)
    note(f"is not {TERM}'s roster" in said and not (late / "frozen").exists(),
         "a first --session over Organization Day's roster is refused", said[:200])
    shutil.rmtree(late, ignore_errors=True)
    # OD0, OD: ORGANIZATION DAY'S ROSTER BEFORE THE DOCKET TURNS. Without the
    # term's frozen roster nothing is installed; with it, the night installs
    # it, builds in full, and 2025-2026 -- still the session's -- is as it was.
    shutil.move(str(root / "frozen" / TERM), str(logs / "frozen_aside"))
    code, v, rec = N.night("OD0", "--runner", export=batches.variant("OD"), run_id="913")
    shutil.move(str(logs / "frozen_aside"), str(root / "frozen" / TERM))
    note(str(v.get("fetch")).startswith("roster") and installed_state(root) == pre_files
         and NI.NEW_TERM_ROSTER in NI.plain_why(v),
         "OD0: a new roster over a term with no frozen roster installs nothing, and says to freeze",
         (v.get("fetch"), NI.plain_why(v)[:160]))
    code, v, rec = N.night("OD", "--runner", export=batches.variant("OD"), build=real, run_id="914")
    note(v.get("fetch") == "installed" and b"Newmember0" in (root / "legislators.txt").read_bytes()
         and FT.own_roster_terms(root) == [TERM],
         "OD: Organization Day's roster goes in over the term's frozen roster, and the term's "
         "members are named from that", (v.get("fetch"), FT.own_roster_terms(root)))
    if not a.guards:
        note(v.get("built"), "OD: built in full", v.get("not_clean"))
        RESULTS.setdefault("od_verdict", {"publishable": v.get("publishable"),
                                          "gates": v.get("gates"), "not_clean": v.get("not_clean")})
        compare_term(root, pre, "OD", finished=False)
    restore(root, pre_files)
    # DB1, DB2: the database night between Organization Day and the switch.
    if a.views:
        run_db(N, root, Path(a.views), batches, pre_files, real, pre)
        restore(root, pre_files)

    # NT: THE SWITCH.
    code, v, rec = N.night("NT", "--runner", "--new-term",
                           export=batches.variant("B"), build=real, run_id="910")
    note(v.get("fetch") == "installed" and (rec.get("turned") or {}).get("to") == NEW,
         "NT: the New term run installs the turn", (v.get("fetch"), rec.get("turned")))
    if not a.guards:
        note(v.get("built") and v.get("publishable"), "NT: built, and publishable behind approval",
             v.get("not_clean"))
        # The publish job deploys by the verdict that came down with the site
        # (cloud.py site-down writes it to nightly.RUN_VERDICT): NT's own.
        NI.write_json(NI.RUN_VERDICT, NI.load_json(NI.VERDICT))
        code, _, _ = N.night("NT-publish", "--runner", "--deploy-to", "production", run_id="910")
        c = NI.load_json(NI.CENSUS) or {}
        note(code == 0 and c.get("new_term") and c.get("run_id") == "910",
             "NT: its publish makes its counts the baseline", c.get("run_id"))
        compare_term(root, pre, "NT")
        check_new_term(root, batches, "NT")
    else:
        NI.write_json(NI.CENSUS, {**(NI.load_json(NI.CENSUS) or {}), "run_id": "910", "new_term": True})
    after_switch = installed_state(root)
    # A1: the next night: grown, a 2026 row entered after the switch, and the
    # roll calls empty over 2026's frozen copies.
    code, v, rec = N.night("A1", "--runner", export=batches.variant("B+late", rollcalls="empty"),
                           build=real, run_id="911")
    note(v.get("fetch") == "installed" and {x["name"] for x in rec.get("released") or []}
         == {"RollCallSummary.txt", "RollCallHistory.txt"},
         "A1: the empty roll-call files go in over 2025-2026's frozen copies, without a second "
         "New term run", (v.get("fetch"), rec.get("released")))
    if not a.guards:
        note(v.get("clean") and v.get("publishable"), "A1: the night after the switch is clean",
             v.get("not_clean"))
        note(any("left out" in w and TERM in w for w in v.get("warnings") or []),
             "A1: the 2026 row entered after the switch is on the run's page, left out",
             v.get("warnings"))
        compare_term(root, pre, "A1")
        check_new_term(root, batches, "A1")
    # A2: the first roll calls of 2027.
    code, v, rec = N.night("A2", "--runner", export=batches.variant("B+", rollcalls="2027"),
                           run_id="912")
    note(v.get("fetch") == "installed" and b"2027|H|1|" in (root / "RollCallSummary.txt").read_bytes(),
         "A2: the first 2027 roll calls are installed", v.get("fetch"))
    # C, D and S after the switch, at build_data and narrative level.
    for var in ("C", "D", "S"):
        level(root, batches, var, pre, logs)

    os.chdir(REPO)
    (logs / "rehearsal.json").write_text(json.dumps(RESULTS, indent=1), encoding="utf-8")
    shutil.copy2(logs / "rehearsal.json", root / "rehearsal.json")
    n, bad = len(RESULTS["checks"]), len(RESULTS["failed"])
    print(f"\n{n - bad} of {n} expectations held" + (f"; FAILED: {RESULTS['failed']}" if bad else ""))
    print(f"record: {root / 'rehearsal.json'}")
    return 1 if bad else 0


def docket_days_apart(a, b):
    """{bill}: the bills of the term whose docket rows two dockets hold
    otherwise, by the first six columns (a database night rewrites the
    seventh)."""
    from collections import defaultdict

    def rows(data):
        out = defaultdict(set)
        for ln in lines(data):
            f = [x.strip() for x in ln.split("|")]
            if len(f) > 5 and f[0] in TERM.split("-"):
                out[f[3].upper()].add("|".join(f[:6]))
        return out
    x, y = rows(a), rows(b)
    return {k for k in set(x) | set(y) if x.get(k) != y.get(k)}


def run_db(N, root, views, batches, pre_files, real="stub", pre=None):
    """The database night at the turn: the views hold 2027's first rows and the
    new roster, and the export is empty. DB1 is built in full where `real`
    is, and its 2025-2026 compared as OD's is (the review of 5 October 2026:
    its build was a stub, and nobody looked at what it would publish)."""
    NI = N.NI
    work = root / "_rehearsal" / "views"
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(views, work)
    cols = json.loads((root / "db" / "_columns.json").read_text(encoding="utf-8"))
    # 2027's Organization Day rows in the docket view.
    dk = cols["Docket"]
    rows = []
    for ln in batches.resolutions:
        f = ln.split("|")
        r = {c: "" for c in dk}
        r.update(SessionYear="2027", LSR=f[1], ExpandedBillNo=f[3], StatusDate=f[2],
                 CondensedBillNo=f[3], LegislativeBody=f[4], Description=f[5],
                 DataBase="NHLegislatureDB", OrderDate=f[2], statusorder="1")
        rows.append("|".join(r[c] for c in dk))
    with open(work / "Docket.psv", "a", encoding="utf-8", newline="") as fh:
        fh.write("".join(x + "\r\n" for x in rows))
    # The new roster in the Legislators view, as Organization Day makes it:
    # the same third of the House no longer active, their rows kept (their
    # ballots still name them), and a new member, with an id and an employee
    # number of their own, sitting in each of their seats.
    lg = cols["Legislators"]
    swap = dict(batches.swapped)
    out, added = [], []
    for ln in (work / "Legislators.psv").read_text(encoding="utf-8").splitlines():
        f = ln.split("|")
        if len(f) == len(lg) and f[0] in swap and f[lg.index("Active")] == "True":
            k = list(swap).index(f[0])
            g = list(f)
            g[0], g[1], g[2], g[3], g[4] = swap[f[0]], f"Newmember{k}", "Test", f"{990000 + k}", ""
            g[lg.index("EMailAddress")] = f"Test.Newmember{k}@gc.nh.gov"
            f[lg.index("Active")] = "False"
            added.append("|".join(g))
        out.append("|".join(f))
    (work / "Legislators.psv").write_text("".join(x + "\r\n" for x in out + added),
                                          encoding="utf-8", newline="")
    src = json.loads((work / "source.json").read_text(encoding="utf-8"))
    for v, extra in (("Docket", len(rows)), ("Legislators", len(added))):
        src["views"][v]["rows"] = src["views"][v]["count"] = src["views"][v]["rows"] + extra
    (work / "source.json").write_text(json.dumps(src), encoding="utf-8")
    empty = {n: BOM for n in batches.base if n != "Members.txt"}
    for label, members in (("DB1", batches.mem_r1), ("DB2", batches.base["Members.txt"])):
        restore(root, pre_files)
        code, v, rec = N.night(label, "--runner", export={**empty, "Members.txt": members},
                               views=work, run_id="920", build=real if label == "DB1" else "stub")
        df = v.get("day_files") or {}
        if label == "DB1":
            leg = (root / "legislators.txt").read_bytes()
            new_rows = [ln for ln in lines((root / "Docket.txt").read_bytes())
                        if ln.startswith("2027|")]
            note(df.get("source") == "database" and b"Newmember0" in leg and not new_rows,
                 "DB1: the database night installs the new roster tonight's Members.txt names, "
                 "and leaves 2027's rows out", (df.get("source"), df.get("why"), df.get("stops")))
            note(any("New term" in w for w in v.get("warnings") or []),
                 "DB1: its page says a newer session year is a New term run's to take",
                 v.get("warnings"))
            if real == "real" and pre is not None:
                note(v.get("built"), "DB1: built in full", v.get("not_clean"))
                RESULTS.setdefault("db1_verdict", {"publishable": v.get("publishable"),
                                                   "gates": v.get("gates"),
                                                   "not_clean": v.get("not_clean")})
                # The views are another day's than the export installed: the
                # bills whose docket rows they hold otherwise are set apart.
                apart = docket_days_apart(pre_files["Docket.txt"],
                                          (root / "Docket.txt").read_bytes())
                RESULTS["db1_other_day"] = sorted(apart)
                print(f"    the database's docket holds {len(apart)} of {TERM}'s bills otherwise "
                      "than the export installed: another day's", flush=True)
                compare_term(root, pre, "DB1", finished=False, other_day=apart)
        else:
            note(df.get("source") != "database" and any("roster" in s or "legislators.txt" in s
                                                        for s in df.get("stops") or []),
                 "DB2: with the old Members.txt the roster guard stops it", df.get("stops"))


def level(root, batches, var, pre, logs):
    """Variant C or D installed after the switch: build_data and narrative on
    it, into a scratch folder. 2025-2026 whole, the stragglers counted."""
    saved = installed_state(root)
    restore(root, batches.variant(var))
    out = logs / f"level_{var}"
    shutil.rmtree(out, ignore_errors=True)
    rc1, _, said1 = sh(["build_data.py", "--dir", ".", "--out", str(out), "--frozen-terms"], root)
    rc2, _, said2 = sh(["build_data.py", "--dir", ".", "--out", str(out)], root)
    (logs / f"level_{var}.log").write_text(said1 + "\n\n" + said2, encoding="utf-8")
    bills = json.loads((out / "bills.json").read_text(encoding="utf-8")) if rc2 == 0 else {}
    sp = json.loads((out / "sponsors.json").read_text(encoding="utf-8")) if rc2 == 0 else {}
    was_b = json.loads((pre / "bills.json").read_text(encoding="utf-8"))[TERM] \
        if (pre / "bills.json").exists() else None
    now = bills.get(TERM) or {}
    note(rc1 == 0 and rc2 == 0, f"{var}-level: build_data runs on variant {var} after the switch")
    if was_b is not None:
        same = sum(1 for b, r in was_b.items()
                   if {k: x for k, x in (now.get(b) or {}).items() if k != "archived"} == r)
        note(same == len(was_b) == len(now), f"{var}-level: {TERM} whole, {same:,} of {len(was_b):,} records equal")
    if var == "S":
        # Only the sponsor files name 2027: the build reads the session's
        # term from the guard's six files, so 2025-2026 is finished and its
        # freeze's, and no 2027 sponsor is filed on a 2025-2026 bill.
        was_s = json.loads((pre / "sponsors.json").read_text(encoding="utf-8"))[TERM]
        note(sp.get(TERM) == was_s, f"S-level: {TERM}'s sponsors are its freeze's, every list, "
                                    "with only the sponsor files naming 2027")
        note("left out" in said2, "S-level: the session's 2025-2026 rows are counted and left out",
             [ln for ln in said2.splitlines() if "left out" in ln][:2])
        restore(root, saved)
        return
    want = {f.split("|")[3] for f in batches.batch}
    note(want <= set(bills.get(NEW) or {}), f"{var}-level: the 2027 batch is there "
                                            f"({len(bills.get(NEW) or {})} measures)")
    note(not [b for b in (sp.get(NEW) or {}) if b not in (bills.get(NEW) or {})],
         f"{var}-level: no 2026 sponsor filed under {NEW}")
    if var == "C":
        note("left out" in said2 and "2025-2026" in said2,
             "C-level: the ten 2026 rows are counted and said, not merged",
             [ln for ln in said2.splitlines() if "left out" in ln][:3])
        # narrative.py on the session docket keeps its hands off 2025-2026.
        nar = logs / "level_C_narratives.json"
        shutil.copy2(root / "narratives.json", nar)
        rc, _, said = sh(["narrative.py", "--docket", "Docket.txt", "--all", "--out", str(nar),
                          "--members", str(out / "legislators.json"), "--bills", str(out / "bills.json")],
                         root)
        n = json.loads(nar.read_text(encoding="utf-8"))
        before = json.loads((root / "narratives.json").read_text(encoding="utf-8"))
        note(rc == 0 and n.get(TERM) == before.get(TERM),
             "C-level: narrative.py on a docket with 2026 stragglers leaves 2025-2026's histories as they were",
             [ln for ln in said.splitlines() if "left out" in ln][:2])
        nar.unlink()
    restore(root, saved)


if __name__ == "__main__":
    sys.exit(main())
