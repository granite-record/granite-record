/*
 * THE LIVE WORKER, graniterecord-live (the person, 26 October 2026: the live
 * layer approved with its defaults). Live Now's data: which House and Senate
 * streams are live, scheduled today or ended today, asked of YouTube's Data
 * API and written to the private R2 bucket graniterecord-live, from which a
 * read-only Pages Function (a later branch) serves the page. No page waits on
 * it: the night draws /live with today's meetings already in it, and the page
 * says when live status was last checked, never "nothing is live".
 *
 * It has no address and answers no request. Its cron, every 2 minutes and
 * only in [env.production] (wrangler.toml), runs run() below, which:
 *   1. reads control.json, the person's one switch, and state.json;
 *   2. works out what is due (clock.js), and with nothing due stops there,
 *      writing nothing;
 *   3. takes the lease (store.js), or stops if another run has it;
 *   4. looks at YouTube (youtube.js) and, on the first run after 03:00, deletes
 *      what is 30 days old;
 *   5. writes streams/<today>.json while the lease holds, and releases it;
 *   6. pings Healthchecks with what it did, and /fail when a person should
 *      know: a hold beginning (YouTube's quota, search's allowance, or a
 *      refused key), three runs in a row finding another run's lease, or a
 *      run that held the lease, had something due and wrote nothing; and on
 *      every run, looking or not, while something stands that a person must
 *      mend: five or more failed looks in a row, no key, or a control.json
 *      that cannot be read (honoured as shadow, which may not be what the
 *      person meant: a typed "of" for "off").
 * Each run's codes also go to Workers Logs as one line.
 *
 * THE DATABASE HALF, SO FAR: THE NOVEMBER TEST (test_mode.js, design 2.7).
 * While control.json says "sql": "test", the first run between 10:00 and
 * 16:00 on a weekday makes the test's one connection, before anything else
 * it does, and writes the test's file at once, under the lease; in test mode
 * nothing else reads the database. "sql": "on" runs the session reads
 * (votes.js): while a chamber sits, the day's roll calls, ballots and docket
 * tally lines, merged into votes/<date>.json, read before YouTube is asked
 * and written at once under the lease. "off", or a missing or unreadable
 * control.json, asks the database nothing. The host is
 * named only in wrangler.toml's production vars, and tds.js refuses any
 * other but the loopback address.
 *
 * Its secrets are YOUTUBE_API_KEY, a second key in the existing Google
 * project restricted to the YouTube Data API v3, and HEALTHCHECK_URL; README.md
 * says how the person sets each. Without the key, YouTube is asked nothing and
 * every run says so, until the first run after the key is put; a key YouTube
 * refuses is held for the rest of the day, or until the person turns YouTube
 * off and on again. Without the URL, nothing is pinged.
 *
 * TURNING YOUTUBE OFF forgets what state.json kept of YouTube -- the upcoming
 * ids, the ids live, the playlist reads, any hold -- on the first run that
 * honours it, so nothing of YouTube's is kept while the half is off.
 */
import { clock } from "../follow/common.js";
import { NEW_YORK, iso, midnightAfter, nh, youtubeDue } from "./clock.js";
import { FAILS_TO_TELL, forget, look, offFile, streamsKey } from "./youtube.js";
import { TEST_SITTINGS, runTest, testDue } from "./test_mode.js";
import { BUDGET, SQL_BUDGET_MS, freshStreams, holdSentence, liftHolds, offStatus, overBudget, overStatus,
         readVotes, votesDue } from "./votes.js";
import { votesKey } from "./merge.js";
import { CONTROL_DEFAULT, WAITS_TO_TELL, WRITE_BY_MS, checkpoint, emptyState, leaseHeld, noteWait, putJSON,
         readControl, readJSON, readState, releaseLease, sweep, takeLease } from "./store.js";

export const PING_TIMEOUT_MS = 8000;
// The first run at or after this New Hampshire hour each day sweeps.
export const SWEEP_HOUR = 3;
// A session read that took longer than this leaves YouTube to the next run,
// so the run stays inside its lease (YouTube's calls are 8 s each).
export const SLOW_READ_MS = 30_000;

