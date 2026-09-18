#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.5
"""
Where every seat on the New Hampshire House floor goes, as a diagram.

    python3 seating.py --check      # the layout's own arithmetic
    python3 seating.py --svg out.svg

THE NUMBERING IS THE RECORD; THE GEOMETRY IS A DIAGRAM.

A member's seat number is a fact: it is in the General Court's own roster
(field 5 of legislators.txt, and Legislators.seatno in the database), it is
what their licence plate carries, and it decodes as division * 1000 + seat --
3084 is division 3, seat 84.

Where that seat physically sits in Representatives Hall is NOT on this disk.
The Clerk's floor plan is a scanned drawing, not coordinates. What IS on the
plan, and readable, is every row's first and last seat number, and this file
is built from that: the rows, their order, the direction each one runs, and
where the floor has an aisle. It is a schematic of the divisions, not a survey
of the room, and the page says so.

What a reader can rely on: which division a seat is in, which row of it, which
way that row runs, and the seat's number. What they cannot: true distances.

THE ARITHMETIC THAT PROVES THE DECODING

The plan's highest seat in each division is 43, 101, 119, 99 and 43 -- 405
positions. No division has a seat 13. 405 - 5 = 400, which is exactly the
number of seats in the New Hampshire House, the largest state lower chamber in
the country. That agreement is why the decoding can be trusted; --check
asserts it rather than leaving it in a comment.

A sixth "division" holds one seat, 6002, and it is not on the floor at all: it
is the Speaker's chair on the rostrum. It is drawn where the plan draws the
Speaker, and it is a seat like the other 400 rather than a label.
"""

import argparse
import math

# The highest seat number in each division, read off the Clerk's plan. The
# divisions run left to right across the hall as 5, 4, 3, 2, 1.
HIGHEST = {1: 43, 2: 101, 3: 119, 4: 99, 5: 43}
LEFT_TO_RIGHT = [5, 4, 3, 2, 1]

# Thirteen is skipped in every division. This is not a vacancy and not a gap
# in the data: the seat does not exist, and the row closes up over it.
SKIPPED = 13

SPEAKER_SEAT = 6002

# EVERY ROW, AS THE PLAN LABELS IT: (first seat, last seat) in the order the
# row actually runs across the floor, left to right. Two facts live in each
# pair and a third in the order of the tuple.
#
# WHICH SEATS ARE IN THE ROW. Checked rather than eyed: a division's rows must
# account for exactly the seats that division has, each once. A list that
# merely summed to the right total could repeat one seat while dropping
# another, draw two members in one chair, and look perfectly fine.
#
# WHICH WAY THE ROW RUNS. The numbering snakes. 3001-3007 runs left to right,
# then 3015-3008 runs back the other way, then 3016-3023 turns again. Laying
# every row out ascending put the low number on the same side each time, which
# is neither how the seats are numbered nor what somebody holding a licence
# plate is looking for. The two corner rows of divisions 2 and 4 break the
# alternation; the plan is followed rather than the pattern.
#
# HOW DEEP THE ROW IS: front to back, the front row being nearest the Speaker.
ROWS = {
    5: ((1, 4), (9, 5), (10, 17), (25, 18), (26, 34), (41, 35), (42, 43)),
    4: ((1, 6), (14, 7), (15, 22), (31, 23), (32, 41), (52, 42), (53, 64),
        (77, 65), (78, 90), (97, 94), (93, 91), (98, 99)),
    3: ((1, 7), (15, 8), (16, 23), (32, 24), (33, 42), (53, 43), (54, 64),
        (76, 65), (77, 89), (103, 90), (104, 119)),
    2: ((1, 6), (14, 7), (15, 22), (31, 23), (32, 41), (52, 42), (53, 64),
        (77, 65), (78, 90), (96, 91), (99, 97), (100, 101)),
    1: ((1, 4), (9, 5), (10, 17), (25, 18), (26, 34), (41, 35), (42, 43)),
}

