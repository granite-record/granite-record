#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.29
"""
Write a real HTML page for every bill.

    python3 build_bill_pages.py --site site

Three problems, one solution.

SEARCH. The interactive page addresses a bill as bills.html#HB1442. A crawler
cannot see a fragment, so no bill on this site is indexable and a search for
"NH HB 1442" will never lead here. A page per bill at its own URL, with a title
and description, is the difference between being found and being told about.

ACCESSIBILITY. These pages need no JavaScript. Everything is real markup: the
timeline is a list, the votes are tables, party is carried by text and not only
by colour. Whatever renders here works in a screen reader.

PROVENANCE. Every block says where it came from and links the official record.
A journalist writing "according to Granite Record" should be able to follow any
number on the page back to the General Court in one click.

Writes site/bill/<id>.html, plus sitemap.xml and robots.txt.
"""

import argparse
import html
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

E = html.escape

GC_DOCKET = ("https://gc.nh.gov/bill_status/legacy/bs2016/bill_docket.aspx"
             "?lsr={lsr}&sy={yr}&txtsessionyear={yr}&txtbillnumber={bill}"
             "&sortoption=billnumber")

PARTY = {"R": "Republican", "D": "Democrat", "I": "Independent",
         "L": "Libertarian", "X": "not on file"}

VOTE_LABEL = {"Yea": "Yes", "Nay": "No", "Presiding": "Presiding",
              "Not Voting/Excused": "Excused", "Not Voting/Not Excused": "Absent"}


def fdate(d):
    if not d or len(d) < 10:
        return d or ""
    y, m, dd = d[:4], d[5:7], d[8:10]
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    try:
        return f"{months[int(m) - 1]} {int(dd)}, {y}"
    except (ValueError, IndexError):
        return d


def hms(s):
    s = int(s)
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def vote_tables(rc):
    """Party breakdown as a table, then the full roll.

    A chart alone fails a screen reader and a colour-blind reader both. The
    numbers are here as text; the interactive page may draw them as well.
    """
    members = rc.get("members") or []
    if not members:
        kind = rc.get("vote_kind_label") or "voice vote"
        return (f'<p class="src">Decided on a {E(kind)}. Only the outcome was '
                "recorded — there is no count of how any member voted.</p>")

    parties, states = {}, []
    for m in members:
        p = m.get("p") or "X"
        v = m.get("v") or ""
        parties.setdefault(p, {}).setdefault(v, 0)
        parties[p][v] += 1
        if v not in states:
            states.append(v)
    order = ["Yea", "Nay", "Presiding", "Not Voting/Excused",
             "Not Voting/Not Excused"]
    cols = [s for s in order if s in states] + [s for s in states if s not in order]

    head = "".join(f"<th>{E(VOTE_LABEL.get(c, c))}</th>" for c in cols)
    rows = ""
    for p in sorted(parties, key=lambda x: -sum(parties[x].values())):
        cells = "".join(f"<td>{parties[p].get(c, 0)}</td>" for c in cols)
        rows += f"<tr><th scope=\"row\">{E(PARTY.get(p, p))}</th>{cells}</tr>"
    totals = "".join(f"<td>{sum(v.get(c, 0) for v in parties.values())}</td>"
                     for c in cols)
    rows += f'<tr><th scope="row">Total</th>{totals}</tr>'

    def roll(state):
        names = sorted(m["n"] for m in members if m.get("v") == state)
        if not names:
            return ""
        return (f'<details><summary>{E(VOTE_LABEL.get(state, state))} '
                f'— {len(names)}</summary><ul class="roll">'
                + "".join(f"<li>{E(n)}</li>" for n in names)
                + "</ul></details>")

    return (f'<table class="votes"><caption class="sr">Votes by party</caption>'
            f'<thead><tr><th scope="col">Party</th>{head}</tr></thead>'
            f"<tbody>{rows}</tbody></table>"
            + "".join(roll(c) for c in cols))


