/*
 * POST /api/bench/links -- the owner's Links tab, which only her own link
 * opens: every link with what it has answered, a new link, and pause,
 * resume, take back and turn off. Any other link, a wrong token, or a link
 * turned off, is the same 404 as no bench at all.
 *
 * Body, JSON: { t, action, ... }:
 *   list                         every link: name, queues, state, the days made
 *                                and last used, answers, not merged yet, and
 *                                agreement with hers on calibration items
 *   make      name, queues       a contributor's link. Its token is in this
 *                                answer once, for the page to make the address
 *                                and the share sheet to send; only its hash is
 *                                kept, so it cannot be shown again
 *   pause | resume | off  id     a contributor's link; never her own, and a
 *                                link turned off stays off
 *   takeback  id                 that link's answers not merged yet, undone,
 *                                their items open again (calibration answers
 *                                stay: they are how it agrees with hers)
 *   answers   id                 its latest answers, for "See answers"
 *   takeone   id, answer         one of them back
 * The merge is never here: it is bench_pull.py's, on the laptop.
 */

import { answersOf, linkFor, linkList, makeLink, setState, takeBack, touch }
  from "../../../workers/bench/store.js";
import { clock, errName, json, note, notHere, plain, readJson, rightPlace, sameSite }
  from "../../../workers/bench/common.js";

const PATH = "/api/bench/links";
const STATES = { pause: "paused", resume: "active", off: "off" };

export async function onRequest({ request, env }) {
  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST") return plain(405, "POST only\n", { Allow: "POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const db = env.BENCH_DB, body = await readJson(request);
    const link = body && await linkFor(db, body.t);
    if (!link || link.role !== "owner" || link.state !== "active") return notHere();
    const now = clock(env), action = String(body.action || "list");
    await touch(db, link, now);
    if (action === "make") {
      const made = await makeLink(db, { name: body.name, queues: body.queues }, now);
      if (!made) return json(400, { why: "a name and at least one kind to judge" });
      note("links.made");
      return json(200, { made, links: await linkList(db) });
    }
    if (Object.hasOwn(STATES, action)) {
      const n = await setState(db, body.id, STATES[action]);
      note(`links.${action}`, n);
      return json(n ? 200 : 409, { changed: n, links: await linkList(db) });
    }
    if (action === "takeback" || action === "takeone") {
      const n = await takeBack(db, body.id, action === "takeone" ? body.answer : null);
      note(`links.${action}`, n);
      return json(200, { taken: n, links: await linkList(db) });
    }
    if (action === "answers") return json(200, { answers: await answersOf(db, body.id) });
    if (action !== "list") return json(400, { why: "no such action" });
    return json(200, { links: await linkList(db) });
  } catch (e) {
    note(`links.error.${errName(e)}`);
    return json(503, { error: "unavailable" });
  }
}
