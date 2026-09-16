#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.4
"""
The Secretary of State's clerks and polling places, out of the PDF.

    python3 parse_clerks.py --report      # says what it found, writes nothing
    python3 parse_clerks.py               # -> town_clerks.json

WHY A PDF AND NOT A FETCH

`app.sos.nh.gov/statelistclerkandpolling` is the one page carrying the clerk
and the polling place for every town and ward in the state, and it is behind a
CAPTCHA: `fetch_town_clerks.py` records that and has never been run. The list
was exported by hand instead and lives in `sources/`, so this reads a document
on disk and touches no network.

WHAT MAKES THIS PDF AWKWARD

Every cell is hard-wrapped in the text layer itself. "SKIFFINGTON" is stored as
"SKIFFINGTO" and "N" on two lines, "ALEXANDRIA" as "ALEXANDR" and "IA",
"603-835-6879" as "603-835-68" and "79". A cell cannot be read by joining its
lines with a space, and it cannot be read by joining them with nothing either:
"CHARLOTTE" and "COMEAU" are two names, "NEW" and "BOSTON" two words.

Geometry gets close and not close enough. The text area of a column ends about
4pt inside its border, and a line the generator broke ends within one
character of that -- but one character here is 6pt, so "SKIFFINGTO" stops 10pt
short of the border and looks like a line that simply ended. A threshold loose
enough to catch it is loose enough to join two real words.

So each kind of column is read the way that column can be checked:

  town              against the towns this site already has pages for. Every
                    combination of space and nothing at each break is tried
                    and the one naming a real town wins. The dotted
                    abbreviations of the unincorporated places are matched by
                    prefix -- "AT.& GIL. AC. GT." to "ATK. & GIL. ACADEMY
                    GRANT" -- because the two lists spell them differently.
  clerk             by scoring the candidates. A written name is two to four
                    tokens, does not end in a single letter, has at most one
                    initial and no eighteen-letter surname; the candidate that
                    breaks fewest of those wins, and geometry breaks the ties.
                    Then it is CHECKED: a clerk's e-mail usually contains
                    their surname, and this prints how many of the surnames it
                    reconstructed appear in the address beside them.
  address, polling  geometry, with the threshold measured from the column's
                    own border rather than assumed. A missing space in an
                    address is legible; a missing space in a name is a
                    different person's name.
  phone, fax,       joined with nothing, always. None of these can contain a
  e-mail, website   space, so there is nothing to decide.

ROWS THAT ARE NOT ROWS. The export splits a row across a page break -- page 3
ends with "BENNINGT" and page 4 begins with "ON" -- and leaves spacer rows
whose town cell is empty. Any row whose town does not name a town is folded
into the row before it, line by line, and the whole row is re-read. That
handles both without knowing which it was.

AND THE HALF THAT NAMES THE WRONG TOWN. Not every page break leaves a half
that names nothing. Page 19 ends with "GREEN'S" and page 20 begins with
"GRANT", and GRANT is a five-letter prefix of exactly one town in the state:
Grantham. So the tail of Green's Grant was read as a row of its own, filed
under `grantham`, and overwrote the real Grantham -- which is why Grantham's
page offered "https://mnh.gov" as the town's website, the back half of Green's
Grant's "www.gorhamnh.gov", while Green's Grant kept the front half,
"www.gorha". One row, two wrong towns, both published as live links.

What separates that case from every other is knowable without guessing at
"GRANT": the row ABOVE it held only part of its own town's name. Two rows in
the document are matched by that last, loosest rule, and only one of them is
short of the name it matched -- "GREEN'S" against GREEN'S GRANT, where "LOW &
BURBANKS GRANT" is all of LOW & BURBANK'S GRANT and merely spelled without the
apostrophe. So a row that follows a truncated one is folded into it when, and
only when, joining the two town cells spells a town in full.

THE WEBSITE COLUMN IS NOT ALWAYS A WEBSITE. Five towns have their clerk's
e-mail address typed in it, Ellsworth has "NONE AVAILABLE", and Orange has an
address the Secretary of State's own cell labels "(UNOFFICIAL COMMUNITY RUN
WEBSITE)". None of those is the town's website, and a page that draws no link
is right where one that links a fragment is not -- so the value is checked
against `parse_officials.web_address` and anything that is not a host is
recorded as nothing.

CASE. The list is typed in capitals. Capitals are how the form stores it and
not how a name is written, so the name and the polling place are title-cased
for display and the original is kept beside them under _raw. The rule knows
Mc, Mac, O', hyphens and the Roman-numeral suffixes.
"""
import argparse
import bisect
import collections
import json
import pathlib
import re
import sys

