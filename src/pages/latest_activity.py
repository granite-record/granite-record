#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.3
"""
What the home page's Latest Activity holds: the latest meetings, each with
the bills it took up and what was done to each there.

    import latest_activity as LA
    home["latest"] = LA.latest(rows, histories, today, bills)   # build_site_v2
    # build_pages.recent_box draws it, and did_html says what was done

ASKED FOR on 24 October 2026: "On the latest activity bar on the homepage,
bills should not be repeated twice like they are right now for both the bill
executive sessions and the outcome of the executive session listed as two
separate meetings. Maybe have latest activity show things like recent
meetings and all the bills from that meeting are grouped together and when
you click it, it takes you to the committee page or a house session day page
scrolled down to that meeting?"

WHY A BILL CAME TWICE. home.json's `recent` was the twelve newest events of
every bill's history, one row an event, and the box drew the first five. An
executive session is an event ("Executive Session: 10/23/2026 10:00 am GP
230") and the report the committee voted at it is another ("Interim Study
Report: Not Recommended for Future Legislation 10/23/2026 (Vote 18-3;)"), on
the same day, so every bill a committee voted on took two of the five rows.
On 24 October 2026 the box was HB 1710 twice, SB 193 twice and SB 441: three
bills, and the meeting each was voted at named by none of them.

ONE ITEM A MEETING, AS COMING UP HAS THEM. A committee's day -- whatever kinds
of sitting it held, as build_pages.meeting_key keys a card of Coming up and of
the Calendar, which a committee's page also lists one entry a day under
#day-<date> -- or a chamber's sitting, which has a page of its own. Each bill
the meeting took up is in it once, with what was done to it there.

WHAT WAS DONE, ASKED OF WHAT ALREADY SAYS IT:

  a committee's meeting   committee_acts.outcome, the committee page's own
                          reading: the recommendation, interim study report or
                          retention the docket dates to that meeting, or, for
                          an executive session with none dated to it, the
                          committee's next act on the bill with its own date
                          (House HHS met on 15 October 2026 and its reports
                          are dated the 22nd: "No vote at this meeting" on its
                          page, and the vote and its day here);
  a chamber's sitting     the session day's own motions (session_days.
                          floor_items, motions.classify): the last motion that
                          settled where the bill stands, in the vote words the
                          sitting's page draws it in.

Data, not words: build_pages says it, in the page's language (did_html).

NOT HERE: a study or statutory committee's meeting, which Coming up leaves
off too (build_pages.home_week, the person, 7 October 2026); a committee of
conference, one bill's meeting with no page to lead to, whose report is
voted at the sittings that are here; a sitting the docket names no committee
for; and a cancelled one, which did not happen.

Standard library and the project's own readers only; build_site_v2 calls it
where the histories are already read.
"""

import re
from collections import OrderedDict, defaultdict

import bill_order as BO
import committee_acts as CA
import proceedings as P

# Meetings kept in home.json, newest first. The page shows fewer
# (build_pages.RECENT_SHOWN); the rest are there for a page that is read a day
# or two after it was built, and for a check.
LIMIT = 12
# Bills kept for each meeting the page does not show, against a page read a
# day or two after its build. A meeting it shows keeps every bill, up to
# build_pages.RECENT_BILLS, since its card opens on all of them (the owner,
# 24 October 2026: "the ability to click it for a dropdown to list all the
# bills from that session"); "and N more" counts from `n` past that. A House
# sitting takes up a hundred and more, and home.json is fetched by every
# visit to the home page.
BILLS_KEPT = 8

# A BILL'S TITLE, KEPT TO THIS MANY CHARACTERS, AND CUT AT A WORD (the owner's
# review of the new box, 24 October 2026). home.json is fetched by every
# visit, so a long title is cut; drawn whole in a card that opens, a title cut
# at exactly 110 read "... in businesses owned by a sitting president or t".
# It ends at the last whole word inside the limit now, with an ellipsis.
TITLE_KEPT = 110
DANGLING = frozenset({"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on",
                      "or", "the", "to", "with"})
# What a committee's meeting is not, for this box (above).
STUDY_KINDS = ("study committee", "statutory committee")
NOT_HELD = ("cancelled",)

