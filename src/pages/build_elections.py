#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-07.12
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
site/elect_pages.json, where it is on disk, the new members-elect's
provisional pages (build_elect_pages.py);
and, for a ballot question, corrections/ballot_results.json (read, never
written: the constitutional amendments), collected/ballot_questions.json
(the other questions, read from the Secretary of State's spreadsheets by
src/parse/parse_sos_questions.py: 2022's convention question and 2026's
school district local tax cap) and site/idx/<term>.json for the bill's own
page. Each question's card prints its own rule, from its kind, and the
number of voters who would have had to vote the other way where the
statewide count decides it; a question the statewide count does not decide
(the local tax cap, decided by each school district and administrative unit)
states no outcome. Nothing here asks the network.

ONE RULE FOR WHO IS ELECTED. Whether a seat's result is final, who won it
and whom to link are decided by build_members_elect.members_elect, the
function the members-elect step draws from, called here on each election
with that election's own entry of the hand file. Nothing here decides any of
it again. So: no race reads "Elected" until the recount deadline the owner
enters has passed, or its count is a recount's; a race the owner marks not
final reads "Result not final", with "a recount was requested" where she
says so; a held winner is not shown; and a winner links to a member's page
only where that function links them. Losers are shown by name and party.

A NEW WINNER LINKS TO THEIR PROVISIONAL PAGE (the owner, 16 November 2026:
member-elect pages, linked wherever a member-elect's name is printed): the
page site/elect_pages.json lists for that election, race and name, which
build_elect_pages.py writes and the Officials tab and the town pages already
link ("e"). On the race's card and the election's map, and nowhere a member
is linked: never another member's record, and none for an election the list
is not of.

NO NUMBER BUT THE SECRETARY OF STATE'S. Every count on the page is the
collected file's. Where the reader noted that a file's printed total
disagrees with its own town counts (Grafton 9 in 2026: the Totals cell
leaves out Orange), the card says so in plain words and shows the towns'
sum, which is what the collected file holds. Every other note the reader
made is listed, as it wrote it, under "Notes on the Files".

THE MARGIN IS election_margin.py's, the one rule (the elections display
design of 19 November 2026, approved that day): each card's label at its top
right in the party chip's shape ("R+1.3", "R+0.7 over R", Unopposed, Tied),
the gap in votes and the votes that would have changed it under the rows; on
the House and Senate tabs, margin buttons with their counts and an order,
smallest margin first, which the overview's Smallest Margins lists the first
eight of. A race whose winner the owner holds back has no margin shown: it
would say who won. Figures only: never "close", "safe" or "competitive".

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
import election_margin as EM
import i18n
import shell as S

E = C.esc
OUT_DIR = "elections"
INDEX = "/elections/"
BALLOTS = Path("corrections") / "ballot_results.json"
QUESTIONS = Path("collected") / "ballot_questions.json"
# The Secretary of State's results page for each year's general election, the
# addresses corrections/ballot_results.json already cites for the same files.
SOS_PAGES = {2022: "https://www.sos.nh.gov/elections/2022-election-results/2022-general-election-results",
             2024: "https://www.sos.nh.gov/2024-general-election-results",
             2026: "https://www.sos.nh.gov/2026-general-election-results"}
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


def provisional(site):
    """{election day: {(race key, name): slug}}: the new members-elect's
    provisional pages, site/elect_pages.json's, under the election they are
    of; {} where there is no list or it will not read."""
    f = Path(site) / "elect_pages.json"
    try:
        doc = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except ValueError:
        return {}
    if not isinstance(doc, dict) or not doc.get("election"):
        return {}
    return {doc["election"]: {(p.get("race"), p.get("name")): p["slug"]
                              for p in doc.get("pages") or [] if p.get("slug")}}


def with_pages(races_me, pages):
    """Give each new winner of `races_me` that `pages` ({(race key, name):
    slug}, provisional's for this election) names their page's "e", as
    build_members_elect gives the members-elect file's: the chip on the
    race's card and the map then links it (chip_slug)."""
    for key, me in (races_me or {}).items():
        for e in me.get("elected") or []:
            if e.get("k") == "new" and (pages or {}).get((key, e.get("n"))):
                e["e"] = pages[(key, e["n"])]
    return races_me


