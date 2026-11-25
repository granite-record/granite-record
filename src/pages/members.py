#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.5
"""
A member of the General Court as the site has them: how a member is named,
the roll calls and the floor as a member's record reads them, and the
members' own files -- the sitting members, the former members and their
seats, attendance, and the officers.

    import members as MEM
    MEM.member_labels("Nelson, Jodi", chamber="H", party="R", district="13", county="Rockingham")
    MEM.member_slug(m, labels)       # "jodi-nelson-rock-13"
    MEM.person_name("Nelson, Jodi")  # "Jodi Nelson"
    MEM.write_rollcall_index(out, rollcalls, cards, nobill)   # site/rollcalls_index.json
    MEM.build_legislators(...)       # the legislator pages' files, former members among them

In the file's order:

  - NAMING A MEMBER: the one way of naming one (member_labels: "Rep. Jodi
    Nelson", with the party and the seat), the address of their page
    (member_slug, own_slug), and the names a record prints read into one form
    (person_name, sort_name, name_key, roster_name_keys);
  - THE ROLL CALLS AND THE FLOOR as a member's record reads them: a ballot's
    date and place in a service (vote_date, service_order), the one index of
    every roll call (write_rollcall_index), the seats a term's ballots and
    printed record give (term_seats, printed_record), and what the session-day
    step needs of the floor (write_floor_record);
  - THE MEMBERS: former members and the addresses their pages have had
    (former_roster, keep_moved, last_term_labels), attendance
    (attendance_context, member_attendance), the officers and the legislator
    pages' files (build_officers, build_legislators).

SECTIONS OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: names and slugs; roll-call and floor
records; members, former members and attendance). They moved here as they
stood, comments and all, in the file's order; the import of parts.py's
district tag that stood in the naming is at the head here instead, and the
cards of a vote on no bill (write_nobill_cards), which the bill's own code
draws, stayed. This imports no builder (_import_cycles_cut). build_site_v2
imports every name here back under its own, so build_site_v2.member_labels,
build_site_v2.build_legislators and the rest answer as they did, for the
bills' sponsors and votes, main and the checks.
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import bill_order as BO
import build_date
import entities as EN
import member_figures as MF
import member_links as ML
import motions as MO
import names as NM
import proceedings as P
import state_settings as ST
import vote_passage as VP
# The words the pages say, src/pages/words/: here, the vote words.
from components import WORDBOOK as _WORDBOOK
# The district a label carries (district_tag) is parts.py's, which officials_tabs reads too.
from parts import district_tag
# The Speaker's chair, whose occupant's page names the office (member_office).
from seating import SPEAKER_SEAT


def sitting_labels(m):
    """A roster member's labels as their own page gives them (build_legislators
    and own_slug make them so): the Sponsor filter's list labels a member no
    bill names this way (sponsor_roster.add_sitting)."""
    return member_labels(m.get("name"), chamber=m.get("chamber"),
                         party=m.get("party_code") or m.get("party"),
                         district=m.get("district"), county=m.get("county"),
                         county_abbr=m.get("county_abbr"))


_OWN_SLUG = {}


def own_slug(m):
    """The address of this member's OWN page, built the way that page is.

    NOT member_slug(m, whatever_label_is_to_hand). member_slug takes the name
    out of the label it is given, and a sponsor's label is deliberately the
    seat and the name AS THE RECORD PRINTED THEM AT THE TIME -- so a 2009 bill
    naming "Patrick Long, Hills 10" produced patrick-long-sd-20 for a senator
    whose page is pat-long-sd-20, because the roster spells him Pat. A link to
    a file that does not exist.

    It has been right for everyone else by coincidence: Cindy Rosenwald and
    Mark McConkey are spelled the same way in a 2009 bill's text as in today's
    roster, so the name the label carried happened to be the name the page was
    built from. Pat Long is the first case where the two differ, and the
    mechanism was wrong for all of them.

    So the slug comes from the member's own roster row, through the same
    member_labels call build_legislators makes, which is what guarantees the
    two agree. Cached because a sponsor list asks for it 68,930 times.
    """
    mid = str(m.get("id") or "")
    if not mid:
        return ""
    if mid not in _OWN_SLUG:
        lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                            party=m.get("party_code") or m.get("party"),
                            district=m.get("district"), county=m.get("county"),
                            county_abbr=m.get("county_abbr"))
        _OWN_SLUG[mid] = m.get("slug") or member_slug(m, lab)
    return _OWN_SLUG[mid]


def member_slug(m, lab):
    """jodi-nelson-rock-13, debra-altschiller-sd-24.

    Computed here so the search page and the static page agree on the address
    without either having to guess.

    House districts are numbered within a county -- Rockingham 13 and
    Hillsborough 13 are different places -- so the county has to be in the
    address. Senate districts are numbered once across the state, so the number
    is already unique. Both are geographic; only the numbering differs.
    """
    name = re.sub(r"^(?:Rep|Sen)\.\s+", "",
                  lab.get("display_plain") or m.get("name", ""))
    if "," in name:
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    senate = str(m.get("chamber", "")).upper().startswith("S")
    where = "sd" if senate else (m.get("county_abbr") or m.get("county") or "")
    s = unicodedata.normalize("NFKD", f"{name} {where} {m.get('district','')}")
    s = s.encode("ascii", "ignore").decode()
    return re.sub(r"-{2,}", "-", re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")).lower()


# ------------------------------------------------------------------ naming --
# One way of naming a member, used everywhere the site refers to one.
#
#     display_plain   Rep. Jodi Nelson
#     display         Rep. Jodi Nelson (R)
#     display_full    Rep. Jodi Nelson (R - Rock. 13)
#                     Sen. Debra Altschiller (D - SD24)
#
# Three forms rather than one because a party letter beside a name that already
# sits next to a party colour chip reads as a stutter. The page picks the form
# that fits what is already on screen; nothing downstream has to split strings
# apart to get there.
#
# The honorific comes from the CHAMBER, not from a member's `title` field. That
# field can hold "Speaker" or "President", and this is a consistent way of
# referring to somebody rather than a statement of their highest office.
#
# The party letter is DROPPED rather than guessed when it is not known, and the
# district with it. A member resolved from a roll call page may have neither,
# and "(?)" beside a name is worse than a name on its own. A House district
# with no county is likewise omitted: "Rock. 13" locates a seat, "13" does not.
HONORIFIC = {"H": "Rep.", "S": "Sen."}

_TITLE_RE = re.compile(r"^(?:rep|sen|representative|senator)\.?\s+", re.I)
# The party letters a name's tail and a label keep: the parties the state's one table has a
# word for (R, D, I and L; state_settings.party_initials).
PARTY_INITIALS = ST.party_initials()
# Case-insensitive: the bill status page writes the letter in lower case,
# so "Howard Pearl (r)" kept its tail, sorted as "(r), howard pearl" and
# matched nobody on the roster. 112 sponsor rows, all his.
_PARTY_TAIL_RE = re.compile(r"\s*\([" + re.escape(PARTY_INITIALS) + r"](?:\s*[-\u2013][^)]*)?\)\s*$", re.I)
# build_data.py's "label" field is a composite -- "Nelson, Jodi(R) Rock. 13" --
# with the party letter in the MIDDLE and the seat after it. Nothing here is
# fed that field any more, but a formatter that mangles its input silently is
# worse than one that guards against it: this cuts at the party marker
# wherever it appears. No real name contains "(R)".
_COMPOSITE_RE = re.compile(r"\s*\([" + re.escape(PARTY_INITIALS) + r"]\)\s.*$")
# A generational suffix, as the rosters write one.
_SUFFIX_RE = re.compile(r"(?:Jr|Sr)\.?|II|III|IV|V", re.I)
_PLACEHOLDER_RE = re.compile(r"^(?:Member\s*#|\(unknown)", re.I)


def person_name(raw):
    """"Nelson, Jodi" -> "Jodi Nelson".

    Idempotent: run it on something already formatted and the honorific and
    party letter are stripped before being put back, so nothing can ever read
    "Rep. Rep. Jodi Nelson (R) (R)".
    """
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = _COMPOSITE_RE.sub("", _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", s)))
    if "," in s:
        parts = [x.strip() for x in s.split(",") if x.strip()]
        if len(parts) == 2:
            s = f"{parts[1]} {parts[0]}"
        elif len(parts) > 2:
            # "Smith, John, Jr." - the suffix belongs at the end, not the middle.
            # AND WHEREVER THE RECORD PUT IT: "Barnes, Jr., John" was drawn
            # "Sen. Jr. Barnes John" on his page and in every list (found by
            # the former members' directory, 12 October 2026). A part that is
            # a suffix goes last, whichever comma it followed.
            suf = [p for p in parts[1:] if _SUFFIX_RE.fullmatch(p)]
            rest = [p for p in parts[1:] if not _SUFFIX_RE.fullmatch(p)]
            s = " ".join([*rest, parts[0], *suf])
    return s.strip()


def sort_name(raw):
    """Surname first, for the lists that are read alphabetically."""
    s = re.sub(r"\s+", " ", (raw or "").strip())
    s = _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", s))
    if "," in s:
        return s.lower()
    bits = s.split()
    return f"{bits[-1]}, {' '.join(bits[:-1])}".lower() if len(bits) > 1 else s.lower()


def name_key(raw):
    """("rebecca", "kwoka") -- a member's first and last word, either way round.

    sort_name treats the final word as the surname, which is right until a
    surname has more than one word in it. "Rebecca Perkins Kwoka" becomes
    "kwoka, rebecca perkins" while the roster holds "Perkins Kwoka, Rebecca",
    and the two never meet. The same for "Sabourin dit Choiniere" and for the
    particle in "de Vries" -- 217 sponsor rows across four members, drawn
    without the district everybody else has beside their name.

    Taking the first word and the last word sidesteps the split entirely: both
    spellings of a name yield the same pair however many words sit between
    them. It is a weaker key than a surname, so it is tried only after
    sort_name has failed.
    """
    s = _PARTY_TAIL_RE.sub("", _TITLE_RE.sub("", re.sub(r"\s+", " ",
                                                        (raw or "").strip())))
    if "," in s:
        last, first = [x.strip() for x in s.split(",", 1)]
        s = f"{first} {last}"
    w = [x for x in re.sub(r"[^\w' -]", " ", s, flags=re.UNICODE).lower().split()
         if x]
    return (w[0], w[-1]) if len(w) >= 2 else None


def roster_name_keys(members):
    """(by sort_name, by name_key, clashes) for the sitting members.

    A name two members share (a father and a son in one chamber) would have
    gone to whichever came first in legislators.json, with setdefault, and
    linked a sponsor named by that alone to the wrong person (bug hunt of
    November 2026, #10). A key two members share is now left out of both
    maps, so the sponsor keeps a bare name, and is returned as
    [(which key, the key, [the members])] for the build to say aloud;
    preflight warns, naming both, on one in data/legislators.json."""
    by_sort, by_name, seen = {}, {}, {}
    for m in members:
        for how, book, k in (("sort name", by_sort, sort_name(m.get("name") or "")),
                             ("first and last word", by_name, name_key(m.get("name") or ""))):
            if how == "first and last word" and not k:
                continue
            seen.setdefault((how, k), []).append(m)
            book.setdefault(k, m)
    clashes = [(how, k, ms) for (how, k), ms in seen.items() if len(ms) > 1]
    for how, k, ms in clashes:
        (by_sort if how == "sort name" else by_name).pop(k, None)
    return by_sort, by_name, clashes


def member_labels(name, chamber=None, party=None, district=None, county=None,
                  county_abbr=None, label=None):
    who = person_name(label or name)
    if not who:
        return {"display_plain": "", "display": "", "display_full": "",
                "district_label": "", "sort": ""}
    if _PLACEHOLDER_RE.match(who):
        # A member the roster could not name. Calling that "Rep. Member #377204"
        # dresses up a gap as a person.
        return {"display_plain": who, "display": who, "display_full": who,
                "district_label": "", "sort": who.lower()}
    hon = HONORIFIC.get((chamber or "").strip().upper()[:1], "")
    plain = f"{hon} {who}".strip()
    pc = (party or "").strip()[:1].upper()
    p = pc if pc in PARTY_INITIALS else ""
    short = f"{plain} ({p})" if p else plain
    tag = district_tag((chamber or "").strip().upper()[:1], district, county,
                       county_abbr)
    if tag:
        full = f"{plain} ({p} - {tag})" if p else f"{plain} ({tag})"
    else:
        full = short
    return {"display_plain": plain, "display": short, "display_full": full,
            "district_label": tag, "sort": sort_name(label or name)}


def vote_date(s):
    """"8/19/2026" as something that sorts. Text does not.

    The docket writes m/d/Y with no padding, so a string sort puts August
    above December and 2023 above 2025. Every member page claimed "newest
    first" over that order.
    """
    p = (s or "").split("/")
    try:
        return (int(p[2]), int(p[0]), int(p[1]))
    except (IndexError, ValueError):
        return (0, 0, 0)


def service_order(v):
    """A ballot's place in a member's service: its term first, then its day.

    BY THE TERM BEFORE THE DAY (the deep walk of 6 November 2026). The day
    alone is the clerk's, and one is wrong: roll call 1999-S-109, CACR 17, is
    dated 22 October 2009 between two of 22 October 1999, the only one of
    2,303,047 ballots dated outside its term. Taken by the day, it was the
    last vote of every senator of 1999 who cast it. Frederick King's and Leo
    Fraser's one page was kept as the Senate's, though both sat in the House
    after; Frederick King's House address answered with a 301 to "Former Sen.
    Frederick King". And Carl Johnson's seat was taken from 1999-2000's bills
    (SD3), not from his last term's (SD2). The term is the roll call's, from
    its session year (proceedings.vote_term): 1999-2000 for 1999-S-109,
    whatever its day says."""
    return (P.vote_term(v.get("year", ""), v.get("date")), vote_date(v.get("date")))


def write_rollcall_index(out, rollcalls, cards=None, nobill=None):
    """One shared file describing all 1,504 roll calls.

    A legislator's page listed 1,081 rows of "HB2026 / Veto Override / Yea":
    no plain English for the question and no outcome. Everything needed to
    answer that is already built: rollcalls.json has the tallies, the
    plain-English question and the recorded outcome.

    THE PREVAILING SIDE, NOT A PARTY'S (the person, 23 October 2026: "I'd
    rather categorize votes by whether or not the member voted on the
    prevailing side of the motion since I don't want to label either party as
    taking a position on a bill"). The party split this file carried, from
    which the Votes tab said "voted with Republicans" or "against Democrats",
    is gone; what decides the side a member was on is `p`, the clerk's
    recorded outcome. And for the tab to draw a vote as its bill page does
    (option A of that day): `mk` and `mf`, the approved vote words' key and
    fill (motions.classify, as the bill record has them); `nd`, what the yes
    side had to reach; and `c`, where the roll call's card is on its bill's
    Votes tab, the index into that bill record's `rollcalls` (`cards`, which
    build_bills fills), so the ring and the members' names come from the bill
    record itself, fetched when a reader opens them.

    It is one file rather than a copy inside each of the 406 member files
    because the same roll calls describe all of them: repeated, it would add
    something over a hundred megabytes to the site; shared, it is fetched
    once, when a reader opens the Votes tab, and serves every member page
    after that. The bill's title is not in it at all -- the page already has
    the term's bill index loaded and can look the title up there.
    """
    ix = {}
    cards = cards or {}
    motions = _WORDBOOK["votes"]["motions"]
    for term, term_bills in rollcalls.items():
        for bid, rows in term_bills.items():
            for r in rows:
                # The same key main() builds votes_by_bill with. A vote
                # sequence number restarts each session, so the year and the
                # body are both part of naming one.
                key = f'{r.get("year")}-{r.get("body")}-{r.get("number")}'
                ix[key] = {
                    # The plain-English gloss, where the parser could make
                    # one. "OTPA" is the record's word and means nothing to
                    # anyone who has not read the manual; "pass the bill with
                    # changes" is the same fact in language a reader has.
                    "q": (r.get("question_plain") or "").strip(),
                    # The tallies as the source document gives them, not as
                    # summed from the member rows: the clerk's count is the
                    # count, and where the two disagree the clerk wins.
                    "y": r.get("yeas"), "n": r.get("nays"),
                    "p": 1 if r.get("passed") else 0,
                    "pr": 1 if r.get("procedural") else 0,
                }
                if r.get("threshold_note"):
                    ix[key]["tn"] = r["threshold_note"]
                # Where the clerk's record and the ballots disagree, the
                # member's Votes row says so, as the bill's vote card does.
                if r.get("outcome_conflict"):
                    ix[key]["oc"] = r["outcome_conflict"]
                k = MO.classify(r.get("question"), bid, r.get("body") or "", motions)
                if k.get("mk"):
                    ix[key]["mk"] = k["mk"]
                if k.get("mf"):
                    ix[key]["mf"] = k["mf"]
                if r.get("threshold_needed"):
                    ix[key]["nd"] = r["threshold_needed"]
                card = (cards.get(term) or {}).get(bid, {}).get(key)
                if card is not None:
                    ix[key]["c"] = card
                # A vote on no bill has its card in nobill/<term>.json
                # (write_nobill_cards): `c` is the index there and `ct` the
                # term, which a vote of Organization Day does not share with
                # its year.
                nb = ((nobill or {}).get(term) or {}).get(key) if bid == "_procedural" else None
                if nb is not None:
                    ix[key]["c"] = nb
                    ix[key]["ct"] = term
                # WHAT A VOTE ON NO BILL WAS ABOUT, in a few words (23 October
                # 2026): the one-line summary journal_motions.py wrote from the
                # Journal, or the kind of question, where its passage is shown
                # on the session day (vote_passage). One field, because every
                # visitor to a member page loads this file.
                if bid == "_procedural":
                    w = VP.short(VP.entry(key))
                    if w:
                        ix[key]["w"] = w

    f = out / "rollcalls_index.json"
    f.write_text(json.dumps(ix, separators=(",", ":"), sort_keys=True),
                 encoding="utf-8")
    print(f"{len(ix):,} roll calls -> {f.name} "
          f"({f.stat().st_size / 1024:,.0f} KB, read once per reader)")


# WHAT THE SESSION-DAY STEP NEEDS OF THE FLOOR THAT ONLY THIS STEP KNOWS:
# data/floor_record.json, read by build_session_pages.py (FLOOR_RECORD) for
# each chamber's term files of session days, and published by nothing.
#
#   presiding  {roll call: [[member id, label], ...]}: whom each roll call's
#              "Presiding" ballot names, labelled with the seat of the term
#              (term_seats), else the name alone. The record's word for who was
#              in the chair, ballot by ballot -- the person, 9 October 2026,
#              v18: "a general line naming the members who presided over the
#              chamber during the day" -- and never attendance_context's
#              reading of a day that names nobody, which is for counting a
#              member's attendance and not for saying who presided.
#   cards      {term: {bill: {roll call: card}}}: where each roll call's card
#              is on its bill's Votes tab (the bill record's `rollcalls`), so
#              a session day can point at the vote display that tab already
#              draws (v2: "keep the live site's vote display as it is").
#
# Not published: the session-day files carry what a page needs of it. It is
# this step's because the ballots are read here and nowhere after: the
# session-day step reading data/member_votes.json for itself would load
# 560 MB twice more a build to find a few thousand ballots.
FLOOR_RECORD = "floor_record.json"


def ballot_seat(v, body):
    """The member a ballot names, labelled with the seat they held when it
    was cast: the sitting roster's label as the ballot carries it ("Rep.
    Sherman Packard (R - Rock 3)" in 2010), or the former member's read off
    the ballot's own ("Sytek, Donna(R) Rock 26", FORMER_LABEL)."""
    lab = (v.get("label") or "").strip()
    if lab.startswith(("Rep. ", "Sen. ")):
        return lab
    m = FORMER_LABEL.search(lab)
    if m:
        return member_labels(v.get("name"), chamber=body, party=v.get("party"),
                             district=m.group("district").lstrip("0"),
                             county=m.group("county").strip())["display_full"]
    return member_labels(v.get("name"), chamber=body, party=v.get("party"))["display"]


