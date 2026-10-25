/*
 * The sender: a scheduled Worker that sends the daily and weekly emails.
 *
 * WHEN. Cron runs it at the top of every hour (wrangler.toml); cron reads UTC
 * and New Hampshire moves between UTC-4 and UTC-5, so no fixed UTC hour is
 * 8:00 there all year. Each run asks what time it is in New Hampshire
 * instead (nhClock), and:
 *   - every run purges requests older than 48 hours and addresses left
 *     following nothing;
 *   - from 8:00 to 20:00 New Hampshire time, it sends the daily to each daily
 *     subscriber not yet sent that day, and on Saturdays the weekly to each
 *     weekly subscriber not yet sent that day -- and on any later day to a
 *     weekly subscriber whose Saturday did not go (WEEKLY CATCH-UP, below).
 * A subscriber is taken once per New Hampshire day, by an update that marks
 * the row before the email goes, and is given back only if the email did not
 * go. So the email comes at the first run at or after 8:00 -- 12:00 UTC in
 * summer, 13:00 in winter -- and a later run that day sends only what an
 * earlier one could not.
 *
 * WHO FIRST. The reader served least recently, then by id: a refusal (Resend's
 * daily cap, its rate limit) gives the day back, so a reader refused today is
 * first tomorrow, and no reader is left behind for ever by a lasting cap.
 *
 * HOW MUCH A RUN DOES. At most SEND_LIMIT emails (each is a request out of the
 * Worker), and at most D1_QUERIES_PER_RUN database statements, counted one by
 * one, a batch's included: a run stops taking readers before the next could
 * pass either, and the next hour's run carries on.
 *
 * WHAT. It reads the changes files the build publishes (CHANGES_FORMAT.md):
 * tonight's file, the nights since each subscriber's cursor, at most eight,
 * and current.json. If tonight's file is not there yet it waits, run by run,
 * until noon, and after noon sends what it has; either way the log says so.
 * A followed record that has ended is told once, and its follow ends.
 *
 * WHAT IT KEEPS. Counts: the sends table, and log lines that are a code and a
 * number (common.note). No recipient, no record, no follow list.
 *
 * WHO IS TOLD WHEN IT BREAKS (22 October 2026, the review before go-live).
 * Every run ends with a ping to HEALTHCHECK_URL, a secret, as the nightly
 * pings its own: a plain ping for a run that did its work or had none, and
 * /fail, with the run's codes and counts as the body, for one that met a
 * problem a person must act on (PROBLEMS). An hourly ping is also the
 * sender's heartbeat: Healthchecks writes when the pings stop. With no
 * secret, no ping. The body carries counts and codes, never an address.
 *
 * ONE ADDRESS, ON THE PREVIEW ONLY: POST /test-send (A TEST SEND, below),
 * which sends the person test emails on request and records nothing. Every
 * other request, and every request at all to the production sender, is the
 * 404 it has always been.
 */

import { ConfigError, linksFor, openAddress, openFollow, sameText, sealFollow } from "./address.js";
import { addDays, chamberOf, clock, errName, fallbackLabel, json, keyOf, nhClock, note, parseKey,
         readCapped } from "./common.js";
import { readCurrent, readNight } from "./changes.js";
import { digestEmail, nothingNewEmail, pageNames, sendMail, welcomeEmail } from "./mail.js";
import { countConfirmed, forget, purge } from "./store.js";

export { nhClock };
export const SEND_FROM_HOUR = 8;      // New Hampshire time
export const SEND_UNTIL_HOUR = 20;    // a backlog past this waits for tomorrow
export const WAIT_UNTIL_HOUR = 12;    // how long to wait for tonight's file
// Ten nights, so a weekly that went a day or two after its Saturday (WEEKLY
// CATCH-UP) still reaches back to the night after the last one it carried.
export const NIGHTS_READ = 10;
const PER_RECORD = 20;
// A followed legislator's roll calls are listed whole (the person, 11 October
// 2026: "all roll call votes they made the previous week"), up to the sixty a
// member's feed carries; the rest of a record's items stay at PER_RECORD.
const PER_MEMBER_VOTES = 60;
const PER_EMAIL = 200;
// A pause "until I turn it back on" is kept as this date (schema.sql).
export const PAUSED_FOR_GOOD = "9999-12-31";

