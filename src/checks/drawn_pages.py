#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.2
"""
What the browser draws on a built site's pages, written down, so that two
builds can be compared by what a reader is shown and not only by the HTML.

    python3 src/checks/drawn_pages.py --site <site> --out <dir>
    python3 src/checks/drawn_pages.py --compare <dir> <dir>

WHY. A bill's, a legislator's and a committee's page is app.js drawing a JSON
record in the browser, and the bill search, the home page and the Calendar
draw part of themselves the same way. A sha256 manifest of the built site
proves the HTML and the records unchanged and says nothing of what the
scripts make of them, so a change meant to move nothing (the component plan's
"nothing should move" steps, 9 October 2026) is proved by comparing this
tool's output as well.

WHAT IT DRAWS. Every bill, legislator and committee page under --site, at its
own address and at the address of each of its tabs (the slugs the site's
_redirects serves), and the bill search, the home page, the Calendar, the
all-results search and the legislators page. Each page's scripts run in node
as a browser runs them: every classic script in the order the page names it,
an external one read from the site (components.js in the head, app.js,
find.js) and an inline one from the page, the deferred ones after, then
DOMContentLoaded and load. They run against tests/dom_stub.js, the stand-in
preflight runs app.js against, told only what the page itself holds: an
element is there if the page or something already drawn carries its id, a
record's JSON is the page's own, and fetch is answered from the site folder.
The day is fixed (--today), so a page that says "in 3 days" says it the same
in both runs. What each page's scripts wrote -- every element's markup and
text, the title, and every error, in the order met -- goes to one file per
page and tab under --out, with manifest.json, the sha256 of each.

--compare names every page and tab whose drawing differs between two such
folders, or that only one has, and exits 1 if there is any.

Asks nobody: it reads --site and tests/dom_stub.js and writes only --out.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile

# The pages that are not a record but draw part of themselves in the browser.
LISTS = ("bills.html", "index.html", "calendar.html", "search.html", "officials.html")

# The node side. One context a page, so nothing one page's scripts declare is
# another's; the stub is loaded into it and then told what the page holds.
DRIVER = r"""
const fs = require("fs"), vm = require("vm"), path = require("path");
const [stubPath, jobsPath, outPath] = process.argv.slice(2);
const STUB = fs.readFileSync(stubPath, "utf8");
const jobs = JSON.parse(fs.readFileSync(jobsPath, "utf8"));
let errors = null;
process.on("unhandledRejection", e => { if (errors) errors.push("unhandled: " + String(e && e.stack || e).split("\n")[0]); });
process.on("uncaughtException", e => { if (errors) errors.push("uncaught: " + String(e && e.stack || e).split("\n")[0]); });
const tick = () => new Promise(r => setImmediate(r));

