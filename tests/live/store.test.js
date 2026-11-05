// workers/live/store.js through the Worker's run(): one writer at a time (the
// lease), nothing public written without it, losing state.json harmless, a
// run that had something due and wrote nothing said as a failure, the
// 30-day sweep, and control.json, the person's one switch. The bucket is an
// R2 in memory with etags (fake_r2.js). preflight runs this suite (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { AsyncLocalStorage } from "node:async_hooks";
import { readFileSync, readdirSync } from "node:fs";
import { CONTROL_DEFAULT, CONTROL_VALUES, LEASE_MS, WRITE_BY_MS, parseControl } from "../../workers/live/store.js";
import { pingBody } from "../../workers/live/index.js";
import { HC, MIN, T, iso, world } from "./world.js";

const STREAM = { id: "houseFinanc", chamber: "H", title: "House Finance (01/07/2027)",
                 scheduled: T("2027-01-07T14:00:00Z"), listedAt: T("2027-01-05T14:00:00Z"),
                 start: T("2027-01-07T14:00:00Z"), end: T("2027-01-07T18:00:00Z") };

test("a run takes the lease before it writes, writes only while it holds it, and releases it", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add(STREAM);
  const seen = [];
  w.r2.hooks.put = async key => {
    if (!key.startsWith("streams/")) return;
    seen.push(w.r2.read("state.json").lease);
  };
  const out = await w.runAt(undefined, { run: "run-lease-1" });
  assert.deepEqual(out.wrote, ["streams/2027-01-07.json"]);
  assert.equal(seen.length, 1);
  assert.equal(seen[0].run, "run-lease-1");
  assert.equal(seen[0].until, iso(T("2027-01-07T14:00:00Z") + LEASE_MS));
  assert.equal(w.state().lease, null, "released");
  // In order: read the switch and the state, take the lease, write, release.
  const order = w.r2.ops.filter(([op, k]) => op === "put" || k === "state.json").map(([op, k]) => `${op} ${k}`);
  assert.deepEqual(order, ["get state.json", "put state.json", "put streams/2027-01-07.json", "put state.json"]);
});

test("a run that finds another's lease writes nothing, and the third tick in a row tells Healthchecks", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  const held = t => w.r2.seed("state.json", { v: 1, lease: { run: "other", until: iso(T(t) + 60_000) },
                                              day: "2027-01-07", count: { units: 0, searches: 0 }, yt: {},
                                              swept: "2027-01-07" });
  for (const [i, t] of ["2027-01-07T14:00:00Z", "2027-01-07T14:02:00Z", "2027-01-07T14:04:00Z"].entries()) {
    held(t);
    const before = w.r2.puts().length;
    const out = await w.runAt(t);
    assert.deepEqual(out.codes, [`lease_held_${i + 1}`]);
    assert.deepEqual(w.r2.puts().slice(before), ["lease-waits.json"], "the one object a waiting run writes");
    assert.equal(w.yt.calls.length, 0, "and it asks YouTube nothing");
  }
  assert.equal(w.fails().length, 1);
  assert.match(w.fails()[0].body, /3 runs in a row have found another run's lease/);
  // A tick with no run waiting breaks the row.
  w.r2.seed("state.json", { v: 1, lease: null, yt: {} });
  assert.deepEqual((await w.runAt("2027-01-07T14:06:00Z")).wrote, ["streams/2027-01-07.json"]);
  held("2027-01-07T14:10:00Z");
  assert.deepEqual((await w.runAt("2027-01-07T14:10:00Z")).codes, ["lease_held_1"]);
});

test("a run that loses state.json between reading it and taking the lease writes nothing public", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add(STREAM);
  let once = true;
  w.r2.hooks.put = async (key, _v, opts) => {
    if (key === "state.json" && once && opts.onlyIf) {
      once = false;
      w.r2.seed("state.json", { v: 1, lease: { run: "faster", until: iso(w.now + LEASE_MS) }, yt: {} });
    }
  };
  w.r2.seed("state.json", { v: 1, lease: null, yt: {} });
  const out = await w.runAt();
  assert.deepEqual(out.codes, ["lease_held_1"]);
  assert.deepEqual(out.wrote, []);
  assert.deepEqual(w.r2.puts().filter(k => k.startsWith("streams/")), []);
  assert.equal(w.r2.read("state.json").lease.run, "faster", "the other run's lease stands");
});

