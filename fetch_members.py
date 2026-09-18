#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.7
"""
Pull each member's own page on gencourt: photo, district, towns, contact,
committees and the position they hold on each.

    python3 fetch_members.py --probe 11286     # one page, print what it found
    python3 fetch_members.py --limit 5         # try a handful
    python3 fetch_members.py                   # the roster

Writes member_details.json, keyed by the same member id as data/legislators.json.
Pages are cached in member_pages/ and never refetched, so a parser change is
re-applied with --reparse and touches no network.

WHAT THE PAGE ACTUALLY SAYS

Written against gc.nh.gov/house/members/member.aspx?pid=11286, which reads:

    Representative Alice Wade (D)
    Strafford - District 15
    [member picture]
    Contact Information
    State House-Member Mail
    107 North Main Street
    Concord, NH 03301
    Alice.Wade@gc.nh.gov
    Seat #: 4017
    ...
    Committee Name: Legislative Administration
    Position: Member
    ...
    Towns Represented
    Dover Ward: 2

So the fields are labelled, and this reads the labels rather than the layout --
the same approach fetch_session.py takes to the docket pages, and for the same
reason: markup gets restyled, labels do not.

THE ADDRESS IS THE STATE HOUSE, NOT A HOME

The contact block on this page is the general mailing address every member
shares. data/legislators.json also carries an address parsed out of
legislators.txt, and that one is the member's own. This uses the page's, which
is what a constituent should write to and is nobody's house.

BIOGRAPHY IS DELIBERATELY NOT TAKEN

The page also carries a personal biography and a list of local involvement,
both written by the member. They are public, but they are not the legislative
record, and reproducing several hundred self-written profiles on a site run by
a candidate is a different act from publishing what the General Court did.

SENATE PAGES ARE A DIFFERENT SHAPE

Only a House page has been read. Senate members are fetched too, but anything
that does not parse is reported rather than guessed at, and the count of those
is the first thing to look at in the output.
"""

import argparse
import json
import random
import re
import refusal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

UA = {"User-Agent": "granite-record/1.0 (civic transparency project; "
                    "contact@graniterecord.org)"}

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")

# House: "Representative Alice Wade (D)"
# Senate: "Senator Timothy Lang (R-Sanbornton)" -- the party carries the
# member's home town after a hyphen, and a pattern expecting a bare letter and
# a closing bracket matched neither the name nor anything after it.
NAME_RE = re.compile(
    r"\b(?P<title>Representative|Senator)\s+(?P<name>[A-Z][^()\n]{1,60}?)\s*"
    r"\((?P<party>[A-Za-z])(?:\s*[-\u2013]\s*(?P<home>[^)]{2,40}))?\)")
# "Strafford - District 15" / "District 24"
DIST_RE = re.compile(r"(?:(?P<county>[A-Z][A-Za-z]+)\s*[-\u2013]\s*)?"
                     r"District\s*(?P<district>\d+)")
EMAIL_RE = re.compile(r"[\w.\-]+@(?:gc|leg)\.(?:nh\.gov|state\.nh\.us)", re.I)
SEAT_RE = re.compile(r"Seat\s*#\s*:?\s*(\d+)")
# House pictures live under memberpics/, Senate under senators/. The folder is
# the reliable part; the path in front of it is not. A page can write the same
# picture as "/senate/images/senators/14.jpg" or "../../images/senators/14.jpg"
# and both are correct -- so requiring the chamber in the path missed every
# senator whose page used the relative form, and reported no photo for a member
# who has one.
PHOTO_RE = re.compile(
    r"src\s*=\s*[\"'](?P<src>[^\"']*?(?P<dir>memberpics|senators)/"
    r"(?P<file>[^\"'/]+))[\"']", re.I)
PHONE_RE = re.compile(r"Phone\s*:?\s*(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})", re.I)
CMTE_LINK_RE = re.compile(r"committeedetails\.aspx\?id=(\d+)", re.I)
# "Committee Name: Legislative Administration Position: Member"
CMTE_RE = re.compile(
    r"Committee Name\s*:?\s*(?P<name>.+?)\s*"
    r"Position\s*:?\s*(?P<position>[A-Za-z][A-Za-z /-]{0,30}?)\s*"
    r"(?=Committee Function|Committee Name|Personal Biography|"
    r"Local Government|Towns Represented|$)", re.I | re.S)
TOWNS_RE = re.compile(
    r"Towns Represented\s*(?P<towns>.+?)\s*"
    r"(?=HELPFUL LINKS|DOCUMENTS|OTHER RESOURCES|The General Court|$)",
    re.I | re.S)