// D1's limit on queries one Worker invocation may run: 50 on the Workers Free
// plan and 1,000 on Workers Paid, by Cloudflare's D1 limits page
// (developers.cloudflare.com/d1/platform/limits/, read 25 October 2026).
// That page counts a db.batch() as one; this counts each statement in it, the
// safe side. D1_QUERIES_PER_RUN sets the figure a run keeps to (README.md,
// "The plan's limits"). The most one reader costs is PER_READER: taking the
// row, reading its follows, and then the cursor and the ended follows, or the
// address's deletion when its last follow ends. RESERVE is the sends rows.
export const D1_QUERIES = 50;
export const PER_READER = 5;
const RESERVE = 2;
const IN_CHUNK = 90;                  // D1 binds at most 100 values a statement

// What a run at this moment may send, by New Hampshire's clock (common.js).
export function due(now) {
  const c = nhClock(now);
  const open = c.hour >= SEND_FROM_HOUR && c.hour < SEND_UNTIL_HOUR;
  return { ...c, daily: open, weekly: open && c.weekday === "Sat" };
}

// WEEKLY CATCH-UP (22 October 2026). A weekly reader's day is Saturday; one
// whose Saturday did not go -- Resend refused it all day, the sender was down
// -- was left until the next Saturday, and the week between was dropped when
// the nights read no longer reached back to it. Now a weekly reader last sent
// eight or more days ago is due on any day in the sending hours. A reader
// never yet sent waits for a Saturday, as before.
export const WEEKLY_CATCH_UP_DAYS = 8;

// A run's problems a person must act on: each makes the Healthchecks ping a
// /fail. Waiting for tonight's file before noon is no problem; still waiting
// at noon is one.
export const PROBLEMS = {
  config: "the sender's configuration is missing",
  "site-follow": "the site's follow pages do not answer, so nothing was sent",
  current: "the site's current.json is missing or unreadable",
  tonight: "tonight's changes file was still missing at noon",
  "resend-auth": "Resend refused the key or the sending domain",
  "resend-rate": "Resend's rate limit stopped the run",
  "resend-down": "Resend failed three times in a row, so the run stopped",
  "all-refused": "every email this run tried was refused",
  "run-failed": "the run stopped on an error of its own",
};

// A D1 binding that counts every statement it runs, a batch's one by one.
export function counting(db) {
  const count = { n: 0 };
  const wrap = st => ({
    bind: (...a) => wrap(st.bind(...a)),
    first: (...a) => { count.n++; return st.first(...a); },
    all: () => { count.n++; return st.all(); },
    run: () => { count.n++; return st.run(); },
    raw: () => { count.n++; return st.raw(); },
    statement: st,
  });
  return {
    count,
    prepare: sql => wrap(db.prepare(sql)),
    batch: stmts => { count.n += stmts.length; return db.batch(stmts.map(s => s.statement)); },
  };
}

// ---- what one subscriber is told -------------------------------------------------------
// A followed record no longer listed as followable, with no ending in any
// night read: the build should have said how it ended, and did not, or the
// night that said it is older than the nights read. The follower is told the
// record has stopped, rather than followed in silence for ever -- but only
// while the list names some record of that kind, because an empty list is a
// broken build, not every bill or member ending at once. A topic is not
// ended this way: it leaves the list when no bill of the sitting term
// carries it (at the turn of a term, before the new bills are in), and comes
// back when one does, so its follow is kept.
const STOPPED = {
  bill: "is no longer moving on the record.",
  member: "is no longer among the sitting legislators on the record.",
  committee: "is no longer among the committees on the record.",
};

// TESTIFY ON A BILL (the person, 22 October 2026: "emails include updates for
// when testimony has opened for a certain bill and when it closes, with a
// similar button to click to go straight to the testify page"). Each
// chamber's online sign-in opens for a bill once its public hearing is
// scheduled (the Senate's guidance of 2021) and, in practice, stays open
// until midnight at the end of the hearing's day (the editor's account, an
// observed() claim in guides.py: no document on record states it). So a
// bill a reader follows says so three times, the person chose: when the
// hearing is newly scheduled ("open", the night's own news), and, to a daily
// reader, the morning before the hearing ("eve") and the morning of it
// ("day"), whether or not anything else is new. A weekly reader has it in the
// week ahead. The hearing is current.json's -- what is still scheduled as of
// last night -- and a hearing whose committee names no chamber has no form to
// send anyone to, so it is not said.
//
// ahead: a test send's (A TEST SEND, below), never a run's. A bill with a
// public hearing still to come says "open" on any day, so that a test shows
// the block wherever a followed bill has one ahead, not only on the three
// mornings a real email says it.
//
// The House calls its hearings "public hearing" and the Senate "hearing"
// (the audit of 25 October 2026, M2): both are the one meeting that takes
// testimony, and this read the House's alone.
const PUBLIC_HEARING = /^(public )?hearing$/i;
export function testifyFor(kind, upcoming, items, frequency, today, ahead = false) {
  if (kind !== "bill") return null;
  const next = (upcoming || [])
    .filter(u => PUBLIC_HEARING.test(u.what || "") && u.date >= today && chamberOf(u.committee))
    .sort((a, b) => (a.date + (a.time || "")).localeCompare(b.date + (b.time || "")))[0];
  if (!next) return null;
  const daily = frequency !== "weekly";
  const phase = daily && next.date === today ? "day"
    : daily && next.date === addDays(today, 1) ? "eve"
    : items.some(it => it.meeting && PUBLIC_HEARING.test(it.meeting.what || "") &&
        it.meeting.date === next.date && it.meeting.state !== "cancelled") ? "open"
    : ahead ? "open" : "";
  return phase ? { phase, chamber: chamberOf(next.committee), date: next.date,
                   time: next.time || "", committee: next.committee, venue: next.venue || "" } : null;
}

