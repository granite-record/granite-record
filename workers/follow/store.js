/*
 * The database calls more than one endpoint makes: forgetting an address,
 * finding the reader a link belongs to, the purge, the count and the day's
 * ceiling. The binding is FOLLOW_DB (schema.sql), never the reports' DB.
 *
 * Every value is bound, never written into the SQL, so no statement text
 * carries an address, a hash or a ref.
 */

import { TOKEN, hashToken } from "./address.js";
import { addDays, isoSeconds, nhClock } from "./common.js";

export const PENDING_HOURS = 48;
// How many unconfirmed requests one inbox may have waiting (address.js
// mailboxOf: its +tags and Gmail's dots are one inbox). A fourth within 48
// hours sends nothing, and is answered exactly as the first was.
export const PENDING_PER_MAILBOX = 3;

const ago = (now, ms) => isoSeconds(new Date(now.getTime() - ms));

// Requests older than 48 hours. Sign-up runs this alone, so that nothing it
// does touches the subscribers table.
export async function purgePending(db, now) {
  const r = await db.prepare("DELETE FROM pending WHERE created_at < ?1")
    .bind(ago(now, PENDING_HOURS * 3600000)).run();
  return r?.meta?.changes ?? 0;
}

// THE PURGE, run every hour by the sender: requests older than 48 hours,
// ceiling rows older than a fortnight, and addresses left following nothing.
export async function purge(db, now) {
  const r = await db.batch([
    db.prepare("DELETE FROM pending WHERE created_at < ?1")
      .bind(ago(now, PENDING_HOURS * 3600000)),
    db.prepare("DELETE FROM signup_days WHERE day < ?1")
      .bind(ago(now, 14 * 86400000).slice(0, 10)),
    // An address kept for nothing. Removing the last follow on the manage
    // page, or the last follow ending, deletes the address at the time; this
    // catches one left by two of those crossing, a day or two on.
    db.prepare("DELETE FROM subscribers WHERE confirmed_on < ?1 AND NOT EXISTS " +
      "(SELECT 1 FROM follows f WHERE f.subscriber_id = subscribers.id)")
      .bind(addDays(nhClock(now).date, -1)),
  ]);
  return { pending: r[0]?.meta?.changes ?? 0, orphans: r[2]?.meta?.changes ?? 0 };
}

// FORGETTING AN ADDRESS: the subscriber, every follow and every pending
// request, in one transaction. By the subscriber's id (unsubscribe, the
// manage page, the sender) or by the address's lookup hash (a bounce), or
// both. Returns how many subscribers went, for the log's count.
export async function forget(db, { id = null, hmac = null }) {
  const stmts = [];
  if (id !== null) {
    stmts.push(db.prepare("DELETE FROM follows WHERE subscriber_id = ?1").bind(id));
    // The pending requests of this subscriber's address too, by its hash,
    // before the row that holds the hash goes.
    stmts.push(db.prepare("DELETE FROM pending WHERE email_hmac = " +
      "(SELECT email_hmac FROM subscribers WHERE id = ?1)").bind(id));
  }
  if (hmac !== null) {
    stmts.push(db.prepare("DELETE FROM follows WHERE subscriber_id IN " +
      "(SELECT id FROM subscribers WHERE email_hmac = ?1)").bind(hmac));
    stmts.push(db.prepare("DELETE FROM pending WHERE email_hmac = ?1").bind(hmac));
  }
  const counted = [];
  if (id !== null) {
    counted.push(stmts.length);
    stmts.push(db.prepare("DELETE FROM subscribers WHERE id = ?1").bind(id));
  }
  if (hmac !== null) {
    counted.push(stmts.length);
    stmts.push(db.prepare("DELETE FROM subscribers WHERE email_hmac = ?1").bind(hmac));
  }
  const r = await db.batch(stmts);
  return counted.reduce((n, i) => n + (r[i]?.meta?.changes ?? 0), 0);
}

// ---- links -----------------------------------------------------------------------
// The subscriber a link belongs to, or null. A link is current until its
// reader asks for a new one; there is no other expiry, because every email
// carries the same link and a reader who hears nothing for months must not
// find it dead.
const COLUMN = { manage: "manage_hash", unsubscribe: "unsub_hash" };

export async function subscriberFor(db, token, purpose) {
  if (typeof token !== "string" || !TOKEN.test(token) || !Object.hasOwn(COLUMN, purpose))
    return null;
  return await db.prepare(
    "SELECT id, email_hmac, email_enc, frequency, link_gen, manage_hash, unsub_hash " +
    `FROM subscribers WHERE ${COLUMN[purpose]} = ?1`).bind(await hashToken(token)).first();
}

// ---- the one number ---------------------------------------------------------------
export async function countConfirmed(db) {
  const n = await db.prepare("SELECT COUNT(*) AS n FROM subscribers").first("n");
  return Number(n) || 0;
}

// ---- the day's ceiling --------------------------------------------------------------
// Raised and checked in one statement, so simultaneous sign-ups cannot all
// read 49 and all go in; raised only for an email about to be sent. null when
// the day is full.
export async function underCeiling(db, day, ceiling) {
  const n = await db.prepare(
    "INSERT INTO signup_days (day, n) VALUES (?1, 1) " +
    "ON CONFLICT(day) DO UPDATE SET n = n + 1 WHERE n < ?2 RETURNING n")
    .bind(day, ceiling).first("n");
  return n === null || n === undefined ? null : Number(n);
}

// Whether the day is already full, asking and changing nothing: what sign-up
// answers 429 on, the same for every address.
export async function dayFull(db, day, ceiling) {
  const n = await db.prepare("SELECT n FROM signup_days WHERE day = ?1").bind(day).first("n");
  return Number(n || 0) >= ceiling;
}