def floor_moment(st):
    """A floor station's moment in its recording, as its bill's Hearings tab
    plays it (app.js renderHearings): {"d": the day, "b": "H" or "S", "v": the
    recording, "from": where the player opens, "end": the vote's or the
    chair's close, "stated": whether the opening is the clerk's own words},
    or None for a station with no recording, no moment, or the consent
    calendar's."""
    state = st.get("state") or ""
    if not st.get("video_id") or not str(st.get("what") or "").startswith("floor"):
        return None
    ws = st.get("window_start")
    if state in ("floor_precise", "floor_stated"):
        end = st.get("debate_end")
        if st.get("debate_start") is not None:
            frm = max(int(st["debate_start"]), 0)
        elif end is not None:
            frm = max(int(ws) if ws is not None else 0, int(end) - 600)
        else:
            return None
    elif state == "floor_dated" and st.get("debate_start") is not None:
        frm, end = max(int(st["debate_start"]), 0), None
    else:
        return None
    return {"d": st.get("when"), "b": "H" if st.get("committee") == "House" else "S",
            "v": st["video_id"], "from": frm,
            **({"end": int(end)} if end is not None else {}),
            "stated": st.get("debate_start") is not None, "s": state}


_SUFFIX = NM.SUFFIXES


def _surname(name):
    """The last word of a surname as a ballot ("McCarty, Winston", "Barnes,
    Jr., John") or a sponsor line ("McCarty", "K. Rice", "Fuller Clark",
    "John Barnes Jr.") gives it, a Jr. or a III not counted as one."""
    words = [w for w in str(name or "").split(",")[0].replace(".", " ").split()
             if w.lower() not in _SUFFIX]
    return words[-1].lower() if words else ""