// nights: the nights read, oldest first. cursor: { date, built } of the newest
// night already sent to this subscriber. follows: [{ kind, ref, fh }]. detail:
// "all", or "milestones" for the items CHANGES_FORMAT.md marks so. Returns one
// section per followed record with something to say (mail.digestEmail's
// input); a member's ballots come apart from its other items, as `votes`.
// testifyAhead: a test send's alone (testifyFor's `ahead`); run() never
// passes it.
export function collect({ follows, nights, cursor, current, frequency, today, detail = "all",
                          testifyAhead = false }) {
  const sections = [];
  const listed = new Set([...current.followable.keys()].map(k => k.slice(0, k.indexOf(":"))));
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
        if (detail === "milestones" && !it.milestone) continue;
        guids.add(it.guid);
        items.push(it);
      }
      if (r.study && fresh(r.study)) study = r.study;
      if (r.ended) ended = r.ended;
    }
    if (!ended && !meta && Object.hasOwn(STOPPED, f.kind) && listed.has(f.kind))
      ended = { how: "gone", summary: `${label} ${STOPPED[f.kind]}`, fallback: true };
    items.sort((a, b) => b.date.localeCompare(a.date));
    const ballots = f.kind === "member" ? items.filter(i => i.vote) : [];
    const rest = ballots.length ? items.filter(i => !i.vote) : items;
    const votes = ballots.slice(0, Math.min(PER_MEMBER_VOTES, room));
    room -= votes.length;
    const shown = rest.slice(0, Math.min(PER_RECORD, room));
    room -= shown.length;
    // "This week" is the seven days to today (22 October 2026): an old
    // executive session newly on the record, or one still to come, was
    // counted as this week's.
    const thisWeek = i => i.date <= today && i.date > addDays(today, -7);
    const week = frequency === "weekly" && f.kind === "bill"
      ? { votes: items.filter(i => i.kind === "vote" && thisWeek(i)).length,
          exec: items.filter(i => i.kind === "exec" && thisWeek(i)).length }
      : null;
    const upcoming = frequency === "weekly"
      ? (current.upcoming.get(key) || []).filter(u => u.date >= today).slice(0, 5) : [];
    const testify = testifyFor(f.kind, current.upcoming.get(key), items, frequency, today,
      testifyAhead);
    if (!items.length && !study && !ended && !upcoming.length && !testify) continue;
    sections.push({ key, kind: f.kind, ref: f.ref, fh: f.fh, label, title: meta?.title || "",
      now: meta?.now || "", url: meta?.url || "", items: shown, votes,
      more: items.length - shown.length - votes.length, study, ended, week, upcoming, testify });
  }
  return sections;
}

// A READER BACK FROM A PAUSE hears what is new since it ended, not the news
// of the days they asked not to be sent: the cursor moves to the end of the
// pause's last day where it is older than that.
export function resumeFrom(s) {
  const cursor = { date: s.sent_date || "", built: s.sent_built || "" };
  const p = s.paused_until || "";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(p) || p === PAUSED_FOR_GOOD) return cursor;
  return cursor.date && cursor.date > p ? cursor : { date: p, built: `${p}T23:59:59Z` };
}

// ---- one run ------------------------------------------------------------------------------
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Resend's answers, by what the run does with them (22 October 2026). A key or
// a domain refused is the configuration, not the reader: the run stops. A
// request it calls bad (400, 422: an address it will not take) is the
// reader's: the day stays taken, so the reader waits until tomorrow at the
// back of the line rather than at the front of every hour, and is never
// deleted for it -- a bug of ours could make every request bad. Anything else
// (5xx, a lost answer) gives the day back, as before.
const AUTH = new Set([401, 403]);
const READERS_OWN = new Set([400, 422]);
const DOWN_IN_A_ROW = 3;

