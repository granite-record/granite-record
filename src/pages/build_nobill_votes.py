#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.3
"""
A page a term of the votes not on a bill: what each was about, how it went,
and the session day it was taken on.

    python3 src/pages/build_nobill_votes.py --site site [--base URL]

WHY (23 October 2026). The owner: "Those are often important votes that
sometimes get reported on, but it's very hard to find that information on
GenCourt since the vote is just labeled something like voting whether to
approve the committee report with no other context." The session days now
quote the Journal for each of them (vote_passage, from journal_motions.json);
this lists a term's of them in one place, both chambers, newest first,
filterable by the kind of question -- a reprimand, an appeal of a ruling, a
member allowed to go on speaking, a rules suspension -- each row linked to
the roll call's own anchor on its day's page, where the Journal's words and
page are.

WHAT A ROW SAYS. The day, the chamber, the kind of question, a description,
the count and the outcome. The description is the one-line summary the
parser wrote where it wrote one; else, where the Journal's passage is shown,
the heading the Journal printed it under; else the roll-call file's own
words, marked as theirs ("In the record"), with the kind read off those
words alone. A division or a voice vote the Journal records and the
roll-call file does not is a row too, and says so. A call of the roll or an
attendance roll puts no question and is left out, as the session days leave
it out.

THE ADDRESS. /session/nobill/<term>.html, beside the chambers' pages and
their days, a name of its own: build_session_pages owns /session/H and
/session/S in the sitemap and build_full_sessions /session/house and
/session/senate (its docstring says why a page must not sit inside another
builder's part). Each session day's "Votes on No Bill" links its term's
page, and each chamber's page links the latest.

Reads rollcalls.json, journal_motions.json and the session days already
written under site/session/; writes site/session/nobill/ and its sitemap
entries. Asks nobody anything.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import html as _html
import json
import re
from collections import Counter, defaultdict

import components as C
import journal_motions as JM
import proceedings as P
import shell as S
import structured as LD
import vote_passage as VP

E = lambda s: _html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731
CHAMBER = {"H": "House", "S": "Senate"}
FOLDER = "session/nobill"
# A roll call that puts no question: session_days.QUORUM, word for word, so
# a day's page and this list leave out the same ones.
NO_QUESTION = re.compile(r"^\s*(?:call\s+of\s+the\s+roll|attendance|quorum)", re.I)


def address(term):
    return f"/{FOLDER}/{term}.html"


def href(term):
    """The page's address as a link from any page of the site (relative,
    as the site's links are)."""
    return f"{FOLDER}/{term}.html"


def file_kind_of(words):
    """The kind the roll-call file's own words name, for a vote whose
    passage is not shown: its first kind, or "other"."""
    got = [k for k in JM.kinds_in(words) if k != "report"]
    return got[0] if got else "other"


_PAGES = {}


def _page_text(p):
    """The anchors of the votes on no bill a session day's page carries, as
    one string, or None where there is no such page: a day's page can be a
    megabyte, and only its anchors are wanted."""
    if p not in _PAGES:
        try:
            _PAGES[p] = " ".join(m.group(0) for m in re.finditer(
                r'id="(?:rc|jv)-[\w-]+"', p.read_text(encoding="utf-8")))
        except OSError:
            _PAGES[p] = None
    return _PAGES[p]


def anchor_page(site, body, day, anchor, near=()):
    """The session day's page that carries `anchor`, as a link to it, or "":
    the roll call's own day first, then the days the pairing may have drawn
    it on instead (the House's roll calls of 24 and 25 February 2021 are
    dated the 26th). Where none carries it -- a vote on no bill the day
    draws under a bill it was entered on -- the day's own page, unanchored."""
    for d in (day, *near):
        t = _page_text(Path(site) / "session" / body / f"{d}.html")
        if t is not None and f'id="{anchor}"' in t:
            return f"session/{body}/{d}.html#{anchor}"
    own = _page_text(Path(site) / "session" / body / f"{day}.html")
    return f"session/{body}/{day}.html" if own is not None else ""


