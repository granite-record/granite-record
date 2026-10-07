/*
 * /api/follow/manage -- a reader's own page: what they follow, how often,
 * a new link, and unsubscribe. A private link, not a login, and the same
 * link at the foot of every email until the reader asks for a new one.
 *
 * GET answers a shell whose script reads the token from after "#" and posts
 * it straight back (action=view), so the token travels in a body and never in
 * an address. Every POST must come from this site's own page (common.sameSite).
 * A post from anywhere else changes nothing, and there are no cookies here for
 * another site to borrow.
 *
 * WHAT THE PAGE SHOWS. What the link's holder follows and how often. Never
 * the address: a link forwarded with an email must not hand the address on.
 *
 * ACTIONS (POST, form-encoded, t = the token):
 *   view                    the page
 *   frequency value=daily|weekly
 *   remove    follow=<kind>:<ref>   -- removing the last one deletes the address
 *   newlink                 the links move to a new generation in one statement,
 *                           and the new ones are emailed to the address, not
 *                           shown here; every earlier link stops working
 *   unsubscribe             the address and everything it follows, deleted
 */

import { TOKEN, followHash, linksFor, openAddress, openFollow }
  from "../../../workers/follow/address.js";
import { errName, esc, fallbackLabel, keyOf, note, notHere, parseKey, plain,
         readForm, redirect, rightPlace, sameSite, siteUrl } from "../../../workers/follow/common.js";
import { readCurrent } from "../../../workers/follow/changes.js";
import { newLinkEmail, sendMail } from "../../../workers/follow/mail.js";
import { DELETES, deleted, message, page } from "../../../workers/follow/page.js";
import { forget, subscriberFor } from "../../../workers/follow/store.js";

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
  "Every link in our emails stops working when a new link is asked for, and the " +
  "address may since have been deleted. Use the link in your most recent email " +
  "from Granite Record.");

const ON_ITS_WAY = () => message(200, "A new link is on its way",
  "We have emailed a new link to your address. This link, and every link in " +
  "earlier emails, no longer works.");

function hidden(t, action, extra = "") {
  return `<input type="hidden" name="t" value="${esc(t)}">` +
    `<input type="hidden" name="action" value="${esc(action)}">${extra}`;
}

// What the reader follows, opened: [{ key, since }], or a follow that will
// not open is left out and counted.
async function followed(env, db, sub) {
  const rows = (await db.prepare(
    "SELECT follow_enc, since FROM follows WHERE subscriber_id = ?1").bind(sub.id).all())
    .results || [];
  const out = [];
  let bad = 0;
  for (const r of rows) {
    try {
      const key = await openFollow(env, r.follow_enc, sub.email_hmac);
      if (parseKey(key)) out.push({ key, since: r.since }); else bad++;
    } catch { bad++; }
  }
  if (bad) note("manage.unreadable-follow", bad);
  return out.sort((a, b) => a.since.localeCompare(b.since) || a.key.localeCompare(b.key));
}

function render(origin, t, sub, follows, current, notice) {
  const list = follows.map(({ key }) => {
    const { kind, ref } = parseKey(key);
    const meta = current?.followable.get(key);
    const label = meta?.label || fallbackLabel(kind, ref);
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
<p>This page's link is the same in every email we send you. If you forwarded one
of them, or think someone else has this link, ask for a new one. It is sent to
your address, and every link in earlier emails stops working, their unsubscribe
links included.</p>
<form method="post" action="${PATH}">${hidden(t, "newlink")}
<button type="submit" class="plain">Send me a new link</button></form>
<h2>Unsubscribe</h2>
<p>${esc(DELETES)}</p>
<form method="post" action="${PATH}">${hidden(t, "unsubscribe")}
<button type="submit" class="danger">Unsubscribe and delete my address</button></form>`;
  return page(200, { title: "Your email updates", body });
}

// "SEND ME A NEW LINK". The links move to the next generation in ONE
// statement that names the link that asked: of two presses at once (a
// double-click), one moves them and the other finds its link no longer
// current and sends nothing, so one email goes and its links work. The email
// goes after the move; if it cannot be sent, the move is undone by a second
// statement that names the new link, so the reader keeps the links they had.
async function newLink(env, db, sub, origin) {
  const next = await linksFor(env, sub.email_hmac, sub.link_gen + 1);
  const moved = await db.prepare(
    "UPDATE subscribers SET link_gen = ?1, manage_hash = ?2, unsub_hash = ?3 " +
    "WHERE id = ?4 AND manage_hash = ?5")
    .bind(sub.link_gen + 1, next.manageHash, next.unsubHash, sub.id, sub.manage_hash).run();
  if (!moved?.meta?.changes) {
    note("manage.new-link-already-moving");
    return ON_ITS_WAY();
  }
  const undo = () => db.prepare(
    "UPDATE subscribers SET link_gen = ?1, manage_hash = ?2, unsub_hash = ?3 " +
    "WHERE id = ?4 AND manage_hash = ?5")
    .bind(sub.link_gen, sub.manage_hash, sub.unsub_hash, sub.id, next.manageHash).run();
  let sent;
  try {
    const mail = newLinkEmail({ origin, manage: next.manage, unsub: next.unsub,
                                feedbackUrl: env.FEEDBACK_URL });
    sent = await sendMail(env, { to: await openAddress(env, sub.email_enc, sub.email_hmac),
                                 ...mail });
  } catch (e) {
    await undo();
    throw e;
  }
  if (!sent.ok) {
    await undo();
    note(`manage.resend-refused.${sent.status}`);
    return message(503, "The new link could not be sent",
      "Nothing has changed: this link still works. Please try again later.");
  }
  note("manage.new-link", 1);
  return ON_ITS_WAY();
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
    const sub = await subscriberFor(db, t, "manage");
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
      const fh = await followHash(env, sub.email_hmac, keyOf(k.kind, k.ref));
      const n = await db.prepare("SELECT COUNT(*) AS n FROM follows WHERE subscriber_id = ?1")
        .bind(sub.id).first("n");
      const mine = await db.prepare("SELECT 1 AS y FROM follows WHERE subscriber_id = ?1 " +
        "AND follow_hmac = ?2").bind(sub.id, fh).first();
      if (!mine) return back("");
      if (Number(n) <= 1) {
        await forget(db, { id: sub.id });
        note("manage.forgot", 1);
        return deleted();
      }
      await db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND follow_hmac = ?2")
        .bind(sub.id, fh).run();
      return back("removed");
    }
    if (action === "unsubscribe") {
      await forget(db, { id: sub.id });
      note("manage.forgot", 1);
      return deleted();
    }
    if (action === "newlink") return await newLink(env, db, sub, origin);

    // view
    const follows = await followed(env, db, sub);
    const cur = await readCurrent(p => env.ASSETS.fetch(new URL(p, request.url)));
    if (!cur.value) note("manage.current-unreadable");
    return render(origin, t, sub, follows, cur.value, form.get("notice") || "");
  } catch (e) {
    note(`manage.error.${errName(e)}`);
    return message(503, "Please try again shortly",
      "Something went wrong on our side. Nothing has changed.");
  }
}
