/*
 * The votes half: while a chamber sits, the day's roll calls, the ballots of
 * new ones and the docket's tally lines, read from the General Court's public
 * SQL database (the live layer's design, sections 2.2, 2.3 and 2.6) and
 * merged into votes/<date>.json (merge.js). Only while control.json says
 * "sql": "on"; index.js runs it under the lease.
 *
 * EACH CHAMBER IS IN ONE OF FOUR STATES, worked out every run:
 *   hot        its session stream is live, or scheduled to start within 15
 *              minutes (today's streams file, written by the YouTube half),
 *              or one of its roll calls dated today was first seen in the
 *              last 45 minutes: read every run
 *   warm       for 5 hours after it was last hot, never past 23:59 New
 *              Hampshire time: every 10 minutes
 *   heartbeat  neither, on a weekday from the end of the night's window
 *              (08:30 EST, 09:30 EDT) to 18:00, from 1 January to 30 June,
 *              and on weekdays in the 14 days after a day it was hot: every
 *              15 minutes, Q1 over 14 days alone. A roll call dated today
 *              makes the chamber hot
 *   off        otherwise
 * NO CLOCK CAP: reading goes on while the stream is live or roll calls keep
 * coming. Votes do not depend on YouTube: the heartbeat finds a sitting
 * YouTube does not report, by its own first roll call.
 *
 * ONE CONNECTION A RUN, for both chambers, closed at once. A hot run reads
 * Q1 for today, and for the last 14 days when the last such wide read is 10
 * minutes old; Q3 (one hot run in five once Q3 has taken over 1 s); and Q2
 * for at most 20 roll calls that need ballots: new, incomplete (after two
 * tries at most every 10 minutes), or whose tally or save changed, never
 * one dated more than 14 days back.
 *
 * THE NIGHT'S WINDOW (refusal.NIGHT_WINDOWS, through live.gen.js): warm and
 * heartbeat reads never start inside one. A hot read inside one happens only
 * for a chamber whose session stream is live -- a sitting already under way
 * on a morning the night runs late -- on the IT office's word of 15 September.
 *
 * THE DAILY BUDGET: at 600 connections, 1,200 statements or 150,000 rows in a
 * New Hampshire day, the votes half holds until the next day.
 *
 * HOLDS, in state.json, each ending by the next New Hampshire day at the
 * latest, none needing a person:
 *   connect   three failed connections in a row: 30 minutes, then one try;
 *             failing again, the rest of the day (4060, the database rather
 *             than the password, counts here)
 *   login     the published login refused: the rest of the day, lifted at
 *             once if the published login in live.gen.js changes
 *   encrypt   the server asks for encryption a Worker cannot carry (or
 *             speaks TDS older than 7.2): the rest of the day, tried again
 *             the next; section 2.8 is the decision
 *   guard     a configuration slip: the rest of the day
 *   query     three failed statements in a row: the rest of the day
 *   budget    the rest of the day
 * Every hold sends /fail while it stands (index.js).
 */
import { NIGHT_WINDOWS, SQL_LOGIN } from "./live.gen.js";
import { HOUR, MINUTE, iso, midnightAfter, NEW_YORK, nh, nightWindow, since } from "./clock.js";
import { sessionOf } from "./youtube.js";
import { MAX_ROLLCALLS, addDays, q1, q2, q3, readBallots, readDocket, readSummary } from "./sql.js";
import { open } from "./tds.js";
import { dayOfLine, dayOfRow, emptyFile, merge, votesKey } from "./merge.js";

export const CHAMBERS = ["H", "S"];
export const STREAM_LEAD = 15 * MINUTE;
export const RC_HOT = 45 * MINUTE;
export const WARM_FOR = 5 * HOUR;
export const EVERY = { hot: 2 * MINUTE, warm: 10 * MINUTE, heartbeat: 15 * MINUTE, wide: 10 * MINUTE,
                       q3slow: 10 * MINUTE, q2retry: 10 * MINUTE };
// A cron run a few seconds early is on time. The YouTube half's minute of
// slack would turn 15 minutes into 14 on the cron's 2-minute grid.
export const SLACK = 10_000;
export const WIDE_DAYS = 14;
export const AFTER_HOT_DAYS = 14;
export const HEARTBEAT_UNTIL = 18;            // New Hampshire hour
export const SEASON_LAST_MONTH = 6;           // January to June
export const Q2_TRIES = 2;
export const Q3_SLOW_MS = 1000;
export const FAILS_TO_HOLD = 3;
export const CONNECT_HOLD = 30 * MINUTE;
export const SQL_BUDGET_MS = 45_000;
export const BUDGET = Object.freeze({ connections: 600, statements: 1200, rows: 150_000 });

