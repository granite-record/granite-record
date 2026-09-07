#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-07.7
"""
A page's worth of data for every committee.

    python3 build_committees.py --site site --data data

WHAT A COMMITTEE PAGE ANSWERS

Bill-first search answers "what happened to HB 1442". This answers "what did
Legislative Administration do on 3 March", which is the question a reporter or
a member of that committee actually asks, and the site could not answer it at
all.

WHERE EACH PART COMES FROM

  identity, leadership, room   committees.json          fetch_committees.py
  who sits on it               data/committee_members.json
                                                        fetch_committee_members_db.py
  bills referred               site/index.json          the search index
  what happened on a day       proceedings.csv          one row per
                                                        (bill, date, kind, recording)
  what the committee decided   committee_reports.json, senate_reports.json

The web pages give the chair and the room and not the House rosters; the
database gives both chambers' rosters and no leadership. Neither alone is a
committee page.

THE DAY NARRATIVE

Composed from proceedings.csv rather than written, in the same spirit as the
bill narratives: every clause is a row somebody can check. A day reads

    The Committee on Education met on January 28, 2026 for public hearings on
    HB1123, HB319 and HB722. It also held an executive session on HB1142, and
    recommended that the House find it inexpedient to legislate, 12-2.

and the recommendation half only appears when committee_reports.json has one
for that bill. A committee that met and whose report is not on file gets the
first sentence and nothing more, which is the honest outcome.

Writes site/committees.json and site/committee/<code>.json. It writes no HTML:
the page is app.js with one committee open, the same way a bill's page is.
"""

import argparse
import collections
import json
import re
from pathlib import Path

import proceedings as P
import shell as S

# The kinds proceedings.csv records, in the order a committee day runs, with
# the plural the narrative needs.
KIND_ORDER = ["public hearing", "hearing", "executive session",
              "full committee work session", "subcommittee work session",
              "work session", "committee of conference"]
PLURAL = {
    "public hearing": "public hearings",
    "hearing": "hearings",
    "executive session": "executive sessions",
    "full committee work session": "full committee work sessions",
    "subcommittee work session": "subcommittee work sessions",
    "work session": "work sessions",
    "committee of conference": "committees of conference",
}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


def fdate(d):
    if not d or len(d) < 10:
        return d or ""
    try:
        return f"{MONTHS[int(d[5:7]) - 1]} {int(d[8:10])}, {d[:4]}"
    except (ValueError, IndexError):
        return d


def andlist(xs):
    xs = list(xs)
    if not xs:
        return ""
    if len(xs) == 1:
        return xs[0]
    return ", ".join(xs[:-1]) + " and " + xs[-1]


def spaced(bill):
    """HB1123 as "HB 1123", the way the site writes a bill number."""
    m = re.match(r"^([A-Z]+)\s*(\d+.*)$", (bill or "").upper())
    return f"{m.group(1)} {m.group(2)}" if m else (bill or "")


def recommendation(reports, term, bill, committee=""):
    """What THIS committee recommended, and the vote, if it is on file.

    The committee name is not optional. A bill is reported by a House
    committee and then, if it passes, by a Senate one; several bills are also
    re-referred and reported twice by different committees of the same
    chamber. Taking the first report on file gave a committee another
    committee's recommendation -- 8 executive sessions of the current term,
    including one where a House committee was credited with a decision made
    across the building.

    Where no report on file is this committee's, nothing is said. A sitting
    day with a hearing and no attributable report is the ordinary case, and
    silence is the honest form of it.
    """
    want = (committee or "").strip().lower()
    for rec in (reports.get(term, {}) or {}).get(bill, []) or []:
        maj = (rec.get("majority_recommendation") or "").strip()
        if not maj:
            continue
        if want:
            said = [(r.get("committee") or "").strip().lower()
                    for r in rec.get("reports") or []]
            if said and want not in said:
                continue
        vote = ""
        for r in rec.get("reports") or []:
            if (r.get("side") or "").lower().startswith(("majority", "committee")):
                y, n = r.get("vote_yeas"), r.get("vote_nays")
                if y is not None and n is not None:
                    vote = f"{y}–{n}"
                break
        return maj.lower(), (rec.get("minority_recommendation") or "").strip().lower(), vote
    return "", "", ""


