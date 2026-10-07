// What the follow code talks to, faked: Resend, Turnstile, the site's own
// files (env.ASSETS for a Function, the public site for the sender), and the
// console. Nothing here touches the network: any request to a host that is
// not one of these fails the test that made it.
//
// Every key, secret and token is made at run time from random bytes and
// lives only in memory. Every address is invented, on example.com.

import { FakeD1 } from "./fake_d1.js";
import { loadFixtures } from "./fixtures.js";

export { FIXTURES, loadFixtures } from "./fixtures.js";
export const SITE = "https://graniterecord.org";

const b64 = bytes => Buffer.from(bytes).toString("base64");
const random = n => crypto.getRandomValues(new Uint8Array(n));

export function makeKeys() {
  return {
    FOLLOW_ADDRESS_KEY: b64(random(32)),
    FOLLOW_LOOKUP_KEY: b64(random(32)),
    RESEND_API_KEY: "test-" + Buffer.from(random(12)).toString("hex"),
    TURNSTILE_SECRET: "test-" + Buffer.from(random(12)).toString("hex"),
    RESEND_WEBHOOK_SECRET: "whsec_" + b64(random(24)),
  };
}

export function captureConsole() {
  const lines = [];
  const saved = {};
  for (const m of ["log", "info", "warn", "error", "debug", "trace"]) {
    saved[m] = console[m];
    console[m] = (...a) => lines.push(a.map(x => (x instanceof Error ? `${x.name}: ${x.message}` :
      typeof x === "string" ? x : JSON.stringify(x))).join(" "));
  }
  return { lines, restore() { Object.assign(console, saved); } };
}

export class FakeNet {
  constructor() {
    this.outbox = [];               // what Resend was asked to send
    this.resendStatus = 200;        // what Resend answers
    this.turnstileSecret = "";
    this.site = new Map();          // path -> JSON value
    this.asked = [];                // every address asked, origin and path
  }

  install() {
    this.saved = globalThis.fetch;
    globalThis.fetch = (input, init) => this.handle(new Request(input, init));
  }

  restore() { globalThis.fetch = this.saved; }

  async handle(req) {
    const u = new URL(req.url);
    this.asked.push(u.origin + u.pathname);
    if (u.origin === "https://api.resend.com" && u.pathname === "/emails" && req.method === "POST") {
      const body = await req.json();
      const mail = { ...body, auth: req.headers.get("Authorization"),
                     at: this.clock ? new Date(this.clock()).toISOString() : null };
      if (this.resendStatus !== 200) {
        this.refused = (this.refused || 0) + 1;
        // Resend's error names the address it refused, which is exactly why
        // no error body may reach a log.
        return new Response(JSON.stringify({ statusCode: this.resendStatus,
          name: "validation_error", message: `Invalid \`to\` field: ${body.to?.[0]}` }),
          { status: this.resendStatus, headers: { "Content-Type": "application/json" } });
      }
      this.outbox.push(mail);
      return Response.json({ id: `fake-${this.outbox.length}` });
    }
    if (u.origin === "https://challenges.cloudflare.com" &&
        u.pathname === "/turnstile/v0/siteverify") {
      const f = new URLSearchParams(await req.text());
      const ok = f.get("secret") === this.turnstileSecret && f.get("response") === "pass";
      return Response.json({ success: ok });
    }
    if (u.origin === SITE) return this.asset(u.pathname);
    throw new Error(`the tests ask no network, and this asked ${u.origin}`);
  }

  asset(path) {
    const v = this.site.get(path);
    if (v === undefined) return new Response("Not found", { status: 404 });
    return new Response(typeof v === "string" ? v : JSON.stringify(v),
      { status: 200, headers: { "Content-Type": "application/json" } });
  }

  // A Pages Function's env.ASSETS.
  binding() {
    return { fetch: req => this.asset(new URL(req instanceof Request ? req.url : String(req)).pathname) };
  }
}