// The heartbeat starts where the night's daily window ends: its end in UTC,
// as a New Hampshire clock time on the day asked about.
const DAILY = NIGHT_WINDOWS.find(([wd]) => wd === null);

// ---- whether a chamber sits -------------------------------------------------
// The streams file as the YouTube half left it, if it is fresh enough to
// believe: checked, ok, and not past its next check by more than 5 minutes.
export function freshStreams(file, now) {
  if (!file || !file.status || !file.status.ok || !file.next_check) return null;
  return +now <= Date.parse(file.next_check) + 5 * MINUTE ? file : null;
}

// Whether chamber c's session stream is live (or about to be).
export function sessionLive(streams, c, now) {
  return Boolean(streams && (streams.streams || []).some(x => sessionOf(x.title) === c && x.chamber === c && (
    x.status === "live" || (x.status === "upcoming" && x.scheduled
                            && Date.parse(x.scheduled) - +now <= STREAM_LEAD))));
}

function heartbeatHours(now) {
  const c = nh(now);
  if (c.weekend) return false;
  const [y, m, d] = c.date.split("-").map(Number);
  const end = Date.UTC(y, m - 1, d, DAILY[2][0], DAILY[2][1]);     // the window's end, in UTC, that day
  return +now >= end && c.hour < HEARTBEAT_UNTIL;
}

// {state, live} of chamber c: state is hot, warm, heartbeat or off.
export function chamberState(now, c, sq = {}, streams = null) {
  const t = +now, today = nh(now).date;
  const me = (sq.chambers || {})[c] || {};
  const live = sessionLive(streams, c, now);
  const window = nightWindow(now);
  let state = "off";
  if (live || since(me.last_rc, t) < RC_HOT) state = "hot";
  else if (since(me.last_hot, t) < WARM_FOR && nh(Date.parse(me.last_hot)).date === today) state = "warm";
  else if (heartbeatHours(now) && (Number(today.slice(5, 7)) <= SEASON_LAST_MONTH
           || (me.hot_day && me.hot_day < today && me.hot_day >= addDays(today, -AFTER_HOT_DAYS)))) state = "heartbeat";
  // The night's window: only a live session stream reads inside it.
  if (window && !(state === "hot" && live)) state = "off";
  return { state, live };
}

// ---- what a run reads ----------------------------------------------------------
// null, or {states, wide, q3, why}: what this run's one connection reads.
export function votesDue(now, sq = {}, streams = null) {
  const t = +now;
  const held = sq.held && Date.parse(sq.held.until) > t ? sq.held : null;
  const states = Object.fromEntries(CHAMBERS.map(c => [c, chamberState(now, c, sq, streams)]));
  const any = s => CHAMBERS.some(c => states[c].state === s);
  if (held) return { states, held, read: false };
  const last = since(sq.read, t), wideAgo = since(sq.wide, t);
  let read = false, wide = false, q3 = false, why = null;
  if (any("hot")) {
    read = true; why = "hot";
    wide = wideAgo >= EVERY.wide - SLACK;
    q3 = !(sq.q3_ms > Q3_SLOW_MS && since(sq.q3, t) < EVERY.q3slow - SLACK);
  } else if (any("warm") && last >= EVERY.warm - SLACK) {
    read = true; why = "warm"; wide = true; q3 = true;
  } else if (any("heartbeat") && last >= EVERY.heartbeat - SLACK) {
    read = true; why = "heartbeat"; wide = true; q3 = false;
  }
  return { states, held: null, read, wide, q3, why };
}

// When this reader will next read, as the votes file's next_read_by: the
// soonest of what each chamber's state calls for, or null when both are off.
export function nextRead(now, states) {
  const step = CHAMBERS.map(c => ({ hot: EVERY.hot, warm: EVERY.warm, heartbeat: EVERY.heartbeat }[states[c].state]))
    .filter(Boolean);
  return step.length ? iso(+now + Math.min(...step)) : null;
}

