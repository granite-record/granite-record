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

After the session-day pages and after patch 1's Live Now step (it reads
live/schedule.json for the floor card):

    Step("Session days' live side: each sitting's session.votes file, /session/<B>/today",
         ["build_live_session.py", "--site", "site", "--base", a.base],
         needs=["site/session/days.json", "site/data/rollcalls.csv", "site/live/schedule.json"],
         produces=["site/session/H/today.html", "site/session/S/today.html",
                   "site/schema/session.votes.json"],
         note="the record's roll calls of each dated session-day page in the live file's shape, "
              "checked against schema/session.votes.json; the two today pages")

It asks no network. It reads the published data/rollcalls.csv and
data/votes-<term>.csv once each. It writes one JSON file per dated
session-day page, so the deploy grows by that many files; run
`python3 src/checks/check_site.py` for the count rather than trusting a
guess here.

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
its page is gone, and leaves the term files (2025-2026.json) alone.
