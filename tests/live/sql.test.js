// The live Worker's statements (workers/live/sql.js), and the November test
// (workers/live/test_mode.js) end to end: a fake SQL Server on the loopback
// address answers Q1 and Q2 from records/rollcalls/ in git and Q3 from a few
// docket lines written here, the test writes its file, and compare_test.mjs
// finds it equal to the record -- or, changed, not. preflight runs this file
// (_live_tds).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { MAX_ROLLCALLS, Q1, Q2, Q2_CHAMBER, Q3, VERSION, WIDTH, addDays, fill, lit, q1, q2, q3, readBallots,
         readDocket, readSummary, readVersion } from "../../workers/live/sql.js";
import { SQL_BUDGET_MS, TEST_HOURS, TEST_SITTINGS, nhToUtc, runTest, termOf, testDue } from "../../workers/live/test_mode.js";
import { BALLOT_CHAR, VOTE_WORD } from "../../workers/live/live.gen.js";
import { nodeConnect, startFakeTds, text } from "./fake_tds.js";
import { CHAR_OF_WORD, compare, compareDocket, recordTime } from "./compare_test.mjs";

// ---- the statements ------------------------------------------------------------
const LITERAL = /'(?:[^']|'')*'/g;
const ALLOWED = /^(?:''|'%RC \[0-9\]%'|'\d{8}'|'%\d\d\/\d\d\/\d{4}%'|'[HS]')$/;

function shapely(sql) {
  assert.ok(sql.startsWith("SELECT "), sql.slice(0, 40));
  assert.doesNotMatch(sql, /;|--|\/\*|\*\/|\*|\{|\}/, "no statement end, comment, star or unfilled place");
  for (const l of sql.match(LITERAL) || []) assert.match(l, ALLOWED, `the literal ${l}`);
}

test("Q1 asks for a window of days with 'YYYYMMDD' dates", () => {
  const sql = q1({ year: 2026, from: "2026-02-25", until: "2026-03-12" });
  shapely(sql);
  assert.match(sql, /WHERE s\.SessionYear = 2026 AND s\.VoteDate >= '20260225' AND s\.VoteDate < '20260312'\n/);
});

test("Q2 asks for each chamber's roll calls, sorted, at most 20 in all", () => {
  const both = q2({ year: 2027, rollcalls: [{ body: "H", seq: 15 }, { body: "S", seq: 3 }, { body: "H", seq: 14 },
                                            { body: "H", seq: 14 }] });
  shapely(both);
  assert.ok(both.endsWith("WHERE h.SessionYear = 2027\n  AND ((h.LegislativeBody = 'H' AND h.VoteSequenceNumber IN (14,15))"
                          + " OR (h.LegislativeBody = 'S' AND h.VoteSequenceNumber IN (3)))"), both);
  const senate = q2({ year: 2027, rollcalls: [{ body: "S", seq: 9 }] });
  assert.ok(senate.endsWith("AND ((h.LegislativeBody = 'S' AND h.VoteSequenceNumber IN (9)))"), senate);
  const twenty = Array.from({ length: MAX_ROLLCALLS }, (_, i) => ({ body: "H", seq: i + 1 }));
  shapely(q2({ year: 2027, rollcalls: twenty }));
  for (const bad of [[...twenty, { body: "S", seq: 1 }], [], [{ body: "X", seq: 1 }], [{ body: "H", seq: "14" }],
                     [{ body: "H", seq: -1 }], [{ body: "H", seq: 1.5 }], [{ body: "H", seq: "1) OR (1=1" }]]) {
    assert.throws(() => q2({ year: 2027, rollcalls: bad }), RangeError, JSON.stringify(bad));
  }
});

test("Q3 takes lines entered on the day, or in the 21 days before with the day's date in their words", () => {
  const sql = q3({ year: 2026, day: "2026-03-11" });
  shapely(sql);
  assert.match(sql, /\(d\.StatusDate >= '20260311' AND d\.StatusDate < '20260312'\)/);
  assert.match(sql, /\(d\.StatusDate >= '20260218' AND d\.Description LIKE '%03\/11\/2026%'\)/);
  assert.match(sql, /d\.Description LIKE '%RC \[0-9\]%'/, "RC only before a digit: bare RC is Regular Calendar");
  const turn = q3({ year: 2027, day: "2027-01-07" });
  assert.match(turn, /'20261217'/);
  assert.match(turn, /'20270108'/);
});

