#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
What the page builders share: the pieces more than one builder draws a page
with, kept here rather than inside one builder that the others import.

    import parts as P
    P.cal_days(...)            # a day of the Calendar's cards (build_pages, build_calendar, build_live)
    P.meeting_key(row)         # what one meeting is made of (the Calendar, Latest activity)
    P.party_word("Democrat", "es", plural=True)
    P.district_tag("H", "07", "Carroll")   # "Carr 7"
    P.tel(num), P.maillink(addr), P.weblink(url)   # the town pages and the Officials tabs
    P.TABS_JS                  # the tab strip's script (the town pages, Legislators, the Learn hub)

WHY THIS MODULE (the refactor's stage 3, 19 November 2026). These were the
builders' own -- build_pages' calendar cards, Latest activity's sizes and
party word, build_site_v2's district tag, build_town_pages' links and tab
script -- and the other builders imported them from there: build_calendar
and build_live imported build_pages whole, officials_tabs three builders,
build_town_pages build_pages. So the builders imported one another, and with
i18n's translation audit thirty modules of src/pages were one import cycle
(reports/refactor/stage0-code.md, section 2). Each was moved here as it stood,
body and comments, and is still named where it was (build_pages.cal_days,
build_site_v2.district_tag, build_town_pages.tel, ...), so nothing that reads
the old name changed. A builder imports this module; this module imports no
builder at load (committee_codes asks build_committees for today's committees
only when it is handed the data to ask with).

Each part keeps the comments that say why it is as it is; the section a part
came from is named above it.
"""

import json
import re
from collections import OrderedDict, namedtuple
from pathlib import Path

import bill_order as BO
import i18n
import plain_action as PA
import shell as S
import state_settings as ST
from components import WORDBOOK, chip, clock
from i18n import say
# The parser's test for an e-mail address, so that what it accepts from a
# threaded cell and what a page links are the same test.
from parse_officials import EMAIL_OK

E = S.E


# ---- from build_pages: Latest activity's sizes ---------------------------------------------

# How much of Latest activity the home page shows, and where the rest is.
# Five is a glance; the twelve it showed before was most of a phone screen for
# a list nobody reads to the end. The overflow goes to the bill search, which
# sorts by most recent action and does it better than a table can.
# FOUR MEETINGS NOW, NOT FIVE DOCKET LINES (the person, 24 October 2026;
# latest_activity.py), and THREE BILLS OF EACH, then "and N more", which
# leads to the meeting: a House sitting takes up a hundred bills and a
# committee's day twenty. Four, because that is what keeps the box the height
# it was: drawn from the data of 24 October 2026 in the 248px rail of a
# 1280px window, the five docket lines stood 1,258px tall, four meetings stand
# 1,317 and five 1,645, their interim study reports' words wrapping in the
# narrow column.
# AND EVERY BILL OF EACH, IN A CARD THAT OPENS (the owner, the same evening:
# "formatted similarly to the coming up page ... with the ability to click it
# for a dropdown to list all the bills from that session"). A card shut is two
# lines, so four meetings stand shorter than before; open, it lists every bill
# the meeting took up, up to RECENT_BILLS -- which latest_activity keeps in
# home.json for the meetings shown, and eight for the rest -- and "and N
# more" past that, which only a House sitting reaches.
RECENT_SHOWN = 4
RECENT_BILLS = 40


# ---- from build_pages: the kinds of meeting, a meeting's key, a card's name and links ------

# THE KINDS OF MEETING: the schedule's word, lower case, to what a reader sees
# and the class that colours it. THE COLOURS ARE THE GENERAL COURT'S OWN,
# because staff already read its schedule by them: blue a hearing, green a
# work session, orange an executive session, red a committee of conference
# -- the legend fetch_schedule.py quotes; the floor has one of its own, a
# study or statutory committee its own raspberry (the person, 25 September
# 2026), and a kind not named keeps the neutral k-other. The table is words,
# written once since 9 October 2026 (the component plan's C3): it is
# src/pages/words/meeting_kinds.json, whose notes say the rest, and app.js draws
# a committee's calendar with the same file, from components.js. It was a
# table here and another in app.js, held alike by a check that read both.
MEET_KIND = {k: tuple(v) for k, v in WORDBOOK["meeting_kinds"]["kinds"].items()}

# THE CHIPS ARE NAMES TOO, in title case like the boxes above the schedule
# (the person, 25 September 2026: capitalise the chips to match). A kind the
# table does not know -- "cancelled", or a phrase the docket invents -- is
# set the same way, its small words left small: "Committee of Conference".
# The small words are meeting_kinds.json's, which app.js's kindTitle reads too.
_SMALL = frozenset(WORDBOOK["meeting_kinds"]["small"])


def kind_title(k):
    words = (k or "").split()
    return " ".join(w if (i and w.lower() in _SMALL) or not w[:1].isalpha()
                    else w[:1].upper() + w[1:] for i, w in enumerate(words)) or "Meeting"

# THE KEY, each colour once, in the order the Calendar's row of boxes has
# them -- which is the key, and the filter, above its schedule. Names, so in
# title case, as the person asked on 25 September 2026: "Public Hearing or
# Executive Session". "Work Session" also covers the chamber committees'
# other meetings, and "Study Committee" the statutory ones, whose chips
# say which they are. meeting_kinds.json's "legend".
MEET_LEGEND = tuple(tuple(kc) for kc in WORDBOOK["meeting_kinds"]["legend"])


# The record's own words on a page in another language are marked as
# English (i18n.py, the first kind).
EN_ATTR = ' lang="en"'


def kind_word(k, lang="en"):
    """(the words a chip says for the schedule's kind `k`, its colour's
    class): MEET_KIND's, in `lang` (i18n.say_word, keyed by the English, so
    words/meeting_kinds.json changing a word asks for its translation)."""
    word, kcls = MEET_KIND.get((k or "").strip().lower(), (kind_title(k), ""))
    # The docket's own "cancelled" is not in the table of kinds, and the
    # Calendar's script knows the chip by this word (build_calendar.WEEK_ES).
    if lang != i18n.DEFAULT and word == "Cancelled":
        return say(lang, "calp.cancelled", "Cancelled"), kcls
    return i18n.say_word(lang, "kind", word), kcls


def clock_span(a, b, lang="en"):
    """"10:00 AM–12:15 PM" -- a sitting from its first item to its last,
    which is how the General Court prints one -- or one time where the two
    are the same."""
    return clock(a, lang) if a == b else f"{clock(a, lang)}–{clock(b, lang)}"


# What a calendar card is keyed on; see meeting_key. A named tuple so the
# code reading one says which part it means: `key.chamber` is "H", "S" or ""
# (a study committee, a conference), and `key.bill` is empty except on a
# committee of conference, which is one bill's.
Meet = namedtuple("Meet", "date chamber name bill")
CHAMBER_WORD = {"H": "House", "S": "Senate"}
CONFERENCE = "Committee of conference"


def meeting_key(u):
    """What makes one meeting out of a handful of `upcoming` bill rows.

    ONE DEFINITION, BECAUSE TWO PLACES COUNT IT. The calendar groups by this
    tuple and the status box above it states the number of groups; when the
    grouping lived only inside calendar_html the box counted the rows instead
    and said "39 hearings scheduled in the next two weeks" over a fortnight
    holding eight meetings -- and no hearing at all. Nothing can drift now
    without moving both.

    NOT THE TIME. The docket gives every BILL its own slot inside a meeting --
    Executive Departments on 21 January runs 09:00, 09:10, 09:20 and on down
    its fifteen bills -- so a key holding the time made one meeting into one
    card per bill. The busiest week of 2026 came out as 356 meetings where it
    holds 68, and a committee that had set aside a morning read as fifteen
    committees that each met for ten minutes.

    It has not shown yet because the fortnight this draws is out of session
    and its meetings carry a bill or two each. January is when it would have
    shown, on the page that gets the most readers, in the month that gets the
    most of them. The card states the span instead, 09:00-13:50, which is
    what the General Court's own schedule prints.

    NOR THE KIND. A committee that holds a public hearing in the morning and
    an executive session after it has had one day, not two, and a reader
    scanning a week wants to see the committee once: "they should only take
    up one entry and just list all of the scheduled items in order." Keyed on
    the kind it appeared twice, which across the record since 2025 is 1,452
    entries where the room holds 1,007 -- 34% of committee-days do more than
    one thing.

    The kinds are not lost, they are shown differently: the card carries a
    divided colour bar, one segment per kind, and its body lists the day's
    items in order with the time each was set for.

    NOR THE ROOM. Two rooms looked like two meetings until a real day said
    otherwise: Ways and Means on 30 September is a subcommittee at 09:30 in
    GP 228, then the full committee at 10:00 and 10:30 in GP 234. That is one
    committee having one working day, and a reader scanning the week wants it
    once. The room is a property of each item, not of the entry, and is shown
    on the line it belongs to -- with the entry naming it once when every item
    shares it.

    So the key is the day and the committee, and nothing else -- where "the
    committee" is a committee in full, which for most of them means its
    chamber as well as its name.

    THE CHAMBER, BECAUSE A NAME IS NOT A COMMITTEE. Both chambers have a
    Finance, a Judiciary, a Ways and Means, a Transportation, an Executive
    Departments and Administration and a Children and Family Law. Keyed on
    the name alone, the two sitting on one day became one card: 28 January
    2025's "Finance" held House Finance's work session on HB 519 in LOB
    210-211 and Senate Finance's hearings on SB 64, 113, 114 and 117 in SH
    103, under one name and one link -- and 50 cards on the calendar were
    two chambers' committees drawn as one. So a chamber's committee is keyed
    on (chamber, name), and the card names its chamber.

    A study or statutory committee has no chamber: the database copy's row
    carries none, and the docket's row for a bill that set one up carries
    the BILL's chamber, which must not split the one meeting into two.

    A COMMITTEE OF CONFERENCE IS ONE BILL'S, AND BOTH CHAMBERS'. House Rule
    50, as the House Calendar prints it each June: "The House and Senate
    Conferees on a bill shall meet jointly but vote separately while in
    conference", and the first-named conferee of the bill's own chamber sets
    the time and place. Each bill has its own conferees, its own notice on
    its own docket -- "Conference Committee Meeting: 06/16/2025 09:30 am LOB
    206-208" on HB 485, 02:00 pm on HB 273 -- and its own report. So a
    conference is keyed on the bill, with no chamber and whatever name the
    row carries: one card per bill's conference per day. The Senate docket's
    notice names no committee -- "Committee of Conference Meeting:
    06/16/2025, 12:00 pm, Room 100, SH" on SB 14 -- yet the row came to carry
    the bill's Senate committee, and keyed on that name SB 14's conference
    was drawn as a sitting of Senate Judiciary, linked to that committee's
    page, and a second time from its recording. Per day would be one card for every conference in
    the building, which is the mistake above made across a whole corridor:
    the docket noticed 33 for 26 May 2026, each at its own time, in nine
    rooms.
    """
    date = u.get("date") or ""
    what = (u.get("what") or u.get("kind") or "").strip().lower()
    if what == "committee of conference":
        return Meet(date, "", CONFERENCE, (u.get("bill") or "").strip().upper())
    name = u.get("committee") or ""
    if u.get("study") or what in ("study committee", "statutory committee"):
        return Meet(date, "", name, "")
    return Meet(date, (u.get("body") or "").strip().upper(), name, "")


def is_conference(key):
    return key.name == CONFERENCE


# The floor's cards, by the name build_calendar.FLOOR keys them on.
FLOOR_CARD = {"house floor": "House Session Day", "senate floor": "Senate Session Day"}


def card_name(key, lang="en"):
    """What a card calls its committee: "House Judiciary", "Senate Finance",
    "Committee of conference on HB 2", "Commission on Aging", "House Session
    Day".

    THE CHAMBER IS SAID, on every chamber's committee and not only on the
    names both chambers use: a card reading "Commerce" beside one reading
    "Senate Finance" would leave a reader to guess whose Commerce it is. It
    is how the General Court's own schedule titles them -- "House Ways and
    Means : GP, Room 234". The floor and the sittings whose committee the
    docket did not record already say it, and are not told twice.

    THE FLOOR IS A SESSION DAY (the person, 9 October 2026: "Session day
    should be Session Day"). Its card said "House floor", the key the week
    is grouped on, over a chip saying Floor Session; the approved Calendar
    calls it "House Session Day", and the key stays "House floor" for every
    lookup made on it (build_calendar.FLOOR, the floor's links below).
    """
    if is_conference(key):
        num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", key.bill)
        if lang != i18n.DEFAULT:
            return (say(lang, "cal.conference_on", "Committee of conference on {bill}", bill=num)
                    if num else say(lang, "cal.conference", "Committee of conference"))
        return f"{CONFERENCE} on {num}" if num else CONFERENCE
    if key.name.strip().lower() in FLOOR_CARD:
        if lang != i18n.DEFAULT:
            return (say(lang, "cal.house_day", "House Session Day")
                    if key.name.strip().lower() == "house floor"
                    else say(lang, "cal.senate_day", "Senate Session Day"))
        return FLOOR_CARD[key.name.strip().lower()]
    word = CHAMBER_WORD.get(key.chamber)
    first = (key.name.split() or [""])[0]
    if word and first not in CHAMBER_WORD.values():
        return f"{word} {key.name}"
    return key.name


def pick_name(key):
    """The committee as the Calendar page's picker lists it: the card's own
    name, except that every committee of conference is one entry. A reader
    who asks for the conferences wants them all, not a list of eighty bills."""
    return CONFERENCE if is_conference(key) else card_name(key)


def card_bodies(key, rows):
    """The chambers a card is filtered under. A committee of conference is
    both chambers' by rule, whichever of them called it; anything else is the
    chambers its rows record."""
    if is_conference(key):
        return ["H", "S"]
    return sorted({(r.get("body") or "").strip().upper()
                   for r in rows if (r.get("body") or "").strip()})


def committee_codes(site, data=None):
    """{(chamber, lower-cased name): code} out of site/committees.json, for
    a card's link to its committee's page.

    ON THE CHAMBER AS WELL AS THE NAME. Keyed on the name alone, the second
    of two committees of one name overwrote the first, so every House
    Finance, Judiciary, Ways and Means, Transportation, Executive
    Departments and Administration and Children and Family Law card linked
    to the Senate committee's page -- 168 cards, House Judiciary of 15
    January 2025 among them, sent to committee/S10.
    """
    # FROM THE STEP THAT KNOWS FIRST, WHERE `data` IS GIVEN (10 October
    # 2026): build_committees' own reading of today's committees, which no
    # later step writes, so a build into an empty site links its Coming Up
    # cards as a warm one does; last night's committees.json, where it is
    # here, fills in after it. The home page asks for it (main); the calendar,
    # which runs after build_committees, reads the file it wrote. Asked for
    # only where `data` is named, because the folder is the real data's: a
    # caller holding the map to a committees.json of its own (preflight's
    # _calendar_chambers) got every real committee as well, on GitHub's
    # machine and not on a clone without data.
    code = {}
    try:
        if data is None:
            raise LookupError("not asked for")
        import build_committees as BC
        code.update(BC.page_codes(site, data))
    except LookupError:
        pass
    except Exception as e:   # noqa: BLE001 -- the cards keep their words, unlinked
        print(f"  committee links: build_committees could not be read ({e}); "
              "falling back to site/committees.json")
    cf = Path(site) / "committees.json"
    if cf.exists():
        try:
            for c in json.loads(cf.read_text(encoding="utf-8")):
                if c.get("name") and c.get("code"):
                    code.setdefault(((c.get("chamber") or "").strip().upper(),
                                     c["name"].strip().lower()), c["code"])
        except (ValueError, OSError):
            pass
    return code


# ---- from build_pages: a party's word ------------------------------------------------------

def party_word(name, lang="en", plural=False):
    """A party's name as the roster spells it ("Republican", "Democrat"), in
    `lang`, singular or plural; a name not here, as it came."""
    one = {"Republican": say(lang, "party.r", "Republican"),
           "Democrat": say(lang, "party.d", "Democrat"),
           "Democratic": say(lang, "party.dem", "Democratic"),
           "Independent": say(lang, "party.i", "Independent"),
           "Libertarian": say(lang, "party.l", "Libertarian"),
           "Party not on file": say(lang, "party.none", "Party not on file")}
    many = {"Republican": say(lang, "party.rs", "Republicans"),
            "Democrat": say(lang, "party.ds", "Democrats"),
            "Democratic": say(lang, "party.ds", "Democrats"),
            "Independent": say(lang, "party.is", "Independents"),
            "Libertarian": say(lang, "party.ls", "Libertarians")}
    return (many if plural else one).get(name, one.get(name, name) if plural else name)


# ---- from build_pages: a day of the Calendar's cards ---------------------------------------

def is_cancelled(rows):
    """True when every row of a card is a cancelled meeting.

    ONE DEFINITION, BECAUSE TWO PLACES USE IT: the card marks itself
    data-cancelled from this, and the week's lead leaves the same cards out
    of its count. A cancelled meeting is shown, so a reader who saw it
    noticed can see it did not happen, and it is not a sitting -- counting
    it said "22 sittings" of a week of 2025 in which 21 met.
    """
    return bool(rows) and all((r.get("what") or "").lower() == "cancelled"
                              for r in rows)


def meeting_who(cmte, rows):
    """Who is meeting: "floor", "study" or "standing".

    For the Calendar page's filters, which ask who and what separately. The
    floor is the House or the Senate sitting as a whole. A study or statutory
    committee is one the database copy says is one, or one the docket files
    as a "study committee" sitting -- HB 1763's committee on 2 September 2026
    reached the calendar through the docket alone. Everything else is a
    chamber's own committee: the standing committees, a committee of
    conference drawn from them, and the sittings whose committee the docket
    did not record.
    """
    if (cmte or "").strip().lower() in ("house floor", "senate floor"):
        return "floor"
    if any(r.get("study") or (r.get("what") or "").strip().lower()
           in ("study committee", "statutory committee") for r in rows):
        return "study"
    return "standing"


def cal_days(days, meets, titles, years, code, when, esc, level=3,
             sessions=None, docs=None, lang="en", events=None, kd_full=True, morning=""):
    """The day blocks and their meeting cards, for any set of days.

    Split out of calendar_html on 18 September so the calendar PAGE draws the
    same cards from the same grouping. meeting_key already exists because two
    places counted meetings and disagreed; a second renderer drawing something
    that merely looked like these would be the same mistake in markup.

    THE KEY DATES OF A DAY COME FIRST (the owner, 24 October 2026: "Coming
    up should list major events like the election days, town meeting days,
    organization day, etc and those dates should show up on the calendar
    page too"). `events` is key_dates.days(): {day: [(key date, role)]}.
    Each is a card of its own class, which opens on its sentence and source,
    on the Calendar and in Coming up alike (the owner, 24 October 2026: "in
    the same format, just color coded"); it was a plain line in Coming up
    until that evening. Neither is a meeting: a day holding only a key date
    still says it has no meetings on the Calendar (`kd_full`), and is not a
    calnone day.
    """
    import key_dates as KD
    events = events or {}
    # THE DAY'S HEADING LEVEL IS THE CALLER'S TO SAY. On the home page these
    # sit under "Coming up", an h2, so they are h3. On a week's own page the
    # h1 IS the week, and an h3 under it skips a level -- which is a depth,
    # not a size, and a screen reader reads it as a missing section.
    h = f"h{level}"
    html, missing = [], 0
    for date, keys in days.items():
        label, rel = when(date)
        # THE DAY'S OWN DATE TRAVELS WITH IT. This block is written when the
        # site is built and read for as long as the build stands, so the home
        # page has called a past day "today", with a meeting that had already
        # happened at the top of Coming up. HOME_JS
        # reads this attribute in the reader's own clock, drops the days that
        # have passed and writes the relative word again.
        # THE DATE AND HOW FAR OFF IT IS, and nothing else. The day's span
        # was briefly here, on 20 September, to spare the cards a line; the
        # card carries its own time again now -- beside its bill count, which
        # is the more compact place for it -- so a span here would be the
        # same string twice.
        # A DAY WITH NOTHING ON IT, which only the week page passes: it lists
        # every weekday so a quiet one reads as quiet rather than as missing.
        # Its own class, so the week's filter never hides a line that is true
        # under any filter, and the home rail's reader of `class="calday"`
        # never counts it.
        kds = events.get(date) or []
        html.append(f'<div class="calday{"" if keys or kds else " calnone"}" '
                    f'data-d="{esc(date)}"><{h} class="caldate">'
                    f'<span>{esc(label)}</span>'
                    f'<span class="cdrel">{esc(rel)}</span>'
                    + f"</{h}>")
        html += [KD.card_html(e, role, date, lang) for e, role in kds]
        if not keys:
            if kd_full or not kds:
                html.append(f'<p class="calempty">{say(lang, "cal.empty", "No meetings scheduled.")}</p>')
            html.append("</div>")
            continue
        for key in keys:
            # THE NAME THE CARD PRINTS, with its chamber: two committees of
            # one name on one day are two cards now, and each has to say
            # which it is. The key's own name is the committee's, for the
            # links and the questions asked about it below.
            _d, cmte = key.date, card_name(key)
            # In another language the card's name is the page's words for a
            # session day or a conference, and the committee's own name
            # otherwise, which is the record's and stays English.
            shown = card_name(key, lang)
            own_name = lang != i18n.DEFAULT and shown == cmte
            rows = meets[key]
            # THE DAY'S ITEMS, IN ORDER. One entry can hold a hearing, a work
            # session and an executive session, so the body is a little
            # schedule rather than a flat list of bills: each slot keeps the
            # time it was set for and says what kind of sitting it is.
            # Inside a slot, by number as bills.html lists them. Without the
            # last key a slot kept proceedings.csv's order, which is the
            # number's text: HB 101, HB 110, HB 78.
            slotted = OrderedDict()
            for r in sorted(rows, key=lambda x: ((x.get("time") or "~"),
                                                 (x.get("what") or ""),
                                                 (x.get("venue") or ""),
                                                 BO.bill_key((x.get("bill") or "").strip()))):
                slotted.setdefault(((r.get("time") or ""),
                                    (r.get("what") or ""),
                                    (r.get("venue") or "")), []).append(r)
            kinds, rooms = [], []
            for _tm, wk, vn in slotted:
                if wk not in kinds:
                    kinds.append(wk)
                if vn and vn not in rooms:
                    rooms.append(vn)
            venue = rooms[0] if len(rooms) == 1 else ""
            # THE SPAN, NOT A SLOT. Each row is one bill with its own place in
            # the meeting, so the meeting runs from the first to the last --
            # which is how the General Court prints it, 10:00am - 3:30pm. A
            # meeting whose bills all share one slot states it once. In the
            # twelve-hour clock a reader uses (clock); the record's own
            # "10:00" stays in data-time and data-last below.
            slots = sorted(x for x in (r.get("time") or "" for r in rows) if x)
            time = clock_span(slots[0], slots[-1], lang) if slots else ""
            # BILLS, NOT ROWS. A study or statutory committee's meeting is a
            # row with no bill, and counting rows called it "(1 bill)".
            # AND EACH BILL ONCE. A bill heard and then voted on the same day
            # is two items on the card and one bill: House Housing on 21
            # January 2025 heard eight bills and voted on five of them after,
            # and its card said "(13 bills)" over the eight it lists. 250 of
            # the 1,883 cards since January 2025 stated more bills than they
            # held, House Commerce's of 18 February 2026 "(53 bills)" over 37.
            # The items stay two, each in its own slot; the count is of the
            # bills.
            n = len({(r.get("bill") or "").strip().upper() for r in rows
                     if (r.get("bill") or "").strip()})
            # A study or statutory committee's card says so, for the week
            # page's toggle; a cancelled one says that, so it is not offered
            # for anybody's own calendar.
            study = any(r.get("study") for r in rows)
            cancelled = is_cancelled(rows)
            # WHAT A FILTER NEEDS, ON THE CARD ITSELF. The week page is static
            # HTML on a CDN and the filtering happens in the reader's browser,
            # so each card states its own chamber, committee and bills rather
            # than the page shipping a second copy of the week as JSON. A
            # reader with no script still gets every card, which is the whole
            # week and the correct answer to no filter at all.
            bodies = card_bodies(key, rows)
            bills_attr = " ".join(sorted({(r.get("bill") or "").strip().upper()
                                          for r in rows if r.get("bill")}))
            # THE MIXED COLOUR. One segment per kind the day holds, stacked
            # down the edge of the card, so a committee doing two things reads
            # at a glance as one committee doing two things rather than as two
            # committees. Segments rather than a gradient, so the colours stay
            # in the stylesheet and both themes keep working.
            # DEDUPED ON THE COLOUR, not on the kind's name. A full committee
            # work session and a subcommittee work session are two kinds and
            # one colour, and drawn per kind the bar showed two identical
            # segments, which reads as two things rather than one.
            bars = []
            for k in kinds:
                cls = MEET_KIND.get(k.strip().lower(), ("", ""))[1] or "k-other"
                if cls not in bars:
                    bars.append(cls)
            html.append('<details class="calmeet"'
                        f' data-body="{esc(" ".join(bodies))}"'
                        f' data-cmte="{esc(cmte.lower())}"'
                        # THE PICKER'S NAME, where it is not the card's own:
                        # the committees of conference are one entry there.
                        + (f' data-pick="{esc(pick_name(key))}"'
                           if pick_name(key) != cmte else "")
                        + f' data-bills="{esc(bills_attr)}"'
                        f' data-date="{esc(_d)}"'
                        + (f' data-time="{esc(slots[0])}"' if slots else "")
                        + (f' data-last="{esc(slots[-1])}"' if slots else "")
                        + (f' data-venue="{esc(PA.place(venue))}"' if venue else "")
                        + (' data-study=""' if study else "")
                        + (' data-cancelled=""' if cancelled else "")
                        # WHO AND WHAT, for the Calendar page's filters: whose
                        # sitting it is, and the kinds its bar is drawn in
                        # (hearing, meet, exec, conf, floor, other). The same
                        # colours as the bar, because they are the bar.
                        + f' data-who="{esc(meeting_who(key.name, rows))}"'
                        + f' data-kinds="{esc(" ".join(b[2:] for b in bars))}"'
                        + "><summary>")
            html.append('<span class="calmix" aria-hidden="true">'
                        + "".join(f'<i class="{c}"></i>' for c in bars) + "</span>")
            # THE COMMITTEE FIRST. It is what a reader scans a rail for, and
            # putting the time ahead of it meant the rail's card spent its
            # first line on four digits. The time follows, beside the bill
            # count, so the two read as one phrase about that sitting:
            # "Ways and Means / 09:30-10:30 (11 bills)".
            html.append(f'<span class="calcmte"{EN_ATTR if own_name else ""}>{esc(shown)}</span>')
            if time:
                html.append(f'<span class="caltime">{esc(time)}</span>')
            # THE COUNT DIRECTLY AFTER THE TIME, not after the kind. The
            # parentheses only work while the two are adjacent -- with the
            # kind chip between them the rail read "09:30-11:30 Subcommittee
            # work session (5 bills)", a bracket around nothing in
            # particular. On its own where there is no time, for the same
            # reason.
            _bills = (say(lang, "cal.one_bill", "1 bill") if n == 1
                      else say(lang, "cal.n_bills", "{n} bills", n=n))
            if n:
                html.append(f'<span class="calcount">'
                            + (f"({_bills})" if time else _bills) + "</span>")
            # A SESSION DAY'S NAME SAYS WHAT IT IS ("House Session Day"), so
            # no chip says "Session Day" again under it, as the approved
            # Calendar has it (9 October 2026); its bar keeps the colour.
            for k in ([] if key.name.strip().lower() in FLOOR_CARD else kinds):
                word, kcls = kind_word(k, lang)
                html.append(chip(word, f"calkind {kcls}"))
            # THE ROOM IN WORDS (the audit of 25 October 2026, S7): "Granite
            # Place 231" for the clerk's "GP 231", as app.js's calendarBlock
            # says it (roomWords) and a bill's Hearings tab always has.
            if venue:
                html.append(f'<span class="calwhere">{esc(PA.place(venue))}</span>')
            html.append('<span class="caret"></span></summary>'
                        '<div class="calbody">')
            one = len(slotted) == 1
            for (tm, wk, vn), items in slotted.items():
                word, kcls = kind_word(wk, lang)
                if not one:
                    html.append('<p class="calslot">'
                                + (f'<span class="caltime">{esc(clock(tm, lang))}</span>' if tm else "")
                                + chip(word, f"calkind {kcls}")
                                + (f'<span class="calwhere">{esc(PA.place(vn))}</span>'
                                   if vn and not venue else "") + "</p>")
                # A ROW WITH NO BILL is a study or statutory committee's
                # meeting: it says what kind of meeting and what set the
                # committee up, as text, and links nowhere -- there is no
                # page here for a commission to lead to.
                # ONCE: the database holds some meetings twice -- the Land and
                # Community Heritage Authority's board on 16 November 2026 is
                # meetings 2941 and 2942 -- and the card said its note twice.
                for note in OrderedDict.fromkeys(
                        r["note"] for r in items
                        if not (r.get("bill") or "").strip() and r.get("note")):
                    html.append(f'<p class="calnote"{EN_ATTR if lang != i18n.DEFAULT else ""}>'
                                f'{esc(note)}</p>')
                items = [r for r in items if (r.get("bill") or "").strip()]
                if not items:
                    continue
                html.append('<ul class="calbills">')
                for r in items:
                    bid = (r.get("bill") or "").strip()
                    yr, ti = years.get(bid), titles.get(bid)
                    if not ti:
                        missing += 1
                    href = (f'bill/{yr}/{bid.lower()}.html' if yr
                            else f'/bills#{esc(bid)}')
                    num = re.sub(r"^([A-Z]+)(\d)", r"\1 \2", bid)
                    html.append(f'<li><a class="cbn" href="{esc(href)}">{esc(num)}</a>'
                                + (f'<span class="cbt"{EN_ATTR if lang != i18n.DEFAULT else ""}>'
                                   f'{esc(ti)}</span>' if ti else "")
                                + "</li>")
                html.append("</ul>")
            # INTO THE SITTING, NOT JUST THE COMMITTEE. A day has an address
            # now -- committee/H05#day-2024-04-30 -- so the way out of a
            # calendar entry lands on the sitting it names rather than at the
            # top of a page holding eighty-six of them.
            # THE FLOOR HAS NO COMMITTEE PAGE TO GO TO. Floor rows carry no
            # committee -- which is why sitting days were nowhere on this site
            # until the calendar gave them one -- so "House floor" and "Senate
            # floor" lead to the day's own page instead, where the whole
            # sitting is set out in the order the journal records it.
            # A FLOOR CARD LINKS ONLY WHERE THE SITTING PAGE EXISTS. Both
            # chambers have pages now, but proceedings.csv and narratives.json
            # do not agree on every sitting: the Senate sat on 19 August 2026
            # by one and not by the other, and the link was a 404. `sessions`
            # is the set of pages actually on disk, so the caller that built
            # them decides, rather than this guessing from the name.
            floor = {"house floor": "H",
                     "senate floor": "S"}.get(key.name.strip().lower())
            # THE MORNING PAGE (live/session, 6 November 2026): on the build's
            # own day a sitting with no page yet gets one after this step,
            # from build_live_session, which shows the link this leaves
            # hidden once it has written the page. Any other day stays as it
            # was: no page, no link.
            waits = None
            if floor and sessions is not None and (floor, _d) not in sessions:
                waits = floor if morning and _d == morning else None
                floor = None
            elif floor and sessions is None:
                floor = None
            # THE OFFICIAL DOCUMENT, where the caller has one: the calendar
            # that printed the notice, or the journal of a floor sitting.
            # Addresses the record holds, passed in; never built here.
            # In a new tab and marked as going out, as every calendar and
            # journal on the Calendar opens (F12, 7 October 2026).
            got = (docs or {}).get(key) or []
            if got:
                html.append('<p class="calmore caldocs">'
                            + "".join(f'<a class="out" href="{esc(u)}" '
                                      'target="_blank" rel="noopener">'
                                      f'{esc(w)} (PDF)</a>' for w, u in got)
                            + "</p>")
            # A STUDY OR STATUTORY COMMITTEE'S RECORDING, where one is named
            # for the meeting (build_calendar.study_recordings). Its card has
            # no page to lead to, so it leads to the recording itself; a bill's
            # sitting leads to the bill, whose page holds its recording at the
            # moment the bill was taken up.
            rec = next((r.get("video_id") for r in rows
                        if r.get("study") and r.get("video_id")), "")
            if study and rec:
                html.append('<p class="calmore"><a class="out" href="https://www.youtube.com/'
                            f'watch?v={esc(rec)}" target="_blank" rel="noopener">'
                            + say(lang, "cal.recording", "The recording, on YouTube") + "</a></p>")
            # A study committee that shares a name with a standing one is not
            # that committee, so its card does not borrow the page; and a
            # chamber's committee takes its OWN chamber's page, which the
            # name alone does not say.
            cc = None if study else code.get((key.chamber, key.name.strip().lower()))
            # A STUDY OR STATUTORY COMMITTEE HAS A PAGE OF ITS OWN (18 October
            # 2026) where the General Court lists it as active: the row names
            # it (build_calendar.study_page), and the card leads into the
            # meeting there, as a standing committee's card leads into its day.
            own = next((r.get("page") for r in rows
                        if r.get("study") and r.get("page")), "") if study else ""
            if floor:
                did = (f'What the {esc(key.name[:-6].strip())} did that day'
                       if lang == i18n.DEFAULT
                       else say(lang, "cal.house_did", "What the House did that day")
                       if floor == "H" else say(lang, "cal.senate_did", "What the Senate did that day"))
                html.append('<p class="calmore">'
                            f'<a href="session/{floor}/{esc(_d)}.html">{did}</a></p>')
            elif waits:
                # Hidden until build_live_session writes the page: "did" is
                # not yet so, and the words say only that its votes are read.
                # The address as served (shell.canon), so the week page,
                # which clean_links rewrites, and the month's data file,
                # which it does not, carry the same card. data-href, not
                # href, until the page exists: a build without the live
                # step leaves no link to a page that was never written.
                html.append(f'<p class="calmore" data-morning="{waits}/{esc(_d)}" hidden>'
                            f'<a data-href="session/{waits}/{esc(_d)}">The '
                            f'{"House" if waits == "H" else "Senate"}\'s votes, as they are read</a></p>')
            elif cc:
                html.append('<p class="calmore">'
                            f'<a href="committee/{esc(cc)}.html#day-{esc(_d)}">'
                            + say(lang, "cal.on_page", "This meeting on the {name} page",
                                  name=esc(cmte)) + '</a></p>')
            elif own:
                html.append('<p class="calmore">'
                            f'<a href="{esc(own)}#day-{esc(_d)}">'
                            + say(lang, "cal.on_page", "This meeting on the {name} page",
                                  name=esc(cmte)) + '</a></p>')
            html.append("</div></details>")
        html.append("</div>")
    return "".join(html), missing


# ---- from build_site_v2: a seat's county and the district a label carries ------------------

# Without the trailing point, which is the form data/legislators.json's own
# county_abbr carries. A member drawn from the roster read "Hills 12" and
# one drawn from here read "Hills. 6", so the punctuation tracked exactly
# who had left office.
COUNTY_ABBR = {**ST.COUNTY_ABBR_LOWER, "co\u00f6s": "Coos"}
# EITHER SPELLING RESOLVES, because the sources do not agree on which they
# store. member_party.json writes a seat already abbreviated -- 622 rows say
# "Hills", 440 "Rock", 212 "Merr", and so on through all nine that shorten --
# and this map is keyed on the full name, so .get() missed and the seat was
# dropped out of the label altogether: 228 sponsor rows read "Rep. Jane Smith
# (R)" where every other row on the same bill reads "(R - Hills 12)".
#
# 62 of those 228 are filled from former_members.json by way of build_data's
# roll-call pass, and the seat it carries is the one that member held LAST,
# not the one they held when the bill was filed. That is a fact about where
# the seat comes from and cannot be told apart here -- district_tag is handed
# a county and a number and no provenance -- so it is fixed upstream or not at
# all, and is written down rather than guessed at.
#
# A trailing point is allowed on the way in because Counties.txt writes
# "Hills." and the roster writes "Hills"; what comes out is always the
# roster's spelling, so the punctuation stops tracking who has left office.
COUNTY_OF = {**COUNTY_ABBR, **{v.lower(): v for v in COUNTY_ABBR.values()}}


def district_tag(chamber, district, county=None, county_abbr=None):
    d = str(district or "").strip()
    # The bill status page pads a district ("Carr 07"); nobody says it so.
    d = d.lstrip("0") or d if d.isdigit() else d
    if not d:
        return ""
    if chamber == "S":
        return f"SD{d}"
    ab = (county_abbr or "").strip() or COUNTY_OF.get(
        (county or "").strip().rstrip(".").lower(), "")
    return f"{ab} {d}" if ab else ""


# ---- from build_town_pages: a number that dials, an address that mails ---------------------

# Ten digits, then an extension if there is one: "603-588-6785 ext 221",
# "603-927-2400 ext. 4", "(603) 224-5000 x 12".
PHONE = re.compile(r"^\s*\(?(\d{3})\)?[-. ]?(\d{3})[-. ]?(\d{4})\s*,?\s*"
                   r"(?:(?:ext\.?|ex\.?|x)\s*(\d+))?\s*$", re.I)


def tel(num):
    """A number that dials, on the device most readers are holding.

    These were plain text. A town clerk's number on a town page is the single
    most likely thing on this site to be tapped, and tapping it did nothing.

    AN EXTENSION IS NOT MORE OF THE NUMBER. This took every digit in the
    value, so "603-588-6785 ext 221" dialled +6035886785221 -- a number in no
    country this site is about -- and 28 links on the town pages did that.
    The extension is written the way a phone reads it now, `;ext=221` after
    the number (RFC 3966), and a value that holds no single number -- two
    numbers in one cell -- is shown as written and not linked, because either
    guess would ring somebody.
    """
    m = PHONE.match(num or "")
    if m:
        a, b, c, ext = m.groups()
        href = f"tel:+1{a}{b}{c}" + (f";ext={ext}" if ext else "")
        return f'<a class="offtel" href="{href}">{E(num)}</a>'
    digits = re.sub(r"[^0-9]", "", num or "")
    if len(digits) == 10:
        digits = "1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return f'<a class="offtel" href="tel:+{digits}">{E(num)}</a>'
    return f'<span class="offtel">{E(num)}</span>'


def maillink(addr):
    """A mailto link for an e-mail address, and nothing for anything else.

    NHDOT's e-mail column holds notes as well as addresses -- "can email
    through the website, no stated email", "no stated email address", "not
    listed", once a street address -- 125 of them across 104 towns, and every
    one was published as a mailto link a reader could click. A note that
    says there is no address tells a reader what no link already does, and
    the town's website is on the page, so nothing is drawn.

    All five places on these pages that write a mailto go through here.
    """
    a = (addr or "").strip()
    if not EMAIL_OK.match(a):
        return ""
    # A LINE MAY BREAK AFTER THE @, and so the address breaks there rather
    # than wherever the column runs out: at the interface's 16px a select
    # board member's address in a town card's contact column read
    # "Jim.Craig@GoffstownNH.g" over "ov" (the review of the polish
    # foundation, 8 October 2026). Only the words drawn; the address is whole.
    return f'<a href="mailto:{E(a)}">{E(a).replace("@", "@<wbr>", 1)}</a>'


# ---- from build_town_pages: an outward link ------------------------------------------------

def weblink(url, label=None):
    """An outward link labelled with where it goes, or nothing.

    "official page" told a reader nothing about which page; the host does, and
    it is what they would read off the address bar anyway. The arrow is this
    site's mark for a link that leaves it.

    A SCHEME IS ADDED AND A NON-ADDRESS IS REFUSED. The DoT directory does not
    write addresses the way a browser reads them, and this function used to
    pass every value through untouched into an href:

      * 17 of its 234 rows are a bare host -- "www.concordnh.gov". With no
        scheme that is a RELATIVE link, and bills.html carries <base href="/">,
        so it left the site for /www.concordnh.gov. 40 dead links.
      * 4 rows are prose -- "no website", "website was discontinued" -- which
        became links to /no%20website. 8 dead links.
      * 7 more are the directory's two columns interleaved a character at a
        time by parse_officials.py: "httpsT:o//wwnw wIn.bfooscawennh.gov/" is
        "https://www.boscawennh.gov/" with "To www Info" threaded through it.
        A parser bug, not this file's to fix -- but not this file's to publish
        as a link either.

    So the host is checked before anything is written. No dot, a space, or an
    "@" (town_clerks.json records an email address as the website for two
    towns) and it is not an address this page can send a reader to, and the
    caller draws nothing rather than a link to a 404.
    """
    url = (url or "").strip()
    if not url:
        return ""
    # https:// and not http://: a guess, and the safe one -- every host here
    # that does carry a scheme carries this one, and a server that only speaks
    # http will redirect where the reverse would not.
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    if not _is_address(re.sub(r"^https?://", "", url, flags=re.I).split("/")[0]):
        return ""
    host = re.sub(r"^https?://(?:www\.)?", "", url).rstrip("/").split("/")[0]
    return (f'<a href="{E(url)}" target="_blank" rel="noopener">{E(label or host)}'
            "</a>")


def _is_address(host):
    """Whether a host is one a reader could be sent to. See weblink()."""
    return bool(host) and "." in host and " " not in host and "@" not in host


# ---- from build_town_pages: the tab strip's script -----------------------------------------

# THE SWITCHING SCRIPT, the legislators page's (build_pages.py, "THREE TABS,
# WHICH ARE THE ORDERING") with the address added. Inline, after the panels,
# so it runs before the page is first painted and a reader never sees three
# panels collapse into one.
#
# ONE HISTORY ENTRY PER PAGE, NOT PER CLICK: replaceState rather than
# pushState, so Back leaves the page rather than stepping through its tabs.
# A hash that names no tab -- #results, from the skip link -- is left alone
# and the first tab shown.
#
# A SECTION'S ADDRESS OPENS ITS TAB (6 November 2026), as the Constitution
# tab's script already does (constitution_tab.TABS_JS): an address naming
# something inside a panel -- /officials#of-county-strafford, a county's
# heading on County Officials -- opened the first tab and landed nowhere,
# because what it named was hidden. The panel holding it opens, the address
# is left as it was, and the page is brought to it once loaded and again
# when the web fonts arrive, since the browser's own jump came while the
# panel was still hidden. #results wraps the panels and is in none, so it is
# left alone as before.
#
# THE ADDRESS IS WRITTEN WITH THE PAGE'S OWN PATH. The page carries
# <base href="/">, so a bare "#officials" resolves against the site's root:
# choosing "Town officials" on /town/acworth wrote /#officials into the address
# bar, and a reload, a bookmark or a link copied from there opened the home
# page (the audit of 2 October 2026, on all 320 pages). The trap is written
# down in six other places in the build; this call had been missed.
#
# HOME AND END, as the bill's and the member's tabs have them: a tab list
# answers both, and here End scrolled the page to its foot with the keyboard
# left on a tab out of sight (the review of 2 October 2026).
TABS_JS = """<script>
(function(){
  var bar=document.querySelector(".twntabs");
  if(!bar)return;
  var tabs=[].slice.call(bar.querySelectorAll("[role=tab]"));
  if(!tabs.length)return;
  // The tab an address names: a panel's own, or the one holding what it names.
  function named(h){
    if(!h)return null;
    for(var i=0;i<tabs.length;i++)if(tabs[i].dataset.pane===h)return h;
    var el=document.getElementById(h),p=el&&el.closest&&el.closest(".twnpane");
    for(i=0;p&&i<tabs.length;i++)if(tabs[i].dataset.pane===p.id)return p.id;
    return null;
  }
  function hash(){try{return decodeURIComponent(location.hash.slice(1));}catch(e){return "";}}
  // A TAB THAT HAS RETIRED (the owner, 7 November 2026): from 2 December
  // the Officials page's Members-Elect tab hides itself (data-until, judged
  // by the reader's own date as components.js judges it), and an address
  // naming it -- a bookmark, a link someone shared -- opened six tabs with
  // none chosen and nothing under them. It opens the strip's data-retired
  // tab instead (Legislators, which the tab's intro said "lists who holds
  // each seat"), else the first tab still shown, and says so in the address.
  function gone(t){
    if(!t)return false;
    if(t.hidden)return true;
    var u=t.getAttribute("data-until");
    if(u===null)return false;
    var d=new Date(),day=d.getFullYear()+"-"+("0"+(d.getMonth()+1)).slice(-2)+"-"+
      ("0"+d.getDate()).slice(-2);
    return !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(u)||day>=u;
  }
  function tab(id){for(var i=0;i<tabs.length;i++)if(tabs[i].dataset.pane===id)return tabs[i];return null;}
  function live(){return tabs.filter(function(t){return !gone(t);});}
  function instead(){
    var r=bar.getAttribute("data-retired");
    if(r&&tab(r)&&!gone(tab(r)))return r;
    var l=live();
    return (l[0]||tabs[0]).dataset.pane;
  }
  // To what a section's address names, once its panel is open.
  function land(){
    var h=hash(),id=named(h);
    if(!id||h===id||gone(tab(id)))return;
    var el=document.getElementById(h);
    if(el)el.scrollIntoView();
  }
  // AGAIN ONCE LOADED AND WHEN THE FONTS ARRIVE, but only on a first arrival
  // and only while the reader has not moved: a reload or Back is put back
  // where the reader was by the browser itself, and a reader who has scrolled
  // on, on a slow connection, was pulled back to the heading 17 seconds later
  // (the review of 6 November 2026).
  var moved=false,restored=false;
  try{var nv=performance.getEntriesByType("navigation")[0];
    restored=!!nv&&(nv.type==="reload"||nv.type==="back_forward");}catch(e){}
  ["wheel","touchmove","keydown","pointerdown"].forEach(function(t){
    addEventListener(t,function(){moved=true;},{passive:true,once:true});
  });
  // A reader sent from a retired tab is shown the strip, once loaded, so
  // that what they were given -- Legislators, chosen -- is in view.
  var sent=false;
  function later(){if(moved||restored)return;if(sent)toStrip();else land();}
  // A LINK TO A TAB from inside another -- County Officials' "by county in
  // Legislators" -- shows that tab; the browser's own jump went to a panel
  // still hidden and left the reader where they were, halfway down a
  // different list. The strip is brought back into view, as the hub's
  // LAND_JS sets it for a tab's address.
  function toStrip(){
    var t=bar.getBoundingClientRect().top;
    if(t<0)window.scrollTo(0,Math.max(0,t+window.scrollY-8));
  }
  function show(id,write){
    tabs.forEach(function(t){
      var on=t.dataset.pane===id;
      t.setAttribute("aria-selected",String(on));
      t.tabIndex=on?0:-1;
      var pane=document.getElementById(t.dataset.pane);
      if(pane)pane.hidden=!on;
    });
    if(write&&history.replaceState)
      history.replaceState(null,"",location.pathname+location.search+"#"+id);
    inView();
  }
  // THE CHOSEN TAB IN VIEW, as the Officials page's strip does: on a phone the
  // strip scrolls, and /town/acworth#services opened Services with its tab
  // past the strip's edge (the town-pages fix of 25 October 2026). The strip
  // moves, 2rem clear of the edge where its shadow is; the page does not.
  function inView(){
    var t=bar.querySelector('[aria-selected="true"]');
    if(!t||bar.scrollWidth<=bar.clientWidth+2)return;
    var a=t.getBoundingClientRect(),b=bar.getBoundingClientRect();
    if(a.left<b.left)bar.scrollLeft-=b.left-a.left+32;
    else if(a.right>b.right)bar.scrollLeft+=a.right-b.right+32;
  }
  tabs.forEach(function(t){
    t.addEventListener("click",function(){show(t.dataset.pane,true);});
  });
  // The keys go round the tabs still shown: a retired one takes no focus.
  // One that retired while it had it -- a page left open past midnight --
  // gives the keys to the tab it hands over to.
  bar.addEventListener("keydown",function(e){
    var on=live(),i=on.indexOf(document.activeElement);
    if(i<0&&tabs.indexOf(document.activeElement)>=0)i=on.indexOf(tab(instead()));
    if(i<0)return;
    var j;
    if(e.key==="ArrowRight")j=(i+1)%on.length;
    else if(e.key==="ArrowLeft")j=(i-1+on.length)%on.length;
    else if(e.key==="Home")j=0;
    else if(e.key==="End")j=on.length-1;
    else return;
    e.preventDefault();
    on[j].focus(); show(on[j].dataset.pane,true);
  });
  addEventListener("hashchange",function(){
    var h=hash(),id=named(h);
    if(!id)return;
    if(gone(tab(id))){show(instead(),true);toStrip();return;}
    show(id,false);
    if(h===id)toStrip();else land();
  });
  bar.hidden=false;
  var first=named(hash());
  if(first&&gone(tab(first))){sent=true;show(instead(),true);}
  else show(first||(live()[0]||tabs[0]).dataset.pane,false);
  addEventListener("load",later);
  // and again once the fonts have their widths
  if(document.fonts&&document.fonts.ready)
    document.fonts.ready.then(function(){inView();later();});
})();
</script>"""