# THE MOTIONS THAT DO NOT SAY WHERE A BILL STANDS. A sitting can put several
# questions to one bill -- an amendment, then the report it amends -- and the
# box says what the sitting did to the bill, which is the last motion that
# settled something about it. These are the questions that settle something
# else: a part of the bill's text, the order of business, the rules, a member.
# votes.json's own keys.
PROCEDURAL = frozenset({
    "committee_amendment", "floor_amendment", "amendment", "enrolled_amendment",
    "table_amendment", "table_motion", "reconsider", "special_order",
    "suspend_rules", "previous_question", "limit_debate", "divide", "part",
    "uphold_ruling", "member_continue", "print_debate", "reprimand", "unnamed",
    "waive_referral", ""})


def short_title(title, n=TITLE_KEPT):
    """`title` as Latest Activity keeps it: whole up to `n` characters, and
    past that cut at the last whole word inside `n`, with an ellipsis."""
    t = " ".join((title or "").split())
    if len(t) <= n:
        return t
    head = t[:n + 1]
    cut = head.rsplit(" ", 1)[0] if " " in head else t[:n]
    # Nor on a word that leads into what was cut: "president or..." reads as
    # a sentence stopped, "president..." as one shortened.
    words = cut.split(" ")
    while len(words) > 1 and words[-1].lower().strip(",;:-") in DANGLING:
        words.pop()
    return " ".join(words).rstrip(" ,;:-") + "\u2026"


def spaced(bill):
    """"HB1710" -> "HB 1710", as Coming up's cards print a number."""
    return re.sub(r"^([A-Z]+)(\d)", r"\1 \2", str(bill or ""))


def _code(name, body):
    """A committee as committee_acts compares one (owners' `code_of`): its
    chamber's letter first, which is all at_meeting reads of it, and its name
    as the docket writes it, which the reports and the meetings share."""
    return (body or "").strip().upper()[:1] + "|" + re.sub(r"\s+", " ", (name or "").strip().lower())


def _int(v):
    s = str(v if v is not None else "").strip()
    return int(s) if s.isdigit() else None


def committee_rows(rows, histories, today):
    """The proceedings rows of committee meetings held on or before `today`,
    as the calendar reads a row (build_calendar.weeks_from), with the bare
    notices left off (proceedings.sittings)."""
    out = []
    for r in P.committee_only(rows):
        date = (r.get("date") or "")[:10]
        kind = (r.get("kind") or "").strip()
        cmte = (r.get("committee") or "").strip()
        if (not re.match(r"\d{4}-\d\d-\d\d$", date) or date > today or not cmte
                or not (r.get("bill") or "").strip() or r.get("study")
                or kind.lower() in STUDY_KINDS or kind.lower() in NOT_HELD):
            continue
        out.append(r)
    kept, _notices = P.sittings(out, histories)
    return [{"date": r["date"][:10], "time": (r.get("time") or "").strip(),
             "bill": (r.get("bill") or "").strip().upper(),
             "committee": (r.get("committee") or "").strip(),
             "what": (r.get("kind") or "").strip(),
             "venue": (r.get("venue") or "").strip(),
             "body": (r.get("body") or "").strip().upper(),
             "term": (r.get("term") or "").strip()} for r in kept]


def floor_days(histories, today, terms=None):
    """{(body, date): {(term, bill)}}: the days each chamber sat on a bill, on
    or before `today`, from the floor's rows of each history. `terms` limits
    the terms read, newest first being all a box of the latest needs."""
    out = defaultdict(set)
    for term, byb in (histories or {}).items():
        if terms is not None and term not in terms:
            continue
        for bill, rec in (byb or {}).items():
            for e in (rec or {}).get("events") or ():
                if e.get("type") not in ("floor", "veto_override") or e.get("cancelled"):
                    continue
                body = (e.get("body") or "").strip().upper()
                date = (e.get("date") or "")[:10]
                if body in ("H", "S") and re.match(r"\d{4}-\d\d-\d\d$", date) and date <= today:
                    out[(body, date)].add((term, bill))
    return out


