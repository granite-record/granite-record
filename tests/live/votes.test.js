// The votes half (workers/live/votes.js, merge.js) on its own: the docket's
// tally lines, the merge that never drops what was shown, each chamber's
// state across the day and the night's window, which roll calls need
// ballots, and the holds. The replays of whole sitting days are in
// replay.test.js. preflight runs this suite (_live_tests).
import { test } from "node:test";
import assert from "node:assert/strict";
import { MISSES_TO_NOTE, attach, dayOfLine, emptyFile, merge, parseTally } from "../../workers/live/merge.js";
import { BUDGET, EVERY, Q2_TRIES, _failedConnect, ballotsDue, chamberState, freshStreams, liftHolds, loginPrint,
         nextRead, overBudget, sessionLive, votesDue } from "../../workers/live/votes.js";

const MIN = 60_000;
const T = s => Date.parse(s);
const at = s => new Date(T(s));

const row = (seq, over = {}) => ({
  id: `2027-H-${seq}`, year: 2027, body: "H", seq, vote_date: `2027-01-07T10:${String(seq).padStart(2, "0")}:00`,
  bill_as_recorded: "HB2", yeas: 190, nays: 171, present: 0, absent: 39, question: "Ought to Pass",
  modified: `2027-01-07T10:${String(seq).padStart(2, "0")}:05`, user: "VOTE SYSTEM", ...over });

// ---- the docket -----------------------------------------------------------------
test("a tally line's RC counts only before digits, in the House's form and the Senate's, with the key's outcome", () => {
  assert.deepEqual(parseTally("OTPA: MA RC 171-143 03/11/2026 HJ 8 P. 20", "H"),
                   { yeas: 171, nays: 143, abbrev: "MA", outcome: "Motion Adopted", day: "2026-03-11", days: ["2026-03-11"] });
  assert.deepEqual(parseTally("Ought to Pass, RC 16Y-8N, MA; 01/29/2026", "S"),
                   { yeas: 16, nays: 8, abbrev: "MA", outcome: "Motion Adopted", day: "2026-01-29", days: ["2026-01-29"] });
  assert.equal(parseTally("Special Order to RC", "H"), null, "bare RC is Regular Calendar");
  assert.equal(parseTally("Removed from RC and tabled", "S"), null);
  assert.deepEqual(parseTally("Floor Amendment # 2026-0412s, AF, RC 10Y-14N; 02/19/2026", "S"),
                   { yeas: 10, nays: 14, abbrev: "AF", outcome: "Amendment Failed", day: "2026-02-19", days: ["2026-02-19"] });
  // The outcome is the tally's own clause's: a key word further along the line is not it.
  assert.equal(parseTally("Lay on Table, RC 12Y-11N; 01/29/2027 (MA in committee)", "S").outcome, null);
  // A line that writes two dates is the last one's, or today's when Q3 took it for today.
  const re = { body: "S", line: "Reconsider vote of 01/22/2027, RC 12Y-11N, MF; 01/29/2027", entered: "2027-01-20T10:00:00" };
  assert.equal(dayOfLine(re), "2027-01-29");
  assert.equal(dayOfLine(re, "2027-01-22"), "2027-01-22");
  const unknown = parseTally("OT RC 200-150", "H");
  assert.deepEqual([unknown.abbrev, unknown.outcome], [null, null], "a word not in the key is kept as written, no outcome");
  assert.equal(dayOfLine({ body: "S", line: "Ought to Pass, RC 16Y-8N, MA; 01/29/2026", entered: "2026-01-19T10:00:00" }),
               "2026-01-29", "a line is the sitting's it writes, not the day it was entered");
  assert.equal(dayOfLine({ body: "H", line: "MA RC 190-171", entered: "2027-01-07T10:15:00" }), "2027-01-07");
});