// What this run is due to do, from the person's switch and state.json alone.
export function plan(now, state, control) {
  const s = state || emptyState();
  const c = nh(now);
  const yt = s.yt || {};
  const off = control.youtube === "off";
  const due = off ? null : youtubeDue(now, yt);
  return {
    today: c.date,
    youtube: due && due.any ? due : null,
    held: (due && due.held) || null,
    off: off && yt.off !== c.date,
    sweep: s.swept !== c.date && c.hour >= SWEEP_HOUR,
    test: control.sql === "test" ? testDue(now, s.test || {}) : null,
  };
}

function stamp(when) {
  if (!when) return "at an unknown time";
  const c = nh(+new Date(when));
  return `${c.date} ${String(c.hour).padStart(2, "0")}:${String(c.minute).padStart(2, "0")} New Hampshire time`;
}

// What Healthchecks is told: the run's codes, what control.json says and that
// it is honoured, and the day's spend.
export function pingBody(out, control) {
  const sql = `sql ${control.sql}`;
  const said = control.source === "control.json"
    ? `youtube ${control.youtube}, ${sql} by control.json, uploaded ${stamp(control.uploaded)}`
    : `youtube ${control.youtube}, ${sql}: control.json ${control.source}, so shadow`;
  const count = out.count ? `today ${out.count.units} units, ${out.count.searches} searches` +
    (out.count.connections ? `, ${out.count.connections} connections, ${out.count.statements} statements` +
      (out.count.rows ? `, ${out.count.rows} rows` : "") : "")
    : "today not counted";
  return [`run ${out.run.slice(0, 8)} ${out.codes.join(" ")}`, said, count,
          out.fail ? `FAIL: ${out.fail}` : ""].filter(Boolean).join(" | ");
}

// What stands and needs a person, said as /fail on every run until it is
// mended (a refused key among them, for its day), so Healthchecks does not
// flap between a failing look and the quiet runs between looks.
export function standing(env, s, control, now) {
  if (control.source === "unreadable") {
    return "control.json cannot be read, so it is honoured as shadow (youtube on, sql off): put one of control/*.json";
  }
  const sh = s && s.sql && s.sql.held;
  if (control.sql === "on" && sh && Date.parse(sh.until) > +now) return holdSentence(sh);
  if (control.youtube === "off") return null;
  if (!env.YOUTUBE_API_KEY) {
    return "there is no YOUTUBE_API_KEY secret, so YouTube is not asked: README.md says how to put it";
  }
  const held = s && s.yt && s.yt.held;
  if (held && held.why === "key" && Date.parse(held.until) > +now) {
    return `YouTube refused the key: the YouTube half waits for ${held.until}, or for YouTube off and on with a new key`;
  }
  const n = (s && s.yt && s.yt.fails) || 0;
  if (n >= FAILS_TO_TELL) return `${n} looks at YouTube in a row have failed`;
  return null;
}

async function ping(env, fetchImpl, out, control) {
  const url = env.HEALTHCHECK_URL;
  if (!url) return;
  const target = out.fail ? `${String(url).replace(/\/+$/, "")}/fail` : String(url);
  try {
    await fetchImpl(target, { method: "POST", body: pingBody(out, control),
                              signal: AbortSignal.timeout(PING_TIMEOUT_MS) });
  } catch { /* Healthchecks says so itself when the pings stop */ }
}

async function blocked(bucket, now, out) {
  const n = await noteWait(bucket, now);
  out.codes.push(`lease_held_${n}`);
  if (n >= WAITS_TO_TELL) out.fail = `${n} runs in a row have found another run's lease`;
  return out;
}