function siteOrigin(env) {
  const o = String(env.SITE_ORIGIN || "").replace(/\/+$/, "");
  return /^https:\/\/[A-Za-z0-9.-]+(:\d+)?$/.test(o) ||
    /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(o) ? o : "";
}

// THE WAY OUT FIRST (run(), below): the status the site's count page answers,
// 0 for none at all.
async function followPagesLive(origin, now) {
  try {
    return (await fetch(`${origin}/api/follow/count?run=${now.getTime()}`,
      { headers: { Accept: "application/json" } })).status;
  } catch { return 0; }
}

// The site, asked afresh each run: a night's file is new each morning.
const siteGet = (origin, now) => path => fetch(`${origin}${path}?run=${now.getTime()}`,
  { headers: { Accept: "application/json" } });

// A reader's follows, opened. One that will not open is left out and counted.
async function followsOf(env, db, s) {
  const rows = (await db.prepare(
    "SELECT follow_hmac, follow_enc FROM follows WHERE subscriber_id = ?1").bind(s.id).all())
    .results || [];
  const out = [];
  for (const r of rows) {
    try {
      const k = parseKey(await openFollow(env, r.follow_enc, s.email_hmac));
      if (k) out.push({ ...k, fh: r.follow_hmac });
    } catch { /* counted below */ }
  }
  if (out.length < rows.length) note("sender.unreadable-follow", rows.length - out.length);
  out.sort((a, b) => keyOf(a.kind, a.ref).localeCompare(keyOf(b.kind, b.ref)));
  // ONE SECTION A RECORD. A bill request moved onto its bill keeps the
  // request's fingerprint until the manage page mends it, so a reader who
  // then signs up for the same bill holds it twice for a while.
  const once = out.filter((f, i) => i === 0 || keyOf(f.kind, f.ref) !== keyOf(out[i - 1].kind, out[i - 1].ref));
  return { follows: once, held: rows.length };
}

