// GRANITE_VERSION: 2026-09-12.14
/*
 * POST /api/report -- a reader says something on a page is wrong.
 *
 * ONE OF TWO THINGS ON THIS SITE THAT RUN. The other is email following
 * (functions/api/follow/ and the sender in workers/follow/), live on
 * graniterecord.org since 23 October 2026, which only a reader who asks for
 * updates reaches. Every page a reader receives is still a file on a CDN;
 * this is write-only, is on no page's critical path, and if it is down the
 * box on the page falls back to an email link. That is why it is acceptable
 * on a site that is static on purpose.
 *
 * WHAT IS STORED, AND WHAT IS NOT. The record the page was showing, the page's
 * own path, which tab was open (one of the tabs the pages render), what kind of
 * thing is wrong (from a list), the reader's sentence, and the build the page
 * came from. No IP address, no cookie, no identifier, no referrer, no email.
 * Volume is limited by a Cloudflare rate rule in front of this path and a daily
 * ceiling below, neither of which needs to know who anyone is. The rate rule
 * lives on the graniterecord.org zone and sees only the site's own names, so
 * since 13 September a post sent to any other address, or to any path but
 * /api/report exactly, is refused before its body is read.
 *
 * EVERY ANSWER TO A POST IS 204, BUT TWO. Success, a duplicate, a honeypot, a
 * bad field: the same empty answer, so a script learns nothing. The
 * exceptions are the two reports that passed every rule and then could not be
 * kept, because the box offers the email address only on a reply that is not
 * a success:
 *   - no database bound, or the database refused the write: 503. Until
 *     24 September a storage failure was answered 204, the reader was thanked,
 *     and the report existed only in the Function's log.
 *   - the day's ceiling already reached: 429. It was 204 as well, so on the
 *     day the ceiling was hit every reader after the five hundredth was
 *     thanked for a report nobody would see. The person asked on 24 September
 *     for the email address instead, while doubting the day will ever come.
 * Neither helps a script: a 503 says storage is down, and a 429 says the day
 * is full, which a script that filled it already knows.
 *
 * THE READER'S WORDS ARE NOT TRUSTED HERE OR ANYWHERE AFTER. compile_reports.py
 * screens what arrives before any assistant reads it, and reports/TRIAGE.md is
 * the rule the reading session follows.
 *
 * RED-TEAMED ON 12 SEPTEMBER. Verified and fixed here: a member report's page
 * address was never matched to the member, so it could carry 80 characters of
 * the sender's words into the triage file outside the quotation; the tab was
 * free text, the same hole in 24 letters, and a reader on the Co-sponsored tab
 * had their report silently dropped; the daily ceiling was a count then an
 * insert, so simultaneous posts ran past it and every post read the whole
 * day's rows; a body with no Content-Length was read whole before the size
 * check; a duplicate never expired, so a report repeated after a fix vanished;
 * the invisible-character list missed direction marks, variation selectors and
 * fillers; and every old production deployment address kept taking reports.
 */

export const FIELDS = new Set(["date", "status", "sponsor", "vote", "hearing",
  "committee", "text", "link", "chapter", "veto", "topic", "fiscal", "other"]);

// The tabs the pages render. compile_reports.TABS is the same list, and
// preflight holds the two together.
export const TABS = new Set(["", "Summary", "Bill Text", "Votes", "Hearings", "Reports",
  "Sponsors", "Documents", "Related", "Prime sponsored", "Co-sponsored", "Bills", "Meetings"]);
// A TAB'S OLD NAME, AND ITS NAME NOW (8 October 2026). A bill's Hearings tab
// was Videos, and a committee's Meetings tab was Sessions (the person's words,
// D19), and a page loaded before either was renamed still sends the old name;
// it is stored under the name the tab has. compile_reports.RENAMED_TABS is the
// same map, for the reports already stored under the old one.
export const RENAMED_TABS = new Map([["Videos", "Hearings"], ["Sessions", "Meetings"]]);

