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
is sticky. live.js (live/committee-player) fills it: "{name} is live now" with
a Watch button, or "Playing live", only while the card is out of view.

## 11. build_committees.py and build_study_committees.py: the live hook (section 1.6)

One call each, on each committee page's finished HTML, before it is written
(live/committee-player's src/pages/live_hook.py):

    import live_hook
    LIVE_PAST = live_hook.past()          # once a run, before the loop

    html = live_hook.place(html, code=code, chamber=chamber, name=name, history=LIVE_PAST)

- build_committees.py: on the S.page(...) result for `{code}.html`, before
  S.clean_links, with the committee's code, chamber ("H"/"S") and the name
  the page uses.
- build_study_committees.py: on `html` after its results slot is filled,
  with code `ss<id>` as the page's address names it, chamber "" for a joint
  body (any chamber's stream may match), and its name.

place() puts the hook directly before `<div id="results">`, outside app.js's
root, and adds live.js and live.css. It stops (ValueError) on a page with no
results slot or with a hook already in it. Bump both files' stamps and
versions.json.

preflight's _live_committee says whether this is applied. Until it is, it
holds that this item still says how.
