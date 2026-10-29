# District numbers in circles: a design trial

The owner's trial of 29 October 2026: put the district numbers on the
interactive map (the "District numbers" label mode) in circles, to see if they
read better. On branch `design/map-label-circles`. **Nothing merges until the
owner has seen it.**

## What changed

- **The circle.** Each number sits in a circle of the card's colour
  (`--surface`) with a hairline `--ink-2` edge, in place of the halo.
- **One size per layer.** The circle is sized to the layer's longest number
  plus room round it, and is never narrower than 1.6 times the type. The size
  holds at every zoom and does not jump while panning. On a House map the
  longest number is two figures; on the floterials it is four ("HI45").
- **Counties unchanged.** The counties' labels are names, not numbers, and
  keep the halo.
- **Behaviour unchanged.** The labels still let clicks through
  (`pointer-events: none`). They keep their own colours in forced-colours mode,
  as the plain numbers did, and dark mode follows the site's tokens.
- **The layout rule is the same.** A group's numbers (those in no city, then
  each city's) are drawn all or none. Each number's box is now the circle's
  square rather than its figures.

## The cost: circles show far fewer numbers

A circle is taller than the figures it holds. Under the all-or-none rule, one
collision hides a whole group, so the larger boxes cost far more labels than
their size suggests.

The table below comes from the map's own label test
(`tests/test_map_labels.js`), run over the same views on the preview's real
map data. It covers the whole state and twelve places, each at four zooms,
with the map's box at three widths: 49 views per width and layer. The counts
are number labels drawn in total across those views.

| Map, box width | Halo (now) | Circle | Pill (tried) |
|---|---|---|---|
| House, 1366 | 1,551 | 754 | 729 |
| House, 768 | 1,659 | 819 | 796 |
| House, 375 | 613 | 446 | 508 |
| Floterial, 1366 | 485 | 191 | 240 |
| Floterial, 375 | 173 | 104 | 175 |
| Senate, 1366 | 332 | 308 | 307 |
| Executive Council, 1366 | 69 | 69 | 69 |
| Congress, 1366 | 22 | 24 | 23 |

The pill was a rounded box only 1.35 times the type's height, tried to see
whether a smaller shape helps. It does not, much: any box taller than the
figures loses numbers.

Where the loss shows (screenshots below, on real data):

- **The Senate map, whole state.** Today it numbers 23 of the 24 districts at
  1280 and 390. With circles it numbers none: the southern districts are too
  close for 24 circles, so all are hidden.
- **The House map, whole state.** No numbers either way, before or after: the
  House districts never all fit at this size.
- **Manchester, zoom ×7.5** (the zoom at which today's labels first number
  Manchester's wards on a desktop):
  - 1280: halo 23 numbers, circles 11, and none of them are Manchester's.
  - 390: 18 against 6.
- **Manchester, zoom ×12** (the most the map zooms):
  - 1280: 17 numbers either way. The circles read better here, above all on
    the striped (split) districts.
  - 390: halo 16, circles 4. On a phone, Manchester's own numbers never
    appear with circles, even at full zoom (the label test agrees: never
    within eight presses of +, against seven today).

## Preflight is red on this branch, on purpose

`preflight.py --code` fails one check: "the district map's labels never
overlap", which also holds a design rule: Manchester's wards must be numbered
within eight presses of + at every width. With circles they never are in the
phone's box (341px): "Manchester's wards are never labelled (341 numbers)
within eight presses". That failure is the trial's main finding, not a fault
in the build. The check is left as it is: loosening it is the owner's
decision. Everything else passes (879 passed, 1 failed, 9 skipped).

## The screenshots

The screenshots were drawn on the preview site's real data (its
`district_map.json`) on its Officials page. The map was mounted with dev's
`map.js` and `map.css` for "before" and this branch's for "after". Each
screenshot is the map's box alone.

`shots/<before|after>-<view>-<width>-<light|dark>.png`. The views:

- `state-house`: the House map, whole state.
- `state-senate`: the Senate map, whole state.
- `manchester-x7.5`: the House map, centred on Manchester at zoom ×7.5.
- `manchester-x12`: the same at zoom ×12.

`shots/after-forced-*-1280-light.png` are the same four views with forced
colours on.

## To decide

1. **Keep the halo.** The circles read better, but they cost about half the
   House and floterial numbers and all of the Senate's statewide.
2. **Circles anyway, accepting fewer numbers.** It is one CSS rule and the
   sizing in `numbersLayout`, as on this branch.
3. **Circles only where they fit**, with the halo elsewhere. This would change
   the all-or-none rule, so a map could mix the two styles. It is not built.
