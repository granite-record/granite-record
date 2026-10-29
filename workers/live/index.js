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
 * THIS BRANCH IS THE YOUTUBE HALF ALONE. control.json's "sql" is read and
 * reported and nothing more: this Worker has no database half, asks the
 * General Court nothing, and names none of its addresses.
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
import { iso, nh, youtubeDue } from "./clock.js";
import { FAILS_TO_TELL, forget, look, offFile, streamsKey } from "./youtube.js";
import { CONTROL_DEFAULT, WAITS_TO_TELL, WRITE_BY_MS, emptyState, leaseHeld, noteWait, putJSON,
         readControl, readJSON, readState, releaseLease, sweep, takeLease } from "./store.js";

export const PING_TIMEOUT_MS = 8000;
// The first run at or after this New Hampshire hour each day sweeps.
export const SWEEP_HOUR = 3;

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
  const sql = `sql ${control.sql}${control.sql === "off" ? "" : " (not read: this Worker has no database half)"}`;
  const said = control.source === "control.json"
    ? `youtube ${control.youtube}, ${sql} by control.json, uploaded ${stamp(control.uploaded)}`
    : `youtube ${control.youtube}, ${sql}: control.json ${control.source}, so shadow`;
  const count = out.count ? `today ${out.count.units} units, ${out.count.searches} searches` : "today not counted";
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

// One run. opts (tests): now, fetchImpl, run (its id), elapsed() (ms since the
// run began), timeoutMs, log.
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
    if (s.day !== p.today) { s.day = p.today; s.count = { units: 0, searches: 0 }; }
    out.count = s.count;
    if (p.held) out.codes.push(`youtube_held_${p.held.why}`);
    if (!p.youtube && !p.off && !p.sweep) {
      out.codes.push("nothing_due");
      return out;
    }
    if (leaseHeld(state, now, runId)) return await blocked(bucket, now, out);
    // Forgotten before the lease is written, so a run that fails after taking
    // it still leaves state.json with nothing of YouTube's past 30 days.
    forget(s.yt, now);
    const lease = await takeLease(bucket, s, etag, runId, now);
    if (!lease) return await blocked(bucket, now, out);

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
