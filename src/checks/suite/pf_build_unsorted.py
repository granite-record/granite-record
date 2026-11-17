#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.5
"""
preflight's checks of build checks with no module under test, for a person to sort.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_Seal, _in_suite, _parsed, _run, _sealed_run, _source, _suite_files, check)
from pf_fixture import (CHAIN_NEEDS, PROCEEDINGS_MODULES, _fixture_site_shared,
                        _fixture_site_v2, _fixture_site_whole, _site_fixture)
from pf_harness import (_with_components)
from pf_shared import (AMENDMENT_PAGE, BASE_HREF, CALENDAR_PAGE, INLINE_BODY, OFFSITE,
                       _ASKS_GC_FLOOR, _ELECT_DEADLINE, _ELECT_HAND, _ELECT_IN, _ELECT_SOURCE,
                       _ballot_mixed_rows, _bill_index_write, _cors_rules, _cors_said,
                       _elect_absent, _elect_blocks, _elect_built, _elect_card, _elect_fixture,
                       _elect_part, _elect_run, _elect_strip, _mk, _site_bills,
                       _strip_js_comments, _tap_failures, _turn_day, _turn_files)


@check("build", "every file the API's records put under /api/ may be read from another origin, by "
                "exactly one _headers rule, and no rule reaches the Functions' /api/ addresses")
def _api_records_cors():
    """THE RECORDS ARE READABLE FROM ANYWHERE, as the /data files are
    (_data_cors, whose reading of _headers this shares): every file the
    fixture's build wrote under /api/, and an address of each kind the
    fixture writes none of (a member, a request), is given
    Access-Control-Allow-Origin: * by exactly one rule -- Pages sends a header
    two rules name joined, "*, *", which a browser refuses -- and no rule
    reaches /api/live/, /api/report or /api/follow/, which are the Functions'
    and answer for themselves."""
    shared, _base, _ran, _days = _fixture_site_shared()
    built = shared / "site"
    rules = _cors_rules((built / "_headers").read_text(encoding="utf-8"))
    paths = sorted("/" + p.relative_to(built).as_posix() for p in (built / "api").rglob("*")
                   if p.is_file())
    assert paths, "the fixture's build wrote nothing under /api/"
    paths += ["/api/members/376682.json", "/api/members/index.json", "/api/requests/2027/0001.json",
              "/api/requests/2027/index.json", "/api/bills/2027-2028/HB1.json"]
    wrong = [f"{p} ({_cors_said(rules, p)})" for p in paths if _cors_said(rules, p) != ["*"]]
    assert not wrong, ("these API files are not given Access-Control-Allow-Origin: * by exactly "
                       "one _headers rule: " + "; ".join(wrong[:6]))
    fns = ["/api/live/votes/2026-01-07", "/api/live/streams", "/api/report", "/api/follow/signup",
           "/api/follow/count"]
    reach = [p for p in fns if _cors_said(rules, p)]
    assert not reach, f"a _headers rule reaches the Functions' addresses: {reach}"
    return "ok", (f"{len(paths)} addresses under /api/ each given * by one rule; none of the "
                  f"{len(fns)} Functions' addresses by any")


def _api_law_page_text(page, anchor):
    """(the paragraphs, the source note's line) a chapter's page shows for
    one section, read off the page itself: the <p>s of its rs-text, their
    tags and the page's own "(repealed)" marks taken off, and its rs-source;
    None where the page has no such section."""
    import html as _html
    at = page.find(f'<section class="rs-sec" id="{anchor}">')
    if at < 0:
        return None
    sec = page[at:page.find("</section>", at)]
    body = sec.split('<div class="rs-text" translate="no">', 1)[-1]
    body = re.split(r'<p class="rs-source">|<div class="rs-folds">', body)[0]
    body = re.sub(r' <span class="rs-gone">.*?</span>', "", body)   # the page's own "(repealed)"
    paras = [_html.unescape(re.sub(r"<[^>]+>", "", p)).strip()
             for p in re.findall(r"<p>(.*?)</p>", body, re.S)]
    note = re.search(r'<p class="rs-source">(.*?)</p>', sec, re.S)
    return [p for p in paras if p], (_html.unescape(note.group(1)) if note else "")


def _api_bill_text_expected(site, rec):
    """What a bill's Bill Text tab shows, read here from what the tab reads
    (app.js: the version index for a bill with more than one version or with
    amendments, else the record's own printing): [(name, day, text)]."""
    year, bid = str(rec.get("year")), str(rec.get("id"))
    ix = Path(site) / "versions" / year / f"{bid}.json"
    if ((rec.get("nver") or 0) > 1 or (rec.get("namd") or 0)) and ix.is_file():
        got = []
        for v in json.loads(ix.read_text(encoding="utf-8")).get("versions") or []:
            m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(v.get("date") or ""))
            p = Path(site) / str(v.get("text_url") or "").lstrip("/")
            got.append((v.get("title"), f"{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}" if m else None,
                        p.read_text(encoding="utf-8") if v.get("text_url") and p.is_file() else None))
        if got:
            return got
    body = ((rec.get("billtext") or {}).get("body") or "")
    return [((rec.get("billtext") or {}).get("version") or "", None, body)] if body.strip() else []


@check("build", "the API's files a record are each in the shape api_schema promises: \"format\": 1 "
                "and only fields it marks stable; the sitting term's bills and roll calls a file "
                "each and no other term's; the members and the requests; and the laws' and the "
                "bills' text, each as its page shows it",
       needs=("api_records", "api_schema", "api_page", "site_read", "rsa", "build_rsa"))
def _api_records(AR, AS, AP, SR, RSA, BR):
    """THE API'S RECORDS (api_records.py; the owner's word of 16 November
    2026: static files, "format": 1 in every one and no /v1/ in the path, the
    sitting term's records first; and the same morning, that laws and bills
    carry their text). Held three ways, each by its own reading here and not
    by the writer's own guard (AR.held), so a guard that stopped guarding is
    caught too:

      the fixture's build   every file build_exports wrote under site/api/:
                            each is JSON with "format": 1 and no field the
                            resource it belongs to does not mark stable, to
                            the depth api_schema describes; the sitting term
                            -- the newest its bill index holds, never a
                            literal -- has a file for each bill and roll call,
                            exactly, and no other term has one; every term has
                            its rows, and every term's bills a line each in
                            bill-texts-<term>.jsonl.gz; each bill's text is
                            what its Bill Text tab shows, and a bill with none
                            says so; each section's text and source note are
                            the chapter page's own paragraphs and line, with
                            the day the table was taken, the latest year of
                            laws and the official page the page's lead gives;
                            index.json lists every resource with tonight's
                            counts; schema.json describes the same fields; and
                            the /api page names each kind with a file that is
                            there
      a record made up here two terms, a person with a seat and a sponsorship,
                            one replaced, a request become a bill, a bill with
                            two versions, one with its printing alone, one
                            with no text, and a file an earlier build left:
                            the members' and requests' files, which the
                            fixture has no roster or requests for; the
                            versions as the tab reads them; the newer term
                            taking the files a record from the older, whose
                            file is taken away; and a page's field let into a
                            bill's file stops the step
      the real record       where a site/ built from it carries /api/, as on
                            the laptop after a build: the text of a sample of
                            the sitting term's bills and of the chapters,
                            against their pages
    """
    import csv as _csv_
    import gzip
    shared, _base, _ran, _days = _fixture_site_shared()
    built = shared / "site"
    api = built / "api"
    assert (api / "index.json").is_file(), "the fixture's build wrote no site/api/index.json"

    def walk(obj, spec, inside, where, out, depth=0):
        """Every field of obj, to the depth `inside` names, that spec does
        not mark stable -- read here, apart from AR.unpromised."""
        for k, v in obj.items():
            f = spec.get(k)
            if not f or f[2] != "stable":
                out.append(f"{where}.{k}")
            elif k in inside and depth < 4:
                for x in (v if isinstance(v, list) else [v]):
                    if isinstance(x, dict):
                        walk(x, inside[k], inside, f"{where}.{k}", out, depth + 1)
                    elif x is not None:
                        out.append(f"{where}.{k} holds {type(x).__name__}, not an object")

    def kind(rel):
        """(resource, rows or record) of a path under api/, or None; a night
        of the change feed is ("changes", "night")."""
        if re.fullmatch(r"changes/\d{4}-\d{2}-\d{2}\.json", rel):
            return "changes", "night"
        for name, rx_rows, rx_rec in (
                ("bills", r"bills/\d{4}-\d{4}/index\.json", r"bills/\d{4}-\d{4}/[A-Z]+\d+[A-Z]?\.json"),
                ("rollcalls", r"rollcalls/\d{4}-\d{4}\.json", r"rollcalls/\d{4}-\d{4}/\d{4}-[HS]-\d+\.json"),
                ("members", r"members/index\.json", r"members/[0-9A-Za-z-]+\.json"),
                ("requests", r"requests/\d{4}/index\.json", r"requests/\d{4}/\d{4,5}\.json"),
                ("laws", r"laws/index\.json", r"laws/\d{1,3}(?:-[A-Z]{1,2})?\.json")):
            if re.fullmatch(rx_rows, rel):
                return name, "rows"
            if re.fullmatch(rx_rec, rel):
                return name, "record"
        return None

    def read_api(root):
        """{path under api/: its object} of every file, and what is wrong with each."""
        got, bad = {}, []
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
            except ValueError as e:
                bad.append(f"{rel} is not JSON ({e})")
                continue
            got[rel] = obj
            if not isinstance(obj, dict) or obj.get("format") != 1:
                bad.append(f"{rel} does not say \"format\": 1")
                continue
            if rel == "index.json":
                continue
            k = kind(rel)
            if k is None:
                bad.append(f"{rel} is a file no resource of api_schema describes")
                continue
            spec, inside = AS.api_file_fields(*k)
            extra = []
            walk(obj, spec, inside, rel, extra)
            bad += [f"{e}, which api_schema does not promise" for e in extra]
        return got, bad

    def texts_of(data):
        """{key: line} of every bill-texts-<term>.jsonl.gz under `data`, and what is wrong."""
        lines, bad = {}, []
        spec, inside = AS.api_file_fields("bills", "texts")
        for p in sorted(Path(data).glob("bill-texts-*.jsonl.gz")):
            for raw in gzip.decompress(p.read_bytes()).decode("utf-8").splitlines():
                x = json.loads(raw)
                extra = []
                walk(x, spec, inside, p.name, extra)
                bad += [f"{e}, which api_schema does not promise" for e in extra]
                lines[x.get("key")] = x
        return lines, bad

    def as_text(versions):
        return [(v.get("name"), v.get("date"), v.get("text")) for v in versions]

    got, bad = read_api(api)
    lines, bad_t = texts_of(built / "data")
    assert not bad + bad_t, f"{len(bad + bad_t)} findings in the fixture's /api/: " + "; ".join((bad + bad_t)[:8])
    rows = SR.bill_index(built)
    sitting = max(r["term"] for r in rows)
    terms = {r["term"] for r in rows}
    per_bill = {rel for rel in got if kind(rel) == ("bills", "record")}
    want = {f"bills/{sitting}/{r['id']}.json" for r in rows if r["term"] == sitting}
    assert per_bill == want, (f"the bills with a file of their own are not the sitting term's "
                              f"({sitting}): missing {sorted(want - per_bill)[:4]}, more "
                              f"{sorted(per_bill - want)[:4]}")
    for t in terms:
        f = got.get(f"bills/{t}/index.json") or {}
        assert f.get("term") == t and len(f.get("bills") or []) == sum(r["term"] == t for r in rows), \
            f"bills/{t}/index.json does not hold every bill of {t} as a row"
    assert set(lines) == {f"{r['term']}/{r['id']}" for r in rows}, \
        "bill-texts-<term>.jsonl.gz do not hold every bill of every term, a line each"
    one = got[sorted(want)[0]]
    assert one["key"] == f"{sitting}/{one['id']}" and "events" in one and "narrative" not in one \
        and "stations" not in one, f"a bill's file is not its row and its record's stable fields: {sorted(one)}"
    # EACH BILL'S TEXT IS WHAT ITS BILL TEXT TAB SHOWS, read here from what
    # the tab reads; a bill with none says so, in its file and its line.
    n_text = 0
    for y, b, rec in SR.records(built):
        key = f"{rec.get('term')}/{b}"
        want_t = _api_bill_text_expected(built, rec)
        line = lines.get(key) or {}
        assert as_text(line.get("versions") or []) == want_t and \
            line.get("text_on_file") == bool(want_t), \
            f"{key}'s line in bill-texts is not the text its Bill Text tab shows"
        f = got.get(f"bills/{sitting}/{b}.json")
        if rec.get("term") == sitting:
            assert f and as_text(f.get("versions") or []) == want_t and \
                f.get("text_on_file") == bool(want_t), \
                f"{key}'s file is not the text its Bill Text tab shows"
        n_text += bool(want_t)
    with (built / "data" / "rollcalls.csv").open(encoding="utf-8", newline="") as fh:
        rcs = list(_csv_.DictReader(fh))
    per_rc = {rel for rel in got if kind(rel) == ("rollcalls", "record")}
    want_rc = {f"rollcalls/{sitting}/{r['roll_call']}.json" for r in rcs if r["term"] == sitting}
    assert want_rc and per_rc == want_rc, (
        f"the roll calls with a file of their own are not the sitting term's: missing "
        f"{sorted(want_rc - per_rc)[:4]}, more {sorted(per_rc - want_rc)[:4]}")
    assert {f"rollcalls/{t}.json" for t in {r["term"] for r in rcs}} <= set(got), \
        "a term with roll calls has no file of their rows"
    ballots = [b for rel in per_rc for b in got[rel]["ballots"]]
    assert ballots and all(b.get("member_id") and b.get("vote") is not None for b in ballots), \
        f"the sitting term's roll calls carry no ballots, or ballots without a member: {ballots[:2]}"
    assert all(isinstance(got[rel]["passed"], bool) and isinstance(got[rel]["yeas"], int)
               for rel in per_rc), "a roll call's file does not type its tally and outcome"

    # THE LAWS: every section's heading, text and source note as its chapter's
    # page shows them, read off the fixture's built pages, with the source
    # note's law, the day the table was taken and the page's official link.
    table = RSA.load(shared / "db" / "NH_RSA.psv", shared / "db" / "_columns.json")
    taken = json.loads((shared / "db" / "_manifest.json").read_text(encoding="utf-8"))["NH_RSA"]["fetched"][:10]
    n_sec = 0
    for ch in table.chapters:
        law = got.get(f"laws/{ch}.json") or {}
        page = BR.chapter_file(built / "laws", ch).read_text(encoding="utf-8")
        assert law.get("text_taken") == taken and law.get("laws_through") == 2025 and \
            law.get("official") and f'<a href="{law["official"]}" rel="noopener">The official text' in page, \
            f"laws/{ch}.json does not name the day its text was taken and its source as its page does: {law}"
        for s in law.get("sections") or []:
            shown = _api_law_page_text(page, "s" + s["section"].split(":", 1)[1])
            if s["repealed"]:
                assert s["text"] is None and s["note"] is None, s
                continue
            # A section the table holds no text for is "" here and no
            # paragraph on its page (18 of the real record's 26,321).
            assert shown and (s["text"].split("\n") if s["text"] else []) == shown[0] and \
                (f"Source. {s['note']}" if s["note"] else "") == shown[1] and \
                s["heading"] == table.sections[s["section"]].heading, \
                (f"{s['section']}'s text in laws/{ch}.json is not what its chapter's page shows: "
                 f"{s['text'][:80]!r} against {shown}")
            n_sec += 1
    assert n_sec >= 3 and got["laws/91-A.json"]["sections"][0]["changed_by"] == \
        [{"year": 1967, "law": "251:1", "bill": "", "effective": None}], got["laws/91-A.json"]
    assert [c["chapter"] for c in got["laws/index.json"]["chapters"]] == ["91-A", "404"], \
        got["laws/index.json"]

    # THE INDEX, AND THE SCHEMA THAT DESCRIBES THE SAME FIELDS.
    ix = got["index.json"]
    names = [r["name"] for r in AS.API_RESOURCES]
    assert [r["name"] for r in ix["resources"]] == names and ix["sitting_term"] == sitting, \
        (f"index.json lists {[r['name'] for r in ix['resources']]} for {ix['sitting_term']}, not "
         f"{names} for {sitting}")
    counted = {n: sum(1 for rel in got if (kind(rel) or ("",))[0] == n) for n in names}
    assert {r["name"]: r["files_tonight"] for r in ix["resources"]} == counted, \
        (ix["resources"], counted)
    sch = json.loads((built / "data" / "schema.json").read_text(encoding="utf-8"))
    assert sch.get("x-api-records") == AS.api_records_schema(), \
        "schema.json does not describe the API's records as api_schema does"
    assert any(r.get("path", "").startswith("bill-texts-") and r.get("schema") for r in sch["resources"]), \
        "schema.json does not describe the bill texts' files"
    flat = [f for r in sch["x-api-records"] for fl in r["files"] for f in fl["fields"]]
    while any("x-fields" in f for f in flat):
        flat = [g for f in flat for g in ([f] + f.pop("x-fields", []))]
    assert flat and all(f["x-stability"] == "stable" for f in flat), \
        "a field of the API's records is described but not stable, and no file may carry it"
    people = next(r for r in AS.package([], [{"path": "/data/people.json", "rows": 1, "bytes": 1}],
                                        "", "x")["resources"] if r["name"] == "people")
    assert {f["name"]: f["description"] for f in people["schema"]["fields"]} == \
        {k: v[1] for k, v in AS.API_PERSON.items()}, \
        "a member's file and people.json describe the same person's fields in different words"

    # THE PAGE names each kind the build wrote, with a file that is there.
    page = (built / "api.html").read_text(encoding="utf-8")
    sec = page.split('id="records"', 1)[-1].split("</section>", 1)[0]
    links = re.findall(r'href="(/api/[^"]+)"', sec)
    assert "One Record at a Time" in page and links and \
        all((built / h.lstrip("/")).is_file() for h in links), \
        f"the /api page does not describe the records with a file that is there: {links}"
    for name in ("bills", "rollcalls", "laws"):
        assert f"/api/{name}/" in sec, f"the /api page does not describe /api/{name}/"
    assert "Bill Texts by Term" in page, "the /api page does not list the bill texts' files"

    # A RECORD MADE UP HERE.
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        site, out = d / "site", d / "site" / "data"
        (site / "idx").mkdir(parents=True)
        out.mkdir()
        row = lambda t, b, y: {"id": b, "year": y, "term": t, "title": f"{b} of {t}", "kind": "active",
                               "status": "In committee", "sponsor": "A Member", "committees": ["Finance"],
                               "nrc": 1, "chip": "In Committee", "rail": [], "sponsor_slug": "x"}
        idx = {"2027-2028": [row("2027-2028", "HB1", 2027)],
               "2025-2026": [row("2025-2026", "HB1", 2025), row("2025-2026", "SB2", 2026)]}
        for t, rr in idx.items():
            (site / "idx" / f"{t}.json").write_text(json.dumps(rr), encoding="utf-8")
        (site / "idx" / "2027-requests.json").write_text(json.dumps([
            {"id": "LSR20270001", "n": "LSR 2027-0001", "year": 2027, "title": "a request",
             "sponsor": "A Member", "cosp": ["B. Two"], "body": "HB", "status": "Filed",
             "withdrawn": False, "introduced": "HB 1", "address": "request/2027-0001",
             "sponsor_slug": "x", "rail": []}]), encoding="utf-8")
        (site / "meta.json").write_text(json.dumps(
            {"terms": ["2027-2028", "2025-2026"],
             "requests": {"term": "2027-requests", "year": 2027}}), encoding="utf-8")
        # HB 1 of 2027 has two versions (build_bill_versions' index and texts);
        # SB 2 of 2026 its printing alone; HB 1 of 2025 no text at all.
        vdir = site / "versions" / "2027"
        vdir.mkdir(parents=True)
        (vdir / "HB1.0.txt").write_text("AN ACT as introduced.\n1 Section one.", encoding="utf-8")
        (vdir / "HB1.1.txt").write_text("AN ACT as amended.\n1 Section one, amended.", encoding="utf-8")
        (vdir / "HB1.json").write_text(json.dumps({"bill": "HB1", "year": "2027", "versions": [
            {"title": "Introduced", "label": "Introduced", "date": "01/05/2027 09:00:00",
             "text_url": "/versions/2027/HB1.0.txt"},
            {"title": "As Amended by the House", "label": "As Amended by the House",
             "date": "03/10/2027 16:14:22", "text_url": "/versions/2027/HB1.1.txt"}]}), encoding="utf-8")

        def put(name, cols, rows_):
            with (out / name).open("w", encoding="utf-8", newline="") as fh:
                w = _csv_.writer(fh)
                w.writerow(cols)
                w.writerows(rows_)
        put("rollcalls.csv", list(AS.CSV["rollcalls.csv"]),
            [["2025-H-9", "2025-2026", "2025", "H", "9", "2025-03-01", "HB1", "q", "", "200", "100",
              "0", "1", "0", "", "", "docket"],
             ["2027-H-1", "2027-2028", "2027", "H", "1", "2027-01-07", "HB1", "q", "", "201", "163",
              "30", "1", "0", "", "", "count"]])
        put("votes-2027-2028.csv", list(AS.CSV["votes-<term>.csv"]),
            [["2027-H-1", "2027-2028", "2027-01-07", "HB1", "q", "m1", "Member, A", "R", "House", "Yea"]])
        put("legislators.csv", list(AS.CSV["legislators.csv"]),
            [["m1", "A Member", "House", "Republican", "1", "Belknap", "a@gc.nh.gov",
              "Finance; Rules", "3", "120", "100"]])
        put("sponsors.csv", list(AS.CSV["sponsors.csv"]),
            [["2027-2028", "HB1", "m1", "A Member", "R", "H", "1", "", "the sponsor file", "100"],
             ["2025-2026", "SB2", "m1", "A Member", "R", "H", "0", "", "the sponsor file", "100"]])
        stale = site / "api" / "bills" / "2025-2026" / "HB1.json"
        stale.parent.mkdir(parents=True)
        stale.write_text("{}", encoding="utf-8")
        rec = AR.Records([r for rr in idx.values() for r in rr], site)
        for t, rr in idx.items():
            for r in rr:
                rec.add_bill(t, {"id": r["id"], "year": r["year"], "term": t, "title": "(New Title) x",
                                 "events": [{"date": "2027-01-05", "text": "Introduced"}],
                                 "narrative": "a page's own words", "stations": [{"when": "x"}],
                                 "nver": 2 if t == "2027-2028" else 1,
                                 "billtext": ({"version": "FINAL VERSION", "body": "AN ACT, chaptered."}
                                              if r["id"] == "SB2" else {"version": "", "body": ""})})
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):          # its lines are the build's
            text_rows = rec.text_files(out)
        people = [{"person": "100", "name": "A Member", "employee_numbers": ["m1"], "person_ids": [],
                   "member_ids": ["m1"], "page": "/legislator/a-member", "sitting": True,
                   "chambers": ["H"], "first_term": "2025-2026", "last_term": "2027-2028"},
                  {"person": "101", "replaced_by": "100"}]
        summary, said = AR.write(site, out, rec, people=people, person_of={"m1": "100"},
                                 base="https://example.org", built="2027-01-08T09:00:00Z",
                                 db=d / "no-db", citations=d / "none.json",
                                 ledger=d / "no-hashes.json", ledger_out=d / "api-hashes.next.json")
        made, bad = read_api(site / "api")
        made_t, bad_t = texts_of(out)
        assert not bad + bad_t, f"{len(bad + bad_t)} findings in the made-up /api/: " + "; ".join((bad + bad_t)[:6])
        assert len([x for x in made if x.startswith("changes/")]) == 8, sorted(made)
        made = {k: v for k, v in made.items() if not k.startswith("changes/")}
        assert sorted(made) == [
            "bills/2025-2026/index.json", "bills/2027-2028/HB1.json", "bills/2027-2028/index.json",
            "index.json", "members/100.json", "members/101.json", "members/index.json",
            "requests/2027/0001.json", "requests/2027/index.json", "rollcalls/2025-2026.json",
            "rollcalls/2027-2028.json", "rollcalls/2027-2028/2027-H-1.json"], sorted(made)
        assert not stale.exists(), \
            "a bill's file an earlier build left, of a term no longer sitting, is still there"
        hb = made["bills/2027-2028/HB1.json"]
        two = [{"name": "Introduced", "date": "2027-01-05", "text": "AN ACT as introduced.\n1 Section one."},
               {"name": "As Amended by the House", "date": "2027-03-10",
                "text": "AN ACT as amended.\n1 Section one, amended."}]
        assert hb["title"] == "HB1 of 2027-2028" and hb["events"] and hb["committees"] == ["Finance"] \
            and hb["outcome"] == "active" and hb["roll_calls"] == 1 and hb["versions"] == two \
            and hb["text_on_file"] is True, hb
        assert [x["path"] for x in text_rows] == ["/data/bill-texts-2027-2028.jsonl.gz",
                                                  "/data/bill-texts-2025-2026.jsonl.gz"] and \
            made_t == {"2027-2028/HB1": {"key": "2027-2028/HB1", "versions": two, "text_on_file": True},
                       "2025-2026/HB1": {"key": "2025-2026/HB1", "versions": [], "text_on_file": False},
                       "2025-2026/SB2": {"key": "2025-2026/SB2", "versions": [
                           {"name": "FINAL VERSION", "date": None, "text": "AN ACT, chaptered."}],
                           "text_on_file": True}}, (text_rows, made_t)
        assert made["rollcalls/2027-2028/2027-H-1.json"]["ballots"] == [
            {"member_id": "m1", "person": "100", "member": "Member, A", "party": "R", "vote": "Yea"}], \
            made["rollcalls/2027-2028/2027-H-1.json"]
        m = made["members/100.json"]
        assert m["seat"]["committees"] == ["Finance", "Rules"] and m["seat"]["recorded_votes"] == 120 \
            and m["sponsored"] == [{"key": "2025-2026/SB2", "prime": False},
                                   {"key": "2027-2028/HB1", "prime": True}], m
        assert made["members/101.json"] == {"format": 1, "person": "101", "replaced_by": "100",
                                            "sponsored": []}, made["members/101.json"]
        # Its text, in its own file alone, null until the night has read it (17 November 2026).
        assert made["requests/2027/0001.json"] == {
            "format": 1, "lsr": "2027-0001", "year": 2027, "title": "a request", "sponsor": "A Member",
            "cosponsors": ["B. Two"], "body": "HB", "status": "Filed", "withdrawn": False,
            "bill": "2027-2028/HB1", "text": None, "text_pdf": ""}, made["requests/2027/0001.json"]
        assert "text" not in made["requests/2027/index.json"]["requests"][0], \
            "the rows of the requests carry their text"
        assert made["index.json"]["sitting_term"] == "2027-2028" and \
            made["index.json"]["requests_year"] == 2027, made["index.json"]
        assert any("api/laws/" in s and "not written" in s for s in said), said
        try:
            AR.held("bills", "record", {"format": 1, "key": "x", "narrative": "a page's"}, "t")
            stopped = False
        except SystemExit:
            stopped = True
        assert stopped, "a bill's file carrying a page's field was written, not stopped"

    # THE REAL RECORD, where a site/ built from it carries /api/ (the laptop's
    # after a build): a sample of the sitting term's bills and of the chapters.
    real, said_real = Path("site"), "no site/ built from the real record here carries /api/"
    if (real / "api" / "index.json").is_file() and (real / "laws").is_dir():
        rix = json.loads((real / "api" / "index.json").read_text(encoding="utf-8"))
        term = rix["sitting_term"]
        ids = sorted((str(r["year"]), r["id"]) for r in SR.bill_index(real) if r["term"] == term)
        recs = [SR.one(real, y, b) for y, b in ids[::max(1, len(ids) // 25)]]
        for r in recs:
            f = json.loads((real / "api" / "bills" / term / f"{r['id']}.json").read_text(encoding="utf-8"))
            assert as_text(f["versions"]) == _api_bill_text_expected(real, r), \
                f"{term}/{r['id']}'s text in /api/ is not what its Bill Text tab shows"
        chs = sorted(p.stem for p in (real / "api" / "laws").glob("*.json") if p.stem != "index")
        for ch in chs[::max(1, len(chs) // 25)]:
            law = json.loads((real / "api" / "laws" / f"{ch}.json").read_text(encoding="utf-8"))
            page = BR.chapter_file(real / "laws", ch).read_text(encoding="utf-8")
            for s in law["sections"]:
                if not s["repealed"]:
                    shown = _api_law_page_text(page, "s" + s["section"].split(":", 1)[1])
                    assert shown and (s["text"].split("\n") if s["text"] else []) == shown[0], \
                        f"{s['section']}'s text in /api/ is not what its chapter's page shows"
        said_real = (f"and of the real record's, {len(recs)} of {term}'s bills and "
                     f"{len(chs[::max(1, len(chs) // 25)])} chapters against their pages")
    return "ok", (f"the fixture's {len(got):,} files under /api/ each say format 1 and carry only "
                  f"stable fields; {sitting}'s {len(per_bill)} bills and {len(per_rc)} roll calls a "
                  f"file each, no other term's; {len(terms)} term(s) of rows and of texts, "
                  f"{n_text} bill(s) with text and the rest saying they have none; {n_sec} sections' "
                  "text and notes as their pages show them; index.json, schema.json and the /api "
                  "page agree; a made-up record's members, request, versions, newer term and stale "
                  f"file each as promised; {said_real}")


@check("build", "the API's change feed lists, each night, exactly the records whose promised fields "
                "changed and those gone -- a page's field or the day the laws were taken is no "
                "change -- keeps eight nights, merges a second build of one date, and lists "
                "nothing, saying why, with no hashes to compare",
       needs=("api_records", "api_schema", "follow_changes"))
def _api_changes(AR, AS, FC):
    """THE CHANGE FEED (api_records.py; the owner's word of 16 November 2026):
    /api/changes/<date>.json, {"format": 1, "date", "built", "changed":
    {bills, rollcalls, members, laws, requests}, "removed": {...}}, a change
    being a change of a field the API promises. Driven here over a record made
    up for it, night after night, the hashes kept between nights as nightly.py
    keeps them (archive/api-hashes.next.json to archive/api-hashes.json):

      no hashes        the first night lists nothing, never every record, and
                       says so; its eight files are there
      a night's change one of each kind planted -- a bill's docket line, its
                       text, a roll call's tally, a ballot, a member's seat, a
                       section's text, a request's status, a request gone and
                       a bill new -- listed, exactly; and changes no promise
                       covers -- a bill's narrative and stations -- not listed
      a second build   of the same date, after the first was kept: what the
                       first listed and what changed since; and after it was
                       not kept, everything since the last kept night
      the turn         a new term's first bill: the old term's roll calls lose
                       their ballots' files and are not listed for it; and the
                       statutes taken again the same night, no word changed,
                       list no chapter
      eight nights     each build writes the eight nights' files, and the
                       hashes keep no older night
      a later ledger   hashes dated after tonight are not compared with
    """
    import csv as _csv_
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        led, nxt = d / "archive" / "api-hashes.json", d / "archive" / "api-hashes.next.json"

        def build(tonight, s):
            """One build over state `s`; (what it said, {date: the night's file})."""
            site, out, db = d / "site", d / "site" / "data", d / "db"
            for p in (site / "idx", out, db):
                p.mkdir(parents=True, exist_ok=True)
            idx = {}
            for key, b in s["bills"].items():
                t, bid = key.split("/")
                idx.setdefault(t, []).append({"id": bid, "year": int(t[:4]) + 1, "term": t,
                                              "title": b["title"], "kind": "active", "status": "s",
                                              "chip": "c", "committees": [], "nrc": 0, "rail": []})
            for p in (site / "idx").glob("*.json"):
                p.unlink()
            for t, rows in idx.items():
                (site / "idx" / f"{t}.json").write_text(json.dumps(rows), encoding="utf-8")
            (site / "idx" / "2027-requests.json").write_text(json.dumps([
                {"n": f"LSR 2027-{n}", "year": 2027, "title": "a request", "sponsor": "A Member",
                 "body": "HB", "status": st, "withdrawn": False, "address": f"request/2027-{n}"}
                for n, st in s["requests"].items()]), encoding="utf-8")
            (site / "meta.json").write_text(json.dumps(
                {"terms": sorted(idx, reverse=True),
                 "requests": {"term": "2027-requests", "year": 2027}}), encoding="utf-8")

            def put(name, cols, rows):
                with (out / name).open("w", encoding="utf-8", newline="") as fh:
                    w = _csv_.writer(fh)
                    w.writerow(cols)
                    w.writerows(rows)
            put("rollcalls.csv", list(AS.CSV["rollcalls.csv"]),
                [[rc, t, rc[:4], "H", rc.split("-")[-1], f"{rc[:4]}-03-01", "HB1", "q", "", y, "100",
                  "0", "1", "0", "", "", "count"] for rc, t, y in s["rollcalls"]])
            for p in out.glob("votes-*.csv"):
                p.unlink()
            for t in idx:
                put(f"votes-{t}.csv", list(AS.CSV["votes-<term>.csv"]),
                    [[rc, t, "2026-03-01", "HB1", "q", "m1", "Member, A", "R", "House", v]
                     for rc, (tt, v) in s["ballots"].items() if tt == t])
            put("legislators.csv", list(AS.CSV["legislators.csv"]),
                [["m1", "A Member", "House", "Republican", s["district"], "Belknap", "", "", "1",
                  "2", "100"]])
            put("sponsors.csv", list(AS.CSV["sponsors.csv"]), [])
            (db / "_columns.json").write_text(json.dumps({"NH_RSA": [
                "id", "TitleNo", "ChapterNo", "SectionNo", "Title", "Chapter", "Section",
                "SourceNote", "rsa", "EntireRSA", "titleNumber", "url"]}), encoding="utf-8")
            (db / "_manifest.json").write_text(json.dumps(
                {"NH_RSA": {"rows": 1, "fetched": s["taken"] + "T20:53:02"}}), encoding="utf-8")
            (db / "NH_RSA.psv").write_text("|".join([
                "1", "VI", "91-A", "91-A-4", "TITLE VI PUBLIC OFFICERS AND EMPLOYEES",
                "CHAPTER 91-A ACCESS TO GOVERNMENTAL RECORDS AND MEETINGS",
                "Section 91-A:4 Minutes and Records.", "<p><b>Source.</b> 1967, 251:1. </p>", "",
                f"<codesect> {s['section']}</codesect>", "6", "VI\\91-A\\91-A-4.htm"]) + "\n",
                encoding="utf-8")
            (d / "rsa_citations.json").write_text(json.dumps(
                {"enacted": {"91-A:4": [["1967", "251:1", ""]]}, "asof": {"laws_through": 2025}}),
                encoding="utf-8")
            rec = AR.Records([r for rows in idx.values() for r in rows], site)
            for key, b in s["bills"].items():
                t, bid = key.split("/")
                rec.add_bill(t, {"id": bid, "year": int(t[:4]) + 1, "term": t, "title": b["title"],
                                 "events": [{"date": "2026-01-05", "text": b["events"]}],
                                 "billtext": {"version": "Introduced", "body": b["text"]},
                                 "narrative": b["narrative"], "stations": [{"when": b["station"]}]})
            people = [{"person": "100", "name": "A Member", "member_ids": ["m1"], "sitting": True}]
            _sum, said = AR.write(site, out, rec, people=people, person_of={"m1": "100"},
                                  base="https://example.org", built=f"{tonight}T09:00:00Z",
                                  db=db, citations=d / "rsa_citations.json", ledger=led,
                                  ledger_out=nxt)
            nights = {p.stem: json.loads(p.read_text(encoding="utf-8"))
                      for p in (site / "api" / "changes").glob("*.json")}
            return said, nights

        def keep():
            os.replace(nxt, led)

        def listed(f, side="changed"):
            return {k: v for k, v in f[side].items() if v}

        bill = lambda **k: {"title": "t", "events": "Introduced", "text": "AN ACT.", "narrative": "n",
                            "station": "x", **k}
        s = {"bills": {"2025-2026/HB1": bill(), "2025-2026/HB2": bill(), "2025-2026/HB3": bill()},
             "rollcalls": [("2026-H-1", "2025-2026", "201"), ("2026-H-2", "2025-2026", "150")],
             "ballots": {"2026-H-1": ("2025-2026", "Yea"), "2026-H-2": ("2025-2026", "Nay")},
             "district": "1", "section": "I. Every citizen may inspect.", "taken": "2026-09-08",
             "requests": {"0001": "Requested", "0002": "Requested"}}
        said, nights = build("2026-11-10", s)
        assert sorted(nights) == FC.window("2026-11-10") and \
            all(not listed(f) and not listed(f, "removed") and f["format"] == 1
                for f in nights.values()), ("a night with no hashes listed something", nights)
        assert any("WARNING" in x and "api-hashes.json" in x for x in said), said
        assert set(nights["2026-11-10"]) == {"format", "date", "built", "changed", "removed"} and \
            list(nights["2026-11-10"]["changed"]) == list(AR.KINDS), nights["2026-11-10"]
        keep()

        # ONE OF EACH KIND, and three changes no promise covers.
        s["bills"]["2025-2026/HB1"] = bill(events="Referred to Finance")
        s["bills"]["2025-2026/HB2"] = bill(narrative="told anew", station="moved")
        s["bills"]["2025-2026/HB3"] = bill(text="AN ACT, amended.")
        s["bills"]["2025-2026/HB4"] = bill()
        s["rollcalls"][0] = ("2026-H-1", "2025-2026", "202")
        s["ballots"]["2026-H-2"] = ("2025-2026", "Yea")
        s["district"] = "2"
        s["section"] = "I. Every citizen may inspect and copy."
        s["requests"] = {"0001": "Filed"}
        said, nights = build("2026-11-11", s)
        want = {"bills": ["2025-2026/HB1", "2025-2026/HB3", "2025-2026/HB4"],
                "rollcalls": ["2026-H-1", "2026-H-2"], "members": ["100"], "laws": ["91-A"],
                "requests": ["2027-0001"]}
        assert listed(nights["2026-11-11"]) == want and \
            listed(nights["2026-11-11"], "removed") == {"requests": ["2027-0002"]}, \
            ("the night does not list exactly the records whose promised fields changed",
             nights["2026-11-11"])
        assert not listed(nights["2026-11-10"]), "a kept night's file was rewritten with tonight's"
        keep()

        # A SECOND BUILD OF THE SAME DATE: kept, then one more change.
        s["bills"]["2025-2026/HB2"] = bill(title="retitled")
        said, nights = build("2026-11-11", s)
        assert listed(nights["2026-11-11"])["bills"] == ["2025-2026/HB1", "2025-2026/HB2",
                                                        "2025-2026/HB3", "2025-2026/HB4"], \
            ("a second build of one date dropped what the first listed", nights["2026-11-11"])
        # ... and not kept: the next build of the date compares with the kept one.
        s["requests"] = {"0001": "Filed", "0003": "Requested"}
        said, nights = build("2026-11-11", s)
        assert listed(nights["2026-11-11"])["requests"] == ["2027-0001", "2027-0003"] and \
            listed(nights["2026-11-11"])["bills"] == ["2025-2026/HB1", "2025-2026/HB2",
                                                     "2025-2026/HB3", "2025-2026/HB4"], nights["2026-11-11"]
        keep()

        # THE TURN: the new term's first bill takes the files a record, and the
        # old term's roll calls, losing their ballots' file, are not listed;
        # nor is the chapter, its table taken again with no word of it changed.
        s["taken"] = "2026-09-15"
        s["bills"]["2027-2028/HB1"] = bill()
        s["rollcalls"].append(("2027-H-1", "2027-2028", "300"))
        s["ballots"]["2027-H-1"] = ("2027-2028", "Yea")
        said, nights = build("2026-12-03", s)
        assert listed(nights["2026-12-03"]) == {"bills": ["2027-2028/HB1"], "rollcalls": ["2027-H-1"]} \
            and not listed(nights["2026-12-03"], "removed"), \
            ("the turn of a term listed records that did not change", nights["2026-12-03"])
        hashes = json.loads(nxt.read_text(encoding="utf-8"))
        assert sorted(hashes["nights"]) == ["2026-12-03"] and sorted(nights) == FC.window("2026-12-03"), \
            ("the hashes keep a night older than the eight the folder carries", sorted(hashes["nights"]))
        keep()

        # HASHES DATED AFTER TONIGHT are not compared with.
        said, nights = build("2026-11-20", s)
        assert not listed(nights["2026-11-20"]) and any("WARNING" in x and "after tonight" in x
                                                         for x in said), said
    return "ok", ("no hashes: nothing listed and said; one of each kind listed exactly, a page's "
                  "fields and the day the laws were taken not; a second build of a date keeps the "
                  "first's list, and one not kept compares with the kept; the turn lists only the "
                  "new term's; eight nights; later hashes refused")


@check("build", "the page of numbers' log names an amendment it leaves off, and the Learn and "
                "data pages say whose the voters' counts are, built from the file")
def _ballot_said_built():
    """build_civics and build_exports run over the fixture site with a
    ballot_results.json of three sources and a decided row with no cite (the
    review of 7 October 2026). learn_numbers leaves that row off its table
    and names it in learn_numbers.HELD, and build_civics prints it -- a line
    nothing held to being printed, so taking the loop out failed no check.
    And the two sentences that say whose the counts are, the page of numbers'
    and the data page's, were held to their rows only by calling the
    functions behind them, where a page that wrote a name of its own in
    place of the function's answer passed.

    Fails on build_civics leaving out the LEAVES OFF line, on the page of
    numbers not saying both sources with their counts, on the data page not
    saying what ballot_words says of the same rows, and on either page
    showing the row with no cite."""
    for s in ("build_civics.py", "build_exports.py"):
        if not _paths.locate(s).exists():
            return "skip", f"{s} is not here"
    import html as _html
    root = Path(tempfile.mkdtemp(prefix="gr-ballot-said-"))
    try:
        base, _ran = _fixture_site_whole(root)
        sos, bp, uncited, pending = _ballot_mixed_rows()
        _mk(root / "corrections" / "ballot_results.json").write_text(
            json.dumps({"rows": [sos, bp, uncited, pending]}), encoding="utf-8")
        said = {}
        for s in ("build_civics.py", "build_exports.py"):
            r = _run([sys.executable, _paths.script(s), "--site", "site", "--base", base],
                     cwd=root, capture_output=True, text=True, timeout=180)
            assert r.returncode == 0, f"{s} failed: " + (r.stderr or r.stdout or "")[-400:]
            said[s] = r.stdout or ""

        def text(p):
            h = (root / "site" / p).read_text(encoding="utf-8")
            return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", h)))

        numbers, data = text("learn/by-the-numbers.html"), text("data.html")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    bad = []
    left = ("learn/by-the-numbers.html LEAVES OFF CACR7 of 1991-1992: ballot_results.json "
            "gives it no cite")
    if left not in said["build_civics.py"]:
        bad.append("build_civics does not log the row it leaves off: "
                   + said["build_civics.py"][-300:])
    # The table runs by election, and so does the count of whose: 1998's
    # Ballotpedia row before 2024's.
    want = ("Yes and No are the statewide count printed where the Source column says: "
            "Ballotpedia's for 1, the Secretary of State's for 1. 0 of the 2 below were ratified.")
    if want not in numbers:
        i = numbers.find("Constitutional Amendments Sent to the Voters")
        bad.append(f"the page of numbers says {numbers[i:i + 600]!a}")
    if "CACR 7" in numbers[numbers.find("Constitutional Amendments Sent to the Voters"):]:
        bad.append("the page of numbers shows the row with no cite")
    words = ("the statewide Yes and No votes on each of the 3 the voters have decided, with "
             "where each count is printed and the day it was read: the Secretary of State's "
             "for 2, Ballotpedia's for 1, and Ballotpedia's figures beside 1 of them as a "
             "cross-check; "
             "for the one still to go to the voters, Ballotpedia's listing of the question")
    if f"no script writes: {words}." not in data:
        i = data.find("no script writes")
        bad.append(f"the data page says {data[i:i + 500]!a}")
    assert not bad, "; ".join(bad)
    return "ok", ("build_civics logs the row with no cite it leaves off; the page of numbers "
                  "and the data page name the Secretary of State and Ballotpedia, each counted, "
                  "from the rows")


@check("build", "a term that loses a fifth of its rows is refused even when the table is not")
def _proceedings_term_shrink():
    """build_proceedings refused to shrink by a fifth when the table held one
    term. It holds every term now, and a rebuild that leaves
    verification_manifest_2023-2024.csv out loses 6,998 docket rows while
    keeping 87% of the table -- inside the old guard's allowance, so the term
    would have left the site with nothing said. The guard now also counts
    rows per (term, source).

    The same thing in miniature: a prior table of 150 rows of 2023-2024 and
    1,000 of 2025-2026, every one saying `manifest`, as each table written
    before calendar rows did. A rebuild from both manifests goes through,
    because `manifest` is the docket under its old name rather than a source
    that vanished. Without the 2023-2024 manifest the table keeps 87% and is
    refused, naming that term and no other, and left as it was.
    --allow-shrink lets it through.
    """
    need = PROCEEDINGS_MODULES
    absent = [f for f in need if not _paths.locate(f).exists()]
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    import importlib.util
    root = Path(tempfile.mkdtemp(prefix="gr-termshrink-"))
    try:
        for f in need:
            (root / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(_paths.locate(f), root / f)
        # The copy's own write(), under a name of its own, so no later check
        # that imports proceedings is handed a module from a deleted folder.
        spec = importlib.util.spec_from_file_location(
            "_termshrink_proceedings", root / "proceedings.py")
        P = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(P)
        cols = ["bill", "body", "committee", "proceeding", "sched_date",
                "sched_time", "venue", "tier", "bills_in_slot", "match",
                "video_id", "video_title", "stream_start", "predicted_offset",
                "watch_url", "candidates", "observed_start", "observed_end",
                "notes"]
        prior = []
        for term, name, day, n in (
                ("2023-2024", "verification_manifest_2023-2024.csv",
                 "2024-02-06", 150),
                ("2025-2026", "verification_manifest.csv", "2026-02-03", 1000)):
            with (root / name).open("w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(cols)
                for i in range(1, n + 1):
                    w.writerow([f"HB{i}", "H", "Judiciary", "public hearing",
                                day, "10:00", "LOB 206", "A", 1,
                                "no video found"] + [""] * 9)
                    prior.append({"term": term, "bill": f"HB{i}", "body": "H",
                                  "kind": "public hearing", "date": day,
                                  "time": "10:00", "committee": "Judiciary",
                                  "venue": "LOB 206",
                                  "match": "no video found",
                                  "source": "manifest"})
        table = root / "proceedings.csv"

        def rebuild(*args):
            """The prior table put back, then one run over it. An inherited
            GRANITE_PROCEEDINGS is emptied so the child writes here."""
            P.write(prior, table)
            was = table.read_bytes()
            r = _run([sys.executable, "build_proceedings.py", *args],
                     cwd=root, capture_output=True, text=True, timeout=120,
                     env={"GRANITE_PROCEEDINGS": ""})
            return r, was

        r, _ = rebuild()
        assert r.returncode == 0, (
            "a rebuild from both manifests was refused; a prior `manifest` "
            "row is the docket's and must count as `docket`: "
            + ((r.stdout or "") + (r.stderr or "")).strip()[-300:])
        got = Counter((x["term"], x["source"]) for x in P.load(table))
        assert got == {("2023-2024", "docket"): 150,
                       ("2025-2026", "docket"): 1000}, (
            f"the rebuild from both manifests wrote {dict(got)}; wanted 150 "
            "docket rows of 2023-2024 and 1,000 of 2025-2026")

        (root / "verification_manifest_2023-2024.csv").unlink()
        r, was = rebuild()
        err = (r.stderr or "").strip()
        assert r.returncode != 0, (
            "without the 2023-2024 manifest the table kept 1,000 of 1,150 "
            "rows, 87%, and the rebuild went through: a whole term left the "
            "table with nothing said")
        assert "2023-2024" in err, (
            "refused, but the message does not name the term that lost its "
            "rows: " + err[-300:])
        assert "2025-2026" not in err, (
            "the refusal names 2025-2026 too, which lost nothing: "
            + err[-300:])
        assert table.read_bytes() == was, (
            "the rebuild was refused and still rewrote the table")

        r, _ = rebuild("--allow-shrink")
        assert r.returncode == 0, (
            "--allow-shrink did not let the smaller table through: "
            + ((r.stdout or "") + (r.stderr or "")).strip()[-300:])
        kept = Counter(x["term"] for x in P.load(table))
        assert kept == {"2025-2026": 1000}, (
            f"--allow-shrink wrote {dict(kept)}; wanted 1,000 rows of 2025-2026")
        return "ok", ("150 + 1,000 `manifest` rows rebuild as docket; without "
                      "2023-2024's manifest the table keeps 87% and the "
                      "rebuild is refused by that term's name; --allow-shrink "
                      "writes it")
    finally:
        shutil.rmtree(root, ignore_errors=True)


# THE ADDRESS A LINK NAMES IS THE ONE THE HOST SERVES (Search Console, 7
# November 2026: 25,718 pages indexed, 18,786 discovered and not, 6,896 "page
# with redirect"). shell.clean_links turns the .html out of every href a
# builder writes as HTML; the links a script draws -- app.js, components.js,
# find.js, map.js, live.js, the home page's and the Officials page's inline
# scripts, and the HTML the calendar's month files carry -- are outside it
# ("never inside a <script>") and were 6,896 redirects a crawler followed.
# The rules the .html in code may still be: a regex that reads an address, the
# local-server fallback (fetch(url+".html"), r:fetch(...)), the key a script looks a page up
# by (GR_HREFS["search.html"]), the calendar's own TAB, a property called html.
_CLEAN_JS = ("app.js", "components.js", "find.js", "map.js", "live.js")
_HTML_IN_CODE = re.compile(r'(?<!\\)(?<=[\w$})\]])\.html(?=["\'`#?\\])')
_HTML_OK = re.compile(r'GR_HREFS|\.test\(|\.replace\(/|[^\w]TAB=|r:fetch\(|url\+"\.html"|"\.html"')
_HREF_IN_DATA = re.compile(r'(?:href|data-href)=\\?"([^"\\]*)')
_COMMENTS = re.compile(r"/\*.*?\*/|(?:(?<=\s)|^)//[^\n]*", re.S | re.M)


def _html_in_script(text):
    """[line] of a script's code where an address with .html is built."""
    out = []
    for line in _COMMENTS.sub("", text).splitlines():
        if _HTML_IN_CODE.search(line) and not _HTML_OK.search(line):
            out.append(line.strip()[:140])
    return out


@check("build", "no link, in a page or in an address a script builds, names a .html page or an "
       "address _redirects redirects")
def _addresses_clean():
    """Every internal link at the address the host serves, in the HTML as
    written and in what the scripts draw.

    Builds the fixture site (the run's one build) and holds four things:
      1. every href, src and data-href in every built page, outside script
         and style bodies, resolved as a browser does, is not a path
         _redirects answers with a 301, does not end in .html, and does not
         end in a slash where the page is a file (/calendar/ for calendar.html);
      2. the same of every href inside the HTML the month files of the
         calendar carry (site/calendar/data/*.json);
      3. app.js, components.js, find.js, map.js and live.js build no address
         ending in .html (the allowed shapes are _HTML_OK's);
      4. nor do the scripts inside the built pages, which are the Python
         builders' own: the home page's, the Officials page's.
    A .html in a GR_HREFS key, a regex or a fallback fetch is not a link.
    """
    from urllib.parse import urldefrag, urljoin
    if [x for x in CHAIN_NEEDS if not _paths.locate(x).exists()]:
        return "skip", "the builders are not here to build the fixture's site"
    here = Path(".").resolve()
    site = _fixture_site_shared()[0] / "site"
    moved = {}
    red = site / "_redirects"
    for line in (red.read_text(encoding="utf-8").splitlines() if red.exists() else []):
        p = line.split()
        if len(p) == 3 and p[2] == "301":
            moved["/" + p[0].strip("/")] = p[1]

    def wrong(path):
        """Why `path` is not a canonical address, or ''."""
        q = path.split("?")[0]
        if q != "/" and q.rstrip("/") in moved or q in moved:
            return f"_redirects sends it to {moved.get(q) or moved.get(q.rstrip('/'))}"
        if q.endswith(".html") and q != "/404.html":
            return "ends in .html, which the host redirects"
        if q != "/" and q.endswith("/") and (site / (q.strip("/") + ".html")).is_file():
            return "ends in a slash, which the host redirects"
        return ""

    bad, n = Counter(), 0
    where = {}

    def note(rel, raw, why):
        bad[(why, raw)] += 1
        where.setdefault((why, raw), rel)

    pages = sorted(site.rglob("*.html"))
    assert pages, "the fixture chain wrote no pages to check"
    scripts = []
    for page in pages:
        rel = page.relative_to(site).as_posix()
        full = page.read_text(encoding="utf-8", errors="replace")
        scripts += [(rel, s) for s in re.findall(r"(?is)<script(?![^>]*\btype=\"application/json\")[^>]*>(.*?)</script>", full)]
        text = INLINE_BODY.sub(r"\1", full)
        m = BASE_HREF.search(text)
        at = urljoin("https://x/" + rel, m.group(1) if m else "")
        for raw in re.findall(r'(?:href|src|data-href)\s*=\s*"([^"]*)"', text, re.I):
            raw = raw.strip()
            if not raw or OFFSITE.match(raw):
                continue
            target = urldefrag(urljoin(at, raw))[0]
            if not target.startswith("https://x/"):
                continue
            n += 1
            why = wrong(target[len("https://x"):])
            if why:
                note(rel, raw, why)
    for f in sorted((site / "calendar" / "data").glob("*.json")) if (site / "calendar" / "data").is_dir() else []:
        for raw in _HREF_IN_DATA.findall(f.read_text(encoding="utf-8", errors="replace")):
            if raw and not OFFSITE.match(raw):
                n += 1
                why = wrong("/" + raw.lstrip("/"))
                if why:
                    note(f.relative_to(site).as_posix(), raw, why)
    assert not bad, (
        f"{sum(bad.values())} links to {len(bad)} addresses the host does not serve as written: "
        + "; ".join(f"{k[1]!r} on {where[k]} ({k[0]})" for k, _ in bad.most_common(6)))

    built = []
    for name in _CLEAN_JS:
        src = here / "src" / "pages" / name
        if src.exists():
            built += [(name, l) for l in _html_in_script(src.read_text(encoding="utf-8"))]
    for rel, body in scripts:
        built += [(rel, l) for l in _html_in_script(body)]
    assert not built, (
        f"{len(built)} places a script builds an address ending in .html, which the host "
        "redirects: " + "; ".join(f"{w}: {l}" for w, l in built[:5]))
    return "ok", (f"{n:,} links in {len(pages)} fixture pages and the calendar's month files, "
                  f"none redirected or ending in .html; {len(_CLEAN_JS)} scripts and "
                  f"{len(scripts)} inline scripts build no .html address")


@check("build", "a bill with no filing year gets no feed, not one at the root")
def _feed_needs_a_year():
    """feed/bill/<year>/<id>.xml is the only thing keeping two terms apart.

    build_feeds had no notion of a term at all. The path is built from
    b.get("year"), and a bill without one collapsed it to feed/bill/<id>.xml --
    where the next term's bill of the same number lands on top. It is 2,233 of
    the site's 8,017 files, so this is the largest single place a bill number
    was still standing in for a bill.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_feeds.py").exists():
        return "skip", "build_feeds.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        site = root / "site"
        (site / "bill" / "2026").mkdir(parents=True)
        rows = [{"id": "HB1", "n": "HB 1", "year": 2026, "term": "2025-2026",
                 "title": "a bill with a year", "committee": "", "topic": "",
                 "status": "In committee", "kind": "active", "nrc": 0,
                 "last_action": "2026-02-01", "votedays": []},
                {"id": "HB2", "n": "HB 2", "year": "", "term": "2025-2026",
                 "title": "a bill with none", "committee": "", "topic": "",
                 "status": "In committee", "kind": "active", "nrc": 0,
                 "last_action": "2026-02-01", "votedays": []}]
        _bill_index_write(site, rows)
        # Records travel inside their pages, as build_bill_pages writes them.
        # This fixture used to write site/bills/2026/<ID>.json, the layout the
        # site stopped having on 9 September -- so it went on passing while
        # build_feeds read that dead path and skipped every real bill.
        d = {"next_step": "", "sponsors": [],
             "events": [{"date": "2026-02-01", "text": "It was introduced."}]}
        for r in rows:
            # HB2's page sits in a year folder, but the index gives it no
            # year: a record the index cannot place must still get no feed.
            # (Its term it has: every row of the index is in its term's file.)
            (site / "bill" / "2026" / f"{r['id'].lower()}.html").write_text(
                '<script type="application/json" id="gr-data">'
                + json.dumps(d) + "</script>", encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_feeds.py"),
                            "--site", "site", "--base", "https://x.test"],
                           cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-160:]
        assert (site / "feed" / "bill" / "2026" / "hb1.xml").exists(),             "the bill WITH a year got no feed"
        stray = sorted(p.name for p in (site / "feed" / "bill").glob("*.xml"))
        assert not stray, (f"a feed was written to feed/bill/ with no year in "
                           f"the path: {stray}")
        # And the guid says which term, so two terms' HB1 cannot collide.
        x = (site / "feed" / "bill" / "2026" / "hb1.xml").read_text(encoding="utf-8")
        assert "2025-2026:HB1:" in x, "the guid does not carry the term"
        return "ok", "no year, no feed; and the guid names the term"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a feed is keyed the way its page is, links the address the host serves, and none is left stale")
def _feeds_keyed_and_current():
    """Three defects found on 12 September, one fix each.

    Committee feeds were keyed on the name as the search index spells it --
    274 feeds for 53 committees, six for one -- while the page is
    /committee/H05, so a Follow button had no stable address to name. Every
    feed link ended in .html, which the host answers with a 308. And nothing
    removed a feed that stopped being written: 7,505 per-bill feeds of closed
    terms and the 274 name-keyed committee feeds were shipped long after
    anything updated them. The prune refuses a large fall unless told, since
    a failed run would otherwise unpublish every feed and call it housekeeping.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_feeds.py").exists():
        return "skip", "build_feeds.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        site = root / "site"
        (site / "bill" / "2026").mkdir(parents=True)
        (site / "committee").mkdir()
        rows = [{"id": "HB1", "n": "HB 1", "year": 2026, "term": "2025-2026",
                 "title": "a bill", "committee": "House Education", "topic": "",
                 "status": "In committee", "kind": "active", "nrc": 0,
                 "last_action": "2026-02-01", "votedays": []}]
        _bill_index_write(site, rows)
        d = {"next_step": "", "sponsors": [],
             "events": [{"date": "2026-02-01", "text": "It was introduced."}]}
        (site / "bill" / "2026" / "hb1.html").write_text(
            '<script type="application/json" id="gr-data">' + json.dumps(d) + "</script>",
            encoding="utf-8")
        (site / "committee" / "H05.json").write_text(json.dumps({
            "code": "H05", "name": "Education", "chamber": "House", "bills": {},
            "sessions": [{"date": "2026-01-20", "term": "2025-2026",
                          "narrative": "The Committee on Education met on January 20, 2026.",
                          "items": [{"bill": "HB1", "n": "HB 1"}]}]}), encoding="utf-8")
        stale = [site / "feed" / "committee" / "house-education.xml",
                 site / "feed" / "bill" / "2017" / "hb9.xml"]
        for p in stale:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("<rss/>", encoding="utf-8")

        def build(*extra):
            r = _run([sys.executable, _paths.script("build_feeds.py"), "--site", "site",
                      "--base", "https://x.test", *extra],
                     cwd=root, capture_output=True, text=True, timeout=120)
            assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
            return r.stdout

        out = build()
        cf = site / "feed" / "committee" / "H05.xml"
        assert cf.exists(), "no feed at /feed/committee/H05.xml, where the page's code says"
        x = cf.read_text(encoding="utf-8")
        assert "committee:H05:2026-01-20" in x and "met on January 20, 2026" in x, \
            "the committee feed is not its sitting days"
        assert all(p.exists() for p in stale), "stale feeds were removed without --allow-prune"
        assert "LEFT" in out, "a large fall was left without saying so"
        build("--allow-prune")
        assert not any(p.exists() for p in stale), "stale feeds survived --allow-prune"
        assert not (site / "feed" / "bill" / "2017").exists(), "an emptied folder was left"
        links = []
        for f in (site / "feed").rglob("*.xml"):
            links += re.findall(r"<link>([^<]+)</link>", f.read_text(encoding="utf-8"))
        assert links and not [l for l in links if l.endswith(".html")], \
            "a feed links an address the host redirects: " + str([l for l in links if l.endswith(".html")][:3])
        return "ok", "committee feed at its code, from its sitting days; no .html links; stale pruned only when told"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a legislator's feed dates each vote the day it was cast, newest first, and links the bill's own page")
def _legislator_feed_dates():
    """A member file writes a vote's date as the roll call export does,
    8/19/2026, and build_feeds read it as if it were 2026-08-19.

    Three defects from that one misreading, all in every legislator feed on
    the site until 13 September. rfc822() could not parse the date and gave
    every vote the build time as its pubDate. newest() sorted the raw strings,
    so 9/4/2025 came before 8/19/2026 and 12/2/2025 after both, and the sixty
    items a feed keeps were chosen in that order. And find() took the term
    from the date's first four characters, "8/19", found none, and linked the
    generic bills page for any bill number used in more than one term.

    The guid keeps the date as the member file writes it, so a reader already
    subscribed does not see every vote again as new.
    """
    from datetime import datetime
    here = Path(".").resolve()
    if not _paths.locate("build_feeds.py").exists():
        return "skip", "build_feeds.py not here"
    root = Path(tempfile.mkdtemp(prefix="gr-legfeed-"))
    try:
        site = root / "site"
        # HB221 in two terms, so only the vote's own date can say which bill
        # a vote was on.
        rows = [{"id": "HB221", "n": "HB 221", "year": year, "term": term,
                 "title": f"a bill of {term}", "committee": "", "topic": "",
                 "status": "In committee", "kind": "active", "nrc": 0,
                 "last_action": f"{year}-02-01", "votedays": []}
                for year, term in ((2023, "2023-2024"), (2025, "2025-2026"))]
        (site / "legislators").mkdir(parents=True)
        _bill_index_write(site, rows)
        for r in rows:
            page = site / "bill" / str(r["year"]) / "hb221.html"
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_text('<script type="application/json" id="gr-data">'
                            + json.dumps({"next_step": "", "sponsors": [], "events": []})
                            + "</script>", encoding="utf-8")
        (site / "legislators.json").write_text(json.dumps(
            [{"id": "10004", "display": "Rep. Example", "n_votes": 3}]), encoding="utf-8")
        # Out of order on purpose, the way the strings sort: 9/4 above 8/19
        # above 12/2.
        votes = [{"d": d, "b": "HB221", "q": q, "v": v} for d, q, v in (
            ("9/4/2025", "Ought to Pass", "Yea"),
            ("8/19/2026", "Veto Override", "Nay"),
            ("12/2/2025", "Inexpedient to Legislate", "Yea"))]
        (site / "legislators" / "10004.json").write_text(
            json.dumps({"votes": votes}), encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_feeds.py"), "--site", "site",
                  "--base", "https://x.test"],
                 cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
        f = site / "feed" / "legislator" / "10004.xml"
        assert f.exists(), "no feed was written for a member with three votes"
        x = f.read_text(encoding="utf-8")
        items = re.findall(r"<item>.*?</item>", x, re.S)
        got = [re.search(r"<pubDate>([^<]+)</pubDate>", i).group(1) for i in items]
        want = [datetime.strptime(d, "%Y-%m-%d").strftime("%a, %d %b %Y 00:00:00 +0000")
                for d in ("2026-08-19", "2025-12-02", "2025-09-04")]
        assert got == want, (
            f"pubDates {got}; wanted the day each vote was cast, newest first: {want}")
        links = [re.search(r"<link>([^<]+)</link>", i).group(1) for i in items]
        assert all(l == "https://x.test/bill/2025/hb221" for l in links), (
            f"a vote of the 2025-2026 term links {sorted(set(links))}, not "
            "https://x.test/bill/2025/hb221")
        assert "vote:10004:HB221:8/19/2026:" in x, (
            "the guid changed shape, so every subscriber would see each vote again")
        return "ok", ("three votes dated as cast, newest first, each linking HB 221 of "
                      "2025-2026 though HB221 exists in two terms; guids unchanged")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a reports file keyed on bill number is refused, not ignored")
def _reports_old_shape():
    """The third and fourth files off ARCHITECTURE item 3, same silence.

    committee_reports.json and senate_reports.json are {term: {bill: [reports]}}
    now. Read either in the old flat shape with a term lookup and every bill
    comes back with no committee report -- no recommendation, no vote, no
    reasoning -- and the build exits zero.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    for name in ("committee_reports.json", "senate_reports.json"):
        root = Path(tempfile.mkdtemp())
        try:
            _site_fixture(root)
            nested = json.loads((root / name).read_text(encoding="utf-8"))
            flat = {b: r for byb in nested.values() for b, r in byb.items()}
            (root / name).write_text(json.dumps(flat), encoding="utf-8")
            r = _run([sys.executable, _paths.script("build_site_v2.py"),
                                "--data", "data", "--out", "site",
                                "--segments", "work"],
                               cwd=root, capture_output=True, text=True,
                               timeout=180)
            assert r.returncode != 0, (
                f"the build accepted a {name} keyed on bill number and "
                "produced a site whose bills have no committee reports")
            said = (r.stdout + r.stderr).lower()
            assert "keyed on bill number" in said, (r.stdout + r.stderr)[-160:]
        finally:
            shutil.rmtree(root, ignore_errors=True)
    return "ok", "both reports files must name their term"


@check("build", "an archived term's bill cannot borrow the current term's text")
def _bills_by_term():
    """The last file the whole pipeline was driven from by bill number alone.

    data/bills.json is what build_bills loops over, so a bare bill number there
    puts two terms' bills under one key at the very top. It is {term: {bill:
    record}} now, and the loop runs over every term the file holds.

    testimony.json and sponsors.json are still flat, and HB100 exists in every
    biennium, so they are read ONLY for the term they describe. Showing an
    archived bill the CURRENT bill's sponsors would be worse than showing it
    none. bill_status.json and bill_text.json are keyed on the term now; the
    check below this one covers what an archived bill reads OUT of them.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
        # The same number in an earlier term, which the flat files also carry.
        old = dict(bills["2025-2026"]["HB1442"])
        old.update({"lsr_year": "2024", "lsr": "2024-0503",
                    "title": "an entirely different bill of the same number"})
        bills["2023-2024"] = {"HB1442": old}
        (root / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-160:]
        idx = {(x["term"], x["id"]): x for x in _site_bills(root / "site")}
        assert ("2023-2024", "HB1442") in idx, "the archived term produced no row"
        assert ("2025-2026", "HB1442") in idx, "the current term lost its row"

        a = json.loads((root / "site" / "bills" / "2024" / "HB1442.json")
                       .read_text(encoding="utf-8"))
        n = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                       .read_text(encoding="utf-8"))
        # sponsors.json is the flat file the fixture carries. text_url comes
        # from bill_status.json, which is keyed on the term: the fixture holds
        # only the current one, so the archived bill must still get nothing.
        assert n.get("sponsors"), "the current term's bill lost its sponsors"
        assert not a.get("sponsors"), (
            "the archived bill is showing the current term's sponsors")
        assert n.get("text_url"), "the current term's bill lost its text link"
        assert not a.get("text_url"), (
            "the archived bill is showing the current term's bill text link")
        return "ok", "two terms, one number, and neither borrows the other"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "an archived bill reads its own term's status and text")
def _termed_status_and_text():
    """The other half of the two-terms check, once the files can hold two.

    bill_status.json and bill_text.json were keyed on the bill number alone,
    and everything downstream leaned on that: an archived bill was given
    NOTHING from them, deliberately, because HB100 exists in every biennium and
    the current term's sponsors on a 2023 bill is worse than no sponsors.

    They are {term: {bill: record}} now, so an archived bill must read its own
    term out of them -- and still must not read the current term's. Both halves
    are asserted here, because a lookup that ignores the term passes the first
    half by accident: it hands back whatever record the flat file had.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        bills = json.loads((root / "data" / "bills.json").read_text(encoding="utf-8"))
        old = dict(bills["2025-2026"]["HB1442"])
        old.update({"lsr_year": "2024", "lsr": "2024-0503",
                    "title": "an entirely different bill of the same number"})
        # text_pdf off the bill record is the fallback for a term the status
        # file does not hold. Clearing it is what makes the assertion below
        # about the FILE rather than about the fallback.
        old.pop("text_pdf", None)
        bills["2023-2024"] = {"HB1442": old}
        (root / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")

        st = json.loads((root / "bill_status.json").read_text(encoding="utf-8"))
        if not all(re.match(r"^\d{4}-\d{4}$", k) for k in st):
            st = {"2025-2026": st}
        st["2023-2024"] = {"HB1442": {
            "gen_status": "SIGNED BY GOVERNOR", "house_status": "",
            "senate_status": "", "text_pdf": "https://gc.nh.gov/archived.pdf",
            "chapter": "", "lsr": "2024-0503", "body": "H"}}
        (root / "bill_status.json").write_text(json.dumps(st), encoding="utf-8")

        (root / "bill_text.json").write_text(json.dumps({
            "2025-2026": {"HB1442": {
                "version": "as introduced", "title": "the current bill",
                "text": "ANALYSIS\nThe current term's analysis.\n"
                        "Be it Enacted by the Senate and House"}},
            "2023-2024": {"HB1442": {
                "version": "as amended", "title": "the archived bill",
                "text": "ANALYSIS\nThe archived term's analysis.\n"
                        "Be it Enacted by the Senate and House"}},
        }), encoding="utf-8")

        r = _run([sys.executable, _paths.script("build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]

        a = json.loads((root / "site" / "bills" / "2024" / "HB1442.json")
                       .read_text(encoding="utf-8"))
        n = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                       .read_text(encoding="utf-8"))

        # text_url is the link AS PUBLISHED, not the raw scrape: the
        # session year is appended where the scrape did not carry one,
        # because billText.aspx without it answers with an ASP.NET error.
        assert (a.get("text_url") or "").startswith(
                "https://gc.nh.gov/archived.pdf"), (
            "the archived bill did not read its own term out of "
            f"bill_status.json; text_url is {a.get('text_url')!r}")
        assert n.get("text_url") != "https://gc.nh.gov/archived.pdf", (
            "the current bill took the ARCHIVED term's text link")

        at = (a.get("billtext") or {}).get("analysis", "")
        nt = (n.get("billtext") or {}).get("analysis", "")
        assert "archived term" in at, (
            f"the archived bill's text came from the wrong term: {at[:60]!r}")
        assert "current term" in nt, (
            f"the current bill's text came from the wrong term: {nt[:60]!r}")
        return "ok", ("status and text both follow the term, in both "
                      "directions")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a narratives.json keyed on bill number is refused, not ignored")
def _narratives_old_shape():
    """The same silence rollcalls.json had, on the file that drives everything.

    narratives.json is {term: {bill: record}} because bill numbers repeat every
    biennium. Read the old flat shape with a term lookup and every bill comes
    back with no history, no status, no reports and no events -- and the build
    succeeds.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        nested = json.loads((root / "narratives.json").read_text(encoding="utf-8"))
        flat = {b: r for byb in nested.values() for b, r in byb.items()}
        (root / "narratives.json").write_text(json.dumps(flat), encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode != 0, ("the build accepted a narratives.json keyed "
                                   "on bill number and produced a site whose "
                                   "bills have no history")
        said = (r.stdout + r.stderr).lower()
        assert "keyed on bill number" in said, (r.stdout + r.stderr).strip()[-160:]
        return "ok", "the build stops and says how to rebuild it"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "an in-progress status does not outrank a vote that ended the bill")
def _disposed_beats_stale_status():
    """SB532, SB533 and SB576 read "In committee" after the Senate killed them.

    The status columns are not always advanced once a bill is finished -- 21 of
    the real ones still read REPORT FILED or NO ACTION on bills signed into law
    -- and classify_stated outranks the docket, so a stale in-progress status
    wins over a dated floor vote that disposed of the bill.

    The evidence is the motion code, not a substring of the docket:
    classify() tests `"inexpedient to legislate" in text`, and that phrase is in
    every MINORITY report too, which is how three concurrent resolutions the
    House adopted 197-156, 195-149 and 204-163 came to read "Killed".
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        r = _fixture_site_v2(root)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        idx = {x["id"]: x for x in _site_bills(root / "site")}
        assert idx["SB900"]["status"] == "Killed", (
            f"SB900 reads {idx['SB900']['status']!r}; the Senate adopted "
            "Inexpedient to Legislate on it and the status field had not "
            "caught up")
        # And the rule must not reach a bill whose last adopted motion passed
        # it. HB1442's docket carries "Inexpedient to Legislate" nowhere, but
        # HR10's minority reports do on the real data.
        assert idx["HB1442"]["status"] != "Killed", idx["HB1442"]["status"]
        assert idx["HR10"]["status"].startswith("Adopted"), idx["HR10"]["status"]
        return "ok", "a dated floor vote beats an in-progress status field"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the Senate's own report reaches the page, dated from its own chamber")
def _senate_reports():
    """1,254 bills had a bare docket line where the Senate had written a report.

    build_site_v2.committee_reports said "a Senate report always [lands in the
    docket list], because the Senate prints no reasoning". That is true of the
    docket and false of the record: the General Court's database holds 1,446
    Senate committee reports and 1,096 of them explain the committee's
    thinking.

    The join back to the docket -- which supplies the day the committee signed
    and the journal page -- has to know the chamber. On the recommendation
    alone it matched the wrong one 364 times, because "Ought to Pass" is what
    both chambers say.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        r = _fixture_site_v2(root)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        hb = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                        .read_text(encoding="utf-8"))
        sen = [x for x in hb.get("reports", [])
               if (x.get("source") or "").startswith("Senate committee report")]
        assert len(sen) == 2, f"{len(sen)} Senate reports on the page, not 2"
        by_rec = {x["majority_recommendation"]: x for x in sen}

        # The one the docket also records: it takes the signing date and the
        # Senate Calendar page, not the day it was released.
        study = by_rec["REFERRED TO INTERIM STUDY"]
        assert (study["dated"], study["date"]) == ("signed", "2026-04-16"),             (study["dated"], study["date"])
        assert study["cite"] == "SC 14", study["cite"]
        assert "federal rules still in flux" in study["reports"][0]["text"],             "the committee's reasoning did not reach the page"

        # The one the docket does not: it must not borrow the House's.
        otp = by_rec["OUGHT TO PASS"]
        assert not (otp.get("cite") or "").startswith("HC"),             (f"a Senate report cites {otp['cite']}, a House Calendar -- the "
             "join matched on the recommendation without the chamber")
        assert otp["date"] != "2026-02-24",             "a Senate report is dated from the day the House committee signed"

        # The docket line it replaces is not shown underneath it as well --
        # and the OTHER Senate report, which the database does not cover, still
        # is. Absorbing has to be targeted; dropping every Senate docket line
        # once any written report exists would lose the second report entirely.
        dk = [x.get("cite") for x in hb.get("docket_reports", [])
              if x.get("body") == "S"]
        assert "SC 14" not in dk, "the docket line the written report replaces "                                  "is shown underneath it as well"
        assert "SC 9" in dk, (f"Senate docket lines are {dk}; the report the "
                              "database does not cover has been dropped")
        return "ok", "2 written, 1 docket line kept, dated from the Senate"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "an earlier term's votes stay on the earlier term's bill")
