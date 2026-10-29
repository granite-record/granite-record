/*
 * GET /api/live/streams -- Live Now's own data, NOT public API (the live
 * layer's design, section 5): today's streams/<date>.json from the private
 * bucket, as the live Worker wrote it. YouTube's developer policy III.I.15
 * forbids offering an API service that gives access to YouTube API data, so
 * this answer is not documented, sends no CORS header (another site's script
 * cannot read it) and carries X-Robots-Tag: noindex.
 *
 * Today is New Hampshire's date. In the first hour after its midnight, before
 * the Worker has written the new day's file, yesterday's is served; the
 * page reads the file's own `day` and `next_check`, so it is never taken
 * for today's.
 *
 *   200  the file, cached 30 s per data centre (section 1.6), with its ETag
 *   304  If-None-Match holds the ETag
 *   404  no file, or no binding
 *   405  anything but GET or HEAD
 *   503  the bucket could not be read
 */
import { nhClock } from "../../../workers/follow/common.js";
import { answer, cached, liveStore, methodNotAllowed, notFound } from "./_store.js";

export const MAX_AGE = 30;
export const YESTERDAY_UNTIL_HOUR = 1;
const PRIVATE = { "X-Robots-Tag": "noindex" };

function yesterday(date) {
  const [y, m, d] = date.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d) - 86_400_000).toISOString().slice(0, 10);
}

// opts.now (tests): the moment to take as now.
export async function onRequest({ request, env, waitUntil }, opts = {}) {
  const store = liveStore(env);
  if (!store) return notFound(60, PRIVATE);
  if (request.method !== "GET" && request.method !== "HEAD") return methodNotAllowed(PRIVATE);
  if (new URL(request.url).pathname !== "/api/live/streams") return notFound(60, PRIVATE);
  const c = nhClock(opts.now ? new Date(+opts.now) : new Date());
  try {
    return await cached(request, { waitUntil }, MAX_AGE, async () => {
      let o = await store.get(`streams/${c.date}.json`);
      if (!o && c.hour < YESTERDAY_UNTIL_HOUR) o = await store.get(`streams/${yesterday(c.date)}.json`);
      if (!o) return notFound(60, PRIVATE);
      return answer(new Request(request.url), o, { ...PRIVATE, "Cache-Control": `public, max-age=${MAX_AGE}` });
    });
  } catch {
    return new Response("Live status could not be read\n", { status: 503, headers: {
      "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", ...PRIVATE } });
  }
}
