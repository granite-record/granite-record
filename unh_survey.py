#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.2
"""
Find out what the UNH scans of the pre-digital General Court actually are.

    python3 unh_survey.py --recon           # robots, sitemap, the series page
    python3 unh_survey.py --get <url>       # one page, cached, paced
    python3 unh_survey.py --head <url>      # size and type only, no body
    python3 unh_survey.py --show <url>      # print what is cached, no network
    python3 unh_survey.py --log             # every request this project made

WHAT THIS IS FOR

scholars.unh.edu/senate_house holds the University of New Hampshire library's
scans of the New Hampshire House and Senate Journals. If they go back far
enough and are legible enough they close the largest hole in this record:
roll calls before 1999, sponsors before 1997, and floor amendments of that
era, none of which exist here in any form.

Nothing is modelled from the landing page. This script exists so that what
gets written down about the collection came from the collection.

THIS IS NOT gc.nh.gov, AND THAT CUTS BOTH WAYS

refusal.py holds every fetcher that asks the General Court, because that
address has blocked this project twice. It does not hold this one, and
deliberately: a UNH refusal should not stop the General Court lane that runs
continuously beside this, and a General Court refusal should not stop a
library that has said nothing to us. So the care has to be in here instead:

  * An honest User-Agent naming the project and an address to complain to.
  * robots.txt parsed and asked before every request, not read once and
    remembered. scholars.unh.edu disallows /do/, which is where a Digital
    Commons repository keeps OAI-PMH -- the machine route this went looking
    for. --recon had it in the list until robots.txt said no.
  * One request at a time, seconds apart, never in parallel.
  * Every response cached under archive/unh/raw/ and never asked for twice.
    Cached BEFORE it is judged, so that a block page is on disk to be read
    rather than something a second request has to go and ask about.
  * A refusal -- 403, a block page, a rate limit -- stops the run and is
    written to archive/unh/refused.<host>.json, which the next run reads and
    obeys for 24 hours. One file per host, because a refusal is a fact about
    an address: see mark_for().
  * No bulk retrieval without a person saying yes first. --recon is three
    requests; anything that walks a list is a separate script, not this one.

IT SERVES MORE THAN ONE HOST

Only because the UNH record says these volumes were "Scanned by Internet
Archive, Open Content Alliance (2008)", which puts the same books on a host
built for programmatic access. Everything above applies per host rather than
to scholars.unh.edu alone, so that the second host gets the same care as the
first without a second copy of the rules to drift away from it.

REDIRECTS ARE NOT FOLLOWED

A redirect followed silently is a request that was neither paced nor counted,
and a redirect to a login or block page comes back looking like a 200. A 3xx
is reported here with its Location and goes no further.
"""

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

HOST = "scholars.unh.edu"
BASE = f"https://{HOST}"

OUT = Path("archive/unh")
RAW = OUT / "raw"
LOG = OUT / "fetch_log.jsonl"


def mark_for(url):
    """Where a refusal by THIS host is recorded.

    One file per host, for the reason refusal.py gives for keeping the General
    Court's mark away from everything else: a refusal is a fact about an
    address. scholars.unh.edu saying no should not stop a request to the
    Internet Archive, which has said nothing to us, and the reverse likewise.
    """
    return OUT / f"refused.{urllib.parse.urlsplit(url).netloc}.json"

# Who we are and where to complain. A library that would rather hand over a
# copy than be crawled needs to be able to say so to somebody.
UA = {
    "User-Agent": "granite-record/1.0 (New Hampshire legislative history; "
                  "+https://graniterecord.org; contact@graniterecord.org)",
    "Accept": "*/*",
}

QUIET_HOURS = 24
DELAY = 5.0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


urlopen = urllib.request.build_opener(_NoRedirect).open


def cache_path(url):
    """A readable file name for a URL, unique on a hash of the whole thing."""
    p = urllib.parse.urlsplit(url)
    stem = (p.path.strip("/") or "index").replace("/", "_")
    if p.query:
        stem += "_" + p.query.replace("&", "_").replace("=", "-")
    stem = "".join(c if (c.isalnum() or c in "._-") else "-" for c in stem)[:120]
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return RAW / f"{stem}.{digest}"