def _rollcalls_by_term():
    """HB1442 exists in 2023-2024 and in 2025-2026, with different tallies.

    Bill numbers repeat every biennium and nothing outside proceedings.csv used
    to know it. rollcalls.json is keyed on the term for that reason, and the
    fixture carries the same number twice so a build that merged them would be
    visible here rather than in two years' time.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        r = _fixture_site_v2(root)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        hb = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                        .read_text(encoding="utf-8"))
        # The votes tab also carries voice and division votes read off the
        # docket, which have no tally and no member grid. The roll call FILE's
        # entries are the ones with a tally, and those are what is at issue --
        # but not the fixture's motion to divide HB 1442, which the file files
        # under no bill and vote_passage draws under it (23 October 2026).
        rcs = [r for r in hb.get("rollcalls", []) if r.get("tally") and r.get("question") != "Divide"]
        assert len(rcs) == 1, (f"HB1442 shows {len(rcs)} recorded roll calls; "
                               "the 2023-2024 bill of the same number has "
                               "leaked in")
        got = (rcs[0]["yeas"], rcs[0]["nays"])
        assert got == (214, 119), f"HB1442's vote reads {got}, not 214-119"
        assert not [r for r in hb.get("rollcalls", []) if r.get("yeas") == 190],             "the 2023-2024 tally of 190-160 is on the 2025-2026 bill"
        votes = {m["v"] for m in rcs[0].get("members", [])}
        assert votes == {"Yea"}, (f"the member grid holds {sorted(votes)}; the "
                                  "previous term's Nay has been counted too")
        idx = {x["id"]: x for x in _site_bills(root / "site")}
        # Its own roll call, and not 2024's (the motion to divide it is a
        # procedural roll call, which nrc does not count).
        assert idx["HB1442"]["nrc"] == 1, idx["HB1442"]["nrc"]
        return "ok", "the same number in two terms stays two bills"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a rollcalls.json keyed on bill number is refused, not ignored")
def _rollcalls_old_shape():
    """The failure this replaces is silent.

    rollcalls.json used to be {bill: [votes]} and is now {term: {bill: [votes]}}.
    Read the old shape with the new lookup and every bill comes back with no
    recorded votes, the build succeeds, and 449 bills quietly lose their
    tallies. Five instances of exactly that in a week is why this is a check.
    """
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        _site_fixture(root)
        nested = json.loads((root / "rollcalls.json").read_text(encoding="utf-8"))
        flat = {}
        for byterm in nested.values():
            for bill, votes in byterm.items():
                flat.setdefault(bill, []).extend(votes)
        (root / "rollcalls.json").write_text(json.dumps(flat), encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_site_v2.py"),
                            "--data", "data", "--out", "site", "--segments", "work"],
                           cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode != 0, ("the build accepted a rollcalls.json keyed on "
                                   "bill number and produced a site with no votes")
        said = (r.stdout + r.stderr).lower()
        assert "keyed on bill number" in said, (r.stdout + r.stderr).strip()[-160:]
        return "ok", "the build stops and says how to rebuild it"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the built site says what it should")
def _chain_output():
    here = Path(".").resolve()
    if not _paths.locate("build_site_v2.py").exists():
        return "skip", "build_site_v2.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        r = _fixture_site_v2(root)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-140:]
        s = root / "site"
        hb = json.loads(
            (s / "bills" / "2026" / "HB1442.json").read_text(encoding="utf-8"))

        def _yr(u):
            m = re.search(r"(?:%5C|/)(\d{4})(?:%5C|/)", u or "")
            return m.group(1) if m else None

        def _exec(d):
            return next((x for x in d.get("stations", [])
                         if x.get("what") == "executive session"), None)

        idx = {x["id"]: x for x in _site_bills(s)}
        lg = json.loads((s / "legislators.json").read_text(encoding="utf-8"))
        checks = [
            # And nothing is left at the flat path, which would mean the
            # writer moved and a reader did not.
            (not list((s / "bills").glob("*.json")),
             "per-bill data is still being written flat as well as under its "
             f"year: {[p.name for p in (s / 'bills').glob('*.json')][:4]}"),
            (len(hb.get("documents", [])) >= 4, "the Documents tab is empty"),
            # Every page of a volume this bill is on, not whichever came first.
            # A citation is only linked to a volume from its own year. The
            # 2025 event below cites HJ 7, which is on file only as the 2026
            # journal, so it keeps its citation and gets no link.
            (not any((e.get("cite_url") and _yr(e["cite_url"])
                      and _yr(e["cite_url"]) != (e.get("date") or "")[:4])
                     for e in hb.get("events", [])),
             "a citation links a volume from a different year than its action: "
             + repr([(e.get("date"), e.get("cite"), e.get("cite_url"))
                     for e in hb.get("events", [])
                     if e.get("cite_url") and _yr(e["cite_url"])
                     and _yr(e["cite_url"]) != (e.get("date") or "")[:4]])),
            (any((e.get("date") or "").startswith("2025")
                 and (e.get("cite") or "").startswith("HJ 7")
                 and not e.get("cite_url")
                 for e in hb.get("events", [])),
             "the 2025 action citing HJ 7 should keep its citation and lose "
             "its link, since only the 2026 volume is on file: "
             + repr([(e.get("date"), e.get("cite"), e.get("cite_url"))
                     for e in hb.get("events", [])
                     if (e.get("cite") or "").startswith("HJ 7")])),
            (any(d["label"] == "HJ 7, pages 55 and 56"
                 for d in hb.get("documents", [])),
             "the journal entry names one page and drops the others: "
             + repr([d["label"] for d in hb.get("documents", [])
                     if d.get("kind") == "record"])),
            (hb["stations"][0].get("start_stated") is True,
             "a stated boundary did not reach the station"),
            (hb["stations"][0].get("tolerance") == 30, "the tolerance was not carried"),
            (hb["reports"][0]["reports"][0].get("vote_yeas") == 19,
             "the committee vote was not carried"),
            # A written report takes its date from the docket line citing the
            # same calendar -- the day the committee signed, which is 24
            # February here and three days before the calendar carrying it.
            # Without this the nine bills a single committee reported twice
            # show two blocks a reader cannot tell apart.
            (hb["reports"][0].get("date") == "2026-02-24",
             f"the report is dated {hb['reports'][0].get('date')!r}, not the day "
             "the committee signed"),
            (hb["reports"][0].get("dated") == "signed",
             "the report does not say where its date came from"),
            (hb["reports"][0].get("cite_url"),
             "the report does not link the calendar it was printed in"),
            # And the Senate's, which no calendar prints the reasoning for.
            (len(hb.get("docket_reports") or []) == 1,
             f"{len(hb.get('docket_reports') or [])} docket reports, expected the "
             "Senate's one; a House report whose calendar IS on file must not "
             "appear twice"),
            ((hb.get("docket_reports") or [{}])[0].get("committee")
             == "Senate Commerce",
             "the reporting committee was not carried onto the docket report"),
            # A start the chair announced keeps its own placement, and takes no
            # end from a clustering that put the proceeding somewhere else.
            # 2,732 stations paired the two; 429 of them ended before they
            # began, and the page dropped those ends without saying anything.
            (_exec(hb) is not None, "the executive session is not on the page"),
            ((_exec(hb) or {}).get("start") == 300,
             f"the stated start was not used: {(_exec(hb) or {}).get('start')!r}"),
            # Every sponsor is named the same way. A member who has left has
            # no page, so no link -- that is the only difference the site draws.
            (all((sp.get("chamber") or "").strip() for sp in hb.get("sponsors", [])),
             "a sponsor has no chamber, which puts them under a heading of "
             "their own: "
             + repr([sp.get("name") for sp in hb.get("sponsors", [])
                     if not (sp.get("chamber") or "").strip()])),
            ((_exec(hb) or {}).get("end") is None,
             "an end from a placement 4,700 seconds away was attached to a "
             f"start the chair stated: {(_exec(hb) or {}).get('end')!r}"),
            (all(s.get("end") is None or s.get("start") is None
                 or s["end"] > s["start"] for s in hb["stations"]),
             "a station ends at or before it starts"),
            (hb["events"][0].get("cite_url"), "the journal citation did not resolve"),
            # A House Resolution is adopted by the House and that is the end
            # of it. Reading it as "Passed one chamber" implies a Senate stage
            # that does not exist, and "Became law" would be worse.
            (idx["HR10"]["status"] == "Adopted by the House",
             f"HR10 reads {idx['HR10']['status']!r}, not the end of a "
             "one-chamber resolution"),
            (idx["HR10"]["kind"] == "adopted",
             f"HR10 kind is {idx['HR10']['kind']!r}"),
            (idx["SB434"]["status"] == "Vetoed, override failed",
             f"SB434 reads {idx['SB434']['status']!r}, not the docket's outcome"),
            # The card's byline draws the prime sponsor as the person chip,
            # with the seat (D14, 10 October 2026).
            (idx["HB1442"].get("sponsor_label") == "Rep. Jodi Nelson (R - Rock 13)",
             f"sponsor reads {idx['HB1442'].get('sponsor_label')!r}"),
            (lg[0].get("display_full") == "Rep. Jodi Nelson (R - Rock 13)",
             f"legislator reads {lg[0].get('display_full')!r}"),
            # The floor branch ran at all: the stated start reached the station.
            (any(x.get("debate_start") == 600 for x in hb["stations"]),
             "the stated floor start did not reach the station, so the branch "
             "below was not exercised"),
            # And taking that branch did not cost the bill its status record.
            # These three are the fields that were lost when the floor code
            # rebound `st`, and they are checked together because they failed
            # together and would again.
            ((hb.get("text_url") or "").startswith("https://gc.nh.gov/x.pdf"),
             f"text_url reads {hb.get('text_url')!r} on a bill with a stated "
             "floor boundary"),
            (hb.get("facts", {}).get("lsr") == "2026-0503",
             f"facts reads {hb.get('facts')!r} on a bill with a stated floor "
             "boundary"),
            (hb.get("next_step", "").startswith("House:"),
             f"next_step reads {hb.get('next_step')!r}, not the per-chamber "
             "status the status page gives"),
        ]
        bad = [why for ok_, why in checks if not ok_]
        assert not bad, "; ".join(bad)
        return "ok", f"{len(checks)} facts about the output, all as expected"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "captions that stop an hour short put no time on the page")
def _late_captions_fixture():
    """A caption track can start an hour into its recording, and then every
    time read off it is an hour early: the chair's stated boundary, drawn as
    the chair's own moment, and the clustering beside it. On 10 September that
    was 74 published starts on nine recordings, and nothing on any page looked
    wrong, because a start an hour early is still a start.

    caption_span.py compares where the captions stop with where the recording
    does, and build_site_v2 withholds both sources for a track past the line.
    Here the fixture's VID4 -- a stated start at 0:05:00 and a clustered one
    at 1:23:20 -- gets captions that stop at twenty minutes of two hours, and
    VID1 gets captions that reach the end of its fifteen. One must lose its
    times and the other must keep them, or the guard is either missing or
    withholding what it has no reason to doubt.
    """
    here = Path(".").resolve()
    if not (_paths.locate("build_site_v2.py").exists()
            and _paths.locate("caption_span.py").exists()):
        return "skip", "build_site_v2.py or caption_span.py not here"
    root = Path(tempfile.mkdtemp(prefix="gr-late-"))
    try:
        _site_fixture(root)

        def track(cues):
            # YouTube's json3 as yt-dlp writes it: a window spanning the
            # track, then one event per cue, indented a field to a line.
            ev = [{"tStartMs": 0, "dDurationMs": cues[-1][0] + 4000, "id": 1,
                   "wpWinPosId": 1, "wsWinStyleId": 1}]
            ev += [{"tStartMs": t, "dDurationMs": 4000, "wWinId": 1,
                    "segs": [{"utf8": s}]} for t, s in cues]
            return json.dumps({"wireMagic": "pb3", "events": ev}, indent=2)

        (root / "work" / "VID4" / "captions.en.json3").write_text(track([
            (300000, "will open the executive session on House Bill 1442"),
            (1196000, "we are adjourned")]), encoding="utf-8")
        (root / "work" / "VID1" / "captions.en.json3").write_text(track([
            (150000, "I am opening the hearing on House Bill 1442"),
            (892000, "thank you all")]), encoding="utf-8")
        with open(root / "videos_house_fixture.csv", "w", newline="",
                  encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["video_id", "title", "duration_iso"])
            wr.writerow(["VID1", "House Commerce", "PT15M30S"])
            wr.writerow(["VID4", "House Commerce", "PT2H"])
        r = _run([sys.executable, _paths.script("build_site_v2.py"),
                  "--data", "data", "--out", "site", "--segments", "work"],
                 cwd=root, capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
        rec = json.loads((root / "site" / "bills" / "2026" / "HB1442.json")
                         .read_text(encoding="utf-8"))
        by = {s.get("video_id"): s for s in rec.get("stations") or []}
        late, kept = by.get("VID4"), by.get("VID1")
        assert late and kept, (
            "the fixture's two recorded proceedings are not both on HB1442's "
            f"record: {sorted(k for k in by if k)}")
        assert late.get("start") is None and late.get("state") == "approximate", (
            "VID4's captions stop 100 minutes short of its recording and its "
            f"station still reads {late.get('state')} at {late.get('start')}: "
            "a time read off an out-of-step track reached the page")
        assert kept.get("start") is not None, (
            "VID1's captions reach the end of its recording and its station "
            "lost its start: the guard is withholding a time it has no reason "
            "to doubt")
        assert "withheld" in r.stdout and "VID4" in r.stdout, (
            "the build withheld VID4's times without saying so")
        return "ok", ("a track stopping 100 minutes short loses its stated and "
                      "clustered times, one reaching its end keeps them, and "
                      "the build names what it withheld")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the night reads a calendar from the text beside it where the PDF is not kept, "
       "under the PDF's own name; and that text is pdftotext -layout's, found beside git where "
       "the path has none, or no text at all", needs=(
           "extract_calendar_text", "fetch_committee_reports", "extract_amendments"))
def _calendar_text_readers(ET, FC, EA):
    """THE TEXT STANDS FOR THE PDF (16 November 2026). GitHub's machine has
    each calendar's text and never its PDF, so the night's readers read the
    text, and the text must be the same program's the laptop's 3,257 came
    from. On fixtures, in a throwaway folder:

      - pdftotext() is the one on the path, else Git for Windows' beside git
        (git in Git/cmd or in Git/mingw64/bin), else the one under
        ProgramFiles' Git, else none;
      - with --layout-only no other program reads the columns: no pdftotext,
        or one that fails, is no text, where the default falls back;
        and the run writes no text for that PDF;
      - fetch_committee_reports.py --offline --text reads a calendar that is
        only text, by the PDF's own name, and without --text finds nothing
        to read; --text without --offline is refused;
      - extract_amendments.py --text reads the same way, its source the
        PDF's name, and without --text finds no PDF.
    """
    import contextlib
    import io
    import types
    here = Path(".").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gr-caltext-"))
    saved = (sys.argv, ET.shutil, ET.pdftotext, os.environ.get("ProgramFiles"),
             sys.modules.get("pdfplumber"))

    class Plumber:
        """pdfplumber, faked: one page of text, from any file."""
        @staticmethod
        def open(path):
            page = types.SimpleNamespace(extract_text=lambda: "the columns, read another way")
            return contextlib.nullcontext(types.SimpleNamespace(pages=[page]))

    def which(found):
        return types.SimpleNamespace(which=lambda name: found.get(name))

    def tool(*parts):
        p = tmp.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"")
        return str(p)

    def run(mod, argv):
        sys.argv = argv
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                mod.main()
                return 0, out.getvalue()
            except SystemExit as e:
                return e.code, out.getvalue()

    try:
        os.chdir(tmp)
        real = ET.pdftotext
        # Where pdftotext is.
        git_pt = tool("Git", "mingw64", "bin", "pdftotext.exe")
        os.environ["ProgramFiles"] = str(tmp / "nowhere")
        for found, want in (({"pdftotext": "/usr/bin/pdftotext"}, "/usr/bin/pdftotext"),
                            ({"git": str(tmp / "Git" / "cmd" / "git.exe")}, git_pt),
                            ({"git": str(tmp / "Git" / "mingw64" / "bin" / "git.exe")}, git_pt),
                            ({}, None)):
            ET.shutil = which(found)
            got = real()
            assert (Path(got).resolve() if got else None) == (
                Path(want).resolve() if want else None), (found, got)
        pf_pt = tool("PF", "Git", "mingw64", "bin", "pdftotext.exe")
        os.environ["ProgramFiles"] = str(tmp / "PF")
        ET.shutil = which({})
        assert real() and Path(real()).resolve() == Path(pf_pt).resolve(), real()
        ET.shutil = saved[1]

        # --layout-only: pdftotext -layout's text or none.
        sys.modules["pdfplumber"] = Plumber
        pdf = Path("calendars") / "2026" / "HC009.pdf"
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b"%PDF-1.4 a calendar")
        ET.pdftotext = lambda: None
        assert ET.extract(pdf, layout_only=True) == (None, "no pdftotext here"), \
            ET.extract(pdf, layout_only=True)
        assert ET.extract(pdf) == ("the columns, read another way", "pdfplumber"), ET.extract(pdf)
        ET.pdftotext = lambda: sys.executable          # a "pdftotext" that fails
        text, how = ET.extract(pdf, layout_only=True)
        assert text is None and how.startswith("pdftotext gave no text"), (text, how)
        assert ET.extract(pdf)[1] == "pdfplumber"
        ET.pdftotext = lambda: None
        code, out = run(ET, ["extract_calendar_text.py", "--layout-only"])
        assert code == 0 and not pdf.with_suffix(".txt").exists() and \
            "pdftotext: none here" in out, (code, out[-300:])
        ET.pdftotext = saved[2]
        pdf.unlink()

        # The committee reports, from a calendar that is only its text.
        txt = Path("calendars") / "2026" / "HC001.txt"
        txt.write_text(CALENDAR_PAGE, encoding="utf-8")
        code, out = run(FC, ["fetch_committee_reports.py", "--year", "2026", "--offline", "--text",
                             "--out", "reports.json"])
        rep = json.loads(Path("reports.json").read_text(encoding="utf-8"))
        bills = rep.get("2025-2026", {})
        assert code in (0, None) and sorted(bills) == ["HB1418", "HB1419"] and all(
            r["source"] == "House Calendar 1, 2026" for v in bills.values() for r in v), (
                code, sorted(bills), out[-300:])
        assert "the text beside it" in out, out[-300:]
        Path("reports.json").unlink()
        code, _ = run(FC, ["fetch_committee_reports.py", "--year", "2026", "--offline",
                           "--out", "reports.json"])
        assert code and "no calendars" in str(code) and not Path("reports.json").exists(), code
        code, _ = run(FC, ["fetch_committee_reports.py", "--year", "2026", "--text"])
        assert code == 2, f"--text without --offline was not refused ({code})"

        # The amendments, the same way.
        am = Path("calendars") / "2023" / "HC012.txt"
        am.parent.mkdir(parents=True)
        am.write_text(AMENDMENT_PAGE, encoding="utf-8")
        code, out = run(EA, ["extract_amendments.py", "--text", "--calendars", "calendars",
                             "--narratives", "none.json", "--out", "amendments.json"])
        got = json.loads(Path("amendments.json").read_text(encoding="utf-8"))
        assert "2023-0471h" in got and got["2023-0471h"]["source"] == "HC012.pdf", (
            code, sorted(got)[:4], out[-300:])
        Path("amendments.json").unlink()
        code, _ = run(EA, ["extract_amendments.py", "--calendars", "calendars",
                           "--narratives", "none.json", "--out", "amendments.json"])
        assert code and "No PDFs" in str(code) and not Path("amendments.json").exists(), code
    finally:
        os.chdir(here)
        (sys.argv, ET.shutil, ET.pdftotext) = saved[:3]
        if saved[3] is None:
            os.environ.pop("ProgramFiles", None)
        else:
            os.environ["ProgramFiles"] = saved[3]
        if saved[4] is None:
            sys.modules.pop("pdfplumber", None)
        else:
            sys.modules["pdfplumber"] = saved[4]
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("pdftotext is the path's, else Git for Windows' beside git, else ProgramFiles' "
                  "Git's; --layout-only writes no other program's text; the committee reports "
                  "and the amendments read a calendar that is only text, under its PDF's name, "
                  "and find nothing without --text")


@check("build", "a fetch writes the term it was asked for")
def _fetch_writes_its_term():
    """The run that made 1,996 requests and saved none of them.

    fetch_bill_status.py keeps the whole file in `out_all` and this term's
    slice in `out`, so a run over one term cannot drop another. `out_all[term]
    = out` sat before the loop, which was right until an empty term stopped
    being written: the term was then popped while `out` was still empty and
    never reattached, so every write produced a file that did not reference
    the dict the loop was filling.

    It exited zero. The console said "1,996 bills of 2023-2024 -> ...". The
    file had no 2023-2024 in it, and the only reason nothing was lost is that
    the pages were already cached.

    This runs the real script over a cache of one page, with no network -- the
    parser skips a bill it has no cached page for -- and asks the only question
    that matters: is what it fetched in the file, and is the other term still
    there beside it.
    """
    here = Path(".").resolve()
    if not _paths.locate("fetch_bill_status.py").exists():
        return "skip", "fetch_bill_status.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "data").mkdir()
        (root / "data" / "bills.json").write_text(json.dumps({
            "2023-2024": {"HB100": {"lsr_year": "2024", "lsr_num": "1234",
                                    "title": "", "bill": "HB100"}},
            "2025-2026": {"HB100": {"lsr_year": "2026", "lsr_num": "9999",
                                    "title": "the current HB100", "bill": "HB100"}},
        }), encoding="utf-8")
        (root / "data" / "sponsors.json").write_text(json.dumps(
            {"2025-2026": {"HB100": []}}), encoding="utf-8")
        # The other term, already on file. It must still be there afterwards.
        (root / "bill_status.json").write_text(json.dumps({
            "2025-2026": {"HB100": {"title": "the current HB100.",
                                    "gen_status": "IN COMMITTEE"}}}),
            encoding="utf-8")
        # One cached page, named the way the fetcher names them.
        cache = root / "status_pages"
        cache.mkdir()
        (cache / "2024_1234_HB100.html").write_text(
            "<html><body><table><tr><td>Bill Title: an entirely different bill "
            "of the same number</td></tr><tr><td>LSR#: 1234</td></tr>"
            "<tr><td>Body: H</td></tr><tr><td>Gen Status: SIGNED BY GOVERNOR"
            "</td></tr></table></body></html>", encoding="utf-8")

        r = _sealed_run(
            [sys.executable, _paths.script("fetch_bill_status.py"),
             "--reparse", "--term", "2023-2024", "--data", "data",
             "--out", "bill_status.json", "--cache", "status_pages"],
            cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]

        got = json.loads((root / "bill_status.json").read_text(encoding="utf-8"))
        assert "2023-2024" in got, (
            "the term it was asked to fetch is not in the file it wrote. It "
            f"wrote: {sorted(got)}. The console will have said it saved them.")
        assert got["2023-2024"].get("HB100", {}).get("title"), (
            "the term is there and the bill it parsed is not: "
            f"{got['2023-2024']}")
        assert "different bill" in got["2023-2024"]["HB100"]["title"], (
            "the archived bill took a title from somewhere other than its own "
            f"cached page: {got['2023-2024']['HB100']['title']!r}")
        assert got.get("2025-2026", {}).get("HB100"), (
            "the term that was NOT being fetched was dropped on the way out")
        assert got["2025-2026"]["HB100"]["title"] == "the current HB100.", (
            "the term that was not being fetched was overwritten")
        return "ok", ("the fetched term is written and the other term "
                      "survives it")
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "an archived term's manifest cannot overwrite the current term's")
def _manifest_out():
    """build_proceedings reads every verification_manifest*.csv, and
    build_manifest's --out defaults to the current term's. A run over an
    archived docket that forgot --out would replace the current term's rows
    with the archived term's: the current term gone from proceedings.csv, the
    other in it twice. It is refused before anything is read."""
    here = Path(".").resolve()
    if not _paths.locate("build_manifest.py").exists():
        return "skip", "build_manifest.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        r = _run([sys.executable, _paths.script("build_manifest.py"),
                  "--docket", "Docket_2019-2020.txt", "--videos", "none.csv"],
                 cwd=root, capture_output=True, text=True, timeout=60)
        said = (r.stdout or "") + (r.stderr or "")
        assert r.returncode != 0 and "verification_manifest_2019-2020.csv" in said, (
            "an archived docket with the default --out was not refused: "
            + said.strip()[-160:])
        assert not (root / "verification_manifest.csv").exists()
        return "ok", "an archived docket must name its own manifest"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "publish.bat CALLs every batch script it runs, so the steps after it run")
def _publish_calls():
    """npx is npx.cmd, and cmd hands a batch file that runs another batch
    file without CALL over to it for good. publish.bat ran `npx wrangler`
    bare, so every publish ended at "Deployment complete!" and the check_live
    gate after it -- the one step that says whether the deploy landed -- never
    ran, with exit 0 and no message. Found on 11 September by reading a
    publish log that stopped one line early."""
    bat = Path("publish.bat")
    if not bat.exists():
        return "skip", "no publish.bat"
    scripts = {"npx", "npm", "yarn", "pnpm", "wrangler"}
    bad = []
    for i, line in enumerate(_source(bat, errors="replace").splitlines(), 1):
        words = line.strip().lstrip("@").split()
        if not words or words[0].upper() == "REM" or words[0].startswith("::"):
            continue
        first = words[0].lower().strip('"')
        if first in scripts or first.endswith((".bat", ".cmd")):
            bad.append(f"line {i}: {line.strip()[:60]}")
    assert not bad, ("publish.bat runs a batch script without CALL, so "
                     "nothing after it runs: " + "; ".join(bad))
    return "ok", "every batch script publish.bat runs is CALLed"


@check("build", "build_bills binds each of its names that hold every member once")
def _bill_loop_names():
    """The dry run of 8f700a7 (10 October 2026) stopped in the site data,
    "'list' object has no attribute 'get'": the story's linked members were
    put in `_people`, the name build_bills already gave every member and
    former member, so the next bill's sponsor list read a list. The fixture's
    bills never reached that read, so nothing here failed. Read off the
    function's own source: a name it binds to the members is bound once."""
    import ast
    src = Path(_paths.locate("build_site_v2.py")).read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.FunctionDef) and n.name == "build_bills")
    held = {"_people", "legs", "leg_by_sort", "leg_by_name"}
    bound = {}
    for n in ast.walk(fn):
        for tgt in (n.targets if isinstance(n, ast.Assign) else
                    [n.target] if isinstance(n, (ast.AnnAssign, ast.AugAssign)) else []):
            for x in ast.walk(tgt):
                if isinstance(x, ast.Name) and x.id in held:
                    bound.setdefault(x.id, []).append(x.lineno)
    twice = {k: v for k, v in bound.items() if len(v) > (0 if k != "_people" else 1)}
    assert not twice, f"build_bills binds a name that holds the members again: {twice}"
    return "ok", "_people bound once; legs, leg_by_sort and leg_by_name never rebound"


