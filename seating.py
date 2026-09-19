#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.9
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
#
# AND WHERE THE FLOOR IS INSIDE A ROW. A row can be a single run of seats,
# ((97, 94),) and so on, or SEVERAL runs with floor between them, written as
# ((97, 94), 3.5, (93, 91)) -- the number being that much floor, measured in
# seat widths.
#
# Divisions 2 and 4 each have one. Their plan labels put 4097-4094 at the far
# outer edge and 4093-4091 well inside it, with clear floor between: one row
# in two pieces, not two rows. Read as two rows it gave those divisions twelve
# where the others have eleven, and stacked the pieces radially -- which is
# what you see when the back of the hall looks wrong. Read as one gapped row
# the seats still come to 98 and 100 exactly, which is the check that settles
# it either way.
ROWS = {
    5: ((1, 4), (9, 5), (10, 17), (25, 18), (26, 34), (41, 35), (42, 43)),
    4: ((1, 6), (14, 7), (15, 22), (31, 23), (32, 41), (52, 42), (53, 64),
        (77, 65), (78, 90), ((97, 94), 3.5, (93, 91)), (98, 99)),
    3: ((1, 7), (15, 8), (16, 23), (32, 24), (33, 42), (53, 43), (54, 64),
        (76, 65), (77, 89), (103, 90), (104, 119)),
    2: ((1, 6), (14, 7), (15, 22), (31, 23), (32, 41), (52, 42), (53, 64),
        (77, 65), (78, 90), ((99, 97), 3.5, (96, 91)), (100, 101)),
    1: ((1, 4), (9, 5), (10, 17), (25, 18), (26, 34), (41, 35), (42, 43)),
}

# A ROW IS NOT ALWAYS CENTRED IN ITS DIVISION. A short row at the back of the
# hall sits where the walls put it, not in the middle of the wedge, and
# centring every one of them was the thing that made the outer rows look
# wrong. Keyed by (division, row index); the value is how far off centre the
# row sits, as a fraction of the room it has spare. Positive is toward the
# left of the drawing, which is the higher bearing.
#
# THE BACK ROWS HUG THE INNER EDGE -- the side facing the middle of the hall,
# which is the corner the walls cut off. Every one of these was named:
# 5043-5042 and 5041-5035 against the edge nearest division 4; 4099-4098
# against the edge nearest division 3; 2101-2100 likewise; 1041-1035 and
# 1043-1042 against the edge nearest division 2.
#
# They are flush against it, not merely biased toward it, which is what 1.0
# means here. Divisions on the left of the hall take the negative sign and
# those on the right the positive, because the two halves mirror.
ROW_ALIGN = {
    (5, 5): -1.0, (5, 6): -1.0,
    (4, 10): -1.0,
    (2, 10): +1.0,
    (1, 5): +1.0, (1, 6): +1.0,
}

# DIVISIONS 1 AND 5 STAND AGAINST THEIR INNER EDGE, every row of them. Their
# rows run 4, 5, 7, 8, 9, 7, 2 -- growing to nine and then falling back -- so
# no pair of straight edges can bound them and stretching each row to the
# wedge would pull the four-seat front row twice as far apart as the nine-seat
# middle. Lining every row up on the inner side instead gives the block one
# straight edge, the one facing the rest of the hall, and lets the outer side
# step with the row lengths, which is what the wall does.
#
# A lean across the block was tried first and was nearly right, but left the
# inner edge wandering by a degree or so a row, and it fought the back rows,
# which are pinned to that same edge.
INNER = {5: -1.0, 1: +1.0}

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
SPACING = SEAT_R * 2.45      # the closest two seats in a row are allowed to be

# ONE ROW SPACING FOR THE WHOLE HALL. Row k of every division is the same
# distance from the Speaker as row k of every other, so the front rows of
# divisions 2, 3 and 4 line up and so do their backs -- they have eleven rows
# each and the plan shows them level.
#
# This used to be a fixed DEPTH divided by each division's row count, which
# meant the two seven-row divisions spread their rows nearly twice as far
# apart as the eleven-row ones. On the plan they are much the same, and
# divisions 1 and 5 are simply shallower blocks: seven rows deep instead of
# eleven, ending before the others do rather than reaching the same wall with
# gaps between them.
STEP = SPACING * 1.36        # row to row, measured outward from the Speaker

# THE AISLES, AND WHY THEY ARE MEASURED AT THE FRONT. Floor between one
# division and the next, held as an angle so the blocks stay apart at every
# depth. The angle is set from a width in the FRONT row, where the radius is
# smallest and an aisle is therefore at its narrowest -- which is exactly
# where the divisions were reported to touch. Size it anywhere else and the
# front is the place it goes wrong.
AISLE_SEATS = 2.4            # aisle width at the front row, in seat widths

MARGIN = 48.0                # room for the seat radius and the division labels
LABEL_OUT = 26.0             # how far beyond the last row a caption's arc sits
LABEL_UP = 14.0              # how far the letters reach above that arc