def printed_record(path="text_sponsors.json"):
    """What the term's bills print about where members sat, from the sponsor
    lines text_sponsors.py read off each bill's own text:
      one   {(term, member id): (chamber, county, district)}: the one seat
            printed for a member it placed -- the rule
            build_data.date_ballot_seats already uses for the sitting members;
      two   {(term, member id)}: a member printed at two seats, so neither
            is proven;
      named {(term, chamber, surname): {(county, district)}}: the seats
            printed under a surname that text_sponsors could not place on
            anyone (1999 "Rep. McCarty, Hills 38") -- and not one it placed
            on a member of that surname elsewhere, which is that member's
            line printed once more. A seat placed on a namesake is the
            namesake's, and says nothing of this member (the second review
            of 5 November 2026: counting those refused 29 seats that were
            right, David Flanders's Rock 20 among them).
    Empty where the file is not here.

    READ FROM THE MODEL'S TENURES (18 November 2026, the refactor's model
    design, step 5): each seat is one of entities.printed_tenures, the
    tenures of the seats a term's bills print that build_entities puts in
    the model -- a member's, or a seat no one was placed on -- under every
    name the lines print it."""
    p = Path(path)
    try:
        text = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except ValueError:
        text = {}
    seen, loose, placed = defaultdict(set), defaultdict(set), defaultdict(set)
    for t in EN.printed_tenures(text, p.as_posix()):
        line, term = t["sponsor_line"], t["term"]
        s = (line["chamber"], line["county"], line["district"].lstrip("0"))
        for name in line["names"]:
            k = (term, s[0], _surname(name))
            if t.get("member_id"):
                seen[(term, t["member_id"])].add(s)
                placed[k].add(s[1:])
            else:
                loose[k].add(s[1:])
    one = {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}
    two = {k for k, v in seen.items() if len(v) > 1}
    named = {k: v - placed.get(k, set()) for k, v in loose.items() if v - placed.get(k, set())}
    return one, two, named


def printed_seats(path="text_sponsors.json"):
    """printed_record's `one`: the one seat a term's bills print for a member."""
    return printed_record(path)[0]


# The seat a label names: "Rep. Jane Doe (R - Hills 48)" -> "Hills 48", "(D - SD12)" -> "SD12".
_LABEL_SEAT = re.compile(r"\([A-Z] - (?P<seat>[^()]+)\)\s*$")


def seat_of_the_lines(term, label, index, held):
    """Whether the seat `label` names is a district of the lines `term` sat on (the district
    table's era of the term, entities.era_of): True where it is, and where those lines are not
    on file -- a term before 2013, or a kind the era's table lacks -- since then there is
    nothing to hold it to; False where the lines are on file and hold no such district (Hills 48
    in 2015-2016, on the 2012 lines, which number Hillsborough's districts to 45). `index` is
    entities.district_index of the table's districts, `held` its {(kind, era)}."""
    m = _LABEL_SEAT.search(label or "")
    if not m:
        return True
    seat = m.group("seat").strip()
    kind, era = ("senate" if re.fullmatch(r"SD\s*\d+", seat) else "house"), EN.era_of(term)
    if era is None or (kind, era) not in held:
        return True
    return bool(EN.resolve_district(index, kind, seat, era))


def term_seats(votes_by_member, printed=None, record=None, ballots=None, lines=None,
               refused=None):
    """{term: {member id: label}}: the seat each member held in each term --
    the label a session day of the term names them by (labels-use-the-seat-
    held-at-the-time; the person, 16 September 2026).

    THE SEAT A TERM'S BILLS PRINT, FIRST (5 November 2026). A ballot's label
    is not dated: a former member's is built from one record of their seat
    (build_data._former_label), the seat they last held, so Shannon Chandley
    read "Hills 22" on her 2009-2010 ballots, the seat she took in 2016, where
    every bill she sponsored in 2010 prints "Hills 6". Measured against the
    bills' sponsor lines, the ballots' seat was the printed one on 29-47% of
    member-years in 1999-2004 and 48-76% in 2005-2012. So:
      - where the term's bills print one seat for the member (`printed`,
        printed_seats), that seat;
      - else, in the member's last term in the record only, the seat their
        ballots give: today's roster for a sitting member, the corrected
        record of where they last sat for one who has left. It is that
        record's own claim about that term, not a carried guess -- and it is
        refused where the term's bills say otherwise: a member they print at
        two seats, or a sponsor line of the member's surname, in their
        chamber, at another seat that text_sponsors could not place on
        anyone (Winston McCarty, 1999-2000: the record's Merr 10, the bills'
        Hills 38; the review of 5 November 2026). That record matches the
        bills' seat in 1,439 of the 1,517 last terms where both say;
      - else no seat. The name alone is true; an earlier term's seat taken
        from a later record is not known to be (the manager's condition, 5
        November: no source, no seat).
    Only a label with a seat, and only one per member and term: ballots of a
    term that name two seats name neither. `record` is printed_record's
    (one, two, named); `printed` alone stands for `one` with nothing doubted.

    AND ONLY A SEAT OF THE LINES THE TERM SAT ON (20 November 2026). Carlos E.
    Gonzalez's 2015-2016 days named him "Hills 48": his last term, whose bills
    print no seat for him, so the seat his ballots give -- the record's one
    seat for him, the person's correction, whose evidence is the 2001-2002
    journals. 2015-2016 sat on the 2012 lines, which number Hillsborough's
    districts to 45. So a seat from either source is named only where it is a
    district of the term's lines (seat_of_the_lines, by the district table,
    `lines`: parse_districts.table's (districts, places), read from the
    folder the build runs in where not given); else the name alone. Before
    2013 no table of the lines is on file, and a seat is named as before.
    Each seat refused is added to `refused`, where one is given, as (term,
    member id, label)."""
    if record is None:
        record = printed_record() if printed is None else (printed, set(), {})
    printed, two, named = record
    if lines is None:
        import parse_districts as PDIST
        lines = PDIST.table(".", ST.SETTINGS)
    index = EN.district_index({"district": lines[0]})
    held = {(d["kind"], d.get("era")) for d in lines[0]}
    seen, cache = defaultdict(lambda: defaultdict(set)), {}
    body, who, last = {}, {}, {}
    for mid, rows in votes_by_member.items():
        mid = str(mid)
        for v in rows:
            t = P.vote_term(v["year"], v.get("date"))
            last[mid] = max(last.get(mid, ""), t)
            body.setdefault((t, mid), v.get("body"))
            who.setdefault((t, mid), v)
            k = (v.get("label"), v.get("name"), v.get("body"), v.get("party"))
            if k not in cache:
                cache[k] = ballot_seat(v, v.get("body"))
            if " - " in cache[k]:
                seen[t][mid].add(cache[k])
    out = defaultdict(dict)
    for (t, mid), v in sorted(who.items()):
        got = printed.get((t, mid))
        if got and got[0] == body[(t, mid)]:
            ch, county, dist = got
            lab = member_labels(v.get("name"), chamber=ch, party=v.get("party"),
                                district=dist, county=county)["display_full"]
            if " - " in lab:
                if seat_of_the_lines(t, lab, index, held):
                    out[t][mid] = lab
                elif refused is not None:
                    refused.append((t, mid, lab))
                continue
        ls = seen.get(t, {}).get(mid) or set()
        if t != last[mid] or len(ls) != 1 or (t, mid) in two:
            continue
        lab = next(iter(ls))
        said = named.get((t, body[(t, mid)], _surname(v.get("name"))))
        if said and lab not in {member_labels(v.get("name"), chamber=body[(t, mid)],
                                              party=v.get("party"), district=d,
                                              county=c)["display_full"] for c, d in said}:
            continue
        if not seat_of_the_lines(t, lab, index, held):
            if refused is not None:
                refused.append((t, mid, lab))
            continue
        out[t][mid] = lab
    if ballots is not None:
        # WHO VOTED, AS THEIR BALLOTS NAME THEM: the map term_seats was before
        # 5 November 2026, one label with a seat per member and term. Not a
        # seat to show; build_session_pages.by_ballot links a name no roster
        # matches among these, as it did, so the seats' new source moves no
        # link (the lens of 5 November: 102 gained and 56 lost when it read
        # the seats instead -- Rep. Jeb Bradley among them, who voted that
        # term whatever seat he held).
        ballots.update({t: {m: next(iter(ls)) for m, ls in sorted(ms.items()) if len(ls) == 1}
                        for t, ms in sorted(seen.items())})
    return {t: dict(sorted(ms.items())) for t, ms in sorted(out.items()) if ms}


def write_floor_record(data_dir, votes_by_member, cards, moments=None, nobill=None,
                       record=None, worked=None):
    """data/floor_record.json (FLOOR_RECORD, above). Returns its path.
    `record` is term_seats' printed record, read from text_sponsors.json when
    not given. `worked` is (seats, ballots), term_seats' answer where main
    has worked it out already, for the movers (term_voters)."""
    if worked is None:
        ballots = {}
        seats = term_seats(votes_by_member, record=record, ballots=ballots)
    else:
        seats, ballots = worked
    presiding = defaultdict(list)
    for rows in votes_by_member.values():
        for v in rows:
            if v.get("vote") == "Presiding":
                # the seat of the term (term_seats), else the name alone --
                # not a later record's seat, and not the party letter alone,
                # which a member's link never shows (components.person_link)
                mid = str(v.get("member_id") or "")
                lab = ((seats.get(P.vote_term(v["year"], v.get("date"))) or {}).get(mid)
                       or member_labels(v.get("name"), chamber=v.get("body"),
                                        party=v.get("party"))["display_plain"])
                presiding[_roll_call_key(v)].append([mid, lab])
    f = Path(data_dir) / FLOOR_RECORD
    f.write_text(json.dumps({
        "_about": "Not published. For build_session_pages.py: who each roll call's "
                  "Presiding ballot names (presiding), and where each roll call's card is "
                  "on its bill's Votes tab (cards, the index into the bill record's "
                  "rollcalls); the seat each member held in each term, as its bills "
                  "print it, else their ballots' in their last term (seats); who voted in "
                  "each term, as their ballots label them, for linking a name and not for "
                  "showing a seat (ballots); and where each roll call on no bill is in its term's "
                  "nobill/<term>.json (nobill). Written by build_site_v2.py, which reads "
                  "the ballots.",
        "presiding": {k: sorted(v) for k, v in sorted(presiding.items())},
        "cards": cards, "moments": moments or {}, "seats": seats, "ballots": ballots,
        "nobill": nobill or {}},
        separators=(",", ":"), sort_keys=True),
        encoding="utf-8")
    print(f"{f}: {len(presiding):,} roll calls with a presiding ballot, "
          f"{sum(len(b) for t in cards.values() for b in t.values()):,} roll-call cards "
          f"on {sum(len(t) for t in cards.values()):,} bills' Votes tabs; "
          f"{sum(len(s) for s in seats.values()):,} members' seats across "
          f"{len(seats)} terms")
    # SILENCE IS NOT SUCCESS: ballots with no presiding officer at all is a
    # vote field read wrong, and every session day would name nobody.
    if votes_by_member and not presiding:
        print("  WARNING: no ballot reads Presiding; no session day will name who presided")
    return f


# The seat out of a ballot's own label: "Shurtleff, Steve(D) Merrimack 15".
# build_data._former_label builds that string and says at length why this reads
# it rather than former_members.json -- it is the only copy
# member_corrections.json has been applied to. The shape is a contract between
# the two functions: change it in both places or in neither.
FORMER_LABEL = re.compile(r"\(\s*[A-Za-z]?\s*\)\s*(?P<county>[A-Za-z .']+?)\s+"
                          r"(?P<district>\d+)\s*$")


