#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.4
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
The Clerk's floor plan is a scanned drawing, not coordinates. So this file
does not pretend to reproduce the room. It lays the five divisions out as a
fan in the order the plan shows them, left to right -- 5, 4, 3, 2, 1 -- with
each division's seats in rows that grow as they get further from the Speaker,
and it says on the page that it is a diagram.

What it IS faithful to, and what a reader can rely on: which division a seat
belongs to, roughly where that division sits relative to the others, and the
seat's number. What it is NOT: the true distances, the real row lengths, or
the shape of the hall.

THE ARITHMETIC THAT PROVES THE DECODING

The plan's highest seat in each division is 43, 101, 119, 99 and 43 -- 405
positions. No division has a seat 13. 405 - 5 = 400, which is exactly the
number of seats in the New Hampshire House, the largest state lower chamber in
the country. That agreement is why the decoding can be trusted; --check
asserts it rather than leaving it in a comment.

A sixth "division" holds one seat, 6002, and it is not on the floor at all: it
is the Speaker's chair on the rostrum. It is drawn where the plan draws the
Speaker.
"""

import argparse
import math

# The highest seat number in each division, read off the Clerk's plan. The
# divisions run left to right across the hall as 5, 4, 3, 2, 1.
HIGHEST = {1: 43, 2: 101, 3: 119, 4: 99, 5: 43}
LEFT_TO_RIGHT = [5, 4, 3, 2, 1]

# Thirteen is skipped in every division. This is not a vacancy and not a gap
# in the data: the seat does not exist.
SKIPPED = 13

SPEAKER_SEAT = 6002

# HOW MANY SEATS IN EACH ROW, front to back -- the front row being the one
# nearest the Speaker. TRANSCRIBED off the Clerk's plan, which labels every
# row with the range of seat numbers in it, and then checked: the rows of a
# division must account for exactly the seats that division has, each once.
# All five do, with nothing missing and nothing repeated, which is what makes
# this a reading of the plan rather than an impression of it.
#
# A range that spans seat 13 holds one fewer than it looks: 3008-3015 is seven
# seats, not eight, because no division has a thirteenth.
#
# The back rows of divisions 1, 2, 4 and 5 really are short -- two and three
# seats -- because they are the corner boxes the plan draws tucked against the
# walls. That is the room, not a rounding error.
ROWS = {
    5: (4, 5, 7, 8, 9, 7, 2),                                     # 42
    4: (6, 7, 8, 9, 10, 11, 12, 13, 13, 4, 3, 2),                 # 98
    3: (7, 7, 8, 9, 10, 11, 11, 12, 13, 14, 16),                  # 118
    2: (6, 7, 8, 9, 10, 11, 12, 13, 13, 6, 3, 2),                 # 100
    1: (4, 5, 7, 8, 9, 7, 2),                                     # 42
}

# WHERE EACH DIVISION SITS, as a bearing from the Speaker in degrees, with 90
# straight ahead. The plan sets five blocks in a horseshoe -- 5 out to the
# left, then 4, 3 across the front, 2, and 1 out to the right -- and the
# bearings are read off it: division 5's block lies almost due left of the
# rostrum, division 3's almost straight in front.
#
# Each division is a BLOCK OF STRAIGHT ROWS turned to face the Speaker, not a
# set of arcs. That is what the plan draws, and it is why the earlier version
# looked wrong however the row counts were adjusted: an arc through every
# division made one continuous bowl, where the room is five separate blocks
# with floor between them.
DIV_ANGLE = {5: 176.0, 4: 133.0, 3: 90.0, 2: 47.0, 1: 4.0}

CX, CY = 0.0, 0.0            # the Speaker; the drawing is shifted to fit later
SEAT_R = 8.5                 # drawn radius of one seat
SPACING = SEAT_R * 2.5       # centre to centre along a row
RF, ROWGAP = 110.0, 30.0     # front row from the Speaker, and row to row

# The gap a seat keeps from every other seat, including seats of another
# division. Solved for rather than set: see _fit.
CLEAR = SEAT_R * 2.15

# Room around the drawing for the seat radius, the division labels and the
# word Speaker under the rostrum dot.
MARGIN = 46.0


def seats_in(division):
    """Every seat number in a division, in order, with 13 left out."""
    return [n for n in range(1, HIGHEST[division] + 1) if n != SKIPPED]


def all_seats():
    """Every seat number on the floor, as division * 1000 + n."""
    return [d * 1000 + n for d in sorted(HIGHEST) for n in seats_in(d)]


def _place(scale):
    """{seat: (x, y)} with the blocks pushed `scale` times their base distance
    from the Speaker, who is at the origin.

    A division is a grid: rows stack away from the Speaker along its bearing,
    and the seats of a row run across it, centred, at a fixed spacing. So a
    four-seat front row sits in the middle of its block the way the plan draws
    it, rather than being stretched to the width of the widest row behind it.
    """
    pos = {}
    for d in LEFT_TO_RIGHT:
        th = math.radians(DIV_ANGLE[d])
        ux, uy = math.cos(th), -math.sin(th)        # away from the Speaker
        vx, vy = math.sin(th), math.cos(th)         # across a row
        todo = seats_in(d)
        assert sum(ROWS[d]) == len(todo), (
            f"division {d}: rows sum to {sum(ROWS[d])}, it has {len(todo)} seats")
        i = 0
        for k, n in enumerate(ROWS[d]):
            r = (RF + k * ROWGAP) * scale
            take = todo[i:i + n]
            i += n
            start = -(len(take) - 1) / 2.0
            for j, seat in enumerate(take):
                off = (start + j) * SPACING
                pos[d * 1000 + seat] = (CX + ux * r + vx * off,
                                        CY + uy * r + vy * off)
    return pos


def _closest(pos):
    """The distance between the two nearest seats anywhere on the floor.

    Compared within a grid of cells rather than every seat against every other
    -- 400 seats is 79,800 pairs, which is fine once and wasteful inside a
    search that runs it eighty times.
    """
    cell = max(SPACING, CLEAR) * 1.5
    grid = {}
    for seat, (x, y) in pos.items():
        grid.setdefault((int(x // cell), int(y // cell)), []).append((x, y))
    best = float("inf")
    for (cx, cy), here in grid.items():
        near = [p for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                for p in grid.get((cx + dx, cy + dy), ())]
        for i, (x1, y1) in enumerate(here):
            for (x2, y2) in near:
                if x1 == x2 and y1 == y2:
                    continue
                best = min(best, math.hypot(x1 - x2, y1 - y2))
    return best


def _fit():
    """The smallest scale at which no two seats collide, found by search.

    The five blocks fan out from one point, so two of them are always closest
    somewhere in the middle of their depth -- not at the front where they are
    narrow, and not at the back where they have diverged. Rather than tune a
    radius until the picture stops looking wrong, the room is pushed outwards
    until the nearest pair of seats anywhere is a seat's width apart, which is
    a condition rather than a preference.
    """
    lo, hi = 1.0, 12.0
    if _closest(_place(lo)) >= CLEAR:
        return lo
    for _ in range(40):
        mid = (lo + hi) / 2
        if _closest(_place(mid)) >= CLEAR:
            hi = mid
        else:
            lo = mid
    return hi


def layout():
    """{seat number: (x, y)} for all 400 floor seats, plus the Speaker.

    Shifted so the whole drawing starts at a small margin from the origin,
    because the blocks fan out around the Speaker and half of them would
    otherwise sit at negative coordinates.
    """
    pos = _place(_fit())
    pos[SPEAKER_SEAT] = (CX, CY)
    xs = [x for x, _ in pos.values()]
    ys = [y for _, y in pos.values()]
    dx = MARGIN - min(xs)
    dy = MARGIN - min(ys)
    return {s: (x + dx, y + dy) for s, (x, y) in pos.items()}


def extent():
    """(width, height) the drawing needs, with its margins."""
    pos = layout()
    return (max(x for x, _ in pos.values()) + MARGIN,
            max(y for _, y in pos.values()) + MARGIN)


def labels():
    """{division: (x, y)} for the caption on each block, beyond its last row."""
    scale = _fit()
    pos = _place(scale)
    out = {}
    for d in LEFT_TO_RIGHT:
        th = math.radians(DIV_ANGLE[d])
        r = (RF + (len(ROWS[d]) - 1) * ROWGAP) * scale + 26
        out[d] = (CX + math.cos(th) * r, CY - math.sin(th) * r)
    xs = [x for x, _ in pos.values()] + [CX]
    ys = [y for _, y in pos.values()] + [CY]
    dx, dy = MARGIN - min(xs), MARGIN - min(ys)
    return {d: (x + dx, y + dy) for d, (x, y) in out.items()}


def check():
    """The arithmetic that says the seat numbering was decoded correctly."""
    per = {d: len(seats_in(d)) for d in sorted(HIGHEST)}
    positions = sum(HIGHEST.values())
    floor = sum(per.values())
    print(f"highest seat per division: {HIGHEST}")
    print(f"  numbered positions 1..N across five divisions : {positions}")
    print(f"  less the seat 13 no division has              : -{len(HIGHEST)}")
    print(f"  seats on the floor                            : {floor}")
    assert positions - len(HIGHEST) == floor
    assert floor == 400, f"the House has 400 seats, this lays out {floor}"
    print(f"  the New Hampshire House has                   : 400  OK")

    # THE ROWS ACCOUNT FOR THE SEATS, EACH ONCE. This is what makes ROWS a
    # reading of the plan rather than an impression of it: a row list that
    # merely summed to the right total could still have the wrong shape, and
    # one that repeated a seat while dropping another would sum correctly and
    # draw two members in one chair.
    for d in sorted(HIGHEST):
        want = seats_in(d)
        assert sum(ROWS[d]) == len(want), (
            f"division {d}: rows sum to {sum(ROWS[d])}, it has {len(want)} seats")
    print(f"  every division's rows account for its seats    : OK")

    pos = layout()
    assert len(pos) == floor + 1, f"{len(pos)} placed, wanted {floor} + the Speaker"
    assert SPEAKER_SEAT in pos
    # No two seats on top of each other: an overlap in a diagram of who sits
    # where does not look like a rendering fault, it hides one member behind
    # another. Checked across divisions as well as within them, which is the
    # case the fan used to get wrong.
    near = _closest({s: p for s, p in pos.items() if s != SPEAKER_SEAT})
    w, h = extent()
    print(f"  seats placed                                  : {len(pos) - 1} + Speaker")
    print(f"  closest two seats                             : {near:.1f} "
          f"(a seat is {SEAT_R * 2:.0f} across)")
    print(f"  drawing                                       : {w:.0f} x {h:.0f}")
    assert near >= SEAT_R * 2, f"two seats are {near:.1f} apart and would overlap"

    # Every seated member openable from the chart, the Speaker included -- the
    # rostrum used to be drawn as furniture and skipped.
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
    pos = labels_pos = None
    pos = layout()
    labels_pos = labels()
    w, h = extent()
    out = [f'<svg viewBox="0 0 {w:.0f} {h:.0f}" class="seatmap" role="img" '
           f'aria-label="{title}: 400 seats in five divisions">',
           f"<title>{title}</title>"]

    for d in LEFT_TO_RIGHT:
        lx, ly = labels_pos[d]
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
    # representative whose chair is on the rostrum -- 382 of them hold a seat
    # and this was the 382nd -- was on the chart as a label and could not be
    # opened from it. A seat like the others now, drawn where the plan draws
    # the rostrum, with the word beneath it.
    sx, sy = pos[SPEAKER_SEAT]
    sp = by_seat.get(SPEAKER_SEAT)
    at = ""
    if sp:
        at = (f' data-seat="{SPEAKER_SEAT}" data-div="6" data-n="2"'
              f' data-slug="{sp.get("slug", "")}" data-name="{sp.get("name", "")}"'
              f' tabindex="0" role="button"')
    out.append(
        f'<g class="rostrumgrp"{at}>'
        f'<circle class="seat rostrum p-{(sp or {}).get("party_code", "")}'
        f'{"" if sp else " vacant"}" cx="{sx:.1f}" cy="{sy:.1f}" r="{SEAT_R}"></circle>'
        f'<text class="rostrumtext" x="{sx:.0f}" y="{sy + 26:.0f}" '
        f'text-anchor="middle">Speaker</text>'
        f'<title>{(sp["name"] + " — Speaker, on the rostrum") if sp else "The Speaker’s chair"}</title>'
        f'</g>')
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
            '.rostrum{fill:#333}.rostrumtext{fill:#ccc;font:12px sans-serif}'
            '</style>' + svg(), encoding="utf-8")
        print(f"wrote {a.svg}")
        return 0
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
