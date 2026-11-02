// workers/live/clock.js: New Hampshire's clock, the YouTube half's cadence,
// the holds' midnights and the night's windows, across the changes of
// 14 March and 7 November 2027. preflight runs this suite (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { EVERY, NEW_YORK, PACIFIC, STEP, inWindow, midnightAfter, nextLook, nh, nightWindow,
         youtubeDue } from "../../workers/live/clock.js";
import { NIGHT_WINDOWS } from "../../workers/live/live.gen.js";
import { plan } from "../../workers/live/index.js";
import { CONTROL_DEFAULT } from "../../workers/live/store.js";
import { MIN, T, iso, world } from "./world.js";

// The looks youtubeDue asks for over [from, to), each run updating the times
// it reads as a look updates them (youtube.js).
function looks(from, to, yt = {}) {
  const out = [];
  for (let t = T(from); t < T(to); t += STEP) {
    const d = youtubeDue(new Date(t), yt);
    if (d.discover) { yt.discovery = iso(t); yt.looked = iso(t); }
    if (d.live) yt.looked = iso(t);
    if (d.search) yt.search = iso(t);
    if (d.refresh) yt.refreshed = nh(t).date;
    if (d.any) out.push({ t, ...d, window: inWindow(new Date(t)) });
  }
  return out;
}

test("New Hampshire's clock across the changes of 14 March and 7 November 2027", () => {
  assert.deepEqual(nh(T("2027-03-14T06:59:00Z")), { date: "2027-03-14", hour: 1, minute: 59, weekday: "Sun", weekend: true });
  assert.equal(nh(T("2027-03-14T07:00:00Z")).hour, 3);           // 02:00 EST is 03:00 EDT
  assert.deepEqual(nh(T("2027-11-07T05:59:00Z")), { date: "2027-11-07", hour: 1, minute: 59, weekday: "Sun", weekend: true });
  assert.equal(nh(T("2027-11-07T06:00:00Z")).hour, 1);           // 02:00 EDT is 01:00 EST
  assert.equal(nh(T("2027-03-15T04:00:00Z")).weekend, false);    // Monday, 00:00 EDT
});

test("the window is weekdays 07:00 to 20:00 there, on either side of each change", () => {
  const cases = {
    "2027-03-12T11:58:00Z": false, "2027-03-12T12:00:00Z": true,     // Friday, EST
    "2027-03-15T10:58:00Z": false, "2027-03-15T11:00:00Z": true,     // Monday, EDT
    "2027-03-15T23:58:00Z": true, "2027-03-16T00:00:00Z": false,     // 19:58 and 20:00 EDT
    "2027-11-05T11:00:00Z": true, "2027-11-08T11:58:00Z": false,     // Friday EDT; Monday 06:58 EST
    "2027-11-08T12:00:00Z": true, "2027-11-09T01:00:00Z": false,     // Monday 07:00 and 20:00 EST
    "2027-03-13T16:00:00Z": false, "2027-11-07T16:00:00Z": false,    // a Saturday and a Sunday noon
  };
  for (const [at, want] of Object.entries(cases)) assert.equal(inWindow(new Date(T(at))), want, at);
});

test("a weekday: every run in the window, every 30 minutes outside it, search every 30 minutes in it, one refresh", () => {
  // Monday 15 March 2027, the first weekday after the spring change: 00:00 to 24:00 EDT.
  const all = looks("2027-03-15T04:00:00Z", "2027-03-16T04:00:00Z");
  const inside = all.filter(l => l.window && l.discover), outside = all.filter(l => !l.window && l.discover);
  assert.equal(inside.length, 390, "13 hours of runs every 2 minutes");
  assert.equal(inside[0].t, T("2027-03-15T11:00:00Z"), "the window opens at 07:00 EDT");
  const before = outside.filter(l => l.t < inside[0].t), after = outside.filter(l => l.t > inside.at(-1).t);
  assert.deepEqual([before.length, after.length], [14, 8], "7 hours before and 4 after, every 30 minutes");
  assert.equal(after[0].t - inside.at(-1).t, 30 * MIN, "the first look after the window is 30 minutes after its last");
  for (const part of [before, after]) {
    for (let i = 1; i < part.length; i++) assert.equal(part[i].t - part[i - 1].t, 30 * MIN, iso(part[i].t));
  }
  const searches = all.filter(l => l.search);
  assert.equal(searches.length, 26, "07:00, 07:30 ... 19:30");
  assert.ok(searches.every(l => l.window));
  assert.deepEqual(all.filter(l => l.refresh).map(l => iso(l.t)), ["2027-03-15T11:00:00Z"]);
  assert.equal(all.filter(l => l.live).length, 0, "nothing live, nothing asked after");
});