const PRELUDE = String.raw`
(function(){
  const R = Date, T = new R(__today[0], __today[1] - 1, __today[2], 12, 0, 0).getTime();
  class FixedDate extends R { constructor(...a) { if (a.length) super(...a); else super(T); }
    static now() { return T; } }
  globalThis.Date = FixedDate;
})();
`;
// The stub's elements, given what a page's scripts ask of an element beyond
// it: attributes that are kept and read back, the insertion methods, and an
// id that getElementById can find once something has drawn it.
const AFTER_STUB = String.raw`
var ALL = [];
(function(){
  const bare = el;
  el = function (tag) {
    const e = bare(tag);
    e._attr = {};
    e.setAttribute = (k, v) => { e._attr[k] = String(v); if (k === "id") e.id = String(v); };
    e.getAttribute = k => (k in e._attr ? e._attr[k] : null);
    e.hasAttribute = k => k in e._attr;
    e.removeAttribute = k => { delete e._attr[k]; };
    e.toggleAttribute = (k, on) => { const v = on === undefined ? !(k in e._attr) : !!on;
      if (v) e._attr[k] = ""; else delete e._attr[k]; return v; };
    e.after = e.before = e.prepend = e.replaceWith = e.replaceChildren = () => {};
    e.insertAdjacentHTML = (where, h) => { if (where === "beforeend") e.innerHTML += h;
      else if (where === "afterbegin") e.innerHTML = h + e.innerHTML; };
    e.matches = () => false;
    e.cloneNode = () => el(tag);
    ALL.push(e);
    return e;
  };
})();
(function(){
  const PAGE = __page, json = {};
  for (const m of PAGE.matchAll(/<script type="application\/json" id="([^"]+)">([\s\S]*?)<\/script>/g))
    json[m[1]] = m[2];
  const has = id => { const n = 'id="' + id + '"'; if (PAGE.includes(n)) return true;
    return ALL.some(e => (e._html || "").includes(n)); };
  const q = document.querySelector;
  document.getElementById = function (id) {
    if (made[id]) return made[id];
    const own = ALL.find(e => e.id === id);
    if (own) return own;
    if (!has(id)) return null;
    const e = made[id] = el(); if (id in json) e.textContent = json[id];
    // An element the page itself carries keeps the attributes its tag gives it.
    const tag = new RegExp('<([a-z][a-z0-9]*)\\b[^>]*\\bid="' + id + '"[^>]*>').exec(PAGE);
    if (tag) {
      e.tagName = tag[1].toUpperCase();
      const unq = v => v.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<")
        .replace(/&gt;/g, ">").replace(/&amp;/g, "&");
      for (const a of tag[0].matchAll(/\s([a-z][\w-]*)(?:="([^"]*)")?/g)) e._attr[a[1]] = unq(a[2] || "");
    }
    return e; };
  document.querySelector = function (sel) {
    const mm = /^meta\[name="([^"]+)"\]$/.exec(sel);
    if (mm) { const x = new RegExp('<meta name="' + mm[1] + '" content="([^"]*)"').exec(PAGE);
      if (!x) return null; const e = el(); e.getAttribute = a => a === "content" ? x[1] : null; return e; }
    if (/^#[\w-]+$/.test(sel)) return document.getElementById(sel.slice(1));
    return q.call(document, sel); };
  globalThis.clearTimeout = globalThis.clearInterval = () => {};
  globalThis.setInterval = () => 0;
  const heard = {};
  document.addEventListener = (t, f) => (heard["d:" + t] = heard["d:" + t] || []).push(f);
  globalThis.addEventListener = (t, f) => (heard["w:" + t] = heard["w:" + t] || []).push(f);
  globalThis.__fire = k => (heard[k] || []).forEach(f => { try { f({type: k.slice(2), target: document}); }
    catch (e) { __err("listener " + k + ": " + e.constructor.name + ": " + e.message); } });
  globalThis.fetch = async u => { const b = __read(String(u));
    return b === null ? {ok: false, status: 404, statusText: "Not Found",
                         json: async () => { throw new Error("HTTP 404 " + u); }, text: async () => ""}
                      : {ok: true, status: 200, json: async () => JSON.parse(b), text: async () => b}; };
  location.pathname = __path; location.href = "https://x" + __path; location.origin = "https://x";
  location.search = ""; location.hash = "";
})();
`;

