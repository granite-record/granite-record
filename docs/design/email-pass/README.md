# The email layout pass: before and after

Rendered 29 October 2026 with `tests/follow/preview_digest.js`, through the
sender's own `collect()` and `digestEmail()`. **Nothing was sent.** The code
is on branch `email/layout` (commit dd2b6d8), cut from dev. The emails
change in inboxes only once the sender is deployed again, which is the
owner's word.

The owner's note: the emails "aren't actively wrong or bad, but definitely
could use another pass at the layout and visuals to ensure the information is
easy to parse".

## What changed

| Before | After |
|---|---|
| "At a glance" repeated, word for word, the first lines of the sections under it, so each bill appeared twice | One line of counts ("12 updates on 3 bills, 1 law, 1 committee and 1 topic."), and each update told once, under its record |
| Subject: "HB 1080-FN — Interim study report: does not recommend future legislation, 11–0, and 11 more updates" | "12 updates on HB 1080-FN, HB 1198-FN and 4 more", the most pressing record first; the top news moves to the preheader, the grey line an inbox shows after the subject |
| Under a bill's own heading, every line began with its number again | A line under its own record starts with what happened; a law's or a topic's lines still name their bill |
| A tally could break across lines ("11-" / "9", in the weekly at 390px) | Each tally is held on one line |
| "Now" said the record's words ("In committee") | The site's card chip word ("In Committee", "Passed House", "To the Governor") |
| A legislator's roll calls were laid out differently from every other entry | The same rows: the date in its column, the bill and the ballot beside it |
| An ending came last in its record's section | It leads, and in each group the most pressing record comes first |

These stay as they were:

- **The urgent subject:** a hearing today or tomorrow that a reader can
  testify at still leads it ("Public hearing today on HB 9903-FN: testify
  online, and 8 updates").
- **A single update:** it is still its own subject.
- **Welcome and confirmation emails:** unchanged, because they already read
  clearly.

## The renders

In `shots/`, each at 390px (a phone) and 1280px (desktop), as a mail client
draws them, under a grey strip that gives the subject.

| Name | What it is |
|---|---|
| `*-daily-real-*` | The preview's real nights (3 nights, 2 follows) |
| `*-daily-real-6-*` | The preview's real nights (5 nights, 6 follows), the busiest sample |
| `*-weekly-real-*` | The preview's real week |
| `*-daily-testify-*` | The test fixtures, with a hearing set on HB 9903-FN and online testimony open: the testimony block, the button and the three values to choose |
| `*-weekly-testify-*` | The same in the weekly, beside the hearing under "Coming up" |
| `*-welcome-*`, `*-confirm-*` | The two emails a sign-up sends |

`renders/` holds the plain-text part of each, subject first, before and
after.

## Dark mode

The email sets its own white ground and dark ink, so a mail client that
leaves colours alone (Apple Mail, Gmail on the web) shows it as in these
renders. The `*-390-dark.png` shots show that: identical to light. Gmail's
apps on Android and iOS may recolour an email in their own dark mode, and a
headless browser cannot reproduce that. A test on a phone is the only check
for it.