@check("build", "every deploy names the production branch, and both name the same one")
def _deploy_branch():
    """wrangler takes a deploy's branch from git unless told, so a Pages
    production branch of main and a repository on master sent every deploy to
    a preview while wrangler printed "Deployment complete". publish.bat and
    nightly.py both deploy; a nightly that nobody watches is where a deploy
    that quietly became a preview would go unseen longest."""
    bat = _source("publish.bat", errors="replace")
    m = re.search(r"^set PRODUCTION_BRANCH=(\S+)", bat, re.M)
    assert m, "publish.bat does not set PRODUCTION_BRANCH"
    deploys = [ln for ln in bat.splitlines()
               if "wrangler pages deploy" in ln and not ln.strip().upper().startswith("REM")]
    assert deploys and all("--branch=%PRODUCTION_BRANCH%" in ln for ln in deploys), \
        "a publish.bat deploy does not pass --branch=%PRODUCTION_BRANCH%"
    # AND THE FOLDER MUST BE ON THE RIGHT BRANCH, which is a DIFFERENT name
    # from the one above and must stay one. --branch publishes whatever the
    # folder holds as production, so a branch checked out here is a branch
    # published; the guard has to come before the first upload.
    #
    # The two were one constant until the repository was renamed master ->
    # main on 17 September. The Pages project was not renamed and its
    # production branch still answers to master, so afterwards the guard
    # compared main against master and would have refused every deploy --
    # silently, in the nightly's case. Merging them again breaks it one way or
    # the other: point --branch at the repository's name and deploys go to a
    # PREVIEW while wrangler reports success, which is the 6 September
    # failure; point the guard at Cloudflare's name and nothing deploys at
    # all. So this asserts they are read from separate settings.
    rb = re.search(r"^set REPO_BRANCH=(\S+)", bat, re.M)
    assert rb, ("publish.bat does not set REPO_BRANCH -- the branch the folder "
                "must be on is not the branch Cloudflare calls production")
    guard = bat.find('if not "%BRANCH%"=="%REPO_BRANCH%" goto :wrongbranch')
    assert guard != -1 and "git rev-parse --abbrev-ref HEAD" in bat, \
        "publish.bat deploys without checking which branch the folder is on"
    assert guard < bat.find("call npx wrangler pages deploy"), \
        "publish.bat checks the branch only after uploading"
    night = _source(_paths.locate("nightly.py"), errors="replace")
    n = re.search(r'^PRODUCTION_BRANCH = "([^"]+)"', night, re.M)
    assert n, "nightly.py does not set PRODUCTION_BRANCH"
    assert n.group(1) == m.group(1), (
        f"publish.bat deploys to {m.group(1)} and nightly.py to {n.group(1)}")
    nr = re.search(r'^REPO_BRANCH = "([^"]+)"', night, re.M)
    assert nr, "nightly.py does not set REPO_BRANCH"
    assert nr.group(1) == rb.group(1), (
        f"publish.bat publishes from {rb.group(1)} and nightly.py from {nr.group(1)}")
    assert "if branch != REPO_BRANCH:" in night, \
        "nightly.py gates its deploy on something other than REPO_BRANCH"
    assert '"--branch={PRODUCTION_BRANCH}"' in night.replace("f\"", "\""), \
        "nightly.py's deploy does not pass --branch"
    # The last line of defence: whichever names are written down, this folder
    # has to be on the one they publish from, or nothing will deploy.
    here = ""
    try:
        here = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, timeout=20).stdout.decode(
                                  "utf-8", "replace").strip()
    except Exception:
        pass
    note = ""
    if here and here != rb.group(1):
        note = (f"; this folder is on {here}, so neither publish.bat nor the "
                f"nightly would deploy from it")
    return "ok", (f"deploys to {m.group(1)}, published from {rb.group(1)}"
                  f"{note}")