# THE CROSS AISLE. Divisions 2 and 4 are not one continuous stack: the plan
# draws their last rows as a small block tucked into the corner of the hall,
# with floor between it and the rest of the division. Without that gap those
# rows read as the back of the block, and the shape is wrong in the one place
# the eye is drawn to. The number is the index of the first row beyond it.
CROSS_AISLE = {4: 9, 2: 9}
CROSS_ROWS = 1.2             # how many rows' worth of floor the gap is

# CONCENTRIC ARCS AROUND THE SPEAKER, which is what the plan draws and what a
# hemicycle is. An earlier version made each division a block of straight rows
# on its own bearing: it got the row lengths right, but the rows of
# neighbouring divisions then converged as they approached the rostrum and
# touched. Arcs cannot do that -- a row sits at one radius from the Speaker,
# so two rows of neighbouring divisions stay as far apart at the front as they
# are at the back.
CX, CY = 0.0, 0.0            # the Speaker; the drawing is shifted to fit later
A_LEFT, A_RIGHT = 178.0, 2.0  # the widest bearings the floor reaches
SEAT_R = 8.5                 # drawn radius of one seat
SPACING = SEAT_R * 2.45      # centre to centre along a row
DEPTH = 330.0                # front row to back row, the same for every division

# THE AISLES, AND WHY THEY ARE MEASURED AT THE FRONT. Floor between one
# division and the next, held as an angle so the blocks stay apart at every
# depth. The angle is set from a width in the FRONT row, where the radius is
# smallest and an aisle is therefore at its narrowest -- which is exactly
# where the divisions were reported to touch. Size it anywhere else and the
# front is the place it goes wrong.
AISLE_SEATS = 2.4            # aisle width at the front row, in seat widths

MARGIN = 48.0                # room for the seat radius and the division labels


def seats_in(division):
    """Every seat number in a division, in order, with 13 left out."""
    return [n for n in range(1, HIGHEST[division] + 1) if n != SKIPPED]


def all_seats():
    """Every seat number on the floor, as division * 1000 + n."""
    return [d * 1000 + n for d in sorted(HIGHEST) for n in seats_in(d)]


def rows_of(division):
    """The rows of a division, each a list of seat numbers left to right.

    In the direction the plan gives the row, and closed up over seat 13, which
    does not exist rather than standing empty.
    """
    out = []
    for first, last in ROWS[division]:
        step = 1 if last >= first else -1
        out.append([n for n in range(first, last + step, step) if n != SKIPPED])
    return out


def _radii(division, r0):
    """Each row's distance from the Speaker, front to back.

    Every division reaches the same depth, so one with seven rows has them
    further apart than one with twelve -- which is what the plan shows: all
    five blocks run from the rostrum to the back of the hall. The cross aisle
    of divisions 2 and 4 spends part of that depth on floor instead of seats.
    """
    rows = ROWS[division]
    cut = CROSS_AISLE.get(division)
    units = (len(rows) - 1) + (CROSS_ROWS if cut is not None else 0.0)
    step = DEPTH / units if units else 0.0
    out, at = [], 0.0
    for k in range(len(rows)):
        if cut is not None and k == cut:
            at += CROSS_ROWS
        out.append(r0 + at * step)
        at += 1.0
    return out


def _wedge(division, r0):
    """The angle a division needs, in radians, at this front radius.

    The widest row decides, and it is not always the back row: a front row of
    six seats sitting close to the rostrum can want more angle than thirteen
    seats far behind it.
    """
    return max(len(r) * SPACING / rad
               for r, rad in zip(rows_of(division), _radii(division, r0)))


def _aisle(r0):
    return AISLE_SEATS * SPACING / r0


def _total(r0):
    return (sum(_wedge(d, r0) for d in LEFT_TO_RIGHT)
            + _aisle(r0) * (len(LEFT_TO_RIGHT) - 1))


