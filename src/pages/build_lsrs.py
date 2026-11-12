#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.11
"""
Next session's bill requests, as a term the bill search can open.

    python3 src/pages/build_lsrs.py --site site

WHAT AN LSR IS

Before a bill exists it is a Legislative Service Request: a member tells the
Office of Legislative Services what they want drafted, and the office gives it
a number like 2027-0001. It carries a title and a prime sponsor and nothing
else -- no text, no committee, no hearing, no number of its own -- until it is
drafted and filed, at which point it becomes HB 1234 and this site's ordinary
machinery picks it up. Some are withdrawn before that happens and never become
anything.

So this is the earliest public signal of what the next session will be about,
and it is the reason the person asked for it on 18 September: "viewing LSRs
that have been filed officially which are for next term and just have the
title and prime sponsor right now ... It should be replaced by the actual 2027
term bills once the full text is available and they've been officially filed,
and should be listed between All terms and the current term in the term
selector, and the 2025-2026 term (Current term) should be the default until
the bills for next term are fully available."

The default was settled the other way on 30 September: the site opens on
2027-2028 from its first bill, because the General Court publishes bills in
batches and the first arrives with others. That is what the newest-term rule
already does, so nothing holds 2025-2026 first.

WHAT THIS WRITES

  site/idx/<year>-requests.json the rows, in the shape idx/<term>.json uses,
                                so the bill search reads them with the code it
                                already has rather than a second path
  site/meta.json                one key merged in: "requests", which names the
                                term, its label, its year and how many there are

THE YEAR IS THE REQUESTS' OWN (18 October 2026). It was two literals, "2027-
requests" and "2027 Bill Requests", and app.js said "for 2027", so the requests
for 2028, filed from September 2027, would have been listed as 2027's. The
year is the newest session the requests name, and only that session's are
listed: by the time the next session's are filed, the older ones are bills or
withdrawn, and each bill is in its own term.

MERGING INTO meta.json, WHICH ANOTHER BUILDER OWNS

build_site_v2.py writes meta.json. This reads it and adds one key, the way
build_indexes.py appends to a sitemap.xml that build_bill_pages.py wrote --
the same pattern and the same requirement, which is that this step runs AFTER
the one that writes the file. build_all.py orders it; the assert below is what
catches the day somebody reorders them, because a silently missing key would
show as the option simply not being there.

The rows carry no committee, no topic and no status kind, because an LSR has
none of those. That is not missing data, and the facets are correct to show
nothing for this term.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re

def requests_term(year):
    """(the requests' term key, the term picker's label) for a session year:
    ("2027-requests", "2027 Bill Requests")."""
    return f"{year}-requests", f"{year} Bill Requests"


def session_of(r):
    """A request's session year as a number: its own, or its number's
    (2027-0001 is 2027's); None where it gives neither."""
    s = str(r.get("session") or "").strip()
    if s.isdigit():
        return int(s)
    m = LSR_NO.match(str(r.get("lsr") or "").strip())
    return int(m.group(1)) if m else None


def newest_session(lsrs):
    """(the newest session the requests name, that session's requests, how
    many of an older session were left out)."""
    years = [session_of(r) for r in lsrs]
    year = max((y for y in years if y), default=None)
    mine = [r for r, y in zip(lsrs, years) if y == year]
    return year, mine, len(lsrs) - len(mine)

# What the General Court's own search calls each body, spelled out. A reader
# who has not met these two-letter forms should not have to learn them to read
# a card.
BODY = {"HB": "House bill request", "SB": "Senate bill request",
        "CACR": "Constitutional amendment request",
        "HR": "House resolution request", "SR": "Senate resolution request",
        "HCR": "House concurrent resolution request",
        "SCR": "Senate concurrent resolution request",
        "HJR": "House joint resolution request",
        "SJR": "Senate joint resolution request"}


# A name folded to the letters in it, so that "Aboul-Hosn, Nadia" and
# "Nadia Aboul-Hosn" fold the same, and a middle initial on one side and not
# the other does not decide whether a sponsor gets their page.
def _fold(s):
    return re.sub(r"[^a-z]", "", str(s or "").lower())


def roster(site):
    """{folded name: (label, slug)} for the sitting members.

    The source names a sponsor "Ellen Read" and nothing more. The roster has
    her party, her seat and her page, and a request is filed by somebody
    sitting now, so the label the roster carries is the right one for it.
    A name that matches nothing is left as it was typed rather than guessed
    at -- a wrong member on a bill is the error this site fixes first.
    """
    p = site / "legislators.json"
    if not p.exists():
        return {}
    out = {}
    for m in json.loads(p.read_text(encoding="utf-8")):
        # "Abbas, Daryl" -- surname first, and there are no separate first and
        # last fields on the roster to read instead; every one of the 406 has
        # them as None. The LSR source writes "Daryl Abbas", so the comma is
        # what turns one into the other.
        name = (m.get("name") or "").strip()
        if "," not in name:
            continue
        last, first = (x.strip() for x in name.split(",", 1))
        if not (first and last):
            continue
        key = _fold(f"{first} {last}")
        # A name two sitting members share cannot be resolved from a name
        # alone, so neither gets the label rather than one of them getting
        # the other's.
        out[key] = None if key in out else (m.get("display") or m.get("name"),
                                            m.get("slug"))
    # AND THE NEW MEMBERS-ELECT, WHO HAVE A PROVISIONAL PAGE (Alice, 7 November
    # 2026; build_elect_pages.py): matched "by name only where certain" -- the
    # same folded name, the request's chamber theirs (the third field, which
    # rows_from holds a request to), and nobody else of the name, sitting,
    # former or elect. Anything less stays unlinked, as before.
    ep = site / "elect_pages.json"
    if ep.exists():
        fj = site / "former.json"
        gone = set()
        for m in (json.loads(fj.read_text(encoding="utf-8")) if fj.exists() else []):
            last, _, first = str(m.get("name") or "").partition(",")
            gone.add(_fold(f"{first} {last}"))
        for p in json.loads(ep.read_text(encoding="utf-8")).get("pages") or []:
            key = _fold(p.get("name"))
            party = f" ({p['party']})" if p.get("party") else ""
            out[key] = None if (key in out or key in gone) else (
                f"{p.get('name')}{party}", p.get("slug"), p.get("chamber"))
    return out


def chamber_of(body):
    """H or S for a request's kind (HB, SR, HCR ...); None for a
    constitutional amendment request, which either chamber may file."""
    b = str(body or "").upper()
    return None if b.startswith("CA") else (b[:1] if b[:1] in ("H", "S") else None)


LSR_NO = re.compile(r"^(\d{4})-(\d+)$")


def became_bills(bills, lsrs):
    """{request number: "HB 45"} for the requests that are bills now.

    A request that is drafted and introduced keeps its number as the bill's
    LSR: 2027-0001 becomes whatever bill carries LSR 2027-0001. fetch_lsrs
    marks a request that leaves its list withdrawn, because the list alone
    cannot tell a withdrawal from an introduction, and in December and
    January that would have put "Withdrawn" on every request introduced in
    that time. The bills can tell: data/bills.json is {term: {bill: record}},
    and a record's lsr_year and lsr_num are the request's year and number --
    matched as integers, the list padding "0001" where the bills write none.
    """
    want = set()
    for r in lsrs:
        m = LSR_NO.match(str(r.get("lsr") or "").strip())
        if m:
            want.add((m.group(1), int(m.group(2))))
    if not want:
        return {}
    have = {}
    for byb in (bills or {}).values():
        for bid, rec in byb.items():
            y, n = str(rec.get("lsr_year") or ""), str(rec.get("lsr_num") or "")
            if n.isdigit() and (y, int(n)) in want:
                have[(y, int(n))] = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid)
    return {f"{y}-{n:04d}": b for (y, n), b in have.items()}