@check("build", "the docket fetch stops at a block page or a dropped connection, and caches no error")
def _docket_fetch_stops():
    """fetch_archive_docket read refusals by substring of an error's text,
    and urllib wraps a reset at connect time as "<urlopen error [WinError
    10054] ...>", which matched nothing; and it cached any 200, the
    firewall's block page included, and exited 0 -- so under a block the lane
    would have gone on into the next step. A fake server stands in: each
    case runs the real main() in a subprocess in a temp directory."""
    here = Path(".").resolve()
    if not _paths.locate("fetch_archive_docket.py").exists():
        return "skip", "fetch_archive_docket.py not here"
    good = ('<tr><td>01/05/2016</td><td>H</td><td>Introduced and referred to '
            'Education</td></tr>' * 3)
    good = "<html>" + good + "x" * 2000 + "</html>"
    cases = {
        "block page": (['"<h1>Web Page Blocked</h1> Attack ID: 99" + "x"*2000'], 2, True),
        "two resets": (["urllib.error.URLError(ConnectionResetError(10054, 'r'))"] * 2, 2, True),
        "three 500s": (["urllib.error.HTTPError('u', 500, 'e', {}, None)"] * 3, 3, False),
        "error, then fine": (['"Index 0 is either negative or above rows count" + "x"*2000',
                              repr(good), repr(good), repr(good)], 0, False),
    }
    results = []
    for name, (answers, want_rc, want_refusal) in cases.items():
        root = Path(tempfile.mkdtemp())
        try:
            (root / "data").mkdir()
            (root / "data" / "bills.json").write_text(json.dumps({"2015-2016": {
                f"HB{1000 + i}": {"lsr_year": "2016", "lsr_num": str(2000 + i)}
                for i in range(4)}}), encoding="utf-8")
            (root / "wrap.py").write_text(
                "import sys, urllib.error\n"
                f"sys.path.insert(0, {str(here)!r})\n" "import _paths\n"
                "import fetch_archive_docket as D\n"
                f"answers = [{', '.join(answers)}]\n"
                "def get(url, timeout):\n"
                "    a = answers.pop(0)\n"
                "    return (None, a) if isinstance(a, Exception) else (a, None)\n"
                "D.get = get\n"
                "D.time.sleep = lambda s: None\n"
                "sys.argv = ['x', '--term', '2015-2016', '--delay', '0']\n"
                "sys.exit(D.main())\n", encoding="utf-8")
            r = _sealed_run([sys.executable, "wrap.py"], cwd=root, capture_output=True,
                            text=True, timeout=60)
            refused = (root / "archive" / "refused.json").exists()
            cached = sorted(p.name for p in (root / "docket_pages").glob("*.html")) \
                if (root / "docket_pages").exists() else []
            assert r.returncode == want_rc, (
                f"{name}: status {r.returncode}, not {want_rc}: "
                + (r.stderr or r.stdout).strip()[-200:])
            assert refused == want_refusal, f"{name}: refusal recorded {refused}"
            assert not (root / "archive" / ".lock").exists(), f"{name}: lock left behind"
            if name == "error, then fine":
                assert "2016_2000_HB1000.html" not in cached, "an error page was cached"
                assert len(cached) == 3, f"cached {cached}"
            results.append(name)
        finally:
            shutil.rmtree(root, ignore_errors=True)
    # A page cached whole but empty -- SB 68 of 2017 -- is asked again with
    # --refetch-empty, and only then. Four bills, one cached empty.
    empty = "<html><h1>Docket of HB1000</h1>Bill Title: x" + "y" * 2000 + "</html>"
    for flag, want_asked in (("", 3), ("--refetch-empty", 4)):
        root = Path(tempfile.mkdtemp())
        try:
            (root / "data").mkdir()
            (root / "docket_pages").mkdir()
            (root / "docket_pages" / "2016_2000_HB1000.html").write_text(
                empty, encoding="utf-8")
            (root / "data" / "bills.json").write_text(json.dumps({"2015-2016": {
                f"HB{1000 + i}": {"lsr_year": "2016", "lsr_num": str(2000 + i)}
                for i in range(4)}}), encoding="utf-8")
            (root / "wrap.py").write_text(
                "import sys\n"
                f"sys.path.insert(0, {str(here)!r})\n" "import _paths\n"
                "import fetch_archive_docket as D\n"
                f"answers = [{repr(good)}] * 4\n"
                "asked = []\n"
                "def get(url, timeout):\n"
                "    asked.append(url)\n"
                "    return answers.pop(0), None\n"
                "D.get = get\n"
                "D.time.sleep = lambda s: None\n"
                "sys.argv = ['x', '--term', '2015-2016', '--delay', '0'"
                + (f", {flag!r}" if flag else "") + "]\n"
                "rc = D.main()\n"
                "print('ASKED', len(asked))\n"
                "sys.exit(rc)\n", encoding="utf-8")
            r = _sealed_run([sys.executable, "wrap.py"], cwd=root, capture_output=True,
                            text=True, timeout=60)
            assert r.returncode == 0, (r.stderr or r.stdout).strip()[-200:]
            assert f"ASKED {want_asked}" in r.stdout, (
                f"{flag or 'no flag'}: {r.stdout.strip()[-120:]}")
            again = (root / "docket_pages" / "2016_2000_HB1000.html").read_text(
                encoding="utf-8")
            assert ("Introduced" in again) == bool(flag), (
                f"{flag or 'no flag'}: the empty page was "
                + ("not " if flag else "") + "replaced")
            results.append(f"empty page {'re-asked' if flag else 'kept'}")
        finally:
            shutil.rmtree(root, ignore_errors=True)
    return "ok", "; ".join(results) + " -- each behaves"


@check("build", "every fetcher that asks gc.nh.gov consults refusal.py first")
def _every_fetcher_checks_refusal():
    """A refusal is a fact about the address, not about the run that found it.

    `refusal.py` records one in `archive/refused.json` and holds the fetch
    lane for 24 hours. It exists because a calendar drain met two 403s,
    stopped itself correctly, and a chained run asked the same address for a
    docket fifty-four seconds later. But the holding only works if the next
    fetcher asks, and ten that name a gc.nh.gov URL did not: started by hand,
    any of them walked straight through a standing refusal.

    `fetch_archive_bills.py` was the sharpest of the ten. It asks
    `bill_status/legacy/bs2016/`, which is the exact path the General Court's
    IT office asked this project to go lightly on, on session days.

    The test is a literal URL rather than the words "gc.nh.gov", because
    `fetch_town_clerks.py` names the host only to say it asks somebody else --
    app.sos.nh.gov, the Secretary of State -- and must not be caught by this.
    The eight `fetch_*_db.py` scripts read the SQL host the General Court
    publishes credentials for, which is not the server that did the blocking,
    and they hold no literal URL either.
    """
    import re as _re
    URL = _re.compile(r"""["']https?://gc\.nh\.gov""")
    # NOT ONLY THE fetch_*.py SCRIPTS (25 September 2026). resolve_members.py,
    # a network step of build_all, asks bill_status/legacy/bs2016/ for roll-call
    # pages, and four probe scripts ask the General Court too; none consulted
    # refusal.py, and this check, reading fetch_*.py alone, never looked. So it
    # reads every script that holds a General Court URL AND makes a request --
    # the pages that only write a link to the General Court are not asking it.
    # netcheck.py is the one exception by design: it is what a person runs to
    # diagnose a refusal, so a standing refusal must not stop it.
    #
    # AND THE CALL, NOT THE IMPORT (26 September 2026). This asked only for
    # "import refusal", which a script can carry and never call check() -- and
    # it missed probe_schema.py outright, which downloads with urlretrieve,
    # a word ASKS did not have. check() is also where a stood-down laptop
    # waits for GitHub's night now, so a script that only imports refusal
    # walks through the window as well as through a refusal.
    # fetch_committee_details.py holds no literal URL -- its addresses are
    # read from committees.json -- so it is named here: it asks gc.nh.gov for
    # every committee's page.
    #
    # A CALL, READ AS CODE (26 September 2026). "refusal.check(" as text was
    # satisfied by a comment or a string saying so. The call is read from the
    # parsed source now: an ast.Call of refusal.check, with refusal imported.
    # And a script whose addresses come from a module rather than a literal
    # -- check_civics_links.py asks every gc.nh.gov address civics.py holds,
    # and held no URL of its own, so this never read it -- is read when it
    # imports one of ADDRESSES and makes a request.
    import ast as _ast
    ASKS = _re.compile(r"urlopen|urlretrieve|urllib\.request\.Request|requests\.(?:get|post)"
                       r"|http\.client")
    NAMED = ("fetch_committee_details.py",)
    # modules holding gc.nh.gov addresses scripts ask; guides holds
    # GENERAL_COURT_LINKS, which check_civics_links asks after (17 October 2026)
    ADDRESSES = ("civics", "guides")

    def read(name, src, tree=None):
        """(asks the General Court, calls refusal.check with refusal imported).
        `tree` is the script's parse where this run already has one."""
        tree = tree or _ast.parse(src)
        imported = {a.name for n in _ast.walk(tree) if isinstance(n, _ast.Import)
                    for a in n.names} | {n.module for n in _ast.walk(tree)
                                         if isinstance(n, _ast.ImportFrom) and n.module}
        asks = name in NAMED or (
            (URL.search(src) and (name.startswith("fetch_") or ASKS.search(src)))
            or (bool(imported & set(ADDRESSES)) and ASKS.search(src)))
        checks = "refusal" in imported and any(
            isinstance(n, _ast.Call) and isinstance(n.func, _ast.Attribute)
            and n.func.attr == "check" and isinstance(n.func.value, _ast.Name)
            and n.func.value.id == "refusal" for n in _ast.walk(tree))
        return bool(asks), checks
    probes = {
        "a urlretrieve that imports refusal and never checks":
            ('BASE = "https://gc.nh.gov/x/"\nimport refusal\n'
             'urllib.request.urlretrieve(BASE + "a", "a")\n', (True, False)),
        "a check that is only a comment and a string":
            ('BASE = "https://gc.nh.gov/x/"\nimport refusal, urllib.request\n'
             '# refusal.check("x") comes first\nNOTE = "refusal.check(\'x\')"\n'
             'urllib.request.urlopen(BASE)\n', (True, False)),
        "a script asking the addresses civics.py holds":
            ('import civics, urllib.request\nfor u in civics.TOPICS:\n'
             '    urllib.request.urlopen(u)\n', (True, False)),
        "a script that asks and checks":
            ('import civics, refusal, urllib.request\nrefusal.check("x")\n'
             'urllib.request.urlopen(civics.GC)\n', (True, True)),
        "a builder that imports civics and asks nobody":
            ('import civics\nprint(civics.GC)\n', (False, False)),
    }
    for what, (src, want) in probes.items():
        assert read("probe.py", src) == want, f"the reader got {what} wrong: {read('probe.py', src)}"
    asks, missing, literal = [], [], []
    scanned = _paths.code_files("*.py", dirs=_paths.SCRIPT_DIRS)
    for p in scanned:
        if p.name == "netcheck.py" or _in_suite(p):
            continue
        src = p.read_text(encoding="utf-8", errors="replace")
        try:
            ask, checks = read(p.name, src, _parsed(p))
        except SyntaxError as e:
            raise AssertionError(f"{p.name} will not parse, so whether it asks the General "
                                 f"Court cannot be read: {e}")
        if not ask:
            continue
        asks.append(p.name)
        if p.name.startswith("fetch_") and URL.search(src):
            literal.append(p.name)
        if not checks:
            missing.append(p.name)

    assert asks, "no fetcher holds a gc.nh.gov URL, which cannot be right"
    # FLOORS: the scripts this read on 6 October 2026, before any file moved,
    # and the ones that asked gc.nh.gov. Read from the root alone after a
    # move, it would find no fetcher left there and pass. A script retired on
    # purpose lowers them, in the same commit: 161 and 25 then, 160 and 24
    # since fetch_testimony.py was retired on 7 October, 159 and 23 since
    # fetch_leadership.py was deleted on 23 October.
    assert len(scanned) >= 159 and len(asks) >= _ASKS_GC_FLOOR, (
        f"{len(scanned)} scripts were read and {len(asks)} ask gc.nh.gov; on 23 October "
        f"159 were read and {_ASKS_GC_FLOOR} asked: the code folders are not being read")
    assert all(n in asks for n in NAMED if _paths.locate(n).exists()), "a named fetcher was not read"
    assert not _paths.locate("check_civics_links.py").exists() or "check_civics_links.py" in asks, \
        "check_civics_links.py, which asks the addresses civics.py holds, was not read"
    assert not missing, (
        "these ask gc.nh.gov and never call refusal.check(), so neither a standing "
        "refusal nor GitHub's night window would stop them:\n    " + "\n    ".join(missing)
        + "\n  Add `import refusal` and `refusal.check(\"...\")` straight "
          "after the arguments are parsed (after an offline branch that asks nobody).")
    # CONTRIBUTING.md'S COUNT (7 October 2026). It tells a contributor how
    # many fetch_*.py scripts carry a literal gc.nh.gov URL and call check(),
    # and it still said 18 after fetch_testimony.py was retired and
    # seventeen were left. The number is the one this reads, so it is held to
    # it: a script retired or added changes the sentence in the same commit.
    contrib = _paths.ROOT / "CONTRIBUTING.md"
    if contrib.exists():
        said = _re.search(r"All (\d+)\s+`fetch_\*\.py` scripts carrying a literal\s+"
                          r"`gc\.nh\.gov` URL", _source(contrib))
        assert said, ("CONTRIBUTING.md no longer says \"All N `fetch_*.py` scripts carrying a "
                      "literal `gc.nh.gov` URL\", which this holds to the count it reads: "
                      "change this check with the sentence")
        assert int(said.group(1)) == len(literal), (
            f"CONTRIBUTING.md says {said.group(1)} fetch_*.py scripts carry a literal "
            f"gc.nh.gov URL, and {len(literal)} do: " + ", ".join(literal))
    return "ok", (f"{len(asks)} scripts ask gc.nh.gov; all call refusal.check(), and "
                  f"CONTRIBUTING.md's {len(literal)} fetch_*.py with a literal URL agree")


@check("build", "a fetcher's offline mode is not stopped by a refusal or by GitHub's night, "
                "and its fetching mode is")
def _offline_modes_ask_nobody():
    """refusal.check() stops a fetch that would ask the General Court: a
    standing refusal (exit 2), or on a stood-down laptop GitHub's night window
    (exit 4). Four scripts called it before an offline branch that asks
    nobody -- fetch_lsrs.py --parse, fetch_members.py --reparse,
    fetch_session.py --reparse and probe_archive_shape.py --report -- so
    re-reading pages already saved was stopped too, for as long as a refusal
    stood or every night for five and a half hours. fetch_legislation.py's
    --parse was already below it. check_civics_links.py did not call it at
    all until 26 September; its --list asks nobody. fetch_committee_reports.py
    --offline was a fifth, found on 27 September when the offline re-read of
    every House calendar met the guard.

    Each is run in a temp folder holding a fresh refusal and a stand-down file,
    at a clock inside the window: the offline mode gets past the check, and
    the fetching mode stops at it. Nothing is asked of anybody -- the
    fetching mode stops before its first request, and the offline one makes
    none -- and each runs sealed (_Seal), so a fetching mode that got past
    the check would meet a raiser, not the General Court, and fail here."""
    import time as _time
    here = Path(".").resolve()
    runs = [("fetch_lsrs.py", ["--parse"], []),
            # The request texts (17 November 2026): reading the PDFs asks nobody, the drain does.
            ("fetch_lsrs.py", ["--read-texts"], ["--texts"]),
            ("fetch_members.py", ["--reparse"], []),
            ("fetch_session.py", ["--year", "2020", "--reparse", "--max-lsr", "3"],
             ["--year", "2020", "--max-lsr", "3"]),
            ("probe_archive_shape.py", ["--report"], []),
            ("check_civics_links.py", ["--list"], ["--delay", "0"]),
            ("fetch_committee_reports.py", ["--year", "2020", "--offline"], ["--year", "2020"])]
    runs = [r for r in runs if _paths.locate(r[0]).exists()]
    if not runs:
        return "skip", "none of the six scripts is here"
    tmp = Path(tempfile.mkdtemp(prefix="gr-offline-"))
    seal = _Seal()
    try:
        (tmp / "archive").mkdir()
        (tmp / "data").mkdir()
        (tmp / "data" / "legislators.json").write_text("[]", encoding="utf-8")
        (tmp / "archive" / "refused.json").write_text(json.dumps(
            {"at": "t", "epoch": _time.time(), "where": "preflight", "why": "403"}),
            encoding="utf-8")
        (tmp / "archive" / "runs-in-the-cloud.json").write_text("{}", encoding="utf-8")
        env = dict(os.environ, GRANITE_CLOCK_UTC="2026-09-29T09:00:00Z", GITHUB_ACTIONS="")
        for script, offline, online in runs:
            for args, stopped in ((offline, False), (online, True)):
                r = seal.run([sys.executable, _paths.script(script), *args], cwd=tmp,
                             capture_output=True, text=True, timeout=120, env=env)
                said = (r.stdout or "") + (r.stderr or "")
                # Stopped by the refusal, by GitHub's night, or -- for a fetcher GitHub
                # owns, such as fetch_lsrs.py -- by the stand-down itself.
                held = r.returncode in (2, 4) and ("refused" in said or "window" in said
                                                   or "GitHub runs it" in said)
                assert held == stopped, (
                    f"python3 {script} {' '.join(args)} "
                    + ("was not stopped by a standing refusal" if stopped else
                       "was stopped by the refusal check, though it asks nobody")
                    + f" (exit {r.returncode}): {said.strip()[-200:]}")
    finally:
        seal.close()
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(runs)} offline modes run past a standing refusal and GitHub's night; "
                  "their fetching modes stop at them, sealed from the network")


@check("build", "a fetcher, the lane or the pipeline that preflight starts cannot reach the "
                "network, and it would fail if one tried")
def _children_sealed():
    """_Seal is what stands between a regression in a fetcher's own stop and
    a request from preflight to the General Court. So:

      - a sealed child that tries each way out -- create_connection,
        getaddrinfo, a socket's connect, urllib through the proxies -- is
        refused every time, and the sentinel names each try; so is a
        grandchild it starts, as the lane starts its steps; the child's
        proxies point at the loopback address and NO_PROXY is gone;
      - _Seal.run fails a run that tried, and a run the seal was not in;
      - every check here that starts a fetcher, a probe, livestreams.py,
        check_civics_links.py, the lane, build_all.py or cloud.py as a
        process starts it through the seal -- read from this file, so the
        next check that starts one bare fails here. Those that do now:
        _offline_modes_ask_nobody (fetch_lsrs, fetch_members, fetch_session,
        probe_archive_shape, check_civics_links, fetch_committee_reports), _lane_daily (the lane and
        its steps), _fetch_writes_its_term (fetch_bill_status),
        _docket_fetch_stops (fetch_archive_docket, through its wrapper),
        _carried_outputs (build_all.py --local) and the livestreams checks
        (_ls_run, _ls_nights, _ls_state).
    """
    import ast
    probe = ("import socket, subprocess, sys, urllib.request\n"
             "def tr(name, fn):\n"
             "    try:\n"
             "        fn()\n"
             "        print(name, 'REACHED')\n"
             "    except OSError as e:\n"
             "        print(name, type(e).__name__)\n"
             "port = int(sys.argv[1])\n"
             "tr('create_connection', lambda: socket.create_connection(('127.0.0.1', port), 1))\n"
             "tr('getaddrinfo', lambda: socket.getaddrinfo('localhost', 80))\n"
             "tr('connect', lambda: socket.socket().connect(('127.0.0.1', port)))\n"
             "tr('urlopen', lambda: urllib.request.urlopen('http://example.invalid/', timeout=1))\n"
             "import os\n"
             "print('NO_PROXY', repr(os.environ.get('NO_PROXY', '')), "
             "os.environ.get('HTTP_PROXY', ''))\n"
             "r = subprocess.run([sys.executable, '-c', 'import socket\\ntry:\\n "
             "socket.getaddrinfo(\"localhost\", 80)\\nexcept OSError as e: "
             "print(type(e).__name__)'], capture_output=True, text=True)\n"
             "print('grandchild', r.stdout.strip())\n")
    with _Seal() as seal:
        r = _run([sys.executable, "-c", probe, str(seal.port)], env=seal.env(
            dict(os.environ, NO_PROXY="*", no_proxy="*")), capture_output=True, text=True,
            timeout=60)
        out = r.stdout.split("\n")
        tried = seal.asked.read_text(encoding="utf-8").splitlines() \
            if seal.asked.exists() else []
        for name in ("create_connection", "getaddrinfo", "connect", "urlopen"):
            assert f"{name} " in r.stdout and f"{name} REACHED" not in r.stdout, (
                f"a sealed child's {name} was not refused: {r.stdout[-300:]} {r.stderr[-300:]}")
        assert "SealedByPreflight" in r.stdout or "URLError" in r.stdout, r.stdout[-300:]
        assert any(ln.startswith(f"NO_PROXY '' http://127.0.0.1:{seal.port}") for ln in out), (
            f"a sealed child kept NO_PROXY, or has no closed proxy: {r.stdout[-200:]}")
        assert any(ln.startswith("grandchild SealedByPreflight") for ln in out), (
            f"a process the sealed child started was not sealed: {r.stdout[-200:]}")
        assert len(tried) >= 5 and seal.starts() >= 2, (
            f"the sentinel named {len(tried)} tries and {seal.starts()} sealed processes, "
            "not the five and two made")
        seal.asked.unlink()
        try:
            seal.run([sys.executable, "-c", "import socket; socket.getaddrinfo('x', 1)"],
                     capture_output=True, text=True, timeout=60)
            raise RuntimeError("unreached")
        except AssertionError as e:
            assert "TRIED TO REACH THE NETWORK" in str(e), str(e)
        except RuntimeError:
            raise AssertionError("_Seal.run passed a child that tried to reach the network")
        try:
            seal.run([sys.executable, "-S", "-E", "-c", "print(1)"], capture_output=True,
                     text=True, timeout=60)
            raise AssertionError("_Seal.run passed a child the seal was not in")
        except AssertionError as e:
            assert "without the seal" in str(e), str(e)

    # Every spawn here of something that can reach the network is sealed.
    NET = (r"(?:fetch_\w+|probe_\w+|livestreams|gc_lane|check_civics_links|netcheck"
           r"|snapshot_gencourt|resolve_members|nightly|build_all|cloud|check_live)")
    NAMES = re.compile(r"\b" + NET + r"\.py\b|\bimport " + NET + r"\b")
    SPAWNERS = {"_run", "run", "call", "Popen", "check_output", "check_call", "popen"}

    def bare(tree):
        out = []
        for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
            body = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr) and
                                   isinstance(fn.body[0].value, ast.Constant)) else fn.body
            nodes = [n for b in body for n in ast.walk(b)]
            # What a check says -- an assertion's message, a raise, its
            # ("ok"/"skip", message) -- names scripts without starting them.
            # A return of anything else, _ls_run's of a spawn, is read.
            said = {id(n) for m in nodes
                    if isinstance(m, (ast.Assert, ast.Raise)) or (
                        isinstance(m, ast.Return) and isinstance(m.value, ast.Tuple)
                        and m.value.elts and isinstance(m.value.elts[0], ast.Constant))
                    for part in ([m.msg] if isinstance(m, ast.Assert) else [m])
                    if part is not None for n in ast.walk(part)}
            names = any(isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and id(n) not in said and NAMES.search(n.value) for n in nodes)
            # Sealed: _sealed_run(...), a _Seal's run() -- by convention the
            # _Seal is called `seal` -- or a spawn given env=seal.env(...).
            spawns = [n for n in nodes if isinstance(n, ast.Call)
                      and (getattr(n.func, "id", None) or getattr(n.func, "attr", None))
                      in SPAWNERS and n.args and "sys.executable" in ast.unparse(n.args[0])
                      and ast.unparse(n.func) != "seal.run"
                      and not any(k.arg == "env" and "seal.env(" in ast.unparse(k.value)
                                  for k in n.keywords)]
            if names and spawns:
                out.append(fn.name)
        return out
    trial = ast.parse('def a():\n    """fetch_x.py"""\n    _run([sys.executable, "build_x.py"])\n\n'
                      'def b():\n    _run([sys.executable, str(here / "fetch_x.py")])\n\n'
                      'def c():\n    _sealed_run([sys.executable, "fetch_x.py"])\n'
                      '    seal.run([sys.executable, "gc_lane.py"])\n'
                      '    _run([sys.executable, "cloud.py"], env=seal.env(e))\n\n'
                      'def d():\n    w = "import fetch_x as D"\n'
                      '    child.run([sys.executable, "wrap.py"])\n\n'
                      'def e():\n    return other.run([sys.executable, "livestreams.py"])\n\n'
                      'def f():\n    _run([sys.executable, "build_x.py"])\n'
                      '    assert x, "fetch_x.py now writes it"\n'
                      '    return "skip", "run build_all.py first"\n')
    assert bare(trial) == ["b", "d", "e"], f"the reader of spawns found {bare(trial)}"
    found = [n for f in _suite_files() for n in bare(_parsed(f))]
    assert not found, ("these checks start a fetcher, the lane or the pipeline as a process "
                       "without the seal, so a regression would reach the network from "
                       "preflight: " + ", ".join(found) + ". Start it with _sealed_run or "
                       "a _Seal's run().")
    return "ok", ("a sealed child and its children reach nothing and the sentinel says so; "
                  "every check that starts a fetcher, the lane or the pipeline seals it")


