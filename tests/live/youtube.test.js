// workers/live/youtube.js, through the Worker's own run(): what it asks
// YouTube, how it reads each answer, what it writes, what it spends, and how
// it says a failure. YouTube is a function answering synthetic answers in the
// documented shape (fake_youtube.js); nothing here was recorded from it.
// preflight runs this suite (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { CHANNELS } from "../../workers/live/live.gen.js";
import { FAILS_TO_TELL, MISSES_TO_DROP, PAGE, forget, look, sessionOf, statusOf, stem } from "../../workers/live/youtube.js";
import { nh } from "../../workers/live/clock.js";
import { ITEMS, KEY } from "./fake_youtube.js";
import { DAY, HC, HOUR, MIN, T, iso, world } from "./world.js";

const UU = c => "UU" + CHANNELS[c].slice(2);

// Old uploads enough to fill both playlists' newest 50 many times over.
function fillers(w, { from = "2026-12-21T12:00:00Z", n = 60, every = 6 * HOUR } = {}) {
  for (const c of ["H", "S"]) {
    for (let i = 0; i < n; i++) {
      w.yt.add({ id: `${c}old${String(i).padStart(7, "0")}`, chamber: c, upload: true,
                 title: `${c === "H" ? "House" : "Senate"} recording ${i}`, listedAt: T(from) + i * every });
    }
  }
}

// What the day's file said of each stream, run by run: {video: [[t, status], ...]}.
function watch(w) {
  const seen = {};
  return {
    seen,
    each: async (_out, t) => {
      const f = w.streams(nh(t).date);
      for (const s of (f && f.streams) || []) {
        const h = (seen[s.video] = seen[s.video] || []);
        if (!h.length || h.at(-1)[1] !== s.status) h.push([t, s.status]);
      }
    },
    first: (id, status) => ((seen[id] || []).find(([, s]) => s === status) || [])[0],
  };
}

test("statusOf reads every synthetic answer as youtube_items.json says, the same file the Python is held to", () => {
  assert.ok(ITEMS.items.length >= 10);
  for (const c of ITEMS.items) assert.equal(statusOf(c.item), c.js, c.name);
  const kinds = new Set(ITEMS.items.map(c => c.js));
  for (const k of ["live", "upcoming", "ended", "never", "upload"]) assert.ok(kinds.has(k), k);
});

test("a title's stem drops its date and what follows; a session stream is House Session or Senate Session alone", () => {
  assert.equal(stem("Committee of Conference on SB 534  (05/22/2026"), "committee of conference on sb 534");
  assert.equal(stem("House Election Law (03/07/2025) (Full Stream)"), "house election law");
  assert.equal(stem("Ways and Means - Revenue Estimates (5/27/20 - morning session)"), "ways and means revenue estimates");
  assert.equal(stem("Executive Departments & Administration (01/24/23)"), "executive departments and administration");
  for (const [title, chamber] of [["House Session (08/19/2026)", "H"], ["Senate Session (12/04/24)", "S"],
                                  ["House Session 03/16/2022 (Entire Session)", "H"],
                                  ["Full Committee Work Session (03/02/2026)", null],
                                  ["Judiciary : Work and Executive Sessions (9/1/20)", null],
                                  ["Senate Finance (01/07/2027)", null]]) {
    assert.equal(sessionOf(title), chamber, title);
  }
});

test("each call is asked as the design says: the newest 50 of each uploads playlist, videos 50 ids at a time, live search by channel", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });       // Thursday 10:00 EST
  fillers(w, { n: 80, from: "2026-11-01T12:00:00Z" });
  await w.runAt();
  const by = m => w.yt.calls.filter(c => c.method === m);
  assert.equal(by("channels").length, 1, "the uploads playlists are confirmed once");
  assert.deepEqual(by("channels")[0].params, { part: "contentDetails", id: `${CHANNELS.H},${CHANNELS.S}` });
  assert.deepEqual(by("playlistItems").map(c => c.params),
                   ["H", "S"].map(c => ({ part: "contentDetails", playlistId: UU(c), maxResults: "50" })));
  const videos = by("videos");
  assert.equal(videos.length, 2, "100 new ids ask in two calls");
  for (const v of videos) {
    assert.deepEqual(Object.keys(v.params).sort(), ["id", "part"], "no maxResults beside id");
    assert.equal(v.params.part, "snippet,liveStreamingDetails,status");
    assert.ok(v.params.id.split(",").length <= PAGE);
  }
  assert.deepEqual(by("search").map(c => c.params),
                   ["H", "S"].map(c => ({ part: "snippet", channelId: CHANNELS[c], eventType: "live",
                                          type: "video", maxResults: "50" })));
  assert.ok(w.yt.calls.every(c => c.keyed), "every call carries the key");
  w.yt.calls.length = 0;
  await w.runAt(T("2027-01-07T15:02:00Z"));
  assert.equal(by("channels").length, 0, "and not again");
  assert.equal(by("videos").length, 0, "nothing new, live or due: no videos.list");
  assert.equal(by("playlistItems").length, 2);
});

