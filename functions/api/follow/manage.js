/*
 * /api/follow/manage -- a reader's own page: what they follow, how often,
 * a new link, and unsubscribe. A private link, not a login, and the same
 * link at the foot of every email until the reader asks for a new one.
 *
 * GET answers a shell whose script reads the token from after "#" and posts
 * it straight back (action=view), so the token travels in a body and never in
 * an address. Every POST must come from this site's own page (common.sameSite).
 * A post from anywhere else changes nothing, and there are no cookies here for
 * another site to borrow.
 *
 * WHAT THE PAGE SHOWS. What the link's holder follows and how often. Never
 * the address: a link forwarded with an email must not hand the address on.
 *
 * ACTIONS (POST, form-encoded, t = the token):
 *   view                    the page
 *   save                    THE PAGE'S ONE FORM (the person, 11 October 2026: one
 *                           Save; add "from the manager without a new
 *                           confirmation email"; pause "for a set period or
 *                           until you turn them back on"). Fields: listed (every
 *                           record the page showed a box for) and keep (the boxes
 *                           ticked); add_bill, add_law (typed: "HB 1442",
 *                           "RSA 91-A") and add (every legislator and
 *                           committee ticked in the lists); frequency, detail, and
 *                           pause = none | until (with pause_until) | forever.
 *                           Only what tonight's current.json lists can be
 *                           added; the link proves the inbox, so nothing more
 *                           is asked. Unticking everything deletes the address.
 *   frequency value=daily|weekly
 *   remove    follow=<kind>:<ref>   -- removing the last one deletes the address
 *   newlink                 the links move to a new generation in one statement,
 *                           and the new ones are emailed to the address, not
 *                           shown here; every earlier link stops working
 *   unsubscribe             the address and everything it follows, deleted
 */

import { TOKEN, followHash, linksFor, openAddress, openFollow, sealFollow }
  from "../../../workers/follow/address.js";
import { MAX_FOLLOWS, addDays, clock, errName, esc, fallbackLabel, isoSeconds, keyOf, nhClock,
         note, notHere, parseKey, plain, readForm, redirect, rightPlace, sameSite, siteUrl }
  from "../../../workers/follow/common.js";
import { readCurrent } from "../../../workers/follow/changes.js";
import { longDate, newLinkEmail, sendMail } from "../../../workers/follow/mail.js";
import { DELETES, PICK_SCRIPT, deleted, message, page } from "../../../workers/follow/page.js";
import { forget, subscriberFor } from "../../../workers/follow/store.js";

const PATH = "/api/follow/manage";

// A notice is its words, or a function of how often the reader's updates
// come that returns them.
const NOTICES = {
  confirmed: "Confirmed. You will get email updates on what is listed below.",
  // A reader already subscribed whose sign-up box asked for the other
  // frequency (confirm.js): theirs was kept, so the page says so, in the
  // words of the How often below it, where the reader can change it.
  kept: freq => `Confirmed. You will get email updates on what is listed below, ${freq} as ` +
    "before: signing up again does not change how often. To change it, choose under How often " +
    "and save.",
  saved: "Saved.",
  removed: "Removed.",
  notfound: "Saved, but something you asked to add is not a bill, law, legislator or committee " +
    "that can be followed this term, so it was left out.",
  full: `Saved, but one address can follow at most ${MAX_FOLLOWS} bills, laws, legislators, ` +
    "committees and topics in all, so not everything you asked to add was added.",
};

// THE PAGE IN A READER'S WORDS (the language sweep, 17 October 2026): no
// "records" (the database's noun), no "tonight" or "rebuilt" (the build's
// clock), a date as the site writes one, and "check" where this said "tick",
// which is British.
const UPDATED_DAILY = "Granite Record updates overnight, so even the daily email covers the " +
  "record as of that morning.";

