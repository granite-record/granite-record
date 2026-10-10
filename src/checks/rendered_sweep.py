#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-08.3
"""
The rendered sweep: a built site measured as a reader's browser draws it.

    python3 src/checks/rendered_sweep.py                       # every page, every view
    python3 src/checks/rendered_sweep.py --report logs/sweep_after.json
    python3 src/checks/rendered_sweep.py --pages bill-law,learn --widths 375 --modes light,dark
    python3 src/checks/rendered_sweep.py --compare logs/sweep_before.json
    python3 src/checks/rendered_sweep.py --list                # the pages, as resolved

WHY THIS EXISTS

preflight reads files. A size set in a token, a colour mixed from two others,
a heading that turns out smaller than the paragraph under it, a row pushed
31px past a phone's edge by two long chips: those exist only on a drawn page,
and every one of them has been found by a person or a survey before a check.
So before a front-end release this serves the built site on the loopback
address, has headless Chrome draw a fixed list of page types (PAGES) at 1366,
768 and 375 pixels wide, in the light theme, the dark theme, Windows' forced
colours and at a browser text size of 24px, and measures on every run:

  - every element that owns text: its size, and its contrast against the
    first opaque ground behind it at its own WCAG threshold (4.5:1, or 3:1
    from 24px, or 18.66px bold);
  - every horizontal overflow: the page scrolling sideways, an element
    sticking out past the edge, text cut off inside its box, a box that
    scrolls inside itself, and a placeholder wider than its field;
  - text drawn over other text, and text the page's left edge cuts off,
    which no overflow sees because each box is inside its parent;
  - the visible h1s, a heading smaller than what it heads, and the longest
    lines of prose.

Each run saves a screenshot (the top of the page, to --shot-cap pixels), and
the whole sweep writes ONE JSON report, whose "summary" is the part to read
first. With --compare it also says what moved against an earlier report.
It exits 1 when a view could not be measured or a page asked for anything
outside (below), and 0 otherwise: what it found is the report's to say, not
its exit status's, because a baseline taken before a fix is meant to find
things.

The 24px runs are the reason the browser's own setting is in the list at all:
a reader who has made their text larger should get larger text, and the
report says on how many page views it grew. Sizes are reported as they would
be at the browser's default of 16px ("at16"), so a 24px run is judged by the
same floors as the rest.

WHAT IT ASKS. Nothing but the loopback address, where it serves the site
itself, and Google Fonts, so that the real faces load. Chrome is started by
sweep_browser.js with every other host name resolving to nothing, and every
request a page makes elsewhere is counted in the report ("outside"). It never
writes into the site, and it writes nothing but the report and the
screenshots.

WHAT IT CANNOT SEE. Text drawn into an image; a ground drawn by a gradient
or an image (the run counts those, "imgGround", and judges against the
colour behind them); a state no step opens (a popover, a hover); a focus
ring (not measured yet); and whether a selected state stays distinct in
forced colours (the screenshots show it; nothing counts it yet). It is not
in preflight because preflight has no browser and must not need one: it is
a step before a front-end release, run by a person.

It needs Chrome (or --chrome PATH) and node 22 or later, which has a
WebSocket of its own.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import functools
import http.server
import io
import json
import os
import shutil
import subprocess
import tempfile
import threading
from datetime import datetime, timezone

import child

# ------------------------------------------------------------------ the views --

# Desktop, a tablet held upright, a phone. The phone is emulated as one (touch,
# and the viewport the page's own meta tag asks for).
WIDTHS = {1366: (900, False), 768: (1024, False), 375: (812, True)}

# The theme, Windows' forced colours, and the browser's text size at 24px
# (Chrome's "Very large"), which is light, at its 16px theme otherwise.
MODES = {"light": 16, "dark": 16, "forced": 16, "text24": 24}

# ------------------------------------------------------------------ the pages --
#
# A FIXED LIST, so that two reports compare. Each record page names the one
# the polish surveys measured, and a rule for finding another of its kind
# where that one has changed or gone; the report says which was used and why.
# `steps` open a state of the page: a tab by its words, or an element by a
# selector.

PAGES = [
    {"name": "home", "path": "index.html"},
    {"name": "bills", "path": "bills.html"},
    {"name": "bill-law", "bill": ("2025-2026", "HB1681"), "rule": "law",
     "why": "a bill that became law: the full rail, chapter and effective date"},
    {"name": "bill-killed", "bill": ("2025-2026", "HB1083"), "rule": "killed",
     "why": "a bill killed by a roll call"},
    {"name": "bill-killed-votes", "bill": ("2025-2026", "HB1083"), "rule": "killed",
     "steps": [{"tab": "^Votes"}], "why": "its Votes tab: the vote rings"},
    {"name": "bill-study", "bill": ("2025-2026", "HB410"), "rule": "study",
     "why": "a bill sent to interim study"},
    # Added by the review of the polish foundation (8 October 2026), the two
    # states the list did not open and where it found a page scrolling
    # sideways at 768 and a vote's word drawn over its tally at 24px.
    {"name": "bill-law-text", "bill": ("2025-2026", "HB1681"), "rule": "law",
     "steps": [{"tab": "^Bill Text"}], "why": "its Bill Text tab: the versions and the text"},
    {"name": "member-votes", "path": "legislator/joe-alexander-hills-29.html",
     "dir": "legislator", "steps": [{"tab": "^Votes"}],
     "why": "a member's Votes tab: the table of every roll call"},
    {"name": "legislators-towns", "path": "legislators.html"},
    {"name": "legislators-last", "path": "legislators.html",
     "steps": [{"click": "#tab-legislators"}, {"click": "#tab-last"}]},
    {"name": "legislators-county", "path": "legislators.html",
     "steps": [{"click": "#tab-legislators"}, {"click": "#tab-county"}]},
    {"name": "legislators-seat", "path": "legislators.html",
     "steps": [{"click": "#tab-legislators"}, {"click": "#tab-seat"}]},
    {"name": "member", "path": "legislator/joe-alexander-hills-29.html", "dir": "legislator"},
    {"name": "committees", "path": "committees.html"},
    {"name": "committee", "path": "committee/H64.html", "dir": "committee"},
    {"name": "calendar", "path": "calendar.html"},
    # Added with the Week view of 9 October 2026, Monday to Friday beside the
    # month: a week in session, its own page, in the List view and the Week
    # view, where the tab's own week is often quiet.
    {"name": "calendar-busy", "path": "calendar/2026-W08.html", "dir": "calendar",
     "why": "a week in session, 16-20 February 2026, in the List view"},
    {"name": "calendar-week", "path": "calendar/2026-W08.html", "dir": "calendar",
     "steps": [{"click": '#calbar [data-view="week"]'}],
     "why": "the same week in the Week view"},
    {"name": "session-day", "path": "session/H/2026-02-19.html", "dir": "session/H",
     "latest": True},
    {"name": "town", "path": "town/goffstown.html", "dir": "town"},
    {"name": "learn", "path": "learn/how-a-bill-becomes-law.html"},
    {"name": "numbers", "path": "learn/by-the-numbers.html"},
    {"name": "data", "path": "data.html"},
    {"name": "about", "path": "about.html"},
    {"name": "404", "path": "no-such-page-here.html", "missing": True,
     "why": "a path that is not there, answered with 404.html as the host does"},
]

# What a bill must be to stand for its kind, read from the term's index row.
RULES = {
    "law": lambda r: r.get("kind") == "law",
    "killed": lambda r: r.get("kind") == "done" and "kill" in str(r.get("status", "")).lower()
    and (r.get("nrc") or 0) > 0,
    "study": lambda r: r.get("kind") == "study",
}


def _bill_path(row):
    return f"bill/{row['year']}/{row['id'].lower()}.html"


def resolve_pages(site):
    """[page] with "path" settled and "note" saying what was used, for every
    page of PAGES. A page that cannot be found is kept with "missing_why", so
    the report says it was not measured rather than leaving it out."""
    site = Path(site)
    rows_by_term = {}

    def rows(term):
        if term not in rows_by_term:
            f = site / "idx" / f"{term}.json"
            try:
                rows_by_term[term] = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                rows_by_term[term] = []
        return rows_by_term[term]

    out = []
    for p in PAGES:
        p = dict(p)
        if "bill" in p:
            term, bid = p["bill"]
            rule = RULES[p["rule"]]
            row = next((r for r in rows(term) if r.get("id") == bid), None)
            if row and rule(row) and (site / _bill_path(row)).is_file():
                p["path"], p["note"] = _bill_path(row), f"{row.get('n', bid)} ({row['year']})"
            else:
                pick = next((r for r in rows(term) if rule(r) and (site / _bill_path(r)).is_file()),
                            None)
                if pick:
                    p["path"] = _bill_path(pick)
                    p["note"] = (f"{pick.get('n', pick['id'])} ({pick['year']}), because {bid} "
                                 f"of {term} is {'not ' + p['rule'] if row else 'not in the index'}")
                else:
                    p["path"], p["missing_why"] = "", f"no bill of {term} is {p['rule']}"
        elif p.get("missing"):
            p["note"] = p.get("why", "")
        elif not (site / p["path"]).is_file():
            d = site / p.get("dir", "-")
            found = sorted(d.glob("*.html")) if d.is_dir() else []
            if found:
                f = found[-1] if p.get("latest") else found[0]
                p["note"] = f"{p['path']} is not there; {f.relative_to(site).as_posix()} instead"
                p["path"] = f.relative_to(site).as_posix()
            else:
                p["missing_why"] = f"{p['path']} is not in the site"
        out.append(p)
    return out


# ------------------------------------------------------------------ the server --

class _Site(http.server.SimpleHTTPRequestHandler):
    """The built site, as the host serves it: a path without its .html finds
    the page, a missing one gets 404.html with a 404, and the types are
    stated rather than read from the Windows registry, which has served .js
    as text/plain."""

    extensions_map = {"": "application/octet-stream", ".html": "text/html; charset=utf-8",
                      ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                      ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
                      ".ico": "image/x-icon", ".webmanifest": "application/manifest+json",
                      ".xml": "application/xml", ".txt": "text/plain; charset=utf-8",
                      ".csv": "text/csv; charset=utf-8", ".pdf": "application/pdf"}

    def log_message(self, *args):
        pass

    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.exists(path) and os.path.exists(path + ".html"):
            self.path = self.path.split("?", 1)[0].split("#", 1)[0] + ".html"
            path += ".html"
        if not os.path.exists(path):
            page = Path(self.directory) / "404.html"
            if page.is_file():
                body = page.read_bytes()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                return io.BytesIO(body)
        return super().send_head()


def serve(site):
    """(server, base URL): the site on a free port of the loopback address,
    in a thread of its own."""
    handler = functools.partial(_Site, directory=str(Path(site).resolve()))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


# ------------------------------------------------------------------ the browser --

def find_chrome(given=None):
    """The Chrome to drive: --chrome, $CHROME, or the usual places."""
    for c in (given, os.environ.get("CHROME"),
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              shutil.which("google-chrome"), shutil.which("chromium"),
              shutil.which("chromium-browser"), shutil.which("chrome")):
        if c and Path(c).is_file():
            return str(c)
    return None


def plan_runs(pages, widths, modes):
    runs = []
    for p in pages:
        if p.get("missing_why"):
            continue
        for w in widths:
            h, mobile = WIDTHS[w]
            for m in modes:
                runs.append({"id": f"{p['name']}_{w}_{m}", "page": p["name"], "path": p["path"],
                             "steps": p.get("steps", []), "width": w, "height": h,
                             "mobile": mobile, "mode": m, "standard": MODES[m]})
    return runs


def drive(chrome, base, runs, shots, shot_cap, progress=True):
    """(browser, [run]): every run measured by sweep_browser.js."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-sweep-"))
    try:
        job = tmp / "runs.json"
        job.write_text(json.dumps({"chrome": chrome, "profile": str(tmp / "profile"),
                                   "base": base, "shots": str(shots) if shots else None,
                                   "shotCap": shot_cap, "runs": runs}), encoding="utf-8")
        proc = subprocess.Popen(["node", str(_paths.locate("sweep_browser.js")), str(job)],
                                stdout=subprocess.PIPE, stderr=None if progress else subprocess.DEVNULL,
                                text=True, encoding="utf-8")
        browser, got = None, []
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "browser" in rec:
                browser = rec
            else:
                got.append(rec)
        proc.wait()
        if proc.returncode != 0 and not got:
            raise SystemExit(f"sweep_browser.js stopped ({proc.returncode}) before any page was "
                             "measured; its own words are above")
        return browser, got
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------ the report --