export async function run(env, now = new Date()) {
  const out = { purged: 0, sent: 0, failed: 0, ended: 0, waiting: 0, skipped: 0, queries: 0,
                problems: [] };
  const origin = siteOrigin(env);
  if (!env.FOLLOW_DB || !origin) { note("sender.config"); out.problems.push("config"); return out; }
  const db = counting(env.FOLLOW_DB);
  const budget = Math.max(PER_READER + RESERVE + 5,
    Number(env.D1_QUERIES_PER_RUN) || D1_QUERIES);
  const done = () => { out.queries = db.count.n; return out; };

  try {
    const p = await purge(db, now);
    out.purged = p.pending;
    if (p.pending) note("sender.purged", p.pending);
  } catch (e) {
    note(`sender.purge-failed.${errName(e)}`);
  }

  const when = due(now);
  if (!when.daily) return done();
  const limit = Math.max(1, Math.min(1000, Number(env.SEND_LIMIT) || 40));
  const subs = (await db.prepare(
    "SELECT id, email_hmac, email_enc, frequency, link_gen, last_sent_on, sent_date, sent_built, " +
    "paused_until, detail " +
    "FROM subscribers WHERE (frequency = 'daily' OR (frequency = 'weekly' AND " +
    "(?3 = 1 OR (last_sent_on IS NOT NULL AND last_sent_on <= ?4)))) " +
    "AND (last_sent_on IS NULL OR last_sent_on < ?1) " +
    // PAUSED THROUGH A DAY: nothing goes until the day after it.
    "AND (paused_until IS NULL OR paused_until < ?1) " +
    "ORDER BY last_sent_on IS NOT NULL, last_sent_on, id LIMIT ?2")
    .bind(when.date, limit, when.weekly ? 1 : 0,
          addDays(when.date, -WEEKLY_CATCH_UP_DAYS)).all()).results || [];
  if (!subs.length) return done();
  if (!when.weekly && subs.some(s => s.frequency === "weekly"))
    note("sender.weekly-catch-up", subs.filter(s => s.frequency === "weekly").length);

  // THE WAY OUT FIRST. Every email links to the manage and unsubscribe pages,
  // which are the site's Functions and answer 404 while the site has no follow
  // database bound: a deploy that lost the binding would leave readers mailed
  // with links that do nothing. The count is the cheapest of those pages.
  const live = await followPagesLive(origin, now);
  if (live !== 200) {
    note(`sender.site-follow-missing.${live}`, subs.length);
    out.problems.push("site-follow");
    out.waiting = subs.length;
    return done();
  }

  const get = siteGet(origin, now);
  const cur = await readCurrent(get);
  if (!cur.value) {
    note(cur.missing ? "sender.current-missing" : "sender.current-unreadable", subs.length);
    out.problems.push("current");
    out.waiting = subs.length;
    return done();
  }
  let mended = cur.notes || 0;
  // Every page an email can link a name to, read once for the run (mail.js,
  // pageNames): the person asked, 17 October 2026, for every bill an email
  // names to link to its page.
  const names = pageNames(cur.value);

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
      return done();
    }
    note("sender.tonight-missing-sending-anyway", subs.length);
    out.problems.push("tonight");
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
  // A reader whose cursor is older than the oldest night read is sent what
  // the nights read hold, and the rest is not theirs to have: said, not hidden.
  const beyond = subs.filter(s => s.sent_date && s.sent_date < floor).length;
  if (beyond) note("sender.cursor-beyond-window", beyond);
  if (mended) note("sender.entries-dropped-or-mended", mended);
  const ordered = [...nights.values()].sort((a, b) => a.date.localeCompare(b.date));
  const newest = ordered[ordered.length - 1] || null;

  const tally = { daily: { sent: 0, items: 0, failed: 0, ended: 0 },
                  weekly: { sent: 0, items: 0, failed: 0, ended: 0 } };
  const gap = Math.max(0, Number(env.SEND_GAP_MS ?? 600) || 0);
  let stop = false;
  let downInARow = 0;

  for (const [i, s] of subs.entries()) {
    if (stop) break;
    if (db.count.n + PER_READER + RESERVE > budget) {
      note("sender.query-budget-reached", subs.length - i);
      break;
    }
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

    // ---- before the email: anything that fails gives the day back --------------------
    let sections, ending, gone, moved = [];
    try {
      const { follows, held } = await followsOf(env, db, s);
      sections = collect({ follows, nights: ordered, cursor: resumeFrom(s),
        current: cur.value, frequency: s.frequency, today: when.date, detail: s.detail });
      if (!sections.length) {
        if (moveCursor) await moveCursor.run();
        continue;
      }
      // A BILL REQUEST DRAFTED INTO A BILL is not an ending: its follow moves
      // onto the bill (build_feeds, BILL REQUESTS), so it neither ends the
      // follow nor counts toward the address going.
      ending = sections.filter(x => x.ended && !x.ended.becomes);
      moved = sections.filter(x => x.ended && x.ended.becomes)
        .map(x => ({ fh: x.fh, to: x.ended.becomes,
                     had: follows.some(f => keyOf(f.kind, f.ref) === x.ended.becomes) }));
      // Every follow ends in this email: the address goes with them, and the
      // email says so rather than carrying links that will not work.
      gone = ending.length > 0 && ending.length === held;
      const links = gone ? { manage: "", unsub: "" } : await linksFor(env, s.email_hmac, s.link_gen);
      const to = await openAddress(env, s.email_enc, s.email_hmac);
      const mail = digestEmail({ origin, frequency: s.frequency, date: when.date, sections,
        manage: links.manage, unsub: links.unsub, feedbackUrl: env.FEEDBACK_URL, gone, names });
      // ONE EMAIL A READER A DAY, EVEN IF AN ANSWER IS LOST (15 October 2026).
      // Resend can take an email and the answer never arrive; the day was then
      // given back and the next run sent it again. The key is the reader's row
      // and the day, so Resend sends the second request's email only if it has
      // none under that key from the last 24 hours. Its 409 is that refusal:
      // an email under this key is with Resend already, so the day stays taken
      // and the bookkeeping below runs as for any email sent.
      const r = await sendMail(env, { to, ...mail }, `digest/${when.date}/${s.frequency}/${s.id}`);
      if (!r.ok && r.status === 409) {
        note("sender.resend-already-has-it", 1);
      } else if (!r.ok) {
        tally[s.frequency].failed++;
        out.failed++;
        note(`sender.resend-refused.${r.status}`, 1);
        if (READERS_OWN.has(r.status)) continue;      // the day stays taken
        await giveBack();
        if (AUTH.has(r.status)) {
          stop = true;
          out.problems.push("resend-auth");
        } else if (r.status === 429) {
          // Resend's rate limit, after sendMail's one wait and retry: the
          // rest wait for the next run.
          stop = true;
          out.problems.push("resend-rate");
        } else if (++downInARow >= DOWN_IN_A_ROW) {
          stop = true;
          out.problems.push("resend-down");
        }
        continue;
      }
      downInARow = 0;
    } catch (e) {
      out.failed++;
      tally[s.frequency].failed++;
      note(`sender.error.${errName(e)}`, 1);
      try { await giveBack(); } catch { /* counted */ }
      if (e instanceof ConfigError) { stop = true; out.problems.push("config"); }
      continue;
    }

    // ---- the email has gone ---------------------------------------------------------------
    // Nothing from here gives the day back: the reader has the email, and its
    // links are their links. What is left is bookkeeping -- the cursor, and the
    // follows that ended -- tried twice; if both fail, the log says so, today
    // is still taken, and tomorrow's email carries this one's news again
    // rather than none.
    const t = tally[s.frequency];
    t.sent++; t.ended += ending.length;
    t.items += sections.reduce((n, x) => n + x.items.length + x.more, 0);
    out.sent++; out.ended += ending.length;
    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        if (gone) {
          await forget(db, { id: s.id });
        } else {
          const writes = moveCursor ? [moveCursor] : [];
          for (let j = 0; j < ending.length; j += IN_CHUNK) {
            const part = ending.slice(j, j + IN_CHUNK);
            writes.push(db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND follow_hmac IN (" +
              part.map((_, k) => `?${k + 2}`).join(", ") + ")").bind(s.id, ...part.map(x => x.fh)));
          }
          // The request's row now holds its bill, sealed as any follow is;
          // one already followed has the request's row dropped instead.
          for (const m of moved) {
            writes.push(m.had
              ? db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND follow_hmac = ?2").bind(s.id, m.fh)
              : db.prepare("UPDATE follows SET follow_enc = ?1 WHERE subscriber_id = ?2 AND follow_hmac = ?3")
                  .bind(await sealFollow(env, m.to, s.email_hmac), s.id, m.fh));
          }
          if (moved.length) note("sender.requests-moved-to-bills", moved.length);
          if (writes.length) await db.batch(writes);
        }
        break;
      } catch (e) {
        if (attempt === 2) note(`sender.after-send-failed.${errName(e)}`, 1);
      }
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
  if (out.failed && !out.sent && !out.problems.length) out.problems.push("all-refused");
  if (out.ended) note("sender.follows-ended", out.ended);
  return done();
}

