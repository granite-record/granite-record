/*
 * GET /api/follow/count -- the one figure that leaves the follow database.
 *
 * The number of confirmed subscribers, as one integer and a newline, and
 * nothing else: not the follows, not the records, not a date. Only a
 * confirmation makes a subscriber, so this counts rows, and a request still
 * waiting for its confirmation is not in it.
 */

import { countConfirmed } from "../../../workers/follow/store.js";
import { errName, note, notHere, plain, rightPlace } from "../../../workers/follow/common.js";

const PATH = "/api/follow/count";

export async function onRequest({ request, env }) {
  if (!env.FOLLOW_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "GET" && request.method !== "HEAD")
    return plain(405, "GET only\n", { Allow: "GET" });
  try {
    return plain(200, `${await countConfirmed(env.FOLLOW_DB)}\n`);
  } catch (e) {
    note(`count.error.${errName(e)}`);
    return plain(503, "");
  }
}