def route(body):
    """The stops a request's bill will pass once it is introduced, in order,
    for its page's rail (Alice, 11 November 2026: the page is a bill's with
    the parts that do not exist yet left quiet): the chamber it starts in,
    then the other, the Governor and Law; a resolution of one chamber has
    that chamber and whether it is adopted; a concurrent resolution has two
    chambers and no Governor; a constitutional amendment goes to the voters,
    and its kind does not say which chamber it starts in, so none is named.
    These are build_site_v2.journey_rail's own routes, by the kind the
    request names."""
    b = str(body or "").upper()
    first = {"H": "House", "S": "Senate"}.get(b[:1])
    other = {"House": "Senate", "Senate": "House"}.get(first)
    if b.startswith("CA"):
        return ["Voters"]
    if not first:
        return []
    if b in ("HR", "SR"):
        return [first, "Adopted"]
    if b in ("HCR", "SCR"):
        return [first, other]
    return [first, other, "Governor", "Law"]


def rows_from(lsrs, who, became=None, year=None):
    """The rows of idx/<year>-requests.json and the sponsor names that matched
    nobody. `year` is the session they are listed under (newest_session)."""
    year = year or newest_session(lsrs)[0]
    term, _label = requests_term(year)
    rows, unmatched = [], []
    for r in lsrs:
        num = str(r.get("lsr") or "").strip()
        if not num:
            continue
        m = LSR_NO.match(num)
        bill = (became or {}).get(f"{m.group(1)}-{int(m.group(2)):04d}" if m else num, "")
        body = str(r.get("body") or "").upper()
        name = str(r.get("sponsor") or "").strip()
        hit = who.get(_fold(name))
        # A member-elect's match holds only for a request of their chamber.
        if hit and len(hit) > 2 and chamber_of(body) != hit[2]:
            hit = None
        if name and not hit:
            unmatched.append(name)
        # The co-sponsors, matched as the prime sponsor is (a name that
        # matches nobody is kept as the source gives it), for the request's
        # own page; a request with none carries no key.
        co = []
        for c in r.get("cosponsors") or []:
            c = str(c or "").strip()
            h = who.get(_fold(c))
            if h and len(h) > 2 and chamber_of(body) != h[2]:
                h = None
            if c:
                co.append({"label": h[0] if h else c, "slug": h[1] if h else ""})
        rows.append({
            "id": "LSR" + num.replace("-", ""),
            "n": "LSR " + num,
            "year": session_of(r) or year,
            "title": (r.get("title") or "").strip(),
            "sponsor": name,
            "sponsor_label": hit[0] if hit else name,
            "sponsor_slug": hit[1] if hit else "",
            **({"cosponsors": co} if co else {}),
            "body": body,
            "body_label": BODY.get(body, body),
            "committee": "", "committees": [], "topic": "", "topic_by": "",
            # No status KIND: an LSR has not reached a stage the Status facet
            # names. The word on the card is the one fact there is about where
            # it stands.
            "kind": "",
            "status": (f"Introduced as {bill}" if bill else
                       "Withdrawn" if r.get("withdrawn") else "Filed as a request"),
            "status_stated": True,
            "withdrawn": bool(r.get("withdrawn")) and not bill,
            "term": term, "carried": False, "passage": "",
            "last_action": "", "nrc": 0, "votedays": [],
            "lsr": True,
            **({"introduced": bill} if bill else {}),
            # "filed": the text is public (true, or its day) -- the stop Filed
            # on the request's rail. The list carries nothing of the kind
            # yet; this passes it on when the source gives it.
            **({"filed": r["filed"]} if r.get("filed") else {}),
            # A REQUEST'S OWN PAGE (Alice, 8 November 2026): its address, from
            # the number this source gives it -- New Hampshire's shape stays
            # here, and the page writer reads only "address" and "moved_to".
            "address": REQUEST_ADDRESS.format(num=num),
            # Once it is a bill, its address forwards to the bill's page.
            **({"moved_to": bill_address(bill, session_of(r) or year)} if bill else {}),
        })
    rows.sort(key=lambda x: x["n"])
    return rows, unmatched


