/*
 * POST /api/follow/signup -- a reader asks for email updates on one record.
 *
 * Nothing is followed here. This keeps the request -- the address sealed,
 * its lookup hash, the record, and the hash of a confirmation token -- and
 * emails the address a link to confirm it. Only the confirmation makes a
 * subscriber (confirm.js), and a request not confirmed within 48 hours is
 * deleted.
 *
 * THE ANSWER DOES NOT DEPEND ON THE ADDRESS. A new address, one already
 * subscribed, one already following this very record, one with requests
 * already waiting: every one is answered 202 {"ok":true}, and this file never
 * asks whether the address is subscribed at all, so it could not answer
 * differently if it tried. Even an existing subscriber gets a confirmation
 * email, because only the inbox can say the request is theirs. The other
 * answers depend only on what was sent or on the day:
 *   400 {"why":"invalid"}         not an address, not a record, not JSON
 *   400 {"why":"check"}           Turnstile said no
 *   400 {"why":"not-followable"}  not followable tonight (current.json)
 *   429 {"why":"busy"}            the day's ceiling on confirmations
 *   503 {"why":"unavailable"}     the changes file, the database or Resend failed
 *
 * Volume: Turnstile on the form, a Cloudflare rate rule on this path (it
 * needs no address and keeps none), the day's ceiling, and at most three
 * waiting requests per address -- a fourth sends nothing and is answered as
 * the first was.
 */

import { cleanAddress, hashToken, lookupHash, newToken, sealAddress, ConfigError }
  from "../../../workers/follow/address.js";
import { clock, errName, hostAllowed, isoSeconds, json, keyOf, note, notHere, plain,
         readCapped, refOk, rightPlace } from "../../../workers/follow/common.js";
import { readCurrent } from "../../../workers/follow/changes.js";
import { confirmationEmail, sendMail } from "../../../workers/follow/mail.js";
import { PENDING_PER_ADDRESS, purgePending, underCeiling } from "../../../workers/follow/store.js";

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

export async function onRequest({ request, env }) {
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
    const meta = cur.value.followable.get(keyOf(kind, ref));
    if (!meta) return NO("not-followable");

    const db = env.FOLLOW_DB;
    const now = clock(env);
    await purgePending(db, now);
    const ceiling = Math.max(1, Number(env.SIGNUP_DAILY_CEILING) || DAILY_CEILING);
    if ((await underCeiling(db, isoSeconds(now).slice(0, 10), ceiling)) === null) {
      note("signup.day-full");
      return json(429, { ok: false, why: "busy" });
    }
    const hmac = await lookupHash(env, address);
    const waiting = await db.prepare("SELECT COUNT(*) AS n FROM pending WHERE email_hmac = ?1")
      .bind(hmac).first("n");
    if (Number(waiting) >= PENDING_PER_ADDRESS) {
      note("signup.waiting-enough");
      return SENT();
    }
    const token = newToken();
    const id = await db.prepare(
      "INSERT INTO pending (email_hmac, email_enc, follow_kind, follow_ref, " +
      "confirm_token_hash, created_at) VALUES (?1, ?2, ?3, ?4, ?5, ?6) RETURNING id")
      .bind(hmac, await sealAddress(env, address, hmac), kind, ref,
            await hashToken(token), isoSeconds(now)).first("id");
    const mail = confirmationEmail({ origin: new URL(request.url).origin,
      label: meta.label, title: meta.title, token });
    const sent = await sendMail(env, { to: address, ...mail });
    if (!sent.ok) {
      await db.prepare("DELETE FROM pending WHERE id = ?1").bind(id).run();
      note(`signup.resend-refused.${sent.status}`);
      return DOWN();
    }
    note("signup.sent", 1);
    return SENT();
  } catch (e) {
    note(`signup.error.${errName(e)}`);
    return DOWN();
  }
}
