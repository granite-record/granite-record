#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.29
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
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from collections import Counter
from pathlib import Path

CHECKS = []


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
        r = subprocess.run([sys.executable, "floor_markers.py",
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
    return subprocess.run(
        [sys.executable, "apply_markers.py", "--workdir", str(root / "work"),
         "--manifest", str(root / "manifest.csv"), *flags],
        capture_output=True, text=True, timeout=180)


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
        r = subprocess.run([sys.executable, "verify_batch.py",
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

@check("frontend", "bills.html carries the changes and its tags balance")
def _bills_html():
    p = Path("bills.html")
    if not p.exists():
        p = Path("site/bills.html")
    if not p.exists():
        return "skip", "bills.html not here or in site/"
    t = p.read_text(encoding="utf-8")
    want = {
        "play control is a button": '<button type="button" class="pstub"',
        # A link inside a button is not a link a keyboard or a screen reader
        # can reach, so this one sits outside the card's expand button. What it
        # is called changed once already; anchoring on the tag rather than the
        # wording is what the check is actually about.
        "detail link outside the button": '<a class="detail',
        "page heading": '<h1 class="sr">',
        # A stated boundary is a different claim from an estimate and the
        # page words it differently; the check follows the wording.
        "stated boundary worded as such": "the chair opens it at ${hms(s.start)}",
        "estimate still carries a tolerance": "estimated within \\u00b1",
        "consent bills get no timestamp": 's.state==="consent"',
        "member sort key": "(a.s||a.n||\"\")",
        # A jump button pressed before the player exists must build the
        # player AT that time. Clicking the stub instead builds it at the
        # opening offset -- up to five minutes earlier -- and then posts
        # seekTo into an iframe created a line before, which YouTube is not
        # listening on yet. The video then sits at a different time from the
        # button that was pressed, which is what a reader sees as the player
        # and the printed timestamps disagreeing.
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
        r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
        shutil.rmtree(f.parent, ignore_errors=True)
        assert r.returncode == 0, "node --check: " + r.stderr.strip()[:150]
        extra = ", node --check clean"
    return "ok", f"7 markers present, tags balanced{extra}"


@check("frontend", "the bill page stylesheet still formats")
def _bill_css():
    p = Path("build_bill_pages.py")
    if not p.exists():
        return "skip", "build_bill_pages.py not here"
    import re as _re
    src = p.read_text(encoding="utf-8")
    m = _re.search(r"@media \(max-width: 720px\)\{\{.*?\n\}\}", src, _re.S)
    assert m, "the narrow-screen block is not there"
    m.group(0).format()          # doubled braces, in an f-string template
    assert "start_stated" in src, "the tolerance wording was not updated"
    return "ok", "braces resolve, narrow-screen overrides present"


@check("frontend", "both stylesheets carry the corrected palette")
def _palette():
    bad = []
    for name, path in (("bills.html", Path("bills.html")),
                       ("style.css (build_pages.py)", Path("build_pages.py"))):
        if not path.exists():
            continue
        t = path.read_text(encoding="utf-8")
        if "--ink-3:#6C7274" not in t:
            bad.append(f"{name}: --ink-3 still fails contrast")
        if "--edge:" not in t:
            bad.append(f"{name}: no --edge for control borders")
    assert not bad, "; ".join(bad)
    return "ok", "--ink-3 at 4.5:1, --edge at 3:1"


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


@check("files", "no generator writes ground_truth.csv")
def _record_untouched():
    """The 35 hand-marked times are the only measurement of this system a
    person made, and they were lost twice while they lived as two columns in a
    file that rebuilds overwrite. They now live in ground_truth.csv, which a
    person edits and every generator only reads. A build_ or fetch_ script
    that opens it for writing is the next loss waiting to happen."""
    bad = []
    for f in sorted(Path(".").glob("build_*.py")) + sorted(Path(".").glob("fetch_*.py")):
        src = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r'ground_truth\.csv', src) and re.search(
                r'(?:open\s*\([^)]*ground_truth\.csv[^)]*["\']w|'
                r'ground_truth[^\n]{0,40}write_text|'
                r'TRUTH\s*\.\s*open\s*\(\s*["\']w)', src):
            bad.append(f.name)
    assert not bad, "these write the record: " + ", ".join(bad)
    return "ok", "only a person writes it"


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
    r = subprocess.run([sys.executable, str(f)], capture_output=True, text=True)
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
    js = "\n".join(re.findall(r"<script>(.*?)</script>",
                              f.read_text(encoding="utf-8"), re.S))
    assert js.strip(), "no script in bills.html"
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
    "; ({render, IDX, renderDetail, setFocused:(x)=>{focused=x;}, getFocused:()=>focused, getQuery:()=>query});"); }
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
// its own address. In the search list that is obvious. On the focused view the
// reader is already reading a detail page, so a bare arrow in the corner reads
// as a link to the one they are on; there it carries its name instead.
scope.setFocused("HB1442");
try { scope.render(); } catch (e) {
  console.log("RENDER focused " + e.constructor.name + ": " + e.message);
  process.exit(1); }
const focusHtml = document.querySelector("#results").innerHTML;
scope.setFocused(null);
if (!/Standalone page/.test(focusHtml)) {
  console.log("ARROW: on the focused view the link to the standalone page does "
              + "not say where it goes"); process.exit(1); }
if (/Standalone page/.test(listHtml)) {
  console.log("ARROW: the search list labels its arrow, which only belongs on "
              + "the focused view"); process.exit(1); }
if (!/class="detail"/.test(listHtml)) {
  console.log("ARROW: the search list drew no link to a standalone page");
  process.exit(1); }
if (!/title="A standalone page for/.test(listHtml)) {
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
                      text:"For it."}]}],
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
         "does not publish the written reasoning",
         // And what happened between the two House reports.
         "Between these reports the docket",
         // The tab counts what the tab draws: three written blocks and the
         // Senate's one. It used to count only the written ones.
         "Committee reports (4)",
         // A boundary the chair announced is quoted; one the clustering
         // guessed says so. Both stations here start at a stated boundary,
         // so only the end can produce the difference.
         "and closes it at 00:15:00",
         "00:15:00 ends",
         "ending about 00:40:00",
         ", end estimated",
         "00:40:00 about where it ends"]},
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
        r = subprocess.run(["node", "go.js"], cwd=root, capture_output=True,
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
    b, h = Path("build_site_v2.py"), Path("bills.html")
    if not (b.exists() and h.exists()):
        return "skip", "build_site_v2.py or bills.html not here"
    src = b.read_text(encoding="utf-8")
    page = h.read_text(encoding="utf-8")

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
    f = Path("bills.html")
    if not f.exists():
        f = Path("site/bills.html")
    if not f.exists():
        return "skip", "bills.html not here or in site/"
    js = "\n".join(re.findall(r"<script>(.*?)</script>",
                              f.read_text(encoding="utf-8"), re.S))
    assert js.strip(), "no script found in bills.html"
    bad = _tdz_suspects(js)
    assert not bad, "; ".join(bad[:3])
    return "ok", "checked every function in bills.html"


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

    w("data/bills.json", {
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
                 "senate_committee": "", "lsr": "2026-0900"}})
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
         "date": "2026-03-06", "vote": "Yea"}])
    w("data/towns.json", {"Raymond": [{"county": "Rockingham", "district": "13",
                                       "ward": "0", "seats": 2}]})
    w("narratives.json", {
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
                                     "Lacking Necessary Two-Thirds Vote"}]}})
    w("rollcalls.json", {"HB1442": [
        {"year": "2026", "body": "H", "number": "310", "date": "2026-03-06",
         "time": "11:12", "bill": "HB1442", "procedural": False,
         "question": "Ought to Pass", "question_raw": "Ought to Pass",
         "question_plain": "pass the bill", "yeas": 214, "nays": 119, "voting": 333,
         "not_voting": 67, "seats": 400, "seated": 400, "vacancies": 0,
         "threshold_needed": None, "threshold_rule": None, "passed": True,
         "threshold_note": None, "title": "relative to insurance coverage"}]})
    w("bill_status.json", {
        "HB1442": {
            "gen_status": "PASSED/ADOPTED", "house_status": "PASSED/ADOPTED",
            "senate_status": "", "text_pdf": "https://gc.nh.gov/x.pdf",
            "chapter": "", "lsr": "2026-0503", "body": "H"},
        "HR10": {"gen_status": "HOUSE", "house_status": "PASSED/ADOPTED",
                 "senate_status": "", "text_pdf": "", "chapter": "",
                 "lsr": "2026-0900", "body": "H"}})
    w("committee_reports.json", {"HB1442": [
        {"bill": "HB1442", "title": "insurance coverage",
         "majority_recommendation": "OUGHT TO PASS", "minority_recommendation": None,
         "source": "House Calendar 9, 2026",
         "reports": [{"side": "Committee", "author": "Rep. Jodi Nelson",
                      "committee": "Commerce", "text": "The committee supports this.",
                      "vote_yeas": 19, "vote_nays": 0}]}]})
    # A floor appearance WITH a boundary the clerk stated. This is not
    # decoration: build_site_v2 used to apply that boundary by rebinding `st`
    # to stations[-1], and `st` was already the bill's status record from 350
    # lines earlier. Every bill that took this branch -- 611 of 2,234 on the
    # real data -- then shipped with no facts block, no text_pdf, and a
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
    with open(root / "verification_manifest.csv", "w", newline="",
              encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(row))
        wr.writeheader()
        wr.writerow(row)
        wr.writerow(row4)
    # The site reads proceedings.csv, not the manifest. Build it the way
    # build_all does, from the two sources the fixture just wrote.
    import subprocess, sys
    for f in ("build_proceedings.py", "proceedings.py"):
        if Path(f).exists():
            shutil.copy(f, root / f)
    r = subprocess.run([sys.executable, "build_proceedings.py"], cwd=root,
                       capture_output=True, text=True)
    assert r.returncode == 0, "fixture proceedings: " + (r.stderr or r.stdout)[-200:]


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
        r = subprocess.run([sys.executable, "build_proceedings.py"], cwd=root,
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
            ("build_feeds.py", ["--site", "site", "--base", base],
             "site/feed/all.xml"),
        ]
        for script, args, produces in steps:
            r = subprocess.run([sys.executable, str(here / script), *args],
                               cwd=root, capture_output=True, text=True, timeout=180)
            if r.returncode != 0:
                tail = (r.stderr or r.stdout).strip().splitlines()
                raise AssertionError(f"{script}: " + (tail[-1][:120] if tail else "?"))
            assert (root / produces).exists(), f"{script} produced no {produces}"
        r = subprocess.run([sys.executable, str(here / "check_site.py"),
                            "--site", "site", "--base", base],
                           cwd=root, capture_output=True, text=True, timeout=120)
        bad = [l.strip() for l in r.stdout.splitlines() if l.strip().startswith("x ")]
        assert not bad, "check_site: " + "; ".join(bad)[:140]
        return "ok", "5 builders, then check_site, on a 2-bill fixture"
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
        r = subprocess.run([sys.executable, str(here / "build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        s = root / "site"
        hb = json.loads((s / "bills" / "HB1442.json").read_text(encoding="utf-8"))

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
            (hb.get("text_pdf") == "https://gc.nh.gov/x.pdf",
             f"text_pdf reads {hb.get('text_pdf')!r} on a bill with a stated "
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


@check("data", "a bill the governor signed says so")
def _signed():
    if not (Path("narratives.json").exists() and Path("build_site_v2.py").exists()):
        return "skip", "narratives.json or build_site_v2.py not here"
    bs = imp("build_site_v2")
    assert bs, "build_site_v2.py will not import"
    nv = json.loads(Path("narratives.json").read_text(encoding="utf-8"))
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
