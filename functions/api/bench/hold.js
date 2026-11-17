/*
 * POST /api/bench/hold -- the page is open: what this link holds is held for
 * another ten minutes (workers/bench/store.js hold). The page asks every two
 * minutes while it is open, so a page closed lets its items go within ten.
 *
 * Body, JSON: { t }. Answers 200 and { held: n }. A wrong token is a 404.
 */

import { hold, linkFor } from "../../../workers/bench/store.js";
import { clock, errName, json, note, notHere, plain, readJson, rightPlace, sameSite }
  from "../../../workers/bench/common.js";

const PATH = "/api/bench/hold";

export async function onRequest({ request, env }) {
  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "POST") return plain(405, "POST only\n", { Allow: "POST" });
  if (!sameSite(request, env)) return plain(403, "Forbidden\n");
  try {
    const db = env.BENCH_DB, body = await readJson(request);
    const link = body && await linkFor(db, body.t);
    if (!link || link.state === "off") return notHere();
    const n = link.state === "active" ? await hold(db, link, clock(env)) : 0;
    return json(200, { held: n });
  } catch (e) {
    note(`hold.error.${errName(e)}`);
    return json(503, { error: "unavailable" });
  }
}