# House: "State House-Member Mail, 107 North Main Street, Concord, NH 03301"
# Senate: "State House, Room 117, 107 North Main Street, Concord, NH 03301"
# Both start at the State House and end at the ZIP; nothing between them is
# anyone's home.
MAIL_RE = re.compile(r"(State House.{0,90}?Concord,\s*NH\s*\d{5})", re.I | re.S)

# Senate: "Current Committees: Chair, Ways and Means; Vice Chair, Election
# Law; Finance". Semicolons separate the committees, and a leading position is
# only read as one when it is a position the Senate actually uses -- otherwise
# a committee whose name contains a comma would lose half of itself.
# Everything that can follow the committee list on a senator's page. The list
# is greedy up to whichever comes first, and a terminator missing from here
# does not fail loudly -- it quietly appends the next paragraph to the last
# committee, which then goes on the site as a committee name.
SEN_CMTE_RE = re.compile(
    r"Current Committees\s*:?\s*(?P<list>.+?)\s*"
    r"(?=View Bills|Contact Information|Phone\s*:|Email\s*:|Years Served|"
    r"Other Elected|Profession\s*:|Family\s*:|Other Information|"
    r"State House|Mailing|Legislative Aide|$)", re.I | re.S)
SEN_POS_RE = re.compile(
    r"^(?P<pos>Vice\s+Chair(?:man|woman)?|Chair(?:man|woman)?|Clerk|"
    r"Ranking\s+Member|President)\s*,\s*(?P<name>.+)$", re.I)
# Senate: "District 2: Ashland, Belmont, ... and Thornton."
SEN_TOWNS_RE = re.compile(
    r"District\s*\d+\s*:\s*(?P<towns>.+?)\s*"
    r"(?=Current Committees|Contact Information|View Bills|$)", re.I | re.S)

# Positions worth naming beyond plain membership. Captured, not matched: the
# page states the position and this only decides which ones are notable enough
# to show beside a name.
NOTABLE = re.compile(r"chair|clerk|vice|leader|speaker|president|whip", re.I)


def member_url(m, mid):
    """Where a member's own page lives.

    Built here rather than trusted from the roster, because the roster's Senate
    address was wrong: the path is "district02", spelled out and zero-padded,
    not "dist2".
    """
    if (m.get("chamber") or "").upper().startswith("S"):
        d = str(m.get("district") or "").strip()
        return ("https://gc.nh.gov/senate/members/webpages/"
                f"district{int(d):02d}.aspx" if d.isdigit() else "")
    return f"https://gc.nh.gov/house/members/member.aspx?pid={mid}"


def text_of(html):
    html = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", html,
                  flags=re.S | re.I)
    html = re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", html, flags=re.I)
    t = TAG.sub(" ", html)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&#39;", "'"),
                 ("&quot;", '"'), ("&lt;", "<"), ("&gt;", ">")):
        t = t.replace(a, b)
    return WS.sub(" ", t).strip()


# The General Court closes the connection without answering when it is being
# asked for too much at once -- which is what a nightly run looks like from its
# side. urllib reports that as RemoteDisconnected, whose message says nothing
# about the cause, so it is named here instead of left to be puzzled over.
REFUSED = ("remotedisconnected", "connection reset", "connection aborted",
           "closed connection without response", "timed out")


def busy_note():
    """Say the likely reason before the requests start, not after they fail."""
    if Path(".nightly.lock").exists():
        print("NOTE: a nightly run is going, and the General Court will refuse\n"
              "      connections from a second one. Wait for it to finish.\n")


def refused(err):
    return any(w in f"{type(err).__name__} {err}".lower() for w in REFUSED)


def get(url, timeout=60, tries=5):
    """Fetch, backing off properly when the far end is turning us away.

    Two seconds then four is the right shape for a blip and the wrong one for
    throttling, which is what these failures were: six requests across three
    scripts all refused at once while a nightly run held the connection budget.
    Backing off 3, 9, 27 then 60 seconds gives a busy server time to mean it.
    """
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace"), None
        except Exception as e:
            last = e
            if i < tries - 1:
                wait = min(60, 3 ** (i + 1)) + random.uniform(0, 1.5)
                if refused(e):
                    print(f"    refused, waiting {wait:.0f}s "
                          f"({i + 1} of {tries - 1})")
                time.sleep(wait)
    if refused(last):
        return None, (f"{last} -- the General Court refused the connection. "
                      "This is\n  almost always another fetch running at the "
                      "same time; nothing is wrong\n  with the address.")
    return None, last


