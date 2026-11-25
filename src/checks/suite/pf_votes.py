#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.3
"""
preflight's checks of roll calls and the votes pages.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import _paths

from pf_core import (_run, _source, check)
from pf_harness import (_with_components)
from pf_shared import (_mk)


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


@check("rollcalls", "a roll call on no bill is not glossed as one on a bill",
       needs=("rollcall_parser",))
def _no_bill_no_bill_gloss(rollcall_parser):
    """2026-H-271 tabled a motion to restore Rep. Read's privileges. The file
    files it under no bill as "Laid on Table", and the glossary's "set the bill
    aside without killing it" reached the member's Votes tab. On no bill the
    gloss is empty (not None, which means a motion the glossary lacks); on a
    bill it stands."""
    d = Path(tempfile.mkdtemp())
    try:
        f = d / "RollCallSummary.txt"
        f.write_text("\n".join([
            "2026|H|271|5/14/2026 11:00:00 AM||163|147|20|10|||Laid on Table|",
            "2026|H|272|5/14/2026 11:30:00 AM|HB56|200|150|20|10|||Laid on Table|relative to something",
        ]) + "\n", encoding="utf-8")
        rows = {r["number"]: r for r in rollcall_parser.parse(f)}
        assert rows[271]["question_plain"] == "", rows[271]["question_plain"]
        assert "bill" in (rows[272]["question_plain"] or ""), rows[272]["question_plain"]
        return "ok", "no gloss about a bill on the vote filed under none; the bill's keeps it"
    finally:
        shutil.rmtree(d, ignore_errors=True)


# The seven roll calls whose bill field is typed another way than the bill's
# own number, as the General Court's files give them.
_RC_TYPED = [
    "2001|S|11|3/29/2001 12:00:00 AM|SB115-FN|22|1|23|1|NULL|NULL|Ordering to third reading.  Sen. McCarley/Sen. Hollingworth|granting a cost of living adjustment to certain retired group II firefighters.||6/4/2002 10:46:02 AM",
    "2012|S|118|6/6/2012 12:00:00 AM|SB 406|18|4|23|0|||Committee of Conference Report 2462|(New Title) relative to establishing an early offer alternative in medical injury claims.||6/6/2012 7:31:16 PM",
    "2016|H|21|1/7/2016 3:19:26 PM|sb136|156|152|17|74|||OTPA|||",
    "2016|H|31|1/20/2016 2:44:45 PM|HCACR2|234|90|19|56|||ITL|Relating to dedicated funds.  Providing that funds shall be used solely for the purpose of the fund.||",
    "2016|H|38|2/4/2016 2:57:33 PM|HCACR15|220|85|25|69|||ITL|relating to the election of judges. Providing that judges be elected for specific terms.||",
    "2017|S|198|6/22/2017 12:00:00 AM|HB 315|3|20|23|0|||C of C Report 2306|(New Title) relative to persons who may accompany a youth operator of an OHRV.||6/22/2017 3:33:45 PM",
    "2018|S|84|3/8/2018 12:00:00 AM|SB 426|13|10|23|1|||Inexpedient to Legislate|relative to the commission on primary care workforce issues.||3/9/2018 4:46:41 PM",
    "2025|H|1|1/8/2025 10:00:00 AM|HRULE64|216|164|10|10|||Amend H Rule 64|relating to the rules of the House",
]


@check("rollcalls", "a roll call reaches its bill however the file typed the number",
       needs=("rollcall_parser",))
def _rollcall_typed_bill(RP):
    """2016 H 31 is CACR 2's 234-90 vote to kill it, filed as "HCACR2": it
    matched no bill number, was classed as procedural, and reached neither
    the bill's page nor any member's. "SB 406", "sb136" and "SB115-FN" missed
    the same way, each at a different step, because rollcall_parser stripped
    spaces without upper-casing and build_data upper-cased without stripping.
    One normaliser now answers both; a vote on a House rule stays procedural.
    """
    want = {"SB115-FN": "SB115", "SB 406": "SB406", "sb136": "SB136",
            "HCACR2": "CACR2", "HCACR15": "CACR15", "HB 315": "HB315",
            "SB 426": "SB426", "HB2-FN-A-LOCAL": "HB2", "HB1-L": "HB1",
            "HRULE64": "", "SUSPRULE": "", "HR      ": "", "": ""}
    got = {k: RP.bill_number(k) for k in want}
    assert got == want, f"bill_number gave {[(k, v) for k, v in got.items() if v != want[k]]}"
    d = Path(tempfile.mkdtemp())
    try:
        (d / "RollCallSummary.txt").write_text("\n".join(_RC_TYPED) + "\n", encoding="utf-8")
        rows = {(r["year"], r["body"], r["number"]): r
                for r in RP.parse(d / "RollCallSummary.txt")}
        bad = {k: (r["bill"], r["procedural"]) for k, r in rows.items()
               if k != ("2025", "H", 1) and (r["procedural"] or r["bill"] != RP.bill_number(r["bill"]))}
        assert not bad, f"typed bill numbers still procedural or unnormalised: {bad}"
        assert rows[("2025", "H", 1)]["procedural"] and rows[("2025", "H", 1)]["bill"] == "HRULE64", (
            "a vote on a House rule was taken for a bill")
        # Keyed as the page looks the bill up, through the CLI the build runs.
        r = _run([sys.executable, _paths.script("rollcall_parser.py"), "--file",
                  "RollCallSummary.txt", "--dir", "none", "--all", "--out", "rc.json"],
                 cwd=d, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, "rollcall_parser failed: " + (r.stderr or r.stdout)[-300:]
        keyed = json.loads((d / "rc.json").read_text(encoding="utf-8"))
        assert sorted(keyed["2015-2016"]) == ["CACR15", "CACR2", "SB136"] and \
            sorted(keyed["2001-2002"]) == ["SB115"] and \
            sorted(keyed["2011-2012"]) == ["SB406"] and \
            sorted(keyed["2017-2018"]) == ["HB315", "SB426"] and \
            sorted(keyed["2025-2026"]) == ["_procedural"], (
            f"roll calls keyed {[(t, sorted(b)) for t, b in keyed.items()]}")
        # build_data keys each member's ballot by the summary's bill, and only
        # a rebuild would show it reverting -- the nightly runs --code alone.
        src = _source(_paths.locate("build_data.py"))
        assert '"bill": RP.roll_call_bill(r[0], r[1], r[2], r[4]) or r[4].upper()' in src, (
            "build_data.py no longer keys the roll-call summary's bill through "
            "rollcall_parser.roll_call_bill, so no ballot on \"SB 406\" reaches SB 406's page")
        return "ok", ("spaces, case, -FN and HCACR normalise to the bill's own number, in "
                      "parse, in the keys and in build_data's ballots; a House rule vote "
                      "stays procedural")
    finally:
        shutil.rmtree(d, ignore_errors=True)


# Real rows of rollcalls/RollCallSummary_<year>.txt: the House address of 1999,
# HCO 1 of 2002, measures of three special sessions, the draft and the rules
# vote that stay procedural, and the Senate's two votes on 2009's SR 1.
_RC_MEASURES = [
    "1999|H|169|7/1/1999 12:25:00 PM|HA1|256|58|316|100|HA 1  FOR THE REMOVAL OF DAVID A BROCK, CHIEF JUSTICE OF THE NEW| HAMPSHIRE SUPREME COURT, FROM HIS SAID OFFICE.|JOINT COMMITTEE REPORT:  OUGHT NOT TO PASS|for the removal of David A. Brock, chief justice of the New Hampshire supreme court, from his said office.||9/27/1999 2:46:42 PM",
    "2002|S|146|6/27/2002 12:00:00 AM|HCO1|13|11|24|0|||Adoption of the suspension of the rules Sen. Francoeur/Sen Barnes|relative to implementing an election pursuant to representative districts established in the order.||7/2/2002 12:42:20 PM",
    "2008|H|401|6/4/2008 8:33:00 AM|SSHR1   |151|162|317|83|SSHR1: 2008 SPECIAL SESSION RULES OF THE HOUSE.||  FLAM 2149H REP HESS|2008 Special Session Rules of the House||6/10/2008 9:06:08 AM",
    "2009|S|32|4/1/2009 12:00:00 AM|SR1|14|9|23|0|||Sen. Reynolds moved Introduction.|requesting an opinion of the justices concerning the constitutionality of SB 21.||5/4/2009 4:03:47 PM",
    "2009|S|33|4/1/2009 12:00:00 AM|SR1|14|9|23|0|||Sen. Reynolds moved Ought to Pass|requesting an opinion of the justices concerning the constitutionality of SB 21.||5/4/2009 4:29:58 PM",
    "2010|S|69|6/9/2010 12:00:00 AM|SSSB1|14|9|23|1|||Ought to Pass|relative to video lottery and table gaming at certain locations throughout the state and establishing the gaming regulatory oversight authority to oversee and assess the regulation of gaming activities in New Hampshire.||6/10/2010 3:22:00 PM",
    "2010|S|70|6/9/2010 12:00:00 AM|DRAFT|14|9|23|1|||Draft of SSSB 2 - LSR 2371, Laid on Table|making distributions from limited liability companies, partnerships, and associations subject to the interest and dividends tax only if they have transferable shares.||6/10/2010 3:21:49 PM",
    "2013|H|199|11/7/2013 10:56:00 AM|SSHB1|183|141|324|76|SSHB1: RELATIVE TO ACCESS TO HEALTH INSURANCE COVERAGE.              ||  DRAFTING, INTRO, READ & REFERRAL TO COMM (REP SHURTLEFF)           |making appropriations for the expenses of certain departments of the state for fiscal years ending June 30, 2014 and June 30, 2015.||11/8/2013 2:44:00 PM",
    "2015|H|199|11/18/2015 12:46:54 PM|SSHCR1|79|258|28|35|||Adopt Amendment|establishing a joint task force for the response to the heroin and opioid epidemic in New Hampshire.||",
    "2018|S|258|7/25/2018 12:00:00 AM|SSRULES|11|13|24|0|||Amendment to Special Session Senate Rules 5-4 and 5-5|Senator Feltes moved to offer an amendment to amend Special Session Senate Rules 5-4 and 5-5.||7/30/2018 11:20:23 AM",
]


@check("rollcalls", "a vote on a measure with a record reaches it, and a vote on a measure "
       "whose number another record holds reaches neither", needs=("rollcall_parser",))
def _rollcall_measure_kinds(RP):
    """Three kinds data/bills.json holds were missing from the bill-number
    pattern -- the House address (HA), HCO and every special-session measure
    (SSHB, SSSB, SSHR, SSHCR) -- so 68 roll calls on them were published as
    procedural and twelve records said they had no roll call: HA 1 of 1999,
    the House's 256-58 on removing Chief Justice Brock, among them. A vote on
    the chamber's own special-session rules, or on a draft no record carries,
    stays procedural.

    And the Senate's roll calls 32 and 33 of 2009 are on 2009's SR 1, an
    opinion of the justices on SB 21; the one SR 1 the record holds for
    2009-2010 is 2010's, on EPA vapor recovery, whose page drew both, with 23
    senators' ballots linked to it. They are filed under a name no record
    carries, and are not procedural."""
    want = {"HA1": "HA1", "HCO1": "HCO1", "SSHR1   ": "SSHR1", "SSSB1": "SSSB1",
            "SSHB1": "SSHB1", "SSHCR1": "SSHCR1", "SSRULES": "", "DRAFT": "", "HRULE64": ""}
    got = {k: RP.bill_number(k) for k in want}
    assert got == want, f"bill_number gave {[(k, v) for k, v in got.items() if v != want[k]]}"
    assert RP.roll_call_bill("2010", "S", 32, "SR1") == "SR1" and \
        RP.roll_call_bill("2009", "S", "33", "SR1") == "SR1 (2009)", (
        "roll_call_bill no longer names 2009's SR 1, or names another year's roll call as it")
    d = Path(tempfile.mkdtemp())
    try:
        (d / "RollCallSummary.txt").write_text("\n".join(_RC_MEASURES) + "\n", encoding="utf-8")
        rows = {(r["year"], r["body"], r["number"]): r
                for r in RP.parse(d / "RollCallSummary.txt")}
        assert len(rows) == len(_RC_MEASURES), f"read {len(rows)} of {len(_RC_MEASURES)} rows"
        flags = {r["bill"]: r["procedural"] for r in rows.values()}
        assert flags == {"HA1": False, "HCO1": False, "SSHR1": False, "SR1 (2009)": False,
                         "SSSB1": False, "DRAFT": True, "SSHB1": False, "SSHCR1": False,
                         "SSRULES": True}, f"bills and procedural flags as parsed: {flags}"
        r = _run([sys.executable, _paths.script("rollcall_parser.py"), "--file",
                  "RollCallSummary.txt", "--dir", "none", "--all", "--out", "rc.json"],
                 cwd=d, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, "rollcall_parser failed: " + (r.stderr or r.stdout)[-300:]
        keyed = {t: sorted(b) for t, b in
                 json.loads((d / "rc.json").read_text(encoding="utf-8")).items()}
        assert keyed == {"1999-2000": ["HA1"], "2001-2002": ["HCO1"], "2007-2008": ["SSHR1"],
                         "2009-2010": ["SR1 (2009)", "SSSB1", "_procedural"],
                         "2013-2014": ["SSHB1"], "2015-2016": ["SSHCR1"],
                         "2017-2018": ["_procedural"]}, f"roll calls keyed {keyed}"
        return "ok", ("HA, HCO and special-session votes reach their measures; a draft and "
                      "a rules vote stay procedural; 2009's SR 1 is on no 2010 page")
    finally:
        shutil.rmtree(d, ignore_errors=True)


# Real rows of records/rollcalls/RollCallSummary_2025.txt: SB 287's own Senate
# roll call of 27 March 2025, and the last two of the Senate's 26 June 2025,
# the second of them SB 287's conference report as the file has it, under HB
# 287 (Senate Journal 17, page 940, prints it as SB 287's).
_RC_REFILED = [
    "2025|S|39|3/27/2025 12:00:00 AM|SB287|16|8|24|0|||Ought to Pass|requiring applicants for absentee ballots to present a copy of their photo identification with their application.||3/27/2025 5:21:48 PM",
    "2025|S|116|6/26/2025 12:00:00 AM|HB115|8|16|24|0|||Floor Amendment|(New Title) making temporary appropriations for the expenses and encumbrances of the state of New Hampshire.||6/27/2025 9:19:36 AM",
    "2025|S|117|6/26/2025 12:00:00 AM|HB287|16|8|24|0|||Conference Committee Report|requiring police departments to provide fire departments with certain motorist personal and insurance information following a motor vehicle incident.||6/27/2025 9:16:09 AM",
]


@check("rollcalls", "a roll call a person shows is filed under the wrong bill is keyed to the bill "
       "it belongs to, for the bill's page and the ballots alike, and only while the roll-call file "
       "still files it as the entry says (corrections/rollcall_corrections.json)",
       needs=("rollcall_parser",))
def _rollcall_refiled(RP):
    """P14 of the polish of 26 October 2026: the Senate's 16-8 adoption of
    SB 287's conference report on 26 June 2025 is roll call 117 of 2025 in
    the General Court's file, filed under HB 287, a House bill killed in
    February; HB 287's page carried it and every senator's Votes tab linked
    HB 287. No hand-made file could move a roll call to another bill:
    docket_corrections.json's "misfiled" moves docket rows, and HB 287's
    docket has none for this vote. rollcall_parser.roll_call_bill, where
    rollcalls.json and build_data's ballots both name a roll call's bill,
    now reads corrections/rollcall_corrections.json.

    Driven here by a corrections folder of the check's own in a temporary
    project, never the real one: an entry moves 2025-S-117 to SB 287 in
    parse, through roll_call_bill and in the rollcalls.json the build's own
    command writes; an entry the file no longer bears out (2025-S-39 is SB
    287's already) is not applied and is said; one no file holds is said; a
    malformed entry stops the run; no file changes nothing. Then the
    person's own file, where there is one, is read against the roll-call
    files on disk: an entry that has stopped matching fails here, as a
    docket correction that has stopped matching does."""
    import contextlib
    import io
    keep = (RP.REFILED, dict(RP._REFILED), {k: set(v) for k, v in RP.REFILED_SEEN.items()})

    def reset(path):
        RP.REFILED = path
        RP._REFILED.clear()
        RP.REFILED_SEEN.clear()

    d = Path(tempfile.mkdtemp(prefix="gr-refiled-"))
    try:
        corr = _mk(d / "corrections" / "rollcall_corrections.json")
        entry = {"says": "HB287", "belongs_to": "SB287", "why": "w", "evidence": ["e"],
                 "checked": "2026-10-26"}
        corr.write_text(json.dumps({"misfiled": {
            "2025-S-117": entry, "2025-S-39": dict(entry, says="HB999"),
            "2025-S-500": dict(entry, says="HB1", belongs_to="HB2")}}), encoding="utf-8")
        (d / "RollCallSummary.txt").write_text("\n".join(_RC_REFILED) + "\n", encoding="utf-8")
        reset(corr)
        # The last asks for 2025-S-117 as a file that has since come to say
        # another bill: the entry is out of date and must not move it (the
        # review of 26 October 2026 removed the "says" guard and nothing
        # failed).
        got = [RP.roll_call_bill("2025", "S", 117, "HB287"), RP.roll_call_bill("2025", "S", "117", "HB 287"),
               RP.roll_call_bill("2026", "S", 117, "HB287"), RP.roll_call_bill("2025", "H", 117, "HB287"),
               RP.roll_call_bill("2025", "S", 117, "HB288")]
        assert got == ["SB287", "SB287", "HB287", "HB287", "HB288"], (
            f"roll_call_bill gives 2025-S-117 as typed twice, 2026-S-117, 2025-H-117 and 2025-S-117 "
            f"filed under HB288 as {got}")
        rows = {r["number"]: r for r in RP.parse(d / "RollCallSummary.txt")}
        assert {n: r["bill"] for n, r in rows.items()} == {39: "SB287", 116: "HB115", 117: "SB287"} \
            and not rows[117]["procedural"], f"parse files them under {[(n, r['bill']) for n, r in rows.items()]}"
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            told = RP.refiled_report()
            quiet = RP.refiled_report(complete=False)
        assert told == (["2025-S-117"], ["2025-S-39"], ["2025-S-500"]) and \
            quiet == (["2025-S-117"], ["2025-S-39"], []), (
            f"the report says applied, stale, unread: {told}; where not every file was read {quiet}")
        assert "NOT applied" in out.getvalue() and "did nothing" in out.getvalue(), out.getvalue()
        # The command build_all runs, in the temporary project: it reads the
        # corrections folder of the folder it runs in.
        r = _run([sys.executable, _paths.script("rollcall_parser.py"), "--file", "RollCallSummary.txt",
                  "--dir", "none", "--all", "--out", "rc.json"],
                 cwd=d, capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, "rollcall_parser failed: " + (r.stderr or r.stdout)[-300:]
        keyed = json.loads((d / "rc.json").read_text(encoding="utf-8")).get("2025-2026") or {}
        assert sorted(keyed) == ["HB115", "SB287"] and \
            sorted(x["number"] for x in keyed["SB287"]) == [39, 117], (
            f"rollcalls.json keys 2025-2026 as {[(b, [x['number'] for x in xs]) for b, xs in keyed.items()]}")
        assert "2025-S-117 is filed under HB287 in the roll-call file and drawn under SB287" in r.stdout, (
            "rollcall_parser does not say what the corrections file did: " + r.stdout[-400:])
        # An entry this cannot apply stops the run rather than passing.
        for bad in ({"2025-S-117": dict(entry, belongs_to="HB287")}, {"S-117": entry},
                    {"2025-S-117": dict(entry, says="")}, ["2025-S-117"]):
            corr.write_text(json.dumps({"misfiled": bad}), encoding="utf-8")
            reset(corr)
            try:
                RP.refiled()
            except SystemExit:
                continue
            raise AssertionError(f"rollcall_corrections.json took {bad} rather than refusing it")
        reset(d / "corrections" / "absent.json")
        assert RP.refiled() == {} and RP.roll_call_bill("2025", "S", 117, "HB287") == "HB287", (
            "with no corrections file a roll call still moved")
    finally:
        RP.REFILED = keep[0]
        RP._REFILED.clear()
        RP._REFILED.update(keep[1])
        RP.REFILED_SEEN.clear()
        RP.REFILED_SEEN.update(keep[2])
        shutil.rmtree(d, ignore_errors=True)
    # build_data names every ballot's bill through the same function, and says
    # what the file did, so the members' Votes tabs move with the bill's page;
    # and so does the floor index, so the day's recording moves with them.
    src = _source(_paths.locate("build_data.py"))
    assert "RP.roll_call_bill(r[0], r[1], r[2], r[4])" in src and \
        "RP.refiled_report(complete=False)" in src, (
        "build_data.py no longer names a ballot's bill through rollcall_parser.roll_call_bill, or "
        "no longer says what rollcall_corrections.json did")
    assert "RP.roll_call_bill(p[0], p[1], p[2], p[4])" in \
        _source(_paths.locate("build_floor_index.py")), (
        "build_floor_index.py no longer names a roll call's bill through rollcall_parser.roll_call_bill, "
        "so a roll call a person moved keeps its recording on the bill it was filed under")
    # THE PERSON'S OWN FILE, read and never written: each entry still matches
    # the roll call the files on disk hold (records/rollcalls/ is in git).
    real = _paths.ROOT / "corrections" / "rollcall_corrections.json"
    if not real.is_file():
        return "ok", ("2025-S-117 moves to SB 287 in a project of the check's own, in parse, "
                      "rollcalls.json and roll_call_bill; a stale entry is not applied, a malformed one "
                      "stops; no corrections/rollcall_corrections.json of the person's yet")
    try:
        entries = dict(RP.refiled(real))
    except SystemExit as e:
        raise AssertionError(str(e)) from None
    found, years = {}, set()
    files = sorted((_paths.ROOT / "records" / "rollcalls").glob("RollCallSummary_*.txt"))
    files.append(_paths.ROOT / "RollCallSummary.txt")
    for f in files:
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            p = line.split("|")
            if len(p) < 13 or not p[2].strip().isdigit():
                continue
            k = (p[0].strip().lstrip("﻿"), p[1].strip(), int(p[2]))
            years.add(k[0])
            if k in entries:
                found.setdefault(k, RP.bill_number(p[4]) or p[4].strip())
    bad, unread = [], []
    for k, e in sorted(entries.items()):
        name = f"{k[0]}-{k[1]}-{k[2]}"
        if k not in found:
            (bad if k[0] in years else unread).append(f"{name} is in no roll-call file of {k[0]} here")
        elif found[k] != RP.bill_number(e.get("says")):
            bad.append(f"{name} is filed under {found[k]} in the roll-call file now, not "
                       f"{RP.bill_number(e.get('says'))}: the entry is stale")
    assert not bad, "corrections/rollcall_corrections.json: " + "; ".join(bad)
    return "ok", (f"a project of the check's own moves 2025-S-117 to SB 287, refuses a malformed entry and "
                  f"leaves a stale one; the person's {len(entries)} "
                  f"entr{'y matches' if len(entries) == 1 else 'ies match'} the roll-call files here"
                  + (f" ({'; '.join(unread)})" if unread else ""))


# Every docket and Journal line below is copied from the files on disk, and
# every roll call is a real one with its real number, question, tally and
# ballot count, so each case is a vote that happened and whose outcome a
# Journal on disk confirms.
_RC_DOCKETS = {
    "Docket_db_2011-2012.txt": [
        "2012|2423|03/21/2012 02:52:45 PM|CACR26|H|Ought to Pass: MF RC 237-115 Lacking Necessary Three-Fifths Vote; HJ 28, PG.1684-1686|x",
        "2012|2423|03/21/2012 03:21:03 PM|CACR26|H|Reconsideration of OTP (Rep Hess): MA RC 242-111; HJ 28, PG.1687-1689|x",
        "2012|2423|03/21/2012 03:22:01 PM|CACR26|H|Ought to Pass: MA RC 239-114 By Necessary Three-Fifths Vote; HJ 28, PG.1689-1691|x",
    ],
    "Docket_db_2013-2014.txt": [
        "2014|0624|01/08/2014 09:03:06 AM|HB435|H|Inexpedient to Legislate MA RC 129-156|x",
        "2014|0624|01/08/2014 09:11:48 AM|HB435|H|Inexpedient to Legislate MF RC 132-169|x",
    ],
    "Docket_db_2001-2002.txt": [
        "2002|0661|05/22/2002 01:18:27 PM|SB141|S|Notwithstanding the Governors Veto Shall the Bill Pass, RC 12y - 11n, Veto Sustained; SJ 15, Pg.603|x",
    ],
    "Docket_db_1999-2000.txt": [
        "1999|1041|05/20/1999 01:27:25 PM|HB300|H|Introduced and ref to Finance;  Reps Chandler & Burling moved to Susp Rules for Hearing Notice,|x",
        "1999|1041|05/20/1999 02:03:30 PM|HB300|H|motion failed 2/3RC(219-122);  HJ54, p1461-1464|x",
    ],
    # A row with no outcome of its own borrows the previous row's, but not its
    # words: SB 228's "Motion: OTP" is a majority vote under a suspension.
    "Docket_db_2005-2006.txt": [
        "2005|1083|11/16/2005 03:43:12 PM|SB228|H|Rep O'Neil & Craig Susp Rules for introduction and consideration MA 2/3 VV|x",
        "2005|1083|11/16/2005 03:46:14 PM|SB228|H|Motion: OTP  RC(332-4)  HJ 21, pg 1735|x",
        "2005|1083|11/16/2005 03:49:07 PM|SB228|H|Enrolled;  HJ 21, Pg. 1739|x",
    ],
    # CACR 19's tabling, 17-7 on 14 June, has no RC line of its own; the
    # term-wide fallback must not hand it the 7 June rules suspension's 17-7.
    "Docket_db_2007-2008.txt": [
        "2007|1341|06/07/2007 04:09:16 PM|CACR19|S|Sen. Larsen Rules Suspension 18b,21,22,24,[48a,b,c,d,g,h] for Introduction; 2/3 nec. RC 17Y-7N, MA|x",
        "2007|1341|06/14/2007 01:48:45 PM|CACR19|S|Sen. Kenney Floor Amendment{2149}(New Title) RC 8Y-16N, AF; SJ 23, Pg.703-704|x",
        "2007|1341|06/14/2007 02:18:13 PM|CACR19|S|Ought to Pass RC 14Y-10N, MF, 3/5 nec; SJ 23, Pg.704|x",
        "2007|1341|06/14/2007 02:32:30 PM|CACR19|S|Sen. Gottesman Moved Laid on Table 17Y-7N, MA; SJ 23, Pg.704-705|x",
    ],
    "Docket_2017-2018.txt": [
        "2018|2938|3/15/2018 12:00:00 AM|SB331|S|Inexpedient to Legislate, RC 13Y-11N, MA === BILL KILLED ===; 03/15/2018; SJ 8|x",
        "2018|2938|3/15/2018 12:00:00 AM|SB331|S|Inexpedient to Legislate, RC 13Y-11N, MA === BILL KILLED ===; 03/15/2018; SJ 8|x",
        "2018|2938|3/15/2018 12:00:00 AM|SB331|S|Inexpedient to Legislate, RC 12Y-12N, MF; 03/15/2018; SJ 8|x",
    ],
    "Docket_2023-2024.txt": [
        "2024|2404|2/15/2024 12:00:00 AM|HB1212|H|Reconsider ITL (Rep. Cloutier): MF RC 187-181 02/15/2024 HJ 5 P. 44|x",
    ],
    "Docket.txt": [
        "2026|2956|3/13/2026 11:05:31 AM|CACR25|H|Inexpedient to Legislate: MA RC 176-162 03/12/2026  HJ 8  P. 105|x",
    ],
}
_RC_JOURNALS = {
    # House Journal 6 of 2026, page 142 and the end of the day: a member
    # allowed to continue by three fifths, under that term's rules.
    "journals/2026/HJ 06 March 5, 2026.txt": "\n".join([
        "The question being shall the member continue.",
        "Rep. Wheeler requested a roll call; sufficiently seconded.",
        "Comtois, Barbara      Freeman, Lisa          YEAS 91 - NAYS 82                        Woodcock, Stephen",
        "Paige, David          Jacobs, Samantha              YEAS - 91                         Newell, Jodi",
        "Grant, George      Hemingway, Wayne",
        "",
        "The motion failed lacking the necessary three-fifths vote and with a quorum not being reached, the House",
        "",
        "was adjourned."]),
    # Senate Journal 8 of 2018: the Clerk's note on SB 331's first roll call.
    "journals_senate/2018/SJ008.txt": "\n".join([
        "                               SENATE CLERK'S NOTE",
        "The roll call vote below on SB 331 was inadvertently entered in the Daily",
        "Journal and has been corrected in the Senate Permanent Journal from",
        "12-12 to 13-11.",
        "",
        "The question is on the adoption of the motion of Inexpedient to Legislate.",
        "",
        "Roll Call, Yeas: 13 - Nays: 11. Adopted."]),
}


def _rc_seated(year, body, number, date, bill, q, y, n, seated):
    return {"year": year, "body": body, "number": number, "date": date, "bill": bill,
            "question": q, "question_raw": q, "yeas": y, "nays": n, "seated": seated}


_RC_ROLLS = [
    # 2012 CACR26: 239 of the 397 in office carried it; 3/5 of 400 would not
    _rc_seated("2012", "H", 180, "2012-03-21", "CACR26", "OTP", 237, 115, 397),
    _rc_seated("2012", "H", 181, "2012-03-21", "CACR26", "RECONSIDERATION (REP HESS)", 242, 111, 397),
    _rc_seated("2012", "H", 182, "2012-03-21", "CACR26", "OTP", 239, 114, 397),
    # 2026 CACR25: killing a CACR is a majority question (HJ 8: adopted)
    _rc_seated("2026", "H", 215, "2026-03-12", "CACR25", "ITL", 176, 162, 392),
    # 2014 HB435: the docket's MA is wrong (HJ 5: "the majority committee report failed")
    _rc_seated("2014", "H", 15, "2014-01-08", "HB435", "ITL", 129, 156, 394),
    _rc_seated("2014", "H", 16, "2014-01-08", "HB435", "ITL", 132, 169, 394),
    # 2024 HB1212: the docket's MF is wrong (HJ 5: "the motion was adopted")
    _rc_seated("2024", "H", 60, "2024-02-15", "HB1212", "Reconsider", 187, 181, 396),
    # 2002 SB141: a veto override worded the old way
    _rc_seated("2002", "S", 138, "2002-05-22", "SB141",
        "Not withstanding the Governor's Veto-shall the bill pass", 12, 11, 24),
    # 2018 SB331: three votes, paired in order; the first corrected (SJ 8)
    _rc_seated("2018", "S", 106, "2018-03-15", "SB331", "Inexpedient to Legislate", 12, 12, 24),
    _rc_seated("2018", "S", 107, "2018-03-15", "SB331", "Inexpedient to Legislate", 13, 11, 24),
    _rc_seated("2018", "S", 108, "2018-03-15", "SB331", "Inexpedient to Legislate", 12, 12, 24),
    # 2025: a rules suspension with no bill and no docket line (HJ 5: failed, two thirds)
    _rc_seated("2025", "H", 21, "2025-02-13", None, "Rules Suspension", 199, 176, 399),
    # 1999 HB300: "SUSP RULES", the roll-call file's abbreviation (HJ 17: failed, two thirds)
    _rc_seated("1999", "H", 103, "1999-05-20", "HB300",
        "REPS CHANDLER & BURLING:  SUSP RULES FOR HEARING", 219, 122, 399),
    # 2026: no docket line, and a threshold only that term's rules and the Journal know
    _rc_seated("2026", "H", 132, "2026-03-05", None, "Shall Member Continue", 91, 82, 392),
    # 2005 SB228: a majority vote, whatever the row above it needed
    _rc_seated("2005", "H", 152, "2005-11-16", "SB228", "MOTION:  OTP", 332, 4, 396),
    # 2007 CACR19: an amendment, three fifths to pass, and a tabling no RC line names
    _rc_seated("2007", "S", 168, "2007-06-14", "CACR19", "Floor Amendment (2149s) Sen. Kenney/Sen. Burling",
        8, 16, 24),
    _rc_seated("2007", "S", 169, "2007-06-14", "CACR19", "Ought to Pass Sen. Clegg/Sen. Foster", 14, 10, 24),
    _rc_seated("2007", "S", 170, "2007-06-14", "CACR19", "Laid on Table Sen. Sgambati/Sen. Reynolds",
        17, 7, 24),
]


# The real rows of records/rollcalls/RollCallSummary_1999.txt: the Senate's
# votes of 22 October 1999 on CACR 16 and CACR 17, the middle one dated 2009
# by the file, though it was entered the same morning as the others, 25
# October 1999.
_RC_MISDATED = [
    "1999|S|108|10/22/1999 12:00:00 AM|CACR16|17|6|23|0|||Order to 3rd Reading3/5 Necessary|relating to use of statewide property and personal income taxes.||10/25/1999 10:29:09 AM",
    "1999|S|109|10/22/2009 12:00:00 AM|CACR17|15|8|23|0|||Order to 3rd Reading3/5 Necessary|relating to establishing a restricted education trust fund.||10/25/1999 10:26:07 AM",
    "1999|S|110|10/22/1999 12:00:00 AM|CACR16|12|9|23|0|||Final Passage3/5 Necessary|relating to use of statewide property and personal income taxes.||10/25/1999 10:26:57 AM",
]


@check("rollcalls", "a roll call a person shows is misdated is drawn on the day the record gives, "
       "for rollcalls.json, the ballots and the floor index alike, and only while the roll-call "
       "file still gives the day the entry says (corrections/rollcall_corrections.json)",
       needs=("rollcall_parser",))
def _rollcall_misdated(RP):
    """THE DEEP WALK OF 6 NOVEMBER 2026. Roll call 1999-S-109 is dated 22
    October 2009 in the General Court's file. CACR 17's docket dates the
    15-8 vote to order it to third reading 22 October 1999; the file itself
    entered it on 25 October 1999, the morning it entered 1999-S-108 and
    1999-S-110, both dated 22 October 1999; and it is the only one of
    2,303,047 ballots dated outside its term. CACR 17's Votes tab and 23 senators' own drew it as
    2009, and the six who sat only in 1999-2000 read "1999 to 2009". The
    person's file could move a roll call to another bill ("misfiled") and
    not to another day; "misdated" does, read by
    rollcall_parser.roll_call_when wherever a roll call's day is read.

    Driven here by a corrections folder of the check's own in a temporary
    project, never the real one: an entry dates 1999-S-109 22 October 1999
    in roll_call_when and in parse, keeping its time; an entry the file no
    longer bears out is not applied and is said; one no file holds is said;
    a malformed entry, or one without evidence, stops the run; no file
    changes nothing."""
    import contextlib
    import io
    keep = (RP.REFILED, dict(RP._MISDATED), {k: set(v) for k, v in RP.MISDATED_SEEN.items()},
            dict(RP._REFILED))

    def reset(path):
        RP.REFILED = path
        RP._MISDATED.clear()
        RP._REFILED.clear()
        RP.MISDATED_SEEN.clear()

    d = Path(tempfile.mkdtemp(prefix="gr-misdated-"))
    try:
        corr = _mk(d / "corrections" / "rollcall_corrections.json")
        entry = {"says": "10/22/2009", "is": "10/22/1999",
                 "evidence": "CACR 17's docket dates the 15-8 vote 10/22/1999", "checked": "2026-11-07"}
        corr.write_text(json.dumps({"misdated": {
            "1999-S-109": entry, "1999-S-108": dict(entry, says="10/23/1999", **{"is": "10/22/1999"}),
            "1999-S-500": entry}}), encoding="utf-8")
        (d / "RollCallSummary.txt").write_text("\n".join(_RC_MISDATED) + "\n", encoding="utf-8")
        reset(corr)
        got = [RP.roll_call_when("1999", "S", 109, "10/22/2009 12:00:00 AM"),
               RP.roll_call_when("1999", "S", "109", "10/22/2009"),
               RP.roll_call_when("1999", "H", 109, "10/22/2009 12:00:00 AM"),
               RP.roll_call_when("1999", "S", 109, "10/23/2009 12:00:00 AM"),
               RP.roll_call_when("1999", "S", 110, "10/22/1999 12:00:00 AM")]
        assert got == ["10/22/1999 12:00:00 AM", "10/22/1999", "10/22/2009 12:00:00 AM",
                       "10/23/2009 12:00:00 AM", "10/22/1999 12:00:00 AM"], (
            f"roll_call_when gives 1999-S-109 twice, 1999-H-109, 1999-S-109 dated another day and "
            f"1999-S-110 as {got}")
        rows = {r["number"]: r for r in RP.parse(d / "RollCallSummary.txt")}
        assert {n: r["date"] for n, r in rows.items()} == \
            {108: "1999-10-22", 109: "1999-10-22", 110: "1999-10-22"}, (
            f"parse dates them {[(n, r['date']) for n, r in rows.items()]}")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            told = RP.misdated_report()
            quiet = RP.misdated_report(complete=False)
        assert told == (["1999-S-109"], ["1999-S-108"], ["1999-S-500"]) and \
            quiet == (["1999-S-109"], ["1999-S-108"], []), (
            f"the report says applied, stale, unread: {told}; where not every file was read {quiet}")
        assert "NOT applied" in out.getvalue() and "did nothing" in out.getvalue(), out.getvalue()
        # An entry this cannot apply stops the run rather than passing.
        for bad in ({"1999-S-109": dict(entry, **{"is": "10/22/2009"})}, {"S-109": entry},
                    {"1999-S-109": dict(entry, says="2009-10-22")},
                    {"1999-S-109": dict(entry, evidence="")}, ["1999-S-109"]):
            corr.write_text(json.dumps({"misdated": bad}), encoding="utf-8")
            reset(corr)
            try:
                RP.misdated()
            except SystemExit:
                continue
            raise AssertionError(f"rollcall_corrections.json took {bad} rather than refusing it")
        # "misfiled" alone, as the person's file has it today: nothing moves.
        corr.write_text(json.dumps({"misfiled": {}}), encoding="utf-8")
        reset(corr)
        assert RP.misdated() == {} and \
            RP.roll_call_when("1999", "S", 109, "10/22/2009 12:00:00 AM") == "10/22/2009 12:00:00 AM"
        reset(d / "corrections" / "absent.json")
        assert RP.misdated() == {}, "with no corrections file a roll call still moved"
    finally:
        RP.REFILED = keep[0]
        RP._MISDATED.clear()
        RP._MISDATED.update(keep[1])
        RP.MISDATED_SEEN.clear()
        RP.MISDATED_SEEN.update(keep[2])
        RP._REFILED.clear()
        RP._REFILED.update(keep[3])
        shutil.rmtree(d, ignore_errors=True)
    # Every reader of a roll call's day beside its bill reads it through the
    # same function, and the two that report say what the file did.
    src = _source(_paths.locate("build_data.py"))
    assert '"datetime": RP.roll_call_when(r[0], r[1], r[2], r[3])' in src and \
        "RP.misdated_report(complete=False)" in src, (
        "build_data.py no longer dates a ballot through rollcall_parser.roll_call_when, or no "
        "longer says what rollcall_corrections.json's misdated did")
    assert "RP.roll_call_when(p[0], p[1], p[2], p[3])" in \
        _source(_paths.locate("build_floor_index.py")), (
        "build_floor_index.py no longer dates a roll call through rollcall_parser.roll_call_when")
    src = _source(_paths.locate("rollcall_parser.py"))
    assert "roll_call_when(year, body, num, p[3])" in src and "    misdated_report()" in src, (
        "rollcall_parser.parse no longer dates a roll call through roll_call_when")
    # THE PERSON'S OWN FILE, where there is one, against the files on disk.
    real = _paths.ROOT / "corrections" / "rollcall_corrections.json"
    files = sorted((_paths.ROOT / "records" / "rollcalls").glob("RollCallSummary_*.txt"))
    if not real.is_file() or not RP.misdated(real):
        return "ok", ("1999-S-109 is drawn on 22 October 1999 while the file dates it 2009, and "
                      "not once the file stops; a stale or unread entry is said; a malformed one "
                      "stops; the person's file has no misdated entry")
    seen = {}
    for f in files:
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            p = line.split("|")
            if len(p) > 3 and REFILED_ROW.fullmatch("|".join(p[:3])):
                seen[(p[0], p[1], int(p[2]))] = RP._file_day(p[3])
    stale = [f"{k[0]}-{k[1]}-{k[2]}" for k, e in RP.misdated(real).items()
             if seen.get(k) is not None and seen.get(k) != RP._file_day(e.get("says"))]
    assert not stale, f"rollcall_corrections.json's misdated entries no longer match the files: {stale}"
    return "ok", (f"{len(RP.misdated(real))} misdated entr(ies) in the person's file, each matching "
                  "the roll-call files on disk; the made-up cases hold")


REFILED_ROW = re.compile(r"\d{4}\|[HS]\|\d+")

# (passed, threshold_needed, outcome_source), as the Journals record them
_RC_WANT = {
    ("2012", 180): (False, 239, "docket"), ("2012", 181): (True, None, "docket"),
    ("2012", 182): (True, 239, "docket"), ("2026", 215): (True, None, "docket"),
    ("2014", 15): (False, None, "count"), ("2014", 16): (False, None, "docket"),
    ("2024", 60): (True, None, "count"), ("2002", 138): (False, 16, "docket"),
    ("2018", 106): (True, None, "journal"), ("2018", 107): (True, None, "docket"),
    ("2018", 108): (False, None, "docket"), ("2025", 21): (False, 250, "rule"),
    ("1999", 103): (False, 228, "rule"), ("2026", 132): (False, None, "journal"),
    ("2005", 152): (True, None, "docket"), ("2007", 168): (False, None, "docket"),
    ("2007", 169): (False, 15, "docket"), ("2007", 170): (True, None, "rule"),
}


@check("rollcalls", "the clerk's recorded outcome decides a roll call; three fifths "
       "is of the members in office", needs=("rollcall_outcomes",))
def _rollcall_outcomes(rollcall_outcomes):
    """What a roll call decided is what the General Court recorded.

    rollcall_parser used to decide it by rule, and the rule was wrong three
    ways: three fifths on every motion about a CACR (2026's CACR25 kill,
    "fell 64 short" of a bar it never faced), three fifths of the 400 seats
    rather than of the members in office (239 of 397 carried CACR 26 in 2012,
    and the site said Failed), and a veto override known by two wordings of
    its question (SB 141 of 2002, sustained, said Adopted). A rules
    suspension written "SUSP RULES" was not known at all, and a vote no
    docket line names -- a member allowed to continue in March 2026 -- has
    its threshold only in that term's rules and its outcome only in the
    Journal.

    This fails on a return to seats, to CACR-wide three fifths, to a narrow
    veto or suspension vocabulary, or to the rule where the Journal speaks.
    """
    RO = rollcall_outcomes
    d = Path(tempfile.mkdtemp())
    try:
        for name, lines in _RC_DOCKETS.items():
            (d / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        for name, text in _RC_JOURNALS.items():
            (d / name).parent.mkdir(parents=True, exist_ok=True)
            (d / name).write_text(text + "\n", encoding="utf-8")
        rolls = [dict(r) for r in _RC_ROLLS]
        RO.apply(rolls, root=d)
        by = {(r["year"], r["number"]): r for r in rolls}
        bad = []
        for k, want in _RC_WANT.items():
            r = by[k]
            got = (r["passed"], r["threshold_needed"], r["outcome_source"])
            if got != want:
                bad.append(f"{k[0]}-{r['body']}-{k[1]} {r['bill']}: got {got}, want {want}")
        assert not bad, "; ".join(bad)
        notes = [r.get("threshold_note") or "" for r in rolls]
        assert not any("entire" in x or "seats" in x for x in notes), (
            "a threshold note still counts the seats: "
            + "; ".join(x for x in notes if "entire" in x or "seats" in x))
        assert by[("2012", 182)]["threshold_note"] == (
            "Needed 239 — three fifths of the 397 members in office."), (
            by[("2012", 182)]["threshold_note"])
        assert "two thirds of the 23 members voting" in (
            by[("2002", 138)]["threshold_note"] or ""), by[("2002", 138)]["threshold_note"]
        sb331 = by[("2018", 106)]["outcome_conflict"] or ""
        assert "Senate Clerk's note" in sb331 and "13–11" in sb331, (
            f"SB 331's 12-12 ballots against the Permanent Journal's 13-11 are "
            f"not explained: {sb331!r}")
        assert not by[("2018", 108)]["outcome_conflict"], (
            "the Clerk's note corrected the FIRST 12-12 roll call, not the second")
        for k in (("2014", 15), ("2024", 60)):
            assert by[k]["outcome_conflict"], f"{k}: the docket's impossible outcome went unremarked"
        member = by[("2026", 132)]
        assert member.get("threshold_unknown") and "three fifths" in (
            member.get("threshold_note") or ""), (
            "a threshold the Journal names without a count must be said in its "
            f"words and drawn with no mark: {member}")
        return "ok", (f"{len(rolls)} real votes decided as the Journals record them, "
                      "from the docket, the Journal, the count or the rule")
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check("rollcalls", "a division is marked against what a roll call on the same question "
       "needs: three fifths of the members in office for a CACR, two thirds where the "
       "docket says so", needs=("rollcall_outcomes", "build_site_v2"))
def _division_thresholds(RO, B):
    """The language sweep of 17 October 2026: CACR 13's House chart said "171
    needed", a majority of the 340 voting, where the docket says "MA DV 325-15
    By Necessary Three-Fifths Vote" and three fifths of the 394 members in
    office that day was 237. Bill pages took a threshold from the roll-call
    file only, and a division is not in it, so every division was marked at a
    majority -- 174 of them, 1989-2026, needed more.

    This fails if a division goes back to a majority mark, if three fifths is
    taken of those voting rather than of the members in office, if a fraction
    named for another count on the same docket line is borrowed, or if a
    CACR's division with no count of members in office is given a number."""
    cacr13 = "Ought to Pass: MA DV 325-15 By Necessary Three-Fifths Vote 02/05/2026"
    got = RO.division_threshold("CACR13", "Ought to Pass", cacr13, 325, 15, 394, True)
    assert (got.get("threshold_needed"), got.get("threshold_rule")) == (
        237, "three fifths of the 394 members in office"), got
    # No roll call that day, so no count of the members in office: no number.
    got = RO.division_threshold("CACR25", "Third Reading", "3RD READING MA DIV(280-17); HJ27,P859",
                                280, 17, None, True)
    assert got.get("threshold_unknown") and not got.get("threshold_needed"), got
    # Two thirds is of those voting, and a suspension needs it unnamed.
    got = RO.division_threshold(
        "HB1426", "Susp Rules for New Conf Comm",
        "Rep Welch Susp Rules for New Conf Comm, MA 2/3DIV(258-58); House Acceded", 258, 58,
        390, True)
    assert got.get("threshold_needed") == 211, got
    # A majority question keeps the majority mark.
    assert RO.division_threshold("HB1", "Ought to Pass", "Ought to Pass: MA DV 200-150", 200,
                                 150, 390, True) == {}
    # A fraction named for the next count on the line is not this one's.
    got = RO.division_threshold(
        "CACR9", "Adopt Committee Amendment",
        "Amendment #2128h: AA DIV 200-100; Ought to Pass: MF DIV 201-150 Lacking Necessary "
        "Three-Fifths", 200, 100, 390, True)
    assert got == {}, got
    # THE REVIEW OF 17 OCTOBER 2026. A CACR's passage is three fifths of the
    # members in office whatever fraction the docket line names (2025's CACR
    # 8, "Lacking Necessary Two-Thirds Vote"; HJ 14: "3/5ths").
    got = RO.division_threshold(
        "CACR8", "Ought to Pass",
        "Ought to Pass: MF DV 203-158 Lacking Necessary Two-Thirds Vote 05/08/2025", 203, 158,
        398, False)
    assert (got.get("threshold_needed"), got.get("threshold_rule")) == (
        239, "three fifths of the 398 members in office"), got
    # The 1989-1998 dockets' bare "ADOPTED" of a CACR's report is its passage.
    got = RO.division_threshold("CACR25", "Adopt", "ADOPTED DIV(278-67); HJ27,P834", 278, 67,
                                None, True)
    assert got.get("threshold_unknown"), got
    # A fraction the docket names over a suspension's two thirds.
    got = RO.division_threshold(
        "CACR2", "Susp Rules for 3rd reading",
        "Rep Chandler Susp Rules for 3rd reading, MA by nec 3/5 DIV(286-43); HJ35", 286, 43,
        398, True)
    assert got.get("threshold_needed") == 239, got
    # The Journal's sentence, where the docket line names no fraction.
    d = Path(tempfile.mkdtemp())
    try:
        (d / "journals" / "2000").mkdir(parents=True)
        (d / "journals" / "2000" / "HJ012.txt").write_text(
            "Rep. Mock moved that CACR 2 be removed from the table.\n\nOn a division vote, 251 "
            "members having voted in the affirmative and 87 in the negative, the motion\nwas "
            "adopted by the necessary three-fifths.\n", encoding="utf-8")
        said = RO.journal_division_words(d, "H", "2000-04-13", 251, 87)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    assert "three-fifths" in said, said
    got = RO.division_threshold("CACR2", "Taken from the Table",
                                "Taken from the Table, Rep Mock MA DIV(251-87)", 251, 87, 398,
                                True, said)
    assert got.get("threshold_needed") == 239, got
    # Three fifths named of a question that is not a CACR: of those voting.
    got = RO.division_threshold(
        "HB1414", "Special Order HB1414",
        "Special Order HB1414 (Rep. Huot): MA DV 236-137 By Necessary 3/5 03/21/2024", 236, 137,
        390, True)
    assert (got.get("threshold_needed"), got.get("threshold_rule")) == (
        224, "three fifths of the 373 members voting"), got
    rolls = {"2025-2026": {"_procedural": [
        {"body": "H", "date": "2026-02-05", "seated": 394},
        {"body": "H", "date": "2026-02-05", "seated": 394},
        {"body": "H", "date": "2026-02-05", "seated": 39}]}}
    office = RO.members_in_office(rolls)
    assert office == {("H", "2026-02-05"): 394}, office
    rec = {"events": [{"date": "2026-02-05", "type": "floor", "body": "H", "raw": cacr13,
                       "action": "Ought to Pass", "motion": "MA", "vote_kind": "DV",
                       "yeas": "325", "nays": "15", "cancelled": False}]}
    cards = [v for v in B.bill_rollcalls("CACR13", "2025-2026", [], rec, {}, [], set(), office)
             if v.get("vote_kind") == "DV"]
    assert cards and cards[0].get("threshold_needed") == 237 and "237" in (
        cards[0].get("threshold_note") or ""), (
        f"CACR 13's division on its Votes tab: {cards}")
    return "ok", "a CACR's division is marked at 237 of 394, not 171 of 340"


@check("data", "every roll call's outcome is the one the record gives it",
       needs=("rollcall_outcomes",))
def _rollcall_outcomes_data(rollcall_outcomes):
    """The built rollcalls.json against the dockets and Journals on disk.

    Re-deciding every roll call and comparing is the whole check: it fails
    on a rollcalls.json built before the outcome was read from the record,
    on one built by code that has since changed, and -- through the counts
    below -- on a docket that silently stopped being read. The conflicts are
    the votes where the record and the ballots disagree; there were seven
    when this was written, each explained on its page, and a new one is for
    a person to look at.
    """
    RO = rollcall_outcomes
    p = Path("rollcalls.json")
    if not p.exists():
        return "skip", "no rollcalls.json here"
    if not RO.docket_paths("."):
        return "skip", "no Docket*.txt here"
    data = json.loads(p.read_text(encoding="utf-8"))
    rolls = [r for bills in data.values() for rows in bills.values() for r in rows]
    missing = sum(1 for r in rolls if "outcome_source" not in r)
    assert not missing, (
        f"{missing:,} of {len(rolls):,} roll calls carry no outcome_source: "
        "rollcalls.json predates the recorded outcome. Rebuild it with "
        "python3 src/parse/rollcall_parser.py --file RollCallSummary.txt --all --out rollcalls.json")
    fresh = [dict(r) for r in rolls]
    RO.apply(fresh, root=".")
    moved = [f'{r["year"]}-{r["body"]}-{r["number"]}' for r, f in zip(rolls, fresh)
             if (bool(r.get("passed")), r.get("threshold_needed"), r.get("outcome_source"))
             != (bool(f["passed"]), f["threshold_needed"], f["outcome_source"])]
    assert not moved, (
        f"{len(moved)} roll calls in rollcalls.json are not what the record on "
        f"disk decides now -- rebuild it. First few: {', '.join(moved[:5])}")
    billed = [r for r in rolls if r.get("bill")]
    from_docket = sum(1 for r in billed if (r.get("outcome_source") or "").startswith("docket"))
    assert from_docket >= 0.9 * len(billed), (
        f"only {from_docket:,} of {len(billed):,} roll calls on a bill took their "
        "outcome from the docket; the pairing or the outcome reader has stopped "
        "working")
    conflicts = [f'{r["year"]}-{r["body"]}-{r["number"]}' for r in rolls
                 if r.get("outcome_conflict")]
    assert len(conflicts) <= 7, (
        f"{len(conflicts)} roll calls where the record and the ballots disagree, "
        "against seven when this check was written; a person should read the "
        "new ones: " + ", ".join(conflicts))
    seats = [r for r in rolls if "entire" in (r.get("threshold_note") or "")]
    assert not seats, f"{len(seats)} threshold notes still count the seats"
    return "ok", (f"{len(rolls):,} roll calls as the record decides them; "
                  f"{from_docket:,} of {len(billed):,} on a bill from the docket, "
                  f"{len(conflicts)} conflicts explained on their pages")


@check("rollcalls", "floor_markers matches a spoken tally to the record")
def _tally_match():
    if not _paths.locate("floor_markers.py").exists():
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
        r = _run([sys.executable, _paths.script("floor_markers.py"),
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


@check("rollcalls", "a roll call the docket names as a rules suspension needs two thirds",
       needs=("rollcall_outcomes",))
def _rollcall_suspend_from_docket(RO):
    """The same 181-121 suspension on a bill's Votes tab: the roll call's
    own question may name only what the suspension was for, so the docket's
    words for the tally decide. A suspension carried by voice before a
    passage roll call on the same line leaves the passage at a majority."""
    r = {"yeas": 181, "nays": 121, "question_raw": "Transmittal", "bill": "HB1"}
    got, _ = RO.threshold(r, "Suspend the Rules for transmittal, MF, RC 181-121")
    assert got == 202, f"a suspension 181-121 on the Votes tab needs {got}, not 202"
    assert RO.threshold(r, "OTP, MF, RC 181-121") == (None, None), "Ought to Pass is a majority"
    after = "Susp Rules for 3rd reading, MA VV, OT3rdg, Passed RC 181-121"
    assert RO.threshold(r, after) == (None, None), \
        "a passage roll call after a voice-vote suspension is drawn at two thirds"
    assert RO.threshold(r, "Reconsider Susp Rules, MF, RC 181-121") == (None, None)
    return "ok", "named on the docket 181-121 needs 202; the passage after one needs a majority"


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


@check("rollcalls", "after the turn a ballot of a finished term names its member from the nearest frozen "
       "roster at or after it, never the House Organization Day installed", needs=("build_data",))
def _ballot_member_after_turn(build_data):
    """The rehearsal of the turn, 19 November 2026: with the fake 2027 House
    installed, Rep. Peter Bixby's 2024 ballots took the party that roster gave
    him (R, not the D he voted under), so the Learn page's HB 1002 split
    stopped agreeing with the ballots. Only a finished term's OWN frozen
    roster was read for a ballot, and an older term's took the installed one.
    build_data.ballot_member decides it now, and here on four members: B, of
    D in 2023-2026 and R in the installed House; P, Independent on the
    former list, absent from the 2025-2026 roster and sitting again as a D;
    N, new in 2027; and the ballots of Organization Day 2024 (2025-2026's)
    and 2026 (2027-2028's)."""
    bm = build_data.ballot_member
    legs = {"B": {"party_code": "R", "seat": "now"}, "P": {"party_code": "D", "seat": "now"},
            "N": {"party_code": "R", "seat": "now"}}
    froze = {"B": {"party_code": "D", "seat": "2025-2026"}}
    rosters = [("2025-2026", froze)]
    former = {"P": {"name": "P", "party": "I"}}
    case = {
        # (member, session year, day): what names the ballot
        ("B", "2024", "3/7/2024 10:00:00 AM"): froze["B"],    # an older term: the nearest frozen roster
        ("B", "2022", "1/5/2022 10:00:00 AM"): froze["B"],
        ("B", "2026", "5/21/2026 10:00:00 AM"): froze["B"],    # the finished term's own roster
        ("B", "2024", "12/4/2024 1:00:38 PM"): froze["B"],    # Organization Day 2024 is 2025-2026's
        ("B", "2026", "12/2/2026 1:00:00 PM"): legs["B"],     # Organization Day 2026 is the new House's
        ("B", "2027", "1/7/2027 10:15:33 AM"): legs["B"],
        ("P", "2024", "3/7/2024 10:00:00 AM"): None,          # not in 2025-2026: the former list, as before
        ("P", "2027", "1/7/2027 10:15:33 AM"): legs["P"],
        ("N", "2027", "1/7/2027 10:15:33 AM"): legs["N"],
        ("X", "2024", "3/7/2024 10:00:00 AM"): None,          # nobody sitting: the former list
    }
    bad = [f"{k}: {bm(k[0], k[1], k[2], legs, rosters, former)} where {v}"
           for k, v in case.items() if bm(k[0], k[1], k[2], legs, rosters, former) is not v]
    assert not bad, "a ballot named from the wrong roster: " + "; ".join(bad)
    # Before any turn there is no frozen roster to read: the installed one names every ballot.
    assert all(bm(k[0], k[1], k[2], legs, [], former) is legs.get(k[0])
               for k in case), "with no frozen roster a ballot was not named from the installed one"
    return "ok", (f"{len(case)} ballots of 2022-2027 each named from its own roster, the nearest "
                  "frozen one after it, the former list, or the installed House for its own term")


@check("build", "the live Worker reads a roll call's bill field as the record does: every field in "
       "records/rollcalls/ and the procedural ones (SUSPRULE, RULE 1-2, HRULE64) give merge.js's "
       "billNumber what rollcall_parser.bill_number gives", needs=("rollcall_parser",))
def _live_bill_number(RP):
    """The live file's `bill` is the term and the bill the record would file
    the roll call under, or null where the field names no bill: a procedural
    vote written "2025-2026/SUSPRULE" is a link to nothing, and breaks
    schema/session.votes.json. The patterns reach the Worker through
    live.gen.js (BILL_NUMBER); this holds the whole function equal."""
    root = Path(".")
    fields = {"SUSPRULE", "RULE 1-2", "HRULE64", "SEN/RULE", "SR1 (2009)", "SSRULES", "REPORT", "",
              "HB 1", "hb1", "HB1-FN", "HB 1-FN-A", "HB1-FN-LOCAL", "HCACR13", "CACR 13", "SSSB 1", "HA1",
              "HCO2", "HR 10", "SCR3", "HJR1", "SJR 2", "HB1-L", "SB12-A", "HB", "1", "HBX1"}
    for f in sorted((root / "records/rollcalls").glob("RollCallSummary*.txt")):
        for line in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            q = line.split("|")
            if len(q) >= 13:
                fields.add(q[4])
    fields = sorted(fields)
    want = [RP.bill_number(x) for x in fields]
    node = shutil.which("node")
    assert node, "node is not on PATH, and the Worker's billNumber is the thing held here"
    src = ("import { billNumber } from " + json.dumps((root.resolve() / "workers/live/merge.js").as_uri())
           + ";\nlet s = ''; process.stdin.on('data', d => s += d); process.stdin.on('end', () => "
           "process.stdout.write(JSON.stringify(JSON.parse(s).map(billNumber))));\n")
    r = _run([node, "--input-type=module", "-e", src], input=json.dumps(fields),
             capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, f"node could not read the fields: {(r.stderr or r.stdout).strip()[-400:]}"
    got = json.loads(r.stdout)
    differ = [f"{x!r}: the Worker {g!r}, the record {w!r}" for x, g, w in zip(fields, got, want) if g != w]
    assert not differ, f"{len(differ)} bill fields read apart: " + "; ".join(differ[:5])
    none = sum(1 for w in want if not w)
    assert none >= 8, f"only {none} fields name no bill: the procedural cases are not being read"
    return "ok", f"{len(fields):,} bill fields read alike, {none} of them naming no bill"


@check("rollcalls", "a declared conflict of interest reaches the member's vote row marked as one",
       needs=("rollcall_parser",))
def _ballot_conflict(rollcall_parser):
    """Code 5 is a declared conflict of interest, and attendance counts the
    member present for it. The site's word for it is "No vote recorded", which
    an empty ballot shares, so the flag travels beside the word from the one
    place that reads the code -- and build_data has to put it on the row, or
    attendance never sees it and every conflict is an absence again."""
    RP = rollcall_parser
    got = {c: RP.ballot(c) for c in ("5", " 5 ", "7", "", "Yea", "Not Voting/Excused")}
    assert got["5"] == got[" 5 "] == {"vote": RP.NO_VOTE, "conflict": True}, got
    assert got["7"] == {"vote": RP.NO_VOTE} and got[""] == {"vote": ""} \
        and got["Yea"] == {"vote": "Yea"}, f"only code 5 is a conflict: {got}"
    src = _source(_paths.locate("build_data.py"))
    assert "**RP.ballot(r[6])" in src, (
        "build_data.py no longer puts rollcall_parser.ballot's fields on each member vote "
        "row, so no conflict reaches attendance")
    return "ok", "code 5 flagged as a conflict, code 7 and an empty code not; build_data puts it on the row"


# The votes data stage (build_votes.py, 12 November 2026).

_BANNED_VOTES = [re.compile("party" + r"[- ]" + "line", re.I),
                 re.compile("other way from most of " + "their party", re.I)]


def _votes_brute_flip(y, n, need):
    """Voters who would have had to switch for the outcome to change, found by
    switching them one at a time: need None is a majority (a tie is not one),
    "2/3" two thirds of those voting, a number the yeas a question needed."""
    tot = y + n

    def out(yy):
        if need is None:
            return yy > tot - yy
        if need == "2/3":
            return 3 * yy >= 2 * tot
        return yy >= need
    base, k = out(y), 0
    while k <= tot:
        k += 1
        if (y - k >= 0 and out(y - k) != base) or (y + k <= tot and out(y + k) != base):
            return k
    return None


@check("code", "votes data: the number of voters who would have had to switch is the elections' rule against the "
       "roll call's own threshold, a close vote is 5 or fewer, and an unknown threshold is no flip", needs=("build_votes",))
def _votes_flips(BV):
    seen = 0
    for tot in range(1, 31):
        for y in range(tot + 1):
            n = tot - y
            cases = [({}, None), ({"threshold_needed": -(-2 * tot // 3),
                                   "threshold_rule": f"two thirds of the {tot} members voting"}, "2/3")]
            for need in {max(1, (3 * tot + 4) // 5), tot // 2 + 2}:
                cases.append(({"threshold_needed": need,
                               "threshold_rule": f"three fifths of the {tot} members in office"}, need))
            for extra, bneed in cases:
                need = extra.get("threshold_needed")
                if bneed is None:
                    carried = y > n
                elif bneed == "2/3":
                    carried = 3 * y >= 2 * tot
                else:
                    carried = y >= need
                r = dict(extra, yeas=y, nays=n, passed=carried)
                got, want = BV.flips(r), _votes_brute_flip(y, n, bneed)
                assert got == want, f"{y}-{n} {extra}: flips {got}, a recount by switching one at a time {want}"
                seen += 1
    # A tie is not a majority: one switch carries it, and one undoes a one-vote win.
    assert BV.flips({"yeas": 5, "nays": 5, "passed": False}) == 1
    assert BV.flips({"yeas": 6, "nays": 5, "passed": True}) == 1
    # Unknown: the Journal says it needed more and not how many; an outcome the count does not give.
    assert BV.flips({"yeas": 91, "nays": 82, "passed": False, "threshold_unknown": True}) is None
    assert BV.flips({"yeas": 12, "nays": 10, "passed": False}) is None
    assert BV.flips({"yeas": 12, "nays": 12, "passed": True}) is None
    assert BV.flips({"yeas": 0, "nays": 0, "passed": True}) is None
    # The rule is the elections' own, not a second copy.
    BE = BV.BE
    assert BV.flips({"yeas": 40, "nays": 20, "passed": True, "threshold_needed": 40,
                     "threshold_rule": "two thirds of the 60 members voting"}) == BE.flip_two_thirds(40, 20)
    assert BV.flips({"yeas": 7, "nays": 5, "passed": True}) == BE.flip_majority(7, 5)

    def close(y, n, body="H"):
        return BV.row_of({"year": "2026", "body": body, "number": 1, "date": "2026-01-01", "yeas": y,
                          "nays": n, "passed": y > n, "question": "Ought to Pass"}, "HB1", {}).get("cl")
    assert close(15, 6) and not close(16, 5) and close(8, 8), (
        "a House vote is close at 5 or fewer voters from changing the outcome")
    assert BV.CLOSE_HOUSE == 5 and BV.CLOSE_SENATE == 2
    assert close(14, 10, "S") and not close(15, 9, "S") and close(12, 12, "S"), (
        "a Senate vote is close at 2 or fewer voters from changing the outcome")
    return "ok", f"{seen:,} tallies under a majority, two thirds and three fifths agree with a recount by switching voters"


def _votes_fixture():
    def rc(num, body, y, n, **kw):
        r = {"year": "2026", "body": body, "number": num, "date": f"2026-02-{num:02d}", "bill": "HB1",
             "question": "Ought to Pass", "question_plain": "pass the bill", "yeas": y, "nays": n,
             "passed": y > n, "excused": 1, "not_excused": 0, "presiding": 0, "no_vote_recorded": 0}
        r.update(kw)
        return r
    rolls = {"2025-2026": {"HB1": [rc(1, "H", 3, 1), rc(2, "H", 2, 2, passed=False),
                                   rc(3, "S", 2, 1, yeas_stated=3, nays_stated=1)],
                           "_procedural": [rc(4, "H", 3, 0, bill=None, procedural=True, question="Suspend the Rules")]},
             "2023-2024": {"SB2": [dict(rc(1, "S", 2, 0, bill="SB2"), year="2024", date="2024-03-01")]}}

    def v(mid, code, num, body="H", year="2026", party="R"):
        return {"member_id": mid, "party": party, "year": year, "body": body, "vote_number": str(num), "vote": code}
    Y, N, E = "Yea", "Nay", "Not Voting/Excused"
    ballots = [v("10", Y, 1), v("11", Y, 1, party="D"), v("12", Y, 1), v("13", N, 1, party="D"), v("14", E, 1),
               v("10", Y, 2), v("11", N, 2, party="D"), v("12", Y, 2), v("13", N, 2, party="D"), v("14", E, 2),
               v("20", Y, 3, "S"), v("21", Y, 3, "S"), v("22", N, 3, "S"), v("23", E, 3, "S"),
               v("10", Y, 4), v("11", Y, 4, party="D"), v("12", Y, 4), v("14", E, 4),
               v("20", Y, 1, "S", "2024"), v("21", Y, 1, "S", "2024"), v("22", E, 1, "S", "2024")]
    return rolls, ballots


@check("code", "votes data: a file a term, the counted tally tied to its ballots, the stated one carried, a vote on "
       "no bill Procedural, no word of a party's position", needs=("build_votes",))
def _votes_files(BV):
    rolls, ballots = _votes_fixture()
    with tempfile.TemporaryDirectory() as td:
        rows, enc, rep = BV.build(rolls, iter(ballots), td)
        assert sorted(rep["files"]) == ["2023-2024.json", "2025-2026.json", "ballots-2023-2024.json",
                                        "ballots-2025-2026.json", "index.json"], rep["files"]
        ix = json.loads((Path(td) / "votes" / "index.json").read_text(encoding="utf-8"))
        assert ix["terms"] == ["2025-2026", "2023-2024"] and ix["from"] == "2023" \
            and ix["close"] == {"H": BV.CLOSE_HOUSE, "S": BV.CLOSE_SENATE} \
            and sum(sum(c.values()) for c in ix["counts"].values()) == len(
                [x for rs in rows.values() for x in rs]), ix
        t = json.loads((Path(td) / "votes" / "2025-2026.json").read_text(encoding="utf-8"))["rolls"]
        by = {x["id"]: x for x in t}
        assert [x["id"] for x in t] == ["2026-H-1", "2026-H-2", "2026-S-3", "2026-H-4"], [x["id"] for x in t]
        b = json.loads((Path(td) / "votes" / "ballots-2025-2026.json").read_text(encoding="utf-8"))["chambers"]
        assert b["H"]["m"] == ["10", "11", "12", "13", "14"] and b["H"]["r"]["2026-H-1"] == "YYYNE", b["H"]
        assert b["H"]["r"]["2026-H-4"] == "YYY.E" and b["S"]["r"]["2026-S-3"] == "YYNE", b
        for x in t:                                                  # every counted tally is its ballots'
            s = b[x["c"]]["r"][x["id"]]
            assert (s.count("Y"), s.count("N")) == (x["y"], x["n"]), x
        assert by["2026-S-3"]["ys"] == 3 and by["2026-S-3"]["ns"] == 1 and by["2026-S-3"]["y"] == 2, by["2026-S-3"]
        assert "ys" not in by["2026-H-1"]
        assert by["2026-H-4"]["k"] == "Procedural" and by["2026-H-4"]["b"] == "" \
            and by["2026-H-1"]["k"] == "Committee report"
        assert by["2026-H-2"]["f"] == 1 and by["2026-H-2"]["cl"] == 1 \
            and by["2026-H-1"]["pc"] == [1, 1, 2, 0], (by["2026-H-2"], by["2026-H-1"])
        assert json.loads((Path(td) / "votes" / "2023-2024.json").read_text(
            encoding="utf-8"))["rolls"][0]["id"] == "2024-S-1"
        text = "".join(p.read_text(encoding="utf-8") for p in (Path(td) / "votes").glob("*.json"))
        for rx in _BANNED_VOTES:
            assert not rx.search(text), f"a built votes file says {rx.pattern}"
        # A stale term is removed.
        (Path(td) / "votes" / "1999-2000.json").write_text("{}", encoding="utf-8")
        BV.build(rolls, iter(ballots), td)
        assert not (Path(td) / "votes" / "1999-2000.json").exists()
        # A ballot twice, a word with no letter, and a tally the ballots do not give all stop the build.
        for bad, why in (([*ballots, ballots[0]], "two ballots"),
                         ([dict(ballots[0], vote="Maybe"), *ballots[1:]], "no letter"),
                         (ballots[1:], "do not count")):
            try:
                BV.build(rolls, iter(bad), td)
            except (ValueError, SystemExit) as e:
                assert why in str(e), (why, str(e))
            else:
                raise AssertionError(f"a build with {why} went through")
        # The streamed reader gives what json.load gives, across chunk boundaries.
        p = Path(td) / "mv.json"
        p.write_text(json.dumps(ballots), encoding="utf-8")
        assert list(BV.stream_array(p, chunk=7)) == ballots and list(BV.stream_array(p)) == ballots
        p.write_text("[]", encoding="utf-8")
        assert list(BV.stream_array(p)) == []
    src = _source("src/pages/build_votes.py")
    for rx in _BANNED_VOTES:
        assert not rx.search(src), f"build_votes.py carries {rx.pattern}"
    return "ok", "files by term, tallies tied, stated tallies carried, procedural named, no party's position"


@check("frontend", "the votes page: every filter round-trips through the address, a row passes the filters its "
       "data says, a member's ballots count to the row's tally, and the page says what it covers (roll calls "
       "from 1999) and labels no vote by party")
def _votes_page():
    js = Path("src/pages/app.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and Path("tests/dom_stub.js").exists() and node
            and Path("src/pages/build_votes_page.py").exists()):
        return "skip", "app.js, dom_stub.js, node or build_votes_page.py is not here"
    src = _source(js)
    block = src[src.index("THE VOTES PAGE ====="):]
    # THE OWNER'S DECISION OF 12 NOVEMBER 2026: no label of how the parties divided, no mark on a member
    # who voted against theirs, and nothing of a party's counts (pc) is read by the page.
    for rx in (re.compile("bi" + "partisan", re.I), re.compile("party" + r"[- ]" + "line", re.I),
               re.compile("against (?:their|his|her) " + "party", re.I),
               re.compile("other way from most of " + "their party", re.I),
               re.compile(r"\.pc\b|\bpc\s*[:\[]")):
        assert not rx.search(block), f"the votes page carries {rx.pattern}"
    sys.path.insert(0, "src/pages")
    try:
        import build_votes_page as VPG
    finally:
        sys.path.pop(0)
    said = VPG.LEAD + " " + VPG.NOTE + " " + VPG.DESC + " " + VPG.body()
    assert "from 1999" in VPG.LEAD, "the page does not say what it covers"
    for rx in (re.compile(r"before 1999", re.I), re.compile(r"no recorded votes", re.I),
               re.compile("bi" + "partisan|party" + r"[- ]" + "line", re.I)):
        assert not rx.search(said), f"the votes page says {rx.pattern}"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source("tests/dom_stub.js"), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") +
  "; ({votesRead,votesAddr,votesPass,votesLetter,votesClose,votesDefault,votesActive,VT})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const terms = ["2025-2026", "2023-2024"], out = {bad: []};
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
for (const qs of ["", "?q=hb+1442", "?term=all&margin=close&body=H",
    "?from=2024-03-01&to=2024-03-31&result=failed&kind=Amendment&member=daryl-abbas-sd-22&sort=close&q=x",
    "?term=2023-2024", "?from=2023-01-01&to=2026-01-01", "?q=a+b&sort=new", "?q=a&term=all",
    "?kind=Passage&kind=Amendment&body=S&body=H&margin=tied&margin=close&result=failed&result=passed"]) {
  const st = s.votesRead(qs, terms), a = s.votesAddr(st, terms), st2 = s.votesRead(a, terms);
  if (!same(st, st2)) out.bad.push(["round trip", qs, a, st, st2]);
  if (qs === "" && a !== "") out.bad.push(["a bare page has an address", a]);
}
if (s.votesAddr(s.votesRead("?from=2024-03-01", terms), terms) !== "from=2024-03-01")
  out.bad.push(["a day names its term", s.votesAddr(s.votesRead("?from=2024-03-01", terms), terms)]);
// A filter of boxes is each value the address names, once, in the filter's own order; a single value,
// as every link before the boxes wrote it, is that one box.
out.many = s.votesAddr(s.votesRead("?kind=Passage&kind=Amendment&kind=Passage&body=S&body=H&margin=tied&margin=close" +
  "&result=failed&result=passed&kind=Nope", terms), terms);
out.one = [s.votesRead("?body=H", terms).body, s.votesRead("?kind=Veto+override", terms).kind,
  s.votesRead("?margin=tied", terms).margin, s.votesRead("?result=failed", terms).result];
const junk = s.votesRead("?body=X&result=zz&term=1850-1851&kind=Nope&margin=q&from=notaday", terms);
if (!same(junk, s.votesDefault(terms))) out.bad.push(["a value it does not know is a filter", junk]);
// Rows and ballots: three House roll calls and one Senate, five House members and two Senators.
const rows = [
  {id: "2025-H-1", d: "2025-01-08", c: "H", b: "HB1", k: "Passage", p: 1, y: 3, n: 1, t: "2025-2026", cl: 1, f: 1},
  {id: "2025-H-2", d: "2025-02-08", c: "H", b: "", k: "Procedural", p: 0, y: 2, n: 2, t: "2025-2026"},
  {id: "2025-H-3", d: "2025-03-08", c: "H", b: "HB3", k: "Amendment", p: 1, y: 4, n: 0, t: "2025-2026"},
  {id: "2025-S-1", d: "2025-01-30", c: "S", b: "SB4", k: "Passage", p: 1, y: 1, n: 1, t: "2025-2026", cl: 1, f: 1}];
s.VT.bal["2025-2026"] = {chambers: {
  H: {m: ["10", "11", "12", "13", "14"], r: {"2025-H-1": "YYYN.", "2025-H-2": "YYNN.", "2025-H-3": "YYYYE"}},
  S: {m: ["20", "21"], r: {"2025-S-1": "YN"}}}};
const st = s.votesDefault(terms);
for (const r of rows) {
  const l = s.votesLetter(r, r.c === "H" ? ["10", "999"] : ["20"]);
  if (!l) out.bad.push(["a member on the roll call has no letter", r.id]);
}
// Every counted tally is the ballots' count, through the page's own reader.
for (const r of rows) {
  const ids = r.c === "H" ? ["10", "11", "12", "13", "14"] : ["20", "21"];
  const ls = ids.map(i => s.votesLetter(r, [i]));
  const y = ls.filter(x => x === "Y").length, n = ls.filter(x => x === "N").length;
  if (y !== r.y || n !== r.n) out.bad.push(["ballots do not count to the tally", r.id, y, n]);
}
const pass = (over, ids) => rows.filter(r => s.votesPass(r, Object.assign({}, st, over), ids || null)).map(r => r.id);
out.close = pass({margin: ["close"]}); out.tied = pass({margin: ["tied"]}); out.house = pass({body: ["H"]});
out.failed = pass({result: ["failed"]}); out.kind = pass({kind: ["Amendment"]}); out.days = pass({from: "2025-02-01", to: "2025-03-01"});
out.either = pass({margin: ["close", "tied"]}); out.both = pass({body: ["H", "S"]});
out.kinds = pass({kind: ["Amendment", "Procedural"]});
out.m14 = pass({}, ["14"]); out.m20 = pass({}, ["20"]); out.m1 = pass({}, ["12"]);
out.words = s.votesClose(rows[0]) + "|" + s.votesClose(rows[1]) + "|" + s.votesClose(rows[2]);
process.stdout.write("\\n@@" + JSON.stringify(out));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js's votes page did not run under node: " + (r.stderr or r.stdout or "")[-400:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert not got["bad"], f"{got['bad'][:2]}"
    want = {"close": ["2025-H-1", "2025-S-1"], "tied": ["2025-H-2", "2025-S-1"], "house": ["2025-H-1", "2025-H-2", "2025-H-3"],
            "failed": ["2025-H-2"], "kind": ["2025-H-3"], "days": ["2025-H-2"],
            "either": ["2025-H-1", "2025-H-2", "2025-S-1"], "both": ["2025-H-1", "2025-H-2", "2025-H-3", "2025-S-1"],
            "kinds": ["2025-H-2", "2025-H-3"],
            "m14": ["2025-H-3"], "m20": ["2025-S-1"], "m1": ["2025-H-1", "2025-H-2", "2025-H-3"]}
    for k, v in want.items():
        assert got[k] == v, f"the filter {k} gave {got[k]}, not {v}"
    assert got["many"] == ("body=H&body=S&result=passed&result=failed&margin=close&margin=tied"
                           "&kind=Amendment&kind=Passage"), (
        f"the boxes an address ticks are written back as {got['many']!r}: each value once, in its filter's order")
    assert got["one"] == [["H"], ["Veto override"], ["tied"], ["failed"]], (
        f"a link's one value is not its one box: {got['one']}")
    assert got["words"].startswith("Close: 1 voter would have had to switch|Tied|"), got["words"]
    return "ok", ("address round trip, a value a parameter for each filter of boxes and one value its box, "
                  "filters, ballots tie to tallies, 1999 scope wording, no party label")


# THE VOTES PAGE AS A READER MET IT (the review of 14 November 2026, on the preview): a session
# day's search found none of the roll calls the file dates a day later; "veto" found no veto
# override; a former member or dates in 2003 showed "0 votes in 2025-2026"; nothing on a phone said
# whose votes these were; an unknown member hung the page; the Member box lost what was typed when
# the members' lists arrived; a bill voted only by voice led to /votes and nothing. Run in node
# against dom_stub.js, through the functions the page draws with.
_VOTES_READER_JS = r"""
require("./stub.js");
const fs = require("fs");
// The page's listeners, kept where the stub drops them, so a check can fire one.
const HEARD = {};
document.addEventListener = (t, f) => { (HEARD[t] = HEARD[t] || []).push(f); };
const route = {};
globalThis.fetch = async u => {
  const k = Object.keys(route).find(x => String(u).endsWith(x));
  const v = k ? route[k] : [];
  return {ok: true, status: 200, json: async () => v, text: async () => JSON.stringify(v)};
};
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") +
  "; ({votesRead, votesAddr, votesPass, votesRowsOf, votesRowHtml, votesTermOf, votesDefault," +
  " votesControls, votesFacets, votesDraw, votesNeedPeople, votesChange, voteGroups, renderVotes, VT, IDX, LOADED," +
  " sit: x => { SITDAYS = x; }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const tick = async n => { for (let i = 0; i < (n || 6); i++) await new Promise(r => setImmediate(r)); };
(async () => {
const out = {};
const terms = ["2025-2026", "2023-2024", "2021-2022", "2019-2020", "2003-2004", "2001-2002", "1999-2000"];
// A SESSION DAY: read and written back, its term, and Organization Day's.
const d = s.votesRead("?day=2021-02-24&body=H", terms);
out.dayTerm = d.term; out.dayAddr = s.votesAddr(d, terms);
out.org = [s.votesTermOf("2022-12-07", terms), s.votesTermOf("2022-12-06", terms), s.votesTermOf("2024-12-04", terms)];
const rows = [
  {id: "2021-H-1", d: "2021-02-26", s: "2021-02-24", c: "H", b: "HB1", mk: "otp", k: "Committee report", q: "Ought to Pass", p: 1, y: 3, n: 1, t: "2021-2022"},
  {id: "2021-H-30", d: "2021-02-26", s: "2021-02-25", c: "H", b: "HB2", mk: "otp", k: "Committee report", q: "Ought to Pass", p: 1, y: 3, n: 1, t: "2021-2022"},
  {id: "2021-S-53", d: "2021-02-18", s: "", c: "S", b: "", mk: "", k: "Procedural", q: "Attendance", p: 1, y: 20, n: 0, t: "2021-2022"},
  {id: "2021-S-54", d: "2021-02-18", c: "S", b: "SB5", mk: "otp", k: "Committee report", q: "Ought to Pass", p: 1, y: 14, n: 10, t: "2021-2022"}];
const st0 = s.votesDefault(terms);
const pass = over => rows.filter(r => s.votesPass(r, Object.assign({}, st0, over), null)).map(r => r.id);
out.day24 = pass({day: "2021-02-24", body: ["H"]}); out.day25 = pass({day: "2021-02-25", body: ["H"]});
out.day18 = pass({day: "2021-02-18", body: ["S"]}); out.file26 = pass({from: "2021-02-26", to: "2021-02-26"});
s.sit({H: new Set(["2021-02-24", "2021-02-25"]), S: new Set(["2021-02-18"]), rc: {}});
out.link1 = s.votesRowHtml(rows[0], 0, ""); out.link3 = s.votesRowHtml(rows[2], 2, "");
// THE TERM FOLLOWS the dates and the member, in the address as on the page.
s.VT.idx = {terms, close: {H: 5, S: 2}, counts: {}};
s.VT.people = [
  {slug: "sylvia-larsen-sd-15", m: {display_plain: "Sen. Sylvia Larsen", slug: "sylvia-larsen-sd-15"}, ids: ["205035"],
   terms: ["1999-2000", "2001-2002"], hay: "sen sylvia larsen", former: true},
  {slug: "one-term-rep", m: {display_plain: "Rep. One Term", slug: "one-term-rep"}, ids: ["77"], terms: ["2003-2004"],
   hay: "rep one term", former: true},
  {slug: "jane-doe", m: {display_plain: "Rep. Jane Doe", slug: "jane-doe"}, ids: ["10"], terms: null,
   hay: "rep jane doe", former: false}];
s.VT.peopleAsked = true;
out.memTerm = ["sylvia-larsen-sd-15", "one-term-rep", "jane-doe"].map(m => s.votesRead("?member=" + m, terms).term);
const lar = s.votesRead("?member=sylvia-larsen-sd-15", terms);
out.larAddr = s.votesAddr(lar, terms);
out.larBack = s.votesRead("?" + out.larAddr, terms).term;
s.VT.st = s.votesRead("", terms);
s.votesChange("from", "2003-02-01");
const a1 = s.votesAddr(s.VT.st, terms);
out.changed = [s.VT.st.term, a1, s.votesRead("?" + a1, terms).term];
// THE MEMBER NAMED, AND WHAT THEY VOTED ON COUNTED: on three roll calls, yea on one, excused on one,
// nay on one, and not on the fourth.
s.VT.rows["2025-2026"] = [
  {id: "2025-H-1", d: "2025-01-08", c: "H", b: "", mk: "", k: "Procedural", q: "Lay on Table", p: 0, y: 1, n: 1, t: "2025-2026"},
  {id: "2025-H-2", d: "2025-01-09", c: "H", b: "", mk: "", k: "Procedural", q: "Adjourn", p: 1, y: 1, n: 0, t: "2025-2026"},
  {id: "2025-H-3", d: "2025-01-10", c: "H", b: "", mk: "", k: "Procedural", q: "Recess", p: 1, y: 1, n: 1, t: "2025-2026"},
  {id: "2025-H-4", d: "2025-01-11", c: "H", b: "", mk: "", k: "Procedural", q: "Recess", p: 1, y: 1, n: 0, t: "2025-2026"}];
s.VT.bal["2025-2026"] = {chambers: {H: {m: ["10", "11"], r: {"2025-H-1": "YN", "2025-H-2": "EY", "2025-H-3": "NY", "2025-H-4": ".Y"}}}};
s.VT.st = s.votesRead("?member=jane-doe&term=2025-2026", terms);
s.votesDraw();
out.count = document.getElementById("vcount").textContent;
await tick();
// AN UNKNOWN MEMBER is dropped once the members' lists arrive, and the page reads on.
s.VT.people = null; s.VT.peopleAsked = false;
route["legislators.json"] = [{slug: "jane-doe", id: "10", display_plain: "Rep. Jane Doe"}];
route["former.json"] = [];
s.VT.st = s.votesRead("?member=no-such-person&term=2025-2026", terms);
s.votesDraw();
const before = document.getElementById("vcount").textContent;
await tick(12);
out.unknown = [before, s.VT.st.member, document.getElementById("vcount").textContent];
// "veto" FINDS A VOTE BY ITS QUESTION, "fish" still by its bill.
s.VT.by = {};
s.IDX.push({id: "HB10", term: "2025-2026", year: 2025, n: "HB 10", title: "relative to fish and game licenses",
  hayT: "hb10 hb 10 relative to fish and game licenses", hayC: "fish and game"});
s.LOADED.add("2025-2026");
const vr = [
  {id: "2025-H-90", d: "2025-09-18", c: "H", b: "HB10", mk: "override_second", k: "Veto override", q: "Veto Override", p: 0, y: 200, n: 150, t: "2025-2026"},
  {id: "2025-H-20", d: "2025-03-18", c: "H", b: "HB10", mk: "otp", k: "Committee report", q: "Ought to Pass", p: 1, y: 200, n: 150, t: "2025-2026"}];
const ask = q => s.votesRowsOf(vr.slice(), Object.assign({}, st0, {q}), s.voteGroups(q, s.IDX.filter(b => b.term === "2025-2026")),
  null, null).map(r => r.id).sort();
out.veto = ask("veto"); out.fish = ask("fish"); out.amend = ask("amendment");
// A VOTE ON NO BILL SAYS ITS QUESTION ONCE; an unnamed motion's result is in the Result filter's words; a
// bill the index does not hold is written as the site writes a number.
const nb1 = {id: "2023-H-9", d: "2023-05-04", c: "H", b: "", w: "Affirm the Committee Report (Censure Rep. Spillane)",
  q: "Affirm The Report", mk: "", k: "Procedural", p: 1, y: 300, n: 20, t: "2023-2024"};
const nb2 = {id: "2023-H-10", d: "2023-05-04", c: "H", b: "", w: "Printing in the Journal", q: "Personal Priviledge",
  mk: "", k: "Procedural", p: 1, y: 300, n: 20, t: "2023-2024"};
const other = {id: "2002-S-142", d: "2002-06-27", c: "S", b: "SB457", mk: "", k: "Other", q: "Sections 3 and 4",
  p: 1, y: 14, n: 10, t: "2001-2002"};
out.nb1 = s.votesRowHtml(nb1, 0, ""); out.nb2 = s.votesRowHtml(nb2, 1, ""); out.other = s.votesRowHtml(other, 2, "");
// A BILL'S VOTES TAB leads to /votes only where it has a roll call, by its bare number.
const bill = {id: "HB2", n: "HB 2-FN-A-L", year: 2025, term: "2025-2026"};
out.voiceOnly = s.renderVotes(bill, {rollcalls: [{question: "Ought to Pass", date: "2025-03-01", body: "H",
  vote_kind: "VV", passed: true}]});
out.withRc = s.renderVotes(bill, {rollcalls: [{question: "Ought to Pass", date: "2025-03-01", body: "H",
  passed: true, yeas: 200, nays: 150, tally: {}, members: []}]});
// THE FILTERS DRAWN AGAIN WHEN THE MEMBERS ARRIVE keep what is typed in the Member box, the focus and
// its caret; the Filter button is the page's own and no drawing of the filters writes it; the close-vote
// rule is above the list only while Margin asks for close votes. The letters are typed through the
// page's own handler (the votes page's listeners, heard where the stub would drop them).
window.GR_VOTES = true;
const box = {id: "vmem", value: "lar", selectionStart: 3, selectionEnd: 3, focused: 0,
  focus() { this.focused++; }, setSelectionRange(a, b) { this.range = [a, b]; }};
const side = {id: "vfacets", _html: "", scrollTop: 0, contains: n => n === box, querySelectorAll: () => []};
Object.defineProperty(side, "innerHTML", {get() { return side._html; }, set(v) { side._html = String(v); }});
const shut = {id: "vclose", hidden: true, textContent: ""};
const byId = document.getElementById.bind(document);
document.getElementById = id => ({vfacets: side, vmem: box, vclose: shut})[id] || byId(id);
s.VT.st = s.votesRead("", terms);
(HEARD.input || []).filter(f => /GR_VOTES/.test(String(f))).forEach(f => f({target: box}));
document.activeElement = box;
s.VT.drawn = "";
s.votesControls(); s.votesFacets(null, null);
out.ctl = side._html; out.focused = box.focused; out.range = box.range || null;
out.closeShut = [shut.hidden, shut.textContent];
s.VT.st = s.votesRead("?margin=close", terms);
document.activeElement = null;
s.votesControls();
out.closeOpen = [shut.hidden, shut.textContent];
process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.constructor.name + ": " + e.message); process.exit(1); });
"""


@check("frontend", "the votes page as a reader met it: a session day's roll calls by the day its page "
       "gives them, the date linked to that day; the term follows the dates and the member; the member "
       "named and what they voted on counted; an unknown member dropped; a vote found by its question; "
       "the controls keep what is typed; a bill with no roll call does not lead to /votes")
def _votes_page_reads():
    js = Path("src/pages/app.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and Path("tests/dom_stub.js").exists() and node
            and Path("src/pages/build_votes_page.py").exists()):
        return "skip", "app.js, dom_stub.js, node or build_votes_page.py is not here"
    sys.path.insert(0, "src/pages")
    try:
        import build_votes_page as VPG
    finally:
        sys.path.pop(0)
    # The lead is one sentence, and does not list the filters drawn under it.
    assert VPG.LEAD.count(". ") == 0 and VPG.LEAD.endswith(".") and "narrow" not in VPG.LEAD, (
        f"the votes page's lead is {VPG.LEAD!r}: one sentence, the filters left to speak for themselves")
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source("tests/dom_stub.js"), encoding="utf-8")
        (root / "go.js").write_text(_VOTES_READER_JS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=90)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js's votes page did not run under node: " + (r.stderr or r.stdout or "")[-400:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    bad = []
    # A session day is the roll calls its page counts (`s`), not the roll calls of its date.
    if (got["dayTerm"], got["dayAddr"]) != ("2021-2022", "body=H&day=2021-02-24"):
        bad.append(f"?day=2021-02-24&body=H reads as term {got['dayTerm']} and writes back {got['dayAddr']!r}")
    if got["org"] != ["2023-2024", "2021-2022", "2025-2026"]:
        bad.append(f"Organization Day's terms are {got['org']}, not the next term's from the first "
                   "Wednesday of December of an even year")
    for k, want in (("day24", ["2021-H-1"]), ("day25", ["2021-H-30"]), ("day18", ["2021-S-54"]),
                    ("file26", ["2021-H-1", "2021-H-30"])):
        if got[k] != want:
            bad.append(f"the filter {k} lists {got[k]}, not {want}")
    if '<a href="session/H/2021-02-24">Feb 26, 2021</a>' not in got["link1"]:
        bad.append("a roll call the file dates 26 February and the page of 24 February counts does not show "
                   "the file's date linked to that page: " + got["link1"][:160])
    if 'href="session/' in got["link3"]:
        bad.append("a roll call no session page counts links its date to a page that does not draw it")
    # The term follows the member and the dates, and the address opens on what was on screen.
    if got["memTerm"] != ["all", "2003-2004", "2025-2026"]:
        bad.append(f"a member of two terms, of one term and a sitting member open on {got['memTerm']}")
    if (got["larAddr"], got["larBack"]) != ("member=sylvia-larsen-sd-15", "all"):
        bad.append(f"a former member's address is {got['larAddr']!r}, read back as {got['larBack']}")
    if got["changed"] != ["2003-2004", "from=2003-02-01", "2003-2004"]:
        bad.append(f"dates in 2003 picked on the page leave the term, the address and its reading at "
                   f"{got['changed']}")
    # Whose votes, and what they voted on.
    if got["count"] != "Rep. Jane Doe voted yea or nay on 2 of 3 roll calls in 2025–2026":
        bad.append(f"the count line with a member reads {got['count']!r}")
    if got["unknown"][1:] != ["", "4 votes in 2025–2026"]:
        bad.append(f"/votes?member=no-such-person: {got['unknown']}")
    # A vote is found by its question and kind; its bill's words still find it.
    if (got["veto"], got["fish"], got["amend"]) != (["2025-H-90"], ["2025-H-20", "2025-H-90"], []):
        bad.append(f"'veto' finds {got['veto']}, 'fish' {got['fish']} and 'amendment' {got['amend']}")
    # Said once; one set of result words; a number as the site writes it.
    if 'class="vq"' in got["nb1"] or 'class="vq">Personal Priviledge' not in got["nb2"]:
        bad.append("a vote on no bill draws its question under the Journal's words where it says nothing more, "
                   "or not where it does")
    if "SB 457" not in got["other"] or "Motion Passed" not in got["other"] or ">Adopted<" in got["other"]:
        bad.append("an unnamed motion's row: " + got["other"][:240])
    # A bill's Votes tab: the votes page only for a roll call, by the bare number.
    if "Find these votes" in got["voiceOnly"]:
        bad.append("a bill voted only by voice leads to the votes page")
    if 'href="votes?q=HB+2&amp;term=2025-2026">Find these votes on the votes page' not in got["withRc"]:
        bad.append("a bill with a roll call does not lead to /votes?q=HB+2&term=2025-2026: "
                   + (re.search(r'<p class="src vlink">.*?</p>', got["withRc"], re.S) or [""])[0][:200])
    # The filters keep what is in hand; the Filter button is the page's, which no drawing writes.
    if 'id="vmem"' not in got["ctl"] or 'value="lar"' not in got["ctl"] or got["focused"] != 1 \
            or got["range"] != [3, 3]:
        bad.append("the filters drawn again lose the Member box's letters, its focus or caret "
                   f"(focused {got['focused']}, caret {got['range']})")
    toggle = '<button class="ftoggle" id="vftoggle" type="button" aria-expanded="false" aria-controls="vfacets">'
    if toggle not in VPG.body() or "vftoggle" in got["ctl"]:
        bad.append("the Filter button is not the page's own, written once, where no drawing of the filters "
                   "can set it shut over a panel that is open")
    if got["closeShut"][0] is not True or got["closeOpen"][0] is not False \
            or not got["closeOpen"][1].startswith("Close: 5 or fewer House voters"):
        bad.append(f"the close-vote rule is not above the list only while Margin asks for close votes: "
                   f"{got['closeShut']} {got['closeOpen']}")
    assert not bad, "; ".join(bad[:4])
    return "ok", ("?day= lists the roll calls its page counts and links the file's date to it; the term "
                  "follows dates, a day and a member, in the address alike; the member is named and their "
                  "yeas and nays counted; an unknown member is dropped; 'veto' finds an override; the Member "
                  "box keeps its letters and focus; a voice-only bill has no link")


# THE VOTES PAGE'S FILTERS AS THE BILL SEARCH'S (the owner on the bench, 24 November 2026: "The votes
# page filters should be more similar to the left sidebar search filters on bill and law pages"; 25
# November, start it). A term of seven roll calls and a term of two, a member's ballots, and every
# address the page read before its filters were a sidebar, each drawn through votesDraw in node against
# dom_stub.js; and the bill search's own sidebar drawn beside them, to compare their markup with.
_VSIDE_ROWS = {
    "2025-2026": [
        {"id": "2025-H-1", "d": "2025-01-08", "c": "H", "b": "HB1", "k": "Committee report", "q": "Ought to Pass",
         "p": 1, "y": 200, "n": 150, "f": 26},
        {"id": "2025-H-2", "d": "2025-01-08", "c": "H", "b": "HB2", "k": "Amendment", "q": "Adopt the amendment",
         "p": 0, "y": 170, "n": 172, "f": 2, "cl": 1},
        {"id": "2025-H-3", "d": "2025-02-12", "c": "H", "b": "", "w": "Suspend the rules", "k": "Procedural",
         "q": "Suspend the Rules", "p": 0, "y": 180, "n": 180, "f": 1, "cl": 1},
        {"id": "2025-S-1", "d": "2025-01-30", "c": "S", "b": "SB4", "k": "Passage", "q": "Pass the bill",
         "p": 1, "y": 14, "n": 10, "f": 3},
        # A tie a question needing two thirds lost by four: tied, and not close.
        {"id": "2025-S-2", "d": "2025-02-20", "c": "S", "b": "SB5", "k": "Veto override", "q": "Override the veto",
         "p": 0, "y": 12, "n": 12, "f": 4},
        {"id": "2025-S-3", "d": "2025-03-05", "c": "S", "b": "SB6", "k": "Amendment", "q": "Adopt the amendment",
         "p": 1, "y": 13, "n": 11, "f": 2, "cl": 1},
        # Dated the 6th by the file and counted on the 5th's session page.
        {"id": "2025-H-4", "d": "2025-03-06", "s": "2025-03-05", "c": "H", "b": "HB7", "k": "Passage",
         "q": "Pass the bill", "p": 1, "y": 300, "n": 50, "f": 126}],
    "2023-2024": [
        {"id": "2023-H-1", "d": "2023-02-01", "c": "H", "b": "HB8", "k": "Committee report", "q": "Ought to Pass",
         "p": 0, "y": 100, "n": 250, "f": 76},
        {"id": "2024-S-1", "d": "2024-04-04", "c": "S", "b": "SB9", "k": "Passage", "q": "Pass the bill",
         "p": 1, "y": 20, "n": 4, "f": 9}]}
# Rep. Jane Doe, member 10: yea on H-1, excused on H-2, nay on H-3, not on H-4.
_VSIDE_JANE = {"2025-H-1": "Y", "2025-H-2": "E", "2025-H-3": "N", "2025-H-4": "."}
# Every address the page read before the sidebar, each with what it means; and a few the boxes make.
_VSIDE_CASES = [
    ("", {}), ("?body=H", {"body": ["H"]}), ("?body=S", {"body": ["S"]}),
    ("?result=failed", {"result": ["failed"]}), ("?result=passed", {"result": ["passed"]}),
    ("?margin=close", {"margin": ["close"]}), ("?margin=tied", {"margin": ["tied"]}),
    ("?kind=Amendment", {"kind": ["Amendment"]}), ("?kind=Veto+override", {"kind": ["Veto override"]}),
    ("?from=2025-02-01&to=2025-02-28", {"from": "2025-02-01", "to": "2025-02-28"}),
    ("?from=2025-03-06", {"from": "2025-03-06"}),
    ("?day=2025-03-05&body=H", {"day": "2025-03-05", "body": ["H"]}),
    ("?member=jane-doe", {"member": "jane-doe"}), ("?q=HB2", {"q": "HB2"}),
    ("?term=2023-2024", {"term": "2023-2024"}), ("?term=all&kind=Passage", {"term": "all", "kind": ["Passage"]}),
    ("?sort=close", {"sort": "close"}),
    ("?kind=Amendment&kind=Passage&body=S", {"kind": ["Amendment", "Passage"], "body": ["S"]}),
    ("?margin=close&margin=tied&result=failed", {"margin": ["close", "tied"], "result": ["failed"]})]
_VSIDE_GROUPS = [("body", "Chamber"), ("dates", "Dates"), ("result", "Result"), ("margin", "Margin"),
                 ("kind", "Kind of Question"), ("member", "Member")]
_VSIDE_TICKS = ("body", "result", "margin", "kind")

_VOTES_SIDE_JS = r"""
require("./stub.js");
const fs = require("fs");
const HEARD = {};
document.addEventListener = (t, f) => { (HEARD[t] = HEARD[t] || []).push(f); };
const wrote = [];
history.replaceState = (a, b, u) => { wrote.push(String(u)); location.search = String(u).includes("?") ? "?" + String(u).split("?")[1] : ""; };
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") +
  "; ({votesRead, votesAddr, votesDraw, votesControls, votesFacets, votesOpenFor, VT, renderFacets, sel," +
  " openGroups, LOADED, setRCX: v => { RCX = v; }, setMeta: m => { META = m; }, setTerm: t => { term = t; }," +
  " setRows: r => { IDX = r; }})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
const out = {cases: {}, events: {}};
(async () => {
const terms = ["2025-2026", "2023-2024"], rcx = {};
s.VT.idx = {terms, close: {H: 5, S: 2}, counts: {}};
for (const [t, rows] of Object.entries(fx.rows)) {
  s.VT.rows[t] = rows.map(r => Object.assign({t}, r));
  rows.forEach(r => { rcx[r.id] = {y: r.y, n: r.n}; });
}
s.setRCX(rcx);
// Both terms' bill indexes are taken as here, so no row waits on one (votesWants).
s.LOADED.add("2025-2026"); s.LOADED.add("2023-2024");
s.VT.bal["2025-2026"] = {chambers: {H: {m: ["10", "11"], r: Object.fromEntries(Object.entries(fx.jane).map(([k, l]) => [k, l + "Y"]))},
  S: {m: ["20"], r: {"2025-S-1": "Y", "2025-S-2": "N", "2025-S-3": "Y"}}}};
s.VT.people = [{slug: "jane-doe", ids: ["10"], terms: null, hay: "rep jane doe hills 4", former: false,
  m: {slug: "jane-doe", display_plain: "Rep. Jane Doe", display_full: "Rep. Jane Doe (D - Hills 4)", party: "D"}}];
s.VT.peopleAsked = true;
const $ = id => document.getElementById(id);
const badge = () => document.querySelector("#vftoggle .badge");
const draw = qs => {
  s.VT.st = s.votesRead(qs, terms); s.VT.openG = null; s.VT.drawn = "";
  s.votesOpenFor(s.VT.st); s.votesControls(); s.votesDraw();
  const b = badge();
  return {side: $("vfacets").innerHTML, ids: [...$("vlist").innerHTML.matchAll(/data-vring="([^"]+)"/g)].map(m => m[1]),
    count: $("vcount").textContent, term: $("vterm").value, sort: $("vsort").value, box: $("vq").value,
    badge: [b.textContent, b.hidden], close: $("vclose").hidden, addr: s.votesAddr(s.VT.st, terms)};
};
for (const [qs] of fx.cases) out.cases[qs] = draw(qs);
// THE BOXES HEARD: a box ticked and unticked through the page's own handler, every page's change
// handler hearing it as the browser's would (the bill search's among them, which a box of data-f
// would reach); the Filter button opening and Escape shutting the panel; a group's head opening it.
window.GR_VOTES = true;
const all = (type, ev) => { try { (HEARD[type] || []).forEach(f => f(ev)); return ""; }
  catch (e) { return e.constructor.name + ": " + e.message; } };
const mine = (type, ev) => (HEARD[type] || []).filter(f => /GR_VOTES/.test(String(f))).forEach(f => f(ev));
draw("");
const box = (v, on) => ({dataset: {vtick: "kind"}, value: v, checked: on, id: "", name: "", type: "checkbox",
  tagName: "INPUT", form: null, closest: () => null, matches: () => false, getAttribute: () => null,
  classList: {contains: () => false}});
out.events.threw = all("change", {target: box("Procedural", true)});
out.events.ticked = [s.VT.st.kind, wrote[wrote.length - 1] || "", /data-vtick="kind" value="Procedural" checked/.test($("vfacets").innerHTML)];
all("change", {target: box("Procedural", false)});
out.events.unticked = [s.VT.st.kind, wrote[wrote.length - 1] || ""];
const cls = new Set(), lay = {id: "vlay", classList: {toggle: c => (cls.has(c) ? (cls.delete(c), false) : (cls.add(c), true)),
  contains: c => cls.has(c), remove: c => cls.delete(c), add: c => cls.add(c)}};
const attrs = {}, ftb = {id: "vftoggle", setAttribute: (k, v) => { attrs[k] = v; }, focus() { attrs.focused = true; }};
const byId = document.getElementById.bind(document);
document.getElementById = id => ({vlay: lay, vftoggle: ftb})[id] || byId(id);
mine("click", {target: {closest: q => (q === "#vftoggle" ? ftb : null)}});
out.events.opened = [cls.has("fopen"), attrs["aria-expanded"]];
mine("keydown", {key: "Escape", target: {closest: q => (q === "#vfacets,#vftoggle" ? ftb : null)}});
out.events.shut = [cls.has("fopen"), attrs["aria-expanded"], !!attrs.focused];
const head = {getAttribute: k => (k === "data-g" ? "result" : null)};
mine("click", {target: {closest: q => (q === "#vfacets .fhead" ? head : null)}});
out.events.head = /data-g="result"\s+aria-expanded="true"/.test($("vfacets").innerHTML);
document.getElementById = byId;
// The bill search's own sidebar, over two bills, to hold the votes page's groups to its markup.
s.setMeta({terms: ["2025-2026"], committee_codes: {}, topics: []});
s.setRows([{id: "HB1", n: "HB 1", title: "a bill", kind: "done", status: "Killed", chip: "Died", committees: ["Finance"],
  committee: "Finance", topic: "", sponsor: "", term: "2025-2026", year: 2025, passage: "", votedays: [], nrc: 0, last_action: ""},
  {id: "SB2", n: "SB 2", title: "a bill", kind: "law", status: "Signed into law", chip: "Became Law", committees: [],
  committee: "", topic: "", sponsor: "", term: "2025-2026", year: 2025, passage: "", votedays: [], nrc: 0, last_action: ""}]);
s.LOADED.add("2025-2026"); s.setTerm("2025-2026");
s.sel.status.add("Died");
s.renderFacets();
out.bills = document.querySelector("#facets").innerHTML;
process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.constructor.name + ": " + e.message); process.exit(1); });
"""
# A filter group as the bill search's fgroup draws one, and a box of it as its short lists draw one.
_VSIDE_FRAME = re.compile(r'<div class="fgroup (open)?"><button class="fhead" data-g="(\w+)"\s+aria-expanded="(true|false)">'
                          r'<span>([^<]*)</span>(?:<span class="badge">(\d+)</span>)?\s*<span class="chev">▸</span>'
                          r'</button><div class="fbody( whole)?" (hidden)?>')
_VSIDE_BOX = re.compile(r'<label class="fopt (off)?( fzero)?">\s*<input type="checkbox" data-(f|vtick)="(\w+)" '
                        r'value="([^"]*)" (checked)?>\s*<span>(.*?)</span>\s*<span class="c">([\d,]*)</span></label>', re.S)


def _vside_vals(r, k):
    """A roll call's values for a filter of boxes, as the page states them: its chamber, its result,
    close where `cl` says so and tied where its yeas are its nays, and its kind of question."""
    if k == "body":
        return [r["c"]]
    if k == "result":
        return ["passed" if r["p"] else "failed"]
    if k == "margin":
        return [m for m, on in (("close", r.get("cl")), ("tied", r["y"] > 0 and r["y"] == r["n"])) if on]
    return [r["k"]]


def _vside_state(meaning):
    st = {"q": "", "term": "2025-2026", "body": [], "result": [], "margin": [], "kind": [], "from": "", "to": "",
          "day": "", "member": "", "sort": ""}
    st.update(meaning)
    return st


def _vside_passes(r, st, ignore=None):
    """Whether a roll call is listed under a state, the box group `ignore` left out: written here from
    the rule the page states, not from its code."""
    for k in _VSIDE_TICKS:
        if k != ignore and st[k] and not set(_vside_vals(r, k)) & set(st[k]):
            return False
    if (st["from"] and r["d"] < st["from"]) or (st["to"] and r["d"] > st["to"]):
        return False
    if st["day"] and r.get("s", r["d"]) != st["day"]:
        return False
    if st["q"] and r["b"] != st["q"]:
        return False
    return not st["member"] or _VSIDE_JANE.get(r["id"], ".") != "."


def _vside_listed(st):
    """The roll calls a state lists, in its order: the newest first (the House before the Senate on a
    day, the higher roll first), or the fewest voters from changing the outcome first."""
    rows = [r for t, rs in _VSIDE_ROWS.items() if st["term"] in ("all", t) for r in rs]
    newest = sorted(rows, key=lambda r: (r["d"], r["c"] == "H", int(r["id"].split("-")[2])), reverse=True)
    rank = {r["id"]: i for i, r in enumerate(newest)}
    hit = [r for r in newest if _vside_passes(r, st)]
    if st["sort"] == "close":
        hit.sort(key=lambda r: (r.get("f") is None, r.get("f") or 0, rank[r["id"]]))
    return [r["id"] for r in hit], rows


def _vside_addr(st):
    """The address a state is written back as, by the page's rule: what differs from the page bare, in
    the order q, term, body, from, to, day, result, margin, kind, member, sort, a filter of boxes a value
    a parameter in its own order. Every case's term is the newest but where its address names one."""
    from urllib.parse import urlencode
    pairs = [("q", st["q"])] if st["q"] else []
    pairs += [("term", st["term"])] if st["term"] != "2025-2026" else []
    pairs += [("body", v) for v in st["body"]]
    pairs += [(k, st[k]) for k in ("from", "to", "day") if st[k]]
    pairs += [(k, v) for k in ("result", "margin", "kind") for v in st[k]]
    pairs += [("member", st["member"])] if st["member"] else []
    pairs += [("sort", st["sort"])] if st["sort"] and st["sort"] != ("best" if st["q"] else "new") else []
    return urlencode(pairs)


def _votes_side_run():
    """_VOTES_SIDE_JS's answer over the fixture, or None where node, app.js or the stub is not here."""
    js = Path("src/pages/app.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and Path("tests/dom_stub.js").exists() and node):
        return None
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source("tests/dom_stub.js"), encoding="utf-8")
        (root / "fx.json").write_text(json.dumps({"rows": _VSIDE_ROWS, "jane": _VSIDE_JANE, "cases": _VSIDE_CASES}),
                                      encoding="utf-8")
        (root / "go.js").write_text(_VOTES_SIDE_JS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=90)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js's votes page did not run under node: " + (r.stderr or r.stdout or "")[-400:])
        return json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("frontend", "the votes page's filters are the bill search's: its term picker, box, Sort and count "
       "across the top; its groups at the side, drawn by its own pieces, Chamber alone open, each box with "
       "the roll calls it would list; under 60em its Filter button, worded its way; its stylesheet's rules")
def _votes_sidebar():
    """The owner's ask of 24 November 2026, held. The page writes the bill search's top (bills.html:
    the term picker beside the box and its Return key, then the Sort and the count beside it) and the
    frame of its filters (the column, and the Filter button that opens it under 60em, its words the bill
    search's way and naming the votes' own filters). app.js draws the groups into the column with the
    bill search's own pieces: each group the markup fgroup draws, each box the markup its short lists
    draw (data-vtick where the bill search's say data-f, so a votes box never reaches the bill search's
    handler), in the order Chamber, Dates, Result, Margin, Kind of Question, Member; Chamber alone open
    on a bare page, as Status is there; the Result's words the rows' own chips; each box's number the
    roll calls the list would hold with it, the other filters and the term kept -- counted here from the
    rule the page states, not its code -- greyed at none. The boxes, the Filter button, Escape and a
    group's head are heard through the page's own handlers. And app.css names these ids in the bill
    search's own rules, keeps the column where the template hides its own, and puts the button over the
    groups under 60em; no rule of the old row is left."""
    sys.path.insert(0, "src/pages")
    try:
        import build_votes_page as VPG
    finally:
        sys.path.pop(0)
    page = VPG.body()
    bad = []
    # The top: the term picker, then the box and its key, as bills.html's .qline; the Sort before the count.
    top = re.search(r'<div class="vtop" id="vctl" role="search" aria-label="Search the votes">(.*?)\n</div>', page, re.S)
    parts = ['<form class="qline"', '<select id="vterm"', '<div class="qbox"><input id="vq"',
             '<button id="vgo" type="submit"', '<div class="qhint">', '<select id="vsort"',
             '<span id="vcount" role="status" aria-live="polite" aria-atomic="true">']
    order = re.findall("|".join(re.escape(p) for p in parts), top.group(1) if top else "")
    if order != parts:
        bad.append(f"the top of the page is not the bill search's, the term picker and the box, then the Sort "
                   f"before the count: {order}")
    # The frame: the Filter button, the column, then the list, with the close-vote line above it.
    parts = ['<div class="vlay" id="vlay">', '<button class="ftoggle" id="vftoggle" type="button" aria-expanded="false" '
             'aria-controls="vfacets"><span>', '<span class="badge" hidden></span><span class="chev">',
             '<aside class="facets" id="vfacets" aria-label="Filters"></aside>', '<div class="vmain">', 'id="vclose" hidden',
             '<div id="vlist">']
    frame = re.findall("|".join(re.escape(p) for p in parts), page)
    if frame != parts:
        bad.append(f"the frame of the filters and the list is not the bill search's: {frame}")
    bills = _source("src/pages/bills.html")
    said = str(getattr(VPG, "TOGGLE", "")).lower()
    named = re.findall(r"[a-z]+", said.replace("filter by ", "", 1))
    if not (said.startswith("filter by ") and "Filter by topic, sponsor or committee" in re.sub(r"\s+", " ", bills)
            and set(named) - {"or"} <= {"chamber", "date", "dates", "result", "margin", "kind", "member"}):
        bad.append(f"the Filter button says {said!r}: the bill search's words for its own filters")
    js = _source("src/pages/app.js")
    block = js[js.index("THE VOTES PAGE ====="):]
    for old in ("bfilt", "vfilters", "vtoggle", "vsearch", "vbadge"):
        if old in block or re.search(r"\b" + old + r"\b", page):
            bad.append(f"the votes page still draws its old row ({old})")
    if "fgroupFrame(" not in block or "fcheck(" not in block or 'class="fgroup' in block:
        bad.append("the votes page draws its groups with markup of its own, not the bill search's pieces")
    got = _votes_side_run()
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    # The bill search's own groups and boxes are the markup the pattern reads.
    bf = [m.group(2) for m in _VSIDE_FRAME.finditer(got["bills"])]
    bb = [m.group(4) for m in _VSIDE_BOX.finditer(got["bills"]) if m.group(3) == "f"]
    if "status" not in bf or got["bills"].count('class="fgroup') != len(bf) or "status" not in bb:
        bad.append(f"the pattern does not read the bill search's own groups ({bf}) and boxes ({sorted(set(bb))})")
    groups_seen = 0
    for qs, meaning in _VSIDE_CASES:
        c, st = got["cases"][qs], _vside_state(meaning)
        side = c["side"]
        frames = list(_VSIDE_FRAME.finditer(side))
        if side.count('class="fgroup') != len(frames) or [(m.group(2), m.group(4)) for m in frames] != _VSIDE_GROUPS:
            bad.append(f"{qs or '/votes'}: the groups are {[(m.group(2), m.group(4)) for m in frames]}, not the bill "
                       "search's markup in the order Chamber, Dates, Result, Margin, Kind of Question, Member")
            continue
        groups_seen += len(frames)
        want_open = {"body"} | {k for k in _VSIDE_TICKS if st[k]} | ({"dates"} if st["from"] or st["to"] or st["day"]
                                                                     else set()) | ({"member"} if st["member"] else set())
        opened = {m.group(2) for m in frames if m.group(3) == "true"}
        if opened != want_open or any((m.group(1) == "open") != (m.group(3) == "true") or
                                      (m.group(7) == "hidden") == (m.group(3) == "true") for m in frames):
            bad.append(f"{qs or '/votes'}: the groups open are {sorted(opened)}, not {sorted(want_open)}")
        _ids, rows = _vside_listed(st)
        for m in _VSIDE_BOX.finditer(side):
            off, _z, attr, k, v, on, words, n = m.groups()
            if attr != "vtick":
                bad.append(f"{qs}: a box heard as {attr}")
                continue
            want = sum(1 for r in rows if _vside_passes(r, st, k) and v in _vside_vals(r, k))
            if int(n.replace(",", "") or -1) != want or bool(off) != (want == 0 and not on) or bool(on) != (v in st[k]):
                bad.append(f"{qs or '/votes'}: the {k} box {v!r} says {n} (off {bool(off)}, ticked {bool(on)}), where "
                           f"{want} roll calls would be listed")
        badges = {m.group(2): int(m.group(5) or 0) for m in frames}
        for k in _VSIDE_TICKS:
            if badges[k] != len(st[k]):
                bad.append(f"{qs or '/votes'}: the {k} group's head says {badges[k]} ticked, not {len(st[k])}")
    if not bad:
        bare = got["cases"][""]["side"]
        if bare.count('class="chip rcres pass">Motion Passed<') != 1 or bare.count('class="chip rcres fail">Motion Failed<') != 1:
            bad.append("the Result's boxes are not the rows' own chips")
        if 'class="sbox" id="vmem"' not in bare or 'id="vf-from"' not in bare or 'id="vf-to"' not in bare:
            bad.append("the Member group has no name box, or the Dates group no From and To")
    ev = got["events"]
    if ev["threw"] or ev["ticked"][0] != ["Procedural"] or not ev["ticked"][1].endswith("?kind=Procedural") \
            or not ev["ticked"][2] or ev["unticked"][0] != [] or "kind=" in ev["unticked"][1]:
        bad.append(f"a box ticked and unticked through the page's handlers: {ev['threw'] or ev['ticked']} {ev['unticked']}")
    if ev["opened"] != [True, "true"] or ev["shut"] != [False, "false", True] or not ev["head"]:
        bad.append(f"the Filter button opens {ev['opened']}, Escape shuts {ev['shut']}, a head opens its group "
                   f"{ev['head']}")
    # The stylesheet: these ids in the bill search's rules; the column kept; the button under 60em.
    css = re.sub(r"/\*.*?\*/", "", _source("src/pages/app.css"), flags=re.S)
    for rule in ("#vq,#q,#rsq{", "#vq:focus,#q:focus,#rsq:focus{", ".qbox #vq,.qbox #q,.qbox #rsq{", "#vgo,#qgo,#rsgo{",
                 "#vterm,#year{", "#vsort,#sort{", ".searchrow,.vtop{--pickw:", ".shell .vlay .facets{display:block}"):
        if rule not in css:
            bad.append(f"app.css has no {rule}")
    narrow = re.search(r"@media \(max-width:59\.9375em\)\{\s*\.vlay\{(.*?)\n\}", css, re.S)
    if not narrow or ".shell .vlay .ftoggle{display:flex}" not in narrow.group(0) \
            or ".shell .vlay:not(.fopen) .facets{display:none}" not in narrow.group(0):
        bad.append("under 60em the Filter button is not over the groups, shut until pressed")
    if re.search(r"\.(?:vfilters|vtoggle|vsearch)\b|\.vpage\.vfopen", css):
        bad.append("app.css keeps a rule of the old row")
    assert not bad, "; ".join(bad[:4])
    return "ok", (f"the bill search's top and frame; {groups_seen} groups over {len(_VSIDE_CASES)} addresses in its "
                  "markup, Chamber alone open on a bare page and each group an address sets with it, every box's "
                  "number the roll calls it would list; the boxes, the button, Escape and a head heard; the "
                  "stylesheet's rules")


@check("frontend", "every address the votes page read before its sidebar lists the same roll calls and ticks "
       "the box it names, the phone's Filter button carries how many filters are set, and the address the "
       "page writes is the one it read")
def _votes_address_ticks():
    """KEEP every filter in the address (the brief of 25 November 2026): ?q=&term=&body=&from=&to=&day=
    &result=&margin=&kind=&member=&sort=, the same names and meanings, so every link already out there
    opens the same votes, and a parameter that now ticks a box ticks that box. Each address of a link
    -- one value a filter, as every link before the boxes wrote it -- and a few the boxes write, each
    drawn in node: the roll calls it lists are those the rule gives, counted here from the rule and
    not from the page's code, in the page's order; the box it names is ticked and no other; the dates,
    the session day, the member, the words, the term and the order are where the page shows them; the
    close-vote line stands above the list only while Margin asks for close votes; the address the page
    writes back is the canonical one; and the Filter button's count is how many filters the side has
    set -- each box, each date, a session day, a member -- hidden at none, the term and the order across
    the top not among them, as the bill search's button counts what its groups have ticked."""
    got = _votes_side_run()
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    bad = []
    for qs, meaning in _VSIDE_CASES:
        c, st = got["cases"][qs], _vside_state(meaning)
        where = qs or "/votes"
        ids, _rows = _vside_listed(st)
        if c["ids"] != ids:
            bad.append(f"{where} lists {c['ids']}, not {ids}")
        ticked = sorted((m.group(4), m.group(5)) for m in _VSIDE_BOX.finditer(c["side"]) if m.group(6))
        want = sorted((k, v) for k in _VSIDE_TICKS for v in st[k])
        if ticked != want:
            bad.append(f"{where} ticks {ticked}, not {want}")
        for key, field in (("from", "vf-from"), ("to", "vf-to")):
            m = re.search(r'id="' + field + r'" data-vf="' + key + r'" value="([^"]*)"', c["side"])
            if not m or m.group(1) != st[key]:
                bad.append(f"{where}: the {key} box says {m and m.group(1)!r}, not {st[key]!r}")
        if bool(st["day"]) != ("Session day" in c["side"]) or (st["day"] and "The House, March 5, 2025" not in c["side"]):
            bad.append(f"{where}: the session day is not named in the Dates group with its Clear")
        jane = 'class="mchip p-D"' in c["side"] and "data-vmemclear" in c["side"]
        if bool(st["member"]) != jane or (st["member"] and "Rep. Jane Doe voted yea or nay on 2 of 3 roll calls"
                                         not in c["count"]):
            bad.append(f"{where}: the member is not shown as their chip with its Clear, or not counted: {c['count']!r}")
        if c["term"] != st["term"] or c["box"] != st["q"] or c["sort"] != (st["sort"] or ("best" if st["q"] else "new")):
            bad.append(f"{where}: the term picker {c['term']!r}, the box {c['box']!r}, the Sort {c['sort']!r}")
        if c["close"] != ("close" not in st["margin"]):
            bad.append(f"{where}: the close-vote line is {'hidden' if c['close'] else 'shown'}")
        n = sum(len(st[k]) for k in _VSIDE_TICKS) + sum(1 for k in ("from", "to", "day", "member") if st[k])
        if c["badge"] != ([str(n), False] if n else ["", True]):
            bad.append(f"{where}: the Filter button carries {c['badge']}, where {n} filters are set")
        if c["addr"] != _vside_addr(st):
            bad.append(f"{where} is written back as {c['addr']!r}, not {_vside_addr(st)!r}")
    assert not bad, "; ".join(bad[:4])
    return "ok", (f"{len(_VSIDE_CASES)} addresses, each a link's parameter or the boxes' own: the roll calls the "
                  "rule gives, the box it names ticked and no other, the dates, the day, the member, the words, the "
                  "term and the order in place, the address written back as read, and the Filter button carrying "
                  "the filters set and not the term or the order")


@check("data", "votes data: every roll call has a row, every counted tally ties to its ballots, the 14 stated "
       "tallies are carried, and the close votes are the ones a recount by switching voters gives",
       needs=("build_votes",))
def _votes_data(BV):
    rp, mp = Path("rollcalls.json"), Path("data/member_votes.json")
    if not rp.exists() or not mp.exists():
        return "skip", "rollcalls.json or data/member_votes.json is not here"
    import gzip
    rolls = json.loads(rp.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        rows, enc, rep = BV.build(rolls, BV.stream_array(mp), td)
        every = [r for t in rolls.values() for rcs in t.values() for r in rcs]
        got = [x for rs in rows.values() for x in rs]
        assert len(got) == len(every) and len({x["id"] for x in got}) == len(got), (
            f"{len(got):,} rows for {len(every):,} roll calls")
        stated = sorted(x["id"] for x in got if "ys" in x)
        assert stated == sorted(f'{r["year"]}-{r["body"]}-{r["number"]}' for r in every if "yeas_stated" in r), stated
        assert len(stated) == 14, (f"{len(stated)} roll calls where the clerk's tally differs from the ballots, "
                                   "against the 14 known")
        assert not rep["unmatched"], f"{rep['unmatched']:,} ballots on a roll call with no row"
        unknown = [x["id"] for x in got if x.get("fu")]
        assert len(unknown) <= 5, f"{len(unknown)} roll calls with an unknown threshold: {unknown}"
        assert all("f" not in x and "cl" not in x for x in got if x.get("fu"))
        rule_of = {f'{r["year"]}-{r["body"]}-{r["number"]}': (r.get("threshold_rule") or "") for r in every}
        for x in got:
            if "f" not in x:
                continue
            k = _votes_brute_flip(x["y"], x["n"], "2/3" if rule_of[x["id"]].startswith("two thirds")
                                  else x.get("nd"))
            assert k == x["f"] and bool(x.get("cl")) == (k <= BV.CLOSE[x["c"]]), (x["id"], x["f"], k)
        files = list((Path(td) / "votes").glob("*.json"))
        size = sum(p.stat().st_size for p in files)
        gz = sum(len(gzip.compress(p.read_bytes())) for p in files)
        # A file of rows and a file of ballots a term, and the index the votes page opens with.
        assert "index.json" in {p.name for p in files} and len(files) == 2 * len(rows) + 1, (
            f"{len(files)} files for {len(rows)} terms, wanted a pair a term and votes/index.json")
        assert size < 6 * 1024 * 1024 and gz < 1024 * 1024, (
            f"the votes files are {size / 1024:,.0f} KB, {gz / 1024:,.0f} KB gzipped, against the design's "
            "2 MB of rows and 2.3 million ballot characters")
        text = "".join(p.read_text(encoding="utf-8") for p in files)
        for rx in _BANNED_VOTES:
            assert not rx.search(text), f"a built votes file says {rx.pattern}"
    return "ok", (f"{len(got):,} roll calls in {len(rows)} terms, {len(files)} files, {size / 1024:,.0f} KB "
                  f"({gz / 1024:,.0f} KB gzipped)")
