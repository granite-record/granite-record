#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.19
"""
Check the site is fit to publish before uploading it.

    python3 src/checks/check_site.py --site site --base https://graniterecord.org

Deployment is the point at which mistakes stop being private. A missing file or
a link to a page that was never generated is invisible on a local server, where
you only ever open the three pages you were testing, and obvious to the first
stranger who arrives from a search result.

This checks the things that are checkable without a browser: that every file
the pages reference exists, that the JSON parses and is not empty, that the
sitemap points only at files that are there, that no page still names a local
address, and that the data is not visibly stale.

Exit code is non-zero if anything would be broken for a visitor, so it can gate
an upload in a script.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone

# The logo and the icons, by name: the one list, kept where the build places
# them. They are not in the repository, so a site built from a bare clone has
# none of them, and every page's head still links four.
from build_pages import BRAND_FILES
import site_read

# A JSON file here whose emptiness is a fact about the record rather than a
# build that produced nothing. Every other empty one is a failure: silence is
# not success, and a builder that writes [] and exits zero is the failure mode
# this whole check exists for.
#
# former.json holds the legislators who appear in the record and hold no seat
# now. On the live site that is 1,785 people; on preflight's fixture, whose
# roster and vote file are a handful of rows, nobody has left and the correct
# answer is []. Flagging that made preflight fail on a site that was built
# perfectly.
MAY_BE_EMPTY = {"former.json"}

# Every page the navigation links to, plus the files every page loads. A tab
# that is in the nav and not in here is a tab that can go missing without the
# checker noticing -- which calendar.html did, between being added to both nav
# emitters and being added to this list.
REQUIRED = ["index.html", "bills.html", "officials.html", "resources.html",
            "about.html", "calendar.html", "style.css",
            "meta.json", "legislators.json", "home.json"]

# Cloudflare Pages refuses a deployment holding a file over 25 MiB. Nothing
# measured a file against that until 2 October, when index.json stood at
# 22.6 MiB and the only guard was build_exports' own, for its own CSVs.
# index.json is retired since (bill_index, below); this still measures the
# rest.
# Warned from nine tenths of it: a file grows a bill at a time, and the
# number to act on is the one before a deploy is refused.
FILE_CAP = 25 * 1024 * 1024
FILE_NEAR = 0.9

TERM_NAME = re.compile(r"\d{4}-\d{4}")


def near_the_cap(sizes, errors, warnings):
    """Each file of [(bytes, name)] against FILE_CAP: an error for one over
    it, a warning for one within a tenth of it."""
    for n, name in sorted(sizes, reverse=True):
        if n < FILE_NEAR * FILE_CAP:
            break
        said = (f"{name} is {n / 1048576:.1f} MiB against Cloudflare Pages' "
                f"{FILE_CAP // 1048576} MiB for one file")
        if n > FILE_CAP:
            errors.append(said + " - the deployment would be refused")
        else:
            warnings.append(said)


def bill_index(site, errors):
    """Every bill's row, as the pages read it: site/idx/<term>.json for each
    term site/meta.json names (site_read.bill_index). A term named with no
    file, an empty or unreadable one, a row in another term's file or a term
    file meta.json does not name is a site whose bills page would offer a
    different list from the one the rest of it describes, and is refused.

    AND NO index.json (retired 5 October 2026). It was the same rows joined
    into one file, which no page read: 23.7 MB on 2 October, nine tenths of
    what a file may be. The build deletes the last one; one still here is a
    site that would go on deploying a frozen list of every bill, and is
    refused too."""
    if (site / "index.json").exists():
        errors.append("index.json is in the site: it was retired, and a copy here "
                      "is a frozen list of every bill that would still deploy. "
                      "build_site_v2.py deletes it; run the build again")
    try:
        rows = site_read.bill_index(site)
    except site_read.Broken as e:
        errors.append(f"the bill index does not hold together: {e}")
        return
    if rows is None:
        return              # no meta.json: the required files say so
    terms = sorted({r["term"] for r in rows}, reverse=True)
    print(f"\nbill index: {len(rows):,} bills across {len(terms)} "
          f"term{'' if len(terms) == 1 else 's'}, {terms[-1]} to {terms[0]}, as "
          "meta.json names them")


def search_index(site, errors, warnings):
    """site/sidx, the bills' own words (build_search_index.py), against the
    indexes it was built from.

    A site without it still searches -- titles only -- and nothing on it says
    what is missing, so nothing else here would notice: on 2 October a build
    that had lost the texts of eighteen terms wrote eighteen empty files, and
    the only check that read them was one the nightly does not run. A term
    before the newest with text for fewer than half its bills is refused; the
    newest with none, or with more than 200 bills and text for fewer than half
    (a bill_text.json cut to 111 of 2,243 said nothing, the review of
    2 October 2026), is a warning, because in the first days of a session the
    bills are numbered before their text is fetched. A build told that no
    text was expected (--allow-no-text, which preflight's fixture is) says so
    in its manifest, and is warned of and not refused.
    """
    idx = site / "idx"
    terms = sorted(f.stem for f in idx.glob("*.json")) if idx.exists() else []
    if not terms:
        return
    sidx = site / "sidx"
    try:
        man = json.loads((sidx / "manifest.json").read_text(encoding="utf-8"))
        on = man["terms"]
    except (OSError, ValueError, KeyError, TypeError):
        errors.append("the search index is not in the site: no readable "
                      "sidx/manifest.json beside the bill indexes in idx/. "
                      "The search would read titles only and say nothing of "
                      "it - run build_search_index.py")
        return
    allowed = bool(man.get("no_text_expected"))
    real = [t for t in terms if TERM_NAME.fullmatch(t)]
    newest = max(real) if real else None
    bad, thin = [], []
    for t in terms:
        tally = on.get(t) if isinstance(on, dict) else None
        f = sidx / f"{t}.json"
        if not isinstance(tally, dict) or not f.exists():
            bad.append(f"{t} has no search index")
            continue
        if f.stat().st_size != tally.get("bytes"):
            bad.append(f"sidx/{t}.json is not the file the manifest describes")
            continue
        bills, text = tally.get("bills") or 0, tally.get("with_text") or 0
        if t not in real or not bills:
            continue
        if t != newest and text < 0.5 * bills:
            thin.append(f"{t} has text for {text:,} of its {bills:,} bills")
        elif t == newest and not text:
            warnings.append(f"the search index has no text for {t}, the "
                            f"newest term: its {bills:,} bills are found by "
                            "title and topic only")
        elif t == newest and bills > 200 and text < 0.5 * bills:
            warnings.append(f"the search index has text for {text:,} of the "
                            f"{bills:,} bills of {t}, the newest term: the "
                            "rest are found by title and topic only")
    if not (sidx / "words.json").exists():
        bad.append("sidx/words.json, every word the bills use, is not there: "
                   "a misspelt search would be offered nothing")
    print(f"\nsearch index: {len(terms)} terms, "
          f"{sum((on.get(t) or {}).get('with_text') or 0 for t in terms):,} "
          "bills with their text read"
          + (" (built with --allow-no-text)" if allowed else ""))
    for b in bad:
        errors.append("search index: " + b)
    if thin:
        said = ("search index: " + "; ".join(thin) + " - their texts were not "
                "read, and those bills would be found by title and topic only")
        (warnings if allowed else errors).append(said)


def redirect_rules(site):
    """The left-hand side of every rule in the site's _redirects, as path
    segments. Pages answers each one -- a tab's address with its record's page,
    /learn with the Resources hub it moved to -- so a link to one is not a
    broken link, though no file sits there. preflight's _links_resolve reads
    the file the same way. `:name` is one segment, `*` is the rest."""
    p = Path(site) / "_redirects"
    if not p.exists():
        return []
    return [[x for x in line.split()[0].strip("/").split("/") if x]
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def redirected(site, target, rules):
    """Does a rule of _redirects answer this file's address?"""
    try:
        segs = [x for x in target.relative_to(Path(site).resolve()).as_posix().split("/") if x]
    except ValueError:
        return False
    for rule in rules:
        if rule and rule[-1] == "*":
            if len(segs) >= len(rule) - 1 and all(r.startswith(":") or r == s
                                                  for r, s in zip(rule[:-1], segs)):
                return True
        elif len(rule) == len(segs) and all(r.startswith(":") or r == s for r, s in zip(rule, segs)):
            return True
    return False


def served(target):
    """Is this address one the host will answer?

    Cloudflare Pages serves /bill/2026/hb1442 from hb1442.html and redirects
    the .html form to it -- measured against the live site. So the canonical
    links, the skip links and all 34,158 sitemap entries now name the address
    WITHOUT the extension, and a checker that only looks for a file of that
    exact name calls every one of them broken. It did: 34,154 of them.

    A directory is served by its index.html for the same reason.
    """
    if target.exists():
        return True
    if target.is_dir():
        return (target / "index.html").exists()
    return target.with_suffix(target.suffix + ".html").exists() \
        or target.with_name(target.name + ".html").exists()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    errors, warnings = [], []

    if not site.exists():
        print(f"No such folder: {site}")
        sys.exit(1)

    print("=" * 62)
    print(f"Checking {site.resolve()}")
    print("=" * 62)

    # ---- files that must exist ---------------------------------------------
    for f in REQUIRED:
        if not (site / f).exists():
            errors.append(f"missing required file: {f}")
    print(f"\nrequired files: {len(REQUIRED) - sum(1 for f in REQUIRED if not (site/f).exists())}"
          f"/{len(REQUIRED)} present")

    # ---- JSON parses and is not empty ---------------------------------------
    counts = {}
    for f in site.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{f.name} is not valid JSON: {e}")
            continue
        n = len(d) if isinstance(d, (list, dict)) else 1
        counts[f.name] = n
        if n == 0 and f.name not in MAY_BE_EMPTY:
            errors.append(f"{f.name} is empty")
    for k, v in sorted(counts.items()):
        print(f"  {k:<22} {v:,} entries")

    # ---- the logo and the icons ---------------------------------------------
    # ONE PLAIN ERROR, NOT TEN BROKEN LINKS. Without this a site built from a
    # clone was refused with "broken link: index.html -> /icon.svg" and nine
    # more like it, none of which says the one thing a person needs to know:
    # the files were never in the repository. Still an error -- a site without
    # its icons must not be published -- but one that says why and what to do.
    # The links to them are counted here and left out of the list below.
    no_brand = [f for f in BRAND_FILES if not (site / f).exists()]
    brand_at = {(site / f).resolve() for f in no_brand}
    to_brand = 0
    print(f"\nlogo and icons: {len(BRAND_FILES) - len(no_brand)}/{len(BRAND_FILES)} present")

    # ---- every internal link resolves ---------------------------------------
    print("\nlinks:")
    bad = Counter()
    checked = 0
    pages = list(site.glob("*.html")) + list((site / "bill").rglob("*.html"))[:200]
    rules = redirect_rules(site)
    for p in pages:
        txt = p.read_text(encoding="utf-8", errors="replace")
        # Strip script blocks first. They contain template literals like
        # href="${esc(d.docket_url)}", which are code that builds a link at
        # runtime, not a link to a file on disk.
        txt = re.sub(r"<script\b.*?</script>", " ", txt, flags=re.S | re.I)
        # A <base href="/"> makes every relative link on the page resolve from
        # the site root instead of from the folder the page sits in. A bill's
        # page carries one, because it is bills.html -- written to sit at the
        # root -- served two folders down. Without honouring it this reported
        # six broken links on each of 4,230 pages that a browser resolves
        # perfectly well, and a checker that cries wolf gets switched off.
        mb = re.search(r'<base\s+href="([^"]*)"', txt, re.I)
        base = (mb.group(1) if mb else "") or ""
        for href in re.findall(r'(?:href|src)="([^"]+)"', txt):
            if href.startswith(("http", "mailto:", "#", "data:", "//")):
                continue
            if "${" in href or "{{" in href:
                continue
            clean = href.split("#")[0].split("?")[0]
            if not clean:
                continue
            # A leading slash means the site root, not the filesystem root.
            if clean.startswith("/"):
                target = (site / clean.lstrip("/")).resolve()
            elif base.startswith("/"):
                target = (site / base.lstrip("/") / clean).resolve()
            else:
                target = (p.parent / clean).resolve()
            checked += 1
            if not served(target) and not redirected(site, target, rules):
                if target in brand_at:
                    to_brand += 1
                    continue
                bad[f"{p.name} -> {href}"] += 1
    print(f"  {checked:,} internal references checked across {len(pages)} pages")
    for k, n in list(bad.items())[:10]:
        errors.append(f"broken link: {k}")
    if not bad:
        print("  all resolve" + (f", bar {to_brand:,} to the logo and icons that "
                                 "are not here" if to_brand else ""))
    if no_brand:
        errors.append(
            f"the logo and icons are not in the site: {len(no_brand)} of "
            f"{len(BRAND_FILES)} files are missing ({', '.join(no_brand)})"
            + (f", and {to_brand:,} links on the pages checked point at them"
               if to_brand else "")
            + ". They are not in the repository (DATA.md says why): the "
            "project's own build takes them from its kit, and a fork brings "
            "its own -- a mark in brand/ and python3 src/pages/build_brand.py, or files "
            "of those names in assets/ -- and then builds again")

    # ---- the bill index, and the search index beside it --------------------
    bill_index(site, errors)
    search_index(site, errors, warnings)

    # ---- per-bill pages and feeds -------------------------------------------
    nbill = len(list((site / "bill").rglob("*.html"))) if (site / "bill").exists() else 0
    nfeed = len(list((site / "feed").rglob("*.xml"))) if (site / "feed").exists() else 0
    njson = (len(list((site / "bills").glob("*/*.json")))
             + len(list((site / "bills").glob("*.json")))
             if (site / "bills").exists() else 0)
    print(f"\nbill pages: {nbill:,} html, {njson:,} json, {nfeed:,} feeds")
    if njson and nbill < njson * 0.95:
        warnings.append(f"only {nbill:,} static pages for {njson:,} bills - "
                        "run build_bill_pages.py")
    if not nfeed:
        warnings.append("no RSS feeds - run build_feeds.py")

    # ---- sitemap points only at files that exist ----------------------------
    sm = site / "sitemap.xml"
    if sm.exists():
        locs = re.findall(r"<loc>([^<]+)</loc>", sm.read_text(encoding="utf-8"))
        # THE BASE AND ITS SLASH, together. This used to take the base off
        # and then lstrip("/") whatever was left, so
        # "https://graniterecord.orgsession/H/2026-05-21" became a path that
        # exists and passed -- 1,669 of them, on the live sitemap, until 24
        # September. An address with no slash after the domain is one no
        # browser will open, so it is counted here and not resolved.
        root = a.base.rstrip("/") + "/"
        missing = 0
        for u in locs:
            rel = u[len(root):] if u.startswith(root) else None
            if rel and not served(site / rel):
                missing += 1
        print(f"\nsitemap: {len(locs):,} URLs, {missing:,} pointing at files "
              "that are not here")
        if missing:
            errors.append(f"{missing} sitemap URLs have no file")
        noslash = [u for u in locs if u.startswith(root[:-1]) and not u.startswith(root)]
        if noslash:
            errors.append(f"{len(noslash)} sitemap URLs have no slash after "
                          f"{root[:-1]}, e.g. {noslash[0]} - a builder passed "
                          "shell.page a path without its leading /")
        wrong_base = [u for u in locs if not u.startswith(root[:-1])]
        if wrong_base:
            errors.append(f"{len(wrong_base)} sitemap URLs use a different base "
                          f"than {a.base} - rerun python3 src/pages/build_bill_pages.py --base")
    else:
        warnings.append("no sitemap.xml - search engines will find less")

    # ---- nothing still points at a local server -----------------------------
    leaked = []
    for p in list(site.glob("*.html"))[:20] + list((site / "feed").glob("*.xml"))[:5]:
        t = p.read_text(encoding="utf-8", errors="replace")
        if "localhost" in t or "127.0.0.1" in t:
            leaked.append(p.name)
    if leaked:
        errors.append(f"local addresses left in: {', '.join(leaked)}")
    else:
        print("\nno localhost references")

    # ---- freshness ----------------------------------------------------------
    bj = site / "build.json"
    if bj.exists():
        b = json.loads(bj.read_text(encoding="utf-8"))
        fin = b.get("finished", "")
        try:
            age = (datetime.now() - datetime.fromisoformat(fin)).days
            print(f"\nlast build: {fin} ({age} days ago)")
            if age > 2:
                warnings.append(f"data is {age} days old - rebuild before publishing")
        except ValueError:
            pass
        failed = [s["step"] for s in b.get("steps", []) if s["status"] == "failed"]
        if failed:
            errors.append(f"last build had failures: {', '.join(failed)}")
        skipped = [s["step"] for s in b.get("steps", []) if s["status"] == "skipped"]
        if skipped:
            warnings.append(f"last build skipped: {', '.join(skipped[:4])}")
    else:
        warnings.append("no build.json - the site cannot show how fresh it is")

    # ---- size ---------------------------------------------------------------
    sizes = [(f.stat().st_size, f.relative_to(site).as_posix())
             for f in site.rglob("*") if f.is_file()]
    total = sum(n for n, _f in sizes)
    nfiles = len(sizes)
    print(f"\nsize: {total/1e6:.1f} MB across {nfiles:,} files")
    # One file against the host's cap on a file (FILE_CAP, above).
    if sizes:
        big, name = max(sizes)
        print(f"  largest file: {name}, {big / 1048576:.1f} MiB of the "
              f"{FILE_CAP // 1048576} a file may be")
    near_the_cap(sizes, errors, warnings)
    # Cloudflare Pages allows 20,000 files on the free plan and 100,000 on
    # Pro, which this project moved to on 8 September. Warned at 90% rather
    # than at the cap: the number to act on is the one before a deploy is
    # refused, and every bill costs three files, so 10,000 is about three
    # more terms of warning.
    if nfiles > 90000:
        warnings.append(f"{nfiles:,} files against Cloudflare Pages' 100,000 "
                        "on the Pro plan")

    # ---- files the last build did not write ---------------------------------
    # site/ is written, never emptied, so a page the build has stopped
    # emitting stays on disk and ships. Four were found this way on 18
    # September: a "Committee of Conference" page for a code the committee
    # build now skips, and two legislators under districts a correction had
    # already moved them out of -- Steve Shurtleff under Grafton 9 and Wendy
    # Chase under Belknap 5, each sitting beside the corrected page. Nothing
    # linked to them and they were not in the sitemap, but a direct address
    # still answered, with the wrong district in the title.
    #
    # The five directories below are written whole by the build, so a file in
    # one of them older than the build that just ran is one the build no
    # longer writes. The site root is deliberately NOT checked: icons, the og
    # images, _headers and _redirects are copied once and keep their date.
    # Only checked after a build that finished every step -- a build stopped
    # halfway legitimately leaves the rest of the site where it was.
    if bj.exists():
        b = json.loads(bj.read_text(encoding="utf-8"))
        if b.get("ok") and b.get("finished") and b.get("seconds"):
            began = (datetime.fromisoformat(b["finished"]).timestamp()
                     - float(b["seconds"]))
            stale = []
            for d in ("bill", "legislator", "committee", "town", "feed"):
                for f in (site / d).rglob("*"):
                    if f.is_file() and f.stat().st_mtime < began:
                        stale.append(f.relative_to(site).as_posix())
            if stale:
                stale.sort()
                errors.append(
                    f"{len(stale)} file(s) the last build did not write, which "
                    f"would still deploy: {', '.join(stale[:6])}"
                    + (" ..." if len(stale) > 6 else ""))

    # ---- verdict ------------------------------------------------------------
    print("\n" + "=" * 62)
    if errors:
        print(f"{len(errors)} PROBLEM(S) - do not publish yet")
        for e in errors[:15]:
            print(f"  x {e}")
    if warnings:
        print(f"\n{len(warnings)} warning(s)")
        for w in warnings:
            print(f"  ! {w}")
    if not errors and not warnings:
        print("Ready to publish.")
    elif not errors:
        print("\nNo blocking problems. The warnings are worth reading first.")
    print("=" * 62)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
