// The November test as the Worker runs it (index.js with test_mode.js): only
// while control.json says "sql": "test", one connection a weekday between
// 10:00 and 16:00, its file written at once under the lease, each past
// sitting read once, and nothing at all asked of the database otherwise. A
// fake SQL Server on the loopback address answers from records/rollcalls/
// (from_records.js); YouTube is the synthetic one (world.js). preflight runs
// this suite (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { nodeConnect, startFakeTds } from "./fake_tds.js";
import { fromRecords } from "./from_records.js";
import { HC, MIN, T, world } from "./world.js";

const WED = "2026-11-18T15:30:00Z";                 // 10:30 in New Hampshire
const TEST = { youtube: "on", sql: "test" };

// A world whose database is a fake on this machine, and every run given its
// socket opener, as the Worker is given cloudflare:sockets'.
async function withDb(opts, body, fakeOpts = {}) {
  const fake = await startFakeTds({ answer: fromRecords(), ...fakeOpts });
  try {
    const w = world(opts);
    Object.assign(w.env, { SQL_HOST: "127.0.0.1", SQL_PORT: String(fake.port) });
    const runAt = w.runAt;
    w.runAt = (when, o = {}) => runAt(when, { connect: nodeConnect, ...o });
    await body(w, fake);
  } finally {
    await fake.close();
  }
}

test("sql test: the day's one connection reads 11 March 2026 and writes its file at once, under the lease", () =>
  withDb({ start: WED, control: TEST }, async (w, fake) => {
    const seen = [];
    w.r2.hooks.put = async key => { if (key.startsWith("test/")) seen.push(w.r2.read("state.json").lease); };
    const out = await w.runAt();
    assert.ok(out.codes.includes("sql_test_sitting_ok"), out.codes.join(" "));
    assert.equal(fake.seen.connections, 1);
    assert.deepEqual(out.wrote.slice(0, 1), ["test/2026-03-11.json"], "the test's file before the streams'");
    assert.ok(seen[0] && seen[0].run === out.run, "written under this run's lease");
    const f = w.r2.read("test/2026-03-11.json");
    assert.equal(f.rollcalls.length, 56);
    assert.deepEqual(w.state().test, { done: ["2026-03-11"], last: "2026-11-18" });
    assert.equal(w.state().count.connections, 1);
    assert.equal(w.state().count.statements, 6, "@@VERSION, Q1, Q3 and Q2 three times");
    assert.match(w.pings[0].body, /sql test by control\.json/);
    assert.match(w.pings[0].body, /1 connections, 6 statements/);
    assert.equal(w.fails().length, 0);
    // The rest of the day asks the database nothing.
    await w.every("2026-11-18T15:32:00Z", "2026-11-18T23:00:00Z");
    assert.equal(fake.seen.connections, 1);
  }));

test("sql test over three weekdays: day 1, then veto day, then a login alone; weekends and other hours nothing", () =>
  withDb({ start: "2026-11-18T05:00:00Z", control: TEST }, async (w, fake) => {
    const conns = [];
    await w.every("2026-11-18T05:00:00Z", "2026-11-24T05:00:00Z", async (_o, t) => {
      if (fake.seen.connections > conns.length) conns.push(new Date(t).toISOString());
    }, 10 * MIN);
    // Wed, Thu, Fri, and Mon 23 Nov: the first run at or after 10:00 EST (15:00 UTC).
    assert.deepEqual(conns, ["2026-11-18T15:00:00.000Z", "2026-11-19T15:00:00.000Z",
                             "2026-11-20T15:00:00.000Z", "2026-11-23T15:00:00.000Z"]);
    assert.ok(w.r2.read("test/2026-03-11.json") && w.r2.read("test/2026-08-19.json"));
    const login = w.r2.read("test/login/2026-11-20.json");
    assert.equal(login.kind, "live.test.login");
    assert.equal(login.problem, null);
    assert.ok(login.connection.login_ms >= 0);
    assert.deepEqual(w.state().test.done, ["2026-03-11", "2026-08-19"]);
    assert.equal(w.fails().length, 0);
  }));