// The run's ping (WHO IS TOLD WHEN IT BREAKS, above): codes and counts only.
export async function ping(env, out) {
  const url = String(env.HEALTHCHECK_URL || "").trim().replace(/\/+$/, "");
  if (!/^https:\/\/[^\s]+$/.test(url)) return false;
  const bad = out.problems.length > 0;
  const body = [
    ...out.problems.map(p => `problem: ${p}: ${PROBLEMS[p] || p}`),
    ["sent", "failed", "waiting", "ended", "skipped", "purged", "queries"]
      .map(k => `${k} ${out[k] || 0}`).join(", "),
  ].join("\n");
  try {
    const r = await fetch(url + (bad ? "/fail" : ""), { method: "POST", body });
    try { await r.body?.cancel(); } catch { /* nothing to read */ }
    return r.ok;
  } catch {
    note("sender.healthcheck-unreachable");
    return false;
  }
}

// ---- A TEST SEND, ON THE PREVIEW ONLY ---------------------------------------------------
// The person, 23 October 2026: "Is there a way you can manually trigger
// sending me test emails since my account is already signed up for updates
// on a number of bills and topics? That way I can give quicker feedback
// rather than needing updates to occur nightly."
//
// POST /test-send. For each confirmed subscriber in this Worker's database --
// the first TEST_SEND_MOST by id; the answer says how many more were left --
// it builds the daily, the weekly and the "You're following" email with the
// sender's own collect(), digestEmail() and welcomeEmail(), over the last
// nights of the site's /changes/ files, and sends each through sendMail with
// "[Test] " before its subject and an Idempotency-Key of its own. A digest
// with nothing in those nights is sent as a short note saying so
// (mail.nothingNewEmail), where a real run would send nothing.
//
// IT RECORDS NOTHING. It reads the subscribers and their follows and writes
// no row: not last_sent_on, not the cursor (sent_date, sent_built), not the
// sends table, not signup_days, and no follow ends. A reader paused today is
// left out, as run() leaves them. Its answer is counts and its log is codes
// and counts, as every other; neither carries an address.
//
// TWO GUARDS, BOTH OR NOTHING. TEST_SEND = "on", a plain var that only
// [env.preview.vars] in wrangler.toml sets; and TEST_SEND_TOKEN, a secret the
// person sets on the preview Worker alone, which the request's
// "Authorization: Bearer" must match (address.js sameText, in constant time).
// Without both, /test-send is the 404 every address has always been. The
// production sender has neither, and no address to be asked at
// (workers_dev = false, no route); preflight's _follow_test_send holds the
// configuration to that, and tests/follow/test_send.test.js the rest.
export const TEST_PATH = "/test-send";
export const TEST_SEND_MOST = 5;
export const TEST_KINDS = ["daily", "weekly", "welcome"];
export const TEST_NIGHTS = 7;
export const TEST_NIGHTS_MOST = 10;
export const TEST_PREFIX = "[Test] ";
// A token shorter than this is no token: the README's is 44 characters.
const TEST_TOKEN_LEAST = 32;
const TEST_BODY_MOST = 256;
const TEST_EXPECTS = 'no body, or {"kinds": ["daily", "weekly", "welcome"], "nights": 1 to 10}';

