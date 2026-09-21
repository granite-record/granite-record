#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.2
"""
Fetch what New Hampshire's towns publish about their own officials.

    python3 town_sites.py --status              # what is on disk, no network
    python3 town_sites.py --home                # each municipality's home page
    python3 town_sites.py --links               # candidates found, no network
    python3 town_sites.py --officials           # fetch those candidates
    python3 town_sites.py --home --only lyme hancock --limit 5

WHY THIS EXISTS. `town_officials.json` is NHDOT's administrative contact
directory, and on elected officials it is close to empty: about twelve town
clerks across 234 municipalities and not one tax collector, treasurer,
moderator or supervisor of the checklist. It also predates the November 2025
city elections and the March 2026 town elections. The towns publish their own
rosters, and those are the authority for a municipality's officials; NHDOT is
secondary.

NOT THE GENERAL COURT, AND NOT THE LANE. This asks town websites. It takes no
lock, it does not touch `archive/`, and `archive/refused.json` is about
gc.nh.gov and does not apply. Captures go under `town_sites/`, which is
gitignored for the same reason `sources/gis/` is: it is large and it is
re-fetchable.

WHAT IT WILL NOT DO. It does not submit a form, it does not follow a link off
the town's own host, and it does not contact anybody. The Secretary of State's
advice to a voter to "contact your city/town clerk" is advice to a voter.
Closing a gap here means reading what a town has already published, and where
that fails the honest answer is that the town does not publish it.

ROBOTS. `/robots.txt` is read once per host and cached, and a path it
disallows for `*` or for this agent is not fetched -- it is recorded as
refused-by-robots, which is a different fact from a 404 and is stored as one.
A `Crawl-delay` longer than the pace is honoured.

PACE AND REFUSAL. Five seconds between requests, and a refusal is final: a
host that answers 403, 429 or 503 is recorded and not asked again in that run,
and nothing is ever retried. Two sources for the address, because they
disagree about 38 towns and one of them is sometimes the dead one -- Conway's
clerk-list host does not resolve at all, and `deerfieldnh.gog` is a typo for
`.gov`. Both are tried, in order, and the record says which answered.

WHAT IS SAVED. The bytes, unmodified, plus a `_meta.json` for each town
carrying for every URL: the URL asked, the status, the time it was read, the
content type, the length and a sha256. A parser reads those files and touches
no network, which is the rule here and the reason is that a parser has to be
free to be wrong without costing a request.
"""
import argparse
import collections
import hashlib
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
STORE = ROOT / "town_sites"

AGENT = ("granite-record/1.0 (civic transparency project; "
         "contact@graniterecord.org)")
HEADERS = {"User-Agent": AGENT,
           "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}
PACE = 5.0
TIMEOUT = 30
REFUSED = {403, 429, 503}

# What a page about a town's officials is called, and how good a candidate
# each name is. A link scores the highest pattern it matches, and the four
# best-scoring links of a town are the ones worth a request.
WANT = [
    (100, r"\belected\s+officials?\b"),
    (95, r"\btown\s+officials?\b"),
    (95, r"\bcity\s+officials?\b"),
    (90, r"\bboard\s+of\s+selectmen\b"),
    (90, r"\bselect\s*board\b"),
    (85, r"\bboard\s+of\s+aldermen\b"),
    (80, r"\bcity\s+council\b"),
    (75, r"\bboards?\s*(?:&(?:amp;)?|and)?\s*committees?\b"),
    (70, r"\b(?:town|city)\s+government\b"),
    (65, r"\bgovernment\b"),
    (60, r"\bofficials?\b"),
    (75, r"\bboards?\s*(?:&(?:amp;)?|and)?\s*commissions?\b"),
    (55, r"\bdepartments?\b"),
    (50, r"\btown\s+clerk\b"),
    (50, r"\bcity\s+clerk\b"),
    (45, r"\btown\s+office\b"),
    (45, r"\bmayor\b"),
    (40, r"\bmoderator\b"),
    (40, r"\btax\s+collector\b"),
    (40, r"\btreasurer\b"),
    (40, r"\bsupervisors?\s+of\s+the\s+checklist\b"),
]

SKIP_HREF = re.compile(
    r"^(mailto:|tel:|javascript:|#)|\.(pdf|jpe?g|png|gif|zip|docx?|xlsx?|mp4)$",
    re.I)

# A SINGLE MEETING IS NOT A ROSTER. "Select Board Meeting 12" and "Town
# Council meeting" are news items and calendar entries, and on some sites they
# are the only thing on the home page that matches at all -- Lyme's home page
# carries twelve links and one of them is a news item about a Select Board
# meeting. Matching those would spend a request per town on an agenda.
NOISE = re.compile(
    r"/(news|calendar|event|events|agenda|agendas|minutes|archive|archives"
    r"|meeting|meetings|notice|notices|blog|post|posts)(/|$|\?)"
    r"|[?&](eid|aid|nid)=", re.I)


# ---------------------------------------------------------------- targets ---

def municipalities():
    """{key: (display name, [url, ...])} for the 234 incorporated places.

    Two sources for the address, in the order they have proved reliable:
    NHDOT's directory names 230 of them and the clerk list 215, they agree on
    176, and where they differ either may be the live one.
    """
    places = json.loads((ROOT / "places.json").read_text(encoding="utf-8"))["places"]
    clerks = json.loads((ROOT / "town_clerks.json").read_text(encoding="utf-8"))
    offs = json.loads((ROOT / "town_officials.json").read_text(encoding="utf-8"))
    out = {}
    for key, p in sorted(places.items()):
        if not p["named_by"]["nhdot_officials"]["present"]:
            continue                       # the 25 unincorporated places
        urls, seen = [], set()
        for raw in ((offs.get(key) or {}).get("website"),
                    (clerks.get(key) or {}).get("website")):
            u = normalise(raw)
            if u and u not in seen:
                seen.add(u)
                urls.append(u)
        out[key] = (p["name"], urls)
    return out


def normalise(u):
    if not u or not u.strip():
        return None
    u = u.strip()
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    p = urllib.parse.urlparse(u)
    if not p.netloc or "." not in p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}" or None


