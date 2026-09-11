#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.6
"""
The record as CSV, for anyone who wants to work with it rather than read it.

    python3 build_exports.py --site site

WHY

Everything this site knows is already published as JSON, and JSON is a fine
answer for a program and a poor one for a person with a spreadsheet and a
question. Somebody building a scorecard, checking a claim about a member's
votes, or teaching a class should not have to learn how index.json is shaped
or which of nineteen per-term files to fetch first. A CSV opens in anything.

WHAT IT REFUSES TO DO

It writes no file over the host's limit. Cloudflare Pages rejects anything
past 25 MiB, and the member votes are 437,702 rows and 27.9 MB in one piece --
which would have failed at deploy time, after a five-minute build, with an
error about a file rather than about a decision. So the votes are split by
term, and every table's size is checked against the cap before it is written
rather than after.

It also states row counts and column names in a manifest beside the files, so
a program can discover what is here in one request instead of guessing from
filenames.
"""

import argparse
import csv
import json
from pathlib import Path

# Cloudflare Pages refuses a file larger than this. Checked before writing,
# because the alternative is finding out during a deploy.
CAP = 25 * 1024 * 1024
SAFE = int(CAP * 0.9)          # leave room; a term grows through a session


def load(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def term_of(year):
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return ""
    a = y if y % 2 else y - 1
    return f"{a}-{a + 1}"


def write(out, name, columns, rows, what):
    """One table, with its size checked before it is a deploy's problem."""
    p = out / name
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        n = 0
        for r in rows:
            w.writerow(r)
            n += 1
    size = p.stat().st_size
    flag = "  OVER THE 25 MiB CAP" if size > SAFE else ""
    print(f"  {name:<28} {n:>9,} rows  {size / 1e6:>7.1f} MB{flag}")
    return {"file": name, "rows": n, "bytes": size,
            "columns": list(columns), "what": what,
            "over_cap": size > SAFE}


# The columns of bills.csv that are not filled for every term, and are not
# meant to be. Measured rather than asserted: see coverage() below.
SPARSE = ["sponsor", "committee", "topic", "passage"]


def coverage(out):
    """How much of each sparse column is actually there, per term.

    A CSV with an empty column reads as a bug unless something says
    otherwise, and somebody writing a scorecard off sponsors would find them
    for 4,085 bills of 33,683 and reasonably conclude the file was broken.

    It is not broken; the General Court's own search gives a title and a
    status for every bill back to 1989 and gives sponsors only for the recent
    terms, and the archived dockets that carry the rest are still being
    fetched one term at a time. Publishing the shape of that is the
    difference between a gap and a defect.
    """
    import csv as _csv
    path = out / "bills.csv"
    if not path.exists():
        return []
    per, totals = {}, {}
    with path.open(encoding="utf-8", newline="") as fh:
        for r in _csv.DictReader(fh):
            term = r.get("term") or ""
            totals[term] = totals.get(term, 0) + 1
            row = per.setdefault(term, dict.fromkeys(SPARSE, 0))
            for c in SPARSE:
                if (r.get(c) or "").strip():
                    row[c] += 1
    return [{"term": term, "bills": totals[term],
             **{c: per[term][c] for c in SPARSE}}
            for term in sorted(totals) if term]


def bills(out, site):
    idx = load(site / "index.json", [])
    # chapter goes last so a reader who counted columns before it existed
    # still finds each one where it was.
    cols = ["term", "year", "bill", "title", "sponsor", "committee", "topic",
            "status", "outcome", "passage", "roll_calls", "chapter"]
    rows = ([b.get("term", ""), b.get("year", ""), b.get("id", ""),
             b.get("title", ""), b.get("sponsor", ""),
             "; ".join(b.get("committees") or ([b["committee"]]
                                               if b.get("committee") else [])),
             b.get("topic", ""), b.get("status", ""), b.get("kind", ""),
             # Five characters: where it started and each stop it reached.
             # Documented on the data page rather than left as a code.
             b.get("passage", ""), b.get("nrc", 0), b.get("chapter", "")]
            for b in sorted(idx, key=lambda b: (str(b.get("term")),
                                                str(b.get("id")))))
    return write(out, "bills.csv", cols, rows,
                 "Every bill of every term: title, sponsor, committee, "
                 "outcome, how far it got, and the chapter of the laws it "
                 "became.")


def legislators(out, site):
    legs = load(site / "legislators.json", [])
    cols = ["id", "name", "chamber", "party", "district", "county", "email",
            "phone", "committees", "bills_sponsored", "recorded_votes"]
    rows = ([m.get("id", ""), m.get("display_full") or m.get("name", ""),
             "Senate" if m.get("chamber") == "S" else "House",
             m.get("party", ""), m.get("district", ""), m.get("county", ""),
             m.get("email", ""), m.get("phone", ""),
             "; ".join(m.get("committees") or []),
             m.get("n_sponsored", 0), m.get("n_votes", 0)]
            for m in sorted(legs, key=lambda m: str(m.get("name"))))
    return write(out, "legislators.csv", cols, rows,
                 "The sitting roster, with district, contact details and "
                 "committee seats.")


def rollcalls(out):
    rc = load("rollcalls.json", {})
    cols = ["roll_call", "term", "year", "body", "number", "date", "bill",
            "question", "question_plain", "yeas", "nays", "not_voting",
            "passed", "procedural", "threshold_needed", "threshold_rule"]
    rows = []
    for term, bills_ in (rc.items() if isinstance(rc, dict) else []):
        for _b, entries in (bills_.items() if isinstance(bills_, dict) else []):
            for r in (entries if isinstance(entries, list) else [entries]):
                rows.append([
                    f'{r.get("year")}-{r.get("body")}-{r.get("number")}',
                    term, r.get("year", ""), r.get("body", ""),
                    r.get("number", ""), r.get("date", ""), r.get("bill") or "",
                    r.get("question", ""), r.get("question_plain") or "",
                    r.get("yeas", ""), r.get("nays", ""),
                    r.get("not_voting", ""),
                    1 if r.get("passed") else 0,
                    1 if r.get("procedural") else 0,
                    r.get("threshold_needed") or "",
                    r.get("threshold_rule") or ""])
    rows.sort(key=lambda r: (str(r[2]), str(r[3]), int(r[4] or 0)))
    return write(out, "rollcalls.csv", cols, rows,
                 "Every recorded vote: the question in the record's words and "
                 "in plain English, the tally, and what it needed to carry.")


def votes(out, data):
    """Member votes, split by term because one file would exceed the cap."""
    mv = load(Path(data) / "member_votes.json", [])
    cols = ["roll_call", "term", "date", "bill", "question", "member_id",
            "member", "party", "chamber", "vote"]
    by_term = {}
    for v in mv:
        by_term.setdefault(term_of(v.get("year")), []).append(v)
    made = []
    for term in sorted(by_term):
        if not term:
            continue
        rows = ([f'{v.get("year")}-{v.get("body")}-{v.get("vote_number")}',
                 term, v.get("date", ""), v.get("bill", ""),
                 v.get("question", ""), v.get("member_id", ""),
                 v.get("name", ""), v.get("party", ""),
                 "Senate" if v.get("body") == "S" else "House",
                 v.get("vote", "")]
                for v in by_term[term])
        made.append(write(
            out, f"votes-{term}.csv", cols, rows,
            f"How every member voted on every roll call of {term}. "
            "Join to rollcalls.csv on roll_call."))
    return made


def proceedings_table(out, site):
    """Every proceeding, with the time its bill's page prints.

    THE PAGE'S TIME, NOT THE SCHEDULE. start_seconds was proceedings.csv's
    predicted_offset -- the meeting's called time minus the stream's start --
    and how_placed was the manifest's match method, "single video". So 13,987
    rows told anyone who downloaded them that the schedule was when a bill
    was heard, while the pages print the boundary the chair stated for
    12,751 of them. It is the mix-up the bench made on 9 September, in the
    one file meant for other people to build on.

    Now start_seconds and end_seconds are the bill page's own station, read
    from the page, and how_placed is the page's word for how it was placed;
    the schedule is kept, named for what it is. A proceeding the page gives
    no time -- none recorded, or captions an hour out of step with their
    recording -- has none here either.
    """
    import proceedings as P
    import site_read as SR
    cols = ["term", "bill", "body", "kind", "date", "time", "committee",
            "venue", "video_id", "video_title", "start_seconds",
            "end_seconds", "how_placed", "end_how", "scheduled_seconds"]
    idx = load(Path(site) / "index.json", [])
    folder = {(b.get("term"), b.get("id")): str(b.get("year") or "")
              for b in (idx if isinstance(idx, list) else [])}
    stations = SR.by_bill(site, SR.video_years(), fields=("stations",))

    def published(r):
        key = (folder.get((r.get("term"), r.get("bill"))),
               (r.get("bill") or "").upper())
        sts = (stations.get(key) or {}).get("stations") or []
        here = [s for s in sts if s.get("when") == r.get("date")
                and s.get("video_id") == r.get("video_id")]
        want = (r.get("kind") or "").strip().lower()
        if len(here) > 1 and want:
            here = [s for s in here if want in (s.get("what") or "").lower()] or here
        return here[0] if here else {}

    rows, placed = [], 0
    for r in P.load():
        st = published(r) if r.get("video_id") else {}
        placed += st.get("start") is not None
        rows.append([r.get("term", ""), r.get("bill", ""), r.get("body", ""),
                     r.get("kind", ""), r.get("date", ""), r.get("time", ""),
                     r.get("committee", ""), r.get("venue", ""),
                     r.get("video_id", ""), r.get("video_title", ""),
                     "" if st.get("start") is None else st["start"],
                     "" if st.get("end") is None else st["end"],
                     st.get("state") or "", st.get("end_from") or "",
                     r.get("predicted_offset") or ""])
    rows.sort(key=lambda r: (r[4], r[1]))
    print(f"  proceedings.csv: {placed:,} rows carry the time their page "
          "prints")
    return write(out, "proceedings.csv", cols, rows,
                 "Every hearing, executive session and floor debate on "
                 "record, and the recording it is on where there is one. "
                 "start_seconds and end_seconds are the moment in the "
                 "recording the bill's page gives, and how_placed says how it "
                 "was found: stated (the chair said it), floor_stated, "
                 "floor_precise (a roll call's clock time), located (estimated "
                 "from the captions; the page says approximate). "
                 "scheduled_seconds is the meeting's called time minus the "
                 "stream's start, which is the schedule and not a finding.")


def sponsors(out, data):
    sp = load(Path(data) / "sponsors.json", {})
    cols = ["term", "bill", "member_id", "member", "party", "chamber",
            "prime", "role"]
    rows = []
    for term, bills_ in (sp.items() if isinstance(sp, dict) else []):
        for bill, people in (bills_.items() if isinstance(bills_, dict) else []):
            for m in (people if isinstance(people, list) else []):
                rows.append([term, bill, m.get("member_id", ""),
                             m.get("label") or m.get("name", ""),
                             m.get("party", ""), m.get("chamber", ""),
                             1 if m.get("prime") else 0, m.get("role", "")])
    rows.sort(key=lambda r: (r[0], r[1], -r[6]))
    return write(out, "sponsors.csv", cols, rows,
                 "Who put their name to which bill, and who was prime. "
                 "Sponsoring is not voting and is not counted as one.")


# How the tables join, said once here rather than guessed at by everyone
# who downloads them. Keyed by file so the page and the manifest agree.
JOINS = {
    "votes-": "roll_call joins rollcalls.csv; bill + term joins bills.csv; "
              "member_id joins legislators.csv.",
    "rollcalls.csv": "roll_call is year-body-number and is the key the vote "
                     "files use. bill + term joins bills.csv.",
    "sponsors.csv": "bill + term joins bills.csv; member_id joins "
                    "legislators.csv.",
    "proceedings.csv": "bill + term joins bills.csv. video_id is a YouTube id.",
    "legislators.csv": "id is member_id in the vote and sponsor files.",
    "bills.csv": "bill + term is the key every other table refers to. A bill "
                 "number alone is not a key: HB100 names a different bill in "
                 "every biennium.",
}


def _pct(n, of):
    if not of:
        return "&mdash;"
    if n == 0:
        return '<span class="c0">none</span>'
    if n >= of:
        return '<span class="c1">all</span>'
    return f'<span class="cp">{100 * n / of:.0f}%</span>'


def data_page(site, out, tables, base, cov=()):
    """The downloads, described for somebody who has not read the code."""
    try:
        import shell as S
    except ImportError:
        print("  (shell.py not here, so no data.html)")
        return
    tmpl = S.template(site)
    E = lambda s: (str(s).replace("&", "&amp;").replace("<", "&lt;")
                   .replace(">", "&gt;"))

    def row(tb):
        join = next((v for k, v in JOINS.items() if tb["file"].startswith(k)
                     or tb["file"] == k), "")
        return f'''<section class="dl">
      <h3><a href="data/{E(tb["file"])}">{E(tb["file"])}</a></h3>
      <p class="dlmeta">{tb["rows"]:,} rows &middot; {tb["bytes"] / 1e6:.1f} MB
        &middot; CSV, UTF-8, header row</p>
      <p>{E(tb["what"])}</p>
      {f'<p class="note">{E(join)}</p>' if join else ""}
      <p class="cols"><b>Columns</b> {", ".join(E(c) for c in tb["columns"])}</p>
    </section>'''

    cov_rows = "".join(
        f'''<tr><td>{E(c["term"])}</td><td class="n">{c["bills"]:,}</td>
        <td>{_pct(c["sponsor"], c["bills"])}</td>
        <td>{_pct(c["committee"], c["bills"])}</td>
        <td>{_pct(c["topic"], c["bills"])}</td>
        <td>{_pct(c["passage"], c["bills"])}</td></tr>''' for c in cov)

    body = f'''<div class="civics hubpage datapage">
    <div class="phead">
      <h1>The data</h1>
      <p class="pmeta">Everything this site knows, as CSV. {sum(t["rows"] for t in tables):,}
        rows across {len(tables)} tables.</p>
    </div>
    <p class="src">These are built from the same files the pages are drawn
      from, by the same run, so a download and a page cannot disagree. They
      are rebuilt whenever the site is.</p>

    <h2>Before you start</h2>
    <p class="src"><b>A bill number is not a key.</b> HB100 names a different
      bill in every biennium, so every table carries a <code>term</code> and
      the pair <code>bill</code>&nbsp;+&nbsp;<code>term</code> is what joins
      them. Getting this wrong silently merges two centuries of different
      bills, which is a mistake this project has made and fixed.</p>
    <p class="src"><b>The <code>passage</code> column</b> in bills.csv is one
      character per stop: where the bill started, then the House, the Senate,
      the Governor and the statute book. <code>p</code> passed,
      <code>x</code> stopped there, <code>-</code> never reached it. A
      resolution has three characters rather than five, because it has fewer
      places to go.</p>
    <p class="src"><b>The <code>chapter</code> column</b> is the chapter of
      that year's session laws the bill became, as the General Court's docket
      records it &mdash; &ldquo;1, special session&rdquo; for a special
      session's own numbering. It is empty for a bill that did not become law, and for the
      few whose docket gives the same number to two bills in one year, where
      one of them is a typing error the docket cannot say which.</p>
    <p class="src"><b>Where a number is missing it is missing on purpose.</b> A
      hearing with no start time is one nobody has placed in the recording
      yet, not one that did not happen; a bill with no roll calls was decided
      on a voice vote, which records no individual member.</p>

    <h2>What is filled in, and for which terms</h2>
    <p class="src">Every bill back to 1989 has a title and an outcome. The
      rest arrives term by term as the archived dockets are fetched, and a
      column that is empty below is empty because the record has not been
      collected yet &mdash; not because the bill had no sponsor.</p>
    <div class="covwrap"><table class="cov">
      <thead><tr><th>Term</th><th>Bills</th><th>Sponsor</th><th>Committee</th>
        <th>Topic</th><th>Passage</th></tr></thead>
      <tbody>{cov_rows}</tbody></table></div>

    <h2>The tables</h2>
    {"".join(row(t) for t in tables)}

    <h2>For programs</h2>
    <p class="src"><a href="data/manifest.json">data/manifest.json</a> lists
      every table with its rows, byte size and column names, so a script can
      discover what is here in one request instead of guessing from
      filenames. The site&#39;s own JSON is served from this origin too and is
      open to cross-origin requests:
      <a href="index.json">index.json</a> (every bill),
      <a href="legislators.json">legislators.json</a>,
      <a href="rollcalls_index.json">rollcalls_index.json</a>.</p>

    <h2>Using it</h2>
    <p class="src">The record itself is the State of New Hampshire&#39;s and is
      public. This site adds the parsing, the joining and the plain-English
      summaries. Use it for whatever you like; a link back to
      graniterecord.org helps somebody check your working, which is the point
      of publishing the whole thing rather than a chart of it.</p>
    <p class="note">Found something that looks wrong? It probably is, and the
      page for that bill links the General Court&#39;s own record so the two
      can be compared.</p>
  </div>'''

    page = S.page(tmpl, path="/data.html", base=base,
                  title="The data | Granite Record",
                  og_title="The data",
                  description=("Every bill, vote, sponsor and hearing the "
                               "New Hampshire General Court has on record, "
                               "as CSV files anyone can download."),
                  globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the tables",
                  # NOT the empty string. shell.page only strips the
                  # template's own aria-current inside "if nav_current",
                  # so a page that passes nothing keeps bills.html's --
                  # and this page told every screen reader it was Bills.
                  sr_title="", nav_current="data.html")
    page = page.replace('<div id="results"></div>',
                        f'<div id="results">{body}</div>', 1)
    (site / "data.html").write_text(page, encoding="utf-8")
    print(f"  {'data.html':<28} the same tables, described")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--data", default="data")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    out = site / "data"
    out.mkdir(parents=True, exist_ok=True)

    print("Bulk downloads:")
    tables = [bills(out, site), legislators(out, site), rollcalls(out),
              proceedings_table(out, site), sponsors(out, a.data)]
    tables += votes(out, a.data)

    over = [t for t in tables if t["over_cap"]]
    manifest = {
        "what": "Granite Record bulk downloads. Public record of the New "
                "Hampshire General Court, rebuilt from the General Court's "
                "own published sources.",
        "base": "https://graniterecord.org/data/",
        "source": "https://graniterecord.org",
        "tables": [{k: v for k, v in t.items() if k != "over_cap"}
                   for t in tables],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    total = sum(t["bytes"] for t in tables)
    print(f"  {'manifest.json':<28} {len(tables):>9,} tables "
          f"{total / 1e6:>7.1f} MB in all")
    if over:
        raise SystemExit(
            "\nThese are past what Cloudflare Pages will take (25 MiB) and "
            "the deploy\nwould fail on them:\n  "
            + "\n  ".join(f'{t["file"]} at {t["bytes"] / 1e6:.1f} MB'
                          for t in over)
            + "\nSplit them before publishing.")
    cov = coverage(out)
    manifest["coverage"] = {
        "what": "How much of each column of bills.csv is filled, per term. A "
                "column that is empty is a record not yet collected rather "
                "than a bill without one.",
        "columns": SPARSE, "by_term": cov,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=1), encoding="utf-8")
    data_page(site, out, tables, a.base, cov)
    print("\nEvery table names its rows and columns in manifest.json, so a "
          "program can\nfind what is here in one request.")


if __name__ == "__main__":
    main()
