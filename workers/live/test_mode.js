/*
 * The November test: the one gate before any sitting (the live layer's design,
 * 26 October 2026, section 2.7). The run planner calls runTest() on each run
 * while control.json says "sql": "test", and writes the file it returns, under
 * its lease, with the state it returns; in test mode nothing else reads the
 * database -- no hot, warm or heartbeat reads.
 *
 * ONE CONNECTION A WEEKDAY, on the first run between 10:00 and 16:00 New
 * Hampshire time (TEST_HOURS), which preflight holds outside every window of
 * refusal.NIGHT_WINDOWS, in either half of the year.
 *   Day 1   one connection that records PRELOGIN's encryption answer and
 *           version, LOGINACK's TDS and server version, and SELECT @@VERSION;
 *           then Q1, Q3 and Q2 exactly as in session (Q2 in at most three
 *           statements of 20 roll calls) for 11 March 2026, the busiest House
 *           day, with votes to 20:46. It records each statement's time and
 *           bytes, and returns test/2026-03-11.json in the live votes file's
 *           shape.
 *   Day 2   the same for 19 August 2026, veto day in both chambers: the
 *           Senate's saves of the next morning, and the docket's text dates.
 *   Later   one connection that logs in and closes, recording how long each
 *           took: test/login/<today>.json. That is how reachability from
 *           Cloudflare's addresses shows over the following weeks.
 * A past sitting is read once. A day whose read failed -- no connection, or a
 * statement that failed -- is asked again on the next weekday, and its file
 * says what failed, including an encryption answer this reader cannot meet:
 * the result the test exists to find.
 *
 * The comparison is offline: the person downloads the file
 *     npx wrangler r2 object get graniterecord-live/test/2026-03-11.json --file test-2026-03-11.json --remote
 * and runs
 *     node tests/live/compare_test.mjs test-2026-03-11.json
 * which compares every roll call's tally, and every ballot by vote, with
 * records/rollcalls/ in git.
 */
import { open } from "./tds.js";
import { MAX_ROLLCALLS, VERSION, addDays, q1, q2, q3, readBallots, readDocket, readSummary,
         readVersion } from "./sql.js";
import { isoSeconds, nhClock } from "../follow/common.js";

export const TEST_SITTINGS = ["2026-03-11", "2026-08-19"];
export const TEST_HOURS = [10, 16];
export const TEST_Q2_STATEMENTS = 3;
export const SQL_BUDGET_MS = 45000;
export const SOURCE = "The General Court's public SQL database (RollCallSummary, RollCallHistory, Docket)";
const WEEKDAYS = new Set(["Mon", "Tue", "Wed", "Thu", "Fri"]);

// What the test does on a run at `now`, given its state ({done, last}): null
// (nothing), {kind: "sitting", day, today} or {kind: "login", today}.
export function testDue(now, test = {}) {
  const c = nhClock(now);
  if (!WEEKDAYS.has(c.weekday) || c.hour < TEST_HOURS[0] || c.hour >= TEST_HOURS[1]) return null;
  if (test?.last === c.date) return null;
  const day = TEST_SITTINGS.find(d => !(test?.done || []).includes(d));
  return day ? { kind: "sitting", day, today: c.date } : { kind: "login", today: c.date };
}

