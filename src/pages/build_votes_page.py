#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.4
"""
The votes page: /votes, a search of every roll call since 1999.

    python3 src/pages/build_votes_page.py --site site [--base URL]

WHAT IT WRITES: site/votes.html and its sitemap entry, and nothing else. The
page is the shell every record page is made from (shell.page) with a heading
and one lead; its list, its filters and its search are app.js's votes block
(THE VOTES PAGE), which reads votes/index.json and the term files that
build_votes.py writes. GR_VOTES, set here, is what makes app.js draw it.

LAID OUT AS THE BILL SEARCH IS (the owner on the bench, 24 November 2026:
"The votes page filters should be more similar to the left sidebar search
filters on bill and law pages"). The page writes what bills.html writes for
the bill search and build_rsa for the Laws page, in the same classes: across
the top the term picker beside the box and its Return key (.qline, .qbox),
and under them the Sort with the count beside it (.qhint); then the filters'
column (.facets) beside the list, and the Filter button (.ftoggle) that
opens them under 60em, worded the bill search's way with the votes' own
filters. app.js fills the pickers once the terms are known and draws the
groups into the column. Without scripts none of it is shown (app.css,
html:not(.js)): the noscript line says where the votes are.

WHAT IT SAYS OF ITS SCOPE is what it covers -- "Roll calls from 1999" -- and
nothing of what came before (the owner, 12 November 2026): the roll calls of
1989 to 1998 are on file in scanned journals and are a later stage, and a
page that said there were no recorded votes before 1999 would say what is not
known. It says nothing of how a party voted either: no label for a vote that
split the parties, no mark on a member who voted against theirs.

Not a tab of the header: a top-level page, reached from the header search's
row, a member's Votes tab, a bill's Votes tab and a session day.

Asks nobody anything: it writes a page of its own text.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse

import shell as S

PATH = "votes.html"
TITLE = "Votes"
DESC = ("Search every roll call of the New Hampshire House and Senate from 1999 by bill number "
        "or words, and see how each member voted.")
# ONE SENTENCE (the review of 14 November 2026): a second listed the filters
# drawn right under it, and the page speaks for itself.
LEAD = ("Every roll call of the New Hampshire House and Senate from 1999, with how each member "
        "voted.")
# What a roll call is, once, so that the page does not seem to be missing the votes that leave no
# member's name.
NOTE = ("A voice vote or a division records no member&rsquo;s vote, and is on the bill&rsquo;s "
        "page and its session day, not here.")
# THE FILTER BUTTON'S WORDS, the bill search's way ("Filter by topic, sponsor
# or committee"), naming the votes' own filters: three of the six, as the bill
# search's names three of its seven -- the first group, and a day's votes and a
# member's, which the design found most wanted after a bill's -- in the order
# the groups stand in. On one line at a phone's 360px with the count beside
# them (258px of its 264 in Chrome, 25 November 2026), where "chamber, date,
# result or member" took two.
TOGGLE = "Filter by chamber, date or member"


def body():
    return f"""<div class="vpage" id="vpage">
<h1 id="vhead">{TITLE}</h1>
<p class="lead">{LEAD}</p>
<p class="src fill">{NOTE}</p>
<div class="vtop" id="vctl" role="search" aria-label="Search the votes">
<form class="qline" id="vform" action="/votes"><label for="vterm" class="sr">Legislative term</label><select id="vterm" data-vf="term" title="Two-year term"></select><label for="vq" class="sr">Search the votes by bill number or words</label><div class="qbox"><input id="vq" name="q" type="search" spellcheck="false" autocomplete="off" disabled placeholder="Bill number or words"><button id="vgo" type="submit" disabled title="Search" aria-label="Search">&#8629;</button></div></form>
<div class="qhint"><label for="vsort" class="sr">Sort order</label><select id="vsort" data-vf="sort"></select><span id="vcount" role="status" aria-live="polite" aria-atomic="true">Loading&hellip;</span></div>
</div>
<div class="vlay" id="vlay">
<button class="ftoggle" id="vftoggle" type="button" aria-expanded="false" aria-controls="vfacets"><span>{TOGGLE}</span><span class="badge" hidden></span><span class="chev">&#9656;</span></button>
<aside class="facets" id="vfacets" aria-label="Filters"></aside>
<div class="vmain">
<p class="src vnote" id="vclose" hidden></p>
<div id="vlist"></div>
</div>
</div>
<noscript><p class="note">This page needs JavaScript to search. Without it, each bill&rsquo;s page lists its votes on its Votes tab, and each session day lists the votes taken.</p></noscript>
</div>"""


def page(site, base):
    html = S.page(S.template(site), path="/" + PATH, base=base, title=f"{TITLE} | Granite Record",
                  og_title=TITLE, description=DESC, globals={"GR_STATIC": True, "GR_VOTES": True},
                  og_type="website", noscript="", skip_label="Skip to the votes",
                  nav_current=PATH, sr_title="", cite=False)
    slot = '<div id="results"></div>'
    assert slot in html, f"{PATH}: the template has no results slot"
    return S.clean_links(html.replace(slot, f'<div id="results">{body()}</div>', 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    (site / PATH).write_text(page(site, base), encoding="utf-8")
    S.sitemap_merge(site, base, [base + S.canon("/" + PATH)], "/votes")
    print(f"  {PATH}: the votes page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
