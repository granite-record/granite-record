#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-06.2
"""
Senate committee reports, with their reasoning, from the General Court's
own database.

    python3 fetch_reports_db.py --sample 5    # read a few, write nothing
    python3 fetch_reports_db.py

WHY THIS EXISTS

The site's committee reports come from House Calendar PDFs, and that is a
House-only source. build_site_v2.committee_reports says so in as many words:
"a Senate report always [reaches the docket list], because the Senate prints
no reasoning."

That is true of the docket and false of the record. The database holds 1,446
Senate committee reports across 1,254 bills, and 1,096 of them carry the
committee's actual reasoning -- a median of 60 words explaining why. The site
has been showing a bare docket line for every one of them.

    committee, recommendation, vote, amendment, who signed, and the reasoning

WHAT IT DOES NOT DO

It does not touch the House. The database has 1,378 House bills with a
committee report; the calendar PDFs already give the site 1,901, with the same
text verbatim. Swapping a proven wider source for a narrower one to gain
nothing is not an improvement, so the House is left alone and this adds the
half that was missing.

It also leaves "Hearing Report" alone. That is a different document -- hearing
date, who attended, a bill analysis -- and calling it a committee report
because both are filed under CandH_Reports would put the wrong thing on the
page. It is worth having, separately, and is not this.

WHAT IT WRITES

senate_reports.json, in the record shape committee_reports.json uses, so
build_site_v2 can read the two together with no second format to understand.
A separate FILE rather than a merge into that one, because
fetch_committee_reports.py rebuilds it a calendar year at a time and decides
what to keep by looking for ", <year>" in each record's source. A record whose
source is not a calendar has no business in the middle of that.

HOW MUCH OF IT PARSES, MEASURED ON ALL 1,446

    calendar, date, committee, bill number, recommendation,
    vote, who signed                                        100%
    amendment number                                        35% (510, which
                                                            is how many are
                                                            reported with one)

And checked against a source this did not generate: the recommendation parsed
out of the report text agrees with the docket's own Senate report line on
1,443 of 1,443 bills where the docket has one, with no disagreements. The
other 3 are the reports that say HAS NO RECOMMENDATION, which the docket does
not record.

THIS IS NOT THE WEB SERVER. It is the SQL host the General Court publishes
credentials for, at gc.nh.gov/downloads. Nothing here touches gc.nh.gov, and
every statement is a SELECT.
"""

import argparse
import html
import json
import re
import sys
import tempfile
from pathlib import Path

import probe_db

SQL = """
SELECT ISNULL(BillNbr,''),
       ISNULL(FORMAT(ReleaseDate,'yyyy-MM-dd'),''),
       CAST(ISNULL(HTMLText,'') AS varchar(max))
FROM CandH_Reports
WHERE ChamberCode = 'S' AND CommitteeType = 'Committee Report'
  AND HTMLText IS NOT NULL AND DATALENGTH(HTMLText) > 0
ORDER BY BillNbr, ReleaseDate
"""

# The document, in the order it is laid out:
#
#     STATE OF NEW HAMPSHIRE / SENATE / REPORT OF THE COMMITTEE
#     REGULAR CALENDAR
#     Tuesday, March 17, 2026
#     THE COMMITTEE ON Judiciary
#     to which was referred CACR 11
#     A RESOLUTION relating to sheriffs. ...
#     Having considered the same, the committee recommends that the Resolution
#     OUGHT TO PASS WITH AMENDMENT
#     BY A VOTE OF: 4-0
#     AMENDMENT # 2026-1219s
#     Senator Tara Reardon
#     For the Committee
#     <the aide, with a phone number>
#     <the reasoning, where there is any>
#     REGULAR CALENDAR            <- the calendar entry repeats the whole thing
#
# Written after reading thirty of them rather than from a description of the
# format, which is the rule that produced every good parser in this project.
CALENDAR = re.compile(r"\b(REGULAR CALENDAR|CONSENT CALENDAR)\b")
PRINTED = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|"
                     r"Sunday),\s*([A-Z][a-z]+ \d{1,2},\s*\d{4})")