def seats_in(division):
    """Every seat number in a division, in order, with 13 left out."""
    return [n for n in range(1, HIGHEST[division] + 1) if n != SKIPPED]


def all_seats():
    """Every seat number on the floor, as division * 1000 + n."""
    return [d * 1000 + n for d in sorted(HIGHEST) for n in seats_in(d)]


def _run(first, last):
    """One unbroken stretch of seats, in the direction the plan gives it.

    Closed up over seat 13, which does not exist rather than standing empty.
    """
    step = 1 if last >= first else -1
    return [n for n in range(first, last + step, step) if n != SKIPPED]


def _parts(division, k):
    row = ROWS[division][k]
    return row if isinstance(row[0], (tuple, list)) else (row,)


def places(division, k, gap_units=None):
    """Row k as [(offset in seat widths, seat number)], left to right.

    The offset is what lets a row carry floor inside it: seats advance one
    unit each, a gap advances by however many seat widths it is worth, and
    nothing is drawn there.

    gap_units replaces the nominal floor with that much in total, shared out
    in the proportions written down. It is how a gapped row is widened to
    reach both edges of its division WITHOUT pulling its seats apart: the
    chairs stay at the hall's spacing and the aisle between them takes up the
    slack, which is what an aisle is.
    """
    parts = _parts(division, k)
    nominal = sum(float(x) for x in parts if isinstance(x, (int, float)))
    scale = (gap_units / nominal) if (gap_units is not None and nominal) else 1.0
    out, at = [], 0.0
    for part in parts:
        if isinstance(part, (int, float)):
            at += float(part) * scale
            continue
        for n in _run(*part):
            out.append((at, n))
            at += 1.0
    return out


def _has_gap(division, k):
    return any(isinstance(x, (int, float)) for x in _parts(division, k))


def rows_of(division):
    """The rows of a division, each a list of seat numbers left to right."""
    return [[n for _, n in places(division, k)]
            for k in range(len(ROWS[division]))]


def _span(division, k):
    """How wide row k is, first seat centre to last, in seat widths."""
    p = places(division, k)
    return (p[-1][0] - p[0][0]) if p else 0.0


def _radii(division, r0):
    """Each row's distance from the Speaker, front to back.

    One ladder for the whole hall: row k is at the same radius in every
    division, so blocks with the same number of rows line up at the front and
    at the back, and a block with fewer rows is simply shallower.
    """
    return [r0 + k * STEP for k in range(len(ROWS[division]))]


def _wedge(division, r0):
    """The angle a division needs, in radians, at this front radius.

    The widest row decides, and it is not always the back row: a front row of
    six seats sitting close to the rostrum can want more angle than thirteen
    seats far behind it.
    """
    rad = _radii(division, r0)
    # Only the rows that reach both edges decide it. The short pair at the
    # back of each division does not: it is placed against a wall rather than
    # spanning the block, so letting it vote would make the wedge narrow
    # enough to crush every row in front of it.
    return max(_span(division, k) * SPACING / rad[k]
               for k in range(len(ROWS[division]))
               if (division, k) not in ROW_ALIGN)


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
        mid, wedge = mids[d]
        rad = _radii(d, r0)
        for k in range(len(ROWS[d])):
            r = rad[k]
            span = _span(d, k)
            align = ROW_ALIGN.get((d, k))
            if align is None and d in INNER:
                align = INNER[d]
            if align is None:
                # THE SEATS ON EACH EDGE MAKE A STRAIGHT LINE. A row reaches
                # both edges of its division, so every row's first seat sits
                # on one bounding line and its last on the other -- and those
                # lines are radial, which is to say straight.
                #
                # That is what decides the spacing, rather than the other way
                # round: the seats of a short row stand a little further apart
                # than those of a long one. Centring every row at one fixed
                # spacing inset the short rows by different amounts and made
                # both edges wander.
                if _has_gap(d, k):
                    # The chairs keep the hall's spacing and the floor between
                    # them widens to reach the edges. Stretching this row like
                    # any other pulled its seats 40% further apart than every
                    # other row in the division, which is not what an aisle
                    # does to the chairs beside it.
                    step = SPACING / r
                    nseat = len(places(d, k))
                    want = wedge / step - (nseat - 1)
                    row_places = places(d, k, gap_units=max(0.0, want))
                    first = mid + wedge / 2
                    for off, seat in row_places:
                        ang = first - step * off
                        pos[d * 1000 + seat] = (CX + r * math.cos(ang),
                                                CY - r * math.sin(ang))
                    continue
                step = wedge / span if span else 0.0
                first = mid + wedge / 2
            else:
                # Except rows placed against something rather than spanning
                # the block: the short pair at the back of divisions 2 and 4,
                # and every row of the two sheared divisions.
                step = SPACING / r
                slack = max(0.0, wedge / step - span)
                first = mid + step * (span / 2 + align * slack / 2)
            for off, seat in places(d, k):
                ang = first - step * off
                pos[d * 1000 + seat] = (CX + r * math.cos(ang),
                                        CY - r * math.sin(ang))
    pos[SPEAKER_SEAT] = (CX, CY)
    return pos