# The other directory decides two things here: its properly spaced names settle
# the joins this PDF leaves ambiguous, and its `web_address` decides what counts
# as a website. One rule for both files, so the two cannot drift into disagreeing
# about what a town page may link.
import parse_officials

ROOT = pathlib.Path(__file__).resolve().parent
PDF = ROOT / "sources" / "sos-clerks-and-polling-places.pdf"
OUT = ROOT / "town_clerks.json"

TOWN, CLERK, ADDR, PHONE, FAX, EMAIL, SITE, POLL, ELECT, SHOURS, LHOURS = range(11)
TIGHT = {PHONE, FAX, EMAIL, SITE}
BLANK = {"", "not applicable", "n/a", "none", "not available", "-"}

# A line the generator broke ends within one character of the text area, and
# the text area ends this far inside the column's border. Both measured: the
# widest lines in each column stop 4pt short of the border, and a character at
# this size is about 6pt.
PAD, CHAR = 4.0, 6.6

KEEP = {"PO", "NH", "US", "VFW", "JFK", "YMCA", "YWCA", "AMVETS", "SAU", "II",
        "III", "IV", "VI", "VII", "NE", "NW", "SE", "SW", "TV", "MS", "HS"}
SUFFIX = {"JR", "SR", "II", "III", "IV", "V"}


# ---------------------------------------------------------------- casing ----

def namecase(s):
    out = []
    for tok in s.split():
        u = tok.upper()
        if u in SUFFIX:
            out.append({"JR": "Jr", "SR": "Sr"}.get(u, u))
            continue
        if len(tok) == 1:
            out.append(u)
            continue

        def one(w):
            if w[:2].upper() == "MC" and len(w) > 2:
                return "Mc" + w[2:].capitalize()
            if w[:3].upper() == "MAC" and len(w) > 4:
                return "Mac" + w[3:].capitalize()
            if w[:2].upper() == "O'" and len(w) > 2:
                return "O'" + w[2:].capitalize()
            return w.capitalize()

        parts = re.split(r"([-'])", tok)
        out.append("".join(p if p in "-'" else one(p) for p in parts if p))
    return " ".join(out)


def placecase(s):
    out = []
    for tok in s.split():
        u = re.sub(r"[^A-Z0-9']", "", tok.upper())
        if u in KEEP:
            out.append(tok.upper())
        elif re.fullmatch(r"\d+[A-Z]?", u) or len(u) <= 1:
            out.append(tok.upper())
        else:
            out.append(namecase(tok))
    return " ".join(out)


# ------------------------------------------------------------- the table ----

def cell_lines(words, x0, x1, top, bot):
    """One cell as lines: (text, right_edge_of_the_line)."""
    rows = collections.defaultdict(list)
    for w in words:
        if x0 - 0.5 <= w["x0"] < x1 and top - 0.5 <= w["top"] < bot:
            rows[round(w["top"], 1)].append(w)
    out = []
    for t in sorted(rows):
        ws = sorted(rows[t], key=lambda w: w["x0"])
        out.append((" ".join(w["text"] for w in ws),
                    max(w["x1"] for w in ws)))
    return out


def geom_join(lines, right):
    """Join by geometry: a line that reaches the text area's end ran on.

    With one rule geometry cannot know: a break between a digit and a letter
    is a space. Addresses and times wrap exactly there -- "1528ELM ST" for
    1528 Elm St, "7:00PM" for 7:00 PM, "MANCHESTER03101" for the ZIP -- and a
    word is never broken across that boundary, because the generator breaks
    inside a word and "1528ELM" is two.
    """
    limit = right - PAD - CHAR
    s = ""
    for i, (t, x1) in enumerate(lines):
        s += t
        if i + 1 < len(lines):
            nxt = lines[i + 1][0]
            straddle = bool(t and nxt and (
                (t[-1].isdigit() and nxt[0].isalpha())
                or (t[-1].isalpha() and nxt[0].isdigit())))
            s += " " if (x1 < limit or straddle) else ""
    return re.sub(r"\s+", " ", s).strip()