# Where a request's page is: /request/2027-0001, as a bill's is
# /bill/2026/hb1034.
REQUEST_ADDRESS = "request/{num}"

# THE DAY FILING FOR A SESSION IS COMPLETE, by the session's year, entered by
# a person when the General Court's list stops growing (Alice, 8 November
# 2026: "the remaining request pages retire, each forwarding to its prime
# sponsor's page"). Until it is entered, no request page retires.
FILING_COMPLETE = {}


def bill_address(bill, year):
    """'HB 45' of 2027 -> 'bill/2027/hb45', the bill's own page."""
    return f"bill/{year}/{str(bill).replace(' ', '').lower()}"


def retire(rows, year, today):
    """From the day filing is complete (FILING_COMPLETE), each request still
    a request -- not a bill and not withdrawn -- forwards to its prime
    sponsor's page, or to the requests' list where the sponsor has none. A
    withdrawn request keeps its page, as a withdrawn bill does."""
    done = FILING_COMPLETE.get(int(year)) if year else None
    if not done or today < done:
        return 0
    n = 0
    for r in rows:
        if not r.get("moved_to") and not r.get("withdrawn"):
            r["moved_to"] = (f"legislator/{r['sponsor_slug']}" if r.get("sponsor_slug")
                             else f"bills?term={r['term']}")
            n += 1
    return n