// A pause is at most a year ahead; "until I turn it back on" is kept as the
// last date there is (schema.sql), which the sender reads the same way.
const PAUSED_FOR_GOOD = "9999-12-31";
const PAUSE_DAYS_MOST = 366;
// THE LONGEST SAVE THIS TAKES. The form sends a "listed" field for every box
// it shows -- each followed record and every topic -- a "keep" for each ticked,
// and now an "add" for every legislator and committee ticked in one go. The
// 4 KiB every other endpoint reads was spent by fifty or so followed bills
// beside the forty-odd topics, and a longer form was not refused but read as
// no form at all: "This link is no longer current". 64 KiB holds MAX_FOLLOWS records
// listed and kept, every topic, and every legislator and committee there is
// ticked at once, several times over.
const MAX_FORM = 65536;
const GROUPS = [["bill", "Bills"], ["lsr", "Bill requests"], ["law", "Laws"],
                ["member", "Legislators"], ["committee", "Committees"], ["topic", "Topics"]];

// MENDING A MOVED FOLLOW (22 October 2026). The sender moves a bill
// request's follow onto its bill in place, and cannot fingerprint the bill
// (it is not given the lookup key), so the row keeps the request's
// follow_hmac. Every visit to this page mends that: each row's fingerprint is
// made again from what it holds, and a record held twice keeps one row.
async function mend(env, db, sub) {
  const rows = (await db.prepare("SELECT follow_hmac, follow_enc FROM follows WHERE subscriber_id = ?1")
    .bind(sub.id).all()).results || [];
  const want = new Map(), writes = [];
  for (const r of rows) {
    let k = "";
    try { k = await openFollow(env, r.follow_enc, sub.email_hmac); } catch { continue; }
    if (!parseKey(k)) continue;
    const fh = await followHash(env, sub.email_hmac, k);
    if (!want.has(k)) want.set(k, []);
    want.get(k).push({ ...r, fh });
  }
  for (const list of want.values()) {
    const keep = list.find(r => r.follow_hmac === r.fh) || list[0];
    for (const r of list) if (r !== keep)
      writes.push(db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND follow_hmac = ?2")
        .bind(sub.id, r.follow_hmac));
    if (keep.follow_hmac !== keep.fh)
      writes.push(db.prepare("UPDATE follows SET follow_hmac = ?1 WHERE subscriber_id = ?2 AND follow_hmac = ?3")
        .bind(keep.fh, sub.id, keep.follow_hmac));
  }
  if (writes.length) { await db.batch(writes); note("manage.mended", writes.length); }
}

const SHELL = () => page(200, {
  title: "Your email updates",
  fill: "t",
  submit: "view",
  body: `<h1>Your email updates</h1>
<form id="view" method="post" action="${PATH}"><input type="hidden" name="t" value="">
<input type="hidden" name="action" value="view"><input type="hidden" name="notice" value="">
</form>
<p class="quiet" data-waits>Opening your page&hellip;</p>`,
});

const STALE = () => message(400, "This link is no longer current",
  "Every link in our emails stops working when a new link is asked for, and the " +
  "address may since have been deleted. Use the link in your most recent email " +
  "from Granite Record.");

const ON_ITS_WAY = () => message(200, "A new link is on its way",
  "We have emailed a new link to your address. This link, and every link in " +
  "earlier emails, no longer works.");

function hidden(t, action, extra = "") {
  return `<input type="hidden" name="t" value="${esc(t)}">` +
    `<input type="hidden" name="action" value="${esc(action)}">${extra}`;
}

// What the reader follows, opened: [{ key, since }], or a follow that will
// not open is left out and counted.
async function followed(env, db, sub) {
  const rows = (await db.prepare(
    "SELECT follow_enc, since FROM follows WHERE subscriber_id = ?1").bind(sub.id).all())
    .results || [];
  const out = [];
  let bad = 0;
  for (const r of rows) {
    try {
      const key = await openFollow(env, r.follow_enc, sub.email_hmac);
      if (parseKey(key)) out.push({ key, since: r.since }); else bad++;
    } catch { bad++; }
  }
  if (bad) note("manage.unreadable-follow", bad);
  return out.sort((a, b) => a.since.localeCompare(b.since) || a.key.localeCompare(b.key));
}

