#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.2
"""
The statutes (RSA) as pages: /rsa, and one page a chapter at /rsa/<chapter>.

    python3 src/pages/build_rsa.py --site site --base https://graniterecord.org

Asks nobody. Reads the General Court's statute table through rsa.py, what
rsa.py wrote (rsa_citations.json), and the bill index the site build wrote
(site/idx/<term>.json) for each bill's number, title and whether it is still
moving. Writes site/rsa.html, site/rsa/<chapter>.html and the three files the
landing page's search reads, site/rsa/chapters.json, headings.json and
words.json.

THE DESIGN IS RSA_PAGE.md (7 October 2026), with the person's asks of 11
October: "a more easily searchable and viewable interface for RSAs,
including tagging sections that are in progress that propose to amend that
RSA section, with history of how it's changed through various bills over the
years. You should be able to easily scroll through sections and search
through the database for related laws in plain text, and the RSA pages
should be linked throughout the site to the Granite Record pages as an
interlinked system."

A CHAPTER PAGE, top to bottom (RSA_PAGE.md §5):

1. The chapter's number and name, and one line saying what the text is: the
   table as the General Court holds it, through the laws of the latest year
   its source notes name, with the official page one link away.
2. Pending: the sitting term's bills still moving that say they change this
   chapter, as chips, each section they name tagged below.
3. The sections in order, under the chapter's own inner headings, each an
   anchor (/rsa/91-a#s4) carrying: its heading, a Pending tag where a bill
   still moving would change it, its text with every citation the table
   holds linked to its own anchor, its source note, and four folds -- How it
   has changed (the source note's laws, newest first, each the bill it was),
   Also proposed by (every other bill whose own instructions name the
   section, failed ones included), Cites, Cited by.
4. A repealed section is one muted line, its anchor kept, so an old bill's
   link still lands on something true.

TWO RECORDS, NOT ONE (RSA_PAGE.md §3). "How it has changed" is the Office of
Legislative Services' source note; "Also proposed by" is the bills' own
instructions. They are labelled apart and never merged.

THE TEXT IS TODAY'S. A 1997 bill's link opens the section as it reads now;
the currency line says so, and the history says when it changed, not what
it said.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import html
import json
import math
import re

import build_date
import rsa
import shell as S

E = html.escape
SHOWN = 8          # a list folds after this many, as the bill page's Amends row does
OG_ALT = "Granite Record: New Hampshire's statutes"

STOP = set("""a an and are as at be been by for from has have in is it its may not of on or
shall such that the this to under which with any all other each than those these who whom
whose upon into within without where when there their them they was were will would
pursuant thereof therein hereby section chapter paragraph subparagraph rsa provided
including include includes also more less only same such state new hampshire person""".split())
WORD = re.compile(r"[a-z][a-z']{2,}")


SMALL = set("a an and as at but by for in nor of on or per the to vs via with from into upon".split())
ROMAN = re.compile(r"^(?=[IVXLC]+$)[IVXLC]+$")


def nice(name):
    """The table's capitals as a heading: "ACCESS TO GOVERNMENTAL RECORDS AND
    MEETINGS" -> "Access to Governmental Records and Meetings", Roman numerals
    and abbreviations of two or more capitals left as they are."""
    if not name or not name.isupper():
        return name or ""
    out = []
    for i, w in enumerate(name.split()):
        core = w.strip("(),;:.")
        if ROMAN.match(core) or (len(core) <= 4 and "." in w) or core in ("RSA", "UCC", "N.H."):
            out.append(w)
        elif i and w.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append("-".join(x[:1].upper() + x[1:].lower() for x in w.split("-")))
    return " ".join(out)


def bill_order(key):
    """A bill key in the order the site lists bills: kind, then number."""
    term, _, bill = key.partition("/")
    m = re.match(r"([A-Z]+)(\d+)", bill)
    return (term, m.group(1), int(m.group(2))) if m else (term, bill, 0)


def stem(w):
    """The light stem the search uses on both sides, so "dogs" finds "dog"
    and "liabilities" "liability"; the same rule is in LANDING_JS."""
    w = w.lower().strip("'")
    if w.endswith("'s"):
        w = w[:-2]
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def chapter_slug(ch):
    return ch.lower()


def sec_anchor(addr):
    return "s" + addr.split(":", 1)[1]


def href(addr):
    """The site's own address for a statute address: /rsa/91-a#s4, /rsa/91-a."""
    ch, _, sec = addr.partition(":")
    return f"/rsa/{chapter_slug(ch)}" + (f"#{sec_anchor(addr)}" if sec else "")


