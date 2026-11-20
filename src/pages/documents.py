#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
What a bill's page cites and lists of its record: each cited docket line
with its plain words (_with_plain) and the journal or calendar it is printed
in, as a link (_cite); everything a reader can open for themselves, deduped
on the address (bill_documents, bill_text_url); what the page says of a
bill whose record is the House Journal's (journal_story,
journal_decided_story); and the notes on where a record comes from
(record_notes, PAST_SOURCE, DOCKET_SOURCE, ROW_NAMES_ANOTHER).

    import documents as DOC
    DOC.bill_documents(b, bid, st, narr, sources, rep_written, rep_docket)   # (docs, text_url)
    DOC.journal_story(b, jkeys)   # {intro, steps, dates, stages, notes, docs}

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited, in two
pieces in the file's order: _with_plain and _cite; bill_documents to
bill_text_url. A cited volume's address is parts.py's (_source_url), a
journal's queue_links.py's, the plain words plain_action.py's and the
journey's marks journey.py's. It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import re

import names
import narrative as N
import past_sponsors as PSP
import plain_action as PA
import shell as _shell
from journey import J_MARK, _j_words
from parts import _source_url
from queue_links import journal_url
from status import DISPOSED, JOURNAL_SOURCE


def _with_plain(events, bill):
    """Each cited docket line with its plain words beside it (plain_action.py),
    which the Documents tab prints first and the clerk's line under them (the
    person's choice A, 14 October 2026). Only a line with a citation: those
    are the Documents tab's rows, and the rest would only make the page
    heavier.

    Each is read with the docket line after it, in the list's order: HB 2023
    of 2022's "Introduced and Adopted: MA DV 259-66" is its introduction
    because "Ought to Pass" follows it, and HB 1703 of 2016's, with nothing
    after it, its passage too (plain_action._introduced, 16 October 2026)."""
    lines = [ev.get("text") or "" for ev in events]
    for i, ev in enumerate(events):
        if ev.get("cite"):
            words = PA.plain(lines[i], bill, next_line=lines[i + 1] if i + 1 < len(lines) else "")
            if words:
                ev["plain"] = words
    return events


def _cite(ev, sources, year=""):
    """The journal or calendar one docket action is printed in, as a link.

    A docket line cites "HJ 7" with no year, because within one session there
    is only one. Across sessions there is one per year, so the lookup is tried
    with the year first.

    It then used to fall back to the bare key, and that was wrong. calendars.json
    and journals.json each hold both forms -- "HC 10" beside "HC 10 2025" and
    "HC 10 2026" -- because their fetchers write the bare key too, and the bare
    key holds whichever year was fetched last. So a 2025 action citing HJ 3
    resolved to the 2026 journal: 4,468 of 12,970 links, a third of them,
    pointing at a volume that does not contain the action they claim to record.
    SR1 cited SJ 1 on a 2024 action and opened the 2026 Senate Journal.

    A missing citation is a gap. A citation to the wrong document is a false
    one, on a site whose whole claim is that it can be checked -- so the year in
    the resolved link is compared with the year of the action, and a link that
    disagrees is not offered at all. The citation itself is still printed; only
    the link is withheld.

    The citation is read off the event, not searched for in the line. The line
    has already been through narrative.clean(), which removes the citation so
    that the hearing pattern's venue group does not swallow "SC 4" -- so a
    search of it found nothing, on every event of every bill. narrative.py
    takes the citation off the raw line and carries it on the event.
    """
    # `year` is the year of the action's date -- or, where narrative.py dated
    # a row by the day it states in another year than it was entered, the
    # year it was entered (the event's "cite_year"): a notice of December
    # for a hearing in January cites December's calendar.
    key = (ev.get("cite") or "").strip()
    if not key:
        return {}
    page = (ev.get("cite_page") or "").strip()
    out = {"cite": key + (f", page {page}" if page else "")}
    url = _source_url(sources, key, year)
    if url:
        out["cite_url"] = url
    return out


