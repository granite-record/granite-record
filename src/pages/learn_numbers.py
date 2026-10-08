#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-14.10
"""
The record in numbers: a Learn page of statistics computed from the site's own data.

    import learn_numbers; html = learn_numbers.body(site=Path("site"), root=Path("."))

Asked for by the person on 13 September ("interesting data for the political science nerds")
and defined by them the same evening -- LAUNCH.md section 0a has the list and their decisions.
build_civics.py writes it to /learn/by-the-numbers.html.

It shipped as a draft: noindex, absent from the Learn hub and from the sitemap, so the person
could read it at its own address before anyone else was led to it. They read it and asked on
17 September for it to be public, and all three of those are now gone. It is still not one of
civics.TOPICS -- those are short explanations meant to be read in order, and this is a long
table of counts -- so the hub links it under a heading of its own after them.

Every figure is counted at build time, never typed, and each section says what it counts, over
what period, and how.

THE SECOND BATCH (7 October 2026, the person's front-end notes F16-F22). Each figure was
measured first, read-only, against sources this project did not write, and the counting
moved here only once the measurement held: bills filed and how they ended, per term; bills
filed and passed per member; the bills each committee received; the hearings with the most
sign-ins; each committee's passage rate; bills passed as introduced against amended, and how
many amendments a bill takes; attendance on roll-call days; and the constitutional
amendments sent to the voters, with the Secretary of State's count. The consent-calendar
table gained its two totals, and a Senate report the docket prints a second time counts once.
"Laws without the governor's signature" and the veto table's "Awaiting" column went, at the
person's word. Every figure has a function here that a check in preflight runs on a fixture
whose answer is known, which is what holds its definition still.

A MISSING INPUT IS SAID, NOT SKIPPED IN SILENCE. body() reads files a build makes or the kit
carries (narratives.json, testimony_db.json, data/member_votes.json, ballot_results.json). Where
one is not there its section is left out -- as build_site_v2 leaves out the voters' card when
ballot_results.json is missing -- and MISSING names it, which build_civics prints; preflight's
data checks fail on a built page that lacks a section. That is because the builders' fixture
site holds none of them and must still build. What does stop the build is a figure whose input
is here and cannot be finished: a hearing's bill retitled later with no printing on disk to
give the title it was heard under (strict, the default; preflight's fixtures pass False).
A constitutional amendment the voters decided whose row of ballot_results.json names no
source or no cite is left off its table and named in HELD, which build_civics prints too.
"""

import html
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date as _date
from pathlib import Path

import adopted_amendments as AA
import ballot_source as BS
import build_date
import committee_names as CN
import later_referrals as LR
import narrative
import site_read as SR

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def _load(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "&mdash;"


def _np(n, d):
    """A count and its share: "1,240 (57.7%)", on one line -- in a six-column
    table the browser otherwise breaks it before the bracket, row by row."""
    return f"{n:,}&nbsp;({_pct(n, d)})"


def _table(head, rows, cls="numtab"):
    # The first column is a term, a year, a bill or a chamber, and app.css
    # keeps it on one line ("1989-1990" broke at its dash); a committee's
    # name is the exception, and wraps.
    if head and head[0] == "Committee":
        cls += " names"
    return (f'<div class="tablewrap"><table class="{cls}"><thead><tr>'
            + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
            + "</tbody></table></div>")


def _t(term):
    return E(term).replace("-", "&ndash;")


YEAR = {}   # (term, bill) -> filing year, from the index; filled by body()


def _bill_link(term, bid, year=None):
    y = year or YEAR.get((term, bid)) or term.split("-")[0]
    shown = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid)
    return f'<a href="bill/{E(y)}/{E(bid.lower())}">{E(shown)}</a>'


def _day(iso):
    """"2025-02-10" -> "10 Feb 2025"."""
    try:
        d = _date.fromisoformat(iso)
    except (TypeError, ValueError):
        return E(iso)
    return f"{d.day}&nbsp;{d:%b}&nbsp;{d:%Y}"


def _cat(text):
    """PASS, KILL or STUDY from a motion or a report's recommendation."""
    t = (text or "").lower()
    if "interim study" in t:
        return "STUDY"
    if "ought to pass" in t:
        return "PASS"
    if "inexpedient to legislate" in t or "indefinitely postpone" in t:
        return "KILL"
    return None


# What a bill is in the figures that count bills: a House or Senate bill,
# special sessions' included. Resolutions and constitutional amendments are
# not bills. A joint resolution does go to the governor -- HJR 1 of 2007 was
# signed -- so the veto table, which counts what reached the governor, says
# "bills and joint resolutions" and can run a few above the bills here.
BILL = re.compile(r"^(?:SS)?[HS]B\d+$")
LAW = frozenset({"Signed into law", "Became law unsigned", "Veto overridden, became law"})
# A veto whose override vote is still to come, in bill_disposition's words
# (build_site_v2.VETO_PENDING); "Vetoed, override failed" is not one.
VETO_PENDING = frozenset({"Vetoed", "Vetoed, awaiting an override vote",
                          "Vetoed, override vote pending"})
# Passed both chambers in the same text: it reached the governor.
REACHED = LAW | VETO_PENDING | {"Vetoed, override failed"}
SEATS = {"H": 400, "S": 24}
NAME = {"H": "House", "S": "Senate"}


# A QUESTION A MAJORITY DOES NOT DECIDE. A veto override needs two thirds, a
# rules suspension two thirds, and passing a constitutional amendment three
# fifths of the members in office, so a margin of one on any of them says
# nothing about how close it was: HB 1072's override at 160-159 was 53 short
# of what it needed, and it led the table of closest votes. Decided by the
# question rather than by threshold_needed, which has been set on CACR motions
# that need only a majority -- a kill motion and a floor amendment among them
# -- so a close vote of that kind would have been dropped for no reason.
_OVERRIDE_Q = re.compile(r"veto|become law", re.I)
_SUSPEND_Q = re.compile(r"\bsusp", re.I)
_CACR_PASSAGE_Q = re.compile(r"^\s*(ought to pass|otp|concur|adopt conference|third reading|"
                             r"final passage|pass)", re.I)