// What a page can be, and the one shape its record takes. Measured from the
// built site on 12 September: bills 2026/HB100, members by numeric id,
// committees by code (H05, s100) -- or, for a committee the General Court
// filed under a code it later gave a different one, by the code and the first
// year of its run (S03-1989, 25 September), which no code of theirs can be.
//
// AND A PAGE IN ANOTHER LANGUAGE, whose translation a reader says is wrong
// (the owner, 24 October 2026: "We should also add a report button for
// translation inaccuracy."). Its record is "translation:" and the page's own
// address, which names its language -- /es/, /es/guides/how-to-vote -- at
// most three words deep, in the lower case and hyphens a page's address is
// written in. Its field is TRANSLATION and no other kind's is; it has no
// tab; and onRequest keeps it only where the page there is one the site
// built in that language (translatedPage). A new language is a new prefix
// here and in compile_reports.py, and preflight sends a report from every
// page the build writes in one.
//
// AND A SESSION DAY AND A STUDY COMMITTEE (the cohesion audit of 30 October
// 2026, I-8: a mistake on either had no button). A session day's record is
// its chamber and date, "session:H/2010-03-11", from /session/H/2010-03-11; a
// study committee's is its page's own name, "study:ss1451", from
// /committee/ss1451. Each is accepted only from its own address.
const RECORD = /^(bill:\d{4}\/[A-Z]{2,6}\d{1,4}|member:\d{1,7}|committee:[A-Za-z]\d{2,3}(?:-\d{4})?|session:[HS]\/\d{4}-\d{2}-\d{2}|study:ss\d{1,6}|translation:\/es\/(?:[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*){0,2})?)$/;
const PATH = /^\/(bill\/\d{4}\/[a-z]{2,6}\d{1,4}|legislator\/[a-z0-9-]{1,80}|committee\/[A-Za-z]\d{2,3}(?:-\d{4})?|session\/[HS]\/\d{4}-\d{2}-\d{2}|committee\/ss\d{1,6}|es\/(?:[a-z0-9]+(?:-[a-z0-9]+)*(?:\/[a-z0-9]+(?:-[a-z0-9]+)*){0,2})?)$/;
export const TRANSLATION = "translation";
const BUILD = /^[0-9T:.+\-Z]{0,40}$/;
// A legislator's address is the slug build_site_v2.member_slug writes: the
// name, then the county or "sd", then the district, lowercased, with every run
// of anything else made one hyphen. NOT "ends in a number". The 12 September
// rule said every address did, and it was true of the sitting roster; a former
// member whose seat the record does not hold has a slug of the name alone --
// /legislator/adam-schroadter and seven more -- and a report from any of their
// pages was refused while the reader was thanked. The slug is a sender's
// choice, so onRequest still accepts it only if the page there is that
// member's. preflight runs every built legislator page through this file.
const MEMBER_PAGE = /^\/legislator\/[a-z0-9]+(-[a-z0-9]+)*$/;

const MAX_BODY = 4096;
const MAX_NOTE = 1000;
const MIN_ELAPSED_MS = 3000;   // a person takes longer than this to say what is wrong
const DAILY_CEILING = 500;     // beyond this the day is a flood, not readers

// Characters that change what a person sees without changing the text:
// format characters (zero-width, direction marks and overrides, the tag
// block, the byte-order mark, the soft hyphen), variation selectors, the
// combining grapheme joiner, and the Hangul fillers. Tested by code point, so
// this file carries none of them.
const FORMAT = /\p{Cf}/u;
function invisible(cp) {
  return FORMAT.test(String.fromCodePoint(cp)) || cp === 0x034F || cp === 0x115F ||
    cp === 0x1160 || cp === 0x3164 || cp === 0xFFA0 || (cp >= 0xFE00 && cp <= 0xFE0F) ||
    (cp >= 0xE0100 && cp <= 0xE01EF);
}

export function cleanNote(raw) {
  const t = String(raw ?? "").normalize("NFKC").replace(/\r\n?/g, "\n");
  let out = "", hidden = false;
  for (const ch of t) {
    const cp = ch.codePointAt(0);
    if (invisible(cp)) { hidden = true; continue; }
    if ((cp < 0x20 && cp !== 0x0A && cp !== 0x09) || (cp >= 0x7F && cp <= 0x9F)) continue;
    out += ch;
  }
  out = out.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  return { text: out.slice(0, MAX_NOTE), hidden };
}

