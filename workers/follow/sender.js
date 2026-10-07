/*
 * The sender: a scheduled Worker that sends the daily and weekly emails.
 *
 * WHEN. Cron runs it at the top of every hour (wrangler.toml); cron reads UTC
 * and New Hampshire moves between UTC-4 and UTC-5, so no fixed UTC hour is
 * 8:00 there all year. Each run asks what time it is in New Hampshire
 * instead (nhClock), and:
 *   - every run purges requests older than 48 hours and links past their age;
 *   - from 8:00 to 20:00 New Hampshire time, it sends the daily to each daily
 *     subscriber not yet sent that day, and on Saturdays the weekly to each
 *     weekly subscriber not yet sent that day.
 * A subscriber is taken once per New Hampshire day, by an update that marks
 * the row before the email goes and is undone if it fails. So the email comes
 * at the first run at or after 8:00 -- 12:00 UTC in summer, 13:00 in winter --
 * and a later run that day sends only what an earlier one could not.
 *
 * WHAT. It reads the changes files the build publishes (CHANGES_FORMAT.md):
 * tonight's file, the nights since each subscriber's cursor, at most eight,
 * and current.json. If tonight's file is not there yet it waits, run by run,
 * until noon, and after noon sends what it has; either way the log says so.
 * A followed record that has ended is told once, and its follow ends.
 *
 * WHAT IT KEEPS. Counts: the sends table, and log lines that are a code and a
 * number (common.note). No recipient, no record, no follow list.
 */

import { ConfigError, hashToken, openAddress } from "./address.js";
import { addDays, errName, fallbackLabel, keyOf, nhClock, note } from "./common.js";
import { readCurrent, readNight } from "./changes.js";
import { digestEmail, sendMail } from "./mail.js";
import { forget, linkStatement, purge } from "./store.js";

export { nhClock };
export const SEND_FROM_HOUR = 8;      // New Hampshire time
export const SEND_UNTIL_HOUR = 20;    // a backlog past this waits for tomorrow
export const WAIT_UNTIL_HOUR = 12;    // how long to wait for tonight's file
export const NIGHTS_READ = 8;
const PER_RECORD = 20;
const PER_EMAIL = 200;

// What a run at this moment may send, by New Hampshire's clock (common.js).
export function due(now) {
  const c = nhClock(now);
  const open = c.hour >= SEND_FROM_HOUR && c.hour < SEND_UNTIL_HOUR;
  return { ...c, daily: open, weekly: open && c.weekday === "Sat" };
}

// ---- what one subscriber is told -------------------------------------------------------
// nights: the nights read, oldest first. cursor: { date, built } of the newest
// night already sent to this subscriber. Returns one section per followed
// record with something to say (mail.digestEmail's input).
export function collect({ follows, nights, cursor, current, frequency, today }) {
  const sections = [];
  const billsListed = [...current.followable.keys()].some(k => k.startsWith("bill:"));
  const after = t => !!t && !!cursor.built && Date.parse(t) > Date.parse(cursor.built);
  let room = PER_EMAIL;
  for (const f of follows) {
    const key = keyOf(f.kind, f.ref);
    const meta = current.followable.get(key);
    const label = meta?.label || fallbackLabel(f.kind, f.ref);
    const items = [], guids = new Set();
    let study = null, ended = null;
    for (const n of nights) {
      if (cursor.date && n.date < cursor.date) continue;
      // The cursor's own night again only if it was rebuilt since, and then
      // only what that rebuild first saw.
      const same = cursor.date && n.date === cursor.date;
      if (same && !after(n.built)) continue;
      const r = n.refs.get(key);
      if (!r) continue;
      const fresh = x => !same || after(x.seen);
      for (const it of r.items) {
        if (!fresh(it) || guids.has(it.guid)) continue;
        // A topic is followed for the sitting term only.
        if (f.kind === "topic" && it.term !== current.sitting_term) continue;
        guids.add(it.guid);
        items.push(it);
      }
      if (r.study && fresh(r.study)) study = r.study;
      if (r.ended) ended = r.ended;
    }
    // A bill no longer listed as followable, with no ending in any night
    // read: the build should have said how it ended, and did not, or the
    // night that said it is older than the nights read. Tell the follower
    // the bill has stopped, rather than following it in silence for ever.
    // Only while the list names some bill: an empty list is a broken build,
    // not every bill ending at once.
    if (!ended && f.kind === "bill" && billsListed && !meta)
      ended = { how: "gone", summary: `${label} is no longer moving on the record.`,
                fallback: true };
    items.sort((a, b) => b.date.localeCompare(a.date));
    const shown = items.slice(0, Math.min(PER_RECORD, room));
    room -= shown.length;
    const week = frequency === "weekly" && f.kind === "bill"
      ? { votes: items.filter(i => i.kind === "vote").length,
          exec: items.filter(i => i.kind === "exec").length }
      : null;
    const upcoming = frequency === "weekly"
      ? (current.upcoming.get(key) || []).filter(u => u.date >= today).slice(0, 5) : [];
    if (!items.length && !study && !ended && !upcoming.length) continue;
    sections.push({ key, kind: f.kind, ref: f.ref, label, title: meta?.title || "",
      url: meta?.url || "", items: shown, more: items.length - shown.length,
      study, ended, week, upcoming });
  }
  return sections;
}