def bill_documents(b, bid, st, narr, sources, rep_written, rep_docket):
    """Everything a reader can open for themselves, deduped on the URL.

    add_doc was defined once per bill inside a 465-line body; it is a
    nested helper of a 60-line function now, which is what a closure
    that small should be.

    Its third parameter is named `sort` rather than `kind`, so that no
    binding called `kind` exists in this scope at all. `kind` means the
    bill's status kind in the caller, and the last thing this refactor
    should do is create a fresh instance of the shadowing it is here
    to remove.

    Returns (docs, text_url): the text URL is built here and the caller
    needs it for the payload as well.
    """
    docs, seen_doc = [], set()

    def add_doc(label, url, sort):
        if url and url not in seen_doc:
            seen_doc.add(url)
            docs.append({"label": label, "url": url, "kind": sort})

    text_url = bill_text_url(b, st)
    add_doc("Bill text", text_url, "text")
    # NOT FOR A JOURNAL RECORD. Both addresses are built from the LSR, which a
    # bill read off the House Journal does not have (add_journal_bills says
    # why none is invented). Whether the General Court's own pages have the
    # bill is not known here: its data files do not, and no page was asked.
    if not b.get("journal"):
        add_doc("Bill status page", (
            "https://gc.nh.gov/bill_status/legacy/bs2016/Bill_status.aspx"
            f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
            f"&txtsessionyear={b.get('lsr_year','')}"
            f"&txtbillnumber={bid.lower()}&sortoption=billnumber"), "status")
        add_doc("Docket", (
            "https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
            f"?lsr={b.get('lsr_num','')}&sy={b.get('lsr_year','')}"
            f"&txtsessionyear={b.get('lsr_year','')}"
            f"&txtbillnumber={bid.lower()}&sortoption=billnumber"), "docket")
    # The journals and calendars the docket itself cites. These are the
    # official record of the individual actions, which is a stronger thing
    # to link than a summary of them.
    # One entry per volume, naming every page of it this bill is on.
    # add_doc dedupes on the URL, and a volume has one URL however many
    # pages are cited -- so listing them per event kept whichever page came
    # first and dropped the rest without a word. 565 of the 7,013 volumes
    # cited on this site carry a bill on more than one page; HB686 is on
    # HJ 7 at both 143 and 144, and the list named only 143.
    vols = {}
    for e in (narr or {}).get("events", []):
        # Not a row the docket cancelled. A notice a later row cancelled or
        # moved (narrative.overtaken) is carried as cancelled so that nothing
        # reads it as a sitting, but the calendar it cites printed the bill:
        # Senate Calendar 1A of 2006 printed SB 339's hearing of 19 January,
        # and the Documents tabs of 59 bills lost 62 calendars like it when
        # those notices stopped being told as held (decision 56). And so does
        # every other notice the history no longer tells -- one set for after
        # the bill was withdrawn, or after the chamber took the measure from
        # its committee (decision 59e) -- since its calendar printed the bill.
        if e.get("cancelled") and not (e.get("overtaken") or e.get("notice")):
            continue
        c = _cite(e, sources, e.get("cite_year") or (e.get("date") or "")[:4])
        if not c.get("cite_url"):
            continue
        key = (e.get("cite") or "").strip()
        v = vols.setdefault(key, {"url": c["cite_url"], "pages": []})
        pg = (e.get("cite_page") or "").strip()
        if pg and pg not in v["pages"]:
            v["pages"].append(pg)
    for key, v in vols.items():
        pages = sorted(v["pages"], key=lambda x: int(x))
        label = key + ("" if not pages else
                       f", page {pages[0]}" if len(pages) == 1 else
                       ", pages " + ", ".join(pages[:-1]) + " and " + pages[-1])
        add_doc(label, v["url"], "record")
    # The calendar a committee report was printed in.
    # committee_reports() has already turned each report's calendar into
    # a key and a URL, so this cites what the report itself is citing
    # rather than parsing "House Calendar 51, 2025" a second time.
    # THE LABEL SAYS WHAT IT IS FIRST, AND THE YEAR IN BRACKETS (the cohesion
    # audit's P-12, 6 November 2026): "House Calendar 12, 2026, committee
    # report" read as a date, December 2026. The citation is the General
    # Court's own and is not changed where it is shown as one, on the Reports
    # tab; only this list's label is.
    def report_label(cite):
        return "Committee report, " + re.sub(r",\s*((?:19|20)\d\d)\s*$", r" (\1)", cite or "")
    for r in rep_written:
        add_doc(report_label(r.get('source') or r.get('cite')),
                r.get("cite_url", ""), "report")
    for r in rep_docket:
        if r.get("cite_url"):
            add_doc(report_label(r['cite']), r["cite_url"], "report")
    return docs, text_url


