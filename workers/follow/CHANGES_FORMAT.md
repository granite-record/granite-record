# The changes files: what the sender reads from the site

The email sender (`sender.js`) never reads the record itself. Each night the
build publishes, beside the feeds, a small set of files under `/changes/`
saying what is new for every followable record, and the sender reads only
those. This file is the contract between the two: the build writes exactly
this, and `changes.js` refuses anything else. `tests/follow/check_changes.js`
checks a folder of them against `changes.js`, so the build can be held to
this contract by the same code the sender runs.

The files are public data -- the same facts and the same guids as the RSS
feeds -- and hold nothing about any reader.

There are two kinds of file:

| Path | What | Written |
|---|---|---|
| `/changes/current.json` | what can be followed tonight, what each is called, and what is scheduled | every build, replaced whole |
| `/changes/<YYYY-MM-DD>.json` | what was new on one night, by record | every build; the last eight nights at least are kept |

A night with nothing new still gets its file, with an empty `refs`. A missing
file means the night did not publish, and the sender treats it that way: it
waits, and says so in its log, rather than reading a missing night as a quiet
one.

## Names: a followable record's key

Every record is named `<kind>:<ref>`, with the same ref its page and feed use:

| Kind | Ref | Example key |
|---|---|---|
| `bill` | filing year, `/`, the bill id in capitals | `bill:2026/HB1442` |
| `member` | the member's numeric id | `member:736` |
| `committee` | the committee code, as its page is keyed | `committee:H05` |
| `topic` | the topic's slug, as its feed is named | `topic:housing` |

`common.js` holds the four patterns (`refOk`). A key that does not match is
dropped by the sender and refused at sign-up.

## `current.json`

```json
{
  "format": 1,
  "date": "2026-10-10",
  "built": "2026-10-10T09:06:12Z",
  "sitting_term": "2025-2026",
  "new_by": "first-seen",
  "followable": {
    "bill:2026/HB1442":  {"label": "HB 1442", "title": "relative to ...", "url": "/bill/2026/hb1442"},
    "member:736":        {"label": "Rep. A. Example (Merrimack 12)", "url": "/legislator/a-example-merrimack-12"},
    "committee:H05":     {"label": "House Education", "url": "/committee/H05"},
    "topic:housing":     {"label": "Housing", "url": "/bills?topic=Housing"}
  },
  "upcoming": {
    "bill:2026/HB1442": [
      {"date": "2026-10-14", "time": "10:00", "what": "public hearing",
       "committee": "House Education", "venue": "LOB 205"}
    ]
  }
}
```

- `format` is `1`. A file of any other format is refused whole.
- `date` is the night's date (below), and `built` the moment the build that
  wrote the file finished, in UTC, as `YYYY-MM-DDTHH:MM:SSZ`.
- `sitting_term` is the term whose bills can be followed, `YYYY-YYYY`.
- `new_by` says how this build decided what is new: `first-seen` or
  `record-date` (below). The sender reads both; it is there so a log or a
  person can tell which one produced a night.
- `followable` lists every record a reader may follow tonight, and only those:
  - **bills** of the sitting term that are still moving, or referred for
    interim study -- `shell.still_moving`, the test the bill feeds use;
  - **members** that `shell.member_followable` passes;
  - **committees** that `shell.committee_followable` passes;
  - **topics** of the sitting term only. A topic is listed only if a bill of
    the sitting term carries it, and its items (below) are the sitting term's
    alone.

  Each entry has a `label` (at most 120 characters, plain text: what the
  record is called in an email and on the manage page), an optional `title`
  (at most 300, plain text), and an optional `url`, a path on the site
  beginning with one `/`, with any query already percent-encoded (a topic's
  is the bill search narrowed to it, `/bills?topic=Banking%20and%20Finance`).
  Sign-up refuses a key that is not here, and the manage page names each
  followed record by its label.
- `upcoming` holds, for any key, the proceedings scheduled from `date` onward
  as the build knows them -- the hearings feed's rows, filed under each bill
  and under the committee that will sit. Each has `date` (`YYYY-MM-DD`) and
  `what` (`public hearing`, `executive session`, `work session`, or the
  record's own words), and may have `time` (`HH:MM`, 24-hour, New Hampshire
  time), `committee` and `venue`, each plain text of at most 120 characters.
  The weekly email lists these; it is state, not news, so it lives here and
  not in a night.

## `<YYYY-MM-DD>.json`: one night

```json
{
  "format": 1,
  "date": "2026-10-08",
  "built": "2026-10-08T09:02:40Z",
  "sitting_term": "2025-2026",
  "new_by": "first-seen",
  "refs": {
    "bill:2026/HB1442": {
      "items": [
        {"guid": "2025-2026:HB1442:2026-10-07:executive-session-10-07-2026-10-00-am-lob-205",
         "date": "2026-10-07", "kind": "exec",
         "summary": "HB 1442 -- Executive Session: 10/07/2026 10:00 am LOB 205",
         "url": "/bill/2026/hb1442", "term": "2025-2026",
         "seen": "2026-10-08T09:02:40Z"}
      ],
      "study": {"recommends": true,
                "summary": "The interim study committee recommended future legislation.",
                "date": "2026-10-07", "guid": "2025-2026:HB1442:study-report",
                "seen": "2026-10-08T09:02:40Z"},
      "ended": {"how": "law", "summary": "HB 1442 was signed into law.",
                "date": "2026-10-07", "guid": "2025-2026:HB1442:closed:law"}
    }
  }
}
```

