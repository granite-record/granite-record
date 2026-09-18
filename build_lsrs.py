#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.1
"""
The 2027 bill requests, as a term the bill search can open.

    python3 build_lsrs.py --site site

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

WHAT THIS WRITES

  site/idx/2027-requests.json   the rows, in the shape idx/<term>.json uses,
                                so the bill search reads them with the code it
                                already has rather than a second path
  site/meta.json                one key merged in: "requests", which names the
                                term, its label and how many there are

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

import argparse
import json
import re
from pathlib import Path

TERM = "2027-requests"
LABEL = "2027 Bill Requests"

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
    return out


def rows_from(lsrs, who):
    rows, unmatched = [], []
    for r in lsrs:
        num = str(r.get("lsr") or "").strip()
        if not num:
            continue
        body = str(r.get("body") or "").upper()
        name = str(r.get("sponsor") or "").strip()
        hit = who.get(_fold(name))
        if name and not hit:
            unmatched.append(name)
        rows.append({
            "id": "LSR" + num.replace("-", ""),
            "n": "LSR " + num,
            "year": int(r.get("session") or 2027),
            "title": (r.get("title") or "").strip(),
            "sponsor": name,
            "sponsor_label": hit[0] if hit else name,
            "sponsor_slug": hit[1] if hit else "",
            "body": body,
            "body_label": BODY.get(body, body),
            "committee": "", "committees": [], "topic": "", "topic_by": "",
            # No status KIND: an LSR has not reached a stage the Status facet
            # names. The word on the card is the one fact there is about where
            # it stands.
            "kind": "",
            "status": "Withdrawn" if r.get("withdrawn") else "Filed as a request",
            "status_stated": True,
            "withdrawn": bool(r.get("withdrawn")),
            "term": TERM, "carried": False, "passage": "",
            "last_action": "", "nrc": 0, "votedays": [],
            "lsr": True,
        })
    rows.sort(key=lambda x: x["n"])
    return rows, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--src", default="lsrs.json")
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

    rows, unmatched = rows_from(lsrs, roster(site))
    assert rows, "no request survived shaping, though the source had some"
    idx = site / "idx"
    idx.mkdir(parents=True, exist_ok=True)
    (idx / f"{TERM}.json").write_text(json.dumps(rows, separators=(",", ":")),
                                      encoding="utf-8")

    mj = site / "meta.json"
    assert mj.exists(), ("meta.json is not written yet -- this step runs after "
                         "build_site_v2.py, which writes it")
    meta = json.loads(mj.read_text(encoding="utf-8"))
    meta["requests"] = {"term": TERM, "label": LABEL, "n": len(rows),
                        "withdrawn": sum(1 for r in rows if r["withdrawn"])}
    mj.write_text(json.dumps(meta), encoding="utf-8")

    by = {}
    for r in rows:
        by[r["body"]] = by.get(r["body"], 0) + 1
    kinds = ", ".join(f"{k} {n}" for k, n in sorted(by.items(), key=lambda x: -x[1]))
    print(f"  {len(rows)} bill requests for 2027 -> idx/{TERM}.json ({kinds})")
    print(f"  {meta['requests']['withdrawn']} withdrawn; "
          f"{sum(1 for r in rows if r['sponsor_slug'])} sponsors matched to a member")
    if unmatched:
        seen = sorted(set(unmatched))
        print(f"  {len(seen)} sponsor name(s) matched nobody on the roster: "
              + ", ".join(seen[:6]) + (" ..." if len(seen) > 6 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