test("a weekend day of 23 hours and one of 25: discovery every 30 minutes, no gap and no double", () => {
  for (const [from, to, n] of [["2027-03-14T05:00:00Z", "2027-03-15T04:00:00Z", 46],
                               ["2027-11-07T04:00:00Z", "2027-11-08T05:00:00Z", 50]]) {
    const all = looks(from, to);
    assert.equal(all.length, n, from);
    assert.ok(all.every(l => l.discover && !l.search && !l.refresh && !l.window));
    for (let i = 1; i < all.length; i++) assert.equal(all[i].t - all[i - 1].t, 30 * MIN, iso(all[i].t));
  }
});

test("ids still live are asked after every 10 minutes outside the window, and the window's last run hands on", () => {
  // Friday 12 March 2027, 19:00 to 23:00 EST, with one stream live past 20:00.
  const yt = { live: ["sessionLive"] };
  const all = looks("2027-03-13T00:00:00Z", "2027-03-13T04:00:00Z", yt);
  const after = all.filter(l => !l.window);
  assert.ok(after.length >= 18, `${after.length} looks after 20:00`);
  let last = all.filter(l => l.window).at(-1).t;
  for (const l of after) {
    assert.ok(l.t - last <= EVERY.live && l.t - last >= EVERY.live - 2 * MIN, `${iso(l.t)}: ${(l.t - last) / MIN} min`);
    last = l.t;
  }
  assert.ok(after.filter(l => l.discover).length >= 6, "discovery goes on every 30 minutes");
});

test("nothing is due on a quiet weekend between its discoveries, and such a run writes nothing", async () => {
  const yt = { discovery: "2027-03-13T15:00:00Z", looked: "2027-03-13T15:00:00Z" };
  for (let m = 2; m < 28; m += 2) {
    const d = youtubeDue(new Date(T("2027-03-13T15:00:00Z") + m * MIN), yt);
    assert.equal(d.any, false, `${m} minutes after`);
  }
  const p = plan(new Date(T("2027-03-13T15:10:00Z")),
                 { v: 1, yt, swept: "2027-03-13", count: {} }, { ...CONTROL_DEFAULT });
  assert.deepEqual([p.youtube, p.off, p.sweep], [null, false, false]);
  const w = world({ start: "2027-03-13T15:10:00Z" });
  w.r2.seed("state.json", { v: 1, lease: null, day: "2027-03-13", count: { units: 3, searches: 0 }, yt, swept: "2027-03-13" });
  const out = await w.runAt();
  assert.deepEqual(out.codes, ["nothing_due"]);
  assert.deepEqual(w.r2.puts(), [], "a run with nothing due puts nothing");
  assert.equal(w.yt.calls.length, 0);
  assert.equal(w.pings.length, 1, "and still pings Healthchecks");
});

test("next_check is the planner's own next look", () => {
  const at = (s, yt) => iso(nextLook(new Date(T(s)), { discovery: s, looked: s, search: s, ...yt }));
  assert.equal(at("2027-03-15T15:00:00Z"), "2027-03-15T15:02:00Z", "in the window, the next run");
  assert.equal(at("2027-03-13T15:00:00Z"), "2027-03-13T15:30:00Z", "a Saturday: 30 minutes");
  assert.equal(at("2027-03-13T15:00:00Z", { live: ["x"] }), "2027-03-13T15:10:00Z", "with a stream live: 10");
  // Friday 19:58 EST: the window's last run; the next look is 20:28, not Monday.
  assert.equal(at("2027-03-13T00:58:00Z"), "2027-03-13T01:28:00Z");
  // 06:40 EDT on a Monday, last discovery at 06:30: the window opens at 07:00.
  assert.equal(iso(nextLook(new Date(T("2027-03-15T10:40:00Z")),
                            { discovery: "2027-03-15T10:30:00Z", looked: "2027-03-15T10:30:00Z" })),
               "2027-03-15T11:00:00Z");
  const held = { discovery: "2027-03-15T15:00:00Z", held: { why: "quota", until: "2027-03-16T07:00:00Z" } };
  assert.equal(iso(nextLook(new Date(T("2027-03-15T15:00:00Z")), held)), "2027-03-16T07:00:00Z", "a hold: its end");
});