def narrate(name, chamber, date, items, reports):
    """One committee day, in sentences, from the rows themselves."""
    by_kind = collections.defaultdict(list)
    for it in items:
        by_kind[it["kind"]].append(it)
    kinds = [k for k in KIND_ORDER if k in by_kind] + \
            [k for k in by_kind if k not in KIND_ORDER]
    if not kinds:
        return ""

    who = f"The Committee on {name}" if not name.lower().startswith("committee") \
        else name
    out = []
    first = kinds[0]
    bills = andlist(spaced(i["n"] or i["bill"]) for i in by_kind[first])
    noun = PLURAL[first] if len(by_kind[first]) > 1 and first in PLURAL else first
    out.append(f"{who} met on {fdate(date)} for {noun} on {bills}.")

    for k in kinds[1:]:
        bs = andlist(spaced(i["n"] or i["bill"]) for i in by_kind[k])
        noun = PLURAL[k] if len(by_kind[k]) > 1 and k in PLURAL else k
        out.append(f"It also held {'an' if noun[0] in 'aeiou' else 'a'} "
                   f"{noun} on {bs}." if len(by_kind[k]) == 1
                   else f"It also held {noun} on {bs}.")

    # What it decided, where a report says so. Only executive sessions produce
    # a recommendation, and only some of those have a report on file yet.
    said = []
    for it in by_kind.get("executive session", []):
        maj, minor, vote = recommendation(reports, it["term"], it["bill"], name)
        if not maj:
            continue
        body = "House" if chamber == "H" else "Senate"
        bit = (f"On {spaced(it['n'] or it['bill'])} it recommended that the "
               f"{body} find it {maj}" if maj.startswith("inexpedient")
               else f"On {spaced(it['n'] or it['bill'])} it recommended "
                    f"{maj}")
        if vote:
            bit += f", {vote}"
        if minor and minor != maj:
            bit += f", with a minority recommending {minor}"
        said.append(bit + ".")
    out += said
    return " ".join(out)


