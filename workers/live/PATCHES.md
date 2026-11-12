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

**Built on live/session (6 November 2026), by the release session's plan of
5 November.** build_pages runs before /live exists, so `home_body` leaves the
English home an empty slot, `<p class="lv-home" hidden data-day=""></p>`,
and build_live fills it from its own schedule (`link_home`) while
`build_live.LINKED` is on, the owner's switch (SWITCH_ON.md 5). preflight's
`_live_links` holds it. What follows is the line as first proposed.

Under #session (Recent Session Days), one line:

    <p class="lv-home" data-day="2027-01-07"><a href="/live">Live Now</a><span class="lv-count"> — 7 meetings today</span></p>

- The count is len(schedule.json days[today]). The night can call
  build_live.schedule(site, today), or read the file if build_live runs first.
- With 0 meetings: "Live Now" alone.
- Three lines of inline script: if data-day is not today in New Hampshire
  (Intl, America/New_York), remove .lv-count and keep the link. A missed
  night never shows yesterday's count, and a home visit makes no request.

## 3. build_indexes.py: the find.json row

**Built on live/session (6 November 2026), not in build_indexes:** /live is
not on disk when build_indexes runs, so build_live puts its own row in
through `shell.find_merge` (one row per address, however often it runs) while
`LINKED` is on, and takes it out while it is off. As first proposed:

    ["page", "Live Now", "Which House and Senate meetings are streaming now, with today's calendar.",
     S.canon("live.html"), "live stream streaming watch video hearing now today"]

## 4. The Videos tab's strip hook (section 1.6, later)

Two lines: `<div class="lv-strip" hidden>` in the Videos tab's sticky strip,
for the committee player's bar. Until it lands, the card scrolls and nothing
is sticky. live.js (live/committee-player) fills it: "{name} is live now" with
a Watch button, or "Playing live", only while the card is out of view.

## 5. build_all.py: the session days' live step (branch 6)

The LAST step, after "bulk downloads": build_exports writes the
data/rollcalls.csv and data/votes-<term>.csv this reads, and the session
pages' step writes session/H and session/S.

    Step("Session days' live side: each sitting's session.votes file, the morning page",
         ["build_live_session.py", "--site", "site", "--base", a.base],
         needs=["site/data/manifest.json", "site/session/H", "site/session/S"],
         produces=["site/schema/session.votes.json"],
         note="the record's roll calls of each dated session-day page in the live file's shape, "
              "checked against schema/session.votes.json; on a sitting's morning, its dated page")

(Revised 30 October 2026: the owner retired /session/<B>/today. The day's
page is its dated address from the morning of the sitting, so the step
produces no fixed page.)

- **Order.** After the session pages' step, whose prune() would take the
  morning page as a sitting the record does not hold, and after /live's
  step, whose live/schedule.json says the floor sits on a day with no bills
  listed yet (Organization Day).
- **needs.** Only artefacts other steps declare (the bulk downloads'
  manifest and the session pages' folders), so preflight's "inputs no step
  produces" check holds. live/schedule.json is not one: build_live_session
  reads it where it is there, and does without it.
- **Reads.** proceedings.csv's floor rows for the day's bills, as the
  Calendar does.
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
the edit, bump build_session_pages.py's GRANITE_VERSION
(`python3 src/ops/inventory.py --bump-changed`).

## 11. build_committees.py and build_study_committees.py: the live hook (section 1.6)

**For the release session** (both files are theirs). Apply after the chain
merge, on the manager's word. One call in each, on each committee page's
finished HTML, before it is written (src/pages/live_hook.py):

    import live_hook

    # once a run, in main(), before the loop:
    LIVE_PAST = live_hook.past()
    LIVE_ALL = [...]      # every committee this run writes a page for, as (chamber, name)

    html = live_hook.place(html, code=..., chamber=..., name=..., history=LIVE_PAST, others=LIVE_ALL)

- **build_committees.py.** The page is written in one expression today,
  `(out / f"{code}.html").write_text(S.clean_links(S.page(...)))`, around
  line 1347. Split it:
  - `html = S.page(...)`;
  - then `html = live_hook.place(html, code=code, chamber=chamber.strip().upper(), name=name, history=LIVE_PAST, others=LIVE_ALL)`;
  - then write `S.clean_links(html)`.

  Use code, chamber and name from the loop around line 1290. The chamber
  must be exactly "H" or "S": both the hook's stems and its chamber guard
  read it. **Skip a retired committee** (the `retired` set): it never
  streams again, and a retired code can share its name with a sitting
  committee (S33 and S50 are both Election Law and Internal Affairs), which
  would light both pages.
- **build_study_committees.py.** In write_page, around line 1000, after the
  results slot is filled: `html = live_hook.place(html, code="ss" + c["cid"], chamber="", name=c["name"], history=LIVE_PAST, others=LIVE_ALL)`.
  The chamber is "" on purpose. build_pages.meeting_key keys study rows
  with chamber "", so the stems equal /live's. Passing the body's H/S
  (CHAMBER_OF_TYPE) would add a "house ..." stem and a different name, and
  the page and /live would disagree.
- **LIVE_ALL.** Each builder may pass its own committees, as
  (chamber, name) exactly as passed to place(). It feeds live_hook.longer():
  the stems of committees whose names extend this one's, which the page
  refuses (the Senate's Education never takes Education Finance's stream).
- **Stamps.** Bump both files' stamps.

place() puts the hook directly before `<div id="results">`, outside app.js's
root, and adds live.js and live.css. It stops (ValueError) on a page with no
results slot or with a hook already in it.

preflight's _live_committee says whether this is applied: it looks for a
call, not a mention. Until it is applied, it holds that this item still
says how. On a built site, it holds every page's stems to /live's
schedule.json and, once applied, one hook on every committee page.