def floor_did(bill, term, events, body, date, motion_words):
    """What chamber `body` did to the bill at its sitting of `date`: the last
    motion that settled where the bill stands and carried, else the last such
    motion put, as {"act": "floor", "mk", "mf", "carried", "yeas", "nays",
    "consent"}; None where the sitting put none to it. The vote words are
    motions.classify's, as the sitting's page reads the same motion."""
    import motions as MO
    import session_days as SD
    put = []
    for e, it in SD.floor_items(bill, term, events):
        if (it.carried is None or (e.get("body") or "").strip().upper() != body
                or (e.get("date") or "")[:10] != date):
            continue
        k = MO.classify(it.action, bill, body, motion_words)
        if k.get("mk", "") in PROCEDURAL:
            continue
        put.append((it, k))
    if not put:
        return None
    it, k = next(((i, k) for i, k in reversed(put) if i.carried), put[-1])
    did = {"act": "floor", "mk": k["mk"], "carried": bool(it.carried)}
    if k.get("mf"):
        did["mf"] = k["mf"]
    if it.counted:
        did["yeas"], did["nays"] = it.yeas, it.nays
    if it.consent:
        did["consent"] = True
    return did


def committee_did(code, date, kinds, acts, owners, mine, today):
    """What committee `code` did to a bill at its meeting of `date`, as
    committee_acts.outcome reads it, made into one act: {"act": "report" |
    "study report" | "retained", ...} with the vote's own fields, and `dated`
    where the docket dates the act to another day than this meeting. None
    where the meeting voted nothing and no act of the committee's follows an
    executive session (a hearing, a work session)."""
    o = CA.outcome(code, date, kinds, acts, owners, mine)
    if o.get("outcome") == "voted" and o.get("votes"):
        return _act(o["votes"][0])
    v = o.get("voted") or {}
    if o.get("outcome") != "no vote" or not v.get("date") or v["date"] < date or v["date"] > today:
        return None
    for a, own in zip(acts, owners):
        if own == code and a["act"] == v.get("act") and a["date"] == v["date"]:
            return {**_act(CA.public(a)), "dated": v["date"]}
    return None


def _act(a):
    """An act as the box needs it: what it was and its vote."""
    keep = ("act", "code", "recommendation", "said", "yeas", "nays")
    return {k: a[k] for k in keep if a.get(k) is not None and a.get(k) != ""}


