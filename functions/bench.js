/*
 * GET /bench -- the shared bench's one page (workers/bench/page.js), a
 * Function's answer rather than a file: nothing of it is in site/, no page
 * links to it, it is not in the sitemap, and robots.txt does not name it,
 * which would advertise it. Opened as /bench#<token> from a link the owner
 * sends; without a link that works, the page says only that it needs one.
 *
 * Answers 404, as every route of the bench does, until BENCH_DB is bound in
 * wrangler.toml for the environment: the binding is the switch.
 */

import { notHere, plain, rightPlace } from "../workers/bench/common.js";
import { benchPage } from "../workers/bench/page.js";

const PATH = "/bench";

export async function onRequest({ request, env }) {
  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();
  if (request.method !== "GET" && request.method !== "HEAD") return plain(405, "GET only\n", { Allow: "GET" });
  return benchPage();
}
