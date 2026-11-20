#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.5
"""
preflight's checks of towns, districts and the map.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

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

from pf_core import (_run, _sealed_run, _source, check, imp)
from pf_fixture import (_fixture_site_shared)
from pf_runner import (REMINDERS)
from pf_shared import (_cite_plain, _css_rules, _map_data, _map_totals_run, _map_totals_text,
                       _mk, _officials_now)


@check("build", "a town page's Officials tab is two columns: the elected on the left, and on the right the "
       "offices, the clerk and the staff and administrative positions, in that order",
       needs=("build_town_pages",))
def _town_officials_columns(B):
    """The owner, 10 November 2026: "City offices go to the top right of the
    officials tab on town pages with clerk below it, elected officials on the
    left, town staff and administrative positions on the right." NHDOT's rows
    carry a position and no word for elected or not, so the rule is the one
    the tab already drew: the select board and the mayor and council, the
    bodies that govern, are the elected and go left; every other row of the
    directory is staff or administration and goes right, under the offices'
    own card (where to write, how to reach them) and the Secretary of State's
    clerk. One column on a phone, in the same order from the top: the elected,
    the offices, the clerk, the staff (the tab's grid is app.css's .twncols)."""
    import shell as S
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    off = {"_offices": {"lyme": {"officials": [
               {"position": "Board of Selectman", "name": "Ben Kilham", "phone": "", "email": ""},
               {"position": "Town Administrator", "name": "Dina Cutting", "phone": "", "email": ""},
               {"position": "Road Agent", "name": "Roy Agent", "phone": "", "email": ""}],
           "website": "www.lymenh.gov", "mailing": "PO Box 126, Lyme, NH 03768"}},
           "_local": {"lyme": {"clerk": "Emily Shepard", "phone": "603-795-2535"}}}
    dist = {"house": [{"county": "Grafton", "district": "12"}], "senate": "5"}
    page = B.build("Lyme", "0", {"0": {}}, dist, [], off, "https://x.test", S.template())
    pane = page[page.index('id="officials" role="tabpanel"'):]
    pane = pane[:pane.index('id="vote" role="tabpanel"')]
    cols = re.findall(r'<div class="twncol">(.*?)</div>(?=<div class="twncol">|</div></div></div>)', pane, re.S)
    assert 'class="twncols twnwide"' in pane and len(cols) == 2, (
        f"the Officials tab is not two columns: {len(cols)} found")
    heads = [re.findall(r'<h3 class="twnh">(.*?)</h3>', c) for c in cols]
    assert heads == [["Select board"],
                     ["Town offices", "Town clerk", "Staff and administrative positions"]], (
        f"the columns hold {heads}, not the select board on the left and the offices, the clerk "
        "and the staff on the right")
    assert "Roy Agent" in cols[1] and "Dina Cutting" in cols[1] and "Ben Kilham" in cols[0] \
        and "Ben Kilham" not in cols[1], "a position is in the wrong column"
    assert "PO Box 126" in cols[1].split("Town clerk")[0], "the offices' card does not lead the right column"
    # The tab in the page's own order is the phone's: elected, offices, clerk, staff.
    order = [pane.index(x) for x in ("Select board", "Town offices", "Town clerk", "Staff and administrative")]
    assert order == sorted(order), f"the cards are not in the order the phone shows them: {order}"
    css = " ".join(_source("src/pages/app.css").split())
    assert ".twncols{display:grid;grid-template-columns:minmax(0,1fr)" in css and (
        "@media (min-width:68.75em){ .twncols{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}" in css), (
        "app.css does not lay the columns side by side on a wide screen and stack them below it")
    # With cards in one column only, the tab is as it was: two abreast, no wrapper.
    only = B.in_columns([B.card("Town clerk", "<p>x</p>", side="r")])
    assert 'twncols' not in only[0] and 'twn-r' in only[0], "one column's cards are wrapped"
    return "ok", "select board left; offices, clerk and staff right; one column, in that order, below 1100px"


@check("build", "a town or a ward page names its own record for Report a problem, and the Function and "
       "the compiler both take it from that page's address and no other",
       needs=("build_town_pages", "compile_reports"))
def _town_report(B, CR):
    """The owner, 10 November 2026: "Add report a problem to town pages". A
    town page (a ward's too) carries window.GR_REPORT = "town:<slug>", which
    app.js mounts as the Report box alone, no Share; report.js takes the
    record from /town/<slug> and compile_reports reads it back to the same
    address. (functions/api/report.js is run on it in _report_function, and
    on every built town page in _report_pages.)"""
    import shell as S
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    dist = {"house": [{"county": "Grafton", "district": "11"}], "senate": "5"}
    for town, ward, wards, slug in (("Lyme", "0", {"0": {}}, "lyme"),
                                    ("Concord", "4", {"1": {}, "4": {}}, "concord-ward-4")):
        page = B.build(town, ward, wards, dist, [], {}, "https://x.test", S.template())
        assert f'window.GR_REPORT="town:{slug}";' in page, f"{town}'s page does not name its record town:{slug}"
        assert f'href="https://x.test/town/{slug}"' in page, f"{town}'s page is not at /town/{slug}"
        rec = f"town:{slug}"
        assert CR.RECORD.match(rec) and CR.PATH.match(f"/town/{slug}"), f"the compiler refuses {rec}"
        assert CR.page_of(rec, {}) == f"/town/{slug}", f"the compiler finds {rec}'s page at {CR.page_of(rec, {})}"
        stored = {"id": 5, "at": "2026-11-10T12:00:00.000Z", "record": rec, "kind": "town",
                  "url": f"/town/{slug}", "tab": "", "field": "other",
                  "note": "The clerk's hours are wrong.", "build": "", "hidden": 0}
        assert CR.well_formed(stored), f"a stored report from {rec} is set aside as malformed"
        assert CR.producer(rec, "other") == "build_town_pages.py", "the producer of a town's page is not named"
    app = _source("src/pages/app.js")
    assert 'rec.slice(0,at)!=="town"&&!document.querySelector("#pageacts [data-share]")' in app, (
        "app.js no longer mounts a town's Report box without a Share beside it")
    return "ok", "town:lyme and town:concord-ward-4 named by their pages, kept and compiled from /town/<slug>"


@check("build", "Cite this page sits under a town's line, as a guide's does, not alone above the "
                "town's name", needs=("build_town_pages",))
def _cite_under_a_towns_line(B):
    """The audit of 25 October 2026 (S9), approved by the owner: on town and
    calendar pages a lone "Cite this page" sat above the title. Above a
    record's heading it is one of a row of actions; on a town's page there is
    no row, only the button over the name. It goes under the lede, set to the
    left with its pane, as a guide's does, and is written once, naming the
    page as shell.page named it. (The Calendar's weeks and its list of
    documents: _calendar_documents, which builds them.)"""
    import shell as S
    if not Path("src/pages/bills.html").exists():
        return "skip", "bills.html is not here"
    dist = {"house": [{"county": "Grafton", "district": "11"}], "senate": "5"}
    page = B.build("Lyme", "0", {"0": {}}, dist, [], {}, "https://x.test", S.template())
    at = {k: page.find(v) for k, v in (
        ("results", '<div id="results">'), ("h1", '<h1 class="offtitle">Lyme</h1>'),
        ("lede", '<p class="lead twnlede">'), ("row", '<div class="pageacts" id="pageacts">'),
        ("tabs", 'class="twntabs'))}
    assert min(at.values()) >= 0, f"the town page lost a part this reads: {at}"
    assert page.count('class="pcite"') == 1, "Cite this page is drawn twice, or not at all"
    assert at["results"] < at["h1"] < at["lede"] < at["row"] < at["tabs"], (
        f"Cite this page is not under the town's line and above its tabs: {at}")
    # read without shell.cite_url's <wbr>s, which are no characters
    row = _cite_plain(page[at["row"]:at["tabs"]])
    assert "https://x.test/town/lyme" in row and "Who represents Lyme, New Hampshire" in row, (
        "the citation does not name the town's page as shell.page named it")
    # Whole selectors: the list inside :is() has commas of its own.
    css = {" ".join(sel.split()) for _, sel, body, _ in _css_rules(
        _source("src/pages/app.css"))
        if "justify-content:flex-start" in body.replace(" ", "")}
    assert ":is(.officials,.calhead,.cdpage) > .pageacts" in css, (
        "the row under a town's or the Calendar's line is not set to the left, under the words")
    return "ok", "once, under the town's line and above its tabs, to the left, naming the page"


# THE ADDRESS BOX'S SUGGESTIONS (the person, 24 October 2026: "I'd like to
# make some improvements to the address search so that it shows you a
# dropdown of matching addresses around New Hampshire as you're typing with
# the zip codes"). find.js's matcher over files read from disk: the real
# ones for _addr_streets, the fixture's for _addr_suggest.
_ADDR_FIND = r"""
require("./stub.js");
const fs = require("fs"), vm = require("vm");
vm.runInThisContext(fs.readFileSync("./find.js", "utf8"), {filename: "find.js"});
const F = vm.runInThisContext("({yaQuery, yaSuggest})");
const out = {};
for (const s of JSON.parse(fs.readFileSync("./queries.json", "utf8"))) {
  const q = F.yaQuery(s);
  let file = null;
  try { file = JSON.parse(fs.readFileSync("./addr/" + q.key + ".json", "utf8")); } catch (e) {}
  out[s] = {key: q && q.key, got: file ? F.yaSuggest(file, q, 8).map(c => c.label) : null};
}
process.stdout.write("\n@@" + JSON.stringify(out));
"""

# The address box itself: find.js's combobox in node, against dom_stub.js,
# with elements that keep their attributes, a fetch that records what it was
# asked and answers from the fixture's files (or 404s, or fails), and a
# createElement that counts the script tags anything makes.
_ADDR_COMBO = r"""
require("./stub.js");
const fs = require("fs"), vm = require("vm");
const FILES = JSON.parse(fs.readFileSync("./files.json", "utf8"));
const asked = [], scripts = [];
let mode = "ok";
globalThis.fetch = async u => {
  asked.push(String(u));
  if (mode === "down") throw new Error("offline");
  const m = /^\/addr\/([a-z0-9]{2})\.json$/.exec(u), f = m && FILES[m[1]];
  if (mode === "404" || !f) return {ok: false, status: 404, json: async () => { throw new Error("html"); }};
  return {ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(f))};
};
const create = document.createElement.bind(document);
document.createElement = t => { if (String(t).toLowerCase() === "script") scripts.push(t); return create(t); };
let F;
try { vm.runInThisContext(fs.readFileSync("./find.js", "utf8"), {filename: "find.js"});
      F = vm.runInThisContext("({yaCombo, yaFile, YA})"); }
catch (e) { console.log("LOAD " + e.message); process.exit(1); }
scripts.length = 0;
function kept(id) {
  const e = document.createElement("div"), at = {};
  e.id = id;
  e.setAttribute = (k, v) => { at[k] = String(v); };
  e.getAttribute = k => (k in at ? at[k] : null);
  e.removeAttribute = k => { delete at[k]; };
  return e;
}
const inp = kept("ytaddr"), list = kept("ytalist"), say = kept("ytasay");
list.hidden = true;
const picked = [];
F.yaCombo(inp, list, say, c => picked.push(c.label));
const ticks = async () => { for (let i = 0; i < 20; i++) await new Promise(r => setImmediate(r)); };
const key = k => { const e = {key: k, prevented: 0, stopped: 0, preventDefault() { this.prevented++; },
  stopPropagation() { this.stopped++; }}; (inp._on.keydown || []).forEach(f => f(e)); return e; };
const type = async v => { inp.value = v; inp.fire("input"); await ticks(); };
const snap = () => ({expanded: inp.getAttribute("aria-expanded"), active: inp.getAttribute("aria-activedescendant"),
  hidden: list.hidden, html: list.innerHTML, say: say.textContent, value: inp.value,
  options: (list.innerHTML.match(/role="option"/g) || []).length});