# ------------------------------------------------------------------ robots ---

class Robots:
    """Just enough of the standard to be polite: Disallow and Crawl-delay."""

    def __init__(self):
        self.cache = {}

    def rules(self, host, fetch):
        if host in self.cache:
            return self.cache[host]
        st, _ct, body = fetch(f"https://{host}/robots.txt")
        dis, delay, agent_match, mine = [], 0.0, False, False
        if st == 200 and body:
            for line in body.decode("utf-8", "replace").splitlines():
                line = line.split("#")[0].strip()
                if not line or ":" not in line:
                    continue
                k, v = (x.strip() for x in line.split(":", 1))
                k = k.lower()
                if k == "user-agent":
                    agent_match = v == "*" or "granite-record" in v.lower()
                    mine = mine or "granite-record" in v.lower()
                elif agent_match and k == "disallow" and v:
                    dis.append(v)
                elif agent_match and k == "crawl-delay":
                    try:
                        delay = max(delay, float(v))
                    except ValueError:
                        pass
        self.cache[host] = (dis, delay)
        return self.cache[host]

    def allows(self, url, fetch):
        p = urllib.parse.urlparse(url)
        dis, _ = self.rules(p.netloc, fetch)
        path = p.path or "/"
        for d in dis:
            pat = re.escape(d).replace(r"\*", ".*")
            if re.match(pat, path):
                return False
        return True

    def delay(self, url, fetch):
        return self.rules(urllib.parse.urlparse(url).netloc, fetch)[1]


# ------------------------------------------------------------------ store ---

def town_dir(key):
    d = STORE / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def meta_path(key):
    return town_dir(key) / "_meta.json"


def load_meta(key):
    p = meta_path(key)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_meta(key, meta):
    meta_path(key).write_text(json.dumps(meta, indent=1, sort_keys=True) + "\n",
                              encoding="utf-8")


def page_name(url, kind):
    h = hashlib.sha256(url.encode()).hexdigest()[:10]
    return f"{kind}-{h}.html"


# ------------------------------------------------------------------ fetch ---

class Fetcher:
    def __init__(self, pace=PACE):
        self.pace = pace
        self.last = 0.0
        self.refused = set()
        self.n = 0

    def raw(self, url, timeout=TIMEOUT):
        wait = self.pace - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        self.n += 1
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.headers.get("Content-Type", ""), r.read()
        except urllib.error.HTTPError as e:
            try:
                body = e.read()[:4000]
            except Exception:
                body = b""
            return e.code, e.headers.get("Content-Type", "") if e.headers else "", body
        except Exception as e:
            return None, type(e).__name__, str(e)[:300].encode()

    def get(self, url, robots):
        host = urllib.parse.urlparse(url).netloc
        if host in self.refused:
            return {"status": "refused_earlier", "url": url}
        if not robots.allows(url, self.raw):
            return {"status": "robots_disallow", "url": url}
        extra = robots.delay(url, self.raw)
        if extra > self.pace:
            time.sleep(extra - self.pace)
        st, ct, body = self.raw(url)
        rec = {"url": url, "status": st, "content_type": ct,
               "read_on": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "bytes": len(body or b"")}
        if st in REFUSED:
            self.refused.add(host)
            rec["note"] = "the host refused; not asked again in this run"
        if st == 200 and body:
            rec["sha256"] = hashlib.sha256(body).hexdigest()
        return rec, body


