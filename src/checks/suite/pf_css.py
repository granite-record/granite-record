#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
preflight's checks of the stylesheet (app.css).

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import math
import os
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_run, _source, check)
from pf_fixture import (_fixture_site_shared)
from pf_harness import (_app_js, _components_js, _node_app, _node_file, _with_components)
from pf_shared import (_BALLOTPEDIA, _HEARD_PRELUDE, _MANUAL_1999, _RAIL_FACE, _SOS_2024,
                       _SUMMARY_VOTES, _VW_DOT_HEAD, _braced, _built_sites, _css_can_reach,
                       _css_decls, _css_font_size, _css_hex, _css_palette, _css_px, _css_ratio,
                       _css_rules, _css_screen_rules, _css_selectors, _css_token_colour,
                       _css_won, _front_sources, _html_walk, _line_of, _vw_loose_dots)


@check("frontend", "bills.html carries the changes and its tags balance")
def _bills_html():
    p = Path("src/pages/bills.html")
    if not p.exists():
        p = Path("site/bills.html")
    if not p.exists():
        return "skip", "bills.html not here or in site/"
    # Most of what this looks for lives in app.js now, which bills.html loads
    # rather than contains. Reading only the page would pass every one of these
    # by finding nothing to disagree with -- so the page is read together with
    # the files it pulls in, and it is an error if those are missing.
    t = p.read_text(encoding="utf-8")
    for asset in ("app.css", "components.js", "app.js"):
        f = p.parent / asset
        assert f.exists(), (f"bills.html loads {asset} and it is not next to "
                            f"it in {p.parent}/")
        t += "\n" + f.read_text(encoding="utf-8")
    want = {
        "play control is a button": '<button type="button" class="pstub"',
        # A link inside a button is not a link a keyboard or a screen reader
        # can reach, so this one sits outside the card's expand button. What it
        # is called changed once already; anchoring on the tag rather than the
        # wording is what the check is actually about.
        # Since 10 October 2026 the number is that link (C5), and the title
        # is the button; the corner arrow went with the button it sat beside.
        "detail link outside the button": '<a class="cnum" href="${esc(c.href)}" translate="no">',
        "page heading": '<h1 class="sr">',
        # The player opens AT the boundary, not before it. The old lead was
        # five minutes for an estimate, which put the reader in the middle of
        # the previous bill and then made the page explain a time that was not
        # the bill's. Two seconds is enough not to clip the first syllable.
        "player opens at the mark": "h.from=Math.max(Math.floor(s.start-2),0)",
        # One word, and only where the placement is an inference rather than
        # something the chair said. The tolerance, which of two dates was being
        # shown, and "about where it ends" were methodology in the way.
        "an inferred start says so": "h.approx=!s.start_stated",
        "consent bills get no timestamp": 'st==="consent"',
        "member sort key": "(a.s||a.n||\"\")",
        # A jump button pressed before the player exists must build the
        # player AT that time. Clicking the stub instead builds it at the
        # opening offset -- up to five minutes earlier -- and then posts
        # seekTo into an iframe created a line before, which YouTube is not
        # listening on yet. The video then sits at a different time from the
        # button that was pressed, which is what a reader sees as the player
        # and the printed timestamps disagreeing.
        # Per-bill data is addressed by its filing year, because a bill number
        # is unique within a term and not beyond it. A 2027 HB686 would
        # otherwise overwrite this one's docket, votes and recordings.
        # A record small enough travels inside its own page, so what is
        # fetched is the page and not a JSON file beside it. Still addressed
        # by filing year, for the same reason: a bill number is unique within
        # a term and not beyond it.
        "the record is read from the bill's own page, under its year":
            "DATA(`bill/${yr}/${id.toLowerCase()}`)",
        "a record too large to inline is followed to its own file":
            'meta[name="gr-data"]',
        # /bill/2026/hb1123, which is what a person pastes. The year is the
        # point of the check and it is still there; only the shape changed,
        # from a hash on the search page to the bill's own address.
        "the address carries the year": '`${BASE}bill/${_y}/${id.toLowerCase()}`',
        "a cold jump loads the player at the time asked for":
            "st.dataset.embed=`${vid}|${Math.max(0,Math.floor(Number(t)))}|${p2}`",
        "tab panels": 'role="tabpanel"',
        "visually hidden class": ".sr{position:absolute",
    }
    missing = [k for k, v in want.items() if v not in t]
    assert not missing, "missing: " + ", ".join(missing)
    assert "<h5" not in t, "an <h5> survived the heading pass"
    import re as _re
    bad = []
    for tag in ("div", "button", "article", "main", "p", "span"):
        o = len(_re.findall(rf"<{tag}[\s>]", t))
        c = len(_re.findall(rf"</{tag}>", t))
        if o != c:
            bad.append(f"{tag} {o}/{c}")
    assert not bad, "unbalanced: " + ", ".join(bad)
    if t.count("`") % 2:
        raise AssertionError("odd number of backticks; a template literal is open")
    extra = ""
    if shutil.which("node"):
        js = "\n".join(_re.findall(r"<script>(.*?)</script>", t, _re.S))
        f = Path(tempfile.mkdtemp()) / "b.js"
        f.write_text(js, encoding="utf-8")
        r = _run(["node", "--check", str(f)], capture_output=True, text=True)
        shutil.rmtree(f.parent, ignore_errors=True)
        assert r.returncode == 0, "node --check: " + r.stderr.strip()[:150]
        extra = ", node --check clean"
    return "ok", f"7 markers present, tags balanced{extra}"


@check("frontend", "the assets are revalidated, and no page names a version")
def _asset_headers():
    """What replaced "a page asks for the script it was built against".

    That check guarded `?v=<hash>`, which pointed every page at the exact
    bytes it was built with. It worked, and it cost a gigabyte a publish: the
    hash is inside the HTML, so one changed byte of app.css rewrote all
    34,000 record pages and Cloudflare had to be sent every one of them.

    site/_headers does the same job from the other end -- the three asset
    files are `max-age=0, must-revalidate`, which is what Pages already
    serves HTML and JSON as -- so this asserts both halves: the file says it,
    and no page has quietly started naming a version again.
    """
    site = Path("site")
    if not (site / "bills.html").exists():
        return "skip", "site/bills.html not built"

    hdr = site / "_headers"
    assert hdr.exists(), ("site/_headers is not there, so app.js and app.css "
                          "are served max-age=14400 with nothing in the page "
                          "to tell a browser they changed")
    text = hdr.read_text(encoding="utf-8")
    want = "max-age=0, must-revalidate"
    missing = [a for a in ("/app.js", "/app.css", "/components.js")
               if not re.search(re.escape(a) + r"\s*\n\s*Cache-Control:[^\n]*"
                                + re.escape(want), text)]
    assert not missing, (f"site/_headers does not give {', '.join(missing)} "
                         f"{want}")

    pages = [site / "bills.html", site / "index.html",
             site / "officials.html"]
    for folder, pat in (("bill", "*/*.html"), ("legislator", "*.html"),
                        ("committee", "*.html"), ("town", "*.html")):
        got = sorted((site / folder).glob(pat))
        if got:
            pages.append(got[len(got) // 2])

    bad = []
    for f in pages:
        if not f.exists():
            continue
        for m in re.finditer(r'(?:src|href)="((?:app|style)\.(?:js|css))\?v=',
                             f.read_text(encoding="utf-8")):
            bad.append(f"{f} still names a version on {m.group(1)}")
    assert not bad, "; ".join(sorted(set(bad))[:3])
    return "ok", (f"_headers names all three, and none of "
                  f"{len([f for f in pages if f.exists()])} page kinds "
                  f"carries a version query")


@check("frontend", "one palette, and every pair of it measures up")
def _palette():
    """Contrast, computed from the tokens, not asserted about their spelling.

    WCAG 2.1: 4.5:1 for body text, 3:1 for a control boundary. The audit of
    7 September found eleven pairs below those and this is what stops them
    coming back -- including the five that were the same bug, a secondary grey
    used on tinted status boxes it had never been checked against.

    ONE PALETTE: build_pages.py used to carry its own copy, which had
    drifted -- --st-veto was #7C2D3A in one file and #8C4A2F in the other --
    and then a style.css cut from this one. Every page loads app.css now
    (23 October 2026), so there is no second copy to compare.

    BOTH SCHEMES, since 12 September. Dark mode shipped with its pairs
    measured by hand and nothing to stop them drifting, which is the same
    position the light palette was in before the 7 September audit. The two
    things checked here that a hand measurement keeps forgetting:

      * Dark defines EVERY colour the light block does. A token missing from
        one scheme is not a slightly-wrong colour, it is the light value
        surviving into the dark page -- white text on a white chip. This is
        the failure mode, and it is the cheap one to catch.
      * A card is still visibly a card. The note at the top of app.css
        records that the page ground was darkened on purpose to put 1.20:1
        between a card and the paper behind it, 1.08:1 being below the level
        at which most people see an edge at all. The first dark ground
        drafted gave that back at 1.13:1 and looked fine in a screenshot,
        because an edge you cannot see is exactly what a screenshot cannot
        show.
    """
    def root_of(text, which="light"):
        # Everything the palette owns stops at the marker.
        end = text.find("/* PALETTE END")
        head = text[:end] if end > 0 else text
        i = head.find(":root{")
        if i < 0:
            return {}
        shut = head.index("}", head.index("--sans:", i))
        if which == "light":
            block = head[i:shut + 1]
        else:
            # BY MARKER, NOT BY THE SECOND ":root{". There are two dark blocks
            # now -- one behind the media query for the system preference and
            # one behind [data-theme="dark"] for the reader's own choice --
            # and neither selector is a bare ":root{" any more, so the old
            # search found nothing and would have reported a complete palette
            # as having no dark half at all.
            tag = {"dark": "/* DARK:OS", "dark2": "/* DARK:CHOSEN"}[which]
            k = head.find(tag)
            if k < 0:
                return {}
            block = head[k:head.find("/* DARK:", k + len(tag))
                         if head.find("/* DARK:", k + len(tag)) > 0 else len(head)]
        # Keyed WITHOUT the leading "--", because that is how the pairs
        # below name them and a dict keyed the other way silently matches
        # nothing while every assertion still runs.
        return {k[2:]: v for k, v in re.findall(
            r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{3,6})\s*[;}]", block)}

    def lum(h):
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        ch = []
        for i in (0, 2, 4):
            v = int(h[i:i + 2], 16) / 255
            ch.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]

    def ratio(a, b):
        x, y = sorted((lum(a), lum(b)), reverse=True)
        return (x + 0.05) / (y + 0.05)

    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = _source(css)
    tok = root_of(text, "light")
    assert tok, "app.css has no :root block this can read"
    dark = root_of(text, "dark")
    assert dark, (
        "app.css has no dark :root block. It is a "
        "@media(prefers-color-scheme:dark) block under the light one, above "
        "the /* PALETTE END */ marker.")

    # EVERY COLOUR, IN BOTH. A token defined once is the light value showing
    # through on the dark page.
    # THE TWO DARK BLOCKS MUST BE THE SAME TOKENS. They are the same values
    # written twice because CSS cannot put one declaration block behind both a
    # media query and a selector; app.css says why at length. This is what
    # makes the duplication safe: drift is a failed build, not a page that is
    # the wrong colour by one route and right by the other.
    dark2 = root_of(text, "dark2")
    assert dark2, ("app.css has no /* DARK:CHOSEN */ block. The theme control "
                   "in the nav sets [data-theme] and needs one.")
    drift2 = sorted(k for k in set(dark) | set(dark2)
                    if dark.get(k, "").lower() != dark2.get(k, "").lower())
    assert not drift2, (
        "the two dark blocks disagree about "
        + ", ".join("--" + k for k in drift2[:4])
        + ". DARK:OS serves the system preference and DARK:CHOSEN the "
          "reader's own choice; they are the same palette and must stay "
          "identical.")

    missing = sorted(set(tok) - set(dark))
    assert not missing, (
        "the dark palette does not redefine " + ", ".join("--" + m for m in missing)
        + ". Every token is redefined in both blocks; a colour inherited from "
        "the light block is how white text ends up on a white chip.")
    spare = sorted(set(dark) - set(tok))
    assert not spare, (
        "the dark palette defines " + ", ".join("--" + s for s in spare)
        + ", which the light one does not. A token that exists in one scheme "
        "only will fall back to nothing in the other.")

    TEXT = [("ink", "surface"), ("ink", "paper"),
            ("ink-2", "surface"), ("ink-2", "paper"), ("ink-2", "wash"),
            ("pine", "surface"), ("pine", "paper")]
    for st in ("active", "law", "done", "study", "veto", "table"):
        TEXT += [(f"st-{st}", f"st-{st}-bg"), ("ink-2", f"st-{st}-bg")]
    BOUND = [("edge", "surface"), ("edge", "paper"),
             ("pine", "surface"), ("pine", "paper")]
    # The rail's discs are graphics on the card and the page, and their white
    # glyph -- check, cross, "~", two bars -- is the card's own colour on them
    # (8 October 2026: interim study's orange and the table's yellow).
    for st in ("law", "done", "study", "table"):
        BOUND += [(f"st-{st}", "surface"), (f"st-{st}", "paper")]
    # A meeting's kind: its ink is the chip's text on its tint, and it is also
    # the card's edge bar and the chip's edge on the card and the page -- and,
    # since 25 September 2026, the Calendar's box for that kind, whose tick
    # is drawn in the card's own ground on the ink, so the same 3:1 holds it.
    # The sixth, study and statutory committees, joined the five that day.
    for k in ("hear", "meet", "exec", "conf", "floor", "study"):
        TEXT += [(f"cal-{k}", f"cal-{k}-bg")]
        BOUND += [(f"cal-{k}", "surface"), (f"cal-{k}", "paper")]
    # KEY DATES' GOLD (24 October 2026, the owner: the elections, town
    # meeting days and deadlines "under a separate meeting type in the key"):
    # its ink as the six kinds' are, and its tint is also the ground of a key
    # date's card and of Coming up's key-date lines, so the words drawn on it
    # -- the name, the source line, the links -- hold 4.5:1 there too.
    TEXT += [("cal-date", "cal-date-bg"), ("ink", "cal-date-bg"),
             ("ink-2", "cal-date-bg"), ("pine", "cal-date-bg")]
    BOUND += [("cal-date", "surface"), ("cal-date", "paper")]

    bad, n = [], 0
    for scheme, t in (("light", tok), ("dark", dark)):
        for pairs, need, kind in ((TEXT, 4.5, "text"), (BOUND, 3.0, "boundary")):
            for fg, bg in pairs:
                if fg not in t or bg not in t:
                    bad.append(f"--{fg} or --{bg} is not defined in {scheme}")
                    continue
                n += 1
                r = ratio(t[fg], t[bg])
                if r < need:
                    bad.append(f"--{fg} on --{bg} is {r:.2f}:1 in {scheme}, "
                               f"{kind} needs {need}")
        # A CARD HAS TO LOOK LIKE AN OBJECT. Not a WCAG threshold -- it is
        # this site's own decision, recorded at the top of app.css, and the
        # floor is set below the 1.20:1 that decision picked rather than at
        # it, so a deliberate future adjustment is not a failure.
        sep = ratio(t["surface"], t["paper"])
        if sep < 1.15:
            bad.append(
                f"a card is {sep:.2f}:1 against the page in {scheme}, and the "
                "note at the top of app.css sets 1.20:1 on purpose -- at "
                "1.08:1 most people see no edge at all. A screenshot cannot "
                "show this; only the number can.")
    assert not bad, "; ".join(bad[:4])
    return "ok", f"{n} pairs across both schemes, all above their threshold"


@check("frontend", "a fiscal note's table on a phone is one row per line with its years beneath: "
       "short headings, nothing wider than its box, the same table to a screen reader, and "
       "the desktop table as it was")
def _fiscal_note_on_a_phone():
    """The person, 7 November 2026, of HB 1034 of 2026's fiscal note at 375px:
    the table was 357px in a 288px box, FY 2029 off the edge, FY 2028 cut to
    "$C", the box scrolling sideways, "FY / 2026" and "Funding / Source"
    wrapped. Her layout, phones only: each row's name on its own line, its
    figures in a compact row beneath under short headings (FY26), a row that
    spans the years its value once, captions wrapping.

    Held from both ends. THE MARKUP, drawn by app.js's fiscalTable in node
    from a made-up note: every figure carries its short heading (data-y) and
    its row the class that decides how many share a line -- "fns" for six
    characters or fewer, "fnm" for up to forty, "fnl" past that, "fnspan" for
    a spanning row, which keeps its colspan and no heading -- the table, its
    groups, rows, heads and cells their roles, so a row drawn as a flex line
    stays a table to a screen reader; a raw note draws no table. THE
    STYLESHEET: inside @media (max-width:45em) alone, the wrapper does not
    scroll, the table and caption are blocks, the column heads are hidden
    the way the Data page's are (in the accessibility tree, not on screen),
    each body row wraps, the name takes a line of its own, "fns" figures share
    one, "fnm" at most two, "fnl" and a span one each, and the short heading
    is drawn with alternative text "" so it is not read twice; and outside it
    the desktop rules still scroll the wrapper and give the table its 22em."""
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    css = Path("src/pages/app.css")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and css.exists() and node):
        return "skip", "app.js, app.css, dom_stub.js or node is not here"
    note = {"lead": "", "tables": [
        {"caption": "Estimated Political Subdivision Impact",
         "years": ["FY 2026", "FY 2027", "FY 2028", "FY 2029"],
         "rows": [{"label": "Revenue", "values": ["$0", "$5,000", "$0", "$0"], "span": False},
                  {"label": "Revenue Fund", "values": ["General Fund"], "span": True},
                  {"label": "Expenditures*", "values": ["$0", "Indeterminable Increase",
                                                        "$15,000,000", "$0"], "span": False},
                  {"label": "Appropriations*", "values": ["$0", "x" * 41, "$0", "$0"],
                   "span": False}],
         "footnote": "*Expenditure = Cost of bill"},
        {"caption": "", "raw": ["The Office of Legislative Budget Assistant states this bill has no fiscal impact."]}]}
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "note.json").write_text(json.dumps(note), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({fiscalTable})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
process.stdout.write("\\n@@" + JSON.stringify(s.fiscalTable(JSON.parse(fs.readFileSync("./note.json", "utf8")))));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not draw a fiscal note under node: " + (r.stderr or r.stdout or "")[-300:])
        page = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    bad = []
    flat = re.sub(r"\s+", " ", page)
    if flat.count('<table class="fn" role="table">') != 1:
        bad.append("the note's one table is not drawn once as table.fn with role=\"table\"")
    rows = re.findall(r'<tr role="row" class="([^"]*)"><th scope="row" role="rowheader">([^<]*)</th>(.*?)</tr>', flat)
    want = {"Revenue": "fns", "Revenue Fund": "fnspan", "Expenditures*": "fnm", "Appropriations*": "fnl"}
    if {lab: cls for cls, lab, _ in rows} != want:
        bad.append(f"the rows' classes are {[(lab, cls) for cls, lab, _ in rows]}, not {want}")
    for cls, lab, cells in rows:
        heads = re.findall(r'<td role="cell" data-y="([^"]*)">', cells)
        if cls == "fnspan":
            if heads or '<td colspan="4" role="cell">' not in cells:
                bad.append(f"the spanning row {lab!r} does not keep its colspan, or carries a year heading")
        elif heads != ["FY26", "FY27", "FY28", "FY29"]:
            bad.append(f"{lab!r}'s figures carry the headings {heads}, not FY26 to FY29")
    if flat.count('role="columnheader"') != 5 or flat.count('role="rowgroup"') != 2:
        bad.append("the column heads or the row groups lost their roles")
    if '<div class="fnraw">' not in flat or flat.count("<table") != 1:
        bad.append("a raw note is not drawn as its plain lines")

    # Spacing is no part of a rule: "a, b" is "a,b", and "(max-width: 45em)"
    # the phone's width as much as "(max-width:45em)" is.
    rules = [(ctx, re.sub(r"\s*,\s*", ",", sel), body, ln) for ctx, sel, body, ln
             in _css_rules(_source(css))]
    on_phone = lambda ctx: any(re.sub(r"\s+", "", c) == "@media(max-width:45em)" for c in ctx)
    phone_only = re.compile(r"\.fn(?:s|m|l|span)\b|\[data-y\]")
    phone = {sel: dict(_css_decls(body)) for ctx, sel, body, _ in rules
             if on_phone(ctx) and ("table.fn" in sel or ".fnwrap" in sel)}
    desk = {sel: dict(_css_decls(body)) for ctx, sel, body, _ in rules
            if not ctx and ("table.fn" in sel or ".fnwrap" in sel)}
    # What only a phone may do: a rule of the reflow's own classes anywhere
    # else, a table.fn rule inside another width's at-rule, or the desktop's
    # table.fn rules laying it out as anything but a table.
    stray = sorted({sel for ctx, sel, body, _ in rules
                    if not on_phone(ctx) and phone_only.search(sel)}
                   | {sel for ctx, sel, body, _ in rules
                      if ctx and not on_phone(ctx) and "table.fn" in sel
                      and not any(c.startswith("@media print") or "forced-colors" in c for c in ctx)}
                   | {sel for sel, d in desk.items()
                      if {"display", "flex", "flex-wrap", "flex-basis", "content"} & set(d)})

    def has(rules_, sel, prop, test):
        v = rules_.get(sel, {}).get(prop)
        return v is not None and test(v)
    need = [
        (".fnwrap", "overflow-x", lambda v: v == "visible", "the wrapper still scrolls sideways"),
        ("table.fn", "display", lambda v: v == "block", "the table is not a block"),
        ("table.fn", "min-width", lambda v: v == "0", "the table keeps a minimum width"),
        ("table.fn caption", "display", lambda v: v == "block", "the caption does not wrap as a block"),
        ("table.fn thead", "clip", lambda v: "rect(0 0 0 0)" in v.replace(",", " "),
         "the column heads are not hidden the Data page's way"),
        ("table.fn tbody tr", "flex-wrap", lambda v: v == "wrap", "a row does not wrap its figures"),
        ("table.fn tbody th", "flex", lambda v: v.split()[-1] == "100%", "the row's name does not take a line"),
        ("table.fn td", "flex", lambda v: v.split()[-1] in ("0", "0%"), "\"fns\" figures do not share a line"),
        ("table.fn td", "max-width", lambda v: v == "100%",
         "a figure can run past its row (a flex item never shrinks below its longest word without it)"),
        ("table.fn tbody tr.fnm td", "flex-basis", lambda v: v == "40%", "\"fnm\" figures are not two to a line"),
        ("table.fn tbody tr.fnl td,table.fn td[colspan]", "flex-basis", lambda v: v == "100%",
         "\"fnl\" figures and a span are not one to a line"),
    ]
    for sel, prop, test, why in need:
        if not has(phone, sel, prop, test):
            bad.append(f"phone: {why} ({sel} {{{prop}: {phone.get(sel, {}).get(prop)}}})")
    before = phone.get("table.fn td[data-y]::before", {})
    contents = [v for k, v in _css_decls(next((body for ctx, sel, body, _ in rules
                                               if sel == "table.fn td[data-y]::before"), ""))
                if k == "content"]
    if contents != ['attr(data-y)', 'attr(data-y) / ""'] or before.get("display") != "block":
        bad.append(f"phone: the short heading is not drawn above its figure with alternative text \"\" "
                   f"(content {contents})")
    if not (has(desk, ".fnwrap", "overflow-x", lambda v: v == "auto")
            and has(desk, "table.fn", "min-width", lambda v: v == "22em")):
        bad.append("desktop: the wrapper no longer scrolls or the table lost its 22em: the desktop "
                   "table is not as it was")
    if stray:
        bad.append(f"the phone's fiscal-table layout reaches past its 45em block: {stray}")
    assert not bad, "; ".join(bad)
    return "ok", ("fiscalTable gives each figure its short heading and each row its class, keeps "
                  "a span's colspan and every role; app.css reflows it within 45em alone and the "
                  "desktop table keeps its scroller and 22em")


# ---- the type floor and the palette's reach (8 October 2026) ------------------
#
# WRITTEN AHEAD OF THE CHANGE THEY HOLD, and holding it since the polish's
# foundation landed (8 October 2026): every size in rem, nothing under the
# 13px floor, every colour a token, and the party and vote inks apart in
# lightness. Each was committed marked as expected to fail
# (check(expect_fail=)) and the mark came off in the commit that made it
# pass. These read the files, which is all preflight may;
# src/checks/rendered_sweep.py measures the drawn page.

_FLOOR_PX = 13          # nothing smaller, and this size only in capitals

# THE ONE PLACE 13px IS MIXED CASE (the person, 8 October 2026). Looking at the
# foundation's phone screenshots -- "I think the mobile text scaling might be a
# bit off and I preferred the old bill card previews on mobile" -- they chose a
# compact phone card whose rail sets its stops' names and days at 13px, "the
# approved floor; nothing under 13px"; and where the rail is too narrow for its
# days, at a large text setting, its names keep that size on a bill's own page
# too. The floor stands: these rules are allowed 13px in mixed case, under
# exactly these queries and by exactly this token, and nothing else is.
_MIXED_13_TOKEN = "--t-rail"
_MIXED_13 = {
    (("@media (max-width:37.5em)",), ".card:not(.focus) .rail.dated :is(.stop i,small)"),
    (("@container rail (max-width:19.5em)",), ".rail.dated .stop i"),
}


@check("frontend", "every text size is set in rem and every breakpoint in em, so the text size a "
                   "reader sets in the browser reaches every element and the layout it needs")
def _sizes_follow_the_reader():
    """The browser's own text size -- the setting older readers are told to
    change -- reaches a size written in rem and none written in px: before
    8 October 2026 every size on the site was px, and at a 24px setting the
    rendered sweep found 0 of 63 views drew a character larger. So no font
    size in px or pt, in app.css's tokens and rules, the inline styles of the
    builders, app.js and find.js; and no media or container query, nor a
    script's matchMedia, in px, because a breakpoint in em moves with the
    same setting and hands larger text the narrower layout it needs instead
    of crowding the wide one. --measure, which holds a line to a number of
    characters, is in rem for the same reason.

    The vote rings write their words into the SVG in the ring's own units
    (the font-size attribute), which follow the setting only because the
    ring's box is sized in rem; that is held here too."""
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = _source(css)
    bad, sizes, queries = [], 0, 0
    # A size is read through var() to what it is: a token of any name holding
    # a px size is a px size wherever it is used (the review of 8 October
    # 2026 hid "--note-size:15px" behind var() and this passed it).
    tokens = _css_palette(text)["light"]
    for ctx, sel, body, ln in _css_rules(text):
        for k, v in _css_decls(body):
            size = _css_font_size(k, v) if not k.startswith("--t-") else v
            if size is None:
                continue
            sizes += 1
            how = _css_px(size, tokens)[1] if size.startswith("var(") else ""
            if re.search(r"\d(px|pt)\b", size) or how in ("px", "pt"):
                bad.append(f"app.css:{ln} {sel[:40]} sets {k} in "
                           f"{how or re.search(r'(px|pt)', size).group(1)}")
    for m in re.finditer(r"@(media|container)([^{]*)\{", re.sub(r"/\*.*?\*/", "", text, flags=re.S)):
        if re.search(r"(?:min|max)-(?:width|height)", m.group(2)):
            queries += 1
            if re.search(r"(?:min|max)-(?:width|height)\s*:\s*[\d.]+px", m.group(2)):
                bad.append(f"@{m.group(1)}{m.group(2).rstrip()} is in px")
    meas = _css_palette(text)["light"].get("--measure", "")
    if not meas.endswith("rem"):
        bad.append(f"--measure is {meas or 'not defined'}, not rem")
    donut = re.search(r"(?:^|[}\s])\.donut\{([^}]*)\}", text)
    if not donut or not re.search(r"width:[\d.]+rem", donut.group(1)):
        bad.append("the vote ring's box is not sized in rem, so the words written in its own "
                   "units do not follow the reader's text size")
    inline = 0
    for name, src in _front_sources():
        for m in re.finditer(r"font-size\s*:\s*([^;\"'`}<>]+)", src):
            inline += 1
            if re.search(r"\d(px|pt)\b", m.group(1)):
                bad.append(f"{name}:{_line_of(src, m.start())} sets text in px inline")
        for m in re.finditer(r"matchMedia\(\s*[\"'`]([^\"'`]*)", src):
            if re.search(r"(?:min|max)-width\s*:\s*[\d.]+px", m.group(1)):
                bad.append(f"{name}:{_line_of(src, m.start())} asks matchMedia({m.group(1)}) in px")
        # And a size a script sets as it runs: .style.fontSize, setProperty
        # and cssText, which no rule above reads.
        for m in re.finditer(r"\.style\.fontSize\s*=\s*([^;\n]+)|setProperty\(\s*[\"'`]font-size"
                             r"[\"'`]\s*,\s*([^)\n]+)|cssText\s*\+?=\s*([^;\n]+)", src):
            val = next(g for g in m.groups() if g is not None)
            if m.group(3) is not None and not re.search(r"font(?:-size)?\s*:", val):
                continue
            if re.search(r"\d(px|pt)\b", val):
                bad.append(f"{name}:{_line_of(src, m.start())} sets text in px from a script")
    assert sizes > 300 and queries > 40, (
        f"only {sizes} sizes and {queries} width queries were read in app.css; there were "
        "445 and 59 on 8 October 2026, so the reader has stopped reading")
    assert not bad, f"{len(bad)} sizes or breakpoints in px: " + "; ".join(bad[:12]) + (
        f" (+{len(bad) - 12} more)" if len(bad) > 12 else "")
    return "ok", (f"{sizes} sizes and {queries} width queries in app.css, {inline} inline sizes "
                  "in the builders and scripts: every size in rem, every breakpoint in em, the "
                  "measure and the vote ring's box in rem")


@check("frontend", "no text is set under the 13px floor, and 13px only in capitals and the phone "
                   "card's rail: not by a "
                   "token or a rule of app.css, an inline style of a builder, app.js or find.js, "
                   "nor an SVG's font-size")
def _type_floor():
    """The floor of the type scale, read from every place a size is written.

    A size is held to it at the browser's default of 16px: px as written,
    rem at 16, pt at 4/3. A token is read through var() to its value, and a
    rule that sets its size by a token under the floor is counted under the
    token rather than listed. A size relative to its parent (em, %, a
    keyword) cannot be read from a file and is left to the rendered sweep;
    a var() nothing defines is a size this cannot vouch for, and fails (the
    browser drops the declaration and the text takes its parent's size,
    which is how --t-h3 went unnoticed). 13px is the floor for capitals
    only, so a rule at 13px must set text-transform: uppercase itself --
    except the phone card's rail (_MIXED_13, the person's choice of 8 October
    2026), sized by --t-rail, which nothing else may use.

    Outside app.css: the inline styles of every builder in src/pages/, of
    app.js and find.js, and the font-size attribute of SVG text, which no
    stylesheet and no browser setting reaches (the vote rings' letters).
    _FRONT_EXEMPT names what is left out and why."""
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = _source(css)
    tokens = _css_palette(text)["light"]
    low = {k: px for k, (px, _) in ((k, _css_px(v, tokens)) for k, v in tokens.items()
                                     if k.startswith("--t-")) if px is not None and px < _FLOOR_PX}
    bad, uses, read, relative = [], Counter(), 0, 0
    allowed = set()
    for ctx, sel, body, ln in _css_rules(text):
        ds = _css_decls(body)
        caps = any(k == "text-transform" and "uppercase" in v for k, v in ds)
        if any(_MIXED_13_TOKEN in v for k, v in ds if _css_font_size(k, v) is not None) \
                and (ctx, sel) not in _MIXED_13:
            bad.append(f"app.css:{ln} {sel[:48]} is sized by {_MIXED_13_TOKEN}, which is the "
                       "phone card's rail's and nothing else's")
        for k, v in ds:
            size = _css_font_size(k, v)
            if size is None:
                continue
            read += 1
            px, how = _css_px(size, tokens)
            if px is None:
                if how.startswith("undefined"):
                    bad.append(f"app.css:{ln} {sel[:48]} is sized by {size}, which nothing defines")
                elif how == "relative":
                    relative += 1
                else:
                    bad.append(f"app.css:{ln} {sel[:48]} is sized by {size}, which this cannot read")
                continue
            tok = re.fullmatch(r"var\(\s*(--[\w-]+).*\)", size)
            if px < _FLOOR_PX and tok and tok.group(1) in low:
                uses[tok.group(1)] += 1
            elif px < _FLOOR_PX:
                bad.append(f"app.css:{ln} {sel[:48]} is set at {px:g}px")
            elif px < 14 and not caps:
                if (ctx, sel) in _MIXED_13 and tok and tok.group(1) == _MIXED_13_TOKEN:
                    allowed.add((ctx, sel))
                    continue
                bad.append(f"app.css:{ln} {sel[:48]} is {px:g}px in mixed case, and 13px is "
                           "for capitals only")
    bad[:0] = [f"{k} is {px:g}px and sizes {uses[k]} rules" for k, px in sorted(low.items())]
    # An allowance nothing uses is a door left open: say so, so it is closed.
    bad += [f"_MIXED_13 allows {' '.join(c)} {s} 13px in mixed case, and app.css has no "
            f"such rule at {_MIXED_13_TOKEN}: take it out of the allowance"
            for c, s in sorted(_MIXED_13 - allowed)]
    rail_px = _css_px(f"var({_MIXED_13_TOKEN})", tokens)[0]
    if rail_px != _FLOOR_PX:
        bad.append(f"{_MIXED_13_TOKEN} is {rail_px}px, where the person chose the {_FLOOR_PX}px "
                   "floor for the phone card's rail")
    inline = svg = 0
    for name, src in _front_sources():
        for m in re.finditer(r"font-size\s*:\s*([^;\"'`}<>]+)", src):
            px, how = _css_px(m.group(1).strip(), tokens)
            inline += 1
            if px is not None and px < _FLOOR_PX:
                bad.append(f"{name}:{_line_of(src, m.start())} sets text at {px:g}px inline")
            elif how.startswith("undefined"):
                bad.append(f"{name}:{_line_of(src, m.start())} sizes text by "
                           f"{m.group(1).strip()}, which nothing defines")
        for m in re.finditer(r"\bstyle\s*=\s*([\"'])(.*?)\1", src, re.S):
            for k, v in _css_decls(m.group(2)):
                size = _css_font_size(k, v) if k == "font" else None
                px = _css_px(size, tokens)[0] if size else None
                if px is not None and px < _FLOOR_PX:
                    bad.append(f"{name}:{_line_of(src, m.start())} sets text at {px:g}px inline")
        for m in re.finditer(r"\bfont-size\s*=\s*[\"']\s*(\d*\.?\d+)\s*[\"']", src):
            svg += 1
            if float(m.group(1)) < _FLOOR_PX:
                bad.append(f"{name}:{_line_of(src, m.start())} sets an SVG's text at "
                           f"{float(m.group(1)):g} by its font-size attribute")
    assert not bad, (f"{len(bad)} sizes under the {_FLOOR_PX}px floor or unread: "
                     + "; ".join(bad[:16]) + (f" (+{len(bad) - 16} more)" if len(bad) > 16 else ""))
    return "ok", (f"{read} sizes in app.css ({relative} relative to their parent, which the "
                  f"rendered sweep measures), {inline} inline and {svg} SVG font-size attributes "
                  f"in the builders and scripts: none under {_FLOOR_PX}px, and {_FLOOR_PX}px "
                  f"only in capitals but for the phone card's rail ({len(allowed)} rules, "
                  f"{_MIXED_13_TOKEN})")


# The colours CSS knows by name, which are as much a colour written out as a hex.
_CSS_NAMED = set("""aliceblue antiquewhite aqua aquamarine azure beige bisque black
blanchedalmond blue blueviolet brown burlywood cadetblue chartreuse chocolate coral
cornflowerblue cornsilk crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey
darkkhaki darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen
darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue dimgray
dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite gold goldenrod
gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki lavender lavenderblush
lawngreen lemonchiffon lightblue lightcoral lightcyan lightgoldenrodyellow lightgray lightgreen
lightgrey lightpink lightsalmon lightseagreen lightskyblue lightslategray lightslategrey
lightsteelblue lightyellow lime limegreen linen magenta maroon mediumaquamarine mediumblue
mediumorchid mediumpurple mediumseagreen mediumslateblue mediumspringgreen mediumturquoise
mediumvioletred midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive
olivedrab orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip
peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue saddlebrown
salmon sandybrown seagreen seashell sienna silver skyblue slateblue slategray slategrey snow
springgreen steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow
yellowgreen""".split())


def _colour_literals(value):
    """The colours written in a value as themselves: a hex, a colour
    function (not color-mix of tokens), a named colour. What is inside a
    string, a url() or a var() name is not read."""
    v = re.sub(r"\"[^\"]*\"|'[^']*'", '""', value)
    v = re.sub(r"url\([^)]*\)", "url()", v)
    v = re.sub(r"var\(\s*--[\w-]+", "var(", v)
    found = re.findall(r"#[0-9A-Fa-f]{3,8}\b", v)
    found += re.findall(r"(?<![\w-])(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^()]*\)?", v,
                        re.I)
    found += [w for w in re.findall(r"(?<![\w#-])[A-Za-z]+(?![\w-])", v) if w.lower() in _CSS_NAMED]
    return found


_THEME_COLOR = re.compile(r'<meta name="theme-color" content="([^"]*)"'
                          r'(?: media="\(prefers-color-scheme: (light|dark)\)")?[^>]*>')


@check("frontend", "every colour is the palette's: none is written outside it in app.css, a "
                   "builder, app.js or find.js, and the theme-color a browser's bar takes is "
                   "the palette's page colour")
def _colours_from_palette():
    """Each colour has one definition, in the palette, which is what lets
    the dark theme, print and forced colours re-colour the site at all: a
    colour written into a rule is the same in every one of them.

    So a colour may be written as itself only as a token's definition, in
    the palette or in the print block's copy of it (_print_is_light holds
    that copy to the light values). An alpha mask's #000 is opacity, not a
    colour, and is not read; nor are transparent, currentColor and the
    system colours forced colours use. Outside app.css: every inline style
    and SVG paint attribute in the builders, app.js and find.js, and any
    string there that is a colour and nothing else.

    A <meta name="theme-color"> cannot take a var(), so it is the one place
    a colour is written out: it must be the palette's --paper for its theme,
    or the browser's bar is a different grey from the page under it."""
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = _source(css)
    pal = _css_palette(text)
    end = text.find("/* PALETTE END")
    end_line = _line_of(text, end) if end > 0 else 0
    bad, read = [], 0
    for ctx, sel, body, ln in _css_rules(text):
        printing = any(c.startswith("@media print") for c in ctx)
        for k, v in _css_decls(body):
            read += 1
            if k in ("mask-image", "-webkit-mask-image", "mask", "-webkit-mask"):
                continue
            lit = _colour_literals(v)
            if not lit or (k.startswith("--") and (ln < end_line or printing)):
                continue
            bad.append(f"app.css:{ln} {sel[:40]} writes {k}: {', '.join(lit)}"
                       + (" (a token defined outside the palette)" if k.startswith("--") else ""))
    themed = 0
    for name, src in _front_sources():
        for m in _THEME_COLOR.finditer(src):
            themed += 1
            scheme = m.group(2) or "light"
            want = pal[scheme].get("--paper", "")
            if m.group(1).lower() != want.lower():
                bad.append(f"{name}:{_line_of(src, m.start())} gives the browser's bar "
                           f"{m.group(1)} in the {scheme} theme, and the page is {want} (--paper)")
        rest = _THEME_COLOR.sub(lambda m: " " * len(m.group(0)), src)
        for m in re.finditer(r"\bstyle\s*=\s*([\"'])(.*?)\1", rest, re.S):
            lit = [x for k, v in _css_decls(m.group(2)) for x in _colour_literals(v)]
            if lit:
                bad.append(f"{name}:{_line_of(rest, m.start())} writes {', '.join(lit)} in an "
                           "inline style")
        for m in re.finditer(r"\b(fill|stroke|stop-color|flood-color|lighting-color)\s*=\s*"
                             r"([\"'])(.*?)\2", rest):
            lit = _colour_literals(m.group(3))
            if lit:
                bad.append(f"{name}:{_line_of(rest, m.start())} paints an SVG {m.group(1)} "
                           f"{', '.join(lit)}")
        for m in re.finditer(r"([\"'`])\s*(#[0-9A-Fa-f]{3,8}|(?:rgba?|hsla?)\([^)\"'`]*\))\s*\1",
                             rest):
            bad.append(f"{name}:{_line_of(rest, m.start())} holds the colour {m.group(2)} "
                       "as a string")
        # A colour a script sets as it runs: .style.<property>, setProperty
        # and cssText (the review of 8 October 2026 put "background:#fafafa"
        # into a cssText and this passed it).
        for m in re.finditer(r"\.style\.\w+\s*=\s*([^;\n]+)|setProperty\(([^)\n]+)\)|"
                             r"cssText\s*\+?=\s*([^;\n]+)", rest):
            val = next(g for g in m.groups() if g is not None)
            lit = _colour_literals(re.sub(r"[\"'`]", " ", val))
            if lit:
                bad.append(f"{name}:{_line_of(rest, m.start())} sets {', '.join(lit)} from a "
                           "script")
    assert themed >= 2, (f"only {themed} theme-color lines were found; bills.html and "
                         "build_pages.py each write two, and this reads them")
    assert not bad, (f"{len(bad)} colours outside the palette: " + "; ".join(bad[:12])
                     + (f" (+{len(bad) - 12} more)" if len(bad) > 12 else ""))
    return "ok", (f"{read} declarations of app.css and the inline styles, SVG paint and strings "
                  f"of {len(_front_sources())} builders and scripts: every colour a token, and "
                  f"the {themed} theme-colors the palette's page")


# A ground is what text sits on: an ink in a rule that gives none of its own
# is read on each of these. --on-X is the ink for X, and --X-ink the ink on X,
# so each is read on its X alone.
_GROUNDS = ("--paper", "--surface", "--wash")
# Tokens that draw no mark of their own: hairlines (no contrast asked of
# them, as the palette's notes say), grounds and tints.
_NOT_MARKS = re.compile(r"^--(?:rule|rule-2|paper|surface|wash|shadow|film|film-stub|"
                        r"film-stub-hot)$|-(?:bg|soft)$")
# A RULE WHOSE COLOUR DRAWS A MARK AND NO WORDS: the element it colours holds
# only an SVG stroked in currentColor, so its colour is a graphic's, held to
# 3:1 on the page and a card (WCAG 1.4.11) as a stroke is, and not to text's
# 4.5:1 on every ground. Named one by one, each with what draws it, and
# _token_pairs_measure fails if the rule or its drawing changes. How it got
# here's orange "~" on the line that sent a bill to interim study (app.js
# JMARK.s, the WAVE svg; the person's marks of 8 October 2026): --st-study
# is 4.53:1 on the page and 4.17:1 on --wash, where no list of decisions is
# drawn, and the wave is a stroke, not a letter. And since dev's rail endings
# (merged 9 October 2026) the interim study report's orange arrow, the same
# ink in the same rule (app.js JMARK.f, the ARROW svg). A rule naming several
# selectors draws a mark only where every one of them is named here.
_COLOR_DRAWS_A_MARK = {".jl .j-istudy .jg": ("JMARK", "s", "WAVE"),
                       ".jl .j-ifuture .jg": ("JMARK", "f", "ARROW"),
                       # a committee's meeting: the interim study report it
                       # recommended, in the same arrow (app.js actSaid)
                       ".mrec .mmark": ("ACTMARK", "rec", "ARROW")}


def _grounds_for(ink, default=_GROUNDS):
    m = re.fullmatch(r"--on-(.+)", ink) or re.fullmatch(r"--(.+)-ink", ink)
    return ["--" + m.group(1)] if m else list(default)


def _token_pairs(text, sources):
    """{(ink, ground, need): [where]}: every pair of tokens the site draws
    one on the other, read from app.css's rules and the builders' and
    scripts' inline styles and SVG, and the contrast each must have: 4.5 for
    text, 3 for large text and for a mark (a bar, an edge, a ring, a
    swatch). A ground mixed from two tokens in srgb is "a|N|b".

    A rule's text is read on the ground the same rule gives it, and
    otherwise on _grounds_for(ink). A mark -- a fill, a stroke, a border, an
    outline -- is read on the ground outside it, the page and a card
    (_grounds_for(token, ...)), never on its own rule's background: a
    button's edge is seen against what is around the button. A component's
    own variable (`.calcat.k-exec{--cat:var(--cal-exec)}`) stands for every
    token it is given."""
    pal = _css_palette(text)["light"]
    rules = [r for r in _css_rules(text)
             if not any(c.startswith("@media print") or "forced-colors" in c for c in r[0])]
    local = {}
    for _, _, body, _ in rules:
        for k, v in _css_decls(body):
            if k.startswith("--") and k not in pal:
                local.setdefault(k, set()).update(re.findall(r"var\(\s*(--[\w-]+)", v))

    def refs(v, seen=()):
        out = []
        for t in re.findall(r"var\(\s*(--[\w-]+)", v):
            if t in pal:
                out.append(t)
            elif t in local and t not in seen:
                out += refs(" ".join(f"var({x})" for x in sorted(local[t])), seen + (t,))
        return out

    def ground_of(v):
        v = " ".join(v.split())
        if re.fullmatch(r"var\(--[\w-]+\)", v):
            return (refs(v) or [None])[0]
        m = re.fullmatch(r"color-mix\(in srgb,\s*var\((--[\w-]+)\)\s+(\d+)%,\s*var\((--[\w-]+)\)\)", v)
        return f"{m.group(1)}|{m.group(2)}|{m.group(3)}" if m else None

    pairs = {}

    def add(ink, grounds, need, where):
        for g in grounds:
            pairs.setdefault((ink, g, need), []).append(where)

    for ctx, sel, body, ln in rules:
        ds = _css_decls(body)
        got = dict(ds)
        size = next((s for s in (_css_font_size(k, v) for k, v in ds) if s), None)
        px = _css_px(size, pal)[0] if size else None
        bold = got.get("font-weight", "") in ("700", "800", "900", "bold")
        large = px is not None and (px >= 24 or (px >= 18.66 and bold))
        ground = next((ground_of(got[k]) for k in ("background-color", "background") if k in got),
                      None)
        where = f"app.css:{ln} {sel[:40]}"
        drawn = all(s in _COLOR_DRAWS_A_MARK for s in _css_selectors(sel))
        for k in ("color", "-webkit-text-fill-color"):
            v = got.get(k, "").strip()
            if re.fullmatch(r"var\(--[\w-]+\)", v):
                for ink in refs(v):
                    if drawn:
                        add(ink, _grounds_for(ink, ("--paper", "--surface")), 3.0, where)
                    else:
                        add(ink, [ground] if ground else _grounds_for(ink),
                            3.0 if large else 4.5, where)
        for k, v in ds:
            if k in ("fill", "stroke") or (k.startswith(("border", "outline"))
                                           and k not in ("border-radius", "outline-offset")):
                for t in refs(v):
                    if not _NOT_MARKS.search(t):
                        add(t, _grounds_for(t, ("--paper", "--surface")),
                            4.5 if (k == "fill" and px is not None) else 3.0, where)
    for name, src in sources:
        # app.js draws its graphics inside a card: the bill's, a member's,
        # a committee's. A builder's may sit on the page.
        marks_on = ("--surface",) if name == "app.js" else ("--paper", "--surface")
        for m in re.finditer(r"\bstyle\s*=\s*([\"'])(.*?)\1", src, re.S):
            got = dict(_css_decls(m.group(2)))
            where = f"{name}:{_line_of(src, m.start())}"
            inks = refs(got.get("color", "")) if re.fullmatch(
                r"var\(--[\w-]+\)", got.get("color", "").strip()) else []
            for ink in inks:
                add(ink, _grounds_for(ink), 4.5, where)
            if not inks and re.fullmatch(r"var\(--[\w-]+\)", got.get("background", "").strip()):
                for t in refs(got["background"]):
                    if not _NOT_MARKS.search(t):
                        add(t, _grounds_for(t, marks_on), 3.0, where)
        for m in re.finditer(r"<(text|tspan|circle|line|polygon|polyline|path|rect|ellipse)\b"
                             r"([^>]*)>([^<]*)", src):
            where = f"{name}:{_line_of(src, m.start())}"
            words = m.group(1) in ("text", "tspan")
            # A text whose own words are only a separator (the thin-spaced
            # bar between a ring's two counts) reads nothing; a ${...} is
            # words the script puts there.
            if words and not re.search(r"[A-Za-z0-9$]",
                                       re.sub(r"\\u[0-9A-Fa-f]{4}", "", m.group(3))):
                continue
            for k, v in re.findall(r"\b(fill|stroke)=\"(var\(--[\w-]+\))\"", m.group(2)):
                for t in refs(v):
                    if _NOT_MARKS.search(t) and not words:
                        continue
                    big = re.search(r"\bfont-size=\"(\d+)\"", m.group(2))
                    text_ink = words and k == "fill"
                    need = (3.0 if big and int(big.group(1)) >= 24 else 4.5) if text_ink else 3.0
                    add(t, _grounds_for(t, marks_on), need, where)
    return pairs


@check("frontend", "every pair of tokens the site draws one on the other -- read from app.css's "
                   "rules and the builders' and scripts' inline styles and SVG, not listed by "
                   "hand -- measures up in both themes")
def _token_pairs_measure():
    """_palette measures the pairs somebody listed; this measures the pairs
    the code draws, so a new token pair cannot arrive unmeasured.

    Read from each rule of app.css: its text colour on its own ground where
    the rule gives one (a token, or two mixed in srgb), and otherwise on the
    grounds text sits on (_GROUNDS; --on-pine on pine, --film-stub-ink on
    the still); its fills, strokes and borders as marks on the page and a
    card, and so the colour of a rule that colours only a drawing
    (_COLOR_DRAWS_A_MARK, each held here to what it names). Hairlines,
    grounds and tints draw no mark and are not held (_NOT_MARKS). The same from the inline styles of the builders, app.js
    and find.js, and from their SVG: a text's fill is text, a shape's fill
    or stroke a mark, and a swatch's background a mark.

    WCAG 2.1: 4.5:1 for text, 3:1 for large text (24px, or 18.66px bold) and
    for the parts of a graphic needed to read it. Not read: a token whose
    name is built (`var(--ink${won?"":"-2"})`), a print or forced-colours
    rule (_print_is_light and the sweep), and a ground an ancestor gives."""
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = _source(css)
    pal = _css_palette(text)
    pairs = _token_pairs(text, _front_sources())
    assert len(pairs) >= 60, (f"only {len(pairs)} pairs were read from the rules; there were "
                              "more than 60 on 8 October 2026, so the reader has stopped reading")
    bad, low = [], None
    # A colour read as a mark's is a mark's only while the rule is there and
    # what it colours is still the drawing named (_COLOR_DRAWS_A_MARK).
    sels = {s for _, sel, _, _ in _css_rules(text) for s in _css_selectors(sel)}
    # app.js and components.js: the wave is the dated rail's, which
    # components.js draws in both languages since 10 October 2026, and app.js
    # names it again (const WAVE=RL_WAVE), which is followed to its drawing.
    js = "\n".join(_source(f)
                   for f in ("src/pages/app.js", "src/pages/components.js") if Path(f).exists())
    for sel, (table, key, svg) in _COLOR_DRAWS_A_MARK.items():
        alias = re.search(rf"\bconst {svg}\s*=\s*([A-Z_][A-Z0-9_]*)\s*;", js)
        drawing = re.search(rf"\bconst {alias.group(1) if alias else svg}\s*=\s*((?:'[^']*'\s*\+?\s*)+);", js)
        if sel not in sels:
            bad.append(f"{sel} is no longer a rule of app.css; take it off _COLOR_DRAWS_A_MARK")
        elif not re.search(rf"\bconst {table}\s*=\s*\{{[^}}]*\b{key}\s*:\s*{svg}\b", js):
            bad.append(f"app.js {table}.{key} is no longer {svg}, so {sel}'s colour may be "
                       "words again, and words need 4.5:1")
        elif not drawing or 'stroke="currentColor"' not in drawing.group(1) \
                or re.search(r"<text\b", drawing.group(1)):
            bad.append(f"app.js {svg} is no longer an SVG stroked in currentColor with no "
                       f"text, so {sel}'s colour is not a mark's")
    for (ink, ground, need), where in sorted(pairs.items()):
        for name in ("light", "dark"):
            a, b = _css_token_colour(ink, pal[name]), _css_token_colour(ground, pal[name])
            if a is None or b is None:
                bad.append(f"{ink} on {ground.replace('|', ' ')} cannot be measured in {name} "
                           f"({where[0]})")
                continue
            r = _css_ratio(a, b)
            if low is None or r / need < low[0] / low[1]:
                low = (r, need, ink, ground, name)
            if r < need:
                bad.append(f"{ink} on {ground.replace('|', ' ')} is {r:.2f}:1 in {name}, and "
                           f"needs {need:g} ({where[0]}" + (f" and {len(where) - 1} more"
                                                             if len(where) > 1 else "") + ")")
    assert not bad, f"{len(bad)} pairs: " + "; ".join(bad[:10])
    r, need, ink, ground, name = low
    return "ok", (f"{len(pairs)} pairs drawn, both themes; the closest is {ink} on "
                  f"{ground.replace('|', ' ')} in {name}, {r:.2f}:1 against {need:g}")


@check("frontend", "party and a vote's two sides are told apart by lightness as well as hue, in "
                   "both themes: Republican and Democratic 1.7:1, yes and no 2:1")
def _inks_apart():
    """A seat on the chart and a district on the map are too small for a
    letter, and a print, a photocopy or a reader who cannot tell red from
    blue sees only lightness. So the two party inks must differ in it, and
    so must the vote ring's yes and no: measured as a contrast ratio of the
    one ink against the other. The floors are this site's own, not WCAG's:
    1.7:1 for the parties, the gap the approved inks were chosen to clear,
    and 2:1 for yes and no, which the light pair has always met (2.19:1)."""
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    pal = _css_palette(_source(css))
    bad, said = [], []
    for name in ("light", "dark"):
        for a, b, need in (("--rep", "--dem", 1.7), ("--yes", "--no", 2.0)):
            ca, cb = _css_token_colour(a, pal[name]), _css_token_colour(b, pal[name])
            assert ca and cb, f"{a} or {b} is not a colour this can read in {name}"
            r = _css_ratio(ca, cb)
            said.append(f"{a[2:]}/{b[2:]} {r:.2f}:1 in {name}")
            if r < need:
                bad.append(f"{a} and {b} are {r:.2f}:1 apart in {name}, under {need:g}:1 "
                           f"({pal[name][a]} and {pal[name][b]})")
    assert not bad, "; ".join(bad)
    return "ok", "; ".join(said)


@check("frontend", "a focus ring is not cut off by the box around its control, a text box's edge is "
                   "the control edge, and small grey text carries no opacity")
def _rings_edges_opacity():
    """Three findings of the audit of 2 October 2026 that are one kind of
    thing: a rule that looks right in the stylesheet and measures wrong on the
    page.

    S5. The site's focus ring is 2px, 2px outside the control. A bill card's
    header fills its card and the card clips, Play fills .player and .player
    clips, a filter group's head fills the filter rail: no ring on a card's
    header in the list or on Play, one line of it elsewhere. Each is drawn
    inside its control now. Play's is in the still's own ink, because the
    still is near-black in both themes and the light theme's pine on it is
    2:1; that pair is measured here.

    S10. Six text boxes were edged in --rule-2, a card's hairline: 1.68:1
    against the page in light, 2.52:1 in dark, where WCAG 1.4.11 asks 3:1.
    Every rule that draws a text box's border uses --edge, which _palette
    already holds at 3:1 on the page and on a card in both themes.

    S11. Two pieces of small --ink-2 text had an opacity on top: the days of
    the months either side in the Calendar's grid (3.17:1 on the selected
    week's band) and the bracketed motion on a member's Votes tab (4.14:1).
    Neither rule carries an opacity now, and --ink-2 on the band -- pine mixed
    16% into the page -- is computed here for both themes and held to 4.5:1.
    """
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = _source(css)
    bare = re.sub(r"/\*.*?\*/", "", text, flags=re.S)

    def rules(selector):
        """Every declaration block whose selector list names `selector`."""
        return [body for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", bare)
                if selector in [s.strip() for s in sel.split(",")]]

    bad = []
    # S5
    # A card's control is its title's button since 10 October 2026 (C5),
    # where it was the whole head.
    for sel in (".ctitle:focus-visible", ".fhead:focus-visible", ".pstub:focus-visible"):
        got = rules(sel)
        off = [m for b in got for m in re.findall(r"outline-offset:\s*(-?\d+)px", b)]
        if not off or int(off[-1]) >= 0:
            bad.append(f"{sel} is not drawn inside its control (outline-offset "
                       f"{off[-1] + 'px' if off else 'unset'}): the box around it clips the ring")
    stub = rules(".pstub:focus-visible")
    if not any("var(--film-stub-ink)" in x for x in stub):
        bad.append("Play's ring is not in the still's own ink")
    film = dict(re.findall(r"--(film-stub(?:-ink)?):\s*(#[0-9A-Fa-f]{3,6})", text))
    if len(film) == 2:
        r = _css_ratio(_css_hex(film["film-stub-ink"]), _css_hex(film["film-stub"]))
        if r < 3:
            bad.append(f"Play's ring, --film-stub-ink on --film-stub, is {r:.2f}:1; a focus "
                       "indicator needs 3:1")
    else:
        bad.append("--film-stub or --film-stub-ink is no longer a hex colour this can measure")
    # S10
    boxes = [(sel, body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", bare)
             if re.search(r"(^|[\s,>])(?:#q|input(?:\[type=(?:search|text)\])?)\s*(,|$)",
                          sel.strip()) and re.search(r"\bborder:\s*1px solid", body)]
    if len(boxes) < 3:
        bad.append(f"only {len(boxes)} rules were found drawing a text box's border; the "
                   "bill search's, the pages' and the Calendar's are three")
    for sel, body in boxes:
        m = re.search(r"\bborder:\s*1px solid\s*([^;}]+)", body)
        if m.group(1).strip() != "var(--edge)":
            bad.append(f"{' '.join(sel.split())[:60]} edges a text box in "
                       f"{m.group(1).strip()}, not --edge")
    # S11
    for sel in (".cmout .cmn", ".votes .vq .dim"):
        if any(re.search(r"\bopacity:\s*(0?\.\d+)", b) for b in rules(sel)):
            bad.append(f"{sel} carries an opacity: small --ink-2 text under one "
                       "measured 3.17:1 and 4.14:1")
    band = re.search(r"\.cmrow\.cmsel td\{background:color-mix\(in srgb,var\(--pine\) "
                     r"(\d+)%,var\(--paper\)\)\}", bare)
    if not band:
        bad.append("the selected week's band is no longer pine mixed into the page; "
                   "measure --ink-2 on what it is now")
    else:
        k = int(band.group(1)) / 100
        light = text[text.index(":root{"):text.index("/* DARK:OS")]
        dark = text[text.index("/* DARK:CHOSEN"):text.index("/* PALETTE END")]
        for scheme, block in (("light", light), ("dark", dark)):
            tok = dict(re.findall(r"--(ink-2|pine|paper):\s*(#[0-9A-Fa-f]{3,6})", block))
            if len(tok) != 3:
                bad.append(f"--ink-2, --pine or --paper is not a hex colour in {scheme}")
                continue
            pine, paper = _css_hex(tok["pine"]), _css_hex(tok["paper"])
            mixed = tuple(p * k + q * (1 - k) for p, q in zip(pine, paper))
            r = _css_ratio(_css_hex(tok["ink-2"]), mixed)
            if r < 4.5:
                bad.append(f"--ink-2 on the selected week's band is {r:.2f}:1 in {scheme}; "
                           "a day's number is text and needs 4.5")
    assert not bad, "; ".join(bad[:5])
    return "ok", (f"three rings drawn inside their controls, Play's in the still's ink; "
                  f"{len(boxes)} text boxes edged in --edge; no opacity on the two small "
                  "greys, and --ink-2 on the week's band above 4.5:1 in both themes")


@check("frontend", "on paper the page is the light theme, whichever theme is on; the controls are not "
                   "printed, a recording's times are, and no white words lose their ground")
def _print_is_light():
    """The audit of 2 October 2026, M24. app.css had no print rules, and with
    the dark theme on a page printed in the dark theme's light ink on white
    paper: body text 2.2:1 against the sheet and a heading 1.2:1. The header,
    the bill search row, "Back to bill search", "Cite this page", the report
    box and Play all printed.

    One @media print block undoes the dark palette by writing the light
    palette's values again under the dark palette's two selectors. They are
    the light block's numbers written a second time, so this holds them to
    it: every colour the dark palette redefines is given back, at the light
    value, and nothing else.

    WHAT IS LEFT OFF IS THE CONTROL, NOT THE RECORD (the review of 2 October).
    The block hid .player whole, and that box holds each sitting's times:
    Play's own words, the line of moments under it, "approximate", the
    motions. On paper a bill's Hearings tab named no time at all. The frame
    of a playing recording is left off; Play prints as the line of text it
    is.

    AND WHITE WORDS KEEP THEIR GROUND. A browser prints no background unless
    asked, so type set in --on-pine, or in --surface on a filled stop of the
    passage rail, was white on white: a stop a bill had passed printed as an
    empty ring. Every rule in app.css that sets type in --on-pine, --surface
    or white is either under something the block leaves off, or under
    something it asks the ground for (print-color-adjust:exact). Read from
    the rules, so the next white label on a filled ground cannot be missed.
    """
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = _source(css)
    m = re.search(r"@media print\{\s*:root\[data-theme=\"dark\"\],"
                  r":root:not\(\[data-theme=\"light\"\]\)\{(.*?)\}(.*?)\n\}\n", text, re.S)
    assert m, ("app.css has no @media print block that undoes the dark palette under "
               "both of its selectors (the reader's choice, and the system's)")
    strip = lambda s: re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    head = text[:text.index("/* PALETTE END")]
    light = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;}]+)",
                            strip(head[head.index(":root{"):head.index("/* DARK:OS")])))
    dark = re.findall(r"(--[\w-]+)\s*:", strip(head[head.index("/* DARK:CHOSEN"):]))
    on_paper = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;}]+)", m.group(1)))
    missing = [n for n in dark if n not in on_paper]
    assert not missing, (
        "on paper the dark theme keeps its own " + ", ".join(missing[:5])
        + ": every colour the dark palette redefines must be given back")
    spare = sorted(set(on_paper) - set(dark))
    assert not spare, "the print block sets " + ", ".join(spare) + ", which the dark palette does not"
    drift = [f"{n} is {on_paper[n].strip()} on paper and {light[n].strip()} in the light palette"
             for n in dark if on_paper[n].strip().lower() != light.get(n, "").strip().lower()]
    assert not drift, "; ".join(drift[:4])
    assert "color-scheme:light" in m.group(1), "on paper the page still asks for a dark colour scheme"
    rest = strip(m.group(2))
    hidden = re.search(r"([^{}]+)\{display:none !important\}", rest)
    gone = {s.strip() for s in hidden.group(1).split(",")} if hidden else set()
    want = {"nav.top", ".searchrow", ".backto", ".pageacts", "details.report", ".player iframe"}
    assert want <= gone, (
        "printed, though it is a control and does nothing on paper: "
        + ", ".join(sorted(want - gone)))
    assert not ({".player", ".pbar", ".tolnote", ".jump", ".pstub"} & gone), (
        "a recording's box is left off the sheet, and it holds the times: where in the "
        "recording the bill was taken up, the vote, and whether a time is approximate")
    stub = re.search(r"(?:^|\})\s*\.pstub\{([^}]*)\}", rest)
    assert stub and "display:block" in stub.group(1) and "aspect-ratio:auto" in stub.group(1) \
        and "color:var(--ink)" in stub.group(1) and "background:none" in stub.group(1), (
            "on paper Play is not set as a line of text: it carries the time the recording "
            "is played from, in the still's light ink on a ground that does not print")
    exact = re.search(r"([^{}]+)\{\s*-webkit-print-color-adjust:exact;print-color-adjust:exact\}", rest)
    kept = {s.strip() for s in exact.group(1).split(",")} if exact else set()
    under = lambda sel, group: any(sel == g or sel.startswith(g + " ") or sel.startswith(g + ":")
                                   or sel.startswith(g + ".") for g in group)
    white, lost = 0, []
    for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", strip(text)):
        if not re.search(r"(?<![-\w])color:\s*(?:var\(--(?:on-pine|surface|paper)\)|#fff(?:fff)?\b|white\b)",
                         rule.group(2), re.I):
            continue
        for sel in rule.group(1).split(","):
            sel = sel.strip().replace(":where(body.pg) ", "")
            white += 1
            if not (under(sel, gone) or under(sel, kept)):
                lost.append(sel)
    assert white >= 10 and not lost, (
        "set in white, or in the colour of the page, on a ground that does not print, and "
        "neither left off the sheet nor given its ground on paper: " + ", ".join(sorted(set(lost))[:6]))
    # One is not type: the Calendar's ticked kind of meeting is a white tick,
    # drawn as a border, on the kind's own colour.
    assert re.search(r"\.cbx::after\{[^}]*border:solid var\(--surface\)", strip(text)) \
        and ".calcat input:checked + .cbx" in kept, (
            "a ticked kind of meeting prints as an empty box: its tick is the colour of the "
            "page on a ground that is not asked for on paper")
    return "ok", (f"{len(dark)} colours given back at their light values under both dark "
                  f"selectors; {len(gone)} controls left off the sheet, "
                  f"a recording's box not among them; {white} rules that set white type each "
                  f"left off or printed on their ground ({len(kept)} grounds asked for)")


