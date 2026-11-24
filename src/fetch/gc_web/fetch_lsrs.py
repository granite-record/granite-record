#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.10
"""
Next session's bill requests, before any of them is a bill.

    python3 src/fetch/gc_web/fetch_lsrs.py --probe     # what the page offers, saves nothing
    python3 src/fetch/gc_web/fetch_lsrs.py             # fetch the CSV, save it, write lsrs.json
    python3 src/fetch/gc_web/fetch_lsrs.py --parse     # re-read what is saved, no network

WHAT AN LSR IS

A Legislative Service Request is the first step in making a law: a legislator
asks the Office of Legislative Services to draft a bill, and the request is
given a number like 2027-0001. At that point it has a title and a prime
sponsor and nothing else -- no text, no committee, no hearing, no vote. When
drafting finishes and the bill is introduced it becomes an HB or an SB and
this file stops being the best record of it.

241 were on file for 2027 when this was written. They are worth publishing
because they are the earliest public sign of what the next session intends to
take up, and nothing else on this site can answer "what is coming" at all.

NOT EVERY REQUEST BECOMES A BILL. The General Court keeps a separate list of
withdrawn ones, and a request can disappear between two runs of this script.
That is a withdrawal, not a fetch error, and `--parse` keeps a request that
has gone rather than dropping it silently: the record that somebody asked for
a bill is true even after they stopped asking.

IT DISCOVERS THE CSV RATHER THAN GUESSING ITS ADDRESS

The search page offers a "Download CSV File" link. This loads that page, reads
the link out of it, and follows it. It does NOT construct the address.

That is not fastidiousness. This project's address has been blocked by the
General Court's firewall twice, and the first time was for asking for
filenames that did not exist. A guessed URL that 404s is exactly that
behaviour. If the link is not on the page, this says so and stops, which is a
report a person can act on rather than a probe somebody else has to absorb.

Two requests, a pause between them, and it identifies itself.

GITHUB'S NIGHTLY RUNS IT NOW (30 September 2026). nightly.take_lsrs() runs it
every night, keeps the list whole, and lsrs.json is the night's file in the
kit rather than one committed to git. On a laptop that has stood down it
refuses; --parse, which asks nobody, still works.

THE TEXT, ONCE IT IS PUBLIC (the owner, 17 November 2026: "Once the
co-sponsors and sponsor have signed off, the bill text shows as a PDF on the
lsr search page along with the co-sponsors"). Until then nothing here took
a text: the CSV's four columns -- LSR Number, Bill Type, LSR Title, Sponsors,
as it was saved on 18 September -- carry no link, and the results page, read
only when the CSV could not be had, was read for those four fields alone.
Nobody here has yet seen a request with a text, so where the link will be is
not known [a guess, written down as one]. Two places are read for it, and
neither constructs an address:

  the CSV          a column whose header names a PDF, a text, a link or an
                   address, if the list grows one (parse_csv)
  the results page the page the search page links as "see all Bill
                   Requests" (results_link), one request more a night, read
                   for a link in each request's own row of its table that
                   names a PDF or the text (text_links). A row that names two
                   requests, or two such links, gives none: a text on the
                   wrong request is a wrong fact. Only the General Court's own
                   addresses are taken

The address goes on the request in lsrs.json as "text_pdf". --texts is the
night's drain of them (nightly.take_lsr_texts, on GitHub only): the PDFs this
disk does not hold, a few a night, as the calendars' drain asks for its
documents -- the refusal check first, the lock, 15 seconds apart with jitter
and as long before the first, one refusal or two dropped connections ending
the run, a document asked for three times before it is left. Each lands at
archive/lsr_text/<request>.pdf, with what was asked and how it ended in
archive/lsr_texts.json. --read-texts, which asks nobody, writes the text of
each beside it (<request>.txt) with pdftotext -layout, the program the
calendars' texts come from; the kit carries the text and the record, never
the PDF.

AND THE CO-SPONSORS (split_sponsors). The Sponsors column is read as a list
the day it becomes one: names parted by semicolons, or by commas where a role
mark shows the list is written that way ("Ellen Read (Prime), Bob Roe"), and
a role before a name as well as after it ("(Prime) Ellen Read", as the
results page prints the prime). Which form the General Court will use is not
known either; preflight's data check says on the night when a name still
reads as a list.

AND THE REQUESTS THE CSV DOES NOT HOLD (the night of 23 November 2026). The
CSV held 908 requests, the newest of 21 November, while the page of every
request (results_link) listed 1,264 the same evening ("LSR's Found: 1264"):
the CSV had stopped growing and the page had not. So the page, which the
night already asked for every request's text link, is read every night now,
and each request it lists that the CSV does not is taken from it
(with_page_rows): the number, the kind, the title and the sponsors, the
prime first and the co-sponsors after, as the page prints them -- "Sponsors:
(Prime) Nancy Murphy , David Watters, Rosemarie Rung" (page_listed). A
request on both keeps the CSV's row, and no CSV row is dropped or changed for
the page. A request taken from the page carries "from_page" in lsrs.json
until the CSV lists it.

The page's rows are used only when they add up: as many requests read as the
page says it lists, each with its kind, a title and a prime sponsor. Where
they do not, or the page is not read, nothing is taken from it, a request
taken from it on an earlier night is kept as it stood rather than marked
withdrawn (merge), and the night's line says so (LISTED: how many the CSV
held, how many the page listed, how many were taken from it). Nobody here has
seen the page's HTML: the reader was written from the owner's printout of the
page [a guess at its markup], and the page's own count is the check on it.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import html as _html
import io
import json
import os
import random
import re
import refusal
import time
import urllib.error
import urllib.parse
import urllib.request

SEARCH = "https://gc.nh.gov/lsr_search/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
RAW_PAGE = Path("archive/lsr_search.html")
RAW_CSV = Path("archive/lsrs.csv")
OUT = Path("lsrs.json")
PAUSE = 5.0

# THE CSV IS NOT A LINK. It is an ASP.NET postback:
#
#   <a href="javascript:__doPostBack('ctl00$pageBody$lnkCVS','')">Download CSV File</a>
#
# so getting the file means POSTing the form the way the browser does, with
# the control's name in __EVENTTARGET and the page's own hidden state sent
# back with it. That is what a click does; it is not a second address, and it
# is still not a guess -- the target is read out of the page.
CSV_LINK = re.compile(
    r"<a[^>]+__doPostBack\(&#39;([^&]+)&#39;[^>]*>\s*[^<]*\bCSV\b", re.I)
RESULTS = "https://gc.nh.gov/lsr_search/LSR_Results.aspx"
HIDDEN = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION")

# The rows of the page of every request (page_listed; AND THE REQUESTS THE CSV
# DOES NOT HOLD), as the owner's printout of 23 November 2026 shows one: the
# number, the kind, "Title:" and the title, then "Sponsors: (Prime)" and the
# names. A row begins at a number followed by its kind and "Title:", and runs
# to the next; any kind of two to five capitals, so that HJR and SJR, which
# the page lists, are rows too.
ROW_START = re.compile(r"(?<![\w-])(\d{4}-\d{3,4})\s*([A-Z]{2,5})\s*(?i:title)\s*:")
# "LSR's Found: 1264", the count the page states above its rows.
FOUND = re.compile(r"\bLSR\W{0,2}s\s+found\s*:?\s*(\d[\d,]*)", re.I)
# The words this says tonight's lists in, after which nightly.take_lsrs finds
# them in its output and puts them on the night's line.
LISTED = "tonight's lists: "

# "2027-0001", the shape of a request number, and the session it belongs to.
LSR_NO = re.compile(r"^\s*(\d{4})-(\d{3,4})\s*$")

# THE TEXT, ONCE IT IS PUBLIC (the docstring). Where each PDF and its text are
# kept, the record of what was asked for each, and the drain's pace and budget.
# build_lsrs.REQUEST_TEXTS reads the same folder; preflight holds the two equal.
TEXTS = Path("archive/lsr_text")
TEXT_STATE = Path("archive/lsr_texts.json")
TEXT_PAUSE = 15.0
TEXT_BUDGET = 10
# The General Court's own hosts: a link anywhere else is not taken.
GC_HOSTS = ("gc.nh.gov", "www.gc.nh.gov", "gencourt.state.nh.us", "www.gencourt.state.nh.us")
# A request's number inside a row of the results page, and a link in it.
LSR_IN = re.compile(r"(?<![\d-])(\d{4}-\d{3,4})(?![\d-])")
ANCHOR = re.compile(r"<a\b[^>]*?\bhref\s*=\s*([\"'])(.*?)\1[^>]*>(.*?)</a\s*>", re.I | re.S)
# A link that names the text: "pdf" or "text" in its address (billText.aspx,
# txtFormat=pdf, a .pdf), or "PDF", "Text" or "Bill Text" in its words.
TEXT_ADDRESS = re.compile(r"pdf|text", re.I)
TEXT_WORDS = re.compile(r"\b(?:pdf|bill\s+text|text)\b", re.I)


def gc_url(href, base=SEARCH):
    """An address the page gives, made whole against `base`, where it is the
    General Court's own (GC_HOSTS) over http or https; "" for anything else."""
    href = _html.unescape(str(href or "")).strip()
    if not href or href.lower().startswith(("javascript:", "mailto:", "#")):
        return ""
    url = urllib.parse.urljoin(base, href)
    p = urllib.parse.urlsplit(url)
    return url if p.scheme in ("http", "https") and p.hostname in GC_HOSTS else ""