def masks(n):
    for m in range(1 << max(0, n - 1)):
        yield m


def joins(frags, mask):
    s = frags[0]
    for i in range(1, len(frags)):
        s += ("" if (mask >> (i - 1)) & 1 else " ") + frags[i]
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------------------ town ----

def abbrev_of(short, full):
    """Is `short` an abbreviation of `full`, token by token?

    "AT.& GIL. AC. GT." is "ATK. & GIL. ACADEMY GRANT" on the Secretary of
    State's list, and "GT." for "GRANT" drops the interior rather than the
    tail -- so a token matches if its letters appear in order in the full
    word, starting at the first. "BENNINGT" for "BENNINGTON" is the same rule
    with nothing dropped, which is what a page break leaves behind.
    """
    a = [x for x in re.split(r"[^A-Z0-9]+", short.upper()) if x]
    b = [x for x in re.split(r"[^A-Z0-9]+", full.upper()) if x]
    if len(a) != len(b) or not a:
        return False
    # ONE TOKEN HAS TO BE MOST OF THE WORD. "ON" -- the second half of
    # BENNINGTON, left at the top of page 4 by the page break -- is O then N
    # in ORANGE, uniquely among 259 towns, and was filed as Orange. A single
    # truncated token must be at least four characters and most of the name;
    # the dotted places keep the loose rule because four tokens of initials
    # are distinctive on their own.
    if len(a) == 1 and (len(a[0]) < 4 or len(a[0]) < 0.6 * len(b[0])):
        return False
    for x, y in zip(a, b):
        if not y.startswith(x[0]):
            return False
        i = 0
        for ch in x:                     # x as a subsequence of y
            i = y.find(ch, i)
            if i < 0:
                return False
            i += 1
    return True


def read_town(lines, towns):
    """The town, the ward, the cell as it read, and whether it held the whole
    of the name. The last of those is what `stitch` needs: a cell matched only
    as a prefix of the town it names is the front half of a row a page break
    cut, and the back half is the row below."""
    frags = [t for t, _ in lines]
    raw = " ".join(frags)
    ward = None
    m = re.search(r"WARD\s*0*(\d+)\s*$", raw)
    if m:
        ward = m.group(1)
        stripped = re.sub(r"WARD\s*0*\d+\s*$", "", raw).strip()
        frags = [f for f in re.split(r"\s+", stripped) if f]
    if not frags or not frags[0].strip():
        return None, ward, raw, True
    for mask in masks(len(frags)):
        cand = joins(frags, mask)
        if cand.upper() in towns:
            return cand.upper(), ward, raw, True
    # The abbreviated, the truncated and the differently spelled, and ONLY
    # where one town answers. "NEW" is a prefix of Newbury, Newfields,
    # Newington, Newmarket, Newport and Newton, and answering with whichever
    # came first would file a town under another town's name.
    #
    # Both directions, because the two lists abbreviate in both: this PDF
    # writes "AT.& GIL. AC. GT." where the district file writes it out, and
    # writes "CHANDLER S PURCHASE" where the district file has "CHANDLER'S
    # PUR." -- the same rule, with the short and long sides swapped.
    for mask in masks(len(frags)):
        cand = joins(frags, mask)
        hit = [t for t in towns if abbrev_of(cand, t) or abbrev_of(t, cand)]
        if len(hit) == 1:
            return hit[0], ward, raw, True
        if len(hit) > 1:
            return None, ward, raw + f"  [{len(hit)} towns match]", True
    # A PAGE BREAK CUTS A ROW IN HALF and leaves the first half short of whole
    # tokens: page 19 ends with "GREEN'S" and page 20 begins with "GRANT". A
    # prefix of the whole name catches those, at five letters and up so that
    # "NEW" and "ON" catch nothing, and only where one town answers.
    #
    # A match here is reported as WHOLE only when the cell spells all of the
    # name. "LOW & BURBANKS GRANT" does, missing an apostrophe this list does
    # not write; "GREEN'S" does not, and the row carrying it is half a row.
    letters = lambda s: re.sub(r"[^A-Z0-9]", "", s.upper())
    for mask in masks(len(frags)):
        cand = letters(joins(frags, mask))
        if len(cand) < 5:
            continue
        hit = [t for t in towns if letters(t).startswith(cand)]
        if len(hit) == 1:
            return hit[0], ward, raw, len(cand) == len(letters(hit[0]))
    return None, ward, raw, True