// The roll calls Q2 reads this run: new or changed first, then incomplete
// ones whose retries are due; never one dated more than 14 days back.
export function ballotsDue(now, need = {}, today) {
  const t = +now, oldest = addDays(today, -WIDE_DAYS);
  return Object.entries(need)
    .filter(([, n]) => n.day >= oldest && (n.tries < Q2_TRIES || since(n.last, t) >= EVERY.q2retry - SLACK))
    .sort(([a, x], [b, y]) => x.tries - y.tries || (x.day < y.day ? 1 : x.day > y.day ? -1 : a < b ? -1 : 1))
    .slice(0, MAX_ROLLCALLS)
    .map(([id, n]) => ({ id, body: n.body, seq: n.seq }));
}

// ---- holds -----------------------------------------------------------------------
// state.json's sql with any hold lifted that should lift before this run: a
// login hold once the published login changes, and a budget hold on a new day.
export async function liftHolds(sq = {}, now) {
  const h = sq.held;
  if (!h || Date.parse(h.until) <= +now) return sq;
  if (h.why === "login" && h.print !== await loginPrint()) return { ...sq, held: null, connfails: 0 };
  return sq;
}

// A print of the published login, so that a login hold lifts the moment the
// published credentials in live.gen.js change. The login is published; this
// says only whether it changed.
export async function loginPrint(login = SQL_LOGIN) {
  const d = new Uint8Array(await crypto.subtle.digest("SHA-256",
    new TextEncoder().encode(`${login.database}|${login.user}|${login.password}`)));
  return [...d.slice(0, 8)].map(b => b.toString(16).padStart(2, "0")).join("");
}

const SENTENCE = {
  connect: "the General Court's database could not be reached",
  login: "the database refused the published login: the published password may have changed; read the PDF again",
  encrypt: "the database asks for an encrypted connection this reader cannot make (design section 2.8)",
  guard: "the configuration names a host the reader refuses outside production",
  query: "three statements in a row failed",
  budget: "the day's budget of connections, statements or rows is spent",
};

export function holdSentence(h) {
  return `votes held${h.why === "connect" && h.stage === 1 ? " for 30 minutes" : " for the day"}: ${SENTENCE[h.why] || h.why}`;
}

// The state after a run's connection failed with TdsError code `code`.
function failedConnect(sq, code, now, print) {
  const dayEnd = iso(midnightAfter(now, NEW_YORK));
  const at = iso(now);
  if (code === "login") return { ...sq, connfails: 0, held: { why: "login", until: dayEnd, since: at, print } };
  if (code === "encrypt" || code === "version") return { ...sq, connfails: 0, held: { why: "encrypt", until: dayEnd, since: at } };
  if (code === "guard") return { ...sq, connfails: 0, held: { why: "guard", until: dayEnd, since: at } };
  // connect, database, anything else on the way in.
  const n = (sq.connfails || 0) + 1;
  if (sq.after_hold) return { ...sq, connfails: n, after_hold: false, held: { why: "connect", until: dayEnd, since: at, stage: 2 } };
  if (n >= FAILS_TO_HOLD) {
    return { ...sq, connfails: n, after_hold: true,
             held: { why: "connect", until: iso(+now + CONNECT_HOLD), since: at, stage: 1 } };
  }
  return { ...sq, connfails: n };
}

