/*
 * POST /api/follow/signup -- a reader asks for email updates on one record.
 *
 * Nothing is followed here. This keeps the request -- the address sealed,
 * its lookup hash, its inbox's hash, the record sealed, the hash of a
 * confirmation token, and daily or weekly as the box was set -- and emails
 * the address a link to confirm it. Only the confirmation makes a subscriber
 * (confirm.js), and a request not confirmed within 48 hours is deleted.
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
 *   400 {"why":"invalid"}         not an address, not a record, not JSON, or a
 *                                 frequency other than daily or weekly
 *   400 {"why":"check"}           Turnstile said no, or said yes for another
 *                                 form or site (action-mismatch,
 *                                 hostname-mismatch), with its error codes when
 *                                 it gave any (its own fixed words, never the
 *                                 reader's: invalid-input-secret is a secret
 *                                 that is not this widget's)
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
// THE DAY'S CEILING SERVES A WEBINAR (17 October 2026). It was 50, and with
// SIGNUP_DAILY_CEILING unset on production the 51st sign-up of the 10
// November walkthrough would have been told "too many sign-ups today". A
// webinar's audience is a few hundred, each following perhaps two or three
// things, one confirmation email each: 1,000 holds that with room. It still
// bounds abuse once Turnstile, the rate rule and the three waiting requests
// an inbox may have let a request through: a day at the ceiling is 2% of
// Resend Pro's 50,000 emails a month (the plan the person chose; no daily
// limit, by resend.com/pricing, read 25 October 2026), so a flood shows in
// the log as signup.day-full long before it can spend the month.
// SIGNUP_DAILY_CEILING still overrides it, either way.
const DAILY_CEILING = 1000;

const SENT = () => json(202, { ok: true });
const NO = why => json(400, { ok: false, why });
// Siteverify's own vocabulary, and nothing else is passed on.
const TS_CODES = new Set(["missing-input-secret", "invalid-input-secret", "missing-input-response",
  "invalid-input-response", "bad-request", "timeout-or-duplicate", "internal-error"]);
const NO_CHECK = codes => codes.length ? json(400, { ok: false, why: "check", codes }) : NO("check");
const DOWN = () => json(503, { ok: false, why: "unavailable" });

// HOW OFTEN, CHOSEN IN THE BOX (the person, 16 October 2026: "Daily or
// weekly" beside the address, Daily selected), and kept with the request
// until confirm.js gives it to the new subscriber. Returns the frequency, or
// null for one to refuse.
//
// None at all is daily: a page loaded before the box had the choice sends
// none, and daily is what such a sign-up always became. Anything else is
// refused as "invalid", as a kind or a record the form cannot send is, rather
// than quietly made daily: the form's two radios can send nothing but these
// two words, so another value is not a reader's choice, and a reader who did
// choose would get a frequency they had not asked for and no word of it.
const FREQUENCIES = new Set(["daily", "weekly"]);
function frequencyOf(raw) {
  if (raw === undefined || raw === null || raw === "") return "daily";
  return typeof raw === "string" && FREQUENCIES.has(raw) ? raw : null;
}

// Returns null for a yes, else the list of Turnstile's codes for its no
// (empty when it gave none), each also a log line.
//
// SITEVERIFY SAYS NO WITH A 400 (found 12 October 2026, the person's sign-up
// looping on "did not finish"): its refusal comes as HTTP 400 with the codes
// in the body, and this read only a 200's body, so every refusal reached the
// page with no reason at all. The body is read whatever the status. And a yes
// counts only for this form and this site, as Cloudflare's own integration
// guide asks: the widget is rendered with the action "follow" (app.js), and
// the hostname it was solved on must be one of this deployment's own
// (hostAllowed, the list the Origin check uses).
const TS_ACTION = "follow";
async function turnstileNo(env, token) {
  if (!env.TURNSTILE_SECRET) throw new ConfigError();
  if (typeof token !== "string" || !token || token.length > 2048) return ["missing-input-response"];
  // No remoteip: the check works without it, and this file handles no IP.
  const res = await fetch(TURNSTILE, { method: "POST",
    body: new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: token }) });
  const j = await res.json().catch(() => null);
  if (!j) { note("signup.check.http", res.status); return []; }
  if (j.success === true) {
    const why = j.action !== TS_ACTION ? "action-mismatch"
      : !hostAllowed(`https://${j.hostname}`, env) ? "hostname-mismatch" : "";
    if (!why) return null;
    note(`signup.check.${why}`);
    return [why];
  }
  const codes = (Array.isArray(j["error-codes"]) ? j["error-codes"] : []).filter(c => TS_CODES.has(c));
  note(`signup.check.${codes[0] || "no"}`);
  return codes;
}

// AFTER THE ANSWER: keep the request if its inbox has room, raise the day's
// count, send. Every outcome is a log line of a code, and nothing is
// answered, so nothing here can be timed from outside.
async function keepAndSend(env, now, { address, key, meta, origin, ceiling, frequency }) {
  const db = env.FOLLOW_DB;
  try {
    await purgePending(db, now);
    const hmac = await lookupHash(env, address);
    const token = newToken();
    // Counted and kept in one statement: D1 runs one statement at a time, so
    // a dozen requests at once cannot all read "two waiting" and all go in.
    const id = await db.prepare(
      "INSERT INTO pending (email_hmac, email_enc, mailbox_hmac, follow_enc, " +
      "confirm_token_hash, created_at, frequency) SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?8 " +
      "WHERE (SELECT COUNT(*) FROM pending WHERE mailbox_hmac = ?3) < ?7 RETURNING id")
      .bind(hmac, await sealAddress(env, address, hmac), await mailboxHash(env, address),
            await sealFollow(env, key, hmac), await hashToken(token), isoSeconds(now),
            PENDING_PER_MAILBOX, frequency).first("id");
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
    const frequency = frequencyOf(body.frequency);
    if (!address || !refOk(kind, ref) || !frequency) return NO("invalid");
    const no = await turnstileNo(env, body.turnstile);
    if (no) return NO_CHECK(no);

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
      { address, key, meta, origin: new URL(request.url).origin, ceiling, frequency }));
    if (typeof context.waitUntil === "function") context.waitUntil(job);
    else await job;
    return SENT();
  } catch (e) {
    note(`signup.error.${errName(e)}`);
    return DOWN();
  }
}