def rows_of(rollcalls, site):
    """{term: [row]} -- every vote on no bill, and every vote only the
    Journal records, newest first."""
    from datetime import date, timedelta
    out = defaultdict(list)
    for term, bills in (rollcalls or {}).items():
        for r in (bills or {}).get("_procedural") or []:
            words = (r.get("question_raw") or r.get("question") or "").strip()
            key = f'{r.get("year")}-{r.get("body")}-{r.get("number")}'
            e = VP.entry(key)
            if not e and NO_QUESTION.search(words):
                continue
            day = r.get("date") or ""
            try:
                near = [(date.fromisoformat(day) - timedelta(days=k)).isoformat()
                        for k in (1, 2, 3)]
            except ValueError:
                near = []
            kind = e["kind"] if e else file_kind_of(words)
            out[term].append({
                "key": key, "body": r.get("body"), "date": day, "kind": kind,
                "line": (e or {}).get("line") or "",
                "heading": (e or {}).get("heading") or "",
                "words": words, "shown": bool(e), "member": (e or {}).get("member") or "",
                "yeas": r.get("yeas"), "nays": r.get("nays"), "passed": r.get("passed"),
                "how": "roll call",
                "link": anchor_page(site, r.get("body"), day, f"rc-{key}", near) if day else "",
                "n": int(r.get("number") or 0)})
    for e in VP.load()["journal_only"]:
        key = re.sub(r"[^\w-]", "", e.get("key") or "")
        out[e.get("term") or P.vote_term(e["date"][:4], e["date"])].append({
            "key": key, "body": e.get("body"), "date": e.get("date"), "kind": e.get("kind"),
            "line": e.get("line") or "", "heading": e.get("heading") or "", "words": "",
            "shown": True, "member": e.get("member") or "", "yeas": e.get("yeas"), "nays": e.get("nays"),
            "passed": e.get("passed"), "how": e.get("how"),
            "link": anchor_page(Path(site), e.get("body"), e.get("date"), f"jv-{key}"),
            "n": 10 ** 6 + int(e.get("at") or 0)})
    for t in out:
        out[t].sort(key=lambda x: (x["date"], x["body"], x["n"]), reverse=True)
    out.pop("", None)
    return dict(out)


def _title(h):
    """A heading the Journal printed in capitals, in the site's Title Case."""
    small = {"of", "the", "to", "on", "a", "an", "and", "or", "for", "in", "by"}
    out = []
    for i, w in enumerate(h.split()):
        low = w.lower()
        out.append(low if i and low in small else w.capitalize())
    return " ".join(out)


# The words build_session_pages.journal_extra_html puts before the member.
WHO = {"discipline": "The member it concerned", "privileges": "The member it concerned",
       "member_continue": "The member speaking"}


def row_html(x):
    label = VP.load()["kinds"].get(x["kind"], "") or "Another question"
    if x["line"]:
        desc = E(x["line"])
    elif x["shown"] and x["heading"]:
        desc = f'Under the Journal&rsquo;s heading &ldquo;{E(_title(x["heading"]))}&rdquo;'
    elif x["words"]:
        desc = f'<span class="nbrec">In the record:</span> {E(x["words"])}'
    else:
        # 2013-H-196, 314-1 on 7 November 2013: the file has the count and
        # no words, and the pairing placed it in no Journal. A blank cell
        # reads as a page that failed to draw.
        desc = '<span class="nbrec">The roll-call file gives it no words.</span>'
    # WHO IT WAS ABOUT, where the line does not say. A reprimand's row read
    # "Under the Journal's heading “Motion of Reprimand”" twelve times over
    # for 20 February 2020 (the rendered list, 23 October 2026): the member
    # the passage names, in the Journal's own words as the session day gives
    # them, tells the rows apart without writing a summary no person approved.
    role = WHO.get(x["kind"])
    if role and x.get("member") and not x["line"]:
        title = "Rep." if x["body"] == "H" else "Sen."
        desc += f'<span class="nbwho">{role}: {E(title)} {E(x["member"])}</span>'
    when = E(C.date_words(x["date"])) if x["date"] else ""
    when = f'<a href="{E(x["link"])}">{when}</a>' if x["link"] and when else when
    if x["how"] == "division":
        count, how = f'{x["yeas"]}–{x["nays"]}', "a division"
    elif x["how"] == "voice":
        count, how = "", "a voice vote"
    else:
        count, how = f'{x["yeas"]}–{x["nays"]}', ""
    chip = C.vote_chip(None, x["passed"], "", {}) if x["passed"] is not None else ""
    note = f'<small>{E(how)}</small>' if how else ""
    return (f'<tr data-kind="{E(x["kind"])}"><td class="d" data-l="Day">{when}'
            f'<span class="vch">{E(CHAMBER.get(x["body"], ""))}</span></td>'
            f'<td class="k" data-l="Kind">{E(label)}</td>'
            f'<td class="b" data-l="What it was">{desc}</td>'
            f'<td class="o" data-l="Result">{chip} <i>{E(count)}</i>{note}</td></tr>')


SCRIPT = """<script>
(function(){
  var sel=document.querySelector(".nbkind"),rows=document.querySelectorAll(".nbtab tbody tr"),
      count=document.querySelector(".nbcount");
  if(!sel)return;
  function show(){
    var k=sel.value,n=0;
    [].forEach.call(rows,function(r){var on=!k||r.dataset.kind===k;r.hidden=!on;if(on)n++;});
    count.textContent=n.toLocaleString("en-US")+(n===1?" vote":" votes")+" shown";
    if(history.replaceState)history.replaceState(null,"",location.pathname+(k?"?kind="+k:"")+location.hash);
  }
  sel.addEventListener("change",show);
  var want=new URLSearchParams(location.search).get("kind");
  if(want&&[].some.call(sel.options,function(o){return o.value===want;})){sel.value=want;show();}
})();
</script>"""