def same_person(path=Path("corrections/member_corrections.json")):
    """[[house id, senate id], ...] the owner confirmed are one person: the
    "same_person" entries of member_corrections.json whose "confirmed" begins
    with a date (2 November 2026: thirty, of the 31 pairs no rule joined; the
    thirty-first, "no, two people", is kept as the answer and joins nothing).
    Read, never written: the file is the owner's."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out = []
    for e in (doc.get("same_person") or []) if isinstance(doc, dict) else []:
        if isinstance(e, dict) and re.match(r"\d{4}-\d{2}-\d{2}", str(e.get("confirmed") or "")):
            ids = [str(e[k]) for k in ("house", "senate") if e.get(k)]
            if len(ids) == 2:
                out.append(ids)
    return out


def former_movers(register, e2p, legs, links, votes_by_member, confirmed=()):
    """{later id: [earlier ids]} for a member who sat in both chambers and sits
    in neither now, as the person register joins them (30 October 2026).

    A member who changes chamber is given a new number in each, and the site
    numbers a member by the PersonID their votes carry: Shannon Chandley voted
    as 568 in the House and as 9404 in the Senate, and had a page for each.
    member_links joins those numbers only for a member who sits today, so once
    such a member left, their record stayed in two halves. The register
    (generated/person_numbers.json, people.py) is the one join the public data
    API publishes, under the one-chamber rule; the site takes the same one, so
    the two say the same about who is one person. Each register number is an
    Employeeno, and the site's id for it is the PersonID the roster gives it
    (people.emp_to_pid), else the number itself. A person joined here has two
    or more site ids that voted, none of them a sitting member's or already
    joined to one; the page kept is the one that voted last -- the later
    chamber's, as a sitting mover's is -- and it carries every chamber's
    votes.

    AND THE PAIRS THE OWNER CONFIRMED (`confirmed`, same_person): site ids
    already, joined on the same terms, after the register's and only where
    neither id is in a join yet."""
    sitting = {str(k) for k in legs} | {str(k) for k in (links or {})} | \
        {str(x) for v in (links or {}).values() for x in v}
    # By the day, not the text of it: dates are M/D/YYYY, and as text
    # "9/13/2018" sorts after "10/10/2018" (the review of 30 October 2026).
    # And by the term before the day (service_order): a day the clerk got
    # wrong made two House members' page the Senate's.
    last = lambda i: max((service_order(v) for v in votes_by_member.get(i, [])),
                         default=("", vote_date("")))
    out = {}
    groups = [[str((e2p or {}).get(n) or n) for n in person.get("numbers") or []]
              for person in (register or {}).get("people") or []]
    groups += [[str(i) for i in pair] for pair in confirmed or ()]
    for ids in groups:
        ids = [i for i in dict.fromkeys(ids) if votes_by_member.get(i)]
        placed = set(out) | {x for v in out.values() for x in v}
        if len(ids) < 2 or any(i in sitting or i in placed for i in ids):
            continue
        ids.sort(key=last)
        out[ids[-1]] = ids[:-1]
    return out


def former_roster(legs, votes_by_member, links, former_file, current_term):
    """People who voted in the current term and hold no seat in it now.

    THE MID-TERM DEPARTURES. Twenty members of the 2025-2026 House cast
    between 250 and 591 votes each and then left -- resignations, and a seat
    filled at a special election. The roster is a snapshot of who serves
    today, correctly, so it does not carry them; the vote record does. Until
    now that meant the site held their whole voting history and gave them no
    page, so every one of those votes and every bill they sponsored was plain
    text. They are the former members a reader is most likely to look up,
    because they were here this term.

    Deliberately NOT merged into the sitting roster. site/legislators.json is
    read by about a dozen builders -- the legislators page, the town pages,
    committee rosters, the feeds, the exports, the directory, and the Learn
    section's count of sitting members -- and a former member reaching any of
    them would be the site saying they still serve. This returns a separate
    map, and build_legislators writes it to its own file.

    The seat comes from the vote rows themselves ("St. Clair, Charlie(D)
    Belknap 05"), because that is the seat they held when the vote was cast,
    which is the only seat the record can honestly give them --
    former_members.json fills any gap. No email and no telephone: a published
    official address belongs to the office, and they no longer hold it.
    """
    folded = {str(x) for v in (links or {}).values() for x in v}
    former_file = former_file or {}
    # THE ADDRESS HAS TO READ LIKE EVERYONE ELSE'S. member_slug puts the county
    # in a House member's address because district numbers repeat between
    # counties, and it uses the abbreviation the roster carries -- rock-13, not
    # rockingham-13. A former member has no roster row and so no abbreviation,
    # which gave the first build /legislator/michael-vose-rockingham-5 beside
    # /legislator/jodi-nelson-rock-13. Same map build_data.py builds for the
    # same reason: the sitting roster is where the abbreviations live.
    abbr = {m["county"]: m["county_abbr"] for m in legs.values()
            if m.get("county") and m.get("county_abbr")}
    out = {}
    for mid, mv in votes_by_member.items():
        mid = str(mid)
        if mid in legs or mid in folded or not mv:
            continue
        # EVERY TERM, not only the current one. The cost was measured before
        # this was widened: about 3,600 more files and 200 MB, against a
        # 100,000 cap and a warning threshold of 90,000. Run check_site.py for
        # where the deployment actually sits; the figure this comment used to
        # name here was not one any command produced. What
        # it buys is 36,541 sponsor mentions, 53% of every one on the site,
        # turning from plain text into a link to that person's record.
        #
        # Anyone the record holds at all: a page is written even where the
        # party, the seat or the dates are thin, and says what it does not
        # know rather than guessing. A sparse page is still the only place
        # that person's voting record exists.
        if not mv:
            continue
        # The term before the day (service_order): the last ballot names the
        # seat, and the last of a joined page's says where its record ends.
        dated = sorted(mv, key=service_order)
        last = dated[-1]
        every = sorted([v for x in (mid, *(links or {}).get(mid, []))
                        for v in votes_by_member.get(x, [])],
                       key=service_order)
        rec = dict(former_file.get(mid) or {})
        # THE BALLOT'S OWN LABEL FIRST, because it is the only thing here that
        # has been through member_corrections.json. That file is the person's,
        # no generator writes it, and build_data applies it to the map it
        # builds the labels from -- but it never writes that corrected map out,
        # so former_members.json on disk still holds whatever the generators
        # deduced. Reading the file first published the uncorrected seat while
        # taking the corrected NAME from the same ballot two lines above:
        # 376628 went out as "Rep. Steve Shurtleff (D - Graf 9)", the name from
        # the correction and the seat from the Thomas Oppel record it replaced.
        #
        # Where no correction exists the two sources agree, because the label
        # is built from the same file. So this costs nothing and picks up every
        # correction made there without a second copy of the logic.
        m = FORMER_LABEL.search(str(last.get("label") or ""))
        county = (m.group("county").strip() if m else "") or rec.get("county") or ""
        district = ((m.group("district").lstrip("0") if m else "")
                    or str(rec.get("district") or "").lstrip("0"))
        out[mid] = {
            "id": mid,
            "name": last.get("name") or rec.get("name") or "",
            "chamber": last.get("body") or "",
            "party": last.get("party") or rec.get("party") or "",
            "party_code": last.get("party") or "",
            "county": county, "district": district,
            "county_abbr": abbr.get(county, ""),
            "former": True,
            # What the record can say about their service, and nothing beyond
            # it. Not why they left: the site does not distinguish a member
            # who resigned from one who died, and must not start here.
            # OVER EVERY NUMBER JOINED TO THEM (former_movers, the review of 30
            # October 2026): Shannon Chandley's page read "on record 2019 to
            # 2024" above 1,838 votes back to 2009, and her House years went
            # from the directory. The name, chamber and seat stay the ones of
            # her own latest vote.
            "served": {"first": every[0].get("date") or "",
                       "last": every[-1].get("date") or "",
                       "terms": sorted({P.vote_term(v.get("year", ""), v.get("date"))
                                        for v in every if v.get("year")})},
        }
    return out


def corrected_seats(path=Path("corrections/member_corrections.json")):
    """The member ids whose seat the person set in member_corrections.json
    ("members", an entry with a county or a district). Read, never written:
    a seat the person gave is theirs, and nothing dated from the bills goes
    over it."""
    try:
        got = json.loads(Path(path).read_text(encoding="utf-8")).get("members") or {}
    except (OSError, ValueError):
        return set()
    return {str(k) for k, v in got.items()
            if isinstance(v, dict) and (v.get("county") or v.get("district"))}


def _member_address(m):
    lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                        party=m.get("party_code") or m.get("party"),
                        district=m.get("district"), county=m.get("county"),
                        county_abbr=m.get("county_abbr"))
    return "/legislator/" + (m.get("slug") or member_slug(m, lab))


def date_former_seats(former, votes_by_member, printed, corrected, legs):
    """(former, {id: (record's seat, bills' seat)}): each former member's
    page seat put right from the bills of their last term (5 November 2026).

    A former member's page took its seat from their last ballot's label, and
    that label from one record of where they last sat (build_data.
    _former_label, from former_members.json, which the General Court's
    current-state Legislators view fills). Against the bills their last term
    printed it was wrong on 75 of the 1,468 pages where the bills print one
    seat: Rebecca Hutchinson's 1999-2000 seat was "Rock 73", in a county the
    1992 map numbered to 36, where her bills print Rockingham 8.

    So where the member's own number's last term's bills print one seat in
    their chamber (printed_seats) and it is not the record's, the page takes
    the bills' -- unless the person set the seat in member_corrections.json
    (`corrected`), which stands as they wrote it. The page's address is built
    from the seat, so it moves; the old one is kept in the row's moved_from,
    and build_pages answers it with a 301 (build_pages.moved_members). A
    change whose new address another page already has is not made."""
    abbr = {m["county"]: m["county_abbr"] for m in legs.values()
            if m.get("county") and m.get("county_abbr")}
    # every address a page or a 301 already answers: the former members', the
    # sitting members', and each one a page has moved from (the review of 5
    # November 2026: a sitting member's address was not in the set)
    taken = ({_member_address(m) for m in former.values()}
             | {_member_address(m) for m in legs.values() if m.get("name")}
             | {a for m in former.values() for a in m.get("moved_from") or []})
    out = {}
    for mid, m in former.items():
        rows = votes_by_member.get(mid) or []
        if not rows or mid in corrected:
            continue
        # The last term by the roll call's own, not the day's (service_order).
        last = max(rows, key=service_order)
        got = printed.get((P.vote_term(last.get("year", ""), last.get("date")), mid))
        if not got or got[0] != (m.get("chamber") or ""):
            continue
        _ch, county, dist = got
        same = (dist == str(m.get("district") or "").lstrip("0")
                and (m.get("chamber") == "S"
                     or county.lower()[:4] == str(m.get("county") or "").lower()[:4]))
        if same:
            continue
        was = _member_address(m)
        new = dict(m, county=county if m.get("chamber") != "S" else (m.get("county") or ""),
                   district=dist, county_abbr=abbr.get(county, m.get("county_abbr") or ""))
        now = _member_address(new)
        if now != was and now in taken:
            print(f"  WARNING: {m.get('name')} ({mid}) not given the seat the bills print: "
                  f"{now} is another page's address")
            continue
        if now != was:
            new["moved_from"] = [*(m.get("moved_from") or []), was]
            taken.add(now)
        former[mid] = new
        out[mid] = (f"{m.get('county') or ''} {m.get('district') or ''}".strip(),
                    f"{county} {dist}".strip())
    return former, out


def last_term_labels(former, votes_by_member, record, table):
    """(former, {id: (seat shown, seat now)}): A FORMER MEMBER'S LABEL NAMES THE SEAT THEY HELD IN
    THEIR LAST TERM ON RECORD, or none (labels-use-the-seat-held-at-the-time; 19 November 2026).

    The seat a former member's page gave was the record's one seat for them -- their last
    ballot's label, from former_members.json, the General Court's lists or the person's
    member_corrections.json -- put right from the bills of their last term by date_former_seats
    where those print one seat and the person set none. Neither says which term the record's seat
    is of. Carlos E. Gonzalez's correction gives "Hills 48", which the journals print for him in
    2001-2002, and his last term, 2015-2016, was on the 2012 lines, which number Hillsborough's
    districts to 45: the label named a seat that did not exist in the term it stands for. So,
    for the member's last term (by the roll call's own, service_order):
      - where its bills print one seat in their chamber (`record`'s one), that seat -- over a
        corrected seat too, whose evidence names earlier terms (three such, 2015-2016);
      - where they print two, the record's seat, as before: both members so printed (1999-2000)
        are printed far oftener at the record's seat than at the other;
      - where they print none and the district table holds the term's era (`table`, the
        2012 lines from 2013-2014, today's from 2023-2024), the record's seat only if it is a
        district of those lines; else no district;
      - else the record's seat, as before (before 2013 no table of the lines is on file).
    ONLY THE LABEL MOVES, never the page: the row keeps the address it has ("slug"), so no
    page moves and no link breaks. A district dropped keeps the member's county, which no
    redrawing of the lines changes. `record` is printed_record's (one, two, named);
    `table` parse_districts.table's (districts, places)."""
    one, two, _named = record
    index = EN.district_index({"district": table[0]})
    held = {(d["kind"], d.get("era")) for d in table[0]}
    abbr = {}
    for m in former.values():
        if m.get("county") and m.get("county_abbr"):
            abbr.setdefault(m["county"], m["county_abbr"])
    out = {}
    for mid, m in former.items():
        rows = votes_by_member.get(mid) or []
        ch = m.get("chamber") or ""
        county, dist = m.get("county") or "", str(m.get("district") or "").lstrip("0")
        if not rows or not dist or ch not in ("H", "S"):
            continue
        last = max(rows, key=service_order)
        term = P.vote_term(last.get("year", ""), last.get("date"))
        got = one.get((term, mid))
        if got and got[0] == ch:
            if got[2] == dist and (ch == "S" or got[1].lower()[:4] == county.lower()[:4]):
                continue
            now = ((got[1] or county) if ch == "H" else county, got[2])
        elif (term, mid) in two:
            continue
        else:
            kind, era = ("senate" if ch == "S" else "house"), EN.era_of(term)
            said = dist if ch == "S" else f"{county} {dist}"
            if era is None or (kind, era) not in held or EN.resolve_district(index, kind, said, era):
                continue
            now = (county, "")
        new = dict(m, slug=_member_address(m)[len("/legislator/"):], county=now[0], district=now[1],
                   county_abbr=abbr.get(now[0], m.get("county_abbr") or "") if now[0] != county
                   else m.get("county_abbr") or "")
        former[mid] = new
        out[mid] = (f"{county} {dist}".strip(), f"{now[0]} {now[1]}".strip() if now[1] else "no district")
    return former, out


# EVERY ADDRESS A FORMER MEMBER'S PAGE HAS HAD, KEPT (the review of 5 November
# 2026; the manager: "keep the 301s permanently -- old emails link through
# them"). A page's moved_from is worked out afresh every build, so an address
# a page left would die the day the reason it moved went away: the person
# correcting that seat, or the record coming to agree with the bills. This
# file holds {address: member id} for every move ever published, is merged
# into and never pruned (src/ops/record_moves.py), and is read by every build.
MOVED_ADDRESSES = Path("generated/moved_addresses.json")


def keep_moved(former, path=MOVED_ADDRESSES, links=None, sitting=()):
    """Every recorded address of a former member's page answers with a 301 to
    the page they have now: appended to the row's moved_from where it is not
    the page's own address and not there already. Returns (kept, unrecorded):
    how many recorded addresses were put back, and the moves this build made
    that the file does not hold yet, said so they get recorded.

    A MEMBER JOINED TO ANOTHER'S PAGE IS ON THAT PAGE (`links`, {page's id:
    [ids joined to it]}). The file records an address for the member whose
    page it then led to, and the page a member's record is on can change:
    the night of 6 November recorded Frederick King's House address for his
    Senate number, 205005, whose page was the one kept, and once his page was
    kept as the House's (service_order) 205005 had none of its own. The
    address goes to the page that carries 205005's record now -- here, the
    House page whose own address it is, so nothing is added. The file is not
    re-pointed: it only grows (record_moves.py)."""
    try:
        moved = json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else {}
    except ValueError:
        print(f"  WARNING: {path} will not read: no recorded former address is kept this build")
        moved = {}
    on_page = {str(x): str(k) for k, v in (links or {}).items() for x in v}
    # NEVER A LIVE PAGE'S OWN ADDRESS (the review of 6 November 2026). The
    # file records an address for the member whose page it led to and is
    # never re-pointed, so a pair joined and then parted would have each of
    # its two pages' addresses recorded for the other -- King's House address
    # under his Senate number, his Senate address under his House number --
    # and each page would answer the other's address with a 301: a loop
    # between two live pages. An address that is a page's own now stays that
    # page's, and is said.
    own = {_member_address(x): k for k, x in former.items()}
    own.update({a: "sitting" for a in sitting or ()})
    kept = 0
    for addr, mid in sorted(moved.items()):
        m = former.get(str(mid)) or former.get(on_page.get(str(mid), ""))
        if m is None:
            print(f"  WARNING: {addr} is recorded for member {mid}, who has no former page now")
            continue
        if addr in own and addr != _member_address(m):
            print(f"  WARNING: {addr} is recorded for member {mid}, and is the address of another "
                  "page now: it is not answered with a 301")
            continue
        if addr != _member_address(m) and addr not in (m.get("moved_from") or []):
            m["moved_from"] = [*(m.get("moved_from") or []), addr]
            kept += 1
    unrecorded = sorted(a for k, m in former.items() for a in m.get("moved_from") or []
                        if a not in moved)
    return kept, unrecorded


def turned_addresses(term_rosters, legs, former, links=None):
    """({sitting id: [addresses]}, how many former rows took one): THE ADDRESS A
    MEMBER'S PAGE HAD IN A TERM WHOSE ROSTER IS FROZEN, ANSWERED WHERE THEIR
    PAGE IS NOW (25 November 2026, for Organization Day).

    A member's address is built from the seat they hold (member_slug), so on
    the night the roster turns to the next term a member re-elected to
    another seat -- five Representatives at the election of 3 November 2026
    -- has their page at a new address, and one elected to the other chamber
    under a new number (Jim Creighton and Laura Telerski) has the page their
    record is joined to at the new chamber's; and the address the page had
    until Organization Day, in readers' bookmarks and in every update email
    sent, would answer nothing. Each member of a term whose own roster is
    frozen (`term_rosters`, which build_site_v2 labels the term's members
    by) is looked for where their record is now: a sitting member's page,
    under their own number or the one it is joined to (`links`), or a former
    member's (`former`). Where the address their row gave then is no page's
    now, it answers with a 301 to that page: a sitting member's in the map
    returned, which build_legislators writes into their row of
    legislators.json for build_pages' _redirects; a former member's
    appended to their row's moved_from, as every earlier address of a
    former member's page is. An address that is a page's own now stays that
    page's, and is never moved. Worked out afresh each build from the frozen
    roster, which is kept, so nothing needs recording."""
    on_page = {str(x): str(k) for k, v in (links or {}).items() for x in v}
    live = ({_member_address(m) for m in legs.values() if m.get("name")}
            | {_member_address(m) for m in former.values()}
            | {a for m in former.values() for a in m.get("moved_from") or []})
    sitting, n_former = {}, 0
    for t in sorted(term_rosters or {}):
        for mid, row in sorted((term_rosters[t] or {}).items()):
            mid = str(mid)
            if not isinstance(row, dict) or not row.get("name"):
                continue
            was = _member_address(row)
            if was in live:
                continue
            page = mid if mid in legs or mid in former else on_page.get(mid, "")
            if page in legs:
                sitting.setdefault(page, []).append(was)
            elif page in former:
                m = former[page]
                m["moved_from"] = [*(m.get("moved_from") or []), was]
                n_former += 1
            else:
                continue
            live.add(was)
    return sitting, n_former


# THE SEATS AS THE ELECTION LEFT THEM, FROM THE DAY AFTER ORGANIZATION DAY,
# BEFORE THE GENERAL COURT'S ROSTER TURNS (the owner, 25 November 2026: "I
# would say wait until December 3rd to switch to the new titles since the
# swearing in ceremony happens on the morning of December 2nd"). The roster
# installed is the House of 2025-2026 until the General Court publishes the
# next one, and legislators.json stays exactly that: the night's census counts
# it, and every list of who holds a seat -- the Legislators tab, the town
# pages, the map, the committees -- reads it. What switches on the day is each
# member's own identity, as the roster's turn will draw it:
#
#   a member NOT RETURNING (build_members_elect.seat_changes: no race's winners
#     name them, and their seat's race is decided) is a former member: their
#     own file is the former member's, from the same code (former_roster,
#     date_former_seats, last_term_labels, build_legislators), so their page
#     reads "Former Representative ...", their search row "Former Rep. ...",
#     and they are in the Former members list -- and when the roster turns,
#     and they are former.json's, nothing of it changes;
#   a member ELECTED TO ANOTHER SEAT -- another district of their chamber, or
#     the other chamber (Jim Creighton and Laura Telerski) -- is drawn at the
#     seat they won: the chamber, the district and its towns, their label, the
#     title of a senator; a senator-elect sits on no Senate committee and in
#     no floor seat yet. Their page keeps its address until the roster turns,
#     when members.turned_addresses moves it and answers the old one with a
#     301.
#
# On a bill, a roll call or a committee roster every member keeps the seat
# they held then (labels-use-the-seat-held-at-the-time): those are drawn from
# the ballots and from the roster as it stands, never from this. Written to
# site/seat_switch.json (SEAT_SWITCH), which build_legislator_pages, the
# search (build_indexes) and the requests (build_lsrs, build_request_pages)
# read through read_switch and nothing else; none is written before the day,
# or once the roster has turned.
SEAT_SWITCH = "seat_switch.json"


def site_rows(legs, former=None, links=None):
    """([sitting row], [former row]): the roster and the former members in the
    shape site/legislators.json and site/former.json give them to the
    members-elect step (an id, a name, a chamber, a county, a district, the
    page's slug, its display_full, a joined page's member_ids), worked out as
    build_legislators works them out, for build_members_elect.seat_switch to
    match the election's winners against before those files are written."""
    def row(mid, m):
        lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                            party=m.get("party_code") or m.get("party"),
                            district=m.get("district"), county=m.get("county"),
                            county_abbr=m.get("county_abbr"))
        out = {**m, **lab, "id": str(mid), "slug": m.get("slug") or member_slug(m, lab)}
        if (links or {}).get(mid):
            out["member_ids"] = [str(mid), *(str(x) for x in links[mid])]
        return out
    return ([row(k, v) for k, v in legs.items()],
            [row(k, v) for k, v in (former or {}).items()])


