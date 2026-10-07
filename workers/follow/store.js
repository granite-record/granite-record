/*
 * The database calls more than one endpoint makes: forgetting an address,
 * issuing and checking a link, the purge, the count and the day's ceiling.
 * The binding is FOLLOW_DB (schema.sql), never the reports' DB.
 *
 * Every value is bound, never written into the SQL, so no statement text
 * carries an address, a hash or a ref.
 */

import { hashToken, newToken, TOKEN } from "./address.js";
import { isoSeconds } from "./common.js";

export const PENDING_HOURS = 48;
// How many unconfirmed requests one address may have waiting. A fourth within
// 48 hours sends nothing and is answered exactly as the first was.
export const PENDING_PER_ADDRESS = 3;
const LINK_DAYS = { manage: 60, unsubscribe: 180 };

const ago = (now, ms) => isoSeconds(new Date(now.getTime() - ms));

// Requests older than 48 hours. Sign-up runs this alone, so that nothing it
// does touches the subscribers table: its answer cannot depend on it.
export async function purgePending(db, now) {
  const r = await db.prepare("DELETE FROM pending WHERE created_at < ?1")
    .bind(ago(now, PENDING_HOURS * 3600000)).run();
  return r?.meta?.changes ?? 0;
}

// THE PURGE, run every hour by the sender: requests older than 48 hours,
// links past their age (but never an address's newest link of a purpose),
// ceiling rows older than a fortnight, and addresses left following nothing.
export async function purge(db, now) {
  const r = await db.batch([
    db.prepare("DELETE FROM pending WHERE created_at < ?1")
      .bind(ago(now, PENDING_HOURS * 3600000)),
    db.prepare(
      "DELETE FROM links WHERE purpose = 'manage' AND created_at < ?1 AND created_at < " +
      "(SELECT MAX(l2.created_at) FROM links l2 WHERE l2.subscriber_id = links.subscriber_id " +
      "AND l2.purpose = links.purpose)").bind(ago(now, LINK_DAYS.manage * 86400000)),
    db.prepare(
      "DELETE FROM links WHERE purpose = 'unsubscribe' AND created_at < ?1 AND created_at < " +
      "(SELECT MAX(l2.created_at) FROM links l2 WHERE l2.subscriber_id = links.subscriber_id " +
      "AND l2.purpose = links.purpose)").bind(ago(now, LINK_DAYS.unsubscribe * 86400000)),
    db.prepare("DELETE FROM signup_days WHERE day < ?1")
      .bind(ago(now, 14 * 86400000).slice(0, 10)),
    // An address kept for nothing. Removing the last follow on the manage
    // page, or the last follow ending, deletes the address at the time; this
    // catches one left by two of those crossing, a day on.
    db.prepare("DELETE FROM links WHERE subscriber_id IN (SELECT id FROM subscribers s " +
      "WHERE s.confirmed_at < ?1 AND NOT EXISTS (SELECT 1 FROM follows f " +
      "WHERE f.subscriber_id = s.id))").bind(ago(now, 86400000)),
    db.prepare("DELETE FROM subscribers WHERE confirmed_at < ?1 AND NOT EXISTS " +
      "(SELECT 1 FROM follows f WHERE f.subscriber_id = subscribers.id)")
      .bind(ago(now, 86400000)),
  ]);
  return { pending: r[0]?.meta?.changes ?? 0,
           links: (r[1]?.meta?.changes ?? 0) + (r[2]?.meta?.changes ?? 0),
           orphans: r[5]?.meta?.changes ?? 0 };
}

// FORGETTING AN ADDRESS: the subscriber, every follow, every link and every
// pending request, in one transaction. By the subscriber's id (unsubscribe,
// the manage page) or by the address's lookup hash (a bounce), or both.
// Returns how many subscribers went, for the log's count.
export async function forget(db, { id = null, hmac = null }) {
  const stmts = [];
  if (id !== null) {
    stmts.push(db.prepare("DELETE FROM links WHERE subscriber_id = ?1").bind(id));
    stmts.push(db.prepare("DELETE FROM follows WHERE subscriber_id = ?1").bind(id));
  }
  if (hmac !== null) {
    const of = "(SELECT id FROM subscribers WHERE email_hmac = ?1)";
    stmts.push(db.prepare(`DELETE FROM links WHERE subscriber_id IN ${of}`).bind(hmac));
    stmts.push(db.prepare(`DELETE FROM follows WHERE subscriber_id IN ${of}`).bind(hmac));
    stmts.push(db.prepare("DELETE FROM pending WHERE email_hmac = ?1").bind(hmac));
  }
  const counted = [];
  if (id !== null) {
    // The pending requests of this subscriber's address too, by its hash,
    // before the row that holds the hash goes.
    stmts.push(db.prepare("DELETE FROM pending WHERE email_hmac = " +
      "(SELECT email_hmac FROM subscribers WHERE id = ?1)").bind(id));
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
export async function issueLink(db, subscriberId, purpose, now) {
  const token = newToken();
  await db.prepare(
    "INSERT INTO links (token_hash, subscriber_id, purpose, created_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(await hashToken(token), subscriberId, purpose, isoSeconds(now)).run();
  return token;
}

// The statement form of issueLink, for a batch: [token, statement].
export async function linkStatement(db, subscriberId, purpose, now) {
  const token = newToken();
  return [token, db.prepare(
    "INSERT INTO links (token_hash, subscriber_id, purpose, created_at) VALUES (?1, ?2, ?3, ?4)")
    .bind(await hashToken(token), subscriberId, purpose, isoSeconds(now))];
}

// The subscriber a link opens, or null. A link is good while it is younger
// than its purpose's age, and an address's newest link of a purpose is good
// whatever its age, so a reader who hears nothing for months is not locked out.
export async function subscriberFor(db, token, purpose, now) {
  if (typeof token !== "string" || !TOKEN.test(token)) return null;
  return await db.prepare(
    "SELECT s.id AS id, s.email_hmac AS email_hmac, s.email_enc AS email_enc, " +
    "s.frequency AS frequency FROM links l JOIN subscribers s ON s.id = l.subscriber_id " +
    "WHERE l.token_hash = ?1 AND l.purpose = ?2 AND (l.created_at >= ?3 OR l.created_at >= " +
    "(SELECT MAX(l2.created_at) FROM links l2 WHERE l2.subscriber_id = l.subscriber_id " +
    "AND l2.purpose = l.purpose))")
    .bind(await hashToken(token), purpose, ago(now, LINK_DAYS[purpose] * 86400000))
    .first();
}

// ---- the one number ---------------------------------------------------------------
export async function countConfirmed(db) {
  const n = await db.prepare("SELECT COUNT(*) AS n FROM subscribers").first("n");
  return Number(n) || 0;
}

// The day's ceiling: raised and checked in one statement, so simultaneous
// sign-ups cannot all read 49 and all go in. null when the day is full.
export async function underCeiling(db, day, ceiling) {
  const n = await db.prepare(
    "INSERT INTO signup_days (day, n) VALUES (?1, 1) " +
    "ON CONFLICT(day) DO UPDATE SET n = n + 1 WHERE n < ?2 RETURNING n")
    .bind(day, ceiling).first("n");
  return n === null || n === undefined ? null : Number(n);
}