def term_of_year(y):
    y = int(y)
    a = y if y % 2 else y - 1
    return f"{a}-{a + 1}"


# ------------------------------------------------------------------ bills

class Bills:
    """Each bill's number, title, chip and whether it is still moving, from
    the site's own index (site/idx/<term>.json)."""

    def __init__(self, site, current):
        self.rows, self.current = {}, current
        for p in sorted((Path(site) / "idx").glob("[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].json")):
            try:
                for r in json.loads(p.read_text(encoding="utf-8")):
                    self.rows[f"{p.stem}/{r.get('id')}"] = r
            except (OSError, ValueError):
                continue

    def row(self, key):
        return self.rows.get(key) or {}

    def moving(self, key):
        r = self.row(key)
        return bool(r) and S.still_moving(dict(r, term=r.get("term") or key.split("/")[0]),
                                          self.current)

    def label(self, key):
        r = self.row(key)
        term, _, bill = key.partition("/")
        if r.get("n"):
            return r["n"]
        m = re.match(r"([A-Z]+)(\d+)$", bill)
        return f"{m.group(1)} {m.group(2)}" if m else bill

    def url(self, key):
        r = self.row(key)
        term, _, bill = key.partition("/")
        year = r.get("year") or term[:4]
        return f"/bill/{year}/{bill.lower()}"

    def chip(self, key, with_year=True):
        """A bill as the site draws one in a list: its number linked, its
        status after it, the term's years where it is not the sitting one."""
        r = self.row(key)
        term = key.split("/")[0]
        when = "" if term == self.current or not with_year else f' <span class="rs-yr">{E(term)}</span>'
        st = r.get("chip") or ""
        title = r.get("title") or ""
        return (f'<li><a href="{E(self.url(key))}" title="{E(title)}">{E(self.label(key))}</a>{when}'
                + (f' <span class="rs-st">{E(st)}</span>' if st else "") + "</li>")


def folded(items, cls="rs-list"):
    """A list of <li>, the first SHOWN open and the rest behind Show all."""
    if not items:
        return ""
    head = "".join(items[:SHOWN])
    rest = items[SHOWN:]
    more = (f'<details class="rs-more"><summary>Show all {len(items)}</summary>'
            f'<ul class="{cls}">{"".join(rest)}</ul></details>') if rest else ""
    return f'<ul class="{cls}">{head}</ul>{more}'


# ------------------------------------------------------------------ text

def linked_text(table, text, own):
    """The section's text as paragraphs, every citation the table holds a
    link to its own anchor, the rest as written; a repealed target says so."""
    out = []
    for para in [p.strip() for p in (text or "").split("\n") if p.strip()]:
        pieces, pos = [], 0
        for c in rsa.cites(para):
            kind, target = table.resolve(c.chapter, c.section)
            if not kind or target == own:
                continue
            # the span to link: from "RSA" for the head, the number alone in a list
            st = c.start if c.how == "rsa" else para.find(c.section, c.start)
            en = c.end
            if st < pos or st < 0:
                continue
            gone = kind == "section" and table.sections[target].repealed
            pieces.append(E(para[pos:st]))
            pieces.append(f'<a href="{E(href(target))}">{E(para[st:en])}</a>'
                          + (' <span class="rs-gone">(repealed)</span>' if gone else ""))
            pos = en
        pieces.append(E(para[pos:]))
        out.append(f"<p>{''.join(pieces)}</p>")
    return "".join(out)


