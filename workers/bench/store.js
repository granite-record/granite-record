/*
 * The shared bench's database calls (schema.sql), on BENCH_DB, never the
 * reports' DB or FOLLOW_DB. Every value is bound, never written into the SQL.
 *
 * SERVED ONCE. An item is claimed by one statement (claimOne): an UPDATE whose
 * WHERE picks the first open item no live hold covers, and which RETURNs it,
 * so two people asking at once are never given one item. A hold lasts ten
 * minutes and the page renews it every two while it is open (hold), so a
 * closed page lets its items go within ten. A link holds two at most: the
 * one shown and the next, fetched ahead. An answer is written, and its item
 * marked judged, in one batch, and only while the link still holds it.
 *
 * LIMITS, each a guess of the design's (its section 5, 17 November 2026):
 * DAILY_CAP answers a day for a contributor's link, counted and raised in one
 * statement; one answer a second (GAP_MS); notes of NOTE_MOST characters.
 *
 * CALIBRATION. One item in CALIB_EVERY a contributor is given is one the
 * owner judged already (calib), never one that link has answered; its answer
 * is kept here beside hers, and never merged into the ledger.
 */

import { hashToken } from "../follow/address.js";

export const HOLD_MS = 10 * 60 * 1000;
export const HELD_MOST = 2;
export const CALIB_EVERY = 25;
export const DAILY_CAP = 500;
export const GAP_MS = 1000;
export const NOTE_MOST = 280;
export const QUEUES = ["timing", "topic", "tag"];
export const TOKEN = /^[A-Za-z0-9_-]{43}$/;
export const LINK_ID = /^[a-z2-9]{6}$/;

export const iso = d => d.toISOString();
export const day = d => d.toISOString().slice(0, 10);
const later = (now, ms) => iso(new Date(now.getTime() + ms));
const parse = (s, fallback) => { try { return JSON.parse(s); } catch { return fallback; } };

// ---- links -------------------------------------------------------------------------

// The link a token belongs to, or null: one indexed read, whatever the token.
export async function linkFor(db, token) {
  if (typeof token !== "string" || !TOKEN.test(token)) return null;
  const row = await db.prepare(
    "SELECT id, name, role, queues, state, made_on, last_on, daily_cap FROM links WHERE token_hash = ?1")
    .bind(await hashToken(token)).first();
  return row ? { ...row, queues: queuesOf(row) } : null;
}

// The queues a link may judge: every one for the owner's.
export function queuesOf(link) {
  if (link.role === "owner") return QUEUES.slice();
  const q = typeof link.queues === "string" ? parse(link.queues, []) : link.queues;
  return QUEUES.filter(x => Array.isArray(q) && q.includes(x));
}

// The day a link was last used, and nothing finer.
export async function touch(db, link, now) {
  await db.prepare("UPDATE links SET last_on = ?1 WHERE id = ?2 AND (last_on IS NULL OR last_on < ?1)")
    .bind(day(now), link.id).run();
}