def _share(sizes, below):
    total = sum(sizes.values())
    return round(100 * sum(n for s, n in sizes.items() if float(s) < below) / total, 1) if total else None


def _merge(into, sizes):
    for s, n in sizes.items():
        into[s] = into.get(s, 0) + n
    return into


def _median_size(sizes):
    """The size half the characters are under, from {size: chars}."""
    items = sorted((float(s), n) for s, n in sizes.items())
    half, run = sum(n for _, n in items) / 2, 0
    for s, n in items:
        run += n
        if run >= half:
            return s
    return None


def summarise(runs):
    """The numbers a person reads first, from the runs."""
    ok = [r for r in runs if "m" in r]
    s = {"runs": len(runs), "measured": len(ok),
         "errors": [f"{r['id']}: {r['error']}" for r in runs if r.get("error")]}

    def text_of(sel):
        sizes = {}
        for r in sel:
            _merge(sizes, r["m"]["text"]["sizes"])
        return sizes

    # The shares are of the light and dark runs, as the surveys counted them;
    # the smallest is over every run at the browser's 16px, forced colours
    # included. A 24px run is judged on its own, below.
    themed = [r for r in ok if r["mode"] in ("light", "dark")]
    at16 = [r for r in ok if MODES[r["mode"]] == 16 and r["m"]["text"]["min"]]
    sizes = text_of(themed)
    s["text"] = {
        "what": "characters in the light and dark runs, by their size at the browser's 16px",
        "chars": sum(sizes.values()),
        "share_under_16px": _share(sizes, 16), "share_under_14px": _share(sizes, 14),
        "share_under_13px": _share(sizes, 13),
        "smallest_px": min((r["m"]["text"]["min"] for r in at16), default=None),
        "by_width": {str(w): {"share_under_16px": _share(text_of([r for r in themed if r["width"] == w]), 16),
                              "smallest_px": min((r["m"]["text"]["min"] for r in at16
                                                  if r["width"] == w), default=None)}
                     for w in sorted({r["width"] for r in themed}, reverse=True)},
        "by_page_1366_light": {r["page"]: {"share_under_16px": _share(r["m"]["text"]["sizes"], 16),
                                           "smallest_px": r["m"]["text"]["min"]}
                               for r in ok if r["width"] == 1366 and r["mode"] == "light"},
        "views_with_text_under_13px": sum(1 for r in at16 if r["m"]["text"]["min"] < 13),
        "views_with_mixed_case_under_14px": sum(1 for r in at16 if r["m"]["text"]["mixedCase13"]),
    }
    smallest = min(at16, key=lambda r: r["m"]["text"]["min"], default=None)
    if smallest:
        s["text"]["smallest_where"] = {"run": smallest["id"], **(smallest["m"]["text"]["minAt"] or {})}
    # THE BROWSER'S TEXT SIZE: did the text grow? A 24px run against the
    # light run of the same page and width, by the median character.
    light = {(r["page"], r["width"]): r for r in ok if r["mode"] == "light"}
    grew = []
    for r in ok:
        if r["mode"] != "text24" or (r["page"], r["width"]) not in light:
            continue
        a = _median_size(light[(r["page"], r["width"])]["m"]["text"]["sizes"])
        b = _median_size({str(float(k) * 24 / 16): v for k, v in r["m"]["text"]["sizes"].items()})
        grew.append({"run": r["id"], "median_px_at_16": a, "median_px_at_24": b,
                     "grew": bool(a and b and b > a * 1.2)})
    big = [r for r in ok if r["mode"] == "text24" and r["m"]["text"]["minAt"]]
    s["text_size_24px"] = {"views": len(grew), "text_grew": sum(1 for g in grew if g["grew"]),
                           "smallest_drawn_px": min((r["m"]["text"]["minAt"]["px"] for r in big),
                                                    default=None),
                           "share_under_16px_at_16": _share(text_of(big), 16),
                           "what": "a 24px run's median character against the 16px light run of "
                                   "the same page and width; grown means by a fifth or more. The "
                                   "share is of its text scaled back to a 16px setting, so a page "
                                   "that ignores the setting reads small here",
                           "views_list": grew}
    fails = [dict(f, run=r["id"]) for r in ok for f in r["m"]["contrast"]["fails"]]
    s["contrast"] = {
        "measured": sum(r["m"]["contrast"]["measured"] for r in ok),
        "failures": sum(r["m"]["contrast"]["failures"] for r in ok),
        "runs_with_failures": sorted({r["id"] for r in ok if r["m"]["contrast"]["failures"]}),
        "by_mode": {m: sum(r["m"]["contrast"]["failures"] for r in ok if r["mode"] == m)
                    for m in MODES},
        "lowest": {m: min(({"run": r["id"], **r["m"]["contrast"]["lowest"]} for r in ok
                           if r["mode"] == m and r["m"]["contrast"]["lowest"]),
                          key=lambda x: x["ratio"] / x["need"], default=None)
                   for m in MODES},
        "first_failures": fails[:25],
    }
    s["overflow"] = {
        "sideways": sorted(r["id"] for r in ok if r["m"]["overflow"]["sideways"]),
        "elements_past_the_edge": sum(len(r["m"]["overflow"]["poking"]) for r in ok),
        "runs_with_elements_past_the_edge": sorted(r["id"] for r in ok if r["m"]["overflow"]["poking"]),
        "text_cut_off": sum(1 for r in ok for c in r["m"]["overflow"]["clipped"] if not c["ellipsis"]),
        "placeholders_cut_off": sorted({f"{r['page']} {r['width']} {p['sig']}" for r in ok
                                        for p in r["m"]["overflow"]["placeholders"] if not p["fits"]}),
        "boxes_that_scroll_sideways": sum(len(r["m"]["overflow"]["scrollers"]) for r in ok),
    }
    # TEXT ON TEXT. Two words drawn one over the other, or a word the page's
    # left edge cuts off, are unreadable whatever their size and contrast; the
    # overflow above never sees them, because each box is inside its parent.
    # A report from before the measure existed has no "overlap" and counts 0.
    lap = [r for r in ok if r["m"].get("overlap")]
    s["overlap"] = {
        "views": sorted(r["id"] for r in lap if r["m"]["overlap"]["count"]),
        "pairs": sum(r["m"]["overlap"]["count"] for r in lap),
        "cut_at_the_left_edge": sorted(r["id"] for r in lap if r["m"]["overlap"]["edgeCut"]),
        "first": [dict(p, run=r["id"]) for r in lap for p in r["m"]["overlap"]["pairs"]][:25],
    }
    # A screenshot is evidence only if it shows the view that was measured.
    s["shots_not_as_measured"] = sorted(f"{r['id']}: {r['shotWrong']}" for r in ok
                                        if r.get("shotWrong"))
    s["headings"] = {
        "views_without_one_visible_h1": sorted(r["id"] for r in ok if len(r["m"]["headings"]["h1"]) != 1),
        "h1_px_1366_light": {r["page"]: [h["px"] for h in r["m"]["headings"]["h1"]]
                             for r in ok if r["width"] == 1366 and r["mode"] == "light"},
        "smaller_than_what_they_head_1366_light": sum(len(r["m"]["headings"]["rank"]) for r in ok
                                                      if r["width"] == 1366 and r["mode"] == "light"),
    }
    longest = [r["m"]["lines"]["widest"][0]["cpl"] for r in ok if r["m"]["lines"]["widest"]]
    s["lines"] = {"longest_cpl": max(longest, default=None),
                  "views_over_80": sum(1 for r in ok if r["m"]["lines"]["over80"])}
    s["network"] = {"outside": sorted({u for r in runs for u in r.get("outside", [])}),
                    # The 404 page's own answer is the one 404 wanted.
                    "failed_on_the_site": sorted({u for r in runs for u in r.get("failed", [])
                                                  if u != f"404 /{r['path']}"})[:30],
                    "page_errors": sorted({e for r in runs for e in r.get("errors", [])})[:20],
                    "fonts_failed": sorted({f for r in ok for f in r["m"]["fontsFailed"]})}
    return s