const forget = () => { for (const k of Object.keys(F.YA.files)) delete F.YA.files[k]; };
const out = {};
(async () => {
  await type("107");
  out.pending = {asked: asked.length, ...snap()};
  await type("107 n main");
  out.typed = snap();
  const d1 = key("ArrowDown"); out.down1 = {...snap(), prevented: d1.prevented};
  key("ArrowDown"); out.down2 = snap();
  key("ArrowDown"); out.down3 = snap();
  key("ArrowUp"); out.up = snap();
  const en = key("Enter"); out.enter = {...snap(), prevented: en.prevented, picked: picked.slice()};
  await type("107 north main st conc");
  out.north = snap();
  const e1 = key("Escape"); out.escape = {...snap(), stopped: e1.stopped};
  const e2 = key("Escape"); out.escapeShut = {stopped: e2.stopped};
  await type("107 n main"); inp.fire("blur"); out.blur = snap();
  await type("107 n main"); key("Tab"); out.tab = snap();
  await type("107 n main");
  const ev = {target: {closest: () => ({getAttribute: () => "1"})}, stopped: 0, stopPropagation() { this.stopped++; }};
  (list._on.click || []).forEach(f => f(ev));
  out.click = {...snap(), stopped: ev.stopped, picked: picked.slice()};
  const plain = key("Enter"); out.enterShut = {prevented: plain.prevented};
  forget(); mode = "404"; await type("107 n main"); out.missing = snap();
  forget(); mode = "down"; await type("50 battle st"); out.down = snap();
  mode = "ok"; forget();
  const before = asked.length;
  out.bad = [await F.yaFile("a/"), await F.yaFile(".."), await F.yaFile("A1"), await F.yaFile("")];
  out.badAsked = asked.length - before;
  out.asked = asked; out.scripts = scripts.length;
  process.stdout.write("\n@@" + JSON.stringify(out));
})().catch(e => { console.log("RUN " + e.message); process.exit(1); });
"""


def _addr_node(script, files):
    """Run one of the two harnesses in a folder of its own: find.js, the
    stub, and `files` ({name: text}). Returns what it printed after @@."""
    node = shutil.which("node") or shutil.which("node.exe")
    root = Path(tempfile.mkdtemp())
    try:
        (root / "find.js").write_text(_source(_paths.locate("src/pages/find.js")),
                                      encoding="utf-8")
        (root / "stub.js").write_text(_source("tests/dom_stub.js"),
                                      encoding="utf-8")
        for name, text in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_text(text, encoding="utf-8")
        (root / "go.js").write_text(script, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=120)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "find.js's address box did not run under node: " + (r.stderr or r.stdout or "")[-400:])
        return json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)


@check("frontend", "the address box's street files: their shape, New Hampshire's real streets "
                   "with their ZIP codes, and find.js finding them as a reader types them")
def _addr_streets():
    """The files build_addr_index.py writes from collected/nh_streets.json,
    which git carries, so this runs wherever the code does.

    THE SHAPE. Every file is named by its key, two letters or digits, and
    says so; its towns are a sorted list and every row names one of them; a
    ZIP code is five digits; the house numbers are runs, low to high, each of
    one parity; and every row is in the file because one of its forms -- its
    name, or a form it carries -- begins with that file's key, which is the
    rule find.js reads a file by. A few hundred files, none large: a phone
    fetches one as its reader types.

    REAL STREETS, each asked of the Census geocoder on 24 October 2026 and
    matched where this says. 107 North Main Street is the State House, Concord, 03301 (Ward 4).
    50 Battle Street is Webster on Concord's ZIP, 03303: the town is the
    municipality's, not the post office's. Willow Street in Manchester is
    03101 on its odd side and 03103 on its even, so 600 and 601 are offered
    with different ZIP codes. 1050 State Route 118 is Dorchester, a road of
    rural numbers. 100 Elm Street, Manchester, and 45 Lake Street, Nashua,
    are ward cities; Hale's Location is an unorganized place, named with
    what it is.

    AND FIND.JS FINDS THEM, as typed: each query's first suggestion is the
    one the Census matched, so the build's keys and the browser's matching
    are held to each other on the real list.

    WITHOUT THE LIST the step says so, removes any earlier files and writes
    none, and a build goes on: the box then offers nothing and works as it
    did before.
    """
    src = Path("collected/nh_streets.json")
    node = shutil.which("node") or shutil.which("node.exe")
    script = _paths.locate("build_addr_index.py")
    if not (src.exists() and node and script.exists() and Path("tests/dom_stub.js").exists()):
        return "skip", "collected/nh_streets.json, build_addr_index.py, dom_stub.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        # Sealed, as the pipeline's steps are run here: the step asks no network.
        r = _sealed_run([sys.executable, str(script), "--site", str(root / "site"), "--src", str(src)],
                        capture_output=True, text=True, timeout=180)
        assert r.returncode == 0, "build_addr_index.py failed: " + (r.stderr or r.stdout)[-300:]
        addr = root / "site" / "addr"
        files = sorted(addr.glob("*.json"))
        assert 200 <= len(files) <= 700, (
            f"{len(files)} files of street suggestions; about 350 were written on 24 October 2026, "
            "and a count far from that is a key gone wrong")
        sizes = sorted(p.stat().st_size for p in files)
        assert sizes[-1] < 100_000 and sum(sizes) < 4_000_000, (
            f"the largest file is {sizes[-1]:,} bytes and all {sum(sizes):,}: a phone fetches one "
            "as its reader types")
        import build_addr_index as BA
        rows = {}
        for p in files:
            d = json.loads(p.read_text(encoding="utf-8"))
            k = p.stem
            assert re.fullmatch(r"[a-z0-9]{2}", k) and d["k"] == k, f"{p.name} says it is {d.get('k')!r}"
            t = d["t"]
            assert t == sorted(set(t)) and all(isinstance(x, str) and x for x in t), \
                f"{p.name}: its towns are not a sorted list of names"
            for row in d["r"]:
                name, ti, zp, runs = row[:4]
                forms = row[4] if len(row) > 4 else []
                assert isinstance(name, str) and 0 <= ti < len(t), f"{p.name}: {row}"
                assert re.fullmatch(r"(\d{5})?", zp), f"{p.name}: {name} has the ZIP {zp!r}"
                assert len(runs) % 2 == 0 and all(
                    runs[i] <= runs[i + 1] and runs[i] % 2 == runs[i + 1] % 2
                    for i in range(0, len(runs), 2)), f"{p.name}: {name}'s numbers {runs}"
                assert all(BA.key(f) == k for f in forms) and (
                    BA.key(BA.norm(name).replace(" ", "")) == k or forms), (
                    f"{p.name}: {name} is in a file none of its forms begins with")
                rows.setdefault((name, t[ti], zp), []).append((k, runs))

        def has(name, town, zp, n):
            got = rows.get((name, town, zp))
            assert got, f"{name}, {town} {zp} is in none of the files"
            runs = got[0][1]
            return any(runs[i] <= n <= runs[i + 1] and (n - runs[i]) % 2 == 0
                       for i in range(0, len(runs), 2))
        for name, town, zp, n in (("N Main St", "Concord", "03301", 107),
                                  ("Battle St", "Webster", "03303", 50),
                                  ("Willow St", "Manchester", "03101", 601),
                                  ("Willow St", "Manchester", "03103", 600),
                                  ("State Rte 118", "Dorchester", "03266", 1050),
                                  ("Elm St", "Manchester", "03101", 100),
                                  ("Lake St", "Nashua", "03060", 45)):
            assert has(name, town, zp, n), f"{n} {name}, {town} {zp} is not in its street's numbers"
        assert not has("Willow St", "Manchester", "03101", 600), \
            "Willow Street's even side is 03103 and its odd 03101: the parity is not kept"
        assert {k for k, _ in rows[("N Main St", "Concord", "03301")]} >= {"nm", "no", "ma"}, \
            "N Main St is not in the files of n main, north main and main"
        assert any(t == "Hale's Location" for _, t, _ in rows), \
            "Hale's Location is not named with what it is"

        want = {"107 north main st conc": "107 N Main St, Concord, NH 03301",
                "107 n main st, concord": "107 N Main St, Concord, NH 03301",
                "50 battle st": "50 Battle St, Webster, NH 03303",
                "601 willow st manch": "601 Willow St, Manchester, NH 03101",
                "600 willow st manch": "600 Willow St, Manchester, NH 03103",
                "1050 route 118 dorch": "1050 State Rte 118, Dorchester, NH 03266",
                "100 elm st manch": "100 Elm St, Manchester, NH 03101",
                "45 lake st nash": "45 Lake St, Nashua, NH 03060",
                "20 boulder ridge rd hale": "20 Boulder Ridge Rd, Hale's Location, NH 03860",
                "bickford woods rd": "Bickford Woods Rd, Dorchester, NH 03266"}
        shards = {f"addr/{p.name}": p.read_text(encoding="utf-8") for p in files}
        got = _addr_node(_ADDR_FIND, {"queries.json": json.dumps(list(want)), **shards})
        bad = [f"{q!r} first offers {(g['got'] or ['nothing'])[0]!r}, not {w!r}"
               for q, w in want.items() for g in [got[q]] if not g["got"] or g["got"][0] != w]
        assert not bad, "find.js does not offer what the Census matched: " + "; ".join(bad)

        # Without the list: a warning, the earlier files gone, and the build goes on.
        (root / "old" / "addr").mkdir(parents=True)
        (root / "old" / "addr" / "zz.json").write_text("{}", encoding="utf-8")
        r = _sealed_run([sys.executable, str(script), "--site", str(root / "old"),
                         "--src", str(root / "none.json")], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "WARNING" in r.stdout and not (root / "old" / "addr").exists(), (
            "build_addr_index.py without its list did not warn, stop the build, or remove the "
            "earlier files: " + (r.stdout + r.stderr)[-300:])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert '["build_addr_index.py", "--site", "site"]' in _source(_paths.locate("build_all.py")), "build_all.py no longer runs build_addr_index.py"
    return "ok", (f"{len(files)} files, the largest {sizes[-1] / 1e3:.0f} KB; {len(want)} real "
                  "addresses each offered first as the Census matched it, parity choosing "
                  "Willow Street's ZIP; without the list a warning and no files")


@check("frontend", "the address box is a combobox, asks nothing but this site's own files while "
                   "the reader types, and works as before when a file does not load")
def _addr_suggest():
    """find.js's yaCombo, run in node against dom_stub.js, over files
    build_addr_index.shards() makes from a fixture of three streets.

    THE COMBOBOX (WAI-ARIA's pattern, with a listbox). A house number alone
    asks for nothing. "107 n main" opens the list: aria-expanded true and a
    status line saying how many. ArrowDown and ArrowUp move through it,
    wrapping, with aria-activedescendant naming the option and the option
    aria-selected; Enter takes it, fills the box and closes the list, and so
    does a tap, which goes no further than the list (the document's handler
    took a tap on an option that had just been redrawn away as a tap outside
    the panel, and shut it: the browser test of 24 October 2026). Escape
    closes the list and stops there; with the list closed it is the panel's
    again. Leaving the box, or Tab, closes it, and Enter with no option
    chosen is the form's, as it was.

    NOTHING BUT THIS SITE WHILE TYPING. Every request is /addr/<two letters
    or digits>.json, a key of anything else asks nothing, and no script tag
    is made -- the Census's JSONP is a script tag, and it is made only by
    ytGeocode, which typing never reaches. The markup carries the roles and
    the privacy line says where the address goes.

    A FILE THAT DOES NOT LOAD -- a 404, the network down -- is no list and no
    error, and Look up is the form's submit, which no suggestion gates.
    """
    js = _paths.locate("src/pages/find.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and node and Path("tests/dom_stub.js").exists()):
        return "skip", "find.js, dom_stub.js or node is not here"
    import build_addr_index as BA
    files = BA.shards([["N Main St", "Concord", "03301", "1-299 2-298"],
                       ["N Main St", "Laconia", "03246", "601-1199 600-1444"],
                       ["Battle St", "Webster", "03303", "1-1699 2-1698"]])
    assert {"nm", "no", "ma", "ba"} <= set(files), f"the fixture's files are {sorted(files)}"
    got = _addr_node(_ADDR_COMBO, {"files.json": json.dumps(files)})
    p = got["pending"]
    assert p["asked"] == 0 and p["expanded"] != "true", f"a house number alone asked for a file: {p}"
    t = got["typed"]
    assert t["expanded"] == "true" and not t["hidden"] and t["options"] == 2 \
        and "107 N Main St, Concord, NH 03301" in t["html"] and t["say"] == "2 addresses suggested", (
        f"typing 107 n main did not open a list of the two North Main Streets: {t}")
    assert t["html"].index("Concord") < t["html"].index("Laconia"), \
        "the number in range (Concord's 1-299) is not offered before the one out of it (Laconia's)"
    seq = [got[k]["active"] for k in ("down1", "down2", "down3", "up")]
    assert seq == ["ytalist-0", "ytalist-1", "ytalist-0", "ytalist-1"] and got["down1"]["prevented"], (
        f"the arrow keys moved aria-activedescendant {seq}, not 0, 1, 0 (wrapping), 1")
    assert 'id="ytalist-1" data-i="1" aria-selected="true"' in got["up"]["html"], \
        "the option the arrow keys are on is not aria-selected"
    e = got["enter"]
    assert e["prevented"] and e["picked"] == ["107 N Main St, Laconia, NH 03246"] \
        and e["value"] == e["picked"][0] and e["expanded"] == "false" and e["hidden"] \
        and e["active"] is None, f"Enter on an option: {e}"
    assert got["north"]["options"] == 1, f"107 north main st conc: {got['north']}"
    assert got["escape"]["stopped"] == 1 and got["escape"]["hidden"] and got["escape"]["say"] == "" \
        and got["escapeShut"]["stopped"] == 0, (
        "Escape with the list open closes the list and stops there, and with it closed is the "
        f"panel's: {got['escape']}, {got['escapeShut']}")
    assert got["blur"]["hidden"] and got["tab"]["hidden"], "leaving the box, or Tab, left the list open"
    c = got["click"]
    assert c["stopped"] == 1 and c["picked"][-1] == "107 N Main St, Laconia, NH 03246" and c["hidden"], (
        f"a tap on an option: {c} -- it must take the option and go no further, or the document "
        "shuts the panel")
    assert got["enterShut"]["prevented"] == 0, "Enter with no option chosen no longer submits the form"
    for k in ("missing", "down"):
        m = got[k]
        assert m["expanded"] == "false" and m["options"] == 0 and m["hidden"], \
            f"a file that does not load ({k}) still drew a list: {m}"
    assert got["bad"] == [None] * 4 and got["badAsked"] == 0, \
        "a key that is not two letters or digits asked for a file"
    stray = [u for u in got["asked"] if not re.fullmatch(r"/addr/[a-z0-9]{2}\.json", u)]
    assert not stray and got["scripts"] == 0, (
        f"while the reader typed, find.js asked for {stray} and made {got['scripts']} script tags: "
        "only this site's own files may be asked for until an address is chosen")
    src = _source(js)
    part = src[src.index("const YA={"):src.index("function ytRows(")]
    assert not re.search(r"https?://", part), "the suggestions' code names another server"
    assert part.count("fetch(") == 1 and 'fetch("/addr/"+k+".json")' in part, \
        "the suggestions fetch something other than /addr/<key>.json"
    draw = src[src.index("function ytDraw("):src.index("function ytLook(")]
    for need in ('role="combobox"', 'aria-autocomplete="list"', 'aria-controls="ytalist"',
                 'role="listbox"', 'id="ytasay" role="status"',
                 'f.addEventListener("submit",e=>{e.preventDefault();ytLook(box,res);});'):
        assert need in draw, f"the address box's markup or its form lost {need}"
    assert "matched in your browser" in draw and "US Census Bureau" in draw, \
        "the privacy line no longer says where the suggestions and the address go"
    # WHAT THIS SITE CAN KNOW OF THE ADDRESS (the person, 25 October 2026: "I
    # approve the privacy text update"). The line said the address "is not
    # kept anywhere", a claim about the Census Bureau's servers nobody here
    # can know. It says what ytGeocode does -- the address goes from the
    # browser to the Census and never reaches this site -- in English and in
    # its Spanish, and the Data page's Privacy in Detail, which said nothing
    # of the address box, says where the street's two letters and the
    # address go.
    line = re.search(r'tr\("yt\.addr_privacy","([^"]*)"\)', draw)
    assert line, "the address box has no privacy line"
    assert "never reaches this site" in line.group(1) and "kept anywhere" not in line.group(1), (
        "the privacy line does not say the address never reaches this site, or claims again that "
        f"it is not kept anywhere: {line.group(1)!r}")
    import i18n
    es = i18n.catalog("es")["strings"]["yt.addr_privacy"]["es"]
    assert "nunca llega a este sitio" in es and "ningún lugar" not in es, (
        f"the privacy line's Spanish does not say what the English now says: {es!r}")
    assert "geocoding.geo.census.gov/" in src and 'fetch("/addr/"+k+".json")' in part, (
        "the address no longer goes to the Census's geocoder, or the street list is no longer this "
        "site's own: the words below describe what it did")
    import build_exports as BE
    detail = " ".join(BE.PRIVACY.split())
    for need in ("<i>Your town</i>", "first two letters", "so this site sees only those two letters",
                 "your browser sends the address to the US Census Bureau&rsquo;s address lookup",
                 "this site does not", "only in your browser"):
        assert need in detail, (
            f"the Data page's Privacy in Detail does not say of the address box {need!r}")
    assert "kept anywhere" not in detail, "the Data page claims what the Census Bureau keeps"
    return "ok", ("a combobox by the arrow keys, Enter, Escape and a tap; only /addr/<key>.json "
                  "asked while typing; a 404 or the network down is no list and no error; and the "
                  "privacy line, its Spanish and the Data page say the address goes to the Census "
                  "and never to this site")


@check("frontend", "a town page carries the district map in a tab of its own, second, framed on "
                   "the town with its own State House district chosen")
def _town_page_map():
    """Polish 3: "The map also goes on the town pages" (the approved drawing,
    private/design/polish/proto/town-dover-ward-1.html). Read off the
    fixture's built town pages: every one has a District Map tab, second,
    after Representatives; its panel holds the map's mount, named for the
    town, a ward's page for its ward; the map's script comes after the tabs'
    switching script, so the map is mounted the first time its tab is shown.
    And map_section names the town's own State House district, never its
    floterial, by the map's code ("ST14" for Strafford 14)."""
    import build_town_pages as BT
    shared, _base, _ran, _days = _fixture_site_shared()
    pages = sorted((shared / "site" / "town").glob("*.html"))
    if not pages:
        return "skip", "the fixture builds no town page"
    for f in pages:
        page = f.read_text(encoding="utf-8")
        tabs = re.findall(r'role="tab" id="tab-([a-z]+)"', page)
        assert tabs[:2] == ["representatives", "map"], f"{f.name}: the tabs are {tabs}"
        m = re.search(r'<div class="twnmap" id="twnmap" data-town="([^"]+)"([^>]*)></div>', page)
        assert m, f"{f.name}: the District Map tab holds no map"
        ward = re.search(r"-ward-(\d+)\.html$", f.name)
        assert (f'data-ward="{ward.group(1)}"' in m.group(2)) if ward else "data-ward" not in m.group(2), (
            f"{f.name}: the map is not told the page's ward: {m.group(0)}")
        assert BT.MAP_JS in page and page.index(BT.MAP_JS) > page.index(BT.TABS_JS), (
            f"{f.name}: the map's script is not after the tabs' switching script")
    got = "".join(BT.map_section("Dover", "4", {"house": [
        {"county": "Strafford", "district": "21", "floterial": True},
        {"county": "Strafford", "district": "14", "floterial": False}]}))
    assert 'data-town="Dover" data-ward="4" data-pick="ST14"' in got, (
        f"map_section does not choose the ward's own district: {got[:300]}")
    # No box of instructions between the heading and the map (the audit of 25
    # October 2026: on a phone the map began 470 to 540px below its heading).
    assert got.startswith('<section class="twnsec twnwide"><h3 class="twnh">The Map</h3>'
                          '<div class="twnmap" id="twnmap"'), (
        f"something stands between the Map tab's heading and the map: {got[:200]}")
    return "ok", (f"{len(pages)} town pages, each with the Map second, the map told its "
                  "town and ward and mounted after the tabs, straight under its heading; Dover "
                  "Ward 4 opens on Strafford 14")


@check("frontend", "an official's chip on a town page says the party in letters, as a "
                   "legislator's does", needs=("build_town_pages",))
def _official_party_letter(BT):
    """The Governor's, the Executive Councillors' and the federal
    delegation's chips on a town page carried their party by the colour of
    the bar alone (the survey of 7 October 2026), where a legislator's chip
    says "(R - Rock 16)". officials.json's own rows: Gov. Kelly Ayotte (R)
    and Rep. Chris Pappas (D); an office whose holder this site was not told
    shows no chip at all, and a party not given shows no letter."""
    gov = BT.office_block("Governor", {"name": "Kelly Ayotte", "party": "R",
                                       "official_url": "https://www.governor.nh.gov/"}, "")
    assert ('<span class="mchip p-R" translate="no"><a href="https://www.governor.nh.gov/" rel="noopener">'
            'Kelly Ayotte <span class="mtag">(R)</span></a></span>') in gov, gov
    us = BT.office_block("", {"name": "Chris Pappas", "party": "D"}, "")
    assert '<span class="mchip p-D" translate="no">Chris Pappas <span class="mtag">(D)</span></span>' in us, us
    none = BT.office_block("", {"name": "A. Person"}, "")
    assert '<span class="mchip p-X" translate="no">A. Person</span>' in none, none
    return "ok", "\"Kelly Ayotte (R)\", \"Chris Pappas (D)\"; no letter where no party is given"


@check("files", "no town official is published without a source or beyond a board's seats")
def _town_officials_sane():
    """A name against an office is a claim about a real person.

    town_officials_web.json is read off 145 towns' own pages, which are not
    built alike and are not built for this. Two things went wrong while it
    was being written and both would have published a falsehood quietly:

    An unrecognised heading let the office above it stay in force. Lyme
    spells one "Cemetary Trustees"; the Treasurer heading above it carried
    on, and three members of a board came out as the town's Treasurer.

    And a roster page that lists every body in sequence gave Bennington
    fifteen selectmen. RSA 41:8 has a town choose one selectman a year for a
    three-year term -- three, or five where a town has voted so -- and
    fifteen is a run that walked into the next body.

    So this checks what survived: every record carries where it came from and
    when, and no office holds more people than it can. Both are properties of
    the output, so they hold however the parser is rewritten.
    """
    if not Path("collected/town_officials_web.json").exists():
        return "skip", "no town_officials_web.json here"
    m = imp("parse_town_sites")
    if m is None:
        return "skip", "parse_town_sites.py does not import"
    data = json.loads(Path("collected/town_officials_web.json").read_text(encoding="utf-8"))

    import collections as _c
    bad, n = [], 0
    for key, v in sorted(data.items()):
        counts = _c.Counter()
        for r in v.get("officials", []):
            n += 1
            for f in ("name", "office", "source_url", "read_on", "method",
                      "status"):
                if not r.get(f):
                    bad.append(f"{key}: a record has no {f}: {r.get('name')!r}")
            if r.get("status") not in ("published", "not_published_by_source",
                                       "not_established"):
                bad.append(f"{key}: {r.get('name')!r} has status "
                           f"{r.get('status')!r}, which is not one of the three")
            counts[r.get("office")] += 1
            # A HEADING PUBLISHED AS A PERSON. The person, reviewing a sample
            # of these records, marked "New Business" wrong: it had been
            # published as Seabrook's Treasurer, off a selectmen page that
            # carries a meeting agenda. The screen that followed found
            # "Annual Report" as Groton's clerk, "New Page" as Hooksett's
            # council, and Bedford's breadcrumbs as its Town Clerk.
            #
            # This list is deliberately NOT the parser's own: a check built
            # from the parser's vocabulary can only agree with the parser.
            name = (r.get("name") or "").lower()
            if re.search(r"\b(business|report|page|officials?|agenda|minutes|"
                         r"meeting|list|pledge|committee|department|board|"
                         r"council|town|city)\b", name):
                bad.append(f"{key}: {r.get('name')!r} is published as a "
                           f"person holding {r.get('office')}")
        for office, c in counts.items():
            cap = m.SEATS.get(office, m.SEAT_MAX)
            if c > cap:
                bad.append(f"{key}: {c} people hold {office}, which seats {cap}")
    assert not bad, "\n  ".join(bad[:20])
    return "ok", (f"{n} officials across {len(data)} towns, each with a source "
                  f"and none beyond its office's seats")


@check("files", "a town's own select board or city council is published current, from one page, and labelled when partial")
def _town_boards_sane():
    """town_boards.json is what puts a town's own select board, and a city's
    own mayor and council, on its page in place of NHDOT's September 2025
    directory -- Lyme's page named a chair who is no longer on the board,
    and Dover's a mayor who left office in January. A body goes in only where
    its own page was current when read, and that is a property of the file,
    so it is checked on the file whatever town_boards.py becomes.

    WHOLE OR MARKED PARTIAL (the person, 24 September 2026). A board of three
    or five published whole has that many members and a source for the
    number. One that lists fewer is marked partial: with fewer members than
    a size that has a source, or with no size at all, never with more.

    The words below are deliberately NOT town_boards.py's screen: a check
    built from the screen's own vocabulary can only agree with it.
    """
    p = Path("collected/town_boards.json")
    if not p.exists():
        return "skip", "no town_boards.json here"
    T = imp("town_boards")
    if T is None:
        return "skip", "town_boards.py does not import"
    data = json.loads(p.read_text(encoding="utf-8"))
    boards = data.get("boards") or {}
    councils = data.get("councils") or {}
    dotf = Path("collected/town_officials.json")
    dot = json.loads(dotf.read_text(encoding="utf-8")) if dotf.exists() else {}
    bad, n = [], 0
    for key, b in sorted(councils.items()):
        ms = b.get("members") or []
        n += len(ms)
        if key not in T.CITIES:
            bad.append(f"{key}: a council is published for a place that is "
                       "not one of the thirteen cities")
        # A mayor read off another of the city's pages is shown but may not
        # be counted in the council's size (Nashua's aldermen are fifteen
        # without him), so a whole council is its size with or without them.
        on_page = [m for m in ms if not m.get("source_url")
                   or m["source_url"] == b.get("source_url")]
        size = b.get("size")
        if not b.get("partial") and size not in (len(on_page), len(ms)):
            bad.append(f"{key}: {len(ms)} members published whole for a "
                       f"council of {size}")
        # `read`: the members the size counts, which leaves out a mayor
        # from another page where the council's sentence does.
        counted = b.get("read") or len(on_page)
        if b.get("partial") and size and counted >= size:
            bad.append(f"{key}: marked partial with {counted} of {size}")
        if b.get("read") and b["read"] not in (len(on_page), len(ms)):
            bad.append(f"{key}: {b['read']} counted of {len(ms)} members")
        if not b.get("read"):
            bad.append(f"{key}: the council carries no count of the members "
                       "its size counts, so a partial one's label counts all")
        if size and not b.get("size_from"):
            bad.append(f"{key}: the council's size {size} has no source")
        for f in ("source_url", "read_on"):
            if not b.get(f):
                bad.append(f"{key}: the council has no {f}")
        if not b.get("later"):
            bad.append(f"{key}: nothing on the city's page is later than "
                       "the directory")
        for m in ms:
            if len((m.get("name") or "").split()) < 2 or re.search(
                    r"\b(ward|large|council\w*|mayor|alder\w*|board|city|"
                    r"minutes|agenda|meeting|contact|email|staff)\b",
                    m.get("name") or "", re.I):
                bad.append(f"{key}: {m.get('name')!r} is published as a "
                           "councillor")
    for key, b in sorted(boards.items()):
        ms = b.get("members") or []
        n += len(ms)
        size = b.get("size")
        if not b.get("partial") and (size not in (3, 5) or len(ms) != size):
            bad.append(f"{key}: {len(ms)} members published whole for a board "
                       f"of {size}; a whole board is three or five")
        if b.get("partial") and (size not in (3, 5, None)
                                 or (size and len(ms) >= size) or not ms):
            bad.append(f"{key}: {len(ms)} members marked partial for a board "
                       f"of {size}")
        if size and not b.get("size_from"):
            bad.append(f"{key}: the board's size {size} has no source")
        for f in ("source_url", "read_on"):
            if not b.get(f):
                bad.append(f"{key}: the board has no {f}")
        if not re.match(r"https?://", b.get("source_url") or ""):
            bad.append(f"{key}: {b.get('source_url')!r} is not an address")
        rows = [o.get("name") for o in (dot.get(key) or {}).get("officials") or []
                if (o.get("position") or "").startswith("Board of Selectman")]
        for m in ms:
            name = m.get("name") or ""
            if len(name.split()) < 2 or re.search(
                    r"\b(links?|documents?|polic(?:y|ies)|minutes|agendas?|"
                    r"meetings?|board|committee|office|department|staff|"
                    r"assistant|administrator|secretary|town|city|building|"
                    r"garden|events?|contact|quick|members?|current|report|"
                    r"welcome|news|page)\b", name, re.I):
                bad.append(f"{key}: {name!r} is published as a selectman")
            t = m.get("term_ends")
            if t and T.term_has_ended(int(t), b.get("read_on")):
                bad.append(f"{key}: {name}'s term ended in {t}, before the "
                           f"page was read, so the page predates the board")
            dn = m.get("directory_name")
            if dn and (dn not in rows or not T.same_person(dn, name)):
                bad.append(f"{key}: {name} borrows the directory's contact for "
                           f"{dn!r}, who is not the same selectman")
        for i, a in enumerate(ms):
            for c in ms[i + 1:]:
                if T.compatible(a.get("name", ""), c.get("name", "")):
                    bad.append(f"{key}: {a['name']!r} and {c['name']!r} are "
                               "one person counted twice")
        # Columbia's page named the directory's three, undated and without
        # terms, six months after its minutes swore in a new selectman. The
        # same board as the directory's is published only with a term the
        # 2026 meeting began, or a date after it, to show the page is newer.
        names = [m.get("name") or "" for m in ms]
        same = len(names) == len(rows) and all(
            any(T.same_person(r, nm) for r in rows) for nm in names) and all(
            any(T.same_person(r, nm) for nm in names) for r in rows)
        newer = any(str(m.get("term_ends") or "").isdigit()
                    and int(m["term_ends"]) >= 2029 for m in ms) or \
            "dated" in (b.get("later") or "")
        if not b.get("later"):
            bad.append(f"{key}: nothing recorded on the page is later than "
                       "the directory")
        elif same and not newer:
            bad.append(f"{key}: the directory's own board with no term or "
                       "date after the March 2026 meeting is published as "
                       "the town's current board")
    # A name the page wrote wholly in capitals is published with a spelling
    # in normal case beside it (the person, 24 September 2026): Kensington's
    # "IAN O'REILLY" is Ian O'Reilly.
    for key, b in sorted((boards | councils).items()):
        for m in b.get("members") or []:
            name = m.get("name") or ""
            if name == name.upper() and re.search(r"[A-Z]{2}", name) and (
                    not m.get("display") or m["display"] == m["display"].upper()
                    or m["display"].lower() != name.lower()):
                bad.append(f"{key}: {name!r} is written in capitals and has "
                           f"no spelling in normal case ({m.get('display')!r})")
    assert not bad, "\n  ".join(bad[:20])
    partial = sum(1 for b in (boards | councils).values() if b.get("partial"))
    return "ok", (f"{len(boards)} towns' own boards and {len(councils)} cities' "
                  f"councils, {n} people, current when read and from one page; "
                  f"{partial} marked partial")


@check("build", "a town page links an e-mail address and nothing else, and never beside the wrong person",
       needs=("build_town_pages",))
def _town_mailto(B):
    """175 mailto links on 132 town pages were not addresses.

    NHDOT's e-mail column holds notes as well as addresses, and every note
    was published as a link: "can email through the website, no stated
    email", "no stated email address", "not listed", a street address, and
    two addresses threaded together with a phone number's overflow. And nine
    addresses sit on the wrong row -- rbridle@ beside Amy Hansen in Hampton,
    each other's beside Bow's and Salisbury's two selectmen, the town clerk's
    beside Newfields' road agent.

    Fixture rows carry the ten distinct values the directory had in that
    column that are not addresses, one good address, and the Hampton,
    Salisbury and Newfields rows as NHDOT prints them.
    """
    notes = ["can email through the website, no stated email",
             "no stated email address",
             "can email through the website, no stated email address",
             "can email thorugh the website, no stated email address",
             "can email thorugh the website, no stated email",
             "210 Main St", "not listed",
             "an email through the website, no stated email address",
             "t g1ruelle@eastkingstonnh.gov", "t.t o4wnadmin@sutton-nh.org"]
    offs = [{"position": "Road Agent", "name": f"Person {i}", "phone": "",
             "email": v} for i, v in enumerate(notes)]
    offs.append({"position": "Town Administrator", "name": "Grace Ruelle",
                 "phone": "", "email": "gruelle@eastkingstonnh.gov"})
    html = "".join(B.officials_sections("East Kingston", "east-kingston", {"officials": offs, "email": "not listed"}))
    got = re.findall(r'href="mailto:([^"]*)"', html)
    assert got == ["gruelle@eastkingstonnh.gov"], (
        f"a town page links {got}; only the one address in the fixture is an "
        "address, and a note published as a mailto is a link to nowhere")

    # Nothing on these pages may write a mailto except through maillink(),
    # which is parts.py's since 19 November 2026: the two files together
    # write one, maillink's own.
    src = _source(_paths.locate("build_town_pages.py")) + _source(_paths.locate("parts.py"))
    sites = src.count('href="mailto:')
    assert sites == 1, (
        f"build_town_pages.py and parts.py write a mailto href in {sites} places. Every "
        "one goes through maillink(), which is where a note is refused.")

    hampton = [
        ("Town Manager", "James Sullivan", "jsullivan@hamptonnh.gov"),
        ("Board of Selectman, Chair", "Rusty Bridle", "ahanson@hamptonnh.gov"),
        ("Board of Selectman", "Amy Hansen", "rbridle@town.hampton.nh.us"),
        ("Board of Selectman", "Carleigh Beriont", "crage@hamptonnh.gov"),
        ("Board of Selectman", "Charles Rage", "jwaddell@hamptonnh.gov"),
        ("Board of Selectman", "Jeffery Grip", "cbariont@hamptonnh.gov"),
        ("Public Works Director", "Jennifer Hale", "jhale@hamptonnh.gov")]
    salisbury = [
        ("Town Administrator", "April Rollins", "salisburyadmin@tds.net"),
        ("Board of Selectman, Chair", "Brett Walker",
         "brettwalkerselectman@gmail.com"),
        ("Board of Selectman", "Jim Hoyt", "johnw.herbert@tds.net"),
        ("Board of Selectman", "John Herbert", "jhoytselectman@gmail.com")]
    newfields = [
        ("Board of Selectman", "Hobart Harmon", "hharmon@newfieldsnh.gov"),
        ("Town Clerk", "Sue McKinnon", "suemckinnon@newfieldsnh.gov"),
        ("Road Agent", "Brian Knipstein", "suemckinnon@newfieldsnh.gov")]
    wrong = {"Rusty Bridle", "Amy Hansen", "Carleigh Beriont", "Jeffery Grip",
             "Jim Hoyt", "John Herbert", "Brian Knipstein"}
    bad = []
    for town in (hampton, salisbury, newfields):
        rows = [{"position": p, "name": n, "phone": "", "email": e}
                for p, n, e in town]
        for o in rows:
            other = B.names_someone_else(o["email"], o["name"], rows)
            if bool(other) != (o["name"] in wrong):
                bad.append(f"{o['name']} beside {o['email']}: "
                           f"{'names ' + other if other else 'kept'}")
    assert not bad, (
        "an address beside the wrong person is drawn, or one beside its own "
        "is not: " + "; ".join(bad))
    rows = [{"position": p, "name": n, "phone": "", "email": e}
            for p, n, e in hampton]
    html = "".join(B.officials_sections("Hampton", "hampton", {"officials": rows}))
    for addr in ("ahanson@", "rbridle@", "crage@", "cbariont@"):
        assert f"mailto:{addr}" not in html, (
            f"Hampton's page links {addr} beside a selectman it does not "
            "belong to")
    for addr in ("jsullivan@", "jhale@"):
        assert f"mailto:{addr}" in html, f"Hampton's page lost {addr}, which is its owner's"
    return "ok", (f"{len(notes)} notes refused, 1 address linked, "
                  f"{len(wrong)} addresses beside the wrong person withheld")


@check("build", "a town page's phone number dials, extension and all",
       needs=("build_town_pages",))
def _town_tel(B):
    """28 dial links on the town pages rang numbers in no country.

    tel() took every digit in the value, so "603-588-6785 ext 221" became
    tel:+6035886785221. The extension is written as ;ext= now, and a cell that
    holds two numbers is shown and not dialled.
    """
    want = {"603-588-6785 ext 221": "tel:+16035886785;ext=221",
            "603-927-2400 ext. 4": "tel:+16039272400;ext=4",
            "603-382-5200 ext.261": "tel:+16033825200;ext=261",
            "603-642-8406 ext 1": "tel:+16036428406;ext=1",
            "(603) 271-3420": "tel:+16032713420",
            "603-271-3420": "tel:+16032713420",
            "1-603-271-3420": "tel:+16032713420",
            "603-382-5200 ext. 266 VM 603- 382-6771": None,
            "603-523-770": None}
    bad = []
    for num, href in want.items():
        m = re.search(r'href="([^"]*)"', B.tel(num))
        got = m.group(1) if m else None
        if got != href:
            bad.append(f"{num!r} -> {got}, not {href}")
    assert not bad, "; ".join(bad)
    return "ok", f"{len(want)} numbers, extensions dialled after the number"


@check("build", "a town page's election heading says Next Election until the day, Last election "
                "until the town could have voted again, and then no date",
       needs=("build_town_pages",))
def _town_election_heading(B):
    """How to Vote's card is headed with the Secretary of State's election
    date, and election_line says "Next Election" only while that date is
    ahead of the build. After it the heading said "Election on file"; the
    person approved "Last election: November 3, 2026" in its place on
    16 October 2026, with "Next Election" kept as it stands. The list is
    read by hand, so a passed date is the town's last election only until
    the town could have voted again (next_possible_election); from that day
    the card is headed "Where you vote", as it is wherever the list names no
    date, and places.json's row has no "when" (a review's finding, the same
    day).

    The horizon is held on stated days first, worked out by hand from the
    statutes its docstring cites and a calendar, so that this is not the
    function read back to itself.

    Then real rows of collected/town_clerks.json: Allenstown's, and Concord
    ward 4's, which names the school district's election beside the state's.
    Each is built on days worked out from its own date -- the day before it,
    the day, the day after, the last day it is still the town's last
    election and the first it is not -- through election_line, the built
    page's card heading and the row of places.json that the header's "your
    town" panel prints (find.js, ytVote). So a fresh reading of the list
    that names another day moves the days and not the verdict (the same
    review). A row the list has since left blank is tried with the date it
    named when this was written and the rest of the row as it stands, and
    the result says so: skipping it would hold nothing."""
    import datetime as _dt
    import json as _json
    import shell as S
    D = _dt.date
    stated = {D(2026, 11, 3): D(2027, 3, 1),     # school district meetings open 1 March
              D(2026, 9, 8): D(2026, 11, 3),     # the state primary, then the general election
              D(2027, 3, 1): D(2027, 3, 9),      # a school meeting, then the second Tuesday
              D(2027, 3, 9): D(2027, 4, 13),     # March's town elections, then April's
              D(2027, 5, 11): D(2027, 9, 14),    # May's, then September, taken in odd years too
              D(2027, 11, 2): D(2028, 1, 1),     # a city's November, then a presidential year
              D(2028, 11, 7): D(2029, 3, 1)}
    bad = [f"next_possible_election({d}) is {B.next_possible_election(d)}, not {h}"
           for d, h in stated.items() if B.next_possible_election(d) != h]

    tmpl = S.template()
    local = _json.loads(Path("collected/town_clerks.json").read_text(encoding="utf-8"))
    wards = {str(w): {} for w in range(1, 11)}
    towns = [("Allenstown", "0", {"0": {}}), ("Concord", "4", wards)]
    # What the two rows named on 16 October 2026, for a reading that leaves
    # one blank.
    then = {"allenstown": "11/03/2026-STATE GENERAL ELECTION",
            "concord-ward-4": ("11/03/2026-STATE GENERAL ELECTION, "
                               "11/03/2026-CONCORD SCHOOL DISTRICT ELECTION")}
    rows, lent = {}, []
    for town, ward, _w in towns:
        key = B.slug(town, ward)
        assert key in then and isinstance(local.get(key), dict), (
            f"collected/town_clerks.json has no row {key!r}; this check's cases are that row")
        rows[key] = dict(local[key])
        if B.election_day(rows[key].get("election")) is None:
            rows[key]["election"] = then[key]
            lent.append(key)
    off = {"_local": {**local, **rows}}
    said = []
    was = os.environ.get("GRANITE_BUILD_DATE")
    try:
        for town, ward, w in towns:
            loc = rows[B.slug(town, ward)]
            d = B.election_day(loc["election"])
            h = B.next_possible_election(d)
            when = f"{d:%B} {d.day}, {d.year}"
            one = _dt.timedelta(days=1)
            said.append(f"{town}{'' if ward == '0' else ' ward ' + ward} {when}, Last election "
                        f"to {h - one}")
            for day, want in ((d - one, f"Next Election: {when}"), (d, f"Next Election: {when}"),
                              (d + one, f"Last election: {when}"),
                              (h - one, f"Last election: {when}"), (h, "")):
                os.environ["GRANITE_BUILD_DATE"] = day.isoformat()
                got = B.election_line(loc["election"])
                if got != want:
                    bad.append(f"{town} {ward} built {day}: election_line said {got!r}, not {want!r}")
                page = B.build(town, ward, w, {}, [], off, "https://x.test", tmpl)
                head = want or "Where you vote"
                dated = re.findall(r'<h3 class="twnh">([^<]*lection[^<]*)</h3>', page)
                if f'<h3 class="twnh">{head}</h3>' not in page or (dated and not want):
                    bad.append(f"{town} {ward} built {day}: the How to Vote card is headed "
                               f"{dated or 'otherwise'}, not {head!r}")
                rec = B.place_record(town, ward, w, {}, [], loc)
                if rec.get("when") != (want or None):
                    bad.append(f"{town} {ward} built {day}: places.json says {rec.get('when')!r}, "
                               f"not {want or None!r}")
    finally:
        if was is None:
            os.environ.pop("GRANITE_BUILD_DATE", None)
        else:
            os.environ["GRANITE_BUILD_DATE"] = was
    assert not bad, "\n  ".join(bad)
    return "ok", (f"{len(stated)} stated horizons; " + "; ".join(said)
                  + ", then Where you vote, on the page and in places.json"
                  + (f" ({', '.join(lent)} blank on the list now, tried with its 16 October date)"
                     if lent else ""))


@check("data", "the Secretary of State's clerk list is read again once its election date has "
       "stopped heading the town pages", needs=("build_town_pages", "parse_clerks_csv"))
def _town_clerks_reread(B, PC):
    """A REMINDER, the register of probate paragraph's kind
    (_probate_after_the_vote).

    How to Vote's card on a town page is headed with the election
    collected/town_clerks.json names, and election_line stops calling a
    passed one the town's last on the first day the town could have voted
    again (next_possible_election): from then the card says only "Where you
    vote", which is true and says less. Nothing reads the Secretary of
    State's list on a schedule -- a person downloads its CSV and runs
    src/towns/parse_clerks_csv.py -- so without this the date would drop off
    every town page that had one and nobody would be told (a review's
    finding, 16 October 2026).

    It fails from that day for as long as the list was last read before it
    (parse_clerks_csv.READ_ON, the export's own day), and passes once the
    list is read again, whatever the new one names: a list read after that
    day which still names the old election is the Secretary of State's word,
    not a stale copy of it. A data check, and a reminder (REMINDERS): on the
    night it warns, because a list to reread is no reason to hold the site.

    The rule is run on fixed days before it is run on the clock, so a
    reminder that could never fire fails now rather than passing quietly
    through the day it was written for."""
    import datetime as _dt
    import build_date
    D = _dt.date

    def rule(today, rows, read_on):
        """{election day: the rows naming it}, for each election that has
        stopped heading the pages by `today` on a list read before it did."""
        out = {}
        for key, row in rows.items():
            d = B.election_day((row or {}).get("election") if isinstance(row, dict) else None)
            if d is None:
                continue
            h = B.next_possible_election(d)
            if h <= today and read_on < h:
                out.setdefault(d, []).append(key)
        return out

    one = {"allenstown": {"election": "11/03/2026-STATE GENERAL ELECTION"}}
    sept = D(2026, 9, 20)
    assert not rule(D(2027, 2, 28), one, sept), \
        "the reminder fires on 28 February 2027, before the town could have voted again"
    assert rule(D(2027, 3, 1), one, sept) == {D(2026, 11, 3): ["allenstown"]}, \
        "the reminder does not fire on 1 March 2027 for a list read in September 2026"
    assert not rule(D(2027, 3, 1), one, D(2027, 3, 1)), \
        "a list read again on 1 March 2027 does not quiet the reminder"

    try:
        read_on = D.fromisoformat(str(PC.READ_ON))
    except ValueError:
        raise AssertionError(f"parse_clerks_csv.READ_ON is {PC.READ_ON!r}, which is not a day: "
                             "write the day the Secretary of State's export was made, as "
                             "\"2026-09-20\"") from None
    local = json.loads(Path("collected/town_clerks.json").read_text(encoding="utf-8"))
    today = build_date.today()
    stale = rule(today, local, read_on)
    words = lambda d: f"{d:%B} {d.day}, {d.year}"         # noqa: E731
    assert not stale, "; ".join(
        f"{len(keys)} rows of collected/town_clerks.json name the election of {words(d)}, and "
        f"since {words(B.next_possible_election(d))}, when those towns could have voted again, "
        "the town pages' How to Vote card has been headed only \"Where you vote\""
        for d, keys in sorted(stale.items())) + (
        f". The list was last read on {read_on}: download the Secretary of State's list again "
        f"as CSV ({PC.SOURCE_URL}; a person's to start, it is somebody else's server), point "
        "CSV_IN and READ_ON in src/towns/parse_clerks_csv.py at it, and run that script")
    dated = sorted({d for d in map(B.election_day, (r.get("election") for r in local.values()
                                                    if isinstance(r, dict))) if d})
    return "ok", (f"the list read {read_on} names {', '.join(map(str, dated)) or 'no election'}, "
                  "and no date of it has stopped heading the town pages since it was read; the "
                  "rule fires on 1 March 2027 for a list read in September 2026")


@check("files", "no file a town page's officials are drawn from holds less than its floor, and the "
       "clerk list carries every correction made to it", needs=("town_sources",))
def _town_sources_floors(TS):
    """SILENCE IS NOT SUCCESS, for the three files the town pages' officials
    come from (the freshness review, 23 October 2026).

    `python3 src/towns/parse_officials.py`, run as its docstring says on a
    machine with no built site, matched none of the directory's 234
    municipalities against a site/districts.json that was not there, wrote
    `{}` in collected/town_officials.json's place and exited 0 (found before
    it ever reached git): every town's select board, town offices and three
    cities' councils would have gone from the pages at the next build with
    nothing to say why. Its writer and
    parse_clerks_csv.py's now refuse to write under town_sources.FLOORS; this
    holds the files in git to the same floors, whatever wrote them.

    AND THE CORRECTIONS. src/fetch/other/fetch_town_clerks.py writes the
    same file from the same list in a shape of its own, without
    corrections/place_corrections.json -- run, it would put Errol Town Hall
    back at Colebrook's address on three rows, and pass every floor. So
    every polling place the corrections file corrects must be in the file
    with what the list says beside it.

    The floors are run on an empty file first, so a floor that nothing can
    fall under fails here."""
    for key in TS.SOURCES:
        empty = {"boards": {}, "councils": {}} if key == "town_sites" else {}
        assert TS.short_of(key, empty), f"an empty {TS.SOURCES[key]['file']} is under no floor"
    bad, held = [], []
    for key in TS.SOURCES:
        data = TS.load(key)
        if data is None:
            bad.append(f"{TS.SOURCES[key]['file']} is not there")
            continue
        bad += TS.short_of(key, data)
        have = TS.counts(key, data)
        held.append(f"{TS.SOURCES[key]['file']} " + ", ".join(
            f"{have[f]} {f}" for f in TS.FLOORS[key]))
    fixes = Path("corrections/place_corrections.json")
    fixed = json.loads(fixes.read_text(encoding="utf-8")).get("polling_place") or {} \
        if fixes.exists() else {}
    clerks = TS.load("sos_list") or {}
    for k in sorted(fixed):
        if not (clerks.get(k) or {}).get("polling_place_source_says"):
            bad.append(f"collected/town_clerks.json does not carry the correction of {k}'s "
                       "polling place: write it with src/towns/parse_clerks_csv.py, which "
                       "applies corrections/place_corrections.json")
    assert not bad, "\n  ".join(bad)
    return "ok", "; ".join(held) + f"; all {len(fixed)} polling place corrections applied"


@check("frontend", "a town page's Services tab: the office where two sources agree on its "
                   "street, the town's libraries and its transfer stations, each card's sources "
                   "and their age in one small line",
       needs=("build_town_pages",))
def _town_services_tab(T):
    """The town directory's first phase on the page (the person, 24 October
    2026: "the address of city hall ... That would exist on town pages").
    The tab's cards, drawn from the two readers' files as they are written:

      - an office whose street two sources agree on is drawn there, with a
        map, unlabelled -- it is under "Town office" -- and the sources named
        and dated under it;
      - a city's is "City hall", a town's "Town office";
      - an office with only a box for its mail draws it as its mailing
        address, and no street;
      - the libraries, a branch said to be one, and a town with none says
        so rather than drawing nothing;
      - the transfer stations (25 October 2026), each opening its page at
        DES, with a map and who holds its permit where that is not the town
        itself, the list and its day under them and the town's own website
        for the hours (the town office where it has none); a shared station
        drawn in the town it is in, under its permit holder; and no card at
        all where DES lists none, since DES lists as closed some stations
        that run;
      - and an unincorporated place, which NHDOT does not list and which has
        no office, has no tab at all.

    EACH CARD'S SOURCES IN ONE SMALL LINE (the audit of 25 October 2026: the
    grey boxes of sourcing were 41 to 45 per cent of the tab): "NH DOT
    directory, Sep 2025 · Secretary of State, Sep 2026", "IMLS library
    survey, FY2024", "NH DES permit list, read Oct 25, 2026 · hours on the
    town's website" -- every source still named with its age, no box, and
    no "No street address ... two sources agree on" or "Where it is".

    And the panel is on every town page, named Services in a town and a
    city alike."""
    off = {"mailing": "5 School St, Bristol, NH 03222", "phone": "603-744-3354",
           "website": "https://www.bristolnh.gov", "as_of": "2025-09-02"}
    hall = {"street": "5 School St", "place": "Bristol", "zip": "03222",
            "from": [{"source": "nhdot", "on": "2025-09-02"},
                     {"source": "sos_list", "on": "2026-09-20"}]}
    libs = {"libraries": [{"name": "Minot-Sleeper Library", "street": "35 Pleasant Street",
                           "city": "Bristol", "phone": "603-744-3352", "kind": "central"}],
            "survey": "FY2024"}
    got = "".join(T.services_sections("Bristol", "bristol", off, hall, libs))
    for want in ('<h3 class="twnh">Town office</h3>',
                 '<span class="offwho">5 School St, Bristol, NH 03222</span>',
                 'href="https://www.openstreetmap.org/search?query=5%20School%20St%2C%20Bristol%2C%20NH%2003222"',
                 '<p class="twnsrc">NH DOT directory, Sep 2025 &middot; Secretary of State, Sep 2026</p>',
                 '<h3 class="twnh">Library</h3>', "Minot-Sleeper Library",
                 '<p class="twnsrc">IMLS library survey, FY2024</p>'):
        assert want in got, f"the Services tab does not draw {want!r}"
    assert "Mailing address" not in got, "the office's own street is said again as its mailing address"
    # The survey and the town's site, ordered after NHDOT, each with its month;
    # and of three that agree on a street the newest two, which are what draws it.
    said = T.office_sources("Lyme", {"as_of": "2025-09-02"}, [
        {"source": "granit_cai", "on": "2014-09-30"},
        {"source": "town_site", "on": "2026-10-20", "url": "https://www.lymenh.gov/"}])
    assert said == ["NH DOT directory, Sep 2025", "Lyme's website, Oct 2026",
                    "NH GRANIT survey, Sep 2014"], f"the office's sources read {said}"
    said = T.office_sources("Lyme", {}, [{"source": "granit_cai", "on": "2014-09-30"}]
                            + hall["from"])
    assert said == ["NH DOT directory, Sep 2025", "Secretary of State, Sep 2026"], (
        f"three sources agreeing on a street read {said}, not the newest two")
    city = "".join(T.services_sections("Concord", "concord", {"mailing": "41 Green St, Concord, NH 03301"},
                                       {}, {"libraries": [
                                           {"name": "Concord Public Library", "street": "45 Green Street",
                                            "city": "Concord", "phone": "", "kind": "central"},
                                           {"name": "Penacook Branch Library", "street": "3 Merrimack Street",
                                            "city": "Penacook", "phone": "", "kind": "branch"}]}))
    assert '<h3 class="twnh">City hall</h3>' in city and '<h3 class="twnh">Libraries</h3>' in city \
        and "Branch library, 3 Merrimack Street, Penacook" in city, (
            "a city's office is not City hall, or its branch is not said to be one")
    boxed = "".join(T.services_sections("Acworth", "acworth",
                                        {"mailing": "PO Box 37, Acworth, NH 03601",
                                         "phone": "603-835-6879", "as_of": "2025-09-02"},
                                        {"street": ""}, {}))
    assert "Library" not in "".join(T.services_sections("Acworth", "acworth", {"phone": "1"}, None, None)), (
        "a libraries file that was not loaded is drawn as a town with no library")
    assert "PO Box 37, Acworth, NH 03601<span class=\"offseat\">Mailing address</span>" in boxed and \
        "offmap" not in boxed and '<p class="twnsrc">NH DOT directory, Sep 2025</p>' in boxed and \
        '<p class="twnsrc">No public library is listed in Acworth &middot; IMLS library survey, ' \
        'FY2024</p>' in boxed, (
            "a town with a box for its mail draws a street, does not name the directory and its "
            "month, or does not say it has no library and where that is from")
    assert T.services_sections("Hale's Location", "hale-s-location", {}, None, None) == [], (
        "an unincorporated place has a Services tab")
    # ---- the transfer stations ------------------------------------------------
    page = ("https://onestop.des.nh.gov/ords/r/apex_whs/nhdesbasicsearch/"
            "solid-waste-facility?p60_swf_lid=0001234")
    one = {"read_on": "2026-10-25", "stations": [
        {"name": "Acworth Transfer Station", "street": "222 Beryl Mountain Rd", "also": "",
         "place": "Acworth", "page": page, "permittee": "Town of Acworth", "named": False}]}
    acw = "".join(T.services_sections("Acworth", "acworth", {"phone": "603-835-6879",
                                                             "website": "acworthnh.gov"},
                                      None, None, one))
    for want in ('<h3 class="twnh">Transfer station</h3>',
                 f'<a href="{T.E(page)}" target="_blank" rel="noopener">Acworth Transfer Station</a>',
                 "222 Beryl Mountain Rd, Acworth",
                 "query=222%20Beryl%20Mountain%20Rd%2C%20Acworth%2C%20NH",
                 '<p class="twnsrc">NH DES permit list, read Oct 25, 2026 &middot; hours on '
                 '<a href="https://acworthnh.gov" target="_blank" rel="noopener">the town&#x27;s '
                 'website</a></p>'):
        assert want in acw, f"the transfer station card does not draw {want!r}"
    assert "Permit holder" not in acw, "a town's own station is said to be the town's permit"
    berlin = "".join(T.services_sections("Berlin", "berlin", {"phone": "1"}, None, None, {
        "read_on": "2026-10-25", "stations": [
            {"name": "AVRRDD Recycling Center and Transfer Station", "street": "100 West Milan Rd",
             "also": "Route 110", "place": "Berlin", "page": page, "named": False,
             "permittee": "Androscoggin Valley Regional Refuse Disposal District"},
            {"name": "Berlin Drop Off", "street": "1 Main St", "also": "", "place": "Berlin",
             "page": page, "permittee": "City of Berlin", "named": False}]}))
    assert '<h3 class="twnh">Transfer stations</h3>' in berlin and \
        "100 West Milan Rd (Route 110), Berlin<br>Permit holder: Androscoggin Valley Regional " \
        "Refuse Disposal District" in berlin and \
        '<p class="twnsrc">NH DES permit list, read Oct 25, 2026 &middot; hours from city hall</p>' \
        in berlin, ("two stations, a district's permit, or a city with no website's hall are not "
                    "said so")
    jackson = "".join(T.services_sections("Jackson", "jackson", {"phone": "1"}, None, None, {
        "read_on": "2026-10-25", "stations": [
            {"name": "Bartlett Jackson Harts Location Transfer Station",
             "street": "102 Transfer Station Rd", "also": "", "place": "Bartlett", "page": page,
             "permittee": "Town of Bartlett", "named": True}]}))
    assert "Bartlett Jackson Harts Location Transfer Station</a><span class=\"offseat\">102 Transfer " \
        "Station Rd, Bartlett<br>Permit holder: Town of Bartlett" in jackson and \
        "hours from the town office" in jackson, (
            "a shared station is not drawn in the town it is in, under its permit holder")
    for none in ({}, None, {"read_on": "2026-10-25", "stations": []}):
        assert "Transfer station" not in "".join(T.services_sections(
            "Holderness", "holderness", {"phone": "1"}, None, {}, none)), (
                f"a town DES lists no station in draws a transfer station card ({none!r})")
    # One small line a card, and no box: every card above ends in its line.
    drawn = [got, city, boxed, acw, berlin, jackson]
    cards = [c for h in drawn for c in re.findall(r'<section class="twnsec[^"]*">.*?</section>', h)]
    loose = [c[:90] for c in cards if 'class="note"' in c or c.count('class="twnsrc"') != 1
             or not re.search(r'<p class="twnsrc">[^<]*(?:<a [^>]+>[^<]*</a>)?</p></section>$', c)]
    assert cards and not loose, f"a Services card has a grey box, or not one source line at its end: {loose}"
    import inspect
    src = inspect.getsource(T.build)
    assert '("services", "Services",' in src, "the Services tab is not one of a town page's panels"
    assert 'off["_stations"].get(slug(town, "0"), {})' in src, (
        "the transfer stations are not given to the Services tab")
    return "ok", ("an office drawn where two sources agree, a city's City hall, a boxed office as "
                  "its mailing address, libraries and none, the transfer stations with their page, "
                  "map and permit holder, none drawn where DES lists none, and no tab where there is "
                  "no town; every card's sources and their age in one small line, no box")


@check("frontend", "a town office's mailing address never ends in a \"PO Box\" with no number, "
                   "on the Officials tab or the Services tab, and is not the street said twice",
       needs=("build_town_pages",))
def _town_mailing_box(T):
    """NHDOT's directory prints thirteen towns' mailing line as a street and
    the bare words "PO Box" -- Bethlehem's "2155 Main St, PO Box", Hanover's
    "41 South Main St, PO Box" -- and the office cards drew it so (the audit
    of 25 October 2026). mailing_line drops a "PO Box" no number follows,
    and a comma left at the end, on both tabs; a box with its number is
    kept. And on the Services tab a mailing line that is the street NHDOT's
    own line agreed with (collected/town_halls.json's `from`) is not drawn
    again under the street in another spelling -- Hanover's "41 South Main
    St" under "41 S Main St" -- while one with a box is.

    Read on the files in git as well as on these cases: every office in
    collected/town_officials.json, drawn on both tabs, ends in no bare box."""
    for raw, want in (("2155 Main St, PO Box", "2155 Main St"),
                      ("84 South Main St, P.O. Box ", "84 South Main St"),
                      ("780 Rte 63, PO Box 55,", "780 Rte 63, PO Box 55"),
                      ("297 Mayhew Turnpike,", "297 Mayhew Turnpike"),
                      ("PO Box 37, Acworth, NH 03601", "PO Box 37, Acworth, NH 03601"),
                      ("PO Box", ""), ("", "")):
        assert T.mailing_line(raw) == want, f"{raw!r} is drawn {T.mailing_line(raw)!r}, not {want!r}"
    off = {"mailing": "41 South Main St, PO Box", "phone": "603-643-0742", "as_of": "2025-09-02"}
    agreed = {"street": "41 S Main St", "place": "Hanover", "zip": "03755",
              "from": [{"source": "granit_cai", "on": "2014-09-30"},
                       {"source": "nhdot", "on": "2025-09-02", "said": off["mailing"]}]}
    tab = "".join(T.officials_sections("Hanover", "hanover", off))
    assert '41 South Main St<span class="offseat">Mailing address</span>' in tab, (
        f"the Officials tab's office card draws {off['mailing']!r} with its bare box")
    svc = "".join(T.services_sections("Hanover", "hanover", off, agreed, None, None))
    assert "41 S Main St, Hanover, NH 03755" in svc and "Mailing address" not in svc, (
        "the Services tab draws NHDOT's line again under the street it agreed with")
    boxed = dict(off, mailing="780 Rte 63, PO Box 55,")
    svc = "".join(T.services_sections("Westmoreland", "westmoreland", boxed,
                                      dict(agreed, street="780 NH Rte 63", place="Westmoreland",
                                           zip="03467"), None, None))
    assert '780 Rte 63, PO Box 55<span class="offseat">Mailing address</span>' in svc, (
        "a mailing line with a box number under the street is not drawn")
    # ---- the files in git -----------------------------------------------------
    def load(name):
        p = Path("collected") / name
        return {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items()
                if not k.startswith("_")} if p.exists() else None
    offices, halls = load("town_officials.json"), load("town_halls.json")
    if offices is None or halls is None:
        return "ok", "the cases (collected/town_officials.json or town_halls.json is not here)"
    bare = re.compile(r"P\.?\s*O\.?\s*Box\s*,?\s*<|,\s*<span class=\"offseat\">", re.I)
    raw = [k for k, v in offices.items() if T.BARE_BOX.search(v.get("mailing") or "")]
    bad = [k for k, v in sorted(offices.items())
           if bare.search("".join(T.officials_sections(v.get("municipality") or k, k, v))
                          + "".join(T.services_sections(v.get("municipality") or k, k, v,
                                                        halls.get(k), None, None)))]
    assert not bad, f"offices drawn with a bare box or a trailing comma: {bad[:8]}"
    return "ok", (f"a bare box and a trailing comma dropped, a box with its number kept; "
                  f"{len(offices)} offices in git drawn on both tabs, {len(raw)} of whose lines "
                  "end in a bare box, none drawn with one")


@check("files", "the town directory's readers: a library is placed by its census block, and a "
                "town office's street is drawn only where two sources agree on it",
       needs=("parse_libraries", "parse_town_halls"))
def _town_directory_readers(L, H):
    """The town directory's first phase (the person, 24 October 2026: "the
    address of city hall ... That would exist on town pages"), held to what
    its two readers were written against.

    A LIBRARY IS IN ITS BLOCK'S TOWN. The survey's postal city is not the
    town for 26 of New Hampshire's 229 libraries (Penacook's is in Concord,
    North Conway's in Conway, Woodsville's in Haverhill), so parse_libraries
    places each by its census block and the Census's 2020 names, written as
    the site writes a town's: "Alton town" is Alton, "Hale's location"
    Hale's Location.

    A TOWN OFFICE'S STREET ONLY WHERE TWO SOURCES AGREE. Every disagreement
    between NH GRANIT's 2014 survey and NHDOT's directory was read by hand
    when parse_town_halls was written, and the cases here are those: the
    same address spelled two ways agrees ("1 City Hall Plz" and "1 City Hall
    Plaza", "488 Townhouse Rd" and "488 Town House Rd", "818 First New
    Hampshire Tpke" and "818 1st NH Turnpike", "268" and "268B"); an office
    that has moved (Durham's from 15 to 8 Newmarket Rd) and a number typed
    twice two ways (Lempster's 865 and 856) do not. The survey's own names
    for a town's buildings ("Harrisville -Town Office", "Stratham - Town
    Hall / EOC", "City of Keene - City Hall", the village "West Milan") are
    read as its towns'. And the files in git: every library placed, every
    street drawn carrying two sources with their days, and neither under its
    floor."""
    # ---- libraries ---------------------------------------------------------
    assert L.phone("6038352150") == "603-835-2150" and L.phone("-3") == "", "a phone"
    import tempfile as _tf
    tmp = Path(_tf.mkdtemp(prefix="gr-towndir-"))
    try:
        names = tmp / "names.txt"
        names.write_text("STATE|STATEFP|COUNTYFP|COUNTYNAME|COUSUBFP|COUSUBNS|COUSUBNAME|CLASSFP|FUNCSTAT\n"
                         "NH|33|001|Belknap County|01060|00873530|Alton town|T1|A\n"
                         "NH|33|007|Coos County|04280|00873542|Berlin city|C5|A\n"
                         "NH|33|003|Carroll County|32820|00873600|Hale's location|Z1|F\n"
                         "NH|33|009|Grafton County|00000|00000000|County subdivisions not defined|Z9|F\n",
                         encoding="utf-8")
        was = L.NAMES
        L.NAMES = names
        try:
            got = L.subdivision_names()
        finally:
            L.NAMES = was
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert got == {("001", "01060"): "Alton", ("007", "04280"): "Berlin",
                   ("003", "32820"): "Hale's Location"}, f"the Census names read as {got}"
    towns = {"CONCORD": ["1"], "CONWAY": ["0"]}
    rows = [{"CENBLOCK": "330130001001000", "LIBNAME": "PENACOOK BRANCH LIBRARY",
             "ADDRESS": "76 MAIN STREET", "CITY": "PENACOOK", "ZIP": "03303", "PHONE": "6037536740",
             "C_OUT_TY": "BR", "LATITUDE": "43.28", "LONGITUD": "-71.6", "FSCSKEY": "NH0167",
             "FSCS_SEQ": "004"}]
    data, unplaced, _n = L.build(rows, {"330130001001000": ("013", "14200")},
                                 {("013", "14200"): "Concord"}, towns, "2026-10-24")
    assert not unplaced and list(data) == ["concord"] and \
        data["concord"]["libraries"][0]["name"] == "Penacook Branch Library" and \
        data["concord"]["libraries"][0]["kind"] == "branch", (
            f"Penacook's library is not placed in Concord by its block: {data}, {unplaced}")

    # ---- town offices ------------------------------------------------------
    agree = [("1 City Hall Plaza, Manchester, NH 03101", "1", "cityhallplz"),
             ("488 Town House Rd, Cornish, NH 03745", "488", "townhouserd"),
             ("818 1st NH Turnpike, Northwood, NH 03261", "818", "1stnhtpke"),
             ("268B Mammoth Rd Londonderry 03053", "268", "mammothrd"),
             ("130 NH Route 10 Piermont 03779", "130", "rte10")]
    for text, number, street in agree:
        assert H.carries(text, number, street), f"{text!r} does not carry {number} {street}"
    for text, number, street in (("8 Newmarket Road Durham 03824", "15", "newmarketrd"),
                                 ("856 NH Route 10 Lempster 03605", "865", "rte10")):
        assert not H.carries(text, number, street), f"{text!r} is taken to carry {number} {street}"
    assert H.street_in("PO Box 37 Acworth 03601") is None, "a box's number is read as a street"
    assert H.street_in("93 Main Street Sutton 03221") == ("93", "mainst")
    survey_row = {"BLDGNBR": "130", "PREDIR": "", "STREETNAME": "NH Rte 10", "STREETTYPE": "Rte",
                  "SUFFDIR": ""}
    assert H.street_of(survey_row) == ("130 NH Rte 10", "130", "rte10"), H.street_of(survey_row)
    loud = {"BLDGNBR": "29", "PREDIR": "S", "STREETNAME": "South Village", "STREETTYPE": "Rd",
            "SUFFDIR": ""}
    assert H.street_of(loud)[0] == "29 South Village Rd", H.street_of(loud)
    assert H.mailing_parts("84 South Main St, PO Box") == ("84 South Main St", "", "")
    assert H.mailing_parts("4 Signature Dr (off Rte 125), Barrington, NH 03825") == \
        ("4 Signature Dr", "Barrington", "03825")
    names = {"HARRISVILLE": ["0"], "STRATHAM": ["0"], "KEENE": ["0"], "MILAN": ["0"]}
    rows = [{"CAICAT": "6", "ANCHORNAME": n} for n in
            ("Harrisville -Town Office", "Stratham - Town Hall / EOC", "City of Keene - City Hall",
             "West Milan - Town Hall", "Keene - Old Town Hall")]
    found, unmatched = H.survey_offices(rows, names)
    assert sorted(found) == ["harrisville", "keene", "milan", "stratham"] and not unmatched, (
        f"the survey's own names for a town's office: {sorted(found)}, {unmatched}")

    # ---- the files in git ----------------------------------------------------
    libs = json.loads(Path("collected/libraries.json").read_text(encoding="utf-8"))
    n_lib = sum(len(v["libraries"]) for k, v in libs.items() if not k.startswith("_"))
    assert n_lib >= 220 and all(v.get("read_on") for k, v in libs.items() if not k.startswith("_")), (
        f"collected/libraries.json holds {n_lib} libraries, or a town without its day")
    halls = json.loads(Path("collected/town_halls.json").read_text(encoding="utf-8"))
    rows = {k: v for k, v in halls.items() if not k.startswith("_")}
    drawn = {k: v for k, v in rows.items() if v["street"]}
    assert len(rows) >= 230 and len(drawn) >= H.FLOOR_FOUND, (
        f"collected/town_halls.json: {len(rows)} towns, {len(drawn)} with a street, "
        f"under {H.FLOOR_FOUND}")
    bad = [k for k, v in drawn.items()
           if len({f["source"] for f in v["from"]}) < 2 or not all(f.get("on") for f in v["from"])
           or not (v["place"] and v["zip"])]
    assert not bad, f"a street drawn without two dated sources, or its place and ZIP: {bad[:6]}"
    return "ok", (f"{n_lib} libraries in {len(libs) - 1} towns; {len(drawn)} of {len(rows)} town "
                  "offices with a street two sources agree on; the hand-read cases hold")


@check("files", "the transfer station reader: a station is one DES lists as operating and as "
                "publicly owned on its own page, never one a name makes look like a town's",
       needs=("parse_transfer_stations", "town_sources"))
def _transfer_station_reader(W, TS):
    """The Town Services tab's transfer station card (the person, 24 October
    2026: "Are you able to retrieve the other info like the transfer stations
    so those cards can be included?"), held to what its reader was written
    against: the pages read on 25 October 2026.

    THE OWNER IS DES'S FIELD, NOT THE NAME. Auburn's "Municipal Solid Waste
    and Citizen Drop Off Facility" is Waste Management of New Hampshire's,
    and "Raymond A. LaRoche Sr. Transfer Station and Recycling Center" is the
    Town of Durham's: the page's owner type says which, and a name is never
    read for it. Nor a business's class (scrap metal, asbestos, a hauler's
    truck transfer station), nor a page that is another facility's.

    A SHARED STATION IS IN EACH TOWN ITS NAME IS MADE OF: Campton Thornton's
    in Campton too, Bartlett Jackson Harts Location's in Hart's Location,
    whose apostrophe DES does not write. Raymond, in Durham's station's name,
    is a person's name there: the rest of it is not towns. And the names
    are written for the page with their acronyms and small words kept as
    they should be; and the file in git is over its floor, every station
    carrying its permit, its day and its page at DES."""
    cases = {"TOWN OF MILTON TRANSFER STATION/RECYCLING CENTER":
             "Town of Milton Transfer Station/Recycling Center",
             "BCEP SOLID WASTE DISTRICT": "BCEP Solid Waste District",
             "TRI-TOWN TRANSFER STATION": "Tri-Town Transfer Station",
             "ASHLAND TRANSFER STATION & RECYCLING CENTER":
             "Ashland Transfer Station & Recycling Center",
             "29 DPW ROAD": "29 DPW Road", "357 NH RT 3A": "357 NH Rt 3A",
             "NORTH OF VILLAGE": "North of Village",
             "ALLENSTOWN TRANSFER STATION (CASELLA WASTE SERVICES)":
             "Allenstown Transfer Station (Casella Waste Services)"}
    for raw, want in cases.items():
        assert W.facility_case(raw) == want, f"{raw!r} is written {W.facility_case(raw)!r}"
    towns = {t: ["0"] for t in ("CAMPTON", "THORNTON", "RAYMOND", "DURHAM", "BARTLETT", "JACKSON",
                                "HART'S LOCATION", "STARK", "NEW BOSTON", "AUBURN", "ANTRIM")}
    for name, want in (("CAMPTON THORNTON TRANSFER STATION & RECYCLING CENTER", ["CAMPTON", "THORNTON"]),
                       ("BARTLETT JACKSON HARTS LOCATION TRANSFER STATION",
                        ["BARTLETT", "JACKSON", "HART'S LOCATION"]),
                       ("RAYMOND A. LAROCHE SR. TRANSFER STATION AND RECYCLING CENTER", []),
                       ("TOWN OF STARK, NH TRANSFER STATION AND RECYCLING CENTER", []),
                       ("NEW BOSTON TRANSFER STATION/RECYCLING CENTER", [])):
        assert W.named_towns(name, towns) == want, f"{name!r} names {W.named_towns(name, towns)}"
    items = W.page_items('<input type="hidden" id="P60_OWNER_TYPE" name="P60_OWNER_TYPE" '
                         'data-type="VARCHAR2" value="PUBLIC"><input type="hidden" '
                         'id="P60_FACILITY_STREET_ADDRESS" name="P60_FACILITY_STREET_ADDRESS" '
                         'data-type="VARCHAR2" value="100 DURHAM POINT RD&lt;br&gt;DURHAM">')
    assert items == {"P60_OWNER_TYPE": "PUBLIC",
                     "P60_FACILITY_STREET_ADDRESS": "100 DURHAM POINT RD\nDURHAM"}, items

    def rec(lid, name, city, permit, kind="C/S/T", status="OPERATING"):
        return {"SWF_TYPE": kind, "SWF_STATUS": status, "SWF_NAME": name, "SWF_CITY": city,
                "SWF_PERMIT": permit, "SWF_ADD_1": "1 MAIN ST", "SWF_ADD_2": "", "SWF_LAT": 43.0,
                "SWF_LONG": -71.0, "ONESTOP_LINK": "https://onestop.des.nh.gov/ords/r/apex_whs/"
                f"nhdesbasicsearch/solid-waste-facility?p60_swf_lid={lid}"}

    def page(lid, permit, city, owner, holder):
        return {"P60_FACILITY_ID": lid, "P60_PERMIT_NUMBER": permit, "P60_FACILITY_STATUS": "OPERATING",
                "P60_OWNER_TYPE": owner, "P60_PERMITTEE_NAME": holder,
                "P60_FACILITY_STREET_ADDRESS": f"1 MAIN ST\n{city}"}
    records = [rec("0000338", "RAYMOND A. LAROCHE SR. TRANSFER STATION AND RECYCLING CENTER", "DURHAM", "P1"),
               rec("0000001", "MUNICIPAL SOLID WASTE AND CITIZEN DROP OFF FACILITY", "AUBURN", "P2"),
               rec("0000002", "N N M RECYCLING, LLC", "ANTRIM", "P3", kind="C/S/T \u2013 SCRAP METAL"),
               rec("0000003", "CAMPTON THORNTON TRANSFER STATION & RECYCLING CENTER", "THORNTON", "P4"),
               rec("0000004", "STARK TRANSFER STATION", "STARK", "P5", status="NOT OPERATING"),
               rec("0000005", "JACKSON TRANSFER STATION", "JACKSON", "P6"),
               rec("0000006", "NEW BOSTON TRANSFER STATION", "NEW BOSTON", "P7")]
    pages = {"0000338": page("0000338", "P1", "DURHAM", "PUBLIC", "TOWN OF DURHAM"),
             "0000001": page("0000001", "P2", "AUBURN", "PRIVATE", "WASTE MANAGEMENT OF NEW HAMPSHIRE, INC."),
             "0000002": page("0000002", "P3", "ANTRIM", "PRIVATE", "N N M RECYCLING, LLC"),
             "0000003": page("0000003", "P4", "THORNTON", "PUBLIC", "TOWN OF THORNTON"),
             "0000004": page("0000004", "P5", "STARK", "PUBLIC", "TOWN OF STARK"),
             "0000005": page("0000005", "P-OTHER", "JACKSON", "PUBLIC", "TOWN OF JACKSON")}
    data, left = W.build(records, pages, towns, "2026-10-25", {})
    assert sorted(data) == ["campton", "durham", "thornton"], (
        f"the stations kept are {sorted(data)}; left out {left}")
    assert data["durham"]["stations"][0]["permittee"] == "Town of Durham" and \
        data["durham"]["stations"][0]["owner_type"] == "public", data["durham"]
    assert [x["named"] for x in data["campton"]["stations"]] == [True] and \
        [x["named"] for x in data["thornton"]["stations"]] == [False], (
            "a shared station is not in its own town and in the town its name names")
    reasons = " | ".join(f"{k}: {v}" for k, v in sorted(left.items()))
    for want in ("owned private: ['MUNICIPAL SOLID WASTE AND CITIZEN DROP OFF FACILITY",
                 "a business's class", "another permit's", "not on disk"):
        assert want in reasons, f"the report does not say {want!r}: {reasons}"
    # ---- the file in git ------------------------------------------------------
    got = json.loads(Path("collected/transfer_stations.json").read_text(encoding="utf-8"))
    short = TS.short_of("des_swf", got)
    assert not short, "; ".join(short)
    rows = [x for k, v in got.items() if not k.startswith("_") for x in v["stations"]]
    bad = [x["name"] for x in rows
           if x.get("owner_type") != "public" or x.get("kind") not in W.KINDS.values()
           or not (x.get("permit") and x.get("read_on")
                   and str(x.get("page") or "").startswith("https://onestop.des.nh.gov/"))]
    assert not bad, f"a station kept that is not public, or without its permit, day or page: {bad[:6]}"
    n = TS.counts("des_swf", got)
    return "ok", (f"{n['stations']} stations in {n['towns']} towns, each DES's public one with its "
                  "permit, day and page; the owner read off the page, never the name, and the shared "
                  "names in each of their towns")


@check("files", "each source of a town page's officials carries its copy's date in its own file, "
       "and the dates the pages and the board rule are written with agree with it",
       needs=("town_sources", "build_town_pages", "town_boards"))
def _town_sources_dated(TS, B, T):
    """WHAT A COPY IS AS OLD AS, KEPT WITH THE COPY (the freshness review,
    23 October 2026). town_boards.json and town_officials_web.json carried
    the day each page was read; the clerk list and NHDOT's directory carried
    none, so the day they were true as of lived in a constant in their
    parser and in the words of the page builder. Now every row carries it:
    the list's `read_on`, the export's own day, and the directory's `as_of`,
    its PDF's CreationDate. town_sources reads them, and the reminder
    (_town_sources_fresh) is only as good as they are.

    AND THE WORDS AND RULES WRITTEN AROUND ONE EDITION. The town pages say
    NHDOT's directory is "dated September 2025" and that its boards are from
    "before the 2026 town elections", and town_boards.py takes a town's own
    page as current only if it postdates MEETING (the March 2026 meeting)
    and a city's only after CITY_ELECTION (November 2025). Each is right for
    the copies on disk today, and each would stay as it is when a new copy
    is read: a September 2026 directory called "dated September 2025", or
    pages read in April 2027 held to the meetings of 2026. So each is held
    here to the date in the file it describes."""
    bad, said = [], []
    dates = {}
    for key in TS.SOURCES:
        data = TS.load(key)
        name, field = TS.SOURCES[key]["file"], TS.DATE_FIELD[key]
        if data is None:
            bad.append(f"{name} is not there")
            continue
        when, missing = TS.copy_date(key, data)
        if when is None:
            bad.append(f"no row of {name} carries {field}: run {TS.SOURCES[key]['writer']} again")
        elif missing:
            bad.append(f"{missing} rows of {name} carry no {field}")
        dates[key] = when
        said.append(f"{key} {when}")

    def meeting_after(d):
        m = TS.town_meeting(d.year)
        return m if m > d else TS.town_meeting(d.year + 1)

    def meeting_before(d):
        m = TS.town_meeting(d.year)
        return m if m <= d else TS.town_meeting(d.year - 1)

    def city_before(d):
        y = d.year if d.year % 2 else d.year - 1
        e = TS.general_election(y)
        return e if e <= d else TS.general_election(y - 2)

    d = dates.get("nhdot")
    if d:
        want = f"dated {d:%B %Y}"
        if not B.NHDOT.endswith(want):
            bad.append(f"build_town_pages.NHDOT reads {B.NHDOT!r}, and the directory in "
                       f"collected/town_officials.json is {want}")
        src = _source(B.__file__)
        years = set(re.findall(r"before the (\d{4}) town elections", src, re.I))
        first = meeting_after(d).year
        if years != {str(first)}:
            bad.append(f"build_town_pages.py says the directory's boards are from before the "
                       f"{' and '.join(sorted(years)) or 'no'} town elections, and the first "
                       f"after its date ({d}) are {first}'s")
    b = dates.get("town_sites")
    if b:
        m, c = meeting_before(b), city_before(b)
        if tuple(T.MEETING) != (m.year, m.month) or T.TERM_FLOOR != m.year:
            bad.append(f"town_boards.MEETING is {T.MEETING} and TERM_FLOOR {T.TERM_FLOOR}, and "
                       f"the last town meeting before the pages were read ({b}) was {m}")
        if tuple(T.CITY_ELECTION) != (c.year, c.month):
            bad.append(f"town_boards.CITY_ELECTION is {T.CITY_ELECTION}, and the last city "
                       f"election before the pages were read ({b}) was {c}")
    assert not bad, "\n  ".join(bad)
    return "ok", ("copies of " + ", ".join(said) + "; the pages' \"dated "
                  f"{dates['nhdot']:%B %Y}\" and town_boards' meeting of "
                  f"{T.MEETING[0]} agree with them")


@check("files", "the municipal officials' sources are due a reading after the town meetings, the "
       "cities' elections and a year, and before a general election, and on no other days",
       needs=("town_sources", "build_members_elect"))
def _town_sources_rule(TS, BME):
    """The rule _town_sources_fresh holds the real files to on the clock
    (town_sources.due), run here on fixed days, so a reminder that could
    never fire fails now rather than passing quietly through the day it was
    written for (_officials_recheck_rule's reason). The general election is
    BME's rule, the one the officials' reminder uses: two copies of one
    date must not part."""
    import datetime as _dt
    D = _dt.date
    assert TS.town_meeting(2026) == D(2026, 3, 10) and TS.town_meeting(2027) == D(2027, 3, 9), (
        "the town meetings of 2026 and 2027 are not March 10 and March 9")
    parted = [y for y in range(2024, 2034) if TS.general_election(y) != BME.general_election(y)]
    assert not parted, f"town_sources and build_members_elect date the November election of {parted} apart"
    sept20, cases = D(2026, 9, 20), []
    for key, as_of, day, looked, want in (
            # The copies of September 2026: nothing until the 2027 town meetings have had
            # their five weeks.
            ("sos_list", sept20, D(2026, 10, 23), None, False),
            ("sos_list", sept20, D(2027, 4, 12), None, False),
            ("sos_list", sept20, D(2027, 4, 13), None, True),
            ("town_sites", sept20, D(2027, 4, 12), None, False),
            ("town_sites", sept20, D(2027, 4, 13), None, True),
            ("town_sites", D(2027, 4, 20), D(2027, 4, 21), None, False),
            # A city's council read in May 2027: due after November 2027's elections and
            # their inaugurations.
            ("town_sites", D(2027, 5, 1), D(2028, 1, 10), None, False),
            ("town_sites", D(2027, 5, 1), D(2028, 1, 11), None, True),
            # The list's polling places, before a general election: a list read in July is
            # due sixty days before November 3, 2026, and not after the day.
            ("sos_list", D(2026, 7, 1), D(2026, 9, 3), None, False),
            ("sos_list", D(2026, 7, 1), D(2026, 9, 4), None, True),
            ("sos_list", D(2026, 7, 1), D(2026, 11, 3), None, True),
            ("sos_list", D(2026, 7, 1), D(2026, 11, 4), None, False),
            # The directory of September 2025: due since the 2026 town meetings; quiet for a
            # look that found nothing newer, until the next; a look to come is no look.
            ("nhdot", D(2025, 9, 2), D(2026, 10, 23), None, True),
            ("nhdot", D(2025, 9, 2), D(2026, 10, 23), D(2026, 10, 23), False),
            ("nhdot", D(2025, 9, 2), D(2027, 4, 13), D(2026, 10, 23), True),
            ("nhdot", D(2025, 9, 2), D(2026, 10, 23), D(2026, 11, 1), True),
            # A year whatever the calendar -- a list read on April 13, 2027 is 366 days
            # old five days before the 2028 meetings' date comes -- and a date that is none.
            ("sos_list", D(2027, 4, 13), D(2028, 4, 12), None, False),
            ("sos_list", D(2027, 4, 13), D(2028, 4, 13), None, True),
            ("sos_list", None, D(2026, 10, 23), None, True),
            ("sos_list", D(2026, 11, 1), D(2026, 10, 23), None, True)):
        said = TS.due(key, as_of, day, looked)
        if bool(said) != want:
            cases.append(f"{key} read {as_of}, on {day}" + (f", looked {looked}" if looked else "")
                         + (f": due ({said[:80]})" if said else ": not due"))
    assert not cases, "the rule is wrong on: " + "; ".join(cases)
    said = TS.due("nhdot", D(2025, 9, 2), D(2026, 10, 23))
    assert "March 10, 2026" in said and "416 days" in said, said
    said = TS.due("sos_list", D(2027, 4, 13), D(2028, 4, 13))
    assert said.startswith("the copy is 366 days old"), said
    assert TS.next_due("town_sites", sept20, D(2026, 10, 23)) == D(2027, 4, 13), (
        TS.next_due("town_sites", sept20, D(2026, 10, 23)))
    assert "_town_sources_fresh" in REMINDERS, (
        "_town_sources_fresh is not among the REMINDERS, which warn on the night and never hold it")
    return "ok", ("due five weeks after the town meetings, ten weeks after the cities' elections, "
                  "sixty days before a general election for the polling places, and after a year; "
                  "a look that found nothing newer counts as a reading")


@check("data", "the sources of the town pages' municipal officials are read again when the town "
       "meetings, the cities' elections or a year have passed since", needs=("town_sources",))
def _town_sources_fresh(TS):
    """A REMINDER, the register of probate paragraph's kind
    (_probate_after_the_vote), on the rule _town_sources_rule holds
    (town_sources.due): the Secretary of State's clerk list, NHDOT's
    directory and the towns' own websites are each read by a person, on no
    schedule, and the officials they name change at the town meetings in
    March, at the cities' elections in November of an odd year, and on any
    day an appointment is made. Nothing said when a copy had gone stale (the
    freshness review, 23 October 2026, found the directory of September
    2025 giving 154 towns' select boards seven months after the meetings
    that changed them). A data check and one of the REMINDERS: on the night
    it warns, on its own Healthchecks check, and never holds the site; on
    the laptop it fails until the copy is read again, or, for a copy no one
    can read again, until town_sources.LOOKED_ON records the day a person
    looked for a newer one and found none."""
    import build_date
    today = build_date.today()
    late, fine = [], []
    for key, r in TS.report(today):
        s = TS.SOURCES[key]
        if r["due"]:
            late.append(f"{key}, {s['file']} (its copy of {r['date']}): {r['due']}. To read it again, "
                        + s["again"].format(url=s["url"]))
        else:
            fine.append(f"{key} of {r['date']}, next due {r['next']}")
    assert not late, "\n  ".join(late) + ("\n  python3 src/towns/town_sources.py prints the "
                                          "whole map")
    return "ok", "; ".join(fine)


@check("build", "a town page names one clerk, the Secretary of State's",
       needs=("build_town_pages",))
def _town_one_clerk(B):
    """Thirty town pages named two clerks, and seven named two people.

    How to Vote names the clerk from the Secretary of State's list; NHDOT's
    directory names one too, on nineteen rows, and both were drawn. Windsor
    had Stephanie L Houle above and Melissa Merrill below. NHDOT's six
    "Town Administrator/ Town Clerk" rows are the worst of it: the Secretary
    of State names somebody else as clerk in all six. Two of the six are
    confirmed as administrators by a second source and are kept as that --
    Alton and Atkinson -- and the other four are not drawn.

    A board officer called Clerk is a different office and stays.
    """
    import html as _html
    import shell as S
    tmpl = S.template()
    town_rows = {
        "albany": [("Town Administrator/ Town Clerk", "Kelly Collins"),
                   ("Board of Selectman, Chair", "Kathy Golding")],
        "alton": [("Town Administrator/ Town Clerk", "Ryan Heath"),
                  ("Board of Selectman", "Andrew Morse")],
        "windsor": [("Town Clerk", "Melissa Merrill"),
                    ("Board of Selectman, Clerk", "Sean O'Keefe")],
        "manchester": [("City Clerk", "Matthew Normand"),
                       ("Mayor", "Jay Ruais")]}
    clerk = {"albany": "Sandra Vizard", "alton": "Jennifer Collins",
             "windsor": "Stephanie L Houle", "manchester": "Matthew Normand"}
    off = {"_offices": {k: {"officials": [
               {"position": p, "name": n, "phone": "", "email": ""}
               for p, n in rows]} for k, rows in town_rows.items()},
           "_local": {k: {"clerk": v, "polling_place": "Town Hall"}
                      for k, v in clerk.items()}}
    bad = []
    for key in town_rows:
        town = key.title()
        page = B.build(town, "0", {"0": {}}, {}, [], off, "https://x.test", tmpl)
        seats = re.findall(r'<span class="offseat">([^<]*)</span>', page)
        vote = [s for s in seats if s == "Town or city clerk"]
        other = [s for s in seats if s != "Town or city clerk"
                 and re.search(r"\b(?:town|city) clerk\b", s, re.I)]
        if len(vote) != 1 or other:
            bad.append(f"{town}: {len(vote)} How to Vote clerk rows, and "
                       f"{other} below")
        if f'<span class="mchip" translate="no">{clerk[key]}</span><span class="offseat">' \
                f'Town or city clerk' not in page:
            bad.append(f"{town}: the Secretary of State's clerk is not the one named")
    alton = B.build("Alton", "0", {"0": {}}, {}, [], off, "https://x.test", tmpl)
    if '<span class="mchip" translate="no">Ryan Heath</span><span class="offseat">Town Administrator</span>' not in alton:
        bad.append("Alton's administrator, confirmed by his own address, is not kept")
    albany = B.build("Albany", "0", {"0": {}}, {}, [], off, "https://x.test", tmpl)
    if "Kelly Collins" in albany:
        bad.append("Albany's combined row is drawn, and nothing confirms either half")
    windsor = B.build("Windsor", "0", {"0": {}}, {}, [], off, "https://x.test", tmpl)
    if "Melissa Merrill" in windsor:
        bad.append("Windsor names NHDOT's clerk beside the Secretary of State's")
    # The board's own officer is drawn as a member of the board -- without
    # the directory's officer label, which a board chooses again after each
    # election -- and is not taken for the town clerk.
    if "Sean O'Keefe" not in _html.unescape(windsor):
        bad.append("a board officer called Clerk was taken for the town clerk")
    assert not bad, "\n  ".join(bad)
    return "ok", "one clerk per page, the Secretary of State's; two administrators kept"


@check("build", "a town page's source note sends a reader to a website only when it links one",
       needs=("build_town_pages",))
def _town_note_website(B):
    """NHDOT records "no website" for Clarksville and Ellsworth and "website
    was discontinued" for Stewartstown, and their pages told a reader to
    check the town's own website for changes. The note names the website
    only when the page links one -- from NHDOT or from the Secretary of
    State's list -- and otherwise points at the town offices row above it.
    """
    import html as _html
    import shell as S
    tmpl = S.template()
    row = [{"position": "Board of Selectman", "name": "Pat Doe",
            "phone": "", "email": ""}]
    off = {"_offices": {
               "clarksville": {"officials": row, "website": "no website",
                               "phone": "603-246-7751"},
               "lyme": {"officials": row, "website": "www.lymenh.gov"},
               "hart": {"officials": row},
               "bath": {"officials": row}},
           "_local": {"hart": {"website": "https://www.hartnh.gov"},
                      "bath": {}}}
    want = {"Clarksville": ", so ask the town offices for changes.",
            "Lyme": ", so check Lyme's own website for changes.",
            "Hart": ", so check Hart's own website for changes.",
            "Bath": "."}
    bad = []
    for town, end in want.items():
        page = B.build(town, "0", {"0": {}}, {}, [], off, "https://x.test", tmpl)
        # Each of NHDOT's cards on the Town officials tab says it is dated;
        # the LAST says where to look for changes, and only the last, so a
        # reader is told once.
        ends = [_html.unescape(e) for e in re.findall(
            r"It does not show anyone elected or appointed since "
            r"then([^<]*)</p>", page)]
        got = ends[-1] if ends else None
        if got != end:
            bad.append(f"{town}: the note ends {got!r}, not {end!r}")
        if any(e != "." for e in ends[:-1]):
            bad.append(f"{town}: where to look for changes is said "
                       f"{len([e for e in ends if e != '.'])} times")
    assert not bad, "\n  ".join(bad)
    return "ok", "website named on 2 fixture pages that link one, not on 2 that do not"


@check("build", "a town's own page gives its select board current and screened, and a part of it labelled",
       needs=("town_boards", "parse_town_sites"))
def _town_boards_decide(T, P):
    """The person's rules of 24 September 2026, run on the layouts they were
    written from.

    Every town page showed NHDOT's directory of September 2025, and at least
    68 towns' own pages list a selectman it still shows. A town's own dated
    roster wins where it was CURRENT when read, and only names that survive
    the screen. A page that lists PART of the board is shown too, marked
    partial -- but only a part the page gives, never a part this failed to
    read. Each fixture below is a real page's layout, cut down, and each
    outcome is one the rule exists for:

      Lyme       the whole board, read off the town's page: published
      Wentworth  headed "For the year ending December 2024": not
      a term that ran out at the 2026 meeting, read in September: not
      Goffstown  a phone line between a member and their term, and "2024
                 through 2027" read as 2027: all five
      Hancock    report titles below the roster are not the page's date
      Temple     "Contact Leala Kullgren" is not a selectman
      Milan      "Lynn Dube, Administrative Assistant" is not a selectman
      Carroll    "(resigned 4/21/2026)" is not a selectman
      Campton    five names, a directory of four and no size stated:
                 published, partial, with no size
      Bow        "a five member Board of Selectmen" is the size to meet
      Columbia   the directory's own three, no date and no term: not -- its
                 minutes swear in a selectman the page never added
      Winchester the directory's own five, with a term ending 2029: published
      two pages  a name on another of the town's pages the first lacks: not
      a list of committees is not the board's page
      Belmont    each name with "Chairman", "Elected" and a term on the lines
                 under it: all five, where one was read
      Alstead    the whole board on one line, and its staff after: three
      Greenland  "Planning Board Alternate Rep" is a selectman sent there
      Harrisville  minutes that name the board above the roster
      Farmington a CivicPlus "Staff Contacts" heading over the board, on the
                 board's own page
      Littleton  five on the page where the directory had three: partial,
                 with no size, because the directory's count is not one
      a part     two of a stated three, the third nowhere on the page:
                 published, "2 of 3"
      two gaps   a name the page gives that this did not read -- one the
                 directory knows, one it does not: not published as partial

    These run through parse_town_sites.from_headings, so a parser change
    that stops reading a layout shows here as a board that stopped being
    published, not as silence.
    """
    read = "2026-09-20T22:22:15-0400"

    def dot(*names):
        return {"officials": [
            {"position": "Board of Selectman" + (", Chair" if i == 0 else ""),
             "name": nm, "phone": "", "email": ""} for i, nm in enumerate(names)]}

    def town(pages, d):
        found, lines = [], {}
        for url, ls in pages.items():
            lines[url] = ls
            page = {"url": url, "read_on": read, "link_text": ""}
            found += [(o, p, page)
                      for o, p in P.from_headings(ls, P.page_office(url))]
        return T.decide("x", found, d, lambda u: lines.get(u, []),
                        list(pages.values()))

    cases = [
        ("Lyme", "own", ["Ben Kilham", "David Kahn", "Michael Hinsely"], town(
            {"https://lyme.test/pages/select-board": [
                "Select Board", "Staff Contacts:",
                "Dina Cutting - Town Administrator - (603) 795-4639",
                "Board Members:", "Ben Kilham - Chair until 2028",
                "David Kahn - Vice Chair until 2027",
                "Michael Hinsely - Member until 2029"]},
            dot("Judith Brotman", "Ben Kilham", "David Kahn"))),
        ("Wentworth", "directory", None, town(
            {"https://wentworth.test/town-officials": [
                "Wentworth Town Officials", "For the year ending December 2024",
                "Select Board", "Arnold D. Scheller, Chairperson, 2027",
                "Brian DuBois, 2027", "Rick Ducheneau, Sr., 2028"]},
            dot("Arnold Scheller", "Brian DuBois", "Rick Ducheneau"))),
        ("an ended term", "directory", None, town(
            {"https://ended.test/select-board": [
                "Select Board", "Ann Aldous, Chair, Term expires 2026",
                "Bea Brandt, Term expires 2027", "Cal Carver, Term expires 2028"]},
            dot("Ann Aldous", "Bea Brandt", "Cal Carver"))),
        ("Goffstown", "own", ["Jim Craig", "Joshua Douglas", "Allison DeCesere",
                              "Mark T. Lemay", "Richard Manzo"], town(
            {"https://goffstown.test/381/Select-Board": [
                "Select Board", "Committee Members", "Jim Craig, Chairman",
                "Phone: 603-361-4253", "Term: 2024 through 2027",
                "Joshua Douglas, Vice Chairman", "Term: 2025 through 2028",
                "Allison DeCesere, Selectwoman", "Phone: 603-759-5334",
                "Term: 2026 through 2029", "Mark T. Lemay, Selectman",
                "Phone: 603-305-0507", "Term: 2024 through 2027",
                "Richard Manzo, Selectman", "Phone: 603-289-5929",
                "Term: 2025 through 2028", "Staff Liason", "Derek Horne",
                "Town Administrator"]},
            dot("Peter Georgantas", "Jim Craig", "Joshua Douglas", "Mark Lemay",
                "Richard Manzo"))),
        ("Hancock", "own", ["Virginia Smith", "Peter Webster",
                            "Elisabeth Villaume"], town(
            {"https://hancock.test/selectboard/index.php": [
                "Selectboard Members", "Virginia Smith, Member (2028)",
                "Peter Webster, Member (2029)", "Elisabeth Villaume, Chair (2027)",
                "Town Reports", "Year Ending December 31, 2013"]},
            dot("Virginia Smith", "Elisabeth Villaume", "Jeff Brown"))),
        ("Temple", "own", ["Ken Caisse", "George Willard", "Clayton Lennarz"], town(
            {"https://temple.test/258/Select-Board": [
                "Select Board", "Contact Leala Kullgren - board@temple.test",
                "Members", "Ken Caisse, SB Chair", "Term Expires: 2027",
                "George Willard, SB Member", "Term Expires: 2028",
                "Clayton Lennarz, SB Member", "Term Expires 2029",
                "Leala Kullgren, SB Assistant"]},
            dot("Bill Ezell", "George Willard", "Ken Caisse"))),
        ("Milan", "own", ["Peter Nolet", "Jason Huter", "Dana Brouillette"], town(
            {"https://milan.test/government": [
                "Selectmen's Office", "Peter Nolet, Chairman", "Jason Huter",
                "Dana Brouillette", "Lynn Dube, Administrative Assistant"]},
            dot("Randy Fortin", "Kenneth Lee Dube", "Peter Nolet"))),
        ("Carroll", "own", ["Brian Mycko", "Bonnie Moroney", "Aaron Foti"], town(
            {"https://carroll.test/boards-and-committees/board-of-selectmen/": [
                "Board of Selectmen", "Brian Mycko, 2028 - Chairman",
                "Bonnie Moroney, 2027 - Selectperson",
                "Aaron Foti, 2027 - Selectman (appointed 5/5/2026)",
                "Jules Marquis, 2029 - Selectman (resigned 4/21/2026)"]},
            dot("John Greer", "Bonnie Moroney", "Jules Marquis"))),
        ("Campton", "own", ["Sharon Davis", "Mort Donahue", "Karl Kelly",
                            "Sherrill Howard", "Jade Hartsgrove"], town(
            {"https://campton.test/board_of_selectmen.php": [
                "Board of Selectmen", "Sharon Davis - Chair",
                "Mort Donahue - Vice Chair", "Karl Kelly - Selectman",
                "Sherrill Howard - Selectman", "Jade Hartsgrove - Selectman"]},
            dot("Sharon Davis", "Karl Kelly", "Mort Donahue", "Sherrill Howard"))),
        ("Bow", "own", ["Kip McDaniel", "Ian Flanagan", "Angela Brennan",
                        "Eleana Colby", "Christopher Nicolopoulos"], town(
            {"https://bow.test/283/Board-of-Selectmen": [
                "Board of Selectmen", "Kip McDaniel, Chairman (2027)",
                "Ian Flanagan, Vice Chair (2027)", "Angela Brennan, (2028)",
                "Eleana Colby, (2029)", "Christopher Nicolopoulos, (2028)",
                "The Town of Bow is governed by a five member Board of "
                "Selectmen elected to staggered three year terms."]},
            dot("Kip McDaniel", "Angela Brennan", "Christopher Nicolopoulos"))),
        ("Columbia", "directory", None, town(
            {"https://columbia.test/selectmen/": [
                "Selectmen", "Norman Cloutier, Chairman", "Eric Stohl",
                "Donald Campbell",
                "Selectmen’s Meetings are held on the 2nd & 4th Wednesdays "
                "of each month beginning at 6:00 pm at the Columbia Town "
                "Office."]},
            dot("Norman Cloutier", "Donald Campbell", "Eric Stohl"))),
        ("Winchester", "own", ["Ben Kilanski", "Trevor Croteau",
                               "Herbert C. Stephens", "Jack Marsh",
                               "Theresa Sepe"], town(
            {"https://winchester.test/1389/Board-of-Selectmen": [
                "Board of Selectmen", "Staff Contacts",
                "Karey Miner - Town Administrator", "Board Members",
                "Ben Kilanski - Chair", "Term Expires: 2029",
                "Trevor Croteau - Vice Chair", "Term Expires: 2028",
                "Herbert C. Stephens - Member", "Term Expires: 2028",
                "Jack Marsh - Member", "Term Expires: 2027",
                "Theresa Sepe - Member", "Term Expires: 2027"]},
            dot("Ben Kilanski", "Herbert Stephens", "Jack Marsh",
                "Theresa Sepe", "Trevor Croteau"))),
        # The first page is read whole and is current, so the second page's
        # extra name is the only thing that keeps this town off its roster.
        ("two pages", "directory", None, town(
            {"https://two.test/select-board": [
                "Select Board", "Ann Aldous, Chair (2027)",
                "Bea Brandt, Member (2028)", "Cal Carver, Member (2029)"],
             "https://two.test/town-officials": [
                "Board of Selectmen", "Dee Dunmore, Selectman (2028)"]},
            dot("Ann Aldous", "Bea Brandt", "Cal Carver"))),
        ("a committees list", "directory", None, town(
            {"https://list.test/boards-and-committees": [
                "Board of Selectmen", "Ann Aldous, Chair", "Bea Brandt",
                "Cal Carver"]},
            dot("Ann Aldous", "Bea Brandt", "Cal Carver"))),
        ("Belmont", "own", ["Ruth Mooney", "Travis O’Hara", "Jon Pike",
                            "Mark Lewandoski", "Sharon Ciampi"], town(
            {"https://belmont.test/boards/board-of-selectmen/": [
                "Belmont Board of Selectmen", "Send Email", "Board Members",
                "Ruth Mooney", "Chairman", "Elected", "Term Expiration: 2027",
                "Travis O’Hara", "Vice Chairman", "Elected",
                "Term Expiration: 2029", "Jon Pike", "Board Member", "Elected",
                "Term Expiration: 2028", "Mark Lewandoski", "Board Member",
                "Elected", "Term Expiration: 2029", "Sharon Ciampi",
                "Board Member", "Elected", "Term Expiration: 2027",
                "Member vacancies are filled by election by the voters in "
                "March as terms expire."]},
            dot("Ruth Mooney", "Claude Patten, Jr", "Jon Pike", "Sharon Ciampi",
                "Travis O'Hara"))),
        ("Alstead", "own", ["Joe Levesque", "Joel McCarty", "David Hogan"], town(
            {"https://alstead.test/departments": [
                "Select Board Office",
                "Joe Levesque - Chair, Joel McCarty - Full Member, David "
                "Hogan - Full Member",
                "Misty Gratacos - Select Board Office Administrator, Work "
                "(603) 835-2986",
                "Select Board Meetings: Every Tuesday, 5:00 p.m, at the Town "
                "Hall."]},
            dot("Joel McCarty", "Gordon Kemp", "Matt Saxton"))),
        ("Greenland", "own", ["Laura Malloy", "Paul Stanley", "Stephan Toth",
                              "Heather Droesch", "Zack Pike"], town(
            {"https://greenland.test/1466/Board-of-Selectmen": [
                "Board of Selectmen", "Laura Malloy, Chairman",
                "Term Expires: March 2029", "Paul Stanley, Vice Chairman",
                "Term Expires: March 2029",
                "Stephan Toth, Planning Board Alternate Rep",
                "Term Expires: March 2027", "Heather Droesch, Planning Board Rep",
                "Term Expires: March 2028", "Zack Pike, Member",
                "Term Expires: March 2028", "Overview"]},
            dot("Laura Malloy", "Heather Droesch", "Paul Stanley", "Stephan Toth",
                "Zach Pike"))),
        ("Harrisville", "own", ["Andrew Maneval", "Kathleen Scott",
                                "Andrea Hodson"], town(
            {"https://harrisville.test/government/office-of-the-selectboard/": [
                "Select Board Tuesday, September 8, 2026 Meeting Minutes Select "
                "Board: Andrew Maneval, Andrea Hodson, Kathy Scott Recording "
                "Secretary: Mary Ann Noyer", "Read More", "Select Board",
                "Andrew Maneval, Chair (2029)", "Kathleen Scott (2027)",
                "Andrea Hodson (2028)",
                "Administrative Assistant – Mary Ann Noyer"]},
            dot("Andrew Maneval", "Andrea Hodson", "Kathleen Scott"))),
        ("Farmington", "own", ["Charlie King", "Douglas Staples", "John Scruton",
                               "Ann Titus", "Jason Chapman"], town(
            {"https://farmington.test/1368/Board-of-Selectmen": [
                "Board of Selectmen", "Meetings", "Staff Contacts",
                "Charlie King, Chairman", "Term Expires: 2028",
                "Douglas Staples, Vice Chairman", "Term Expires: 2027",
                "John Scruton, Selectman", "Term Expires: 2028",
                "Ann Titus, Selectman", "Term Expires: 2027",
                "Jason Chapman, Selectman", "Term Expires: 2029", "Overview"]},
            dot("Gerry Vachon", "Ann Titus", "Charlie King", "Douglas Staples",
                "Jason Chapman"))),
        ("Littleton", "own", ["David Harkless", "Kerri Harrington",
                              "Paul Lehmann", "Taylor Caswell", "Ed Cherian"],
         town({"https://littleton.test/1296/Board-of-Selectmen": [
             "Board of Selectmen", "Board Members",
             "David Harkless, Member (2027)", "Kerri Harrington, Chair (2027)",
             "Paul Lehmann, Vice Chair (2028)", "Taylor Caswell, Member (2029)",
             "Ed Cherian, Member (2029)"]},
            dot("Linda Macneil", "Kerri Harrington", "Roger Emerson"))),
        ("a part", "own", ["Ann Aldous", "Bea Brandt"], town(
            {"https://part.test/select-board": [
                "Select Board", "The Select Board is a three member board.",
                "Ann Aldous, Chair (2029)", "Bea Brandt (2028)", "Overview"]},
            dot("Cal Carver", "Bea Brandt", "Dee Dunmore"))),
        ("a gap the directory knows", "directory", None, town(
            {"https://gap.test/select-board": [
                "Select Board", "Ann Aldous, Chair (2029)", "Bea Brandt (2028)",
                "Photo: the board at Town Meeting", "Cal Carver (2027)"]},
            dot("Ann Aldous", "Bea Brandt", "Cal Carver"))),
        ("a gap it does not", "directory", None, town(
            {"https://gap2.test/select-board": [
                "Select Board", "Ann Aldous, Chair (2029)", "Bea Brandt (2028)",
                "Photo: the board at Town Meeting", "Cal Carver (2027)"]},
            dot("Ann Aldous", "Bea Brandt", "Zed Zimmer"))),
        # A table read as lines: its header row, then each member's name,
        # an "Email" link and the year the term ends.
        ("Hampton", "own", ["Carleigh Beriont", "Chuck Rage", "Amy Hansen",
                            "Jeff Grip", "Donald Bliss"], town(
            {"https://hampton.test/282/Select-Board": [
                "Select Board", "Name", "Email", "Term Expires",
                "Carleigh Beriont, C hairwoman", "Email Carleigh Beriont",
                "2027", "Chuck Rage", "Email Chuck Rage", "2029", "Amy Hansen",
                "Email Amy Hansen", "2028", "Jeff Grip, Vice-chairman",
                "Email Jeff Grip", "2027", "Donald Bliss", "Email Donald Bliss",
                "2029"]},
            dot("Rusty Bridle", "Amy Hansen", "Carleigh Beriont", "Charles Rage",
                "Jeffery Grip"))),
        # Two of the directory's three, undated and without terms: a part
        # of the board lacks somebody by being a part, so the missing name
        # is no evidence the page is newer than the directory.
        ("a stale part", "directory", None, town(
            {"https://stale.test/select-board": [
                "Select Board", "The Select Board is a three member board.",
                "Ann Aldous, Chair", "Bea Brandt, Member", "Overview"]},
            dot("Ann Aldous", "Bea Brandt", "Cal Carver"))),
    ]
    bad = []
    for label, want, names, got in cases:
        if got["case"] != want:
            bad.append(f"{label}: {got['case']}, not {want} ({got['why']})")
        elif names is not None:
            have = [m["name"] for m in got["members"]]
            if have != names:
                bad.append(f"{label}: publishes {have}, not {names}")
    # Each "not" above for the reason it exists, not an earlier one that
    # happens to catch the fixture too.
    why = {label: got["why"] for label, _, _, got in cases}
    for label, words in (("two pages", "another of the town's pages"),
                         ("Columbia", "the directory's own board"),
                         ("a gap the directory knows", "did not read"),
                         ("a gap it does not", "did not read"),
                         ("a stale part", "the directory's own board")):
        if words not in why[label]:
            bad.append(f"{label} is kept off its roster for another reason: "
                       f"{why[label]!r}")
    # Partial where the page gives part, with the size's source or none;
    # whole everywhere else.
    got = {label: g for label, _, _, g in cases}
    for label, size in (("a part", 3), ("Campton", None), ("Littleton", None)):
        g = got[label]
        if not g.get("partial") or g.get("size") != size:
            bad.append(f"{label}: partial={g.get('partial')} size="
                       f"{g.get('size')}, not partial with size {size}")
    for label in ("Lyme", "Goffstown", "Belmont", "Greenland", "Farmington"):
        if got[label].get("partial"):
            bad.append(f"{label}: a whole board is marked partial")
    belmont = (got["Belmont"].get("members") or []) + [{}, {}]
    if (belmont[0].get("role"), belmont[1].get("directory_name")) != \
            ("Chairman", "Travis O'Hara"):
        bad.append("Belmont's chair is not read off the line under her name, "
                   "or O’Hara is not the directory's O'Hara: "
                   f"{belmont[0].get('role')!r}, {belmont[1].get('directory_name')!r}")
    v, why_ = T.screen(T.BOARD, {"name": "Andrew Lawn"},
                       {"url": "https://jaffrey.test/558/Select-Board"},
                       ["Andrew Lawn", "Selectman"])
    if v != "keep":
        bad.append(f"Jaffrey's selectman Andrew Lawn is screened off: {why_}")
    # The people who work for a board are not on it, and not counted
    # against its seats: Alstead's three staff lines each name the select
    # board, and read as members they made six, over the cap of five, and the
    # whole board was dropped.
    staff = P.from_headings([
        "Select Board Office",
        "Joe Levesque - Chair, Joel McCarty - Full Member, David Hogan - Full "
        "Member",
        "Misty Gratacos - Select Board Office Administrator, Work (603) "
        "835-2986",
        "Sharon Iozzo - Assistant Select Board Office Administrator",
        "Shelley Steuwe - Select Board Recording Secretary"])
    names = [q["name"] for o, q in staff if o == T.BOARD]
    if names != ["Joe Levesque", "Joel McCarty", "David Hogan"]:
        bad.append(f"Alstead's select board reads as {names}")
    lyme = cases[0][3]
    if [m.get("directory_name") for m in lyme.get("members") or []] != \
            ["Ben Kilham", "David Kahn", None]:
        bad.append("Lyme's members are not matched to the directory's rows for "
                   "the same people, so their phones and e-mail are lost")
    if not T.same_person("Don Milbrand", "Don Millbrand") or \
            T.same_person("Don Milbrand", "Dan Millbrand"):
        bad.append("Bristol's Don Milbrand is not the directory's Don "
                   "Millbrand, or a name two letters out is the same person")
    for text, year in (("Term: 2024 through 2027", "2027"), ("2025 - 2028", "2028"),
                       ("Term Expires: March 2027", "2027")):
        if P.term_year(text) != year:
            bad.append(f"{text!r} ends in {P.term_year(text)}, not {year}")
    for name in ("Stratham Community Garden", "President Wilshire", "Quick Links"):
        v, _ = T.screen(T.BOARD, {"name": name},
                        {"url": "https://s.test/select-board"}, [name])
        if v != "reject":
            bad.append(f"{name!r} passes the screen as a selectman")
    # A NAME WRITTEN WHOLLY IN CAPITALS IS SET IN NORMAL CASE (the person, 24
    # September 2026), carefully. Where no rule knows the case -- MacDonald
    # or Macdonald -- a spelling on disk decides, and failing that it is
    # cased the ordinary way and reported as a guess.
    guessed = []
    for raw, want, known in (
            ("IAN O'REILLY", "Ian O'Reilly", None),
            ("TOM MCDONALD", "Tom McDonald", None),
            ("MARY SMITH-JONES", "Mary Smith-Jones", None),
            ("JOHN SMITH JR.", "John Smith Jr.", None),
            ('ROBERT "BUBBA" ELLIS', 'Robert "Bubba" Ellis', None),
            ("W. WILLIAM HUTWELKER III", "W. William Hutwelker III", None),
            ("O.J. ROBINSON", "O.J. Robinson", None),
            ("JANE MACDONALD", "Jane MacDonald", {"MACDONALD": "MacDonald"}),
            ("JANE MACDONALD", "Jane Macdonald", None),
            ("JR SMITH", "JR Smith", None),
            ("ANNA DIPIETRO", "Anna DiPietro", {"DIPIETRO": "DiPietro"}),
            ("ANNA DIPIETRO", "Anna Dipietro", None),
            ("Sara Hamilton", "Sara Hamilton", None),
            ("James Bailey III", "James Bailey III", None)):
        got_ = T.display_name(raw, known, guessed)
        if got_ != want:
            bad.append(f"{raw!r} is set as {got_!r}, not {want!r}")
    if guessed != ["MACDONALD", "DIPIETRO"]:
        bad.append(f"the cases guessed are {guessed}, not the Macdonald and "
                   "the Dipietro no list on disk settled")
    # A plain spelling is a spelling: one list's "Leclerc" and another's
    # "LeClerc" settle nothing. And the clerks are not read: the Secretary
    # of State gives them in capitals, so their case is the rule
    # parse_clerks.namecase applied, not anybody's spelling.
    root = Path(tempfile.mkdtemp(prefix="gr-spell-"))
    _mk(root / "generated" / "careers.json").write_text(json.dumps(
        {"a": {"name": "Paul LeClerc"}, "b": {"name": "Ann DiPietro"}}),
        encoding="utf-8")
    _mk(root / "collected" / "town_officials.json").write_text(json.dumps(
        {"x": {"officials": [{"name": "Brian Leclerc"},
                             {"name": "Tom Macdonald"}]}}), encoding="utf-8")
    _mk(root / "collected" / "town_clerks.json").write_text(json.dumps(
        {"y": {"clerk": "Joe MacHado", "clerk_raw": "JOE MACHADO"}}),
        encoding="utf-8")
    ks = T.known_spellings(root)
    shutil.rmtree(root, ignore_errors=True)
    if "LECLERC" in ks or ks.get("DIPIETRO") != "DiPietro" or \
            ks.get("MACDONALD") != "Macdonald" or "MACHADO" in ks:
        bad.append(f"the spellings on disk are read as {ks}")
    assert not bad, "\n  ".join(bad)
    return "ok", (f"{len(cases)} layouts decided as the rule says, terms read to "
                  "their end, non-names screened out, capitals recased")


@check("build", "a city's own page gives its mayor and council, each in the seat the page names",
       needs=("town_boards",))
def _town_council_read(T):
    """The cities follow the towns' rule (the person, 24 September 2026), and
    a council page is laid out differently from a select board's: a seat
    under the name, over it, on the same line, or -- Dover -- the first name,
    the surname and the role on three lines. Every city held an election
    after the directory's September 2025 edition, and the city's own page
    already named a different mayor in Dover and Laconia.

    Each layout below is a real city's page, cut down; each must give its
    members in the seats the page names, and nobody else on the page: not
    Nashua's Legislative Affairs Manager, not Portsmouth's school board or
    its ward registrars, and not the ward in "Councilor, Ward I", which has
    the shape of a name.
    """
    read = "2026-09-20T22:22:15-0400"
    layouts = [
        ("Concord", ["Members", "Mayor", "Byron Champlin", "Ward Councilors",
                     "Brent Todd, Ward One", "Michele Horne, Ward Two",
                     "Mark Davie, Ward Four", "At-Large Councilors",
                     "Nathan Fennessy", "Amanda Grady Sexton",
                     "Government Websites by CivicPlus®"],
         [("Byron Champlin", "Mayor"), ("Brent Todd", "Ward 1"),
          ("Michele Horne", "Ward 2"), ("Mark Davie", "Ward 4"),
          ("Nathan Fennessy", "At large"), ("Amanda Grady Sexton", "At large")]),
        ("Claremont", ["Dale Girard", "Mayor", "(603) 558-0860", "Contact Dale",
                       "(dgirard@council.claremontnh.com)", "×", "Submit",
                       "A copy of this message will be sent to your email "
                       "address.", "Andrew O'Hearne", "Councilor, Ward I",
                       "William Limoges", "Councilor, At Large",
                       "Click here to contact everyone on the City Council at "
                       "once."],
         [("Dale Girard", "Mayor"), ("Andrew O'Hearne", "Ward 1"),
          ("William Limoges", "At large")]),
        ("Laconia", ["Councilors", "Mayor - Mike Bordes", "Jon Hildreth, Ward 1",
                     "Mike Conant , Ward 6", "Overview"],
         [("Mike Bordes", "Mayor"), ("Jon Hildreth", "Ward 1"),
          ("Mike Conant", "Ward 6")]),
        ("Lebanon", ["Mayor Douglas Whittlesey",
                     "Assistant Mayor Devin R. Wilkie",
                     "Councilor Kellen Appleton", "Home", "City Councilors",
                     "Douglas Whittlesey", "Mayor, Ward 1 (Term Expires: 3/27)",
                     "Devin R. Wilkie",
                     "Assistant Mayor, Ward 2 (Term Expires: 3/27)",
                     "Kellen Appleton",
                     "Councilor, At-Large (Term Expires: 3/28)"],
         [("Douglas Whittlesey", "Mayor, Ward 1"),
          ("Devin R. Wilkie", "Assistant mayor, Ward 2"),
          ("Kellen Appleton", "At large")]),
        ("Keene", ["Ward 1", "Jacob R. Favolise",
                   "Councilor Ward 1 – 2026 to 2027", "603-338-8880",
                   "jfavolise@keenenh.gov",
                   "Member: Municipal Services, Facilities and Infrastructure "
                   "Committee", "Ward 5", "Philip M. Jones",
                   "Councilor Ward Five – 2026 to 2029", "At-Large",
                   "Bettina A. Chadbourne", "Councilor At Large – 2026 to 2027",
                   "For locations of the City wards, please view the City Ward "
                   "Map."],
         [("Jacob R. Favolise", "Ward 1"), ("Philip M. Jones", "Ward 5"),
          ("Bettina A. Chadbourne", "At large")]),
        ("Nashua", ["DIRECTORY:", "Lori Wilshire", "Alderman-At-Large President",
                    "Email", "Phone: 603-809-4203", "More Information",
                    "Ward 1 - James Ravan", "Alderman - Ward 1", "Email",
                    "Donna L. Graham", "Legislative Affairs Manager", "Email"],
         [("Lori Wilshire", "At large"), ("James Ravan", "Ward 1")]),
        ("Portsmouth", ["CITY COUNCIL (City Charter, Art. IV, Sec. 4.1 - Elected "
                        "at large, 2 Year Terms)", "Deaglan McEachern", "Mayor",
                        "Portsmouth, NH 03801", "2026-2027", "Kate Cook",
                        "Councilor", "Portsmouth, NH 03801", "2026-2027",
                        "SCHOOL BOARD (City Charter, Art. VI, Sec. 6.3-a, 4 Year "
                        "Terms)", "Byron Matto", "School Board Member",
                        "Ward 1", "Penny Reynolds", "Registrar"],
         [("Deaglan McEachern", "Mayor"), ("Kate Cook", "")]),
        ("Dover", ["Current Members", "Dennis", "Shanahan", "Role: Mayor",
                   "Term Begin: 1/5/2026", "Term End: 1/3/2028", "hideThis",
                   "April", "Richer", "Role: City Councilor, Ward 1",
                   "Term End: 1/3/2028", "Richard L.", "Robison, Jr.",
                   "Role: City Councilor, Ward 5"],
         [("Dennis Shanahan", "Mayor"), ("April Richer", "Ward 1"),
          ("Richard L. Robison, Jr.", "Ward 5")]),
        # Each seat ABOVE its holder, the next seat straight under the name.
        # Read as Keene's "seat under the name", every alderman moved one
        # ward on, Ward 12's became at-large, and the last was dropped
        # (fetched 25 September 2026, before anything was published).
        ("Manchester", ["Aldermen", "Aldermen Email List", "Ward  1 Alderman",
                        "Bryce Kaw-uh", "Ward  2 Alderman", "Dan Goonan",
                        "Ward 12 Alderman", "Kelly Thomas", "At-Large Alderman",
                        "Dan O'Neil", "At-Large Alderman", "June Trisciani",
                        "Mayor and Aldermen Related Links", "Committees"],
         [("Bryce Kaw-uh", "Ward 1"), ("Dan Goonan", "Ward 2"),
          ("Kelly Thomas", "Ward 12"), ("Dan O'Neil", "At large"),
          ("June Trisciani", "At large")]),
    ]
    bad = []
    got = {}
    for city, lines, want in layouts:
        got[city] = T.read_council(lines)
        have = [(m["name"], m["seat"]) for m in got[city]]
        if have != want:
            bad.append(f"{city}: reads {have}, not {want}")
    if [m.get("role") for m in got["Nashua"]][:1] != ["President"]:
        bad.append("Nashua's president of the board of aldermen lost the office")
    # Lebanon's mayor is also one of Ward 1's two councillors: the seat the
    # page says more fully, lower down, is the one kept. And its "Term
    # Expires: 3/27" is March 2027.
    terms = {c: [m.get("term_expires") for m in got[c]]
             for c in ("Dover", "Keene", "Lebanon")}
    if terms["Dover"][:1] != ["2028"] or \
            terms["Keene"] != ["2027", "2029", "2027"] or \
            terms["Lebanon"] != ["2027", "2027", "2028"]:
        bad.append(f"a council term is read off its start, or not read: {terms}")
    for text, want in (
            ("The Keene City Council consists of 16 members: Two in each of "
             "the five wards, plus five at-large members, and the Mayor as the "
             "Chair.", (16, True)),
            ("The City Council consists of nine (9) councilors elected at large "
             "for terms of two (2) years.", (9, False)),
            ("A nine-member City Council is elected for two-year terms.",
             (9, False)),
            ("All of the powers of the city shall be vested in a Council of nine "
             "Councilors, one Councilor from each ward, two Councilors at Large, "
             "and one Councilor to serve as Mayor.", (9, True)),
            ("The Board of Aldermen consists of 9 ward aldermen elected for a "
             "term of 2 years at every municipal election and 6 at-large "
             "aldermen elected for a term of 4 years, 3 of which are elected "
             "at each municipal election.", (15, False))):
        if T.stated_council_size([text]) != want:
            bad.append(f"{text[:48]!r}... states {T.stated_council_size([text])}, "
                       f"not {want}")
    # The rule, on Keene: sixteen, the mayor named on another of the city's
    # pages and counted because the council's own sentence counts him; and a
    # page naming the directory's council unchanged, with nothing later on
    # it, is not published.
    dot = {"officials": [{"position": "Mayor", "name": "Jay Kahn"}]
           + [{"position": f"City Councilor, Ward {w}", "name": n}
              for w, n in ((1, "Jacob Favolise"), (5, "Philip Jones"),
                           (5, "Thomas Powers"))]}
    council = ["The Keene City Council consists of 4 members, and the Mayor "
               "as the Chair.", "Ward 1", "Jacob R. Favolise",
               "Councilor Ward 1 – 2026 to 2027", "Ward 5", "Philip M. Jones",
               "Councilor Ward Five – 2026 to 2029", "Molly V. Ellis",
               "Councilor Ward Five – 2026 to 2029", "The end."]
    v = T.decide_council("keene", [
        {"url": "https://keene.test/my-city-government/city-council/",
         "read_on": read, "lines": council},
        {"url": "https://keene.test/my-city-government/", "read_on": read,
         "lines": ["Mayor:", "Mayor Jay Kahn"]}], dot)
    if v["case"] != "own" or v.get("partial") or \
            [m["name"] for m in v["members"]][:1] != ["Jay Kahn"] or \
            v["members"][0].get("source_url") != "https://keene.test/my-city-government/":
        bad.append(f"Keene's own council and its mayor from another page are "
                   f"not published whole: {v['case']} {v['why']}")
    # A part of a council whose sentence leaves the mayor out, with the
    # mayor from another page: he is shown and not counted, so it is 2 of
    # Nashua's 15 aldermen, not 3.
    part = T.decide_council("nashua", [
        {"url": "https://nashua.test/260/Board-of-Aldermen", "read_on": read,
         "lines": ["The Board of Aldermen consists of 9 ward aldermen and 6 "
                   "at-large aldermen.", "Lori Wilshire",
                   "Alderman-At-Large President", "Ward 1 - James Ravan",
                   "Alderman - Ward 1", "The end."]},
        {"url": "https://nashua.test/804/City-Officials", "read_on": read,
         "lines": ["Meet Mayor Jim Donchess"]}],
        {"officials": [{"position": "Mayor", "name": "Jim Donchess"}]})
    if part["case"] != "own" or not part.get("partial") or \
            (part.get("read"), part.get("size"), len(part["members"])) != (2, 15, 3):
        bad.append("a part of a council, its mayor from another page, is not "
                   "counted without him: "
                   f"{part['case']} {part['why']} read {part.get('read')} of "
                   f"{part.get('size')}")
    same = T.decide_council("x", [
        {"url": "https://x.test/city-council", "read_on": read,
         "lines": ["Mayor", "Jay Kahn", "Jacob Favolise, Ward 1",
                   "Philip Jones, Ward 5", "Thomas Powers, Ward 5"]}], dot)
    if same["case"] != "directory" or "own council" not in same["why"]:
        bad.append(f"the directory's own council, unchanged and undated, is "
                   f"published: {same['case']} {same['why']}")
    assert not bad, "\n  ".join(bad)
    return "ok", (f"{len(layouts)} cities' layouts read seat by seat, five "
                  "statements of a council's size, and the rule on two pages")


@check("build", "the hand file of towns that moved has its shape, and without it nothing changes",
       needs=("town_websites", "build_town_pages"))
def _town_websites_file(W, B):
    """corrections/town_websites.json is the owner's, and town_websites.py its
    one reader (13 November 2026: Effingham moved to a new website and both
    directories still name the old one). Held here: an entry needs an
    address, a day and evidence and a bad one is an error and not a silent
    nothing; a file that is absent, or names no town, changes nothing --
    load() answers {}, is_current() says every page is current, and
    apply_websites() leaves the directories' addresses where they were; and
    the file in git, where there is one, is valid."""
    import json as _json
    import tempfile
    good = {"towns": {"effingham": {
        "website": "https://www.effingham.nh.gov/",
        "directories_say": {"nhdot": "https://www.effinghamnh.net/"},
        "evidence": ["read 13 November 2026"], "checked_on": "2026-11-13"}}}
    bad = []
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "w.json"
        p.write_text(_json.dumps(good), encoding="utf-8")
        got = W.load(p)
        if got.get("effingham", {}).get("website") != "https://www.effingham.nh.gov":
            bad.append(f"the address is not normalised: {got}")
        if W.is_current("effingham", "https://effinghamnh.net/pages/x", p):
            bad.append("a page of the old site is current")
        if not W.is_current("effingham", "https://www.effingham.nh.gov/1200/Board", p):
            bad.append("a page of the new site is not current")
        if not W.is_current("lyme", "https://lymenh.gov/pages/x", p):
            bad.append("a town the file does not name lost its pages")
        for what, mutate in (
                ("no evidence", lambda e: e.update(evidence=[])),
                ("no day", lambda e: e.update(checked_on="soon")),
                ("no address", lambda e: e.update(website="effingham.nh.gov")),
                ("a host with no dot", lambda e: e.update(website="https://localhost"))):
            e = _json.loads(_json.dumps(good))
            mutate(e["towns"]["effingham"])
            p.write_text(_json.dumps(e), encoding="utf-8")
            try:
                W.load(p)
                bad.append(f"a file with {what} loaded")
            except ValueError:
                pass
        p.write_text("{not json", encoding="utf-8")
        try:
            W.load(p)
            bad.append("a file that does not parse loaded")
        except ValueError:
            pass
    nowhere = Path(tempfile.gettempdir()) / "no-such-town-websites.json"
    if W.load(nowhere) != {} or not W.is_current("effingham", "https://x.example/", nowhere):
        bad.append("an absent file changes something")
    off = {"_offices": {"effingham": {"website": "https://www.effinghamnh.net/"}},
           "_local": {"effingham": {"website": "www.effinghamnh.net"}}}
    before = _json.dumps(off, sort_keys=True)
    if B.apply_websites(off, {}) != [] or _json.dumps(off, sort_keys=True) != before:
        bad.append("apply_websites with no entries changed the directories' data")
    if B.apply_websites(off, got) != ["effingham"] or \
            off["_offices"]["effingham"]["website"] != "https://www.effingham.nh.gov" or \
            off["_local"]["effingham"]["website"] != "https://www.effingham.nh.gov":
        bad.append(f"apply_websites did not put the address in both: {off}")
    real = Path("corrections/town_websites.json")
    if real.exists():
        problems = W.problems(_json.loads(real.read_text(encoding="utf-8")))
        if problems:
            bad.append(f"corrections/town_websites.json: {problems}")
    assert not bad, "\n  ".join(bad)
    return "ok", "shape held, bad entries refused, absent file and empty entries change nothing"


@check("build", "a board in the hand file outranks the directory and a failing page; an e-mail in it replaces NHDOT's",
       needs=("town_boards", "parse_town_sites", "town_websites", "build_town_pages"))
def _town_hand_board_email(T, P, W, B):
    """The owner's decision of 13 November 2026 on Effingham: the town's page
    still says "Term Expires: 2026" under a member and so fails the
    current-page rule, and the hand file's board (the Contact Us card and a
    reader's e-mail as evidence) is used anyway; the contact e-mail the hand
    file gives is drawn in place of NHDOT's. Held on a fixture: a saved page
    that fails the rule gives no board with no hand entry, the entry's board
    with one -- source and day the file's, no directory contact lent -- and a
    second town with the same page and no entry stays as it was; an entry
    with no board or e-mail changes neither; the e-mail replaces NHDOT's only
    where it is given."""
    import json as _json
    import os
    import tempfile
    page = ("<html><body><main><h1>Select Board</h1><p>Members</p>"
            "<p>Ann Aldous, Chair</p><p>Term Expires: 2026</p>"
            "<p>Bea Brandt, Member</p><p>Term Expires: 2027</p>"
            "<p>Cal Carver, Member</p><p>Term Expires: 2028</p></main></body></html>")
    dotrec = {"officials": [
        {"position": "Board of Selectman, Chair", "name": n, "phone": "",
         "email": "old@old.example"} for n in ("Ann Aldous", "Bea Brandt", "Old Member")]}
    ev = ["read 13 November 2026"]
    hand = {"towns": {"xx": {
        "website": "https://www.xx.example", "evidence": ev, "checked_on": "2026-11-13",
        "board": {"members": [{"name": "Ann Aldous", "role": "Chair"},
                              {"name": "Bea Brandt"}, {"name": "Dee Dow"}],
                  "evidence": ev, "checked_on": "2026-11-13"},
        "email": {"address": "hello@xx.example", "evidence": ev,
                  "checked_on": "2026-11-13"}},
        "zz": {"website": "https://www.zz.example", "evidence": ev,
               "checked_on": "2026-11-13"}}}
    bad = []
    was_store, was_env = P.STORE, os.environ.get(W.ENV)
    with tempfile.TemporaryDirectory() as d:
        store = Path(d) / "town_sites"
        for key in ("xx", "yy", "zz"):
            (store / key).mkdir(parents=True)
            host = {"xx": "https://www.xx.example", "yy": "https://yy.example",
                    "zz": "https://www.zz.example"}[key]
            (store / key / "officials-1.html").write_text(page, encoding="utf-8")
            (store / key / "_meta.json").write_text(_json.dumps({"officials-1.html": {
                "kind": "officials", "status": 200, "url": host + "/10/Select-Board",
                "link_text": "Select Board", "read_on": "2026-11-13T08:00:00-0500",
                "score": 90}}), encoding="utf-8")
        hp = Path(d) / "hand.json"
        hp.write_text(_json.dumps(hand), encoding="utf-8")
        dot = {k: dotrec for k in ("xx", "yy", "zz")}
        try:
            P.STORE = store
            os.environ.pop(W.ENV, None)
            none, _t, _c = T.build(["xx", "yy", "zz"], dot)
            os.environ[W.ENV] = str(hp)
            got, _t, _c = T.build(["xx", "yy", "zz"], dot)
        finally:
            P.STORE = was_store
            if was_env is None:
                os.environ.pop(W.ENV, None)
            else:
                os.environ[W.ENV] = was_env
    if any(k in none["boards"] for k in ("xx", "yy", "zz")):
        bad.append(f"the page passed the current rule without the file: {sorted(none['boards'])}")
    b = got["boards"].get("xx")
    if not b:
        bad.append("the hand file's board was not used")
    else:
        if [m["name"] for m in b["members"]] != ["Ann Aldous", "Bea Brandt", "Dee Dow"] \
                or b["members"][0]["role"] != "Chair":
            bad.append(f"the members are not the file's: {b['members']}")
        if b.get("read_on") != "2026-11-13" or not b.get("hand_file"):
            bad.append(f"the day or the mark: {b.get('read_on')} {b.get('hand_file')}")
        if any(m.get("directory_name") for m in b["members"]):
            bad.append("a directory contact is lent to a hand-file board")
    if "yy" in got["boards"] or "zz" in got["boards"]:
        bad.append("a town with no board in the file got one")
    # The e-mail, on the page builder's side.
    off = {"_offices": {"xx": {"email": "old@old.example", "website": "a.example"},
                        "zz": {"email": "old@old.example", "website": "a.example"}},
           "_local": {}}
    with tempfile.TemporaryDirectory() as d2:
        hp2 = Path(d2) / "h.json"
        hp2.write_text(_json.dumps(hand), encoding="utf-8")
        entries = W.load(hp2)
    B.apply_websites(off, entries)
    if off["_offices"]["xx"]["email"] != "hello@xx.example":
        bad.append("the e-mail the file gives did not replace NHDOT's")
    if off["_offices"]["zz"]["email"] != "old@old.example" or \
            "email_checked" in off["_offices"]["zz"]:
        bad.append("an entry with no e-mail changed the e-mail")
    assert not bad, "\n  ".join(bad)
    return "ok", "hand board used though the page fails; other towns, and an entry without one, unchanged"


@check("build", "a CivicPlus Contact Us block is read card by card: seats, staff, and Vacant skipped",
       needs=("parse_town_sites", "town_boards"))
def _town_contact_block(P, T):
    """Effingham's Board of Selectmen page (read 13 November 2026) puts its
    staff and board in a CivicPlus staff directory in the sidebar -- a name
    and a title to a card -- which the page reader's flattening drops. The
    fixture is that block cut down. Held: the board's seats are read
    ("Selectman", "Chairperson- Board of Selectmen"), the administrator and
    the assistant are staff and not seats, "Vacant Vacant" is nobody, the
    office's own card (no title) is nobody, a title that is only "Chair" is a
    seat on the body whose page this is, and a seat the screen would reject
    off a flattened page (the card is not on it) is judged on its title."""
    def card(name, title):
        return ('<li class="widgetItem h-card"><h4 class="widgetTitle field '
                f'p-name"> {name} </h4><div class="field p-job-title">{title}'
                '</div><div class="field p-tel">Phone: </div></li>')
    block = ('<div class="widget widgetStaffDirectory skin63 wide"><div '
             'class="widgetHeader"><h3><a href=/m/directory>Contact Us</a></h3>'
             '</div><ol class="semanticList">'
             '<li class="widgetItem h-card"><h4 class="widgetTitle field '
             'p-name">Board of Selectmen</h4><div class="field h-adr">68 School '
             'Street</div></li>'
             + card("Steven Iannuzzi", "Town Administrator")
             + card("Heidi Stebbins", "Administrative Assistant")
             + card("Vacant Vacant", "Finance Administrator")
             + card("Leo Racine", "Chairperson- Board of Selectmen")
             + card("Chris Seamans", "Selectman")
             + card("Rosemarie Wissenbach", "Selectman")
             + '</ol></div><p>Elsewhere</p>')
    page = "<html><body><aside>" + block + "</aside><main>Board</main></body></html>"
    bad = []
    cards = P.contact_cards(page)
    names = [c["name"] for c in cards]
    if names != ["Steven Iannuzzi", "Heidi Stebbins", "Leo Racine", "Chris Seamans",
                 "Rosemarie Wissenbach"]:
        bad.append(f"the cards read: {names}")
    seats, staff = P.contact_pairs(page, "Board of Selectmen")
    if [(o, p["name"]) for o, p in seats] != [
            ("Board of Selectmen", "Leo Racine"), ("Board of Selectmen", "Chris Seamans"),
            ("Board of Selectmen", "Rosemarie Wissenbach")]:
        bad.append(f"the seats: {[(o, p['name']) for o, p in seats]}")
    if [c["name"] for c in staff] != ["Steven Iannuzzi", "Heidi Stebbins"]:
        bad.append(f"the staff: {staff}")
    if next(p for o, p in seats if p["name"] == "Leo Racine")["role"] != "Chairperson":
        bad.append("the chair's role is not read from the title")
    # A bare "Chair" is the page's body's; on a page of no body's, nobody's.
    bare = ('<div class="widgetStaffDirectory"><ol>' + card("Dana Swenson", "Chair")
            + card("Sam Roe", "Police Chief") + "</ol></div>")
    s1, t1 = P.contact_pairs(bare, "Board of Selectmen")
    s2, t2 = P.contact_pairs(bare, None)
    if [p["name"] for _o, p in s1] != ["Dana Swenson"] or [c["name"] for c in t1] != ["Sam Roe"]:
        bad.append(f"a bare Chair on the board's page: {s1} {t1}")
    if s2 or [c["name"] for c in t2] != ["Sam Roe"]:
        bad.append(f"a bare Chair on no board's page: {s2} {t2}")
    # An alderwoman is neither staff nor a seat this reads.
    wm = '<div class="widgetStaffDirectory"><ol>' + card("Jo Poe", "Alderwoman-At-Large") + "</ol></div>"
    if P.contact_pairs(wm, "Board of Aldermen") != ([], []):
        bad.append("Alderwoman-At-Large was read as staff")
    # The screen judges a card on its title.
    page_ = {"url": "https://x.test/1200/Board-of-Selectmen", "link_text": ""}
    v_ok, _ = T.screen(T.BOARD, seats[0][1], page_, [])
    rep = {"name": "Kay Lee", "card": True, "title": "Selectmen's Rep"}
    v_rep, _ = T.screen(T.BOARD, rep, page_, [])
    if v_ok != "keep" or v_rep != "reject":
        bad.append(f"screen on cards: {v_ok}, {v_rep}")
    assert not bad, "\n  ".join(bad)
    return "ok", "name/title cards read, Vacant and the office card skipped, seats told from staff"


@check("build", "a moved town's page shows its own current staff and website, and no other town's changes",
       needs=("build_town_pages",))
def _town_staff_own_page(B):
    """The town's own staff list (collected/town_boards.json "staff") is drawn
    in place of NHDOT's other rows, with the page it was read from and the
    day; the website of a town in the hand file is linked and the
    directories' is not; and a town without either is drawn exactly as
    before (the same HTML to the byte)."""
    import html as _html
    import shell as S
    tmpl = S.template()
    row = [{"position": "Town Administrator", "name": "Caitlyn Pitts",
            "phone": "603-539-7770", "email": ""},
           {"position": "Board of Selectman", "name": "Chuck Fuller",
            "phone": "", "email": ""}]
    staff = {"source_url": "https://www.effingham.nh.gov/1200/Board-of-Selectmen",
             "read_on": "2026-11-13T08:11:59-0500",
             "people": [{"name": "Steven Iannuzzi", "title": "Town Administrator"},
                        {"name": "Ann Clerk", "title": "Town Clerk"}]}

    def off(moved):
        o = {"_offices": {"effingham": {"officials": [dict(r) for r in row],
                                         "website": "https://www.effinghamnh.net/",
                                         "phone": "603-539-7770"},
                          "lyme": {"officials": [dict(r) for r in row]},
                          "franklin": {"officials": [dict(r) for r in row],
                                       "website": "https://www.franklinnh.net/",
                                       "phone": "603-934-3900"}},
             "_local": {"effingham": {"website": "www.effinghamnh.net"}}}
        if moved:
            B.apply_websites(o, {"effingham": {"website": "https://www.effingham.nh.gov",
                                               "checked_on": "2026-11-13",
                                               "email": {"address": "townadmin@effingham.nh.gov",
                                                         "checked_on": "2026-11-13"}},
                                 "franklin": {"website": "https://www.franklinnh.gov",
                                              "checked_on": "2026-11-13",
                                              "email": {"address": "clerk@franklinnh.gov",
                                                        "checked_on": "2026-11-13"}}})
            o["_staff"] = {"effingham": staff}
        return o

    def page(town, o):
        return B.build(town, "0", {"0": {}}, {}, [], o, "https://x.test", tmpl)
    old, new = page("Effingham", off(False)), page("Effingham", off(True))
    bad = []
    if "effinghamnh.net</a>" not in old or "effinghamnh.net" in new or \
            "effingham.nh.gov</a>" not in new:
        bad.append("the directories' address is still linked on the moved town's page")
    if "Caitlyn Pitts" not in old or "Caitlyn Pitts" in new:
        bad.append("NHDOT's staff row is not replaced by the town's")
    if "Steven Iannuzzi" not in new:
        bad.append("the town's staff are not drawn")
    if "Ann Clerk" in new:
        bad.append("a clerk row of the town's list is drawn; the clerk is the Secretary of State's")
    if "listed its staff when this site read it on November 13, 2026" not in _html.unescape(new):
        bad.append("the staff card does not say where and when it was read")
    if "Chuck Fuller" not in new:
        bad.append("the directory's board vanished although the town's was not used")
    # The caveat points back at the directory's date, so it comes straight
    # after it, before the sentences that carry the days a town was checked.
    nu = _html.unescape(new)
    if "checked November 13, 2026" not in nu:
        bad.append("the moved town's offices card has no checked day to order the caveat against")
    elif re.search(r"dated [A-Z][a-z]+ \d{4}\. It does not show anyone elected or appointed since then",
                   nu.split("(checked November 13, 2026)")[0]) is None:
        bad.append("on the moved town's offices card the 'since then' sentence does not come "
                   "straight after the directory's date")
    # The noun is the place's own: a city's card says the city's, a town's the town's.
    fr = _html.unescape(page("Franklin", off(True)))
    for need in ("The website is the city's current one (checked November 13, 2026).",
                 "The e-mail address is the city's own (checked November 13, 2026)."):
        if need not in fr:
            bad.append(f"a moved city's offices card does not say: {need}")
    if "the town's" in fr:
        bad.append("a moved city's offices card says the town's")
    for need in ("The website is the town's current one (checked November 13, 2026).",
                 "The e-mail address is the town's own (checked November 13, 2026)."):
        if need not in nu:
            bad.append(f"a moved town's offices card does not say: {need}")
    # A town the hand file does not name is the same page to the byte.
    if page("Lyme", off(False)) != page("Lyme", off(True)):
        bad.append("another town's page changed")
    assert not bad, "\n  ".join(bad)
    return "ok", "staff from the town's page replace NHDOT's, the old address is unlinked, other towns unchanged"


@check("build", "a town page draws its own board where it has one, and the directory's without its chair",
       needs=("build_town_pages",))
def _town_board_drawn(B):
    """What a reader sees of the rule above. Lyme's page named Judith
    Brotman as chair of a board she is no longer on; its own page lists Ben
    Kilham, David Kahn and Michael Hinsely. Where the town's page is used,
    the directory's names are gone, the source and the date it was read are
    under the names, and the directory's phone and e-mail stay with the
    member they belong to. Where it is not, the directory's board is shown
    as the directory's, dated, and without the chair it named: that chair
    disagrees with the town's own page in 25 of the 40 towns where both name
    one.
    """
    import html as _html
    import shell as S
    tmpl = S.template()
    dot = [
        {"position": "Town Administrator", "name": "Dina Cutting",
         "phone": "603-795-4639", "email": "dina@lyme.test"},
        {"position": "Board of Selectman, Chair", "name": "Judith Brotman",
         "phone": "", "email": "selectboard@lyme.test"},
        {"position": "Board of Selectman", "name": "Ben Kilham",
         "phone": "603-795-4000", "email": "bkilham@lyme.test"},
        {"position": "Board of Selectman", "name": "David Kahn",
         "phone": "", "email": "jbrotman@lyme.test"},
        {"position": "Road Agent", "name": "Scott Bailey", "phone": "",
         "email": ""}]
    board = {"source_url": "https://www.lymenh.gov/pages/select-board",
             "read_on": "2026-09-20T22:22:15-0400", "size": 3,
             "size_from": "the page states it", "members": [
                 {"name": "Ben Kilham", "role": "Chair", "term_ends": "2028",
                  "directory_name": "Ben Kilham"},
                 {"name": "David Kahn", "role": "Vice Chair",
                  "term_ends": "2027", "directory_name": "David Kahn"},
                 {"name": "Michael Hinsely", "role": None, "term_ends": "2029",
                  "directory_name": None}]}
    council = [{"position": "Town Councilor, Chair", "name": "Pat Doe",
                "phone": "", "email": ""},
               {"position": "City Councilor, District 6 (Secretary)",
                "name": "Lee Roe", "phone": "", "email": ""}]
    off = {"_offices": {"lyme": {"officials": dot, "website": "www.lymenh.gov"},
                        "dalton": {"officials": dot},
                        "derry": {"officials": council}},
           "_boards": {"lyme": board}}
    lyme = _html.unescape(B.build("Lyme", "0", {"0": {}}, {}, [], off,
                                  "https://x.test", tmpl))
    dalton = _html.unescape(B.build("Dalton", "0", {"0": {}}, {}, [], off,
                                    "https://x.test", tmpl))
    derry = _html.unescape(B.build("Derry", "0", {"0": {}}, {}, [], off,
                                   "https://x.test", tmpl))
    bad = []
    if "Judith Brotman" in lyme:
        bad.append("Lyme names the directory's chair, whom its own page does "
                   "not list")
    for who in ("Ben Kilham", "David Kahn", "Michael Hinsely"):
        if who not in lyme:
            bad.append(f"Lyme's own board is drawn without {who}")
    if 'href="https://www.lymenh.gov/pages/select-board"' not in lyme or \
            "September 20, 2026" not in lyme:
        bad.append("Lyme's own board does not say where it was read, and when")
    if "tel:+16037954000" not in lyme:
        bad.append("Ben Kilham lost the phone the directory gives him")
    if "jbrotman@" in lyme:
        bad.append("David Kahn is drawn beside Judith Brotman's address")
    if "Dina Cutting" not in lyme:
        bad.append("the rest of the directory's rows went with its board")
    seats = re.findall(r'<span class="offseat">([^<]*)</span>', dalton + derry)
    chair = [s for s in seats if re.search(r"chair|secretary", s, re.I)]
    if chair:
        bad.append(f"the directory's officers are drawn: {chair}")
    for who in ("Judith Brotman", "Ben Kilham", "David Kahn"):
        if who not in dalton:
            bad.append(f"Dalton, with no board of its own on file, lost {who}")
    if "before the 2026 town elections" not in dalton:
        bad.append("the directory's board is not dated against the 2026 "
                   "town elections")
    if "Town Councilor" not in seats or "City Councilor, District 6" not in seats:
        bad.append(f"a councillor's seat went with the officer label: {seats}")

    # A PART OF THE BOARD, LABELLED (the person, 24 September 2026): "3 of
    # 5 members listed" beside the heading and the size's source under the
    # names; where no source gives the size, "5 members listed" and a
    # sentence saying so. Not the directory's board in its place.
    def with_board(key, b):
        o = {"_offices": {key: {"officials": dot}}, "_boards": {key: b}}
        return _html.unescape(B.build(key.title(), "0", {"0": {}}, {}, [], o,
                                      "https://x.test", tmpl))
    part = dict(board, partial=True, size=5, size_from="the page states it")
    chester = with_board("chester", part)
    if "3 of 5 members listed" not in chester or \
            "has 5 seats, as its own page says" not in chester:
        bad.append("a board listing 3 of its 5 seats is not labelled so, or "
                   "does not say where the 5 comes from")
    if "Judith Brotman" in chester:
        bad.append("the directory's board is drawn beside a partial list")
    nosize = with_board("campton", dict(board, partial=True, size=None,
                                        size_from=""))
    if "3 members listed" not in nosize or "No source on file gives the size" \
            not in nosize or " of None" in nosize:
        bad.append("a list whose board's size no source gives is not labelled "
                   "without a number")
    if "members listed" in lyme:
        bad.append("a whole board carries a partial list's label")

    # A CITY'S MAYOR AND COUNCIL, ITS OWN. Dover's directory row names Robert
    # Carrier as mayor; the city's page, Dennis Shanahan since January.
    dover_dot = [
        {"position": "Mayor", "name": "Robert Carrier", "phone": "",
         "email": "rcarrier@dover.test"},
        {"position": "Town Councilor, Ward 1", "name": "April Richer",
         "phone": "603-555-0101", "email": "aricher@dover.test"},
        {"position": "Road Agent", "name": "JOHN MCDONALD", "phone": "",
         "email": ""}]
    council = {"source_url": "https://www.dover.test/city-council/index.html",
               "read_on": "2026-09-20T22:01:20-0400", "size": 2,
               "size_from": "the page states it", "later": "x", "members": [
                   {"name": "Dennis Shanahan", "seat": "Mayor", "role": "",
                    "term_ends": "2028", "directory_name": None},
                   {"name": "April Richer", "seat": "Ward 1", "role": "",
                    "term_ends": "2028", "directory_name": "April Richer"}]}
    dover = _html.unescape(B.build("Dover", "0", {"0": {}}, {}, [], {
        "_offices": {"dover": {"officials": dover_dot}},
        "_councils": {"dover": council}}, "https://x.test", tmpl))
    if "Robert Carrier" in dover or "Dennis Shanahan" not in dover:
        bad.append("Dover's page names the directory's mayor, not its own")
    # The card credits the city's website, with its day; the Sources line
    # under the tabs no longer says it again (the audit of 25 October 2026:
    # it names only what no card names).
    if "As Dover's website listed the mayor and council when this site read it on "\
            "September 20, 2026" not in dover:
        bad.append("Dover's own council does not say whose website it was read "
                   "from, and when")
    dseats = re.findall(r'<span class="offseat">([^<]*)</span>', dover)
    if "Mayor" not in dseats or "Ward 1" not in dseats:
        bad.append(f"the council's seats are not the city page's: {dseats}")
    if "tel:+16035550101" not in dover:
        bad.append("April Richer lost the phone the directory gives her")
    if "John McDonald" not in dover or "JOHN MCDONALD" in dover:
        bad.append("a directory name written in capitals is not set in normal "
                   "case")
    # A part of a council, its mayor from another of the city's pages and
    # not one of the seats its sentence counts: Nashua's fifteen aldermen
    # leave the mayor out, so two aldermen read are "2 of 15", not "3".
    part = dict(council, size=15, partial=True, read=2, members=[
        dict(council["members"][0], source_url="https://www.dover.test/mayor"),
        council["members"][1],
        {"name": "Lee Roe", "seat": "Ward 2", "role": "", "term_ends": None,
         "directory_name": None}])
    nashua = _html.unescape(B.build("Nashua", "0", {"0": {}}, {}, [], {
        "_offices": {"nashua": {"officials": dover_dot}},
        "_councils": {"nashua": part}}, "https://x.test", tmpl))
    if "2 of 15 members listed" not in nashua or "3 of 15" in nashua:
        bad.append("a partial council counts the mayor from another page "
                   "among seats that leave the mayor out")
    assert not bad, "\n  ".join(bad)
    return "ok", ("the town's own board drawn with its source and date, the "
                  "directory's without its chair, contacts kept with their "
                  "owner; a partial list labelled, a city's own council drawn")


@check("build", "a town page is tabs: each tab opens a panel with something in it, by click and by address",
       needs=("build_town_pages", "build_pages"))
def _town_tabs(B, BP):
    """The person, 24 September 2026: a town page's sections "just read as
    very cluttered and indistinct", and they asked for tabs -- the officials
    who represent the town, the town's own officials, how to vote -- that
    grow as more is collected. So a town page is the legislators page's tab
    pattern: a named tablist, buttons with aria-selected, aria-controls and
    a roving tabindex, panels labelled by their tab, Representatives first.

    Three things would break quietly and are held here. A tab whose panel is
    empty, or missing, is a control that opens nothing. A place with no town
    government -- the 25 unincorporated places -- must have no Town officials
    tab rather than an empty one, or one that files a neighbouring town's
    clerk under "Town clerk". And the address: /town/lyme#vote must open How
    to vote, and a click must write the tab into the address WITHOUT adding a
    history entry, or Back walks through the tabs instead of leaving the page.
    The script runs in node against dom_stub.js, with the page's own tabs.

    AND THE ADDRESS IT WRITES IS THE TOWN'S OWN. The page carries
    <base href="/">, and the script wrote a bare "#officials", which a browser
    resolves against the base: choosing a tab on /town/acworth put /#officials
    in the address bar, and a reload, a bookmark or a copied link opened the
    home page (the audit of 2 October 2026; all 320 pages). So what is
    written must start with the page's own path, query included.

    The strip scrolls inside itself and the panels' grid tracks are
    minmax(0, 1fr), so no number of tabs and no long address can make a
    360px page scroll sideways; that is read off app.css.
    """
    import html as _html
    import shell as S
    tmpl = S.template()
    rep = {"name": "Vail, Suzanne", "display_full": "Rep. Suzanne Vail (D - Hills 6)",
           "party": "Democrat", "slug": "suzanne-vail-hills-6", "chamber": "H",
           "county": "Grafton", "district": "12", "email": "", "phone": ""}
    sen = {"name": "Abbas, Daryl", "display_full": "Sen. Daryl Abbas (R - SD5)",
           "party": "Republican", "slug": "daryl-abbas-sd-5", "chamber": "S",
           "district": "5", "email": "", "phone": ""}
    dist = {"congress": 2, "council": 2, "senate": 5, "house": [
        {"county": "Grafton", "district": 12, "floterial": False, "seats": 4}]}
    local = {"clerk": "Emily Shepard", "polling_place": "Lyme Community Gymnasium",
             "election": "11/03/2026-STATE GENERAL ELECTION", "phone": "603-795-2535"}
    off = {"_offices": {"lyme": {"officials": [
               {"position": "Board of Selectman", "name": "Ben Kilham",
                "phone": "", "email": ""},
               {"position": "Town Administrator", "name": "Dina Cutting",
                "phone": "", "email": ""}], "website": "www.lymenh.gov"}},
           "_local": {"lyme": local,
                      "bean-s-grant": dict(local, clerk="Christina Zornio")}}
    pages = {t: B.build(t, "0", {"0": {}}, dist, [rep, sen], off,
                        "https://x.test", tmpl)
             for t in ("Lyme", "Bean's Grant", "Nowhere")}
    # The District Map is every place's second tab (Polish 3): every town and
    # ward is on the map.
    LABELS = {"representatives": "Representatives", "map": "Map", "officials": "Officials",
              "vote": "How to Vote", "services": "Services"}
    want = {"Lyme": ["representatives", "map", "officials", "vote"],
            "Bean's Grant": ["representatives", "map", "vote"],
            "Nowhere": ["representatives", "map"]}
    bad = []
    for town, page in pages.items():
        bars = re.findall(r'<div class="twntabs" role="tablist" aria-label="[^"]+" '
                          r'hidden>(.*?)</div>', page, re.S)
        if len(bars) != 1:
            bad.append(f"{town}: {len(bars)} tab strips, written hidden until "
                       "the script shows them")
            continue
        tabs = re.findall(r'role="tab" id="tab-(\w+)" data-pane="(\w+)" '
                          r'aria-controls="(\w+)" aria-selected="(\w+)" '
                          r'tabindex="(-?\d)"', bars[0])
        ids = [t[0] for t in tabs]
        if ids != want[town]:
            bad.append(f"{town}: tabs {ids}, not {want[town]}")
        # The labels (the owner, 10 November 2026: the Vote tab reads "How to
        # Vote", its id and address still "vote"); the page names the town,
        # so a city's are these too, each on one line (.twntabs scrolls).
        names = re.findall(r'role="tab" id="tab-(\w+)"[^>]*>([^<]*)</button>', bars[0])
        if any(LABELS[t] != n for t, n in names):
            bad.append(f"{town}: the tabs read {[n for _t, n in names]}, not "
                       f"{[LABELS[t] for t, _n in names]}")
        for i, (tid, pane, ctl, sel, ti) in enumerate(tabs):
            first = i == 0
            if not tid == pane == ctl or (sel == "true") != first \
                    or (ti == "0") != first:
                bad.append(f"{town}: tab {tid} is not wired as the roster's are")
            m = re.search(rf'<div class="twnpane" id="{ctl}" role="tabpanel" '
                          rf'aria-labelledby="tab-{tid}"><h2 class="twnph">'
                          rf'.*?<div class="twngrid">(.*?)</div></div>', page, re.S)
            if not m or '<section class="twnsec' not in m.group(1):
                bad.append(f"{town}: tab {tid} opens no panel, or an empty one")
        levels = [int(x) for x in re.findall(r"<h([1-6])[ >]",
                                             page[page.index('id="results"'):])]
        if any(b > a + 1 for a, b in zip(levels, levels[1:])):
            bad.append(f"{town}: the headings skip a level: {levels}")
    lyme = pages["Lyme"]
    if BP.pchip(rep) not in lyme or BP.pchip(sen) not in lyme:
        bad.append("a legislator is not drawn with the shared person chip")
    if "Christina Zornio" in pages["Bean's Grant"].split('id="vote"')[0]:
        bad.append("an unincorporated place files its voting clerk as a town "
                   "officer")
    if "In Grafton County." not in _html.unescape(lyme) or \
            "Grafton district 12" not in lyme:
        bad.append("the county and the districts are not said above the tabs")
    concord = B.build("Concord", "0", {"0": {}}, dist, [rep, sen],
                      {"_offices": {"concord": {"officials": [],
                                                "website": "www.concordnh.gov"}},
                       "_local": {"concord": local}}, "https://x.test", tmpl)
    if "Town website" not in lyme.partition('id="vote"')[2] or \
            "City website" not in concord.partition('id="vote"')[2]:
        bad.append("How to vote calls a city's website the town's, or a "
                   "town's the city's")
    if 'id="tab-officials" data-pane="officials" aria-controls="officials" aria-selected="false" ' \
            'tabindex="-1">Officials</button>' not in concord:
        bad.append("a city's Officials tab is not named Officials")

    css = _source("src/pages/app.css")
    strip = re.search(r"\.twntabs\{[^}]*\}", css)
    grid = re.search(r"\.twngrid\{[^}]*\}", css)
    if not strip or "overflow-x:auto" not in strip.group(0):
        bad.append("the tab strip does not scroll inside itself, so tabs can "
                   "widen a 360px page")
    # EACH TAB ON ONE LINE, THE STRIP'S EDGE SAYING IT GOES ON (the audit of
    # 25 October 2026): the Officials page's rules, every strip's now, and
    # no phone rule that shares the width out and wraps the words.
    tab = re.search(r"\.twntabs \[role=tab\]\{[^}]*\}", css)
    if not tab or "white-space:nowrap" not in tab.group(0):
        bad.append("a tab's label can wrap: .twntabs [role=tab] has no white-space:nowrap")
    if re.search(r"\.twntabs \[role=tab\]\{flex:1", css):
        bad.append("a phone rule shares the strip's width out among the tabs, which wraps them")
    if not re.search(r"@media \(max-width:63\.9375em\)\{\s*\.twntabs \[role=tab\]\{flex:0 0 auto", css) or \
            not re.search(r"\n\.twntabs\{display:flex[^}]*background:[^}]*var\(--scrolledge\)", css):
        bad.append("below 1024px the strip's tabs are not kept whole with its edge's shadow")
    if re.search(r"\.oftabs(?: \[role=tab\])?\{(?:white-space|flex|background)", css):
        bad.append("the Officials page's strip has rules of its own again beside .twntabs's")
    if not grid or "minmax(0,1fr)" not in grid.group(0):
        bad.append("the panels' grid track can grow past the page")
    if not re.search(r"\.twntabs\[hidden\]\{display:none\}", css) or \
            not re.search(r"\.twnpane\[hidden\]\{display:none\}", css):
        bad.append("a display rule overrides `hidden` on the strip or a panel")

    node = shutil.which("node") or shutil.which("node.exe")
    if node and not bad:
        script = re.search(r"<script>\n(.*?)</script>", B.TABS_JS, re.S).group(1)
        tabs = json.dumps([["representatives"], ["officials"], ["vote"]])
        harness = """
function node2(){
  const e = el(); e.attrs = {};
  e.setAttribute = function(k, v){ this.attrs[k] = String(v); };
  e.getAttribute = function(k){ return k in this.attrs ? this.attrs[k] : null; };
  e.focus = function(){ document.activeElement = this; };
  return e;
}
const tabEls = %s.map(([p]) => { const t = node2(); t.dataset.pane = p; return t; });
const panes = {}; tabEls.forEach(t => { panes[t.dataset.pane] = node2(); });
const bar = node2(); bar.hidden = true; bar.querySelectorAll = () => tabEls;
// A phone's strip: 300px showing tabs 200px apart, each 150px wide; and its
// top, which a link to a tab from further down the page has above the window.
bar.scrollWidth = 600; bar.clientWidth = 300; bar.scrollLeft = 0;
let barTop = 0;
bar.getBoundingClientRect = () => ({left: 0, right: 300, top: barTop});
const scrolled = []; globalThis.scrollTo = (x, y) => scrolled.push(y); globalThis.scrollY = 1000;
// How the page was reached (a reload is put back by the browser, not landed
// on), and the web fonts' arrival, which the script lands again on.
const mode = process.argv[3] || "";
Object.defineProperty(globalThis, "performance", {configurable: true,
  value: {getEntriesByType: k => k === "navigation" ? [{type: mode === "reload" ? "reload" : "navigate"}] : []}});
const fontsCb = []; document.fonts = {ready: {then: f => fontsCb.push(f)}};
tabEls.forEach((t, i) => { t.getBoundingClientRect = () =>
  ({left: i * 200 - bar.scrollLeft, right: i * 200 + 150 - bar.scrollLeft}); });
bar.querySelector = () => tabEls.find(t => t.attrs["aria-selected"] === "true") || null;
document.querySelector = s => s === ".twntabs" ? bar : null;
// A section inside the third panel, as /officials#of-county-strafford names a
// county's heading inside County Officials; and #results, which wraps the
// panels and is in none. Each counts the times the page is brought to it.
// A panel landed on, rather than its strip, counts too; and something inside
// a panel that is none of the strip's tabs, which opens nothing.
let landed = 0, wrapped = 0, paneLanded = 0;
Object.keys(panes).forEach(k => { panes[k].id = k;
  panes[k].closest = s => s === ".twnpane" ? panes[k] : null;
  panes[k].scrollIntoView = () => { paneLanded++; }; });
const sec = node2(); sec.closest = s => s === ".twnpane" ? panes.vote : null;
sec.scrollIntoView = () => { landed++; };
const wrap = node2(); wrap.closest = () => null; wrap.scrollIntoView = () => { wrapped++; };
const loose = node2(); loose.id = "loose";
const lost = node2(); lost.closest = s => s === ".twnpane" ? loose : null;
lost.scrollIntoView = () => { landed += 100; };
document.getElementById = id => panes[id]
  || ({"vote-where": sec, "results": wrap, "lost-x": lost})[id] || null;
const wrote = []; let pushed = 0;
history.replaceState = (a, b, u) => wrote.push(u);
history.pushState = () => { pushed++; };
const on = {}; globalThis.addEventListener = (t, f) => (on[t] = on[t] || []).push(f);
location.hash = process.argv[2];
location.pathname = "/town/lyme"; location.search = "?from=test";
const shown = () => Object.keys(panes).filter(p => !panes[p].hidden);
const out = {};
%s
out.load = shown(); out.bar = bar.hidden; out.strip = bar.scrollLeft;
out.early = landed;
// A reader who scrolls on before the page has loaded.
if (mode === "moved") (on.wheel || []).forEach(f => f());
(on.load || []).forEach(f => f()); out.landed = landed; out.wrapped = wrapped;
fontsCb.forEach(f => f()); out.fonts = landed; out.paneLanded = paneLanded;
tabEls[1].fire("click"); out.click = shown();
document.activeElement = tabEls[1]; bar.fire("keydown", {key: "ArrowRight"});
out.arrow = shown();
// A link to a tab from below the strip brings the strip back into view.
barTop = -500;
location.hash = "#representatives"; (on.hashchange || []).forEach(f => f());
out.back = shown(); out.wrote = wrote.slice(); out.pushed = pushed;
out.toStrip = scrolled.slice(); barTop = 0;
// A link on the page to a section in another tab: its tab opens, the page is
// brought to it, and the address is left as the link wrote it.
location.hash = "#vote-where"; (on.hashchange || []).forEach(f => f());
out.section = shown(); out.landed2 = landed - out.fonts; out.wrote2 = wrote.length;
// A link to a tab whose strip is in view moves nothing.
location.hash = "#officials"; (on.hashchange || []).forEach(f => f());
out.stripStill = scrolled.length; out.paneLanded2 = paneLanded;
// Home and End, as the bill's and the member's tabs answer them, and the
// page's own scroll held off (the review of 2 October 2026).
const keyed = k => { let held = false;
  bar.fire("keydown", {key: k, preventDefault(){ held = true; }});
  return [shown()[0], tabEls.indexOf(document.activeElement), held]; };
document.activeElement = tabEls[0]; out.end = keyed("End"); out.home = keyed("Home");
process.stdout.write(JSON.stringify(out));
""" % (tabs, script)
        stub = _source("tests/dom_stub.js")
        for hsh, first, mode in (("#vote", "vote", ""), ("", "representatives", ""),
                                 ("#results", "representatives", ""),
                                 ("#vote-where", "vote", ""),
                                 ("#nowhere", "representatives", ""),
                                 ("#lost-x", "representatives", ""),
                                 ("#vote-where", "vote", "moved"),
                                 ("#vote-where", "vote", "reload")):
            r = subprocess.run([node, "-e", stub + "\n" + harness, "x", hsh, mode],
                               capture_output=True, encoding="utf-8",
                               timeout=60)
            if r.returncode:
                bad.append("the tab script would not run: " + r.stderr[-300:])
                break
            got = json.loads(r.stdout)
            if got["load"] != [first] or got["bar"]:
                bad.append(f"arriving at {hsh or 'no hash'!r} shows {got['load']}, "
                           f"not {first}, with the strip hidden={got['bar']}")
            # The chosen tab in view: #vote's tab stands at 400-550 in a
            # strip 300 wide, so the strip moves; the first tab's does not.
            if (got["strip"] > 0) != (first == "vote"):
                bad.append(f"arriving at {hsh or 'no hash'!r} left the strip at "
                           f"{got['strip']}px: the chosen tab is not brought into view")
            if got["click"] != ["officials"] or got["arrow"] != ["vote"] \
                    or got["back"] != ["representatives"]:
                bad.append(f"click, arrow and address showed {got['click']}, "
                           f"{got['arrow']} and {got['back']}")
            # A section's address opens the tab holding it and the page is
            # brought to it once loaded and when the fonts arrive -- not
            # before, and not at all for a reload or a reader who has already
            # scrolled on. Any other address is not scrolled; a panel is never
            # landed on in place of its strip.
            where = f"arriving at {hsh or 'no hash'!r}{' (' + mode + ')' if mode else ''}"
            lands = hsh == "#vote-where" and not mode
            if got["early"] or got["landed"] != (1 if lands else 0) \
                    or got["fonts"] != (2 if lands else 0) or got["wrapped"] or got["paneLanded"]:
                bad.append(f"{where} landed on the section {got['early']} time(s) before "
                           f"load, {got['landed']} by load and {got['fonts']} by the fonts, on "
                           f"#results {got['wrapped']} and on a panel {got['paneLanded']}: "
                           "only an address naming something inside a panel is landed on, "
                           "once loaded and once the fonts arrive, and never on a reload or "
                           "after the reader has scrolled")
            if got["section"] != ["vote"] or got["landed2"] != 1 or got["wrote2"] != 2:
                bad.append(f"a link to #vote-where showed {got['section']}, landed "
                           f"{got['landed2']} time(s) and wrote {got['wrote2']} addresses: "
                           "an address naming a section must open the tab holding it, "
                           "bring the page to it, and leave the address as it was")
            if got["toStrip"] != [492] or got["stripStill"] != 1 or got["paneLanded2"]:
                bad.append(f"a link to a tab scrolled to {got['toStrip']} with the strip 500px "
                           f"above the window, made {got['stripStill']} scroll(s) in all, and "
                           f"landed on a panel {got['paneLanded2']} time(s): the strip, not the "
                           "panel, comes back into view, and only when it is out of sight")
            if got["end"] != ["vote", 2, True] or got["home"] != ["representatives", 0, True]:
                bad.append(f"End and Home gave {got['end']} and {got['home']} "
                           "([tab shown, tab focused, page scroll held off]): "
                           "a tab list answers both, and End scrolled the page "
                           "to its foot")
            if got["wrote"] != ["/town/lyme?from=test#officials",
                                "/town/lyme?from=test#vote"] or got["pushed"]:
                bad.append(f"switching wrote {got['wrote']} and pushed "
                           f"{got['pushed']} history entries: the address must "
                           "be the town's own path, its query and the tab, "
                           'because a bare #tab resolves against <base href="/"> '
                           "and names the home page")
    if '<base href="/">' not in lyme:
        bad.append('the town page no longer carries <base href="/">: read '
                   "TABS_JS again, the address it writes was built around it")
    assert not bad, "\n  ".join(bad)
    return "ok", ("tabs wired as the roster's, none empty, none for a place with "
                  "no town government; #vote opens its tab and a click writes "
                  "the town's own address and the tab, without a history entry; "
                  "an address naming a section opens the tab holding it and lands on it"
                  + ("" if node else " (node absent: script not run)"))


# ---- a town page's Elections tab (the owner, 19 November 2026; town_elections.py) ----

def _te_world(TE, BME):
    """The tab's general elections on file, built from collected/ alone: the district
    table's towns and wards as the town rows of 2022 on spell them (the reader's own
    reading, place_district_table), each House and Senate race's winners its results'
    "elected" (members_elect's rule needs the roster, which a checkout lacks), the other
    offices' the offices file's. Returns (ledger, {year: town rows}, {year: offices doc},
    {year: results}); None where the files are not here."""
    col = _paths.ROOT / "collected"
    years = TE.years_on_file(col)
    if not years:
        return None
    table = {}
    for y in years:
        if y < TE.WARDS_SINCE:
            continue
        with open(col / TE.TOWN_ROWS.format(year=y), encoding="utf-8", newline="") as f:
            import csv
            for r in csv.DictReader(f):
                m = re.match(r"^(.*?) Ward (\d+)$", r["place_district_table"])
                town, ward = (m.group(1), m.group(2)) if m else (r["place_district_table"], "0")
                if town:
                    table.setdefault(town, {})[ward] = {}
    ledger = TE.Ledger(table)
    rows, offices, results = {}, {}, {}
    for y in years:
        rows[y] = TE.read_town_rows(col / TE.TOWN_ROWS.format(year=y))
        res = json.loads((col / TE.RESULTS.format(year=y)).read_text(encoding="utf-8"))
        results[y] = res
        me = {k: {"seats": r["seats"], "elected": [{"n": BME.reading_order(c["name"])}
                                                   for c in r["candidates"] if c.get("elected") is True]}
              for k, r in res["races"].items()}
        TE.add_house_senate(ledger, y, rows[y], res, me, {}, {}, lambda k: frozenset())
        off = col / TE.OFFICES.format(year=y)
        if off.is_file():
            offices[y] = json.loads(off.read_text(encoding="utf-8"))
            TE.add_offices(ledger, y, offices[y], True)
    return ledger, rows, offices, results


def _te_drawn(html):
    """{(year, election heading, race name): [(name, votes, marks)]} of a tab's general
    elections, read off its HTML: the chip's name, the count and the chips after it."""
    out = {}
    for ysec in re.findall(r'<section class="twnsec twnwide te-year">(.*?)</section>', html, re.S):
        year = re.match(r'<h3 class="twnh">(\d{4})</h3>', ysec).group(1)
        for head, body in re.findall(r'<h4 class="te-el">([^<]*)</h4>(.*?)(?=<h4 class="te-el">|<details|$)',
                                     ysec, re.S):
            if not head.startswith("General election"):
                continue
            for name, rows in re.findall(r'<article class="er-race te-race"><div class="er-hd"><h5>([^<]*)'
                                         r'</h5>.*?<ul class="er-rows">(.*?)</ul>', body, re.S):
                got = []
                for li in re.findall(r'<li class="er-row">(.*?)</li>', rows, re.S):
                    who = re.search(r'translate="no">(?:<a href="[^"]*">)?(.*?)(?: <span class="mtag">|</a>|</span>)',
                                    li).group(1)
                    n = int(re.search(r'<span class="er-n">([\d,]+)', li).group(1).replace(",", ""))
                    marks = re.findall(r'<span class="chip">([^<]*)</span>', li)
                    got.append((who, n, tuple(marks)))
                out[(year, head, name)] = got
    return out


@check("files", "a town page's Elections tab: every count of a general election is the town's or "
                "the ward's own, as the Secretary of State's town rows and the other offices' place "
                "rows print it, for every page and race of 2022 on",
       needs=("town_elections", "build_members_elect"))
def _town_elections_counts(TE, BME):
    """Summed here again from the files, not from the tab's ledger: the House and Senate
    town rows the race's own count is made of (in_race_count), read to a page by the
    reader's own spelling of the place; the other offices' place rows whose printed name
    is a page's town or "<town> Ward <n>" (or " - Ward <n>"), a candidate's recount
    column where the file prints one. Each must be the count the tab prints for that page
    and race, and every candidate the files count must be on the tab. Before 2022 a place's
    spelling is the reading the tab makes (place_of), held by _town_elections_places."""
    w = _te_world(TE, BME)
    if w is None:
        return "skip", "no collected/election_town_rows_*.csv in this checkout"
    ledger, rows, offices, results = w
    want = {}
    import csv
    for y in rows:
        if y < TE.WARDS_SINCE:
            continue
        day = results[y]["election"]
        with open(_paths.ROOT / "collected" / TE.TOWN_ROWS.format(year=y), encoding="utf-8",
                  newline="") as f:
            for r in csv.DictReader(f):
                race = results[y]["races"].get(r["district_key"])
                if race is None or r["in_race_count"] != "true" or r["row_kind"] not in (
                        "candidate", "write_in_named"):
                    continue
                m = re.match(r"^(.*?) Ward (\d+)$", r["place_district_table"])
                page = (m.group(1), m.group(2)) if m else (r["place_district_table"], "0")
                d = want.setdefault((page, day, TE.house_name(r["district_key"], race.get("floterial"))), {})
                d[r["candidate"]] = d.get(r["candidate"], 0) + int(r["votes"])
    for y, doc in offices.items():
        if y < TE.WARDS_SINCE:
            continue
        for key, race in doc["races"].items():
            cols = race["columns"]
            for c in race["candidates"]:
                label = f"{c['name']}, {c['party']}" if c.get("party") else c["name"]
                i = cols.index(label + " (recount)") if label + " (recount)" in cols else cols.index(label)
                for p in race.get("places") or []:
                    m = re.match(r"^(.*?)(?: - | )Ward (\d+)$", p[1])
                    page = (m.group(1), m.group(2)) if m else (p[1], "0")
                    if page not in {(t, wd) for t, ws in ledger.places.wards.items() for wd in ws}:
                        continue
                    d = want.setdefault((page, doc["election"], TE.office_name(key, race)), {})
                    d[c["name"]] = d.get(c["name"], 0) + p[2][i]
    bad, n_races, n_rows, pages = [], 0, 0, 0
    for town, wards in ledger.places.wards.items():
        for ward in wards:
            label = f"{town}, Ward {ward}" if ward != "0" else town
            drawn = _te_drawn("".join(TE.tab_cards(ledger.for_page(town, ward), label, ward != "0")))
            pages += 1
            for (page, day, name), cands in want.items():
                if page != (town, ward):
                    continue
                year = day[:4]
                head = f"General election, {TE.long_day(day)}"
                got = drawn.get((year, head, name))
                if got is None:
                    bad.append(f"{label} {day} {name}: on file, not on the tab")
                    continue
                n_races += 1
                g = {who.rsplit(" (", 1)[0]: n for who, n, _m in got}
                for c in cands:
                    n_rows += 1
                    if g.get(c) != cands[c]:
                        bad.append(f"{label} {day} {name} {c}: the tab says {g.get(c)}, the files "
                                   f"{cands[c]}")
    assert n_races > 2000, f"only {n_races} races compared: the reading of the files has gone wrong"
    assert not bad, f"{len(bad)} count(s) on the tab are not the files': " + "; ".join(bad[:8])
    return "ok", (f"{n_rows:,} candidates' counts in {n_races:,} races of 2022 on, over {pages} town "
                  "and ward pages, are each the town rows' or the place rows' own sum")


@check("files", "a town page's Elections tab reads every place the results files print to a town "
                "of the district table, the short forms of the unincorporated places included, "
                "and none to two", needs=("town_elections",))
def _town_elections_places(TE):
    """Every printed place in every town rows file and every other office's place rows
    of 2016 on reads to a town of the table (here, the town rows' own spellings of 2022
    on), a ward of a city with ward pages to that ward; the eight known odd forms each
    to the town it names."""
    w = _te_world(TE, imp("build_members_elect"))
    if w is None:
        return "skip", "no collected/election_town_rows_*.csv in this checkout"
    ledger, _rows, _off, _res = w
    known = {"At. & Gil Ac. Gt": "Atk. & Gil. Academy Grant",
             "Atkinson & Gilmanton Ac Gt": "Atk. & Gil. Academy Grant",
             "Thomp. and Mes's Pur.": "Thompson & Mes's Purchase",
             "Thompson & Meserve's": "Thompson & Mes's Purchase",
             "Low & Burbank's Gt.": "Low & Burbank's Grant",
             "Laconia Wd 3": "Laconia", "Concord - Ward 10": "Concord"}
    for printed, town in known.items():
        got = ledger.places.place_of(printed)
        assert got and got[0] == town, f"{printed!r} reads to {got}, not {town}"
    assert ledger.places.place_of("Concord - Ward 10") == ("Concord", "10")
    assert ledger.places.place_of("Nowhere Ward 3") is None
    assert not ledger.unread, ("places read to no town: "
                               + ", ".join(f"{k} ({', '.join(sorted(v))})"
                                           for k, v in sorted(ledger.unread.items())))
    return "ok", (f"{len(ledger.places.memo)} printed places, each read to one town or ward; "
                  f"the {len(known)} odd forms tried each to its town")


@check("build", "a town page's Elections tab: a heading per year, newest first; in a year the "
                "general, then the specials newest first, and no State Primary (no town's count of "
                "one is on file); in an election the "
                "ballot's order, a floterial after the town's own district; the winner marked by "
                "the race's outcome, never the town's; a member's chip linked only where the "
                "member's own tab carries that very race",
       needs=("town_elections", "build_member_elections", "build_members_elect"))
def _town_elections_order_and_marks(TE, BMEL, BME):
    """On a made-up town: a race the town's leader lost, a primary handed in (not drawn: a
    town shows only its own counts, the owner, 19 November 2026, and the module reads no
    primary file), two specials in one year and one in the next, and a member matched to a
    race their own tab does not carry.
    Then on the files: every general race on every page marks as won exactly the race's
    winners, and the tab holds races where the town's leader lost, so that is tested."""
    def race(key, name, cands, seats=1, fl=False):
        return {"key": key, "name": name, "seats": seats, "floterial": fl, "href": "", "cands": cands,
                "scatter": 0, "unopposed": False}
    gen = {"day": "2024-11-05", "stage": "general", "party": "", "whole": False, "races": [
        race("H|Grafton|9", "State House, Grafton 9 (floterial)", [], fl=True),
        race("sheriff|Grafton", "Grafton County Sheriff", []),
        race("H|Grafton|12", "State House, Grafton 12", []),
        race("governor", "Governor", [
            {"name": "Ann Lead", "party": "d", "votes": 900, "won": False, "slug": ""},
            {"name": "Bo Win", "party": "r", "votes": 100, "won": True, "slug": ""}]),
        race("S|5", "State Senate, District 5", [])]}
    for r in gen["races"]:
        r["cands"] = r["cands"] or [{"name": "X Y", "party": "d", "votes": 1, "won": True, "slug": ""}]
    els = [dict(gen, races=list(gen["races"])),
           {"day": "2024-09-10", "stage": "primary", "party": "", "whole": True, "races": [
               dict(race("governor", "Governor", [{"name": "P Q", "party": "r", "votes": 5, "most": True,
                                                   "slug": ""}]), ballot="R")]},
           {"day": "2024-03-12", "stage": "special", "party": "", "whole": True, "races": [
               dict(race("H|Grafton|12", "State House, Grafton 12", [{"name": "S T", "party": "d", "votes": 3,
                                                                      "won": True, "slug": ""}]),
                    stage="special", day="2024-03-12", ballot="")]},
           {"day": "2024-06-04", "stage": "special", "party": "", "whole": True, "races": [
               dict(race("H|Grafton|9", "State House, Grafton 9", [{"name": "U V", "party": "r", "votes": 4,
                                                                    "won": True, "slug": ""}]),
                    stage="special", day="2024-06-04", ballot="")]},
           {"day": "2025-04-08", "stage": "special", "party": "", "whole": True, "races": [
               dict(race("H|Grafton|12", "State House, Grafton 12", [{"name": "W Z", "party": "d", "votes": 2,
                                                                      "won": True, "slug": ""}]),
                    stage="special", day="2025-04-08", ballot="")]}]
    html = "".join(TE.tab_cards(TE.sort_elections(els), "Lyme"))
    years = re.findall(r'<h3 class="twnh">(\d{4})</h3>', html)
    assert years == ["2025", "2024"], f"the years read {years}"
    heads = re.findall(r'<h4 class="te-el">([^<]*)</h4>', html)
    assert heads == ["Special election, April 8, 2025", "General election, November 5, 2024",
                     "Special election, June 4, 2024", "Special election, March 12, 2024"], (
        f"the elections read {heads}")
    assert "P Q" not in html and "primary, September" not in html, "a State Primary is drawn"
    import ast
    tree = ast.parse(_source(Path(TE.__file__)))
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    reads = [n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
             and n.attr in ("primaries_on_file", "primary_race", "PRIMARY_RE")]
    reads += [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and id(n) not in docs
              and isinstance(n.value, str) and n.value.startswith("primary_")]
    assert not reads, f"town_elections.py reads the State Primary: {reads}"
    names = re.findall(r"<h5>([^<]*)</h5>", html.split("Special election, June")[0].split("General election")[1])
    assert names == ["Governor", "State Senate, District 5", "State House, Grafton 12",
                     "State House, Grafton 9 (floterial)", "Grafton County Sheriff"], \
        f"the general's races read {names}"
    gov = re.search(r"<h5>Governor</h5>.*?</ul>", html, re.S).group(0)
    rows = re.findall(r'<li class="er-row">(.*?)</li>', gov, re.S)
    assert "Ann Lead" in rows[0] and "Won the race" not in rows[0], \
        "the town's leader, who lost the race, is marked as its winner"
    assert "Bo Win" in rows[1] and "Won the race" in rows[1], "the race's winner is not marked"
    # A member's chip: linked only where the member's own tab carries that race.
    keep_for = BMEL.member_for
    try:
        BMEL.member_for = lambda c, *a, **k: {"Ann Lead": {"id": "1", "slug": "ann-lead"},
                                              "Bo Win": {"id": "2", "slug": "bo-win"},
                                              "Cy Odd": {"id": "1", "slug": "ann-lead"}}.get(c["name"])
        res = {"races": {"H|Grafton|12": {"seats": 1, "candidates": [
            {"name": "Ann Lead", "party": "d", "votes": 900, "elected": True},
            {"name": "Bo Win", "party": "r", "votes": 100, "elected": False},
            {"name": "Cy Odd", "party": "l", "votes": 7, "elected": False}]}}}
        by_member = {"1": [{"d": "2024-11-05", "k": "H|Grafton|12", "v": 900}], "2": []}
        links = TE.member_links(by_member, [("2024-11-05", res, {}, {}, None)], [])
    finally:
        BMEL.member_for = keep_for
    assert links == {("2024-11-05", "general", "", "H|Grafton|12", "Ann Lead"): "ann-lead"}, \
        f"linked {links}: only a race the member's own tab carries, at its own count, links"
    linked = TE.race_card(race("H|Grafton|12", "State House, Grafton 12", [
        {"name": "Ann Lead", "party": "d", "votes": 900, "won": True, "slug": "ann-lead"},
        {"name": "Bo Win", "party": "r", "votes": 100, "won": False, "slug": ""}]))
    assert linked.count("<a href=") == 1 and 'href="legislator/ann-lead"' in linked, \
        "a chip is linked without a member, or not linked with one"
    # On the files: the winners are the race's, wherever the town's leader lost.
    w = _te_world(TE, BME)
    if w is None:
        return "ok", "order, marks and links held on a made-up town (no results in this checkout)"
    ledger, _rows, offices, results = w
    winners = {}
    for y, res in results.items():
        for k, r in res["races"].items():
            winners[(res["election"], TE.house_name(k, r.get("floterial")))] = {
                c["name"] for c in r["candidates"] if c.get("elected") is True}
    for y, doc in offices.items():
        for k, r in doc["races"].items():
            winners[(doc["election"], TE.office_name(k, r))] = {
                c["name"] for c in r["candidates"] if c.get("elected") is True}
    bad, upsets, n = [], 0, 0
    for town, wards in ledger.places.wards.items():
        for ward in wards:
            for e in ledger.for_page(town, ward):
                if e["stage"] != "general":
                    continue
                for r in e["races"]:
                    n += 1
                    marked = {c["name"] for c in r["cands"] if c["won"] is True}
                    want = winners[(e["day"], r["name"])] & {c["name"] for c in r["cands"]}
                    if marked != want:
                        bad.append(f"{town} {ward} {e['day']} {r['name']}: marked {sorted(marked)}, "
                                   f"the race's winners {sorted(want)}")
                    if r["seats"] == 1 and r["cands"] and r["cands"][0]["name"] not in want and want:
                        upsets += 1
                        card = TE.race_card(r)
                        first = re.findall(r'<li class="er-row">(.*?)</li>', card, re.S)[0]
                        if "Won the race" in first:
                            bad.append(f"{town} {ward} {e['day']} {r['name']}: the town's leader is "
                                       "drawn as the winner")
    assert upsets > 100, f"only {upsets} races where a town's leader lost: the test is not testing"
    assert not bad, f"{len(bad)} race(s) marked by the town, not the race: " + "; ".join(bad[:6])
    return "ok", (f"order, marks and links held on a made-up town; on the files {n:,} general "
                  f"races on the pages mark exactly the race's winners, {upsets:,} of them where "
                  "the town's own leader lost")


@check("build", "the Officials page's seven tabs say their short names, in both languages, over "
                "panels headed in full; and from the day a tab retires, an address naming it "
                "opens Legislators", needs=("build_town_pages",))
def _officials_tabs_fit_and_retire(B):
    """The owner, 7 November 2026, on the walk of dry run 4.

    SEVEN TABS ON ONE LINE. With Members-Elect the strip needed 1,282px of
    its 1,132 at 1280 and 1440, and the new tab showed only its "M" behind
    the edge, in English and in Spanish. The tabs say "Federal", "Executive",
    "Judicial" and "County" -- "Federal", "Ejecutivo", "Judicial" and
    "Condados", the plural, as the tab is the ten counties' -- with their
    counts, which measured 1,016px and about 979px on dry run 6 with the web
    fonts; the panels keep "Federal Delegation" and the
    rest as their headings, which a screen reader walking the headings and a
    page read without the script still get. Each Spanish word is a draft.

    A RETIRED TAB'S ADDRESS. From 2 December the Members-Elect tab hides
    itself, by the build or by the reader's own date, and
    /officials#members-elect opened six tabs with none chosen and nothing
    under them. The strip names Legislators as the tab such an address opens
    (data-retired), and TABS_JS opens it and writes it into the address; an
    address naming something inside the retired panel does the same; the day
    before, the tab opens as it always has; a strip naming no such tab opens
    its first one still shown; with no address the page opens My Town as
    before; and the arrow keys and End pass over a retired tab."""
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    bad = []
    full = {"federal": "Federal Delegation", "executive": "Executive Branch",
            "judicial": "Judicial Branch", "counties": "County Officials"}
    cat = json.loads(_source("src/pages/lang/es.json"))["strings"]
    short = {"en": {"federal": "Federal", "executive": "Executive", "judicial": "Judicial",
                    "counties": "County"},
             "es": {"federal": "Federal", "executive": "Ejecutivo", "judicial": "Judicial",
                    "counties": "Condados"}}
    for pid, en in short["en"].items():
        e = cat.get(f"of.tab_short.{pid}") or {}
        if (e.get("en"), e.get("es"), e.get("state")) != (en, short["es"][pid], "draft"):
            bad.append(f"es.json's of.tab_short.{pid} is {e}, not {en!r} and "
                       f"{short['es'][pid]!r} as a draft")
    for key, es in (("elect.elected", "Elección del {day}"), ("elect.takes", "Toma de posesión: {day}.")):
        e = cat.get(key) or {}
        if e.get("es") != es or e.get("state") != "draft":
            bad.append(f"es.json's {key} is {e}: the owner's words, a draft, read {es!r}, in "
                       "number with one member-elect and with many")
    for lang, rel in (("en", "officials.html"), ("es", "es/officials.html")):
        f = site / rel
        if not f.exists():
            if lang == "en":
                bad.append("the fixture built no officials.html")
            continue
        page = f.read_text(encoding="utf-8")
        strip = re.search(r'<div class="twntabs oftabs" role="tablist" aria-label="[^"]+" '
                          r'data-retired="legislators" hidden>(.*?)</div>', page, re.S)
        if not strip:
            bad.append(f"{rel}'s strip names no data-retired tab, or is not written hidden")
            continue
        for pid, word in short[lang].items():
            got = re.search(rf'id="tab-{pid}"[^>]*>([^<]*)', strip.group(1))
            if not got or got.group(1).strip() != word:
                bad.append(f"{rel}'s {pid} tab says {got and got.group(1)!r}, not {word!r}")
            head = re.search(rf'<div class="twnpane" id="{pid}"[^>]*><h2 class="twnph">([^<]*)</h2>',
                             page)
            want = full[pid] if lang == "en" else (cat.get(f"of.tab.{pid}") or {}).get("es")
            if not head or head.group(1) != want:
                bad.append(f"{rel}'s {pid} panel is headed {head and head.group(1)!r}, not "
                           f"{want!r}: the panel keeps the whole name")
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        assert not bad, "\n  ".join(bad)
        return "skip", "the labels and the strip's attribute hold; node is not installed to run TABS_JS"
    script = re.search(r"<script>\n(.*?)</script>", B.TABS_JS, re.S).group(1)
    harness = """
function node2(){
  const e = el(); e.attrs = {};
  e.setAttribute = function(k, v){ this.attrs[k] = String(v); };
  e.getAttribute = function(k){ return k in this.attrs ? this.attrs[k] : null; };
  e.focus = function(){ document.activeElement = this; };
  return e;
}
let [day, hsh, built, retired] = process.argv.slice(2);
const RealDate = Date;
globalThis.Date = class extends RealDate {
  constructor(...a){ if (a.length) super(...a); else super(day + "T12:00:00"); } };
const tabEls = ["my-town", "legislators", "members-elect"].map(p => {
  const t = node2(); t.dataset.pane = p; return t; });
tabEls[2].attrs["data-until"] = "2026-12-02";
if (built === "built") tabEls[2].hidden = true;
const panes = {};
tabEls.forEach(t => { const p = node2(); p.id = t.dataset.pane; panes[p.id] = p;
  p.closest = s => s === ".twnpane" ? p : null; });
const bar = node2(); bar.hidden = true;
if (retired !== "none") bar.attrs["data-retired"] = "legislators";
bar.querySelectorAll = () => tabEls;
bar.scrollWidth = 300; bar.clientWidth = 300; bar.scrollLeft = 0;
// The strip 100px above the window, where the browser's own jump to an
// address leaves it.
bar.getBoundingClientRect = () => ({left: 0, right: 300, top: -100});
tabEls.forEach((t, i) => { t.getBoundingClientRect = () => ({left: i * 100, right: i * 100 + 90}); });
bar.querySelector = () => tabEls.find(t => t.attrs["aria-selected"] === "true") || null;
document.querySelector = s => s === ".twntabs" ? bar : null;
const sec = node2(); sec.closest = s => s === ".twnpane" ? panes["members-elect"] : null;
let landed = 0; sec.scrollIntoView = () => { landed++; };
document.getElementById = id => panes[id] || (id === "elect-s-8" ? sec : null);
const wrote = []; history.replaceState = (a, b, u) => wrote.push(u); history.pushState = () => {};
const on = {}; globalThis.addEventListener = (t, f) => (on[t] = on[t] || []).push(f);
const scrolled = []; globalThis.scrollTo = (x, y) => scrolled.push(y); globalThis.scrollY = 1000;
Object.defineProperty(globalThis, "performance", {configurable: true,
  value: {getEntriesByType: () => [{type: "navigate"}]}});
document.fonts = {ready: {then: () => {}}};
location.hash = hsh; location.pathname = "/officials"; location.search = "";
const shown = () => Object.keys(panes).filter(p => !panes[p].hidden);
const out = {};
%s
out.load = shown(); out.wrote = wrote.slice();
(on.load || []).forEach(f => f()); out.landed = landed; out.lifted = scrolled.slice();
const key = k => { bar.fire("keydown", {key: k, preventDefault(){}});
  return [shown()[0], tabEls.indexOf(document.activeElement)]; };
document.activeElement = tabEls[0]; out.end = key("End");
document.activeElement = tabEls[0]; out.left = key("ArrowLeft");
location.hash = "#members-elect"; (on.hashchange || []).forEach(f => f());
out.change = shown(); out.wrote2 = wrote.slice();
// A page left open past midnight with the tab focused: at the reader's 2
// December the keys go from the tab it hands over to.
day = "2026-12-02"; document.activeElement = tabEls[2]; out.midnight = key("ArrowLeft");
process.stdout.write(JSON.stringify(out));
""" % script
    stub = _source("tests/dom_stub.js")
    after = ["/officials#legislators"]
    cases = [
        # (day, hash, built hidden, data-retired) -> shown, written, End, ArrowLeft, hashchange
        (("2026-12-01", "#members-elect", "", ""),
         (["members-elect"], [], ["members-elect", 2], ["members-elect", 2], ["members-elect"])),
        (("2026-12-02", "#members-elect", "", ""),
         (["legislators"], after, ["legislators", 1], ["legislators", 1], ["legislators"])),
        (("2026-12-02", "", "", ""),
         (["my-town"], [], ["legislators", 1], ["legislators", 1], ["legislators"])),
        (("2026-12-02", "#elect-s-8", "", ""),
         (["legislators"], after, ["legislators", 1], ["legislators", 1], ["legislators"])),
        (("2026-12-01", "#members-elect", "built", ""),
         (["legislators"], after, ["legislators", 1], ["legislators", 1], ["legislators"])),
        (("2026-12-02", "#members-elect", "", "none"),
         (["my-town"], ["/officials#my-town"], ["legislators", 1], ["legislators", 1],
          ["my-town"])),
        (("2026-12-02", "#legislators", "", ""),
         (["legislators"], [], ["legislators", 1], ["legislators", 1], ["legislators"]))]
    for args, (load, wrote, end, left, change) in cases:
        r = subprocess.run([node, "-e", stub + "\n" + harness, "x", *args],
                           capture_output=True, encoding="utf-8", timeout=60)
        if r.returncode:
            bad.append("the tab script would not run: " + r.stderr[-300:])
            break
        got = json.loads(r.stdout)
        where = f"on {args[0]}, arriving at {args[1] or 'no address'!r}" + (
            ", the tab built hidden" if args[2] else "") + (
            ", the strip naming no tab for it" if args[3] else "")
        if got["load"] != load or got["wrote"] != wrote:
            bad.append(f"{where} shows {got['load']} and writes {got['wrote']}, not {load} "
                       f"and {wrote}")
        if got["landed"]:
            bad.append(f"{where} brought the page to something inside a retired panel")
        # Sent from a retired tab, the reader is shown the strip once the page
        # has loaded, with what they were given chosen; anyone else is not moved.
        sent = bool(args[1]) and wrote and wrote[0] != "/officials" + args[1]
        lift = [892] if sent else []
        if got["lifted"] != lift:
            bad.append(f"{where}, the page was scrolled to {got['lifted']} by load, not {lift}: "
                       "a reader sent from a retired tab is shown the strip, and nobody else is "
                       "moved")
        if got["end"] != end or got["left"] != left:
            bad.append(f"{where}, End and ArrowLeft from My Town gave {got['end']} and "
                       f"{got['left']}, not {end} and {left}: the keys pass over a retired tab")
        if got["change"] != change:
            bad.append(f"{where}, a link to #members-elect then shows {got['change']}, not {change}")
        # From Legislators, ArrowLeft is My Town; from My Town, where a strip
        # naming no tab hands over, it goes round to Legislators.
        night = ["legislators", 1] if args[3] == "none" else ["my-town", 0]
        if got["midnight"] != night:
            bad.append(f"{where}, ArrowLeft on the tab once it has retired gave {got['midnight']}, "
                       f"not {night}: the keys go from the tab it hands over to")
    # FROM THE BUILD OF 2 DECEMBER the tab is not drawn at all, and its
    # address, or a heading inside it, named nothing: OFFICIALS_HASH_JS sends
    # it to #legislators before TABS_JS reads it, while nothing has that id.
    import build_pages as BP
    alias = re.search(r"<script>(.*?)</script>", BP.OFFICIALS_HASH_JS, re.S).group(1)
    probe = ("var L={},loc={pathname:'/officials',search:'',hash:process.argv[2]};"
             "var ids=process.argv[3]?process.argv[3].split(','):[];"
             "global.location=loc;global.document={getElementById:function(i){"
             "return ids.indexOf(i)>=0?{}:null;}};global.history={replaceState:function(s,t,u){"
             "var i=u.indexOf('#');loc.hash=i<0?'':u.slice(i);}};"
             "global.addEventListener=function(n,f){(L[n]=L[n]||[]).push(f);};"
             + alias + ";process.stdout.write(loc.hash);")
    for hsh, ids, want in (("#members-elect", "", "#legislators"),
                           ("#of-elect-house", "", "#legislators"),
                           ("#of-elect-senate", "", "#legislators"),
                           ("#members-elect", "members-elect", "#members-elect"),
                           ("#of-elect-house", "members-elect,of-elect-house", "#of-elect-house"),
                           ("#elect-nothing", "", "#elect-nothing"),
                           ("#statewide", "", "#executive"),
                           # By district went (the walk of 8 November 2026): its
                           # view's address opens By county, and its chambers'
                           # headings are By county's now; once the tab has
                           # gone, Legislators.
                           ("#pane-edist", "members-elect,pane-ecounty", "#pane-ecounty"),
                           ("#tab-edist", "members-elect,pane-ecounty", "#pane-ecounty"),
                           ("#of-eld-house", "members-elect,of-eld-house", "#of-eld-house"),
                           ("#pane-edist", "", "#legislators"),
                           ("#of-eld-senate", "", "#legislators"),
                           ("#of-eld-house", "", "#legislators"),
                           ("#pane-elast", "", "#legislators"),
                           ("#pane-ecounty", "", "#legislators")):
        r = subprocess.run([node, "-e", probe, "x", hsh, ids], capture_output=True,
                           encoding="utf-8", timeout=60)
        if r.returncode or r.stdout != want:
            bad.append(f"/officials{hsh} with {ids or 'nothing'} on the page becomes "
                       f"{r.stdout or r.stderr[-200:]!r}, not {want!r}")
    assert not bad, "\n  ".join(bad)
    return "ok", ("Federal, Executive, Judicial and County -- Federal, Ejecutivo, Judicial and "
                  "Condados -- over panels headed in full; from 2 December #members-elect, or a "
                  f"section in it, opens Legislators and says so in the address ({len(cases)} "
                  "cases in node)")


@check("build", "a town page's State House and Senate cards say how many of a district's seats "
                "are vacant, in the map's word, and never that no member is matched",
       needs=("build_town_pages",))
def _town_seats_vacant(B):
    """The audit of 25 October 2026: a district with nobody sitting said "No
    sitting member is matched to this district", which reads as the site
    failing, and Gilford's four-seat district listed its three members and
    nothing about the fourth. Each card now ends a district's members with
    "1 seat vacant" or "N seats vacant", the word the district map's legend
    and panel use, as a row of the list; a full district says nothing of
    the kind. Read off representatives_sections, on a four-seat district
    with three members, a floterial with nobody, a full one and an empty
    Senate seat."""
    def rep(name, chamber, district):
        return {"name": name, "display_full": f"Rep. {name}", "party": "Republican",
                "slug": name.lower().replace(" ", "-"), "chamber": chamber, "county": "Belknap",
                "district": district, "email": "", "phone": ""}
    legs = [rep(n, "H", "5") for n in ("Ann One", "Bo Two", "Cy Three")] + [rep("Di Four", "H", "6")]
    dist = {"senate": 7, "house": [
        {"county": "Belknap", "district": 5, "floterial": False, "seats": 4},
        {"county": "Belknap", "district": 6, "floterial": False, "seats": 1},
        {"county": "Belknap", "district": 8, "floterial": True, "seats": 2}]}
    got = "".join(B.representatives_sections(dist, legs, {}))
    parts = re.split(r'<h4 class="twnsub">', got.split('<h3 class="twnh">State Senate', 1)[0])[1:]
    senate = got.split('<h3 class="twnh">State Senate', 1)[1].split("</section>", 1)[0]
    row = '<li class="offrow"><span class="offwho">{}</span></li>'
    bad = []
    if len(parts) != 3:
        bad.append(f"the State House card has {len(parts)} districts, not 3")
    else:
        five, six, eight = parts
        if five.count('class="mchip') != 3 or not five.endswith(row.format("1 seat vacant") + "</ul>"):
            bad.append("Belknap 5's three members of four are not followed by \"1 seat vacant\"")
        if "vacant" in six:
            bad.append("a full district is said to have a seat vacant")
        if row.format("2 seats vacant") not in eight or "No sitting" in eight:
            bad.append("a floterial with nobody in its two seats does not say \"2 seats vacant\"")
    if row.format("1 seat vacant") not in senate:
        bad.append("a Senate seat with nobody in it does not say \"1 seat vacant\"")
    if "matched" in got:
        bad.append("a card still says that no member is matched to a district")
    assert not bad, "; ".join(bad)
    return "ok", ("3 of 4 seats and \"1 seat vacant\", a full district quiet, \"2 seats vacant\" "
                  "on an empty floterial and \"1 seat vacant\" on an empty Senate seat")


@check("data", "town_officials.json holds addresses or notes, never half of each")
def _town_officials_cells():
    """The file the town pages read, held to what the parser now writes.

    Data, and not code, because this file is regenerated rather than edited:
    a parser fix does nothing for the site until `parse_officials.py` has been
    run again, and until then the town pages go on publishing the old values.
    An e-mail cell with an "@" is an address; a phone is a number, with an
    extension if it has one, or one of the four cells NHDOT prints that are
    not -- each named below.
    """
    f = Path("collected/town_officials.json")
    if not f.exists():
        return "skip", "no town_officials.json here"
    P = imp("parse_officials")
    if P is None:
        return "skip", "parse_officials.py does not import"
    B = imp("build_town_pages")
    if B is None:
        return "skip", "build_town_pages.py does not import"
    # As the directory prints them: Barnstead's second selectman carries the
    # administrator's extension, Plaistow's cell holds two numbers, and
    # Grafton's and Wentworth's town numbers are one digit short.
    printed = {"ext. 4", "603-382-5200 ext. 266 VM 603- 382-6771",
               "603-523-770", "603-764-995"}
    data = json.loads(f.read_text(encoding="utf-8"))
    bad, n = [], 0
    for key, v in sorted(data.items()):
        phones = [("town", v.get("phone") or "")]
        for o in v.get("officials") or []:
            n += 1
            e = o.get("email") or ""
            if "@" in e and not P.EMAIL_OK.match(e):
                bad.append(f"{key}: {o.get('name')}'s e-mail {e!r}")
            phones.append((o.get("name"), o.get("phone") or ""))
        for who, ph in phones:
            if ph and not B.PHONE.match(ph) and ph not in printed:
                bad.append(f"{key}: {who}'s phone {ph!r}")
    assert not bad, (
        "town_officials.json carries cells the parser no longer writes -- run "
        "parse_officials.py and rebuild the town pages:\n  " + "\n  ".join(bad[:12]))
    return "ok", f"{n} offices, every e-mail cell an address or a note"


@check("files", "every correction still corrects what the source actually says")
def _corrections_still_apply():
    """A correction outlives the thing it corrects, and that is the danger.

    place_corrections.json overrides three polling places the Secretary of
    State's own list gets wrong -- Errol Town Hall with Colebrook's street and
    ZIP, on three rows, which would send a voter thirty miles to the wrong
    town. Each correction records what the list SAYS as well as what it should
    say, and parse_clerks_csv.py refuses to apply one whose `source_says` no
    longer matches.

    This is the check for the other half of that: a correction the Secretary
    of State has since fixed is a correction that should be deleted, and one
    still silently sitting in the file is the site overriding a good value
    with a stale one. Neither is caught by anything downstream, because the
    output looks exactly as intended either way.
    """
    if not Path("corrections/place_corrections.json").exists():
        return "skip", "no place_corrections.json here"
    src = Path("records/sources/sos-clerks-and-polling-places-2026-09-20.csv")
    if not src.exists():
        return "skip", "the clerk list export is not in records/sources/"
    m = imp("parse_clerks_csv")
    if m is None:
        return "skip", "parse_clerks_csv.py does not import"

    fixes = json.loads(Path("corrections/place_corrections.json").read_text(encoding="utf-8"))
    towns = m.load_towns("site")
    import csv as _csv
    with open(src, encoding="utf-8-sig", newline="") as fh:
        rows = list(_csv.DictReader(fh))
    _data, unmatched, applied, stale = m.build(rows, towns, fixes)

    want = set(fixes.get("polling_place", {}))
    bad = list(stale)
    missed = want - set(applied)
    if missed:
        bad.append(f"corrections that matched no row at all: {sorted(missed)}")
    if unmatched:
        bad.append(f"{len(unmatched)} rows of the export name no town this "
                   f"site has: {unmatched}")
    assert not bad, "\n  ".join(bad)
    return "ok", (f"{len(applied)} correction(s) applied, each against the "
                  f"value the export still carries")


@check("files", "GRANIT's geometry carries the districts we publish")
def _granit_carries_our_districts():
    """A map cannot be better than the boundaries under it.

    NH GRANIT's 2022 layers are a fourth witness to `districts/house.txt`, and
    an independent one: a GIS office digitising boundaries rather than anybody
    transcribing a list. 164 base polygons and 39 coded floterial ones, whose
    codes agree with ours exactly.

    The floterial layer is the part worth guarding. Both House shapefiles are
    required to depict all districts, they genuinely overlap, and a map built
    on the base layer alone silently drops 39 districts and the members
    elected from them. If that count ever stops matching, the geometry and the
    record have parted company.

    Skips when the zips are absent: they are 4.2 MB, not in git, and
    re-fetchable from ftp.granit.unh.edu.
    """
    if not Path("records/sources/gis/NHHouseDistricts2022_Base.zip").exists():
        return "skip", "records/sources/gis/ has no GRANIT zips"
    g = imp("parse_granit")
    if g is None:
        return "skip", "parse_granit.py does not import"

    layers, problems = g.survey()
    hc = g.house_codes()
    bad = list(problems)
    if hc:
        if hc["granit_base"] != hc["ours_base"]:
            bad.append(f"base districts differ: only GRANIT "
                       f"{sorted(hc['granit_base'] - hc['ours_base'])}, only "
                       f"ours {sorted(hc['ours_base'] - hc['granit_base'])}")
        if hc["granit_floterial"] != hc["ours_floterial"]:
            bad.append(f"floterial districts differ: only GRANIT "
                       f"{sorted(hc['granit_floterial'] - hc['ours_floterial'])}, "
                       f"only ours "
                       f"{sorted(hc['ours_floterial'] - hc['granit_floterial'])}")
    assert not bad, "\n  ".join(bad)
    n = sum(v["polygons"] for v in layers.values() if v.get("present"))
    return "ok", (f"{n} polygons across {sum(1 for v in layers.values() if v.get('present'))} "
                  f"layers; {len(hc['granit_base'])} base and "
                  f"{len(hc['granit_floterial'])} floterial House districts "
                  f"agreeing with districts/house.txt")


def _seats_held(page):
    """{"H"/"S": {"seats", "held", "vacant", "parties": {code: n}}}: what the
    Legislators tab's "Who holds the seats" draws (build_pages.static_bar),
    read off the English Officials page -- off its Legislators panel alone,
    for the Members-Elect tab draws its "Who won the seats" in the same bars
    between an election and Organization Day."""
    i = page.find('<div class="twnpane" id="legislators"')
    if i >= 0:
        j = page.find('<div class="twnpane"', i + 1)
        page = page[i:j if j > 0 else len(page)]
    out = {}
    for name, filled, legend in re.findall(
            r'<div class="comp"><div class="compline"><b>(House|Senate)</b>'
            r'<span class="statemeta">([^<]*)</span></div><div class="pbar2">.*?</div>'
            r'<div class="plegend">(.*?)</div>', page, re.S):
        m = re.match(r"(\d+) of (\d+) seats filled(?:, (\d+) vacant)?$", filled)
        assert m, f"the {name}'s line is {filled!r}"
        got = dict((c, int(n)) for c, n in re.findall(
            r'<span class="pdot seg-([^"]+)"></span>[^<]*<b>(\d+)</b>', legend))
        vac = got.pop("V", 0)
        assert vac == int(m.group(3) or 0), f"the {name}'s vacant seats are said two ways"
        out[name[0]] = {"seats": int(m.group(2)), "held": int(m.group(1)), "vacant": vac,
                        "parties": got}
    return out


@check("frontend", "the district map says the chamber shown statewide under its legend -- the "
                   "State House's and the State Senate's seats by party and the vacant ones, "
                   "counted from the sitting members it colours the districts by, a floterial's "
                   "once -- following the layer switch, in English and Spanish, nothing on the "
                   "Council and US House, and the Legislators tab's \"Who holds the seats\" "
                   "the same numbers")
def _map_party_totals():
    """The owner, 7 November 2026: "IF IT FITS: on the map, a short list of
    the party totals for the chamber layer shown (Senate or House):
    Democrats, Republicans, Independents, statewide."

    map.js in node (_map_totals_run) on three maps built here:
      - from the tracked files (_map_data) with a roster of real seats: in
        the State House a Republican and a Democrat in Hillsborough 21, an
        Independent in Strafford 7, two Democrats in the floterial
        Hillsborough 40 and one in Merrimack 10; in the Senate a Republican
        in 16 and Democrats in 9 and 21. totals() is the roster counted here
        by chamber and party, each member once -- the floterial's two not
        again under the wards below it -- over the seats the district files
        give, a seat nobody holds vacant;
      - the same map with every seat filled but one: "1 vacant", and no
        vacant seats said where there are none;
      - the fixture's built site/district_map.json, whose numbers must be
        those its Officials page's Legislators tab draws under "Who holds
        the seats" (build_pages.static_bar, from home.json's composition).
    Held of each: the line mounted under the legend is totalsLine(totals())
    for State House and State Senate, and empty for the Council and the US
    House, on the way there and back; it reads "Statewide House: 1
    Republican · 3 Democrats · ..." in the legend's order, each count in its
    own unbreakable span, and in Spanish the catalog's words with none of
    the English left; it is written inside the legend's box after the legend,
    and not at all for a mount that asks for no totals. And map.css draws
    an empty line not at all and keeps each count whole."""
    import i18n
    css = _source("src/pages/map.css")
    assert re.search(r"\.gm \.gmtot:empty\{display:none\}", css), \
        "map.css draws the empty totals line (.gmtot:empty) on the Council and US House"
    assert re.search(r"\.gm \.gmtot \.gmti\{white-space:nowrap\}", css), \
        "map.css lets a phone break a count (.gmti) in two"

    def rep(name, county, d, party, chamber="H"):
        return {"name": name, "chamber": chamber, "county": county, "district": str(d),
                "party": party, "slug": name.lower().replace(" ", "-"),
                "display_full": f"Rep. {name} ({party[0]} - x)", "sort": name}
    roster = [rep("Ann Ray", "Hillsborough", 21, "Republican"),
              rep("Bo Dee", "Hillsborough", 21, "Democrat"),
              rep("Cy Indy", "Strafford", 7, "Independent"),
              rep("Di Flo", "Hillsborough", 40, "Democrat"),
              rep("Ed Flo", "Hillsborough", 40, "Democrat"),
              rep("Jo Mer", "Merrimack", 10, "Democrat"),
              rep("Fay Sen", "Hillsborough", 16, "Republican", chamber="S"),
              rep("Gus Sen", "Hillsborough", 9, "Democrat", chamber="S"),
              rep("Hal Sen", "Hillsborough", 21, "Democrat", chamber="S")]
    data = _map_data(roster)
    if data is None:
        return "skip", "the geometry, the district files or the officials file is not here"
    flo = set(data["layers"]["float"]["f"])
    assert "HI40" in flo and "HI21" not in flo, "Hillsborough 40 is no longer the floterial here"
    import build_district_map as BDM

    # The roster counted here, each member once, against the district files' seats.
    def expect(members, seats_by):
        held = Counter()
        for m in members:
            held[m["code"]] += 1
        parties = Counter(m["party"][0] for m in members)
        return {"seats": sum(seats_by.values()), "held": len(members),
                "vacant": sum(max(0, n - held[c]) for c, n in seats_by.items()),
                "parties": [[p, parties[p]] for p in "RDI" if parties[p]]}
    house = [{"code": f"{BDM.CODE[m['county']]}{m['district']}", "party": m["party"]}
             for m in roster if m["chamber"] == "H"]
    senate = [{"code": m["district"], "party": m["party"]} for m in roster if m["chamber"] == "S"]
    want = {"roster": {"base": expect(house, data["seats"]),
                       "senate": expect(senate, {f: 1 for f in data["layers"]["senate"]["f"]})}}
    # Every seat filled but one State House seat.
    full = json.loads(json.dumps(data))
    full["who"] = {k: v for k, v in full["who"].items() if k.startswith(("exec|", "cong|"))}
    short = sorted(data["seats"])[0]
    for code, n in data["seats"].items():
        lk = "float" if code in flo else "base"
        full["who"][f"{lk}|{code}"] = [{"n": f"R{code}{i}", "p": "R", "s": ""}
                                       for i in range(n - (code == short))]
    for f in data["layers"]["senate"]["f"]:
        full["who"][f"senate|{f}"] = [{"n": f"D{f}", "p": "D", "s": ""}]
    want["full"] = {"base": {"seats": sum(data["seats"].values()), "held": sum(data["seats"].values()) - 1,
                             "vacant": 1, "parties": [["R", sum(data["seats"].values()) - 1]]},
                    "senate": {"seats": 24, "held": 24, "vacant": 0, "parties": [["D", 24]]}}
    maps = {"roster": data, "full": full}
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    fix_map, fix_page = site / "district_map.json", site / "officials.html"
    assert fix_map.is_file() and fix_page.is_file(), \
        "the fixture's build wrote no district_map.json or officials.html"
    maps["fixture"] = json.loads(fix_map.read_text(encoding="utf-8"))
    got = _map_totals_run(maps)
    if got is None:
        return "skip", "node is not installed (map.css read: the empty line hidden, counts whole)"

    bad = []
    for name, by in want.items():
        for lk, t in by.items():
            if got[name]["totals"][lk] != t:
                bad.append(f"{name} {lk}: totals() is {got[name]['totals'][lk]}, not {t}")
    # The fixture's map against its own Legislators tab.
    tab = _seats_held(fix_page.read_text(encoding="utf-8"))
    if set(tab) != {"H", "S"}:
        bad.append(f"the fixture's Officials page draws \"Who holds the seats\" for {sorted(tab)}")
    for ch, lk in (("H", "base"), ("S", "senate")):
        t, s = got["fixture"]["totals"][lk], tab.get(ch)
        if s and (not t or {**t, "parties": dict(t["parties"])} != s):
            bad.append(f"fixture {lk}: the map counts {t}, the Legislators tab draws {s}")

    def words(t, lk, lang):
        """The line totalsLine draws, as text, in `lang`, from the catalog."""
        say = (lambda k, en, **v: i18n.say("es", k, en, **v)) if lang == "es" else \
            (lambda k, en, **v: i18n.fill(en, v))
        noun = {"R": ("map.r_one", "{n} Republican", "map.r_many", "{n} Republicans"),
                "D": ("map.d_one", "{n} Democrat", "map.d_many", "{n} Democrats"),
                "I": ("map.i_one", "{n} Independent", "map.i_many", "{n} Independents")}
        # a letter but R, D and I as map.js's countWords says it: "2 Ls"
        its = [(say(*noun[p][:2], n=n) if n == 1 else say(*noun[p][2:], n=n)) if p in noun
               else f"{n} {p}" + ("" if n == 1 else "s") for p, n in t["parties"]]
        if t["vacant"]:
            its.append(say("map.n_vacant_one", "{n} vacant", n=1) if t["vacant"] == 1
                       else say("map.n_vacant", "{n} vacant", n=t["vacant"]))
        head = say("map.statewide", "Statewide")
        body = (say("map.tot_senate", "<b>Senate:</b> {list}", list=" · ".join(its)) if lk == "senate"
                else say("map.tot_base", "<b>House:</b> {list}", list=" · ".join(its)))
        return _map_totals_text(head + " " + body)

    english = ("Statewide", "House", "Senate", "Republican", "Democrat", "Independent", "vacant")
    for name, one in got.items():
        for lk in ("exec", "cong", "county", "towns"):
            if one["totals"][lk] is not None or one["lines"][lk] != "":
                bad.append(f"{name}: the {lk} layer has a total {one['totals'][lk]} {one['lines'][lk]!r}")
        for lk in ("base", "senate"):
            t, line = one["totals"][lk], one["lines"][lk]
            if not t:
                bad.append(f"{name}: no totals for {lk}")
                continue
            n = len(t["parties"]) + (1 if t["vacant"] else 0)
            if len(re.findall(r'<span class="gmti">', line)) != n:
                bad.append(f"{name} {lk}: the {n} counts are not each a whole span: {line[:160]!r}")
            if _map_totals_text(line) != words(t, lk, "en"):
                bad.append(f"{name} {lk}: the line reads {_map_totals_text(line)!r}, "
                           f"not {words(t, lk, 'en')!r}")
        for lang in ("en", "es"):
            seq = one["drawn_" + lang]
            for lk, html_ in seq:
                t = one["totals"][lk]
                said = _map_totals_text(html_)
                if lk in ("exec", "cong"):
                    if html_:
                        bad.append(f"{name} {lang}: on {lk} the map says {said!r}")
                    continue
                if said != words(t, lk, lang):
                    bad.append(f"{name} {lang}: on {lk} after {[x for x, _ in seq]} the map says "
                               f"{said!r}, not {words(t, lk, lang)!r}")
                if lang == "es" and any(re.search(r"\b" + w + r"\b", said) for w in english):
                    bad.append(f"{name}: the Spanish line says English: {said!r}")
        if not re.search(r'<div class="gmkey"><div class="gmleg"[^>]*></div><p class="gmtot"></p>',
                         one["markup"]):
            bad.append(f"{name}: mount() writes no totals line straight after the legend")
        if "gmtot" in one["markupNone"]:
            bad.append(f"{name}: a mount asking for no totals still writes their line")
    assert not bad, "; ".join(bad[:6])
    f = got["fixture"]["totals"]
    return "ok", (f"\"{_map_totals_text(got['roster']['lines']['base'])}\" and "
                  f"\"{_map_totals_text(got['roster']['lines']['senate'])}\" for the roster, a "
                  f"floterial's two once; \"1 vacant\" and none said; Spanish whole; nothing on "
                  f"the Council and US House; the fixture's {f['base']['held']} of "
                  f"{f['base']['seats']} and {f['senate']['held']} of {f['senate']['seats']} the "
                  "Legislators tab's own")


@check("build", "every district on the map is filled from the record's party, and a vacant "
                "one is not filled", needs=("build_district_map",))
def _map_fills_from_the_record(BDM):
    """A district is filled with the party of who sits for it (the D5 inks):
    its sitting members' parties, Republican, then Democratic, then
    Independent, drawn as equal stripes where there are two or more; a
    district every seat of which is vacant is filled with nothing, and the map
    hatches it. A base district by its OWN members (method (a), 8 October
    2026) and a floterial by its own, framed. The Executive Council and the US
    House from corrections/officials.json.

    Built from the tracked files with a roster of real seats: Manchester ward 1
    (Hillsborough 21) with a Republican and a Democrat, Rochester ward 3
    (Strafford 7) with an Independent, the floterial Hillsborough 40 with two
    Democrats, who must fill the floterial and not the wards under it, Senate
    16 with a Republican, and Coos 6 with nobody. Then every district of every
    filled layer against the members the build put there, every member in
    exactly one district, and counties and towns filled with nothing.
    """
    def rep(name, county, d, party, chamber="H"):
        return {"name": name, "chamber": chamber, "county": county, "district": str(d),
                "party": party, "slug": name.lower().replace(" ", "-"),
                "display_full": f"Rep. {name} ({party[0]} - x)", "sort": name}
    roster = [rep("Ann Ray", "Hillsborough", 21, "Republican"),
              rep("Bo Dee", "Hillsborough", 21, "Democrat"),
              rep("Cy Indy", "Strafford", 7, "Independent"),
              rep("Di Flo", "Hillsborough", 40, "Democrat"),
              rep("Ed Flo", "Hillsborough", 40, "Democrat"),
              rep("Fay Sen", "Hillsborough", 16, "Republican", chamber="S")]
    data = _map_data(roster)
    if data is None:
        return "skip", "the geometry, the district files or the officials file is not here"
    f = data["fill"]
    want = {("base", "HI21"): "RD", ("base", "ST7"): "I", ("float", "HI40"): "D",
            ("senate", "16"): "R", ("base", "CO6"): "", ("senate", "1"): "",
            ("base", "HI22"): ""}
    got = {k: f[k[0]].get(k[1]) for k in want}
    assert got == want, f"the fills are {got}, not {want}"
    assert "county" not in f and "towns" not in f, "counties or towns are filled by party"
    placed = [p["n"] for k, ps in data["who"].items() if not k.startswith(("exec|", "cong|"))
              for p in ps]
    assert sorted(placed) == sorted(m["display_full"] for m in roster), (
        f"the roster's members are not each in one district: {placed}")
    off = _officials_now()
    for lk, office in (("exec", "council"), ("cong", "us_house")):
        for num, o in off[office]["districts"].items():
            assert f[lk][str(int(num))] == o["party"][:1].upper(), (
                f"{lk} {num} is filled {f[lk][str(int(num))]!r}; officials.json says {o['party']}")
    wrong = []
    for lk in ("base", "float", "senate", "exec", "cong"):
        assert set(f[lk]) == set(data["layers"][lk]["f"]), f"{lk}: a district has no fill entry"
        for fid, v in f[lk].items():
            ps = {p["p"] for p in data["who"].get(f"{lk}|{fid}", [])}
            if v != "".join(x for x in "RDI" if x in ps) + "".join(sorted(ps - set("RDI"))):
                wrong.append(f"{lk} {fid}: {v!r} for {sorted(ps)}")
    assert not wrong, "filled otherwise than its members' parties: " + "; ".join(wrong[:6])
    return "ok", (f"{sum(len(v) for v in f.values())} districts filled from their members; "
                  "stripes, an Independent, a floterial apart and a vacancy as the record has them")


@check("files", "the district map's geometry is as fresh as its inputs",
       needs=("build_district_geometry",))
def _map_geometry_fresh(BDG):
    """generated/district_geometry.json is built by a person from NH GRANIT's
    zips (src/towns/build_district_geometry.py), which only the laptop holds,
    and committed; the night publishes it. So nothing rebuilds it when an
    input moves, and this is what notices.

    Held always: the file names the builder's own stamp, so a builder changed
    since it was run fails until it is run again; its State House base and
    floterial codes, Senate, Executive Council and US House numbers, ten
    counties and every town are exactly records/districts/'s, so a
    redistricting that changes the district files without the map fails here
    instead of drawing old lines quietly; and every feature has rings that
    name arcs the file holds and a label point inside the map. Held where the
    zips are on this disk: each one's sha256 is the one the file was built
    from.
    """
    p = Path("generated/district_geometry.json")
    if not p.exists():
        return "skip", "generated/district_geometry.json is not here"
    g = json.loads(p.read_text(encoding="utf-8"))
    src = _source(_paths.locate("build_district_geometry.py"))
    stamp = re.search(r"GRANITE_VERSION:\s*(\S+)", src).group(1)
    assert g.get("_builder") == stamp, (
        f"the geometry was written by build_district_geometry.py {g.get('_builder')}, and the "
        f"builder is now {stamp}: run python3 src/towns/build_district_geometry.py where the "
        "GIS zips are, and commit what it writes")
    rec = BDG.record_names()
    bad = [f"{lk}: only in the geometry {sorted(set(g['layers'][lk]['f']) - rec[lk])[:6]}, "
           f"only in records/districts {sorted(rec[lk] - set(g['layers'][lk]['f']))[:6]}"
           for lk in BDG.LAYERS if set(g["layers"][lk]["f"]) != rec[lk]]
    assert not bad, "the geometry and the district files disagree:\n  " + "\n  ".join(bad)
    counts = {lk: len(g["layers"][lk]["f"]) for lk in BDG.LAYERS}
    assert counts == {"base": 164, "float": 39, "senate": 24, "exec": 5, "cong": 2,
                      "county": 10, "towns": 259}, f"the layers hold {counts}"
    n, broken = len(g["arcs"]), []
    for lk in BDG.LAYERS:
        for fid, f in g["layers"][lk]["f"].items():
            refs = [r if r >= 0 else ~r for ring in f["r"] for r in ring]
            x, y = f["l"]
            if not f["r"] or any(r >= n for r in refs) or not (0 <= x <= g["w"] and 0 <= y <= g["h"]):
                broken.append(f"{lk} {fid}")
        if any(a >= n for a in g["layers"][lk]["m"]):
            broken.append(f"{lk}'s borders")
    assert not broken, "features with no rings, arcs not in the file or a label off the map: " \
        + ", ".join(broken[:8])
    gis = Path("records/sources/gis")
    here = {z: d for z, d in g["_inputs"].items() if (gis / z).exists()}
    import hashlib
    moved = [z for z, d in here.items() if hashlib.sha256((gis / z).read_bytes()).hexdigest() != d]
    assert not moved, (f"{', '.join(moved)} changed since the geometry was built: run "
                       "python3 src/towns/build_district_geometry.py and commit what it writes")
    return "ok", (f"built by {stamp}; {sum(counts.values())} features agreeing with "
                  f"records/districts; " + (f"all {len(here)} zips' digests agree" if len(here) == len(g["_inputs"])
                                            else "the GIS zips are not on this disk, so their digests "
                                                 "were not compared"))


@check("files", "our district files still say what the Secretary of State's do")
def _districts_match_sos():
    """districts/*.txt had no provenance at all until this check.

    No source URL, no retrieval date, no statement of which redistricting plan
    they encode -- and everything the site says about who represents a town
    rests on them. They are now checked against "Towns and Wards as Districted
    for Election Purposes 2022", the Secretary of State's own table, whose
    embedded CreationDate is 26 April 2023.

    The comparison is worth having precisely because the two run in opposite
    directions: that table is one row per place naming its districts, ours is
    one district naming its places. An error would have to be made twice, by
    two people, from two directions, to survive both.

    This fails if either side moves. A redistricting, a hand edit, a re-export
    of the table: any of them should be a decision somebody makes, not a
    difference that appears.
    """
    if not Path("records/sources/sos-towns-and-wards-districted-2023-04-26.pdf").exists():
        return "skip", "the Secretary of State's table is not in records/sources/"
    m = imp("parse_sos_districts")
    if m is None:
        return "skip", "parse_sos_districts.py does not import"
    try:
        import pdfplumber                                    # noqa: F401
    except Exception:
        return "skip", "pdfplumber is not installed"

    rows, notes, theirs, mine, only_theirs, only_mine, diffs = m.compare()
    bad = []
    if only_theirs:
        bad.append(f"{len(only_theirs)} places are in the Secretary of State's "
                   f"table and not in ours: {only_theirs[:6]}")
    if only_mine:
        bad.append(f"{len(only_mine)} places are in ours and not in the "
                   f"Secretary of State's table: {only_mine[:6]}")
    for field, items in diffs.items():
        bad.append(f"{len(items)} disagree on {field}: "
                   + "; ".join(f"{k} ours {a} theirs {b}" for k, a, b in items[:5]))
    assert not bad, (
        "the Secretary of State's published district table and districts/*.txt "
        "no longer agree. Theirs is the legal definition and ours is what the "
        "site publishes, so a difference here is a difference between what a "
        "reader is told and what the law says:\n  " + "\n  ".join(bad))
    return "ok", (f"{len(theirs)} places and wards, every congressional, "
                  f"Executive Council, senatorial and representative district "
                  f"agreeing")


@check("files", "the five lists of New Hampshire places still reconcile")
def _places_reconcile():
    """Five lists count the same state and get five different answers.

    districts/*.txt has 320 rows, town_clerks.json 339, town_officials.json
    234, db/Towns.psv 273, and the Secretary of State's own page 331. None is
    wrong -- they count different things -- but every tool that joins two of
    them has to decide what a place is, and before places.json that decision
    was made separately, and differently, in each of them.

    The arithmetic that makes them one list is the check, because it is what
    breaks silently. A town that gains a ward, a district file edited for a
    new plan, a re-export of the clerk list with more rows: each moves one
    number and leaves the rest alone, and a join that used to be one-to-one
    quietly stops being.

    This recomputes from the sources rather than trusting places.json, so a
    stale places.json fails rather than agreeing with itself.
    """
    if not Path("generated/places.json").exists():
        return "skip", "no places.json here; run build_places.py"
    bp = imp("build_places")
    if bp is None:
        return "skip", "build_places.py does not import"

    places, disagree, synthetic, _ = bp.build()
    saved = json.loads(Path("generated/places.json").read_text(encoding="utf-8"))["places"]

    assert not disagree, (
        "the four district files no longer name the same places: "
        + "; ".join(f"{k} differs on {len(v)} rows" for k, v in disagree.items()))

    assert places.keys() == saved.keys(), (
        f"places.json is stale: {len(places)} places rebuild from the sources, "
        f"{len(saved)} are saved. Re-run build_places.py.")

    n = len(places)
    gc_rows = sum(len(p["named_by"]["districts"]["wards"]) or 1 for p in places.values())
    sos_rows = sum(len(p["named_by"]["sos_clerks"]["wards"]) or 1
                   for p in places.values()
                   if p["named_by"]["sos_clerks"]["present"])
    in_off = sum(1 for p in places.values()
                 if p["named_by"]["nhdot_officials"]["present"])

    clerks = json.loads(Path("collected/town_clerks.json").read_text(encoding="utf-8")) \
        if Path("collected/town_clerks.json").exists() else None

    bad = []
    if gc_rows != 320:
        bad.append(f"districts/*.txt should come to 320 rows, not {gc_rows}")
    if sos_rows != 331:
        bad.append(f"the clerk list should come to 331 rows, not {sos_rows}")
    if clerks is not None and len(clerks) != sos_rows + len(synthetic):
        bad.append(f"town_clerks.json has {len(clerks)} keys; the clerk list's "
                   f"{sos_rows} rows plus {len(synthetic)} synthesised "
                   f"town-level rows come to {sos_rows + len(synthetic)}")
    if in_off != 234:
        bad.append(f"NHDOT's directory should name 234 of them, not {in_off}")
    if n - in_off != 25:
        bad.append(f"{n - in_off} places are absent from NHDOT's directory, not "
                   f"the 25 unincorporated places")

    # A ward is a property of a place AS A PARTICULAR LIST WARDS IT. Where both
    # lists ward a place they must ward it the same way, or a polling place
    # will be filed under a ward that district does not have.
    for key, p in places.items():
        a = p["named_by"]["districts"]["wards"]
        b = p["named_by"]["sos_clerks"]["wards"]
        if a and b and a != b:
            bad.append(f"{key} is warded {a} by the district files and {b} by "
                       f"the clerk list")
        if p["county"] is None:
            bad.append(f"{key} is not in exactly one county")

    assert not bad, "\n  ".join(bad)
    return "ok", (f"{n} places = {in_off} in NHDOT's directory + {n - in_off} "
                  f"unincorporated; {gc_rows} district rows, {sos_rows} clerk "
                  f"rows + {len(synthetic)} synthesised")
