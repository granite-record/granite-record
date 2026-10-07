/*
 * /api/follow/unsubscribe -- deletes an address and everything it follows
 * from the database, at once (page.js DELETES says what that does and does
 * not reach).
 *
 * Two ways in, one result:
 *   - the mail provider's own button, from the List-Unsubscribe and
 *     List-Unsubscribe-Post headers (RFC 8058): a POST to
 *     /api/follow/unsubscribe?u=<token> whose body is
 *     "List-Unsubscribe=One-Click". It is answered 200 whatever happened, as
 *     the RFC expects. What it carries decides it, not where it came from:
 *     the token is the only authority here and there is no cookie to borrow,
 *     so an Origin -- a provider's, or "null" -- changes nothing.
 *   - the link in the email's body, whose token is after "#": GET answers a
 *     page with one button, which posts the token from the page (same-site,
 *     common.sameSite). A GET deletes nothing, because mail scanners open
 *     links to look at them.
 * A GET of the header's address -- a client that opens it in a browser
 * rather than posting -- answers the same one-button page, and spends
 * nothing until the button is pressed.
 *
 * An unsubscribe link can do nothing but this. It cannot open the manage
 * page, so its token in the header's address -- the one place a token is in
 * a request address, and so in Cloudflare's request log -- shows nobody what
 * was followed.
 */

import { TOKEN } from "../../../workers/follow/address.js";
import { errName, esc, note, notHere, plain, readCapped, rightPlace, sameSite }
  from "../../../workers/follow/common.js";
import { DELETES, deleted, message, page } from "../../../workers/follow/page.js";
import { forget, subscriberFor } from "../../../workers/follow/store.js";

const PATH = "/api/follow/unsubscribe";

function button(u) {
  return page(200, {
    title: "Unsubscribe",
    fill: u ? "" : "u",
    body: `<h1>Unsubscribe from email updates</h1>
<p>${esc(DELETES)}</p>
<form method="post" action="${PATH}"><input type="hidden" name="u" value="${esc(u)}">
<button type="submit" class="danger">Unsubscribe and delete my address</button></form>`,
  });
}

const STALE = () => message(400, "This link is no longer current",
  "It may have been replaced by a newer one, or the address may already be deleted. " +
  "The newest email from Granite Record has a link that works.");

// RFC 8058's body, form-encoded or multipart, and nothing else.
function oneClickBody(type, raw) {
  if (type.startsWith("application/x-www-form-urlencoded"))
    return new URLSearchParams(raw).get("List-Unsubscribe") === "One-Click";
  if (type.startsWith("multipart/form-data"))
    return /name="?List-Unsubscribe"?\s*\r?\n\r?\n\s*One-Click\s*(\r?\n|$)/.test(raw);
  return false;
}

async function drop(env, u) {
  const db = env.FOLLOW_DB;
  const sub = await subscriberFor(db, u, "unsubscribe");
  if (!sub) return false;
  await forget(db, { id: sub.id });
  note("unsubscribe.forgot", 1);
  return true;
}

export async function onRequest({ request, env }) {
  if (!env.FOLLOW_DB || !rightPlace(request, env, PATH)) return notHere();
  const fromHeader = new URL(request.url).searchParams.get("u") || "";
  if (request.method === "GET" || request.method === "HEAD")
    return button(TOKEN.test(fromHeader) ? fromHeader : "");
  if (request.method !== "POST") return plain(405, "GET or POST\n", { Allow: "GET, POST" });
  try {
    const type = request.headers.get("Content-Type") || "";
    const raw = await readCapped(request, 4096);
    if (raw === null) return plain(413, "Too large\n");
    // The provider's one-click post: token in the address, fixed body.
    if (fromHeader && oneClickBody(type, raw)) {
      if (!TOKEN.test(fromHeader) || !(await drop(env, fromHeader)))
        note("unsubscribe.one-click-matched-nothing");
      return plain(200, "Unsubscribed\n");
    }
    // A post with the header's address and some other body, from no page.
    if (fromHeader && !request.headers.get("Origin")) return plain(400, "Bad request\n");
    // A post from a browser: from this site's own page, or nothing.
    if (!sameSite(request, env)) return plain(403, "Forbidden\n");
    if (!type.startsWith("application/x-www-form-urlencoded")) return STALE();
    const u = new URLSearchParams(raw).get("u") || fromHeader;
    if (!u || !TOKEN.test(u)) return STALE();
    return (await drop(env, u)) ? deleted() : STALE();
  } catch (e) {
    note(`unsubscribe.error.${errName(e)}`);
    return message(503, "Please try again shortly",
      "Something went wrong on our side, and nothing was deleted. Your link still works.");
  }
}