def not_returning(site):
    """({slug: why}, {slug: why not decided}) for the sitting members, from
    the 2026 election's results (site/members_elect.json, build_members_elect).

    Alice, 12 November 2026: "Bills that were requested by members before the
    election but the members lost reelection can be removed without being
    labeled as withdrawn." After an election the General Court drops the
    requests of members who are not coming back, and the list alone cannot
    say why a request left it.

    BY IDENTITY, NEVER BY NAME. A sitting member is not returning when their
    own race is decided (nothing not_final, nothing held) and their slug is
    not among the slugs of that election's winners (each elected entry of a
    sitting member carries "s"). Lost, retired, or ran for another office:
    the file does not say which and the rule does not need it. A name check
    flags 169 standing requests falsely (nicknames, spellings), so none is
    made here. A member whose race is not decided, or is in no race the file
    lists, is not decided: the second dict, and their requests are left as
    they are."""
    ep, lp = site / "members_elect.json", site / "legislators.json"
    if not (ep.exists() and lp.exists()):
        return {}, {}
    races = (json.loads(ep.read_text(encoding="utf-8")).get("races")) or {}
    won = {e.get("s") for r in races.values() for e in r.get("elected") or []
           if e.get("s")}
    gone, open_ = {}, {}
    for m in json.loads(lp.read_text(encoding="utf-8")):
        slug = m.get("slug")
        if not slug or slug in won:
            continue
        key = (f"H|{m.get('county')}|{m.get('district')}" if m.get("chamber") == "H"
               else f"S|{m.get('district')}")
        race = races.get(key)
        if race is None:
            open_[slug] = f"no race {key} in members_elect.json"
        elif race.get("not_final") or race.get("held"):
            open_[slug] = f"race {key} is not final"
        else:
            gone[slug] = f"not among the winners of {key}"
    return gone, open_