# ------------------------------------------------------------------ indexes

# A CHAPTER'S POPULAR NAME, as the statutes themselves write it: readers search
# "right to know", and chapter 91-A is titled "Access to Governmental Records
# and Meetings". The statutes say the name beside the citation, in either
# order -- "the right-to-know law, RSA 91-A", "RSA 91-A, the right-to-know
# law" -- or declare it: "This chapter shall be known as the Uniform
# Commercial Code". A name is kept where the chapter declares it or the
# statutes use it at least twice.
KNOWN_AS = re.compile(r"(?:shall|may)\s+be\s+(?:known|cited)(?:\s+and\s+(?:may\s+be\s+)?cited)?\s+as\s+"
                      r"(?:the\s+)?[\"\u201c]?([A-Z][^\"\u201d.;]{3,80}?)[\"\u201d]?(?:\.|,|;|\s+and\b)")
NAME_THEN_RSA = re.compile(r"\bthe\s+((?:[A-Za-z'\u2019-]+\s+){0,4}(?:law|act|code))\s*,\s*RSA\s+"
                           r"(\d{1,3}(?:-[A-Z]{1,2})?)(?![:\d])", re.I)
RSA_THEN_NAME = re.compile(r"\bRSA\s+(\d{1,3}(?:-[A-Z]{1,2})?)(?![:\d])\s*,\s*the\s+"
                           r"((?:[A-Za-z'\u2019-]+\s+){0,4}(?:law|act|code))\b", re.I)


def popular_names(table):
    """{chapter: [names]} from the statutes' own words."""
    got = collections.defaultdict(collections.Counter)
    for s in table.sections.values():
        for m in KNOWN_AS.finditer(s.text):
            got[s.chapter][m.group(1).strip()] += 2
        for m in NAME_THEN_RSA.finditer(s.text):
            got[m.group(2).upper()][m.group(1).strip().lower()] += 1
        for m in RSA_THEN_NAME.finditer(s.text):
            got[m.group(1).upper()][m.group(2).strip().lower()] += 1
    out = {}
    for ch, names in got.items():
        if ch not in table.chapters:
            continue
        keep, seen = [], set()
        for n, c in names.most_common():
            if c >= 2 and n.lower() not in seen:
                seen.add(n.lower())
                keep.append(n)
        if keep:
            out[ch] = keep[:4]
    return out


def build_indexes(table, cites):
    """chapters.json, headings.json and words.json for the landing page's
    search (RSA_PAGE.md §6), all in the reader's browser.

    words.json is what each section is ABOUT, not every word in it: the
    heading's words, and its twelve most telling words by how often the
    section uses them against how many sections do -- the plain-text search
    the person asked for, at a size a reader can fetch once."""
    names = popular_names(table)
    chapters = {ch: [nice(info["name"]), info["title_no"], len(info["sections"]), info["repealed"],
                     names.get(ch, [])]
                for ch, info in table.chapters.items()}
    headings = [[a, s.heading] for a, s in table.sections.items() if not s.repealed]
    df = collections.Counter()
    tfs = {}
    for a, s in table.sections.items():
        if s.repealed:
            continue
        tf = collections.Counter(stem(w) for w in WORD.findall(s.text.lower()) if w not in STOP)
        tfs[a] = tf
        df.update(tf.keys())
    n = max(1, len(tfs))
    order = list(tfs)
    idx = {a: i for i, a in enumerate(order)}
    post = collections.defaultdict(list)
    for a, tf in tfs.items():
        head = {stem(w) for w in WORD.findall(table.sections[a].heading.lower()) if w not in STOP}
        top = sorted(tf, key=lambda w: (-tf[w] * math.log(n / df[w]), w))[:12]
        for w in sorted(head | set(top)):
            post[w].append(idx[a])
    # Postings as the gap from the one before, which compresses to about half
    # (951 KB to 518 KB gzipped on 8 September 2026's table), and numbered by
    # headings.json's own order, which is the same list -- so the sections are
    # not written twice.
    assert [h[0] for h in headings] == order, "headings.json and words.json list sections differently"
    words = {"words": {w: [v[0]] + [b - a for a, b in zip(v, v[1:])] for w, v in sorted(post.items())}}
    return chapters, headings, words


