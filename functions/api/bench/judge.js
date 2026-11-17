/*
 * POST /api/bench/judge -- an answer, kept, and the page's next items.
 *
 * Body, JSON: { t, queue, ref, answer, note }. `ref` names an item the link
 * holds; `answer` is { answer: "yes" | "no" | "unsure", better } for a claim
 * and { steps: [{ answer, mark }] } for a moment (workers/bench/store.js
 * toLedger). The note is cleaned as the report box cleans a reader's words
 * (functions/api/report.js cleanNote) and kept to one line of 280
 * characters; it becomes open data once the owner merges it, which the page
 * says before it is written.
 *
 * Answers: 200 and the page's next view; 409 when the item is no longer this
 * link's (answered already, or its hold lapsed) or the link is paused; 400
 * for an answer the item does not take; 429 within a second of the last, or
 * when the day's answers are all given. A wrong token is a 404.
 */

import { cleanNote } from "../report.js";
import { NOTE_MOST, judge, linkFor, touch } from "../../../workers/bench/store.js";
import { clock, errName, json, note, notHere, oneNote, plain, readJson, rightPlace, sameSite }
  from "../../../workers/bench/common.js";
import { chosenQueue, view } from "../../../workers/bench/view.js";

const PATH = "/api/bench/judge";
const STATUS = { gone: 409, bad: 400, fast: 429, full: 429 };

export async function onRequest({ request, env }) {
  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST") return plain(405, "POST only\n", { Allow: "POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const db = env.BENCH_DB, body = await readJson(request);
    const link = body && await linkFor(db, body.t);
    if (!link || link.state === "off") return notHere();
    const now = clock(env), queue = chosenQueue(body, link);
    if (link.state !== "active") return json(409, { why: "paused", ...(await view(db, link, queue, now)) });
    const said = oneNote(cleanNote(typeof body.note === "string" ? body.note : ""), NOTE_MOST);
    const r = await judge(db, link, { ref: body.ref, answer: body.answer, note: said }, now);
    if (!r.ok) {
      note(`judge.refused.${r.why}`);
      return json(STATUS[r.why] || 400, { why: r.why, ...(await view(db, link, queue, now)) });
    }
    await touch(db, link, now);
    note("judge.kept");
    return json(200, { saved: { side: r.side }, ...(await view(db, link, queue, now)) });
  } catch (e) {
    note(`judge.error.${errName(e)}`);
    return json(503, { error: "unavailable" });
  }
}