// null when nothing is due; otherwise {test: the new state, key, file}.
export async function runTest(env, { connect, now = new Date(), test = {} } = {}) {
  const job = testDue(now, test);
  if (!job) return null;
  const until = Date.now() + SQL_BUDGET_MS;
  const next = { ...test, done: [...(test?.done || [])], last: job.today };
  const readAt = isoSeconds(now);
  let conn = null;
  let refused = null;
  try {
    conn = await open(env, { connect, until });
  } catch (e) {
    refused = { code: e.code || "connect", error: e.message, connection: e.info || null };
  }
  if (job.kind === "login") {
    conn?.close();
    return { test: next, key: `test/login/${job.today}.json`,
             file: { kind: "live.test.login", day: job.today, read_at: readAt,
                     connection: refused ? refused.connection : conn.info,
                     problem: refused?.code || null, error: refused?.error || null } };
  }

  const year = Number(job.day.slice(0, 4));
  const statements = [];
  const run = async (name, sql, read) => {
    if (!conn?.open) {
      statements.push({ name, ms: null, bytes: null, rows: null, problem: "query",
                        error: "not run: the connection had closed" });
      return null;
    }
    let res;
    try {
      res = await conn.query(sql, { until });
    } catch (e) {
      statements.push({ name, ms: null, bytes: e.bytes ?? null, rows: null, problem: e.code || "query",
                        error: e.message });
      return null;
    }
    const said = { name, ms: res.ms, bytes: res.bytes, rows: res.rows.length, problem: null, error: null };
    statements.push(said);
    try {
      return read(res);
    } catch (e) {
      Object.assign(said, { problem: e.code || "shape", error: e.message });
      return null;
    }
  };

  let version = null;
  let summary = [];
  let docket = [];
  const ballots = [];
  let unread = [];
  if (conn) {
    version = await run("version", VERSION, readVersion);
    summary = await run("q1", q1({ year, from: job.day, until: addDays(job.day, 1) }), r => readSummary(r, year)) || [];
    docket = await run("q3", q3({ year, day: job.day }), readDocket) || [];
    const calls = summary.map(r => ({ body: r.body, seq: r.seq }));
    for (let k = 0; k * MAX_ROLLCALLS < calls.length; k++) {
      const part = calls.slice(k * MAX_ROLLCALLS, (k + 1) * MAX_ROLLCALLS);
      if (k >= TEST_Q2_STATEMENTS) { unread = unread.concat(part.map(c => `${year}-${c.body}-${c.seq}`)); continue; }
      ballots.push(...(await run(`q2 ${k + 1}`, q2({ year, rollcalls: part }), readBallots) || []));
    }
    conn.close();
  }

  const problem = refused?.code || statements.find(s => s.problem)?.problem || null;
  if (!problem && !unread.length) next.done.push(job.day);
  const shape = liveShape({ readAt, summary, ballots });
  return {
    test: next,
    key: `test/${job.day}.json`,
    file: {
      api: 1, kind: "session.votes", date: job.day, provisional: true,
      read_at: readAt, next_read_by: null,
      status: { state: "test", problem, since: null },
      source: SOURCE,
      members: shape.members, rollcalls: shape.rollcalls, tallies: [],
      test: { connection: refused ? refused.connection : conn.info, version,
              problem: refused?.code || null, error: refused?.error || null,
              statements, docket, unread },
    },
  };
}

// Q1's and Q2's records as the live votes file carries them (design section
// 5): each roll call's ballots one character a member, aligned to members[body].
export function liveShape({ readAt, summary, ballots }) {
  const members = { H: [], S: [] };
  const votes = new Map();
  for (const b of ballots) {
    if (!members[b.body].includes(b.member)) members[b.body].push(b.member);
    const key = `${b.body}-${b.seq}`;
    if (!votes.has(key)) votes.set(key, new Map());
    votes.get(key).set(b.member, b.vote);
  }
  for (const body of ["H", "S"]) members[body].sort((x, y) => x.localeCompare(y, "en", { numeric: true }));
  const rollcalls = summary.map(r => {
    const got = votes.get(`${r.body}-${r.seq}`) || new Map();
    const count = c => [...got.values()].filter(v => v === c).length;
    return {
      id: r.id, body: r.body, seq: r.seq,
      bill: r.bill_as_recorded ? `${termOf(r.year)}/${r.bill_as_recorded}` : null,
      bill_as_recorded: r.bill_as_recorded, question: r.question,
      taken: r.body === "H" ? nhToUtc(r.vote_date) : null,
      saved: r.body === "S" ? nhToUtc(r.modified) : null,
      keyed_by: r.user === "VOTE SYSTEM" ? "voting system" : "clerk",
      yeas: r.yeas, nays: r.nays, present: r.present, absent: r.absent,
      ballots: members[r.body].map(m => got.get(m) || ".").join(""),
      ballots_complete: got.size > 0 && count("Y") === r.yeas && count("N") === r.nays,
      docket: null, first_seen: readAt, note: null,
    };
  });
  return { members, rollcalls };
}

// The term a session year belongs to: an odd year starts one.
export function termOf(year) {
  return year % 2 ? `${year}-${year + 1}` : `${year - 1}-${year}`;
}

const NH_SECONDS = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York", hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit",
});

// A moment as New Hampshire's wall clock reads it, YYYY-MM-DDTHH:MM:SS.
export function nhLocal(d) {
  const p = Object.fromEntries(NH_SECONDS.formatToParts(d).map(x => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day}T${String(Number(p.hour) % 24).padStart(2, "0")}:${p.minute}:${p.second}`;
}

// New Hampshire's wall-clock time, as the database keeps it, as UTC; null for
// none, or for a time the spring change skips.
export function nhToUtc(local) {
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})$/.exec(local || "");
  if (!m) return null;
  const naive = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]);
  for (const hours of [5, 4]) {
    const d = new Date(naive + hours * 3600000);
    if (nhLocal(d) === local) return isoSeconds(d);
  }
  return null;
}