def results_link(html, base=SEARCH):
    """The address of the page of every request, as the search page links it
    ("Click here to see all Bill Requests": LSR_Results.aspx, no query), or
    None where the page offers none -- then it is not asked for."""
    for _q, href, _label in ANCHOR.findall(html or ""):
        url = gc_url(href, base)
        p = urllib.parse.urlsplit(url)
        if url and not p.query and p.path.lower().endswith("/lsr_results.aspx"):
            return url
    return None


def text_links(html, base=RESULTS):
    """({request: the address of its text}, [requests whose row gave two]).

    The results page is read a row of its table at a time (</tr>), because
    nobody has seen where a text's link will sit [a guess]: a row naming one
    request, and one link in it that names a PDF or the text (TEXT_WORDS, in
    its address or its words), gives that request its link. A row naming two
    requests gives none, and a row with two such links is listed, not read.
    A page with no table rows gives nothing."""
    out, twice = {}, []
    for row in re.split(r"</tr\s*>", html or "", flags=re.I):
        # From the row's own opening tag: what stands between rows is no row's.
        start = row.lower().rfind("<tr")
        if start < 0:
            continue
        row = row[start:]
        nums = set(LSR_IN.findall(re.sub(r"<[^>]+>", " ", row)))
        if len(nums) != 1:
            continue
        num = nums.pop()
        links = set()
        for _q, href, label in ANCHOR.findall(row):
            url = gc_url(href, base)
            p = urllib.parse.urlsplit(url)
            words = _html.unescape(re.sub(r"<[^>]+>", " ", label))
            if url and (TEXT_ADDRESS.search(urllib.parse.unquote(f"{p.path}?{p.query}"))
                        or TEXT_WORDS.search(words)):
                links.add(url)
        if len(links) == 1:
            out[num] = links.pop()
        elif links:
            twice.append(num)
    return out, sorted(twice)


