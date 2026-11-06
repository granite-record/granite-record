#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-06.1
"""
Which guide claims a fresh reading of the state's pages may have overtaken,
guide by guide in the order they are checked: the worksheet a reader takes
to fact_sheet.py.

    python3 src/checks/recheck_sources.py --readings sources          # every guide, in ORDER
    python3 src/checks/recheck_sources.py --readings DIR how-to-vote  # one guide
    python3 src/checks/recheck_sources.py --order                     # the order, and why

WHY (6 November 2026, the manager session). The laptop's weekly run reads
the state's pages into sources/<id>/<YYYY-MM-DD>.txt (or .pdf), and
state_sources.py down brings them to any machine holding the bucket's keys.
A guide's claims each name the page they rest on and the day it was read
(guides.claim). When a page has been read since a claim was, the claim may
no longer be what the page says. This finds those claims and lists them in
the checking order (ORDER). For each claim it says whether the figures,
phone numbers, form numbers, counts, times and dates in the claim's own
words are still in the reading. docs/SOURCE_RECHECK.md says how a reader
works the list, and what a CHANGED finding looks like.

WHAT IT CANNOT DO. A claim is the guide's summary of a page, not a quote.
So the words around those anchors -- "must" or "may", a condition, who
qualifies -- are a reader's to compare (fact_sheet.py <slug> prints the page
beside its claims). An anchor found is not "nothing changed", and an anchor
missing is not "changed": it is where to look first. Each line says which.

It reads the code, records/sources/REGISTRY.csv and the readings folder. No
network, and it writes nothing.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import csv
import html
import json
import re
import shutil
import subprocess

import guides

# THE CHECKING ORDER (the manager session, 6 November 2026: "highest-traffic
# guides first (voting, DMV, property tax, benefits)"). No traffic figures
# are on hand, so these four themes come first as asked, and within each the
# home page's Common Questions (guides.HOME) lead, then the guides that rest
# most on agency pages. A guide that rests on no agency page (the General
# Court's own guides) has nothing here to recheck and is not listed;
# preflight's _recheck_order holds every other published guide to a place.
ORDER = [
    ("Voting", ["how-to-vote", "run-for-office", "election-worker"]),
    ("DMV", ["renew-drivers-license", "new-to-new-hampshire", "real-id", "register-a-car",
             "motorcycle-license", "vanity-and-special-plates"]),
    ("Property tax", ["property-tax-relief", "property-tax-abatement", "property-tax-bill"]),
    ("Benefits", ["food-and-health-assistance", "heating-and-electric-help", "health-insurance",
                  "medicare-and-social-security", "disability-help", "child-care-scholarship",
                  "file-for-unemployment"]),
    ("Housing, safety and rights", ["tenant-rights", "landlord-duties", "homelessness-help",
                                    "domestic-violence-help", "wage-rights", "consumer-rights",
                                    "discrimination"]),
    ("Everything else", ["vital-records", "public-records", "passport", "storms-and-emergencies",
                         "car-insurance", "homeowners-insurance", "renters-insurance",
                         "fishing-license", "hunting-license", "boating", "building-permits",
                         "trash-and-recycling", "report-a-road-problem", "who-to-contact",
                         "town-warrant-article"]),
]

# THE ANCHORS: the parts of a claim's words a machine can look for in a
# page's text. Each is (its kind, a pattern).
MONTHS = ("January|February|March|April|May|June|July|August|September|October|November|"
          "December")
ANCHORS = [
    ("money", re.compile(r"\$\s?\d[\d,]*(?:\.\d\d)?")),
    ("percent", re.compile(r"\b\d+(?:\.\d+)?\s?%")),
    ("phone", re.compile(r"(?:\b1-)?\(?\b\d{3}\)?[-. ]\d{3}-\d{4}\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    ("form", re.compile(r"\b(?!RSA\b|HB\b|SB\b|CACR\b)[A-Z]{2,5}[- ]?\d{1,4}[A-Z]?\b")),
    ("count", re.compile(r"\b\d+\s+(?:business\s+|calendar\s+)?(?:days?|weeks?|months?|years?|"
                         r"hours?)\b", re.I)),
    ("time", re.compile(r"\b\d{1,2}(?::\d\d)?\s?(?:a\.\s?m\.|p\.\s?m\.|am\b|pm\b)", re.I)),
    ("date", re.compile(rf"\b(?:{MONTHS})\s+\d{{1,2}}(?:,\s+\d{{4}})?")),
]


def norm(s):
    """Text compared the same way on both sides: entities and case off,
    dashes and spaces made one, "$ 50" as "$50", "5 p.m." as "5 pm"."""
    s = html.unescape(str(s or "")).replace("\xa0", " ")
    s = re.sub(r"[‐-―]", "-", s).lower()
    s = re.sub(r"\$\s+", "$", s)
    s = re.sub(r"\b([ap])\.\s?m\.", r"\1m", s)
    return re.sub(r"\s+", " ", s)


def anchors(says):
    """[(kind, the words)] of a claim, each once, in the order they appear."""
    seen, out = set(), []
    for kind, pat in ANCHORS:
        for m in pat.finditer(says or ""):
            w = m.group(0).strip()
            if (kind, w) not in seen:
                seen.add((kind, w))
                out.append((kind, w))
    return out


def found(kind, words, text, digits):
    """Whether `words` of `kind` are in a reading (`text` normalised,
    `digits` its digits alone, for a phone number written any way)."""
    if kind == "phone":
        return re.sub(r"\D", "", words)[-10:] in digits
    return norm(words) in text


def url_key(u):
    return re.sub(r"^https?://(www\.)?", "", str(u or "").strip().lower()).rstrip("/")


def registry(root):
    """{address as compared: registry row} of records/sources/REGISTRY.csv."""
    p = Path(root) / "records" / "sources" / "REGISTRY.csv"
    with p.open(encoding="utf-8", newline="") as fh:
        return {url_key(r["url"]): r for r in csv.DictReader(fh) if r.get("url")}


def latest(readings, rid):
    """(the day, the file) of a registry row's newest reading, or None."""
    d = Path(readings) / rid
    files = sorted(f for f in d.glob("*") if re.fullmatch(r"\d{4}-\d\d-\d\d\.(txt|pdf)", f.name)) \
        if d.is_dir() else []
    if not files:
        return None
    # A day's text and PDF both: the text, which this reads.
    day = files[-1].name[:10]
    same = [f for f in files if f.name.startswith(day)]
    return day, next((f for f in same if f.suffix == ".txt"), same[0])


