#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
What a bill's text says it changes: the statutes its clauses amend or repeal
(bill_amends), as against every statute it mentions, and the articles a
CACR's text amends (constitution_targets).

    import bill_statutes as BST
    BST.bill_amends(body)            # {citation as written: url}
    BST.constitution_targets(body)   # the articles, as parse_constitution reads them

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md section 5). It moved here as it stood,
comments and all, nothing inside it edited: from
AMEND_WORD's comment to constitution_targets, one block. The links
themselves are rsa_links.py's (RSA_CITE, rsa_url) and the constitution's
parse_constitution.py's. It imports no builder (_import_cycles_cut). build_site_v2 imports every
name here back under its own, so build_site_v2.<name> answers as it did, for
build_bills, main and the checks.
"""

import re

import parse_constitution as PCON
from rsa_links import RSA_CITE, rsa_url


# WHAT A BILL AMENDS IS NOT WHAT IT MENTIONS. rsa_links finds every citation
# anywhere in a document, which is right for turning words into links and wrong
# for a row headed "Amends RSA chapters". 628 bills on this site cite RSA 91-A
# and 150 of them amend it; the other 478 say things like "exempt from
# disclosure under RSA 91-A:5, IV" inside the text of some other statute, and
# the row told a reader the bill changes the Right-to-Know law. Counted over
# the 14,085 bills whose text is on disk: 15,788 of 36,303 chapter claims --
# 43.5% -- were mentions of this kind.
#
# A New Hampshire bill states what it changes in ONE CLAUSE ENDING IN A COLON,
# and everything after that colon is the new text:
#
#   Amend RSA 126-A:5 by inserting after paragraph II the following new
#     paragraph:                                          -> RSA 126-A:5
#   Amend RSA 91-A:4, IV(a) to read as follows:           -> RSA 91-A:4
#   Repeal. RSA 91-A:5, VI, relative to X, is repealed.   -> RSA 91-A:5
#   The following are repealed: I. RSA 77:3 ... II. RSA 76:8 ...
#
# Of those bills' 24,700 `Amend` instructions, 24,267 close with a colon within
# 400 characters. The 433 that do not are lower-case "amend" inside statutory
# prose -- "may amend the petition only if the defendant is provided..." -- and
# are not instructions at all, so a clause with no colon yields NOTHING rather
# than 400 characters of somebody else's text. `Amend` is matched case
# sensitively for the same reason: an instruction opens a sentence.
AMEND_WORD = re.compile(r"\bAmend\b")
# The two forms the drafters use, and no third.
REPEALED = re.compile(r"\b(?:is|are)\s+repealed\b", re.I)
REPEAL_LIST = re.compile(r"\bfollowing\s+(?:is|are)\s+repealed\s*:", re.I)
# The colon that ends a clause -- NOT the one inside "RSA 91-A:4", which is
# part of the citation and is always followed by a digit.
CLAUSE_END = re.compile(r":(?!\d)")
# Where a repeal list stops: the bill's next numbered section. "213:1" as well
# as "1", because an enacted bill is renumbered into the session laws and its
# sections then read "213:1 New Chapter; ...".
NEXT_SECTION = re.compile(r"^\s*(?:\d{1,3}:)?\d{1,3}\s+[A-Z(]", re.M)
# A WINDOW CUT MID-CITATION INVENTS ONE. The 2,000 character stop landed inside
# "XXIII. RSA 175:1" in 2011's HB 1500 and the tail read as RSA 17 -- a real
# chapter, and the wrong one. Trimming the part-word is what makes this reader
# a strict subset of rsa_links rather than nearly one.
PART_WORD = re.compile(r"\S+$")


def bill_amends(body):
    """{citation as written: url} for the statutes a bill's text says it changes.

    The same shape rsa_links returns, so the page reads it the same way, and
    measured to be a strict subset of it: across all 14,085 texted bills this
    names no chapter rsa_links did not.

    A bill that CREATES a chapter -- "Amend RSA by inserting after chapter
    359-S the following new chapter:" -- names no existing chapter here and
    gets no row. That is the largest part of the 784 bills that had a row and
    now have none; the rest are findings, appropriations and effective-date
    clauses that cite a statute without touching it.
    """
    out = {}
    body = body or ""

    def take(s):
        for m in RSA_CITE.finditer(s or ""):
            url = rsa_url(m.group(1), m.group(2))
            if url:
                out.setdefault(m.group(0), url)

    for m in AMEND_WORD.finditer(body):
        stop = CLAUSE_END.search(body, m.end(), m.end() + 400)
        if stop:
            take(body[m.start():stop.start()])
    # "The following are repealed:" puts its targets AFTER the colon, one
    # roman numeral to a line, and the list runs to the next section.
    for m in REPEAL_LIST.finditer(body):
        nxt = NEXT_SECTION.search(body, m.end())
        end = min(nxt.start() if nxt else len(body), m.end() + 2000)
        take(PART_WORD.sub("", body[m.end():end]))
    # "RSA 21-I:19-a, relative to X, is repealed." -- the target is behind the
    # verb, so the window runs back to the start of that sentence.
    for m in REPEALED.finditer(body):
        lo = body.rfind(". ", max(0, m.start() - 300), m.start())
        take(body[(lo + 2 if lo != -1 else max(0, m.start() - 300)):m.start()])
    return out


_CONSTITUTION = []


def constitution_targets(body):
    """The articles a CACR's text says it changes, as parse_constitution reads
    them against collected/constitution.json, which is read once a build; []
    on a disk without that file."""
    if not _CONSTITUTION:
        _CONSTITUTION.append(PCON.load() or {})
    return PCON.cacr_targets(body, _CONSTITUTION[0])
