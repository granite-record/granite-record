#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.15
"""
Collect House online testimony sign-ins: who registered support or opposition
on each bill, and who filed written testimony.

    python3 fetch_testimony.py --probe        # DO THIS FIRST
    python3 fetch_testimony.py --manifest verification_manifest.csv --limit 5
    python3 fetch_testimony.py --manifest verification_manifest.csv

Why this one is different from every other source in the project.

Everything else is a file or a URL with parameters. This is an ASP.NET WebForms
page: the committee dropdown and the results grid are driven by __doPostBack,
so there is nothing to put in a query string. Reading it means fetching the
page, pulling __VIEWSTATE and __EVENTVALIDATION out of the HTML, posting them
back with the committee, date and bill selected, and parsing the grid that
comes back. Those tokens change on every request and the control names are not
documented anywhere.

So --probe runs first and prints what the form actually contains: every select,
its options, every hidden field, and the form action. Send me that output and I
will finish the request builder against the real names rather than guesses.

What this collects, and what it does not. Only counts: how many signed in, how
many for and against, and how many gave a New Hampshire address. Not the names.
The individual entries are on the General Court's own page and this links there
instead -- republishing several hundred names and home towns is a different act
from publishing a total, and the total is the part nobody else provides.

The in-state and out-of-state split is kept because it is plainly factual and
because a count means something different when much of it came from elsewhere.
Reporting both numbers is not the same as drawing a conclusion from them.

One caution that belongs on the page and not just here: sign-ins record who
chose to register a position, which is a measure of who mobilised. Advocacy
groups on all sides organise them. It is not a poll.
"""

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://gc.nh.gov/house/committees/remotetestimony/"
PAGE = BASE + "submitted_testimony.aspx"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}


class FormProbe(HTMLParser):
    """Everything needed to reproduce a postback: hidden fields, selects, action."""

    def __init__(self):
        super().__init__()
        self.hidden, self.selects, self.action = {}, {}, None
        self._sel, self._opt, self._buf = None, None, []
        self.buttons = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "form":
            self.action = d.get("action")
        elif tag == "input":
            t = (d.get("type") or "").lower()
            name = d.get("name") or d.get("id")
            if not name:
                return
            if t == "hidden":
                self.hidden[name] = d.get("value", "")
            elif t in ("submit", "button"):
                self.buttons.append((name, d.get("value", "")))
        elif tag == "select":
            self._sel = d.get("name") or d.get("id")
            if self._sel:
                self.selects[self._sel] = []
        elif tag == "option" and self._sel:
            self._opt = d.get("value", "")
            self._buf = []

    def handle_data(self, data):
        if self._opt is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "option" and self._sel and self._opt is not None:
            self.selects[self._sel].append(
                (self._opt, " ".join("".join(self._buf).split())))
            self._opt, self._buf = None, []
        elif tag == "select":
            self._sel = None


class Grid(HTMLParser):
    """The results table.

    Each row is a th holding the person's name, then td cells for town, state,
    position, and links to any attached or typed testimony. Treating th as
    "header" swept all hundred names into the header list and shifted every
    column by one, so Position was read from Attachment and every count came
    out zero.

    Only the FIRST row of th cells is a header. After that a th is the row's
    first cell.
    """

    def __init__(self):
        super().__init__()
        self.rows, self.row, self.cell = [], [], []
        self.head, self.in_cell = [], False
        self._have_head = False
        self.links = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag in ("td", "th"):
            self.in_cell, self.cell = True, []
        elif tag == "tr":
            self.row = []
        elif tag == "a" and "href" in d:
            self.links.append(d["href"])

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th"):
            self.row.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        elif tag == "tr" and self.row:
            if not self._have_head and not any(
                    c.lower() in ("nh", "support", "oppose", "neutral")
                    for c in self.row):
                self.head = self.row
                self._have_head = True
            elif any(c for c in self.row):
                self.rows.append(self.row)
            self.row = []


# ASP.NET keeps state in a session cookie as well as in the form tokens, so a
# postback made without the cookie from the GET is rejected or silently
# returns the unfilled page.
_JAR = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_JAR))


