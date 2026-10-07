#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.4
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

And every bill's row -- the list the bills page and the search draw from --
is read here too, by bill_index(), from the per-term files the pages fetch
(5 October 2026). The block above it says why, and what its three answers
are.
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
            rec = _page_record(site, f)
            if rec is not None:
                yield d.name, f.stem.upper(), rec


def _page_record(site, f):
    """The record one bill page carries, inlined or beside it; None if none.

    A page whose record will not parse is worth knowing about, but it is one
    page: the caller counts them rather than having the walk stop on it.
    """
    text = f.read_text(encoding="utf-8", errors="replace")
    m = INLINE.search(text)
    if m:
        raw = m.group(1)
    else:
        mm = META.search(text)
        if not mm:
            return None
        side = Path(site) / mm.group(1).lstrip("/")
        if not side.exists():
            return None
        raw = side.read_text(encoding="utf-8")
    try:
        return json.loads(raw)
    except ValueError:
        return None


def one(site, year, bid):
    """One bill's record, by the folder year and the bill id; None if absent.

    For a caller that wants a single bill -- the report compiler shows what a
    page says beside what a reader said about it -- and should not walk a
    year of pages to find it. Same convention, same reading, as records().
    """
    f = Path(site) / "bill" / str(year) / f"{str(bid).lower()}.html"
    return _page_record(site, f) if f.is_file() else None


def stations(site="site", years=None):
    """(year, BILLID, station) for every proceeding the site publishes."""
    for year, bid, rec in records(site, years):
        for s in (rec.get("stations") or []):
            yield year, bid, s


def by_bill(site="site", years=None, fields=None):
    """{(year, BILLID): record}, from one walk, for callers that look bills up.

    The committee pages and the feeds used to open site/bills/<year>/<ID>.json
    one bill at a time, and when the records moved inside the pages those
    files stopped existing for all but the largest few. A missing file read as
    "this bill has nothing", so for two days the committee pages printed no
    time for 9,672 proceedings the bill pages timed, and 5,436 bill pages
    advertised a feed nobody wrote. A lookup keyed the same way as the old
    path, filled from here, cannot drift from the pages again.

    fields keeps only those keys of each record: the feeds need the events
    and sponsors of 9,739 bills, not every ballot of 33,683. The year is the
    folder the page sits in, as a string, and the bill is upper case.
    """
    out = {}
    for year, bid, rec in records(site, years):
        out[(year, bid)] = ({k: rec[k] for k in fields if k in rec}
                            if fields else rec)
    return out


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


# ---- the bill index ------------------------------------------------------------
#
# ONE READER OF EVERY BILL'S ROW (5 October 2026). Every bill's row -- title,
# sponsor, committee, topic, status, passage -- is published one term to a
# file, site/idx/<term>.json, and site/meta.json names the terms. Those are
# what every page fetches. The build's own readers read site/index.json
# instead: the same rows joined into one file that no page fetched, 23.7 MB
# on 2 October -- nine tenths of the 25 MiB Cloudflare Pages takes in one
# file -- and a term's worth bigger with every field added to a row. They read
# the term files now, here, and the answer keeps apart three things a missing
# file used to blur:
#
#   no site built yet   None: there is no site/meta.json. GitHub's machine
#                       starts with site/ empty, and the callers that treat
#                       that as normal -- handoff, the nightly's census,
#                       preflight's data checks -- say so and go on.
#   broken              Broken, raised: meta.json will not read or names no
#                       term; a term it names has no file, or an empty or
#                       unreadable one; a row sits in another term's file;
#                       idx/ holds a term meta.json does not name, or term
#                       files and no meta.json at all. Each is a site whose
#                       pages would offer a different list of bills from the
#                       one it describes.
#   whole               every row: the terms in meta.json's order, which is
#                       newest first, and each term's rows in its file's order.
#
# The next session's bill requests (idx/<year>-requests.json, which meta.json
# names under "requests") are not bills, and are not in it.

TERM_FILE = re.compile(r"\d{4}-\d{4}")


class Broken(Exception):
    """The bill index is on disk and does not hold together. The message says
    which file, and how."""


def bill_index_files(meta):
    """The index files a meta.json names, as paths under the site: each term
    in its order, then the bill requests where it names them. For a caller
    that wants the bytes rather than the rows -- the nightly's fingerprint,
    of a built site and of what production serves."""
    meta = meta if isinstance(meta, dict) else {}
    terms = meta.get("terms") if isinstance(meta.get("terms"), list) else []
    names = [f"idx/{t}.json" for t in terms
             if isinstance(t, str) and TERM_FILE.fullmatch(t)]
    req = meta.get("requests")
    if isinstance(req, dict) and isinstance(req.get("term"), str) and req["term"]:
        names.append(f"idx/{req['term']}.json")
    return names


def bill_index(site="site"):
    """Every bill row the site publishes; None where no site is built.

    Raises Broken where the index is there and does not hold together. The
    block above says what each answer means.
    """
    site = Path(site)
    mp, idx = site / "meta.json", site / "idx"
    if not mp.exists():
        stray = (sorted(f.name for f in idx.glob("*.json") if TERM_FILE.fullmatch(f.stem))
                 if idx.is_dir() else [])
        if stray:
            raise Broken(f"{idx} holds {len(stray)} term file(s) ({', '.join(stray[:3])}) "
                         f"and there is no {mp} to say which are the site's")
        return None
    try:
        meta = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Broken(f"{mp} will not read: {e}") from None
    terms = meta.get("terms") if isinstance(meta, dict) else None
    if not isinstance(terms, list) or not terms:
        raise Broken(f"{mp} names no terms, so no bill can be read")
    odd = [t for t in terms if not (isinstance(t, str) and TERM_FILE.fullmatch(t))]
    if odd:
        raise Broken(f"{mp} names {odd[:3]} among its terms, and a term is two years")
    rows = []
    for t in terms:
        f = idx / f"{t}.json"
        if not f.exists():
            raise Broken(f"{mp} names {t} and {f} is not there")
        try:
            part = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            raise Broken(f"{f} will not read: {e}") from None
        if not isinstance(part, list) or not part:
            raise Broken(f"{f} holds no bills")
        other = [r for r in part if not isinstance(r, dict) or r.get("term") != t]
        if other:
            o = other[0] if isinstance(other[0], dict) else {}
            raise Broken(f"{f} holds {len(other):,} row(s) that are not of {t}, the "
                         f"first {o.get('id')!r} of {o.get('term')!r}")
        rows.extend(part)
    stray = sorted(f.stem for f in idx.glob("*.json")
                   if TERM_FILE.fullmatch(f.stem) and f.stem not in terms)
    if stray:
        raise Broken(f"{idx} holds {', '.join(stray[:3])}, which {mp} does not name: "
                     "a term no page offers, or one an earlier build left behind")
    return rows


def bill_index_or_stop(site="site", who=""):
    """bill_index(), for a builder that cannot go on without every bill:
    the rows, or SystemExit saying what is missing and what to run. A builder
    that read an empty list here would write pages, counts and downloads of
    no bills and exit 0."""
    try:
        rows = bill_index(site)
    except Broken as e:
        raise SystemExit(f"{who or 'this step'}: the bill index is broken: {e}") from None
    if rows is None:
        raise SystemExit(f"{who or 'this step'}: no bill index in {site} (no meta.json). "
                         "Run build_site_v2.py first -- every bill comes from it.")
    return rows
