/*
 * POST /api/follow/bounce -- Resend's webhook, for bounces and complaints.
 *
 * An address that bounces for good, or whose owner marks an email as spam,
 * is deleted with everything it follows, automatically and with nobody
 * seeing it: the address in the event is hashed with the lookup key, the hash
 * finds the row, and the row goes. The address itself is never logged,
 * stored or answered.
 *
 * ONLY A SIGNED EVENT CHANGES ANYTHING. Resend signs its webhooks the Svix
 * way: headers svix-id, svix-timestamp and svix-signature, the signature an
 * HMAC-SHA-256 of "<id>.<timestamp>.<body>" under the endpoint's secret
 * ("whsec_" and base64, set as RESEND_WEBHOOK_SECRET), compared here in
 * constant time, and refused if the timestamp is more than five minutes from
 * now. Anything else is answered 401 and changes nothing.
 *
 * A bounce Resend calls transient (a full mailbox) is not a reason to delete
 * anyone; every other bounce, and every complaint, is.
 */

import { ConfigError, b64Decode, cleanAddress, hmacBytes, lookupHash, sameBytes }
  from "../../../workers/follow/address.js";
import { clock, empty, errName, note, notHere, plain, readCapped, rightPlace }
  from "../../../workers/follow/common.js";
import { forget } from "../../../workers/follow/store.js";

const PATH = "/api/follow/bounce";
const MAX_BODY = 65536;
const TOLERANCE_S = 300;

export async function verify(env, headers, body, now) {
  const secret = String(env.RESEND_WEBHOOK_SECRET || "").trim();
  if (!secret) throw new ConfigError();
  let key;
  try { key = b64Decode(secret.replace(/^whsec_/, "")); } catch { throw new ConfigError(); }
  if (!key.length) throw new ConfigError();
  const id = headers.get("svix-id"), ts = headers.get("svix-timestamp"),
        sigs = headers.get("svix-signature");
  if (!id || !ts || !sigs || !/^\d{1,12}$/.test(ts)) return false;
  if (Math.abs(now.getTime() / 1000 - Number(ts)) > TOLERANCE_S) return false;
  const want = await hmacBytes(key, `${id}.${ts}.${body}`);
  let ok = false;
  for (const part of sigs.split(" ")) {
    const [v, sig] = part.split(",", 2);
    if (v !== "v1" || !sig) continue;
    let got;
    try { got = b64Decode(sig); } catch { continue; }
    if (sameBytes(got, want)) ok = true;      // every candidate is compared
  }
  return ok;
}

export async function onRequest({ request, env }) {
  if (!env.FOLLOW_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST") return plain(405, "POST only\n", { Allow: "POST" });
  try {
    const body = await readCapped(request, MAX_BODY);
    if (body === null) return empty(413);
    if (!(await verify(env, request.headers, body, clock(env)))) {
      note("bounce.unsigned");
      return empty(401);
    }
    let event;
    try { event = JSON.parse(body); } catch { return empty(400); }
    const type = event && event.type;
    if (type !== "email.bounced" && type !== "email.complained") return empty(204);
    const data = (event && event.data) || {};
    if (type === "email.bounced" && /transient|temporary/i.test(String(data.bounce?.type || "")))
      return empty(204);
    const to = Array.isArray(data.to) ? data.to : [data.to];
    let gone = 0;
    for (const raw of to.slice(0, 50)) {
      const address = cleanAddress(raw);
      if (!address) continue;
      gone += await forget(env.FOLLOW_DB, { hmac: await lookupHash(env, address) });
    }
    note(type === "email.bounced" ? "bounce.forgot" : "complaint.forgot", gone);
    return empty(204);
  } catch (e) {
    note(`bounce.error.${errName(e)}`);
    // Resend retries an answer that is not 2xx, which is what a failure here wants.
    return empty(503);
  }
}