def get(url, data=None, timeout=60):
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(data).encode() if data else None,
        headers={**UA, **({"Content-Type": "application/x-www-form-urlencoded",
                           "Referer": PAGE} if data else {})})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        # An ASP.NET 500 usually explains itself in the body. Reading it turns
        # "something went wrong" into the actual exception name, which is the
        # difference between fixing this in one attempt and in five.
        body = e.read().decode("utf-8", errors="replace")
        m = re.search(r"<title>([^<]{0,200})</title>", body, re.I)
        detail = re.search(r"(?:Exception Details|Description):\s*([^<\n]{0,220})",
                           body, re.I)
        raise RuntimeError(
            f"HTTP {e.code} from the form post.\n"
            f"  {m.group(1).strip() if m else '(no title)'}\n"
            f"  {detail.group(1).strip() if detail else ''}\n"
            "  A 500 here is almost always __EVENTVALIDATION rejecting a value "
            "that was not among the options the page rendered.") from None


def tokens(html):
    """The hidden fields that must be posted back verbatim."""
    p = FormProbe()
    p.feed(html)
    return {k: v for k, v in p.hidden.items() if k.startswith("__")}, p


CMTE = "ctl00$pageBody$ddlCommittee"
BILLS = "ctl00$pageBody$ddlBills"


def postback(html, target, values):
    """Build the form post an AutoPostBack dropdown would make.

    Neither dropdown has a submit button: changing one fires __doPostBack
    itself. So the request is the full form, plus __EVENTTARGET naming which
    control changed. Everything else must be echoed back exactly as received or
    the page rejects it.
    """
    hid, p = tokens(html)
    form = dict(hid)
    form["__EVENTTARGET"] = target
    form["__EVENTARGUMENT"] = ""
    # Every select posts its current value, not only the one that changed --
    # but only those that HAVE a value. The bills dropdown renders with no
    # options until a committee is chosen, and posting an empty value for a
    # control with no options is exactly what event validation rejects, which
    # is what produced a 500 here.
    for name, opts in p.selects.items():
        if name in values:
            continue
        if opts:
            form[name] = opts[0][0]
    form.update({k: v for k, v in values.items() if v is not None})
    return form


# The pager is a Repeater whose page links each fire a postback of their own:
#
#   <a href="javascript:__doPostBack('ctl00$pageBody$rptPaging$ctl01$lnkPage','')">2</a>
#
# Page 1 is ctl00, page 2 is ctl01, and so on. The grid shows 100 rows a page,
# so any bill that drew more than that reported exactly 100 until now -- and
# the bills that draw more are precisely the contested ones whose totals
# matter most.
PAGER = re.compile(r"__doPostBack\(&#39;(ctl00\$pageBody\$rptPaging\$"
                   r"ctl\d+\$lnkPage)&#39;")


def page_targets(html):
    """Postback targets for each page of results, in order, first excluded."""
    seen, out = set(), []
    for t in PAGER.findall(html):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[1:]


def all_rows(html, cid, bval, delay, cap=250):
    """Every page of the grid, not just the first hundred rows.

    The cap was 40 pages, which silently truncated the two largest bills at
    exactly 4,100 -- the same failure as the original 100, one order up. HB 1703
    runs to 142 pages, so a bill that drew fourteen thousand sign-ins was
    reported as four thousand.

    A truncated count is now flagged rather than passed off as a total, because
    understating the most mobilised bills is the worst direction for this
    particular number to be wrong in.
    """
    g = Grid()
    g.feed(html)
    rows, head = list(g.rows), g.head
    targets = page_targets(html)
    cur = html
    for t in targets[:cap]:
        time.sleep(delay)
        cur = get(PAGE, postback(cur, t, {CMTE: cid, BILLS: bval}))
        gg = Grid()
        gg.feed(cur)
        if not gg.rows:
            break
        rows.extend(gg.rows)
        head = head or gg.head
    return rows, head, len(targets) + 1, len(targets) > cap


def bills_for(html):
    """The bill options the page offers once a committee is chosen."""
    p = FormProbe()
    p.feed(html)
    out = []
    for val, label in p.selects.get(BILLS, []):
        if val and not val.lower().startswith("select"):
            out.append((val, label))
    return out


