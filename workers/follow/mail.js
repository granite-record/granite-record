/*
 * The mail: one call to Resend, and the four emails this sends -- the
 * confirmation, a new link, the daily and the weekly -- each in plain text
 * and in simple HTML.
 *
 * NO REPLY ADDRESS. Nothing here sets Reply-To, and every email says where to
 * go instead: the report box on the record's page, or the feedback form. An
 * inbox of replies would hold addresses, which is what the rest of this is
 * built to keep anyone from seeing.
 *
 * EVERY UPDATE CARRIES ITS WAY OUT. A manage link and an unsubscribe link in
 * the body, and the List-Unsubscribe and List-Unsubscribe-Post headers
 * (RFC 8058), which the large mail providers turn into their own one-click
 * button: they POST to the address in the header, which deletes the address
 * and everything it follows at once.
 *
 * NOTHING SAYS "NOW". The record is rebuilt once a night, and every update
 * says that what it reports is as of last night's build.
 */

import { ConfigError } from "./address.js";
import { esc, oneLine, siteUrl } from "./common.js";

const RESEND = "https://api.resend.com/emails";

// One email to one address. Answers { ok, status } and never anything Resend
// said: its error messages name the address they refused, so the body of an
// error is not read at all.
export async function sendMail(env, { to, subject, text, html, headers }, idempotencyKey) {
  const from = String(env.MAIL_FROM || "").trim();
  if (!env.RESEND_API_KEY || !from) throw new ConfigError();
  const res = await fetch(RESEND, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
      ...(idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {}),
    },
    body: JSON.stringify({ from, to: [to], subject, text, html,
                           ...(headers ? { headers } : {}) }),
  });
  try { await res.body?.cancel(); } catch { /* nothing to read */ }
  return { ok: res.ok, status: res.status };
}

// ---- addresses of the private pages -------------------------------------------------
// The token goes after "#": a browser does not send that part to the server,
// so it is in no request address and no log. The one exception is the
// List-Unsubscribe header, which RFC 8058 has the mail provider POST to with a
// fixed body, so its token must be in the address; it is an unsubscribe token,
// good for nothing but deleting, and spent by the request that carries it.
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

export function longDate(day, weekday = false) {
  const [y, m, d] = day.split("-").map(Number);
  const s = `${d} ${MONTHS[m - 1]} ${y}`;
  return weekday ? `${DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]} ${s}` : s;
}

export function clockTime(hhmm) {
  if (!/^\d{2}:\d{2}$/.test(hhmm || "")) return "";
  let h = Number(hhmm.slice(0, 2));
  const ap = h < 12 ? "a.m." : "p.m.";
  h = h % 12 || 12;
  return `${h}:${hhmm.slice(3)} ${ap}`;
}

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

const NIGHTLY = "The record is rebuilt once a night, so this reports what changed " +
  "up to last night's build, not what is happening now.";
const NO_REPLY = "This address takes no replies. If something here is wrong, use " +
  "“Report a problem with this page” on the record's page";

// ---- the frame of every email --------------------------------------------------------
const P = "margin:0 0 12px";
function frame(inner) {
  return "<!doctype html><html><head><meta charset=\"utf-8\">" +
    "<meta name=\"viewport\" content=\"width=device-width\"></head>" +
    "<body style=\"margin:0;padding:0;background:#ffffff\">" +
    "<div style=\"max-width:600px;margin:0 auto;padding:24px 16px;font-family:Georgia," +
    "'Times New Roman',serif;font-size:16px;color:#1a1a1a;line-height:1.5\">" +
    "<p style=\"margin:0 0 20px;font-size:13px;letter-spacing:.06em;" +
    "text-transform:uppercase;color:#555\">Granite Record</p>" +
    inner + "</div></body></html>";
}
const a = (href, label) => `<a href="${esc(href)}" style="color:#1d4e89">${esc(label)}</a>`;

function footer(origin, feedbackUrl, manage, unsub, gone) {
  const fb = feedbackUrl ? siteOrForm(feedbackUrl) : "";
  const lines = [NIGHTLY, ""];
  const html = [`<hr style="border:0;border-top:1px solid #ddd;margin:28px 0 16px">`,
    `<p style="${P};font-size:14px;color:#444">${esc(NIGHTLY)}</p>`];
  if (gone) {
    const s = "That was the last thing you followed, so your address has been deleted " +
      "with it. To follow something again, use Follow on its page.";
    lines.push(s, "");
    html.push(`<p style="${P};font-size:14px;color:#444">${esc(s)}</p>`);
  } else {
    lines.push("Change what you follow, or whether it comes daily or weekly:",
      manageLink(origin, manage), "",
      "Unsubscribe, deleting your address and everything you follow at once:",
      unsubscribeLink(origin, unsub), "");
    html.push(`<p style="${P};font-size:14px">${a(manageLink(origin, manage),
      "Change what you follow, or daily or weekly")}</p>`,
      `<p style="${P};font-size:14px">${a(unsubscribeLink(origin, unsub),
        "Unsubscribe")} — deletes your address and everything you follow, at once.</p>`);
  }
  lines.push(NO_REPLY + (fb ? `, or the feedback form: ${fb}` : ".") );
  html.push(`<p style="${P};font-size:13px;color:#555">${esc(NO_REPLY)}` +
    (fb ? `, or ${a(fb, "the feedback form")}.` : ".") + "</p>");
  return { text: lines.join("\n"), html: html.join("") };
}