function render(origin, t, sub, follows, current, notice, today) {
  const followed = new Set(follows.map(f => f.key));
  const meta = key => current?.followable.get(key);
  const box = (key, checked) => {
    const { kind, ref } = parseKey(key);
    const m = meta(key);
    const label = m?.label || fallbackLabel(kind, ref);
    // A topic's box is a chip: the whole of it ticks, so its name is no link.
    const what = m?.url && kind !== "topic"
      ? `<a href="${esc(siteUrl(origin, m.url))}">${esc(label)}</a>` : esc(label);
    const sub2 = [m?.title, m?.now ? `Now: ${m.now}` : ""].filter(Boolean)
      .map(x => `<span class="title">${esc(x)}</span>`).join("");
    // A switch on a record of its own, a chip's own box on a topic (page.js).
    return `<li><label><input type="checkbox"${kind === "topic" ? "" : ' class="sw"'} name="keep" value="${esc(key)}"${checked ? " checked" : ""}>` +
      `<input type="hidden" name="listed" value="${esc(key)}">` +
      `<span class="what">${what}${sub2}</span></label></li>`;
  };
  const groups = GROUPS.map(([kind, name]) => {
    const mine = follows.filter(f => f.key.startsWith(kind + ":"));
    let body = "", add = "";
    if (kind === "topic") {
      const all = [...(current?.followable || new Map()).keys()].filter(k => k.startsWith("topic:"));
      const keys = [...new Set([...mine.map(f => f.key), ...all])]
        .sort((a, b) => (meta(a)?.label || a).localeCompare(meta(b)?.label || b));
      body = keys.length ? `<ul class="chips">${keys.map(k => box(k, followed.has(k))).join("")}</ul>`
        : `<p class="quiet">No topic can be followed right now.</p>`;
      return `<h3>${name}</h3><p class="quiet">This term's bills on a subject. Check one to follow it.</p>${body}`;
    }
    body = mine.length ? `<ul class="follows">${mine.map(f => box(f.key, true)).join("")}</ul>` : "";
    if (kind === "bill")
      add = `<p class="add"><label for="add_bill">Add a bill</label> <input id="add_bill" name="add_bill" ` +
        `placeholder="HB 1442" maxlength="20" autocomplete="off"></p>`;
    if (kind === "law")
      add = `<p class="add"><label for="add_law">Add a law</label> <input id="add_law" name="add_law" ` +
        `placeholder="RSA 91-A" maxlength="20" autocomplete="off"></p>`;
    if (kind === "member" || kind === "committee") add = picker(kind, current, followed);
    return `<h3>${name}</h3>${body}${add}`;
  }).join("\n");
  const freq = sub.frequency === "weekly" ? "weekly" : "daily";
  // Its own notices only: the name comes from after "#", which anyone can
  // type, and "constructor" would otherwise find Object's and call it.
  const said = Object.hasOwn(NOTICES, notice) ? NOTICES[notice] : "";
  const noticeText = typeof said === "function" ? said(freq) : said;
  const detail = sub.detail === "milestones" ? "milestones" : "all";
  const p = sub.paused_until || "";
  const pause = !p || p < today ? "none" : p === PAUSED_FOR_GOOD ? "forever" : "until";
  const radio = (name, value, now, words, small) =>
    `<label><input type="radio" name="${name}" value="${value}"${value === now ? " checked" : ""}>` +
    `<span>${words}<small>${small}</small></span></label>`;
  const status = pause === "forever" ? "Paused until you turn updates back on."
    : pause === "until" ? `Paused through ${esc(longDate(p))}.` : "";
  const body = `<h1>Your email updates</h1>
<p class="lede">What you follow, how often, and how much. Nothing changes until you save.</p>
${noticeText ? `<p class="note">${esc(noticeText)}</p>` : ""}
${status ? `<p class="note">${status}</p>` : ""}
<form method="post" action="${PATH}">${hidden(t, "save")}
<div class="pair">
<section class="card"><h2>How often</h2>
<fieldset class="seg"><legend class="sr">Send me updates</legend>
${radio("frequency", "daily", freq, "Daily", "About 8:00 a.m. New Hampshire time, only on days when something is new")}
${radio("frequency", "weekly", freq, "Weekly", "Saturday about 8:00 a.m.: the week ahead, then the week's news")}
</fieldset></section>
<section class="card"><h2>How much</h2>
<fieldset class="seg"><legend class="sr">Include</legend>
${radio("detail", "all", detail, "Everything", "Every entry on the record of what you follow")}
${radio("detail", "milestones", detail, "Milestones only", "Hearings scheduled, committee votes, floor votes, and how a bill ended")}
</fieldset></section>
</div>
<section class="card"><h2>What you follow</h2>
<p class="quiet">Uncheck anything to stop following it. Adding here needs no confirmation email.
Unchecking everything deletes your address.</p>
${groups}
</section>
<section class="card"><h2>Pause</h2>
<fieldset class="pauses"><legend class="quiet">Stop sending for a while, keeping what you follow</legend>
${radio("pause", "none", pause, "Not paused", "")}
<label><input type="radio" name="pause" value="until"${pause === "until" ? " checked" : ""}><span>Paused through
<input type="date" name="pause_until" aria-label="the last day of the pause" min="${esc(today)}"
 max="${esc(addDays(today, PAUSE_DAYS_MOST))}" value="${pause === "until" ? esc(p) : ""}"></span></label>
${radio("pause", "forever", pause, "Paused until I turn updates back on", "")}
</fieldset>
<p class="quiet">${esc(UPDATED_DAILY)}</p>
</section>
<p class="save"><span class="quiet">Nothing changes until you save.</span><button type="submit">Save changes</button></p>
</form>
<section class="card"><h2>A new link</h2>
<p>This page's link is the same in every email we send you. If you forwarded one
of them, or think someone else has this link, ask for a new one. It is sent to
your address, and every link in earlier emails stops working, their unsubscribe
links included.</p>
<form method="post" action="${PATH}">${hidden(t, "newlink")}
<button type="submit" class="plain">Send me a new link</button></form>
</section>
<section class="card danger"><h2>Unsubscribe</h2>
<p>${esc(DELETES)}</p>
<form method="post" action="${PATH}">${hidden(t, "unsubscribe")}
<button type="submit" class="danger">Unsubscribe and delete my address</button></form>
</section>`;
  return page(200, { title: "Your email updates", body, script: PICK_SCRIPT });
}

