#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
The site's topic vocabulary: the category a General Court topic name ends up
under, for one record, and the chapters a bill's own text says it changes,
which split two of those names in two.

    import topic_vocabulary as TV
    TV.vocabulary_of("CACR", {"title": "relating to the governor."}, "CACR1")   # None: retired
    TV.statute_changes("2025-2026", "HB1")     # ["21-I", "21-I:1", ...] from rsa_citations.json

A RULE ABOUT A FACT, KEPT WITH THE PARSERS (the refactor's stage 3, 19
November 2026). These were build_site_v2's, the page builder, and
request_topics -- a parser, which files next session's bill requests -- read
vocabulary_of from there, so a step of src/parse imported the 13,000-line
page builder for one rule (reports/refactor/stage0-code.md, section 2). They
moved here as they stood; build_site_v2 names each as before
(build_site_v2.vocabulary_of, build_site_v2._CHANGES, ...), and its
unify_vocabulary applies vocabulary_of to every record, as it did.
"""

import json
import re
from pathlib import Path

import topic_model as TM



_CHANGES = []


def statute_changes(term, bid):
    """The chapters and sections a bill's own text says it changes, from
    rsa.py's rsa_citations.json -- the bill search's RSA filter (the person,
    11 October 2026: the statute search replaces the floor vote day filter).
    Each section's chapter is listed with it, so a chapter matches a bill
    that changes any section of it. [] where the file is not on this disk."""
    if not _CHANGES:
        p = Path("rsa_citations.json")
        try:
            _CHANGES.append(json.loads(p.read_text(encoding="utf-8")).get("bills", {}) if p.is_file() else {})
        except (OSError, ValueError):
            _CHANGES.append({})
    got = ((_CHANGES[0].get(term) or {}).get(bid) or {}).get("changes") or []
    out = set(got) | {a.split(":")[0] for a in got}

    def key(a):
        ch, _, sec = a.partition(":")
        m = re.match(r"(\d+)(?:-([A-Z]+))?$", ch)
        return ((int(m.group(1)), m.group(2) or "") if m else (99999, ch), sec)
    return sorted(out, key=key)


# A GENERAL COURT TOPIC NAME IN A READER'S WORDS (the person, approved 17
# October 2026): "CACR", a kind of measure rather than a subject, on the
# constitutional amendments. Applied after the model's vocabulary, which is
# measured in the General Court's own names; build_feeds keeps each topic's
# old feed address (feeds.TOPIC_ADDRESS) so a feed already followed goes on
# working. "Crimes, Crim.Proc. & Corr." was the other, worded "Crimes,
# Criminal Procedure and Corrections"; since 17 November 2026 it and
# "Property - Real and Personal" are each split in two instead (TM.SPLITS,
# vocabulary_of below).
TOPIC_WORDS = {"CACR": "Constitutional Amendments"}


def statute_chapters(term, bid):
    """The chapters a bill's own text says it changes (statute_changes, without
    the sections), for the split of a topic in two; () for a request, or where
    rsa_citations.json is not on this disk."""
    return tuple(sorted({a.split(":")[0] for a in statute_changes(term, bid)})) if term and bid else ()


def vocabulary_of(s, rec, bid="", term=""):
    """The site category a General Court topic name ends up under, for one
    record: None where the name is retired, otherwise the name to show.

    TWO NAMES ARE SPLIT IN TWO (TM.SPLITS, 17 November 2026): a bill the
    General Court or the model files under Crimes, Crim.Proc. & Corr. is
    Crimes and Criminal Procedure or Corrections, and one under Property -
    Real and Personal is Real Estate or Personal Property, by the chapters
    it changes (given `term`, from rsa_citations.json) and its title -- a
    request, which has neither a term here nor a text, by its title.

    ONE IS DRAWN FROM ALL THE OTHERS (TM.cannabis_topic, 17 November 2026): a
    bill or request whose title is about cannabis is Cannabis, whichever name
    the General Court or the model gave it, but a constitutional amendment and
    a study, which keep theirs.

    ONE PATH FOR EVERY TERM. unify_vocabulary applies it to every record, so
    the 2025-2026 labels and the official codes official_topics.adopt gives the
    archive are mapped by the same lines, and so are the table in
    reports/topics-stage0 and its preflight check.

    A retired name is None -- unless a proposal the owner has turned on
    (TM.ENABLED) claims the bill, as Legislative Rules and Organization would
    claim the General Court's "Regular Meeting" housekeeping resolutions. A
    proposal reads the bill's number ("HR1": a resolution of the chamber's
    own) as well as its title, and a record here is keyed by it rather than
    carrying it: the review of 24 October 2026 found this term's HR 1-4 and SR 5
    still with no topic, their "Regular Meeting" retired and the housekeeping
    rule never asked."""
    asked = rec if rec.get("bill") else {**rec, "bill": bid}
    if s in TM.RETIRED and not TM.proposal_for(asked, "first"):
        return None
    new_s = TM.remap_gold(s, asked)
    if TM.cannabis_topic(new_s, asked.get("title")) == TM.CANNABIS:
        return TM.CANNABIS
    if new_s in TM.SPLITS:
        return TM.split_topic(new_s, asked.get("title"), statute_chapters(term, bid or asked.get("bill")))
    return TOPIC_WORDS.get(new_s, new_s)