def parse(html, base=None):
    """Everything the page states, and nothing it does not."""
    t = text_of(html)
    rec = {}

    m = NAME_RE.search(t)
    if m:
        rec["title"] = m.group("title")
        rec["page_name"] = WS.sub(" ", m.group("name")).strip()
        rec["party_code"] = m.group("party").upper()
        # The Senate names the member's town of residence in the same brackets
        # as the party. A town is not an address, and the General Court prints
        # it on the page itself.
        if m.group("home"):
            rec["home"] = WS.sub(" ", m.group("home")).strip(" .,")

    # Anchored after the name, so the navigation's own "District" links cannot
    # supply one.
    tail = t[m.end():] if m else t
    d = DIST_RE.search(tail[:400])
    if d:
        rec["county"] = (d.group("county") or "").strip()
        rec["district"] = d.group("district")

    e = EMAIL_RE.search(t)
    if e:
        rec["email"] = e.group(0)
    s = SEAT_RE.search(t)
    if s:
        rec["seat"] = s.group(1)
    mail = MAIL_RE.search(t)
    if mail:
        rec["mailing"] = re.sub(r"\s*,\s*", ", ",
                                WS.sub(" ", mail.group(1))).strip(" ,")

    p = PHOTO_RE.search(html)
    if p:
        f = p.group("file")
        # The page uses a placeholder rather than omitting the tag. A site that
        # showed it would print "no photo" 300 times in a grid.
        # Resolved against the page it came from, which is the only thing
        # that turns a relative path into an address.
        if "nophoto" in f.lower():
            rec["photo"] = ""
        elif base:
            rec["photo"] = urllib.parse.urljoin(base, p.group("src"))
        else:
            sub = ("house/images/memberpics" if p.group("dir").lower() ==
                   "memberpics" else "senate/images/senators")
            rec["photo"] = f"https://gc.nh.gov/{sub}/{f}"
    else:
        # No photo matched. Whether that is a member without one or a path
        # this does not know is not something to guess at, so the images that
        # ARE on the page are recorded for the probe to show.
        seen = [x for x in re.findall(r"<img\b[^>]*?src=[\"']([^\"']+)", html,
                                      re.I)
                if not re.search(r"logo|seal|icon|spacer|banner|nav", x, re.I)]
        if seen:
            rec["_images_seen"] = seen[:5]

    ids = CMTE_LINK_RE.findall(html)
    cmtes = []
    for i, cm in enumerate(CMTE_RE.finditer(t)):
        name = WS.sub(" ", cm.group("name")).strip(" :.-")
        pos = WS.sub(" ", cm.group("position")).strip(" :.-")
        if not name:
            continue
        cmtes.append({"name": name, "position": pos,
                      "notable": bool(NOTABLE.search(pos)),
                      "id": ids[i] if i < len(ids) else ""})
    if cmtes:
        rec["committees"] = cmtes

    ph = PHONE_RE.search(t)
    if ph:
        rec["phone"] = ph.group(1)

    # ---- the Senate shape ------------------------------------------------
    sc = SEN_CMTE_RE.search(t)
    if sc and not cmtes:
        # "Chair, Ways and Means; Vice Chair, Election Law; Finance" uses
        # semicolons, with commas inside a position. "Education, Finance" uses
        # commas and has no position at all. Splitting on semicolons alone
        # turned the second into one committee called "Education, Finance".
        #
        # So: semicolons where there are any. Where there are none and the text
        # before the first comma is not a position the Senate uses, the commas
        # are the separators.
        raw_list = sc.group("list")
        parts = raw_list.split(";")
        if len(parts) == 1 and "," in raw_list:
            head = raw_list.split(",")[0].strip()
            if not SEN_POS_RE.match(head + ", x"):
                parts = raw_list.split(",")
        for part in parts:
            part = WS.sub(" ", part).strip(" .;")
            if not part:
                continue
            pm = SEN_POS_RE.match(part)
            name = (pm.group("name") if pm else part).strip(" .,")
            pos = (pm.group("pos").strip() if pm else "Member")
            cmtes.append({"name": name, "position": pos,
                          "notable": bool(NOTABLE.search(pos)), "id": ""})
        if cmtes:
            rec["committees"] = cmtes
        rec["_committees_raw"] = WS.sub(" ", sc.group("list")).strip()

    st = SEN_TOWNS_RE.search(t)
    if st and "towns_raw" not in rec:
        raw = WS.sub(" ", st.group("towns")).strip(" .")
        if raw and len(raw) < 400:
            rec["towns_raw"] = raw
            rec["towns"] = [re.sub(r"^and\s+", "", x.strip(), flags=re.I)
                            for x in raw.split(",") if x.strip()]

    tw = TOWNS_RE.search(t)
    if tw and "towns_raw" not in rec:
        raw = WS.sub(" ", tw.group("towns")).strip()
        rec["towns_raw"] = raw
        # "Dover Ward: 2" and comma or semicolon separated lists both appear.
        # The raw string is kept either way, so a split that gets it wrong
        # loses nothing.
        rec["towns"] = [x.strip() for x in re.split(r"[;,]", raw) if x.strip()]
    return rec