// ---- the merge ----------------------------------------------------------------
test("the merge never drops a roll call, sets first_seen once, and notes one the database stops listing", () => {
  const ballots = new Map([["2027-H-1", new Map([["11", "Y"], ["12", "N"]])]]);
  let m = merge(null, { date: "2027-01-07", rows: [row(1, { yeas: 1, nays: 1 })], ballots, at: "2027-01-07T15:02:00Z",
                        covered: true });
  assert.equal(m.file.rollcalls[0].first_seen, "2027-01-07T15:02:00Z");
  assert.deepEqual([m.file.members.H, m.file.rollcalls[0].ballots, m.file.rollcalls[0].ballots_complete],
                   [["11", "12"], "YN", true]);
  assert.equal(m.file.rollcalls[0].taken, "2027-01-07T15:01:00Z", "the House's VoteDate, as UTC");
  assert.equal(m.file.rollcalls[0].bill, "2027-2028/HB2");
  assert.equal(m.file.rollcalls[0].keyed_by, "voting system");
  let file = m.file, misses = m.misses;
  for (let i = 1; i <= MISSES_TO_NOTE; i++) {
    m = merge(file, { date: "2027-01-07", rows: [], at: `2027-01-07T15:0${2 + 2 * i}:00Z`, covered: true, misses });
    file = m.file; misses = m.misses;
    assert.equal(file.rollcalls.length, 1, `read ${i}: still shown`);
    assert.equal(file.rollcalls[0].note === null, i < MISSES_TO_NOTE, `read ${i}`);
  }
  assert.match(file.rollcalls[0].note, /^no longer listed by the database at 10:08; the record will settle it$/);
  assert.equal(file.rollcalls[0].first_seen, "2027-01-07T15:02:00Z", "first_seen never moves");
  // Listed again: the note goes, the count starts over.
  m = merge(file, { date: "2027-01-07", rows: [row(1, { yeas: 1, nays: 1 })], at: "2027-01-07T15:10:00Z", covered: true, misses });
  assert.equal(m.file.rollcalls[0].note, null);
  assert.equal(m.misses["2027-H-1"], undefined);
  // A read that did not cover the date counts no miss.
  m = merge(m.file, { date: "2027-01-07", rows: [], at: "2027-01-07T15:12:00Z", covered: false, misses: {} });
  assert.deepEqual(m.misses, {});
});

test("members only grow: a roll call read before keeps its string, padded, and one read again is replaced whole", () => {
  const a = merge(null, { date: "2027-01-07", rows: [row(1, { yeas: 2, nays: 0 })], at: "2027-01-07T15:02:00Z",
                          ballots: new Map([["2027-H-1", new Map([["11", "Y"], ["12", "Y"]])]]) }).file;
  const b = merge(a, { date: "2027-01-07", rows: [row(1, { yeas: 2, nays: 0 }), row(2, { yeas: 1, nays: 2 })],
                       at: "2027-01-07T15:04:00Z",
                       ballots: new Map([["2027-H-2", new Map([["13", "Y"], ["11", "N"], ["12", "N"]])]]) }).file;
  assert.deepEqual(b.members.H, ["11", "12", "13"]);
  assert.deepEqual(b.rollcalls.map(r => r.ballots), ["YY.", "NNY"]);
  assert.deepEqual(b.rollcalls.map(r => r.ballots_complete), [true, true]);
  // A set short of its tally is incomplete: the clerk is still keying it.
  const c = merge(b, { date: "2027-01-07", rows: [row(1, { yeas: 3, nays: 0 }), row(2, { yeas: 1, nays: 2 })],
                       at: "2027-01-07T15:06:00Z" }).file;
  assert.equal(c.rollcalls[0].ballots_complete, false, "the tally moved and the ballots did not");
});

test("a Senate tally with no roll call yet stands alone, and is attached the moment its roll call arrives", () => {
  const line = { body: "S", bill_as_recorded: "SB12", entered: "2027-01-01T10:00:00", order: 7,
                 line: "Ought to Pass, RC 15Y-8N, MA; 01/07/2027" };
  let f = merge(null, { date: "2027-01-07", lines: [line], at: "2027-01-07T14:21:00Z" }).file;
  assert.deepEqual(f.tallies.map(t => [t.bill, t.yeas, t.nays, t.outcome, t.rollcall, t.first_seen]),
                   [["2027-2028/SB12", 15, 8, "Motion Adopted", null, "2027-01-07T14:21:00Z"]]);
  const s = { id: "2027-S-3", year: 2027, body: "S", seq: 3, vote_date: "2027-01-07T00:00:00", bill_as_recorded: "SB12",
              yeas: 15, nays: 8, present: 0, absent: 1, question: "Ought to Pass", modified: "2027-01-08T09:12:00",
              user: "senclerk" };
  f = merge(f, { date: "2027-01-07", rows: [s], at: "2027-01-08T14:14:00Z" }).file;
  assert.equal(f.tallies[0].rollcall, "2027-S-3");
  assert.equal(f.tallies[0].first_seen, "2027-01-07T14:21:00Z", "the line's first_seen kept");
  assert.deepEqual(f.rollcalls[0].docket, { line: line.line, abbrev: "MA", outcome: "Motion Adopted" });
  assert.equal(f.rollcalls[0].taken, null, "the Senate's VoteDate is midnight: no time taken");
  assert.equal(f.rollcalls[0].saved, "2027-01-08T14:12:00Z");
  assert.equal(f.rollcalls[0].keyed_by, "clerk");
});