// Two runs at every tick, interleaving at each await as two invocations would.
// `who` knows which run is writing, so each public write is checked against
// the lease state.json holds at that moment.
async function twice(w, from, to) {
  const who = new AsyncLocalStorage();
  const bad = [], writes = [];
  w.r2.hooks.put = async key => {
    if (!key.startsWith("streams/")) return;
    const lease = w.r2.read("state.json").lease;
    writes.push(who.getStore());
    if (!(lease && lease.run === who.getStore() && Date.parse(lease.until) > w.now)) {
      bad.push(`${iso(w.now)} ${who.getStore()} wrote ${key} under ${JSON.stringify(lease)}`);
    }
  };
  let blocked = 0;
  for (let t = T(from); t < T(to); t += 2 * MIN) {
    w.now = t;
    const outs = await Promise.all(["a", "b"].map(x => who.run(`${x}-${t}`, () => w.runAt(t, { run: `${x}-${t}` }))));
    blocked += outs.filter(o => o.codes.some(c => c.startsWith("lease_held"))).length;
  }
  return { bad, writes, blocked };
}

test("over a day whose every cron fires twice, no public file is ever written without its writer's lease", async () => {
  const w = world({ start: "2027-01-07T05:00:00Z" });
  w.yt.add(STREAM);
  w.yt.add({ ...STREAM, id: "senateSessi", chamber: "S", title: "Senate Session (01/07/27)", scheduled: null,
             start: T("2027-01-07T15:00:00Z"), end: T("2027-01-07T21:00:00Z"), listedAt: T("2027-01-07T21:00:00Z") });
  await w.runAt("2027-01-07T04:58:00Z");                    // the first run ever was alone
  const { bad, writes, blocked } = await twice(w, "2027-01-07T05:00:00Z", "2027-01-08T05:00:00Z");
  assert.deepEqual(bad, []);
  assert.ok(writes.length > 400, `${writes.length} public writes checked`);
  assert.ok(blocked > 400, `${blocked} runs found the other's lease`);
  assert.equal(w.streams("2027-01-07").status.ok, true);
  assert.ok(w.fails().length > 0, "a cron that fires twice, tick after tick, is said");
  assert.ok(w.fails().every(p => /runs in a row have found another run's lease/.test(p.body)));
});

test("the one unguarded case is the design's: two runs at the very moment no state.json exists", async () => {
  // store.js: "The first run ever, with no state.json, writes one
  // unconditionally: two runs at that exact moment is the one unguarded case."
  // It is that moment and no other: from the next tick, the lease holds.
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add(STREAM);
  const first = await twice(w, "2027-01-07T14:00:00Z", "2027-01-07T14:02:00Z");
  assert.equal(first.writes.length, 2, "both wrote: the gap the design names");
  const after = await twice(w, "2027-01-07T14:02:00Z", "2027-01-07T16:00:00Z");
  assert.deepEqual(after.bad, []);
  assert.equal(after.writes.length, 59, "one a tick");
});

test("a lease that lapses before the file is written writes none, says so, and the next run looks again", async () => {
  const w = world({ start: "2027-01-08T03:00:00Z" });        // 22:00 EST: discovery every 30 minutes
  w.yt.add(STREAM);
  await w.runAt();
  const discovered = w.state().yt.discovery;
  const out = await w.runAt("2027-01-08T03:30:00Z", { elapsed: () => WRITE_BY_MS + 1 });
  assert.ok(out.codes.includes("lease_lapsed"), out.codes.join(" "));
  assert.deepEqual(out.wrote, []);
  assert.match(out.fail, /1 file\(s\) were due and not written/);
  assert.equal(w.fails().length, 1);
  assert.equal(w.state().yt.discovery, discovered, "the look not written is not counted as made");
  assert.equal(w.state().count.units, w.yt.spent().units, "what it spent is");
  assert.equal(w.state().lease, null);
  const again = await w.runAt("2027-01-08T03:32:00Z");
  assert.deepEqual(again.wrote, ["streams/2027-01-07.json"]);
});

test("a run that had something due and wrote nothing tells Healthchecks, whatever stopped it", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.r2.hooks.put = async key => { if (key.startsWith("streams/")) throw new Error("R2 said 500"); };
  const out = await w.runAt();
  assert.ok(out.codes.includes("write_failed_streams/2027-01-07.json"));
  assert.equal(w.fails().length, 1);
  const w2 = world({ start: "2027-01-07T14:00:00Z" });
  w2.r2.hooks.get = async key => { if (key === "state.json") throw new Error("R2 unreachable"); };
  const out2 = await w2.runAt();
  assert.ok(out2.codes.includes("error") && /R2 unreachable/.test(out2.fail));
  assert.equal(w2.fails().length, 1);
  const w3 = world({ start: "2027-01-07T14:00:00Z" });
  delete w3.env.LIVE;
  const out3 = await w3.runAt();
  assert.match(out3.fail, /no LIVE bucket is bound/);
  assert.equal(w3.fails().length, 1);
});

test("a lost state.json is harmless: the next run starts it again and the day's file carries on", async () => {
  const w = world({ start: "2027-01-07T13:00:00Z" });
  w.yt.add(STREAM);
  w.yt.add({ id: "fiscalNextW", chamber: "H", title: "Fiscal Committee (01/15/2027)",
             scheduled: T("2027-01-15T15:00:00Z"), listedAt: T("2027-01-06T16:00:00Z") });
  await w.every("2027-01-07T13:00:00Z", "2027-01-07T15:00:00Z");
  const before = w.streams("2027-01-07");
  assert.deepEqual(before.streams.map(s => s.status), ["live"]);
  w.r2.objects.delete("state.json");
  const out = await w.runAt("2027-01-07T15:00:00Z");
  assert.deepEqual(out.wrote, ["streams/2027-01-07.json"]);
  const after = w.streams("2027-01-07");
  assert.deepEqual(after.streams.map(s => [s.video, s.status]), [["houseFinanc", "live"]]);
  assert.equal(after.streams[0].seen.playlist, before.streams[0].seen.playlist, "the file's record carries on");
  const s = w.state();
  assert.ok(s.yt.upcoming.fiscalNextW, "a kept upcoming id is found again in the playlist");
  assert.ok(s.yt.uploads, "the uploads playlists are confirmed again");
  assert.ok(s.count.units <= 4, `the day's count starts again: ${s.count.units}`);
  assert.equal(w.fails().length, 0);
});

test("an unreadable state.json is replaced under the lease", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.r2.seed("state.json", "{ not json");
  const etag = w.r2.objects.get("state.json").etag;
  let conditional = null;
  w.r2.hooks.put = async (key, _v, opts) => { if (key === "state.json" && conditional === null) conditional = opts.onlyIf; };
  const out = await w.runAt();
  assert.deepEqual(conditional, { etagMatches: etag }, "taken on the etag of what was there");
  assert.deepEqual(out.wrote, ["streams/2027-01-07.json"]);
  assert.equal(w.state().v, 1);
});