const notFound = () => new Response("Not found\n", { status: 404 });

// Both guards, the path and the method, or false.
export function testSendAllowed(request, env) {
  if (env?.TEST_SEND !== "on") return false;
  const want = String(env.TEST_SEND_TOKEN ?? "").trim();
  if (want.length < TEST_TOKEN_LEAST) return false;
  let path;
  try { path = new URL(request.url).pathname; } catch { return false; }
  if (request.method !== "POST" || path !== TEST_PATH) return false;
  const m = /^Bearer[ \t]+(\S+)[ \t]*$/i.exec(request.headers.get("Authorization") || "");
  return !!m && sameText(m[1], want);
}

// What was asked: nothing (every kind, TEST_NIGHTS nights), or
// {"kinds": [...], "nights": n}. null for anything else, a body over
// TEST_BODY_MOST bytes included.
export function testAsk(raw) {
  if (raw === null || raw === undefined) return null;
  if (!String(raw).trim()) return { kinds: [...TEST_KINDS], nights: TEST_NIGHTS };
  let o;
  try { o = JSON.parse(raw); } catch { return null; }
  if (!o || typeof o !== "object" || Array.isArray(o) ||
      Object.keys(o).some(k => k !== "kinds" && k !== "nights")) return null;
  const kinds = o.kinds ?? TEST_KINDS, nights = o.nights ?? TEST_NIGHTS;
  if (!Array.isArray(kinds) || !kinds.length || kinds.length > 10 ||
      kinds.some(k => !TEST_KINDS.includes(k))) return null;
  if (!Number.isInteger(nights) || nights < 1 || nights > TEST_NIGHTS_MOST) return null;
  return { kinds: TEST_KINDS.filter(k => kinds.includes(k)), nights };
}

