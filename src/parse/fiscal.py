#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-08.1
"""
The fiscal note, as the table it is printed as.

    import fiscal
    note, body = fiscal.parse(billtext_body)

WHAT IT IS FOR

884 bills carry a fiscal note, and every one arrives from the PDF as a single
column of lines -- the table flattened, header cells and figures alike:

    Estimated State Impact
    FY 2025
    FY 2026
    FY 2027
    FY 2028
    Revenue
    $0
    ($55,000,000)
    ($55,000,000)
    ($55,000,000)
    Revenue Fund(s)
    Federal Revenue

Read down the page that is four fiscal years and four figures with nothing
saying which belongs to which. It is a table in the bill's own PDF and it is
one here.

THE RULE THAT MATTERS

A figure is placed under a year only when the row has exactly one figure per
year. Where it has fewer -- "$0" then "Indeterminable Increase" for four years
-- the row spans the table instead, because which years the second figure
covers is not stated and putting it under FY 2026 would be inventing an
answer. Same for a row whose label this does not know: the table is handed
back as the lines it came from rather than guessed into columns.

A misaligned figure in a fiscal table is the worst thing this file could
produce. It would look authoritative and be wrong.
"""

import re

# The row labels the General Court's fiscal notes use, lower-cased and with
# the trailing asterisk stripped. Collected from all 884 notes rather than
# imagined: these nine cover every table but eight rows, and those eight are
# what the "raw" fallback exists for.
YEAR_ROWS = {
    "revenue", "expenditures", "appropriations",
    "county revenue", "county expenditures",
    "local revenue", "local expenditures",
    "state revenue", "state expenditures",
}
# Rows whose value is prose and belongs across the whole table.
SPAN_ROWS = {
    "revenue fund(s)", "funding source(s)", "appropriation fund(s)",
    "revenue fund", "funding source",
}

FY = re.compile(r"^FY ?(\d{4})$")
CAPTION = re.compile(r"^Estimated\b.*Impact\b.*$", re.I)
# The heading that ends the block. METHODOLOGY on 752 notes, AGENCIES
# CONTACTED on 125, and seven have neither.
ENDS = re.compile(r"^[A-Z][A-Z &'()*/,.-]{3,60}:\s*$", re.M)
FOOTNOTE = re.compile(r"^\*")


def _key(line):
    return line.strip().rstrip("*").strip().lower()


def _table(lines):
    """One caption's worth of lines as a table, or as itself.

    Returns {"caption", "years", "rows"} where a row is
    {"label", "values", "span"} -- or {"caption", "raw"} where anything in it
    was not recognised.
    """
    caption, i = "", 0
    if lines and CAPTION.match(lines[0]):
        caption, i = lines[0], 1

    years = []
    while i < len(lines) and FY.match(lines[i]):
        years.append(lines[i])
        i += 1

    # The PDF wraps a cell, so "Indeterminable Increase" arrives as two lines
    # and a four-year row counts seven values and spans instead of aligning.
    # Only this pair is rejoined, and only onto a value that is exactly the
    # word it continues -- a general "join short lines" rule would merge two
    # real figures.
    CONT = {"increase", "decrease"}
    rows, cur, foot = [], None, ""
    for line in lines[i:]:
        if FOOTNOTE.match(line):
            foot = line
            continue
        k = _key(line)
        if k in YEAR_ROWS or k in SPAN_ROWS:
            cur = {"label": line, "values": [], "span": k in SPAN_ROWS}
            rows.append(cur)
        elif cur is not None:
            if (cur["values"] and line.strip().lower() in CONT
                    and cur["values"][-1].strip().lower() == "indeterminable"):
                cur["values"][-1] += " " + line.strip()
            else:
                cur["values"].append(line)
        else:
            # A line before any label this knows. The table is not the shape
            # this reads, and a guess here is a figure under the wrong year.
            return {"caption": caption, "raw": lines}

    if not years or not rows:
        return {"caption": caption, "raw": lines}

    for r in rows:
        # One figure per year, or the row spans. Never a partial row laid out
        # as though the missing years were the last ones.
        if not r["span"] and len(r["values"]) != len(years):
            r["span"] = True
    return {"caption": caption, "years": years, "rows": rows,
            **({"footnote": foot} if foot else {})}


def parse(body):
    """(the note, the body with the note taken out) -- or (None, body)."""
    if not body:
        return None, body
    m = re.search(r"^FISCAL IMPACT:?", body, re.M | re.I)
    if not m:
        return None, body
    rest = body[m.start():]
    end = ENDS.search(rest, 20)
    block = rest[:end.start()] if end else rest
    lines = [l.strip() for l in block.split("\n") if l.strip()]
    if not lines:
        return None, body

    # 386 notes put a sentence on the FISCAL IMPACT line itself.
    lead = re.sub(r"^FISCAL IMPACT:?\s*", "", lines[0], flags=re.I).strip()
    lines = lines[1:]

    # A note can hold two tables -- the state's and the political
    # subdivisions' -- one after the other under their own captions.
    groups, cur = [], []
    for line in lines:
        if CAPTION.match(line) and cur:
            groups.append(cur)
            cur = [line]
        else:
            cur.append(line)
    if cur:
        groups.append(cur)

    tables = [_table(g) for g in groups if g]
    tables = [t for t in tables if t.get("rows") or t.get("raw")]
    if not lead and not tables:
        return None, body

    note = {"lead": lead, "tables": tables}
    return note, body[:m.start()] + (rest[end.start():] if end else "")


def check(note):
    """Everything wrong with a parsed note, for a caller that wants to know."""
    bad = []
    for t in note.get("tables", []):
        if "raw" in t:
            continue
        n = len(t.get("years", []))
        for r in t.get("rows", []):
            if not r["span"] and len(r["values"]) != n:
                bad.append(f"{r['label']!r} has {len(r['values'])} figures "
                           f"for {n} years and is not spanning")
    return bad