test("a day of streams: live, upcoming, ended, unscheduled and cancelled, each in the file as it is", async () => {
  const w = world({ start: "2026-12-20T17:02:00Z" });       // a Sunday, weeks before
  const A = w.yt.add({ id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)",
                       scheduled: T("2027-01-07T14:00:00Z"), listedAt: T("2026-12-20T17:00:00Z"),
                       start: T("2027-01-07T14:01:00Z"), end: T("2027-01-07T16:30:00Z") });
  fillers(w);                                                // 60 newer uploads push A out of the 50
  const F = w.yt.add({ id: "houseSessio", chamber: "H", title: "House Session (01/07/2027)",
                       scheduled: T("2027-01-07T14:00:00Z"), listedAt: T("2027-01-04T15:00:00Z"),
                       start: T("2027-01-07T13:58:00Z"), end: T("2027-01-08T02:12:00Z") });
  const B = w.yt.add({ id: "senJudUnsch", chamber: "S", title: "Senate Judiciary (01/07/2027)",
                       start: T("2027-01-07T15:15:00Z"), end: T("2027-01-07T17:40:00Z"),
                       listedAt: T("2027-01-07T17:40:00Z"), searchLag: 4 * MIN });
  const E = w.yt.add({ id: "houseWaysMe", chamber: "H", title: "House Ways and Means (01/07/2027)",
                       start: T("2027-01-07T18:05:00Z"), end: T("2027-01-07T19:50:00Z") });
  const D = w.yt.add({ id: "houseCommer", chamber: "H", title: "House Commerce and Consumer Affairs (01/07/2027)",
                       scheduled: T("2027-01-07T20:00:00Z"), listedAt: T("2027-01-05T15:00:00Z"),
                       cancelledAt: T("2027-01-07T17:00:00Z") });
  const G = w.yt.add({ id: "fiscalNextW", chamber: "H", title: "Fiscal Committee (01/15/2027)",
                       scheduled: T("2027-01-15T15:00:00Z"), listedAt: T("2027-01-06T16:00:00Z") });
  w.yt.add({ id: "domeUpload1", chamber: "H", upload: true, title: "The State House Dome",
             listedAt: T("2027-01-07T13:00:00Z") });

  await w.runAt();                                           // it sees A while A is in the 50
  assert.deepEqual(Object.keys(w.state().yt.upcoming), [A.id], "A is kept, scheduled weeks ahead");
  await w.runAt(T("2026-12-28T17:00:00Z"));                  // a Monday: the day's refresh asks A again
  assert.equal(w.state().yt.upcoming[A.id].seen, "2026-12-28T17:00:00Z");
  assert.ok(!w.yt.playlist("H", T("2027-01-07T05:00:00Z"), 50).some(v => v.id === A.id),
            "by the day, A is out of the newest 50");

  const v = watch(w);
  await w.every("2027-01-07T05:00:00Z", "2027-01-08T06:00:00Z", v.each);
  const at = s => T(`2027-01-07T${s}:00Z`);

  // Before the window: what is scheduled today, and nothing else.
  assert.equal(v.first(A.id, "upcoming"), at("05:00"));
  assert.equal(v.first(F.id, "upcoming"), at("05:00"));
  assert.equal(v.first(D.id, "upcoming"), at("05:00"));
  assert.equal(v.seen[G.id], undefined, "next week's hearing is kept, not listed today");
  assert.equal(w.state().yt.upcoming[G.id].at, "2027-01-15T15:00:00Z");
  assert.equal(v.seen.domeUpload1, undefined, "an ordinary upload is no stream");
  // Pre-scheduled: live at the run it starts in, or the next.
  assert.equal(v.first(F.id, "live"), at("13:58"));
  assert.ok(v.first(A.id, "live") - A.start <= 2 * MIN, "A, found by its kept id though out of the 50");
  // Unscheduled and not in the playlist while live: search finds it.
  assert.equal(v.first(B.id, "live"), at("15:30"), "the next search after YouTube indexes it");
  assert.ok(v.first(B.id, "live") - B.start <= 30 * MIN + B.searchLag + 2 * MIN);
  // Unscheduled and in the playlist while live: the next run.
  assert.ok(v.first(E.id, "live") - E.start <= 2 * MIN);
  // Ended, at the next look, and kept for "Earlier today".
  assert.equal(v.first(A.id, "ended"), at("16:30"));
  assert.ok(v.first(B.id, "ended") - B.end <= 2 * MIN);
  assert.ok(v.first(F.id, "ended") - F.end <= 10 * MIN, "past 20:00, the session is followed every 10 minutes");
  // Cancelled: gone from the file at the next look.
  const late = w.streams("2027-01-07");
  assert.ok(!late.streams.some(s => s.video === D.id), "a cancelled stream is not left scheduled");
  assert.deepEqual(late.streams.map(s => [s.video, s.status]).sort(),
                   [[A.id, "ended"], [B.id, "ended"], [E.id, "ended"], [F.id, "ended"]].sort());

  // What each path saw first: the shadow measurement.
  const by = Object.fromEntries(late.streams.map(s => [s.video, s]));
  assert.equal(by[A.id].seen.playlist, "2027-01-07T16:30:00Z",
               "A reached the newest 50 that day only when it ended, and YouTube moved its publish time");
  assert.equal(by[B.id].seen.search, "2027-01-07T15:30:00Z");
  assert.equal(by[B.id].seen.playlist, "2027-01-07T17:40:00Z", "B was listed only once it ended");
  assert.ok(Date.parse(by[E.id].seen.playlist) - E.start <= 2 * MIN);
  assert.ok(late.streams.every(s => !("session" in s)), "the design's fields only: the page reads a session from its title");
  assert.deepEqual([sessionOf(by[F.id].title), sessionOf(by[B.id].title)], ["H", null]);
  assert.deepEqual([by[B.id].chamber, by[F.id].chamber], ["S", "H"]);
  assert.deepEqual([by[F.id].scheduled, by[F.id].started, by[F.id].ended],
                   ["2027-01-07T14:00:00Z", "2027-01-07T13:58:00Z", "2027-01-08T02:12:00Z"]);
  assert.equal(by[B.id].scheduled, null);
  assert.equal(by[A.id].embeddable, true);

  // The next day starts its own file, with nothing of yesterday's in it.
  const next = w.streams("2027-01-08");
  assert.ok(next && next.status.ok && next.streams.length === 0, JSON.stringify(next));
  assert.equal(w.state().yt.upcoming[G.id].at, "2027-01-15T15:00:00Z", "next week's hearing is still kept");
  // No look failed, and no file said anything but what it found.
  for (const day of ["2027-01-07", "2027-01-08"]) assert.equal(w.streams(day).status.ok, true);
  assert.equal(w.fails().length, 0);
});

