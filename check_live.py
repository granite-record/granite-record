#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.12
"""
What is the live site actually serving?

    python3 check_live.py
    python3 check_live.py --base https://graniterecord.org --site site

Fetches a handful of URLs from the published site and compares each against the
file that was supposed to produce it. Reads nothing from the General Court.

WHY THIS EXISTS

check_site.py verifies the folder before it is deployed: the links resolve, the
files are there, the sitemap points at things that exist. It has been right
every time. What it cannot see is the deploy itself -- whether what left this
machine is what the world is now getting.

Three times now the answer has been no, in three different ways:

  a stale copy in the browser        the page loads, and it is yesterday's
  the file never reached the deploy  the page loads, and it is yesterday's
  every path returning index.html    the stylesheet arrives as HTML, so the
                                     site loses its formatting and every link
                                     appears to go nowhere

The third is the one that looks most like a catastrophe and is usually a
configuration line. It is diagnosed by asking for the stylesheet and reading
what comes back: CSS, or a web page wearing its name.

WHAT IT CHECKS

  /                     served, and is HTML
  /bills                served, HTML, and carries the GRANITE_VERSION that
                        site/bills.html carries
  /style.css            served as CSS and not as HTML
  /index.json           served as JSON, and parses, and has bills in it
  /legislators          served, and is a different page from /
  /feed/all.xml         served as XML

The last one matters more than it looks: if / and /bills return the same bytes,
every path is falling through to the home page, which is the failure that
removes the formatting too.
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "granite-record-selfcheck/1.0", "Cache-Control": "no-cache",
      "Pragma": "no-cache"}


TIMES = []


def get(url, limit=400_000):
    """Read up to limit bytes, and say whether that was all of them.

    index.json is over 400 KB, so the first version of this cut it in half and
    then reported that it would not parse -- a checker written to reduce
    confusion, inventing some. A body that stops exactly on the limit is a
    truncation, and the only honest thing to say about it is that it was not
    read to the end.
    """
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read(limit)
            TIMES.append((url, time.time() - t0, len(body)))
            return r.status, r.headers.get("Content-Type", ""), body, None
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read(4096), None
    except Exception as e:
        return None, "", b"", e


# Things that rewrite a page between the origin and the reader. Each is a
# switch in the Cloudflare dashboard, and each explains bytes that differ while
# the length does not.
CF_SIGNS = [
    (b"/cdn-cgi/l/email-protection", "Email Address Obfuscation",
     "every mailto is replaced with a hex string that is SALTED PER REQUEST, "
     "so the page differs every time and the length never changes. It also "
     "means an address only appears if a Cloudflare script runs."),
    (b"rocket-loader", "Rocket Loader",
     "script tags are rewritten and deferred. When it works nobody notices; "
     "when it does not, the page loads and nothing runs -- no charts, no "
     "tabs, no search."),
    (b"/cdn-cgi/scripts/", "a Cloudflare script injection", ""),
    (b"static.cloudflareinsights.com", "Web Analytics",
     "a beacon script is appended to every page and reports each visit back "
     "to Cloudflare. It is cookieless and it counts page views, which is "
     "what /about now says this site collects -- so this one is on "
     "purpose. It is listed because it still arrives by injection rather "
     "than from the build: the page a reader gets is not the page that "
     "was checked."),
    (b"cloudflareinsights", "Web Analytics", ""),
    (b"cf-web-analytics", "Web Analytics beacon",
     "a script is appended to every page."),
    (b"/cdn-cgi/apps/", "a Cloudflare app injection", ""),
]

# SETTINGS THE PERSON HAS CHOSEN. Email Address Obfuscation is on because
# the contact address on every page should reach a person and not a scraper,
# and its own decoder script (/cdn-cgi/scripts/<hash>/cloudflare-static/
# email-decode.min.js) is the "script injection" that came with it -- one
# switch, not two. They are still reported, because a rewritten page is
# worth knowing about, but they are not counted as problems.
ACCEPTED = {"Email Address Obfuscation", "a Cloudflare script injection"}


def first_difference(served, local):
    """Where the served bytes stop matching the file that produced them."""
    n = min(len(served), len(local))
    i = 0
    while i < n and served[i] == local[i]:
        i += 1
    if i == n and len(served) == len(local):
        return None
    a = max(0, i - 60)
    return (i, local[a:i + 90].decode("utf-8", "replace"),
            served[a:i + 90].decode("utf-8", "replace"))


def stamp(b):
    i = b.find(b"GRANITE_VERSION:")
    if i < 0:
        return ""
    return b[i + 16: i + 34].decode("ascii", "replace").strip(" -->\r\n\t")


def _flat(s):
    return " ".join(s.split())[:100]


def _wrap(s, w):
    out, line = [], ""
    for word in s.split():
        if len(line) + len(word) + 1 > w:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    return out + ([line] if line else [])


def one_bill(base, site, bid, year, tries=3):
    """Is this bill's page the same every time, and the same as the local one?

    Content that changes between refreshes cannot be a data problem: the file
    on disk does not change while you press F5. Either the deploy is still
    propagating, or something between here and the reader is serving different
    bytes at different moments -- a stale edge, a cache, a captive portal.

    A bill genuinely missing its status is the opposite: identical every time,
    identical to the local copy, and wrong in both. That is a build to redo,
    not a deploy.

    So each URL is asked for three times and the answers compared with each
    other, then with the file that produced them.
    """
    bid = bid.upper().replace(" ", "")
    # Both carry the filing year, because a bill number is unique within a
    # term and not beyond it.
    paths = [f"/bill/{year}/{bid.lower()}.html", f"/bills/{year}/{bid}.json"]
    locals_ = [Path(site) / "bill" / year / f"{bid.lower()}.html",
               Path(site) / "bills" / year / f"{bid}.json"]
    print(f"\n{bid}: asking {tries} times for each\n")
    steady = True
    global rewritten
    rewritten = False
    for path, lf in zip(paths, locals_):
        sizes, digests = [], []
        for _ in range(tries):
            st, ct, body, err = get(base + path, 12_000_000)
            if err:
                sizes.append(f"{type(err).__name__}")
                digests.append("err")
                continue
            sizes.append(f"{st}/{len(body):,}")
            digests.append(hashlib.sha256(body).hexdigest()[:8])
        same = len(set(digests)) == 1
        steady &= same
        print(f"  {path}")
        print(f"    {'  '.join(sizes)}   " +
              ("identical each time" if same else "*** DIFFERENT BETWEEN "
                                                  "REQUESTS ***"))
        if lf.exists():
            lb = lf.read_bytes()
            match = hashlib.sha256(lb).hexdigest()[:8] in digests
            print(f"    local {len(lb):,} bytes, "
                  + ("same as what is served" if match
                     else "*** NOT what is served ***"))
            if not match and body:
                # By feature, not by marker. Web Analytics is recognised by
                # two different strings and was being announced twice.
                named = set()
                for sign, name, why in CF_SIGNS:
                    if sign in body and sign not in lb and name not in named:
                        named.add(name)
                        print(f"    Cloudflare is applying {name}.")
                        if why:
                            for ln in _wrap(why, 66):
                                print(f"      {ln}")
                        rewritten = True
                d = first_difference(body, lb)
                if d:
                    i, was, now = d
                    print(f"    they part company at byte {i:,}:")
                    print(f"      built  ...{_flat(was)}")
                    print(f"      served ...{_flat(now)}")
        else:
            print(f"    local {lf} does not exist")

    # What the bill's own record actually contains, locally.
    lf = locals_[1]
    if lf.exists():
        try:
            d = json.loads(lf.read_text(encoding="utf-8"))
            bits = [("status", d.get("status") or d.get("next_step")),
                    ("rollcalls", d.get("rollcalls")),
                    ("reports", d.get("reports")),
                    ("events", (d.get("events") or [])),
                    ("sponsors", d.get("sponsors")),
                    ("documents", d.get("documents"))]
            print("\n  what the local record holds:")
            for k, v in bits:
                have = (f"{len(v):,}" if isinstance(v, list)
                        else ("yes" if v else "no"))
                print(f"    {k:<12}{have}"
                      + ("   <- empty" if not v else ""))
        except Exception as e:
            print(f"  local record will not parse: {e}")
    return steady


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true",
                    help="exit non-zero only if the deploy did not land")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--site", default="site")
    ap.add_argument("--bill", help="one bill, e.g. HB396")
    ap.add_argument("--year", default="2026")
    a = ap.parse_args()
    base = a.base.rstrip("/")
    site = Path(a.site)

    if a.bill:
        steady = one_bill(base, a.site, a.bill, a.year)
        print()
        if steady:
            print("The same bytes every time. If the page is wrong, it is "
                  "wrong in the\nbuild -- rebuild and publish. If it looks "
                  "right here and wrong on a\nphone, the phone is holding an "
                  "old copy.")
        elif rewritten:
            print("DIFFERENT BYTES BETWEEN REQUESTS, and the reason is named "
                  "above: what\nthe reader gets is not what was built. "
                  "Cloudflare is rewriting the page\nin flight, which is why "
                  "it varies between refreshes and why parts of it\ndepend on "
                  "a Cloudflare script having loaded.\n\n"
                  "These are switches under Speed and under Scrape Shield in "
                  "the dashboard.\nA site of static files that has already "
                  "been built does not need any of\nthem, and each one is a "
                  "way for a page to arrive incomplete.")
        else:
            print("DIFFERENT BYTES BETWEEN REQUESTS. Nothing on this machine "
                  "can cause\nthat: the files do not change while you refresh. "
                  "Either a deploy is\nstill propagating -- wait a few minutes "
                  "and run this again -- or an\nedge is serving two versions "
                  "at once, which the Deployments tab in\nCloudflare will "
                  "show as two recent deploys.")
        return 0 if steady else 1

    print(f"asking {base} what it is serving\n")
    print(f"  {'path':<16}{'status':<8}{'type':<26}what came back")
    print("  " + "-" * 74)

    seen, problems = {}, []

    def row(path, want_type, note=""):
        # JSON has to arrive whole to be judged; HTML and CSS do not.
        limit = 12_000_000 if want_type == "json" else 400_000
        st, ct, body, err = get(base + path, limit)
        seen[path] = (st, ct, body)
        if err:
            print(f"  {path:<16}{'-':<8}{'-':<26}{type(err).__name__}: {err}")
            problems.append(f"{path} could not be fetched")
            return
        short = (ct.split(";")[0] or "?")[:24]
        looks_html = body[:400].lstrip()[:1].lower() == b"<" or b"<!doctype" in body[:200].lower()
        desc = f"{len(body):,} bytes"
        if want_type == "css" and (looks_html or "html" in ct):
            desc += " -- HTML, not CSS"
            problems.append(f"{path} is being served as a web page")
        elif want_type == "json":
            if len(body) >= limit:
                desc += " -- larger than this reads; not checked"
            else:
                try:
                    v = json.loads(body.decode("utf-8"))
                    desc += f", parses, {len(v):,} entries"
                    if not len(v):
                        problems.append(f"{path} is empty")
                except Exception:
                    desc += " -- not JSON"
                    problems.append(f"{path} is not JSON")
        elif want_type == "xml" and b"<rss" not in body[:600] and b"<?xml" not in body[:200]:
            desc += " -- not XML"
            problems.append(f"{path} is not XML")
        if st != 200:
            problems.append(f"{path} returned HTTP {st}")
        print(f"  {path:<16}{st or '-':<8}{short:<26}{desc}{note}")

    row("/", "html")
    row("/bills", "html")
    row("/style.css", "css")
    row("/index.json", "json")
    row("/legislators", "html")
    row("/feed/all.xml", "xml")

    # Everything falling through to the home page is the failure that also
    # takes the formatting with it, and it is invisible one URL at a time.
    def h(p):
        b = seen.get(p, (None, "", b""))[2]
        return hashlib.sha256(b).hexdigest() if b else ""
    if h("/") and h("/") == h("/bills") == h("/legislators"):
        problems.append("every path returns the same page -- the site is "
                        "falling through to index.html")

    print()
    # The search page is the one with the scripts, so it is the one Rocket
    # Loader would rewrite -- and a bill page could never show that, because a
    # bill page has no scripts to rewrite. Comparing it against the file that
    # produced it is the only way to see what the reader is actually being
    # handed.
    body = seen.get("/bills", (None, "", b""))[2]
    lf = site / "bills.html"
    if body and lf.exists():
        lb = lf.read_bytes()
        if hashlib.sha256(body).hexdigest() != hashlib.sha256(lb).hexdigest():
            print(f"  /bills is not the file that built it: served "
                  f"{len(body):,} bytes, built {len(lb):,}")
            named = set()
            for sign, name, why in CF_SIGNS:
                if sign in body and sign not in lb and name not in named:
                    named.add(name)
                    print(f"    Cloudflare is applying {name}.")
                    for ln in _wrap(why, 66):
                        print(f"      {ln}")
                    if name not in ACCEPTED:
                        problems.append(
                            f"Cloudflare is applying {name} to /bills")
            d = first_difference(body, lb)
            if d:
                i, was, now = d
                print(f"    they part company at byte {i:,}:")
                print(f"      built  ...{_flat(was)}")
                print(f"      served ...{_flat(now)}")
        else:
            print("  /bills is byte-for-byte the file that built it")
        print()

    live = stamp(seen.get("/bills", (None, "", b""))[2])
    local = ""
    f = site / "bills.html"
    if f.exists():
        local = stamp(f.read_bytes())
    if live or local:
        agree = live and local and live == local
        print(f"  bills page version   live {live or '(none found)'}"
              f"   local {local or '(none found)'}   "
              f"{'match' if agree else 'DIFFERENT'}")
        if local and live and not agree:
            problems.append("the live bills page is not the file in "
                            f"{site}/ -- deploy again")

    # How long it took, because "the site is slow" and "this connection is
    # slow" feel identical and are fixed differently. A static file from a CDN
    # is a few hundred milliseconds from anywhere; seconds means something
    # between here and there, not the site.
    if TIMES:
        secs = sorted(x[1] for x in TIMES)
        mid = secs[len(secs) // 2]
        total = sum(x[2] for x in TIMES)
        print(f"  response time: median {mid * 1000:,.0f} ms, "
              f"slowest {secs[-1] * 1000:,.0f} ms, {total / 1024:,.0f} KB in all")
        if mid > 1.5:
            print("\n  That is slow for static files on a CDN. The site is not\n"
                  "  doing the work -- it is a folder of files. Try again with\n"
                  "  the VPN off: graniterecord.org has never been blocked, so\n"
                  "  it does not need one, and a busy tunnel slows everything\n"
                  "  sharing it.")
        elif mid > 0.6:
            print("  Slower than usual but not alarming.")
    print()
    if not problems:
        print("The site is serving what was built.")
        return 0
    print("Problems:")
    for x in problems:
        print(f"  - {x}")
    blob = " ".join(problems)
    tips = []
    if "same page" in blob:
        tips.append(("every path the same",
                     "a catch-all or SPA rule is rewriting requests; look for "
                     f"a _redirects file in {site}/ and in the Cloudflare "
                     "settings"))
    if "not the file" in blob or "deploy again" in blob:
        tips.append(("versions differ",
                     "the deploy did not include the file; run publish again"))
    if "HTTP 4" in blob or "HTTP 5" in blob:
        tips.append(("a path failed", "it was never built; run build_all.py"))
    if "Cloudflare is applying" in blob:
        tips.append(("Cloudflare is rewriting pages",
                     "these are dashboard switches, under Speed and under "
                     "Scrape Shield. A site of files already built needs none "
                     "of them, and each is a way for a page to arrive "
                     "incomplete."))
    for head, body_ in tips:
        print(f"\n  {head}")
        for ln in _wrap(body_, 66):
            print(f"    {ln}")

    # Two kinds of problem, and publish.bat cares about only one of them.
    #
    # A deploy that did not land is a publish failure: the version served is
    # not the version built, a path 404s, or every path returns the same
    # page. Twice on 6 September publish printed "Deployment complete" for a
    # deployment the production domain never took, and nothing said so.
    #
    # Cloudflare rewriting pages is real and worth fixing, but it is a
    # standing dashboard setting rather than something this run did. Failing
    # every publish on it would make the guard noise, and a guard that always
    # fires is a guard nobody reads.
    landed = not any(("not the file" in x) or ("could not be fetched" in x)
                     or ("returned HTTP" in x) or ("same page" in x)
                     or ("served as a web page" in x)
                     for x in problems)
    if a.gate:
        if landed:
            print()
            print("  The deploy landed. The problems above are dashboard "
                  "settings, not this publish.")
            return 0
        print()
        print("  THE DEPLOY DID NOT LAND. What is live is not what was built.")
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
