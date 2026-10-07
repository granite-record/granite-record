/*
 * What every follow endpoint and the sender share, apart from the crypto
 * (address.js), the database (store.js), the changes files (changes.js) and
 * the mail (mail.js): what a follow is, how a line reaches the log, which
 * names are the site's, and how an answer is headed.
 *
 * Kept outside functions/ so it can never become a route of its own. The
 * Functions under functions/api/follow/ import it by a relative path; if
 * Pages' bundler will not follow an import out of functions/, this folder's
 * .js files are copied, unchanged, into a folder under functions/ whose files
 * export no onRequest handler, and the imports point there instead.
 */

// ---- what can be followed -------------------------------------------------
// The four kinds, and the ref each page and feed is keyed by. The bill and
// committee patterns are report.js's RECORD; a topic is its feed's slug.
export const KINDS = ["bill", "member", "committee", "topic"];
const REF = {
  bill: /^\d{4}\/[A-Z]{2,6}\d{1,4}$/,
  member: /^\d{1,7}$/,
  committee: /^[A-Za-z]\d{2,3}(?:-\d{4})?$/,
  topic: /^[a-z0-9]+(?:-[a-z0-9]+)*$/,
};

export function refOk(kind, ref) {
  return typeof kind === "string" && Object.hasOwn(REF, kind) &&
    typeof ref === "string" && ref.length <= 80 && REF[kind].test(ref);
}

export const keyOf = (kind, ref) => `${kind}:${ref}`;

export function parseKey(k) {
  const s = String(k ?? "");
  const i = s.indexOf(":");
  if (i < 1) return null;
  const kind = s.slice(0, i), ref = s.slice(i + 1);
  return refOk(kind, ref) ? { kind, ref } : null;
}

// A name for a record when the changes file has none for it any more (a
// member who no longer sits, a bill that has finished).
export function fallbackLabel(kind, ref) {
  if (kind === "bill") {
    const [year, id] = ref.split("/");
    const m = /^([A-Z]+)(\d+)$/.exec(id || "");
    return m ? `${m[1]} ${m[2]} (${year})` : ref;
  }
  if (kind === "member") return `Legislator no. ${ref}`;
  if (kind === "committee") return `Committee ${ref}`;
  return ref.split("-").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
}

// The longest follow list one address may hold. A page of the site offers one
// record at a time, so this is far beyond what a reader builds by hand.
export const MAX_FOLLOWS = 200;

// ---- the log --------------------------------------------------------------
// EVERY LINE IS A CODE AND A COUNT, AND NOTHING ELSE. No address, no token,
// no follow, no error message: a message is information, and the messages
// these calls can raise include the address they were given (Resend's
// "Invalid `to` field: ..." does). So a caught error is logged by its name
// alone, and that name only if it is a plain word. This is the only place in
// the follow code that writes to the console; preflight holds that.
export function note(code, n) {
  const c = String(code).replace(/[^a-z0-9_.-]/gi, "?").slice(0, 60);
  if (n === undefined || n === null) console.log(`follow ${c}`);
  else console.log(`follow ${c} ${Math.trunc(Number(n)) || 0}`);
}

export function errName(e) {
  const n = e && e.name;
  return typeof n === "string" && /^[A-Za-z]{1,40}$/.test(n) ? n : "Error";
}

// ---- the site's own names ---------------------------------------------------
// The same rule as report.js's originAllowed, and the same list unless one is
// given for following alone: the production names on production, every
// <branch>.graniterecord.pages.dev on a preview, localhost in development.
// Asked of the address a request was sent to, and of its Origin header.
export function allowedHosts(env) {
  return String(env.FOLLOW_ORIGINS || env.REPORT_ORIGINS ||
    "graniterecord.org www.graniterecord.org").split(/\s+/).filter(Boolean);
}

export function hostAllowed(urlish, env) {
  if (!urlish) return false;
  let host;
  try { host = new URL(urlish).host; } catch { return false; }
  return allowedHosts(env).some(a =>
    a.startsWith("*.") ? host.endsWith(a.slice(1)) : host === a);
}

// The address a request came to, and the path exactly: the router hands a
// Function /api/follow/x/ and case variants too (report.js, 13 September).
export function rightPlace(request, env, path) {
  if (!hostAllowed(request.url, env)) return false;
  return new URL(request.url).pathname === path;
}

