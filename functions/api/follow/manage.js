/*
 * /api/follow/manage -- a reader's own page: what they follow, how often,
 * a new link, and unsubscribe. A private link, not a login.
 *
 * GET answers a shell whose script reads the token from after "#" and posts
 * it straight back (action=view), so the token travels in a body and never in
 * an address. Every POST must come from this site's own page: an Origin of
 * the site's own names, and Sec-Fetch-Site same-origin where the browser
 * sends it. A post from anywhere else changes nothing, and there are no
 * cookies here for another site to borrow.
 *
 * WHAT THE PAGE SHOWS. What the link's holder follows and how often. Never
 * the address: a link forwarded with an email must not hand the address on.
 *
 * ACTIONS (POST, form-encoded, t = the token):
 *   view                    the page
 *   frequency value=daily|weekly
 *   remove    follow=<kind>:<ref>   -- removing the last one deletes the address
 *   newlink                 every link of this address stops working, and one
 *                           new one is emailed to the address, not shown here
 *   unsubscribe             the address and everything it follows, deleted
 */

import { TOKEN, hashToken, openAddress } from "../../../workers/follow/address.js";
import { clock, errName, esc, fallbackLabel, note, notHere, parseKey, plain,
         readForm, redirect, rightPlace, sameSite, siteUrl } from "../../../workers/follow/common.js";
import { readCurrent } from "../../../workers/follow/changes.js";
import { newLinkEmail, sendMail } from "../../../workers/follow/mail.js";
import { message, page } from "../../../workers/follow/page.js";
import { forget, linkStatement, subscriberFor } from "../../../workers/follow/store.js";

const PATH = "/api/follow/manage";

const NOTICES = {
  confirmed: "Confirmed. You will get email updates on what is listed below.",
  saved: "Saved.",
  removed: "Removed.",
};

const SHELL = () => page(200, {
  title: "Your email updates",
  fill: "t",
  submit: "view",
  body: `<h1>Your email updates</h1>
<form id="view" method="post" action="${PATH}"><input type="hidden" name="t" value="">
<input type="hidden" name="action" value="view"><input type="hidden" name="notice" value="">
</form>
<p class="quiet">Opening your page&hellip;</p>`,
});

const STALE = () => message(400, "This link is no longer current",
  "Links in our emails stop working after a while, and all of them stop when a new " +
  "link is asked for. Use the link in your most recent email from Granite Record.");

const GONE = () => message(200, "Your address has been deleted",
  "Your address and everything you followed are deleted, at once and for good. " +
  "Nothing more will be sent. To follow something again, use Follow on its page.");

function hidden(t, action, extra = "") {
  return `<input type="hidden" name="t" value="${esc(t)}">` +
    `<input type="hidden" name="action" value="${esc(action)}">${extra}`;
}

function render(origin, t, sub, follows, current, notice) {
  const list = follows.map(f => {
    const key = `${f.kind}:${f.ref}`;
    const meta = current?.followable.get(key);
    const label = meta?.label || fallbackLabel(f.kind, f.ref);
    const what = meta?.url
      ? `<a href="${esc(siteUrl(origin, meta.url))}">${esc(label)}</a>` : esc(label);
    const title = meta?.title ? `<span class="title">${esc(meta.title)}</span>` : "";
    const last = follows.length === 1;
    return `<li><span class="what">${what}${title}</span>
<form method="post" action="${PATH}">${hidden(t, "remove",
      `<input type="hidden" name="follow" value="${esc(key)}">`)}
<button type="submit" class="plain">${last ? "Remove, and delete my address" : "Remove"}</button></form></li>`;
  }).join("\n");
  const daily = sub.frequency !== "weekly";
  const body = `<h1>Your email updates</h1>
${NOTICES[notice] ? `<p class="note">${esc(NOTICES[notice])}</p>` : ""}
<h2>How often</h2>
<form method="post" action="${PATH}">${hidden(t, "frequency")}
<fieldset><legend class="quiet">Send me updates</legend>
<label><input type="radio" name="value" value="daily"${daily ? " checked" : ""}>
<span>Daily, about 8:00 a.m. New Hampshire time, on days when something is new</span></label>
<label><input type="radio" name="value" value="weekly"${daily ? "" : " checked"}>
<span>Weekly, Saturday about 8:00 a.m., with the week's news and the hearings coming up</span></label>
</fieldset><button type="submit">Save</button></form>
<p class="quiet">The record is rebuilt once a night, so even the daily email reports
the night before, not what is happening now.</p>
<h2>What you follow</h2>
${follows.length ? `<ul class="follows">${list}</ul>` : "<p>Nothing at the moment.</p>"}
<p class="quiet">To follow something else, use Follow on its page.</p>
<h2>A new link</h2>
<p>If you forwarded one of these emails, or think someone else has this link, ask for
a new one. It is sent to your address, and every link in earlier emails stops working,
their unsubscribe links included.</p>
<form method="post" action="${PATH}">${hidden(t, "newlink")}
<button type="submit" class="plain">Send me a new link</button></form>
<h2>Unsubscribe</h2>
<p>Deletes your address and everything you follow, at once. Nothing is kept.</p>
<form method="post" action="${PATH}">${hidden(t, "unsubscribe")}
<button type="submit" class="danger">Unsubscribe and delete my address</button></form>`;
  return page(200, { title: "Your email updates", body });
}