test("the first run after 03:00 deletes what was last written 30 calendar days ago, and nothing else", async () => {
  const w = world({ start: "2027-01-07T07:58:00Z" });        // 02:58 EST
  const at = s => T(s);
  w.r2.seed("streams/2026-12-08.json", { day: "2026-12-08" }, at("2026-12-09T03:00:00Z"));   // 22:00 EST on the 8th
  w.r2.seed("streams/2026-12-09.json", { day: "2026-12-09" }, at("2026-12-10T04:58:00Z"));   // 23:58 EST on the 9th
  w.r2.seed("votes/2026-12-08.json", {}, at("2026-12-08T20:00:00Z"));
  w.r2.seed("test/2026-03-11.json", {}, at("2026-12-07T15:00:00Z"));                          // a past sitting, read a month ago
  w.r2.seed("test/2026-08-19.json", {}, at("2026-12-20T15:00:00Z"));
  for (let i = 0; i < 2500; i++) w.r2.seed(`votes/old-${String(i).padStart(5, "0")}.json`, {}, at("2026-11-01T12:00:00Z"));
  w.r2.seed("control.json", { youtube: "on", sql: "off" }, at("2026-10-01T12:00:00Z"));
  w.r2.seed("lease-waits.json", { n: 1, last: "2026-10-01T12:00:00Z" }, at("2026-10-01T12:00:00Z"));
  await w.runAt();
  assert.ok(w.r2.objects.has("streams/2026-12-08.json"), "not before 03:00");
  const out = await w.runAt("2027-01-07T08:00:00Z");
  assert.ok(out.codes.includes("swept_2503"), out.codes.join(" "));
  const left = [...w.r2.objects.keys()].sort();
  assert.deepEqual(left.filter(k => !k.startsWith("streams/2027")),
                   ["control.json", "lease-waits.json", "state.json", "streams/2026-12-09.json",
                    "test/2026-08-19.json"]);
  const lists = w.r2.ops.filter(([op]) => op === "list").length;
  await w.every("2027-01-07T08:02:00Z", "2027-01-07T12:00:00Z");
  assert.equal(w.r2.ops.filter(([op]) => op === "list").length, lists, "once a day");
  await w.runAt("2027-01-08T08:00:00Z");
  assert.ok(!w.r2.objects.has("streams/2026-12-09.json"), "the 9th goes on the 8th of January");
});

