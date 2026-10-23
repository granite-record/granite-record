#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.3
"""
The Journal's words for a vote on no bill, as every page shows them.

    import vote_passage as VP
    VP.load()                     # journal_motions.json, read once
    VP.entry("2026-H-290")        # its entry, or None where none is shown
    VP.short(e)                   # the member Votes tab's few words
    VP.passage_html(e, esc)       # the quote, its heading and its page

ONE PLACE FOR THE WORDS (23 October 2026). A session day's "Votes on No
Bill", the per-term list of votes not on a bill and the shared roll-call
index the member Votes tab reads all say what such a vote was about, and
they say it from journal_motions.json, which src/parse/journal_motions.py
writes; this reads it and draws it, so the three cannot drift apart.

WHAT IS SHOWN. Only an entry no gate held back (`held` empty). The Journal's
sentences verbatim, in a quotation, under its own heading where it printed
one, cited to the Journal and the page, linked to the document where the
drain's queue holds its address; the kind of question in the site's words;
and a one-line summary only where the parser wrote one -- never one of its
own here. Captions are never quoted on this site; the Journal is the
official record and is quoted, always with its page.

Standard library only, and nothing of the site builder's: importing this
changes nothing about where a builder stands (queue_links.py says why that
matters). journal_motions.py, the parser, is read for its patterns alone.

AND THREE THINGS SINCE (the owner's review of 23 October 2026): a vote on
a committee's report carries the report, whole, in a fold ("View the
report"); a reprimand, a censure, a member's privileges and the questions
with no name of their own are shown as "Misc vote" and filtered as "Misc
votes"; and a motion to move the previous question, limit debate or divide
the question of one bill is that bill's (on_bills, motion_events).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import json


SOURCE = Path("journal_motions.json")
_CACHE = {}
CHAMBER = {"H": "House", "S": "Senate"}
# The site's word for what a division is, said once (the owner's words of 23
# October 2026, to be marked clearly).
DIVISION_NOTE = "A division: the journal gives the count, not each member’s vote."
VOICE_NOTE = "A voice vote: the journal gives no count and no member’s vote."


def load(path=SOURCE):
    """{"rollcalls": {key: entry}, "journal_only": [entry], "kinds": {kind:
    words}} -- empty where the step has not run here."""
    key = str(path)
    if key not in _CACHE:
        try:
            d = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            d = {}
        _CACHE[key] = {"rollcalls": d.get("rollcalls") or {},
                       "journal_only": d.get("journal_only") or [],
                       "kinds": d.get("kinds") or {},
                       "groups": d.get("groups") or {},
                       "group_words": d.get("group_words") or {},
                       "bill_votes": d.get("bill_votes") or []}
    return _CACHE[key]


def entry(key, path=SOURCE):
    """The entry for roll call `key` ("2026-H-290") that is shown, or None."""
    e = load(path)["rollcalls"].get(key)
    return e if e and not e.get("held") else None


def journal_only(body=None, day=None, path=SOURCE):
    """The votes only the Journal records, of a chamber and a day."""
    return [e for e in load(path)["journal_only"]
            if (body is None or e.get("body") == body) and (day is None or e.get("date") == day)]


def kind_label(e, path=SOURCE):
    kinds = load(path)["kinds"]
    return kinds.get((e or {}).get("kind") or "", "") or ""


def short(e, path=SOURCE, limit=110):
    """A few words for a row that says only "no bill" now: the one-line
    summary where there is one, else the kind of question, never more than
    `limit` characters."""
    if not e:
        return ""
    s = e.get("line") or kind_label(e, path)
    if len(s) > limit:
        s = s[:limit - 1].rsplit(" ", 1)[0] + "…"
    return s


def _words_date(iso):
    """The day in a sentence, in the components' one formatter: "March 6,
    2026"."""
    import components as C
    return C.date_words(iso, "full") if iso else ""