test("upcoming ids are kept until their day has passed, and not past 30 calendar days unrefreshed", async () => {
  const now = new Date(T("2027-01-07T15:00:00Z"));
  const asked = [];
  const fetchImpl = async url => {
    const u = new URL(url);
    asked.push(u.pathname.split("/").pop());
    if (u.pathname.endsWith("playlistItems")) return Response.json({ items: [] });
    return Response.json({ items: [] });
  };
  const yt = { uploads: { H: UU("H"), S: UU("S") }, lists: { H: [], S: [] }, upcoming: {
    nextWeek029: { at: "2027-01-15T15:00:00Z", seen: iso(+now - 29 * DAY) },
    nextWeek030: { at: "2027-01-15T15:00:00Z", seen: iso(+now - 30 * DAY) },
    yesterday01: { at: "2027-01-06T18:00:00Z", seen: iso(+now - HOUR) },
    stillToday1: { at: "2027-01-07T23:00:00Z", seen: iso(+now - HOUR) } } };
  const due = { discover: true, live: false, search: false, refresh: false };
  let r = await look({ key: KEY, fetchImpl, now, yt, due });
  assert.deepEqual(asked.filter(m => m === "videos").length, 1, "the one due today is asked");
  assert.deepEqual(Object.keys(r.yt.upcoming).sort(), ["nextWeek029", "stillToday1"]);
  // stillToday1 is asked and never answered: kept as last seen for
  // MISSES_TO_DROP looks in a row, then dropped as deleted or made private.
  for (let i = 1; i <= MISSES_TO_DROP; i++) {
    assert.equal(r.yt.gone.stillToday1, i);
    r = await look({ key: KEY, fetchImpl, now: new Date(+now + i * 2 * MIN), yt: r.yt, due });
  }
  assert.deepEqual(Object.keys(r.yt.upcoming).sort(), ["nextWeek029"]);
  assert.equal(r.yt.gone, undefined);
});

test("a live stream videos.list leaves out is kept as last seen for three looks, said, and dropped at the fourth", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  const V = { id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)", scheduled: T("2027-01-07T14:00:00Z"),
              listedAt: T("2027-01-05T14:00:00Z"), start: T("2027-01-07T14:00:00Z"), end: T("2027-01-07T18:00:00Z") };
  w.yt.add(V);
  await w.runAt();
  const before = w.streams("2027-01-07").streams;
  assert.deepEqual(before.map(s => [s.video, s.status]), [[V.id, "live"]]);
  // YouTube stops answering for it, while it would still list it.
  const exists = w.yt.exists.bind(w.yt);
  w.yt.exists = (v, now) => v.id !== V.id && exists(v, now);
  assert.equal(MISSES_TO_DROP, 3);
  for (let i = 1; i <= 3; i++) {
    const out = await w.runAt(T("2027-01-07T14:00:00Z") + i * 2 * MIN);
    assert.ok(out.codes.includes("(1 known stream(s) left out by videos.list, kept as last seen)"), out.codes.join(" "));
    const f = w.streams("2027-01-07");
    assert.deepEqual(f.streams, before, `look ${i}: kept as last seen`);
    assert.deepEqual(w.state().yt.live, [V.id]);
  }
  await w.runAt(T("2027-01-07T14:00:00Z") + 4 * 2 * MIN);
  assert.deepEqual(w.streams("2027-01-07").streams, [], "dropped at the next");
  assert.deepEqual(w.state().yt.live, []);
  // One answer in between starts the count again.
  w.yt.exists = exists;
  const w2 = world({ start: "2027-01-07T14:00:00Z" });
  w2.yt.add(V);
  await w2.runAt();
  let skip = true;
  const e2 = w2.yt.exists.bind(w2.yt);
  w2.yt.exists = (v, now) => (v.id === V.id && skip ? false : e2(v, now));
  for (let i = 1; i <= 12; i++) {
    skip = i % 3 !== 0;                                     // two misses, then an answer
    await w2.runAt(T("2027-01-07T14:00:00Z") + i * 2 * MIN);
    assert.equal(w2.streams("2027-01-07").streams.length, 1, `look ${i}`);
    assert.equal((w2.state().yt.gone || {})[V.id], skip ? (i % 3) : undefined, `look ${i}: the count`);
  }
  assert.equal(w2.fails().length, 0);
});

// A heavy week, built as the record's busiest weeks run: up to 22 recordings a
// weekday and 16 live at once (streams.md's measured peaks), House hearings
// scheduled days ahead, Senate committees nobody scheduled and the playlist
// carries only once they end, a session to 23:59, cancellations, and next
// week's hearings kept as upcoming ids.
function heavyWeek(w) {
  fillers(w, { from: "2026-12-01T12:00:00Z", n: 60, every: 8 * HOUR });
  const all = [];
  for (let d = 11; d <= 15; d++) {
    const day = `2027-01-${d}`;
    const est = (h, m = 0) => T(`${day}T00:00:00Z`) + (h + 5) * HOUR + m * MIN;
    for (let i = 0; i < 14; i++) {
      const start = est(9, (i % 8) * 10);
      all.push(w.yt.add({ id: `h${d}c${String(i).padStart(7, "0")}`, chamber: "H",
                          title: `House Committee ${i} (01/${d}/2027)`, scheduled: start,
                          listedAt: start - 3 * DAY, start: start + 60_000,
                          end: start + (90 + ((i * 17) % 150)) * MIN }));
    }
    for (let i = 0; i < 5; i++) {
      const start = est(9, 30 + i * 45);
      all.push(w.yt.add({ id: `s${d}c${String(i).padStart(7, "0")}`, chamber: "S",
                          title: `Senate Committee ${i} (01/${d}/2027)`, start, end: start + 100 * MIN,
                          listedAt: start + 100 * MIN, searchLag: 3 * MIN }));
    }
    for (let i = 0; i < 2; i++) {
      w.yt.add({ id: `x${d}c${String(i).padStart(7, "0")}`, chamber: "H", title: `House Cancelled ${i} (01/${d}/2027)`,
                 scheduled: est(15 + i), listedAt: est(15 + i) - 4 * DAY, cancelledAt: est(12) });
    }
    for (let i = 0; i < 4; i++) {
      w.yt.add({ id: `n${d}c${String(i).padStart(7, "0")}`, chamber: "H", title: `House Next ${i} (01/${d + 7}/2027)`,
                 scheduled: est(10 + i) + 7 * DAY, listedAt: est(10) });
    }
    if (d === 13) {
      all.push(w.yt.add({ id: "hSession013", chamber: "H", title: "House Session (01/13/2027)",
                          scheduled: est(9), listedAt: est(9) - 5 * DAY, start: est(8, 58), end: est(23, 59) }));
    }
    if (d === 14) {
      all.push(w.yt.add({ id: "sSession014", chamber: "S", title: "Senate Session (01/14/27)",
                          start: est(10), end: est(16, 30), searchLag: 3 * MIN }));
    }
  }
  return all;
}

