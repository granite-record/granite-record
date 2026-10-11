// functions/api/follow/count.js: the one figure that leaves the system is
// one integer.

import test from "node:test";
import assert from "node:assert/strict";
import { get, makeWorld, SITE } from "./fakes.js";
import { act, handlers, join, signUp } from "./flows.js";

test("the count is one integer: confirmed subscribers, nothing else", async () => {
  const w = makeWorld();
  try {
    const count = async () => {
      const r = await w.call(handlers.count, get("/api/follow/count"));
      assert.equal(r.status, 200);
      assert.match(r.body, /^\d+\n$/, "one integer and a newline, nothing else");
      assert.match(r.headers["content-type"], /^text\/plain/);
      return Number(r.body);
    };
    assert.equal(await count(), 0);
    const a = await join(w, "counted.one");
    await join(w, "counted.two", "committee", "H90");
    await signUp(w, w.address("not.yet.counted"));
    await signUp(w, a.address, "topic", "housing");        // a second record is not a second reader
    assert.equal(await count(), 2);
    await act(w, a.manage, "unsubscribe");
    assert.equal(await count(), 1);
    const p = await w.call(handlers.count, new Request(`${SITE}/api/follow/count`, { method: "POST" }));
    assert.equal(p.status, 405);
    w.d1.failWhen = () => new Error("no such table");
    const e = await w.call(handlers.count, get("/api/follow/count"));
    assert.equal(e.status, 503);
    assert.equal(e.body, "");
  } finally { w.close(); }
});