def needs_more_than_majority(bid, r):
    """True for a roll call on a question that needs more than a majority."""
    q = " ".join(str(r.get(k) or "") for k in ("question", "question_raw"))
    if _OVERRIDE_Q.search(q) or _SUSPEND_Q.search(q):
        return True
    return (bid or "").upper().startswith("CACR") and bool(
        _CACR_PASSAGE_Q.search(r.get("question") or "")
        or _CACR_PASSAGE_Q.search(r.get("question_raw") or ""))


def overturned(narr):
    """(per chamber {ch: (decided, against, passage<->kill)}, [(bid, ch, rec, floor)])."""
    stats, cases = {}, []
    for ch in ("H", "S"):
        decided = against = swap = 0
        for bid, rec in narr.items():
            ev = rec.get("events") or []
            reports = [e for e in ev if e.get("body") == ch and e.get("type") == "report"
                       and not (e.get("raw") or "").lower().startswith("minority")]
            if not reports:
                continue
            first = reports[0].get("date", "")
            dec = next(((e, _cat(e.get("action"))) for e in ev
                        if e.get("body") == ch and e.get("type") == "floor" and e.get("motion") == "MA"
                        and _cat(e.get("action")) and e.get("date", "") >= first), None)
            if not dec:
                continue
            e, fc = dec
            before = [r for r in reports if r.get("date", "") <= e.get("date", "")]
            rc = _cat(re.sub(r"^.*?report:\s*", "", (before or reports)[-1].get("raw") or "", flags=re.I))
            if not rc:
                continue
            decided += 1
            if rc != fc:
                against += 1
                swap += {rc, fc} == {"PASS", "KILL"}
                cases.append((bid, ch, rc, fc))
        stats[ch] = (decided, against, swap)
    return stats, cases


# ---------------------------------------------------------------------------
# The figures. Each takes what it counts and returns the counts; body() draws
# them. preflight runs every one on a fixture whose answer is known.
# ---------------------------------------------------------------------------

def outcomes(idx):
    """{term: Counter(filed, Became Law, Died, Interim Study, other)}.

    Every House and Senate bill the term numbered, by the chip its card shows
    (build_site_v2.chip_word): Became Law, Died -- killed, tabled and left
    there, vetoed with the veto standing, or lost between the chambers --
    Interim Study, and everything else as other: withdrawn, never introduced,
    or, while a session still sits, not yet decided."""
    out = defaultdict(Counter)
    for r in idx:
        if not BILL.match(r.get("id") or ""):
            continue
        c = out[r.get("term")]
        c["filed"] += 1
        chip = r.get("chip")
        c[chip if chip in ("Became Law", "Died", "Interim Study") else "other"] += 1
    return out


def per_member(idx):
    """{term: {"H": [filed, became law], "S": [...]}}: House and Senate bills
    by the chamber their prime sponsor sat in, as the index's sponsor label
    names it ("Rep." or "Sen."). A bill a committee sponsored counts to
    nobody. Divided by SEATS on the page."""
    out = defaultdict(lambda: {"H": [0, 0], "S": [0, 0]})
    for r in idx:
        if not BILL.match(r.get("id") or ""):
            continue
        lab = (r.get("sponsor_label") or "").strip()
        ch = "H" if lab.startswith("Rep") else "S" if lab.startswith("Sen") else None
        if ch:
            c = out[r.get("term")][ch]
            c[0] += 1
            c[1] += r.get("status") in LAW
    return out


def _first_referrals(row):
    """{"H": committee, "S": committee} as the bill's page names them."""
    out = {}
    for c in row.get("committees") or []:
        word, _, nm = c.partition(" ")
        ch = {"House": "H", "Senate": "S"}.get(word)
        if ch and nm and nm.lower() != "no committee assignment":
            out[ch] = nm
    return out


def referrals(idx, narr, term):
    """{"House X": [first referrals, sent on to it]} for the term.

    First referral: the committee a chamber first sent the bill to, as the
    bill's page names it (one per bill per chamber). Sent on: the bill came to
    the committee after another committee of the same chamber had it -- a
    second referral, most often to Finance or Ways and Means for a bill with a
    cost -- read from the docket by later_referrals. Every numbered measure of
    the term counts, resolutions and constitutional amendments included."""
    out = defaultdict(lambda: [0, 0])
    for r in idx:
        if r.get("term") != term:
            continue
        first = _first_referrals(r)
        if not first:
            continue
        refs = LR.chamber_referrals((narr.get(r.get("id")) or {}).get("events"), term)
        for ch, fc in first.items():
            out[f"{NAME[ch]} {fc}"][0] += 1
            seq = refs[ch]
            pos = seq.index(fc) if fc in seq else -1
            for c in seq:
                if c != fc and (pos < 0 or seq.index(c) > pos):
                    out[f"{NAME[ch]} {c}"][1] += 1
    return out


def committee_rates(idx, narr, term):
    """({"House X": [reported on, passed both chambers, became law]},
         {"H": [bills, passed, law], "S": [...]}).

    Of the House and Senate bills a committee made a majority report on in
    the term, whatever it recommended, how many passed both chambers and how
    many became law. A bill two committees of a chamber reported on counts in
    both rows; the chamber's totals count it once, under the first."""
    rows, tot = defaultdict(lambda: [0, 0, 0]), {"H": [0, 0, 0], "S": [0, 0, 0]}
    for r in idx:
        if r.get("term") != term or not BILL.match(r.get("id") or ""):
            continue
        seen = AA.reporting_committees((narr.get(r["id"]) or {}).get("events"), term, CN.official)
        passed, law = r.get("status") in REACHED, r.get("status") in LAW
        for ch in ("H", "S"):
            for i, name in enumerate(seen[ch]):
                c = rows[f"{NAME[ch]} {name}"]
                c[0] += 1
                c[1] += passed
                c[2] += law
                if i == 0:
                    tot[ch][0] += 1
                    tot[ch][1] += passed
                    tot[ch][2] += law
    return rows, tot


