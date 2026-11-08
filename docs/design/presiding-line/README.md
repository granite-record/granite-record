# The Presiding Officers, their chips alone (8 November 2026)

Alice's walk of 7 November 2026, item A: remove this sentence from the
Legislators tab's Presiding Officers block, in English and Spanish:

> The Speaker presides over the House, and the Deputy Speaker sometimes in the
> Speaker's place; the Senate President presides over the Senate.

The block is now its heading and the three chips: Speaker, Deputy Speaker and
Senate President. Each chip's role names the office. The Spanish sentence
(`off.presiding_why`) has left `es.json`.

`_presiding_chips_alone` holds the block to its heading and the chips, with no
"presides", in both languages, and es.json to carrying no `off.presiding_why`.
It fails on the old code (tried in a copy of the tree with the old files put
back).

## The shots

Dry run 6 (https://7c76e0a0.graniterecord.pages.dev) with
`fix/members-elect-polish` 068ed8b0 applied ("before"). "After" is the same
page with this branch's `officials_tabs.presiding` drawn on the preview's own
`officers.json` and `legislators.json`. Playwright served it in place. Each
shot is the block alone.

| Shot | What |
|---|---|
| `a1-{before,after}-{1280,390}-{light,dark}` | `/officials#legislators` |
| `a2-{before,after}-{1280,390}-light` | `/es/officials#legislators` |

The chips are the same before and after; only the sentence goes. No page
scrolls sideways.
