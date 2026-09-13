#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-13.1
"""
What a search engine is told a page is about, in schema.org's vocabulary.

    import structured as LD
    shell.page(..., jsonld=LD.bill(b, d, base, path))

WHY

Until 13 September no page on the site carried structured data at all, and
shell.page()'s jsonld parameter could not have: it interpolated a name, NL,
that was never defined, so the first caller would have raised. A bill page
told a crawler about 137 words of prose and nothing about what kind of thing
it was.

WHAT IS SAID, AND WHAT IS NOT

Only what the page itself shows and the record states: a bill's number, title,
kind, term, sponsors and its page; a legislator's name, office, chamber, party
and district; a committee's name and chamber. Every object carries the page's
own canonical address.

Deliberately NOT said:
  - a legislator's email or telephone. The page draws them for a reader, and
    the person who runs the site wants the addresses kept away from scrapers;
    structured data is the one place a scraper reads without trying.
  - anything the site infers: no topic the site guessed, no "passed" or
    "failed" beyond the status the record gives, no ratings, no counts
    presented as judgements.
  - legislationPassedBy / legislationLegalForce, which assert legal effect the
    site does not have the standing to assert.

Every function returns a dict; shell.page() serialises it safely.
"""

JURISDICTION = "US-NH"
LEGISLATURE = {"@type": "GovernmentOrganization", "name": "New Hampshire General Court",
               "url": "https://gc.nh.gov/"}
CHAMBER = {"H": {"@type": "GovernmentOrganization", "name": "New Hampshire House of Representatives",
                 "parentOrganization": LEGISLATURE},
           "S": {"@type": "GovernmentOrganization", "name": "New Hampshire Senate",
                 "parentOrganization": LEGISLATURE}}
KINDS = {"HB": "bill", "SB": "bill", "CACR": "constitutional amendment",
         "HCR": "concurrent resolution", "SCR": "concurrent resolution",
         "HJR": "joint resolution", "SJR": "joint resolution",
         "HR": "resolution", "SR": "resolution", "PET": "petition"}


def _crumbs(base, trail):
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": base + url}
        for i, (name, url) in enumerate(trail, 1)]}


def bill(b, d, base, canon_path):
    """A bill's page. b is its index row, d its record."""
    import re
    bid = b["id"]
    m = re.match(r"[A-Z]+", bid)
    prefix = m.group(0) if m else ""
    url = base + canon_path
    obj = {"@type": "Legislation",
           "@id": url,
           "url": url,
           "name": f"{b.get('n') or bid} ({b.get('year')}): {(b.get('title') or '').strip()}".strip(": "),
           "legislationIdentifier": b.get("n") or bid,
           "legislationJurisdiction": JURISDICTION,
           "legislationType": KINDS.get(prefix, "bill"),
           "isPartOf": {"@type": "CreativeWorkSeries",
                        "name": f"New Hampshire General Court, {b.get('term')} term"},
           "publisher": LEGISLATURE}
    sponsors = [s.get("label") or s.get("name") for s in (d.get("sponsors") or [])
                if s.get("label") or s.get("name")]
    if sponsors:
        obj["sponsor"] = [{"@type": "Person", "name": n} for n in sponsors[:20]]
    return [obj, _crumbs(base, [("Granite Record", "/"), ("Bills", "/bills"),
                                (f"{b.get('term')}", f"/directory/bills-{b.get('term')}"),
                                (b.get("n") or bid, canon_path)])]


def person(m, base, canon_path):
    """A sitting legislator's page. No email, no telephone -- see the docstring."""
    chamber = (m.get("chamber") or "H")[:1]
    url = base + canon_path
    office = "State Senator" if chamber == "S" else "State Representative"
    district = (f"Senate District {m.get('district')}" if chamber == "S"
                else f"{m.get('county') or ''} {m.get('district') or ''}".strip())
    obj = {"@type": "Person", "@id": url, "url": url,
           "name": m.get("display_plain") or m.get("name") or "",
           "jobTitle": office,
           "memberOf": {**CHAMBER[chamber], "roleName": district} if district else CHAMBER[chamber]}
    if m.get("party"):
        obj["affiliation"] = {"@type": "Organization", "name": f"{m['party']} Party"
                              if not str(m["party"]).lower().endswith("party") else m["party"]}
    return [obj, _crumbs(base, [("Granite Record", "/"), ("Legislators", "/legislators"),
                                (obj["name"], canon_path)])]


def committee(code, name, base, canon_path):
    chamber = (code or "H")[:1].upper()
    url = base + canon_path
    word = "Senate" if chamber == "S" else "House"
    obj = {"@type": "GovernmentOrganization", "@id": url, "url": url,
           "name": f"New Hampshire {word} Committee on {name}" if not name.lower().startswith(("committee", "special")) else f"New Hampshire {word} {name}",
           "parentOrganization": CHAMBER.get(chamber, LEGISLATURE)}
    return [obj, _crumbs(base, [("Granite Record", "/"), ("Committees", "/committees"),
                                (name, canon_path)])]


def listing(name, description, base, canon_path):
    """An index page: a collection, not an article."""
    url = base + canon_path
    return [{"@type": "CollectionPage", "@id": url, "url": url, "name": name,
             "description": description, "isPartOf": {"@type": "WebSite", "name": "Granite Record",
                                                      "url": base + "/"}}]