test("equal tallies on one bill with fewer roll calls saved than lines wait, rather than guess which is which", () => {
  const f = emptyFile("2027-01-07");
  f.rollcalls = [{ ...row(12, { body: "S", id: "2027-S-12" }), ballots: "", ballots_complete: false }];
  f.tallies = [{ body: "S", bill_as_recorded: "HB2", yeas: 190, nays: 171, order: 1, line: "Floor Amendment #1, AA, RC 190Y-171N" },
               { body: "S", bill_as_recorded: "HB2", yeas: 190, nays: 171, order: 2, line: "OTPA, RC 190Y-171N, MA" }];
  attach(f);
  assert.equal(f.rollcalls[0].docket, null, "S 11 is not saved yet: S 12 is not given the amendment's line");
  assert.ok(f.tallies.every(t => t.rollcall === null));
});

test("a 0-0 roll call whose ballots are all no vote recorded is not complete", () => {
  const m = merge(null, { date: "2027-01-07", rows: [row(1, { yeas: 0, nays: 0 })], at: "2027-01-07T15:02:00Z",
                          ballots: new Map([["2027-H-1", new Map([["11", "."], ["12", "."]])]]) });
  assert.equal(m.file.rollcalls[0].ballots_complete, false);
});

test("two equal tallies on one bill pair by order: statusorder against sequence", () => {
  const f = emptyFile("2027-01-07");
  f.rollcalls = [row(14), row(9)].map(r => ({ ...r, ballots: "", ballots_complete: false }));
  f.tallies = [{ body: "H", bill_as_recorded: "HB2", yeas: 190, nays: 171, order: 30, line: "second" },
               { body: "H", bill_as_recorded: "HB2", yeas: 190, nays: 171, order: 12, line: "first" }];
  attach(f);
  const by = Object.fromEntries(f.rollcalls.map(r => [r.seq, r.docket.line]));
  assert.deepEqual(by, { 9: "first", 14: "second" });
});

// ---- the states ---------------------------------------------------------------
const streams = (status, over = {}) => ({ status: { ok: true }, next_check: "2027-01-07T15:04:00Z", streams: [
  { video: "x", chamber: "H", title: "House Session (01/07/2027)", status, scheduled: "2027-01-07T15:00:00Z", ...over }] });

test("hot: the session stream live, or about to start, or a roll call first seen in the last 45 minutes", () => {
  const now = at("2027-01-07T15:02:00Z");
  assert.equal(chamberState(now, "H", {}, streams("live")).state, "hot");
  assert.equal(chamberState(now, "S", {}, streams("live")).state, "heartbeat", "the House's stream is not the Senate's");
  assert.equal(chamberState(at("2027-01-07T14:46:00Z"), "H", {}, streams("upcoming")).state, "hot", "14 minutes before");
  assert.equal(chamberState(at("2027-01-07T14:44:00Z"), "H", {}, streams("upcoming")).state, "heartbeat");
  assert.equal(chamberState(now, "H", {}, streams("live", { title: "House Finance (01/07/2027)" })).state, "heartbeat");
  const sq = { chambers: { H: { last_rc: "2027-01-07T14:20:00Z" } } };
  assert.equal(chamberState(now, "H", sq).state, "hot", "votes without YouTube");
  assert.equal(chamberState(at("2027-01-07T15:06:00Z"), "H", sq).state, "heartbeat", "46 minutes on");
});

