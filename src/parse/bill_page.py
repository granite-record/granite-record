#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-16.1
"""
A printing of a bill, read off its HTML: the version it says it is, the
amendments folded into it, the title, the sponsors, the committee, and the
text from the analysis down.

    import bill_page
    rec = bill_page.parse_text(html, "HB1442", "2026")

No network, and nothing written. Two readers share it, so a difference
between them is the printing's and never the parser's:

  fetch_bill_text.py      the bill's page as the General Court's web server
                          serves it, saved under bill_text/
  bill_text_from_db.py    the same printing as the General Court's database
                          holds it (db/LegislationText.psv, HTMLText)

It was fetch_bill_text.py's own until 16 October 2026 and moved here line
for line, so that the second reader could use it without importing a
fetcher. Read over the database's printings of 2025-2026, choosing each
bill's current one, it gives the record the web page gave for 2,192 of the
2,234 bills and the same words for the other 42, which differ only where the
dump turned a line break or a "|" inside the HTML into a space.
"""

import html
import re

WS = re.compile(r"\s+")
TAG = re.compile(r"<[^>]+>")


def text_of(doc):
    doc = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", doc,
                 flags=re.S | re.I)
    doc = re.sub(r"<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", doc, flags=re.I)
    t = TAG.sub(" ", doc)
    # EVERY ENTITY, NOT THE SIX SOMEBODY HAPPENED TO HIT. This was a list of
    # six replacements, so &ldquo; and &rdquo; went to the site as themselves:
    # 3,882 of them across the current term, 3,816 inside bill text and 41
    # inside the official analysis, where HB2 read
    # 'Modifies the definition of &ldquo;environmental review&rdquo;'.
    #
    # html.unescape knows the whole table and resolves numeric references too
    # (&#8209;, the non-breaking hyphen, appeared 42 times). It runs AFTER the
    # tags are stripped, so an escaped &lt;p&gt; in the bill's own words cannot
    # become markup.
    t = html.unescape(t)
    t = t.replace("\u00a0", " ")
    lines = [WS.sub(" ", ln).strip() for ln in t.splitlines()]
    return "\n".join(ln for ln in lines if ln)


# The page furniture, so it can be told apart from a bill. Anything that
# survives this and is still short is a page that did not carry the text.
CHROME = re.compile(
    r"skip to main content|general court of nh|quick links|helpful links|"
    r"contact a representative|contact a senator|redistricting information|"
    r"my gcnh portal|chaptered final version|documents & media|other resources",
    re.I)

# A NAVIGATION LABEL IS SHORT; A SECTION OF STATUTE IS NOT. These phrases are
# matched against a whole line, and the body of a bill is rendered a paragraph
# to a line, so a paragraph that happens to contain one of them was deleted
# entire. "other resources" is the one that bit: it is a menu heading on the
# General Court's site and it is also ordinary English. Across the 2,234
# cached pages of this term it cut 9 lines, every one of them the bill's own
# words and not one of them furniture -- 682 words of statute, on HB2,
# HB1606, SB127, SB193 and SB551. HB1606 defines "real property" as "land,
# buildings, crops, or other resources still attached to ... the land"; the
# published page then used the term 26 times and never defined it.
#
# The other ten phrases matched nothing at all on those pages, so the list was
# doing no work on a real bill and all of its work on the bill's text. It is
# kept rather than trimmed, because it still has to recognise an error page
# that came back 200, and because the next phrase to collide with a statute
# would be a different bug with the same cause -- "redistricting information"
# in an election bill, say. The length test is what stops that whole class:
# the furniture is a menu item of two to five words, and the shortest line
# this ever wrongly cut was 20.
CHROME_MAX_WORDS = 10


def strip_chrome(text):
    return "\n".join(
        ln for ln in text.splitlines()
        if not (CHROME.search(ln) and len(ln.split()) <= CHROME_MAX_WORDS))


# ---------------------------------------------------------------- parsing --
#
# What one of these pages looks like, from the probe:
#
#     HB 1442-FN - FINAL VERSION
#     5Mar2026... 1054h
#     04/16/2026 1384s
#     2026 SESSION
#     26-2729
#     12/06
#     HOUSE BILL 1442-FN
#     AN ACT permitting classification of individuals based on biological sex
#     SPONSORS: Rep. Layon, Rock. 13; Rep. Barbour, Hills. 35; ...
#     COMMITTEE: Judiciary
#     --------------------------------
#     <the analysis, then the bill itself>
#
# The two lines under the heading are the amendments folded into this text and
# the dates they were adopted: 1054h is 2026-1054h. So a bill's text states
# which amendments are in it, which is the join between an amendment and the
# version that carries it -- and it comes free with the text.

