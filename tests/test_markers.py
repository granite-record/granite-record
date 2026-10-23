#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-05.24
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
    ("The Senate will be attended to the clerk. >> Thank you, Mr. President. House Bill 510 "
     "establishing a commission to study due process", "'attentive' captioned 'attended' "
     "(0LydHiwxZX0 0:24:49)"),
    ("committee on Election law Municipal Affairs to wish was referred C Bill 219 FN",
     "the clerk's reading, 'which' captioned 'wish' (5a1rrU9MYcU 1:17:30)"),
    ("committee on election art to referred to House Bill 481, an act relative to "
     "moving the state primary date", "the clerk's reading, words lost (5NhVPeBehr8 1:02:18)"),
    ("Committee on Health, Human Services and elderly affairs to which are referred to "
     "House Bill 1734, FN", "the clerk's reading, 'are referred' (b9vTd1d8PuI 9:56:55)"),
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
    # A number between that is no scheduled bill does not stop it.
    ("house bill 1088 relative to employment protection for kobe 19 in the workplace "
     "representative um uh huff you're recognized for a motion", "HB1088",
     "NbX26UHaEc0 2:11:24"),
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
    ("beginning in fiscal year 202 26 thank you madam president thank you Senator "
     "Pearl the motion is to refer SB 202", "SB202", [], "5a1rrU9MYcU 4:57:08"),
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
    ("Voting stations are open for 30 seconds. >> [music] >> Well, members president "
     "had an opportunity to vote. House will attend to the state of the vote. With 188 "
     "voting in the affirmative and 166 voting in the negative, House Bill 1607 is laid "
     "on the", "HB1607", [], "EXjvgzYBkb8 4:32:39"),
    # Somebody's history, not the chair taking the bill up (23 October 2026).
    ("senator I just uh sent her an email a friend of mine and she introduced me to "
     "Representative Keith Ammon so um he told me about Bill 302 and that's how I came "
     "come to know it", "HB302", [], "9ccqlbN4A1E 1:32:25"),
    ("For the past several years, I have introduced legislation to prohibit sanctuary "
     "cities in New Hampshire. By agreeing to House amendment on SB62, we will finally "
     "complete this journey.", "SB62", [], "9OkjR4DvQto 1:07:15"),
    # A close of a bill by its number cancels the opening it sits in.
    ("So we'll open on 111 what's that oh have we officially closed 111 yeah i'm sorry i "
     "was about to thank you though zen doily great okay sp 111 is closed 154 moving on",
     "SB111", ["SB154"], "V4ktDpuwgDM 1:35:01"),
    # A weak phrase whose bill comes before it, with another bill between.
    ("HB 704 FNA and open the public hearing on 743 FN and recognize the prime sponsor",
     "HB704", ["HB743"], "f0HyxRD3fCA 1:15:12"),
]
# Floor: the clerk's list of second referrals is not a debate opening.
NOT_FLOOR_OPENINGS = [
    ("committee on criminal justice and public safety, SP 145 FN is referred to the "
     "committee on finance. From the committee on housing, SP 173 is referred to the "
     "committee on ways and means.", "SB173", ["SB145"], "8gFNudlxXDo 0:35:41"),
]
# And spoken openings of the same shapes, which those guards must leave alone.
STILL_OPENINGS = [
    ("beginning with Senate Bill 400 um representative mlan thank you Mr chair",
     "SB400", "GdUz9CRluqE 2:08:30"),
    ("open the meeting on HP 10:21. It is 9:33 in the morning. I recognize the "
     "prime sponsor, Representative David Walker.", "HB1021", "YrSXjhMWh-8 0:39:08"),
    ("will open we'll close the hearing on house bill 89 and open the hearing on "
     "house bill 163 and recognize the sponsor", "HB163", "BIpJk7K-k34 0:16:32"),
    # Real openings the first version of the guards dropped, read on every
    # recording on 17 October 2026; the guards were narrowed to keep them.
    ("will open it up to discussion if people have a different take on this but "
     "my impression on 396 is that", "HB396", "9yzcPQyUVbE 1:09:55"),
    ("open up for discussion purposes for the HB 443 so let's turn to that bill",
     "HB443", "0Y2d_XDakUY 0:06:33"),
    ("Now open up for motion on 1148 which is relative to the fishing Game Commission",
     "HB1148", "BiiKMa_5KIg 0:14:26"),
    ("beginning here it's HB 497 I hope everybody has that in front of them",
     "HB497", "byME6vPFS3U 0:08:20"),
    ("beginning of house bill 2 and go through the sections each of you have a packet",
     "HB2", "z0XsJZl7JDw 0:00:38"),
    ("opening a closed session on HB 2026 to improve the state's transportation "
     "infrastructure", "HB2026", "ClkTYzvmn84 0:08:08"),
    # A close of the item being opened does not cancel it (after review).
    ("introduce the bill we'd introduce it and close it so we had our hearing so what "
     "we'll do right now I'll welcome representative cordelli to our our hearing today "
     "on 147.", "HB147", "c2VFUD5sfM0 0:51:00"),
    ("quickly just open it up and close it it used to be if a person didn't show up "
     "for today it's HB 1534", "HB1534", "Hcd1VaWItFE 5:22:21"),
]