def seat_switched(switch, legs, former, votes_by_member, links, former_file, current_term,
                  district_lines=None):
    """`switch` (build_members_elect.seat_switch's, or None) with "members":
    {member id: the member as the election left them}, for build_legislators;
    {} where the site does not switch.

      leaving  their former member's row, made as the roster's turn makes it:
               former_roster over the roster without them, then the seat their
               last term's bills print (date_former_seats) and the label of
               their last term's seat (last_term_labels), among every former
               member so that no two pages take one address;
      moved    their roster row at the seat they won: the race's chamber,
               county and district, its towns (the switch's), the county's
               abbreviation as the roster spells it, a senator's title and no
               House committee or floor seat for one elected to the Senate,
               and the address their page has now."""
    if not switch:
        return {}
    members = {}
    leaving = {str(k) for k in switch.get("leaving") or {}} & set(legs)
    if leaving:
        import contextlib
        import io
        rest = {k: v for k, v in legs.items() if k not in leaving}
        gone = former_roster(rest, votes_by_member, links, former_file, current_term)
        both = {**(former or {}), **{k: v for k, v in gone.items() if k in leaving}}
        # The former members already went through this in main, which said what it
        # had to of them: only a line about a member leaving now is said again.
        said = io.StringIO()
        with contextlib.redirect_stdout(said):
            both, _redated = date_former_seats(both, votes_by_member, printed_seats(),
                                               corrected_seats(), rest)
        for line in said.getvalue().splitlines():
            if any(f"({k})" in line for k in leaving):
                print(line)
        if district_lines is not None:
            both, _relabelled = last_term_labels(both, votes_by_member, printed_record(),
                                                 district_lines)
        # AT THE ADDRESS THEIR PAGE HAS NOW: every list still links it, and it
        # moves, with a 301, only when the roster turns (turned_addresses).
        for k in sorted(leaving):
            if k in both:
                m = legs[k]
                lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                                    party=m.get("party_code") or m.get("party"),
                                    district=m.get("district"), county=m.get("county"),
                                    county_abbr=m.get("county_abbr"))
                row = dict(both[k], slug=m.get("slug") or member_slug(m, lab))
                row.pop("moved_from", None)
                members[k] = row
    abbr = {m["county"]: m["county_abbr"] for m in legs.values()
            if m.get("county") and m.get("county_abbr")}
    for mid, won in sorted((switch.get("moved") or {}).items()):
        m = legs.get(str(mid))
        parts = str((won or {}).get("key") or "").split("|")
        if not m or parts[0] not in ("H", "S") or len(parts) != (3 if parts[0] == "H" else 2):
            continue
        ch = parts[0]
        lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                            party=m.get("party_code") or m.get("party"),
                            district=m.get("district"), county=m.get("county"),
                            county_abbr=m.get("county_abbr"))
        new = dict(m, chamber=ch, district=parts[-1], towns=list(won.get("towns") or []),
                   slug=m.get("slug") or member_slug(m, lab))
        if ch == "H":
            new.update(county=parts[1], county_abbr=abbr.get(parts[1], m.get("county_abbr") or ""))
        if ch != str(m.get("chamber") or "")[:1].upper():
            new.update(title="Senator" if ch == "S" else "Representative", committees=[],
                       seat="")
        new["label"] = member_labels(new.get("name"), chamber=ch,
                                     party=new.get("party_code") or new.get("party"),
                                     district=new["district"], county=new.get("county"),
                                     county_abbr=new.get("county_abbr"))["display_full"]
        members[str(mid)] = new
    return {**switch, "members": members}