test("a heavy week's quota: each weekday at most 1,300 units and 52 searches, a weekend day about 150 units, and the Worker counts what YouTube counts", async () => {
  const from = T("2027-01-10T08:00:00Z"), to = T("2027-01-18T08:00:00Z");   // Sunday to Monday, 03:00 EST
  const w = world({ start: from });
  const streams = heavyWeek(w);
  let peak = 0;
  const v = watch(w);
  const counted = {};
  await w.every(from, to, async (out, t) => {
    await v.each(out, t);
    const s = w.state();
    counted[s.day] = s.count;
    peak = Math.max(peak, streams.filter(x => x.start <= t && t < x.end).length);
  });
  assert.ok(peak >= 16, `${peak} live at once`);
  // Per Pacific day, since the quota resets at midnight Pacific (08:00 UTC in January).
  const days = [];
  for (let t = from; t < to; t += DAY) days.push({ day: iso(t).slice(0, 10), ...w.yt.spent(t, t + DAY) });
  const weekdays = days.filter(d => !["Sat", "Sun"].includes(nh(T(d.day) + 12 * HOUR).weekday));
  assert.equal(weekdays.length, 5);
  for (const d of weekdays) {
    assert.ok(d.units <= 1300, `${d.day}: ${d.units} units`);
    assert.equal(d.searches, 52, `${d.day}: ${d.searches} searches`);
  }
  for (const d of days.filter(x => !weekdays.includes(x))) {
    assert.ok(d.units <= 160 && d.searches === 0, `${d.day}: ${d.units} units, ${d.searches} searches`);
  }
  // The Worker's own count, by New Hampshire day, is YouTube's.
  for (let d = 11; d <= 17; d++) {
    const day = `2027-01-${d}`;
    const start = T(`${day}T05:00:00Z`);
    assert.deepEqual({ units: counted[day].units, searches: counted[day].searches }, w.yt.spent(start, start + DAY), day);
  }
  // And every stream that started in the window was seen live in time.
  for (const s of streams) {
    if (!(nh(s.start).hour >= 7 && nh(s.start).hour < 20)) continue;
    const seen = v.first(s.id, "live");
    const bound = s.listedAt <= s.start ? 2 * MIN : 30 * MIN + s.searchLag + 2 * MIN;
    assert.ok(seen !== undefined && seen - s.start <= bound, `${s.id}: ${seen === undefined ? "never" : (seen - s.start) / MIN} min`);
  }
  console.log(`# quota by Pacific day: ${days.map(d => `${d.day} ${d.units}u/${d.searches}s`).join(", ")}`);
});

test("quotaExceeded holds the YouTube half to midnight Pacific, says so in the file, and tells Healthchecks once", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add({ id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)", scheduled: T("2027-01-07T14:00:00Z"),
             listedAt: T("2027-01-05T14:00:00Z"), start: T("2027-01-07T14:00:00Z"), end: T("2027-01-07T18:00:00Z") });
  await w.runAt();
  w.yt.fail("playlistItems", "quota");
  const out = await w.runAt(T("2027-01-07T14:02:00Z"));
  assert.ok(out.codes.includes("youtube_problem_quota"), out.codes.join(" "));
  const f = w.streams("2027-01-07");
  assert.deepEqual(f.status, { ok: false, problem: "quota", since: "2027-01-07T14:02:00Z" });
  assert.equal(f.checked, "2027-01-07T14:00:00Z", "the time of the last look that worked");
  assert.deepEqual(f.streams.map(s => [s.video, s.status]), [["houseFinanc", "live"]], "what it found then, kept");
  assert.equal(f.next_check, "2027-01-08T08:00:00Z", "midnight Pacific");
  assert.equal(w.state().yt.held.until, "2027-01-08T08:00:00Z");
  assert.equal(w.fails().length, 1);
  assert.match(w.fails()[0].body, /quota/);
  const calls = w.yt.calls.length, puts = w.r2.puts().length;
  await w.every("2027-01-07T14:04:00Z", "2027-01-08T08:00:00Z");
  assert.equal(w.yt.calls.length, calls, "nothing asked during the hold");
  assert.deepEqual(w.r2.puts().slice(puts).filter(k => k.startsWith("streams/")), [], "and nothing written over what it said");
  assert.equal(w.fails().length, 1, "Healthchecks heard it once");
  assert.ok(w.pings.at(-1).body.includes("youtube_held_quota"));
  await w.runAt(T("2027-01-08T08:00:00Z"));
  assert.ok(w.yt.calls.length > calls, "asked again at midnight Pacific");
  assert.equal(w.streams("2027-01-08").status.ok, true);
});

test("a refused key holds it for the rest of New Hampshire's day, and so does a forbidden answer", async () => {
  for (const kind of ["key_invalid", "forbidden"]) {
    const w = world({ start: "2027-01-07T15:00:00Z" });
    w.yt.fail("*", kind);
    const out = await w.runAt();
    assert.ok(out.codes.includes("youtube_problem_key"), `${kind}: ${out.codes}`);
    assert.equal(w.state().yt.held.until, "2027-01-08T05:00:00Z", kind);
    assert.equal(w.streams("2027-01-07").status.problem, "key");
    assert.equal(w.fails().length, 1);
    const n = w.yt.calls.length;
    await w.every("2027-01-07T15:02:00Z", "2027-01-08T05:00:00Z", null, 10 * MIN);
    assert.equal(w.yt.calls.length, n, `${kind}: nothing asked until midnight`);
    await w.runAt(T("2027-01-08T05:00:00Z"));
    assert.ok(w.yt.calls.length > n, `${kind}: asked again the next day`);
  }
});