# A stylesheet a page may take BESIDE app.css: the district map's, on the pages
# that draw it. Anything else a page links is a second stylesheet.
# And the live layer's, on /live and beside every committee page's live hook
# (live_hook.place; workers/live/PATCHES.md 11, 2 November 2026).
BESIDE_APP_CSS = ("/map.css", "/live.css")


@check("frontend", "every page links the one stylesheet, /app.css, and none links style.css")
def _one_stylesheet_linked():
    """One stylesheet for every page (23 October 2026).

    Until that day the five pages build_pages.py writes -- the home page,
    Officials, About, /search and 404 -- loaded style.css, a cut of app.css
    between SHARED and PAGES markers, and every record page loaded app.css
    whole. So where a rule sat in app.css decided which pages got it, and a
    component first drawn on a record page had to be moved into the shared
    region the day another page drew it. It was forgotten more than once:
    .mchip on the roster, the whole footer on four pages, the line that says
    why the header search lists a bill (.fwhy) on the home page and /search.
    Each was found after it shipped, and each fix was a cut and a paste.

    So every page links /app.css -- from the root, so the 404 page served at
    any depth finds it -- exactly once, and no page links style.css, which
    no build writes any more. Read off every page the fixture's builders
    wrote, and site/'s where one is built, so a builder that writes its own
    head is caught too. A page may take the district map's stylesheet beside
    it (BESIDE_APP_CSS); nothing else.
    """
    sites = _built_sites()
    if not sites:
        return "skip", "no built site here, and the builders are not here to build the fixture's"
    said = []
    for what, site in sites:
        assert not (site / "style.css").exists(), (
            f"{what} has a style.css. No page links it and no build writes it: an "
            "old build's, which publish would ship unused")
        bad, n = [], 0
        pages = sorted(site.rglob("*.html"))
        if what == "site/":
            # The real site holds 34,000 pages, and they are built in two ways:
            # every kind of page, a few of each, is the answer.
            by_dir = {}
            for p in pages:
                by_dir.setdefault(p.parent, []).append(p)
            pages = [p for ps in by_dir.values() for p in ps[:5]]
        for p in pages:
            t = p.read_text(encoding="utf-8", errors="replace")
            if "<head" not in t:
                continue
            n += 1
            links = re.findall(r'<link\b[^>]*\brel="stylesheet"[^>]*>', t)
            ours = [re.search(r'href="([^"]*)"', x).group(1) for x in links
                    if not re.search(r'href="https?:', x)]
            rel = p.relative_to(site).as_posix()
            if ours.count("/app.css") != 1:
                bad.append(f"{rel} links /app.css {ours.count('/app.css')} times")
            other = [h for h in ours if h != "/app.css" and h not in BESIDE_APP_CSS]
            if other:
                bad.append(f"{rel} links {', '.join(other)}")
        assert n, f"{what} has no pages with a head"
        assert not bad, (f"{len(bad)} pages of {what} do not link the one stylesheet "
                         f"alone: " + "; ".join(bad[:5]))
        said.append(f"{n:,} pages of {what}")
    return "ok", ("each links /app.css once and no other of ours but the map's and the live layer's: "
                  + ", ".join(said))

@check("frontend", "placeholder text has a colour from the palette")
def _placeholder_colour():
    """3.04:1 in dark, because nothing had ever set it.

    Neither stylesheet had a ::placeholder rule, so every search box on the
    site rendered its instruction in the browser's default #757575 -- 4.61:1
    on white and 3.04:1 on the dark card, against a 4.5 threshold. It is
    text, it is the only instruction those boxes carry, and it was below the
    line on every page in dark mode for as long as dark mode existed.

    A colour a browser picks is not covered by the palette check, which reads
    the tokens this file declares; the only way to catch it is to name the
    rule that has to exist. Every page loads app.css, so one rule reaches
    every box.
    """
    want = "::placeholder{color:var(--ink-2)"
    src = _source("src/pages/app.css")
    assert want in src, (
        "app.css has no ::placeholder colour. The browser's default is "
        "#757575, which is 3.04:1 on --surface in dark -- below the 4.5 a "
        "palette pair would have to clear.")
    built = Path("site/app.css")
    if not built.exists():
        return "ok", "app.css only; site/app.css not built"
    assert want in built.read_text(encoding="utf-8"), (
        "site/app.css has no ::placeholder colour: it was lost on the way "
        "into the site (build_pages.strip_css).")
    return "ok", "--ink-2: 7.74:1 light, 6.32:1 dark"


@check("frontend", "nowrap is never applied to a block by element name")
def _nowrap():
    """The shape of the defect that made every legislator page scroll sideways.

    `.votes td.o .pass,.votes td.o .fail,.votes td.o i{white-space:nowrap}`
    was written to keep the outcome words on one line -- "Adopted", "292-25".
    The third selector names an ELEMENT, so it also caught `.votes td.o .thr`,
    which is an <i> in the same cell, is `display:block`, and holds a
    sentence: "A majority voted yes, but this needed 214 (two thirds of
    members voting)". At 169px of column that wanted 519px, and with nowrap it
    pushed the document 435px wide at 768 and 210px at 1440 -- on every
    legislator page carrying a two-thirds vote, which is most of them. Below
    720px the table is already reflowed into blocks, which is why the
    accessibility pass of 11 September, done at phone widths, found nothing.

    WHAT THIS CANNOT DO, said plainly: it does not measure overflow. That
    needs layout, and preflight has no layout -- dom_stub.js is a shim whose
    querySelectorAll returns []. The width sweep is a browser job and lives in
    DESIGN.md. What is checkable here is the mistake itself, and it is a
    narrow one worth naming: a nowrap rule whose last compound is a bare
    element name reaches everything of that element type in that context,
    including something a later rule gave a class and made a block. A block
    that cannot wrap and has no scroller of its own overflows as soon as its
    text is long, and "is its text long" is not a question CSS can be asked.

    So: keep nowrap on classes. `.votes td.o .thr` needed the exception and
    now carries `white-space:normal` explicitly, which is also allowed.
    """
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    text = re.sub(r"/\*.*?\*/", "", _source(css), flags=re.S)

    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", text)
    nowrap, blocks, released = [], [], set()
    for sel, body in rules:
        sel = " ".join(sel.split())
        if not sel or sel.startswith("@"):
            continue
        decls = body.replace(" ", "")
        # The visually-hidden idiom carries nowrap and is exempt: it is 1px
        # square and clipped, so it has no column to overflow. This is the
        # `.vfull thead` rule that hides a table's header from sight while
        # keeping it for a screen reader.
        hidden = "position:absolute" in decls and ("clip:" in decls
                                                   or "width:1px" in decls)
        for one in sel.split(","):
            one = one.strip()
            if not one:
                continue
            if "white-space:nowrap" in decls and not hidden:
                nowrap.append(one)
            if "white-space:normal" in decls:
                released.add(one)
            if "display:block" in decls:
                blocks.append(one)

    # The last compound of a selector, and everything before it.
    def split_last(s):
        parts = s.replace(" > ", " ").split()
        return " ".join(parts[:-1]), parts[-1] if parts else ""

    bad = []
    for nsel in nowrap:
        prefix, last = split_last(nsel)
        # Only a BARE element name is the trap: .thr or [data-x] name one
        # thing, `i` names every <i> that happens to be there.
        if not re.fullmatch(r"[a-z]+", last):
            continue
        for bsel in blocks:
            if bsel in released:
                continue
            bprefix, blast = split_last(bsel)
            if bprefix != prefix or blast == last:
                continue
            # And the block must be named by a CLASS. Two bare element names
            # in the same place are two different elements -- `thead` does not
            # match a `tbody` -- and flagging that pair was this check's first
            # and only false positive. A class can sit on an element of the
            # nowrap rule's type, which is exactly how `.thr` was an <i>.
            if re.fullmatch(r"[a-z]+", blast):
                continue
            bad.append(
                f"{{{nsel}}} sets white-space:nowrap by element name, and "
                f"{{{bsel}}} in the same place is display:block. A block that "
                "cannot wrap overflows its column as soon as its text is a "
                "sentence -- name the class, or give the block "
                "white-space:normal.")
    assert not bad, "; ".join(bad[:3])
    return "ok", (f"{len(nowrap)} nowrap selectors, "
                  f"{sum(1 for s in nowrap if re.fullmatch(r'[a-z]+', split_last(s)[1]))}"
                  " of them by element name, none reaching a block")


# The chips app.css lets stay on one line on a phone, each for its reason. A
# chip whose words are a phrase has no business here.
CHIP_NOWRAP_OK = {
    ".l-numtab .cstat": "Ratified or Not Ratified, in a table in .l-tablewrap, a box that "
                        "scrolls sideways for it",
    ".l-speak .calkind": "a meeting's kind, in the testifying guide's table in .l-tablewrap, "
                         "a box that scrolls sideways for it",
}


@check("frontend", "every tab strip that scrolls says so with the one deep edge: 40px covers of its "
       "own ground over 32px of --scrolledge, a token deeper in dark than the faint --shadow was")
