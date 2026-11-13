#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.1
"""
The votes page: /votes, a search of every roll call since 1999.

    python3 src/pages/build_votes_page.py --site site [--base URL]

WHAT IT WRITES: site/votes.html and its sitemap entry, and nothing else. The
page is the shell every record page is made from (shell.page) with a heading
and one lead; its list, its filters and its search are app.js's votes block
(THE VOTES PAGE), which reads votes/index.json and the term files that
build_votes.py writes. GR_VOTES, set here, is what makes app.js draw it.

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
LEAD = ("Every roll call of the New Hampshire House and Senate from 1999, with how each member "
        "voted. Search by bill number or by words, then narrow by term, chamber, date, result, "
        "how close the vote was, the kind of question, or a member.")
# What a roll call is, once, so that the page does not seem to be missing the votes that leave no
# member's name.
NOTE = ("A voice vote or a division records no member&rsquo;s vote, and is on the bill&rsquo;s "
        "page and its session day, not here.")


def body():
    return f"""<div class="vpage" id="vpage">
<h1 id="vhead">{TITLE}</h1>
<p class="lead">{LEAD}</p>
<p class="src fill">{NOTE}</p>
<div id="vctl"></div>
<p class="src" id="vcount" role="status" aria-live="polite">Loading&hellip;</p>
<div id="vlist"></div>
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
    S.sitemap_merge(site, base, [base + S.canon(PATH)], "/votes")
    print(f"  {PATH}: the votes page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
