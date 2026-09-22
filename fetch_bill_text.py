#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.23
"""
The text of each bill, as text rather than as a link to a PDF.

    python3 fetch_bill_text.py --probe HB1442   # one bill, report only, no write
    python3 fetch_bill_text.py --probe HB1442 --raw   # dump the HTML to look at
    python3 fetch_bill_text.py                  # every bill, cached
    python3 fetch_bill_text.py --reparse        # re-extract from cache, no network

WHY THIS IS NOW POSSIBLE

`fetch_bill_status.py --links` read all 2,234 cached status pages and found ten
address shapes. One of them settles a question that had been open:

    billText.aspx?id&sy&txtFormat     e.g. id=7&txtFormat=html&sy=2025

txtFormat takes **html**, not only pdf. So the text can be fetched and put on
the page, rather than linked to as a PDF that a phone downloads and a screen
reader cannot read. That also gives the RSA linker something worth pointing at,
and it is the prerequisite for amendment diffing: a diff is two texts.

WHY THIS IS PROBE-FIRST

Fetching billText.aspx from outside returns the page furniture and no bill --
the text arrives some way that a plain reader does not see, most likely inside
a frame or written by a script. Guessing which, and writing an extractor
against the guess, is how you end up with 2,234 files of navigation menu.

So --probe fetches ONE bill and describes what came back: the size, the frames,
the embeds, how much text can be pulled out of it and what the first of that
text says. Send that and the extractor gets written against the real thing.

WHAT IT WILL WRITE, once the shape is known

  bill_text/<bill>.html   the page as fetched, cached permanently
  bill_text.json          {bill: {"text": ..., "version": ..., "fetched": ...}}

A bill's text changes when it is amended, so unlike the status pages this
cannot be cached once and forgotten. The plan is to refetch only bills whose
docket has moved since the last run, which the narratives already know.

ON VERSIONS

A search result showed a fourth parameter that is not in the --links output,
because no bill page links to it:

    billText.aspx?id=692&txtFormat=pdf&v=current

If `v` takes values other than "current", those are the earlier versions of the
bill, which is exactly what an amendment diff compares. --probe reports whether
the fetched page mentions any, so that question gets answered in the same run
rather than in another one.
"""

import argparse
import html
import json
import proceedings as P
import random
import re
from collections import Counter
import refusal
import sys
import time
import urllib.request
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}
BASE = "https://gc.nh.gov/bill_status/legacy/bs2016/billText.aspx"
WS = re.compile(r"\s+")
TAG = re.compile(r"<[^>]+>")
ID_RE = re.compile(r"[?&]id=(\d+)", re.I)
FRAME_RE = re.compile(r"<(?:i?frame|embed|object)\b[^>]*?"
                      r"(?:src|data)\s*=\s*[\"']([^\"']+)", re.I)
VER_RE = re.compile(r"[?&]v=([A-Za-z0-9_\-]+)", re.I)


# The General Court closes the connection without answering when it is being
# asked for too much at once -- which is what a nightly run looks like from its
# side. urllib reports that as RemoteDisconnected, whose message says nothing
# about the cause, so it is named here instead of left to be puzzled over.
REFUSED = ("remotedisconnected", "connection reset", "connection aborted",
           "closed connection without response", "timed out")


def busy_note():
    """Say the likely reason before the requests start, not after they fail."""
    if Path(".nightly.lock").exists():
        print("NOTE: a nightly run is going, and the General Court will refuse\n"
              "      connections from a second one. Wait for it to finish.\n")


def refused(err):
    return any(w in f"{type(err).__name__} {err}".lower() for w in REFUSED)