def run():
    fails = []

    for text, bill, others, where in NOT_OPENINGS:
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        got = [m for m in S.find_markers(w, [bill] + others, {}) if m["bill"] == bill
               and m["kind"] == "open"]
        if got:
            fails.append(f"OPENED  ({where}): {text[:60]}")
    # A guard's words that are the bill's own title do not count against it
    # (after review): HB 771 is "relative to funding for open enrollment
    # schools", spoken so on YnRjE5qQj3w at 0:38:56.
    w = [(i * 0.4, x) for i, x in enumerate(
        "relative to funding for open enrollment schools? Representative Lad moves we "
        "concur. Chair recognizes Representative Crein to speak against the motion. Thank "
        "you, Mr. Speaker. HB771 would require".split())]
    t771 = {"HB771": "relative to funding for open enrollment schools."}
    if not [m for m in S.find_markers(w, ["HB771"], t771) if m["kind"] == "open"]:
        fails.append("'open enrollment' in HB 771's own title (YnRjE5qQj3w 0:38:56) was guarded")
    if S.find_markers(w, ["HB771"], {}):
        fails.append("'open enrollment' with no title to go on was not guarded")
    for text, bill, others, where in NOT_FLOOR_OPENINGS:
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        if S.find_markers(w, [bill] + others, {}, floor=True):
            fails.append(f"OPENED ON THE FLOOR ({where}): {text[:60]}")
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
    # Not after a witness's own testimony (hIbS7l-s6QY 4:02:46), and not a
    # title read beyond half a minute of the phrase: maO9FgPtnGY's chair
    # announced the afternoon at 4:10:14 and opened HB 1819 at 4:18:22, both
    # spoken as below, with the recess between them.
    t6 = {"HB1632": "relative to out-of-state solid waste."}
    w6 = [(i * 0.4, x) for i, x in enumerate(
        "so let me start my testimony with a little bit of a story so round about 38 "
        "years ago there was a decision in the state of New Hampshire to privatize "
        "Solid Waste and we have a disproportionate amount of out of state waste".split())]
    if S.find_markers(w6, list(t6), t6):
        fails.append("a witness's 'start my testimony' was placed by the bill's title")
    # Nor where "you" start it (r9q9bnsslqs 0:30:14, spoken; after review).
    t6b = {"SB314": "relative to pre-trial competency evaluations."}
    w6b = [(i * 0.4, x) for i, x in enumerate(
        "might think when you start hearing the word competency evaluations it's very "
        "common for people to think you're talking about serious crimes".split())]
    if S.find_markers(w6b, list(t6b), t6b):
        fails.append("a witness's 'when you start hearing' was placed by the bill's title")
    t7 = {"HB1819": "relative to review of education freedom account service providers."}
    w7 = ([(15014.0 + i * 0.4, x) for i, x in enumerate(
        "And we will start up again with another hearing at 2:15. >> [laughter]".split())]
          + [(15502.0 + i * 0.4, x) for i, x in enumerate(
              "we'll open the hearing on House Bill 18/19FN relative to review of education "
              "freedom account service providers".split())])
    got = [m["t"] for m in S.find_markers(w7, list(t7), t7)]
    if got != [15502.0]:
        fails.append(f"a title read after the recess placed the announcement: {got}")
    # The clerk's reading is the opening however long the room takes
    # (uVvh7EfGSTg 7:48:15, spoken so, the title 35 seconds on).
    t8 = {"HB475": "relative to reductions from the default budget for official ballot "
                   "town meetings"}
    w8 = ([(28096.0 + i * 0.3, x) for i, x in enumerate(
        "majority of the committee on the municipal and County government to which "
        "was referred house bill when it quiets down I'll".split())]
          + [(28133.0 + i * 0.4, x) for i, x in enumerate(
              "continue act relative to the reductions from the default budget for official "
              "ballot Town meetings".split())])
    if [m["t"] for m in S.find_markers(w8, list(t8), t8, floor=True)] != [28096.0]:
        fails.append("the clerk's reading interrupted before its title was not placed")

    # Two bills opened in one breath share the moment; a correction is not a
    # block; opened and recessed is not a span, and coming out of a recess is
    # not a recess (17 October 2026). Each spoken, at the recording and time
    # beside it.
    def opens(text, cands, at=0.0):
        w = [(at + i * 0.4, x) for i, x in enumerate(text.split())]
        return {m["bill"]: m for m in S.find_markers(w, cands, {}) if m["kind"] == "open"}
    got = opens("will start the day today with a work session on HB 56 and HB 253 let's "
                "start this morning with the Pledge of Allegiance", ["HB56", "HB253"])
    if sorted(got) != ["HB253", "HB56"] or got["HB56"]["t"] != got["HB253"]["t"]:
        fails.append(f"a block opening (-iWFQuQeru0 0:06:39) gave {got}")
    got = opens("open the executive session on House Bill 1097 and recognize I think you "
                "wrote 1197 representative", ["HB1097", "HB1197"])
    if "HB1197" in got:
        fails.append("a correction (-eGkacU96-Q 1:48:14) was read as a block")
    for text, where in (
            ("going to open up the public hearing on HB1357 and recess the public "
             "hearing on HB1357 till February 3rd at 3:15. Thank you.", "IQ2_t0-5Y9w 0:01:36"),
            ("open and recess the uh hearing for HCR16. uh the prime sponsor was not here",
             "HpDeBZsI2wU 2:41:53")):
        bill = "HB1357" if "1357" in text else "HCR16"
        w = ([(i * 0.4, x) for i, x in enumerate(text.split())]
             + [(900 + i * 0.4, x) for i, x in enumerate(
                 f"we have more on {bill} later I'll open the hearing on House Bill 1442".split())])
        segs = S.to_segments(S.find_markers(w, [bill, "HB1442"], {}), [bill, "HB1442"])
        S.fill_ends(segs, S.last_mentions(w, [bill, "HB1442"]), [])
        first = (segs.get(bill) or [{}])[0]
        if not first.get("recessed") or first.get("end") is not None:
            fails.append(f"opened and recessed ({where}) became a span: {first}")
    got = opens("opening and coming out of recess for House Bill 1241. And then I will call "
                "on Representative", ["HB1241"])
    if not got or got["HB1241"].get("recessed"):
        fails.append(f"coming out of a recess (T5AtXiL_VVc 0:33:02) read as one: {got}")
    # A close does not attach to an opening that was recessed: on a9iqYhIVaA8
    # the chair said the first sentence at 3:00:15 and the second at 5:22:27,
    # a sitting between them whose own opening was not caught.
    w10 = ([(10815.0 + i * 0.4, x) for i, x in enumerate(
        "will open the hearing on HB 289 and then recess it until one o'clock so that "
        "people that are here for that".split())]
           + [(19347.0 + i * 0.4, x) for i, x in enumerate(
               "going to close the hearing on that and I would like to um I had recessed the "
               "hearing earlier on HB 289".split())])
    segs = S.to_segments(S.find_markers(w10, ["HB289"], {}), ["HB289"])
    first = (segs.get("HB289") or [{}])[0]
    if not first.get("recessed") or first.get("end") is not None:
        fails.append(f"a close attached to an opening that was recessed (a9iqYhIVaA8): {first}")
    # Coming back is not a recess (RESUMING): G5a_5cNnorE at 1:38:27, spoken.
    got = opens("opened at ten o'clock and then recess we will now come out of recess on hb "
                "487 and i will recommend recognize the sponsor of the bill", ["HB487"])
    if not got or got["HB487"].get("recessed"):
        fails.append(f"coming out of a recess (G5a_5cNnorE 1:38:27) read as one: {got}")
    # The title stands for a bill only after an opening that names a
    # proceeding (TITLED). Spoken, and placed by title before that rule:
    for text, bill, title, where in (
            ("opens a door to listing you know a myriad of other conditions because there's "
             "really two categories of Health there's physical health and mental health and "
             "everything falls under one of those", "SB151",
             "relative to mental health education.", "NHUzbncPxRU 3:40:16"),
            ("a way of opening this conversation and trying to find a way to fund the "
             "university system and the community college system in a way that makes sense, "
             "that helps to retain uh our youngest and brightest students here in New "
             "Hampshire.", "SB604", "making an appropriation to the university system of New "
             "Hampshire.", "rnZQ363ufk4 0:17:08")):
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        if S.find_markers(w, [bill], {bill: title}):
            fails.append(f"a title placed {bill} after an opening naming no proceeding ({where})")
    # Narrowed after reading what it gave on every recording, spoken as here.
    got = opens("turn to public hearings for two more bills HB 759 and HB 760 so we'll begin "
                "the activity of the afternoon", ["HB759", "HB760"])
    if "HB760" in got:
        fails.append("the day described (tGTxrTv7BA4 4:11:25) was read as a block")
    for text, cands, bill, want, where in (
            ("open this hearing at one o'clock on recess till 1 30. open the hearing on "
             "House Bill 49 FNA call on the prime sponsor", ["HB49"], "HB49", False,
             "V6IY6c_XJwk 3:32:17"),
            ("now open the reopen the public hearing on House Bill 567 FN and because we "
             "recessed this public hearing last year or last week", ["HB567"], "HB567",
             False, "xAFePV5Jckw 0:06:10"),
            ("I'll open the committee on committee of conference on HB1 and HB2 and "
             "announce that we are in a break.", ["HB1", "HB2"], "HB1", True,
             "1SIDO6pM17w 0:04:55")):
        got = opens(text, cands)
        if bill not in got or bool(got[bill].get("recessed")) != want:
            fails.append(f"recessed ({where}): {got.get(bill)}, wanted {want}")
    t9 = {"HB1507": "requiring schools to provide a minimum amount of time for recess "
                    "per day."}
    w9 = [(i * 0.4, x) for i, x in enumerate(
        "will open the executive session on HB1507 requiring schools to provide a minimum "
        "amount of time for recess per day. And I recognize".split())]
    got = [m for m in S.find_markers(w9, list(t9), t9) if m["kind"] == "open"]
    if not got or got[0].get("recessed"):
        fails.append(f"a title that speaks of recess (9FFIBlZjGXU 1:50:15) was read as one: {got}")

    # A bill named only as it was opened gives its end nothing to go on (17
    # October 2026). Last named 10 s after its opening, it ends at the first
    # close naming no bill before the next boundary, else the last vote
    # result, else nowhere; a bill named again later keeps last mention + 60.
    def ends(last, evidence, named=(), what=""):
        byb = {"HB1118": [{"start": 100.0, "end": None, "what": what}],
               "HB1119": [{"start": 600.0, "end": None}]}
        S.fill_ends(byb, {"HB1118": last, "HB1119": 610.0}, evidence, list(named))
        s = byb["HB1118"][0]
        return s.get("end"), s.get("end_from")
    # What end_evidence counts as a vote, read in the ends it made: spoken.
    for text, want, where in (
            ("chairman Lynn yes motion passes 19 to1 um uh consent", True, "a5nhRJLyv0M 4:38:09"),
            ("yes Mr chairman the vote is 19-6 in favor of the motion okay that's adopted",
             True, "lXP6sTGwRJw 2:22:19"),
            ("via alleged search violations it failed miserably not only did it fail",
             False, "-JbQ-7NpeNg 2:48:31"),
            ("1633 and in 6 639 that passed the house last year it did not allow",
             False, "M9yjz-9dtw4 4:48:10"),
            ("Okay, we are now moving on to the regular calendar. the first bill um we "
             "will take up", False, "XJsE-D96t2w 0:21:51")):
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        got = any(k == "vote result" for _t, k in S.end_evidence(w, ["HB5"]))
        if got != want:
            fails.append(f"end_evidence ({where}) read a vote: {got}, wanted {want}")
    votes = [(300.0, "vote result"), (400.0, "vote result"), (700.0, "vote result")]
    # The first vote, not the last; nothing past another scheduled bill
    # named; no vote at all on a hearing (after review, 17 October 2026).
    for got, want, why in (
            (ends(110.0, votes), (300.0, "vote result"), "the first vote after the opening"),
            (ends(110.0, votes + [(250.0, "unnamed close")]), (250.0, "unnamed close"),
             "a close naming no bill"),
            (ends(110.0, votes, [(102.0, "HB1118"), (104.0, "HB1120"), (280.0, "HB1120")]),
             (None, None), "another scheduled bill named before any vote"),
            (ends(110.0, votes + [(450.0, "unnamed close")], [(420.0, "HB1120")]),
             (300.0, "vote result"), "a close past another bill named is that bill's"),
            (ends(110.0, votes, (), "public hearing"), (None, None), "a vote ending a hearing"),
            (ends(110.0, votes + [(350.0, "unnamed close")], (), "hearing"),
             (350.0, "unnamed close"), "a hearing's close"),
            (ends(110.0, []), (None, None), "nothing to end it on"),
            (ends(300.0, votes), (360.0, "last mention of the bill"), "named again later")):
        if got != want:
            fails.append(f"fill_ends, {why}: {got}, wanted {want}")

    # "HB1 1282" is HB 1282 and "HB 1116" is HB 116 where only those are
    # scheduled (23 October 2026). Spoken, IuZ30vZcQlc at 5:20:29: the close
    # of HB 1282 went to HB 1275, the next bill in the window.
    w = [(i * 0.4, x) for i, x in enumerate(
        "going to close out the hearing for HB1 1282 and open up the hearing for HB1275 "
        "relative to the effects of per and poly floral substances on agriculture.".split())]
    got = [(m["kind"], m["bill"]) for m in S.find_markers(w, ["HB1282", "HB1275"], {})]
    if ("close", "HB1282") not in got or ("close", "HB1275") in got:
        fails.append(f"the close of 'HB1 1282' (IuZ30vZcQlc 5:20:29) gave {got}")
    # EyOi37y9mNU at 5:14:46, spoken: HB 116 read as "HB 1116".
    w = [(i * 0.4, x) for i, x in enumerate(
        "I think it's uh about time for our next um hearing um which is on uh HB 1116 um "
        "relative to reporting requirements for publicy and um we welcome the".split())]
    if [m["bill"] for m in S.find_markers(w, ["HB116", "HB184"], {})] != ["HB116"]:
        fails.append("'HB 1116' for HB 116 (EyOi37y9mNU 5:14:46) was not read")
    if S.find_markers(w, ["HB1116", "HB116"], {})[0]["bill"] != "HB1116":
        fails.append("'HB 1116' was taken for HB 116 where HB 1116 is scheduled")
    # A plural names the proceeding too (-h65KB-w-4E 2:51:20, spoken).
    w = [(i * 0.4, x) for i, x in enumerate(
        "okay I am going to open up our exec sessions this afternoon um sorry we're late "
        "we're running late on this um we will start with HB 424 directing the".split())]
    got = [m["what"] for m in S.find_markers(w, ["HB424"], {}) if m["kind"] == "open"]
    if got[:1] != ["exec session"]:
        fails.append(f"'our exec sessions' (-h65KB-w-4E 2:51:20) was labelled {got}")

    # The bill read with its title and then moved is the executive session
    # (READ_MOTION, 23 October 2026). Each spoken so, with the title the
    # record gives the bill in that recording's term.
    for text, bill, title, want, where in (
            ("okay and it has a fiscal note so it'll go to finance or one of those places um "
             "the next one hb1 174 increasing the maximum weight of a utility terrain vehicle "
             "to 3500 lb unladen dry weight representative Davis do you have a motion thank you "
             "Mr chair I I would make a motion not to pass", "HB174",
             "increasing the maximum weight of a utility terrain vehicle to 3,500 pounds "
             "unladen dry weight.", True, "C6YkO_S7nmg 0:15:50"),
            ("yes 20 years consent thank you okay the next bill we have is SB 215 this bill is "
             "relative to nursing certification requirements I Look to represent McDonald to "
             "make a motion thank you and I move ought to pass is there a second", "SB215",
             "relative to nursing certification requirements.", True, "H_oSDFVHpgw 1:49:50"),
            ("okay moving on uh HB 334 FN HB 334 FN relative to the comprehensive State "
             "development plan believe I have a motion from representative D I make a motion to "
             "itl representative Davis I'll second", "HB334",
             "relative to the comprehensive state development plan.", True,
             "C6YkO_S7nmg 0:34:35"),
            # The motion's own words name the bill: not the opening.
            ("I am moving opop pass on HB 1362 um relative to authorizing municipalities to "
             "stabilize rent increases in rental housing um so this is enabling legislation um "
             "as we heard from the municipal Association um it just gives the municipality",
             "HB1362", "relative to authorizing municipalities to stabilize rent increases in "
             "rental housing.", False, "o5qhR8Nft4o 0:23:50"),
            # The question put, near the end of the item.
            ("the motion before us on house bill 1619 fn relative to qualifying conditions for "
             "the therapeutic cannabis program the motion before us is itl moved by "
             "representative merchant seconded by representative delemus would the clerk "
             "please call the roll", "HB1619",
             "relative to qualifying conditions for the therapeutic cannabis program.", False,
             "isY9DRIEy2s 6:22:17")):
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        got = [m for m in S.find_markers(w, [bill], {bill: title}) if m["kind"] == "open"]
        ok = bool(got) and got[0]["what"] == "executive session" and "weak" in got[0]["how"]
        if ok != want:
            fails.append(f"read with its title and moved ({where}): {got}, wanted {want}")
        if want and S.find_markers(w, [bill], {}):
            fails.append(f"read with its title ({where}) was placed with no title to go on")
        if want and S.find_markers(w, [bill], {bill: title}, floor=True):
            fails.append(f"read with its title ({where}) was placed on the floor")

    # And read with its title, then its sponsor welcomed: weak, and naming no
    # proceeding (READ_SPONSOR). Spoken, delPtmOeKmc at 3:05:40.
    w = [(i * 0.4, x) for i, x in enumerate(
        "all right um all right I'm going to uh call the uh Judiciary Committee back to order "
        "and uh commence the hearing on uh HB 88 uh FN uh relative to establishing community "
        "property trusts and I will recognize uh the prime sponsor representative Dan "
        "McGuire thank you Mr chairman".split())]
    t88 = {"HB88": "establishing community property trusts."}
    got = [m for m in S.find_markers(w, ["HB88"], t88) if m["kind"] == "open"]
    if not got or got[0]["what"] != "" or "then the sponsor" not in got[0]["how"]:
        fails.append(f"read with its title, then the sponsor (delPtmOeKmc 3:05:40): {got}")

    # The clerk reading the other chamber's message opens a concurrence on
    # the floor (FLOOR_MESSAGE_RE, 23 October 2026). Spoken, 6oCT6ls3uDk.
    for text, bill, other, where in (
            ("The eyes have it. Committee report is adopted. Chair recognizes the clerk for a "
             "message. Mr. Speaker, the Senate refuses to concur with the House in the adoption "
             "of the amendment to the following title bill sent from the House, Senate Bill "
             "625, establishing a committee to study options for family members", "SB625",
             "HB1269", "0:38:26"),
            ("Judy Aaron, Barbara Clapp Joyce, Peter Bixby, and Nick Germana to the committee. "
             "The chair recognizes the clerk. Mr. Speaker, the Senate concurs with the House in "
             "the passage of the following entitled bill with amendment, the passage of which "
             "amendment the Senate asks concurrence of the House. House Bill 1269, relative to "
             "qualifications to practice acupuncture. Representative Leon moves that we concur",
             "HB1269", "SB625", "1:28:40")):
        w = [(i * 0.4, x) for i, x in enumerate(text.split())]
        got = [(m["bill"], m["what"]) for m in S.find_markers(w, [bill, other], {}, floor=True)
               if m["kind"] == "open"]
        if got != [(bill, "floor debate")]:
            fails.append(f"the clerk's message (6oCT6ls3uDk {where}) gave {got}")
        if [m for m in S.find_markers(w, [bill, other], {}) if m["kind"] == "open"]:
            fails.append(f"the clerk's message (6oCT6ls3uDk {where}) opened a committee item")

    return fails


if __name__ == "__main__":
    bad = run()
    n = (len(MUST_MATCH) + len(MUST_NOT_MATCH) + len(NOT_OPENINGS) + len(NOT_FLOOR_OPENINGS)
         + len(STILL_OPENINGS)
         + len(BILL_BEFORE) + 10)
    if bad:
        print(f"{len(bad)} of {n} failed:")
        for b in bad:
            print("  " + b)
        sys.exit(1)
    print(f"{n} marker cases pass "
          f"({len(MUST_MATCH)} spoken phrasings, {len(MUST_NOT_MATCH)} decoys, "
          f"{len(NOT_OPENINGS) + len(NOT_FLOOR_OPENINGS)} spoken non-openings, "
          f"{len(STILL_OPENINGS)} spoken "
          f"openings beside them, {len(BILL_BEFORE)} named before the phrase, 10 behaviours)")