test("a hold ends at midnight Pacific for the quota and New Hampshire's midnight for a key, across each change", () => {
  const cases = [
    [PACIFIC, "2027-03-13T20:00:00Z", "2027-03-14T08:00:00Z"],   // Saturday noon PST: midnight is still PST
    [PACIFIC, "2027-03-14T12:00:00Z", "2027-03-15T07:00:00Z"],   // Sunday 05:00 PDT: the next is PDT
    [PACIFIC, "2027-11-07T07:30:00Z", "2027-11-08T08:00:00Z"],   // Sunday 23:30 PDT before, 00:00 PST after
    [NEW_YORK, "2027-11-07T03:00:00Z", "2027-11-07T04:00:00Z"],  // 23:00 EDT on the 6th
    [NEW_YORK, "2027-11-07T12:00:00Z", "2027-11-08T05:00:00Z"],
    [NEW_YORK, "2027-03-14T04:59:00Z", "2027-03-14T05:00:00Z"],
    [NEW_YORK, "2027-03-14T12:00:00Z", "2027-03-15T04:00:00Z"],
  ];
  for (const [tz, at, want] of cases) assert.equal(iso(midnightAfter(new Date(T(at)), tz)), want, `${tz} ${at}`);
  const yt = { held: { why: "quota", until: "2027-03-14T08:00:00Z" } };
  assert.equal(youtubeDue(new Date(T("2027-03-14T07:58:00Z")), yt).any, false);
  assert.equal(youtubeDue(new Date(T("2027-03-14T08:00:00Z")), yt).discover, true);
});

test("the night's windows are refusal.py's, through live.gen.js, at their UTC hours whatever New Hampshire's", () => {
  assert.ok(NIGHT_WINDOWS.length >= 1);
  // Every window: in at its start and a minute before its end, out a minute
  // before its start (unless another window is there) and at its end.
  for (const day of ["2027-01-11", "2027-07-12", "2027-03-15", "2027-11-08"]) {     // Mondays
    for (let k = 0; k < 7; k++) {
      const d = T(`${day}T00:00:00Z`) + k * 86_400_000;
      const weekday = (new Date(d).getUTCDay() + 6) % 7;
      for (const [wd, [sh, sm], [eh, em]] of NIGHT_WINDOWS) {
        if (wd !== null && wd !== weekday) continue;
        const s = d + (sh * 60 + sm) * MIN, e = d + (eh * 60 + em) * MIN;
        assert.ok(nightWindow(new Date(s)), iso(s));
        assert.ok(nightWindow(new Date(e - MIN)), iso(e - MIN));
        const inOther = t => NIGHT_WINDOWS.some(([w2, [a, b], [c, f]]) =>
          (w2 === null || w2 === weekday) && t >= d + (a * 60 + b) * MIN && t < d + (c * 60 + f) * MIN);
        if (!inOther(s - MIN)) assert.equal(nightWindow(new Date(s - MIN)), null, iso(s - MIN));
        if (!inOther(e)) assert.equal(nightWindow(new Date(e)), null, iso(e));
      }
    }
  }
  // The daily window opens at 03:00 EST in January and 04:00 EDT in July.
  const daily = NIGHT_WINDOWS.find(w => w[0] === null);
  if (daily) {
    assert.equal(nh(T(`2027-01-12T${String(daily[1][0]).padStart(2, "0")}:00:00Z`)).hour, daily[1][0] - 5);
    assert.equal(nh(T(`2027-07-13T${String(daily[1][0]).padStart(2, "0")}:00:00Z`)).hour, daily[1][0] - 4);
  }
});