// ADDING LEGISLATORS AND COMMITTEES (the person's test of 16 October 2026:
// "The legislators were not searchable and the drop-down sorted them by first
// name instead of last name. You could only select one committee and
// legislator at a time until you save."). Each was a <select> ordered by its
// label, which begins "Rep. Glen" -- one pick a Save.
//
// Now a closed <details> a kind, "Add legislators" and "Add committees", so
// the page at 375 px is as short as it was until the reader opens one. Inside
// it a box that narrows the list as they type (page.js PICK_SCRIPT, shown only
// where the script runs) and the whole list as boxes to tick, every one named
// "add", so one Save adds all that are ticked (save() takes every add, up to
// MAX_FOLLOWS). The list scrolls within a height a phone shows whole, rather
// than pushing How often and Save a full roster's length down the page.
//
// The House and the Senate apart, as every listing of legislators on the site
// is; legislators by the roster's own sort name ("aldrich, glen", current.json
// "sort"), committees by their names, which carry the chamber as the search
// writes them ("House Education Committee"). What is followed already is left
// out. A list without chambers (a build before these were written) is one
// group in the label's order.
const CHAMBER_ORDER = ["House", "Senate", ""];
const byName = (a, b) => a.localeCompare(b, "en", { sensitivity: "base" });
// The party and district are one unit, as on every chip on the site
// (components.py CHIP_TAG): at 375 px a row broke inside them, "(R - Rock" on
// one line and "25)" on the next. The trailing "(...)" is its own span, which
// page.js keeps on one line. The text is unchanged.
const TAG = /^(.*\S)\s+(\([^()]*\))$/;
const rowName = label => {
  const m = TAG.exec(label);
  return m ? `${esc(m[1])} <span class="tag">${esc(m[2])}</span>` : esc(label);
};

