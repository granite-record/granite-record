#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-14.2
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
what period, and how. Where a section needs something this disk does not hold -- the Secretary
of State's certified results for constitutional amendments that reached the ballot, and the
person's check that the most-attended hearings are not simply the most polarizing bills -- it
says so and waits, rather than filling the gap.
"""

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)


def _load(p, default):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _pct(n, d):
    return f"{100 * n / d:.1f}%" if d else "&mdash;"


def _table(head, rows, cls="numtab"):
    return (f'<div class="tablewrap"><table class="{cls}"><thead><tr>'
            + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
            + "</tbody></table></div>")


def _t(term):
    return E(term).replace("-", "&ndash;")


YEAR = {}   # (term, bill) -> filing year, from the index; filled by body()


def _bill_link(term, bid, year=None):
    y = year or YEAR.get((term, bid)) or term.split("-")[0]
    shown = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", bid)
    return f'<a href="bill/{E(y)}/{E(bid.lower())}">{E(shown)}</a>'


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


def body(site=Path("site"), root=Path(".")):
    idx = _load(Path(site) / "index.json", [])
    narr_all = _load(Path(root) / "narratives.json", {})
    rollcalls = _load(Path(root) / "rollcalls.json", {})
    YEAR.update({(r.get("term"), r.get("id")): str(r.get("year") or "") for r in idx})
    terms = sorted({r.get("term") for r in idx if r.get("term")})
    current = terms[-1] if terms else ""
    recent = terms[-10:]
    # The page carried a "Draft" banner here saying it was unlinked and asking
    # search engines not to list it. Both of those stopped being true on 17
    # September, when the person read it and asked for it to be public, and a
    # banner that describes the page's old status is worse than none.
    #
    # What survives is the half of it that is still the point: every number
    # here is counted from the record at build time. That is what separates
    # this page from a statistics page somebody typed, and it is the first
    # thing a reader should know.
    out = ['<p class="caveat">Every number on this page is counted from the '
           'General Court\'s own record when the site is built, not typed in. '
           'Each section says what it counts and over what period. Where the '
           'record on this site cannot answer something, the section says so '
           'rather than estimating.</p>']

    # 1. Committees overruled on the floor.
    narr = narr_all.get(current, {})
    st, cases = overturned(narr)
    name = {"H": "House", "S": "Senate"}
    label = {"PASS": "pass", "KILL": "kill", "STUDY": "interim study"}
    rows = []
    for ch in ("H", "S"):
        d, a, s = st.get(ch, (0, 0, 0))
        rows.append([name[ch], f"{d:,}", f"{a} ({_pct(a, d)})", f"{s} ({_pct(s, d)})"])
    out.append(f"<h2>How often the full chamber overrules its committee</h2>"
               f"<p>In the {_t(current)} term, a committee's recommendation "
               "was followed by the chamber far more often than not. Counted here: each bill's "
               "committee report in each chamber, against the first motion adopted on that "
               "chamber's floor that decided the bill there &mdash; ought to pass, inexpedient to "
               "legislate or indefinite postponement, or interim study.</p>"
               + _table(["Chamber", "Recommendations decided on the floor", "Decided otherwise",
                         "Passage and kill reversed"], rows))
    if cases:
        items = "".join(f"<li>{_bill_link(current, b)} &mdash; {name[c]}: committee "
                        f"{label[r]}, floor {label[f]}</li>" for b, c, r, f in sorted(cases)[:60])
        out.append(f"<details><summary>The {len(cases)} bills</summary><ul class=\"numlist\">"
                   f"{items}</ul></details>")

    # 2. Vetoes, of the bills that reached the governor.
    vrows = []
    for t in recent:
        rs = [r for r in idx if r.get("term") == t]
        st_ = Counter(r.get("status") for r in rs)
        failed, over, pending = (st_["Vetoed, override failed"], st_["Veto overridden, became law"],
                                 st_["Vetoed"])
        vetoed = failed + over + pending
        # Only the current term can still be waiting. A veto of a finished
        # term that no override vote reached stood, as build_civics counts it.
        if t != current:
            failed, pending = failed + pending, 0
        reached = st_["Signed into law"] + st_["Became law unsigned"] + vetoed
        vrows.append([_t(t), f"{reached:,}", f"{vetoed} ({_pct(vetoed, reached)})",
                      str(failed), str(over), str(pending) if pending else ""])
    out.append("<h2>Vetoes</h2><p>Of the bills that reached the governor in each of the last ten "
               "terms, how many were vetoed, and what became of the veto. A bill that became "
               "law without a signature reached the governor and was not vetoed.</p>"
               + _table(["Term", "Reached the governor", "Vetoed", "Veto stood",
                         "Overridden", "Awaiting"], vrows))

    # 3. How the votes were taken, by year.
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
    out.append("<h2>How the votes were taken</h2><p>Every recorded floor decision, by year and by "
               "how it was decided: a roll call records each member by name, a division records "
               "the count, and a voice vote records only which side sounded louder.</p>"
               + _table(["Year", "Floor decisions", "Roll call", "Division", "Voice"], krows))

    # 4. The closest roll calls of the current term.
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
    crow = [[_bill_link(current, b, str(r.get("year") or "")), name.get(r.get("body"), ""),
             E(r.get("question_plain") or r.get("question") or ""), f"{r['yeas']}&ndash;{r['nays']}",
             E(r.get("date") or "")] for _m, b, r in close[:10]]
    out.append(f"<h2>The closest votes of {_t(current)}</h2><p>The ten "
               "roll calls on bills decided by the fewest votes, procedural motions and votes "
               "that needed more than a majority left out.</p>"
               + _table(["Bill", "Chamber", "Question", "Yeas&ndash;nays", "Date"], crow))

    # 5. Consent calendar share by committee.
    by_c = defaultdict(lambda: [0, 0])
    rows_by = {r.get("id"): r for r in idx if r.get("term") == current}
    for bid, rec in narr.items():
        row = rows_by.get(bid) or {}
        ev = rec.get("events") or []
        off = {e.get("body") for e in ev if e.get("type") == "consent_off"}
        for e in ev:
            if e.get("type") != "report" or (e.get("raw") or "").lower().startswith("minority"):
                continue
            ch = e.get("body")
            word = "House " if ch == "H" else "Senate "
            cm = next((c for c in row.get("committees") or [] if c.startswith(word)), "")
            if not cm:
                continue
            by_c[cm][0] += 1
            if re.search(r"\bCC\b", e.get("raw") or "") and ch not in off:
                by_c[cm][1] += 1
    ccrows = sorted(([E(c), f"{n:,}", f"{k:,}", _pct(k, n)] for c, (n, k) in by_c.items() if n >= 10),
                    key=lambda r: -float(r[3].rstrip("%")) if r[3].endswith("%") else 0)
    out.append(f"<h2>Consent calendars, by committee</h2><p>A committee sends a report to the "
               "consent calendar by its own vote, and in both chambers that vote must be unanimous, "
               "though the recommendation itself may have been carried on a divided one. The "
               "whole calendar is adopted in one vote without debate, and what it adopts is each "
               "committee's recommendation, to pass the bill, to kill it, or to send it to interim "
               "study, unless the bill is first taken off &mdash; since January 2023 at the request "
               "of ten members in the House, and since April 2026 of two in the Senate. "
               f"For each committee of {_t(current)} "
               "with ten reports or more: the share that went on the consent calendar and stayed "
               "there &mdash; a measure of how often the committee agreed with itself.</p>"
               + _table(["Committee", "Reports", "On consent and kept there", "Share"], ccrows))

    # 6. Laws without a signature.
    urows = []
    for t in recent:
        rs = [r for r in idx if r.get("term") == t]
        laws = sum(1 for r in rs if r.get("kind") == "law")
        unsigned = sum(1 for r in rs if r.get("status") == "Became law unsigned")
        urows.append([_t(t), f"{laws:,}", f"{unsigned} ({_pct(unsigned, laws)})"])
    out.append("<h2>Laws without the governor's signature</h2><p>A bill the governor neither "
               "signs nor vetoes within five days, Sundays excepted, becomes law without a "
               "signature &mdash; unless the legislature's adjournment prevents its return, and "
               "then it does not become law (Part Second, Article 44).</p>"
               + _table(["Term", "Laws", "Without a signature"], urows))

    out.append("<h2>Still to come</h2><ul>"
               "<li>The constitutional amendments that reached the voters, with the results the "
               "Secretary of State certified &mdash; read from the Secretary of State and kept "
               "with their sources, since the results are not in this record.</li>"
               "<li>The hearings with the most sign-ins, as counts only, once checked against "
               "being simply a list of the most polarizing bills.</li>"
               "<li>Bills passed as introduced against those amended, and how many amendments a "
               "bill takes before it passes; each committee's passage rate.</li></ul>")
    return "".join(out)
