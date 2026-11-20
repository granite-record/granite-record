#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
What a bill's committees reported and who spoke at its hearings: the
committee reports the calendars printed, read beside the docket
(committee_reports), the interim study committees' statements as cards
(interim_cards), the sign-ins of a public hearing (hearing_testimony), and
the Senate's written hearing reports, their speakers matched to members and
each report placed on its hearing (speaker_index, hearing_report_for_page,
attach_hearing_reports).

    import hearing_reports as HR
    HR.committee_reports(recs, narr, sources, house_cmte, senate_cmte)   # the Reports tab's rows
    HR.interim_cards(reports, statements, narratives)
    HR.hearing_testimony(event, tdb, scraped)    # a hearing line's sign-in counts
    HR.attach_hearing_reports(stations, reports, bid, idx, name_part, tally, ...)

SECTIONS OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: committee and hearing reports). They
moved here as they stood, comments and all, in the file's order:
PUBLIC_HEARING, which only the sign-ins read, then from CAL_DATE, a
calendar's publication date, to attach_hearing_reports. It imports no
builder (_import_cycles_cut): a cited volume's address is parts.py's
(_source_url) and the study committee's report endings.py's
(interim_report). build_site_v2 imports every name here back under its own,
so build_site_v2.committee_reports and the rest answer as they did, for
build_bills, main and the checks.
"""

import re
from collections import defaultdict

import committee_names as CN
import senate_hearing_reports as SHR
# Where the recordings this site links begin (about_figures), which report_station splits on.
from about_figures import STREAM_START
# The study committee's report on a bill (endings.py), which interim_cards falls back on.
from endings import interim_report
# The journey's days (journey.py), a member's page address (members.py), and the docket line
# an event was read from and a cited volume's address (parts.py).
from journey import _j_days
from members import own_slug
from parts import _source_url, docket_line


# Sign-ins are filed for a public hearing, so the count belongs on that line.
PUBLIC_HEARING = re.compile(r"public hearing", re.I)


# A calendar's publication date, out of the filename the viewer link carries:
# "calendars%5C2026%5CNo10%20March%206%202026.pdf". Every one of the 24
# calendars a committee report cites resolves this way, so a report that the
# docket does not date can still be placed on the day it was printed.
# ONE SPACE OR MORE (the walk of 31 October 2026): 2018's House Calendar 39
# is "November%2009%20%202018", two before the year, and every interim report
# it printed had no date. A space as typed counts too (SOURCE_YEAR's second
# shape, "No10 March 6 2026.pdf").
CAL_DATE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October"
    r"|November|December)(?:%20| )+(\d{1,2})(?:%20| )+(\d{4})", re.I)
MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]
# "House Calendar 51, 2025" is how a report names the calendar it was printed
# in; "HC 51" is how the docket cites the same volume. One key for both.
REPORT_CAL = re.compile(r"House Calendar (\d+[A-Za-z]?)(?:,\s*(\d{4}))?", re.I)
# What the chamber did between one report and the next. These are the three
# ways a bill goes back to a committee that has already reported it, and one
# of them sits between the two reports on eight of the nine bills whose
# reports all come from a single committee -- which is the answer to "what
# does the second report mean". Interim study is deliberately not here: it
# ends a bill for the session rather than sending it back for another report.
REPORT_AGAIN = re.compile(r"recommit|re-?refer|retained in committee", re.I)


def rec_key(s):
    """A recommendation as the two sources agree on it.

    The docket writes "Ought to Pass with Amendment"; the Senate's own report
    writes "OUGHT TO PASS WITH AMENDMENT", and sometimes "IS INEXPEDIENT TO
    LEGISLATE" where the docket says "Inexpedient to Legislate". Stripping the
    leading verb, the case and the punctuation makes them one string -- the
    punctuation being what separates "Re-referred" from "rereferred". Measured
    on every Senate report the database holds: 1,443 of the 1,443 bills whose
    docket records a Senate report agree with the report's own wording, with
    no disagreements.
    """
    s = re.sub(r"^(?:is|be|has)\s+", "", (s or "").strip().lower())
    return re.sub(r"[^a-z ]", "", s).strip()


def _cal_key(source):
    """"House Calendar 51, 2025" as the docket writes it: ("HC 51", "2025")."""
    m = REPORT_CAL.search(source or "")
    return (f"HC {m.group(1)}", m.group(2) or "") if m else ("", "")


def _cal_date(url):
    """The day a calendar was published, from the filename in its link."""
    m = CAL_DATE.search(url or "")
    if not m:
        return ""
    return (f"{int(m.group(3)):04d}-{MONTHS.index(m.group(1).lower()) + 1:02d}"
            f"-{int(m.group(2)):02d}")


def _mdy(s):
    """The docket's 03/17/2026 as 2026-03-17."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", (s or "").strip())
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else ""