def _long_day(iso):
    """"2025-02-06" -> "February 6, 2025", as the narratives write a day:
    shell.date_words."""
    return _shell.date_words(str(iso or ""), "full")


def journal_story(b, jkeys):
    """What the page says of a bill whose record is the House Journal's:
    {intro, steps, dates, stages, notes, docs}.

    The bill is in none of the General Court's current files, so there is no
    docket to narrate and none is invented: no docket row, no status-page
    field, nothing presented as the General Court's own words. What is said
    is what the journal prints -- the day the bill was introduced and the
    committee it went to, and the day it was withdrawn and how -- in this
    site's words, with the journal cited for each, and one note saying where
    the record comes from. It says nothing about why the General Court's
    files lack the bill, which nothing on disk states.

    The rail and On the record read `steps` the way they read journey()'s:
    one House decision, drawn as the stop where the bill ended.
    """
    j = b.get("journal") or {}
    i, w = j.get("introduced") or {}, j.get("withdrawn") or {}
    if j.get("decided") and not w:
        return journal_decided_story(b, jkeys)
    committee = names.committee(b.get("house_committee") or "")
    vote, _, kind = (w.get("vote") or "").partition(", ")
    if not re.search(r"\d", vote):
        vote, kind = "", vote
    tally = vote.replace("-", "–")
    how = {"division": "on a division vote", "roll call": "on a roll call",
           "voice vote": "on a voice vote"}.get(kind, "")
    if w.get("how") == "consent calendar":
        step = "Withdrawn on the consent calendar"
        said = (f"On {_long_day(w.get('date'))} the House adopted its consent "
                "calendar, which listed the bill to be withdrawn.")
    else:
        step = "Withdrawn" + (f", {tally}" if tally else f" {how}" if how else "")
        said = (f"On {_long_day(w.get('date'))} the House voted to withdraw it"
                + (f" {how}" if how else "") + (f", {tally}" if tally else "") + ".")
        recon, _, rv = (w.get("reconsideration") or "").partition(", ")
        if recon:
            said += (f" A motion to reconsider {recon}"
                     + (f", {rv.replace('-', chr(0x2013))}" if rv else "") + ".")
    stages = [
        {"label": "House Committee" + (f" ({committee})" if committee else ""),
         "hand": "H:committee", "notes": [],
         "text": (f"It was introduced on {_long_day(i.get('date'))}"
                  + (f" and referred to the House {committee} committee." if committee
                     else "."))},
        {"label": "On the House Floor", "hand": "H:floor", "notes": [], "text": said},
    ]

    def where(c):
        return (f"{c.get('journal')}, {_long_day(c.get('date'))}, page {c.get('page')}"
                if c else "")
    # ONLY WHAT WAS LOOKED AT. The bulk files and the database view were read
    # (journal_bills.py says which) and the bill is in none of them; no
    # status page was ever asked for, so the note does not speak for one.
    notes = [("The data files the General Court publishes for this term, its "
              "docket among them, do not list this bill. This record is the "
              f"House Journal's, which prints its introduction ({where(i)}) and "
              f"its withdrawal ({where(w)}).")]
    vols = {}
    for c in (i, w):
        url = journal_url(c.get("date", ""), c.get("journal", ""), jkeys) if c else ""
        if url:
            v = vols.setdefault(c["journal"], {"url": url, "pages": []})
            if str(c.get("page")) not in v["pages"]:
                v["pages"].append(str(c.get("page")))
    docs = [(f"{k}, page{'s' if len(v['pages']) > 1 else ''} {' and '.join(v['pages'])}",
             v["url"]) for k, v in vols.items()]
    return {"intro": i.get("date", ""),
            "steps": [{"date": w.get("date", ""), "body": "H", "act": "withdrawn",
                       "mark": "x", "text": step, "short": "withdrawn"}] if w else [],
            "dates": sorted(d for d in (i.get("date"), w.get("date")) if d),
            "stages": stages, "notes": notes, "docs": docs}


