#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-07.1
"""
Whose count a row of ballot_results.json is, named from the row's own source.

    import ballot_source as BS
    BS.by(row)       # "Secretary of State", "Ballotpedia": a citation's first words
    BS.named(row)    # "the Secretary of State", "Ballotpedia": the same in a sentence
    BS.whose(row)    # "the Secretary of State's", "Ballotpedia's"

WHY ONE PLACE

Every page that says where the voters' count on a constitutional amendment
came from said "Ballotpedia" in words of its own: the bill's Votes tab
(app.js), its How it got here ("Ballotpedia's count", build_site_v2), the
data page (build_exports). On 7 October 2026 the person made the Secretary
of State the source of every row the voters have decided, and kept
Ballotpedia for the one still to come, so a page that names the source by
itself is wrong on one row or on seventeen. Each now asks here, with the
row, and the answer is the row's `source`.

THE NAME IS THE HOST'S. A row's source is the page its figures were read
from. sos.nh.gov is the Secretary of State's own site, which holds results
from 2016; before that the count is the Department of State's Manual for the
General Court, read from NHPR's scans of it (electiondatabase.nhpr.org) --
the Secretary of State's figures, which is whose they are named; the row's
`cite` says "(NHPR's scan)". A host not listed here is named by itself
rather than guessed at.
"""

import re

# host: (as a citation starts, as a sentence says it)
NAMES = {
    "sos.nh.gov": ("Secretary of State", "the Secretary of State"),
    "electiondatabase.nhpr.org": ("Secretary of State", "the Secretary of State"),
    "ballotpedia.org": ("Ballotpedia", "Ballotpedia"),
}


def host(row):
    """The host of the row's source, without "www.": "sos.nh.gov"."""
    return re.sub(r"^https?://(?:www\.)?([^/?#]+).*$", r"\1", (row or {}).get("source") or "")


def _names(row):
    h = host(row)
    return NAMES.get(h, (h, h))


def by(row):
    """Whose the row's count is, as a citation starts: "Secretary of State"."""
    return _names(row)[0]


def named(row):
    """Whose the row's count is, in a sentence: "the Secretary of State"."""
    return _names(row)[1]


def whose(row):
    """The possessive, in a sentence: "the Secretary of State's"."""
    return named(row) + "'s"