// ---- a world: one database, one fake network, one captured console ---------------
export function makeWorld({ now = "2026-10-06T15:00:00Z", fixtures = true } = {}) {
  const d1 = new FakeD1();
  const net = new FakeNet();
  if (fixtures) for (const [p, v] of loadFixtures()) net.site.set(p, v);
  const keys = makeKeys();
  net.turnstileSecret = keys.TURNSTILE_SECRET;
  net.clock = () => w.now.getTime();
  const w = {
    d1, net, keys, now: new Date(now), responses: [],
    addresses: new Set(),
  };
  w.env = {
    FOLLOW_DB: d1,
    ASSETS: net.binding(),
    FOLLOW_ORIGINS: "graniterecord.org www.graniterecord.org",
    SITE_ORIGIN: SITE,
    MAIL_FROM: "Granite Record <updates@example.com>",
    FEEDBACK_URL: "https://forms.example.com/feedback",
    SEND_GAP_MS: "0",
    ...keys,
    CLOCK: () => w.now.getTime(),
  };
  w.logs = captureConsole();
  net.install();
  w.close = () => { net.restore(); w.logs.restore(); };
  w.at = iso => { w.now = new Date(iso); };
  w.later = hours => { w.now = new Date(w.now.getTime() + hours * 3600000); };
  w.address = name => { const a = `${name}@example.com`; w.addresses.add(a); return a; };
  // Call a Function and keep what it answered.
  w.call = async (handler, request) => {
    const res = await handler({ request, env: w.env, waitUntil() {} });
    const body = res.body ? await res.clone().text() : "";
    const rec = { url: request.url, method: request.method, status: res.status,
                  headers: Object.fromEntries(res.headers), body };
    w.responses.push(rec);
    return rec;
  };
  return w;
}

// ---- requests ---------------------------------------------------------------------
export function postJson(path, obj, { origin = SITE, headers = {} } = {}) {
  return new Request(SITE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json",
               ...(origin ? { Origin: origin } : {}), ...headers },
    body: JSON.stringify(obj),
  });
}

export function postForm(path, fields, { origin = SITE, fetchSite = "same-origin",
                                          headers = {}, query = "" } = {}) {
  return new Request(SITE + path + query, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded",
               ...(origin ? { Origin: origin } : {}),
               ...(fetchSite ? { "Sec-Fetch-Site": fetchSite } : {}), ...headers },
    body: new URLSearchParams(fields).toString(),
  });
}

export const get = (path, query = "") => new Request(SITE + path + query);

// ---- reading what was sent ------------------------------------------------------------
export function tokensIn(mail) {
  const all = `${mail.text || ""} ${mail.html || ""} ${JSON.stringify(mail.headers || {})}`;
  const one = re => (all.match(re) || [])[1] || null;
  return {
    confirm: one(/confirm#t=([A-Za-z0-9_-]{43})/),
    manage: one(/manage#t=([A-Za-z0-9_-]{43})/),
    unsub: one(/unsubscribe#u=([A-Za-z0-9_-]{43})/),
    header: one(/unsubscribe\?u=([A-Za-z0-9_-]{43})/),
  };
}

export function everyToken(w) {
  const out = new Set();
  for (const m of w.net.outbox) {
    const all = `${m.text || ""} ${m.html || ""} ${JSON.stringify(m.headers || {})}`;
    for (const x of all.matchAll(/[#?][tu]=([A-Za-z0-9_-]{43})/g)) out.add(x[1]);
  }
  for (const r of w.responses) {
    const loc = r.headers.location || "";
    for (const x of loc.matchAll(/[#?][tu]=([A-Za-z0-9_-]{43})/g)) out.add(x[1]);
  }
  return out;
}

export const lastMailTo = (w, address) =>
  [...w.net.outbox].reverse().find(m => (m.to || []).includes(address));

// ---- the guarantee every test ends on ----------------------------------------------------
// No log line carries an address, a token or a record a reader follows, and no
// answer carries an address. Returns a list of what leaked, for an assertion.
export function leaks(w, { refs = ["HB9901", "HB9902", "HB9903", "990001", "H90",
                                   "housing", "elections"] } = {}) {
  const found = [];
  const lower = s => s.toLowerCase();
  const addrs = [...w.addresses].map(lower);
  const tokens = [...everyToken(w)];
  for (const line of w.logs.lines) {
    const l = lower(line);
    for (const a of addrs) if (l.includes(a) || l.includes(a.split("@")[0])) found.push(`log has an address: ${line}`);
    for (const t of tokens) if (line.includes(t)) found.push(`log has a token: ${line}`);
    for (const r of refs) if (l.includes(lower(r))) found.push(`log has a record: ${line}`);
    if (!/^follow [a-z0-9_.?-]+( \d+)?$/i.test(line)) found.push(`log line is not a code and a count: ${line}`);
  }
  for (const r of w.responses) {
    const all = lower(r.body + JSON.stringify(r.headers));
    for (const a of addrs) if (all.includes(a)) found.push(`answer to ${r.url} has an address`);
  }
  return found;
}