export async function onRequest({ request, env }) {
  if (!env.FOLLOW_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method === "GET" || request.method === "HEAD") return SHELL();
  if (request.method !== "POST") return plain(405, "GET or POST\n", { Allow: "GET, POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const form = await readForm(request);
    const t = form && form.get("t");
    if (!t || !TOKEN.test(t)) return STALE();
    const db = env.FOLLOW_DB;
    const now = clock(env);
    const sub = await subscriberFor(db, t, "manage", now);
    if (!sub) return STALE();
    const origin = new URL(request.url).origin;
    const action = form.get("action") || "view";
    const back = n => redirect(`${PATH}#t=${t}&n=${n}`);

    if (action === "frequency") {
      const v = form.get("value");
      if (v !== "daily" && v !== "weekly") return back("");
      await db.prepare("UPDATE subscribers SET frequency = ?1 WHERE id = ?2").bind(v, sub.id).run();
      return back("saved");
    }
    if (action === "remove") {
      const k = parseKey(form.get("follow"));
      if (!k) return back("");
      const n = await db.prepare("SELECT COUNT(*) AS n FROM follows WHERE subscriber_id = ?1")
        .bind(sub.id).first("n");
      const mine = await db.prepare("SELECT 1 AS y FROM follows WHERE subscriber_id = ?1 " +
        "AND kind = ?2 AND ref = ?3").bind(sub.id, k.kind, k.ref).first();
      if (!mine) return back("");
      if (Number(n) <= 1) {
        await forget(db, { id: sub.id });
        note("manage.forgot", 1);
        return GONE();
      }
      await db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND kind = ?2 AND ref = ?3")
        .bind(sub.id, k.kind, k.ref).run();
      return back("removed");
    }
    if (action === "unsubscribe") {
      await forget(db, { id: sub.id });
      note("manage.forgot", 1);
      return GONE();
    }
    if (action === "newlink") {
      // The new links first, the email, and only then the old links go: an
      // email that fails leaves the reader with the links they had.
      const [m, ms] = await linkStatement(db, sub.id, "manage", now);
      const [u, us] = await linkStatement(db, sub.id, "unsubscribe", now);
      const keep = [await hashToken(m), await hashToken(u)];
      const unmake = () => db.batch(keep.map(h =>
        db.prepare("DELETE FROM links WHERE token_hash = ?1").bind(h)));
      await db.batch([ms, us]);
      let sent;
      try {
        const mail = newLinkEmail({ origin, manage: m, unsub: u, feedbackUrl: env.FEEDBACK_URL });
        sent = await sendMail(env, { to: await openAddress(env, sub.email_enc, sub.email_hmac),
                                     ...mail });
      } catch (e) {
        await unmake();
        throw e;
      }
      if (!sent.ok) {
        await unmake();
        note(`manage.resend-refused.${sent.status}`);
        return message(503, "The new link could not be sent",
          "Nothing has changed: this link still works. Please try again later.");
      }
      await db.prepare("DELETE FROM links WHERE subscriber_id = ?1 AND token_hash NOT IN (?2, ?3)")
        .bind(sub.id, keep[0], keep[1]).run();
      note("manage.new-link", 1);
      return message(200, "A new link is on its way",
        "We have emailed a new link to your address. This link, and every link in " +
        "earlier emails, no longer works.");
    }

    // view
    const follows = (await db.prepare(
      "SELECT kind, ref FROM follows WHERE subscriber_id = ?1 ORDER BY since, kind, ref")
      .bind(sub.id).all()).results || [];
    const cur = await readCurrent(p => env.ASSETS.fetch(new URL(p, request.url)));
    if (!cur.value) note("manage.current-unreadable");
    return render(origin, t, sub, follows, cur.value, form.get("notice") || "");
  } catch (e) {
    note(`manage.error.${errName(e)}`);
    return message(503, "Please try again shortly",
      "Something went wrong on our side. Nothing has changed.");
  }
}
