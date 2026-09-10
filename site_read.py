#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.1
"""
The built site, read back: one reader of the record inside a page.

Every bill's record used to sit beside its page as site/bills/<year>/<ID>.json
and three tools read it there with a glob. Then the records moved INSIDE the
pages -- one file per bill instead of two, which is what took the site from
73,086 files to 39,501 -- and site/bills/ was left holding the 98 records too
large to inline. The globs still matched. They just matched 98 files instead
of 33,683, and nothing failed:

    IS EVERY SCHEDULED PROCEEDING ON THE SITE  (6,781 in the manifest)
      on the site      290   4%
      absent         6,491   96%

Nothing was absent. 10,310 stations were published and the reader was looking
in the wrong place, and because the answer was a number rather than an error
it read as a catastrophe instead of as a bug. That is this project's oldest
failure -- a tool run against a subset, reporting confidently on the whole --
and the fix for it here is to stop having several readers of one convention.

The convention, which shell.py writes:

    <script type="application/json" id="gr-data">{...}</script>   inlined
    <meta name="gr-data" content="/bills/2025/HB1.json">          kept beside

build_bill_pages.embedded() reads the first of those for its own idempotence
and predates this; it is the writer's own read-back and is left where it is.
Anything that wants to know what the site published should come here.
"""

import json
import re
from pathlib import Path

INLINE = re.compile(
    r'<script type="application/json" id="gr-data">(.*?)</script>', re.S)
META = re.compile(r'<meta name="gr-data" content="([^"]+)"')


def records(site="site", years=None):
    """(year, BILLID, record) for every bill page that carries one.

    years limits the walk to those directories -- a caller that only cares
    about the terms with recordings reads 2,234 pages instead of 33,683.
    """
    site = Path(site)
    root = site / "bill"
    if not root.is_dir():
        return
    dirs = ([root / str(y) for y in years] if years
            else sorted(d for d in root.iterdir() if d.is_dir()))
    for d in dirs:
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.html")):
            text = f.read_text(encoding="utf-8", errors="replace")
            m = INLINE.search(text)
            if m:
                raw = m.group(1)
            else:
                mm = META.search(text)
                if not mm:
                    continue
                side = site / mm.group(1).lstrip("/")
                if not side.exists():
                    continue
                raw = side.read_text(encoding="utf-8")
            try:
                yield d.name, f.stem.upper(), json.loads(raw)
            except ValueError:
                # A page whose record will not parse is worth knowing about,
                # but it is one page: the caller counts them rather than
                # having the walk stop on it.
                continue


def stations(site="site", years=None):
    """(year, BILLID, station) for every proceeding the site publishes."""
    for year, bid, rec in records(site, years):
        for s in (rec.get("stations") or []):
            yield year, bid, s


def video_years(default=("2025", "2026")):
    """The years that have recordings, from proceedings.csv's own terms.

    A pair of literals would go stale the first time an earlier term gets
    video, and the terms are already written down.
    """
    try:
        import proceedings as P
        found = sorted({y for r in P.load() if r.get("video_id")
                        for y in str(r.get("term") or "").split("-")
                        if y.isdigit()})
        return found or list(default)
    except Exception:
        return list(default)
