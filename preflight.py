#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.104
"""
Run every check that needs no network, and report all of them at once.

    python3 preflight.py            # everything
    python3 preflight.py --code     # logic only, ignore the data on disk
    python3 preflight.py --verbose  # show what each check actually produced

The failure this exists to prevent: twelve files change, the first one raises on
line 3, and an hour goes into that one traceback while the other eleven stay
unknown. Nothing here stops at the first failure. Every check is independent,
catches its own exceptions, and reports. What you get is a list of what is
broken, not the first thing that broke.

This is the companion to inventory.py, not a replacement. That answers "am I
running the copy you gave me". This answers "does the copy I am running work".
Run inventory first; a failure here on a stale file is not worth debugging.

WHAT IT DOES NOT DO

No network, no YouTube, no gencourt. It never runs a build and never writes
anything into the project: the marker checks build a throwaway tree under the
system temp directory and delete it. Running this cannot change the site and
cannot lose anything.

TWO HALVES

CODE checks call the changed functions with fixed inputs and known answers.
They run anywhere, need no data, and prove the logic works on your Python
before it meets 2,234 bills.

DATA checks run only when the real files are present, and are read-only. They
answer the questions the code cannot: what shape former_members.json really is,
what the manifest's venue values look like, how many docket rows the proceeding
parser drops on the floor.
"""

import argparse
import ast
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections import Counter
from pathlib import Path

import child

CHECKS = []


def _run(cmd, **kw):
    """subprocess.run, with the child's output read as UTF-8.

    The reason is in child.py, which now holds this for the whole repository:
    seven reads died here on 10 September under a line that said 77 passed,
    and eight hours later the same defect took the pipeline down at step 3 of
    21. This stays as a name because every check below calls it.
    """
    return child.run(cmd, **kw)


def check(group, name, needs=()):
    """Register a check. `needs` names modules that must import for it to run."""
    def deco(fn):
        CHECKS.append({"group": group, "name": name, "fn": fn, "needs": needs})
        return fn
    return deco


def imp(name):
    """Import a project module, or None. Import errors are a finding, not a crash."""
    try:
        return __import__(name)
    except Exception:
        return None


# =========================================================== code: the files ==

@check("status", "an archived page says what its own term actually has")
def _archived_coverage():
    """One paragraph described 1989 and 2023 identically, on 31,449 pages.

    It was gated on a single boolean, and it was wrong in both directions: it
    understated the terms that now have full dockets, and it asserted for
    fifteen terms that "the recorded votes come from the General Court's
    database" when named roll calls exist for two.

    d.archived is the term's coverage object now. It stays truthy so nothing
    that merely tests it had to change -- which is convenient and is exactly
    why this check exists. A build that reverted to `True` would render the
    old single paragraph again on every archived page and pass every other
    check in this file, because a bare True is a perfectly good truthy value.

    Checked on the built site rather than on a fixture: the fixture has one
    term and this is a claim about eighteen.
    """
    site = Path("site")
    if not (site / "bill").is_dir():
        return "skip", "no built site here"
    try:
        import site_read as SR
    except ImportError:
        return "skip", "site_read.py will not import"
    KEYS = {"docket", "sponsors", "reports", "votes", "video", "committee"}
    bare, objects, terms = 0, 0, {}
    seen = 0
    for year, bid, rec in SR.records(site):
        a = rec.get("archived")
        if a is None:
            continue
        seen += 1
        if a is True:
            bare += 1
        elif isinstance(a, dict):
            objects += 1
            terms.setdefault(year, {k for k in a if a.get(k)})
            assert set(a) <= KEYS, (
                f"/bill/{year}/{bid} has an archived key this does not know: "
                + ", ".join(sorted(set(a) - KEYS)))
    if not seen:
        return "skip", "no archived pages in the built site"
    assert not bare, (
        f"{bare:,} archived pages of {seen:,} carry `archived: true` rather "
        "than their term's coverage. A bare true is truthy, so the page "
        "renders the old one-size paragraph and nothing else complains. "
        "Rebuild with the current build_site_v2.")
    # Coverage only ever grows as fetches land, so a term that has a docket
    # and no committee is a sign the flags were computed from the wrong slice.
    odd = [y for y, ks in terms.items() if "docket" in ks and "committee" not in ks]
    assert not odd, ("these years claim a docket but no committee, which no "
                     "real term does: " + ", ".join(sorted(odd)))
    return "ok", (f"{objects:,} archived pages across {len(terms)} years, each "
                  "carrying its own term's coverage")