test("a refused key's hold keeps no print of the key, and lifts when the person turns YouTube off and on; no key at all is said at every run and held for nothing", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });
  w.yt.fail("*", "key_invalid");
  await w.runAt();
  assert.deepEqual(Object.keys(w.state().yt.held).sort(), ["since", "until", "why"], "nothing of the key in state.json");
  await w.runAt(T("2027-01-07T15:02:00Z"));
  const n = w.yt.calls.length;
  assert.equal(n, 1, "held");
  w.env.YOUTUBE_API_KEY = w.yt.key = "a-new-synthetic-key";
  await w.runAt(T("2027-01-07T15:04:00Z"));
  assert.equal(w.yt.calls.length, n, "a new key alone waits for the hold");
  w.r2.seed("control.json", { youtube: "off", sql: "off" });
  await w.runAt(T("2027-01-07T15:06:00Z"));
  w.r2.seed("control.json", { youtube: "on", sql: "off" });
  await w.runAt(T("2027-01-07T15:08:00Z"));
  assert.ok(w.yt.calls.length > n, "off and on again asks at once");
  assert.equal(w.streams("2027-01-07").status.ok, true);

  // With no key: nothing asked, nothing held, and every run says so -- the
  // quiet runs between looks outside the window too, so the check stays down.
  const none = world({ start: "2027-01-07T15:00:00Z", key: null });
  await none.every("2027-01-07T15:00:00Z", "2027-01-07T15:06:00Z");
  assert.equal(none.yt.calls.length, 0, "with no key, nothing is asked");
  assert.equal(none.state().yt.held, undefined, "and nothing is held");
  assert.equal(none.streams("2027-01-07").status.problem, "key");
  assert.equal(none.fails().length, 3, "every look says so");
  assert.match(none.fails()[0].body, /no YOUTUBE_API_KEY secret/);
  await none.every("2027-01-08T02:00:00Z", "2027-01-08T03:00:00Z");      // 21:00 EST: a look every 30 minutes
  assert.equal(none.pings.filter(p => p.at >= T("2027-01-08T02:00:00Z")).every(p => p.url.endsWith("/fail")), true,
               "every run, looking or not");
  none.env.YOUTUBE_API_KEY = KEY;
  await none.runAt(T("2027-01-08T03:00:00Z"));
  assert.ok(none.yt.calls.length > 0, "the first run after the key is put asks");
  assert.equal(none.streams("2027-01-07").status.ok, true);
  assert.equal(none.pings.at(-1).url, HC);
});

test("five failed looks in a row tell Healthchecks, four do not, and a good look starts the count again", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });
  w.yt.fail("videos", "backend", 0);
  for (let i = 0; i < 4; i++) w.yt.fail("playlistItems", "backend");
  await w.every("2027-01-07T15:00:00Z", "2027-01-07T15:08:00Z");
  assert.equal(w.fails().length, 0, "four");
  assert.equal(w.state().yt.fails, 4);
  await w.runAt(T("2027-01-07T15:08:00Z"));                 // a good look
  assert.equal(w.state().yt.fails, 0);
  for (let i = 0; i < 5; i++) w.yt.fail("playlistItems", "backend");
  await w.every("2027-01-07T15:10:00Z", "2027-01-07T15:20:00Z");
  assert.equal(w.fails().length, 1, "the fifth");
  assert.match(w.fails()[0].body, /5 looks at YouTube in a row have failed \(playlistItems: HTTP 503 backendError\)/);
  assert.ok(w.pings.every(p => !p.body.includes(KEY)));
});

test("a failure that persists outside the window keeps Healthchecks down on every run, not only the runs that look", async () => {
  const w = world({ start: "2027-01-08T01:00:00Z" });        // 20:00 EST: a look every 30 minutes
  for (let i = 0; i < 40; i++) w.yt.fail("playlistItems", "backend");
  await w.every("2027-01-08T01:00:00Z", "2027-01-08T06:00:00Z");
  assert.ok(w.state().yt.fails >= FAILS_TO_TELL + 3, `${w.state().yt.fails} failed looks`);
  const after = w.pings.filter(p => p.at >= T("2027-01-08T01:00:00Z") + (FAILS_TO_TELL - 1) * 30 * MIN);
  assert.ok(after.length >= 60, `${after.length} runs`);
  const flips = after.slice(1).filter((p, i) => p.url !== after[i].url).length;
  assert.equal(flips, 0, "no run between the looks pings success");
  assert.ok(after.every(p => p.url.endsWith("/fail") && /looks at YouTube in a row have failed/.test(p.body)));
  w.yt.errors.length = 0;
  await w.runAt("2027-01-08T06:00:00Z");
  assert.equal(w.pings.at(-1).url, HC, "the first good look brings it up");
  await w.runAt("2027-01-08T06:02:00Z");
  assert.equal(w.pings.at(-1).url, HC, "and it stays up");
});

