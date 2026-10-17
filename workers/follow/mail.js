/*
 * The mail: one call to Resend, and the five emails this sends -- the
 * confirmation, the "you are following" a confirmation sends, a new link, the
 * daily and the weekly -- each in plain text and in simple HTML.
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
import { addDays, esc, oneLine, siteUrl } from "./common.js";

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

// nightly: whether the email reports anything, and so needs saying that the
// record is as of last night's build. An email that reports nothing (the one
// a confirmation sends) leaves it out rather than say "this reports".
function footer(origin, feedbackUrl, manage, unsub, gone, nightly = true) {
  const fb = feedbackUrl ? siteOrForm(feedbackUrl) : "";
  const lines = nightly ? [NIGHTLY, ""] : [];
  const html = [`<hr style="border:0;border-top:1px solid #ddd;margin:28px 0 16px">`,
    ...(nightly ? [`<p style="${P};font-size:14px;color:#444">${esc(NIGHTLY)}</p>`] : [])];
  if (gone) {
    const s = "That was the last thing you followed, so your address has been deleted " +
      "from our database with it. To follow something again, use Follow on its page.";
    lines.push(s, "");
    html.push(`<p style="${P};font-size:14px;color:#444">${esc(s)}</p>`);
  } else {
    lines.push("Change what you follow, how often, or pause:",
      manageLink(origin, manage), "",
      "Unsubscribe, deleting your address and everything you follow from our database at once:",
      unsubscribeLink(origin, unsub), "");
    html.push(`<p style="${P};font-size:14px">${a(manageLink(origin, manage),
      "Change what you follow, how often, or pause")}</p>`,
      `<p style="${P};font-size:14px">${a(unsubscribeLink(origin, unsub),
        "Unsubscribe")} — deletes your address and everything you follow from our ` +
        `database, at once.</p>`);
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
  const count = total > 1 ? `You follow ${plural(total, "record", "records")} in all.` : "";
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
  const html = frame(
    `<p style="${P}">You are now following:</p>` +
    `<p style="${P};padding-left:12px;border-left:3px solid #ccc">` +
    (page ? a(page, oneLine(label, 120)) : esc(oneLine(label, 120))) +
    (title ? ` — ${esc(oneLine(title, 160))}` : "") + "</p>" +
    (count ? `<p style="${P}">${esc(count)}</p>` : "") +
    `<p style="${P}">${esc(how)}</p>` +
    (paused ? `<p style="${P}">${esc(paused)}</p>` : "") +
    `<p style="${P}">${esc(keep)}</p>` + f.html);
  return { subject, text, html, headers: listHeaders(origin, unsub) };
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

// The fixed sentence, then the record's own words if they say something else.
// A summary that only repeats the fixed sentence (CHANGES_FORMAT.md's example
// once did) is not printed twice.
function studyLine(study) {
  const fixed = STUDY[String(study.recommends)];
  const own = oneLine(study.summary || "");
  const norm = t => t.toLowerCase().replace(/[\s.]+$/, "").replace(/\s+/g, " ");
  return own && norm(own) !== norm(fixed) ? `${fixed} ${own}` : fixed;
}

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

// THE ORDER A DIGEST IS IN (the design the person approved, 11 October
// 2026): what matters most at a glance, then -- in the weekly -- the week
// ahead, then each kind of record under its own heading.
// AN ITEM IN PLAIN WORDS (the person's choice of 14 October 2026): the
// build's plain sentence where it has one (CHANGES_FORMAT.md, "plain"), the
// clerk's line where it does not. A newly recorded old event says so, and a
// proceeding still to come says it is scheduled, so neither reads as last
// night's news.
const LATE_DAYS = 14;        // older than this when first seen: "Newly recorded"
const LATE_SHOWN = 3;        // newly recorded entries listed a record, the rest counted
const said = it => it.plain || it.summary;
export const late = it => !!it.seen && it.date < addDays(String(it.seen).slice(0, 10), -LATE_DAYS);
function itemWords(it, date) {
  if (it.date > date) return `Scheduled: ${said(it)}`;
  return late(it) ? `Newly recorded: ${said(it)}` : said(it);
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

const GROUPS = [["bill", "Bills"], ["law", "Laws"], ["member", "Legislators"],
                ["committee", "Committees"], ["topic", "Topics"]];

// What most deserves the subject line and the "at a glance" list, best first:
// how a record ended, then a roll call, a study's report, a proceeding
// scheduled, an executive session, a committee report, any other milestone.
const RANK = { vote: 1, study: 2, scheduled: 3, exec: 4, report: 5 };
export function headlines(sections, date = "", skipAhead = false) {
  const out = [];
  for (const s of sections) {
    if (s.ended && !s.ended.fallback && s.ended.summary) out.push([0, s.ended.summary]);
    if (s.study) out.push([2, studyLine(s.study)]);
    for (const it of s.items) {
      if (!it.milestone || late(it)) continue;
      // What is still to come is the week ahead's in a weekly that has one.
      if (date && it.date > date && skipAhead) continue;
      out.push([RANK[it.kind] || 6, date ? itemWords(it, date) : said(it)]);
    }
  }
  const seen = new Set();
  return out.sort((a, b) => a[0] - b[0])
    .map(([, t]) => oneLine(t, 140).replace(/\.$/, ""))
    .filter(t => !seen.has(t) && seen.add(t));
}

// The week ahead, from every section's upcoming: one row a proceeding, with
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

// One ballot beside its roll call: "voted yes; passed 201-163".
function ballotLine(v) {
  const out = v.result ? `; ${v.result}${v.tally ? ` ${v.tally}` : ""}` : (v.tally ? `; ${v.tally}` : "");
  return `voted ${v.ballot}${out}`;
}

export function digestEmail({ origin, frequency, date, sections: given, manage, unsub,
                              feedbackUrl, gone = false }) {
  const weekly = frequency === "weekly";
  const sections = onceEach(given);
  const count = sections.reduce((n, s) => n + s.items.length + (s.votes || []).length + s.more +
    (s.study ? 1 : 0) + (s.ended ? 1 : 0), 0);
  const ahead = weekly ? weekAhead(sections) : [];
  const tops = headlines(sections, date, ahead.length > 0);
  const more = n => n > 0 ? `, and ${plural(n, "more update", "more updates")}` : "";
  const subject = oneLine(weekly
    ? (ahead.length
        ? `Your week: ${plural(ahead.length, "proceeding", "proceedings")} coming up` +
          (tops.length ? `, and ${tops[0]}` : "")
        : tops.length ? `Your week: ${tops[0]}${more(count - 1)}`
          : `Your week to ${longDate(date, true)}`)
    : tops.length ? `${tops[0]}${more(count - 1)}`
      : `${plural(count, "update", "updates")} on what you follow`, 150);
  const intro = weekly
    ? `Your week on the record you follow, to ${longDate(date, true)}.`
    : "What changed on the record you follow, as of last night's build.";
  const text = [intro, ""];
  let html = `<p style="${P}">${esc(intro)}</p>`;

  // AT A GLANCE: where there is enough to need it.
  const glance = tops.slice(0, 3);
  if (glance.length && (count >= 4 || sections.length >= 3)) {
    text.push("At a glance:", ...glance.map(g => `  * ${g}`), "");
    html += `<div style="border:1px solid #ddd;border-radius:4px;padding:12px 14px;margin:0 0 20px">` +
      `<p style="margin:0 0 6px"><b>At a glance</b></p><ul style="margin:0;padding-left:18px">` +
      glance.map(g => `<li style="margin:0 0 4px">${esc(g)}</li>`).join("") + "</ul></div>";
  }

  const heading = h => {
    text.push(h.toUpperCase(), "");
    html += `<h3 style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#555;` +
      `margin:28px 0 8px;padding-top:12px;border-top:1px solid #ddd">${esc(h)}</h3>`;
  };

  if (ahead.length) {
    heading("The week ahead");
    html += `<table style="border-collapse:collapse;width:100%;font-size:15px">`;
    for (const r of ahead) {
      const when = [longDate(r.date, true), clockTime(r.time)].filter(Boolean).join(", ");
      const what = r.what.charAt(0).toUpperCase() + r.what.slice(1);
      const where = [r.committee, r.venue].filter(Boolean).join(", ");
      text.push(`  ${when}: ${what}${where ? `, ${where}` : ""}. For ${r.labels.join(" and ")}.`);
      html += `<tr><td style="padding:6px 10px 6px 0;border-bottom:1px solid #eee;color:#555;` +
        `vertical-align:top;white-space:nowrap">${esc(when)}</td><td style="padding:6px 0;` +
        `border-bottom:1px solid #eee"><b>${esc(what)}</b>${where ? `, ${esc(where)}` : ""}<br>` +
        `<span style="font-size:14px">For ${r.labels.map((l, i) => a(siteUrl(origin, r.urls[i]), l))
          .join(" and ")}</span></td></tr>`;
    }
    html += "</table>";
    text.push("");
  }

  for (const [kind, name] of GROUPS) {
    const mine = sections.filter(s => s.kind === kind);
    if (!mine.length) continue;
    if (weekly && ahead.length && !mine.some(s => s.items.length || (s.votes || []).length ||
        s.study || s.ended || s.week)) continue;
    heading(weekly && ahead.length && kind === GROUPS[0][0] ? `${name}: the week that was` : name);
    for (const s of mine) {
      const url = siteUrl(origin, s.url);
      text.push(s.title ? `${s.label} — ${s.title}` : s.label, url);
      html += `<h2 style="font-size:18px;margin:20px 0 4px;font-weight:600">${a(url, s.label)}</h2>`;
      if (s.title) html += `<p style="margin:0 0 6px;color:#555;font-size:14px">${esc(s.title)}</p>`;
      if (s.now) {
        text.push(`  Now: ${s.now}`);
        html += `<p style="margin:0 0 6px;font-size:14px">Now: ${esc(s.now)}</p>`;
      }
      if ((s.votes || []).length) {
        text.push(`  Roll calls (${s.votes.length}):`);
        html += `<table style="border-collapse:collapse;width:100%;font-size:14px;margin:0 0 10px">`;
        for (const it of s.votes) {
          const v = it.vote;
          const on = v.motion ? ` on ${v.motion}` : "";
          text.push(`  ${longDate(it.date)}  ${v.bill || ""}${v.title ? ` (${oneLine(v.title, 90)})` : ""}` +
            `${on}: ${ballotLine(v)}`);
          html += `<tr><td style="padding:5px 10px 5px 0;border-bottom:1px solid #eee;color:#555;` +
            `vertical-align:top;white-space:nowrap">${esc(longDate(it.date))}</td>` +
            `<td style="padding:5px 0;border-bottom:1px solid #eee">` +
            (v.bill ? a(siteUrl(origin, it.url), v.bill) : "") +
            (v.title ? ` <span style="color:#555">${esc(oneLine(v.title, 140))}</span>` : "") +
            `<br>${esc(on.trim() ? on.trim().replace(/^on /, "On ") + ": " : "")}` +
            `<b>${esc(ballotLine(v))}</b></td></tr>`;
        }
        html += "</table>";
      }
      // What is still to come is the week ahead's, in the weekly; and of
      // the old events newly recorded, the first few, the rest counted.
      const fresh = s.items.filter(it => !late(it) && !(weekly && ahead.length && it.date > date));
      const old = s.items.filter(it => late(it));
      const shown = [...fresh, ...old.slice(0, LATE_SHOWN)];
      const earlier = old.length - Math.min(old.length, LATE_SHOWN);
      if (shown.length) {
        html += `<ul style="margin:0 0 10px;padding-left:20px">`;
        for (const it of shown) {
          const words = itemWords(it, date);
          text.push(`  ${longDate(it.date)}  ${words}`);
          const line = esc(words);
          html += `<li style="margin:0 0 4px"><span style="color:#555">${esc(longDate(it.date))}</span>` +
            ` — ${it.milestone && !late(it) ? `<b>${line}</b>` : line}</li>`;
        }
        html += "</ul>";
      }
      const lines = [s.more ? `…and ${s.more} more on its page.` : "",
        earlier ? `…and ${plural(earlier, "earlier entry", "earlier entries")} newly on the record, on its page.` : "",
        s.study ? studyLine(s.study) : "", weekLine(s.week),
        ...(ahead.length ? [] : (s.upcoming || []).map(u => `Coming up: ${upcomingLine(u)}.`))]
        .filter(Boolean);
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