def _fit():
    """The smallest front radius at which the floor and its aisles fit.

    Solved, not set. Every term shrinks as the radius grows, so there is one
    crossing and a bisection finds it. Widening the fan is not available -- it
    is already most of a half circle -- and shrinking the seats until the
    arithmetic worked would be tuning a number until the picture stopped
    complaining, so the room grows instead.
    """
    span = math.radians(A_LEFT - A_RIGHT)
    lo, hi = 20.0, 8000.0
    for _ in range(90):
        mid = (lo + hi) / 2
        if _total(mid) <= span:
            hi = mid
        else:
            lo = mid
    return hi


def _wedges(r0):
    """{division: (centre bearing, width)} in radians, left to right."""
    aisle = _aisle(r0)
    out, at = {}, math.radians(A_LEFT)
    for i, d in enumerate(LEFT_TO_RIGHT):
        if i:
            at -= aisle
        w = _wedge(d, r0)
        out[d] = (at - w / 2, w)
        at -= w
    return out


def _unshifted():
    """{seat: (x, y)} with the Speaker at the origin."""
    r0 = _fit()
    mids = _wedges(r0)
    pos = {}
    for d in LEFT_TO_RIGHT:
        mid = mids[d][0]
        for row, r in zip(rows_of(d), _radii(d, r0)):
            step = SPACING / r
            # Centred in the wedge rather than stretched across it, so a
            # four-seat front row sits in the middle of its block the way the
            # plan draws it instead of being pushed out to the aisles.
            first = mid + step * (len(row) - 1) / 2
            for k, seat in enumerate(row):
                ang = first - step * k
                pos[d * 1000 + seat] = (CX + r * math.cos(ang),
                                        CY - r * math.sin(ang))
    pos[SPEAKER_SEAT] = (CX, CY)
    return pos


def _shift():
    """(dx, dy) that puts the drawing's top-left corner at the margin."""
    pos = _unshifted()
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    return MARGIN - min(xs), MARGIN - min(ys)


def layout():
    """{seat number: (x, y)} for all 400 floor seats, plus the Speaker."""
    dx, dy = _shift()
    return {s: (x + dx, y + dy) for s, (x, y) in _unshifted().items()}


def extent():
    """(width, height) the drawing needs, with its margins."""
    pos = layout()
    return (max(x for x, _ in pos.values()) + MARGIN,
            max(y for _, y in pos.values()) + MARGIN)


def labels():
    """{division: (x, y)} for the caption on each block, beyond its last row."""
    r0 = _fit()
    mids = _wedges(r0)
    dx, dy = _shift()
    out = {}
    for d in LEFT_TO_RIGHT:
        mid = mids[d][0]
        r = _radii(d, r0)[-1] + 30
        out[d] = (CX + r * math.cos(mid) + dx, CY - r * math.sin(mid) + dy)
    return out