def page_body(term, rows, terms, path, base):
    kinds = VP.load()["kinds"]
    n = Counter(x["kind"] for x in rows)
    opts = '<option value="">Every kind</option>' + "".join(
        f'<option value="{E(k)}">{E(w)} ({n[k]})</option>' for k, w in kinds.items() if n[k])
    others = " &middot; ".join(
        (f'<b>{E(t)}</b>' if t == term else f'<a href="{E(href(t))}">{E(t)}</a>')
        for t in sorted(terms, reverse=True))
    shown = sum(1 for x in rows if x["shown"])
    cite = S.cite_block(path, f"Votes Not on a Bill, {term} | Granite Record", base, S.BUILT)
    head = C.record_head({
        "trail": [["Committees", "committees.html"], ["Votes Not on a Bill", ""]],
        "title": f"Votes Not on a Bill, {E(term)}",
        "line": ("Every vote the House and the Senate took in the term on a question that was on "
                 "no bill: its own rules, a ruling of the chair, a member allowed to go on "
                 "speaking, a member&rsquo;s discipline."),
        "facts": [["Votes", f"{len(rows):,}"],
                  ["In the Journal\u2019s Words", f"{shown:,}",
                   "quoted on the session day, with the page"]],
        "actions": cite, "kind": "committee"})
    return (head
            + '<p class="src fill rnote">The kind and the summary are the site&rsquo;s, from the '
              "House and Senate Journals; where a vote&rsquo;s passage could not be matched to it "
              "for certain, the row says how the General Court&rsquo;s roll-call file words it "
              "(&ldquo;In the record&rdquo;) and nothing more. A division or a voice vote is "
              "recorded in the Journal alone: it gives the count, or not even that, and not each "
              "member&rsquo;s vote. Each day leads to the vote on its session day&rsquo;s page.</p>"
            + f'<p class="src">Terms: {others}</p>'
            + f'<div class="bfilt"><label>Kind <select class="nbkind">{opts}</select></label></div>'
            + f'<p class="src nbcount" aria-live="polite">{len(rows):,} votes shown</p>'
            + '<table class="votes vfull nbtab"><thead><tr><th>Day</th><th>Kind</th>'
              "<th>What it was</th><th>Result</th></tr></thead><tbody>"
            + "".join(row_html(x) for x in rows) + "</tbody></table>")


def write(site, base, term, rows, terms):
    path = address(term)
    name = f"Votes Not on a Bill, {term}"
    desc = (f"Every roll call and division the New Hampshire House and Senate took in {term} on a "
            "question that was on no bill -- rules suspensions, appeals of the chair's ruling, "
            "members allowed to continue, reprimands and censures -- with what the Journal says "
            "each was about.")
    html = S.page(S.template(site), path=path, base=base, title=f"{name} | Granite Record",
                  og_title=name, description=desc, globals={"GR_STATIC": True},
                  og_type="website", jsonld=LD.listing(name, desc, base, S.canon(path)),
                  noscript="", skip_label="Skip to the votes", nav_current="committees.html",
                  sr_title="", cite=False)
    assert '<div id="results"></div>' in html, f"{path}: the template has no results slot"
    body = page_body(term, rows, terms, path, base)
    html = html.replace('<div id="results"></div>',
                        f'<div id="results"><div class="nbpage">{body}</div></div>{SCRIPT}', 1)
    out = Path(site) / FOLDER / f"{term}.html"
    out.write_text(S.clean_links(html), encoding="utf-8")
    return base + S.canon(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--rollcalls", default="rollcalls.json")
    a = ap.parse_args()
    site, base = Path(a.site), a.base.rstrip("/")
    try:
        rollcalls = json.loads(Path(a.rollcalls).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        rollcalls = {}
    by_term = rows_of(rollcalls, site)
    (site / FOLDER).mkdir(parents=True, exist_ok=True)
    urls = [write(site, base, t, rows, by_term) for t, rows in sorted(by_term.items())]
    # A term an earlier build wrote and this one has no vote for.
    keep = {f"{t}.html" for t in by_term}
    for stale in (site / FOLDER).glob("*.html"):
        if stale.name not in keep:
            stale.unlink()
    S.sitemap_merge(site, base, urls, f"/{FOLDER}")
    n = sum(len(v) for v in by_term.values())
    quoted = sum(1 for v in by_term.values() for x in v if x["shown"])
    print(f"  {FOLDER}/: {len(by_term)} terms, {n:,} votes on no bill, {quoted:,} in the "
          "Journal's words")
    # SILENCE IS NOT SUCCESS: roll calls on no bill are on record and no page
    # lists them, or the Journal's words reached none of them.
    if any((b or {}).get("_procedural") for b in rollcalls.values()) and not n:
        print(f"  WARNING: roll calls on no bill exist and {FOLDER}/ lists none of them")
    if n and not quoted and VP.load()["rollcalls"]:
        print("  WARNING: journal_motions.json is here and no row shows the Journal's words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