// "Votes (1,081)", "Votes (1.081)", "Votes (1 081)": the count in any locale.
export function tabName(raw) {
  return String(raw ?? "").replace(/\s*\([\d.,\s']+\)\s*$/, "").trim();
}

export function validate(body) {
  if (!body || typeof body !== "object" || Array.isArray(body)) return null;
  if (body.website) return null;                       // the honeypot
  const record = String(body.record ?? "");
  const url = String(body.url ?? "");
  const sent = tabName(body.tab);
  const tab = RENAMED_TABS.get(sent) ?? sent;
  const field = String(body.field ?? "");
  const build = String(body.build ?? "");
  const elapsed = Number(body.elapsed);
  if (!RECORD.test(record) || !PATH.test(url)) return null;
  if (!TABS.has(tab) || !BUILD.test(build)) return null;
  if (!Number.isFinite(elapsed) || elapsed < MIN_ELAPSED_MS) return null;
  // The record and the page must be the same thing.
  const kind = record.slice(0, record.indexOf(":"));
  const ref = record.slice(kind.length + 1);
  // A translation is reported as one, and nothing else is.
  if (kind === "translation" ? field !== TRANSLATION : !FIELDS.has(field)) return null;
  if (kind === "translation") {
    if (url !== ref || tab !== "") return null;
  } else if (kind === "bill") {
    const [yr, id] = ref.split("/");
    if (url !== `/bill/${yr}/${id.toLowerCase()}`) return null;
  } else if (kind === "committee" || kind === "study") {
    if (url !== `/committee/${ref}`) return null;
  } else if (kind === "session") {
    if (url !== `/session/${ref}`) return null;
  } else if (!MEMBER_PAGE.test(url)) {
    return null;                     // and onRequest checks the page is that member's
  }
  const note = cleanNote(body.note);
  if (note.text.length < 3) return null;
  return { record, kind, ref, url, tab, field, build, note: note.text,
           hidden: note.hidden ? 1 : 0 };
}

// A member's address is a slug the sender chose, so it is only accepted if
// the built page at that address is the page of that member.
//
// THE WHOLE PAGE (15 October 2026). This looked for the member's line in the
// first 20,000 characters, and from 12 October a legislator page carried its
// record as plain HTML ahead of that line: on 2,184 of 2,191 pages it stood
// past the 20,000th character (median 28,005), so a report from nearly every
// member's page was dropped while the reader was thanked. The page is read
// whole by text() either way, so the cut bounded nothing but the search;
// preflight sends a report from every built page through this.
export async function memberPageMatches(env, request, url, id) {
  if (!env.ASSETS) return false;
  try {
    const res = await env.ASSETS.fetch(new URL(url, request.url));
    if (!res.ok) return false;
    const html = await res.text();
    return html.includes(`window.GR_MEMBER="${id}"`);
  } catch {
    return false;
  }
}

// A page in another language is only accepted if the built page at that
// address is one, in the language its address names (24 October 2026): the
// address is the sender's to write, as a member's slug is.
export async function translatedPage(env, request, url) {
  if (!env.ASSETS) return false;
  const lang = url.split("/")[1];
  try {
    const res = await env.ASSETS.fetch(new URL(url, request.url));
    if (!res.ok) return false;
    const html = await res.text();
    return html.includes(`<html lang="${lang}"`);
  } catch {
    return false;
  }
}

// Same site only, by name. Comparing the request with itself accepted every
// old deployment address, which Cloudflare keeps serving for good.
//
// It reads the host of whatever address it is given, so onRequest asks it
// twice: once of the Origin header, and once of the address the request was
// actually sent to. One list and one rule for both, so they cannot drift.
export function originAllowed(origin, env) {
  if (!origin) return false;
  let host;
  try { host = new URL(origin).host; } catch { return false; }
  const allowed = String(env.REPORT_ORIGINS || "graniterecord.org www.graniterecord.org")
    .split(/\s+/).filter(Boolean);
  return allowed.some(a => a.startsWith("*.") ? host.endsWith(a.slice(1)) : host === a);
}

async function readCapped(request) {
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks = [];
  let size = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > MAX_BODY) { await reader.cancel(); return null; }
    chunks.push(value);
  }
  const all = new Uint8Array(size);
  let at = 0;
  for (const c of chunks) { all.set(c, at); at += c.byteLength; }
  return new TextDecoder().decode(all);
}

async function digest(s) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0"))
    .join("").slice(0, 32);
}

