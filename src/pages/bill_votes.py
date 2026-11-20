#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A bill's roll calls, as its Votes tab draws them: a day's votes put back in
the order they happened, with the amendments named (vote_chronology, and
_paired_by_count, which pairs each roll call with its docket row by count),
every recorded vote on one bill (bill_rollcalls), the note above the table
(vote_note_for), and the card of a roll call on no bill, a term to a file
(write_nobill_cards).

    import bill_votes as BV
    BV.bill_rollcalls(bid, term, rcs, narr, votes_by_bill, legs, unnamed)
    BV.write_nobill_cards(out, rollcalls, votes_by_bill, legs, unnamed)

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited, in four
pieces in the file's order: VOTE_KIND_RE to _paired_by_count; NOBILL and
write_nobill_cards; bill_rollcalls; vote_note_for. A ballot's voter is
sponsors.py's (vote_member), an amendment's number amendments.py's, the
division thresholds rollcall_outcomes.py's and a vote's motions
vote_passage.py's. It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import json
import re
from collections import defaultdict

import rollcall_outcomes as RO
import vote_passage as VP
from amendments import AMEND_NUM, _amendment_said
from sponsors import vote_member


VOTE_KIND_RE = re.compile(r"\b(RC|VV|DV)\b")


def vote_chronology(rcs, narr):
    """Put a day's votes back in the order they happened, and name amendments.

    Two problems, one cause. The votes tab sorted by question text inside a
    date, so a tabling motion came before the vote it interrupted because "Lay"
    sorts before "Ought". And an amendment roll call is recorded as "Adopt
    Amendment" with no number, so two of them in a row are indistinguishable.

    The docket already answers both. It lists every floor action in the order
    it happened, names the amendment each one is about, and marks how each was
    decided. The roll call file numbers its votes in that same order. So the
    two are paired, in order, within a chamber and a day.

    The pairing is only used when the counts agree. If the docket shows three
    roll calls that day and the roll call file has four, something is missing
    from one of them and lining them up would put the wrong number beside the
    wrong vote -- so nothing is claimed and the votes fall back to their own
    numbering.

    AND AN AMENDMENT IS NAMED BY THE ROW WHOSE COUNT IS ITS ROLL CALL'S (the
    launch audit's recheck of 7 October 2026). The counts of a day can agree
    and its order not: HB 1711 of 2024's floor amendment 2024-1358h, "FLAM #
    2024-1358h ...: AF RC 101-252", was entered the day after the passage it
    preceded, so the docket's order put it second, and roll call 197 -- the
    passage, 204-149 -- was named as that amendment; HB 2 of 2025's 1526h and
    1560h were entered in the other order from their votes, 195-175 and
    203-167, and each roll call carried the other's number. On 38 days of 37
    bills a row so paired states a count its roll call does not have. The
    order is still the docket's sequence; the name is the row's whose count,
    and kind (an amendment or not), the roll call carries (_paired_by_count),
    and a row whose count no roll call of the day carries names nothing.

    Returns (order, names) keyed by (body, roll call number).
    """
    lines = defaultdict(list)
    for i, e in enumerate((narr or {}).get("events", [])):
        if e.get("cancelled"):
            continue
        raw = e.get("raw", "")
        vk = (e.get("vote_kind") or "").upper()
        if not vk:
            m = VOTE_KIND_RE.search(raw)
            vk = m.group(1) if m else ""
        if vk:
            lines[(e.get("date"), e.get("body"))].append((i, vk, raw))

    order, names = {}, {}
    for (date, body), evs in lines.items():
        rc_lines = [(i, raw) for i, vk, raw in evs if vk == "RC"]
        mine = sorted((r for r in rcs
                       if r.get("date") == date and r.get("body") == body),
                      key=lambda r: int(r.get("number") or 0))
        if len(rc_lines) != len(mine):
            continue
        said = _paired_by_count([raw for _i, raw in rc_lines], mine)
        for j, ((i, raw), r) in enumerate(zip(rc_lines, mine)):
            k = (r.get("body"), r.get("number"))
            order[k] = i
            row = said.get(j)
            am = AMEND_NUM.search(rc_lines[row][1]) if row is not None else None
            if am and "amendment" in (r.get("question") or "").lower():
                names[k] = am.group(1)
    return order, names


# A roll call's count as a docket row states it: "RC 171-162" (the House),
# "RC 16Y-8N" (the Senate).
RC_TALLY = re.compile(r"\bRC\s*\(?\s*(\d{1,3})\s*Y?\s*[-–]\s*(\d{1,3})\s*N?\b", re.I)
AMENDMENT_ROW = re.compile(r"\b(?:FLAM|Amendment)\b", re.I)
PASSAGE_Q = re.compile(r"^\s*(?:Ought\s+to\s+Pass|OTP)\b", re.I)