def label_arcs():
    """{division: (radius, high bearing, low bearing)} for its caption's path.

    A CAPTION FOLLOWS ITS BLOCK. They were flat text on a point, which had two
    faults. The small one is that a straight word over a curved block looks
    stuck on. The large one is that divisions 1 and 5 lie at bearings of 4 and
    176 degrees -- very nearly flat -- so their captions sat further out
    sideways than any seat, and "Division 5" was centred at x=16 in a box
    starting at 0: cut in half, at both ends of the hall, in every render
    since the captions were added.

    On an arc just beyond the last row they hug the block instead, and the
    ones at the flat ends run vertically, which is how the Clerk's plan prints
    them.
    """
    r0 = _fit()
    mids = _wedges(r0)
    out = {}
    for d in LEFT_TO_RIGHT:
        mid, w = mids[d]
        out[d] = (_radii(d, r0)[-1] + LABEL_OUT, mid + w / 2, mid - w / 2)
    return out


def _corners():
    """Every point the drawing has to enclose: the seats, and the label arcs.

    The arcs are sampled rather than reasoned about, because the outermost
    point of an arc is not always an endpoint -- a wedge straddling due north
    reaches highest in its middle.
    """
    pts = list(_unshifted().values())
    for r, hi, lo in label_arcs().values():
        for k in range(9):
            a = lo + (hi - lo) * k / 8
            out = r + LABEL_UP
            pts.append((CX + out * math.cos(a), CY - out * math.sin(a)))
    return pts


def _shift():
    """(dx, dy) that puts the drawing's top-left corner at the margin."""
    pts = _corners()
    return (MARGIN - min(x for x, _ in pts), MARGIN - min(y for _, y in pts))


def layout():
    """{seat number: (x, y)} for all 400 floor seats, plus the Speaker."""
    dx, dy = _shift()
    return {s: (x + dx, y + dy) for s, (x, y) in _unshifted().items()}


def extent():
    """(width, height) the drawing needs, with its margins."""
    dx, dy = _shift()
    pts = _corners()
    return (max(x for x, _ in pts) + dx + MARGIN,
            max(y for _, y in pts) + dy + MARGIN)


def label_paths():
    """{division: "M x y A r r 0 0 1 x2 y2"} -- the shifted arc each caption runs on.

    High bearing to low, which is left to right across the drawing, so the
    letters sit the right way up on the outside of the curve.
    """
    dx, dy = _shift()
    out = {}
    for d, (r, hi, lo) in label_arcs().items():
        x1, y1 = CX + r * math.cos(hi) + dx, CY - r * math.sin(hi) + dy
        x2, y2 = CX + r * math.cos(lo) + dx, CY - r * math.sin(lo) + dy
        out[d] = f"M {x1:.1f} {y1:.1f} A {r:.1f} {r:.1f} 0 0 1 {x2:.1f} {y2:.1f}"
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
    pos = _unshifted()
    ends = {}
    for d in LEFT_TO_RIGHT:
        row = rows_of(d)[0]
        ends[d] = [pos[d * 1000 + row[0]], pos[d * 1000 + row[-1]]]
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

    # NOTHING IS DRAWN OUTSIDE THE BOX. The division captions were sized out
    # of the picture for several days: the viewBox was measured from the seats
    # alone, and the two captions at the flat ends of the hall sit further out
    # sideways than any seat does, so "Division 5" was centred at x=16 in a
    # box starting at 0. It looked like a rendering quirk and was arithmetic.
    for d, (r, hi, lo) in label_arcs().items():
        for k in range(9):
            a = lo + (hi - lo) * k / 8
            out = r + LABEL_UP
            x = CX + out * math.cos(a) + _shift()[0]
            y = CY - out * math.sin(a) + _shift()[1]
            assert 0 <= x <= w and 0 <= y <= h, (
                f"division {d}'s caption leaves the drawing at ({x:.0f}, {y:.0f}) "
                f"in a {w:.0f} by {h:.0f} box")
    print(f"  captions inside the drawing                   : {len(label_arcs())}")

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
    paths = label_paths()
    w, h = extent()
    out = [f'<svg viewBox="0 0 {w:.0f} {h:.0f}" class="seatmap" role="img" '
           f'aria-label="{title}: 400 seats in five divisions">',
           f"<title>{title}</title>"]

    # The captions ride an arc just outside each block, so they curve with it
    # and the two at the flat ends of the hall run vertically rather than off
    # the edge of the drawing.
    out.append("<defs>")
    for d in LEFT_TO_RIGHT:
        out.append(f'<path id="divarc{d}" d="{paths[d]}" fill="none"/>')
    out.append("</defs>")
    for d in LEFT_TO_RIGHT:
        out.append(f'<text class="divlabel"><textPath href="#divarc{d}" '
                   f'startOffset="50%" text-anchor="middle">Division {d}'
                   f"</textPath></text>")

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