# ----------------------------------------------------------------- clerk ----

VOWEL = re.compile(r"[AEIOUY]")


def name_score(s):
    """How unlike a written name a candidate is. Lower is better.

    The two rules at the bottom are the ones that decide the cases geometry
    cannot, and both come from a wrong answer this produced:

      "CHARLOTTECOMEAU" -- 15 letters. A surname is not that long, and two
      names run together are. "CHARLOTTE" ends 0.6pt inside the edge of its
      column, so geometry called that break a word-wrap and was wrong.

      "FRANCINE MSKIFFINGTON" -- MSK has no vowel in it. An initial joined to
      the surname after it reads as a consonant cluster no name starts with,
      and scoring on token count alone rated it the same as the right answer
      and then preferred it for being a character shorter.
    """
    toks = s.split()
    bad = 0
    if not 2 <= len(toks) <= 4:
        bad += 10 * min(abs(len(toks) - 3), 3)
    if toks and len(toks[-1]) == 1:
        bad += 12                      # a surname is not one letter
    initials = sum(1 for t in toks if len(t) == 1)
    if initials > 1:
        bad += 4 * (initials - 1)
    for t in toks:
        core = re.sub(r"[^A-Za-z]", "", t)
        if len(core) >= 14:
            bad += 8
        if len(core) == 2 and t.upper() not in SUFFIX:
            bad += 2
        if len(core) >= 4 and not VOWEL.search(core[:3].upper()):
            bad += 6
    return bad


# THE NAMES THE OTHER DIRECTORY SPELLS PROPERLY. NHDOT's municipal officials
# list -- parse_officials.py, 1,414 named offices -- writes names with their
# spaces in, so its tokens are a dictionary for the joins this PDF leaves
# ambiguous. "JOYCE" is a name somebody in New Hampshire holds; "AJOYCE" is
# not, and that is the whole of the difference between "Kimberly A Joyce" and
# "Kimberly Ajoyce" once the score and the geometry have both shrugged.
KNOWN = set()


def load_known(path="town_officials.json"):
    p = pathlib.Path(path)
    if not p.exists():
        return 0
    for rec in json.loads(p.read_text(encoding="utf-8")).values():
        for o in rec.get("officials", []):
            for tok in re.split(r"[^A-Za-z']+", o.get("name", "")):
                if len(tok) > 2:
                    KNOWN.add(tok.upper())
    return len(KNOWN)


def known_tokens(s):
    return sum(1 for tok in s.split()
               if re.sub(r"[^A-Za-z']", "", tok).upper() in KNOWN)


def read_clerk(lines, right):
    """The name, deciding only the breaks geometry cannot.

    A line that stops more than two characters short of the text area ended
    because the text did -- that break is a space and nothing else. A line
    that reaches within one character of it is a word the generator cut --
    that break is nothing. Only the sliver between the two is a question, and
    that is what the scoring is for; usually there is one such break in a
    cell and often none.

    Deciding every break by score was the first draft and it got
    "FRANCINE M SKIFFINGTON" wrong: "FRANCINE MSKIFFINGTON" is two tokens
    with no initial and scores just as well, and it is shorter, so it won.
    Geometry already knew that "FRANCINE M" ended halfway across the column.
    """
    frags = [t for t, _ in lines]
    if not frags:
        return "", ""
    raw = " ".join(frags)
    # GEOMETRY IS THE TIEBREAK, NOT THE ANSWER. A line that stops well short
    # of the text area certainly ended in a space, but a line that reaches it
    # may be either: "CHARLOTTE" ends 0.6pt inside the edge and is a whole
    # name. So every break a space could not explain is asked of the score,
    # and geometry only decides between two candidates the score likes
    # equally.
    space_at = right - PAD - 2 * CHAR
    fixed, ask = [], []
    for i in range(len(frags) - 1):
        if lines[i][1] < space_at:
            fixed.append(" ")          # far short of the edge: a real space
        else:
            fixed.append(None)
            ask.append(i)
    g = geom_join(lines, right)
    best, best_key = None, None
    for mask in range(1 << len(ask)):
        seps = list(fixed)
        for j, i in enumerate(ask):
            seps[i] = "" if (mask >> j) & 1 else " "
        cand = re.sub(r"\s+", " ",
                      "".join(f + (seps[i] if i < len(seps) else "")
                              for i, f in enumerate(frags))).strip()
        key = (name_score(cand), -known_tokens(cand),
               0 if cand == g else 1, len(cand))
        if best_key is None or key < best_key:
            best, best_key = cand, key
    return best, raw


