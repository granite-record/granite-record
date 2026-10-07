// functions/api/follow/unsubscribe.js: one click deletes the address and
// everything followed, at once, whatever Origin the click carries; a look at
// the link deletes nothing; the button works as a real browser presses it.

import test from "node:test";
import assert from "node:assert/strict";
import { run } from "../../workers/follow/sender.js";
import { get, lastMailTo, leaks, makeWorld, postForm, SITE, tokensIn } from "./fakes.js";
import { handlers, join, signUp, snapshot, view } from "./flows.js";

// A subscriber who joined on Sunday the 4th and had Monday's update, so holds
// an unsubscribe link: the sender's email is where those come from.
const world = () => makeWorld({ now: "2026-10-04T15:00:00Z" });
async function updated(w, name) {
  const s = await join(w, name);
  await signUp(w, s.address, "member", "990001");          // and a request still waiting
  w.at("2026-10-05T12:00:00Z");
  await run(w.env, w.now);
  return { ...s, ...tokensIn(lastMailTo(w, s.address)) };
}

const oneClick = (u, body = "List-Unsubscribe=One-Click") =>
  new Request(`${SITE}/api/follow/unsubscribe?u=${u}`, { method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" }, body });

test("the mail provider's one-click post deletes the address and everything with it", async () => {
  const w = world();
  try {
    const s = await updated(w, "one.click");
    assert.equal(s.header, s.unsub, "the header and the body carry the same unsubscribe link");
    const r = await w.call(handlers.unsubscribe, oneClick(s.header));
    assert.equal(r.status, 200);
    for (const t of ["subscribers", "follows", "pending"])
      assert.equal(w.d1.rows(t).length, 0, t);
    assert.equal((await view(w, s.manage)).status, 400);
    // Again, or with a link that never was: still 200, as RFC 8058 expects.
    assert.equal((await w.call(handlers.unsubscribe, oneClick(s.header))).status, 200);
    assert.equal((await w.call(handlers.unsubscribe, oneClick("B".repeat(43)))).status, 200);
    assert.ok(w.logs.lines.includes("follow unsubscribe.one-click-matched-nothing"),
      "a one-click that deleted nothing says so in the log");
    assert.deepEqual(leaks(w), []);
  } finally { w.close(); }
});

test("the link in the body: a look deletes nothing, the button deletes everything", async () => {
  const w = world();
  try {
    const s = await updated(w, "body.link");
    const before = snapshot(w);
    const g = await w.call(handlers.unsubscribe, get("/api/follow/unsubscribe"));
    assert.equal(g.status, 200);
    assert.match(g.body, /Unsubscribe and delete my address/);
    assert.match(g.body, /location\.hash/);
    const h = await w.call(handlers.unsubscribe, get("/api/follow/unsubscribe", `?u=${s.unsub}`));
    assert.match(h.body, new RegExp(`name="u" value="${s.unsub}"`), "a client that GETs the header's address gets the button");
    assert.deepEqual(snapshot(w), before, "looking deleted nothing");
    const r = await w.call(handlers.unsubscribe, postForm("/api/follow/unsubscribe", { u: s.unsub }));
    assert.match(r.body, /Your address has been deleted/);
    assert.match(r.body, /deleted from our database/);
    assert.doesNotMatch(r.body + h.body, /for good|Nothing is kept/);
    for (const t of ["subscribers", "follows", "pending"])
      assert.equal(w.d1.rows(t).length, 0, t);
  } finally { w.close(); }
});

test("the button works as a browser presses it, from the body's link and from the header's", async () => {
  const browser = { origin: "null", fetchSite: "same-origin" };
  let w = world();
  try {
    const s = await updated(w, "browser.body");
    const r = await w.call(handlers.unsubscribe, postForm("/api/follow/unsubscribe", { u: s.unsub }, browser));
    assert.match(r.body, /Your address has been deleted/);
    assert.equal(w.d1.rows("subscribers").length, 0);
  } finally { w.close(); }
  // A mail client that opens the header's address in a browser: its page's button.
  w = world();
  try {
    const t = await updated(w, "browser.header");
    const page = await w.call(handlers.unsubscribe, get("/api/follow/unsubscribe", `?u=${t.header}`));
    assert.match(page.body, /<form method="post" action="\/api\/follow\/unsubscribe">/);
    const q = await w.call(handlers.unsubscribe, postForm("/api/follow/unsubscribe", { u: t.header },
      { ...browser, query: `?u=${t.header}` }));
    assert.match(q.body, /Your address has been deleted/);
    assert.equal(w.d1.rows("subscribers").length, 0);
  } finally { w.close(); }
});

test("a one-click post deletes whatever Origin it carries: the token is the authority", async () => {
  // RFC 8058's body form-encoded from a provider's server, from one that sends
  // an Origin, from one that sends "null", and as multipart/form-data.
  const fd = new FormData();
  fd.set("List-Unsubscribe", "One-Click");
  for (const [name, headers, body] of [
    ["from.provider", { Origin: "https://mail.example.com" }, null],
    ["from.null", { Origin: "null" }, null],
    ["from.multipart", {}, fd]]) {
    const w = world();
    try {
      const s = await updated(w, name);
      const r = await w.call(handlers.unsubscribe, new Request(`${SITE}/api/follow/unsubscribe?u=${s.header}`,
        { method: "POST", body: body ?? "List-Unsubscribe=One-Click",
          headers: body ? headers : { "Content-Type": "application/x-www-form-urlencoded", ...headers } }));
      assert.equal(r.status, 200, name);
      assert.equal(w.d1.rows("subscribers").length, 0, name);
    } finally { w.close(); }
  }
});

test("a button post from another site deletes nothing", async () => {
  const w = world();
  try {
    const s = await updated(w, "not.from.here");
    const before = snapshot(w);
    for (const opts of [{ origin: "https://evil.example.com" }, { fetchSite: "cross-site" },
                        { origin: "null", fetchSite: "cross-site" }]) {
      const r = await w.call(handlers.unsubscribe, postForm("/api/follow/unsubscribe", { u: s.unsub }, opts));
      assert.equal(r.status, 403);
      const q = await w.call(handlers.unsubscribe,
        postForm("/api/follow/unsubscribe", { u: s.unsub }, { ...opts, query: `?u=${s.unsub}` }));
      assert.equal(q.status, 403, "nor its post to the header's address with any body but the RFC's");
    }
    assert.equal((await w.call(handlers.unsubscribe, oneClick(s.header, "anything else"))).status, 400);
    assert.deepEqual(snapshot(w), before);
  } finally { w.close(); }
});

test("an unsubscribe link opens nothing but this, and a manage link is not one", async () => {
  const w = world();
  try {
    const s = await updated(w, "two.kinds");
    assert.equal((await view(w, s.unsub)).status, 400, "an unsubscribe link cannot open the manage page");
    const r = await w.call(handlers.unsubscribe, postForm("/api/follow/unsubscribe", { u: s.manage }));
    assert.match(r.body, /no longer current/);
    assert.equal(w.d1.rows("subscribers").length, 1);
  } finally { w.close(); }
});