function picker(kind, current, followed) {
  const all = [...(current?.followable || new Map()).entries()].filter(([k]) => k.startsWith(kind + ":"));
  const rows = all.filter(([k]) => !followed.has(k));
  if (!rows.length) return "";
  const what = kind === "member" ? ["legislators", "legislator", "Name or district"]
    : ["committees", "committee", "Name"];
  // Those of neither chamber come last and are named for what they are (the
  // review of 16 October 2026: a joint committee sat under the Senate's
  // heading with none of its own). Where nothing has a chamber -- a build
  // before these were written -- the one group needs no heading.
  const chambered = all.some(([, v]) => v.chamber);
  const other = kind === "committee" ? "Joint and other committees" : "Other legislators";
  const sets = CHAMBER_ORDER.map(ch => {
    const mine = rows.filter(([, v]) => (v.chamber || "") === ch)
      .sort(([ka, a], [kb, b]) => byName(a.sort || a.label, b.sort || b.label) ||
        byName(a.label, b.label) || ka.localeCompare(kb));
    if (!mine.length) return "";
    const items = mine.map(([k, v]) =>
      `<li><label><input type="checkbox" name="add" value="${esc(k)}"><span>${rowName(v.label)}</span></label></li>`)
      .join("\n");
    const legend = ch || (chambered ? other : "");
    return `<fieldset>${legend ? `<legend>${legend}</legend>` : ""}<ul>\n${items}\n</ul></fieldset>`;
  }).join("");
  return `<details class="pick" data-pick><summary>Add ${what[0]} <span class="picked" data-picked></span></summary>
<p class="pickfind" hidden><label for="find_${kind}">Find</label>
<input type="search" id="find_${kind}" data-find placeholder="${what[2]}" autocomplete="off" spellcheck="false"></p>
<div class="picklist">${sets}
<p class="quiet none" data-none hidden>No ${what[1]} matches. Clear the box to see them all.</p></div>
</details>`;
}

// What a typed bill or law means, from tonight's list: "HB 1442" is the
// sitting term's HB 1442 (its newest filing year, where both have one), and
// "RSA 91-a" or "91-A" is the chapter. null for anything that is not listed.
export function typedKey(kind, raw, current) {
  const s = String(raw || "").toUpperCase().replace(/\s+/g, "").replace(/^RSA/, "");
  if (!s || !current) return null;
  if (kind === "law") {
    const k = `law:${s.replace(/:.*$/, "")}`;
    return current.followable.has(k) ? k : null;
  }
  const m = /^([A-Z]{2,6})0*(\d{1,4})$/.exec(s);
  if (!m) return null;
  const tail = `/${m[1]}${m[2]}`;
  const hits = [...current.followable.keys()].filter(k => k.startsWith("bill:") && k.endsWith(tail)).sort();
  return hits.length ? hits[hits.length - 1] : null;
}