def _paired_by_count(raws, mine):
    """{position in mine: position in raws}: each roll call of a day (mine,
    in their numbering) and the docket row (raws, in the docket's order) it
    is. In order, except where a pair's counts disagree: those rows and roll
    calls are paired again by count and kind -- an amendment, a passage or
    another motion -- in order within each; one row and one roll call left
    over, of one kind, are each other (a count mistyped); any other left over
    is paired with nothing."""
    def tally(raw):
        m = RC_TALLY.search(raw or "")
        return (int(m.group(1)), int(m.group(2))) if m else None

    def kind(s, question=False):
        s = s or ""
        if PASSAGE_Q.match(s):
            return "passage"
        if ("amendment" in s.lower()) if question else AMENDMENT_ROW.search(s):
            return "amendment"
        return "other"

    def counted(r):
        try:
            return (int(r.get("yeas")), int(r.get("nays")))
        except (TypeError, ValueError):
            return None

    out = {j: j for j in range(min(len(raws), len(mine)))}
    off = [j for j in out if tally(raws[j]) and counted(mine[j])
           and tally(raws[j]) != counted(mine[j])]
    if not off:
        return out
    for j in off:
        out.pop(j)
    rows, rcs = defaultdict(list), defaultdict(list)
    for j in off:
        rows[tally(raws[j]) + (kind(raws[j]),)].append(j)
        rcs[counted(mine[j]) + (kind(mine[j].get("question"), True),)].append(j)
    for key, idx in rows.items():
        if len(rcs.get(key, ())) == len(idx):
            out.update(zip(rcs[key], idx))
    left_rows = [j for j in off if j not in out.values()]
    left_rcs = [j for j in off if j not in out]
    if (len(left_rows) == len(left_rcs) == 1
            and kind(raws[left_rows[0]]) == kind(mine[left_rcs[0]].get("question"), True)):
        out[left_rcs[0]] = left_rows[0]
    return out


# EVERY ROLL CALL HAS ITS CARD, A VOTE ON NO BILL TOO (the person, 23 October
# 2026: "every vote on a rep's page should be a roll call in order to know how
# they voted ... The two displays should not be structured differently from
# each other"). A bill's roll calls are cards in its record, which its Votes
# tab draws as a ring with a row for each party's yes and no, and a member's
# Votes tab opens the same ring from that card. A roll call on no bill -- a
# rules suspension, a ruling of the chair, a reprimand -- had no record and so
# no card, and could be drawn only as its two counts. Its card is made here by
# the bill's own code (bill_rollcalls), from the same ballots, and kept a term
# to a file, nobill/<term>.json, {"rollcalls": [card, ...]}, so a member's
# Votes tab draws it with the bill page's own ring. A few hundred roll calls
# across every term; the files are small and fetched only when one is opened.
NOBILL = "nobill"


def write_nobill_cards(out, rollcalls, votes_by_bill, legs, unnamed):
    """Write nobill/<term>.json for every term with a roll call on no bill,
    and return {term: {roll call: index into that file's rollcalls}}."""
    folder = out / NOBILL
    folder.mkdir(parents=True, exist_ok=True)
    found, written = {}, set()
    for term, term_bills in sorted(rollcalls.items()):
        rows = term_bills.get("_procedural") or []
        if not rows:
            continue
        keys = {f"{r.get('year')}-{r.get('body')}-{r.get('number')}" for r in rows}
        # The ballots of these roll calls, wherever build_data filed them: a
        # vote on no bill is filed under its bill column as typed ("", or
        # "HRULE64"), never under "_procedural".
        ballots = defaultdict(list)
        for (t, _b), by_key in votes_by_bill.items():
            if t != term:
                continue
            for k, members in by_key.items():
                if k in keys:
                    ballots[k].extend(members)
        cards = bill_rollcalls("_procedural", term, rows, None,
                               {(term, "_procedural"): ballots}, legs, unnamed)
        at = {}
        for i, c in enumerate(cards):
            c.pop("_ord", None)
            k = c.pop("_rc", None)
            if k:
                at[k] = i
        f = folder / f"{term}.json"
        f.write_text(json.dumps({"term": term, "rollcalls": cards},
                                separators=(",", ":"), sort_keys=True), encoding="utf-8")
        written.add(f.name)
        found[term] = at
    # A term an earlier build wrote and this one has no such vote for.
    for stale in folder.glob("*.json"):
        if stale.name not in written:
            stale.unlink()
    n = sum(len(v) for v in found.values())
    print(f"{NOBILL}/: {n:,} roll calls on no bill, each with its card, in {len(found)} terms")
    # SILENCE IS NOT SUCCESS: the roll calls are there and none found a card.
    if any(t.get("_procedural") for t in rollcalls.values()) and not n:
        print(f"  WARNING: roll calls on no bill exist and {NOBILL}/ holds none of them")
    return found