def load(p, default):
    f = Path(p)
    if not f.exists():
        return default
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--data", default="data")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site, data = Path(a.site), Path(a.data)

    idx = load(site / "index.json", [])
    if not idx:
        raise SystemExit(f"{site}/index.json is not there. Run build_site_v2 "
                         "first -- the bills a committee heard come from it.")
    web = load("committees.json", {})
    seats = load(data / "committee_members.json", {})
    codes = load(data / "committees.json", {})
    # Both files, CONCATENATED per bill rather than one shadowing the other.
    # setdefault kept only the first: a bill reported by a House committee and
    # then by a Senate one -- which is most bills that pass a chamber -- lost
    # the Senate's report entirely, so a Senate committee narrating its own
    # executive session had nothing of its own to quote and quoted the House's.
    reports = {}
    for src in (load("committee_reports.json", {}), load("senate_reports.json", {})):
        for t, byb in src.items():
            for b, v in byb.items():
                reports.setdefault(t, {}).setdefault(b, []).extend(
                    v if isinstance(v, list) else [v])
    legs = {str(m.get("id")): m for m in load(site / "legislators.json", [])}

    # (chamber, name) -> code. NOT name alone: both chambers have a
    # Judiciary, a Finance and a Ways and Means, so a name-only map silently
    # gave one chamber's committee the other's roster and sitting days -- the
    # same confusion as a bill number across two terms, in a different file.
    #
    # The code carries the chamber: H05 is a House committee, S30 a Senate
    # one, and that is the only place the chamber is stated for a House
    # committee, whose page does not say.
    by_name = {}
    for code, rec in codes.items():
        nm = (rec.get("name") or "").strip().lower()
        ch = code[:1].upper() if code else ""
        if nm and ch in ("H", "S"):
            by_name[(ch, nm)] = code

    def code_of(name, chamber):
        """The committee a name means, in the chamber that named it."""
        nm = (name or "").strip().lower()
        ch = (chamber or "").strip().upper()[:1]
        if not nm:
            return None
        # The search index writes "Senate Judiciary" and "House Finance";
        # proceedings.csv writes the bare name and carries the chamber in its
        # own column. Both forms end up here.
        for pre, c in (("house ", "H"), ("senate ", "S")):
            if nm.startswith(pre):
                nm, ch = nm[len(pre):], c
                break
        return by_name.get((ch, nm))
    # The web file carries the chamber and the leadership.
    lead = {}
    for chamber, rows in (web.items() if isinstance(web, dict) else []):
        for c in rows:
            code = code_of(c.get("name"), chamber)
            if code:
                lead[code] = {**c, "chamber": chamber}

    # ---- what each committee heard, day by day --------------------------
    days = collections.defaultdict(lambda: collections.defaultdict(list))
    bill_meta = {(b.get("term"), b.get("id")): b for b in idx}

    _station_cache = {}

    def station_of(year, bill, date, kind):
        """The bill page's own station for this proceeding, or None.

        One source for a proceeding's start, because two sources disagreed by
        four hours and neither page said which was which.
        """
        key = (year, bill)
        if key not in _station_cache:
            f = site / "bills" / str(year) / f"{bill}.json"
            try:
                _station_cache[key] = json.loads(
                    f.read_text(encoding="utf-8")).get("stations") or []
            except (OSError, ValueError):
                _station_cache[key] = []
        want = (kind or "").strip().lower()
        for st in _station_cache[key]:
            if st.get("when") != date:
                continue
            if want and want not in (st.get("what") or "").strip().lower():
                continue
            return st
        return None
    unmatched = collections.Counter()
    for r in P.load():
        cname = (r.get("committee") or "").strip()
        if not cname or not r.get("date"):
            continue
        code = code_of(cname, r.get("body"))
        if not code:
            unmatched[f"{r.get('body') or '?'} {cname}"] += 1
            continue
        meta = bill_meta.get((r.get("term"), r.get("bill"))) or {}
        st = station_of(meta.get("year", ""), r.get("bill"), r.get("date"),
                        r.get("kind"))
        days[code][(r.get("term"), r.get("date"))].append({
            "bill": r.get("bill"), "n": meta.get("n") or spaced(r.get("bill")),
            "title": meta.get("title", ""), "year": meta.get("year", ""),
            "term": r.get("term"), "kind": r.get("kind"),
            "video_id": (st or {}).get("video_id") or r.get("video_id") or "",
            # From the bill's own station, so the two pages agree by
            # construction. None where the bill has no station for that day:
            # no time is true, and the schedule guess was out by hours.
            "start": (st or {}).get("start"),
            "end": (st or {}).get("end"),
            # What the bill page says about how the start was arrived at, so
            # this page can say the same thing rather than imply certainty.
            "state": (st or {}).get("state") or "",
            "time": r.get("time") or "", "venue": r.get("venue") or "",
        })

    # ---- bills referred, per term ---------------------------------------
    referred = collections.defaultdict(lambda: collections.defaultdict(list))
    for b in idx:
        for nm in (b.get("committees") or ([b.get("committee")]
                                           if b.get("committee") else [])):
            # The chamber is in the name here -- "Senate Judiciary" -- so
            # code_of takes it from the prefix.
            code = code_of(nm, "")
            if code:
                referred[code][b.get("term")].append({
                    "id": b.get("id"), "n": b.get("n"), "year": b.get("year"),
                    "title": b.get("title", ""), "status": b.get("status", ""),
                    "kind": b.get("kind", ""), "term": b.get("term"),
                })

    out = site / "committee"
    out.mkdir(parents=True, exist_ok=True)
    t = S.template(site)
    index, written, urls, skipped = [], 0, [], []

    # H29 is "No Committee Assignment" -- the code the General Court files a
    # bill under when it has no committee. It is not a committee and must not
    # have a page; it had one, with two bills on it and no way in, because the
    # index only lists a chamber it can name and H29 has none.
    NOT_A_COMMITTEE = {"no committee assignment"}
    for code in sorted(set(list(seats) + list(referred) + list(days))):
        info = lead.get(code, {})
        name = (info.get("name") or (codes.get(code) or {}).get("name") or "")
        # A code with no name is not a committee this site can present. Five
        # of them -- H13, H14, H39, H40, H41 -- are in the database's
        # CommitteeMembers and in no other source: no name, no bills, no
        # sitting day, and pages titled "The House Committee on H13".
        if not name or name.strip().lower() in NOT_A_COMMITTEE:
            skipped.append(f"{code}" + (f" ({name})" if name else " (unnamed)"))
            continue
        # The code carries the chamber where nothing else states it.
        chamber = (info.get("chamber")
                   or (seats.get(code) or [{}])[0].get("chamber")
                   or (code[:1].upper() if code[:1].upper() in "HS" else ""))
        members = []
        for m in seats.get(code, []):
            lg = legs.get(m["id"]) or {}
            members.append({**m,
                            "slug": lg.get("slug", ""),
                            "label": lg.get("display_full") or m["name"],
                            "county": lg.get("county", "")})
        # Leadership comes from the web pages, which name a person rather than
        # an id, so it is matched on the name the roster prints.
        for m in members:
            plain = m["name"].split(",")
            plain = f"{plain[1].strip()} {plain[0].strip()}" if len(plain) > 1 \
                else m["name"]
            if info.get("chair") and plain == info["chair"]:
                m["role"] = "Chair"
            elif info.get("vice_chair") and plain == info["vice_chair"]:
                m["role"] = "Vice Chair"
            else:
                m.setdefault("role", "Member")

        sessions = []
        for (term, date), items in sorted(days.get(code, {}).items(),
                                          key=lambda kv: (kv[0][1] or ""),
                                          reverse=True):
            items.sort(key=lambda i: (i["start"] if i["start"] is not None
                                      else 1e9))
            sessions.append({
                "date": date, "term": term,
                "video_id": next((i["video_id"] for i in items
                                  if i["video_id"]), ""),
                "narrative": narrate(name, chamber, date, items, reports),
                "items": items,
            })

        rec = {
            "code": code, "name": name, "chamber": chamber,
            "chair": info.get("chair", ""), "vice_chair": info.get("vice_chair", ""),
            "aide": info.get("aide", ""), "room": info.get("room", ""),
            "phone": info.get("phone", ""), "url": info.get("url", ""),
            "members": members,
            "bills": {t: sorted(v, key=lambda b: b["id"])
                      for t, v in referred.get(code, {}).items()},
            "sessions": sessions,
        }
        (out / f"{code}.json").write_text(json.dumps(rec), encoding="utf-8")

        # The page, which is bills.html with this committee open. Same shell
        # as a bill's and a member's, from shell.py, so the three cannot drift.
        chamber_word = "Senate" if chamber == "S" else "House"
        towns = f"{len(rec['members'])} members"
        desc = (f"The {chamber_word} Committee on {name}. "
                f"{towns}, {sum(len(v) for v in rec['bills'].values()):,} bills "
                f"referred and {len(sessions):,} sitting days, each with what "
                "was taken up and when. From the New Hampshire General Court's "
                "own records.")
        nos = ('<noscript><div class="wrap" style="max-width:70ch;'
               'padding:26px 20px">'
               f"<h1>{S.E(name)}</h1><p>The {chamber_word} Committee on "
               f"{S.E(name)}"
               + (f", chaired by {S.E(rec['chair'])}" if rec["chair"] else "")
               + ".</p><p>This page draws the committee's bills and sitting "
                 "days in the browser, so it needs JavaScript. Everything it "
                 "shows comes from the file linked below, which needs none.</p>"
                 f'<ul><li><a href="/committee/{S.E(code)}.json">this page\'s '
                 "data as JSON</a></li>"
               + (f'<li><a href="{S.E(rec["url"])}" rel="noopener">this '
                  "committee on gencourt</a></li>" if rec.get("url") else "")
               + '</ul><p><a href="/bills.html">All bills</a></p></div></noscript>')
        path = f"/committee/{code}.html"
        (out / f"{code}.html").write_text(S.page(
            t, path=path, base=a.base,
            title=f"{name} — {chamber_word} committee | Granite Record",
            og_title=f"{name} — New Hampshire {chamber_word}",
            description=desc,
            globals={"GR_COMMITTEE": code, "GR_STANDALONE": True},
            noscript=nos, skip_label="Skip to this committee"),
            encoding="utf-8")
        urls.append(f"{a.base}{path}")
        written += 1
        index.append({
            "code": code, "name": name, "chamber": chamber,
            "chair": rec["chair"], "n_members": len(members),
            "n_bills": sum(len(v) for v in rec["bills"].values()),
            "n_sessions": len(sessions),
            "terms": sorted(rec["bills"]),
        })

    (site / "committees.json").write_text(json.dumps(index), encoding="utf-8")

    # The way in. Committee pages were built, sitemapped and unreachable: no
    # link to one existed anywhere on the site.
    def _card(c):
        bits = []
        if c["chair"]:
            bits.append(f"Chaired by {S.E(c['chair'])}")
        if c["n_members"]:
            bits.append(f"{c['n_members']} member"
                        + ("" if c["n_members"] == 1 else "s"))
        if c["n_bills"]:
            bits.append(f"{c['n_bills']:,} bill"
                        + ("" if c["n_bills"] == 1 else "s"))
        if c["n_sessions"]:
            bits.append(f"{c['n_sessions']:,} sitting day"
                        + ("" if c["n_sessions"] == 1 else "s"))
        return (f'<a class="ccard" href="committee/{S.E(c["code"])}.html">'
                f'<span class="cc-n">{S.E(c["name"])}</span>'
                f'<span class="cc-m">{" &middot; ".join(bits)}</span></a>')

    live = [c for c in index if c["n_sessions"] or c["n_bills"]]
    past = [c for c in index if c not in live]
    body = []
    for ch, word in (("H", "House"), ("S", "Senate")):
        rows_ = [c for c in live if c["chamber"] == ch]
        if not rows_:
            continue
        body.append(f"<h2>{word}</h2><div class=\"ccards\">"
                    + "".join(_card(c) for c in
                              sorted(rows_, key=lambda x: x["name"]))
                    + "</div>")
    if past:
        body.append('<h2>No longer meeting</h2><p class="src">Committees with '
                    "no bills and no sitting day on record. Their pages are "
                    "kept so the bills they once handled still have somewhere "
                    'to point.</p><div class="ccards">'
                    + "".join(_card(c) for c in
                              sorted(past, key=lambda x: x["name"]))
                    + "</div>")

    page_html = S.page(
        S.template(site), path="/committees.html", base=a.base,
        title="Committees | Granite Record",
        og_title="New Hampshire General Court committees",
        description=("Every committee of the New Hampshire General Court: who "
                     "sits on it, the bills referred to it, and what it did on "
                     "each day it met."),
        globals={"GR_STATIC": True},
        noscript="", skip_label="Skip to the committees")
    # A plain listing rather than an app view: there is nothing to filter and
    # 56 links do not need JavaScript to draw.
    page_html = page_html.replace(
        '<div id="results"></div>',
        f'<div id="results"><div class="clist"><h1>Committees</h1>'
        f'<p class="src">Bill-first search answers what happened to a bill. '
        f'These answer what a committee did on a day.</p>'
        + "".join(body) + "</div></div>", 1)
    (site / "committees.html").write_text(page_html, encoding="utf-8")
    print("committees.html written")

    assert written, ("no committee page was written. That means no committee "
                     "name in proceedings.csv matched data/committees.json, "
                     "which is a parse problem rather than an empty session.")
    # sitemap.xml is written by build_bill_pages.py, which runs first.
    # Appended rather than replaced: rewriting it here would drop every other
    # URL on the site.
    sm = site / "sitemap.xml"
    if sm.exists():
        text = sm.read_text(encoding="utf-8")
        add = "".join(f"<url><loc>{S.E(u)}</loc></url>\n" for u in urls
                      if S.E(u) not in text)
        if add:
            sm.write_text(text.replace("</urlset>", add + "</urlset>"),
                          encoding="utf-8")
            print(f"{len(add.splitlines())} added to sitemap.xml")

    print(f"{written} committees -> {out}/")
    if skipped:
        print(f"  {len(skipped)} code(s) skipped as not a nameable committee: "
              + ", ".join(skipped))
    print(f"  {sum(i['n_members'] for i in index):,} seats, "
          f"{sum(i['n_bills'] for i in index):,} bill referrals, "
          f"{sum(i['n_sessions'] for i in index):,} sitting days")
    lead_n = sum(1 for i in index if i["chair"])
    print(f"  {lead_n} of {written} have a chair on file")
    if unmatched:
        print(f"  {len(unmatched)} committee name(s) in proceedings.csv match "
              "nothing in data/committees.json:")
        for nm, n in unmatched.most_common(6):
            print(f"    {nm!r} on {n:,} rows")
    empty = [i["code"] for i in index if not i["n_sessions"]]
    if empty:
        print(f"  {len(empty)} committee(s) have no sitting day on record: "
              + ", ".join(empty[:8]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