def compare(before, after):
    """What moved between two reports' summaries, in the few numbers that
    matter; the full runs are in each."""
    a, b = before.get("summary", {}), after.get("summary", {})

    def get(d, *ks):
        for k in ks:
            d = (d or {}).get(k)
        return d
    rows = [("share of text under 16px", "text", "share_under_16px"),
            ("share of text under 13px", "text", "share_under_13px"),
            ("smallest text, px", "text", "smallest_px"),
            ("contrast failures", "contrast", "failures"),
            ("page views scrolling sideways", "overflow", "sideways"),
            ("elements past the edge", "overflow", "elements_past_the_edge"),
            ("views where 24px text grew", "text_size_24px", "text_grew"),
            ("pairs of text drawn over each other", "overlap", "pairs")]
    out = {}
    for label, *ks in rows:
        x, y = get(a, *ks), get(b, *ks)
        x = len(x) if isinstance(x, list) else x
        y = len(y) if isinstance(y, list) else y
        out[label] = {"before": x, "after": y}
    return out


def _build_stamp(site):
    try:
        b = json.loads((Path(site) / "build.json").read_text(encoding="utf-8"))
        return {"finished": b.get("finished"), "ok": b.get("ok")}
    except (OSError, ValueError):
        return None


def _commit():
    try:
        r = child.run(["git", "-C", str(_paths.ROOT), "rev-parse", "HEAD"], capture_output=True,
                      text=True, timeout=20)
        return r.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def headline(s):
    t, c, o = s["text"], s["contrast"], s["overflow"]
    lines = [
        f"{s['measured']} of {s['runs']} views measured"
        + (f"; {len(s['errors'])} could not be ({s['errors'][0]})" if s["errors"] else ""),
        f"text: {t['share_under_16px']}% of characters under 16px, {t['share_under_13px']}% under "
        f"13px; the smallest {t['smallest_px']}px"
        + (f" ({t['smallest_where'].get('sig')}, {t['smallest_where'].get('run')})"
           if t.get("smallest_where") else ""),
        f"browser text at 24px: grew on {s['text_size_24px']['text_grew']} of "
        f"{s['text_size_24px']['views']} views",
        f"contrast: {c['failures']} failures in {c['measured']:,} measurements "
        f"({', '.join(f'{m} {n}' for m, n in c['by_mode'].items())})",
        f"overflow: {len(o['sideways'])} views scroll sideways, {o['elements_past_the_edge']} "
        f"elements past the edge, {o['text_cut_off']} boxes cut text off, "
        f"{len(o['placeholders_cut_off'])} placeholders do not fit",
        f"text on text: {s['overlap']['pairs']} pairs drawn over each other on "
        f"{len(s['overlap']['views'])} views; text cut off at the left edge on "
        f"{len(s['overlap']['cut_at_the_left_edge'])}"
        + (f"; {len(s['shots_not_as_measured'])} SCREENSHOTS NOT AS MEASURED"
           if s["shots_not_as_measured"] else ""),
        f"headings: {len(s['headings']['views_without_one_visible_h1'])} views without exactly one "
        f"visible h1; longest prose line {s['lines']['longest_cpl']} characters",
        f"network: {len(s['network']['outside'])} requests outside the loopback address and "
        f"Google Fonts; {len(s['network']['fonts_failed'])} faces failed to load",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", default="site", help="the built site to serve (default site/)")
    ap.add_argument("--report", default="logs/rendered_sweep.json",
                    help="where the one JSON report goes")
    ap.add_argument("--shots", help="where the screenshots go (default: beside the report, "
                                    "in a folder named after it)")
    ap.add_argument("--no-shots", action="store_true", help="measure without screenshots")
    ap.add_argument("--shot-cap", type=int, default=2400,
                    help="the most of a page a screenshot takes, in CSS pixels (default 2400)")
    ap.add_argument("--pages", help="only these pages, by name, comma-separated (--list names them)")
    ap.add_argument("--widths", default="1366,768,375")
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--chrome", help="the Chrome to drive (default: found in the usual places)")
    ap.add_argument("--compare", help="an earlier report: say what moved")
    ap.add_argument("--list", action="store_true", help="print the pages, resolved, and stop")
    ap.add_argument("--quiet", action="store_true", help="no line per view while it runs")
    a = ap.parse_args()

    site = Path(a.site)
    if not (site / "index.html").is_file():
        raise SystemExit(f"{site} holds no built site (no index.html): build it first, "
                         "python3 build_all.py --local")
    pages = resolve_pages(site)
    if a.pages:
        want = set(a.pages.split(","))
        unknown = want - {p["name"] for p in pages}
        if unknown:
            raise SystemExit(f"no page called {', '.join(sorted(unknown))}; --list names them")
        pages = [p for p in pages if p["name"] in want]
    if a.list:
        for p in pages:
            print(f"{p['name']:20} {p.get('path') or '-':45} {p.get('missing_why') or p.get('note') or ''}")
        return 0
    widths = [int(w) for w in a.widths.split(",")]
    modes = a.modes.split(",")
    bad = [w for w in widths if w not in WIDTHS] + [m for m in modes if m not in MODES]
    if bad:
        raise SystemExit(f"not a width or a mode here: {', '.join(map(str, bad))} "
                         f"(widths {', '.join(map(str, WIDTHS))}; modes {', '.join(MODES)})")
    chrome = find_chrome(a.chrome)
    if not chrome:
        raise SystemExit("no Chrome found: pass --chrome PATH, or set CHROME")
    if not shutil.which("node"):
        raise SystemExit("no node on the PATH: the browser is driven by sweep_browser.js")

    report = Path(a.report)
    shots = None if a.no_shots else Path(a.shots) if a.shots else report.with_suffix("")
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    runs = plan_runs(pages, widths, modes)
    print(f"{len(runs)} views: {len(pages)} pages x {len(widths)} widths x {len(modes)} modes",
          flush=True)
    srv, base = serve(site)
    started = datetime.now(timezone.utc)
    try:
        browser, got = drive(chrome, base, runs, shots, a.shot_cap, progress=not a.quiet)
    finally:
        srv.shutdown()
    # SILENCE IS NOT SUCCESS: a view the browser never reported is named.
    seen = {r["id"] for r in got}
    for r in runs:
        if r["id"] not in seen:
            got.append({"id": r["id"], "page": r["page"], "width": r["width"], "mode": r["mode"],
                        "path": r["path"], "error": "the browser never reported this view"})
    summary = summarise(got)
    out = {
        "tool": "src/checks/rendered_sweep.py",
        "made": started.isoformat(timespec="seconds"),
        "seconds": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "site": str(site.resolve()), "build": _build_stamp(site), "commit": _commit(),
        "browser": (browser or {}).get("browser"), "host_rules": (browser or {}).get("hostRules"),
        "widths": widths, "modes": modes, "shots": str(shots) if shots else None,
        "pages": [{k: p[k] for k in ("name", "path", "note", "why", "missing_why", "steps") if p.get(k)}
                  for p in pages],
        "summary": summary,
        "runs": got,
    }
    if a.compare:
        out["compared_with"] = {"report": a.compare,
                                "moved": compare(json.loads(Path(a.compare).read_text(encoding="utf-8")),
                                                 out)}
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print()
    print(headline(summary))
    if a.compare:
        for k, v in out["compared_with"]["moved"].items():
            print(f"  {k}: {v['before']} -> {v['after']}")
    print(f"\nreport: {report}" + (f"\nscreenshots: {shots}" if shots else ""))
    return 1 if summary["errors"] or summary["network"]["outside"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