// A state-changing post from a browser carries an Origin, and on this site it
// must be the site's own. Sec-Fetch-Site, where the browser sends it, must say
// the same. A post with no Origin is not a browser's form and is refused.
export function sameSite(request, env) {
  const site = request.headers.get("Sec-Fetch-Site");
  if (site && site !== "same-origin") return false;
  return hostAllowed(request.headers.get("Origin"), env);
}

// ---- time ------------------------------------------------------------------
// Tests set env.CLOCK; wrangler can only ever set a string there, so in a
// deployment it is never a function and the real clock is used.
export function clock(env) {
  return typeof env?.CLOCK === "function" ? new Date(env.CLOCK()) : new Date();
}

export const isoSeconds = d => d.toISOString().replace(/\.\d{3}Z$/, "Z");

// New Hampshire's clock. The IANA zone carries the daylight-saving rule, so
// the rule is not written out here to go stale if the law changes.
const NH = new Intl.DateTimeFormat("en-US", {
  timeZone: "America/New_York", hourCycle: "h23", weekday: "short",
  year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
});

export function nhClock(now) {
  const p = Object.fromEntries(NH.formatToParts(now).map(x => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour) % 24,
           minute: Number(p.minute), weekday: p.weekday };
}

export function addDays(day, n) {
  const t = Date.UTC(+day.slice(0, 4), +day.slice(5, 7) - 1, +day.slice(8, 10)) + n * 86400000;
  return new Date(t).toISOString().slice(0, 10);
}

// ---- reading a request -------------------------------------------------------
export async function readCapped(request, max) {
  if (Number(request.headers.get("Content-Length") || 0) > max) return null;
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > max) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) { all.set(c, at); at += c.byteLength; }
  return new TextDecoder().decode(all);
}

export async function readForm(request, max = 4096) {
  if (!(request.headers.get("Content-Type") || "")
    .startsWith("application/x-www-form-urlencoded")) return null;
  const raw = await readCapped(request, max);
  return raw === null ? null : new URLSearchParams(raw);
}

// ---- answering ---------------------------------------------------------------
// Nothing here is cached, indexed, framed or sent on as a referrer: a page
// that carries a private link in its forms must not hand it to the next site
// a reader clicks through to.
const BASE = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "X-Robots-Tag": "noindex",
};

export function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status, headers: { ...BASE, "Content-Type": "application/json; charset=utf-8" } });
}

export function plain(status, body, extra = {}) {
  return new Response(body, {
    status, headers: { ...BASE, "Content-Type": "text/plain; charset=utf-8", ...extra } });
}

export function empty(status, extra = {}) {
  return new Response(null, { status, headers: { ...BASE, ...extra } });
}

export function htmlResponse(status, body, nonce = "") {
  const script = nonce ? `'nonce-${nonce}'` : "'none'";
  return new Response(body, {
    status,
    headers: {
      ...BASE,
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": `default-src 'none'; style-src 'unsafe-inline'; ` +
        `script-src ${script}; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`,
      "X-Frame-Options": "DENY",
    },
  });
}

export function redirect(location) {
  return new Response(null, { status: 303, headers: { ...BASE, Location: location } });
}

export function notHere() {
  return plain(404, "Not found\n");
}

// ---- writing a value into a page ------------------------------------------------
// EVERY value that reaches HTML goes through esc(), whether it came from a
// reader, the database or the changes file: a label is the site's own data,
// and is escaped all the same.
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ESC[c]);
}

// Plain text from the changes file or the database: control characters and
// line breaks out, length capped. What an email's subject or a line is made of.
export function oneLine(s, max = 300) {
  const t = String(s ?? "").replace(/[\u0000-\u001f\u007f-\u009f]+/g, " ")
    .replace(/\s+/g, " ").trim();
  return t.length <= max ? t : t.slice(0, max - 1).trimEnd() + "…";
}

// A path on the site, made a whole address. Anything that is not a plain
// path -- another site, a scheme, a protocol-relative "//" -- becomes the
// site's front page instead of a link somewhere else.
const PATH = /^\/(?!\/)[A-Za-z0-9\-._~/?=&%+]*$/;
export function siteUrl(origin, path) {
  return PATH.test(String(path ?? "")) ? origin + path : origin + "/";
}
