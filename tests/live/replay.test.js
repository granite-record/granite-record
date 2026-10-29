// The replays (the live layer's design, section 7.2): whole sitting days run
// through the Worker's own run() on a fake clock, every 2 minutes from 07:00
// to 23:59 New Hampshire time, under the real cadence rules, against a fake
// SQL Server on the loopback address that holds each roll call from the
// moment the record says it was saved (records/rollcalls/ in git) plus a
// lag, and a YouTube answering the day's session stream as the committed
// index recorded it (collected/videos/). Files in git only, so they run in a
// cloud session too. preflight runs this suite (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { nodeConnect, startFakeTds } from "./fake_tds.js";
import { CODE, fromRecords, year } from "./from_records.js";
import { recordTime } from "./compare_test.mjs";
import { BALLOT_CHAR } from "../../workers/live/live.gen.js";
import { BUDGET } from "../../workers/live/votes.js";
import { nhToUtc } from "../../workers/live/test_mode.js";
import { MIN, T, world } from "./world.js";

const LAG = 30_000;
const ON = { youtube: "on", sql: "on" };

// When the database holds a roll call: the House's when it was taken, the
// Senate's when it was saved (its VoteDate is midnight).
const savedAt = f => T(nhToUtc(recordTime(f[1] === "S" ? f[14] : f[3])));
const dayOf = f => recordTime(f[3]).slice(0, 10);

// A day's run: the world, its database releasing rows on the world's clock,
// every run to `to`. Returns the world and what was read when.
async function replay({ start, to, streams = [], docket = [], extra = null }) {
  let w;
  const answer = fromRecords({ released: f => savedAt(f) + LAG <= w.now, docket,
                               lineShown: entered => T(nhToUtc(entered)) <= w.now });
  const fake = await startFakeTds({ answer });
  try {
    w = world({ start, control: ON });
    Object.assign(w.env, { SQL_HOST: "127.0.0.1", SQL_PORT: String(fake.port) });
    const runAt = w.runAt;
    w.runAt = (when, o = {}) => runAt(when, { connect: nodeConnect, ...o });
    for (const s of streams) w.yt.add(s);
    const reads = [];
    let before = 0;
    await w.every(start, to, async (out, t) => {
      if (fake.seen.connections > before) reads.push({ t, codes: out.codes });
      before = fake.seen.connections;
      if (extra) await extra(w, t, out);
    }, 2 * MIN);
    return { w, reads, fake: fake.seen };
  } finally {
    await fake.close();
  }
}

// Every roll call of `y` dated `day` in `body`, from the record.
const recordDay = (y, day, body) => year(y).summary.filter(f => f[1] === body && dayOf(f) === day);

// The file's ballots against the record's, member by member.
function ballotsAgree(file, y, f) {
  const rc = file.rollcalls.find(r => r.id === `${y}-${f[1]}-${f[2]}`);
  const want = new Map(year(y).history.filter(h => h[1] === f[1] && h[2] === f[2])
    .map(h => [h[4] || h[3], BALLOT_CHAR[CODE[h[6]]]]));
  const got = new Map(file.members[f[1]].map((m, i) => [m, rc.ballots[i]]));
  const differ = [...want].filter(([m, c]) => got.get(m) !== c).slice(0, 3);
  return { differ, members: want.size };
}

test("replay, 11 March 2026, the House: every roll call within two runs, every ballot the record's, under the budget", async () => {
  const day = "2026-03-11";
  const { w, reads } = await replay({
    start: "2026-03-11T11:00:00Z", to: "2026-03-12T04:00:00Z",          // 07:00 to 23:58 EDT
    streams: [{ id: "houseSess11", chamber: "H", title: "House Session (03/11/2026)",
                start: T("2026-03-11T12:58:46Z"), end: T("2026-03-12T00:49:01Z") }],
    docket: [["H", "HB1376", "2026-03-11T09:32:51", "12", "OTPA: MA RC 171-143 03/11/2026 HJ 8 P. 20"]] });
  const file = w.r2.read(`votes/${day}.json`);
  const record = recordDay("2026", day, "H");
  assert.equal(record.length, 56);
  assert.equal(file.rollcalls.filter(r => r.body === "H").length, 56);
  const late = [];
  for (const f of record) {
    const rc = file.rollcalls.find(r => r.id === `2026-H-${f[2]}`);
    const wait = T(rc.first_seen) - (savedAt(f) + LAG);
    if (!(wait >= 0 && wait <= 4 * MIN)) late.push(`${rc.id} ${wait / MIN} min`);
    assert.deepEqual([rc.yeas, rc.nays, rc.present, rc.absent], [f[5], f[6], f[7], f[8]].map(Number), rc.id);
    const { differ, members } = ballotsAgree(file, "2026", f);
    assert.ok(members > 300 && !differ.length, `${rc.id}: ${JSON.stringify(differ)}`);
    assert.equal(rc.ballots_complete, true, rc.id);
  }
  assert.deepEqual(late, [], "within two runs of reaching the database");
  // The docket's line, attached; the outcome is the docket's, never worked out.
  const hb1376 = file.rollcalls.find(r => r.bill_as_recorded === "HB1376" && r.yeas === 171);
  assert.deepEqual(hb1376.docket, { line: "OTPA: MA RC 171-143 03/11/2026 HJ 8 P. 20", abbrev: "MA", outcome: "Motion Adopted" });
  const s = w.state();
  console.log(`# replay 2026-03-11: ${s.count.connections} connections, ${s.count.statements} statements, ${s.count.rows} rows`);
  assert.ok(s.count.connections < BUDGET.connections && s.count.statements < BUDGET.statements
            && s.count.rows < BUDGET.rows, JSON.stringify(s.count));
  assert.ok(s.count.connections >= 300 && s.count.connections <= 460, `${s.count.connections} connections`);
  assert.equal(file.status.problem, null);
  // Nothing read before the night's window ended unless the stream was live, nor after 23:59.
  const first = reads[0].t;
  assert.ok(first >= T("2026-03-11T12:58:00Z"), `first read ${new Date(first).toISOString()}`);
  assert.ok(reads.at(-1).t < T("2026-03-12T04:00:00Z"));
  assert.equal(w.fails().length, 0, w.fails().map(p => p.body).join("\n"));
});