def passage(idx, narr_all):
    """{term: {"passed", "amended", "conference", "dist": Counter(amendments)}}.

    Every House and Senate bill that passed both chambers (it reached the
    governor). Amended: either chamber adopted an amendment before the
    governor acted, or the bill went to a committee of conference; the
    Enrolled Bills Committee's technical correction is not an amendment. The
    distribution counts the amendments the two chambers adopted, 6 standing
    for six or more (adopted_amendments says how)."""
    out = defaultdict(lambda: {"passed": 0, "amended": 0, "conference": 0, "dist": Counter()})
    for r in idx:
        if not BILL.match(r.get("id") or "") or r.get("status") not in REACHED:
            continue
        ev = ((narr_all.get(r.get("term")) or {}).get(r["id"]) or {}).get("events")
        per, conf, _eba = AA.chamber_amendments(ev)
        o = out[r.get("term")]
        o["passed"] += 1
        o["amended"] += per["H"]["amended"] or per["S"]["amended"] or conf
        o["conference"] += conf
        o["dist"][min(per["H"]["n"] + per["S"]["n"], 6)] += 1
    return out


def consent(narr, rows_by, term=""):
    """({committee: [recommendations, on consent and kept there]},
         {"H": Counter(kept, regular, removed), "S": ...}).

    Every majority committee report of the term, credited to the committee
    that made it, as adopted_amendments reads it for the passage rates --
    the bill's committee in that chamber only where the report names none. A
    report the docket prints a second time -- the
    Senate reprints one when a bill taken off its consent calendar comes back
    as a special order -- with the same committee, recommendation, amendment
    and tally as the report before it counts once. On consent and kept: the
    report carries CC and the chamber did not take the bill off; removed: it
    carried CC and the chamber did; regular: it never went on consent."""
    by_c = defaultdict(lambda: [0, 0])
    per = {"H": Counter(), "S": Counter()}
    for bid, rec in narr.items():
        row = rows_by.get(bid) or {}
        ev = rec.get("events") or []
        # A REMOVAL IS A REMOVAL HOWEVER THE ROW IS TYPED. This read the rows
        # typed consent_off and no others, and counted as kept on the calendar
        # 59 reports of 2025-2026 whose chamber took them off in a row typed
        # "other" -- every one of the House's "Removed from Consent (Reps.
        # ...)" of the term, HB 691 of 2025 among them, decided on a roll
        # call of 190-156. The histories' reader is the one list of wordings.
        off = {e.get("body") for e in ev if not e.get("cancelled")
               and (e.get("type") == "consent_off"
                    or narrative.removed_from_consent(e.get("raw")))}
        # A SECOND COMMITTEE'S REPORT IS THAT COMMITTEE'S. This credited every
        # report to the committee the bill's page names, so 247 reports of
        # 2025-2026 that Finance, Ways and Means and the rest made after a
        # second referral counted to the bill's first committee: House Finance
        # showed 20 reports here while the passage rates below, on the same
        # page, showed it reporting on 107 bills. The totals did not move.
        made_by = {id(e): nm for e, _ch, nm in AA.credited_reports(ev, term, CN.official)}
        prev = {}
        for e in ev:
            if e.get("type") != "report" or (e.get("raw") or "").lower().startswith("minority"):
                continue
            ch = e.get("body")
            key = (e.get("committee"), e.get("recommendation"), e.get("amendment"),
                   e.get("yeas"), e.get("nays"))
            reprint = prev.get(ch) == key
            prev[ch] = key
            word = "House " if ch == "H" else "Senate "
            cm = next((c for c in row.get("committees") or [] if c.startswith(word)), "")
            if cm and made_by.get(id(e)):
                cm = word + made_by[id(e)]
            if not cm or reprint or ch not in per:
                continue
            by_c[cm][0] += 1
            cc = bool(re.search(r"\bCC\b", e.get("raw") or ""))
            if cc and ch not in off:
                by_c[cm][1] += 1
                per[ch]["kept"] += 1
            else:
                per[ch]["removed" if cc else "regular"] += 1
    return by_c, per


def attendance(votes):
    """{(term, "H"|"S"): (roll-call days, mean share present)}, 1999 on.

    For each day a chamber took at least one roll call, the share of the
    members on that day's ballots who were present for at least one of them --
    voting, presiding or declaring a conflict -- averaged over the days. The
    ballots are the member pages' (build_site_v2.member_attendance's rules):
    the day a misdated roll call was really taken, the presiding officer the
    record leaves unnamed, and a run of empty ballots ending a member's term
    as a seat nobody held."""
    import build_site_v2 as B
    import proceedings as P
    by_member = defaultdict(list)
    for v in votes:
        by_member[v.get("member_id")].append(v)
    ctx = B.attendance_context(by_member)
    dates, chair = ctx["dates"], ctx["chair"]
    seq = defaultdict(list)
    for v in votes:
        t = P.vote_term(str(v.get("year") or ""), v.get("date"))
        if not t:
            continue
        key = B._roll_call_key(v)
        kind = B.ATTENDANCE_KIND.get(v.get("vote"), "no_vote")
        if v.get("conflict"):
            kind = "conflict"
        elif kind in ("excused", "not_excused") and chair.get(key) == v.get("member_id"):
            kind = "presided"
        num = str(v.get("vote_number") or "")
        seq[(v.get("member_id"), t, v.get("body"))].append(
            ((str(v.get("year")), int(num) if num.isdigit() else 0), key, kind))
    days = defaultdict(lambda: defaultdict(lambda: [set(), set()]))
    for (mid, t, body), run in seq.items():
        run.sort(key=lambda b: b[0])
        while run and run[-1][2] == "no_vote":
            run.pop()
        for _o, key, kind in run:
            day = dates.get(key)
            if not day or day == (0, 0, 0):
                continue
            d = days[(t, body)][day]
            d[0].add(mid)
            if kind in ("voted", "presided", "conflict"):
                d[1].add(mid)
    out = {}
    for k, ds in days.items():
        shares = [len(p) / len(m) for m, p in ds.values() if m]
        if shares:
            out[k] = (len(shares), statistics.fmean(shares))
    return out


# -- the hearings with the most sign-ins ------------------------------------
_D = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _amendment_hearing(ev, day):
    """"a non-germane amendment" or "an amendment" where the docket's line for
    `day` is a public hearing on one rather than on the bill, else ""."""
    if any(e.get("type") == "hearing" and e.get("body") == "H" and not e.get("cancelled")
           and e.get("date") == day for e in ev):
        return ""
    for e in ev:
        raw = e.get("raw") or ""
        if any(f"{m.group(3)}-{m.group(1)}-{m.group(2)}" == day for m in _D.finditer(raw)):
            m = re.search(r"public hearing on (non-germane )?amendment", raw, re.I)
            if m:
                return "a non-germane amendment" if m.group(1) else "an amendment"
            return ""
    return ""


