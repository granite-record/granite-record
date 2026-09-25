#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-20.8
"""
Fetch what New Hampshire's towns publish about their own officials.

    python3 town_sites.py --status              # what is on disk, no network
    python3 town_sites.py --home                # each municipality's home page
    python3 town_sites.py --links               # candidates found, no network
    python3 town_sites.py --officials           # fetch those candidates
    python3 town_sites.py --home --only lyme hancock --limit 5
    python3 town_sites.py --home --retry-refused --agent browser

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

PACE AND REFUSAL. Five seconds between requests. A host that answers 403, 429
or 503 is recorded and not asked again in that run, and a run never retries
anything on its own. The one way a refused town is asked again is
`--retry-refused`, which a person starts, which fetches nothing else, and
which is the whole of what the two agents above are for.

Two sources for the address, because they disagree about 38 towns and one of
them is sometimes the dead one -- Conway's clerk-list host does not resolve
at all, and `deerfieldnh.gog` is a typo for `.gov`. Both are tried, in order,
and the record says which answered.

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

# WHO THIS SAYS IT IS, AND WHY THERE ARE TWO ANSWERS.
#
# The first pass identifies itself. A quarter of the towns -- 9 of the first
# 36 -- answered 403 to it: Antrim, Barnstead, Barrington, Berlin, Bethlehem,
# Brentwood, Brookfield, Canaan, Candia and the rest, all behind the same kind
# of blanket filter, and none of them disallowing this project in robots.txt.
# At that rate about 58 of 234 towns are unreachable under a name, and they
# skew large.
#
# The person decided to use the browser string `fetch_town_clerks.py` already
# uses for the Secretary of State, on the reasoning that robots.txt is a
# town's considered statement of who may read its pages -- and it permits this
# -- while a filter that rejects every client it does not recognise is a
# default nobody chose. It is their project and their standing with these
# towns, so it was their call and not this script's.
#
# AND IT MADE NO DIFFERENCE, WHICH IS WHY THIS PARAGRAPH IS STILL HERE.
# Antrim, Barnstead, Brentwood and Canaan were asked again under the browser
# string and answered 403 to that too. So the filter is not reading the name:
# it is Cloudflare's bot management, and the same four serve the "Performing
# security verification" interstitial to the browser pane as well, which does
# not clear. These towns are not reachable by this project by any means it is
# willing to use, and `refused_by_host` is the honest record of that rather
# than a gap that looks like nobody looked.
#
# The two agents stay because the decision was made and the machinery is what
# proved the answer. Every fetch stores the agent it used, `--agent browser`
# is never the default, and `--retry-refused` is started by a person and
# fetches nothing else.
AGENTS = {
    "project": ("granite-record/1.0 (civic transparency project; "
                "contact@graniterecord.org)"),
    "browser": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
}
AGENT = AGENTS["project"]


def headers(agent):
    return {"User-Agent": AGENTS[agent],
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

# AND THE SAME WORDS IN THE LINK TEXT, which the path does not always carry.
# "Select Board Meeting Minutes" matches the select-board pattern and scores
# 90, and it is a page of attendees and motions: parsing Stark's produced
# 1,294 candidate name-and-office pairs for a town that elects perhaps twenty
# people. Thirty-one of the 514 pages fetched before this existed are of that
# kind, and they account for nearly all of the noise.
NOISE_TEXT = re.compile(
    r"\b(minutes?|agendas?|newsletters?|meetings?|sessions?|notices?|"
    r"calendars?|archives?|packets?|videos?|recordings?|schedules?|dates?|"
    r"live\s*stream(ed)?)\b", re.I)


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
        # A CITY'S CLERKS ARE FILED BY WARD. The clerk list has no "franklin",
        # only "franklin-ward-1" to "-3", so the city's own address in it was
        # never tried -- and for Franklin it is the live one (franklinnh.gov),
        # while NHDOT's franklinnh.org resolves and never answers. All twelve
        # cities with wards are filed this way; the first ward stands for the
        # city where the city has no line of its own.
        clerk = clerks.get(key) or next(
            (v for k, v in sorted(clerks.items())
             if k.startswith(key + "-ward-") and isinstance(v, dict)), None) or {}
        for raw in ((offs.get(key) or {}).get("website"),
                    clerk.get("website")):
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
    def __init__(self, pace=PACE, agent="project"):
        self.pace = pace
        self.agent = agent
        self.last = 0.0
        self.refused = set()
        self.n = 0

    def raw(self, url, timeout=TIMEOUT):
        wait = self.pace - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        self.last = time.time()
        self.n += 1
        req = urllib.request.Request(url, headers=headers(self.agent))
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
               "agent": self.agent, "bytes": len(body or b"")}
        if st in REFUSED:
            self.refused.add(host)
            rec["note"] = "the host refused; not asked again in this run"
        if st == 200 and body:
            rec["sha256"] = hashlib.sha256(body).hexdigest()
        return rec, body


# ------------------------------------------------------------------ links ---

def score_of(text):
    return max((s for s, pat in WANT if re.search(pat, text, re.I)), default=0)


def bare_host(netloc):
    """'www.wolfeboronh.org' -> 'wolfeboronh.org'.

    Written out because `netloc.lstrip("www.")` does not do this: lstrip takes
    a SET of characters, so it eats every leading w and dot it can find and
    turns wolfeboronh.org into olfeboronh.org. It happened to compare equal
    only because both sides were mangled the same way.
    """
    h = netloc.lower().split("@")[-1]
    return h[4:] if h.startswith("www.") else h


def _keep(url, base, out, score, text, hosts=None):
    p = urllib.parse.urlparse(url)
    if p.scheme not in ("http", "https"):
        return
    ok = hosts or {bare_host(urllib.parse.urlparse(base).netloc)}
    if bare_host(p.netloc) not in ok:
        return                              # stay on the town's own host
    clean = f"{p.scheme}://{p.netloc}{p.path}" + (f"?{p.query}" if p.query else "")
    if clean.rstrip("/") == base.rstrip("/") or NOISE.search(clean):
        return
    # The noise words in the PATH as well, and not only as a whole segment.
    # Stark's minutes page is /2024/05/select-board-meeting-minutes/ and its
    # link text is just "Select Board", so neither the text filter nor a
    # segment-shaped URL rule catches it; the words are inside one segment.
    if NOISE_TEXT.search(re.sub(r"[-_/.]+", " ", p.path)):
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

    AND A SITEMAP NAMES THE TOWN'S CANONICAL HOST, which is not always the one
    we asked. Ashland answers on ashlandnh.org, the address NHDOT holds, and
    every one of the 96 URLs in its own sitemap is ashland.nh.gov. Rejecting
    those as off-host left Ashland with no candidates at all -- it and four
    other towns -- while the page it needs, /pages/boards-committees, sat in
    the file. A host the sitemap itself uses throughout is the town's own by
    definition, so it is allowed beside the one we asked, and the difference
    is worth reading afterwards as a correction to the address we hold.
    """
    out = {}
    hosts = {bare_host(urllib.parse.urlparse(base).netloc)}
    smap_hosts = collections.Counter(
        bare_host(urllib.parse.urlparse(u).netloc)
        for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap or ""))
    if smap_hosts:
        # Only a host the sitemap uses for most of itself; one stray absolute
        # link to somewhere else is not the town changing address.
        top, n = smap_hosts.most_common(1)[0]
        if n >= 0.8 * sum(smap_hosts.values()):
            hosts.add(top)
    for m in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                         html_text or "", re.S | re.I):
        href, text = m.group(1).strip(), m.group(2)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        text = re.sub(r"\s+", " ", text).strip()
        if not text or SKIP_HREF.search(href):
            continue
        score = score_of(text)
        if score and not NOISE_TEXT.search(text):
            _keep(urllib.parse.urljoin(base, href), base, out, score, text,
                  hosts)

    for loc in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap or ""):
        loc = html.unescape(loc.strip())
        if SKIP_HREF.search(loc):
            continue
        # The path IS the link text on a sitemap: /pages/select-board is a
        # page about the select board and says so in the only words it has.
        words = re.sub(r"[-_/]+", " ", urllib.parse.urlparse(loc).path).strip()
        score = score_of(words)
        if score and not NOISE_TEXT.search(words):
            _keep(loc, base, out, score, words, hosts)

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
                # A REFUSAL HAS TO LEAVE A TRACE. Tilton's two candidate pages
                # were both refused, the run printed "2 page(s)" because it
                # counts candidates, and nothing at all was written -- so the
                # town looked identical to one whose pages had never been
                # asked for. Silence is not success, and a skip is a fact
                # about a URL that belongs in the record beside the fetches.
                res.update({"kind": "officials_skipped", "link_text": text,
                            "score": score,
                            "read_on": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
                meta[page_name(u, "skipped")] = res
                failed += 1
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


def refused_home(key):
    """Did this town's home page come back refused, and never succeed?

    A refusal is a fact about a host and a name, not about the town, so it is
    kept and looked up rather than inferred from an empty directory.
    """
    meta = load_meta(key)
    if any(r.get("kind") == "home" and r.get("status") == 200
           for r in meta.values()):
        return False
    return any(r.get("kind") == "home" and r.get("status") in REFUSED
               for r in meta.values())


def why_no_home(key):
    """Why this town has no home page, as one of a fixed set of reasons.

    These are different facts and the brief is emphatic that they must not be
    stored as the same one. A town behind a bot filter, a town whose address
    in our data is dead, and a town that has said in robots.txt that unnamed
    crawlers may not read it are three different things, and only the last is
    the town's own decision about us.
    """
    meta = load_meta(key)
    if any(r.get("kind") == "home" and r.get("status") == 200
           for r in meta.values()):
        return None
    if "_no_url" in meta:
        return "no_website_recorded"
    codes = {r.get("status") for r in meta.values() if r.get("kind") == "home"}
    if any(c in REFUSED for c in codes):
        return "refused_by_host"
    if codes and all(c is None for c in codes):
        return "address_does_not_resolve"
    if 404 in codes:
        return "not_found"
    if any(r.get("status") == "robots_disallow" for r in meta.values()):
        return "not_permitted_by_robots"
    if codes:
        return f"http_{sorted(str(c) for c in codes)[0]}"
    return "not_attempted"


def status(towns):
    home = officials = skipped = 0
    why = collections.Counter()
    who = collections.defaultdict(list)
    for key in towns:
        meta = load_meta(key)
        officials += sum(1 for r in meta.values()
                         if r.get("kind") == "officials" and r.get("status") == 200)
        skipped += sum(1 for r in meta.values()
                       if r.get("kind") == "officials_skipped")
        reason = why_no_home(key)
        if reason is None:
            home += 1
        else:
            why[reason] += 1
            who[reason].append(key)
    print(f"  {len(towns)} municipalities")
    print(f"    home page saved       {home}")
    print(f"    officials pages saved {officials}")
    if skipped:
        print(f"    officials pages refused {skipped}")
    for reason, n in why.most_common():
        print(f"    {reason:26s} {n:4d}")
    for reason, keys in sorted(who.items()):
        print(f"  {reason} ({len(keys)}):")
        for i in range(0, len(keys), 6):
            print("      " + ", ".join(keys[i:i + 6]))


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
    ap.add_argument("--agent", choices=sorted(AGENTS), default="project",
                    help="which name to fetch under; 'browser' is the string "
                         "fetch_town_clerks.py uses and is never the default")
    ap.add_argument("--retry-refused", action="store_true",
                    help="only the towns whose home page was refused")
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

    if a.retry_refused:
        towns = {k: v for k, v in towns.items() if refused_home(k)}
        print(f"  {len(towns)} town(s) whose home page was refused: "
              f"{', '.join(towns) or 'none'}")
        if not towns:
            return 0
    fetcher, robots = Fetcher(a.pace, a.agent), Robots()
    if a.agent != "project":
        print(f"  fetching as {a.agent!r}")
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