test("with sql off, missing or unreadable, or on (until the session reads land), the database is never asked", async () => {
  for (const control of [{ youtube: "on", sql: "off" }, undefined, '{"sql": "tset"}', { youtube: "on", sql: "on" }]) {
    await withDb({ start: "2026-11-18T05:00:00Z", control }, async (w, fake) => {
      await w.every("2026-11-18T05:00:00Z", "2026-11-21T05:00:00Z", null, 10 * MIN);
      assert.equal(fake.seen.connections, 0, JSON.stringify(control));
      assert.ok(![...w.r2.objects.keys()].some(k => k.startsWith("test/")));
    });
  }
});

test("a server that requires encryption: said as a failure, no login sent, and the same sitting asked the next weekday", () =>
  withDb({ start: WED, control: TEST }, async (w, fake) => {
    const out = await w.runAt();
    assert.ok(out.codes.includes("sql_test_sitting_encrypt"), out.codes.join(" "));
    assert.equal(fake.seen.login7.length, 0);
    assert.equal(w.fails().length, 1);
    assert.match(w.fails()[0].body, /the November test could not read \(encrypt\)/);
    assert.equal(w.r2.read("test/2026-03-11.json").test.problem, "encrypt");
    assert.deepEqual(w.state().test.done, []);
    await w.runAt("2026-11-18T17:00:00Z");
    assert.equal(fake.seen.connections, 1, "not again the same day");
    await w.runAt("2026-11-19T15:30:00Z");
    assert.equal(fake.seen.connections, 2, "the next weekday");
  }, { encryption: 0x03 }));

test("a test file that cannot be written: said, the sitting not counted as read, and read again on the next weekday only", () =>
  withDb({ start: WED, control: TEST }, async (w, fake) => {
    w.r2.hooks.put = async key => { if (key.startsWith("test/")) throw new Error("R2 said 500"); };
    const out = await w.runAt();
    assert.ok(out.codes.includes("write_failed_test/2026-03-11.json"), out.codes.join(" "));
    assert.match(out.fail, /was not written: it is asked again on the next weekday/);
    assert.deepEqual(w.state().test, { done: [], last: "2026-11-18" });
    w.r2.hooks.put = null;
    await w.every("2026-11-18T15:32:00Z", "2026-11-18T21:00:00Z", null, 10 * MIN);
    assert.equal(fake.seen.connections, 1);
    await w.runAt("2026-11-19T15:30:00Z");
    assert.equal(fake.seen.connections, 2);
    assert.ok(w.r2.read("test/2026-03-11.json"));
  }));

test("a run that finds another's lease never connects, and a lapsed lease writes no test file", () =>
  withDb({ start: WED, control: TEST }, async (w, fake) => {
    w.r2.seed("state.json", { v: 1, lease: { run: "other", until: "2026-11-18T15:31:00Z" }, yt: {} });
    const out = await w.runAt();
    assert.deepEqual(out.codes, ["lease_held_1"]);
    assert.equal(fake.seen.connections, 0);
    const lapsed = await w.runAt("2026-11-18T15:32:00Z", { elapsed: () => 100_000 });
    assert.ok(lapsed.codes.includes("lease_lapsed"), lapsed.codes.join(" "));
    assert.ok(!w.r2.objects.has("test/2026-03-11.json"));
    assert.deepEqual(w.state().test.done, []);
  }));

test("the run's ping names the test and its counts; Healthchecks' URL is the plain one when it read", () =>
  withDb({ start: WED, control: TEST }, async w => {
    await w.runAt();
    assert.equal(w.pings[0].url, HC);
    assert.match(w.pings[0].body, /sql_test_sitting_ok/);
    assert.ok(T(w.pings[0].at) > 0);
  }));