// A token: 32 random bytes, base64url, 43 characters. Only its hash is kept.
export function newToken() {
  let s = "";
  for (const x of crypto.getRandomValues(new Uint8Array(32))) s += String.fromCharCode(x);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// Six letters and digits, none that reads as another (no l, o, 0 or 1).
const ID_LETTERS = "abcdefghijkmnpqrstuvwxyz23456789";
export function newId() {
  return [...crypto.getRandomValues(new Uint8Array(6))].map(x => ID_LETTERS[x % 32]).join("");
}

// A name the owner gives a link: one line, at most 60 characters.
export function cleanName(raw) {
  return String(raw ?? "").normalize("NFKC").replace(/[\u0000-\u001f\u007f-\u009f]+/g, " ")
    .replace(/\p{Cf}/gu, "").replace(/\s+/g, " ").trim().slice(0, 60);
}

// A new contributor's link: { id, token }, the token shown once and never kept.
export async function makeLink(db, { name, queues }, now) {
  const n = cleanName(name);
  const q = QUEUES.filter(x => Array.isArray(queues) && queues.includes(x));
  if (!n || !q.length) return null;
  for (let tries = 0; tries < 5; tries++) {
    const id = newId(), token = newToken();
    const r = await db.prepare(
      "INSERT OR IGNORE INTO links (id, name, token_hash, role, queues, state, made_on, daily_cap) " +
      "VALUES (?1, ?2, ?3, 'contributor', ?4, 'active', ?5, ?6)")
      .bind(id, n, await hashToken(token), JSON.stringify(q), day(now), DAILY_CAP).run();
    if (r?.meta?.changes) return { id, token };
  }
  return null;
}

// Pause, resume or turn off a contributor's link; never the owner's own, and
// never one turned off. A link paused or turned off lets go of what it holds.
export async function setState(db, id, state) {
  if (!LINK_ID.test(String(id)) || !["active", "paused", "off"].includes(state)) return 0;
  const r = await db.batch([
    db.prepare("UPDATE links SET state = ?1 WHERE id = ?2 AND role = 'contributor' AND state != 'off'")
      .bind(state, id),
    db.prepare("UPDATE items SET held_by = NULL, held_until = NULL WHERE held_by = ?1 AND state = 'open' " +
      "AND ?2 != 'active'").bind(id, state),
    db.prepare("DELETE FROM calib_holds WHERE link = ?1 AND ?2 != 'active'").bind(id, state),
  ]);
  return r[0]?.meta?.changes ?? 0;
}

// ---- what is held ------------------------------------------------------------------

function item(row, calib) {
  return { kind: row.kind, key: row.key, queue: row.queue, grp: row.grp || "",
           card: parse(row.card, {}), ...(calib ? { calib: true } : {}) };
}

// What this link holds now, its own items in the order they are served, then
// a calibration item.
export async function heldItems(db, link, now) {
  const t = iso(now);
  const own = (await db.prepare(
    "SELECT kind, key, queue, grp, card FROM items WHERE held_by = ?1 AND state = 'open' " +
    "AND held_until > ?2 ORDER BY ord").bind(link.id, t).all()).results || [];
  const cal = (await db.prepare(
    "SELECT c.kind, c.key, c.queue, c.card FROM calib_holds h JOIN calib c ON c.kind = h.kind " +
    "AND c.key = h.key WHERE h.link = ?1 AND h.held_until > ?2 ORDER BY h.held_until")
    .bind(link.id, t).all()).results || [];
  return [...own.map(r => item(r, false)), ...cal.map(r => item(r, true))];
}

// ONE STATEMENT: the first open item of these queues that no live hold covers,
// held for this link, and returned. Two links asking at once cannot both
// have it: the UPDATE that takes it is the read that chose it.
export async function claimOne(db, link, queues, now) {
  const row = await db.prepare(
    "UPDATE items SET held_by = ?1, held_until = ?2 WHERE rowid = (" +
    "SELECT rowid FROM items WHERE state = 'open' AND queue IN (SELECT value FROM json_each(?3)) " +
    "AND (held_until IS NULL OR held_until <= ?4) ORDER BY ord LIMIT 1) " +
    "RETURNING kind, key, queue, grp, card")
    .bind(link.id, later(now, HOLD_MS), JSON.stringify(queues), iso(now)).first();
  return row ? item(row, false) : null;
}

// A calibration item for this link, in one statement too: one the owner
// judged, in these queues, that this link has neither answered nor holds.
export async function claimCalib(db, link, queues, now) {
  const row = await db.prepare(
    "INSERT INTO calib_holds (link, kind, key, held_until) SELECT ?1, c.kind, c.key, ?2 FROM calib c " +
    "WHERE c.queue IN (SELECT value FROM json_each(?3)) AND NOT EXISTS (SELECT 1 FROM judgments j " +
    "WHERE j.link = ?1 AND j.kind = c.kind AND j.key = c.key AND j.state != 'undone') " +
    "AND NOT EXISTS (SELECT 1 FROM calib_holds h WHERE h.link = ?1 AND h.kind = c.kind AND h.key = c.key) " +
    "ORDER BY c.ord LIMIT 1 RETURNING kind, key")
    .bind(link.id, later(now, HOLD_MS), JSON.stringify(queues)).first();
  if (!row) return null;
  const c = await db.prepare("SELECT kind, key, queue, card FROM calib WHERE kind = ?1 AND key = ?2")
    .bind(row.kind, row.key).first();
  return c ? item(c, true) : null;
}

// How many answers a link has given that stand (none taken back).
async function answered(db, link) {
  return Number(await db.prepare(
    "SELECT COUNT(*) AS n FROM judgments WHERE link = ?1 AND state != 'undone'").bind(link.id).first("n")) || 0;
}

// What the page shows next: what this link holds in `queues` (every queue it
// may judge, or the one chosen), and more claimed until it holds HELD_MOST.
// A hold in a queue no longer chosen is let go. A contributor's every
// CALIB_EVERY-th item is a calibration item, where one is left.
export async function next(db, link, queues, now) {
  const want = QUEUES.filter(q => queues.includes(q) && link.queues.includes(q));
  if (!want.length) return [];
  const w = JSON.stringify(want);
  await db.batch([
    db.prepare("UPDATE items SET held_by = NULL, held_until = NULL WHERE held_by = ?1 AND state = 'open' " +
      "AND queue NOT IN (SELECT value FROM json_each(?2))").bind(link.id, w),
    db.prepare("DELETE FROM calib_holds WHERE link = ?1 AND NOT EXISTS (SELECT 1 FROM calib c " +
      "WHERE c.kind = calib_holds.kind AND c.key = calib_holds.key " +
      "AND c.queue IN (SELECT value FROM json_each(?2)))").bind(link.id, w),
  ]);
  const held = await heldItems(db, link, now);
  let given = link.role === "contributor" ? await answered(db, link) + held.length : 0;
  while (held.length < HELD_MOST) {
    let got = null;
    if (link.role === "contributor" && (given + 1) % CALIB_EVERY === 0) got = await claimCalib(db, link, want, now);
    if (!got) got = await claimOne(db, link, want, now);
    if (!got) break;
    held.push(got);
    given++;
  }
  return held;
}

// The page is open: its holds go on for another ten minutes. Only a hold still
// live is renewed; one already lapsed may be someone else's by now.
export async function hold(db, link, now) {
  const r = await db.batch([
    db.prepare("UPDATE items SET held_until = ?1 WHERE held_by = ?2 AND state = 'open' AND held_until > ?3")
      .bind(later(now, HOLD_MS), link.id, iso(now)),
    db.prepare("UPDATE calib_holds SET held_until = ?1 WHERE link = ?2 AND held_until > ?3")
      .bind(later(now, HOLD_MS), link.id, iso(now)),
  ]);
  return (r[0]?.meta?.changes ?? 0) + (r[1]?.meta?.changes ?? 0);
}

// ---- an answer -----------------------------------------------------------------------

// Seconds as the laptop bench writes a time: H:MM:SS.
export function clock(sec) {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  return `${Math.floor(s / 3600)}:${String(Math.floor(s % 3600 / 60)).padStart(2, "0")}:` +
    String(s % 60).padStart(2, "0");
}

// What the page sends, in the ledger's words, or null where it is not an
// answer this card can be given. `a` is { answer, better } for a claim and
// { steps: [{ answer, mark }] } for a moment; `options` the queue's list.
//
// A CLAIM (a topic or a tag): Yes, No or Not sure, in the words the card
// carries ({ yes: "correct", no: "wrong", unsure: "unsure" }); a better
// answer only with a No, and only one of the queue's options.
//
// A MOMENT (a timing): one step for each published time, the start and then
// the end where there is one. Each step is Yes (within about ten seconds),
// No with the moment marked off the player (seconds), No with none ("cannot
// find it"), or Not sure. The verdict is the No's word if a step is No, else
// Not sure's if one is, else Yes's; the fields say each step, and each moment
// marked as review.py's timing kind writes one ("observed_start": "1:10:01").
export function toLedger(card, options, a) {
  if (!card || !a || typeof a !== "object") return null;
  const said = x => ["yes", "no", "unsure"].includes(x);
  const fields = {};
  let side;
  if (card.type === "moment") {
    const steps = Array.isArray(card.steps) ? card.steps : [];
    const got = Array.isArray(a.steps) ? a.steps : [];
    if (!steps.length || got.length !== steps.length) return null;
    for (let i = 0; i < steps.length; i++) {
      const s = got[i] || {}, name = steps[i].field === "end" ? "end" : "start";
      if (!said(s.answer)) return null;
      fields[name] = s.answer;
      if (s.mark !== undefined && s.mark !== null) {
        const m = Number(s.mark);
        if (s.answer !== "no" || !Number.isFinite(m) || m < 0 || m > 172800) return null;
        fields[`observed_${name}`] = clock(m);
      }
    }
    const all = got.map(s => s.answer);
    side = all.includes("no") ? "no" : all.includes("unsure") ? "unsure" : "yes";
  } else if (card.type === "claim") {
    if (!said(a.answer)) return null;
    side = a.answer;
    if (a.better !== undefined && a.better !== null && a.better !== "") {
      if (side !== "no" || !card.better || !Array.isArray(options) || !options.includes(a.better)) return null;
      fields[card.better.field] = a.better;
    }
  } else {
    return null;
  }
  const verdict = (card.words || {})[side];
  if (typeof verdict !== "string" || !verdict) return null;
  return { verdict, side, fields };
}

// THE DAILY CAP, counted and raised in one statement, so two answers at once
// cannot both read 499. null when the day is full. The owner's link has none.
export async function underCap(db, link, now) {
  if (link.daily_cap === null || link.daily_cap === undefined) return 0;
  const n = await db.prepare(
    "INSERT INTO link_days (link, day, n) VALUES (?1, ?2, 1) " +
    "ON CONFLICT(link, day) DO UPDATE SET n = n + 1 WHERE n < ?3 RETURNING n")
    .bind(link.id, day(now), Number(link.daily_cap)).first("n");
  return n === null || n === undefined ? null : Number(n);
}

async function refund(db, link, now) {
  if (link.daily_cap === null || link.daily_cap === undefined) return;
  await db.prepare("UPDATE link_days SET n = n - 1 WHERE link = ?1 AND day = ?2 AND n > 0")
    .bind(link.id, day(now)).run();
}

// The card, queue and options of an item this link may answer now -- one it
// holds, or a calibration item it holds -- or null.
async function heldCard(db, link, kind, key, now) {
  const t = iso(now);
  const own = await db.prepare(
    "SELECT i.card, i.queue, q.options, 0 AS calib FROM items i JOIN queues q ON q.queue = i.queue " +
    "WHERE i.kind = ?1 AND i.key = ?2 AND i.held_by = ?3 AND i.state = 'open' AND i.held_until > ?4")
    .bind(kind, key, link.id, t).first();
  if (own) return own;
  return await db.prepare(
    "SELECT c.card, c.queue, q.options, 1 AS calib FROM calib_holds h JOIN calib c ON c.kind = h.kind " +
    "AND c.key = h.key JOIN queues q ON q.queue = c.queue WHERE h.link = ?1 AND h.kind = ?2 AND h.key = ?3 " +
    "AND h.held_until > ?4").bind(link.id, kind, key, t).first();
}

// AN ANSWER: kept, and its item marked judged, in one batch, only while this
// link holds the item and only a second or more after its last answer that
// stands. { ok: true, verdict, side, calib } or { ok: false, why }, why one of
// "gone" (not held: answered already, lapsed, or never given), "bad" (not an
// answer this card takes), "fast" (within a second of the last) and "full"
// (the day's cap).
export async function judge(db, link, { kind, key, answer, note = "" }, now) {
  if (typeof kind !== "string" || typeof key !== "string" || kind.length > 40 || key.length > 300)
    return { ok: false, why: "bad" };
  const held = await heldCard(db, link, kind, key, now);
  if (!held) return { ok: false, why: "gone" };
  const got = toLedger(parse(held.card, null), parse(held.options, null), answer);
  if (!got) return { ok: false, why: "bad" };
  const gap = iso(new Date(now.getTime() - GAP_MS));
  const last = await db.prepare(
    "SELECT at FROM judgments WHERE link = ?1 AND state != 'undone' ORDER BY id DESC LIMIT 1")
    .bind(link.id).first("at");
  if (last && last > gap) return { ok: false, why: "fast" };
  if (await underCap(db, link, now) === null) return { ok: false, why: "full" };
  const t = iso(now), calib = Number(held.calib) ? 1 : 0;
  // Written only while the link still holds the item, read again inside the
  // batch: a hold that lapsed since heldCard read it may be another's now.
  const holds = calib
    ? "EXISTS (SELECT 1 FROM calib_holds WHERE link = ?3 AND kind = ?1 AND key = ?2 AND held_until > ?8)"
    : "EXISTS (SELECT 1 FROM items WHERE kind = ?1 AND key = ?2 AND held_by = ?3 AND state = 'open' " +
      "AND held_until > ?8)";
  // The item goes with its answer, and only if the answer went in: the second
  // statement asks for the row the first wrote.
  const wentIn = "EXISTS (SELECT 1 FROM judgments WHERE link = ?1 AND kind = ?2 AND key = ?3 " +
    "AND at = ?4 AND state = 'kept')";
  const r = await db.batch([
    db.prepare(
      "INSERT INTO judgments (kind, key, link, verdict, fields, note, side, at, calib, state) " +
      "SELECT ?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, 'kept' WHERE NOT EXISTS (SELECT 1 FROM judgments " +
      `WHERE link = ?3 AND state != 'undone' AND at > ?10) AND ${holds}`)
      .bind(kind, key, link.id, got.verdict, JSON.stringify(got.fields), String(note || ""), got.side, t,
            calib, gap),
    calib
      ? db.prepare(`DELETE FROM calib_holds WHERE link = ?1 AND kind = ?2 AND key = ?3 AND ${wentIn}`)
        .bind(link.id, kind, key, t)
      : db.prepare("UPDATE items SET state = 'judged', held_by = NULL, held_until = NULL WHERE kind = ?2 " +
          `AND key = ?3 AND held_by = ?1 AND state = 'open' AND ${wentIn}`).bind(link.id, kind, key, t),
  ]);
  if (!r[0]?.meta?.changes) {
    await refund(db, link, now);
    return { ok: false, why: await heldCard(db, link, kind, key, now) ? "fast" : "gone" };
  }
  return { ok: true, verdict: got.verdict, side: got.side, calib: !!calib };
}

// UNDO: this link's latest answer, while it is still kept (not merged, not
// taken back already), back: the answer marked undone, its item held for this
// link again so the page can show it, and the day's count given back. Only the
// latest: a second Undo finds the answer it took back and does nothing more.
// Returns the item, or null.
export async function undo(db, link, now) {
  const j = await db.prepare(
    "SELECT id, kind, key, calib, state FROM judgments WHERE link = ?1 ORDER BY id DESC LIMIT 1")
    .bind(link.id).first();
  if (!j || j.state !== "kept") return null;
  const until = later(now, HOLD_MS);
  const r = await db.batch([
    db.prepare("UPDATE judgments SET state = 'undone' WHERE id = ?1 AND state = 'kept'").bind(j.id),
    Number(j.calib)
      ? db.prepare("INSERT OR REPLACE INTO calib_holds (link, kind, key, held_until) VALUES (?1, ?2, ?3, ?4)")
        .bind(link.id, j.kind, j.key, until)
      : db.prepare("UPDATE items SET state = 'open', held_by = ?1, held_until = ?2 WHERE kind = ?3 " +
          "AND key = ?4 AND state = 'judged'").bind(link.id, until, j.kind, j.key),
  ]);
  if (!r[0]?.meta?.changes) return null;
  await refund(db, link, now);
  const row = Number(j.calib)
    ? await db.prepare("SELECT kind, key, queue, card FROM calib WHERE kind = ?1 AND key = ?2")
      .bind(j.kind, j.key).first()
    : await db.prepare("SELECT kind, key, queue, grp, card FROM items WHERE kind = ?1 AND key = ?2")
      .bind(j.kind, j.key).first();
  return row ? item(row, Number(j.calib) === 1) : null;
}

// ---- how far along -------------------------------------------------------------------

// The group an item is in: its label, how many items it has and how many are
// judged ("Medicaid and public assistance: 12 of 30").
export async function progress(db, grp) {
  if (!grp) return null;
  const g = await db.prepare(
    "SELECT g.label, (SELECT COUNT(*) FROM items i WHERE i.grp = g.grp AND i.state != 'elsewhere') AS goal, " +
    "(SELECT COUNT(*) FROM items i WHERE i.grp = g.grp AND i.state = 'judged') AS done " +
    "FROM groups g WHERE g.grp = ?1").bind(grp).first();
  return g ? { grp, label: g.label, goal: Number(g.goal) || 0, done: Number(g.done) || 0 } : null;
}

// Every queue's share checked: its pool, and how many of it are judged -- what
// the ledger held when the last pack or merge said, and what is kept here and
// not merged yet. A calibration answer is not counted: it was judged already.
export async function farAlong(db) {
  const rows = (await db.prepare(
    "SELECT q.queue, q.label, q.pool, q.judged + (SELECT COUNT(*) FROM items i WHERE i.queue = q.queue " +
    "AND i.state = 'judged' AND EXISTS (SELECT 1 FROM judgments j WHERE j.kind = i.kind AND j.key = i.key " +
    "AND j.state = 'kept' AND j.calib = 0)) AS judged FROM queues q ORDER BY q.ord").all()).results || [];
  return rows.map(r => ({ queue: r.queue, label: r.label, pool: Number(r.pool) || 0,
                          judged: Math.min(Number(r.judged) || 0, Number(r.pool) || 0) }));
}

// The queues the page's chooser offers this link: label and order, from the pack.
export async function queueLabels(db, link) {
  const rows = (await db.prepare("SELECT queue, label FROM queues ORDER BY ord").all()).results || [];
  return rows.filter(r => link.queues.includes(r.queue)).map(r => ({ queue: r.queue, label: r.label }));
}

// ---- the owner's Links page ------------------------------------------------------------

// Every link, with what it has answered: answers that stand, those not merged
// yet, and how often its calibration answers agree with the owner's.
export async function linkList(db) {
  const rows = (await db.prepare(
    "SELECT l.id, l.name, l.role, l.queues, l.state, l.made_on, l.last_on, " +
    "(SELECT COUNT(*) FROM judgments j WHERE j.link = l.id AND j.state != 'undone' AND j.calib = 0) AS answers, " +
    "(SELECT COUNT(*) FROM judgments j WHERE j.link = l.id AND j.state = 'kept' AND j.calib = 0) AS unmerged, " +
    "(SELECT COUNT(*) FROM judgments j JOIN calib c ON c.kind = j.kind AND c.key = j.key WHERE j.link = l.id " +
    "AND j.calib = 1 AND j.state != 'undone' AND j.side = c.hers) AS agree, " +
    "(SELECT COUNT(*) FROM judgments j WHERE j.link = l.id AND j.calib = 1 AND j.state != 'undone' " +
    "AND j.side != 'unsure') AS asked " +
    "FROM links l ORDER BY l.role = 'owner', l.state = 'off', l.made_on DESC, l.id").all()).results || [];
  return rows.map(r => ({ id: r.id, name: r.name, role: r.role, queues: queuesOf(r), state: r.state,
                          made_on: r.made_on, last_on: r.last_on || "", answers: Number(r.answers) || 0,
                          unmerged: Number(r.unmerged) || 0, agree: Number(r.agree) || 0,
                          asked: Number(r.asked) || 0 }));
}

// A link's latest answers, for "See answers": what was asked, what was said.
export async function answersOf(db, id, most = 50) {
  if (!LINK_ID.test(String(id))) return [];
  const rows = (await db.prepare(
    "SELECT j.id, j.kind, j.key, j.verdict, j.side, j.fields, j.note, j.at, j.calib, j.state, " +
    "COALESCE(i.card, c.card) AS card FROM judgments j LEFT JOIN items i ON i.kind = j.kind AND i.key = j.key " +
    "LEFT JOIN calib c ON c.kind = j.kind AND c.key = j.key WHERE j.link = ?1 AND j.state != 'undone' " +
    "ORDER BY j.id DESC LIMIT ?2").bind(id, most).all()).results || [];
  return rows.map(r => {
    const card = parse(r.card, {});
    return { id: r.id, head: String(card.head || r.key), what: String(card.what || ""), side: r.side,
             verdict: r.verdict, fields: parse(r.fields, {}), note: r.note || "", at: r.at,
             calib: Number(r.calib) === 1, state: r.state };
  });
}

// TAKE BACK: a link's answers that are kept and not merged (one, or all of
// them), marked undone, and their items open again for someone else. A
// calibration answer stays: it is the evidence of how the link agrees.
export async function takeBack(db, id, jid = null) {
  if (!LINK_ID.test(String(id))) return 0;
  if (jid !== null && !Number.isSafeInteger(Number(jid))) return 0;
  // -1 stands for every answer: no judgment has that id.
  const which = jid === null ? -1 : Number(jid);
  const r = await db.batch([
    db.prepare("UPDATE items SET state = 'open', held_by = NULL, held_until = NULL WHERE state = 'judged' " +
      "AND EXISTS (SELECT 1 FROM judgments j WHERE j.kind = items.kind AND j.key = items.key " +
      "AND j.link = ?1 AND j.state = 'kept' AND j.calib = 0 AND (?2 = -1 OR j.id = ?2))").bind(id, which),
    db.prepare("UPDATE judgments SET state = 'undone' WHERE link = ?1 AND state = 'kept' AND calib = 0 " +
      "AND (?2 = -1 OR id = ?2)").bind(id, which),
  ]);
  return r[1]?.meta?.changes ?? 0;
}
