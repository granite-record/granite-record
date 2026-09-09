#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.3
"""
One way to write a name, so the same committee reads the same in every term.

    import names
    names.committee("WILDLIFE & RECREATION")   -> "Wildlife & Recreation"
    names.committee("Ways and    Means")       -> "Ways and Means"

WHY

data/bills.json carries 28 committee names in capitals, all of them from terms
before about 2015 -- "COMMERCE, LABOR AND CONSUMER PROTECTION", "WILDLIFE &
RECREATION" -- because that is how the archived bill records write them. The
current term writes them in title case. Same committee, two spellings, and a
reader moving between terms sees the older one shouting.

calendar_meetings.py had a title-caser of its own for the same reason, since
the calendars shout too. This is that function, in one place, so a name is
normalised the same way whichever file is asking. It is deliberately small and
deliberately shared: two implementations of this would drift, and the whole
point is that they do not.

WHAT IT WILL NOT DO

It does not translate. "NO COMMITTEE ASSIGNMENT" becomes "No Committee
Assignment" and not "none", because deciding that a bill has no committee is a
judgment about the record and this only decides how letters are cased.
"""

import re

# Words that stay lower case inside a name, but never at the start of one.
SMALL = {"and", "of", "on", "the", "for", "to", "in", "at", "a", "an", "or",
         "as", "by", "from", "with"}

# Letter runs that are not words and must not be title-cased. Kept short on
# purpose: something belongs here because it was seen in the record, not
# because it might appear one day.
KEEP = {"COVID", "RSA", "RSAS", "LBA", "DHHS", "NH", "US", "OHRV", "CACR",
        "DOT", "DES", "II", "III", "IV"}

WORD = re.compile(r"[A-Za-z][A-Za-z'’]*")


def _word(w, first):
    if w.upper() in KEEP:
        return w.upper()
    low = w.lower()
    if low in SMALL and not first:
        return low
    # Not str.title(): it capitalises after an apostrophe, so O'BRIEN comes
    # back O'Brien but DON'T comes back Don'T.
    return low[:1].upper() + low[1:]


def committee(s):
    """A committee's name as a name rather than a shout."""
    if not s:
        return s or ""
    s = re.sub(r"\s*\(RSA[^)]*\)", "", s)          # "(RSA 21-I:2)" is not a name
    s = re.sub(r",(?=\S)", ", ", s)                # "INSTITUTIONS,HEALTH"
    s = re.sub(r"\s{2,}", " ", s).strip(" ,")
    if not s:
        return ""
    # Only touch a name that is shouting or is already tidy; a mixed-case name
    # somebody wrote deliberately is left exactly as it is.
    letters = [c for c in s if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) < 0.9:
        return s
    out, first = [], True
    pos = 0
    for m in WORD.finditer(s):
        out.append(s[pos:m.start()])
        out.append(_word(m.group(0), first))
        first = False
        pos = m.end()
    out.append(s[pos:])
    return "".join(out)

# --------------------------------------------------------------- a person ---

# The chamber's word for one of its own. The roster carries "Senator" and
# "Representative" in full; these are what fits on a chip.
TITLE = {"H": "Rep.", "S": "Sen."}


def legislator(rec):
    """A member as the site names them: Rep. Erica Layon (R - Rock 13).

    THIS MUST AGREE WITH build_site_v2.member_labels()["display_full"], which
    is the older of the two and the one every page already uses. It is not
    duplicated here for fun: data/legislators.json is written by build_data.py,
    which runs BEFORE build_site_v2 and cannot import it, and its label was
    being built inline as "Abbas, Daryl(R) Rock 22" -- a database row rather
    than a person, and a second format for the same member.

    preflight checks the two against the whole roster, so they cannot drift.

    The rules, all of them the older function's:
      - the honorific comes from the CHAMBER, never from a title field, which
        may hold "Speaker" and is an office rather than a way of referring to
        somebody
      - a Senate seat is SD24; a House seat is its county abbreviation and
        number, and is dropped entirely when the county is unknown, because
        "13" locates nothing
      - an unknown party is dropped rather than guessed, and the district with
        it: "(?)" beside a name is worse than a name on its own
    """
    if not isinstance(rec, dict):
        return str(rec or "")
    first = (rec.get("first") or "").strip()
    last = (rec.get("last") or "").strip()
    if not (first or last):
        nm = (rec.get("name") or "").strip()
        if "," in nm:
            last, first = [x.strip() for x in nm.split(",", 1)]
        else:
            bits = nm.split()
            first, last = " ".join(bits[:-1]), (bits[-1] if bits else "")
    who = " ".join(x for x in (first, last) if x)
    if not who:
        return ""
    ch = (rec.get("chamber") or "").strip().upper()[:1]
    plain = f"{TITLE.get(ch, '')} {who}".strip()
    pc = (rec.get("party_code") or rec.get("party") or "").strip()[:1].upper()
    party = pc if pc in "RDILU" else ""
    d = str(rec.get("district") or "").strip()
    if not d:
        tag = ""
    elif ch == "S":
        tag = f"SD{d}"
    else:
        ab = (rec.get("county_abbr") or "").strip()
        tag = f"{ab} {d}" if ab else ""
    if tag:
        return f"{plain} ({party} - {tag})" if party else f"{plain} ({tag})"
    return f"{plain} ({party})" if party else plain


if __name__ == "__main__":
    for t in ("WILDLIFE & RECREATION", "COMMERCE, LABOR AND CONSUMER PROTECTION",
              "PUBLIC INSTITUTIONS,HEALTH & HUMAN SERVICES",
              "ELECTION LAW AND VETERANS' AFFAIRS", "WAYS AND    MEANS",
              "Special Committee on COVID Response Efficacy",
              "Environment and Agriculture", "NO COMMITTEE ASSIGNMENT"):
        print(f"  {t!r}\n    -> {committee(t)!r}")