// THE ONE FORM. Returns the notice to show, or "gone" when nothing is left
// followed and the address has been deleted.
async function save(env, db, sub, form, current, now) {
  const today = nhClock(now).date;
  const listed = new Set(form.getAll("listed").filter(k => parseKey(k)));
  const keep = new Set(form.getAll("keep").filter(k => listed.has(k)));
  let notice = "saved";
  const adds = [];
  for (const [kind, field] of [["bill", "add_bill"], ["law", "add_law"]]) {
    const raw = (form.get(field) || "").trim();
    if (!raw) continue;
    const k = typedKey(kind, raw, current);
    if (k) adds.push(k); else notice = "notfound";
  }
  for (const k of form.getAll("add")) {
    if (!k) continue;
    if (parseKey(k) && current?.followable.has(k)) adds.push(k); else notice = "notfound";
  }
  // Topics ticked that were not followed are adds too: their boxes are listed.
  const rows = (await db.prepare("SELECT follow_hmac, follow_enc FROM follows WHERE subscriber_id = ?1")
    .bind(sub.id).all()).results || [];
  const have = new Map();
  for (const r of rows) {
    try {
      const k = await openFollow(env, r.follow_enc, sub.email_hmac);
      if (parseKey(k)) have.set(k, r.follow_hmac);
    } catch { /* an unreadable follow is left as it is */ }
  }
  for (const k of keep) if (!have.has(k) && current?.followable.has(k)) adds.push(k);
  const drop = [...have.keys()].filter(k => listed.has(k) && !keep.has(k));
  const fresh = [...new Set(adds)].filter(k => !have.has(k));
  let room = MAX_FOLLOWS - (rows.length - drop.length);
  if (fresh.length > room) notice = "full";
  if (rows.length - drop.length + Math.min(fresh.length, Math.max(room, 0)) <= 0) {
    await forget(db, { id: sub.id });
    note("manage.forgot", 1);
    return "gone";
  }

  const writes = [];
  for (const k of drop)
    writes.push(db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND follow_hmac = ?2")
      .bind(sub.id, have.get(k)));
  for (const k of fresh) {
    if (room-- <= 0) break;
    writes.push(db.prepare("INSERT OR IGNORE INTO follows (subscriber_id, follow_hmac, follow_enc, since) " +
      "VALUES (?1, ?2, ?3, ?4)").bind(sub.id, await followHash(env, sub.email_hmac, k),
        await sealFollow(env, k, sub.email_hmac), today));
  }
  const frequency = ["daily", "weekly"].includes(form.get("frequency")) ? form.get("frequency") : sub.frequency;
  const detail = ["all", "milestones"].includes(form.get("detail")) ? form.get("detail") : (sub.detail || "all");
  let paused = sub.paused_until || null;
  const pause = form.get("pause");
  if (pause === "none") paused = null;
  else if (pause === "forever") paused = PAUSED_FOR_GOOD;
  else if (pause === "until") {
    const d = form.get("pause_until") || "";
    if (/^\d{4}-\d{2}-\d{2}$/.test(d) && d >= today && d <= addDays(today, PAUSE_DAYS_MOST)) paused = d;
  }
  // BACK FROM A PAUSE, a reader starts from now: nothing of the paused days.
  const resumed = sub.paused_until && sub.paused_until >= today && !paused;
  writes.push(resumed
    ? db.prepare("UPDATE subscribers SET frequency = ?1, detail = ?2, paused_until = NULL, " +
        "sent_date = ?3, sent_built = ?4 WHERE id = ?5").bind(frequency, detail, today, isoSeconds(now), sub.id)
    : db.prepare("UPDATE subscribers SET frequency = ?1, detail = ?2, paused_until = ?3 WHERE id = ?4")
        .bind(frequency, detail, paused, sub.id));
  await db.batch(writes);
  if (fresh.length) note("manage.added", Math.min(fresh.length, MAX_FOLLOWS));
  if (drop.length) note("manage.removed", drop.length);
  return notice;
}

