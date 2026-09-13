// GRANITE_VERSION: 2026-09-12.1
/*
 * POST /api/report -- a reader says something on a page is wrong.
 *
 * THE ONLY THING ON THIS SITE THAT RUNS. Every byte a reader receives is
 * still a file on a CDN; this is write-only, is on no page's critical path,
 * and if it is down the box on the page falls back to an email link. That is
 * why it is acceptable on a site that is static on purpose.
 *
 * WHAT IS STORED, AND WHAT IS NOT. The record the page was showing, the page's
 * own path, which tab was open, what kind of thing is wrong (picked from a
 * list), the reader's sentence, and the build the page came from -- all of
 * which the page knows without asking. No IP address, no cookie, no
 * identifier, no referrer, no email. Volume is limited by a Cloudflare rate
 * rule in front of this path and by a daily ceiling below, neither of which
 * needs to know who anyone is.
 *
 * EVERY ANSWER IS 204. Success, a honeypot, a bad field, a full day, a
 * database error: the same empty answer, so a script learns nothing about
 * which rule it met. The page shows "thank you" on any 2xx.
 *
 * THE READER'S WORDS ARE NOT TRUSTED HERE OR ANYWHERE AFTER. They are read
 * nightly by a program and then by an assistant, so a report can be written
 * to steer the thing that reads it. This file cannot tell a genuine report
 * from a manipulative one and does not try; it removes the characters that
 * hide text from a human reader (zero-width, direction overrides, tag
 * characters), records THAT it had to, and keeps the rest as plain text.
 * compile_reports.py screens what arrives, and reports/TRIAGE.md is the rule
 * the reading session follows.
 */

const FIELDS = new Set(["date", "status", "sponsor", "vote", "hearing",
  "committee", "text", "link", "chapter", "veto", "topic", "fiscal", "other"]);

// What a page can be, and the one shape its record takes. Measured from the
// built site on 12 September: bills 2026/HB100 (prefixes of 2-6 letters, at
// most four digits), members by numeric id, committees by code (H05, s100).
const RECORD = /^(bill:\d{4}\/[A-Z]{2,6}\d{1,4}|member:\d{1,7}|committee:[A-Za-z]\d{2,3})$/;
const PATH = /^\/(bill\/\d{4}\/[a-z]{2,6}\d{1,4}|legislator\/[a-z0-9-]{1,80}|committee\/[A-Za-z]\d{2,3})$/;
const TAB = /^[A-Za-z][A-Za-z ]{0,23}$/;
const BUILD = /^[0-9T:.+\-Z]{0,40}$/;

const MAX_BODY = 4096;
const MAX_NOTE = 1000;
const MIN_ELAPSED_MS = 3000;   // a person takes longer than this to say what is wrong
const DAILY_CEILING = 500;     // beyond this the day is a flood, not readers

// Characters that change what a human sees without changing what a program
// reads: zero-width and joiners, direction embeddings, overrides and isolates,
// the byte-order mark, the soft hyphen, and the invisible "tag" block.
const HIDDEN = /[\u00AD\u180E\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u2069\uFEFF]|[\u{E0000}-\u{E007F}]/u;
const HIDDEN_ALL = new RegExp(HIDDEN.source, "gu");
const CONTROL_ALL = /[\u0000-\u0008\u000B-\u001F\u007F-\u009F]/g;

export function cleanNote(raw) {
  let t = String(raw ?? "").normalize("NFKC");
  const hidden = HIDDEN.test(t);
  t = t.replace(HIDDEN_ALL, "")
       .replace(/\r\n?/g, "\n")
       .replace(CONTROL_ALL, "")
       .replace(/[ \t]+\n/g, "\n")
       .replace(/\n{3,}/g, "\n\n")
       .trim();
  return { text: t.slice(0, MAX_NOTE), hidden };
}

export function validate(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  if (body.website) return null;                       // the honeypot
  const record = String(body.record ?? "");
  const url = String(body.url ?? "");
  const tab = String(body.tab ?? "").replace(/\s*\(\d[\d,]*\)\s*$/, "").trim();
  const field = String(body.field ?? "");
  const build = String(body.build ?? "");
  const elapsed = Number(body.elapsed);
  if (!RECORD.test(record) || !PATH.test(url) || !FIELDS.has(field)) return null;
  if (tab && !TAB.test(tab)) return null;
  if (!BUILD.test(build)) return null;
  if (!Number.isFinite(elapsed) || elapsed < MIN_ELAPSED_MS) return null;
  // The record and the page must be the same thing: a bill report from a bill
  // page, and the same bill.
  const kind = record.slice(0, record.indexOf(":"));
  if ((kind === "bill") !== url.startsWith("/bill/")) return null;
  if (kind === "bill") {
    const [yr, id] = record.slice(5).split("/");
    if (url !== `/bill/${yr}/${id.toLowerCase()}`) return null;
  }
  if (kind === "committee" && url !== `/committee/${record.slice(10)}`) return null;
  if (kind === "member" && !url.startsWith("/legislator/")) return null;
  const note = cleanNote(body.note);
  if (note.text.length < 3) return null;
  return { record, kind, url, tab, field, build, note: note.text,
           hidden: note.hidden ? 1 : 0 };
}

async function digest(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0"))
    .join("").slice(0, 32);
}

const NOTHING = () => new Response(null, { status: 204 });

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "POST") {
    return new Response("POST only\n", {
      status: 405, headers: { "Allow": "POST", "Content-Type": "text/plain" } });
  }
  try {
    // Same origin only. A browser always sends Origin on a POST from script,
    // and a page on another site sends its own. Absent means not a browser.
    const origin = request.headers.get("Origin");
    if (!origin || origin !== new URL(request.url).origin) return NOTHING();
    // JSON only, which also means a cross-site page cannot send this without
    // a preflight this endpoint never answers.
    if (!(request.headers.get("Content-Type") || "").startsWith("application/json"))
      return NOTHING();
    if (Number(request.headers.get("Content-Length") || 0) > MAX_BODY) return NOTHING();
    const raw = await request.text();
    if (raw.length > MAX_BODY) return NOTHING();
    let body;
    try { body = JSON.parse(raw); } catch { return NOTHING(); }
    const r = validate(body);
    if (!r || !env.DB) return NOTHING();

    const today = new Date().toISOString().slice(0, 10);
    const n = await env.DB.prepare(
      "SELECT COUNT(*) AS n FROM reports WHERE at >= ?1").bind(today).first("n");
    if (n >= DAILY_CEILING) return NOTHING();

    const dedup = await digest([r.record, r.field,
      r.note.toLowerCase().replace(/\s+/g, " ")].join("|"));
    await env.DB.prepare(
      "INSERT OR IGNORE INTO reports " +
      "(at, record, kind, url, tab, field, note, build, hidden, dedup) " +
      "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)")
      .bind(new Date().toISOString(), r.record, r.kind, r.url, r.tab, r.field,
            r.note, r.build, r.hidden, dedup)
      .run();
  } catch (e) {
    // Swallowed on purpose: the reader's box has already said thank you, and
    // an error message is information. It still appears in the Function's
    // own log in the Cloudflare dashboard.
    console.log("report not stored:", e && e.message);
  }
  return NOTHING();
}