def cite_words(e):
    """"House Journal 14, May 21, 2026, page 24" -- or "pages 23-24" where
    the quote begins a page before the tally; the file's own page where the
    Journal printed none (the House before 2013)."""
    j = e.get("journal") or ""
    when = _words_date(e.get("page_date") or e.get("date"))
    p, p0 = e.get("page"), e.get("page_from")
    if p:
        pages = (f"pages {p0}–{p}" if p0 and p0 != p and p0 < p else f"page {p}")
    else:
        pages = f"page {e.get('pdf_page')} of the file" if e.get("pdf_page") else ""
    return ", ".join(x for x in (j, when, pages) if x)


def cite_href(e):
    """The Journal's own address, at the page where the reader's viewer
    takes a page number; "" where the drain's queue holds no address."""
    u = e.get("url") or ""
    if u and e.get("pdf_page"):
        return f"{u}#page={int(e['pdf_page'])}"
    return u


def passage_html(e, esc, cls="nbj"):
    """The quote: the Journal's heading, its sentences, the count where the
    roll call stands, and what it says the vote did; then whose words and
    where. Earlier sentences put again ("The question now being ...") are
    parted from the rest by an ellipsis, as a quotation is."""
    said = e.get("said") or []
    out, gap = [], False
    head = e.get("heading") or ""
    if head:
        out.append(f'<p class="nbjh">{esc(head)}</p>')
    for i, x in enumerate(said):
        if x.get("k") == "outcome":
            y, n = e.get("yeas"), e.get("nays")
            count = (f'<span class="nbt">[{esc(str(y))}–{esc(str(n))}]</span> '
                     if y is not None and n is not None and e.get("how") != "division" else "")
            out.append(f'<p class="nbout">{count}{esc(x.get("t") or "")}</p>')
            continue
        if gap or (i and said[i - 1].get("earlier") and not x.get("earlier")):
            out.append('<p class="nbgap" aria-hidden="true">…</p>')
            gap = False
        t = esc(x.get("t") or "")
        if x.get("by"):
            t = f'<span class="nbby">{esc(x["by"])}:</span> “… {t}”'
        out.append(f"<p>{t}</p>")
    if e.get("after"):
        out.append('<p class="nbgap" aria-hidden="true">…</p>'
                   f'<p class="nbout">{esc(e["after"])}</p>')
    href = cite_href(e)
    where = esc(cite_words(e))
    if href:
        where = f'<a href="{esc(href)}" target="_blank" rel="noopener">{where}</a>'
    who = "Senate" if e.get("body") == "S" else "House"
    return (f'<figure class="{cls}"><blockquote'
            + (f' cite="{esc(e.get("url"))}"' if e.get("url") else "")
            + f'>{"".join(out)}</blockquote>'
            f'<figcaption>The {who} Journal’s words, {where}.</figcaption></figure>')


# ------------------------------------------------------------ the report
#
# "View the report" (the owner's words, 23 October 2026): the committee's
# report the vote was on, whole and verbatim as the Journal prints it
# (journal_motions.report_of), folded shut under the passage, cited to its
# pages. The fold's id is the address the term's list links to; app.js
# opens a fold the address points into.

def report_anchor(e):
    """"rep-2026-H-290": the fold's id on the session day."""
    return "rep-" + "".join(c for c in str((e or {}).get("key") or "") if c.isalnum() or c in "-_")


def report_cite(e):
    """"House Journal 14, May 21, 2026, page 23" -- the report's own pages."""
    r = (e or {}).get("report") or {}
    p0, p1 = r.get("page_from"), r.get("page_to")
    if p0:
        pages = f"pages {p0}–{p1}" if p1 and p1 != p0 else f"page {p0}"
    else:
        f0, f1 = r.get("pdf_from"), r.get("pdf_to")
        pages = (f"pages {f0}–{f1} of the file" if f1 and f1 != f0 else
                 f"page {f0} of the file" if f0 else "")
    when = _words_date(e.get("page_date") or e.get("date"))
    return ", ".join(x for x in (e.get("journal") or "", when, pages) if x)