test("a failed look keeps what was last checked and says it failed; it is never written as a fresh look that found nothing", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add({ id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)", scheduled: T("2027-01-07T14:00:00Z"),
             listedAt: T("2027-01-05T14:00:00Z"), start: T("2027-01-07T14:00:00Z"), end: T("2027-01-07T18:00:00Z") });
  await w.runAt();
  w.yt.fail("videos", "backend", 2);
  await w.runAt(T("2027-01-07T14:02:00Z"));
  let f = w.streams("2027-01-07");
  assert.deepEqual([f.status, f.checked, f.next_check],
                   [{ ok: false, problem: "youtube", since: "2027-01-07T14:02:00Z" }, "2027-01-07T14:00:00Z",
                    "2027-01-07T14:04:00Z"]);
  assert.deepEqual(f.streams.map(s => s.status), ["live"]);
  await w.runAt(T("2027-01-07T14:04:00Z"));
  assert.equal(w.streams("2027-01-07").status.since, "2027-01-07T14:02:00Z", "since when, not since this run");
  await w.runAt(T("2027-01-07T14:06:00Z"));
  f = w.streams("2027-01-07");
  assert.deepEqual([f.status.ok, f.checked], [true, "2027-01-07T14:06:00Z"]);

  // The day's first look fails: the file says so, with no time checked and nothing listed.
  const w2 = world({ start: "2027-01-07T05:00:00Z" });
  w2.yt.fail("playlistItems", "backend");
  await w2.runAt();
  f = w2.streams("2027-01-07");
  assert.deepEqual([f.status.ok, f.status.problem, f.checked, f.streams], [false, "youtube", null, []]);
  // Over a day of failures and recoveries, no file is ever "ok" without a time it was checked.
  const w3 = world({ start: "2027-01-07T05:00:00Z" });
  for (let i = 0; i < 40; i++) w3.yt.errors.push({ method: i % 3 ? "videos" : "playlistItems", ...ITEMS.errors.backend });
  await w3.every("2027-01-07T12:00:00Z", "2027-01-07T16:00:00Z", async () => {
    const g = w3.streams("2027-01-07");
    if (g) assert.ok(!(g.status.ok && !g.checked) && (g.status.ok || g.status.problem), JSON.stringify(g.status));
  });
});

// How a reader of the file tells its state, by README.md's rule (the page is a
// later branch): failed or off as the file says; stale when now is more than
// 5 minutes past next_check; fresh otherwise.
function reading(f, now) {
  if (!f) return "no file";
  if (!f.status.ok) return f.status.problem;
  if (now > Date.parse(f.next_check) + 5 * MIN) return "stale";
  return f.streams.some(s => s.status === "live") ? "fresh, live" : "fresh, none live";
}

test("a stopped Worker, a failed look, a hold or the switch reads from the file as what it is, never as a fresh look that found nothing", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add({ id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)", scheduled: T("2027-01-07T14:00:00Z"),
             listedAt: T("2027-01-05T14:00:00Z"), start: T("2027-01-07T14:00:00Z"), end: T("2027-01-07T23:30:00Z") });
  const written = [];
  w.r2.hooks.put = async (key, value) => { if (key === "streams/2027-01-07.json") written.push([w.now, JSON.parse(value)]); };
  await w.every("2027-01-07T14:00:00Z", "2027-01-07T15:00:00Z");
  const day = () => w.streams("2027-01-07");
  assert.equal(reading(day(), T("2027-01-07T14:59:00Z")), "fresh, live");
  // The Worker stops at 14:58: by 15:06 the file says so by itself.
  assert.equal(reading(day(), T("2027-01-07T15:04:00Z")), "fresh, live");
  assert.equal(reading(day(), T("2027-01-07T15:06:00Z")), "stale");
  // A quiet evening checked every 30 minutes is not stale between looks.
  const q = world({ start: "2027-01-08T02:00:00Z" });
  await q.runAt();
  assert.equal(reading(q.streams("2027-01-07"), T("2027-01-08T02:34:00Z")), "fresh, none live");
  assert.equal(reading(q.streams("2027-01-07"), T("2027-01-08T02:36:00Z")), "stale");
  // A failed look, a hold and the switch each say themselves, at once.
  w.yt.fail("videos", "backend");
  await w.runAt("2027-01-07T15:10:00Z");
  assert.equal(reading(day(), T("2027-01-07T15:10:00Z")), "youtube");
  w.yt.fail("playlistItems", "quota");
  await w.runAt("2027-01-07T15:12:00Z");
  for (const t of ["2027-01-07T15:12:00Z", "2027-01-07T22:00:00Z", "2027-01-08T08:04:00Z"]) {
    assert.equal(reading(day(), T(t)), "quota", t);
  }
  w.r2.seed("control.json", { youtube: "off", sql: "off" });
  await w.runAt("2027-01-08T08:00:00Z");
  assert.equal(reading(w.streams("2027-01-08"), T("2027-01-08T08:00:00Z")), "off");
  // No file written while the stream was live reads as a fresh look that
  // found nothing live, at the moment it was written or any moment after.
  assert.ok(written.length >= 32, `${written.length} files written`);
  for (const [t, f] of written) {
    for (const later of [t, t + 3 * MIN, t + 30 * MIN, t + 6 * HOUR]) {
      assert.notEqual(reading(f, later), "fresh, none live", `written ${iso(t)}, read ${iso(later)}`);
    }
  }
});

test("a look YouTube never answers fails inside its deadline", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });
  w.yt.hang = "playlistItems";
  const t0 = Date.now();
  // Node does not wait on AbortSignal.timeout's timer alone; a Worker does.
  const awake = setInterval(() => {}, 1000);
  const out = await w.runAt(undefined, { timeoutMs: 50 }).finally(() => clearInterval(awake));
  assert.ok(Date.now() - t0 < 2000);
  assert.ok(out.codes.includes("youtube_problem_youtube"), out.codes.join(" "));
  assert.equal(w.streams("2027-01-07").status.problem, "youtube");
  assert.equal(w.state().yt.fails, 1);
});

test("search's own allowance running out holds search alone, to midnight Pacific", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });
  w.yt.fail("search", "quota");
  const out = await w.runAt();
  assert.ok(out.codes.some(c => c.includes("search held to midnight Pacific")), out.codes.join(" "));
  assert.equal(w.streams("2027-01-07").status.ok, true, "the playlists were read");
  assert.equal(w.state().yt.search_held, "2027-01-08T08:00:00Z");
  assert.equal(w.fails().length, 1, "the hold beginning is told");
  assert.match(w.fails()[0].body, /search's own allowance is spent/);
  await w.every("2027-01-07T15:02:00Z", "2027-01-07T17:00:00Z");
  assert.equal(w.yt.calls.filter(c => c.method === "search").length, 1, "the one that was refused");
  assert.ok(w.yt.calls.filter(c => c.method === "playlistItems").length >= 120);
  assert.equal(w.fails().length, 1, "once: the runs during the hold are not failures");
});

