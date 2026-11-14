#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-14.32
"""
The record in numbers: a Learn page of statistics computed from the site's own data.

    import learn_numbers; html = learn_numbers.body(site=Path("site"), root=Path("."))

Asked for by the person on 13 September ("interesting data for the political science nerds")
and defined by them the same evening -- LAUNCH.md section 0a has the list and their decisions.
build_civics.py writes it to /learn/by-the-numbers.html.

It shipped as a draft: noindex, absent from the Learn hub and from the sitemap, so the person
could read it at its own address before anyone else was led to it. They read it and asked on
17 September for it to be public, and all three of those are now gone. It is still not one of
civics.TOPICS -- those are short explanations meant to be read in order, and this is a long
table of counts -- so the hub links it under a heading of its own after them.

Every figure is counted at build time, never typed, and each section says what it counts, over
what period, and how.

THE SECOND BATCH (7 October 2026, the person's front-end notes F16-F22). Each figure was
measured first, read-only, against sources this project did not write, and the counting
moved here only once the measurement held: bills filed and how they ended, per term; bills
filed and passed per member; the bills each committee received; the hearings with the most
sign-ins; each committee's passage rate; bills passed as introduced against amended, and how
many amendments a bill takes; attendance on roll-call days; and the constitutional
amendments sent to the voters, with the Secretary of State's count. The consent-calendar
table gained its two totals, and a Senate report the docket prints a second time counts once.
"Laws without the governor's signature" and the veto table's "Awaiting" column went, at the
person's word. Every figure has a function here that a check in preflight runs on a fixture
whose answer is known, which is what holds its definition still.

A MISSING INPUT IS SAID, NOT SKIPPED IN SILENCE. body() reads files a build makes or the kit
carries (narratives.json, testimony_db.json, data/member_votes.json, ballot_results.json). Where
one is not there its section is left out -- as build_site_v2 leaves out the voters' card when
ballot_results.json is missing -- and MISSING names it, which build_civics prints; preflight's
data checks fail on a built page that lacks a section. That is because the builders' fixture
site holds none of them and must still build. What does stop the build is a figure whose input
is here and cannot be finished: a hearing's bill retitled later with no printing on disk to
give the title it was heard under (strict, the default; preflight's fixtures pass False).
A constitutional amendment the voters decided whose row of ballot_results.json names no
source or no cite is left off its table and named in HELD, which build_civics prints too.
"""

import html
import json
import math
import re
import statistics
from collections import Counter, defaultdict
from datetime import date as _date
from pathlib import Path

import adopted_amendments as AA
import components
import ballot_source as BS
import build_date
import shell
import committee_names as CN
import later_referrals as LR
import narrative
import site_read as SR
from i18n import say

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def _load(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


# The first head of the tables whose first column is a committee's name,
# in each language it is built in (say() keys nums.c_cmte).
_COMMITTEE_HEADS = ("Committee", "Comité")


def _pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "&mdash;"


def _np(n, d):
    """A count and its share: "1,240 (57.7%)", on one line -- in a six-column
    table the browser otherwise breaks it before the bracket, row by row."""
    return f"{n:,}&nbsp;({_pct(n, d)})"


# A CELL THAT IS A NUMBER: a count, a count with its share, a share, a tally
# or a mean. Its column is set to the right in tabular figures, so a column
# of counts reads down by place value; a column with anything else in it --
# a term, a name, a date -- stays to the left.
_NUMCELL = re.compile(r"^[\d,.]+(?:&nbsp;\([\d.]+%\))?%?$|^&mdash;$|^\d+&ndash;\d+$")


# A table of more rows than this can be sorted by any column (the owner,
# 11 November 2026: "over about 8 rows"); a short one is read whole.
SORTABLE_OVER = 8
_NUM = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def raw_value(cell):
    """The number a cell stands for, as text: "1,240 (57.7%)" is 1240 and
    "52.1%" is 52.1, a dash or nothing is "" (a blank sorts last whichever
    way a column is sorted). What `data-v` carries, so the enhancer in
    components.js never parses a formatted figure."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(cell))).strip()
    m = _NUM.search(text)
    return m.group(0).replace(",", "") if m else ""


def _table(head, rows, cls="numtab", sortable=None, groups=None, numcols=()):
    """The table, its rows each a list of cells. A cell is the HTML it prints,
    or (html, value) where its sort value is not what it prints (a date's
    ISO form, a margin). With more than SORTABLE_OVER rows -- or sortable=True
    -- the table says it can be sorted (data-sortable) and every numeric cell
    carries its raw value (data-v); components.js adds the buttons, so a
    reader with no script sees the table as it is, in its default order.
    `groups` names each row's group (a chamber): a sort keeps the groups
    together unless the column's head is the first's."""
    # The first column is a term, a year, a bill or a chamber, and app.css
    # keeps it on one line ("1989-1990" broke at its dash); a committee's
    # name is the exception, and wraps. In another language the head's first
    # word is that language's, so the committee's tables are named by the
    # words they print in English (_COMMITTEE_HEADS).
    if head and head[0] in _COMMITTEE_HEADS:
        cls += " names"
    if len(head) >= 8:
        cls += " dense"       # app.css: no room for an idle sort chevron on every head
    if sortable is None:
        sortable = len(rows) > SORTABLE_OVER
    shown = [[c[0] if isinstance(c, tuple) else c for c in r] for r in rows]
    num = [k in numcols or (k > 0 and any(str(r[k]).strip() for r in shown if k < len(r))
           and all(_NUMCELL.match(str(r[k]).strip()) for r in shown
                   if k < len(r) and str(r[k]).strip()))
           for k in range(len(head))]

    def td(k, c):
        v = ""
        if isinstance(c, tuple):
            c, v = c
            v = f' data-v="{E(v)}"'
        elif sortable and k < len(num) and num[k]:
            v = f' data-v="{raw_value(re.sub(r"<svg.*?</svg>", "", str(c)))}"'
        return f'<td class="l-num"{v}>{c}</td>' if k < len(num) and num[k] else f"<td{v}>{c}</td>"

    def th(k, h):
        extra = " data-ungroup" if groups and k == 0 else ""
        return f'<th class="l-num"{extra}>{h}</th>' if num[k] else f"<th{extra}>{h}</th>"
    flags = (" data-sortable" if sortable else "") + (" data-group" if sortable and groups else "")
    return (f'<div class="l-tablewrap l-numwrap"><table class="l-table l-numtab {cls}"{flags}><thead><tr>'
            + "".join(th(k, h) for k, h in enumerate(head)) + "</tr></thead><tbody>"
            + "".join((f'<tr data-g="{E(groups[i])}">' if sortable and groups else "<tr>")
                      + "".join(td(k, c) for k, c in enumerate(r)) + "</tr>"
                      for i, r in enumerate(rows))
            + "</tbody></table></div>")


# The status chip's class for a kind of ending, from the words file the
# chips are drawn from (src/pages/words/chips.json).
CHIP = components.WORDBOOK["chips"]["kind"]


def wide(table):
    """A table of many columns takes the page's whole width under its
    section's heading rather than the prose's measure: the sign-ins (a title
    and a hearing beside four counts) and the amendments (seven columns, the
    source among them) squeezed into the measure and broke every cell. The
    markers are civics.wide's, which build_civics reads."""
    return f"<!--wide-->{table}<!--/wide-->"


def ends_chart(oc, terms, lang="en"):
    """HOW EACH TERM'S BILLS ENDED, as shares of the bills filed: a 100%
    stacked bar a term (Became Law, Interim Study, Died, Other), over the
    table of the same counts. Replaces the single bar of Became Law's share
    (11 November 2026): the job is the split, in four classes, over many
    terms. The Became Law share is at the end of each bar."""
    data = [(t, oc[t]) for t in terms if oc.get(t) and oc[t]["filed"]]
    if not data:
        return ""
    pct = [(t, 100 * c["Became Law"] / c["filed"]) for t, c in data]
    hi, lo = max(pct, key=lambda r: r[1]), min(pct, key=lambda r: r[1])
    said = say(lang, "nums.ch_ends_said",
               "Stacked bar chart: how the bills of each term ended, as shares of the bills filed. The "
               "share that became law ran from {a}% in {ta} to {b}% in {tb}; the highest was {c}% in "
               "{tc}, the lowest {d}% in {td}. The rest were sent to interim study, died or ended some "
               "other way. The figures are in the table below.",
               a=f"{pct[0][1]:.1f}", ta=components.term_words(pct[0][0]),
               b=f"{pct[-1][1]:.1f}", tb=components.term_words(pct[-1][0]),
               c=f"{hi[1]:.1f}", tc=components.term_words(hi[0]),
               d=f"{lo[1]:.1f}", td=components.term_words(lo[0]))
    rows = [(_t(t), [c["Became Law"], c["Interim Study"], c["Died"], c["other"]]) for t, c in data]
    parts = [("law", say(lang, "nums.c_law", "Became Law")), ("study", say(lang, "nums.c_study", "Interim Study")),
             ("done", say(lang, "nums.c_died", "Died")), ("rest", say(lang, "nums.c_other", "Other"))]
    return stack100_chart(rows, parts, say(lang, "nums.ch_ends_h", "How Each Term&rsquo;s Bills Ended"),
                          said, lang, 0,
                          say(lang, "nums.ch_ends_p", "The figure at the end of each bar is the share that became "
                              "law; the table below has every count."))


def _t(term):
    return E(term).replace("-", "&ndash;")


YEAR = {}   # (term, bill) -> filing year, from the index; filled by body()


def _bill_link(term, bid, year=None):
    y = year or YEAR.get((term, bid)) or term.split("-")[0]
    shown = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid)
    return f'<a href="bill/{E(y)}/{E(bid.lower())}">{E(shown)}</a>'


def _day(iso, lang="en"):
    """"2025-02-10" -> "Feb 10, 2025", held together by no-break spaces in a
    table's cell: shell.date_words. In Spanish "10 feb. 2025"."""
    try:
        d = _date.fromisoformat(iso)
    except (TypeError, ValueError):
        return E(iso)
    return E(shell.date_words(d, "medium", lang)).replace(" ", "&nbsp;")


def _whose(row, lang="en"):
    """Whose count a row of ballot_results.json is (ballot_source.whose), for
    a sentence in `lang`: "the Secretary of State's" in English, "de la
    Secretaría de Estado" in Spanish, whose sentence takes it after "count"."""
    if lang == "en":
        return BS.whose(row)
    who = BS.named(row)
    if who == "the Secretary of State":
        return say(lang, "nums.whose_sos", "the Secretary of State's")
    return say(lang, "nums.whose_other", "{name}'s", name=who)


def _cat(text):
    """PASS, KILL or STUDY from a motion or a report's recommendation."""
    t = (text or "").lower()
    if "interim study" in t:
        return "STUDY"
    if "ought to pass" in t:
        return "PASS"
    if "inexpedient to legislate" in t or "indefinitely postpone" in t:
        return "KILL"
    return None


# What a bill is in the figures that count bills: a House or Senate bill,
# special sessions' included. Resolutions and constitutional amendments are
# not bills. A joint resolution does go to the governor -- HJR 1 of 2007 was
# signed -- so the veto table, which counts what reached the governor, says
# "bills and joint resolutions" and can run a few above the bills here.
BILL = re.compile(r"^(?:SS)?[HS]B\d+$")
LAW = frozenset({"Signed into law", "Became law unsigned", "Veto overridden, became law"})
# A veto whose override vote is still to come, in bill_disposition's words
# (build_site_v2.VETO_PENDING); "Vetoed, override failed" is not one.
VETO_PENDING = frozenset({"Vetoed", "Vetoed, awaiting an override vote",
                          "Vetoed, override vote pending"})
# Passed both chambers in the same text: it reached the governor.
REACHED = LAW | VETO_PENDING | {"Vetoed, override failed"}
SEATS = {"H": 400, "S": 24}
NAME = {"H": "House", "S": "Senate"}


# A QUESTION A MAJORITY DOES NOT DECIDE. A veto override needs two thirds, a
# rules suspension two thirds, and passing a constitutional amendment three
# fifths of the members in office, so a margin of one on any of them says
# nothing about how close it was: HB 1072's override at 160-159 was 53 short
# of what it needed, and it led the table of closest votes. Decided by the
# question rather than by threshold_needed, which has been set on CACR motions
# that need only a majority -- a kill motion and a floor amendment among them
# -- so a close vote of that kind would have been dropped for no reason.
_OVERRIDE_Q = re.compile(r"veto|become law", re.I)
_SUSPEND_Q = re.compile(r"\bsusp", re.I)
_CACR_PASSAGE_Q = re.compile(r"^\s*(ought to pass|otp|concur|adopt conference|third reading|"
                             r"final passage|pass)", re.I)