test("replay, 12 March 2020, the House with no stream: the heartbeat finds the sitting, and every roll call is in within 15 minutes", async () => {
  const day = "2020-03-12";
  const { w, reads } = await replay({ start: "2020-03-12T11:00:00Z", to: "2020-03-13T05:00:00Z" });   // to 01:00
  const file = w.r2.read(`votes/${day}.json`);
  const record = recordDay("2020", day, "H");
  assert.equal(record.length, 49);
  assert.ok(reads[0].t === T("2020-03-12T13:30:00Z"), "the heartbeat's first read, 09:30 EDT");
  const late = [];
  for (const f of record) {
    const rc = file.rollcalls.find(r => r.id === `2020-H-${f[2]}`);
    const wait = rc ? T(rc.first_seen) - (savedAt(f) + LAG) : Infinity;
    if (!(wait >= 0 && wait <= 15 * MIN)) late.push(`2020-H-${f[2]} ${wait / MIN} min`);
    if (rc) assert.equal(ballotsAgree(file, "2020", f).differ.length, 0, rc.id);
  }
  assert.deepEqual(late, []);
  // Hot followed the roll calls: a gap over 45 minutes fell to warm and came back.
  const kinds = reads.map(r => (r.codes.find(c => c.startsWith("sql_read_")) || "").replace(/_wide|_\d+rc$/g, ""));
  assert.ok(kinds.includes("sql_read_hot") && kinds.includes("sql_read_warm") && kinds.includes("sql_read_heartbeat"));
  const lastVote = Math.max(...record.map(savedAt));
  assert.ok(reads.some(r => r.t > lastVote), "the 23:58 roll call was read");
  console.log(`# replay 2020-03-12: ${w.state().count.connections} connections, ${w.state().count.statements} statements`);
});

test("replay, 29-30 January 2026, the Senate: every roll call reaches the sitting's file, the two saved next morning too", async () => {
  const day = "2026-01-29";
  const { w } = await replay({
    start: "2026-01-29T12:00:00Z", to: "2026-01-30T23:00:00Z",          // Thursday 07:00 to Friday 18:00 EST
    streams: [{ id: "senateSes29", chamber: "S", title: "Senate Session (01/29/2026)",
                start: T("2026-01-29T14:58:46Z"), end: T("2026-01-29T18:44:45Z") }],
    // HB751's S 10 and S 12 are both 16-8: two lines, paired in order.
    docket: [["S", "HB751", "2026-01-19T10:00:00", "4", "Floor Amendment # 2026-0187s, AA, RC 16Y-8N; 01/29/2026"],
             ["S", "HB751", "2026-01-19T10:00:00", "5", "Ought to Pass with Amendment, RC 16Y-8N, MA; 01/29/2026"]] });
  const file = w.r2.read(`votes/${day}.json`);
  const record = recordDay("2026", day, "S");
  assert.ok(record.length >= 10);
  for (const f of record) {
    const rc = file.rollcalls.find(r => r.id === `2026-S-${f[2]}`);
    assert.ok(rc, `2026-S-${f[2]} reached the sitting's file`);
    assert.equal(rc.taken, null);
    assert.equal(rc.saved, nhToUtc(recordTime(f[14])));
  }
  for (const seq of ["9", "11"]) {
    const rc = file.rollcalls.find(r => r.id === `2026-S-${seq}`);
    assert.ok(T(rc.first_seen) > T("2026-01-30T16:00:00Z"), `S ${seq}, saved the next morning, read then`);
  }
  // The docket's line created ten days ahead attached to its roll call.
  const by = id => file.rollcalls.find(r => r.id === id).docket;
  assert.deepEqual([by("2026-S-10").outcome, by("2026-S-12").outcome], ["Amendment Adopted", "Motion Adopted"]);
  assert.ok(!w.r2.objects.has("votes/2026-01-30.json") || w.r2.read("votes/2026-01-30.json").rollcalls.length === 0,
            "nothing filed under the day it was saved");
});

test("replay, a non-sitting weekday in January: the heartbeat alone, a few connections, and no public file", async () => {
  const { w, reads } = await replay({ start: "2026-01-02T12:00:00Z", to: "2026-01-03T05:00:00Z" });   // a Friday, no roll calls
  assert.ok(reads.length >= 34 && reads.length <= 38, `${reads.length} reads: design section 2.3 measured 34-38`);
  assert.ok(reads.every(r => r.codes.some(c => c.startsWith("sql_read_heartbeat"))));
  assert.ok(![...w.r2.objects.keys()].some(k => k.startsWith("votes/")), "no file for a day with nothing");
  assert.equal(w.state().count.statements, reads.length, "Q1 alone, one a read");
  assert.equal(w.fails().length, 0);
});