def probe():
    print(f"fetching {PAGE}\n")
    html = get(PAGE)
    p = FormProbe()
    p.feed(html)
    print(f"form action : {p.action}")
    print(f"page size   : {len(html):,} bytes\n")

    print("HIDDEN FIELDS (these must be posted back verbatim)")
    for k, v in p.hidden.items():
        print(f"  {k:<34} {len(v):>7,} chars"
              + (f"  = {v}" if len(v) < 40 else ""))

    print("\nSELECTS")
    for name, opts in p.selects.items():
        print(f"  {name}  ({len(opts)} options)")
        for val, label in opts[:6]:
            print(f"      {val!r:<12} {label}")
        if len(opts) > 6:
            print(f"      ... {len(opts) - 6} more")

    if p.buttons:
        print("\nBUTTONS")
        for n, v in p.buttons:
            print(f"  {n:<34} {v}")

    targets = sorted(set(re.findall(r"__doPostBack\('([^']+)'", html)))
    if targets:
        print("\nPOSTBACK TARGETS found in the page script")
        for t in targets[:20]:
            print(f"  {t}")

    g = Grid()
    g.feed(html)
    print(f"\nGRID: headers {g.head or '(none)'}, {len(g.rows)} data rows")
    print("An empty grid on first load is expected — it fills after a postback.")

    print("\n" + "=" * 64)
    print("Send this whole output back. With the real control names I can build")
    print("the postback; guessing at them would waste a run and hit the server")
    print("for nothing.")
    print("=" * 64)
    Path("testimony_probe.json").write_text(json.dumps(
        {"action": p.action, "hidden": list(p.hidden), "selects":
         {k: v[:40] for k, v in p.selects.items()},
         "buttons": p.buttons, "targets": targets}, indent=2), encoding="utf-8")
    print("\nAlso written to testimony_probe.json")


# The page states the totals above the grid:
#
#     Support: 3625 | Oppose: 3251 | Neutral: 2
#
# Which makes counting rows the wrong approach entirely. Counting needed one
# request per hundred sign-ins, capped out on the biggest bills, and reported
# 4,100 for a bill with 6,878. This line is exact and costs nothing.
TOTALS = re.compile(
    r"Support:\s*(?P<s>\d[\d,]*)\s*\|\s*Oppose:\s*(?P<o>\d[\d,]*)"
    r"(?:\s*\|\s*Neutral:\s*(?P<n>\d[\d,]*))?", re.I)


def stated_totals(html):
    """The counts the page prints, or None if the line is absent."""
    m = TOTALS.search(re.sub(r"<[^>]+>", " ", html))
    if not m:
        return None
    num = lambda x: int((x or "0").replace(",", ""))
    return {"support": num(m.group("s")), "oppose": num(m.group("o")),
            "neutral": num(m.group("n"))}


# Position values as the page writes them.
FOR = {"support", "supports", "in favor", "in favour"}
AGAINST = {"oppose", "opposes", "opposed"}
NEUTRAL = {"neutral", "no position"}