test("a value reaches a statement only through lit(): whole numbers, real dates, H or S", () => {
  assert.equal(lit("int", 0), "0");
  assert.equal(lit("ints", [3, 14]), "3,14");
  assert.equal(lit("day", "2027-01-07"), "'20270107'");
  assert.equal(lit("mdy", "2027-01-07"), "'%01/07/2027%'");
  assert.equal(lit("body", "S"), "'S'");
  for (const [kind, v] of [["int", "2026"], ["int", -1], ["int", 1.5], ["int", NaN], ["int", 2 ** 60], ["ints", []],
                           ["day", "2026-02-30"], ["day", "2026-3-11"], ["day", "2026-03-11'; DROP TABLE x"],
                           ["mdy", "11/03/2026"], ["body", "h"], ["body", "'H'"], ["text", "anything"]]) {
    assert.throws(() => lit(kind, v), RangeError, `${kind} ${String(v)}`);
  }
  assert.throws(() => fill(Q1, { Y: ["int", 2026], FIRST: ["day", "2026-03-11"] }), /no value for \{UNTIL\}/);
  assert.throws(() => fill(Q2_CHAMBER, { BODY: ["body", "H"], SEQS: ["ints", [1]], Y: ["int", 1] }), /no place for Y/);
  for (const t of [Q1, Q2, Q3, Q2_CHAMBER]) assert.equal(t.match(/'(?:[^']|'')*'/g)?.filter(l => !ALLOWED.test(l)).length ?? 0, 0);
  assert.equal(VERSION, "SELECT @@VERSION");
  assert.equal(addDays("2026-03-01", -1), "2026-02-28");
});

test("each reader takes its statement's width, and refuses a row that is not the shape asked for", () => {
  const q1row = ["H", "14", "2026-03-11T09:23:27", "HB1376", "190", "171", "0", "39", "OTP", "", "VOTE SYSTEM"];
  const [r] = readSummary({ columns: Array(WIDTH.q1).fill(""), rows: [q1row] }, 2026);
  assert.deepEqual(r, { id: "2026-H-14", year: 2026, body: "H", seq: 14, vote_date: "2026-03-11T09:23:27",
                        bill_as_recorded: "HB1376", yeas: 190, nays: 171, present: 0, absent: 39, question: "OTP",
                        modified: null, user: "VOTE SYSTEM" });
  const day = readSummary({ columns: Array(11).fill(""), rows: [[...q1row.slice(0, 2), "2026-03-11", ...q1row.slice(3)]] }, 2026);
  assert.equal(day[0].vote_date, "2026-03-11T00:00:00");
  const bad = (i, v) => { const x = [...q1row]; x[i] = v; return { columns: Array(11).fill(""), rows: [x] }; };
  for (const [i, v] of [[0, "X"], [1, "1a"], [2, "2026-13-01T00:00:00"], [4, "-3"], [9, "yesterday"], [0, null]]) {
    assert.throws(() => readSummary(bad(i, v), 2026), e => e.code === "shape", `${i} ${v}`);
  }
  assert.throws(() => readSummary({ columns: Array(10).fill(""), rows: [] }, 2026), e => e.code === "shape");
  assert.deepEqual(readBallots({ columns: Array(4).fill(""), rows: [["S", "3", "960", "6"], ["H", "14", "11463", "0"]] }),
                   [{ body: "S", seq: 3, member: "960", vote: "P" }, { body: "H", seq: 14, member: "11463", vote: "." }]);
  for (const row of [["H", "1", "960", "9"], ["H", "1", "", "1"], ["H", "1", "9 60", "1"], ["H", "1", "960", null]]) {
    assert.throws(() => readBallots({ columns: Array(4).fill(""), rows: [row] }), e => e.code === "shape", String(row));
  }
  assert.deepEqual(readDocket({ columns: Array(5).fill(""), rows: [["S", "SB12", "2027-01-07T10:01:02", "5", "RC 15Y-8N"]] }),
                   [{ body: "S", bill_as_recorded: "SB12", entered: "2027-01-07T10:01:02", order: 5, line: "RC 15Y-8N" }]);
  assert.equal(readVersion({ columns: [""], rows: [["Microsoft SQL Server 2019"]] }), "Microsoft SQL Server 2019");
});