# What the House Journal's question on a committee report becomes as a line
# of the journey, by the status DISPOSED gives it.
J_DECIDED_ACT = {"Killed": "killed", "Indefinitely postponed": "postponed",
                 "Referred for interim study": "study"}


def journal_decided_story(b, jkeys):
    """journal_story for the bill whose journal record is the House's vote on
    its committee's report rather than a withdrawal (journal_bills.EARLIER:
    HB 459 of 2021), told only where its docket is not on this machine --
    with the docket narrated, the page is the docket's like any other bill's.

    The same shape and the same restraint: the day it was introduced and the
    committee it went to, the day the House voted and the count, each in this
    site's words with the journal cited, and one note of where the record
    comes from. The floor sentence is narrative.py's for the docket's own row
    of the vote, "Inexpedient to Legislate: MA RC 198-153", so the two builds
    read alike.
    """
    j = b.get("journal") or {}
    i, d = j.get("introduced") or {}, j.get("decided") or {}
    committee = names.committee(b.get("house_committee") or "")
    what = d.get("question") or ""
    hit = next((res for pat, res in DISPOSED if pat.search(what)), None)
    act = J_DECIDED_ACT.get(hit[1] if hit else "", "")
    y, _, n = (d.get("vote") or "").partition("-")
    counted = y.strip().isdigit() and n.strip().isdigit()
    tally = f"{int(y)}–{int(n)}" if counted else ""
    verb = N.RECOMMENDATION.get(what.strip().lower())
    said = (f"On {_long_day(d.get('date'))} the House "
            + (f"voted to {verb}" if verb else f"adopted “{what}”")
            + (f" on a {d['how']}" if d.get("how") else "")
            + (f" {tally}" if tally else "") + ".")
    stages = [
        {"label": "House Committee" + (f" ({committee})" if committee else ""),
         "hand": "H:committee", "notes": [],
         "text": (f"It was introduced on {_long_day(i.get('date'))}"
                  + (f" and referred to the House {committee} committee." if committee
                     else "."))},
        {"label": "On the House Floor", "hand": "H:floor", "notes": [], "text": said},
    ]

    def where(c):
        return (f"{c.get('journal')}, {_long_day(c.get('date'))}, page {c.get('page')}"
                if c else "")
    # ONLY WHAT WAS LOOKED AT: the list the bill search gave for the term and
    # the database's table of past bills, neither of which has it.
    notes = [("This bill is not in the list the General Court's bill search gave "
              "for the term, and its database's table of past bills has no row for "
              "it. This record is the House Journal's, which prints its "
              f"introduction ({where(i)}) and the vote on its committee's report "
              f"({where(d)}).")]
    vols = {}
    for c in (i, d):
        url = journal_url(c.get("date", ""), c.get("journal", ""), jkeys) if c else ""
        if url:
            v = vols.setdefault(c["journal"], {"url": url, "pages": []})
            if str(c.get("page")) not in v["pages"]:
                v["pages"].append(str(c.get("page")))
    docs = [(f"{k}, page{'s' if len(v['pages']) > 1 else ''} {' and '.join(v['pages'])}",
             v["url"]) for k, v in vols.items()]
    steps = []
    if act and d:
        st = {"date": d.get("date", ""), "body": "H", "act": act,
              "mark": J_MARK.get(act, "x"),
              "vote": ("RC", int(y), int(n)) if counted else None}
        st["text"], st["short"] = _j_words(st, b.get("bill") or "")
        st.pop("vote")
        steps = [st]
    return {"intro": i.get("date", ""), "steps": steps,
            "dates": sorted(x for x in (i.get("date"), d.get("date")) if x),
            "stages": stages, "notes": notes, "docs": docs}