#
# WHAT robots.txt SAYS, ENFORCED RATHER THAN READ
#
# scholars.unh.edu disallows /do/ to every agent, and /do/oai/ is where a
# Digital Commons repository keeps its OAI-PMH endpoint. That is the machine
# route this survey went looking for, and it is closed: the first version of
# --recon had it in the list and would have asked for it. It does not now.
#
# robots.txt also advertises a sitemap, https://scholars.unh.edu/siteindex.xml,
# which is a machine route the host has explicitly offered instead. That is
# what an enumeration here should be built on.
#
# A rule read once and remembered in prose is a rule a later run breaks, so it
# is asked of the cached robots.txt before every request instead.
_ROBOTS = {}


def robots(url):
    """The parsed robots.txt for this URL's host, from cache."""
    p = urllib.parse.urlsplit(url)
    host = p.netloc
    if host not in _ROBOTS:
        rurl = f"{p.scheme}://{host}/robots.txt"
        path = cache_path(rurl)
        if not path.exists():
            get(rurl, delay=0)
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(path.read_bytes().decode("utf-8", "replace").splitlines())
        _ROBOTS[host] = rp
    return _ROBOTS[host]


def allowed(url):
    """Does robots.txt let this project's agent ask for this?"""
    if urllib.parse.urlsplit(url).path == "/robots.txt":
        return True
    return robots(url).can_fetch(UA["User-Agent"], url)


def note_refusal(url, why):
    mark = mark_for(url)
    mark.parent.mkdir(parents=True, exist_ok=True)
    mark.write_text(json.dumps({
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "host": urllib.parse.urlsplit(url).netloc,
        "url": url,
        "why": why,
        "clear": f"python3 unh_survey.py --clear {urllib.parse.urlsplit(url).netloc}, "
                 f"once a person has decided",
    }, indent=1), encoding="utf-8")


def refused_now(url):
    """(True, text) while a refusal by this URL's host is younger than QUIET_HOURS."""
    mark = mark_for(url)
    if not mark.exists():
        return False, ""
    try:
        rec = json.loads(mark.read_text(encoding="utf-8"))
        when = datetime.fromisoformat(rec["when"])
    except Exception as e:
        return True, f"{mark} is on file and unreadable ({e}); a person should look"
    age = (datetime.now(timezone.utc) - when).total_seconds() / 3600
    if age >= QUIET_HOURS:
        return False, ""
    return True, (f"{rec.get('host')} refused us {age:.1f}h ago: {rec.get('why')}\n"
                  f"  asking {rec.get('url')}\n"
                  f"  {QUIET_HOURS - age:.1f}h of quiet left. "
                  f"Clearing it is a person's decision: {rec.get('clear')}")


