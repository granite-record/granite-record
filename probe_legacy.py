#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.2
"""
The years the database does not have, from the search the site already offers.

    python3 probe_legacy.py --year 2019           # two requests
    python3 probe_legacy.py --year 2019 --raw     # and keep the results page

WHY THIS EXISTS

The General Court's public database covers 1989-2016 and 2025-2026 and has
nothing for 2017-2024. Those eight years are wanted: bill numbers, titles,
dockets and status, with links out for the rest.

They are not missing from the web. The Advanced Bill Status Search at
/bill_status/legacy/bs2016/ takes a session year, says "1989-Current" beside
the box, and answers 2019 with 768 bills -- each with its title, general and
per-chamber status, last committee, last hearing, and links to its docket,
status, text and history. That is the whole of what an archived bill needs.

WHAT THE FIRST ATTEMPT GOT WRONG

It sent a GET with invented query parameters and got HTTP 500. The page is an
ASP.NET WebForm: it wants a POST carrying __VIEWSTATE, and the year lives in
txtsessionyear. Guessing the shape of a request is the same mistake as
guessing the shape of a filename, and it produced the same useless answer.

So this does what a browser does. Load the form, take the hidden fields it
gives you, post them back with the year filled in. The same pattern
probe_calendars.py uses for the calendar index, and for the same reason.

WHAT IT WILL NOT DO

Two requests. One year. It does not sweep years and does not retry. Whether
eight years are worth sixteen requests is a decision for a person, and this
exists to inform it rather than to act on it.
"""

import argparse
import html as _html
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://gc.nh.gov/bill_status/legacy/bs2016/"
UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "corrections@graniterecord.org)"}

HIDDEN = re.compile(r"<input\b[^>]*type=[\"']hidden[\"'][^>]*>", re.I)
ATTR = re.compile(r"(\w[\w:-]*)\s*=\s*[\"']([^\"']*)[\"']")
FOUND = re.compile(r"Bills?\s+Found\s*:?\s*([\d,]+)", re.I)
BILLNO = re.compile(r"\b(CACR|HB|SB|HR|SR|HCR|SCR|HJR|SJR)\s?0*(\d{1,4})\b")
# The links each result offers. These are what an archived bill would cite.
LINKS = re.compile(r"(billdocket|bill_status|billText|billHistory)\.aspx"
                   r"\?[^\"'<>\s]*", re.I)


def get(url, data=None):
    req = urllib.request.Request(
        url, data=data,
        headers=dict(UA, **({"Content-Type":
                             "application/x-www-form-urlencoded"} if data else {})))
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode("utf-8", errors="replace"), r.status


def hidden_fields(page):
    out = {}
    for m in HIDDEN.finditer(page):
        a = {k.lower(): v for k, v in ATTR.findall(m.group(0))}
        if a.get("name"):
            out[a["name"]] = _html.unescape(a.get("value", ""))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", required=True,
                    help="a session year, e.g. 2019. The form says 1989-Current")
    ap.add_argument("--raw", action="store_true", help="save the results page")
    a = ap.parse_args()

    print(f"1/2  loading the search form: {URL}")
    try:
        form, _ = get(URL)
    except Exception as e:
        sys.exit(f"  failed: {type(e).__name__}: {e}\n"
                 "  netcheck.py diagnoses a refusal without making it worse.")
    fields = hidden_fields(form)
    print(f"     {len(fields)} hidden field(s): {', '.join(fields) or 'none'}")

    # Everything else on the form may be left empty; these three are what the
    # browser sends when you type a year and press Submit.
    fields["txtsessionyear"] = str(a.year)
    fields["sortoption"] = "billnumber"
    fields["cmdsubmit"] = "Submit"

    print(f"2/2  posting txtsessionyear={a.year}")
    try:
        page, status = get(URL, urllib.parse.urlencode(fields).encode())
    except urllib.error.HTTPError as e:
        sys.exit(f"  HTTP {e.code}. The form did not accept that.")
    except Exception as e:
        sys.exit(f"  failed: {type(e).__name__}: {e}")

    found = FOUND.search(page)
    bills = sorted({f"{m.group(1).upper()}{int(m.group(2))}"
                    for m in BILLNO.finditer(page)})
    links = LINKS.findall(page)
    print(f"\n  HTTP {status}, {len(page):,} chars")
    if found:
        print(f"  the page says: Bills Found : {found.group(1)}")
    print(f"  {len(bills):,} distinct bill numbers")
    print(f"  {len(links):,} per-bill links (docket, status, text, history)")
    if bills:
        print("  first few: " + ", ".join(bills[:14]))
    for label in ("Title:", "G-Status:", "House Status:", "Senate Status:",
                  "Next/Last Comm:", "Next/Last Hearing:"):
        print(f"    {label:<20} {'present' if label in page else 'ABSENT'}")

    if a.raw:
        out = Path(f"probe_legacy_{a.year}.html")
        out.write_text(page, encoding="utf-8")
        print(f"\n  wrote {out}")

    print()
    n = int((found.group(1) if found else "0").replace(",", "") or 0)
    if n > 100:
        print(f"  {n:,} bills for {a.year}, from two requests. The eight years")
        print("  the database is missing cost sixteen requests in total, and")
        print("  they carry title, status and the links an archived bill cites.")
        print("  Read the saved page before writing a parser against it.")
    else:
        print("  Not a year listing. Save it and look before concluding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