def summarise(rows, head):
    """Counts by position, which is the number people actually want."""
    idx = {h.lower(): i for i, h in enumerate(head)}
    pos_i = next((i for h, i in idx.items() if "position" in h), 3)
    town_i = next((i for h, i in idx.items() if "town" in h), 1)
    # A position column that does not hold positions means the header did not
    # line up; find the column that actually does.
    vals = {(r[pos_i] or "").strip().lower() for r in rows if len(r) > pos_i}
    if not (vals & (FOR | AGAINST | NEUTRAL)):
        for i in range(max(len(r) for r in rows) if rows else 0):
            col = {(r[i] or "").strip().lower() for r in rows if len(r) > i}
            if col & (FOR | AGAINST | NEUTRAL):
                pos_i, town_i = i, max(i - 2, 0)
                break
    counts = Counter()
    towns = Counter()
    for r in rows:
        if len(r) > pos_i:
            counts[r[pos_i].strip().lower() or "unstated"] += 1
        if len(r) > town_i and r[town_i].strip():
            towns[r[town_i].strip()] += 1
    # Counts only. The names and towns are on the General Court's own page and
    # this site links there; republishing several hundred names and home towns
    # is a different act from publishing a total, and the total is the part
    # nobody else provides.
    #
    # In-state and out-of-state are kept because they are plainly factual --
    # people wrote down where they live -- and because a count of sign-ins
    # means something different when a large share came from elsewhere. Stating
    # the two numbers is not the same as drawing a conclusion from them.
    st_i = next((i for h, i in idx.items() if h.strip() == "state"),
                max(pos_i - 1, 0))
    states = Counter((r[st_i] or "").strip().upper()
                     for r in rows if len(r) > st_i)
    return {"total": len(rows), "by_position": dict(counts),
            "nh": states.get("NH", 0),
            "out_of_state": sum(n for st, n in states.items() if st and st != "NH"),
            "support": sum(n for v, n in counts.items() if v in FOR),
            "oppose": sum(n for v, n in counts.items() if v in AGAINST),
            "neutral": sum(n for v, n in counts.items() if v in NEUTRAL)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="dump the form structure; run this first")
    ap.add_argument("--manifest", default="verification_manifest.csv")
    ap.add_argument("--out", default="testimony.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--committee", help="only committees whose name contains this")
    ap.add_argument("--fresh", action="store_true", help="ignore what is on file")
    ap.add_argument("--dump", help="fetch one bill and print its raw grid rows, "
                                   "e.g. --dump HB1376")
    ap.add_argument("--max-pages", type=int, default=12,
                    help="page through the roll for the New Hampshire split up "
                         "to this many pages; beyond it the stated totals are "
                         "used on their own")
    a = ap.parse_args()

    if a.probe:
        probe()
        return

    html = get(PAGE)
    hid, p0 = tokens(html)
    committees = [(v, lab) for v, lab in p0.selects.get(CMTE, [])
                  if v and not v.lower().startswith("select")]
    if not committees:
        print("No committee list on the page. Run --probe and send the output.")
        return
    print(f"{len(committees)} committees\n")

    out = {}
    op = Path(a.out)
    if op.exists() and not a.fresh:
        out = json.loads(op.read_text(encoding="utf-8"))
        print(f"{len(out):,} bills already on file")

    if a.dump:
        want = a.dump.upper().replace(" ", "")
        for cid, cname in committees:
            time.sleep(a.delay)
            page = get(PAGE, postback(html, CMTE, {CMTE: cid}))
            for bval, blabel in bills_for(page):
                if not blabel.upper().replace(" ", "").startswith(want):
                    continue
                print(f"{cname}\n{blabel[:100]}\n")
                res = get(PAGE, postback(page, BILLS, {CMTE: cid, BILLS: bval}))
                g = Grid()
                g.feed(res)
                print(f"headers: {g.head}")
                print(f"{len(g.rows)} rows; first 8 verbatim:\n")
                for r in g.rows[:8]:
                    print("   " + " | ".join(f"{c[:24]!r}" for c in r))
                # Five bills came back at exactly 100, which is not a
                # coincidence. Look for a pager in every form it might take.
                pg = re.findall(r"__doPostBack\(&#?\w*;?'?([^'&]+)'?[^,]*,\s*"
                                r"&?#?\w*;?'?(Page\$[^'&]+)", res)
                print(f"\npaging postbacks: {pg[:6] or 'none'}")
                for pat, label in (
                        (r"Page\$\d+", "Page$N reference"),
                        (r"pagerstyle|PagerStyle|pager", "pager style class"),
                        (r"of\s+\d+\s+(?:records|rows|entries)", "record count"),
                        (r"ddlPage|PageSize|ctl00\$pageBody\$\w*[Pp]ag\w*", "pager control"),
                        (r"Showing\s+\d+", "showing count")):
                    m = re.findall(pat, res)
                    print(f"  {label:<22} {m[:4] if m else 'not present'}")
                # The pager is a Repeater: ctl00$pageBody$rptPaging. Its page
                # links are what has to be posted to get rows 101 onward.
                print("\n  every form control on the page:")
                for n in sorted(set(re.findall(r'name="([^"]+)"', res))):
                    print(f"    {n}")
                i = res.lower().find("rptpaging")
                if i > 0:
                    frag = re.sub(r"\s+", " ", res[max(0, i - 700):i + 900])
                    print("\n  markup around the pager:\n")
                    print("    " + frag[:1500])
                links = re.findall(r"__doPostBack\(([^)]{0,120})\)", res)
                print(f"\n  __doPostBack calls: {links[:8] or 'none'}")
                return
        print(f"{a.dump} not found in any committee.")
        return

    only = {c.strip().lower() for c in (a.committee or "").split(",") if c.strip()}
    nreq = 0
    for cid, cname in committees:
        if only and not any(o in cname.lower() for o in only):
            continue
        time.sleep(a.delay)
        nreq += 1
        # Choosing a committee repopulates the bill dropdown.
        try:
            page = get(PAGE, postback(html, CMTE, {CMTE: cid}))
        except RuntimeError as e:
            print(f"{cname}: {e}")
            break
        bills = bills_for(page)
        print(f"{cname}: {len(bills)} bills")
        if a.limit and nreq > a.limit:
            print("  (limit reached)")
            break

        for bval, blabel in bills:
            m = re.match(r"\s*([A-Z]{2,5})\s*0*(\d{1,4})", blabel, re.I)
            key = (m.group(1).upper() + m.group(2)) if m else \
                re.sub(r"[\s:].*$", "", blabel).upper()
            if not m or int(m.group(2)) == 0:
                # "HB 0" is a placeholder row, not a bill.
                continue
            if key in out and not a.fresh and not out[key].get("truncated"):
                continue
            time.sleep(a.delay)
            nreq += 1
            res = get(PAGE, postback(page, BILLS, {CMTE: cid, BILLS: bval}))
            told = stated_totals(res)
            # Page through only when the origin split is affordable. The totals
            # themselves come from the page, so a big bill costs one request
            # rather than seventy.
            g0 = Grid()
            g0.feed(res)
            npages = len(page_targets(res)) + 1
            if told and npages > a.max_pages:
                summary = {"total": told["support"] + told["oppose"] + told["neutral"],
                           **told, "by_position": {}, "pages": npages,
                           # No NH split: getting it would mean walking every
                           # page, and the totals do not need that.
                           "nh": 0, "out_of_state": 0, "origin_unknown": True}
                nreq += 1
            else:
                raw, head, npages, truncated = all_rows(res, cid, bval, a.delay,
                                                        cap=a.max_pages)
                nreq += npages - 1
                rows = [r for r in raw if len(r) >= 4]
                if not rows and not told:
                    continue
                summary = summarise(rows, head) if rows else {"total": 0}
                summary["pages"] = npages
                # Where the page states the totals, they win: they are exact
                # and cannot be cut short.
                if told:
                    summary.update(told)
                    summary["total"] = sum(told.values())
            # A bill nobody signed in on gets no record. Storing a zero would
            # put "0 signed in" under its hearing, which reads as a finding
            # rather than an absence.
            if not summary.get("total"):
                continue
            summary.update({
                "bill": key, "label": blabel, "committee": cname,
                # Where to read the individual entries, rather than copying
                # them here.
                "source": PAGE})
            out[key] = summary
            print(f"  {key:<10} {summary['total']:>5} signed in"
                  + (f" over {npages} pages" if npages > 1 else "") + "  "
                  f"{summary['oppose']} against / {summary['support']} for"
                  + (f" / {summary['neutral']} neutral" if summary["neutral"] else "")
                  + ("   (origin not counted, too many pages)"
                     if summary.get("origin_unknown") else
                     f"   ({summary.get('nh', 0)} NH"
                     + (f", {summary['out_of_state']} out of state"
                        if summary.get("out_of_state") else "") + ")"))
            if nreq % 20 == 0:
                op.write_text(json.dumps(out, indent=2), encoding="utf-8")

    op.write_text(json.dumps(out, indent=2), encoding="utf-8")
    tot = sum(v["total"] for v in out.values())
    print(f"\n{len(out):,} bills, {tot:,} sign-ins -> {a.out}")
    print(f"{nreq:,} requests")
    if out:
        top = sorted(out.values(), key=lambda v: -v["total"])[:5]
        print("\nMost signed-in:")
        for v in top:
            print(f"  {v['bill']:<10} {v['total']:>5}  "
                  f"{v['oppose']} against / {v['support']} for")
    print("\nSign-ins record who chose to register a position. Advocacy groups")
    print("organise them on every side, so this is a measure of who mobilised")
    print("and not a measure of public opinion. The site says so too.")


if __name__ == "__main__":
    main()