def log(entry):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["when"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# A block page wearing HTTP 200 is real, but so is an ordinary page that
# happens to mention Cloudflare in a script tag -- which is most of the web.
# The first version of this looked for the bare word and called the UNH series
# landing page, 200 OK and perfectly healthy, a refusal. These are the titles
# and error codes a challenge page actually carries, not words that appear in
# one. Matched against the <title> and the first 4kB only.
BLOCK_MARKS = (
    "just a moment...",                 # Cloudflare's JS challenge
    "attention required! | cloudflare",
    "access denied",
    "access to this page has been denied",
    "request blocked",
    "you have been blocked",
    "please verify you are a human",
    "error code: 1020",                 # Cloudflare firewall rule
    "error code: 1015",                 # Cloudflare rate limit
    "unusual traffic from your computer",
)


def classify(status=None, body=None):
    """refused | missing | failed | ok. A block page arrives wearing a 200."""
    if status in (401, 403, 429):
        return "refused"
    if status == 404 or status == 410:
        return "missing"
    if status and status >= 500:
        return "failed"
    if body:
        low = body[:4000].lower()
        if any(m in low for m in BLOCK_MARKS):
            return "refused"
    return "ok"


def head(url, delay=DELAY):
    """How big is it, without fetching it.

    A bound annual House journal is a book. Asking for one to find out that it
    is 300MB is a rude way to learn a number the server will state in a header.
    Not cached: there is no body to keep, and the answer is one line.
    """
    blocked, text = refused_now(url)
    if blocked:
        print(text, file=sys.stderr)
        sys.exit(2)
    if not allowed(url):
        print(f"robots.txt disallows {url} -- not asking for it.", file=sys.stderr)
        return None, {}
    time.sleep(delay)
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    try:
        with urlopen(req, timeout=45) as r:
            status, headers = r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        status, headers = e.code, dict(e.headers)
    except Exception as e:
        log({"url": url, "method": "HEAD", "error": f"{type(e).__name__}: {e}"})
        print(f"  {url}\n  {type(e).__name__}: {e}", file=sys.stderr)
        return None, {}
    verdict = classify(status)
    log({"url": url, "method": "HEAD", "status": status, "verdict": verdict,
         "content_type": headers.get("Content-Type", ""),
         "content_length": headers.get("Content-Length", ""),
         "location": headers.get("Location", "")})
    # A 403 counts whichever method met it. It may well mean no more than
    # "this CGI does not implement HEAD" -- but the difference between that
    # and being unwelcome cannot be told apart from here, and the way to tell
    # them apart is to ask the same address again by another method, which is
    # the definition of working around a refusal. So it stops, and a person
    # decides. What it is NOT allowed to do is guess in our own favour.
    if verdict == "refused":
        note_refusal(url, f"HTTP {status} on a HEAD request")
        print(f"REFUSED: {url} -> HTTP {status} (HEAD). On file in {mark_for(url)}.\n"
              f"  This may only mean that HEAD is not implemented here. Telling\n"
              f"  that from a block needs a person, not another request.",
              file=sys.stderr)
        sys.exit(2)
    return status, headers


def get(url, delay=DELAY, refresh=False):
    """(status, headers, bytes, source). Cached forever; paced when not."""
    path = cache_path(url)
    meta = path.with_suffix(path.suffix + ".meta.json")
    if path.exists() and meta.exists() and not refresh:
        rec = json.loads(meta.read_text(encoding="utf-8"))
        return rec["status"], rec["headers"], path.read_bytes(), "cache"

    blocked, text = refused_now(url)
    if blocked:
        print(text, file=sys.stderr)
        sys.exit(2)

    if not allowed(url):
        print(f"robots.txt disallows {url} -- not asking for it.", file=sys.stderr)
        log({"url": url, "verdict": "disallowed by robots.txt"})
        return None, {}, b"", "robots"

    time.sleep(delay)
    req = urllib.request.Request(url, headers=UA)
    status, headers, body = None, {}, b""
    try:
        with urlopen(req, timeout=45) as r:
            status, headers, body = r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        status, headers, body = e.code, dict(e.headers), e.read() or b""
    except Exception as e:
        log({"url": url, "error": f"{type(e).__name__}: {e}"})
        print(f"  {url}\n  {type(e).__name__}: {e}", file=sys.stderr)
        return None, {}, b"", "error"

    verdict = classify(status, body.decode("utf-8", "replace"))
    log({"url": url, "status": status, "bytes": len(body), "verdict": verdict,
         "content_type": headers.get("Content-Type", ""),
         "location": headers.get("Location", "")})

    # CACHE FIRST, JUDGE SECOND. The first version exited on a refusal before
    # writing anything, so the one thing a person needs to see -- what the
    # block page said -- was the one thing thrown away, and diagnosing it cost
    # another request to the host that had just refused us. A response we have
    # already paid for is kept, whatever it turns out to be.
    RAW.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    meta.write_text(json.dumps({"url": url, "status": status, "verdict": verdict,
                                "headers": headers, "bytes": len(body)},
                               indent=1), encoding="utf-8")

    if verdict == "refused":
        note_refusal(url, f"HTTP {status}" if status else "a block page with 200")
        print(f"REFUSED: {url} -> HTTP {status}. Stopping, and it is on file "
              f"in {mark_for(url)}. What it said is cached at {path} -- read that "
              f"rather than asking again. Tell a person before this host is "
              f"asked anything else.", file=sys.stderr)
        sys.exit(2)

    return status, headers, body, "network"


def describe(url, status, headers, body, source):
    ct = headers.get("Content-Type", "?")
    loc = headers.get("Location", "")
    print(f"\n{url}")
    print(f"  {status}  {len(body):,} bytes  {ct}  [{source}]")
    if loc:
        print(f"  -> Location: {loc}")
    print(f"  cached at {cache_path(url)}")


def recon(delay, refresh):
    """What is reachable, and on whose terms.

    /do/oai/ is deliberately absent. It is where a Digital Commons repository
    keeps OAI-PMH, it was in the first draft of this list, and robots.txt
    disallows /do/ to everyone. The sitemap in its place is the route the host
    advertises in that same file.
    """
    got = 0
    for url in (f"{BASE}/robots.txt",
                f"{BASE}/siteindex.xml",
                f"{BASE}/senate_house/"):
        status, headers, body, source = get(url, delay=delay, refresh=refresh)
        if status is None:
            continue
        got += 1
        describe(url, status, headers, body, source)
        text = body.decode("utf-8", "replace")
        if url.endswith(("robots.txt", ".xml")):
            print("\n".join(f"    | {ln}" for ln in text.splitlines()[:25]))
    # Silence is not success: a run that asked for nothing and exited zero is
    # the failure this project has met five times in a week.
    if got == 0:
        print("recon reached nothing at all -- no page answered.", file=sys.stderr)
        sys.exit(1)
    print(f"\n{got} of 3 answered. Every byte is under {RAW}; "
          f"every request is in {LOG}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recon", action="store_true",
                    help="robots.txt, the series landing page, OAI Identify")
    ap.add_argument("--get", metavar="URL", help="one page, cached and paced")
    ap.add_argument("--head", metavar="URL", help="size and type only; no body")
    ap.add_argument("--show", metavar="URL", help="print what is cached; no network")
    ap.add_argument("--log", action="store_true", help="every request made so far")
    ap.add_argument("--clear", nargs="?", const=True, metavar="HOST",
                    help="clear a recorded refusal, for one host or all "
                         "(a person's decision)")
    ap.add_argument("--delay", type=float, default=DELAY,
                    help=f"seconds between requests (default {DELAY:g})")
    ap.add_argument("--refresh", action="store_true",
                    help="ask again for something already cached")
    a = ap.parse_args()

    if a.clear:
        marks = sorted(OUT.glob("refused.*.json"))
        if a.clear is not True and isinstance(a.clear, str):
            marks = [m for m in marks if m.name == f"refused.{a.clear}.json"]
        if not marks:
            print("nothing on file")
            return
        for m in marks:
            print(f"cleared {m}  ({m.read_text(encoding='utf-8').strip()})")
            m.unlink()
        return

    if a.log:
        if not LOG.exists():
            print("no requests made yet")
            return
        for line in LOG.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            print(f"{r['when']}  {r.get('status','---')}  "
                  f"{r.get('bytes',0):>9,}  {r.get('verdict',''):8}  {r['url']}")
        return

    if a.show:
        path = cache_path(a.show)
        if not path.exists():
            print(f"not cached: {a.show}\n  looked at {path}", file=sys.stderr)
            sys.exit(1)
        sys.stdout.write(path.read_bytes().decode("utf-8", "replace"))
        return

    if a.head:
        status, headers = head(a.head, delay=a.delay)
        if status is None:
            sys.exit(1)
        n = headers.get("Content-Length")
        print(f"\n{a.head}\n  {status}  {headers.get('Content-Type','?')}"
              + (f"  {int(n):,} bytes ({int(n)/1e6:.1f} MB)" if n and n.isdigit() else "  size not stated")
              + (f"\n  -> Location: {headers['Location']}" if headers.get("Location") else ""))
        return

    if a.get:
        status, headers, body, source = get(a.get, delay=a.delay, refresh=a.refresh)
        if status is None:
            sys.exit(1)
        describe(a.get, status, headers, body, source)
        return

    if a.recon:
        recon(a.delay, a.refresh)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