# THE DOCKET'S RECOMMENDATION, in the calendar's words, for a statement the
# calendar printed none for (2004's): interim_report's "rec", "not", "without".
INTERIM_WORDS = {"rec": "RECOMMENDED FOR FUTURE LEGISLATION",
                 "not": "NOT RECOMMENDED FOR FUTURE LEGISLATION",
                 "without": "WITHOUT RECOMMENDATION"}
INTERIM_SIDE = "Interim study report"
INTERIM_FROM_DOCKET = ("The calendar prints no recommendation for this one; the "
                       "recommendation shown is the House docket's.")


def _same_statement(r, s):
    """Whether committee_reports.json's record `r` is the interim study
    statement `s` mis-filed as a report: from the same calendar, and signed
    by the same member or opening on the same words. Every one of the 39 on
    29 October 2026's kit is; a report the calendar printed for the bill
    beside the statement would not be, and stays."""
    if r.get("source") != s.get("source"):
        return False
    lead = lambda x: re.sub(r"\W+", " ", x or "").strip().lower()[:80]
    return any((x.get("author") and x.get("author") == s.get("author"))
               or (lead(x.get("text")) and lead(x.get("text")) == lead(s.get("text")))
               for x in r.get("reports") or [])


def interim_cards(reports, statements, narratives):
    """Put each committee's INTERIM STUDY STATEMENT (interim_statements.py)
    on its bill's Reports tab, as a report of its own, in `reports` -- {term:
    {bill: [report]}}, committee_reports.json's shape -- and return the ones
    held back: [(term, bill, calendar, why)].

    The owner, 29 October 2026: what the committee said, the recommendation
    in plain words, the vote and the calendar, because it matters to anyone
    deciding whether to file the subject again. The docket's one-line
    "Interim Study Report" stays where it is.

    HELD BACK where the docket's own Interim Study Report line disagrees --
    the recommendation, or the vote, both being stated: the calendar and the
    docket are the Clerk's two records of one report, and a page showing one
    over the other would choose without saying so. Three on 29 October
    2026's kit, listed for the Clerk rather than shown.

    A statement the calendar prints no recommendation for (2004 prints none)
    takes the docket's and says so; neither, and it states none.

    The same calendar's report fetch_committee_reports.py mis-filed for the
    bill -- its split takes a statement for an ordinary report now and then,
    HB 1530 of 2024's RECOMMENDED FOR FUTURE LEGISLATION as one of "INTERIM
    STUDY" -- gives way to the statement, so neither shows twice; a report
    of the same calendar that is not the statement (_same_statement) stays."""
    held = []
    for term, byb in (statements or {}).items():
        for bid, sts in byb.items():
            narr = (narratives.get(term) or {}).get(bid)
            d = interim_report(narr, term) if narr else None
            for s in sts:
                why = []
                if d and s.get("rec") and d.get("rec") and s["rec"] != d["rec"]:
                    why.append(f"the calendar says {s.get('printed')}, the docket "
                               f"{INTERIM_WORDS.get(d['rec'], d['rec'])}")
                if d and d.get("vote") and s.get("vote_yeas") is not None and \
                        f"{s['vote_yeas']}–{s['vote_nays']}" != d["vote"]:
                    why.append(f"the calendar's vote is {s['vote_yeas']}-{s['vote_nays']}, "
                               f"the docket's {d['vote'].replace('–', '-')}")
                if why:
                    held.append((term, bid, s.get("source", ""), "; ".join(why)))
                    continue
                printed = s.get("printed") or ""
                from_docket = not printed and bool(d and d.get("rec"))
                if from_docket:
                    printed = INTERIM_WORDS.get(d["rec"], "")
                block = {"side": INTERIM_SIDE, "author": s.get("author", ""),
                         "committee": s.get("committee", ""), "text": s.get("text", "")}
                if s.get("vote_yeas") is not None:
                    block["vote_yeas"], block["vote_nays"] = s["vote_yeas"], s["vote_nays"]
                if from_docket:
                    block["note"] = INTERIM_FROM_DOCKET
                mine = [r for r in (reports.setdefault(term, {}).get(bid) or [])
                        if not _same_statement(r, s)]
                mine.append({"bill": bid, "title": s.get("title", ""), "body": "H",
                             "source": s.get("source", ""), "interim": True,
                             "majority_recommendation": printed or None,
                             "minority_recommendation": None, "reports": [block]})
                reports[term][bid] = mine
    return held