// "SEND ME A NEW LINK". The links move to the next generation in ONE
// statement that names the link that asked: of two presses at once (a
// double-click), one moves them and the other finds its link no longer
// current and sends nothing, so one email goes and its links work. The email
// goes after the move; if it cannot be sent, the move is undone by a second
// statement that names the new link, so the reader keeps the links they had.
async function newLink(env, db, sub, origin) {
  const next = await linksFor(env, sub.email_hmac, sub.link_gen + 1);
  const moved = await db.prepare(
    "UPDATE subscribers SET link_gen = ?1, manage_hash = ?2, unsub_hash = ?3 " +
    "WHERE id = ?4 AND manage_hash = ?5")
    .bind(sub.link_gen + 1, next.manageHash, next.unsubHash, sub.id, sub.manage_hash).run();
  if (!moved?.meta?.changes) {
    note("manage.new-link-already-moving");
    return ON_ITS_WAY();
  }
  const undo = () => db.prepare(
    "UPDATE subscribers SET link_gen = ?1, manage_hash = ?2, unsub_hash = ?3 " +
    "WHERE id = ?4 AND manage_hash = ?5")
    .bind(sub.link_gen, sub.manage_hash, sub.unsub_hash, sub.id, next.manageHash).run();
  let sent;
  try {
    const mail = newLinkEmail({ origin, manage: next.manage, unsub: next.unsub,
                                feedbackUrl: env.FEEDBACK_URL });
    sent = await sendMail(env, { to: await openAddress(env, sub.email_enc, sub.email_hmac),
                                 ...mail });
  } catch (e) {
    await undo();
    throw e;
  }
  if (!sent.ok) {
    await undo();
    note(`manage.resend-refused.${sent.status}`);
    return message(503, "The new link could not be sent",
      "Nothing has changed: this link still works. Please try again later.");
  }
  note("manage.new-link", 1);
  return ON_ITS_WAY();
}

export async function onRequest({ request, env }) {
  if (!env.FOLLOW_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method === "GET" || request.method === "HEAD") return SHELL();
  if (request.method !== "POST") return plain(405, "GET or POST\n", { Allow: "GET, POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const form = await readForm(request, MAX_FORM);
    const t = form && form.get("t");
    if (!t || !TOKEN.test(t)) return STALE();
    const db = env.FOLLOW_DB;
    const sub = await subscriberFor(db, t, "manage");
    if (!sub) return STALE();
    await mend(env, db, sub);
    const origin = new URL(request.url).origin;
    const action = form.get("action") || "view";
    const back = n => redirect(`${PATH}#t=${t}&n=${n}`);

    if (action === "save") {
      const cur = await readCurrent(p => env.ASSETS.fetch(new URL(p, request.url)));
      if (!cur.value) {
        note("manage.current-unreadable");
        return message(503, "Please try again shortly",
          "The site could not say what can be followed just now. Nothing has changed.");
      }
      const said = await save(env, db, sub, form, cur.value, clock(env));
      return said === "gone" ? deleted() : back(said);
    }
    if (action === "frequency") {
      const v = form.get("value");
      if (v !== "daily" && v !== "weekly") return back("");
      await db.prepare("UPDATE subscribers SET frequency = ?1 WHERE id = ?2").bind(v, sub.id).run();
      return back("saved");
    }
    if (action === "remove") {
      const k = parseKey(form.get("follow"));
      if (!k) return back("");
      const fh = await followHash(env, sub.email_hmac, keyOf(k.kind, k.ref));
      const n = await db.prepare("SELECT COUNT(*) AS n FROM follows WHERE subscriber_id = ?1")
        .bind(sub.id).first("n");
      const mine = await db.prepare("SELECT 1 AS y FROM follows WHERE subscriber_id = ?1 " +
        "AND follow_hmac = ?2").bind(sub.id, fh).first();
      if (!mine) return back("");
      if (Number(n) <= 1) {
        await forget(db, { id: sub.id });
        note("manage.forgot", 1);
        return deleted();
      }
      await db.prepare("DELETE FROM follows WHERE subscriber_id = ?1 AND follow_hmac = ?2")
        .bind(sub.id, fh).run();
      return back("removed");
    }
    if (action === "unsubscribe") {
      await forget(db, { id: sub.id });
      note("manage.forgot", 1);
      return deleted();
    }
    if (action === "newlink") return await newLink(env, db, sub, origin);

    // view
    const follows = await followed(env, db, sub);
    const cur = await readCurrent(p => env.ASSETS.fetch(new URL(p, request.url)));
    if (!cur.value) note("manage.current-unreadable");
    return render(origin, t, sub, follows, cur.value, form.get("notice") || "", nhClock(clock(env)).date);
  } catch (e) {
    note(`manage.error.${errName(e)}`);
    return message(503, "Please try again shortly",
      "Something went wrong on our side. Nothing has changed.");
  }
}