def page(b, d, generated):
    bid = b["id"]
    title = b.get("title") or ""
    n = b.get("n") or bid
    desc = (f"{n}, {title} " if title else f"{n}. ")
    desc = re.sub(r"\s+", " ", desc)[:180].strip()
    desc += f" Status: {b.get('status','')}. Sponsors, votes, hearings and the full record."

    # A plain table of what the General Court states about this bill. Every
    # value here is quoted from its status page rather than worked out.
    LABELS = [("gen_status", "Status"), ("house_status", "In the House"),
              ("senate_status", "In the Senate"),
              ("date_introduced", "Introduced"), ("floor_date", "Floor date"),
              ("lsr", "LSR number"), ("chapter", "Chapter"),
              ("local", "Local government impact"),
              ("committee_code", "Committee code")]
    f = dict(d.get("facts") or {})
    if d.get("chapter"):
        f["chapter"] = d["chapter"]
    rows_f = "".join(
        f'<tr><th scope="row">{E(lab)}</th><td>'
        + ("yes" if k == "local" and f[k] == "Y" else
           "no" if k == "local" and f[k] == "N" else E(f[k]))
        + "</td></tr>"
        for k, lab in LABELS if f.get(k))
    facts_block = (
        f'<h2>On the record</h2><p class="src">Quoted from the General Court '
        f"bill status page, not worked out from the docket.</p>"
        f'<table class="facts"><tbody>{rows_f}</tbody></table>'
        + (f'<p style="margin-top:10px"><a href="{E(d["text_pdf"])}" '
           'rel="noopener">Bill text (PDF) &#8599;</a></p>'
           if d.get("text_pdf") else "")) if rows_f else ""

    src = ""
    if d.get("docket_url"):
        src = (f'<a class="official" href="{E(d["docket_url"])}" rel="noopener">'
               "Official record at gencourt.state.nh.us &#8599;</a>")

    def cite(e):
        if e.get("cite_url"):
            return (f' <a class="cite" href="{E(e["cite_url"])}" rel="noopener">'
                    f'{E(e["cite"])} &#8599;</a>')
        return f' <span class="cite">{E(e["cite"])}</span>' if e.get("cite") else ""

    timeline = "".join(
        f'<li><span class="d">{E(fdate(e["date"]))}</span>'
        f'<span>{E(e.get("text") or "")}{cite(e)}</span></li>'
        for e in (d.get("events") or []))

    # Sponsors grouped by chamber, the originating one first, exactly as the
    # card shows them. The origin comes from the prime sponsor's own seat: a
    # concurrent resolution's number does not say which chamber it started in.
    sp_all = d.get("sponsors") or []
    nsp = len(sp_all)
    ch_of = lambda s: str(s.get("chamber") or "").upper()[:1]
    sp_prime = next((s for s in sp_all if s.get("prime")), sp_all[0] if sp_all else {})
    origin = ch_of(sp_prime) or ("S" if bid.upper().startswith("S") else "H")
    CHNAME = {"H": "Representatives", "S": "Senators"}

    def sp_name(s):
        who = E(s.get("display_full") or s.get("label") or s.get("name", ""))
        return f"<b>{who}</b>" if s.get("prime") else who

    def sp_block(ch, label=None):
        group = [s for s in sp_all if ch_of(s) == ch] if ch else [
            s for s in sp_all if ch_of(s) not in ("H", "S")]
        if not group:
            return ""
        return (f'<h3 class="spgrp">{label or CHNAME[ch]} '
                f'<span>{len(group)}</span></h3><p>'
                + ", ".join(sp_name(s) for s in group) + "</p>")

    # A count per party and nothing said about it, sorted by party code so the
    # order is fixed rather than a ranking by size.
    pc = Counter(str(s.get("party") or "").upper()[:1] for s in sp_all)
    pc.pop("", None)
    sp_party = " \u00b7 ".join(f"{pc[k]} {k}" for k in sorted(pc))
    sponsors = ("" if not sp_all else
                f'<p class="spcount">{nsp} sponsor{"" if nsp == 1 else "s"}'
                + (f" \u00b7 {sp_party}" if sp_party else "") + "</p>"
                + sp_block(origin) + sp_block("S" if origin == "H" else "H")
                + sp_block(None, "Chamber not on file"))

    votes = ""
    for rc in (d.get("rollcalls") or []):
        # Which amendment the vote was on, where the docket named it.
        amd = (f' <span class="ramd">{E(rc["amendment"])}</span>'
               if rc.get("amendment") else "")
        votes += (
            f'<section class="rc"><h3>{E(rc.get("question") or "Vote")}{amd}</h3>'
            f'<p class="meta">{E(fdate(rc.get("date")))} · '
            f'{"House" if rc.get("body") == "H" else "Senate"} · '
            f'<b>{rc.get("yeas", 0)}&#8211;{rc.get("nays", 0)}</b>, '
            f'{"adopted" if rc.get("passed") else "failed"}</p>'
            + (f'<p class="note">{E(rc["threshold_note"])}</p>'
               if rc.get("threshold_note") else "")
            + vote_tables(rc) + "</section>")
    if not votes:
        votes = ('<p class="src">No roll call votes on this bill. Where a chamber '
                 "acts by voice or division vote, no record exists of how "
                 "individual members voted.</p>")

    # Statutes cited in the committee's own words become links, substituted
    # after escaping and longest first so "RSA 91-A" cannot eat the front of
    # "RSA 91-A:4".
    _rsa_map = d.get("rsa") or {}

    # One pass. Replacing in sequence rescans what it has already written, so
    # "RSA 91-A" matched inside the anchor just built for "RSA 91-A:4".
    def rsa(s):
        if not _rsa_map:
            return s
        pat = re.compile("|".join(re.escape(k) for k in
                                  sorted(_rsa_map, key=len, reverse=True)))
        return pat.sub(lambda m: f'<a href="{E(_rsa_map[m.group(0)])}" '
                                 f'rel="noopener" class="rsa">'
                                 f'{E(m.group(0))}</a>', s)

    # Amendments, in the docket's order. A committee amendment is considered
    # before any floor amendment, and where two change the same section the
    # later one governs, so the sequence is not rearranged.
    AVK = {"VV": "voice vote", "DV": "division vote", "RC": "roll call"}
    # Applied after escaping, so the brackets are the document's own and not
    # markup that arrived with the text.
    CUT_RE = re.compile(r"\[([^\]]{1,400})\]")

    def cut(m):
        return (f'<del class="cut" title="removed by this amendment">'
                f'{m.group(1)}</del>')

    amds = d.get("amendments") or []
    namd = len(amds)
    if amds:
        rows = ""
        for x in amds:
            who = x.get("mover") or x.get("proposed_by") or ""
            state = ("adopted" if x.get("adopted") is True
                     else "rejected" if x.get("adopted") is False else "")
            when = fdate(x.get("date")) if x.get("date") else ""
            vk = AVK.get(x.get("vote_kind") or "")
            body = (f'<details class="amdtext"><summary>Read the amendment'
                    f'</summary><p class="report">'
                    f'{CUT_RE.sub(cut, rsa(E(x["text"])))}</p>'
                    '<p class="src">Text in [brackets] is being removed. Text '
                    "being added is underlined in the original, and underlining "
                    "is lost when a PDF is read as text, so additions are not "
                    "marked here."
                    + (f' From {E(x["source"])}.' if x.get("source") else "")
                    + "</p></details>"
                    if x.get("text") else
                    '<p class="src">The text is not in the calendars this site '
                    "has read. It was moved on the date above and the docket "
                    "records the outcome.</p>")
            tgts = "".join(f'<span class="tgt">{E(v)}</span>'
                           for v in (x.get("targets") or []))
            sup = "; ".join(f'{E(s["num"])} ({", ".join(E(y) for y in s["shared"])})'
                            for s in (x.get("supersedes") or []))
            extra = ((f'<p class="amdt">Changes {tgts}</p>' if tgts else "")
                     + (f'<p class="amdsup">Later than {sup}, so where they '
                        "change the same thing this one governs.</p>"
                        if sup else ""))
            rows += (f'<section class="amd"><h3>{E(x["num"])} '
                     f'<span class="amdk">{E(x.get("kind") or "Amendment")}</span>'
                     + (f' <span class="bstat s-{"law" if state == "adopted" else "done"}">'
                        f'{state}</span>' if state else "")
                     + f'</h3><p class="meta">{E(when)}'
                     + (f" &middot; {E(vk)}" if vk else "")
                     + (f" &middot; {E(who)}" if who else "")
                     + f"</p>{extra}{body}</section>")
        amend_block = ('<p class="src">In the order the docket took them up. A '
                       "committee amendment is considered before any floor "
                       "amendment, and where two change the same section the "
                       "later one governs.</p>" + rows)
    else:
        amend_block = '<p class="src">No amendments on this bill.</p>'

    # The bill as published. The version label leads, because "as introduced"
    # and "as amended by the House" are different laws.
    bt = d.get("billtext") or {}
    if bt.get("body"):
        inc = ", ".join(E(x["num"]) for x in (bt.get("in_text") or []))
        btext_block = (
            f'<p class="btver"><span class="btv">'
            f'{E(bt.get("version") or "Version not stated")}</span>'
            + (f' <span class="btamd">includes {inc}</span>' if inc else "")
            + "</p>"
            + (f'<div class="btan"><h3>Analysis</h3><p class="report">'
               f'{rsa(E(bt["analysis"]))}</p>'
               '<p class="src">Written by the General Court, not by this '
               "site.</p></div>" if bt.get("analysis") else "")
            + '<h3>The bill</h3><p class="src">Text in [brackets] is being '
              "removed from current law. Text being added is printed in bold "
              "italics in the original, and that formatting is lost when the "
              "page is read as text, so additions are not marked here.</p>"
              f'<p class="billbody">'
              f'{CUT_RE.sub(cut, rsa(E(bt["body"])))}</p>')
    else:
        btext_block = ('<p class="src">The text of this bill has not been read '
                       "into this site yet. The Documents section links to it "
                       "on the General Court's own site.</p>")

    nrep = sum(len(r.get("reports") or []) for r in (d.get("reports") or []))
    nvotes = len(d.get("rollcalls") or [])
    # The same links the card's Documents tab shows, said the same way.
    DOCWHAT = {"text": "the bill as it currently stands",
               "status": "the page this site takes a bill's status from",
               "docket": "every recorded action, in the General Court's own words",
               "record": "the official record of one action",
               "report": "the calendar a committee report was printed in"}
    docs = d.get("documents") or []
    docs_block = ("<ul class=\"docs\">" + "".join(
        f'<li class="doc"><a href="{E(x["url"])}" rel="noopener">{E(x["label"])}</a>'
        f'<span>{E(DOCWHAT.get(x.get("kind"), ""))}</span></li>' for x in docs)
        + "</ul>") if docs else (
        '<p class="src">No official documents on file for this bill yet.</p>')

    # Committee reports, in the order they were signed, with the Senate's
    # beside the House's. What each of the four sections below is used to be
    # unsayable: the record's calendar and the reporting committee were both
    # dropped here, so a bill a committee reported twice printed two headings
    # reading "Majority" and "Minority" twice over with nothing between them.
    acts = {}
    for a in (d.get("report_actions") or []):
        acts.setdefault(a["before"], []).append(a)

    def between(key):
        return "".join(
            '<p class="src">Between these reports the docket records, on '
            f'{E(fdate(a["date"]))}: <em>{E(a["text"])}</em></p>'
            for a in acts.get(key, []))

    def head(r, cmte, body):
        # The day the committee signed, where the docket states it; the day the
        # calendar carrying the report was published, where it does not.
        when = E(fdate(r.get("date"))) if r.get("date") else ""
        if when and r.get("dated") == "printed":
            when += " <span class=\"src\">as printed</span>"
        cite = E(r.get("source") or r.get("cite") or "")
        if cite and r.get("cite_url"):
            cite = f'<a href="{E(r["cite_url"])}" rel="noopener">{cite}</a>'
        bits = [x for x in (" ".join(y for y in (body, cmte) if y), cite) if x]
        return (f'<h3 class="rephead">{when}</h3>'
                f'<p class="meta">{" &#183; ".join(bits)}</p>' if when or bits else "")

    reports = ""
    for r in (d.get("reports") or []):
        # The committee's vote goes beside the label it is a vote on, matching
        # the search page. Where the committee split, the two numbers are the
        # two sides; where one report was filed, the whole tally belongs to it.
        divided = bool(r.get("minority_recommendation"))
        tally = next((x for x in (r.get("reports") or [])
                      if x.get("vote_yeas") is not None), None)
        inner = (r.get("reports") or [])
        reports += between(r.get("date") or "")
        reports += head(r, (inner[0] or {}).get("committee", ""), "House")
        for e in inner:
            rec = (r.get("minority_recommendation") if e.get("side") == "Minority"
                   else r.get("majority_recommendation")) or ""
            y = e.get("vote_yeas", (tally or {}).get("vote_yeas"))
            nn = e.get("vote_nays", (tally or {}).get("vote_nays"))
            vote = ""
            if y is not None and nn is not None:
                vote = (f' <span class="cvote">'
                        f'{nn if e.get("side") == "Minority" else y}</span>'
                        if divided else
                        f' <span class="cvote">{y}–{nn}</span>')
            reports += (f'<section><h4>{E(e.get("side",""))}{vote}'
                        + (f" &#8212; {E(rec)}" if rec else "") + "</h4>"
                        f'<p class="meta">{E(e.get("author",""))}</p>'
                        f'<p class="report">{rsa(E(e.get("text","")))}</p></section>')

    # Reports the docket records that no calendar on file printed. Nearly all
    # are the Senate's, which reports a bill once with a vote and no minority
    # and publishes no reasoning -- so this is the whole of a Senate report,
    # and on 319 bills it is the only report there is.
    for r in (d.get("docket_reports") or []):
        reports += between(r.get("date") or "")
        reports += head(r, r.get("committee", ""),
                        "Senate" if r.get("body") == "S" else "House")
        y, nn = r.get("vote_yeas"), r.get("vote_nays")
        vote = (f' <span class="cvote">{y}–{nn}</span>'
                if y is not None and nn is not None else "")
        amd = (f' Amendment {E(r["amendment"])}'
               + (", with a new title." if r.get("new_title") else ".")
               if r.get("amendment") else "")
        said = ("The Senate reports a bill once, with the committee’s vote and "
                "no minority report, and does not publish the written reasoning "
                "the House prints in its calendar."
                if r.get("body") == "S" else
                "The calendar carrying this report has not been read into the "
                "site yet, so only what the docket states is shown.")
        reports += (f'<section><h4>{E(r.get("side") or "Committee")}{vote}'
                    + (f" &#8212; {E(r.get('recommendation',''))}"
                       if r.get("recommendation") else "") + "</h4>"
                    f'<p class="src">{amd} {said}</p></section>')

    if reports:
        reports = ('<p class="src">The recommendation, the vote and the day it '
                   "was signed come from the docket; the reasoning, where there "
                   "is any, is reproduced from the House Calendar in the "
                   "committee’s own words.</p>" + reports)

    hearings = ""
    for s in (d.get("stations") or []):
        line = f'{E(fdate(s.get("when")))}'
        if s.get("time"):
            line += f' at {E(s["time"])}'
        what = " ".join(x for x in [s.get("committee"), s.get("what")] if x)
        link = ""
        # "stated" is "located" with the boundary in the chair's own words.
        # These pages tested only "located", so the 3,829 best-evidenced
        # proceedings on the site showed "start time not identified yet" on
        # the page a search engine indexes and a shared link lands on.
        if s.get("state") in ("located", "stated") and s.get("start") is not None:
            span = (f'{hms(s["start"])}\u2013{hms(s["end"])}'
                    if s.get("end") and s["end"] > s["start"]
                    else f'from {hms(s["start"])}')
            # Guard on the seconds. round() on a sub-30-second span gives 0,
            # and "about 0 min" beside a real range reads as broken.
            _span = (s["end"] - s["start"]) if (s.get("end")
                     and s["end"] > s["start"]) else 0
            # Decide on the rounded value, not on a threshold: a 30-second
            # span is >= 30 but round(0.5) is 0 under banker's rounding, so a
            # seconds threshold still printed "about 0 min".
            _m = round(_span / 60)
            mins = (f', about {_m} min' if _m >= 1
                    else (f', about {round(_span)} sec' if _span > 0 else ""))
            # "(estimated)" is wrong on a span whose start the chair announced.
            # The tolerance says everything the reader needs; where it came
            # from is a methodology question, not a caption.
            tol = s.get("tolerance") or 300
            prov = (f"\u00b1{round(tol)} sec" if s.get("start_stated")
                    else f"estimated, \u00b1{max(1, round(tol / 60))} min")
            link = (f' <a href="https://www.youtube.com/watch?v={E(s["video_id"])}'
                    f'&t={int(s["start"])}s" rel="noopener">recording {span}</a>'
                    f'{mins} ({prov})')
        elif (s.get("state") in ("floor_precise", "floor_stated")
              and s.get("debate_end")):
            # Where the clerk took it up, if that was heard; the window is
            # the previous bill's roll call and can be half an hour earlier.
            _at = (int(s["debate_start"]) if s.get("debate_start") is not None
                   else max(int(s.get("window_start") or 0) - 60, 0))
            link = (f' <a href="https://www.youtube.com/watch?v={E(s["video_id"])}'
                    f'&t={_at}s" rel="noopener">floor recording</a>')
        elif s.get("state") == "floor_dated" and s.get("debate_start") is not None:
            # A voice or division vote leaves no roll call to time the end, but
            # the clerk still opened the item and the marker pass heard it.
            link = (f' <a href="https://www.youtube.com/watch?v={E(s["video_id"])}'
                    f'&t={int(s["debate_start"])}s" rel="noopener">floor'
                    f' recording from {hms(s["debate_start"])}</a>'
                    " — no roll call to time the end")
        elif s.get("state") == "consent":
            # Nothing to find. Telling a reader to scrub a nine-hour session for
            # a bill that was adopted in a block and never read out sends them
            # looking for something that is not in the recording.
            link = (f' <a href="https://www.youtube.com/watch?v={E(s["video_id"])}"'
                    " rel=\"noopener\">the session</a> — adopted with the consent"
                    " block, so it was never taken up separately")
        elif s.get("video_id"):
            # The recording is offered whether or not its timestamp is known.
            # Pinning down start times is ongoing work, and a proceeding with a
            # recording and no time is still a proceeding somebody can watch.
            link = (f' <a href="https://www.youtube.com/watch?v={E(s["video_id"])}"'
                    " rel=\"noopener\">recording</a> — start time not identified"
                    " yet, so scrub to find it")
        elif s.get("state") == "prestream":
            link = " — no recording; hearings were not streamed before 2020"
        hearings += f'<li><span class="d">{line}</span><span>{E(what)}{link}</span></li>'

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(n)} — {E(title[:90])} | Granite Record</title>
<meta name="description" content="{E(desc)}">
<link rel="canonical" href="/bill/{b.get("year","")}/{bid.lower()}.html">
<link rel="alternate" type="application/rss+xml" title="{E(n)} updates"
 href="/feed/bill/{b.get("year","")}/{bid.lower()}.xml">