# Most clerks answer at the office rather than by name -- townclerk@,
# atclerk@, tctc@ -- and an address like that can neither confirm nor deny a
# surname. Only the ones that look like a person's address are counted, or the
# number means nothing.
# Any local part with one of these in it is the office, not a person: the
# first draft only matched them whole and counted atclerk@, tctx@, twn@ and
# deputytctc@ as failures, which made the number meaningless.
GENERIC = re.compile(r"clerk|tax|town|twn|city|office|admin|info|select|"
                     r"deputy|elect|vote|^tc|^tx|contact|registrar", re.I)


def surname_in_email(name, email):
    """True/False where the address carries a name, None where it cannot say."""
    local = (email.split("@")[0] or "").lower()
    if not local or GENERIC.search(local.replace(".", "").replace("_", "")):
        return None
    toks = [re.sub(r"[^A-Za-z]", "", t).lower() for t in name.split()]
    toks = [t for t in toks if len(t) > 2 and t.upper() not in SUFFIX]
    if not toks:
        return None
    # a surname in full, or an initial-plus-surname like jtate
    if any(t in local for t in toks):
        return True
    first = toks[0]
    return any(first[0] + t in local for t in toks[1:]) if len(toks) > 1 else False


# ----------------------------------------------------------------- parse ----

def header_bottom(words, xs, bands):
    """The rule under the column labels, read off the page rather than assumed.

    The header is a row of the table like every other row, and its first cell
    says which row it is: "Town/City". So the band spelling that IS the
    header, and the line the table draws under it is where the data starts.

    THE CONSTANT THIS REPLACES was `t.bbox[1] + 26`, and it was a third of a
    line short. The labels stand three text lines deep -- "State Election" at
    top 45.57, "Start Time -" at 57.07, "End Time" at 68.57 -- and only the
    two hours columns carry a third line. A cut at 40.0 + 26 = 66.0 clears
    the first two and leaves the third standing; every page of this export is
    laid out to the same tenth of a point, so it left it standing on all 53.
    "End Time" then sat alone in the header band with no town beside it,
    `stitch` did to it what it does to any row that names no town and folded
    it into the row above -- the last row of the page before -- and 45 town
    pages went out reading "8:00 AM - 7:00 PM End Time" under How to Vote.

    There is nothing to tune in the replacement. The header band is 40.0 to
    84.5 on all 53 pages and the first line of data is at 90.07, so the
    measured answer clears the labels by 6pt and misses the data by 5.6.
    """
    for top, bot in bands:
        if any(w["text"].lower().startswith("town/city") for w in words
               if top - 0.5 <= w["top"] < bot and xs[0] - 0.5 <= w["x0"] < xs[1]):
            return bot
    return None


def read_pdf(path):
    import pdfplumber
    out, notes = [], []
    with pdfplumber.open(path) as pdf:
        for pg in pdf.pages:
            tables = pg.find_tables()
            if not tables:
                notes.append(f"page {pg.page_number}: no table")
                continue
            t = tables[0]
            xs = sorted({round(c[0], 1) for c in t.cells}
                        | {round(c[2], 1) for c in t.cells})
            if len(xs) != 12:
                notes.append(f"page {pg.page_number}: {len(xs)} column edges")
                continue
            words = pg.extract_words()
            bands = sorted({(round(c[1], 1), round(c[3], 1)) for c in t.cells})
            cut = header_bottom(words, xs, bands)
            if cut is None:
                # Skipped rather than read on a guess. A page whose header
                # cannot be found is a page where a column label and a town's
                # data are indistinguishable, and reading one as the other is
                # the bug this function exists to stop.
                notes.append(f"page {pg.page_number}: no Town/City header row")
                continue
            ws = [w for w in words if w["top"] >= cut]
            for top, bot in bands:
                if bot <= cut:            # the header band, and the title above it
                    continue
                cells = [cell_lines(ws, xs[i], xs[i + 1], top, bot)
                         for i in range(11)]
                if not any(c for c in cells):
                    continue
                out.append({"page": pg.page_number, "cells": cells, "xs": xs})
    return out, notes


