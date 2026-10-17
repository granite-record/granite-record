#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.12
"""
The phrasings the marker patterns must match, and the ones they must not.

    python3 tests/test_markers.py

Every case below was read out of a real transcript. They arrived over one day,
in this order: seven from the first recording read by hand; twelve more from
--gaps on recordings that came back empty; eleven from --phrases counting what
was said before every unmarked bill across eight hundred recordings; seven
floor forms from the clerk's script.

OPEN_RE went through nine revisions collecting them, and each revision was
checked against a fixture written in a shell heredoc and then thrown away. So
the evidence for why the pattern looks the way it does existed only in a
terminal scrollback. This file is that evidence, kept.

Two rules for adding to it:

  A phrase goes in MUST_MATCH only if it was actually spoken on a recording.
  Nothing invented, however plausible -- the floor patterns were validated
  against sentences typed out of a document for a whole day before anyone ran
  them on a floor caption file, and that is exactly the mistake this guards
  against.

  A phrase goes in MUST_NOT_MATCH when it looks like an opening and is not.
  Those are cheaper to find than to fix: an agenda being read out named six
  bills in one breath and produced six false openings before anyone noticed.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import segment_markers as S  # noqa: E402


# Spoken, and a boundary. (text, what it demonstrates)
MUST_MATCH = [
    # -- committee, read by hand from the first recordings --------------
    ("I am opening the hearing on House Bill 1491", "plain open"),
    ("I'll open the hearing on House Bill 1498", "contraction"),
    ("we're going to open up the public hearing for House Bill 1300", "open up ... for"),
    ("At this time, the chair will open the executive session on House Bill 1181",
     "the chair as subject"),
    ("we'll open up the um executive session. First bill I have here is HP 1080",
     "filler between article and noun"),
    ("having no other pink cards, I will close the public hearing on HB 1083", "close"),
    ("And with that, the chair will close the executive session on House Bill 1386",
     "close naming the bill"),

    # -- from --gaps on recordings that came back empty -----------------
    ("I'm now going to turn to um HP 253 relative to interest-bearing pool trust",
     "verb takes the bill directly"),
    ("we're going to do the full committee work session on House Bill 1600",
     "work session"),
    ("the next hearing is on House Bill 269", "next <noun> is on"),
    ("And we will start the public hearing on 294", "start"),
    ("open an executive session on House Bill 1384", "an, not the"),
    ("we're going to open up the house election Law Public hearing for House Bill 474",
     "committee name between article and noun"),
    ("we're going to take testimony on HB 138", "take testimony on"),

    # -- from --phrases, counted across every unmarked proceeding -------
    ("open up the exact session on House Bill 1082", "'exact' is how captions hear 'exec'"),
    ("well move on to House Bill 1082", "move on to (37 occurrences)"),
    ("the next one is House Bill 1082", "next one is (24)"),
    ("we're going to take up House Bill 1082", "take up (17)"),
    ("so we're going to hear House Bill 1082", "going to hear (20)"),
    ("we'll start with House Bill 1082", "start with (25)"),
    ("last but not least House Bill 1082", "last but not least (19)"),
    ("let's get started with HB 1082", "get started with"),
    ("okay moving right along to House Bill 1082", "moving right along"),
    ("the bill to be heard today is House Bill 1082", "to be heard today"),
    ("I'm here to introduce House Bill 1082", "the sponsor, not the chair"),
    ("our first bill is Senate Bill 435", "first bill is"),
    ("First one we'll take up is Senate Bill 481", "first one we'll take up"),

    # -- from --gaps, read on recordings where nothing fired at all -----
    #
    # Every one of these is an opening no pattern caught, and they share a
    # shape rather than a vocabulary: the verb takes the BILL directly, with
    # no proceeding noun after it. That is the case OPEN_DIRECT_RE exists for,
    # and its verb list was too short.
    ("I'll open HP 369. Representative Patenza, good to see you",
     "open, with the bill straight after"),
    ("we're going to start HB 602 requiring certain offenders to participate",
     "start, with the bill straight after"),
    ("Senator Eler is going to introduce SB 269", "introduce, by the sponsor"),
    ("from the Department of Health and Human Services as I introduce "
     "Senate Bill 264", "introduce, mid-sentence"),
    ("The next bill up on the docket is 1586 allowing the commissioner",
     "next bill up on the docket"),
    ("first up we have Senate I'm sorry, House Bill 206 and 204",
     "first up we have"),
    ("So we'll move now to HB 1398, establishing a committee to study",
     "move now to, not 'move on to'"),
    # And one the noun list missed by a single word: the chair said "session"
    # on its own, where SUBJECT knew only "executive session" and "hearing".
    ("And uh we're opening the session on House Bill 1123 requiring certain "
     "companies to post expected salary ranges", "bare 'session' as the noun"),
    ("With that, we're going to close down the hearing for this bill 1574",
     "close down, where CLOSE_RE knew close out and close up"),

    # -- a second --gaps pass, after the batch above was in -------------
    ("Send judiciary is back in session. We're doing HB 1217 an act permitting",
     "we're doing"),
    ("So what we will do is we'll begin um our meeting, our work session on "
     "SB 475", "begin"),
    ("why don't we get started? Um, we can start a discussion about HB 1096, "
     "establishing a committee", "start a discussion about"),
    ("so with that um we're on to House Bill 781 which is um requiring schools",
     "we're on to"),
    # "recess ... HB 283" PAUSES 283; the opening in this sentence is the bare
    # "open" that follows it. Recess was briefly an opening verb here and it
    # fired on "recess uh till 2:00 and please be back in your seats. Thanks.
    # House Bill 1352", putting a bill at the lunch break seven minutes before
    # it was taken up.
    ("at this point I will recess uh House Bill 283 open house bill 768 which "
     "is allowing public schools", "bare open, no pronoun before it"),
    ("let's just go let's get it right into 1174 right now", "get right into"),

    # -- the chair's politeness, which is not a hedge ---------------------
    #
    # Spoken, word for word, and every one of them IS the chair taking the
    # bill up: the sponsor starts speaking immediately after. They are here
    # because the first version of the HEDGE guard read "you could" as a
    # hypothesis and dropped about fifteen boundaries of exactly this shape
    # to fix one real false positive. The median did not move, so only a
    # boundary-by-boundary diff found it.
    ("Uh welcome. Uh if you could introduce HB1442",
     "'if you could' is a request, not a hedge (HpDeBZsI2wU 0:16:54)"),
    ("Senator Alvis, welcome again. And if you could introduce HB1442 when "
     "you're ready", "the same, with the bill by bare number (JXCR09--m6w)"),
    ("we have the prime sponsor for our next bill and you could introduce "
     "yourself and HB1442", "'and you could' (7zQ2ckW27Ks 0:02:25)"),
    ("Representative, if you could introduce HB1442 for us",
     "'if you could' again (Rmk7jA6ze74 1:05:28)"),

    # -- the floor: the clerk's script ----------------------------------
    ("Majority of the Committee on Finance to which was referred Senate Bill 408, "
     "relative to insurance coverage for prosthetics", "House, standard"),
    ("Majority Committee on Criminal Justice and Public Safety to which was "
     "referred House Bill 1010", "House, no 'of the'"),
    ("The Committee on Executive Departments and Administration, which has been "
     "referred House Bill 1020", "House, comma before which"),
    ("The committee on Commerce to which was referred House Bill 1030", "Senate"),
    ("committee on transportation to which was referred to House Bill 1078FN",
     "'referred to', as captioned"),

    # -- committee of conference, read out of work/ on 18 September ----------
    # A proceeding kind the rest of the project already knows and no pattern
    # here could find: its verbs are not in OPEN_RE and its noun is not in
    # SUBJECT. Each of these three was read back out of the caption file named
    # beside it, not copied from a summary of them.
    ("Good morning and welcome to the Committee of Conference on HB 1374",
     "welcome to -- work/7Gu9nfs5-vk"),
    ("good morning everyone I'm going to call to order a committee of "
     "conference for House Bill 458",
     "call to order, indefinite article, 'for' -- work/7sSEP3Vjn9w"),
    ("It is now 931 according to my phone so I am going to convene and call "
     "to order the committee of conference on House bill 1738",
     "two verbs before the noun -- work/DxY8IqDXajc"),

    # -- weak phrases agreeing with a stated opening 89% or more, 17 October
    # 2026, each read off the recording and time beside it ------------------
    ("next hearing which is on 527 HP 527 replacing Statewide education property tax",
     "next hearing which is (0mwuMat8uGI 4:33:27)"),
    ("call the committee of conference to order on Senate Bill 221.",
     "the noun before 'to order' (Hhj-jGwswUw 0:03:33)"),
    ("order the committee of conference on House Bill 1623 for the house we have "
     "Representatives Harrington", "order the committee (7sSEP3Vjn9w 0:32:50)"),
    ("attentive to the clerk. Senate Bill 65 FN relative to storm water management "
     "for solar arrays.", "the Senate's clerk (9Mv01Z_AsjU 0:22:48)"),
    ("committee on Election law Municipal Affairs to wish was referred C Bill 219 FN",
     "the clerk's reading, 'which' captioned 'wish' (5a1rrU9MYcU 1:17:30)"),
    ("committee on election art to referred to House Bill 481, an act relative to "
     "moving the state primary date", "the clerk's reading, words lost (5NhVPeBehr8 1:02:18)"),
]

# Spoken, the bill named BEFORE the phrase: the marker is the moment the bill
# was named. (text, bill, where.) Weak phrases of 89% and over, 17 October 2026.
BILL_BEFORE = [
    ("House Bill 184 establishing a committee to study changing school start "
     "times and I welcome the prime sponsor", "HB184", "EyOi37y9mNU 6:10:20"),
    ("House Bill 1280 I'll open the public hearing on that and recognize the "
     "prime sponsor", "HB1280", "3EjgNRn8UqA 0:03:33"),
    ("hb750 relative making incentive grants for school districts that improve "
     "in certain assessment scores I recognize represent peoples for a motion",
     "HB750", "0Y2d_XDakUY 1:08:31"),
]

# Look like openings. Are not.
MUST_NOT_MATCH = [
    ("I have no other pink cards for this hearing", "closing remark"),
    ("there was a hearing on that last year", "past reference"),
    ("the work session sheet is on the table", "a document"),
    ("we had testimony on that from the department last week", "past reference"),
    ("turn to page five of the handout", "not a bill"),
    # Testimony, not a boundary. A member of the public naming the bill they
    # came about reads exactly like a sponsor introducing it, and there are far
    # more of them.
    ("My name is Chase Poyer, and I'm here to oppose HB1442", "a witness"),
    ("I strongly support HB1442. These bills would protect", "a witness"),
    ("Oh, this is for HB1442. I'm so sorry, I read the wrong card",
     "a pink card being sorted"),
    # SPOKEN, word for word, by the chair of Science, Technology and Energy on
    # 3 April 2023 (Ud-N9egBHQI at 2:03:37), an hour behind schedule and in
    # the middle of another bill's hearing. "start the hearing on" is a real
    # opening phrase and this is not an opening: the chair opened HB1442's
    # real-world counterpart eleven minutes later, with "I'm going to open a
    # public hearing on". Marked wrong at the bench.
    ("it doesn't look like we're going to get to those bills before the lunch "
     "break, we might start the hearing on HB1442 before the lunch break, I "
     "have over a dozen pink cards for it", "a plan, not a boundary"),
    ("we may open the hearing on HB1442 after we finish this one",
     "a plan, not a boundary"),
]


# Spoken, with the bill the docket scheduled, and read on 17 October 2026 as a
# published start that was not an opening. (text, the bill it must not open,
# the other scheduled bills, where it was said.)
NOT_OPENINGS = [
    ("begin the roll call vote on house bill 1430. the motion is itl we'll start "
     "with representative abrami", "HB1430", [], "kTWMOT-FfVI 0:32:37"),
    ("beginning of house 25 that worksheet starts at the laps extension part",
     "HB25", [], "-AaP0NKGK4Q 0:08:52"),
    ("open for further discussion and amendment. Okay. Seeing none, the question "
     "is on the adoption of ought to pass as amended on Senate Bill 482",
     "SB482", [], "-IqRWnHKSlQ 1:05:11"),
    ("open to any questions that you may have and happy to help okay thank you "
     "Mr trelli any questions seeing none thank you HB 138", "HB138", [],
     "1SigcuPF4dM 1:53:59"),
    ("Open Democracy and I'm going to be testifying in opposition to SB 223.",
     "SB223", [], "4Yho2i88AZw 0:06:04"),
    ("open the door to censorship. Not now, not ever. Vote no on the amendment "
     "to SB 33.", "SB33", [], "itJRViVSJqk 6:01:13"),
    ("open meeting law and the Public's right to know Senate Bill 259 "
     "strengthens accessibility", "SB259", [], "2oN7obi1qfE 0:17:32"),
    ("going to do is close this hearing see I don't have any further pin cards "
     "on 739 and we're going to move into the last one", "HB739", [],
     "0Y2d_XDakUY 1:46:00"),
    ("will open we'll close the hearing on house bill 89 and open the hearing on "
     "house bill 163 and recognize the sponsor", "HB89", ["HB163"],
     "BIpJk7K-k34 0:16:32"),
    ("introduced and he was telling me there a that there is money in it and "
     "they're going to take $100,000 out the money that", "SB100", [],
     "5zhoZ4k_UNY 1:44:14"),
]
# And spoken openings of the same shapes, which those guards must leave alone.
STILL_OPENINGS = [
    ("beginning with Senate Bill 400 um representative mlan thank you Mr chair",
     "SB400", "GdUz9CRluqE 2:08:30"),
    ("open the meeting on HP 10:21. It is 9:33 in the morning. I recognize the "
     "prime sponsor, Representative David Walker.", "HB1021", "YrSXjhMWh-8 0:39:08"),
    ("will open we'll close the hearing on house bill 89 and open the hearing on "
     "house bill 163 and recognize the sponsor", "HB163", "BIpJk7K-k34 0:16:32"),
]


def run():
    fails = []

    for text, bill, others, where in NOT_OPENINGS:
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        got = [m for m in S.find_markers(w, [bill] + others, {}) if m["bill"] == bill
               and m["kind"] == "open"]
        if got:
            fails.append(f"OPENED  ({where}): {text[:60]}")
    for text, bill, where in STILL_OPENINGS:
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        cands = [bill, "HB89"] if bill == "HB163" else [bill]
        if not any(m["bill"] == bill and m["kind"] == "open"
                   for m in S.find_markers(w, cands, {})):
            fails.append(f"NOT OPENED ({where}): {text[:60]}")

    # The patterns find_markers actually runs, read from it rather than listed
    # again here. This list used to be a second copy, and the copies drifted
    # the first time a pattern was added: the quotes proving CONF_OPEN_RE were
    # reported as MISSED by a test whose own list did not contain it.
    for text, why in MUST_MATCH:
        hit = (any(rx.search(text) for rx, _, _ in S.COMMITTEE_PATS)
               or S.FLOOR_OPEN_RE.search(text)
               or any(rx.search(text) for rx, _, _ in S.FLOOR_WEAK_PATS))
        if not hit:
            fails.append(f"MISSED  ({why}): {text[:70]}")
    for text, bill, where in BILL_BEFORE:
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        got = [m for m in S.find_markers(w, [bill], {}) if m["bill"] == bill]
        if not got or got[0]["t"] != 0.0 or "weak" not in got[0]["how"]:
            fails.append(f"BILL BEFORE ({where}): {got}")

    # Tested through find_markers, not against the patterns alone. "turn to"
    # matches in "turn to page five of the handout", and that is fine: a phrase
    # only becomes a marker when a bill the docket scheduled that day is named
    # right after it. The bill check is the guard, so the guard is what gets
    # tested.
    for text, why in MUST_NOT_MATCH:
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        got = S.find_markers(w, ["HB1442"], {"HB1442": "relative to court records"})
        if got:
            fails.append(f"MARKED ({why}): {text[:70]}")

    # The agenda readout. A phrase followed by several bills in one breath is
    # the chair running through the day, not starting an item -- this produced
    # six false openings from one sentence.
    words = [(i * 0.4, w) for i, w in enumerate(
        "for reference these are in numerical order house bill 27 289 323 365 "
        "385 418 and we will take them in that order".split())]
    cands = ["HB27", "HB289", "HB323", "HB365", "HB385", "HB418"]
    got = S.find_markers(words, cands, {c: "" for c in cands})
    if got:
        fails.append(f"agenda readout produced {len(got)} markers, wanted 0")

    # One opening read twice, seconds apart, is one opening. Bucketing by
    # round(t/30) let 1:11:44 and 1:11:48 fall either side of a boundary.
    w2 = []
    for t0, s in ((4304.0, "going to open the noticed executive session"),
                  (4308.0, "Going to open the executive session for House Bill 1520")):
        w2 += [(t0 + i * 0.4, x) for i, x in enumerate(s.split())]
    mk = S.find_markers(w2, ["HB1520"], {"HB1520": "defining citizenship"})
    if len(mk) != 1:
        fails.append(f"one opening read twice gave {len(mk)} markers, wanted 1")

    # A match's time is the word that starts it, not the window's start. This
    # has been got wrong five times in five different functions.
    w3 = [(i * 0.4, x) for i, x in enumerate(
        "some earlier talk that runs on for a while and then finally we are "
        "going to open the public hearing on House Bill 1442".split())]
    mk = S.find_markers(w3, ["HB1442"], {"HB1442": "relative to court records"})
    if not mk:
        fails.append("no marker in the late-phrase case")
    elif mk[0]["t"] < 4.0:
        fails.append(f"marker timed at {mk[0]['t']}s -- that is the window's "
                     "start, not the phrase's")

    # The title stands for a garbled number after an opening that names a
    # proceeding (17 October 2026). Spoken, itJRViVSJqk at 5:33:24: the
    # clerk's reading of HB 564 with the number captioned "5604", placed by
    # its title alone -- which no marker had been since data/bills.json was
    # keyed by term.
    w5 = [(i * 0.4, x) for i, x in enumerate(
        "Majority of the committee on education policy and administration to "
        "which was referred House Bill 5604, an act relative to the adoption of "
        "school administrative unit budgets, considered the same".split())]
    t5 = {"HB564": "relative to the adoption of school administrative unit budgets",
          "HB56": "relative to the state forester"}
    mk = S.find_markers(w5, list(t5), t5, floor=True)
    if [(m["bill"], m["how"]) for m in mk] != [("HB564", "title")]:
        fails.append(f"the clerk's reading of HB 564 by its title gave {mk}")
    if S.find_markers(w5, list(t5), {}, floor=True):
        fails.append("a garbled number with no titles to go on was still placed")

    # A bill named only as it was opened gives its end nothing to go on (17
    # October 2026). Last named 10 s after its opening, it ends at the first
    # close naming no bill before the next boundary, else the last vote
    # result, else nowhere; a bill named again later keeps last mention + 60.
    def ends(last, evidence):
        byb = {"HB1118": [{"start": 100.0, "end": None}],
               "HB1119": [{"start": 600.0, "end": None}]}
        S.fill_ends(byb, {"HB1118": last, "HB1119": 610.0}, evidence)
        s = byb["HB1118"][0]
        return s.get("end"), s.get("end_from")
    votes = [(300.0, "vote result"), (400.0, "vote result"), (700.0, "vote result")]
    for got, want, why in (
            (ends(110.0, votes), (400.0, "vote result"), "the last vote before the next boundary"),
            (ends(110.0, votes + [(250.0, "unnamed close")]), (250.0, "unnamed close"),
             "a close naming no bill"),
            (ends(110.0, []), (None, None), "nothing to end it on"),
            (ends(300.0, votes), (360.0, "last mention of the bill"), "named again later")):
        if got != want:
            fails.append(f"fill_ends, {why}: {got}, wanted {want}")

    return fails


if __name__ == "__main__":
    bad = run()
    n = (len(MUST_MATCH) + len(MUST_NOT_MATCH) + len(NOT_OPENINGS) + len(STILL_OPENINGS)
         + len(BILL_BEFORE) + 5)
    if bad:
        print(f"{len(bad)} of {n} failed:")
        for b in bad:
            print("  " + b)
        sys.exit(1)
    print(f"{n} marker cases pass "
          f"({len(MUST_MATCH)} spoken phrasings, {len(MUST_NOT_MATCH)} decoys, "
          f"{len(NOT_OPENINGS)} spoken non-openings, {len(STILL_OPENINGS)} spoken "
          f"openings beside them, {len(BILL_BEFORE)} named before the phrase, 5 behaviours)")
