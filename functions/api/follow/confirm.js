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
 * not one (daily or weekly, as the sign-up box was set), the record is added
 * to what it follows, the request is deleted, and the reader is sent to their
 * manage page -- by the same manage link every email of theirs carries.
 *
 * A READER ALREADY SUBSCRIBED KEEPS THEIR FREQUENCY, AND IS TOLD SO. This is
 * the sign-up change's own choice, not one the person made, and it is put to
 * them to keep or overturn (16 October 2026). The box opens on Daily, so a
 * weekly reader who follows one more record without touching it would
 * otherwise be turned daily by a choice they never made. The cost falls the
 * other way: a daily reader who picks Weekly in the box stays daily. So
 * where the box asked for the other one, the manage page the confirmation
 * lands on says how often they still come, above the How often that changes
 * it ("kept", manage.js), rather than the plain "Confirmed." that would let
 * the reader think the box's choice was made.
 *
 * A CONFIRMATION THAT ADDS A RECORD SENDS ONE EMAIL (the person's test of
 * 16 October 2026). The confirmation link works once, and the manage page is
 * reached by the link at the foot of every email -- of which, until the first
 * update, there was none: a reader who left the page had no way back. So once
 * the database has the follow, the address is sent "You're following ...",
 * with what it now follows, how often, and the same manage and unsubscribe
 * links and one-click headers as every other email (mail.welcomeEmail). It
 * goes after the answer, in waitUntil, so it never holds up or fails the
 * confirmation; a refusal or an error is a log line, and the reader is shown
 * nothing of it. A confirmation that adds nothing -- the record was followed
 * already -- sends nothing.
 */

import { TOKEN, followHash, hashToken, linksFor, openAddress, openFollow }
  from "../../../workers/follow/address.js";
import { MAX_FOLLOWS, clock, errName, isoSeconds, nhClock, note, notHere, parseKey, plain,
         readForm, redirect, rightPlace, sameSite } from "../../../workers/follow/common.js";
import { readCurrent } from "../../../workers/follow/changes.js";
import { sendMail, welcomeEmail } from "../../../workers/follow/mail.js";
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

// The second paragraph is for the reader who confirmed and came back by the
// same link, looking for their page. It names every email, not only the one
// a confirmation sends: a reader who confirmed before that email existed
// (16 October 2026) was never sent it, and will find the link in their next
// update.
const SPENT = () => message(400, "This link has expired or been used",
  "A confirmation link works once, for 48 hours. If you still want these updates, " +
  "use Follow on its page again and a new link will be sent.",
  "If you have already confirmed, the link to your page for email updates, where you " +
  "can change what you follow, is at the foot of every email we send you about them. " +
  "If you cannot find one, your next update will have it.");

// AFTER THE ANSWER: the "You're following" email. Every outcome is a log line
// of a code, and nothing of it reaches the reader.
async function welcome(env, { origin, sub, key, meta, frequency, kept, pausedUntil, total, newcomer,
                              links }) {
  try {
    const { kind } = parseKey(key);
    const mail = welcomeEmail({ origin, kind, label: meta.label, title: meta.title, url: meta.url,
      frequency, kept, pausedUntil, total, newcomer,
      manage: links.manage, unsub: links.unsub, feedbackUrl: env.FEEDBACK_URL });
    const sent = await sendMail(env, { to: await openAddress(env, sub.email_enc, sub.email_hmac),
                                       ...mail });
    if (!sent.ok) { note(`confirm.welcome-refused.${sent.status}`); return; }
    note("confirm.welcome-sent", 1);
  } catch (e) {
    note(`confirm.welcome-error.${errName(e)}`);
  }
}

export async function onRequest(context) {
  const { request, env } = context;
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
      "SELECT id, email_hmac, email_enc, follow_enc, frequency FROM pending " +
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
    // The table allows only the two words; anything else read back is daily,
    // as the manage page reads a subscriber's.
    const frequency = p.frequency === "weekly" ? "weekly" : "daily";
    // A new subscriber starts from now: nothing already published is sent,
    // and the first email is the first run of a later day. Whether this made
    // the subscriber decides one sentence of the email below (newcomer).
    const made = await db.prepare(
      "INSERT INTO subscribers (email_hmac, email_enc, frequency, confirmed_on, link_gen, " +
      "manage_hash, unsub_hash, last_sent_on, sent_date, sent_built) " +
      "VALUES (?1, ?2, ?7, ?3, 0, ?4, ?5, ?3, ?3, ?6) ON CONFLICT(email_hmac) DO NOTHING")
      .bind(p.email_hmac, p.email_enc, today, first.manageHash, first.unsubHash,
            isoSeconds(now), frequency).run();
    const sub = await db.prepare(
      "SELECT id, email_hmac, email_enc, link_gen, frequency, paused_until FROM subscribers " +
      "WHERE email_hmac = ?1").bind(p.email_hmac).first();
    // A new subscriber has the box's frequency by the insert above; one that
    // differs is a subscriber's own, kept.
    const kept = (sub.frequency === "weekly" ? "weekly" : "daily") !== frequency;
    const fh = await followHash(env, p.email_hmac, key);
    const has = await db.prepare(
      "SELECT COUNT(*) AS n, SUM(follow_hmac = ?2) AS already FROM follows " +
      "WHERE subscriber_id = ?1").bind(sub.id, fh).first();
    if (Number(has.n) >= MAX_FOLLOWS && !Number(has.already)) {
      await dropRequest();
      // In a reader's words (the language sweep, 17 October 2026): "records"
      // was the database's noun for what a reader follows.
      return message(200, "You follow as many things as one address can",
        `One address can follow ${MAX_FOLLOWS} bills, laws, legislators, committees and ` +
        "topics in all. Remove one on the page linked at the foot of any of our emails, " +
        "then use Follow on its page again.");
    }
    // The sealed key moves across as it is: it is bound to the same reader.
    const [added] = await db.batch([
      db.prepare("INSERT OR IGNORE INTO follows (subscriber_id, follow_hmac, follow_enc, since) " +
        "VALUES (?1, ?2, ?3, ?4)").bind(sub.id, fh, p.follow_enc, today),
      db.prepare("DELETE FROM pending WHERE id = ?1").bind(p.id),
    ]);
    note("confirm.confirmed", 1);
    const links = await linksFor(env, p.email_hmac, sub.link_gen);
    // Only where the follow went in: a record already followed, or two
    // presses of Confirm at once of which the other added it, sends nothing.
    if (added?.meta?.changes) {
      // A pause is told only while it lasts. Nothing clears paused_until once
      // its day has gone by; the sender and the manage page read a date
      // before today as no pause (the review of 16 October 2026: one ended on
      // 8 October was told on the 20th as "paused through 8 October 2026").
      const p = sub.paused_until || "";
      const pausedUntil = p && p >= today ? p : "";
      // Started on the next turn, so that the answer is not held for it.
      const job = new Promise(r => setTimeout(r, 0)).then(() => welcome(env, {
        origin: new URL(request.url).origin, sub, key, meta: cur.value.followable.get(key),
        frequency: sub.frequency === "weekly" ? "weekly" : "daily", kept, pausedUntil,
        total: Number(has.n) + 1, newcomer: !!made?.meta?.changes, links }));
      if (typeof context.waitUntil === "function") context.waitUntil(job);
      else await job;
    }
    return redirect(`/api/follow/manage#t=${links.manage}&n=${kept ? "kept" : "confirmed"}`);
  } catch (e) {
    note(`confirm.error.${errName(e)}`);
    return message(503, "Please try again shortly",
      "Something went wrong on our side. Your link still works for 48 hours.");
  }
}