// What the bucket's own test files say was done, so that a lost or replaced
// state.json never reads a sitting twice: a sitting whose file shows a
// connection made is read, and a file written today (a sitting's or the
// day's login) is today's one attempt.
async function recovered(bucket, test, today) {
  const t = { ...test, done: [...(test.done || [])] };
  for (const day of TEST_SITTINGS) {
    const f = await readJSON(bucket, `test/${day}.json`);
    if (!f) continue;
    if (f.test && !f.test.problem && !t.done.includes(day)) t.done.push(day);
    if (f.read_at && nh(Date.parse(f.read_at)).date === today) t.last = today;
  }
  if (await readJSON(bucket, `test/login/${today}.json`)) t.last = today;
  t.done = TEST_SITTINGS.filter(d => t.done.includes(d));
  return t;
}

// The November test's part of a run: one connection, and its file written at
// once while the lease holds. AT MOST ONE CONNECTION A DAY, whatever happens
// after it: the day is put into state.json under the lease before anything
// connects, and a run that cannot put it does not connect. The sitting is
// put as read as soon as its file is written. If the file cannot be written
// the sitting is not counted as read and is asked again on the next weekday:
// a lost file is the one case a past sitting is read twice.
async function test(env, bucket, s, p, lease, now, out, opts, elapsed) {
  let connect = opts.connect;
  if (!connect) ({ connect } = await import("cloudflare:sockets"));
  const before = await recovered(bucket, s.test || {}, p.test.today);
  if (before.last === p.test.today || !testDue(now, before)) {
    s.test = before;
    out.codes.push("sql_test_already_done_today");
    return false;
  }
  s.test = { ...before, last: p.test.today };
  if (!(await checkpoint(bucket, s, lease))) {
    s.test = before;
    out.codes.push("sql_test_not_started_lease_lost");
    return false;
  }
  const r = await runTest(env, { connect, now, test: before });
  if (!r) return false;
  // A refused connection is the test's own finding (the login file's problem,
  // or the sitting file's test.problem); a failed statement is its status's.
  const refused = (r.file.test ? r.file.test.problem : r.file.problem) || null;
  const problem = refused || (r.file.status && r.file.status.problem) || null;
  const sent = r.file.test ? r.file.test.statements.filter(x => !/^not run/.test(x.error || "")).length : 0;
  s.count = { ...s.count, connections: (s.count.connections || 0) + (refused === "guard" ? 0 : 1),
              statements: (s.count.statements || 0) + sent };
  out.count = s.count;
  out.codes.push(`sql_test_${p.test.kind}_${problem || "ok"}`);
  let wrote = false;
  if (elapsed() < WRITE_BY_MS) {
    try { await putJSON(bucket, r.key, r.file); wrote = true; out.wrote.push(r.key); }
    catch { out.codes.push(`write_failed_${r.key}`); }
  } else {
    out.codes.push("lease_lapsed");
  }
  s.test = wrote ? r.test : { ...before, last: r.test.last };
  if (wrote && !(await checkpoint(bucket, s, lease))) out.codes.push("lease_lost");
  if (!wrote) {
    out.fail = `the November test's file ${r.key} was not written: it is asked again on the next weekday`;
  } else if (refused) {
    out.fail = `the November test could not read (${refused}): ${r.key} says why`;
  } else if (problem) {
    out.fail = `a statement of the November test failed (${problem}): ${r.key} says which; the sitting is not asked again`;
  }
  return true;
}

