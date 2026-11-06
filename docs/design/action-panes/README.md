# Action panes open beside their button; Testify's closed wording

Branch `fix/action-panes`, off dev 2e324165, for the 24 Nov train (merges
from Wed 11 Nov). These are the owner's two requests of 6 November 2026.

## 1. Panes open to the left on a desktop

**Before.** Above a phone's width, a head's actions (Cite this page,
Testify, Follow, Print, Share, Report a problem) are its right-hand column.
Every pane hung from the column's foot, right-aligned under the stack, so it
read as disconnected from its button.

**After.** Each of Cite, Testify, Follow and Report a problem is what its
pane is measured from:
- the pane's top is level with its button's top;
- its right edge stops a gap short of the column;
- it fills the room between the title and facts and the buttons;
- it never covers the button that opened it.

On a phone (45em and under), the buttons are a row under the head, and the
panes open below it as before. Print and Share have no pane.

**Where.** It is one CSS rule, on `.racts`, the column every record head
draws (`components.record_head`, app.js `billHead`). So it applies on
bills, members, committees, session days, roll calls on no bill and study
committees. No script changed, so keyboard, focus and Escape are as they
were.

**Measured.** In a browser on the real built site, on HB 1123 of 2026 and the
House's 21 May 2026, at 390, 1024, 1280 and 1440 (and by the reviewer also
at 730, 800 and 900, and on a member, a committee and the no-bill page):
- every pane is level with its button: 0px off at every desktop width;
- each is fully on screen, with no sideways scroll;
- none covers its own button;
- Escape shuts the pane and puts the keyboard back on its button, and a
  click outside shuts it;
- at 720px panes still open below, and at 721px they open to the left.

**Shots** (`*-before.png`, `*-after.png`): HB 1123 with Testify and with
Cite open, and the House's 21 May 2026 with Cite and Report open, at 1280
and 390, light and dark.

## 2. Testify's closed wording

| | Before | After |
|---|---|---|
| Pane | "Online testimony for this bill has passed: its public hearing was Jan 13, 2026." | "Online testimony submissions for this bill have closed as of January 13, 2026." (the last past hearing's day, the month in full) |
| Where it can open again | "It opens again if the bill is scheduled for a hearing in the other chamber." | "They may open again if the bill goes to the Senate and the Senate holds its own public hearing." ("the House" for a Senate bill) |
| Button, for a screen reader | "Testify, not open: its hearing has passed" | "Testify, closed" |

The re-open line keeps its condition exactly: a bill still moving, heard by
one chamber, with the other ahead. So a dead bill like HB 1123 gets no
re-open line. The states "not opened yet" and "did not open" are unchanged.

**The re-open line on real data.** No 2025-2026 bill can show it today. The
session is over, and every bill's index row now says it ended (`kind` is
"done"), so none is "still moving". The `hb1048-moving-*` shots show HB 1048
of 2026 as it stood on 1 March 2026: heard by the House on 28 January,
passed by the House, with no Senate hearing yet. **They are simulated:** the
browser's clock is set to that day and the bill's one index row reads
"active". Nothing else of the page or its record is changed.

## Checks

- preflight `--code`: 0 failed.
- Every expectation that quoted the old line holds the new one.
- A new check, `_panes_open_left`, holds the desktop rule, the phone rule
  untouched, and the rule's place in the cascade.

## For the owner

The re-open line also shows while the bill is **already** in the other
chamber, unheard there (the rail's `h`), or tabled there (`t`). For a House
bill now sitting in the Senate, "if the bill goes to the Senate" reads a
little off, since it has gone. The condition is unchanged, as asked; the
words for that case are the owner's to choose.