test("the key is never written to the bucket, a log line or Healthchecks", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add({ id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)", scheduled: T("2027-01-07T14:00:00Z"),
             listedAt: T("2027-01-05T14:00:00Z"), start: T("2027-01-07T14:00:00Z"), end: T("2027-01-07T15:00:00Z") });
  w.yt.fail("videos", "backend", 6);
  w.yt.fail("search", "quota");
  await w.every("2027-01-07T14:00:00Z", "2027-01-07T15:30:00Z");
  w.yt.fail("*", "key_invalid");
  await w.runAt(T("2027-01-07T15:30:00Z"));
  const everything = [...[...w.r2.objects.values()].map(o => o.body), ...w.logs, ...w.pings.map(p => p.body + p.url)];
  assert.ok(everything.length > 50);
  for (const text of everything) assert.ok(!text.includes(KEY), text.slice(0, 200));
  assert.ok(w.fails().length >= 2);
});

test("control.json saying youtube off: nothing is asked, and the day's file says so once", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z", control: { youtube: "off", sql: "off" } });
  const out = await w.runAt();
  assert.deepEqual(out.codes, ["youtube_off", "swept_0"]);
  assert.equal(w.yt.calls.length, 0);
  const f = w.streams("2027-01-07");
  assert.deepEqual([f.status, f.next_check], [{ ok: false, problem: "off", since: "2027-01-07T14:00:00Z" }, null]);
  assert.match(w.pings[0].body, /youtube off, sql off by control\.json, uploaded 2027-01-07 09:00 New Hampshire time/);
  const puts = w.r2.puts().length;
  await w.every("2027-01-07T14:02:00Z", "2027-01-07T16:00:00Z");
  assert.equal(w.r2.puts().length, puts, "written once");
  await w.every("2027-01-08T05:00:00Z", "2027-01-08T05:04:00Z");
  assert.equal(w.streams("2027-01-08").status.problem, "off", "and once on the next day");
  w.r2.seed("control.json", { youtube: "on", sql: "off" });
  await w.runAt(T("2027-01-08T05:30:00Z"));
  assert.ok(w.yt.calls.length > 0, "switched back on, it asks at its next run");
  assert.equal(w.streams("2027-01-08").status.ok, true);
  assert.equal(w.yt.calls.filter(c => !c.keyed).length, 0);
  assert.ok(w.pings.every(p => p.url === HC), "nothing here is a failure");
});

test("control.json saying youtube off forgets everything state.json kept of YouTube, at its first run", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add({ id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)", scheduled: T("2027-01-07T14:00:00Z"),
             listedAt: T("2027-01-05T14:00:00Z"), start: T("2027-01-07T14:00:00Z"), end: T("2027-01-07T18:00:00Z") });
  w.yt.add({ id: "fiscalNextW", chamber: "H", title: "Fiscal Committee (01/15/2027)",
             scheduled: T("2027-01-15T15:00:00Z"), listedAt: T("2027-01-06T16:00:00Z") });
  fillers(w);
  w.yt.fail("search", "quota");
  await w.every("2027-01-07T14:00:00Z", "2027-01-07T14:10:00Z");
  const yt = w.state().yt;
  assert.ok(yt.upcoming.fiscalNextW && yt.live.length && yt.lists.H.length === 50 && yt.uploads && yt.search_held);
  w.r2.seed("control.json", { youtube: "off", sql: "off" });
  await w.runAt("2027-01-07T14:10:00Z");
  assert.deepEqual(w.state().yt, { off: "2027-01-07" }, "no id, list, playlist or hold kept");
  // Off for six weeks: still nothing of YouTube's anywhere but the day files, which the sweep takes.
  await w.every("2027-01-07T14:12:00Z", "2027-02-18T14:00:00Z", null, 6 * HOUR);
  assert.deepEqual(Object.keys(w.state().yt), ["off"]);
  assert.deepEqual([...w.r2.objects.keys()].filter(k => k.startsWith("streams/")).sort()[0], "streams/2027-01-20.json", "the sweep took the rest");
  assert.equal(w.yt.calls.filter(c => c.at >= T("2027-01-07T14:10:00Z")).length, 0);
});

test("a month of failed looks keeps nothing of YouTube's in state.json past 30 calendar days", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add({ id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)", scheduled: T("2027-01-07T14:00:00Z"),
             listedAt: T("2027-01-05T14:00:00Z"), start: T("2027-01-07T14:00:00Z"), end: T("2027-03-07T18:00:00Z") });
  w.yt.add({ id: "fiscalNextW", chamber: "H", title: "Fiscal Committee (03/15/2027)",
             scheduled: T("2027-03-15T15:00:00Z"), listedAt: T("2027-01-06T16:00:00Z") });
  await w.runAt();
  assert.ok(w.state().yt.upcoming.fiscalNextW && w.state().yt.live.length && w.state().yt.lists);
  // From here every look fails, YouTube's own trouble.
  for (let i = 0; i < 2000; i++) w.yt.fail("*", "backend");
  const check = async (_o, t) => {
    const yt = w.state().yt;
    const day = nh(t).date;
    if (day >= "2027-02-06") {
      const text = JSON.stringify(yt);
      assert.ok(!/houseFinanc|fiscalNextW|UU/.test(text) && !yt.lists && !yt.uploads, `${day}: ${text}`);
    }
  };
  await w.every("2027-01-07T14:30:00Z", "2027-02-10T14:00:00Z", check, 3 * HOUR);
  assert.ok(w.state().yt.fails > 100);
  // forget() alone, on the day of the rule's edge.
  const kept = { listed: "2027-01-08T15:00:00Z", lists: { H: ["a"] }, live: ["a"], uploads: { H: "x" },
                 upcoming: { b: { at: "2027-03-01T15:00:00Z", seen: "2027-01-08T15:00:00Z" } } };
  assert.deepEqual(forget(structuredClone(kept), new Date(T("2027-02-06T15:00:00Z"))), kept, "29 days: kept");
  assert.deepEqual(forget(structuredClone(kept), new Date(T("2027-02-07T15:00:00Z"))), { upcoming: {} }, "30 days: gone");
  // A miss counted for an id no longer kept goes with it.
  const missed = { ...structuredClone(kept), gone: { b: 2, x: 1 },
                   upcoming: { b: { at: "2027-01-08T15:00:00Z", seen: "2027-01-08T15:00:00Z" } } };
  const after = forget(missed, new Date(T("2027-01-09T15:00:00Z")));
  assert.deepEqual([after.upcoming, after.gone], [{}, undefined], "its day passed");
});