def committee_reports(recs, narr, sources, house_cmte, senate_cmte):
    """Every committee report on a bill, dated, in the order they were signed.

    Two sources hold different halves of this and neither is enough alone.

    The House Calendar prints why a committee decided as it did, signed by
    name, and that is the only place the reasoning exists. It says nothing
    about when, and a bill reported twice by one committee -- 9 of the 108
    with more than one report -- came out as two identical-looking blocks with
    no way to tell which was which, or that on HB104 they are one report
    printed in two calendars.

    The docket records that a committee reported, the day it signed, what it
    moved, by what vote, and the volume and page it was printed in. It has no
    prose. It also has the Senate: 1,708 reports the tab used to answer with
    "Senate reports use a different format and are not loaded yet". The format
    is one report, with a vote and no minority -- which is what the Senate
    does.

    So each written report is dated from the docket line citing the same
    calendar, or failing that from the day that calendar was published, and
    every report the docket has that no calendar printed is carried alongside
    it. The page says which of the two dates it is showing.
    """
    events = [e for e in (narr or {}).get("events", [])
              if e.get("type") == "report" and not e.get("cancelled")]
    # The date the committee signed, per calendar volume, from the docket.
    signed = {}
    for e in events:
        d = _mdy(e.get("report_date"))
        if e.get("cite") and d:
            signed.setdefault(e["cite"], d)

    # The Senate's reports come from the database, not from a House Calendar,
    # and carry their own printed date. Where the docket records the same
    # recommendation it has the day the committee SIGNED and the journal page
    # it was printed in, which are better than the day it was released -- so
    # those are taken, and that docket line is then not shown a second time
    # saying what the report above it already says.
    #
    # Keyed on the CHAMBER as well as the recommendation. On the wording alone
    # it matched the wrong chamber 364 times out of 1,446 -- both chambers say
    # "Ought to Pass" -- and gave a Senate report a House Calendar citation and
    # the day the House committee signed. A citation to the wrong document is
    # worse than none on a site whose whole claim is that it can be checked.
    by_rec, used = {}, set()
    for e in events:
        if e.get("recommendation"):
            by_rec.setdefault((e.get("body") or "",
                               rec_key(e["recommendation"])), []).append(e)

    out, seen_cal = [], set()
    for r in recs:
        key, year = _cal_key(r.get("source"))
        seen_cal.add(key)
        url = _source_url(sources, key, year)
        rr = dict(r)
        if signed.get(key):
            rr["date"], rr["dated"] = signed[key], "signed"
        elif _cal_date(url):
            rr["date"], rr["dated"] = _cal_date(url), "printed"
        elif r.get("date"):
            rr["date"], rr["dated"] = r["date"], r.get("dated") or "printed"
        else:
            rr["date"], rr["dated"] = "", ""
        rr["cite"] = key
        rr["cite_url"] = url
        if not key and r.get("date") and r.get("body"):
            match = next((e for e in
                          by_rec.get((r["body"],
                                      rec_key(r.get("majority_recommendation"))), [])
                          if id(e) not in used), None)
            if match:
                used.add(id(match))
                when = _mdy(match.get("report_date"))
                if when:
                    rr["date"], rr["dated"] = when, "signed"
                cite = match.get("cite", "")
                rr["cite"] = cite
                rr["cite_url"] = _source_url(sources, cite, rr["date"][:4])
        out.append(rr)
    out.sort(key=lambda x: x.get("date") or "9999")

    # Reports the docket has and no calendar printed. A House report reaches
    # this list when it was printed in a calendar this site has not read; a
    # Senate report always does, because the Senate prints no reasoning.
    docket = []
    for e in events:
        if id(e) in used:
            continue          # a written report above is this same report
        if e.get("cite") and e["cite"] in seen_cal:
            continue
        # A minority report carries no vote and no volume of its own; where the
        # calendar's version of it is already above, showing the docket's bare
        # line again says nothing new.
        if e.get("side") and any(x.get("side") == e["side"]
                                 for r in recs for x in (r.get("reports") or [])):
            continue
        # A HOUSE REPORT ROW THE CLERK ENTERED WITH NO CALENDAR CITED is the
        # calendar's written report of the same committee, recommendation and
        # vote, printed within sixty days after the day the row says it was
        # signed: "Committee Report: Inexpedient to Legislate 03/03/2025 (Vote
        # 18-0; CC)" on HB 125 of 2025 is House Calendar 15's report of 7
        # March, and was shown again below it saying its calendar had not been
        # read (the launch audit of 7 October 2026: 180 bills of 2025-2026).
        # Not SB 110 of 2025's Ways and Means report, 15-1 like Resources' a
        # month before it.
        signed_on = _mdy(e.get("report_date")) or e.get("date", "")
        if (e.get("body") == "H" and not e.get("cite") and signed_on
                and any((r.get("body") or "H") == "H" and r.get("date")
                        and 0 <= _j_days(r["date"][:10], signed_on[:10]) <= 60
                        and any(rec_key(r.get("minority_recommendation" if x.get("side") == "Minority"
                                              else "majority_recommendation"))
                                == rec_key(e.get("recommendation"))
                                and x.get("committee") == e.get("committee")
                                and str(x.get("vote_yeas")) == str(e.get("yeas"))
                                and str(x.get("vote_nays")) == str(e.get("nays"))
                                for x in (r.get("reports") or []))
                        for r in out)):
            continue
        docket.append({
            "date": _mdy(e.get("report_date")) or e.get("date", ""),
            "dated": "signed" if _mdy(e.get("report_date")) else "recorded",
            "body": e.get("body", ""),
            # The committee that reported, which narrative.py carries forward
            # from the referral line. The bill record holds only the committee
            # it is with now, so a report from an earlier one had no name.
            "committee": (e.get("committee")
                          or (senate_cmte if e.get("body") == "S" else house_cmte)),
            "side": e.get("side", ""),
            "recommendation": (e.get("recommendation") or "").upper(),
            "vote_yeas": int(e["yeas"]) if e.get("yeas") else None,
            "vote_nays": int(e["nays"]) if e.get("nays") else None,
            "amendment": e.get("amendment", ""),
            "new_title": bool(e.get("new_title")),
            "cite": e.get("cite", ""),
            "cite_url": _source_url(sources, e.get("cite", ""),
                                    (e.get("date") or "")[:4]),
        })
    docket.sort(key=lambda x: x.get("date") or "9999")

    # Why there is a second report. Taken from the docket between one report
    # and the next, so it is the chamber's own record of what it did rather
    # than an inference from the two reports looking different.
    dates = sorted(x["date"] for x in out + docket if x.get("date"))
    between = []
    for a, z in zip(dates, dates[1:]):
        # Strictly before the later report: an action on the same day
        # is the floor acting on that report, not the reason for it.
        # The docket's lines, each whole and once (docket_line): the note
        # quotes a line. Read by the clause, HB 278 of 1999's "Comm Am, AA
        # VV; Rep Soltani moved to recommit, ML VV; Passed with Am and ref to
        # Finance VV" gave the failed motion alone as what the docket records
        # between its two reports.
        again = [e for e in (narr or {}).get("events", [])
                 if not e.get("cancelled") and not e.get("in_line")
                 and e.get("type") != "report"
                 and a < (e.get("date") or "") < z and REPORT_AGAIN.search(docket_line(e))]
        # THE ONE THAT SENT IT BACK, not the first that names it: HB 75 of
        # 1999 quoted "Sen. Russman moved Rerefer, Sen. Russman Withdrew
        # Motion to Rerefer" over "Sen D'Allesandro Moved Rerefer, MA, VV",
        # which carried. A motion that failed, was withdrawn or was not voted
        # on is quoted only where nothing else between the reports is.
        e = (next((e for e in again if _again_carried(docket_line(e))), None)
             or next((e for e in again if _again_carried(docket_line(e)) is None), None)
             or (again[0] if again else None))
        if e:
            between.append({"before": z, "date": e["date"], "text": docket_line(e)})
    return out, docket, between