def stitch(rows, towns):
    """Fold every row that does not name a town into the row before it, and
    every row that completes the half-named one above it.

    The second of those is the page break at GREEN'S / GRANT, and it is decided
    by the row above rather than by the row in hand: "GRANT" names Grantham
    perfectly well on its own, and the only thing that says it is not Grantham
    is that the row before it holds "GREEN'S", which is not all of any town's
    name. Joining the two cells has to spell a town in full before this fires,
    so a genuinely new town after a truncated one is still a new town.
    """
    merged, folded, rejoined = [], 0, []
    whole = True
    for r in rows:
        name, ward, raw, got_whole = read_town(r["cells"][TOWN], towns)
        fold = name is None and bool(merged)
        if merged and not whole:
            both = merged[-1]["cells"][TOWN] + r["cells"][TOWN]
            done, _, _, done_whole = read_town(both, towns)
            if done is not None and done_whole:
                fold = True
                rejoined.append(f"{done} (its tail read as {name})"
                                if name else done)
        if fold:
            for i in range(11):
                merged[-1]["cells"][i] = merged[-1]["cells"][i] + r["cells"][i]
            folded += 1
            whole = read_town(merged[-1]["cells"][TOWN], towns)[3]
            continue
        if name is None:
            continue
        merged.append(r)
        whole = got_whole
    return merged, folded, rejoined


def fold_wards(data, towns):
    """A town this site has unwarded, that the Secretary of State wards.

    Eight of them: Berlin, Derry, Farmington, Goffstown, Hudson, Merrimack,
    Salem and Walpole. The ward in this PDF is a voting ward, and the district
    file this site's pages are named after does not divide those towns at all
    -- so `derry` had no row while `derry-ward-1` through `-4` had four, and
    the town page showed nothing.

    The clerk, the phone, the e-mail and the website are the town's and are
    identical across its wards, so they carry over. The polling place is not:
    there are four of them. They go in a list, and the page says so, because
    picking one of four for a reader who has not said which ward they are in
    would be picking wrong three times out of four.
    """
    added = []
    for town, wards in towns.items():
        if wards != ["0"] and len(wards) > 1:
            continue
        s = re.sub(r"[^a-z0-9]+", "-", town.lower()).strip("-")
        if s in data:
            continue
        mine = sorted((k for k in data if k.startswith(s + "-ward-")),
                      key=lambda k: int(k.rsplit("-", 1)[1]))
        if not mine:
            continue
        first = dict(data[mine[0]])
        by = []
        for k in mine:
            r = data[k]
            if r.get("polling_place"):
                by.append({"ward": k.rsplit("-", 1)[1],
                           "polling_place": r["polling_place"],
                           "state_hours": r.get("state_hours", "")})
        for f in ("polling_place", "polling_raw", "state_hours", "local_hours"):
            first.pop(f, None)
        if by:
            first["polling_by_ward"] = by
        data[s] = first
        added.append(f"{town} ({len(mine)} wards)")
    return added