# ------------------------------------------------------------------ pages

def chapter_page(tmpl, table, data, bills, ch, base):
    info = table.chapters[ch]
    secs = info["sections"]
    proposed = collections.defaultdict(list)     # address -> [bill key]
    for term, bs in data.get("bills", {}).items():
        for bill, rec in bs.items():
            for a in rec.get("changes", []):
                if a == ch or a.startswith(ch + ":"):
                    proposed[a].append(f"{term}/{bill}")
    cited_by = collections.defaultdict(list)
    for src, targets in data.get("statute", {}).items():
        for t in targets:
            if t.startswith(ch + ":") or t == ch:
                cited_by[t].append(src)
    pending_ch = sorted({k for a, ks in proposed.items() for k in ks if bills.moving(k)},
                        key=bill_order)
    latest = data.get("asof", {}).get("laws_through") or ""
    path = f"/rsa/{chapter_slug(ch)}"
    title = f"RSA {ch}: {nice(info['name'])}"
    p = S.page(tmpl, path=path, base=base, title=S.title_of(f"RSA {ch}", "Statutes"),
               og_title=title, description=f"New Hampshire RSA chapter {ch}, {info['name']}: "
               "its text, the bills that changed it and the bills that would.",
               og_image="og-learn.png", og_alt=OG_ALT, globals={"GR_STATIC": True},
               noscript="", skip_label="Skip to the statute", sr_title="",
               nav_current="resources.html", cite=False)
    first = table.sections[secs[0]] if secs else None
    # The General Court's own table of contents page for the chapter, the
    # address build_site_v2.rsa_url has linked for a chapter since 4
    # September, rather than a guessed one for the whole chapter's text.
    tno = (first.url.split("/")[0] if first and first.url else "") or (first.title_no if first else "")
    official = (f"https://gc.nh.gov/rsa/html/NHTOC/NHTOC-{tno}-{ch}.htm" if tno
                else "https://gc.nh.gov/rsa/html/nhtoc.htm")
    lead = (f"The text as the General Court's table holds it, "
            f"through the laws of {E(str(latest))}. "
            f'<a href="{E(official)}" rel="noopener">The official text on gc.nh.gov</a>.')
    crumb = nice(re.sub(r"^TITLE\s+(\S+)\s*", r"TITLE \1: ", first.title)) if first else ""
    head = (f'<header class="l-head"><p class="rs-crumb"><a href="/rsa">The statutes</a> &rsaquo; '
            f'{E(crumb)}</p><h1>{E(title)}</h1>'
            f'<p class="l-lead">{lead}</p>' + S.cite_block(path, title, base, S.BUILT) + "</header>")
    pend = ""
    if pending_ch:
        pend = ('<section class="rs-pending" aria-label="Pending"><h2>Bills now before the '
                f'General Court that would change this chapter</h2>'
                + folded([bills.chip(k) for k in pending_ch]) + "</section>")
    toc_items = []
    body = []
    sub = None
    for a in secs:
        s = table.sections[a]
        if s.sub and s.sub != sub:
            sub = s.sub
            body.append(f'<h2 class="rs-sub">{E(sub)}</h2>')
        anchor = sec_anchor(a)
        if s.repealed:
            body.append(f'<p class="rs-repealed" id="{E(anchor)}"><a href="#{E(anchor)}">{E(a)}</a> '
                        f'{E(s.heading)}</p>')
            continue
        toc_items.append(f'<li><a href="{E(path)}#{E(anchor)}">{E(a)} {E(s.heading)}</a></li>')
        pend_k = sorted((k for k in proposed.get(a, []) if bills.moving(k)), key=bill_order)
        other = [k for k in proposed.get(a, []) if not bills.moving(k)]
        hist = list(reversed(data.get("enacted", {}).get(a, [])))
        rows = []
        if hist:
            items = []
            for y, law, b in hist:
                bl = (f' &middot; <a href="{E(bills.url(b))}">{E(bills.label(b))}</a>' if b else "")
                items.append(f'<li><span class="rs-yr">{E(y)}</span> Laws of {E(y)}, chapter '
                             f'{E(law.split(":")[0])}{bl}</li>')
            rows.append(("How it has changed", "From the section's source note, newest first.",
                         folded(items, "rs-hist")))
        if other:
            other.sort(key=lambda k: (k.split("/")[0], bill_order(k)[1], -bill_order(k)[2]), reverse=True)
            rows.append(("Also proposed by", "Bills whose own text says they change this section, "
                         "passed or not.", folded([bills.chip(k) for k in other])))
        out_c = data.get("statute", {}).get(a, [])
        if out_c:
            rows.append(("Cites", "", folded([f'<li><a href="{E(href(t))}">RSA {E(t)}</a></li>'
                                              for t in out_c], "rs-refs")))
        if cited_by.get(a):
            rows.append(("Cited by", "", folded([f'<li><a href="{E(href(t))}">RSA {E(t)}</a></li>'
                                                 for t in sorted(cited_by[a], key=rsa.addr_key)],
                                                "rs-refs")))
        tag = ""
        if pend_k:
            tag = (f'<details class="rs-tag"><summary>Pending: {len(pend_k)} '
                   f'bill{"s" if len(pend_k) != 1 else ""}</summary>'
                   + folded([bills.chip(k) for k in pend_k]) + "</details>")
        folds = "".join(
            f'<details class="rs-fold"><summary>{E(h)}</summary>'
            + (f'<p class="rs-note">{E(n)}</p>' if n else "") + f"{c}</details>"
            for h, n, c in rows)
        body.append(
            f'<section class="rs-sec" id="{E(anchor)}"><h3 class="rs-h"><a href="#{E(anchor)}">'
            f'{E(a)}</a> {E(s.heading)}</h3>{tag}'
            f'<div class="rs-text">{linked_text(table, s.text, a)}</div>'
            + (f'<p class="rs-source">Source. {E(s.note)}</p>' if s.note else "")
            + (f'<div class="rs-folds">{folds}</div>' if folds else "") + "</section>")
    toc = ""
    if len(toc_items) > 1:
        toc = (f'<details class="rs-toc"><summary>The {len(toc_items)} sections</summary>'
               f'<ol>{"".join(toc_items)}</ol></details>')
    if info.get("repealed") and not toc_items:
        body.insert(0, f'<p class="rs-repealed">This chapter has been repealed. {E(info.get("note") or "")}</p>')
    art = f'<div class="rs-art">{pend}{toc}{"".join(body)}</div>'
    return p.replace('<div id="results"></div>',
                     f'<div id="results"><div class="l-page rs-page">{head}{art}</div></div>', 1)


