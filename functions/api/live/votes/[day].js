/*
 * GET /api/live/votes/<YYYY-MM-DD> -- the public, provisional live votes file
 * (the live layer's design, section 5): API v1, beta. It carries no YouTube
 * data. It serves votes/<date>.json from the private bucket, as the live
 * Worker wrote it, and nothing else: only this one path shape reaches the
 * bucket, so control.json, state.json and test/ are unreachable.
 *
 *   200  the file: JSON, CORS open, cached 15 s, with its ETag
 *   304  If-None-Match holds the ETag
 *   404  no file for that date (cached 60 s), not a date, or no binding
 *   405  anything but GET or HEAD
 *   503  the bucket could not be read
 */
import { answer, cached, liveStore, methodNotAllowed, notFound } from "../_store.js";

export const MAX_AGE = 15;
const DAY = /^(\d{4})-(\d{2})-(\d{2})$/;
const CORS = { "Access-Control-Allow-Origin": "*" };

// A real calendar date written YYYY-MM-DD, or null.
export function realDay(s) {
  const m = DAY.exec(String(s || ""));
  if (!m) return null;
  const t = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return t.toISOString().slice(0, 10) === s ? s : null;
}

export async function onRequest({ request, env, params, waitUntil }) {
  const store = liveStore(env);
  if (!store) return notFound(60, CORS);
  if (request.method !== "GET" && request.method !== "HEAD") return methodNotAllowed(CORS);
  const day = realDay(Array.isArray(params && params.day) ? params.day.join("/") : params && params.day);
  if (!day) return notFound(60, CORS);
  try {
    return await cached(request, { waitUntil }, MAX_AGE, async () => {
      const o = await store.get(`votes/${day}.json`);
      if (!o) return notFound(60, CORS);
      return answer(new Request(request.url), o, { ...CORS, "Cache-Control": `public, max-age=${MAX_AGE}` });
    });
  } catch {
    return new Response("The live votes could not be read\n", { status: 503, headers: {
      "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store", ...CORS } });
  }
}