### Which night a file is

The file's `date` is its name, and is the date `build_date` gives the build:
the UTC date of the night's run. The nightly starts at 08:17 UTC, which is
the small hours of the same calendar day in New Hampshire in both summer and
winter, so the file named for a day is that morning's news. The daily email
at about 8:00 New Hampshire time reads the file named for that day.

A build run again on the same date (by hand, after a failure) rewrites that
date's file. Under `first-seen`, an item it adds carries a later `seen` than
the email already sent, and goes out in the next one; see "What new means".

### `refs`

Keyed by record key. A record appears only if something is new for it this
night. Each value may have:

- `items`: what is new, in the order the build gives them (the sender sorts
  by `date`, newest first). Each item has:
  - `guid` -- the item's id, at most 300 characters, **the same guid the
    record's feed gives the same item** where it has one. An item appears in
    at most one night of any eight-night window, and the sender also drops a
    guid it has already put in the same email.
  - `date` -- the record's own date for what happened, `YYYY-MM-DD`.
  - `kind` -- one of `action` (a docket entry), `hearing` (a hearing held),
    `scheduled` (a proceeding newly scheduled), `exec` (an executive
    session), `vote` (a roll call, or a member's ballot in one), `report` (a
    committee report), `sponsor` (a member named on a bill), `sitting` (a
    committee's day), `study` (a step of an interim study). The weekly email
    counts `vote` and `exec` for each bill; an unknown kind is read as
    `action`, so the list can grow without breaking an older sender.
  - `summary` -- one line of plain text, at most 300 characters: the feed
    item's title. No HTML; the sender escapes it.
  - `url` -- optional, a path on the site beginning with one `/`.
  - `term` -- the term the item belongs to, `YYYY-YYYY`. Required on a topic's
    items: the sender sends a topic follower only items of `sitting_term`.
  - `seen` -- the `built` of the build that first published the item.
    Required under `first-seen`; absent under `record-date`.
- `study` (bills referred for interim study): the study committee's report,
  once it exists. `recommends` is `true` (recommended future legislation),
  `false` (did not) or `null` (the report does not say). `summary`, `date`,
  `guid` and, under `first-seen`, `seen`, as for an item.
- `ended`: the record has finished. For a bill, the night it concludes --
  signed, vetoed and settled, killed, died, or its term ended -- with `how`
  (the index's own word: `law`, `veto`, `done`, `adopted`, `dead`,
  `withdrawn`, `term-ended`, or another word of the record's), a one-line
  `summary` of how it ended, `date` and `guid`, the closing item's guid in
  the bill's feed (`<term>:<id>:closed:<kind>`). The sender sends it once and
  then **ends every follow of that record**. A member, committee or topic
  may carry one too (a member who no longer sits); the sender treats it the
  same way.

  A bill key that `current.json` listed the night before and does not list
  tonight must carry an `ended` tonight. The sender has a fallback for one
  that does not -- it tells the follower the bill is no longer moving and ends
  the follow -- but the record's own words are better than its fallback.

## What "new" means: two ways, one format

The build may decide "new" either way, and this format serves both:

- **`first-seen`.** A ledger carried between nights holds each guid with the
  build that first published it. A night's file holds the items first seen
  that night, each with `seen`. Late arrivals -- a docket row entered days
  after the day it records -- go out the next morning, dated by the record
  but filed under the night they appeared.
- **`record-date`.** No ledger: a night's file holds the items whose record
  `date` is that night's date (or the day before it, for a build that runs
  after midnight), and no item carries `seen`. Simpler, and an item that
  arrives late lands in a night already sent, so a daily reader never hears
  of it.

The sender keeps, for each subscriber, the `date` and `built` of the newest
night it has sent them (its cursor), and on the next send reads:

- every night whose `date` is after the cursor's, in full;
- the cursor's own night again, only if it has been rebuilt since (`built`
  is later), and then only its items whose `seen` is later than the cursor's
  `built`. Under `record-date` nothing carries `seen`, so a rebuilt night
  adds nothing, which is that method's known gap.

It reads at most the last eight nights, which is why the build keeps eight:
a weekly email reads seven, and the eighth covers a Saturday whose build ran
late.

## Size and limits

The sender drops, and counts in its log, any item or entry that breaks the
rules above, and refuses a file whose `format`, `date` or `refs` is wrong.
It sends at most 20 items for one record and 200 in one email, saying how
many more there are. The files carry no HTML and nothing about readers.

## Fixtures

`tests/follow/fixtures/changes/` holds one week of nights (5-10 October 2026)
and a `current.json`. **Every record in them is invented**: HB 9901-9903,
member 990001 and committee H90 do not exist, and the summaries are written
in the shape of real feed items, not copied from any. The tests run the
sender against them, and `check_changes.js` holds them to this contract.