LANDING_JS = """<script>
(function(){
  var box=document.getElementById("rsq"),out=document.getElementById("rsout");
  if(!box||!out)return;
  var CH=null,HD=null,WD=null;
  function get(u){return fetch(u).then(function(r){return r.ok?r.json():null;});}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function link(a){var p=a.split(":");return "/rsa/"+p[0].toLowerCase()+(p[1]?"#s"+p[1]:"");}
  // The same light stem build_rsa.stem gives the index.
  function stem(w){w=w.toLowerCase().replace(/^'+|'+$/g,"");if(/'s$/.test(w))w=w.slice(0,-2);
    if(w.length>4&&/ies$/.test(w))return w.slice(0,-3)+"y";
    if(w.length>3&&/s$/.test(w)&&!/ss$/.test(w))return w.slice(0,-1);return w;}
  var STOP=" a an and are as at be by for from in is it of on or the to with any all under ";
  function words(q){return (q.toLowerCase().match(/[a-z][a-z']{1,}/g)||[]).filter(function(w){
    return STOP.indexOf(" "+w+" ")<0;}).map(stem);}
  function has(text,w){return (text.toLowerCase().match(/[a-z][a-z']+/g)||[]).some(function(x){
    return stem(x)===w||(w.length>=4&&x.indexOf(w)===0);});}
  var CITE=/^\\s*(?:rsa\\s*)?(\\d{1,3}(?:-[a-z]{1,2})?)(?::\\s*([0-9a-z.\\-]+))?\\s*$/i;
  function show(rows,note){
    out.innerHTML=(note?'<p class="rs-note">'+esc(note)+'</p>':'')+(rows.length?'<ol class="rs-hits">'+rows.slice(0,50).map(function(r){
      return '<li><a href="'+link(r[0])+'">RSA '+esc(r[0])+'</a> '+esc(r[1]||"")+'</li>';}).join("")+'</ol>':'');
  }
  function load(){return Promise.all([
    CH?CH:get("rsa/chapters.json").then(function(d){return CH=d||{};}),
    HD?HD:get("rsa/headings.json").then(function(d){return HD=d||[];}),
    WD?WD:get("rsa/words.json").then(function(d){return WD=d||{words:{}};})]);}
  function run(){
    var q=box.value.trim();
    if(!q){out.innerHTML="";return;}
    var m=CITE.exec(q);
    load().then(function(r){
      var ch=r[0],hd=r[1],wd=r[2];
      if(m&&ch[m[1].toUpperCase()]){
        var c=m[1].toUpperCase(),a=c+(m[2]?":"+m[2]:"");
        show([[a,m[2]?((hd.filter(function(x){return x[0]===a;})[0]||[])[1]||ch[c][0]):ch[c][0]]],"By number:");return;
      }
      var ws=words(q);if(!ws.length){show([],"");return;}
      // Every source counts: a chapter's name, a section's heading, and what
      // each section is about. Ranked by how many of the words it matches,
      // then by where they matched, so a near miss is listed below, not lost.
      var hit={},name={};
      function add(a,label,w,pts){var h=hit[a]||(hit[a]={w:{},s:0});h.w[w]=1;h.s+=pts;if(label)name[a]=label;}
      Object.keys(ch).forEach(function(c){var known=(ch[c][4]||[]).join(" ");
        ws.forEach(function(w){if(has(ch[c][0]||"",w))add(c,ch[c][0],w,3);
          else if(known&&has(known,w))add(c,ch[c][0]+" (the "+ch[c][4][0]+")",w,3);});});
      hd.forEach(function(x){ws.forEach(function(w){if(has(x[1],w))add(x[0],x[1],w,2);});});
      var heads={};hd.forEach(function(x){heads[x[0]]=x[1];});
      // words.json numbers sections by headings.json's order, each posting
      // the gap from the one before.
      ws.forEach(function(w){var i=0;(wd.words[w]||[]).forEach(function(g){i+=g;var a=(hd[i]||[])[0];
        if(a)add(a,heads[a],w,1);});});
      var rows=Object.keys(hit).map(function(a){return [a,name[a]||heads[a]||"",Object.keys(hit[a].w).length,hit[a].s];})
        .filter(function(x){return x[2]>=Math.min(ws.length,Math.max(1,ws.length-1));})
        .sort(function(x,y){var cx=x[0].indexOf(":")<0,cy=y[0].indexOf(":")<0;
          return y[2]-x[2]||(cy-cx)||y[3]-x[3]||(x[0]<y[0]?-1:1);});
      var all=rows.filter(function(x){return x[2]===ws.length;}).length;
      show(rows,rows.length?(all===rows.length?"Matching every word:":all+" match every word; then the closest:")
        :"Nothing found. Try fewer words, or a chapter number such as 91-A.");
    });
  }
  var t=null;box.addEventListener("input",function(){clearTimeout(t);t=setTimeout(run,180);});
  document.getElementById("rsform").addEventListener("submit",function(e){e.preventDefault();run();});
})();
</script>"""


