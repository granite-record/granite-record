#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.7
"""
Do the civics pages' source links actually go anywhere?

    python3 src/fetch/gc_web/check_civics_links.py --list     # print them, ask nothing
    python3 src/fetch/gc_web/check_civics_links.py            # one HEAD each, slowly

MAKES REQUESTS. Not many -- there are fewer than twenty distinct addresses --
but they go to gc.nh.gov and nh.gov, and gc.nh.gov has refused this project
twice. So it is a separate script that has to be asked for, it is one request
at a time with a long gap, and it stops at the second refusal -- and at the
General Court's first, or its second dropped connection, which it records
(refusal.note) so that every fetch of theirs stops too.

And it asks refusal.check() before its first request, as every script that
asks gc.nh.gov does: a standing refusal stops it (exit 2), and on a
stood-down laptop so do GitHub's night window, the half hour before it, and
a bucket refusal record not read since the last one (exit 4). Its addresses
come from civics.py rather than being written here, which is why preflight's
reader of fetchers used to miss it. --list asks nobody and is never stopped.

WHY IT EXISTS SEPARATELY FROM preflight

preflight runs on every change and must not touch the network. It checks that
a source link is well formed and on a state domain, which catches a typo and
nothing else. Whether the page is still at that address is a different
question and only the network can answer it.

That distinction matters more here than anywhere else on the site. These pages
end with "where this comes from", and the whole point of that block is that a
reader who wants to check is one click from the authority. A link that 404s
does not merely fail -- it makes the page look like it was written from
memory, which is the one impression this section cannot afford.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

import civics
import refusal

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}


def links():
    seen, out = set(), []
    for t in civics.TOPICS:
        for label, url in t["sources"]:
            if url in seen:
                continue
            seen.add(url)
            out.append((label, url, t["slug"]))
    return out


def ask(url, timeout=30):
    """(status, what went wrong, refusal.classify's reading of a failure, how
    many dropped connections the asking met).

    A HEAD that fails is asked again as a GET, as it always was -- and a HEAD
    that DROPPED is a dropped connection all the same, counted with the GET's
    (7 October 2026: a HEAD and a GET to gc.nh.gov that both dropped were
    counted as one, so the General Court's second dropped connection was met
    and the next link asked for twice more before anything was recorded). A
    GET's answer is read far enough to see the firewall's block page served
    as a 200, which is a refusal; a HEAD's answer has no page to read."""
    met = 0
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, head = r.status, (b"" if method == "HEAD" else r.read(4000))
        except urllib.error.HTTPError as e:
            # Some ASP.NET handlers refuse HEAD and answer a GET fine.
            if method == "HEAD" and e.code in (405, 501):
                continue
            return e.code, "", refusal.classify(e), met
        except Exception as e:                              # noqa: BLE001
            kind = refusal.classify(e)
            met += kind == "dropped"
            if method == "HEAD":
                continue
            return None, f"{type(e).__name__}: {e}"[:120], kind, met
        if refusal.classify(body=head.decode("utf-8", "replace")) == "refused":
            return None, "the firewall's block page, with a 200", "refused", met
        return status, "", None, met
    return None, "no answer", None, met


def general_court(url):
    """Is this the General Court's web server, whose refusal is recorded?"""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return host == "gc.nh.gov" or host.endswith(".gc.nh.gov")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--delay", type=float, default=10.0)
    a = ap.parse_args()

    ls = links()
    print(f"{len(ls)} distinct source addresses across "
          f"{len(civics.TOPICS)} pages")
    if a.list:
        for label, url, slug in ls:
            print(f"  {slug:24} {url}")
        print("\n  Nothing was asked for.")
        return 0

    refusal.check("The civics link check")

    codes, bad, refused, drops = Counter(), [], 0, 0
    for i, (label, url, slug) in enumerate(ls, 1):
        code, err, kind, met = ask(url)
        codes[code] += 1
        mark = "ok " if code and 200 <= code < 400 else "BAD"
        print(f"  [{i}/{len(ls)}] {mark} {code or err}  {url}", flush=True)
        # THE GENERAL COURT'S REFUSAL IS RECORDED (7 October 2026): one, or a
        # second dropped connection -- a HEAD's counts as much as a GET's, and
        # one met on a link that answered in the end still counts -- as every
        # fetcher reads them (refusal.classify), so every General Court fetch
        # stops for 24 hours and not only this check. Only gc.nh.gov's: a 403
        # from nh.gov is that server's, and stops nothing of the General Court's.
        if general_court(url):
            drops += met
            if kind == "refused" or drops >= 2:
                refusal.note("check_civics_links", f"{code or err} on {url}")
                print("\nREFUSED by the General Court. Stopping, and refusal.py now "
                      "holds one for 24 hours;\npython3 netcheck.py says what kind "
                      "it is without making it worse.")
                return 2
        if not (code and 200 <= code < 400):
            bad.append((slug, label, url, code or err))
            if code is None or code in (403, 429):
                refused += 1
                if refused >= 2:
                    print("\nTwo refusals. Stopping rather than pushing at a "
                          "server that is saying no.")
                    break
        if i < len(ls):
            time.sleep(a.delay)

    print(f"\n{sum(n for c, n in codes.items() if c and 200 <= c < 400)} of "
          f"{len(ls)} answered")
    for slug, label, url, why in bad:
        print(f"  {slug}: {label}\n      {url}\n      {why}")
    if bad:
        print("\nA source link that does not answer makes the page look "
              "written from memory,\nwhich is the one impression this section "
              "cannot afford. Fix it in civics.py.")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