// The votes half's part of a run (control.json "sql": "on"): its one
// connection, the files it changed written at once under the lease, and
// state.json put again before anything else happens. Whether it connected.
async function votes(env, bucket, s, v, lease, now, out, opts, elapsed) {
  let connect = opts.connect;
  if (!connect) ({ connect } = await import("cloudflare:sockets"));
  s.sql = { ...s.sql, read: out.at };
  if (!(await checkpoint(bucket, s, lease))) { out.codes.push("sql_not_started_lease_lost"); return false; }
  const room = Math.max(5_000, Math.min(SQL_BUDGET_MS, WRITE_BY_MS - elapsed() - 25_000));
  const r = await readVotes({ env, connect, now, sq: s.sql, due: v, until: Date.now() + room,
                              files: d => readJSON(bucket, votesKey(d)) });
  s.sql = { ...r.sq, on: nh(now).date };
  s.count = { ...s.count, connections: (s.count.connections || 0) + r.spent.connections,
              statements: (s.count.statements || 0) + r.spent.statements,
              rows: (s.count.rows || 0) + r.spent.rows };
  out.count = s.count;
  out.codes.push(...r.codes);
  if (r.fail) out.fail = out.fail || r.fail;
  let missed = 0;
  for (const [key, value] of r.writes) {
    if (elapsed() >= WRITE_BY_MS) { out.codes.push("lease_lapsed"); missed++; continue; }
    try { await putJSON(bucket, key, value); out.wrote.push(key); }
    catch { out.codes.push(`write_failed_${key}`); missed++; }
  }
  if (missed) out.fail = out.fail || `${missed} votes file(s) were due and not written`;
  if (overBudget(s.count) && !(s.sql.held && s.sql.held.why === "budget")) {
    s.sql.held = { why: "budget", until: iso(midnightAfter(now, NEW_YORK)), since: out.at };
    out.fail = out.fail || `${holdSentence(s.sql.held)} (${BUDGET.connections} connections, ` +
      `${BUDGET.statements} statements or ${BUDGET.rows} rows)`;
  }
  if (!(await checkpoint(bucket, s, lease))) out.codes.push("lease_lost");
  return true;
}