def _house_committee_after(ev, row, day):
    """The House committee that reported on the bill first on or after `day`,
    else the one its page names."""
    for e in ev:
        if (e.get("type") == "report" and e.get("body") == "H" and not e.get("cancelled")
                and not (e.get("raw") or "").lower().startswith("minority")
                and (e.get("date") or "") >= day and e.get("committee")):
            return e["committee"]
    return next((c[6:] for c in row.get("committees") or [] if c.startswith("House ")), "")


def version_title(text, bid):
    """The title a printing of a bill carries: what follows AN ACT or A
    RESOLUTION, or a CACR's RELATING TO and PROVIDING THAT, up to SPONSORS."""
    t = re.sub(r"\s+", " ", text or "")
    if bid.startswith("CACR"):
        m = re.search(r"RELATING TO:\s*(.+?)\s*PROVIDING THAT:\s*(.+?)\s*SPONSORS:", t)
        if m:
            return f"relating to {m.group(1).strip()} Providing that {m.group(2).strip()}"
    m = re.search(r"\b(?:AN ACT|RESOLUTION)\s+(.+?)\s*SPONSORS:", t)
    return m.group(1).strip() if m else ""


def _site_version_title(site, year, bid, day):
    """The title of the latest printing dated on or before `day`, from the
    bill's versions on the site (build_bill_versions), or None where the site
    holds none for it -- a bill printed once, which kept its title."""
    p = Path(site) / "versions" / str(year) / f"{bid}.json"
    if not p.exists():
        return None
    # THE FIRST PRINTING WHERE NONE IS DATED BEFORE THE HEARING. A version's
    # date is when the database stored it, which can trail the printing: HB
    # 524 of 2025 was heard on 12 February and its Introduced row is dated 5
    # March. The first printing is the introduced text, which is what a first
    # hearing hears.
    vs = (_load(p, {}) or {}).get("versions") or []
    best = 0 if vs else None
    for i, v in enumerate(vs):
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", v.get("date") or "")
        if m and f"{m.group(3)}-{m.group(1)}-{m.group(2)}" <= day:
            best = i
    if best is None:
        return None
    f = Path(site) / "versions" / str(year) / f"{bid}.{best}.txt"
    return version_title(f.read_text(encoding="utf-8"), bid) if f.exists() else None


_INTRODUCED, _SENATE_AMENDED = {3, 4}, {5}


def _past_titles(root, wanted):
    """{(year, bid): {"intro": title, "senate": title}} for the printings the
    General Court's dump of past bills' text holds (db/past/
    PastLegislationText.jsonl), read once for the bills in `wanted`."""
    p = Path(root) / "db" / "past" / "PastLegislationText.jsonl"
    out = defaultdict(dict)
    if not p.exists() or not wanted:
        return out
    marks = {f'"BillNbr":"{b}"'.encode(): b for _y, b in wanted}
    with p.open("rb") as fh:
        for line in fh:
            hit = next((b for m, b in marks.items() if m in line), None)
            if not hit:
                continue
            r = json.loads(line)
            key = (str(r.get("sessionyear")), hit)
            if key not in wanted:
                continue
            v = int(r.get("VersionID") or 0)
            kind = "intro" if v in _INTRODUCED else "senate" if v in _SENATE_AMENDED else None
            if kind and kind not in out[key]:
                t = version_title(r.get("text") or "", hit)
                if t:
                    out[key][kind] = t
    return out


_NEW_TITLE = re.compile(r"^\s*\((?:[\w ]*)New Title\s*\)", re.I)


def signins(tdb, narr_all, idx, site=Path("site"), root=Path("."), top=20, strict=True):
    """{term: [hearing]}: each term's `top` hearings by sign-ins, most first.

    A hearing is one bill on one House committee date in testimony_db.json, and
    its count is every support, oppose and neutral sign-in the House's online
    form recorded for it; a bill heard twice can appear twice. Each carries the
    title the bill had when it was heard (the printing dated on or before the
    hearing, else the one it was introduced with), the committee that heard it,
    and whether the sitting was a hearing on an amendment rather than the bill."""
    rows = {(r.get("term"), r.get("id")): r for r in idx}
    out, past = {}, set()
    for term, bills in tdb.items():
        if not re.fullmatch(r"\d{4}-\d{4}", str(term)):
            continue
        hs = [(bid, h) for bid, rec in (bills or {}).items() for h in (rec or {}).get("hearings") or []]
        hs.sort(key=lambda x: (-x[1]["total"], x[0], x[1]["date"]))
        sel = []
        for bid, h in hs[:top]:
            row = rows.get((term, bid)) or {}
            ev = ((narr_all.get(term) or {}).get(bid) or {}).get("events") or []
            year = str(row.get("year") or term[:4])
            title = _site_version_title(site, year, bid, h["date"])
            sel.append({"bill": bid, "year": year, "date": h["date"], "total": h["total"],
                        "support": h["support"], "oppose": h["oppose"], "neutral": h["neutral"],
                        "committee": _house_committee_after(ev, row, h["date"]),
                        "on": _amendment_hearing(ev, h["date"]),
                        "title": title, "title_now": row.get("title") or "",
                        "origin": next((e.get("body") for e in ev if e.get("type") == "introduced"),
                                       "S" if bid.startswith("S") else "H")})
            if title is None:
                past.add((term, bid))
        out[term] = sel
    # A bill with no printings on the site kept its title, unless the record
    # marks a new one -- an older term, whose printings the site does not
    # hold. Its title as heard comes from the General Court's own text.
    if past:
        bills_json = _load(Path(root) / "data" / "bills.json", {})
        retitled = {(t, b) for t, b in past
                    if _NEW_TITLE.match(((bills_json.get(t) or {}).get(b) or {}).get("title") or "")}
        want = {(x["year"], b) for t, b in retitled for x in out[t] if x["bill"] == b}
        want |= {(str(int(y) + d), b) for y, b in list(want) for d in (-1, 1)}
        found = _past_titles(root, want)
        for t, sel in out.items():
            for x in sel:
                if x["title"] is not None:
                    continue
                if (t, x["bill"]) not in retitled:
                    x["title"] = x["title_now"]
                    continue
                got = next((found[(y, x["bill"])] for y in (x["year"], t[:4], t[5:])
                            if found.get((y, x["bill"]))), {})
                x["title"] = (got.get("senate") if x["origin"] == "S" else None) or got.get("intro")
                if not x["title"]:
                    if strict:
                        raise SystemExit(f"learn_numbers.py: {x['bill']} of {t} was retitled after "
                                         "its hearing and no printing on this disk gives the title it "
                                         "was heard under (db/past/PastLegislationText.jsonl)")
                    x["title"] = x["title_now"]
    return out