def _scroll_edges():
    """The R2 polish batch, 30 October 2026. A tab strip that scrolls on a
    phone shows more is there only by its edge, and on three strips the edge
    was 16px of --shadow: at 390px the Officials strip hid three of its six
    tabs and an opened bill card hid Reports, Sponsors and Documents, with
    5 grey levels between the edge and the ground (measured on the preview).
    The record strip had already been given a deeper one ("nobody saw it",
    14 October), but in --lift, which all but vanishes in dark mode.

    So one token, --scrolledge: --lift's .22 in light and on paper, and in
    dark at least the .5 --shadow was. Every scrolling strip -- the Officials
    and town strip at every width, a list card's on a tablet and a phone, and
    the record strip -- has two covers of its own ground that travel with
    its tabs (local), at least as wide as the two shadows of --scrolledge
    fixed under them, and no --shadow."""
    css = _source("src/pages/app.css")
    rules = _css_rules(css)
    bad = []
    tok = {}
    head = css[:css.index("/* PALETTE END")]
    for name, at in (("light", ":root{"), ("dark", "/* DARK:OS"), ("chosen", "/* DARK:CHOSEN")):
        m = re.search(r"--scrolledge:rgba\(0,0,0,([\d.]+)\)", head[head.index(at):])
        tok[name] = float(m.group(1)) if m else None
    m = re.search(r"@media print\{\s*:root\[data-theme=\"dark\"\],:root:not\(\[data-theme=\"light\"\]\)\{([^}]*)\}", css)
    p = re.search(r"--scrolledge:rgba\(0,0,0,([\d.]+)\)", m.group(1)) if m else None
    tok["print"] = float(p.group(1)) if p else None
    if tok["light"] != .22 or tok["print"] != .22:
        bad.append(f"--scrolledge is {tok['light']} in light and {tok['print']} on paper, where --lift's .22 was chosen")
    if not (tok["dark"] and tok["dark"] >= .5 and tok["dark"] == tok["chosen"]):
        bad.append(f"--scrolledge in dark is {tok['dark']} (system) and {tok['chosen']} (chosen): "
                   "at least the .5 the faint --shadow was, and the same in both")
    strips = ((".twntabs", "", "--paper"),
              (".tabs", "max-width:45em", "--surface"),
              (".card .tabs", "min-width:45.0625em) and (max-width:68.75em", "--surface"),
              (".card.focus.rec > .cbody > .tabs", "max-width:68.75em", "--paper"))
    for sel, media, ground in strips:
        got = [b for at, sl, b, _l in rules
               if (any(media in a.replace(": ", ":") for a in at) if media else not at)
               and sel in [x.strip() for x in sl.split(",")]
               and "background" in dict(_css_decls(b))]
        if not got:
            bad.append(f"{sel} at ({media}) has no scroll edge")
            continue
        bg = dict(_css_decls(got[-1]))["background"]
        layers = re.split(r",\s*(?=linear-gradient)", bg)
        covers = [x for x in layers if re.search(r"\blocal\b", x)]
        edges = [x for x in layers if "var(--scrolledge)" in x]
        cw = [int(n) for x in covers for n in re.findall(r"/(\d+)px 100%", x)]
        ew = [int(n) for x in edges for n in re.findall(r"/(\d+)px 100%", x)]
        if "var(--shadow)" in bg or len(covers) != 2 or len(edges) != 2 or not all(f"var({ground})" in x for x in covers):
            bad.append(f"{sel} at ({media}): {len(covers)} covers of {ground} and {len(edges)} edges of "
                       "--scrolledge, where it wants two of each and no --shadow")
        elif len(cw) != 2 or len(ew) != 2 or min(cw) < max(ew) or min(ew) < 32:
            bad.append(f"{sel} at ({media}): covers {cw}px over edges {ew}px; the covers must be at least "
                       "as wide as the edges, and the edges 32px")
    assert not bad, "; ".join(bad[:6])
    return "ok", (f"--scrolledge .22 in light and on paper, {tok['dark']:g} in dark; {len(strips)} strips "
                  "with 40px covers over 32px edges of it")


@check("frontend", "a chip is held on one line only where its words are short or its box scrolls: a vote's result wraps")
def _chip_nowrap():
    """A chip that says a vote's result in the bill page's words is a phrase,
    and a phrase must be able to wrap.

    `.votes td.o .chip,.votes td.o i{white-space:nowrap}` held the outcome on
    a member's Votes tab to one line while it was "Adopted" or "Failed". On 23
    October 2026 the tab took the bill page's words -- "Motion Passed:
    Overridden in the House" -- and the rule, more specific than the phone's
    `.chip{white-space:normal;max-width:100%}`, kept them on one line: the
    words ran out of the chip and off the card, and Rep. Wade's Votes tab was
    469px wide on a 390px phone, 1041px at 1024 and 847px at 768 (the webinar
    pass, measured on the dry run in Chrome). Nothing failed, because nothing
    here measures layout.

    What is checkable is the rule itself: no rule holds a chip -- `.chip` or a
    hook a chip is placed by (`.cstat`, `.rcres`, `.calkind`, `.fkind`,
    `.sgn`) -- to one line, but the base `.chip` that the phone's rule
    releases, and CHIP_NOWRAP_OK, each with its reason. And the result on a
    member's Votes tab is released by name.
    """
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not there"
    rules = _css_rules(_source(css))
    hooks = ("chip", "cstat", "rcres", "calkind", "fkind", "sgn")
    held, released, phone = [], set(), False
    for at, sel, body, line in rules:
        decls = dict(_css_decls(body))
        ws = decls.get("white-space", "")
        for one in (" ".join(s.split()) for s in sel.split(",")):
            last = one.replace(" > ", " ").split()[-1] if one else ""
            classes = set(re.findall(r"\.([\w-]+)", last))
            if not classes & set(hooks):
                continue
            if ws == "nowrap":
                held.append((one, line, at))
            elif ws == "normal":
                released.add(one)
                if one == ".chip" and any("max-width:45em" in a.replace(" ", "") for a in at) \
                        and decls.get("max-width") == "100%":
                    phone = True
    assert phone, ("the phone's rule that lets a chip wrap -- @media (max-width:45em)"
                   "{.chip{white-space:normal;max-width:100%}} -- is gone")
    bad = [f"{{{s}}} (line {n}) holds a chip to one line" for s, n, at in held
           if not (s == ".chip" and not at) and s not in CHIP_NOWRAP_OK]
    assert not bad, ("; ".join(bad[:3]) + ". A chip's words can be a phrase -- a vote's "
                     "result is \"Motion Passed: Overridden in the House\" -- and held to one "
                     "line they run out of the chip and push the page sideways on a phone. "
                     "Let it wrap, or name it in CHIP_NOWRAP_OK with why its words are short "
                     "or its box scrolls.")
    stale = sorted(set(CHIP_NOWRAP_OK) - {s for s, _, _ in held})
    assert not stale, f"CHIP_NOWRAP_OK names {stale}, which no rule holds to one line any more"
    assert ".votes td.o .chip" in released, (
        "the result on a member's Votes tab is not released to wrap by name: "
        ".votes td.o .chip{white-space:normal;max-width:100%}")
    return "ok", (f"{len(held)} rules hold a chip to one line: the base .chip, which a phone "
                  f"releases, and {len(CHIP_NOWRAP_OK)} whose words are short or whose box "
                  "scrolls; a vote's result wraps")


@check("frontend", "every control a filter strip draws has the strip's frame and 16px words, and 44px on a phone")
def _bfilt_controls():
    """A control added to a filter strip is styled with the strip's selects.

    The Find box on a member's Votes tab (e4a2c98, 23 October 2026) was the
    first control in a `.bfilt` that was not a select, and app.css styled
    only `.bfilt select`. It was drawn as the browser's own box: 13px words,
    21px tall, a 2px grey edge, lower than the two selects beside it and
    white in the dark theme -- and an iPhone zooms the page when a field
    under 16px is tapped, which is what a webinar's audience, on their
    phones, would have done with it (the webinar pass of 23 October 2026).

    So: every <select>, <input> and <textarea> inside a `class="bfilt..."`
    in app.js is named, by element and type, in the rule that gives the
    strip's selects their frame and 16px words, and in the phone block's
    44px rule.
    """
    css_p, js_p = Path("src/pages/app.css"), Path("src/pages/app.js")
    if not (css_p.exists() and js_p.exists()):
        return "skip", "app.css or app.js is not there"
    js = _source(js_p)
    want = set()
    for m in re.finditer(r'class="bfilt[^"]*"', js):
        span = js[m.start():js.index("</div>", m.start())]
        for tag, attrs in re.findall(r"<(select|textarea|input)\b([^>]*)>", span):
            t = re.search(r'type="(\w+)"', attrs)
            want.add(f".bfilt {tag}[type={t.group(1)}]" if tag == "input" and t else f".bfilt {tag}")
    assert want, "app.js draws no filter strip (class=\"bfilt\") with a control in it"
    rules = _css_rules(_source(css_p))
    framed, tall = set(), set()
    for at, sel, body, line in rules:
        decls = dict(_css_decls(body))
        sels = {" ".join(s.split()) for s in sel.split(",")}
        if not at and decls.get("font-size") == "var(--t-ui)" and decls.get("border", "").startswith("1px solid"):
            framed |= sels
        if any("max-width:45em" in a.replace(" ", "") for a in at) and decls.get("min-height") == "44px":
            tall |= sels
    bad = []
    for w in sorted(want):
        if w not in framed:
            bad.append(f"{w} is not in the rule that gives the strip's controls their frame "
                       "and 16px words (with .bfilt select): the browser draws its own box, at "
                       "13px, which an iPhone zooms the page to when it is tapped")
        if w not in tall:
            bad.append(f"{w} is not held to 44px on a phone with .bfilt select")
    assert not bad, "; ".join(bad[:3])
    return "ok", f"{len(want)} kinds of control in the filter strips, each framed, 16px and 44px on a phone: " \
        + ", ".join(sorted(want))


@check("frontend", "a table in a box that scrolls for it is laid out as a table, so the box, the Tab stop, is what scrolls")
def _scrollstop_tables():
    """One scroller, not one inside another.

    On a phone app.css makes every record page's table a block that scrolls
    inside itself (`:where(body:not(.pg)) table{display:block;overflow-x:
    auto}`). The Data page's coverage table already sits in a box that
    scrolls for it, `.covwrap`, marked data-scrollstop so that app.js makes
    it a Tab stop while its content is wider than it is. The phone rule
    reached the table too: it took 480px of its 606 and scrolled the rest
    inside the box's own scroll, and that inner scroller, holding nothing a
    keyboard can reach, was no Tab stop -- axe's scrollable-region-focusable,
    serious, on the live site and the dry run alike (the webinar pass of 23
    October 2026).

    So: every table that opens a box marked data-scrollstop, in a builder or
    in app.js, has a rule in app.css that lays it out as a table again.
    """
    css_p = Path("src/pages/app.css")
    if not css_p.exists():
        return "skip", "app.css is not there"
    sources = sorted(Path("src/pages").glob("*.py")) + [Path("src/pages/app.js")]
    tables = {}
    for p in sources:
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"<div\b[^>]*\bdata-scrollstop=[^>]*>\s*<table\b[^>]*\bclass=\"([^\"]+)\"", text):
            for c in m.group(1).split():
                tables.setdefault(c, p.name)
    assert tables, "no table opens a box marked data-scrollstop: the Data page's coverage table did"
    rules = _css_rules(_source(css_p))
    as_table = set()
    for at, sel, body, line in rules:
        if dict(_css_decls(body)).get("display") == "table":
            as_table |= {" ".join(s.split()) for s in sel.split(",")}
    bad = [f"table.{c} ({where}) is in a box that scrolls for it and has no rule laying it out "
           "as a table: on a phone it scrolls inside the box's scroll, where no Tab stop reaches it"
           for c, where in sorted(tables.items())
           if not ({f"table.{c}", f".{c}"} & as_table)]
    assert not bad, "; ".join(bad[:3])
    return "ok", (f"{len(tables)} table(s) in a box that scrolls for it, each laid out as a "
                  "table: " + ", ".join(f"table.{c}" for c in sorted(tables)))


@check("frontend", "a table cut off on a phone shows its edge, a byline's dot wraps with what it leads "
                   "to, a cut vote title ends in an ellipsis, and Report a problem fits half a phone's row")
def _small_visual_s9():
    """The audit of 25 October 2026 (S9), approved by the owner, each a rule
    a browser reads right and nothing here measured:

    - Wide tables on /learn/by-the-numbers (723px in a 364px box) and /data
      (606px) were cut at the box's edge on a phone with nothing to say there
      was more. Both boxes have the officials strip's edge (.oftabs): covers
      that scroll with the table over shadows that stay with the box, in the
      box's own ground. And the box is what scrolls, so its table is laid out
      as a table, or the phone's rule makes the table scroll inside the box
      and the box's edge never moves.
    - A byline's separator dot was an item of its own in a wrapping row, and
      142 of 267 on /bills at 390px ended a line. It is drawn at the head of
      the item after it, and the dot before the topic, bare text with no box
      to draw on, gives its own box up so its dot joins the topic's text.
    - A vote title on a member's Votes tab, cut at two lines, stopped
      mid-phrase as though that were all of it. Two lines are drawn whole
      and end in an ellipsis (the cohesion audit of 30 October 2026, B-7: a
      fade over a third line had sat on the motion's line below it).
    - "Report a problem" broke over two lines in half a phone's row of
      actions: there it says "Report".
    """
    css_p, js_p = Path("src/pages/app.css"), Path("src/pages/app.js")
    if not (css_p.exists() and js_p.exists()):
        return "skip", "app.css or app.js is not there"
    rules = _css_rules(_source(css_p))

    def decl(selector, phone=False):
        """The declarations of every rule naming `selector`, later ones last."""
        got = {}
        for at, sel, body, _ in rules:
            if selector in {" ".join(s.split()) for s in sel.split(",")} and \
                    bool(phone) == any("max-width:45em" in a.replace(" ", "") for a in at):
                got.update(_css_decls(body))
        return got
    bad = []
    # The edge.
    for box in (".l-tablewrap", ".covwrap"):
        bg = decl(box).get("background", "")
        if not (bg.count(" local") == 2 and bg.count(" scroll") == 2 and "var(--shadow)" in bg
                and bg.count("var(--surface)") == 3):
            bad.append(f"{box} has no edge that says its table goes on, in its own ground: {bg[:120]!r}")
    if decl(":where(.l-tablewrap) > table").get("display") != "table":
        bad.append("a table in .l-tablewrap is not laid out as a table, so on a phone it scrolls "
                   "inside the box and the box's edge never moves")
    # The dot.
    if decl(".cmeta > .cdot").get("display") != "none" or \
            decl(".cmeta > .cdot:last-child").get("display") != "contents":
        bad.append("a byline's dot is still an item of its own, which a line can end on")
    dot = decl(".cmeta > .cdot + *::before")
    if not dot.get("content", "").startswith('"\\00b7') or dot.get("display") != "inline-block":
        bad.append(f"the item after a byline's dot does not draw it at its head: {dot}")
    # The cut: two lines and an ellipsis (the cohesion audit of 30 October
    # 2026, B-7), where the fade's third line had sat on the motion's line.
    vt = decl(".votes .vt")
    want = {"display": "-webkit-box", "-webkit-box-orient": "vertical", "-webkit-line-clamp": "2",
            "line-clamp": "2", "max-height": "2.7em", "overflow": "hidden"}
    if any(vt.get(k) != v for k, v in want.items()) or "mask-image" in vt or "-webkit-mask-image" in vt:
        bad.append("a vote title is not cut at two whole lines with an ellipsis, or a fade "
                   f"is still drawn over a third: {vt}")
    # Report.
    if '<summary>${icon("report")}<span>Report<span class="rpw"> a problem</span></span></summary>' \
            not in _source(js_p) or \
            decl(".racts .report .rpw", phone=True).get("display") != "none":
        bad.append("Report a problem is not \"Report\" in half a phone's row of actions")
    assert not bad, "; ".join(bad[:5])
    return "ok", ("two scrolling boxes with their edge, tables laid out as tables; a byline's dot "
                  "with what it leads to; a cut title two lines and an ellipsis; Report on a phone")