// The send: [status, answer]. The answer is counts, dates and fixed words.
export async function testSend(env, now, { kinds, nights }) {
  const out = { ok: false, date: "", nights, nights_read: 0, kinds, subscribers: 0, taken: 0,
    sent: 0, emails: Object.fromEntries(kinds.map(k => [k, 0])), nothing_new: 0, testify: 0,
    skipped: {}, failed: {}, notes: [] };
  const add = (o, k) => { o[k] = (o[k] || 0) + 1; };
  const origin = siteOrigin(env);
  if (!env.FOLLOW_DB || !origin) return [503, { ...out, why: "config" }];
  if (await followPagesLive(origin, now) !== 200) return [503, { ...out, why: "site-follow" }];
  const get = siteGet(origin, now);
  const cur = await readCurrent(get);
  if (!cur.value) return [503, { ...out, why: "current" }];
  // The site's newest night, which the emails are as of: a preview that has
  // not been deployed for some days still has its nights to show.
  const today = cur.value.date;
  out.date = today;
  const read = [];
  for (let d = addDays(today, -(nights - 1)); d <= today; d = addDays(d, 1)) {
    const r = await readNight(get, d);
    if (r.value) read.push(r.value);
  }
  out.nights_read = read.length;
  const names = pageNames(cur.value);
  const db = env.FOLLOW_DB;
  out.subscribers = await countConfirmed(db);
  const subs = (await db.prepare(
    "SELECT id, email_hmac, email_enc, frequency, link_gen, paused_until, detail " +
    "FROM subscribers ORDER BY id LIMIT ?1").bind(TEST_SEND_MOST).all()).results || [];
  out.taken = subs.length;
  const nhToday = nhClock(now).date;
  const batch = crypto.randomUUID();
  const gap = Math.max(0, Number(env.SEND_GAP_MS ?? 600) || 0);
  let stop = false, first = true, digests = 0;

  for (const s of subs) {
    if (stop) break;
    if (s.paused_until && s.paused_until >= nhToday) { add(out.skipped, "paused"); continue; }
    let follows, links, to;
    try {
      ({ follows } = await followsOf(env, db, s));
      if (!follows.length) { add(out.skipped, "follows-nothing"); continue; }
      links = await linksFor(env, s.email_hmac, s.link_gen);
      to = await openAddress(env, s.email_enc, s.email_hmac);
    } catch (e) {
      add(out.failed, `error-${errName(e)}`);
      if (e instanceof ConfigError) stop = true;
      continue;
    }
    const own = { manage: links.manage, unsub: links.unsub, feedbackUrl: env.FEEDBACK_URL };
    for (const kind of kinds) {
      if (stop) break;
      let mail, testify = 0, empty = false;
      if (kind === "welcome") {
        // The first record followed that tonight's list still names, as a
        // confirmation would have sent it to a reader new to the list.
        const f = follows.find(x => cur.value.followable.has(keyOf(x.kind, x.ref)));
        if (!f) { add(out.skipped, "welcome-nothing-listed"); continue; }
        const meta = cur.value.followable.get(keyOf(f.kind, f.ref));
        mail = welcomeEmail({ origin, kind: f.kind, label: meta.label, title: meta.title, url: meta.url,
          frequency: s.frequency, total: follows.length, newcomer: true, ...own });
      } else {
        const sections = collect({ follows, nights: read, cursor: { date: "", built: "" },
          current: cur.value, frequency: kind, today, detail: s.detail, testifyAhead: true });
        empty = !sections.length;
        testify = sections.filter(x => x.testify).length;
        mail = empty ? nothingNewEmail({ origin, frequency: kind, date: today, nights, ...own })
          : digestEmail({ origin, frequency: kind, date: today, sections, names, ...own });
      }
      if (!first && gap) await sleep(gap);
      first = false;
      let r;
      try {
        r = await sendMail(env, { to, ...mail, subject: TEST_PREFIX + mail.subject },
          `test/${batch}/${kind}/${s.id}`);
      } catch (e) {
        add(out.failed, `error-${errName(e)}`);
        if (e instanceof ConfigError) stop = true;
        continue;
      }
      if (!r.ok) {
        add(out.failed, `resend-${r.status}`);
        if (AUTH.has(r.status) || r.status === 429) stop = true;
        continue;
      }
      out.sent++;
      out.emails[kind]++;
      if (kind !== "welcome") digests++;
      if (empty) out.nothing_new++;
      out.testify += testify;
    }
  }

  if (!out.subscribers) out.notes.push("no confirmed subscriber in this database, so nothing was sent");
  if (out.subscribers > subs.length)
    out.notes.push(`${out.subscribers} confirmed subscribers: test emails went to the first ` +
      `${subs.length} by id, and the other ${out.subscribers - subs.length} were sent nothing`);
  if (read.length < nights)
    out.notes.push(`${nights - read.length} of the ${nights} nights to ${today} have no changes file on the site`);
  if (today < nhToday)
    out.notes.push(`the site's newest night is ${today}, before today in New Hampshire (${nhToday}); ` +
      "the emails are as of that night");
  if (digests && !out.testify)
    out.notes.push("no followed bill has a public hearing ahead, so no email has a testify block");
  if (stop) out.notes.push("stopped early: see failed");
  note("sender.test-sent", out.sent);
  for (const [k, n] of Object.entries(out.failed)) note(`sender.test-failed.${k}`, n);
  out.ok = !Object.keys(out.failed).length;
  return [200, out];
}

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(run(env, new Date(controller.scheduledTime))
      .catch(e => {
        note(`sender.run-failed.${errName(e)}`);
        return { sent: 0, failed: 0, problems: ["run-failed"] };
      })
      .then(out => ping(env, out)));
  },
  // One address answers, on the preview alone and only to the person's token
  // (A TEST SEND, above). Everything else, and everything on production, gets
  // nothing.
  async fetch(request, env) {
    if (!testSendAllowed(request, env)) return notFound();
    try {
      const ask = testAsk(await readCapped(request, TEST_BODY_MOST));
      if (!ask) return json(400, { ok: false, why: "invalid", expects: TEST_EXPECTS });
      const [status, answer] = await testSend(env, clock(env), ask);
      return json(status, answer);
    } catch (e) {
      note(`sender.test-failed.error-${errName(e)}`, 1);
      return json(500, { ok: false, why: "error" });
    }
  },
};