COMMITTEE = re.compile(r"THE COMMITTEE ON\s*\n?\s*(.+?)\s*\n", re.I)
REFERRED = re.compile(r"to which was referred\s*\n?\s*([A-Z]{2,5}\s*\d+)", re.I)
TITLE = re.compile(r"to which was referred\s*\n?\s*[A-Z]{2,5}\s*\d+\s*\n"
                   r"(.+?)\n\s*Having considered", re.I | re.S)
RECOMMEND = re.compile(r"committee recommends that the (?:Bill|Resolution|CACR)"
                       r"\s*\n?\s*(.+?)\s*\n\s*BY A VOTE OF", re.I | re.S)
VOTE = re.compile(r"BY A VOTE OF:\s*(\d+)\s*-\s*(\d+)", re.I)
AMENDMENT = re.compile(r"AMENDMENT\s*#\s*([0-9A-Za-z\-]+)", re.I)
AUTHOR = re.compile(r"\n(Senator[^\n]*?)\s*\n\s*For the Committee", re.I)

FOR_CMTE = re.compile(r"\n\s*For the Committee\s*\n", re.I)
CAL_REPEAT = re.compile(r"\n\s*(?:FOR THE\s+)?(?:REGULAR|CONSENT)\s+CALENDAR\s*\n",
                        re.I)
# "Brendan Bunnell 271-4063" -- the committee aide, on their own line. Not part
# of what the committee said, and not a person the page has anything to say
# about.
AIDE = re.compile(r"^\s*[A-Z][A-Za-z.'\- ]+\s+\(?\d{3}[\-–]\d{4}\)?\s*$")

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], 1)}


def text_of(h):
    """The report as text, with its line structure kept.

    The line structure IS the format here: the committee, the bill and the
    recommendation are each on their own line and are told apart by that.
    Flattening to one paragraph, which is the usual way to strip HTML, would
    throw away the only thing separating them.
    """
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h or "")
    h = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = html.unescape(h).replace(" ", " ")
    h = re.sub(r"[ \t]+", " ", h)
    return re.sub(r"\n[ \t]*", "\n", h).strip()


def iso(printed):
    """'March 17, 2026' -> '2026-03-17', or '' if it is not a date."""
    m = re.match(r"([A-Z][a-z]+) (\d{1,2}),\s*(\d{4})", printed or "")
    if not m or m.group(1) not in MONTHS:
        return ""
    return f"{m.group(3)}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"


def reasoning(t):
    """What the committee said, after the formal block and before the repeat.

    Empty for the 350 reports that carry no reasoning at all, which is a real
    answer: those committees filed a recommendation and nothing else.
    """
    m = FOR_CMTE.search(t)
    if not m:
        return ""
    tail = t[m.end():]
    c = CAL_REPEAT.search(tail)
    if c:
        tail = tail[:c.start()]
    keep = [ln for ln in tail.split("\n") if ln.strip() and not AIDE.match(ln)]
    return " ".join(keep).strip()


