# Described patches for the release session

Changes the live layer needs in files the release session owns. They are
described here, not applied: the release session applies them after the
release, on the manager's word. Each one names the file, the place and the
text.

## 1. build_all.py: the Live Now step

Right after the step "a page for every week of the General Court":

    Step("Live Now: /live and its schedule, from the Calendar's own cards",
         ["build_live.py", "--site", "site", "--base", a.base],
         needs=["site/calendar.html", "proceedings.csv"],
         produces=["site/live.html", "site/live/schedule.json", "site/live.js", "site/live.css"],
         note="today's meetings and the next four weekdays', each with the Calendar's card; live.js adds what is streaming")

It asks no network and takes about as long as one calendar week. It touches
the nightly, so who applies it is the manager's call.

## 2. build_pages.home_body: the home line (design section 1.5)

Under #session (Recent Session Days), one line:

    <p class="lv-home" data-day="2027-01-07"><a href="/live">Live Now</a><span class="lv-count"> — 7 meetings today</span></p>

- The count is len(schedule.json days[today]). The night can call
  build_live.schedule(site, today), or read the file if build_live runs first.
- With 0 meetings: "Live Now" alone.
- Three lines of inline script: if data-day is not today in New Hampshire
  (Intl, America/New_York), remove .lv-count and keep the link. A missed
  night never shows yesterday's count, and a home visit makes no request.

## 3. build_indexes.py: the find.json row

If /live exists in site/:

    ["page", "Live Now", "Which House and Senate meetings are streaming now, with today's calendar.",
     S.canon("live.html"), "live stream streaming watch video hearing now today"]

## 4. The Videos tab's strip hook (section 1.6, later)

Two lines: `<div class="lv-strip" hidden>` in the Videos tab's sticky strip,
for the committee player's bar. Until it lands, the card scrolls and nothing
is sticky.

## 5. build_all.py: the session days' live step (branch 6)

The LAST step, after "bulk downloads": build_exports writes the
data/rollcalls.csv and data/votes-<term>.csv this reads, and the session
pages' step writes session/H and session/S.

    Step("Session days' live side: each sitting's session.votes file, /session/<B>/today",
         ["build_live_session.py", "--site", "site", "--base", a.base],
         needs=["site/data/manifest.json", "site/session/H", "site/session/S"],
         produces=["site/session/H/today.html", "site/session/S/today.html",
                   "site/schema/session.votes.json"],
         note="the record's roll calls of each dated session-day page in the live file's shape, "
              "checked against schema/session.votes.json; the two today pages")

