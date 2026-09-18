#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-18.2
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

# The fan. Angles are degrees, measured from the positive x axis, and the
# seats sweep from left to right across the top of the circle.
CX, CY = 500.0, 540.0        # the focus, at the Speaker's desk
R0, DR = 120.0, 27.0         # first row's radius, and the gap between rows
A_LEFT, A_RIGHT = 172.0, 8.0  # the widest angles seats reach
SEAT_R = 8.5                 # drawn radius of one seat


def _capacity(width_deg, radius):
    """How many seats fit across a wedge of this width at this radius.

    At least one, so a narrow division still fills rather than looping.
    """
    arc = math.radians(width_deg) * radius
    return max(1, int(arc // (SEAT_R * 2.6)))


def seats_in(division):
    """Every seat number in a division, in order, with 13 left out."""
    return [n for n in range(1, HIGHEST[division] + 1) if n != SKIPPED]


def all_seats():
    """Every seat number on the floor, as division * 1000 + n."""
    return [d * 1000 + n for d in sorted(HIGHEST) for n in seats_in(d)]


def layout():
    """{seat number: (x, y)} for all 400 floor seats, plus the Speaker.

    Each division gets a slice of the fan proportional to how many seats it
    holds, so the big middle division is wide and the two end divisions are
    narrow -- which is the proportion the plan shows. Within a division the
    seats fill row by row outward from the Speaker, and each row holds as many
    as fit at its radius, so the rows lengthen as they go back.
    """
    counts = {d: len(seats_in(d)) for d in HIGHEST}
    total = sum(counts.values())
    span = A_LEFT - A_RIGHT

    pos, at = {}, A_LEFT
    for d in LEFT_TO_RIGHT:
        width = span * counts[d] / total
        hi, lo = at, at - width          # angles decrease left to right
        at = lo

        todo = seats_in(d)
        # ROWS ARE ALLOCATED, NOT FILLED GREEDILY. Taking as many as fit at
        # each radius and letting the remainder fall into a final row left
        # two or three seats floating alone above an otherwise full division,
        # which read as a mistake rather than as the back row. Instead: find
        # the fewest rows that can hold the division, then hand the seats out
        # in proportion to how much room each row has, so the back row is
        # short in the way a real back row is short rather than nearly empty.
        rows = 1
        while sum(_capacity(width, R0 + k * DR) for k in range(rows)) < len(todo):
            rows += 1
        caps = [_capacity(width, R0 + k * DR) for k in range(rows)]
        share, given = sum(caps), 0
        per = []
        for k, c in enumerate(caps):
            n = round(len(todo) * c / share) if k < rows - 1 else len(todo) - given
            n = max(0, min(n, len(todo) - given))
            per.append(n)
            given += n
        # Rounding can leave a seat or two unplaced; put them in the back row,
        # which has the most room for them.
        if given < len(todo):
            per[-1] += len(todo) - given

        i = 0
        for row, n in enumerate(per):
            if not n:
                continue
            r = R0 + row * DR
            take = todo[i:i + n]
            if len(take) == 1:
                angles = [(hi + lo) / 2]
            else:
                step = (hi - lo) / len(take)
                angles = [hi - step * (k + 0.5) for k in range(len(take))]
            for seat, ang in zip(take, angles):
                t = math.radians(ang)
                pos[d * 1000 + seat] = (CX + r * math.cos(t),
                                        CY - r * math.sin(t))
            i += len(take)

    pos[SPEAKER_SEAT] = (CX, CY - 40.0)
    return pos


def check():
    """The arithmetic that says the decoding is right, asserted not asserted at."""
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

    pos = layout()
    assert len(pos) == floor + 1, f"{len(pos)} placed, wanted {floor} + the Speaker"
    assert SPEAKER_SEAT in pos
    # No two seats on top of each other: a diagram that overlaps is unreadable
    # and, worse, hides a member behind another member.
    pts = sorted(pos.items())
    close = 0
    for i, (s1, (x1, y1)) in enumerate(pts):
        for s2, (x2, y2) in pts[i + 1:]:
            if math.hypot(x1 - x2, y1 - y2) < SEAT_R * 1.6:
                close += 1
    print(f"  seats placed                                  : {len(pos) - 1} + Speaker")
    print(f"  pairs closer than a seat's width              : {close}")
    assert close == 0, f"{close} pairs of seats overlap; the diagram would hide members"
    print("\nOK")
    return 0


def svg(by_seat=None, title="New Hampshire House seating"):
    """The chart. by_seat maps a seat number to a dict with name/party/slug.

    Every seat is drawn whether or not somebody holds it, because an empty
    chair is a fact about the House worth showing -- 18 of the 400 are vacant.
    A seat with a member carries the data attributes the page's script reads;
    a vacant one says so and is not a link.
    """
    by_seat = by_seat or {}
    pos = layout()
    out = [f'<svg viewBox="0 0 1000 560" class="seatmap" role="img" '
           f'aria-label="{title}: 400 seats in five divisions">']
    out.append('<title>%s</title>' % title)

    # The rostrum, so the diagram has a front and the fan has a reason.
    #
    # AND THE SPEAKER IS A MEMBER, NOT FURNITURE. This drew a grey box with
    # the word "Speaker" in it and then `continue`d past seat 6002, so the one
    # representative whose seat is on the rostrum -- 382 of them hold a seat
    # and this was the 382nd -- appeared on the chart as a label and could not
    # be reached from it. The box carries their name and the same data
    # attributes every other seat carries, so the page's one click handler
    # opens them like anyone else.
    sx, sy = pos[SPEAKER_SEAT]
    sp = by_seat.get(SPEAKER_SEAT)
    at = ""
    if sp:
        at = (f' data-seat="{SPEAKER_SEAT}" data-div="6" data-n="2"'
              f' data-slug="{sp.get("slug", "")}" data-name="{sp.get("name", "")}"'
              f' tabindex="0" role="button"')
    out.append(f'<g class="rostrumgrp"{at}>'
               f'<rect class="rostrum{"" if sp else " vacant"}" x="{CX-90:.0f}" '
               f'y="{sy-14:.0f}" width="180" height="30" rx="6"></rect>'
               f'<text class="rostrumtext" x="{CX:.0f}" y="{sy+7:.0f}" '
               f'text-anchor="middle">{sp["name"] if sp else "Speaker"}</text>'
               f'<title>{(sp["name"] + " — Speaker, on the rostrum") if sp else "The Speaker’s chair"}</title>'
               f'</g>')

    for seat in all_seats() + [SPEAKER_SEAT]:
        x, y = pos[seat]
        m = by_seat.get(seat)
        d, n = divmod(seat, 1000)
        if seat == SPEAKER_SEAT:
            continue
        cls = "seat" + ("" if m else " vacant")
        party = (m or {}).get("party_code") or ""
        attrs = (f'data-seat="{seat}" data-div="{d}" data-n="{n}"')
        if m:
            attrs += (f' data-slug="{m.get("slug","")}"'
                      f' data-name="{m.get("name","")}"')
        label = (f'{m.get("name")} — division {d}, seat {n}' if m
                 else f'Vacant — division {d}, seat {n}')
        out.append(
            f'<circle class="{cls} p-{party}" cx="{x:.1f}" cy="{y:.1f}" '
            f'r="{SEAT_R}" {attrs} tabindex="0" role="button">'
            f'<title>{label}</title></circle>')
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