def ballots(rows):
    """(shown, held, to come) out of ballot_results.json's rows.

    Shown: a constitutional amendment the voters decided whose row names
    where its count was read (`source`) and where it is printed (`cite`).
    Held: decided, and the row names no source or no cite -- left off the
    page, and named in the build's log (HELD), never in a sentence to the
    reader. To come: an election not yet held.

    Until 7 October 2026 a row was shown only where the Secretary of State's
    count (then the row's `sos`) equalled the row's own, which was
    Ballotpedia's, and two were held: CACR 7 of 1992 and CACR 41 of 2006,
    where Ballotpedia's No was 18 and 2 votes off. That day the person made
    the Secretary of State every decided row's source, corrected those two,
    and kept Ballotpedia's figures on each row as the cross-check, so the
    page shows all seventeen."""
    shown, held, to_come = [], [], []
    for r in rows or []:
        if r.get("yes") is None and r.get("no") is None:
            to_come.append(r)
            continue
        (shown if r.get("source") and r.get("cite") else held).append(r)
    key = lambda r: (r.get("election") or "", r.get("bill") or "")
    return sorted(shown, key=key), sorted(held, key=key), sorted(to_come, key=key)


def ratified(yes, no):
    """Two thirds of the votes cast on it (Part II, Article 100), in whole
    numbers so that exactly two thirds is two thirds."""
    return yes + no > 0 and 3 * yes >= 2 * (yes + no)


def vetoes(rows):
    """(reached the governor, vetoed, stood, overridden, still to be voted on)
    for one term's index rows. A veto stood when its override failed or no
    override vote came before the session ended; one still to be voted on
    is the chip's Vetoed, which only a session with days left can show."""
    st = Counter(r.get("status") for r in rows)
    pending = sum(st[s] for s in VETO_PENDING)
    live = sum(1 for r in rows if r.get("status") in VETO_PENDING and r.get("chip") == "Vetoed")
    over = st["Veto overridden, became law"]
    stood = st["Vetoed, override failed"] + pending - live
    vetoed = stood + over + live
    reached = st["Signed into law"] + st["Became law unsigned"] + vetoed
    return reached, vetoed, stood, over, live


# ---------------------------------------------------------------------------
# The page.
# ---------------------------------------------------------------------------

MISSING = []   # [(file, the section left out)] of the last body(); build_civics prints it
HELD = []      # [what was left off, and why] of the last body(); build_civics prints it

# Every section's heading, as body() writes it (the closest votes' ends in the
# term). preflight's data check holds the built page to the list, so a section
# left out for want of its input fails a full preflight run.
HEADINGS = ("Bills filed, and how they ended", "Bills filed and passed per member",
            "The bills each committee received", "The hearings with the most sign-ins",
            "How often the full chamber overrules its committee",
            "Consent calendars, by committee", "Each committee's passage rate",
            "Passed as introduced, or amended", "How many amendments a bill takes before it passes",
            "How the votes were taken", "The closest votes of", "Attendance on roll-call days",
            "Vetoes", "Constitutional amendments sent to the voters")


def _need(path, what):
    """The parsed file, or None with the file and its section on MISSING."""
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    MISSING.append((str(p), what))
    return None


