#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
preflight's checks of data checks with no module under test, for a person to sort.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import csv
import json
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from pf_core import (_run, _source, check)
from pf_shared import (LSR_LISTLIKE, SPONSOR_HONORIFIC, _CLERKS_COMMITTEES, _CLOCK_SEMICOLON,
                       _ROOM_CHANGED, _ballot_census, _map_totals_run, _map_totals_text,
                       _narratives, _site_bills, _site_records, _speakers_against_journal)


@check("data", "the meetings decision 58 cancels for all their bills are told for none of them")
def _whole_day_histories():
    """Decision 58 (_whole_day_cancelled, _whole_day_not_silent): Ways and
    Means' executive session of 29 October 2015 and Commerce's of 29 October
    2013 are cancelled for HB 571 and HB 634 of 2015 and SB 92 of 2013, whose
    own notices of them carry no mark. Nothing but the calendars' half of the
    rule holds them there, so the histories on disk are read: none tells the
    day, and each lists it among the meetings no committee sat for."""
    narr = Path("narratives.json")
    if not narr.exists():
        return "skip", "no narratives.json here"
    data = _narratives()
    want = {("2015-2016", "HB571"): ("2015-10-29", "October 29, 2015"),
            ("2015-2016", "HB634"): ("2015-10-29", "October 29, 2015"),
            ("2013-2014", "SB92"): ("2013-10-29", "October 29, 2013")}
    bad = []
    for (term, bill), (day, words) in want.items():
        h = (data.get(term) or {}).get(bill)
        if not h:
            bad.append(f"{bill} of {term} has no history")
            continue
        if words in (h.get("narrative") or ""):
            bad.append(f"{bill} of {term} tells {words}")
        if not any(m[0] == day and m[1] == "H" for m in h.get("voided") or []):
            bad.append(f"{bill} of {term} draws its committee's meeting of {day}: voided "
                       f"{h.get('voided')!r}")
    assert not bad, "\n".join(bad)
    return "ok", "HB 571 and HB 634 of 2015 and SB 92 of 2013 tell no meeting of 29 October"


@check("data", "SB 411 of 2000's Senate hearing of 10 February is Environment's, at 1:00, in the "
               "1999-2000 manifest")
def _sb411_manifest_row():
    """The review of decision 60 (_rescheduled_row_new_time): the row merged
    for SB 411 said Ways and Means at 9:00, and was replaced with build_manifest
    --merge --refresh --only SB411@2000-02-10. A manifest put back from an
    older copy brings Ways and Means' day of 10 February 2000 back."""
    f = Path("verification_manifest_1999-2000.csv")
    if not f.exists():
        return "skip", f"no {f.name} here"
    with f.open(encoding="utf-8", newline="") as fh:
        got = [(r["committee"], r["sched_time"]) for r in csv.DictReader(fh)
               if r["bill"] == "SB411" and r["body"].upper() == "S"
               and r["sched_date"] == "2000-02-10"]
    assert got == [("Environment", "13:00")], (
        f"{f.name} has SB 411's Senate rows of 10 February 2000 as {got!r}")
    return "ok", "SB 411 of 2000 heard by Environment at 1:00 on 10 February"


@check("data", "SB 398 of 2000's hearing of 15 March is Wildlife and Recreation's in the 1999-2000 "
               "manifest and proceedings.csv")
def _vacated_sb398_manifest():
    """_vacated_sb398, in the files on disk: a manifest merged before
    docket_parser read the vacate, or a table built from one, files the
    hearing under Transportation, the committee the Senate took the bill
    from. A full rebuild of the term's manifest puts it right."""
    got = []
    for f, bill, body, day, cmte in (
            (Path("verification_manifest_1999-2000.csv"), "bill", "body", "sched_date", "committee"),
            (Path("proceedings.csv"), "bill", "body", "date", "committee")):
        if not f.exists():
            return "skip", f"no {f.name} here"
        with f.open(encoding="utf-8", newline="") as fh:
            got += [(f.name, r[cmte]) for r in csv.DictReader(fh)
                    if r[bill] == "SB398" and r[body].upper() == "S" and r[day] == "2000-03-15"]
    want = [("verification_manifest_1999-2000.csv", "Wildlife and Recreation"),
            ("proceedings.csv", "Wildlife and Recreation")]
    assert got == want, f"SB 398's hearing of 15 March 2000 is filed as {got!r}"
    return "ok", "Wildlife and Recreation's, in the manifest and the table"


@check("data", "SB 31 of 1999's rescheduled hearing of 9 April, its chamber in lower case, is in "
               "the 1999-2000 manifest")
def _manifest_lower_case_chamber_on_disk():
    """_manifest_lower_case_chamber, in the file on disk: a manifest built
    before parse_rows read the chamber in either case has no row for SB 31's
    hearing of 9 April 1999 or HB 506's of 2 March."""
    f = Path("verification_manifest_1999-2000.csv")
    if not f.exists():
        return "skip", f"no {f.name} here"
    with f.open(encoding="utf-8", newline="") as fh:
        have = {(r["bill"], r["body"], r["sched_date"]) for r in csv.DictReader(fh)}
    want = {("SB31", "S", "1999-04-09"), ("HB506", "H", "1999-03-02"),
            ("SB30", "S", "1999-06-23"), ("HB346", "S", "1999-11-30")}
    assert want <= have, f"{f.name} has no row for {sorted(want - have)}"
    return "ok", "SB 31, HB 506, SB 30 and HB 346 have their meetings in the 1999-2000 manifest"


@check("data", "the 1999-2000 manifest's Senate rows name a committee, but for the bills whose "
               "docket names none")
def _senate_introduction_committee_on_disk():
    """_senate_introduction_committee, in the file on disk: 645 of 998 Senate
    rows named no committee. What is left are bills the Senate's docket gives
    no introduction for, or gives one in words no reader of this project
    takes (the scratch notes of 7 October 2026 list them); a manifest built
    before reads hundreds. And the six hearings the introduction alone put
    under the wrong committee (_senate_introduction_committee) are their
    own committee's."""
    f = Path("verification_manifest_1999-2000.csv")
    if not f.exists():
        return "skip", f"no {f.name} here"
    with f.open(encoding="utf-8", newline="") as fh:
        sen = [r for r in csv.DictReader(fh) if r["body"].upper() == "S"]
    none = sorted({r["bill"] for r in sen if not r["committee"]})
    assert len(none) <= 13, (f"{len(none)} Senate bills of 1999-2000 have a manifest row with no "
                             f"committee: {', '.join(none[:12])}")
    want = {("SB27", "1999-03-10"): "Banks", ("SB27", "1999-03-17"): "Banks",
            ("SB27", "1999-03-24"): "Banks", ("CACR16", "1999-02-17"): "Education",
            ("SB69", "1999-03-30"): "Public Institutions, Health and Human Services",
            ("HB707", "1999-09-08"): "Judiciary"}
    got = {(r["bill"], r["sched_date"]): r["committee"] for r in sen
           if (r["bill"], r["sched_date"]) in want}
    assert got == want, f"{f.name} files {sorted(set(got.items()) - set(want.items()))}"
    return "ok", (f"{sum(1 for r in sen if not r['committee'])} of {len(sen)} Senate rows name no "
                  f"committee, on {len(none)} bills whose docket names none it can read")


@check("data", "SB 139 of 2005 and SB 312 of 2000 sit in proceedings.csv at the hour their TIME "
               "CHANGE row gave them")
def _senate_time_change_table():
    """_senate_time_change, in the table on disk: a proceedings.csv built
    before it, or from a manifest that was, gives these two hearings 1:30 and
    1:00."""
    f = Path("proceedings.csv")
    if not f.exists():
        return "skip", "no proceedings.csv here"
    want = {("2005-2006", "SB139", "2005-02-22"): "14:00", ("1999-2000", "SB312", "2000-02-23"): "13:45"}
    with f.open(encoding="utf-8", newline="") as fh:
        got = {(r["term"], r["bill"], r["date"]): r["time"] for r in csv.DictReader(fh)
               if (r["term"], r["bill"], r["date"]) in want and r["body"] == "S"
               and r["kind"] == "hearing"}
    assert got == want, f"proceedings.csv gives {got!r}, not {want!r}"
    return "ok", "2:00 on 22 February 2005 and 1:45 on 23 February 2000"


@check("data", "the Senate sittings of 1999-2006 a ROOM CHANGE or TIME CHANGE row moved are in "
               "that room in their term's manifest")
def _senate_room_change_manifests():
    """_senate_room_change, in the files on disk: a manifest built before it
    keeps each sitting's notice row in the room the notice gave, and
    build_proceedings, keeping the first row, puts the hearing there. A full
    rebuild of the term's manifest puts it right."""
    bad, n = [], 0
    for term in sorted({t for t, _, _ in _ROOM_CHANGED}):
        f = Path(f"verification_manifest_{term}.csv")
        if not f.exists():
            return "skip", f"no {f.name} here"
        with f.open(encoding="utf-8", newline="") as fh:
            rows = [r for r in csv.DictReader(fh) if r["body"].upper() == "S"]
        for (t, bill, day), room in _ROOM_CHANGED.items():
            if t != term:
                continue
            n += 1
            got = sorted({r["venue"] for r in rows if r["bill"] == bill and r["sched_date"] == day})
            if got != [room]:
                bad.append(f"{f.name} has {bill}'s Senate sitting of {day} in {got!r}, not {room!r}")
    assert not bad, "\n".join(bad)
    return "ok", f"{n} sittings in the room their latest change row gave them"


@check("data", "HB 355 of 2022's conference of 16 May, which its twin cancels, is not in the "
               "2021-2022 manifest")
def _cancelled_twin_manifest():
    """_cancelled_twin, in the file on disk: a manifest built before it holds
    the conference, and every page that reads the table draws it. A full
    rebuild of the term's manifest takes it out and keeps the 17th and 18th."""
    f = Path("verification_manifest_2021-2022.csv")
    if not f.exists():
        return "skip", f"no {f.name} here"
    with f.open(encoding="utf-8", newline="") as fh:
        got = sorted((r["sched_date"], r["sched_time"]) for r in csv.DictReader(fh)
                     if r["bill"] == "HB355" and r["proceeding"] == "committee of conference")
    want = [("2022-05-17", "11:00"), ("2022-05-18", "12:00")]
    assert got == want, f"{f.name} has HB 355's conferences as {got!r}, not {want!r}"
    return "ok", "the 17th and the 18th, and not the 16th"


@check("data", "the hearings whose hour the clerk typed with a semicolon are in their term's "
               "manifest at that hour")