def refused(why):
    """Record a refusal and stop with status 2, as every fetcher of the
    General Court does (refusal.note)."""
    refusal.note("fetch_lsrs", why)
    print(f"  REFUSED: {why}. refusal.py now holds the lane; netcheck.py says what "
          "kind of refusal it was.")
    sys.exit(2)


def get(url, timeout=60):
    """One request, identified, with a refusal classified rather than guessed.

    AND THE BLOCK PAGE (7 October 2026). The firewall serves its page with a
    200, which this returned as the search page: "nothing on that page offers
    a CSV", and no refusal on file for the next fetch to read. Read as
    refusal.classify reads it, and a refusal ends the run with status 2 where
    it ended with 1."""
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body, enc = r.read(), r.headers.get_content_charset() or "utf-8"
    except Exception as e:                              # noqa: BLE001
        if refusal.classify(e) == "refused":
            refused(f"{type(e).__name__}: {e} from {url}")
        sys.exit(f"  {type(e).__name__}: {e} from {url}")
    if refusal.classify(body=body[:4000].decode(enc, "replace")) == "refused":
        refused(f"the firewall's block page, served as 200, from {url}")
    return body, enc


def find_csv(html):
    """The postback target that offers the CSV, or None with nothing assumed."""
    m = CSV_LINK.search(html)
    return m.group(1) if m else None


def hidden_fields(html):
    """The form state ASP.NET requires back with any postback."""
    out = {}
    for f in HIDDEN:
        m = re.search(r'id="' + f + r'"[^>]*value="([^"]*)"', html)
        if m:
            out[f] = html_unescape(m.group(1))
    return out


def html_unescape(s):
    import html as _h
    return _h.unescape(s)


def post(url, fields, timeout=90):
    """The form, submitted the way the page's own button submits it."""
    data = urllib.parse.urlencode(fields).encode("ascii")
    req = urllib.request.Request(url, data=data, headers={
        **UA, "Content-Type": "application/x-www-form-urlencoded",
        "Referer": url})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            got = (r.read(), r.headers.get_content_charset() or "utf-8",
                   r.headers.get("Content-Type", ""),
                   r.headers.get("Content-Disposition", ""))
    except Exception as e:                              # noqa: BLE001
        if refusal.classify(e) == "refused":
            refused(f"{type(e).__name__}: {e} posting to {url}")
        sys.exit(f"  {type(e).__name__}: {e} posting to {url}")
    # The block page answering the postback was read as "the postback did not
    # return a file", and the results page asked for next (get's note).
    if refusal.classify(body=got[0][:4000].decode(got[1], "replace")) == "refused":
        refused(f"the firewall's block page, served as 200, posting to {url}")
    return got


