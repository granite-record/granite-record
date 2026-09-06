#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.2
"""
Turn the General Court's bulk files into the data the site runs on.

Schemas below were established by running probe_schema.py against the real
files rather than guessed, which matters -- earlier guesses about these were
wrong about a third of the time.

    legislators.txt      id | last | first | middle | body | seat | countyCode |
                         district | party | mailLabel | street | city | state |
                         zip | email
    HouseDistricts.txt   countyCode | district | ward | town
    Counties.txt         code | name | abbreviation
    SubjectCodes.txt     id | code | name
    Committees.txt       code | name | abbreviation
    LsrSponsors.txt      year | lsr | sequence | memberId | flag
    LSRs.txt             39 fields; 0 year, 1 lsr, 2 title, 3 body, 9 padded
                         bill, 10 bill, 12 subjectCode, 13/14 house committee,
                         21/22 senate committee, 31 hearing datetime, 32 room
    RollCallHistory.txt  year | body | voteNumber | recordId | memberId | -- |
                         vote | timestamp
    RollCallSummary.txt  year | body | number | datetime | bill | yea | nay |
                         ... | question | title

RollCallHistory already contains every member's vote, so no page scraping is
needed. fetch_rollcall_details.py is obsolete.

    python3 build_data.py --dir . --out data

Standard library only.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PARTY = {"R": "Republican", "D": "Democrat", "I": "Independent", "L": "Libertarian"}


def rows(path, expect=None):
    p = Path(path)
    if not p.exists():
        print(f"  missing: {p.name}")
        return []
    out = []
    with open(p, encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            f = line.split("|")
            if expect and len(f) != expect:
                continue
            out.append([x.strip() for x in f])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=".")
    ap.add_argument("--out", default="data")
    a = ap.parse_args()
    d, out = Path(a.dir), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    report = []

    # ---------------------------------------------------------- counties ---
    counties = {}
    for r in rows(d / "Counties.txt", 3):
        counties[r[0]] = {"name": r[1], "abbr": r[2].rstrip(".")}
    print(f"counties: {len(counties)}")

    # ------------------------------------------------------- legislators ---
    legs = {}
    bad_party = Counter()
    for r in rows(d / "legislators.txt", 15):
        pcode = (r[8] or "").upper()
        if r[8] and r[8] != pcode:
            bad_party[r[8]] += 1          # the file contains a lowercase 'r'
        c = counties.get(r[6].zfill(2), {})
        name = f"{r[1]}, {r[2]}".strip(", ")
        legs[r[0]] = {
            "id": r[0], "last": r[1], "first": r[2], "middle": r[3],
            "name": name, "chamber": r[4],
            "county_code": r[6].zfill(2), "county": c.get("name", ""),
            "county_abbr": c.get("abbr", ""), "district": r[7],
            "party": PARTY.get(pcode, pcode or "Unknown"), "party_code": pcode,
            "email": r[14],
            "address": ", ".join(x for x in [r[10], r[11], r[12], r[13]] if x),
            "label": f"{name}({pcode}) {c.get('abbr','')} {r[7]}".strip(),
            # The parameter is pid, and it takes the id from THIS file -- not
            # the member= id used in roll call page links, which is a different
            # space entirely (Keith Ammon is pid 836 and member 377204).
            # Verified against gc.nh.gov/house/members/member.aspx?pid=836.
            "url": f"https://gc.nh.gov/house/members/member.aspx?pid={r[0]}"
                   if r[4] == "H" else
                   # "district02", not "dist2": the word is spelled out and the
                   # number is zero-padded to two digits. Every senator's link
                   # was a 404.
                   f"https://gc.nh.gov/senate/members/webpages/"
                   f"district{int(r[7] or 0):02d}.aspx",
            # These pages carry a photo, a biography, committee positions and
            # towns, but they only resolve while the member is serving. For
            # anyone who has left, the General Court's own fallback is a search
            # across past members.
            "url_past": "https://gc.nh.gov/bill_Status/byAnyMember.aspx",
        }
    # ---- committee assignments, from Members.txt ---------------------------
    # That file is tab-delimited with a header row and carries five committee
    # columns per member, plus a phone number and their title. It has no member
    # id, so it cannot be joined on the key everything else uses -- but both it
    # and legislators.txt carry the work email, which is unique. Falling back to
    # a name match catches the few where an address differs.
    mp = d / "Members.txt"
    if mp.exists():
        by_email = {m["email"].lower(): m for m in legs.values() if m.get("email")}
        by_name = {f"{m['last']}|{m['first']}".lower(): m for m in legs.values()}
        matched = unmatched = 0
        with open(mp, encoding="utf-8-sig", errors="replace") as fh:
            head = next(fh).rstrip("\n").split("\t")
            col = {n.strip().lower(): i for i, n in enumerate(head)}
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) < len(head):
                    continue
                get = lambda name: (f[col[name]].strip()
                                    if name in col and col[name] < len(f) else "")
                m = by_email.get(get("workemail").lower()) or \
                    by_name.get(f"{get('lastname')}|{get('firstname')}".lower())
                if not m:
                    unmatched += 1
                    continue
                matched += 1
                cs = []
                for i in range(1, 6):
                    c = get(f"committee{i}")
                    if c and c not in cs:
                        cs.append(c)
                m["committees"] = cs
                m["title"] = get("persontitle")
                m["phone"] = get("phone")
                m["elected_status"] = get("electedstatus")
        withc = sum(1 for m in legs.values() if m.get("committees"))
        print(f"committee assignments: {matched} members matched, "
              f"{withc} with at least one committee")
        if unmatched:
            report.append(f"{unmatched} rows in Members.txt matched nobody in the "
                          "roster \u2014 expected, since that file also lists members "
                          "who have left")
        allc = Counter(c for m in legs.values() for c in m.get("committees", []))
        report.append(f"{len(allc)} distinct committees named across the roster; "
                      f"largest is {allc.most_common(1)[0][0]} with "
                      f"{allc.most_common(1)[0][1]} members" if allc else
                      "no committee assignments parsed \u2014 check Members.txt")

    house = sum(1 for m in legs.values() if m["chamber"] == "H")
    print(f"legislators: {len(legs)}  ({house} House, {len(legs)-house} Senate)")
    if bad_party:
        report.append(f"party codes with inconsistent case, normalised: {dict(bad_party)}")

    # ------------------------------------------------------------ towns ---
    # countyCode + district -> towns, and the reverse.
    towns, seats = defaultdict(list), defaultdict(list)

    # districts/house.txt includes the 41 floterial districts that
    # HouseDistricts.txt leaves out entirely, which is why eight sitting members
    # matched no town at all. Prefer it where parse_districts.py has run.
    dj = {}
    djp = Path("site/districts.json")
    if djp.exists():
        dj = json.loads(djp.read_text(encoding="utf-8"))
    if dj:
        cc_of = {v["name"]: k for k, v in counties.items()}
        nflot = 0
        for town, wards in dj.items():
            for ward, v in wards.items():
                for h in v.get("house", []):
                    cc = cc_of.get(h["county"], "")
                    if not cc:
                        continue
                    key = f"{cc}-{str(h['district']).lstrip('0') or '0'}"
                    seats[key].append({"town": town, "ward": ward})
                    towns[town].append({"county_code": cc, "county": h["county"],
                                        "district": str(h["district"]),
                                        "ward": ward,
                                        "floterial": h.get("floterial", False)})
                    nflot += bool(h.get("floterial"))
        print(f"districts: {len(towns)} towns from districts.json "
              f"({nflot} floterial town-district pairs)")

    for r in ([] if dj else rows(d / "HouseDistricts.txt", 4)):
        cc, dist, ward, town = r[0].zfill(2), r[1].lstrip("0") or "0", r[2], r[3]
        key = f"{cc}-{dist}"
        seats[key].append({"town": town, "ward": ward})
        towns[town].append({"county_code": cc, "county": counties.get(cc, {}).get("name", ""),
                            "district": dist, "ward": ward})
    print(f"towns: {len(towns)} across {len(seats)} House districts")

    for m in legs.values():
        if m["chamber"] == "H":
            k = f"{m['county_code']}-{m['district'].lstrip('0') or '0'}"
            m["towns"] = sorted({s["town"] for s in seats.get(k, [])})
        else:
            m["towns"] = []          # Senate districts are not in this file
    unmatched = [m for m in legs.values() if m["chamber"] == "H" and not m["towns"]]
    if unmatched:
        # Name the actual county and district. NH has floterial districts, which
        # overlay several towns already covered by their own districts and are
        # numbered separately, so they may simply be absent from
        # HouseDistricts.txt rather than mismatched.
        detail = "; ".join(f"{m['name']} = {m['county']} {m['district']}"
                           for m in unmatched)
        report.append(f"{len(unmatched)} House members whose district matched no "
                      f"town: {detail}")
        seats_by_county = defaultdict(set)
        for k in seats:
            cc, dist = k.split("-")
            seats_by_county[cc].add(int(dist))
        for m in unmatched:
            have = sorted(seats_by_county.get(m["county_code"], []))
            # Not `d`: that name holds the working directory Path, and rebinding
            # it here turned every later `d / "SomeFile.txt"` into int / str.
            dist_no = int(m["district"] or 0)
            report.append(f"    {m['county']} has districts "
                          f"{have[0] if have else '-'}\u2013{have[-1] if have else '-'}; "
                          f"this member is district {dist_no}"
                          + (" (above the range, so probably floterial)"
                             if have and dist_no > have[-1] else ""))
    report.append("Senate districts are not in HouseDistricts.txt, so town lookup "
                  "covers representatives only. Senate needs another source.")

    # --------------------------------------------------------- subjects ---
    subjects = {r[1]: {"id": r[0], "code": r[1], "name": r[2]}
                for r in rows(d / "SubjectCodes.txt", 3)}
    committees = {r[0]: {"code": r[0], "name": r[1], "abbr": r[2]}
                  for r in rows(d / "Committees.txt", 3)}
    print(f"subjects: {len(subjects)}   committees: {len(committees)}")

    # ------------------------------------------------------------ bills ---
    bills, by_lsr = {}, {}
    for r in rows(d / "LSRs.txt"):
        if len(r) < 33:
            continue
        bill = r[10].upper()
        if not bill:
            continue
        hc, sc = r[13], r[21]
        # LSRs.txt fields 5, 6 and 7 are 0/1 flags with no documentation. The
        # suffixes on a bill number are -FN (has a fiscal note), -A (carries an
        # appropriation) and -LOCAL (has a local impact), and they appear in
        # that order: "HB 1442-FN-A-LOCAL". Three undocumented booleans against
        # three suffixes is a strong fit, but the ORDER of the columns is a
        # guess and needs checking against a bill whose designation you know.
        flags = {"a": r[5] == "1", "fn": r[6] == "1", "local": r[7] == "1"}
        suffix = "".join(x for x, on in
                         (("-FN", flags["fn"]), ("-A", flags["a"]),
                          ("-LOCAL", flags["local"])) if on)
        rec = {
            "bill": bill, "lsr": f"{r[0]}-{r[1]}", "lsr_year": r[0], "lsr_num": r[1],
            "title": r[2], "chamber": r[3],
            "subject_code": r[12],
            "subject": subjects.get(r[12], {}).get("name", ""),
            "house_committee": committees.get(hc, {}).get("name", hc),
            "senate_committee": committees.get(sc, {}).get("name", sc),
            "hearing": r[31] or "", "hearing_room": r[32] or "",
            "suffix": suffix, "flags": flags,
            "designation": re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bill) + suffix,
        }
        bills[bill] = rec
        by_lsr[(r[0], r[1])] = bill
    # LSRs.txt does not cover every bill the docket knows about: 1,387 rows
    # against 2,233 bills with docket history. Building the site's bill list
    # from LSRs.txt alone hides roughly 800 bills that have a real record.
    # Add a stub for anything the docket mentions but LSRs.txt omits, so it is
    # searchable and has a history page even without a subject or committee.
    from_lsrs = len(bills)
    docket_bills, docket_titles = {}, {}
    dp = d / "Docket.txt"
    if dp.exists():
        with open(dp, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.split("|")
                if len(f) > 5 and f[3].strip():
                    b = f[3].strip().upper()
                    docket_bills.setdefault(b, (f[0].strip(), f[1].strip()))
    # Roll call rows carry a title, which is better than nothing for a stub.
    rp = d / "RollCallSummary.txt"
    if rp.exists():
        with open(rp, encoding="utf-8-sig", errors="replace") as fh:
            for line in fh:
                f = line.split("|")
                if len(f) > 12 and f[4].strip() and f[12].strip():
                    docket_titles.setdefault(f[4].strip().upper(), f[12].strip())
    # Titles recovered from the legacy docket pages for bills the current
    # session's files no longer describe.
    fetched_titles = {}
    tp = Path("bill_titles.json")
    if tp.exists():
        fetched_titles = json.loads(tp.read_text(encoding="utf-8"))
        print(f"recovered titles on file: {len(fetched_titles):,}")

    added = 0
    for b, (yr, lsr) in docket_bills.items():
        if b in bills:
            continue
        bills[b] = {"bill": b, "lsr": f"{yr}-{lsr}", "lsr_year": yr, "lsr_num": lsr,
                    "title": (fetched_titles.get(b)
                              or docket_titles.get(b, "")), "chamber": b[0],
                    "subject_code": "", "subject": "",
                    "house_committee": "", "senate_committee": "",
                    "hearing": "", "hearing_room": "", "stub": True}
        by_lsr.setdefault((yr, lsr), b)
        added += 1
    for b, t in fetched_titles.items():
        if b in bills and not bills[b].get("title"):
            bills[b]["title"] = t
    nsuf = Counter()
    for b in bills.values():
        if b.get("suffix"):
            nsuf[b["suffix"]] += 1
    if nsuf:
        report.append("bill-number suffixes derived from LSRs.txt columns 5/6/7: "
                      + ", ".join(f"{k} {v}" for k, v in nsuf.most_common(6))
                      + ". VERIFY the column order against a bill whose "
                      "designation you know \u2014 HB 1442 should be -FN.")
    print(f"bills: {len(bills)}  ({from_lsrs} from LSRs.txt, {added} added from "
          f"the docket)")
    untitled = sum(1 for r in bills.values() if not r.get("title"))
    if untitled:
        print(f"  {untitled:,} still have no title - run fetch_bill_titles.py")
    if added:
        titled = sum(1 for b in bills.values() if b.get("stub") and b["title"])
        yrs = Counter(bills[b]["lsr_year"] for b in bills if bills[b].get("stub"))
        report.append(
            f"{added} bills are in Docket.txt but not LSRs.txt, by LSR year "
            f"{dict(yrs)}. LSRs.txt, LsrsOnly.txt and RollCallSummary.txt all "
            "cover the current session only, so these carry a docket history but "
            f"no title, subject or sponsor ({titled} picked up a title from roll "
            "calls). Their titles live on the legacy docket pages.")
    unmapped = sum(1 for b in bills.values()
                   if b.get("subject_code") and not b["subject"])
    if unmapped:
        report.append(f"{unmapped} bills carry a subject code that is not in "
                      "SubjectCodes.txt")

    # --------------------------------------------------------- sponsors ---
    # LsrsOnly.txt is the better sponsor source. It states "Prime" or "Sponsor"
    # outright instead of encoding it in a flag, and carries the bill number and
    # title on every row, so it also supplies titles for bills that LSRs.txt
    # omits entirely.
    #   26-2001|944|1190|2026|Sponsor|SB416|H|relative to the pooling of tips.
    sponsors = defaultdict(list)
    lo = d / "LsrsOnly.txt"
    lo_rows = [r for r in rows(lo, 8)] if lo.exists() else []
    if lo_rows:
        seen = set()
        for r in lo_rows:
            bill, mid, role = r[5].upper(), r[1], r[4]
            m = legs.get(mid)
            if not bill or (bill, mid) in seen:
                continue
            seen.add((bill, mid))
            if bill in bills and not bills[bill].get("title"):
                bills[bill]["title"] = r[7]
            sponsors[bill].append({
                "member_id": mid,
                "name": m["name"] if m else f"Former member #{mid}",
                "party": m["party_code"] if m else "X",
                "chamber": r[6],
                "label": m["label"] if m else f"Former member #{mid}",
                "sequence": 0 if role.lower() == "prime" else 1,
                "prime": role.lower() == "prime", "role": role})
        for b in sponsors:
            sponsors[b].sort(key=lambda x: (x["sequence"], x["name"]))
        nprime = sum(1 for v in sponsors.values() for x in v if x["prime"])
        noprime = sum(1 for v in sponsors.values() if not any(x["prime"] for x in v))
        print(f"sponsors: {sum(len(v) for v in sponsors.values()):,} links across "
              f"{len(sponsors):,} bills (from LsrsOnly.txt)")
        report.append(f"sponsors read from LsrsOnly.txt, which labels the prime "
                      f"sponsor explicitly: {nprime:,} primes, {noprime} bills with "
                      "none marked")
        unknown = {x["member_id"] for v in sponsors.values() for x in v
                   if x["party"] == "X"}
        if unknown:
            report.append(f"{len(unknown)} sponsors are not in legislators.txt "
                          "(former members)")

    lo_bills = set(sponsors)
    flags, cross, missing_member, missing_lsr = Counter(), Counter(), 0, 0
    # LsrsOnly.txt does not cover every bill -- HB197 and HB104 came back with
    # no sponsors at all. So fall back to LsrSponsors.txt per bill rather than
    # picking one file for everything.
    for r in rows(d / "LsrSponsors.txt", 5):
        bill = by_lsr.get((r[0], r[1].zfill(4)))
        if not bill:
            missing_lsr += 1
            continue
        if bill in lo_bills:
            continue                      # already covered, and better, by LsrsOnly
        m = legs.get(r[3])
        if not m:
            missing_member += 1
            continue
        flags[r[4]] += 1
        # Hypothesis: the flag marks a sponsor from the OTHER chamber.
        cross[(r[4], m["chamber"] != bills[bill]["chamber"])] += 1
        sponsors[bill].append({"member_id": r[3], "name": m["name"],
                               "party": m["party_code"], "chamber": m["chamber"],
                               "label": m["label"], "sequence": int(r[2] or 0),
                               "flag": r[4]})
    # Field 4 = 1 marks the prime sponsor. There are about as many 1s as there
    # are bills, and it matched the prime sponsor on gencourt for SB566. The
    # earlier cross-chamber reading was wrong.
    # Only relevant to the LsrSponsors.txt fallback. When LsrsOnly.txt supplied
    # the sponsors it already said "Prime" outright, and re-deriving it here
    # from a flag those rows do not have would overwrite the right answer.
    # Runs for bills that came from LsrSponsors.txt, whether or not LsrsOnly.txt
    # supplied others. Guarding the whole block on "LsrsOnly was absent" left the
    # fallback bills with no prime field at all.
    disagree = 0
    if True:
        for b in [x for x in sponsors if x not in lo_bills]:
            sponsors[b].sort(key=lambda x: x["sequence"])
            flagged = [x for x in sponsors[b] if x["flag"] == "1"]
            for x in sponsors[b]:
                x["prime"] = (x["flag"] == "1") if flagged else (x["sequence"] == 1)
            if flagged and flagged[0]["sequence"] != 1:
                disagree += 1
    filled = len(sponsors) - len(lo_bills)
    if filled:
        print(f"sponsors: {filled:,} further bills filled from LsrSponsors.txt")
    print(f"sponsors: {sum(len(v) for v in sponsors.values()):,} links across "
          f"{len(sponsors):,} bills in total")
    # Bills the current session's files do not cover, from the STATUS page --
    # which lists sponsors as labelled links with party and member id, rather
    # than leaving them to be sifted out of docket prose.
    bsp = Path("bill_status.json")
    if bsp.exists():
        st = json.loads(bsp.read_text(encoding="utf-8"))
        added_sp = added_t = 0
        for bill, v in st.items():
            if bill in bills:
                if v.get("title") and not bills[bill].get("title"):
                    bills[bill]["title"] = v["title"]
                    added_t += 1
                for k in ("committee_code", "chapter", "text_pdf"):
                    if v.get(k) and not bills[bill].get(k):
                        bills[bill][k] = v[k]
            if not v.get("sponsors") or (sponsors.get(bill)):
                continue
            sponsors[bill] = [
                {"member_id": x.get("web_member_id", ""), "name": x["name"],
                 "party": x.get("party", ""), "chamber": x.get("chamber", ""),
                 "label": (f"{x['name']} ({x['party']})" if x.get("party")
                           else x["name"]),
                 "sequence": i, "prime": i == 0, "url": x.get("url", ""),
                 "source": "bill status page", "prime_inferred": True}
                for i, x in enumerate(v["sponsors"])]
            added_sp += 1
        if added_sp or added_t:
            print(f"bill status page: {added_sp:,} bills gained sponsors, "
                  f"{added_t:,} gained a title")
            report.append(f"{added_sp:,} bills took their sponsors from the bill "
                          "status page, because the sponsor files cover the "
                          "current session only. Prime is the first listed there; "
                          "the page does not mark the field.")

    nosp = [b for b in bills if b not in sponsors]
    if nosp:
        report.append(f"{len(nosp)} bills still have no sponsor in either file "
                      f"(e.g. {', '.join(sorted(nosp)[:5])})")
    nflag = flags.get("1", 0)
    # Belt and braces: anything that still lacks the field falls back to first
    # in sequence, so a later change to either source cannot crash the build.
    for b in sponsors:
        for x in sponsors[b]:
            x.setdefault("prime", x.get("sequence", 1) in (0, 1))
    noprime = sum(1 for b in sponsors if not any(x["prime"] for x in sponsors[b]))
    if flags:
        report.append(f"prime sponsor from field 4: {nflag:,} flagged across "
                      f"{len(sponsors):,} bills; {noprime} bills have none flagged "
                      f"(sequence order used there); {disagree} where the flagged "
                      "sponsor was not first in sequence")
    if missing_lsr or missing_member:
        report.append(f"sponsor rows dropped: {missing_lsr} unknown LSR, "
                      f"{missing_member} unknown member")

    # ------------------------------------------------------- roll calls ---
    # Names for members who left mid-term, from resolve_members.py.
    former = {}
    fp = Path("former_members.json")
    if fp.exists():
        former = json.loads(fp.read_text(encoding="utf-8"))
        print(f"former members named: {len(former)}")

    def _former_label(mid):
        # Members who left mid-term are shown exactly like everyone else. Some
        # died in office, and a colleague reading the record should not have
        # that flagged at them. The vote is the fact; the circumstances of
        # their leaving are not this site's business.
        f = former.get(mid)
        if not f:
            return f"Member #{mid}"
        pc = (f.get("party") or "")[:1].upper()
        return (f"{f['name']}({pc}) {f.get('county','')} "
                f"{f.get('district','')}").strip()

    summary = {}
    for r in rows(d / "RollCallSummary.txt"):
        if len(r) < 13:
            continue
        summary[(r[0], r[1], r[2])] = {
            "year": r[0], "body": r[1], "number": r[2], "datetime": r[3],
            "bill": r[4].upper(), "yea": int(r[5] or 0), "nay": int(r[6] or 0),
            "question": r[11], "title": r[12],
        }
    print(f"roll call summaries: {len(summary):,}")

    member_votes, vote_kinds, hist_bodies = [], Counter(), Counter()
    vnums, unmatched_votes = set(), 0
    for r in rows(d / "RollCallHistory.txt", 8):
        key = (r[0], r[1], r[2])
        hist_bodies[r[1]] += 1
        vnums.add(int(r[2]) if r[2].isdigit() else -1)
        s = summary.get(key)
        if not s:
            unmatched_votes += 1
            continue
        m = legs.get(r[4])
        vote_kinds[r[6]] += 1
        member_votes.append({
            # 420 members cast votes but only 406 are in legislators.txt: the
            # file holds current members, and people resign or die mid-term.
            # Their votes are still part of the record.
            "member_id": r[4],
            "name": (m["name"] if m else
                     former.get(r[4], {}).get("name", f"Member #{r[4]}")),
            "party": (m["party_code"] if m else
                      (former.get(r[4], {}).get("party") or "X")[:1].upper()),
            "label": (m["label"] if m else _former_label(r[4])),
            "year": r[0], "body": r[1], "vote_number": r[2],
            "bill": s["bill"], "question": s["question"],
            "date": s["datetime"].split(" ")[0], "vote": r[6],
        })
    print(f"member votes: {len(member_votes):,}")
    print(f"  vote values: {dict(vote_kinds)}")
    report.append(f"RollCallHistory field 2 ranges {min(vnums) if vnums else 0}"
                  f"\u2013{max(vnums) if vnums else 0}, and joins to RollCallSummary "
                  f"on (year, body, number). Chambers present: {dict(hist_bodies)}.")
    if unmatched_votes:
        report.append(f"{unmatched_votes:,} history rows had no matching summary row "
                      "(likely roll calls from a session the summary file no longer covers)")

    former = {v["member_id"] for v in member_votes if v["party"] == "X"}
    if former:
        report.append(f"{len(former)} members cast votes but are not in the current "
                      "roster; names resolved from former_members.json. They are "
                      "displayed no differently from anyone else.")
    per_member = Counter(v["member_id"] for v in member_votes)
    if per_member:
        n = sorted(per_member.values())
        report.append(f"votes per member: median {n[len(n)//2]}, "
                      f"min {n[0]}, max {n[-1]}, members covered {len(per_member)}")

    # ------------------------------------------------------------ write ---
    (out / "legislators.json").write_text(
        json.dumps(sorted(legs.values(), key=lambda m: m["name"]), indent=2), encoding="utf-8")
    (out / "member_votes.json").write_text(json.dumps(member_votes), encoding="utf-8")
    (out / "towns.json").write_text(json.dumps(towns, indent=2), encoding="utf-8")
    (out / "bills.json").write_text(json.dumps(bills, indent=2), encoding="utf-8")
    (out / "sponsors.json").write_text(json.dumps(sponsors, indent=2), encoding="utf-8")
    (out / "subjects.json").write_text(json.dumps(subjects, indent=2), encoding="utf-8")
    (out / "committees.json").write_text(json.dumps(committees, indent=2), encoding="utf-8")

    print(f"\nwritten to {out}/")
    print("\n" + "=" * 70)
    print("THINGS TO CHECK")
    print("=" * 70)
    for r in report:
        # The Windows console is cp1252, so bullets and dashes arrive as noise.
        # Console output is ASCII; the JSON keeps the real characters.
        print("  - " + r.replace("\u2014", "--").replace("\u2013", "-")
                        .replace("\u2019", "'").replace("\u201c", '"')
                        .replace("\u201d", '"'))

    # A concrete spot check beats any amount of schema inference.
    sample = next((b for b in sponsors if sponsors[b]), None)
    if sample:
        print(f"\nSpot check \u2014 {sample}: {bills[sample]['title'][:64]}")
        print(f"  subject: {bills[sample]['subject'] or '(none)'}")
        print(f"  House committee: {bills[sample]['house_committee'] or '(none)'}")
        for s in sponsors[sample][:6]:
            src = s.get("role") or f"flag={s.get('flag', '-')}"
            print(f"  {'PRIME' if s.get('prime') else '     '} {s['label']}  {src}")
        print("\n  Confirm the PRIME line matches the prime sponsor on gencourt.")


if __name__ == "__main__":
    main()