def parse_one(bill, release, raw):
    """One report, or None with a reason."""
    t = text_of(raw)
    need = {"committee": COMMITTEE, "recommend": RECOMMEND, "vote": VOTE,
            "author": AUTHOR, "referred": REFERRED}
    got = {}
    for k, pat in need.items():
        m = pat.search(t)
        if not m:
            return None, f"no {k}"
        got[k] = m
    if got["referred"].group(1).replace(" ", "").upper() != bill.upper():
        return None, (f"the text is about {got['referred'].group(1)}, "
                      f"not {bill}")
    pr = PRINTED.search(t)
    date = iso(pr.group(1)) if pr else ""
    cal = CALENDAR.search(t)
    am = AMENDMENT.search(t)
    ti = TITLE.search(t)
    # "the committee recommends that the Bill BE REFERRED TO INTERIM STUDY".
    # The auxiliary belongs to that sentence, not to the motion: the docket
    # writes the same motion as "Referred to Interim Study", and a chip reading
    # "BE REFERRED TO INTERIM STUDY" beside a House chip reading "OUGHT TO
    # PASS" looks like two different vocabularies rather than one.
    rec = re.sub(r"\s+", " ", got["recommend"].group(1)).strip().upper()
    rec = re.sub(r"^(?:IS|BE|HAS)\s+", "", rec)
    return {
        "bill": bill.upper(),
        # Which chamber reported. build_site_v2 joins this record to the
        # docket's own line to pick up the signing date and the journal page,
        # and without the chamber that join matched on the recommendation
        # alone: 364 of these took a House Calendar citation and a House
        # signing date, because "Ought to Pass" is what both chambers say.
        "body": "S",
        "title": re.sub(r"\s+", " ", ti.group(1)).strip() if ti else "",
        # Not a calendar citation. build_site_v2 reads a calendar out of this
        # field to date and link a House report; naming this one plainly keeps
        # it out of that path instead of half-matching it.
        "source": f"Senate committee report, released {release}",
        "date": date or release,
        "dated": "printed" if date else "released",
        "calendar": cal.group(1).title() if cal else "",
        "majority_recommendation": rec,
        "minority_recommendation": "",
        "reports": [{
            # The Senate files one report per bill with no minority, which is
            # the same "Committee" side the docket path already uses for it.
            "side": "Committee",
            "author": re.sub(r"\s+", " ", got["author"].group(1)).strip(),
            "committee": re.sub(r"\s+", " ", got["committee"].group(1)).strip(),
            "vote_yeas": int(got["vote"].group(1)),
            "vote_nays": int(got["vote"].group(2)),
            "amendment": am.group(1) if am else "",
            "text": reasoning(t),
        }],
    }, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="senate_reports.json")
    ap.add_argument("--sample", type=int, default=0,
                    help="print this many parsed reports and write nothing")
    ap.add_argument("--force-write", action="store_true")
    a = ap.parse_args()

    base = (f"Database={probe_db.DATABASE};User ID={probe_db.USER};"
            f"Password={probe_db.PASSWORD};Encrypt=False;"
            "TrustServerCertificate=True;Connect Timeout=20")
    cs = f"Server={probe_db.HOST};{base}"

    print("SELECT only, one connection: Senate committee reports")
    tmp = tempfile.TemporaryDirectory()
    raw = Path(tmp.name) / "reports.txt"
    # newline=" " because this column is HTML: a line break between two words
    # is the only space between them, and deleting it runs them together.
    n, err = probe_db.run_to_file(cs, SQL, raw, newline=" ", every=400,
                                  label="reports ")
    if err:
        sys.exit(f"  the database refused: {err}")
    print(f"  {n:,} reports")
    if not n:
        sys.exit("  nothing came back. CandH_Reports held 1,446 on 6 September.")

    out, failed = {}, []
    with raw.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            p = line.rstrip("\n").split("|", 2)
            if len(p) < 3:
                continue
            rec, why = parse_one(p[0].strip(), p[1].strip(), p[2])
            if rec is None:
                failed.append((p[0].strip(), why))
                continue
            out.setdefault(rec["bill"], []).append(rec)
    tmp.cleanup()

    prose = sum(1 for v in out.values() for r in v
                if len(r["reports"][0]["text"].split()) >= 15)
    total = sum(len(v) for v in out.values())
    print(f"  {total:,} parsed across {len(out):,} bills, "
          f"{prose:,} carrying the committee's reasoning")
    if failed:
        print(f"  {len(failed):,} could not be read:")
        for bill, why in failed[:8]:
            print(f"    {bill}: {why}")

    # A parse that quietly drops most of what it read is the failure this
    # project keeps meeting, so it is refused rather than written.
    if total < n * 0.9 and not a.force_write:
        sys.exit(f"\nNOT WRITING {a.out}: {total:,} of {n:,} reports parsed. "
                 "That is a format change, not a session with fewer reports. "
                 "Pass --force-write to override.")

    if a.sample:
        for bid in sorted(out)[:a.sample]:
            print("\n" + "=" * 70)
            print(json.dumps(out[bid], indent=1)[:1400])
        print(f"\n--sample: nothing written to {a.out}")
        return 0

    p = Path(a.out)
    if p.exists():
        try:
            had = len(json.loads(p.read_text(encoding="utf-8")))
        except ValueError:
            had = 0
        if had and len(out) < had * 0.5 and not a.force_write:
            sys.exit(f"\nNOT WRITING {a.out}: this run found {len(out):,} bills "
                     f"against {had:,} already on file.")
    p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
