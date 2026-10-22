/*
 * The mail: one call to Resend, and the five emails this sends -- the
 * confirmation, the "you are following" a confirmation sends, a new link, the
 * daily and the weekly -- each in plain text and in simple HTML.
 *
 * NO REPLY ADDRESS. Nothing here sets Reply-To, and every email says where to
 * go instead: the report box on a bill's, legislator's or committee's page,
 * or the feedback form. An inbox of replies would hold addresses, which is
 * what the rest of this is built to keep anyone from seeing.
 *
 * EVERY UPDATE CARRIES ITS WAY OUT. A manage link and an unsubscribe link in
 * the body, and the List-Unsubscribe and List-Unsubscribe-Post headers
 * (RFC 8058), which the large mail providers turn into their own one-click
 * button: they POST to the address in the header, which deletes the address
 * and everything it follows at once.
 *
 * NOTHING SAYS "NOW". The site is updated once a day, overnight, and every
 * update says that what it reports is as of then.
 *
 * AN EMAIL LOOKS LIKE THE SITE AND LEADS BACK TO IT. The person, 17 October
 * 2026, reading a daily, a weekly and the welcome email, asked for "a header
 * with the logo with Granite Record horizontal like it is in the site header"
 * and for the bills to have "hyperlinks to their pages on Granite Record". So
 * every email opens with the site's header, and every bill, law, legislator
 * and committee it names is a link to its page (names(), below). The layout is
 * tables and inline styles, which Gmail, Outlook and Apple Mail draw alike.
 */

import { ConfigError } from "./address.js";
import { addDays, esc, oneLine, parseKey, siteUrl } from "./common.js";

const RESEND = "https://api.resend.com/emails";

// One email to one address. Answers { ok, status } and never anything Resend
// said: its error messages name the address they refused, so the body of an
// error is not read at all.
// RESEND'S RATE LIMIT, MET ONCE AND WAITED OUT (22 October 2026). A 429 is
// Resend saying "not this second": the sender and a sign-up's confirmation
// share one team's limit, and a confirmation refused for it was lost while the
// reader was told it was on its way. So a 429 is waited out -- Resend's own
// retry-after, at most RETRY_WAIT_MOST seconds, or one second -- and the same
// request sent once more, under the same Idempotency-Key, so a retry can never
// send twice. A second 429 is the caller's to handle.
export const RETRY_WAIT_MOST = 5;

function retryWait(res) {
  const s = Number(res.headers?.get?.("retry-after"));
  return Math.min(RETRY_WAIT_MOST, Number.isFinite(s) && s > 0 ? s : 1) * 1000;
}

export async function sendMail(env, { to, subject, text, html, headers }, idempotencyKey) {
  const from = String(env.MAIL_FROM || "").trim();
  if (!env.RESEND_API_KEY || !from) throw new ConfigError();
  const ask = () => fetch(RESEND, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    },
    body: JSON.stringify({ from, to: [to], subject, text, html,
                           ...(headers ? { headers } : {}) }),
  });
  let res = await ask();
  if (res.status === 429) {
    try { await res.body?.cancel(); } catch { /* nothing to read */ }
    await new Promise(r => setTimeout(r, retryWait(res)));
    res = await ask();
  }
  try { await res.body?.cancel(); } catch { /* nothing to read */ }
  return { ok: res.ok, status: res.status };
}

// ---- addresses of the private pages -------------------------------------------------
// The token goes after "#": a browser does not send that part to the server,
// so it is in no request address and no log. The one exception is the
// List-Unsubscribe header, which RFC 8058 has the mail provider POST to with a
// fixed body, so its token must be in the address -- and so it is in the
// request log of every request made to that address (wrangler tail, Workers
// Logs). It is the unsubscribe token, good for nothing but deleting the
// address; it opens no page that shows what is followed. A POST of the
// one-click body spends it, by deleting the address; a GET of it (a client
// that opens it in a browser) only shows the button, and the token stays
// current until the reader asks for a new link.
//
// Every email to one reader carries the same two links (address.js linksFor),
// until the reader asks for a new one.
export const manageLink = (origin, t) => `${origin}/api/follow/manage#t=${t}`;
export const unsubscribeLink = (origin, u) => `${origin}/api/follow/unsubscribe#u=${u}`;
export const confirmLink = (origin, t) => `${origin}/api/follow/confirm#t=${t}`;

export function listHeaders(origin, unsub) {
  return {
    "List-Unsubscribe": `<${origin}/api/follow/unsubscribe?u=${unsub}>`,
    "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
  };
}

// ---- words ----------------------------------------------------------------------
const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// A date as every page of the site writes one. The language sweep of 17
// October 2026 found the emails saying "Saturday 17 October 2026" where the
// site says "Saturday, October 17, 2026". These are components.js's dateWords
// in its "full" and "long" forms, and dayDate its "day" form; a Worker cannot
// load that browser script, so tests/follow/mail.test.js loads both and holds
// them to one answer.
export function longDate(day, weekday = false) {
  const [y, m, d] = String(day).split("-").map(Number);
  const s = `${MONTHS[m - 1]} ${d}, ${y}`;
  return weekday ? `${DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]}, ${s}` : s;
}

export function dayDate(day) {
  const [y, m, d] = String(day).split("-").map(Number);
  return `${DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]}, ${MONTHS[m - 1]} ${d}`;
}

