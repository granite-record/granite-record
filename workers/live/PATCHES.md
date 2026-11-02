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
- **Stamps.** Bump both files' stamps and versions.json.

place() puts the hook directly before `<div id="results">`, outside app.js's
root, and adds live.js and live.css. It stops (ValueError) on a page with no
results slot or with a hook already in it.

preflight's _live_committee says whether this is applied: it looks for a
call, not a mention. Until it is applied, it holds that this item still
says how. On a built site, it holds every page's stems to /live's
schedule.json and, once applied, one hook on every committee page.
