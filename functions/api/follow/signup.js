/*
 * POST /api/follow/signup -- a reader asks for email updates on one record.
 *
 * Nothing is followed here. This keeps the request -- the address sealed,
 * its lookup hash, its inbox's hash, the record sealed, and the hash of a
 * confirmation token -- and emails the address a link to confirm it. Only
 * the confirmation makes a subscriber (confirm.js), and a request not
 * confirmed within 48 hours is deleted.
 *
 * THE ANSWER DOES NOT DEPEND ON THE ADDRESS, in what it says or in how long
 * it takes. Everything this file does with the address happens after the
 * answer has gone, in the request's waitUntil: a new address, one already
 * subscribed, one following this very record, an inbox with requests already
 * waiting -- each is answered 202 {"ok":true} at the same point, having asked
 * the same things. This file never asks whether the address is subscribed at
 * all. Even an existing subscriber gets a confirmation email, because only
 * the inbox can say the request is theirs. The other answers depend only on
 * what was sent or on the day:
 *   400 {"why":"invalid"}         not an address, not a record, not JSON
 *   400 {"why":"check"}           Turnstile said no
 *   400 {"why":"not-followable"}  not followable tonight (current.json)
 *   429 {"why":"busy"}            the day's confirmation emails are used up
 *   503 {"why":"unavailable"}     the changes file, the database or a secret is missing
 * A refusal by Resend after the answer is logged by its status alone, and the
 * request deleted: the reader sees no email and can ask again.
 *
 * Volume: Turnstile on the form, a Cloudflare rate rule on this path (it
 * needs no address and keeps none), the day's ceiling -- raised only when an
 * email is about to go, so requests that send nothing cannot fill it -- and at
 * most three waiting requests per inbox, counted and kept in one statement:
 * "pat+1@" and "pat+2@" are one inbox, and so are Gmail's dotted spellings.
 */

import { cleanAddress, hashToken, keysReady, lookupHash, mailboxHash, newToken,
         sealAddress, sealFollow, ConfigError } from "../../../workers/follow/address.js";
import { clock, errName, hostAllowed, isoSeconds, json, keyOf, note, notHere, plain,
         readCapped, refOk, rightPlace } from "../../../workers/follow/common.js";
import { readCurrent } from "../../../workers/follow/changes.js";
import { confirmationEmail, sendMail } from "../../../workers/follow/mail.js";
import { PENDING_PER_MAILBOX, dayFull, purgePending, underCeiling }
  from "../../../workers/follow/store.js";

const PATH = "/api/follow/signup";
const MAX_BODY = 4096;
const TURNSTILE = "https://challenges.cloudflare.com/turnstile/v0/siteverify";
const DAILY_CEILING = 50;

const SENT = () => json(202, { ok: true });
const NO = why => json(400, { ok: false, why });
const DOWN = () => json(503, { ok: false, why: "unavailable" });

async function turnstileOk(env, token) {
  if (!env.TURNSTILE_SECRET) throw new ConfigError();
  if (typeof token !== "string" || !token || token.length > 2048) return false;
  // No remoteip: the check works without it, and this file handles no IP.
  const res = await fetch(TURNSTILE, { method: "POST",
    body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token }) });
  if (!res.ok) return false;
  const j = await res.json().catch(() => null);
  return !!(j && j.success === true);
}

// AFTER THE ANSWER: keep the request if its inbox has room, raise the day's
// count, send. Every outcome is a log line of a code, and nothing is
// answered, so nothing here can be timed from outside.
async function keepAndSend(env, now, { address, key, meta, origin, ceiling }) {
  const db = env.FOLLOW_DB;
  try {
    await purgePending(db, now);
    const hmac = await lookupHash(env, address);
    const token = newToken();
    // Counted and kept in one statement: D1 runs one statement at a time, so
    // a dozen requests at once cannot all read "two waiting" and all go in.
    const id = await db.prepare(
      "INSERT INTO pending (email_hmac, email_enc, mailbox_hmac, follow_enc, " +
      "confirm_token_hash, created_at) SELECT ?1, ?2, ?3, ?4, ?5, ?6 " +
      "WHERE (SELECT COUNT(*) FROM pending WHERE mailbox_hmac = ?3) < ?7 RETURNING id")
      .bind(hmac, await sealAddress(env, address, hmac), await mailboxHash(env, address),
            await sealFollow(env, key, hmac), await hashToken(token), isoSeconds(now),
            PENDING_PER_MAILBOX).first("id");
    if (id === null || id === undefined) { note("signup.waiting-enough"); return; }
    const drop = () => db.prepare("DELETE FROM pending WHERE id = ?1").bind(id).run();
    if ((await underCeiling(db, isoSeconds(now).slice(0, 10), ceiling)) === null) {
      await drop();
      note("signup.day-full");
      return;
    }
    const mail = confirmationEmail({ origin, label: meta.label, title: meta.title, token });
    const sent = await sendMail(env, { to: address, ...mail });
    if (!sent.ok) {
      await drop();
      note(`signup.resend-refused.${sent.status}`);
      return;
    }
    note("signup.sent", 1);
  } catch (e) {
    note(`signup.error.${errName(e)}`);
  }
}

export async function onRequest(context) {
  const { request, env } = context;
  // Not open until the database is bound: a deployment without it has no
  // follow endpoints at all.
  if (!env.FOLLOW_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST")
    return plain(405, "POST only\n", { Allow: "POST" });
  try {
    if (!hostAllowed(request.headers.get("Origin"), env)) return NO("invalid");
    if (!(request.headers.get("Content-Type") || "").startsWith("application/json"))
      return NO("invalid");
    const raw = await readCapped(request, MAX_BODY);
    if (raw === null) return NO("invalid");
    let body;
    try { body = JSON.parse(raw); } catch { return NO("invalid"); }
    if (!body || typeof body !== "object" || Array.isArray(body)) return NO("invalid");
    if (body.website) return SENT();     // the honeypot is told what a person is
    const address = cleanAddress(body.email);
    const kind = String(body.kind ?? ""), ref = String(body.ref ?? "");
    if (!address || !refOk(kind, ref)) return NO("invalid");
    if (!(await turnstileOk(env, body.turnstile))) return NO("check");

    const cur = await readCurrent(p => env.ASSETS.fetch(new URL(p, request.url)));
    if (!cur.value) { note("signup.current-unreadable"); return DOWN(); }
    const key = keyOf(kind, ref);
    const meta = cur.value.followable.get(key);
    if (!meta) return NO("not-followable");

    // What every accepted request asks before its answer, whatever the address.
    await keysReady(env);
    if (!env.RESEND_API_KEY || !String(env.MAIL_FROM || "").trim()) throw new ConfigError();
    const now = clock(env);
    const ceiling = Math.max(1, Number(env.SIGNUP_DAILY_CEILING) || DAILY_CEILING);
    if (await dayFull(env.FOLLOW_DB, isoSeconds(now).slice(0, 10), ceiling)) {
      note("signup.day-full");
      return json(429, { ok: false, why: "busy" });
    }
    // Started on the next turn, not now: an async function runs up to its
    // first await at once, and nothing about the address may happen before
    // the answer has been handed back.
    const job = new Promise(r => setTimeout(r, 0)).then(() => keepAndSend(env, now,
      { address, key, meta, origin: new URL(request.url).origin, ceiling }));
    if (typeof context.waitUntil === "function") context.waitUntil(job);
    else await job;
    return SENT();
  } catch (e) {
    note(`signup.error.${errName(e)}`);
    return DOWN();
  }
}