test("warm: five hours after hot, never past midnight; heartbeat's hours and season; quiet otherwise", () => {
  const sq = { chambers: { H: { last_hot: "2027-01-08T01:00:00Z", hot_day: "2027-01-07" } } };  // 20:00 EST
  assert.equal(chamberState(at("2027-01-08T04:58:00Z"), "H", sq).state, "warm", "23:58");
  assert.equal(chamberState(at("2027-01-08T05:00:00Z"), "H", sq).state, "off", "00:00: never past 23:59");
  const early = { chambers: { H: { last_hot: "2027-01-07T15:00:00Z", hot_day: "2027-01-07" } } };
  assert.equal(chamberState(at("2027-01-07T19:58:00Z"), "H", early).state, "warm");
  assert.equal(chamberState(at("2027-01-07T20:00:00Z"), "H", early).state, "heartbeat", "five hours on, before 18:00");
  // The heartbeat: weekdays, from the night's window's end to 18:00, January to June.
  assert.equal(chamberState(at("2027-01-07T13:28:00Z"), "H", {}).state, "off", "08:28 EST: the night's window");
  assert.equal(chamberState(at("2027-01-07T13:30:00Z"), "H", {}).state, "heartbeat", "08:30 EST");
  assert.equal(chamberState(at("2027-04-07T13:28:00Z"), "H", {}).state, "off", "09:28 EDT");
  assert.equal(chamberState(at("2027-04-07T13:30:00Z"), "H", {}).state, "heartbeat", "09:30 EDT");
  assert.equal(chamberState(at("2027-01-07T22:58:00Z"), "H", {}).state, "heartbeat", "17:58");
  assert.equal(chamberState(at("2027-01-07T23:00:00Z"), "H", {}).state, "off", "18:00");
  assert.equal(chamberState(at("2027-01-09T16:00:00Z"), "H", {}).state, "off", "a Saturday");
  assert.equal(chamberState(at("2027-07-14T16:00:00Z"), "H", {}).state, "off", "July");
  const veto = { chambers: { S: { hot_day: "2027-09-15" } } };
  assert.equal(chamberState(at("2027-09-29T16:00:00Z"), "S", veto).state, "heartbeat", "14 days after a hot day");
  assert.equal(chamberState(at("2027-09-30T16:00:00Z"), "S", veto).state, "off", "15");
  assert.equal(chamberState(at("2027-09-15T23:30:00Z"), "S", veto).state, "off", "not the hot day itself, after 18:00");
});

test("inside the night's window only a live session stream reads: not warm, not heartbeat, not a recent roll call", () => {
  const inWindow = at("2027-01-07T13:00:00Z");           // 08:00 EST, inside 08:00-13:30 UTC
  assert.equal(chamberState(inWindow, "H", {}, { ...streams("live"), next_check: "2027-01-07T13:02:00Z" }).state, "hot");
  assert.equal(chamberState(inWindow, "H", { chambers: { H: { last_rc: "2027-01-07T12:50:00Z" } } }).state, "off");
  assert.equal(chamberState(inWindow, "H", { chambers: { H: { last_hot: "2027-01-07T12:00:00Z" } } }).state, "off");
  // Monday's weekly window never meets a reading state.
  assert.equal(chamberState(at("2027-01-11T05:00:00Z"), "H", {}).state, "off");
});

test("a stale or failed streams file is not believed", () => {
  const f = streams("live");
  assert.ok(freshStreams(f, at("2027-01-07T15:09:00Z")));
  assert.equal(freshStreams(f, at("2027-01-07T15:09:01Z")), null);
  assert.equal(freshStreams({ ...f, status: { ok: false } }, at("2027-01-07T15:02:00Z")), null);
  assert.equal(sessionLive(null, "H", at("2027-01-07T15:02:00Z")), false);
});