def page_text(html):
    """The page of every request as text, a line to each piece of it: comments,
    scripts and styles out, a link whose words name a text out (text_links
    reads those; one is no part of a title), and every tag a line break."""
    html = re.sub(r"<!--.*?-->|<(script|style)\b.*?</\1\s*>", " ", html or "", flags=re.I | re.S)
    html = ANCHOR.sub(lambda m: " " if TEXT_WORDS.search(
        _html.unescape(re.sub(r"<[^>]+>", " ", m.group(3)))) else m.group(0), html)
    text = _html.unescape(re.sub(r"<[^>]+>", "\n", html))
    text = re.sub(r"[^\S\n]+", " ", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def page_sponsors(words):
    """(prime, [co-sponsors]) from what follows "Sponsors:" in a row of the page
    of every request: the role mark and the names parted by commas, each name
    on a line of its own where the page links it -- "(Prime) Nancy Murphy ,
    David Watters, Rosemarie Rung". The list ends at the first line no comma
    joins to it, because what follows is not a name (the page's foot, after
    its last row). A Jr. or a numeral keeps its name, and the names are read
    as split_sponsors reads them: the one marked Prime is the prime, else the
    first."""
    s = re.sub(r"^\s*(\([^()\n]*\))\s*", r"\1 ", (words or "").strip())
    s = re.sub(r",\s*\n\s*", ", ", re.sub(r"\s*\n\s*,", ",", s))
    parts = []
    for bit in (b.strip() for b in s.split("\n", 1)[0].split(",")):
        if parts and re.fullmatch(r"(?:jr|sr|ii|iii|iv)\.?", bit, re.I):
            parts[-1] = f"{parts[-1]} {bit}"
        elif bit:
            parts.append(bit)
    return split_sponsors("; ".join(parts))


def page_listed(html):
    """([rows], why): the requests the page of every request lists, each in
    parse_csv's shape, and "" -- or [] and why they cannot be used.

    Used only when they add up: the page states how many it lists ("LSR's
    Found: 1264", FOUND) and as many are read, each with its kind, a title,
    and a prime sponsor after its "Sponsors:". A request printed twice the same
    way is one request; printed twice differently, the page is not used.
    Nobody here has seen the page's HTML [a guess, written down as one], so a
    page that does not add up is a page misread, never a smaller list.
    """
    text = page_text(html)
    starts = list(ROW_START.finditer(text))
    if not starts:
        return [], "no request could be read off it"
    rows, bad = {}, []
    for i, m in enumerate(starts):
        chunk = text[m.end():starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        num, no = m.group(1), LSR_NO.match(m.group(1))
        part = re.split(r"(?i)\bsponsors\s*:", chunk, maxsplit=1)
        title = " ".join(part[0].split())
        prime, co = page_sponsors(part[1]) if len(part) == 2 else ("", [])
        row = {"lsr": num, "session": int(no.group(1)) if no else 0, "body": m.group(2).upper(),
               "title": title, "sponsor": prime, "cosponsors": co, "withdrawn": False}
        if not (no and title and prime) or rows.setdefault(num, row) != row:
            bad.append(num)
    if bad:
        return [], f"{len(bad)} of its rows could not be read: {', '.join(sorted(set(bad))[:3])}"
    found = FOUND.search(text)
    if not found:
        return [], "it states no count to check its rows against"
    if int(found.group(1).replace(",", "")) != len(rows):
        return [], f"it says {int(found.group(1).replace(',', ''))} and {len(rows)} could be read"
    return list(rows.values()), ""


def parse_results_html(html):
    """The results page's requests (page_listed), for when the CSV cannot be
    had; [] where they cannot be used.

    Its rows carry exactly what an LSR has -- number, body, title, prime
    sponsor and co-sponsors -- so nothing is lost by reading them; it is only
    more fragile than a file with headers, which is why it is the fallback and
    not the first choice.
    """
    return page_listed(html)[0]


def with_page_rows(rows, page):
    """(rows, whether the page was used, what to say) -- the CSV's `rows`, and
    after them each request the page of every request lists and the CSV does
    not (page_listed), marked "from_page" (AND THE REQUESTS THE CSV DOES NOT
    HOLD). `page` is the page's HTML, or None where it was not read. No CSV
    row is dropped or changed for the page, and where its rows cannot be
    used nothing is taken from it and the words say why."""
    if page is None:
        return rows, False, f"the CSV held {len(rows)}, the page was not read, none taken from it"
    got, why = page_listed(page)
    if why:
        return rows, False, (f"the CSV held {len(rows)}, the page could not be used ({why}), "
                             "none taken from it")
    have = {r["lsr"] for r in rows}
    taken = [dict(r, from_page=True) for r in got if r["lsr"] not in have]
    return rows + taken, True, (f"the CSV held {len(rows)}, the page listed {len(got)}, "
                                f"{len(taken)} taken from the page")


def parse_csv(text):
    """The rows, by header name rather than by column position.

    A column order is not a promise, and this file is somebody else's. Every
    field is matched on a substring of its header so that "LSR #", "LSR
    Number" and "LSRNumber" all land in the same place.
    """
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise SystemExit("  the CSV is empty")
    head = [h.strip().lower() for h in rows[0]]

    def col(*names):
        for i, h in enumerate(head):
            if any(n in h for n in names):
                return i
        return None

    ix = {"lsr": col("lsr", "number", "request"), "body": col("body", "chamber", "type"),
          "title": col("title", "subject"), "sponsor": col("sponsor", "prime", "member")}
    missing = [k for k, v in ix.items() if v is None]
    if missing:
        raise SystemExit(
            f"  the CSV has no column for {', '.join(missing)}.\n"
            f"  Its headers are: {rows[0]}\n"
            "  Match them in parse_csv rather than reading by position.")
    # A LINK TO THE TEXT, if the list grows a column for one (THE TEXT, ONCE
    # IT IS PUBLIC): the first header not read above that names a PDF, a
    # text, a link or an address. Only the General Court's own addresses.
    tcol = next((i for i, h in enumerate(head) if i not in ix.values()
                 and re.search(r"pdf|text|link|url|document", h)), None)

    out = []
    for r in rows[1:]:
        if not any(x.strip() for x in r):
            continue
        def g(k):
            i = ix[k]
            return r[i].strip() if i < len(r) else ""
        num = g("lsr")
        m = LSR_NO.match(num)
        if not m:
            continue
        prime, co = split_sponsors(g("sponsor"))
        link = gc_url(r[tcol].strip(), SEARCH) if tcol is not None and tcol < len(r) else ""
        out.append({"lsr": num, "session": int(m.group(1)),
                    # NOT truncated. The column carries CACR and HCR as well as
                    # HB and HR, and a two-character slice turned those into
                    # "CA" and "HC", which are not kinds of anything.
                    "body": g("body").strip().upper(),
                    "title": " ".join(g("title").split()),
                    "sponsor": prime, "cosponsors": co,
                    **({"text_pdf": link} if link else {}),
                    "withdrawn": False})
    if not out:
        raise SystemExit(
            f"  {len(rows)-1} rows and not one carried a request number of the "
            "shape 2027-0001. That is a format change, not an empty session.")
    return out


ROLE = re.compile(r"\s*\(([^)]*)\)\s*$")
# The role before the name, as the results page prints the prime: "(Prime) Ellen Read".
LEAD_ROLE = re.compile(r"^\s*\(([^)]*)\)\s*")


def split_sponsors(field):
    """"Ellen Read (Prime)" -> ("Ellen Read", []).

    Every request carries exactly one name today, because a request is made by
    one member. The column is named "Sponsors" all the same, so this reads a
    list and separates the one marked Prime from any others rather than
    assuming the singular it currently always is -- co-sponsors appear once a
    bill is drafted, and that is the same column.

    The role marker is dropped from the name: "(Prime)" describes the row, and
    printing it beside every name would put the word on the page 241 times to
    say what the field already means.

    AND THE FORMS NOT SEEN YET (17 November 2026; the docstring's THE
    CO-SPONSORS): a part parted by commas where a role mark is followed by
    one ("Ellen Read (Prime), Bob Roe, Jane Doe"), a Jr. or a numeral set off
    by a comma kept with its name ("Bob Roe Jr."); and the role before the
    name ("(Prime) Ellen Read"). Without a role mark a comma parts nothing:
    "Roe, Bob" is one name.
    """
    prime, co = "", []
    parts = []
    for part in re.split(r"\s*;\s*", (field or "").strip()):
        if not re.search(r"\)\s*,", part):
            parts.append(part)
            continue
        for bit in (b.strip() for b in part.split(",")):
            if parts and bit and re.fullmatch(r"(?:jr|sr|ii|iii|iv)\.?", bit, re.I):
                parts[-1] = f"{parts[-1]} {bit}"
            else:
                parts.append(bit)
    for part in parts:
        if not part:
            continue
        m = ROLE.search(part) or LEAD_ROLE.match(part)
        role = (m.group(1) if m else "").strip().lower()
        name = " ".join(LEAD_ROLE.sub("", ROLE.sub("", part)).split())
        if not name:
            continue
        if "prime" in role and not prime:
            prime = name
        else:
            co.append(name)
    if not prime and co:
        prime, co = co[0], co[1:]
    return prime, co


def merge(new, page_read=True):
    """New rows over old, and a request that has gone is kept and marked.

    A request vanishing between runs is a withdrawal, which is a fact about
    the record rather than a gap in it. Dropping it would make the site
    quietly disagree with what it said last week.

    Or it is an introduction, which the list alone cannot tell from a
    withdrawal: a request drafted and filed becomes a bill. The flag says only
    that it left the list, and build_lsrs.became_bills reads the bills to say
    which -- a request whose number a bill carries reads "Introduced as HB 45".

    AND A REQUEST TAKEN FROM THE PAGE (AND THE REQUESTS THE CSV DOES NOT
    HOLD). One the CSV lists is the CSV's from then on, and loses its
    "from_page". On a night the page of every request was not read or could
    not be used (`page_read` false), one taken from it before that the CSV
    does not list is kept as it stood: not read tonight is not gone.
    """
    old = {}
    if OUT.exists():
        try:
            for r in json.loads(OUT.read_text(encoding="utf-8")):
                old[r["lsr"]] = r
        except (ValueError, OSError, KeyError):
            old = {}
    seen = {r["lsr"] for r in new}
    gone = 0
    for k, r in old.items():
        if k not in seen and not r.get("withdrawn") and (page_read or not r.get("from_page")):
            r["withdrawn"] = True
            gone += 1
    merged = {**old, **{r["lsr"]: {**old.get(r["lsr"], {}), **r} for r in new}}
    for r in new:
        if not r.get("from_page"):
            merged[r["lsr"]].pop("from_page", None)
    return [merged[k] for k in sorted(merged)], gone


def with_text_links(rows, page):
    """Give each row the link the results page `page` holds for its text
    (text_links), and say how many have one. A row keeps a link it already
    has (the CSV's, or an earlier night's through merge)."""
    links, twice = text_links(page or "")
    for r in rows:
        if r.get("lsr") in links and not r.get("text_pdf"):
            r["text_pdf"] = links[r["lsr"]]
    n = sum(1 for r in rows if r.get("text_pdf"))
    print(f"  {n} of {len(rows)} requests link their text"
          + (f"; {len(twice)} row(s) with two links left unread: {', '.join(twice[:6])}"
             if twice else ""))
    return n


# ---- the texts: the night's drain (THE TEXT, ONCE IT IS PUBLIC) ----------------

def load_rows():
    """lsrs.json's rows, or [] where it is not here or will not read."""
    try:
        rows = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def load_state():
    """archive/lsr_texts.json: {request: {"url", "state", "attempts", "error",
    "bytes", "fetched", "text"}}, {} where there is none yet."""
    try:
        d = json.loads(TEXT_STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in d.items() if isinstance(v, dict)} if isinstance(d, dict) else {}


def save_state(state):
    TEXT_STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TEXT_STATE.with_name(TEXT_STATE.name + ".part")
    tmp.write_text(json.dumps(dict(sorted(state.items())), indent=1), encoding="utf-8")
    os.replace(tmp, TEXT_STATE)


def texts_wanted(rows=None, state=None):
    """[(request, address)] the list links a text for and this disk has not
    settled: never asked for, or asked for at another address (a new link is
    a new document), or still to be asked again. A text fetched (held), not
    served (gone) or asked for three times (failed) at the address the list
    gives now is not asked for again."""
    rows = load_rows() if rows is None else rows
    state = load_state() if state is None else state
    out = []
    for r in rows:
        num, url = str(r.get("lsr") or ""), str(r.get("text_pdf") or "")
        if not (LSR_NO.match(num) and url):
            continue
        s = state.get(num) or {}
        if s.get("url") == url and s.get("state") in ("held", "gone", "failed"):
            continue
        out.append((num, url))
    return sorted(out)


def _fetch(url, timeout=60):
    """One document, identified, its bytes."""
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def drain_texts(a, held):
    """Up to --budget of texts_wanted(), fetched. 0 done, 1 stopped, 2 refused:
    the calendars' drain's rules (fetch_calendar_archive.drain), so the lane
    and the night read its status as they read that one's."""
    state, stopped = load_state(), ""
    todo = texts_wanted(load_rows(), state)
    n = min(len(todo), a.budget)
    print(f"{len(todo):,} request text(s) wanted, taking {n:,} this run about {a.delay:g}s apart")
    got = fail = run = dropped = 0
    try:
        for i, (num, url) in enumerate(todo[:a.budget], 1):
            if a.night or i > 1:
                # Paced, with jitter; and on the night a pause before the first
                # too, because the night asked this address a moment before.
                time.sleep(a.delay * random.uniform(0.75, 1.25))
            # Immediately before the request: a refusal another process met, or
            # a lane gone, while this one waited, stops it here.
            if refusal.MARK.exists():
                stopped = "refused"
                print("\narchive/refused.json is on file. Stopping.")
                break
            if not held.still():
                stopped = "the lane"
                print("\nThe lane holding archive/.lock is gone. Stopping.")
                break
            s = state.setdefault(num, {})
            if s.get("url") != url:
                s.clear()
                s["url"] = url
            try:
                blob = _fetch(url)
                kind = refusal.classify(body=blob[:4000].decode("utf-8", "replace"))
                why = "the firewall's block page, served as 200" if kind else ""
                if not kind and not blob.startswith(b"%PDF"):
                    kind, why = "failed", f"not a PDF ({len(blob):,} bytes)"
            except Exception as e:                          # noqa: BLE001
                kind, why = refusal.classify(e) or "failed", f"{type(e).__name__}: {e}"
            if kind:
                s["attempts"] = int(s.get("attempts") or 0) + 1
                s["error"] = why[:180]
                fail += 1
                print(f"  [{i}] {num}: {kind}: {s['error'][:80]}", flush=True)
                if kind == "refused":
                    refusal.note("fetch_lsrs", s["error"])
                    stopped = "refused"
                    print("\nRefused. Stopping and not coming back today.\npython3 netcheck.py "
                          "says what kind of refusal it is without making it worse.")
                    break
                if kind == "missing":
                    # Linked by the list and not served: the list is out of date,
                    # and asking again would not change that.
                    s["state"] = "gone"
                    continue
                s["state"] = "failed" if s["attempts"] >= 3 else "wanted"
                run += 1
                if kind == "dropped":
                    dropped += 1
                    if dropped >= 2:
                        refusal.note("fetch_lsrs", s["error"])
                        stopped = "refused"
                        print("\nTwo dropped connections this run. Stopping and not coming "
                              "back today.")
                        break
                if run >= 2:
                    stopped = "two in a row"
                    print("\nTwo in a row. Stopping.")
                    break
                time.sleep(120 if kind == "dropped" else a.delay * 3)
                continue
            run = 0
            TEXTS.mkdir(parents=True, exist_ok=True)
            pdf = TEXTS / f"{num}.pdf"
            # A part file, then a rename; and the text of an earlier address
            # goes, so --read-texts reads this one.
            tmp = pdf.with_name(pdf.name + ".part")
            tmp.write_bytes(blob)
            os.replace(tmp, pdf)
            pdf.with_suffix(".txt").unlink(missing_ok=True)
            s.update(state="held", bytes=len(blob), error="",
                     fetched=time.strftime("%Y-%m-%dT%H:%M:%S"))
            s.pop("text", None)
            got += 1
    finally:
        save_state(state)
    print(f"\n{got:,} fetched, {fail} failed")
    if stopped == "refused":
        return 2
    return 1 if stopped else 0


def read_texts():
    """The text of each PDF fetched, beside it, by pdftotext -layout
    (extract_calendar_text.extract, the calendars' own reading): asks nobody.
    A PDF that gives no text is recorded so ("text": "none"), and is not
    fetched again for it. Returns how many were read."""
    import extract_calendar_text as ET
    state, n, none = load_state(), 0, []
    for num, s in sorted(state.items()):
        pdf = TEXTS / f"{num}.pdf"
        txt = pdf.with_suffix(".txt")
        if s.get("state") != "held" or not pdf.is_file() or (txt.is_file() and txt.stat().st_size):
            continue
        text, how = ET.extract(pdf, layout_only=True)
        if text and text.strip():
            tmp = txt.with_name(txt.name + ".part")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, txt)
            s["text"] = how
            n += 1
        else:
            s["text"] = "none"
            none.append(f"{num} ({how})")
    save_state(state)
    print(f"  the text of {n} request PDF(s) read" + (f"; none in {', '.join(none)}" if none else ""))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="load the search page and report what it offers; save nothing")
    ap.add_argument("--parse", action="store_true",
                    help="re-read the saved CSV; touches no network")
    ap.add_argument("--texts", action="store_true",
                    help="fetch the request texts the list links and this disk does not hold: "
                         "the night's drain (nightly.take_lsr_texts)")
    ap.add_argument("--read-texts", action="store_true",
                    help="the text of each request PDF fetched, beside it; touches no network")
    ap.add_argument("--budget", type=int, default=TEXT_BUDGET,
                    help=f"(--texts) texts this run, then stop (default {TEXT_BUDGET})")
    ap.add_argument("--delay", type=float, default=TEXT_PAUSE,
                    help=f"(--texts) seconds between requests, jittered (default {TEXT_PAUSE:g})")
    ap.add_argument("--night", action="store_true",
                    help="(--texts) the night's: a pause before the first request as well")
    a = ap.parse_args()

    # --read-texts asks nobody, as --parse does: before the check.
    if a.read_texts:
        read_texts()
        return 0
    # --parse asks nobody, so neither a refusal nor GitHub's night stops it:
    # the check comes after it, as fetch_legislation.py's does.
    if a.parse:
        if not RAW_CSV.exists():
            raise SystemExit(f"  {RAW_CSV} is not here. Run without --parse first.")
        rows = parse_csv(RAW_CSV.read_text(encoding="utf-8", errors="replace"))
        # And the page of every request saved beside it, where it is
        # (AND THE REQUESTS THE CSV DOES NOT HOLD).
        saved = RAW_PAGE.with_name("lsr_results.html")
        rows, page_read, listed = with_page_rows(
            rows, saved.read_text(encoding="utf-8", errors="replace") if saved.is_file() else None)
        merged, gone = merge(rows, page_read)
        OUT.write_text(json.dumps(merged, indent=1), encoding="utf-8")
        print(f"{len(rows)} requests parsed -> {OUT}"
              + (f"; {gone} newly marked withdrawn" if gone else ""))
        print(f"  {LISTED}{listed}")
        return 0
    # One writer per file: the night takes the requests, and lsrs.json reaches
    # this machine from R2.
    refusal.stand_down("The LSR fetch", "GitHub's nightly takes next session's bill "
                       "requests now, and lsrs.json reaches this machine from R2.")
    refusal.check("The LSR fetch")
    if a.texts:
        with refusal.hold("the request texts") as held:
            return drain_texts(a, held)

    print(f"asking {SEARCH} for the page that offers the file")
    body, enc = get(SEARCH)
    html = body.decode(enc, "replace")
    RAW_PAGE.parent.mkdir(parents=True, exist_ok=True)
    RAW_PAGE.write_text(html, encoding="utf-8")
    target = find_csv(html)
    if not target:
        raise SystemExit(
            "  nothing on that page offers a CSV.\n"
            f"  The page is saved at {RAW_PAGE}; read it and fix CSV_LINK.\n"
            "  Nothing else is asked for -- a guessed address is how this "
            "address was blocked the first time.")
    print(f"  the CSV is a postback to {target}")
    if a.probe:
        print("  --probe: stopping here, nothing downloaded")
        return 0

    fields = hidden_fields(html)
    missing = [f for f in HIDDEN if f not in fields]
    if missing:
        print(f"  WARNING: the form is missing {', '.join(missing)}; "
              "the postback may be refused")
    time.sleep(PAUSE)
    raw, enc2, ctype, disp = post(SEARCH, {**fields, "__EVENTTARGET": target,
                                           "__EVENTARGUMENT": ""})
    body_text = raw.decode(enc2, "replace")
    looks_csv = ("csv" in ctype.lower() or "csv" in disp.lower()
                 or ("," in body_text[:400] and "<html" not in body_text[:400].lower()))
    page = None
    if looks_csv:
        RAW_CSV.write_bytes(raw)
        print(f"  {len(raw):,} bytes of CSV -> {RAW_CSV}")
        rows = parse_csv(body_text)
    else:
        # The postback answered with a page rather than a file. The results
        # page carries the same four fields, so read those instead of asking
        # again in a different way.
        print("  the postback did not return a file; reading the results page")
        time.sleep(PAUSE)
        raw2, enc3 = get(RESULTS)
        RAW_PAGE.with_name("lsr_results.html").write_bytes(raw2)
        page = raw2.decode(enc3, "replace")
        rows, why = page_listed(page)
        if not rows:
            raise SystemExit(
                f"  the results page yielded no requests either ({why}). Both are saved "
                "under archive/; read them before asking again.")
        rows = [dict(r, from_page=True) for r in rows]
        print(f"  {len(rows)} requests read from the results page")
        page_read, listed = True, (f"the CSV was not served, the page listed {len(rows)}, "
                                   f"{len(rows)} taken from the page")
    # THE REQUESTS THE CSV DOES NOT HOLD, AND THE LINKS TO THE TEXTS (THE TEXT,
    # ONCE IT IS PUBLIC): the page the search page links for every request,
    # read every night, one request more, for the requests it lists that the
    # CSV does not and for each request's text link where the CSV gives none.
    # Never a constructed address: where the search page links no such page,
    # none, and nothing is taken from it.
    if page is None:
        addr = results_link(html)
        if addr:
            time.sleep(PAUSE)
            raw3, enc4 = get(addr)
            RAW_PAGE.with_name("lsr_results.html").write_bytes(raw3)
            page = raw3.decode(enc4, "replace")
        else:
            print("  the search page links no page of every request: no text link is read")
        rows, page_read, listed = with_page_rows(rows, page)
    with_text_links(rows, page)
    have = {r["lsr"] for r in rows}
    held = 0 if page_read else sum(1 for r in load_rows() if r.get("from_page")
                                   and not r.get("withdrawn") and r.get("lsr") not in have)
    print(f"  {LISTED}{listed}"
          + (f"; {held} taken from it before kept as they stood" if held else ""))
    merged, gone = merge(rows, page_read)
    OUT.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    sessions = sorted({r["session"] for r in rows})
    print(f"{len(rows)} requests for {', '.join(str(s) for s in sessions)} -> {OUT}")
    if gone:
        print(f"  {gone} request(s) no longer listed, kept and marked withdrawn")
    print("\nThese are requests, not bills: a title and a prime sponsor, and "
          "nothing else\nuntil one is drafted and introduced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