test("a ballot's code is the live file's character as the design's section 2.5 has it, written out here", () => {
  // Y Yea, N Nay, E excused, X not excused, P presiding, . no vote recorded:
  // codes 1, 2, 3, 4 and 6 the first five, and 0, 5 and 7 the last.
  assert.deepEqual(BALLOT_CHAR, { 0: ".", 1: "Y", 2: "N", 3: "E", 4: "X", 5: ".", 6: "P", 7: "." });
  // compare_test.mjs's own table, from the record's words, says the same.
  for (const [code, word] of Object.entries(VOTE_WORD)) assert.equal(CHAR_OF_WORD[word], BALLOT_CHAR[code], word);
});

test("New Hampshire's clock as UTC, and the term a session year is in", () => {
  assert.equal(nhToUtc("2026-03-11T09:23:27"), "2026-03-11T13:23:27Z");
  assert.equal(nhToUtc("2027-01-07T10:00:00"), "2027-01-07T15:00:00Z");
  assert.equal(nhToUtc("2026-03-08T02:30:00"), null, "the hour the spring change skips");
  assert.equal(nhToUtc(null), null);
  assert.equal(termOf(2026), "2025-2026");
  assert.equal(termOf(2027), "2027-2028");
});

// ---- the November test, end to end ------------------------------------------------
const RECORDS = new URL("../../records/rollcalls/", import.meta.url);
const fields = name => readFileSync(new URL(name, RECORDS), "utf8").replace(/^﻿/, "").split(/\r?\n/)
  .filter(Boolean).map(l => l.split("|"));