def _again_carried(raw):
    """True where a line sending a bill back to committee records it carried,
    False where it records it failed, was withdrawn or was not voted on, None
    where it says neither."""
    raw = raw or ""
    m = REPORT_AGAIN.search(raw)
    rest = raw[m.start():] if m else raw
    # AND NO FURTHER THAN A FAILED MOTION TO RECONSIDER IT. "Re-Referred to
    # Res, Rec & Dev committee RC(158-154); Rep Royce moved to reconsider, ML
    # RC(156-157)" (SB 135 of 1999, one line since the 1999-2006 reader joins
    # the two rows the database cut it into) is the bill sent back and a
    # motion to undo that which failed, the reading _j_segments gives it too.
    # Read to the end, the ML was the re-referral's, and the Reports tab gave
    # a cancelled subcommittee session as the reason for the second report.
    # A reconsideration that carried is left where it was.
    again = LOST_RECONSIDER.search(rest) if m else None
    if again:
        rest = rest[:again.start()]
        raw = raw[:m.start() + again.start()]
    # Withdrawn or not voted on in the clause that sends it back, not in one
    # before it: "Ought to Pass [not voted on]; Sen. Prescott Moved Recommit,
    # MA, VV" (SB 10 of 2001) and "REP FLANAGAN WITHDREW OTP/AM MOTION;
    # RE-REFERRED TO CON & STAT" (HB 303 of 1991) are recommittals that
    # carried. "REP BUCKLEY WITHDREW RECOMMIT MOTION" is still withdrawn.
    clause = raw[raw.rfind(";", 0, m.start()) + 1:] if m else raw
    if re.search(r"withdr[ae]w|not\s+voted\s+on", clause, re.I):
        return False
    if re.search(r"\b(?:MF|ML)\b|\bfail|\blost\b", rest):
        return False
    # The past tense is the outcome only where no one is said to have moved
    # it: "Sen. Kelly moved to Rereferred to Committee" (HB 450 of 2009) is
    # the motion, and its "MA, VV" is the next line.
    if re.search(r"\bMA\b|\badopted\b|\bcarried\b", rest, re.I) or (
            re.search(r"\b(?:re-?referred|recommitted|retained)\b", raw, re.I)
            and not re.search(r"\bmov(?:ed|es?)\b", raw, re.I)):
        return True
    return None