def chip_slug(e):
    """The page a winner's chip links to: a member's, where members_elect
    linked one by id; a new person's provisional page ("e"); else none."""
    if not e:
        return ""
    if e.get("id") and e.get("s"):
        return e["s"]
    return (e.get("e") or "") if e.get("k") == "new" else ""


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


def question_number(label):
    m = re.search(r"(\d+)\s*$", str(label or ""))
    return int(m.group(1)) if m else 99


def question_cards(election, path=BALLOTS, questions=QUESTIONS):
    """Every question on an election's ballot, one dict each, in the order
    of the ballot: a constitutional amendment from corrections/ballot_results.json
    (kind "cacr", its row as it stands), and every other kind from
    collected/ballot_questions.json, which src/parse/parse_sos_questions.py
    reads from the Secretary of State's spreadsheets. A CACR's count is the
    corrections file's, never the spreadsheets'; the spreadsheets' own figure
    is kept beside it only to say where the Secretary of State's files
    disagree (the 2026 county files against its statewide summary)."""
    try:
        doc = json.loads(Path(questions).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        doc = {}
    mine = (doc.get("elections") or {}).get(election) or []
    cards = [dict(r, kind="cacr") for r in ballot_rows(election, path)]
    for r in cards:
        for q in mine:
            if q.get("kind") == "cacr" and q.get("label") == r.get("label") and q.get("county_sum"):
                r["county_sum"] = q["county_sum"]
    for q in mine:
        if q.get("kind") != "cacr" and q.get("yes", 0) + q.get("no", 0) > 0:
            cards.append(dict(q, source=SOS_PAGES.get(year_of(election), ""),
                              cite=f"{year_of(election)} general election results, sos.nh.gov"))
    return sorted(cards, key=lambda c: question_number(c.get("label")))


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

INC_WORDS = {"H": "held a seat in the House on election day",
             "S": "held a seat in the Senate on election day"}


def inc_mark(chamber):
    """The asterisk after an incumbent's name, its words in its title."""
    return f' <abbr class="er-inc" title="{INC_WORDS[chamber]}">*</abbr>'


def inc_legend(chamber):
    """The one line under a list of cards that marks any (the owner, 19 November 2026)."""
    return f'<p class="src er-incl">* {INC_WORDS[chamber]}.</p>'


def candidate_rows(race, elected_names, held=frozenset(), mine=None, primary=False, inc=frozenset(),
                   chamber="H"):
    """The race's rows, most votes first. `mine` is the candidate a member's
    Elections tab is about (same_name), whose row is marked er-me.

    A SHARE ON EVERY ROW. One seat: of every vote cast in the race, the
    scattered write-ins included, as it always was. More than one seat (the
    owner, 19 November 2026, "share of all votes"): of all the votes cast for
    the candidates listed, the scattered write-ins left out -- Strafford 21
    of 2026, Alice Wade's 8,807 of 29,275, 30.1%. None where a winner is held
    back: the shares would say what the hidden row holds.

    A PRIMARY (`primary`, a member's Elections tab): the reader's leaders,
    "nominated": true, are marked Most votes -- never "nominated", which the
    files do not say (the design's decision 4) -- and nothing is Elected.

    AN INCUMBENT (`inc`, same_name of each, build_member_elections.incumbents:
    a certain match who held a seat of the race's chamber on election day) has
    an asterisk after the name."""
    shown = [c for c in race["candidates"] if same_name(c["name"]) not in held]
    cands = sorted(shown, key=lambda c: (-c["votes"], c["name"]))
    top = max((c["votes"] for c in cands), default=0) or 1
    counted = sum(c["votes"] for c in race["candidates"]) + (
        int(race.get("scatter") or 0) + int(race.get("other_votes") or 0) if race["seats"] == 1 else 0)
    one = not held
    out = []
    for c in cands:
        p = letters(c["party"])
        won = elected_names.get(same_name(c["name"]))
        tied = c.get("elected") is None and not primary
        most = primary and c.get("nominated") is True
        chipm = {"party_code": p if len(p) == 1 else "X",
                 "display_full": f'{c["name"]} ({p})' if p else c["name"],
                 "slug": chip_slug(won)}
        share = f' <span>&middot; {100 * c["votes"] / counted:.1f}%</span>' if one and counted else ""
        bar_cls = p[:1] if p[:1] in ("R", "D") else "X"
        out.append(
            '<li class="er-row' + (" er-me" if mine and same_name(c["name"]) == mine else "")
            + '"><span class="er-who">' + C.pchip(chipm)
            + (inc_mark(chamber) if same_name(c["name"]) in inc else "")
            + (' <span class="er-wi">write-in</span>' if c.get("write_in") else "")
            + (" " + C.chip("Elected") if won else "")
            + (" " + C.chip("Most votes") if most else "")
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


def margin_of(key, race, election, hand=None, primary=""):
    """The race's margin, election_margin's (the one rule), or None where a
    winner of the race is held back: its label and its gap would say who won.
    `primary` is a primary's party: its label then has no letter ("+42.2")."""
    if held_names(hand or {}, key):
        return None
    stage = "primary" if primary else "general"
    return EM.margin(race, EM.results_contest(election, key, stage, primary.lower()), primary=bool(primary))


def margin_chip(m):
    """The margin's label in the one chip, coloured by the last winner's party
    as the party chip is (pt-R, pt-D, pt-I); a cross-nomination, a party with
    no colour of its own, Unopposed and Tied on the neutral chip; none for a
    race with no margin."""
    if not m or not m.get("label"):
        return ""
    p = m["label"].split("+")[0] if m["status"] == "contested" else ""
    return C.chip(EM.words(m), "er-mg" + (f" pt-{p}" if p in ("R", "D", "I") else ""))


def margin_line(m, seats, final, primary=False):
    """The figures beside the label (the owner's of 11 November 2026): the gap
    in votes and the points and, once the result is final, the votes that
    would have changed it, floor(gap/2)+1 (election_margin.flip). Figures only.
    A primary's says the most votes by how many, and no more: what the files
    count, never who was nominated."""
    if not m or m["status"] != "contested":
        return ""
    g = m["gap"]
    gap = f'<b>{g:,} vote{"s" if g != 1 else ""}</b>, {m["points"]:.1f} points'
    if primary:
        return ('<p class="er-out">' + ("Most votes" if seats == 1 else
                                        f"The last of the {seats} places with the most votes")
                + f" by {gap}.</p>")
    if not final:
        return (f'<p class="er-out">The gap {"between the first two" if seats == 1 else "at the last seat"} '
                f"is {gap}.</p>")
    n = EM.flip(m)
    if seats == 1:
        return (f'<p class="er-out">Won by {gap}. {n:,} voter{"s" if n != 1 else ""} choosing the '
                "other way would have changed the result.</p>")
    return (f'<p class="er-out">The last seat by {gap}. {n:,} vote{"s" if n != 1 else ""} moved from '
            "the last winner to the first out would have changed the result.</p>")


def margin_data(m):
    """The card's data-band, data-points and data-gap, which the page's filter
    and order read (MARGIN_JS): the points of a tie are 0, of a race with no
    margin nothing. (A County filter is to add data-county beside them.)"""
    s = (m or {}).get("status")
    pts = f'{m["points"]:.1f}' if s == "contested" else "0" if s == "tie" else ""
    gap = str(m["gap"]) if s in ("contested", "tie") else ""
    return f' data-band="{EM.band(m)}" data-points="{pts}" data-gap="{gap}"'


def race_card(key, race, me, results, tnotes, election, hand=None, h="h3", mine=None, anchor=True,
              primary="", inc=frozenset()):
    """One race as its card. The elections page draws every race so; a
    member's Elections tab draws each race the member is in by this same
    function (build_member_elections), with `mine` their candidate's name
    (same_name) to mark their row, and anchor=False: the card there is no
    link's target, and one race may be on the tab for two elections. Its
    margin's label is at the top right of either (margin_chip), and the gap
    under the rows (margin_line); the page's card also carries the margin for
    its filter (margin_data). `primary` is a primary's party, for a member's
    tab (build_member_elections.primary_rows): its leaders Most votes, its
    label with no letter; the race's "other_votes", the votes for candidates
    of another party the tab leaves off, are said in the note."""
    elected_names = {e["n"]: e for e in me.get("elected") or []}
    held = held_names(hand or {}, key)
    towns = race.get("towns") or []
    seats = race["seats"]
    m = margin_of(key, race, election, hand, primary)
    meta = [", ".join(towns), f'{seats} seat{"s" if seats != 1 else ""}']
    if len(race["candidates"]) <= seats and not (m and m["status"] == "unopposed"):
        # Said once: the chip says it wherever it is drawn.
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
        foot.append(f"Each voter could choose up to {seats}, so a share is of all the votes cast for "
                    "the candidates listed; each bar is scaled to the most votes in the race.")
    if held:
        foot.append("A winner of this race is not shown here yet.")
    if scatter:
        foot.append(f'{scatter:,} scattered write-in vote{"s" if scatter != 1 else ""} '
                    f'{"are" if scatter != 1 else "is"} not shown.')
    other, n_other = race.get("other_votes"), race.get("other_rows") or 0
    if n_other:
        foot.append(f'{n_other:,} candidate{"s" if n_other != 1 else ""} of another party, with '
                    f'{other:,} vote{"s" if other != 1 else ""}, {"are" if n_other != 1 else "is"} '
                    "not shown.")
    at = (f' id="{race_id(key)}" data-towns="{E(" | ".join(towns).lower())}"' + margin_data(m)
          if anchor else "")
    return (f'<article class="er-race"{at}>'
            f'<div class="er-hd"><{h}>{E(race_name(key, race))}</{h}>{margin_chip(m)}</div>'
            f'<p class="er-meta">{" &middot; ".join(E(x) if not x.startswith("<b>") else x for x in meta)}</p>'
            f'<ul class="er-rows">{candidate_rows(race, elected_names, held, mine, bool(primary), inc, key[0])}</ul>'
            + margin_line(m, seats, not me.get("not_final"), bool(primary))
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


def closest(races, decided_races, path, hand, n=8, election=None):
    """The `n` races of smallest margin, the order the page's "Smallest margin
    first" takes (election_margin.order_key): a tie, then by points, then by
    votes. A race with a held winner, or none contested, is not among them."""
    rows = []
    for k, r in races.items():
        if k not in decided_races:
            continue
        mg = margin_of(k, r, election or "", hand)
        if mg and mg["status"] in ("contested", "tie"):
            rows.append((EM.order_key(mg), BME.race_order(k), k, r, mg))
    rows.sort(key=lambda x: (x[0], x[1]))
    out = []
    for _key, _o, k, r, mg in rows[:n]:
        m = mg["gap"]
        me = decided_races.get(k) or {}
        tags = (" " + C.chip("Recounted") if r.get("recounted") else "") + \
               (" " + C.chip("Result not final") if me.get("not_final") else "")
        said = ("<span>tied for the last seat</span>" if m == 0 else
                f'<span>last seat by <b>{m:,}</b> vote{"s" if m != 1 else ""}</span>')
        out.append(f'<li><a href="{path}#{race_id(k)}">{E(race_name(k, r))}</a>{margin_chip(mg)}'
                   f"{said}{tags}</li>")
    return '<ol class="er-close">' + "".join(out) + "</ol>"


def margin_filter(pane, keys, races, election, hand):
    """The margin buttons, each with the number of the pane's races it shows,
    and the order, above a pane's cards (the design's decisions 5 and 7: words
    are figures only). Hidden until the page's script (MARGIN_JS) shows it, so
    a reader without one meets no control that does nothing."""
    bands = Counter(EM.band(margin_of(k, races[k], election, hand)) for k in keys)
    btns = [("", "Any", len(keys))] + [(b, w, bands.get(b, 0)) for b, w in EM.BANDS]
    return (f'<div class="er-filt bfilt" id="er-mf-{pane}" data-pane="{pane}" hidden>'
            f'<div class="er-mfl"><span class="er-lab" id="er-mfl-{pane}">Margin</span>'
            f'<div class="wkchips er-seg" role="group" aria-labelledby="er-mfl-{pane}">'
            + "".join(f'<button type="button" data-band="{b}" aria-pressed="{"true" if not b else "false"}">'
                      f'{w} <span class="er-c">{n:,}</span></button>' for b, w, n in btns)
            + "</div></div>"
            f'<label>Order<select id="er-mo-{pane}"><option value="district">By district</option>'
            '<option value="small">Smallest margin first</option>'
            '<option value="large">Largest margin first</option></select></label>'
            f'<p class="count er-count" role="status"></p></div>')


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


def flip_two_thirds(yes, no):
    """How many voters changing their vote would have changed whether two
    thirds voted yes. A voter who moves from one side to the other moves one
    vote and leaves the total where it was, so for a question that fell short
    it is the yes votes short of two thirds of the total, rounded up, and for
    one that reached it the yes votes above two thirds, rounded down, and one
    more."""
    t = yes + no
    return (3 * yes - 2 * t) // 3 + 1 if 3 * yes >= 2 * t else -((3 * yes - 2 * t) // 3)


def flip_majority(yes, no):
    """The same for a majority, where a tie is not a majority: a voter who
    changes sides moves the gap by two, so a question that carried is undone
    when half the gap, rounded up, have changed sides (a tie is enough), and
    one that did not carry is carried by half the gap, rounded down, and one
    more."""
    gap = abs(yes - no)
    return (gap + 1) // 2 if yes > no else gap // 2 + 1


def two_thirds(yes, no):
    return yes + no > 0 and 3 * yes >= 2 * (yes + no)


def question_title(c):
    name = E(c.get("label") or "")
    if c["kind"] == "cacr":
        return f'{name} ({E(re.sub(r"^CACR", "CACR ", c.get("bill") or ""))})'
    if c["kind"] == "convention":
        return name + " " + i18n.say("en", "elect.q.convention_t", "(the convention question)")
    return name + " " + i18n.say("en", "elect.q.cap_t", "(school district local tax cap, {bill})",
                                 bill=E(c.get("measure") or "HB 1300"))


def question_rule(c):
    """The rule the question is decided by, in its source's words: the one
    place a card's rule comes from."""
    if c["kind"] == "cacr":
        return i18n.say("en", "elect.q.cacr_rule", "An amendment needs two thirds of the votes cast on it "
                        "(Part Second, Article 100).")
    if c["kind"] == "convention":
        return i18n.say("en", "elect.q.conv_rule",
                        "If a majority of the qualified voters voting on the question approves it, "
                        "delegates are chosen (Part Second, Article 100(b)).")
    return i18n.say("en", "elect.q.cap_rule",
                    "A school district&rsquo;s local tax cap, and a school administrative unit&rsquo;s "
                    "fixed cap, is binding if a &ldquo;3/5 majority of the voters voting in the "
                    "municipalities and wards&rdquo; it serves approve the question (RSA 32:5-i, "
                    "VI(a) and (b), added by HB 1300, chapter 324 of 2026).")


def question_decision(c):
    """(the decision, the flip sentence) of a question the statewide count
    decides; for the local tax cap, which it does not, (the sentence saying so, "")."""
    yes, no = c["yes"], c["no"]
    if c["kind"] == "local_cap":
        return (i18n.say("en", "elect.q.cap_out",
                         "The statewide total decides nothing, because each school district and each "
                         "school administrative unit counts only the towns and wards it serves. Which "
                         "of them reached three fifths is not shown yet: no table of which town or "
                         "ward is in which school district is on hand."), "")
    if c["kind"] == "cacr":
        ok, n = two_thirds(yes, no), flip_two_thirds(yes, no)
        head = (i18n.say("en", "elect.q.ratified", "Ratified") if ok
                else i18n.say("en", "elect.q.not_ratified", "Not ratified"))
    else:
        ok, n = yes > no, flip_majority(yes, no)
        head = (i18n.say("en", "elect.q.approved", "Approved") if ok
                else i18n.say("en", "elect.q.not_approved", "Not approved"))
    flip = (i18n.say("en", "elect.q.flip_one", "The gap between yes and no is {gap}. {n} voter would have had to vote the "
                     "other way to change the result.", gap=f"{abs(yes - no):,}", n=f"{n:,}") if n == 1 else
            i18n.say("en", "elect.q.flip", "The gap between yes and no is {gap}. {n} voters would have had to vote the "
                     "other way to change the result.", gap=f"{abs(yes - no):,}", n=f"{n:,}"))
    return head, flip


def county_table(c):
    rows = "".join(
        f'<tr><th scope="row" class="is-text">{E(name)}</th><td class="l-num">{y:,}</td>'
        f'<td class="l-num">{n:,}</td><td class="l-num">{100 * y / (y + n):.1f}%</td></tr>'
        for name, (y, n) in (c.get("counties") or {}).items() if y + n > 0)
    if not rows:
        return ""
    return ('<div class="l-tablewrap"><table class="l-table"><caption>'
            + i18n.say("en", "elect.q.county_cap", "By county") + '</caption><thead><tr><th scope="col">'
            + i18n.say("en", "elect.q.county", "County") + '</th><th scope="col" class="l-num">'
            + i18n.say("en", "elect.q.yes", "Yes") + '</th><th scope="col" class="l-num">'
            + i18n.say("en", "elect.q.no", "No") + '</th><th scope="col" class="l-num">'
            + i18n.say("en", "elect.q.yes_share", "Yes share") + f"</th></tr></thead><tbody>{rows}</tbody>"
            "</table></div>")


def county_disagreement(r):
    """Where the Secretary of State's ten county files do not add up to its
    statewide summary, said once with both figures: the card shows the
    summary's, the count the corrections file holds."""
    cy, cn = r["county_sum"]
    same = two_thirds(r["yes"], r["no"]) == two_thirds(cy, cn)
    return i18n.say("en", "elect.q.disagree",
                    "The ten county files add up to {cy} yes and {cn} no; the statewide summary, shown "
                    "above, has {y} yes and {n} no. {same}", cy=f"{cy:,}", cn=f"{cn:,}",
                    y=f"{r['yes']:,}", n=f"{r['no']:,}",
                    same=(i18n.say("en", "elect.q.same", "The result is the same on either count.") if same
                          else i18n.say("en", "elect.q.differ", "The result is not the same on both counts.")))


def ballot_block(rows, site, results):
    out = []
    for r in rows:
        yes, no = r["yes"], r["no"]
        tot = yes + no
        if tot <= 0:
            continue
        href = bill_href(site, r.get("term") or "", r.get("bill") or "") if r["kind"] == "cacr" else ""
        head, flip = question_decision(r)
        cap = r["kind"] == "local_cap"
        top = max(yes, no)
        out.append(
            '<article class="er-race">'
            + f'<h3>{question_title(r)}</h3>'
            + (f'<p class="er-meta"><a href="{E(href)}">The amendment&rsquo;s page</a></p>' if href else "")
            + ('<p class="er-foot">' + i18n.say("en", "elect.q.statewide",
                                                "Statewide total:") + "</p>" if cap else "")
            + '<ul class="er-rows">'
            + f'<li class="er-row"><span class="er-who">Yes</span><span class="er-n">{yes:,} <span>&middot; {100 * yes / tot:.1f}%</span></span>'
              f'<span class="er-b" aria-hidden="true"><i class="er-yes" style="width:{100 * yes / top:.1f}%"></i></span></li>'
            + f'<li class="er-row"><span class="er-who">No</span><span class="er-n">{no:,} <span>&middot; {100 * no / tot:.1f}%</span></span>'
              f'<span class="er-b" aria-hidden="true"><i class="er-no" style="width:{100 * no / top:.1f}%"></i></span></li>'
            + "</ul>"
            + f'<p class="er-foot">{question_rule(r)}</p>'
            + (f'<p class="er-out">{head}</p>' if cap else f'<p class="er-out"><b>{head}.</b> {flip}</p>')
            + (f'<p class="er-foot">{E(r["note"])}</p>' if r.get("note") else "")
            + (f'<p class="er-foot">{county_disagreement(r)}</p>' if r.get("county_sum") else "")
            + (county_table(r) if r["kind"] != "cacr" else "")
            + ('<p class="er-foot">' + i18n.say(
                "en", "elect.q.how", "The Secretary of State&rsquo;s statewide summary does not hold this "
                "question, so the total is the ten county files&rsquo; totals added up.") + "</p>" if cap else "")
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
                    **({"s": chip_slug(e)} if chip_slug(e) else {})}
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


# THE FILTER AND THE ORDER OF A PANE'S RACES (the elections display design of
# 19 November 2026, asks 2 and 3): the margin buttons (margin_filter) show the
# races of one band, the Order sorts every race of the pane by its margin into
# one list (.er-flat) and By district puts each back in its county, and the
# House's town box narrows them by a town or ward. One script for all three,
# since each hides cards; a link carrying data-order (the overview's Smallest
# Margins) opens a pane in that order.
MARGIN_JS = """<script id="er-margin-js">
(function(){
  var each=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};
  each(".er-filt").forEach(function(f){
    var pane=document.getElementById(f.getAttribute("data-pane"));
    if(!pane)return;
    var cards=each(".er-race",pane),home=cards.map(function(c){return c.parentNode;});
    var flat=pane.querySelector(".er-flat"),heads=each(".er-county",pane),btns=each("button[data-band]",f);
    var sel=f.querySelector("select"),say=f.querySelector(".er-count"),box=pane.querySelector(".er-find");
    var find=box&&box.querySelector("input"),band="";
    f.hidden=false;if(box)box.hidden=false;
    var num=function(c,k){var v=c.getAttribute("data-"+k);return v===null||v===""?null:+v;};
    var by=function(up){return function(a,b){
      var x=num(a,"points"),y=num(b,"points");
      if(x===null||y===null)return (x===null)-(y===null)||cards.indexOf(a)-cards.indexOf(b);
      return (up?x-y:y-x)||(up?num(a,"gap")-num(b,"gap"):num(b,"gap")-num(a,"gap"))||cards.indexOf(a)-cards.indexOf(b);};};
    function apply(){
      var q=find?find.value.trim().toLowerCase():"",ord=sel?sel.value:"district",n=0;
      cards.forEach(function(c){
        var on=(!band||c.getAttribute("data-band")===band)&&(!q||(c.getAttribute("data-towns")||"").indexOf(q)>=0);
        c.hidden=!on;if(on)n++;});
      if(ord==="district"||!flat){
        cards.forEach(function(c,i){home[i].appendChild(c);});
        if(flat)flat.hidden=true;
        heads.forEach(function(h){var g=h.nextElementSibling;
          h.hidden=!cards.some(function(c){return c.parentNode===g&&!c.hidden;});if(g)g.hidden=h.hidden;});
      }else{
        cards.slice().sort(by(ord==="small")).forEach(function(c){flat.appendChild(c);});
        flat.hidden=false;
        heads.forEach(function(h){h.hidden=true;if(h.nextElementSibling)h.nextElementSibling.hidden=true;});
      }
      say.textContent=band||q?n+" of "+cards.length+" races"+(q?" with a town or ward matching \\u201c"+find.value.trim()+"\\u201d":""):"";
    }
    btns.forEach(function(b){b.addEventListener("click",function(){
      band=b.getAttribute("data-band");
      btns.forEach(function(x){x.setAttribute("aria-pressed",x===b?"true":"false");});apply();});});
    if(sel)sel.addEventListener("change",apply);
    if(find)find.addEventListener("input",apply);
    each("a[data-order]").forEach(function(a){if(a.getAttribute("data-pane")!==pane.id)return;
      a.addEventListener("click",function(){if(sel)sel.value=a.getAttribute("data-order");band="";
        btns.forEach(function(x){x.setAttribute("aria-pressed",x.getAttribute("data-band")===""?"true":"false");});apply();});});
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


def county_groups(keys, races, decided_races, results, tnotes, election, hand, inc=None):
    by = {}
    for k in sorted(keys, key=BME.race_order):
        by.setdefault(BME.KEY_RE.match(k).group(1), []).append(k)
    out = []
    for county, ks in by.items():
        out.append(f'<h3 class="er-county" id="er-{county.lower()}">{E(county)} County '
                   f'<span>{len(ks)} district{"s" if len(ks) != 1 else ""}</span></h3>'
                   '<div class="er-cards">'
                   + "".join(race_card(k, races[k], decided_races.get(k) or {}, results, tnotes,
                                       election, hand, h="h4", inc=(inc or {}).get(k, frozenset()))
                             for k in ks) + "</div>")
    return "".join(out)


def not_on_file_words(results):
    """What the Secretary of State's site no longer serves for this election,
    in words, or "": the counties with no House file, and the Senate."""
    gone = results.get("_not_on_file") or {}
    parts = [f"{c} County\u2019s State Representative results" for c in gone.get("counties") or []]
    if gone.get("senate"):
        parts.append("the State Senate results")
    return " and ".join(parts)


def page_body(election, results, decided_races, report, hand, site, ballots, settled=False, inc=None):
    """The page. `inc` is {race key: the incumbents' same_name}
    (build_member_elections.incumbents), each marked * on its card, with one
    line under the tab's cards saying what the mark is."""
    races = results["races"]
    inc = {k: v - held_names(hand, k) for k, v in (inc or {}).items()}
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
        + '<section class="ofpart"><h3 class="er-h">Smallest Margins</h3>'
          '<p class="src">The last seat&rsquo;s margin in points, the lead of the last winner over the '
          "first out, smallest first, with the gap in votes.</p>"
        + closest(races, decided_races, path, hand, election=election)
        + '<p class="src">' + " &middot; ".join(
            f'<a href="{path}#er-mf-{p}" data-order="small" data-pane="{p}">Every {w} race, smallest margin '
            "first</a>" for p, w, ks in (("senate", "State Senate", senate), ("house", "State House", house))
            if ks) + "</p></section>")
    notes = [n for n in results.get("_notes") or [] if not TOTALS_NOTE.match(n)]
    if notes:
        overview += ('<section class="ofpart"><h3 class="er-h">Notes on the Files</h3>'
                     '<p class="src">What the reader of the Secretary of State&rsquo;s files noticed in '
                     "them, in its own words. A printed total that leaves out a town is said on its "
                     "race&rsquo;s card instead.</p><ul class=\"er-notes\">"
                     + "".join(f"<li>{E(n)}</li>" for n in notes) + "</ul></section>")
    # The town box's count is the margin filter's line (MARGIN_JS), which says both.
    find = ('<div class="er-find" id="er-find" hidden><label for="er-q">Find a town or ward</label>'
            '<input id="er-q" type="search" autocomplete="off" placeholder="A town or ward"></div>')
    flat = '<div class="er-cards er-flat" hidden></div>'
    panels = [("overview", "Overview", overview)]
    if senate:
        panels.append(("senate", f'State Senate <span class="ofn">({len(senate)})</span>',
                       margin_filter("senate", senate, races, election, hand)
                       + '<div class="er-cards">' + "".join(
                           race_card(k, races[k], decided_races.get(k) or {}, results, tnotes,
                                     election, hand, inc=inc.get(k, frozenset()))
                           for k in sorted(senate, key=BME.race_order)) + "</div>" + flat
                       + (inc_legend("S") if any(inc.get(k) for k in senate) else "")))
    panels.append(("house", f'State House <span class="ofn">({len(house)})</span>',
                   margin_filter("house", house, races, election, hand) + find
                   + county_groups(house, races, decided_races, results, tnotes, election, hand, inc)
                   + flat + (inc_legend("H") if any(inc.get(k) for k in house) else "")))
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
            + tabs_html(panels) + BT.TABS_JS + MARGIN_JS + "</div>")


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
    pages = provisional(site)
    # The incumbents' marks are the member tab's rule (build_member_elections.incumbents),
    # imported here and not at the top: that module imports this one.
    import build_member_elections as BMEL
    meta_p = site / "meta.json"
    terms = (json.loads(meta_p.read_text(encoding="utf-8")).get("terms") or []) if meta_p.is_file() else []
    roster = BMEL.Roster(sitting, former, terms, history)
    for election, _p, results in items:
        settled = settled_in(items, election)
        races_me, report, hand = decided(results, sitting, former, districts, hand_path, today,
                                         settled, history)
        with_pages(races_me, pages.get(election))
        if not hand.get("recount_deadline") and not settled:
            warn.append(f"{election}: no recount_deadline in {Path(hand_path).as_posix()}, so every "
                        "race but a recounted one reads Result not final")
        ballots = question_cards(election, BALLOTS, Path(collected) / QUESTIONS.name)
        inc = {k: BMEL.incumbents(k, r, election, roster,
                                  {e["n"]: e for e in (races_me.get(k) or {}).get("elected") or []},
                                  (hand.get("matches") or {}).get(k) or {})
               for k, r in results["races"].items()}
        body = page_body(election, results, races_me, report, hand, site, ballots, settled, inc)
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
    gaps = BME.history_gaps(sponsors, BME.PAST_SPONSORS_DEFAULT, BME.CAREERS_DEFAULT)
    if gaps:
        n = sum(1 for e, races in made if year_of(e) <= BME.HISTORY_UNTIL
                for r in races.values() for w in r["elected"] if not w.get("id"))
        warn.append(BME.gap_line(gaps, n, "winner(s)").replace("WARNING ", "", 1))
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