def read_switch(site):
    """{"leaving": {id: row}, "moved": {id: row}, "day", "term"} from
    site/seat_switch.json (SEAT_SWITCH), the rows as build_legislators wrote
    them -- a leaving member's as former.json would have it, a moved member's
    as legislators.json would -- or both {} where there is no file: before
    the day after Organization Day, and once the roster has turned. A file
    that will not read stops the reader: the step writes it whole."""
    p = Path(site) / SEAT_SWITCH
    if not p.is_file():
        return {"leaving": {}, "moved": {}, "day": None, "term": None}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        return {**{k: {str(r["id"]): r for r in doc.get(k) or []} for k in ("leaving", "moved")},
                "day": doc.get("day"), "term": doc.get("term")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise SystemExit(f"{p.as_posix()} will not read ({type(e).__name__}: {e}): "
                         "build_site_v2 writes it whole, so this is a fault to look at")


# What one ballot says about whether the member took part, in the order a
# roll call is read when two of a member's numbers somehow both hold a ballot
# on it: a vote cast outranks anything else the other ballot says.
ATTENDANCE_KIND = {"Yea": "voted", "Nay": "voted", "Presiding": "presided",
                   "Not Voting/Excused": "excused",
                   "Not Voting/Not Excused": "not_excused"}
_ATTENDANCE_RANK = ("voted", "presided", "conflict", "excused", "not_excused",
                    "no_vote")
# In the room without a Yea or a Nay: in the chair, or standing aside from
# one question under the chamber's conflict rule.
_ATTENDANCE_PRESENT = ("voted", "presided", "conflict")


def _roll_call_key(v):
    return f'{v.get("year")}-{v.get("body")}-{v.get("vote_number")}'


def attendance_context(votes_by_member):
    """{"dates": {roll call: day}, "chair": {roll call: member_id}, ...}.

    Two things a member's own ballots cannot say about themselves, read once
    off every ballot for member_attendance. Beside them, for the build's log,
    the roll calls whose date was not trusted and the declared conflicts seen.

    THE DAY A ROLL CALL WAS TAKEN, where its date breaks the order. The
    numbers run in the order the votes were taken, and two dates do not: 1999
    Senate roll call 109 is dated 10/22/2009 between two of 10/22/1999, and
    2003 Senate roll call 24 is dated 4/4/2003 between 3/27 and 4/3, where the
    journal prints it on the pages of 3 April. As they stand, each is a
    sitting that never happened, attended by every senator on it. So a date
    outside its term, or one its two neighbours keep in order while it
    breaks it, is not trusted: where both neighbours fall on one day the roll
    call is read on that day, having been taken between them, and otherwise
    it is a roll call on no day. A run that breaks the order together --
    2008 House 144-148, the veto day of 24 September, numbered before the
    special session's eight of 4 June, 401-408 -- has neighbours out of order
    with each other, and is left as it is.

    WHO WAS IN THE CHAIR, where the record names nobody. The House codes its
    presiding officer "Presiding" -- except that on some days no roll call
    carries that ballot at all, and the Speaker is coded Excused or Not
    Excused on every one: 2/11/2016, 1/3/2018, 1/2/2019 and 2/16/2022 among
    them, each a day the journal puts the Speaker in the chair, and every
    House roll call of 2021 from 7 April. So on a House day on which no roll
    call names anyone presiding, the member the record puts in the chair most
    often that year is read as presiding wherever they are coded absent. On
    those days only: where the record names somebody else it is believed,
    which is how the five days Speaker Packard was on leave in 2025-2026 stay
    days absent. Not the Senate, whose President votes as a senator and is
    recorded presiding on 195 ballots in twenty-eight years.
    """
    dates, chaired, conflicts = {}, set(), 0
    in_chair = defaultdict(Counter)
    for rows in votes_by_member.values():
        for v in rows:
            key = _roll_call_key(v)
            conflicts += bool(v.get("conflict"))
            if key not in dates:
                dates[key] = vote_date(v.get("date"))
            if v.get("vote") == "Presiding":
                chaired.add(key)
                in_chair[(str(v.get("year")), v.get("body"))][v.get("member_id")] += 1
    runs = defaultdict(list)
    for key in dates:
        y, b, n = key.split("-", 2)
        if n.isdigit():
            runs[(y, b)].append((int(n), key))
    none = (0, 0, 0)
    trusted = dict(dates)
    for (y, b), seq in runs.items():
        seq.sort()
        t = P.term_of(y)
        span = {int(t[:4]), int(t[5:])} if t else set()
        for i, (_, key) in enumerate(seq):
            day = dates[key]
            if day == none:
                continue
            prev = dates[seq[i - 1][1]] if i else none
            nxt = dates[seq[i + 1][1]] if i + 1 < len(seq) else none
            broken = (none not in (prev, nxt) and prev <= nxt
                      and not prev <= day <= nxt)
            if day[0] not in span or broken:
                trusted[key] = prev if prev != none and prev == nxt else none
    house_days = defaultdict(list)
    for key, day in trusted.items():
        if key.split("-")[1] == "H" and day != none:
            house_days[day].append(key)
    chair = {}
    for day, keys in house_days.items():
        if any(k in chaired for k in keys):
            continue
        for k in keys:
            top = in_chair.get((k.split("-")[0], "H"))
            if top:
                chair[k] = top.most_common(1)[0][0]
    return {"dates": trusted, "chair": chair, "conflicts": conflicts,
            "redated": sorted(k for k in dates if trusted[k] != dates[k])}


def member_attendance(votes, context=None):
    """{term: {"chambers", "days", "attended", "roll_calls", "voted", ...}}.

    ATTENDANCE, AS THE PERSON DEFINED IT (23-24 September): a day is a day the
    member's chamber held at least one roll call while they held the seat, and
    it counts as attended if they cast a vote on any roll call that day, with
    no note about part days; beside that, how many of the roll calls held
    while they sat they voted on.

    WHILE THEY SAT is the ballots themselves. Every roll call from 1999 lists
    the members seated for it, whatever they did -- 381 to 400 ballots on a
    House roll call, 22 to 24 on a Senate one -- and between a member's first
    and last ballot of a term, 8 of the 6,015 member-terms miss a roll call at
    all. So a member who arrived at a special election is counted from the
    roll call they first appear on and one who left stops at their last, with
    no service dates to model and none to get wrong. The same rows the Votes
    tab lists: `votes` is every number the member voted under.

    ONE SEAT OUTLIVES ITS HOLDER. The 2017 Senate kept one member on every
    roll call for three months after they had gone, each ballot code 7 with
    nothing in it: 134 ballots on ten days, which counted as absences from a
    seat nobody held. So a run of ballots recording nothing that ends a
    member's term in a chamber is not counted. Only there, and only ballots
    that record nothing: an excused ballot is a member who held the seat and
    was away. No other member-term from 1999 ends in such a run.

    PRESIDING COUNTS AS PRESENT. The Speaker is recorded "Presiding" on most
    of a term's House roll calls and votes on few; on 98 days Terie Norelli
    presided and cast no Yea or Nay at all. Reading that as absence would make
    the person running the chamber its worst attender. The Votes tab already
    tells a reader a presiding ballot "is not a missed vote", and this agrees
    with it; the page says "presided over" where it happened. `context` is
    attendance_context(), which also says who presided where the record
    names nobody, and which day a misdated roll call was taken.

    SO DOES A DECLARED CONFLICT OF INTEREST (rollcall_parser.CONFLICT): the
    member was there and stood aside from one question under the chamber's
    rule. On seven days a member declared a conflict and voted on nothing
    else, and each read as a day absent.

    "No vote recorded" otherwise -- database code 7 and an empty code -- is
    not a vote cast, so it is missed.
    """
    ctx = context or {}
    dates, chair = ctx.get("dates", {}), ctx.get("chair", {})
    by_term = defaultdict(list)
    for v in votes:
        # Organization Day's ballots are the next term's (proceedings.vote_term).
        t = P.vote_term(str(v.get("year") or ""), v.get("date"))
        if not t:
            continue
        kind = ATTENDANCE_KIND.get(v.get("vote"), "no_vote")
        key = _roll_call_key(v)
        if v.get("conflict"):
            kind = "conflict"
        elif (kind in ("excused", "not_excused")
              and chair.get(key) == v.get("member_id")):
            kind = "presided"
        num = str(v.get("vote_number") or "")
        by_term[t].append(((v.get("body"), str(v.get("year")),
                            int(num) if num.isdigit() else 0), key, kind, v))
    out = {}
    for t in sorted(by_term):
        kept = []
        for body in sorted({b[0][0] for b in by_term[t]}, key=str):
            run = sorted((b for b in by_term[t] if b[0][0] == body),
                         key=lambda b: b[0])
            while run and run[-1][2] == "no_vote":
                run.pop()
            kept += run
        if not kept:
            continue
        calls, days, chambers = {}, {}, set()
        for (body, _, _), key, kind, v in kept:
            was = calls.get(key)
            if was is None or _ATTENDANCE_RANK.index(kind) < _ATTENDANCE_RANK.index(was):
                calls[key] = kind
            if body in ("H", "S"):
                chambers.add(body)
            day = dates.get(key) or vote_date(v.get("date"))
            # An undated ballot is still a roll call held while they sat; it
            # cannot say which day, so it is left out of the days rather than
            # lumped into one invented day with every other undated ballot.
            if day != (0, 0, 0):
                days[day] = days.get(day, False) or kind in _ATTENDANCE_PRESENT
        kinds = Counter(calls.values())
        out[t] = {"chambers": "".join(sorted(chambers)),
                  "days": len(days),
                  "attended": sum(1 for x in days.values() if x),
                  "roll_calls": len(calls),
                  **{k: kinds.get(k, 0) for k in _ATTENDANCE_RANK}}
    return out


def sponsored_in_order(rows):
    """A member's sponsored bills: prime first, then by year, oldest first,
    then by bill number in bills.html's order (bill_order)."""
    return sorted(rows, key=lambda x: (not x["prime"], x.get("year") or 0,
                                       BO.bill_key(x["bill"])))


def member_office(m, offices=None):
    """The office a sitting member holds that their page names, or "".

    THE SPEAKER'S OWN PAGE SAID NOTHING OF IT (the survey of 7 October 2026).
    Rep. Sherman Packard's page listed House Rules and his presiding counts,
    and the seating chart labels the Speaker's chair, while nothing on his
    page named the office. The chair is seat 6002, on the rostrum and in no
    division (seating.SPEAKER_SEAT): the member the roster seats there is the
    Speaker. A member who has left holds no seat, and no office here.

    AND THE OTHER OFFICERS (the person, 9 October 2026: "Sharon Carson is the
    Senate President and should also have some indicator similar to how you
    did the Speaker of the House"). `offices` is build_officers' {member id:
    office} for the sitting members the record names today -- the President
    of the Senate, the Deputy Speaker, the Speaker Pro Tempore -- read from
    the journals and calendars by officers.py. The Speaker is still the
    chair's: build_officers leaves the Speaker out and says so where the
    record and the chair disagree."""
    if m.get("former"):
        return ""
    if m.get("chamber") == "H" and str(m.get("seat") or "") == str(SPEAKER_SEAT):
        return "Speaker of the House"
    return (offices or {}).get(str(m.get("id") or ""), "")


def build_officers(out, votes_by_member, legs, today=None):
    """site/officers.json, and {member id: office} for the sitting members
    who hold one today (member_office).

    WHO PRESIDED, BY THE OFFICE THEY HELD THAT DAY (the person, 9 October
    2026: "he is the deputy speaker and sometimes fills in for Sherman
    Packard if he has other business, as does Jim Kofalt occasionally as
    speaker pro temp"). A roll call records its presiding officer as a
    ballot, "Presiding", and nothing of their office: Rep. Steven Smith
    presided over 257 House roll calls of 2025-2026 and Speaker Packard over
    287. officers.py reads who held each office on which days from the
    journals and the calendars; each tenure is named here as the member of
    that chamber that term it names, by their ballots, and published with
    the surname-first key a roll call's ballots carry ("s"), so that a vote
    card can say "Deputy Speaker of the House" beside the presiding ballot
    of the day it was cast. A tenure that names no member, or more than one,
    is left out and counted here."""
    import officers as OF
    today = today or build_date.today().isoformat()
    tens, mentions, bad = OF.load()
    for e, why in bad:
        print(f"  WARNING: corrections/officials.json legislative_officers: an entry "
              f"left out, {why}: {e}")
    rows, missed = OF.resolve(tens, OF.ballot_people(votes_by_member), legs,
                              OF.term_of(today))
    pub = []
    for r in rows:
        if not r["member_id"]:
            continue
        raw = r["ballot_name"] or (legs.get(r["member_id"]) or {}).get("name") or ""
        if not raw:
            missed.append((r, 0))
            continue
        lab = member_labels(raw, chamber=r["body"])
        pub.append({"b": r["body"], "office": r["office"], "title": r["title"],
                    "name": r["name"], "id": str(r["member_id"]),
                    "s": lab["sort"] or sort_name(raw),
                    "from": r["from"], "to": r["to"], "kind": r["kind"],
                    "source": r["source"]})
    (out / "officers.json").write_text(json.dumps({
        "_about": "Who held the chair's offices -- the Speaker, the Deputy Speaker "
                  "and the Speaker Pro Tempore of the House, and the President of the "
                  "Senate -- from which day (from) until the day before `to`, as the "
                  "House and Senate Journals and the House Calendar on disk say, each "
                  "with the sentence it was read from (source). `s` is the member's "
                  "name as a roll call's ballots sort it, and `id` their member id. "
                  "kind: elected (from the election to the next, within its term), "
                  "term (the one person named in an appointed office that term), day "
                  "(two people named in one appointed office in one term: only the day "
                  "each is named), hand (corrections/officials.json).",
        "officers": pub}, separators=(",", ":")), encoding="utf-8")
    print(f"officers: {len(pub)} tenure(s) -> officers.json, from "
          f"{len(mentions)} mention(s) in the journals and calendars"
          + (f"; {len(missed)} naming no single member of their chamber "
             f"({', '.join(sorted({t['name'] for t, _n in missed}))[:200]})" if missed else ""))
    if not mentions and Path("journals").is_dir():
        print("  WARNING: journals/ is here and no officer was read from it: "
              "officers.py's patterns no longer match the record")

    offices, chair = {}, None
    seated = {str(mid): m for mid, m in legs.items() if not m.get("former")}
    for (body, title), t in OF.holders(tens, mentions, today).items():
        if t.get("member_id"):
            hit = [t["member_id"]] if str(t["member_id"]) in seated else []
        else:
            hit = [mid for mid, m in seated.items()
                   if (m.get("chamber") or "")[:1] == body
                   and OF.same_person(OF._roster_name(m.get("name") or ""), t["name"])]
        if len(hit) != 1:
            print(f"  WARNING: the {t['office']} the record names today, {t['name']}, is "
                  f"{'nobody' if not hit else 'more than one member'} on the roster; "
                  "no page names the office")
            continue
        if title == "Speaker":
            chair = hit[0]
            continue
        offices[str(hit[0])] = t["office"]
    seat = [mid for mid, m in seated.items() if str(m.get("seat") or "") == str(SPEAKER_SEAT)]
    if chair and seat and seat != [chair]:
        print(f"  WARNING: the roster seats {seat} in the Speaker's chair and the record's "
              f"Speaker today is {chair}; the page names the chair's")
    print(f"officers today: {len(offices) + bool(seat)} sitting member(s) whose page "
          "names an office: " + ", ".join(
              f"{seated[mid].get('name')} ({o})" for mid, o in sorted(offices.items())))
    return offices


def build_legislators(out, legs, votes_by_member, towns, unnamed,
                      sponsored=None, bill_year=None, links=None,
                      former=None, offices=None, index_rows=None, manual=None,
                      moved=None, switched=None):
    """One JSON per member, plus the index and the town map.

    Split out of main(). main() was 808 lines even after the station
    builders came out, and the bug that cost 611 bills their facts was two
    different things sharing the name `st` 350 lines apart in this scope.

    `links` is member_links.links(): the numbers a sitting member also voted
    under in the other chamber. `offices` is build_officers' {member id:
    office} for the sitting members the record names in one today.
    `index_rows` is the bill index, {(term, bill): row}, whose chips say
    which of a member's bills passed (member_figures). `manual` is
    manual_seats': {member id: {chamber: [term]}}, the 1989-1998 terms the
    Manual for the General Court seats a member in with no bill that term.
    `moved` is turned_addresses' {sitting id: [addresses]}: the addresses a
    sitting member's page had in a frozen term, which their row carries as
    moved_from for build_pages to answer with a 301, as a former member's
    row does. `switched` is seat_switched's: from the day after
    Organization Day, until the roster turns, each member it names (one not
    returning, as a former member; one elected to another seat, at it) is
    written a second time, after the rest, by the same code -- their own file
    as it will be once the roster turns, their row into site/seat_switch.json
    and not into legislators.json or former.json, which stay as the roster
    and the record give them.
    """
    lg, fm, sw = [], [], []
    # Read off every ballot once, because what one member's attendance needs
    # to know about a roll call -- its day, its chair -- is not in their own.
    attending = attendance_context(votes_by_member)
    print(f"attendance: {len(attending['chair']):,} House roll call(s) naming nobody in "
          f"the chair read as the year's presiding officer's; "
          f"{len(attending['redated'])} misdated ({', '.join(attending['redated'][:4])}); "
          f"{attending['conflicts']:,} declared conflict(s)")
    # The record holds 411 of them, 1999-2019. None at all, over ballots
    # from those years, is a member_votes.json written before build_data
    # flagged them -- and then every one counts as an absence, silently.
    if not attending["conflicts"] and any(
            str(v.get("year") or "9999") < "2020"
            for rows in votes_by_member.values() for v in rows):
        print("  WARNING: no ballot is flagged as a declared conflict of interest; "
              "data/member_votes.json predates rollcall_parser.ballot and counts each "
              "as an absence. Rebuild it: python3 src/parse/build_data.py")
    # ONE CODE PATH FOR BOTH POPULATIONS. The former members go through the
    # same member_labels, the same member_slug and the same per-member JSON as
    # the sitting roster, so every check that guards how a member is named --
    # preflight's "nobody is named surname-first", "a member is named the same
    # way by both namers", "an unnamed member is not dressed up as a person" --
    # applies to them unchanged. Only the list they land in differs, and that
    # is the whole point: former_roster says why. And the members the election
    # moved, last (`switched`): their own file written again over the one just
    # written, their row to the switch's own list.
    for mid, m, as_switched in [*((k, v, False) for k, v in legs.items()),
                                *((k, v, False) for k, v in (former or {}).items()),
                                *((k, v, True) for k, v in
                                  ((switched or {}).get("members") or {}).items())]:
        # A MEMBER WHO CHANGED CHAMBER VOTED UNDER TWO NUMBERS, one for each:
        # Sen. Cindy Rosenwald's page carried 1,399 of her 4,218 votes. A page
        # keeps every chamber the member sat in. Own votes first, so a member
        # nobody is joined to sorts exactly as before. Newest first, by the
        # term and then the day (service_order): 1999-S-109, dated 2009 in
        # the record, headed the whole list of every senator of 1999 who cast
        # it, and now heads their 1999-2000 votes. The day it prints is the
        # record's until the person corrects it (rollcall_corrections.json).
        joined = (links or {}).get(mid, [])
        mv = sorted([v for x in (mid, *joined) for v in votes_by_member.get(x, [])],
                    key=service_order, reverse=True)
        counts = defaultdict(int)
        for v in mv:
            counts[v["vote"]] += 1
        lab = member_labels(m.get("name"), chamber=m.get("chamber"),
                            party=m.get("party_code") or m.get("party"),
                            district=m.get("district"), county=m.get("county"),
                            county_abbr=m.get("county_abbr"))
        # "seat" is the House floor seat, division * 1000 + number, and it is
        # empty for all 24 senators because only the House has a seating
        # chart. build_data says how the number decodes and why it is worth
        # carrying.
        # NO TELEPHONE FOR A LEGISLATOR (the person, 22 October 2026: "some of
        # them list their personal phone numbers which were retrieved from
        # GenCourt"). A member's number is often their own cell, so none is
        # published, on any page or in any download; an office's number -- a
        # clerk's, the Secretary of State's, a committee's, the federal
        # delegation's -- is not a member's and is kept where it is drawn.
        row = {**{k: m.get(k) for k in ("id", "name", "chamber", "party", "county",
                                        "county_abbr", "district", "label", "email",
                                        "url", "url_past", "towns",
                                        "committees", "title", "seat")},
               **lab, "n_votes": len(mv), "counts": dict(counts),
               "n_sponsored": len((sponsored or {}).get(mid, [])),
               "slug": m.get("slug") or member_slug(m, lab)}
        if joined:
            # The numbers this page stands for, as the member's own file lists
            # them: a session day names a mover by the seat their ballots of
            # that term give, and those ballots are under the earlier number
            # (build_session_pages.Members.label, 5 November 2026).
            row["member_ids"] = [mid, *joined]
        if m.get("former"):
            # No email and no telephone, whatever the roster once held: the
            # address belonged to the office. The towns go too -- the town map
            # is today's, and the district they sat for may not exist in it.
            # The seat goes for the same reason as the towns: a House seat is
            # occupied by whoever sits there now, so printing a former
            # member's would name a chair that is somebody else's, and the
            # only seat this disk holds is the current one anyway.
            row.update({"former": True, "served": m.get("served") or {},
                        "email": "", "towns": [],
                        "committees": [], "seat": ""})
            if m.get("moved_from"):
                # The addresses of the pages this one took in (former_movers),
                # which build_pages answers with a 301 to this one.
                row["moved_from"] = list(m["moved_from"])
            if joined:
                # EACH CHAMBER'S YEARS, for the lists that name a former
                # member's seat and years (the directory, the site search):
                # the one row of a member whose page joins two chambers gave
                # every year under the last seat, "Sen. Jeb Bradley R, SD3,
                # 1999-2024" of a senator whose 1999-2002 were in the House
                # (the deep walk of 6 November 2026). As their own file gives
                # them (`both`, below).
                row["service"] = ML.service(mv)
            (sw if as_switched else fm).append(row)
        else:
            if (moved or {}).get(mid):
                # The addresses this page had in a frozen term (turned_addresses),
                # which build_pages answers with a 301 to this one.
                row["moved_from"] = list(moved[mid])
            (sw if as_switched else lg).append(row)
        # What they put their name to. The page's own meta description has
        # promised "sponsored bills" since it was written and the file did not
        # carry them, so the page could not show them and a search engine was
        # being told about a section that does not exist.
        #
        # Prime sponsorship first, then the rest: a member's own bills are the
        # ones they are asked about. Within each, OLDEST year first -- this
        # said "newest first" over code that has always run oldest first --
        # and then by number as bills.html lists them. The number was compared
        # as text, so HB436 was listed before HB61.
        raw = (sponsored or {}).get(mid, [])
        # The terms before 1999 that the sponsor record places them in, by chamber: the
        # "On Record" line covers them as the TERM picker does (ML.record_spans).
        # AND THE ONES THE MANUAL FOR THE GENERAL COURT SEATS THEM IN WITH NO BILL THAT TERM
        # (manual_seats; the owner, 14 November 2026), in the Manual's chamber: past_terms is
        # both, and manual_terms, in their own file, the Manual's alone, so a check can tell
        # them apart. The TERM picker still lists the terms of their bills.
        from_manual = (manual or {}).get(mid) or {}
        of_bills = ML.earlier_terms(raw)
        earlier = {ch: sorted(set(of_bills.get(ch, ())) | set(from_manual.get(ch, ())))
                   for ch in sorted(set(of_bills) | set(from_manual))}
        if earlier:
            row["past_terms"] = earlier
        mine = sponsored_in_order([{k: v for k, v in e.items() if k != "ch"} for e in raw])
        # Which numbers the votes below were cast under, and the years in each
        # chamber, for the page to say why a senator's list has House votes in
        # it. Only where there are two: everyone else's file is as it was.
        both = ({"member_ids": [mid, *joined], "service": ML.service(mv)}
                if joined else {})
        # AND ONE THE ELECTION SENT TO THE OTHER CHAMBER (seat_switched): their votes are
        # the chamber they sat in, which the page says by chamber, as it will once the
        # roster joins their new number to this one -- not the Senate's years of a House
        # record.
        if as_switched and not joined and \
                str(m.get("chamber") or "") != str((legs.get(mid) or m).get("chamber") or ""):
            both = {"service": ML.service(mv)}
        office = member_office(m, offices)
        att = member_attendance(mv, attending)
        (out / "legislators" / f"{mid}.json").write_text(json.dumps({
            **m, **lab, "counts": dict(counts), **both,
            # The page's own address, as the roster row has it: the member's
            # page finds their next session's requests by it (build_lsrs'
            # sponsor_slug; Alice, 7 November 2026).
            "slug": row["slug"],
            **({"office": office} if office else {}),
            # In the member's own file and nowhere else: not in the `row`
            # above, which is what the legislators page, the town pages and
            # every other listing read. It is a figure on their own page, not
            # a column anyone is sorted by.
            "attendance": att,
            **({"past_terms": earlier} if earlier else {}),
            **({"manual_terms": from_manual} if from_manual else {}),
            # EACH TERM AT A GLANCE (member_figures.term_figures), as the
            # person ordered it on 9 October 2026 (item 7 and v7): the
            # session days attended, the roll calls recorded on, the bills
            # filed and the bills passed -- filed and passed counting prime
            # and co-sponsored bills together, passed the bill search's.
            "term_figures": MF.term_figures(mine, att, index_rows or {}),
            "n_sponsored": len(mine),
            "n_prime": sum(1 for x in mine if x["prime"]),
            "sponsored": mine,
            # y is the bill's FILING year, which is what its address is under
            # -- a 2025 bill voted on in 2026 lives at /bill/2025/. Without it
            # the page had to guess the year from the bill number, and a
            # number that exists in two terms was resolved to whichever came
            # first in the index.
            # k names the roll call this vote was cast in, in the
            # shape main() already keys them by. It is what lets the page
            # look up what the vote decided without all 406 member files
            # carrying their own copy of that.
            "votes": [{"d": v["date"], "b": v["bill"], "q": v["question"],
                       "v": v["vote"],
                       "k": (f'{v["year"]}-{v["body"]}-{v["vote_number"]}'),
                       "y": (bill_year or {}).get(
                           (P.vote_term(v.get("year", ""), v.get("date")), v["bill"]), "")}
                      for v in mv],
        }), encoding="utf-8")
    if unnamed:
        print(f"{len(unnamed):,} member id(s) still have no name and appear as "
              '"Member #id" in roll calls:')
        print("  " + ", ".join(sorted(unnamed)[:12])
              + (" ..." if len(unnamed) > 12 else ""))
        # A six-digit id is an Employeeno that build_data fell back to because
        # the legislators table has no row for that person -- not a PersonID
        # nobody has looked up yet. fetch_members_db.py has already read every
        # inactive legislator the database holds, so re-running it will not
        # name these; the General Court's own roster does not carry them.
        #
        # resolve_members.py could, in principle: rc_yeahnay.aspx lists the
        # names who voted each way, and the leftovers after removing everyone
        # identified must be these people. It reads the current session's
        # RollCallHistory.txt only, and skips a blank id outright, so it needs
        # both of those changed first. Three members of the 2023-2024 House,
        # 1,470 votes, is what that would buy.
        orphans = [u for u in unnamed if u.isdigit() and len(u) >= 6]
        if orphans:
            print(f"  {len(orphans)} of these are an Employeeno, used because "
                  "the legislators table")
            print("  has no row for them at all. fetch_members_db.py has read "
                  "every inactive")
            print("  member it holds, so it will not name them; only "
                  "rc_yeahnay.aspx would.")
        if len(orphans) < len(unnamed):
            print("  The rest are PersonIDs: run fetch_members_db.py, which "
                  "writes")
            print("  former_members.json, then build_data.py, which reads it.")
    (out / "legislators.json").write_text(json.dumps(lg), encoding="utf-8")
    # Its own file, never merged into the one above. See former_roster.
    (out / "former.json").write_text(json.dumps(fm), encoding="utf-8")
    # THE SEATS AS THE ELECTION LEFT THEM (seat_switched), from the day after
    # Organization Day until the roster turns, and no file otherwise: site/ is
    # never emptied, and a file a night before left would draw a switch the
    # roster has since made itself.
    swp = out / SEAT_SWITCH
    if (switched or {}).get("members"):
        ids = set((switched.get("leaving") or {}))
        swp.write_text(json.dumps({
            "day": switched.get("day"), "election": switched.get("election"),
            "term": switched.get("term"),
            "leaving": [r for r in sw if str(r.get("id")) in ids],
            "moved": [r for r in sw if str(r.get("id")) not in ids]}), encoding="utf-8")
        print(f"the seats as the {switched.get('election')} election left them, from "
              f"{switched.get('day')}: {sum(1 for r in sw if str(r.get('id')) in ids)} member(s) "
              f"not returning drawn as former members, {sum(1 for r in sw if str(r.get('id')) not in ids)} "
              f"at the seat they were elected to (their own pages and the search; "
              f"legislators.json is the roster's {len(lg):,}) -> {swp.as_posix()}")
    elif swp.exists():
        swp.unlink()
        print(f"  {swp.as_posix()}: removed -- the site no longer switches by date (before the "
              "day after Organization Day, or the roster has turned)")
    (out / "towns.json").write_text(json.dumps(towns), encoding="utf-8")
    print(f"{len(lg):,} legislator pages, {len(towns):,} towns")
    if fm:
        print(f"{len(fm):,} former member(s) -> former.json "
              f"({sum(x['n_votes'] for x in fm):,} votes, "
              f"{sum(x['n_sponsored'] for x in fm):,} sponsorships now linkable)")
    return lg