def report_html(e, esc):
    """The fold: shut, "View the report", the report's heading and its
    paragraphs, and whose words and where. "" where no report was kept."""
    r = (e or {}).get("report") or {}
    paras = r.get("paras") or []
    if not paras:
        return ""
    u = e.get("url") or ""
    href = f"{u}#page={int(r['pdf_from'])}" if u and r.get("pdf_from") else u
    where = esc(report_cite(e))
    if href:
        where = f'<a href="{esc(href)}" target="_blank" rel="noopener">{where}</a>'
    who = "Senate" if e.get("body") == "S" else "House"
    body = "".join(f"<p>{esc(p)}</p>" for p in paras)
    head = f'<p class="nbjh">{esc(r["heading"])}</p>' if r.get("heading") else ""
    return (f'<details class="nbrep" id="{esc(report_anchor(e))}"><summary>View the report</summary>'
            f'<div class="nbrepb">{head}{body}</div>'
            f'<p class="nbrepc">The report as the {who} Journal prints it, {where}.</p></details>')


# ------------------------------------------------- the kinds a reader sees

def group_of(kind, path=SOURCE):
    """The per-term list's filter's name for a kind: "misc" for a
    reprimand, a member's privileges and every question with no name of its
    own (journal_motions.GROUPS), else the kind itself."""
    return (load(path).get("groups") or {}).get(kind or "", kind or "")


def group_words(group, path=SOURCE):
    """The filter's words for a group: "Misc votes", or the kind's own."""
    d = load(path)
    return (d.get("group_words") or {}).get(group) or (d.get("kinds") or {}).get(group, "") or ""


# --------------------------------------------- motions on a bill's debate
#
# THE BILL'S OWN (the owner, 23 October 2026: "Motions to limit debate on a
# bill by calling the question or splitting the question should be included
# on that bill's vote page and the session day it happened"). Two things
# follow from journal_motions.json, and every page that draws a bill's votes
# or a day's takes them from here, so they cannot say different things:
#
#   on_bills()      a roll call the roll-call file files under no bill whose
#                   passage moves to divide, limit or call the question of
#                   exactly one bill of the term -- drawn under that bill.
#   motion_events() the divisions and voice votes on those motions, from the
#                   bill's own docket rows that no reader of the docket drew,
#                   and from the Journal where the docket has none -- each as
#                   a floor row the bill's Votes tab and the session day draw
#                   as they draw any division or voice vote.

def on_bills(path=SOURCE):
    """{roll call key: bill} for every roll call on no bill that is a motion
    on one bill's debate."""
    return {k: e["on_bill"] for k, e in load(path)["rollcalls"].items()
            if e.get("on_bill") and not e.get("held")}


def move_on_bills(rollcalls, path=SOURCE):
    """(rollcalls, {key: bill}): a copy of rollcalls.json's terms with each
    such roll call taken out of "_procedural" and put under its bill (marked
    `filed_under`), and which were moved. Nothing is moved where
    journal_motions.json is not here."""
    moved = on_bills(path)
    if not moved:
        return rollcalls, {}
    out, did = {}, {}
    for term, bills in (rollcalls or {}).items():
        if not isinstance(bills, dict):
            out[term] = bills
            continue
        nb = dict(bills)
        keep = []
        for r in bills.get("_procedural") or []:
            k = f'{r.get("year")}-{r.get("body")}-{r.get("number")}'
            b = moved.get(k)
            if b:
                nb[b] = list(nb.get(b) or []) + [dict(r, filed_under="_procedural")]
                did[k] = b
            else:
                keep.append(r)
        if "_procedural" in bills:
            nb["_procedural"] = keep
        out[term] = nb
    return out, did


def _by_bill(path=SOURCE):
    key = ("by_bill", str(path))
    if key not in _CACHE:
        idx = {}
        for e in load(path).get("bill_votes") or []:
            idx.setdefault((e.get("term"), e.get("bill")), []).append(e)
        _CACHE[key] = idx
    return _CACHE[key]


_ROW_VOTE = None


def _row_vote(raw):
    """(motion, vote kind, yeas, nays) a docket row states, or None:
    "Sen. Sanborn moved to call the question, MA, VV; SJ 14"."""
    import re
    global _ROW_VOTE
    if _ROW_VOTE is None:
        _ROW_VOTE = re.compile(r"\b(?P<m>MA|MF|ML)\b[,;\s]*(?P<v>VV|DV|DIV|RC)\b[,;\s=]*"
                               r"(?:\(?\s*(?P<y>\d+)\s*-\s*(?P<n>\d+))?")
    m = _ROW_VOTE.search(raw or "")
    if not m:
        return None
    v = "DV" if m.group("v") in ("DV", "DIV") else m.group("v")
    return (m.group("m"), v, int(m.group("y")) if m.group("y") else None,
            int(m.group("n")) if m.group("n") else None)