class Gentle:
    """Watches the far end and gets out of its way.

    A fetch that runs all night unattended has to answer a question a person
    would answer by looking: is the server still comfortable? The General Court
    is a single IIS box, and this is a project that has already been blocked
    once for asking too hard.

    Three signals, none of them clever:

      it stopped answering    consecutive failures. Not one -- a blip is a
                              blip -- but a run of them means stop.
      it slowed down          responses taking much longer than they were at
                              the start. That is a queue forming, and the
                              polite response is to wait longer between asks.
      it said no              a 429 or a 5xx is the server saying so outright,
                              and is treated as worse than silence.

    Slowing down is the first response and stopping is the last. The run is
    resumable, so stopping early costs nothing but time.
    """

    def __init__(self, delay, stop_after=6, max_delay=30.0):
        self.delay = delay
        self.base = delay
        self.stop_after = stop_after
        self.max_delay = max_delay
        self.fails = 0
        self.times = []
        self.baseline = None
        self.reason = ""

    def ok(self, seconds):
        self.fails = 0
        self.times.append(seconds)
        # The first twenty set the pace this server is happy at.
        if self.baseline is None and len(self.times) >= 20:
            self.baseline = sorted(self.times)[len(self.times) // 2]
        if self.baseline:
            recent = self.times[-10:]
            med = sorted(recent)[len(recent) // 2]
            if med > self.baseline * 3 and self.delay < self.max_delay:
                self.delay = min(self.max_delay, round(self.delay * 1.8, 1))
                return (f"slowing to {self.delay}s between requests: responses "
                        f"went from {self.baseline:.1f}s to {med:.1f}s")
            if med < self.baseline * 1.5 and self.delay > self.base:
                self.delay = max(self.base, round(self.delay / 1.5, 1))
                return f"easing back to {self.delay}s: the server has recovered"
        return ""

    def failed(self, why):
        self.fails += 1
        self.delay = min(self.max_delay, round(max(self.delay, 1) * 2, 1))
        if self.fails >= self.stop_after:
            self.reason = (f"{self.fails} requests in a row failed "
                           f"({why}). Stopping rather than pushing.")
        return self.reason

    def refused(self, code):
        """A 429 or 5xx is not a blip; it is the server saying no."""
        self.reason = (f"the General Court answered HTTP {code}, which is it "
                       "asking us to stop. Stopping.")
        return self.reason


def hms(secs):
    secs = int(max(0, secs))
    h, m = divmod(secs // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {secs % 60:02d}s"


class Ticker:
    """A line that moves, so a slow run cannot be mistaken for a stuck one.

    A fetch that pauses four seconds between requests and reports every
    hundredth of them says nothing for seven minutes at a time. There is no way
    to tell that from a hang, and the difference matters at one in the morning.

    So: one line, rewritten after every request, carrying the count, the share
    done, how long is left at the rate it is actually going, and the delay it
    has settled on. Plus a permanent line now and then, because a run that
    scrolls away leaves nothing behind to read.

    Where the output is not a terminal -- redirected to a log -- the moving
    line is pointless and would fill the file with control characters, so it
    falls back to the permanent lines alone.
    """

    def __init__(self, total, every, live=None):
        self.total = total
        self.every = max(1, every)
        self.t0 = time.time()
        self.live = sys.stdout.isatty() if live is None else live
        self.width = 0

    def __call__(self, i, bid, delay, fetched, cached, failed):
        done = time.time() - self.t0
        rate = done / max(1, i)
        left = hms(rate * (self.total - i)) if i >= 3 else "..."
        pct = 100 * i / max(1, self.total)
        line = (f"  {i:,}/{self.total:,}  {pct:4.1f}%  {hms(done)} gone, "
                f"{left} left  {delay:g}s apart  {bid}")
        if failed:
            line += f"  ({failed} failed)"
        if self.live:
            pad = max(0, self.width - len(line))
            self.width = len(line)
            sys.stdout.write("\r" + line + " " * pad)
            sys.stdout.flush()
        if i % self.every == 0 or i == self.total:
            if self.live:
                sys.stdout.write("\n")
                self.width = 0
            print(f"  {i:,} of {self.total:,}  ({fetched:,} fetched, "
                  f"{cached:,} from cache)", flush=True)

    def done(self):
        if self.live and self.width:
            sys.stdout.write("\n")
            sys.stdout.flush()
            self.width = 0


def get(url, timeout=60, tries=5):
    """Fetch, backing off properly when the far end is turning us away.

    Two seconds then four is the right shape for a blip and the wrong one for
    throttling, which is what these failures were: six requests across three
    scripts all refused at once while a nightly run held the connection budget.
    Backing off 3, 9, 27 then 60 seconds gives a busy server time to mean it.
    """
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return (r.read().decode("utf-8", errors="replace"),
                        r.headers, None)
        except Exception as e:
            last = e
            if i < tries - 1:
                wait = min(60, 3 ** (i + 1)) + random.uniform(0, 1.5)
                if refused(e):
                    print(f"    refused, waiting {wait:.0f}s "
                          f"({i + 1} of {tries - 1})")
                time.sleep(wait)
    if refused(last):
        return None, None, (f"{last} -- the General Court refused the connection. "
                      "This is\n  almost always another fetch running at the "
                      "same time; nothing is wrong\n  with the address.")
    return None, None, last


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


def url_for(text_pdf, bill, year):
    """The html form of whatever address the status page gave for the PDF."""
    m = ID_RE.search(text_pdf or "")
    if not m:
        return ""
    return f"{BASE}?id={m.group(1)}&txtFormat=html&sy={year}"


def probe(url, raw=False):
    print(f"fetching {url}\n")
    html, headers, err = get(url)
    if html is None:
        print(f"failed: {err}")
        return
    if raw:
        Path("probe_billtext.html").write_text(html, encoding="utf-8")
        print("wrote probe_billtext.html\n")

        # What actually separates one line of the bill from the next.
        #
        # The heading comes out on separate lines and the body runs together,
        # so the two are marked up differently and only one of the two markups
        # is being turned into a line break. Rather than ask which, this shows
        # the markup around the enacting clause -- where the body starts -- and
        # counts the tags in it.
        i = re.search(r"Be it Enacted|That the following|RESOLVED", html, re.I)
        if i:
            seg = html[max(0, i.start() - 300): i.start() + 1400]
            print("  the markup where the bill starts:")
            print("  " + "-" * 66)
            # The whole file is one line, so splitting on newlines showed one
            # truncated line and nothing useful. Wrapped instead.
            flat = re.sub(r"\s+", " ", seg)
            for i in range(0, min(len(flat), 1500), 100):
                print("  " + flat[i:i + 100])
            print("  " + "-" * 66)
            tags = Counter(m.group(1).lower() for m in
                           re.finditer(r"<(/?[a-zA-Z][\w-]*)", seg))
            print("  tags in that stretch: "
                  + ", ".join(f"{k} x{v}" for k, v in tags.most_common(10)))
            nl = seg.count("\n")
            print(f"  raw newlines in it: {nl}")
            print("\n  If the lines are separated by something other than <br>,")
            print("  </p>, </div>, </li> or </tr>, that is what the extractor")
            print("  is missing. Send the block above.")
        else:
            print("  no enacting clause found in the markup; send the file.")

    print(f"  content-type   {headers.get('Content-Type', '?')}")
    print(f"  bytes          {len(html):,}")

    frames = FRAME_RE.findall(html)
    print(f"  frames/embeds  {len(frames)}")
    for f in frames[:6]:
        print(f"                 {f[:100]}")

    vers = sorted(set(VER_RE.findall(html)))
    print(f"  v= values seen {vers or 'none'}")

    body = text_of(html)
    lean = strip_chrome(body)
    print(f"  text extracted {len(body):,} chars, "
          f"{len(lean):,} once the page furniture is removed")
    print(f"  <pre> blocks   {len(re.findall(r'<pre\\b', html, re.I))}")
    print(f"  <table>s       {len(re.findall(r'<table\\b', html, re.I))}")

    print("\nfirst 600 characters of what is left:")
    print("-" * 68)
    print(lean[:600] if lean.strip() else "(nothing)")
    print("-" * 68)

    if len(lean) < 400:
        print("\nToo little to be a bill. The text is not in this page: follow "
              "the frame\nor embed above if there is one, and send this output "
              "either way.")
    else:
        print("\nThat looks like a bill. If the top of it reads like the "
              "beginning of the\nbill rather than a menu, the extractor can be "
              "written from here.")


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

VERSION_RE = re.compile(
    r"^\s*(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR)\s*\d+[\w-]*\s*[-\u2013]\s*(?P<v>[A-Z][A-Z \u2019'/]{3,40})\s*$",
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


# Things a page can be that are not a bill. A fetch only saves what came back
# with a 200, and a server under strain answers 200 with an apology.
NOT_A_BILL = [
    ("condensedbillno", "the ASP.NET error from a missing sy parameter"),
    ("Web Page Blocked", "the firewall's block page"),
    ("Attack ID", "the firewall's block page"),
    ("Runtime Error", "an ASP.NET runtime error"),
    ("Server Error in", "an ASP.NET server error"),
    ("Service Unavailable", "the server refusing"),
]


def is_empty(rec, html):
    """A page that came back, and had no bill on it.

    A blank body with the site furniture around it is a 200 like any other, so
    the fetch stored it and moved on. It has no version, no title and no text
    -- three things every real page has -- which is what tells it apart from a
    bill that is merely short.
    """
    return not rec.get("version") and not rec.get("title") \
        and len(rec.get("text") or "") < 200


def inspect(cache, limit=0, purge=False):
    """Read the cache and say whether what is in it is bills.

    Nothing is fetched and nothing is written, so this is safe to run while a
    fetch is going -- the pages already on disk are the pages already on disk.

    What it is looking for is the failure that does not announce itself. A
    fetch stores whatever came back with a 200, and a struggling server answers
    200 with an error page. Those land in the cache the same size and shape as
    a bill and are only visibly wrong if somebody looks.
    """
    files = sorted(Path(cache).glob("*.html"))
    if not files:
        print(f"Nothing cached under {cache}/ yet.")
        return
    if limit:
        files = files[-limit:]
    # A file the fetch wrote seconds ago may still be being written, and half
    # a page reads as a page that is too small or missing its heading. Rather
    # than raise a false alarm about the one file in 850 that happened to be in
    # flight, the newest are left out and counted separately.
    now = time.time()
    inflight = [f for f in files if now - f.stat().st_mtime < 15]
    files = [f for f in files if f not in inflight]
    print(f"reading {len(files):,} cached pages from {cache}/, no network")
    if inflight:
        print(f"  ({len(inflight)} written in the last few seconds skipped -- "
              "a fetch is running)")
    print()

    versions, gaps = Counter(), Counter()
    bad, thin, tiny, ok = [], [], [], []
    for f in files:
        try:
            html = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue                     # being written right now; fine
        hit = next((why for mark, why in NOT_A_BILL if mark in html), None)
        if hit:
            bad.append((f.stem, hit))
            continue
        rec = parse_text(html, f.stem, "")
        if is_empty(rec, html):
            bad.append((f.stem, "came back empty: no version, title or text"))
            continue
        if len(html) < 2000:
            tiny.append(f.stem)
        elif rec.get("heading_only"):
            thin.append(f.stem)
        else:
            ok.append((f.stem, rec))
        versions[rec.get("version") or "(none)"] += 1
        for k in missing(rec):
            gaps[k] += 1

    print(f"  {len(ok):,} look like bills")
    if bad:
        print(f"  {len(bad):,} are NOT bills -- an error page was saved as one:")
        for stem, why in bad[:5]:
            print(f"      {stem}: {why}")
        print("      Deleting those files makes the next run fetch them "
              "again.")
        if purge:
            for stem, _ in bad:
                (Path(cache) / f"{stem}.html").unlink(missing_ok=True)
            print(f"      DELETED {len(bad)}. They will be fetched on the "
                  "next run.")
        else:
            print("      Add --purge to delete them.")
    if thin:
        print(f"  {len(thin):,} have a heading and almost no text "
              f"(e.g. {', '.join(thin[:4])})")
    if tiny:
        print(f"  {len(tiny):,} {'is' if len(tiny) == 1 else 'are'} too small "
              f"to be a page (e.g. {', '.join(tiny[:4])})")

    print("\n  versions:")
    for v, k in versions.most_common(8):
        print(f"    {k:>5,}  {v}")
    if gaps:
        print("\n  fields not found: "
              + ", ".join(f"{k} on {v:,}" for k, v in gaps.most_common()))

    if ok:
        stem, rec = ok[len(ok) // 2]
        print(f"\n  a page from the middle of the run, {stem}:")
        print(f"    version   {rec.get('version')}")
        print(f"    title     {(rec.get('title') or '')[:70]}")
        amd = rec.get("amendments_in_text") or []
        if amd:
            print("    contains  "
                  + ", ".join(x.get("num") or x["short"] for x in amd))
        body = WS.sub(" ", rec.get("text", ""))
        print(f"    {len(body):,} characters, beginning:")
        print(f"      {body[:190]}")

    print(f"\n  Nothing was written and nothing was fetched. Safe to run "
          "while a fetch\n  is going, and safe to run again whenever.")


def embed_check(url, timeout=120):
    """Can this document be shown inside our page, or only linked to?

    One request, headers only. Three things decide it:

      X-Frame-Options            DENY or SAMEORIGIN and an iframe renders
                                 blank -- silently, which is the worst way to
                                 find out
      Content-Security-Policy    frame-ancestors does the same job in the
                                 newer form and wins where both are set
      Accept-Ranges              a PDF viewer asks for byte ranges so it can
                                 show page one without pulling the whole file.
                                 Without it, a long bill loads in full before
                                 anything appears.

    A HEAD costs the server almost nothing. Where HEAD is refused -- some
    ASP.NET handlers do -- one GET is made and abandoned after a kilobyte.
    """
    print(f"asking about {url}\n")

    def ask(u, method):
        t0 = time.time()
        req = urllib.request.Request(u, headers=UA, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = b"" if method == "HEAD" else r.read(2048)
            return r.status, r.headers, body, time.time() - t0

    # The HTML of the same document, as a control. It is a page the General
    # Court already holds; the PDF is rendered on request. If the HTML is quick
    # and the PDF is not, that is the cost of generating it -- which every
    # reader would pay, on the General Court's machine, if it were embedded.
    # If both are slow, it is us being throttled and says nothing about the PDF.
    ctrl = url.replace("txtFormat=pdf", "txtFormat=html")
    ctrl_t = None
    try:
        _, _, _, ctrl_t = ask(ctrl, "GET")
        print(f"  the same document as HTML took {ctrl_t:.1f}s")
    except Exception as e:
        print(f"  the same document as HTML also failed: {type(e).__name__}")

    took = None
    try:
        status, hdrs, body, took = ask(url, "HEAD")
        how = "HEAD"
    except Exception:
        try:
            status, hdrs, body, took = ask(url, "GET")
            how = "GET, first two kilobytes only"
        except Exception as e:
            print(f"\n  the PDF failed: {type(e).__name__}: {e}")
            # Three seconds is generous for a nine kilobyte page the
            # General Court already holds. Slower than that and the connection
            # is the suspect, not the PDF.
            if ctrl_t is not None and ctrl_t < 3:
                print(f"\n  The HTML of the same bill came back in "
                      f"{ctrl_t:.1f}s, so this is not\n  throttling -- it is "
                      f"the PDF taking more than {timeout}s to generate.\n"
                      "  Embedding it would put that wait on every reader who "
                      "opens the\n  bill, and that work on the General Court's "
                      "machine rather than\n  ours. Link to it instead.")
            else:
                print("\n  The HTML was slow too, so this is the connection or "
                      "the address\n  being throttled and says nothing about "
                      "the PDF. Try again later.")
            return
    print(f"\n  {how}, HTTP {status}, {took:.1f}s\n")

    xfo = hdrs.get("X-Frame-Options", "")
    csp = hdrs.get("Content-Security-Policy", "")
    anc = ""
    m = re.search(r"frame-ancestors([^;]*)", csp, re.I)
    if m:
        anc = m.group(1).strip()
    for k in ("Content-Type", "Content-Length", "Accept-Ranges",
              "X-Frame-Options", "Content-Security-Policy", "Server"):
        v = hdrs.get(k)
        if v:
            print(f"  {k:<26}{str(v)[:80]}")
    if body[:4] == b"%PDF":
        print(f"  {'body begins':<26}%PDF -- it is a real PDF")

    print()
    blocked = bool(xfo) or bool(anc and "none" in anc.lower())
    if blocked:
        why = f"X-Frame-Options: {xfo}" if xfo else f"frame-ancestors {anc}"
        print(f"  CANNOT be embedded. {why}")
        print("  An iframe would render blank, and blank is how a reader finds\n"
              "  out. Link to it prominently instead.")
    else:
        print("  Nothing forbids embedding it. An iframe should show the "
              "document,\n  with the General Court's own typography -- the bold "
              "italics for added\n  text, the strikethrough, the fiscal note "
              "tables -- none of which\n  survives being read as text.")
        if took and ctrl_t and took > max(6, ctrl_t * 4):
            print(f"\n  But it took {took:.1f}s against {ctrl_t:.1f}s for the "
                  "same bill as HTML.\n  That is the PDF being generated on "
                  "request, and an embed would put\n  that wait on every "
                  "reader and that work on the General Court.")
        if hdrs.get("Accept-Ranges", "").lower() != "bytes":
            print("\n  No Accept-Ranges, so a viewer must load the whole file "
                  "before showing\n  page one. Fine for a short bill, slow for "
                  "a budget.")
    print("\n  Worth trying in a browser too: a header can allow it and a "
          "sandbox or\n  an extension still refuse.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="bill_status.json")
    ap.add_argument("--term", help="which term of data/bills.json to fetch, "
                                   "e.g. 2023-2024; the newest by default")
    ap.add_argument("--data", default="data")
    ap.add_argument("--cache", default="bill_text")
    ap.add_argument("--out", default="bill_text.json")
    ap.add_argument("--probe", help="one bill, e.g. HB1442")
    ap.add_argument("--raw", action="store_true", help="also save the HTML")
    ap.add_argument("--reparse", action="store_true",
                    help="parse what is cached, fetch nothing")
    ap.add_argument("--purge", action="store_true",
                    help="with --inspect: delete the pages that are not bills, "
                         "so the next run fetches them again")
    ap.add_argument("--embed-timeout", type=float, default=120,
                    help="seconds to wait for the PDF; it is generated on "
                         "request and a long bill can take a while")
    ap.add_argument("--embed-check", action="store_true",
                    help="one request: can a bill PDF be shown inside our "
                         "page, or only linked to?")
    ap.add_argument("--inspect", action="store_true",
                    help="read the cache and report on it. Writes nothing and "
                         "fetches nothing, so it is safe while a fetch runs.")
    ap.add_argument("--refetch", action="store_true",
                    help="fetch again even if cached; a bill's text changes "
                         "when it is amended")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("--gentle", action="store_true",
                    help="for running unattended: 4s between requests, backs "
                         "off when the server slows, stops on a run of "
                         "failures. Resumable, so stopping costs only time.")
    ap.add_argument("--stop-after", type=int, default=6,
                    help="consecutive failures before giving up")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="stop after this long, whatever else happens")
    a = ap.parse_args()
    refusal.check("The bill text fetch")

    # Both files are {term: {bill: record}}. A bill number is unique within a
    # term and not across them, so the term has to be settled before anything
    # is looked up: HB100 of 2023 and HB100 of 2025 are different bills with
    # different texts, and fetching one under the other's key is silent.
    all_bills = json.loads(
        (Path(a.data) / "bills.json").read_text(encoding="utf-8")) \
        if (Path(a.data) / "bills.json").exists() else {}
    newest = max(all_bills) if all_bills else ""
    term = a.term or newest
    if all_bills and term not in all_bills:
        sys.exit(f"data/bills.json has no term {term!r}. It holds: "
                 + ", ".join(sorted(all_bills)))
    bills = all_bills.get(term, {})
    st_all = json.loads(Path(a.status).read_text(encoding="utf-8")) \
        if Path(a.status).exists() else {}
    st = P.per_term(st_all, term, newest)
    if term != newest:
        print(f"term {term}: {len(bills):,} bills, "
              f"{len(st):,} with a status page on file")

    if a.embed_check:
        b = (a.probe or "HB1123").upper().replace(" ", "")
        rec, meta = st.get(b, {}), bills.get(b, {})
        pdf = rec.get("text_pdf", "")
        if not pdf:
            sys.exit(f"{b} has no text address on file. Try --probe <a bill "
                     "that does>.")
        if "sy=" not in pdf:
            pdf += f"&sy={rec.get('text_year') or meta.get('lsr_year', '')}"
        embed_check(pdf, timeout=a.embed_timeout)
        return

    if a.inspect:
        inspect(a.cache, purge=a.purge)
        return

    if a.probe:
        busy_note()
        b = a.probe.upper().replace(" ", "")
        rec, meta = st.get(b, {}), bills.get(b, {})
        if not rec:
            sys.exit(f"{b} is not in {a.status}. Run fetch_bill_status.py first.")
        url = url_for(rec.get("text_pdf", ""), b, meta.get("lsr_year", ""))
        if not url:
            sys.exit(f"{b} has no text address on its status page "
                     f"(text_pdf is {rec.get('text_pdf', '')!r}).")
        probe(url, a.raw)
        return

    cache = Path(a.cache)
    cache.mkdir(exist_ok=True)
    todo = []
    for bid, rec in sorted(st.items()):
        url = url_for(rec.get("text_pdf", ""), bid,
                      rec.get("text_year") or bills.get(bid, {}).get("lsr_year", ""))
        if url:
            todo.append((bid, url))
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo):,} bills have a text address\n")

    out, fetched, cached, failed, thin = {}, 0, 0, [], []
    every = max(1, min(100, len(todo) // 20))
    if a.gentle and a.delay < 4:
        a.delay = 4.0
    gov = Gentle(a.delay, a.stop_after)
    tick = Ticker(len(todo), every)
    started = time.time()
    # Whatever it managed is written when it stops, however it stops. A run cut
    # short at three in the morning should leave its work behind, not throw it
    # away because it did not reach the end.
    stopped = ""
    for i, (bid, url) in enumerate(todo, 1):
        f = cache / f"{bid}.html"
        if f.exists() and not a.refetch:
            html = f.read_text(encoding="utf-8", errors="replace")
            cached += 1
        elif a.reparse:
            continue
        else:
            t0 = time.time()
            html, hdrs, err = get(url, tries=2 if a.gentle else 5)
            took = time.time() - t0
            if html is None:
                failed.append((bid, str(err)[:60]))
                stopped = gov.failed(str(err)[:40])
                if stopped:
                    break
                time.sleep(gov.delay)
                continue
            note = gov.ok(took)
            if note:
                tick.done()
                print(f"  {note}", flush=True)
            f.write_text(html, encoding="utf-8")
            fetched += 1
            time.sleep(gov.delay)
        if a.max_minutes and (time.time() - started) / 60 >= a.max_minutes:
            stopped = f"reached the {a.max_minutes:g} minute limit"
            break
        yr = (st.get(bid, {}).get("text_year")
              or bills.get(bid, {}).get("lsr_year", "") or "")
        rec = parse_text(html, bid, yr)
        if rec.get("heading_only"):
            thin.append(bid)
        out[bid] = rec
        # Scaled to the run. A fixed interval of 200 meant a --limit 20 run
        # printed nothing at all and looked hung -- which it did, for a few
        # minutes, while working perfectly.
        tick(i, bid, gov.delay, fetched, cached, len(failed))

    tick.done()
    if stopped:
        print(f"\nSTOPPED EARLY: {stopped}")
        print(f"{fetched:,} were fetched and are kept. Run the same command "
              "again to carry on\nfrom here -- nothing already downloaded is "
              "fetched twice.")
    print(f"\n{len(out):,} bills parsed: {fetched:,} fetched, {cached:,} "
          f"already on disk")
    if fetched:
        mins = (time.time() - started) / 60
        print(f"took {mins:.0f} min, ending at {gov.delay}s between requests")
    if failed:
        print(f"{len(failed):,} could not be fetched. First three:")
        for bid, why in failed[:3]:
            print(f"    {bid}  {why}")
    if thin:
        print(f"{len(thin):,} pages had a heading and almost no text. Those "
              f"are bills whose\ntext is not posted, or a shape this does not "
              f"read. e.g. {', '.join(thin[:4])}")
    vers = Counter(r.get("version", "(none)") for r in out.values())
    print("\nversions seen:")
    for v, k in vers.most_common(10):
        print(f"  {k:>6,}  {v}")
    # Each page serves ONE version: whichever the bill is at now. So these are
    # different bills at different stages, not several views of one bill, and
    # a before-and-after cannot be assembled from this endpoint alone.
    if len(vers) > 1:
        print("  Each page carries one version -- the bill's current one -- so\n"
              "  these are bills at different stages, not versions of the same\n"
              "  bill. An earlier text is not reachable from here.")
    withamd = [r for r in out.values() if r.get("amendments_in_text")]
    amended = [r for r in out.values()
               if "AMENDED" in (r.get("version") or "").upper()
               or "ADOPTED BY BOTH" in (r.get("version") or "").upper()
               or "FINAL" in (r.get("version") or "").upper()]
    print(f"\n{len(withamd):,} texts name the amendments folded into them, "
          f"out of {len(amended):,}\nwhose version says they were amended at "
          "all. A text that has not been\namended has nothing to name.")

    gaps = Counter()
    for r in out.values():
        for k in missing(r):
            gaps[k] += 1
    if gaps:
        print("fields not found: " + ", ".join(f"{k} on {v:,}"
                                               for k, v in gaps.most_common()))

    op = Path(a.out)
    # bill_text.json is {term: {bill: record}}. `out_all` is what gets written
    # and `out` is this term's slice, so a run over one term cannot drop
    # another -- the count guard below compares this term against this term,
    # not against every term on file, which would let a complete 2023-2024 run
    # look like a failed one next to a full 2025-2026.
    out_all = {}
    if op.exists():
        try:
            out_all = P.in_term(
                json.loads(op.read_text(encoding="utf-8")), newest)
        except ValueError:
            out_all = {}
        had = len(out_all.get(term, {}))
        if had and len(out) < had * 0.5 and not stopped:
            print(f"\nNOT WRITING {a.out}: {len(out):,} against {had:,} on "
                  f"file for {term}.\nThat is a run that failed, not bills "
                  "that lost their text.")
            return
        if had and len(out) < had:
            # A partial run should add to the file, not replace it with less.
            prior = dict(out_all.get(term, {}))
            prior.update(out)
            out = prior
            print(f"merged with what was already there: {len(out):,} bills")
    if out:
        out_all[term] = out
    else:
        out_all.pop(term, None)
    op.write_text(json.dumps(out_all, indent=2), encoding="utf-8")
    print(f"\n-> {a.out}  ("
          + ", ".join(f"{t}: {len(v):,}" for t, v in sorted(out_all.items()))
          + ")")


if __name__ == "__main__":
    main()