def bill_rollcalls(bid, term, rcs, narr, votes_by_bill, legs, unnamed,
                   in_office=None):
    """Every recorded vote on one bill, in the order the docket took them.

    Lifted verbatim out of build_bills except for indentation.

    IT ALSO KILLS A SHADOW, BY CONSTRUCTION RATHER THAN BY CARE. In the
    enclosing scope `kind` is the bill's status kind, read five times in the
    payload; this block rebound it to a ("voice vote", False) tuple 147 lines
    after the last of those reads. Harmless only by that distance -- any new
    use of `kind` in the payload would silently have got a tuple or None. The
    same was true of `n`, a bill count outside and a nay count here. Neither
    name means anything else in this function now, so neither can shadow
    anything again.

    build_bills' own docstring records that this failure already happened
    once, with `st` meaning two things 350 lines apart. This is the second
    instance, found while splitting the function the first one caused.
    """
    rc_out = []
    rc_order, rc_names = vote_chronology(rcs, narr)
    for r in sorted(rcs, key=lambda x: (x.get("date", ""), int(x.get("number", 0)))):
        key = f"{r.get('year')}-{r['body']}-{r['number']}"
        members = votes_by_bill.get((term, bid), {}).get(key, [])
        tally = defaultdict(lambda: defaultdict(int))
        for m in members:
            tally[m["party"] or "X"][m["vote"]] += 1
        rc_out.append({
            "date": r.get("date"), "body": r.get("body"),
            "question": r.get("question"), "yeas": r.get("yeas"),
            "nays": r.get("nays"), "passed": r.get("passed"),
            "threshold_note": r.get("threshold_note"),
            # Which amendment this vote was on, where the docket says so.
            # "Adopt Amendment" twice in an afternoon is two different
            # amendments and no way to tell which is which.
            "amendment": rc_names.get((r.get("body"), r.get("number"))),
            "_ord": (r.get("date") or "",
                     rc_order.get((r.get("body"), r.get("number")),
                                  10 ** 6 + int(r.get("number") or 0))),
            # What the yes side had to reach, so the chart can mark it.
            # rollcall_outcomes works this out per motion: two thirds of
            # those voting for a veto override or a rules suspension, three
            # fifths of the members in office (the ballots, not the seats)
            # to pass a CACR, and whatever the docket or the Journal names
            # for a motion it says needed more; a simple majority otherwise.
            # `passed` is the clerk's recorded outcome where the record
            # names one, and where the record and the ballots disagree the
            # page says so -- in the site's own words, each side attributed
            # to its source -- rather than choosing quietly.
            "threshold_needed": r.get("threshold_needed"),
            "threshold_rule": r.get("threshold_rule"),
            **({"threshold_unknown": True} if r.get("threshold_unknown") else {}),
            **({"outcome_conflict": r["outcome_conflict"]}
               if r.get("outcome_conflict") else {}),
            "tally": {p: dict(v) for p, v in tally.items()},
            # The roll call's own name, "2026-H-95", taken off before the
            # record is written (build_bills): a session day names the card.
            "_rc": key,
            # "s" is the surname-first sort key. The grids are read
            # alphabetically, and sorting the displayed string would order
            # 400 members by honorific and then by first name.
            "members": [vote_member(m, r.get("body"), legs, unnamed)
                        for m in members],
        })

    # Voice and division votes, from the docket. A voice vote records only
    # which side sounded louder; a division records the count but not who
    # voted which way. Both decide bills, and leaving them off the votes tab
    # makes a bill look as though nothing happened on the floor.
    #
    # AND A DIVISION ON AN AMENDMENT, AND A VOTE ON A CONFERENCE REPORT (the
    # launch audit of 7 October 2026, cause 16). "Amendment # 2025-2406h: AF
    # DV 153-185" (SB 222 of 2025) and "FLAM # 2026-1971h(NT) ...: AA DV" are
    # counted votes of the floor, and the tab took floor motions alone, so 105
    # divisions on amendments of 2025-2026 had no card; nor did a chamber's
    # voice or division vote on a conference report, which narrative.py now
    # reads ("conf_report"). Asked in the roll call file's own words for the
    # same questions, "Adopt Floor Amendment", "Adopt Committee Amendment",
    # "Adopt Amendment", "Adopt Conference Committee Report", with the
    # number beside it. An amendment's voice vote is not drawn: 1,508 of
    # 2025-2026, most a committee's amendment adopted without a word; nor a
    # vote on part of one, whose question is not the amendment's.
    VK = {"VV": ("voice vote", False), "DV": ("division vote", False)}
    for _i, e in enumerate((narr or {}).get("events", [])):
        if e.get("cancelled"):
            continue
        vk = "DV" if (e.get("vote_kind") or "").upper() in ("DV", "DIV") else e.get("vote_kind")
        number = None
        if e.get("type") == "amendment":
            said = _amendment_said(e)
            if (vk != "DV" or not (e.get("yeas") and e.get("nays")) or said is None
                    or e.get("part") == "some"):
                continue
            k = (e.get("amend_kind") or "").lower()
            question = ("Adopt Floor Amendment" if "floor" in k
                        else "Adopt Committee Amendment" if "committee" in k
                        else "Adopt Amendment")
            passed, number = said, (e.get("amendment") or "").strip() or None
        elif e.get("type") == "conf_report":
            question = "Adopt Conference Committee Report"
            passed, number = e.get("motion") == "MA", (e.get("amendment") or "").strip() or None
        elif e.get("type") == "floor":
            question = e.get("action") or "Floor action"
            passed = e.get("motion") in ("MA", "AA")
        else:
            continue
        kind = VK.get(vk)
        if not kind:
            continue          # RC is already covered by the roll call file
        label, _ = kind
        y, n = e.get("yeas"), e.get("nays")
        # WHAT A DIVISION NEEDED, BY THE ROLL CALL'S RULE (17 October 2026).
        # These cards carried no threshold, so the chart marked a majority of
        # those voting on every one: "171 needed" beside the House's 325-15
        # on CACR 13, which needed three fifths of the 394 members in office,
        # 237. 185 counted divisions of 1989-2026 needed more than a majority
        # by their docket line, their question or the Journal
        # (rollcall_outcomes.division_threshold); fifteen of them of a count
        # not on record, which the chart leaves unmarked rather than marked
        # wrong.
        # And a CACR's division whose docket line names no fraction is read
        # with the House Journal's sentence for it (rollcall_outcomes.
        # journal_division_words): 2000's CACR 2, taken from the table "by
        # the necessary three-fifths", 17 October 2026.
        need = (RO.division_threshold(
                    bid, question, e.get("raw") or "", int(y), int(n),
                    (in_office or {}).get((e.get("body"), e["date"])), passed,
                    RO.journal_division_words(".", e.get("body"), e["date"], int(y), int(n))
                    if bid.upper().startswith("CACR") else "")
                if y and n else {})
        rc_out.append({
            "date": e["date"], "body": e.get("body"),
            "question": question,
            # Who made the motion, split off the question by narrative.py so
            # the Senate's "Sen. Abbas Moved Laid on Table" reads as a motion
            # to lay on the table, moved by Abbas. Roll calls from the roll
            # call file never carry one; the page prints it only when present.
            "mover": e.get("mover") or "",
            "yeas": int(y) if y else None, "nays": int(n) if n else None,
            "passed": passed,
            "vote_kind": vk, "vote_kind_label": label,
            "threshold_note": None, "tally": {}, "members": [],
            # The amendment's or the report's number, beside the question.
            "amendment": number, "_ord": (e["date"], _i),
            **need,
        })
    # THE MOTIONS ON THE BILL'S OWN DEBATE (the owner, 23 October 2026):
    # moving the previous question, limiting debate, dividing the question --
    # by division or by voice, from the bill's docket rows narrative.py reads
    # as no floor action ("Sen. Sanborn moved to call the question, MA, VV")
    # and from the Journal where the docket gives none (HB 1601's previous
    # question, 255-78 on a division, 12 March 2014). vote_passage decides
    # which, once for this tab and the session day; each is drawn before the
    # bill's own rows of that day, where the motion was made.
    for e in VP.motion_events(term, bid, (narr or {}).get("events", []), rcs):
        label, _ = VK[e["vote_kind"]]
        rc_out.append({
            "date": e["date"], "body": e["body"], "question": e["action"],
            "mover": e.get("mover") or "", "yeas": e.get("yeas"), "nays": e.get("nays"),
            "passed": e["motion"] == "MA", "vote_kind": e["vote_kind"],
            # By the Journal's own words (the owner, 23 October 2026): carried
            # "without objection" is said so, and is no voice vote.
            "vote_kind_label": "adopted without objection" if e.get("wo") else label,
            **({"wo": True} if e.get("wo") else {}),
            **({"ruling": e["ruling"]} if e.get("ruling") else {}),
            "threshold_note": None, "tally": {}, "members": [], "amendment": None,
            "_ord": (e["date"], e["_at"] - 0.5),
        })
    # By the docket's own sequence, not by the wording of the motion.
    rc_out.sort(key=lambda r: r["_ord"])
    return rc_out


def vote_note_for(narr, rollcalls):
    """The note above the votes table, silenced where it would contradict it."""
    note = (narr or {}).get("vote_note", "")
    if rollcalls and note.startswith("Every floor vote"):
        return ""
    return note
