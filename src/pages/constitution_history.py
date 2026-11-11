#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.1
"""
An article's "History and citations" fold on the Laws page's Constitution tab.

    import constitution_history as CH
    CH.fate(row, ballot)                 # a CACR's fate, in words
    CH.fold(part, key, cc, bills, ballots)   # the fold's HTML, or ""

Asks nobody and reads nothing: build_rsa.py hands it constitution_citations.json
(parse/constitution_citations.py), the bill index through its Bills object, and
the rows of corrections/ballot_results.json (read, never written).

THE FOLD IS THE STATUTES' (build_rsa.chapter_page): the same <details class="rs-fold">
named "History and citations", closed, a list under each heading with its count on
the heading, bills drawn as the statutes' lists draw them. Four lists, in the
statutes' order: Cited by (bills other than CACRs, then statute sections), How it has
changed (the CACRs the voters ratified, each with the Secretary of State's count) and
Other proposed amendments (every other CACR aimed at the article, with its fate). No
earlier wording is shown: none is on disk (the person, 11 November 2026).

THE FATE IS THE BILL PAGE'S. build_site_v2.bill_disposition works out what became of
each bill from the docket of its own era (the 1989-2013 docket and the 2015 on one
read differently) and the index row carries it as `kind`, `status` and `rail`; this
words it for an article and asks no docket. A CACR the voters decided carries the
count from ballot_results.json, and ratified or not is worked out from yes and no
against two thirds (Part Second, Article 100), as the bill page does.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import html
import re

import components as C
import i18n as I

E = html.escape
FOLD_NAME = "History and citations"
CHAMBER = {"H": "House", "S": "Senate"}


def ratified(yes, no):
    """Two thirds of those voting on the question (Part Second, Article 100)."""
    return 3 * yes >= 2 * (yes + no)


def _step(row):
    """The rail's last step with a chamber's vote: (chamber, day, note), or None."""
    for s in reversed(row.get("rail") or []):
        if str(s[0])[:1] in CHAMBER and len(s) > 2 and s[2]:
            return CHAMBER[str(s[0])[0]], (s[1] or ""), str(s[2])
    return None


def voters(ballot, lang=I.DEFAULT):
    """The voters' answer as a sentence, from a row of ballot_results.json:
    "Ratified by the voters, Nov 7, 2006, Question No. 2: 240,767 yes, 100,688 no"."""
    day = C.date_words(ballot.get("election") or "", "medium")
    yes, no = ballot.get("yes"), ballot.get("no")
    if yes is None or no is None:
        return I.say(lang, "constitution.hist.count_pending", "Passed both chambers; on the ballot {day}, count not yet recorded", day=day)
    if ratified(yes, no):
        return I.say(lang, "constitution.hist.ratified", "Ratified by the voters, {day}: {yes} yes, {no} no",
                     day=day, yes=f"{yes:,}", no=f"{no:,}")
    return I.say(lang, "constitution.hist.not_ratified",
                 "Passed both chambers; not ratified by the voters, {day}: {yes} yes, {no} no",
                 day=day, yes=f"{yes:,}", no=f"{no:,}")


def fate(row, ballot=None, lang=I.DEFAULT):
    """What became of a CACR, from its row in the site's index (the bill page's
    own disposition) and, where the voters decided it, its row of the ballot file."""
    row = row or {}
    status, kind = row.get("status") or "", row.get("kind") or ""
    if kind == "adopted" or ballot:
        if ballot:
            return voters(ballot, lang)
        return I.say(lang, "constitution.hist.to_voters", "Passed both chambers; sent to the voters")
    step = _step(row)
    chamber, day, note = step if step else ("", "", "")
    when = C.date_words(day, "medium") if day else ""
    at = f"{chamber}, {when}" if chamber and when else chamber or when
    if status == "Killed":
        return I.say(lang, "constitution.hist.itl", "Inexpedient to legislate ({at})", at=at) if at else \
            I.say(lang, "constitution.hist.itl_bare", "Inexpedient to legislate")
    if status == "Failed to pass":
        vote = re.sub(r"^failed,?\s*", "", note).strip()
        return I.say(lang, "constitution.hist.failed", "Failed the three-fifths vote in the {chamber}{vote} "
                     "({when})", chamber=chamber or "chamber", vote=f", {vote}" if vote else "", when=when) \
            if when else I.say(lang, "constitution.hist.failed_bare", "Failed the three-fifths vote")
    if status == "Died on the table":
        return I.say(lang, "constitution.hist.table", "Laid on the table and died there")
    if status == "Indefinitely postponed":
        return I.say(lang, "constitution.hist.postponed", "Indefinitely postponed")
    if kind == "study":
        return I.say(lang, "constitution.hist.study", "Sent to interim study")
    if status == "Died when the session ended":
        return I.say(lang, "constitution.hist.session_end", "Died when the session ended")
    if status == "Passed one chamber":
        return I.say(lang, "constitution.hist.one_chamber", "Passed one chamber and died")
    return status


def _item(bills, term, bill, text, ballot=None, lang=I.DEFAULT):
    """One CACR: the bill as the statutes' lists draw one, its term's years, its fate."""
    k = f"{term}/{bill}"
    st = fate(bills.row(k), ballot, lang)
    return (f'<li><a href="{E(bills.url(k))}" title="{E((bills.row(k) or {}).get("title") or "")}">'
            f'{E(bills.label(k))}</a> <span class="rs-yr">{E(term)}</span>'
            + (f' <span class="rs-st">{E(st)}</span>' if st else "") + text + "</li>")


def verb_note(verb, lang=I.DEFAULT):
    """What a CACR did to the article, where amending it is not it."""
    if verb == "repeal":
        return I.say(lang, "constitution.hist.verb_repeal", "proposed to repeal it")
    if verb == "insert_after":
        return I.say(lang, "constitution.hist.verb_after", "proposed a new article after it")
    if verb == "new":
        return I.say(lang, "constitution.hist.verb_new", "proposed this article as new")
    return ""


def _order(rows):
    """Newest term first, and within a term the higher number first."""
    return sorted(rows, key=lambda r: (r[0], int(re.sub(r"\D", "", r[1]) or 0)), reverse=True)


def lists(part, key, cc, bills, ballots, rsa_href, lang=I.DEFAULT):
    """[(heading key, heading, note, [<li>])] for one article, empty lists left out."""
    got = (cc or {}).get("articles", {}).get(f"{part}:{key}") or {}
    out = []
    cited = [f'<li><a href="{E(bills.url(f"{t}/{b}"))}" title="{E((bills.row(f"{t}/{b}") or {}).get("title") or "")}">'
             f'{E(bills.label(f"{t}/{b}"))}</a> <span class="rs-yr">{E(t)}</span></li>'
             for t, b in _order(got.get("bills", []))]
    cited += [f'<li><a href="{E(rsa_href(a))}">RSA {E(a)}</a></li>' for a in got.get("rsa", [])]
    won, lost = [], []
    for term, bill, verb in _order(got.get("proposed", [])):
        b = ballots.get((term, bill))
        says = verb_note(verb, lang)
        item = _item(bills, term, bill, f' <span class="rs-note">{E(says)}</span>' if says else "", b, lang)
        if b and b.get("yes") is not None and ratified(b["yes"], b["no"]) and verb != "insert_after":
            won.append(item)
        else:
            lost.append(item)
    if cited:
        out.append(("cited", I.say(lang, "constitution.hist.cited", "Cited by"), I.say(
            lang, "constitution.hist.cited_note", "Bills and statutes that name this article and its part."), cited))
    if won:
        out.append(("hist", I.say(lang, "constitution.hist.changed", "How it has changed"), I.say(
            lang, "constitution.hist.changed_note", "Amendments the voters ratified, newest first."), won))
    if lost:
        out.append(("other", I.say(lang, "constitution.hist.other", "Other proposed amendments"), I.say(
            lang, "constitution.hist.other_note", "Every other constitutional amendment aimed at this article, "
            "with what became of it."), lost))
    return out


def fold(part, key, cc, bills, ballots, rsa_href, lang=I.DEFAULT):
    """The article's fold, or "" where it has nothing to list."""
    rows = lists(part, key, cc, bills, ballots, rsa_href, lang)
    if not rows:
        return ""
    return ('<div class="rs-folds"><details class="rs-fold"><summary><span class="rs-fname">'
            + E(I.say(lang, "constitution.hist.name", "History and citations")) + "</span></summary>"
            + "".join(f'<div class="rs-fpart" data-list="{k}"><h5 class="rs-fh">{E(h)} '
                      f'<span class="rs-fcount">&middot; {len(items):,}</span></h5>'
                      f'<p class="rs-note">{E(n)}</p><ul class="rs-list">{"".join(items)}</ul></div>'
                      for k, h, n, items in rows)
            + "</details></div>")