- **needs.** Only artefacts other steps declare (the bulk downloads'
  manifest and the session pages' folders), so preflight's "inputs no step
  produces" check holds. live/schedule.json is not one: build_live_session
  reads it for the floor card where it is there, and does without it.
- **Network.** It asks none. It reads the two CSVs once each.
- **Files.** It writes one JSON file per dated session-day page, so the
  deploy grows by that many. Run `python3 src/checks/check_site.py` for the
  count rather than trusting a guess here.
- **Failure.** It stops the night, by name, when there are dated pages and
  no rollcalls.csv or votes CSV to read, no roll call under their dates, or
  no ballot for them.
- **Fixture chain.** If the step goes into preflight's fixture chain
  (_fixture_site_whole), the sitting-day check there already reads dated
  pages only (live/session's preflight), so today.html is not taken for a
  sitting.

## 6. build_session_pages.py: the overlay hook on each dated page (section 4.3)

In each dated session-day page (session/<B>/<date>.html) whose date is
within 14 days of the build's:

- after the day head's facts (`</dl>` of `<dl class="rfacts">`), before
  `<div class="racts">`:

      <div id="live-votes" class="lv-overlay" data-day="2027-01-07" data-body="H" hidden></div>

- in the head: `<link rel="stylesheet" href="/live.css">`;
- before `</body>`: `<script src="/live.js" defer></script>`.

live.js asks nothing for a page more than 14 days old, so an older page
needs neither. The night rebuilds every page each morning, so the window
moves with it. With no record file for the day (patch 5 not run), the
overlay draws nothing: a roll call the page already shows never appears
twice.

prune() needs no change. build_live_session removes a date's JSON when
its page is gone, and leaves the term files (2025-2026.json) alone. With
the edit, bump build_session_pages.py's GRANITE_VERSION and versions.json
together (`python3 src/ops/inventory.py --bump-changed`).

## 7. README.md, "The data": three rows (branch 7)

Add after the row for `/session/<H\|S>/<term>.json`. The first two rows can
go in once patch 5 runs on the night; the third only with
`live_docs.PUBLIC`, in the change that links Live Now.

    | `/session/<H\|S>/<date>.json` | one session day's roll calls as the night's record holds them, one file beside each dated session-day page, in the live votes file's shape (`/schema/session.votes.json`) with `"provisional": false`: each roll call's id, bill (null for a vote on no bill, its words in `bill_as_recorded`), question, tally, whether it passed and what it needed, and the members' ballots, one character each in the order of `members` |
    | `/schema/session.votes.json` | the JSON Schema both of those files and the live votes file hold to |
    | `/api/live/votes/<YYYY-MM-DD>` | beta and provisional: one sitting day's roll calls as read from the General Court's public database during the day, replaced by the night's record every morning; where the record and this both hold a roll call's id, the record's wins. CORS open, ETag and 304, kept 15 s; ask at most every 30 s. The data page's For Developers section says the rest |

## 8. watchers/README.md: the laptop's courtesy (DESIGN.md 10, default 5)

A paragraph at the end of "GitHub's night, and the laptop's fetches", before
its `---`:

    **The live Worker reads the same SQL host by day** (workers/live/README.md):
    one connection every 2 minutes while a chamber sits, and one small query a
    quarter hour on weekdays from January to June. So, as a courtesy and not a
    rule anything enforces: from January to June, no whole-table
    `fetch_*_db.py` pull on a weekday between 9 a.m. and 6 p.m. Eastern. Run
    it in the evening, or on a weekend. A pull that answers one question
    (`probe_db.py`) is not what this is about.

It is not enforced (DESIGN.md 10 names the alternative, refusal.window_check
over those hours, and why it was not chosen). watchers/README.md has no
GRANITE_VERSION; nothing to bump.

## 9. CLAUDE.md: the paragraph for the owner (DESIGN.md 6.5)

CLAUDE.md is the owner's. This is DESIGN.md 6.5's paragraph, brought up to
what was built, for the owner to place under "Static site" once approved,
with the date of approval:

    Live Now and live session votes add one more, approved by the person on
    [date]: `workers/live/`, a Worker with no address whose cron, every two
    minutes, asks YouTube's Data API which House and Senate streams are live,
    and — while a chamber sits, plus one small query every fifteen minutes on
    weekdays from January to June — asks the General Court's public SQL
    database (never gc.nh.gov) for the day's roll calls, ballots and docket
    tally lines, at most 1,200 statements a day, keeping out of the night's
    window unless a session stream is live. It writes to one private R2
    bucket, `graniterecord-live`; `control.json` there, written only by a
    person and always with `--remote`, is the switch, and stops the database
    half or the whole Worker at its next run. `functions/api/live/` reads that
    bucket and nothing else, through `_store.js`, which can only get and head.
    No page waits on them: `/live`, `/session/<B>/today` and the session pages
    are drawn by the night and say when live data was last read, never
    "nothing is live"; the night writes each sitting's record in the live
    file's shape (`build_live_session.py`, `schema/session.votes.json`), and a
    page draws the record's roll calls and only those the record lacks from
    the live file. The stream list is the page's own data and is deleted after
    30 days (YouTube's developer policy III.I.15 and III.E.4.d); the live
    votes file is public and provisional, and documented only once
    `live_docs.PUBLIC` is set.