const SUMMARY = fields("RollCallSummary_2026.txt");
const HISTORY = fields("RollCallHistory_2026.txt");
const CODE = Object.fromEntries(Object.entries(VOTE_WORD).map(([code, word]) => [word, code]));
const ymd = s => `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;

// Docket lines in the recorded forms, two that Q3 must take and three it must not.
const DOCKET = [
  ["H", "HB1376", "2026-03-11T09:32:51", "12", "OTPA: MA RC 171-143 03/11/2026 HJ 8 P. 20", true],
  ["S", "SB501", "2026-03-01T10:00:00", "7", "Ought to Pass, RC 16Y-8N, MA; 03/11/2026", true],
  ["S", "SB502", "2026-02-17T10:00:00", "3", "Ought to Pass, RC 15Y-9N, MA; 03/11/2026", false],
  ["H", "HB1378", "2026-03-10T15:00:00", "9", "OTP: MA RC 175-149 03/10/2026", false],
  ["H", "HB1400", "2026-03-11T11:00:00", "4", "Special Order to RC", false],
];

// The fake's answers: the record for Q1 and Q2, the lines above for Q3, each
// filtered by the literals the statement carries.
function fromRecords(over = {}) {
  return (sql) => {
    if (sql === VERSION) {
      return over.version || { columns: text(""), rows: [["Microsoft SQL Server 2019 (RTM) - 15.0.2000.5 (X64) (a fake)"]] };
    }
    let m = /FROM RollCallSummary s\nWHERE s\.SessionYear = (\d+) AND s\.VoteDate >= '(\d{8})' AND s\.VoteDate < '(\d{8})'\n/.exec(sql);
    if (m) {
      if (over.q1) return over.q1;
      const [, y, from, until] = m;
      const rows = SUMMARY.filter(f => f[0] === y && recordTime(f[3]).slice(0, 10) >= ymd(from)
                                  && recordTime(f[3]).slice(0, 10) < ymd(until))
        .map(f => [f[1], f[2], recordTime(f[3]), f[4], f[5], f[6], f[7], f[8], f[11], recordTime(f[14]) || "",
                   f[1] === "H" ? "VOTE SYSTEM" : "senclerk"]);
      return { columns: text(...Array(11).fill("")), rows };
    }
    m = /FROM RollCallHistory h LEFT JOIN legislators l ON l\.Employeeno = h\.EmployeeNumber\nWHERE h\.SessionYear = (\d+)\n  AND \((.*)\)$/s.exec(sql);
    if (m) {
      const asked = new Set();
      for (const c of m[2].matchAll(/\(h\.LegislativeBody = '([HS])' AND h\.VoteSequenceNumber IN \(([\d,]+)\)\)/g)) {
        for (const s of c[2].split(",")) asked.add(`${c[1]}-${s}`);
      }
      const rows = HISTORY.filter(f => f[0] === m[1] && asked.has(`${f[1]}-${f[2]}`))
        .map(f => [f[1], f[2], f[4] || f[3], CODE[f[6]]]);
      return { columns: text("", "", "", ""), rows };
    }
    m = /WHERE d\.SessionYear = (\d+) AND d\.Description LIKE '%RC \[0-9\]%'\n  AND \(   \(d\.StatusDate >= '(\d{8})' AND d\.StatusDate < '(\d{8})'\)\n       OR \(d\.StatusDate >= '(\d{8})' AND d\.Description LIKE '%(\d\d\/\d\d\/\d{4})%'\)\)/.exec(sql);
    if (m) {
      if (over.q3) return over.q3;
      const [, , day, next, since, mdy] = m;
      const rows = DOCKET.filter(([, , at, , line]) => /RC [0-9]/.test(line)
          && ((at.slice(0, 10) >= ymd(day) && at.slice(0, 10) < ymd(next)) || (at.slice(0, 10) >= ymd(since) && line.includes(mdy))))
        .map(([b, bill, at, order, line]) => [b, bill, at, order, line]);
      return { columns: text("", "", "", "", ""), rows };
    }
    return { error: { number: 102, message: "Incorrect syntax: the fake knows the live Worker's statements alone" } };
  };
}

const env = port => ({ SQL_HOST: "127.0.0.1", SQL_PORT: String(port) });
const WED = new Date("2026-11-18T15:30:00Z");                   // 10:30 in New Hampshire
const THU = new Date("2026-11-19T15:30:00Z");
const FRI = new Date("2026-11-20T15:30:00Z");
const DAY2 = { done: ["2026-03-11"], last: "2026-11-18" };

// The test's file for a sitting, read once from a fake answering from the
// record, for the tests below to change a copy of.
const files = new Map();
function sitting(now, test) {
  const key = `${now.toISOString()} ${JSON.stringify(test)}`;
  if (!files.has(key)) {
    files.set(key, (async () => {
      const fake = await startFakeTds({ answer: fromRecords() });
      try {
        return (await runTest(env(fake.port), { connect: nodeConnect, now, test })).file;
      } finally {
        await fake.close();
      }
    })());
  }
  return files.get(key).then(f => structuredClone(f));
}

// A copy of a test file with every statement's time set to 0: the data are
// compared apart from the clock, which on a busy machine runs a fake's Q2 past
// 2 s. The time rule has a test of its own.
function untimed(file) {
  const f = structuredClone(file);
  for (const s of f.test.statements) if (s.ms !== null) s.ms = 0;
  return f;
}

test("the test runs on weekdays between 10:00 and 16:00 in New Hampshire, once a day", () => {
  assert.deepEqual(TEST_HOURS, [10, 16]);
  assert.deepEqual(TEST_SITTINGS, ["2026-03-11", "2026-08-19"]);
  assert.deepEqual(testDue(WED, {}), { kind: "sitting", day: "2026-03-11", today: "2026-11-18" });
  assert.equal(testDue(new Date("2026-11-18T14:59:00Z"), {}), null, "09:59 EST");
  assert.equal(testDue(new Date("2026-11-18T21:00:00Z"), {}), null, "16:00 EST");
  assert.ok(testDue(new Date("2026-07-15T14:00:00Z"), {}), "10:00 EDT");
  assert.equal(testDue(new Date("2026-07-15T20:00:00Z"), {}), null, "16:00 EDT");
  assert.equal(testDue(new Date("2026-11-21T15:30:00Z"), {}), null, "a Saturday");
  assert.equal(testDue(WED, { last: "2026-11-18" }), null, "one connection a day");
  assert.deepEqual(testDue(WED, { done: ["2026-03-11"] }).day, "2026-08-19");
  assert.deepEqual(testDue(WED, { done: TEST_SITTINGS }), { kind: "login", today: "2026-11-18" });
});

test("day 1 reads 11 March 2026 in one connection, Q2 in three statements, and the record agrees ballot for ballot", async () => {
  const fake = await startFakeTds({ answer: fromRecords() });
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: {} });
    assert.equal(got.key, "test/2026-03-11.json");
    assert.deepEqual(got.test, { done: ["2026-03-11"], last: "2026-11-18" });
    assert.equal(fake.seen.connections, 1);
    const asked = fake.seen.batches;
    assert.equal(asked[0], VERSION);
    assert.equal(asked[1], q1({ year: 2026, from: "2026-03-11", until: "2026-03-12" }));
    assert.equal(asked[2], q3({ year: 2026, day: "2026-03-11" }));
    assert.equal(asked.length, 6, "the version, Q1, Q3 and three Q2s");
    for (const sql of asked.slice(3)) {
      const n = [...sql.matchAll(/IN \(([\d,]+)\)/g)].reduce((k, x) => k + x[1].split(",").length, 0);
      assert.ok(n >= 1 && n <= MAX_ROLLCALLS, `${n} roll calls in one Q2`);
    }

    const f = got.file;
    assert.equal(f.kind, "session.votes");
    assert.equal(f.date, "2026-03-11");
    assert.equal(f.status.problem, null);
    assert.deepEqual(f.test.statements.map(s => [s.name, s.problem]),
                     [["version", null], ["q1", null], ["q3", null], ["q2 1", null], ["q2 2", null], ["q2 3", null]]);
    assert.ok(f.test.statements.every(s => s.ms >= 0 && s.bytes > 0));
    assert.equal(f.test.connection.prelogin.encryption, "NOT_SUP");
    assert.match(f.test.version, /Microsoft SQL Server/);
    assert.equal(f.rollcalls.length, 56);
    assert.ok(f.rollcalls.every(r => r.body === "H" && r.ballots_complete && r.keyed_by === "voting system"));
    const first = f.rollcalls.find(r => r.seq === 134);
    assert.equal(first.bill, "2025-2026/HB1376");
    assert.equal(first.taken, "2026-03-11T13:28:32Z");
    assert.deepEqual(f.test.docket.map(d => d.bill_as_recorded), ["HB1376", "SB501"]);

    const c = compare(untimed(f));
    assert.ok(c.ok, c.said.join("\n"));
    const ballots = HISTORY.filter(x => x[1] === "H" && f.rollcalls.some(r => r.seq === Number(x[2]))
                                    && CODE[x[6]] !== "0" && CODE[x[6]] !== "7").length;
    assert.deepEqual(c.counts, { rollcalls: 56, ballots });
    assert.ok(ballots > 20000, `${ballots} ballots`);

    const docket = DOCKET.map(([b, bill, at, , line]) => {
      const t = recordAs(at);
      return `2026|1234|${t}|${bill}|${b}|${line}|${t}`;
    }).join("\n");
    const d = compareDocket(f, docket);
    assert.ok(d.ok, d.said.join("\n"));

    assert.equal(await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: got.test }), null,
                 "a second run that day asks nothing");
    assert.equal(fake.seen.connections, 1);
  } finally {
    await fake.close();
  }
});

function recordAs(iso) {
  const [d, t] = iso.split("T");
  const [y, m, day] = d.split("-").map(Number);
  let [h, min, s] = t.split(":");
  h = Number(h);
  return `${m}/${day}/${y} ${h % 12 || 12}:${min}:${s} ${h < 12 ? "AM" : "PM"}`;
}

test("day 2 reads veto day, 19 August 2026, both chambers, the Senate's saves of the next morning with it", async () => {
  const fake = await startFakeTds({ answer: fromRecords() });
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: THU, test: DAY2 });
    assert.equal(got.key, "test/2026-08-19.json");
    assert.deepEqual(got.test.done, ["2026-03-11", "2026-08-19"]);
    const f = got.file;
    const senate = f.rollcalls.filter(r => r.body === "S");
    assert.equal(f.rollcalls.length, 44);
    assert.equal(senate.length, 16);
    assert.ok(senate.every(r => r.taken === null && r.saved && r.saved.startsWith("2026-08-20")), "saved the next morning");
    assert.equal(fake.seen.batches.length, 6);
    const c = compare(untimed(f));
    assert.ok(c.ok, c.said.join("\n"));
  } finally {
    await fake.close();
  }
});

test("compare_test finds a changed ballot, a changed tally and a missing roll call", async () => {
  const f = untimed(await sitting(WED, {}));
  const r = f.rollcalls[3];
  const i = r.ballots.search(/[YN]/);
  r.ballots = r.ballots.slice(0, i) + (r.ballots[i] === "Y" ? "N" : "Y") + r.ballots.slice(i + 1);
  f.rollcalls[5].yeas += 1;
  const gone = f.rollcalls.shift().id;
  const c = compare(f);
  assert.equal(c.ok, false);
  const said = c.said.join("\n");
  assert.match(said, new RegExp(`${r.id} member ${f.members.H[i]}`));
  assert.match(said, new RegExp(`${f.rollcalls[4].id} yeas`));
  assert.match(said, new RegExp(`${gone} is in the record and not in the test file`));
});

test("compare_test finds each difference the go rests on, every one a no-go", async () => {
  const house = untimed(await sitting(WED, {}));
  const senate = untimed(await sitting(THU, DAY2));
  assert.ok(compare(house).ok && compare(senate).ok, "the files as read are a go");
  const differs = (change, from, rx) => {
    const f = structuredClone(from);
    change(f);
    const c = compare(f);
    assert.equal(c.ok, false, `not a no-go: ${rx}`);
    assert.match(c.said.join("\n"), rx);
    assert.match(c.said.at(-1), /^no-go/);
  };
  const [a, b] = house.rollcalls;
  for (const k of ["nays", "present", "absent"]) {
    differs(f => { f.rollcalls[0][k] += 1; }, house, new RegExp(`${a.id} ${k}: ${a[k] + 1}, the record ${a[k]}`));
  }
  differs(f => { f.rollcalls[1].bill_as_recorded = "HB9999"; }, house, new RegExp(`${b.id} bill: HB9999, the record`));
  differs(f => { f.rollcalls[0].taken = "2026-03-11T12:00:00Z"; }, house,
          new RegExp(`${a.id} taken: 2026-03-11T08:00:00, the record`));
  const s = senate.rollcalls.find(r => r.body === "S");
  differs(f => { f.rollcalls.find(r => r.id === s.id).saved = "2026-08-21T12:00:00Z"; }, senate,
          new RegExp(`${s.id} saved: 2026-08-21T08:00:00, the record 2026-08-20T`));
  differs(f => { f.rollcalls[1].ballots_complete = false; }, house, new RegExp(`${b.id}'s ballots are not complete`));
  differs(f => { f.rollcalls.push({ ...f.rollcalls[0], id: "2026-H-999", seq: 999 }); }, house,
          /2026-H-999 is in the test file and not in the record/);
  differs(f => { Object.assign(f.test.statements.find(x => x.name === "q3"), { problem: "query", error: "207 Invalid column" }); },
          house, /q3 failed \(query\): 207 Invalid column/);
  differs(f => { f.test.connection.prelogin.encryption = "REQ"; }, house, /the server answered encryption REQ/);
  differs(f => { f.test.unread = ["2026-H-999"]; }, house, /the ballots of 1 roll calls were not read/);
  differs(f => { Object.assign(f.test, { problem: "login", error: "18456 Login failed" }); }, house,
          /the test did not read: login: 18456/);
});