// ---- one read -------------------------------------------------------------------
// Runs this run's reads and merges them. `files(date)` reads votes/<date>.json
// as it stands; returns {sq, writes: [[key, file]], counts, codes, fail}.
//   env, connect   as tds.open takes them
//   sq             state.json's sql, as read
//   due            votesDue's answer, with due.read true
//   until          the run's SQL deadline (epoch ms)
export async function readVotes({ env, connect, now, sq: before = {}, due, files, count = {}, until }) {
  const t = +now, at = iso(now), today = nh(now).date, year = Number(today.slice(0, 4));
  const sq = structuredClone(before);
  sq.chambers = sq.chambers || {};
  const codes = [], writes = [];
  let fail = null;
  const spent = { connections: 0, statements: 0, rows: 0 };

  // A login hold lifts if the published login changed.
  const print = await loginPrint();

  let conn;
  try {
    spent.connections++;
    conn = await open(env, { connect, until });
  } catch (e) {
    const next = failedConnect(sq, e.code || "connect", now, print);
    codes.push(`sql_${e.code || "connect"}`);
    if (next.held && next.held !== sq.held) fail = `${holdSentence(next.held)} (${e.message})`;
    next.read = at;
    const held = next.held && Date.parse(next.held.until) > t ? next.held : null;
    return { sq: next, writes: await problemFile(files, today, held ? held.why : (e.code || "connect"), at, due,
                                                 held ? (held.stage === 1 ? held.until : null) : nextRead(now, due.states)),
             spent, codes, fail };
  }
  sq.connfails = 0;
  sq.after_hold = false;

  let summary = null, docket = null;
  const ballots = new Map();
  const errors = [];
  const run = async (name, sql, read) => {
    if (!conn.open) { errors.push(`${name}: the connection had closed`); return null; }
    spent.statements++;
    try {
      const res = await conn.query(sql, { until });
      spent.rows += res.rows.length;
      const got = read(res);
      sq.qfails = 0;
      return { got, ms: res.ms };
    } catch (e) {
      sq.qfails = (sq.qfails || 0) + 1;
      errors.push(`${name}: ${e.code || "query"} ${String(e.message || e).slice(0, 120)}`);
      return null;
    }
  };

  const from = due.wide ? addDays(today, -WIDE_DAYS) : today;
  const r1 = await run("q1", q1({ year, from, until: addDays(today, 1) }), r => readSummary(r, year));
  if (r1) { summary = r1.got; if (due.wide) sq.wide = at; }
  if (due.q3) {
    const r3 = await run("q3", q3({ year, day: today }), readDocket);
    if (r3) { docket = r3.got; sq.q3 = at; sq.q3_ms = r3.ms; }
  }
  // Ballots for what the previous reads, and this one, found needing them.
  const need = { ...(sq.need || {}) };
  const known = sq.saves || {};
  for (const r of summary || []) {
    // A roll call never read before, or whose tally or save moved, has its
    // ballots asked in this same run.
    const k = known[r.id];
    if (dayOfRow(r) >= addDays(today, -WIDE_DAYS) && (!k || k.m !== r.modified)) {
      need[r.id] = { body: r.body, seq: r.seq, day: dayOfRow(r), tries: 0, last: null };
    }
  }
  const asked = ballotsDue(now, need, today);
  if (asked.length) {
    const r2 = await run("q2", q2({ year, rollcalls: asked }), readBallots);
    for (const a of asked) need[a.id] = { ...need[a.id], tries: need[a.id].tries + 1, last: at };
    if (r2) {
      for (const b of r2.got) {
        const id = `${year}-${b.body}-${b.seq}`;
        if (!ballots.has(id)) ballots.set(id, new Map());
        ballots.get(id).set(b.member, b.vote);
      }
    }
  }
  conn.close();
  sq.read = at;
  if (errors.length) {
    codes.push(`sql_query_failed_${errors.length}`);
    if ((sq.qfails || 0) >= FAILS_TO_HOLD) {
      sq.held = { why: "query", until: iso(midnightAfter(now, NEW_YORK)), since: at };
      fail = `${holdSentence(sq.held)} (${errors[0]})`;
    }
  }

  // Merge by date: the dates Q1 and Q3 named, and today.
  const dates = new Set([today]);
  for (const r of summary || []) if (dayOfRow(r)) dates.add(dayOfRow(r));
  for (const l of docket || []) if (dayOfLine(l, today)) dates.add(dayOfLine(l, today));
  // Every day the read covered that holds roll calls already shown, so a
  // roll call the database stopped listing counts its miss.
  if (summary) for (const v of Object.values(sq.saves || {})) if (v.day >= from && v.day <= today) dates.add(v.day);
  // A roll call whose ballots were read is merged into its own day's file,
  // whatever window this read covered: never read and thrown away.
  for (const a of asked) if (need[a.id] && need[a.id].day) dates.add(need[a.id].day);
  let misses = { ...(sq.misses || {}) };
  const saves = { ...(sq.saves || {}) };      // {id: {m: DateModified, day}}
  const firstSeenToday = new Set();
  const nextBy = nextRead(now, due.states);
  for (const date of [...dates].sort()) {
    const prev = await files(date);
    if (prev === undefined) { codes.push(`sql_unreadable_${date}`); continue; }   // never rebuilt from one read
    const rows = (summary || []).filter(r => dayOfRow(r) === date);
    const lines = (docket || []).filter(l => dayOfLine(l, today) === date);
    const mine = new Map([...ballots].filter(([id]) => rows.some(r => r.id === id)
                                                  || (prev && prev.rollcalls.some(x => x.id === id))));
    // Today's file is written when it exists, has something, or a chamber is
    // hot or warm: a quiet heartbeat day leaves no public file behind.
    const sitting = Object.values(due.states).some(x => x.state === "hot" || x.state === "warm");
    if (!prev && !rows.length && !lines.length && !(date === today && sitting)) continue;
    const covered = Boolean(summary) && date >= from && date <= today;
    const flat = Object.fromEntries(Object.entries(saves).map(([id, v]) => [id, v.m]));
    const m = merge(prev, { date, rows, ballots: mine, lines, at, covered, misses, saves: flat });
    misses = m.misses;            // replaced: a roll call listed again starts its count over
    for (const r of rows) saves[r.id] = { m: r.modified, day: date };
    // A complete set needs nothing more; an incomplete one stays asked for,
    // its tries counting (two, then every 10 minutes).
    for (const rc of m.file.rollcalls) {
      if (rc.ballots_complete) delete need[rc.id];
      else if (!need[rc.id] && date >= addDays(today, -WIDE_DAYS)) {
        need[rc.id] = { body: rc.body, seq: rc.seq, day: date, tries: 0, last: null };
      }
      if (date === today && rc.first_seen === at) firstSeenToday.add(rc.body);
    }
    const f = m.file;
    if (summary) f.read_at = at;
    if (date === today) {
      f.next_read_by = nextBy;
      const problem = errors.length ? "query" : null;
      f.status = { state: "reading", problem, since: problem ? (f.status && f.status.problem === problem
                                                                ? f.status.since : at) : null };
    }
    if (date === today || rows.length || lines.length || m.changed.length) writes.push([votesKey(date), f]);
  }
  for (const c of firstSeenToday) sq.chambers[c] = { ...(sq.chambers[c] || {}), last_rc: at };
  // Kept only for what the next read can still touch.
  const oldest = addDays(today, -WIDE_DAYS);
  sq.need = Object.fromEntries(Object.entries(need).filter(([, n]) => n.day >= oldest));
  sq.saves = Object.fromEntries(Object.entries(saves).filter(([, v]) => v.day >= oldest));
  sq.misses = Object.fromEntries(Object.entries(misses).filter(([id]) => Object.hasOwn(sq.saves, id)));
  for (const c of CHAMBERS) {
    if (due.states[c].state === "hot") {
      sq.chambers[c] = { ...(sq.chambers[c] || {}), last_hot: at, hot_day: today };
      if (sq.over === today) sq.over = null;          // sitting again: the day's end is said again later
    }
  }
  if (sq.held && sq.held.why === "query" && sq.held.since === at) {
    for (const w of writes) if (w[0] === votesKey(today)) w[1] = heldStatus(w[1], "query", at);
  }
  codes.push(`sql_read_${due.why}${due.wide ? "_wide" : ""}_${(summary || []).length}rc`);
  return { sq, writes, spent, codes, fail };
}

