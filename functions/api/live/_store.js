/*
 * The live Functions' one way into the private R2 bucket graniterecord-live,
 * bound as LIVE (the live layer's design, section 6.4). READ-ONLY BY
 * CONSTRUCTION: this is the only file under functions/api/live/ that names
 * env.LIVE, and what it hands back can get and head, nothing else. Previews
 * read the production bucket, accepted explicitly by the person; this facade
 * is why that is safe. preflight fails if any file here calls put, delete,
 * list or a multipart upload, or names env.LIVE outside this file.
 *
 * Without the binding (forks, local builds, a deploy before the bucket
 * exists) it is null, and every live Function answers 404.
 */
export function liveStore(env) {
  const bucket = env && env.LIVE;
  if (!bucket) return null;
  return Object.freeze({
    get: key => bucket.get(key),
    head: key => bucket.head(key),
  });
}

// The headers every live answer carries.
export const JSON_TYPE = "application/json; charset=utf-8";
export const NOSNIFF = { "X-Content-Type-Options": "nosniff" };

// Whether If-None-Match holds this ETag: weak or strong, one of a list, or *.
export function held(request, etag) {
  const h = request.headers.get("If-None-Match");
  if (!h || !etag) return false;
  return h.split(",").map(x => x.trim().replace(/^W\//, "")).some(x => x === "*" || x === etag);
}

export function notFound(maxAge = 60, extra = {}) {
  return new Response("Not found\n", { status: 404, headers: {
    "Content-Type": "text/plain; charset=utf-8", "Cache-Control": `public, max-age=${maxAge}`, ...NOSNIFF, ...extra } });
}

export function methodNotAllowed(extra = {}) {
  return new Response("GET or HEAD only\n", { status: 405, headers: {
    "Content-Type": "text/plain; charset=utf-8", Allow: "GET, HEAD", ...NOSNIFF, ...extra } });
}

// An object from the store as an answer: its JSON, its ETag, a 304 when the
// reader already holds it, and the caller's headers. HEAD gets no body.
export async function answer(request, object, headers) {
  const etag = object.httpEtag;
  const base = { "Content-Type": JSON_TYPE, ETag: etag, ...NOSNIFF, ...headers };
  if (held(request, etag)) {
    return new Response(null, { status: 304, headers: base });
  }
  const body = request.method === "HEAD" ? null : await object.text();
  return new Response(body, { status: 200, headers: base });
}

// A copy per data centre through the Cache API, for `seconds`: the bucket is
// read at most once each while readers poll. `make()` builds the answer; a
// 304 is worked out per request from the copy's ETag.
export async function cached(request, ctx, seconds, make) {
  const cache = globalThis.caches && globalThis.caches.default;
  // Keyed on the address without its query: ?r=1, ?r=2 ... are one copy, and
  // never a way round it to the bucket.
  const u = new URL(request.url);
  const key = new Request(u.origin + u.pathname, { method: "GET" });
  let full = cache ? await cache.match(key) : null;
  if (!full) {
    full = await make();
    if (cache && full.status === 200) {
      const copy = full.clone();
      const put = cache.put(key, copy);
      if (ctx && ctx.waitUntil) ctx.waitUntil(put); else await put;
    }
  }
  if (full.status !== 200) return full;
  if (held(request, full.headers.get("ETag"))) {
    return new Response(null, { status: 304, headers: full.headers });
  }
  if (request.method === "HEAD") return new Response(null, { status: 200, headers: full.headers });
  return full;
}