def _clock_semicolon_manifests():
    """_clock_semicolon, in the files on disk: a manifest built before it has
    SB 362 of 2000's hearing at 3:00 and no row for the other four. A full
    rebuild of the term's manifest puts them in."""
    bad = []
    for term in sorted({t for t, _, _, _ in _CLOCK_SEMICOLON}):
        f = Path(f"verification_manifest_{term}.csv")
        if not f.exists():
            return "skip", f"no {f.name} here"
        with f.open(encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        for (t, bill, ch, day), hour in _CLOCK_SEMICOLON.items():
            if t != term:
                continue
            got = sorted({r["sched_time"] for r in rows if r["bill"] == bill
                          and r["body"].upper() == ch and r["sched_date"] == day
                          and r["proceeding"] == "hearing"})
            if got != [hour]:
                bad.append(f"{f.name} has {bill}'s hearing of {day} at {got!r}, not {hour}")
    assert not bad, "\n".join(bad)
    return "ok", f"{len(_CLOCK_SEMICOLON)} hearings at the hour their semicolon gives"


@check("data", "SB 107 of 2023's House hearing of 5 April 2023 carries no recording time in the "
               "2023-2024 manifest until the timestamp pass has scored one")
def _sb107_time_held():
    """HELD FOR THE TIMESTAMP PASS (the person's decision of 8 October 2026).
    A full rebuild of 2023-2024 works out the recording match that the
    meridiem fix of 18 September (82181fa) left as the kit had it: the docket
    says "Public Hearing: 04/05/2023 01:30 am LOB 306-308" (Docket_2023-2024.txt
    line 16093), read as 1:30 in the afternoon, and at that minute only one of
    House Executive Departments and Administration's two recordings of the day
    was on air, so the rebuilt row picks uU3lVfuRJAc and an approximate offset
    of 3:26:49. Nobody has scored that time against the recording, and nothing
    about timestamps goes on the site before probe_alignment has, so the
    manifest sent carries the row's time fields as the kit's copy has them --
    two recordings that day, pick manually, no video and no offset -- and a
    rebuild that puts the time back is held here. When the dedicated
    timestamp pass has scored it, this check goes with that pass."""
    f = Path("verification_manifest_2023-2024.csv")
    if not f.exists():
        return "skip", f"no {f.name} here"
    with f.open(encoding="utf-8", newline="") as fh:
        got = [(r["match"], r["video_id"], r["stream_start"], r["predicted_offset"], r["watch_url"])
               for r in csv.DictReader(fh)
               if r["bill"] == "SB107" and r["body"].upper() == "H"
               and r["proceeding"] == "public hearing" and r["sched_date"] == "2023-04-05"]
    want = [("2 videos that day - pick manually", "", "", "", "")]
    assert got == want, (f"{f.name} gives SB 107's House hearing of 5 April 2023 {got!r}: a time "
                         "nobody has scored. Put back the kit's row for it (its line in the copy "
                         "the bucket holds) until the timestamp pass decides it")
    return "ok", "no recording time on it, as the kit has it, until the timestamp pass"


@check("data", "the three Senate hearings of 1999-2001 whose committee the clerk misspelled or "
               "shortened are filed in proceedings.csv under the committee's name")
def _clerks_committee_names_table():
    """_clerks_committee_names, in the table on disk: built from manifests
    that hold the clerk's words and before the aliases, it prints "P I, H and
    H S" on HB 390 of 2001's hearing card; built from manifests older than
    the parser batch, it names no committee for two of them and Judiciary for
    the third."""
    f = Path("proceedings.csv")
    if not f.exists():
        return "skip", "no proceedings.csv here"
    with f.open(encoding="utf-8", newline="") as fh:
        got = {(r["term"], r["bill"], r["date"]): r["committee"] for r in csv.DictReader(fh)
               if (r["term"], r["bill"], r["date"]) in _CLERKS_COMMITTEES and r["body"] == "S"
               and r["kind"] == "hearing"}
    assert got == _CLERKS_COMMITTEES, f"proceedings.csv files them under {got!r}"
    return "ok", "three hearings under the names their committees had then"


@check("data", "SB 373 of 2002 and SB 79 and SB 395 of 1999-2000 each have the hearing their "
               "history tells in their term's manifest")
def _rescheduled_rows_in_manifests():
    """Decision 60: the three bills had no hearing drawn anywhere, because the
    manifests had no row for the day a rescheduling row names. The rows were
    added with build_manifest --merge; a manifest rebuilt without them, or a
    parser that stops reading them, takes the three off the site again. And
    HB 618 of 2000's hearing of 24 April (decision 59b), whose notice
    "==HEARING== April 24" was read as nothing until then."""
    want = {"1999-2000": [("SB79", "1999-03-24"), ("SB395", "2000-02-24"),
                          ("HB618", "2000-04-24"), ("SB393", "2000-02-08"),
                          ("SB370", "2000-02-09")],
            "2001-2002": [("SB373", "2002-01-22"), ("SB189", "2001-04-11")]}
    bad, n = [], 0
    for term, pairs in want.items():
        f = Path(f"verification_manifest_{term}.csv")
        if not f.exists():
            return "skip", f"no {f.name} here"
        with f.open(encoding="utf-8", newline="") as fh:
            have = {(r["bill"], r["sched_date"]) for r in csv.DictReader(fh)
                    if r["body"].upper() == "S" and r["proceeding"] == "hearing"}
        for b, d in pairs:
            n += 1
            if (b, d) not in have:
                bad.append(f"{f.name} has no Senate hearing of {b} on {d}")
    assert not bad, "\n".join(bad)
    return "ok", f"{n} hearings on the day each history tells them"


# What a term's search index may weigh. The page fetches it when somebody
# searches; /search fetches every term's. Measured on 1 October: 197,000 to
# 303,000 bytes a term, 4.4 MB for all twenty. A file past this has stopped
# choosing what a bill is about.
#
# That is its words and phrases. Since 2 October the file also holds, for each
# bill, the pairs of those words that stand together, and they are held to a
# size of their own: 102,000 to 186,000 bytes a term that day, with the whole
# file 285,000 to 461,000 and all twenty 6.5 MB. Pairs past this would mean
# the build had stopped choosing which pairs the page could ask for.
SEARCH_INDEX_MOST = 450_000
SEARCH_PAIRS_MOST = 250_000
SEARCH_INDEX_MOST_ALL = 9_000_000


@check("data", "every term has a search index, for its own bills, within its size")
def _search_index_built():
    """Silence is not success. A term whose index was never written, or was
    written empty, searches by title exactly as it did before, and nothing on
    the page looks broken: the bills its text would have found are simply
    not there.

    For every term the bill search offers -- meta.json's, and the bill
    requests -- site/sidx/<term>.json exists, names only bills of that
    term's own index and every one of them, and is not empty unless the term
    has no text at all (the requests, which are a title and a sponsor). And
    it is within its size: the build keeps what a bill is ABOUT, and a file
    of a megabyte would mean it had started keeping what a bill mentions.

    Since 2 October it also holds the pairs of words that stand together in
    each bill, one string of codes a bill ("b"). A file without them is an
    older build's: a search of several words would then find no word outside
    a title, and nothing on the page would say why. And words.json leaves
    out the record's own slips, so that a reader who types "goverment", as
    one bill does, is offered the word.
    """
    site = Path("site")
    if not (site / "idx").is_dir() or not (site / "meta.json").exists():
        return "skip", "site/idx is not built"
    sidx = site / "sidx"
    assert sidx.is_dir(), (
        "site/idx is built and site/sidx is not: the search reads titles and "
        "topics and none of the bills' own text. build_search_index.py "
        "writes it; build_all runs it after the site data.")
    meta = json.loads((site / "meta.json").read_text(encoding="utf-8"))
    terms = list(meta.get("terms") or [])
    if (meta.get("requests") or {}).get("term"):
        terms.append(meta["requests"]["term"])
    bad, total, entries, empty = [], 0, 0, []
    for t in terms:
        f, ix = sidx / f"{t}.json", site / "idx" / f"{t}.json"
        if not ix.exists():
            continue
        if not f.exists():
            bad.append(f"{t}: no search index")
            continue
        size = f.stat().st_size
        total += size
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except ValueError as e:
            bad.append(f"{t}: unreadable ({e})")
            continue
        ids = [r.get("id") for r in json.loads(ix.read_text(encoding="utf-8"))
               if isinstance(r, dict) and (not r.get("term") or r["term"] == t)]
        if d.get("v") != 1 or d.get("term") != t:
            bad.append(f"{t}: says it is version {d.get('v')!r} of {d.get('term')!r}")
        elif d.get("ids") != ids:
            bad.append(f"{t}: names {len(d.get('ids') or [])} bills, and the "
                       f"term's index has {len(ids)} -- built from another index")
        n = sum(len(v) for v in (d.get("w") or {}).values())
        entries += n
        if not n:
            empty.append(t)
        # The pairs: without them a search of several words finds no word
        # outside a title, and nothing on the page says why.
        # A term with no text at all (the bill requests) has no words and
        # an empty list of pairs.
        b = d.get("b")
        if not isinstance(b, list) or (n and len(b) != len(d.get("ids") or [])):
            bad.append(f"{t}: holds no pairs of words for its bills (\"b\"): "
                       "built by an older build_search_index.py")
        elif n and not any(b):
            bad.append(f"{t}: has words and not one pair of them")
        pairs = len(json.dumps(d.get("b") or [], ensure_ascii=False,
                               separators=(",", ":")).encode("utf-8"))
        if size - pairs > SEARCH_INDEX_MOST:
            bad.append(f"{t}: {size - pairs:,} bytes of words and phrases, "
                       f"more than {SEARCH_INDEX_MOST:,}")
        if pairs > SEARCH_PAIRS_MOST:
            bad.append(f"{t}: {pairs:,} bytes of pairs, more than "
                       f"{SEARCH_PAIRS_MOST:,}")
    # EVERY WORD THE BILLS USE. Without sidx/words.json a misspelt search is
    # offered nothing, and nothing on the page says so; with a thin one, real
    # words would be offered as other words. The cases file lists real words
    # that were read as other words for a day (tests/search_cases.json,
    # "known"): each must be in it.
    wf = sidx / "words.json"
    if not wf.exists():
        bad.append("words.json is not there: a misspelt search is offered "
                   "nothing (a run of build_search_index.py over every term "
                   "writes it; one with --terms does not)")
    else:
        try:
            w = json.loads(wf.read_text(encoding="utf-8"))
        except ValueError as e:
            w = {}
            bad.append(f"words.json: unreadable ({e})")
        ws = set(str(w.get("words") or "").split(" ")) - {""}
        if w.get("v") != 1 or w.get("n") != len(ws):
            bad.append(f"words.json: version {w.get('v')!r}, and says "
                       f"{w.get('n')!r} words where it holds {len(ws):,}")
        elif len(ws) < 10_000:
            bad.append(f"words.json holds {len(ws):,} words: one term's texts "
                       "alone use fifteen thousand")
        cases = Path("tests/search_cases.json")
        if ws and cases.exists():
            want = json.loads(_source(cases)).get("known") or []
            lost = [x for x in want if x not in ws]
            if lost:
                bad.append(f"words.json lacks {lost[:6]}: words bills use, "
                           "which the search would offer as other words")
        # The record's own slips are not words: one bill says each of these,
        # and a reader who typed one was offered nothing (2 October).
        kept = [s for s, v in (("goverment", "government"), ("libary", "library"),
                               ("hopsital", "hospital")) if s in ws and v in ws]
        if kept:
            bad.append(f"words.json holds {kept}: slips one bill makes, which "
                       "a reader who makes the same one is then offered "
                       "nothing for")
    assert not bad, "the search index: " + "; ".join(bad[:4])
    real = [t for t in empty if re.fullmatch(r"\d{4}-\d{4}", t)]
    assert not real, (
        f"the search index of {', '.join(real)} is empty: no bill text was "
        "read for it, and its bills are found by title and topic only. "
        "bill_text.json and archive_text.json are what the build reads.")
    assert total <= SEARCH_INDEX_MOST_ALL, (
        f"the search indexes come to {total:,} bytes, more than "
        f"{SEARCH_INDEX_MOST_ALL:,}: /search fetches them all")
    return "ok", (f"{len(terms)} terms, {entries:,} entries, {total:,} bytes in "
                  f"all and none over {SEARCH_INDEX_MOST:,}"
                  + (f"; no text for {', '.join(empty)}, as expected" if empty else ""))


@check("data", "every bill request's prime sponsor and co-sponsors read as one person's name each, not "
               "a list the Sponsors column's form left unsplit")
def _lsr_sponsor_names_are_names():
    """The night's lsrs.json, where it is here: a sponsor or co-sponsor name holding a semicolon, a
    comma, a parenthesis, "and" or an ampersand is a list fetch_lsrs.split_sponsors did not split, or
    a role mark it did not take off -- the sign that the request list began printing co-sponsors in a
    form nobody has yet seen (_lsr_sponsors_split). On the night it warns (RECORD_CHECKS): the site
    goes on, and the run's page says which requests to look at."""
    p = Path("lsrs.json")
    if not p.exists():
        return "skip", "no lsrs.json here"
    rows = json.loads(p.read_text(encoding="utf-8"))
    odd = [f"{r.get('lsr')}: {n!r}" for r in rows for n in [r.get("sponsor") or "", *(r.get("cosponsors") or [])]
           if n and LSR_LISTLIKE.search(str(n))]
    assert not odd, (f"{len(odd)} request sponsor name(s) read as a list, e.g. {odd[:5]}: the request list's "
                     "Sponsors column may print co-sponsors in a form split_sponsors does not read")
    co = sum(len(r.get("cosponsors") or []) for r in rows)
    return "ok", f"{len(rows):,} requests, each sponsor one name; {co:,} co-sponsors listed"


@check("data", "the built site: a member's On Record terms before 1999 (past_terms) are the terms "
               "of the 1989-1998 bills their page lists, which the TERM picker offers, with the "
               "terms the Manual seats them in with no bill (manual_terms), and nothing else")
def _on_record_terms_built():
    """The check above proves the rule on a fixture; this, that the build kept it, on every
    member's own file. The TERM picker offers the term of every bill the page lists
    (app.js recordTerms), and the On Record line, the static sentence and the description say
    the years before 1999 from past_terms (member_links.earlier_terms), so every term of the
    picker must be in it. On the candidate for the release of 16 November 2026 one was not, on
    four pages: the rows the General Court's sponsor record supplies itself had no chamber, and
    Donna Sytek, Speaker in 1997-1998, read "House, 1989-1996, 1999-2000" with 1997-1998 in her
    TERM picker, as Robert Johnson (1993-1994), Roland Turgeon (1997-1998) and Dennis Abbott
    (1995-1996) missed a term each. A site built before 13 November 2026 has no past_terms.

    AND THE TERMS THE MANUAL SEATS THEM IN WITH NO BILL (build_site_v2.manual_seats; the owner,
    14 November 2026), which past_terms carries too and manual_terms alone, by chamber: so
    past_terms is the bills' terms and manual_terms' together, manual_terms names only terms
    of 1989-1998 with no bill of the page in them, and each is in past_terms under its own
    chamber. Nothing else may put a term on the line."""
    d = Path("site") / "legislators"
    if not d.is_dir():
        return "skip", "site/legislators is not here"
    early = lambda t: str(t or "")[:4].isdigit() and int(str(t)[:4]) < 1999
    bad, pages, early_pages, with_past, with_manual = [], 0, 0, 0, 0
    for f in sorted(d.glob("*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            bad.append(f"{f.name} does not read: {e}")
            continue
        if not isinstance(rec, dict):
            continue
        pages += 1
        listed = {str(x.get("term")) for x in rec.get("sponsored") or () if early(x.get("term"))}
        past = rec.get("past_terms") or {}
        said = {str(t) for ts in past.values() for t in ts or ()}
        manual = rec.get("manual_terms") or {}
        seated = {str(t) for ts in manual.values() for t in ts or ()}
        early_pages += bool(listed or said)
        with_past += bool(past)
        with_manual += bool(seated)
        who = f"{f.stem} ({rec.get('display_full') or rec.get('name') or ''})"
        if listed - said:
            bad.append(f"{who}: bills of {', '.join(sorted(listed - said))} and no such term on record")
        if said - listed - seated:
            bad.append(f"{who}: on record in {', '.join(sorted(said - listed - seated))} with no "
                       "bill of it and no Manual seat")
        if {t for t in seated if not early(t)}:
            bad.append(f"{who}: manual_terms names {', '.join(sorted(t for t in seated if not early(t)))}, "
                       "a term from 1999 on")
        if seated & listed:
            bad.append(f"{who}: manual_terms names {', '.join(sorted(seated & listed))}, a term "
                       "its bills already show")
        if any(t not in (past.get(ch) or ()) for ch, ts in manual.items() for t in ts or ()):
            bad.append(f"{who}: manual_terms {manual} is not in past_terms {past} under its chamber")
    assert pages, "site/legislators holds no member's file"
    # The old site's hint only where it is the explanation: no member's file carries past_terms
    # at all. On a site that has them, the pages named are the finding.
    assert not bad, (f"{len(bad)} finding(s) where a page's On Record terms before 1999 are not "
                     "its bills' and its Manual seats'"
                     + ("" if with_past else " (a site built before 13 November 2026 has no "
                                             "past_terms: rebuild it)")
                     + ": " + "; ".join(bad[:8]) + (" ..." if len(bad) > 8 else ""))
    return "ok", (f"{early_pages:,} of {pages:,} member pages have On Record terms before 1999, "
                  f"{with_manual:,} of them with terms the Manual seats them in with no bill; each "
                  "page's are exactly its bills' terms and those")


@check("data", "every upcoming row on the built site says whose sitting it is")
def _upcoming_rows_say_chamber():
    """site/home.json's upcoming rows, each with the chamber cmteUpcoming
    tells House Judiciary's sitting from Senate Judiciary's by.

    A DATA CHECK, NOT A FRONTEND ONE, on purpose. It was an assertion in
    tests/test_cmte_match.js, which _cmte_match runs under --code whenever
    site/committee is built, and nightly.py gates itself on preflight --code
    before build_all. Every home.json written before build_site_v2 wrote the
    chamber -- the live one had 62 rows and none said it -- failed it, so the
    nightly would have stopped before the one step that writes the chamber,
    and stayed stopped until a person built by hand: the failure
    _town_pages_built's docstring records. The builder's side is held under
    --code by _upcoming_shape, on a fixture. This says whether the built site
    has caught up, and the fix it names is a rebuild.
    """
    hp = Path("site/home.json")
    if not hp.exists():
        return "skip", "site/home.json is not built"
    up = json.loads(hp.read_text(encoding="utf-8")).get("upcoming") or []
    if not up:
        return "ok", "nothing is scheduled in the fortnight, so no row to name a chamber"
    nobody = [u for u in up if u.get("body") not in ("H", "S")]
    assert not nobody, (
        f"{len(nobody)} of {len(up)} upcoming rows in site/home.json do not say whose "
        "sitting they are, so a committee page cannot tell House Judiciary's from "
        "Senate Judiciary's on a bill both list -- rebuild with build_site_v2.py: "
        + json.dumps(nobody[0])[:140])
    return "ok", f"{len(up)} upcoming rows, each naming its chamber"


# THE CALENDARS ON DISK THAT ARE ANOTHER'S. A base calendar whose text is its
# supplement's, word for word, is not that calendar: twelve such on 8 October
# 2026, each a person's fetch to put right (fetch_committee_reports.py --year,
# after the copy is moved aside). A new one is a fault; these are known.
CALENDAR_COPIES = {
    "2023": ["HC011", "HC014", "HC015", "HC018", "HC023", "HC024", "HC045"],
    "2024": ["HC005", "HC015", "HC035"], "2025": ["HC016", "HC027"]}


@check("data", "no House Calendar on disk is its own supplement's copy, but the twelve "
               "known and waiting on a fetch")
def _calendar_copies():
    root = Path("calendars")
    if not root.is_dir():
        return "skip", "no calendars/ here"
    found = {}
    for base in sorted(root.glob("*/HC[0-9][0-9][0-9].txt")):
        for sup in sorted(base.parent.glob(base.stem + "[A-Z].txt")):
            if base.read_bytes() == sup.read_bytes():
                found.setdefault(base.parent.name, []).append(base.stem)
    new = sorted(f"{y}/{s}" for y, ss in found.items() for s in ss
                 if s not in CALENDAR_COPIES.get(y, []))
    assert not new, ("these base calendars are their supplement's text, word for word, "
                     "and are not on the known list: " + ", ".join(new))
    left = sum(len(v) for v in found.values())
    return "ok", (f"{left} known base calendar(s) still their supplement's copy, waiting on a "
                  "person's fetch" if left else "no base calendar is its supplement's copy")


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


REPORT_PAGES_TEST = r"""
import { readFileSync } from "node:fs";
import { onRequest } from %s;
const pages = JSON.parse(readFileSync(%s, "utf8"));
let rows = 0;
const env = { DB: { prepare: () => ({ bind: () => ({ first: async () => 1,
  run: async () => { rows++; } }) }) } };
const bad = [];
for (const [url, record, file] of pages) {
  // The built page itself, served at its own address and nowhere else.
  env.ASSETS = { fetch: async u => new URL(u).pathname === url
    ? new Response(readFileSync(file, "utf8")) : new Response("", { status: 404 }) };
  const before = rows;
  const r = await onRequest({ env, request: new Request("https://graniterecord.org/api/report", {
    method: "POST", headers: { "Origin": "https://graniterecord.org",
                               "Content-Type": "application/json" },
    body: JSON.stringify({ record, url, tab: "", build: "", elapsed: 9000,
                           field: record.startsWith("translation:") ? "translation" : "other",
                           note: "A check that a report from this page is kept." }) }) });
  if (r.status !== 204 || rows !== before + 1) bad.push(url);
}
console.log(JSON.stringify({ n: pages.length, bad }));
"""


def _report_pages_kept(site, fn, node):
    """Send one report from every built legislator and committee page, as the
    box on that page would, through the Function's own onRequest with the page
    served from disk. Returns ({kind: pages sent from}, [addresses not kept],
    pages with no box). Separate from the check so it can be pointed at a
    built site and a report.js in two different folders."""
    pages, sent, boxless = [], Counter(), 0
    for folder, glob_name, kind in (("legislator", "GR_MEMBER", "member"),
                                    ("committee", "GR_COMMITTEE", "committee"),
                                    ("town", "GR_REPORT", "town")):
        for f in sorted((Path(site) / folder).glob("*.html")):
            m = re.search(rf'window\.{glob_name}="([^"]*)"',
                          f.read_text(encoding="utf-8", errors="replace"))
            if not m:
                boxless += 1          # no global, so app.js mounts no box
                continue
            # A town's global is the whole record, "town:<slug>" (10 November 2026).
            rec = m.group(1) if kind == "town" else f"{kind}:{m.group(1)}"
            pages.append([f"/{folder}/{f.stem}", rec, str(f.resolve())])
            sent[kind] += 1
    # And from every page built in another language, a mistake in its
    # translation (24 October 2026), as components.js's box sends one.
    for f in sorted((Path(site) / "es").rglob("*.html")) if (Path(site) / "es").is_dir() else []:
        rel = f.relative_to(site).with_suffix("").as_posix()
        url = "/" + (rel[:-len("index")] if rel.split("/")[-1] == "index" else rel)
        pages.append([url, f"translation:{url}", str(f.resolve())])
        sent["translation"] += 1
    root = Path(tempfile.mkdtemp())
    try:
        (root / "pages.json").write_text(json.dumps(pages), encoding="utf-8")
        t = root / "t.mjs"
        t.write_text(REPORT_PAGES_TEST % (json.dumps(Path(fn).resolve().as_uri()),
                                          json.dumps(str(root / "pages.json"))),
                     encoding="utf-8")
        r = _run([node, str(t)], capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, (r.stdout + r.stderr).strip()[-400:]
        out = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert out["n"] == len(pages), f"node read {out['n']} of {len(pages)} pages"
    return dict(sent), out["bad"], boxless


@check("data", "a report from every built legislator and committee page is one the Function keeps")
def _report_pages():
    """The box is on every legislator and committee page, and the Function
    refuses a report whose address it does not recognise -- answering 204, so
    the reader is thanked either way. From 12 to 24 September the rule said
    every legislator address ends in a number; eight former members' pages,
    /legislator/adam-schroadter among them, have a slug of the name alone,
    and every report sent from them was dropped. The code check tests shapes;
    this sends one report from each page the build actually wrote, so the
    next slug the builder learns to write is tested the night it appears."""
    site, fn = Path("site"), Path("functions/api/report.js")
    if not (site / "legislator").is_dir():
        return "skip", "site/legislator not built"
    if not fn.exists():
        return "skip", "no functions/api/report.js here"
    node = shutil.which("node")
    if not node:
        return "skip", "node is not on PATH"
    sent, bad, boxless = _report_pages_kept(site, fn, node)
    total = sum(sent.values())
    assert sent.get("member"), "no legislator page carries GR_MEMBER, so none has a report box"
    assert not (site / "town").is_dir() or sent.get("town"), (
        "no town page carries GR_REPORT, so none has a report box")
    assert not bad, (f"{len(bad)} of {total:,} pages send a report the Function drops while "
                     f"thanking the reader: " + ", ".join(bad[:6]))
    return "ok", (f"{sent.get('member', 0):,} legislator, {sent.get('committee', 0):,} committee, "
                  f"{sent.get('town', 0):,} town and {sent.get('translation', 0):,} Spanish pages each sent one report, and every "
                  "one was kept"
                  + (f"; {boxless} pages carry no box" if boxless else ""))


@check("data", "a refusal met on this laptop has reached the bucket")
def _refusal_reached_the_bucket():
    """refusal.note() on a stood-down laptop sends the refusal to the bucket's
    state/refused.json, which is the record GitHub's night reads. When the
    bucket could not be reached it said so loudly and left
    archive/cloud/refusal-unsent.json; until that goes, a refusal this laptop
    met does not stop the night, which asks the same address every morning.
    Sending it is harmless and reads nothing from the General Court, but it is
    still the person's to see: the remedy is named, not run."""
    p = Path("archive/cloud/refusal-unsent.json")
    if not p.exists():
        return "ok", "no refusal met here is waiting to reach the bucket"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    why = str(d.get("why") or "")
    if "waiting behind" in why or "newer refusal" in why:
        # The bucket holds another refusal, which stops the night for now;
        # this one is not lost, but it needs a person before it can be sent.
        raise AssertionError(
            f"{p} says a refusal met on this laptop at {d.get('at', '?')} is not in the "
            f"bucket: {why}. The night is stopped by the bucket's for now. python3 "
            "src/ops/cloud.py pull says where things stand; python3 refusal.py --clear removes the "
            "marker with the refusal, if a person has decided it is over.")
    raise AssertionError(
        f"{p} says a refusal met on this laptop at {d.get('at', '?')} never reached the "
        "bucket" + (f" ({why})" if why else "") + ", so GitHub's night would still ask the "
        "General Court. python3 src/ops/cloud.py send-refusal sends it (the bucket, not the General "
        "Court); python3 refusal.py --clear removes the marker with the refusal, if a "
        "person has decided it is over.")


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


@check("data", "every speaker a House sitting page names on a counted motion spoke on the question "
       "the journal decides with that count, and every speech it decides so is named")
def _every_speaker_where_the_journal_decides():
    """The third review of 3 October 2026 read every name the second pass put
    on a motion against the journal, with a reader of its own, and found what
    no check here could: a speech that fell through to a later roll call
    (Rep. Rowe on HB 1670's floor amendment of 15 February 2012, whose
    committee amendment he spoke for), forty-five chips naming two members,
    and two dozen correct names taken off -- the comma form of "moved ...,
    spoke in favor", a roll call the journal prints one vote off its
    ballots, and divisions whose docket count was a typo. The data check
    that held speakers asked only that nobody be on both sides of a motion.

    This reads the BUILT pages and the journal text, by a walk written apart
    from journal_days': the first decision the journal prints after a speech
    is its question's, read past a Call of the House, the previous question
    or a motion to print and their own decisions, and past a motion to set
    the question aside that the journal shows failing. Then, for every
    motion drawn with a count the journal prints once in the bill's stretch,
    every member named on it has a speech of that side decided there (or,
    for the bill's one motion of the day, a speech the journal decides
    nothing after), and every speech decided there is named on it or under
    "also spoke". A motion drawn from another day's row ("Printed in the
    journal with this sitting"), or whose count another motion of the bill
    shares, is not held."""
    root, jroot = Path("site/session"), Path("journals")
    if not (root / "H").exists() or not jroot.exists():
        return "skip", "no site/session/H or journals/ here"
    bad, held, slips = _speakers_against_journal(root, jroot)
    assert held, "no counted motion of a House sitting page was held to the journal"
    assert not bad, (f"{len(bad)} speaker(s) the journal does not place where the page does: "
                     + "; ".join(bad[:4]))
    return "ok", (f"{held:,} counted motions held to the journal: every speaker named on one "
                  "spoke on its question, and every speech decided by its count is named"
                  + (f"; the journal's own slips, read as the member each names and said here "
                     f"so they are seen: {'; '.join(slips)}" if slips else ""))


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
    # FROM THE PAGES. This read site/bills/<year>/<ID>.json, which since the
    # records moved inside the pages holds only the few too large to inline,
    # so it checked a handful of messages and passed while 108 of 175 cited a
    # calendar from another year.
    if not Path("site/bill").is_dir():
        return "skip", "no bill pages built"
    # EXACTLY two stops, not three. The governor quotes a letter in
    # HB475's message with a real ellipsis in it, and a pattern reading
    # "..." as a defect flags the site's most careful quotation as its
    # worst.
    junk = re.compile(r"HOUSERECORD|SENATERECORD|\x0c|(?<!\.)\.\.(?!\.)"
                      r"|\w- \w|  ")
    url_year = re.compile(r"(?:calendars|journals)(?:%5C|\\|/)(\d{4})(?:%5C|\\|/)",
                          re.I)
    n, bad = 0, []
    for _year, _bid, d in _site_records():
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
        else:
            src = v["source"]
            m = url_year.search(src.get("url") or "")
            if m and str(src.get("year") or "") and m.group(1) != str(src["year"]):
                bad.append(f"{d.get('id')} of {d.get('term')} was printed in "
                           f"{src['year']} and cites a {m.group(1)} calendar")
    if not n:
        return "skip", "no bill carries a veto message"
    assert not bad, (f"{len(bad)} of {n} veto messages are not fit to quote: "
                     f"{'; '.join(bad[:3])}")
    return "ok", (f"{n} veto messages, each whole, attributed and citing a "
                  f"calendar of its own year")


@check("data", "the note about voice votes is not printed over the roll calls")
def _vote_note_truth():
    """narrative counts the floor votes the DOCKET calls voice or division
    votes; the table under the note comes from RollCallSummary, which knows
    votes the docket line never mentions. On 7,872 bills of five terms the
    note read "there is no record of how individual legislators voted"
    directly above the record of how they voted."""
    if not Path("site/bill").is_dir():
        return "skip", "no bill pages built"
    bad, n = [], 0
    for year, bid, rec in _site_records():
        if not rec.get("rollcalls"):
            continue
        n += 1
        if (rec.get("vote_note") or "").startswith("Every floor vote"):
            bad.append(f"{bid} of {year}")
    assert not bad, (f"{len(bad):,} of {n:,} bills with roll calls say every "
                     f"vote was a voice vote: {', '.join(bad[:4])}")
    return "ok", f"{n:,} bills with roll calls, none denying them"


@check("data", "no law or veto says \"No recorded action yet\"")
def _next_step_settled():
    """next_step() reads a narrated docket, and with none it answers "No
    recorded action yet". When the docket's signature line began settling
    the twelve unnarrated terms' bills on 11 September, about 10,000 laws
    of 1989-2016 said that in their status box, under a chip reading
    "Signed into law", and it was published before anything looked. Read
    from the built pages and the index together."""
    rows = _site_bills()
    if rows is None:
        return "skip", "no site built"
    kinds = {(str(r.get("year")), r["id"].upper()): r.get("kind") for r in rows}
    bad, n = [], 0
    for year, bid, rec in _site_records():
        if kinds.get((year, bid)) not in ("law", "veto"):
            continue
        n += 1
        step = rec.get("next_step") or ""
        if step.startswith("No recorded action"):
            bad.append(f"{bid} of {year}: no action recorded")
        # AND NOTHING STILL MOVING. The signature was read off the last
        # docket line alone, so anything filed after it -- an effective
        # date, a chaptering row -- left 185 laws saying "In progress" or
        # "Enrolled. Pending the governor's signature" under a chip that
        # said they were law, 31 of them in the current term.
        elif kinds.get((year, bid)) == "law" and re.match(
                r"(In progress|In committee|Pending|Enrolled\. Pending)", step):
            bad.append(f"{bid} of {year}: {step[:40]!r} under \"law\"")
    assert not bad, (f"{len(bad):,} of {n:,} laws and vetoes say no action "
                     f"is recorded: {', '.join(bad[:4])}")
    return "ok", f"{n:,} laws and vetoes, each saying what became of it"


@check("data", "a committee report cites the calendar of its own year")
def _report_citations():
    """All 7,376 House report citations of 2013-2022 linked a 2023 or 2024
    calendar -- committee_reports() fell back to calendars.json's bare "HC n"
    key, which holds the latest year -- and 4,391 printed that calendar's date
    as the day the report was printed: 2015's CACR1 read "printed 2024-05-03".
    The veto messages had the same fault and a check; the reports had none.
    Read from the pages: a report's link must be to the year its source
    names."""
    if not Path("site/bill").is_dir():
        return "skip", "no bill pages built"
    url_year = re.compile(r"(?:%5C|/)(\d{4})(?:%5C|/)", re.I)
    n, bad = 0, []
    for year, bid, rec in _site_records():
        for rep in (rec.get("reports") or []):
            m = url_year.search(rep.get("cite_url") or "")
            sy = re.search(r"(\d{4})\s*$", rep.get("source") or "")
            if not (m and sy):
                continue
            n += 1
            if m.group(1) != sy.group(1):
                bad.append(f"{bid} of {year}: {rep.get('source')} links a "
                           f"{m.group(1)} calendar")
    if not n:
        return "skip", "no committee report carries a calendar link"
    assert not bad, (f"{len(bad):,} of {n:,} report citations link a calendar "
                     f"from another year: {'; '.join(bad[:3])}")
    return "ok", f"{n:,} report citations, each to its own year's calendar"


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

    AND THE STATUS CHIP'S WORDS, in the same reading of the index (2 October
    2026; a check of its own until then, "a bill both chambers passed does
    not read "Passed one chamber""). The chip and the rail beside it are one
    fact said twice. Before 23 September, 49 bills read "Passed one chamber"
    beside a rail whose second chamber was passed -- CACR 13 of 2026 among
    them, adopted by the Senate 23-1 -- and 30 resolutions drew a governor
    who never sees a resolution. Each of the three is said by name when it
    fails, and all that fail are said together.
    """
    rows = _site_bills()
    if rows is None:
        return "skip", "the bill index is not built"
    bad, n, laws, pppp, vetoes = [], 0, 0, 0, 0
    both, gov = [], []
    for b in rows:
        p = b.get("passage") or ""
        kind = b.get("kind") or ""
        if kind == "law":
            laws += 1
        key = (b.get("term"), b.get("id"))
        # _RAIL_KNOWN is named further down, where the second check stood.
        if (len(p) == 5 and p[2] == "p" and b.get("status") == "Passed one chamber"
                and key not in _RAIL_KNOWN):
            both.append(f"{key[0]} {key[1]} {p}")
        if (len(p) == 5 and p[3] != "-"
                and re.match(r"^(?:SS)?(?:HCR|SCR|CACR)\d", b.get("id") or "")):
            gov.append(f"{key[0]} {key[1]} {p}")
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
    wrong = ([f"{len(bad)} of {n:,} rails disagree with the record: "
              f"{'; '.join(bad[:3])}"] if bad else []) \
        + ([f"{len(both)} bills read \"Passed one chamber\" beside a rail "
            f"that passed the second chamber: {'; '.join(both[:5])}"] if both else []) \
        + ([f"{len(gov)} resolutions draw a governor on their rail: "
            f"{'; '.join(gov[:5])}"] if gov else [])
    assert not wrong, ". AND ".join(wrong)
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
                  f"{vetoes} vetoed and crossed at the governor; of {len(rows):,} "
                  "bills, no second chamber passed under \"Passed one chamber\", "
                  "and no governor on a resolution")


# Where the rail and the label disagree because the RAIL is wrong. None: CACR
# 9 of 1995 was the one named here until 2 October 2026, when its rail was
# made to stop in the House (build_site_v2.passage). Kept, empty, so that a
# new one has to be named to pass.
_RAIL_KNOWN = set()


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


@check("data", "every sponsor LsrSponsors.txt gives the session's bills who sat in its term is "
       "on the bill, once, and a member the database knows has a chamber")
def _sponsors_on_record():
    """The data side of _sponsors_who_left. LsrSponsors.txt is the General
    Court's every sponsor of the session's requests, sitting or not; LsrsOnly
    .txt holds the sitting only. Read from the second, 168 sponsorships of
    2025-2026 by 20 members who had left were on no page -- LsrSponsors.txt:
    7674, "2026|2787|6|11371|0", is Rep. Morton on HB 1449 -- 7 bills listed
    their only sponsor twice, by PersonID and by employee number (CACR 30's
    Rep. Oppel, 11182 and 409281; HB 728's Rep. Doucette, 893 and 377220),
    and 34 primes who had left had no chamber (HB 1036's Rep. Vose).

    For the newest term: every LsrSponsors.txt row of its years, on the bill
    its request is (bills.json's lsr_year and lsr_num), is among that bill's
    sponsors -- unless its member is neither sitting (legislators.txt) nor
    cast a ballot in the term, and then it is not: HB 171 carries the request
    of Reps. Rochefort and Massimilla, who left before the term began, and
    its own text does not name them; no bill lists one person twice, an employee number counted as
    the PersonID db/Legislators.psv gives it; and every sponsor whose id is a
    PersonID there has a chamber. Two people of one name are two ids: HB 583's
    Patrick Long (409256) and Pat Long (218767)."""
    sp, bl, ls = Path("data/sponsors.json"), Path("data/bills.json"), Path("LsrSponsors.txt")
    if not (sp.exists() and bl.exists() and ls.exists()):
        return "skip", "data/sponsors.json, data/bills.json or LsrSponsors.txt not here"
    sponsors = json.loads(sp.read_text(encoding="utf-8"))
    bills = json.loads(bl.read_text(encoding="utf-8"))
    if not all(re.match(r"^\d{4}-\d{4}$", k) for k in sponsors):
        return "skip", "data/sponsors.json is not keyed on the term yet"
    newest = max(bills)
    years = set(newest.split("-"))
    mine = sponsors.get(newest) or {}
    by_lsr = {(str(r.get("lsr_year") or ""), str(r.get("lsr_num") or "").zfill(4)): b
              for b, r in (bills.get(newest) or {}).items()}
    pid = {}        # Employeeno -> PersonID
    people = set()  # PersonID
    lp, lc = Path("db/Legislators.psv"), Path("db/_columns.json")
    if lp.exists() and lc.exists():
        cols = json.loads(lc.read_text(encoding="utf-8")).get("Legislators") or []
        if "PersonID" in cols and "Employeeno" in cols:
            ip, ie = cols.index("PersonID"), cols.index("Employeeno")
            for line in lp.read_text(encoding="utf-8", errors="replace").splitlines():
                f = [x.strip() for x in line.split("|")]
                if len(f) == len(cols) and f[ip]:
                    people.add(f[ip])
                    if f[ie]:
                        pid[f[ie]] = f[ip]

    def who(x):
        m = str(x.get("member_id") or "")
        return pid.get(m, m)
    # A member who is not sitting and cast no ballot in the term never sat in
    # it, and is on none of its bills: HB 171's Reps. Rochefort and
    # Massimilla, whose request it carries and whose names its text does not.
    sitting = set()
    lt = Path("legislators.txt")
    if lt.exists():
        sitting = {ln.split("|")[0].strip().lstrip("﻿")
                   for ln in lt.read_text(encoding="utf-8-sig", errors="replace").splitlines()
                   if ln.strip()}
    sat = set()
    for f in [Path("RollCallHistory.txt"),
              *(Path("records/rollcalls") / f"RollCallHistory_{y}.txt" for y in sorted(years))]:
        if f.exists():
            for ln in f.read_text(encoding="utf-8-sig", errors="replace").splitlines():
                p = ln.split("|")
                if len(p) == 8 and p[0].strip() in years and p[4].strip():
                    sat.add(p[4].strip())
    missing, extra, rows, outside = [], [], 0, 0
    for line in ls.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        f = [x.strip() for x in line.split("|")]
        if len(f) != 5 or f[0] not in years:
            continue
        bill = by_lsr.get((f[0], f[1].zfill(4)))
        if not bill:
            continue        # a request with no bill: build_data leaves it out, and says so
        rows += 1
        on = f[3] in {who(x) for x in mine.get(bill) or []}
        if f[3] not in sitting and f[3] not in sat:
            outside += 1
            if on:
                extra.append((bill, f[3]))
        elif not on:
            missing.append((bill, f[3]))
    twice = sorted(b for b, v in mine.items()
                   if any(n > 1 for i, n in Counter(who(x) for x in v).items() if i))
    nochamber = sorted({b for b, v in mine.items() for x in v
                        if str(x.get("member_id") or "") in people
                        and x.get("chamber") not in ("H", "S")})
    assert rows, f"no row of LsrSponsors.txt names a bill of {newest}"
    bad = []
    if missing:
        bad.append(f"{len(missing):,} LsrSponsors.txt row(s) on {len({b for b, _ in missing}):,} "
                   f"bill(s) are not on the bill: "
                   + ", ".join(f"{b} {m}" for b, m in sorted(missing)[:6]))
    if extra:
        bad.append(f"{len(extra):,} sponsor(s) who never sat in {newest} are on its bills: "
                   + ", ".join(f"{b} {m}" for b, m in sorted(extra)[:6]))
    if twice:
        bad.append(f"{len(twice)} bill(s) list one person twice: {', '.join(twice[:8])}")
    if nochamber:
        bad.append(f"{len(nochamber)} bill(s) have a sponsor the database knows with no chamber: "
                   + ", ".join(nochamber[:8]))
    assert not bad, f"{newest}'s sponsors: " + "; ".join(bad)
    return "ok", (f"{newest}: all {rows - outside:,} LsrSponsors.txt rows of members who sat in it "
                  f"on their bills and none of the {outside} of members who did not, nobody listed "
                  f"twice, and every sponsor the database knows has a chamber"
                  + ("" if people else " (db/Legislators.psv not here, so ids not joined)"))


@check("data", "every sponsor row of the session's term whose member sits in its chamber carries the "
       "district and county the term's roster gives them")
def _sponsor_seats_data():
    """The data side of _sitting_sponsors_take_the_roster_seat. data/sponsors.json's rows of
    2025-2026 carried, for fifteen senators who had sat in the House, the House seat of their
    record in past_members.json, matched by name: 2,471 rows on 1,049 bills, Sen. Tim McGough's
    district "12" (Hills 12, his House seat) where the roster, the database's active record,
    the status page and the owner say District 11. The labels beside them were right.

    For the newest term: every row whose member sits in the row's chamber -- by the roster's
    id, or on a row carrying another id (the status page's) by first and last name among that
    chamber's members where one alone answers, as build_data seats them -- has the roster's
    district, as a number, and its county, in full or abbreviated. The roster is the term's
    own: data/frozen/<term>/legislators.json while the installed one is the next House's."""
    sp, lg = Path("data/sponsors.json"), Path("data/legislators.json")
    if not (sp.exists() and lg.exists()):
        return "skip", "data/sponsors.json or data/legislators.json not here"
    sponsors = json.loads(sp.read_text(encoding="utf-8"))
    if not sponsors or not all(re.match(r"^\d{4}-\d{4}$", k) for k in sponsors):
        return "skip", "data/sponsors.json is not keyed on the term yet"
    newest = max(sponsors)
    own = Path("data/frozen") / newest / "legislators.json"
    roster = {str(m.get("id")): m for m in json.loads((own if own.exists() else lg).read_text(
        encoding="utf-8"))}

    def first_last(name):
        # build_data's _first_last: "McGough, Tim" and "Tim McGough" are both ("tim", "mcgough").
        n = (name or "").strip()
        if "," in n:
            last, first = [x.strip() for x in n.split(",", 1)]
            n = f"{first} {last}"
        w = re.sub(r"[^A-Za-z ]", " ", n).lower().split()
        return (w[0], w[-1]) if len(w) >= 2 else None
    by_name = {}
    for m in roster.values():
        by_name.setdefault((first_last(m.get("name")), m.get("chamber")), []).append(m)
    rows = members = 0
    seen, wrong = set(), Counter()
    for bill, people in (sponsors.get(newest) or {}).items():
        for x in people or []:
            ch = (x.get("chamber") or "")[:1]
            m = roster.get(str(x.get("member_id") or ""))
            if not (m and m.get("chamber") == ch):
                got = by_name.get((first_last(x.get("name")), ch)) or []
                m = got[0] if len(got) == 1 else None
            if m is None or not str(x.get("district") or ""):
                continue
            rows += 1
            if m["id"] not in seen:
                seen.add(m["id"])
                members += 1
            same = (str(x.get("district")).lstrip("0") == str(m.get("district") or "").lstrip("0")
                    and (x.get("county") or "") in (m.get("county"), m.get("county_abbr"), ""))
            if not same:
                seat = (f"SD{m.get('district')}" if m.get("chamber") == "S"
                        else f"{m.get('county_abbr')} {m.get('district')}")
                wrong[f"{m.get('name')} ({seat}) as {x.get('county')} {x.get('district')}"] += 1
    assert rows, f"no sponsor row of {newest} is a sitting member's"
    assert not wrong, (f"{sum(wrong.values()):,} sponsor row(s) of {newest} give {len(wrong)} sitting "
                       "member(s) another seat than the roster's: "
                       + "; ".join(f"{k} on {n:,} row(s)" for k, n in wrong.most_common(6))
                       + ". Rebuild with python3 src/parse/build_data.py --dir . --out data")
    return "ok", (f"{newest}: {rows:,} sponsor rows of {members} sitting members, each with the "
                  "district and county the term's roster gives them")


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
    rc = Path("records/rollcalls")
    hist = sorted(rc.glob("RollCallHistory_*.txt")) if rc.exists() else []
    if not hist:
        return "skip", "no records/rollcalls/RollCallHistory_*.txt here"
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
    per_term = {}
    for (year, no_party, no_name), cast in _ballot_census()["named"].items():
        y = int(year or 0)
        if not y:
            continue
        t = f"{y - (1 - y % 2)}-{y - (1 - y % 2) + 1}"
        tot, nop, non = per_term.get(t, (0, 0, 0))
        per_term[t] = (tot + cast, nop + cast * no_party, non + cast * no_name)

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

    # A PARTY, ON EVERY TERM. The rule was narrowed to 2017 onward for a while
    # and covers every term again; why is worth keeping, because it is the
    # difference between a guard that was loosened and one that was true at the
    # time it was narrow.
    #
    # 24 years of roll calls arrived at once and 773,506 of their ballots had
    # no party: 88% of 1999-2000, 57% of 2011-2012. No roster on
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
    p = Path("generated/careers.json")
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


@check("data", "no sponsor row is a heading, a seat, an honorific or a name with a figure in it, and the five senators printed as Rep. are theirs")
def _sponsor_rows_data():
    """The same rule on text_sponsors.json and the lists past_sponsors.json publishes for
    2023-2024: 0 rows naming REFERRED, 0 seat-only rows, 0 names containing a figure, and
    0 names containing "Rep." or "Sen." -- the chamber is a field, and 2005 HB 64's "Rep.
    Rep. A. Tilton" was a sponsor called "Rep. A. Tilton". These are the rows the pages
    list and sponsors.csv exports. And the five senators printed as "Rep. X, Dist N" that
    the site had placed on representatives of their surnames."""
    ts = Path("text_sponsors.json")
    if not ts.exists():
        return "skip", "no text_sponsors.json here"
    text = json.loads(ts.read_text(encoding="utf-8"))
    rows = [(t, b, r) for t, bs in text.items() for b, rs in bs.items() for r in rs]
    ps = Path("past_sponsors.json")
    if ps.exists():
        doc = json.loads(ps.read_text(encoding="utf-8"))
        rows += [(t, b, r) for t, bs in doc.items() for b, e in bs.items()
                 for r in e.get("publish") or ()]
    seatish = re.compile(r"^(?:[A-Za-z]+\.?\s*)?\d+$|^(?:dist|district|dsit|dit)\.?$", re.I)
    bad = [f"{t} {b} {r.get('name')!r}" for t, b, r in rows
           if "REFERRED" in (r.get("name") or "").upper()
           or re.search(r"\d", r.get("name") or "") or seatish.match((r.get("name") or "").strip())
           or SPONSOR_HONORIFIC.search(r.get("name") or "")]
    assert not bad, (f"{len(bad)} sponsor rows are not a person, e.g. {bad[:6]}: rebuild "
                     "with python3 src/parse/text_sponsors.py --apply")
    five = [("2001-2002", "HB428", "Boyce", "209042"), ("2003-2004", "HB1360", "Boyce", "209042"),
            ("2001-2002", "SB84", "O'Neil", "209046"), ("2001-2002", "HB1301", "Johnson", "205015"),
            ("2003-2004", "HB1242", "Kenney", "209049")]
    wrong = []
    for t, b, name, want in five:
        got = [r.get("member_id") for r in (text.get(t) or {}).get(b) or ()
               if (r.get("as_printed") or "").startswith(f"Rep. {name}, Dist")]
        if got != [want]:
            wrong.append(f"{t} {b} {name}: {got}")
    assert not wrong, f"a senator printed as Rep. is not theirs: {wrong}"
    return "ok", f"{len(rows):,} sponsor rows, every one a person or a committee; the five senators placed"


@check("data", "past_sponsors.json gives 2023 HB 32 and 2024 HB 1713 to their prime sponsor, and every 2023-2024 bill a verdict")
def _past_sponsors_data():
    """The two primes the bill status page had wrong, on the file the build publishes
    from, and the 37 co-sponsorships it had left off: Steve Shurtleff (376628) on 29
    bills, Kimberly Abare (409060) on 4 and Rep. Lorrie J. Carey (377080) on 4.

    COUNTED ON WHAT IS PUBLISHED, not on the record's rows: the record's list for a bill
    that agrees with its page or has none, and the list text_sponsors.py read off the page
    for one that differs -- the two lists merge_into gives the site and sponsors.csv. And
    pinned on two bills: CACR 9 names Shurtleff and Abare, and 2024 HB 1429 links Carey,
    whom the site named H. Robert Menear until member_corrections.json said otherwise."""
    p = Path("past_sponsors.json")
    if not p.exists():
        return "skip", "no past_sponsors.json here (python3 src/parse/past_sponsors.py --apply)"
    t = json.loads(p.read_text(encoding="utf-8")).get("2023-2024") or {}
    for bid in ("HB32", "HB1713"):
        pub = (t.get(bid) or {}).get("publish") or []
        prime = [r.get("employee") for r in pub if r.get("prime")]
        assert prime == ["376628"] and pub[0].get("employee") == "376628", (
            f"2023-2024 {bid} publishes prime {prime}, first {pub[:1]}: both print Rep. "
            "Shurtleff first and the record marks him prime")
    odd = [b for b, e in t.items() if e.get("page") not in ("agrees", "differs", "no page")
           or (e.get("page") != "differs" and not e.get("publish"))]
    assert not odd, f"2023-2024 bills with no verdict or nothing to publish: {odd[:8]}"
    ts = Path("text_sponsors.json")
    text = (json.loads(ts.read_text(encoding="utf-8")).get("2023-2024") or {}) if ts.exists() else {}
    published = {b: (e.get("publish") or (text.get(b) if e.get("page") == "differs" else None) or [])
                 for b, e in t.items()}
    three = ("376628", "409060", "377080")
    restored = Counter(m for rows in published.values()
                       for m in {x for r in rows for x in (r.get("employee"), r.get("member_id"))
                                 if x in three})
    assert restored["376628"] >= 29 and restored["409060"] >= 4 and restored["377080"] >= 4, (
        f"the bills whose published list names Shurtleff, Abare and Carey: {dict(restored)}")
    cacr9 = {r.get("member_id") for r in published.get("CACR9") or ()}
    assert {"376628", "409060"} <= cacr9, (
        f"2023 CACR 9 publishes {sorted(x for x in cacr9 if x)}: it prints Rep. Shurtleff "
        "and Rep. Abare, and the record lists both")
    carey = [r for r in published.get("HB1429") or () if r.get("member_id") == "377080"]
    assert carey, (
        "2024 HB 1429 does not link employee 377080, printed Rep. Carey, Merr. 1: she is Rep. "
        "Lorrie J. Carey (member_corrections.json). If data/member_votes.json predates that "
        "correction, run python3 src/parse/build_data.py and then python3 "
        "src/parse/past_sponsors.py --apply")
    n = Counter(e.get("page") for e in t.values())
    return "ok", (f"HB 32 and HB 1713 prime Shurtleff; Shurtleff on {restored['376628']} "
                  f"published lists, Abare on {restored['409060']}, Carey on "
                  f"{restored['377080']}; {n['agrees']:,} bills agree with their page, "
                  f"{n['differs']:,} published as printed, {n['no page']:,} have no page")


@check("data", "every 2023-2024 sponsor published under a member sits in the chamber that member voted in that term")
def _past_sponsors_chamber():
    """The bill status page files six sitting senators of 2023-2024 under the House --
    Donna Soucy, Jeb Bradley, Carrie Gendreau, Lou D'Allesandro, Shannon Chandley and
    Rebecca Whitley -- and past_sponsors.records took that chamber before the one the bill
    prints. past_sponsors.json carried H for them on 906 rows; seat_into dated all but 34
    from the printed line, and those 34 read "Sen. Donna Soucy (D - SD18)" under
    Representatives while sponsors.csv exported them as H. Every published 2023-2024 row
    with a member id is held here to the chamber that member's ballots were cast in that
    term, read from data/member_votes.json rather than from anything past_sponsors wrote.
    A member with no ballot that term is counted and not judged."""
    p, mv = Path("past_sponsors.json"), Path("data/member_votes.json")
    if not p.exists() or not mv.exists():
        return "skip", "no past_sponsors.json or data/member_votes.json here"
    term = "2023-2024"
    t = json.loads(p.read_text(encoding="utf-8")).get(term) or {}
    ts = Path("text_sponsors.json")
    text = (json.loads(ts.read_text(encoding="utf-8")).get(term) or {}) if ts.exists() else {}
    voted = {}
    for year, body, member in _ballot_census()["seats"]:
        y = str(year or "")
        if y.isdigit() and body in ("H", "S"):
            y = int(y)
            if f"{y - (1 - y % 2)}-{y - (1 - y % 2) + 1}" == term:
                voted.setdefault(member, set()).add(body)
    bad, n, unvoted = [], 0, 0
    for bid, e in sorted(t.items()):
        rows = e.get("publish") or (text.get(bid) if e.get("page") == "differs" else None) or []
        for r in rows:
            mid = str(r.get("member_id") or "")
            if not mid:
                continue
            if mid not in voted:
                unvoted += 1
                continue
            n += 1
            if r.get("chamber") not in voted[mid]:
                bad.append(f"{bid} {r.get('name')} ({mid}) {r.get('chamber') or 'no chamber'}, "
                           f"voted {'/'.join(sorted(voted[mid]))}")
    assert n, "no published 2023-2024 row carries a member id with a ballot that term"
    assert not bad, (f"{len(bad)} published 2023-2024 sponsor row(s) sit in a chamber their "
                     f"member did not vote in that term, e.g. {bad[:6]}: rebuild with python3 "
                     "src/parse/past_sponsors.py --apply")
    return "ok", (f"{n:,} published rows with a member id, each in the chamber of that "
                  f"member's {term} ballots"
                  + (f"; {unvoted:,} under a member with no ballot that term" if unvoted else ""))


@check("data", "the Learn pages state the record's own figures, and none is left unfilled")
def _learn_figures():
    """civics.py names each count as [[name]] and build_civics fills it from the
    built site. They were typed until 14 September and had drifted: "4,230
    bills on this site" of 33,683, "68 vetoed bills" across "two terms" of
    nineteen. A page that published a bare [[name]], or a count that is not the
    index's, fails here."""
    page = Path("site") / "learn" / "how-a-bill-becomes-law.html"
    idx = _site_bills() if page.exists() else None
    if idx is None:
        return "skip", "the Learn pages or the index are not built"
    unfilled = [p.name for p in (Path("site") / "learn").glob("*.html")
                if "[[" in p.read_text(encoding="utf-8", errors="replace")]
    assert not unfilled, f"a figure left unfilled on {unfilled}"
    n = len(idx)
    # "in this record" since the Learn pages' wording of 9 October 2026 (E6),
    # as the index check reads it.
    assert f"Across the {n:,} bills in this record" in page.read_text(encoding="utf-8"), (
        f"how-a-bill-becomes-law does not state the index's {n:,} bills: built before "
        "build_civics filled the figures, or from another index")
    return "ok", f"every Learn page filled; the bill page states the index's {n:,} bills"


@check("data", "the page of numbers is public, and reachable from the hub and the sitemap")
def _numbers_page_public():
    """learn_numbers.py writes /learn/by-the-numbers.html, and it is public: it
    must not ask search engines to ignore it, and the Learn hub and the sitemap
    must both lead to it. It shipped as a draft that asked for all three the
    other way round, so this is that guard reversed rather than a deleted one --
    a page reached only by knowing its address is one nobody finds, and losing
    the hub link or the sitemap entry to a template change would put it back in
    the drawer silently.

    The build-fault half is the reason this is a check at all: an unfilled
    [[figure]] or a traceback in the body is a page that publishes a hole where
    a number should be."""
    site = Path("site")
    page = site / "learn" / "by-the-numbers.html"
    if not page.exists():
        return "skip", "learn/by-the-numbers.html not built"
    text = page.read_text(encoding="utf-8", errors="replace")
    assert '<meta name="robots" content="noindex">' not in text, (
        "the page of numbers is public and should not ask to be delisted")
    assert "[[" not in text and "Traceback" not in text, "the page carries a build fault"
    hub = site / "resources.html"
    if hub.exists():
        assert "by-the-numbers" in hub.read_text(encoding="utf-8", errors="replace"), (
            "the Resources hub does not link the page of numbers")
    sm = site / "sitemap.xml"
    if sm.exists():
        assert "by-the-numbers" in sm.read_text(encoding="utf-8", errors="replace"), (
            "the sitemap does not list the page of numbers")
    return "ok", "indexable, on the Resources hub and in the sitemap"


@check("data", "a committee's members are the ones on it today, not every seat the table still holds")
def _committee_rosters_current():
    """Staff reading the site on 15 September found wrong committee rosters.
    The database's CommitteeMembers keeps a seat after its term, and the pages
    listed every one: Senate Finance showed 24 members, and 11 sitting senators
    on Judiciary where the Senate names 5. A member is on a committee's page
    now only if their own roster entry lists that committee -- House Finance's
    divisions counting as Finance -- or, for a sitting member whose entry lists
    none, if the seat table does. No member who has left is on any roster."""
    site = Path("site")
    legs_p = site / "legislators.json"
    files = sorted((site / "committee").glob("*.json"))
    if not (legs_p.exists() and files):
        return "skip", "the committee pages or the roster are not built"
    legs = {str(m.get("id")): m for m in json.loads(legs_p.read_text(encoding="utf-8"))}
    bad, n = [], 0
    for f in files:
        c = json.loads(f.read_text(encoding="utf-8"))
        for m in c.get("members") or []:
            n += 1
            lg = legs.get(str(m.get("id")))
            if not lg:
                bad.append(f"{c.get('code')}: {m.get('name')} does not sit")
                continue
            # AN EMPTY LIST IS AN ANSWER. `if mine and ...` skipped exactly
            # the members this check exists to catch: the build published
            # every stale seat for a member whose roster named no committee,
            # and this passed all fourteen of them because their `mine` was
            # empty and the guard short-circuited. A check that excuses the
            # cases the build gets wrong is how one reached a reader.
            names_ = lg.get("committees")
            if names_ is None:
                continue
            mine = {re.sub(r"\s+-\s+Division\s+[IVX]+$", "", x).strip().lower()
                    for x in names_}
            if (c.get("name") or "").strip().lower() not in mine:
                bad.append(f"{c.get('code')} {c.get('name')}: {lg.get('name')} lists "
                           + (f"{sorted(mine)}" if mine else "no committee at all"))
    assert not bad, f"{len(bad)} seats on a roster that is not today's: " + "; ".join(bad[:4])
    return "ok", f"{n:,} seats across {len(files)} committees, every one on the member's own roster"


@check("data", "the built site's chamber changers carry both chambers' votes")
def _member_links_built():
    """The code check above proves the rule; this, that the build used it.

    A districts file moved or a roster field renamed would make every link
    quietly fail rule 5, and 20 pages would go back to one chamber with the
    build exiting zero. Sen. Cindy Rosenwald's page must carry her House votes,
    and Rep. Patrick Long of Hillsborough 26 -- who shares a name with Sen. Pat
    Long, and sits at the same time -- must carry nobody's votes but his own.
    """
    site = Path("site") / "legislators"
    a, b = site / "9406.json", site / "11177.json"
    if not (a.exists() and b.exists()):
        return "skip", "site/legislators has no file for 9406 or 11177"
    r = json.loads(a.read_text(encoding="utf-8"))
    chambers = Counter((str(v.get("k", "")).split("-") + ["", ""])[1] for v in r.get("votes") or [])
    assert chambers.get("H") and chambers.get("S") and (r.get("member_ids") or [""])[0] == "9406", (
        f"Sen. Cindy Rosenwald's page has {dict(chambers)} votes and member_ids "
        f"{r.get('member_ids')}: the site was built without member_links, or before it")
    o = json.loads(b.read_text(encoding="utf-8"))
    assert "member_ids" not in o and all("-H-" in str(v.get("k")) for v in o.get("votes") or []), (
        "Rep. Patrick Long (Hills 26) carries another number's votes")
    n = 0
    for p in site.glob("*.json"):
        with open(p, encoding="utf-8", errors="replace") as fh:
            n += '"member_ids"' in fh.read(20000)
    # And the Sponsored tabs: every 2023-2024 sponsor record carries an employee
    # number or no id, so a site built before bill_sponsor_list filed by the
    # member the page links lists no 2023-2024 sponsorship for anybody.
    terms = Counter(x.get("term") for x in r.get("sponsored") or [])
    assert terms.get("2023-2024"), (
        f"Sen. Cindy Rosenwald's Sponsored tabs list {dict(terms)}: none of 2023-2024, so the "
        "site was built filing sponsorships under the record's own id")
    return "ok", (f"Rosenwald's page holds {chambers['H']:,} House and {chambers['S']:,} Senate "
                  f"votes and {terms['2023-2024']} sponsorships of 2023-2024; {n} member pages "
                  "join two numbers")


def _map_totals_against(site):
    """("ok"|"skip", what was found) for `site`, a built site's folder: the
    totals map.js draws under the map's legend from its district_map.json,
    against home.json's composition, which the Legislators tab draws as "Who
    holds the seats" (build_pages.static_bar). Raises where they differ."""
    dm, home = site / "district_map.json", site / "home.json"
    if not (dm.is_file() and home.is_file()):
        return "skip", f"{dm.as_posix()} and {home.as_posix()} are not both here"
    comp = json.loads(home.read_text(encoding="utf-8")).get("composition") or {}
    assert comp.get("H") and comp.get("S"), "home.json carries no composition for the two chambers"
    got = _map_totals_run({"night": json.loads(dm.read_text(encoding="utf-8"))})
    if got is None:
        return "skip", "node is not installed"
    bad, said = [], []
    for ch, lk in (("H", "base"), ("S", "senate")):
        t, c = got["night"]["totals"][lk], comp[ch]
        tab = {"seats": c["seats"], "held": c["sitting"], "vacant": c["vacant"],
               "parties": {p["code"]: p["n"] for p in c["parties"]}}
        if not t or {**t, "parties": dict(t["parties"])} != tab:
            bad.append(f"{c['chamber']}: the map counts {t}, the Legislators tab draws {tab}")
        said.append(_map_totals_text(got["night"]["lines"][lk]))
    assert not bad, ("the map's statewide line and \"Who holds the seats\" disagree: "
                     + "; ".join(bad))
    return "ok", "; ".join(said)


@check("data", "the district map's statewide line for the State House and the State Senate is "
               "the night's \"Who holds the seats\", seat for seat and party for party")
def _map_totals_published():
    """The owner's ask of 7 November 2026, held on the night's own files: the
    map counts each chamber from site/district_map.json's sitting members
    (map.js, totals), the Legislators tab from site/legislators.json through
    home.json's composition (build_site_v2.build_composition), two roads
    from one roster. They must say the same seats, the same members by party
    and the same vacant seats; a member the map places in no district of its
    own -- a county it has no code for -- shows here as a difference."""
    return _map_totals_against(Path("site"))


@check("data", "every bill of the session whose Legislation row sets a flag carries its "
               "suffix in data/bills.json")
def _session_designations_built():
    """The built record against the view (the audit of 7 October 2026, cause
    13): no bill of the current term whose row in db/Legislation.psv sets the
    appropriation, fiscal-note or local flag is left with the bare number."""
    bp, lp = Path("data/bills.json"), Path("db/Legislation.psv")
    if not (bp.exists() and lp.exists()):
        return "skip", "data/bills.json or db/Legislation.psv is not here"
    built = json.loads(bp.read_text(encoding="utf-8"))
    cur = built.get(max(built)) or {}
    want, bare = 0, []
    yes = lambda v: v.strip().lower() in ("1", "true")
    with open(lp, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\r\n").split("|")
            if len(f) < 27:
                continue
            r = cur.get(f[14].strip().upper())
            if not r or str(r.get("lsr_year")) != f[2].strip() or \
                    str(r.get("lsr_num") or "").lstrip("0") != f[3].strip().lstrip("0"):
                continue
            if any(yes(x) for x in f[8:11]):
                want += 1
                if "-" not in (r.get("designation") or ""):
                    bare.append(f[14].strip())
    assert not bare, (f"{len(bare)} bills whose Legislation row sets a flag show the bare "
                      f"number in data/bills.json, e.g. {bare[:6]}: rebuild data/ "
                      "(build_data.py)")
    return "ok", f"all {want:,} flagged bills of the session's view carry their suffix"


@check("data", "a committee's meetings on the built site say what happened to each bill, "
               "and a vote is placed only at a meeting the docket dates it to")
def _meeting_outcomes_on_the_site():
    """The built committee records (committee_acts by way of
    build_committees). House Housing's real meetings: on 17 February 2026
    HB 1681 was heard, 7 signing in for it and 6 against (testimony_db.json's
    count for that hearing), and voted on 3 March, 17-0, Ought to Pass with
    Amendment 2026-0998h; HB 1652-FN was recommended for interim study,
    12-0. And over every committee: each meeting's outcomes name the bills
    its items do, once each; a vote is given only at the meeting the docket
    dates it to, and never a Senate report's (dated by its sitting); a Bills
    tab act placed at a meeting is at one of the committee's meetings on
    that bill."""
    folder = Path("site/committee")
    if not (folder / "H64.json").exists():
        return "skip", "site/committee is not built"
    bad, n_meet, n_out, n_voted = [], 0, 0, 0
    for f in sorted(folder.glob("*.json")):
        c = json.loads(f.read_text(encoding="utf-8"))
        met = {(s.get("date"), it.get("bill")) for s in c.get("sessions") or []
               for it in s.get("items") or []}
        for s in c.get("sessions") or []:
            n_meet += 1
            outs = s.get("outcomes")
            if outs is None:
                bad.append(f"{f.stem} {s.get('date')}: no outcomes")
                continue
            items = list(dict.fromkeys(it.get("bill") for it in s.get("items") or []))
            if [o.get("bill") for o in outs] != items:
                bad.append(f"{f.stem} {s.get('date')}: outcomes for {[o.get('bill') for o in outs]}"
                           f", items {items}")
            for o in outs:
                n_out += 1
                if o.get("outcome") not in ("voted", "heard", "no vote", "worked", "scheduled"):
                    bad.append(f"{f.stem} {s.get('date')} {o.get('bill')}: {o.get('outcome')!r}")
                for v in o.get("votes") or []:
                    n_voted += 1
                    if v.get("meeting") != s.get("date") or v.get("dated") == "sitting":
                        bad.append(f"{f.stem} {s.get('date')} {o.get('bill')}: a vote of "
                                   f"{v.get('date')} ({v.get('dated')}) placed here")
        for rows in (c.get("bills") or {}).values():
            for r in rows:
                for a in r.get("reported") or []:
                    if a.get("meeting") and (a["meeting"], r.get("id")) not in met:
                        bad.append(f"{f.stem}: {r.get('id')}'s {a.get('act')} placed at "
                                   f"{a['meeting']}, no meeting of the committee on it")
    h64 = {s["date"]: {o["bill"]: o for o in s.get("outcomes") or []}
           for s in json.loads((folder / "H64.json").read_text(encoding="utf-8"))["sessions"]}
    o = (h64.get("2026-02-17") or {}).get("HB1681") or {}
    if (o.get("outcome"), o.get("signins"), (o.get("voted") or {}).get("meeting")) != (
            "heard", {"for": 7, "against": 6, "neutral": 0, "total": 13}, "2026-03-03"):
        bad.append(f"HB 1681 at House Housing on 17 Feb 2026: {o}")
    o = (h64.get("2026-02-17") or {}).get("HB1652") or {}
    v = (o.get("votes") or [{}])[0]
    if (o.get("outcome"), v.get("code"), v.get("yeas"), v.get("nays")) != ("voted", "IS", 12, 0):
        bad.append(f"HB 1652-FN at House Housing on 17 Feb 2026: {o}")
    o = (h64.get("2026-03-03") or {}).get("HB1681") or {}
    v = (o.get("votes") or [{}])[0]
    if (v.get("code"), v.get("amendment"), v.get("yeas"), v.get("nays")) != (
            "OTPA", "2026-0998h", 17, 0):
        bad.append(f"HB 1681 at House Housing on 3 Mar 2026: {o}")
    assert not bad, f"{len(bad)} wrong: " + "; ".join(bad[:6])
    return "ok", (f"{n_out:,} bills at {n_meet:,} meetings, {n_voted:,} votes each at the meeting "
                  "the docket dates it to; HB 1681 heard 17 Feb 2026 (7 for, 6 against)")


@check("data", "a member's file gives each term's bills filed and passed and attendance, "
               "as the member's own sponsorships and attendance say")
def _member_figures_on_the_site():
    """legislators/<id>.json's term_figures (member_figures.term_figures),
    held to the same file's sponsorships and attendance, for every member,
    and to the record for one: Speaker Packard's 2025-2026 -- 17 bills (4 as
    prime sponsor; the database's Sponsors table names the same 17), 5
    passed (HB 10, HB 1000, HB 1774 and SB 562 became law, chapters 74, 3,
    242 and 265; HR 42 adopted by the House), 33 session days with 28
    attended and 591 roll calls with 338 recorded (42 yeas, 9 nays and 287
    presiding in RollCallHistory.txt and RollCallHistory_2025.txt)."""
    folder = Path("site/legislators")
    if not (folder / "425.json").exists():
        return "skip", "site/legislators is not built"
    bad, n = [], 0
    for f in sorted(folder.glob("*.json")):
        m = json.loads(f.read_text(encoding="utf-8"))
        tf = m.get("term_figures")
        if tf is None:
            bad.append(f"{f.stem}: no term_figures")
            continue
        n += 1
        for t, a in (m.get("attendance") or {}).items():
            x = tf.get(t) or {}
            if (x.get("session_days"), x.get("days_attended"), x.get("roll_calls")) != (
                    a.get("days"), a.get("attended"), a.get("roll_calls")):
                bad.append(f"{f.stem} {t}: {x} beside {a}")
        for t, x in tf.items():
            mine = {s["bill"] for s in m.get("sponsored") or [] if s.get("term") == t}
            if x.get("bills_filed") != len(mine) or \
                    x.get("prime") + x.get("cosponsored") != x.get("bills_filed"):
                bad.append(f"{f.stem} {t}: {x.get('bills_filed')} filed, {len(mine)} sponsored")
    p = json.loads((folder / "425.json").read_text(encoding="utf-8"))
    want = {"bills_filed": 17, "bills_passed": 5, "became_law": 4, "adopted": 1, "ratified": 0,
            "prime": 4, "prime_passed": 2, "cosponsored": 13, "cosponsored_passed": 3,
            "session_days": 33, "days_attended": 28, "roll_calls": 591,
            "roll_calls_recorded": 338}
    got = (p.get("term_figures") or {}).get("2025-2026")
    if got != want:
        bad.append(f"Speaker Packard's 2025-2026: {got}")
    assert not bad, f"{len(bad)} wrong: " + "; ".join(bad[:6])
    return "ok", (f"{n:,} members' term figures agree with their sponsorships and attendance; "
                  "Speaker Packard 2025-2026: 17 filed, 5 passed, 28 of 33 days, 338 of 591 "
                  "roll calls")
