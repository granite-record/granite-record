#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A member of the General Court as the site names them: the one way of naming
a member (member_labels: "Rep. Jodi Nelson", with the party and the seat),
the address of their page (member_slug, own_slug), and the names a record
prints read into one form (person_name, sort_name, name_key,
roster_name_keys).

    import members as MEM
    MEM.member_labels("Nelson, Jodi", chamber="H", party="R", district="13", county="Rockingham")
    MEM.member_slug(m, labels)       # "jodi-nelson-rock-13"
    MEM.person_name("Nelson, Jodi")  # "Jodi Nelson"

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: names and slugs, which the members'
records read). It moved here as it stood, comments and all, sitting_labels to
member_labels; the import of parts.py's county and district tag that stood
in it is at the head here instead. It imports no builder (_import_cycles_cut).
build_site_v2 imports every name here back under its own, so
build_site_v2.member_labels and the rest answer as they did, for the bills'
sponsors and votes, main and the checks.
"""

import re
import unicodedata

import state_settings as ST
# The district a label carries (district_tag) is parts.py's, which officials_tabs reads too.
from parts import district_tag


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