# ------------------------------------------------------------------ links ---

def score_of(text):
    return max((s for s, pat in WANT if re.search(pat, text, re.I)), default=0)


def _keep(url, base, out, score, text):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https"):
        return
    if p.netloc.lower().lstrip("www.") != \
            urllib.parse.urlparse(base).netloc.lower().lstrip("www."):
        return                              # stay on the town's own host
    clean = f"{p.scheme}://{p.netloc}{p.path}" + (f"?{p.query}" if p.query else "")
    if clean.rstrip("/") == base.rstrip("/") or NOISE.search(clean):
        return
    # ONE PAGE IS ONE PAGE whichever scheme it is linked under. Bath links its
    # selectboard page as both http:// and https://, and counting them apart
    # spent two of that town's four requests on the same page.
    ident = (p.netloc.lower().lstrip("www."), p.path.rstrip("/").lower(), p.query)
    # AND THE PAGE ITSELF BEATS A PAGE ABOUT IT. "Board of Selectmen
    # Initiatives" matches the same pattern as "Board of Selectmen" and scored
    # the same, so which got fetched was down to the order they happened to
    # appear in. A link whose text is the office and little else is the
    # roster; one with several more words is a page about the office.
    rank = (score, -max(0, len(text.split()) - 4))
    if ident not in out or rank > out[ident][0]:
        keep_url = clean
        if ident in out and p.scheme == "http" and out[ident][3].startswith("https"):
            keep_url = out[ident][3]
        out[ident] = (rank, score, text, keep_url)


def links_from(html_text, base, sitemap=None):
    """(score, text, absolute url) for the candidates on a saved page.

    Two sources, because one of them is often empty. A town on a modern static
    host renders its navigation in JavaScript and the HTML carries almost no
    links at all -- Lyme's home page has twelve, one of which is a news item --
    while its sitemap.xml lists all ninety-one pages including
    /pages/select-board. Where both exist they agree; where one is silent the
    other answers.
    """
    out = {}
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                         html_text or "", re.S | re.I):
        href, text = m.group(1).strip(), m.group(2)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        text = re.sub(r"\s+", " ", text).strip()
        if not text or SKIP_HREF.search(href):
            continue
        score = score_of(text)
        if score:
            _keep(urllib.parse.urljoin(base, href), base, out, score, text)

    for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap or ""):
        loc = html.unescape(loc.strip())
        if SKIP_HREF.search(loc):
            continue
        # The path IS the link text on a sitemap: /pages/select-board is a
        # page about the select board and says so in the only words it has.
        words = re.sub(r"[-_/]+", " ", urllib.parse.urlparse(loc).path).strip()
        score = score_of(words)
        if score:
            _keep(loc, base, out, score, words)

    return sorted(((score, text, url)
                   for (_rank, score, text, url) in out.values()),
                  key=lambda r: (-r[0], len(r[1]), r[1]))


def saved(key, kind):
    meta = load_meta(key)
    for name, rec in meta.items():
        if rec.get("kind") == kind and rec.get("status") == 200:
            p = town_dir(key) / name
            if p.exists():
                return rec["url"], p.read_text(encoding="utf-8", errors="replace")
    return None, None


def saved_home(key):
    """(base url, home html, sitemap xml or "")."""
    base, page = saved(key, "home")
    _u, smap = saved(key, "sitemap")
    return base, page, smap or ""


# ------------------------------------------------------------------- runs ---