test("a bare 401, with no reason given, is a refused key", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });
  w.yt.errors.push({ method: "*", status: 401, body: { error: { code: 401, message: "Unauthorized", errors: [] } } });
  const out = await w.runAt();
  assert.ok(out.codes.includes("youtube_problem_key"), out.codes.join(" "));
  assert.equal(w.state().yt.held.why, "key");
});

test("an upcoming id is asked from two hours before its start to the end of today, and not a minute either side", async () => {
  const now = new Date(T("2027-01-07T15:00:00Z"));
  const endOfToday = T("2027-01-08T05:00:00Z");
  const asked = [];
  const fetchImpl = async url => {
    const u = new URL(url);
    if (u.pathname.endsWith("videos")) asked.push(...u.searchParams.get("id").split(","));
    return Response.json({ items: [] });
  };
  const at = t => ({ at: iso(t), seen: iso(+now - HOUR) });
  const yt = { uploads: { H: UU("H"), S: UU("S") }, lists: { H: [], S: [] }, upcoming: {
    twoHoursAgo: at(+now - 2 * HOUR), justPast2h: at(+now - 2 * HOUR - MIN),
    lastMinute1: at(endOfToday - MIN), midnight001: at(endOfToday) } };
  await look({ key: KEY, fetchImpl, now, yt, due: { discover: true, live: false, search: false, refresh: false } });
  assert.deepEqual(asked.sort(), ["lastMinute1", "twoHoursAgo"]);
});

test("a cron that fires a few seconds early is on time: the look due at the next tick is made", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });
  await w.runAt();
  const n = w.yt.calls.filter(c => c.method === "playlistItems").length;
  await w.runAt(T("2027-01-07T15:02:00Z") - 5_000);
  assert.ok(w.yt.calls.filter(c => c.method === "playlistItems").length > n, "discovered at 15:01:55");
});

test("with YouTube off, a missing key is nobody's failure", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z", key: null, control: { youtube: "off", sql: "off" } });
  await w.every("2027-01-07T15:00:00Z", "2027-01-07T15:10:00Z");
  assert.equal(w.fails().length, 0);
});

test("a refused key keeps Healthchecks down for its hold, the quiet runs too, and up again once a look works", async () => {
  const w = world({ start: "2027-01-07T15:00:00Z" });
  w.yt.fail("*", "key_invalid");
  await w.every("2027-01-07T15:00:00Z", "2027-01-07T16:00:00Z");
  assert.ok(w.pings.length >= 30 && w.pings.every(p => p.url.endsWith("/fail")), w.pings.map(p => p.url).join(" "));
  assert.match(w.pings.at(-1).body, /YouTube refused the key/);
  await w.runAt("2027-01-08T05:00:00Z");
  assert.equal(w.pings.at(-1).url, HC, "the next day's good look");
});

test("an upcoming id asked only at the day's refresh, and never answered, is dropped at its fourth refresh", async () => {
  const w = world({ start: "2027-01-03T16:30:00Z" });          // a Sunday, before the fillers
  const G = w.yt.add({ id: "fiscalLater", chamber: "H", title: "Fiscal Committee (01/29/2027)",
                       scheduled: T("2027-01-29T15:00:00Z"), listedAt: T("2027-01-03T16:00:00Z") });
  fillers(w, { from: "2027-01-03T17:00:00Z", n: 60, every: MIN });  // push it out of the 50 from 18:00
  await w.runAt();
  assert.ok(w.state().yt.upcoming[G.id], "kept");
  w.yt.exists = (v, now) => v.id !== G.id && now >= Math.min(v.listedAt ?? Infinity, v.start ?? Infinity);
  const days = ["04", "05", "06", "07"];
  for (const [i, d] of days.entries()) {
    await w.every(`2027-01-${d}T12:00:00Z`, `2027-01-${d}T13:00:00Z`);
    const yt = w.state().yt;
    if (i < 3) {
      assert.ok(yt.upcoming[G.id], `refresh ${i + 1}: still kept`);
      assert.equal(yt.gone[G.id], i + 1, `refresh ${i + 1}: the misses carry between refreshes`);
    } else {
      assert.equal(yt.upcoming[G.id], undefined, "dropped at the fourth");
      assert.equal(yt.gone, undefined);
    }
  }
});

test("a run that fails after taking the lease, day after day, still leaves nothing of YouTube's past 30 days", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add({ id: "fiscalNextW", chamber: "H", title: "Fiscal Committee (03/15/2027)",
             scheduled: T("2027-03-15T15:00:00Z"), listedAt: T("2027-01-06T16:00:00Z") });
  await w.runAt();
  assert.ok(w.state().yt.upcoming.fiscalNextW);
  // From here R2 cannot list, so every run after 03:00 sweeps and stops before it releases.
  w.r2.list = async () => { throw new Error("R2 said 500"); };
  for (let i = 0; i < 2000; i++) w.yt.fail("*", "backend");
  await w.every("2027-01-08T09:00:00Z", "2027-02-10T09:00:00Z", null, 6 * HOUR);
  const text = JSON.stringify(w.state().yt);
  assert.ok(!/fiscalNextW|UU/.test(text), text);
});