@check("frontend", "the voters' card on a CACR draws its counts whole and its mark at two thirds")
def _ballot_card_drawn():
    """The Votes tab of a CACR the voters were sent ends with their vote (5
    October 2026): "The voters", the election's day, Yes and No in full with
    their separators, each one's share, the ring with its mark at two thirds
    of the votes cast, a line saying this was the statewide public vote and
    what an amendment needs, and the outcome in words.

    Drawn in node from records shaped as build_site_v2.ballot_card writes
    them. Fails on a count drawn without its separators or split across
    lines (app.css keeps .ballot's counts whole), on the counts put in the
    ring's 92px hole, on the mark at a majority, on an outcome that is not
    the record's, on the docket's own differing tally going unsaid, on an
    election to come drawn as a result, and on the voters' vote left out of
    the tab's count or put ahead of the chambers'.

    And since the review of 5 October 2026: on the docket's figure said
    without which side differs and whose the card's are, on a second date
    style inside the card, on an election past with no count still "is on",
    and on the Documents tab crediting the status page with the voters'
    answer it does not give."""
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    assert re.search(r"\.ballot \.lrow \.c\{[^}]*white-space:nowrap", css), (
        "app.css does not keep a voters' count on one line (.ballot .lrow .c)")
    # As build_site_v2.ballot_card writes them since 7 October 2026: whose
    # the count is (by, whose) and where it is printed (cite), from the row.
    sos = {"by": "Secretary of State", "whose": "the Secretary of State's", "read": "2026-10-07"}
    bp = {"source": _BALLOTPEDIA[0], "cite": _BALLOTPEDIA[1], "by": "Ballotpedia",
          "whose": "Ballotpedia's", "read": "2026-10-05"}
    recs = {
        "lost": {"date": "2024-11-05", "label": "Question No. 1",
                 "yes": 452307, "no": 237221, "ratified": False, "source": _SOS_2024[0],
                 "cite": _SOS_2024[1], **sos},
        "won": {"date": "2006-11-07", "label": "Question No. 1", "yes": 316005, "no": 52893,
                "ratified": True, "source": "https://electiondatabase.nhpr.org/document/685?page=184",
                "cite": "Manual for the General Court 2007, p. 335 (NHPR's scan)", **sos},
        "docket": {"date": "1998-11-03", "label": "Question 1", "yes": 119104, "no": 169439,
                   "ratified": False, "docket": [119104, 159439], "source": _MANUAL_1999[0],
                   "cite": _MANUAL_1999[1], **sos},
        "pending": {"date": "2026-11-03", "label": "Eliminate Office of Register of Probate Amendment",
                    "pending": True, **bp},
        "over": {"date": "2026-11-03", "label": "Eliminate Office of Register of Probate Amendment",
                 "pending": True, "over": True, **bp},
    }
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "recs.json").write_text(json.dumps(recs), encoding="utf-8")
        (root / "go.js").write_text("""
require("./stub.js");
const fs = require("fs");
globalThis.fetch = async u => ({ok: true, status: 200, json: async () => ({H: [], S: []}),
  text: async () => "{}"});
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({renderVotes, renderDetail, votesDrawn, renderDocuments})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const recs = JSON.parse(fs.readFileSync("./recs.json", "utf8"));
const rc = {question: "Ought to Pass", date: "2023-03-30", body: "S", vote_kind: "VV", passed: true};
const out = {};
for (const [k, v] of Object.entries(recs)) {
  out[k] = s.renderVotes({id: "CACR6"}, {rollcalls: [rc], ballot: v});
  out[k + "N"] = s.votesDrawn({rollcalls: [rc], ballot: v});
}
out.tabs = s.renderDetail({id: "CACR6", n: "CACR 6", term: "2023-2024"},
                          {rollcalls: [rc], ballot: recs.lost});
out.none = s.renderVotes({id: "HB1"}, {rollcalls: [rc]});
const page = [{kind: "status", label: "Bill status page", url: "https://gc.nh.gov/x"}];
for (const [k, src, b] of [["docsBallot", "ballot_results.json", recs.lost],
                           ["docsDocket", "General Court docket", recs.docket],
                           ["docsPending", "General Court bill status page", recs.pending]])
  out[k] = s.renderDocuments({id: "CACR6"}, {documents: page, status_source: src, ballot: b});
process.stdout.write("\\n@@" + JSON.stringify(out));
""", encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not draw the voters' card under node: "
            + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    def voters(html):
        i = html.find('<section class="rc ballot"')
        return html[i:] if i >= 0 else ""

    def flat(html):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()

    lost, won = voters(got["lost"]), voters(got["won"])
    assert lost and won, "a CACR's Votes tab draws no card for the voters"
    assert got["lost"].find('<section class="rc"') < got["lost"].find('class="rc ballot"'), (
        "the voters' card is drawn ahead of the chambers' votes")
    assert "class=\"rc ballot\"" not in got["none"], "a bill with no ballot row drew a voters' card"
    for html, word, cls, pct, other, how in (
            (lost, "Not ratified", "fail", "65.6%", "34.4%", "short of"),
            (won, "Ratified", "pass", "85.7%", "14.3%", "more than")):
        text = flat(html)
        assert '<h2 class="rcq">The voters</h2>' in html, f"the voters' card is headed {text[:60]!a}"
        # The one chip, its words in Title Case (the component plan's step 3).
        assert f'<span class="chip rcres {cls}">{word.title()}</span>' in html, (
            f"the voters' card does not say {word.title()!r}: {text[:120]!a}")
        assert f"{word}: {pct} voted yes, {how} the two thirds it needed." in text, (
            f"the outcome is not said in words: {text[:200]!a}")
        assert "statewide public vote" in text and "two thirds of the votes cast" in text, (
            f"the voters' card does not say what the vote was or what it needed: {text[:300]!a}")
        assert "State general election" in text and "Source: Secretary of State, " in text, (
            f"the voters' card names no election or no source: {text[:300]!a}")
        # The share in the ring; the counts in the legend, never in the ring.
        ring = html[html.find("<svg"):html.find("</svg>")]
        assert f">{pct}</text>" in ring and not re.search(r">[\d,]{6,}", ring), (
            f"the ring's middle holds {flat(ring)!a}, not the yes share alone")
        legend = html[html.find('<div class="legend">'):]
        assert '<span class="c">' in legend and f"· {pct}</span>" in legend \
            and f"· {other}</span>" in legend, f"the legend reads {flat(legend)[:120]!a}"
        # The mark: two thirds of the way round from the gap, not half.
        m = re.search(r'<polygon points="([\d.]+),([\d.]+)', ring)
        assert m, "the voters' ring has no mark"
        a = (180 + 16 + 328 * 2 / 3) * math.pi / 180
        tip = (86 + 74 * math.sin(a), 86 - 74 * math.cos(a))
        assert abs(float(m.group(1)) - tip[0]) < 0.2 and abs(float(m.group(2)) - tip[1]) < 0.2, (
            f"the voters' mark is at {m.group(1)},{m.group(2)}, not two thirds round "
            f"({tip[0]:.1f},{tip[1]:.1f})")
        assert "Two thirds of the votes cast needed" in ring, "the mark does not say what it marks"
    for count in ("452,307", "237,221"):
        assert f">{count} · " in lost, f"{count} is not drawn whole in the legend"
    assert "316,005" in won and "52,893" in won, "the 2006 counts are not drawn in full"
    assert "Question No. 1" in lost, (
        "the voters' card does not say how the source lists the measure")
    # The docket's differing figure: which side, both numbers, and whose the
    # card's are -- not a second pair for the reader to compare digit by digit.
    dock = flat(voters(got["docket"]))
    assert "docket records 159,439 votes against, not 169,439. The counts above are " \
           "the Secretary of State's" in dock.replace("&#39;", "'"), (
        f"the docket's own differing tally goes unsaid, or unplaced: {dock[:400]!a}")
    assert "docket records" not in flat(lost), "a tally the docket does not print is said to be its"
    # One date style in the card: the head's, every vote card's.
    pend = voters(got["pending"])
    assert "The vote is on Nov 3, 2026." in flat(pend) and "<svg" not in pend \
        and "rcres" not in pend and "atified" not in pend and "This is the statewide" in flat(pend), (
            f"an election still to come is drawn as {flat(pend)[:200]!a}")
    assert "read Oct 7, 2026" in flat(lost) and "October" not in flat(lost), (
        f"the voters' card mixes its date styles: {flat(lost)[-200:]!a}")
    # The day after, with no count in the file: past tense, still no outcome.
    over = voters(got["over"])
    assert "The vote was on Nov 3, 2026; its count is not recorded here yet." in flat(over) \
        and "This was the statewide" in flat(over) and "<svg" not in over \
        and "atified" not in over and got["overN"] == 1, (
            f"an election past with no count in the file is drawn as {flat(over)[:200]!a}")
    assert (got["lostN"], got["wonN"], got["pendingN"]) == (2, 2, 1), (
        f"the Votes tab counts {got['lostN']}, {got['wonN']}, {got['pendingN']}")
    assert re.search(r">Votes\s*\(2\)\s*</button>", re.sub(r"<(?!/?button)[^>]+>", "", got["tabs"])), (
            "the Votes tab of a CACR with one chamber vote and the voters' does not say 2")
    # The Documents tab: the status page is not where a CACR's voters' answer
    # is from, and says where it is; an election to come keeps the plain line.
    for k, where in (("docsBallot", "the count on the Votes tab"),
                     ("docsDocket", "its docket's referendum line")):
        assert f"whether the voters ratified it is read from {where}" in flat(got[k]) \
            and "saying where the bill stands" not in got[k], (
                f"a CACR's status page is credited with the voters' answer: {flat(got[k])[:300]!a}")
    assert "saying where the bill stands" in got["docsPending"], (
        f"a CACR still to go to the voters lost its status page's line: {flat(got['docsPending'])!a}")
    return "ok", ("452,307 and 237,221 whole in the legend, 65.6% in the ring, the mark two "
                  "thirds round, Not ratified in words; 85.7% Ratified; the docket's 159,439 "
                  "said against the Secretary of State's 169,439; Nov 3, 2026 to come, and past "
                  "with no count; after the chambers', and counted; the status page not "
                  "credited with the voters")
_RAIL_LABEL = {"I": "Introduced", "H": "House", "S": "Senate", "G": "Governor", "L": "Law",
               "V": "Voters"}
# The narrowest a phone's rail may set two stops' words: more than a word
# space at 11px in the fallback face, which is about 3px.
_RAIL_GAP = 3.0
# Rails from the index that were tightest when the review measured them: two
# full stops side by side, a year on both dates, a word wider than its stop.
_RAIL_WORST = [
    ("2025-2026 HB510", [["Ip", "2025-01-09"], ["Hp", "2026-01-07", "197–149, amended"],
                         ["Sx", "2026-05-07", "refused conference"], ["G-"], ["Lx"]]),
    ("2025-2026 HB104", [["Ip", "2025-01-08"], ["Hp", "2026-01-08", "voice vote, amended"],
                         ["Sx", "2026-03-05", "postponed"], ["G-"], ["Lx"]]),
    ("2025-2026 SB445", [["Ip", "2026-01-07"], ["Sp", "2026-03-26", "voice vote, amended"],
                         ["Hp", "2026-05-07", "voice vote, amended"],
                         ["Gp", "2026-06-19", "signed"], ["Lp", "", "Chapter 185"]]),
    ("2025-2026 SB34", [["Ip", "2025-01-08"], ["Sp", "2025-03-06", "16–8"],
                        ["Hp", "2026-01-07", "186–155, amended"], ["G-"], ["Lx"]]),
    ("1993-1994 HB288", [["Ip", "1993-01-06"], ["Hp", "1993-03-11", "to Appropriations"],
                         ["Sx", "1994-05-24", "killed"], ["G-"], ["Lx"]]),
    ("1991-1992 SB475", [["Ip"], ["Sp", "1992-02-19", "voice vote"],
                         ["Hx", "1992-04-23", "refused conference"], ["G-"], ["Lx"]]),
]


def _rail_phone(css):
    """(the width of a list card's rail on a 360px phone, the gutter either
    side of a stop's words), read from app.css. The card is 336px inside
    its 12px page margins, 334 inside its edges, and its head pads 16px on
    the left and 46px on the right for the corner link -- 16 once the rail
    takes that reserve back."""
    root = dict(re.findall(r"--(sp-\d+):(\d+)px", css))
    m = re.search(r"\.rail\.dated small\{[^}]*padding-inline:([^;}]+)", css)
    pad = 0.0
    if m:
        v = m.group(1).strip()
        t = re.fullmatch(r"var\(--(sp-\d+)\)", v)
        pad = float(root.get(t.group(1), 0)) if t else float((re.match(r"[\d.]+", v) or ["0"])[0])
    back = re.search(r"\.card:not\(\.focus\) \.chead \.rail\.dated\{width:calc\(100% \+ 46px "
                     r"- var\(--sp-6\)\)", css)
    # SINCE 10 OCTOBER 2026 THE HEAD PADS ALIKE ON BOTH SIDES (C5): the corner
    # link went, the number being the link, and its 46px with it.
    alike = re.search(r"(?m)^\.chead\{padding:var\(--sp-6\);", css)
    # On a phone the rail takes half the card's padding either side
    # (8 October 2026), 8px of the head's 16 on each hand.
    phone = re.search(r"@media \(max-width:30em\)\{\s*\.chead \.rail\.dated\{margin-inline:"
                      r"calc\(-1 \* var\(--(sp-\d+)\)\)\}", css)
    take = 2 * float(root.get(phone.group(1), 0)) if phone else 0
    return 334 - 16 - (16 if (back or alike) else 46) + take, pad


def _rail_drawn(rail):
    """What a card draws under each stop of `rail` (an index row's stops):
    its day, month first and with its year on every stop (the person, 8
    October 2026: the year was on the first and wherever it changed, so one
    bill's rail carried it on some stops and not others), or nothing. Never
    the stop's words (the person, 5 October 2026: "only have dates for the
    actions under each of the items") -- _rail_on_a_phone holds app.js's
    datedRail to exactly this."""
    import shell as S
    return [S.date_words(cell[1]) if len(cell) > 1 and cell[1] else "" for cell in rail]


def _rail_gap(rail, width, pad):
    """The narrowest gap, in px, between two neighbouring stops' words on one
    row of `rail` (an index row's stops) laid out `width` wide, as a card
    draws them (_rail_drawn): the stop's name over its day, both at the type
    scale's 14px since 8 October 2026, and on a rail under 552px (34.5em, the
    container query in app.css) the day's year on a line of its own. A card in
    a list on a phone draws them at 13px since that evening (the compact card,
    _phone_card_compact); 14px is a bill's own page's, the tighter of the two,
    so it is what is laid out here."""
    def w(s, px):
        return sum(_RAIL_FACE.get(c, 1000) for c in s) * px / 1000

    def wrap(text, room):
        lines, cur = [], ""
        for word in text.split():
            t = f"{cur} {word}" if cur else word
            if cur and w(t, 14) > room:
                lines.append(cur)
                cur = word
            else:
                cur = t
        return lines + ([cur] if cur else [])

    rows = []
    slot = width / len(rail)
    for cell, drawn in zip(rail, _rail_drawn(rail)):
        stop = cell[0]
        parts = [drawn[:-5], drawn[-4:]] if drawn and width < 552 else [drawn] if drawn else []
        lines = [ln for part in parts for ln in wrap(part, slot - 2 * pad)]
        rows.append([w(_RAIL_LABEL.get(stop[:1], stop), 14)] + [w(ln, 14) for ln in lines])
    return min([slot - (a[i] + b[i]) / 2 for a, b in zip(rows, rows[1:])
                for i in range(min(len(a), len(b)))] or [slot])


# Rails from the index whose stops carry words and no day, beside those of
# _RAIL_WORST: under each stop a card draws its day, or nothing.
_RAIL_UNDATED = [
    ("2025-2026 CACR13", [["Ip", "2026-01-07"], ["Hp", "2026-02-05", "325–15"],
                          ["Sp", "2026-03-26", "23–1"], ["Vh", "", "Nov 2026"]]),
    ("2005-2006 CACR30", [["Ip", "2006-01-04"], ["Hp", "2006-03-22", "277–61, amended"],
                          ["Sp", "2006-04-20", "24–0"], ["Vp", "2006-11-07", "ratified"]]),
    ("2025-2026 HB1", [["Ip", "2025-02-20"], ["Hp", "2025-04-10", "192–183, amended"],
                       ["Sp", "2025-06-05", "15–9, amended"], ["Gp", "2025-06-27", "signed"],
                       ["Lp", "", "Chapter 140"]]),
    ("2015-2016 SB305", [["Ip", "2016-01-06"], ["Sp", "2016-02-18", "voice vote"],
                         ["Hx", "", "report not accepted"], ["G-"], ["Lx"]]),
]


@check("frontend", "a phone's rail keeps every stop's words apart from the next stop's")
def _rail_on_a_phone():
    """The list card's rail on a 360px phone: as wide as the bill page's, a
    gutter either side of each stop's words, and on the rails that were
    tightest when it was 272px and had none, no two stops' words closer than
    a word space, laid out in a face wider than the site's (_rail_gap).

    And what is laid out is what app.js draws: under each stop its day and
    nothing else, or nothing where the stop has no day (the person, 5 October
    2026). datedRail is run in node over those rails and the ones with words
    and no day; a stop that draws "voice vote", "Chapter 140" or "Nov 2026"
    again fails here."""
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    if not css:
        return "skip", "app.css is not here"
    rails = _RAIL_WORST + _RAIL_UNDATED
    got = _app_js(json.dumps([r for _n, r in rails])
                  + ".map(r => scope.datedRail({id: 'X', passage: '', rail: r}))",
                  names=("datedRail",))
    drew = "node is not here to draw them"
    if got is not None:
        for (name, rail), html in zip(rails, got):
            stops = re.split(r'<span class="stop ', html)[1:]
            drawn = ["".join(re.sub(r"<[^>]+>", "", (re.findall(r"<small>(.*?)</small>", s, re.S)
                                                     or [""])[0]).split("\n")).strip()
                     for s in stops]
            assert drawn == _rail_drawn(rail), (
                f"{name}'s rail draws {drawn!a} under its stops, where a card draws the "
                f"day alone: {_rail_drawn(rail)!a}")
            assert all(re.fullmatch(r"(?:[A-Z][a-z]{2} \d{1,2}, \d{4})?", d) for d in drawn), (
                f"{name}'s rail draws words under a stop: {drawn!a}")
        drew = (f"app.js draws the day alone under each stop of {len(rails)} rails, and "
                "nothing under a stop with no day")
    width, pad = _rail_phone(css)
    assert width >= 302, (
        f"a list card's rail is {width}px on a 360px phone, inside the corner link's "
        "reserve: app.css no longer gives it the head's whole width")
    assert pad >= 4, f"a rail stop's words have {pad}px either side, where 4 keeps them apart"
    assert not re.search(r"\.rail\.dated small\{[^}]*white-space:nowrap", css), (
        "a rail stop's words may not wrap, so a full stop runs into the next")
    tight = [(round(g, 1), name) for name, rail in _RAIL_WORST
             for g in [_rail_gap(rail, width, pad)] if g < _RAIL_GAP]
    assert not tight, (f"on a {width}px rail these set two stops' words under "
                       f"{_RAIL_GAP}px apart: {tight}")
    worst = min((_rail_gap(r, width, pad), n) for n, r in _RAIL_WORST)
    return "ok", (f"{width}px with {pad:g}px either side of each stop's words; the six "
                  f"tightest rails of the review are {worst[0]:.1f}px apart at least "
                  f"({worst[1]}), in the wider of Public Sans' and Segoe UI's widths; {drew}")


# THE RAIL AT A LARGE TEXT SIZE (the person, 8 October 2026). Where a rail is
# too narrow for its days -- at a 24px browser setting a 375px phone's is 14em
# across -- the foundation stood it up, one stop a line with its day, and the
# person said "I don't like the new design of the rails being stacked
# vertically on mobile". Decided with them the same evening: the rail stays
# horizontal with the stop names and marks only; the days step out of it, and
# stay in How it got here and in what a screen reader hears.
#
# Five names alone are still too wide for one row there: 341px drawn on a
# 333px rail, "Introduced" 12px into "House" and cut 7px at the card's edge
# (Chrome, 9 October 2026). So they take turns, the first, third and fifth
# under the line and the second and fourth over it, the first set from the
# rail's start and the rest centred on their marks (app.css's narrow rail).
# This lays that out in _RAIL_FACE's widths, as _rail_gap does the dated rail.
_RAIL_PHONES = (320, 360, 375, 414)      # the phones a rail is laid out on
_RAIL_TEXT = (16, 18, 20, 24)            # and the browser's text sizes


def _rail_names(rail):
    """The names a rail draws over its marks, from an index row's stops."""
    return [_RAIL_LABEL.get(cell[0][:1], cell[0]) for cell in rail]


def _rail_names_turn(names, width, px):
    """(the narrowest gap, in px, between two names on one row; how far a
    name runs past either end of the rail, 0 where none does) for a rail
    `width` wide too narrow for its days, its names at `px` taking turns
    under and over the line: the first from the rail's start, the rest
    centred on their marks, each stop a share of the width."""
    slot = width / len(names)
    spans = []
    for i, name in enumerate(names):
        w = sum(_RAIL_FACE.get(c, 1000) for c in name) * px / 1000
        left = 0.0 if i == 0 else (i + .5) * slot - w / 2
        spans.append((left, left + w))
    gap = min([spans[i + 2][0] - spans[i][1] for i in range(len(spans) - 2)] or [width])
    past = max(0.0, -min(a for a, _ in spans), max(b for _, b in spans) - width)
    return gap, past


def _rail_narrow_em(css):
    """The width, in em of the rail's text, under which app.css takes a
    rail's days away (the container query that hides .rail.dated small), or
    None."""
    for ctx, sel, body, _ln in _css_rules(css):
        m = re.fullmatch(r"@container rail \(max-width:([\d.]+)em\)", ctx[-1] if ctx else "")
        if m and sel == ".rail.dated small" and ("display", "none") in _css_decls(body):
            return float(m.group(1))
    return None


def _rail_narrow_views(css):
    """[(phone, text size, rail width)] for each phone of _RAIL_PHONES and
    text size of _RAIL_TEXT whose rail app.css draws without its days. A
    phone's rail is as wide on a list card as on a bill's own page
    (_rail_phone), and the query reads it in em of the rail's text, which is
    the browser's size."""
    em = _rail_narrow_em(css)
    if em is None:
        return []
    w360 = _rail_phone(css)[0]
    return [(w, std, w360 + (w - 360)) for w in _RAIL_PHONES for std in _RAIL_TEXT
            if (w360 + (w - 360)) / std <= em]


@check("frontend", "at a large text size a phone's rail stays across, its names and marks only: "
                   "no stop stood on a line of its own, the days in How it got here and said aloud")
def _rail_large_text():
    """The person's answer of 8 October 2026 ("I don't like the new design of
    the rails being stacked vertically on mobile"): where a rail is too
    narrow for its days, app.css keeps every stop in the row, hides the days,
    and sets the names in turns over and under the line from the rail's
    start; no rule there stands a stop on a line of its own, as the
    foundation's did (flex:0 0 100% and a row per stop). Laid out in
    _RAIL_FACE's widths, which are wider than the faces a reader is shown,
    every run of names a rail can have stays apart and inside the rail on
    every phone and text size where that is so -- the 375px phone at 24px
    among them, and never a 360px phone at the browser's default, which keeps
    its days. The days are still drawn in How it got here, and the rail still
    says each in full to a reader who hears it (its aria-label)."""
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    if not css:
        return "skip", "app.css is not here"
    em = _rail_narrow_em(css)
    assert em, "app.css no longer takes a narrow rail's days away (@container rail ... " \
               ".rail.dated small{display:none})"
    rules = {sel: dict(_css_decls(body)) for ctx, sel, body, _ln in _css_rules(css)
             if ctx and ctx[-1] == f"@container rail (max-width:{em:g}em)"}
    stood = [f"{sel} {k}:{v}" for sel, ds in rules.items() for k, v in ds.items()
             if (k in ("flex", "flex-basis") and "100%" in v) or k == "flex-direction"]
    assert not stood, ("the narrow rail stands its stops up again, a line each, where the "
                       f"person asked for it across: {stood}")
    up = rules.get(".rail.dated .stop:nth-child(even) i", {})
    assert up.get("position") == "absolute" and up.get("bottom") == "100%", (
        "the narrow rail's second and fourth names are not set over the line "
        f"(.rail.dated .stop:nth-child(even) i is {up})")
    assert rules.get(".rail.dated .stop:first-child i", {}).get("align-self") == "flex-start", (
        "the narrow rail's first name is centred on its mark, where \"Introduced\" is cut at "
        "the card's edge")
    assert rules.get(".rail.dated .stop", {}).get("margin-top"), (
        "the narrow rail leaves no room over the line for the names set there")
    # The room over the line holds a name's whole line: a name taller than
    # the stop's margin runs up into the sponsor line over the rail (a
    # line-height of 2.5rem over a 1.25rem margin passed; the review of
    # 9 October 2026).
    toks = _css_palette(css)["light"]
    room = _css_px(rules[".rail.dated .stop"]["margin-top"], toks)[0]
    tall = _css_px(rules.get(".rail.dated .stop i", {}).get("line-height", ""), toks)[0]
    assert room is not None and tall is not None and room >= tall, (
        f"the narrow rail's names over the line are {tall}px tall in {room}px of room "
        "(.rail.dated .stop margin-top, .rail.dated .stop i line-height, in rem or px)")
    views = _rail_narrow_views(css)
    assert (375, 24) in {(w, s) for w, s, _ in views}, (
        "a 375px phone at a 24px setting keeps its rail's days, and the rail is 14em there")
    assert (360, 16) not in {(w, s) for w, s, _ in views}, (
        "a 360px phone at the browser's 16px loses its rail's days")
    shapes = {tuple(_rail_names(r)): n for n, r in _RAIL_WORST + _RAIL_UNDATED}
    shapes.update({("Introduced", "House"): "a resolution", ("Introduced", "Senate", "House"):
                   "a resolution of two chambers"})
    bad = [(round(g, 1), round(past, 1), w, std, who) for names, who in shapes.items()
           for w, std, rw in views for g, past in [_rail_names_turn(names, rw, 13 * std / 16)]
           if g < _RAIL_GAP or past > 0]
    assert not bad, (f"where the days step out, names on one row under {_RAIL_GAP}px apart or "
                     f"past the rail's end (gap, past, phone, text size, rail): {sorted(bad)[:5]}")
    worst = min((_rail_names_turn(names, rw, 13 * std / 16)[0], w, std)
                for names in shapes for w, std, rw in views)
    # The days a reader is not shown here are told: the rail's label says
    # each in full, and How it got here draws them.
    rail = [["Ip", "2025-01-08"], ["Hp", "2025-02-13", "voice vote"],
            ["Sp", "2025-05-22", "16–8, amended"], ["Gp", "2025-07-15", "signed"],
            ["Lp", "", "Chapter 160"]]
    got = _app_js("[scope.datedRail({id: 'HB57', passage: '', rail: " + json.dumps(rail) + "}), "
                  "scope.journeyList({id: 'HB57'}, {journey: {steps: [{mark: 'p', body: 'H', "
                  "text: 'Passed on a voice vote', date: '2025-02-13'}]}})]",
                  names=("datedRail", "journeyList"))
    told = "node is not here to draw them"
    if got is not None:
        said = re.search(r'aria-label="([^"]*)"', got[0])
        assert said and all(d in said.group(1) for d in (
            "January 8, 2025", "February 13, 2025", "May 22, 2025", "July 15, 2025")), (
            f"the rail no longer says its days to a reader who hears it: {said and said.group(1)!a}")
        assert 'role="img"' in got[0], "the rail is no longer one image with its label"
        assert re.search(r'<span\s+class="jd">Feb 13, 2025</span>', got[1]), (
            f"How it got here does not draw the day: {got[1]!a}")
        told = "the rail says every day in full, and How it got here draws it"
    return "ok", (f"under {em:g}em the rail keeps its stops across, its days out, its names in "
                  f"turns: {len(views)} phone views of {len(_RAIL_PHONES) * len(_RAIL_TEXT)}, "
                  f"{len(shapes)} runs of names, at least {worst[0]:.1f}px apart ({worst[1]}px "
                  f"phone, {worst[2]}px text); {told}")


# THE PHONE'S BILL CARD, COMPACT (the person, 8 October 2026). Looking at the
# foundation's phone screenshots: "I think the mobile text scaling might be a
# bit off and I preferred the old bill card previews on mobile". Decided with
# them the same evening, under 600px (37.5em) at the browser's own size:
_PHONE_CARD = {
    ".card:not(.focus) .chead .ctitle": ("--t-card", 17),           # the title, in the serif
    ".card:not(.focus) .chead :is(.cmeta,.cwhy)": ("--t-sm", 14),   # sponsor and committee
    ".card:not(.focus) .crow .cstat": ("--t-sm", 14),               # the status chip
    ".card:not(.focus) .crow .cyear": ("--t-sm", 14),               # "carried over", a chip too
    ".card:not(.focus) .rail.dated :is(.stop i,small)": ("--t-rail", 13),  # the rail, the floor
}


@check("frontend", "a bill's card in a list on a phone is compact: a 17px serif title, a 14px "
                   "sponsor line and chip, a 13px rail with the year on every stop, all in rem")
def _phone_card_compact():
    """The card on the bill search and a committee's or a member's page (app.js
    cardHtml, closed or opened -- a bill's own page, .focus, keeps its head),
    under 37.5em: each size of _PHONE_CARD by its token, each token the size
    the person chose and in rem, so the browser's text setting still grows
    them; the title in the serif; and the year on every dated stop (app.js
    datedRail), which no rule hides but the narrow rail's, where the days
    step out whole (_rail_large_text)."""
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    if not css:
        return "skip", "app.css is not here"
    tokens = _css_palette(css)["light"]
    rules = {sel: dict(_css_decls(body)) for ctx, sel, body, _ln in _css_rules(css)
             if ctx == ("@media (max-width:37.5em)",)}
    bad = []
    for sel, (tok, px) in _PHONE_CARD.items():
        size = rules.get(sel, {}).get("font-size")
        if size != f"var({tok})":
            bad.append(f"{sel} is {size or 'not set'} under 37.5em, not var({tok})")
        got = _css_px(f"var({tok})", tokens)
        if got != (px, "rem"):
            bad.append(f"{tok} is {got[0]}px ({got[1]}), where the person chose {px}px in rem")
    serif = [sel for _c, sel, body, _l in _css_rules(css)
             if ".ctitle" in [s.strip() for s in sel.split(",")]
             and dict(_css_decls(body)).get("font-family") == "var(--serif)"]
    if not serif:
        bad.append("a card's title is no longer set in the serif")
    # AND NOTHING SETS IT IN ANOTHER FACE: a rule that reaches the title on a
    # phone alone ("...ctitle{font-family:var(--sans)}" under 37.5em) left
    # the rule above standing and passed (the review of 9 October 2026).
    other = sorted({f"{' '.join(ctx)} {sel}" for ctx, sel, body, _l in _css_rules(css)
                    if any(re.search(r"\.ctitle\b[^\s>+~]*$", s.strip()) for s in sel.split(","))
                    for k, v in _css_decls(body)
                    if k in ("font-family", "font") and v != "var(--serif)"})
    if other:
        bad.append(f"a card's title is set in another face: {other}")
    # A year hidden any way a rule can hide it -- not drawn, not seen or
    # transparent -- on the stop's year or the day that holds it (a rule at
    # visibility:hidden, or on `.rail small`, passed; the same review).
    hid = [f"{' '.join(ctx)} {sel}" for ctx, sel, body, _l in _css_rules(css)
           if re.search(r"\.ry\b|\.rail\b[^,{]*\bsmall\b", sel)
           and any((k, v) in (("display", "none"), ("visibility", "hidden"),
                              ("visibility", "collapse"), ("opacity", "0"))
                   for k, v in _css_decls(body))
           and not (ctx and ctx[-1].startswith("@container rail") and sel == ".rail.dated small")]
    if hid:
        bad.append(f"a rule hides a stop's year: {hid}")
    assert not bad, "; ".join(bad)
    rail = [["Ip", "2025-01-08"], ["Hp", "2026-01-07"], ["Sx", "2026-05-07"], ["G-"], ["Lx"]]
    html = _app_js("scope.datedRail({id: 'X', passage: '', rail: " + json.dumps(rail) + "})",
                   names=("datedRail",))
    drew = "node is not here to draw it"
    if html is not None:
        years = re.findall(r'<small>[^<]*<span class="ry">\s*(\d{4})</span></small>', html)
        assert years == ["2025", "2026", "2026"], (
            f"a card's rail does not carry the year on every dated stop: {html!a}")
        drew = "the year on each of three dated stops"
    return "ok", (f"under 37.5em: {', '.join(f'{tok} {px}px' for tok, px in _PHONE_CARD.values())}"
                  f" in rem, the title in the serif; {drew}")


@check("frontend", "on a phone a bill card's status stays at the right end of the card's first line, beside "
                   "the number, as on a wide screen")
def _phone_card_status_right():
    """The owner, 14 November 2026: "move the bill status chips to the top
    right of the cards like they are on desktop". Under the narrow queries
    (the card's list rules and the static pages') the head row (.crow) must
    not wrap, its chip (.cstat) must keep margin-left:auto, and no rule
    under a narrow query may put margin-left:0 on a .crow chip, which is
    what dropped it to a line of its own on 9 October."""
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    if not css:
        return "skip", "app.css is not here"
    narrow = [(ctx, sel, dict(_css_decls(body))) for ctx, sel, body, _ln in _css_rules(css)
              if ".crow" in sel and ":not(.focus)" not in sel and any("max-width" in c for c in ctx)]
    bad = []
    for want in (".crow", ".crow .cstat"):
        got = [s for _c, s, _d in narrow if s.endswith(want)]
        if len(got) < 2:
            bad.append(f"{want} is set under {len(got)} narrow queries, not the card list's and the static pages'")
    for ctx, sel, d in narrow:
        if "cstat" in sel and d.get("margin-left") not in (None, "auto"):
            bad.append(f"{' '.join(ctx)} {sel} sets margin-left:{d['margin-left']}, off the right end")
        if sel.endswith(".crow") and d.get("flex-wrap") == "wrap":
            bad.append(f"{' '.join(ctx)} {sel} lets the head row wrap, so the status drops below the number")
        if sel.endswith(".crow .cstat") and d.get("margin-left") != "auto":
            bad.append(f"{' '.join(ctx)} {sel} does not keep margin-left:auto")
        if sel.endswith(".crow") and d.get("flex-wrap") != "nowrap":
            bad.append(f"{' '.join(ctx)} {sel} does not keep the row on one line (flex-wrap:nowrap)")
    assert not bad, "; ".join(bad)
    return "ok", ("under the narrow queries (the card list's and the static pages') the head row stays on "
                  "one line and the status keeps margin-left:auto, with no margin-left:0 on it")


@check("frontend", "a vote tally in the Summary links to its card on the Votes tab, by date, chamber and counts")
def _summary_votes_linked():
    """The owner, 10 November 2026: a tally like 198-167 in the Summary opens
    the Votes tab at that vote. A tally is linked only where one card has its
    date, its chamber and its counts (voteLinks); the same counts on another
    day or in the other chamber stay text, and so do two cards that fit. Each
    card has the anchor the link names."""
    html = _app_js(
        "(() => { const S = " + json.dumps(_SUMMARY_VOTES) + "; return {summary: scope.renderSummary(S.b, S.d, null),"
        " votes: scope.renderVotes(S.b, S.d), anchors: scope.voteAnchors(S.d)}; })()",
        names=("renderSummary", "renderVotes", "voteAnchors"))
    if html is None:
        return "skip", "node or app.js is not here"
    got, sm = html, html["summary"]
    assert got["anchors"] == ["vote-2025-03-12-H-231-99", "vote-2025-03-12-H-231-99-2", "vote-2025-04-10-S-16-8",
                              "vote-2025-05-01-H-198-167"], f"the cards' anchors: {got['anchors']}"
    for a in got["anchors"]:
        assert f'id="{a}"' in got["votes"], f"the Votes tab has no card with id {a}"
    links = re.findall(r'<a class="vtl" href="([^"]+)" data-vote="([^"]+)">(?:<span class="tally">)?([^<]+)', sm)
    said = [(h, t) for h, _v, t in links]
    # Journey: the Senate's 16-8 of 10 April, and the House's 198-167 of 1 May.
    assert ("bill/2025/hb1/votes#vote-2025-04-10-S-16-8", "16–8") in said, f"a row's tally is not linked: {said}"
    assert ("bill/2025/hb1/votes#vote-2025-05-01-H-198-167", "198–167") in said, f"a division's tally is not linked: {said}"
    # The same counts on 2 May, in the other chamber on 10 April, and on 12 March
    # (two cards fit) stay text.
    assert sm.count('class="vtl"') == 4, f"{sm.count('class=\"vtl\"')} tallies linked, not the 2 rows and 2 story ones: {said}"
    assert "Passed, <span class=\"tally\">198–167</span>" in sm and "Passed, <span class=\"tally\">231–99</span>" in sm, (
        "a tally no single card fits was changed")
    # The story: its sentence's date and first chamber.
    story = sm[sm.index('<p class="story">'):]
    assert story.count('class="vtl"') == 2, "the story links other than its two tallies"
    assert re.search(r'concurred <a class="vtl" href="[^"]*#vote-2025-05-01-H-198-167"', story), "a story tally is not linked"
    assert re.search(r'the Senate voted <a class="vtl" href="[^"]*#vote-2025-04-10-S-16-8"', story), "a Senate story tally is not linked"
    assert "the House passed it 16–8" in story, "the House's 16-8 of 10 April, which no card has, was linked"
    # The address /bill/<year>/<bill>/votes#vote-... stays this bill's page, opens
    # the Votes tab and brings the card up, on load, on a click and on a hash change.
    src = _source("src/pages/app.js").replace("\r\n", "\n")
    assert src.count("VOTE_HASH.test(said)") >= 3 and "jumpToVote();\n};" in src \
        and "a[data-vote]" in src, "a vote's address does not open the Votes tab at its card"
    assert "a.vtl{white-space:nowrap}" in _source("src/pages/app.css"), (
        "app.css lets a tally link break across two lines")
    return "ok", "tallies link to their cards by date, chamber and counts, none where no single card fits"


@check("frontend", "a bill's Videos tab is a committee's Videos tab for one bill: one player, a playlist of "
                   "its recordings, the chosen sitting's moments, vote and sign-ins under it, each fact once, "
                   "and a plain entry for a sitting with none")
def _hearings_one_player():
    """The owner, 10 November 2026: "changing the ways bills are formatted to
    be more similar to how the committee videos tab is formatted ... we'd only
    have one player and the format would be cleaner", keeping "displays of
    testimony numbers and outcome in chips". renderHearings draws videoView,
    the Videos tab's own: ONE player, the bill's recordings as its playlist in
    the order of the bill's story (a row each: its day, its kind's chip, where,
    its length), and under the player for the one chosen when and where, the
    sign-in counts and the committee's outcome as chips, the floor's roll call
    with its count, the bill's moments with "approximate" where inferred. A
    sitting with no recording to play keeps a card of its own. The committee's
    own list puts a bill's moments and its outcome chip on one line.

    CALMER, AND VIDEOS AGAIN (the owner, 19 November 2026): each fact once --
    the day, the kind, the committee and the length are the chosen row's, so
    the player has no caption and the detail under it repeats none of them;
    the bill's moments are the first line under the player, labelled, as play
    buttons; the sign-ins are plain figures under "Public sign-ins", not the
    chips that read as more buttons; "approximate" where a moment is
    inferred."""
    st = [
        {"when": "2025-03-12", "time": "10:00", "what": "public hearing", "committee": "Judiciary", "body": "H",
         "venue": "LOB 206", "video_id": "VIDA", "state": "located", "start": 600.0, "end": 1500.0,
         "start_stated": False, "seconds": 7380,
         "testimony": {"total": 60, "support": 58, "oppose": 2, "neutral": 0, "dated": True}},
        {"when": "2025-03-19", "time": "13:00", "what": "executive session", "committee": "Judiciary", "body": "H",
         "venue": "LOB 206", "video_id": "VIDA", "state": "stated", "start": 120.0, "end": None,
         "start_stated": True, "seconds": 7380},
        {"when": "2025-04-09", "what": "floor debate", "committee": "House", "video_id": "VIDB",
         "state": "floor_precise", "debate_start": 3000.0, "debate_end": 3600.0, "window_start": 2400.0,
         "start_stated": True, "motions": ["OTP"], "tallies": ["190-149"], "mks": [{"mk": "otp"}], "seconds": 20000},
        {"when": "2019-01-08", "what": "public hearing", "committee": "Judiciary", "body": "H",
         "video_id": "", "state": "prestream",
         "testimony": {"total": 5, "support": 3, "oppose": 2, "neutral": 0, "dated": True}},
    ]
    d = {"stations": st,
         "rollcalls": [{"date": "2025-04-09", "body": "H", "yeas": 190, "nays": 149, "passed": True, "mk": "otp",
                        "question": "Ought to Pass"}],
         "reports": [{"date": "2025-03-19", "body": "H", "dated": "signed", "majority_recommendation": "Ought to Pass",
                      "reports": [{"side": "Majority", "vote_yeas": 12, "vote_nays": 2}]}]}
    day = {"outcomes": [{"bill": "HB1", "outcome": "voted",
                         "votes": [{"act": "report", "recommendation": "Ought to Pass", "yeas": 10, "nays": 2}]}]}
    items = [{"bill": "HB1", "n": "HB 1", "title": "a title", "start": 150, "state": "stated", "kind": "executive session",
              "video_id": "VIDA", "year": "2025"}]
    cmte = {"code": "H1", "name": "Judiciary", "chamber": "H"}
    html = _app_js(
        "(() => { const D = " + json.dumps({"d": d, "day": day, "items": items, "cmte": cmte}) + ";"
        " const b = {id: 'HB1', n: 'HB 1', year: '2025'};"
        " const first = scope.renderHearings(b, D.d);"
        " scope.HEAR_CHOSEN['bill|' + scope.dkey('HB1')] = 'h1';"
        " const exec = scope.renderHearings(b, D.d);"
        " scope.HEAR_CHOSEN['bill|' + scope.dkey('HB1')] = 'h2';"
        " const floor = scope.renderHearings(b, D.d);"
        " const line = scope.cmteVideoDetail(D.cmte, {date: '2026-02-03', id: 'VIDA'}, D.items, D.day, '');"
        " return {first, exec, floor, line}; })()",
        names=("renderHearings", "HEAR_CHOSEN", "dkey", "cmteVideoDetail"))
    if html is None:
        return "skip", "node or app.js is not here"
    first, ex, floor, line = (re.sub(r"\s+", " ", html[k]) for k in ("first", "exec", "floor", "line"))
    assert first.count('class="pstub"') == 1 and first.count("data-player=") == 1, (
        "the tab has more than one player")
    assert first.count('class="vwrow"') == 3 and first.count('aria-current="true"') == 1 and \
        'data-vwpick="h0" aria-current="true"' in first, "the playlist is not the three recordings, the first chosen"
    assert first.index("Public Hearing") < first.index("Executive Session") < first.index("Session Day"), (
        "the playlist is not in the order of the bill's story, each with its kind's chip")
    assert "2 h 3 min" in first and "House Judiciary" in first, "a row lacks its length or its committee"
    head = first[first.index('class="vwdetin"'):first.index('class="vwside"')]
    for want in ("<b>58</b> support", "<b>2</b> oppose", "<b>60</b> signed in", '<h4 class="vwsh">Public sign-ins</h4>',
                 "Legislative Office Building 206", 'data-seek="h0_VIDA|600"', 'data-seek="h0_VIDA|1500"',
                 '<span class="vwml">Where this bill is in the recording</span>',
                 'aria-label="Play from 00:10:00, where it starts"', 'aria-label="Play from 00:25:00, where it ends"',
                 "10:00</button>", "25:00</button>", '<span class="vwto">to</span>', "approximate"):
        assert want in head, f"the first sitting's detail lacks {want!r}: {head[:300]}"
    assert re.search(r"10:00\sAM", head), f"the first sitting's detail lacks its time: {head[:300]}"
    # EACH FACT ONCE: the row says the day, the kind and the committee, and
    # nothing under the player says them again; no caption under the player;
    # the counts are no chips; the moments come before the counts.
    for gone in ("Mar 12, 2025", "Public Hearing", "House Judiciary", 'class="chip sgn', "vwcap"):
        assert gone not in head and (gone != "vwcap" or gone not in first), (
            f"the first sitting's detail says {gone!r} again: {head[:300]}")
    assert head.index('class="vwmoms"') < head.index('class="vwsg"'), "the sign-ins come before the moments"
    assert 'data-embed="VIDA|598|h0_VIDA"' in first and "watch?v=VIDA&t=598s" in first, (
        "the player and its YouTube link do not open at the bill's moment")
    # What was voted: the committee's report of the day, then the floor's roll call, chip and count.
    xd = ex[ex.index('class="vwdetin"'):ex.index('class="vwside"')]
    assert "Executive Session" not in xd and "Ought to Pass (12–2)" in re.sub(r"<[^>]+>", "", xd) and \
        'data-embed="VIDA|118|h1_VIDA"' in ex and "approximate" not in xd, (
            f"the executive session's detail is not its report chip with its count: {xd[:400]}")
    fl = floor[floor.index('class="vwdetin"'):floor.index('class="vwside"')]
    assert "Session Day" not in fl and "190–149" in fl and "rcres pass" in fl and \
        'data-embed="VIDB|3000|h2_VIDB"' in floor and "50:00</button>" in fl and "1:00:00 vote</button>" in fl \
        and 'aria-label="Play from 01:00:00, the vote"' in fl, (
            f"the floor sitting's detail is not its vote, count and moments: {fl[:400]}")
    # The plain entry: the sitting before the channels, with its sign-ins.
    assert 'class="hplain"' in first and 'class="stn pend"' in first and "Jan 8, 2019" in first and \
        "<b>5</b> signed in" in first and "No recording to play" in first, "a sitting with no recording lost its entry"
    # The committee's list: the number, its moments and its chip on one line, the title under them.
    assert re.search(r'<a class="vwbn"[^>]*>HB 1</a><span class="vwmom"><span class="mjumps">.*?</span>'
                     r'<span class="vwout">.*?cstat.*?</span></span><span class="vwbt">a title</span>', line), (
        f"the committee's bill line is not number, moments and chip on one line, then the title: {line[:400]}")
    # A chip's own rule (.cstat, .rcres) pushes it to the right edge; beside the moments it must not.
    css = _source("src/pages/app.css")
    assert ".vwbills .vwmom .chip,.vwres .chip{margin-left:0}" in css, (
        "app.css lets the outcome chip go to the right edge, away from the moments")
    return "ok", ("one player and a playlist of the bill's recordings, no caption; under it the moments as "
                  "labelled play buttons, then the time, room, vote and sign-ins as figures, nothing the row "
                  "says said again; a sitting with no recording its own entry; the committee's moments and "
                  "chip on one line")


@check("frontend", "a bill's Videos tab says Videos wherever a reader meets it, and keeps \"approximate\" "
                   "and the source line", needs=("civics",))
def _videos_tab_words(civics):
    """The owner, 19 November 2026: the Hearings tab is Videos, every
    user-visible "Hearings" for it renamed, the Spanish as a draft, with
    nothing it must say lost: an inferred moment says "approximate", a stated
    one does not (CLAUDE.md, Timestamps), and the source line names the
    General Court's channels, shorter. The strip draws "Videos", the Using
    This Site guide and the two pages that send a reader to the tab name it,
    lang/es.json carries their drafts, and no Senate hearing report is left
    under the player."""
    body = civics.BODY_SITE
    assert "<b>Videos</b> &mdash;" in body and "<b>Hearings</b>" not in body and "<b>Sponsors</b>" not in body \
        and ">Videos</span>" in civics.BILL_TABS_PICTURE and "Hearings" not in civics.BILL_TABS_PICTURE \
        and "Sponsors" not in civics.BILL_TABS_PICTURE, "Using This Site still names a Hearings or a Sponsors tab"
    src = _source(_paths.locate("civics.py"))
    assert "Hearings tab" not in src and src.count("Videos tab plays") == 2, (
        "a Learn page still sends a reader to the Hearings tab")
    es = json.loads(_source("src/pages/lang/es.json"))["strings"]
    vids = ("guide.testifying.this-site-holds-public-hearings-each", "learn.state-agencies.where-a-hearing-was-recorded-bills",
            "guide.using-this-site.videos-the-recording-of-each-meeting", "guide.using-this-site.videos")
    assert all("Videos" in (es.get(k) or {}).get("en", "") and "Videos" in (es.get(k) or {}).get("es", "")
               for k in vids) and not any("pestaña Hearings" in v.get("es", "") for v in es.values()), (
        "lang/es.json still names the Hearings tab, or lacks the Videos tab's drafts")
    st = [{"when": "2025-03-12", "what": "public hearing", "committee": "Judiciary", "body": "H",
           "video_id": "VIDA", "state": "located", "start": 600.0, "end": 900.0, "start_stated": False},
          {"when": "2025-03-19", "what": "public hearing", "committee": "Judiciary", "body": "H",
           "video_id": "VIDB", "state": "stated", "start": 60.0, "end": 900.0, "start_stated": True}]
    js = ("(() => { const b = {id: 'HB1', n: 'HB 1', term: '2025-2026', year: 2025}, d = {stations: "
          + json.dumps(st) + "}; const out = {tab: scope.renderHearings(b, d)};"
          " scope.HEAR_CHOSEN['bill|' + scope.dkey('HB1')] = 'h1'; out.stated = scope.renderHearings(b, d);"
          " out.strip = scope.renderDetail(b, d); return out; })()")
    got = _app_js(js, names=("renderHearings", "renderDetail", "HEAR_CHOSEN", "dkey"))
    if got is None:
        return "skip", "node, app.js or the stub is not here"
    det = lambda h: h[h.index('class="vwdetin"'):h.index('class="vwside"')]
    assert "approximate" in det(got["tab"]) and "approximate" not in det(got["stated"]), (
        "an inferred moment lost \"approximate\", or a stated one carries it")
    assert "Recordings from the General Court&rsquo;s House and Senate YouTube channels." in got["tab"], (
        "the source line is gone")
    assert re.search(r'data-t="2">Videos<', got["strip"]) and "Hearings" not in got["strip"].split("</div>")[0], (
        "the strip does not call the tab Videos")
    return "ok", ("the strip, Using This Site, the two Learn pages and their Spanish drafts say Videos; "
                  "an inferred moment says approximate and a stated one not; the source line kept")


@check("frontend", "Cite this page and Report a problem sit level in a page's row of actions: the report box "
                   "takes no margin above it there")
def _actions_level():
    """The owner, 10 November 2026: on a town's page Report a problem stood
    12px lower than Cite this page. Both are in #pageacts (shell.py's row),
    the report box in #reportbox (app.js mountReport), whose own rule gives
    it margin-top to stand clear of the record it follows; in the row that
    margin is what pushed it down. A page's row keeps none, as a bill page's
    (.racts #reportbox is display:contents). Measured in a browser: both
    buttons' tops the same, at 1280 and at 390."""
    css = _source("src/pages/app.css")
    rules = _css_rules(css)
    base = [b for ctx, sel, b, _l in rules if not ctx and sel == "#reportbox"]
    assert base and "margin-top" in "".join(base), "#reportbox no longer stands clear of the record below it"
    level = [b for ctx, sel, b, _l in rules if not ctx and sel == ".pageacts > #reportbox"]
    assert level and ("margin-top", "0") in _css_decls(level[0]), (
        "app.css does not take the report box's margin off in a page's row of actions (.pageacts > #reportbox)")
    # After the box's own rule, or the margin wins by coming last.
    assert css.index(".pageacts > #reportbox{") > css.index("#reportbox{display:flex"), (
        "the row's rule comes before the report box's own")
    return "ok", "the report box has no margin above it in a page's row of actions, so it is level with Cite"


@check("frontend", "a tally in How it got here stays on one line, never broken after its dash")
def _tally_whole():
    """A browser may break a line after an en dash, and on a phone How it got
    here set "Passed with an amendment, 231–" over "99", and "189–" over
    "155" (the review of the merge, 8 October 2026). app.js holds each tally
    in a span app.css keeps on one line (tallyWhole, .jl .tally): a count
    either side of the dash, thousands and all, and nothing else -- not a
    rule's number, "Senate Rule 3-23", nor the comma after a tally."""
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    if not css:
        return "skip", "app.css is not here"
    # At every width, so outside any query: the break was on a phone, and a
    # rule kept for wide windows alone passed (the review of 9 October 2026).
    assert any(not ctx and sel == ".jl .tally" and ("white-space", "nowrap") in _css_decls(body)
               for ctx, sel, body, _l in _css_rules(css)), (
        "app.css does not keep a How it got here tally on one line at every width "
        "(.jl .tally, outside any @media)")
    texts = ["Passed with an amendment, 231–99", "Killed, 170–163, reconsidered on May 3",
             "Not ratified, 355,054–266,883 (the Secretary of State's count)",
             "Killed under Senate Rule 3-23, still on the table at adjournment",
             "Passed on a voice vote"]
    steps = [{"mark": "p", "body": "H", "text": x, "date": "2026-03-11"} for x in texts]
    html = _app_js("scope.journeyList({id: 'HB9'}, {journey: {steps: " + json.dumps(steps) + "}})",
                   names=("journeyList",))
    if html is None:
        return "skip", "node or app.js is not here"
    held = re.findall(r'<span class="tally">(.*?)</span>', html)
    assert held == ["231–99", "170–163", "355,054–266,883"], (
        f"How it got here holds {held!a} whole, not each tally and nothing else")
    words =[re.sub(r"<[^>]+>", "", m) for m in
             re.findall(r'<span class="jt">(.*?)</span><span\s+class="jd">', html, re.S)]
    assert words == texts, f"a tally's span changed the words How it got here says: {words!a}"
    return "ok", ("three tallies each held on one line, thousands and all; Senate Rule 3-23 "
                  "and the words around them as they were")


@check("data", "every index rail keeps its stops' words apart on a phone")
def _rails_on_a_phone():
    """_rail_on_a_phone's measure over every rail the index carries, laid out
    as a list card draws it on a 360px phone: each stop's day and nothing else
    (_rail_drawn, which _rail_on_a_phone holds app.js to). The words a row
    carries beside its days are said and not drawn, so they take no room."""
    idx = Path("site/idx")
    css = _source("src/pages/app.css") if Path("src/pages/app.css").exists() else ""
    if not (idx.is_dir() and css):
        return "skip", "no built idx/, or no app.css"
    width, pad = _rail_phone(css)
    n, tight, names = 0, [], {}
    for f in sorted(idx.glob("*.json")):
        if not re.match(r"\d{4}-\d{4}$", f.stem):
            continue
        for r in json.loads(f.read_text(encoding="utf-8")):
            if not r.get("rail"):
                continue
            n += 1
            g = _rail_gap(r["rail"], width, pad)
            if g < _RAIL_GAP:
                tight.append((round(g, 1), f"{f.stem} {r.get('id')}"))
            names.setdefault(tuple(_rail_names(r["rail"])), f"{f.stem} {r.get('id')}")
    if not n:
        return "skip", "no index row carries a rail"
    tight.sort()
    assert not tight, (f"{len(tight):,} of {n:,} rails set two stops' words under "
                       f"{_RAIL_GAP}px apart on a {width}px rail: {tight[:5]}")
    # And with its names alone, taking turns over and under the line, where
    # the rail is too narrow for its days (_rail_large_text): every run of
    # names the index carries, on each phone and text size that is so.
    narrow = _rail_narrow_views(css)
    turns = [(round(g, 1), round(past, 1), w, std, who)
             for names_, who in names.items() for w, std, rw in narrow
             for g, past in [_rail_names_turn(names_, rw, 13 * std / 16)]
             if g < _RAIL_GAP or past > 0]
    assert not turns, (f"{len(turns)} rails set two names under {_RAIL_GAP}px apart, or a "
                       f"name past the rail's end, where the days step out (gap, past, phone, "
                       f"text size, bill): {sorted(turns)[:5]}")
    return "ok", (f"{n:,} rails, each stop's words at least {_RAIL_GAP:g}px from the next's at "
                  f"{width}px; their {len(names)} runs of names apart and inside the rail on the "
                  f"{len(narrow)} phone views too narrow for the days")


@check("frontend", "there is one stylesheet, and the rules for the five build_pages pages alone "
                   "are scoped to them")
def _one_stylesheet():
    """Two stylesheets is how a site grows two dialects.

    app.css dressed the record pages and build_pages.py kept 24 KB of its own
    for the home page, the roster, About, 404 and the town pages, so a rule was
    fixed in one of them at a time and each file went on looking internally
    consistent while they drifted. On 16 September that block moved into
    app.css, scoped to :where(body.pg) -- :where so that every rule keeps the
    weight it had, which a plain body.pg did not: it made the block's `button`
    reset beat `.themer` and the theme control came out as bare text. On 23
    October 2026 those pages stopped loading style.css, a cut of app.css, and
    load app.css itself (_one_stylesheet_linked).

    So: build_pages.py keeps no CSS of its own and cuts none out of app.css;
    app.css has no SHARED or PAGES markers for a cut to be made by again; and
    every rule in its block for those pages alone, THE PAGES build_pages.py
    WRITES, is scoped to them, or all 33,683 record pages would take it.
    """
    src = _source(_paths.locate("build_pages.py"))
    app = _source("src/pages/app.css")
    for gone in ('CSS = """', "def stylesheet(", "def shared(", "def pages_region("):
        assert gone not in src, (
            f"build_pages.py has {gone!r} again: a stylesheet of its own, or a cut of "
            "app.css, which is how the pages it writes came to be drawn by different rules")
    for mark in ("/* PAGES:START", "/* PAGES:END", "/* SHARED:START", "/* SHARED:END"):
        assert mark not in app, (
            f"app.css has {mark} again. Nothing reads it, and a region that looks as if "
            "it decides which pages take a rule is the arrangement this replaced")
    head = "/* THE PAGES build_pages.py WRITES"
    tail = "/* ---- /THE PAGES build_pages.py WRITES"
    assert app.count(head) == 1 and app.count(tail) == 1, (
        "app.css's block for the pages build_pages.py writes has lost its heading or its end")
    pages = app[app.index(head):app.index(tail)]
    assert "﻿" not in app, (
        "app.css carries a zero-width mark, which silently kills the rule after "
        "it -- it cost the pages their box-sizing on 16 September")
    stray = [s for s in re.findall(r"(?m)^([.#a-zA-Z][^{\n]*)\{", pages)
             if ":where(body.pg)" not in s and not s.startswith(("body:where", "html", "*", "@"))]
    assert not stray, (
        f"{len(stray)} rules in the block for the pages build_pages.py writes are not "
        f"scoped to them, so every record page takes them: {stray[:3]}")
    return "ok", (f"{len(re.findall(r':where\(body.pg\)', pages)):,} rules for those pages, "
                  "scoped to them, in the one file")


@check("frontend", "the Laws Changed filter's offers sit in the column under its box, a name of 143 "
                   "characters wrapping inside it, and its Clear is 44px to a finger without "
                   "standing its line apart; neither is printed")
def _laws_changed_layout():
    """Measured in Chromium at 390 and 1280 on 26 October 2026, with the
    real list: RSA 14-C's name, 143 characters, wraps inside the 17rem
    column in an offer and in the chosen line, and nothing in the group is
    wider than the column. Held here in app.css, as the rules that do it:
    the list (.rsaoffers) in the column's flow -- not .qoffers, which lies
    over what is below it, where the group's own Clear and the next filter
    are -- with its offers' words free to shrink and wrap (min-width:0,
    overflow-wrap:anywhere), and the chosen line wrapping the same way; its
    Clear, a button in a sentence, no taller to the eye than the sentence's
    line: body.pg's 44px on a phone stood "Legislators · Read the law ·
    Clear" 14px below the rest, so the 44px is padding the margin takes back;
    and the list not printed, as the bill search's offers are not."""
    css = Path("src/pages/app.css")
    if not css.exists():
        return "skip", "app.css is not in this directory"
    rules = _css_rules(_source(css))
    flat = {" ".join(sel.split()): dict(_css_decls(body)) for ctx, sel, body, _ln in rules if not ctx}
    bad = []
    lst = flat.get(".rsaoffers", {})
    if not lst or lst.get("position") in ("absolute", "fixed"):
        bad.append(f".rsaoffers is not a list in the column's flow: {lst}")
    rn = flat.get(".rsaoffers .rn", {})
    if rn.get("min-width") != "0" or rn.get("overflow-wrap") != "anywhere":
        bad.append(f"an offer's words do not wrap inside the column: .rsaoffers .rn is {rn}")
    if flat.get(".frsa", {}).get("overflow-wrap") != "anywhere":
        bad.append(f"the chosen line does not wrap a long name: .frsa is {flat.get('.frsa')}")
    ln = flat.get(".frsa .link", {})
    pad = re.fullmatch(r"(var\(--sp-\d+\)) 0", ln.get("padding", ""))
    if ln.get("min-height") != "0" or not pad \
            or ln.get("margin") != f"calc(-1 * {pad.group(1)}) 0":
        bad.append(f"Clear in the chosen line is not 44px to a finger and a line tall to the eye: "
                   f".frsa .link is {ln}")
    printed = [sel for ctx, sel, body, _ln in rules if any("print" in c for c in ctx)
               and ".rsaoffers" in sel and dict(_css_decls(body)).get("display") == "none"]
    if not printed:
        bad.append("the Laws Changed offers are printed")
    assert not bad, "; ".join(bad)
    return "ok", ("the offers in the column's flow, a long name wrapping in an offer and in the chosen "
                  "line, Clear 44px without standing its line apart, and nothing of it printed")


# ---- one chip, in two sizes (the component plan's step 3, 9 October 2026) ---------
#
# The hooks a page places a chip by. Each is written beside .chip, by
# components.chip in either language, and none of them draws: the shape, the
# two sizes and the colours are the one chip's, in app.css.
_CHIP_HOOKS = ("cstat", "rcres", "calkind", "fkind", "sgn", "btv")
# What a chip's shape is made of. A rule that names a chip may move it, size
# its room under a narrow head or colour its family; it may not give it a
# corner, an edge, a shadow, a case or a spacing of its own -- which is how
# there came to be six shapes.
_CHIP_SHAPE = ("border", "border-left", "border-width", "border-style", "border-left-width",
               "border-left-style", "border-radius", "box-shadow", "text-transform",
               "letter-spacing", "outline")
_CHIP_SUBJECT = re.compile(r"\.(?:chip|chip-m|mchip|" + "|".join(_CHIP_HOOKS) + r")(?![\w-])")
# A chip written by hand in a builder or a script, rather than by chip(): a
# class attribute that starts with one of the chip's own classes. pchip's
# "mchip" and the Calendar's "wkchips" and "cpchip" are other names.
_CHIP_BY_HAND = re.compile(r"""class=\\?["'](?:[\w-]+[ ]+)*(?:chip|"""
                           + "|".join(_CHIP_HOOKS) + r""")(?![\w-])""")


def _chip_css_faults(css):
    """What in a stylesheet draws a chip other than the one chip: a list of
    sentences, empty where the one chip is all there is. Held: the frame,
    `.chip,.mchip`, and the two sizes, `.chip` at --t-sm and `.chip-m` at
    --t-ui, outside any media query (every page loads the one stylesheet, so
    where in it they sit is the cascade's business only); and no other rule
    whose subject is a chip -- .chip, .mchip or a hook -- sets any part of a
    chip's shape, nor a size but the two."""
    bad = []
    shared = {}
    for _at, sel, body, _ln in _css_rules(css):
        if not _at:
            shared.setdefault(tuple(_css_selectors(sel)), {}).update(dict(_css_decls(body)))
    frame = shared.get((".chip", ".mchip"))
    want = {"border": "1px solid var(--edge)", "border-left": "3px solid currentColor",
            "border-radius": "var(--r-in)"}
    if not frame:
        bad.append("no `.chip,.mchip` rule draws the one chip's frame")
    else:
        bad += [f"the frame's {k} is {frame.get(k)!r}, not {v!r}" for k, v in want.items()
                if frame.get(k) != v]
    for sel, size in (((".chip",), "var(--t-sm)"), ((".chip-m",), "var(--t-ui)")):
        got = (shared.get(sel) or {}).get("font-size")
        if got != size:
            bad.append(f"`{sel[0]}` is {got!r}, not {size}")
    for at, sel, body, ln in _css_rules(css):
        sels = _css_selectors(sel)
        if sels == [".chip", ".mchip"] and not at:
            continue
        chips = [s for s in sels if _CHIP_SUBJECT.search(re.split(r"[\s>+~]+", s)[-1])]
        if not chips:
            continue
        for k, v in _css_decls(body):
            # A reset is not a shape: the one chip sets its case and its
            # spacing back to none, whatever it is written inside.
            if k in _CHIP_SHAPE and v not in ("none", "0", "normal"):
                bad.append(f"line {ln}: `{chips[0]}` sets {k}:{v}, a part of the one chip's shape")
            elif k == "font-size" and v not in ("var(--t-sm)", "var(--t-ui)", "inherit") \
                    and not all(".mchip" in s for s in chips):
                bad.append(f"line {ln}: `{chips[0]}` sets font-size:{v}; a chip is S or M")
    return bad


def _chips_by_hand(text):
    """Every chip a script or a builder writes as markup of its own rather
    than by chip(): [(line, the class attribute)]."""
    return [(text.count("\n", 0, m.start()) + 1, m.group(0)) for m in _CHIP_BY_HAND.finditer(text)]


@check("frontend", "Cite this page carries the disclosure triangle where its pane has no pointer, "
       "turned down while open, and the record pages keep their pointer")
def _cite_triangle():
    """The owner, 10 November 2026: "Add triangle indicator to cite page
    button". The chevron "On this page" and the Learn folds use, after the
    words, a quarter turn when open; a record page's Cite button has the
    pane's nub (.racts, summary::after) instead, and the two would share
    one pseudo-element, so the chevron is not drawn there."""
    css = _source("src/pages/app.css")
    for rule in (".pcite:not(.racts .pcite) > summary::after{",
                 ".pcite:not(.racts .pcite)[open] > summary::after{transform:rotate(90deg)}",
                 ".racts :is(.pcite,.follow,.testify,.report) > summary::after{"):
        assert rule in css, f"app.css lacks {rule}"
    i = css.index(".pcite:not(.racts .pcite) > summary::after{")
    assert "mask:var(--l-chev)" in css[i:i + 600] and "M9 5.5l6.5 6.5L9 18.5" in css[i:i + 900], (
        "Cite's triangle is not the chevron the Learn folds use")
    return "ok", "the chevron after Cite this page off record pages, down when open; the nub kept on them"


@check("frontend", "every chip is the one chip: drawn by chip() in both languages, in one "
                   "frame and two sizes, and no rule or page draws one of its own")
def _chips_one_shape():
    """The component plan's step 3 (approved 9 October 2026): chips in one
    shape, and the person's rule of 22 September that every kind of chip
    shares the legislator chip's shape and placement.

    A bill's status, a meeting's kind, a vote's result, a party's letter,
    the sign-ins, the finder's kind and a version of the text were six
    shapes -- a box with a bar, a pill with an inset edge, a pine tint in
    capitals, a 13px outlined tag in capitals, a bare coloured word -- each
    written by its own line of markup in one of two languages. Held here:

    THE STYLESHEET (_chip_css_faults). The frame `.chip,.mchip` -- 3px
    corners, a 1px --edge, a 3px bar in currentColor -- and the two sizes;
    and no other rule naming a chip as its subject
    sets a corner, an edge, a shadow, a case, a spacing, or a size but S's
    and M's. So a pill, a box or capitals cannot come back on one chip.

    THE SOURCE. No builder or script in src/pages/ but the components
    writes a chip's class by hand: every chip is components.chip or
    components.js's chip(), whose answers _components_agree holds to one.

    THE FIXTURE SITE. Every element of every page built on the fixture
    that carries a chip's hook carries .chip, and no page carries a chip's
    hook alone.

    Each part is first shown the breaks it is there for -- a pill on the
    kinds of meeting, capitals on the version, the inset edge, a 13px tag,
    the frame gone, a status chip and a kind chip written by hand -- and
    must find every one, and must pass the person chip and the Calendar's
    own controls, which are other names."""
    css = _source("src/pages/app.css")
    planted = css + (".calkind{border-radius:var(--r-pill)}\n"
                     ".btv{text-transform:uppercase;letter-spacing:.04em}\n"
                     ".chip.k-hearing{box-shadow:inset 0 0 0 1px var(--cal-hear)}\n"
                     ".findout .fkind{font-size:var(--t-label)}\n")
    found = _chip_css_faults(planted)
    for what in ("`.calkind` sets border-radius", "`.btv` sets text-transform",
                 "`.btv` sets letter-spacing", "`.chip.k-hearing` sets box-shadow",
                 "`.findout .fkind` sets font-size:var(--t-label)"):
        assert any(what in f for f in found), f"the stylesheet's scan misses a planted break: {what}"
    assert any("frame" in f for f in _chip_css_faults(css.replace(".chip,.mchip{", ".chip{", 1))), (
        "the stylesheet's scan does not miss the frame when it is gone")
    sample = ('`<span class="cstat ${c}">${esc(w)}</span>` + \'<span class="calkind k-hearing">\''
              ' + `<span class="mchip p-R">` + \'<div class="wkchips">\' + \'<b class="cpchip">\''
              ' + `<span class="chip pt-${p}">`')
    hits = [h for _ln, h in _chips_by_hand(sample)]
    assert len(hits) == 3 and not any(x in " ".join(hits) for x in ("mchip", "wkchips", "cpchip")), (
        f"the scan for chips written by hand finds {hits}, where a status, a kind and a party's "
        "chip were planted and the person chip and the Calendar's controls are other names")

    bad = _chip_css_faults(css)
    for p in sorted(Path("src/pages").glob("*")):
        if p.suffix not in (".js", ".py", ".html") or p.stem == "components":
            continue
        for ln, h in _chips_by_hand(p.read_text(encoding="utf-8")):
            bad.append(f"{p.name} line {ln} writes a chip by hand ({h}...), not by chip()")

    shared, _base, _ran, _days = _fixture_site_shared()
    pages = chips = 0
    for page in sorted((shared / "site").rglob("*.html")):
        pages += 1
        for m in re.finditer(r'class="([^"]*)"', page.read_text(encoding="utf-8")):
            names = set(m.group(1).split())
            hooks = names & set(_CHIP_HOOKS)
            if hooks and "chip" not in names:
                bad.append(f"{page.relative_to(shared / 'site').as_posix()}: "
                           f"class=\"{m.group(1)}\" is a chip's hook without the chip")
            chips += "chip" in names
    assert not bad, f"{len(bad)} ways a chip is not the one chip: " + "; ".join(bad[:6])
    assert chips, "the fixture site carries no chip at all, so its pages held nothing here"
    return "ok", (f"the one chip's frame and two sizes, and no rule drawing a chip of "
                  f"its own; no chip written by hand in src/pages/; {chips:,} chips on "
                  f"{pages:,} fixture pages, each with its hook beside .chip; every planted "
                  "break found")


@check("frontend", "the print sheet's stylesheet keeps the site's rules: sizes in rem from the "
                   "scale, 13px only in capitals, every colour a token measured in both themes, and "
                   "on paper the sheet alone with its marks in line and stroke")
def _print_sheet_css():
    """print.css, held to what app.css is held to, since the checks of
    app.css do not read it: every font size in rem or a token of the type
    scale, none under 13px and 13px only where the rule sets capitals; every
    breakpoint in em; no colour written outside the palette; every pair of
    tokens drawn one on the other measured in both themes -- on the paper,
    the --sheet tokens, which are the same in every theme because paper has
    no dark mode, and app.css holds them so.

    ON PAPER: the page under the sheet, the sheet's heading and its settings
    are left off; an amendment's words are underlined and struck through,
    the law's own added words bold and italic, its removed words struck --
    never colour alone -- and print.js asks for the stylesheet by the name
    the build publishes it under.

    THE PAGE COUNT: what keeps together on paper keeps together in the frame
    print.js counts the pages in, the tables are tables there too, no narrow
    screen's rule reaches it, and its margins are @page's."""
    css_p, app_p = Path("src/pages/print.css"), Path("src/pages/app.css")
    if not (css_p.exists() and app_p.exists()):
        return "skip", "print.css or app.css is not here"
    text, app = _source(css_p), _source(app_p)
    pal = _css_palette(app)
    light = pal["light"]
    bad, sizes, pairs = [], 0, 0
    sheet = ("--sheet", "--sheet-ink", "--sheet-ink-2", "--sheet-rule")
    for tk in sheet:
        if tk not in light or light.get(tk, "").lower() != pal["dark"].get(tk, "").lower():
            bad.append(f"{tk} is not in app.css's palette, the same in both themes")
    rules = _css_rules(text)
    for ctx, sel, body, ln in rules:
        ds = _css_decls(body)
        caps = any(k == "text-transform" and "uppercase" in v for k, v in ds)
        got = dict(ds)
        for k, v in ds:
            if k.startswith("--"):
                bad.append(f"print.css:{ln} defines {k}; a token belongs in app.css's palette")
            if _colour_literals(v) and k not in ("mask", "-webkit-mask"):
                bad.append(f"print.css:{ln} {sel[:40]} writes {k}: {', '.join(_colour_literals(v))}")
            for t in re.findall(r"var\(\s*(--[\w-]+)", v):
                if t not in light:
                    bad.append(f"print.css:{ln} uses {t}, which app.css does not define")
            size = _css_font_size(k, v)
            if size is None:
                continue
            sizes += 1
            px, how = _css_px(size, light)
            if px is None:
                bad.append(f"print.css:{ln} {sel[:40]} sets a size this cannot read: {size}")
            elif how in ("px", "pt") or re.search(r"\d(px|pt)\b", size):
                bad.append(f"print.css:{ln} {sel[:40]} sets text in {how}")
            elif px < _FLOOR_PX or (px < 14 and not caps):
                bad.append(f"print.css:{ln} {sel[:40]} is {px:g}px" + ("" if px < _FLOOR_PX else
                                                                       " in mixed case"))
        # The pairs: the paper's inks on the paper, the menu's on its card.
        ground = next((v for k, v in ds if k in ("background", "background-color")), "")
        g = re.fullmatch(r"var\((--[\w-]+)\)", ground.strip())
        on_paper = ".ps-paper" in sel or any(x.startswith("var(--sheet") for x in got.values())
        for k, v in ds:
            m = re.fullmatch(r"var\((--[\w-]+)\)", v.strip())
            if k == "color" and m:
                grounds = [g.group(1)] if g else (["--sheet"] if m.group(1).startswith("--sheet")
                                                  else ["--surface", "--paper"])
                need = 4.5
            elif (k.startswith("border") and k != "border-radius") or k in ("outline", "fill"):
                m = re.search(r"var\((--[\w-]+)\)", v)
                if not m or m.group(1) in ("--rule", "--rule-2", "--sheet-rule", "--sheet", "--shadow"):
                    continue
                grounds = ["--sheet"] if m.group(1).startswith("--sheet") else ["--surface", "--paper"]
                need = 3.0
            else:
                continue
            for gr in grounds:
                for scheme in ("light", "dark"):
                    a, b = _css_token_colour(m.group(1), pal[scheme]), _css_token_colour(gr, pal[scheme])
                    pairs += 1
                    if a is None or b is None:
                        bad.append(f"print.css:{ln} {m.group(1)} on {gr} cannot be measured in {scheme}")
                    elif _css_ratio(a, b) < need:
                        bad.append(f"print.css:{ln} {sel[:40]}: {m.group(1)} on {gr} is "
                                   f"{_css_ratio(a, b):.2f}:1 in {scheme}, under {need:g}")
        if on_paper and any(k == "color" and "var(--ink" in v for k, v in ds):
            bad.append(f"print.css:{ln} {sel[:40]} inks the paper with the theme's ink, which is light in the dark")
    for m in re.finditer(r"@media([^{]*)\{", re.sub(r"/\*.*?\*/", "", text, flags=re.S)):
        if re.search(r"(?:min|max)-width\s*:\s*[\d.]+px", m.group(1)):
            bad.append(f"@media{m.group(1).rstrip()} is in px")
    for m in re.finditer(r"font\s*:[^;}]*?(\d*\.?\d+)(px|pt)\b", text):
        bad.append(f"print.css sets a {m.group(1)}{m.group(2)} font, in {m.group(2)}")
    printing = [(sel, dict(_css_decls(body))) for ctx, sel, body, _ in rules
                if any(c.startswith("@media print") for c in ctx)]
    hidden = {s.strip() for sel, ds in printing if "none" in ds.get("display", "")
              for s in _css_selectors(sel)}
    for want in ("html.ps-open body > :not(.ps-layer)", ".ps-head", ".ps-menu"):
        if want not in hidden:
            bad.append(f"on paper {want} is not left off")
    marks = {sel: dict(_css_decls(body)) for ctx, sel, body, _ in rules if not ctx}
    for sel, prop, word in ((".ps-ins", "text-decoration", "underline"),
                            (".ps-del", "text-decoration", "line-through"),
                            (".ps-law-cut", "text-decoration", "line-through"),
                            (".ps-law-add", "font-style", "italic")):
        if word not in marks.get(sel, {}).get(prop, ""):
            bad.append(f"{sel} is not {word}: a change would be said by colour or not at all")
    js = _source("src/pages/print.js") if Path("src/pages/print.js").exists() else ""
    # THE PAGES ARE COUNTED AS PAPER BREAKS THEM (print.js countPages, the
    # person's "always list the full number of pages", 10 October 2026): the
    # sheet laid out again in a frame a page's width, in columns a page's
    # height. So what keeps together keeps together there as on paper, the
    # tables stay tables there as on paper, a narrow screen's rules stay on
    # the screen's sheet (the frame is a screen as narrow as a page), and the
    # margins print.js counts with are print.css's own.
    top = [(sel, dict(_css_decls(body))) for ctx, sel, body, _ in rules if not ctx]
    together = {s for sel, ds in top if "avoid" in ds.get("break-inside", "")
                for s in _css_selectors(sel)}
    for want in (".ps-table tr", ".ps-how tr", ".ps-facts tr", ".ps-amds li", ".ps-docs li"):
        if want not in together:
            bad.append(f"{want} keeps together on paper only, not in the frame the pages are counted in")
    if not any(".ps-measure .ps-paper table" in sel and ds.get("display") == "table" for sel, ds in top):
        bad.append("in the counting frame app.css makes the sheet's tables blocks, which on paper it does not")
    for ctx, sel, body, ln in rules:
        if any(c.startswith("@media screen") for c in ctx):
            for s in _css_selectors(sel):
                if not s.startswith(".ps-layer"):
                    bad.append(f"print.css:{ln} {s}: a narrow screen's rule reaching the counting frame")
    pm = re.search(r"@page\s*\{\s*margin:\s*([\d.]+)in\s+([\d.]+)in\s+([\d.]+)in", text)
    jm = re.search(r"const MARGIN=\{top:([\d.]+),side:([\d.]+),foot:([\d.]+)\}", js)
    if not pm or not jm or [float(x) for x in pm.groups()] != [float(x) for x in jm.groups()]:
        bad.append("print.js counts the pages with other margins than print.css's @page")
    if 'l.href="/print.css"' not in js:
        bad.append("print.js does not ask for /print.css, the name the build publishes it under")
    assert sizes > 40 and pairs > 40, f"only {sizes} sizes and {pairs} pairs were read in print.css"
    assert not bad, f"{len(bad)} findings: " + "; ".join(bad[:10])
    return "ok", (f"{sizes} sizes in rem, none under the floor and 13px only in capitals; "
                  f"{pairs} token pairs measured in both themes; on paper the sheet alone, its "
                  f"marks underlined, struck and italic; the pages counted as paper breaks them")


@check("frontend", "the header's five tabs are one row from 1008px, in the flow between the "
                   "wordmark and the controls, and a row of their own on a tablet")
def _nav_ladder():
    """Decisions 130 and 131 (8 October 2026): Search as its drawing at every
    width, and the tablet's tabs on a second row, always shown. With
    "Resources" 43px wider than "Learn", the strip centred on the bar from
    1100px wrapped "Resources" under the others at 1100 and stood 27px from
    the wordmark at 1200 and 1366 (measured in Chrome, 10 October 2026). Held
    in app.css, which every page loads: from 63em the strip
    is in the flow, one row, centred by its own auto margins with the theme
    button taking none; from 721 to 1007 it is a row of its own, five equal
    cells after the controls; Search shows its drawing alone, its word kept
    for a screen reader."""
    css = _source("src/pages/app.css").replace("\r\n", "\n")
    shared = css
    wide = _braced(shared, "@media (min-width:63em){")
    assert ".navtabs{position:static;transform:none;flex-wrap:nowrap;width:max-content;margin:0 auto}" \
        in wide and ".themer{margin-left:0}" in wide and "nav.top .in{position:static;flex-wrap:nowrap}" \
        in wide, "from 1008px the sections are not one row in the flow, centred between the wordmark and the controls"
    assert shared.index("@media (min-width:63em){") > shared.index("@media (min-width:68.75em){"), (
        "the strip centred on the bar comes after the rule that puts it in the flow, and wins")
    tab = _braced(shared, "@media (min-width:45.0625em) and (max-width:62.9375em){")
    assert ".navtabs{order:3;flex:1 0 100%;flex-wrap:nowrap" in tab \
        and "nav.top .navtabs a{flex:1 1 0;justify-content:center;min-height:44px" in tab, (
            "on a tablet the sections are not a row of their own in equal cells")
    assert ".findbtn span{position:absolute;width:1px;height:1px" in shared.split("@media")[0] \
        or re.search(r"\n\.findbtn span\{position:absolute;width:1px;height:1px", shared), (
            "Search shows its word above a phone's width")
    return "ok", ("one row from 1008px, in the flow; a row of equal cells from 721 to 1007; "
                  "Search its drawing at every width")


@check("frontend", "the bill search opens Status alone, puts a narrowed long list's "
                   "zeros last, and folds its filters behind the Filters button below 960px")
def _search_filters_5acd():
    """The person's feedback of 9 October 2026, item 2: 5a approved (Status
    and Bill Type open, Committee closed), 5b NOT approved (a ticked choice
    does not move first), 5c approved (once a search or a filter narrows the
    list, the options with bills before the greyed zeros), 5d approved (the
    Filters button below 960px, tablets too). Round two's questions 8a and 8b
    went as recommended: 5a inside the Filters panel too, and 5c on the long
    lists only, Status and Bill Type keeping their fixed orders.

    Read off app.js and app.css: the groups open at the start, at every
    width; zerosLast run in node on a narrowed and an unnarrowed list, a
    short list, and a ticked zero, which keeps its place among the zeros; and
    the stylesheet's 60em block, which puts the button first, the panel
    after it, and the panel away until it is opened."""
    js = _source("src/pages/app.js")
    css = _source("src/pages/app.css")
    m = re.search(r"const openGroups=new Set\((\[[^\]]*\])\);", js)
    # 12 October 2026: Status alone open; Bill Type folds with the rest.
    assert m and json.loads(m.group(1)) == ["status"], (
        f"the filter groups open at the start are {m.group(1) if m else 'not found'}, "
        "not Status alone")
    fn = re.search(r"const ZEROS_LAST=.*?\nfunction zerosLast\(key,vals,counts\)\{.*?\n\}", js, re.S)
    assert fn, "app.js has no zerosLast"
    assert "zerosLast(key,vals,counts)" in js and "i===order.rule?' fzero'" in js, (
        "the filter groups do not draw their options in zerosLast's order")
    node = shutil.which("node") or shutil.which("node.exe")
    if node:
        prog = ("let query='';const sel={committee:new Set(),topic:new Set(),sponsor:new Set(),"
                "status:new Set(),type:new Set(),voteday:new Set()};" + fn.group(0) + """
const V=["Alpha","Beta","Gamma","Delta"],C={Beta:3,Delta:1},out={};
out.plain=zerosLast("committee",V,C);
query="minimum wage";
out.narrowed=zerosLast("committee",V,C);
out.status=zerosLast("status",V,C);
query="";sel.committee.add("Gamma");
out.ticked=zerosLast("committee",V,C);
process.stdout.write(JSON.stringify(out));""")
        r = _run([node, "-e", prog], capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, "zerosLast would not run: " + (r.stderr or "")[-300:]
        got = json.loads(r.stdout)
        V_ = ["Alpha", "Beta", "Gamma", "Delta"]
        want = {"plain": {"vals": V_, "rule": -1},
                "narrowed": {"vals": ["Beta", "Delta", "Alpha", "Gamma"], "rule": 2},
                "status": {"vals": V_, "rule": -1},
                "ticked": {"vals": ["Beta", "Delta", "Alpha", "Gamma"], "rule": 2}}
        assert got == want, f"zerosLast gives {got}"
    block = re.search(r"@media \(max-width:59\.9375em\)\{(.*?)\n\}", css, re.S)
    assert block, "app.css has no block for the Filters button below 960px"
    body = block.group(1)
    for rule in (".ftoggle{order:1;display:flex", ".facets{order:2;", ".shell > main{order:3",
                 ".shell:not(.fopen) .facets{display:none}"):
        assert rule in body, f"below 960px the stylesheet has no {rule}"
    assert ".fopt.fzero{border-top:1px solid var(--rule)" in css, (
        "the first zero of a narrowed list has no rule above it")
    return "ok", ("Status open at the start, Bill Type folded; a narrowed long list's options with "
                  "bills first and a ticked zero in its place among the zeros; Status in its "
                  "fixed order; the Filters button and its panel below 960px")


@check("frontend", "the Calendar page lays out as a calendar: the month beside the schedule on a desktop, above it below 1024px, nothing wider than the page")
def _calendar_layout():
    """The layout the description asked for, held in the stylesheet.

    On a desktop the month sits in a left column that stays in view while the
    schedule scrolls -- one tall grid area, because sticky is clipped to its
    own area -- and below 1024px it goes above the schedule, compact and
    foldable, with the DOM order the reading order at every width. The week at
    a glance is Monday to Friday beside the month since 9 October 2026, a
    column a day in the schedule's own column, and the days stand one under
    another where that column is narrow; this sums a day's room for a
    committee's name against the narrowest two-column panel (1024px less the
    shell's sides, a scrollbar, the month's column at its narrowest and the
    gap). Until then it was a table of hours that scrolled in its own frame,
    and the rules below that held its chips and cells went with it. Every
    colour is a token, so the dark palette re-grounds all of it; and a
    heading here outranks what it heads.

    Added after the review of 24 September, from what a headless Chrome
    measured at 360px: the week's frame is positioned, so the hidden labels
    inside it are clipped by it instead of widening the page; the calendar's
    tables stay tables under the site's narrow-screen rule that makes every
    table a scrolling block; a kind chip in a column can shrink and wrap; a
    committee's name breaks between words first; and the selected week's
    band is at least 1.2:1 against the page in both themes.

    Added after the recheck of 25 September: a chip inside an OPENED card
    shrinks and wraps too, and a committee's name has room for
    "Administration" -- summed here from the column and the paddings -- and
    hyphenates a longer word rather than splitting it without a hyphen.

    And for the row of boxes that took the key's place the same day: it
    wraps rather than widening a phone's page; each box is its kind's colour,
    outlined when unticked and filled when ticked, with the tick in the
    card's ground; the checkbox itself is there, invisible over its label
    rather than removed, so a pointer, Space and a screen reader reach it;
    the box shows where focus is; and the row is hidden without script.
    """
    css = _source("src/pages/app.css")
    a = css.find("/* THE CALENDAR, AS A CALENDAR")
    assert a >= 0, "app.css has no calendar block"
    block = css[a:css.index("/* HOW THE DAY BEGAN.", a)]
    lit = re.findall(r"rgba?\(|hsla?\(|#[0-9a-fA-F]{3,8}\b", block)
    assert not lit, f"the calendar's rules carry literal colours {lit}; the dark theme cannot reach them"
    grid = _braced(block, ".calapp.on{")
    assert "display:grid" in grid and 'grid-template-areas:"side head" "side main"' in grid, (
        "on a desktop the month is not a column beside the heading and the schedule")
    side = re.search(r"grid-template-columns:clamp\((\d+)px,[^,]+,(\d+)px\)", grid)
    assert side, "the month's column has no width"
    side_min = int(side.group(1))
    sticky = _braced(block, ".calapp.on > .calside{")
    assert "position:sticky" in sticky and "overflow-y:auto" in sticky, (
        "the month does not stay in view while the schedule scrolls")
    narrow = _braced(block, "@media (max-width:63.9375em){")
    assert 'grid-template-areas:"head" "side" "main"' in narrow, "below 1024px the month is not above the schedule"
    assert ".calside.folded .cmgrid tbody tr:not(.cmsel){display:none}" in narrow, (
        "a folded month does not keep the selected week")
    assert ".calfold{display:none" in block and ".calfold{display:inline-flex" in narrow, (
        "the folds are offered where there is room for the month")
    hid = re.search(r"((?:\.[\w-]+\[hidden\],?\s*)+)\{display:none\}", block)
    hidden = set(re.findall(r"\.([\w-]+)\[hidden\]", hid.group(1))) if hid else set()
    assert {"calside", "calbar", "calreset", "cplist", "calpeek", "calcats", "calkey"} <= hidden, (
        "a hidden control with a display rule of its own would show without script: "
        f"only {sorted(hidden)} are held to display:none while hidden")
    # THE ROW OF BOXES (25 September 2026): the key and the filter at once.
    row = _braced(block, ".calcatrow{")
    assert "flex-wrap:wrap" in row, "the row of boxes does not wrap, and would widen a phone's page"
    label = _braced(block, ".calcat{")
    assert "min-height:32px" in label and "font-size:var(--t-ui)" in label, (
        f"a box's label is not a tap target at the interface's size: {label}")
    inp = _braced(block, ".calcat input{")
    assert "opacity:0" in inp and "width:100%" in inp and "height:100%" in inp and "display:none" not in inp, (
        "the checkbox is not left in the page over its label for a pointer, the keyboard and a "
        f"screen reader: {inp}")
    cbx = _braced(block, ".cbx{")
    assert "border:2px solid var(--cat)" in cbx and "background:var(--surface)" in cbx, (
        f"an unticked box is not its colour's outline: {cbx}")
    assert re.search(r"\.calcat input:checked \+ \.cbx\{background:var\(--cat\)\}", block), (
        "a ticked box is not filled with its colour")
    assert "border:solid var(--surface)" in _braced(block, ".cbx::after{"), (
        "the tick is not drawn in the card's ground, which is what holds 3:1 on every colour")
    assert re.search(r"\.calcat input:focus-visible \+ \.cbx\{outline:2px solid var\(--pine\)", block), (
        "a box does not show where the keyboard's focus is")
    # THE WEEK, MONDAY TO FRIDAY, BESIDE THE MONTH (9 October 2026): a column
    # a day in the schedule's own column, as many columns as days, which
    # stand one under another where the schedule is narrow -- by the width it
    # has (a container query), so a phone never scrolls sideways.
    week = _braced(block, ".wkweek{")
    assert "container-type:inline-size" in week, "the week does not stack by the width it has"
    days_ = _braced(block, ".wkdays{")
    assert "display:grid" in days_ and "grid-template-columns:repeat(var(--cols,5),minmax(0,1fr))" in days_, (
        f"the week is not a column a day, as many as the days: {days_}")
    stack = _braced(block, "@container (max-width:40em){")
    assert ".wkdays{grid-template-columns:minmax(0,1fr)}" in stack, (
        "the days do not stand one under another where the schedule is narrow")
    # ITS DAYS ARE THE CONTAINING BLOCK OF WHAT IS POSITIONED INSIDE THEM. The
    # day buttons carry a visually hidden label, position:absolute; with no
    # positioned ancestor it was placed against the page, and at 360px the
    # page scrolled sideways by 192px in the Week view.
    assert "position:relative" in _braced(block, ".wkcol{"), (
        "the week's days are not the containing block of their hidden labels")
    # AND THE MONTH STAYS A TABLE. The stylesheet makes every table a
    # scrolling block at 720px and below; the month then shrank to 26px days.
    assert re.search(r"@media \(max-width: ?45em\)\{[^@]*?\btable\{display:block", css), (
        "the narrow-screen table rule this answers has moved; recheck the calendar against it")
    keep = re.search(r"\.calapp table\{([^}]*)\}", block)
    assert keep and "display:table" in keep.group(1) and "overflow:visible" in keep.group(1), (
        "the month is made a scrolling block on a phone by the site's table rule")
    name = _braced(block, "\n.wkc{")
    assert "overflow-wrap:anywhere" not in name and "overflow-wrap:break-word" in name, (
        "a committee's name in the week breaks mid-word before it breaks between words, or not at all")
    # A LONG WORD FITS, OR IS HYPHENATED. "Administration" broke as
    # "Administratio / n" in the 89px a name had in the week's table; the
    # column and the paddings are summed here from the stylesheet itself, so
    # a padding put back narrows the name and fails this. 99px is the
    # estimate the old rule's comment gave, from a screenshot and not from the
    # font's metrics; a longer word is left to hyphens:auto, both spellings.
    assert "-webkit-hyphens:auto" in name and re.search(r"(?<!-)hyphens:auto", name), (
        f"a committee's name in the week is not hyphenated where it must break: {name}")
    sp = {int(k): int(v) for k, v in re.findall(r"--sp-(\d+):(\d+)px", css)}

    def px(v):
        v = v.strip()
        m_ = re.fullmatch(r"var\(--sp-(\d+)\)", v)
        return sp[int(m_.group(1))] if m_ else int(v.rstrip("px"))

    def sides(decl):
        """(right, left) of a padding shorthand of one to four values."""
        p = [px(x) for x in re.findall(r"var\([^)]*\)|\d+px|0", decl)]
        p = {1: p * 4, 2: p * 2, 3: p + p[1:2], 4: p}[len(p)]
        return p[1], p[3]
    go = _braced(block, ".wkgo{")
    bar = int(re.search(r"grid-template-columns:(\d+)px minmax\(0,1fr\)", go).group(1))
    gap = px(re.search(r"column-gap:([^;}]*)", go).group(1))
    pad = sum(sides(re.search(r"padding:([^;}]*)", go).group(1)))
    have = 1024 - 2 * 24 - 15 - side_min - 32 - 2
    col = (have - 2) // 5 - 1
    measure = col - bar - gap - pad
    assert measure >= 99, (
        f"a committee's name in the week has {measure}px at 1024 ({col}px a day, a {bar}px "
        f"bar, a {gap}px gap, {pad}px of padding): \"Administration\" needs about 99")
    # THE SELECTED WEEK IS A BAND A READER CAN SEE, in both themes: pine mixed
    # into the page. --pine-soft was about 1.0:1 against the light page.
    band = re.search(r"\.cmrow\.cmsel td\{background:color-mix\(in srgb,var\(--pine\) (\d+)%,var\(--paper\)\)\}", block)
    assert band, "the selected week's band is not pine mixed into the page"

    def _tok(name, nth):
        return re.findall(r"--" + name + r":(#[0-9A-Fa-f]{6})", css)[nth]

    def _lum(hexc):
        ch = [int(hexc[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    pct = int(band.group(1)) / 100
    for theme, nth in (("light", 0), ("dark", 1)):
        pine, paper = _tok("pine", nth), _tok("paper", nth)
        mix = "#" + "".join(f"{round(pct * int(pine[i:i + 2], 16) + (1 - pct) * int(paper[i:i + 2], 16)):02X}"
                            for i in (1, 3, 5))
        a_, b_ = sorted((_lum(mix), _lum(paper)))
        ratio = (b_ + 0.05) / (a_ + 0.05)
        assert ratio >= 1.2, f"the selected week's band is {ratio:.2f}:1 against the {theme} page"
    for rule, size in ((".cmtitle{", "--t-lead"), (".cfhead h2{", "--t-lead"),
                       (".calfs legend,.calside .wkfind{", "--t-ui"), (".pkd{", "--t-h3")):
        assert f"font-size:var({size})" in _braced(block, rule), f"{rule} is not set at {size}"
    assert "font-size:var(--t-ui)" in _braced(block, ".calchk{"), "the boxes are not at the interface size"
    # A day's heading outranks its entries: the interface's size over theirs.
    assert "font-size:var(--t-ui)" in _braced(block, ".wkdh{") and \
        all("font-size:var(--t-sm)" in _braced(block, r) for r in ("\n.wkt{", "\n.wkc{", "\n.wkn{")), (
        "a day's heading in the week does not outrank its entries")
    return "ok", (f"month beside the schedule and sticky, above it below 1024px; the week "
                  f"a column a day beside it, {col}px a day at 1024, stacked where it is "
                  f"narrow; a committee's name has {measure}px and hyphens; the month stays "
                  f"a table on a phone; tokens only")


_TEXT_BOX_TYPES = ("", "text", "search", "email", "url", "tel", "number", "password")


def _focus_outline(rules, chain):
    """(what the cascade draws round chain[0] while it has the keyboard's
    focus, or None where it draws nothing): its outline's (width, style,
    colour) with the selector and app.css line that set the style. Focused
    from a keyboard, a box matches :focus and :focus-visible both."""
    el = dict(chain[0], states={"focus", "focus-visible"})
    won = _css_won(rules, [el] + list(chain[1:]))
    style = won.get("outline-style", ("none", "", 0))
    width = won.get("outline-width", ("medium", "", 0))[0]
    colour = won.get("outline-color", ("currentcolor", "", 0))[0]
    if style[0] in ("none", "hidden") or re.fullmatch(r"0+(?:\.0+)?(?:px|em|rem)?", width) \
            or colour == "transparent":
        return None, style
    return (width, style[0], colour), style


@check("frontend", "every text box a page writes shows which one has the keyboard: app.css draws it an "
       "outline while focused, which forced colours keep")
def _text_box_focus_shows():
    """The accessibility sweep of the R1 preview (29 October 2026; WCAG
    2.4.7, focus visible): in forced colours the search boxes -- the home
    page's #hq, the bill search's #q, the Laws page's #rsq, the roster's
    #sq and /search's #resq -- showed no focus at all. Their :focus rules
    set outline:none and drew a soft ring in a box-shadow instead, and
    forced colours paint no shadow and give the border its system colour,
    so nothing said which box had the keyboard. They take the site's 2px
    pine outline now, as the How-to tab's box always did (.g-find
    input:focus), and an outline is what forced colours keep.

    Every text box of every page of the fixture's build is held -- an
    <input> of a text type and a <textarea>, in the elements it is written
    in -- and so is every one a script writes (find.js's header search, the
    town panel's, app.js's sponsor and RSA boxes, the follow form's email),
    whose ancestors this model does not know and takes as any. The cascade
    (_css_won, every screen rule of app.css, forced colours' among them)
    must leave each one, focused, an outline of a style other than none, a
    width other than 0 and a colour other than transparent: a rule that
    takes it away, ahead of the one that draws it, fails here."""
    shared, _base, _ran, _days = _fixture_site_shared()
    site = shared / "site"
    rules = _css_screen_rules(_source("src/pages/app.css"))

    def text_box(chain):
        el = chain[0]
        return el["tag"] == "textarea" or (
            el["tag"] == "input" and el["attrs"].get("type", "").lower() in _TEXT_BOX_TYPES)

    def sig(chain):
        return tuple((e["tag"], tuple(sorted(e["ids"])), tuple(sorted(e["classes"])),
                      e["attrs"].get("type", "")) for e in chain)

    boxes = {}
    pages = 0
    for f in sorted(site.rglob("*.html")):
        page = f.read_text(encoding="utf-8", errors="replace")
        if "<input" not in page and "<textarea" not in page:
            continue
        pages += 1
        found = []
        _html_walk(page, element=lambda chain: found.append(chain) if text_box(chain) else None)
        for chain in found:
            boxes.setdefault(sig(chain), (f.relative_to(site).as_posix(), chain))
    # A script's boxes: each <input> or <textarea> its markup writes, in
    # elements this model does not know (None: any).
    scripted = 0
    for name in ("app.js", "find.js", "components.js"):
        js = Path("src/pages", name).read_text(encoding="utf-8")
        for m in re.finditer(r"<(input|textarea)\b([^<>]*)>", js):
            found = []
            _html_walk(m.group(0).replace("\\", ""), element=found.append)
            if found and text_box(found[0]) and "website" not in found[0][0]["attrs"].get("name", ""):
                scripted += 1
                boxes.setdefault(sig(found[0]) + (name,), (name, found[0] + [None] * 8))
    want = {"hq", "q", "rsq", "sq", "resq"}
    seen = {i for _w, chain in boxes.values() for i in chain[0]["ids"]}
    assert want <= seen, (
        f"the fixture's build no longer writes the search boxes this check holds by name: "
        f"{sorted(want - seen)} not found in {pages} pages")
    bad, drawn = [], Counter()
    for where, chain in boxes.values():
        got, style = _focus_outline(rules, chain)
        el = chain[0]
        name = el["tag"] + "".join("#" + i for i in sorted(el["ids"])) \
            + "".join("." + c for c in sorted(el["classes"]))
        if got is None:
            bad.append(f"{name} on {where}: outline-style {style[0]}"
                       + (f" from {style[1]} (app.css line {style[2]})" if style[1] else " (nothing sets one)"))
        else:
            drawn[" ".join(got)] += 1
    assert not bad, (
        "a text box shows no focus: nothing says which box has the keyboard, and in forced colours a "
        "box-shadow or a border colour does not take its place (WCAG 2.4.7). Draw it the site's "
        "outline:2px solid var(--pine), as .g-find input:focus does: " + "; ".join(bad[:6]))
    return "ok", (f"{len(boxes)} kinds of text box ({pages} pages of the fixture's build, {scripted} written "
                  f"by a script), each with an outline while focused: "
                  + ", ".join(f"{k} ({n})" for k, n in drawn.most_common()))


@check("frontend", "a heading under a section on a guide, a Learn page and /data is smaller than the "
       "section's own: a step, a phase, a subsection at --t-read under the section's --t-h3")
def _subsections_under_sections():
    """The cohesion audit of 30 October 2026 (B-1, and I-1 for Learn and
    /data): a guide's "Step by Step" was 19px and each step's title under it
    20px, so the outline read upside down; Learn's and /data's subsections
    were the same 19px as their sections, so neither could be told from the
    other. A section heading there is --t-h3 in the serif; every h3 and h4
    the pages write under one is --t-read, which must stay the smaller."""
    css = _source("src/pages/app.css")
    size = {}
    for k in ("t-read", "t-h3"):
        m = re.search(rf"--{k}:([\d.]+)rem", css)
        size[k] = float(m.group(1)) if m else None
    bad = []
    if not (size["t-read"] and size["t-h3"] and size["t-read"] < size["t-h3"]):
        bad.append(f"--t-read ({size['t-read']}rem) is not smaller than --t-h3 ({size['t-h3']}rem)")
    sections = {".l-sech": "--t-h3", ".dpsech": "--t-h3"}
    under = (":is(.l-secb,.l-wide) > h3", ".l-phname", ".l-chart > h3", ".l-rh", ".l-tlh",
             ".l-body h3", ".g-sh", ".dph3")
    won = {}
    for at, sel, body, _l in _css_rules(css):
        if at:
            continue
        d = dict(_css_decls(body))
        # On the commas between selectors, not those inside :is( ).
        for part in (x.strip() for x in re.split(r",(?![^()]*\))", sel)):
            fs = d.get("font-size") or (re.search(r"var\(--t-[\w-]+\)", d.get("font", "")) or [None])[0]
            if fs:
                won[part] = fs
    for sel, tok in sections.items():
        if tok not in str(won.get(sel)):
            bad.append(f"{sel} is {won.get(sel)}, where a section here is {tok}")
    for sel in under:
        if "--t-read" not in str(won.get(sel)):
            bad.append(f"{sel} is {won.get(sel)}, not --t-read under its section")
    assert not bad, "; ".join(bad[:6])
    return "ok", f"{len(under)} kinds of heading at --t-read under sections at --t-h3"


@check("frontend", "the Learn and guide pages' index at the foot names its groups no smaller than its links")
def _learn_index_heads_outrank():
    """The accessibility sweep of 29 October 2026: the index of pages at the
    foot of every Learn page and guide (nav.l-all) headed its two groups at
    13px capitals over 16px links, against app.css's own rule that a
    heading reads no smaller than what it heads. The group's name is the
    size of its links now, as a footer column's head is."""
    css = _source("src/pages/app.css")
    tokens = {m.group(1): float(m.group(2)) for m in re.finditer(r"--(t-[\w-]+):([\d.]+)rem", css)}
    size = {}
    for at, sel, body, _l in _css_rules(css):
        if at:
            continue
        d = dict(_css_decls(body))
        tok = re.search(r"var\(--(t-[\w-]+)\)", d.get("font-size") or d.get("font", ""))
        for part in (x.strip() for x in re.split(r",(?![^()]*\))", sel)):
            if tok and part in (".l-all h3", ".l-all a"):
                size[part] = (tok.group(1), tokens.get(tok.group(1)))
    head, link = size.get(".l-all h3"), size.get(".l-all a")
    assert head and link and head[1] and link[1], f"nav.l-all's sizes not read: {size}"
    assert head[1] >= link[1], (f"nav.l-all heads its groups at --{head[0]} ({head[1] * 16:g}px) over links at "
                                f"--{link[0]} ({link[1] * 16:g}px)")
    return "ok", f"nav.l-all's group names at {head[1] * 16:g}px over links at {link[1] * 16:g}px"


@check("frontend", "every search box is the one box: white, 16px words, 44px tall, on the Bills page, a "
       "bill's page, a member's Votes, the Calendar, Officials, /search and the Laws page")
def _one_search_box():
    """The cohesion audit of 30 October 2026 (I-7): the Bills box was 42px on
    the page's grey, a member's Votes box was grey-filled where the rest were
    white, and the Officials and /search boxes were 20px words in a 52px box.
    One box now: --surface, --t-ui, 44px (a height, or a least height where
    the box is a row's), and the Bills page's term menu beside it the same
    height. Each rule is read as the cascade has it."""
    css = _source("src/pages/app.css")
    won = {}
    for at, sel, body, _l in _css_rules(css):
        if at:
            continue
        for part in (x.strip() for x in re.split(r",(?![^()]*\))", sel)):
            won.setdefault(part, {}).update(dict(_css_decls(body)))
    boxes = ("#q", "#rsq", ".bfilt input[type=search]", ":where(body.pg) input[type=search]",
             ":where(body.pg) .lfind input[type=search]", ":where(body.pg) .resfind input[type=search]",
             ".wkfind input")
    bad = []
    for b in boxes:
        d = won.get(b, {})
        h = d.get("height") or d.get("min-height")
        if h != "44px":
            bad.append(f"{b} is {h} tall, not 44px")
        if d.get("font-size") != "var(--t-ui)":
            bad.append(f"{b}'s words are {d.get('font-size')}, not --t-ui")
        # A box that names no ground takes the general box's white.
        ground = d.get("background") or d.get("background-color")
        if ground not in (None, "var(--surface)"):
            bad.append(f"{b} stands on {ground}, not white (--surface)")
    if won.get(":where(body.pg) input[type=search]", {}).get("background") != "var(--surface)":
        bad.append("the general box is not white, so the boxes that name no ground are not either")
    if won.get(".bfilt input[type=search]", {}).get("background") != "var(--surface)":
        bad.append("a member's Votes box is not white")
    if won.get("#year", {}).get("height") != "44px":
        bad.append(f"the Bills page's term menu is {won.get('#year', {}).get('height')} beside a 44px box")
    assert not bad, "; ".join(bad[:6])
    return "ok", f"{len(boxes)} search boxes white, 16px and 44px, and the term menu beside the Bills box"


@check("frontend", "every control that switches a view marks the chosen one the same way: solid pine, "
       "its words in --on-pine, filled with Highlight in forced colours")
def _switches_one_look():
    """The cohesion audit of 30 October 2026 (I-6): Officials showed a solid
    pine "selected" in its roster switch and a pale one in its map's, on the
    same page; the Calendar put round pills ("Both chambers / House /
    Senate") beside its square List / Week / Day; a bill's versions and
    "What changed / Full text" were pale too. One look now: the chosen one
    solid pine with its words in --on-pine, the group edged and square, and,
    where forced colours take the ground away, an outline in Highlight."""
    rules = []
    for f in ("src/pages/app.css", "src/pages/map.css"):
        rules += [(f, at, sel, dict(_css_decls(b))) for at, sel, b, _l in
                  _css_rules(Path(f).read_text(encoding="utf-8"))]
    chosen = {".calviews button[aria-pressed=\"true\"]": None, ".wkchips button[aria-pressed=\"true\"]": None,
              ":where(body.pg) .rtabs [role=tab][aria-selected=true]": None, ".vbtn.sel": None,
              ".vtog.sel": None, ".gm .gmseg label:has(input:checked)": None}
    bad, outlined = [], set()
    for f, at, sel, d in rules:
        for part in (x.strip() for x in sel.split(",")):
            if part in chosen and not at:
                chosen[part] = {**(chosen[part] or {}), **d}
            if any("forced-colors" in a for a in at) and d.get("background") == "Highlight":
                outlined.add(part.replace(":where(body.pg) ", ""))
    for part, d in chosen.items():
        if not d:
            bad.append(f"no rule draws the chosen {part}")
            continue
        ground = d.get("background", d.get("background-color", ""))
        if "var(--pine)" not in ground or d.get("color") != "var(--on-pine)":
            bad.append(f"{part} is {ground or 'no ground'} with {d.get('color')} words, not solid pine and --on-pine")
        if part != ".gm .gmseg label:has(input:checked)" and part.replace(":where(body.pg) ", "") not in outlined:
            bad.append(f"{part} is not filled with Highlight in forced colours, where its ground is the system's")
    for f, at, sel, d in rules:
        if "999px" in d.get("border-radius", "") and any(k in sel for k in (".wkchips", ".vtog", ".calviews")):
            bad.append(f"{f}: {sel} is round again")
    assert not bad, "; ".join(bad[:6])
    return "ok", f"{len(chosen)} switches mark the chosen one solid pine, and outline it in forced colours"


@check("frontend", "a glossary term's button is a 24px target at the least, without moving a letter: "
       "a bill's suffix, the \"A\" of HB 1-A, is no 12px sliver")
def _term_button_24():
    """The cohesion audit of 30 October 2026, B-6 (WCAG 2.5.8): a bill's
    suffix is a glossary term of its own, a letter beside the bill's number,
    and its button measured 12 by 30px on Learn and 18 by 31px on a 1995
    bill at 390: a tap beside the letter missed. The words are not a
    sentence, so the sentence exception does not cover them.

    The box a tap lands in grows, not the word: a transparent ::after, laid
    over the button's middle, at least 24px each way, on a button positioned
    to hold it. Measured on the preview at 390: a tap 11px left, right,
    above and below the "A" lands on it in all four, against two before, and
    every button's own box is the size it was."""
    css = _source("src/pages/app.css")
    rules = _css_rules(css)
    won = {}
    for at, sel, body, _l in rules:
        if at:
            continue
        for part in (x.strip() for x in sel.split(",")):
            if part in (".term .termbtn", ".term .termbtn::after"):
                won.setdefault(part, {}).update(dict(_css_decls(body)))
    btn, hit = won.get(".term .termbtn", {}), won.get(".term .termbtn::after", {})
    bad = []
    if btn.get("position") != "relative":
        bad.append("the button is not positioned, so its ::after measures from somewhere else")
    if hit.get("content") not in ('""', "''") or hit.get("position") != "absolute":
        bad.append(f"no transparent ::after box over the button: {hit}")
    for k in ("width", "height"):
        if "".join(hit.get(k, "").split()) != "max(100%,24px)":
            bad.append(f"the ::after box's {k} is {hit.get(k)!r}, where max(100%,24px) keeps it 24px at the least")
    if any(k in hit for k in ("background", "background-color", "border", "outline")):
        bad.append("the ::after box is drawn, where it must be a target only")
    if any(k in btn for k in ("padding", "padding-inline", "padding-left", "padding-right", "width")) or \
            btn.get("min-width") not in (None, "0"):
        bad.append("the button grows itself, which moves the letters beside it")
    assert not bad, "; ".join(bad)
    return "ok", "a term's button holds a 24px transparent target over its word; the word is the size it was"


@check("frontend", "a head's action pane opens from its own button with a nub pointing at it: on a desktop "
                   "to its left, level with it; on a phone under it, as wide as the row")
def _panes_open_left():
    """The owner, 6 November 2026: a pane hung from the actions' foot read as
    disconnected from the button that opened it. Each of Cite, Testify,
    Follow and Report a problem in a head's actions (.racts) is what its pane
    is measured from, at every width -- Testify's details by name, since it
    sits in a box of its own (mountTestify). Above a phone's width (the
    actions the head's right-hand column) the pane opens to the button's
    left, top level with it, its width the window less the column and the
    gutters; at 45em and under (two buttons to a row) under the button, as
    wide as the row, where app.js placeActPane says the row is. And a nub
    connects them (the owner's second word the same day): the open button's
    ::after, a square of the pane's surface and border turned 45deg, laid on
    the pane's edge at the button's middle -- the right edge on a desktop,
    the top on a phone -- its tip short of the button: the gap (12px) is
    more than half the turned square's diagonal (14px / 2 * 1.414 = 9.9px).
    Measured in a browser at 360, 390, 1024 and 1280, light and dark, on a
    bill and a session day (the branch's notes)."""
    css = Path(_paths.locate("app.css")).read_text(encoding="utf-8")
    js = Path(_paths.locate("app.js")).read_text(encoding="utf-8")
    # the nub in px, as the gap is: in rem a large default text grew it into
    # the button (the review of 6 November 2026)
    shared = ".racts :is(.pcite,.follow,.testify,.report){position:relative;--nub:14px}"
    assert shared in css, "a head's pane is not measured from its own button, or its nub has no size in px"
    # drawn turned and hidden, shown while open: nothing turns as it opens,
    # so the openers' check does not take it for an opener's mark
    nub = re.search(r"\.racts :is\(\.pcite,\.follow,\.testify,\.report\) > summary::after\{([^}]*)\}", css)
    assert nub and all(x in nub.group(1) for x in (
            'content:""', "display:none", "position:absolute", "background:var(--surface)",
            "solid var(--rule-2)", "rotate(45deg)", "pointer-events:none", "z-index:21")), (
        f"the nub is not the pane's own fill and border, turned, over the pane: {nub and nub.group(1)!r}")
    assert ".racts :is(.pcite,.follow,.testify,.report)[open] > summary::after{display:block}" in css, (
        "the nub is not shown while its pane is open")
    pane = re.search(r"\.followpane,\.citebody,\.testifypane\{position:absolute;[^}]*\}", css)
    assert pane and "background:var(--surface)" in pane.group(0) and "border:1px solid var(--rule-2)" in pane.group(0) \
        and "z-index:20" in pane.group(0), "the pane's fill, border or layer no longer match the nub's"
    sp5 = re.search(r"--sp-5:(\d+)px", css)
    assert sp5 and int(sp5.group(1)) > 14 / 2 * 2 ** .5, "the nub's tip would reach the button"

    def block(media):
        got = [b for b in re.findall(re.escape(media) + r"\{\n(.*?)\n\}", css, re.S)
               if ".racts :is(.followpane" in b]
        assert len(got) == 1, f"{len(got)} rules at {media} place the head's panes, not one"
        return got[0]
    desk, phone = block("@media (min-width:45.0625em)"), block("@media (max-width:45em)")
    pane_of = lambda b: re.search(
        r"\.racts :is\(\.followpane,\.citebody,\.testifypane\),\.racts \.report > \.reportform\{([^}]*)\}", b)
    nub_of = lambda b: re.search(r"\[open\] > summary::after\{([^}]*)\}", b)
    d, dn = pane_of(desk), nub_of(desk)
    assert d and "top:0" in d.group(1) and re.search(r"right:calc\(100% \+ var\(--sp-5\)\)", d.group(1)) \
        and "left:auto" in d.group(1), f"on a desktop a pane does not open to its button's left: {d and d.group(1)!r}"
    assert dn and "top:calc(50% - var(--nub) / 2)" in dn.group(1) \
        and "left:calc(-1 * var(--sp-5) - var(--nub) / 2)" in dn.group(1) \
        and "border-top-width:1px;border-right-width:1px" in dn.group(1), (
        f"on a desktop the nub is not on the pane's right edge at the button's middle: {dn and dn.group(1)!r}")
    p, pn = pane_of(phone), nub_of(phone)
    assert p and "top:calc(100% + var(--sp-5))" in p.group(1) and "left:var(--pl,0)" in p.group(1) \
        and "width:var(--pw," in p.group(1), f"on a phone a pane does not open under its button: {p and p.group(1)!r}"
    # from the lifted button's padding box, inside its 1px border
    assert pn and "top:calc(100% + 1px + var(--sp-5) - var(--nub) / 2)" in pn.group(1) \
        and "left:calc(50% - var(--nub) / 2)" in pn.group(1) \
        and "border-top-width:1px;border-left-width:1px" in pn.group(1), (
        f"on a phone the nub is not on the pane's top edge at the button's middle: {pn and pn.group(1)!r}")
    # on a phone the pressed button stands above the band of ground over the
    # gap, so the band does not cut its focus ring (the review of 6 November)
    assert ".racts :is(.pcite,.follow,.testify,.report)[open] > summary{position:relative;z-index:22}" in phone, (
        "on a phone the band over the gap cuts the pressed button's focus ring")
    # A short pane covers the buttons it lies on, down to the actions' foot
    # (the owner's follow-up of 6 November: the foot of Report a problem
    # showed under Testify's one sentence, 8px at 390)
    assert "min-height:calc(var(--pdown,0px) - var(--sp-5))" in p.group(1), (
        "on a phone a short pane leaves the foot of the buttons under it showing")
    # and forced colours, which take the pane's shadow and the band with it,
    # get the band from the open button instead, in the mode's own ground
    band = re.search(r"@media \(forced-colors:active\)\{\s*\.racts :is\(\.pcite,\.follow,\.testify,\.report\)"
                     r"\[open\] > summary::before\{([^}]*)\}", phone)
    assert band and all(x in band.group(1) for x in (
            'content:""', "position:absolute", "left:var(--bl,0)", "var(--bt,100%)", "width:var(--pw,100%)",
            "height:10px", "forced-color-adjust:none", "background:Canvas", "pointer-events:none")), (
        f"in forced colours on a phone nothing covers the next row's tops in the gap: {band and band.group(1)!r}")
    # in forced colours, the nub in the pane's own system colours
    assert re.search(r"@media \(forced-colors:active\)\{\s*\.racts :is\(\.pcite,\.follow,\.testify,\.report\) > "
                     r"summary::after\{forced-color-adjust:none;\s*background:Canvas;border-color:CanvasText\}", css), (
        "in forced colours the nub takes the button's colours, not the pane's")
    # where the row is, said by the script as the pane opens: on the press,
    # on the toggle and when the window changes; and nothing else -- it opens,
    # shuts and focuses nothing
    fn = js[js.index("function placeActPane("):]
    fn = fn[:fn.index("\n}\n")]
    assert all(f'"--{v}"' in fn for v in ("pl", "pw", "pdown", "bl", "bt")) \
        and not re.search(r"open|focus|click", fn), (
        "placeActPane does more than say where the row, the actions' foot and the button are, or not all of it")
    for hook in ('e.target.closest(".racts details > summary");\n  if(s)placeActPane(s.parentElement);\n},true);',
                 'document.addEventListener("toggle",e=>{if(e.target&&e.target.open)placeActPane(e.target);},true);',
                 'window.addEventListener("resize",()=>document.querySelectorAll(".racts details[open]").forEach(placeActPane));'):
        assert hook in js, f"placeActPane is no longer called where it was: {hook[:60]!r}"
    # THE CASCADE, not only the text (the review of 6 November 2026): two
    # rules of the same weight put these buttons back to position:static,
    # and only their place in the file lets the new one win.
    at = css.index(shared)
    for older in (".pageacts .follow,.pageacts .testify{position:static}", ".racts .report{position:static}"):
        assert older in css and css.index(older) < at, (
            f"{older!r} now comes after the rule that measures a pane from its button, and wins")
    return "ok", ("each pane from its own button: to its left and level above 45em, under it and as wide as the "
                  "row at 45em and under; a nub of its own fill and border on its edge at the button's middle, "
                  "clear of the button")


@check("frontend", "a record head's facts follow its line, however tall the actions beside them")
def _head_facts_follow_line():
    """The cohesion audit's P-2: on a bill at 1280 PRIME SPONSOR stood 110px
    under the title where a member's facts stand 74px under theirs -- about
    90px of empty band, set by the actions' height. The actions span the line
    and facts rows, and a grid shares a spanning item's extra height among
    the rows it spans, so a column of five buttons stretched both. An empty
    1fr row under the facts, spanned by the actions too, takes it all: an
    item crossing a flexible row grows that row alone. Measured after in a
    browser: 53px on a bill, a member and a session day, at 1280 and 1024,
    and the rail where it was. On a phone the head is one column and the
    rows are the content's own."""
    css = Path(_paths.locate("app.css")).read_text(encoding="utf-8")
    head = re.search(r"\n\.rhead\{([^}]*)\}", css)
    assert head, "app.css has no .rhead rule"
    areas = re.search(r"grid-template-areas:([^;}]*)", head.group(1))
    rows = re.search(r"grid-template-rows:([^;}]*)", head.group(1))
    names = re.findall(r'"([^"]*)"', areas.group(1)) if areas else []
    assert names == ["trail trail", "top top", "line acts", "facts acts", ". acts", "rail rail"], (
        f"the head's areas no longer put an empty row under the facts beside the actions: {names}")
    assert rows and rows.group(1).split() == ["auto", "auto", "auto", "auto", "1fr", "auto"], (
        "the empty row under the facts is not the head's one flexible row, so the actions' height "
        f"stretches the line and the facts again: {rows and rows.group(1)!r}")
    phone = re.search(r"@media \(max-width:45em\)\{\n  \.rhead\{([^}]*)\}", css)
    assert phone and '"trail" "top" "line" "facts" "rail" "acts"' in phone.group(1) \
        and "grid-template-rows:none" in phone.group(1), (
        "on a phone the head keeps the desktop's six rows, one of them flexible, under one column")
    return "ok", "the actions' extra height goes to an empty row under the facts; on a phone, one column"


@check("frontend", "the House seating chart prints whole, whatever the zoom on the screen it was loaded on")
def _seat_chart_prints_whole():
    """The chart's width is the zoom's, written on the <svg> by the seat
    script, and a reader may have zoomed in (a screen under 1100px opened
    zoomed in until 29 October 2026). A page
    printed after loading there kept that width inside a box that scrolls and
    clips, and the sheet lost the right of the floor, which since the turn is
    Division 5 and its caption (the review of 7 October 2026).

    Held on app.css: a print block, after the box's own rule so that it wins
    at the same weight, sets the chart to the page's width over the script's
    inline width -- which only !important does -- and lets the box neither
    clip nor stop at 78vh."""
    css = re.sub(r"/\*.*?\*/", "", _source("src/pages/app.css"), flags=re.S)
    box = css.find(":where(body.pg) .seatwrap{")
    assert box >= 0, "app.css has no rule for the chart's box"
    blocks = [(m.start(), m.group(1)) for m in re.finditer(
        r"@media print\{((?:[^{}]*\{[^{}]*\})*)\s*\}", css)]
    held = [(at, body) for at, body in blocks
            if re.search(r"(?:^|\})\s*(?::where\(body\.pg\) )?\.seatmap\{width:100% !important\}", body)]
    assert held, ("on paper the chart keeps the width the screen's zoom wrote on it, and its "
                  "box clips the floor")
    at, body = held[-1]
    assert at > box, "the print rule for the chart comes before the box's own rule, which wins"
    wrap = re.search(r"(?:^|\})\s*(?::where\(body\.pg\) )?\.seatwrap\{([^}]*)\}", body)
    assert wrap and "overflow:visible" in wrap.group(1) and "max-height:none" in wrap.group(1), (
        "on paper the chart's box still scrolls, clips or stops at 78vh")
    return "ok", "printed, the chart is the page's width and its box neither clips nor scrolls"


_GRID_FIRST = {"1", "auto", "1/-1", "1/2", "1/auto", "span1", "1/span1"}


def _grid_one_track(v):
    """Whether a grid-template-columns value is one column: minmax(0,1fr) is,
    7.5rem minmax(0,1fr) is not, and repeat(n, ...) is one only for n = 1."""
    v = re.sub(r"repeat\(\s*1\s*,", "(", v)
    if "repeat(" in v:
        return False
    depth, n, tok = 0, 0, False
    for ch in v:
        depth += (ch == "(") - (ch == ")")
        if ch.isspace() and depth == 0:
            tok = False
        elif not tok:
            n, tok = n + 1, True
    return n == 1


def _grid_column(body):
    v = next((v for k, v in reversed(_css_decls(body))
              if k in ("grid-column", "grid-column-start")), None)
    return None if v is None else "".join(v.split())


def _phone_grid_strays(css):
    """[(grid, child, its column, the @media, line)] for every child of a grid
    that a max-width @media makes one column, which a rule elsewhere puts in
    a later column and nothing in that @media puts back in the first. Such a
    child makes a second, implicit column that takes the width it wants; the
    one column the @media meant shrinks to nothing, and its text runs under
    the child's."""
    rules = _css_rules(css)
    out = []
    for at, sel, body, _ in rules:
        if not any(a.startswith("@media") and "max-width" in a for a in at):
            continue
        tpl = next((v for k, v in reversed(_css_decls(body)) if k == "grid-template-columns"), None)
        if tpl is None or not _grid_one_track(tpl):
            continue
        for g in _css_selectors(sel):
            for at2, sel2, body2, line2 in rules:
                c = _grid_column(body2)
                if at2 == at or c is None or c in _GRID_FIRST:
                    continue
                for s in _css_selectors(sel2):
                    if not s.startswith(g + " "):
                        continue
                    back = [_grid_column(b3) for a3, s3, b3, _ in rules
                            if a3 == at and s in _css_selectors(s3)]
                    if not any(x in _GRID_FIRST for x in back if x):
                        out.append((g, s, c, at[-1], line2))
    return out


@check("frontend", "a bill card in a list draws the rail with more weight, as a bill's own "
                   "page does")
def _rail_weight_on_cards():
    """"The rail visuals were updated on the full bill page but not on the
    bill cards" (the person, 18 October 2026). The rail with more weight
    (choice A, 14 October) was scoped to an opened card and a bill's own
    page, so a list's cards kept thin grey lines and small dots. Each of
    its rules must reach a card that is not opened."""
    css = _source("src/pages/app.css")
    weighted = [sel for at, sel, body, _ in _css_rules(css)
                if ".rail.dated .stop" in sel and not at
                and any((k, v) in (("background", "var(--st-law)"), ("width", "1.25rem"))
                        for k, v in _css_decls(body))]
    assert len(weighted) >= 2, "the rail with more weight is not in app.css, so this reads nothing"
    narrow = [sel for sel in weighted if ".card.focus" in sel or ".card" not in sel]
    assert not narrow, ("the rail with more weight reaches only an opened card or a bill's "
                        "own page: " + "; ".join(narrow))
    return "ok", f"all {len(weighted)} rules of the rail with more weight reach a card in a list"


@check("frontend", "a grid that drops to one column on a phone leaves none of its parts in a "
                   "second column")
def _phone_grid_one_column():
    """"On mobile, the documents tab has overlapping text" (the person,
    16 October 2026). A calendar's or a journal's row is a grid of the day
    beside the citation and what happened; on a phone the @media made it one
    column and moved the day above the citation, but the citation and the
    plain words kept the wide layout's grid-column:2. That made a second
    column which took the whole width, the day's column shrank to nothing,
    and the date ran under the words. Read for every grid in the
    stylesheets, not for that one: the same three lines in another rule
    would draw the same overlap."""
    broken = (".g .row{display:grid;grid-template-columns:7rem minmax(0,1fr)}"
              ".g .row > a{grid-column:2}"
              "@media (max-width:45em){.g .row{grid-template-columns:minmax(0,1fr)}}")
    assert _phone_grid_strays(broken), "the check cannot see a child left in a second column"
    assert not _phone_grid_strays(broken[:-1] + ".g .row > a{grid-column:1}}"), (
        "the check flags a child that the @media puts back in the first column")
    bad, grids = [], 0
    for name in ("app.css", "map.css"):
        css = Path("src/pages", name).read_text(encoding="utf-8")
        bad += [f"{name}:{line} {child} keeps grid-column:{col} where {media} makes {grid} "
                f"one column" for grid, child, col, media, line in _phone_grid_strays(css)]
        grids += sum(1 for at, _, body, _ in _css_rules(css)
                     if any(a.startswith("@media") and "max-width" in a for a in at)
                     and any(k == "grid-template-columns" and _grid_one_track(v)
                             for k, v in _css_decls(body)))
    assert grids, "no grid is made one column on a phone, so this check reads nothing"
    assert not bad, "a phone's one-column grid has a part in a second column: " + "; ".join(bad)
    return "ok", f"{grids} grid rules made one column on a phone keep every part in it"


@check("frontend", "a committee's Videos tab is a still and its playlist: the newest chosen, nothing "
                   "from YouTube before Play, a moment the Meetings tab's own button, no bill line "
                   "where none is known, and a tab only where there is a recording")
def _committee_videos_tab():
    """The owner, 26 October 2026, and the manager's review of the design the
    same day (app.js, THE VIDEOS VIEW): the tab is "Videos" with the count
    chip Bills and Meetings carry; the kinds are the Meetings tab's chips;
    a recording the docket ties no bill to has no bill line, and the detail
    says so once, in muted text; a start or a length the index lacks is left
    out with its separator; one caption under the player; every row drawn
    (on a phone the list scrolls under the player, _videos_phone_playlist);
    the chosen row aria-current. Drawn by renderPage in node over a
    committee like the fixture's."""
    items = lambda vid, kind, start, state: [{
        "bill": "HB1442", "n": "HB 1442-FN", "title": "relative to insurance coverage", "year": 2026,
        "term": "2025-2026", "kind": kind, "video_id": vid, "start": start, "state": state,
        "time": "10:00", "venue": "LOB 302"}]
    sess = lambda date, its, kinds: {"date": date, "term": "2025-2026",
                                     "video_id": its[0]["video_id"], "items": its,
                                     "outcomes": [{"bill": "HB1442", "kinds": kinds, "outcome": "heard"}]}
    rec = lambda i, d, **k: dict({"id": i, "date": d, "term": "2025-2026"}, **k)
    cmte = {"code": "H43", "name": "Commerce", "chamber": "H", "bills": {"2025-2026": []},
            "sessions": [sess("2026-02-17", items("", "work session", None, "candidates"), ["work session"]),
                         sess("2026-02-10", items("VID4", "executive session", 300, "stated"),
                              ["executive session"]),
                         sess("2026-02-03", items("VID1", "public hearing", 150.0, "located"),
                              ["public hearing"])],
            "recordings": [rec("-titleOnly1", "2026-02-24", seconds=2170),
                           rec("divOne", "2026-02-17", began="13:00", seconds=7200, label="Division I"),
                           rec("VID4", "2026-02-10", began="12:58", seconds=2700),
                           rec("VID1", "2026-02-03", began="09:58", seconds=6723)]}
    many = dict(cmte, code="H34", recordings=[rec(f"m{i:02d}", f"2026-03-{i:02d}") for i in range(1, 26)])
    later = dict(cmte, code="H05", bills={"2017-2018": [], "2021-2022": []}, sessions=[],
                 recordings=[rec("late1", "2021-03-01", term="2021-2022")])
    none = dict(cmte, code="H01", recordings=[])
    harness = _HEARD_PRELUDE + r"""
load("renderPage, recordTerms, jumpButtons, setPage: (p) => { PAGE = p; }, getPage: () => PAGE,"
  + " setTab: (t) => { PAGE_TAB = t; }, getTab: () => PAGE_TAB, setUp: (u) => { UPCOMING = u; }");
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
const results = document.querySelector("#results");
const draw = (c, tab, extra) => {
  const terms = s.recordTerms("committee", c);
  s.setPage(Object.assign({kind: "committee", data: c, terms, term: terms[0], status: "",
    vfilter: "", vshow: 0, bshow: 0, mshow: 0, vid: ""}, extra || {}));
  s.setTab(tab); s.renderPage(); return results.innerHTML; };
const out = {};
try {
  s.setUp([]);
  out.videos = draw(fx.cmte, 2);
  out.vid1 = draw(fx.cmte, 2, {vid: "VID1"});
  out.div = draw(fx.cmte, 2, {vid: "divOne"});
  out.meetings = draw(fx.cmte, 1);
  out.many = draw(fx.many, 2);
  out.later = draw(fx.later, 2, {term: "2017-2018"});
  out.none = draw(fx.none, 2); out.noneTab = s.getTab();
  // HB 1157-FN's two moments of 3 February 2026, the first inferred.
  out.jumps = s.jumpButtons([{start: 9835, state: "located", kind: "full committee work session"},
                             {start: 9960, state: "stated", kind: "executive session"}], () => "p1");
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + e.stack; }
process.stdout.write("\n@@" + JSON.stringify(out));
"""
    got = _node_app(harness, {"fx.json": json.dumps({"cmte": cmte, "many": many, "later": later,
                                                     "none": none})})
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert "threw" not in got, "the Videos tab would not draw: " + got.get("threw", "")[:400]
    flat = {k: re.sub(r"[ \t\r\n]+", " ", v) if isinstance(v, str) else v for k, v in got.items()}
    v = flat["videos"]
    tabs = re.findall(r'<button class="tab" role="tab"[^>]*>(.*?)</button>', v)
    assert len(tabs) == 3 and tabs[2] == ('Videos<span class="tn"><span class="tnp"> (</span>4'
                                         '<span class="tnp">)</span></span>'), (
        f"the tabs read {tabs}: Videos is not the third, with the count chip the others carry")
    pane = v[v.index('id="ppane"'):]
    # NOTHING FROM YOUTUBE BEFORE PLAY: a still, its embed on a button, and no frame.
    assert "<iframe" not in pane and "ytimg" not in pane and "<img" not in pane, (
        "the Videos tab draws a frame or an image before Play")
    embeds = re.findall(r"<(\w+)[^>]*\sdata-embed=\"([^\"]*)\"", pane)
    assert embeds == [("button", "-titleOnly1|0|m20260224_-titleOnly1")], (
        f"the still is not the newest recording's, from 0, on a button: {embeds}")
    rows = re.findall(r'<li(?: class="vwrest")?><a class="vwrow" href="([^"]*)" data-vwpick="([^"]*)"'
                      r'( aria-current="true")?>(.*?)</a></li>', pane)
    assert [(h, i, bool(c)) for h, i, c, _ in rows] == [
        ("/committee/H43/videos#v--titleOnly1", "-titleOnly1", True),
        ("/committee/H43/videos#v-divOne", "divOne", False),
        ("/committee/H43/videos#v-VID4", "VID4", False), ("/committee/H43/videos#v-VID1", "VID1", False)], (
        f"the rows are not the term's recordings newest first, each its own address, the newest "
        f"chosen: {[(h, i, c) for h, i, c, _ in rows]}")
    import html as _html
    say = {i: _html.unescape(re.sub(r"<[^>]+>", "", body)) for _h, i, _c, body in rows}
    want = {"-titleOnly1": "Feb 24, 2026, 36 min",
            "divOne": "Feb 17, 2026, 1:00 PM, ·\u00a02 h, Work Session Division I",
            "VID4": "Feb 10, 2026, ·\u00a01 bill, 12:58\u00a0PM, ·\u00a045 min, Executive Session HB\u00a01442",
            "VID1": "Feb 3, 2026, ·\u00a01 bill, 9:58\u00a0AM, ·\u00a01 h 52 min, Public Hearing HB\u00a01442"}
    assert say == want, f"the rows read {say!r}, not {want!r}"
    # Its kinds are the Meetings tab's chips, in their words and colours.
    assert '<span class="chip calkind k-exec">Executive Session</span>' in pane \
        and '<span class="chip calkind k-meet">Work Session</span>' in pane, (
        "a row's kind is not the Meetings tab's chip")
    cap = _html.unescape(re.sub(r"<[^>]+>", "", re.search(r'<div class="pbar vwcap">(.*?)</div>', pane).group(1)))
    assert cap == "House Commerce, ·\u00a0Feb 24, 2026, ·\u00a036 min, ·\u00a0On YouTube", (
        f"the caption under the player reads {cap!r}: one line, a missing start left out with its dot")
    # Every dot at the head of the part after it, and each of the caption's
    # parts kept whole with its dot where the line wraps: at 390px "On
    # YouTube" broke between its two words, and the caption ended a line on
    # a dot.
    assert _vw_loose_dots(pane) == 0 and pane.count(_VW_DOT_HEAD) >= 6, (
        "a dot in the Videos tab can end a line: it goes at the head of the part after it")
    css = _source("src/pages/app.css")
    keep = re.search(r"\n([^{}\n]*\.vwcap \.vwi\b[^{}\n]*)\{([^}]*)\}", css)
    assert keep and "white-space:nowrap" in keep.group(2), (
        "the caption's date, time, length or YouTube link can break across two lines, or from its dot")
    assert pane.count("The docket ties no bill to this recording.") == 1 and "No bill" not in pane \
        and 'class="note"' not in pane, (
            "a recording with no bill is not said so once, plainly, under the player")
    assert flat["videos"].count("its newest recording, on the <a") == 1 and \
        "Its last meeting on the record was on" in flat["videos"], (
            "the head names a last meeting older than the newest recording and does not say both")
    # BOTH DATES IN THE ONE STYLE, THE SITE'S: "on Tuesday, April 7, 2026 ...
    # from May 12, 2026" mixed two (the review of 29 October 2026), and the
    # style is the site's "May 12, 2026" (the manager, 29 October 2026).
    assert re.search(r"was on <a [^>]*>Feb 17, 2026</a>; its newest recording, on the "
                     r"<a [^>]*>Videos tab</a>, is from Feb 24, 2026\.", flat["videos"]), (
        "the head's last meeting and newest recording are not dated in the one style: "
        + re.search(r"Its last meeting.{0,300}", flat["videos"]).group(0))
    # THE SKIP LINK STRAIGHT AFTER THE PLAYER AND ITS CAPTION, before what the
    # recording covers: after it, a keyboard passed House Commerce's 37 bills
    # and their moments, 63 stops, to reach it (the review of 29 October 2026).
    # The list's heading under the page's h2 sections: an h3 (a chamber's,
    # under its h1 alone, is an h2: _chamber_videos).
    assert '<h3 class="vwh" id="vwh">4 recordings in 2025–2026</h3>' in pane, (
        "a committee's list of recordings is not headed by an h3")
    main = pane[pane.index('<div class="vwmain">'):pane.index('<div class="vwdet">')]
    assert main.index("On YouTube</a>") < main.find("data-vwskip>Skip to the list of recordings</a>") \
        and "data-vwskip" not in pane[pane.index('<div class="vwdet">'):], (
            "the skip link is not straight after the player and its caption, before the detail")
    # A DAY WHOSE BILLS' RECORDING IS NOT ESTABLISHED says so, as the Meetings
    # tab says it of that day, and not that the docket ties no bill: House
    # Public Works and Highways' only recording of a four-bill hearing of 5
    # May 2021 read as if no bill was heard in it (the review of 29 October
    # 2026). divOne is the fixture's recording of such a day.
    dv = flat["div"][flat["div"].index('class="vwdetin"'):]
    dv = dv[:dv.index('<div class="vwside">')]
    assert "1 bill was before the committee that day; which of its recordings it is in has not been " \
        "established." in dv and "The docket ties no bill" not in dv and \
        'href="/committee/H43/sessions#day-2026-02-17" data-vwday="2026-02-17">This committee&rsquo;s ' \
        "meeting that day</a>" in dv, (
            "a recording of a day whose bills' recordings are not established does not say so, with the "
            "way to that meeting: " + re.sub(r"<[^>]+>", " ", dv)[:300])
    # THE MOMENTS ARE THE MEETINGS TAB'S OWN BUTTONS, byte for byte.
    det = flat["vid1"][flat["vid1"].index('class="vwdetin"'):]
    vj = re.search(r'<span class="vwmom"><span class="mjumps">(.*?)</span>(?:<span class="vwout">.*?</span>)?</span>'
                   r'<span class="vwbt">', det).group(1)
    day = flat["meetings"][flat["meetings"].index('id="day-2026-02-03"'):]
    mj = re.search(r'<span class="mjumps">(.*?)</span></div>', day).group(1)
    assert vj == mj and "approximate" in vj and "|150" in vj, (
        f"the Videos tab's moment for VID1 is {vj!r}, the Meetings tab's {mj!r}")
    assert '<a href="/committee/H43/sessions#day-2026-02-03" data-vwday="2026-02-03">What the committee ' \
        'did at this meeting</a>' in det, "the detail does not lead to the meeting on the Meetings tab"
    # EACH MOMENT AND ITS "APPROXIMATE" ARE ONE, which does not wrap: as two
    # items of a row that wraps, the word started the next line beside the
    # next button, and at 390px HB 1157-FN's inferred moment read plain and
    # its stated one approximate (the review of 29 October 2026).
    pair = re.findall(r'<span class="mjump"><button type="button" class="jump" data-seek="p1\|(\d+)"[^>]*>.*?'
                      r'</button>(<i class="approx">approximate</i>)?</span>', flat["jumps"])
    assert pair == [("9835", '<i class="approx">approximate</i>'), ("9960", "")] and \
        flat["jumps"].count('<span class="mjump">') == 2, (
            f"a moment's button and its \"approximate\" are not held together: {flat['jumps']}")
    assert re.search(r"\n\.mjump\{display:inline-flex;flex-wrap:nowrap;", css), (
        "app.css: a moment's button and its \"approximate\" can wrap apart")
    # THE MANAGER'S LAYOUT (review, 6 and 7), each rule the tab stands on (a
    # phone's, the player staying over the whole list, is
    # _videos_phone_playlist's): on a wide screen two columns, the list as
    # tall as the player block and scrolling inside it; the chosen row a bar
    # as well as a colour, Highlight under forced colours; and a row two
    # lines, its kinds and bills cut short on one (the review of 29 October
    # 2026). A study committee's view is in a tab's pane, the page's width
    # (_study_committee_tabs).
    wide = _braced(css, "@media screen and (min-width:60em){")
    lit = css.find('.vwrow[aria-current="true"]{border-left-color:Highlight}')
    forced = css.rfind("@media (forced-colors:active){", 0, lit) if lit >= 0 else -1
    for ok, why in (
            ("grid-template-columns:minmax(0,1fr) 22rem" in wide and '"main side"' in wide,
             "on a wide screen the list does not stand beside the player"),
            (".vwin{position:absolute;inset:0;" in wide and "overflow:auto" in wide,
             "on a wide screen the list is not as tall as the player block, scrolling inside it"),
            (re.search(r'\n\.vwrow\[aria-current="true"\]\{border-left-color:var\(--pine\)', css),
             "the chosen row is told by its colour alone"),
            (forced >= 0 and "}" not in css[forced + len("@media (forced-colors:active){"):lit],
             "under forced colours the chosen row has no bar"),
            (re.search(r"\n\.vwb\{[^}]*display:flex;[^}]*white-space:nowrap;overflow:hidden\}", css)
             and re.search(r"\n\.vwl\{flex:0 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis\}", css)
             and re.search(r"\n\.vwb \.chip\{flex:none;order:0;", css),
             "a row's kinds and bills can run onto a third line, or its kinds follow its bills on a "
             "phone (the Calendar's .calkind{order:3})")):
        assert ok, f"app.css: {why}"
    # THE SECOND LINE HOLDS ITS HIDDEN COMMAS (the walk of 30 October 2026):
    # .sr is absolutely placed, so the line's overflow:hidden clips it only
    # where the line, or something inside it, is its containing block. None
    # was, and the commas of a long line stood 1px wide past the list's edge:
    # /committee/ss1729/videos scrolled sideways at 390 and at 1280. Each .sr
    # in a row's second line, as renderPage draws it: its nearest positioned
    # ancestor is inside the row, and it or one between it and the row clips.
    # A committee's row and a study committee's, whose line is its parts
    # (studyVideoRows), each part after the first behind a hidden comma.
    study = _app_js('scope.videoView(scope.VW_STATIC.study(' + json.dumps({
        "kind": "study", "who": "Commission to Study Stable Tokens", "key": "1729", "path": "/committee/ss1729",
        "rows": [{"id": "agPR9tSyTok", "date": "2026-10-29", "seconds": 7200, "venue": "State House 122-123",
                  "type": "Regular meeting", "anchor": "day-2026-10-29"}]}) + "))", names=("videoView", "VW_STATIC"))
    # AND EVERY ONE IN THE LIST (the review of 30 October 2026): on a wide
    # screen the list scrolls inside its box (.vwin .vwlist{overflow:auto}),
    # and a comma in a row's first line was placed against the box round it,
    # outside the scrolling, where its row would be with the list unscrolled:
    # the page ran on past its footer by the list's hidden height, 4,865px on
    # House Finance's (H34) at 1280. Each .sr in the list: its nearest
    # positioned ancestor is the list or inside it.
    rules, srs = _css_screen_rules(css), []
    for drawn in (got["videos"], study or ""):
        _html_walk(drawn, element=lambda c: srs.append(c) if "sr" in c[0]["classes"]
                   and any("vwlist" in e["classes"] for e in c[1:]) else None)
    has = lambda c, k, v: _css_won(rules, c).get(k, (v,))[0]
    name = lambda c, j: ".".join(sorted(c[j]["classes"])) or c[j]["tag"] if j < len(c) else "the page"
    loose, outside = [], []
    for c in srs:
        at = lambda cls: next((j for j, e in enumerate(c) if cls in e["classes"]), len(c))
        row, lst = at("vwrow"), at("vwlist")
        held = next((j for j in range(1, len(c)) if has(c[j:], "position", "static") != "static"), len(c))
        if held > lst:
            outside.append(f"{name(c, 1)} held by {name(c, held)}")
        if any("vwb" in e["classes"] for e in c[1:row]) and (held >= row or not any(
                has(c[k:], "overflow", "visible") in ("hidden", "clip") for k in range(held, row))):
            loose.append(f"{name(c, 1)} held by {name(c, held)}")
    in_line = [c for c in srs if any("vwb" in e["classes"] for e in c[1:])]
    assert any("vwl" in c[1]["classes"] for c in in_line) and not loose, (
        "app.css: a hidden comma in a recording's second line is not clipped with it, so a long line "
        f"can push the page sideways ({len(in_line)} drawn): " + "; ".join(sorted(set(loose))[:4]))
    assert len(srs) > len(in_line) and not outside, (
        "app.css: a hidden comma in the list of recordings is placed outside the list, so on a wide screen the "
        f"page runs on past its footer by the list's hidden height ({len(srs)} drawn): "
        + "; ".join(sorted(set(outside))[:4]))
    # The list the rows' offsetParent, a row is measured from its top: taking
    # the list's own offset (its heading, above it in the box) off a row's
    # offsetTop that no longer counts it, vwListShow showed a row landed on at
    # the foot of the list cut short by the heading's height. A row at 660 to
    # 720px down a list 440px tall: 280px either way it is measured.
    kept = _node_app(r"""
require("./stub.js");
const fs = require("fs");
const s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({vwListShow})");
const out = {};
for (const [k, held] of [["list", true], ["box", false]]) {
  const list = {scrollHeight: 2400, clientHeight: 440, scrollTop: 0, offsetTop: 40};
  const li = {offsetTop: 660 + (held ? 0 : 40), offsetHeight: 60, offsetParent: held ? list : {}};
  try { s.vwListShow({closest: (q) => q === ".vwlist" ? list : q === "li" ? li : null}); out[k] = list.scrollTop; }
  catch (e) { out[k] = e.constructor.name + ": " + e.message; }
}
process.stdout.write("\n@@" + JSON.stringify(out));
""")
    assert kept is None or kept == {"list": 280, "box": 280}, (
        f"a row chosen at the foot of the list is not shown whole inside it, measured from the list's top: {kept}")
    # What is cut is the bills' numbers: the count is on the first line, beside
    # the date, so the cut never takes it.
    assert '<span class="vwd">Feb 10, 2026<span class="sr">,</span> <span class="vwi"><span aria-hidden="true">' \
        '&middot;&nbsp;</span><span class="vwn">1 bill</span></span></span>' in pane, (
        "a row's count of bills is not beside its date, where the cut of its second line cannot take it")
    # Every row in the page and shown, at every width: on a phone the list is
    # what scrolls under the player (_videos_phone_playlist).
    m = flat["many"]
    assert m.count('class="vwrow"') == 25 and "vwrest" not in m and "data-vwall" not in m, (
        "a list of 25 is not drawn whole: some rows are held back behind a button")
    # A term with none: the tab, with no count, and the pane says so.
    lt = flat["later"]
    assert re.search(r'role="tab" id="ptab_2"[^>]*>Videos</button>', lt) and \
        "No recording of this committee from 2017–2018 is on file. Recordings here begin in May " \
        "2020, with the General Court&rsquo;s YouTube channels." in lt, (
            "a term with no recording does not keep the tab without a count and say so")
    assert "Videos" not in re.sub(r"<[^>]+>", " ", flat["none"].split('id="ppane"')[0].split('role="tablist"')[-1]) \
        and flat["noneTab"] == 0, "a committee with no recording has a Videos tab, or opens on it"
    # THE ROW THAT IS PLAYING, pressed again, goes on playing: choosing it
    # built a new frame from 0 over the one that was playing. Another row
    # pressed while one plays is played, through the one handler (its still
    # drawn, then pressed). vwChoose over a view whose player holds a frame.
    chose = _node_app(r"""
require("./stub.js");
const fs = require("fs");
const s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({vwChoose, setView: (o) => { VVIEW = o; }})");
const n = {made: 0, played: 0};
const player = {insertAdjacentHTML: () => { n.made += 1; }, remove() {}, scrollIntoView() {},
  querySelector: () => ({click: () => { n.played += 1; }, focus() {}})};
const box = {querySelector: (sel) => sel === ".vwplay iframe" ? {} : sel === ".vwplay" ? player
  : sel === ".vwdetin" ? {innerHTML: ""} : sel === ".vwsay" ? {textContent: ""} : null,
  querySelectorAll: () => []};
const row = (id) => ({dataset: {vwpick: id}, closest: (sel) => sel === ".vw" ? box : null,
  setAttribute() {}, removeAttribute() {}});
const wrote = [];
history.replaceState = (st, title, url) => wrote.push(url);
const out = {};
try {
  s.setView({who: "Senate Finance", rows: [{id: "A", date: "2026-05-12"}, {id: "B", date: "2026-05-05"}],
    chosen: "A", pid: (r) => "m_" + r.id, href: (id) => "/committee/S07/videos#v-" + id});
  s.vwChoose(row("A")); out.again = Object.assign({}, n); out.againWrote = wrote.splice(0);
  s.vwChoose(row("B")); out.other = Object.assign({}, n);
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
""")
    if chose is not None:
        assert "threw" not in chose and chose["again"] == {"made": 0, "played": 0}, (
            f"the row that is playing, pressed again, starts it over in a new frame: {chose}")
        # And the address names it, as a row pressed does: one that arrived
        # naming a recording not on file had gone on naming that.
        assert chose["againWrote"] == ["/committee/S07/videos#v-A"], (
            f"the row that is playing, pressed again, leaves the address as it was: {chose}")
        assert chose["other"] == {"made": 1, "played": 1}, (
            f"another row pressed while one plays is not played through its still: {chose}")
    # AN ADDRESS NAMING ANOTHER RECORDING while one plays is a choice of it:
    # the pane was kept through renderPage, playing the old one under an
    # address that named the new (the head's "Videos tab" link, pressed while
    # Senate Finance's 28 April played, on real data). Kept while what plays is
    # what the page asks for; and a term's tab drawn asks for what it drew, so
    # a recording of the term left behind does not end the next one's playing.
    kept = _node_app(r"""
require("./stub.js");
const fs = require("fs");
const s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({vwPaneKept, renderCommitteeVideos,"
  + " setState: (p, t, v) => { PAGE = p; PAGE_TAB = t; VVIEW = v; }, getVid: () => PAGE.vid})");
const el = {};
const box = {dataset: {vwkey: "S07|2025-2026"}, querySelector: (sel) => sel === "iframe" ? {} : null};
const pane = {parentNode: el, querySelector: (sel) => sel === ".vw" ? box : null};
el.querySelector = (sel) => sel === "#ppane" ? pane : null;
const page = (vid) => ({kind: "committee", data: {code: "S07"}, term: "2025-2026", terms: ["2025-2026"], vid});
const out = {};
try {
  s.setState(page("B"), 2, {chosen: "B"}); out.same = s.vwPaneKept(el) === pane;
  s.setState(page("A"), 2, {chosen: "B"}); out.other = s.vwPaneKept(el) === pane;
  s.setState(page("left2024"), 2, null);
  s.renderCommitteeVideos({code: "S07", name: "Finance", chamber: "S", sessions: [],
    recordings: [{id: "N1", date: "2026-05-12", term: "2025-2026"}]});
  out.drawn = s.getVid();
} catch (e) { out.threw = e.constructor.name + ": " + e.message; }
process.stdout.write("\n@@" + JSON.stringify(out));
""")
    if kept is not None:
        assert "threw" not in kept and kept["same"] and not kept["other"], (
            f"a recording that plays is kept while the address names another: {kept}")
        assert kept["drawn"] == "N1", (
            f"a term's Videos tab drawn asks for {kept['drawn']!r}, not the recording it drew")
    # A TERM CHOSEN WHILE THE ADDRESS NAMES A RECORDING drops it from a
    # committee's address, on its Videos tab; on a member's page, whose tabs
    # are not a committee's, it had rewritten the Votes tab's address as
    # /videos (the review of 29 October 2026). The record page's change
    # listener, fired as the Term control fires it.
    termed = _node_app(r"""
require("./stub.js");
const fs = require("fs");
const heard = [];
document.addEventListener = (t, f) => { if (t === "change") heard.push(f); };
process.on("unhandledRejection", () => {});
const s = (0, eval)(fs.readFileSync("./page.js", "utf8")
  + "; ({setState: (p, t) => { PAGE = p; PAGE_TAB = t; }, getPage: () => PAGE})");
const wrote = [];
history.replaceState = (st, title, url) => wrote.push(url);
const page = (kind, data) => ({kind, data, terms: ["2025-2026", "2023-2024"], term: "2025-2026", status: "",
  vfilter: "", vside: "", vq: "", vopen: {}, vshow: 5, bshow: 5, mshow: 0, vid: ""});
const fire = () => heard.forEach((f) => { try { f({target: {dataset: {pf: "term"}, value: "2023-2024",
  closest: () => null, matches: () => false}}); } catch (_) {} });
const out = {};
location.pathname = "/legislator/jane-doe/votes"; location.hash = "#v-abc";
s.setState(page("member", {}), 2); fire(); out.member = wrote.splice(0);
// The listener ran on past the line, to the lists it starts again.
out.memberRan = [s.getPage().term, s.getPage().bshow];
location.pathname = "/committee/S07/videos"; location.hash = "#v-abc";
s.setState(page("committee", {code: "S07"}), 2); fire(); out.committee = wrote.splice(0);
process.stdout.write("\n@@" + JSON.stringify(out));
""")
    if termed is not None:
        # The committee's first address is the listener's own; a second is
        # the page drawn again for the new term, which this record (no
        # recording in it) opens on Bills.
        assert termed["memberRan"] == ["2023-2024", 0], (
            f"the term's change listener did not run through on a member's page: {termed}")
        assert termed["member"] == [] and termed["committee"][:1] == ["/committee/S07/videos"], (
            f"a term chosen while the address names a recording rewrites {termed}: a member's address "
            "is left alone, and a committee's drops the recording")
    return "ok", ("the third tab, counted; a still of the newest, nothing from YouTube before Play; "
                  "rows of the term with the Meetings tab's chips, no bill line where none is known; "
                  "one caption with nothing missing said, no dot ending a line; the moment the "
                  "Meetings tab's own button; all 25 rows drawn; a term with none says so; no "
                  "tab with no recording; the row playing, pressed again, plays on; an address naming another "
                  "recording ends it")


# A Videos view as app.js meets it on a phone, its parts stood up by hand: the
# tab strip above its pane, which stays at the top of the window (sticky), and
# the player that stays under it where the view is marked [data-vwpin], as
# app.css has it below 60em -- or, `wide`, that does not, as on a desktop.
# The window is 844px high, or `short`, 390: a phone held sideways.
_VW_PHONE_HARNESS = _HEARD_PRELUDE + r"""
load("videoView, vwStick, vwChoose, setView: (o) => { VVIEW = o; }");
const css = (el) => ({position: (el && el.pos) || "static", getPropertyValue: () => ""});
globalThis.getComputedStyle = css;
const observed = [];
globalThis.ResizeObserver = class { constructor(f) { this.f = f; } observe(el) { observed.push(el); } disconnect() {} };
const scrolled = [];
globalThis.scrollBy = (x, y) => scrolled.push(y);
const out = {};
const view = (wide, short) => {
  document.documentElement.clientHeight = short ? 390 : 844;
  const strip = {pos: "sticky", getBoundingClientRect: () => ({height: 45, bottom: 45})};
  const tab = {closest: (q) => q === "[role=tablist]" ? strip : null};
  document.getElementById = (id) => id === "ptab_2" ? tab : null;
  const pane = {getAttribute: (k) => k === "aria-labelledby" ? "ptab_2" : null};
  const n = {det: [], player: [], focus: 0};
  const det = {getBoundingClientRect: () => ({top: -900}), scrollIntoView(o) { n.det.push(o.block); }};
  const player = {insertAdjacentHTML() {}, remove() {}, scrollIntoView(o) { n.player.push(o.block); },
    querySelector: (q) => q === ".pstub" ? {focus() { n.focus += 1; }, click() {}} : null};
  const box = {props: {}, attrs: {}, top: 300, style: {setProperty(k, v) { box.props[k] = v; },
      getPropertyValue: (k) => box.props[k] || ""},
    setAttribute(k, v) { box.attrs[k] = v; }, removeAttribute(k) { delete box.attrs[k]; },
    hasAttribute(k) { return k in box.attrs; }, getBoundingClientRect: () => ({top: box.top}),
    closest: (q) => q === "[role=tabpanel]" ? pane : null,
    querySelector: (q) => q === ".vwmain" ? main : q === ".vwdet" ? det : q === ".vwplay" ? player
      : q === ".vwdetin" ? {innerHTML: ""} : q === ".vwsay" ? {textContent: ""} : null,
    querySelectorAll: () => []};
  // Sticky as app.css draws it: below 60em, where the view is marked.
  const main = {get pos() { return !wide && "data-vwpin" in box.attrs ? "sticky" : "static"; },
    getBoundingClientRect: () => ({height: 268, bottom: 313})};
  document.querySelectorAll = (q) => q === ".vw" ? [box] : [];
  return {box, n, strip, main};
};
try {
  // Every row drawn, nothing held back behind a button.
  const rows = Array.from({length: 40}, (_, i) => ({id: "r" + i, date: "2026-03-01"}));
  const html = s.videoView({who: "House Finance", key: "H34|2025-2026", heading: "40 recordings", rows,
    href: (id) => "/committee/H34/videos#v-" + id, pid: (r) => "p_" + r.id});
  out.rows = (html.match(/class="vwrow"/g) || []).length;
  out.held = /vwrest|data-vwall/.test(html);
  // How far down the strip and the player reach, written on the view; watched, and not afresh.
  const v = view(false);
  s.vwStick(); const first = observed.length; s.vwStick();
  out.props = Object.assign({}, v.box.props); out.watched = [first, observed.length, observed.includes(v.strip), observed.includes(v.main)];
  out.pinned = "data-vwpin" in v.box.attrs;
  // The keyboard on a row under the player: scrolled clear of it. One below it, or a wide
  // screen's (its player does not stay, the strip ends at 45px), left where it is.
  let at = v;
  const focus = (top) => (heard.document.focusin || []).forEach((f) => f({target: {
    closest: (q) => q === ".vw" ? at.box : null, getBoundingClientRect: () => ({top})}}));
  focus(200); focus(400);
  out.under = scrolled.splice(0);
  // The foot of the player that stays: drawn once the view has gone up under the strip, and
  // not while it rests where it stands.
  const scroll = (top) => { at.box.top = top; (heard.window.scroll || []).forEach((f) => f({})); return "data-vwstuck" in at.box.attrs; };
  out.edge = [scroll(300), scroll(-600), scroll(300)];
  at = view(true); s.vwStick(); focus(200);
  out.wideFocus = scrolled.splice(0);
  // A WINDOW TOO SHORT FOR IT: a phone held sideways, 390px high, where the strip and the
  // player are 313px of it. The player is not made to stay; what is under it is kept clear
  // of the strip alone, and the keyboard on a row under the strip is put clear of it.
  at = view(false, true); s.vwStick();
  out.short = {pinned: "data-vwpin" in at.box.attrs, props: Object.assign({}, at.box.props), edge: scroll(-600)};
  focus(200); focus(30);
  out.short.focus = scrolled.splice(0);
  // A row chosen on a phone before anything plays: what it covers brought up under the player;
  // on a wide screen the player brought into view, as before.
  for (const wide of [false, true]) {
    const w = view(wide); s.vwStick();
    s.setView({who: "House Finance", rows: [{id: "A", date: "2026-05-12"}, {id: "B", date: "2026-05-05"}],
      chosen: "A", pid: (r) => "m_" + r.id, href: (id) => "/committee/H34/videos#v-" + id});
    s.vwChoose({dataset: {vwpick: "B"}, closest: (q) => q === ".vw" ? w.box : null, setAttribute() {}});
    out[wide ? "chooseWide" : "choosePhone"] = w.n;
  }
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 300); }
process.stdout.write("\n@@" + JSON.stringify(out));
"""


@check("frontend", "a Videos view keeps the live strip's place first in the band that stays at the top: "
                   "empty, hidden, no height, and nothing here styles it")
def _videos_live_strip_place():
    """From the live layer's design, approved (the manager, 29 October 2026):
    the band that stays at the top of a phone's window (.vwmain, vwPlayer's
    container) holds one empty first child, <div class="lv-strip" hidden>,
    which the live layer's live.js fills ("House Finance is live now ·
    Watch") and draws with its own .lv-strip rules. Hidden, it must not
    change the band's height: so app.css has no rule for it, and none that
    reaches it sets a display that would beat the browser's own [hidden]."""
    got = _app_js('scope.videoView({rows:[{id:"abc",date:"2026-02-03",seconds:3600,count:"2 bills"},'
                  '{id:"def",date:"2026-02-10"}],pid:r=>"vw-"+r.id,who:"House Finance",heading:"2 recordings",'
                  'href:id=>"/committee/H34/videos/"+id,key:"H34"})', names=("videoView",))
    if got is None:
        return "skip", "node, app.js or tests/dom_stub.js is not here"
    assert got.startswith('<div class="vw" data-vwkey="H34"><div class="vwmain"><div class="lv-strip" hidden></div>'
                          '<div class="player vwplay"'), (
        "the Videos band does not begin with the live strip's empty, hidden place: " + got[:200])
    assert got.count("lv-strip") == 1, "the live strip's place is written more than once in a view"
    css = _source("src/pages/app.css")
    assert "lv-strip" not in css, "app.css styles .lv-strip, which is the live layer's to draw"
    for pin in ({}, {"data-vwpin": "", "data-vwstuck": ""}):
        chain = [{"tag": "div", "ids": set(), "classes": {"lv-strip"}, "attrs": {"class": "lv-strip", "hidden": ""},
                  "states": set()},
                 {"tag": "div", "ids": set(), "classes": {"vwmain"}, "attrs": {"class": "vwmain"}, "states": set()},
                 {"tag": "div", "ids": set(), "classes": {"vw"}, "attrs": {"class": "vw", **pin}, "states": set()},
                 {"tag": "body", "ids": set(), "classes": {"pg"}, "attrs": {"class": "pg"}, "states": set()}]
        shows = [(sel, line) for ctx, sel, body, line in _css_rules(css)
                 if not any(re.search(r"\bprint\b", c) for c in ctx) and _css_can_reach(sel, chain)
                 and any(k == "display" for k, _v in _css_decls(body))]
        assert not shows, (
            f"a rule sets the hidden live strip's display, so it takes height in the band: {shows[:3]}")
    return "ok", "the band's first child is <div class=\"lv-strip\" hidden></div>, once, and no rule here draws it"


@check("frontend", "on a phone a Videos view is a playlist as YouTube's: the player stays at the top under "
                   "the tab strip while every recording scrolls on the page beneath it, and nothing the "
                   "keyboard moves to is left under the player; a desktop's view as it was")
def _videos_phone_playlist():
    """The owner, 29 October 2026: "on a phone the player stays at the top
    (sticky) while the list of recordings scrolls beneath it". The player and
    its caption (.vwmain) stick under the tab strip that stays at the top
    already (.rhead ~ .tabs), at --vwtop, the strip's height, which app.js's
    vwStick measures and writes on the view with --vwstick, the player's
    foot; whatever is under the player -- what the recording covers, the
    rows, a bill's moment -- keeps that far from the top when it is scrolled
    to (scroll-margin-top), and where the Tab key leaves it under the player
    app.js puts the focus clear (focusin): Chromium keeps the margin for
    scrollIntoView and not for Tab, and with the margin alone 31 of 40 rows
    gone back up through with Shift+Tab rested under the player at 390px
    (Playwright on real data, 29 October 2026; none with app.js's). The whole list is drawn: it is what
    the page scrolls through, where it had been twenty rows and a button
    (House Finance has 106; videoView drew them in under a millisecond on
    real data). Still no box that scrolls inside a page that scrolls: the
    page scrolls. A row chosen before a first press brings the recording's
    description up under the player. On a wide screen nothing of this
    applies: the player does not stick, and the view is as it was (the same
    pixels before and after at 1280, measured 29 October 2026).

    ONLY WHERE IT LEAVES THE LIST ROOM (the review of 29 October 2026, 1):
    stuck at every width below 60em, the strip, the player and its caption
    were 517px of a phone held sideways (844 by 390) and 548 of a 900 by 600
    window, and not one of 80 Tab and Shift+Tab steps through House
    Finance's list left its row in sight. app.css's sticky rule asks for
    [data-vwpin], which vwStick sets only where the three take at most
    three fifths of the window's height; elsewhere the player scrolls with
    the page and what is under it is kept clear of the strip alone, the
    focus too (80 of 80 steps in sight at 844 by 390, 900 by 600 and 667 by
    375, and still at 390 by 844 and 768 by 1024; one step was under the
    strip without the strip's guard). And while the player stays over the
    list, a foot to it, once the view has gone up under the strip (7)."""
    css = _source("src/pages/app.css")
    phone = _braced(css, "@media screen and (max-width:59.99em){")
    wide = _braced(css, "@media screen and (min-width:60em){")
    stick = re.search(r"\n\s*\.vw\[data-vwpin\] \.vwmain\{position:sticky;top:var\(--vwtop,0px\);z-index:\d+\}", phone)
    band = re.search(r"\n\s*\.vwmain\{background:var\(--vwbg\);padding-bottom:var\(--sp-3\);"
                     r"margin-bottom:calc\(-1 \* var\(--sp-3\)\)\}", phone)
    foot = re.search(r"\n\s*\.vw\[data-vwstuck\] \.vwmain\{box-shadow:0 1px 0 var\(--rule-2\)", phone)
    clear = re.search(r"\.vwdet,\.vwdet :is\(a,button\),\.vwside :is\(a,button\)[^{]*\{scroll-margin-top:calc\("
                      r"var\(--vwstick,0px\)", phone)
    for ok, why in (
            (stick, "on a phone the player does not stay at the top, under the tab strip, where the view is "
                    "marked as leaving the list room"),
            (not re.search(r"(^|[\n}])\s*\.vwmain\{[^}]*position:sticky", phone),
             "on a phone the player stays at the top whatever the window's height: a phone held sideways has "
             "its list under the player"),
            (band, "the player's band is not drawn the same pinned or not, so marking it changes the height it "
                   "is measured by"),
            (foot, "the player that stays over the list has no foot"),
            (clear, "on a phone what is under the player is not kept clear of it when scrolled to"),
            (".vwlist" not in phone and ".vwrest" not in phone.replace(".vwbills:not(.vwopen) .vwrest", ""),
             "on a phone rows of the list are held back"),
            ("sticky" not in wide and "--vwtop" not in wide,
             "on a wide screen the player is made to stay: the desktop's view is to be as it was"),
            (re.search(r"\n\.vw\{--vwbg:var\(--paper\)\}\n\.pane \.vw\{--vwbg:var\(--surface\)\}", css),
             "the player's band is not the ground it stands on")):
        assert ok, f"app.css: {why}"
    got = _node_app(_VW_PHONE_HARNESS)
    if got is None:
        return "ok", "app.css keeps the player at the top on a phone; node is not here to drive app.js"
    assert "threw" not in got, "the Videos view on a phone could not be driven: " + got["threw"]
    assert got["rows"] == 40 and not got["held"], (
        f"a list of 40 draws {got['rows']} rows, or holds some back behind a button: the whole list is "
        "what a phone scrolls through")
    assert got["props"] == {"--vwtop": "45px", "--vwstick": "313px"} and got["pinned"], (
        f"the strip's and the player's reach are not written on the view, or a 390 by 844 phone's player "
        f"is not made to stay: {got['props']}, {got['pinned']}")
    assert got["watched"] == [2, 2, True, True], (
        f"the strip and the player are not watched for a change of size, or are watched afresh each "
        f"time, which reports again without end: {got['watched']}")
    assert got["under"] == [-121] and got["wideFocus"] == [], (
        f"the keyboard on a row under the player is not scrolled clear of it ({got['under']}), or a "
        f"wide screen's below the strip is moved ({got['wideFocus']})")
    assert got["short"] == {"pinned": False, "props": {"--vwtop": "45px", "--vwstick": "45px"}, "edge": False,
                            "focus": [-23]}, (
        "in a window too short for it (390px high, the strip and the player 313px of it) the player is made "
        "to stay, what is under it is not kept clear of the strip alone, or a row the keyboard leaves under "
        f"the strip is not put clear of it: {got['short']}")
    assert got["edge"] == [False, True, False], (
        f"the player that stays has no foot once the list has gone up under it, or has one at rest: {got['edge']}")
    assert got["choosePhone"] == {"det": ["start"], "player": [], "focus": 1} and \
        got["chooseWide"] == {"det": [], "player": ["nearest"], "focus": 1}, (
            f"a row chosen does not bring up what it covers under a phone's player, or a wide screen's "
            f"player into view: {got['choosePhone']}, {got['chooseWide']}")
    return "ok", ("on a phone the player stays under the strip over the whole list, what is under it kept "
                  "clear of it by app.css and by app.js, with a foot once the list goes under it; not in a "
                  "window too short for it, where the focus is kept clear of the strip; a row chosen brings "
                  "up its description; a desktop's view untouched")


@check("frontend", "a recording chosen on a Videos tab is described under the player: its kinds, how many "
                   "bills the docket ties to it, and a line a bill -- the number, then its moments, the "
                   "Meetings tab's own buttons, then its title -- in the order the recording reaches them")
def _videos_description():
    """The owner, 29 October 2026: "under the player, list the bills it
    covers, each with its moment button ("HB 1042 at 00:03:45", with
    "approximate" where inferred) that jumps the player there, reusing the
    Meetings tab's moment buttons and labels ... Show the kind chips too",
    "clear, scannable, the bill number then its moment". The detail had been
    the number, the title, and the moments on a line of their own under the
    title. Now (app.js, cmteVideoDetail): the kinds as the Meetings tab's
    chips and the room; "The docket ties 3 bills to this recording. Choose a
    time to jump the recording there." -- or, with no moment anywhere in it,
    the Meetings tab's own "Exact moments not found." (a bill's player's
    words since the cohesion audit of 30 October 2026); then each bill once, in the order the recording reaches it (its
    first moment; none, after), its number, its moments -- jumpButtons, the
    Meetings tab's bytes, "approximate" held to its button -- and its title
    under them. A bill with no moment is its number and title. Drawn by
    renderPage in node over a committee whose bills come in another order
    than the recording reaches them."""
    item = lambda bill, kind, start, state, vid="VID1", **k: dict({
        "bill": bill, "n": bill[:2] + " " + bill[2:], "title": f"the title of {bill}", "year": 2026,
        "term": "2025-2026", "kind": kind, "video_id": vid, "start": start, "state": state, "time": "10:00",
        "venue": "LOB 302"}, **k)
    # HB 675-FN-A-LOCAL: a number of 17 characters, 164px at 1280, which ran
    # 36px under its first moment in a column of 7.5rem (the review of 29
    # October 2026, 3).
    items = [item("HB1442", "work session", 600, "stated"),
             item("HB1442", "executive session", 3000, "located"),
             item("HB1001", "work session", 120.0, "stated"),
             item("HB1203", "work session", None, "prestream"),
             item("HB675", "work session", 1800, "located", n="HB 675-FN-A-LOCAL")]
    quiet = [item("HB2001", "public hearing", None, "prestream", "VID9"),
             item("HB2002", "public hearing", None, "prestream", "VID9")]
    out = lambda its: [{"bill": b, "kinds": sorted({i["kind"] for i in its if i["bill"] == b}), "outcome": "worked"}
                       for b in dict.fromkeys(i["bill"] for i in its)]
    cmte = {"code": "H43", "name": "Commerce", "chamber": "H", "bills": {"2025-2026": []},
            "sessions": [{"date": "2026-02-10", "term": "2025-2026", "video_id": "VID9", "items": quiet,
                          "outcomes": out(quiet)},
                         {"date": "2026-02-03", "term": "2025-2026", "video_id": "VID1", "items": items,
                          "outcomes": out(items)}],
            "recordings": [{"id": "VID9", "date": "2026-02-10", "term": "2025-2026"},
                           {"id": "VID1", "date": "2026-02-03", "term": "2025-2026", "began": "09:58"}]}
    harness = _HEARD_PRELUDE + r"""
load("renderPage, recordTerms, setPage: (p) => { PAGE = p; }, setTab: (t) => { PAGE_TAB = t; },"
  + " setUp: (u) => { UPCOMING = u; }");
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
const results = document.querySelector("#results");
const draw = (tab, vid) => {
  const terms = s.recordTerms("committee", fx);
  s.setPage({kind: "committee", data: fx, terms, term: terms[0], status: "", vfilter: "", vshow: 0, bshow: 0,
    mshow: 0, vid, mopen: {"day-2026-02-03": true}});
  s.setTab(tab); s.renderPage(); return results.innerHTML; };
const out = {};
try { s.setUp([]); out.vid1 = draw(2, "VID1"); out.vid9 = draw(2, "VID9"); out.meetings = draw(1, ""); }
catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 300); }
process.stdout.write("\n@@" + JSON.stringify(out));
"""
    got = _node_app(harness, {"fx.json": json.dumps(cmte)})
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert "threw" not in got, "the Videos tab would not draw: " + got["threw"]
    flat = {k: re.sub(r"[ \t\r\n]+", " ", v) for k, v in got.items()}
    det = lambda h: h[h.index('class="vwdetin"'):h.index('<div class="vwside">')]
    one = det(flat["vid1"])
    assert '<p class="vwlead">The docket ties 4 bills to this recording. Choose a time to jump the recording ' \
        'there.</p>' in one, "the description does not say how many bills the docket ties to the recording, " \
        "and how its times are used: " + re.sub(r"<[^>]+>", " ", one)[:300]
    # The kinds, as the Meetings tab's chips, before the bills.
    kinds = re.search(r'<p class="vwkinds">(.*?)</p>', one)
    assert kinds and '<span class="chip calkind k-meet">Work Session</span>' in kinds.group(1) and \
        '<span class="chip calkind k-exec">Executive Session</span>' in kinds.group(1) and \
        one.index('class="vwkinds"') < one.index('class="vwbills"'), "the description does not lead with its kinds' chips"
    # A line a bill: the number, then its moments, then its title; in the order
    # the recording reaches them, a bill with no moment after; each once.
    lines = re.findall(r'<li(?: class="vwrest")?><a class="vwbn" href="[^"]*">([^<]*)</a>'
                       r'(?:<span class="vwmom">(?:<span class="mjumps">(.*?)</span>)?(?:<span class="vwout">.*?</span>)?</span>)?'
                       r'<span class="vwbt">([^<]*)</span></li>', one)
    assert [(n, t) for n, _j, t in lines] == [("HB 1001", "the title of HB1001"), ("HB 1442", "the title of HB1442"),
                                             ("HB 675-FN-A-LOCAL", "the title of HB675"),
                                             ("HB 1203", "the title of HB1203")] and one.count('class="vwbn"') == 4, (
        "the bills are not a line each -- the number, its moments, its title -- in the order the recording "
        f"reaches them: {[(n, t) for n, _j, t in lines]}")
    jumps = {n: j for n, j, _t in lines}
    assert jumps["HB 1203"] == "" and 'data-seek="m20260203_VID1|120"' in jumps["HB 1001"], (
        f"a bill's moments are not beside its number, or a bill with none has some: {jumps}")
    # THE MEETINGS TAB'S OWN BUTTONS, byte for byte, both of HB 1442's
    # moments with their kinds, the inferred one "approximate".
    meet = flat["meetings"]
    card = meet[meet.index('id="day-2026-02-03"'):]
    card = card[card.index('data-id="HB1442"'):]
    mj = re.search(r'<span class="mjumps">(.*?)</span></div>', card).group(1)
    assert jumps["HB 1442"] == mj and mj.count('class="mjump"') == 2 and \
        "Work Session 00:10:00</button></span>" in mj and \
        'Executive Session 00:50:00</button><i class="approx">approximate</i></span>' in mj, (
            f"HB 1442's moments under the player are not the Meetings tab's: {jumps['HB 1442']!r} against {mj!r}")
    quiet_det = det(flat["vid9"])
    assert '<p class="vwlead">The docket ties 2 bills to this recording. Exact moments not found.</p>' \
        in quiet_det and 'class="mjumps"' not in quiet_det, (
            "a recording none of whose bills has a moment does not say so: " + re.sub(r"<[^>]+>", " ", quiet_det)[:300])
    css = _source("src/pages/app.css")
    at = css.find(".vwbills li{display:flex")
    phone = _braced(css[css.rfind("@media (max-width:45em){", 0, at):], "@media (max-width:45em){") if at >= 0 else ""
    assert re.search(r"\n\.vwbn\{grid-column:1;", css) and re.search(r"\n\.vwbt\{grid-column:2;", css) and \
        "display:flex;flex-wrap:wrap" in phone and ".vwbills .mjumps,.vwbills .vwmom{display:contents}" in phone and \
        ".vwbt{flex:1 1 100%}" in phone and \
        re.search(r"\n\.vwbills \.vwmom\{grid-column:2;display:flex;flex-wrap:wrap", css), (
            "app.css: a bill's moments are not beside its number with its title under them, on a wide screen "
            "or a phone")
    # THE NUMBERS' COLUMN IS THE LONGEST NUMBER'S, THE SAME DOWN THE LIST
    # (the review of 29 October 2026, 3): the list a grid whose first column
    # is at least 7.5rem and as wide as its widest number, each line a
    # subgrid of it, so HB 675-FN-A-LOCAL is never under its first moment and
    # the moments start on one line; and each number on its line's first
    # baseline, level with its moments or its title's first line, where it
    # had been centred against a title of two or three lines (6). Node draws
    # no boxes: these are the rules that place them, measured in Chromium on
    # real data (no number under a moment in the 736 lines of House Finance,
    # Education Funding and Children and Family Law, at 1280 and at 768,
    # where there had been 32).
    wide_list = re.search(r"\n\.vwbills\{[^}]*display:grid;[^}]*grid-template-columns:minmax\(7\.5rem,max-content\) "
                          r"minmax\(0,1fr\)", css)
    line = re.search(r"\n\.vwbills li\{([^}]*)\}", css)
    assert wide_list and line and "grid-column:1 / -1" in line.group(1) and \
        "grid-template-columns:subgrid" in line.group(1) and "align-items:baseline" in line.group(1) and \
        "grid-template-columns:7.5rem" not in line.group(1) and "align-items:center" not in line.group(1), (
            "app.css: a bill's number is in a fixed column, or one as wide as its own line's, where a long "
            "number runs under its moments or the moments do not start on one line; or a number is not on "
            "its line's first baseline")
    assert '<a class="vwbn" href="bill/2026/hb675">HB 675-FN-A-LOCAL</a>' in one, (
        "a long number is not drawn whole in the description")
    # A LINK IN THE PLAYER'S CAPTION OR UNDER IT IS 24px TALL (the review of
    # 30 October 2026; WCAG 2.5.8): "On YouTube" in the caption and the links
    # under the player sit in a line of text, where the player bar's
    # ".pbar > a" never reaches, and were 19px. Each, as renderPage draws it,
    # takes --tap-text top and bottom from the cascade.
    rules, links = _css_screen_rules(css), {}
    for k in ("vid1", "meetings"):
        _html_walk(got[k], element=lambda c: links.setdefault(
            next((n for n in ("vwcap", "vwlinks") for e in c[1:] if e and n in e["classes"]), ""), []).append(c)
            if c[0]["tag"] == "a" else None)
    short = [f".{n} a: {pad}" for n in ("vwcap", "vwlinks") for c in links.get(n, [])
             for pad in [tuple(_css_won(rules, c).get(f"padding-{s_}", ("0",))[0] for s_ in ("top", "bottom"))]
             if any("".join(v.split()) != "var(--tap-text)" for v in pad)]
    assert links.get("vwcap") and links.get("vwlinks") and not short, (
        "a link in the player's caption or under the player is under 24px tall, or renderPage drew none to "
        f"measure ({len(links.get('vwcap', []))} in the caption, {len(links.get('vwlinks', []))} under it): "
        + "; ".join(short[:4]))
    return "ok", ("the kinds, the count and how the times are used, then a line a bill -- number, the "
                  "Meetings tab's own buttons, title -- in the order the recording reaches them, the numbers "
                  "in a column as wide as the longest and on their lines' first baseline; a recording "
                  "with no moment says so; the caption's and the links' under the player 24px tall")


@check("frontend", "a recording's bills on a committee's Videos tab say what the committee did to each at THAT "
                   "meeting -- the chip and the vote as counted -- and nothing where it voted nothing there")
def _videos_say_the_vote():
    """The owner, 8 November 2026 (walking a test build): beside each bill's
    moment on a committee's Videos tab, the vote and its outcome, in the
    site's chip and the counted tally, "Inexpedient to Legislate (18–0)",
    from the record for THAT meeting. The meeting's `outcomes` (committee_acts.
    outcome) already hold it as "voted" with `votes`; a bill heard and not
    voted that day, or voted on another day (outcome "no vote" with `voted`),
    gets nothing extra, and never the other day's vote."""
    item = lambda bill, kind, start: {
        "bill": bill, "n": bill[:2] + " " + bill[2:], "title": f"the title of {bill}", "year": 2026,
        "term": "2025-2026", "kind": kind, "video_id": "VID1", "start": start, "state": "stated",
        "time": "10:00", "venue": "LOB 302"}
    items = [item("SB459", "executive session", 100), item("SB414", "executive session", 900),
             item("SB500", "public hearing", 1500), item("SB600", "executive session", 2000)]
    act = lambda rec, code, y, n: {"act": "report", "committee": "Judiciary", "date": "2026-04-08",
                                   "dated": "vote", "recommendation": rec, "code": code, "yeas": y, "nays": n,
                                   "meeting": "2026-04-08"}
    outcomes = [
        {"bill": "SB459", "kinds": ["executive session"], "outcome": "voted",
         "votes": [act("Inexpedient to Legislate", "ITL", 18, 0)]},
        {"bill": "SB414", "kinds": ["executive session"], "outcome": "voted",
         "votes": [act("Ought to Pass with Amendment", "OTPA", 10, 8)]},
        {"bill": "SB500", "kinds": ["public hearing"], "outcome": "heard"},
        {"bill": "SB600", "kinds": ["executive session"], "outcome": "no vote",
         "voted": {"act": "report", "date": "2026-05-01"}}]
    cmte = {"code": "H10", "name": "Judiciary", "chamber": "H", "bills": {"2025-2026": []},
            "sessions": [{"date": "2026-04-08", "term": "2025-2026", "video_id": "VID1", "items": items,
                          "outcomes": outcomes}],
            "recordings": [{"id": "VID1", "date": "2026-04-08", "term": "2025-2026"}]}
    harness = _HEARD_PRELUDE + r"""
load("renderPage, recordTerms, setPage: (p) => { PAGE = p; }, setTab: (t) => { PAGE_TAB = t; },"
  + " setUp: (u) => { UPCOMING = u; }");
const fx = JSON.parse(fs.readFileSync("./fx.json", "utf8"));
const results = document.querySelector("#results");
const out = {};
try {
  s.setUp([]);
  const terms = s.recordTerms("committee", fx);
  s.setPage({kind: "committee", data: fx, terms, term: terms[0], status: "", vfilter: "", vshow: 0, bshow: 0,
    mshow: 0, vid: "VID1", mopen: {}});
  s.setTab(2); s.renderPage(); out.html = results.innerHTML;
} catch (e) { out.threw = e.constructor.name + ": " + e.message + " " + (e.stack || "").slice(0, 300); }
process.stdout.write("\n@@" + JSON.stringify(out));
"""
    got = _node_app(harness, {"fx.json": json.dumps(cmte)})
    if got is None:
        return "skip", "node, app.js or dom_stub.js is not here"
    assert "threw" not in got, "the Videos tab would not draw: " + got["threw"]
    html = re.sub(r"[ \t\r\n]+", " ", got["html"])
    html = html[html.index('class="vwbills"'):]
    line = lambda n: re.search(r'<li[^>]*><a class="vwbn"[^>]*>' + n + r'</a>(.*?)</li>', html).group(1)
    text = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", h)).strip()
    one, two = line("SB 459"), line("SB 414")
    assert 'class="vwout"' in one and "Inexpedient to Legislate" in text(one) and "(18–0)" in text(one), (
        f"SB 459's line does not say what the committee voted at the meeting, and by how many: {text(one)!r}")
    assert "Ought to Pass with Amendment" in text(two) and "(10–8)" in text(two) and \
        'class="chip cstat s-law"' in two.replace("chip-m ", "").replace("chip-s ", ""), (
            f"SB 414's line does not say its vote in the recommendation's chip: {text(two)!r}")
    for n in ("SB 500", "SB 600"):
        assert "vwout" not in line(n), (
            f"{n}, which the committee did not vote at this meeting, shows a vote (a hearing takes none, and "
            f"another day's vote is not this meeting's): {text(line(n))!r}")
    css = _source("src/pages/app.css")
    assert re.search(r"\n\.vwout\{grid-column:2;", css), "app.css: the vote beside a bill's moments has no rule"
    return "ok", "a voted bill's line carries the chip and counted tally; a hearing's or another day's vote shows none"


# The sign-up box's daily or weekly drawn and sent by app.js under node, with
# a form of the box's own parts: the Turnstile token already in hand, the
# answer a 202, and every request the box makes kept for the check to read.
_FOLLOW_FREQ_JS = """
require("./stub.js");
const fs = require("fs");
let s;
try { s = (0, eval)(fs.readFileSync("./page.js", "utf8") + "; ({followMailForm, followSubmit, FOLLOW_TS})"); }
catch (e) { console.log("LOAD " + e.constructor.name + ": " + e.message); process.exit(1); }
const sent = [];
globalThis.fetch = async (u, init) => { sent.push({ url: String(u), body: JSON.parse(init.body) });
  return { ok: true, status: 202, json: async () => ({ ok: true }) }; };
function form(choice) {
  const st = { textContent: "" }, btn = { disabled: false }, w = { dataset: {} };
  s.FOLLOW_TS.set(w, { token: "pass", err: "", wait: [] });
  const radio = { value: choice, checked: true };
  // The form's busy flag and its place, which a sign-up taken asks for since
  // 18 October 2026; the confirmation itself is _follow_panel_states's.
  return {
    dataset: {}, setAttribute() {}, removeAttribute() {}, parentNode: { querySelector: () => null },
    closest: () => ({ dataset: { fkey: "bill:2026/HB1442" } }),
    querySelector: q => q === ".followstate" ? st : q === ".followsend" ? btn : q === ".followcheck" ? w
      : /frequency/.test(q) && /:checked/.test(q) ? radio : null,
    elements: { email: { value: "reader@example.com" }, website: { value: "" }, frequency: radio },
  };
}
(async () => {
  const html = s.followMailForm("bill:2026/HB1442");
  for (const c of ["weekly", "daily"]) await s.followSubmit({ preventDefault() {} }, form(c));
  process.stdout.write("\\n@@" + JSON.stringify({ html, sent }));
})().catch(e => { console.log("RUN " + e.constructor.name + ": " + e.message); process.exit(1); });
"""


@check("build", "the email sign-up asks daily or weekly as the manage page does, Daily chosen and "
       "told apart in forced colours, and every follow migration has its two commands")
def _follow_signup_frequency():
    """The person, 16 October 2026: a "Daily or weekly" choice beside the
    email field, Daily selected, just before the "Email me updates" button.
    Until then a sign-up always became daily, and only the manage page could
    make it weekly.

    The box as a record's Follow pane draws it (app.js followMailForm, under
    node) carries the manage page's own words and legend for the choice
    (manage.js, "How often"), with Daily the one checked, between the address
    and the button, and no fieldset opened inside a p -- the parser would
    close the p there and leave the button outside the row. followSubmit
    sends the choice it is given, Weekly and Daily each. The endpoints' side
    -- kept with the request, confirmed as weekly, none at all confirmed as
    daily, any other value refused, a subscriber's own kept and the manage
    page saying so where the box asked otherwise, the migration -- is
    tests/follow/'s, whose cases are run here by name so that one taken out
    is missed.

    IN FORCED COLOURS the chosen one is told from the other, in the box
    (app.css .followfreq) and on the manage page (page.js .seg): the system
    paints away the wash and the rule under it, and the radios are out of
    sight, so in Edge with high contrast on the two came out the same (the
    review of 16 October 2026). The chosen one keeps the system's selection
    colours.

    And README.md gives every file in workers/follow/migrations/ its command
    for both databases: a column the Functions write that a database lacks is
    a sign-up answered "on its way" that sends nothing. 0003's paragraph
    names both log lines its absence leaves, the sign-up's and the
    confirmation's, since confirm.js reads the column too."""
    from html.parser import HTMLParser
    if not Path("workers/follow").is_dir():
        return "skip", "no workers/follow here"
    readme = _source("workers/follow/README.md")
    migrations = sorted(p.name for p in Path("workers/follow/migrations").glob("*.sql"))
    assert "0003_pending_frequency.sql" in migrations, "the sign-up's frequency migration is gone"
    untold = [f"{m} on {db}" for m in migrations
              for db in ("graniterecord-follow-preview", "graniterecord-follow")
              # With the sender's own settings file, and the preview's environment:
              # without them wrangler reads the root wrangler.toml, finds no such
              # database by name and calls it an authentication error (the
              # person, 26 October 2026).
              if f"npx wrangler d1 execute {db} --remote --config workers/follow/wrangler.toml"
                 f"{' --env preview' if db.endswith('-preview') else ''}"
                 f" --file workers/follow/migrations/{m}" not in readme]
    assert not untold, "workers/follow/README.md gives no command for " + ", ".join(untold)
    begin = readme.find("sign-up box's daily or weekly")
    told = readme[begin:readme.find("migrations/0003_pending_frequency.sql", begin)] if begin >= 0 else ""
    assert all(f"`follow {x}.error.Error`" in told for x in ("signup", "confirm")), \
        "README.md's paragraph on 0003 no longer says that sign-ups and confirmations both fail without it"

    # Chosen and not chosen, told apart in forced colours: the selection's
    # system colours, held from the system's repainting, on the chosen label.
    def forced(css, seg):
        got = {}
        for ats, sel, body, _ in _css_rules(css):
            if any("forced-colors" in a for a in ats) and \
                    f"{seg} label:has(input:checked)" in [s.strip() for s in sel.split(",")]:
                got.update(_css_decls(body))
        return got.get("forced-color-adjust") == "none" and got.get("background", "").lower() == "highlight"
    style = re.search(r"const STYLE = `(.*?)`;", _source("workers/follow/page.js"), re.S)
    blind = [name for name, css, seg in (
        ("the sign-up box (app.css .followfreq)", _source("src/pages/app.css"), ".followfreq"),
        ("the manage page (page.js .seg)", style.group(1) if style else "", ".seg")) if not forced(css, seg)]
    assert not blind, ("in forced colours the chosen one of two is drawn like the other on "
                       + " and ".join(blind) + ": no Highlight ground for label:has(input:checked)")

    manage = _source("functions/api/follow/manage.js")
    words = dict(re.findall(r'radio\("frequency", "(daily|weekly)", freq, "([^"]+)"', manage))
    legend = re.search(r'<legend class="sr">([^<]+)</legend>\s*\$\{radio\("frequency"', manage)
    assert set(words) == {"daily", "weekly"} and legend, \
        "manage.js's How often control is not where this check reads its words"

    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return "skip", "app.js, dom_stub.js or node is not here"
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text(_FOLLOW_FREQ_JS, encoding="utf-8")
        r = _run([node, "go.js"], cwd=root, capture_output=True, text=True, timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not draw and send the email box under node: " + (r.stderr or r.stdout or "")[-300:])
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    class Box(HTMLParser):
        def __init__(self):
            super().__init__()
            self.radios, self.legend, self.inside_p = [], "", False
            self.fieldset_in_p, self.here, self.texting = False, None, None

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if tag == "p":
                self.inside_p = True
            elif tag == "fieldset" and self.inside_p:
                self.fieldset_in_p = True
            elif tag == "legend":
                self.texting = "legend"
            elif tag == "input" and a.get("type") == "radio" and a.get("name") == "frequency":
                self.here = {"value": a.get("value"), "checked": "checked" in a, "words": ""}
                self.texting = "label"

        def handle_endtag(self, tag):
            if tag == "p":
                self.inside_p = False
            elif tag == "legend":
                self.texting = None
            elif tag == "label" and self.here:
                self.radios.append(self.here)
                self.here, self.texting = None, None

        def handle_data(self, data):
            if self.texting == "legend":
                self.legend += data
            elif self.texting == "label" and self.here:
                self.here["words"] += data

    html = got["html"]
    box = Box()
    box.feed(html)
    drawn = [(x["value"], x["checked"], x["words"].strip()) for x in box.radios]
    want = [("daily", True, words["daily"]), ("weekly", False, words["weekly"])]
    assert drawn == want, f"the email box offers {drawn}, not the manage page's {want} with Daily chosen"
    assert box.legend.strip() == legend.group(1), \
        f"the email box asks {box.legend.strip()!r} where the manage page asks {legend.group(1)!r}"
    at = [html.find('type="email"'), html.find("<fieldset"), html.find("Email me updates")]
    assert -1 not in at and at == sorted(at), \
        "Daily or weekly is not between the address and the Email me updates button"
    assert not box.fieldset_in_p, \
        "the email box opens its fieldset inside a p: the parser closes the p and the row falls apart"
    sent = [(s["url"], s["body"].get("frequency")) for s in got["sent"]]
    assert sent == [("/api/follow/signup", "weekly"), ("/api/follow/signup", "daily")], \
        f"the email box sent {sent} for Weekly and then Daily"

    cases = ("how often is kept with the request", "a frequency the box cannot send is refused",
             "a weekly sign-up is confirmed as weekly", "names no frequency is confirmed as daily",
             "keeps how often they chose, and is told so", "shows only its own notices",
             "frequency migration brings a pending table")
    r = _run([node, "--disable-warning=ExperimentalWarning", "--test", "--test-reporter=tap",
              "--test-name-pattern=" + "|".join(cases), "tests/follow/index.js"],
             capture_output=True, text=True)
    out = r.stdout + r.stderr
    passed = [c for c in cases
              if re.search(rf"^ok \d+ - [^\n]*{re.escape(c)}(?![^\n]*# SKIP)", out, re.M)]
    assert r.returncode == 0 and len(passed) == len(cases), (
        "tests/follow/ no longer passes the frequency cases "
        + ", ".join(repr(c) for c in cases if c not in passed) + ": " + out.strip()[-400:])
    return "ok", (f"the box draws {words['daily']} (chosen) and {words['weekly']} under "
                  f"{legend.group(1)!r} and sends each, told apart in forced colours there and on "
                  f"the manage page; {len(cases)} cases pass; "
                  f"{len(migrations)} migrations, each told for both databases")


@check("frontend", "who holds the seats is at the head of the Legislators tab, under the presiding "
                   "officers and over the roster, and on a phone each chamber's bar over one short "
                   "line, in English and in Spanish")
def _seat_totals_at_top():
    """The owner's walk of 7 November 2026, C: "Who holds the seats" moves
    from the bottom of the Legislators tab to the top, under the presiding
    officers, and on a phone each chamber is one short line -- "Senate 16 R
    &middot; 8 D", "House 212 R &middot; 169 D &middot; 1 I &middot; 18
    vacant" -- not the tall block of bars, legends and thresholds. And (the
    walk of 8 November) a chart on a phone as well: the chamber's bar,
    thinner, over its line.

    Read off the fixture's built page in both languages: the block once,
    between the presiding officers and the roster; a short line for each
    chamber its bar draws, the last part of that chamber's block, under its
    bar, saying the bar's own counts in its order, each party's letter for
    the eye and its name for a screen reader, and the vacant seats last; and
    app.css showing at a phone's width the bar and the line and not the
    count of seats, the legend or the thresholds, and wider the bar and all
    of those but the line. (The Members-Elect tab's are
    _elect_tab_like_legislators's.)

    THE PRESIDING OFFICERS FIRST. The fixture has no officers.json, so its
    page draws no Presiding Officers and the page alone cannot say the block
    is under them (the review of 8 November 2026): where it draws none, the
    order is read off the Legislators panel as officials_html writes it --
    the presiding officers, then the block, then the roster."""
    import html as _h
    shared, _base, _ran, _days = _fixture_site_shared()
    bad = []
    src = _source("src/pages/build_pages.py")
    panel = re.search(r'\("legislators", say\(lang, "of\.tab\.legislators", "Legislators"\), len\(legs\),'
                      r'(.*?)\n\s*\("federal",', src, re.S)
    order = [panel.group(1).find(x) if panel else -1
             for x in ("OT.presiding(", '<div class="comp-wrap comp-top">', "roster_section(")]
    if -1 in order or order != sorted(order):
        bad.append(f"officials_html does not write the Legislators panel as the presiding officers, "
                   f"then who holds the seats, then the roster (at {order})")
    for lang, rel, words in (("en", "officials.html", ("Senate", "House", "vacant")),
                             ("es", "es/officials.html", ("Senado", "Cámara", "vacante"))):
        page = (shared / "site" / rel).read_text(encoding="utf-8")
        i = page.find('<div class="twnpane" id="legislators"')
        j = page.find('<div class="twnpane"', i + 1)
        pane = page[i:j if j > 0 else len(page)]
        top, roster = pane.find('<div class="comp-wrap comp-top">'), pane.find('<section class="roster"')
        pres = pane.find('<section class="ofpres"')
        if i < 0 or not 0 <= top < roster or pres > top or pane.count('class="comp-wrap') != 1:
            bad.append(f"{rel}: who holds the seats is not once, under the presiding officers and "
                       f"over the roster (at {top}, the roster at {roster}, the officers at {pres})")
            continue
        wrap = pane[top:roster]
        bars = re.findall(r'<div class="comp"><div class="compline"><b>([^<]+)</b>.*?'
                          r'<div class="plegend">(.*?)</div>', wrap, re.S)
        lines = re.findall(r'<p class="compshort"><b>([^<]+)</b> (.*?)</p>', wrap)
        # Each line closes its chamber's block, under the bar.
        closing = re.findall(r'<div class="pbar2">.*?<p class="compshort"><b>([^<]+)</b>.*?</p></div>',
                             wrap, re.S)
        if closing != [c for c, _t in lines]:
            bad.append(f"{rel}: the short lines {[c for c, _t in lines]} do not each close their "
                       f"chamber's block under its bar ({closing})")
        if not bars or [b for b, _l in bars] != [c for c, _t in lines] or \
                [b for b, _l in bars] != list(words[:2]):
            bad.append(f"{rel}: the bars are for {[b for b, _l in bars]} and the short lines for "
                       f"{[c for c, _t in lines]}")
            continue
        for (ch, legend), (_c, text) in zip(bars, lines):
            seen = [(c, n) for c, n in re.findall(r'<span class="pdot seg-([A-Z?]+)"></span>[^<]*<b>(\d+)</b>',
                                                  legend)]
            said = re.findall(r'(\d+) <span aria-hidden="true">([^<]+)</span><span class="sr">[^<]+</span>',
                              text)
            vac = [(c, n) for c, n in seen if c == "V"]
            if [(c, n) for c, n in seen if c != "V"] != [(c, n) for n, c in said]:
                bad.append(f"{rel}: the {ch} line says {said}, its bar {seen}")
            # Each count whole (.csb), the vacant seats the last of them.
            counts = [_h.unescape(re.sub(r"<[^>]+>", "", c))
                      for c in re.findall(r'<span class="csb">((?:[^<]|<span[^>]*>[^<]*</span>)*)</span>', text)]
            gone = [m.group(1) for c in counts for m in [re.fullmatch(r"(\d+) " + words[2] + r"s?", c)] if m]
            if [n for _c, n in vac] != gone or len(counts) != len(seen) or (
                    vac and not re.fullmatch(r"\d+ " + words[2] + r"s?", counts[-1])):
                bad.append(f"{rel}: the {ch} line's counts are {counts}, its bar's {seen}")
    css = _source("src/pages/app.css")
    phone = re.search(r"@media \(max-width:38\.75em\)\{(\s*:where\(body\.pg\) \.comp-top \.comp[^@]*?)\n\}", css)
    rules = phone.group(1) if phone else ""

    def _phone_hides_bar(rules):
        """True where the phone's rules hide the bar or its block (none,
        hidden, or no height), or give the bar no height of its own."""
        hides = lambda d: re.search(  # noqa: E731
            r"display:\s*none|visibility:\s*hidden|(?<![-\w])(?:max-)?height:\s*0(?![.\d])", d)
        gone = [s.strip() for sel, d in re.findall(r"([^{}]+)\{([^}]*)\}", rules) if hides(d)
                for s in sel.split(",")
                if re.search(r"(?:\.pbar2|\.comp-top(?: >)? \.comp|\.comp-top)$", s.strip())]
        return bool(gone) or not re.search(
            r":where\(body\.pg\) \.comp-top \.comp > \.pbar2\{height:[1-9]", rules)
    if not re.search(r":where\(body\.pg\) \.compshort\{display:none;", css) or not phone or not all(
            x in rules for x in (
                ":where(body.pg) .comp-top .comp > .compline,:where(body.pg) .comp-top .comp > .plegend,",
                ":where(body.pg) .comp-top .comp > p:not(.compshort){display:none}",
                ":where(body.pg) .comp-top .comp > .compshort{display:block")) or \
            re.search(r"\.pbar2\{[^}]*display:none", rules) or _phone_hides_bar(rules):
        bad.append("app.css does not show, at a phone's width only, each chamber's bar over its short "
                   "line, without the count of seats, the legend and the thresholds")
    assert not bad, "\n  ".join(bad)
    return "ok", ("in both languages, once, under the presiding officers and over the roster; a "
                  "line for each chamber in its bar's counts, under its bar, for a phone's width "
                  "alone, with the bar")


_UNTIL_NODE = r"""
// The reader's clock, fixed at __DAY__ 09:30 local, and a page of five
// elements: retiring on the day, the day after and the day before, one that
// names no day, and one the build already hid.
const RealDate = Date;
global.Date = class extends RealDate {
  constructor(...a) { if (a.length) super(...a); else super(__Y__, __M__, __D__, 9, 30); }
};
const els = ["2026-12-02", "2026-12-03", "2026-12-01", "after the recount", "2026-12-09"]
  .map((u, i) => ({hidden: i === 4, getAttribute: n => n === "data-until" ? u : null}));
global.document = {readyState: "complete", documentElement: {},
  querySelectorAll: sel => sel === "[data-until]" ? els : []};
"""


@check("frontend", "what retires on a day is hidden by the reader's own clock from that day on "
                   "(components.js's behaviour, through untilAttrs)")
def _until_by_the_reader():
    """The browser's half of retiring on Organization Day (the person's
    decisions of 16 October 2026): a page built on 1 December and read on the
    3rd -- a night held, a copy a browser kept -- must show no member-elect.
    components.js's behaviour judges every element carrying data-until by
    untilAttrs with the reader's own date, when the page loads and whenever it
    draws itself again, and hides it from its day on; it only ever hides. Run
    in node on a stand-in page, with the reader's clock at 2 December and then
    at 1 December. untilAttrs itself is held to components.py's until_attrs by
    _components_agree.

    And no page's own style can bring one back (the review of 16 October
    2026): hidden loses to any display a page's own rule gives an element, so
    app.css, which every page loads, says that an element with data-until
    and hidden is not drawn, with !important."""
    js = _components_js()
    a, b = js.find("// BEHAVIOUR:START"), js.find("// BEHAVIOUR:END")
    assert 0 < a < b and "[data-until]" in js[a:b] and "untilAttrs(" in js[a:b], (
        "components.js's behaviour no longer judges [data-until] by untilAttrs")
    css = _source("src/pages/app.css")
    assert re.search(
        r"(?m)^\[data-until\]\[hidden\]\s*\{\s*display\s*:\s*none\s*!important\s*;?\s*\}",
        css), (
        "app.css does not say [data-until][hidden]{display:none!important}: a "
        "member-elect block a page styles as flex or grid would be drawn after the day they "
        "take office")
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        assert not os.environ.get("GITHUB_ACTIONS"), "node is not on PATH on the nightly"
        return "skip", "node is not on PATH, so the behaviour could not be run"
    got = {}
    for day in ("2026-12-02", "2026-12-01"):
        y, m, d = (int(x) for x in day.split("-"))
        prog = (_UNTIL_NODE.replace("__DAY__", day).replace("__Y__", str(y))
                .replace("__M__", str(m - 1)).replace("__D__", str(d))
                + js + '\nprocess.stdout.write("\\n@@" + JSON.stringify(els.map(e => e.hidden)));\n')
        r = _node_file(node, prog, capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "components.js would not run on the stand-in page: " + (r.stderr or "")[-300:])
        got[day] = json.loads(r.stdout.rsplit("@@", 1)[1])
    want = {"2026-12-02": [True, False, True, True, True],
            "2026-12-01": [False, False, True, True, True]}
    assert got == want, (f"hidden, by the reader's day, for elements retiring on 2, 3 and 1 "
                         f"December, on no day, and one the build hid: {got}, not {want}")
    return "ok", ("on 2 December the element retiring that day is hidden and the next day's is "
                  "not; on 1 December neither; no day is hidden at once; the build's hidden stays")