test("compare_test's time rule: Q2 or Q3 at 2 s is a no-go, Q3 at 1 s runs on one hot run in five, Q1 is not held", async () => {
  const house = untimed(await sitting(WED, {}));
  const at = (name, ms) => {
    const f = structuredClone(house);
    f.test.statements.find(x => x.name === name).ms = ms;
    return compare(f);
  };
  for (const name of ["q3", "q2 2"]) {
    const c = at(name, 2000);
    assert.equal(c.ok, false, name);
    assert.match(c.said.join("\n"), new RegExp(`${name} took 2\\.0 s, over the 2 s the go asks`));
    assert.ok(at(name, 1999).ok, `${name} at 1.999 s is a go`);
  }
  const slow = at("q3", 1000);
  assert.ok(slow.ok);
  assert.match(slow.said.join("\n"), /so Q3, over 1 s, runs on one hot run in five in session/);
  assert.doesNotMatch(at("q3", 999).said.join("\n"), /one hot run in five/);
  assert.ok(at("q1", 9000).ok, "Q1 is not held to the 2 s");
});

test("compareDocket finds a line Q3 missed and one it read that the docket lacks, over the 21 days before", async () => {
  const f = untimed(await sitting(WED, {}));
  const line = ([body, bill, at, , words]) => `2026|1234|${recordAs(at)}|${bill}|${body}|${words}|${recordAs(at)}`;
  const read = ([body, bill, at, order, words]) => ({ body, bill_as_recorded: bill, entered: at, order: Number(order), line: words });
  const docket = DOCKET.map(line);
  assert.ok(compareDocket(f, docket.join("\n")).ok, "SB502, entered 22 days before, is not Q3's");
  const missed = ["H", "HB1390", "2026-03-11T14:00:00", "5", "OTP: MA RC 200-150 03/11/2026"];
  let d = compareDocket(f, [...docket, line(missed)].join("\n"));
  assert.equal(d.ok, false);
  assert.match(d.said.join("\n"), /DIFFERS {2}in Docket\.txt, not read by Q3: H\|HB1390\|OTP: MA RC 200-150/);
  const extra = structuredClone(f);
  extra.test.docket.push(read(["S", "SB9", "2026-03-11T15:00:00", "1", "Ought to Pass, RC 1Y-2N, MF; 03/11/2026"]));
  d = compareDocket(extra, docket.join("\n"));
  assert.equal(d.ok, false);
  assert.match(d.said.join("\n"), /DIFFERS {2}read by Q3, not in Docket\.txt: S\|SB9\|/);
  // Entered 15 and 21 days before with the day's date in its words: Q3's, both.
  const early = [["S", "SB600", "2026-02-24T10:00:00", "2", "Ought to Pass, RC 14Y-10N, MA; 03/11/2026"],
                 ["S", "SB601", "2026-02-18T10:00:00", "3", "Ought to Pass, RC 13Y-11N, MA; 03/11/2026"]];
  const both = structuredClone(f);
  both.test.docket.push(...early.map(read));
  d = compareDocket(both, [...docket, ...early.map(line)].join("\n"));
  assert.ok(d.ok, d.said.join("\n"));
  d = compareDocket(f, [...docket, ...early.map(line)].join("\n"));
  assert.equal(d.said.filter(x => /not read by Q3/.test(x)).length, 2);
});