# WHERE A RECORD COMES FROM, where that is not the list the General Court's
# bill search gave for the term. build_data marks each: "source" on a measure
# added from the database's table of past bills (its PAST_SOURCE) or from the
# docket alone (DOCKET_SOURCE, with title_source naming the journal that
# titles it), "number_source" where the database has no bill number and the
# docket's is used, "journal" on a House Journal record. preflight holds the
# two files' words to each other.
PAST_SOURCE = "General Court database"
DOCKET_SOURCE = "General Court docket"


# A DOCKET ROW THAT NAMES ANOTHER BILL, on a record build_data made from the
# database: quoted as the docket has it, because the page shows the docket's
# lines, and said. SB 267 of 2007's one vote is entered "Sen. Foster Moved
# Suspend All Rules Necessary to Allow for Consideration of SB 266 ...; RC
# 14Y-10N, MF; SJ 25, Pg. 1406-1407". The Senate Journal of 5 September 2007
# prints two motions on those pages: SB 266-FN-A's, "Adopted by the necessary
# 2/3 vote", and then SB 267-FN's, on which Senator Estabrook asked for the
# roll call the docket records, 14 to 10 (journals_senate/2007/SJ 25.txt,
# lines 50-80). The row is under the right bill and names the wrong one.
# {(term, bill): the note}. For the Clerk's list.
ROW_NAMES_ANOTHER = {
    ("2007-2008", "SB267"): (
        "The docket's row for this vote names \u201cSB 266\u201d. The Senate Journal of "
        "September 5, 2007 (pages 1406\u20131407) records the motion, and the 14\u201310 "
        "roll call on it, as being on SB 267-FN, this bill; the row is quoted here as "
        "the docket has it."),
}


def _docket_as_entered(b, narr):
    """The close of the note on a bill told as not introduced: what its docket
    holds, in the docket's own tense, and what this site does with it.

    HB 87 of 2009 has one row, which enters it as introduced. HB 177 and
    HB 277 of 2017 have one that still reads "To Be Introduced 01/04/2017 and
    referred to ...". HB 273 of 2017 has a second, "Public Hearing: 01/10/2017
    01:30 PM LOB 306", which narrative.build tells as the docket's notice: it
    is quoted here, beside the row that enters the bill, and the page's list
    of docket lines shows both (docket_lines). And
    on a record of the bill search's own list, the House status that list
    gives -- IN COMMITTEE on all four of 2017 -- is said, because it is what
    the General Court's own page shows and this page does not repeat."""
    evs = [e for e in (narr or {}).get("events", []) if not e.get("in_line")]
    entered = [e for e in evs if e.get("type") == "entered_introduced"]
    notices = [e for e in evs if e.get("cancelled")
               and e.get("type") in ("hearing", "exec", "worksession")]
    as_ = ("to be introduced" if entered and N.TO_BE_INTRODUCED.match(
        entered[0].get("raw") or "") else "introduced")
    field = ((b or {}).get("house_status") or "").strip() \
        if (b or {}).get("source") != PAST_SOURCE else ""
    field = (f"the General Court's bill search gives its House status as "
             f"\u201c{field}\u201d") if field else ""
    told = "told here as not introduced, and no record on this site says what became of it."
    if len(entered) == 1 and len(evs) == 1:
        return (f"Its docket has one row, which enters it as {as_}"
                + (f", and {field}" if field else "") + f"; it is {told}")
    if len(entered) == 1 and notices and len(evs) == 1 + len(notices):
        count = {2: "two", 3: "three", 4: "four"}.get(len(evs), str(len(evs)))
        rows = ", and ".join(f"one reads \u201c{e.get('raw')}\u201d" for e in notices)
        return (f"Its docket has {count} rows: one enters it as {as_}, and {rows}. "
                + (f"{field[0].upper()}{field[1:]}. " if field else "") + f"It is {told}")
    return (f"Its docket enters it as {as_}" + (f", and {field}" if field else "")
            + f"; it is {told}")