test("what a run reads: hot every run, wide every 10 minutes; warm every 10 with Q3; heartbeat every 15, Q1 alone", () => {
  const hot = { chambers: { H: { last_rc: "2027-01-07T15:00:00Z" } }, read: "2027-01-07T15:00:00Z", wide: "2027-01-07T14:55:00Z" };
  let d = votesDue(at("2027-01-07T15:02:00Z"), hot);
  assert.deepEqual([d.read, d.why, d.wide, d.q3], [true, "hot", false, true]);
  assert.equal(votesDue(at("2027-01-07T15:04:00Z"), hot).wide, false, "9 minutes on");
  d = votesDue(at("2027-01-07T15:06:00Z"), hot);
  assert.deepEqual([d.read, d.wide], [true, true], "the wide read, the first run 10 minutes on");
  assert.equal(votesDue(new Date(T("2027-01-07T15:05:00Z") - 5_000), hot).wide, true, "a cron 5 s early is on time");
  const slow = { ...hot, q3: "2027-01-07T15:00:00Z", q3_ms: 1500 };
  assert.equal(votesDue(at("2027-01-07T15:02:00Z"), slow).q3, false, "Q3 over 1 s: one hot run in five");
  assert.equal(votesDue(at("2027-01-07T15:10:00Z"), slow).q3, true);
  const warm = { chambers: { H: { last_hot: "2027-01-07T15:00:00Z" } }, read: "2027-01-07T15:52:00Z" };
  assert.equal(votesDue(at("2027-01-07T15:58:00Z"), warm).read, false);
  d = votesDue(at("2027-01-07T16:02:00Z"), warm);
  assert.deepEqual([d.read, d.why, d.wide, d.q3], [true, "warm", true, true]);
  const beat = { read: "2027-01-07T16:00:00Z" };
  assert.equal(votesDue(at("2027-01-07T16:14:00Z"), beat).read, false, "14 minutes: not yet");
  d = votesDue(at("2027-01-07T16:16:00Z"), beat);
  assert.deepEqual([d.read, d.why, d.wide, d.q3], [true, "heartbeat", true, false]);
  assert.equal(votesDue(at("2027-01-09T16:14:00Z"), beat).read, false, "a quiet Saturday reads nothing");
  assert.equal(nextRead(at("2027-01-07T15:02:00Z"), votesDue(at("2027-01-07T15:02:00Z"), hot).states),
               "2027-01-07T15:04:00Z");
  assert.equal(nextRead(at("2027-01-09T15:02:00Z"), votesDue(at("2027-01-09T15:02:00Z"), {}).states), null);
  assert.deepEqual(EVERY, { hot: 2 * MIN, warm: 10 * MIN, heartbeat: 15 * MIN, wide: 10 * MIN, q3slow: 10 * MIN,
                            q2retry: 10 * MIN });
});

test("ballots: new and changed first, at most 20, an incomplete set twice and then every 10 minutes, nothing past 14 days", () => {
  const now = at("2027-01-07T15:00:00Z");
  const need = {};
  for (let i = 1; i <= 25; i++) need[`2027-H-${i}`] = { body: "H", seq: i, day: "2027-01-07", tries: 0, last: null };
  need["2027-H-90"] = { body: "H", seq: 90, day: "2027-01-07", tries: Q2_TRIES, last: "2027-01-07T14:55:00Z" };
  need["2027-H-91"] = { body: "H", seq: 91, day: "2027-01-07", tries: Q2_TRIES, last: "2027-01-07T14:50:00Z" };
  need["2026-H-5"] = { body: "H", seq: 5, day: "2026-12-23", tries: 0, last: null };
  const got = ballotsDue(now, need, "2027-01-07").map(x => x.id);
  assert.equal(got.length, 20);
  assert.ok(!got.includes("2026-H-5"), "15 days back");
  const later = ballotsDue(now, Object.fromEntries(Object.entries(need).filter(([, n]) => n.tries)), "2027-01-07");
  assert.deepEqual(later.map(x => x.id), ["2027-H-91"], "two tries, then every 10 minutes");
});

// ---- holds --------------------------------------------------------------------------
test("connection holds: three in a row hold 30 minutes, then one try, failing again holds the day; a success resets", () => {
  const now = at("2027-01-07T15:00:00Z");
  let sq = {};
  for (let i = 1; i <= 2; i++) { sq = _failedConnect(sq, "connect", now); assert.equal(sq.held, undefined, `${i}`); }
  sq = _failedConnect(sq, "database", now);
  assert.deepEqual([sq.held.why, sq.held.until, sq.held.stage], ["connect", "2027-01-07T15:30:00Z", 1], "4060 counts here");
  assert.equal(votesDue(at("2027-01-07T15:20:00Z"), { ...sq, chambers: { H: { last_rc: "2027-01-07T15:00:00Z" } } }).read, false);
  sq = _failedConnect(sq, "connect", at("2027-01-07T15:30:00Z"));
  assert.deepEqual([sq.held.stage, sq.held.until], [2, "2027-01-08T05:00:00Z"], "the one try failed: the day");
  for (const code of ["encrypt", "version", "guard"]) {
    const h = _failedConnect({}, code, now).held;
    assert.deepEqual([h.why, h.until], [code === "version" ? "encrypt" : code, "2027-01-08T05:00:00Z"], code);
  }
});