def text_of(f):
    """A reading's text: a .txt as saved, a .pdf through pdftotext where this
    machine has it, else None (a reader opens the PDF)."""
    if f.suffix == ".txt":
        return f.read_text(encoding="utf-8", errors="replace")
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    r = subprocess.run([exe, "-layout", "-enc", "UTF-8", str(f), "-"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout if r.returncode == 0 else None


def sheet(g, reg, readings):
    """The claims of guide `g` whose page has a reading, each with its outcome:
    [{source, registry, checked, read, file, outcome, anchors: [(kind, words, found)]}]."""
    out = []
    for c in g["claims"]:
        src = str(c["source"])
        if not src.startswith("http") or "gc.nh.gov" in src:
            continue
        row = reg.get(url_key(src))
        item = {"source": src, "says": c["says"], "checked": c["checked"],
                "registry": row["id"] if row else None, "read": None, "file": None, "anchors": []}
        if not row:
            item["outcome"] = "NOT IN REGISTRY"
        else:
            got = latest(readings, row["id"])
            if not got:
                item["outcome"] = "NOT READ"
            else:
                item["read"], f = got
                item["file"] = str(f)
                if c["checked"] and item["read"] <= c["checked"]:
                    item["outcome"] = "NOT NEWER"
                else:
                    t = text_of(f)
                    if t is None:
                        item["outcome"] = "PDF: OPEN IT"
                    else:
                        text, digits = norm(t), re.sub(r"\D", "", t)
                        item["anchors"] = [(k, w, found(k, w, text, digits)) for k, w in anchors(c["says"])]
                        if not item["anchors"]:
                            item["outcome"] = "READ IT"
                        elif all(ok for _k, _w, ok in item["anchors"]):
                            item["outcome"] = "ANCHORS HOLD"
                        else:
                            item["outcome"] = "LOOK"
        out.append(item)
    return out


def ordered(slugs=None):
    """[(theme, guide)] of the published guides in ORDER, or of `slugs`."""
    by = {g["slug"]: g for g in guides.GUIDES}
    pairs = [(theme, by[s]) for theme, ss in ORDER for s in ss if s in by]
    return [p for p in pairs if p[1]["slug"] in slugs] if slugs else pairs


# Where each outcome sends a reader, in the order they should go.
NEXT = {
    "LOOK": "an anchor is missing from the page: compare first",
    "ANCHORS HOLD": "every anchor is on the page: read the rest of the claim",
    "READ IT": "no anchor to look for: read the claim against the page",
    "PDF: OPEN IT": "the reading is a PDF this machine cannot read: open it",
    "NOT NEWER": "the page was not read since the claim was",
    "NOT READ": "the page has no reading yet",
    "NOT IN REGISTRY": "the weekly run does not read this page: a printout or a new registry row",
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("slugs", nargs="*", help="only these guides")
    ap.add_argument("--readings", default="sources", help="the folder state_sources.py down fills")
    ap.add_argument("--order", action="store_true", help="print the checking order and stop")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = _paths.ROOT
    if a.order:
        for i, (theme, g) in enumerate(ordered(a.slugs), 1):
            print(f"{i:2}. {theme:28} {g['slug']}")
        return 0
    readings = Path(a.readings)
    if not readings.is_dir() or not any(readings.iterdir()):
        print(f"no readings in {readings}: run state_sources.py down first (it needs the bucket's "
              "keys), or name the folder they are in with --readings")
        return 1
    reg, rows = registry(root), []
    for theme, g in ordered(a.slugs):
        rows.append({"theme": theme, "slug": g["slug"], "title": g["title"],
                     "claims": sheet(g, reg, readings)})
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    tally = {}
    for r in rows:
        print(f"\n=== {r['theme']}: {r['slug']} ({r['title']})   "
              f"python3 src/checks/fact_sheet.py {r['slug']}")
        for c in sorted(r["claims"], key=lambda c: list(NEXT).index(c["outcome"])):
            tally[c["outcome"]] = tally.get(c["outcome"], 0) + 1
            print(f"  {c['outcome']:16} {c['registry'] or c['source']}"
                  + (f"  read {c['read']} (claim {c['checked']})" if c["read"] else ""))
            if c["outcome"] in ("LOOK", "ANCHORS HOLD", "READ IT", "PDF: OPEN IT"):
                print(f"      claim: {c['says'][:300]}")
                missing = [f"{k} {w!r}" for k, w, ok in c["anchors"] if not ok]
                if missing:
                    print("      not on the page: " + "; ".join(missing))
                if c["file"]:
                    print(f"      page:  {c['file']}")
    print("\n" + "; ".join(f"{n} {k}" for k, n in sorted(tally.items(), key=lambda kv: list(NEXT).index(kv[0])))
          + f" ({sum(tally.values())} claims on agency pages, {len(rows)} guides)")
    for k in NEXT:
        if k in tally:
            print(f"  {k}: {NEXT[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