def needs_more_than_majority(bid, r):
    """True for a roll call on a question that needs more than a majority."""
    q = " ".join(str(r.get(k) or "") for k in ("question", "question_raw"))
    if _OVERRIDE_Q.search(q) or _SUSPEND_Q.search(q):
        return True
    return (bid or "").upper().startswith("CACR") and bool(
        _CACR_PASSAGE_Q.search(r.get("question") or "")
        or _CACR_PASSAGE_Q.search(r.get("question_raw") or ""))


def overturned(narr):
    """(per chamber {ch: (decided, against, passage<->kill)}, [(bid, ch, rec, floor)])."""
    stats, cases = {}, []
    for ch in ("H", "S"):
        decided = against = swap = 0
        for bid, rec in narr.items():
            ev = rec.get("events") or []
            reports = [e for e in ev if e.get("body") == ch and e.get("type") == "report"
                       and not (e.get("raw") or "").lower().startswith("minority")]
            if not reports:
                continue
            first = reports[0].get("date", "")
            dec = next(((e, _cat(e.get("action"))) for e in ev
                        if e.get("body") == ch and e.get("type") == "floor" and e.get("motion") == "MA"
                        and _cat(e.get("action")) and e.get("date", "") >= first), None)
            if not dec:
                continue
            e, fc = dec
            before = [r for r in reports if r.get("date", "") <= e.get("date", "")]
            rc = _cat(re.sub(r"^.*?report:\s*", "", (before or reports)[-1].get("raw") or "", flags=re.I))
            if not rc:
                continue
            decided += 1
            if rc != fc:
                against += 1
                swap += {rc, fc} == {"PASS", "KILL"}
                cases.append((bid, ch, rc, fc))
        stats[ch] = (decided, against, swap)
    return stats, cases


# ---------------------------------------------------------------------------
# The figures. Each takes what it counts and returns the counts; body() draws
# them. preflight runs every one on a fixture whose answer is known.
# ---------------------------------------------------------------------------

def outcomes(idx):
    """{term: Counter(filed, Became Law, Died, Interim Study, other)}.

    Every House and Senate bill the term numbered, by the chip its card shows
    (build_site_v2.chip_word): Became Law, Died -- killed, tabled and left
    there, vetoed with the veto standing, or lost between the chambers --
    Interim Study, and everything else as other: withdrawn, never introduced,
    or, while a session still sits, not yet decided."""
    out = defaultdict(Counter)
    for r in idx:
        if not BILL.match(r.get("id") or ""):
            continue
        c = out[r.get("term")]
        c["filed"] += 1
        chip = r.get("chip")
        c[chip if chip in ("Became Law", "Died", "Interim Study") else "other"] += 1
    return out


def per_member(idx):
    """{term: {"H": [filed, became law], "S": [...]}}: House and Senate bills
    by the chamber their prime sponsor sat in, as the index's sponsor label
    names it ("Rep." or "Sen."). A bill a committee sponsored counts to
    nobody. Divided by SEATS on the page."""
    out = defaultdict(lambda: {"H": [0, 0], "S": [0, 0]})
    for r in idx:
        if not BILL.match(r.get("id") or ""):
            continue
        lab = (r.get("sponsor_label") or "").strip()
        ch = "H" if lab.startswith("Rep") else "S" if lab.startswith("Sen") else None
        if ch:
            c = out[r.get("term")][ch]
            c[0] += 1
            c[1] += r.get("status") in LAW
    return out


def _first_referrals(row):
    """{"H": committee, "S": committee} as the bill's page names them."""
    out = {}
    for c in row.get("committees") or []:
        word, _, nm = c.partition(" ")
        ch = {"House": "H", "Senate": "S"}.get(word)
        if ch and nm and nm.lower() != "no committee assignment":
            out[ch] = nm
    return out


def referrals(idx, narr, term):
    """{"House X": [first referrals, sent on to it]} for the term.

    First referral: the committee a chamber first sent the bill to, as the
    bill's page names it (one per bill per chamber). Sent on: the bill came to
    the committee after another committee of the same chamber had it -- a
    second referral, most often to Finance or Ways and Means for a bill with a
    cost -- read from the docket by later_referrals. Every numbered measure of
    the term counts, resolutions and constitutional amendments included."""
    out = defaultdict(lambda: [0, 0])
    for r in idx:
        if r.get("term") != term:
            continue
        first = _first_referrals(r)
        if not first:
            continue
        refs = LR.chamber_referrals((narr.get(r.get("id")) or {}).get("events"), term)
        for ch, fc in first.items():
            out[f"{NAME[ch]} {fc}"][0] += 1
            seq = refs[ch]
            pos = seq.index(fc) if fc in seq else -1
            for c in seq:
                if c != fc and (pos < 0 or seq.index(c) > pos):
                    out[f"{NAME[ch]} {c}"][1] += 1
    return out


def committee_rates(idx, narr, term):
    """({"House X": [reported on, passed both chambers, became law]},
         {"H": [bills, passed, law], "S": [...]}).

    Of the House and Senate bills a committee made a majority report on in
    the term, whatever it recommended, how many passed both chambers and how
    many became law. A bill two committees of a chamber reported on counts in
    both rows; the chamber's totals count it once, under the first."""
    rows, tot = defaultdict(lambda: [0, 0, 0]), {"H": [0, 0, 0], "S": [0, 0, 0]}
    for r in idx:
        if r.get("term") != term or not BILL.match(r.get("id") or ""):
            continue
        seen = AA.reporting_committees((narr.get(r["id"]) or {}).get("events"), term, CN.official)
        passed, law = r.get("status") in REACHED, r.get("status") in LAW
        for ch in ("H", "S"):
            for i, name in enumerate(seen[ch]):
                c = rows[f"{NAME[ch]} {name}"]
                c[0] += 1
                c[1] += passed
                c[2] += law
                if i == 0:
                    tot[ch][0] += 1
                    tot[ch][1] += passed
                    tot[ch][2] += law
    return rows, tot


MIN_REPORTS = 10   # a committee's rate and consent share are stated from ten reports


def committee_record(idx, narr_all, term):
    """({committee: {"first", "sent", "reported", "passed", "law", "reports",
    "kept"}}, committee_rates' chamber totals, consent's per-chamber counts)
    for the term: the union of what referrals, committee_rates and consent
    each name, so that the one table loses no committee any of the three had
    (preflight holds it to that). first and sent count every numbered
    measure; reported, passed and law House and Senate bills; reports and
    kept every majority report, a reprint counted once."""
    narr = narr_all.get(term, {})
    rf = referrals(idx, narr, term)
    cr, ctot = committee_rates(idx, narr, term)
    rows_by = {r.get("id"): r for r in idx if r.get("term") == term}
    by_c, per_ch = consent(narr, rows_by, term)
    rec = {}
    for name in sorted(set(rf) | set(cr) | set(by_c)):
        f, snt = rf.get(name, (0, 0))
        n, p, law = cr.get(name, (0, 0, 0))
        rn, rk = by_c.get(name, (0, 0))
        rec[name] = {"first": f, "sent": snt, "reported": n, "passed": p, "law": law,
                     "reports": rn, "kept": rk}
    return rec, ctot, per_ch


def committee_chart(rec, term, lang="en"):
    """Each committee of ten reports or more as a point, over its term's
    table: how many bills it reported on against the share that passed both
    chambers. House and Senate are two shapes in neutral tones."""
    pts = [(n, "H" if n.startswith("House") else "S", v["reported"], 100 * v["passed"] / v["reported"])
           for n, v in rec.items() if v["reported"] >= MIN_REPORTS]
    if not pts:
        return ""
    ranked = sorted(pts, key=lambda p: (p[3], p[0]))
    said = say(lang, "nums.ch_cmte_said",
               "Scatter chart of the {n} committees of {term} with ten reports or more: the bills each "
               "reported on, from {lo} to {hi}, against the share that passed both chambers, from "
               "{plo}% for {nlo} to {phi}% for {nhi}. The figures are in the table below.",
               n=len(pts), term=components.term_words(term), lo=min(p[2] for p in pts),
               hi=max(p[2] for p in pts), plo=f"{ranked[0][3]:.1f}", phi=f"{ranked[-1][3]:.1f}",
               nlo=re.sub(r"<[^>]+>", "", ranked[0][0]), nhi=re.sub(r"<[^>]+>", "", ranked[-1][0]))
    return scatter_chart(pts, say(lang, "nums.ch_cmte_h", "Bills Reported On, and the Share That Passed"),
                         said, say(lang, "nums.ch_cmte_x", "bills reported on"),
                         say(lang, "nums.c_both", "Passed both chambers"), lang,
                         say(lang, "nums.ch_cmte_p", "The three highest and three lowest rates are named; "
                             "compare within a chamber."))


def committee_rows(rec, lang="en"):
    """(rows, groups) of the merged committees table: House first, each
    chamber by passage rate, highest first (a committee under ten reports
    last), then by name. A rate or a consent share under ten bills or
    reports is a dash."""
    def key(item):
        name, v = item
        rate = v["passed"] / v["reported"] if v["reported"] >= MIN_REPORTS else -1
        return (not name.startswith("House"), -rate, name)
    rows, groups = [], []
    for name, v in sorted(rec.items(), key=key):
        rows.append([_en(E(name), lang), f"{v['first']:,}", f"{v['sent']:,}", f"{v['reported']:,}",
                     f"{v['passed']:,}", f"{v['law']:,}",
                     _pct(v["passed"], v["reported"]) if v["reported"] >= MIN_REPORTS else "&mdash;",
                     _pct(v["kept"], v["reports"]) if v["reports"] >= MIN_REPORTS else "&mdash;"])
        groups.append("H" if name.startswith("House") else "S")
    return rows, groups


def passage(idx, narr_all):
    """{term: {"passed", "amended", "conference", "dist": Counter(amendments)}}.

    Every House and Senate bill that passed both chambers (it reached the
    governor). Amended: either chamber adopted an amendment before the
    governor acted, or the bill went to a committee of conference; the
    Enrolled Bills Committee's technical correction is not an amendment. The
    distribution counts the amendments the two chambers adopted, 6 standing
    for six or more (adopted_amendments says how)."""
    out = defaultdict(lambda: {"passed": 0, "amended": 0, "conference": 0, "dist": Counter()})
    for r in idx:
        if not BILL.match(r.get("id") or "") or r.get("status") not in REACHED:
            continue
        ev = ((narr_all.get(r.get("term")) or {}).get(r["id"]) or {}).get("events")
        per, conf, _eba = AA.chamber_amendments(ev)
        o = out[r.get("term")]
        o["passed"] += 1
        o["amended"] += per["H"]["amended"] or per["S"]["amended"] or conf
        o["conference"] += conf
        o["dist"][min(per["H"]["n"] + per["S"]["n"], 6)] += 1
    return out


def consent(narr, rows_by, term=""):
    """({committee: [recommendations, on consent and kept there]},
         {"H": Counter(kept, regular, removed), "S": ...}).

    Every majority committee report of the term, credited to the committee
    that made it, as adopted_amendments reads it for the passage rates --
    the bill's committee in that chamber only where the report names none. A
    report the docket prints a second time -- the
    Senate reprints one when a bill taken off its consent calendar comes back
    as a special order -- with the same committee, recommendation, amendment
    and tally as the report before it counts once. On consent and kept: the
    report carries CC and the chamber did not take the bill off; removed: it
    carried CC and the chamber did; regular: it never went on consent."""
    by_c = defaultdict(lambda: [0, 0])
    per = {"H": Counter(), "S": Counter()}
    for bid, rec in narr.items():
        row = rows_by.get(bid) or {}
        ev = rec.get("events") or []
        # A REMOVAL IS A REMOVAL HOWEVER THE ROW IS TYPED. This read the rows
        # typed consent_off and no others, and counted as kept on the calendar
        # 59 reports of 2025-2026 whose chamber took them off in a row typed
        # "other" -- every one of the House's "Removed from Consent (Reps.
        # ...)" of the term, HB 691 of 2025 among them, decided on a roll
        # call of 190-156. The histories' reader is the one list of wordings.
        off = {e.get("body") for e in ev if not e.get("cancelled")
               and (e.get("type") == "consent_off"
                    or narrative.removed_from_consent(e.get("raw")))}
        # A SECOND COMMITTEE'S REPORT IS THAT COMMITTEE'S. This credited every
        # report to the committee the bill's page names, so 247 reports of
        # 2025-2026 that Finance, Ways and Means and the rest made after a
        # second referral counted to the bill's first committee: House Finance
        # showed 20 reports here while the passage rates below, on the same
        # page, showed it reporting on 107 bills. The totals did not move.
        made_by = {id(e): nm for e, _ch, nm in AA.credited_reports(ev, term, CN.official)}
        prev = {}
        for e in ev:
            if e.get("type") != "report" or (e.get("raw") or "").lower().startswith("minority"):
                continue
            ch = e.get("body")
            key = (e.get("committee"), e.get("recommendation"), e.get("amendment"),
                   e.get("yeas"), e.get("nays"))
            reprint = prev.get(ch) == key
            prev[ch] = key
            word = "House " if ch == "H" else "Senate "
            cm = next((c for c in row.get("committees") or [] if c.startswith(word)), "")
            if cm and made_by.get(id(e)):
                cm = word + made_by[id(e)]
            if not cm or reprint or ch not in per:
                continue
            by_c[cm][0] += 1
            cc = bool(re.search(r"\bCC\b", e.get("raw") or ""))
            if cc and ch not in off:
                by_c[cm][1] += 1
                per[ch]["kept"] += 1
            else:
                per[ch]["removed" if cc else "regular"] += 1
    return by_c, per


