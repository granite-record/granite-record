#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.2
"""
/api: the data API's documentation page, drawn in the data page's own
components and counted from tonight's manifest.

    import api_page
    api_page.write(site, manifest, base)      # build_exports.py's last act

docs/design/api/DESIGN.md, 6; the mock it was drawn from is
docs/design/api/mock_body.html. Every figure on it is the manifest's, so the
page cannot say a size the files do not have.

UNLINKED UNTIL THE ANNOUNCEMENT (the owner's plan: built by 24 November,
announced in December). No navigation, no sitemap entry, and no link from the
data page yet; the address works for whoever is given it. Linking it is one
line in data_page's "For Developers" and one in the sitemap, on the day.

THE COMPONENTS ARE THE DATA PAGE'S: dphead and its lead, dponp, dpsec, the
dpdl downloads table with dpmore folds, dptermgrid, dpfold, dl.repo, and the
coverage table's covwrap, which here holds each example's code so that a line
wider than a phone scrolls inside its own box rather than widening the page.
"""

import json

import shell

E = lambda s: (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace('"', "&quot;"))
mb = lambda b: f"{(b or 0) / 1e6:.1f}&nbsp;MB"

ROBOTS = '<meta name="robots" content="noindex,follow">'

SECTIONS = (
    ("files", "The Files"),
    ("start", "Getting Started"),
    ("keys", "Keys and Joins"),
    ("changes", "What Changed Tonight"),
    ("live", "Today&rsquo;s Votes"),
    ("coverage", "What It Covers"),
    ("stability", "Versions and Stability"),
    ("using", "Using It"),
)


def _code(label, text):
    return (f'<div class="covwrap" data-scrollstop="1" role="region" aria-label="{E(label)}">'
            f'<pre class="apicode"><code>{E(text)}</code></pre></div>')


def _row(name, what, more, count, unit, size, href, verb="Download"):
    fold = (f'<details class="dpmore"><summary><span>More about <code>{E(name)}</code></span>'
            f'</summary>{more}</details>') if more else ""
    return (f'<tr role="row"><th scope="row" role="rowheader"><code>{E(name)}</code></th>'
            f'<td role="cell" class="dpw"><p class="dpwhat">{what}</p>{fold}</td>'
            f'<td role="cell" class="n dpr">{count}<span class="dpu"> {unit}</span></td>'
            f'<td role="cell" class="n dps">{size}</td>'
            f'<td role="cell" class="dpg"><a class="dpget" href="{href}"'
            f'{" download" if verb == "Download" else ""}>{verb}<span class="sr"> {E(name)}</span></a></td></tr>')