@check("build", "the lane runs a daily step once a day between its other steps, and stops at a boundary when asked")
def _lane_daily():
    """watchers/gc_lane.py, driven for real in a temp folder on stub steps.

    The nightly fetches the day's bulk files only when nothing holds
    archive/.lock, and the bill-text lane holds it for more than a week: on 13
    September no day's files would have been taken until bill text finished,
    and those files are live views, so a day not taken is gone. So the day's
    fetch became a daily step of the lane itself. What that has to mean:

      - a "daily HH:MM" line runs at the first step boundary after HH:MM, once
        a day, before the queue's next run-once step, and is never run as a
        script called "daily";
      - one that fails does not stop the lane, but skips that day's later
        daily steps, which read what it should have made;
      - a lane restarted the same day does not run them again;
      - watchers/gc_lane.stop ends the lane at the next boundary, lock
        released, file removed;
      - a refusal recorded by a daily step still stops the lane before the
        next step;
      - a malformed daily line is reported and left out;
      - on a stood-down laptop it stops before a step, exit 4 and the reason
        in its log, inside GitHub's night window or before the bucket's
        refusal record has been read since the last one -- and runs once it
        has (26 September 2026). The lane imports the real refusal.py for
        that, where it once needed only to find the file;
      - it asks before EACH daily step, not once before them all, and a daily
        step that exits 4 itself while refusal.gc_turn() says it is GitHub's
        turn was held, not run: it is not recorded as today's, and the lane
        stops rather than ask it again at every boundary;
      - a daily step that exits 4 when gc_turn() says nothing is the
        stand-down itself: recorded, the log says the line should come out
        of the queue, and the lane goes on;
      - a step GitHub's night window stopped part way -- its hold's still()
        said so -- is recorded in neither gc_lane.done nor gc_lane.daily,
        whether it then exited 0, 1 or 4, and the lane stops with 4; and a
        `with hold()` block left normally after that exits 4 by itself.

    The lane runs with this process's environment, GRANITE_NO_BUCKET
    included, and only the clock and GITHUB_ACTIONS set for it -- sealed
    (_Seal), so neither it nor any step it starts can reach the network.
    """
    import time as _time
    here = Path(".").resolve()
    lane = _paths.locate("watchers/gc_lane.py")
    if not lane.exists():
        return "skip", "watchers/gc_lane.py not here"
    root = Path(tempfile.mkdtemp(prefix="gr-lane-"))
    seal = _Seal()
    try:
        # The refusal.py its steps import, and the _paths.py that one's
        # bootstrap looks for above it.
        for f in ("refusal.py", "_paths.py"):
            shutil.copy(_paths.locate(f), root / f)
        (root / "watchers").mkdir()
        (root / "archive").mkdir()
        # A step GitHub's window stops part way: its own clock moves into the
        # window, and its hold says so -- then it ends 0 or 1 regardless
        # ("window"), or leaves a `with hold()` block normally ("window-with").
        (root / "stub.py").write_text(
            "import os, pathlib, sys\n"
            "name, code = sys.argv[1], int(sys.argv[2])\n"
            "how = sys.argv[3] if len(sys.argv) > 3 else ''\n"
            "with open('trace.txt', 'a', encoding='utf-8') as fh:\n"
            "    fh.write(name + '\\n')\n"
            "if name.startswith('make-stop'):\n"
            "    pathlib.Path('watchers/gc_lane.stop').write_text('stop', encoding='utf-8')\n"
            "if how == 'refuse':\n"
            "    pathlib.Path('archive/refused.json').write_text('{}', encoding='utf-8')\n"
            "if how == 'unread':\n"
            "    pathlib.Path('archive/cloud/pull.json').unlink()\n"
            "if how in ('window', 'window-with'):\n"
            "    import refusal\n"
            "    os.environ['GRANITE_CLOCK_UTC'] = '2026-09-29T08:30:00Z'\n"
            "    if how == 'window-with':\n"
            "        with refusal.hold(name) as held:\n"
            "            assert not held.still(), 'the window did not stop the hold'\n"
            "        print(name, 'left its hold normally and was not made to exit 4')\n"
            "    else:\n"
            "        assert not refusal.hold(name).still(), 'the window did not stop the hold'\n"
            "print(name, 'exit', code)\n"
            "sys.exit(code)\n", encoding="utf-8")
        # A daily line that is not due yet, when the clock leaves room for one.
        late = _time.localtime().tm_hour <= 21
        queue = root / "watchers" / "gc_lane.queue"

        def lane_run(lines_, clock=None):
            queue.write_text("\n".join(lines_) + "\n", encoding="utf-8")
            (root / "trace.txt").unlink(missing_ok=True)
            # This process's environment, so GRANITE_NO_BUCKET reaches the
            # lane and every step it starts; only the clock and GitHub's flag
            # are the test's.
            r = seal.run([sys.executable, str(lane)], cwd=root, capture_output=True,
                         text=True, timeout=90,
                         env=dict(os.environ, GRANITE_CLOCK_UTC=clock or "", GITHUB_ACTIONS=""))
            trace = ((root / "trace.txt").read_text(encoding="utf-8").split()
                     if (root / "trace.txt").exists() else [])
            return r.returncode, trace

        first = ["# a comment",
                 "daily 00:00 stub.py daily-a 0",
                 "daily 00:00 stub.py daily-b 7",
                 "daily 00:00 stub.py daily-c 0",
                 "daily 25:00 stub.py malformed 0",
                 "stub.py once-1 0",
                 "stub.py make-stop 0",
                 "stub.py once-2 0"] + (["daily 23:59 stub.py daily-late 0"] if late else [])
        rc, trace = lane_run(first)
        assert rc == 0, f"the lane exited {rc} on a planned stop"
        assert trace == ["daily-a", "daily-b", "once-1", "make-stop"], (
            f"the lane ran {trace}; wanted today's daily steps up to the one that failed, "
            "then the queue, then a stop at the boundary before once-2")
        assert not (root / "watchers" / "gc_lane.stop").exists(), "the stop file was left behind"
        assert not (root / "archive" / ".lock").exists(), "a stopped lane left its lock"
        today = _time.strftime("%Y-%m-%d")
        recorded = (root / "logs" / "gc_lane.daily").read_text(encoding="utf-8").splitlines()
        assert sorted(ln.split("\t", 1)[1] for ln in recorded if ln.startswith(today)) == sorted(
            ["daily 00:00 stub.py daily-a 0", "daily 00:00 stub.py daily-b 7",
             "daily 00:00 stub.py daily-c 0"]), f"today's daily record is {recorded}"
        log = (root / "logs" / "gc_lane.log").read_text(encoding="utf-8")
        assert "not a daily step this lane can run" in log, "a malformed daily line was not reported"

        # The same day again: nothing daily runs twice; once-2 is next, and the
        # queue ends -- but daily steps keep a lane alive, so stop it by hand.
        again = [ln for ln in first if ln != "stub.py make-stop 0"] + ["stub.py make-stop-2 0"]
        rc2, trace2 = lane_run(again)
        assert rc2 == 0 and trace2 == ["once-2", "make-stop-2"], (
            f"restarted the same day the lane ran {trace2} (exit {rc2}); wanted once-2 and "
            "the stop, and no daily step again")

        refused = again + ["daily 00:00 stub.py daily-refused 2 refuse", "stub.py after-refusal 0"]
        rc3, trace3 = lane_run(refused)
        assert rc3 == 3 and trace3 == ["daily-refused"], (
            f"a daily step that recorded a refusal was followed by {trace3} (exit {rc3}); "
            "wanted the lane to stop before its next step")

        # Not stood down, a daily step's 4 is a failure like any other: run,
        # recorded, and the day's later daily steps skipped.
        (root / "archive" / "refused.json").unlink()
        plain = ["daily 00:00 stub.py daily-four 4", "daily 00:00 stub.py daily-four-next 0",
                 "stub.py make-stop-5 0"]
        rc_, trace_ = lane_run(plain)
        recorded = (root / "logs" / "gc_lane.daily").read_text(encoding="utf-8")
        assert rc_ == 0 and trace_ == ["daily-four", "make-stop-5"] and \
            "stub.py daily-four 4" in recorded and "stub.py daily-four-next 0" in recorded, (
                f"on a laptop that has not stood down, a daily step that exited 4 was read as "
                f"the stand-down: the lane ran {trace_} (exit {rc_})")

        # Stood down: GitHub's night window, then the bucket's refusal record.
        (root / "archive" / "runs-in-the-cloud.json").write_text("{}", encoding="utf-8")
        held = ["stub.py held-1 0", "stub.py held-2 0", "stub.py make-stop-3 0"]
        rc4, trace4 = lane_run(held, clock="2026-09-29T08:30:00Z")
        log = (root / "logs" / "gc_lane.log").read_text(encoding="utf-8")
        assert rc4 == 4 and trace4 == [] and "window" in log.splitlines()[-2], (
            f"inside GitHub's night window the lane ran {trace4} (exit {rc4})")
        assert not (root / "archive" / ".lock").exists(), "the lane held for GitHub kept its lock"
        rc5, trace5 = lane_run(held, clock="2026-09-29T14:00:00Z")
        log = (root / "logs" / "gc_lane.log").read_text(encoding="utf-8")
        assert rc5 == 4 and trace5 == [] and "cloud.py pull" in log.splitlines()[-2], (
            f"with the bucket's refusal record never read the lane ran {trace5} (exit {rc5})")
        (root / "archive" / "cloud").mkdir()
        read = json.dumps({"refusal": {"read": 1790689200, "kind": "r2"}})  # 2026-09-29 13:40 UTC
        (root / "archive" / "cloud" / "pull.json").write_text(read, encoding="utf-8")
        rc6, trace6 = lane_run(held, clock="2026-09-29T14:00:00Z")
        assert rc6 == 0 and trace6 == ["held-1", "held-2", "make-stop-3"], (
            f"after the window, with the refusal record read since, the lane ran {trace6} "
            f"(exit {rc6})")

        # Each daily step asks: the first here makes the bucket's refusal record
        # unread, so the second must not start. And one that exits 4 was held,
        # not run -- not recorded, and the lane stops rather than loop on it.
        def recorded_today():
            p = root / "logs" / "gc_lane.daily"
            return {ln.split("\t", 1)[1] for ln in p.read_text(encoding="utf-8").splitlines()
                    if ln.startswith(_time.strftime("%Y-%m-%d"))} if p.exists() else set()
        two = ["daily 00:00 stub.py daily-unread 0 unread", "daily 00:00 stub.py daily-next 0",
               "stub.py after-daily 0"]
        rc7, trace7 = lane_run(two, clock="2026-09-29T14:00:00Z")
        assert rc7 == 4 and trace7 == ["daily-unread"], (
            f"a daily step started without asking whose turn it was: the lane ran {trace7} "
            f"(exit {rc7})")
        assert "daily 00:00 stub.py daily-next 0" not in recorded_today(), \
            "a daily step the lane never started was recorded as run"
        (root / "archive" / "cloud" / "pull.json").write_text(read, encoding="utf-8")
        # A 4 that GitHub's turn explains -- here the step leaves the refusal
        # record unread as it goes -- was held: not recorded, and a stop.
        four = ["daily 00:00 stub.py daily-held 4 unread", "stub.py after-held 0"]
        rc8, trace8 = lane_run(four, clock="2026-09-29T14:00:00Z")
        assert rc8 == 4 and trace8 == ["daily-held"], (
            f"after a daily step that exited 4 the lane ran {trace8} (exit {rc8}); wanted a stop")
        assert "daily 00:00 stub.py daily-held 4 unread" not in recorded_today(), \
            "a daily step held for GitHub's turn (exit 4) was recorded as run, and would be lost"
        (root / "archive" / "cloud" / "pull.json").write_text(read, encoding="utf-8")

        # A 4 that GitHub's turn does not explain is the stand-down itself:
        # recorded, the line named for taking out, and the lane goes on.
        gone = ["daily 00:00 stub.py daily-standdown 4", "daily 00:00 stub.py daily-after-it 0",
                "stub.py make-stop-4 0"]
        rc9, trace9 = lane_run(gone, clock="2026-09-29T14:00:00Z")
        log = (root / "logs" / "gc_lane.log").read_text(encoding="utf-8")
        assert rc9 == 0 and trace9 == ["daily-standdown", "daily-after-it", "make-stop-4"], (
            f"after a daily step stood down for good the lane ran {trace9} (exit {rc9})")
        assert {"daily 00:00 stub.py daily-standdown 4", "daily 00:00 stub.py daily-after-it 0"} \
            <= recorded_today(), "a daily step stood down for good was not recorded, and would " \
                                 "be asked again at every boundary"
        assert "should come out of" in log and "daily-standdown" in log, \
            "the log did not say the stood-down daily line should come out of the queue"

        # GitHub's window stops a step part way: whatever it exits, it is not
        # done, and the lane stops with 4.
        done_file = root / "logs" / "gc_lane.done"

        def done_lines():
            return done_file.read_text(encoding="utf-8").splitlines() if done_file.exists() else []
        cut = [(["daily 00:00 stub.py daily-win-0 0 window", "daily 00:00 stub.py daily-win-0b 0",
                 "stub.py after-win-0 0"], "daily-win-0", True, 0),
               (["daily 00:00 stub.py daily-win-1 1 window", "daily 00:00 stub.py daily-win-1b 0",
                 "stub.py after-win-1 0"], "daily-win-1", True, 1),
               (["stub.py once-win-0 0 window", "stub.py after-once-0 0"], "once-win-0", False, 0),
               (["stub.py once-win-1 1 window", "stub.py after-once-1 0"], "once-win-1", False, 1),
               (["stub.py once-win-with 0 window-with", "stub.py after-with 0"], "once-win-with",
                False, 4)]
        for lines_, name, is_daily, exited in cut:
            rc, trace = lane_run(lines_, clock="2026-09-29T14:00:00Z")
            log = (root / "logs" / "gc_lane.log").read_text(encoding="utf-8").splitlines()
            said = [ln for ln in log if "night window stopped it" in ln]
            assert rc == 4 and trace == [name], (
                f"after {name}, which GitHub's window stopped part way and which exited "
                f"{exited}, the lane ran {trace} (exit {rc}); wanted a stop with 4")
            assert said and f"exited {exited}, but" in said[-1] and name in " ".join(log[-6:]), (
                f"the lane did not say GitHub's window cut {name} short, or it did not exit "
                f"{exited}: {log[-3:]}")
            assert not any(name in ln for ln in done_lines() + sorted(recorded_today())), \
                f"{name}, cut short by GitHub's window, was recorded as run"
            if is_daily:
                assert not any(ln.startswith(lines_[1]) for ln in recorded_today()), \
                    f"the daily step after {name} was recorded as run, or skipped for the day"
            assert not (root / "logs" / "gc_lane.window-stop").exists(), \
                "the lane left the window-stop file behind"
        return "ok", ("daily steps once a day before the queue, a failure skipping the rest of the "
                      "day's and not the lane, none again on a restart, a stop at the boundary, "
                      "a refusal still ending it, and a stood-down lane waiting for GitHub's "
                      "night and for a read of the bucket's refusal -- asked before each daily "
                      "step, a held one not recorded as run, a stood-down one recorded and "
                      "named, and a step the window cut short done in neither list whatever "
                      "it exited -- all sealed from the network")
    finally:
        seal.close()
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the what-is-running one-liner pastes into cmd and names every kind of worker")
def _running_oneliner():
    """watchers/README.md's process list is what CLAUDE.md and HANDOFF.md send a
    session to before it starts anything, and until 26 September it could not
    be pasted into cmd, the shell the person uses: it wrapped PowerShell in
    `python3 -c` with \\" inside double quotes, and cmd, which has no backslash
    escape, ended the string there and took the | after it for a pipe. And its
    pattern, "watch|fetch_", missed the lane's nightly, the snapshot, publish
    and cloud.py, while "watch" alone matches the gpu-watchdog flag of every
    Edge and Teams process on the machine.
    """
    p = Path("watchers/README.md")
    if not p.exists():
        return "skip", "watchers/README.md not here"
    lines = [ln for ln in _source(p).splitlines()
             if "Get-CimInstance Win32_Process" in ln and not ln.startswith(("`", " "))]
    assert len(lines) == 1, f"{len(lines)} process one-liners in {p}, not one"
    ln = lines[0]
    assert ln.startswith('powershell -NoProfile -Command "') and ln.endswith('"') \
        and ln.count('"') == 2 and '\\"' not in ln, \
        "the one-liner is not one double-quoted PowerShell command cmd can pass whole"
    m = re.search(r"-match '([^']+)'", ln)
    assert m, "the one-liner does not match command lines against a pattern"
    pattern = re.compile(m.group(1), re.I)
    # probe_*.py and resolve_members.py ask the General Court too (the
    # refusal check reads them for that), so a session looking for what is
    # running must see them.
    for want in (r"python3 watchers\gc_lane.py", "python3 nightly.py --no-fetch",
                 "python3 src/fetch/gc_web/fetch_legislation.py --all", "python3 src/fetch/gc_web/snapshot_gencourt.py",
                 r"cmd /c publish.bat", "python3 src/ops/cloud.py pull",
                 r"python3 watchers\captions_watch.py", "python3 src/fetch/gc_web/probe_calendars.py",
                 "python3 src/fetch/gc_db/probe_db.py --sample", "python3 src/fetch/gc_web/resolve_members.py"):
        assert pattern.search(want), f"the one-liner would not list: {want}"
    assert not pattern.search("msedgewebview2.exe --gpu-watchdog-timeout-seconds=60 "
                              "--enable-features=RendererHangWatcher"), \
        "the one-liner lists every Edge and Teams process too"
    return "ok", "one double-quoted command, listing the lane, nightly, fetches, publish and cloud.py"


# ---- reader reports -------------------------------------------------------------
#
# The report box, the Function behind it, and the nightly compiler. Everything a
# reader types is untrusted, and part of it will be read by an assistant; the
# person who owns the site asked for attempts to steer that assistant to be
# accounted for, and for substantial changes a report leads to to come to them.

REPORT_JS_TEST = r"""
import { validate, cleanNote, onRequest } from %s;
const fail = [];
const ok = (l, c) => { if (!c) fail.push(l); };
const good = { record: "bill:2026/HB100", url: "/bill/2026/hb100", tab: "Votes (2)",
  field: "vote", build: "2026-09-12T12:36:07", elapsed: 9000, note: "The count is 191-150." };
ok("a real report passes", validate(good) && validate(good).tab === "Votes");
ok("honeypot", validate({ ...good, website: "x" }) === null);
ok("too quick", validate({ ...good, elapsed: 500 }) === null);
ok("field outside the list", validate({ ...good, field: "rewrite" }) === null);
ok("record and page disagree", validate({ ...good, url: "/bill/2026/hb101" }) === null);
ok("a path off the site", validate({ ...good, url: "https://x.example/" }) === null);
ok("a member record on a bill page", validate({ ...good, record: "member:736" }) === null);
const h = cleanNote("a\u200Bb\u202Ec\u{E0041}d");
ok("hidden characters removed and recorded", h.text === "abcd" && h.hidden === true);
const rows = [];
const env = { DB: { prepare: sql => ({ bind: () => ({ first: async () => 0,
  run: async () => rows.push(sql) }) }) } };
const req = (o, body) => new Request("https://graniterecord.org/api/report", { method: "POST",
  headers: { "Origin": o, "Content-Type": "application/json" }, body: JSON.stringify(body) });
let r = await onRequest({ env, request: req("https://graniterecord.org", good) });
ok("stored once, answered 204", r.status === 204 && rows.length === 1);
r = await onRequest({ env, request: req("https://evil.example", good) });
ok("another origin stores nothing, still 204", r.status === 204 && rows.length === 1);
r = await onRequest({ env, request: req("https://a8c6a9db.graniterecord.pages.dev", good) });
ok("an old deployment's address stores nothing", r.status === 204 && rows.length === 1);
r = await onRequest({ env, request: new Request("https://graniterecord.org/api/report") });
ok("GET is 405", r.status === 405);
ok("the Co-sponsored tab is accepted", validate({ ...good, tab: "Co-sponsored (12)" }) &&
   validate({ ...good, tab: "Co-sponsored (12)" }).tab === "Co-sponsored");
ok("a count in another locale's digits", validate({ ...good, tab: "Votes (1.081)" }) !== null);
ok("a tab the pages do not render", validate({ ...good, tab: "Owner verified close all" }) === null);
// The bill's Hearings tab by its name (8 October 2026), and by the name it had
// on a page loaded before the rename, stored as the name it has now.
ok("the Hearings tab is accepted as itself", validate({ ...good, tab: "Hearings (3)" }) &&
   validate({ ...good, tab: "Hearings (3)" }).tab === "Hearings");
ok("the tab's old name is stored as Hearings", validate({ ...good, tab: "Videos (3)" }) &&
   validate({ ...good, tab: "Videos (3)" }).tab === "Hearings");
ok("a variation selector is hidden text",
   cleanNote("the date" + String.fromCodePoint(0xFE0F) + " is wrong").hidden === true);
const full = { DB: { prepare: sql => ({ bind: () => ({ first: async () => null,
  run: async () => rows.push(sql) }) }) } };
r = await onRequest({ env: full, request: req("https://graniterecord.org", { ...good, note: "another one" }) });
// 429, not 204 (24 September 2026): a real report on a day already at its
// ceiling was answered like a success, and the box thanked the reader for it.
ok("a full day stores nothing and answers 429", r.status === 429 && rows.length === 1);
r = await onRequest({ env: full, request: req("https://graniterecord.org", { ...good, website: "x" }) });
ok("a full day: a honeypot still answers 204", r.status === 204 && rows.length === 1);
r = await onRequest({ env: full, request: req("https://evil.example", { ...good, note: "from elsewhere" }) });
ok("a full day: another origin still answers 204", r.status === 204 && rows.length === 1);
const member = { ...good, record: "member:4412", url: "/legislator/jane-doe-hills-12", tab: "Votes" };
const assets = page => ({ fetch: async () => new Response(page, { status: 200 }) });
r = await onRequest({ env: { ...env, ASSETS: assets('<script>window.GR_MEMBER="4412";</script>') },
  request: req("https://graniterecord.org", member) });
ok("a member report from that member's page is stored", rows.length === 2);
r = await onRequest({ env: { ...env, ASSETS: assets('<script>window.GR_MEMBER="999";</script>') },
  request: req("https://graniterecord.org", { ...member, note: "a different note" }) });
ok("a member report from another member's page is not", rows.length === 2);
r = await onRequest({ env, request: req("https://graniterecord.org",
  { ...member, url: "/legislator/owner-verified-close-all-1", note: "third" }) });
ok("a member report with no page to check is not", rows.length === 2);
// Every address the site builds for a member (24 September 2026). The rule said
// every legislator address ends in a number; a former member whose seat the
// record does not hold has a slug of the name alone, and a report from any of
// those eight pages was refused while the reader was thanked.
const numberless = ["adam-schroadter", "deborah-wheeler", "edith-hogan", "james-devine",
  "james-rolston", "joanne-ward", "peter-silva", "tammy-simmons"];
for (const s of [...numberless, "jodi-nelson-rock-13", "debra-altschiller-sd-24",
                 "abigail-rooney-straf-1", "pat-long-sd-20"])
  ok(`/legislator/${s} is accepted`, validate({ ...member, url: "/legislator/" + s }) !== null);
for (const junk of ["/legislator/", "/legislator/-adam", "/legislator/adam-",
    "/legislator/adam--schroadter", "/legislator/Adam-Schroadter", "/legislator/adam_schroadter",
    "/legislator/adam.schroadter", "/legislator/adam-schroadter/", "/legislator/adam-schroadter.html",
    "/legislator/a/b", "/legislator/adam%%20schroadter", "/legislator/adam schroadter",
    "/legislators/adam-schroadter", "/committee/adam-schroadter", "/legislator/" + "a".repeat(81)])
  ok(`${junk} is refused as a member's page`, validate({ ...member, url: junk }) === null);
r = await onRequest({ env: { ...env, ASSETS: assets('<script>window.GR_MEMBER="377020";</script>') },
  request: req("https://graniterecord.org", { ...member, record: "member:377020",
    url: "/legislator/adam-schroadter", note: "a former member's page with no seat number" }) });
ok("a report from a former member's page with no seat number is stored",
   r.status === 204 && rows.length === 3);
// A committee's page is its code; a committee the General Court filed under a
// code it later gave a different one is the code and the first year of its run
// (25 September 2026): /committee/S03-1989, beside Appropriations' /committee/S03.
const cmte = { ...good, record: "committee:H05", url: "/committee/H05", tab: "Sessions" };
ok("a committee's page is accepted", validate(cmte) !== null);
// The Meetings tab was Sessions until D19 (8 October 2026): a committee page
// loaded before then still sends that, and it is stored as the tab's name now.
ok("a committee's Sessions tab is stored as Meetings", validate(cmte) &&
   validate(cmte).tab === "Meetings" && validate({ ...cmte, tab: "Meetings (28)" }).tab === "Meetings");
ok("a committee's page at its code and first year is accepted",
   validate({ ...cmte, record: "committee:S03-1989", url: "/committee/S03-1989" }) !== null);
for (const [rec, url] of [["committee:S03-1989", "/committee/S03"],
    ["committee:S03", "/committee/S03-1989"], ["committee:S03-89", "/committee/S03-89"],
    ["committee:S03-1989-1990", "/committee/S03-1989-1990"], ["committee:S03-", "/committee/S03-"],
    ["committee:S03-1989x", "/committee/S03-1989x"], ["committee:1989", "/committee/1989"]])
  ok(`${rec} from ${url} is refused`, validate({ ...cmte, record: rec, url }) === null);
// A session day and a study committee (the cohesion audit, I-8), each from
// its own address and from no other.
const day = { ...good, record: "session:H/2010-03-11", url: "/session/H/2010-03-11", tab: "" };
ok("a session day's page is accepted", validate(day) !== null);
ok("a Senate session day's page is accepted",
   validate({ ...day, record: "session:S/2024-12-04", url: "/session/S/2024-12-04" }) !== null);
const ss = { ...good, record: "study:ss1451", url: "/committee/ss1451", tab: "Meetings (3)" };
ok("a study committee's page is accepted", validate(ss) !== null && validate(ss).tab === "Meetings");
for (const [rec, url] of [["session:H/2010-03-11", "/session/H/2010-03-12"],
    ["session:H/2010-03-11", "/session/S/2010-03-11"], ["session:X/2010-03-11", "/session/X/2010-03-11"],
    ["session:H/2010-3-11", "/session/H/2010-3-11"], ["session:H/2010-03-11", "/committee/ss1451"],
    ["study:ss1451", "/committee/ss1452"], ["study:ss1451", "/session/H/2010-03-11"],
    ["study:H05", "/committee/H05"], ["committee:ss1451", "/committee/ss1451"],
    ["study:ss1451", "/legislator/jane-doe-hills-12"], ["session:H/2010-03-11", "/legislator/x"]])
  ok(`${rec} from ${url} is refused`, validate({ ...good, record: rec, url, tab: "" }) === null);
// A bill request (11 November 2026), from its own address only, on its one tab.
const rq = { ...good, record: "request:2027-0012", url: "/request/2027-0012", tab: "Summary" };
ok("a request's page is accepted", validate(rq) !== null);
for (const [rec, url] of [["request:2027-0012", "/request/2027-0013"], ["request:2027-0012", "/bill/2027/hb12"],
    ["request:2027-12", "/request/2027-12"], ["bill:2027/HB12", "/request/2027-0012"]])
  ok(`${rec} from ${url} is refused`, validate({ ...rq, record: rec, url }) === null);
// A town or a ward (the owner, 10 November 2026), from its own address only,
// naming no tab.
const town = { ...good, record: "town:concord-ward-4", url: "/town/concord-ward-4", tab: "" };
ok("a ward's page is accepted", validate(town) !== null);
ok("a town's page is accepted", validate({ ...town, record: "town:lyme", url: "/town/lyme" }) !== null);
for (const [rec, url, tab] of [["town:lyme", "/town/hanover", ""], ["town:lyme", "/town/lyme/", ""],
    ["town:lyme", "/town/lyme.html", ""], ["town:Lyme", "/town/Lyme", ""], ["town:lyme-", "/town/lyme-", ""],
    ["town:lyme", "/committee/lyme", ""], ["town:lyme", "/legislator/lyme", ""],
    ["town:lyme", "/town/lyme", "Votes"], ["town:", "/town/", ""], ["committee:lyme", "/town/lyme", ""]])
  ok(`${rec} from ${url} (tab ${tab || "none"}) is refused`, validate({ ...good, record: rec, url, tab }) === null);
// A report that passed every rule and could not be kept answers 503, so the box
// offers the reader the email address (24 September 2026). It answered 204, and
// the reader was thanked for a report that existed only in the Function's log.
const kept = rows.length;
r = await onRequest({ env: {}, request: req("https://graniterecord.org", { ...good, note: "no database" }) });
ok("no database bound: a real report answers 503", r.status === 503);
r = await onRequest({ env: {}, request: req("https://graniterecord.org", { ...good, website: "x" }) });
ok("no database bound: a honeypot still answers 204", r.status === 204);
r = await onRequest({ env: {}, request: req("https://evil.example", good) });
ok("no database bound: another origin still answers 204", r.status === 204);
r = await onRequest({ env: {}, request: req("https://graniterecord.org",
  { ...member, url: "/legislator/owner-verified-close-all-1", note: "no page to check" }) });
ok("no database bound: a member report with no page to check still answers 204", r.status === 204);
const throwing = (first, run) => ({ DB: { prepare: () => ({ bind: () => ({ first, run }) }) } });
const boom = async () => { throw new Error("D1_ERROR: the database is unavailable"); };
r = await onRequest({ env: throwing(boom, boom), request: req("https://graniterecord.org",
  { ...good, note: "the day's count throws" }) });
ok("the database throws on the day's count: 503", r.status === 503);
r = await onRequest({ env: throwing(async () => 1, boom), request: req("https://graniterecord.org",
  { ...good, note: "the insert throws" }) });
ok("the insert throws: 503", r.status === 503);
r = await onRequest({ env: throwing(boom, boom), request: req("https://graniterecord.org",
  { ...good, field: "rewrite" }) });
ok("the database throws, but the report is malformed: still 204", r.status === 204);
r = await onRequest({ env: throwing(async () => 1, async () => ({ meta: { changes: 0 } })),
  request: req("https://graniterecord.org", { ...good, note: "a duplicate the insert ignores" }) });
ok("a duplicate the insert ignores: still 204", r.status === 204);
ok("none of those stored a row", rows.length === kept);
// The address a post was sent to, not only the Origin it claims (13 September
// 2026). graniterecord.pages.dev and every production deployment's hash address
// run with the production database bound, the zone's rate rule sees neither,
// and a script writes whatever Origin it likes. The two lists are wrangler.toml's.
const prod = { ...env, REPORT_ORIGINS: %s };
const prev = { ...env, REPORT_ORIGINS: %s };
const sentTo = (at, o, body) => new Request(at + "/api/report", { method: "POST",
  headers: { "Origin": o, "Content-Type": "application/json" }, body: JSON.stringify(body) });
const before = rows.length;
r = await onRequest({ env: prod, request: sentTo("https://graniterecord.pages.dev",
  "https://graniterecord.org", { ...good, note: "sent to the project address" }) });
ok("production, sent to graniterecord.pages.dev under the site's Origin: nothing stored",
   r.status === 204 && rows.length === before);
r = await onRequest({ env: prod, request: sentTo("https://a8c6a9db.graniterecord.pages.dev",
  "https://graniterecord.org", { ...good, note: "sent to a deployment address" }) });
ok("production, sent to a deployment's hash address under the site's Origin: nothing stored",
   r.status === 204 && rows.length === before);
r = await onRequest({ env: prod, request: sentTo("https://a8c6a9db.graniterecord.pages.dev",
  "https://a8c6a9db.graniterecord.pages.dev", { ...good, note: "sent from and to a deployment" }) });
ok("production, a hash address as both host and Origin: nothing stored",
   r.status === 204 && rows.length === before);
r = await onRequest({ env: prod, request: new Request("https://graniterecord.pages.dev/api/report") });
ok("GET on a refused host is still 405", r.status === 405);
r = await onRequest({ env: prod, request: sentTo("https://graniterecord.org",
  "https://graniterecord.org", { ...good, note: "sent to the site itself" }) });
ok("production, the site's own address and Origin: stored", r.status === 204 && rows.length === before + 1);
// The path as well as the host (13 September 2026): the Pages router sends
// /api/report/ here too, and a rate rule on path eq "/api/report" does not
// count it. The page posts to /api/report and nothing else.
const at = (path, note) => new Request("https://graniterecord.org" + path, { method: "POST",
  headers: { "Origin": "https://graniterecord.org", "Content-Type": "application/json" },
  body: JSON.stringify({ ...good, note }) });
r = await onRequest({ env: prod, request: at("/api/report/", "sent with a trailing slash") });
ok("production, sent to /api/report/ with a trailing slash: nothing stored",
   r.status === 204 && rows.length === before + 1);
r = await onRequest({ env: prod, request: at("/API/Report", "sent in other letters") });
ok("production, sent to /API/Report: nothing stored", r.status === 204 && rows.length === before + 1);
r = await onRequest({ env: prod, request: at("/api/report?from=box", "sent with a query") });
ok("production, /api/report with a query string is still that path: stored",
   r.status === 204 && rows.length === before + 2);
r = await onRequest({ env: prev, request: sentTo("https://abc123.graniterecord.pages.dev",
  "https://abc123.graniterecord.pages.dev", { ...good, note: "sent to a preview" }) });
ok("preview, a preview deployment's own address: stored", r.status === 204 && rows.length === before + 3);
// A MISTAKE IN A TRANSLATION (the owner, 24 October 2026): reported from the
// page's own address, which names its language, as the field "translation"
// with no tab, and kept only from a page the site built in that language.
const tr = { record: "translation:/es/guides/how-to-vote", url: "/es/guides/how-to-vote", tab: "",
  field: "translation", build: "", elapsed: 9000, note: "\u00abVote\u00bb should read \u00abVotar\u00bb." };
ok("a translation report passes", validate(tr) && validate(tr).kind === "translation");
ok("the Spanish home page's passes", validate({ ...tr, record: "translation:/es/", url: "/es/" }) !== null);
ok("a Spanish calendar week's passes", validate({ ...tr, record: "translation:/es/calendar/2026-W45",
   url: "/es/calendar/2026-W45" }) !== null);
for (const [rec, url] of [["translation:/es/guides/how-to-vote", "/es/guides/real-id"],
    ["translation:/es/Guides/x", "/es/Guides/x"], ["translation:/es/calendar/2026-W4", "/es/calendar/2026-W4"],
    ["translation:/es/calendar/W45", "/es/calendar/W45"],["translation:/es/a/b/c/d", "/es/a/b/c/d"],
    ["translation:/fr/x", "/fr/x"], ["translation:/es/../x", "/es/../x"], ["translation:/es", "/es"],
    ["translation:/es/x-", "/es/x-"], ["translation:/es/x.html", "/es/x.html"],
    ["translation:es/x", "es/x"], ["translation:/es/x", "/bill/2026/hb1"], ["translation:/bill/2026/hb1", "/bill/2026/hb1"]])
  ok(`${rec} from ${url} is refused`, validate({ ...tr, record: rec, url }) === null);
ok("a translation of another field is refused", validate({ ...tr, field: "other" }) === null);
ok("a translation with a tab is refused", validate({ ...tr, tab: "Votes" }) === null);
ok("a bill's report of the translation field is refused", validate({ ...good, field: "translation" }) === null);
const esPage = { fetch: async u => new URL(u).pathname === "/es/guides/how-to-vote"
  ? new Response('<!DOCTYPE html><html lang="es" data-alt-en="/guides/how-to-vote">')
  : new Response("", { status: 404 }) };
const nTr = rows.length;
r = await onRequest({ env: { ...env, ASSETS: esPage }, request: req("https://graniterecord.org", tr) });
ok("a translation report from a page in Spanish is stored", r.status === 204 && rows.length === nTr + 1);
r = await onRequest({ env: { ...env, ASSETS: esPage }, request: req("https://graniterecord.org",
  { ...tr, record: "translation:/es/guides/real-id", url: "/es/guides/real-id", note: "no such page" }) });
ok("a translation report from a page the site did not build is not", r.status === 204 && rows.length === nTr + 1);
r = await onRequest({ env: { ...env, ASSETS: { fetch: async () => new Response('<!DOCTYPE html><html lang="en">') } },
  request: req("https://graniterecord.org", { ...tr, note: "a page in English" }) });
ok("a translation report from a page not in its language is not", r.status === 204 && rows.length === nTr + 1);
r = await onRequest({ env, request: req("https://graniterecord.org", { ...tr, note: "no page to check" }) });
ok("a translation report with no page to check is not", r.status === 204 && rows.length === nTr + 1);
console.log(fail.length ? "FAILED: " + fail.join("; ") : "ALL OK");
process.exit(fail.length ? 1 : 0);
"""


@check("build", "the email sender's own tests pass, every one: node --test runs "
       "tests/follow/index.js, which imports every test file in tests/follow/")
def _follow_tests():
    """tests/follow/ is the email sender's test suite (workers/follow/ and
    functions/api/follow/), standard library only, a few seconds in node. It
    is run here whole, so a change to the Worker, the Functions or the site's
    files they draw on (site.gen.js) is tested before it merges, and on the
    night by nightly.py's preflight --code.

    index.js by name, which imports every test file into one process: the
    folder form passed on Node 22 here and failed on GitHub's Node 24 under
    Windows (the dry run of 51a6944). Node's one-time ExperimentalWarning for
    node:sqlite (the fake D1) is not a log line of the code under test. TAP
    by name too: the counts are read off "# pass N", and Node 24's default
    reporter prints "ℹ pass N" instead (the dry run of 5e2ef8f, whose 106
    tests all passed and whose count this check could not find).

    AND EVERY TEST FILE IS IN index.js (23 October 2026). A file left out of
    it is never run by node --test on the folder or by this, and passes in
    silence; so the list is held to the folder's *.test.js."""
    index = Path("tests/follow/index.js")
    if not index.is_file():
        return "skip", "tests/follow/index.js is not here"
    imported = re.findall(r'^import\s+"\./([^"]+)";', _source(index), re.M)
    files = sorted(p.name for p in index.parent.glob("*.test.js"))
    missing = [f for f in files if f not in imported]
    assert not missing, (f"tests/follow/index.js does not import {', '.join(missing)}, so node --test "
                         "never runs it: add an import line for each")
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", f"node is not on PATH, so the {len(files)} test files in tests/follow/ did not run"
    r = _run([node, "--disable-warning=ExperimentalWarning", "--test", "--test-reporter=tap",
              index.as_posix()], capture_output=True, text=True, timeout=300)
    out = (r.stdout or "") + (r.stderr or "")
    count = {k: int(v) for k, v in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$",
                                               out, re.M)}
    fails = _tap_failures(out)
    assert not fails, (
        f"tests/follow/ fails {len(fails)} of {count.get('tests', '?')}: "
        + "; ".join(f"{n!r} ({s})" if s else repr(n) for n, s in fails[:6])
        + (f" (+{len(fails) - 6} more)" if len(fails) > 6 else "")
        + f". `node --test {index.as_posix()}` shows each in full")
    assert r.returncode == 0 and count.get("pass", 0) > 0 and not count.get("fail") \
        and not count.get("cancelled"), (
        f"node --test {index.as_posix()} exited {r.returncode} with {count or 'no count'}: "
        + out.strip()[-500:])
    return "ok", (f"tests/follow: {count['pass']} passed of {count.get('tests')}, from "
                  f"{len(files)} test files, every one imported by index.js")