def attendance(votes):
    """{(term, "H"|"S"): (roll-call days, mean share present)}, 1999 on.

    For each day a chamber took at least one roll call, the share of the
    members on that day's ballots who were present for at least one of them --
    voting, presiding or declaring a conflict -- averaged over the days. The
    ballots are the member pages' (build_site_v2.member_attendance's rules):
    the day a misdated roll call was really taken, the presiding officer the
    record leaves unnamed, and a run of empty ballots ending a member's term
    as a seat nobody held."""
    import build_site_v2 as B
    import proceedings as P
    by_member = defaultdict(list)
    for v in votes:
        by_member[v.get("member_id")].append(v)
    ctx = B.attendance_context(by_member)
    dates, chair = ctx["dates"], ctx["chair"]
    seq = defaultdict(list)
    for v in votes:
        t = P.vote_term(str(v.get("year") or ""), v.get("date"))
        if not t:
            continue
        key = B._roll_call_key(v)
        kind = B.ATTENDANCE_KIND.get(v.get("vote"), "no_vote")
        if v.get("conflict"):
            kind = "conflict"
        elif kind in ("excused", "not_excused") and chair.get(key) == v.get("member_id"):
            kind = "presided"
        num = str(v.get("vote_number") or "")
        seq[(v.get("member_id"), t, v.get("body"))].append(
            ((str(v.get("year")), int(num) if num.isdigit() else 0), key, kind))
    days = defaultdict(lambda: defaultdict(lambda: [set(), set()]))
    for (mid, t, body), run in seq.items():
        run.sort(key=lambda b: b[0])
        while run and run[-1][2] == "no_vote":
            run.pop()
        for _o, key, kind in run:
            day = dates.get(key)
            if not day or day == (0, 0, 0):
                continue
            d = days[(t, body)][day]
            d[0].add(mid)
            if kind in ("voted", "presided", "conflict"):
                d[1].add(mid)
    out = {}
    for k, ds in days.items():
        shares = [len(p) / len(m) for m, p in ds.values() if m]
        if shares:
            out[k] = (len(shares), statistics.fmean(shares))
    return out


# -- the hearings with the most sign-ins ------------------------------------
_D = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def _amendment_hearing(ev, day):
    """"a non-germane amendment" or "an amendment" where the docket's line for
    `day` is a public hearing on one rather than on the bill, else ""."""
    if any(e.get("type") == "hearing" and e.get("body") == "H" and not e.get("cancelled")
           and e.get("date") == day for e in ev):
        return ""
    for e in ev:
        raw = e.get("raw") or ""
        if any(f"{m.group(3)}-{m.group(1)}-{m.group(2)}" == day for m in _D.finditer(raw)):
            m = re.search(r"public hearing on (non-germane )?amendment", raw, re.I)
            if m:
                return "a non-germane amendment" if m.group(1) else "an amendment"
            return ""
    return ""


def _house_committee_after(ev, row, day):
    """The House committee that reported on the bill first on or after `day`,
    else the one its page names."""
    for e in ev:
        if (e.get("type") == "report" and e.get("body") == "H" and not e.get("cancelled")
                and not (e.get("raw") or "").lower().startswith("minority")
                and (e.get("date") or "") >= day and e.get("committee")):
            return e["committee"]
    return next((c[6:] for c in row.get("committees") or [] if c.startswith("House ")), "")


def version_title(text, bid):
    """The title a printing of a bill carries: what follows AN ACT or A
    RESOLUTION, or a CACR's RELATING TO and PROVIDING THAT, up to SPONSORS."""
    t = re.sub(r"\s+", " ", text or "")
    if bid.startswith("CACR"):
        m = re.search(r"RELATING TO:\s*(.+?)\s*PROVIDING THAT:\s*(.+?)\s*SPONSORS:", t)
        if m:
            return f"relating to {m.group(1).strip()} Providing that {m.group(2).strip()}"
    m = re.search(r"\b(?:AN ACT|RESOLUTION)\s+(.+?)\s*SPONSORS:", t)
    return m.group(1).strip() if m else ""


def _site_version_title(site, year, bid, day):
    """The title of the latest printing dated on or before `day`, from the
    bill's versions on the site (build_bill_versions), or None where the site
    holds none for it -- a bill printed once, which kept its title."""
    p = Path(site) / "versions" / str(year) / f"{bid}.json"
    if not p.exists():
        return None
    # THE FIRST PRINTING WHERE NONE IS DATED BEFORE THE HEARING. A version's
    # date is when the database stored it, which can trail the printing: HB
    # 524 of 2025 was heard on 12 February and its Introduced row is dated 5
    # March. The first printing is the introduced text, which is what a first
    # hearing hears.
    vs = (_load(p, {}) or {}).get("versions") or []
    best = 0 if vs else None
    for i, v in enumerate(vs):
        m = re.match(r"(\d{2})/(\d{2})/(\d{4})", v.get("date") or "")
        if m and f"{m.group(3)}-{m.group(1)}-{m.group(2)}" <= day:
            best = i
    if best is None:
        return None
    f = Path(site) / "versions" / str(year) / f"{bid}.{best}.txt"
    return version_title(f.read_text(encoding="utf-8"), bid) if f.exists() else None


_INTRODUCED, _SENATE_AMENDED = {3, 4}, {5}


def _past_titles(root, wanted):
    """{(year, bid): {"intro": title, "senate": title}} for the printings the
    General Court's dump of past bills' text holds (db/past/
    PastLegislationText.jsonl), read once for the bills in `wanted`."""
    p = Path(root) / "db" / "past" / "PastLegislationText.jsonl"
    out = defaultdict(dict)
    if not p.exists() or not wanted:
        return out
    marks = {f'"BillNbr":"{b}"'.encode(): b for _y, b in wanted}
    with p.open("rb") as fh:
        for line in fh:
            hit = next((b for m, b in marks.items() if m in line), None)
            if not hit:
                continue
            r = json.loads(line)
            key = (str(r.get("sessionyear")), hit)
            if key not in wanted:
                continue
            v = int(r.get("VersionID") or 0)
            kind = "intro" if v in _INTRODUCED else "senate" if v in _SENATE_AMENDED else None
            if kind and kind not in out[key]:
                t = version_title(r.get("text") or "", hit)
                if t:
                    out[key][kind] = t
    return out


_NEW_TITLE = re.compile(r"^\s*\((?:[\w ]*)New Title\s*\)", re.I)


def signins(tdb, narr_all, idx, site=Path("site"), root=Path("."), top=20, strict=True):
    """{term: [hearing]}: each term's `top` hearings by sign-ins, most first.

    A hearing is one bill on one House committee date in testimony_db.json, and
    its count is every support, oppose and neutral sign-in the House's online
    form recorded for it; a bill heard twice can appear twice. Each carries the
    title the bill had when it was heard (the printing dated on or before the
    hearing, else the one it was introduced with), the committee that heard it,
    and whether the sitting was a hearing on an amendment rather than the bill."""
    rows = {(r.get("term"), r.get("id")): r for r in idx}
    out, past = {}, set()
    for term, bills in tdb.items():
        if not re.fullmatch(r"\d{4}-\d{4}", str(term)):
            continue
        hs = [(bid, h) for bid, rec in (bills or {}).items() for h in (rec or {}).get("hearings") or []]
        hs.sort(key=lambda x: (-x[1]["total"], x[0], x[1]["date"]))
        sel = []
        for bid, h in hs[:top]:
            row = rows.get((term, bid)) or {}
            ev = ((narr_all.get(term) or {}).get(bid) or {}).get("events") or []
            year = str(row.get("year") or term[:4])
            title = _site_version_title(site, year, bid, h["date"])
            sel.append({"bill": bid, "year": year, "date": h["date"], "total": h["total"],
                        "support": h["support"], "oppose": h["oppose"], "neutral": h["neutral"],
                        "committee": _house_committee_after(ev, row, h["date"]),
                        "on": _amendment_hearing(ev, h["date"]),
                        "title": title, "title_now": row.get("title") or "",
                        "origin": next((e.get("body") for e in ev if e.get("type") == "introduced"),
                                       "S" if bid.startswith("S") else "H")})
            if title is None:
                past.add((term, bid))
        out[term] = sel
    # A bill with no printings on the site kept its title, unless the record
    # marks a new one -- an older term, whose printings the site does not
    # hold. Its title as heard comes from the General Court's own text.
    if past:
        bills_json = _load(Path(root) / "data" / "bills.json", {})
        retitled = {(t, b) for t, b in past
                    if _NEW_TITLE.match(((bills_json.get(t) or {}).get(b) or {}).get("title") or "")}
        want = {(x["year"], b) for t, b in retitled for x in out[t] if x["bill"] == b}
        want |= {(str(int(y) + d), b) for y, b in list(want) for d in (-1, 1)}
        found = _past_titles(root, want)
        for t, sel in out.items():
            for x in sel:
                if x["title"] is not None:
                    continue
                if (t, x["bill"]) not in retitled:
                    x["title"] = x["title_now"]
                    continue
                got = next((found[(y, x["bill"])] for y in (x["year"], t[:4], t[5:])
                            if found.get((y, x["bill"]))), {})
                x["title"] = (got.get("senate") if x["origin"] == "S" else None) or got.get("intro")
                if not x["title"]:
                    if strict:
                        raise SystemExit(f"learn_numbers.py: {x['bill']} of {t} was retitled after "
                                         "its hearing and no printing on this disk gives the title it "
                                         "was heard under (db/past/PastLegislationText.jsonl)")
                    x["title"] = x["title_now"]
    return out


def ballots(rows):
    """(shown, held, to come) out of ballot_results.json's rows.

    Shown: a constitutional amendment the voters decided whose row names
    where its count was read (`source`) and where it is printed (`cite`).
    Held: decided, and the row names no source or no cite -- left off the
    page, and named in the build's log (HELD), never in a sentence to the
    reader. To come: an election not yet held.

    Until 7 October 2026 a row was shown only where the Secretary of State's
    count (then the row's `sos`) equalled the row's own, which was
    Ballotpedia's, and two were held: CACR 7 of 1992 and CACR 41 of 2006,
    where Ballotpedia's No was 18 and 2 votes off. That day the person made
    the Secretary of State every decided row's source, corrected those two,
    and kept Ballotpedia's figures on each row as the cross-check, so the
    page shows all seventeen."""
    shown, held, to_come = [], [], []
    for r in rows or []:
        if r.get("yes") is None and r.get("no") is None:
            to_come.append(r)
            continue
        (shown if r.get("source") and r.get("cite") else held).append(r)
    key = lambda r: (r.get("election") or "", r.get("bill") or "")
    return sorted(shown, key=key), sorted(held, key=key), sorted(to_come, key=key)


def ratified(yes, no):
    """Two thirds of the votes cast on it (Part II, Article 100), in whole
    numbers so that exactly two thirds is two thirds."""
    return yes + no > 0 and 3 * yes >= 2 * (yes + no)


def vetoes(rows):
    """(reached the governor, vetoed, stood, overridden, still to be voted on)
    for one term's index rows. A veto stood when its override failed or no
    override vote came before the session ended; one still to be voted on
    is the chip's Vetoed, which only a session with days left can show."""
    st = Counter(r.get("status") for r in rows)
    pending = sum(st[s] for s in VETO_PENDING)
    live = sum(1 for r in rows if r.get("status") in VETO_PENDING and r.get("chip") == "Vetoed")
    over = st["Veto overridden, became law"]
    stood = st["Vetoed, override failed"] + pending - live
    vetoed = stood + over + live
    reached = st["Signed into law"] + st["Became law unsigned"] + vetoed
    return reached, vetoed, stood, over, live


# ---------------------------------------------------------------------------
# THE OTHER CHARTS (the owner, 11 November 2026, after the flow diagram): each
# a static inline SVG made at build time with no library, over the table it
# is drawn from, which is its accessible twin -- the figure itself is one
# image to a screen reader, which is told the range in words. One axis each,
# never two; direct labels only on the figures a reader looks for; and the
# two chambers are neutral tones and two shapes (a filled circle, an open
# diamond), never the parties' colours, which mean a party everywhere else.
# ---------------------------------------------------------------------------

