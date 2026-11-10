#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-07.4
"""
The official results of each general election on file, one page each, under
Officials (docs/design/elections/DESIGN.md and BUILD_PLAN.md; the owner's
word of 7 November 2026: official results only, built from the Secretary of
State's files, for 2024 and 2026):

    site/elections/<YYYY-MM-DD>-general.html   the page: an overview, then a
                                                tab per office on file
    site/elections/<YYYY-MM-DD>-map.json       the district map's data, each
                                                district filled by its winners
    site/elections/index.html                  /elections/, the list of them

    python3 src/pages/build_elections.py --site site [--collected collected]

WHAT IT READS, and nothing else: every collected/election_<year>.json (the
Secretary of State's count of the State Representative and State Senate
races, read by src/parse/parse_sos_results.py); the owner's
corrections/members_elect.json, read and never written; the site data's
site/legislators.json, site/former.json and site/districts.json;
site/district_map.json, which build_district_map.py writes before this runs;
and, for a ballot question, corrections/ballot_results.json (read, never
written) and site/idx/<term>.json for the bill's own page. Nothing here asks
the network.

ONE RULE FOR WHO IS ELECTED. Whether a seat's result is final, who won it
and whom to link are decided by build_members_elect.members_elect, the
function the members-elect step draws from, called here on each election
with that election's own entry of the hand file. Nothing here decides any of
it again. So: no race reads "Elected" until the recount deadline the owner
enters has passed, or its count is a recount's; a race the owner marks not
final reads "Result not final", with "a recount was requested" where she
says so; a held winner is not shown; and a winner links to a member's page
only where that function links them. Losers are shown by name and party.

NO NUMBER BUT THE SECRETARY OF STATE'S. Every count on the page is the
collected file's. Where the reader noted that a file's printed total
disagrees with its own town counts (Grafton 9 in 2026: the Totals cell
leaves out Orange), the card says so in plain words and shows the towns'
sum, which is what the collected file holds. Every other note the reader
made is listed, as it wrote it, under "Notes on the Files".

NOTHING LIVE. No election-night source, no projection, no race call: the
owner's decision of 7 November 2026 leaves the night's source for nearer
2028.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
import shutil
from collections import Counter

import build_date
import build_district_map as BDM
import build_members_elect as BME
import build_town_pages as BT
import components as C
import i18n
import shell as S

E = C.esc
OUT_DIR = "elections"
INDEX = "/elections/"
BALLOTS = Path("corrections") / "ballot_results.json"
COUNTY_CODE = BDM.CODE
# The reader's own words for a printed total that leaves out a town
# (parse_sos_results.py): "...: the file's Totals cell is =SUM(B47:B48), which
# leaves out Orange; read as the towns add up: Ella V. Barrett's column,
# 1,240, where the Totals say 1,152".
TOTALS_NOTE = re.compile(
    r"^(?P<file>\S+), sheet '[^']*', row \d+: the file's Totals cell is [^,]*, which "
    r"leaves out (?P<left>.+?); read as the towns add up: (?P<name>.+?)'s column, "
    r"(?P<sum>[\d,]+), where the Totals say (?P<said>[\d,]+)$")


def page_path(election):
    return f"/{OUT_DIR}/{election}-general.html"


def race_id(key):
    return "r-" + re.sub(r"[^A-Za-z0-9]+", "-", key).strip("-").lower()


def race_name(key, race):
    m = BME.KEY_RE.match(key)
    if m.group(3):
        return f"Senate District {m.group(3)}"
    return f"{m.group(1)} District {m.group(2)}" + (" (floterial)" if race.get("floterial") else "")


def letters(party):
    """The party as the file prints it, in capitals: "d" -> "D", "i/d" -> "I/D"."""
    return str(party or "").upper()


def year_of(election):
    return int(election[:4])


# ------------------------------------------------------------------ reading ---

def elections_on_file(collected):
    """[(election day, path)], newest first, for every results file."""
    found = []
    for p in sorted(Path(collected).glob("election_*.json")):
        if BME.RESULTS_RE.match(p.name):
            found.append(p)
    out = []
    for p in found:
        doc = BME.read_results(p)
        out.append((doc["election"], p, doc))
    return sorted(out, key=lambda x: x[0], reverse=True)


def decided(results, sitting, former, districts, hand_path, today, settled=False, history=None):
    """members_elect's answer for this election: {race key: {seats, elected,
    not_final, held, recount?}}, and its report. The one rule (above).
    `settled` is an election before the latest on file (see settled_in);
    `history` is the seats each member held each term (BME.load_history)."""
    hand, _note = BME.read_hand(hand_path, results["election"])
    races, report = BME.members_elect(results, sitting, former, districts, hand, today,
                                      settled, history)
    return races, report, hand


def settled_in(items, election):
    """Whether `election` is one of those before the latest on file: long
    settled (the owner, 10 November 2026), so its races are final by rule, a
    recount the results mark still saying so. The latest is judged as ever."""
    return election < max(e for e, _p, _r in items)


def mapped(election):
    """Whether the district map can draw this election: only the elections
    held on the districts the map's boundaries are (2022 on). An earlier
    one was held on the 2012 districts, which no boundary here draws."""
    return year_of(election) >= BME.DISTRICTS_SINCE


def same_name(name):
    """A candidate's name as members_elect names a winner ("n"): the
    results file's own, read first name first (build_members_elect.reading_order),
    so a winner is matched to their row however the file spaced or ordered it."""
    return BME.reading_order(name)


def held_names(hand, key):
    """The winners the owner keeps off the pages in this race. Their rows
    are not drawn: a held winner's name and count would say who won."""
    return {same_name(n) for n in ((hand.get("held") or {}).get(key) or {})}