def _js_block(text, opening, closing):
    """The source from `opening` to the first `closing` after it, or "" when
    `opening` is not in the text: one function of a JS file, read as text."""
    at = text.find(opening)
    if at < 0:
        return ""
    end = text.find(closing, at)
    return text[at:end if end >= 0 else len(text)]


@check("build", "the email sender's test send answers on the preview alone, behind its var and "
       "its token; production has neither and no address, and run() is the same with or without it")
def _follow_test_send():
    """The person, 23 October 2026: "Is there a way you can manually trigger
    sending me test emails since my account is already signed up for updates
    on a number of bills and topics?" The preview sender answers POST
    /test-send (sender.js, A TEST SEND), which sends the subscribers in the
    preview's database test emails and records nothing. It is the one request
    the sender answers, so it is held here from four sides:

    PRODUCTION CANNOT REACH IT. workers/follow/wrangler.toml's top level is
    the production sender: workers_dev = false, no route, and no TEST_SEND in
    its [vars]. Only [env.preview.vars] sets TEST_SEND = "on", and only
    [env.preview] has workers_dev = true. No section of the file sets the
    TEST_SEND_TOKEN secret, which is set with wrangler on the preview Worker.

    NOT WITHOUT BOTH GUARDS. tests/follow/test_send.test.js's cases, run by
    name: a 404 without the var, with a wrong or missing token, and on
    production's own vars with the right token; and sender.js asks the var,
    and compares the token with address.js's sameText, before anything else.

    run() IS THE SAME. The test send's case that runs the 8:00 run after a
    test send and without one, and holds every email, log line and table to
    be the same; run() names nothing of the test path (testifyAhead, which
    makes a bill with a hearing ahead say "open" on any day, is the test's
    alone); and the test path's SQL is SELECTs only. One read of TEST_SEND is
    no part of the test path and is allowed in run(): isPreviewSender, once,
    which keeps the preview from raising `tonight` (7 November 2026;
    _follow_preview_tells_nobody holds it, and that it is called once).

    NO ADDRESS OUT. The test path logs through note() with fixed codes only,
    and the privacy case reads every log line and answer of a test send for
    an address, a link's token, a followed record and the bearer token."""
    toml_path, js_path = Path("workers/follow/wrangler.toml"), Path("workers/follow/sender.js")
    if not (toml_path.is_file() and js_path.is_file()):
        return "skip", "no workers/follow here"
    import tomllib
    conf = tomllib.loads(_source(toml_path))
    envs = conf.get("env", {})
    assert conf.get("workers_dev") is False, (
        "workers/follow/wrangler.toml: the production sender must keep workers_dev = false, so that "
        "it has no address to be asked at")
    assert not ({"route", "routes"} & set(conf)), "workers/follow/wrangler.toml gives the production sender a route"
    assert "TEST_SEND" not in conf.get("vars", {}), (
        "workers/follow/wrangler.toml sets TEST_SEND in [vars], which is production's: it belongs in "
        "[env.preview.vars] alone")
    others = sorted(n for n, e in envs.items() if n != "preview" and "TEST_SEND" in e.get("vars", {}))
    assert not others, f"workers/follow/wrangler.toml sets TEST_SEND for {others}, not the preview alone"
    preview = envs.get("preview", {})
    assert preview.get("vars", {}).get("TEST_SEND") == "on" and preview.get("workers_dev") is True, (
        "the preview sender has no test send: [env.preview] wants workers_dev = true and "
        '[env.preview.vars] TEST_SEND = "on"')

    def keys(d):
        for k, v in d.items():
            yield k
            if isinstance(v, dict):
                yield from keys(v)
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, dict):
                        yield from keys(x)
    assert "TEST_SEND_TOKEN" not in set(keys(conf)), \
        "workers/follow/wrangler.toml sets TEST_SEND_TOKEN: a secret goes in with wrangler secret put"

    js = _source(js_path)
    run_src = _js_block(js, "export async function run(", "\n}\n")
    path_src = (_js_block(js, "export function testSendAllowed(", "\n}\n")
                + _js_block(js, "export function testAsk(", "\n}\n")
                + _js_block(js, "export async function testSend(", "\n}\n")
                + _js_block(js, "  async fetch(request, env) {", "\n  },\n"))
    assert run_src and "testSend(" in path_src and "testSendAllowed(request, env)" in path_src, \
        "sender.js's run(), testSend() or its fetch handler is not where this check reads them"
    named = sorted(set(re.findall(r"\b(testifyAhead|testSend\w*|testAsk|TEST_\w+)\b", run_src)))
    assert not named, f"sender.js's run() names the test send's {named}: a real run must not"
    allowed = _js_block(js, "export function testSendAllowed(", "\n}\n")
    first = allowed.find('env?.TEST_SEND !== "on"')
    assert 0 <= first < allowed.find("sameText(") and "TEST_SEND_TOKEN" in allowed, \
        "sender.js's testSendAllowed no longer asks the TEST_SEND var first and the token by sameText"
    fetch_src = _js_block(js, "  async fetch(request, env) {", "\n  },\n")
    assert re.search(r"if \(!testSendAllowed\(request, env\)\) return notFound\(\);", fetch_src.split("\n")[1]), \
        "sender.js's fetch handler does not answer the 404 before anything else when a guard fails"
    writes = sorted(set(re.findall(r"\b(UPDATE|INSERT|DELETE|forget\(|purge\(|giveBack|moveCursor|sealFollow)",
                                   path_src)))
    assert not writes, f"sender.js's test send writes ({writes}): it must record nothing"
    # Its own codes, and into them only a refusal's key (resend-<status>,
    # error-<name>) or an error's name: never a value of a reader's.
    codes = [c.strip() for c in re.findall(r"\bnote\(\s*((?:[^,()]|\([^()]*\))+)", path_src)]
    loose = [c for c in codes if not re.match(r"""^["`]sender\.test-""", c)
             or set(re.findall(r"\$\{[^}]*\}", c)) - {"${k}", "${errName(e)}"}]
    assert codes and not loose, f"the test send logs something other than its own fixed codes: {loose}"

    node = shutil.which("node") or shutil.which("node.exe")
    if not (node and Path("tests/follow/index.js").is_file()):
        return "skip", "node or tests/follow/ is not here; wrangler.toml and sender.js hold"
    cases = ("test send: 404 without the TEST_SEND var",
             "test send: 404 with a wrong or missing token",
             "test send: 404 on the production configuration",
             "test send: only confirmed subscribers are sent, each subject prefixed Test",
             "test send: changes no subscriber row, cursor, follow, sends or signup_days",
             "test send: a run after a test send does exactly what a run without one does",
             "test send: an empty digest is a short note",
             "test send: at most five subscribers",
             "a test send leaves no address, token or follow list in a log line or its answer")
    r = _run([node, "--disable-warning=ExperimentalWarning", "--test", "--test-reporter=tap",
              "--test-name-pattern=" + "|".join(cases), "tests/follow/index.js"],
             capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    passed = [c for c in cases
              if re.search(rf"^ok \d+ - [^\n]*{re.escape(c)}(?![^\n]*# SKIP)", out, re.M)]
    assert r.returncode == 0 and len(passed) == len(cases), (
        "tests/follow/ no longer passes the test send's cases "
        + ", ".join(repr(c) for c in cases if c not in passed) + ": " + out.strip()[-400:])
    return "ok", ("production's sender has no address and no TEST_SEND; the preview's has both and "
                  f"no token in the file; run() names nothing of the test path; {len(cases)} cases pass")


@check("build", "the preview email sender raises no tonight problem and never pings Healthchecks, "
       "even with the secret set; the README gives HEALTHCHECK_URL to production alone")
def _follow_preview_tells_nobody():
    """The person, 7 November 2026: Healthchecks emails only when something
    needs them. The preview sender (`--env preview`) reads the dry-run site,
    which has a night's changes file only on a morning a dry run deployed,
    so at noon on most days it raised `tonight` and its /fail emailed "down",
    and the next hour's ping "up": five times in November. It had the same
    HEALTHCHECK_URL as production because the README's secrets table said
    to add every sender secret with --env preview.

    Held from three sides. THE RULE: sender.js's isPreviewSender is
    TEST_SEND = "on", which wrangler.toml's [env.preview.vars] sets and its
    production [vars] do not (_follow_test_send holds that too); run()
    pushes `tonight` only behind it, and ping() asks it before it reads the
    secret's address or fetches. THE WORDS: the README's secrets table gives
    HEALTHCHECK_URL to production alone, and no command in the folder puts
    it on the preview; wrangler.toml sets no HEALTHCHECK_URL, a secret. THE
    BEHAVIOUR: tests/follow/sender.test.js's two cases, on wrangler.toml's
    own vars -- the preview at noon with no night and the secret set raises
    nothing and pings nothing, and production still raises `tonight` and
    pings /fail."""
    folder = Path("workers/follow")
    toml_path, js_path, readme = folder / "wrangler.toml", folder / "sender.js", folder / "README.md"
    if not (toml_path.is_file() and js_path.is_file() and readme.is_file()):
        return "skip", "no workers/follow here"
    import tomllib
    conf = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    preview = conf.get("env", {}).get("preview", {})
    assert preview.get("vars", {}).get("TEST_SEND") == "on" and "TEST_SEND" not in conf.get("vars", {}), (
        "workers/follow/wrangler.toml: the preview sender is known by TEST_SEND = \"on\" in "
        "[env.preview.vars], and production's [vars] must not set it")
    raw_toml = toml_path.read_text(encoding="utf-8")
    assert not re.search(r"(?m)^\s*HEALTHCHECK_URL\s*=", raw_toml), \
        "workers/follow/wrangler.toml sets HEALTHCHECK_URL: a secret goes in with wrangler secret put"

    js = js_path.read_text(encoding="utf-8")
    rule = _js_block(js, "export function isPreviewSender(env) {", "\n}\n")
    assert re.search(r'return env\?\.TEST_SEND === "on";', rule), \
        "sender.js's isPreviewSender is no longer TEST_SEND = \"on\""
    run_src = _js_block(js, "export async function run(", "\n}\n")
    pushes = re.findall(r"^.*out\.problems\.push\(\"tonight\"\).*$", js, re.M)
    assert len(pushes) == 1 and "if (!isPreviewSender(env)) out.problems.push(\"tonight\")" in pushes[0] \
        and pushes[0].strip() in run_src, (
        f"sender.js raises `tonight` other than once, in run(), behind isPreviewSender: {pushes}")
    # The one read of TEST_SEND run() may make (_follow_test_send): nothing
    # else in a real run may differ on the preview.
    assert run_src.count("isPreviewSender(") == 1, \
        "sender.js's run() asks isPreviewSender other than once, for `tonight`"
    ping_src = _js_block(js, "export async function ping(env, out) {", "\n}\n")
    asks, fetches = ping_src.find("if (isPreviewSender(env)) {"), ping_src.find("fetch(")
    assert 0 <= asks < fetches and ping_src.find("return false;", asks) < fetches, \
        "sender.js's ping() does not return before any fetch for the preview sender"

    text = readme.read_text(encoding="utf-8")
    rows = [ln for ln in text.splitlines() if re.match(r"^\s*\|\s*`HEALTHCHECK_URL`", ln)]
    cells = [c.strip() for c in rows[0].strip().strip("|").split("|")] if len(rows) == 1 else []
    assert len(cells) == 3 and cells[1] == "no" and cells[2].startswith("production's only"), (
        f"workers/follow/README.md's secrets table must give HEALTHCHECK_URL to the sender as "
        f"\"production's only\": {rows}")
    onto_preview = [ln.strip() for p in sorted(folder.rglob("*")) if p.is_file() and
                    p.suffix in (".md", ".toml", ".js", ".sql")
                    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
                    if re.search(r"secret\s+put\s+HEALTHCHECK_URL\b.*--env\s+preview", ln)]
    assert not onto_preview, f"workers/follow/ says to put HEALTHCHECK_URL on the preview: {onto_preview}"

    node = shutil.which("node") or shutil.which("node.exe")
    if not (node and Path("tests/follow/index.js").is_file()):
        return "skip", "node or tests/follow/ is not here; sender.js, the README and wrangler.toml hold"
    cases = ("the preview sender raises no tonight problem and pings nobody, even with the secret set",
             "the production sender still raises tonight at noon and pings its /fail")
    r = _run([node, "--disable-warning=ExperimentalWarning", "--test", "--test-reporter=tap",
              "--test-name-pattern=" + "|".join(cases), "tests/follow/index.js"],
             capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    passed = [c for c in cases
              if re.search(rf"^ok \d+ - [^\n]*{re.escape(c)}(?![^\n]*# SKIP)", out, re.M)]
    assert r.returncode == 0 and len(passed) == len(cases), (
        "tests/follow/ no longer passes the preview sender's cases "
        + ", ".join(repr(c) for c in cases if c not in passed) + ": " + out.strip()[-400:])
    return "ok", ("the preview sender (TEST_SEND on) raises no tonight and pings nobody; production "
                  "still does; the README gives HEALTHCHECK_URL to production alone; "
                  f"{len(cases)} cases pass")


# THE PLANS' LIMITS, AS CLOUDFLARE AND RESEND PUBLISH THEM (read 25 October
# 2026): D1's queries per Worker invocation and the Workers subrequests per
# invocation on Workers Paid (developers.cloudflare.com/d1/platform/limits/,
# /workers/platform/limits/), and Resend's API requests a second per team, the
# same on every plan (resend.com/docs/api-reference/rate-limit).
# workers/follow/README.md's "The plan's limits" gives the same figures.
FOLLOW_PLAN_LIMITS = {"D1 queries per Worker invocation": 1000,
                      "Subrequests per invocation": 10000,
                      "Resend's API rate": 10}


@check("build", "the email sender's run stays under the plan limits Cloudflare and Resend publish, "
       "and no limit in the email code is one remembered")
def _follow_plan_limits():
    """The audit of 25 October 2026 (C6). The sender's run budget rested on
    figures the code called "as remembered" -- D1's queries and the
    subrequests a Worker invocation may make, Resend's rate and caps, D1 Time
    Travel's window -- with a note to check them "on the day". Read on 25
    October, one had moved: Workers Paid allows 10,000 subrequests an
    invocation, not 1,000. The published figures are now in
    workers/follow/README.md's table, with their pages and the day read
    (FOLLOW_PLAN_LIMITS holds the three a run spends), and this holds three
    things: no file of the email code or of docs/ calls a limit remembered;
    the README's table gives the figures above; and each sender's settings
    keep under them -- D1_QUERIES_PER_RUN under D1's queries, every email,
    every changes file a run reads (NIGHTS_READ and current.json) and every D1
    query under the subrequests, and SEND_GAP_MS at half of Resend's rate or
    less, so the confirmations keep the other half."""
    toml_path, js_path = Path("workers/follow/wrangler.toml"), Path("workers/follow/sender.js")
    readme = Path("workers/follow/README.md")
    if not (toml_path.is_file() and js_path.is_file() and readme.is_file()):
        return "skip", "no workers/follow here"
    remembered = []
    for top in ("workers", "functions", "docs"):
        for p in sorted(Path(top).rglob("*")):
            if p.suffix in (".js", ".md", ".toml") and p.is_file():
                text = " ".join(p.read_text(encoding="utf-8").split())
                if re.search(r"as remembered|remembered, not checked", text):
                    remembered.append(p.as_posix())
    assert not remembered, ("these call a plan's limit remembered: read Cloudflare's and Resend's "
                            "pages and give the published figure, its page and the day read: "
                            + ", ".join(remembered))
    rows = {}
    for line in _source(readme).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        for label in FOLLOW_PLAN_LIMITS:
            if len(cells) >= 3 and cells[0].startswith(label):
                n = re.match(r"([\d,]+)", cells[2])
                rows[label] = int(n.group(1).replace(",", "")) if n else None
    assert rows == FOLLOW_PLAN_LIMITS, (
        f"workers/follow/README.md's table of the plan's limits gives {rows}, and the published "
        f"figures are {FOLLOW_PLAN_LIMITS}: read the pages again and change both")
    import tomllib
    conf = tomllib.loads(_source(toml_path))
    nights = re.search(r"export const NIGHTS_READ = (\d+);", _source(js_path))
    assert nights, "sender.js no longer says NIGHTS_READ where this check reads it"
    files = int(nights.group(1)) + 1                  # the nights' files and current.json
    over = []
    for env, v in [("production", conf.get("vars", {}))] + \
            [(n, e.get("vars", {})) for n, e in conf.get("env", {}).items()]:
        try:
            send, queries, gap = (int(v[k]) for k in ("SEND_LIMIT", "D1_QUERIES_PER_RUN", "SEND_GAP_MS"))
        except (KeyError, ValueError):
            over.append(f"{env}: SEND_LIMIT, D1_QUERIES_PER_RUN or SEND_GAP_MS is not a number")
            continue
        if queries >= FOLLOW_PLAN_LIMITS["D1 queries per Worker invocation"]:
            over.append(f"{env}: D1_QUERIES_PER_RUN {queries} is not under D1's queries an invocation")
        if send + files + queries >= FOLLOW_PLAN_LIMITS["Subrequests per invocation"]:
            over.append(f"{env}: {send} emails, {files} files and {queries} queries pass the subrequests")
        if gap * FOLLOW_PLAN_LIMITS["Resend's API rate"] < 2000:
            over.append(f"{env}: SEND_GAP_MS {gap} sends faster than half of Resend's rate")
    assert not over, "; ".join(over)
    return "ok", (f"no limit remembered; the README's figures are the published ones; each sender's "
                  f"run stays under {FOLLOW_PLAN_LIMITS}")
LIVE_TDS_CASES = ("logs in with the published login", "LOGIN7, decoded field by field",
                  "many 4,096-byte packets", "two statements on one connection",
                  "encryption REQ stops the client before LOGIN7", "a refused login is `login`; 4060",
                  "the server's ERROR is `query`", "dropped halfway through a reply", "a fixed-length INT4 column",
                  "LOGINACK older than TDS 7.2", "never answers fails inside the deadline",
                  "never opens, each fail inside the deadline", "loopback is refused without ENV production",
                  "day 1 reads 11 March 2026", "day 2 reads veto day", "compare_test finds a changed ballot",
                  "compare_test finds each difference the go rests on", "compare_test's time rule",
                  "requires encryption: the file says so", "the sitting is not asked again",
                  "the run's 45 s SQL budget bounds the test",
                  "a packet size past TDS's 32,767 is not taken", "a statement on a closed connection is `query`")
# ======================================================= code: the live layer ==
# workers/live/, the Worker graniterecord-live (the person, 26 October 2026:
# the live layer approved with its defaults). Its YouTube half is built; its
# database half, the two read-only Functions and the pages come in later
# branches, each adding to these two checks rather than a check of its own.

# The live Worker's suite, and how many tests it had when this was written: a
# count that falls means a file stopped loading or a test was lost.
LIVE_TESTS = "tests/live/index.js"
# (On 30 October 2026 the retired /session/<B>/today page's eight tests went
# with it, and the morning page's came in; 216 with the committee player's,
# 218 with In short's, 220 with the reviews' of 6 November.)
LIVE_TESTS_AT_LEAST = 220


@check("build", "the live Worker's own tests pass, every one: node --test runs tests/live/index.js, "
       "which imports every test file in tests/live/")
def _live_tests():
    """workers/live/ is held by its own node suite, as the night's timer is by
    tests/night-timer.test.js: the YouTube half against a YouTube that is a
    function answering synthetic answers in the documented shape (recorded
    ones would be YouTube's data kept in git past its 30 days), and the store
    against an R2 bucket in memory with etags. It proves the cadence across
    both changes of the clock in 2027; live, upcoming, ended, unscheduled and
    cancelled streams each written as they are; a heavy week's quota under
    1,300 units and at 52 searches a weekday; every failure said in the file
    and to Healthchecks, never written as a look that found nothing; the
    lease; the sweep; and the person's switch.

    In one process through index.js, as _follow_tests learned to (a folder
    run passed on Node 22 and failed on GitHub's Node 24 under Windows), and
    every *.test.js in the folder imported there, so none passes in silence."""
    index = Path(LIVE_TESTS)
    if not index.is_file():
        return "skip", f"{LIVE_TESTS} is not here"
    imported = re.findall(r'^import\s+"\./([^"]+)";', index.read_text(encoding="utf-8"), re.M)
    files = sorted(p.name for p in index.parent.glob("*.test.js"))
    missing = [f for f in files if f not in imported]
    assert not missing, (f"{LIVE_TESTS} does not import {', '.join(missing)}, so node --test never "
                         "runs it: add an import line for each")
    assert imported and imported[0] == "no_network.js", (
        f"{LIVE_TESTS} must import no_network.js first, so that no test can reach the network")
    # What the suite imports, named here by path and held equal to its imports
    # as they stand, so that preflight --changed (check_select.py reads this
    # function's strings) runs this check when any of it changes.
    held = {"workers/live/index.js", "workers/live/clock.js", "workers/live/youtube.js",
            "workers/live/store.js", "workers/live/tds.js", "workers/live/sql.js",
            "workers/live/test_mode.js", "workers/live/live.gen.js", "workers/follow/common.js",
            "tests/live/no_network.js", "tests/live/clock.test.js", "tests/live/sql.test.js",
            "tests/live/store.test.js", "tests/live/tds.test.js", "tests/live/youtube.test.js",
            "tests/live/fake_r2.js", "tests/live/fake_youtube.js", "tests/live/fake_tds.js",
            "tests/live/world.js", "tests/live/compare_test.mjs", "tests/live/wire.test.js",
            "tests/live/schema.js", "tests/live/schema.test.js",
            "tests/live/committee.test.js",
            "tests/live/from_records.js", "workers/live/votes.js", "workers/live/merge.js",
            "tests/live/votes.test.js", "tests/live/replay.test.js", "tests/live/functions.test.js",
            "functions/api/live/_store.js", "functions/api/live/streams.js", "functions/api/live/votes/[day].js",
            "tests/live/page.test.js"}
    reached, todo = set(), [index]
    while todo:
        f = todo.pop()
        for rel in re.findall(r"""^\s*import\s+(?:[^;]*?\sfrom\s+)?["'](\.{1,2}/[^"']+)["']""",
                              f.read_text(encoding="utf-8"), re.M | re.S):
            p = Path(os.path.relpath(f.parent / rel)).as_posix()
            if p not in reached:
                reached.add(p)
                todo.append(Path(p))
    assert reached == held, (
        f"tests/live/ reaches {sorted(reached - held)} unnamed here, or no longer reaches "
        f"{sorted(held - reached)}: name each in _live_tests's `held`, so preflight --changed runs it")
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", f"node is not on PATH, so the {len(files)} test files in tests/live/ did not run"
    r = _run([node, "--test", "--test-reporter=tap", index.as_posix()],
             capture_output=True, text=True, timeout=600)
    out = (r.stdout or "") + (r.stderr or "")
    count = {k: int(v) for k, v in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$",
                                               out, re.M)}
    fails = _tap_failures(out)
    assert not fails, (
        f"tests/live/ fails {len(fails)} of {count.get('tests', '?')}: "
        + "; ".join(f"{n!r} ({s})" if s else repr(n) for n, s in fails[:6])
        + (f" (+{len(fails) - 6} more)" if len(fails) > 6 else "")
        + f". `node --test {index.as_posix()}` shows each in full")
    assert r.returncode == 0 and not count.get("fail") and not count.get("cancelled") \
        and count.get("pass", 0) >= LIVE_TESTS_AT_LEAST, (
        f"node --test {index.as_posix()} exited {r.returncode} with {count or 'no count'}, and "
        f"{LIVE_TESTS_AT_LEAST} or more must pass: " + out.strip()[-500:])
    passed = [m.replace("\\#", "#") for m in re.findall(r"^ok \d+ - (.*)$", out, re.M)]
    gone = [c for c in LIVE_TDS_CASES if not any(c in n for n in passed)]
    assert not gone, "these cases the design names no longer pass, or no longer exist: " + "; ".join(gone)
    week = re.search(r"quota by Pacific day: (.*)$", out, re.M)
    spent = [(int(u), int(s)) for u, s in re.findall(r"(\d+)u/(\d+)s", week.group(1))] if week else []
    busiest = max(spent, default=None)
    return "ok", (f"tests/live: {count['pass']} passed of {count.get('tests')}, from {len(files)} test "
                  f"files" + (f"; the busiest simulated weekday spent {busiest[0]:,} units and "
                              f"{busiest[1]} searches" if busiest else ""))


@check("build", "the report endpoint accepts only what a page can name, and stores nothing about the reader")
def _report_function():
    """functions/api/report.js is the one thing on the site that runs.

    It accepts a report only in the shape a record's own page sends -- a
    record, that record's own address, a field from the list, the reader's
    words -- sent to one of the site's own addresses at /api/report exactly,
    from the site's own origin, after the box has been open three seconds,
    with the honeypot empty. It answers 204 to all of it, so a script learns
    nothing -- except a report that passed every rule and could not be kept,
    which answers 503 when storage failed and 429 when the day was already at
    its ceiling, so the box offers the reader the email address. It
    accepts a report from every address the site builds for a member,
    including a former member's that carries no seat number. And it
    reads nothing that identifies a reader: no IP header, no cookie; the
    schema has no column that could hold one.
    """
    fn = Path("functions/api/report.js")
    if not fn.exists():
        return "skip", "no functions/api/report.js here"
    # The code, not its comments: the header comment says "no cookie" and must.
    code = _strip_js_comments(_source(fn))
    reads = re.findall(r"""headers\.get\(\s*["']([^"']+)["']""", code, re.I)
    allowed = {"origin", "content-type", "content-length"}
    assert {h.lower() for h in reads} <= allowed, \
        f"report.js reads a header it has no use for: {sorted(set(reads) - allowed)}"
    for leak in ("request.cf", "cookie", "connecting-ip", "forwarded", "user-agent", "referer"):
        assert leak not in code.lower(), f"report.js reads {leak}"
    schema = _source("reports/schema.sql").lower()
    cols = re.findall(r"^\s*(\w+)\s+(?:integer|text)", schema, re.M)
    for col in cols:
        assert not re.search(r"ip|addr|email|cookie|session|agent|name$", col), \
            f"reports/schema.sql has a column that could identify a reader: {col}"
    node = shutil.which("node")
    if not node:
        return "skip", "node is not on PATH"
    # The host cases run against the lists wrangler.toml actually deploys, so a
    # wildcard added to production's list fails here rather than in the
    # database. The literals are for a folder without the file.
    origins = {"production": "graniterecord.org www.graniterecord.org",
               "preview": "*.graniterecord.pages.dev"}
    toml = Path("wrangler.toml")
    if toml.exists():
        import tomllib
        envs = tomllib.loads(_source(toml)).get("env", {})
        for which in origins:
            origins[which] = envs[which]["vars"]["REPORT_ORIGINS"]
    root = Path(tempfile.mkdtemp())
    try:
        t = root / "t.mjs"
        t.write_text(REPORT_JS_TEST % (json.dumps(fn.resolve().as_uri()),
                                       json.dumps(origins["production"]),
                                       json.dumps(origins["preview"])), encoding="utf-8")
        r = _run([node, str(t)], capture_output=True, text=True)
        assert r.returncode == 0 and "ALL OK" in r.stdout, (r.stdout + r.stderr).strip()[-400:]
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", (f"{len(cols)} columns, none about the reader; the host and path sent to and "
                  "the origin, honeypot, dwell, shape and record-page agreement all enforced; "
                  "204, or 503 and 429 for a real report storage or a full day could not keep")


# ---- the sponsors who have left, built on a fixture --------------------------------
#
# Real rows, cut on 7 October 2026 from the files on disk (the export of 24
# September and the database dump of 8 September), for four bills of 2026:
#
#   HB 1449   LsrsOnly.txt lists eight sitting members, Rep. McGrath the prime;
#             LsrSponsors.txt lists them and Rep. Morton, who has left
#   HB 1036   LsrsOnly.txt lists four and marks none prime; LsrSponsors.txt
#             flags Rep. Vose, who has left
#   HB 171    in LsrSponsors.txt alone, a 2025 request retained into 2026:
#             Rep. Germana the prime and two others sitting, Rep. Haskins,
#             who left during the term, and Reps. Rochefort and Massimilla,
#             who left before it began -- the bill's own text names Germana,
#             Potenza, Haskins and King
#   CACR 30   in LsrSponsors.txt alone, its one sponsor Rep. Oppel, who has
#             left, and whom the status page names with no id
#
# with each bill's record in LSRs.txt and its first docket row; the fifteen
# sitting members from legislators.txt, their address columns left empty and
# their e-mail addresses made up, so that none a scraper could use is in the
# repository; the six who have left as former_members.json,
# past_members.json and db/Legislators.psv (its first eleven columns) hold
# them; and one ballot of each: the first roll call of 2026 for the four who
# left during the term (RollCallHistory.txt) and the first of 2024 for the
# two who left before it (rollcalls/RollCallHistory_2024.txt).
_SPONSORS_WHO_LEFT = {
    "LsrsOnly.txt": [
        f"26-2787|{m}|1995|2026|{r}|HB1449|H|(New Title) limiting times vaccine clinics may "
        "operate at schools, with certain exceptions."
        for m, r in (("9866", "Sponsor"), ("9940", "Sponsor"), ("10694", "Sponsor"),
                     ("10913", "Sponsor"), ("11401", "Sponsor"), ("11420", "Sponsor"),
                     ("11421", "Prime"), ("11424", "Sponsor"))] + [
        f"26-2797|{m}|2005|2026|Sponsor|HB1036|H|relative to the maximum duration of term alimony."
        for m in ("570", "9895", "9937", "10695")],
    "LsrSponsors.txt": [
        "2026|2797|2|570|0", "2026|149|7|746|0", "2026|2797|1|909|1", "2026|2787|9|9866|0",
        "2026|2797|3|9895|0", "2026|2797|6|9937|0", "2026|2787|4|9940|0", "2026|149|6|10610|0",
        "2026|149|3|10614|0", "2026|2787|7|10694|0", "2026|2797|4|10695|0", "2026|149|4|10726|0",
        "2026|149|1|10748|1", "2026|149|5|10855|0", "2026|2787|5|10913|0", "2026|2674|1|11182|1",
        "2026|2787|6|11371|0", "2026|2787|3|11401|0", "2026|2787|8|11420|0", "2026|2787|1|11421|1",
        "2026|2787|2|11424|0"],
    "RollCallHistory.txt": [
        "2026|H|1|377272|909||Yea|", "2026|H|1|409107|10855||Not Voting/Not Excused|",
        "2026|H|1|409281|11182||Yea|", "2026|H|1|409274|11371||Yea|"],
    "RollCallHistory_2024.txt": ["2024|H|1|377141|746||Yea|", "2024|H|1|409162|10614||Yea|"],
    "LSRs.txt": [
        "2026|0149|establishing a moratorium on the issuance of permits for new landfills.|H|1|0|0|"
        "0|25-0149|HB  0171|HB171||ENA|H06|H06|1/8/2025 12:00:00 AM|11||3/20/2025 12:00:00 AM|"
        "3/20/2025 12:00:00 AM|0|S38|S38|3/20/2025 12:00:00 AM|09|01/07/2026||1/7/2026 12:00:00 AM|"
        "0|03|S38|4/15/2025 9:00:00 AM|SH Room 103||||0|0|",
        "2026|2674|relating to the public utilities commissioners.Providing that the public "
        "utilities commissioners are elected.|H|3|0|0|0|26-2674|CACR0030|CACR30||ELE|H36|H36|"
        "1/7/2026 12:00:00 AM|09||3/5/2026 12:00:00 AM|3/5/2026 12:00:00 AM|0||||||||0|02|H36|"
        "2/17/2026 10:00:00 AM|GP Room 158||||0|0|",
        "2026|2787|(New Title) limiting times vaccine clinics may operate at schools, with certain "
        "exceptions.|H|1|0|0|0|26-2787|HB  1449|HB1449||EDG|H09|H09|1/7/2026 12:00:00 AM|13||"
        "3/5/2026 12:00:00 AM|5/21/2026 12:00:00 AM|0|S26|S26|3/12/2026 12:00:00 AM|11|04/16/2026||"
        "4/16/2026 12:00:00 AM|0|02|H09|4/2/2026 2:00:00 PM|SH Room 103||||0|0|",
        "2026|2797|relative to the maximum duration of term alimony.|H|1|0|0|0|26-2797|HB  1036|"
        "HB1036||DOM|H37|H37|1/7/2026 12:00:00 AM|09||3/5/2026 12:00:00 AM|3/5/2026 12:00:00 AM|0||"
        "||||||0|02|H37|2/3/2026 10:00:00 AM|GP Room 230||||0|0|"],
    "Docket.txt": [
        "2026|0149|1/6/2025 8:54:53 AM|HB171|H|  Introduced 01/08/2025 and referred to Environment "
        "and Agriculture  HJ 2  P. 8|1/21/2025 2:02:04 PM",
        "2026|2797|11/7/2025 11:38:24 AM|HB1036|H|  Introduced 01/07/2026 and referred to Children "
        "and Family Law  HJ 1  P. 3|3/24/2026 2:03:43 PM",
        "2026|2787|12/4/2025 10:49:24 AM|HB1449|H|  Introduced 01/07/2026 and referred to Health, "
        "Human Services and Elderly Affairs  HJ 1  P. 22|3/25/2026 12:14:29 PM",
        "2026|2674|12/18/2025 3:29:23 PM|CACR30|H|  Introduced 01/07/2026 and referred to Election "
        "Law  HJ 1  P. 41|3/27/2026 1:42:46 PM"],
    # legislators.txt's first nine columns: id, last, first, middle, chamber,
    # seat, county, district, party.
    "legislators.txt": [
        "11421|McGrath|Linda||H|3093|8|40|R", "11424|DeRoy|Susan|G|H|1030|9|3|R",
        "11401|DeVito|Sayra|Lynn|H|3019|8|8|R", "9940|Litchfield|Melissa|A.|H|3117|8|32|R",
        "10913|McFarlane|Donald|S|H|2093|5|18|R", "10694|Perez|Kristine||H|2071|8|16|R",
        "11420|Sabourin dit Choinière|Matt|R|H|3028|8|30|R", "9866|Terry|Paul|A|H|1012|1|7|R",
        "570|DeSimone|Debra|L|H|1001|8|18|R", "9895|Kofalt|Jim|A|H|2101|6|32|R",
        "10695|Kuttab|Katelyn|T|H|3064|8|17|R", "9937|Lynn|Bob|J.|H|2090|8|17|R",
        "10748|Germana|Nicholas|A|H|4004|3|15|D", "10726|Potenza|Kelley|L|H|3023|9|19|R",
        "10610|King|Seth||H|2081|4|4|R"],
    "Counties.txt": ["01|Belknap|Belk.", "02|Carroll|Carr.", "03|Cheshire|Ches.", "04|Coos|Coos",
                     "05|Grafton|Graf.", "06|Hillsborough|Hills.", "07|Merrimack|Merr.",
                     "08|Rockingham|Rock.", "09|Strafford|Straf.", "10|Sullivan|Sull."],
    "Committees.txt": ["H06|Environment and Agriculture|E&A",
                       "H09|Health, Human Services and Elderly Affairs|HHS&EA",
                       "H36|Election Law|ELEC LAW", "H37|Children and Family Law|CHILD&FAMI",
                       "S26|Health and Human Services|HHS", "S38|Energy and Natural Resources|ENR"],
    "SubjectCodes.txt": ["16|DOM|Domestic Relations", "18|EDG|Education - General",
                         "21|ELE|Elections", "26|ENA|Environment - Administration"],
    # db/Legislators.psv's first eleven columns: PersonID, LastName,
    # FirstName, Employeeno, MiddleName, LegislativeBody, Active, seatno,
    # countycode, District, party.
    "Legislators.psv": [
        "11371|Morton|Jonathan|409274||H|False||06|39|R", "909|Vose|Michael|377272||H|False||08|05|R",
        "11182|Oppel|Thomas|409281||H|False||05|09|D",
        "10614|Rochefort|David|409162||H|False|2019|05|01|r",
        "10855|Haskins|Linda|409107|J|H|False||08|11|D",
        "746|Massimilla|Linda|377141|A.|H|False|5002|05|01|d"],
    "former_members.json": {
        "11371": {"county": "Hillsborough", "district": "39", "name": "Morton, Jonathan",
                  "party": "Republican"},
        "909": {"county": "Rockingham", "district": "05", "name": "Vose, Michael",
                "party": "Republican"},
        "11182": {"county": "Grafton", "district": "09", "name": "Oppel, Thomas",
                  "party": "Democrat"},
        "10614": {"county": "Grafton", "district": "01", "name": "Rochefort, David",
                  "party": "Republican"},
        "10855": {"county": "Rockingham", "district": "11", "name": "Haskins, Linda",
                  "party": "Democrat"},
        "746": {"county": "Grafton", "district": "01", "name": "Massimilla, Linda",
                "party": "Democrat"}},
    "past_members.json": {"409281": "Rep. Oppel, Thomas(Graf. 09)"},
    "bill_status.json": {"2025-2026": {"CACR30": {
        "title": "relating to the public utilities commissioners. Providing that the public "
                 "utilities commissioners are elected.",
        "lsr": "2674", "body": "H",
        "sponsors": [{"name": "Thomas Oppel", "party": "D", "web_member_id": "",
                      "senate_district": "", "chamber": "", "url": "",
                      "no_member_page": True}]}}},
}