test("control.json: missing or unreadable is shadow, and every file the person may put is one this reads", async () => {
  for (const [body, source] of [[undefined, "missing"], ["{", "unreadable"], ['{"youtube": "of"}', "unreadable"],
                                ["[]", "unreadable"], ['{"sql": "maybe"}', "unreadable"]]) {
    const w = world({ start: "2027-01-07T14:00:00Z", control: body });
    await w.runAt();
    assert.ok(w.yt.calls.length > 0, `${source}: YouTube is asked`);
    assert.match(w.pings[0].body, new RegExp(`youtube on, sql off: control\\.json ${source}, so shadow`), body);
    // Unreadable is said as a failure on every run until it is mended: it may
    // be the person's "off" mistyped. Missing is the plain default.
    await w.every("2027-01-07T14:02:00Z", "2027-01-07T14:08:00Z");
    const want = source === "unreadable" ? `${HC}/fail` : HC;
    assert.ok(w.pings.every(p => p.url === want), `${source}: ${w.pings.map(p => p.url)}`);
    if (source === "unreadable") assert.match(w.pings[0].body, /control\.json cannot be read, so it is honoured as shadow/);
  }
  assert.deepEqual(parseControl('{"youtube": "off"}'), { youtube: "off", sql: "off" }, "a field left out takes its default");
  assert.deepEqual(parseControl('{"youtube": "on", "sql": "test", "note": "November"}'), { youtube: "on", sql: "test" });
  const dir = new URL("../../workers/live/control/", import.meta.url);
  const files = readdirSync(dir).sort();
  assert.deepEqual(files, ["all-off.json", "on.json", "sql-off.json", "sql-test.json"]);
  const read = Object.fromEntries(files.map(f => [f, parseControl(readFileSync(new URL(f, dir), "utf8"))]));
  assert.deepEqual(read, { "all-off.json": { youtube: "off", sql: "off" }, "on.json": { youtube: "on", sql: "on" },
                           "sql-off.json": { youtube: "on", sql: "off" }, "sql-test.json": { youtube: "on", sql: "test" } });
  assert.deepEqual(CONTROL_DEFAULT, read["sql-off.json"], "missing is the same as sql-off: shadow");
  for (const v of Object.values(read)) for (const [k, x] of Object.entries(v)) assert.ok(CONTROL_VALUES[k].includes(x));
});

