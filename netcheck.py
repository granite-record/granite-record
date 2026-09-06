#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.2
"""
Why is the General Court refusing us?

    python3 netcheck.py

Eight requests, one per theory, three seconds apart. Nothing is written and
nothing else is touched.

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
it is worth eight requests to find out which.

RUN THE BROWSER TEST TOO

Open https://gc.nh.gov/ in a browser on the same machine. If the site loads
there and every line below fails, the block is on this program rather than on
this address, and the differences below say what about it.
"""

import http.client
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request

OURS = ("granite-record/1.0 (civic transparency project; "
        "corrections@graniterecord.org)")
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


def urllib_try(url, headers, label=""):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            body = r.read(4096)
            keep(label, r.status, r.headers, body)
            return f"HTTP {r.status}, {len(body):,}+ bytes"
    except urllib.error.HTTPError as e:
        body = e.read(4096)
        keep(label, e.code, e.headers, body)
        raise


def raw_try(host, version, scheme="https", label=""):
    """http.client directly, so the HTTP version can be pinned."""
    cls = (http.client.HTTPSConnection if scheme == "https"
           else http.client.HTTPConnection)
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
        return f"HTTP {r.status}, {len(body):,}+ bytes"
    finally:
        c.close()


def raw_try_l(host, version, scheme="https", label=""):
    return raw_try(host, version, scheme, label)


def main():
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
        ("gc.nh.gov root, https 1.0",
         lambda: raw_try(HOSTS[0], 10, "https", "root-10")),
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
            out = f"HTTP {e.code} -- the server ANSWERED"
        except (http.client.RemoteDisconnected, ConnectionResetError):
            out = "refused (closed without answering)"
        except socket.timeout:
            out = "timed out"
        except Exception as e:
            out = f"{type(e).__name__}: {e}"[:44]
        ok = out.startswith("HTTP")
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
    print()
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