@check("status", "an upcoming hearing names a bill, not a key")
def _upcoming_shape():
    """home.json's upcoming list, built on a fixture and read back.

    procs is keyed (term, bill) because a bill number names one bill in each
    biennium. One loop still read it as though the key were the bill alone and
    put the whole tuple in the field, so home.json carried

        "bill": ["2025-2026", "HB1648"]

    and build_feeds.py died on (bill or "").upper().

    It survived for as long as it did because "upcoming" is empty on any day
    with no hearing in the next fortnight, which was every day for weeks --
    and every fixture date here was fixed and in the past, so preflight never
    ran that code either. The fixture now carries one hearing three days out,
    dated from the clock, so this runs whenever preflight does.
    """
    import shutil, subprocess, sys, tempfile
    here = Path(".").resolve()
    need = ["build_site_v2.py", "proceedings.py", "build_proceedings.py"]
    absent = [x for x in need if not (here / x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-upcoming-"))
    try:
        _site_fixture(root)
        # EVERY module, not a guessed list. build_site_v2 imports a dozen
        # of this project's own files and naming them here means the check
        # breaks whenever one is added -- and it breaks as "wrote no
        # home.json", which reads like the thing under test failing rather
        # than the fixture being short a file. Copying them all costs
        # milliseconds.
        for f in [x.name for x in here.glob("*.py")]:
            if (here / f).exists():
                shutil.copy(here / f, root / f)
        r = _run(
            [sys.executable, "build_site_v2.py", "--data", "data",
             "--out", "site", "--segments", "work"],
            cwd=root, capture_output=True, text=True, timeout=300)
        hp = root / "site" / "home.json"
        assert hp.exists(), ("build_site_v2 wrote no home.json on the "
                             "fixture: " + (r.stderr or r.stdout or "")[-200:])
        home = json.loads(hp.read_text(encoding="utf-8"))
        up = home.get("upcoming") or []
        assert up, ("the fixture holds a hearing three days from now and "
                    "home.json lists no upcoming item. Either the window "
                    "moved or the loop that fills it stopped running, and "
                    "while it is empty nothing checks its shape.")
        bad = [u for u in up if not isinstance(u.get("bill"), str)
               or not u["bill"].strip()]
        assert not bad, (f"{len(bad)} of {len(up)} upcoming items do not "
                         "name a bill as a string: "
                         + json.dumps(bad[0])[:140])
        return "ok", (f"{len(up)} upcoming on the fixture, each naming a bill "
                      "as a string -- the shape build_feeds.py needs")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("files", "one contact address, and it is the working one")
def _one_address():
    """Thirty occurrences across twenty-seven files, and they must agree.

    The address is published to readers on every page and, more importantly,
    sent to the General Court in the User-Agent of every fetch script. Those
    are the people who have blocked this address twice; if they ever want to
    say why, the address in their logs is how they would do it, and for a
    while it was one that does not receive mail.

    Thirty copies is the real defect and a constant would be better, but the
    copies are inside User-Agent strings in twenty scripts and inside HTML in
    three more, and threading an import through all of them to save a
    find-and-replace is not obviously the better trade. What is not
    acceptable is the copies silently disagreeing, so this is the guard: one
    address at graniterecord.org, everywhere, and it is the one that works.
    """
    import re
    import subprocess
    CORRECT = "contact@graniterecord.org"
    try:
        out = _run(["git", "ls-files"], capture_output=True,
                             text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return "skip", f"git would not list the tracked files ({e})"
    if out.returncode != 0:
        return "skip", "not a git repository"
    rx = re.compile(r"[A-Za-z0-9._%+-]+@graniterecord\.org")
    found, wrong = 0, {}
    for n in out.stdout.splitlines():
        f = Path(n)
        if not n.strip() or not f.exists() or f.stat().st_size > 4_000_000:
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in rx.finditer(body):
            found += 1
            if m.group(0) != CORRECT:
                line = body[:m.start()].count(chr(10)) + 1
                wrong.setdefault(m.group(0), []).append(f"{n}:{line}")
    assert not wrong, (
        "an address at graniterecord.org that is not " + CORRECT + ": "
        + "; ".join(f"{a} at {', '.join(v[:3])}" for a, v in wrong.items()))
    return "ok", (f"{found} occurrences of {CORRECT} across the tracked "
                  "files, and no other address at that domain")


@check("files", "no tracked file carries a credential")
def _no_secrets():
    """What git would publish, checked before git publishes it.

    This repository is meant to be shared. A key committed once is in the
    history forever, and rewriting published history is not a thing anybody
    does calmly at the moment they notice. secrets.json is gitignored and
    keys.py reads it; this is what makes that arrangement true rather than
    merely intended.

    The General Court's database host, user and password are deliberately NOT
    matched here. They are published at gc.nh.gov/downloads in "ODBC and Data
    Table Structure.pdf" for public use against a read-only account, they are
    documented as such in probe_db.py, and hiding a published credential would
    protect nothing while stopping somebody reproducing this work.
    """
    import subprocess
    try:
        out = _run(["git", "ls-files"], capture_output=True,
                             text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return "skip", f"git would not list the tracked files ({e})"
    if out.returncode != 0:
        return "skip", "not a git repository"
    names = [n for n in out.stdout.splitlines() if n.strip()]
    if not names:
        return "skip", "git tracks nothing here"

    # Shapes that are a credential and nothing else. Deliberately narrow: a
    # pattern loose enough to catch "password = " would fire on prose and on
    # probe_db.py, and a check that cries wolf gets silenced.
    import re
    SHAPES = [
        ("a Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
        ("an OpenAI key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
        ("a GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
        ("a Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
        ("an AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("a private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
        ("a Cloudflare token", re.compile(r"CLOUDFLARE_API_TOKEN\s*[:=]\s*"
                                          r"[\"\']?[A-Za-z0-9_\-]{20,}")),
    ]
    found = []
    for n in names:
        f = Path(n)
        if not f.exists() or f.stat().st_size > 4_000_000:
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for what, rx in SHAPES:
            m = rx.search(body)
            if m:
                line = body[:m.start()].count(chr(10)) + 1
                found.append(f"{n}:{line} looks like {what}")
    # A check signals failure by raising, which the runner turns into FAIL.
    # Returning "fail" is not a status it knows and crashed it on a KeyError
    # the first time one of these actually tripped.
    assert not found, (f"{len(found)} tracked file(s) carry something shaped "
                       "like a credential, and this repository is meant to be "
                       "shared: " + "; ".join(found[:4]))
    return "ok", (f"{len(names)} tracked files, none carrying a key. "
                  "secrets.json is gitignored; probe_db.py's published "
                  "credentials are public by design.")


@check("files", "every listed script parses")
def _parse_all():
    vp = Path("versions.json")
    if not vp.exists():
        return "skip", "no versions.json here"
    names = [n for n in json.loads(vp.read_text(encoding="utf-8"))["files"]
             if n.endswith(".py")]
    bad = []
    for n in names:
        p = Path(n)
        if not p.exists():
            continue
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError as e:
            bad.append(f"{n}:{e.lineno} {e.msg}")
    present = sum(1 for n in names if Path(n).exists())
    assert not bad, "; ".join(bad)
    return "ok", f"{present} of {len(names)} present, all parse"


@check("files", "changed modules import")
def _import_all():
    mods = ["narrative", "build_site_v2", "build_feeds", "floor_markers",
            "apply_markers", "inventory", "build_all", "rollcall_parser"]
    bad = []
    for m in mods:
        if not Path(m + ".py").exists():
            continue
        if imp(m) is None:
            bad.append(m + ": " + traceback.format_exc(limit=0).strip()
                       .splitlines()[-1][:70])
    assert not bad, "; ".join(bad)
    return "ok", f"{len([m for m in mods if Path(m + '.py').exists()])} imported"


# ============================================================ code: narrative ==

# Real lines, taken from bills on the live site.
DOCKET_LINES = [
    ("veto_override",
     "Veto Sustained 08/19/2026: RC 152-167 Lacking Necessary Two-Thirds Vote"),
    ("veto_override",
     "Notwithstanding the Governor's Veto, Shall SB 434 Become Law: RC 16Y-8N, "
     "Veto Overridden by necessary two-thirds vote; 08/19/2026"),
    ("unsigned_law",
     "Law Without Signature 08/19/2026; Chapter 344; Effective 08/19/2026; "
     "Art 44, Pt II, NH Constitution"),
    ("unsigned_law",
     "Enacted in accordance with Article 44 PartII of the N.H. Constitution "
     "without the signature of the governor. Chapter 343;I. sec 4 eff 12/1/26"),
    ("interim_report",
     "Interim Study Report: Not Recommended for Future Legislation 06/02/2026 "
     "(Vote 14-0; RC)"),
    ("floor", "Ought to Pass: MA VV 03/06/2026"),
    ("governor", "Vetoed by Governor 07/15/2026"),
    ("amendment", "Amendment # 2026-0503h: AA VV 03/06/2026"),
    ("report", "Committee Report: Ought to Pass with Amendment # 2026-0503h "
               "(Vote 10-0; CC)"),
]


@check("narrative", "the mover is split off a floor action, both chambers' ways",
       needs=("narrative",))
def _split_mover(narrative):
    """The House writes the mover last in parentheses; the Senate writes it
    first with the verb folded in. Before split_mover the Senate name stayed
    inside the motion, so a voice vote was headed "Sen. Abbas Moved Laid on
    Table" as if that were the question put."""
    s = narrative.split_mover
    assert s("Lay on Table (Rep. K. Rice)") == ("Lay on Table", "Rep. K. Rice")
    assert s("Sen. Abbas Moved Laid on Table") == ("Laid on Table", "Sen. Abbas")
    assert s("Sen. Fuller Clark Moved to Concur with the House Amendment") == \
        ("Concur with the House Amendment", "Sen. Fuller Clark")
    assert s("Sen. Innis Accedes to House Request for Committee of Conference") == \
        ("Accedes to House Request for Committee of Conference", "Sen. Innis")
    assert s("Sen. Birdsell moved to call the question") == \
        ("call the question", "Sen. Birdsell")
    assert s("Ought to Pass") == ("Ought to Pass", "")
    return "ok", "House parenthetical and Senate leading name both split"


@check("narrative", "real docket lines classify correctly", needs=("narrative",))
def _classify(narrative):
    wrong = []
    for want, line in DOCKET_LINES:
        got = narrative.classify(line)["_type"]
        if got != want:
            wrong.append(f"{want}->{got}: {line[:44]}")
    assert not wrong, "; ".join(wrong)
    return "ok", f"{len(DOCKET_LINES)} lines, every type as expected"


@check("narrative", "amendments stage by what the line says", needs=("narrative",))
def _amend_stage(narrative):
    cases = [("Amendment # 2026-0503h: AA VV 03/06/2026", "floor"),
             ("Committee Amendment # 2026-0777h, AA, VV; 03/06/2026", "committee"),
             ("Enrolled Bill Amendment # 2026-2001e Adopted, VV, "
              "(In recess 06/26/2026)", "governor")]
    wrong = []
    for line, want in cases:
        ev = narrative.classify(line)
        ev["body"] = "H"
        got = narrative.stage_of(ev)[1]
        if got != want:
            wrong.append(f"{line[:26]}... -> {got}, wanted {want}")
    assert not wrong, "; ".join(wrong)
    return "ok", "bare->floor, committee->committee, enrolled->governor"


@check("narrative", "veto and enactment sentences render", needs=("narrative",))
def _veto_sentences(narrative):
    out = []
    for line, body in ((DOCKET_LINES[0][1], "H"), (DOCKET_LINES[1][1], "S"),
                       (DOCKET_LINES[2][1], "H"), (DOCKET_LINES[4][1], "H")):
        s = narrative.describe(narrative.classify(line), body)
        assert s, f"no sentence for {line[:40]}"
        out.append(s)
    assert "sustained" in out[0], "House veto line lost its outcome"
    assert "override the governor" in out[1], "Senate override line lost its outcome"
    assert "without the governor" in out[2], "unsigned law line lost its meaning"
    return "ok", out[1][:66] + "..."


@check("narrative", "motion movers expand, but only when unambiguous",
       needs=("narrative",))
def _movers(narrative):
    roster = [{"name": "Germana, Nicholas", "chamber": "H"},
              {"name": "Osborne, Jason", "chamber": "H"},
              {"name": "Osborne, Marjorie", "chamber": "H"},
              {"name": "Altschiller, Debra", "chamber": "S"}]
    tmp = Path(tempfile.mkdtemp()) / "roster.json"
    tmp.write_text(json.dumps(roster), encoding="utf-8")
    keep = narrative.MEMBERS
    try:
        narrative.MEMBERS = narrative.load_members(tmp)
        got = [narrative.expand_mover(x) for x in
               ("Rep. N. Germana", "Sen. D. Altschiller", "Rep. Osborne")]
        assert got[0] == "Rep. Nicholas Germana", got[0]
        assert got[1] == "Sen. Debra Altschiller", got[1]
        assert got[2] == "Rep. Osborne", f"two Osbornes, picked one: {got[2]}"
        narrative.MEMBERS = {}
        assert narrative.expand_mover("Rep. N. Germana") == "Rep. N. Germana"
    finally:
        narrative.MEMBERS = keep
        shutil.rmtree(tmp.parent, ignore_errors=True)
    return "ok", "expanded 2, left the shared surname alone, no roster is a no-op"


# =============================================================== code: status ==

def _narr(lines, body="H"):
    return {"events": [{"raw": x, "type": "other", "date": "2026-08-19",
                        "body": body} for x in lines]}


@check("status", "a sustained veto beats an overridden one", needs=("build_site_v2",))
def _veto_status(build_site_v2):
    B = build_site_v2
    both = _narr(["Vetoed by Governor 07/15/2026",
                  "Veto Sustained 08/19/2026: RC 165-140 Lacking Necessary "
                  "Two-Thirds Vote",
                  "Notwithstanding the Governor's Veto, Shall SB 434 Become "
                  "Law: RC 16Y-8N, Veto Overridden by necessary two-thirds "
                  "vote; 08/19/2026"])
    kind, label = B.classify(both, [])
    assert kind == "veto", f"SB 434 shape came out as {kind}/{label}"
    step = B.next_step(both, {})
    assert "dead" in step.lower(), step
    return "ok", f"{label} / {step}"


@check("status", "law without a signature reads as law", needs=("build_site_v2",))
def _unsigned_status(build_site_v2):
    n = _narr(["Enacted in accordance with Article 44 PartII of the N.H. "
               "Constitution without the signature of the governor. Chapter 343"])
    kind, label = build_site_v2.classify(n, [])
    assert kind == "law", f"came out as {kind}/{label}"
    return "ok", f"{label} / {build_site_v2.next_step(n, {})}"


# =============================================================== code: naming ==

@check("naming", "members are named the same way everywhere",
       needs=("build_site_v2",))
def _naming(build_site_v2):
    m = build_site_v2.member_labels
    cases = [
        (dict(chamber="H", party="R", district="13", county="Rockingham"),
         "Nelson, Jodi", "Rep. Jodi Nelson (R)", "Rep. Jodi Nelson (R - Rock 13)"),
        (dict(chamber="S", party="D", district="24"),
         "Altschiller, Debra", "Sen. Debra Altschiller (D)",
         "Sen. Debra Altschiller (D - SD24)"),
        (dict(chamber="H", party="R", district="13", county="Rockingham"),
         "Rep. Jodi Nelson (R)", "Rep. Jodi Nelson (R)",
         "Rep. Jodi Nelson (R - Rock 13)"),
        # build_data's composite label keeps its own punctuation; what the
        # site draws does not. The abbreviation lost its trailing point so
        # that a member named from the roster and one named from
        # former_members.json read alike -- the difference used to track
        # exactly who had left office.
        (dict(chamber="H", party="R", district="13", county="Rockingham"),
         "Nelson, Jodi(R) Rock 13", "Rep. Jodi Nelson (R)",
         "Rep. Jodi Nelson (R - Rock 13)"),
        (dict(chamber="H", district="7", county="Merrimack"),
         "Doe, Pat", "Rep. Pat Doe", "Rep. Pat Doe (Merr 7)"),
        (dict(chamber="H", party="R"),
         "Doe, Pat", "Rep. Pat Doe (R)", "Rep. Pat Doe (R)"),
    ]
    wrong = []
    for kw, name, want_short, want_full in cases:
        lab = m(name, **kw)
        if lab["display"] != want_short or lab["display_full"] != want_full:
            wrong.append(f"{name!r} -> {lab['display']} / {lab['display_full']}")
    assert not wrong, "; ".join(wrong)
    assert m("Nelson, Jodi", chamber="H")["sort"] == "nelson, jodi"
    return "ok", "6 shapes including the composite label and the missing party"


@check("naming", "an unnamed member is not dressed up as a person",
       needs=("build_site_v2",))
def _placeholder(build_site_v2):
    lab = build_site_v2.member_labels("Member #377204", chamber="H", party="R")
    assert lab["display"] == "Member #377204", lab["display"]
    return "ok", "no honorific, no party letter"


# ========================================================== code: roll calls ==

SUMMARY_LINE = ("2026|H|123|03/06/2026 11:12:09 AM|HB1442|197|151|24|23|0|0|"
                "Ought to Pass|relative to something\n")


@check("rollcalls", "yeas and nays come from fields 5 and 6",
       needs=("rollcall_parser",))
def _cols(rollcall_parser):
    d = Path(tempfile.mkdtemp())
    try:
        f = d / "RollCallSummary.txt"
        f.write_text(SUMMARY_LINE, encoding="utf-8")
        rows = rollcall_parser.parse(f)
        assert rows, "the canonical parser read nothing from a well-formed line"
        r = rows[0]
        assert (r["yeas"], r["nays"]) == (197, 151), (r["yeas"], r["nays"])
        return "ok", f"{r['bill']} {r['yeas']}-{r['nays']}, fields 7/8 are the "
        f"{r['not_voting']} who did not vote"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check("rollcalls", "a vote on a House rule is not filed as a bill",
       needs=("rollcall_parser",))
def _rule_vote_not_a_bill(rollcall_parser):
    """The House amended its own Rule 64 twice on 8 January 2025.

    Both votes are filed in RollCallSummary.txt under "HRULE64", which passes
    for a bill number if the test is letters-then-digits, and gave the site a
    bill that does not exist and no page could ever show. A vote about the
    chamber's own rules is procedural, which is a category this already has.
    """
    d = Path(tempfile.mkdtemp())
    try:
        f = d / "RollCallSummary.txt"
        f.write_text("\n".join([
            "2025|H|1|1/8/2025 10:00:00 AM|HRULE64|216|164|10|10|||"
            "Amend H Rule 64|relating to the rules of the House",
            "2025|H|2|1/8/2025 11:00:00 AM|HB56|216|154|20|8|||"
            "Inexpedient to Legislate|relative to something",
        ]) + "\n", encoding="utf-8")
        rows = {r["bill"]: r for r in rollcall_parser.parse(f)}
        assert "HRULE64" in rows, "the rule vote was dropped, not reclassified"
        assert rows["HRULE64"]["procedural"], (
            "a vote to amend a House rule is filed as a vote on a bill")
        assert not rows["HB56"]["procedural"], (
            "a real bill's vote was swept up as procedural")
        return "ok", "the rule vote is procedural and the bill's is not"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check("rollcalls", "floor_markers matches a spoken tally to the record")
def _tally_match():
    if not Path("floor_markers.py").exists():
        return "skip", "floor_markers.py not here"
    d = Path(tempfile.mkdtemp())
    try:
        (d / "RollCallSummary.txt").write_text(SUMMARY_LINE, encoding="utf-8")
        lines = ["0:00:01 good morning the house will come to order"]
        t = 60
        lines.append(f"0:0{t // 60}:00 Majority of the Committee on Finance to "
                     "which was referred House Bill 1442, relative to something")
        lines.append("0:02:00 debate on the measure continues")
        lines.append("0:03:00 197 in the affirmative, 151 in the negative")
        lines.append("0:03:30 the committee report is adopted")
        (d / "t.txt").write_text("\n".join(lines), encoding="utf-8")
        r = _run([sys.executable, "floor_markers.py",
                            "--transcript", str(d / "t.txt"),
                            "--summary", str(d / "RollCallSummary.txt")],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-160:]
        line = next((l for l in r.stdout.splitlines()
                     if "tallies matched" in l), "")
        assert line, "no tally line in the output at all"
        n = int(line.split(":")[1].strip().split()[0])
        assert n >= 1, (line + "  <- reading the wrong columns would give 0 here")
        return "ok", line.strip()
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ============================================================== code: markers ==

def _fixture(root):
    """A throwaway work tree: one House-style video, one Senate-style."""
    (root / "work" / "PFHOUSE").mkdir(parents=True)
    (root / "work" / "PFSENATE").mkdir(parents=True)

    def caps(lines, secs=6.0):
        out, t = [], 0.0
        for txt in lines:
            out.append({"start": round(t, 1), "end": round(t + secs, 1), "text": txt})
            t += secs
        return out

    h = ["good morning the committee will come to order"] + \
        ["housekeeping"] * 10 + \
        ["we are going to open the public hearing for House Bill 1082 enabling "
         "municipalities"] + ["testimony on HB 1082"] * 20 + \
        ["I'm closing the public hearing for HP 1082 and turning over the gavel"] + \
        ["a pause"] * 5
    (root / "work" / "PFHOUSE" / "transcript.json").write_text(
        json.dumps(caps(h)), encoding="utf-8")
    (root / "work" / "PFHOUSE" / "segments.json").write_text(json.dumps([
        {"bill": "HB1082", "kind": "public hearing", "located": True,
         "why_not": "", "short": False, "tolerance": 300, "dp_start": 0,
         "dp_end": 900, "start": 150.0, "end": 330.0, "mentions_inside": 4,
         "mentions_total": 6, "purity": 0.6}]), encoding="utf-8")

    # Two bills: the first has a loose opening the chair announced, the second
    # has none at all. That second one is the case worth testing, because it is
    # the common Senate shape -- a stated close and an inferred start.
    s = ["senate judiciary will come to order"] + ["introductions"] * 10 + \
        ["Senate Judiciary is now hearing House Bill 1637"] + \
        ["testimony regarding 1637"] * 18 + \
        ["Does anyone else wish to testify on 1637? Seeing no one, that'll end "
         "the hearing"] + \
        ["we will take up the next matter"] + ["testimony about 1416"] * 12 + \
        ["Does anyone else wish to testify on 1416? Seeing none, that will "
         "close the hearing"]
    (root / "work" / "PFSENATE" / "transcript.json").write_text(
        json.dumps(caps(s)), encoding="utf-8")
    (root / "work" / "PFSENATE" / "segments.json").write_text(json.dumps([
        {"bill": "HB1637", "kind": "hearing", "located": True, "why_not": "",
         "short": False, "tolerance": 900, "dp_start": 0, "dp_end": 300,
         "start": 120.0, "end": 260.0, "mentions_inside": 3,
         "mentions_total": 5, "purity": 0.5},
        {"bill": "HB1416", "kind": "hearing", "located": True, "why_not": "",
         "short": False, "tolerance": 900, "dp_start": 300, "dp_end": 600,
         "start": 320.0, "end": 500.0, "mentions_inside": 2,
         "mentions_total": 3, "purity": 0.4}]), encoding="utf-8")

    rows = [{"bill": "HB1082", "video_id": "PFHOUSE", "proceeding": "public hearing",
             "sched_date": "2026-02-03", "sched_time": "10:00",
             "committee": "Election Law", "venue": "LOB 306", "body": "H"},
            {"bill": "HB1637", "video_id": "PFSENATE", "proceeding": "hearing",
             "sched_date": "2026-04-01", "sched_time": "09:00",
             "committee": "Judiciary", "venue": "SH 100", "body": "S"},
            {"bill": "HB1416", "video_id": "PFSENATE", "proceeding": "hearing",
             "sched_date": "2026-04-01", "sched_time": "10:15",
             "committee": "Judiciary", "venue": "SH 100", "body": "S"}]
    with open(root / "manifest.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _run_markers(root, *flags):
    return _run(
        [sys.executable, "apply_markers.py", "--workdir", str(root / "work"),
         "--manifest", str(root / "manifest.csv"), *flags],
        capture_output=True, text=True, timeout=180)


@check("markers", "a whisper transcript is read, not counted as silence",
       needs=("segment_markers",))
def _whisper_transcript(segment_markers):
    """Every whisper-transcribed recording read as zero words.

    read_words parsed only YouTube's json3 {"events": [...]} shape.
    transcribe_and_align writes whisper's output as a LIST of
    {"start","end","text"}, so those folders returned nothing and were counted
    under "no captions" -- silence and failure looking the same again. Twelve
    folders were already dark this way, and the recordings YouTube has no
    captions for can only ever arrive in this shape.
    """
    d = Path(tempfile.mkdtemp())
    try:
        (d / "transcript.json").write_text(json.dumps([
            {"start": 462.8, "end": 465.2,
             "text": "If you would please rise for the pledge"},
            {"start": 610.0, "end": 616.0,
             "text": "we will open the hearing on House Bill 1123"},
        ]), encoding="utf-8")
        w = segment_markers.read_words(d)
        assert w, "a whisper transcript still reads as zero words"
        assert len(w) == 17, f"{len(w)} words, expected 17"
        assert w[0] == (462.8, "If"), w[0]
        # Per LINE, not per word: every word of a sentence carries the
        # sentence's start, which is the honest resolution whisper gives.
        assert w[7][0] == 462.8, w[7]
        assert w[8] == (610.0, "we"), w[8]
        return "ok", f"{len(w)} words off a whisper transcript"
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check("markers", "apply_markers runs and changes nothing without --apply")
def _markers_report():
    if not Path("apply_markers.py").exists():
        return "skip", "apply_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _fixture(root)
        before = (root / "work" / "PFHOUSE" / "segments.json").read_text(encoding="utf-8")
        r = _run_markers(root)
        assert r.returncode == 0, (r.stderr or r.stdout)[-200:]
        assert "stated boundaries found" in r.stdout, r.stdout[-200:]
        after = (root / "work" / "PFHOUSE" / "segments.json").read_text(encoding="utf-8")
        assert before == after, "the report-only run rewrote segments.json"
        n = next(l for l in r.stdout.splitlines() if "stated boundaries found" in l)
        return "ok", n.strip()
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("markers", "--apply patches, keeps a backup, and repeats safely")
def _markers_apply():
    if not Path("apply_markers.py").exists():
        return "skip", "apply_markers.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _fixture(root)
        assert _run_markers(root, "--apply").returncode == 0
        p = root / "work" / "PFHOUSE" / "segments.json"
        first = json.loads(p.read_text(encoding="utf-8"))[0]
        assert (root / "work" / "PFHOUSE" / "segments.pre_markers.json").exists(), \
            "no backup was written"
        assert first.get("start_stated") and first.get("end_stated"), first
        assert first["tolerance"] == 30, first["tolerance"]
        assert _run_markers(root, "--apply").returncode == 0
        second = json.loads(p.read_text(encoding="utf-8"))[0]
        assert (first["start"], first["end"], first["tolerance"]) == \
               (second["start"], second["end"], second["tolerance"]), \
               "a second --apply moved the boundaries"
        sen = json.loads((root / "work" / "PFSENATE" / "segments.json")
                         .read_text(encoding="utf-8"))
        closeonly = next((s for s in sen if s["bill"] == "HB1416"), None)
        assert closeonly, "the second Senate bill went missing"
        assert closeonly.get("end_stated"), "its stated close was not adopted"
        assert not closeonly.get("start_stated"), \
            "an unannounced Senate opening was reported as stated"
        assert closeonly["tolerance"] < 900, \
            "the stated close should narrow the start's tolerance"
        return "ok", ("House both ends stated at +/-30s; Senate close stated, "
                      "start still estimated")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("markers", "verify_batch prints sub-minute bands")
def _verify_bands():
    if not (Path("apply_markers.py").exists() and Path("verify_batch.py").exists()):
        return "skip", "apply_markers.py or verify_batch.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _fixture(root)
        _run_markers(root, "--apply")
        r = _run([sys.executable, "verify_batch.py",
                            "--work", str(root / "work"),
                            "--manifest", str(root / "manifest.csv")],
                           capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout)[-160:]
        assert "sec" in r.stdout, ("no sub-minute band; a 30s tolerance would "
                                   "print as '+/- 0 min'")
        return "ok", next(l.strip() for l in r.stdout.splitlines() if "sec" in l)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ============================================================ code: front end ==

def page_source(name="bills.html"):
    """bills.html together with the app.css and app.js it loads.

    The page was one file with a <style> and a <script> in it. It is three
    files now, so a bill's own page can load the SAME renderer rather than a
    second copy of it. Everything these checks look for -- the palette, the
    station branches, the declaration order -- moved into app.js and app.css
    with it.

    A check that reads only the page now finds nothing to disagree with and
    passes, which is worse than failing, so there is one reader rather than
    three places to remember. Returns ("", None) when the page is not here, so
    a caller can skip rather than assert against nothing.
    """
    p = Path(name)
    if not p.exists():
        p = Path("site") / name
    if not p.exists():
        return "", None
    out = p.read_text(encoding="utf-8")
    for asset in ("app.css", "app.js"):
        f = p.parent / asset
        if f.exists():
            out += "\n" + f.read_text(encoding="utf-8")
    return out, p


@check("frontend", "bills.html carries the changes and its tags balance")
def _bills_html():
    p = Path("bills.html")
    if not p.exists():
        p = Path("site/bills.html")
    if not p.exists():
        return "skip", "bills.html not here or in site/"
    # Most of what this looks for lives in app.js now, which bills.html loads
    # rather than contains. Reading only the page would pass every one of these
    # by finding nothing to disagree with -- so the page is read together with
    # the files it pulls in, and it is an error if those are missing.
    t = p.read_text(encoding="utf-8")
    for asset in ("app.css", "app.js"):
        f = p.parent / asset
        assert f.exists(), (f"bills.html loads {asset} and it is not next to "
                            f"it in {p.parent}/")
        t += "\n" + f.read_text(encoding="utf-8")
    want = {
        "play control is a button": '<button type="button" class="pstub"',
        # A link inside a button is not a link a keyboard or a screen reader
        # can reach, so this one sits outside the card's expand button. What it
        # is called changed once already; anchoring on the tag rather than the
        # wording is what the check is actually about.
        "detail link outside the button": '<a class="detail" href="bill/',
        "page heading": '<h1 class="sr">',
        # The player opens AT the boundary, not before it. The old lead was
        # five minutes for an estimate, which put the reader in the middle of
        # the previous bill and then made the page explain a time that was not
        # the bill's. Two seconds is enough not to clip the first syllable.
        "player opens at the mark": "const LEAD = 2",
        # One word, and only where the placement is an inference rather than
        # something the chair said. The tolerance, which of two dates was being
        # shown, and "about where it ends" were methodology in the way.
        "an inferred start says so": 's.start_stated ? "" : " approximate"',
        "consent bills get no timestamp": 's.state==="consent"',
        "member sort key": "(a.s||a.n||\"\")",
        # A jump button pressed before the player exists must build the
        # player AT that time. Clicking the stub instead builds it at the
        # opening offset -- up to five minutes earlier -- and then posts
        # seekTo into an iframe created a line before, which YouTube is not
        # listening on yet. The video then sits at a different time from the
        # button that was pressed, which is what a reader sees as the player
        # and the printed timestamps disagreeing.
        # Per-bill data is addressed by its filing year, because a bill number
        # is unique within a term and not beyond it. A 2027 HB686 would
        # otherwise overwrite this one's docket, votes and recordings.
        # A record small enough travels inside its own page, so what is
        # fetched is the page and not a JSON file beside it. Still addressed
        # by filing year, for the same reason: a bill number is unique within
        # a term and not beyond it.
        "the record is read from the bill's own page, under its year":
            "DATA(`bill/${yr}/${id.toLowerCase()}`)",
        "a record too large to inline is followed to its own file":
            'meta[name="gr-data"]',
        # /bill/2026/hb1123, which is what a person pastes. The year is the
        # point of the check and it is still there; only the shape changed,
        # from a hash on the search page to the bill's own address.
        "the address carries the year": '`${BASE}bill/${_y}/${id.toLowerCase()}`',
        "a cold jump loads the player at the time asked for":
            "st.dataset.embed=`${vid}|${Math.max(0,Math.floor(Number(t)))}|${p2}`",
        "tab panels": 'role="tabpanel"',
        "visually hidden class": ".sr{position:absolute",
    }
    missing = [k for k, v in want.items() if v not in t]
    assert not missing, "missing: " + ", ".join(missing)
    assert "<h5" not in t, "an <h5> survived the heading pass"
    import re as _re
    bad = []
    for tag in ("div", "button", "article", "main", "p", "span"):
        o = len(_re.findall(rf"<{tag}[\s>]", t))
        c = len(_re.findall(rf"</{tag}>", t))
        if o != c:
            bad.append(f"{tag} {o}/{c}")
    assert not bad, "unbalanced: " + ", ".join(bad)
    if t.count("`") % 2:
        raise AssertionError("odd number of backticks; a template literal is open")
    extra = ""
    if shutil.which("node"):
        js = "\n".join(_re.findall(r"<script>(.*?)</script>", t, _re.S))
        f = Path(tempfile.mkdtemp()) / "b.js"
        f.write_text(js, encoding="utf-8")
        r = _run(["node", "--check", str(f)], capture_output=True, text=True)
        shutil.rmtree(f.parent, ignore_errors=True)
        assert r.returncode == 0, "node --check: " + r.stderr.strip()[:150]
        extra = ", node --check clean"
    return "ok", f"7 markers present, tags balanced{extra}"


@check("frontend", "a page asks for the script it was built against")
def _asset_version():
    """The four hours in which the site was broken and every file was correct.

    app.js and app.css are served with Cache-Control: max-age=14400; the HTML
    around them is not cached at all. So after a publish a returning visitor
    holds the OLD script and receives the NEW page, and the two disagree in
    whatever way that release changed them.

    On 7 September that was the legislator pages: 406 of them went live setting
    window.GR_MEMBER, four-hour-old app.js had never heard of GR_MEMBER, and
    every one of them quietly drew the bill search instead. The page was right,
    the data was right, the deployed script was right, and the site was broken.

    The URL now carries a hash of the two files, so a changed asset is a
    changed address. This checks the built pages actually ask for the hash the
    files on disk have -- a generator that stops adding it fails here rather
    than four hours after the next deploy.
    """
    site = Path("site")
    if not (site / "bills.html").exists():
        return "skip", "site/bills.html not built"
    sh = imp("shell")
    if not sh:
        return "skip", "shell.py will not import"
    q = sh.asset_query(site)
    assert q, "neither app.js nor app.css is on disk, so no version was computed"

    pages = [site / "bills.html"]
    for folder, pat in (("bill", "*/*.html"), ("legislator", "*.html"),
                        ("committee", "*.html")):
        got = sorted((site / folder).glob(pat))
        if got:
            pages.append(got[len(got) // 2])

    bad = []
    for f in pages:
        t = f.read_text(encoding="utf-8")
        if 'src="app.js' not in t:
            continue
        if f'src="app.js{q}"' not in t:
            got = re.search(r'src="app\.js([^"]*)"', t)
            bad.append(f"{f} asks for app.js{got.group(1) if got else ''} "
                       f"but the files on disk are {q}")
        if 'href="app.css' in t and f'href="app.css{q}"' not in t:
            bad.append(f"{f} asks for an app.css that is not {q}")
    assert not bad, "; ".join(bad[:3])
    return "ok", f"{len(pages)} page kinds, all asking for app.js{q}"


@check("frontend", "every record's own page is a working shell for app.js")
def _bill_shell():
    """What replaced "the bill page stylesheet still formats".

    That check guarded 200 lines of CSS inside build_bill_pages.py, which
    rendered every bill a second time in Python. Both are gone: a bill's page
    is bills.html with one bill open, so the stylesheet it uses is app.css and
    the palette check already covers that.

    What needs guarding now is different and worse if it breaks. app.js binds
    to #q, #qgo, #year, #sort, #facets, #results and #count as it loads, and
    tells the page which bill it is through GR_BILL. Drop any one of those and
    the page is a blank screen that reports nothing -- 4,230 times over, with
    every check passing. build_bill_pages.py asserts them as it builds; this
    asserts them on what was actually written.
    """
    # A bill's, a legislator's and a committee's page are the same shell with
    # a different global set, all three from shell.py. Each is checked, because
    # a generator that stops setting its global produces thousands of pages
    # that load, draw nothing and report nothing.
    kinds = [("site/bill", "*/*.html", "GR_BILL", "/bill/"),
             ("site/legislator", "*.html", "GR_MEMBER", "/legislator/"),
             ("site/committee", "*.html", "GR_COMMITTEE", "/committee/")]
    found, sizes = [], []
    for folder, pat, glob_name, urlbit in kinds:
        pages = sorted(Path(folder).glob(pat))
        if not pages:
            continue
        f = pages[len(pages) // 2]
        t = f.read_text(encoding="utf-8")
        for need in ('id="q"', 'id="qgo"', 'id="year"', 'id="sort"',
                     'id="facets"', 'id="results"', 'id="count"'):
            assert need in t, (
                f"{f} has no {need}, which app.js binds to on load. The page "
                "draws nothing and says nothing about why.")
        # The src carries a content hash now, so match the prefix.
        assert 'src="app.js' in t, f"{f} does not load app.js"
        assert f"window.{glob_name}=" in t, (
            f"{f} never says which record it is, so app.js opens none of them")
        assert '<base href="/">' in t, (
            f"{f} has no <base>, so every relative link app.js writes resolves "
            f"under {folder}/ and 404s")
        assert "<noscript>" in t, (
            f"{f} has no <noscript>: a reader without JavaScript gets a blank "
            "page and no way to the General Court")
        # The three things that make a record findable, and the whole reason
        # these pages exist rather than a fragment on the search page.
        assert "<title>" in t and "| Granite Record</title>" in t, f"{f}: no title"
        assert 'name="description"' in t, f"{f}: no meta description"
        assert 'rel="canonical"' in t, f"{f}: no canonical link"
        sm = Path("site/sitemap.xml")
        assert sm.exists() and urlbit in sm.read_text(encoding="utf-8"), (
            f"sitemap.xml does not list {urlbit} pages")
        found.append(f"{len(pages):,} {urlbit.strip('/')}")
        sizes.append(f.stat().st_size)
    if not found:
        return "skip", "no record pages built yet"
    assert len(found) == 3, (
        "only " + ", ".join(found) + " were built. All three page types come "
        "from shell.py and build_all runs all three, so a missing one is a "
        "step that did not run rather than a page type that does not exist.")
    return "ok", (", ".join(found) + f"; {min(sizes)/1024:.1f}-"
                  f"{max(sizes)/1024:.1f} KB each")


@check("frontend", "one palette, and every pair of it measures up")
def _palette():
    """Contrast, computed from the tokens, not asserted about their spelling.

    WCAG 2.1: 4.5:1 for body text, 3:1 for a control boundary. The audit of
    7 September found eleven pairs below those and this is what stops them
    coming back -- including the five that were the same bug, a secondary grey
    used on tinted status boxes it had never been checked against.

    It also fails if the two stylesheets stop sharing one palette.
    build_pages.py used to carry its own copy, which had drifted: --st-veto
    was #7C2D3A in one file and #8C4A2F in the other.
    """
    def root_of(text):
        i = text.find(":root{")
        if i < 0:
            return {}
        block = text[i:text.index("}", text.index('--sans:', i)) + 1]
        # Keyed WITHOUT the leading "--", because that is how the pairs
        # below name them and a dict keyed the other way silently matches
        # nothing while every assertion still runs.
        return {k[2:]: v for k, v in re.findall(
            r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\s*[;}]", block)}

    def lum(h):
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        ch = []
        for i in (0, 2, 4):
            v = int(h[i:i + 2], 16) / 255
            ch.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]

    def ratio(a, b):
        x, y = sorted((lum(a), lum(b)), reverse=True)
        return (x + 0.05) / (y + 0.05)

    css = Path("app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    tok = root_of(css.read_text(encoding="utf-8"))
    assert tok, "app.css has no :root block this can read"

    built = Path("site/style.css")
    if built.exists():
        other = root_of(built.read_text(encoding="utf-8"))
        drift = [k for k in set(tok) & set(other)
                 if tok[k].lower() != other[k].lower()]
        assert not drift, (
            f"app.css and style.css disagree about {', '.join(sorted(drift))}. "
            "The palette is meant to have one definition; build_pages.py reads "
            "app.css's.")

    TEXT = [("ink", "surface"), ("ink", "paper"),
            ("ink-2", "surface"), ("ink-2", "paper"), ("ink-2", "wash"),
            ("pine", "surface"), ("pine", "paper")]
    for st in ("active", "law", "done", "study", "veto"):
        TEXT += [(f"st-{st}", f"st-{st}-bg"), ("ink-2", f"st-{st}-bg")]
    BOUND = [("edge", "surface"), ("edge", "paper"),
             ("pine", "surface"), ("pine", "paper")]

    bad, n = [], 0
    for pairs, need, kind in ((TEXT, 4.5, "text"), (BOUND, 3.0, "boundary")):
        for fg, bg in pairs:
            if fg not in tok or bg not in tok:
                bad.append(f"--{fg} or --{bg} is not defined")
                continue
            n += 1
            r = ratio(tok[fg], tok[bg])
            if r < need:
                bad.append(f"--{fg} on --{bg} is {r:.2f}:1, {kind} needs {need}")
    assert not bad, "; ".join(bad[:4])
    return "ok", f"{n} pairs, all above their threshold"


# ============================================================= code: pipeline ==

@check("pipeline", "build_all runs the steps in the right order", needs=("build_all",))
def _plan(build_all):
    class A:
        key = None
        session = "2026"
        base = "https://graniterecord.org"
        archive = "nh-archive"
    steps = [s.name for s in build_all.plan(A())]
    def at(frag):
        return next(i for i, n in enumerate(steps) if frag in n)
    assert at("plain-language") > at("build data (second pass)"), \
        "narratives are built before the roster they now need"
    assert at("adopt boundaries") < at("site data"), \
        "markers are applied after the site is built, so nothing would use them"
    assert any("testimony" in n for n in steps), "no testimony step"
    scripts = [s.args[0] for s in build_all.plan(A())]
    missing = [x for x in scripts if not Path(x).exists()]
    assert not missing, "steps reference scripts that are not here: " + \
                        ", ".join(missing)
    return "ok", f"{len(steps)} steps, order correct, every script present"


@check("pipeline", "inventory no longer offers a live file for deletion",
       needs=("inventory",))
def _stale(inventory):
    assert "bill_titles.json" not in inventory.STALE, \
        "build_data.py still reads bill_titles.json"
    return "ok", f"STALE lists {len(inventory.STALE)}, none of them read"


@check("pipeline", "feed titles cut at a word boundary", needs=("build_feeds",))
def _clip(build_feeds):
    s = ("Enacted in accordance with Article 44 PartII of the N.H. Constitution "
         "without the signature of the governor. Chapter 343")
    out = build_feeds.clip(s)
    assert out.endswith("\u2026"), out
    assert not out[:-1].rstrip().endswith(("signatur", "governo")), out
    assert build_feeds.clip("short one") == "short one"
    return "ok", out[-38:]


@check("files", "every file's own stamp matches versions.json")
def _stamps():
    """The stamp is what inventory.py compares, so a stale one is a lie.

    Six files shipped with the right code and last week's stamp, because the
    bump was `t.replace(old, new)` with no assertion: str.replace returns the
    string unchanged when the pattern is absent, so a bump that matched nothing
    printed success and did nothing. The first one failed, and every later bump
    looked for a version the file had never reached, so they all failed after
    it. inventory.py then told the truth -- out of date -- about files whose
    code was current, and the only visible symptom was a re-download that
    changed nothing.
    """
    vp = Path("versions.json")
    if not vp.exists():
        return "skip", "no versions.json here"
    want = json.loads(vp.read_text(encoding="utf-8")).get("files", {})
    bad, unstamped, seen = [], [], 0
    for name, ver in want.items():
        f = Path(name)
        if not f.exists():
            continue
        seen += 1
        m = re.search(r"GRANITE_VERSION:\s*([0-9.\-]+)",
                      f.read_text(encoding="utf-8", errors="replace"))
        if not m:
            unstamped.append(name)
        elif m.group(1) != ver:
            bad.append(f"{name} is stamped {m.group(1)}, listed as {ver}")
    assert not bad, "; ".join(bad[:4]) + (f" (+{len(bad) - 4} more)" if len(bad) > 4 else "")
    assert not unstamped, "no stamp line in: " + ", ".join(unstamped[:5])
    return "ok", f"{seen} files agree with the manifest"


@check("files", "no generator writes the bench's record")
def _bench_untouched():
    """review/checked.jsonl is the second thing on this disk that a person
    made by hand, and it is protected the same way ground_truth.csv is.

    The bench appends and never rewrites a line: a later look at the same item
    is a second judgment rather than a correction of the first. A build_ or
    fetch_ script that opens it for writing is the next loss waiting to
    happen, and this project has lost hand-made measurements twice.

    The bench also stays off the network. It shows unpublished judgments about
    named people, and it binds the loopback address for that reason.
    """
    bad = [f.name for f in
           sorted(Path(".").glob("build_*.py")) + sorted(Path(".").glob("fetch_*.py"))
           if "checked.jsonl" in f.read_text(encoding="utf-8", errors="replace")]
    assert not bad, ("these name the bench's record and must not: "
                     + ", ".join(bad))

    rv = Path("review.py")
    if rv.exists():
        src = rv.read_text(encoding="utf-8", errors="replace")
        # The BIND, not the file: the first version of this check read the
        # whole source and failed on the comment explaining why the bind is
        # what it is.
        binds = re.findall(r"HTTPServer\(\s*\(\s*[\"']([\d.]+)[\"']", src)
        assert binds, "review.py no longer opens an HTTPServer"
        assert all(b.startswith("127.") for b in binds), (
            "review.py binds " + ", ".join(binds)
            + "; it must stay on the loopback address")
    return "ok", "only a person writes it, and it is not on the site"


@check("files", "no generator writes a file a person made by hand")
def _record_untouched():
    """The files nobody can regenerate, and nothing may overwrite.

    The 35 hand-marked times are the only measurement of this system a person
    made, and they were lost twice while they lived as two columns in a file
    that rebuilds overwrite. They live in ground_truth.csv now, which a person
    edits and every generator only reads.

    The list has grown since, and each addition is a file that cost somebody
    an evening and cannot be rebuilt from anything:

      ground_truth.csv        35 proceedings timed with a stopwatch
      review/checked.jsonl    the bench's judgments, append-only
      bill_notes.json         written explanations of bills that recur under
                              one number every term, like the budget
      officials.json          offices filled by hand from four official sources

    Naming only the first one meant the check grew stale as quietly as the
    thing it guards against: three of these four had no guard at all.
    """
    HANDMADE = ["ground_truth.csv", "review/checked.jsonl", "bill_notes.json",
                "officials.json"]
    bad = []
    for f in (sorted(Path(".").glob("build_*.py"))
              + sorted(Path(".").glob("fetch_*.py"))):
        src = f.read_text(encoding="utf-8", errors="replace")
        for name in HANDMADE:
            stem = re.escape(name.split("/")[-1])
            if not re.search(stem, src):
                continue
            # Opened for writing, written through a Path, or through a
            # module-level constant that names it.
            if re.search(r'open\s*\([^)]*' + stem + r'[^)]*["\']w', src) or \
               re.search(stem + r'[^\n]{0,40}write_text', src) or \
               re.search(r'(?:TRUTH|LEDGER|NOTES|OFFICIALS)\s*\.\s*'
                         r'open\s*\(\s*["\']w', src):
                bad.append(f"{f.name} writes {name}")
    assert not bad, "these write a hand-made file: " + "; ".join(bad)
    present = [n for n in HANDMADE if Path(n).exists()]
    return "ok", (f"{len(present)} hand-made file(s) here, and only a person "
                  "writes them: " + ", ".join(present))


@check("markers", "every phrasing read from a transcript still matches")
def _marker_cases():
    """tests/test_markers.py holds the 34 phrasings that were read out of real
    recordings, plus the decoys that look like openings and are not. OPEN_RE
    went through nine revisions in a day collecting them, each checked against
    a fixture that was then thrown away. Running them here is what makes the
    tenth revision safe."""
    import subprocess, sys
    f = Path("tests/test_markers.py")
    if not f.exists():
        return "skip", "tests/test_markers.py not here"
    r = _run([sys.executable, str(f)], capture_output=True, text=True)
    assert r.returncode == 0, (r.stdout or r.stderr).strip()[-300:]
    return "ok", r.stdout.strip().splitlines()[-1][:70]


def _strip_js_comments(js):
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    return "\n".join(re.sub(r"//.*$", "", ln) for ln in js.splitlines())


def _tdz_suspects(js):
    """A const or let read earlier in its function than the line declaring it.

    Legal-looking, syntactically perfect, and fatal: const sits in the temporal
    dead zone until its own line runs, so a read above it throws and takes the
    whole function with it. That is how render() died and the bill list went
    blank on a page that otherwise loaded fine -- node --check passes, the tags
    balance, the site builds, and nothing here executed the script.

    Lines defining a function are skipped: a closure may mention a name
    declared after it, because it runs later.
    """
    js = _strip_js_comments(js)
    out = []
    for fm in re.finditer(r"\bfunction\s+(\w+)\s*\([^)]*\)\s*\{", js):
        name, i = fm.group(1), fm.end()
        depth, j = 1, i
        while j < len(js) and depth:
            depth += (js[j] == "{") - (js[j] == "}")
            j += 1
        lines, d = [], 0
        for ln in js[i:j - 1].splitlines():
            lines.append((d, ln))
            d += ln.count("{") + ln.count("(") - ln.count("}") - ln.count(")")
        decl = {}
        for k, (d, ln) in enumerate(lines):
            m = re.match(r"\s*(?:const|let)\s+(\w+)\s*=", ln) if d == 0 else None
            if m and m.group(1) not in decl:
                decl[m.group(1)] = k
        for var, dk in decl.items():
            for k, (d, ln) in enumerate(lines[:dk]):
                if d == 0 and "=>" not in ln and "function" not in ln \
                        and re.search(rf"\b{re.escape(var)}\b", ln):
                    out.append(f"{name}(): '{var}' read at line {k + 1}, "
                               f"declared at {dk + 1}")
                    break
    return out


@check("frontend", "the page's script loads and render() draws")
def _runs():
    """Actually execute it.

    Everything else about bills.html is read rather than run: the tags balance,
    the syntax parses, the palette is right, the site builds around it. All of
    that was green on a page whose render() threw on its first line and left
    the bill list blank.

    So this loads the script in node against a DOM stub, hands it two bills and
    calls render(). It does not prove the page looks right -- nothing here can
    -- but it proves the code path that draws every bill actually runs.
    """
    f, stub = Path("bills.html"), Path("dom_stub.js")
    if not f.exists():
        f = Path("site/bills.html")
    if not f.exists():
        return "skip", "bills.html not here or in site/"
    if not shutil.which("node"):
        return "skip", "node is not installed"
    if not stub.exists():
        return "skip", "dom_stub.js not here"
    # The script is app.js now. The inline form is still read, so this keeps
    # working against an older checkout of the page.
    ext = f.parent / "app.js"
    js = (ext.read_text(encoding="utf-8") if ext.exists()
          else "\n".join(re.findall(r"<script>(.*?)</script>",
                                    f.read_text(encoding="utf-8"), re.S)))
    assert js.strip(), f"no script in {ext if ext.exists() else f}"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(js, encoding="utf-8")
        (root / "stub.js").write_text(stub.read_text(encoding="utf-8"),
                                      encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const src = require("fs").readFileSync("./page.js", "utf8");
let scope;
try { scope = (0, eval)(src +
    "; ({render, IDX, renderDetail, yearOf, dkey, setTerm:(t)=>{term=t;}, setFocused:(x)=>{focused=x;}, getFocused:()=>focused, getQuery:()=>query});"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message);
            process.exit(1); }
scope.IDX.length = 0;
scope.IDX.push({id:"HB1442",n:"HB 1442",title:"a bill",status:"Passed one chamber",
  kind:"active",committees:["House Finance"],topic:"Insurance",sponsor:"Nelson, Jodi",
  sponsor_label:"Rep. Jodi Nelson (R)",term:"2026",year:"2026",hay:"hb1442"});
try { scope.render(); } catch (e) {
  console.log("RENDER " + e.constructor.name + ": " + e.message); process.exit(1); }
const listHtml = document.querySelector("#results").innerHTML;

// The arrow in a card's corner leads to the standalone page -- no JavaScript,
// its own address. In the search list that is useful. On the focused view it
// is not drawn at all: the reader is already on a detail page for that bill,
// and a corner link to another one reads as a link to where they are.
scope.setFocused("HB1442");
try { scope.render(); } catch (e) {
  console.log("RENDER focused " + e.constructor.name + ": " + e.message);
  process.exit(1); }
const focusHtml = document.querySelector("#results").innerHTML;
scope.setFocused(null);
if (/class="detail"/.test(focusHtml)) {
  console.log("ARROW: the focused view still draws a corner link. It points at "
              + "the standalone page for the same bill, which from a reader's "
              + "seat is the page they are already on"); process.exit(1); }
if (!/class="detail"/.test(listHtml)) {
  console.log("ARROW: the search list drew no link to a standalone page");
  process.exit(1); }
// The tooltip promised "no JavaScript" until the standalone page became this
// same app with one bill open. It is the only place a member of the public
// was told that, and it sat on every card in the list.
if (/class="detail"[^>]*title="[^"]*(no JavaScript|without JavaScript)/i.test(listHtml)) {
  console.log("ARROW: the tooltip still promises the page needs no JavaScript, "
    + "which it has since it became a shell for this renderer");
  process.exit(1); }
if (!/class="detail"[^>]*title="[^"]{10,}"/.test(listHtml)) {
  console.log("ARROW: the link has no title, so hovering it says nothing about "
              + "where it goes"); process.exit(1); }
try { scope.render(); } catch (e) {
  console.log("RENDER unfocused " + e.constructor.name + ": " + e.message);
  process.exit(1); }

// The search box, in both of the places it appears.
//
// On the list, typing narrows the list -- no key to press, which is what a
// search box over a list should do.
const box = document.querySelector("#q");
if (!(box._on.input || []).length) {
  console.log("SEARCH: nothing listens to the search box"); process.exit(1); }
box.value = "insurance";
box.fire("input");
if (scope.getQuery() !== "insurance") {
  console.log("SEARCH: typing on the list view did not run the search");
  process.exit(1); }
box.value = ""; box.fire("input");

// On one bill's own view it must not. The reader is reading that bill, and
// running the search takes it off the screen, so it waits to be told: the
// Return key, or the button beside the box.
scope.setFocused("HB1442");
try { scope.render(); } catch (e) {
  console.log("RENDER refocus " + e.constructor.name + ": " + e.message);
  process.exit(1); }
box.value = "hb1442";
box.fire("input");
if (!scope.getFocused()) {
  console.log("SEARCH: typing in the box left the bill the reader was reading");
  process.exit(1); }
if (scope.getQuery() === "hb1442") {
  console.log("SEARCH: the half-typed query was run before it was confirmed");
  process.exit(1); }
box.fire("keydown", {key: "Enter"});
if (scope.getFocused()) {
  console.log("SEARCH: Return did not confirm the search and leave the bill");
  process.exit(1); }
if (scope.getQuery() !== "hb1442") {
  console.log("SEARCH: Return left the bill without running the search");
  process.exit(1); }

// And the button, which is the same thing for anyone not using a keyboard.
const go = document.querySelector("#qgo");
if (!(go._on.click || []).length) {
  console.log("SEARCH: the search button does nothing"); process.exit(1); }
scope.setFocused("HB1442");
try { scope.render(); } catch (e) {
  console.log("RENDER rerefocus " + e.constructor.name + ": " + e.message);
  process.exit(1); }
box.value = "insurance";
box.fire("input");
go.fire("click");
if (scope.getFocused() || scope.getQuery() !== "insurance") {
  console.log("SEARCH: the search button did not run the search");
  process.exit(1); }
scope.setFocused(null); box.value = ""; go.fire("click");

// And the inside of a card, which render() alone never touches. Every bill on
// the site sat on "Loading..." with its data already fetched, because
// renderDetail threw on its first use of a const declared further down -- and
// nothing here had ever called it.
var detail = {
  next_step:"Passed one chamber", status_source:"General Court docket",
  notes:[], stages:[{label:"In House committee",text:"It was introduced."}],
  narrative:"It was introduced.",
  events:[{date:"2026-03-06",type:"floor",body:"H",cancelled:false,
           raw:"Ought to Pass: MA RC 214-119 03/06/2026",action:"Ought to Pass",
           motion:"MA",vote_kind:"RC",yeas:"214",nays:"119",
           cite:"HJ 7, page 55",cite_url:"https://gc.nh.gov/hj7.pdf"}],
  rollcalls:[{question:"Ought to Pass",date:"2026-03-06",body:"H",yeas:214,nays:119,
              passed:true,vote_kind:"RC",amendment:"2026-0503h",threshold_needed:167,
              tally:{R:{Yea:200,Nay:12},D:{Yea:14,Nay:107}},
              members:[{n:"Rep. Jodi Nelson (R)",p:"R",v:"Yea",s:"nelson, jodi"}]}],
  // Two proceedings that differ in one field. The first has an end the chair
  // announced; the second has one the clustering guessed. They used to draw
  // the same range, which made the guess as strong a claim as the quotation
  // on 3,896 of the 5,283 placed proceedings.
  stations:[{state:"located",bill:"HB1442",kind:"public hearing",tolerance:30,
             start:150,end:900,video_id:"VID1",watch:"https://youtu.be/VID1",
             start_stated:true,end_stated:true,date:"2026-02-03",time:"10:00"},
            {state:"located",bill:"HB1442",kind:"executive session",tolerance:30,
             start:1500,end:2400,video_id:"VID3",watch:"https://youtu.be/VID3",
             start_stated:true,end_stated:false,date:"2026-02-10",time:"13:00"}],
  reports:[{majority_recommendation:"OUGHT TO PASS",minority_recommendation:null,
            source:"House Calendar 9, 2026",
            date:"2026-02-24",dated:"signed",cite:"HC 9",
            cite_url:"https://gc.nh.gov/hc9.pdf",
            reports:[{side:"Committee",author:"Rep. Jodi Nelson",committee:"Commerce",
                      text:"Consistent with RSA 91-A:4.",vote_yeas:19,vote_nays:0}]},
           // A divided report where the MAJORITY wants the bill killed and the
           // MINORITY wants it passed. The colours used to come from which side
           // won, so this row rendered the kill green and the pass red -- the
           // reader's shorthand for "good news" attached to the wrong motion on
           // 1,248 of 2,637 chips.
           {majority_recommendation:"INEXPEDIENT TO LEGISLATE",
            minority_recommendation:"OUGHT TO PASS",
            source:"House Calendar 11, 2026",
            // Dated only from the day the calendar was printed, because no
            // docket line cites HC 11. The page has to say which of the two
            // dates it is showing rather than presenting both as the same.
            date:"2026-03-13",dated:"printed",cite:"HC 11",cite_url:"",
            reports:[{side:"Majority",author:"Rep. A",committee:"Commerce",
                      text:"Against it.",vote_yeas:11,vote_nays:9},
                     {side:"Minority",author:"Rep. B",committee:"Commerce",
                      text:"For it."}]},
           // The Senate's own written report, from the General Court's
           // database. It has to be headed "Senate", cite the Senate's
           // calendar rather than the long source string naming the database,
           // and show its amendment. The written path was hardcoded to
           // "House", which put every one of 1,254 Senate reports under a
           // House committee's name.
           {majority_recommendation:"OUGHT TO PASS WITH AMENDMENT",
            minority_recommendation:"", body:"S",
            source:"Senate committee report, released 2026-05-13",
            date:"2026-05-12",dated:"signed",cite:"SC 18A",
            cite_url:"https://gc.nh.gov/sc18a.pdf",
            reports:[{side:"Committee",author:"Senator Debra Altschiller",
                      committee:"Judiciary",vote_yeas:5,vote_nays:0,
                      amendment:"2026-1219s",
                      text:"The committee heard that the federal rule is settled."}]},
           // And one of the 350 that record a recommendation and no reasoning.
           // An empty paragraph under a heading reads as a bug; saying the
           // report gives no reasoning is the fact.
           {majority_recommendation:"OUGHT TO PASS",
            minority_recommendation:"", body:"S",
            source:"Senate committee report, released 2026-06-02",
            date:"2026-06-01",dated:"printed",cite:"",cite_url:"",
            reports:[{side:"Committee",author:"Senator Tara Reardon",
                      committee:"Finance",vote_yeas:4,vote_nays:1,
                      amendment:"",text:""}]}],
  // The Senate's shape: one report, a vote, no minority, and no written
  // reasoning anywhere -- 1,531 of them, and the only report at all on 319
  // bills, which the tab used to answer with "not loaded yet".
  docket_reports:[{date:"2026-04-16",dated:"signed",body:"S",
                   committee:"Senate Commerce",side:"",
                   recommendation:"REFERRED TO INTERIM STUDY",
                   vote_yeas:5,vote_nays:0,amendment:"2026-1201s",
                   new_title:false,cite:"SC 14",cite_url:""}],
  // Why a committee that has already reported reports again.
  report_actions:[{before:"2026-03-13",date:"2026-03-05",
                   text:"Recommit (Rep. Berry): MA VV 03/05/2026"}],
  sponsors:[{name:"Nelson, Jodi",party:"R",chamber:"H",prime:true,
             display_full:"Rep. Jodi Nelson (R - Rock 13)"}],
  documents:[{label:"Bill text",url:"https://gc.nh.gov/x.pdf",kind:"text"}],
  amendments:[{num:"2026-0503h",kind:"Committee Amendment",where:"committee",
               date:"2026-02-11",body:"H",adopted:true,vote_kind:"VV",mover:"",
               proposed_by:"the Committee on Commerce",
               text:"Amend RSA 91-A:4 by replacing [the old text] the new.",
               source:"HC010.pdf",targets:["RSA 91-A:4"],supersedes:[]}],
  billtext:{version:"AS AMENDED BY THE HOUSE",title:"AN ACT x",analysis:"A summary.",
            body:"Be it Enacted: Amend RSA 91-A:4.",
            in_text:[{num:"2026-0503h",short:"503h",date:"5Mar2026"}],chars:40},
  rsa:{"RSA 91-A:4":"https://gc.nh.gov/rsa/html/VI/91-A/91-A-4.htm"}};
if (typeof scope.renderDetail !== "function") {
  console.log("renderDetail is not reachable from the harness"); process.exit(1); }

// A bill number resolves WITHIN the selected term. HB1 exists in every
// biennium, and finding the first row with that number across the whole index
// served the 2025 bill's history under the 2023 bill's heading -- the card
// read "filed 2023" and the body read "introduced on February 20, 2025".
if (typeof scope.yearOf === "function" && typeof scope.setTerm === "function") {
  const savedIdx = scope.IDX.slice();
  scope.IDX.length = 0;
  scope.IDX.push({id:"HB1", n:"HB 1", year:2026, term:"2025-2026", title:"the new one",
                  status:"In committee", kind:"active", nrc:0, committee:"", topic:"",
                  last_action:"2026-02-01", votedays:[]},
                 {id:"HB1", n:"HB 1", year:2024, term:"2023-2024", title:"the old one",
                  status:"Killed", kind:"done", nrc:0, committee:"", topic:"",
                  last_action:"2024-02-01", votedays:[]});
  scope.setTerm("2023-2024");
  if (scope.yearOf("HB1") !== "2024") {
    console.log("yearOf ignored the selected term: got " + scope.yearOf("HB1")
                + " for HB1 in 2023-2024"); process.exit(1); }
  const oldKey = scope.dkey("HB1");
  scope.setTerm("2025-2026");
  if (scope.yearOf("HB1") !== "2026") {
    console.log("yearOf did not follow the term back: got " + scope.yearOf("HB1"));
    process.exit(1); }
  if (scope.dkey("HB1") === oldKey) {
    console.log("the detail cache key is the same in both terms, so switching "
                + "term serves the other bill's record"); process.exit(1); }
  scope.IDX.length = 0;
  savedIdx.forEach(x => scope.IDX.push(x));
  scope.setTerm(null);
}
// Length alone does not prove a branch ran: the tabs and panes are ~1,600
// characters of markup before a single field is read, so a renderDetail that
// silently dropped every body would still clear the threshold below. Each
// fixture therefore names sentences only its own branches can produce.
// "want" is required in both views; "wantFocused" only in the expanded one,
// because the bill text section is the one thing the collapsed card omits.
var fixtures = [
  // Colour follows the motion, not the side that carried it. The fixture's
  // second report has the majority moving Inexpedient to Legislate and the
  // minority moving Ought to Pass, so these two strings can only appear if the
  // chip is coloured by what was moved.
  {name:"full", d:detail,
   want:['class="cstat s-done">INEXPEDIENT TO LEGISLATE',
         'class="cstat s-law">OUGHT TO PASS',
         // Each report says when, and whether that is the day the committee
         // signed or the day the calendar carrying it was printed.
         "Feb 24, 2026",
         "as printed",
         // The Senate's report is drawn at all, coloured by its motion, and
         // says why there is no reasoning under it.
         'class="cstat s-study">REFERRED TO INTERIM STUDY',
         "Senate Commerce",
         // The Senate's report carries the same three-part heading as the
         // House's -- who, by what vote, for what motion -- rather than a
         // bare tally, and its amendment is a fact of its own rather than
         // part of the footnote explaining what is missing.
         '<span class="secsub">Committee</span>',
         "Amendment 2026-1201s",
         "not on the site; this is what the docket records",
         // The Senate's written report is headed by its own chamber and cites
         // the Senate's calendar, not the database it was read out of.
         "Senate Judiciary",
         '<a href="https://gc.nh.gov/sc18a.pdf" rel="noopener">SC 18A</a>',
         "Senator Debra Altschiller",
         "Amendment 2026-1219s.",
         "the federal rule is settled",
         // And a report with no reasoning says so instead of leaving a space.
         "gives no reasoning",
         // And what happened between the two House reports.
         "Between these reports the docket",
         // The tab counts what the tab draws: three written blocks and the
         // Senate's one. It used to count only the written ones.
         // Shortened from "Committee reports": six labels wrapped onto four
         // rows on a 289px card, and this was the longest of them.
         "Reports (6)",
         // Votes counts d.rollcalls, which the pane draws, not b.nrc, which
         // omits procedural and voice votes; Videos counts stations that have
         // a recording. The fixture has one roll call and two recorded
         // stations. (This is JavaScript: a # here is a syntax error, and was.)
         "Votes (1)",
         "Videos (2)",
         // A start and an end, and nothing else. Both stations here start at a
         // boundary the chair announced, so neither carries the one word that
         // marks an inference.
         "00:02:30 starts",
         "00:15:00 ends",
         "00:25:00 starts",
         "00:40:00 ends",
         "00:02:30–00:15:00"]},
  // A bill with nothing on it yet. The fixture above populates every field, so
  // it only ever runs the arm of each ternary that HAS data -- and every one
  // of those has an else. That is what most bills look like early in a
  // session, and nothing here had ever drawn one.
  {name:"empty", d:{next_step:"Introduced"},
   want:["No roll call votes on this bill",
         "No scheduled proceedings on file",
         "No committee report on file",
         "No sponsors on file"]},
  // Amendments filed, text not read in yet. This is the only way to reach the
  // middle arm of the bill text block: the section is behind a
  // focused===b.id guard that ALSO requires text or amendments, so the arm
  // for "neither" is unreachable and is not asserted anywhere.
  {name:"amendments only",
   d:{next_step:"Introduced", amendments:detail.amendments},
   want:[], wantFocused:["site yet, but the amendments to it have"]}
];

// BOTH ways a detail can be drawn, on EVERY shape of bill. The expanded view
// runs code the collapsed one never touches -- and a template that reads a
// const declared further down does not throw until something makes it
// evaluate. Testing only the collapsed view passed a page that broke the
// moment a bill was opened.
for (var fi = 0; fi < fixtures.length; fi++) {
  for (var pass = 0; pass < 2; pass++) {
    var fx = fixtures[fi];
    var mode = fx.name + "/" + (pass ? "focused" : "collapsed");
    try { scope.setFocused && scope.setFocused(pass ? "HB1442" : null); }
    catch (_) {}
    try {
      var html = scope.renderDetail(scope.IDX[0], fx.d);
      if (!html || html.length < 500) {
        console.log("RENDERDETAIL (" + mode + ") produced "
                    + (html ? html.length : 0) + " chars");
        process.exit(1); }
      var want = (fx.want || []).concat(pass ? (fx.wantFocused || []) : []);
      for (var wi = 0; wi < want.length; wi++) {
        if (html.indexOf(want[wi]) < 0) {
          console.log("RENDERDETAIL (" + mode + ") drew " + html.length
                      + " chars but not " + JSON.stringify(want[wi]));
          process.exit(1); }
      }
    } catch (e) {
      console.log("RENDERDETAIL (" + mode + ") " + e.constructor.name + ": "
                  + e.message);
      process.exit(1); }
  }
}
console.log("ok");
""", encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True,
                           text=True, timeout=90)
        assert r.returncode == 0, (r.stdout + r.stderr).strip().splitlines()[0][:150]
        return "ok", ("loaded in node, drew a bill and rendered its detail "
                      "on three shapes of bill, collapsed and focused")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("frontend", "every station state the builder emits has a branch on the page")
def _states_covered():
    """The states build_site_v2 can produce, against the states bills.html draws.

    This exists because of a specific failure. renderHearings tested `located`
    and `approximate` in one if/else chain and then opened a SECOND chain with
    `if (whole_video)`, so a station that matched the first chain fell through
    the second to its `s.video_id` catch-all, which overwrote the inner it had
    just built. Separately, the builder emitted `stated` and `floor_stated`,
    which matched no branch at all. Between them, 5,453 stations carried a real
    timestamp that the page replaced with "the moment was not identified" --
    the site drew 742 of the 6,195 timestamps it held, and every check passed.

    Two halves, because either alone would have missed it: the states must be
    covered, and the chain must be a single chain.
    """
    b = Path("build_site_v2.py")
    page, h = page_source()
    if not (b.exists() and h):
        return "skip", "build_site_v2.py or bills.html not here"
    src = b.read_text(encoding="utf-8")

    emitted = set(re.findall(r'"state":\s*"(\w+)"', src))
    emitted |= set(re.findall(r'\["state"\]\s*=\s*"(\w+)"', src))
    emitted |= set(re.findall(r'"state",\s*"(\w+)"', src))
    # Ternaries: "state": "stated" if said else state -- the else arm is a
    # variable holding one of these, set just above.
    emitted |= set(re.findall(r'state,\s*start\s*=\s*"(\w+)"', src))
    assert emitted, "no station states found in build_site_v2.py"

    drawn = set(re.findall(r's\.state\s*===\s*"(\w+)"', page))
    assert drawn, "no state tests found in bills.html"

    # novideo and prestream mean there is nothing to play; the page handles
    # prestream by name and novideo by falling through to its final else.
    missing = sorted(emitted - drawn - {"novideo"})
    assert not missing, ("the builder emits " + ", ".join(missing)
                         + " and the page draws no branch for it")

    # One chain. A second `if (s.state===...)` after the first restarts the
    # else-ladder and lets a later catch-all overwrite an earlier match.
    opens = [m.start() for m in re.finditer(r'(?<!else )if\s*\(s\.state\s*===', page)]
    assert len(opens) <= 1, (f"{len(opens)} separate if-chains test s.state; a "
                             "station matching an earlier chain is overwritten "
                             "by the catch-all in a later one")
    return "ok", f"{len(emitted)} states emitted, all drawn, one chain"


@check("frontend", "no const is read before the line that declares it")
def _tdz():
    js, f = page_source()
    if not f:
        return "skip", "bills.html not here or in site/"
    assert js.strip(), "no script found for bills.html"
    bad = _tdz_suspects(js)
    assert not bad, "; ".join(bad[:3])
    return "ok", "checked every function in app.js"


# =============================================================== build chain ==

def _site_fixture(root):
    """The smallest project that still exercises every builder.

    Two bills, two members, one recording, one committee report, one roll call,
    one veto the docket settled and the status page did not.
    """
    d = root / "data"
    (root / "work" / "VID1").mkdir(parents=True)
    (root / "work" / "VID4").mkdir(parents=True)
    d.mkdir(parents=True)
    w = lambda p, o: (root / p).write_text(json.dumps(o), encoding="utf-8")

    # {term: {bill: record}}: the file the whole per-bill loop is driven
    # from, so a bill number alone at the top of the pipeline puts two
    # different bills under one key.
    w("data/bills.json", {"2025-2026": {
        "HB1442": {"designation": "HB 1442", "title": "relative to insurance coverage",
                   "lsr_num": "0503", "lsr_year": "2026", "subject": "Insurance",
                   "chamber": "H", "house_committee": "Commerce",
                   "senate_committee": "", "lsr": "2026-0503"},
        "SB434": {"designation": "SB 434", "title": "relative to school materials",
                  "lsr_num": "0611", "lsr_year": "2026", "subject": "Education",
                  "chamber": "S", "senate_committee": "Education",
                  "house_committee": "", "lsr": "2026-0611"},
        # A House Resolution, which the House adopts and which then goes
        # nowhere. Every bill in this fixture used to be an HB or an SB, so
        # nothing here noticed that 36 adopted resolutions were being shown as
        # still in progress, one of them "Pending action in the other chamber".
        "HR10": {"designation": "HR 10", "title": "honouring a retirement",
                 "lsr_num": "0900", "lsr_year": "2026", "subject": "Miscellaneous",
                 "chamber": "H", "house_committee": "Legislative Administration",
                 "senate_committee": "", "lsr": "2026-0900"},
        # Killed on the floor, with a chamber status that never caught up.
        "SB900": {"designation": "SB 900", "title": "relative to a study",
                  "lsr_num": "0901", "lsr_year": "2026", "subject": "Miscellaneous",
                  "chamber": "S", "senate_committee": "Judiciary",
                  "house_committee": "", "lsr": "2026-0901"}}})
    w("data/legislators.json", [
        {"id": "377204", "name": "Nelson, Jodi", "chamber": "H", "party": "Republican",
         # As the real roster writes it. The fixture carried "Rock." with a
         # trailing point, which data/legislators.json has never contained --
         # all ten of its abbreviations are bare -- so this asserted a shape
         # only the fallback table produced.
         "party_code": "R", "county": "Rockingham", "county_abbr": "Rock",
         "district": "13", "label": "Nelson, Jodi(R) Rock 13", "email": "j@gc.nh.gov",
         "url": "", "towns": ["Raymond"], "committees": ["Commerce"], "title": "",
         "phone": ""},
        {"id": "377207", "name": "Altschiller, Debra", "chamber": "S",
         "party": "Democrat", "party_code": "D", "county": "Rockingham",
         "county_abbr": "Rock", "district": "24",
         "label": "Altschiller, Debra(D) Rock. 24", "email": "d@gc.nh.gov", "url": "",
         "towns": ["Stratham"], "committees": ["Education"], "title": "", "phone": ""}])
    w("data/sponsors.json", {"HB1442": [
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R", "chamber": "H",
         "label": "Nelson, Jodi(R) Rock 13", "sequence": 0, "prime": True}]})
    w("data/member_votes.json", [
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R",
         "label": "Nelson, Jodi(R) Rock 13", "year": "2026", "body": "H",
         "vote_number": "310", "bill": "HB1442", "question": "Ought to Pass",
         "date": "2026-03-06", "vote": "Yea"},
        # The same bill number, the same chamber and the same vote sequence
        # number, in the previous term. Sequence numbers restart every session,
        # so this pair is not contrived -- it is what two terms of the file
        # look like side by side.
        {"member_id": "377204", "name": "Nelson, Jodi", "party": "R",
         "label": "Nelson, Jodi(R) Rock 13", "year": "2024", "body": "H",
         "vote_number": "310", "bill": "HB1442",
         "question": "Inexpedient to Legislate",
         "date": "2024-03-06", "vote": "Nay"}])
    w("data/towns.json", {"Raymond": [{"county": "Rockingham", "district": "13",
                                       "ward": "0", "seats": 2}]})
    # {term: {bill: record}}: bill numbers repeat every biennium, so the
    # file is keyed on the term and a bare bill number is not a key.
    w("narratives.json", {"2025-2026": {
        "SB900": {"narrative": "The Senate voted it down.", "stages": [],
                  "notes": [], "unrecognised": [],
                  "events": [{"date": "2026-02-19", "type": "floor", "body": "S",
                              "cancelled": False, "motion": "MA",
                              "action": "Inexpedient to Legislate, RC 16Y-8N",
                              "vote_kind": "", "yeas": None, "nays": None,
                              "raw": "Inexpedient to Legislate, RC 16Y-8N, "
                                     "MA; 02/19/2026"}]},
        "HB1442": {"narrative": "It was introduced.",
                   "stages": [{"label": "In House committee", "text": "It was introduced."}],
                   "notes": [], "unrecognised": [],
                   "events": [{"date": "2026-03-06", "type": "floor", "body": "H",
                               "cancelled": False, "action": "Ought to Pass",
                               "motion": "MA", "vote_kind": "RC", "yeas": "214",
                               "nays": "119",
                               # As narrative.py writes it: clean() has taken
                               # the citation off the line, and cite_of() has
                               # put it in a field. The fixture used to leave
                               # "HJ 7 P. 55" on the raw line, which no built
                               # narrative ever contains, and so tested a
                               # lookup against a string that is never there.
                               "cite": "HJ 7", "cite_page": "55",
                               "raw": "Ought to Pass: MA RC 214-119 03/06/2026"},
                              # The same volume, a different page. Documents
                              # dedupes on the URL, and a volume has one URL
                              # however many pages are cited, so listing them
                              # per event kept the first page and dropped the
                              # rest silently -- 499 entries on the real site.
                              {"date": "2026-03-06", "type": "amendment",
                               "body": "H", "cancelled": False,
                               "amendment": "2026-0503h", "amend_kind":
                               "Committee Amendment", "motion": "AA",
                               "vote_kind": "VV", "mover": "",
                               "cite": "HJ 7", "cite_page": "56",
                               "raw": "Amendment # 2026-0503h: AA VV 03/06/2026"},
                              # The same volume number in the OTHER year of the
                              # term. Only the 2026 HJ 7 is on file, and the
                              # bare key points at it, so this action keeps its
                              # citation and gets no link: HJ 7 of 2025 is a
                              # different document and does not contain it.
                              {"date": "2025-05-14", "type": "floor", "body": "H",
                               "cancelled": False, "action": "Ought to Pass",
                               "motion": "MA", "vote_kind": "VV",
                               "cite": "HJ 7", "cite_page": "9",
                               "raw": "Ought to Pass: MA VV 05/14/2025"},
                              # A committee report as the docket records it,
                              # with no calendar prose behind it. This is the
                              # Senate's whole shape -- one report, a vote, no
                              # minority -- and 319 bills have nothing else.
                              {"date": "2026-04-16", "type": "report", "body": "S",
                               "cancelled": False, "side": "",
                               "committee": "Senate Commerce",
                               "recommendation": "Referred to Interim Study",
                               "amendment": "", "report_date": "04/16/2026",
                               "yeas": "5", "nays": "0", "new_title": False,
                               "cite": "SC 14", "cite_page": "",
                               "raw": "Committee Report: Referred to Interim "
                                      "Study, 04/16/2026, Vote 5-0, CC"},
                              # A second Senate report, from the day the
                              # committee sent it back. The database has no
                              # written report for this one, so it stays a
                              # docket line -- which is the case the absorbing
                              # of the OTHER one must not break.
                              {"date": "2026-03-10", "type": "report",
                               "body": "S", "committee": "Senate Commerce",
                               "recommendation":
                                   "Re-referred to Committee",
                               "report_date": "03/10/2026", "cite": "SC 9",
                               "side": "", "yeas": "5", "nays": "0",
                               "cancelled": False,
                               "raw": "Committee Report: Re-referred to "
                                      "Committee, 03/10/2026; SC 9"},
                              # And the House report the calendar did print, so
                              # the two are joined on the calendar they cite.
                              {"date": "2026-02-27", "type": "report", "body": "H",
                               "cancelled": False, "side": "",
                               "committee": "Commerce",
                               "recommendation": "Ought to Pass",
                               "amendment": "", "report_date": "02/24/2026",
                               "yeas": "19", "nays": "0", "new_title": False,
                               "cite": "HC 9", "cite_page": "12",
                               "raw": "Committee Report: Ought to Pass "
                                      "02/24/2026 (Vote 19-0; CC)"}]},
        "HR10": {"narrative": "The House adopted it.", "stages": [], "notes": [],
                 "unrecognised": [],
                 "events": [{"date": "2026-03-05", "type": "floor", "body": "H",
                             "cancelled": False, "action": "Ought to Pass",
                             "motion": "MA", "vote_kind": "VV",
                             "raw": "Ought to Pass: MA VV 03/05/2026"}]},
        "SB434": {"narrative": "The governor vetoed it.", "stages": [], "notes": [],
                  "unrecognised": [],
                  "events": [{"date": "2026-08-19", "type": "other", "body": "H",
                              "cancelled": False,
                              "raw": "Veto Sustained 08/19/2026: RC 165-140 "
                                     "Lacking Necessary Two-Thirds Vote"}]}}})
    # {term: {bill: [votes]}}. A bill number is unique within a term and not
    # across terms, so the fixture carries the SAME number in two of them --
    # HB1442 in 2025-2026 with 214-119, and an older HB1442 in 2023-2024 with
    # a different tally. A build that merges them shows the wrong vote count
    # on the current bill, which is what the checks below look for.
    w("rollcalls.json", {"2023-2024": {"HB1442": [
        {"year": "2024", "body": "H", "number": "310", "date": "2024-03-06",
         "time": "09:30", "bill": "HB1442", "procedural": False,
         "question": "Inexpedient to Legislate",
         "question_raw": "Inexpedient to Legislate",
         "question_plain": "kill the bill", "yeas": 190, "nays": 160,
         "voting": 350, "not_voting": 50, "seats": 400, "seated": 400,
         "vacancies": 0, "threshold_needed": None, "threshold_rule": None,
         "passed": True, "threshold_note": None,
         "title": "an entirely different bill of the same number"}]},
                         "2025-2026": {"HB1442": [
        {"year": "2026", "body": "H", "number": "310", "date": "2026-03-06",
         "time": "11:12", "bill": "HB1442", "procedural": False,
         "question": "Ought to Pass", "question_raw": "Ought to Pass",
         "question_plain": "pass the bill", "yeas": 214, "nays": 119, "voting": 333,
         "not_voting": 67, "seats": 400, "seated": 400, "vacancies": 0,
         "threshold_needed": None, "threshold_rule": None, "passed": True,
         "threshold_note": None, "title": "relative to insurance coverage"}]}})
    # The Senate's own committee reports, from the General Court's database.
    # Two of them on one bill, which is what a bill re-referred to committee
    # and reported again looks like. The second deliberately shares its
    # recommendation with the HOUSE report event above and has no Senate
    # docket line of its own: joining these to the docket on the wording alone
    # gave 364 real Senate reports a House Calendar citation and the day the
    # House committee signed.
    # {term: {bill: [reports]}}: bill numbers repeat every biennium.
    w("senate_reports.json", {"2025-2026": {"HB1442": [
        {"bill": "HB1442", "title": "AN ACT relative to insurance coverage.",
         "source": "Senate committee report, released 2026-04-17",
         "date": "2026-04-17", "dated": "printed", "body": "S",
         "calendar": "Regular Calendar",
         "majority_recommendation": "REFERRED TO INTERIM STUDY",
         "minority_recommendation": "",
         "reports": [{"side": "Committee", "author": "Senator Debra Altschiller",
                      "committee": "Judiciary", "vote_yeas": 5, "vote_nays": 0,
                      "amendment": "",
                      "text": "The committee heard testimony that the coverage "
                              "question turns on federal rules still in flux, "
                              "and would rather study it than guess."}]},
        {"bill": "HB1442", "title": "AN ACT relative to insurance coverage.",
         "source": "Senate committee report, released 2026-06-02",
         "date": "2026-06-02", "dated": "printed", "body": "S",
         "calendar": "Consent Calendar",
         "majority_recommendation": "OUGHT TO PASS",
         "minority_recommendation": "",
         "reports": [{"side": "Committee", "author": "Senator Tara Reardon",
                      "committee": "Judiciary", "vote_yeas": 4, "vote_nays": 1,
                      "amendment": "", "text": "The study answered it."}]}]}})
    w("bill_status.json", {
        # The database's chamber status is not always advanced once a bill is
        # finished: 21 real ones still read REPORT FILED or NO ACTION on bills
        # signed into law, and SB532, SB533 and SB576 read IN COMMITTEE after
        # the Senate adopted Inexpedient to Legislate on them 16-8. An
        # in-progress status must not outrank a dated floor vote that ended it.
        "SB900": {"gen_status": "SENATE", "house_status": "",
                  "senate_status": "IN COMMITTEE", "text_pdf": "",
                  "chapter": "", "lsr": "2026-0900", "body": "S"},
        "HB1442": {
            "gen_status": "PASSED/ADOPTED", "house_status": "PASSED/ADOPTED",
            "senate_status": "", "text_pdf": "https://gc.nh.gov/x.pdf",
            "chapter": "", "lsr": "2026-0503", "body": "H"},
        "HR10": {"gen_status": "HOUSE", "house_status": "PASSED/ADOPTED",
                 "senate_status": "", "text_pdf": "", "chapter": "",
                 "lsr": "2026-0900", "body": "H"}})
    # {term: {bill: [reports]}}: bill numbers repeat every biennium.
    w("committee_reports.json", {"2025-2026": {"HB1442": [
        {"bill": "HB1442", "title": "insurance coverage",
         "majority_recommendation": "OUGHT TO PASS", "minority_recommendation": None,
         "source": "House Calendar 9, 2026",
         "reports": [{"side": "Committee", "author": "Rep. Jodi Nelson",
                      "committee": "Commerce", "text": "The committee supports this.",
                      "vote_yeas": 19, "vote_nays": 0}]}]}})
    # A floor appearance WITH a boundary the clerk stated. This is not
    # decoration: build_site_v2 used to apply that boundary by rebinding `st`
    # to stations[-1], and `st` was already the bill's status record from 350
    # lines earlier. Every bill that took this branch -- 611 of 2,234 on the
    # real data -- then shipped with no facts block, no text link, and a
    # next_step that fell back to "In progress". The fixture had no floor row
    # at all, so 33 checks passed over it. It has one now.
    w("floor_index.json", {"HB1442": [
        {"date": "2026-03-06", "body": "H", "video_id": "VID2",
         "title": "House Session", "precise": True, "debate_end": 1500,
         "window_start": 100, "motions": ["Ought to Pass"], "tallies": []}]})
    # marks: {video: {bill: [candidate, ...]}}, as segment_markers writes it.
    w("candidate_segments.json", {
        "VID2": {"HB1442": [
            {"start": 600, "end": None, "what": "floor debate",
             "how": "the clerk reads the committee report"}]},
        # A start the chair announced, on a recording where the clustering put
        # the same executive session 80 minutes away. Its end belongs to that
        # other placement, not to this one, and pairing the two is how 429
        # proceedings came to carry an end before their own start.
        "VID4": {"HB1442": [
            {"start": 300, "end": None, "what": "executive session",
             "how": "the chair opens it"}]}})
    # Both files hold a bare key beside the year-suffixed one, because their
    # fetchers write both -- and the bare key holds whichever year was fetched
    # last. Here the bare HJ 7 is the 2026 journal, so a 2025 action citing
    # HJ 7 must NOT be linked to it. That shape put 4,468 of 12,970 links on
    # the real site onto a volume that does not contain the action.
    w("journals.json", {
        "HJ 7": "https://gc.nh.gov/house/calendars_journals/Journals/2026/"
                "HJ%2007%20March%206,%202026.PDF",
        "HJ 7 2026": "https://gc.nh.gov/house/calendars_journals/Journals/2026/"
                     "HJ%2007%20March%206,%202026.PDF"})
    # The viewer link carries the calendar's date in its filename, which is
    # what dates a report the docket did not date. Written once: this file was
    # written twice a few lines apart, and the second copy -- which had no date
    # in the URL -- silently replaced the first.
    w("calendars.json", {
        "HC 9": "https://gc.nh.gov/house/calendars_journals/viewer.aspx"
                "?fileName=calendars%5C2026%5CNo9%20February%2027%202026.pdf",
        "HC 9 2026": "https://gc.nh.gov/house/calendars_journals/viewer.aspx"
                     "?fileName=calendars%5C2026%5CNo9%20February%2027%202026.pdf"})
    w("testimony.json", {"HB1442": {"support": 10, "oppose": 2, "neutral": 0}})
    w("work/VID1/segments.json", [
        {"bill": "HB1442", "kind": "public hearing", "located": True, "why_not": "",
         "short": False, "tolerance": 30, "dp_start": 0, "dp_end": 900,
         "start": 150.0, "end": 900.0, "mentions_inside": 6, "mentions_total": 8,
         "purity": 0.7, "start_stated": True, "end_stated": True}])
    # Same bill, a different day, and the clustering is 4,700 seconds from
    # where the chair opened it -- far outside its own +/-30. Its end is
    # describing a different span and must not be attached to this one.
    w("work/VID4/segments.json", [
        {"bill": "HB1442", "kind": "executive session", "located": True,
         "why_not": "", "short": False, "tolerance": 30, "dp_start": 0,
         "dp_end": 6000, "start": 5000.0, "end": 5600.0, "mentions_inside": 3,
         "mentions_total": 5, "purity": 0.6}])
    row = {"bill": "HB1442", "body": "H", "committee": "Commerce",
           "proceeding": "public hearing", "sched_date": "2026-02-03",
           "sched_time": "10:00", "venue": "LOB 302", "tier": "A-unique-slot",
           "bills_in_slot": "1", "match": "single video", "video_id": "VID1",
           "video_title": "House Commerce", "stream_start": "09:58:00",
           "predicted_offset": "0:02:00",
           "watch_url": "https://youtube.com/watch?v=VID1", "candidates": "",
           "observed_start": "", "observed_end": "", "notes": ""}
    # The same bill's executive session, on a recording where the chair opened
    # it at 0:05:00 and the clustering put it at 1:23:20. Only one of those can
    # be where it happened, and the site takes the chair's -- so the
    # clustering's END, which measures the other one, has nothing to do with
    # this span.
    row4 = dict(row, proceeding="executive session", sched_date="2026-02-10",
                sched_time="13:00", video_id="VID4", video_title="House Commerce",
                stream_start="12:58:00",
                watch_url="https://youtube.com/watch?v=VID4")
    # A HEARING THAT HAS NOT HAPPENED YET, dated from the clock rather than
    # written down, so it is still in the future whenever this runs.
    #
    # home.json's "upcoming" is only built for proceedings in the next
    # fortnight. Every fixture date here was fixed and in the past, so the
    # code that fills it never ran under preflight -- and the real build
    # printed "0 upcoming" for weeks and never ran it either. The morning
    # seven hearings were finally scheduled, that code put a (term, bill)
    # tuple where a bill number belongs and took the whole feed build down
    # with (bill or "").upper().
    #
    # A field that is only populated on some days needs a fixture that
    # populates it on all of them.
    from datetime import date as _date, timedelta as _td
    row5 = dict(row, bill="HB1443", proceeding="subcommittee work session",
                sched_date=(_date.today() + _td(days=3)).isoformat(),
                sched_time="09:30", video_id="", video_title="",
                stream_start="", predicted_offset="", watch_url="",
                match="no video found")
    with open(root / "verification_manifest.csv", "w", newline="",
              encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(row))
        wr.writeheader()
        wr.writerow(row)
        wr.writerow(row4)
        wr.writerow(row5)
    # The site reads proceedings.csv, not the manifest. Build it the way
    # build_all does, from the two sources the fixture just wrote.
    import subprocess, sys
    for f in ("build_proceedings.py", "proceedings.py"):
        if Path(f).exists():
            shutil.copy(f, root / f)
    r = _run([sys.executable, "build_proceedings.py"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, "fixture proceedings: " + (r.stderr or r.stdout)[-200:]


@check("files", "no child process is read in an unnamed encoding")
def _child_encoding():
    """text=True decodes in whatever the console happens to speak.

    A Python child on Windows writes its pipe in the console code page,
    where an em dash is the single byte 0x97, and a parent reading it as
    UTF-8 loses the whole stream: the reader thread raises, dies, and hands
    back None. This was found twice in one day -- silently in this file,
    where seven checks ran children and got nothing under a line that said
    77 passed, and loudly in build_all.py, where the pipeline stopped at
    step 3 of 21 with an AttributeError three frames from the punctuation
    that caused it.

    So the rule is repository-wide and mechanical: a call that decodes a
    child's output must say in what. child.run and child.popen do; anything
    passing text=True without an encoding does not.
    """
    out = _run(["git", "ls-files", "*.py"], capture_output=True, timeout=60)
    if out.returncode != 0:
        return "skip", "not a git repository"
    bad, n = [], 0
    for f in out.stdout.split():
        if f.startswith("obsolete/") or not Path(f).exists():
            continue
        try:
            tree = ast.parse(Path(f).read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in ("run", "Popen", "check_output",
                                           "call", "check_call")):
                continue
            n += 1
            kw = {k.arg for k in node.keywords if k.arg}
            texty = any(k.arg in ("text", "universal_newlines")
                        and getattr(k.value, "value", None) is True
                        for k in node.keywords)
            if texty and "encoding" not in kw:
                bad.append(f"{f}:{node.lineno}")
    assert not bad, ("these read a child's output without naming an "
                     "encoding, so one em dash empties the stream: "
                     + ", ".join(bad))
    return "ok", f"{n} direct subprocess calls, every text one names its encoding"


@check("build", "every builder runs end to end on a fixture site")
@check("build", "proceedings.csv builds from the fixture and both sources land in it")
def _proceedings_table():
    """One table, both sources. This exists because five tools in one day
    were found to read the manifest and not the floor index, and a check that
    builds the table from a fixture holding one of each is the cheapest way to
    notice the next tool that reads only one of them."""
    import shutil, subprocess, sys, tempfile
    root = Path(tempfile.mkdtemp(prefix="gr-proc-"))
    try:
        for f in ("build_proceedings.py", "proceedings.py"):
            shutil.copy(f, root / f)
        cols = ["bill","body","committee","proceeding","sched_date","sched_time",
                "venue","tier","bills_in_slot","match","video_id","video_title",
                "stream_start","predicted_offset","watch_url","candidates",
                "observed_start","observed_end","notes"]
        import csv
        with (root / "verification_manifest.csv").open("w", newline="",
                                                        encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(cols)
            w.writerow(["HB1442","H","Judiciary","public hearing","2026-02-03",
                        "10:00","LOB","A",1,"single video","CMTEV","t",
                        "2026-02-03 09:00:00","1:00:00","u","","","",""])
        (root / "floor_index.json").write_text(json.dumps({"HB1442": [
            {"date":"2026-03-05","body":"H","video_id":"FLOORV",
             "motions":["OTPA"],"tallies":["197-151"],"kind":"floor debate",
             "debate_end":21197.0,"window_start":18954.0,"precise":True}]}),
            encoding="utf-8")
        r = _run([sys.executable, "build_proceedings.py"], cwd=root,
                           capture_output=True, text=True)
        assert r.returncode == 0, (r.stderr or r.stdout)[-300:]
        sys.path.insert(0, str(root))
        import importlib
        P = importlib.import_module("proceedings")
        importlib.reload(P)
        rows = P.load(root / "proceedings.csv")
        assert len(rows) == 2, f"{len(rows)} rows, wanted 2"
        kinds = {r["kind"] for r in rows}
        assert kinds == {"public hearing", "floor debate"}, kinds
        fl = next(r for r in rows if r["kind"] == "floor debate")
        assert fl["debate_end"] == 21197.0 and fl["precise"], fl
        assert P.floor_videos(rows) == {"FLOORV"}
        assert rows[0]["term"] == "2025-2026", rows[0]["term"]
        return "ok", "2 rows, one of each kind, roll-call end carried"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _chain():
    """The check that would have caught the worst bug of the session.

    Importing a module and calling its pure functions never enters main(), so
    build_site_v2.py lost sixty-four lines of its loading code and every check
    here stayed green until a real build failed. This builds a two-bill project
    in the system temp directory and runs the whole chain over it: nothing
    touches the real site, nothing touches the network.
    """
    here = Path(".").resolve()
    need = ["build_site_v2.py", "build_pages.py", "build_bill_pages.py",
            "build_feeds.py", "check_site.py"]
    absent = [x for x in need if not (here / x).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        for src in ("bills.html", "site/bills.html"):
            if (here / src).exists():
                (root / "site").mkdir(exist_ok=True)
                shutil.copy2(here / src, root / "site" / "bills.html")
                break
        base = "https://graniterecord.org"
        steps = [
            ("build_site_v2.py", ["--data", "data", "--out", "site",
                                  "--segments", "work"], "site/index.json"),
            ("build_pages.py", ["--out", "site"], "site/legislators.html"),
            ("build_bill_pages.py", ["--site", "site", "--base", base],
             "site/sitemap.xml"),
            # After the bill pages, as in build_all: it reads their stations.
            ("build_committees.py", ["--site", "site", "--data", "data",
                                     "--base", base], "site/committees.json"),
            ("build_feeds.py", ["--site", "site", "--base", base],
             "site/feed/all.xml"),
        ]
        for script, args, produces in steps:
            if not (here / script).exists():
                continue
            r = _run([sys.executable, str(here / script), *args],
                               cwd=root, capture_output=True, text=True, timeout=180)
            if r.returncode != 0:
                tail = (r.stderr or r.stdout).strip().splitlines()
                raise AssertionError(f"{script}: " + (tail[-1][:120] if tail else "?"))
            assert (root / produces).exists(), f"{script} produced no {produces}"
        # Every bill page that advertises a feed has one. The records moved
        # inside the pages on 9 September and build_feeds went on reading the
        # old side files, so 5,436 pages linked a feed nobody wrote -- and this
        # chain passed, because all.xml was still produced.
        sys.path.insert(0, str(here))
        import site_read as SR
        for year, bid, rec in SR.records(root / "site"):
            if any(e.get("date") for e in (rec.get("events") or [])):
                fx = root / "site" / "feed" / "bill" / year / f"{bid.lower()}.xml"
                assert fx.exists(), (f"{bid} of {year} has dated events and its "
                                     f"page links a feed, but none was written")
        r = _run([sys.executable, str(here / "check_site.py"),
                            "--site", "site", "--base", base],
                           cwd=root, capture_output=True, text=True, timeout=120)
        bad = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("x ")]
        assert not bad, "check_site: " + "; ".join(bad)[:140]
        return "ok", ("6 builders, then check_site, on a 2-bill fixture; "
                      "every page that links a feed has one")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# A House Calendar, laid out the way pdftotext -layout returns one: the heading
# begins a line, the prose that follows does not. The minority's paragraph
# cites ANOTHER bill mid-sentence, which is what the real calendars do
# constantly -- "changes enacted in 2025 through HB 394, which established..."
# and "prevented many towns from adopting SB 2, concentrating budgetary and
# governance decisions...".
CALENDAR_PAGE = """REGULAR CALENDAR

HB 1418, setting a minimum affirmative vote for new or expanded spending.
MAJORITY: OUGHT TO PASS. MINORITY: INEXPEDIENT TO LEGISLATE.
Rep. Ross Berry for the Majority of Election Law. This legislation applies
only to towns and school districts that use the official ballot system. In
many towns turnout is extremely low, often around 15 percent. Vote 12-8.
Rep. Jim Maggiore for the Minority of Election Law. This limitation has
prevented many towns from adopting SB 2, concentrating budgetary decisions
among a relatively small number of attendees. It aligns with changes made
in 2025 through HB 394, which established that representatives serve in an
ex-officio capacity. For these reasons the minority opposes the motion.

HB 1419, relative to something else entirely.
OUGHT TO PASS.
Rep. Dan McGuire for Election Law. The committee heard testimony from the
sponsor and from two municipal clerks, and found the change to be a plain
correction of a cross-reference rather than a matter of policy. No member
spoke against it and the vote was unanimous. Vote 18-0.
"""


# Printed lines, not composed ones. The Election Law block is House Calendar 2
# of 2018 as pdftotext gave it, its two columns out of step at HB 1540; the
# Resources header and its work session are House Calendar 20 of 2005, and the
# Oversight header House Calendar 21 of 1999. Only the masthead's date and the
# stitching between blocks are this file's.
CALENDAR_FIELDS = """\
 Vol.40         Concord,N.H.  Friday,January12,2018                    No.2X

                              COMMITTEE MEETINGS

                    TUESDAY, JANUARY 23

ELECTION LAW, Room 308, LOB

10:00 a.m.  HB 1520, relative to access to ballots and relative to verification counts of machine-counted ballots.
10:30 a.m.  HB 1582, relative to the authority of the moderator to verify the device count.
11:00 a.m.  HB 1486, relative to "over voted" ballots.
            HB 1540-FN, relative to ranked-choice voting.
 1:00 p.m.  HB 1240, allowing voters to vote for multiple candidates for an office.
 1:30 p.m.  Executive session on pending legislation may be held throughout the day, time permitting, from
            the time the committee is initially convened.

RESOURCES, RECREATION AND DEVELOPMENT, Room 305, LOB
2:00 p.m.   Subcommittee work session on HB 491, relative to the inherent dangers of OHRV
            operation and limiting landowner liability for certain fish and game related land uses
            and HB 355, establishing a committee to study the environmental impact and
            damage mitigation of ATV use on public and private trails.

   HEALTH AND HUMAN SERVICES OVERSIGHT COMMITTEE, (RSA 126-A:13), Room 205, LOB
                                        1:30 p.m. Regular meeting.
"""


@check("calendar", "a committee's name keeps its commas, and a bill's line is never a committee",
       needs=("calendar_meetings",))
def _calendar_fields(calendar_meetings):
    """The two ways a calendar header was split in the wrong place.

    A name with a comma of its own was cut at it: "HEALTH, HUMAN SERVICES AND
    ELDERLY AFFAIRS, Room 205, LOB" became the committee "Health" with the rest
    kept as an address. And a bill's own line -- "HB 1540-FN, relative to
    ranked-choice voting.", which shouts and has a comma -- was read as a
    header wherever the columns slipped and left it with no time, so HB 1240
    was heard by the committee "Hb 1540-Fn" in the room "relative to
    ranked-choice voting.". Both were marked wrong on the bench. 16,375 and
    5,054 House rows on 10 September.
    """
    rows, pub, unpaired = calendar_meetings.parse(CALENDAR_FIELDS, "H")
    assert pub == (2018, 1, 12), f"the masthead read as {pub}"
    by = {r["bill"]: r for r in rows if r["bill"]}
    lead = re.compile(r"^(?:Hb|Sb|Hr|Sr|Hcr|Scr|Cacr|Hjr)\s*\d", re.I)
    bad = [r["committee"] for r in rows if lead.match(r["committee"] or "")]
    assert not bad, f"a bill's line was read as a committee: {bad}"
    want = [
        ("HB1240", "Election Law", "LOB 308"),
        ("HB355", "Resources, Recreation and Development", "LOB 305"),
        ("HB491", "Resources, Recreation and Development", "LOB 305"),
    ]
    for bill, com, room in want:
        r = by.get(bill)
        assert r, f"{bill} was not read at all"
        assert (r["committee"], r["room"]) == (com, room), (
            f"{bill} reads as {r['committee']!r} in {r['room'] or r['venue']!r}, "
            f"not {com!r} in {room!r}")
    over = [r for r in rows if r["kind"] == "regular meeting"]
    assert over and over[0]["committee"] == \
        "Health and Human Services Oversight Committee" and \
        over[0]["room"] == "LOB 205", (
        "a citation standing as its own part kept the room out of the room "
        f"field: {[(r['committee'], r['room'] or r['venue']) for r in over]}")
    # HB 1540's line has no time beside it, and the docket puts it at 1:00 --
    # the time printed a line below it. It is not given 11:00 by being welded
    # to HB 1486, and it is not given a time at all; it is counted.
    assert "HB1540" not in by, (
        f"HB 1540 was given a time the calendar does not print beside it: "
        f"{by['HB1540']['time']}")
    assert any("HB 1540" in u[3] for u in unpaired), \
        "HB 1540's untimed line was dropped without being counted"
    return "ok", (f"{len(rows)} rows: whole names, rooms in the room field, and "
                  "the untimed HB 1540 counted rather than timed or made a committee")


@check("reports", "a bill number inside a sentence does not start a new report",
       needs=("fetch_committee_reports",))
def _prose_bill_number(fetch_committee_reports):
    """It split a real minority report in half and filed the tail as a new bill.

    House Calendar 10 of 2026 says "...prevented many towns and school
    districts from adopting SB 2, concentrating budgetary and governance
    decisions...". SB 2 is not a bill -- it is the name New Hampshire gives the
    ballot-vote form of town meeting -- and the section that started there took
    1,669 characters of Municipal and County Government's minority report with
    it. HB 394, cited the same way in the same calendar, took 3,567 more.

    Across the 82 cached calendars: 2 phantom sections, 5 real ones that had
    been swallowed, and 70,935 characters of committee reasoning that were
    being cut off mid-report.
    """
    got = fetch_committee_reports.parse_reports(CALENDAR_PAGE, "House Calendar 1, 2026")
    keys = sorted(got)
    assert "SB2" not in keys, (
        "a bill number inside a sentence started a section: " + str(keys))
    assert "HB394" not in keys, (
        "a bill cited inside a report started a section: " + str(keys))
    assert keys == ["HB1418", "HB1419"], keys
    mino = [e for r in got["HB1418"] for e in r["reports"]
            if e.get("side") == "Minority"]
    assert mino, "the minority report was not read at all"
    text = mino[0]["text"]
    assert "the minority opposes the motion" in text, (
        f"the minority report is cut short at {len(text)} characters: "
        f"...{text[-70:]!r}")
    return "ok", "one section per heading, and the prose stays whole"


@check("build", "a bill with no filing year gets no feed, not one at the root")
def _feed_needs_a_year():
    """feed/bill/<year>/<id>.xml is the only thing keeping two terms apart.

    build_feeds had no notion of a term at all. The path is built from
    b.get("year"), and a bill without one collapsed it to feed/bill/<id>.xml --
    where the next term's bill of the same number lands on top. It is 2,233 of
    the site's 8,017 files, so this is the largest single place a bill number
    was still standing in for a bill.
    """
    here = Path(".").resolve()
    if not (here / "build_feeds.py").exists():
        return "skip", "build_feeds.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        site = root / "site"
        (site / "bill" / "2026").mkdir(parents=True)
        rows = [{"id": "HB1", "n": "HB 1", "year": 2026, "term": "2025-2026",
                 "title": "a bill with a year", "committee": "", "topic": "",
                 "status": "In committee", "kind": "active", "nrc": 0,
                 "last_action": "2026-02-01", "votedays": []},
                {"id": "HB2", "n": "HB 2", "year": "", "term": "",
                 "title": "a bill with none", "committee": "", "topic": "",
                 "status": "In committee", "kind": "active", "nrc": 0,
                 "last_action": "2026-02-01", "votedays": []}]
        (site / "index.json").write_text(json.dumps(rows), encoding="utf-8")
        # Records travel inside their pages, as build_bill_pages writes them.
        # This fixture used to write site/bills/2026/<ID>.json, the layout the
        # site stopped having on 9 September -- so it went on passing while
        # build_feeds read that dead path and skipped every real bill.
        d = {"next_step": "", "sponsors": [],
             "events": [{"date": "2026-02-01", "text": "It was introduced."}]}
        for r in rows:
            # HB2's page sits in a year folder, but the index gives it no
            # year: a record the index cannot place must still get no feed.
            (site / "bill" / "2026" / f"{r['id'].lower()}.html").write_text(
                '<script type="application/json" id="gr-data">'
                + json.dumps(d) + "</script>", encoding="utf-8")
        r = _run([sys.executable, str(here / "build_feeds.py"),
                            "--site", "site", "--base", "https://x.test"],
                           cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-160:]
        assert (site / "feed" / "bill" / "2026" / "hb1.xml").exists(),             "the bill WITH a year got no feed"
        stray = sorted(p.name for p in (site / "feed" / "bill").glob("*.xml"))
        assert not stray, (f"a feed was written to feed/bill/ with no year in "
                           f"the path: {stray}")
        # And the guid says which term, so two terms' HB1 cannot collide.
        x = (site / "feed" / "bill" / "2026" / "hb1.xml").read_text(encoding="utf-8")
        assert "2025-2026:HB1:" in x, "the guid does not carry the term"
        return "ok", "no year, no feed; and the guid names the term"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a reports file keyed on bill number is refused, not ignored")
def _reports_old_shape():
    """The third and fourth files off ARCHITECTURE item 3, same silence.

    committee_reports.json and senate_reports.json are {term: {bill: [reports]}}
    now. Read either in the old flat shape with a term lookup and every bill
    comes back with no committee report -- no recommendation, no vote, no
    reasoning -- and the build exits zero.
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    for name in ("committee_reports.json", "senate_reports.json"):
        root = Path(tempfile.mkdtemp())
        try:
            _site_fixture(root)
            nested = json.loads((root / name).read_text(encoding="utf-8"))
            flat = {b: r for byb in nested.values() for b, r in byb.items()}
            (root / name).write_text(json.dumps(flat), encoding="utf-8")
            r = _run([sys.executable, str(here / "build_site_v2.py"),
                                "--data", "data", "--out", "site",
                                "--segments", "work"],
                               cwd=root, capture_output=True, text=True,
                               timeout=180)
            assert r.returncode != 0, (
                f"the build accepted a {name} keyed on bill number and "
                "produced a site whose bills have no committee reports")
            said = (r.stdout + r.stderr).lower()
            assert "keyed on bill number" in said, (r.stdout + r.stderr)[-160:]
        finally:
            shutil.rmtree(root, ignore_errors=True)
    return "ok", "both reports files must name their term"


@check("build", "an archived term's bill cannot borrow the current term's text")
def _bills_by_term():
    """The last file the whole pipeline was driven from by bill number alone.

    data/bills.json is what build_bills loops over, so a bare bill number there
    puts two terms' bills under one key at the very top. It is {term: {bill:
    record}} now, and the loop runs over every term the file holds.

    testimony.json and sponsors.json are still flat, and HB100 exists in every
    biennium, so they are read ONLY for the term they describe. Showing an
    archived bill the CURRENT bill's sponsors would be worse than showing it
    none. bill_status.json and bill_text.json are keyed on the term now; the
    check below this one covers what an archived bill reads OUT of them.
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
        # The same number in an earlier term, which the flat files also carry.
        old = dict(bills["2025-2026"]["HB1442"])
        old.update({"lsr_year": "2024", "lsr": "2024-0503",
                    "title": "an entirely different bill of the same number"})
        bills["2023-2024"] = {"HB1442": old}
        (root / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-160:]
        idx = {(x["term"], x["id"]): x for x in
               json.loads((root / "site" / "index.json").read_text(encoding="utf-8"))}
        assert ("2023-2024", "HB1442") in idx, "the archived term produced no row"
        assert ("2025-2026", "HB1442") in idx, "the current term lost its row"

        a = json.loads((root / "site" / "bills" / "2024" / "HB1442.json")
                       .read_text(encoding="utf-8"))
        n = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                       .read_text(encoding="utf-8"))
        # sponsors.json is the flat file the fixture carries. text_url comes
        # from bill_status.json, which is keyed on the term: the fixture holds
        # only the current one, so the archived bill must still get nothing.
        assert n.get("sponsors"), "the current term's bill lost its sponsors"
        assert not a.get("sponsors"), (
            "the archived bill is showing the current term's sponsors")
        assert n.get("text_url"), "the current term's bill lost its text link"
        assert not a.get("text_url"), (
            "the archived bill is showing the current term's bill text link")
        return "ok", "two terms, one number, and neither borrows the other"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "an archived bill reads its own term's status and text")
def _termed_status_and_text():
    """The other half of the two-terms check, once the files can hold two.

    bill_status.json and bill_text.json were keyed on the bill number alone,
    and everything downstream leaned on that: an archived bill was given
    NOTHING from them, deliberately, because HB100 exists in every biennium and
    the current term's sponsors on a 2023 bill is worse than no sponsors.

    They are {term: {bill: record}} now, so an archived bill must read its own
    term out of them -- and still must not read the current term's. Both halves
    are asserted here, because a lookup that ignores the term passes the first
    half by accident: it hands back whatever record the flat file had.
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
        old = dict(bills["2025-2026"]["HB1442"])
        old.update({"lsr_year": "2024", "lsr": "2024-0503",
                    "title": "an entirely different bill of the same number"})
        # text_pdf off the bill record is the fallback for a term the status
        # file does not hold. Clearing it is what makes the assertion below
        # about the FILE rather than about the fallback.
        old.pop("text_pdf", None)
        bills["2023-2024"] = {"HB1442": old}
        (root / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")

        st = json.loads((root / "bill_status.json").read_text(encoding="utf-8"))
        if not all(re.match(r"^\d{4}-\d{4}$", k) for k in st):
            st = {"2025-2026": st}
        st["2023-2024"] = {"HB1442": {
            "gen_status": "SIGNED BY GOVERNOR", "house_status": "",
            "senate_status": "", "text_pdf": "https://gc.nh.gov/archived.pdf",
            "chapter": "", "lsr": "2024-0503", "body": "H"}}
        (root / "bill_status.json").write_text(json.dumps(st), encoding="utf-8")

        (root / "bill_text.json").write_text(json.dumps({
            "2025-2026": {"HB1442": {
                "version": "as introduced", "title": "the current bill",
                "text": "ANALYSIS\nThe current term's analysis.\n"
                        "Be it Enacted by the Senate and House"}},
            "2023-2024": {"HB1442": {
                "version": "as amended", "title": "the archived bill",
                "text": "ANALYSIS\nThe archived term's analysis.\n"
                        "Be it Enacted by the Senate and House"}},
        }), encoding="utf-8")

        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]

        a = json.loads((root / "site" / "bills" / "2024" / "HB1442.json")
                       .read_text(encoding="utf-8"))
        n = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                       .read_text(encoding="utf-8"))

        # text_url is the link AS PUBLISHED, not the raw scrape: the
        # session year is appended where the scrape did not carry one,
        # because billText.aspx without it answers with an ASP.NET error.
        assert (a.get("text_url") or "").startswith(
                "https://gc.nh.gov/archived.pdf"), (
            "the archived bill did not read its own term out of "
            f"bill_status.json; text_url is {a.get('text_url')!r}")
        assert n.get("text_url") != "https://gc.nh.gov/archived.pdf", (
            "the current bill took the ARCHIVED term's text link")

        at = (a.get("billtext") or {}).get("analysis", "")
        nt = (n.get("billtext") or {}).get("analysis", "")
        assert "archived term" in at, (
            f"the archived bill's text came from the wrong term: {at[:60]!r}")
        assert "current term" in nt, (
            f"the current bill's text came from the wrong term: {nt[:60]!r}")
        return "ok", ("status and text both follow the term, in both "
                      "directions")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a narratives.json keyed on bill number is refused, not ignored")
def _narratives_old_shape():
    """The same silence rollcalls.json had, on the file that drives everything.

    narratives.json is {term: {bill: record}} because bill numbers repeat every
    biennium. Read the old flat shape with a term lookup and every bill comes
    back with no history, no status, no reports and no events -- and the build
    succeeds.
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        nested = json.loads((root / "narratives.json").read_text(encoding="utf-8"))
        flat = {b: r for byb in nested.values() for b, r in byb.items()}
        (root / "narratives.json").write_text(json.dumps(flat), encoding="utf-8")
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode != 0, ("the build accepted a narratives.json keyed "
                                   "on bill number and produced a site whose "
                                   "bills have no history")
        said = (r.stdout + r.stderr).lower()
        assert "keyed on bill number" in said, (r.stdout + r.stderr).strip()[-160:]
        return "ok", "the build stops and says how to rebuild it"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "an in-progress status does not outrank a vote that ended the bill")
def _disposed_beats_stale_status():
    """SB532, SB533 and SB576 read "In committee" after the Senate killed them.

    The status columns are not always advanced once a bill is finished -- 21 of
    the real ones still read REPORT FILED or NO ACTION on bills signed into law
    -- and classify_stated outranks the docket, so a stale in-progress status
    wins over a dated floor vote that disposed of the bill.

    The evidence is the motion code, not a substring of the docket:
    classify() tests `"inexpedient to legislate" in text`, and that phrase is in
    every MINORITY report too, which is how three concurrent resolutions the
    House adopted 197-156, 195-149 and 204-163 came to read "Killed".
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        idx = {x["id"]: x for x in
               json.loads((root / "site" / "index.json").read_text(encoding="utf-8"))}
        assert idx["SB900"]["status"] == "Killed", (
            f"SB900 reads {idx['SB900']['status']!r}; the Senate adopted "
            "Inexpedient to Legislate on it and the status field had not "
            "caught up")
        # And the rule must not reach a bill whose last adopted motion passed
        # it. HB1442's docket carries "Inexpedient to Legislate" nowhere, but
        # HR10's minority reports do on the real data.
        assert idx["HB1442"]["status"] != "Killed", idx["HB1442"]["status"]
        assert idx["HR10"]["status"].startswith("Adopted"), idx["HR10"]["status"]
        return "ok", "a dated floor vote beats an in-progress status field"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the Senate's own report reaches the page, dated from its own chamber")
def _senate_reports():
    """1,254 bills had a bare docket line where the Senate had written a report.

    build_site_v2.committee_reports said "a Senate report always [lands in the
    docket list], because the Senate prints no reasoning". That is true of the
    docket and false of the record: the General Court's database holds 1,446
    Senate committee reports and 1,096 of them explain the committee's
    thinking.

    The join back to the docket -- which supplies the day the committee signed
    and the journal page -- has to know the chamber. On the recommendation
    alone it matched the wrong one 364 times, because "Ought to Pass" is what
    both chambers say.
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        hb = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                        .read_text(encoding="utf-8"))
        sen = [x for x in hb.get("reports", [])
               if (x.get("source") or "").startswith("Senate committee report")]
        assert len(sen) == 2, f"{len(sen)} Senate reports on the page, not 2"
        by_rec = {x["majority_recommendation"]: x for x in sen}

        # The one the docket also records: it takes the signing date and the
        # Senate Calendar page, not the day it was released.
        study = by_rec["REFERRED TO INTERIM STUDY"]
        assert (study["dated"], study["date"]) == ("signed", "2026-04-16"),             (study["dated"], study["date"])
        assert study["cite"] == "SC 14", study["cite"]
        assert "federal rules still in flux" in study["reports"][0]["text"],             "the committee's reasoning did not reach the page"

        # The one the docket does not: it must not borrow the House's.
        otp = by_rec["OUGHT TO PASS"]
        assert not (otp.get("cite") or "").startswith("HC"),             (f"a Senate report cites {otp['cite']}, a House Calendar -- the "
             "join matched on the recommendation without the chamber")
        assert otp["date"] != "2026-02-24",             "a Senate report is dated from the day the House committee signed"

        # The docket line it replaces is not shown underneath it as well --
        # and the OTHER Senate report, which the database does not cover, still
        # is. Absorbing has to be targeted; dropping every Senate docket line
        # once any written report exists would lose the second report entirely.
        dk = [x.get("cite") for x in hb.get("docket_reports", [])
              if x.get("body") == "S"]
        assert "SC 14" not in dk, "the docket line the written report replaces "                                  "is shown underneath it as well"
        assert "SC 9" in dk, (f"Senate docket lines are {dk}; the report the "
                              "database does not cover has been dropped")
        return "ok", "2 written, 1 docket line kept, dated from the Senate"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "an earlier term's votes stay on the earlier term's bill")
def _rollcalls_by_term():
    """HB1442 exists in 2023-2024 and in 2025-2026, with different tallies.

    Bill numbers repeat every biennium and nothing outside proceedings.csv used
    to know it. rollcalls.json is keyed on the term for that reason, and the
    fixture carries the same number twice so a build that merged them would be
    visible here rather than in two years' time.
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        hb = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                        .read_text(encoding="utf-8"))
        # The votes tab also carries voice and division votes read off the
        # docket, which have no tally and no member grid. The roll call FILE's
        # entries are the ones with a tally, and those are what is at issue.
        rcs = [r for r in hb.get("rollcalls", []) if r.get("tally")]
        assert len(rcs) == 1, (f"HB1442 shows {len(rcs)} recorded roll calls; "
                               "the 2023-2024 bill of the same number has "
                               "leaked in")
        got = (rcs[0]["yeas"], rcs[0]["nays"])
        assert got == (214, 119), f"HB1442's vote reads {got}, not 214-119"
        assert not [r for r in hb.get("rollcalls", []) if r.get("yeas") == 190],             "the 2023-2024 tally of 190-160 is on the 2025-2026 bill"
        votes = {m["v"] for m in rcs[0].get("members", [])}
        assert votes == {"Yea"}, (f"the member grid holds {sorted(votes)}; the "
                                  "previous term's Nay has been counted too")
        idx = {x["id"]: x for x in
               json.loads((root / "site" / "index.json").read_text(encoding="utf-8"))}
        assert idx["HB1442"]["nrc"] == 1, idx["HB1442"]["nrc"]
        return "ok", "the same number in two terms stays two bills"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a rollcalls.json keyed on bill number is refused, not ignored")
def _rollcalls_old_shape():
    """The failure this replaces is silent.

    rollcalls.json used to be {bill: [votes]} and is now {term: {bill: [votes]}}.
    Read the old shape with the new lookup and every bill comes back with no
    recorded votes, the build succeeds, and 449 bills quietly lose their
    tallies. Five instances of exactly that in a week is why this is a check.
    """
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        nested = json.loads((root / "rollcalls.json").read_text(encoding="utf-8"))
        flat = {}
        for byterm in nested.values():
            for bill, votes in byterm.items():
                flat.setdefault(bill, []).extend(votes)
        (root / "rollcalls.json").write_text(json.dumps(flat), encoding="utf-8")
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode != 0, ("the build accepted a rollcalls.json keyed on "
                                   "bill number and produced a site with no votes")
        said = (r.stdout + r.stderr).lower()
        assert "keyed on bill number" in said, (r.stdout + r.stderr).strip()[-160:]
        return "ok", "the build stops and says how to rebuild it"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the built site says what it should")
def _chain_output():
    here = Path(".").resolve()
    if not (here / "build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        s = root / "site"
        hb = json.loads(
            (s / "bills" / "2026" / "HB1442.json").read_text(encoding="utf-8"))

        def _yr(u):
            m = re.search(r"(?:%5C|/)(\d{4})(?:%5C|/)", u or "")
            return m.group(1) if m else None

        def _exec(d):
            return next((x for x in d.get("stations", [])
                         if x.get("what") == "executive session"), None)

        idx = {x["id"]: x for x in
               json.loads((s / "index.json").read_text(encoding="utf-8"))}
        lg = json.loads((s / "legislators.json").read_text(encoding="utf-8"))
        checks = [
            # And nothing is left at the flat path, which would mean the
            # writer moved and a reader did not.
            (not list((s / "bills").glob("*.json")),
             "per-bill data is still being written flat as well as under its "
             f"year: {[p.name for p in (s / 'bills').glob('*.json')][:4]}"),
            (len(hb.get("documents", [])) >= 4, "the Documents tab is empty"),
            # Every page of a volume this bill is on, not whichever came first.
            # A citation is only linked to a volume from its own year. The
            # 2025 event below cites HJ 7, which is on file only as the 2026
            # journal, so it keeps its citation and gets no link.
            (not any((e.get("cite_url") and _yr(e["cite_url"])
                      and _yr(e["cite_url"]) != (e.get("date") or "")[:4])
                     for e in hb.get("events", [])),
             "a citation links a volume from a different year than its action: "
             + repr([(e.get("date"), e.get("cite"), e.get("cite_url"))
                     for e in hb.get("events", [])
                     if e.get("cite_url") and _yr(e["cite_url"])
                     and _yr(e["cite_url"]) != (e.get("date") or "")[:4]])),
            (any((e.get("date") or "").startswith("2025")
                 and (e.get("cite") or "").startswith("HJ 7")
                 and not e.get("cite_url")
                 for e in hb.get("events", [])),
             "the 2025 action citing HJ 7 should keep its citation and lose "
             "its link, since only the 2026 volume is on file: "
             + repr([(e.get("date"), e.get("cite"), e.get("cite_url"))
                     for e in hb.get("events", [])
                     if (e.get("cite") or "").startswith("HJ 7")])),
            (any(d["label"] == "HJ 7, pages 55 and 56"
                 for d in hb.get("documents", [])),
             "the journal entry names one page and drops the others: "
             + repr([d["label"] for d in hb.get("documents", [])
                     if d.get("kind") == "record"])),
            (hb["stations"][0].get("start_stated") is True,
             "a stated boundary did not reach the station"),
            (hb["stations"][0].get("tolerance") == 30, "the tolerance was not carried"),
            (hb["reports"][0]["reports"][0].get("vote_yeas") == 19,
             "the committee vote was not carried"),
            # A written report takes its date from the docket line citing the
            # same calendar -- the day the committee signed, which is 24
            # February here and three days before the calendar carrying it.
            # Without this the nine bills a single committee reported twice
            # show two blocks a reader cannot tell apart.
            (hb["reports"][0].get("date") == "2026-02-24",
             f"the report is dated {hb['reports'][0].get('date')!r}, not the day "
             "the committee signed"),
            (hb["reports"][0].get("dated") == "signed",
             "the report does not say where its date came from"),
            (hb["reports"][0].get("cite_url"),
             "the report does not link the calendar it was printed in"),
            # And the Senate's, which no calendar prints the reasoning for.
            (len(hb.get("docket_reports") or []) == 1,
             f"{len(hb.get('docket_reports') or [])} docket reports, expected the "
             "Senate's one; a House report whose calendar IS on file must not "
             "appear twice"),
            ((hb.get("docket_reports") or [{}])[0].get("committee")
             == "Senate Commerce",
             "the reporting committee was not carried onto the docket report"),
            # A start the chair announced keeps its own placement, and takes no
            # end from a clustering that put the proceeding somewhere else.
            # 2,732 stations paired the two; 429 of them ended before they
            # began, and the page dropped those ends without saying anything.
            (_exec(hb) is not None, "the executive session is not on the page"),
            ((_exec(hb) or {}).get("start") == 300,
             f"the stated start was not used: {(_exec(hb) or {}).get('start')!r}"),
            # Every sponsor is named the same way. A member who has left has
            # no page, so no link -- that is the only difference the site draws.
            (all((sp.get("chamber") or "").strip() for sp in hb.get("sponsors", [])),
             "a sponsor has no chamber, which puts them under a heading of "
             "their own: "
             + repr([sp.get("name") for sp in hb.get("sponsors", [])
                     if not (sp.get("chamber") or "").strip()])),
            ((_exec(hb) or {}).get("end") is None,
             "an end from a placement 4,700 seconds away was attached to a "
             f"start the chair stated: {(_exec(hb) or {}).get('end')!r}"),
            (all(s.get("end") is None or s.get("start") is None
                 or s["end"] > s["start"] for s in hb["stations"]),
             "a station ends at or before it starts"),
            (hb["events"][0].get("cite_url"), "the journal citation did not resolve"),
            # A House Resolution is adopted by the House and that is the end
            # of it. Reading it as "Passed one chamber" implies a Senate stage
            # that does not exist, and "Became law" would be worse.
            (idx["HR10"]["status"] == "Adopted by the House",
             f"HR10 reads {idx['HR10']['status']!r}, not the end of a "
             "one-chamber resolution"),
            (idx["HR10"]["kind"] == "adopted",
             f"HR10 kind is {idx['HR10']['kind']!r}"),
            (idx["SB434"]["status"] == "Vetoed, override failed",
             f"SB434 reads {idx['SB434']['status']!r}, not the docket's outcome"),
            (idx["HB1442"].get("sponsor_label") == "Rep. Jodi Nelson (R)",
             f"sponsor reads {idx['HB1442'].get('sponsor_label')!r}"),
            (lg[0].get("display_full") == "Rep. Jodi Nelson (R - Rock 13)",
             f"legislator reads {lg[0].get('display_full')!r}"),
            # The floor branch ran at all: the stated start reached the station.
            (any(x.get("debate_start") == 600 for x in hb["stations"]),
             "the stated floor start did not reach the station, so the branch "
             "below was not exercised"),
            # And taking that branch did not cost the bill its status record.
            # These three are the fields that were lost when the floor code
            # rebound `st`, and they are checked together because they failed
            # together and would again.
            ((hb.get("text_url") or "").startswith("https://gc.nh.gov/x.pdf"),
             f"text_url reads {hb.get('text_url')!r} on a bill with a stated "
             "floor boundary"),
            (hb.get("facts", {}).get("lsr") == "2026-0503",
             f"facts reads {hb.get('facts')!r} on a bill with a stated floor "
             "boundary"),
            (hb.get("next_step", "").startswith("House:"),
             f"next_step reads {hb.get('next_step')!r}, not the per-chamber "
             "status the status page gives"),
        ]
        bad = [why for ok_, why in checks if not ok_]
        assert not bad, "; ".join(bad)
        return "ok", f"{len(checks)} facts about the output, all as expected"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "captions that stop an hour short put no time on the page")
def _late_captions_fixture():
    """A caption track can start an hour into its recording, and then every
    time read off it is an hour early: the chair's stated boundary, drawn as
    the chair's own moment, and the clustering beside it. On 10 September that
    was 74 published starts on nine recordings, and nothing on any page looked
    wrong, because a start an hour early is still a start.

    caption_span.py compares where the captions stop with where the recording
    does, and build_site_v2 withholds both sources for a track past the line.
    Here the fixture's VID4 -- a stated start at 0:05:00 and a clustered one
    at 1:23:20 -- gets captions that stop at twenty minutes of two hours, and
    VID1 gets captions that reach the end of its fifteen. One must lose its
    times and the other must keep them, or the guard is either missing or
    withholding what it has no reason to doubt.
    """
    here = Path(".").resolve()
    if not ((here / "build_site_v2.py").exists()
            and (here / "caption_span.py").exists()):
        return "skip", "build_site_v2.py or caption_span.py not here"
    root = Path(tempfile.mkdtemp(prefix="gr-late-"))
    try:
        _site_fixture(root)

        def track(cues):
            # YouTube's json3 as yt-dlp writes it: a window spanning the
            # track, then one event per cue, indented a field to a line.
            ev = [{"tStartMs": 0, "dDurationMs": cues[-1][0] + 4000, "id": 1,
                   "wpWinPosId": 1, "wsWinStyleId": 1}]
            ev += [{"tStartMs": t, "dDurationMs": 4000, "wWinId": 1,
                    "segs": [{"utf8": s}]} for t, s in cues]
            return json.dumps({"wireMagic": "pb3", "events": ev}, indent=2)

        (root / "work" / "VID4" / "captions.en.json3").write_text(track([
            (300000, "will open the executive session on House Bill 1442"),
            (1196000, "we are adjourned")]), encoding="utf-8")
        (root / "work" / "VID1" / "captions.en.json3").write_text(track([
            (150000, "I am opening the hearing on House Bill 1442"),
            (892000, "thank you all")]), encoding="utf-8")
        with open(root / "videos_house_fixture.csv", "w", newline="",
                  encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["video_id", "title", "duration_iso"])
            wr.writerow(["VID1", "House Commerce", "PT15M30S"])
            wr.writerow(["VID4", "House Commerce", "PT2H"])
        r = _run([sys.executable, str(here / "build_site_v2.py"),
                  "--data", "data", "--out", "site", "--segments", "work"],
                 cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
        rec = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                         .read_text(encoding="utf-8"))
        by = {s.get("video_id"): s for s in rec.get("stations") or []}
        late, kept = by.get("VID4"), by.get("VID1")
        assert late and kept, (
            "the fixture's two recorded proceedings are not both on HB1442's "
            f"record: {sorted(k for k in by if k)}")
        assert late.get("start") is None and late.get("state") == "approximate", (
            "VID4's captions stop 100 minutes short of its recording and its "
            f"station still reads {late.get('state')} at {late.get('start')}: "
            "a time read off an out-of-step track reached the page")
        assert kept.get("start") is not None, (
            "VID1's captions reach the end of its recording and its station "
            "lost its start: the guard is withholding a time it has no reason "
            "to doubt")
        assert "withheld" in r.stdout and "VID4" in r.stdout, (
            "the build withheld VID4's times without saying so")
        return "ok", ("a track stopping 100 minutes short loses its stated and "
                      "clustered times, one reaching its end keeps them, and "
                      "the build names what it withheld")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ================================================================ data checks ==

@check("data", "former_members.json is the shape the site expects")
def _former():
    p = Path("former_members.json")
    if not p.exists():
        return "skip", ("not here. resolve_members.py writes it to the project "
                        "root and build_data.py reads it there")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(d, dict), f"expected an id-keyed object, got {type(d).__name__}"
    named = sum(1 for v in d.values() if isinstance(v, dict) and v.get("name"))
    sample = next((v.get("name") for v in d.values()
                   if isinstance(v, dict) and v.get("name")), "")
    assert named, "no entries carry a name"
    return "ok", f"{named} members named, e.g. {sample!r}"


@check("data", "manifest venues are venues")
def _venues():
    p = Path("verification_manifest.csv")
    if not p.exists():
        return "skip", "no verification_manifest.csv here"
    rows = list(csv.DictReader(open(p, encoding="utf-8-sig")))
    kinds = Counter(r.get("proceeding", "") for r in rows)
    import re as _re
    cite = _re.compile(r"\b(?:HJ|SJ|HC|SC)\s+\d+")
    bad = [r["venue"] for r in rows if cite.search(r.get("venue") or "")]
    assert not bad, (f"{len(bad)} venues contain a journal citation, e.g. "
                     f"{bad[0]!r} -- the House scheduling pattern is swallowing it")
    return "ok", (f"{len(rows):,} rows, {len(kinds)} proceeding kinds: "
                  + ", ".join(sorted(kinds)))


@check("data", "the proceeding parser is not dropping scheduling rows")
def _dropped():
    if not (Path("Docket.txt").exists() and Path("docket_parser.py").exists()):
        return "skip", "Docket.txt or docket_parser.py not here"
    dp = imp("docket_parser")
    assert dp, "docket_parser.py will not import"
    rows = dp.parse_rows("Docket.txt")
    looks = [r for r in rows
             if "Hearing:" in r["desc"] or "Executive Session:" in r["desc"]
             or "Work Session:" in r["desc"]]
    procs = dp.parse_proceedings(rows, dp.build_referral_timeline(rows))
    ratio = len(procs) / max(len(looks), 1)
    assert ratio > 0.95, (f"{len(looks):,} rows look scheduled, {len(procs):,} "
                          f"parsed ({ratio:.0%}); the rest are dropped silently")
    return "ok", f"{len(looks):,} look scheduled, {len(procs):,} parsed ({ratio:.0%})"


@check("data", "a committee report line gives up its recommendation and nothing else")
def _report_rec():
    if not (Path("Docket.txt").exists() and Path("narrative.py").exists()):
        return "skip", "Docket.txt or narrative.py not here"
    nv = imp("narrative")
    assert nv, "narrative.py will not import"
    recs, dated = Counter(), []
    for rows in nv.parse_docket("Docket.txt").values():
        for r in rows:
            ev = nv.classify(r["desc"])
            if ev["_type"] != "report":
                continue
            rec = (ev.get("rec") or "").strip()
            recs[rec] += 1
            if re.search(r"\d", rec):
                dated.append(rec)
    # The recommendation is a motion out of a fixed vocabulary. When the
    # pattern ends it in the wrong place it takes the date with it, and the
    # count goes from nine to hundreds without anything failing: the phrase
    # table still matches on startswith, so the sentence still reads correctly
    # and only the one line that falls past the table shows the damage.
    assert not dated, (f"{len(dated):,} recommendations carry a date, e.g. "
                       f"{dated[0]!r}; the pattern is ending the motion late")
    assert len(recs) < 20, (f"{len(recs):,} distinct recommendations; a committee "
                            "moves one of about nine things")
    # Each of these is a motion the docket really uses; losing one means a whole
    # class of report stopped parsing.
    for want in ("Ought to Pass", "Ought to Pass with Amendment",
                 "Inexpedient to Legislate", "Rereferred to Committee"):
        assert recs.get(want), f"no report line reads {want!r} any more"
    # Every report line carries a recommendation; most carry a vote and a date,
    # and a minority report carries neither because it is not voted on.
    voted = sum(1 for rows in nv.parse_docket("Docket.txt").values() for r in rows
                if nv.classify(r["desc"]).get("y"))
    assert voted > sum(recs.values()) * 0.7, (
        f"only {voted:,} of {sum(recs.values()):,} report lines yield a vote")
    return "ok", (f"{sum(recs.values()):,} report lines, {len(recs)} distinct "
                  f"recommendations, {voted:,} with a vote")


@check("naming", "a bill whose ending is only on the status page says so once",
       needs=("build_site_v2",))
def _closing(build_site_v2):
    cs = build_site_v2.closing_stage
    stage = lambda t: {"stages": [{"label": "x", "text": t}]}
    # The docket records actions, and a session ending is not one -- it just
    # stops. 117 bills end with a committee report and a red headline the
    # status page alone knows about.
    got = cs("Died when the session ended",
             stage("The committee met in executive session to vote on its "
                   "recommendation."))
    assert got and "died when the session ended" in got["text"].lower(), got
    # Said once. These narratives already carry the ending, in the site's own
    # words, and a second paragraph repeating it reads as a stutter.
    for told in ("The bill died on the table when the session ended on "
                 "August 19, 2026, having been set aside and never taken back up.",
                 "It died when the session ended."):
        assert cs("Died when the session ended", stage(told)) is None, told
    # And not confused with a committee RECOMMENDING interim study, which is
    # the phrase "after the session ends" and is not an ending at all. An
    # earlier guard tested for "kill it" anywhere and matched every bill whose
    # committee recommended the chamber kill it -- suppressing the paragraph
    # on all 111 of them.
    rec = stage("The majority recommended that the House study it after the "
                "session ends, and the minority recommended that the House "
                "kill it, by a vote of 11-7.")
    assert cs("Died when the session ended", rec),         "a committee's recommendation was read as the bill's ending"
    # Killed is deliberately absent: the status page reports it for bills whose
    # docket already says what ended them.
    assert cs("Killed", stage("anything")) is None,         "Killed is back in the table, and it misfires on bills laid on the table"
    assert cs("Signed into law", stage("anything")) is None
    return "ok", "the ending is added when it is missing and not when it is not"


@check("data", "a hearing's sign-in count says whether it is that hearing's",
       needs=("build_site_v2",))
def _testimony_dated(build_site_v2):
    """30,108 people signed in against HB283. On which day matters.

    The database carries the hearing date with each sign-in, so the count can
    sit with the hearing it belongs to. Where it has the bill but not that
    date -- 50 of 2,122 docket hearing lines -- the whole-bill total is still
    true of the bill and is not true of that hearing, and the page has to say
    which of the two it is showing.
    """
    f = getattr(build_site_v2, "hearing_testimony", None)
    assert f, "build_site_v2 has no hearing_testimony"
    tdb = {"total": 300, "support": 100, "oppose": 200, "neutral": 0,
           "hearings": [{"date": "2026-02-03", "total": 120, "support": 40,
                         "oppose": 80, "neutral": 0}]}
    hear = {"raw": "Public Hearing: 02/03/2026 10:00 am LOB 302",
            "date": "2026-02-03"}
    got = f(hear, tdb, None)["testimony"]
    assert got["total"] == 120, f"the hearing shows {got['total']}, not its own 120"
    assert got.get("dated") is True, "a count for this hearing does not say so"

    other = {"raw": "Public Hearing: 05/05/2026 10:00 am LOB 302",
             "date": "2026-05-05"}
    got2 = f(other, tdb, None)["testimony"]
    assert got2["total"] == 300, got2["total"]
    assert not got2.get("dated"), (
        "a whole-bill total is presented as this hearing's count")

    # And a line that is not a hearing carries none of it.
    assert f({"raw": "Ought to Pass: MA VV 03/06/2026", "date": "2026-03-06"},
             tdb, None) == {}, "a floor vote was given a sign-in count"
    return "ok", "the hearing's own count, or the bill's, and it says which"


@check("narrative", "a ballot row gives up a member's party and district",
       needs=("fetch_rollcall_parties",))
def _ballot_row(fetch_rollcall_parties):
    """Real markup from the 2004 roll call a person found on 10 September.

    It is the only source on this disk that carries a PARTY for the people who
    voted before 2017 -- 773,506 ballots with none -- and it is addressed by
    what RollCallSummary already holds, sy and vs and lb, with the bill number
    and LSR the site's own link carries turning out to be ignored.

    Two things the fixture pins. The header row has five cells like every
    other row and is dropped by its party column not being a party, not by
    position. And "Adams, Jarvis" of Hillsborough sat in districts 02 and 31
    of the same chamber in the same year, so a member is (name, district) and
    never a name alone.
    """
    row = ('<tr><td width="36%">{who}</td><td width="20%">{party}</td>'
           '<td width="20%">{county}</td><td width="12%">{dist}</td>'
           '<td width="12%">{vote}</td></tr>')
    page = "<table>" + "".join([
        row.format(who="", party="<strong>Party</strong>",
                   county="<strong>County</strong>",
                   dist="<strong>District</strong>", vote="<strong>Vote</strong>"),
        row.format(who="\n\tAdams, Jarvis\n\n", party="Republican",
                   county="Hillsborough", dist="02", vote="Nay"),
        row.format(who="\nAdams, Jarvis\n", party="Republican",
                   county="Hillsborough", dist="31", vote="Nay"),
        row.format(who="\nAllison, David\n", party="Democrat",
                   county="Sullivan", dist="22", vote="Excused"),
    ]) + "</table>"
    got = fetch_rollcall_parties.parse(page)
    assert len(got) == 3, f"{len(got)} ballots; the header must not be one"
    assert [r["party"] for r in got] == ["R", "R", "D"], got
    # The county is written the way every other file on this disk writes it,
    # so a member from here sits beside one from former_members.json.
    assert got[0]["county"] == "Hills", got[0]
    assert got[2]["county"] == "Sull", got[2]
    assert [r["district"] for r in got[:2]] == ["02", "31"], (
        "two members share a name in one chamber; district is what parts them")
    # Excused is a ballot too: it is how the fullest roll call of a year names
    # almost the whole chamber rather than only those present.
    assert got[2]["vote"] == "Excused", got[2]
    return "ok", "three ballots, header dropped, two members sharing a name"


@check("narrative", "a past member's label gives up their name and district",
       needs=("past_members",))
def _past_member_label(past_members):
    """Real options from the General Court's own list of everyone who served.

    Two of these break the obvious parse. "Battles(-Peirce), Marjorie(Rock.
    18)" carries a parenthesis inside the SURNAME, so the district has to be
    read from the last bracket rather than the first -- a non-greedy match
    calls that member's district "-Peirce". And "Barnes, Jr., John(Dist. 17)"
    carries a suffix, so the name is not two comma-separated fields.

    A senator has a district and no county; a representative has both.
    """
    q = past_members.parse
    assert q("Rep. Vartanian, Elsie(Rock. 20)") == {
        "name": "Vartanian, Elsie", "chamber": "H", "county": "Rock",
        "district": "20", "party": ""}
    assert q("Sen. Blaisdell, Clesson(Dist. 10)") == {
        "name": "Blaisdell, Clesson", "chamber": "S", "county": "",
        "district": "10", "party": ""}
    assert q("Rep. Battles(-Peirce), Marjorie(Rock. 18)")["district"] == "18"
    assert q("Rep. Battles(-Peirce), Marjorie(Rock. 18)")["name"] == \
        "Battles(-Peirce), Marjorie"
    assert q("Sen. Barnes, Jr., John(Dist. 17)")["name"] == "Barnes, Jr., John"
    assert q("Rep. Albert, Russell(Straf 01)")["district"] == "01", \
        "a leading zero is how former_members.json writes a district"
    # No party is ever invented. The list does not carry one, and a member
    # named only from here votes without a party letter rather than with a
    # guessed one.
    assert all(q(s)["party"] == "" for s in (
        "Rep. Vartanian, Elsie(Rock. 20)", "Sen. Barnes, Jr., John(Dist. 17)"))
    assert q("not a legislator") == {}
    return "ok", "six real labels, two of which break the obvious parse"


@check("narrative", "a sponsor row gives up its bill, its LSR and its title",
       needs=("fetch_sponsors_by_member",))
def _sponsor_rows(fetch_sponsors_by_member):
    """Real markup from byAnyMember.aspx, kept because it is not what it looks like.

    Rendered, that page is a four-column table. In the HTML the four fields
    are DIVs inside a single <td>, and a parser written from the rendered
    shape finds nothing at all -- which is exactly what the first draft of
    this one did. The header row carries the same four divs, so rows are
    keyed on the presence of a billinfo link rather than on position.

    The LSR is the point of the whole route: Pastid is the LSR with the
    session year stuck on the end, so HB750 of 1989 joins data/bills.json on
    lsr_num 1171 rather than on a guess at which "Rep. Allard" is meant.
    """
    page = (
        '<table><tr><td><div class="container"><div class="row">'
        '<div class="col-sm-2 font-weight-bold">Year</div>'
        '<div class="col-sm-2 font-weight-bold">Bill #</div>'
        '<div class="col-sm-2 font-weight-bold">Status</div>'
        '<div class="col-sm font-weight-bold">Title</div>'
        '</div></div></td></tr>'
        '<tr><td><div class="container"><div class="row">'
        '<div class="col-sm-2">\n    1989\n</div>'
        '<div class="col-sm-2"><a href="billinfo.aspx?sy=1989&amp;'
        'Pastid=11711989&amp;id=99999" class="link-primary">HB750\n</a></div>'
        '<div class="col-sm-2">&nbsp;SIGNED BY GOVERNOR</div>'
        '<div class="col-sm"><b>title:</b>&nbsp;(New Title) establishing a '
        'redevelopment commission relative to Pease Air  Force Base.</div>'
        '</div></div></td></tr></table>')
    rows = fetch_sponsors_by_member.parse_rows(page)
    assert len(rows) == 1, f"{len(rows)} rows; the header must not parse as a bill"
    r = rows[0]
    assert r["bill"] == "HB750", r
    assert r["year"] == "1989", r
    assert r["lsr"] == "1171", ("Pastid is the LSR with the year on the end, "
                                "and the LSR is the join key: " + repr(r))
    assert r["status"] == "SIGNED BY GOVERNOR", r
    assert r["title"].startswith("(New Title) establishing"), r
    assert "title:" not in r["title"], r
    return "ok", "one row, header skipped, LSR 1171 off the link"


@check("narrative", "the committee of referral is read out of a docket line",
       needs=("referrals",))
def _referral(referrals):
    """Every string below is a real description from db/Docket.psv.

    Five terms had no committee at all until the docket was read for one --
    8,525 bills whose page named no committee -- so this is the parser that
    put a committee on a quarter of the archive, and the shapes it has to
    survive span 1989 to 2015 and four clerks' habits.
    """
    c = referrals.committee
    assert c("INTRODUCED AND REF TO EXEC & ADMIN     HJ 13 ,P 138") == \
        "Executive Departments and Administration"
    assert c("Introduced 1/4/2012 and Referred to Judiciary; HJ 11, PG. 183") == \
        "Judiciary"
    assert c("PASSED AND REF TO FINANCE VV; HJ35,P943") == "Finance"
    assert c("RE-REFERRED TO ENV & AGRIC VV; HJ53B,P1179") == \
        "Environment and Agriculture"
    assert c("Introduced and ref to Labor, Industrial and Rehabilitative "
             "Services   HJ 7, pg 341") == "Labor, Industrial and Rehabilitative Services"
    # A disposition, not a committee. "Refer to Interim Study" is what a
    # committee RECOMMENDS; reading it as a referral would invent a committee
    # of that name for 434 bills.
    assert c("Committee Report: Refer to Interim Study") == ""
    # "Rereferred to Committee" is back to the one it is already in.
    assert c("Rereferred to Committee, MA, VV; SJ 20, P 543") == ""
    # The shout is unshouted before the ampersand is spelled, or the
    # lower-case "and" drops it below the 90% that triggers unshouting.
    assert c("INTRODUCED AND REF TO WAYS & MEANS") == "Ways and Means"
    # This line asserted "Judiciary and F L" for half a day, which was the
    # right answer while it was: nothing in the docket or in any bill's text
    # spells that committee out, and a plausible expansion of a committee's
    # name is still an invented one. Then the General Court's own key to its
    # docket turned up -- docket_abbrev.json -- and JUD is Judiciary and
    # Family Law. The expectation moved because the evidence did, and the
    # rule that produced the cautious answer is unchanged.
    assert c("INTRODUCED AND REF TO JUDICIARY & F L") == "Judiciary and Family Law"
    # Still abbreviated, because the key does not cover these either.
    assert c("INTRODUCED AND REF TO CORR & CJ") == "Corr and Cj"
    return "ok", "seven real docket lines, and two that name no committee"


@check("data", "an archived bill's committee came from a source that has one",
       needs=("referrals",))
def _referral_coverage(referrals):
    """The five terms before 1999 had 0 committees and now have 95-98%.

    A regression here does not raise anything: it silently returns the site
    to a 1989 bill that names no committee, which is what it looked like for
    a year.
    """
    f = Path("data/bills.json")
    if not f.exists():
        return "skip", "no data/bills.json"
    bills = json.loads(f.read_text(encoding="utf-8"))
    thin = []
    for term in ("1989-1990", "1991-1992", "1993-1994", "1995-1996",
                 "1997-1998"):
        bs = bills.get(term) or {}
        if not bs:
            continue
        got = sum(1 for r in bs.values()
                  if r.get("house_committee") or r.get("senate_committee"))
        if got < len(bs) * 0.85:
            thin.append(f"{term} {got}/{len(bs)}")
    assert not thin, ("the docket gives 95-98% of these terms a committee; "
                      "now: " + ", ".join(thin))
    return "ok", "the five pre-1999 terms all above 85%"


@check("data", "a solved voter is one person, and nobody else's")
def _solved_voters():
    """member_party.json pins 38 voters by constraint rather than by roster.

    The method is measured in fetch_rollcall_parties.solve: 286 people whose
    answer was already known were hidden and it returned 286 right and 0
    wrong. This is the standing guard on the file that came out of it, because
    the failure it would cause is silent -- one member's ballots filed under
    another's name, which is the same failure "every voter in the record is
    one person" exists to catch, arriving from a different direction.

    Two things must hold. A solved entry must not claim a person the General
    Court's own list already names -- if it does, one of the two is wrong and
    the roster is the better witness. And no two employeenos may claim the
    same name and district, because that is two people wearing one identity.
    """
    f = Path("member_party.json")
    if not f.exists():
        return "skip", "no member_party.json"
    party = json.loads(f.read_text(encoding="utf-8"))
    solved = {k: v for k, v in party.items() if v.get("source") == "solved"}
    if not solved:
        return "ok", "nothing solved"
    try:
        import past_members
        roster = past_members.roster()
    except Exception:
        roster = {}
    clash = [k for k in solved if k in roster]
    assert not clash, (
        f"{len(clash)} solved voter(s) are already named by the General "
        f"Court's own list, which is the better witness: {clash[:4]}")
    seen = {}
    dupe = []
    for mid, rec in solved.items():
        key = (str(rec.get("name", "")).lower(),
               str(rec.get("district", "")).lstrip("0"))
        if key in seen:
            dupe.append(f"{seen[key]} and {mid} both claim {key}")
        seen[key] = mid
    assert not dupe, ("two member numbers claim one person: " + "; ".join(dupe[:3]))
    return "ok", f"{len(solved)} solved voters, each one person and only theirs"


@check("data", "a hearing date belongs to the bill it sits on")
def _hearing_is_the_bills_own():
    """The archive's bill list will hand you another bill's hearing.

    Asked for session year 2021 or 2022, the General Court's legacy search
    fills the date of "Next/Last Hearing" from the CURRENT session's record
    with the same legislationID -- an id that restarts every term. 1,485 of
    that term's 1,752 bills came back with a hearing in 2025 or 2026, and
    1,481 of them match the current bill's hearing to the minute against the
    General Court's own database. The remaining 93 dates are inside the term
    and are conference-committee meetings, not hearings.

    Nothing renders this field today, which is exactly why it needs a check:
    the first page to read it would publish a 2025 hearing on a 2021 bill.
    """
    f = Path("data/bills.json")
    if not f.exists():
        return "skip", "no data/bills.json"
    bills = json.loads(f.read_text(encoding="utf-8"))
    undated, astray, dropped = [], [], 0
    for term, bs in bills.items():
        try:
            lo, hi = (int(x) for x in term.split("-"))
        except ValueError:
            continue
        for bid, rec in bs.items():
            h = (rec.get("hearing") or "").strip()
            if not h:
                dropped += 1
                continue
            m = re.search(r"(?:19|20)\d{2}", h)
            if not m:
                undated.append(f"{term} {bid} {h!r}")
            elif not lo <= int(m.group(0)) <= hi:
                astray.append(f"{term} {bid} {h!r}")
    assert not undated, (f"{len(undated)} hearing values carry no date, e.g. "
                         + "; ".join(undated[:3]))
    assert not astray, (f"{len(astray)} hearings fall outside their own term, "
                        "which means they belong to another bill of that "
                        "number: " + "; ".join(astray[:3]))
    t2122 = bills.get("2021-2022") or {}
    kept = [b for b, r in t2122.items() if (r.get("hearing") or "").strip()]
    assert not kept, ("2021-2022 hearings come from that term's docket, not "
                      f"from the bill list: {len(kept)} kept, e.g. {kept[:3]}")
    return "ok", f"{dropped:,} empty, none dated outside its term"


@check("data", "a bill the governor signed says so")
def _signed():
    if not (Path("narratives.json").exists() and Path("build_site_v2.py").exists()):
        return "skip", "narratives.json or build_site_v2.py not here"
    bs = imp("build_site_v2")
    assert bs, "build_site_v2.py will not import"
    nvf = json.loads(Path("narratives.json").read_text(encoding="utf-8"))
    # {term: {bill: record}}. This is a check on the whole record, so it reads
    # every term rather than one.
    nv = {b: r for byb in nvf.values() for b, r in byb.items()}
    # The clerk writes it two ways -- "Signed by Governor Ayotte 7/10/2026" and
    # "Signed by the Governor on 7/10/2026" -- and the pattern knew only the
    # first. 233 of the 632 signatures on the record went unrecognised, and the
    # status page carries no governor field at all for those bills, so they
    # kept whatever they had been before: "Passed one chamber" for 137,
    # "Passed, awaiting the governor" for 82, "In committee" for nine and
    # "Killed" for five bills that are law.
    signed = getattr(bs, "SIGNED_RE", None)
    assert signed is not None, ("build_site_v2 has no SIGNED_RE, so the two "
                               "spellings of the signature are not both read")
    both = {"signed by governor": 0, "signed by the governor": 0}
    missed = []
    for bill, v in nv.items():
        text = " ".join(e.get("raw", "") for e in v.get("events", []))
        m = re.search(r"signed by (?:the )?governor", text, re.I)
        if not m:
            continue
        both[m.group(0).lower()] = both.get(m.group(0).lower(), 0) + 1
        if not signed.search(text.lower()):
            missed.append(bill)
    assert not missed, (f"{len(missed):,} bills the docket says were signed are "
                        f"not matched, e.g. {missed[:5]}")
    assert all(both.values()), (
        f"only one spelling is present, so this check proves nothing: {both}")
    return "ok", (f"{sum(both.values()):,} signatures, "
                  + " and ".join(f"{v:,} {k!r}" for k, v in both.items()))


@check("data", "a sponsor is named the same way whether or not they still serve")
def _sponsor_names():
    if not Path("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    bs = imp("build_site_v2")
    assert bs, "build_site_v2.py will not import"
    # The three ways a sponsor's name reaches the join. The status page writes
    # the party letter in lower case, and surnames are not always one word.
    for raw, want in (("Howard Pearl (r)", "pearl, howard"),
                      ("Rep. Jodi Nelson (R - Rock 13)", "nelson, jodi"),
                      ("Nelson, Jodi", "nelson, jodi")):
        got = bs.sort_name(raw)
        assert got == want, f"sort_name({raw!r}) is {got!r}, expected {want!r}"
    # name_key pairs the first and last word, so a surname of any length meets
    # its own "Last, First" spelling.
    for a, b in (("Rebecca Perkins Kwoka", "Perkins Kwoka, Rebecca"),
                 ("Erica de Vries", "de Vries, Erica"),
                 ("Matt Sabourin dit Choiniere", "Sabourin dit Choiniere, Matt"),
                 ("Howard Pearl (r)", "Pearl, Howard")):
        ka, kb = bs.name_key(a), bs.name_key(b)
        assert ka and ka == kb, f"name_key({a!r})={ka!r} != name_key({b!r})={kb!r}"
    # Both spellings of a county abbreviation would let a reader tell which
    # members had left, because only they took the second one.
    assert not [v for v in bs.COUNTY_ABBR.values() if v.endswith(".")],         f"county abbreviations still carry a trailing point: {bs.COUNTY_ABBR}"
    return "ok", ("surnames of any length, either spelling, and the party letter "
                  "in either case")


@check("data", "the volume a docket line cites is kept, not cleaned away")
def _cite_survives():
    if not (Path("Docket.txt").exists() and Path("narrative.py").exists()):
        return "skip", "Docket.txt or narrative.py not here"
    nv = imp("narrative")
    assert nv, "narrative.py will not import"
    raw = cited = 0
    for rows in nv.parse_docket("Docket.txt").values():
        for r in rows:
            raw += 1
            if re.search(r"\b(HJ|SJ|HC|SC)\s*\d", r["desc"]):
                cited += 1
    assert cited > raw * 0.5, (f"only {cited:,} of {raw:,} docket rows cite a "
                               "journal or calendar; that is too few to be true")
    # clean() removes the citation before any pattern sees the line, and has
    # to: the hearing pattern's venue group would otherwise swallow "SC 4".
    # For two terms it was removed and never recorded anywhere else, so
    # _cite() in build_site_v2 -- which exists for no other purpose than to
    # turn this into a link to the published page -- returned nothing on every
    # event of every bill, and the Documents tab was quietly short 12,970
    # citations. A build that publishes nothing still exits zero.
    kept = 0
    for bill, rows in list(nv.parse_docket("Docket.txt").items())[:400]:
        for e in nv.build(bill, rows)["events"]:
            if e.get("cite"):
                kept += 1
    assert kept, ("no event kept its citation; cite_of() is not reaching "
                  "build(), and the Documents tab will publish no source links")
    return "ok", (f"{cited:,} of {raw:,} rows cite a volume; "
                  f"{kept:,} kept across the first 400 bills")


@check("build", "a fetch writes the term it was asked for")
def _fetch_writes_its_term():
    """The run that made 1,996 requests and saved none of them.

    fetch_bill_status.py keeps the whole file in `out_all` and this term's
    slice in `out`, so a run over one term cannot drop another. `out_all[term]
    = out` sat before the loop, which was right until an empty term stopped
    being written: the term was then popped while `out` was still empty and
    never reattached, so every write produced a file that did not reference
    the dict the loop was filling.

    It exited zero. The console said "1,996 bills of 2023-2024 -> ...". The
    file had no 2023-2024 in it, and the only reason nothing was lost is that
    the pages were already cached.

    This runs the real script over a cache of one page, with no network -- the
    parser skips a bill it has no cached page for -- and asks the only question
    that matters: is what it fetched in the file, and is the other term still
    there beside it.
    """
    here = Path(".").resolve()
    if not (here / "fetch_bill_status.py").exists():
        return "skip", "fetch_bill_status.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "data").mkdir()
        (root / "data" / "bills.json").write_text(json.dumps({
            "2023-2024": {"HB100": {"lsr_year": "2024", "lsr_num": "1234",
                                    "title": "", "bill": "HB100"}},
            "2025-2026": {"HB100": {"lsr_year": "2026", "lsr_num": "9999",
                                    "title": "the current HB100", "bill": "HB100"}},
        }), encoding="utf-8")
        (root / "data" / "sponsors.json").write_text(json.dumps(
            {"2025-2026": {"HB100": []}}), encoding="utf-8")
        # The other term, already on file. It must still be there afterwards.
        (root / "bill_status.json").write_text(json.dumps({
            "2025-2026": {"HB100": {"title": "the current HB100.",
                                    "gen_status": "IN COMMITTEE"}}}),
            encoding="utf-8")
        # One cached page, named the way the fetcher names them.
        cache = root / "status_pages"
        cache.mkdir()
        (cache / "2024_1234_HB100.html").write_text(
            "<html><body><table><tr><td>Bill Title: an entirely different bill "
            "of the same number</td></tr><tr><td>LSR#: 1234</td></tr>"
            "<tr><td>Body: H</td></tr><tr><td>Gen Status: SIGNED BY GOVERNOR"
            "</td></tr></table></body></html>", encoding="utf-8")

        r = _run(
            [sys.executable, str(here / "fetch_bill_status.py"),
             "--reparse", "--term", "2023-2024", "--data", "data",
             "--out", "bill_status.json", "--cache", "status_pages"],
            cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]

        got = json.loads((root / "bill_status.json").read_text(encoding="utf-8"))
        assert "2023-2024" in got, (
            "the term it was asked to fetch is not in the file it wrote. It "
            f"wrote: {sorted(got)}. The console will have said it saved them.")
        assert got["2023-2024"].get("HB100", {}).get("title"), (
            "the term is there and the bill it parsed is not: "
            f"{got['2023-2024']}")
        assert "different bill" in got["2023-2024"]["HB100"]["title"], (
            "the archived bill took a title from somewhere other than its own "
            f"cached page: {got['2023-2024']['HB100']['title']!r}")
        assert got.get("2025-2026", {}).get("HB100"), (
            "the term that was NOT being fetched was dropped on the way out")
        assert got["2025-2026"]["HB100"]["title"] == "the current HB100.", (
            "the term that was not being fetched was overwritten")
        return "ok", ("the fetched term is written and the other term "
                      "survives it")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("files", "a writer of a shared file reads it before writing it")
def _writers_merge():
    """former_members.json went from 675 entries to 3 on 7 September.

    fetch_members_db.py fills it from the General Court's legislators table in
    one SELECT; resolve_members.py deduces the handful that table has no row
    for, from the roll call pages. The second wrote its own results over the
    whole file. Everything the first had found was gone, and the only reason
    it was recoverable is that the SELECT can be run again.

    This is the same failure as the manifest losing its 35 hand-marked times,
    twice, and it is worth a structural check rather than a memory: a script
    that WRITES one of these files must also READ it. Reading is not proof of
    merging, but not reading is proof of replacing, and that is the case that
    has actually happened three times.
    """
    shared = ("former_members.json", "bill_status.json", "bill_text.json",
              "testimony_db.json", "narratives.json", "rollcalls.json")
    bad = []
    for f in sorted(Path(".").glob("*.py")):
        if f.name.startswith(("probe_", "test_")):
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        for name in shared:
            if name not in src:
                continue
            # Crude on purpose: the question is whether the file is opened for
            # reading anywhere in the script, not how.
            writes = ("write_text" in src or "json.dump" in src
                      or 'open(' in src and '"w"' in src)
            reads = ("read_text" in src or "json.load" in src
                     or ".exists()" in src)
            if writes and not reads:
                bad.append(f"{f.name} writes {name} and never reads it")
    assert not bad, "; ".join(bad)
    return "ok", f"{len(shared)} shared files, every writer of one reads it first"


@check("data", "no sentence has a hole where a date should be")
def _no_empty_dates():
    """A sentence that says "on" and then stops has lost a fact silently.

    "The governor signed it on , making it Chapter 141 of the session laws."
    That was every one of the 1,254 signatures in the record and 49 of the 69
    vetoes -- every bill that became law -- because the clerk writes the
    governor's surname between the title and the date and the pattern allowed
    only for the title. The chapter and the effective date came through, so
    the sentence read as prose with a gap in it rather than as a parser that
    had failed, and nothing else here could see it: the field was present, the
    narrative was long, the page rendered.

    Any sentence anywhere with "on" or "since" running straight into a comma
    or a full stop is the same shape, so this looks for the shape rather than
    for the governor.
    """
    root = Path("site/bills")
    if not root.exists():
        return "skip", "no bill JSON built"
    gap = re.compile(r"\b(?:on|since|until|through)\s+[.,]")
    n, bad = 0, []
    for f in sorted(root.rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        n += 1
        text = " ".join([d.get("narrative") or ""]
                        + [x.get("text") or "" for x in d.get("stages") or []])
        m = gap.search(text)
        if m:
            bad.append(f"{d.get('id')} ({d.get('year')}): "
                       f"...{text[max(0, m.start() - 46):m.end() + 12]}...")
    assert not bad, (f"{len(bad)} of {n:,} bills have a sentence with an empty "
                     f"date: {'; '.join(bad[:2])}")
    return "ok", f"{n:,} bills, no sentence stops where a date should be"


@check("data", "a fetched schedule still has bills in it")
def _schedule():
    """The schedule is the only thing on this site that is about the future.

    It comes from a JSON service and then one page per event, and the page is
    where the bills are. If that page's shape changes, the fetch still
    succeeds, the events still arrive, and every one of them simply has no
    bills -- which is indistinguishable from a quiet fortnight unless
    something says otherwise.

    So: if a schedule has been fetched at all, at least one event must name a
    bill, and every bill slot must carry a time and a bill number. Skipped
    entirely when no schedule is on disk, because not having fetched one is
    not a fault.
    """
    p = Path("schedule.json")
    if not p.exists():
        return "skip", "no schedule fetched"
    try:
        events = json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        raise AssertionError("schedule.json is not readable JSON")
    if not events:
        return "skip", "the schedule is empty"
    slots = [b for e in events for b in (e.get("bills") or [])]
    named = [e for e in events if e.get("bills")]
    assert named, (
        f"{len(events)} events fetched and not one names a bill. That is the "
        "event page's shape having changed, not an empty schedule -- look at "
        "one in schedule_pages/ before trusting it.")
    bad = [b for b in slots if not (b.get("time") and b.get("bill"))]
    assert not bad, f"{len(bad)} bill slot(s) have no time or no bill: {bad[:2]}"
    kinds = {e.get("kind") or e.get("colour") for e in events}
    unmapped = {k for k in kinds if k.startswith("#")}
    assert not unmapped, (
        f"the service sent {len(unmapped)} colour(s) the legend does not map: "
        f"{sorted(unmapped)}. The colour IS the kind, so an unmapped one is a "
        "meeting whose kind this site does not know.")
    return "ok", (f"{len(events)} events, {len(named)} naming bills, "
                  f"{len(slots)} bill slots, every kind mapped")


@check("data", "the calendar and the docket agree about a hearing")
def _calendar_meetings():
    """The calendar says who is hearing what, where, and when.

    It is the only source that can answer "what is Education hearing on
    Monday" -- the docket answers per bill and cannot be asked that way -- and
    it is also the legal notice, so its publication date is when the window
    for public testimony opens.

    Neither of those is worth anything if the parse is wrong, and the parse
    reads a two-column PDF whose columns do not always line up. So it is
    scored on every run against the docket, which nothing here wrote: for a
    hearing both sources know, do they call it the same kind of meeting, at
    the same time, in the same room?

    The floors are set below the measurement of 8 September (kind 96%, room
    100% of the rows where both name one) so that a regression fails and an
    improvement does not.
    """
    try:
        import calendar_meetings as CM
    except ImportError:
        return "skip", "calendar_meetings is not here"
    if not Path("calendars").exists():
        return "skip", "no calendars on disk"
    rows = CM.load("H") + CM.load("S")
    if not rows:
        return "skip", "no calendar produced a meeting"
    hearings = [r for r in rows
                if r["kind"] == "public hearing" and r["bill"] and r["date"]]
    assert len(hearings) > 5000, (
        f"only {len(hearings):,} public hearings parsed out of the calendars; "
        "8 September measured 7,293, and a collapse here means a format the "
        "parser stopped recognising rather than a quiet session")
    # A bill's own line is never a committee -- see the calendar check that
    # says so on printed lines. This is the same claim over every file.
    lead = re.compile(r"^(?:Hb|Sb|Hr|Sr|Hcr|Scr|Cacr|Hjr)\s*\d", re.I)
    billcom = [r for r in rows if lead.match(r["committee"] or "")]
    assert not billcom, (
        f"{len(billcom):,} calendar rows name a bill as their committee, e.g. "
        f"{billcom[0]['bill']} on {billcom[0]['date']} heard by "
        f"{billcom[0]['committee']!r} in {billcom[0]['calendar']}: a bill's line "
        "was read as a header again")

    # A notice cannot follow the thing it notices. All 7,293 were published on
    # or before the day of the hearing when this was written, median five days
    # ahead, so any exception is a parse fault rather than a late clerk.
    import datetime
    late = [r for r in hearings if r["noticed"] and
            datetime.date.fromisoformat(r["noticed"])
            > datetime.date.fromisoformat(r["date"])]
    assert not late, (
        f"{len(late)} hearing(s) are noticed by a calendar published after the "
        f"hearing itself, e.g. {late[0]['bill']} heard {late[0]['date']} and "
        f"announced {late[0]['noticed']}")

    got = CM.check(rows)
    known = int(str(got["the docket also knows"]).replace(",", ""))
    if known < 500:
        return "ok", (f"{len(hearings):,} public hearings parsed; the docket "
                      "holds too few of them to score against")
    kind = int(str(got["kind agrees"]).split(" of ")[0].replace(",", ""))
    room_s = str(got["room agrees, where both state one"])
    room = int(room_s.split(" of ")[0].replace(",", ""))
    room_n = int(room_s.split(" of ")[1].split(" ")[0].replace(",", ""))
    assert kind / known >= 0.93, (
        f"the calendar and the docket agree about the kind of meeting on only "
        f"{kind / known:.0%} of {known:,}; it was 96% on 8 September. "
        f"{got['kind disagreements'][:3]}")
    assert room_n == 0 or room / room_n >= 0.99, (
        f"they disagree about the room on {room_n - room} of {room_n:,}; "
        f"three was the whole of it on 8 September. {got['room disagreements'][:3]}")
    return "ok", (f"{len(hearings):,} public hearings out of the calendars, "
                  f"{kind:,} of {known:,} agreeing with the docket on kind, "
                  f"{room:,} of {room_n:,} on room")


@check("data", "every published link asks for something the source serves")
def _links_answer():
    """A link is a claim that something is there.

    billText.aspx takes txtFormat=html and txtFormat=pdf, and only one of them
    exists. The scrape minted the pdf shape for all 4,230 bills, and every one
    of them answered

        error: condensedbillno is neither a DataColumn nor a DataRelation for
        table text.

    which renders as a blank page. The status page's own link, in all 2,234
    cached copies of it, is txtFormat=html. Nothing here can tell whether an
    address answers -- that costs a request to somebody else's server -- so
    this checks the one thing it can: that no published address uses a
    parameter value the General Court was never observed to serve.
    """
    root = Path("site/bills")
    if not root.exists():
        return "skip", "no bill JSON built"
    bad, n, links = [], 0, 0
    for f in sorted(root.rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        n += 1
        urls = [x.get("url", "") for x in (d.get("documents") or [])]
        urls.append(d.get("text_url", ""))
        for u in urls:
            if not u:
                continue
            links += 1
            if "txtFormat=pdf" in u:
                bad.append(f"{d.get('id')} links to txtFormat=pdf")
            elif "billText.aspx" in u and "sy=" not in u:
                bad.append(f"{d.get('id')} links to billText.aspx with no "
                           "session year")
    if not n:
        return "skip", "no bill carries a document"
    assert not bad, (f"{len(bad)} link(s) ask for something no page serves: "
                     f"{'; '.join(bad[:3])}")
    return "ok", f"{links:,} published links across {n:,} bills, none malformed"


@check("data", "no fiscal figure sits under a year nobody put it there")
def _fiscal():
    """A fiscal table is the one place on this site where a wrong answer would
    look most authoritative.

    The note arrives from the PDF as a single column -- four fiscal years and
    four figures with nothing saying which belongs to which -- so the table is
    rebuilt here. A row is laid out one figure per year ONLY where it has
    exactly one figure per year. Where it has fewer, as most do, the row spans
    the table instead, because which years the second figure covers is not
    stated and putting it under FY 2026 would be inventing it.

    This asserts that rule held over every note, which is the difference
    between a table and a guess with borders on it.
    """
    root = Path("site/bills")
    if not root.exists():
        return "skip", "no bill JSON built"
    n, cells, spans, raw, bad = 0, 0, 0, 0, []
    for f in sorted(root.rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        note = ((d.get("billtext") or {}).get("fiscal")) or None
        if not note:
            continue
        n += 1
        for t in note.get("tables", []):
            if "raw" in t:
                raw += 1
                continue
            years = len(t.get("years") or [])
            if not years:
                bad.append(f"{d.get('id')} has a table with no years")
                continue
            for r in t.get("rows", []):
                if r.get("span"):
                    spans += 1
                elif len(r.get("values") or []) != years:
                    bad.append(f"{d.get('id')}: {r.get('label')!r} lays "
                               f"{len(r.get('values') or [])} figures across "
                               f"{years} years")
                else:
                    cells += years
    if not n:
        return "skip", "no bill carries a parsed fiscal note"
    assert not bad, (f"{len(bad)} row(s) would place a figure under a year the "
                     f"source did not: {'; '.join(bad[:3])}")
    return "ok", (f"{n:,} fiscal notes, {cells:,} figures under a stated year, "
                  f"{spans:,} rows spanning, {raw} tables left as their lines")


@check("data", "a quoted veto message is whole, attributed and citable")
def _veto_messages():
    """The site quotes the governor. That has to be exactly right.

    The messages come out of the House calendar PDFs, where pdftotext leaves a
    running page header at every page break -- "13 JUNE2025HOUSERECORD 3" --
    and justification splits words across lines. Eleven of the 34 messages
    carried one or the other before those were dealt with, including one that
    read "...to and from these schools 13 JUNE2025HOUSERECORD 3 would place an
    undue burden on working families."

    A garbled quotation with a citation on it is worse than no quotation,
    which is the same reason this site does not quote captions. So: no page
    furniture, no split words, an author, and a link to the calendar it was
    printed in.

    NOT a date. Nine of Ayotte's Senate messages state none -- not in the
    signature and not in the text -- and the page shows none for those rather
    than borrowing the docket's, which is a different fact: the day the veto
    reached the chamber, not the day it was signed. A date is required to be
    well formed if it is there, and not required to be there.
    """
    root = Path("site/bills")
    if not root.exists():
        return "skip", "no bill JSON built"
    # EXACTLY two stops, not three. The governor quotes a letter in
    # HB475's message with a real ellipsis in it, and a pattern reading
    # "..." as a defect flags the site's most careful quotation as its
    # worst.
    junk = re.compile(r"HOUSERECORD|SENATERECORD|\x0c|(?<!\.)\.\.(?!\.)"
                      r"|\w- \w|  ")
    n, bad = 0, []
    for f in sorted(root.rglob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        v = d.get("veto_message")
        if not v:
            continue
        n += 1
        text = " ".join(v.get("text") or [])
        m = junk.search(text)
        if m:
            bad.append(f"{d.get('id')} carries {m.group(0)!r}")
        elif len(text) < 80:
            bad.append(f"{d.get('id')} is {len(text)} characters, not a message")
        elif not v.get("governor"):
            bad.append(f"{d.get('id')} names no author")
        elif v.get("date") and not re.fullmatch(r"\d{4}-\d\d-\d\d",
                                                v["date"]):
            bad.append(f"{d.get('id')} has a date of {v['date']!r}")
        elif not (v.get("source") or {}).get("url"):
            bad.append(f"{d.get('id')} cites no calendar")
    if not n:
        return "skip", "no bill carries a veto message"
    assert not bad, (f"{len(bad)} of {n} veto messages are not fit to quote: "
                     f"{'; '.join(bad[:3])}")
    return "ok", f"{n} veto messages, each whole, attributed and citable"


@check("data", "the passage rail agrees with the outcome it sits beside")
def _rail():
    """Four stops drawn on every card, and each one is a claim.

    The rail is the site's one piece of ornament and it is made of facts, so
    it must not be able to disagree with the status chip six pixels above it.
    A bill that became law has to show the Law stop passed; one that was
    killed or vetoed has to show it stopped; and a bill cannot have got
    through a chamber it never reached.

    "pppp" -- passed the House, passed the Senate, reached the governor,
    became law -- should also come out at exactly the number of bills the
    site independently calls law.
    """
    idx = Path("site/index.json")
    if not idx.exists():
        return "skip", "index.json is not built"
    rows = json.loads(idx.read_text(encoding="utf-8"))
    bad, n, laws, pppp, vetoes = [], 0, 0, 0, 0
    for b in rows:
        p = b.get("passage") or ""
        kind = b.get("kind") or ""
        if kind == "law":
            laws += 1
        if not p:
            continue
        n += 1
        if p[0] not in "HS" or set(p[1:]) - set("phx-") \
                or len(p) not in (3, 5):
            bad.append(f"{b.get('id')}: {p!r} is not a chamber and its stops")
            continue
        # A resolution has one chamber and two stops -- itself, and whether it
        # was adopted. It never crosses, never reaches a governor and never
        # becomes law, so none of the four-stop rules below apply to it.
        if len(p) == 3:
            if p[1] != p[2]:
                bad.append(f"{b.get('id')} is a resolution and its two stops "
                           f"disagree: {p!r}")
            continue
        if p[1:] == "pppp":
            pppp += 1
        # The first character is the chamber the bill started in, and the four
        # after it are the stops in the order it travelled them.
        h, se, g, law = p[1:]
        if kind == "law" and law != "p":
            bad.append(f"{b.get('id')} became law and its Law stop is {law!r}")
        if kind in ("done", "veto") and law != "x":
            bad.append(f"{b.get('id')} is {kind} and its Law stop is {law!r}")
        # A bill is never AT the law stop. "here now" is a 3px ring that reads
        # as active, and it was being drawn on the outcome of 175 bills that
        # were stalled -- laid on the table, or waiting on a concurrence that
        # never came, in a chamber that had finished sitting.
        if law == "h":
            bad.append(f"{b.get('id')} shows the Law stop as 'here now', and "
                       "no bill is ever at the law stop")
        if se == "p" and h == "-":
            bad.append(f"{b.get('id')} passed a Senate it reached without a House")
        if g != "-" and "-" in (h, se) and not b.get("archived"):
            # A bill reaches the governor through both chambers.
            bad.append(f"{b.get('id')} reached the governor as {p!r}")
        # A VETO IS THE GOVERNOR STOPPING THE BILL, and for a while the rail
        # said the opposite: the governor stop was marked passed on the
        # strength of the bill having ARRIVED there, so all 68 vetoed bills
        # drew a green check on the governor who vetoed them. The chambers
        # keep their checks -- the House that failed to override HB 1442 by
        # 165-149 had passed the bill in May, and a failed override is not a
        # chamber rejecting a bill.
        if "veto" in (b.get("status") or "").lower():
            vetoes += 1
            if g != "x":
                bad.append(f"{b.get('id')} was vetoed and its Governor stop "
                           f"is {g!r}")
            if "x" in (h, se):
                bad.append(f"{b.get('id')} reached a governor who vetoed it "
                           f"through a chamber the rail crosses: {p!r}")
    if not n:
        return "skip", "no bill carries a passage"
    assert not bad, (f"{len(bad)} of {n:,} rails disagree with the record: "
                     f"{'; '.join(bad[:3])}")
    # The Law stop and the word "law" are the same fact counted two ways.
    # Not "pppp": nine bills became law over a veto, and their rail reads
    # ppxp -- both chambers, the governor against, law anyway. That is the
    # story, and requiring a clean run would have forbidden telling it.
    #
    # AMONG THE BILLS THAT CARRY A PASSAGE, and only those. The archived
    # terms arrived with statuses and no dockets, so 29,485 bills are called
    # law, study or done on the strength of a status field while having no
    # stages to draw a rail from -- and counting those made a check that was
    # exactly right read as 1,273 against 12,127. A rail cannot be required
    # of a bill whose sequence of events is not on this disk.
    withp = [b for b in rows if b.get("passage")]
    laws_p = sum(1 for b in withp if (b.get("kind") or "") == "law")
    ends_law = sum(1 for b in withp if (b["passage"] or "")[4:5] == "p")
    assert ends_law == laws_p, (
        f"{ends_law:,} rails end at law and {laws_p:,} bills with a rail are "
        "called law. Those are the same bills counted two ways and they have "
        "to match.")
    return "ok", (f"{n:,} rails, {pppp:,} of them the whole way, "
                  f"{vetoes} vetoed and crossed at the governor")


@check("data", "a committee's stated purpose is the rule, not the page around it")
def _duty_is_a_duty():
    """A quotation must end where the quoted text ends.

    The duty is read off gc.nh.gov's committee pages, where it runs straight
    into the site's own navigation with no punctuation between: "...such other
    matters as may be referred to it. HELPFUL LINKS Committees of Conference
    Redistricting Ethics Committee ... 107 North Main Street | Concord, NH
    03301." All 26 published that, under a heading saying it was House Rule 31.

    This is the worst shape of error the site can make -- not a missing fact
    but a wrong one, presented as a quotation from the rules -- and it is
    invisible to every other check here, because a longer string is not an
    empty one and the page renders perfectly.
    """
    root = Path("site/committee")
    if not root.exists():
        return "skip", "no committee JSON built"
    junk = ("HELPFUL LINKS", "DOCUMENTS & MEDIA", "OTHER RESOURCES",
            "Concord, NH", "Copyright", "Driving Directions", "Help Desk")
    n, bad = 0, []
    for f in sorted(root.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        pur = d.get("purpose") or {}
        text = (pur.get("text") or "").strip()
        if not text:
            continue
        n += 1
        hit = next((x for x in junk if x in text), "")
        if hit:
            bad.append(f"{d.get('code')} carries {hit!r}")
        elif not text.endswith("."):
            bad.append(f"{d.get('code')} does not end in a full stop")
        elif len(text) < 60:
            bad.append(f"{d.get('code')} is {len(text)} characters, not a duty")
    if not n:
        return "skip", "no committee states a purpose yet"
    assert not bad, (f"{len(bad)} of {n} stated purposes are not just the "
                     f"rule's text: {'; '.join(bad[:3])}")
    return "ok", f"{n} committees quote a rule, and only the rule"


@check("data", "a proceeding starts at the same moment on both pages")
def _one_start():
    """The committee page and the bill page must not disagree about a time.

    They did, by four hours. The bill page draws the boundary the chair
    stated, found by segment_markers from the captions; the committee page was
    drawing proceedings.csv's predicted_offset, which is the schedule guess --
    the meeting began at ten and this was third on the agenda. SB430's
    executive session on 4 May 2026 was 14557s on one page and 1774s on the
    other, and neither said which to believe.

    Two paths to one number is how they came to differ, so the committee page
    reads the bill's own station now and there is one path. This asserts that
    stays true, because the failure is silent: both pages render, both look
    confident, and only somebody opening the recording finds out.
    """
    # IT READ THE WRONG PLACE FOR TWO DAYS AND PASSED. It opened
    # site/bills/<year>/<ID>.json, which since the records moved inside the
    # pages exists only for the few too large to inline; a missing file was
    # skipped, and it only looked at committee items that already had a start.
    # So it checked 298 proceedings and passed while the committee pages
    # printed no time for 9,672 the bill pages timed. Now it reads the pages,
    # checks every item that has a recording -- a start on one page and none
    # on the other is a disagreement too -- and fails on an item it cannot
    # find on its bill page rather than stepping round it.
    croot = Path("site/committee")
    if not croot.exists() or not Path("site/bill").is_dir():
        return "skip", "committee JSON or bill pages not built"
    import site_read as SR
    recs = SR.by_bill("site", SR.video_years(), fields=("stations",))
    checked, bad, lost = 0, [], []
    for f in sorted(croot.glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        for sess in c.get("sessions", []):
            for it in sess.get("items", []):
                if not it.get("video_id"):
                    continue
                key = (str(it.get("year") or ""), (it.get("bill") or "").upper())
                want = (it.get("kind") or "").strip().lower()
                st = next((x for x in ((recs.get(key) or {}).get("stations")
                                       or [])
                           if x.get("when") == sess.get("date")
                           and (not want
                                or want in (x.get("what") or "").lower())), None)
                if not st:
                    lost.append(f"{c.get('code')} {sess.get('date')} "
                                f"{it.get('bill')} ({it.get('year')})")
                    continue
                checked += 1
                a, b = it.get("start"), st.get("start")
                if (a is None) != (b is None) or (
                        a is not None and abs(float(a) - float(b)) > 1):
                    bad.append(f"{c.get('code')} {sess.get('date')} "
                               f"{it.get('bill')}: committee says {a}, "
                               f"the bill page says {b}")
    if not checked and not lost:
        return "skip", "no committee item carries a recording"
    assert not lost, (
        f"{len(lost)} committee item(s) with a recording have no matching "
        f"station on their bill page: {'; '.join(lost[:3])}")
    assert not bad, (
        f"{len(bad)} of {checked:,} proceedings start at a different moment on "
        f"the committee page than on the bill page: {'; '.join(bad[:2])}")
    return "ok", (f"{checked:,} recorded proceedings, one start each, on both "
                  f"pages")


@check("data", "no published time was read off captions out of step with the recording")
def _late_captions_site():
    """The guard, on the site as built.

    build_site_v2 withholds every time read off a caption track that stops
    well short of its recording -- see caption_span.py, and the build check
    of the same name. A site built before that, or by a build that skipped
    it, still carries them, and nothing on the page looks wrong. So this
    reads what the pages publish: for every recording whose captions stop
    more than caption_span.SLACK short of it, does any station on it carry a
    time read off those captions -- a stated or clustered start, a stated
    floor boundary, or a consent-calendar finding?
    """
    try:
        import caption_span as CS
        import proceedings as P
        import site_read
    except ImportError:
        return "skip", "caption_span, proceedings or site_read is not here"
    if not (Path("site/bill").is_dir() and Path("work").is_dir()):
        return "skip", "no built site, or no work/ to compare it with"
    late, compared, undated = CS.out_of_step(
        [d.name for d in Path("work").iterdir() if d.is_dir()])
    if not compared:
        return "skip", ("no recording under work/ has both captions and a "
                        "published length")
    short = f"{CS.SLACK // 60} minutes"
    if not late:
        return "ok", f"{compared:,} recordings compared; none stops {short} short"
    # Only the terms those recordings belong to: the pages are the slow part.
    rows = P.by_video(P.load())
    years = sorted({y for v in late for r in rows.get(v, [])
                    for y in str(r.get("term") or "").split("-") if y.isdigit()})
    CAPTIONED = {"stated", "located", "floor_stated", "consent"}
    n, bad = 0, []
    for y, b, s in (site_read.stations("site", years) if years else ()):
        if s.get("video_id") not in late:
            continue
        n += 1
        if s.get("state") in CAPTIONED or s.get("start_stated"):
            bad.append(f"{b} of {y}, {s.get('when')}, on {s['video_id']}: "
                       f"{s.get('state')} at {s.get('start')}")
    assert not bad, (
        f"{len(bad)} published station(s) carry a time read off captions that "
        f"stop more than {short} short of their recording -- an hour early, on "
        f"every one measured: {'; '.join(bad[:2])}. Rebuild the site.")
    return "ok", (f"{compared:,} recordings compared; {len(late)} stop more "
                  f"than {short} short, and none of the {n} stations on them "
                  "publishes a time read off their captions"
                  + (f"; {len(undated)} have no published length to compare"
                     if undated else ""))


@check("data", "a committee is credited only with its own recommendations")
def _committee_attribution():
    """The day narrative says what a committee decided. It must be that one.

    A bill is reported by a House committee and then, if it passes, by a
    Senate one, and several are re-referred and reported twice within a
    chamber. The narrative took the first report on file for the bill, so a
    committee could be credited with a decision made by another -- sometimes
    across the building.

    Two causes, both fixed: the lookup ignored the committee, and the merge of
    committee_reports.json with senate_reports.json used setdefault, so a bill
    with a House report never kept its Senate one at all.

    This is the site putting a claim in its own voice about who decided what.
    It is the last thing that should be approximately right.
    """
    root = Path("site/committee")
    if not root.exists():
        return "skip", "no committee pages built"
    reps = {}
    for name in ("committee_reports.json", "senate_reports.json"):
        f = Path(name)
        if not f.exists():
            continue
        for t, byb in json.loads(f.read_text(encoding="utf-8")).items():
            for b, v in byb.items():
                reps.setdefault(t, {}).setdefault(b, []).extend(
                    v if isinstance(v, list) else [v])
    if not reps:
        return "skip", "no committee report files here"

    total, bad = 0, []
    for f in sorted(root.glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        want = (c.get("name") or "").strip().lower()
        for sess in c.get("sessions", []):
            narr = sess.get("narrative", "")
            for it in sess.get("items", []):
                if it.get("kind") != "executive session":
                    continue
                # The claim as the page makes it, so this checks the sentence
                # rather than the intent behind it.
                if f"On {it.get('n') or it.get('bill')} it recommended" not in narr:
                    continue
                total += 1
                mine = any(
                    want in [(r.get("committee") or "").strip().lower()
                             for r in (rec.get("reports") or [])]
                    for rec in (reps.get(it.get("term"), {}) or {})
                    .get(it.get("bill"), []) or [])
                if not mine:
                    bad.append(f"{c.get('code')} {c.get('name')!r} claims "
                               f"{it.get('bill')}")
    assert not bad, (
        f"{len(bad)} of {total:,} recommendation claims are not backed by a "
        f"report of that committee's own: {'; '.join(bad[:3])}")
    return "ok", (f"{total:,} recommendation claims, every one backed by that "
                  "committee's own report")


@check("data", "a term's sponsors came from that term's own files")
def _sponsors_by_term():
    """The check for a mistake made while writing the file this reads.

    data/sponsors.json is {term: {bill: [sponsor]}} now. Splitting the flat
    dict was done, at first, with a bill -> term map built from data/bills.json
    -- which is exactly the confusion the term keying exists to prevent. A bill
    number is in more than one term, so every repeated number took whichever
    term the loop reached last: 1,849 of 2,220 bills' sponsors landed under
    2023-2024, having been read out of the 2025-2026 files, and the site built
    byte-identical because build_site_v2 then found nothing for the current
    term and showed no sponsors rather than the wrong ones.

    LsrSponsors.txt and LsrsOnly.txt cover the current session, so the newest
    term is where nearly all of them belong, and a term holding sponsors for
    bills it does not have is the same error seen from the other side.
    """
    sp = Path("data/sponsors.json")
    bl = Path("data/bills.json")
    if not (sp.exists() and bl.exists()):
        return "skip", "data/sponsors.json or data/bills.json not here"
    sponsors = json.loads(sp.read_text(encoding="utf-8"))
    bills = json.loads(bl.read_text(encoding="utf-8"))
    if not all(re.match(r"^\d{4}-\d{4}$", k) for k in sponsors):
        return "skip", "data/sponsors.json is not keyed on the term yet"

    # No term may carry sponsors for a bill that term does not have.
    stray = {t: sorted(set(byb) - set(bills.get(t, {})))[:4]
             for t, byb in sponsors.items()
             if set(byb) - set(bills.get(t, {}))}
    assert not stray, (
        f"sponsors filed under a term whose bills.json has no such bill: "
        f"{stray}")

    # And the term the current session's files describe must actually have
    # them. 17% is what the bug looked like; a healthy run is above 90%.
    newest = max(bills)
    have, total = len(sponsors.get(newest, {})), len(bills.get(newest, {}))
    assert total and have > total * 0.75, (
        f"{newest} has sponsors on {have:,} of {total:,} bills. Its own "
        "sponsor files cover every bill, so this is sponsors filed under the "
        "wrong term, not sponsors that are missing.")
    census = ", ".join(f"{t} {len(v):,}/{len(bills.get(t, {})):,}"
                       for t, v in sorted(sponsors.items()))
    return "ok", f"sponsors by term: {census}"


@check("data", "every voter in the record is one person, with a party")
def _vote_identity():
    """Two ways a roll call stops naming who voted, both of which shipped.

    A member who has left is not in legislators.txt, so the party letter falls
    back to "X" and the grid shows them under no party at all. That was 63,065
    of the 2023-2024 term's 199,385 votes -- 32% of a term -- and nothing said
    so; it was noticed by a reader. former_members.json now carries them, from
    the General Court's own legislators table.

    Worse, and quieter: RollCallHistory identifies a voter by Employeeno, and
    the roster's PersonID is joined in on it. Three members of the 2023-2024
    House have no legislators row at all, so that join came back empty and all
    three were written with an id of "" -- one row in the grid carrying three
    people's votes, none of them named. Distinct Employeenos must stay
    distinct members however little else is known about them.
    """
    rc = Path("rollcalls")
    hist = sorted(rc.glob("RollCallHistory_*.txt")) if rc.exists() else []
    if not hist:
        return "skip", "no rollcalls/RollCallHistory_*.txt here"
    # The id build_data will key a voter on, per Employeeno: the PersonID the
    # join supplied, or the Employeeno itself when it supplied none.
    by_emp = {}
    for f in hist:
        for line in f.open(encoding="utf-8-sig", errors="replace"):
            r = line.rstrip("\n").split("|")
            if len(r) < 8:
                continue
            emp, pid = r[3].strip(), r[4].strip()
            if emp:
                by_emp.setdefault(emp, set()).add(pid or emp)
    seen = {}
    for emp, ids in by_emp.items():
        for i in ids:
            seen.setdefault(i, set()).add(emp)
    merged = {i: sorted(e) for i, e in seen.items() if len(e) > 1}
    assert not merged, (
        f"{len(merged)} member id(s) carry more than one Employeeno, so two "
        f"or more people's votes are shown as one: "
        f"{dict(list(merged.items())[:3])}")

    mv = Path("data/member_votes.json")
    if not mv.exists():
        return "ok", (f"{len(by_emp):,} voters, each with an id of their own; "
                      "data/member_votes.json not built, so no party census")
    votes = json.loads(mv.read_text(encoding="utf-8"))
    per_term = {}
    for v in votes:
        y = int(v.get("year") or 0)
        if not y:
            continue
        t = f"{y - (1 - y % 2)}-{y - (1 - y % 2) + 1}"
        tot, nop, non = per_term.get(t, (0, 0, 0))
        per_term[t] = (tot + 1,
                       nop + ((v.get("party") or "X") == "X"),
                       non + str(v.get("name") or "").startswith("Member #"))

    # A NAME, EVERYWHERE. This is the guard that holds across the whole
    # archive, and the one that regressed most recently: 24 years of roll
    # calls came off the database dump on 10 September and 783,919 of their
    # ballots were cast by "Member #330274", nobody at all. past_members.json
    # names 733,474 of them. Measured after that, no term is worse than 4%.
    nameless = {t: f"{n:,}/{tot:,}" for t, (tot, _, n) in per_term.items()
                if tot and n > tot * 0.05}
    assert not nameless, (
        f"a term has more than 5% of its ballots cast by somebody unnamed: "
        f"{nameless}. past_members.json is missing or stale; "
        "fetch_sponsors_by_member.py --members writes it in one request.")

    # A PARTY, ON EVERY TERM. This rule covered every term, was narrowed to
    # 2017 onward for one afternoon, and covers every term again -- and the
    # reason is worth keeping, because it is the difference between a guard
    # that was loosened and one that was true at the time.
    #
    # 24 years of roll calls landed on 10 September and 773,506 of their
    # ballots had no party: 88% of 1999-2000, 57% of 2011-2012. No roster on
    # this disk carried one for those people, and the tempting fix -- guessing
    # from a later namesake, or from how somebody voted -- would have
    # fabricated the fact a reader is most likely to act on. So the rule was
    # narrowed to where it was achievable and the rest was REPORTED, with the
    # numbers, rather than asserted or invented.
    #
    # Then a person found the page that has it. The legacy roll call detail
    # prints every member's party beside their vote, and because a party is a
    # fact about a member in a term rather than about a vote, the fullest
    # roll call of each year and chamber names almost the whole chamber: 54
    # requests, 2,078 members, and every term came back inside 5%.
    #
    # The case the rule exists for is still the one that matters: 63,065 of
    # the 2023-2024 term's votes lost their party letter once, and a reader
    # found it before this file did.
    bad = {t: f"{n:,}/{tot:,}" for t, (tot, n, _) in per_term.items()
           if tot and n > tot * 0.05}
    assert not bad, (
        f"a term is missing party on more than 5% of its votes: {bad}. "
        "former_members.json is stale, or member_party.json is missing -- "
        "fetch_rollcall_parties.py writes it from 54 roll call pages.")
    worst = max(((n / tot, t) for t, (tot, n, _) in per_term.items() if tot),
                default=(0, ""))
    return "ok", (f"{len(by_emp):,} distinct voters, every term named and "
                  f"partied; worst term {worst[1]} at {worst[0] * 100:.0f}%")


@check("frontend", "a page says what it is once, and says where it lives")
def _one_head():
    """Exactly one title, one description and one canonical per page.

    shell.page() builds a head that begins with the viewport meta and
    substitutes it into bills.html -- which left the template's own <title>
    in place, so every generated page carried two. Browsers show the first;
    a crawler may take either.
    """
    site = Path("site")
    if not site.exists():
        return "skip", "site is not built"
    bad, n = [], 0
    for p in sorted(site.rglob("*.html")):
        h = p.read_text(encoding="utf-8", errors="replace")[:6000]
        n += 1
        for what, pat in (("title", r"<title>"),
                          ("description", r'<meta name="description"'),
                          ("canonical", r'<link rel="canonical"')):
            c = len(re.findall(pat, h))
            if c > 1:
                bad.append(f"{p.relative_to(site)} has {c} {what} tags")
            elif c == 0 and what == "title":
                bad.append(f"{p.relative_to(site)} has no title")
        if len(bad) > 12:
            break
    assert not bad, (f"{len(bad)} page(s) name themselves more than once: "
                     + "; ".join(bad[:4]))
    return "ok", f"{n:,} pages, one head each"


@check("data", "nobody is named surname-first on a page")
def _no_lastfirst():
    """A member reads the same wherever they appear, including after leaving.

    The roster holds the 406 sitting members. A committee's record reaches
    back past them, so 173 seats across 85 people fell through to the source's
    own spelling and read "Soucy, Donna" beside "Sen. Sharon Carson (R - SD14)"
    -- and a member who has left is shown exactly like one who has not.
    """
    site = Path("site")
    if not site.exists():
        return "skip", "site is not built"
    lastfirst = re.compile(r"^[A-Z][A-Za-z'\-]+,\s+[A-Z]")
    bad, n = [], 0

    def walk(o):
        nonlocal n
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("label", "display_full", "display") and isinstance(v, str):
                    n += 1
                    if lastfirst.match(v):
                        bad.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for p in list(site.glob("committee/*.json")) + [site / "legislators.json"]:
        if p.exists():
            walk(json.loads(p.read_text(encoding="utf-8")))
    if not n:
        return "skip", "no labels found"
    assert not bad, (f"{len(bad)} of {n:,} names are written surname-first: "
                     + "; ".join(sorted(set(bad))[:4]))
    return "ok", f"{n:,} names, all written as a person is addressed"


@check("data", "a person's career is one record, and two people are two")
def _careers():
    """careers.json merges employee numbers into people, and must not overmerge.

    A member gets a new EmployeeNumber when they move from the House to the
    Senate, so 19 of the roster's numbers belong to somebody who already had
    one. The rule is a shared name AND service that does not overlap, because
    nobody holds two seats at once -- and the two shared names whose service
    DOES overlap are two different people, which is the case this guards.
    """
    p = Path("careers.json")
    if not p.exists():
        return "skip", "careers.json is not built"
    d = json.loads(p.read_text(encoding="utf-8"))
    bad = []
    seen = {}
    for key, v in d.items():
        for e in v.get("employee_nos") or []:
            if e in seen:
                bad.append(f"employee number {e} is in two people: "
                           f"{seen[e]} and {key}")
            seen[e] = key
        terms = v.get("terms") or []
        if terms != sorted(terms):
            bad.append(f"{key} lists its terms out of order")
        if len(terms) != len(set(terms)):
            bad.append(f"{key} lists a term twice")
        # A district carried backwards across a redistricting is the error
        # this file exists to avoid; none is recorded until a per-term source
        # supplies one.
        if v.get("district_by_term"):
            for t in v["district_by_term"]:
                if t not in terms:
                    bad.append(f"{key} has a district for {t}, a term it did "
                               "not serve")
    assert not bad, (f"{len(bad)} problem(s) in careers.json: "
                     + "; ".join(bad[:3]))
    multi = sum(1 for v in d.values() if len(v.get("employee_nos") or []) > 1)
    named = sum(1 for v in d.values() if v.get("named"))
    return "ok", (f"{len(d):,} people, {multi} holding more than one employee "
                  f"number, {named:,} named")


@check("data", "a member is named the same way by both namers")
def _one_naming():
    """names.legislator and build_site_v2.member_labels must agree.

    Two functions compose a member's name because data/legislators.json is
    written by build_data.py, which runs first and cannot import the builder.
    They agreed on all 406 members the day the second one was written, and the
    only way to keep that true is to ask.
    """
    try:
        import names
        import build_site_v2 as B
    except ImportError as e:
        return "skip", f"cannot import: {e}"
    src = Path("data/legislators.json")
    if not src.exists():
        return "skip", "data/legislators.json is not built"
    recs = json.loads(src.read_text(encoding="utf-8"))
    recs = list(recs.values()) if isinstance(recs, dict) else recs
    bad = []
    for r in recs:
        if not isinstance(r, dict):
            continue
        mine = names.legislator(r)
        theirs = B.member_labels(
            r.get("name"), chamber=r.get("chamber"), party=r.get("party_code"),
            district=r.get("district"), county=r.get("county"),
            county_abbr=r.get("county_abbr"))["display_full"]
        if mine != theirs:
            bad.append(f"{r.get('name')}: {mine!r} vs {theirs!r}")
    assert not bad, (f"{len(bad)} of {len(recs)} members are named two ways: "
                     + "; ".join(bad[:3]))
    return "ok", f"{len(recs):,} members, one name each"


@check("data", "what is on disk for the markers to read")
def _work():
    w = Path("work")
    if not w.exists():
        return "skip", "no work/ here; run align_all.py first"
    dirs = [d for d in w.iterdir() if d.is_dir()]
    tr = sum(1 for d in dirs if (d / "transcript.json").exists())
    sg = sum(1 for d in dirs if (d / "segments.json").exists())
    applied = 0
    for d in dirs:
        f = d / "segments.json"
        if f.exists() and "start_stated" in f.read_text(encoding="utf-8"):
            applied += 1
    both = sum(1 for d in dirs
               if (d / "transcript.json").exists() and (d / "segments.json").exists())
    return "ok", (f"{len(dirs):,} videos, {tr:,} transcripts, {sg:,} aligned, "
                  f"{both:,} ready for apply_markers, {applied:,} already patched")


# ======================================================================= main ==

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", action="store_true", help="skip the data checks")
    ap.add_argument("--data", action="store_true", help="only the data checks")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()

    sys.path.insert(0, ".")
    print("=" * 74)
    print(f"preflight   {Path('.').resolve()}")
    print(f"python {sys.version.split()[0]}")
    print("=" * 74)

    results, group = [], None
    for c in CHECKS:
        if a.code and c["group"] == "data":
            continue
        if a.data and c["group"] != "data":
            continue
        if c["group"] != group:
            group = c["group"]
            print(f"\n{group.upper()}")
        mods = []
        missing = None
        for n in c["needs"]:
            m = imp(n)
            if m is None:
                missing = n
                break
            mods.append(m)
        if missing:
            status, msg = "skip", f"{missing}.py will not import"
        else:
            try:
                status, msg = c["fn"](*mods)
            except AssertionError as e:
                status, msg = "FAIL", str(e) or "assertion failed"
            except Exception as e:
                status, msg = "ERROR", f"{type(e).__name__}: {e}"
                if a.verbose:
                    traceback.print_exc()
        results.append((c["group"], c["name"], status, msg))
        mark = {"ok": "  ok  ", "skip": " skip ", "FAIL": " FAIL ",
                "ERROR": "ERROR "}[status]
        print(f"  [{mark}] {c['name']}")
        if status != "ok" or a.verbose:
            for line in str(msg).splitlines():
                print(f"           {line}")

    bad = [r for r in results if r[2] in ("FAIL", "ERROR")]
    skipped = [r for r in results if r[2] == "skip"]
    ok = [r for r in results if r[2] == "ok"]

    print("\n" + "=" * 74)
    print(f"{len(ok)} passed, {len(bad)} failed, {len(skipped)} skipped")
    if bad:
        print("\nWhat is broken:")
        for g, n, s, m in bad:
            print(f"  {g}/{n}")
            print(f"    {str(m)[:150]}")
        print("\nEach of these is independent, so fix them in any order. Nothing")
        print("here touched the site or the data files.")
    if skipped:
        print("\nSkipped, mostly because the file is not in this folder:")
        for g, n, s, m in skipped:
            print(f"  {g}/{n}: {m}")
    if not bad:
        print("\nEverything that can be checked without the network is working.")
        print("What is left needs real data: run inventory.py, then align_all,")
        print("then segment_markers.py --all --data data, and score the result:")
        print("  probe_alignment.py --truth --candidate candidate_segments.json")
        print("Do not run apply_markers.py --apply. It is the superseded")
        print("clustering path; build_all skips it unless --with-superseded,")
        print("and it overwrites boundaries segment_markers read from the chair.")
    print("=" * 74)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