test("a refused login holds the day, and lifts at once when the published login changes", async () => {
  const now = at("2027-01-07T15:00:00Z");
  const sq = _failedConnect({}, "login", now, await loginPrint());
  assert.equal(sq.held.until, "2027-01-08T05:00:00Z");
  assert.equal((await liftHolds(sq, now)).held, sq.held, "the same login: held");
  const other = { ...sq, held: { ...sq.held, print: await loginPrint({ database: "NHLegislatureDB", user: "publicuser", password: "old" }) } };
  assert.equal((await liftHolds(other, now)).held, null, "the published login changed: lifted");
});

test("the day's budget: 600 connections, 1,200 statements or 150,000 rows", () => {
  assert.deepEqual({ ...BUDGET }, { connections: 600, statements: 1200, rows: 150_000 });
  assert.equal(overBudget({ connections: 599, statements: 1199, rows: 149_999 }), false);
  for (const k of ["connections", "statements", "rows"]) assert.equal(overBudget({ [k]: BUDGET[k] }), true, k);
});

test("held, a run reads nothing, whatever the chambers' states", () => {
  const sq = { held: { why: "budget", until: "2027-01-08T05:00:00Z" }, chambers: { H: { last_rc: "2027-01-07T15:00:00Z" } } };
  const d = votesDue(at("2027-01-07T15:02:00Z"), sq, streams("live"));
  assert.equal(d.read, false);
  assert.equal(d.held.why, "budget");
  assert.equal(votesDue(at("2027-01-08T15:02:00Z"), sq, { ...streams("live"), next_check: "2027-01-08T15:04:00Z",
    streams: [{ video: "x", chamber: "H", title: "House Session (01/08/2027)", status: "live" }] }).read, true,
               "it ends with the day");
});