// ---- one run ------------------------------------------------------------------------------
const sleep = ms => new Promise(r => setTimeout(r, ms));

function siteOrigin(env) {
  const o = String(env.SITE_ORIGIN || "").replace(/\/+$/, "");
  return /^https:\/\/[A-Za-z0-9.-]+(:\d+)?$/.test(o) ||
    /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(o) ? o : "";
}

export async function run(env, now = new Date()) {
  const out = { purged: 0, sent: 0, failed: 0, ended: 0, waiting: 0, skipped: 0 };
  const db = env.FOLLOW_DB;
  const origin = siteOrigin(env);
  if (!db || !origin) { note("sender.config"); return out; }

  try {
    const p = await purge(db, now);
    out.purged = p.pending;
    if (p.pending) note("sender.purged", p.pending);
  } catch (e) {
    note(`sender.purge-failed.${errName(e)}`);
  }

  const when = due(now);
  if (!when.daily) return out;
  const freqs = when.weekly ? ["daily", "weekly"] : ["daily"];
  const limit = Math.max(1, Math.min(1000, Number(env.SEND_LIMIT) || 40));
  const subs = (await db.prepare(
    "SELECT id, email_hmac, email_enc, frequency, last_sent_on, sent_date, sent_built " +
    `FROM subscribers WHERE frequency IN (${freqs.map((_, i) => `?${i + 3}`).join(", ")}) ` +
    "AND (last_sent_on IS NULL OR last_sent_on < ?1) ORDER BY id LIMIT ?2")
    .bind(when.date, limit, ...freqs).all()).results || [];
  if (!subs.length) return out;

  // The site, asked afresh each run: a night's file is new each morning.
  const get = path => fetch(`${origin}${path}?run=${now.getTime()}`,
    { headers: { Accept: "application/json" } });
  const cur = await readCurrent(get);
  if (!cur.value) {
    note(cur.missing ? "sender.current-missing" : "sender.current-unreadable", subs.length);
    out.waiting = subs.length;
    return out;
  }
  let mended = cur.notes || 0;

  const nights = new Map();
  const tonight = await readNight(get, when.date);
  if (tonight.value) {
    nights.set(when.date, tonight.value);
    mended += tonight.notes || 0;
  } else {
    if (tonight.bad) note("sender.night-unreadable", 1);
    if (when.hour < WAIT_UNTIL_HOUR) {
      note("sender.waiting-for-tonight", subs.length);
      out.waiting = subs.length;
      return out;
    }
    note("sender.tonight-missing-sending-anyway", subs.length);
  }
  const floor = addDays(when.date, -(NIGHTS_READ - 1));
  const oldest = subs.reduce((m, s) => (s.sent_date && s.sent_date < m ? s.sent_date : m),
    when.date);
  let missing = 0;
  for (let d = oldest < floor ? floor : oldest; d < when.date; d = addDays(d, 1)) {
    const r = await readNight(get, d);
    if (r.value) { nights.set(d, r.value); mended += r.notes || 0; }
    else { missing++; if (r.bad) note("sender.night-unreadable", 1); }
  }
  if (missing) note("sender.nights-missing", missing);
  if (mended) note("sender.entries-dropped-or-mended", mended);
  const ordered = [...nights.values()].sort((a, b) => a.date.localeCompare(b.date));
  const newest = ordered[ordered.length - 1] || null;

  const tally = { daily: { sent: 0, items: 0, failed: 0, ended: 0 },
                  weekly: { sent: 0, items: 0, failed: 0, ended: 0 } };
  const gap = Math.max(0, Number(env.SEND_GAP_MS ?? 600) || 0);
  let stop = false;

  for (const s of subs) {
    if (stop) break;
    // Take the row for today, once: a run that overlaps this one finds it taken.
    const took = await db.prepare(
      "UPDATE subscribers SET last_sent_on = ?1 WHERE id = ?2 " +
      "AND (last_sent_on IS NULL OR last_sent_on < ?1)").bind(when.date, s.id).run();
    if (!took?.meta?.changes) { out.skipped++; continue; }
    const giveBack = () => db.prepare("UPDATE subscribers SET last_sent_on = ?1 WHERE id = ?2")
      .bind(s.last_sent_on ?? null, s.id).run();
    const moveCursor = newest
      ? db.prepare("UPDATE subscribers SET sent_date = ?1, sent_built = ?2 WHERE id = ?3")
          .bind(newest.date, newest.built, s.id)
      : null;
    let made = [];
    try {
      const follows = (await db.prepare(
        "SELECT kind, ref FROM follows WHERE subscriber_id = ?1 ORDER BY kind, ref")
        .bind(s.id).all()).results || [];
      const sections = collect({ follows, nights: ordered,
        cursor: { date: s.sent_date || "", built: s.sent_built || "" },
        current: cur.value, frequency: s.frequency, today: when.date });
      if (!sections.length) {
        if (moveCursor) await moveCursor.run();
        continue;
      }
      const ending = sections.filter(x => x.ended);
      // Every follow ends in this email: the address goes with them, and the
      // email says so rather than carrying links that will not work.
      const gone = ending.length > 0 && ending.length === follows.length;
      let manage = "", unsub = "";
      if (!gone) {
        const [m, ms] = await linkStatement(db, s.id, "manage", now);
        const [u, us] = await linkStatement(db, s.id, "unsubscribe", now);
        await db.batch([ms, us]);
        manage = m; unsub = u;
        made = [m, u];
      }
      const to = await openAddress(env, s.email_enc, s.email_hmac);
      const mail = digestEmail({ origin, frequency: s.frequency, date: when.date, sections,
        manage, unsub, feedbackUrl: env.FEEDBACK_URL, gone });
      const r = await sendMail(env, { to, ...mail });
      if (!r.ok) {
        tally[s.frequency].failed++;
        out.failed++;
        await giveBack();
        if (made.length) await forgetLinks(db, made);
        note(`sender.resend-refused.${r.status}`, 1);
        // Resend's rate limit or daily cap: the rest wait for the next run.
        if (r.status === 429) stop = true;
        continue;
      }
      const after = moveCursor ? [moveCursor] : [];
      for (const x of ending)
        after.push(db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND kind = ?2 " +
          "AND ref = ?3").bind(s.id, x.kind, x.ref));
      if (after.length) await db.batch(after);
      if (gone) await forget(db, { id: s.id });
      const t = tally[s.frequency];
      t.sent++; t.ended += ending.length;
      t.items += sections.reduce((n, x) => n + x.items.length + x.more, 0);
      out.sent++; out.ended += ending.length;
    } catch (e) {
      out.failed++;
      tally[s.frequency].failed++;
      note(`sender.error.${errName(e)}`, 1);
      try { await giveBack(); if (made.length) await forgetLinks(db, made); } catch { /* counted */ }
      if (e instanceof ConfigError) stop = true;
      continue;
    }
    if (gap) await sleep(gap);
  }

  for (const [frequency, t] of Object.entries(tally)) {
    if (!t.sent && !t.failed) continue;
    await db.prepare(
      "INSERT INTO sends (date, frequency, emails_sent, items, failed, ended) " +
      "VALUES (?1, ?2, ?3, ?4, ?5, ?6) ON CONFLICT(date, frequency) DO UPDATE SET " +
      "emails_sent = emails_sent + excluded.emails_sent, items = items + excluded.items, " +
      "failed = failed + excluded.failed, ended = ended + excluded.ended")
      .bind(when.date, frequency, t.sent, t.items, t.failed, t.ended).run();
  }
  if (out.sent) note("sender.sent", out.sent);
  if (out.failed) note("sender.failed", out.failed);
  if (out.ended) note("sender.follows-ended", out.ended);
  return out;
}

async function forgetLinks(db, tokens) {
  const hashes = await Promise.all(tokens.map(hashToken));
  await db.batch(hashes.map(h => db.prepare("DELETE FROM links WHERE token_hash = ?1").bind(h)));
}

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(run(env, new Date(controller.scheduledTime))
      .catch(e => note(`sender.run-failed.${errName(e)}`)));
  },
  // No address answers: the sender has no route, and a request gets nothing.
  async fetch() {
    return new Response("Not found\n", { status: 404 });
  },
};