test("a server that requires encryption: the file says so, no login was sent, the sitting is asked again", async () => {
  const fake = await startFakeTds({ encryption: 0x03 });
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: {} });
    assert.deepEqual(got.test, { done: [], last: "2026-11-18" });
    assert.equal(got.file.status.problem, "encrypt");
    assert.equal(got.file.test.problem, "encrypt");
    assert.equal(got.file.test.connection.prelogin.encryption, "REQ");
    assert.equal(got.file.rollcalls.length, 0);
    assert.equal(fake.seen.login7.length, 0);
    assert.equal(fake.seen.afterRefusal, 0);
    const c = compare(got.file);
    assert.equal(c.ok, false);
    assert.match(c.said.join("\n"), /encryption REQ/);
    assert.deepEqual(testDue(THU, got.test).day, "2026-03-11");
  } finally {
    await fake.close();
  }
});

test("a statement that fails is recorded with its code, the rest still run, and the sitting is not asked again", async () => {
  const fake = await startFakeTds({ answer: fromRecords({ q3: { error: { number: 208, message: "Invalid object name 'Docket'." } } }) });
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: {} });
    assert.deepEqual(got.test.done, ["2026-03-11"], "asking again would send the same statements and find the same");
    assert.equal(testDue(THU, got.test).day, "2026-08-19", "the next weekday reads day 2");
    assert.equal(got.file.status.problem, "query");
    const q3s = got.file.test.statements.find(s => s.name === "q3");
    assert.equal(q3s.problem, "query");
    assert.match(q3s.error, /208/);
    assert.equal(got.file.rollcalls.length, 56, "Q1 and Q2 still read");
    assert.equal(compare(untimed(got.file)).ok, false, "and compare_test calls it a no-go");
  } finally {
    await fake.close();
  }
  const odd = await startFakeTds({ answer: fromRecords({ q1: { columns: text(...Array(11).fill("")),
    rows: [["X", "1", "", "", "0", "0", "0", "0", "", "", ""]] } }) });
  try {
    const got = await runTest(env(odd.port), { connect: nodeConnect, now: WED, test: {} });
    assert.equal(got.file.test.statements.find(s => s.name === "q1").problem, "shape");
    assert.equal(got.file.rollcalls.length, 0);
    assert.deepEqual(got.test.done, ["2026-03-11"]);
  } finally {
    await odd.close();
  }
  // Even the diagnostic SELECT @@VERSION alone failing: it was sent.
  const noversion = await startFakeTds({ answer: fromRecords({ version: { error: { number: 229, message: "permission denied" } } }) });
  try {
    const got = await runTest(env(noversion.port), { connect: nodeConnect, now: WED, test: {} });
    assert.equal(got.file.test.statements[0].problem, "query");
    assert.equal(got.file.rollcalls.length, 56);
    assert.deepEqual(got.test.done, ["2026-03-11"]);
  } finally {
    await noversion.close();
  }
});

