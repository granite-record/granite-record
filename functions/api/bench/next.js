/*
 * POST /api/bench/next -- what the bench page shows: the items this link
 * holds, two at most, each claimed by one statement as it is needed
 * (workers/bench/store.js next), the group being worked on and how far along
 * every queue is.
 *
 * Body, JSON: { t, queue }, t the token from after "#" in the link, queue
 * one of the link's queues or "mix". A wrong token, or a link turned off, is
 * the same 404 as no bench at all. Every route of the bench answers 404 until
 * BENCH_DB is bound (workers/bench/common.js).
 */

import { linkFor, touch } from "../../../workers/bench/store.js";
import { clock, errName, json, note, notHere, plain, readJson, rightPlace, sameSite }
  from "../../../workers/bench/common.js";
import { chosenQueue, view } from "../../../workers/bench/view.js";

const PATH = "/api/bench/next";

export async function onRequest({ request, env }) {
  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST") return plain(405, "POST only\n", { Allow: "POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const db = env.BENCH_DB, body = await readJson(request);
    const link = body && await linkFor(db, body.t);
    if (!link || link.state === "off") return notHere();
    const now = clock(env);
    await touch(db, link, now);
    const v = await view(db, link, chosenQueue(body, link), now);
    note("next.items", v.items.length);
    return json(200, v);
  } catch (e) {
    note(`next.error.${errName(e)}`);
    return json(503, { error: "unavailable" });
  }
}