def build(rows, towns):
    data, odd, checked, hits, refused = {}, [], 0, 0, []
    for r in rows:
        cells, xs = r["cells"], r["xs"]
        name, ward, raw, _ = read_town(cells[TOWN], towns)
        if name is None:
            continue
        clerk, clerk_raw = read_clerk(cells[CLERK], xs[CLERK + 1])

        def val(i):
            if i in TIGHT:
                s = "".join(t for t, _ in cells[i])
            else:
                s = geom_join(cells[i], xs[i + 1])
            s = re.sub(r"\s+", " ", s).strip()
            return "" if s.lower() in BLANK else s

        email = val(EMAIL).lower()
        # The Website column, checked against what a website is. The tight join
        # is right for the wrap -- "WWW.GORHA" / "MNH.GOV" is one host -- and
        # wrong for the five cells holding an e-mail address and the one
        # holding a note, so what it produces is only kept if it is a host.
        wrote = val(SITE).lower()
        site = parse_officials.web_address(wrote)
        if site and not site.startswith("http"):
            site = "https://" + site.lstrip("/")
        if wrote and not site:
            refused.append(f"{name}: "
                           f"{geom_join(cells[SITE], xs[SITE + 1]).lower()!r}")
        # THE SECRETARY OF STATE'S OWN CELL REPEATS THE DISTRICT
        # MARKER: "PINKERTON ACADEMY (DIST 1) 5 PINKERTON (DIST 1) ST
        # DERRY" -- the second is inside the street address, where a
        # number and a street name cannot have a district between
        # them. The first is kept: it says which of Derry's four
        # polling places this is.
        poll = re.sub(r"(\((?:DIST|WARD)\.?\s*\d+\))(.*?)\s*\1", r"\1\2",
                      val(POLL))
        rec = {
            "clerk": namecase(clerk), "clerk_raw": clerk_raw,
            "clerk_address": placecase(val(ADDR)),
            "phone": val(PHONE), "email": email, "website": site,
            "polling_place": placecase(poll), "polling_raw": poll,
            "election": val(ELECT), "state_hours": val(SHOURS),
            "local_hours": val(LHOURS),
        }
        s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        key = f"{s}-ward-{ward.lstrip('0') or '0'}" if ward else s
        data[key] = {k: v for k, v in rec.items() if v}
        got = surname_in_email(namecase(clerk), email)
        if got is not None:
            checked += 1
            hits += 1 if got else 0
            if not got:
                odd.append(f"{name}: {namecase(clerk)!r} vs {email}")
    return data, odd, checked, hits, refused


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", default=str(PDF))
    ap.add_argument("--site", default="site")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    pdf = pathlib.Path(a.pdf)
    if not pdf.exists():
        sys.exit(f"{pdf} is not there; the export lives in sources/")
    dj = pathlib.Path(a.site) / "districts.json"
    if not dj.exists():
        sys.exit(f"{dj} is not there; build the site first")
    districts = json.loads(dj.read_text(encoding="utf-8"))
    towns = {t.upper(): sorted(districts[t]) for t in districts}

    n = load_known()
    print(f"  {n} name tokens from town_officials.json to settle joins with"
          if n else "  town_officials.json is not there; joins decided without it")
    raw, notes = read_pdf(pdf)
    rows, folded, rejoined = stitch(raw, towns)
    data, odd, checked, hits, refused = build(rows, towns)
    added = fold_wards(data, towns)
    if added:
        print(f"  {len(added)} towns this site has unwarded, carried over from "
              f"their wards: " + ", ".join(added))
    print(f"  {len(raw)} bands read, {folded} folded into the row above, "
          f"{len(rows)} rows, {len(data)} keyed to a town page")
    if rejoined:
        print(f"    {len(rejoined)} rows a page break cut in half whose tail "
              "named another town on its own: " + ", ".join(rejoined))
    for n in notes:
        print(f"    {n}")
    want = {(t.upper(), w) for t in districts for w in districts[t]}
    have = set()
    for k in data:
        m = re.match(r"^(.*?)(?:-ward-(\d+))?$", k)
        have.add((m.group(1), m.group(2) or "0"))
    missing = sorted(f"{t}" + (f" ward {w}" if w != "0" else "")
                     for t, w in want
                     if (re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-"),
                         w.lstrip("0") or "0") not in have)
    print(f"    {sum(1 for v in data.values() if v.get('polling_place'))}"
          f" of {len(data)} carry a polling place, "
          f"{sum(1 for v in data.values() if v.get('email'))} an e-mail, "
          f"{sum(1 for v in data.values() if v.get('phone'))} a phone, "
          f"{sum(1 for v in data.values() if v.get('website'))} a website")
    if refused:
        print(f"    {len(refused)} whose Website cell is not an address, "
              "recorded as nothing:")
        for line in sorted(set(refused)):
            print(f"      {line}")
    if checked:
        print(f"    surname found in the clerk's own e-mail on {hits} of "
              f"{checked} rows ({100*hits/checked:.0f}%)")
    if missing:
        print(f"    {len(missing)} town pages have no row: "
              + ", ".join(missing[:12]) + (" ..." if len(missing) > 12 else ""))
    if odd:
        print(f"    {len(odd)} rows where the surname is not in the e-mail "
              "(often just a shared office address):")
        for line in odd[:10]:
            print(f"      {line}")
    if a.report:
        print("  --report: nothing written")
        return
    pathlib.Path(a.out).write_text(
        json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"  -> {a.out} ({len(data)} towns and wards)")


if __name__ == "__main__":
    main()