test("a refused login sends no statement, so the same sitting is asked on the next weekday", async () => {
  const fake = await startFakeTds({ login: () => [{ number: 18456, message: "Login failed for user 'publicuser'." }] });
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: {} });
    assert.deepEqual(got.test, { done: [], last: "2026-11-18" });
    assert.equal(got.file.status.problem, "login");
    assert.equal(fake.seen.batches.length, 0);
    assert.equal(testDue(WED, got.test), null, "not again that day");
    assert.equal(testDue(THU, got.test).day, "2026-03-11");
  } finally {
    await fake.close();
  }
});

test("roll calls past three Q2 statements are listed as unread, and the sitting is not asked again", async () => {
  const many = Array.from({ length: 61 }, (_, i) => ["H", String(i + 1), "2026-03-11T10:00:00", "", "1", "0", "0", "0", "",
                                                     "", "VOTE SYSTEM"]);
  const fake = await startFakeTds({ answer: fromRecords({ q1: { columns: text(...Array(11).fill("")), rows: many } }) });
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: {} });
    assert.deepEqual(got.file.test.unread, ["2026-H-61"]);
    assert.equal(got.file.test.statements.filter(s => s.name.startsWith("q2")).length, 3);
    assert.deepEqual(got.test.done, ["2026-03-11"], "the same read would find the same");
    assert.match(compare(got.file).said.join("\n"), /ballots of 1 roll calls were not read/);
  } finally {
    await fake.close();
  }
});

