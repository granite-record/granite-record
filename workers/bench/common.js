/*
 * What every bench Function shares: the switch, the address and origin
 * rules, reading a body, answering, and the log. As workers/follow/common.js
 * does for the follows, and with its readCapped, esc and clock, which are the
 * same here.
 *
 * THE SWITCH IS THE BINDING. Every route answers 404 until BENCH_DB is bound
 * in wrangler.toml for the environment, so code deployed without it changes
 * nothing a reader can reach; preflight holds that every route asks for
 * env.BENCH_DB before anything else.
 *
 * THE TOKEN TRAVELS IN A BODY. A link is /bench#<token>: the part after "#"
 * never leaves the browser, and the page posts the token in the body of each
 * request, never in an address. A wrong token, or a link turned off, costs
 * one indexed read and a 404, the same 404 as no bench at all.
 */

import { clock, esc, readCapped } from "../follow/common.js";

export { clock, esc };

export const MAX_BODY = 4096;

// ---- the log ------------------------------------------------------------------
// A code and a count, and nothing else: no token, no link's name or id, no
// note, no item. The only place in the bench's code that writes to the
// console; preflight holds that.
export function note(code, n) {
  const c = String(code).replace(/[^a-z0-9_.-]/gi, "?").slice(0, 60);
  if (n === undefined || n === null) console.log(`bench ${c}`);
  else console.log(`bench ${c} ${Math.trunc(Number(n)) || 0}`);
}

export function errName(e) {
  const n = e && e.name;
  return typeof n === "string" && /^[A-Za-z]{1,40}$/.test(n) ? n : "Error";
}

// ---- the site's own names ---------------------------------------------------------
// The report box's rule and list (report.js originAllowed), unless the bench
// is given one of its own: the production names on production, every
// <branch>.graniterecord.pages.dev on a preview, localhost in development.
export function allowedHosts(env) {
  return String(env.BENCH_ORIGINS || env.REPORT_ORIGINS ||
    "graniterecord.org www.graniterecord.org").split(/\s+/).filter(Boolean);
}

export function hostAllowed(urlish, env) {
  if (!urlish) return false;
  let host;
  try { host = new URL(urlish).host; } catch { return false; }
  return allowedHosts(env).some(a => (a.startsWith("*.") ? host.endsWith(a.slice(1)) : host === a));
}

// The address a request came to, and the path exactly: the router hands a
// Function its path with a trailing slash and in other cases too.
export function rightPlace(request, env, path) {
  return hostAllowed(request.url, env) && new URL(request.url).pathname === path;
}

// A post from the page carries the site's own Origin, and where the browser
// says where it came from, it says "same-origin". Anything else is refused.
export function sameSite(request, env) {
  const site = request.headers.get("Sec-Fetch-Site");
  if (site && site !== "same-origin") return false;
  return hostAllowed(request.headers.get("Origin"), env);
}

// The body, as JSON, of at most MAX_BODY bytes; null for anything else.
export async function readJson(request) {
  if (!(request.headers.get("Content-Type") || "").startsWith("application/json")) return null;
  const raw = await readCapped(request, MAX_BODY);
  if (raw === null) return null;
  try {
    const v = JSON.parse(raw);
    return v && typeof v === "object" && !Array.isArray(v) ? v : null;
  } catch {
    return null;
  }
}

// ---- answering --------------------------------------------------------------------
// Nothing here is cached, indexed or framed. The JSON answers tell no other
// site where they were asked from.
const BASE = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "X-Robots-Tag": "noindex",
};

export function json(status, obj) {
  return new Response(JSON.stringify(obj), { status, headers: {
    ...BASE, "Referrer-Policy": "same-origin", "Content-Type": "application/json; charset=utf-8" } });
}

export function plain(status, body, extra = {}) {
  return new Response(body, { status, headers: {
    ...BASE, "Referrer-Policy": "same-origin", "Content-Type": "text/plain; charset=utf-8", ...extra } });
}

export function notHere() {
  return plain(404, "Not found\n");
}

// THE PAGE'S OWN RULES. Its script runs under a nonce made for each answer,
// and the one other script allowed is YouTube's player API, from
// www.youtube.com, which plays the recording in a frame from
// www.youtube-nocookie.com, the player the bill pages use. Requests go to
// this site alone. The referrer policy sends another site the origin and
// never the path -- and the token, after "#", is never sent at all: YouTube's
// player is shown the site it is on, as on a bill page.
export const PAGE_REFERRER = "strict-origin-when-cross-origin";

export function pageResponse(status, body, nonce) {
  return new Response(body, { status, headers: {
    ...BASE,
    "Content-Type": "text/html; charset=utf-8",
    "Referrer-Policy": PAGE_REFERRER,
    "Content-Security-Policy": `default-src 'none'; script-src 'nonce-${nonce}' https://www.youtube.com; ` +
      "style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; " +
      "frame-src https://www.youtube-nocookie.com; connect-src 'self'; img-src 'self' data:; " +
      "form-action 'none'; frame-ancestors 'none'; base-uri 'none'",
    "X-Frame-Options": "DENY",
  } });
}

// A note: the report box's cleaning (functions/api/report.js cleanNote: the
// characters that hide text taken out, and said to have been), one line, at
// most `most` characters.
export function oneNote(cleaned, most) {
  return { text: String(cleaned.text || "").replace(/\s+/g, " ").trim().slice(0, most),
           hidden: cleaned.hidden ? 1 : 0 };
}
