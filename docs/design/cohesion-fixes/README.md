# Cohesion audit fixes, before and after (30 October 2026)

Screenshots for four fixes from the cohesion audit (design/cohesion-audit,
REPORT.md). Each fix is on its own branch. The "before" shots are dev 2273166's
built site. The "after" shots are the same site with the branch's change in
place.

| Item | Branch | Shots |
|---|---|---|
| B-3, the follow pages without a link | fix/follow-manage-page | `manage-390-light-*`, `manage-1280-dark-*`, `confirm-390-light-*` |
| B-7, a member's vote titles | fix/votes-fade | `votes-*-390`, `votes-*-1280` (Rep. Presa's Votes tab) |
| I-8, Report a problem on session days and study committees | fix/report-button | `sessionday-*`, `study-*`, and `sessionday-1280-after-open` with the box open |
| B-4, the town in the Officials tab title | fix/town-titles | no visual change on the page; the tab title is measured instead (below) |

## B-3: the follow pages without a link

Before, the manage page showed two messages: "This link is missing its private
part" and, under it, "Opening your page…", which never changed. It used fallback
fonts, and the title was 26 and 30 px.

After:
- Only the note shows, under the title.
- Public Sans and Source Serif 4 load under the page's policy, which now allows
  fonts.googleapis.com and fonts.gstatic.com and nothing else.
- The title is on the site's scale: 28 px on a phone, 34 px on desktop.
- Confirm and unsubscribe also show only the note.

## B-7: a member's vote titles

Before, a cut title kept the top of a third line, faded, 4 px above the motion's
line below it. After, the title is clamped at two lines and ends in an
ellipsis. Every cut title measures 43 px at 390 and 1280.

## I-8: Report a problem

Before, a session day and a study committee had only Cite and Share. After,
Report a problem follows Share, in the bill page's style ("Report" on a phone),
and opens the same box.

## B-4: the Officials tab title

Measured on the built officials.html:

| Address | Before | After |
|---|---|---|
| `?town=Concord` | Officials \| Granite Record | Concord — Officials \| Granite Record |
| `?town=bow` | Officials \| Granite Record | Bow — Officials \| Granite Record |
| `?q=Concord` | Officials \| Granite Record | unchanged |
| `?town=Nowhere` | Officials \| Granite Record | unchanged |
| no parameter | Officials \| Granite Record | unchanged |
