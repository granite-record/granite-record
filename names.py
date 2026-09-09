#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.1
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


if __name__ == "__main__":
    for t in ("WILDLIFE & RECREATION", "COMMERCE, LABOR AND CONSUMER PROTECTION",
              "PUBLIC INSTITUTIONS,HEALTH & HUMAN SERVICES",
              "ELECTION LAW AND VETERANS' AFFAIRS", "WAYS AND    MEANS",
              "Special Committee on COVID Response Efficacy",
              "Environment and Agriculture", "NO COMMITTEE ASSIGNMENT"):
        print(f"  {t!r}\n    -> {committee(t)!r}")