def record_notes(b, narr, status_source="", sponsors=(), term="", bid="",
                 text_version=""):
    """The notes a page carries about where its record comes from, as a list
    (empty for a record of the bill search's own list, which is nearly every
    one). One plain sentence or two each, in this site's words: a reader shown
    a bill the General Court's own search does not return is owed where it was
    read. Said after the docket's own notes, and never on a journal record
    told by journal_story, which says its own.

    ONLY WHAT IS TRUE OF THIS PAGE. The first note said "Its title, committee
    and status here are from the General Court's database" on every one of
    these records -- on the ones with no committee at all, and on the ones
    whose status_source beside it read "derived from the docket". The title is
    always the database's. The status is said to be where status_source says
    it is from. The committee is not placed: it is the docket's introduction
    row's where there is one and the referral code's otherwise, as on every
    archived bill, and no page says which.
    """
    b = b or {}
    out = []
    said = b.get("introduction") or {}
    if b.get("source") == PAST_SOURCE:
        from_db = status_source == PAST_SOURCE
        from_journal = status_source == JOURNAL_SOURCE
        note = ("This bill is not in the list the General Court's bill search gave "
                "for the term, which is where this site's other records of the term "
                "come from. Its title" + (" and status here are" if from_db else " here is")
                + " from the General Court's database of past sessions"
                + ((", and its history from its docket." if from_db or from_journal
                    else ", and its history and status from its docket.") if narr
                   else "."))
        if b.get("number_source") == DOCKET_SOURCE:
            note += (" The database's row for it carries no bill number; the number "
                     "is the one its docket files it under.")
        out.append(note)
    if said:
        # What the House Journal's resolution of introduction says of it
        # (build_data.INTRODUCTION_FROM_JOURNAL), where that decided how
        # the docket is told: on a record made from the database, and on the
        # four of 2017 that are the bill search's own, which carry this note
        # and not the one above.
        where = (f"The House introduces its bills by a resolution that names them "
                 f"by number. The resolution of {_long_day(said.get('date'))} "
                 f"({said.get('journal')}) names House Bills "
                 f"{said.get('numbered')}")
        if said.get("introduced"):
            out.append(where + ", which takes in this one, and the journal's list "
                       "prints its entry with its committee. Its docket enters its "
                       "withdrawal on the morning of the same day, so it is told "
                       "here as introduced and then withdrawn.")
        elif (narr or {}).get("withdrawn"):
            out.append(where + ", which leaves this number out, so it is told here "
                       "as withdrawn without having been introduced.")
        else:
            note = (where + ", which leaves this number out, and no later "
                    "resolution of the term names it. "
                    + _docket_as_entered(b, narr))
            # AND THE HEADING ON ITS TEXT IS NOT AN INTRODUCTION. The four of
            # 2017 have a text on the General Court's site, each headed "HB
            # 273 - AS INTRODUCED" (legislation/2017/HB0273.html), and the Bill
            # Text tab shows that heading under a status of Not introduced.
            # `text_version` is the heading as the tab prints it.
            if (text_version or "").strip().lower() == "as introduced":
                note += (" The General Court's text of it is headed \u201cAs "
                         "introduced\u201d, the heading it gives a bill's first "
                         "printing, and the Bill Text tab shows it under that heading.")
            out.append(note)
    if b.get("source") == PAST_SOURCE and (term, bid) in ROW_NAMES_ANOTHER and narr:
        out.append(ROW_NAMES_ANOTHER[(term, bid)])
    # A SPONSOR LIST THAT MAY BE SHORT. In 1999-2000 the General Court's
    # sponsor record lists fewer sponsors than the bills print
    # (past_sponsors.SHORT_TERMS says what was measured), and a bill filled
    # from it has nothing else to be held to.
    if term in PSP.SHORT_TERMS and any(
            x.get("seat_source") == PSP.SOURCE for x in sponsors or ()):
        out.append("This bill's sponsors are from the General Court's sponsor record, "
                   "the only source this site has for them. For 1999\u20132000 that "
                   "record leaves co-sponsors off some bills that print them, so this "
                   "list may not be complete.")
    if out:
        return out
    ts = b.get("title_source") or {}
    if ts:
        return [("The General Court's data holds this measure's docket and no title "
                 f"for it. The title here is as the {ts.get('journal', 'journal')} "
                 f"prints it ({_long_day(ts.get('date'))}, page {ts.get('page')} of "
                 f"{ts.get('volume', 'the bound volume')}).")]
    j = b.get("journal") or {}
    if j.get("decided") and narr:
        i = j.get("introduced") or {}
        return [("This bill is not in the list the General Court's bill search gave "
                 "for the term, and its database's table of past bills has no row for "
                 "it. Its title and sponsors here are as the House Journal prints "
                 f"them in its list of bills introduced ({i.get('journal')}, "
                 f"{_long_day(i.get('date'))}, page {i.get('page')}); its history is "
                 "from its docket.")]
    return []


