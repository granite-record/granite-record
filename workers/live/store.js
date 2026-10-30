/*
 * The live Worker's one store: the private R2 bucket graniterecord-live,
 * bound as LIVE. Nothing else is bound, and this is the only file that reads
 * or writes it.
 *
 *   control.json         a person's, the one switch; the Worker only reads it
 *   state.json           the Worker's: the lease, the day's counts, and what
 *                        the next run needs (never a fact about a stream
 *                        beyond that)
 *   streams/<day>.json   the Worker's: today's streams, read by the page's
 *                        Function (a later branch); deleted after 30 days
 *   lease-waits.json     the Worker's: how many runs in a row have found
 *                        another run's lease, written only by such a run
 *   votes/, test/        a later branch's; swept after 30 days here already
 *
 * ONE WRITER AT A TIME (the lease). A run reads state.json and its etag; with
 * nothing due it stops there and writes nothing. If another run's lease has
 * not run out, it stops. Otherwise it puts state.json with its own lease,
 * only if the etag is still the one it read -- R2's put returns null when
 * that condition fails, and then another run has it, so it stops. It does its
 * work; writes the public files only while its lease holds (under WRITE_BY_MS
 * of it); and releases by putting state.json again, only if the etag is still
 * its own. Runs are 120 s apart and a lease is 110 s, so a lease never blocks
 * the next normal run. The first run ever, with no state.json, writes one
 * unconditionally: two runs at that exact moment is the one unguarded case.
 *
 * LOSING state.json IS HARMLESS: the day's counts start again, the upcoming
 * ids are found again by the playlists and search, a hold that stood costs
 * one more failed try, and the November test's progress is read again from
 * its own files (index.js recovered()), so no past sitting is read twice.
 */
import { addDays } from "../follow/common.js";
import { iso, nh, since } from "./clock.js";

export const CONTROL = "control.json";
export const STATE = "state.json";
export const WAITS = "lease-waits.json";
export const LEASE_MS = 110_000;
export const WRITE_BY_MS = 90_000;
// Two runs that found a lease within this of each other are runs in a row.
export const WAIT_GAP_MS = 150_000;
export const WAITS_TO_TELL = 3;
export const KEEP_DAYS = 30;
export const SWEPT = ["streams/", "votes/", "test/"];
const JSON_TYPE = { contentType: "application/json; charset=utf-8" };

// ---- control.json: the person's one switch ----------------------------------
// Missing or unreadable means shadow: YouTube on, the database off. A field
// left out takes its default; a value not listed here makes the whole file
// unreadable, and the ping says so.
export const CONTROL_DEFAULT = Object.freeze({ youtube: "on", sql: "off" });
export const CONTROL_VALUES = Object.freeze({ youtube: ["on", "off"], sql: ["off", "test", "on"] });

export function parseControl(text) {
  let c;
  try { c = JSON.parse(text); } catch { return null; }
  if (!c || typeof c !== "object" || Array.isArray(c)) return null;
  const out = { ...CONTROL_DEFAULT };
  for (const [k, allowed] of Object.entries(CONTROL_VALUES)) {
    if (!(k in c)) continue;
    if (!allowed.includes(c[k])) return null;
    out[k] = c[k];
  }
  return out;
}

// {youtube, sql, source: "control.json" | "missing" | "unreadable", uploaded}
export async function readControl(bucket) {
  let o;
  try { o = await bucket.get(CONTROL); } catch { return { ...CONTROL_DEFAULT, source: "unreadable", uploaded: null }; }
  if (!o) return { ...CONTROL_DEFAULT, source: "missing", uploaded: null };
  const c = parseControl(await o.text());
  return c ? { ...c, source: "control.json", uploaded: o.uploaded || null }
           : { ...CONTROL_DEFAULT, source: "unreadable", uploaded: o.uploaded || null };
}

// ---- state.json --------------------------------------------------------------
export function emptyState() {
  return { v: 1, lease: null, day: null, count: { units: 0, searches: 0 }, yt: {}, swept: null };
}

