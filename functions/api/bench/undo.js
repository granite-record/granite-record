/*
 * POST /api/bench/undo -- this link's latest answer, while it is not merged
 * and not taken back already, back: its item is held for this link again and
 * is the first the page is given (workers/bench/store.js undo). A second
 * Undo takes nothing more.
 *
 * Body, JSON: { t, queue }. Answers 200 and the page's view, with "undone"
 * true when an answer was taken back. A wrong token is a 404.
 */

import { linkFor, undo } from "../../../workers/bench/store.js";
import { clock, errName, json, note, notHere, plain, readJson, rightPlace, sameSite }
  from "../../../workers/bench/common.js";
import { chosenQueue, view } from "../../../workers/bench/view.js";

const PATH = "/api/bench/undo";

export async function onRequest({ request, env }) {
  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST") return plain(405, "POST only\n", { Allow: "POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const db = env.BENCH_DB, body = await readJson(request);
    const link = body && await linkFor(db, body.t);
    if (!link || link.state === "off") return notHere();
    const now = clock(env);
    const back = link.state === "active" ? await undo(db, link, now) : null;
    note(back ? "undo.done" : "undo.nothing");
    return json(200, { undone: !!back, ...(await view(db, link, chosenQueue(body, link), now, back)) });
  } catch (e) {
    note(`undo.error.${errName(e)}`);
    return json(503, { error: "unavailable" });
  }
}