function draw(job) {
  const html = fs.readFileSync(path.join(job.site, job.page), "utf8");
  const ctx = vm.createContext({
    console: {log() {}, warn() {}, error() {}, info() {}, debug() {}},
    URL, URLSearchParams, setImmediate, queueMicrotask, TextEncoder, TextDecoder,
    __today: job.today, __page: html, __path: job.path,
    __err: m => errors.push(m),
    __read: u => {
      let p;
      try { p = decodeURIComponent(new URL(u, "https://x/").pathname).replace(/^\/+/, ""); }
      catch (_) { return null; }
      let f = path.join(job.site, p);
      if (p && !fs.existsSync(f) && fs.existsSync(f + ".html")) f += ".html";
      if (!p || !fs.existsSync(f) || fs.statSync(f).isDirectory()) return null;
      return fs.readFileSync(f, "utf8");
    }});
  const run = (code, name) => {
    try { vm.runInContext(code, ctx, {filename: name}); }
    catch (e) { errors.push(name + ": " + e.constructor.name + ": " + e.message); }
  };
  run(PRELUDE, "prelude");
  run(STUB, "dom_stub.js");
  run(AFTER_STUB, "the page");
  const later = [];
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
    const attrs = m[1], src = /\bsrc="([^"]+)"/.exec(attrs), type = /\btype="([^"]+)"/.exec(attrs);
    if (type && !/javascript/.test(type[1])) continue;
    if (src) {
      const file = path.join(job.site, src[1].replace(/^\/+/, ""));
      if (!fs.existsSync(file)) { errors.push(src[1] + ": not in the site"); continue; }
      const code = fs.readFileSync(file, "utf8");
      if (/\bdefer\b/.test(attrs)) later.push([code, src[1]]); else run(code, src[1]);
    } else run(m[2], "an inline script");
  }
  for (const [code, name] of later) run(code, name);
  run('__fire("d:DOMContentLoaded"); __fire("w:load");', "the page loaded");
  return ctx;
}

