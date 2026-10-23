#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.2
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
matters).
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
                       "kinds": d.get("kinds") or {}}
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