def bill_text_url(b, st):
    """The address of the bill's own text, corrected on the way out.

    Small, and out on its own because it feeds both the documents list
    and the payload, and because the twenty lines of comment below are
    the record of two separate failures that each reached every bill on
    the site. They travel with the code they explain.
    """
    # billText.aspx needs the session year as well as the id. Without it
    # the page answers with an ASP.NET error and the reader gets a blank
    # screen. Records fetched before that was understood carry a two-
    # parameter link, so the year is added here from the bill's own filing
    # year -- which is what the status page's link says, on every one
    # checked. Re-running fetch_bill_status.py --reparse replaces the
    # guess with the page's own value and needs no network.
    #
    # AND txtFormat=pdf IS NOT AN ADDRESS THE GENERAL COURT SERVES. The
    # scrape built one anyway, so every bill on this site linked to
    #
    #   error: condensedbillno is neither a DataColumn nor a DataRelation
    #   for table text.
    #
    # All 4,230 of them. The status page's own link -- the one shape that
    # appears in 2,234 cached pages -- is txtFormat=html, which answers
    # with the bill. So the format is corrected here rather than in the
    # scrape, because the scrape is a record of what was fetched and this
    # is a link being published.
    text_url = (st.get("text_pdf", "") or "").replace("txtFormat=pdf",
                                                      "txtFormat=html")
    if text_url and "sy=" not in text_url:
        sy = st.get("text_year") or b.get("lsr_year") or ""
        if sy:
            text_url += f"&sy={sy}"
    # AND 2016 NEEDS &v=current, or the link we publish is dead. Without it
    # billText answers 200 with a two-byte body, so this was sending readers
    # of up to 1,072 bills to a blank page that looked like a working address.
    # Measured 19 September; fetch_legislation.NEEDS_VERSION is the same fact
    # on the fetching side.
    if text_url and "sy=2016" in text_url and "v=" not in text_url:
        text_url += "&v=current"
    return text_url