def drop_unreturned(rows, gone):
    """(kept rows, the rows dropped): a request that left the General Court's
    list (withdrawn, and not a bill) whose prime sponsor, identified by slug,
    is not returning is dropped -- no page, not counted, forwarded to the
    requests' list by build_pages.moved_requests. A request still on the
    list is never dropped, whatever its sponsor, and a withdrawn request of a
    returning member, or of a sponsor with no slug, is left as it is."""
    kept, dropped = [], []
    for r in rows:
        slug = r.get("sponsor_slug")
        (dropped if r.get("withdrawn") and slug and slug in gone else kept).append(r)
    return kept, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--src", default="lsrs.json")
    ap.add_argument("--bills", default="data/bills.json",
                    help="the bills, to tell a request that became one from a withdrawal")
    a = ap.parse_args()
    site, src = Path(a.site), Path(a.src)

    if not src.exists():
        print(f"  no {src} -- nothing to build. Run fetch_lsrs.py first.")
        return 0
    lsrs = json.loads(src.read_text(encoding="utf-8"))
    # SILENCE IS NOT SUCCESS. A source file that parsed to an empty list would
    # otherwise write an empty term, and the option would appear in the picker
    # naming nothing.
    assert isinstance(lsrs, list) and lsrs, f"{src} holds no requests"
    year, lsrs, older = newest_session(lsrs)
    assert year and lsrs, f"{src} names no session a request can be listed under"
    term, label = requests_term(year)

    bp = Path(a.bills)
    became = became_bills(json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {},
                          lsrs)
    rows, unmatched = rows_from(lsrs, roster(site), became, year)
    assert rows, "no request survived shaping, though the source had some"
    gone, undecided = not_returning(site)
    rows, dropped = drop_unreturned(rows, gone)
    assert rows, "every request was dropped as a not-returning member's"
    import build_date
    retired = retire(rows, year, build_date.today().isoformat())
    idx = site / "idx"
    idx.mkdir(parents=True, exist_ok=True)
    # The previous session's file, if this is the night a new session's
    # requests replace it: meta.json names only the one written below, and a
    # file it does not name is one nothing links.
    for old in idx.glob("*-requests.json"):
        if old.name != f"{term}.json":
            old.unlink()
    (idx / f"{term}.json").write_text(json.dumps(rows, separators=(",", ":")),
                                      encoding="utf-8")

    mj = site / "meta.json"
    assert mj.exists(), ("meta.json is not written yet -- this step runs after "
                         "build_site_v2.py, which writes it")
    meta = json.loads(mj.read_text(encoding="utf-8"))
    # by_slug: each matched sponsor's slug and how many requests are theirs,
    # so a member's page knows to offer the requests term, and opens on it,
    # without asking for the list first (Alice, 7 November 2026).
    by_slug = {}
    for r in rows:
        if r["sponsor_slug"]:
            by_slug[r["sponsor_slug"]] = by_slug.get(r["sponsor_slug"], 0) + 1
    meta["requests"] = {"term": term, "label": label, "year": year, "n": len(rows),
                        "withdrawn": sum(1 for r in rows if r["withdrawn"]),
                        "dropped": sorted(r["address"] for r in dropped),
                        "by_slug": dict(sorted(by_slug.items()))}
    mj.write_text(json.dumps(meta), encoding="utf-8")

    by = {}
    for r in rows:
        by[r["body"]] = by.get(r["body"], 0) + 1
    kinds = ", ".join(f"{k} {n}" for k, n in sorted(by.items(), key=lambda x: -x[1]))
    print(f"  {len(rows)} bill requests for {year} -> idx/{term}.json ({kinds})")
    if older:
        print(f"  {older} request(s) of an earlier session left out: bills or withdrawn by now")
    print(f"  {meta['requests']['withdrawn']} withdrawn; "
          f"{sum(1 for r in rows if r['sponsor_slug'])} sponsors matched to a member")
    if dropped:
        print(f"  {len(dropped)} withdrawn request(s) of members not returning dropped, "
              "forwarding to the list: " + ", ".join(r["n"] for r in dropped))
    stuck = [r["n"] for r in rows if r["withdrawn"] and not r["sponsor_slug"]]
    stuck += [r["n"] for r in rows if r["withdrawn"] and r["sponsor_slug"] in undecided]
    if stuck:
        print(f"  {len(stuck)} withdrawn request(s) kept, the sponsor not identified or "
              "their race not decided: " + ", ".join(stuck))
    if became:
        print(f"  {len(became)} introduced as bills, each marked with its bill, its page "
              "forwarding to the bill's")
    if retired:
        print(f"  filing is complete: {retired} request page(s) retired, each forwarding to "
              "its prime sponsor's page")
    if unmatched:
        seen = sorted(set(unmatched))
        print(f"  {len(seen)} sponsor name(s) matched nobody on the roster: "
              + ", ".join(seen[:6]) + (" ..." if len(seen) > 6 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