# THE FIRST HEADING THIS MATCHES IS TAKEN AS THE VERSION, so a heading shape
# it does not accept is not a missing version -- it is the wrong one. A bill
# with a fiscal note prints "SB 290-FN- FISCAL NOTE" as a section heading
# partway down, and that line matches. So SB139 and SB290 were published as
# "FN FISCAL NOTE" and "FISCAL NOTE": the text was the introduced bill both
# times, and only the label was wrong, which is the worse way round -- a
# reader is told they are looking at a fiscal note while reading the bill.
#
# Their own headings are printed "SB - AS INTRODUCED", with no number at all,
# and "SB 139 -FN - AS INTRODUCED", with a space before the -FN. Hence \d*
# rather than \d+, and the optional " -FN" group. Measured over all 2,234
# cached pages of the term: 2,232 read exactly as before, these 2 change, and
# no page lost a version it used to have. It agrees with the record -- the
# database's only printing of either bill is "Introduced", and no bill of this
# term has a "Fiscal Note" printing at all.
VERSION_RE = re.compile(
    r"^\s*(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s*\d*[\w-]*(?:\s+-[A-Z]+)?"
    r"\s*[-\u2013]\s*(?P<v>[A-Z][A-Z \u2019'/]{3,40})\s*$",
    re.M)
# "5Mar2026... 1054h", "04/16/2026 1384s"
STAMP_RE = re.compile(
    r"^\s*(?P<when>\d{1,2}\s*[A-Za-z]{3}\s*\d{4}|\d{2}/\d{2}/\d{4})[.\s]*"
    r"(?P<num>\d{3,4}[a-z])\s*$", re.M)
# Not everything the General Court passes is an act. A CACR proposes a
# constitutional amendment and opens "RELATING TO:"; a resolution opens "A
# RESOLUTION". Sorted alphabetically the first twenty bills are all CACRs,
# which is why a first run reported no title on every one of them.
# "2026 SESSION", printed under the heading. The page states its own session
# year, so nothing has to be told what it is -- and an amendment number built
# from a year nobody supplied comes out as "-1054h", which joins to nothing.
SESSION_RE = re.compile(r"^\s*(20\d{2})\s+SESSION\s*$", re.M | re.I)

TITLE_RE = re.compile(
    r"^\s*((?:AN ACT|A RESOLUTION|RELATING TO)\b.*?)$", re.M | re.I)
# A CACR states its question over the two lines after RELATING TO.
CACR_Q_RE = re.compile(
    r"^\s*PROVIDING THAT\b(?P<v>.*?)$", re.M | re.I)
SPONSORS_RE = re.compile(r"^\s*SPONSORS?:\s*(?P<v>.+?)$", re.M | re.I)
COMMITTEE_RE = re.compile(r"^\s*COMMITTEE:\s*(?P<v>.+?)$", re.M | re.I)
# The rule the General Court prints between the heading and the analysis.
RULE_RE = re.compile(r"^[\s\u2500-\u257F_=-]{12,}$", re.M)
# An amended bill heads its summary "AMENDED ANALYSIS", not "ANALYSIS". A
# pattern that wanted the bare word missed every amended bill and fell through
# to the printed rule instead, so the stored text began with sixty-five dashes.
ANALYSIS_RE = re.compile(r"^\s*(?:[A-Z]+\s+)?ANALYSIS\s*$", re.M | re.I)


def parse_text(html, bill, year):
    """The heading, the amendments it carries, and the bill itself."""
    body = strip_chrome(text_of(html))
    m_year = SESSION_RE.search(body[:900])
    year = str(year or "") or (m_year.group(1) if m_year else "")
    rec = {"bill": bill, "year": year, "chars": len(body)}

    m = VERSION_RE.search(body)
    if m:
        rec["version"] = WS.sub(" ", m.group("v")).strip()
    # The short forms as printed, and the full ones the docket uses, so a join
    # on either works without the caller having to know both.
    # Both forms, so a join on either works. Without a year there is no full
    # form to give, and a half-built one would look joinable and never match.
    stamps = []
    for s in STAMP_RE.finditer(body[:1200]):
        short = s.group("num")
        rec_s = {"date": WS.sub("", s.group("when")), "short": short}
        if year:
            rec_s["num"] = f"{year}-{int(short[:-1]):04d}{short[-1]}"
        stamps.append(rec_s)
    if stamps:
        rec["amendments_in_text"] = stamps
    for key, pat in (("title", TITLE_RE), ("sponsors_raw", SPONSORS_RE),
                     ("committee", COMMITTEE_RE)):
        mm = pat.search(body)
        if mm:
            rec[key] = WS.sub(" ", mm.group(1 if key == "title" else "v")).strip()
    # A CACR's title is the relating-to line; the proposal itself is the
    # sentence after it, and both belong together.
    q = CACR_Q_RE.search(body)
    if q and rec.get("title", "").upper().startswith("RELATING TO"):
        rec["title"] = (rec["title"].rstrip(". ") + ". Providing that"
                        + WS.sub(" ", q.group("v")).rstrip(". ") + ".")

    # The text proper starts after the heading block. Prefer the ANALYSIS
    # heading, fall back to the printed rule, and fall back again to the whole
    # thing rather than returning nothing.
    # From the analysis heading if there is one; otherwise from AFTER the rule
    # the General Court prints between the heading block and the text. Starting
    # AT the rule kept the rule.
    a_cut = ANALYSIS_RE.search(body)
    if a_cut:
        rec["text"] = body[a_cut.start():].strip()
    else:
        r_cut = RULE_RE.search(body)
        rec["text"] = body[r_cut.end():].strip() if r_cut else body
    rec["heading_only"] = len(rec["text"]) < 400
    return rec


def missing(rec):
    return [k for k in ("version", "title", "text") if not rec.get(k)]
