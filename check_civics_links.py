#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.2
"""
Do the civics pages' source links actually go anywhere?

    python3 check_civics_links.py --list     # print them, ask nothing
    python3 check_civics_links.py            # one HEAD each, slowly

MAKES REQUESTS. Not many -- there are fewer than twenty distinct addresses --
but they go to gc.nh.gov and nh.gov, and gc.nh.gov has refused this project
twice. So it is a separate script that has to be asked for, it is one request
at a time with a long gap, and it stops at the second refusal.

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

import argparse
import time
import urllib.error
import urllib.request
from collections import Counter

import civics

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
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, ""
        except urllib.error.HTTPError as e:
            # Some ASP.NET handlers refuse HEAD and answer a GET fine.
            if method == "HEAD" and e.code in (405, 501):
                continue
            return e.code, ""
        except Exception as e:                              # noqa: BLE001
            if method == "HEAD":
                continue
            return None, f"{type(e).__name__}: {e}"[:120]
    return None, "no answer"


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

    codes, bad, refused = Counter(), [], 0
    for i, (label, url, slug) in enumerate(ls, 1):
        code, err = ask(url)
        codes[code] += 1
        mark = "ok " if code and 200 <= code < 400 else "BAD"
        print(f"  [{i}/{len(ls)}] {mark} {code or err}  {url}", flush=True)
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