# A later clause of the line moving to reconsider, which failed.
LOST_RECONSIDER = re.compile(r";[^;]*\b(?i:reconsider)[^;]*\b(?:ML|MF)\b")


def hearing_testimony(e, tdb, scraped):
    """Who signed in for and against, on the hearing this line records.

    The database carries the hearing DATE with each sign-in, so the count sits
    with the hearing it belongs to rather than as one number for the whole
    bill -- which is the point of it: a hearing next week, and where opinion
    stands today. 2,072 of the 2,122 docket hearing lines match a date the
    database also has.

    Counts only. The table has names, towns and the written testimony, and
    almost every one of the 400,000 rows is a private individual who signed a
    committee's sheet; fetch_testimony_db does not ask for any of it.
    """
    if not PUBLIC_HEARING.search(e.get("raw", "")):
        return {}
    if tdb:
        hit = next((h for h in tdb.get("hearings", [])
                    if h.get("date") == e.get("date")), None)
        if hit:
            return {"testimony": {**hit, "dated": True}}
        # The database has the bill but not this date. Its whole-bill total is
        # still true of the bill; it is just not true of this hearing alone,
        # and the page has to say which it is showing.
        return {"testimony": {k: tdb[k] for k in
                              ("total", "support", "oppose", "neutral")}}
    return {"testimony": scraped} if scraped else {}


