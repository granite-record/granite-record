#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.8
"""
Why is the General Court refusing us?

    python3 netcheck.py

Seven requests, one per theory, three seconds apart. Nothing is written and
nothing else is touched.

WHAT COUNTS AS GETTING THROUGH (29 October 2026). Only an answer of 2xx that
is not the firewall's block page. A 403, a 429, a 503 or a redirect is the
server answering -- which is worth knowing, and printed in full below -- but
it is the address being told no, not a request that got through; the first
version counted every answer, so a table of 403s ended "Everything got
through". An eighth request, labelled the root, asked the fourth's page
again over the fourth's HTTP version, and is gone.

NOT BESIDE GITHUB, ON THE LAPTOP THAT HANDED IT THE NIGHT (29 October 2026,
the hourly addendum's 7, item 3). On a stood-down laptop netcheck asks
nothing while refusal.gc_turn() says it is not this laptop's turn -- inside
GitHub's night window, in the half hour before it, or before this laptop has
read the bucket's refusal record since the last one closed (a refusal.py
--clear included) -- which is the laptop's one-fetch-at-a-time rule every
other General Court request here keeps. And it asks nothing while the
refusal on file is one GitHub's night may be testing itself
(refusal._its_own: a drop or a 503 GitHub's night on main met), unless the
person says the test is stopped: --knock-stopped. The laptop cannot read
the switch that turns that testing off, so the flag is the person's word.
Off a stood-down laptop nothing of this applies.

WHAT HAPPENED

Every request started failing with RemoteDisconnected -- the server accepts the
TCP connection and closes it without sending a byte. It did this to the first
step of a nightly run, before that run had asked for anything, and to single
probes with nothing else going. Fetching worked nine hours earlier.

That rules out the obvious cause. It is not too many connections at once,
because one connection did it too.

WHAT IS LEFT, AND HOW EACH IS TOLD APART

  The address is unreachable         everything below fails, including plain
                                     http and the other hostname
  The IP has been blocked            everything fails here, but the site loads
                                     in a browser on the same machine
  The User-Agent is rejected         our UA fails, a browser UA works
  The headers are too sparse         a full browser header set works where a
                                     bare UA does not
  TLS or HTTP version                http/1.0 works where 1.1 does not, or
                                     plain http works where https does not
  One hostname is behind a stricter  gc.nh.gov fails, www.gencourt.state.nh.us
  front door                         works, or the other way round

The last four are all fixable in an hour. The second is fixable by waiting. So
it is worth seven requests to find out which.

RUN THE BROWSER TEST TOO

Open https://gc.nh.gov/ in a browser on the same machine. If the site loads
there and every line below fails, the block is on this program rather than on
this address, and the differences below say what about it.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import http.client
import re
import socket
import ssl
import time
import urllib.error
import urllib.request

import refusal

# What asks, by name, so that a check can stand fakes in for both and no test
# ever reaches the General Court: an opener's open for the urllib requests,
# and the connection class for each scheme of the raw ones.
#
# NO REDIRECT IS FOLLOWED (the reviewers of 30 October 2026). URLOPEN was
# urllib.request.urlopen, which follows a 3xx to its Location: three of the
# seven requests made a second one, to a target nobody chose, and the answer
# there counted as getting through. The opener has no redirect handler
# (refusal.no_redirect_opener), so a 3xx comes back as an HTTPError, and
# answered() reads it as "a redirect, not the page".
URLOPEN = refusal.no_redirect_opener().open
CONNECTIONS = {"https": http.client.HTTPSConnection, "http": http.client.HTTPConnection}

OURS =("granite-record/1.0 (civic transparency project; "
        "contact@graniterecord.org)")
BROWSER = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
FULL = {"User-Agent": BROWSER,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "close"}

PATH = "/senate/about_senate/about.aspx"
HOSTS = ["gc.nh.gov", "www.gencourt.state.nh.us"]


BODIES = []


def keep(label, status, headers, body):
    """Anything that answered is worth reading, especially a refusal.

    A 403 with two kilobytes behind it is a page somebody wrote, and it says
    who is refusing and usually why. That is the whole answer, sitting in a
    response that the first version of this script counted and threw away.
    """
    BODIES.append((label, status, dict(headers or {}), body or b""))


def answered(status, body):
    """One line for an answer, in the words the verdict reads: only a 2xx
    that is not the firewall's block page begins "HTTP 2" and is not said to
    be the block page (through())."""
    text = (body or b"")[:4000].decode("utf-8", "replace")
    if 200 <= status < 300 and refusal.BLOCKED.search(text):
        return f"HTTP {status} -- the firewall's block page, not the page"
    if 200 <= status < 300:
        return f"HTTP {status}, {len(body or b''):,}+ bytes"
    if 300 <= status < 400:
        return f"HTTP {status} -- a redirect, not the page"
    return f"HTTP {status} -- the server ANSWERED, and said no"


def through(out):
    """Whether a result line is a request that got through: a 2xx that is
    not the block page. A 403, a 429, a 503 or a redirect answered, and said
    no."""
    return out.startswith("HTTP 2") and "block page" not in out


def urllib_try(url, headers, label=""):
    req = urllib.request.Request(url, headers=headers)
    try:
        with URLOPEN(req, timeout=45) as r:
            body = r.read(4096)
            keep(label, r.status, r.headers, body)
            return answered(r.status, body)
    except urllib.error.HTTPError as e:
        body = e.read(4096)
        keep(label, e.code, e.headers, body)
        raise


def raw_try(host, version, scheme="https", label=""):
    """http.client directly, so the HTTP version can be pinned."""
    cls = CONNECTIONS["https" if scheme == "https" else "http"]
    kw = {"timeout": 45}
    if scheme == "https":
        kw["context"] = ssl.create_default_context()
    c = cls(host, **kw)
    c._http_vsn, c._http_vsn_str = version, f"HTTP/{version // 10}.{version % 10}"
    try:
        c.request("GET", PATH, headers={"User-Agent": BROWSER, "Accept": "*/*",
                                        "Connection": "close"})
        r = c.getresponse()
        body = r.read(4096)
        keep(label, r.status, r.headers, body)
        return answered(r.status, body)
    finally:
        c.close()


def not_now(knock_stopped=False):
    """The sentence that stops netcheck before its first request, or "": on
    a stood-down laptop only (the docstring's NOT BESIDE GITHUB), while
    gc_turn() says it is not this laptop's turn, and while the refusal on
    file is one GitHub's night may be testing itself and the person has not
    said that test is stopped (`knock_stopped`)."""
    if refusal._governing() is None:
        return ""
    turn = refusal.gc_turn()
    if turn:
        return f"netcheck is not starting. {turn[1]}"
    try:
        raw = refusal.MARK.read_bytes()
    except OSError:
        raw = None
    if raw is not None and not knock_stopped and refusal._its_own(refusal._record(raw)[0])[0]:
        return ("netcheck is not starting. GitHub may be testing the refusal on file here "
                f"({refusal.MARK}) itself, once an hour. Two machines asking at once is how the "
                "second block happened. Set the GitHub variable NIGHT_KNOCK to off, or disable "
                "the knock workflow, wait until the Actions tab shows no knock run and no night "
                f"in progress (a knock job lasts {refusal.KNOCK_JOB_MINUTES} minutes at most), "
                "then run python3 netcheck.py --knock-stopped.")
    return ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Why is the General Court refusing us? Seven "
                                             "requests, one per theory.")
    ap.add_argument("--knock-stopped", action="store_true",
                    help="the person's word that GitHub is not testing the refusal on file: "
                         "NIGHT_KNOCK set to off, and no night running")
    a = ap.parse_args(argv)
    stop = not_now(a.knock_stopped)
    if stop:
        print(f"\n{stop}\n", file=sys.stderr)
        return refusal.STOOD_DOWN
    tests = [
        ("our User-Agent, https, gc.nh.gov",
         lambda: urllib_try(f"https://{HOSTS[0]}{PATH}", {"User-Agent": OURS}, "ua-ours")),
        ("full browser headers",
         lambda: urllib_try(f"https://{HOSTS[0]}{PATH}", FULL, "ua-browser")),
        # The gap in the first run: urllib was the only thing speaking 1.1 over
        # TLS, so "1.0 works, 1.1 does not" could equally have been "the socket
        # works, urllib does not". This tells them apart.
        ("https, HTTP/1.1, raw socket",
         lambda: raw_try(HOSTS[0], 11, "https", "raw-11")),
        ("https, HTTP/1.0, raw socket",
         lambda: raw_try(HOSTS[0], 10, "https", "raw-10")),
        ("plain http, the real page",
         lambda: raw_try(HOSTS[0], 11, "http", "plain-http")),
        ("the other hostname, https 1.1",
         lambda: urllib_try(f"https://{HOSTS[1]}{PATH}", FULL, "other-11")),
        ("the other hostname, https 1.0",
         lambda: raw_try(HOSTS[1], 10, "https", "other-10")),
    ]

    print(f"{len(tests)} requests, one per theory, three seconds apart.")
    print("Nothing is written.\n")
    print(f"  {'what is being tried':<36}result")
    print("  " + "-" * 62)
    results = []
    for label, fn in tests:
        try:
            out = fn()
        except urllib.error.HTTPError as e:
            out = answered(e.code, b"")
        except (http.client.RemoteDisconnected, ConnectionResetError):
            out = "refused (closed without answering)"
        except socket.timeout:
            out = "timed out"
        except Exception as e:
            out = f"{type(e).__name__}: {e}"[:44]
        ok = through(out)
        results.append((label, ok, out))
        print(f"  {label:<36}{out}")
        time.sleep(3)

    # Whatever answered, print it. This is the part that names the blocker.
    if BODIES:
        print("\n" + "=" * 66)
        print("WHAT ANSWERED, in full. This is the useful part.")
        print("=" * 66)
        for label, status, hdrs, body in BODIES:
            print(f"\n[{label}] HTTP {status}")
            for k in ("Server", "CF-Ray", "X-Iinfo", "X-CDN", "Via",
                      "X-Cache", "Set-Cookie", "Location", "X-Powered-By",
                      "X-Sucuri-ID", "X-Amz-Cf-Id", "Content-Type"):
                for hk, hv in hdrs.items():
                    if hk.lower() == k.lower():
                        print(f"    {hk}: {str(hv)[:110]}")
            txt = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ",
                         body.decode("utf-8", "replace"), flags=re.S | re.I)
            txt = re.sub(r"<[^>]+>", " ", txt)
            txt = re.sub(r"\s+", " ", txt).strip()
            print("    " + (txt[:700] if txt else "(no text in the body)"))

    good = [l for l, ok, _ in results if ok]
    told_no = [l for l, ok, out in results if out.startswith("HTTP") and not ok]
    print()
    if told_no:
        print(f"The server ANSWERED {len(told_no)} of these and said no (a 403, a 429, a 503, "
              "a redirect or the firewall's block page): that is this address being told no, "
              "not a request getting through. What answered, above, says who.\n")
    if not good:
        print("Nothing got through.\n\n"
              "Open https://gc.nh.gov/ in a browser on this machine.\n"
              "  Loads      -> the block is on this program, not this address,\n"
              "                and none of the differences above got round it.\n"
              "                Wait a few hours; a rate-limit block expires.\n"
              "  Also fails -> the General Court is down or unreachable from\n"
              "                here. Nothing to fix on our side.")
    elif len(good) == len(results):
        print("Everything got through. Whatever it was has passed.\n"
              "Re-run the fetch that failed.")
    else:
        print("Some got through and some did not, which is the useful answer.\n"
              "Working:")
        for line in good:
            print(f"    {line}")
        print("\nThe difference between those and the rest is what to change in\n"
              "the fetchers. Send this table.")


if __name__ == "__main__":
    sys.exit(main())