test("a connection dropped in the middle of the test: what had run is kept, the rest is said not to have run", async () => {
  const records = fromRecords();
  const fake = await startFakeTds({ answer: (sql, n) => (sql.includes("FROM Docket d")
    ? { columns: text("", "", "", "", ""), rows: Array.from({ length: 900 }, () => ["H", "HB1", "2026-03-11T10:00:00", "1", "RC 1-2"]), drop: true }
    : records(sql, n)) });
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: {} });
    const said = Object.fromEntries(got.file.test.statements.map(s => [s.name, s]));
    assert.equal(said.q1.problem, null);
    assert.equal(said.q3.problem, "query");
    assert.match(said["q2 1"].error, /not run: the connection had closed/);
    assert.equal(got.file.status.problem, "query");
    assert.deepEqual(got.test.done, ["2026-03-11"], "statements were sent: read once");
    assert.equal(fake.seen.connections, 1, "no second connection that day");
  } finally {
    await fake.close();
  }
});

test("the run's 45 s SQL budget bounds the test: the login and every statement end inside it", async () => {
  assert.equal(SQL_BUDGET_MS, 45000, "the design's section 2.1");
  // A login that never answers ends at the budget, not at its 15 s step.
  const mute = await startFakeTds({ silent: "login" });
  try {
    const t0 = Date.now();
    const got = await runTest(env(mute.port), { connect: nodeConnect, now: WED, test: {}, budget: 400 });
    assert.ok(Date.now() - t0 < 8000, `${Date.now() - t0} ms`);
    assert.equal(got.file.test.problem, "connect");
    assert.deepEqual(got.test.done, [], "no statement was sent");
  } finally {
    await mute.close();
  }
  // Nor does a statement that never answers: the rest are said not to have run.
  const records = fromRecords();
  const fake = await startFakeTds({ answer: (sql, n) => (sql.includes("FROM Docket d") ? { silent: true } : records(sql, n)) });
  try {
    const t0 = Date.now();
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: WED, test: {}, budget: 1500 });
    assert.ok(Date.now() - t0 < 8000, `${Date.now() - t0} ms`);
    const q3s = got.file.test.statements.find(s => s.name === "q3");
    assert.equal(q3s.problem, "query");
    assert.match(q3s.error, /no answer in time/);
    assert.ok(got.file.test.statements.filter(s => s.name.startsWith("q2")).every(s => /not run/.test(s.error)));
    assert.deepEqual(got.test.done, ["2026-03-11"], "a statement was sent: not asked again");
  } finally {
    await fake.close();
  }
});

test("once both sittings are read, a weekday's test logs in and closes, and says how long each took", async () => {
  const fake = await startFakeTds({});
  try {
    const got = await runTest(env(fake.port), { connect: nodeConnect, now: FRI, test: { done: TEST_SITTINGS, last: "2026-11-19" } });
    assert.equal(got.key, "test/login/2026-11-20.json");
    assert.equal(got.file.kind, "live.test.login");
    assert.equal(got.file.problem, null);
    assert.ok(got.file.connection.connect_ms >= 0 && got.file.connection.login_ms >= 0);
    assert.equal(fake.seen.login7.length, 1);
    assert.equal(fake.seen.batches.length, 0);
  } finally {
    await fake.close();
  }
});