def landing_page(tmpl, table, data, base):
    path = "/rsa"
    title = "New Hampshire's statutes (RSA)"
    p = S.page(tmpl, path=path, base=base, title=S.title_of(title, "Resources"),
               og_title=title, description="Every chapter of the New Hampshire Revised Statutes "
               "Annotated: search by number, heading or subject, with the bills that changed each "
               "section and the bills that would.", og_image="og-learn.png", og_alt=OG_ALT,
               globals={"GR_STATIC": True}, noscript="", skip_label="Skip to the statutes",
               sr_title="", nav_current="resources.html", cite=False)
    latest = data.get("asof", {}).get("laws_through") or ""
    head = (f'<header class="l-head"><h1>{E(title)}</h1><p class="l-lead">The state\'s laws, '
            f'chapter by chapter, as the General Court\'s table holds them through the laws of '
            f'{E(str(latest))}, each section with the bills that changed it and the bills now '
            'proposing to.</p>' + S.cite_block(path, title, base, S.BUILT) + "</header>")
    search = ('<form id="rsform" class="rs-search" role="search"><label for="rsq">Search the '
              'statutes</label><input id="rsq" type="search" autocomplete="off" '
              'placeholder="A number (91-A:4) or words (right to know, dog bite)">'
              '</form><div id="rsout" aria-live="polite"></div>')
    titles = collections.OrderedDict()
    for ch in sorted(table.chapters, key=rsa.chap_key):
        info = table.chapters[ch]
        titles.setdefault((info["title_no"], info["title"]), []).append(ch)
    blocks = []
    for (tno, tname), chs in titles.items():
        lis = "".join(
            f'<li class="{"rs-off" if table.chapters[c]["repealed"] else ""}"><a href="/rsa/'
            f'{E(chapter_slug(c))}">{E(c)}</a> {E(nice(table.chapters[c]["name"]))}</li>' for c in chs)
        tn = nice(re.sub(r"^TITLE\s+\S+\s*", "", tname))
        blocks.append(f'<details class="rs-title"><summary><span class="rs-tno">Title {E(tno)}</span> '
                      f'{E(tn)}</summary><ul>{lis}</ul></details>')
    art = f'<div class="rs-art">{search}<h2 class="rs-sub">By title</h2>{"".join(blocks)}</div>'
    return p.replace('<div id="results"></div>',
                     f'<div id="results"><div class="l-page rs-page">{head}{art}</div>{LANDING_JS}</div>', 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--only", nargs="*", help="build these chapters alone (for a look), not the set")
    a = ap.parse_args()
    site = Path(a.site)
    table = rsa.load()
    cit = Path("rsa_citations.json")
    if table is None or not cit.is_file():
        print("build_rsa: no statute table or rsa_citations.json here; no statute pages written")
        return 0
    data = json.loads(cit.read_text(encoding="utf-8"))
    current = term_of_year(build_date.today().year)
    bills = Bills(site, current)
    tmpl = S.template(site)
    out = site / "rsa"
    out.mkdir(parents=True, exist_ok=True)
    chs = [c.upper() for c in a.only] if a.only else sorted(table.chapters, key=rsa.chap_key)
    for ch in chs:
        (out / f"{chapter_slug(ch)}.html").write_text(
            chapter_page(tmpl, table, data, bills, ch, a.base), encoding="utf-8")
    (site / "rsa.html").write_text(landing_page(tmpl, table, data, a.base), encoding="utf-8")
    chapters, headings, words = build_indexes(table, data)
    for name, obj in (("chapters.json", chapters), ("headings.json", headings), ("words.json", words)):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")),
                                encoding="utf-8")
    sizes = {n: (out / n).stat().st_size for n in ("chapters.json", "headings.json", "words.json")}
    print(f"build_rsa: {len(chs):,} chapter pages and the landing page; search files "
          + ", ".join(f"{n} {s / 1e6:.1f} MB" for n, s in sizes.items()))
    if not a.only:
        S.sitemap_merge(site, a.base, [a.base + "/rsa"] + [a.base + f"/rsa/{chapter_slug(c)}" for c in chs],
                        owns="/rsa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