// The feedback form is a configured address; it is used only if it is a
// plain https address.
function siteOrForm(u) {
  try { const x = new URL(u); return x.protocol === "https:" ? x.href : ""; } catch { return ""; }
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
  const html = frame(
    `<p style="${P}">Someone asked graniterecord.org to send this address email updates on:</p>` +
    `<p style="${P};padding-left:12px;border-left:3px solid #ccc">${esc(what)}</p>` +
    `<p style="${P}">Nothing is sent unless you confirm.</p>` +
    `<p style="margin:20px 0"><a href="${esc(link)}" style="display:inline-block;padding:10px 18px;` +
    `background:#1d4e89;color:#ffffff;text-decoration:none;border-radius:4px">Confirm</a></p>` +
    `<p style="${P};font-size:14px;color:#444">If it was not you, ignore this email. The ` +
    `request, and this address with it, is deleted within 48 hours without being used.</p>` +
    `<p style="${P};font-size:13px;color:#555">Granite Record is a public record of the ` +
    `New Hampshire General Court. This address takes no replies.</p>`);
  return { subject, text, html };
}

// ---- a new link -----------------------------------------------------------------------
export function newLinkEmail({ origin, manage, unsub, feedbackUrl }) {
  const subject = "Your new link for Granite Record email updates";
  const head = "You asked for a new private link. Every link in earlier emails from " +
    "Granite Record has stopped working, their unsubscribe links included.";
  const f = footer(origin, feedbackUrl, manage, unsub, false);
  return {
    subject,
    text: [head, "", "Your new link, to change what you follow or how often:",
      manageLink(origin, manage), "", "----", f.text].join("\n"),
    html: frame(`<p style="${P}">${esc(head)}</p>` +
      `<p style="${P}">${a(manageLink(origin, manage), "Your new link")}, to change what ` +
      `you follow or how often.</p>` + f.html),
    headers: listHeaders(origin, unsub),
  };
}

// ---- the daily and the weekly ------------------------------------------------------------
// sections: what sender.collect returns, one per followed record with
// something to say. Every value in them came from the changes file and is
// escaped here.
const STUDY = {
  true: "The interim study committee recommended future legislation.",
  false: "The interim study committee did not recommend future legislation.",
  null: "The interim study committee has reported, without saying whether it " +
    "recommends future legislation.",
};
const ENDED_TAIL = "This follow has ended: a record that has finished has nothing " +
  "more to report. Its full history stays on its page.";

function upcomingLine(u) {
  return [longDate(u.date), clockTime(u.time), u.what, u.committee, u.venue]
    .filter(Boolean).join(", ");
}

function weekLine(w) {
  if (!w) return "";
  if (!w.votes && !w.exec) return "No roll call votes or executive sessions this week.";
  const parts = [];
  if (w.votes) parts.push(plural(w.votes, "roll call vote", "roll call votes"));
  if (w.exec) parts.push(plural(w.exec, "executive session", "executive sessions"));
  return `This week: ${parts.join(" and ")}.`;
}

export function digestEmail({ origin, frequency, date, sections, manage, unsub,
                              feedbackUrl, gone = false }) {
  const weekly = frequency === "weekly";
  const count = sections.reduce((n, s) => n + s.items.length + s.more +
    (s.study ? 1 : 0) + (s.ended ? 1 : 0), 0);
  const subject = weekly
    ? `Granite Record: your week to ${longDate(date, true)}`
    : `Granite Record: ${plural(count, "update", "updates")} on what you follow`;
  const intro = weekly
    ? `Your week on the record you follow, to ${longDate(date, true)}.`
    : "What changed on the record you follow, as of last night's build.";
  const text = [intro, ""];
  let html = `<p style="${P}">${esc(intro)}</p>`;

  for (const s of sections) {
    const url = siteUrl(origin, s.url);
    text.push(s.title ? `${s.label} — ${s.title}` : s.label, url);
    html += `<h2 style="font-size:18px;margin:26px 0 4px;font-weight:600">${a(url, s.label)}</h2>`;
    if (s.title) html += `<p style="margin:0 0 8px;color:#555;font-size:14px">${esc(s.title)}</p>`;
    if (s.items.length) {
      html += `<ul style="margin:0 0 10px;padding-left:20px">`;
      for (const it of s.items) {
        text.push(`  ${longDate(it.date)}  ${it.summary}`);
        html += `<li style="margin:0 0 4px"><span style="color:#555">${esc(longDate(it.date))}</span>` +
          ` — ${esc(it.summary)}</li>`;
      }
      html += "</ul>";
    }
    const more = s.more ? `…and ${s.more} more on its page.` : "";
    const lines = [more,
      s.study ? STUDY[String(s.study.recommends)] +
        (s.study.summary ? ` ${s.study.summary}` : "") : "",
      weekLine(s.week),
      ...(s.upcoming || []).map(u => `Coming up: ${upcomingLine(u)}.`)].filter(Boolean);
    for (const l of lines) {
      text.push(`  ${l}`);
      html += `<p style="margin:0 0 8px">${esc(l)}</p>`;
    }
    if (s.ended) {
      const how = s.ended.summary || `${s.label} has finished its course.`;
      text.push(`  ${how} ${ENDED_TAIL}`);
      html += `<p style="margin:0 0 8px"><b>${esc(how)}</b> ${esc(ENDED_TAIL)}</p>`;
    }
    text.push("");
  }
  const f = footer(origin, feedbackUrl, manage, unsub, gone);
  text.push("----", f.text);
  return {
    subject,
    text: text.join("\n"),
    html: frame(html + f.html),
    headers: gone ? undefined : listHeaders(origin, unsub),
  };
}