def _chart(title, said, svg, legend=(), note=""):
    """A chart's figure: title, the SVG (it scales with its box at every
    width; app.css says what it does on a phone), its key, and a line saying
    the table beneath it holds the figures. legend: [(swatch class, words)]."""
    key = "".join(f'<li><span class="l-sw {c}" aria-hidden="true"></span><span>{w}</span></li>'
                  for c, w in legend)
    return (f'<figure class="l-fig l-ch"><figcaption>{title}</figcaption>'
            + (f'<ul class="l-barkey">{key}</ul>' if key else "")
            + f'<div class="l-skwrap">{svg}</div>' + (f"<p>{note}</p>" if note else "") + "</figure>")


# THE CHARTS' TYPE, in the SVG's own units (app.css: .sk.ch is this size). A
# label is measured here, from this size and a width a letter, so a chart's
# margin is made from its longest label rather than a number picked to suit
# one ("1989-1990" lost its first digit in a margin picked for "2019").
# Generous on purpose: a guess too wide leaves a margin, one too narrow cuts
# a number. preflight's check reads the same function.
CH_PX = 15


def text_w(s, px=CH_PX, bold=False):
    """The width of `s` set in the charts' sans at `px`, an upper bound."""
    s = html.unescape(re.sub(r"<[^>]+>", "", str(s)))
    em = sum(0.64 if c.isdigit() else 0.74 if c.isupper() else 0.28 if c == " " else
             0.6 if c in "%,.:" else 0.9 if c in "mwMW" else 0.58 for c in s)
    return em * px * (1.08 if bold else 1.0)


def _svg(w, h, said, body):
    return (f'<svg class="sk ch" viewBox="0 0 {w} {h}" role="img" aria-label="{E(said)}" '
            f'xmlns="http://www.w3.org/2000/svg"><g>{body}</g></svg>')


def stack100_chart(rows, parts, title, said, lang="en", label_part=0, note=""):
    """100% stacked horizontal bars, one per row: rows [(label, [n per part])],
    parts [(class, words)]. The share of the part `label_part` is printed at
    the end of each bar (the one figure a reader compares down the rows); a
    bar's title holds all of them. A 2px surface gap between segments."""
    bw, rh, bh = 360, 20, 12
    lw = math.ceil(max((text_w(label) for label, _ns in rows), default=0)) + 12
    out, y = [], 4
    for label, ns in rows:
        tot = sum(ns)
        out.append(f'<text x="{lw - 8}" y="{y + 10}" text-anchor="end">{label}</text>')
        x = lw
        tip = "; ".join(f"{w} {n:,}" for (_c, w), n in zip(parts, ns))
        out.append(f"<g><title>{E(label)}: {E(tip)}</title>")
        for (cls, _w), n in zip(parts, ns):
            if tot and n:
                seg = bw * n / tot
                out.append(f'<rect class="sk-{cls}" x="{x:.1f}" y="{y}" width="{max(seg - 1.5, 1):.1f}" height="{bh}"/>')
                x += seg
        out.append("</g>")
        if tot:
            out.append(f'<text class="sk-v" x="{lw + bw + 8}" y="{y + 10}">{100 * ns[label_part] / tot:.1f}%</text>')
        y += rh
    svg = _svg(lw + bw + 8 + math.ceil(text_w("100.0%", bold=True)) + 4, y + 4, said, "".join(out))
    return _chart(title, said, svg, [(f"c-{c}", w) for c, w in parts], note)


def chamber_marker(ch, x, y, r=4.5):
    """The chamber's mark: House a filled circle, Senate an open diamond, in
    neutral tones. Never a party colour."""
    if ch == "H":
        return f'<circle class="ch-h" cx="{x:.1f}" cy="{y:.1f}" r="{r}"/>'
    return (f'<path class="ch-s" d="M{x:.1f},{y - r - 1:.1f}L{x + r + 1:.1f},{y:.1f}L{x:.1f},{y + r + 1:.1f}'
            f'L{x - r - 1:.1f},{y:.1f}Z"/>')


def chamber_legend(lang="en"):
    return [("c-h is-circle", _chamber("H", lang)), ("c-s is-diamond", _chamber("S", lang))]


