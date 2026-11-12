# The header's second row, and Officials as a hub

Branch `feat/header-rows`, from dev 6b618b6 (12 November 2026). For the 24
November release if built and proven by 20 November, otherwise 9 December.

## The design

The prototype Alice approved on 7 November, "Header Navigation Prototype":
https://claude.ai/artifact/BEtiaw3PxhQCYUfHzn63r8 (private to its owner).

Its first three artboards are the approved header: the six tabs as they are,
and under them a second row of the current section's own pages; on a phone a
strip under the bar, and a menu that lists every section's pages.

The three below them, added 12 November, are the Officials addition (Alice, 7
November), drawn for her OK before it is built:

- **Officials, 1280** (interactive): the overview Officials opens on, its
  cards, and the My Town pop-up, opened from Settings ("Your town") or from
  the overview's "Who represents Dover, Ward 1". The Legislators item shows the
  "Your rep" marks kept. A dark toggle is in the artboard's tweaks.
- **Officials, 390** (interactive): the same on a phone; the pop-up is a full
  sheet.
- **Officials: what moves**: the proposals below and the questions.

## Proposals, for Alice's OK

1. **The row**: Overview | Legislators | Members-elect (until 2 December) |
   Elections | Executive | Judicial | Federal | County | Map | Former members.
2. **The old My Town addresses open the pop-up.** `/officials#my-town` opens
   the overview with the pop-up open; `/officials?town=Dover` opens it on
   Dover, as the tab does today. `/town/dover` and the other warded cities
   already lead to `?town=`, and have no single page of their own to go to.
3. **A town or ward page** lights Officials and no row item. The Map gets an
   item of its own (today it is inside My Town).

## Questions

1. Is the row's order right, with Members-elect in it until 2 December?
2. Should `#my-town` and `?town=` open the pop-up rather than a town's page?
3. Does the overview lead with "Who represents your town?" above its cards, as
   drawn, or should the pop-up open only from Settings?

The header rows themselves, already approved, are being built meanwhile; the
overview and the pop-up wait for the answers.