(async () => {
  const out = {};
  for (const job of jobs) {
    errors = [];
    const ctx = draw(job);
    let last = "", still = 0;
    for (let i = 0; i < 2000 && still < 40; i++) {
      await tick();
      const now = vm.runInContext("Object.keys(made).map(k => k.length + (made[k]._html || '').length + "
        + "String(made[k].textContent || '').length).join()", ctx);
      still = now === last ? still + 1 : 0; last = now;
    }
    const els = vm.runInContext("Object.keys(made).sort().map(k => [k, made[k]._html || '', "
      + "String(made[k].textContent || ''), !!made[k].hidden, String(made[k].value || ''), "
      + "JSON.stringify(Object.fromEntries(Object.entries(made[k]._attr || {}).sort()))])", ctx);
    out[job.key] = {title: String(vm.runInContext("document.title", ctx) || ""),
                    elements: els.filter(e => e[1] || e[2] || e[3] || e[4] || e[5] !== "{}"), errors};
    errors = null;
  }
  fs.writeFileSync(outPath, JSON.stringify(out));
})();
"""


def tab_slugs(site):
    """{"bill": [...], "legislator": [...], "committee": [...]}: the tab
    addresses the site serves, read from its _redirects."""
    slugs = {"bill": [], "legislator": [], "committee": []}
    red = Path(site) / "_redirects"
    if red.exists():
        for ln in red.read_text(encoding="utf-8").splitlines():
            m = re.match(r"/(bill|legislator|committee)/(?::\w+/)+(\w+) ", ln)
            if m:
                slugs[m.group(1)].append(m.group(2))
    return slugs


def jobs_for(site, today):
    """Every page and tab to draw: (key, page file, address)."""
    site = Path(site)
    slugs = tab_slugs(site)
    out = []
    for kind, pattern in (("bill", "bill/*/*.html"), ("legislator", "legislator/*.html"),
                          ("committee", "committee/*.html")):
        for f in sorted(site.glob(pattern)):
            page = f.relative_to(site).as_posix()
            own = "/" + page[:-len(".html")]
            out.append({"key": page, "page": page, "path": own})
            out += [{"key": f"{page}#{s}", "page": page, "path": f"{own}/{s}"} for s in slugs[kind]]
    for page in LISTS:
        if (site / page).exists():
            out.append({"key": page, "page": page, "path": "/" + page})
    for j in out:
        j["site"] = str(site.resolve())
        j["today"] = [today.year, today.month, today.day]
    return out


def draw(site, out, today):
    """Draw every page and tab of `site` into `out`; returns how many."""
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        raise SystemExit("node is not on PATH, and the pages' scripts run in node")
    stub = _paths.ROOT / "tests" / "dom_stub.js"
    jobs = jobs_for(site, today)
    if not jobs:
        raise SystemExit(f"no record page under {site}: nothing to draw")
    tmp = Path(tempfile.mkdtemp(prefix="gr-drawn-"))
    try:
        (tmp / "drive.js").write_text(DRIVER, encoding="utf-8")
        (tmp / "jobs.json").write_text(json.dumps(jobs), encoding="utf-8")
        r = subprocess.run([node, str(tmp / "drive.js"), str(stub), str(tmp / "jobs.json"),
                            str(tmp / "out.json")], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        if r.returncode != 0 or not (tmp / "out.json").exists():
            raise SystemExit("the pages' scripts did not run: " + (r.stderr or r.stdout)[-400:])
        drawn = json.loads((tmp / "out.json").read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    manifest = {}
    for key, d in drawn.items():
        page, _, tab = key.partition("#")
        f = out / page / f"{tab or '_'}.txt"
        f.parent.mkdir(parents=True, exist_ok=True)
        text = (f"== title\n{d['title']}\n"
                + "".join(f"== {k}{' (hidden)' if hid else ''}\n{h}\n-- text\n{tx}\n"
                          + (f"-- value\n{v}\n" if v else "")
                          + (f"-- attributes\n{at}\n" if at != "{}" else "")
                          for k, h, tx, hid, v, at in d["elements"])
                + "".join(f"== error\n{e}\n" for e in d["errors"]))
        f.write_text(text, encoding="utf-8", newline="\n")
        manifest[key] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True),
                                       encoding="utf-8", newline="\n")
    empty = [k for k, d in drawn.items() if not d["elements"]]
    errs = sum(1 for d in drawn.values() if d["errors"])
    print(f"drawn: {len(drawn)} pages and tabs of {site} into {out}"
          f" ({errs} with an error the scripts met, {len(empty)} with nothing drawn)")
    return drawn


def compare(a, b):
    """The pages and tabs whose drawing differs between two outputs."""
    ma = json.loads((Path(a) / "manifest.json").read_text(encoding="utf-8"))
    mb = json.loads((Path(b) / "manifest.json").read_text(encoding="utf-8"))
    differ = sorted(k for k in set(ma) & set(mb) if ma[k] != mb[k])
    only_a, only_b = sorted(set(ma) - set(mb)), sorted(set(mb) - set(ma))
    for k in differ:
        print("differs:", k)
    for k in only_a:
        print(f"only in {a}:", k)
    for k in only_b:
        print(f"only in {b}:", k)
    print(f"{len(set(ma) & set(mb)) - len(differ)} of {len(set(ma) | set(mb))} pages and tabs "
          f"drawn the same; {len(differ)} differ; {len(only_a) + len(only_b)} in one only")
    return not (differ or only_a or only_b)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", help="a built site folder")
    ap.add_argument("--out", help="where to write what was drawn")
    ap.add_argument("--today", help="the day the pages are drawn on, YYYY-MM-DD "
                    "(default: GRANITE_BUILD_DATE, else today)")
    ap.add_argument("--compare", nargs=2, metavar="DIR", help="two outputs to compare")
    a = ap.parse_args()
    if a.compare:
        sys.exit(0 if compare(*a.compare) else 1)
    if not (a.site and a.out):
        ap.error("--site and --out, or --compare")
    day = a.today or os.environ.get("GRANITE_BUILD_DATE", "")[:10]
    today = datetime.date.fromisoformat(day) if day else datetime.date.today()
    drawn = draw(a.site, a.out, today)
    # SILENCE IS NOT SUCCESS: a site whose record pages draw nothing at all is
    # a broken driver, not a quiet site.
    if not any(d["elements"] for k, d in drawn.items() if "/" in k):
        sys.exit("no record page drew anything")


if __name__ == "__main__":
    main()