<meta property="og:type" content="article">
<meta property="og:title" content="{E(n)} — New Hampshire General Court">
<meta property="og:description" content="{E(desc)}">
<link rel="stylesheet" href="../../style.css">
<style>
.wrap{{max-width:820px}}
.tl{{list-style:none;padding:0;margin:0}}
.tl li{{display:flex;gap:14px;padding:7px 0;border-bottom:1px solid var(--rule)}}
.tl .d{{flex:0 0 150px;color:var(--ink-3);font-size:13px}}
.cite{{font-size:12px;color:var(--ink-3);white-space:nowrap}}
a.cite{{color:var(--pine)}}
.votes{{width:100%;border-collapse:collapse;margin:10px 0;font-size:14px}}
.votes th,.votes td{{padding:7px 10px;border-bottom:1px solid var(--rule);text-align:right}}
.votes th[scope=row]{{text-align:left}}
.votes thead th{{text-align:right;color:var(--ink-3);font-size:12.5px}}
.rc{{border:1px solid var(--rule);border-radius:8px;padding:14px 16px;margin:0 0 14px;background:var(--surface)}}
.rc h3{{margin:0 0 4px;font-size:15px}}
.meta{{font-size:13px;color:var(--ink-2);margin:0 0 8px}}
.report{{font-family:var(--serif);font-size:16px;line-height:1.62}}
/* One committee report, headed by the day it was signed. Nine bills on this
   site were reported twice by the same committee and printed two blocks a
   reader could not tell apart, because neither the date nor the calendar
   reached the page. */