def run_home(towns, fetcher, robots, force=False):
    got = failed = skipped = 0
    for key, (name, urls) in towns.items():
        meta = load_meta(key)
        if not force and any(r.get("kind") == "home" and r.get("status") == 200
                             for r in meta.values()):
            skipped += 1
            continue
        if not urls:
            meta["_no_url"] = {"status": "not_established",
                               "note": "neither source records a website"}
            save_meta(key, meta)
            failed += 1
            continue
        ok = False
        for u in urls:
            res = fetcher.get(u, robots)
            if isinstance(res, dict):
                meta[f"_skipped-{hashlib.sha256(u.encode()).hexdigest()[:8]}"] = res
                continue
            rec, body = res
            rec["kind"] = "home"
            fn = page_name(u, "home")
            if rec.get("status") == 200 and body:
                (town_dir(key) / fn).write_bytes(body)
                ok = True
            meta[fn] = rec
            if ok:
                # A SITEMAP IS ONE REQUEST AND IT IS OFTEN THE ONLY WAY IN.
                # Where the navigation is rendered in JavaScript the HTML
                # carries no links to score, and sitemap.xml lists every page
                # the site has. Where there is none, the 404 is recorded and
                # the HTML links are all there is.
                root = "{0}://{1}".format(*urllib.parse.urlparse(u)[:2])
                sm = fetcher.get(root + "/sitemap.xml", robots)
                if not isinstance(sm, dict):
                    srec, sbody = sm
                    srec["kind"] = "sitemap"
                    sfn = page_name(srec["url"], "sitemap")
                    if srec.get("status") == 200 and sbody and                             b"<loc" in sbody[:200000]:
                        (town_dir(key) / sfn).write_bytes(sbody)
                    meta[sfn] = srec
                break
        save_meta(key, meta)
        got += ok
        failed += (not ok)
        print(f"  {key:22s} {'ok' if ok else 'FAILED':6s}  "
              f"{urls[0] if urls else '-'}", flush=True)
    return got, failed, skipped


def run_officials(towns, fetcher, robots, per_town=4, force=False):
    got = failed = 0
    for key in towns:
        base, page, smap = saved_home(key)
        if not page:
            continue
        meta = load_meta(key)
        have = {r["url"] for r in meta.values() if r.get("kind") == "officials"}
        cands = [(s, t, u) for s, t, u in links_from(page, base, smap)
                 if force or u not in have][:per_town]
        for score, text, u in cands:
            res = fetcher.get(u, robots)
            if isinstance(res, dict):
                continue
            rec, body = res
            rec.update({"kind": "officials", "link_text": text, "score": score})
            fn = page_name(u, "officials")
            if rec.get("status") == 200 and body:
                (town_dir(key) / fn).write_bytes(body)
                got += 1
            else:
                failed += 1
            meta[fn] = rec
        if cands:
            save_meta(key, meta)
            print(f"  {key:22s} {len(cands)} page(s)", flush=True)
    return got, failed


def status(towns):
    home = officials = nourl = 0
    missing = []
    for key in towns:
        meta = load_meta(key)
        h = any(r.get("kind") == "home" and r.get("status") == 200
                for r in meta.values())
        o = sum(1 for r in meta.values()
                if r.get("kind") == "officials" and r.get("status") == 200)
        home += h
        officials += o
        if "_no_url" in meta:
            nourl += 1
        if not h:
            missing.append(key)
    print(f"  {len(towns)} municipalities")
    print(f"    home page saved       {home}")
    print(f"    officials pages saved {officials}")
    print(f"    no website recorded   {nourl}")
    if missing:
        print(f"    {len(missing)} without a home page: "
              + ", ".join(missing[:14]) + (" ..." if len(missing) > 14 else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--home", action="store_true")
    ap.add_argument("--officials", action="store_true")
    ap.add_argument("--links", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--per-town", type=int, default=4)
    ap.add_argument("--pace", type=float, default=PACE)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    towns = municipalities()
    if a.only:
        towns = {k: v for k, v in towns.items() if k in set(a.only)}
    if a.limit:
        towns = dict(list(towns.items())[:a.limit])

    if a.status or not (a.home or a.officials or a.links):
        status(towns)
        return 0

    if a.links:
        for key in towns:
            base, page, smap = saved_home(key)
            if not page:
                continue
            cands = links_from(page, base, smap)[:a.per_town]
            print(f"  {key}  ({base})")
            for s, t, u in cands:
                print(f"      {s:3d}  {t[:40]:42s} {u}")
        return 0

    fetcher, robots = Fetcher(a.pace), Robots()
    if a.home:
        got, failed, skipped = run_home(towns, fetcher, robots, a.force)
        print(f"\n  home pages: {got} fetched, {failed} failed, "
              f"{skipped} already on disk; {fetcher.n} requests")
    if a.officials:
        got, failed = run_officials(towns, fetcher, robots, a.per_town, a.force)
        print(f"\n  officials pages: {got} fetched, {failed} failed; "
              f"{fetcher.n} requests this run")
    if fetcher.refused:
        print(f"  hosts that refused: {sorted(fetcher.refused)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
