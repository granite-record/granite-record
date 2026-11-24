/*
 * POST /api/bench/asks -- the owner's Your input tab, which only her own link
 * opens (the owner, 23 November 2026: "a separate category for me giving
 * feedback on new features or visual changes that need my input"): what waits
 * on her word, from the list the manager keeps (loaded by bench_pack.py
 * --asks), and her answer to one entry, with a note. Any other link, a wrong
 * token, or a link turned off, is the same 404 as no bench at all, as
 * /api/bench/links answers.
 *
 * Body, JSON of at most ASKS_BODY (8 KiB, for a note of 2,000 characters;
 * every other route of the bench keeps MAX_BODY): { t, action, ... }:
 *   list                         every entry not withdrawn, in the list's
 *                                order, each with her latest answer, and how
 *                                many wait
 *   answer   key, answer, note   her answer, one of the entry's own, kept
 *                                beside her earlier ones; the list again
 * Answers 200; 400 for an answer the entry does not offer or a note over
 * 2,000 characters; 409 for an entry no longer asked; 429 within a second of
 * her last. Her notes stay here and reach the laptop only through
 * bench_pull.py --asks (private/asks/answers.jsonl): never the ledger, never
 * the open data.
 */

import { cleanNote } from "../report.js";
import { ASK_NOTE_MOST, askAnswer, askList, askWaiting, linkFor, touch } from "../../../workers/bench/store.js";
import { ASKS_BODY, clock, errName, json, note, notHere, plain, readJson, rightPlace, sameSite }
  from "../../../workers/bench/common.js";

const PATH = "/api/bench/asks";
const STATUS = { gone: 409, bad: 400, long: 400, fast: 429 };

// A note of several lines: the report box's rules (functions/api/report.js
// cleanNote) -- NFKC, the characters that hide text taken out and said to have
// been, control characters out but a line break and a tab, spaces before a
// line break and a third blank line gone, the ends trimmed -- kept to `most`
// characters where cleanNote keeps 1,000. Which characters hide text is
// cleanNote's own answer, asked of each one, so that list lives in report.js
// alone.
export function longNote(raw, most) {
  const t = String(raw ?? "").normalize("NFKC").replace(/\r\n?/g, "\n");
  let out = "", hidden = false;
  for (const ch of t) {
    const cp = ch.codePointAt(0);
    if (cp >= 0x80 && cleanNote(ch).hidden) { hidden = true; continue; }
    if ((cp < 0x20 && cp !== 0x0A && cp !== 0x09) || (cp >= 0x7F && cp <= 0x9F)) continue;
    out += ch;
  }
  out = out.replace(/[ \t]+\n/g, "\n").replace(/\n{3,}/g, "\n\n").trim();
  return { text: out.slice(0, most), hidden: hidden ? 1 : 0 };
}

export async function onRequest({ request, env }) {
  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST") return plain(405, "POST only\n", { Allow: "POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const db = env.BENCH_DB, body = await readJson(request, ASKS_BODY);
    const link = body && await linkFor(db, body.t);
    if (!link || link.role !== "owner" || link.state !== "active") return notHere();
    const now = clock(env), action = String(body.action || "list");
    await touch(db, link, now);
    if (action === "answer") {
      const raw = typeof body.note === "string" ? body.note : "";
      const r = raw.length > ASK_NOTE_MOST ? { ok: false, why: "long" }
        : await askAnswer(db, link, { key: body.key, answer: body.answer, note: longNote(raw, ASK_NOTE_MOST) }, now);
      note(r.ok ? "asks.answered" : `asks.refused.${r.why}`);
      const list = { asks: await askList(db), waiting: await askWaiting(db) };
      return r.ok ? json(200, { saved: { answer: r.answer }, ...list }) : json(STATUS[r.why] || 400, { why: r.why, ...list });
    }
    if (action !== "list") return json(400, { why: "no such action" });
    const asks = await askList(db);
    note("asks.list", asks.length);
    return json(200, { asks, waiting: await askWaiting(db) });
  } catch (e) {
    note(`asks.error.${errName(e)}`);
    return json(503, { error: "unavailable" });
  }
}