const NOTHING = () => new Response(null, { status: 204 });
// A report that passed every rule and could not be kept. Not 204, so the box
// shows the reader the email address with their words filled in (app.js).
const NOT_KEPT = () => new Response(null, { status: 503 });
// A report that passed every rule on a day already at its ceiling. Not 204,
// for the same reason: the reader is offered the email address, not thanks.
const FULL_DAY = () => new Response(null, { status: 429 });

export async function onRequest(context) {
  const { request, env } = context;
  if (request.method !== "POST") {
    return new Response("POST only\n", {
      status: 405, headers: { "Allow": "POST", "Content-Type": "text/plain" } });
  }
  let storing = false;             // set once the report has passed every rule
  try {
    // The address the request came to, before anything else is read. The
    // rate rule in front of this path is a rule on the graniterecord.org zone,
    // and it does not see graniterecord.pages.dev or any <hash>.graniterecord
    // .pages.dev address -- which, for a production deployment, runs with the
    // production database bound. An Origin header is one line a script
    // writes, so it cannot be what keeps those addresses out. Added 13
    // September 2026.
    if (!originAllowed(request.url, env)) return NOTHING();
    // And the path it came to, for the same reason. The router hands this
    // function more than /api/report: in wrangler 4.131.1 a route matches
    // with path-to-regexp, not strict and not case-sensitive, and the
    // _routes.json rule it writes allows a trailing slash, so /api/report/
    // reaches it -- and a rate rule written as path eq "/api/report" does not
    // count that request. Case variants are refused too, rather than trusting
    // _routes.json to stop them. The page posts to exactly /api/report
    // (app.js), so no reader is refused by this. Added 13 September 2026.
    if (new URL(request.url).pathname !== "/api/report") return NOTHING();
    if (!originAllowed(request.headers.get("Origin"), env)) return NOTHING();
    if (!(request.headers.get("Content-Type") || "").startsWith("application/json"))
      return NOTHING();
    if (Number(request.headers.get("Content-Length") || 0) > MAX_BODY) return NOTHING();
    const raw = await readCapped(request);
    if (raw === null) return NOTHING();
    let body;
    try { body = JSON.parse(raw); } catch { return NOTHING(); }
    const r = validate(body);
    if (!r) return NOTHING();
    if (r.kind === "member" && !(await memberPageMatches(env, request, r.url, r.ref)))
      return NOTHING();
    if (r.kind === "translation" && !(await translatedPage(env, request, r.url)))
      return NOTHING();
    if (!env.DB) {
      console.log("report not stored: no DB binding on this deployment");
      return NOT_KEPT();
    }
    storing = true;

    // One statement, so simultaneous posts cannot all read "499" and all go in,
    // and so a post reads one row, not the day's.
    const day = new Date().toISOString().slice(0, 10);
    const n = await env.DB.prepare(
      "INSERT INTO report_days (day, n) VALUES (?1, 1) " +
      "ON CONFLICT(day) DO UPDATE SET n = n + 1 WHERE n < ?2 RETURNING n")
      .bind(day, DAILY_CEILING).first("n");
    if (n === null || n === undefined) return FULL_DAY();

    // The day is in the key: the same words tomorrow are a report again, which
    // is what "reported again after being marked fixed" needs to see.
    const dedup = await digest([day, r.record, r.field,
      r.note.toLowerCase().replace(/\s+/g, " ")].join("|"));
    await env.DB.prepare(
      "INSERT OR IGNORE INTO reports " +
      "(at, record, kind, url, tab, field, note, build, hidden, dedup) " +
      "VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)")
      .bind(new Date().toISOString(), r.record, r.kind, r.url, r.tab, r.field,
            r.note, r.build, r.hidden, dedup)
      .run();
  } catch (e) {
    // The message stays in the Function's own log, because an error message is
    // information. The answer depends on where it was thrown: before the
    // report passed every rule it is a malformed post like any other, and 204;
    // at the database it is a real report that was not kept, and 503, so the
    // reader is offered the email address instead of being thanked.
    console.log("report not stored:", e && e.message);
    if (storing) return NOT_KEPT();
  }
  return NOTHING();
}
