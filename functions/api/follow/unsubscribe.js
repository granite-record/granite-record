/*
 * /api/follow/unsubscribe -- deletes an address and everything it follows,
 * at once and for good.
 *
 * Two ways in, one result:
 *   - the mail provider's own button, from the List-Unsubscribe and
 *     List-Unsubscribe-Post headers (RFC 8058): a POST to
 *     /api/follow/unsubscribe?u=<token> whose body is
 *     "List-Unsubscribe=One-Click", sent by the provider's server and so with
 *     no Origin. It is answered 200 whatever happened, as the RFC expects.
 *   - the link in the email's body, whose token is after "#": GET answers a
 *     page with one button, which posts the token from the page (same-site
 *     Origin required). A GET deletes nothing, because mail scanners open
 *     links to look at them.
 * A GET of the header's address -- a client that opens it in a browser
 * rather than posting -- answers the same one-button page.
 *
 * An unsubscribe link can do nothing but this. It cannot open the manage
 * page, so its token in the header's address shows nobody what was followed.
 */

import { TOKEN } from "../../../workers/follow/address.js";
import { clock, errName, esc, note, notHere, plain, readCapped, rightPlace, sameSite }
  from "../../../workers/follow/common.js";
import { message, page } from "../../../workers/follow/page.js";
import { forget, subscriberFor } from "../../../workers/follow/store.js";

const PATH = "/api/follow/unsubscribe";

function button(u) {
  return page(200, {
    title: "Unsubscribe",
    fill: u ? "" : "u",
    body: `<h1>Unsubscribe from email updates</h1>
<p>This deletes your address and everything you follow, at once. Nothing is kept,
and nothing more will be sent.</p>
<form method="post" action="${PATH}"><input type="hidden" name="u" value="${esc(u)}">
<button type="submit" class="danger">Unsubscribe and delete my address</button></form>`,
  });
}

const DONE = () => message(200, "Your address has been deleted",
  "Your address and everything you followed are deleted, at once and for good. " +
  "Nothing more will be sent. To follow something again, use Follow on its page.");

const STALE = () => message(400, "This link is no longer current",
  "It may have been replaced by a newer one, or the address may already be deleted. " +
  "The newest email from Granite Record has a link that works.");

async function drop(env, u) {
  const db = env.FOLLOW_DB;
  const sub = await subscriberFor(db, u, "unsubscribe", clock(env));
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
    const origin = request.headers.get("Origin");
    // The provider's one-click post: token in the address, fixed body.
    if (fromHeader && !origin) {
      const raw = await readCapped(request, 4096);
      if (raw === null || !/One-Click/.test(raw))
        return plain(400, "Bad request\n");
      if (TOKEN.test(fromHeader)) await drop(env, fromHeader);
      return plain(200, "Unsubscribed\n");
    }
    // A post from a browser: from this site's own page, or nothing.
    if (!sameSite(request, env)) return plain(403, "Forbidden\n");
    if (!(request.headers.get("Content-Type") || "")
      .startsWith("application/x-www-form-urlencoded")) return STALE();
    const raw = await readCapped(request, 4096);
    const u = raw === null ? "" : new URLSearchParams(raw).get("u") || fromHeader;
    if (!u || !TOKEN.test(u)) return STALE();
    return (await drop(env, u)) ? DONE() : STALE();
  } catch (e) {
    note(`unsubscribe.error.${errName(e)}`);
    return message(503, "Please try again shortly",
      "Something went wrong on our side, and nothing was deleted. Your link still works.");
  }
}