@check("build", "a sponsor who has left is on the bill from LsrSponsors.txt, once, named with "
       "the chamber they sat in, built on real rows")
def _sponsors_who_left():
    """LsrsOnly.txt lists sitting members only (dayfiles_from_db asks for
    Active), and build_data read a bill's sponsors from it and asked
    LsrSponsors.txt only for a prime LsrsOnly left unmarked; on a bill only
    LsrSponsors.txt covers, it dropped a member off the roster as unknown. So
    168 sponsorships of 2025-2026 on 157 bills, by 20 members who had left,
    were on no page: HB 1449's Rep. Morton among them. A departed prime was
    put back, but as "Vose, Michael" with no chamber, under "Chamber not on
    file" on 34 bills; and where every sponsor had left, the status page filled
    the bill by name first, so CACR 30 listed Rep. Oppel twice, once by his
    PersonID and once by the employee number past_members.json gives him.

    build_data.py, on these four bills' real rows: every LsrSponsors.txt row
    of a member who sat in the term is on its bill, once; LsrsOnly's prime
    and order stand, and a departed prime it left unmarked is the prime; a
    bill only LsrSponsors.txt covers keeps its sequence; each member who has
    left is labelled as a sitting member is, with the chamber
    db/Legislators.psv gives them; and a member whose last ballot was before
    the term is on no bill of it, as HB 171's own text names neither Rep.
    Rochefort nor Rep. Massimilla, whose request it carries."""
    here = Path(".").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gr-sponsors-left-"))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9")
    fx = _SPONSORS_WHO_LEFT
    try:
        files = _turn_files([], fx["Docket.txt"], fx["LSRs.txt"], fx["LsrsOnly.txt"],
                            fx["LsrSponsors.txt"], [], fx["RollCallHistory.txt"])
        files["legislators.txt"] = _turn_day([f"{r}||||NH||rep{r.split('|')[0]}@example.gov"
                                              for r in fx["legislators.txt"]])
        for name in ("Counties.txt", "Committees.txt", "SubjectCodes.txt"):
            files[name] = _turn_day(fx[name])
        for n, b in files.items():
            (tmp / n).write_bytes(b)
        (tmp / "records" / "rollcalls").mkdir(parents=True)
        (tmp / "records" / "rollcalls" / "RollCallHistory_2024.txt").write_bytes(
            _turn_day(fx["RollCallHistory_2024.txt"]))
        db = tmp / "db"
        db.mkdir()
        cols = ["PersonID", "LastName", "FirstName", "Employeeno", "MiddleName", "LegislativeBody",
                "Active", "seatno", "countycode", "District", "party", "Expr1", "Address",
                "address2", "city", "Zipcode", "Expr2", "EMailAddress", "GenderCode",
                "SecretaryID", "database"]
        (db / "_columns.json").write_text(json.dumps({"Legislators": cols}), encoding="utf-8")
        (db / "Legislators.psv").write_text(
            "".join(r + "|" * (len(cols) - 11) + "\r\n" for r in fx["Legislators.psv"]),
            encoding="utf-8")
        for name in ("former_members.json", "past_members.json", "bill_status.json"):
            (tmp / name).write_text(json.dumps(fx[name]), encoding="utf-8")
        shutil.copy2(here / "corrections" / "member_corrections.json",
                     _mk(tmp / "corrections" / "member_corrections.json"))
        (tmp / "verification_manifest.csv").write_text("bill,sched_date\n", encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_data.py"), "--dir", ".", "--out", "data"],
                 cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace",
                 env=env, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        assert r.returncode == 0, f"build_data on the fixture: {out[-600:]}"
        sp = json.loads((tmp / "data" / "sponsors.json").read_text(encoding="utf-8"))
        sp = sp.get("2025-2026") or {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    def seen(bill):
        return [(x["member_id"], x["chamber"], x["label"], bool(x.get("prime")))
                for x in sp.get(bill) or []]
    want = {
        "HB1449": [("11421", "H", "Rep. Linda McGrath (R - Rock 40)", True),
                   ("11424", "H", "Rep. Susan DeRoy (R - Straf 3)", False),
                   ("11401", "H", "Rep. Sayra DeVito (R - Rock 8)", False),
                   ("9940", "H", "Rep. Melissa Litchfield (R - Rock 32)", False),
                   ("10913", "H", "Rep. Donald McFarlane (R - Graf 18)", False),
                   ("11371", "H", "Rep. Jonathan Morton (R - Hills 39)", False),
                   ("10694", "H", "Rep. Kristine Perez (R - Rock 16)", False),
                   ("11420", "H", "Rep. Matt Sabourin dit Choinière (R - Rock 30)", False),
                   ("9866", "H", "Rep. Paul Terry (R - Belk 7)", False)],
        "HB1036": [("909", "H", "Rep. Michael Vose (R - Rock 5)", True),
                   ("570", "H", "Rep. Debra DeSimone (R - Rock 18)", False),
                   ("9895", "H", "Rep. Jim Kofalt (R - Hills 32)", False),
                   ("10695", "H", "Rep. Katelyn Kuttab (R - Rock 17)", False),
                   ("9937", "H", "Rep. Bob Lynn (R - Rock 17)", False)],
        # Not Reps. Rochefort (10614) and Massimilla (746): their last ballot
        # was of 2024, and HB 171's own text does not name them.
        "HB171": [("10748", "H", "Rep. Nicholas Germana (D - Ches 15)", True),
                  ("10726", "H", "Rep. Kelley Potenza (R - Straf 19)", False),
                  ("10855", "H", "Rep. Linda Haskins (D - Rock 11)", False),
                  ("10610", "H", "Rep. Seth King (R - Coos 4)", False)],
        "CACR30": [("11182", "H", "Rep. Thomas Oppel (D - Graf 9)", True)],
    }
    bad = [f"{b}: {seen(b)}, not {w}" for b, w in want.items() if seen(b) != w]
    assert not bad, "the sponsors of the fixture's bills are not the record's:\n  " + \
        "\n  ".join(bad)
    return "ok", ("HB 1449 keeps Rep. Morton beside LsrsOnly's eight, HB 1036's prime is "
                  "Rep. Vose, HB 171 keeps Rep. Haskins, who left during the term, in sequence "
                  "and not the two who left before it, and CACR 30 lists Rep. Oppel once; each "
                  "who has left labelled as a sitting member is, with the chamber "
                  "db/Legislators.psv gives them")


# The General Court's own rows for five members (16 November 2026): db/Legislators.psv's first
# eleven columns, past_members.json's labels in the file's order (each person once for each
# chamber, the House label after the Senate one), and the status page's entries for HB 123 of
# 2025, whose sponsors only that page gives. And one made-up member, Pat Adams, once of Belknap 3
# and now the senator for District 7, whom HB 123's page lists without a chamber: Rep. Rochefort's
# case with two different numbers, which no real row of the term has (his are 1 and 1).
_SITTING_SEATS = {
    "LsrsOnly.txt": [
        f"26-2787|{m}|1995|2026|{r}|HB1449|{ch}|(New Title) limiting times vaccine clinics may "
        "operate at schools, with certain exceptions."
        for m, r, ch in (("11421", "Prime", "H"), ("11460", "Sponsor", "S"), ("9866", "Sponsor", "H"))],
    "LsrSponsors.txt": ["2026|2787|1|11421|1", "2026|2787|2|11460|0", "2026|2787|3|9866|0"],
    "Docket.txt": [
        "2025|0100|1/6/2025 8:33:35 AM|HB123|H|  Introduced 01/08/2025 and referred to Municipal "
        "and County Government  HJ 2  P. 6|1/21/2025 1:53:38 PM"],
    "legislators.txt": [
        "11421|McGrath|Linda||H|3093|8|40|R", "11460|McGough|Tim||S||6|11|R",
        "9866|Terry|Paul|A|H|1012|1|7|R", "10604|Pearl|Howard||S||7|17|r",
        "11458|Rochefort|David||S||5|1|R", "11999|Adams|Pat||S||1|7|R"],
    "Legislators.psv": [
        "11460|McGough|Tim|218764||S|True||06|11|R", "5686|McGough|Tim|376150||H|False|1015|06|12|r",
        "10604|Pearl|Howard|218759||S|True||07|17|r", "8383|Pearl|Howard|408383|C.|H|False||07|26|R",
        "11458|Rochefort|David|218762||S|True||05|01|R",
        "10614|Rochefort|David|409162||H|False|2019|05|01|r",
        "11421|McGrath|Linda|409266||H|True|3093|08|40|R", "9866|Terry|Paul|409053|A|H|True|1012|01|07|R",
        "11999|Adams|Pat|219999||S|True||01|07|R", "11998|Adams|Pat|419999||H|False||01|03|R"],
    "former_members.json": {"5686": {"county": "Hillsborough", "district": "12", "name": "McGough, Tim",
                                     "party": "Republican"}},
    "past_members.json": {
        "218759": "Sen. Pearl, Howard(Dist. 17)", "218762": "Sen. Rochefort, David(Dist. 01)",
        "218764": "Sen. McGough, Tim(Dist. 11)", "219999": "Sen. Adams, Pat(Dist. 07)",
        "376150": "Rep. McGough, Tim(Hills 12)", "408383": "Rep. Pearl, Howard(Merr. 26)",
        "409053": "Rep. Terry, Paul(Belk. 07)", "409162": "Rep. Rochefort, David(Graf. 01)",
        "409266": "Rep. McGrath, Linda(Rock. 40)", "419999": "Rep. Adams, Pat(Belk. 03)"},
    "bill_status.json": {"2025-2026": {"HB123": {
        "title": "(Second New Title) defining pre-sequestration timber tax revenue, establishing a "
                 "moratorium on carbon sequestration and establishing a commission to study the "
                 "effects of carbon sequestration in New Hampshire forests upon state and local tax "
                 "revenue, effective forest management, and the health of New Hampshire's logging "
                 "industry.", "lsr": "100", "body": "H",
        "sponsors": [{"name": "Howard Pearl", "party": "R", "web_member_id": "",
                      "senate_district": "17", "chamber": "S",
                      "url": "http://www.gencourt.state.nh.us/senate/members/webpages/district17.aspx"},
                     {"name": "David Rochefort", "party": "R", "web_member_id": "",
                      "senate_district": "", "chamber": "", "url": "", "no_member_page": True},
                     {"name": "Pat Adams", "party": "R", "web_member_id": "",
                      "senate_district": "", "chamber": "", "url": "", "no_member_page": True}]}}},
}


@check("build", "a sitting member's sponsor row carries the seat the term's roster gives them, "
       "not a seat of another term the General Court's list gives the same name, built on real rows")
def _sitting_sponsors_take_the_roster_seat():
    """build_data gave every sponsor row without a district the seat of whichever record in
    `former` shares its first and last name, and `former` holds everyone who has served:
    past_members.json names each person once for each chamber, with that chamber's seat. So
    the row of a senator who had sat in the House took the House seat -- 2,471 rows of fifteen
    senators on 1,049 bills of 2025-2026, Sen. Tim McGough's "Hills 12" (PersonID 5686, his
    House record, inactive) beside the label "Sen. Tim McGough (R - SD11)" the roster gave the
    same row. The labels were right; the county and district each bill's record and
    /data/bills-<term>.jsonl.gz carry were not.

    build_data.py, on these members' real rows: Sen. McGough on HB 1449, read from LsrsOnly.txt
    by his PersonID, sits for District 11; Sen. Pearl on HB 123, whom only the bill status page
    lists, by name in the Senate, for District 17, not his old Merrimack 26; Rep. Terry and Rep.
    McGrath keep the seats they have; and Rep. Rochefort, whom HB 123's page lists without a
    chamber (a representative, build_data reads it) and who sits in the Senate now, keeps
    Grafton 1, the House seat the General Court's list gives him: a member a bill names in the
    chamber they sat in before takes no seat from the chamber they sit in now. His numbers are
    the same in both chambers, so the made-up Pat Adams holds that rule: Belknap 3, not 7."""
    here = Path(".").resolve()
    tmp = Path(tempfile.mkdtemp(prefix="gr-sitting-seats-"))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
               HTTP_PROXY="http://127.0.0.1:9", HTTPS_PROXY="http://127.0.0.1:9")
    fx, base = _SITTING_SEATS, _SPONSORS_WHO_LEFT
    try:
        files = _turn_files([], [r for r in base["Docket.txt"] if "|HB1449|" in r] + fx["Docket.txt"],
                            [r for r in base["LSRs.txt"] if "|HB1449|" in r], fx["LsrsOnly.txt"],
                            fx["LsrSponsors.txt"], [], [])
        files["legislators.txt"] = _turn_day([f"{r}||||NH||rep{r.split('|')[0]}@example.gov"
                                              for r in fx["legislators.txt"]])
        for name in ("Counties.txt", "Committees.txt", "SubjectCodes.txt"):
            files[name] = _turn_day(base[name])
        for n, b in files.items():
            (tmp / n).write_bytes(b)
        db = tmp / "db"
        db.mkdir()
        cols = ["PersonID", "LastName", "FirstName", "Employeeno", "MiddleName", "LegislativeBody",
                "Active", "seatno", "countycode", "District", "party", "Expr1", "Address",
                "address2", "city", "Zipcode", "Expr2", "EMailAddress", "GenderCode",
                "SecretaryID", "database"]
        (db / "_columns.json").write_text(json.dumps({"Legislators": cols}), encoding="utf-8")
        (db / "Legislators.psv").write_text(
            "".join(r + "|" * (len(cols) - 11) + "\r\n" for r in fx["Legislators.psv"]),
            encoding="utf-8")
        for name in ("former_members.json", "past_members.json", "bill_status.json"):
            (tmp / name).write_text(json.dumps(fx[name]), encoding="utf-8")
        shutil.copy2(here / "corrections" / "member_corrections.json",
                     _mk(tmp / "corrections" / "member_corrections.json"))
        (tmp / "verification_manifest.csv").write_text("bill,sched_date\n", encoding="utf-8")
        r = _run([sys.executable, _paths.script("build_data.py"), "--dir", ".", "--out", "data"],
                 cwd=tmp, capture_output=True, text=True, encoding="utf-8", errors="replace",
                 env=env, timeout=300)
        out = (r.stdout or "") + (r.stderr or "")
        assert r.returncode == 0, f"build_data on the fixture: {out[-600:]}"
        sp = json.loads((tmp / "data" / "sponsors.json").read_text(encoding="utf-8"))
        sp = sp.get("2025-2026") or {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    def seat(bill, who):
        got = [(x.get("chamber"), x.get("county"), x.get("district"), x.get("label"))
               for x in sp.get(bill) or [] if who in (x.get("member_id"), x.get("name"))]
        return got[0] if len(got) == 1 else got
    want = {("HB1449", "11460"): ("S", "Hills", "11", "Sen. Tim McGough (R - SD11)"),
            ("HB1449", "11421"): ("H", "Rock", "40", "Rep. Linda McGrath (R - Rock 40)"),
            ("HB1449", "9866"): ("H", "Belk", "07", "Rep. Paul Terry (R - Belk 7)"),
            ("HB123", "Howard Pearl"): ("S", "Merr", "17", "Howard Pearl (R)"),
            ("HB123", "David Rochefort"): ("H", "Graf", "01", "David Rochefort (R)"),
            ("HB123", "Pat Adams"): ("H", "Belk", "03", "Pat Adams (R)")}
    bad = [f"{b} {who}: {seat(b, who)}, not {w}" for (b, who), w in want.items() if seat(b, who) != w]
    assert not bad, ("a sponsor row's seat is not the one the record gives the member in that "
                     "chamber that term:\n  " + "\n  ".join(bad))
    return "ok", ("Sen. McGough on HB 1449 sits for District 11, not the Hills 12 of his House "
                  "record, and Sen. Pearl on HB 123's status-page list for District 17, not "
                  "Merrimack 26; Reps. McGrath and Terry keep their seats, and Rep. Rochefort, "
                  "a senator now, keeps Grafton 1 on the bill that names him a representative "
                  "(and the made-up Rep. Adams Belknap 3, not his Senate 7)")


@check("build", "a chapter is read in every form the clerks wrote it, and a clash is withheld")
def _chapters():
    """extract_chapters.py on a docket written to exercise each rule it
    states: the five spellings from 1989 to 2026; a section ("Chapter 23:1")
    and a "see" are not chapters; the date is the signature's, not the first
    on the line (SB 39 of 2009's "Sec 3 eff 12/31/10 ... Chapter 0014" is not
    2010's chapter 14); two bills with one number in one year are both
    withheld; a special session and a January signature number on their
    own; and a row under another bill's LSR is not read."""
    here = Path(".").resolve()
    if not _paths.locate("extract_chapters.py").exists():
        return "skip", "extract_chapters.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "db").mkdir()
        (root / "data").mkdir()
        rows = [
            ("1989", "0010", "HB  0010", "05/08/1989 10:00:00", "HB10",
             "SIGNED BY GOVERNOR  5/8/89   EFF:  7/7/89     CHAP: 112"),
            ("1989", "0011", "HB  0011", "06/09/1989 10:00:00", "HB11",
             "SIGNED BY GOVERNOR  06/09/89 EFF: 01/01/90 CHAP.0179"),
            ("2001", "0100", "SB  0100", "06/29/2001 10:00:00", "SB100",
             "Signed by the Governor on   6/29/2001   Eff-  6/29/2001   Chap-  0149"),
            ("2001", "0101", "SB  0101", "06/29/2001 10:00:00", "SB101",
             "Chapter 23:1 Committee Members Appointed by President: Senators"),
            ("2001", "0102", "HB  0102", "05/01/2001 10:00:00", "HB102",
             "Signed by the Governor on 5/1/2001 Eff: 7/1/2001 Chap:  0069"),
            ("2001", "0102", "HB  0102", "05/01/2001 10:00:00", "HB102",
             "  *Multiple Effective Dates, See Chapter 240 for additional dates"),
            ("2009", "0039", "SB  0039", "04/21/2009 10:00:00", "SB39",
             "Signed by the Governor on 4/17/09; Sections 1 and 4 Eff. 06/17/09;"),
            ("2009", "0039", "SB  0039", "04/21/2009 10:00:00", "SB39",
             "Sec 3 eff 12/31/10, Remainder eff. 04/17/09; Chapter 0014"),
            ("2010", "2001", "HB  0546", "05/10/2010 10:00:00", "HB546",
             "Signed By the Governor 05/07/2010; Chapter 0014"),
            ("2009", "0028", "SB  0028", "05/15/2009 10:00:00", "SB28",
             "Signed by the Governor on 05/15/09; Chapter 0028"),
            ("2009", "0109", "SB  0109", "05/08/2009 10:00:00", "SB109",
             "Signed by the Governor on 05/08/09; Chapter 0028"),
            ("2010", "3001", "SSHB 0001", "06/10/2010 10:00:00", "SSHB1",
             "Signed by the Governor 06/10/2010; Chapter 0001"),
            ("2010", "2002", "SB  0300", "01/14/2010 10:00:00", "SB300",
             "Signed by the Governor on 1/14/10; Chapter 0001"),
            ("2010", "9999", "HB  1400", "06/01/2010 10:00:00", "HB1400",
             "Signed by the Governor on 6/1/10; Chapter 0200"),
            ("2011", "0012", "SB  0012", "07/13/2011 10:00:00", "SB12",
             "Signed by the Governor on 07/13/11; Chapter 0241I. Section 2 "
             "Effective 12/31/13I"),
            ("1997", "0149", "HB  0149", "06/25/1997 10:00:00", "HB149",
             "OVERRIDE GOV VETO, ML RC(17-299); HJ79,P2183-2186"),
        ]
        (root / "db" / "Docket.psv").write_text(
            "".join("|".join([y, l, e, d, b, "H", t, "x", "1", d, "1"]) + "\n"
                    for y, l, e, d, b, t in rows), encoding="utf-8")
        term = lambda y: f"{y}-{int(y) + 1}"
        bills = {}
        for y, l, e, d, b, t in rows:
            bills.setdefault(term(str(int(y) - (1 - int(y) % 2))), {})[b] = {
                "bill": b, "lsr_num": l}
        bills["2009-2010"]["HB1400"]["lsr_num"] = "2003"
        (root / "data" / "bills.json").write_text(json.dumps(bills),
                                                  encoding="utf-8")
        r = _run([sys.executable, _paths.script("extract_chapters.py")],
                 cwd=root, capture_output=True, text=True, timeout=60,
                 env={**os.environ, "PYTHONPATH": str(here)})
        assert r.returncode == 0, (r.stdout + r.stderr).strip()[-300:]
        got = json.loads((root / "chapters.json").read_text(encoding="utf-8"))

        def ch(t, b):
            return (got.get(t, {}).get(b) or {}).get("chapter")
        want = {("1989-1990", "HB10"): 112, ("1989-1990", "HB11"): 179,
                ("2001-2002", "SB100"): 149, ("2001-2002", "SB101"): None,
                ("2001-2002", "HB102"): 69, ("2009-2010", "SB39"): 14,
                ("2009-2010", "HB546"): 14, ("2009-2010", "SB28"): None,
                ("2009-2010", "SB109"): None, ("2009-2010", "SSHB1"): 1,
                ("2009-2010", "SB300"): 1, ("2009-2010", "HB1400"): None,
                ("2011-2012", "SB12"): 241}
        wrong = [f"{b} of {t}: {ch(t, b)}, not {n}"
                 for (t, b), n in want.items() if ch(t, b) != n]
        assert not wrong, "; ".join(wrong)
        assert got["2009-2010"]["SB28"].get("withheld"), \
            "a clash is left blank without saying why"
        assert got["2009-2010"]["SSHB1"].get("special"), \
            "a special session's chapter is not marked as one"
        assert (got.get("1997-1998", {}).get("HB149") or {}).get(
            "override_failed"), "a failed override (\"ML\") was not kept"
        return "ok", "five spellings, sections and see-alsos refused, clashes withheld"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "the database's chapter numbers check the docket's: a confirmed correction applies, a disagreement is withheld, a signed bill's missing number is filled")
def _chapters_database():
    """extract_chapters.py against a PastLegislation dump written for it: 1991
    HB 329's docket "CHAP.01313" gives way to the person-confirmed 131 and keeps
    the docket's number beside it; a disagreement nobody has confirmed is
    withheld with both numbers named; a bill whose docket records the signature
    and no number takes the database's; a number both agree on stands; and the
    join is the stored LSR, so a bill of the same number under another LSR
    takes nothing."""
    here = Path(".").resolve()
    if not _paths.locate("extract_chapters.py").exists():
        return "skip", "extract_chapters.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        for d in ("db", "data", "db/past"):
            (root / d).mkdir(parents=True, exist_ok=True)
        rows = [
            ("1991", "0665", "HB  0329", "05/20/1991 10:00:00", "HB329",
             "SIGNED BY GOVERNOR 05/20/91  EFF: 05/20/91 CHAP.01313"),
            ("1995", "0010", "HB  0005", "05/01/1995 10:00:00", "HB5",
             "SIGNED BY GOVERNOR 05/01/95 EFF: 07/01/95 CHAP.0100"),
            ("1995", "0011", "HB  0006", "05/02/1995 10:00:00", "HB6",
             "SIGNED BY GOVERNOR 05/02/95 EFF: 07/01/95"),
            ("1995", "0012", "HB  0007", "05/03/1995 10:00:00", "HB7",
             "SIGNED BY GOVERNOR 05/03/95 EFF: 07/01/95 CHAP.0102"),
            ("1996", "0013", "HB  0008", "05/04/1996 10:00:00", "HB8",
             "SIGNED BY GOVERNOR 05/04/96 EFF: 07/01/96"),
        ]
        (root / "db" / "Docket.psv").write_text(
            "".join("|".join([y, l, e, d, b, "H", t, "x", "1", d, "1"]) + "\n"
                    for y, l, e, d, b, t in rows), encoding="utf-8")
        bills = {"1991-1992": {"HB329": {"bill": "HB329", "lsr_year": "1991", "lsr_num": "0665"}},
                 "1995-1996": {"HB5": {"bill": "HB5", "lsr_year": "1995", "lsr_num": "0010"},
                               "HB6": {"bill": "HB6", "lsr_year": "1995", "lsr_num": "0011"},
                               "HB7": {"bill": "HB7", "lsr_year": "1995", "lsr_num": "0012"},
                               "HB8": {"bill": "HB8", "lsr_year": "1996", "lsr_num": "0013"}}}
        (root / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
        cols = ["SessionYear", "LSR", "ChapterNo"]
        (root / "db" / "past" / "_manifest.json").write_text(
            json.dumps({"PastLegislation": {"columns": cols}}), encoding="utf-8")
        past = [("1991", "665", "0131"), ("1995", "10", "0101"), ("1995", "11", "0050"),
                ("1995", "12", "0102"), ("1995", "13", "0077")]
        (root / "db" / "past" / "PastLegislation.psv").write_text(
            "".join("|".join(r) + "\n" for r in past), encoding="utf-8")
        r = _run([sys.executable, _paths.script("extract_chapters.py")],
                 cwd=root, capture_output=True, text=True, timeout=60,
                 env={**os.environ, "PYTHONPATH": str(here)})
        assert r.returncode == 0, (r.stdout + r.stderr).strip()[-400:]
        got = json.loads((root / "chapters.json").read_text(encoding="utf-8"))
        hb329 = got["1991-1992"]["HB329"]
        assert hb329.get("chapter") == 131 and hb329.get("docket") == 1313 \
            and hb329.get("corrected"), f"the confirmed correction did not apply: {hb329}"
        hb5 = got["1995-1996"]["HB5"]
        assert hb5.get("chapter") is None and "100" in hb5.get("withheld", "") \
            and "101" in hb5.get("withheld", ""), f"a disagreement was not withheld: {hb5}"
        assert got["1995-1996"]["HB6"].get("chapter") == 50, \
            f"a signed bill with no docket number was not filled: {got['1995-1996'].get('HB6')}"
        assert got["1995-1996"]["HB7"].get("chapter") == 102, "an agreed number did not stand"
        assert (got["1995-1996"].get("HB8") or {}).get("chapter") is None, \
            "a bill took a number through an LSR of another year"
        return "ok", "confirmed 131 over the docket's 1313, a disagreement withheld, a signed bill filled, the join by stored LSR"
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("build", "a chapter the clerk spelled CH., Chap, Chapt: or Chp. is read on the law line and nowhere else")
def _chapters_rare():
    """Five laws had no chapter on the site because the docket spells it in a
    form extract_chapters did not read: 1993 HB 241 "CH.0066", 1999 HB 426
    "Chap, 0070", 2004 SB 335 "Chapt:0099", SB 438 "Chapt:0066" and SB 481
    "Chp. 0258". The same forms name OTHER laws on other lines -- a study
    committee's "for (Ch. 47)", "{LSR 0155, HB 154, CH. 183, ...}" -- and read
    everywhere they would have cost eight laws the chapter they have and given
    two bills another law's number. So they are read on a law line that
    names no other bill, and each of those refusals is exercised here, on the
    real lines."""
    here = Path(".").resolve()
    if not _paths.locate("extract_chapters.py").exists():
        return "skip", "extract_chapters.py not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "db").mkdir()
        (root / "data").mkdir()
        rows = [
            ("1993", "0435", "HB  0241", "04/20/1993 10:00:00", "HB241",
             "BECAME LAW WITHOUT SIGNATURE 04/20/93  EFF DATE:06/19/93 CH.0066"),
            ("1999", "0561", "HB  0426", "05/28/1999 10:00:00", "HB426",
             "Signed by the Governor on  5/28/1999   Eff:  7/27/1999  Chap, 0070"),
            ("2004", "3033", "SB  0335", "05/12/2004 10:00:00", "SB335",
             "Law Without Signature  05/12/04  Eff. 01/01/05, Chapt:0099 "
             "[ Art 44, Pt II, NH Constitution]"),
            ("2004", "3198", "SB  0481", "06/16/2004 10:00:00", "SB481",
             "Law Without Signature, Article 44, Part II N.H. Constitution "
             "06/16/04, Eff. 08/15/04: Chp. 0258"),
            # A study committee's membership line names the law that made it,
            # which is not this bill's: its own number stays its own.
            ("2000", "2570", "HB  1462", "05/10/2000 10:00:00", "HB1462",
             "Signed by the Governor on 5/10/2000 Eff: 7/9/2000 Chap: 0061"),
            ("2000", "2570", "HB  1462", "06/01/2000 10:00:00", "HB1462",
             "Study Committee Members: Senators Russman, Below, F. King, "
             "Fraser, Cohen, for (Ch. 47)"),
            # A law line about ANOTHER bill, on a bill that never became law.
            ("1996", "2331", "HB  1179", "06/18/1997 10:00:00", "HB1179",
             "{LSR 0155, HB 154, CH. 183, 1997  SIGNED BY GOV 6/18/97}"),
            # And a cross-reference with no law in it at all.
            ("1989", "9100", "HB  0001", "05/08/1989 10:00:00", "HB1",
             "SIGNED BY GOVERNOR  5/8/89   EFF:  7/7/89     CHAP: 001"),
            ("1989", "9100", "HB  0001", "05/08/1989 10:00:00", "HB1",
             "CH.124,1989//"),
        ]
        (root / "db" / "Docket.psv").write_text(
            "".join("|".join([y, l, e, d, b, "H", t, "x", "1", d, "1"]) + "\n"
                    for y, l, e, d, b, t in rows), encoding="utf-8")
        bills = {}
        for y, l, e, d, b, t in rows:
            yy = int(y) - (1 - int(y) % 2)
            bills.setdefault(f"{yy}-{yy + 1}", {})[b] = {"bill": b, "lsr_num": l}
        (root / "data" / "bills.json").write_text(json.dumps(bills), encoding="utf-8")
        r = _run([sys.executable, _paths.script("extract_chapters.py")],
                 cwd=root, capture_output=True, text=True, timeout=60,
                 env={**os.environ, "PYTHONPATH": str(here)})
        assert r.returncode == 0, (r.stdout + r.stderr).strip()[-300:]
        got = json.loads((root / "chapters.json").read_text(encoding="utf-8"))
        want = {("1993-1994", "HB241"): 66, ("1999-2000", "HB426"): 70,
                ("2003-2004", "SB335"): 99, ("2003-2004", "SB481"): 258,
                ("1999-2000", "HB1462"): 61, ("1995-1996", "HB1179"): None,
                ("1989-1990", "HB1"): 1}
        ch = lambda t, b: (got.get(t, {}).get(b) or {}).get("chapter")
        wrong = [f"{b} of {t}: {ch(t, b)}, not {n}" for (t, b), n in want.items()
                 if ch(t, b) != n]
        assert not wrong, "; ".join(wrong)
        return "ok", ("CH., Chap, Chapt: and Chp. read on a law line; a committee's "
                      "\"for (Ch. 47)\", another bill's law line and a bare cross-reference are not")
    finally:
        shutil.rmtree(root, ignore_errors=True)

# The person's file with the deadline in it and nothing settled: what the
# rule does alone, past the deadline.
_ELECT_DEADLINE_ONLY = {"2026-11-03": {"recount_deadline": _ELECT_DEADLINE}}


@check("build", "members-elect: a winner is linked to a page only on a certain match -- the "
                "seat's sitting member, or the one former member of that name and county -- and "
                "a name the rule cannot settle only once the person's file says who it is")
def _elect_links():
    """The person's rule (16 October 2026): a link only on a certain match,
    because a stranger's record under a member-elect's name is worse than a
    missing link. On the fixture's election: Jodi Nelson and Debra
    Altschiller, re-elected to their own seats, link to their own pages;
    Michael Vose, the one former member of his name, of Rockingham, links to
    his; John Smith, two former members of Rockingham, is drawn unlinked and
    named to the person, and links to the one the person's file names; and
    the new people -- a write-in among them -- are drawn unlinked. Every link
    is to the record of the id it names, and a winner with no link carries
    neither id nor page."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-elect-links-"))
    try:
        site = _elect_fixture(root)
        sitting = {str(m["id"]): m for m in json.loads((site / "legislators.json").read_text(
            encoding="utf-8"))}
        former = {str(m["id"]): m for m in json.loads((site / "former.json").read_text(
            encoding="utf-8"))}
        nelson = next(m for m in sitting.values() if m["name"].startswith("Nelson,"))
        senator = next(m for m in sitting.values() if m["name"].startswith("Altschiller,"))
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_DEADLINE_ONLY)
        assert code == 0 and doc, f"the step wrote no file on {_ELECT_IN}: {out[-300:]}"

        def drawn(d, key, name):
            hit = [e for e in d["races"][key]["elected"] if e["n"] == name]
            assert len(hit) == 1, f"{name} is not drawn once in {key}: {d['races'][key]}"
            return hit[0]
        want = {("H|Rockingham|13", "Jodi Nelson"): ("sitting", nelson["id"], nelson["slug"]),
                ("S|24", "Debra Altschiller"): ("sitting", senator["id"], senator["slug"]),
                ("H|Rockingham|6", "Michael Vose"): ("former", "900001", "michael-vose-rock-5"),
                ("H|Rockingham|13", "John Smith"): ("new", None, None),
                ("H|Rockingham|32", "Pat Newell"): ("new", None, None),
                ("H|Rockingham|7", "Sam Wright"): ("new", None, None)}
        bad = []
        for (key, name), w in want.items():
            e = drawn(doc, key, name)
            if (e["k"], e.get("id"), e.get("s")) != w:
                bad.append(f"{name} in {key} is {(e['k'], e.get('id'), e.get('s'))}, not {w}")
        for d in (doc,):
            for key, r in d["races"].items():
                for e in r["elected"]:
                    own = {"sitting": sitting, "former": former}.get(e["k"], {}).get(e.get("id"))
                    if e["k"] == "new" and ("id" in e or "s" in e):
                        bad.append(f"{e['n']} in {key} is new and carries a link: {e}")
                    elif e["k"] != "new" and (not own or own["slug"] != e.get("s")):
                        bad.append(f"{e['n']} in {key} links to {e.get('s')}, which is not the "
                                   f"page of {e['k']} member {e.get('id')}")
        assert not bad, "; ".join(bad)
        unlinked, new = _elect_part(out, "NOT LINKED"), _elect_part(out, "NEW --")
        assert "John Smith: 2 former members of that name" in unlinked, (
            "the name the rule cannot settle is not put to the person: " + out[-400:])
        assert "Pat Newell" in new and "Sam Wright" in new and "Jodi Nelson" not in out, (
            "the new people are not listed for the person, or a linked one is: " + out[-400:])
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_HAND)
        assert code == 0 and doc, f"the step with the person's file wrote nothing: {out[-300:]}"
        e = drawn(doc, "H|Rockingham|13", "John Smith")
        assert (e["k"], e.get("id"), e.get("s")) == ("former", "900002", "john-smith-rock-3"), (
            f"John Smith, whom the person's file names 900002, is drawn as {e}")
        assert "John Smith" not in _elect_part(out, "NOT LINKED") and \
            "Pat Newell" not in _elect_part(out, "NEW --"), (
            "a name the person's file settles is still put to the person: " + out[-400:])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("Nelson and Altschiller to their own pages, Vose to his as the one former "
                  "member of his name and county; John Smith unlinked and named to the person "
                  "until the person's file names 900002; the new people unlinked")


@check("build", "members-elect: written only after the election and before Organization Day while "
                "the site's newest term is the one before theirs; otherwise none, and the last "
                "build's removed and the reason said")
def _elect_retires():
    """The person's decisions of 16 October 2026: members-elect retire by
    themselves on Organization Day, 2 December 2026, or as soon as the site's
    newest term is theirs, whichever is first, and a build before the
    election shows none. The fixture's election, its step dated 20 November,
    writes the file; dated 2 December, on the election day itself and in
    October it writes none, removes one an earlier build left and says why;
    so it does once site/meta.json's newest term is 2027-2028; and so with no
    results file at all. None of these is a failure of the build. A results
    file that will not read is: it stops the step, having removed the last
    build's file."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-elect-days-"))
    try:
        site = _elect_fixture(root)
        stale = site / "members_elect.json"
        code, out, doc = _elect_run(root, _ELECT_IN)
        assert code == 0 and doc and doc["takes_office"] == "2026-12-02" and \
            doc["election"] == "2026-11-03" and doc["term"] == "2027-2028", (
            f"dated {_ELECT_IN} the step wrote {doc and {k: doc[k] for k in doc if k != 'races'}}: "
            + out[-300:])
        old = stale.read_bytes()
        bad = []

        def gone(day, why, label):
            stale.write_bytes(old)
            code, out, doc = _elect_run(root, day)
            if code != 0 or doc is not None or why not in out or "Removed" not in out:
                bad.append(f"{label}: exit {code}, {'a file left' if doc else 'no file'}, said "
                           f"{out.strip()[-160:]!r}")
        gone("2026-12-02", "on or after Organization Day", "dated 2 December")
        gone("2027-01-06", "on or after Organization Day", "dated January")
        gone("2026-11-03", "is not after the election", "dated the election day")
        gone("2026-10-16", "is not after the election", "dated October")
        meta_p = site / "meta.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        meta_p.write_text(json.dumps(dict(meta, terms=["2027-2028"] + meta["terms"])),
                          encoding="utf-8")
        gone(_ELECT_IN, "the term is theirs now", "with terms[0] at 2027-2028")
        meta_p.write_text(json.dumps(meta), encoding="utf-8")
        results = root / "collected" / "election_2026.json"
        kept = results.read_bytes()
        results.unlink()
        gone(_ELECT_IN, "no election results", "with no results file")
        results.write_text("{not json", encoding="utf-8")
        stale.write_bytes(old)
        code, out, doc, err = _elect_run(root, _ELECT_IN, err=True)
        last = (err.strip().splitlines() or [""])[-1]
        if code == 0 or doc is not None or not last.startswith("REFUSED"):
            bad.append(f"a results file that will not read: exit {code}, "
                       f"{'a file left' if doc else 'no file'}, its last line on stderr {last!r}")
        results.write_bytes(kept)
        assert not bad, "; ".join(bad)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("written on 20 November; none, the last build's removed and why said, on 2 "
                  "December, in January, on the election day, in October, with 2027-2028 the "
                  "newest term and with no results; a results file that will not read stops it")


@check("build", "members-elect: the step leaves every other file of the site byte for byte as it "
                "was -- legislators.json and former.json among them -- and never writes the "
                "person's file")
def _elect_never_the_roster():
    """A member-elect never enters the roster (the person, 16 October 2026): a
    dozen builders read site/legislators.json as who sits now and the night's
    census gates count it, and former.json is kept apart for the same reason.
    So every file of the fixture's built site is the same, byte for byte,
    before the step and after it, but the one it adds, site/members_elect.json;
    and the person's corrections/members_elect.json is the same too, which the
    step reads. preflight's hand-made-files guard reads the step's source, as
    a build_ script, for any write into corrections/."""
    import hashlib
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    scanned = {f.name for f in _paths.code_files("build_*.py")}
    assert "build_members_elect.py" in scanned, (
        "build_members_elect.py is not among the build_ scripts the hand-made-files guard reads")
    root = Path(tempfile.mkdtemp(prefix="gr-elect-roster-"))
    try:
        site = _elect_fixture(root)
        hand = root / "corrections" / "members_elect.json"

        def sums():
            files = [f for f in site.rglob("*") if f.is_file()] + [hand]
            return {f.relative_to(root).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
                    for f in files if f.exists()}
        _elect_run(root, "2026-10-16", hand=_ELECT_HAND)
        before = sums()
        assert "site/legislators.json" in before and "site/former.json" in before, (
            "the fixture has no roster to hold")
        code, out, doc = _elect_run(root, _ELECT_IN)
        after = sums()
        assert code == 0 and doc, f"the step wrote nothing on {_ELECT_IN}: {out[-300:]}"
        changed = sorted(k for k in before if after.get(k) != before[k])
        added = sorted(set(after) - set(before))
        assert not changed and added == ["site/members_elect.json"], (
            f"the step changed {changed} and added {added}; it may add site/members_elect.json "
            "and nothing else")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", (f"{len(before):,} files of the fixture's site, legislators.json and former.json "
                  "among them, and the person's file, the same byte for byte after the step; "
                  "members_elect.json the one file added")