def body(manifest):
    files = manifest.get("files") or []
    by = {f["path"].rsplit("/", 1)[-1]: f for f in files}
    tables = [f for f in files if f.get("kind") == "table"]
    bills = [f for f in files if f.get("kind") == "bills"]
    db = next((f for f in files if f.get("kind") == "database" and not f.get("skipped")), None)
    people = by.get("people.json")
    schema = by.get("schema.json")
    newest = bills[0]["term"] if bills else "2025-2026"

    rows = [_row("manifest.json",
                 "Every file here, with its address, rows, size, checksum and the night it was built.",
                 "", f"{len(files) + 1:,}", "files", "&mdash;", "data/manifest.json", "Open")]
    if schema:
        rows.append(_row("schema.json",
                         "What every column and field of every file means, its type, and what it joins to.",
                         "<p>A Frictionless Data Package, a published standard that pandas, R and "
                         "the frictionless tools read directly. Each field says whether it is "
                         "<i>stable</i>, <i>beta</i>, or drawn for the page and promised nothing.</p>",
                         "&mdash;", "", mb(schema["bytes"]), "data/schema.json", "Open"))
    if db:
        c = db.get("counts") or {}
        rows.append(_row(
            db["path"].rsplit("/", 1)[-1],
            "Every table on the data page in one SQLite database, with the committee reports and "
            "their reasoning, interim study statements, testimony counts and every noticed meeting.",
            f"<p>{mb(db.get('opened_bytes'))} once opened. Tables: "
            + ", ".join(f"{E(t)} ({n:,})" for t, n in c.items())
            + ". Testimony is counts only, never a name. A vote is its roll call, its member, "
            "their person and a value, so each roll call and each member is stored once.</p>"
            '<p class="dpjoin">votes.rollcall joins rollcalls.id; votes.person and '
            "person_numbers.person join people.person; term + bill joins bills.</p>",
            f"{len(c):,}", "tables", mb(db["bytes"]), f"data/{E(db['path'].rsplit('/', 1)[-1])}"))
    if people:
        rows.append(_row(
            "people.json",
            f"One entry for each of the {people['rows']:,} people with a recorded vote since 1999, "
            "with every number the General Court has used for them.",
            "<p>The General Court gives a member a new employee number and a new person id when "
            "they move between the House and the Senate. This file joins every one of those, and "
            "the ids this site&rsquo;s other files use, to one <code>person</code>. "
            "<code>people.csv</code> is the same, one row a number.</p>",
            f"{people['rows']:,}", "people", mb(people["bytes"]), "data/people.json"))
    if bills:
        grid = "".join(
            f'<li><a href="data/{E(f["path"].rsplit("/", 1)[-1])}" download><span class="dpt">'
            f'{E(f["term"])}</span> <span class="dpm">{f["rows"]:,} bills &middot; {mb(f["bytes"])}'
            f'</span> <span class="sr">{E(f["path"].rsplit("/", 1)[-1])}</span></a></li>' for f in bills)
        rows.append(
            '<tr role="row" class="dpgroup"><th scope="row" role="rowheader">Bills by Term'
            '<code>bills-&lt;term&gt;.jsonl.gz</code></th>'
            '<td role="cell" class="dpw"><p class="dpwhat">Every bill&rsquo;s full record, one line a '
            "bill: its docket, hearings, votes, sponsors, committee reports, and the text of its "
            f"latest printing where the record has it. One file a term, {len(bills)} in all, from "
            f"{E(bills[-1]['term'])} to {E(bills[0]['term'])}.</p>"
            '<details class="dpmore"><summary><span>More about <code>bills-&lt;term&gt;.jsonl.gz'
            "</code></span></summary><p>Each line is one JSON object, keyed "
            f'<code>"key": "{E(newest)}/HB1442"</code>: the record the bill&rsquo;s own page is '
            "drawn from. It leaves out the Senate&rsquo;s hearing reports, which name members of "
            "the public, and YouTube&rsquo;s own titles and links.</p></details></td>"
            f'<td role="cell" class="n dpr">{sum(f["rows"] for f in bills):,}<span class="dpu"> bills</span></td>'
            f'<td role="cell" class="n dps">{mb(sum(f["bytes"] for f in bills))}</td>'
            '<td role="cell" class="dpg"><span class="dpeach">Each term below</span></td></tr>'
            f'<tr role="row" class="dpterms"><td role="cell" colspan="5"><ul class="dptermgrid" '
            f'aria-label="Bills by term">{grid}</ul></td></tr>')
    if tables:
        rows.append(_row("bills.csv and the rest",
                         "The spreadsheets, as on the data page, with every date written YYYY-MM-DD "
                         "and a person column in the sponsor and legislator tables.",
                         "", f"{sum(t['rows'] for t in tables):,}", "rows",
                         mb(sum(t["bytes"] for t in tables)), "/data.html#downloads", "See them"))

    db_name = db["path"].rsplit("/", 1)[-1] if db else "granite-record.sqlite.xz"
    sections = {
        "files": (
            '<p>Everything is under <code>/data/</code>, beside the spreadsheets on '
            '<a href="/data.html">the data page</a>, and '
            '<a href="data/manifest.json">data/manifest.json</a> lists every file with its address, '
            "size and checksum. Start there: one request says what is here and how much. The bill "
            "files are compressed with gzip and the database with xz, which Python, R and the "
            "command line on Linux and macOS open with what they already have.</p>",
            '<div class="dptablewrap dpwide"><table class="dpdl" role="table">'
            '<thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">File</th>'
            '<th scope="col" role="columnheader">What it holds</th>'
            '<th scope="col" role="columnheader" class="n">Rows</th>'
            '<th scope="col" role="columnheader" class="n">Size</th>'
            '<th scope="col" role="columnheader"><span class="sr">Download</span></th></tr></thead>'
            f'<tbody role="rowgroup">{"".join(rows)}</tbody></table></div>'),
        "start": (
            "<p>Every bill of the current term: download its file, then read it a line at a "
            "time, here in Python with nothing to install.</p>"
            + _code("An example on the command line",
                    f"curl -O https://graniterecord.org/data/bills-{newest}.jsonl.gz")
            + _code("An example in Python",
                    "import gzip, json\n"
                    f'with gzip.open("bills-{newest}.jsonl.gz") as lines:\n'
                    "    for line in lines:\n"
                    "        bill = json.loads(line)\n"
                    '        print(bill["key"], bill["title"])')
            + "<p>Or the whole database, in the <code>sqlite3</code> program:</p>"
            + _code("An example on the command line",
                    f"curl -O https://graniterecord.org/data/{db_name}\n"
                    f"xz -d {db_name}\n"
                    f'sqlite3 {db_name[:-3]} "SELECT term, COUNT(*) FROM bills GROUP BY term"')
            + "<p>A page on another site may read the manifest and the spreadsheets from a "
            "reader&rsquo;s browser too: each is served to any origin.</p>", ""),
        "keys": (
            "<p><b>A bill is its term and its number.</b> HB 100 names a different bill in every "
            "term, so every file writes a bill as <code>2025-2026/HB1442</code>, or as a "
            "<code>term</code> and a <code>bill</code> side by side.</p>"
            "<p><b>A person is a <code>person</code>.</b> The General Court numbers a member in two "
            "ways, an employee number and a person id, and this site&rsquo;s files use both; one "
            "person can carry several of each. <code>people.json</code> joins them to one "
            "<code>person</code>, which does not change when a member moves between the House and "
            "the Senate. It is one of the General Court&rsquo;s own numbers for them: their "
            "earliest person id, or their earliest employee number where the record gives no "
            "person id.</p>"
            '<details class="dpfold"><summary><span>When two entries prove to be one person, or one '
            "is two</span></summary><p>A <code>person</code> is never given to anyone else. If two "
            "entries prove to be one person, the one that goes stays in the file with a "
            "<code>replaced_by</code> line, so a program that stored it can still find them. If one "
            "proves to be two people, it keeps its number and the other gets a new one, marked "
            "<code>split_from</code>. A number not yet issued is marked <code>provisional</code> and "
            "may still change.</p></details>"
            '<details class="dpfold"><summary><span>A blank field is usually an answer</span>'
            "</summary><p>The record leaves it empty, the document that would fill it has not been "
            "collected, or this site does not read it yet. The data page&rsquo;s coverage table "
            "counts how far each column reaches in each term.</p></details>", ""),
        "changes": (
            "<p><code>/changes/&lt;date&gt;.json</code> is what each night&rsquo;s build found new, "
            "kept for the last eight nights: the hearings, votes and actions each bill, member, "
            "committee and topic gained. With the checksums in <code>manifest.json</code>, another "
            "site can fetch only the files that moved.</p>", ""),
        "live": (
            "<p>On a day the House or the Senate sits, <code>/api/live/votes/&lt;date&gt;</code> "
            "holds the roll calls recorded so far that day. The nightly files above take the day in "
            "the next morning.</p>"
            '<p class="dpnote">What is live on the General Court&rsquo;s video streams is not part of '
            "the API. Each bill&rsquo;s page links its recording.</p>", ""),
        "coverage": (
            "<p>The General Court publishes its record as a database. Every table of it this site "
            "reads, and where each lands here, is in <code>manifest.json</code> under "
            "<code>sources</code>, and below.</p>"
            '<dl class="repo">' + "".join(
                f"<dt>{E(s['source'])}</dt><dd>{E(s['lands'])}</dd>"
                for s in manifest.get("sources") or []) + "</dl>", ""),
        "stability": (
            "<p>Every JSON file carries <code>&quot;format&quot;: 1</code>. Until February 1, 2027 "
            "the API is a beta, and a field may be renamed or removed; each such change is listed "
            "here and in <code>manifest.json</code> a week before it is made. From February 1, "
            "changes only add: a new file, a new field, a new column at the end. A change that "
            "cannot be made by adding becomes a new file beside the old one, and both are published "
            "for a year. <code>schema.json</code> marks what the promise covers.</p>", ""),
        "using": (
            "<p>The record is the State of New Hampshire&rsquo;s and is public. What this site adds "
            "&mdash; its ids, its joins and its corrections &mdash; is dedicated to the public "
            "domain under CC0: use it for anything, with no need to ask. The plain-English "
            "histories are this site&rsquo;s writing, offered under the MIT License like the code "
            "that builds all of it. A link back to graniterecord.org helps somebody check your "
            "working.</p>"
            '<p class="dpnote">Found something that looks wrong, or a shape that is awkward to use? '
            "Each bill&rsquo;s page has a <i>Report a problem</i> button, or write to "
            "contact@graniterecord.org.</p>", ""),
    }
    onp = "".join(f'<li><a href="/api.html#{sid}">{title}</a></li>' for sid, title in SECTIONS)
    secs = "".join(
        f'\n  <section class="dpsec" id="{sid}" aria-labelledby="{sid}-h">'
        f'\n    <h2 class="dpsech" id="{sid}-h">{title}</h2>'
        f'\n    <div class="dpsecb">{sections[sid][0]}</div>{sections[sid][1]}\n  </section>'
        for sid, title in SECTIONS)
    return (
        '<div class="datapage">\n  <header class="dphead">\n    <h1>The Data API</h1>'
        '\n    <p class="dplead">The whole record behind this site, as files a program can read: '
        "every bill of every term with its full history, every roll call and every member&rsquo;s "
        "vote, the committee reports and their reasoning, and one list joining every number the "
        "General Court uses for a person. No key, no account and no limit to ask about: they are "
        "plain files, rebuilt every night.</p>"
        '\n    <p class="dpnote"><b>A beta until February 1, 2027.</b> Until then a file or a field '
        "may still change, and every change is announced in <code>manifest.json</code> a week "
        "before it is made. From then on, changes only add things.</p>"
        '\n    <details class="dponp"><summary>On this page</summary><nav class="dponpb" '
        f'aria-label="On this page"><ol>{onp}</ol></nav></details>\n  </header>{secs}\n</div>')


def write(site, manifest, base):
    tmpl = shell.template(site)
    page = shell.page(tmpl, path="/api.html", base=base,
                      title="The data API | Granite Record", og_title="The data API",
                      description=("The New Hampshire General Court's record as files a program "
                                   "can read: every bill, vote, sponsor, committee report and "
                                   "hearing, rebuilt every night."),
                      globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the files",
                      sr_title="", nav_current="data.html")
    page = page.replace('<div id="results"></div>', f'<div id="results">{body(manifest)}</div>', 1)
    # NOT INDEXED WHILE UNLINKED: a search engine is not to find a page the
    # site does not link yet. Taken off, with a sitemap line, on the day it is
    # announced.
    page = page.replace('<link rel="canonical"', ROBOTS + '\n<link rel="canonical"', 1)
    assert ROBOTS in page, "api.html: the template has no canonical link to put noindex before"
    (site / "api.html").write_text(shell.clean_links(page), encoding="utf-8")
    print(f"  {'api.html':<28} the API, described (not linked until the announcement)")
