/*
 * /api/follow/confirm -- the link in the confirmation email.
 *
 * GET answers a page with one button, and changes nothing: mail scanners
 * open links to look at them, and a confirmation they could press would
 * defeat the point of asking. The token is after "#" in the link, so the page
 * reads it there and the button posts it.
 *
 * POST, from that page only (same-site, common.sameSite), with a token for a
 * request younger than 48 hours: the address becomes a subscriber if it was
 * not one (daily, the default), the record is added to what it follows, the
 * request is deleted, and the reader is sent to their manage page -- by the
 * same manage link every email of theirs carries.
 */

import { TOKEN, followHash, hashToken, linksFor, openFollow }
  from "../../../workers/follow/address.js";
import { MAX_FOLLOWS, clock, errName, isoSeconds, nhClock, note, notHere, parseKey, plain,
         readForm, redirect, rightPlace, sameSite } from "../../../workers/follow/common.js";
import { readCurrent } from "../../../workers/follow/changes.js";
import { message, page } from "../../../workers/follow/page.js";
import { PENDING_HOURS } from "../../../workers/follow/store.js";

const PATH = "/api/follow/confirm";

const SHELL = () => page(200, {
  title: "Confirm email updates",
  fill: "t",
  body: `<h1>Confirm email updates</h1>
<p>Press Confirm to start receiving email updates on what you asked to follow.
Nothing is sent until you do.</p>
<form method="post" action="${PATH}"><input type="hidden" name="t" value="">
<button type="submit">Confirm</button></form>
<p class="quiet">If it was not you who asked, close this page. The request, and
the address with it, is deleted within 48 hours without being used.</p>`,
});

const SPENT = () => message(400, "This link has expired or been used",
  "A confirmation link works once, for 48 hours. If you still want these updates, " +
  "use Follow on the record's page again and a new link will be sent.");

export async function onRequest({ request, env }) {
  if (!env.FOLLOW_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method === "GET" || request.method === "HEAD") return SHELL();
  if (request.method !== "POST") return plain(405, "GET or POST\n", { Allow: "GET, POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const form = await readForm(request);
    const t = form && form.get("t");
    if (!t || !TOKEN.test(t)) return SPENT();
    const db = env.FOLLOW_DB;
    const now = clock(env);
    const p = await db.prepare(
      "SELECT id, email_hmac, email_enc, follow_enc FROM pending " +
      "WHERE confirm_token_hash = ?1 AND created_at >= ?2")
      .bind(await hashToken(t),
            isoSeconds(new Date(now.getTime() - PENDING_HOURS * 3600000))).first();
    if (!p) return SPENT();
    const dropRequest = () => db.prepare("DELETE FROM pending WHERE id = ?1").bind(p.id).run();
    const key = await openFollow(env, p.follow_enc, p.email_hmac);
    if (!parseKey(key)) { await dropRequest(); return SPENT(); }

    const cur = await readCurrent(path => env.ASSETS.fetch(new URL(path, request.url)));
    if (!cur.value) {
      note("confirm.current-unreadable");
      return message(503, "Please try again shortly",
        "The site could not say what can be followed just now. Your link still works.");
    }
    if (!cur.value.followable.get(key)) {
      await dropRequest();
      return message(200, "This can no longer be followed",
        "What you asked to follow has finished since you asked, so there is nothing more " +
        "to send about it. Its full history stays on its page. Nothing was saved.");
    }

    const today = nhClock(now).date;
    const first = await linksFor(env, p.email_hmac, 0);
    // A new subscriber starts from now: nothing already published is sent,
    // and the first email is the first run of a later day.
    await db.prepare(
      "INSERT INTO subscribers (email_hmac, email_enc, frequency, confirmed_on, link_gen, " +
      "manage_hash, unsub_hash, last_sent_on, sent_date, sent_built) " +
      "VALUES (?1, ?2, 'daily', ?3, 0, ?4, ?5, ?3, ?3, ?6) ON CONFLICT(email_hmac) DO NOTHING")
      .bind(p.email_hmac, p.email_enc, today, first.manageHash, first.unsubHash,
            isoSeconds(now)).run();
    const sub = await db.prepare("SELECT id, link_gen FROM subscribers WHERE email_hmac = ?1")
      .bind(p.email_hmac).first();
    const fh = await followHash(env, p.email_hmac, key);
    const has = await db.prepare(
      "SELECT COUNT(*) AS n, SUM(follow_hmac = ?2) AS already FROM follows " +
      "WHERE subscriber_id = ?1").bind(sub.id, fh).first();
    if (Number(has.n) >= MAX_FOLLOWS && !Number(has.already)) {
      await dropRequest();
      return message(200, "You follow as many records as this allows",
        `One address can follow ${MAX_FOLLOWS} records. Remove one on the page linked ` +
        "at the foot of any of our emails, then use Follow on this record's page again.");
    }
    // The sealed key moves across as it is: it is bound to the same reader.
    await db.batch([
      db.prepare("INSERT OR IGNORE INTO follows (subscriber_id, follow_hmac, follow_enc, since) " +
        "VALUES (?1, ?2, ?3, ?4)").bind(sub.id, fh, p.follow_enc, today),
      db.prepare("DELETE FROM pending WHERE id = ?1").bind(p.id),
    ]);
    note("confirm.confirmed", 1);
    const { manage } = await linksFor(env, p.email_hmac, sub.link_gen);
    return redirect(`/api/follow/manage#t=${manage}&n=confirmed`);
  } catch (e) {
    note(`confirm.error.${errName(e)}`);
    return message(503, "Please try again shortly",
      "Something went wrong on our side. Your link still works for 48 hours.");
  }
}