def totals_notes(results):
    """{(file, candidate name): (towns' sum, printed total, place left out)}."""
    out = {}
    for n in results.get("_notes") or []:
        m = TOTALS_NOTE.match(n)
        if m:
            out[(m.group("file"), m.group("name"))] = (m.group("sum"), m.group("said"), m.group("left"))
    return out


def file_of(key, results):
    """The source file a race was read from, by its name: the county's House
    file, or the Senate file holding the district."""
    m = BME.KEY_RE.match(key)
    names = [Path(s.get("file") or "").name for s in results.get("_source") or []]
    if m.group(1):
        c = m.group(1).lower()
        return [n for n in names if f"-house-{c}" in n]
    return [n for n in names if "-state-senate" in n]


def ballot_rows(election, path=BALLOTS):
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    rows = doc.get("rows") if isinstance(doc, dict) else None
    count = lambda v: isinstance(v, int) and not isinstance(v, bool) and v >= 0
    return [r for r in rows or [] if isinstance(r, dict) and r.get("election") == election
            and count(r.get("yes")) and count(r.get("no")) and r["yes"] + r["no"] > 0]


def bill_href(site, term, bill):
    """The bill's own page through the term's index, or "" where the index
    does not hold it (a wrong link is worse than none)."""
    try:
        rows = json.loads((Path(site) / "idx" / f"{term}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    for r in rows if isinstance(rows, list) else []:
        if isinstance(r, dict) and str(r.get("id", "")).upper() == str(bill).upper() and r.get("year"):
            return f"bill/{r['year']}/{str(bill).lower()}.html"
    return ""


# ------------------------------------------------------------------ drawing ---

def candidate_rows(race, elected_names, held=frozenset()):
    shown = [c for c in race["candidates"] if same_name(c["name"]) not in held]
    cands = sorted(shown, key=lambda c: (-c["votes"], c["name"]))
    top = max((c["votes"] for c in cands), default=0) or 1
    counted = sum(c["votes"] for c in race["candidates"]) + int(race.get("scatter") or 0)
    one = race["seats"] == 1 and not held
    out = []
    for c in cands:
        p = letters(c["party"])
        won = elected_names.get(same_name(c["name"]))
        tied = c.get("elected") is None
        chipm = {"party_code": p if len(p) == 1 else "X",
                 "display_full": f'{c["name"]} ({p})' if p else c["name"],
                 "slug": won.get("s") if won and won.get("id") and won.get("s") else ""}
        share = f' <span>&middot; {100 * c["votes"] / counted:.1f}%</span>' if one and counted else ""
        bar_cls = p[:1] if p[:1] in ("R", "D") else "X"
        out.append(
            '<li class="er-row"><span class="er-who">' + C.pchip(chipm)
            + (' <span class="er-wi">write-in</span>' if c.get("write_in") else "")
            + (" " + C.chip("Elected") if won else "")
            + (" " + C.chip("Tied for the last seat") if tied and not won else "")
            + f'</span><span class="er-n">{c["votes"]:,}{share}</span>'
            + f'<span class="er-b" aria-hidden="true"><i class="er-{bar_cls}" '
              f'style="width:{100 * c["votes"] / top:.1f}%"></i></span></li>')
    return "".join(out)


def status_lines(me):
    """"Result not final", "a recount was requested" and the seats with no
    winner shown, in the members-elect block's own words (components.elect_race)."""
    out = ""
    if me.get("not_final"):
        out += ('<p class="elnf"><b>' + i18n.say("en", "elect.not_final", "Result not final") + "</b>"
                + (" " + i18n.say("en", "elect.recount", "&mdash; a recount was requested")
                   if me.get("recount") else "") + "</p>")
    left = (me.get("seats") or 0) - len(me.get("elected") or []) - (me.get("not_final") or 0)
    if left > 0:
        out += ('<p class="elnone">'
                + (i18n.say("en", "elect.none_one", "No member-elect on file for {n} seat.", n=left)
                   if left == 1 else
                   i18n.say("en", "elect.none", "No member-elect on file for {n} seats.", n=left))
                + "</p>")
    return out


def race_card(key, race, me, results, tnotes, election, hand=None, h="h3"):
    elected_names = {e["n"]: e for e in me.get("elected") or []}
    held = held_names(hand or {}, key)
    towns = race.get("towns") or []
    seats = race["seats"]
    meta = [", ".join(towns), f'{seats} seat{"s" if seats != 1 else ""}']
    if len(race["candidates"]) <= seats:
        meta.append("Unopposed")
    if race.get("recounted"):
        meta.append("<b>Recounted</b>")
    notes = []
    files = file_of(key, results)
    for c in race["candidates"]:
        if same_name(c["name"]) in held:
            continue
        for f in files:
            got = tnotes.get((f, c["name"]))
            if got:
                notes.append(
                    f"The Secretary of State&rsquo;s file prints {E(got[1])} as {E(c['name'])}&rsquo;s "
                    f"total, but its own town counts add up to {E(got[0])}, the count shown here: "
                    f"the file&rsquo;s total leaves out {E(got[2])}.")
    scatter = int(race.get("scatter") or 0)
    foot = []
    if seats > 1:
        foot.append(f"Each voter could choose up to {seats}, so no share of the vote is given; "
                    "each bar is scaled to the most votes in the race.")
    if held:
        foot.append("A winner of this race is not shown here yet.")
    if scatter:
        foot.append(f'{scatter:,} scattered write-in vote{"s" if scatter != 1 else ""} '
                    f'{"are" if scatter != 1 else "is"} not shown.')
    return (f'<article class="er-race" id="{race_id(key)}" data-towns="{E(" | ".join(towns).lower())}">'
            f'<{h}>{E(race_name(key, race))}</{h}>'
            f'<p class="er-meta">{" &middot; ".join(E(x) if not x.startswith("<b>") else x for x in meta)}</p>'
            f'<ul class="er-rows">{candidate_rows(race, elected_names, held)}</ul>'
            + status_lines(me)
            + "".join(f'<p class="er-note">{n}</p>' for n in notes)
            + (f'<p class="er-foot">{" ".join(foot)}</p>' if foot else "")
            + "</article>")


def seat_tally(keys, decided_races):
    """{"R": n, "D": n, "other": n, "open": n not final, "none": n no winner shown}."""
    t = Counter()
    for k in keys:
        me = decided_races.get(k) or {}
        for e in me.get("elected") or []:
            p = str(e.get("p") or "")
            t[p if p in ("R", "D") else "other"] += 1
        t["open"] += me.get("not_final") or 0
        t["none"] += (me.get("seats") or 0) - len(me.get("elected") or []) - (me.get("not_final") or 0)
    return t


def chamber_block(name, t, partial=""):
    """A chamber's seats by party. Its seats are members_elect's, the same
    races the parts are counted from, so the parts always add up to it. The
    majority line is drawn only once every seat's result is final: before
    then a party crossing it would say more than the count does."""
    seats = t["R"] + t["D"] + t["other"] + t["open"] + t["none"]
    maj = seats // 2 + 1
    # A chamber with a county missing has no majority to draw: the seats on file
    # are not the chamber.
    final = not t["open"] and not t["none"] and not partial
    parts = [(t["R"], "er-R", "Republican"), (t["D"], "er-D", "Democratic"),
             (t["other"], "er-X", "other or cross-nominated"),
             (t["open"], "er-open", "result not final"), (t["none"], "er-none", "no winner shown")]
    segs = "".join(f'<i class="{c}" style="flex:{n}"></i>' for n, c, _ in parts if n)
    key = "".join(f'<li><span class="l-sw {c}" aria-hidden="true"></span><span><b>{n:,}</b> {w}</span></li>'
                  for n, c, w in parts if n)
    label = "; ".join(f"{n} {w}" for n, _, w in parts if n)
    bar = (f'<div class="l-barb er-maj" style="--at:{100 * maj / seats:.2f}%" aria-hidden="true">{segs}</div>'
           f'<p class="er-majw">The line is the majority, {maj:,} seats.</p>' if final else
           f'<div class="l-barb" aria-hidden="true">{segs}</div>')
    return (f'<section class="er-ch"><h4>{E(name)}</h4>'
            + (f'<p class="er-meta">{seats:,} seats on file; {E(partial)}</p>' if partial else
               f'<p class="er-meta">{seats:,} seats; {maj:,} make a majority.</p>')
            + f'<figure class="l-fig l-bar" role="img" aria-label="{E(name)}: {E(label)}">'
            + bar + f'<ul class="l-barkey">{key}</ul></figure></section>')


def closest(races, decided_races, path, hand, n=8):
    rows = []
    for k, r in races.items():
        if held_names(hand, k) or k not in decided_races:
            continue
        c = sorted(r["candidates"], key=lambda c: -c["votes"])
        if len(c) > r["seats"]:
            rows.append((c[r["seats"] - 1]["votes"] - c[r["seats"]]["votes"], BME.race_order(k), k, r))
    rows.sort(key=lambda x: (x[0], x[1]))
    out = []
    for m, _o, k, r in rows[:n]:
        me = decided_races.get(k) or {}
        tags = (" " + C.chip("Recounted") if r.get("recounted") else "") + \
               (" " + C.chip("Result not final") if me.get("not_final") else "")
        said = ("<span>tied for the last seat</span>" if m == 0 else
                f'<span>last seat by <b>{m:,}</b> vote{"s" if m != 1 else ""}</span>')
        out.append(f'<li><a href="{path}#{race_id(k)}">{E(race_name(k, r))}</a>{said}{tags}</li>')
    return '<ol class="er-close">' + "".join(out) + "</ol>"


def deadline_line(hand, report, election, settled=False):
    d = hand.get("recount_deadline")
    if settled and not d:
        # An election before the latest on file: long settled, final by rule.
        # (Where the owner entered its deadline, that is said as it always was.)
        return ("This election is long past: its results are shown as final, and a race whose "
                "count is a recount&rsquo;s says so.")
    if not d:
        return ("No deadline for asking for a recount is entered for this election, so every result "
                "reads &ldquo;Result not final&rdquo; except a race whose recount has been counted.")
    if report.get("pending"):
        return (f"A candidate may ask for a recount until {E(C.date_words(d, 'full'))}. Until then no "
                "result here is final, except a race whose recount has been counted.")
    return f"The deadline to ask for a recount was {E(C.date_words(d, 'full'))}."


def ballot_block(rows, site, results):
    import build_site_v2 as B2
    out = []
    for r in rows:
        yes, no = r["yes"], r["no"]
        tot = yes + no
        if tot <= 0:
            continue
        ok = B2.ratified(yes, no)
        href = bill_href(site, r.get("term") or "", r.get("bill") or "")
        name = f'{E(r.get("label") or "")} ({E(re.sub(r"^CACR", "CACR ", r.get("bill") or ""))})'
        out.append(
            '<article class="er-race">'
            + f'<h3>{name}</h3>'
            + (f'<p class="er-meta"><a href="{E(href)}">The amendment&rsquo;s page</a></p>' if href else "")
            + '<ul class="er-rows">'
            + f'<li class="er-row"><span class="er-who">Yes</span><span class="er-n">{yes:,} <span>&middot; {100 * yes / tot:.1f}%</span></span>'
              f'<span class="er-b" aria-hidden="true"><i class="er-yes" style="width:{100 * yes / max(yes, no):.1f}%"></i></span></li>'
            + f'<li class="er-row"><span class="er-who">No</span><span class="er-n">{no:,} <span>&middot; {100 * no / tot:.1f}%</span></span>'
              f'<span class="er-b" aria-hidden="true"><i class="er-no" style="width:{100 * no / max(yes, no):.1f}%"></i></span></li>'
            + "</ul>"
            + f'<p class="er-out"><b>{"Ratified" if ok else "Not ratified"}.</b> An amendment needs two thirds of '
              "the votes cast on it (Part Second, Article 100).</p>"
            + (f'<p class="er-foot">{E(r["note"])}</p>' if r.get("note") else "")
            + f'<p class="er-foot">Source: <a href="{E(r.get("source") or "")}" rel="noopener">'
              f'{E(r.get("cite") or "the Secretary of State")}</a>.</p>'
            + "</article>")
    return '<div class="er-cards">' + "".join(out) + "</div>"


def sources_line(results):
    saved = sorted({s.get("saved") for s in results.get("_source") or [] if s.get("saved")})
    urls = sorted({s.get("url") for s in results.get("_source") or [] if s.get("url")})
    day = E(C.date_words(saved[-1], "full")) if saved else ""
    where = (f'<a href="{E(urls[0])}" rel="noopener">results files</a>' if len(urls) == 1
             else "results files")
    return (f"Read from the Secretary of State&rsquo;s {where}"
            + (f", saved {day}" if day else "") + ".")


# ONE WORD FOR A SEAT THE MAP SHOWS NOBODY FOR: its result is not final, or
# the owner has held its winner back. Which of the two is not drawn on the
# map; the race's card says which.
MAP_WORDS = {
    "map.vacant": "No final winner shown", "map.vacant_l": "no final winner shown",
    "map.n_vacant_one": "{n} with no final winner shown", "map.n_vacant": "{n} with no final winner shown",
    "map.dot_vacant_one": "&middot; {n} with no final winner shown",
    "map.dot_vacant": "&middot; {n} with no final winner shown",
    "map.all_vacant": "No final winner is shown yet.",
    "map.of_vacant": "{n} of {m} with no final winner shown"}


def map_doc(base_map, decided_races, places):
    """The night's district map with its people and fill replaced by this
    election's winners. Only the House and Senate layers are drawn."""
    flo = {w[1] for t in places.values() for w in t["w"].values() if w[1]}
    who, nominated = {}, {}
    for key, me in decided_races.items():
        m = BME.KEY_RE.match(key)
        if m.group(3):
            mk = f"senate|{int(m.group(3))}"
        elif m.group(1) in COUNTY_CODE:
            code = f"{COUNTY_CODE[m.group(1)]}{int(m.group(2))}"
            mk = ("float|" if code in flo else "base|") + code
        else:
            continue
        # A cross-nominated winner ("R/D") is drawn on the neutral chip, as
        # the pages draw them, and fills the district with each party that
        # nominated them: never one party's colour alone.
        who[mk] = [{"n": f'{e["n"]} ({e["p"]})' if e.get("p") else e["n"],
                    "p": e["p"] if len(str(e.get("p") or "")) == 1 else "X",
                    **({"s": e["s"]} if e.get("id") and e.get("s") else {})}
                   for e in me.get("elected") or []]
        nominated[mk] = [x for e in me.get("elected") or [] for x in str(e.get("p") or "").split("/") if x]
    doc = {k: v for k, v in base_map.items() if k not in ("elect", "who", "fill")}
    doc["who"] = who
    doc["fill"] = {lk: {fid: BDM.letters(nominated.get(f"{lk}|{fid}", []))
                        for fid in sorted(base_map["layers"][lk]["f"])}
                   for lk in ("base", "float", "senate")}
    doc["_what"] = ("The district map's data for one general election: each House and Senate "
                    "district filled by the parties of the winners whose result is final, from "
                    "the Secretary of State's results (src/pages/build_elections.py). "
                    "Boundaries: NH GRANIT, University of New Hampshire (2022). Not for legal use.")
    return doc


def map_html(election, words):
    return (f'<div id="ermap" class="er-map" data-src="{OUT_DIR}/{election}-map.json"></div>'
            '<link rel="stylesheet" href="/map.css"><script src="/map.js" defer></script>'
            "<script>(function(){var el=document.getElementById(\"ermap\"),api=null;if(!el)return;"
            "function mount(){if(api||!window.GRMap||el.offsetParent===null)return;"
            "api=GRMap.mount(el,{layer:\"senate\",layers:[\"base\",\"senate\"],data:el.dataset.src,"
            f"words:{json.dumps(words)},"
            "prompt:\"Choose a district to see who won it.\"});}"
            "addEventListener(\"DOMContentLoaded\",mount);var p=el.closest(\".twnpane\");"
            "if(p&&window.MutationObserver)new MutationObserver(mount).observe(p,{attributes:true,attributeFilter:[\"hidden\"]});"
            "})();</script>")


FIND_JS = """<script>
(function(){
  var box=document.getElementById("er-find"),say=document.getElementById("er-found");
  if(!box)return;
  box.hidden=false;
  var cards=[].slice.call(document.querySelectorAll("#house .er-race"));
  box.querySelector("input").addEventListener("input",function(){
    var q=this.value.trim().toLowerCase(),n=0;
    cards.forEach(function(c){var on=!q||c.dataset.towns.indexOf(q)>=0;c.hidden=!on;if(on)n++;});
    say.textContent=q?(n===1?"1 race":n+" races")+" with a town or ward matching \\u201c"+this.value.trim()+"\\u201d":"";
    [].slice.call(document.querySelectorAll("#house .er-county")).forEach(function(h){
      var g=h.nextElementSibling;h.hidden=!!q&&!(g&&g.querySelector(".er-race:not([hidden])"));});
  });
})();
</script>"""


def tabs_html(panels):
    tabs, panes = [], []
    for i, (pid, name, body) in enumerate(panels):
        on = i == 0
        tabs.append(f'<button type="button" role="tab" id="tab-{pid}" data-pane="{pid}" '
                    f'aria-controls="{pid}" aria-selected="{"true" if on else "false"}" '
                    f'tabindex="{0 if on else -1}">{name}</button>')
        panes.append(f'<div class="twnpane" id="{pid}" role="tabpanel" aria-labelledby="tab-{pid}">'
                     f'<h2 class="twnph">{name}</h2>{body}</div>')
    return ('<div class="twntabs" role="tablist" aria-label="Offices" hidden>' + "".join(tabs) + "</div>"
            + "".join(panes))


def county_groups(keys, races, decided_races, results, tnotes, election, hand):
    by = {}
    for k in sorted(keys, key=BME.race_order):
        by.setdefault(BME.KEY_RE.match(k).group(1), []).append(k)
    out = []
    for county, ks in by.items():
        out.append(f'<h3 class="er-county" id="er-{county.lower()}">{E(county)} County '
                   f'<span>{len(ks)} district{"s" if len(ks) != 1 else ""}</span></h3>'
                   '<div class="er-cards">'
                   + "".join(race_card(k, races[k], decided_races.get(k) or {}, results, tnotes,
                                       election, hand, h="h4") for k in ks) + "</div>")
    return "".join(out)


def not_on_file_words(results):
    """What the Secretary of State's site no longer serves for this election,
    in words, or "": the counties with no House file, and the Senate."""
    gone = results.get("_not_on_file") or {}
    parts = [f"{c} County\u2019s State Representative results" for c in gone.get("counties") or []]
    if gone.get("senate"):
        parts.append("the State Senate results")
    return " and ".join(parts)


def page_body(election, results, decided_races, report, hand, site, ballots, settled=False):
    races = results["races"]
    path = page_path(election)
    senate = [k for k in races if k.startswith("S|")]
    house = [k for k in races if k.startswith("H|")]
    tnotes = totals_notes(results)
    year = year_of(election)
    st, ht = seat_tally(senate, decided_races), seat_tally(house, decided_races)
    final_all = not st["open"] and not ht["open"] and not st["none"] and not ht["none"]
    gone = results.get("_not_on_file") or {}
    gone_words = not_on_file_words(results)
    house_partial = ("this chamber has no majority line because "
                     + ", ".join(f"{c} County" for c in gone.get("counties") or [])
                     + " is not on file") if gone.get("counties") else ""
    drawn_map = mapped(election)
    overview = (
        '<section class="ofpart"><h3 class="er-h">Seats Won</h3><div class="er-chs">'
        + (chamber_block("State Senate", st) if senate else "")
        + chamber_block("State House", ht, house_partial) + "</div>"
        + '<p class="src">The winners are the candidates with the most votes, as many as a race has '
          "seats. The Secretary of State&rsquo;s files count the votes; they do not name winners.</p></section>"
        + ('<section class="ofpart"><h3 class="er-h">The Map</h3>'
           '<p class="src fill">Each district is colored by the party of the candidates it elected; '
           "a district that elected both parties, or a candidate both nominated, is striped. A district "
           "with no final winner shown is hatched; choose a district to see what is still to come.</p>"
           + map_html(election, MAP_WORDS) + "</section>" if drawn_map else "")
        + '<section class="ofpart"><h3 class="er-h">Closest Races</h3>'
          '<p class="src">By how many votes the last seat was won, fewest first.</p>'
        + closest(races, decided_races, path, hand) + "</section>")
    notes = [n for n in results.get("_notes") or [] if not TOTALS_NOTE.match(n)]
    if notes:
        overview += ('<section class="ofpart"><h3 class="er-h">Notes on the Files</h3>'
                     '<p class="src">What the reader of the Secretary of State&rsquo;s files noticed in '
                     "them, in its own words. A printed total that leaves out a town is said on its "
                     "race&rsquo;s card instead.</p><ul class=\"er-notes\">"
                     + "".join(f"<li>{E(n)}</li>" for n in notes) + "</ul></section>")
    find = ('<div class="er-find" id="er-find" hidden><label for="er-q">Find a town or ward</label>'
            '<input id="er-q" type="search" autocomplete="off" placeholder="A town or ward">'
            '<p class="count" id="er-found" role="status"></p></div>')
    panels = [("overview", "Overview", overview)]
    if senate:
        panels.append(("senate", f'State Senate <span class="ofn">({len(senate)})</span>',
                       '<div class="er-cards">' + "".join(
                           race_card(k, races[k], decided_races.get(k) or {}, results, tnotes,
                                     election, hand)
                           for k in sorted(senate, key=BME.race_order)) + "</div>"))
    panels.append(("house", f'State House <span class="ofn">({len(house)})</span>',
                   find + county_groups(house, races, decided_races, results, tnotes, election,
                                        hand)))
    if ballots:
        panels.append(("questions", f'Ballot Questions <span class="ofn">({len(ballots)})</span>',
                       ballot_block(ballots, site, results)))
    lead = (f"{E(C.date_words(election, 'full'))}. Every State Senate and State House race, as the "
            "Secretary of State&rsquo;s results files count it, with the votes for every candidate.")
    if gone_words:
        # Said, and filled from nowhere: what the Secretary of State's site no
        # longer serves is not on this page, and nothing stands in for it.
        lead += (f" Not on this page: {E(gone_words)}, which the Secretary of State&rsquo;s site "
                 "no longer serves; no other source stands in for it.")
    if any(r.get("surnames") for r in races.values()):
        lead += (" The State Representative files of this year print each candidate&rsquo;s surname "
                 "only, and they are shown as printed.")
    if not drawn_map:
        lead += (" This election was held on the 2012 districts, which the district map does not "
                 "draw, so there is no map here.")
    return ('<div class="officials er-page">'
            f'<p class="er-crumb"><a href="officials.html">Officials</a> &rsaquo; '
            f'<a href="{OUT_DIR}/">Elections</a></p>'
            f"<h1>{year} General Election</h1>"
            f'<p class="lead">{lead}</p>'
            '<div class="er-state">'
            + C.chip("Official results, some not on file" if gone_words else
                     "Official results" if final_all else "Official results, not all final")
            + f"<span>{sources_line(results)} {deadline_line(hand, report, election, settled)}</span></div>"
            '<p class="src er-other">The Governor, the Executive Council, Congress and the county '
            "offices are not on this page yet: their results files have not been read.</p>"
            + tabs_html(panels) + BT.TABS_JS + FIND_JS + "</div>")


def index_body(items):
    rows = "".join(
        f'<li><a href="{page_path(e).lstrip("/")}">{year_of(e)} General Election</a>'
        f'<span>{E(C.date_words(e, "full"))}</span></li>' for e, _ in items)
    return ('<div class="officials er-page"><p class="er-crumb"><a href="officials.html">Officials</a>'
            " &rsaquo; Elections</p><h1>Elections</h1>"
            '<p class="lead">The official results of each general election on file: every State Senate '
            "and State House race, from the Secretary of State&rsquo;s results files.</p>"
            f'<ul class="er-index">{rows}</ul></div>')


def write_page(site, base, path, title, desc, body, into):
    html = S.page(S.template(site), path=path, base=base, title=title, description=desc,
                  og_title=title.split(" | ")[0], globals={"GR_STATIC": True}, noscript="",
                  skip_label="Skip to the results", sr_title="", og_type="website",
                  nav_current="officials.html", cite=False)
    html = html.replace('<div id="results"></div>', f'<div id="results">{body}</div>', 1)
    assert body[:40] in html, f"{path}: the template has no results slot"
    # Into the folder the build draws in, at the page's place under /elections/.
    out = Path(into) / path.lstrip("/").split("/", 1)[1]
    if path.endswith("/"):
        out = out / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(S.clean_links(html), encoding="utf-8")


def build(site, base, collected, hand_path, today, sponsors=BME.SPONSORS_DEFAULT):
    """Every page drawn into a folder beside site/elections/ first, and put in
    its place only once all of them are drawn: a results file the reader
    refuses, or any failure, leaves last night's pages as they were rather
    than none. With no results file at all, the folder and its addresses in
    the sitemap both go."""
    site = Path(site)
    dest = site / OUT_DIR
    items = elections_on_file(collected)
    if not items:
        if dest.exists():
            shutil.rmtree(dest)
        S.sitemap_merge(site, base, [], "/elections/")
        return [], []
    sitting = BME.load_json(site / "legislators.json", "the sitting roster")
    former = BME.load_json(site / "former.json", "the former members")
    districts = BME.load_json(site / "districts.json", "the district table")
    history = BME.load_history(sponsors)
    base_map = BME.load_json(site / "district_map.json", "the district map's data")
    places = base_map["places"]
    new = site / f".{OUT_DIR}.new"
    if new.exists():
        shutil.rmtree(new)
    new.mkdir()
    made, urls, warn = [], [], []
    for election, _p, results in items:
        settled = settled_in(items, election)
        races_me, report, hand = decided(results, sitting, former, districts, hand_path, today,
                                         settled, history)
        if not hand.get("recount_deadline") and not settled:
            warn.append(f"{election}: no recount_deadline in {Path(hand_path).as_posix()}, so every "
                        "race but a recounted one reads Result not final")
        ballots = ballot_rows(election)
        body = page_body(election, results, races_me, report, hand, site, ballots, settled)
        year = year_of(election)
        path = page_path(election)
        write_page(site, base, path,
                   S.title_of(f"{year} New Hampshire General Election results"),
                   f"The official results of New Hampshire's {year} general election: every State "
                   "Senate and State House race, from the Secretary of State's files.", body, new)
        if mapped(election):
            (new / f"{election}-map.json").write_text(
                json.dumps(map_doc(base_map, races_me, places), ensure_ascii=False,
                           separators=(",", ":")), encoding="utf-8")
        made.append((election, races_me))
        urls.append(base.rstrip("/") + S.canon(path))
    write_page(site, base, INDEX, S.title_of("New Hampshire election results"),
               "The official results of each New Hampshire general election on file.",
               index_body(made), new)
    urls.append(base.rstrip("/") + INDEX)
    if dest.exists():
        shutil.rmtree(dest)
    new.rename(dest)
    S.sitemap_merge(site, base, urls, "/elections/")
    return made, warn


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    ap.add_argument("--collected", default="collected")
    ap.add_argument("--hand", default=str(BME.HAND_DEFAULT))
    ap.add_argument("--sponsors", default=str(BME.SPONSORS_DEFAULT),
                    help="text_sponsors.json, which holds the seat each member printed each term")
    a = ap.parse_args()
    today = build_date.today().isoformat()
    try:
        made, warn = build(a.site, a.base, a.collected, Path(a.hand), today, a.sponsors)
    except BME.Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 1
    if not made:
        print(f"elections: WARNING no results in {a.collected}/ (election_<year>.json): no page "
              "written, and any earlier pages removed")
        return 0
    for w in warn:
        print(f"elections: WARNING {w}")
    for election, races in made:
        seats = sum(r["seats"] for r in races.values())
        won = sum(len(r["elected"]) for r in races.values())
        nf = sum(r["not_final"] for r in races.values())
        print(f"elections: {page_path(election)}, {len(races)} races, {seats} seats: "
              f"{won} elected, {nf} not final, {seats - won - nf} with no winner shown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