export function clockTime(hhmm) {
  if (!/^\d{2}:\d{2}$/.test(hhmm || "")) return "";
  let h = Number(hhmm.slice(0, 2));
  const ap = h < 12 ? "a.m." : "p.m.";
  h = h % 12 || 12;
  return `${h}:${hhmm.slice(3)} ${ap}`;
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const cap = s => String(s).charAt(0).toUpperCase() + String(s).slice(1);

// A list as the site writes one. The language sweep of 17 October 2026 found
// the week ahead running "For HB 1004 and HB 1024 and ...". The site's
// narratives write "HB 1767-FN, HB 303-FN and SB 416", with no comma before
// "and", so this does too; past `most`, the rest are counted.
export function andList(parts, most = 5) {
  const all = parts.length > most
    ? [...parts.slice(0, most - 1), `${parts.length - most + 1} more you follow`] : [...parts];
  return all.length < 2 ? all.join("") : `${all.slice(0, -1).join(", ")} and ${all[all.length - 1]}`;
}

// How current an email is, in a reader's words. This said "up to last night's
// build", which is how the code sees the night and not how a reader does (the
// language sweep, 17 October 2026).
export const UPDATED = "Granite Record is updated once a day, overnight, so this email " +
  "reports what had reached the record by early this morning, not what is happening now.";

// Where to report a mistake, naming only pages that have the button. The
// footer sent every reader to "Report a problem with this page" on "the
// record's page", and a law's or a topic's page has no such button: a bill's,
// a legislator's and a committee's do, as the Learn pages say (the language
// sweep, 17 October 2026).
const NO_REPLY = "This address takes no replies. If something here looks wrong, use " +
  "“Report a problem” on the bill's, legislator's or committee's page";

// ---- the frame of every email --------------------------------------------------------
// The site's palette, light, on a white ground that every block declares
// for itself (17 October 2026). The colours are app.css's ink, ink-2, rule
// and pine. The head declares the email light-only, which Apple Mail and
// Outlook honour by drawing it as written; Gmail's apps and Outlook.com may
// invert it all the same, and because every colour here is dark ink on white
// an inverted email is light ink on dark: no text is light, none sits on an
// image, and no colour is the only thing that says something. mail.test.js
// holds every text colour to 4.5:1 on white.
export const PALETTE = { ink: "#1C2126", ink2: "#4A5259", rule: "#D3D6DA", pine: "#14514C",
                         white: "#FFFFFF" };
const { ink: INK, ink2: INK2, rule: RULE, pine: PINE, white: WHITE } = PALETTE;
const SERIF = "Georgia,'Times New Roman',serif";
const BRAND = "'Source Serif 4',Georgia,'Times New Roman',serif";
const P = "margin:0 0 12px";

// The site's header in an email. The logo mark beside the name, as the site
// header sets them (the person, 17 October 2026). The mark is the PNG the
// site serves, since Gmail shows no SVG, at the site header's proportions;
// its width and height are fixed, so with images blocked its box keeps its
// size and the name beside it, which is text, still reads.
export const MARK = { path: "/mark.png", width: 26, height: 44, alt: "Granite Record logo" };
function masthead(origin) {
  const home = esc(siteUrl(origin, "/"));
  return `<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>` +
    `<td valign="middle" style="padding:0 10px 0 0"><a href="${home}" style="text-decoration:none">` +
    `<img src="${esc(siteUrl(origin, MARK.path))}" width="${MARK.width}" height="${MARK.height}" ` +
    `alt="${esc(MARK.alt)}" style="display:block;border:0;outline:none;width:${MARK.width}px;` +
    `height:${MARK.height}px;font-family:${SERIF};font-size:10px;line-height:12px;color:${INK2}"></a></td>` +
    `<td valign="middle" style="font-family:${BRAND};font-size:22px;line-height:1.1;font-weight:600;` +
    `color:${INK}"><a href="${home}" style="color:${INK};text-decoration:none">Granite Record</a>` +
    `</td></tr></table>`;
}

// One email's HTML: the header, then an optional dateline, then `inner`.
// `preheader` is the line an inbox shows beside the subject, hidden in the
// email itself; without it an inbox would show the header's own words.
function frame(origin, inner, { dateline = "", preheader = "" } = {}) {
  return "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">" +
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">" +
    "<meta name=\"color-scheme\" content=\"light\"><meta name=\"supported-color-schemes\" content=\"light\">" +
    "<title>Granite Record</title></head>" +
    `<body style="margin:0;padding:0;background:${WHITE};color:${INK}" bgcolor="${WHITE}">` +
    (preheader ? `<div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;` +
      `line-height:1px">${esc(oneLine(preheader, 140))}</div>` : "") +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
    `bgcolor="${WHITE}" style="background:${WHITE}"><tr><td align="center" style="padding:0 16px">` +
    // Outlook on Windows reads no max-width: a fixed table for it alone.
    "<!--[if mso]><table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" " +
    "border=\"0\"><tr><td><![endif]-->" +
    `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
    `style="width:100%;max-width:600px">` +
    `<tr><td bgcolor="${WHITE}" style="background:${WHITE};padding:24px 0 14px;border-bottom:1px solid ${RULE}">` +
    masthead(origin) + "</td></tr>" +
    `<tr><td bgcolor="${WHITE}" style="background:${WHITE};padding:20px 0 28px;font-family:${SERIF};` +
    `font-size:16px;line-height:1.5;color:${INK}">` +
    (dateline ? `<p style="margin:0 0 16px;font-size:14px;color:${INK2}">${esc(dateline)}</p>` : "") +
    inner + "</td></tr></table>" +
    "<!--[if mso]></td></tr></table><![endif]-->" +
    "</td></tr></table></body></html>";
}
const a = (href, label) =>
  `<a href="${esc(href)}" style="color:${PINE};text-decoration:underline">${esc(label)}</a>`;

// nightly: whether the email reports anything, and so needs saying how
// current it is. An email that reports nothing (the one a confirmation
// sends) leaves it out rather than say "this email reports".
function footer(origin, feedbackUrl, manage, unsub, gone, nightly = true) {
  const fb = feedbackUrl ? siteOrForm(feedbackUrl) : "";
  const small = `${P};font-size:14px;color:${INK2}`;
  const lines = nightly ? [UPDATED, ""] : [];
  const html = [`<hr style="border:0;border-top:1px solid ${RULE};margin:28px 0 16px">`,
    ...(nightly ? [`<p style="${small}">${esc(UPDATED)}</p>`] : [])];
  if (gone) {
    const s = "That was the last thing you followed, so your address has been deleted " +
      "from our database with it. To follow something again, use Follow on its page.";
    lines.push(s, "");
    html.push(`<p style="${small}">${esc(s)}</p>`);
  } else {
    lines.push("Change what you follow, how often, or pause:",
      manageLink(origin, manage), "",
      "Unsubscribe, deleting your address and everything you follow from our database at once:",
      unsubscribeLink(origin, unsub), "");
    html.push(`<p style="${P};font-size:14px">${a(manageLink(origin, manage),
      "Change what you follow, how often, or pause")}</p>`,
      `<p style="${P};font-size:14px;color:${INK2}">${a(unsubscribeLink(origin, unsub),
        "Unsubscribe")} — deletes your address and everything you follow from our ` +
        `database, at once.</p>`);
  }
  lines.push(NO_REPLY + (fb ? `, or the feedback form: ${fb}` : ".") );
  html.push(`<p style="${small}">${esc(NO_REPLY)}` +
    (fb ? `, or ${a(fb, "the feedback form")}.` : ".") + "</p>");
  return { text: lines.join("\n"), html: html.join("") };
}

// The feedback form is a configured address; it is used only if it is a
// plain https address.
function siteOrForm(u) {
  try { const x = new URL(u); return x.protocol === "https:" ? x.href : ""; } catch { return ""; }
}

// ---- every name a link to its page --------------------------------------------------
// The names an email can link, by what the site calls them: current.json's
// label for every bill still moving, every legislator, committee, law and
// topic, with the short forms a line of the record uses beside it -- a bill
// without its "-FN", a committee without its "Committee", a law as "RSA 91-A".
// The sender reads current.json once a run and hands this to every email.
const SUFFIX = /(?:-[A-Z]{1,3})+$/;
export function pageNames(current) {
  const out = new Map();
  for (const [key, m] of current?.followable || []) {
    const k = parseKey(key);
    if (k && m?.url) addName(out, k.kind, k.ref, m.label, m.url);
  }
  return out;
}
function addName(map, kind, ref, label, url) {
  const put = n => { if (n && url && !map.has(n)) map.set(n, url); };
  put(label);
  if (kind === "bill") put(String(label).replace(SUFFIX, ""));
  if (kind === "committee") put(String(label).replace(/\s+Committee$/, ""));
  if (kind === "law" && ref) put(`RSA ${ref}`);
}

// The names one email knows besides: each followed record by its label, and
// each item's bill by the page the item carries -- so a bill that has since
// concluded, and is no longer in current.json, still links where it is named.
function namesIn(base, sections) {
  const own = new Map();
  for (const s of sections) {
    if (s.url) addName(own, s.kind, s.ref, s.label, s.url);
    for (const it of [...(s.items || []), ...(s.votes || [])]) {
      if (!/^\/bill\//.test(it.url || "")) continue;
      const lead = /^(.+?) — /.exec(said(it) || "");
      if (lead) addName(own, "bill", "", lead[1], it.url);
      if (it.vote?.bill) addName(own, "bill", "", it.vote.bill, it.url);
    }
  }
  return n => own.get(n) ?? (base ? base.get(n) : undefined);
}

// A bill or a law named in a line of text, wherever it stands in it.
const NAMED = /\b(?:(?:HB|SB|HR|SR|HCR|SCR|HJR|SJR|CACR|HA|HCO|HBI|PET|SSHB|SSSB|SSHR|SSHCR) \d{1,4}(?:-[A-Z]{1,3})*|RSA \d{1,3}(?:-[A-Z]{1,2})?)(?![\w-])/g;

// A line of plain text as HTML, escaped, with every bill and law it names
// that the email can find a page for made a link to that page -- and the
// name a line opens with, "House Example Committee — ...", as a whole.
function linkNames(origin, text, find) {
  const t = String(text ?? "");
  const lead = /^(.+?) — /.exec(t);
  if (lead && !lead[1].match(NAMED) && find(lead[1]))
    return a(siteUrl(origin, find(lead[1])), lead[1]) + linkNames(origin, t.slice(lead[1].length), find);
  let out = "", at = 0;
  for (const m of t.matchAll(NAMED)) {
    const url = find(m[0]) || find(m[0].replace(SUFFIX, ""));
    if (!url) continue;
    out += esc(t.slice(at, m.index)) + a(siteUrl(origin, url), m[0]);
    at = m.index + m[0].length;
  }
  return out + esc(t.slice(at));
}

// A whole name -- a committee, a legislator -- as a link where the email
// knows its page, and as the names in it otherwise.
function linkWhole(origin, name, find) {
  const url = find(name) || find(String(name).replace(/\s+Committee$/, ""));
  return url ? a(siteUrl(origin, url), name) : linkNames(origin, name, find);
}

// ---- the confirmation ------------------------------------------------------------------
export function confirmationEmail({ origin, label, title, token }) {
  const what = oneLine(label, 120) + (title ? ` — ${oneLine(title, 160)}` : "");
  const link = confirmLink(origin, token);
  const subject = oneLine(`Confirm: email updates on ${oneLine(label, 80)}`, 120);
  const text = [
    "Someone asked graniterecord.org to send this address email updates on:",
    "", `  ${what}`, "",
    "Nothing is sent unless you confirm. To confirm, open this link and press Confirm:",
    "", link, "",
    "If it was not you, ignore this email. The request, and this address with it, " +
    "is deleted within 48 hours without being used.", "",
    "Granite Record is a public record of the New Hampshire General Court. " +
    "This address takes no replies.",
  ].join("\n");
  const html = frame(origin,
    `<p style="${P}">Someone asked graniterecord.org to send this address email updates on:</p>` +
    `<p style="${P};padding-left:12px;border-left:3px solid ${RULE}">${esc(what)}</p>` +
    `<p style="${P}">Nothing is sent unless you confirm.</p>` +
    `<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0">` +
    `<tr><td bgcolor="${PINE}" style="background:${PINE};border-radius:4px">` +
    `<a href="${esc(link)}" style="display:inline-block;padding:10px 18px;font-family:${SERIF};` +
    `font-size:16px;color:${WHITE};text-decoration:none;border-radius:4px">Confirm</a></td></tr></table>` +
    `<p style="${P};font-size:14px;color:${INK2}">If it was not you, ignore this email. The ` +
    `request, and this address with it, is deleted within 48 hours without being used.</p>` +
    `<p style="${P};font-size:14px;color:${INK2}">Granite Record is a public record of the ` +
    `New Hampshire General Court. This address takes no replies.</p>`,
    { preheader: "Nothing is sent unless you confirm." });
  return { subject, text, html };
}

// ---- you are following ------------------------------------------------------------------
// THE EMAIL A CONFIRMATION SENDS (the person's test of 16 October 2026: once
// the confirmation link was spent, "I don't have a way to get back to the
// manage page yet without another email update or signing myself up to
// follow another subject"). The manage link is the one at the foot of every
// email, and until the first update no email carried it. So a confirmation
// that adds a record sends this, at once: what is now followed, how often it
// comes, and the manage and unsubscribe links every other email carries, with
// the one-click headers.
//
// What a record is called in a sentence: a bill, a law or a legislator by its
// label; a committee, whose label is "House Education Committee", with "the";
// a topic as a topic, since "Housing" alone could be anything.
export function followName(kind, label) {
  const l = oneLine(label, 120);
  if (kind === "committee") return /^(House|Senate|Joint)\b/.test(l) ? `the ${l}` : l;
  if (kind === "topic") return `the topic ${l}`;
  return l;
}

// How often, in the manage page's words for it (manage.js, "How often").
const OFTEN = {
  daily: ["Updates come daily", "about 8:00 a.m. New Hampshire time, and only on days when something is new"],
  weekly: ["Updates come weekly", "on Saturday about 8:00 a.m., with the week ahead and then the week's news"],
};

// kind, label, title and url: the record, as current.json has it. total: how
// many records the address follows now, this one included. kept: the reader
// was subscribed already and the sign-up box asked for the other frequency
// (confirm.js), so theirs stands. pausedUntil: the subscriber's own, "" for
// none. newcomer: this confirmation made the subscriber. Only a newcomer is
// told to keep the email "until your first update arrives": a reader who
// subscribed weeks ago has had updates, each with the link, and that
// sentence would be wrong for them.
//
// HOW MANY, IN A READER'S WORDS (the language sweep, 17 October 2026): "You
// follow 2 records" was the database's noun. A reader follows bills, laws,
// legislators, committees and topics, and "things" covers them all.
export function welcomeEmail({ origin, kind, label, title, url, frequency, kept = false,
                               pausedUntil = "", total = 1, newcomer = true, manage, unsub,
                               feedbackUrl }) {
  const subject = oneLine(`You're following ${followName(kind, label)}`, 150);
  const what = oneLine(label, 120) + (title ? ` — ${oneLine(title, 160)}` : "");
  const page = url ? siteUrl(origin, url) : "";
  const [often, when] = OFTEN[frequency === "weekly" ? "weekly" : "daily"];
  const how = `${often}${kept ? ", as before" : ""}: ${when}.` +
    (kept ? " Signing up again does not change how often." : "");
  const paused = !pausedUntil ? "" : pausedUntil === "9999-12-31"
    ? "Your updates are paused until you turn them back on."
    : `Your updates are paused through ${longDate(pausedUntil)}.`;
  const count = total > 1 ? `You now follow ${plural(total, "thing", "things")} in all.` : "";
  const keep = newcomer
    ? "Keep this email until your first update arrives: the link below opens your " +
      "page for email updates, where you can change what you follow and how often, and " +
      "every update carries the same link."
    : "The link below opens your page for email updates, where you can change what you " +
      "follow and how often. Every update carries the same link.";
  const f = footer(origin, feedbackUrl, manage, unsub, false, false);
  const text = ["You are now following:", "", `  ${what}`, ...(page ? [`  ${page}`] : []), "",
    ...(count ? [count, ""] : []), how, ...(paused ? ["", paused] : []), "", keep, "",
    "----", f.text].join("\n");
  const html = frame(origin,
    `<p style="${P}">You are now following:</p>` +
    `<p style="${P};padding-left:12px;border-left:3px solid ${RULE}">` +
    (page ? a(page, oneLine(label, 120)) : esc(oneLine(label, 120))) +
    (title ? ` — ${esc(oneLine(title, 160))}` : "") + "</p>" +
    (count ? `<p style="${P}">${esc(count)}</p>` : "") +
    `<p style="${P}">${esc(how)}</p>` +
    (paused ? `<p style="${P}">${esc(paused)}</p>` : "") +
    `<p style="${P}">${esc(keep)}</p>` + f.html, { preheader: how });
  return { subject, text, html, headers: listHeaders(origin, unsub) };
}

// ---- a new link -----------------------------------------------------------------------
export function newLinkEmail({ origin, manage, unsub, feedbackUrl }) {
  const subject = "Your new link for Granite Record email updates";
  const head = "You asked for a new private link. Every link in earlier emails from " +
    "Granite Record has stopped working, their unsubscribe links included.";
  const f = footer(origin, feedbackUrl, manage, unsub, false, false);
  return {
    subject,
    text: [head, "", "Your new link, to change what you follow or how often:",
      manageLink(origin, manage), "", "----", f.text].join("\n"),
    html: frame(origin, `<p style="${P}">${esc(head)}</p>` +
      `<p style="${P}">${a(manageLink(origin, manage), "Your new link")}, to change what ` +
      `you follow or how often.</p>` + f.html, { preheader: head }),
    headers: listHeaders(origin, unsub),
  };
}

// ---- the daily and the weekly ------------------------------------------------------------
// sections: what sender.collect returns, one per followed record with
// something to say. Every value in them came from the changes file and is
// escaped here.
//
// THE INTERIM STUDY REPORT, SAID ONE WAY (the language sweep, 17 October
// 2026). One email said it three ways: a fixed sentence, the clerk's line
// after it, and the sentence again at a glance and in the subject, where
// neither named the bill. It is now plain_action.py's words for the same
// report, which every other line of an email already uses, with the bill's
// name in front wherever it stands alone.
const STUDY = {
  true: "Interim study report: recommends future legislation",
  false: "Interim study report: does not recommend future legislation",
  null: "Interim study report: makes no recommendation",
};
export const studyWords = study => STUDY[String(study?.recommends ?? null)] || STUDY.null;

// What ending a follow means, said to the reader. It said "a record that
// has finished has nothing more to report" (the language sweep, 17 October
// 2026: "record" is the database's word).
const ENDED_TAIL = "There will be no more updates on it, so it has been taken off what you " +
  "follow. Its full history stays on its page.";

function weekLine(w) {
  if (!w) return "";
  if (!w.votes && !w.exec) return "No roll call votes or executive sessions this week.";
  const parts = [];
  if (w.votes) parts.push(plural(w.votes, "roll call vote", "roll call votes"));
  if (w.exec) parts.push(plural(w.exec, "executive session", "executive sessions"));
  return `This week: ${parts.join(" and ")}.`;
}

// THE ORDER A DIGEST IS IN (the design the person approved, 11 October
// 2026): what matters most at a glance, then -- in the weekly -- the week
// ahead, then each kind of record under its own heading.
// AN ITEM IN PLAIN WORDS (the person's choice of 14 October 2026): the
// build's plain sentence where it has one (CHANGES_FORMAT.md, "plain"), the
// clerk's line where it does not. A newly recorded old event says so, and a
// meeting still to come says it is scheduled, so neither reads as the
// morning's news.
const LATE_DAYS = 14;        // older than this when first seen: "Newly recorded"
const LATE_SHOWN = 3;        // newly recorded entries listed a record, the rest counted
const said = it => it.plain || it.summary;
export const late = it => !!it.seen && it.date < addDays(String(it.seen).slice(0, 10), -LATE_DAYS);
// beside: whether the entry's own date is printed beside these words, as it
// is in a record's list and is not in the subject or "at a glance".
function itemWords(it, date, beside = true) {
  if (it.meeting) {
    const w = meetingLine(it, beside);
    return late(it) ? `Newly recorded: ${w}` : w;
  }
  if (it.date > date) return `Scheduled: ${said(it)}`;
  const w = dateOnce(said(it), it.date);
  return late(it) ? `Newly recorded: ${w}` : w;
}

// A MEETING SET, IN PLAIN WORDS (the person, 17 October 2026: "emails can use
// plain words for hearing entries"). An entry printed the clerk's "Public
// Hearing: 10/14/2026 10:00 am LOB 305" under October 6, the day the notice
// was posted, and a reader had to work out which date was the hearing's. The
// build hands over what the line says (plain_action.meeting, the room in
// place()'s words) and this says it with the email's own dates: "Hearing set
// for Wednesday, October 14, 10:00 a.m., Legislative Office Building 305". A
// meeting the clerk marked rescheduled, recessed, cancelled or moved says so
// in the same way. The meeting's day is said once, as every entry's is: where
// it is the entry's own date, printed beside, the hour says when; the
// subject and "at a glance" have no date beside them, so they always say it.
const SET = {
  "": (k, when) => `${k} set for ${when}`,
  rescheduled: (k, when) => `${k} rescheduled for ${when}`,
  "time changed": (k, when) => `${k} moved to ${when}`,
  "room changed": (k, when) => `${k} moved to ${when}`,
  cancelled: (k, when) => `${k} cancelled: it was set for ${when}`,
  recessed: (k, when) => `${k} recessed: it was set for ${when}`,
};
export function meetingWords(m, day = "") {
  const kind = cap(String(m.what).replace(/^public hearing\b/, "hearing"));
  const time = clockTime(m.time);
  const when = [m.date === day && time ? "" : dayDate(m.date), time, m.venue].filter(Boolean).join(", ");
  return (SET[m.state || ""] || SET[""])(kind, when);
}
// The name the line opens with, "HB 9903-FN — ", stays in front of the words.
function meetingLine(it, beside) {
  const lead = /^(.+?) — /.exec(said(it) || "");
  return (lead ? `${lead[1]} — ` : "") + meetingWords(it.meeting, beside ? it.date : "");
}

// A DAY SAID ONCE (the language sweep, 17 October 2026). Every entry is
// shown after its date, and a line of the record that repeats it --
// "Executive Session: 10/06/2026 1:00 pm LOB 305", or a committee's "House
// Example Committee — October 5, 2026" -- printed the day twice, once in the
// clerk's numbers. The repeat comes out where it is that same day; a meeting
// scheduled for another day keeps its date, which is the news.
export function dateOnce(words, day) {
  const [y, m, d] = String(day).split("-");
  const forms = [`${m}/${d}/${y}`, `${MONTHS[Number(m) - 1]} ${Number(d)}, ${y}`,
                 `${Number(d)} ${MONTHS[Number(m) - 1]} ${y}`];
  let w = String(words ?? "");
  for (const f of forms) {
    const q = f.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&");
    w = w.replace(new RegExp(`\\s+[\\u2014\\u2013-]\\s+${q}$`), "")
      .replace(new RegExp(`(:\\s*)${q},?\\s*`), "$1");
  }
  return w.trim();
}

// EACH ITEM ONCE AN EMAIL, under the most particular record it is followed
// by: a bill's executive session is news on the bill, and was printed again
// under the law it amends and the topic it is filed under. GROUPS' order is
// that order.
export function onceEach(sections) {
  const seen = new Set(), out = [];
  for (const [kind] of GROUPS) {
    for (const s of sections.filter(x => x.kind === kind)) {
      const items = s.items.filter(it => !seen.has(it.guid));
      for (const it of s.items) seen.add(it.guid);
      const dropped = s.items.length - items.length;
      if (!items.length && dropped && !(s.votes || []).length && !s.study && !s.ended &&
          !(s.upcoming || []).length && !s.more) continue;
      out.push(dropped ? { ...s, items } : s);
    }
  }
  return out;
}

// PLAIN HEADINGS (the person, 17 October 2026: "This header is phrased a bit
// confusing: 'Bills: the week that was'"). Each kind of record under what it
// is, and the weekly's meetings still to come under "Coming up".
const GROUPS = [["bill", "Bills you follow"], ["law", "Laws you follow"],
                ["member", "Legislators you follow"], ["committee", "Committees you follow"],
                ["topic", "Topics you follow"]];
const AHEAD = "Coming up";

// What most deserves the subject line and the "at a glance" list, best first:
// how a record ended, then a roll call, a study's report, a meeting
// scheduled, an executive session, a committee report, any other milestone.
const RANK = { vote: 1, study: 2, scheduled: 3, exec: 4, report: 5 };
export function headlines(sections, date = "", skipAhead = false) {
  const out = [];
  for (const s of sections) {
    if (s.ended && !s.ended.fallback && s.ended.summary) out.push([0, s.ended.summary]);
    if (s.study) out.push([2, `${s.label} — ${studyWords(s.study)}`]);
    for (const it of s.items) {
      if (!it.milestone || late(it)) continue;
      // What is still to come is the week ahead's in a weekly that has one.
      if (date && it.date > date && skipAhead) continue;
      out.push([RANK[it.kind] || 6, date || it.meeting ? itemWords(it, date, false) : said(it)]);
    }
  }
  const seen = new Set();
  return out.sort((a, b) => a[0] - b[0])
    .map(([, t]) => oneLine(t, 140).replace(/\.$/, ""))
    .filter(t => !seen.has(t) && seen.add(t));
}

// The week ahead, from every section's upcoming: one row a meeting, with
// every followed record it concerns.
function weekAhead(sections) {
  const rows = new Map();
  for (const s of sections) {
    for (const u of s.upcoming || []) {
      const k = [u.date, u.time, u.what, u.committee, u.venue].join("|");
      if (!rows.has(k)) rows.set(k, { ...u, labels: [], urls: [] });
      const r = rows.get(k);
      if (!r.labels.includes(s.label)) { r.labels.push(s.label); r.urls.push(s.url); }
    }
  }
  return [...rows.values()].sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
}

// A BALLOT IN THE SITE'S WORDS (the language sweep, 17 October 2026: an
// email read "On OTPA: voted Not Voting/Excused"). A yes or a no is "voted
// yes"; the codes that are neither take app.js's names for them (its OTHER
// table), since a member who was not there did not "vote" anything. The build
// sends the contract's short words (CHANGES_FORMAT.md, "vote"); the roll
// call's own codes, which a build before this sent cut to twenty characters,
// are read as well.
//
// ONLY A YES OR A NO IS "VOTED" ANYTHING (the review of 17 October 2026). A
// code this does not know was printed after "voted", so the older terms'
// "No vote recorded" (567 ballots) read "voted no vote recorded". It has its
// own words now, and any other code is told as what the record calls it.
const BALLOT = { yes: "voted yes", yea: "voted yes", no: "voted no", nay: "voted no",
  excused: "excused absence", "not voting/excused": "excused absence",
  "not voting": "absent, not excused", "not voting/not excused": "absent, not excused",
  presiding: "presiding", "no vote recorded": "no vote recorded" };
export function ballotWords(ballot) {
  const said = oneLine(ballot ?? "", 40);
  const b = said.toLowerCase();
  const k = b.startsWith("not voting/not") ? "not voting/not excused"
    : b.startsWith("not voting/exc") ? "not voting/excused" : b;
  return BALLOT[k] || (said ? `recorded as “${said}”` : "no vote recorded");
}
// One ballot beside its roll call: "voted yes; the motion passed, 201-163".
function ballotLine(v) {
  const out = v.result ? `; the motion ${v.result}${v.tally ? `, ${v.tally}` : ""}`
    : (v.tally ? `; ${v.tally}` : "");
  return `${ballotWords(v.ballot)}${out}`;
}

// names: pageNames(current), the sender's once a run; without it an email
// links what its own sections name.
export function digestEmail({ origin, frequency, date, sections: given, manage, unsub,
                              feedbackUrl, gone = false, names = null }) {
  const weekly = frequency === "weekly";
  const sections = onceEach(given);
  const find = namesIn(names, sections);
  const link = t => linkNames(origin, t, find);
  const count = sections.reduce((n, s) => n + s.items.length + (s.votes || []).length + s.more +
    (s.study ? 1 : 0) + (s.ended ? 1 : 0), 0);
  const ahead = weekly ? weekAhead(sections) : [];
  const tops = headlines(sections, date, ahead.length > 0);
  const more = n => n > 0 ? `, and ${plural(n, "more update", "more updates")}` : "";
  // "Proceedings" was the code's word for them (the language sweep, 17
  // October 2026); every one in the week ahead is a committee's meeting.
  const subject = oneLine(weekly
    ? (ahead.length
        ? `Your week: ${plural(ahead.length, "committee meeting", "committee meetings")} coming up` +
          (tops.length ? `, and ${tops[0]}` : "")
        : tops.length ? `Your week: ${tops[0]}${more(count - 1)}`
          : `Your week to ${longDate(date, true)}`)
    : tops.length ? `${tops[0]}${more(count - 1)}`
      : `${plural(count, "update", "updates")} on what you follow`, 150);
  // NO OPENING SENTENCE, ONLY THE DAY (the person, 17 October 2026: "This
  // sentence is unnecessary: 'What changed on the record you follow, as of
  // last night's build.'"). The footer says how current the email is.
  const dateline = `${weekly ? "Weekly" : "Daily"} update — ${longDate(date, true)}`;
  const text = [dateline, ""];
  let html = "";

  // AT A GLANCE: where there is enough to need it.
  const glance = tops.slice(0, 3);
  if (glance.length && (count >= 4 || sections.length >= 3)) {
    text.push("At a glance:", ...glance.map(g => `  * ${g}`), "");
    html += `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
      `style="border:1px solid ${RULE};border-radius:4px;margin:0 0 8px"><tr><td bgcolor="${WHITE}" ` +
      `style="background:${WHITE};padding:12px 14px"><p style="margin:0 0 6px;font-weight:600">At a glance</p>` +
      `<ul style="margin:0;padding-left:18px">` +
      glance.map(g => `<li style="margin:0 0 4px">${link(g)}</li>`).join("") + "</ul></td></tr></table>";
  }

  const heading = h => {
    text.push(h.toUpperCase(), "");
    html += `<h2 style="margin:28px 0 6px;padding-top:16px;border-top:1px solid ${RULE};` +
      `font-family:${BRAND};font-size:20px;line-height:1.25;font-weight:600;color:${INK}">${esc(h)}</h2>`;
  };
  const same = (x, y) => String(x).replace(/\s+Committee$/, "") === String(y).replace(/\s+Committee$/, "");

  if (ahead.length) {
    heading(AHEAD);
    html += `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">`;
    for (const r of ahead) {
      const when = [dayDate(r.date), clockTime(r.time)].filter(Boolean).join(", ");
      const what = cap(r.what);
      // The committee that will sit is named once, where it sits, and not
      // again among what the reader follows that the meeting concerns.
      const others = r.labels.map((l, i) => [l, r.urls[i]]).filter(([l]) => !(r.committee && same(l, r.committee)));
      text.push(`  ${when}: ${what}${r.committee ? `, ${r.committee}` : ""}${r.venue ? `, ${r.venue}` : ""}.` +
        (others.length ? ` For ${andList(others.map(([l]) => l))}.` : ""));
      html += `<tr><td style="padding:8px 0;border-bottom:1px solid ${RULE};font-size:15px">` +
        `<span style="color:${INK2}">${esc(when)}</span><br><b>${esc(what)}</b>` +
        (r.committee ? `, ${linkWhole(origin, r.committee, find)}` : "") +
        (r.venue ? `, ${esc(r.venue)}` : "") +
        (others.length ? `<br><span style="font-size:14px;color:${INK2}">For ` +
          andList(others.map(([l, u]) => u ? a(siteUrl(origin, u), l) : linkWhole(origin, l, find))) +
          "</span>" : "") + "</td></tr>";
    }
    html += "</table>";
    text.push("");
  }

  for (const [kind, name] of GROUPS) {
    const mine = sections.filter(s => s.kind === kind);
    if (!mine.length) continue;
    if (weekly && ahead.length && !mine.some(s => s.items.length || (s.votes || []).length ||
        s.study || s.ended || s.week)) continue;
    heading(name);
    for (const s of mine) {
      const url = siteUrl(origin, s.url);
      text.push(s.title ? `${s.label} — ${s.title}` : s.label, url);
      html += `<h3 style="margin:18px 0 2px;font-size:17px;line-height:1.3;font-weight:600">` +
        `${a(url, s.label)}</h3>`;
      if (s.title) html += `<p style="margin:0 0 6px;color:${INK2};font-size:14px">${esc(s.title)}</p>`;
      if (s.now) {
        text.push(`  Now: ${s.now}`);
        html += `<p style="margin:0 0 6px;font-size:14px">Now: ${esc(s.now)}</p>`;
      }
      if ((s.votes || []).length) {
        text.push(`  Roll calls (${s.votes.length}):`);
        html += `<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" ` +
          `style="font-size:14px;margin:0 0 10px">`;
        for (const it of s.votes) {
          const v = it.vote;
          const on = v.motion ? `On ${v.motion}: ` : "";
          text.push(`  ${longDate(it.date)}  ${v.bill || ""}${v.title ? ` (${oneLine(v.title, 90)})` : ""}` +
            ` — ${on}${ballotLine(v)}`);
          html += `<tr><td style="padding:6px 0;border-bottom:1px solid ${RULE}">` +
            `<span style="color:${INK2}">${esc(longDate(it.date))}</span> — ` +
            (v.bill ? (it.url ? a(siteUrl(origin, it.url), v.bill) : link(v.bill)) : "") +
            (v.title ? ` <span style="color:${INK2}">${esc(oneLine(v.title, 140))}</span>` : "") +
            `<br>${esc(on)}<b>${esc(ballotLine(v))}</b></td></tr>`;
        }
        html += "</table>";
      }
      // What is still to come is the week ahead's, in the weekly; and of
      // the old events newly recorded, the first few, the rest counted. The
      // study's report leads, with its date, as any milestone would.
      const fresh = s.items.filter(it => !late(it) && !(weekly && ahead.length && it.date > date));
      const old = s.items.filter(it => late(it));
      const shown = [...fresh, ...old.slice(0, LATE_SHOWN)]
        .map(it => ({ date: it.date, words: itemWords(it, date), bold: it.milestone && !late(it) }));
      if (s.study) shown.unshift({ date: s.study.date || date, bold: true,
                                   words: `${s.label} — ${studyWords(s.study)}` });
      const earlier = old.length - Math.min(old.length, LATE_SHOWN);
      if (shown.length) {
        html += `<ul style="margin:0 0 10px;padding-left:20px">`;
        for (const row of shown) {
          text.push(`  ${longDate(row.date)}  ${row.words}`);
          const line = link(row.words);
          html += `<li style="margin:0 0 6px"><span style="color:${INK2}">${esc(longDate(row.date))}</span>` +
            ` — ${row.bold ? `<b>${line}</b>` : line}</li>`;
        }
        html += "</ul>";
      }
      const lines = [s.more ? `…and ${s.more} more on its page.` : "",
        earlier ? `…and ${plural(earlier, "earlier entry", "earlier entries")} newly on the record, on its page.` : "",
        weekLine(s.week)].filter(Boolean);
      for (const l of lines) {
        text.push(`  ${l}`);
        html += `<p style="margin:0 0 8px">${esc(l)}</p>`;
      }
      if (!ahead.length) {
        for (const u of s.upcoming || []) {
          const where = [u.committee, u.venue].filter(Boolean);
          const when = [longDate(u.date, true), clockTime(u.time)].filter(Boolean).join(", ");
          text.push(`  Coming up: ${when}: ${cap(u.what)}${where.length ? `, ${where.join(", ")}` : ""}.`);
          html += `<p style="margin:0 0 8px">Coming up: ${esc(when)}: ${esc(cap(u.what))}` +
            (u.committee ? `, ${linkWhole(origin, u.committee, find)}` : "") +
            (u.venue ? `, ${esc(u.venue)}` : "") + ".</p>";
        }
      }
      if (s.ended) {
        const how = s.ended.summary || `${s.label} has concluded.`;
        text.push(`  ${how} ${ENDED_TAIL}`);
        html += `<p style="margin:0 0 8px"><b>${link(how)}</b> ${esc(ENDED_TAIL)}</p>`;
      }
      text.push("");
    }
  }
  const f = footer(origin, feedbackUrl, manage, unsub, gone);
  text.push("----", f.text);
  return {
    subject,
    text: text.join("\n"),
    html: frame(origin, html + f.html, { dateline, preheader: glance.slice(1).join("; ") || dateline }),
    headers: gone ? undefined : listHeaders(origin, unsub),
  };
}