.rephead{{margin:22px 0 2px;font-size:15px;border-top:1px solid var(--rule);
padding-top:12px}}
#reports h4{{margin:14px 0 2px;font-size:14px}}
.facts{{width:auto;border-collapse:collapse;font-size:14px;margin:8px 0}}
.facts th,.facts td{{padding:6px 16px 6px 0;border-bottom:1px solid var(--rule);
text-align:left;vertical-align:top}}
.facts th{{color:var(--ink-3);font-weight:500;white-space:nowrap}}
.roll{{columns:2;font-size:13px;margin:8px 0 0;padding-left:18px}}
details{{margin:6px 0}}summary{{cursor:pointer;font-size:13.5px;color:var(--pine)}}
.src{{font-size:12.5px;color:var(--ink-3);background:var(--paper);
border-left:3px solid var(--rule-2);padding:9px 13px;margin:0 0 14px}}
.official{{display:inline-block;font-size:13.5px;margin:0 0 16px}}
.ramd{{font-weight:400;color:var(--ink-2);background:var(--wash);
border-radius:5px;padding:1px 7px}}
.cvote{{font-size:14px;font-weight:600;font-variant-numeric:tabular-nums;
color:var(--ink-2);background:var(--wash);border-radius:5px;padding:1px 7px}}
.billhead{{border-bottom:1px solid var(--rule);padding-bottom:16px}}
.crumb{{margin:0 0 10px;font-size:13.5px}}
.crow{{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap}}
.cnum{{font-size:15px;font-weight:600;color:var(--pine)}}
.cyear{{font-size:12.5px;color:var(--ink-3)}}
.bstat{{margin-left:auto;font-size:14px;font-weight:600;padding:4px 13px;
border-radius:20px;white-space:nowrap;background:var(--wash);color:var(--ink-2)}}
.s-active{{background:#FBF2D9;color:#7A5A00}}
.s-law{{background:#E3EFE7;color:#1E5B3C}}
.s-done{{background:#FAE7E5;color:#9E2B25}}
.s-study{{background:#FCEEDF;color:#94500E}}
.s-adopted{{background:#E3EFE7;color:#1E5B3C}}
.s-veto{{background:#F7E4E7;color:#7C2D3A}}
.billhead h1{{font-size:21px;line-height:1.35;margin:8px 0 4px}}
/* A strip of anchors, not tabs. The sections stay in the page, so the whole
   bill is still one document for a crawler, a screen reader and Ctrl-F --
   which is the entire reason these pages exist. */
.tabsx{{position:sticky;top:0;z-index:5;background:var(--paper);display:flex;
gap:18px;flex-wrap:wrap;border-bottom:1px solid var(--rule);padding:11px 0;
margin:0 0 20px;font-size:13.5px}}
.tabsx a{{color:var(--ink-2);text-decoration:none;padding:3px 0;
border-bottom:2px solid transparent}}
.tabsx a:hover,.tabsx a:focus{{color:var(--ink);border-bottom-color:var(--pine)}}
section[id]{{scroll-margin-top:64px}}
section[id] h2{{margin-top:28px}}
.statusbox{{margin:0 0 18px;padding:13px 15px;border-radius:7px;
background:var(--wash);border-left:3px solid var(--rule-2)}}
.statusbox.s-active{{background:#FBF2D9;border-left-color:#7A5A00}}
.statusbox.s-law{{background:#E3EFE7;border-left-color:#1E5B3C}}
.statusbox.s-done{{background:#FAE7E5;border-left-color:#9E2B25}}
.statusbox.s-study{{background:#FCEEDF;border-left-color:#94500E}}
.statusbox.s-adopted{{background:#E3EFE7;border-left-color:#1E5B3C}}
.statusbox.s-veto{{background:#F7E4E7;border-left-color:#7C2D3A}}
.statusbox .lab{{font-size:11.5px;font-weight:600;letter-spacing:.02em;
text-transform:uppercase;color:var(--ink-2)}}
.statusbox .val{{font-size:16px;margin-top:2px}}
.statusbox .src2{{font-size:12px;color:var(--ink-3);margin-top:4px}}
.rsa{{white-space:nowrap}}
.btver{{margin:0 0 12px}}
.btv{{font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;
background:var(--pine-soft);color:var(--pine);border-radius:5px;padding:3px 9px}}
.btamd{{font-size:13px;color:var(--ink-3)}}
.btan{{background:var(--wash);border-radius:8px;padding:13px 15px;margin:0 0 18px}}

.billbody{{font-family:var(--serif);font-size:16px;line-height:1.7;
white-space:pre-wrap}}
.amd{{margin:18px 0 0}}
.amdt{{font-size:13px;color:var(--ink-2);margin:6px 0 0}}
.tgt{{display:inline-block;background:var(--wash);border-radius:5px;
padding:1px 7px;margin-right:4px;font-size:12.5px}}
.amdsup{{font-size:13px;color:var(--ink-2);margin:5px 0 0;
border-left:2px solid var(--rule-2);padding-left:9px}}
.cut{{text-decoration:line-through;color:var(--ink-3)}}
.amd h3{{display:flex;gap:9px;align-items:baseline;flex-wrap:wrap}}
.amdk{{font-weight:400;font-size:13px;color:var(--ink-2)}}
.amdtext summary{{font-size:14px;color:var(--pine);cursor:pointer}}
.spcount{{font-size:14px;color:var(--ink-2);margin:0 0 12px}}
/* One section heading for every section of a bill page, matching the card. */
.spgrp,.btan h3,.amd h3,section[id] h3{{font-size:14px;font-weight:600;
color:var(--ink-2);letter-spacing:.05em;text-transform:uppercase;
margin:20px 0 7px;padding-bottom:6px;border-bottom:1px solid var(--rule)}}
.spgrp span,.amd h3 span{{font-weight:400;letter-spacing:0;text-transform:none;
font-size:13px;color:var(--ink-3)}}
.docs{{list-style:none;margin:0;padding:0}}
.doc{{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;padding:8px 0;
border-bottom:1px solid var(--rule);font-size:15px}}
.doc span{{font-size:12.5px;color:var(--ink-3)}}
.sr{{position:absolute;left:-9999px}}
/* Focus must be visible. Keyboard users navigate by it, and the default
   outline is removed by most resets without anything put back. */
:focus-visible{{outline:2px solid var(--pine);outline-offset:2px;border-radius:3px}}
.skip{{position:absolute;left:-9999px;top:0;background:var(--pine);color:#fff;
padding:10px 16px;z-index:99;border-radius:0 0 6px 0}}
.skip:focus{{left:0}}
/* These pages link style.css and then add this block, so anything declared
   here beats the narrow-screen rules in style.css no matter what the media
   query says -- same specificity, later in the document. Three of those rules
   were being silently thrown away on every phone, and one of them was making
   things worse rather than merely not helping:

     .tl .d{{flex:0 0 150px}}  in a column-direction flex container, a
                              flex-basis is a HEIGHT. Stacking the timeline
                              rows turned every date into a 150px-tall block.
     .roll{{columns:2}}        two columns of names on a 380px screen.
     .cite{{white-space:nowrap}} citations could not wrap, so they ran off
                              the side of the page.

   So the overrides are repeated here, where they can actually win. */
@media (max-width: 720px){{
  .tl li{{flex-direction:column;gap:2px;padding:10px 0}}
  .tl .d{{flex:none;font-weight:600}}
  .cite{{white-space:normal}}
  .roll{{columns:1}}
  .votes th,.votes td{{padding:6px 8px;font-size:13px}}
  .facts th,.facts td{{padding:6px 10px 6px 0}}
  .meta,.src,.cite,summary{{font-size:13px}}
  summary{{min-height:44px;display:flex;align-items:center}}
}}
/* Reduced motion: honour the system preference rather than overriding it. */
@media (prefers-reduced-motion: reduce){{
  *{{animation-duration:.01ms !important;transition-duration:.01ms !important}}
}}
.corrections{{font-size:12.5px;color:var(--ink-3);margin-top:10px}}
.corrections a{{color:var(--pine)}}


/* ---- narrow screens ---------------------------------------------------
   Most people arrive from a search result on a phone. Three things break at
   380px, and each is fixed by reflowing rather than by horizontal scrolling,
   which on a civic site reads as "not meant for you".
     1. The facet sidebar sits beside the results; it has to stack.
     2. Timeline rows use a fixed date column that leaves no room for text.
     3. Vote tables and member lists are wider than the screen.
   Nothing is hidden at any width.                                        */
@media (max-width: 720px){{
  .wrap,.in{{padding-left:14px;padding-right:14px}}
  h1{{font-size:24px;line-height:1.2}}
  h2{{font-size:18px}}
  .shell{{display:block}}
  .facets{{position:static;max-height:none;width:auto;margin:0 0 20px;
          border-right:none;border-bottom:1px solid var(--rule);padding-bottom:14px}}
  .fbody{{max-height:210px}}
  .tl li{{flex-direction:column;gap:2px;padding:10px 0}}
  .tl .d{{flex:none;font-weight:600}}
  .cite{{white-space:normal}}
  table{{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch}}
  .votes th,.votes td{{padding:6px 8px;font-size:13px}}
  .roll,.chosen{{columns:1}}
  .grid{{grid-template-columns:1fr}}
  .tabs{{flex-wrap:wrap;gap:4px}}
  .tabs button{{font-size:13px;padding:6px 10px}}
  .searchrow{{flex-direction:column;align-items:stretch;gap:8px}}
  .searchbig{{flex-direction:column}}
  .searchbig button{{padding:11px 20px}}
  #year{{width:100%}}
  .qhint{{flex-wrap:wrap;gap:8px}}
  .crow{{flex-wrap:wrap;gap:4px}}
  .cnum{{font-size:15px}}
  .pbar{{flex-wrap:wrap;gap:6px}}
  .pbar .jump{{font-size:12px}}
  .twoup{{grid-template-columns:1fr}}
  .entry{{grid-template-columns:1fr}}
  .statgrid{{grid-template-columns:1fr 1fr}}
  nav.top .in{{flex-wrap:wrap;gap:10px 14px;padding-top:10px;padding-bottom:10px}}
  nav.top a{{font-size:13.5px}}
  button,.hit,summary,nav.top a{{min-height:36px}}
}}
@media (max-width: 420px){{
  .statgrid{{grid-template-columns:1fr}}
  .plegend{{gap:8px;font-size:12px}}
}}

</style></head><body>
<a class="skip" href="#main">Skip to the content</a>
<nav class="top"><div class="in"><span class="brand">Granite Record</span>
<a href="../../index.html">Home</a><a href="../../bills.html">Bills</a>
<a href="../../legislators.html">Legislators</a>
<a href="../../learn.html">How it works</a><a href="../../about.html">About</a>
</div></nav>
<div class="wrap" id="main">
<p style="font-size:13px;margin:20px 0 0"><a href="../../bills.html">All bills</a></p>
<div class="billhead">
<p class="crumb"><a href="../../bills.html#{bid}">&#8592; Back to bill search</a></p>
<div class="crow"><span class="cnum">{E(n)}</span>
<span class="cyear">filed {b.get('year','')}</span>
<span class="bstat s-{E(b.get('kind','active'))}">{E(b.get('status',''))}</span></div>
<h1>{E(title)}</h1>
<p class="meta">{E(b.get('sponsor_label') or b.get('sponsor',''))}
{"".join(f" &middot; {E(c)}" for c in (b.get('committees') or ([b['committee']] if b.get('committee') else [])))}
{f" &middot; {E(b.get('topic',''))}" if b.get('topic') else ""}</p>
{src}
</div>

<nav class="tabsx" aria-label="Sections of this bill">
<a href="#timeline">Summary</a>
{'<a href="#billtext">Bill text</a>' if bt.get("body") else ""}
<a href="#votes">Votes{f" ({nvotes})" if nvotes else ""}</a>
<a href="#hearings">Videos</a>
<a href="#reports">Committee reports{f" ({nrep})" if nrep else ""}</a>
<a href="#amendments">Amendments{f" ({namd})" if namd else ""}</a>
<a href="#sponsors">Sponsors{f" ({nsp})" if nsp else ""}</a>
<a href="#documents">Documents{f" ({len(docs)})" if docs else ""}</a>
</nav>

<div class="statusbox s-{E(b.get('kind','active'))}">
<div class="lab">Current status</div>
<div class="val">{E(d.get('next_step',''))}</div>
<div class="src2">{E(d.get('status_source',''))}</div></div>
{"".join(f'<p class="note">{E(x)}</p>' for x in (d.get("notes") or []))}

{facts_block}

{f'<section id="billtext"><h2>Bill text</h2>{btext_block}</section>'
 if bt.get("body") else ""}

<section id="timeline"><h2>Summary</h2>
<p class="src">Every action recorded in the official docket, in order. Each line
ends with the journal or calendar that recorded it; where we have the document,
that citation links to it.</p>
<ul class="tl">{timeline or '<li>No recorded action.</li>'}</ul></section>

<section id="votes"><h2>Votes</h2>
<p class="src">Roll call tallies and individual votes from the General Court roll
call files, in the order the docket records them. Presiding, excused and absent
are shown separately: one member presides over each House roll call and does not
vote except to break a tie.</p>
{votes}</section>

<section id="hearings"><h2>Videos</h2>
<p class="src">Recordings are the General Court&#8217;s own, on YouTube. Where a
start time is known it carries its tolerance; where it is not, the recording is
still here and the start time is work in progress.</p>
<ul class="tl">{hearings or '<li>No proceedings on file.</li>'}</ul></section>

<section id="reports"><h2>Committee reports</h2>
{reports or '<p class="src">No committee report on file. A report is recorded in the docket when a committee reports the bill out, and the written reasoning behind it is printed in the House Calendar; neither has happened here yet.</p>'}</section>

<section id="amendments"><h2>Amendments</h2>
{amend_block}</section>

<section id="sponsors"><h2>Sponsors</h2>
{sponsors or '<p>None on file.</p>'}
{'<p class="src">Prime sponsor in bold. From the General Court sponsor file.</p>' if sponsors else ""}</section>

<section id="documents"><h2>Documents</h2>
{docs_block}</section>

<p><a href="../../feed/bill/{b.get("year","")}/{bid.lower()}.xml">Follow this bill
by RSS</a> &nbsp;&middot;&nbsp; <a href="../../bills.html#{bid}">Open it in the
searchable view &#8594;</a></p>

<p class="src" style="margin-top:26px">Page generated {E(generated)} from data
published by the New Hampshire General Court. Granite Record is an independent
project, not affiliated with the General Court. The official record always takes
precedence. Corrections: corrections@graniterecord.org</p>
</div>
<footer><div class="in">Built from public records published by the New Hampshire
General Court. Not affiliated with the General Court.
<a href="../../about.html">How this is made</a>.</div></footer>
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--base", default="https://graniterecord.org")
    a = ap.parse_args()
    site = Path(a.site)
    idx = json.loads((site / "index.json").read_text(encoding="utf-8"))
    out = site / "bill"
    out.mkdir(parents=True, exist_ok=True)
    generated = date.today().isoformat()

    # The year is part of the path because bill numbers are only unique within a
    # term. Once earlier sessions are backfilled there really is an HB 84 in
    # several of them, and /bill/hb84.html could only ever point at one.
    written, missing, noyear = 0, 0, 0
    urls = []
    for b in idx:
        f = site / "bills" / f"{b['id']}.json"
        if not f.exists():
            missing += 1
            continue
        yr = str(b.get("year") or "")
        if not yr:
            noyear += 1
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        (out / yr).mkdir(parents=True, exist_ok=True)
        (out / yr / f"{b['id'].lower()}.html").write_text(
            page(b, d, generated), encoding="utf-8")
        urls.append(f"{a.base}/bill/{yr}/{b['id'].lower()}.html")
        written += 1
        if written % 500 == 0:
            print(f"  {written:,}...", flush=True)

    for p in ("index.html", "bills.html", "legislators.html", "towns.html",
              "learn.html", "about.html"):
        if (site / p).exists():
            urls.append(f"{a.base}/{p}")

    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{E(u)}</loc><lastmod>{generated}</lastmod></url>\n"
                  for u in urls)
        + "</urlset>\n", encoding="utf-8")
    (site / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {a.base}/sitemap.xml\n",
        encoding="utf-8")

    total = sum(p.stat().st_size for p in out.rglob("*.html"))
    print(f"\n{written:,} bill pages -> {out}/  ({total/1e6:.1f} MB)")
    if missing:
        print(f"{missing:,} bills had no detail file and were skipped")
    if noyear:
        print(f"{noyear:,} bills had no filing year and were skipped \u2014 the year "
              "is part of the URL, so a bill without one cannot be addressed")
    years = sorted({u.split("/bill/")[1].split("/")[0] for u in urls
                    if "/bill/" in u})
    if years:
        print("years: " + ", ".join(years))
    print(f"sitemap.xml: {len(urls):,} URLs")
    print(f"robots.txt points crawlers at {a.base}/sitemap.xml")
    print("\nThese pages need no JavaScript, which is what makes them both "
          "crawlable and screen-reader friendly.")


if __name__ == "__main__":
    main()