# THE SENATE'S OWN HEARING REPORTS, on the hearing they report.
#
# senate_hearing_reports.py reads them out of the database dump; this puts
# each on the Senate public-hearing station of the same bill and the same
# date, and resolves the legislators who testified to the member they are, so
# the page can draw them with the chip everybody else on the site is drawn
# with. Everyone else -- members of the public, officials, lobbyists -- is
# printed as the report names them. The person decided on 24 September that
# the reports are shown as the Senate published them, names and all; the
# sign-in system's names stay out, which is hearing_testimony's rule above
# and a different source.
SPEAKER_TITLE = re.compile(
    r"^(?P<t>Senators?|Sen\.|Representatives?\.?|Reps?\.)\s+(?P<n>.+)$")


def speaker_index(people):
    """{(chamber, surname): [member, ...]} over the sitting and the departed.

    A surname here is everything after the first name, lower-cased, so
    "Perkins Kwoka" and "Sabourin dit Choiniere" index whole.
    """
    idx = defaultdict(list)
    for m in people:
        ch = str(m.get("chamber") or "")[:1].upper()
        last = str(m.get("last") or "").strip()
        first = str(m.get("first") or "").strip()
        if not last and "," in str(m.get("name") or ""):
            last, first = [x.strip() for x in m["name"].split(",", 1)]
        if ch and last:
            idx[(ch, last.lower().replace("’", "'"))].append(
                {**m, "_first": first.lower()})
    return idx


def resolve_speaker(heading, idx, name_part):
    """The member a report's speaker line names, or None.

    Only a line that opens with the chamber's own title -- "Senator Gannon",
    "Rep. Alvin See" -- is tried, and only in that chamber. The surname must
    name exactly one member of it, or name several and the first name settle
    which; a first name that disagrees with the only candidate, and every
    doubt besides, leaves the speaker as the plain text the report printed.
    A wrong member in a chip is a factual error; a missing chip is not.
    """
    m = SPEAKER_TITLE.match(name_part(heading) or "")
    if not m:
        return None
    # "Representatives Barbara Comtois (Belk. 7) and Peters Bixby (Straf. 13)"
    # heads two people's points; a chip would give them to the first.
    if m.group("t").lower().rstrip(".") in ("senators", "representatives"):
        return None
    ch = "S" if m.group("t").lower().startswith("sen") else "H"
    # The report's apostrophe is a typesetter's and the roster's is not:
    # "Prudhomme-O’Brien" and "Prudhomme-O'Brien" are one member.
    words = m.group("n").replace("’", "'").split()
    # A House member's seat run on -- "Rep. David Fracht-Grafton 16" -- and
    # a generational suffix, "Henry Giasson III", are not the surname.
    while len(words) > 1 and (words[-1].isdigit() or re.fullmatch(
            r"(?:Jr|Sr|II|III|IV)\.?", words[-1])):
        words.pop()
    if not words:
        return None
    for cut in range(len(words)):
        first = words[0].lower() if cut else ""
        cands = idx.get((ch, " ".join(words[cut:]).lower()), [])
        if not cands:
            continue
        if first:
            exact = [c for c in cands if c["_first"] == first]
            if len(exact) == 1:
                return exact[0]
            if len(cands) == 1 and cands[0]["_first"][:1] == first[:1]:
                # "Dan Innis" for Daniel, "Pat Long" for Patrick.
                return cands[0]
            return None
        return cands[0] if len(cands) == 1 else None
    return None


def hearing_report_for_page(rec, idx, name_part, pages=None):
    """One parsed report as the Hearings tab draws it, legislators resolved.

    Returns (report, members resolved, legislator lines left as text).
    `pages` is attach_hearing_reports': the party is the member's as `idx`
    holds them, which for a term whose own roster is frozen is the party
    they sat with; the link is to their own page, wherever it is now.
    """
    got = miss = 0
    secs = []
    for s in rec.get("sections", []):
        o = {k: v for k, v in s.items() if k != "speakers"}
        if "speakers" in s:
            o["speakers"] = []
            for sp in s["speakers"]:
                sp = dict(sp)
                mem = resolve_speaker(sp.get("who", ""), idx, name_part)
                if mem:
                    got += 1
                    # The report's own words for the person, in the chip the
                    # site draws a legislator with: the party colour and the
                    # link are the site's; the name is the Senate's.
                    _page = mem if pages is None else pages.get(str(mem.get("id")))
                    sp["member"] = {"label": name_part(sp["who"]),
                                    "party_code": mem.get("party_code") or "",
                                    "slug": own_slug(_page) if _page else ""}
                elif SPEAKER_TITLE.match(name_part(sp.get("who", "")) or ""):
                    miss += 1
                o["speakers"].append(sp)
        secs.append(o)
    # `fallback` is the parser's diagnosis of why a report stayed as text,
    # snippets and all; the page reads a section's `text` instead, and the
    # reasons are for senate_hearing_reports.py --fallbacks, not the reader.
    out = {k: v for k, v in rec.items()
           if k not in ("sections", "filed", "bill", "subject", "fallback")}
    # What was heard, only where it is not the bill itself: the page is the
    # bill's, and its title is already at the top of it. An amendment heard
    # on its own is named, because that is what the report is about.
    if SHR.AMEND_LINE.match(rec.get("subject") or ""):
        out["subject"] = rec["subject"]
    out["sections"] = secs
    return out, got, miss