def _closest(pos):
    """The distance between the two nearest seats anywhere on the floor.

    Compared within a grid of cells rather than every seat against every
    other: 400 seats is 79,800 pairs, which is fine once and wasteful inside a
    search that runs it ninety times.
    """
    cell = SPACING * 1.6
    grid = {}
    for seat, (x, y) in pos.items():
        grid.setdefault((int(x // cell), int(y // cell)), []).append((x, y))
    best = float("inf")
    for (gx, gy), here in grid.items():
        near = [q for ex in (-1, 0, 1) for ey in (-1, 0, 1)
                for q in grid.get((gx + ex, gy + ey), ())]
        for (x1, y1) in here:
            for (x2, y2) in near:
                if x1 == x2 and y1 == y2:
                    continue
                best = min(best, math.hypot(x1 - x2, y1 - y2))
    return best


def _front_aisles():
    """The floor between neighbouring divisions' FRONT rows, in drawing units.

    Measured between the actual end seats rather than inferred from the angle,
    because the angle is the thing under test.
    """
    r0 = _fit()
    mids = _wedges(r0)
    ends = {}
    for d in LEFT_TO_RIGHT:
        row = rows_of(d)[0]
        rad = _radii(d, r0)[0]
        mid = mids[d][0]
        step = SPACING / rad
        half = step * (len(row) - 1) / 2
        ends[d] = [(CX + rad * math.cos(mid + half), CY - rad * math.sin(mid + half)),
                   (CX + rad * math.cos(mid - half), CY - rad * math.sin(mid - half))]
    return [math.hypot(ends[a][1][0] - ends[b][0][0], ends[a][1][1] - ends[b][0][1])
            for a, b in zip(LEFT_TO_RIGHT, LEFT_TO_RIGHT[1:])]


def check():
    """The arithmetic that says the seat numbering was decoded correctly."""
    positions = sum(HIGHEST.values())
    floor = sum(len(seats_in(d)) for d in HIGHEST)
    print(f"highest seat per division: {HIGHEST}")
    print(f"  numbered positions 1..N across five divisions : {positions}")
    print(f"  less the seat 13 no division has              : -{len(HIGHEST)}")
    print(f"  seats on the floor                            : {floor}")
    assert positions - len(HIGHEST) == floor
    assert floor == 400, f"the House has 400 seats, this lays out {floor}"
    print("  the New Hampshire House has                   : 400  OK")

    # THE ROWS ACCOUNT FOR THE SEATS, EACH ONCE. This is what makes ROWS a
    # reading of the plan rather than an impression of it. A row list that
    # merely summed correctly could repeat one seat while dropping another,
    # and would draw two members in one chair without looking wrong.
    for d in sorted(HIGHEST):
        got = [n for row in rows_of(d) for n in row]
        assert len(got) == len(set(got)), f"division {d} repeats a seat"
        assert sorted(got) == seats_in(d), (
            f"division {d}: its rows do not account for its seats exactly once")
    print("  every division's rows account for its seats    : OK")

    pos = layout()
    assert len(pos) == floor + 1, f"{len(pos)} placed, wanted {floor} + the Speaker"
    assert SPEAKER_SEAT in pos

    # No two seats on top of each other. An overlap in a diagram of who sits
    # where does not read as a rendering fault, it hides one member behind
    # another. Checked across divisions as well as within them, because the
    # place two blocks come closest is between them and near the front.
    near = _closest({s: p for s, p in pos.items() if s != SPEAKER_SEAT})
    w, h = extent()
    print(f"  seats placed                                  : {len(pos) - 1} + Speaker")
    print(f"  closest two seats                             : {near:.1f} "
          f"(a seat is {SEAT_R * 2:.0f} across)")
    print(f"  drawing                                       : {w:.0f} x {h:.0f}")
    assert near >= SEAT_R * 2, f"two seats are {near:.1f} apart and would overlap"

    # THE AISLES ARE STILL AISLES AT THE FRONT, which is where they are
    # narrowest and where they were reported to close up.
    aisles = _front_aisles()
    print(f"  aisles at the front row                       : "
          + ", ".join(f"{a:.0f}" for a in aisles))
    assert min(aisles) >= SEAT_R * 2.6, (
        f"two divisions come within {min(aisles):.1f} at the front, which reads "
        "as the blocks touching")

    # Every seated member openable from the chart, the Speaker included -- the
    # rostrum was once drawn as furniture and skipped over.
    who = {s: {"name": f"Member {s}", "slug": f"m{s}", "party_code": "R"}
           for s in all_seats() + [SPEAKER_SEAT]}
    drawn = svg(who)
    assert drawn.count("data-slug=") == len(who), (
        f"{drawn.count('data-slug=')} of {len(who)} seated members are openable")
    print(f"  seats a reader can open                       : {len(who)}")
    print("")
    print("OK")
    return 0


def svg(by_seat=None, title="New Hampshire House seating"):
    """The chart. by_seat maps a seat number to a dict with name/party/slug.

    Every seat is drawn whether or not somebody holds it, because an empty
    chair is a fact about the House worth showing. A seat with a member
    carries the data attributes the page's script reads; a vacant one says so
    and is not a link.
    """
    by_seat = by_seat or {}
    pos = layout()
    caption = labels()
    w, h = extent()
    out = [f'<svg viewBox="0 0 {w:.0f} {h:.0f}" class="seatmap" role="img" '
           f'aria-label="{title}: 400 seats in five divisions">',
           f"<title>{title}</title>"]

    for d in LEFT_TO_RIGHT:
        lx, ly = caption[d]
        out.append(f'<text class="divlabel" x="{lx:.0f}" y="{ly:.0f}" '
                   f'text-anchor="middle">Division {d}</text>')

    for seat in all_seats():
        x, y = pos[seat]
        m = by_seat.get(seat)
        d, n = divmod(seat, 1000)
        cls = "seat" + ("" if m else " vacant")
        party = (m or {}).get("party_code") or ""
        attrs = f'data-seat="{seat}" data-div="{d}" data-n="{n}"'
        if m:
            attrs += (f' data-slug="{m.get("slug", "")}"'
                      f' data-name="{m.get("name", "")}" tabindex="0" role="button"')
        label = (f'{m.get("name")} — division {d}, seat {n}' if m
                 else f'Vacant — division {d}, seat {n}')
        out.append(
            f'<circle class="{cls} p-{party}" cx="{x:.1f}" cy="{y:.1f}" '
            f'r="{SEAT_R}" {attrs}><title>{label}</title></circle>')

    # THE SPEAKER IS A MEMBER, NOT FURNITURE. This was a grey box with the
    # word "Speaker" in it that the loop then skipped, so the one
    # representative whose chair is on the rostrum -- 382 hold a seat and this
    # was the 382nd -- was on the chart as a label and could not be opened
    # from it. A seat like the others now, drawn where the plan draws the
    # rostrum, with the word beneath it.
    sx, sy = pos[SPEAKER_SEAT]
    sp = by_seat.get(SPEAKER_SEAT)
    at = ""
    if sp:
        at = (f' data-seat="{SPEAKER_SEAT}" data-div="6" data-n="2"'
              f' data-slug="{sp.get("slug", "")}" data-name="{sp.get("name", "")}"'
              f' tabindex="0" role="button"')
    inner = (f'{sp["name"]} — Speaker, on the rostrum' if sp
             else "The Speaker’s chair")
    out.append(
        f'<g class="rostrumgrp"{at}>'
        f'<circle class="seat rostrum p-{(sp or {}).get("party_code", "")}'
        f'{"" if sp else " vacant"}" cx="{sx:.1f}" cy="{sy:.1f}" r="{SEAT_R}"></circle>'
        f'<text class="rostrumtext" x="{sx:.0f}" y="{sy + 27:.0f}" '
        f'text-anchor="middle">Speaker</text>'
        f'<title>{inner}</title></g>')
    out.append("</svg>")
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="assert the layout's arithmetic and that nothing overlaps")
    ap.add_argument("--svg", help="write the empty chart to a file, to look at")
    a = ap.parse_args()
    if a.svg:
        from pathlib import Path
        Path(a.svg).write_text(
            '<!doctype html><meta charset="utf-8">'
            '<style>body{background:#111514;margin:0}'
            '.seatmap{width:100%;height:auto}'
            '.seat{fill:#2b4a3f;stroke:#8fb3a6;stroke-width:1}'
            '.seat.vacant{fill:none;stroke:#555;stroke-dasharray:2 2}'
            '.rostrumtext,.divlabel{fill:#ccc;font:12px sans-serif}'
            '</style>' + svg(), encoding="utf-8")
        print(f"wrote {a.svg}")
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