// {state, etag}: state is null when there is none or it cannot be read; the
// etag is kept either way, so an unreadable file is replaced under the lease.
export async function readState(bucket) {
  const o = await bucket.get(STATE);
  if (!o) return { state: null, etag: null };
  let state = null;
  try { state = JSON.parse(await o.text()); } catch { /* replaced below */ }
  if (!state || typeof state !== "object" || state.v !== 1) state = null;
  return { state, etag: o.etag };
}

export function leaseHeld(state, now, run) {
  const l = state && state.lease;
  return Boolean(l && l.run !== run && Date.parse(l.until) > +now);
}

// The lease, or null when another run took state.json first.
export async function takeLease(bucket, state, etag, run, now) {
  const body = { ...state, lease: { run, until: iso(+now + LEASE_MS) } };
  const opts = etag ? { onlyIf: { etagMatches: etag }, httpMetadata: JSON_TYPE } : { httpMetadata: JSON_TYPE };
  const put = await bucket.put(STATE, JSON.stringify(body), opts);
  return put ? { etag: put.etag, held: body.lease } : null;
}

// state.json put mid-run, the lease kept: what must not be lost if the run
// dies before it releases (the November test's day, before it connects).
// Whether it was put; the lease's etag moves with it.
export async function checkpoint(bucket, state, lease) {
  const put = await bucket.put(STATE, JSON.stringify({ ...state, lease: lease.held }),
                               { onlyIf: { etagMatches: lease.etag }, httpMetadata: JSON_TYPE });
  if (put) lease.etag = put.etag;
  return Boolean(put);
}

// Whether state.json was put: false when another run has taken it since.
export async function releaseLease(bucket, state, lease) {
  const put = await bucket.put(STATE, JSON.stringify({ ...state, lease: null }),
                               { onlyIf: { etagMatches: lease.etag }, httpMetadata: JSON_TYPE });
  return Boolean(put);
}

// A run that found another's lease counts itself here, and only such a run
// writes it: so the lease holder's etag is never disturbed. Returns how many
// runs in a row (each within WAIT_GAP_MS of the one before) have now found one.
export async function noteWait(bucket, now) {
  let n = 1;
  try {
    const o = await bucket.get(WAITS);
    const w = o ? JSON.parse(await o.text()) : null;
    if (w && since(w.last, now) < WAIT_GAP_MS) n = (Number(w.n) || 0) + 1;
  } catch { /* counted as the first */ }
  try { await bucket.put(WAITS, JSON.stringify({ n, last: iso(now) }), { httpMetadata: JSON_TYPE }); } catch { /* the ping still says it */ }
  return n;
}

// ---- files -------------------------------------------------------------------
export async function readJSON(bucket, key) {
  const o = await bucket.get(key);
  if (!o) return null;
  try { return JSON.parse(await o.text()); } catch { return null; }
}

export async function putJSON(bucket, key, value) {
  return bucket.put(key, JSON.stringify(value), { httpMetadata: JSON_TYPE });
}

// ---- retention: 30 calendar days ----------------------------------------------
// YouTube's developer policy III.E.4.d keeps its data "not longer than 30
// calendar days": every object under SWEPT last written on a New Hampshire
// day 30 or more days before today is deleted. The votes and test files are
// kept the same span, since the night's record has them by then. Returns how
// many were deleted.
export async function sweep(bucket, now) {
  const oldest = addDays(nh(now).date, -KEEP_DAYS);
  let n = 0;
  for (const prefix of SWEPT) {
    let cursor;
    do {
      const page = await bucket.list({ prefix, cursor });
      const old = page.objects.filter(o => nh(+new Date(o.uploaded)).date <= oldest).map(o => o.key);
      if (old.length) { await bucket.delete(old); n += old.length; }
      cursor = page.truncated ? page.cursor : undefined;
    } while (cursor);
  }
  return n;
}