// One run. opts (tests): now, fetchImpl, connect (the socket opener for the
// database; the Worker's own is cloudflare:sockets'), run (its id), elapsed()
// (ms since the run began), timeoutMs, log.
export async function run(env, opts = {}) {
  const now = opts.now !== undefined ? new Date(+opts.now) : clock(env);
  const fetchImpl = opts.fetchImpl || fetch;
  const runId = opts.run || crypto.randomUUID();
  const began = Date.now();
  const elapsed = opts.elapsed || (() => Date.now() - began);
  const log = opts.log || (line => console.log(line));
  const out = { run: runId, at: iso(now), codes: [], wrote: [], fail: null, count: null };
  let control = { ...CONTROL_DEFAULT, source: "unread", uploaded: null };
  let s = null;
  try {
    const bucket = env.LIVE;
    if (!bucket) throw new Error("no LIVE bucket is bound");
    control = await readControl(bucket);
    const { state, etag } = await readState(bucket);
    s = state ? structuredClone(state) : emptyState();
    s.yt = s.yt || {};
    const p = plan(now, s, control);
    if (s.day !== p.today) { s.day = p.today; s.count = { units: 0, searches: 0, connections: 0, statements: 0, rows: 0 }; }
    out.count = s.count;
    if (p.held) out.codes.push(`youtube_held_${p.held.why}`);
    // The votes half: what it reads, and the two lines it writes once a day.
    s.sql = s.sql || {};
    let v = null, sqlOff = false, sqlOver = false;
    if (control.sql === "on") {
      s.sql = await liftHolds(s.sql, now);
      v = votesDue(now, s.sql, freshStreams(await readJSON(bucket, streamsKey(p.today)), now));
      if (v.held) out.codes.push(`sql_held_${v.held.why}`);
      const sitting = Object.values(v.states).some(x => x.state === "hot" || x.state === "warm");
      const hotToday = Object.values(s.sql.chambers || {}).some(c => c.hot_day === p.today);
      sqlOver = !v.held && !sitting && hotToday && s.sql.over !== p.today;
    } else {
      sqlOff = s.sql.on === p.today && s.sql.off !== p.today;
    }
    const reads = Boolean(v && v.read);
    if (!p.youtube && !p.off && !p.sweep && !p.test && !reads && !sqlOff && !sqlOver) {
      out.codes.push("nothing_due");
      return out;
    }
    if (leaseHeld(state, now, runId)) return await blocked(bucket, now, out);
    // Forgotten before the lease is written, so a run that fails after taking
    // it still leaves state.json with nothing of YouTube's past 30 days.
    forget(s.yt, now);
    const lease = await takeLease(bucket, s, etag, runId, now);
    if (!lease) return await blocked(bucket, now, out);

    // A run that connects to the database asks YouTube nothing: the next run,
    // 2 minutes on, looks. So the run stays well inside its lease.
    let connected = p.test ? await test(env, bucket, s, p, lease, now, out, opts, elapsed) : false;
    // A session read is every run while a chamber sits, and YouTube must keep
    // looking then; only one that ran long leaves the look to the next run.
    if (reads) await votes(env, bucket, s, v, lease, now, out, opts, elapsed);
    if (reads && elapsed() > SLOW_READ_MS) connected = true;
    // A file the person or the day's end should hear of, once.
    for (const [due, mark, make, code] of [[sqlOff, "off", offStatus, "sql_off_said"],
                                           [sqlOver, "over", overStatus, "sql_day_over_said"]]) {
      if (!due) continue;
      const f = await readJSON(bucket, votesKey(p.today));
      if (f) {
        try { await putJSON(bucket, votesKey(p.today), make(f, out.at)); out.wrote.push(votesKey(p.today)); }
        catch { out.codes.push(`write_failed_${votesKey(p.today)}`); continue; }
      }
      s.sql = { ...s.sql, [mark]: p.today };
      out.codes.push(code);
    }
    if (connected && p.youtube) { p.youtube = null; out.codes.push("youtube_next_run"); }
    const ytBefore = structuredClone(s.yt);
    const writes = [];
    if (p.off) {
      writes.push([streamsKey(p.today), offFile(await readJSON(bucket, streamsKey(p.today)), p.today, out.at)]);
      s.yt = { off: p.today };
      out.codes.push("youtube_off");
    } else if (control.youtube !== "off" && s.yt.off) {
      s.yt = { ...s.yt, off: null };
    }
    if (p.youtube) {
      const r = await look({ key: env.YOUTUBE_API_KEY, fetchImpl, now, yt: s.yt, due: p.youtube,
                             prev: await readJSON(bucket, streamsKey(p.today)), timeoutMs: opts.timeoutMs });
      s.yt = r.yt;
      s.count = { ...s.count, units: s.count.units + r.tally.units,
                  searches: s.count.searches + r.tally.searches };
      out.count = s.count;
      writes.push([streamsKey(p.today), r.file]);
      const live = r.file.streams.filter(x => x.status === "live").length;
      out.codes.push(r.problem ? `youtube_problem_${r.problem}` : `youtube_ok_${live}_live`);
      for (const n of r.notes) out.codes.push(`(${n})`);
      if (r.fail) out.fail = r.fail;
    }
    if (p.sweep) {
      out.codes.push(`swept_${await sweep(bucket, now)}`);
      s.swept = p.today;
    }
    // The public files, only while the lease holds.
    for (const [key, value] of writes) {
      if (elapsed() >= WRITE_BY_MS) { out.codes.push("lease_lapsed"); break; }
      try { await putJSON(bucket, key, value); out.wrote.push(key); }
      catch { out.codes.push(`write_failed_${key}`); }
    }
    if (out.wrote.length < writes.length) {
      // A file not written is a look not made, so the next run makes it again;
      // what was spent stays counted.
      s.yt = ytBefore;
      out.fail = out.fail || `${writes.length - out.wrote.length} file(s) were due and not written`;
    }
    if (!(await releaseLease(bucket, s, lease))) out.codes.push("lease_lost");
    return out;
  } catch (e) {
    out.codes.push("error");
    out.fail = out.fail || `the run stopped: ${(e && e.name) || "Error"}: ${String((e && e.message) || e).slice(0, 200)}`;
    return out;
  } finally {
    if (!out.fail) out.fail = standing(env, s, control, now);
    log(JSON.stringify({ live: out.codes, fail: out.fail, run: runId.slice(0, 8), count: out.count }));
    await ping(env, fetchImpl, out, control);
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env));
  },
  // No address answers anything: the Worker is a cron, and workers_dev is off.
  async fetch() { return new Response("Not found", { status: 404 }); },
};
