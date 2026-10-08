#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.8
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
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import io
import json
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

# One row of the results page, for the fallback: the number and body on one
# line, the sponsors on the next.
ROW = re.compile(
    r"(\d{4}-\d{3,4})\s*\t?\s*(HB|SB|CACR|HR|SR|HCR|SCR)\s*\t?\s*Title:\s*(.+?)\s*"
    r"Sponsors:\s*\(Prime\)\s*(.+?)\s*(?=\d{4}-\d{3,4}\s|\Z)", re.S)

# "2027-0001", the shape of a request number, and the session it belongs to.
LSR_NO = re.compile(r"^\s*(\d{4})-(\d{3,4})\s*$")


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


def parse_results_html(html):
    """The results page, for when the CSV cannot be had.

    Its rows carry exactly what an LSR has -- number, body, title, prime
    sponsor -- so nothing is lost by reading them; it is only more fragile
    than a file with headers, which is why it is the fallback and not the
    first choice.
    """
    text = re.sub(r"<[^>]+>", "\n", html)
    text = html_unescape(text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    out = []
    for num, body, title, sponsor in ROW.findall(text):
        m = LSR_NO.match(num)
        if not m:
            continue
        out.append({"lsr": num, "session": int(m.group(1)), "body": body.upper(),
                    "title": " ".join(title.split()),
                    "sponsor": " ".join(sponsor.split()), "withdrawn": False})
    return out


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
        out.append({"lsr": num, "session": int(m.group(1)),
                    # NOT truncated. The column carries CACR and HCR as well as
                    # HB and HR, and a two-character slice turned those into
                    # "CA" and "HC", which are not kinds of anything.
                    "body": g("body").strip().upper(),
                    "title": " ".join(g("title").split()),
                    "sponsor": prime, "cosponsors": co,
                    "withdrawn": False})
    if not out:
        raise SystemExit(
            f"  {len(rows)-1} rows and not one carried a request number of the "
            "shape 2027-0001. That is a format change, not an empty session.")
    return out


ROLE = re.compile(r"\s*\(([^)]*)\)\s*$")


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
    """
    prime, co = "", []
    for part in re.split(r"\s*;\s*", (field or "").strip()):
        if not part:
            continue
        m = ROLE.search(part)
        role = (m.group(1) if m else "").strip().lower()
        name = " ".join(ROLE.sub("", part).split())
        if not name:
            continue
        if "prime" in role and not prime:
            prime = name
        else:
            co.append(name)
    if not prime and co:
        prime, co = co[0], co[1:]
    return prime, co


def merge(new):
    """New rows over old, and a request that has gone is kept and marked.

    A request vanishing between runs is a withdrawal, which is a fact about
    the record rather than a gap in it. Dropping it would make the site
    quietly disagree with what it said last week.

    Or it is an introduction, which the list alone cannot tell from a
    withdrawal: a request drafted and filed becomes a bill. The flag says only
    that it left the list, and build_lsrs.became_bills reads the bills to say
    which -- a request whose number a bill carries reads "Introduced as HB 45".
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
        if k not in seen and not r.get("withdrawn"):
            r["withdrawn"] = True
            gone += 1
    merged = {**old, **{r["lsr"]: {**old.get(r["lsr"], {}), **r} for r in new}}
    return [merged[k] for k in sorted(merged)], gone


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="load the search page and report what it offers; save nothing")
    ap.add_argument("--parse", action="store_true",
                    help="re-read the saved CSV; touches no network")
    a = ap.parse_args()

    # --parse asks nobody, so neither a refusal nor GitHub's night stops it:
    # the check comes after it, as fetch_legislation.py's does.
    if a.parse:
        if not RAW_CSV.exists():
            raise SystemExit(f"  {RAW_CSV} is not here. Run without --parse first.")
        rows = parse_csv(RAW_CSV.read_text(encoding="utf-8", errors="replace"))
        merged, gone = merge(rows)
        OUT.write_text(json.dumps(merged, indent=1), encoding="utf-8")
        print(f"{len(rows)} requests parsed -> {OUT}"
              + (f"; {gone} newly marked withdrawn" if gone else ""))
        return 0
    # One writer per file: the night takes the requests, and lsrs.json reaches
    # this machine from R2.
    refusal.stand_down("The LSR fetch", "GitHub's nightly takes next session's bill "
                       "requests now, and lsrs.json reaches this machine from R2.")
    refusal.check("The LSR fetch")

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
        rows = parse_results_html(raw2.decode(enc3, "replace"))
        if not rows:
            raise SystemExit(
                "  the results page yielded no requests either. Both are saved "
                "under archive/; read them before asking again.")
        print(f"  {len(rows)} requests read from the results page")
    merged, gone = merge(rows)
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