def motion_events(term, bill, events, rcs=(), path=SOURCE):
    """The divisions and voice votes on moving the previous question,
    limiting debate or dividing the question of `bill` that nothing draws
    yet, each as a floor row ({"type": "floor", "action", "mover", "motion",
    "vote_kind", "yeas", "nays", "date", "body", ...}) and where in `events`
    it falls (`_at`, the index of the row it stands before or comes from).

    From the docket first: a row of the bill's that states the motion and a
    voice vote or a division, which narrative.py reads as no floor action.
    Then from the Journal (journal_motions.bill_motion_votes), only for a
    day the bill's docket shows it before that chamber, and only where the
    docket states no such motion that day -- one vote is one card. A roll
    call is the roll-call file's, and a count a roll call of the bill's that
    day has is that roll call's."""
    import re
    import journal_motions as JM
    events = events or []
    out = []
    once = set()              # a docket row the dump repeats is one vote
    given = set()             # (body, date, motion) the docket gives a vote on
    days = {}                 # (body, date) -> index of the bill's first row that day
    for i, e in enumerate(events):
        b = (e.get("body") or "").strip().upper()
        d = (e.get("date") or "")[:10]
        if e.get("cancelled") or not d:
            continue
        days.setdefault((b, d), i)
        raw = e.get("raw") or e.get("action") or ""
        kind = JM.bill_motion_of(raw)
        if not kind:
            continue
        got = _row_vote(raw)
        if e.get("type") in ("floor", "veto_override"):
            given.add((b, d, kind))        # the Votes tab draws it already
            continue
        if not got:
            continue                       # moved, and no vote stated: the Journal may give it
        given.add((b, d, kind))
        if got[1] == "RC":
            continue
        motion, vk, y, n = got
        if (b, d, kind, motion, vk, y, n) in once:
            continue
        once.add((b, d, kind, motion, vk, y, n))
        if any(r.get("date") == d and r.get("body") == b and y is not None
               and (r.get("yeas"), r.get("nays")) == (y, n) for r in rcs or ()):
            continue                       # "Previous Question MA DV 195-166": a roll call
        mover = re.search(r"\b(?:Rep|Sen|Senator|REP|SEN)\.?\s+([A-Z][\w.'’-]+(?:\s+[A-Z][\w.'’-]+)?)"
                          r"\s+(?:moved|moves|MOVED|Moved)\b", raw)
        who = mover.group(1) if mover else ""
        if who.isupper():
            who = who.title()
        out.append({"type": "floor", "action": JM.BILL_MOTION_WORDS[kind][b or "H"],
                    "mover": who, "motion": motion, "vote_kind": vk, "yeas": y, "nays": n,
                    "date": d, "body": b, "raw": raw, "cite": e.get("cite") or "",
                    "cite_page": e.get("cite_page"), "source": "docket", "_at": i})
    for j in _by_bill(path).get((term, bill), []):
        b, d = j.get("body"), j.get("date")
        if (b, d) not in days or (b, d, j.get("motion")) in given:
            continue
        if j.get("how") == "division" and any(
                r.get("date") == d and r.get("body") == b
                and (r.get("yeas"), r.get("nays")) == (j.get("yeas"), j.get("nays")) for r in rcs or ()):
            continue
        out.append({"type": "floor", "action": j.get("words") or "", "mover": j.get("mover") or "",
                    "motion": "MA" if j.get("passed") else "MF",
                    "vote_kind": "DV" if j.get("how") == "division" else "VV",
                    "yeas": j.get("yeas"), "nays": j.get("nays"), "date": d, "body": b,
                    "raw": " ".join(x.get("t") or "" for x in j.get("said") or []),
                    "cite": j.get("journal") or "", "cite_page": j.get("page"),
                    "source": "journal", "journal_key": j.get("key"), "_at": days[(b, d)]})
    return out