@check("build", "members-elect: in every race the elected, the not final and the held add up to "
                "its seats, every race on file is there, and what does not add up is printed for "
                "the person")
def _elect_adds_up():
    """Check 4 of the plan: each race's elected, not final and held are its
    seats. On the fixture's election with the person's file: Senate 23's tie
    is one seat not final; Danville's race, marked not final with a recount
    asked for, is one seat not final and says so; Fremont's write-in winner,
    held, is one held seat; and every other race's winners fill it. Every
    district on file is a race in the file. No reason the person gave is in
    it. And a race the results lose is still there, its seats with no
    member-elect on file, and printed under DO NOT ADD UP."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-elect-seats-"))
    try:
        site = _elect_fixture(root)
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_HAND)
        assert code == 0 and doc, f"the step wrote nothing: {out[-300:]}"
        races = doc["races"]
        districts = json.loads((site / "districts.json").read_text(encoding="utf-8"))
        on_file = {f"H|{h['county']}|{h['district']}" for w in districts.values()
                   for d in w.values() for h in d["house"]} | {
            f"S|{d['senate']}" for w in districts.values() for d in w.values()}
        assert set(races) == on_file, (
            f"the file's races are {sorted(races)}, the district table's {sorted(on_file)}")
        bad = [f"{k}: {len(r['elected'])} + {r['not_final']} + {r['held']} != {r['seats']}"
               for k, r in races.items()
               if len(r["elected"]) + r["not_final"] + r["held"] != r["seats"]]
        assert not bad, "races that do not add up to their seats: " + "; ".join(bad)
        want = {"S|23": (0, 1, 0, None), "H|Rockingham|8": (0, 1, 0, True),
                "H|Rockingham|7": (0, 0, 1, None), "H|Rockingham|13": (2, 0, 0, None),
                "S|24": (1, 0, 0, None)}
        got = {k: (len(races[k]["elected"]), races[k]["not_final"], races[k]["held"],
                   races[k].get("recount")) for k in want}
        assert got == want, f"elected, not final, held and recount read {got}, not {want}"
        text = json.dumps(doc)
        assert "PRIVATE" not in text and "why" not in text, (
            "a reason from the person's file reached the site")
        assert "DO NOT ADD UP" not in out, f"the step says a whole race does not add up: {out}"
        results = root / "collected" / "election_2026.json"
        r = json.loads(results.read_text(encoding="utf-8"))
        del r["races"]["H|Rockingham|6"]
        results.write_text(json.dumps(r), encoding="utf-8")
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_HAND)
        lost = doc["races"].get("H|Rockingham|6") if doc else None
        assert code == 0 and lost == {"seats": 1, "elected": [], "not_final": 0, "held": 0}, (
            f"a race the results lost is drawn as {lost}")
        assert "H|Rockingham|6" in _elect_part(out, "DO NOT ADD UP"), (
            "a race the results lost is not printed for the person: " + out[-400:])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", (f"{len(races)} races, each its seats: the tie and the recount not final, the "
                  "write-in held, no private reason published; a race the results lost is "
                  "there with no member-elect and printed for the person")


@check("build", "members-elect: no race is final until the build's day is past the recount "
                "deadline the person entered, but one the results mark recounted; a not-final "
                "mark for some seats holds back only those; and the person's entries reach only "
                "their own election")
def _elect_final():
    """The person's rule of 16 October 2026: a race counts as final once
    posted and past its recount deadline, or once its recount result is out.
    The deadline is the person's to enter, in the hand file, because the
    results do not carry it and the step does not guess it (the review of 16
    October 2026 found every winner drawn the day the results were
    committed). On the fixture's election:

      - with no deadline entered, on 20 November no race is final and no
        winner is drawn, and the step says why -- and John Smith, whom the
        rule cannot settle, is put to the person all the same, so that he
        is settled by the day his race is drawn;
      - with the deadline 13 November, a build on the 13th draws none, and
        one on the 14th draws the winners;
      - a race the results mark recounted is drawn on the 10th, before the
        deadline, and no other is;
      - a not-final mark with "seats": 1 on Rockingham 13's two seats holds
        one back, and the winner with the more votes is drawn;
      - entries under another election's day change nothing of this one's:
        not its matches, its not-final marks, its held winners, nor -- the
        2024 deadline long past -- whether its races are final."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-elect-final-"))

    def drawn(doc):
        return {k: [e["n"] for e in r["elected"]] for k, r in (doc or {}).get("races", {}).items()
                if r["elected"]}

    def all_held_back(doc):
        return bool(doc) and not drawn(doc) and all(
            r["not_final"] + r["held"] == r["seats"] for r in doc["races"].values())
    try:
        _elect_fixture(root)
        bad = []
        deadline = {"2026-11-03": {"recount_deadline": _ELECT_DEADLINE}}
        code, out, doc = _elect_run(root, _ELECT_IN, hand={"2026-11-03": {}})
        if code or not all_held_back(doc) or "no recount deadline is entered" not in out:
            bad.append(f"no deadline entered, on {_ELECT_IN}: exit {code}, drawn {drawn(doc)}")
        if "John Smith: 2 former members of that name" not in _elect_part(out, "NOT LINKED"):
            bad.append("a winner whose race is not final yet is not put to the person")
        code, out, doc = _elect_run(root, _ELECT_DEADLINE, hand=deadline)
        if code or not all_held_back(doc) or "has not passed" not in out:
            bad.append(f"on the deadline day: exit {code}, drawn {drawn(doc)}")
        code, out, doc = _elect_run(root, "2026-11-14", hand=deadline)
        if code or drawn(doc).get("H|Rockingham|6") != ["Michael Vose"] or "NOT FINAL YET" in out:
            bad.append(f"the day after the deadline: exit {code}, drawn {drawn(doc)}")
        results = root / "collected" / "election_2026.json"
        kept = results.read_bytes()
        r = json.loads(kept)
        r["races"]["H|Rockingham|6"]["recounted"] = True
        results.write_text(json.dumps(r), encoding="utf-8")
        code, out, doc = _elect_run(root, "2026-11-10", hand=deadline)
        if code or drawn(doc) != {"H|Rockingham|6": ["Michael Vose"]}:
            bad.append(f"a recounted race before the deadline: exit {code}, drawn {drawn(doc)}")
        results.write_bytes(kept)
        code, out, doc = _elect_run(root, _ELECT_IN, hand={"2026-11-03": dict(
            deadline["2026-11-03"], not_final={"H|Rockingham|13": {"seats": 1}})})
        r13 = (doc or {}).get("races", {}).get("H|Rockingham|13") or {}
        if code or [e["n"] for e in r13.get("elected", [])] != ["Jodi Nelson"] or \
                r13.get("not_final") != 1:
            bad.append(f"one of Rockingham 13's two seats marked not final: {r13}")
        other = {"recount_deadline": "2024-11-08",
                 "matches": {"H|Rockingham|13": {"John Smith": "900003"}},
                 "not_final": {"H|Rockingham|6": {"recount": True}},
                 "held": {"S|24": {"Debra Altschiller": "PRIVATE"}}}
        code, out, doc = _elect_run(root, _ELECT_IN, hand=dict(deadline, **{"2024-11-05": other}))
        races = (doc or {}).get("races", {})
        smith = [e for e in races.get("H|Rockingham|13", {}).get("elected", [])
                 if e["n"] == "John Smith"]
        if code or drawn(doc).get("H|Rockingham|6") != ["Michael Vose"] or \
                races["H|Rockingham|6"].get("recount") or races["S|24"]["held"] or \
                drawn(doc).get("S|24") != ["Debra Altschiller"] or \
                [e["k"] for e in smith] != ["new"]:
            bad.append(f"2024's entries reached 2026's races: drawn {drawn(doc)}, Smith {smith}")
        code, out, doc = _elect_run(root, _ELECT_IN, hand={"2024-11-05": other})
        if code or not all_held_back(doc):
            bad.append(f"2024's recount deadline made 2026's races final: drawn {drawn(doc)}")
        assert not bad, "; ".join(bad)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("none final with no deadline or on its day, all the day after, a recounted race "
                  "before it; one seat of two held back; 2024's entries reach nothing of 2026; "
                  "a name to settle is put to the person while its race is not final")


@check("build", "members-elect: a source changed since the results were read, a hand file that "
                "will not read or says what it cannot mean, and an error nobody foresaw each stop "
                "the step, the last build's file removed and the reason the last line on stderr")
def _elect_refuses():
    """Check 5 of the plan, and the step's refusals: each _source's sha256 is
    the saved file's, and a source changed since the results were read is
    refused, since the results would no longer be what it says; a hand file
    that will not read is refused, since it might mark a race not final; so
    is a recount deadline that is no day or not after the election, and a
    not-final mark whose seats are no number; and an error nobody foresaw --
    here, the file it writes cannot be written -- stops it too. Each exits
    other than 0, removes the file the last build left, and says why in the
    last line on stderr, which is what build_all prints of a failed step and
    keeps in build.json (the review of 16 October 2026 found a refusal said
    only on stdout, which reached the night's log as "no error text")."""
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    root = Path(tempfile.mkdtemp(prefix="gr-elect-refuses-"))
    try:
        site = _elect_fixture(root)
        stale = site / "members_elect.json"
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_HAND)
        assert code == 0 and doc, f"the step wrote nothing on {_ELECT_IN}: {out[-300:]}"
        old = stale.read_bytes()
        bad = []

        def refused(label, want, hand=None):
            stale.write_bytes(old)
            code, out, doc, err = _elect_run(root, _ELECT_IN, hand=hand, err=True)
            last = (err.strip().splitlines() or [""])[-1]
            if code == 0 or doc is not None or "Removed" not in out or want not in last:
                bad.append(f"{label}: exit {code}, {'a file left' if doc else 'no file'}, last "
                           f"on stderr {last[-200:]!r}")
        src = root / "records" / "sources" / "sos-general-election-2026-fixture.txt"
        src.write_bytes(_ELECT_SOURCE + b"changed since\n")
        refused("a source changed since the results were read",
                "REFUSED: records/sources/sos-general-election-2026-fixture.txt is not the file")
        src.write_bytes(_ELECT_SOURCE)
        (root / "corrections" / "members_elect.json").write_text("{not json", encoding="utf-8")
        refused("a hand file that will not read", "REFUSED: corrections/members_elect.json will "
                                                  "not read")
        for day in ("13 November", "2026-11-03"):
            refused(f"a recount deadline of {day!r}", "\"recount_deadline\" is",
                    hand={"2026-11-03": {"recount_deadline": day}})
        refused("a not-final mark whose seats are no number", "not_final['H|Rockingham|8']",
                hand={"2026-11-03": {"not_final": {"H|Rockingham|8": {"seats": "one"}}}})
        tmp = site / "members_elect.json.tmp"
        tmp.mkdir()
        refused("the file cannot be written", "Error", hand=_ELECT_HAND)
        tmp.rmdir()
        stale.write_bytes(old)
        code, out, doc = _elect_run(root, _ELECT_IN, hand=_ELECT_HAND)
        if code or not doc:
            bad.append(f"once each is put right the step does not write again: exit {code}")
        assert not bad, "; ".join(bad)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return "ok", ("a changed source, an unreadable hand file, two deadlines that are no deadline, "
                  "a not-final mark of no seats and a file that cannot be written each stop it, "
                  "the last file removed and the reason last on stderr")


# map.js mounted in node on dom_stub.js, with components.js loaded first as
# every page loads it, and each district of the filled layers chosen in turn:
# what the panel says of it. The stub's querySelector makes a new element on
# every call, so the root here gives back the same one for the same selector,
# and the panel mount() writes into can be read after it. No labels and no
# zoom: the panel is what is read, and those need a browser's measure.
_ELECT_MAP_JS = r"""
require("./stub.js");
globalThis.CSS = { escape: s => String(s) };
document.createElementNS = (ns, t) => document.createElement(t);
const fs = require("fs");
const G = require("./map.js");
function held() {
  const e = document.createElement("div"), q = {};
  e.querySelector = sel => (q[sel] = q[sel] || held());
  e.style.setProperty = () => {};
  return e;
}
(async () => {
  const out = {};
  for (const name of ["with", "without"]) {
    const T = JSON.parse(fs.readFileSync("./" + name + ".json", "utf8"));
    globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => T });
    const root = held();
    const api = G.mount(root, { labels: "none", zoom: false, data: "/" + name + ".json" });
    await api.ready;
    const panel = root.querySelector(".gmpanel");
    out[name] = {};
    for (const lk of ["base", "float", "senate", "exec", "cong"])
      for (const fid of Object.keys(T.layers[lk].f)) {
        api.select(lk, fid);
        out[name][lk + "|" + fid] = panel.innerHTML;
      }
  }
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.error(String(e && e.stack || e)); process.exit(1); });
"""


def _elect_map_panels(with_map, without_map):
    """{"with": {"layer|district": html}, "without": {...}}: the district
    map's panel (map.js's describe and seatLine) for every district of the
    State House, floterial, Senate, Council and US House layers, drawn in
    node from each district_map.json. None without node."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        assert not os.environ.get("GITHUB_ACTIONS"), "node is not on PATH on the nightly"
        return None
    root = Path(tempfile.mkdtemp(prefix="gr-elect-map-"))
    try:
        (root / "stub.js").write_text(_source("tests/dom_stub.js"),
                                      encoding="utf-8")
        (root / "map.js").write_text(_with_components(
            _source("src/pages/map.js")), encoding="utf-8")
        (root / "with.json").write_bytes(with_map.read_bytes())
        (root / "without.json").write_bytes(without_map.read_bytes())
        (root / "go.js").write_text(_ELECT_MAP_JS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, encoding="utf-8",
                 timeout=120)
        said = (r.stderr or r.stdout or "").strip()
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "map.js would not draw the district panel in node: " + said[-300:])
        return json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)


# "Serving now", then who sits (or the words for nobody), then the block: the
# order the person's decision draws them in, on each surface's own markup.
def _elect_order(sitting):
    return re.compile(r'<p class="elnow" data-elect data-until="2026-12-02">Serving now</p>'
                      r"(?:" + sitting + r')<div class="elect" data-elect data-until="2026-12-02">',
                      re.S)


@check("build", "members-elect in the district map's panel: drawn only for a district whose race "
                "the file holds, every one inside data-elect with \"Serving now\" over the sitting "
                "members, none among them, and nothing without the file")
def _elect_map_panel():
    """The plan's check 1 for the one surface the built pages do not hold:
    the district map's panel, which map.js draws in the browser from
    district_map.json's "elect" (the person's decisions of 16 October 2026: a
    list in the panel, the fill unchanged, members-elect never drawn as
    sitting). map.js is mounted in node with the fixture's district_map.json
    built with the file and without, and every district of the State House,
    floterial, Senate, Council and US House layers chosen in turn. Without
    the file no panel carries data-elect or "Serving now". With it every
    panel is the same as without once each element carrying data-elect is
    taken out whole -- so no member-elect's chip stands among the sitting
    members or anywhere outside a block -- and a panel draws one block for
    each race of the file it shows (a State House district's own and its
    floterial's), each after "Serving now" and who sits, and each holding
    the race's members-elect by name. Silence is not success: every race of
    the file is a district of the map, and is drawn."""
    import html as _h
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    w, o, doc, _said = _elect_built()
    mw, mo = w / "site" / "district_map.json", o / "site" / "district_map.json"
    dw = json.loads(mw.read_text(encoding="utf-8"))
    races = (dw.get("elect") or {}).get("races") or {}
    got = _elect_map_panels(mw, mo)
    if got is None:
        return "skip", "node is not here"
    bad = []
    if not races:
        bad.append("the fixture's district_map.json carries no members-elect")
    if set(got["with"]) != set(got["without"]) or not got["without"]:
        bad.append("the map's districts differ with the file and without")
    off = sorted(set(races) - set(got["with"]))
    if off:
        bad.append(f"races of the file that are no district of the map: {off[:6]}")
    flo = {ws[0]: ws[1] for t in dw["places"].values() for ws in t["w"].values() if ws[1]}
    order = _elect_order(r'<div class="chips">.*?</div>|<p class="quiet">Every seat is vacant\.</p>')
    drawn = 0
    for k, html in sorted(got["without"].items()):
        if "data-elect" in html or "Serving now" in html:
            bad.append(f"the panel for {k} draws a member-elect with no file: {html[:160]}")
    for k, html in sorted(got["with"].items()):
        if _elect_strip(html) != got["without"].get(k):
            bad.append(f"the panel for {k} differs with the file outside its data-elect elements")
        lk, fid = k.split("|", 1)
        shows = [x for x in [k] + ([f"float|{flo[fid]}"] if lk == "base" and fid in flo else [])
                 if x in races]
        blocks = html.count('<div class="elect" data-elect')
        nows = html.count('<p class="elnow" data-elect')
        if not blocks == nows == len(order.findall(html)) == len(shows):
            bad.append(f"the panel for {k} draws {blocks} block(s) and {nows} \"Serving now\", "
                       f"{len(order.findall(html))} of them in order, for {len(shows)} race(s)")
        inside = "".join(html[a:b] for a, b in _elect_blocks(html))
        for e in (e for x in shows for e in races[x]["elected"]):
            if _h.escape(e["n"]) not in inside:
                bad.append(f"the panel for {k} does not name {e['n']} in its block")
        drawn += bool(shows)
    assert not bad, "; ".join(bad[:8])
    return "ok", (f"{len(got['with'])} districts chosen: {drawn} panels draw the file's races, "
                  "each block after \"Serving now\" and who sits, every panel the same as without "
                  "the file outside its data-elect, and none drawn without it")


@check("build", "members-elect: the approved words where the pages draw them -- the map's words in "
                "both copies, \"Serving now\" over the sitting members on a town page's State House "
                "and Senate cards and in the My Town card, and the Officials tab's label and "
                "sentence")
def _elect_pages_words():
    """The person's words of 16 October 2026, read where the fixture's pages
    and find.js draw them rather than from the source that writes them.

    THE MAP'S WORDS, WITH THE FILE AND WITHOUT: neither a town page's Map tab
    nor the Officials page's map says "the members it elected" -- the old
    words, which from the day after an election read as the people just
    elected. The note that replaced them, "Each district colored by the
    party of its sitting members", went from the Officials page on 22
    October 2026 and from the town pages, with the box it was in, on 25
    October (the audit: the map began 470 to 540px below its heading on a
    phone); the Officials page says "Choose a district to see who represents
    it." They are read in both builds.

    "SERVING NOW" WHEREVER A BLOCK IS DRAWN BESIDE THE SITTING MEMBERS: on
    every town page's Representatives tab, the State House card and the
    State Senate card each draw, for every district, "Serving now", then who
    sits (and any seat vacant), then the block -- as many of each as
    there are blocks, and at least one; and so does each House and Senate
    seat of the My Town card (find.js, in node) for a place whose races the
    file holds.

    THE OFFICIALS TAB: its label is "Members-Elect (N)", N the winners the
    file names, and its sentence is "Elected November 3, 2026, by the
    Secretary of State's count. They take office on December 2, 2026; until
    then the Legislators tab lists who holds each seat." -- the fixture's
    days, the person's words."""
    import html as _h
    absent = _elect_absent()
    if absent:
        return "skip", "not here: " + ", ".join(absent)
    w, o, doc, _said = _elect_built()
    ws, os_ = w / "site", o / "site"
    bad = []

    def text(h):
        return " ".join(_h.unescape(re.sub(r"<[^>]+>", "", h)).replace("’", "'").split())
    towns = sorted((ws / "town").glob("*.html"))
    if not towns:
        bad.append("the fixture built no town page")
    for site in (ws, os_):
        for f in [site / "officials.html", *sorted((site / "town").glob("*.html"))]:
            t = text(f.read_text(encoding="utf-8"))
            # The Officials map's note is "Choose a district to see who
            # represents it" since the trims of 22 October 2026; a town's map
            # has no box over it since the audit of 25 October 2026 -- its
            # legend says what the colours are -- and neither says "the
            # members it elected".
            name = f.relative_to(site.parent).as_posix()
            if f.name == "officials.html" and "Choose a district to see who represents it." not in t:
                bad.append(f"{name} does not say \"Choose a district to see who represents it.\"")
            if f.name != "officials.html" and "Choose a kind of district" in t:
                bad.append(f"{name} still draws the box of instructions over its map")
            if "members it elected" in t:
                bad.append(f"{name} still says \"the members it elected\"")
    sec = re.compile(r'<section class="twnsec[^"]*"><h3 class="twnh">(State House|State Senate[^<]*)'
                     r"</h3>(.*?)</section>", re.S)
    town_order = _elect_order(r'<ul class="offlist">.*?</ul>|<p class="note">[^<]*</p>')
    senates = 0
    for f in towns:
        t = f.read_text(encoding="utf-8")
        a = t.find('<div class="twnpane" id="representatives"')
        b = t.find('<div class="twnpane"', a + 1)
        cards = sec.findall(t[a:b if b > a else len(t)]) if a >= 0 else []
        if not any(h == "State House" for h, _b in cards):
            bad.append(f"town/{f.name}: no State House card on its Representatives tab")
        for head, body in cards:
            senates += head.startswith("State Senate")
            n = body.count('<div class="elect" data-elect')
            if not n or n != body.count('<p class="elnow" data-elect') \
                    or n != len(town_order.findall(body)):
                bad.append(f"town/{f.name}'s {head} card: {n} block(s), "
                           f"{body.count('Serving now')} \"Serving now\", "
                           f"{len(town_order.findall(body))} in order")
    if not senates:
        bad.append("no town page of the fixture has a State Senate card to read")
    pw = json.loads((ws / "places.json").read_text(encoding="utf-8"))
    card = _elect_card(ws / "places.json", os_ / "places.json")
    yt_order = _elect_order(r'<ul class="ytppl">.*?</ul>|<p class="ytnote">[^<]*</p>')
    seats = 0
    if card is not None:
        for p in pw["places"]:
            for chunk in card["with"][p["s"]].split('<div class="ytseat">')[1:]:
                office = re.match(r'<p class="ytoff">([^<]*)', chunk)
                ch = {"State House": "H", "State Senate": "S"}.get(office.group(1) if office else "")
                if not ch:
                    continue
                want = int(any(k.startswith(ch + "|") for k in p.get("e") or []))
                got = (chunk.count('<div class="elect" data-elect'),
                       chunk.count('<p class="elnow" data-elect'), len(yt_order.findall(chunk)))
                seats += want
                if got != (want, want, want):
                    bad.append(f"the My Town card for {p['s']}, {office.group(1)}: blocks, "
                               f"\"Serving now\" and the two in order {got}, not {want} each")
        if not seats:
            bad.append("the My Town card draws no House or Senate seat with members-elect")
    t = (ws / "officials.html").read_text(encoding="utf-8")
    n = sum(len(r["elected"]) for r in doc["races"].values())
    tab = re.search(r'<button[^>]*\bid="tab-members-elect"[^>]*>(.*?)</button>', t, re.S)
    if not n or not tab or text(tab.group(1)) != f"Members-Elect ({n:,})":
        bad.append(f"the Officials tab reads {text(tab.group(1)) if tab else None!r}, not "
                   f"\"Members-Elect ({n:,})\"")
    pane = re.search(r'<div class="elpane"[^>]*>.*?<p class="ofwhy">(.*?)</p>', t, re.S)
    said = ("Elected November 3, 2026, by the Secretary of State's count. They take office on "
            "December 2, 2026; until then the Legislators tab lists who holds each seat.")
    if not pane or text(pane.group(1)) != said:
        bad.append(f"the Officials tab says {text(pane.group(1)) if pane else None!r}, not "
                   f"{said!r}")
    assert not bad, "; ".join(bad[:8])
    return "ok", (f"the map's words, without the old ones, on {len(towns) + 1} pages, with the file and "
                  f"without; \"Serving now\" before who sits and the block on {len(towns)} town "
                  f"pages' House and Senate cards"
                  + (f" and {seats} seats of the My Town card" if card is not None else "")
                  + f"; \"Members-Elect ({n:,})\" and its sentence")
