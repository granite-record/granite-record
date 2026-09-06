#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.1
"""
Check the site is fit to publish before uploading it.

    python3 check_site.py --site site --base https://graniterecord.org

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

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = ["index.html", "bills.html", "legislators.html", "learn.html",
            "about.html", "style.css", "index.json", "meta.json",
            "legislators.json", "home.json"]


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
        if n == 0:
            errors.append(f"{f.name} is empty")
    for k, v in sorted(counts.items()):
        print(f"  {k:<22} {v:,} entries")

    # ---- every internal link resolves ---------------------------------------
    print("\nlinks:")
    bad = Counter()
    checked = 0
    pages = list(site.glob("*.html")) + list((site / "bill").rglob("*.html"))[:200]
    for p in pages:
        txt = p.read_text(encoding="utf-8", errors="replace")
        # Strip script blocks first. They contain template literals like
        # href="${esc(d.docket_url)}", which are code that builds a link at
        # runtime, not a link to a file on disk.
        txt = re.sub(r"<script\b.*?</script>", " ", txt, flags=re.S | re.I)
        for href in re.findall(r'(?:href|src)="([^"]+)"', txt):
            if href.startswith(("http", "mailto:", "#", "data:", "//")):
                continue
            if "${" in href or "{{" in href:
                continue
            clean = href.split("#")[0].split("?")[0]
            if not clean:
                continue
            # A leading slash means the site root, not the filesystem root.
            target = ((site / clean.lstrip("/")) if clean.startswith("/")
                      else (p.parent / clean)).resolve()
            checked += 1
            if not target.exists():
                bad[f"{p.name} -> {href}"] += 1
    print(f"  {checked:,} internal references checked across {len(pages)} pages")
    for k, n in list(bad.items())[:10]:
        errors.append(f"broken link: {k}")
    if not bad:
        print("  all resolve")

    # ---- per-bill pages and feeds -------------------------------------------
    nbill = len(list((site / "bill").rglob("*.html"))) if (site / "bill").exists() else 0
    nfeed = len(list((site / "feed").rglob("*.xml"))) if (site / "feed").exists() else 0
    njson = len(list((site / "bills").glob("*.json"))) if (site / "bills").exists() else 0
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
        missing = 0
        for u in locs:
            rel = u.replace(a.base.rstrip("/"), "").lstrip("/")
            if rel and not (site / rel).exists():
                missing += 1
        print(f"\nsitemap: {len(locs):,} URLs, {missing:,} pointing at files "
              "that are not here")
        if missing:
            errors.append(f"{missing} sitemap URLs have no file")
        wrong_base = [u for u in locs if not u.startswith(a.base.rstrip("/"))]
        if wrong_base:
            errors.append(f"{len(wrong_base)} sitemap URLs use a different base "
                          f"than {a.base} - rerun build_bill_pages.py --base")
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
    total = sum(f.stat().st_size for f in site.rglob("*") if f.is_file())
    nfiles = sum(1 for f in site.rglob("*") if f.is_file())
    print(f"\nsize: {total/1e6:.1f} MB across {nfiles:,} files")
    if nfiles > 20000:
        warnings.append(f"{nfiles:,} files - check your host's file-count limit")

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