test("section 7.3's measurement: House lines entered on their roll call's day, Senate lines carrying it, against 95%", async () => {
  const { measure, report } = await import("./measure_docket.mjs");
  const { SUMMARY } = await import("./from_records.js");
  const docket = ["2026|0001|3/11/2026 9:32:51 AM|HB1376|H|OTPA: MA RC 171-143 03/11/2026 HJ 8 P. 20|3/11/2026 9:32:51 AM",
                  "2026|0002|1/19/2026 10:00:00 AM|HB751|S|Ought to Pass, RC 16Y-8N, MA; 01/29/2026|1/19/2026 10:00:00 AM",
                  "2026|0003|3/11/2026 9:40:00 AM|HB1400|H|Special Order to RC|3/11/2026 9:40:00 AM"].join("\n");
  let m = measure(docket, SUMMARY, ["2026"]);
  assert.deepEqual(m, { H: { lines: 1, matched: 1, onDay: 1 }, S: { lines: 1, matched: 1, dated: 1 } });
  assert.equal(report(m).ok, true);
  m = measure(docket.replace("2026|0001|3/11/2026 9:32:51 AM", "2026|0001|3/12/2026 9:32:51 AM"), SUMMARY, ["2026"]);
  assert.equal(m.H.onDay, 0);
  assert.equal(report(m).ok, false);
  assert.match(report(m).said.at(-1), /widen Q3's text test/);
});

test("the miss count starts over when a roll call is listed again, across reads as readVotes carries it", () => {
  let misses = {}, file = merge(null, { date: "2027-01-07", rows: [row(1)], at: "2027-01-07T15:00:00Z", covered: true }).file;
  const read = (rows, t) => { const m = merge(file, { date: "2027-01-07", rows, at: t, covered: true, misses });
                              file = m.file; misses = m.misses; };
  read([], "2027-01-07T15:02:00Z");
  read([], "2027-01-07T15:04:00Z");
  read([row(1)], "2027-01-07T15:06:00Z");
  assert.equal(misses["2027-H-1"], undefined);
  read([], "2027-01-07T15:08:00Z");
  assert.equal(file.rollcalls[0].note, null, "one miss after being listed again is not three in a row");
});

// ---- the load review's findings, as tests ------------------------------------------
import { nodeConnect, startFakeTds } from "./fake_tds.js";
import { fromRecords } from "./from_records.js";
import { Q3_FAILED_MS, readVotes } from "../../workers/live/votes.js";

const local = port => ({ SQL_HOST: "127.0.0.1", SQL_PORT: String(port) });
const hotDue = (now, sq = {}) => votesDue(now, { ...sq, chambers: { H: { last_rc: new Date(+now - MIN).toISOString() } } });

test("a Q3 that never answers: Q2 has already run, the server is sent its cancel, and Q3 slows to one hot run in five", async () => {
  const base = fromRecords();
  const fake = await startFakeTds({ answer: (sql, n) => (/FROM Docket d/.test(sql) ? { silent: true } : base(sql, n)) });
  try {
    const now = at("2026-03-11T19:00:00Z");
    const due = hotDue(now);
    const r = await readVotes({ env: local(fake.port), connect: nodeConnect, now, due, files: async () => null,
                                until: Date.now() + 1500 });
    const order = fake.seen.batches.map(b => (/RollCallHistory/.test(b) ? "q2" : /Docket/.test(b) ? "q3" : "q1"));
    assert.deepEqual(order, ["q1", "q2", "q3"], "ballots before the docket");
    await new Promise(ok => setTimeout(ok, 300));
    assert.ok(fake.seen.packets.some(p => p.type === 0x06), "an ATTENTION packet: the server stops the scan");
    assert.equal(r.sq.q3_ms, Q3_FAILED_MS);
    assert.equal(votesDue(at("2026-03-11T19:02:00Z"), { ...r.sq, chambers: { H: { last_rc: "2026-03-11T19:01:00Z" } } }).q3, false);
    assert.ok(r.writes.some(([k]) => k === "votes/2026-03-11.json"), "what Q1 and Q2 read is still written");
  } finally { await fake.close(); }
});

test("a heartbeat run reads Q1 alone, ballots waiting or not", async () => {
  const fake = await startFakeTds({ answer: fromRecords() });
  try {
    const now = at("2026-03-12T15:00:00Z");
    const sq = { need: { "2026-H-150": { body: "H", seq: 150, day: "2026-03-11", tries: 0, last: null } } };
    const due = votesDue(now, sq);
    assert.equal(due.why, "heartbeat");
    await readVotes({ env: local(fake.port), connect: nodeConnect, now, sq, due, files: async () => null,
                      until: Date.now() + 10_000 });
    assert.equal(fake.seen.batches.length, 1);
    assert.match(fake.seen.batches[0], /FROM RollCallSummary/);
  } finally { await fake.close(); }
});

test("a scheduled session stream that never starts stops counting an hour after its time; inside the night's window only a live one reads", () => {
  const upcoming = (now) => ({ status: { ok: true }, next_check: new Date(+now + 2 * MIN).toISOString(), streams: [
    { video: "x", chamber: "S", title: "Senate Session (11/12/2026)", status: "upcoming", scheduled: "2026-11-12T15:00:00Z" }] });
  for (const [t, want] of [["2026-11-12T15:58:00Z", "hot"], ["2026-11-12T16:02:00Z", "off"]]) {
    assert.equal(chamberState(at(t), "S", {}, upcoming(at(t))).state, want, t);
  }
  // 08:46 EDT, inside the window: scheduled for 09:00, not yet live.
  const t = at("2026-04-08T12:46:00Z");
  const f = { status: { ok: true }, next_check: "2026-04-08T12:48:00Z", streams: [
    { video: "y", chamber: "H", title: "House Session (04/08/2026)", status: "upcoming", scheduled: "2026-04-08T13:00:00Z" }] };
  assert.equal(chamberState(t, "H", {}, f).state, "off");
  f.streams[0].status = "live";
  assert.equal(chamberState(t, "H", {}, f).state, "hot");
});