def report_station(rep, docket_dates):
    """The station a hearing report stands on when the docket has no Senate
    hearing of the bill on the date the report gives.

    UNDER THE REPORT'S OWN DATE. 20 of the 1,293 reports of 24 September give
    a hearing date the docket does not: most a few days after the docket's
    hearing of the same bill -- SB 42 heard on 21 January 2025 by the docket
    and on the 23rd by its report -- and three, HB 183, HB 268 and HB 435, for
    bills the docket gives no Senate hearing at all. They were left off the
    page. The person decided on 24 September that they are shown, dated as
    the Senate committee dated them, and neither date is corrected to the
    other: this site cannot say which is right. The station says it is dated
    by the report, and names the docket's own hearing dates where it has any,
    so a reader sees both. Nothing is matched to it, so it offers no
    recording.
    """
    # "Senate Judiciary Committee" as the docket's rows name it, "Judiciary",
    # so the station's title reads like the other Senate hearings'.
    cmte = re.sub(r"^\s*Senate\s+|\s+Committee\s*$", "",
                  rep.get("committee") or "", flags=re.I).strip()
    heard = rep.get("heard") or ""
    y = int(heard[:4]) if heard[:4].isdigit() else 0
    term = f"{y - 1 + y % 2}-{y + y % 2}" if y else ""
    return {
        "when": heard, "time": None, "what": "hearing",
        "committee": CN.official(cmte, "S", term) if cmte else None,
        "body": "S", "venue": None, "video_id": "", "watch": None,
        "predicted": None, "start": None,
        "state": "prestream" if heard < STREAM_START else "novideo",
        "candidate": None,
        # What the page reads to say where the date came from.
        "dated_by": "report",
        "docket_heard": sorted(docket_dates),
    }


def attach_hearing_reports(stations, reports, bid, idx, name_part, tally,
                           unmatched, pages=None):
    """Each report onto the station of the hearing it reports.

    That is the bill's Senate public hearing on the date the report gives --
    the station the Hearings tab draws with the recording. A list on the
    station, because a committee can hear a bill and then an amendment to it
    the same afternoon and file a report of each. A report whose date the
    docket has no Senate hearing for is not pinned to some other sitting: it
    is counted and named in `unmatched`, and stands on a station of its own
    under the date it gives (report_station).

    `pages` is {id: member} of whose page a member resolved in `idx` links
    to, where `idx` is a term's own frozen roster (build_bills says when).
    """
    heard = [s for s in stations
             if s.get("body") == "S"
             and "hearing" in (s.get("what") or "").lower()]
    docket = {s.get("when") for s in heard}
    own = {}
    for rep in reports:
        at = next((s for s in heard if s.get("when") == rep.get("heard")), None)
        if at is None:
            tally["unmatched"] += 1
            unmatched.append(f"{bid} {rep.get('heard')}")
            # One station for the date, which a bill's report and its
            # amendment's, filed the same afternoon, share.
            at = own.get(rep.get("heard"))
            if at is None:
                at = own[rep.get("heard")] = report_station(rep, docket)
                stations.append(at)
        else:
            tally["matched"] += 1
        page, got, miss = hearing_report_for_page(rep, idx, name_part, pages)
        at.setdefault("reports", []).append(page)
        tally["members"] += got
        tally["members_unresolved"] += miss
        tally["plain"] += bool(rep.get("fallback"))