def body(site=Path("site"), root=Path("."), strict=True):
    # Every bill's row, from the term files the pages read (site_read); it
    # stops where there is none rather than count nothing.
    idx = SR.bill_index_or_stop(site, "learn_numbers.py")
    root = Path(root)
    del MISSING[:]
    del HELD[:]
    narr_all = _need(root / "narratives.json", "every committee and floor figure") or {}
    rollcalls = _load(root / "rollcalls.json", {})
    YEAR.update({(r.get("term"), r.get("id")): str(r.get("year") or "") for r in idx})
    terms = sorted({r.get("term") for r in idx if r.get("term")})
    current = terms[-1] if terms else ""
    recent = terms[-10:]
    if strict and idx and not any("chip" in r for r in idx):
        raise SystemExit("learn_numbers.py: the bill index carries no chip; it was built before "
                         "build_site_v2.chip_word, so how each bill ended cannot be counted")
    # The page carried a "Draft" banner here saying it was unlinked and asking
    # search engines not to list it. Both of those stopped being true on 17
    # September, when the person read it and asked for it to be public, and a
    # banner that describes the page's old status is worse than none.
    #
    # What survives is the half of it that is still the point: every number
    # here is counted from the record at build time. That is what separates
    # this page from a statistics page somebody typed, and it is the first
    # thing a reader should know.
    out = ['<p class="caveat">Every number on this page is counted from the '
           'General Court\'s own record when the site is built, not typed in. '
           'Each section says what it counts and over what period. Where the '
           'record on this site cannot answer something, the section says so '
           'rather than estimating.</p>']
    narr = narr_all.get(current, {})

    # 1. Bills filed, and how they ended.
    oc = outcomes(idx)
    orows = []
    for t in terms:
        c = oc.get(t)
        if not c:
            continue
        n = c["filed"]
        orows.append([_t(t), f"{n:,}", _np(c["Became Law"], n), _np(c["Died"], n),
                      _np(c["Interim Study"], n), _np(c["other"], n)])
    # NOT THE CONSTITUTIONAL AMENDMENTS OR RESOLUTIONS, AND SAID SO (the survey of
    # 7 October 2026): 2,139 for 2025-2026 here and 2,243 bills and resolutions
    # on How a bill becomes law, and neither page said what it counted.
    out.append("<h2>Bills filed, and how they ended</h2><p>Every House and Senate bill "
               "given a number in each term, not counting constitutional amendments or "
               "resolutions, by the word its card on this site shows. "
               "Died covers a bill killed on the floor, left on the table, vetoed with the "
               "veto standing, lost between the two chambers, or still pending when its term "
               "ended; Other is a bill withdrawn, never introduced, or still before the "
               "legislature.</p>"
               + _table(["Term", "Bills filed", "Became Law", "Died", "Interim Study", "Other"],
                        orows))

    # 2. Bills filed and passed per member.
    pm = per_member(idx)
    prows = []
    for t in terms:
        h, s = pm[t]["H"], pm[t]["S"]
        if not (h[0] or s[0]):
            continue
        prows.append([_t(t), f"{h[0] / SEATS['H']:.2f}", f"{h[1] / SEATS['H']:.2f}",
                      f"{s[0] / SEATS['S']:.1f}", f"{s[1] / SEATS['S']:.1f}"])
    out.append("<h2>Bills filed and passed per member</h2><p>The House and Senate bills whose "
               "prime sponsor sat in each chamber, divided by its seats: 400 in the House, 24 "
               "in the Senate. Passed means the bill became law.</p>"
               + _table(["Term", "Filed per representative", "Became law per representative",
                         "Filed per senator", "Became law per senator"], prows))

    # 3. The bills each committee received.
    blocks = []
    for t in reversed(recent):
        rf = referrals(idx, narr_all.get(t, {}), t)
        rrows = sorted(([E(c), f"{f:,}", f"{s:,}" if s else ""] for c, (f, s) in rf.items() if f or s),
                       key=lambda r: (not r[0].startswith("House"),
                                      -int(r[1].replace(",", "")), r[0]))
        first_n = sum(f for f, _s in rf.values())
        sent_n = sum(s for _f, s in rf.values())
        blocks.append(f"<details{' open' if t == current else ''}><summary>{_t(t)}: "
                      f"{first_n:,} first referrals and {sent_n:,} sent on</summary>"
                      + _table(["Committee", "First referral", "Sent on from another committee"],
                               rrows) + "</details>")
    out.append("<h2>The bills each committee received</h2><p>For each committee of the last "
               "ten terms: how many bills its chamber sent it first, as each bill's page names "
               "its committee, and how many it received after another committee of the same "
               "chamber had them &mdash; most often Finance or Ways and Means, for a bill that "
               "spends or raises money. Every numbered measure counts, resolutions "
               "included.</p>" + "".join(blocks))

    # 4. The hearings with the most sign-ins.
    tdb = _need(root / "testimony_db.json", "the hearings with the most sign-ins")
    if tdb:
        # Twenty, and the paragraph says twenty.
        si = signins(tdb, narr_all, idx, site, root, top=20, strict=strict)
        allh = [h for t in si for h in si[t]]
        sided = [h for h in allh if h["support"] + h["oppose"]]
        lop = sum(1 for h in sided if 10 * max(h["support"], h["oppose"])
                  >= 9 * (h["support"] + h["oppose"]))
        against = sum(1 for h in allh if h["oppose"] > h["support"])
        since = min((h["date"] for t in tdb if isinstance(tdb[t], dict) for rec in tdb[t].values()
                     for h in (rec or {}).get("hearings") or []), default="")
        tables = []
        for t in sorted(si, reverse=True):
            # Five columns, the hearing's day and committee in one and the
            # three positions in one: eight ran past the Learn column's 560
            # pixels on a desktop, scrolled, and left the title 117 of them.
            srows = [[_bill_link(t, h["bill"], h["year"]), E(h["title"]),
                      _day(h["date"]) + (f", on {h['on']}" if h["on"] else "")
                      + (f"<br>{E(h['committee'])}" if h["committee"] else ""),
                      f"{h['total']:,}",
                      f"{h['support']:,}&nbsp;support<br>{h['oppose']:,}&nbsp;oppose"
                      + (f"<br>{h['neutral']:,}&nbsp;neutral" if h["neutral"] else "")]
                     for h in si[t]]
            tables.append(f"<h3>{_t(t)}</h3>" + _table(
                ["Bill", "Title as heard", "Hearing and committee", "Signed in", "Positions"],
                srows))
        out.append("<h2>The hearings with the most sign-ins</h2><p>Anyone may use the House's "
                   "online form to say they support or oppose a bill, or are neutral on it, at "
                   "its committee hearing. These are the twenty hearings with the most of those "
                   f"sign-ins in each term since the earliest on record, on {_day(since)}: one "
                   "bill on one House committee date, with the title it had when it was heard. "
                   "A sign-in is a position registered, not a vote and not a person counted: "
                   "one person may sign in on many bills, nobody is sampled, and an organised "
                   "appeal can bring thousands. The busiest hearings were seldom closely "
                   f"divided: {lop} of these {len(allh)} drew nine in ten sign-ins or more on "
                   f"one side, and {against} drew more against the bill than for it. So the "
                   "tables show where turnout was largest, not where opinion was split, and not "
                   "what the committee decided. Senate hearings are not on this form.</p>"
                   + "".join(tables))

    # 5. Committees overruled on the floor.
    st, cases = overturned(narr)
    label = {"PASS": "pass", "KILL": "kill", "STUDY": "interim study"}
    rows = []
    for ch in ("H", "S"):
        d, a, s = st.get(ch, (0, 0, 0))
        rows.append([NAME[ch], f"{d:,}", _np(a, d), _np(s, d)])
    out.append(f"<h2>How often the full chamber overrules its committee</h2>"
               f"<p>In the {_t(current)} term, a committee's recommendation "
               "was followed by the chamber far more often than not. Counted here: each bill's "
               "committee report in each chamber, against the first motion adopted on that "
               "chamber's floor that decided the bill there &mdash; ought to pass, inexpedient to "
               "legislate or indefinite postponement, or interim study.</p>"
               + _table(["Chamber", "Recommendations decided on the floor", "Decided otherwise",
                         "Passage and kill reversed"], rows))
    if cases:
        items = "".join(f"<li>{_bill_link(current, b)} &mdash; {NAME[c]}: committee "
                        f"{label[r]}, floor {label[f]}</li>" for b, c, r, f in sorted(cases)[:60])
        out.append(f"<details><summary>The {len(cases)} bills</summary><ul class=\"numlist\">"
                   f"{items}</ul></details>")

    # 6. Consent calendar share by committee, with the term's totals above it.
    rows_by = {r.get("id"): r for r in idx if r.get("term") == current}
    by_c, per_ch = consent(narr, rows_by, current)
    kept = sum(c["kept"] for c in per_ch.values())
    regular = sum(c["regular"] for c in per_ch.values())
    removed = sum(c["removed"] for c in per_ch.values())
    total = kept + regular + removed
    ccrows = sorted(([E(c), f"{n:,}", f"{k:,}", _pct(k, n)] for c, (n, k) in by_c.items() if n >= 10),
                    key=lambda r: -float(r[3].rstrip("%")) if r[3].endswith("%") else 0)
    out.append(f"<h2>Consent calendars, by committee</h2><p>A committee sends a report to the "
               "consent calendar by its own vote, and in both chambers that vote must be unanimous, "
               "though the recommendation itself may have been carried on a divided one. The "
               "whole calendar is adopted in one vote without debate, and what it adopts is each "
               "committee's recommendation, to pass the bill, to kill it, or to send it to interim "
               "study, unless the bill is first taken off &mdash; since January 2023 at the request "
               "of ten members in the House, and since April 2026 of two in the Senate. "
               f"For each committee of {_t(current)} with ten reports or more: the share that went "
               "on the consent calendar and stayed there &mdash; a measure of how often the "
               "committee agreed with itself. A report counts to the committee that made it, so a "
               "bill sent on to Finance or Ways and Means counts in both, and a report the docket "
               "prints twice counts once.</p>"
               f"<p>In {_t(current)}, <b>{kept:,} of {total:,}</b> committee recommendations "
               f"({_pct(kept, total)}) were adopted on the consent calendar, and "
               f"<b>{regular + removed:,}</b> went to the regular calendar, {removed:,} of them "
               "after being taken off consent.</p>"
               + _table(["Committee", "Reports", "On consent and kept there", "Share"], ccrows))

    # 7. Each committee's passage rate.
    cr, ctot = committee_rates(idx, narr, current)
    crrows = [[E(c), f"{n:,}", _np(p, n), _np(l, n)] for c, (n, p, l) in
              sorted(((c, v) for c, v in cr.items() if v[0] >= 10),
                     key=lambda x: (not x[0].startswith("House"), -x[1][1] / x[1][0], x[0]))]
    # "Bills", not "House bills": a House committee's count holds the Senate
    # bills it reported on after the Senate passed them (378 of 1,942 in
    # 2025-2026), and the paragraph above says why that matters.
    tot_line = "; ".join(f"of the {n:,} bills a {NAME[ch]} committee reported on, "
                         f"{_pct(p, n)} passed both chambers"
                         for ch, (n, p, _l) in ctot.items() if n)
    out.append(f"<h2>Each committee's passage rate</h2><p>Of the House and Senate bills a "
               f"committee reported on in {_t(current)}, whatever it recommended, the share that "
               "passed both chambers and the share that became law. A bill two committees of a "
               "chamber reported on counts in both; committees with ten bills or more. A Senate "
               "committee's House bills had already passed the House, and the other way round, "
               "so compare committees within a chamber rather than across.</p>"
               + (f"<p>In {_t(current)}, {tot_line}.</p>" if tot_line else "")
               + _table(["Committee", "Bills reported on", "Passed both chambers", "Became law"],
                        crrows))

    # 8 and 9. Passed as introduced, and the amendments it took.
    pa = passage(idx, narr_all)
    parows = []
    for t in terms:
        p = pa.get(t)
        if not p or not p["passed"]:
            continue
        n = p["passed"]
        parows.append([_t(t), f"{n:,}", _np(p["amended"], n), _np(n - p["amended"], n),
                       _np(p["conference"], n)])
    out.append("<h2>Passed as introduced, or amended</h2><p>Every House and Senate bill that "
               "passed both chambers in the same text and so went to the governor. Amended: "
               "either chamber adopted an amendment to it first, or a committee of conference "
               "settled the two chambers' versions; the Enrolled Bills Committee's technical "
               "corrections after passage are not counted as amendments.</p>"
               + _table(["Term", "Passed both chambers", "Amended", "As introduced",
                         "To a committee of conference"], parows))
    eras = [("1989-1998", lambda t: t < "1999"), ("1999-2006", lambda t: "1999" <= t < "2007"),
            ("2007-" + (current[5:] if current else ""), lambda t: t >= "2007")]
    drows = []
    for label_, inside in eras + [("All terms", lambda t: True)] + (
            [(current, lambda t: t == current)] if current else []):
        dist = Counter()
        for t, p in pa.items():
            if inside(t):
                dist.update(p["dist"])
        n = sum(dist.values())
        if n:
            drows.append([_t(label_), f"{n:,}"] + [_pct(dist[k], n) for k in range(4)]
                         + [_pct(sum(dist[k] for k in range(4, 7)), n)])
    out.append("<h2>How many amendments a bill takes before it passes</h2><p>The same bills, by "
               "the number of amendments the two chambers adopted to each before it went to the "
               "governor: an amendment withdrawn or defeated after its adoption does not count, "
               "nor does a committee of conference's report. From 2007 every adoption the docket "
               "records carries the amendment's number. Before 1999 it rarely does, and each "
               "amendment a line names counts once, so three or more is the figure there to read "
               "with care.</p>"
               + _table(["Terms", "Bills", "None", "One", "Two", "Three", "Four or more"], drows))

    # 10. How the votes were taken, by year.
    kinds = defaultdict(Counter)
    for t in recent:
        for rec in narr_all.get(t, {}).values():
            for e in rec.get("events") or []:
                if e.get("type") != "floor" or not (e.get("date") or "")[:4].isdigit():
                    continue
                vk = (e.get("vote_kind") or "").upper()
                raw = (e.get("raw") or "") + " " + (e.get("action") or "")
                if not vk:
                    vk = "RC" if re.search(r"\bRC\b", raw) else "DV" if re.search(r"\bDV\b|division", raw, re.I) \
                        else "VV" if re.search(r"\bVV\b", raw) else ""
                if vk in ("RC", "DV", "VV"):
                    kinds[e["date"][:4]][vk] += 1
    krows = []
    for y in sorted(kinds):
        c = kinds[y]
        n = sum(c.values())
        krows.append([y, f"{n:,}", _pct(c["RC"], n), _pct(c["DV"], n), _pct(c["VV"], n)])
    out.append("<h2>How the votes were taken</h2><p>Every recorded floor decision, by year and by "
               "how it was decided: a roll call records each member by name, a division records "
               "the count, and a voice vote records only which side sounded louder.</p>"
               + _table(["Year", "Floor decisions", "Roll call", "Division", "Voice"], krows))

    # 11. The closest roll calls of the current term.
    close = []
    for bid, rows_ in (rollcalls.get(current) or {}).items():
        for r in rows_ or []:
            y, n = r.get("yeas"), r.get("nays")
            if not isinstance(y, int) or not isinstance(n, int) or r.get("procedural"):
                continue
            if needs_more_than_majority(bid, r):
                continue
            if y + n < (100 if r.get("body") == "H" else 10):
                continue
            close.append((abs(y - n), bid, r))
    close.sort(key=lambda x: (x[0], x[1]))
    crow = [[_bill_link(current, b, str(r.get("year") or "")), NAME.get(r.get("body"), ""),
             E(r.get("question_plain") or r.get("question") or ""), f"{r['yeas']}&ndash;{r['nays']}",
             E(r.get("date") or "")] for _m, b, r in close[:10]]
    out.append(f"<h2>The closest votes of {_t(current)}</h2><p>The ten "
               "roll calls on bills decided by the fewest votes, procedural motions and votes "
               "that needed more than a majority left out.</p>"
               + _table(["Bill", "Chamber", "Question", "Yeas&ndash;nays", "Date"], crow))

    # 12. Attendance on roll-call days.
    votes = _need(root / "data" / "member_votes.json", "attendance on roll-call days")
    if votes:
        att = attendance(votes)
        arows = []
        for t in terms:
            h, s = att.get((t, "H")), att.get((t, "S"))
            if not (h or s):
                continue
            arows.append([_t(t)] + [x for v in (h, s) for x in
                                    ((f"{v[0]:,}", f"{100 * v[1]:.1f}%") if v else ("", ""))])
        out.append("<h2>Attendance on roll-call days</h2><p>For each day a chamber took at least "
                   "one roll call, the share of its members in office who were there for at "
                   "least one of that day's roll calls &mdash; voting, presiding, or declaring a "
                   "conflict of interest &mdash; averaged over the days. Members' ballots are on "
                   "record from 1999, and a day with only voice or division votes records no one "
                   "by name, so it cannot be counted.</p>"
                   + _table(["Term", "House roll-call days", "House attendance",
                             "Senate roll-call days", "Senate attendance"], arows))

    # 13. Vetoes, of the bills that reached the governor.
    vrows, waiting = [], 0
    for t in recent:
        reached, vetoed, stood, over, live = vetoes([r for r in idx if r.get("term") == t])
        waiting += live
        vrows.append([_t(t), f"{reached:,}", _np(vetoed, reached), str(stood),
                      str(over)])
    out.append("<h2>Vetoes</h2><p>Of the bills and joint resolutions that reached the governor in "
               "each of the last ten "
               "terms, how many were vetoed, and what became of the veto. A bill that became "
               "law without a signature reached the governor and was not vetoed. A veto stood "
               "when the override failed or no override vote came before the session ended."
               + (f" {waiting} veto{'es' if waiting != 1 else ''} of {_t(current)} "
                  f"{'are' if waiting != 1 else 'is'} still to be voted on, and counted as "
                  "vetoed only." if waiting else "") + "</p>"
               + _table(["Term", "Reached the governor", "Vetoed", "Veto stood", "Overridden"],
                        vrows))

    # 14. Constitutional amendments sent to the voters.
    ballot = _need(root / "ballot_results.json", "the amendments sent to the voters")
    if ballot:
        shown, held, to_come = ballots(ballot.get("rows"))
        # A DECIDED ROW WITH NO SOURCE OR NO CITE is left off and said here,
        # in the build's log, not to the reader.
        HELD.extend(f"{r.get('bill')} of {r.get('term')}: ballot_results.json gives it no "
                    + " and no ".join(k for k in ("source", "cite") if not r.get(k))
                    for r in held)
        brows = []
        for r in shown:
            y, n = r["yes"], r["no"]
            brows.append([f'{_bill_link(r["term"], r["bill"])}<br>{_t(r["term"])}', _day(r["election"]),
                          f"{y:,}", f"{n:,}", _pct(y, y + n),
                          "Ratified" if ratified(y, n) else "Not ratified",
                          f'<a href="{E(r["source"])}" rel="noopener">{E(r["cite"])}</a>'])
        rat = sum(1 for r in shown if ratified(r["yes"], r["no"]))
        # WHOSE COUNT, FROM THE ROWS (ballot_source.py): the Secretary of
        # State for every one since 7 October 2026, and said by the rows, so
        # that a row with another source makes the sentence say so.
        whose = Counter(BS.whose(r) for r in shown)
        if len(whose) == 1:
            said = (f"Yes and No are {next(iter(whose))} statewide count, printed where the "
                    "Source column says.")
        else:
            said = ("Yes and No are the statewide count printed where the Source column says: "
                    + ", ".join(f"{name} for {k}" for name, k in whose.most_common()) + ".")
        # An election still to come, in the tense the build's day gives it:
        # once the day has passed and the row has no count yet, the page says
        # the count is not here rather than that the vote is ahead.
        day = build_date.today().isoformat()
        coming = "".join(
            f" {_bill_link(r['term'], r['bill'])} of {_t(r['term'])} goes to the voters on "
            f"{_day(r['election'])}." if r["election"] >= day else
            f" {_bill_link(r['term'], r['bill'])} of {_t(r['term'])} went to the voters on "
            f"{_day(r['election'])}, and their count is not on this site yet." for r in to_come)
        out.append("<h2>Constitutional amendments sent to the voters</h2><p>A constitutional "
                   "amendment that passes both chambers by three fifths goes to the voters at the "
                   "next general election, and is ratified only with two thirds of the votes cast "
                   "on it (Part Second, Article 100); a blank ballot is not a vote cast on it. "
                   + said + f" {rat} of the {len(shown)} below were ratified." + coming + "</p>"
                   + _table(["Amendment", "Election", "Yes", "No", "Yes share", "Result",
                             "Source"], brows))
    return "".join(out)