// The file today's page reads when a read could not be made: what it said,
// with the problem. Written only when there is a file, or reading was due
// because a chamber is hot.
async function problemFile(files, today, problem, at, due, nextBy) {
  const prev = await files(today);
  if (prev === undefined) return [];                  // unreadable: never written over
  if (!prev && !Object.values(due.states).some(s => s.state === "hot")) return [];
  const f = prev ? structuredClone(prev) : emptyFile(today);
  f.status = { state: "reading", problem, since: f.status && f.status.problem === problem ? f.status.since : at };
  f.next_read_by = nextBy;
  return [[votesKey(today), f]];
}

// The day's file when a hold begins after a read (the budget, three failed
// statements): its sentence, and no next read today.
export function heldStatus(file, why, at) {
  const f = structuredClone(file);
  f.status = { state: "reading", problem: why, since: at };
  f.next_read_by = null;
  return f;
}

// The day's file says the person turned the votes half off, once a day.
export function offStatus(file, at) {
  const f = structuredClone(file);
  f.status = { state: "off", problem: "off", since: at };
  f.next_read_by = null;
  return f;
}

// The day's file says reading has stopped for the day.
export function overStatus(file, at) {
  const f = structuredClone(file);
  f.status = { state: "day_over", problem: "day_over", since: at };
  f.next_read_by = null;
  return f;
}

// Whether this run's counts would pass the day's budget.
export function overBudget(count) {
  return (count.connections || 0) >= BUDGET.connections || (count.statements || 0) >= BUDGET.statements
    || (count.rows || 0) >= BUDGET.rows;
}

export { loginPrint as _loginPrint, failedConnect as _failedConnect };