def latest(rows, histories, today, bills=None, limit=LIMIT, kept=BILLS_KEPT,
           motion_words=None):
    """[meeting], newest first, `limit` of them:

        {"date", "floor": True|absent, "body", "committee" (a committee's
         name as the docket writes it; absent on a sitting), "kinds": [the
         kinds of sitting, in the day's order], "time", "last" (the first and
         last slots, "HH:MM"; absent on a sitting), "n": every bill it took
         up, "bills": [{"bill", "term", "year", "n", "title", "did"?}] the
         first `kept` of them, or build_pages.RECENT_BILLS for each of the
         first RECENT_SHOWN, the meetings the home page shows}

    `rows` is proceedings.csv's (proceedings.load), `histories`
    narratives.json's {term: {bill: history}}, `today` "YYYY-MM-DD", `bills`
    {(term, bill): index row} for each bill's year and title, and
    `motion_words` votes.json's "motions", which classify reads.

    Newest first: by day, a sitting before the committees that met that day,
    and the committees by the hour each finished, the latest first.
    """
    import build_pages as BP
    today = str(today)[:10]
    bills = bills or {}

    # ---- the meetings ------------------------------------------------------
    meets = OrderedDict()
    crows = committee_rows(rows, histories, today)
    for r in crows:
        meets.setdefault(("c", BP.meeting_key(r)), []).append(r)
    newest = sorted({t for t in (histories or {})}, reverse=True)[:2]
    for (body, date), bs in floor_days(histories, today, set(newest)).items():
        meets[("f", (body, date))] = sorted(bs)

    def order(item):
        kind, key = item
        if kind == "f":
            return (key[1], 1, "99:99", key[0] == "H")
        rs = meets[item]
        return (key.date, 0, max((r["time"] for r in rs if r["time"]), default=""), False)
    # Two committees that finished at one hour, by name: sorted so first, as
    # the sort that follows keeps the order of what it holds equal.
    chosen = sorted(meets, key=lambda it: "" if it[0] == "f" else it[1].name.lower())
    chosen = sorted(chosen, key=order, reverse=True)[:limit]

    # ---- what each bill's committees did ------------------------------------
    # Every meeting of each chosen bill, across committees, as build_committees
    # gives committee_acts (its met_on): whose an act is, and which of a
    # committee's meetings the docket dates it to.
    want = {(r["term"], r["bill"]) for k in chosen if k[0] == "c" for r in meets[k]}
    met_on = defaultdict(lambda: defaultdict(set))
    for r in crows:
        if (r["term"], r["bill"]) in want:
            met_on[(r["term"], r["bill"])][(r["date"], _code(r["committee"], r["body"]))].add(
                r["what"].lower())
    acts_of, owners_of = {}, {}

    def history(term, bill):
        return (((histories or {}).get(term) or {}).get(bill) or {}).get("events") or []

    def acts(term, bill):
        k = (term, bill)
        if k not in acts_of:
            acts_of[k] = CA.acts(history(term, bill))
            meetings = sorted((d, c, sorted(ks)) for (d, c), ks in met_on[k].items())
            owners_of[k] = CA.owners(acts_of[k], meetings, _code)
        return acts_of[k], owners_of[k]

    def bill_row(term, bill, did):
        b = bills.get((term, bill)) or {}
        row = {"bill": bill, "term": term, "year": b.get("year") or "",
               "n": spaced(bill), "title": short_title(b.get("title"))}
        if did:
            row["did"] = did
        return row

    def cap(i):
        """How many bills the i-th meeting keeps (BILLS_KEPT)."""
        return max(kept, BP.RECENT_BILLS) if i < BP.RECENT_SHOWN else kept

    out = []
    for item in chosen:
        kind, key = item
        if kind == "f":
            body, date = key
            got = []
            for term, bill in meets[item]:
                did = floor_did(bill, term, history(term, bill), body, date, motion_words)
                got.append((bool(did and did.get("consent")), term, bill, did))
            # What the sitting settled first; and what the chamber debated
            # before what it took together on its consent calendar, as the
            # sitting's page parts them.
            got.sort(key=lambda g: (g[3] is None, g[0], BO.bill_key(g[2])))
            # "floor debate", the kind a sitting's rows carry on the Calendar
            # (meeting_kinds.json), whose colour its bar takes.
            out.append({"date": date, "floor": True, "body": body, "kinds": ["floor debate"],
                        "n": len(got),
                        "bills": [bill_row(t, b, d) for _c, t, b, d in got[:cap(len(out))]]})
            continue
        rs = sorted(meets[item], key=lambda r: (r["time"] or "~", r["what"], BO.bill_key(r["bill"])))
        code = _code(key.name, key.chamber)
        kinds = list(OrderedDict.fromkeys(r["what"] for r in rs))
        per = OrderedDict()
        for r in rs:
            per.setdefault((r["term"], r["bill"]), set()).add(r["what"].lower())
        got = []
        for (term, bill), ks in per.items():
            a, own = acts(term, bill)
            mine = {d: sorted(k) for (d, c), k in met_on[(term, bill)].items() if c == code}
            got.append((term, bill, committee_did(code, key.date, sorted(ks), a, own, mine, today)))
        # What the committee did something to, first, in the meeting's order.
        got.sort(key=lambda g: g[2] is None)
        slots = sorted(r["time"] for r in rs if r["time"])
        m = {"date": key.date, "body": key.chamber, "committee": key.name, "kinds": kinds,
             "n": len(got), "bills": [bill_row(t, b, d) for t, b, d in got[:cap(len(out))]]}
        if slots:
            m["time"], m["last"] = slots[0], slots[-1]
        out.append(m)
    return out


def key_of(m):
    """The build_pages.meeting_key of a meeting `latest` wrote, or None for a
    sitting: for its name, and the link to its committee."""
    if m.get("floor"):
        return None
    import build_pages as BP
    return BP.meeting_key({"date": m.get("date"), "what": (m.get("kinds") or [""])[0],
                           "committee": m.get("committee"), "body": m.get("body")})