def scatter_chart(points, title, said, xlabel, ylabel, lang="en", note=""):
    """Committees as points: x the bills reported on, y the share that passed
    both chambers; points [(name, chamber, x, y)]. The three highest and the
    three lowest rates are named; every point has a title with its figures."""
    if not points:
        return ""
    w, h, top, bot = 540, 300, 14, 40
    xmax = max(p[2] for p in points)
    xmax = (int(xmax // 50) + 1) * 50 if xmax > 100 else (int(xmax // 10) + 1) * 10
    # The margins from what is drawn in them: the left holds the y ticks
    # ("100%") and, rotated, the y title; the right holds half of the last x
    # tick, which is centred on the plot's end.
    left = math.ceil(text_w("100%")) + 6 + CH_PX + 12
    right = math.ceil(text_w(str(xmax)) / 2) + 4
    sx = lambda v: left + (w - left - right) * v / xmax
    sy = lambda v: top + (h - top - bot) * (1 - v / 100)
    out = []
    for v in range(0, 101, 25):
        out.append(f'<line class="ax" x1="{left}" x2="{w - right}" y1="{sy(v):.1f}" y2="{sy(v):.1f}"/>'
                   f'<text x="{left - 6}" y="{sy(v) + 4:.1f}" text-anchor="end">{v}%</text>')
    step = max(10, int(xmax // 5 // 10 * 10)) if xmax > 50 else 10
    for v in range(0, int(xmax) + 1, step):
        out.append(f'<line class="ax" x1="{sx(v):.1f}" x2="{sx(v):.1f}" y1="{top}" y2="{h - bot}"/>'
                   f'<text x="{sx(v):.1f}" y="{h - bot + 14}" text-anchor="middle">{v}</text>')
    out.append(f'<text x="{(left + w - right) / 2:.0f}" y="{h - 6}" text-anchor="middle">{xlabel}</text>'
               f'<text transform="translate({CH_PX},{(top + h - bot) / 2:.0f}) rotate(-90)" text-anchor="middle">{ylabel}</text>')
    ranked = sorted(points, key=lambda p: (p[3], p[0]))
    named = {p[0] for p in ranked[:3] + ranked[-3:]}
    last = {}
    for name, ch, xv, yv in sorted(points, key=lambda p: (p[3], p[0])):
        out.append(f"<g><title>{E(name)}: {xv:,} bills reported on, {yv:.1f}% passed both chambers</title>"
                   + chamber_marker(ch, sx(xv), sy(yv)) + "</g>")
    # of two named committees at one rate, the right-hand point takes the line first, so the
    # left one's name, set a line lower, does not run across it (2023-2024: Childcare, Transportation)
    for name, ch, xv, yv in sorted((p for p in points if p[0] in named), key=lambda p: (-p[3], -p[2], p[0])):
        short = re.sub(r"^(House|Senate) ", "", name)
        # Beside its point on the side with room for the whole name; a name
        # longer than either side is set from the plot's edge on a free line
        # just above its point (below if above is taken), never on the
        # point's own line, which would hide the point it names.
        tw = math.ceil(text_w(short)) + 2
        free = lambda t: not any(abs(t - v) < 12 for v in last.values())
        edge = False
        if sx(xv) + 9 + tw <= w - 2:
            anchor, tx = "start", sx(xv) + 9
        elif sx(xv) - 9 - tw >= left:
            anchor, tx = "end", sx(xv) - 9
        else:
            anchor, tx, edge = "start", max(w - 2 - tw, 2), True
        ty = sy(yv) + 4
        if edge:
            # the lines just above and below its point, then further out;
            # the first free one that also leaves every other point clear, or failing
            # that the first free one (which may cover another point)
            lines = [sy(yv) + d for d in (-10, 18, -22, 30, -34, 42)]
            clear = lambda t: t >= 12 and free(t) and not any(
                tx - 6 <= sx(px) <= tx + tw + 6 and t - 17 <= sy(py) <= t + 9
                for pn, _c, px, py in points if pn != name)
            ty = next((t for t in lines if clear(t)), next((t for t in lines if t >= 12 and free(t)), lines[1]))
        while not free(ty):
            ty += 12
        last[name] = ty
        out.append(f'<text x="{tx:.1f}" y="{ty:.1f}" text-anchor="{anchor}">{E(short)}</text>')
    svg = _svg(w, h, said, "".join(out))
    return _chart(title, said, svg, chamber_legend(lang), note)


def dot_chart(rows, title, said, lang="en", note=""):
    """Attendance by term, a dot a chamber on one axis: rows
    [(label, house %, senate %)] (None where a chamber has none). The axis
    starts where the lowest figure leaves room, and says so."""
    vals = [v for _l, *vs in rows for v in vs if v is not None]
    if not vals:
        return ""
    lo = max(0, int(min(vals) // 5) * 5 - 5)
    bw, rh = 380, 19
    lw = math.ceil(max((text_w(label) for label, *_v in rows), default=0)) + 12
    sx = lambda v: lw + bw * (v - lo) / (100 - lo)
    out = []
    for v in range(lo, 101, 5):
        out.append(f'<line class="ax" x1="{sx(v):.1f}" x2="{sx(v):.1f}" y1="2" y2="{len(rows) * rh + 4}"/>'
                   f'<text x="{sx(v):.1f}" y="{len(rows) * rh + 18}" text-anchor="middle">{v}%</text>')
    for i, (label, h, s) in enumerate(rows):
        y = 4 + i * rh + 9
        out.append(f'<text x="{lw - 8}" y="{y + 4}" text-anchor="end">{label}</text>')
        for ch, v in (("H", h), ("S", s)):
            if v is not None:
                out.append(f"<g><title>{E(label)}, {E(_chamber(ch, lang))}: {v:.1f}%</title>"
                           + chamber_marker(ch, sx(v), y, 4) + "</g>")
    svg = _svg(lw + bw + math.ceil(text_w("100%") / 2) + 6, len(rows) * rh + 28, said, "".join(out))
    return _chart(title, said, svg, chamber_legend(lang), note)


def lines_chart(panels, title, said, lang="en", note=""):
    """Small multiples: one panel a chamber, each its own scale (never one
    axis shared by 400 members and 24), two lines a panel. panels
    [(name, [terms], [(series name, class, [values])])]."""
    pw, ph, left, top, bot = 262, 150, 36, 24, 22
    out = []
    for p, (name, terms, series) in enumerate(panels):
        x0 = p * (pw + 24)
        hi = max((v for _n, _c, vs in series for v in vs if v is not None), default=1) or 1
        nice = 10 ** len(str(int(hi))) / 10 if hi >= 1 else 1
        top_v = (int(hi / nice) + 1) * nice if hi >= 1 else 1
        sx = lambda i: x0 + left + (pw - left - 8) * i / max(len(terms) - 1, 1)
        sy = lambda v: top + (ph - top - bot) * (1 - v / top_v)
        out.append(f'<text x="{x0 + left}" y="{CH_PX}" class="sk-v">{E(name)}</text>')
        for k in range(0, 3):
            v = top_v * k / 2
            out.append(f'<line class="ax" x1="{x0 + left}" x2="{x0 + pw - 8}" y1="{sy(v):.1f}" y2="{sy(v):.1f}"/>'
                       f'<text x="{x0 + left - 5}" y="{sy(v) + 4:.1f}" text-anchor="end">{v:g}</text>')
        for i in (0, len(terms) - 1):
            out.append(f'<text x="{sx(i):.1f}" y="{ph - 6}" text-anchor="{"start" if i == 0 else "end"}">'
                       f'{terms[i][:4]}</text>')
        for sname, cls, vs in series:
            pts = [(sx(i), sy(v)) for i, v in enumerate(vs) if v is not None]
            if len(pts) > 1:
                out.append(f'<polyline class="ln ln-{cls}" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}"/>')
            for i, v in enumerate(vs):
                if v is not None:
                    out.append(f'<circle class="ln-dot ln-{cls}" cx="{sx(i):.1f}" cy="{sy(v):.1f}" r="2.2">'
                               f"<title>{E(name)}, {E(sname)}, {E(terms[i])}: {v:g}</title></circle>")
    svg = _svg(2 * pw + 24, ph + 4, said, "".join(out))
    return _chart(title, said, svg, [("c-ink", say(lang, "nums.ch_filed", "filed per member")),
                                     ("c-pine", say(lang, "nums.ch_law", "became law per member"))], note)


def positions_bar(support, oppose, neutral, lang="en"):
    """A hearing's sign-ins as one thin bar in its cell: support, oppose and
    neutral on the one scale of that hearing's total, in three neutral
    tones, each also its own number in the words beside it."""
    tot = support + oppose + neutral
    if not tot:
        return ""
    x, segs = 0.0, []
    for cls, n, w in (("ink", support, "support"), ("rest", oppose, "oppose"), ("pine", neutral, "neutral")):
        if n:
            segs.append(f'<rect class="pos-{cls}" x="{x:.1f}" y="0" width="{max(100 * n / tot - 1, 1):.1f}" height="6"/>')
            x += 100 * n / tot
    return ('<svg class="pos" viewBox="0 0 100 6" role="img" aria-label="'
            + E(say(lang, "nums.pos_said", "{s} support, {o} oppose, {n} neutral",
                    s=f"{support:,}", o=f"{oppose:,}", n=f"{neutral:,}")) + '" '
            'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">' + "".join(segs) + "</svg>")


def yes_bar(share, lang="en"):
    """A ballot question's yes share as a bar with the two-thirds line it
    needed (Part Second, Article 100) drawn across it."""
    return ('<svg class="pos yes" viewBox="0 0 100 10" role="img" aria-label="'
            + E(say(lang, "nums.yes_said", "{p}% yes; two thirds needed", p=f"{share:.1f}"))
            + '" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">'
            f'<rect class="pos-rest" x="0" y="2" width="100" height="6"/>'
            f'<rect class="pos-ink" x="0" y="2" width="{share:.1f}" height="6"/>'
            '<line class="pos-rule" x1="66.7" x2="66.7" y1="0" y2="10"/></svg>')


# ---------------------------------------------------------------------------
# WHERE A BILL STOPPED: the Sankey diagram and the table that says the same
# (the owner, 11 November 2026). One field draws it, the one every bill's
# card and rail read: the index row's `passage` -- the chamber it started in,
# then a mark for the first chamber, the second, the governor and the end
# (p cleared it, x stopped there, h is there now, - never reached). So the
# diagram, the card and the table cannot disagree, and every House or Senate
# bill of a term lands in exactly one end node: flows() counts it once,
# flow_tree() names the nodes, and preflight holds the end nodes to the
# bills filed, term by term.
# ---------------------------------------------------------------------------

# A bill that stopped, by what the record says ended it (the status word the
# card shows), in the order the end nodes are drawn; and each kind's colour
# class and its words (say() keys nums.sk_*).
END_KIND = {"Killed": "killed", "Died on the table": "tabled", "Referred for interim study": "study",
            "Died when the session ended": "session", "Indefinitely postponed": "postponed",
            "Withdrawn": "withdrawn", "Withdrawn prior to introduction": "withdrawn",
            "Not introduced": "withdrawn", "Refused introduction": "withdrawn",
            "Died: the chambers did not agree on a version": "noversion",
            "Died: conferees could not agree": "conferees",
            "Died when the conference report was rejected": "rejected"}
END_ORDER = ("killed", "tabled", "study", "session", "postponed", "withdrawn", "noversion",
             "conferees", "rejected", "other")
END_CLASS = {"killed": "done", "tabled": "table", "study": "study", "session": "done",
             "postponed": "done", "withdrawn": "rest", "noversion": "done", "conferees": "done",
             "rejected": "done", "other": "rest", "law": "law", "veto": "veto",
             "moving": "active", "unclassified": "rest"}
END_WORDS = {"killed": ("killed (ITL)", "killed (ITL)"), "tabled": ("died on the table", ""),
             "study": ("sent to interim study", ""), "session": ("died when the session ended", ""),
             "postponed": ("indefinitely postponed", ""), "withdrawn": ("withdrawn or not introduced", ""),
             "noversion": ("chambers did not agree on a version", ""),
             "conferees": ("conferees could not agree", ""),
             "rejected": ("conference report rejected", ""), "other": ("other endings", ""),
             "law": ("became law", ""), "veto": ("veto stood", ""),
             "moving": ("still moving", ""), "unclassified": ("not classified", "")}


def flows(idx, term):
    """Where the House and Senate bills of `term` stopped, counted from each
    row's `passage`: {"filed", "resolutions", "carried", "first", "second",
    "nogov", "gov": Counter(kind) for the bills that stopped at each place,
    "cleared_first", "passed_both", "reached", "law_how", "moving",
    "unclassified"}. A bill whose passage is empty or not five marks is
    counted as unclassified, never dropped, so the end nodes always sum to
    "filed" (preflight holds it to that, for every term)."""
    rows = [r for r in idx if r.get("term") == term]
    bills = [r for r in rows if BILL.match(r.get("id") or "")]
    out = {"term": term, "filed": len(bills), "resolutions": len(rows) - len(bills),
           "carried": sum(1 for r in bills if r.get("carried")),
           "first": Counter(), "second": Counter(), "nogov": Counter(), "gov": Counter(),
           "cleared_first": 0, "passed_both": 0, "reached": 0, "law_how": Counter(),
           "moving": 0, "unclassified": 0, "origin": Counter()}
    for r in bills:
        ps = r.get("passage") or ""
        if len(ps) != 5 or ps[0] not in "HS" or any(m not in "px-h" for m in ps[1:]):
            out["unclassified"] += 1
            continue
        out["origin"][ps[0]] += 1
        a, b, c, d = ps[1:]
        if "h" in ps[1:]:
            out["moving"] += 1
            continue
        kind = END_KIND.get(r.get("status"), "other")
        if a != "p":
            out["first"][kind] += 1
            continue
        out["cleared_first"] += 1
        if b != "p":
            out["second"][kind] += 1
            continue
        out["passed_both"] += 1
        if c == "-":
            out["nogov"][kind] += 1
            continue
        out["reached"] += 1
        if d == "p":
            out["gov"]["law"] += 1
            out["law_how"][r.get("status")] += 1
        else:
            out["gov"]["veto" if c == "x" else "other"] += 1
    return out


def flow_tree(f, lang="en"):
    """The diagram's nodes as a tree {"label", "n", "cls", "kids", "key"},
    root first, from flows(): the same numbers the sentence and the table
    read. A node with no bills is left out, so a finished term draws no
    "still moving". Every word is said here in full, each say() with its
    key and English written out, as the catalogue's check reads them."""
    w = {"killed": say(lang, "nums.sk_killed", "killed (ITL)"),
         "tabled": say(lang, "nums.sk_tabled", "died on the table"),
         "study": say(lang, "nums.sk_study", "sent to interim study"),
         "session": say(lang, "nums.sk_session", "died when the session ended"),
         "postponed": say(lang, "nums.sk_postponed", "indefinitely postponed"),
         "withdrawn": say(lang, "nums.sk_withdrawn", "withdrawn or not introduced"),
         "noversion": say(lang, "nums.sk_noversion", "chambers did not agree on a version"),
         "conferees": say(lang, "nums.sk_conferees", "conferees could not agree"),
         "rejected": say(lang, "nums.sk_rejected", "conference report rejected"),
         "other": say(lang, "nums.sk_other", "other endings"),
         "law": say(lang, "nums.sk_law", "became law"),
         "veto": say(lang, "nums.sk_veto", "veto stood"),
         "moving": say(lang, "nums.sk_moving", "still moving"),
         "unclassified": say(lang, "nums.sk_unclassified", "not classified")}

    def leaf(key, n):
        return {"key": key, "label": w[key], "n": n, "cls": END_CLASS[key], "kids": []}

    def ends(counter):
        return [leaf(k, counter[k]) for k in ("law", "veto") + END_ORDER if counter.get(k)]

    def node(key, label, n, kids):
        return {"key": key, "label": label, "n": n, "cls": "n", "kids": [k for k in kids if k["n"]]}
    first_n, second_n = sum(f["first"].values()), sum(f["second"].values())
    gov = node("reached", say(lang, "nums.sk_reached", "Reached the governor"), f["reached"], ends(f["gov"]))
    nogov = node("nogov", say(lang, "nums.sk_nogov", "Never reached the governor"),
                 sum(f["nogov"].values()), ends(f["nogov"]))
    both = node("passed_both", say(lang, "nums.sk_passed_both", "Cleared the second chamber"),
                f["passed_both"], [nogov, gov])
    second = node("second", say(lang, "nums.sk_second", "Stopped in the second chamber"),
                  second_n, ends(f["second"]))
    cleared = node("cleared_first", say(lang, "nums.sk_cleared_first", "Cleared the first chamber"),
                   f["cleared_first"], [second, both])
    stopped = node("first", say(lang, "nums.sk_first", "Stopped in the first chamber"),
                   first_n, ends(f["first"]))
    extra = [leaf("moving", f["moving"]), leaf("unclassified", f["unclassified"])]
    return node("filed", say(lang, "nums.sk_filed", "Bills filed"), f["filed"], [stopped, cleared] + extra)


def flow_leaves(tree):
    """[(key, n)] of the end nodes, left to right."""
    if not tree["kids"]:
        return [(tree["key"], tree["n"])]
    return [x for k in tree["kids"] for x in flow_leaves(k)]


# The geometry, in the figure's own units: a bill is K tall, a leaf at least
# LEAF_MIN and at least PITCH apart so that its label never meets the next,
# five columns of nodes a COL apart.
SK_K, SK_LEAF_MIN, SK_PITCH, SK_NODE_W, SK_COL, SK_W, SK_BAND = 0.14, 2.5, 20, 10, 146, 864, 28


def sankey_svg(tree, said, lang="en"):
    """The flow diagram as inline SVG: nodes in columns by how far a bill
    went, ribbons as tall as the bills they carry, every end node labelled
    with its count. Computed here, drawn with no script and no library; a
    reader who cannot see it has `said` and the table beside it. Nodes are
    colour-classed with the status chips' tokens, and every one is also its
    own words, so colour is never the only way to read it."""
    cursor = [0.0]

    # A node that has nodes after it is named in a band of its own, above its
    # bar and clear of every flow: each takes SK_BAND of height before its
    # first end node, so two nodes that begin together (a branch and its
    # first branch) are named one above the other, a column apart. An end
    # node is named beside its bar, and ends are SK_PITCH apart, so no two
    # names meet.
    def place(n, depth):
        n["depth"] = depth
        if not n["kids"]:
            n["h"] = max(n["n"] * SK_K, SK_LEAF_MIN)
            n["y"] = cursor[0]
            cursor[0] += max(n["h"] + 6, SK_PITCH)
            return
        n["ly"] = cursor[0]
        cursor[0] += SK_BAND
        for k in n["kids"]:
            place(k, depth + 1)
        n["y"] = n["kids"][0]["y"]
        n["h"] = sum(k["h"] for k in n["kids"])
    place(tree, 0)
    height = cursor[0] + 6
    nodes, ribbons, labels, ends = [], [], [], []
    total = tree["n"]

    def walk(n):
        x = 4 + n["depth"] * SK_COL
        pct = f"{100 * n['n'] / total:.1f}" if total else "0.0"
        title = say(lang, "nums.sk_title", "{name}: {n} bills ({pct}% of the {total})",
                    name=n["label"], n=f"{n['n']:,}", pct=pct, total=f"{total:,}")
        nodes.append(f'<g><title>{E(title)}</title><rect class="sk-n sk-{n["cls"]}" x="{x}" '
                     f'y="{n["y"]:.1f}" width="{SK_NODE_W}" height="{n["h"]:.1f}"/></g>')
        lx = x + SK_NODE_W + 6
        if n["kids"]:
            labels.append(f'<text x="{x}" y="{n["ly"] + 15:.1f}">{E(n["label"])} '
                          f'<tspan class="sk-v">{n["n"]:,}</tspan></text>')
            cur = n["y"]
            for k in n["kids"]:
                x1 = 4 + k["depth"] * SK_COL
                xa, xm = x + SK_NODE_W, (x + SK_NODE_W + x1) / 2
                ya0, ya1, yb0, yb1 = cur, cur + k["h"], k["y"], k["y"] + k["h"]
                cur = ya1
                cls = "sk-r " + ("n" if k["kids"] else f"sk-{k['cls']}")
                ribbons.append(
                    f'<path class="{cls}" d="M{xa},{ya0:.1f}C{xm},{ya0:.1f} {xm},{yb0:.1f} {x1},{yb0:.1f}'
                    f'L{x1},{yb1:.1f}C{xm},{yb1:.1f} {xm},{ya1:.1f} {xa},{ya1:.1f}Z"/>')
                walk(k)
        else:
            ends.append((lx, n["label"], n["n"]))
            labels.append(f'<text x="{lx}" y="{n["y"] + n["h"] / 2 + 4:.1f}">{E(n["label"])} '
                          f'<tspan class="sk-v">{n["n"]:,}</tspan></text>')
    walk(tree)
    # Never narrower than its names: the widest end label, from its bar's x,
    # sets the width if it runs past the 864 the layout is drawn for.
    width = max(SK_W, max((math.ceil(lx + text_w(f"{lab} {cnt:,}") + 4)
                           for lx, lab, cnt in ends), default=0))
    return (f'<svg class="sk" viewBox="0 0 {width} {height:.0f}" role="img" aria-label="{E(said)}" '
            f'xmlns="http://www.w3.org/2000/svg"><g aria-hidden="true">'
            + "".join(ribbons) + "".join(nodes) + "".join(labels) + "</g></svg>")


def flow_twin(tree, lang="en"):
    """The diagram's table: each node, indented under what it came from, with
    its bills and its share of the bills filed. No sorting: it is a tree."""
    total, rows = tree["n"], []

    def walk(n, d):
        rows.append([f'<span class="l-ind" style="--d:{d}">{E(n["label"])}</span>', f"{n['n']:,}",
                     _pct(n["n"], total)])
        for k in n["kids"]:
            walk(k, d + 1)
    walk(tree, 0)
    return _table([say(lang, "nums.sk_stage", "Where it stood"), say(lang, "nums.c_bills", "Bills"),
                   say(lang, "nums.c_share", "Share")], rows, cls="numtab l-twin", sortable=False)


def flow_said(f, lang="en"):
    """The diagram's one sentence for a reader who cannot see it."""
    return say(lang, "nums.sk_said",
               "Flow diagram of the {filed} House and Senate bills of the {term} term: {s1} stopped in "
               "the first chamber, {s2} in the second, {nog} cleared both chambers and never reached the "
               "governor, and {g} reached the governor, {law} of which became law. The figures are in "
               "the table below.",
               filed=f"{f['filed']:,}", term=components.term_words(f["term"]),
               s1=f"{sum(f['first'].values()):,}", s2=f"{sum(f['second'].values()):,}",
               nog=f"{sum(f['nogov'].values()):,}", g=f"{f['reached']:,}", law=f"{f['gov']['law']:,}")


def flow_figure(f, lang="en", fold_open=True):
    """The diagram, scrolling sideways on a phone rather than shrinking past
    reading, and its table in a fold under it."""
    tree = flow_tree(f, lang)
    return ('<figure class="l-fig l-sk"><div class="l-skwrap">' + sankey_svg(tree, flow_said(f, lang), lang)
            + '</div><details class="l-fold"><summary>'
            + say(lang, "nums.sk_table", "The same figures as a table") + "</summary>"
            + flow_twin(tree, lang) + "</details></figure>")


def flow_sentence(f, lang="en"):
    """What the diagram says, in words, from the same counts: where bills
    stopped, how many reached the governor, how many were carried over, and
    how many resolutions the diagram leaves out."""
    first_n, second_n = sum(f["first"].values()), sum(f["second"].values())
    nogov = sum(f["nogov"].values())
    return say(lang, "nums.sk_p",
               "Of the {filed} House and Senate bills of {term}, {s1} stopped in the first chamber and "
               "{s2} in the second. {nog} passed both chambers and never reached the governor, and "
               "{g} reached the governor: {law} became law and {veto} were vetoed with the veto "
               "standing. {carried} of the {filed} were carried over from the first year to the second, "
               "which changes when a bill ended and not how. Not counted here: the {res} resolutions "
               "and constitutional amendments of the term.",
               filed=f"{f['filed']:,}", term=_t(f["term"]), s1=f"{first_n:,}", s2=f"{second_n:,}",
               nog=f"{nogov:,}", g=f"{f['reached']:,}", law=f"{f['gov']['law']:,}",
               veto=f"{f['gov']['veto']:,}", carried=f"{f['carried']:,}", res=f"{f['resolutions']:,}")


# ---------------------------------------------------------------------------
# The page.
# ---------------------------------------------------------------------------

MISSING = []   # [(file, the section left out)] of the last body(); build_civics prints it
HELD = []      # [what was left off, and why] of the last body(); build_civics prints it

# Every section's heading, as body() writes it (the closest votes' ends in the
# term). preflight's data check holds the built page to the list, so a section
# left out for want of its input fails a full preflight run.
HEADINGS = ("Bills Filed, and How They Ended", "Bills Filed and Passed per Member",
            "Each Committee's Record", "The Hearings with the Most Sign-Ins",
            "How Often the Full Chamber Overrules Its Committee",
            "What Passed, and How It Changed on the Way",
            "How the Votes Were Taken", "The Closest Votes of", "Attendance on Roll-Call Days",
            "Constitutional Amendments Sent to the Voters")


def _need(path, what):
    """The parsed file, or None with the file and its section on MISSING."""
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    MISSING.append((str(p), what))
    return None


def _chamber(ch, lang="en"):
    """A chamber's name in `lang`: "House" or "Senate" in English (NAME)."""
    return (say(lang, "nums.house", "House") if ch == "H" else
            say(lang, "nums.senate", "Senate") if ch == "S" else "")


def _en(x, lang="en"):
    """Words the record wrote -- a committee's name, a bill's title, a
    question put to a chamber -- set apart in another language, so a screen
    reader says them in English (i18n.py, the first kind of words)."""
    return x if lang == "en" or not x else f'<span lang="en">{x}</span>'


def body(site=Path("site"), root=Path("."), strict=True, lang="en"):
    """The page's sections as HTML, each under its h2. `lang` says it in
    another language (9 November 2026: the person's "more of the site in
    Spanish"): every sentence and heading through say(), keyed nums.*, its
    figures worked out once and filled into the sentence, its tables' words
    in that language and the record's own words (a committee, a title, a
    question) as the record prints them, marked as English. English is as
    it was, to the byte."""
    # Every bill's row, from the term files the pages read (site_read); it
    # stops where there is none rather than count nothing.
    idx = SR.bill_index_or_stop(site, "learn_numbers.py")
    root = Path(root)
    del MISSING[:]
    del HELD[:]
    narr_all = _need(root / "narratives.json", "every committee and floor figure") or {}
    rollcalls = _load(root / "rollcalls.json", {})
    YEAR.update({(r.get("term"), r.get("id")): str(r.get("year") or "") for r in idx})
    terms = sorted({r.get("term") for r in idx if r.get("term")})
    # The term the page's "In the ... term" figures tell: not the newest one
    # while most of its bills are still to be decided (site_read.figures_term).
    current = SR.figures_term(idx)
    recent = terms[-10:]
    if strict and idx and not any("chip" in r for r in idx):
        raise SystemExit("learn_numbers.py: the bill index carries no chip; it was built before "
                         "build_site_v2.chip_word, so how each bill ended cannot be counted")
    # The page carried a "Draft" banner here saying it was unlinked and asking
    # search engines not to list it. Both of those stopped being true on 17
    # September, when the person read it and asked for it to be public, and a
    # banner that describes the page's old status is worse than none.
    #
    # What survives is the half of it that is still the point: every number
    # here is counted from the record at build time. That is what separates
    # this page from a statistics page somebody typed, and it is the first
    # thing a reader should know.
    # The note opens the page under a heading of its own, as every Learn
    # page's opening paragraph does (W4: each heading in the margin beside
    # its prose; the heading is the approved prototype's, 9 October 2026).
    out = ['<h2>' + say(lang, "nums.h_how", "How These Are Counted") + '</h2>'
           '<p>' + say(lang, "nums.p_how", "Every number on this page is counted from the "
                       "General Court's own record when the site is built, not typed in. "
                       "Each section says what it counts and over what period. Where the "
                       "record on this site cannot answer something, the section says so "
                       "rather than estimating.") + '</p>']
    narr = narr_all.get(current, {})

    # 1. Bills filed, and how they ended: where each of the last ten terms' bills
    # stopped (the newest open, the others in folds that need no script), then
    # how they ended term by term, and what became of those that reached the
    # governor -- the Vetoes section's figures, folded in (the owner, 11
    # November 2026).
    oc = outcomes(idx)
    orows = []
    for t in terms:
        c = oc.get(t)
        if not c:
            continue
        n = c["filed"]
        orows.append([_t(t), f"{n:,}", _np(c["Became Law"], n), _np(c["Died"], n),
                      _np(c["Interim Study"], n), _np(c["other"], n)])
    folds = []
    for t in reversed(recent):
        f = flows(idx, t)
        if not f["filed"]:
            continue
        folds.append(f'<details class="l-fold"{" open" if t == current else ""}><summary>'
                     + say(lang, "nums.sk_fold", "{term}: {filed} bills, {law} became law",
                           term=_t(t), filed=f"{f['filed']:,}", law=f"{f['gov']['law']:,}")
                     + "</summary><p>" + flow_sentence(f, lang) + "</p>" + flow_figure(f, lang) + "</details>")
    vrows, waiting = [], 0
    for t in recent:
        reached, vetoed, stood, over, live = vetoes([r for r in idx if r.get("term") == t])
        waiting += live
        vrows.append([_t(t), f"{reached:,}", _np(vetoed, reached), str(stood), str(over)])
    # NOT THE CONSTITUTIONAL AMENDMENTS OR RESOLUTIONS, AND SAID SO (the survey of
    # 7 October 2026): 2,139 for 2025-2026 here and 2,243 bills and resolutions
    # on How a bill becomes law, and neither page said what it counted.
    out.append("<h2>" + say(lang, "nums.h_filed", "Bills Filed, and How They Ended") + "</h2><p>"
               + say(lang, "nums.p_filed", "Every House and Senate bill "
                     "given a number in each term, not counting constitutional amendments or "
                     "resolutions, by the word its card on this site shows. "
                     "Died covers a bill killed on the floor, left on the table, vetoed with the "
                     "veto standing, lost between the two chambers, or still pending when its term "
                     "ended; Other is a bill withdrawn, never introduced, or still before the "
                     "legislature.") + "</p><p>"
               + say(lang, "nums.p_filed_sk",
                     "The diagrams show where each of the last ten terms' bills stopped, from the "
                     "same record the passage rail on a bill's page reads, so a bill is in one place "
                     "in the diagram, on its page and in the table beneath it. Died is split into "
                     "what ended each bill, in the record's own words.") + "</p>"
               + wide('<div class="l-folds is-wide">' + "".join(folds) + "</div>")
               + ends_chart(oc, terms, lang)
               + _table([say(lang, "nums.c_term", "Term"), say(lang, "nums.c_filed", "Bills filed"),
                         say(lang, "nums.c_law", "Became Law"), say(lang, "nums.c_died", "Died"),
                         say(lang, "nums.c_study", "Interim Study"), say(lang, "nums.c_other", "Other")],
                        orows)
               + "<h3>" + say(lang, "nums.h_gov", "From the Governor's Desk") + "</h3><p>"
               + say(lang, "nums.p_vetoes",
                     "Of the bills and joint resolutions that reached the governor in "
                     "each of the last ten "
                     "terms, how many were vetoed, and what became of the veto. A bill that became "
                     "law without a signature reached the governor and was not vetoed. A veto stood "
                     "when the override failed or no override vote came before the session ended.")
               + (" " + (say(lang, "nums.waiting_one", "1 veto of {term} is still to be voted on, and "
                             "counted as vetoed only.", term=_t(current)) if waiting == 1 else
                         say(lang, "nums.waiting", "{n} vetoes of {term} are still to be voted on, and "
                             "counted as vetoed only.", n=waiting, term=_t(current)))
                  if waiting else "") + "</p>"
               + _table([say(lang, "nums.c_term", "Term"), say(lang, "nums.c_reached", "Reached the governor"),
                         say(lang, "nums.c_vetoed", "Vetoed"), say(lang, "nums.c_stood", "Veto stood"),
                         say(lang, "nums.c_over", "Overridden")], vrows))

    # 2. Bills filed and passed per member.
    pm = per_member(idx)
    prows = []
    for t in terms:
        h, s = pm[t]["H"], pm[t]["S"]
        if not (h[0] or s[0]):
            continue
        prows.append([_t(t), f"{h[0] / SEATS['H']:.2f}", f"{h[1] / SEATS['H']:.2f}",
                      f"{s[0] / SEATS['S']:.1f}", f"{s[1] / SEATS['S']:.1f}"])
    pm_terms = [t for t in terms if pm[t]["H"][0] or pm[t]["S"][0]]
    member_chart = ""
    if len(pm_terms) > 1:
        panel = lambda ch, seats, dig: (_chamber(ch, lang), pm_terms, [
            (say(lang, "nums.ch_filed", "filed per member"), "ink",
             [round(pm[t][ch][0] / seats, dig) for t in pm_terms]),
            (say(lang, "nums.ch_law", "became law per member"), "pine",
             [round(pm[t][ch][1] / seats, dig) for t in pm_terms])])
        member_chart = lines_chart(
            [panel("H", SEATS["H"], 2), panel("S", SEATS["S"], 1)],
            say(lang, "nums.ch_member_h", "Bills per Member, Over the Terms"),
            say(lang, "nums.ch_member_said",
                "Two line charts, one for each chamber because their scales differ: the House bills "
                "filed per representative ran from {hl} to {hh} and the Senate's per senator from {sl} "
                "to {sh}. The figures are in the table below.",
                hl=f"{min(pm[t]['H'][0] for t in pm_terms) / SEATS['H']:.2f}",
                hh=f"{max(pm[t]['H'][0] for t in pm_terms) / SEATS['H']:.2f}",
                sl=f"{min(pm[t]['S'][0] for t in pm_terms) / SEATS['S']:.1f}",
                sh=f"{max(pm[t]['S'][0] for t in pm_terms) / SEATS['S']:.1f}"),
            lang, say(lang, "nums.ch_member_p", "Each chamber has its own scale: 400 representatives and 24 senators."))
    out.append("<h2>" + say(lang, "nums.h_member", "Bills Filed and Passed per Member")
               + "</h2><p>" + say(lang, "nums.p_member", "The House and Senate bills whose "
                                  "prime sponsor sat in each chamber, divided by its seats: 400 in the House, 24 "
                                  "in the Senate. Passed means the bill became law.") + "</p>"
               + member_chart + _table([say(lang, "nums.c_term", "Term"),
                         say(lang, "nums.c_f_rep", "Filed per representative"),
                         say(lang, "nums.c_l_rep", "Became law per representative"),
                         say(lang, "nums.c_f_sen", "Filed per senator"),
                         say(lang, "nums.c_l_sen", "Became law per senator")], prows))

    # 3. Each committee: what it was sent, what it reported, how those fared, and
    # how much of it went on consent -- one table for the three sections that
    # said overlapping things about the same committees (the owner, 11
    # November 2026), for each of the last ten terms, the newest open.
    blocks = []
    for t in reversed(recent):
        rec, ctot, per_ch = committee_record(idx, narr_all, t)
        crows, groups = committee_rows(rec, lang)
        first_n = sum(v["first"] for v in rec.values())
        sent_n = sum(v["sent"] for v in rec.values())
        lines = ""
        if t == current:
            tot_line = "; ".join(
                (say(lang, "nums.tot_h", "of the {n} bills a House committee reported on, {pct} passed both chambers",
                     n=f"{n:,}", pct=_pct(p, n)) if ch == "H" else
                 say(lang, "nums.tot_s", "of the {n} bills a Senate committee reported on, {pct} passed both chambers",
                     n=f"{n:,}", pct=_pct(p, n)))
                for ch, (n, p, _l) in ctot.items() if n)
            kept = sum(c["kept"] for c in per_ch.values())
            regular = sum(c["regular"] for c in per_ch.values())
            removed = sum(c["removed"] for c in per_ch.values())
            total = kept + regular + removed

            def chamber_cc(ch):
                c = per_ch.get(ch) or Counter()
                tot = c["kept"] + c["regular"] + c["removed"]
                if not tot:
                    return ""
                return "<p>" + (
                    say(lang, "nums.cc_h_line", "{pct} of the House&rsquo;s {n} committee recommendations "
                        "were adopted on its consent calendar; {off} were taken off it.",
                        pct=_pct(c["kept"], tot), n=f"{tot:,}", off=f"{c['removed']:,}") if ch == "H" else
                    say(lang, "nums.cc_s_line", "{pct} of the Senate&rsquo;s {n} committee recommendations "
                        "were adopted on its consent calendar; {off} were taken off it.",
                        pct=_pct(c["kept"], tot), n=f"{tot:,}", off=f"{c['removed']:,}")) + "</p>"
            lines = (("<p>" + say(lang, "nums.p_rates2", "In {term}, {lines}.", term=_t(t), lines=tot_line)
                      + "</p>" if tot_line else "")
                     + ("<p>" + say(lang, "nums.p_consent2",
                                    "In {term}, <b>{kept} of {total}</b> committee recommendations "
                                    "({pct}) were adopted on the consent calendar, and "
                                    "<b>{regular}</b> went to the regular calendar, {removed} of them "
                                    "after being taken off consent.",
                                    term=_t(t), kept=f"{kept:,}", total=f"{total:,}",
                                    pct=_pct(kept, total), regular=f"{regular + removed:,}",
                                    removed=f"{removed:,}") + "</p>" if total else "")
                     + chamber_cc("H") + chamber_cc("S"))
        blocks.append(f"<details class=\"l-fold\"{' open' if t == current else ''}><summary>"
                      + say(lang, "nums.fold_refs", "{term}: {first} first referrals and {sent} sent on",
                            term=_t(t), first=f"{first_n:,}", sent=f"{sent_n:,}") + "</summary>"
                      + lines + committee_chart(rec, t, lang)
                      + _table([say(lang, "nums.c_cmte", "Committee"),
                                say(lang, "nums.c_first", "First referral"),
                                say(lang, "nums.c_sent", "Sent on from another committee"),
                                say(lang, "nums.c_reported", "Bills reported on"),
                                say(lang, "nums.c_both", "Passed both chambers"),
                                say(lang, "nums.c_law_l", "Became law"),
                                say(lang, "nums.c_rate", "Passage rate"),
                                say(lang, "nums.c_cshare", "Consent share")],
                               crows, groups=groups, sortable=True)
                      + "</details>")
    out.append("<h2>" + say(lang, "nums.h_cmte", "Each Committee's Record") + "</h2><p>"
               + say(lang, "nums.p_cmte",
                     "For each committee of the last ten terms: how many bills its chamber sent it "
                     "first, as each bill's page names its committee, and how many it received after "
                     "another committee of the same chamber had them &mdash; most often Finance or "
                     "Ways and Means, for a bill that spends or raises money. Every numbered measure "
                     "counts in those two columns, resolutions included. The rest count House and "
                     "Senate bills: those the committee made a majority report on, whatever it "
                     "recommended, how many of them passed both chambers and how many became law, "
                     "and, for a committee with ten reports or more, the passage rate and the share of "
                     "its reports that went on the consent calendar and stayed there. A bill two "
                     "committees of a chamber reported on counts in both.") + "</p><p>"
               + say(lang, "nums.p_cmte2",
                     "A committee sends a report to the consent calendar by its own vote, and in both "
                     "chambers that vote must be unanimous, though the recommendation itself may have "
                     "been carried on a divided one. The whole calendar is adopted in one vote without "
                     "debate, and what it adopts is each committee's recommendation, to pass the bill, "
                     "to kill it, or to send it to interim study, unless the bill is first taken off "
                     "&mdash; since January 2023 at the request of ten members in the House, and since "
                     "April 2026 of two in the Senate. A Senate committee's House bills had already "
                     "passed the House, and the other way round, so compare committees within a "
                     "chamber rather than across: the table sorts within each chamber, and the "
                     "Committee heading sorts across both.") + "</p>"
               + '<div class="l-folds">' + "".join(blocks) + "</div>")

    # 4. The hearings with the most sign-ins.
    tdb = _need(root / "testimony_db.json", "the hearings with the most sign-ins")
    if tdb:
        # Twenty, and the paragraph says twenty.
        si = signins(tdb, narr_all, idx, site, root, top=20, strict=strict)
        # THE CURRENT TERM ONLY (the person, 10 October 2026: "remove the
        # 2023-2024 online sign in chart ... and just keep the 2025-2026
        # numbers"). The earlier term's twenty were the first months of the
        # form, and set beside a full term they compared nothing like with like.
        si = {t: hs for t, hs in si.items() if t == current}
        allh = [h for t in si for h in si[t]]
        sided = [h for h in allh if h["support"] + h["oppose"]]
        lop = sum(1 for h in sided if 10 * max(h["support"], h["oppose"])
                  >= 9 * (h["support"] + h["oppose"]))
        against = sum(1 for h in allh if h["oppose"] > h["support"])
        tables = []
        for t in sorted(si, reverse=True):
            # Five columns, the hearing's day and committee in one and the
            # three positions in one: eight ran past the Learn column's 560
            # pixels on a desktop, scrolled, and left the title 117 of them.
            def on_what(w):
                return (say(lang, "nums.on_nongermane", "a non-germane amendment")
                        if w == "a non-germane amendment" else
                        say(lang, "nums.on_amendment", "an amendment"))
            srows = [[_bill_link(t, h["bill"], h["year"]), _en(E(h["title"]), lang),
                      _day(h["date"], lang)
                      + (say(lang, "nums.hear_on", ", on {what}", what=on_what(h["on"]))
                         if h["on"] else "")
                      + (f"<br>{_en(E(h['committee']), lang)}" if h["committee"] else ""),
                      f"{h['total']:,}",
                      say(lang, "nums.n_support", "{n}&nbsp;support", n=f"{h['support']:,}") + "<br>"
                      + say(lang, "nums.n_oppose", "{n}&nbsp;oppose", n=f"{h['oppose']:,}")
                      + ("<br>" + say(lang, "nums.n_neutral", "{n}&nbsp;neutral", n=f"{h['neutral']:,}")
                         if h["neutral"] else "")
                      + positions_bar(h["support"], h["oppose"], h["neutral"], lang)]
                     for h in si[t]]
            tables.append(wide(f"<h3>{_t(t)}</h3>" + _table(
                [say(lang, "nums.c_bill", "Bill"), say(lang, "nums.c_title", "Title as heard"),
                 say(lang, "nums.c_hearing", "Hearing and committee"),
                 say(lang, "nums.c_signed", "Signed in"), say(lang, "nums.c_positions", "Positions")],
                srows)))
        out.append("<h2>" + say(lang, "nums.h_signins", "The Hearings with the Most Sign-Ins")
                   + "</h2><p>" + say(
                       lang, "nums.p_signins",
                       "Anyone may use the House's "
                       "online form to say they support or oppose a bill, or are neutral on it, at "
                       "its committee hearing. These are the twenty hearings with the most of those "
                       "sign-ins in the {term} term: one "
                       "bill on one House committee date, with the title it had when it was heard. "
                       "A sign-in is a position registered, not a vote and not a person counted: "
                       "one person may sign in on many bills, nobody is sampled, and an organized "
                       "appeal can bring thousands. The busiest hearings were seldom closely "
                       "divided: {lop} of these {n} drew nine in ten sign-ins or more on "
                       "one side, and {against} drew more against the bill than for it. So the "
                       "tables show where turnout was largest, not where opinion was split, and not "
                       "what the committee decided. Senate hearings are not on this form.",
                       term=_t(current), lop=lop, n=len(allh), against=against)
                   + "</p>" + "".join(tables))

    # 5. Committees overruled on the floor.
    st, cases = overturned(narr)
    rows = []
    for ch in ("H", "S"):
        d, a, s = st.get(ch, (0, 0, 0))
        rows.append([_chamber(ch, lang), f"{d:,}", _np(a, d), _np(s, d)])

    def rec_word(r):
        return (say(lang, "nums.r_pass", "pass") if r == "PASS" else
                say(lang, "nums.r_kill", "kill") if r == "KILL" else
                say(lang, "nums.r_study", "interim study"))
    out.append("<h2>" + say(lang, "nums.h_overrule", "How Often the Full Chamber Overrules Its Committee")
               + "</h2><p>" + say(
                   lang, "nums.p_overrule",
                   "In the {term} term, a committee's recommendation "
                   "was followed by the chamber far more often than not. Counted here: each bill's "
                   "committee report in each chamber, against the first motion adopted on that "
                   "chamber's floor that decided the bill there &mdash; ought to pass, inexpedient to "
                   "legislate or indefinite postponement, or interim study.", term=_t(current))
               + "</p>"
               + _table([say(lang, "nums.c_chamber", "Chamber"),
                         say(lang, "nums.c_decided", "Recommendations decided on the floor"),
                         say(lang, "nums.c_otherwise", "Decided otherwise"),
                         say(lang, "nums.c_reversed", "Passage and kill reversed")], rows))
    if cases:
        items = "".join("<li>" + say(lang, "nums.case", "{bill} &mdash; {chamber}: committee {rec}, floor {floor}",
                                     bill=_bill_link(current, b), chamber=_chamber(c, lang),
                                     rec=rec_word(r), floor=rec_word(f)) + "</li>"
                        for b, c, r, f in sorted(cases)[:60])
        out.append('<div class="l-folds"><details class="l-fold"><summary>'
                   + say(lang, "nums.the_bills", "The {n} bills", n=len(cases))
                   + f'</summary><ul class="l-bills">{items}</ul></details></div>')

    # 8 and 9, one section: what passed both chambers, and how much it was
    # changed on the way (the owner, 11 November 2026). The era table is the
    # term table rolled up, and the sort does that job.
    pa = passage(idx, narr_all)
    parows, all_d, all_n, all_amended = [], Counter(), 0, 0
    for t in terms:
        p = pa.get(t)
        if not p or not p["passed"]:
            continue
        n, d = p["passed"], p["dist"]
        all_d.update(d)
        all_n += n
        all_amended += p["amended"]
        # Before 1999 the amendment counts are the weakest figures on the page.
        parows.append([_t(t) + ("&nbsp;*" if t < "1999" else ""), f"{n:,}", _np(p["amended"], n),
                       _np(p["conference"], n)] + [_pct(d[k], n) for k in range(3)]
                      + [_pct(sum(d[k] for k in range(3, 7)), n)])
    passed_chart = ""
    if len(parows) > 1:
        rowsd = [(_t(t), [pa[t]["amended"], pa[t]["passed"] - pa[t]["amended"]]) for t in terms
                 if pa.get(t) and pa[t]["passed"]]
        passed_chart = stack100_chart(
            rowsd, [("ink", say(lang, "nums.c_amended", "Amended")),
                    ("rest", say(lang, "nums.c_intro", "As introduced"))],
            say(lang, "nums.ch_pass_h", "Passed Amended, and Passed as Introduced"),
            say(lang, "nums.ch_pass_said",
                "Stacked bar chart: of the bills that passed both chambers in each term, the share "
                "amended on the way and the share passed as introduced. The figures are in the table "
                "below."), lang, 0,
            say(lang, "nums.ch_pass_p", "The figure at the end of each bar is the share amended."))
    out.append("<h2>" + say(lang, "nums.h_passed", "What Passed, and How It Changed on the Way") + "</h2><p>"
               + say(lang, "nums.p_passed",
                     "Every House and Senate bill that passed both chambers in the same text and so "
                     "went to the governor, by term. Amended: either chamber adopted an amendment to "
                     "it first, or a committee of conference settled the two chambers' versions; the "
                     "Enrolled Bills Committee's technical corrections after passage are not counted "
                     "as amendments. The four columns on the right are the number of amendments the two "
                     "chambers adopted to each bill before it went to the governor: an amendment "
                     "withdrawn or defeated after its adoption does not count, nor does a committee of "
                     "conference's report. From 2007 every adoption the docket records carries the "
                     "amendment's number. Before 1999 it rarely does, and each amendment a line names "
                     "counts once, so the terms marked * are the figures to read with care.") + "</p>"
               + (("<p>" + say(lang, "nums.p_passed2",
                               "Across all {terms} terms, {pct} of the {n} bills that passed both "
                               "chambers were amended or went to conference, and {none} took no "
                               "amendment at all.", terms=len(parows), pct=_pct(all_amended, all_n),
                               n=f"{all_n:,}", none=_pct(all_d[0], all_n)) + "</p>") if all_n else "")
               + passed_chart
               + wide(_table([say(lang, "nums.c_term", "Term"), say(lang, "nums.c_both", "Passed both chambers"),
                              say(lang, "nums.c_amended", "Amended"),
                              say(lang, "nums.c_conf", "To a committee of conference"),
                              say(lang, "nums.c_none", "None"), say(lang, "nums.c_one", "One"),
                              say(lang, "nums.c_two", "Two"), say(lang, "nums.c_threeplus", "Three or more")],
                             parows)))

    # 10. How the votes were taken, by year.
    kinds = defaultdict(Counter)
    for t in recent:
        for rec in narr_all.get(t, {}).values():
            for e in rec.get("events") or []:
                if e.get("type") != "floor" or not (e.get("date") or "")[:4].isdigit():
                    continue
                vk = (e.get("vote_kind") or "").upper()
                raw = (e.get("raw") or "") + " " + (e.get("action") or "")
                if not vk:
                    vk = "RC" if re.search(r"\bRC\b", raw) else "DV" if re.search(r"\bDV\b|division", raw, re.I) \
                        else "VV" if re.search(r"\bVV\b", raw) else ""
                if vk in ("RC", "DV", "VV"):
                    kinds[e["date"][:4]][vk] += 1
    krows = []
    for y in sorted(kinds):
        c = kinds[y]
        n = sum(c.values())
        krows.append([y, f"{n:,}", _pct(c["RC"], n), _pct(c["DV"], n), _pct(c["VV"], n)])
    votes_chart = ""
    if len(krows) > 1:
        votes_chart = stack100_chart(
            [(y, [kinds[y]["RC"], kinds[y]["DV"], kinds[y]["VV"]]) for y in sorted(kinds)],
            [("pine", say(lang, "nums.c_rc", "Roll call")), ("ink", say(lang, "nums.c_div", "Division")),
             ("rest", say(lang, "nums.c_voice", "Voice"))],
            say(lang, "nums.ch_votes_h", "How Floor Decisions Were Taken, by Year"),
            say(lang, "nums.ch_votes_said",
                "Stacked bar chart: for each year, the share of recorded floor decisions taken by roll "
                "call, by division and by voice vote. The figures are in the table below."), lang, 0,
            say(lang, "nums.ch_votes_p", "The figure at the end of each bar is the share by roll call."))
    out.append("<h2>" + say(lang, "nums.h_votes", "How the Votes Were Taken") + "</h2><p>"
               + say(lang, "nums.p_votes",
                     "Every recorded floor decision, by year and by "
                     "how it was decided: a roll call records each member by name, a division records "
                     "the count, and a voice vote records only which side sounded louder.") + "</p>"
               + _table([say(lang, "nums.c_year", "Year"), say(lang, "nums.c_floor", "Floor decisions"),
                         say(lang, "nums.c_rc", "Roll call"), say(lang, "nums.c_div", "Division"),
                         say(lang, "nums.c_voice", "Voice")], krows))

    # 11. The closest roll calls of the current term.
    close = []
    for bid, rows_ in (rollcalls.get(current) or {}).items():
        for r in rows_ or []:
            y, n = r.get("yeas"), r.get("nays")
            if not isinstance(y, int) or not isinstance(n, int) or r.get("procedural"):
                continue
            if needs_more_than_majority(bid, r):
                continue
            if y + n < (100 if r.get("body") == "H" else 10):
                continue
            close.append((abs(y - n), bid, r))
    close.sort(key=lambda x: (x[0], x[1]))
    crow = [[_bill_link(current, b, str(r.get("year") or "")), _chamber(r.get("body"), lang),
             _en(E(r.get("question_plain") or r.get("question") or ""), lang),
             f"{r['yeas']}&ndash;{r['nays']}", _day(r.get("date") or "", lang)]
            for _m, b, r in close[:10]]
    out.append("<h2>" + say(lang, "nums.h_closest", "The Closest Votes of {term}", term=_t(current))
               + "</h2><p>" + say(lang, "nums.p_closest", "The ten "
                                  "roll calls on bills decided by the fewest votes, procedural motions and votes "
                                  "that needed more than a majority left out.") + "</p>"
               + _table([say(lang, "nums.c_bill", "Bill"), say(lang, "nums.c_chamber", "Chamber"),
                         say(lang, "nums.c_question", "Question"),
                         say(lang, "nums.c_yn", "Yeas&ndash;nays"), say(lang, "nums.c_date", "Date")], crow))

    # 12. Attendance on roll-call days.
    votes = _need(root / "data" / "member_votes.json", "attendance on roll-call days")
    if votes:
        att = attendance(votes)
        arows = []
        for t in terms:
            h, s = att.get((t, "H")), att.get((t, "S"))
            if not (h or s):
                continue
            arows.append([_t(t)] + [x for v in (h, s) for x in
                                    ((f"{v[0]:,}", f"{100 * v[1]:.1f}%") if v else ("", ""))])
        out.append("<h2>" + say(lang, "nums.h_attend", "Attendance on Roll-Call Days") + "</h2><p>"
                   + say(lang, "nums.p_attend",
                         "For each day a chamber took at least "
                         "one roll call, the share of its members in office who were there for at "
                         "least one of that day's roll calls &mdash; voting, presiding, or declaring a "
                         "conflict of interest &mdash; averaged over the days. Members' ballots are on "
                         "record from 1999, and a day with only voice or division votes records no one "
                         "by name, so it cannot be counted.") + "</p>"
                   + dot_chart([(_t(t), 100 * att[(t, "H")][1] if att.get((t, "H")) else None,
                                 100 * att[(t, "S")][1] if att.get((t, "S")) else None)
                                for t in terms if att.get((t, "H")) or att.get((t, "S"))],
                               say(lang, "nums.ch_att_h", "Attendance by Term, House and Senate"),
                               say(lang, "nums.ch_att_said",
                                   "Dot plot: for each term, the average share of each chamber present on "
                                   "its roll-call days. The figures are in the table below."), lang,
                               say(lang, "nums.ch_att_p", "The scale starts above zero, at the lowest "
                                   "attendance shown, so the dots can be told apart."))
                   + _table([say(lang, "nums.c_term", "Term"),
                             say(lang, "nums.c_h_days", "House roll-call days"),
                             say(lang, "nums.c_h_att", "House attendance"),
                             say(lang, "nums.c_s_days", "Senate roll-call days"),
                             say(lang, "nums.c_s_att", "Senate attendance")], arows))

    # 14. Constitutional amendments sent to the voters.
    ballot = _need(root / "corrections" / "ballot_results.json", "the amendments sent to the voters")
    if ballot:
        shown, held, to_come = ballots(ballot.get("rows"))
        # A DECIDED ROW WITH NO SOURCE OR NO CITE is left off and said here,
        # in the build's log, not to the reader.
        HELD.extend(f"{r.get('bill')} of {r.get('term')}: ballot_results.json gives it no "
                    + " and no ".join(k for k in ("source", "cite") if not r.get(k))
                    for r in held)
        brows = []
        for r in shown:
            y, n = r["yes"], r["no"]
            brows.append([f'{_bill_link(r["term"], r["bill"])}<br>{_t(r["term"])}', _day(r["election"], lang),
                          f"{y:,}", f"{n:,}",
                          (f"{_pct(y, y + n)}{yes_bar(100 * y / (y + n), lang)}", f"{100 * y / (y + n):.1f}"),
                          # the result in the status chip's colours: law's
                          # green, a death's red (chips.json's classes)
                          # THE ONE CHIP (Polish 1's step 3), in Title Case as
                          # the D18 card chips say it ("Not Ratified").
                          (components.chip(say(lang, "nums.ratified", "Ratified"), f"cstat {CHIP['law']}")
                           if ratified(y, n)
                           else components.chip(say(lang, "nums.not_ratified", "Not Ratified"),
                                                f"cstat {CHIP['done']}")),
                          f'<a href="{E(r["source"])}" rel="noopener">{_en(E(r["cite"]), lang)}</a>'])
        rat = sum(1 for r in shown if ratified(r["yes"], r["no"]))
        # WHOSE COUNT, FROM THE ROWS (ballot_source.py): the Secretary of
        # State for every one since 7 October 2026, and said by the rows, so
        # that a row with another source makes the sentence say so.
        whose = Counter(_whose(r, lang) for r in shown)
        if len(whose) == 1:
            said = say(lang, "nums.count_one", "Yes and No are {whose} statewide count, printed where the "
                       "Source column says.", whose=next(iter(whose)))
        else:
            said = (say(lang, "nums.count_many", "Yes and No are the statewide count printed where the "
                        "Source column says: {list}.",
                        list=", ".join(say(lang, "nums.name_for", "{name} for {k}", name=name, k=k)
                                       for name, k in whose.most_common())))
        # An election still to come, in the tense the build's day gives it:
        # once the day has passed and the row has no count yet, the page says
        # the count is not here rather than that the vote is ahead.
        day = build_date.today().isoformat()
        coming = "".join(
            " " + say(lang, "nums.goes", "{bill} of {term} goes to the voters on {day}.",
                      bill=_bill_link(r['term'], r['bill']), term=_t(r['term']),
                      day=_day(r['election'], lang)) if r["election"] >= day else
            " " + say(lang, "nums.went", "{bill} of {term} went to the voters on {day}, and their "
                      "count is not on this site yet.",
                      bill=_bill_link(r['term'], r['bill']), term=_t(r['term']),
                      day=_day(r['election'], lang)) for r in to_come)
        out.append("<h2>" + say(lang, "nums.h_cacr", "Constitutional Amendments Sent to the Voters")
                   + "</h2><p>" + say(
                       lang, "nums.p_cacr",
                       "A constitutional "
                       "amendment that passes both chambers by three fifths goes to the voters at the "
                       "next general election, and is ratified only with two thirds of the votes cast "
                       "on it (Part Second, Article 100); a blank ballot is not a vote cast on it.")
                   + " " + said + " " + say(lang, "nums.rat_of", "{rat} of the {n} below were ratified.",
                                            rat=rat, n=len(shown)) + coming + "</p>"
                   + wide(_table([say(lang, "nums.c_amend", "Amendment"), say(lang, "nums.c_election", "Election"),
                                  say(lang, "nums.c_yes", "Yes"), say(lang, "nums.c_no", "No"),
                                  say(lang, "nums.c_yes_share", "Yes share"),
                                  say(lang, "nums.c_result", "Result"), say(lang, "nums.c_source", "Source")],
                                 brows, cls="numtab amend", numcols=(4,))))
    return "".join(out)