def show(rec, url):
    print(f"\n{url}\n" + "-" * len(url))
    if not rec:
        print("  nothing parsed")
        return
    for k in ("title", "page_name", "party_code", "home", "county", "district",
              "seat", "phone", "email", "mailing", "photo", "towns_raw"):
        if rec.get(k):
            print(f"  {k:<12} {rec[k]}")
    if rec.get("_committees_raw") and len(rec.get("committees", [])) < 2:
        print(f"  committees, as the page wrote them:")
        print(f"               {rec['_committees_raw'][:110]!r}")
        print("               If that is two committees with no separator, "
              "there is nothing\n               here to split on and it needs "
              "the raw HTML to tell.")
    if not rec.get("photo") and rec.get("_images_seen"):
        print("  photo        none matched. Images on the page:")
        for src in rec["_images_seen"]:
            print(f"               {src[:90]}")
    for c in rec.get("committees", []):
        star = "  *" if c["notable"] else "   "
        print(f"  committee  {star}{c['name']} \u2014 {c['position']}")
    missing = [k for k in ("page_name", "district", "email") if not rec.get(k)]
    if missing:
        print(f"  NOT FOUND: {', '.join(missing)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="member_details.json")
    ap.add_argument("--cache", default="member_pages")
    ap.add_argument("--probe", help="one member id, fetch and print, write nothing")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--reparse", action="store_true",
                    help="re-run the parser over cached pages, no network")
    a = ap.parse_args()
    refusal.check("The members fetch")

    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)

    legs = json.loads((Path(a.data) / "legislators.json").read_text(encoding="utf-8"))
    by_id = {str(m["id"]): m for m in legs if m.get("id")}

    if a.probe:
        busy_note()
        m = by_id.get(str(a.probe), {})
        url = m.get("url") or member_url(m, a.probe)
        html, err = get(url)
        if html is None:
            sys.exit(f"could not fetch: {err}")
        show(parse(html, url), url)
        print("\nIf a field above is wrong or missing, send this output and the "
              "pattern\ncan be fixed without another fetch. Nothing was written.")
        return

    out = {}
    op = Path(a.out)
    if op.exists():
        out = json.loads(op.read_text(encoding="utf-8"))
        print(f"{len(out):,} already on file")

    todo = [(i, m) for i, m in by_id.items()
            if a.reparse or i not in out]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo):,} members to do\n")

    fetched = cached = failed = 0
    for n, (mid, m) in enumerate(todo, 1):
        cp = cache / f"{mid}.html"
        if cp.exists():
            html = cp.read_text(encoding="utf-8", errors="replace")
            cached += 1
        elif a.reparse:
            continue
        else:
            url = member_url(m, mid) or m.get("url")
            if not url:
                failed += 1
                continue
            time.sleep(a.delay)
            html, err = get(url)
            if html is None:
                print(f"  {mid}: {type(err).__name__}")
                failed += 1
                continue
            cp.write_text(html, encoding="utf-8")
            fetched += 1
        rec = parse(html, url)
        rec["source"] = m.get("url", "")
        out[mid] = rec
        if n % 50 == 0:
            print(f"  {n:,}/{len(todo):,}", flush=True)
            op.write_text(json.dumps(out, indent=2), encoding="utf-8")

    op.write_text(json.dumps(out, indent=2), encoding="utf-8")

    have = lambda k: sum(1 for r in out.values() if r.get(k))
    print(f"\n{len(out):,} members -> {a.out}")
    print(f"  {fetched:,} fetched, {cached:,} from cache, {failed:,} failed")
    print(f"  {have('page_name'):,} named, {have('district'):,} with a district, "
          f"{have('email'):,} with an email")
    print(f"  {have('photo'):,} with a photo, {have('towns_raw'):,} with towns")
    print(f"  {have('committees'):,} with a committee")
    roles = Counter(c["position"] for r in out.values()
                    for c in r.get("committees", []) if c.get("notable"))
    if roles:
        print("\npositions beyond plain membership:")
        for k, v in roles.most_common(12):
            print(f"  {v:>4}  {k}")
    bad = [i for i, r in out.items() if not r.get("page_name")]
    if bad:
        print(f"\n{len(bad):,} pages gave no name at all. Senate pages are a "
              "different shape\nand have never been read; these are probably "
              "them. Run --probe on one\nand send the output:")
        for i in bad[:5]:
            print(f"  python3 fetch_members.py --probe {i}")
    print("\nPages are cached permanently, so --reparse re-applies a parser "
          "change\nwith no network at all.")


if __name__ == "__main__":
    main()