test("Healthchecks hears every run, what control.json says and that it is honoured; without its URL, nothing", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z", control: { youtube: "on", sql: "test" } });
  w.yt.add(STREAM);
  await w.runAt();
  await w.runAt("2027-01-07T14:02:00Z");
  assert.equal(w.pings.length, 2);
  assert.ok(w.pings.every(p => p.url === HC));
  assert.match(w.pings[1].body, /^run run-0000 youtube_ok_1_live \| youtube on, sql test by control\.json, uploaded 2027-01-07 09:00 New Hampshire time \| today \d+ units, 2 searches$/);
  const quiet = world({ start: "2027-01-07T14:00:00Z", healthcheck: null });
  const out = await quiet.runAt();
  assert.deepEqual(out.wrote, ["streams/2027-01-07.json"]);
  assert.equal(quiet.pings.length, 0);
  assert.match(pingBody({ run: "abcdef123", codes: ["x"], count: null, fail: "why" },
                        { ...CONTROL_DEFAULT, source: "missing" }), /FAIL: why$/);
});

test("the lease's numbers are the design's (section 3.3): 110 s, writes under 90 s, both inside the cron's 120 s", () => {
  assert.equal(LEASE_MS, 110_000);
  assert.equal(WRITE_BY_MS, 90_000);
  assert.ok(WRITE_BY_MS < LEASE_MS && LEASE_MS < 120_000);
});

test("a lease that has run out, or is this run's own, does not stop a run; and the release clears it", async () => {
  for (const lease of [{ run: "other", until: "2027-01-07T13:59:59Z" }, { run: "run-mine", until: "2027-01-07T14:01:00Z" }]) {
    const w = world({ start: "2027-01-07T14:00:00Z" });
    w.yt.add(STREAM);
    w.r2.seed("state.json", { v: 1, lease, day: "2027-01-07", count: { units: 0, searches: 0 }, yt: {}, swept: "2027-01-07" });
    const out = await w.runAt(undefined, { run: "run-mine" });
    assert.deepEqual(out.wrote, ["streams/2027-01-07.json"], JSON.stringify(lease));
    assert.equal(w.state().lease, null, `released: ${JSON.stringify(lease)}`);
  }
});

test("a run whose lease was taken from it while it worked does not release over the taker", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.yt.add(STREAM);
  w.r2.hooks.put = async key => {
    if (key.startsWith("streams/")) {
      w.r2.seed("state.json", { v: 1, lease: { run: "taker", until: iso(w.now + LEASE_MS) }, yt: {} });
    }
  };
  const out = await w.runAt();
  assert.ok(out.codes.includes("lease_lost"), out.codes.join(" "));
  assert.equal(w.state().lease.run, "taker", "the taker's lease stands");
});

test("a lease is lapsed at WRITE_BY_MS itself, not only past it", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  const out = await w.runAt(undefined, { elapsed: () => WRITE_BY_MS });
  assert.ok(out.codes.includes("lease_lapsed"), out.codes.join(" "));
  assert.deepEqual(out.wrote, []);
});

test("a control.json R2 cannot hand over is unreadable: shadow, and said as a failure", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.r2.hooks.get = async key => { if (key === "control.json") throw new Error("R2 said 500"); };
  const out = await w.runAt();
  assert.deepEqual(out.wrote, ["streams/2027-01-07.json"], "the run went on as shadow");
  assert.equal(w.fails().length, 1);
  assert.match(w.fails()[0].body, /control\.json unreadable, so shadow/);
});

test("a state.json of another version is not read: its lease is not honoured and it is replaced", async () => {
  const w = world({ start: "2027-01-07T14:00:00Z" });
  w.r2.seed("state.json", { v: 2, lease: { run: "other", until: "2027-01-07T15:00:00Z" }, yt: { upcoming: { x: {} } } });
  const out = await w.runAt();
  assert.deepEqual(out.wrote, ["streams/2027-01-07.json"]);
  assert.equal(w.state().v, 1);
  assert.equal(w.state().yt.upcoming.x, undefined);
});

